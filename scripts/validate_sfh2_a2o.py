#!/usr/bin/env python3
"""Validate the compact SFH2.2-A2O pilot contract and artifacts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping

from sfh2_a2o.common import BASELINE_COMMIT, GOLD_PATH, OUT, ROOT, all_cases, build_case_packet, file_hash, input_hashes, load_inputs, provider_payload, read_json, text
from sfh2_a2o.contracts import occurrence_function_tool, validate_deepseek_strict_schema
from sfh2_a2o.provenance import project_legacy_occurrence_role


FORBIDDEN_RUNTIME_PATTERNS = (
    re.compile(r"surface\s*=="),
    re.compile(r"surface\s+in"),
    re.compile(r"endswith\s*\("),
    re.compile(r"startswith\s*\("),
)


def _rows(document: Any, key: str = "records") -> list[dict[str, Any]]:
    if isinstance(document, Mapping) and isinstance(document.get(key), list):
        return [dict(row) for row in document[key] if isinstance(row, Mapping)]
    return [dict(row) for row in document] if isinstance(document, list) else []


def validate_artifacts(root: Path = ROOT) -> dict[str, Any]:
    errors: list[str] = []
    schema_errors = validate_deepseek_strict_schema(occurrence_function_tool()["function"]["parameters"])
    if schema_errors:
        errors.extend(schema_errors)
    cases = all_cases()
    selection = read_json(OUT / "selection.json", {}) or {}
    selected_ids = [text(row.get("case_id")) for row in selection.get("cases", []) or [] if isinstance(row, Mapping)]
    case_ids = [text(row.get("case_id")) for row in cases]
    if selected_ids != case_ids:
        errors.append("selection_case_order_or_membership_mismatch")
    if len(case_ids) != 26 or len(set(case_ids)) != 26:
        errors.append("case_count_or_uniqueness_invalid")
    if selection.get("selection_hash") != __import__("sfh2_a2o.common", fromlist=["stable_hash"]).stable_hash(selection.get("cases", [])):
        errors.append("selection_hash_invalid")
    if selection.get("reviewed_role_case_count") != 6 or selection.get("challenge_case_count") != 20:
        errors.append("cohort_counts_invalid")
    if set(selection.get("challenge_stories", [])) != {"09-pinzao-063", "25-paidiao-015", "21-qiaoyi-011", "10-guizhen-011", "02-yanyu-060"}:
        errors.append("challenge_story_set_invalid")

    gold = read_json(GOLD_PATH, {}) or {}
    gold_rows = _rows(gold)
    gold_ids = {text(row.get("case_id")) for row in gold_rows}
    if gold_ids != set(case_ids):
        errors.append("gold_case_set_mismatch")
    if any(text(row.get("review_status")) not in {"reviewed", "review_required"} for row in gold_rows):
        errors.append("invalid_gold_review_status")
    if any(text(row.get("review_status")) == "reviewed" and not text(row.get("expected_narrative_function")) for row in gold_rows):
        errors.append("reviewed_gold_function_missing")

    packets = read_json(OUT / "case-packets.json", {}) or {}
    packet_rows = _rows(packets, "packets")
    if {text(row.get("case_id")) for row in packet_rows} != set(case_ids):
        errors.append("packet_case_set_mismatch")
    encoded_packets = json.dumps(packets, ensure_ascii=False, sort_keys=True)
    for forbidden in ("expected_narrative_function", "expected_legacy_occurrence_role", "review_status"):
        if forbidden in encoded_packets:
            errors.append("gold_leak_in_case_packets:" + forbidden)

    inputs = load_inputs()
    packets_by_id = {text(row.get("case_id")): row.get("packet", {}) for row in packet_rows}
    for case in cases:
        case_id = text(case.get("case_id"))
        packet = packets_by_id.get(case_id)
        if not isinstance(packet, Mapping):
            errors.append("packet_missing:" + case_id)
            continue
        provider = provider_payload(packet)
        encoded = json.dumps(provider, ensure_ascii=False, sort_keys=True)
        if any(token in encoded for token in ("expected_", "review_status", "occurrence_role", "gold")):
            # ``gold_not_supplied`` is an explicit boundary marker, not leaked
            # evaluation content.
            leaked = [token for token in ("expected_", "review_status", "occurrence_role") if token in encoded]
            errors.extend("provider_semantic_leak:" + token for token in leaked)

    results = read_json(OUT / "occurrence-results.json", {}) or {}
    result_rows = _rows(results)
    if {text(row.get("case_id")) for row in result_rows} != set(case_ids):
        errors.append("result_case_set_mismatch")
    for row in result_rows:
        occurrence = row.get("occurrence_result")
        if isinstance(occurrence, Mapping) and set(occurrence) != {"case_id", "narrative_function", "confidence", "supporting_evidence_ids", "reason_summary"}:
            errors.append("occurrence_output_shape_invalid:" + text(row.get("case_id")))
        if row.get("candidate_only") is not True or row.get("canonical_write_back") is not False:
            errors.append("candidate_only_safety_invalid:" + text(row.get("case_id")))
        if row.get("identity_preserved") is not True:
            errors.append("identity_not_preserved:" + text(row.get("case_id")))
        if row.get("valid") is True and row.get("provenance_layer") not in {"main_text", "liu_annotation"}:
            errors.append("invalid_provenance_layer:" + text(row.get("case_id")))

    for path in (root / "scripts/sfh2_a2o").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_RUNTIME_PATTERNS:
            if pattern.search(source):
                errors.append(f"forbidden_surface_rule:{path.name}:{pattern.pattern}")
    protected = input_hashes()
    protected_unchanged = all((root / path).is_file() and file_hash(root / path) == digest for path, digest in protected.items())
    if not protected_unchanged:
        errors.append("protected_input_hash_changed")
    transport = read_json(OUT / "transport.json", {}) or {}
    if isinstance(transport, Mapping) and transport.get("provider_attempts", 0) > 40:
        errors.append("provider_budget_exceeded")
    if (OUT / "raw-api").exists():
        errors.append("raw_provider_payload_committed_under_a2o_output")
    return {
        "schema": "sfh2-a2o-validator-v1",
        "baseline_commit": BASELINE_COMMIT,
        "case_count": len(case_ids),
        "gold_count": len(gold_rows),
        "strict_schema_errors": schema_errors,
        "protected_inputs_unchanged": protected_unchanged,
        "errors": sorted(set(errors)),
        "valid": not errors,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    report = validate_artifacts(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
