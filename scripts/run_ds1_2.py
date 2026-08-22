#!/usr/bin/env python3
"""Run the bounded DS1.2 local-evidence DeepSeek experiment."""

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
    CANDIDATE_PATH,
    MANIFEST_PATH,
    MODEL,
    OUTPUT_DIR,
    PROMPT_VERSION,
    ROOT,
    SEARCHED_SOURCE_PATHS,
    STORY_ID,
    TRACE_PATH,
    LocalEvidenceSearch,
    build_evidence_registry,
    build_initial_messages,
    build_minimal_story_input,
    input_hash,
    protected_hashes,
    run_tool_loop,
    source_hashes,
    stable_json,
    validate_final_result,
)
from ds1_common import sha256_bytes, sha256_file, write_json  # noqa: E402
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


def main() -> int:
    args = parse_args()
    if not 1 <= args.max_tool_rounds <= 6:
        raise SystemExit("--max-tool-rounds must be between 1 and 6")

    minimal_input = build_minimal_story_input(ROOT, args.story)
    initial_hash = input_hash(minimal_input)
    registry, registry_hashes = build_evidence_registry(ROOT)
    search = LocalEvidenceSearch(registry)
    messages = build_initial_messages(minimal_input)
    started_at = utc_now()
    run_id = sha256_bytes(f"{args.story}:{initial_hash}:{started_at}".encode("utf-8"))[:20]
    thinking = {"type": args.thinking}
    trace: dict[str, Any] = {
        "schema": "ds1-2-retrieval-trace",
        "schema_version": 1,
        "stage": "DS1.2",
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
        final_result, steps, loop_summary = run_tool_loop(
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
        validation_errors = validate_final_result(final_result, loop_summary["returned_evidence_refs"])
        trace["steps"] = steps
        trace["loop_summary"] = loop_summary
        trace["final_result_hash"] = input_hash(final_result)
        trace["completed_at"] = utc_now()
        write_json(ROOT, TRACE_PATH, trace)

        candidate = {
            "schema": "ds1-2-local-context-candidate",
            "schema_version": 1,
            "stage": "DS1.2",
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
            "result": final_result,
            "validation_errors": validation_errors,
            "canonical_write_back": False,
        }
        write_json(ROOT, CANDIDATE_PATH, candidate)
        manifest = {
            "schema": "ds1-2-manifest",
            "schema_version": 1,
            "stage": "DS1.2",
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
            "canonical_write_back": False,
        }
        write_json(ROOT, MANIFEST_PATH, manifest)
        print(f"candidate: {CANDIDATE_PATH.as_posix()}")
        print(f"trace: {TRACE_PATH.as_posix()}")
        print(f"validation_errors: {len(validation_errors)}")
        return 0 if not validation_errors else 2
    except Exception as error:
        trace["execution_status"] = "failed"
        trace["error"] = str(error)
        trace["completed_at"] = utc_now()
        write_json(ROOT, TRACE_PATH, trace)
        manifest = {
            "schema": "ds1-2-manifest",
            "schema_version": 1,
            "stage": "DS1.2",
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
        print(f"DS1.2 run failed: {error}", file=sys.stderr)
        print(f"trace: {TRACE_PATH.as_posix()}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
