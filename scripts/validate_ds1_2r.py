#!/usr/bin/env python3
"""Validate DS1.2R evidence/identity hardening artifacts."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ds1_2_common import (  # noqa: E402
    ALLOWED_SOURCE_LAYERS,
    ROOT,
    SEARCHED_SOURCE_PATHS,
    STORY_ID,
    build_evidence_registry,
    build_minimal_story_input,
    source_hashes,
    stable_json,
)
from ds1_2r_common import (  # noqa: E402
    CANDIDATE_PATH,
    CONFLICT_TYPES,
    EPISTEMIC_STATUSES,
    MANIFEST_PATH,
    MAX_TOP_K,
    MAX_TOOL_ROUNDS,
    TRACE_PATH,
    _fold,
    protected_hashes,
    required_identity_conflict_present,
    validate_final_result_r,
)
from ds1_common import read_json, sha256_file  # noqa: E402
try:
    from scripts import sfh2r_contract  # noqa: E402
except ImportError:  # direct execution from scripts/
    import sfh2r_contract  # type: ignore  # noqa: E402


FORBIDDEN_PATH_PARTS = ("data/generated", "site/public/generated", "data/annotation", "irr0", "model-output")


def _forbidden(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return any(part in normalized for part in FORBIDDEN_PATH_PARTS)


def _hit_key(hit: Mapping[str, Any]) -> str:
    return "|".join(
        (
            _fold(str(hit.get("source", ""))),
            stable_json(hit.get("locator", {})),
            re.sub(r"\s+", "", _fold(str(hit.get("quote", "")))),
        )
    )


def _validate_trace(trace: Mapping[str, Any], registry: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if trace.get("schema") != "ds1-2r-retrieval-trace" or trace.get("stage") != "DS1.2R":
        errors.append("trace schema/stage is invalid")
    if trace.get("story_id") != STORY_ID or trace.get("candidate_status") != "candidate":
        errors.append("trace Story/status is invalid")
    if trace.get("canonical_write_back") is not False:
        errors.append("trace must set canonical_write_back=false")
    if trace.get("parameters", {}).get("deduplicate_results") is not True:
        errors.append("trace must enable deterministic deduplication")
    paths = trace.get("searched_source_paths", [])
    if paths != sorted(SEARCHED_SOURCE_PATHS) or trace.get("allowed_source_paths") != sorted(SEARCHED_SOURCE_PATHS):
        errors.append("trace source boundary is not the fixed registered corpus")
    if any(_forbidden(str(path)) for path in paths):
        errors.append("forbidden generated/model path appears in trace source boundary")
    recorded_trace_hashes = trace.get("source_hashes")
    current_trace_hashes = source_hashes(ROOT)
    if not (
        isinstance(recorded_trace_hashes, Mapping)
        and (
            dict(recorded_trace_hashes) == current_trace_hashes
            or sfh2r_contract.frozen_hashes_are_current_or_authorized(recorded_trace_hashes, current_trace_hashes)
        )
    ):
        errors.append("trace source hashes do not match current registered inputs")

    steps = trace.get("steps", [])
    if not isinstance(steps, list):
        return errors + ["trace steps must be an array"]
    prior_returned: set[str] = set()
    for index, step in enumerate(steps):
        if not isinstance(step, Mapping):
            errors.append(f"steps[{index}] is not an object")
            continue
        name = step.get("tool_name")
        if name not in {"search_local_evidence", "open_local_evidence"}:
            errors.append(f"steps[{index}] uses an unsupported tool")
            continue
        round_no = step.get("round")
        if not isinstance(round_no, int) or not 1 <= round_no <= MAX_TOOL_ROUNDS:
            errors.append(f"steps[{index}] has an invalid round")
        arguments = step.get("arguments", {})
        if not isinstance(arguments, Mapping):
            errors.append(f"steps[{index}] arguments are invalid")
            arguments = {}
        if name == "search_local_evidence":
            top_k = arguments.get("top_k", MAX_TOP_K)
            if not isinstance(top_k, int) or not 1 <= top_k <= MAX_TOP_K:
                errors.append(f"steps[{index}] top_k exceeds the limit")
            refs = step.get("returned_evidence_refs", [])
            hits = step.get("returned_hits", [])
            if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
                errors.append(f"steps[{index}] returned refs are invalid")
                refs = []
            if len(refs) > MAX_TOP_K:
                errors.append(f"steps[{index}] returned more than five hits")
            if not isinstance(hits, list) or len(hits) != len(refs):
                errors.append(f"steps[{index}] hit/ref counts differ")
                hits = []
            if len({_hit_key(hit) for hit in hits if isinstance(hit, Mapping)}) != len(hits):
                errors.append(f"steps[{index}] contains duplicate evidence passages")
            if {hit.get("evidence_ref") for hit in hits if isinstance(hit, Mapping)} != set(refs):
                errors.append(f"steps[{index}] hits do not match returned refs")
            for ref in refs:
                if ref not in registry:
                    errors.append(f"steps[{index}] returned unknown evidence ref")
                else:
                    prior_returned.add(ref)
            scores = step.get("returned_scores", {})
            if not isinstance(scores, Mapping) or set(scores) != set(refs):
                errors.append(f"steps[{index}] scores do not match returned refs")
            raw_count = step.get("raw_match_count")
            dedup_count = step.get("deduplicated_match_count")
            duplicate_count = step.get("duplicate_match_count")
            if not all(isinstance(value, int) for value in (raw_count, dedup_count, duplicate_count)):
                errors.append(f"steps[{index}] lacks deduplication counts")
            elif not (raw_count >= dedup_count >= len(refs) and duplicate_count == raw_count - dedup_count):
                errors.append(f"steps[{index}] deduplication counts are inconsistent")
        else:
            ref = arguments.get("evidence_ref")
            status = step.get("open_status")
            if status == "success":
                if ref not in prior_returned:
                    errors.append(f"steps[{index}] opened a ref not returned by an earlier search")
                if step.get("evidence_refs_opened") != [ref]:
                    errors.append(f"steps[{index}] successful open trace is incomplete")
                results = step.get("opened_results", [])
                if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], Mapping) or results[0].get("evidence_ref") != ref:
                    errors.append(f"steps[{index}] successful open result is invalid")
            elif status == "rejected":
                if not step.get("error"):
                    errors.append(f"steps[{index}] rejected open lacks an error")
                if step.get("evidence_refs_opened"):
                    errors.append(f"steps[{index}] rejected open must not record a successful ref")
            else:
                errors.append(f"steps[{index}] open status is missing")

        for hit in step.get("returned_hits", []):
            if isinstance(hit, Mapping):
                for value in hit.values():
                    if isinstance(value, str) and _forbidden(value):
                        errors.append(f"steps[{index}] contains a forbidden path")

    loop = trace.get("loop_summary", {})
    if not isinstance(loop, Mapping):
        errors.append("trace loop_summary is missing")
    else:
        if loop.get("tool_rounds", 0) > MAX_TOOL_ROUNDS:
            errors.append("tool round limit exceeded")
        if not set(loop.get("returned_evidence_refs", [])).issubset(set(registry)):
            errors.append("loop summary contains unknown returned refs")
        if set(loop.get("returned_evidence_refs", [])) != prior_returned:
            errors.append("loop summary refs differ from trace")
        if not set(loop.get("opened_evidence_refs", [])).issubset(prior_returned):
            errors.append("loop summary contains unsafe opened refs")
    if not any(step.get("tool_name") == "search_local_evidence" and step.get("returned_evidence_refs") for step in steps if isinstance(step, Mapping)):
        errors.append("no non-empty local evidence search was recorded")
    dedup = trace.get("deduplication", {})
    if not isinstance(dedup, Mapping) or dedup.get("duplicate_match_count", 0) < 0:
        errors.append("deduplication summary is invalid")
    return errors


def _validate_candidate(candidate: Mapping[str, Any], trace: Mapping[str, Any], registry: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if candidate.get("schema") != "ds1-2r-local-context-candidate" or candidate.get("stage") != "DS1.2R":
        errors.append("candidate schema/stage is invalid")
    if candidate.get("story_id") != STORY_ID or candidate.get("candidate_status") != "candidate":
        errors.append("candidate Story/status is invalid")
    if candidate.get("run_type") != "real_model" or candidate.get("provider") != "deepseek":
        errors.append("candidate must be a real DeepSeek candidate")
    if candidate.get("canonical_write_back") is not False:
        errors.append("candidate must set canonical_write_back=false")
    refs = candidate.get("retrieved_evidence_refs", [])
    if not isinstance(refs, list) or not set(refs).issubset(registry):
        errors.append("candidate contains unknown retrieved refs")
        refs = []
    opened = candidate.get("opened_evidence_refs", [])
    if not isinstance(opened, list) or not set(opened).issubset(set(refs)):
        errors.append("candidate opened refs are unsafe")
    if candidate.get("retrieval_trace") != TRACE_PATH.as_posix():
        errors.append("candidate trace path is incorrect")
    errors.extend(validate_final_result_r(candidate.get("result"), refs, registry))
    if not required_identity_conflict_present(candidate.get("result", {})):
        errors.append("士衡→陆机 / 陶士衡→陶侃 conflict is missing")
    if candidate.get("validation_errors"):
        errors.append("candidate contains validation errors")
    if candidate.get("deduplication") != trace.get("deduplication"):
        errors.append("candidate/trace deduplication summaries differ")
    return errors


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    registry, _ = build_evidence_registry(root)
    for record in registry.values():
        if record.source_layer not in ALLOWED_SOURCE_LAYERS or _forbidden(record.source_path):
            errors.append("controlled registry contains an invalid/forbidden source")
    minimal = build_minimal_story_input(root, STORY_ID)
    if not minimal.get("story_text_original"):
        errors.append("minimal Story input is empty")

    manifest_path = root / MANIFEST_PATH
    trace_path = root / TRACE_PATH
    candidate_path = root / CANDIDATE_PATH
    if not manifest_path.is_file() or not trace_path.is_file():
        return sorted(errors)
    manifest = read_json(root, MANIFEST_PATH)
    if manifest.get("canonical_write_back") is not False:
        errors.append("manifest must set canonical_write_back=false")
    recorded_manifest_hashes = manifest.get("source_hashes")
    current_manifest_hashes = source_hashes(root)
    if not (
        isinstance(recorded_manifest_hashes, Mapping)
        and (
            dict(recorded_manifest_hashes) == current_manifest_hashes
            or sfh2r_contract.frozen_hashes_are_current_or_authorized(recorded_manifest_hashes, current_manifest_hashes)
        )
    ):
        errors.append("manifest source hashes do not match current sources")
    if manifest.get("protected_hashes") != protected_hashes(root):
        errors.append("protected canonical/Gold/DS1-v0 hashes changed")
    baseline = manifest.get("baseline_ds1_2", {})
    expected_baseline_paths = {
        "candidate_path": "data/generated/ds1-2/27-jiajue-008.json",
        "trace_path": "data/generated/ds1-2/27-jiajue-008-trace.json",
    }
    for key in ("candidate_path", "trace_path"):
        path = baseline.get(key)
        if path != expected_baseline_paths[key]:
            errors.append("baseline DS1.2 path is invalid")
        elif not (root / path).is_file() or baseline.get(key.replace("path", "sha256")) != sha256_file(root, Path(path)):
            errors.append(f"baseline DS1.2 artifact changed: {path}")

    trace = read_json(root, TRACE_PATH)
    if trace.get("execution_status") == "failed":
        if candidate_path.is_file():
            errors.append("failed run left a candidate")
    else:
        errors.extend(_validate_trace(trace, registry))
        if not candidate_path.is_file():
            errors.append("successful run has no candidate")
        else:
            candidate = read_json(root, CANDIDATE_PATH)
            errors.extend(_validate_candidate(candidate, trace, registry))
    return sorted(set(errors))


def main() -> int:
    errors = validate(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("DS1.2R validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
