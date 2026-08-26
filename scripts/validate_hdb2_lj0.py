#!/usr/bin/env python3
"""Validate HDB2-LJ0 selection, strict packets, and candidate-only results."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hdb2_lj0_common as common  # noqa: E402
from run_hdb2_lj0 import protected_hashes  # noqa: E402


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_run() -> Path | None:
    root = ROOT / "data/generated/hdb2-lj0/live"
    runs = sorted((path for path in root.iterdir() if path.is_dir()), key=lambda path: path.name) if root.is_dir() else []
    return runs[-1] if runs else None


def validate(selection: Mapping[str, Any], cases_doc: Mapping[str, Any] | None = None, run_dir: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    rows = list(selection.get("cases", []))
    if not 20 <= len(rows) <= 30:
        errors.append("selection_count_out_of_range")
    if not selection.get("frozen_before_live"):
        errors.append("selection_not_frozen")
    if selection.get("candidate_only") is not True:
        errors.append("selection_not_candidate_only")
    if selection.get("canonical_write_back") is not False:
        errors.append("selection_canonical_write_back")
    occurrence_ids = [str(row.get("occurrence_id")) for row in rows]
    if len(set(occurrence_ids)) != len(occurrence_ids):
        errors.append("duplicate_occurrence_ids")
    if not any(str(row.get("story_id")) == "05-fangzheng-011" and str(row.get("surface")) == "武帝" for row in rows):
        errors.append("required_wudi_case_missing")
    categories = {str(row.get("selection_category")) for row in rows}
    for category in ("candidate_person", "compositional_reference", "office_title_holder", "ambiguous_identity"):
        if category not in categories:
            errors.append(f"selection_category_missing:{category}")
    if cases_doc is not None:
        cases = list(cases_doc.get("cases", []))
        if len(cases) != len(rows):
            errors.append("case_count_mismatch")
        for case in cases:
            packet = common.wire_packet(case)
            rendered = json.dumps(packet, ensure_ascii=False, sort_keys=True)
            if any(token in rendered for token in ("person_id", "provisional_person_id", "relation_id", "graph_id")):
                errors.append(f"provider_id_in_packet:{case.get('occurrence_id')}")
            if not all(str(candidate.get("candidate_key", "")).startswith("c") for candidate in case.get("candidates", [])):
                errors.append(f"non_local_candidate_key:{case.get('occurrence_id')}")
            evidence_ids = {str(row.get("evidence_id")) for row in case.get("evidence_items", [])}
            if len(evidence_ids) != len(case.get("evidence_items", [])):
                errors.append(f"duplicate_evidence_ids:{case.get('occurrence_id')}")
            if any(str(row.get("evidence_id")) not in evidence_ids for row in case.get("evidence_items", [])):
                errors.append(f"missing_evidence_id:{case.get('occurrence_id')}")
    run_summary: dict[str, Any] = {}
    if run_dir is not None:
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.is_file():
            errors.append("run_manifest_missing")
        else:
            manifest = _load(manifest_path)
            if manifest.get("candidate_only") is not True or manifest.get("canonical_write_back") is not False:
                errors.append("run_projection_flags_invalid")
            if manifest.get("protected_hashes_before") != manifest.get("protected_hashes_after"):
                errors.append("protected_hashes_changed_during_run")
            run_summary["status"] = manifest.get("status", "complete")
        decisions_path = run_dir / "decisions.json"
        if decisions_path.is_file():
            decisions = _load(decisions_path).get("records", [])
            if any(row.get("candidate_only") is not True or row.get("canonical_write_back") is not False for row in decisions):
                errors.append("decision_projection_flags_invalid")
            if any(row.get("result_state") not in common.PERSON_RESULT_STATES for row in decisions):
                errors.append("invalid_experimental_result_state")
            run_summary["decision_count"] = len(decisions)
    return {"valid": not errors, "errors": sorted(set(errors)), "selection_count": len(rows), "run": run_summary}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path)
    args = parser.parse_args()
    selection_path = ROOT / "data/annotation/hdb2-lj0-selection.json"
    if not selection_path.is_file():
        print(json.dumps({"valid": False, "errors": ["selection_missing"]}, ensure_ascii=False, indent=2))
        return 1
    selection = _load(selection_path)
    cases_doc = None
    run_dir = args.run_dir if args.run_dir and args.run_dir.is_absolute() else (ROOT / args.run_dir if args.run_dir else _latest_run())
    if run_dir and (run_dir / "cases.json").is_file():
        cases_doc = _load(run_dir / "cases.json")
    result = validate(selection, cases_doc, run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
