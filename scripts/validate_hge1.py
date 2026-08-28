#!/usr/bin/env python3
"""Validate HGE1-WA selection and candidate-only growth artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import hge1_wave_a as wave  # noqa: E402


def _default_run_base() -> Path | None:
    """Choose the strongest completed run for a no-argument validation.

    Preparation often leaves an offline fixture beside the live run.  A
    lexical directory sort would select that fixture even when a reachable
    provider run exists, so the validator prefers a reachable live manifest
    and falls back to the newest deterministic offline artifact only when no
    such run is present.
    """
    candidates: list[tuple[tuple[int, int, str], Path]] = []
    for manifest_path in (wave.GENERATED / "live").glob("*/manifest.json"):
        manifest = wave.read_json(manifest_path, {}) or {}
        preflight = manifest.get("preflight") if isinstance(manifest.get("preflight"), dict) else {}
        reachable = int(preflight.get("status") == "reachable")
        live_requested = int(manifest.get("live_requested") is True)
        candidates.append(((reachable, live_requested, manifest_path.parent.name), manifest_path.parent))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def validate(run_id: str | None = None) -> dict[str, object]:
    errors = list(wave.validate_selection(wave.read_json(wave.SELECTION_PATH, {}) or {}))
    selection = wave.read_json(wave.SELECTION_PATH, {}) or {}
    target_selection = wave.read_json(wave.TARGET_SELECTION_PATH, {}) or {}
    errors.extend(wave.validate_target_selection(selection, target_selection))
    frozen_baseline = wave.read_json(wave.GENERATED / "baseline.json", {}) or {}
    if not frozen_baseline:
        errors.append("missing_frozen_baseline")
    elif frozen_baseline != wave.baseline():
        errors.append("baseline_snapshot_drift")
    if frozen_baseline.get("protected_hashes") != wave.hda1.protected_hashes():
        errors.append("protected_hash_drift")
    if run_id:
        run_base = wave.GENERATED / "live" / run_id
    else:
        run_base = _default_run_base()
    candidate = wave.read_json(wave.DERIVED / "hge1-wave-a-candidate-db.json", {}) or {}
    growth = wave.read_json(wave.DERIVED / "hge1-wave-a-metrics.json", {}) or {}
    for document, name in ((candidate, "candidate_db"), (growth, "growth")):
        if document.get("candidate_only") is not True or document.get("canonical_write_back") is not False:
            errors.append(f"{name}_safety_flags")
    for row in candidate.get("person_observations", []) or []:
        cid = str(row.get("candidate_person_id") or "")
        if cid.startswith("person-"):
            errors.append(f"production_id_allocated:{cid}")
    for row in candidate.get("relation_candidates", []) or []:
        if row.get("cooccurrence_only") is True:
            errors.append(f"cooccurrence_relation:{row.get('candidate_id')}")
        if not row.get("evidence_ref") or not row.get("exact_span"):
            errors.append(f"relation_provenance:{row.get('candidate_id')}")
    if run_base and run_base.is_dir():
        manifest = wave.read_json(run_base / "manifest.json", {}) or {}
        if manifest.get("selection_hash") != selection.get("selection_hash"): errors.append("run_selection_hash")
        if manifest.get("target_selection_hash") != target_selection.get("target_selection_hash"): errors.append("run_target_selection_hash")
        if manifest.get("protected_hashes_before") != frozen_baseline.get("protected_hashes"): errors.append("run_protected_hash_snapshot")
        if manifest.get("candidate_only") is not True or manifest.get("canonical_write_back") is not False: errors.append("run_safety_flags")
    # Rebuilding the deterministic projection from the immutable run twice is
    # the HGE1 byte-stability check.  API response files are not touched.
    deterministic = False
    if run_base and run_base.is_dir():
        run = {"base": run_base, "person_results": wave.read_json(run_base / "person-results.json", []) or [], "temporal_results": wave.read_json(run_base / "temporal-results.json", []) or [], "target_selection": target_selection}
        first = wave.build_projection(selection, run)
        second = wave.build_projection(selection, run)
        deterministic = wave.stable_hash(first) == wave.stable_hash(second)
        if not deterministic: errors.append("projection_not_deterministic")
    output = {"schema": "hge1-validation-v1", "valid": not errors, "errors": sorted(set(errors)), "selection_hash": selection.get("selection_hash"), "story_count": len(selection.get("story_ids", []) or []), "deterministic_projection": deterministic, "candidate_only": True, "canonical_write_back": False}
    wave.write_json(wave.GENERATED / "validation.json", output)
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
