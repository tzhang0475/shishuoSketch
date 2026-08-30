#!/usr/bin/env python3
"""Validate HDA2 selection, provenance, and candidate-only boundaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import hda2_identity_remediation as hda2  # noqa: E402
import sfh2r_contract  # noqa: E402


def validate(run_id: str | None = None) -> dict[str, object]:
    errors: list[str] = []
    selection = hda2.read_json(hda2.SELECTION_PATH, {}) or {}
    if not selection:
        errors.append("missing_selection")
    else:
        expected_hash = hda2.stable_hash({key: value for key, value in selection.items() if key != "selection_hash"})
        if selection.get("selection_hash") != expected_hash:
            errors.append("selection_hash_invalid")
        if selection.get("frozen_before_live") is not True:
            errors.append("selection_not_frozen")
        if selection.get("candidate_only") is not True or selection.get("canonical_write_back") is not False:
            errors.append("selection_safety_flags")
        if len(selection.get("records", []) or []) != selection.get("selected_claim_count"):
            errors.append("selection_count_mismatch")
        if len({row.get("claim_id") for row in selection.get("records", []) or []}) != len(selection.get("records", []) or []):
            errors.append("selection_duplicate_claim")
        if (
            selection.get("hda1_input_hashes") != hda2.hda1_inputs()
            and not sfh2r_contract.frozen_hashes_are_current_or_authorized(
                selection.get("hda1_input_hashes"), hda2.hda1_inputs()
            )
        ):
            errors.append("hda1_input_snapshot_drift")
    packets = hda2.read_json(hda2.OUT / "remediation-packets.json", {}) or {}
    if packets.get("packet_count") != len(packets.get("packets", []) or []):
        errors.append("packet_count_mismatch")
    if packets.get("candidate_only") is not True or packets.get("canonical_write_back") is not False:
        errors.append("packet_safety_flags")
    for packet in packets.get("packets", []) or []:
        evidence_ids = [item.get("evidence_id") for item in packet.get("evidence_items", []) or []]
        if len(evidence_ids) != len(set(evidence_ids)):
            errors.append(f"duplicate_evidence_ids:{packet.get('claim_id')}")
        if set(evidence_ids) != set(packet.get("source_evidence_ids", []) or []):
            errors.append(f"packet_evidence_index:{packet.get('claim_id')}")
        for item in packet.get("evidence_items", []) or []:
            if item.get("exact_span") and item.get("exact_span") not in item.get("evidence_text", "") and item.get("exact_span_grounded") is True:
                errors.append(f"grounding_flag_inconsistent:{packet.get('claim_id')}")
    run_base = hda2.OUT / "live" / run_id if run_id else None
    overlay = hda2.read_json(hda2.OUT / "repair-overlay.json", []) or []
    for row in overlay:
        if row.get("alternative_surface") == "null":
            errors.append(f"literal_null_alternative:{row.get('claim_id')}")
        if row.get("candidate_only") is not True or row.get("canonical_write_back") is not False:
            errors.append(f"overlay_safety_flags:{row.get('claim_id')}")
    if run_base and run_base.is_dir():
        manifest = hda2.read_json(run_base / "manifest.json", {}) or {}
        if manifest.get("selection_hash") != selection.get("selection_hash"):
            errors.append("run_selection_hash")
        if manifest.get("candidate_only") is not True or manifest.get("canonical_write_back") is not False:
            errors.append("run_safety_flags")
        result_doc = hda2.read_json(run_base / "remediation-results.json", {}) or {}
        for row in result_doc.get("results", []) or []:
            if row.get("execution_status") == "validated":
                payload = row.get("payload") or {}
                packet = next((p for p in packets.get("packets", []) or [] if p.get("claim_id") == row.get("claim_id")), {})
                check = hda2.validate_remediation_payload(payload, packet)
                if not check.get("valid"):
                    errors.append(f"validated_payload_invalid:{row.get('claim_id')}")
    output = {"schema": "hda2-validation-v1", "valid": not errors, "errors": sorted(set(errors)), "selection_count": len(selection.get("records", []) or []), "packet_count": packets.get("packet_count", 0), "candidate_only": True, "canonical_write_back": False}
    hda2.write_json(hda2.OUT / "validation.json", output)
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
