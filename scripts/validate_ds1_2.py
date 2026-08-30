#!/usr/bin/env python3
"""Validate the DS1.2 local-evidence boundary and any generated run."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ds1_2_common import (  # noqa: E402
    ALLOWED_SOURCE_LAYERS,
    CANDIDATE_PATH,
    MANIFEST_PATH,
    MAX_TOOL_ROUNDS,
    MAX_TOP_K,
    OUTPUT_DIR,
    ROOT,
    SEARCHED_SOURCE_PATHS,
    SCHEMA_VERSION,
    STORY_ID,
    TRACE_PATH,
    build_evidence_registry,
    build_minimal_story_input,
    protected_hashes,
    source_hashes,
    validate_final_result,
)
from ds1_common import read_json, sha256_file  # noqa: E402
try:
    from scripts import sfh2r_contract  # noqa: E402
except ImportError:  # direct execution from scripts/
    import sfh2r_contract  # type: ignore  # noqa: E402


FORBIDDEN_PATH_PARTS = (
    "data/generated",
    "site/public/generated",
    "data/annotation",
    "irr0",
    "model-output",
)


def _is_forbidden(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return any(part in normalized for part in FORBIDDEN_PATH_PARTS)


def _validate_trace(trace: Mapping[str, Any], registry: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if trace.get("schema") != "ds1-2-retrieval-trace" or trace.get("schema_version") != SCHEMA_VERSION:
        errors.append("trace schema/version is invalid")
    if trace.get("artifact_kind") != "generated_retrieval_trace" or trace.get("candidate_status") != "candidate":
        errors.append("trace must be marked as a generated candidate artifact")
    if trace.get("stage") != "DS1.2" or trace.get("story_id") != STORY_ID:
        errors.append("trace scope is invalid")
    if trace.get("canonical_write_back") is not False:
        errors.append("trace must set canonical_write_back=false")
    searched = trace.get("searched_source_paths", [])
    allowed = trace.get("allowed_source_paths", [])
    if not isinstance(searched, list) or not all(isinstance(path, str) for path in searched):
        errors.append("searched_source_paths must be a string array")
        searched = []
    if not isinstance(allowed, list) or not all(isinstance(path, str) for path in allowed):
        errors.append("allowed_source_paths must be a string array")
        allowed = []
    if any(_is_forbidden(path) for path in searched + allowed):
        errors.append("forbidden generated/model path appears in search boundary")
    if set(searched) != set(allowed):
        errors.append("searched_source_paths and allowed_source_paths differ")
    if set(searched) != set(SEARCHED_SOURCE_PATHS):
        errors.append("trace search paths do not match the fixed registered corpus boundary")
    if any(path not in {record.source_path for record in registry.values()} for path in searched):
        errors.append("trace searches a source path outside the registered evidence indexes")

    steps = trace.get("steps", [])
    if not isinstance(steps, list):
        return errors + ["trace steps must be an array"]
    prior_returned: set[str] = set()
    search_rounds: set[int] = set()
    for index, step in enumerate(steps):
        if not isinstance(step, Mapping):
            errors.append(f"steps[{index}] must be an object")
            continue
        name = step.get("tool_name")
        if name not in {"search_local_evidence", "open_local_evidence"}:
            errors.append(f"steps[{index}] uses an unsupported tool")
        arguments = step.get("arguments", {})
        if not isinstance(arguments, Mapping):
            errors.append(f"steps[{index}].arguments must be an object")
            arguments = {}
        if name == "search_local_evidence":
            round_no = step.get("round")
            if not isinstance(round_no, int) or not 1 <= round_no <= MAX_TOOL_ROUNDS:
                errors.append(f"steps[{index}] has an invalid tool round")
            else:
                search_rounds.add(round_no)
            top_k = arguments.get("top_k", MAX_TOP_K)
            if not isinstance(top_k, int) or not 1 <= top_k <= MAX_TOP_K:
                errors.append(f"steps[{index}] exceeds top_k limit")
            refs = step.get("returned_evidence_refs", [])
            hits = step.get("returned_hits", [])
            if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
                errors.append(f"steps[{index}] returned refs are invalid")
                refs = []
            if len(refs) > MAX_TOP_K:
                errors.append(f"steps[{index}] returned more than five hits")
            if not isinstance(hits, list) or {hit.get("evidence_ref") for hit in hits if isinstance(hit, Mapping)} != set(refs):
                errors.append(f"steps[{index}] returned_hits do not match returned refs")
            for ref in refs:
                if ref not in registry:
                    errors.append(f"steps[{index}] returned unknown evidence ref {ref}")
                else:
                    prior_returned.add(ref)
            scores = step.get("returned_scores", {})
            if not isinstance(scores, Mapping) or set(scores) != set(refs):
                errors.append(f"steps[{index}] returned_scores do not match refs")
        elif name == "open_local_evidence":
            ref = arguments.get("evidence_ref")
            # A rejected open is a valid bounded-tool outcome.  Older DS1.2
            # traces predate the explicit open_status field, so the presence
            # of an error with no opened result is accepted as the same state.
            if step.get("open_status") == "rejected" or (
                step.get("error") and not step.get("evidence_refs_opened") and not step.get("opened_results")
            ):
                if ref in prior_returned:
                    errors.append(f"steps[{index}] rejected an already-returned ref")
                if not step.get("error"):
                    errors.append(f"steps[{index}] rejected open lacks an error")
                continue
            if ref not in prior_returned:
                errors.append(f"steps[{index}] opened a ref not returned by an earlier search")
            opened = step.get("evidence_refs_opened", [])
            if opened != [ref]:
                errors.append(f"steps[{index}] open trace is incomplete")
            results = step.get("opened_results", [])
            if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], Mapping) or results[0].get("evidence_ref") != ref:
                errors.append(f"steps[{index}] opened result is incomplete")
        if isinstance(step.get("returned_hits"), list):
            for hit in step["returned_hits"]:
                if isinstance(hit, Mapping) and any(_is_forbidden(str(value)) for value in hit.values() if isinstance(value, str)):
                    errors.append(f"steps[{index}] exposes a forbidden generated path")

    loop = trace.get("loop_summary", {})
    if not isinstance(loop, Mapping):
        errors.append("trace loop_summary is missing")
    else:
        if loop.get("tool_rounds", 0) > MAX_TOOL_ROUNDS:
            errors.append("tool round limit exceeded")
        returned = set(loop.get("returned_evidence_refs", []))
        if not returned.issubset(set(registry)):
            errors.append("loop summary contains unknown evidence refs")
        if returned != prior_returned:
            errors.append("loop summary returned refs differ from the trace")
        if not set(loop.get("opened_evidence_refs", [])).issubset(prior_returned):
            errors.append("loop summary opened an unknown/unsearched ref")
        if loop.get("total_returned_chars", 0) > 24000:
            errors.append("total returned evidence text exceeds the budget")
    if not any(
        isinstance(step, Mapping)
        and step.get("tool_name") == "search_local_evidence"
        and step.get("returned_evidence_refs")
        for step in steps
    ):
        errors.append("a successful DS1.2 run must contain a non-empty local evidence search")
    recorded_hashes = trace.get("source_hashes")
    current_source_hashes = source_hashes(ROOT)
    source_hashes_ok = (
        isinstance(recorded_hashes, Mapping)
        and (
            dict(recorded_hashes) == current_source_hashes
            or sfh2r_contract.frozen_hashes_are_current_or_authorized(recorded_hashes, current_source_hashes)
        )
    )
    if not source_hashes_ok:
        errors.append("trace source hashes do not match current registered inputs")
    return errors


def _validate_candidate(candidate: Mapping[str, Any], trace: Mapping[str, Any], registry: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema", "schema_version", "stage", "story_id", "candidate_status", "run_type",
        "model", "provider", "prompt_config_version", "initial_input_hash", "retrieved_evidence_refs",
        "opened_evidence_refs", "retrieval_trace", "result", "validation_errors", "canonical_write_back",
    }
    if not required.issubset(candidate):
        errors.append("candidate is missing required fields")
    if candidate.get("schema") != "ds1-2-local-context-candidate" or candidate.get("schema_version") != 1:
        errors.append("candidate schema/version is invalid")
    if candidate.get("artifact_kind") != "generated_local_context_candidate":
        errors.append("candidate artifact kind is invalid")
    if candidate.get("stage") != "DS1.2" or candidate.get("story_id") != STORY_ID:
        errors.append("candidate scope is invalid")
    if candidate.get("candidate_status") != "candidate" or candidate.get("provider") != "deepseek":
        errors.append("candidate status/provider is invalid")
    if candidate.get("run_type") != "real_model":
        errors.append("candidate must be marked real_model")
    if candidate.get("canonical_write_back") is not False:
        errors.append("candidate must set canonical_write_back=false")
    retrieved = candidate.get("retrieved_evidence_refs", [])
    if not isinstance(retrieved, list) or not all(isinstance(ref, str) for ref in retrieved):
        errors.append("candidate retrieved refs are invalid")
        retrieved = []
    if not set(retrieved).issubset(registry):
        errors.append("candidate contains an unresolved retrieved evidence ref")
    opened = candidate.get("opened_evidence_refs", [])
    if not isinstance(opened, list) or not set(opened).issubset(set(retrieved)):
        errors.append("candidate opened refs are not a subset of retrieved refs")
    errors.extend(validate_final_result(candidate.get("result"), retrieved))
    if candidate.get("validation_errors"):
        errors.append("candidate contains model/schema validation errors")
    if candidate.get("retrieval_trace") != TRACE_PATH.as_posix():
        errors.append("candidate retrieval trace path is not repository-relative")
    loop = trace.get("loop_summary", {})
    if isinstance(loop, Mapping) and set(retrieved) != set(loop.get("returned_evidence_refs", [])):
        errors.append("candidate refs differ from retrieval trace")
    return errors


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        registry, _ = build_evidence_registry(root)
    except Exception as error:  # pragma: no cover - defensive boundary
        return [f"controlled evidence registry failed: {error}"]
    if not registry:
        errors.append("controlled evidence registry is empty")
    for ref, record in registry.items():
        if not ref or record.source_path not in {
            "data/evidence/wp1-evidence.json",
            "data/derived/s1-jianshu-historical-assertions.json",
        }:
            errors.append(f"registry entry {ref} is outside the allowed source indexes")
        if record.source_layer not in ALLOWED_SOURCE_LAYERS:
            errors.append(f"registry entry {ref} has an invalid source layer")
        if _is_forbidden(record.source_path):
            errors.append(f"registry entry {ref} comes from a forbidden path")
    try:
        minimal = build_minimal_story_input(root, STORY_ID)
        if minimal.get("story_id") != STORY_ID or not minimal.get("story_text_original"):
            errors.append("minimal input is incomplete")
    except Exception as error:
        errors.append(f"minimal input failed: {error}")

    manifest_path = root / MANIFEST_PATH
    trace_path = root / TRACE_PATH
    candidate_path = root / CANDIDATE_PATH
    if manifest_path.is_file():
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
            errors.append("manifest source hashes do not match current registered inputs")
        expected_protected = manifest.get("protected_hashes", {})
        if expected_protected != protected_hashes(root):
            errors.append("protected canonical/Gold/DS1-v0 hashes changed after the run")
        if trace_path.is_file():
            if manifest.get("trace_sha256") != sha256_file(root, TRACE_PATH):
                errors.append("manifest trace hash does not match trace")
        if candidate_path.is_file() and manifest.get("candidate_sha256") != sha256_file(root, CANDIDATE_PATH):
            errors.append("manifest candidate hash does not match candidate")

    if trace_path.is_file():
        trace = read_json(root, TRACE_PATH)
        if trace.get("execution_status") == "failed":
            if candidate_path.is_file():
                errors.append("a failed run must not leave a DS1.2 candidate artifact")
        else:
            errors.extend(_validate_trace(trace, registry))
        if trace.get("execution_status") != "failed" and not candidate_path.is_file():
            errors.append("successful trace has no candidate")
        if trace.get("execution_status") != "failed" and candidate_path.is_file():
            candidate = read_json(root, CANDIDATE_PATH)
            errors.extend(_validate_candidate(candidate, trace, registry))
    elif candidate_path.is_file():
        errors.append("candidate exists without its retrieval trace")

    return sorted(set(errors))


def main() -> int:
    errors = validate(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    if not (ROOT / TRACE_PATH).is_file():
        print("DS1.2 static boundary valid; no real-model run artifact is present yet.")
    elif read_json(ROOT, TRACE_PATH).get("execution_status") == "failed":
        print("DS1.2 boundary valid; the recorded real-model run failed and produced no candidate.")
    else:
        print("DS1.2 validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
