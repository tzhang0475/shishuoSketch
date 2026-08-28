#!/usr/bin/env python3
"""Validate HGE1-WB selection, A+B growth, and candidate-only boundaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import hge1_wave_a as wave_a  # noqa: E402
import hge1_wave_b as wave_b  # noqa: E402


def _default_run() -> Path | None:
    candidates = sorted((wave_b.GENERATED / "live").glob("*/manifest.json"))
    return candidates[-1].parent if candidates else None


def validate(run_id: str | None = None) -> dict[str, object]:
    errors: list[str] = []
    selection = wave_b.read_json(wave_b.SELECTION_PATH, {}) or {}
    target = wave_b.read_json(wave_b.TARGET_SELECTION_PATH, {}) or {}
    errors.extend(wave_b.validate_selection(selection))
    # The selection stores a frozen exclusion snapshot rather than duplicating
    # every excluded Story ID.  Recompute that snapshot offline and compare its
    # hash so a later artifact scan cannot silently make the Wave B boundary
    # wider or narrower.
    current_prior = wave_b.previous_story_snapshot()
    if selection.get("prior_story_hash") != current_prior.get("hash"):
        errors.append("prior_story_snapshot_drift")
    errors.extend(wave_b.validate_target_selection(selection, target))
    wave_a_selection = wave_b.read_json(wave_a.SELECTION_PATH, {}) or {}
    wave_a_metrics = wave_b.read_json(wave_b.DERIVED / "hge1-wave-a-metrics.json", {}) or {}
    series = wave_b.read_json(wave_b.SERIES_PATH, {}) or {}
    rows = series.get("series", []) or []
    if [row.get("wave") for row in rows[:3]] != ["baseline", "HGE1-WA", "HGE1-WB"]:
        errors.append("growth_series_order")
    if rows and wave_a_metrics.get("after"):
        wa_row = next((row for row in rows if row.get("wave") == "HGE1-WA"), {})
        for key in ("story_count", "candidate_person_count", "graph_nodes", "graph_edges"):
            if key in wa_row and wa_row.get(key) != wave_a_metrics.get("after", {}).get(key):
                errors.append(f"wave_a_value_changed:{key}")
    database = wave_b.read_json(wave_b.DERIVED / "hge1-wave-b-candidate-db.json", {}) or {}
    growth = wave_b.read_json(wave_b.DERIVED / "hge1-wave-b-metrics.json", {}) or {}
    for document, name in ((database, "candidate_db"), (growth, "growth"), (series, "series")):
        if document.get("candidate_only") is not True or document.get("canonical_write_back") is not False:
            errors.append(f"{name}_safety_flags")
    for row in database.get("person_observations", []) or []:
        pid = str(row.get("candidate_person_id") or "")
        if pid.startswith("person-") and not row.get("person_id"):
            errors.append(f"production_candidate_id:{pid}")
    run_base = wave_b.GENERATED / "live" / run_id if run_id else _default_run()
    deterministic = False
    if run_base and run_base.is_dir():
        manifest = wave_b.read_json(run_base / "manifest.json", {}) or {}
        if manifest.get("selection_hash") != selection.get("selection_hash"):
            errors.append("run_selection_hash")
        if manifest.get("target_selection_hash") != target.get("target_selection_hash"):
            errors.append("run_target_selection_hash")
        if manifest.get("candidate_only") is not True or manifest.get("canonical_write_back") is not False:
            errors.append("run_safety_flags")
        run = {"base": run_base, "person_results": wave_b.read_json(run_base / "person-results.json", []) or [], "temporal_results": wave_b.read_json(run_base / "temporal-results.json", []) or [], "target_selection": target}
        first = wave_b.build_projection(selection, run)
        second = wave_b.build_projection(selection, run)
        deterministic = wave_b.stable_hash(first) == wave_b.stable_hash(second)
        if not deterministic:
            errors.append("projection_not_deterministic")
    output = {"schema": "hge1-wave-b-validation-v1", "valid": not errors, "errors": sorted(set(errors)), "story_count": len(selection.get("story_ids", []) or []), "selection_hash": selection.get("selection_hash"), "deterministic_projection": deterministic, "candidate_only": True, "canonical_write_back": False}
    wave_b.write_json(wave_b.GENERATED / "validation.json", output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id")
    args = parser.parse_args()
    result = validate(args.run_id)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
