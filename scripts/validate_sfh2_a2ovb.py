#!/usr/bin/env python3
"""Validate the A2OVB pilot without making provider calls."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

from sfh2_a2ovb.common import (
    A2OR_ROOT,
    A2OSP_ROOT,
    ACTIVE_GOLD_SHA256,
    BOUNDARY_FUNCTIONS,
    CASE_COUNT,
    CURRENT_SC1_SHA256,
    FROZEN_SC1_SHA256,
    GOLD_PATH,
    IDENTITY_MANIFEST_SHA256,
    OUT,
    ROOT,
    by_case,
    boundary_case_ids,
    exact_occurrence_key,
    file_hash,
    load_frozen_bundle,
    provider_payload,
    read_json,
    stable_hash,
)
from sfh2_a2ovb.contracts import boundary_tool, validate_boundary_payload, validate_deepseek_strict_schema


BASELINE_COMMIT = "ca3ac0d39f7f85282f555a4b4494f6116c9afbe1"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _changed_since_baseline() -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--name-only", BASELINE_COMMIT, "--"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _walk(value: Any, path: str = "$") -> Iterable[tuple[str, Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def validate(output: Path = OUT) -> dict[str, Any]:
    bundle = load_frozen_bundle()
    expected_boundary = boundary_case_ids(bundle)
    architecture = read_json(output / "architecture.json", {}) or {}
    selection = read_json(output / "selection.json", {}) or {}
    packets_doc = read_json(output / "boundary-packets.json", {}) or {}
    results_doc = read_json(output / "boundary-results.json", {}) or {}
    finals_doc = read_json(output / "final-results.json", {}) or {}
    boundary_eval = read_json(output / "boundary-evaluation.json", {}) or {}
    full_eval = read_json(output / "full-evaluation.json", {}) or {}
    accounting = read_json(output / "provider-accounting.json", {}) or {}
    preflight = read_json(output / "provider-preflight.json", {}) or {}
    safety = read_json(output / "storage-safety-audit.json", {}) or {}

    _assert(architecture.get("baseline_commit") == BASELINE_COMMIT, "baseline mismatch")
    _assert(architecture.get("case_count") == CASE_COUNT, "architecture case count")
    _assert(architecture.get("primary_new_provider_calls") == 0, "primary calls were not zero")
    _assert(architecture.get("validator_is_primary_blind") is True, "primary blindness missing")
    _assert(architecture.get("validator_is_gold_blind") is True, "Gold blindness missing")
    _assert(architecture.get("validator_is_residual_error_blind") is True, "residual blindness missing")
    _assert(architecture.get("provider_packet_excludes_primary") is True, "primary exclusion missing")
    _assert(not validate_deepseek_strict_schema(boundary_tool()["function"]["parameters"]), "strict schema invalid")
    properties = boundary_tool()["function"]["parameters"]["properties"]
    _assert(set(properties) == {"case_id", "boundary_judgment", "confidence", "supporting_evidence_ids", "reason_summary"}, "unexpected contract fields")

    _assert(selection.get("total_case_count") == CASE_COUNT, "total selection count")
    _assert(selection.get("boundary_case_ids") == expected_boundary, "boundary routing changed")
    _assert(selection.get("gold_used_for_selection") is False, "Gold selection leak")
    _assert(selection.get("a2ov_used_for_selection") is False, "reviewer selection leak")
    _assert(selection.get("residual_labels_used_for_selection") is False, "residual selection leak")
    witness = by_case(read_json(A2OSP_ROOT / "a2or-post-promotion-evaluation.json", {}))
    _assert(len(witness) == CASE_COUNT, "A2OSP witness count")
    _assert(selection.get("exact_occurrence_keys") == {case_id: witness[case_id].get("exact_occurrence_key") for case_id in bundle["case_ids"]}, "selection witness mismatch")

    packet_rows = packets_doc.get("records", [])
    result_rows = results_doc.get("records", [])
    final_rows = finals_doc.get("records", [])
    _assert(len(packet_rows) == len(expected_boundary), "boundary packet count")
    _assert(len(result_rows) == len(expected_boundary), "boundary result count")
    _assert(len(final_rows) == CASE_COUNT, "final count")
    packet_map = by_case(packets_doc)
    result_map = by_case(results_doc)
    final_map = by_case(finals_doc)
    _assert(set(packet_map) == set(expected_boundary), "packet IDs")
    _assert(set(result_map) == set(expected_boundary), "result IDs")
    _assert(set(final_map) == set(bundle["case_ids"]), "final IDs")

    forbidden_packet_tokens = (
        "primary_function", "primary_confidence", "primary_reason_summary", "occurrence_role",
        "legacy_occurrence_role", "expected_narrative_function", "expected_legacy", "residual_error",
        "qualified_genuine_semantic_error", "reviewer_decision", "gold_alignment",
    )
    for case_id in expected_boundary:
        row = packet_map[case_id]
        _assert(row.get("exact_occurrence_key") == exact_occurrence_key(bundle["packets"][case_id]), "packet key changed:" + case_id)
        payload = row.get("provider_payload")
        _assert(isinstance(payload, Mapping), "provider payload missing:" + case_id)
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        for forbidden in forbidden_packet_tokens:
            _assert(forbidden not in encoded, f"blind packet leak {forbidden}:{case_id}")
        _assert(payload.get("case_id") == case_id, "payload case ID")
        _assert(payload.get("target", {}).get("source_start") == row["exact_occurrence_key"]["source_start"], "target start")
        _assert(payload.get("target", {}).get("source_end") == row["exact_occurrence_key"]["source_end"], "target end")
        _assert(payload.get("provenance_layer"), "provenance missing")

    for case_id in expected_boundary:
        row = result_map[case_id]
        _assert(row.get("exact_occurrence_key") == exact_occurrence_key(bundle["packets"][case_id]), "result key changed:" + case_id)
        _assert(row.get("validator_valid") is True, "invalid validator result:" + case_id)
        packet = packet_map[case_id]["provider_payload"]
        checked = validate_boundary_payload(packet, row.get("validator_result"))
        _assert(checked.get("valid") is True, "local result validation:" + case_id)
        _assert(row.get("primary_function_for_routing_only") == bundle["primary_rows"][case_id]["occurrence_result"]["narrative_function"], "routing witness")

    gold_leak_tokens = ("expected_narrative_function", "expected_legacy_occurrence_role", "review_status", "gold_function")
    packet_json = json.dumps([row.get("provider_payload") for row in packet_rows], ensure_ascii=False, sort_keys=True)
    for token in gold_leak_tokens:
        _assert(token not in packet_json, "Gold packet leak:" + token)
    system_prompt = str(architecture.get("prompt", {})) + json.dumps(read_json(output / "architecture.json", {}), ensure_ascii=False)
    for forbidden in ("康伯", "文度", "庾道季", "吾愧", "09-pinzao-063", "expected_narrative_function"):
        _assert(forbidden not in system_prompt, "known evaluation detail leaked:" + forbidden)

    for case_id in bundle["case_ids"]:
        final = final_map[case_id]
        primary = final.get("primary_semantic")
        effective = final.get("final_semantic")
        _assert(isinstance(primary, Mapping) and isinstance(effective, Mapping), "semantic record missing:" + case_id)
        _assert(final.get("exact_occurrence_key") == exact_occurrence_key(bundle["packets"][case_id]), "final key changed:" + case_id)
        _assert(final.get("identity_preserved") is True and final.get("provenance_preserved") is True, "frozen data changed:" + case_id)
        if case_id not in expected_boundary or final.get("boundary_judgment") == "uncertain":
            _assert(effective == primary, "copy drift:" + case_id)
        else:
            changed = [key for key in set(primary) | set(effective) if primary.get(key) != effective.get(key)]
            _assert(changed in ([], ["narrative_function"]), "undeclared semantic mutation:" + case_id)

    _assert(preflight.get("valid") is True, "provider preflight invalid")
    if accounting.get("live") is True:
        _assert(accounting.get("provider_calls") == len(expected_boundary) + 1, "provider logical calls")
        _assert(accounting.get("schema_probe_calls") == 1, "schema probe count")
        _assert(accounting.get("boundary_validator_calls") == len(expected_boundary), "boundary call count")
        _assert(accounting.get("non_boundary_calls") == 0, "non-boundary provider calls")
        _assert(accounting.get("provider_failures", 0) == 0 and accounting.get("invalid_payloads", 0) == 0 and accounting.get("truncations", 0) == 0, "provider failures")
        _assert(accounting.get("parsed_calls") == accounting.get("provider_calls"), "parsed calls")
    _assert(full_eval.get("metrics", {}).get("valid_boundary_records") == len(expected_boundary), "boundary coverage")
    _assert(boundary_eval.get("valid_records") == len(expected_boundary), "boundary evaluation coverage")
    _assert(safety.get("canonical_writes") == 0 and safety.get("identity_replacements") == 0 and safety.get("provenance_replacements") == 0, "unsafe semantic mutation")
    _assert(safety.get("production_person_creations") == 0 and safety.get("name_specific_python_semantic_rules") == 0 and safety.get("surface_specific_role_rules") == 0, "unsafe runtime behavior")
    _assert(file_hash(GOLD_PATH) == ACTIVE_GOLD_SHA256, "active Gold changed")
    _assert(file_hash(ROOT / "data/derived/sc1-site.json") == FROZEN_SC1_SHA256, "frozen SC1 changed")
    _assert(file_hash(ROOT / "data/derived/sc1-current-site.json") == CURRENT_SC1_SHA256, "current SC1 changed")
    identity_manifest_path = ROOT / "data/frozen/sfh2/identity-v1/manifest.json"
    _assert(file_hash(identity_manifest_path) == IDENTITY_MANIFEST_SHA256, "identity changed")
    for path in (ROOT / "scripts/sfh2_a2ovb").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        _assert(not re.search(r"surface\s*(?:==|in)", source), "surface-specific semantic rule:" + path.name)
    protected_prefixes = (
        "data/generated/sfh2-a2o/", "data/generated/sfh2-a2ot/", "data/generated/sfh2-a2or/", "data/generated/sfh2-a2os/", "data/generated/sfh2-a2osp/", "data/generated/sfh2-a2ov/",
        "data/annotation/sfh2-a2o-evaluation-gold.json", "data/frozen/sfh2/", "data/derived/sc1-site.json", "data/derived/sc1-current-site.json", "data/people.json", "data/aliases.json",
    )
    changed = _changed_since_baseline()
    _assert(not [path for path in changed if path.startswith(protected_prefixes)], "protected path changed:" + repr([path for path in changed if path.startswith(protected_prefixes)]))
    return {"schema": "sfh2-a2ovb-validator-v1", "valid": True, "boundary_cohort_count": len(expected_boundary), "provider_calls": accounting.get("provider_calls", 0), "copy_drift": 0, "undeclared_mutations": 0, "protected_hashes_valid": True, "candidate_only": True, "canonical_write_back": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    try:
        print(json.dumps(validate(args.output), ensure_ascii=False, indent=2, sort_keys=True))
    except (AssertionError, OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"A2OVB validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
