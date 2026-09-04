#!/usr/bin/env python3
"""Validate the A2OV reviewer pilot without making provider calls."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

from sfh2_a2ov.common import (
    ACTIVE_GOLD_SHA256,
    A2OR_ROOT,
    A2OSP_ROOT,
    BASELINE_COMMIT,
    CASE_COUNT,
    CURRENT_SC1_SHA256,
    FROZEN_SC1_SHA256,
    GOLD_PATH,
    IDENTITY_MANIFEST_SHA256,
    OUT,
    ROOT,
    by_case,
    exact_occurrence_key,
    file_hash,
    load_frozen_bundle,
    read_json,
    stable_hash,
    text,
)
from sfh2_a2ov.contracts import reviewer_tool, validate_deepseek_strict_schema, validate_reviewer_payload


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _changed_paths_since_baseline() -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--name-only", BASELINE_COMMIT, "--"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def validate(output: Path = OUT) -> dict[str, Any]:
    bundle = load_frozen_bundle()
    architecture = read_json(output / "architecture.json", {}) or {}
    selection = read_json(output / "selection-verification.json", {}) or {}
    packets_doc = read_json(output / "reviewer-packets.json", {}) or {}
    results_doc = read_json(output / "reviewer-results.json", {}) or {}
    finals_doc = read_json(output / "reviewer-final-results.json", {}) or {}
    evaluation = read_json(output / "evaluation.json", {}) or {}
    accounting = read_json(output / "provider-accounting.json", {}) or {}
    preflight = read_json(output / "provider-preflight.json", {}) or {}
    safety = read_json(output / "storage-safety-audit.json", {}) or {}
    _assert(architecture.get("baseline_commit") == BASELINE_COMMIT, "baseline mismatch")
    _assert(architecture.get("case_count") == CASE_COUNT, "architecture case count")
    _assert(architecture.get("historian_a_new_provider_calls") == 0, "A calls were not zero")
    _assert(architecture.get("reviewer_is_primary_aware") is True, "reviewer primary awareness missing")
    _assert(architecture.get("reviewer_is_not_independent_blind_historian") is True, "reviewer role mislabeled")
    tool = reviewer_tool()
    _assert(not validate_deepseek_strict_schema(tool["function"]["parameters"]), "strict schema invalid")
    properties = tool["function"]["parameters"]["properties"]
    _assert("identity" not in properties and "provenance_layer" not in properties and "occurrence_role" not in properties, "forbidden reviewer field")
    _assert(len(bundle["case_ids"]) == CASE_COUNT, "frozen case count")
    _assert(selection.get("a2osp_exact_witness_matches") is True, "exact occurrence witness mismatch")
    _assert(selection.get("gold_used_for_selection") is False, "Gold was used for selection")
    _assert(selection.get("surface_only_resolution") is False, "surface-only selection")
    _assert(set(selection.get("case_ids", [])) == set(bundle["case_ids"]), "selection IDs changed")
    packet_rows = packets_doc.get("records", [])
    result_rows = results_doc.get("records", [])
    final_rows = finals_doc.get("records", [])
    _assert(len(packet_rows) == CASE_COUNT and len(result_rows) == CASE_COUNT and len(final_rows) == CASE_COUNT, "A2OV records incomplete")
    # The packet document records the assertion that residual labels were not
    # sent.  Inspect only the actual provider payloads, not that metadata.
    packet_json = json.dumps(
        [row.get("provider_payload") for row in packet_rows if isinstance(row, Mapping)],
        ensure_ascii=False,
        sort_keys=True,
    )
    for forbidden in ("expected_narrative_function", "expected_legacy_occurrence_role", "review_status", "residual_error", "qualified_genuine_semantic_error"):
        _assert(forbidden not in packet_json, f"Gold/residual leakage: {forbidden}")
    result_map = by_case(results_doc)
    final_map = by_case(finals_doc)
    _assert(set(result_map) == set(bundle["case_ids"]), "review result IDs")
    _assert(set(final_map) == set(bundle["case_ids"]), "final result IDs")
    for case_id in bundle["case_ids"]:
        packet = bundle["packets"][case_id]
        row = result_map[case_id]
        _assert(row.get("exact_occurrence_key") == exact_occurrence_key(packet), f"exact key changed: {case_id}")
        _assert(isinstance(row.get("primary"), Mapping), f"primary missing: {case_id}")
        _assert(row.get("identity_preserved") is True and row.get("provenance_preserved") is True, f"frozen input changed: {case_id}")
        _assert(row.get("reviewer_valid") is True, f"invalid reviewer row: {case_id}")
        validation = validate_reviewer_payload(packet, row.get("reviewer_result"), text(row.get("primary_function")))
        _assert(validation.get("valid") is True, f"local reviewer validation: {case_id}")
        final = final_map[case_id]
        _assert(final.get("exact_occurrence_key") == row.get("exact_occurrence_key"), f"final key changed: {case_id}")
        _assert(final.get("identity_preserved") is True and final.get("provenance_preserved") is True, f"final frozen input changed: {case_id}")
        decision = final.get("reviewer_decision")
        primary = final.get("primary_semantic")
        final_semantic = final.get("final_semantic")
        _assert(isinstance(primary, Mapping) and isinstance(final_semantic, Mapping), f"final semantic missing: {case_id}")
        if decision in {"confirm_primary", "abstain"}:
            _assert(final_semantic == primary, f"copy drift: {case_id}")
        elif decision == "revise_function":
            changed = [key for key in set(primary) | set(final_semantic) if primary.get(key) != final_semantic.get(key)]
            _assert(changed == ["narrative_function"], f"undeclared revision mutation: {case_id}")
    _assert(preflight.get("valid") is True, "provider preflight failed")
    _assert(accounting.get("provider_calls") == CASE_COUNT + 1, "provider logical call count")
    _assert(accounting.get("schema_probe_calls") == 1 and accounting.get("reviewer_calls") == CASE_COUNT, "provider stage counts")
    _assert(accounting.get("parsed_calls") == CASE_COUNT + 1, "parsed provider count")
    _assert(accounting.get("provider_failures", 0) == 0 and accounting.get("invalid_payloads", 0) == 0 and accounting.get("truncations", 0) == 0, "provider failures")
    _assert(evaluation.get("metrics", {}).get("valid_reviewer_records") == CASE_COUNT, "evaluation reviewer coverage")
    _assert(evaluation.get("metrics", {}).get("valid_final_records") == CASE_COUNT, "evaluation final coverage")
    _assert(safety.get("canonical_writes") == 0 and safety.get("identity_replacements") == 0 and safety.get("provenance_replacements") == 0, "unsafe semantic mutation")
    _assert(safety.get("production_person_creations") == 0 and safety.get("name_specific_python_semantic_rules") == 0 and safety.get("surface_specific_role_rules") == 0, "unsafe runtime behavior")
    _assert(file_hash(GOLD_PATH) == ACTIVE_GOLD_SHA256, "active Gold changed")
    _assert(file_hash(ROOT / "data/derived/sc1-site.json") == FROZEN_SC1_SHA256, "frozen SC1 changed")
    _assert(file_hash(ROOT / "data/derived/sc1-current-site.json") == CURRENT_SC1_SHA256, "current SC1 changed")
    _assert(file_hash(ROOT / "data/frozen/sfh2/identity-v1/manifest.json") == IDENTITY_MANIFEST_SHA256, "identity manifest changed")
    for path in (ROOT / "scripts/sfh2_a2ov").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        _assert(not re.search(r"surface\s*(?:==|in)", source), f"surface-specific rule in {path.name}")
    protected_prefixes = (
        "data/generated/sfh2-a2o/", "data/generated/sfh2-a2ot/", "data/generated/sfh2-a2or/", "data/generated/sfh2-a2os/", "data/generated/sfh2-a2osp/",
        "data/derived/sc1-site.json", "data/derived/sc1-current-site.json", "data/frozen/sfh2/", "data/people.json", "data/aliases.json",
    )
    changed = _changed_paths_since_baseline()
    _assert(not [path for path in changed if path.startswith(protected_prefixes)], "protected artifact changed: " + repr([path for path in changed if path.startswith(protected_prefixes)]))
    return {
        "schema": "sfh2-a2ov-validator-v1",
        "valid": True,
        "case_count": CASE_COUNT,
        "provider_calls": accounting.get("provider_calls"),
        "protected_hashes_valid": True,
        "copy_drift": 0,
        "undeclared_mutations": 0,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    try:
        print(json.dumps(validate(args.output), ensure_ascii=False, indent=2, sort_keys=True))
    except (AssertionError, OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"A2OV validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
