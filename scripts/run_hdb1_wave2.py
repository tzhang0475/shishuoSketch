#!/usr/bin/env python3
"""Run HDB1-W2 with the frozen HNG2 semantic pipeline.

W2 is deliberately independent of HDB1-W1 candidate state.  It reuses the
same target/window construction and HNG2-V1 semantic calls, but computes its
selection from the current production boundary minus the frozen prior-HNG2
and W1 sets.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_hng0_2 as hng02  # noqa: E402
import run_hng2_consolidation as consolidation  # noqa: E402
import run_hng2_fresh_validation as frozen  # noqa: E402
import run_hdb1_wave1 as wave1  # noqa: E402
from hdb1_common import (  # noqa: E402
    ROOT as COMMON_ROOT,
    STAGE as W1_STAGE,
    choose_targets,
    file_hash,
    load_frozen_selection as load_w1_selection,
    load_frozen_previous_hng2_exclusion,
    load_mentions,
    load_participant_map,
    load_people_catalog,
    production_story_rows,
    protected_hashes,
    read_json,
    source_refs_for_story,
    stable_hash,
    utc_now,
    write_json,
)


OUT = ROOT / "data/generated/hdb1-wave2"
SELECTION_PATH = ROOT / "data/annotation/hdb1-wave2-selection.json"
W1_SELECTION_PATH = ROOT / "data/annotation/hdb1-wave1-selection.json"
STAGE = "hdb1-wave2-remaining-scope-production"
RUN_VERSION = "hdb1-w2-v1"


def build_selection() -> dict[str, Any]:
    production_rows = production_story_rows()
    production_ids = {str(row["id"]) for row in production_rows}
    w1_selection = load_w1_selection()
    w1_ids = {str(row["story_id"]) for row in w1_selection.get("stories", [])}
    # W2 is a historical continuation of the frozen HDB1 selection contract;
    # use the same captured exclusion manifest as W1 so later HNG2 files do
    # not change a byte-stability rebuild.
    prior = load_frozen_previous_hng2_exclusion()
    prior_ids = {str(value) for value in prior.get("story_ids", [])}
    remaining = production_ids - prior_ids - w1_ids
    if prior_ids & w1_ids:
        raise RuntimeError("hdb1_w1_overlaps_prior_hng2")
    if remaining & prior_ids or remaining & w1_ids or not remaining <= production_ids:
        raise RuntimeError("hdb1_w2_remaining_set_boundary_failure")

    mentions = load_mentions()
    participants = load_participant_map()
    catalog = load_people_catalog()
    stories: list[dict[str, Any]] = []
    for story_id in sorted(remaining, key=lambda value: stable_hash({"wave": "HDB1-W2", "story_id": value})):
        targets = choose_targets(story_id, mentions, participants, catalog)
        target_rows: list[dict[str, Any]] = []
        for target in targets:
            refs = source_refs_for_story(story_id, target)
            target_rows.append(
                {
                    **target,
                    "story_id": story_id,
                    "reference_person_id": target.get("person_id"),
                    "reference_candidate_person_ids": target.get("candidate_person_ids", []),
                    "reference_canonical_name": target.get("canonical_name"),
                    "source_refs": refs["person"],
                    "selection_key": stable_hash(
                        {
                            "wave": "HDB1-W2",
                            "story_id": story_id,
                            "target_id": target["target_id"],
                            "surface": target.get("surface"),
                            "source_refs": refs["person"],
                        }
                    ),
                }
            )
        story_refs = source_refs_for_story(story_id, target_rows[0])
        stories.append(
            {
                "story_id": story_id,
                "selection_key": stable_hash(
                    {
                        "wave": "HDB1-W2",
                        "story_id": story_id,
                        "target_ids": [row["target_id"] for row in target_rows],
                        "source_refs": story_refs,
                    }
                ),
                "source_refs": story_refs,
                "previous_hng2_overlap": False,
                "hdb1_w1_overlap": False,
                "reused_story": False,
                "targets": target_rows,
            }
        )
    stories.sort(key=lambda row: (str(row["selection_key"]), str(row["story_id"])))

    core: dict[str, Any] = {
        "stage": STAGE,
        "wave_id": "HDB1-W2",
        "run_version": RUN_VERSION,
        "algorithm_version": "HNG2-C.3/HNG2-V1-frozen",
        "prompt_versions": {
            "person_read": frozen.PROMPT_VERSION,
            "person_fill": frozen.PROMPT_VERSION,
            "temporal_read": frozen.PROMPT_VERSION,
            "temporal_fill": frozen.PROMPT_VERSION,
        },
        "model": frozen.MODEL,
        "temperature": 0,
        "frozen_before_live": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "production_story_count": len(production_ids),
        "prior_hng2_story_count": len(prior_ids),
        "hdb1_w1_story_count": len(w1_ids),
        "remaining_story_count": len(stories),
        "story_count": len(stories),
        "story_ids": [str(row["story_id"]) for row in stories],
        "stories": stories,
        "person_target_count": sum(len(row.get("targets", [])) for row in stories),
        "expected_semantic_calls": 2 * sum(len(row.get("targets", [])) for row in stories) + 2 * len(stories),
        "prior_hng2_hash": prior.get("exclusion_hash"),
        "hdb1_w1_selection_hash": w1_selection.get("selection_hash"),
        "prior_hng2_production_overlap_count": len(prior_ids & production_ids),
        "prior_hng2_outside_production_count": len(prior_ids - production_ids),
        "prior_hng2_production_overlap_ids": sorted(prior_ids & production_ids),
        "production_scope_hash": stable_hash(sorted(production_ids)),
        "production_scope_file_sha256": file_hash(ROOT / "data/derived/sc1-site.json"),
        "prior_hng2_exclusion": prior,
        "overlap_with_prior_hng2": [],
        "overlap_with_hdb1_w1": [],
        "protected_hashes_before_live": protected_hashes(),
        "selection_method": "production minus prior-HNG2 and HDB1-W1 sets; deterministic target/evidence metadata; no model output",
        "w1_candidate_context_excluded": True,
        "no_search_plan": True,
        "no_research_gap_loop": True,
        "no_recursive_retrieval": True,
    }
    core["selection_hash"] = stable_hash(core)
    return core


def ensure_selection() -> dict[str, Any]:
    candidate = build_selection()
    if SELECTION_PATH.is_file():
        existing = read_json(SELECTION_PATH, {}) or {}
        existing_hash = existing.get("selection_hash")
        if not existing_hash or stable_hash({key: value for key, value in existing.items() if key != "selection_hash"}) != existing_hash:
            raise RuntimeError("hdb1_w2_selection_existing_hash_invalid")
        if stable_hash(existing) != stable_hash(candidate):
            raise RuntimeError("hdb1_w2_selection_immutable_mismatch")
        return existing
    write_json(SELECTION_PATH, candidate)
    return candidate


def load_frozen_selection() -> dict[str, Any]:
    selection = read_json(SELECTION_PATH, {}) or {}
    selection_hash = selection.get("selection_hash")
    if not selection_hash or stable_hash({key: value for key, value in selection.items() if key != "selection_hash"}) != selection_hash:
        raise RuntimeError("hdb1_w2_selection_hash_invalid")
    if selection.get("frozen_before_live") is not True or selection.get("canonical_write_back") is not False:
        raise RuntimeError("hdb1_w2_selection_not_frozen")
    return selection


def run_live(selection: Mapping[str, Any], run_id: str) -> dict[str, Any]:
    base = OUT / "live" / run_id
    if base.exists():
        raise RuntimeError(f"hdb1_w2_immutable_live_run_exists:{base}")
    raw_dir = base / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=False)
    preflight = frozen.preflight()
    write_json(base / "preflight.json", preflight)
    if preflight.get("status") != "reachable":
        write_json(
            base / "manifest.json",
            {
                "stage": STAGE,
                "wave_id": "HDB1-W2",
                "run_id": run_id,
                "status": "execution_environment_failure",
                "failure": "approved_network_preflight_failed",
                "preflight": preflight,
                "semantic_calls": 0,
                "candidate_only": True,
                "canonical_write_back": False,
            },
        )
        raise RuntimeError("hdb1_w2_approved_network_preflight_failed")

    person_units, temporal_units = wave1.build_units(selection)
    # This is the same frozen prior-HNG2 evidence context used by W1.  No W1
    # candidate artifact is loaded or sent to the semantic pipeline.
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
        raise RuntimeError(f"hdb1_w2_semantic_call_count_mismatch:{sequence - 1}:{expected}")
    operations = wave1._operation_metrics(person_results, temporal_results, preflight, selection)
    raw_hashes = wave1._raw_hashes(raw_dir)
    manifest = {
        "stage": STAGE,
        "wave_id": "HDB1-W2",
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
        "provider_failures": operations.get("provider_failures"),
        "parse_failures": operations.get("parse_failures"),
        "truncated_responses": operations.get("truncated_responses"),
        "preflight_calls": 1,
        "candidate_only": True,
        "canonical_write_back": False,
        "raw_api_immutable": True,
        "raw_api_hashes": raw_hashes,
        "overlap_with_prior_hng2": [],
        "overlap_with_hdb1_w1": [],
        "w1_candidate_context_excluded": True,
        "no_search_plan": True,
        "no_research_gap_loop": True,
        "no_recursive_retrieval": True,
        "protected_hashes_before_live": selection.get("protected_hashes_before_live", {}),
        "created_at": utc_now(),
    }
    write_json(base / "person-results.json", person_results)
    write_json(base / "temporal-results.json", temporal_results)
    write_json(
        base / "production-summary.json",
        {
            "stage": STAGE,
            "wave_id": "HDB1-W2",
            "run_id": run_id,
            "candidate_only": True,
            "canonical_write_back": False,
            "selection_hash": selection.get("selection_hash"),
            "stories_processed": len(temporal_results),
            "person_targets": len(person_results),
            "semantic_calls": operations.get("semantic_calls_attempted"),
            "expected_semantic_calls": expected,
            "operations": operations,
        },
    )
    write_json(base / "manifest.json", manifest)
    return {"output": str(base), "manifest": manifest}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--live", action="store_true")
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
