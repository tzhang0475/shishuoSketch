#!/usr/bin/env python3
"""Validate the DS2 seven-Story generated pilot and its protected boundary."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ds1_common import read_json, sha256_file  # noqa: E402
from ds2_common import (  # noqa: E402
    ALLOWED_SOURCE_LAYERS,
    FINAL_FIELDS,
    MAX_TOP_K,
    MAX_TOOL_ROUNDS,
    OUTPUT_DIR,
    PILOT_STORIES,
    REVIEW_PATH,
    ROOT,
    SEARCHED_SOURCE_PATHS,
    SUMMARY_PATH,
    build_evidence_registry,
    build_story_minimal_input,
    protected_hashes,
    source_hashes,
    stable_json,
    validate_ds2_result,
)


FORBIDDEN_PATH_PARTS = (
    "data/generated",
    "site/public/generated",
    "data/annotation",
    "irr0",
    "model-output",
)


def _forbidden(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return any(part in normalized for part in FORBIDDEN_PATH_PARTS)


def _hit_key(hit: Mapping[str, Any]) -> str:
    return "|".join(
        (
            str(hit.get("source", "")),
            stable_json(hit.get("locator", {})),
            "".join(str(hit.get("quote", "")).split()),
        )
    )


def _validate_trace(trace: Mapping[str, Any], registry: Mapping[str, Any], story_id: str) -> list[str]:
    errors: list[str] = []
    if trace.get("schema") != "ds2-retrieval-trace" or trace.get("stage") != "DS2":
        errors.append(f"{story_id}: trace schema/stage is invalid")
    if trace.get("story_id") != story_id or trace.get("candidate_status") != "candidate":
        errors.append(f"{story_id}: trace identity/status is invalid")
    if trace.get("canonical_write_back") is not False:
        errors.append(f"{story_id}: trace permits canonical write-back")
    if trace.get("source_hashes") != source_hashes(ROOT):
        errors.append(f"{story_id}: trace source hashes changed")
    expected_paths = sorted(SEARCHED_SOURCE_PATHS)
    if trace.get("searched_source_paths") != expected_paths or trace.get("allowed_source_paths") != expected_paths:
        errors.append(f"{story_id}: trace source boundary is not the registered corpus")
    if any(_forbidden(str(path)) for path in expected_paths):
        errors.append("registered source boundary contains a forbidden generated path")

    steps = trace.get("steps", [])
    if not isinstance(steps, list):
        return errors + [f"{story_id}: trace steps are not an array"]
    prior_returned: set[str] = set()
    for index, step in enumerate(steps):
        if not isinstance(step, Mapping):
            errors.append(f"{story_id}: steps[{index}] is not an object")
            continue
        name = step.get("tool_name")
        if name not in {"search_local_evidence", "open_local_evidence"}:
            errors.append(f"{story_id}: steps[{index}] uses an unsupported tool")
            continue
        round_no = step.get("round")
        if not isinstance(round_no, int) or not 1 <= round_no <= MAX_TOOL_ROUNDS:
            errors.append(f"{story_id}: steps[{index}] exceeds tool-round limit")
        if name == "search_local_evidence":
            args = step.get("arguments", {})
            top_k = args.get("top_k", MAX_TOP_K) if isinstance(args, Mapping) else None
            if not isinstance(top_k, int) or not 1 <= top_k <= MAX_TOP_K:
                errors.append(f"{story_id}: steps[{index}] exceeds top_k limit")
            refs = step.get("returned_evidence_refs", [])
            hits = step.get("returned_hits", [])
            if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
                errors.append(f"{story_id}: steps[{index}] returned refs are invalid")
                refs = []
            if len(refs) > MAX_TOP_K:
                errors.append(f"{story_id}: steps[{index}] returned more than five hits")
            if not isinstance(hits, list) or len(hits) != len(refs):
                errors.append(f"{story_id}: steps[{index}] hit/ref counts differ")
                hits = []
            if len({_hit_key(hit) for hit in hits if isinstance(hit, Mapping)}) != len(hits):
                errors.append(f"{story_id}: steps[{index}] contains duplicate passages")
            if {hit.get("evidence_ref") for hit in hits if isinstance(hit, Mapping)} != set(refs):
                errors.append(f"{story_id}: steps[{index}] hit/ref identity differs")
            if not isinstance(step.get("returned_scores"), Mapping) or set(step["returned_scores"]) != set(refs):
                errors.append(f"{story_id}: steps[{index}] scores differ from refs")
            for ref in refs:
                if ref not in registry:
                    errors.append(f"{story_id}: unknown returned evidence ref {ref}")
                else:
                    prior_returned.add(ref)
            raw = step.get("raw_match_count")
            dedup = step.get("deduplicated_match_count")
            duplicates = step.get("duplicate_match_count")
            if not all(isinstance(value, int) for value in (raw, dedup, duplicates)) or not (raw >= dedup >= len(refs) and duplicates == raw - dedup):
                errors.append(f"{story_id}: deduplication counts are invalid")
            for hit in hits:
                if isinstance(hit, Mapping):
                    if hit.get("project_status") not in {"accepted", "not_materialized", "disputed", "unknown"}:
                        errors.append(f"{story_id}: evidence hit lacks project status")
                    if any(_forbidden(str(value)) for value in hit.values() if isinstance(value, str)):
                        errors.append(f"{story_id}: generated/model path leaked into hit")
        else:
            args = step.get("arguments", {})
            ref = args.get("evidence_ref") if isinstance(args, Mapping) else None
            status = step.get("open_status")
            if status == "success":
                if ref not in prior_returned or step.get("evidence_refs_opened") != [ref]:
                    errors.append(f"{story_id}: unsafe successful open at step {index}")
                opened = step.get("opened_results", [])
                if not isinstance(opened, list) or len(opened) != 1 or not isinstance(opened[0], Mapping) or opened[0].get("evidence_ref") != ref:
                    errors.append(f"{story_id}: successful open result is invalid")
            elif status == "rejected":
                if not step.get("error") or step.get("evidence_refs_opened"):
                    errors.append(f"{story_id}: rejected open trace is invalid")
            else:
                errors.append(f"{story_id}: open status is missing")

    loop = trace.get("loop_summary", {})
    if not isinstance(loop, Mapping):
        errors.append(f"{story_id}: loop summary is missing")
    else:
        if loop.get("tool_rounds", 0) > MAX_TOOL_ROUNDS:
            errors.append(f"{story_id}: loop exceeded six rounds")
        returned = set(loop.get("returned_evidence_refs", []))
        if returned != prior_returned or not returned.issubset(set(registry)):
            errors.append(f"{story_id}: loop returned refs differ from trace")
        if not set(loop.get("opened_evidence_refs", [])).issubset(prior_returned):
            errors.append(f"{story_id}: loop opened an unreturned ref")
        if loop.get("total_returned_chars", 0) > 24000:
            errors.append(f"{story_id}: evidence text budget exceeded")
    if not any(step.get("tool_name") == "search_local_evidence" and step.get("returned_evidence_refs") for step in steps if isinstance(step, Mapping)):
        errors.append(f"{story_id}: no useful local search was recorded")
    return errors


def _validate_candidate(candidate: Mapping[str, Any], trace: Mapping[str, Any], registry: Mapping[str, Any], story_id: str) -> list[str]:
    errors: list[str] = []
    if candidate.get("schema") != "ds2-context-candidate" or candidate.get("stage") != "DS2":
        errors.append(f"{story_id}: candidate schema/stage is invalid")
    if candidate.get("story_id") != story_id or candidate.get("candidate_status") != "candidate":
        errors.append(f"{story_id}: candidate identity/status is invalid")
    if candidate.get("run_type") != "real_model" or candidate.get("provider") != "deepseek":
        errors.append(f"{story_id}: candidate is not a real DeepSeek candidate")
    if candidate.get("canonical_write_back") is not False:
        errors.append(f"{story_id}: candidate permits canonical write-back")
    refs = candidate.get("retrieved_evidence_refs", [])
    opened = candidate.get("opened_evidence_refs", [])
    if not isinstance(refs, list) or not set(refs).issubset(registry):
        errors.append(f"{story_id}: candidate has unknown evidence refs")
        refs = []
    if not isinstance(opened, list) or not set(opened).issubset(set(refs)):
        errors.append(f"{story_id}: candidate opened refs are unsafe")
    if candidate.get("retrieval_trace") != f"data/generated/ds2/{story_id}-trace.json":
        errors.append(f"{story_id}: candidate trace path is not repository-relative")
    errors.extend(validate_ds2_result(candidate.get("result"), refs, registry))
    if candidate.get("validation_errors"):
        errors.append(f"{story_id}: candidate contains validation errors")
    if candidate.get("deduplication") != trace.get("deduplication"):
        errors.append(f"{story_id}: candidate/trace deduplication differs")
    return errors


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    registry, _ = build_evidence_registry(root)
    for record in registry.values():
        if record.source_layer not in ALLOWED_SOURCE_LAYERS or _forbidden(record.source_path):
            errors.append(f"controlled registry contains a forbidden source: {record.source_path}")
    if [build_story_minimal_input(root, story_id).get("story_id") for story_id in PILOT_STORIES] != list(PILOT_STORIES):
        errors.append("pilot Story universe is not exact")

    manifest_path = root / OUTPUT_DIR / "manifest.json"
    summary_path = root / SUMMARY_PATH
    review_path = root / REVIEW_PATH
    if not manifest_path.is_file() or not summary_path.is_file() or not review_path.is_file():
        return sorted(errors + ["DS2 output/summary/review artifacts are incomplete"])
    manifest = read_json(root, OUTPUT_DIR / "manifest.json")
    if manifest.get("pilot_stories") != list(PILOT_STORIES) or manifest.get("canonical_write_back") is not False:
        errors.append("DS2 manifest scope/write-back contract is invalid")
    if manifest.get("source_hashes") != source_hashes(root):
        errors.append("DS2 source hashes changed")
    if manifest.get("protected_hashes") != protected_hashes(root):
        errors.append("protected canonical/Gold/frontend/research hashes changed")

    review = read_json(root, REVIEW_PATH)
    expected_review_keys = {"story_id", "evidence_seeking", "scene_reconstruction", "relationship_understanding", "context_selection", "restraint", "notes"}
    if [row.get("story_id") for row in review.get("records", [])] != list(PILOT_STORIES):
        errors.append("DS2 review template Story universe is not exact")
    for row in review.get("records", []):
        if set(row) != expected_review_keys:
            errors.append(f"review record has unexpected fields: {row.get('story_id')}")

    summary = read_json(root, SUMMARY_PATH)
    if summary.get("pilot_stories") != list(PILOT_STORIES):
        errors.append("DS2 summary Story universe is not exact")
    records = summary.get("records", [])
    if [row.get("story_id") for row in records] != list(PILOT_STORIES):
        errors.append("DS2 summary records are incomplete or reordered")

    for story_id in PILOT_STORIES:
        candidate_path = OUTPUT_DIR / f"{story_id}.json"
        trace_path = OUTPUT_DIR / f"{story_id}-trace.json"
        if not (root / trace_path).is_file():
            errors.append(f"{story_id}: trace is missing")
            continue
        trace = read_json(root, trace_path)
        if trace.get("execution_status") == "failed":
            if (root / candidate_path).is_file():
                errors.append(f"{story_id}: failed run left a candidate")
            continue
        if not (root / candidate_path).is_file():
            errors.append(f"{story_id}: successful run has no candidate")
            continue
        candidate = read_json(root, candidate_path)
        errors.extend(_validate_trace(trace, registry, story_id))
        errors.extend(_validate_candidate(candidate, trace, registry, story_id))
        if manifest.get("candidate_hashes", {}).get(story_id) != sha256_file(root, candidate_path):
            errors.append(f"{story_id}: candidate hash does not match manifest")
        if manifest.get("trace_hashes", {}).get(story_id) != sha256_file(root, trace_path):
            errors.append(f"{story_id}: trace hash does not match manifest")
    return sorted(set(errors))


def main() -> int:
    errors = validate(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("DS2 validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
