#!/usr/bin/env python3
"""Validate the bounded F1 run without rebuilding or contacting a provider."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_f1.common import (  # noqa: E402
    OUT,
    exact_key,
    protected_snapshot,
    read_json,
    selection_rows,
    snapshot_diff,
    stable_hash,
    text,
)


def _records(name: str) -> list[dict[str, Any]]:
    document = read_json(OUT / name, {}) or {}
    return [dict(row) for row in document.get("records", []) or [] if isinstance(row, Mapping)]


def _by_occurrence(name: str) -> dict[str, dict[str, Any]]:
    return {
        text(row.get("occurrence_id") or row.get("case_id") or (row.get("occurrence_key") or {}).get("occurrence_id")): row
        for row in _records(name)
        if text(row.get("occurrence_id") or row.get("case_id") or (row.get("occurrence_key") or {}).get("occurrence_id"))
    }


def validate() -> dict[str, Any]:
    selection = selection_rows()
    selected_ids = [text(row.get("occurrence_id")) for row in selection]
    selected_keys = {text(row.get("occurrence_id")): exact_key(row) for row in selection}
    preflight = read_json(OUT / "preflight-validation.json", {}) or {}
    before = preflight.get("protected_snapshot_before_live")
    after = protected_snapshot()
    errors: list[str] = []
    if not isinstance(before, Mapping):
        errors.append("protected_preflight_snapshot_missing")
    elif snapshot_diff(before, after):
        errors.append("protected_hash_mutation:" + ",".join(snapshot_diff(before, after)))

    architecture = read_json(OUT / "architecture-verification.json", {}) or {}
    if architecture.get("baseline_commit") != "b30c380095772f61dcf3109b75535a70007c47ab":
        errors.append("baseline_commit_mismatch")
    if architecture.get("a2ov_excluded") is not True or architecture.get("a2or_primary_included") is not True or architecture.get("a2ovb_boundary_included") is not True:
        errors.append("frozen_dag_mismatch")

    identity = _by_occurrence("identity-results.json")
    primary = _by_occurrence("occurrence-primary-results.json")
    boundary = _by_occurrence("boundary-results.json")
    candidates = _by_occurrence("candidate-semantic-records.json")
    queue = _by_occurrence("review-queue.json")
    for name, table in (("identity", identity), ("occurrence_primary", primary), ("candidate", candidates), ("review_queue", queue)):
        if set(table) != set(selected_ids):
            errors.append(f"{name}_occurrence_set_mismatch")
    if not set(boundary).issubset(set(selected_ids)):
        errors.append("boundary_occurrence_set_mismatch")

    for occurrence_id in selected_ids:
        candidate = candidates.get(occurrence_id)
        if isinstance(candidate, Mapping):
            if candidate.get("occurrence_key") != selected_keys[occurrence_id]:
                errors.append("candidate_exact_key_mismatch:" + occurrence_id)
            if candidate.get("candidate_only") is not True or candidate.get("canonical_write_back") is not False:
                errors.append("candidate_safety_mismatch:" + occurrence_id)
        identity_row = identity.get(occurrence_id, {})
        primary_row = primary.get(occurrence_id, {})
        primary_result = primary_row.get("occurrence_result") if isinstance(primary_row.get("occurrence_result"), Mapping) else {}
        if identity_row.get("candidate_only") is not True or identity_row.get("canonical_write_back") is not False:
            errors.append("identity_safety_mismatch:" + occurrence_id)
        if primary_row.get("candidate_only") is not True or primary_row.get("canonical_write_back") is not False:
            errors.append("primary_safety_mismatch:" + occurrence_id)
        routed = text(primary_result.get("narrative_function")) in {"participant", "reference"} and primary_row.get("valid") is True
        if routed and occurrence_id not in boundary:
            errors.append("missing_boundary_result:" + occurrence_id)
        if not routed and occurrence_id in boundary:
            errors.append("unexpected_boundary_result:" + occurrence_id)

    checkpoints = list((OUT / "checkpoints").glob("*.json")) if (OUT / "checkpoints").is_dir() else []
    checkpoint_units: set[str] = set()
    checkpoint_errors: list[str] = []
    for path in checkpoints:
        document = read_json(path, {}) or {}
        unit_id = text(document.get("unit_id"))
        if unit_id:
            checkpoint_units.add(unit_id)
        output = document.get("output")
        if not unit_id or not isinstance(output, Mapping) or document.get("output_hash") != stable_hash(output):
            checkpoint_errors.append(path.name)
    errors.extend("checkpoint_invalid:" + name for name in checkpoint_errors)

    resume = read_json(OUT / "resume-validation.json", {}) or {}
    if resume.get("phase_b_restarted_over_original_30") is not True or resume.get("phase_b_duplicate_semantic_writes") != 0 or resume.get("deterministic_resume") is not True:
        errors.append("resume_validation_failed")
    safety = read_json(OUT / "safety-audit.json", {}) or {}
    for key in ("canonical_writes", "production_person_creations", "alias_mutations", "profile_mutations", "identity_replacements_outside_identity_stage", "python_lexical_semantic_rules", "boundary_primary_label_leaks", "copy_drift", "undeclared_mutations"):
        if safety.get(key) != 0:
            errors.append("safety_nonzero:" + key)
    accounting = read_json(OUT / "provider-accounting.json", {}) or {}
    transport_log = read_json(OUT / "transport-log.json", []) or []
    if not isinstance(transport_log, list):
        errors.append("transport_log_not_list")
        transport_log = []
    for row in transport_log:
        if isinstance(row, Mapping):
            raw_path = text(row.get("raw_archive_path"))
            if raw_path and (str(ROOT) in raw_path or raw_path.startswith("data/")):
                errors.append("raw_provider_payload_inside_repository")

    result = {
        "schema": "sfh2-f1-validation-summary-v1",
        "valid": not errors,
        "errors": sorted(set(errors)),
        "selected_occurrences": len(selected_ids),
        "selected_stories": len({text(exact_key(row)["story_id"]) for row in selection}),
        "identity_records": len(identity),
        "occurrence_primary_records": len(primary),
        "boundary_records": len(boundary),
        "candidate_records": len(candidates),
        "review_queue_records": len(queue),
        "checkpoint_count": len(checkpoints),
        "checkpoint_units": len(checkpoint_units),
        "provider_calls": accounting.get("provider_calls", 0),
        "provider_attempts": accounting.get("provider_attempts", 0),
        "protected_hashes_unchanged": not bool(before and snapshot_diff(before, after)),
        "candidate_only": True,
        "canonical_write_back": False,
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    args = parser.parse_args(argv)
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
