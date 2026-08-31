#!/usr/bin/env python3
"""Validate the isolated SFH2.2-A0R review-contract closeout."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from sfh2_a0r.common import (
    A0_OUT,
    MAX_PROVIDER_ATTEMPTS,
    MODEL,
    OUT,
    PROMPT_VERSIONS,
    ROOT,
    architecture_freeze,
    input_hashes,
    read_json,
    selection,
    stable_hash,
    text,
)
from sfh2_a0r.contracts import semantic_diff_paths
from sfh2_a0r.selection import build_selection

GOLD_KEYS = {
    "expected_identity", "expected_canonical_hint", "expected_role", "expected_semantic_kind",
    "expected_referent_surface", "expected_attribute_type", "expected_attribute_value",
    "expected_bearer", "must_not_resolve_to", "allow_abstention", "case_key",
}
FORBIDDEN_RUNTIME_PATTERNS = (
    re.compile(r"surface\s*=="),
    re.compile(r"surface\s+in\s+"),
    re.compile(r"canonical_hint\s*=\s*['\"](?:王|卿|宣王|太丘長)"),
)
SEMANTIC_RECORD_KEYS = {"semantic_record", "revised_semantic_record"}


def _walk(value: Any, path: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            yield child_path, child
            yield from _walk(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def _keys(value: Any) -> set[str]:
    return {path.rsplit(".", 1)[-1].split("[", 1)[0] for path, _ in _walk(value)}


def _runtime_errors() -> list[str]:
    errors: list[str] = []
    package = ROOT / "scripts/sfh2_a0r"
    for path in sorted(package.glob("*.py")):
        content = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_RUNTIME_PATTERNS:
            if pattern.search(content):
                errors.append(f"semantic_heuristic_in_runtime:{path.name}:{pattern.pattern}")
    return errors


def _selection_errors() -> list[str]:
    errors: list[str] = []
    current = selection()
    cases = current.get("cases", []) if isinstance(current.get("cases"), list) else []
    if current.get("case_count") != 20 or len(cases) != 20:
        errors.append("selection_not_exactly_twenty")
    if current.get("gold_fields_present") is not False or current.get("gold_not_in_selection") is not True:
        errors.append("selection_gold_contract")
    if stable_hash({key: value for key, value in current.items() if key != "selection_hash"}) != text(current.get("selection_hash")):
        errors.append("selection_hash_invalid")
    try:
        if build_selection() != current:
            errors.append("selection_rebuild_drift")
    except Exception as exc:
        errors.append(f"selection_rebuild_error:{type(exc).__name__}")
    if len({text(row.get("case_id")) for row in cases if isinstance(row, Mapping)}) != len(cases):
        errors.append("selection_case_ids_not_unique")
    if GOLD_KEYS.intersection(_keys(cases)):
        errors.append("gold_fields_in_selection")
    return errors


def _architecture_errors(preflight: bool) -> list[str]:
    errors: list[str] = []
    current = selection()
    expected = architecture_freeze(text(current.get("selection_hash")))
    path = OUT / "architecture-freeze.json"
    if not path.is_file():
        if not preflight:
            errors.append("architecture_freeze_missing")
        return errors
    actual = read_json(path, {}) or {}
    if actual != expected:
        errors.append("architecture_freeze_drift")
    model = actual.get("model_config") or {}
    if model.get("model") != MODEL or model.get("temperature") != 0 or model.get("thinking") != {"type": "disabled"}:
        errors.append("model_config_changed")
    if model.get("prompt_versions") != PROMPT_VERSIONS:
        errors.append("prompt_versions_changed")
    if actual.get("selection_is_frozen") is not True:
        errors.append("selection_not_frozen")
    if actual.get("candidate_only") is not True or actual.get("canonical_write_back") is not False:
        errors.append("architecture_storage_contract")
    return errors


def _provider_artifact_errors(document: Any, name: str) -> list[str]:
    errors: list[str] = []
    if GOLD_KEYS.intersection(_keys(document)):
        errors.append(f"gold_fields_in_{name}")
    if SEMANTIC_RECORD_KEYS.intersection(_keys(document)):
        # A0R output must not carry complete records in review/adjudication
        # envelopes.  Pass 1 is allowed to contain its own semantic record.
        if name in {"pass2-review-decisions.json", "pass3-adjudication-decisions.json"}:
            errors.append(f"complete_record_in_{name}")
    return errors


def _transport_errors() -> list[str]:
    errors: list[str] = []
    live = OUT / "live"
    if not live.is_dir():
        return errors
    seen: set[str] = set()
    for path in sorted(live.glob("*/transport.json")):
        rows = read_json(path, None)
        if not isinstance(rows, list):
            errors.append(f"transport_not_list:{path.parent.name}")
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                errors.append(f"transport_row_invalid:{path.parent.name}")
                continue
            raw_path = text(row.get("raw_path"))
            if not raw_path:
                continue
            if raw_path in seen:
                errors.append(f"raw_path_reused:{raw_path}")
            seen.add(raw_path)
            if not (ROOT / raw_path).is_file():
                errors.append(f"raw_path_missing:{raw_path}")
    return errors


def _selector_errors() -> list[str]:
    errors: list[str] = []
    p1_doc = read_json(OUT / "pass1-semantic-results.json", {}) or {}
    p2_doc = read_json(OUT / "pass2-review-decisions.json", {}) or {}
    p3_doc = read_json(OUT / "pass3-adjudication-decisions.json", {}) or {}
    final_doc = read_json(OUT / "final-decisions.json", {}) or {}
    p1 = {text(row.get("case_id")): row for row in p1_doc.get("records", []) or [] if isinstance(row, Mapping)}
    p2 = {text(row.get("case_id")): row for row in p2_doc.get("records", []) or [] if isinstance(row, Mapping)}
    p3 = {text(row.get("case_id")): row for row in p3_doc.get("records", []) or [] if isinstance(row, Mapping)}
    finals = final_doc.get("records", []) if isinstance(final_doc.get("records"), list) else []
    if len(p1) != 20 or len(p2) != 20 or len(finals) != 20:
        errors.append("stage_case_count")
    for row in finals:
        if not isinstance(row, Mapping):
            errors.append("final_row_invalid")
            continue
        case_id = text(row.get("case_id"))
        decision = text(row.get("selector_decision"))
        selected = row.get("selected_record") if isinstance(row.get("selected_record"), Mapping) else None
        if decision == "select_pass1":
            expected = p1.get(case_id, {}).get("record") if isinstance(p1.get(case_id), Mapping) else None
            if selected != expected:
                errors.append(f"select_pass1_not_exact:{case_id}")
        elif decision == "select_pass2":
            expected = p2.get(case_id, {}).get("effective_record") if isinstance(p2.get(case_id), Mapping) else None
            if selected != expected:
                errors.append(f"select_pass2_not_exact:{case_id}")
        if row.get("candidate_only") is not True or row.get("canonical_write_back") is not False:
            errors.append(f"final_storage_contract:{case_id}")
        if row.get("final_state") in {"stable_entity_resolved", "local_candidate_resolved"} and not isinstance(row.get("selected_candidate"), Mapping):
            errors.append(f"identity_without_candidate:{case_id}")
        if isinstance(row.get("selected_record"), Mapping) and row["selected_record"].get("abstain") is True and row.get("final_state") in {"stable_entity_resolved", "local_candidate_resolved"}:
            errors.append(f"abstain_stored_as_identity:{case_id}")
    for row in p3.values():
        if not isinstance(row, Mapping):
            continue
        if SEMANTIC_RECORD_KEYS.intersection(_keys(row)):
            errors.append(f"selector_contains_complete_record:{row.get('case_id')}")
        decision = text(row.get("decision"))
        if decision in {"select_pass1", "select_pass2"} and row.get("patch"):
            errors.append(f"selector_selection_has_patch:{row.get('case_id')}")
    preservation = read_json(OUT / "semantic-preservation-audit.json", {}) or {}
    if int(preservation.get("selection_preservation_failures") or 0) != 0:
        errors.append("selection_preservation_failures")
    patch_audit = read_json(OUT / "reviewer-damage-audit.json", {}) or {}
    patch = patch_audit.get("patch_audit") or {}
    if int(patch.get("undeclared_patch_mutations") or 0) or int(patch.get("invalid_patch_count") or 0):
        errors.append("patch_mutation_failures")
    return errors


def _safety_errors() -> list[str]:
    errors: list[str] = []
    safety = read_json(OUT / "storage-safety-audit.json", {}) or {}
    for key in ("production_person_creations", "canonical_writes", "alias_mutations", "profile_mutations", "related_person_promotions", "attribute_person_promotions", "collective_person_promotions", "substring_candidate_creation", "python_identity_replacements", "internal_consistency_errors"):
        if safety.get(key) != 0:
            errors.append(f"unsafe_{key}")
    if safety.get("protected_inputs_unchanged") is not True:
        errors.append("protected_inputs_changed")
    if safety.get("candidate_only") is not True or safety.get("canonical_write_back") is not False:
        errors.append("safety_storage_contract")
    internal = read_json(OUT / "internal-consistency-audit.json", {}) or {}
    if internal.get("error_count") != 0 or internal.get("errors"):
        errors.append("internal_consistency_errors")
    metrics = read_json(OUT / "metrics.json", {}) or {}
    for key in ("production_persons_created", "canonical_writes", "alias_mutations", "profile_mutations", "copy_drift_errors", "undeclared_patch_mutations"):
        if metrics.get(key) != 0:
            errors.append(f"metrics_{key}")
    if metrics.get("candidate_only") is not True or metrics.get("canonical_write_back") is not False:
        errors.append("metrics_storage_contract")
    if metrics.get("no_full_188_story_live_run") is not True:
        errors.append("full_story_live_run_not_prohibited")
    return errors


def validate(*, preflight: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    errors.extend(_selection_errors())
    errors.extend(_architecture_errors(preflight))
    errors.extend(_runtime_errors())
    if preflight:
        return {
            "schema": "sfh2-a0r-validation-v1",
            "preflight": True,
            "valid": not errors,
            "errors": sorted(set(errors)),
            "case_count": selection().get("case_count", 0),
            "selection_hash": selection().get("selection_hash"),
        }
    required = [
        "case-packets.json", "pass1-semantic-results.json", "pass2-review-decisions.json",
        "pass3-adjudication-decisions.json", "final-decisions.json", "dimension-evaluation.json",
        "semantic-preservation-audit.json", "reviewer-damage-audit.json", "metrics.json",
        "storage-safety-audit.json", "internal-consistency-audit.json", "transport.json",
        "validation-summary.json", "recommendation.json",
    ]
    for name in required:
        if not (OUT / name).is_file():
            errors.append(f"missing_artifact:{name}")
    packets = read_json(OUT / "case-packets.json", {}) or {}
    if len(packets.get("packets", []) or []) != 20:
        errors.append("packet_count")
    if packets.get("gold_not_sent_to_provider") is not True:
        errors.append("packet_gold_contract")
    for name in ("case-packets.json", "pass1-semantic-results.json", "pass2-review-decisions.json", "pass3-adjudication-decisions.json", "final-decisions.json"):
        errors.extend(_provider_artifact_errors(read_json(OUT / name, {}) or {}, name))
    errors.extend(_selector_errors())
    errors.extend(_safety_errors())
    transport = read_json(OUT / "transport.json", {}) or {}
    if transport.get("model") != MODEL:
        errors.append("transport_model_changed")
    if int(transport.get("new_live_attempts") or 0) > MAX_PROVIDER_ATTEMPTS:
        errors.append("provider_attempt_budget")
    for stage in PROMPT_VERSIONS:
        if text((transport.get("prompt_versions") or {}).get(stage)) != PROMPT_VERSIONS[stage]:
            errors.append(f"transport_prompt_changed:{stage}")
    errors.extend(_transport_errors())
    architecture = read_json(OUT / "architecture-freeze.json", {}) or {}
    if architecture.get("input_hashes") != input_hashes():
        errors.append("frozen_input_hash_drift")
    summary = read_json(OUT / "validation-summary.json", {}) or {}
    if summary.get("candidate_only") is not True or summary.get("canonical_write_back") is not False:
        errors.append("summary_storage_contract")
    return {
        "schema": "sfh2-a0r-validation-v1",
        "preflight": False,
        "valid": not errors,
        "errors": sorted(set(errors)),
        "case_count": selection().get("case_count", 0),
        "selection_hash": selection().get("selection_hash"),
        "provider_attempts": transport.get("new_live_attempts", 0),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    result = validate(preflight=args.preflight)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
