#!/usr/bin/env python3
"""Validate the isolated SFH2.2-A0 semantic-authority pilot."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from sfh2_a0.common import (
    MAX_PROVIDER_ATTEMPTS, MODEL, OUT, PILOT_VERSION, PROMPT_VERSIONS,
    SELECTION_PATH, architecture_freeze, canonical_json, file_hash,
    input_hashes, read_json, stable_hash, text,
)
from sfh2_a0.selection import build_selection

ROOT = Path(__file__).resolve().parents[1]
GOLD_KEYS = {
    "expected_identity", "expected_canonical_hint", "expected_role", "expected_semantic_kind",
    "expected_referent_surface", "expected_attribute_type", "expected_attribute_value",
    "expected_bearer", "must_not_resolve_to", "allow_abstention", "case_key",
}
EXCLUDED_ROLES = {
    "citation_source_person", "historical_exemplum", "person_attribute",
    "collective_reference", "structural", "genealogy_reference", "annotation_person",
}
PRODUCTION_ID = re.compile(r"(?:^|[^A-Za-z0-9])person-[0-9A-Za-z_-]+(?:$|[^A-Za-z0-9])")


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


def _production_ids(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, str) and PRODUCTION_ID.search(value):
        found.append(path)
    elif isinstance(value, Mapping):
        for key, child in value.items():
            found.extend(_production_ids(child, f"{path}.{key}" if path else str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_production_ids(child, f"{path}[{index}]"))
    return found


def _semantic_record_production_id_errors(document: Mapping[str, Any], path_name: str) -> list[str]:
    """Reject IDs emitted by the provider, not IDs added by realization.

    Pass artifacts also carry the deterministic provisional realization, which
    may legitimately contain an existing registry Person ID.  The A0
    prohibition applies to the LLM semantic record itself; inspecting the
    whole document would confuse Python's lookup output with provider output.
    """

    errors: list[str] = []
    for index, row in enumerate(document.get("records", []) or []):
        if not isinstance(row, Mapping) or not row.get("valid") or not isinstance(row.get("record"), Mapping):
            continue
        if _production_ids(row["record"]):
            errors.append(f"production_id_in_{path_name}:records[{index}].record")
    return errors


def _selection_errors(selection: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    cases = selection.get("cases") if isinstance(selection.get("cases"), list) else []
    if selection.get("case_count") != 20 or len(cases) != 20:
        errors.append("selection_not_exactly_twenty")
    if selection.get("gold_fields_present") is not False or selection.get("gold_not_in_selection") is not True:
        errors.append("selection_gold_contract")
    if stable_hash({key: value for key, value in selection.items() if key != "selection_hash"}) != text(selection.get("selection_hash")):
        errors.append("selection_hash_invalid")
    if len({text(row.get("case_id")) for row in cases if isinstance(row, Mapping)}) != len(cases):
        errors.append("selection_case_ids_not_unique")
    if len({text(row.get("mention_id")) for row in cases if isinstance(row, Mapping)}) != len(cases):
        errors.append("selection_mention_ids_not_unique")
    if GOLD_KEYS.intersection(_keys(cases)):
        errors.append("gold_fields_in_selection")
    for row in cases:
        if not isinstance(row, Mapping) or not text(row.get("case_id")) or not text(row.get("mention_id")) or not text(row.get("source_evidence_id")):
            errors.append("selection_case_missing_provenance")
    return errors


def _runtime_heuristic_errors() -> list[str]:
    errors: list[str] = []
    package = ROOT / "scripts/sfh2_a0"
    forbidden = [
        re.compile(r"surface\s*=="),
        re.compile(r"surface\s+in\s+"),
        re.compile(r"canonical_hint\s*=\s*['\"](?:王|卿|宣王|太丘長)"),
    ]
    for path in sorted(package.glob("*.py")):
        content = path.read_text(encoding="utf-8")
        for pattern in forbidden:
            if pattern.search(content):
                errors.append(f"semantic_heuristic_in_runtime:{path.name}:{pattern.pattern}")
    return errors


def _transport_raw_errors() -> list[str]:
    errors: list[str] = []
    live = OUT / "live"
    if not live.is_dir():
        return errors
    for path in sorted(live.glob("*/transport.json")):
        rows = read_json(path, None)
        if not isinstance(rows, list):
            errors.append(f"transport_not_list:{path.parent.name}")
            continue
        seen: set[str] = set()
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


def validate(*, preflight: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    selection = read_json(SELECTION_PATH, {}) or {}
    errors.extend(_selection_errors(selection))
    try:
        if build_selection() != selection:
            errors.append("selection_rebuild_drift")
    except Exception as exc:
        errors.append(f"selection_rebuild_error:{type(exc).__name__}")
    gold = read_json(ROOT / "data/annotation/sfh2-a0-evaluation-gold.json", {}) or {}
    if not gold.get("evaluation_only") or not gold.get("not_for_provider"):
        errors.append("gold_not_isolated")
    if len(gold.get("records", []) or []) != 20:
        errors.append("gold_count")
    architecture = read_json(OUT / "architecture-freeze.json", {}) or {}
    expected_architecture = architecture_freeze(text(selection.get("selection_hash")))
    if architecture != expected_architecture:
        errors.append("architecture_freeze_drift")
    errors.extend(_runtime_heuristic_errors())
    if preflight:
        return {
            "schema": "sfh2-a0-validation-v1",
            "preflight": True,
            "valid": not errors,
            "errors": sorted(set(errors)),
            "case_count": selection.get("case_count", 0),
            "selection_hash": selection.get("selection_hash"),
        }

    packets = read_json(OUT / "case-packets.json", {}) or {}
    packet_rows = packets.get("packets", []) if isinstance(packets, Mapping) else []
    if len(packet_rows) != 20:
        errors.append("packet_count")
    if packets.get("gold_not_sent_to_provider") is not True:
        errors.append("packet_gold_contract")
    if GOLD_KEYS.intersection(_keys(packets)):
        errors.append("gold_fields_in_packets")
    for path_name, expected_count in (("pass1-semantic-results.json", 20), ("pass2-review-results.json", 20), ("final-decisions.json", 20)):
        document = read_json(OUT / path_name, {}) or {}
        rows = document.get("records", []) if isinstance(document, Mapping) else []
        if len(rows) != expected_count:
            errors.append(f"{path_name}:count")
        if document.get("candidate_only") is not True or document.get("canonical_write_back") is not False:
            errors.append(f"{path_name}:storage_contract")
    p3_document = read_json(OUT / "pass3-adjudication-results.json", {}) or {}
    p3_rows = p3_document.get("records", []) if isinstance(p3_document, Mapping) else []
    if len(p3_rows) > 20:
        errors.append("pass3_count")
    for path_name in ("pass1-semantic-results.json", "pass2-review-results.json", "pass3-adjudication-results.json"):
        document = read_json(OUT / path_name, {}) or {}
        errors.extend(_semantic_record_production_id_errors(document, path_name))
        if GOLD_KEYS.intersection(_keys(document)):
            errors.append(f"gold_fields_in_{path_name}")

    final_document = read_json(OUT / "final-decisions.json", {}) or {}
    finals = final_document.get("records", []) if isinstance(final_document, Mapping) else []
    for row in finals:
        if not isinstance(row, Mapping):
            errors.append("final_row_invalid")
            continue
        if row.get("candidate_only") is not True or row.get("canonical_write_back") is not False:
            errors.append(f"final_storage:{row.get('case_id')}")
        if row.get("final_state") in {"stable_entity_resolved", "local_candidate_resolved"} and not isinstance(row.get("selected_candidate"), Mapping):
            errors.append(f"identity_without_candidate:{row.get('case_id')}")
        if text(row.get("semantic_kind")) in {"person_attribute", "collective", "structural"} and row.get("selected_candidate") is not None:
            errors.append(f"non_person_promoted:{row.get('case_id')}")
        if text(row.get("occurrence_role")) in EXCLUDED_ROLES and row.get("core_graph_eligible") is True:
            errors.append(f"excluded_role_graph_eligible:{row.get('case_id')}")
        if row.get("final_state") in {"stable_entity_resolved", "local_candidate_resolved"} and row.get("selected_record", {}).get("abstain") is True:
            errors.append(f"abstain_identity:{row.get('case_id')}")

    safety = read_json(OUT / "storage-safety-audit.json", {}) or {}
    for key in ("production_person_creations", "canonical_writes", "alias_mutations", "profile_mutations", "related_person_promotions", "attribute_person_promotions", "collective_person_promotions", "substring_candidate_creation", "python_identity_replacements", "internal_consistency_errors"):
        if safety.get(key) != 0:
            errors.append(f"unsafe_{key}")
    if safety.get("protected_inputs_unchanged") is not True:
        errors.append("protected_inputs_changed")
    internal = read_json(OUT / "internal-consistency-audit.json", {}) or {}
    if internal.get("error_count") != 0 or internal.get("errors"):
        errors.append("internal_consistency_errors")
    transport = read_json(OUT / "transport.json", {}) or {}
    if transport.get("model") != MODEL:
        errors.append("model_changed")
    if int(transport.get("new_live_attempts") or 0) > MAX_PROVIDER_ATTEMPTS:
        errors.append("provider_attempt_budget")
    for stage, maximum in (("primary_historian", 40), ("critical_reviewer", 40), ("adjudicator", 40)):
        if int((transport.get("by_stage") or {}).get(stage, {}).get("calls") or 0) > maximum:
            errors.append(f"stage_attempt_budget:{stage}")
    if GOLD_KEYS.intersection(_keys(read_json(OUT / "evaluation.json", {}) or {})):
        # Gold is intentionally present in the evaluation artifact, so this
        # is not an error.  Keep the explicit check out of provider artifacts.
        pass
    metrics = read_json(OUT / "metrics.json", {}) or {}
    if metrics.get("candidate_only") is not True or metrics.get("canonical_write_back") is not False:
        errors.append("metrics_storage_contract")
    if metrics.get("production_persons_created") != 0 or metrics.get("canonical_writes") != 0:
        errors.append("metrics_unsafe_storage")
    errors.extend(_transport_raw_errors())
    return {
        "schema": "sfh2-a0-validation-v1",
        "preflight": False,
        "valid": not errors,
        "errors": sorted(set(errors)),
        "case_count": selection.get("case_count", 0),
        "selection_hash": selection.get("selection_hash"),
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
