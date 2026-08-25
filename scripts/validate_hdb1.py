#!/usr/bin/env python3
"""Validate HDB1-W1 selection, live provenance, and candidate safety gates."""

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

import build_hdb1_candidate_database as builder  # noqa: E402
from hdb1_common import (  # noqa: E402
    PERSON_LIKE_KINDS,
    SELECTION_PATH,
    ensure_selection,
    file_hash,
    load_frozen_selection,
    production_story_rows,
    protected_hashes,
    read_json,
    stable_hash,
)


ROOT_OUT = ROOT / "data/generated/hdb1-wave1"
PRODUCTION_PERSON_RE = re.compile(r"^person-[0-9]+$")


def _fail(errors: list[str], message: str) -> None:
    errors.append(message)


def validate_selection(selection: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    stories = list(selection.get("stories", []))
    production_ids = {str(row["id"]) for row in production_story_rows()}
    selected_ids = [str(row.get("story_id")) for row in stories]
    if selection.get("story_count") != 48 or len(stories) != 48 or len(set(selected_ids)) != 48:
        _fail(errors, "selection_not_48_unique")
    if any(story_id not in production_ids for story_id in selected_ids):
        _fail(errors, "selection_outside_sc1_production_scope")
    counts: dict[str, int] = {}
    for row in stories:
        counts[str(row.get("stratum"))] = counts.get(str(row.get("stratum")), 0) + 1
        overlap = str(row.get("story_id")) in set(selection.get("previous_hng2_exclusion", {}).get("story_ids", []))
        if bool(row.get("previous_hng2_overlap")) != overlap:
            _fail(errors, f"overlap_metadata_mismatch:{row.get('story_id')}")
        if bool(row.get("previous_hng2_overlap")) != bool(row.get("reused_story")):
            _fail(errors, f"reuse_metadata_mismatch:{row.get('story_id')}")
        targets = list(row.get("targets", []))
        if not 1 <= len(targets) <= 2:
            _fail(errors, f"target_count_out_of_range:{row.get('story_id')}")
        for target in targets:
            if target.get("source_section") != "main_text":
                _fail(errors, f"non_main_target:{target.get('target_id')}")
            if not target.get("surface"):
                _fail(errors, f"empty_target_surface:{target.get('target_id')}")
    if counts != {"social-density": 16, "temporal-gap": 16, "baseline": 16}:
        _fail(errors, f"strata_not_16_each:{counts}")
    if selection.get("frozen_before_live") is not True or selection.get("canonical_write_back") is not False:
        _fail(errors, "selection_freeze_or_write_flag_invalid")
    core = {key: value for key, value in selection.items() if key != "selection_hash"}
    if stable_hash(core) != selection.get("selection_hash"):
        _fail(errors, "selection_hash_invalid")
    if selection.get("selection_hash") != read_json(SELECTION_PATH, {}).get("selection_hash"):
        _fail(errors, "selection_file_hash_mismatch")
    expected_calls = 2 * int(selection.get("person_target_count") or 0) + 96
    if selection.get("expected_semantic_calls") != expected_calls:
        _fail(errors, "expected_semantic_call_formula_invalid")
    return errors


def _raw_api_validation(run_id: str, manifest: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    raw_dir = ROOT_OUT / "live" / run_id / "raw-api"
    if not raw_dir.is_dir():
        return ["raw_api_directory_missing"]
    expected = manifest.get("raw_api_hashes") or {}
    actual = {str(path.relative_to(raw_dir)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(raw_dir.glob("*.json"))}
    if expected != actual:
        _fail(errors, "raw_api_hash_manifest_mismatch")
    for path in raw_dir.glob("*.json"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "DEEPSEEK_API_KEY" in text or "sk-" in text:
            _fail(errors, f"possible_api_key_in_raw:{path.name}")
    return errors


def _result_maps(run_id: str) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    base = ROOT_OUT / "live" / run_id
    person = read_json(base / "person-results.json", []) or []
    temporal = read_json(base / "temporal-results.json", []) or []
    return ({str(row.get("unit_id")): row for row in person}, {str(row.get("unit_id")): row for row in temporal})


def _candidate_evidence_errors(run_id: str, projection: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    person_map, temporal_map = _result_maps(run_id)
    def has_span(row: Mapping[str, Any], ref: Any, span: Any) -> bool:
        text = str(span or "")
        if not ref or not text:
            return False
        return any(str(window.get("ref")) == str(ref) and text in str(window.get("evidence_text") or "") for window in row.get("evidence_windows", []))
    for candidate in projection.get("person_candidates", []):
        result = person_map.get(str(candidate.get("unit_id")))
        if result is None or not has_span(result, candidate.get("evidence_ref"), candidate.get("exact_span")):
            _fail(errors, f"person_candidate_evidence_not_grounded:{candidate.get('candidate_id')}")
        if candidate.get("provisional_person_id") and PRODUCTION_PERSON_RE.fullmatch(str(candidate["provisional_person_id"])):
            _fail(errors, f"production_person_id_allocated:{candidate.get('candidate_id')}")
    for candidate in [*projection.get("relation_candidates", []), *projection.get("kinship_candidates", []), *projection.get("marriage_candidates", []), *projection.get("office_candidates", [])]:
        result = person_map.get(str(candidate.get("unit_id")))
        if result is None or not has_span(result, candidate.get("evidence_ref"), candidate.get("exact_span")):
            _fail(errors, f"relation_candidate_evidence_not_grounded:{candidate.get('candidate_id')}")
        if not str(candidate.get("relation_surface") or "") or str(candidate.get("relation_surface")) not in str(candidate.get("exact_span") or ""):
            _fail(errors, f"relation_surface_not_preserved:{candidate.get('candidate_id')}")
        subject = candidate.get("subject_person_id") or candidate.get("subject_provisional_person_id")
        obj = candidate.get("object_person_id") or candidate.get("object_provisional_person_id")
        if subject and obj and subject == obj:
            _fail(errors, f"collapsed_nonidentity_self_relation:{candidate.get('candidate_id')}")
    for candidate in projection.get("temporal_candidates", []):
        result = temporal_map.get(str(candidate.get("unit_id")))
        if result is None or not has_span(result, candidate.get("evidence_ref"), candidate.get("exact_span")):
            _fail(errors, f"temporal_candidate_evidence_not_grounded:{candidate.get('temporal_candidate_id')}")
        role = str(candidate.get("temporal_role") or "")
        if role in {"later_outcome", "quoted_precedent", "background_context"} and candidate.get("scene_time_candidate"):
            _fail(errors, f"non_scene_temporal_promoted:{candidate.get('temporal_candidate_id')}")
        if candidate.get("scene_time_candidate") and candidate.get("h0a_status") == "conflict":
            _fail(errors, f"scene_temporal_conflict_projected:{candidate.get('temporal_candidate_id')}")
    return errors


def validate_run(run_id: str) -> dict[str, Any]:
    selection = load_frozen_selection()
    errors = validate_selection(selection)
    base = ROOT_OUT / "live" / run_id
    manifest = read_json(base / "manifest.json", {}) or {}
    if manifest.get("status") != "complete":
        _fail(errors, "live_manifest_not_complete")
        return {"valid": False, "errors": errors, "run_id": run_id}
    if manifest.get("selection_hash") != selection.get("selection_hash"):
        _fail(errors, "live_selection_hash_mismatch")
    if manifest.get("candidate_only") is not True or manifest.get("canonical_write_back") is not False:
        _fail(errors, "live_write_boundary_invalid")
    expected = int(selection.get("expected_semantic_calls") or 0)
    if manifest.get("semantic_calls_attempted") != expected:
        _fail(errors, f"semantic_call_count_mismatch:{manifest.get('semantic_calls_attempted')}:{expected}")
    errors.extend(_raw_api_validation(run_id, manifest))
    current_protected = protected_hashes()
    for path, before in (selection.get("protected_hashes_before_live") or {}).items():
        if current_protected.get(path) != before:
            _fail(errors, f"protected_artifact_changed:{path}")
    try:
        projection = builder.build_run(run_id, write=False)
    except Exception as exc:
        _fail(errors, f"candidate_projection_failed:{type(exc).__name__}:{exc}")
        projection = {}
    if projection:
        errors.extend(_candidate_evidence_errors(run_id, projection))
        deterministic = builder.deterministic_rebuild_check(run_id)
        if not deterministic.get("equal"):
            _fail(errors, "candidate_projection_not_deterministic")
    return {
        "valid": not errors,
        "errors": errors,
        "run_id": run_id,
        "selection_hash": selection.get("selection_hash"),
        "semantic_calls": manifest.get("semantic_calls_attempted"),
        "canonical_write_back": False,
        "protected_hashes_unchanged": not any(error.startswith("protected_artifact_changed") for error in errors),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection-only", action="store_true")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    if args.selection_only:
        selection = load_frozen_selection()
        result = {"valid": not validate_selection(selection), "errors": validate_selection(selection), "selection_hash": selection.get("selection_hash")}
    elif args.run_id:
        result = validate_run(args.run_id)
    else:
        parser.error("--run-id or --selection-only is required")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())

