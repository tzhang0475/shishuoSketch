#!/usr/bin/env python3
"""Run the DS2 seven-Story context-generalization pilot."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ds1_common import sha256_bytes, sha256_file  # noqa: E402
from ds2_common import (  # noqa: E402
    DS1_2_TOOLS,
    MODEL,
    OUTPUT_DIR,
    PILOT_STORIES,
    PROMPT_VERSION,
    REVIEW_PATH,
    ROOT,
    STAGE,
    SUMMARY_PATH,
    DeduplicatingLocalEvidenceSearch,
    build_evidence_registry,
    build_initial_messages,
    build_story_minimal_input,
    input_hash,
    normalize_ds2_result,
    protected_hashes,
    review_template,
    run_tool_loop,
    source_hashes,
    stable_json,
    summary_record,
    validate_ds2_result,
    write_json,
)
from smoke_deepseek import call_deepseek  # noqa: E402


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", action="store_true", help="run exactly the frozen seven-Story pilot")
    parser.add_argument("--max-tool-rounds", type=int, default=6)
    parser.add_argument("--thinking", choices=["disabled", "enabled"], default="disabled")
    parser.add_argument("--timeout", type=int, default=120)
    return parser.parse_args()


def story_paths(story_id: str) -> tuple[Path, Path]:
    return OUTPUT_DIR / f"{story_id}.json", OUTPUT_DIR / f"{story_id}-trace.json"


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


def run_story(
    story_id: str,
    *,
    registry: dict[str, Any],
    registry_hashes: dict[str, str],
    protected: dict[str, str],
    max_tool_rounds: int,
    thinking: dict[str, str],
    timeout: int,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    candidate_path, trace_path = story_paths(story_id)
    minimal_input = build_story_minimal_input(ROOT, story_id)
    initial_hash = input_hash(minimal_input)
    search = DeduplicatingLocalEvidenceSearch(registry, story_id=story_id)
    started_at = utc_now()
    run_id = sha256_bytes(f"{STAGE}:{story_id}:{initial_hash}:{started_at}".encode("utf-8"))[:20]
    trace: dict[str, Any] = {
        "schema": "ds2-retrieval-trace",
        "schema_version": 1,
        "stage": STAGE,
        "artifact_kind": "generated_retrieval_trace",
        "candidate_status": "candidate",
        "story_id": story_id,
        "run_id": run_id,
        "execution_kind": "real_model",
        "model": MODEL,
        "provider": "deepseek",
        "prompt_version": PROMPT_VERSION,
        "parameters": {
            "temperature": 0,
            "thinking": thinking,
            "max_tool_rounds": max_tool_rounds,
            "max_top_k": 5,
            "max_total_returned_chars": search.max_total_chars,
            "deduplicate_results": True,
        },
        "initial_input_hash": initial_hash,
        "initial_input": minimal_input,
        "source_hashes": registry_hashes,
        "searched_source_paths": sorted({record.source_path for record in search.registry.values()}),
        "allowed_source_paths": sorted({record.source_path for record in search.registry.values()}),
        "canonical_write_back": False,
        "started_at": started_at,
        "steps": [],
    }
    try:
        raw_result, steps, loop_summary = run_tool_loop(
            messages=build_initial_messages(minimal_input),
            search=search,
            tools=DS1_2_TOOLS,
            model_call=lambda messages, **kwargs: call_deepseek(messages, timeout=timeout, **kwargs),
            max_tool_rounds=max_tool_rounds,
            thinking=thinking,
        )
        normalized, adjustments = normalize_ds2_result(
            raw_result,
            loop_summary["returned_evidence_refs"],
            registry,
        )
        validation_errors = validate_ds2_result(
            normalized,
            loop_summary["returned_evidence_refs"],
            registry,
        )
        trace.update(
            {
                "steps": steps,
                "loop_summary": loop_summary,
                "deduplication": dedup_summary(steps),
                "normalization_adjustments": adjustments,
                "final_result_hash": input_hash(normalized),
                "completed_at": utc_now(),
            }
        )
        write_json(ROOT, trace_path, trace)
        candidate = {
            "schema": "ds2-context-candidate",
            "schema_version": 1,
            "stage": STAGE,
            "artifact_kind": "generated_context_candidate",
            "story_id": story_id,
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
            "retrieval_trace": trace_path.as_posix(),
            "token_usage": loop_summary["usage_records"],
            "deduplication": trace["deduplication"],
            "normalization_adjustments": adjustments,
            "result": normalized,
            "validation_errors": validation_errors,
            "canonical_write_back": False,
        }
        write_json(ROOT, candidate_path, candidate)
        return candidate, trace
    except Exception as error:
        trace.update({"execution_status": "failed", "error": str(error), "completed_at": utc_now()})
        write_json(ROOT, trace_path, trace)
        if candidate_path.is_file():
            candidate_path.unlink()
        return None, trace


def main() -> int:
    args = parse_args()
    if not args.pilot:
        raise SystemExit("use --pilot to run exactly the seven frozen DS2 Stories")
    if not 1 <= args.max_tool_rounds <= 6:
        raise SystemExit("--max-tool-rounds must be between 1 and 6")

    registry, registry_hashes = build_evidence_registry(ROOT)
    protected = protected_hashes(ROOT)
    records: list[dict[str, Any]] = []
    failures = 0
    for story_id in PILOT_STORIES:
        candidate, trace = run_story(
            story_id,
            registry=registry,
            registry_hashes=registry_hashes,
            protected=protected,
            max_tool_rounds=args.max_tool_rounds,
            thinking={"type": args.thinking},
            timeout=args.timeout,
        )
        error_count = len(candidate.get("validation_errors", [])) if candidate is not None else 1
        records.append(summary_record(story_id, trace=trace, candidate=candidate, error_count=error_count))
        if error_count:
            failures += 1

    write_json(
        ROOT,
        SUMMARY_PATH,
        {
            "schema": "ds2-pilot-summary",
            "schema_version": 1,
            "stage": STAGE,
            "pilot_stories": list(PILOT_STORIES),
            "records": records,
            "source_hashes": registry_hashes,
            "protected_hashes": protected,
            "canonical_write_back": False,
        },
    )
    if not (ROOT / REVIEW_PATH).is_file():
        write_json(ROOT, REVIEW_PATH, review_template())

    manifest = {
        "schema": "ds2-pilot-manifest",
        "schema_version": 1,
        "stage": STAGE,
        "pilot_stories": list(PILOT_STORIES),
        "candidate_paths": {story_id: story_paths(story_id)[0].as_posix() for story_id in PILOT_STORIES},
        "trace_paths": {story_id: story_paths(story_id)[1].as_posix() for story_id in PILOT_STORIES},
        "summary_path": SUMMARY_PATH.as_posix(),
        "review_path": REVIEW_PATH.as_posix(),
        "source_hashes": registry_hashes,
        "protected_hashes": protected,
        "canonical_write_back": False,
        "execution_kind": "real_model",
        "candidate_hashes": {
            story_id: sha256_file(ROOT, story_paths(story_id)[0])
            for story_id in PILOT_STORIES
            if (ROOT / story_paths(story_id)[0]).is_file()
        },
        "trace_hashes": {
            story_id: sha256_file(ROOT, story_paths(story_id)[1])
            for story_id in PILOT_STORIES
            if (ROOT / story_paths(story_id)[1]).is_file()
        },
    }
    write_json(ROOT, OUTPUT_DIR / "manifest.json", manifest)
    print(f"summary: {SUMMARY_PATH.as_posix()}")
    print(f"review: {REVIEW_PATH.as_posix()}")
    for record in records:
        print(
            f"{record['story_id']}: status={record['execution_status']} "
            f"rounds={record['tool_rounds']} searches={record['search_calls']} "
            f"errors={record['final_validation_errors']}"
        )
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
