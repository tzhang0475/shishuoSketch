#!/usr/bin/env python3
"""Validate the additive HDB2-PSL1.3A semantic-prejudgment run.

This validator is offline.  It checks the strict structure boundary, saved
packet provenance, structural cleanup, and protected-input hashes; it never
calls DeepSeek or writes canonical data.
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

import hdb2_psl1_3a_common as layer  # noqa: E402
import hdb2_psl1_3_common as psl1_3  # noqa: E402
import hdb2_psl1_common as psl1  # noqa: E402
from run_hdb2_psl1 import protected_hashes  # noqa: E402


# SFH2R/SFH2R.1 intentionally rebuild the candidate-only HDB2-F profile
# projections.  PSL1.3A predates that explicit derived-input transition, so
# its validator must keep the semantic/frozen inputs strict while excluding
# only the two authorized profile projections from the old immutable hash
# comparison.  The chained transition itself is validated by sfh2r1.
_REBUILT_CANDIDATE_PROFILES = {
    "data/derived/hdb2-f-person-knowledge.json",
    "data/derived/hdb2-f-candidate-person-knowledge.json",
}


def _frozen_a_hashes(value: Mapping[str, Any] | None) -> dict[str, str]:
    return {
        str(path): str(digest)
        for path, digest in (value or {}).items()
        if str(path) not in _REBUILT_CANDIDATE_PROFILES
    }


def _load(path: Path, default: Any = None) -> Any:
    return layer.read_json(path, default)


def _validate_selection(selection: Mapping[str, Any], errors: list[str]) -> None:
    expected = psl1_3.freeze_selection()
    if dict(selection) != expected:
        errors.append("frozen_psl1_3_selection_changed")
    if selection.get("frozen_before_live") is not True:
        errors.append("selection_not_frozen")
    if selection.get("candidate_only") is not True or selection.get("canonical_write_back") is not False:
        errors.append("selection_safety_flags_invalid")


def _validate_reference_packets(run_dir: Path, errors: list[str]) -> dict[str, dict[str, Any]]:
    document = _load(run_dir / "reference-packets.json", {}) or {}
    packets: dict[str, dict[str, Any]] = {}
    for row in document.get("records", []) or []:
        key = str(row.get("key") or "")
        packet = row.get("packet") or {}
        if not key:
            errors.append("reference_packet_key_missing")
            continue
        if key in packets:
            errors.append(f"reference_packet_duplicate:{key}")
        packets[key] = packet
        if packet.get("candidate_only") is not True or packet.get("canonical_write_back") is not False:
            errors.append(f"reference_packet_safety_flags_invalid:{key}")
        forbidden = psl1_3._walk_keys(packet)
        if forbidden:
            errors.append(f"reference_packet_provider_id:{key}:{','.join(sorted(forbidden))}")
        if not packet.get("evidence_items"):
            errors.append(f"reference_packet_evidence_empty:{key}")
    return packets


def _validate_run(run_dir: Path, errors: list[str]) -> dict[str, Any]:
    manifest = _load(run_dir / "manifest.json", {}) or {}
    selection = _load(run_dir / "selection.json", {}) or {}
    _validate_selection(selection, errors)
    if manifest.get("candidate_only") is not True or manifest.get("canonical_write_back") is not False:
        errors.append("manifest_safety_flags_invalid")
    before_hashes = _frozen_a_hashes(manifest.get("protected_hashes_before"))
    after_hashes = _frozen_a_hashes(manifest.get("protected_hashes_after"))
    if before_hashes != after_hashes:
        errors.append("protected_hashes_changed")
    if after_hashes != _frozen_a_hashes(protected_hashes()):
        errors.append("protected_hashes_do_not_match_current")
    packets = _validate_reference_packets(run_dir, errors)
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
    for mention_id, case in cases.items():
        structure = structures.get(mention_id, {})
        if structure.get("candidate_only") is False or structure.get("canonical_write_back") is True:
            errors.append(f"structure_safety_flags_invalid:{mention_id}")
        packet = packets.get(f"reference:{mention_id}")
        if packet is None:
            errors.append(f"reference_packet_missing:{mention_id}")
        elif not isinstance(packet.get("reference_hypotheses"), list) or not packet.get("reference_hypotheses"):
            errors.append(f"reference_hypotheses_missing:{mention_id}")
    model_records = list((_load(run_dir / "model-results.json", {}) or {}).get("records", []) or [])
    for row in model_records:
        if row.get("call_type") != "reference_semantic_arbitration":
            continue
        if row.get("classification") in {"deterministic_bypass", "offline_fixture", "offline_ambiguous_no_fixture", "not_run_preflight_failure"}:
            if row.get("classification") == "offline_fixture":
                packet = packets.get(str(row.get("packet_key") or ""))
                validation = layer.validate_semantic_arbitration(row.get("payload") or {}, packet or {})
                if validation.get("valid") is not True:
                    errors.append(f"offline_reference_payload_invalid:{row.get('mention_id')}")
            continue
        packet = packets.get(str(row.get("packet_key") or ""))
        if packet is None:
            errors.append(f"reference_model_packet_missing:{row.get('mention_id')}")
            continue
        validation = layer.validate_semantic_arbitration(row.get("payload") or {}, packet)
        if validation.get("valid") is not True:
            errors.extend(f"reference_payload_invalid:{row.get('mention_id')}:{error}" for error in validation.get("errors", []))
    final = _load(run_dir / "decisions-final.json", {}) or {}
    if final.get("candidate_only") is not True or final.get("canonical_write_back") is not False:
        errors.append("final_safety_flags_invalid")
    structural_mentions = {
        mention_id for mention_id, structure in structures.items()
        if structure.get("surface_structure") in {"compositional_kinship", "patron_plus_office", "surname_plus_title", "non_person"}
    }
    final_by_id = {str(row.get("mention_id")): row for row in final.get("records", []) or []}
    for mention_id in structural_mentions:
        row = final_by_id.get(mention_id, {})
        if row.get("top_candidate") is not None or row.get("final_candidate") is not None:
            errors.append(f"structural_final_candidate_not_suppressed:{mention_id}")
    wuzi = next(
        (row for row in structures.values() if row.get("story_id") == "05-fangzheng-011" and row.get("target_surface") == "武子"),
        None,
    )
    if wuzi and wuzi.get("surface_structure") != "lexicalized_personal_form":
        errors.append("武子_not_lexicalized_personal_form")
    household = next(
        (row for row in structures.values() if row.get("story_id") == "05-fangzheng-028" and row.get("target_surface") == "家兄"),
        None,
    )
    if household and household.get("surface_structure") == "compositional_kinship":
        # The frozen 1.3A run recorded the source-local abbreviated anchor
        # ``敦``.  The current semantic regression helper expands that same
        # grounded local participant to 王敦.  Accept either wire form, but
        # never accept an ungrounded arbitrary anchor: the saved graph must
        # contain the corresponding existing Person candidate.
        anchor = household.get("anchor_person")
        graph_case = cases.get(str(household.get("mention_id")), {})
        grounded_names = {
            str(candidate.get("display_name") or "")
            for candidate in graph_case.get("candidates", []) or []
            if isinstance(candidate, Mapping)
        }
        grounded_abbreviations = {
            str(candidate.get("display_name") or "")
            for candidate in graph_case.get("candidates", []) or []
            if isinstance(candidate, Mapping)
            and anchor
            and anchor in str(candidate.get("profile", {}).get("aliases", []) or [])
        }
        if anchor not in grounded_names and not (anchor and grounded_abbreviations):
            errors.append("家兄_anchor_not_grounded")
    return {
        "run_dir": str(run_dir.relative_to(ROOT)),
        "reference_packets": len(packets),
        "reference_model_records": sum(row.get("call_type") == "reference_semantic_arbitration" for row in model_records),
        "final_records": len(final.get("records", []) or []),
    }


def validate(run_dir: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    tool = layer.semantic_tool()["function"]
    params = tool["parameters"]
    if tool.get("strict") is not True or params.get("additionalProperties") is not False:
        errors.append("semantic_tool_not_strict")
    if set(params.get("required", [])) != set(params.get("properties", {})):
        errors.append("semantic_tool_required_contract_invalid")
    # Prior PSL1.3 safety regressions are read-only and remain a prerequisite
    # for this adapter; this call does not change their artifacts.
    for name, record in (
        ("required", psl1_3.required_regression_records()),
        ("false", psl1_3.false_resolution_regression()),
        ("interface", psl1_3.interface_regression_records()),
    ):
        if record.get("all_pass") is not True:
            errors.append(f"prior_{name}_regression_failed")
    reference_regressions = layer.reference_regression_records()
    if reference_regressions.get("all_pass") is not True:
        errors.append("reference_structure_regression_failed")
    details: dict[str, Any] = {
        "candidate_only": True,
        "canonical_write_back": False,
        "reference_tool": tool,
        "reference_regressions": reference_regressions,
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
