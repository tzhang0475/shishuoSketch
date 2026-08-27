#!/usr/bin/env python3
"""Offline validator for HDB2-PSL1.3B.

The validator checks the conservative reference boundary and the new
ten-Story selection.  It never calls the provider and never writes canonical
or prior experimental artifacts.
"""

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

import hdb2_psl1_3b_common as layer  # noqa: E402
import hdb2_psl1_3_common as psl1_3  # noqa: E402
from run_hdb2_psl1 import protected_hashes  # noqa: E402


def _load(path: Path, default: Any = None) -> Any:
    return layer.read_json(path, default)


def _validate_selection(selection: Mapping[str, Any], errors: list[str]) -> None:
    expected = layer.freeze_selection()
    if dict(selection) != expected:
        errors.append("frozen_psl1_3b_selection_changed")
    rows = list(selection.get("independent_cases", []) or [])
    story_ids = [str(row.get("story_id") or "") for row in rows]
    if len(rows) != 10:
        errors.append("selection_count_not_10")
    if len(set(story_ids)) != len(story_ids):
        errors.append("selection_stories_not_distinct")
    if selection.get("overlap_with_prior_story_ids"):
        errors.append("selection_overlaps_prior_psl_story")
    if selection.get("frozen_before_live") is not True:
        errors.append("selection_not_frozen")
    if selection.get("candidate_only") is not True or selection.get("canonical_write_back") is not False:
        errors.append("selection_safety_flags_invalid")


def _validate_packets(run_dir: Path, errors: list[str]) -> dict[str, dict[str, Any]]:
    document = _load(run_dir / "reference-packets.json", {}) or {}
    result: dict[str, dict[str, Any]] = {}
    for row in document.get("records", []) or []:
        key = str(row.get("key") or "")
        packet = row.get("packet") or {}
        if not key:
            errors.append("reference_packet_key_missing")
            continue
        if key in result:
            errors.append(f"reference_packet_duplicate:{key}")
        result[key] = packet
        if packet.get("candidate_only") is not True or packet.get("canonical_write_back") is not False:
            errors.append(f"reference_packet_safety_flags_invalid:{key}")
        if psl1_3._walk_keys(packet):
            errors.append(f"reference_packet_contains_provider_id:{key}")
        if not packet.get("evidence_items"):
            errors.append(f"reference_packet_evidence_empty:{key}")
    return result


def _validate_run(run_dir: Path, errors: list[str]) -> dict[str, Any]:
    manifest = _load(run_dir / "manifest.json", {}) or {}
    selection = _load(run_dir / "selection.json", {}) or {}
    _validate_selection(selection, errors)
    if manifest.get("candidate_only") is not True or manifest.get("canonical_write_back") is not False:
        errors.append("manifest_safety_flags_invalid")
    before = manifest.get("protected_hashes_before")
    after = manifest.get("protected_hashes_after")
    if before != after:
        errors.append("protected_hashes_changed")
    if after != protected_hashes():
        errors.append("protected_hashes_do_not_match_current")

    packets = _validate_packets(run_dir, errors)
    graph = _load(run_dir / "graph.json", {}) or {}
    structures_document = _load(run_dir / "reference-structures.json", {}) or {}
    structures = {
        str(row.get("mention_id")): row
        for row in structures_document.get("records", []) or []
        if row.get("mention_id")
    }
    cases = {str(row.get("mention_id")): row for row in graph.get("cases", []) or []}
    if set(structures) != set(cases):
        errors.append("reference_structure_case_coverage_invalid")

    office_without_holder = 0
    holder_with_empty_evidence = 0
    for mention_id, structure in structures.items():
        if structure.get("candidate_only") is not True or structure.get("canonical_write_back") is not False:
            errors.append(f"structure_safety_flags_invalid:{mention_id}")
        packet = packets.get(f"reference:{mention_id}")
        if packet is None:
            errors.append(f"reference_packet_missing:{mention_id}")
        office = str(structure.get("surface_structure") or "") in layer.OFFICE_ROLE_STRUCTURES
        if not office:
            continue
        if structure.get("holder") and not structure.get("holder_assignment_evidence_ids"):
            holder_with_empty_evidence += 1
            errors.append(f"holder_with_empty_evidence:{mention_id}")
        if not structure.get("holder"):
            office_without_holder += 1
            case = cases.get(mention_id, {})
            for predicate in case.get("deterministic_predicates", []) or []:
                if predicate.get("predicate") == "OfficeCompatible" and float(predicate.get("value", 0.5)) > 0.5:
                    errors.append(f"ungrounded_office_compatible:{mention_id}")
                if predicate.get("predicate") == "OfficeCompatible" and predicate.get("evidence_ids"):
                    errors.append(f"ungrounded_office_evidence:{mention_id}")

    model_records = list((_load(run_dir / "model-results.json", {}) or {}).get("records", []) or [])
    for row in model_records:
        if row.get("call_type") != "reference_semantic_arbitration":
            continue
        classification = row.get("classification")
        if classification in {"deterministic_bypass", "offline_fixture", "offline_ambiguous_no_fixture", "not_run_preflight_failure"}:
            if classification == "offline_fixture":
                packet = packets.get(str(row.get("packet_key") or ""), {})
                checked = layer.validate_semantic_arbitration(row.get("payload") or {}, packet)
                if checked.get("valid") is not True:
                    errors.append(f"offline_reference_payload_invalid:{row.get('mention_id')}")
            continue
        packet = packets.get(str(row.get("packet_key") or ""), {})
        checked = layer.validate_semantic_arbitration(row.get("payload") or {}, packet)
        if checked.get("valid") is not True:
            errors.extend(f"reference_payload_invalid:{row.get('mention_id')}:{item}" for item in checked.get("errors", []))

    final = _load(run_dir / "decisions-final.json", {}) or {}
    if final.get("candidate_only") is not True or final.get("canonical_write_back") is not False:
        errors.append("final_safety_flags_invalid")
    structural = {"compositional_kinship", "patron_plus_office", "surname_plus_title", "non_person"}
    final_by_id = {str(row.get("mention_id")): row for row in final.get("records", []) or []}
    for mention_id, structure in structures.items():
        if structure.get("surface_structure") not in structural:
            continue
        row = final_by_id.get(mention_id, {})
        if row.get("top_candidate") is not None or row.get("final_candidate") is not None:
            errors.append(f"structural_candidate_not_suppressed:{mention_id}")

    return {
        "run_dir": str(run_dir.relative_to(ROOT)),
        "case_count": len(cases),
        "reference_packets": len(packets),
        "reference_model_records": sum(row.get("call_type") == "reference_semantic_arbitration" for row in model_records),
        "holder_metrics": layer.holder_metrics(structures),
        "office_without_holder": office_without_holder,
        "holder_with_empty_evidence_count": holder_with_empty_evidence,
    }


def validate(run_dir: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    function = layer.semantic_tool()["function"]
    parameters = function["parameters"]
    if function.get("strict") is not True:
        errors.append("semantic_tool_not_strict")
    if parameters.get("additionalProperties") is not False:
        errors.append("semantic_parameters_not_closed")
    if set(parameters.get("required", [])) != set(parameters.get("properties", {})):
        errors.append("semantic_parameters_required_invalid")
    regressions = layer.reference_regression_records()
    if regressions.get("all_pass") is not True:
        errors.append("reference_regression_failed")
    details: dict[str, Any] = {
        "candidate_only": True,
        "canonical_write_back": False,
        "selection": layer.freeze_selection(),
        "reference_regressions": regressions,
        "holder_metrics": layer.holder_metrics({}),
    }
    if run_dir is not None:
        details.update(_validate_run(run_dir, errors))
    return {"valid": not errors, "errors": sorted(set(errors)), **details}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path)
    args = parser.parse_args()
    run_dir = args.run_dir
    if run_dir and not run_dir.is_absolute():
        run_dir = ROOT / run_dir
    result = validate(run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
