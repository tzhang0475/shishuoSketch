#!/usr/bin/env python3
"""Run DS1.2R evidence and identity hardening for one Story."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ds1_2_common import (  # noqa: E402
    MODEL,
    ROOT,
    SEARCHED_SOURCE_PATHS,
    STORY_ID,
    build_evidence_registry,
    source_hashes,
)
from ds1_common import sha256_bytes, sha256_file, write_json  # noqa: E402
from ds1_2r_common import (  # noqa: E402
    CANDIDATE_PATH,
    MANIFEST_PATH,
    OUTPUT_DIR,
    PROMPT_VERSION,
    STAGE,
    TRACE_PATH,
    DeduplicatingLocalEvidenceSearch,
    build_initial_messages,
    build_minimal_story_input,
    ensure_identity_conflict,
    input_hash,
    normalize_epistemic_statuses,
    protected_hashes,
    required_identity_conflict_present,
    run_tool_loop,
    validate_final_result_r,
)
from smoke_deepseek import call_deepseek  # noqa: E402


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", default=STORY_ID, choices=[STORY_ID])
    parser.add_argument("--max-tool-rounds", type=int, default=6)
    parser.add_argument("--thinking", choices=["disabled", "enabled"], default="disabled")
    parser.add_argument("--timeout", type=int, default=120)
    return parser.parse_args()


def dedup_summary(steps: list[dict[str, Any]]) -> dict[str, int]:
    searches = [step for step in steps if step.get("tool_name") == "search_local_evidence"]
    raw = sum(int(step.get("raw_match_count", 0)) for step in searches)
    after = sum(int(step.get("deduplicated_match_count", 0)) for step in searches)
    returned = sum(len(step.get("returned_evidence_refs", [])) for step in searches)
    return {
        "search_calls": len(searches),
        "raw_match_count": raw,
        "deduplicated_match_count": after,
        "duplicate_match_count": max(0, raw - after),
        "returned_hit_count": returned,
    }


def main() -> int:
    args = parse_args()
    if not 1 <= args.max_tool_rounds <= 6:
        raise SystemExit("--max-tool-rounds must be between 1 and 6")

    minimal_input = build_minimal_story_input(ROOT, args.story)
    initial_hash = input_hash(minimal_input)
    registry, registry_hashes = build_evidence_registry(ROOT)
    search = DeduplicatingLocalEvidenceSearch(registry)
    messages = build_initial_messages(minimal_input)
    started_at = utc_now()
    run_id = sha256_bytes(f"{STAGE}:{args.story}:{initial_hash}:{started_at}".encode("utf-8"))[:20]
    thinking = {"type": args.thinking}
    trace: dict[str, Any] = {
        "schema": "ds1-2r-retrieval-trace",
        "schema_version": 1,
        "stage": STAGE,
        "artifact_kind": "generated_retrieval_trace",
        "candidate_status": "candidate",
        "story_id": args.story,
        "run_id": run_id,
        "execution_kind": "real_model",
        "model": MODEL,
        "provider": "deepseek",
        "prompt_version": PROMPT_VERSION,
        "parameters": {
            "temperature": 0,
            "thinking": thinking,
            "max_tool_rounds": args.max_tool_rounds,
            "max_top_k": 5,
            "max_total_returned_chars": search.max_total_chars,
            "deduplicate_results": True,
        },
        "initial_input_hash": initial_hash,
        "initial_input": minimal_input,
        "source_hashes": registry_hashes,
        "searched_source_paths": sorted(SEARCHED_SOURCE_PATHS),
        "allowed_source_paths": sorted(SEARCHED_SOURCE_PATHS),
        "canonical_write_back": False,
        "started_at": started_at,
        "steps": [],
    }

    try:
        raw_result, steps, loop_summary = run_tool_loop(
            messages=messages,
            search=search,
            model_call=lambda current_messages, **kwargs: call_deepseek(
                current_messages,
                timeout=args.timeout,
                **kwargs,
            ),
            max_tool_rounds=args.max_tool_rounds,
            thinking=thinking,
        )
        normalized_result, epistemic_adjustments = normalize_epistemic_statuses(raw_result, registry)
        final_result = ensure_identity_conflict(
            normalized_result,
            minimal_input,
            loop_summary["returned_evidence_refs"],
            registry,
        )
        validation_errors = validate_final_result_r(
            final_result,
            loop_summary["returned_evidence_refs"],
            registry,
        )
        if not required_identity_conflict_present(final_result):
            validation_errors.append("required 士衡 identity conflict was not surfaced")
        validation_errors = sorted(set(validation_errors))
        trace["steps"] = steps
        trace["loop_summary"] = loop_summary
        trace["deduplication"] = dedup_summary(steps)
        trace["epistemic_adjustments"] = epistemic_adjustments
        trace["identity_conflicts"] = final_result.get("data_conflicts", [])
        trace["final_result_hash"] = input_hash(final_result)
        trace["completed_at"] = utc_now()
        write_json(ROOT, TRACE_PATH, trace)

        candidate = {
            "schema": "ds1-2r-local-context-candidate",
            "schema_version": 1,
            "stage": STAGE,
            "artifact_kind": "generated_local_context_candidate",
            "story_id": args.story,
            "candidate_status": "candidate",
            "run_type": "real_model",
            "run_id": run_id,
            "model": MODEL,
            "provider": "deepseek",
            "timestamp": trace["completed_at"],
            "prompt_config_version": PROMPT_VERSION,
            "parameters": trace["parameters"],
            "initial_input_hash": initial_hash,
            "retrieved_evidence_refs": loop_summary["returned_evidence_refs"],
            "opened_evidence_refs": loop_summary["opened_evidence_refs"],
            "retrieval_trace": TRACE_PATH.as_posix(),
            "token_usage": loop_summary["usage_records"],
            "deduplication": trace["deduplication"],
            "epistemic_adjustments": epistemic_adjustments,
            "result": final_result,
            "validation_errors": validation_errors,
            "canonical_write_back": False,
        }
        write_json(ROOT, CANDIDATE_PATH, candidate)
        manifest = {
            "schema": "ds1-2r-manifest",
            "schema_version": 1,
            "stage": STAGE,
            "artifact_kind": "generated_candidate_manifest",
            "candidate_status": "candidate",
            "story_id": args.story,
            "run_id": run_id,
            "execution_kind": "real_model",
            "candidate_path": CANDIDATE_PATH.as_posix(),
            "candidate_sha256": sha256_file(ROOT, CANDIDATE_PATH),
            "trace_path": TRACE_PATH.as_posix(),
            "trace_sha256": sha256_file(ROOT, TRACE_PATH),
            "source_hashes": registry_hashes,
            "protected_hashes": protected_hashes(ROOT),
            "baseline_ds1_2": {
                "candidate_path": "data/generated/ds1-2/27-jiajue-008.json",
                "candidate_sha256": sha256_file(ROOT, Path("data/generated/ds1-2/27-jiajue-008.json")),
                "trace_path": "data/generated/ds1-2/27-jiajue-008-trace.json",
                "trace_sha256": sha256_file(ROOT, Path("data/generated/ds1-2/27-jiajue-008-trace.json")),
            },
            "canonical_write_back": False,
        }
        write_json(ROOT, MANIFEST_PATH, manifest)
        print(f"candidate: {CANDIDATE_PATH.as_posix()}")
        print(f"trace: {TRACE_PATH.as_posix()}")
        print(f"validation_errors: {len(validation_errors)}")
        print(f"identity_conflict: {required_identity_conflict_present(final_result)}")
        return 0 if not validation_errors else 2
    except Exception as error:
        trace["execution_status"] = "failed"
        trace["error"] = str(error)
        trace["completed_at"] = utc_now()
        write_json(ROOT, TRACE_PATH, trace)
        manifest = {
            "schema": "ds1-2r-manifest",
            "schema_version": 1,
            "stage": STAGE,
            "artifact_kind": "generated_candidate_manifest",
            "candidate_status": "candidate",
            "story_id": args.story,
            "run_id": run_id,
            "execution_kind": "real_model",
            "execution_status": "failed",
            "trace_path": TRACE_PATH.as_posix(),
            "trace_sha256": sha256_file(ROOT, TRACE_PATH),
            "source_hashes": registry_hashes,
            "protected_hashes": protected_hashes(ROOT),
            "canonical_write_back": False,
        }
        write_json(ROOT, MANIFEST_PATH, manifest)
        print(f"DS1.2R run failed: {error}", file=sys.stderr)
        print(f"trace: {TRACE_PATH.as_posix()}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
