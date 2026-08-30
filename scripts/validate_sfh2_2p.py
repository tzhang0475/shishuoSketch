#!/usr/bin/env python3
"""Validate the isolated SFH2.2-P freeze, safety, and evaluation contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_2p.common import OUT, SELECTION_PATH, file_hash, input_hashes, load_inputs, packet_index, read_json, stable_hash, text
from sfh2_2p.selection import build_selection


def _records(document: Any, key: str = "records") -> list[dict[str, Any]]:
    if isinstance(document, list):
        return [dict(row) for row in document if isinstance(row, Mapping)]
    if isinstance(document, Mapping) and isinstance(document.get(key), list):
        return [dict(row) for row in document[key] if isinstance(row, Mapping)]
    return []


def _walk(value: Any, keys: set[str] | None = None) -> list[tuple[str, Any]]:
    keys = keys or set()
    found: list[tuple[str, Any]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            found.append((str(key), item))
            found.extend(_walk(item, keys))
    elif isinstance(value, list):
        for item in value:
            found.extend(_walk(item, keys))
    return found


def validate() -> dict[str, Any]:
    errors: list[str] = []
    selection = read_json(SELECTION_PATH, {}) or {}
    expected_selection = build_selection(load_inputs())
    if selection != expected_selection:
        errors.append("selection_not_frozen_or_deterministic")
    generated = read_json(OUT / "selection.json", {}) or {}
    if generated != selection:
        errors.append("generated_selection_mismatch")
    if text(selection.get("model")) != "deepseek-v4-flash":
        errors.append("model_drift")
    if selection.get("case_count") != 30:
        errors.append("pilot_case_count_not_30")
    if selection.get("gold_case_count") != 25 or selection.get("blind_case_count") != 5:
        errors.append("gold_blind_partition_drift")
    cases = _records(selection, "cases")
    case_ids = [text(row.get("case_id")) for row in cases]
    mention_ids = [text(row.get("mention_id")) for row in cases]
    if len(set(case_ids)) != len(case_ids) or len(set(mention_ids)) != len(mention_ids):
        errors.append("duplicate_case_or_mention")
    inputs = load_inputs()
    input_manifest = read_json(OUT / "input-manifest.json", {}) or {}
    if input_manifest.get("selection_hash") != selection.get("selection_hash"):
        errors.append("input_manifest_selection_drift")
    if input_manifest.get("input_hashes") != input_hashes(inputs):
        errors.append("pilot_input_hash_drift")
    if input_manifest.get("model") != "deepseek-v4-flash":
        errors.append("input_manifest_model_drift")
    mentions = {text(row.get("mention_id")): row for row in _records(inputs.get("mentions"))}
    packets = packet_index(inputs)
    for row in cases:
        mention = mentions.get(text(row.get("mention_id")))
        packet = packets.get(text(row.get("story_id")))
        if not mention or not packet:
            errors.append(f"selection_reference_missing:{row.get('case_id')}")
            continue
        if text(mention.get("surface")) != text(row.get("surface")) or text(mention.get("source_evidence_id")) != text(row.get("source_evidence_id")):
            errors.append(f"selection_mention_drift:{row.get('case_id')}")
    if selection.get("selection_hash") != stable_hash({key: value for key, value in selection.items() if key != "selection_hash"}):
        errors.append("selection_hash_invalid")

    packets_doc = read_json(OUT / "case-packets.json", {}) or {}
    packets_rows = _records(packets_doc, "packets")
    if len(packets_rows) != len(cases):
        errors.append("case_packet_count")
    packet_forbidden = {"expected_identity", "expected_person_id", "must_not_resolve_to", "evaluation_mode", "expected_semantic_class"}
    for key, value in _walk(packets_rows):
        if key in packet_forbidden:
            errors.append(f"gold_leaked_to_case_packets:{key}")
            break
    if any(row.get("gold_visible_to_model") is not False for row in packets_rows):
        errors.append("gold_visibility_flag")

    final = read_json(OUT / "final-decisions.json", {}) or {}
    final_rows = _records(final)
    if len(final_rows) != len(cases):
        errors.append("final_case_count")
    candidate_sets = read_json(OUT / "candidate-sets.json", {}) or {}
    candidate_rows = _records(candidate_sets)
    people = {text(row.get("person_id")) for row in (inputs.get("people") or {}).get("people", []) or [] if isinstance(row, Mapping)}
    for row in candidate_rows:
        for candidate in row.get("candidates", []) or []:
            if not isinstance(candidate, Mapping):
                errors.append("candidate_not_object")
                continue
            pid = text(candidate.get("person_id"))
            if pid and pid not in people:
                errors.append(f"unknown_production_person:{pid}")
            cid = text(candidate.get("candidate_person_id"))
            if cid and cid.startswith("person-"):
                errors.append(f"candidate_uses_production_id:{cid}")
            bases = " ".join(text(value) for value in candidate.get("retrieval_basis", []) or [])
            if any(word in bases.lower() for word in ("substring", "co_occurrence", "local_context_scan", "nearest")):
                errors.append("unsafe_substring_candidate_basis")

    final_by_case = {text(row.get("case_id")): row for row in final_rows}
    for case in cases:
        final_row = final_by_case.get(text(case.get("case_id")), {})
        selected = final_row.get("selected_candidate") if isinstance(final_row.get("selected_candidate"), Mapping) else {}
        selected_pid = text(selected.get("person_id"))
        violations = [value for value in case.get("must_not_resolve_to", []) or [] if text(value) == selected_pid]
        if violations and final_row.get("final_state") in {"stable_entity_resolved", "local_candidate_resolved"}:
            errors.append(f"forbidden_mapping:{case.get('case_id')}:{','.join(violations)}")
    # Explicit known contamination controls remain mechanical checks, not
    # semantic inference.
    for row in candidate_rows:
        surface = text(row.get("surface"))
        pids = {text(candidate.get("person_id")) for candidate in row.get("candidates", []) or [] if isinstance(candidate, Mapping)}
        if surface == "仲文" and "person-031" in pids:
            errors.append("hda2_suppressed_claim_reintroduced:仲文")
        if surface in {"王丞相", "王大將軍"} and "person-054" in pids:
            errors.append(f"wangyin_contamination_reintroduced:{surface}")

    safety = read_json(OUT / "alias-safety-audit.json", {}) or {}
    for key in ("new_global_aliases", "new_occurrence_propagated_alias_evidence", "substring_derived_candidates", "profile_contamination_recurrence"):
        if safety.get(key) != 0:
            errors.append(f"alias_safety:{key}")
    if safety.get("aliases_before_sha256") != safety.get("aliases_after_sha256"):
        errors.append("pilot_mutated_aliases")
    for name in ("input-manifest.json", "l3-semantic-results.json", "l5-identity-results.json", "candidate-recall-audit.json", "gold-evaluation.json", "blind-case-results.json", "metrics.json", "validation-summary.json", "recommendation.json", "network-role-audit.json", "registry-miss-results.json", "replay-transport.json"):
        if not (OUT / name).is_file():
            errors.append(f"missing_output:{name}")
    metrics = read_json(OUT / "metrics.json", {}) or {}
    if metrics.get("candidate_only") is not True or metrics.get("canonical_write_back") is not False:
        errors.append("candidate_only_contract")
    if metrics.get("no_full_188_story_live_run") is not True:
        errors.append("full_story_live_run_flag")
    transport = read_json(OUT / "transport.json", {}) or {}
    if text(transport.get("model")) != "deepseek-v4-flash":
        errors.append("transport_model_drift")
    if transport.get("new_live_calls", 0) > 80:
        errors.append("live_call_budget_exceeded")
    evaluation = read_json(OUT / "gold-evaluation.json", {}) or {}
    evaluation_metrics = evaluation.get("metrics") if isinstance(evaluation.get("metrics"), Mapping) else {}
    if evaluation_metrics.get("candidate_recall_denominator", 0) < evaluation_metrics.get("candidate_recall_numerator", 0):
        errors.append("recall_metric_invalid")
    evaluation_rows = _records(evaluation)
    expected_semantic_false_positives = sum(row.get("category") == "semantic_identity_failure" for row in evaluation_rows)
    if evaluation_metrics.get("semantic_false_positive_count") != expected_semantic_false_positives:
        errors.append("semantic_false_positive_accounting_invalid")
    if evaluation_metrics.get("wrong_resolutions") != expected_semantic_false_positives:
        errors.append("wrong_resolution_accounting_invalid")
    return {
        "schema": "sfh2-2p-validation-v1",
        "valid": not errors,
        "errors": sorted(set(errors)),
        "selection_hash": selection.get("selection_hash"),
        "case_count": len(cases),
        "gold_case_count": selection.get("gold_case_count"),
        "blind_case_count": selection.get("blind_case_count"),
        "candidate_recall": evaluation_metrics.get("candidate_recall"),
        "semantic_precision": evaluation_metrics.get("semantic_precision"),
        "forbidden_mapping_violations": evaluation_metrics.get("forbidden_mapping_violations", 0),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
