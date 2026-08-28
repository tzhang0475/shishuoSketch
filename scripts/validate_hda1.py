#!/usr/bin/env python3
"""Validate HDA1 artifacts without contacting a provider."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import hda1_identity_audit as audit  # noqa: E402


def validate(run_id: str | None = None) -> dict[str, object]:
    errors: list[str] = []
    claims_doc = audit.read_json(audit.OUT / "claims.json", {}) or {}
    packets_doc = audit.read_json(audit.OUT / "audit-packets.json", {}) or {}
    if claims_doc.get("candidate_only") is not True or claims_doc.get("canonical_write_back") is not False:
        errors.append("claims_safety_flags")
    claims = list(claims_doc.get("claims", []) or [])
    packets = list(packets_doc.get("packets", []) or [])
    if claims_doc.get("claim_count") != len(claims): errors.append("claim_count")
    if len(claims) != len(packets): errors.append("packet_count")
    if len({str(x.get("claim_id")) for x in claims}) != len(claims): errors.append("duplicate_claim_id")
    for packet in packets:
        forbidden = audit.blind_packet_forbidden_fields(packet)
        if forbidden: errors.append(f"blind_packet_forbidden:{packet.get('claim_id')}:{sorted(forbidden)}")
        if not packet.get("person_id") or not packet.get("target_surface"):
            errors.append(f"packet_identity_coordinates:{packet.get('claim_id')}")
        evidence_ids = {str(x.get("evidence_id")) for x in packet.get("evidence_items", []) or []}
        if set(str(x) for x in packet.get("source_evidence_ids", []) or []) - evidence_ids:
            errors.append(f"packet_evidence_pointer:{packet.get('claim_id')}")
        for item in packet.get("evidence_items", []) or []:
            text = str(item.get("evidence_text") or "")
            span = str(item.get("exact_span") or "")
            # Missing byte-contiguous spans are an auditable evidence-quality
            # result, not a packet/provenance corruption: HDA1 must retain
            # the original source spelling and fail closed rather than repair
            # witness line breaks or glyphs.
            if item.get("exact_span_grounded") is True and span and span not in text:
                errors.append(f"packet_grounding_flag_inconsistent:{packet.get('claim_id')}")
    manifest = audit.read_json(audit.OUT / "manifest.json", {}) or {}
    if manifest.get("claims_hash") != audit.stable_hash(claims_doc): errors.append("claims_hash")
    if manifest.get("packets_hash") != audit.stable_hash(packets_doc): errors.append("packets_hash")
    results = []
    if run_id:
        results = list((audit.read_json(audit.OUT / "live" / run_id / "audit-results.json", {}) or {}).get("results", []) or [])
    elif (audit.OUT / "audit-results.json").is_file():
        pointer = audit.read_json(audit.OUT / "audit-results.json", {}) or {}
        result_path = ROOT / str(pointer.get("results_path") or "")
        results = list((audit.read_json(result_path, {}) or {}).get("results", []) or [])
    claim_ids = {str(x.get("claim_id")) for x in claims}
    if results and {str(x.get("claim_id")) for x in results} != claim_ids:
        errors.append("result_claim_coverage")
    output = {"schema": "hda1-validation-v1", "valid": not errors, "errors": sorted(set(errors)), "claim_count": len(claims), "packet_count": len(packets), "candidate_only": True, "canonical_write_back": False}
    audit.write_json(audit.OUT / "validation.json", output)
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
