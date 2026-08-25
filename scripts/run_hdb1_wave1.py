#!/usr/bin/env python3
"""Run HDB1-W1 with the frozen HNG2-C.3/V1 semantic pipeline.

The runner owns only production selection, execution bookkeeping, and
candidate-only artifact boundaries.  Semantic prompts, strict tools,
grounding, resolver logic, and H0A normalization are imported unchanged from
the frozen HNG2-V1 runner.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_hng0_2 as hng02  # noqa: E402
import historical_context_algorithm as algorithm  # noqa: E402
import run_hng2_consolidation as consolidation  # noqa: E402
import run_hng2_fresh_validation as frozen  # noqa: E402
import run_hng2_read_fill_validation as c1  # noqa: E402
from hdb1_common import (  # noqa: E402
    ROOT as COMMON_ROOT,
    RUN_VERSION,
    SELECTION_PATH,
    STAGE,
    build_selection,
    ensure_selection,
    load_frozen_selection,
    load_people_catalog,
    production_story_map,
    read_json,
    stable_hash,
    utc_now,
    write_json,
)


OUT = ROOT / "data/generated/hdb1-wave1"


def _attempts(results: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    for row in results:
        for call_name in ("person_read", "person_fill", "temporal_read", "temporal_fill"):
            attempts.extend(list(((row.get(call_name) or {}).get("transport") or {}).get("attempts", [])))
    return attempts


def _raw_hashes(raw_dir: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(raw_dir.glob("*.json")):
        result[str(path.relative_to(raw_dir))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _operation_metrics(person_results: Sequence[Mapping[str, Any]], temporal_results: Sequence[Mapping[str, Any]], preflight: Mapping[str, Any], selection: Mapping[str, Any]) -> dict[str, Any]:
    attempts = _attempts([*person_results, *temporal_results])
    usage = {
        key: sum(int((attempt.get("usage") or {}).get(key) or 0) for attempt in attempts)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }
    latencies = [float(attempt.get("elapsed_seconds")) for attempt in attempts if attempt.get("status") == "response" and attempt.get("elapsed_seconds") is not None]
    retry_calls = sum(max(0, len(((row.get(call) or {}).get("transport") or {}).get("attempts", [])) - 1) for row in [*person_results, *temporal_results] for call in ("person_read", "person_fill", "temporal_read", "temporal_fill"))
    expected = int(selection.get("expected_semantic_calls") or 0)
    return {
        "model": frozen.MODEL,
        "temperature": 0,
        "prompt_versions": {
            "person_read": frozen.PROMPT_VERSION,
            "person_fill": frozen.PROMPT_VERSION,
            "temporal_read": frozen.PROMPT_VERSION,
            "temporal_fill": frozen.PROMPT_VERSION,
        },
        "expected_semantic_calls": expected,
        "semantic_calls_attempted": len(attempts),
        "semantic_calls_base": expected,
        "api_calls": len(attempts) + 1,
        "preflight_calls": 1,
        "retry_calls": retry_calls,
        "provider_failures": sum(attempt.get("classification") == "provider_request_failure" for attempt in attempts),
        "parse_failures": sum(attempt.get("classification") == "response_parse_failure" for attempt in attempts),
        "truncated_responses": sum(attempt.get("classification") == "response_truncated" for attempt in attempts),
        "token_usage": usage,
        "median_latency_seconds": statistics.median(latencies) if latencies else None,
        "maximum_latency_seconds": max(latencies) if latencies else None,
        "algorithm_hashes": {
            "historical_context_algorithm.py": frozen.file_hash(ROOT / "scripts/historical_context_algorithm.py"),
            "run_hng2_read_fill_validation.py": frozen.file_hash(ROOT / "scripts/run_hng2_read_fill_validation.py"),
            "run_hng2_algorithm_closeout.py": frozen.file_hash(ROOT / "scripts/run_hng2_algorithm_closeout.py"),
        },
        "preflight": dict(preflight),
    }


def build_units(selection: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    catalog = load_people_catalog()
    stories_by_id = production_story_map()
    person_units: list[dict[str, Any]] = []
    temporal_units: list[dict[str, Any]] = []
    for story_selection in selection.get("stories", []):
        story_id = str(story_selection["story_id"])
        for target in story_selection.get("targets", []):
            person_windows = c1._select_story_windows(
                story_id,
                target=str(target.get("surface") or ""),
                canonical_name=str(target.get("canonical_name") or ""),
                lane="person",
            )
            person_units.append(
                {
                    "unit_id": str(target["target_id"]),
                    "story_id": story_id,
                    "target": {"surface": target["surface"], "source_work": "世說新語", "story_id": story_id},
                    "selection": target,
                    "person_windows": person_windows,
                    "case": frozen._case_for_target(target, catalog),
                }
            )
        temporal_windows = c1._select_story_windows(story_id, lane="temporal")
        temporal_units.append(
            {
                "unit_id": f"hdb1-temporal-{story_id}",
                "story_id": story_id,
                "selection": story_selection,
                "story": {"story_id": story_id, "target_unit": "Story/scene"},
                "temporal_windows": temporal_windows,
            }
        )
        if story_id not in stories_by_id:
            raise RuntimeError(f"hdb1_unit_outside_production_scope:{story_id}")
    return person_units, temporal_units


def _basic_production_summary(selection: Mapping[str, Any], person_results: Sequence[Mapping[str, Any]], temporal_results: Sequence[Mapping[str, Any]], operations: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "wave_id": "HDB1-W1",
        "candidate_only": True,
        "canonical_write_back": False,
        "stories_processed": len(temporal_results),
        "person_targets": len(person_results),
        "main_text_targets": len(person_results),
        "secondary_targets": sum(len(row.get("targets", [])) > 1 for row in selection.get("stories", [])),
        "semantic_calls": operations.get("semantic_calls_attempted"),
        "expected_semantic_calls": operations.get("expected_semantic_calls"),
        "operations": dict(operations),
        "selection_hash": selection.get("selection_hash"),
    }


def run_live(selection: Mapping[str, Any], run_id: str) -> dict[str, Any]:
    base = OUT / "live" / run_id
    if base.exists():
        raise RuntimeError(f"hdb1_immutable_live_run_exists:{base}")
    raw_dir = base / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=False)
    preflight = frozen.preflight()
    write_json(base / "preflight.json", preflight)
    if preflight.get("status") != "reachable":
        write_json(
            base / "manifest.json",
            {
                "stage": STAGE,
                "run_id": run_id,
                "status": "execution_environment_failure",
                "failure": "approved_network_preflight_failed",
                "preflight": preflight,
                "semantic_calls": 0,
                "candidate_only": True,
                "canonical_write_back": False,
            },
        )
        raise RuntimeError("hdb1_approved_network_preflight_failed")

    person_units, temporal_units = build_units(selection)
    known_evidence = consolidation.load_previous_findings()["evidence_refs"]
    person_results: list[dict[str, Any]] = []
    temporal_results: list[dict[str, Any]] = []
    sequence = 1
    for unit in person_units:
        result, sequence = frozen.run_person(unit, raw_dir, sequence, known_evidence)
        person_results.append(result)
    for unit in temporal_units:
        result, sequence = frozen.run_temporal(unit, raw_dir, sequence)
        temporal_results.append(result)
    expected = int(selection.get("expected_semantic_calls") or 0)
    if sequence - 1 != expected:
        raise RuntimeError(f"hdb1_semantic_call_count_mismatch:{sequence - 1}:{expected}")
    operations = _operation_metrics(person_results, temporal_results, preflight, selection)
    manifest = {
        "stage": STAGE,
        "run_id": run_id,
        "run_version": RUN_VERSION,
        "status": "complete",
        "selection_hash": selection.get("selection_hash"),
        "algorithm_hashes": operations.get("algorithm_hashes"),
        "prompt_versions": operations.get("prompt_versions"),
        "model": frozen.MODEL,
        "temperature": 0,
        "expected_semantic_calls": expected,
        "semantic_calls_attempted": operations.get("semantic_calls_attempted"),
        "retry_calls": operations.get("retry_calls"),
        "preflight_calls": 1,
        "candidate_only": True,
        "canonical_write_back": False,
        "raw_api_immutable": True,
        "raw_api_hashes": _raw_hashes(raw_dir),
        "previous_hng2_overlap": selection.get("overlap_with_previous_hng2", []),
        "no_search_plan": True,
        "no_research_gap_loop": True,
        "no_recursive_retrieval": True,
        "protected_hashes_before_live": selection.get("protected_hashes_before_live", {}),
        "created_at": utc_now(),
    }
    write_json(base / "person-results.json", person_results)
    write_json(base / "temporal-results.json", temporal_results)
    write_json(base / "production-summary.json", _basic_production_summary(selection, person_results, temporal_results, operations))
    write_json(base / "manifest.json", manifest)
    return {"output": str(base), "manifest": manifest}


def load_live_run(run_id: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    base = OUT / "live" / run_id
    manifest = read_json(base / "manifest.json", {}) or {}
    if manifest.get("status") != "complete":
        raise RuntimeError(f"hdb1_live_run_not_complete:{run_id}")
    return manifest, read_json(base / "person-results.json", []) or [], read_json(base / "temporal-results.json", []) or []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true", help="freeze/verify selection without network calls")
    parser.add_argument("--live", action="store_true", help="run the frozen 48-Story live wave")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    selection = ensure_selection()
    if not args.live or args.prepare:
        print(json.dumps(selection, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    print(json.dumps(run_live(selection, run_id), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

