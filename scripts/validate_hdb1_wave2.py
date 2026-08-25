#!/usr/bin/env python3
"""Validate HDB1-W2 and the offline W1+W2 candidate aggregate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_hdb1_cross_wave_database as cross  # noqa: E402
import build_hdb1_candidate_database as builder  # noqa: E402
import run_hdb1_wave2 as wave2  # noqa: E402
import run_hng2_fresh_validation as frozen  # noqa: E402
from hdb1_common import (  # noqa: E402
    PERSON_LIKE_KINDS,
    load_frozen_selection as load_w1_selection,
    production_story_rows,
    protected_hashes,
    read_json,
    stable_hash,
)


PRODUCTION_PERSON_RE = re.compile(r"^person-[0-9]+$")
W1_ROOT = ROOT / "data/generated/hdb1-wave1"
W2_ROOT = ROOT / "data/generated/hdb1-wave2"


def _fail(errors: list[str], message: str) -> None:
    errors.append(message)


def validate_selection(selection: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    production_ids = {str(row["id"]) for row in production_story_rows()}
    w1 = load_w1_selection()
    w1_ids = {str(row["story_id"]) for row in w1.get("stories", [])}
    prior_ids = {str(value) for value in (selection.get("prior_hng2_exclusion") or {}).get("story_ids", [])}
    selected_ids = [str(value) for value in selection.get("story_ids", [])]
    story_rows = list(selection.get("stories", []))
    if selection.get("story_count") != len(selected_ids) or len(selected_ids) != len(set(selected_ids)):
        _fail(errors, "w2_story_id_shape_invalid")
    if set(selected_ids) != {str(row.get("story_id")) for row in story_rows}:
        _fail(errors, "w2_story_ids_rows_mismatch")
    if not set(selected_ids) <= production_ids:
        _fail(errors, "w2_story_outside_production_scope")
    expected_ids = production_ids - (prior_ids & production_ids) - w1_ids
    if set(selected_ids) != expected_ids:
        _fail(errors, f"w2_remaining_set_mismatch:{len(selected_ids)}:{len(expected_ids)}")
    if set(selected_ids) & prior_ids:
        _fail(errors, "w2_overlap_prior_hng2")
    if set(selected_ids) & w1_ids:
        _fail(errors, "w2_overlap_hdb1_w1")
    if selection.get("overlap_with_prior_hng2") != [] or selection.get("overlap_with_hdb1_w1") != []:
        _fail(errors, "w2_overlap_metadata_nonempty")
    if selection.get("production_story_count") != 143 or selection.get("prior_hng2_story_count") != len(prior_ids) or selection.get("hdb1_w1_story_count") != len(w1_ids):
        _fail(errors, "w2_scope_counts_invalid")
    if selection.get("prior_hng2_production_overlap_count") != len(prior_ids & production_ids):
        _fail(errors, "w2_prior_production_overlap_count_invalid")
    if selection.get("prior_hng2_outside_production_count") != len(prior_ids - production_ids):
        _fail(errors, "w2_prior_outside_production_count_invalid")
    if selection.get("frozen_before_live") is not True or selection.get("canonical_write_back") is not False:
        _fail(errors, "w2_freeze_boundary_invalid")
    if selection.get("w1_candidate_context_excluded") is not True:
        _fail(errors, "w1_candidate_context_flag_invalid")
    core = {key: value for key, value in selection.items() if key != "selection_hash"}
    if stable_hash(core) != selection.get("selection_hash"):
        _fail(errors, "w2_selection_hash_invalid")
    if selection.get("selection_hash") != (read_json(ROOT / "data/annotation/hdb1-wave2-selection.json", {}) or {}).get("selection_hash"):
        _fail(errors, "w2_selection_file_hash_invalid")
    expected_calls = 2 * int(selection.get("person_target_count") or 0) + 2 * len(selected_ids)
    if selection.get("expected_semantic_calls") != expected_calls:
        _fail(errors, "w2_semantic_call_formula_invalid")
    for row in story_rows:
        targets = list(row.get("targets", []))
        if not 1 <= len(targets) <= 2:
            _fail(errors, f"w2_target_count_invalid:{row.get('story_id')}")
        for target in targets:
            if target.get("source_section") != "main_text" or not target.get("surface"):
                _fail(errors, f"w2_target_boundary_invalid:{target.get('target_id')}")
    return errors


def _raw_validation(run_id: str, manifest: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    raw_dir = W2_ROOT / "live" / run_id / "raw-api"
    if not raw_dir.is_dir():
        return ["w2_raw_api_directory_missing"]
    actual = {str(path.relative_to(raw_dir)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(raw_dir.glob("*.json"))}
    if actual != (manifest.get("raw_api_hashes") or {}):
        _fail(errors, "w2_raw_api_hash_mismatch")
    for path in raw_dir.glob("*.json"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "DEEPSEEK_API_KEY" in text or "sk-" in text:
            _fail(errors, f"possible_api_key_in_w2_raw:{path.name}")
    return errors


def _same_window_span(result: Mapping[str, Any], ref: Any, span: Any) -> bool:
    if not ref or not span:
        return False
    return any(str(window.get("ref")) == str(ref) and str(span) in str(window.get("evidence_text") or "") for window in result.get("evidence_windows", []))


def _w2_projection_errors(run_id: str, projection: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    base = W2_ROOT / "live" / run_id
    person_results = read_json(base / "person-results.json", []) or []
    temporal_results = read_json(base / "temporal-results.json", []) or []
    person_map = {str(row.get("unit_id")): row for row in person_results}
    temporal_map = {str(row.get("unit_id")): row for row in temporal_results}
    for candidate in projection.get("person_candidates", []):
        result = person_map.get(str(candidate.get("unit_id")))
        if result is None or not _same_window_span(result, candidate.get("evidence_ref"), candidate.get("exact_span")):
            _fail(errors, f"w2_person_evidence_not_grounded:{candidate.get('candidate_id')}")
        if candidate.get("provisional_person_id") and PRODUCTION_PERSON_RE.fullmatch(str(candidate.get("provisional_person_id"))):
            _fail(errors, f"w2_production_person_id_allocated:{candidate.get('candidate_id')}")
    for candidate in [*projection.get("relation_candidates", []), *projection.get("kinship_candidates", []), *projection.get("marriage_candidates", []), *projection.get("office_candidates", [])]:
        result = person_map.get(str(candidate.get("unit_id")))
        if result is None or not _same_window_span(result, candidate.get("evidence_ref"), candidate.get("exact_span")):
            _fail(errors, f"w2_relation_evidence_not_grounded:{candidate.get('candidate_id')}")
        if candidate.get("relation_surface") and str(candidate["relation_surface"]) not in str(candidate.get("exact_span") or ""):
            _fail(errors, f"w2_relation_surface_not_preserved:{candidate.get('candidate_id')}")
        subject = candidate.get("subject_person_id") or candidate.get("subject_provisional_person_id")
        obj = candidate.get("object_person_id") or candidate.get("object_provisional_person_id")
        if subject and obj and subject == obj:
            _fail(errors, f"w2_self_relation:{candidate.get('candidate_id')}")
    for candidate in projection.get("temporal_candidates", []):
        result = temporal_map.get(str(candidate.get("unit_id")))
        if result is None or not _same_window_span(result, candidate.get("evidence_ref"), candidate.get("exact_span")):
            _fail(errors, f"w2_temporal_evidence_not_grounded:{candidate.get('temporal_candidate_id')}")
        if candidate.get("scene_time_candidate") and str(candidate.get("temporal_role")) in {"later_outcome", "quoted_precedent", "background_context"}:
            _fail(errors, f"w2_non_scene_temporal_promoted:{candidate.get('temporal_candidate_id')}")
        if candidate.get("scene_time_candidate") and candidate.get("h0a_status") == "conflict":
            _fail(errors, f"w2_scene_h0a_conflict_projected:{candidate.get('temporal_candidate_id')}")
    return errors


def _w1_context_errors(run_id: str) -> list[str]:
    errors: list[str] = []
    w1_db = read_json(ROOT / "data/derived/hdb1-candidate-historical-db.json", {}) or {}
    forbidden: set[str] = set()
    for key in ("person_candidates", "identity_candidates", "relation_candidates", "kinship_candidates", "marriage_candidates", "office_candidates", "temporal_candidates"):
        for row in w1_db.get(key, []) or []:
            for field in ("candidate_id", "identity_observation_id", "provisional_person_id", "temporal_candidate_id", "candidate_fact_id"):
                value = row.get(field)
                if value:
                    forbidden.add(str(value))
    base = W2_ROOT / "live" / run_id
    for name in ("person-results.json", "temporal-results.json"):
        text = (base / name).read_text(encoding="utf-8")
        leaked = sorted(value for value in forbidden if value in text)
        if leaked:
            _fail(errors, f"w1_candidate_context_in_w2_prompt_or_result:{name}:{leaked[:3]}")
    return errors


def validate_run(run_id: str) -> dict[str, Any]:
    selection = wave2.load_frozen_selection()
    errors = validate_selection(selection)
    base = W2_ROOT / "live" / run_id
    manifest = read_json(base / "manifest.json", {}) or {}
    if manifest.get("status") != "complete":
        _fail(errors, "w2_manifest_not_complete")
        return {"valid": False, "errors": errors, "run_id": run_id}
    if manifest.get("selection_hash") != selection.get("selection_hash"):
        _fail(errors, "w2_manifest_selection_hash_mismatch")
    if manifest.get("candidate_only") is not True or manifest.get("canonical_write_back") is not False:
        _fail(errors, "w2_manifest_write_boundary_invalid")
    if manifest.get("w1_candidate_context_excluded") is not True:
        _fail(errors, "w2_manifest_w1_context_flag_invalid")
    if manifest.get("semantic_calls_attempted") != selection.get("expected_semantic_calls"):
        _fail(errors, "w2_semantic_call_count_mismatch")
    errors.extend(_raw_validation(run_id, manifest))
    for path, before in (selection.get("protected_hashes_before_live") or {}).items():
        current = protected_hashes().get(path)
        if current != before:
            _fail(errors, f"protected_artifact_changed:{path}")
    errors.extend(_w1_context_errors(run_id))
    try:
        projection = cross.load_wave_projection("HDB1-W2", run_id)
        errors.extend(_w2_projection_errors(run_id, projection))
        first = stable_hash(cross.load_wave_projection("HDB1-W2", run_id))
        second = stable_hash(cross.load_wave_projection("HDB1-W2", run_id))
        if first != second:
            _fail(errors, "w2_projection_not_deterministic")
    except Exception as exc:
        _fail(errors, f"w2_projection_failed:{type(exc).__name__}:{exc}")
    return {
        "valid": not errors,
        "errors": errors,
        "run_id": run_id,
        "selection_hash": selection.get("selection_hash"),
        "semantic_calls": manifest.get("semantic_calls_attempted"),
        "canonical_write_back": False,
        "protected_hashes_unchanged": not any(error.startswith("protected_artifact_changed") for error in errors),
    }


def validate_aggregate(w1_run_id: str, w2_run_id: str) -> dict[str, Any]:
    errors: list[str] = []
    try:
        result = cross.build_all(w1_run_id, w2_run_id, write=False)
        aggregate = result["aggregate"]
        if aggregate.get("candidate_only") is not True or aggregate.get("canonical_write_back") is not False:
            _fail(errors, "aggregate_write_boundary_invalid")
        for row in aggregate.get("candidate_identity_registry", []):
            if row.get("resolved_person_id") is None and PRODUCTION_PERSON_RE.fullmatch(str(row.get("resolved_person_id") or "")):
                _fail(errors, "aggregate_allocated_production_person_id")
            if row.get("surface_bucket_only") and row.get("status") != "unresolved_surface_cluster":
                _fail(errors, "surface_bucket_promoted_to_identity")
        for row in aggregate.get("candidate_facts", []):
            if row.get("canonical_write_back") is not False or row.get("candidate_only") is not True:
                _fail(errors, f"aggregate_fact_write_boundary:{row.get('candidate_fact_id')}")
            if row.get("subject_cluster_id") and row.get("subject_cluster_id") == row.get("object_cluster_id") and row.get("relation_class") != "identity_name":
                _fail(errors, f"aggregate_self_relation:{row.get('candidate_fact_id')}")
        first = stable_hash(cross.build_all(w1_run_id, w2_run_id, write=False)["aggregate"])
        second = stable_hash(cross.build_all(w1_run_id, w2_run_id, write=False)["aggregate"])
        if first != second:
            _fail(errors, "aggregate_not_deterministic")
    except Exception as exc:
        _fail(errors, f"aggregate_validation_failed:{type(exc).__name__}:{exc}")
    return {"valid": not errors, "errors": errors, "w1_run_id": w1_run_id, "w2_run_id": w2_run_id, "api_calls": 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection-only", action="store_true")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--aggregate", action="store_true")
    parser.add_argument("--w1-run-id", default=None)
    parser.add_argument("--w2-run-id", default=None)
    args = parser.parse_args()
    if args.selection_only:
        selection = wave2.load_frozen_selection()
        result = {"valid": not validate_selection(selection), "errors": validate_selection(selection), "selection_hash": selection.get("selection_hash")}
    elif args.aggregate:
        w1_id = args.w1_run_id or cross._latest_complete_run(cross.W1_ROOT)
        w2_id = args.w2_run_id or cross._latest_complete_run(cross.W2_ROOT)
        result = validate_aggregate(w1_id, w2_id)
    elif args.run_id:
        result = validate_run(args.run_id)
    else:
        parser.error("--selection-only, --run-id, or --aggregate is required")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
