"""Run and evaluate the SFH2.2-A2OVB blind boundary-validator pilot."""

from __future__ import annotations

import copy
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from sfh2_a2o.provenance import project_legacy_occurrence_role

from .common import (
    A2O_ROOT,
    A2OR_ROOT,
    A2OSP_ROOT,
    A2OT_ROOT,
    A2OV_ROOT,
    ACTIVE_GOLD_SHA256,
    BOUNDARY_FUNCTIONS,
    BOUNDARY_JUDGMENTS,
    CASE_COUNT,
    CHALLENGE_COUNT,
    CONFIDENCES,
    CURRENT_SC1_SHA256,
    FROZEN_SC1_SHA256,
    FUNCTION_NAME,
    GOLD_PATH,
    IDENTITY_MANIFEST_SHA256,
    IDENTITY_MANIFEST_PATH,
    MODEL,
    OUT,
    PROMPT_VERSION,
    REVIEWED_ROLE_COUNT,
    ROOT,
    SCHEMA_VERSION,
    SELECTION_HASH,
    STRICT_ENDPOINT,
    TEMPERATURE,
    THINKING,
    boundary_case_ids,
    by_case,
    exact_key_map,
    exact_occurrence_key,
    file_hash,
    input_hashes,
    load_frozen_bundle,
    primary_function,
    primary_semantic,
    protected_hashes,
    provider_payload,
    read_json,
    stable_hash,
    text,
    write_json,
)
from .contracts import boundary_tool, validate_boundary_payload, validate_deepseek_strict_schema, validate_probe_payload
from .prompt import HISTORIAN_SYSTEM, probe_messages, prompt_metadata
from .transport import BoundaryClient, summarize


def _stable_transport(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "stage", "case_id", "request_hash", "model", "temperature", "thinking",
        "prompt_version", "attempt", "classification", "valid", "parse_error",
        "usage", "finish_reason", "response_witness_sha256", "http_status",
        "provider_error_body", "provider_error_code", "provider_error_message",
        "provider_error_type", "provider_error_param", "provider_request_id",
        "retryable", "attempt_history", "elapsed_seconds",
    )
    return {key: copy.deepcopy(row[key]) for key in keys if key in row}


def _architecture(bundle: Mapping[str, Any], tool: Mapping[str, Any]) -> dict[str, Any]:
    code_paths = [
        ROOT / "scripts/sfh2_a2ovb/common.py",
        ROOT / "scripts/sfh2_a2ovb/contracts.py",
        ROOT / "scripts/sfh2_a2ovb/prompt.py",
        ROOT / "scripts/sfh2_a2ovb/transport.py",
        ROOT / "scripts/sfh2_a2ovb/pipeline.py",
    ]
    result: dict[str, Any] = {
        "schema": "sfh2-a2ovb-architecture-v1",
        "stage": "SFH2.2-A2OVB",
        "baseline_commit": "ca3ac0d39f7f85282f555a4b4494f6116c9afbe1",
        "case_count": len(bundle["case_ids"]),
        "boundary_cohort_rule": "A2OR cached narrative_function in participant/reference; no Gold selection",
        "boundary_function_values": list(BOUNDARY_FUNCTIONS),
        "boundary_cohort_count": len(boundary_case_ids(bundle)),
        "primary_source": "A2OR cached live occurrence-results.json used only for routing and fallback",
        "primary_source_path": "data/generated/sfh2-a2or/occurrence-results.json",
        "primary_new_provider_calls": 0,
        "validator_role": "blind specialized participant/reference boundary validator",
        "validator_is_primary_blind": True,
        "validator_is_gold_blind": True,
        "validator_is_residual_error_blind": True,
        "provider_packet_excludes_primary": True,
        "provider_packet_excludes_gold": True,
        "provider_packet_excludes_residual_labels": True,
        "provenance_is_structural": True,
        "identity_is_frozen": True,
        "model_config": {
            "model": MODEL,
            "temperature": TEMPERATURE,
            "thinking": dict(THINKING),
            "endpoint": STRICT_ENDPOINT,
            "prompt_version": PROMPT_VERSION,
            "function_name": FUNCTION_NAME,
            "expected_provider_calls": 1 + len(boundary_case_ids(bundle)),
            "retry_policy": "transient_only_at_most_one_retry; HTTP400_not_retryable",
        },
        "prompt": prompt_metadata(),
        "prompt_hash": stable_hash(HISTORIAN_SYSTEM),
        "schema_hash": stable_hash(tool),
        "code_files": {str(path.relative_to(ROOT)): file_hash(path) for path in code_paths if path.is_file()},
        "frozen_input_hashes": input_hashes(),
        "active_gold_evaluation_hash": file_hash(GOLD_PATH),
        "protected_hashes_at_preparation": protected_hashes(),
        "candidate_only": True,
        "canonical_write_back": False,
        "no_full_188_story_live_run": True,
    }
    result["architecture_hash"] = stable_hash(result)
    return result


def _selection(bundle: Mapping[str, Any]) -> dict[str, Any]:
    exact = exact_key_map(bundle)
    boundary = boundary_case_ids(bundle)
    primary_counts = Counter(primary_function(bundle["primary_rows"][case_id]) for case_id in bundle["case_ids"])
    return {
        "schema": "sfh2-a2ovb-selection-v1",
        "selection_method": "all_frozen_A2OR_cases_routed_by_cached_primary_boundary_function",
        "selection_is_deterministic": True,
        "total_case_count": len(bundle["case_ids"]),
        "boundary_cohort_count": len(boundary),
        "non_boundary_case_count": len(bundle["case_ids"]) - len(boundary),
        "primary_function_counts": dict(sorted(primary_counts.items())),
        "boundary_case_ids": boundary,
        "non_boundary_case_ids": [case_id for case_id in bundle["case_ids"] if case_id not in boundary],
        "case_ids": list(bundle["case_ids"]),
        "exact_occurrence_keys": exact,
        "source_selection_hash": SELECTION_HASH,
        "gold_used_for_selection": False,
        "a2ov_used_for_selection": False,
        "residual_labels_used_for_selection": False,
        "surface_only_resolution": False,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _boundary_packets(bundle: Mapping[str, Any]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for case_id in boundary_case_ids(bundle):
        packet = bundle["packets"][case_id]
        payload = provider_payload(packet)
        records.append({
            "case_id": case_id,
            "cohort": bundle["primary_rows"][case_id].get("cohort"),
            "exact_occurrence_key": exact_occurrence_key(packet),
            "provider_payload": payload,
        })
    return {
        "schema": "sfh2-a2ovb-boundary-packets-v1",
        "case_count": len(records),
        "routing_source": "A2OR cached result, represented only in selection.json; not included in provider payload",
        "provider_payload_is_primary_blind": True,
        "provider_payload_is_gold_blind": True,
        "provider_payload_is_residual_error_blind": True,
        "records": records,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _write_preparation(output: Path, bundle: Mapping[str, Any], tool: Mapping[str, Any]) -> None:
    write_json(output / "architecture.json", _architecture(bundle, tool))
    write_json(output / "selection.json", _selection(bundle))
    write_json(output / "boundary-packets.json", _boundary_packets(bundle))


def _result_row(case_id: str, packet: Mapping[str, Any], payload: Mapping[str, Any] | None, transport: Mapping[str, Any]) -> dict[str, Any]:
    provider_packet = provider_payload(packet)
    validation = validate_boundary_payload(provider_packet, payload)
    return {
        "case_id": case_id,
        "cohort": None,
        "exact_occurrence_key": exact_occurrence_key(packet),
        "story_id": text(packet.get("story_id")),
        "mention_id": text(packet.get("mention_id")),
        "surface": text((packet.get("target") or {}).get("surface")),
        "provenance_layer": text(packet.get("provenance_layer")),
        "validator_valid": validation.get("valid") is True,
        "validator_contract_status": "valid" if validation.get("valid") else "provider_or_contract_invalid",
        "validator_errors": sorted(set(validation.get("errors", []))),
        "validator_result": copy.deepcopy(validation.get("result")) if validation.get("valid") else None,
        "frozen_identity": copy.deepcopy(packet.get("frozen_identity_context", {})),
        "frozen_identity_hash": stable_hash(packet.get("frozen_identity_context", {})),
        "identity_preserved": True,
        "provenance_preserved": True,
        "transport": _stable_transport(transport),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _final_row(case_id: str, bundle: Mapping[str, Any], boundary_rows: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    packet = bundle["packets"][case_id]
    primary = primary_semantic(bundle["primary_rows"][case_id])
    p_function = text(primary.get("narrative_function"))
    boundary = case_id in boundary_rows
    boundary_row = boundary_rows.get(case_id)
    judgment = None
    confidence = None
    validator_result = None
    valid = True
    if boundary:
        validator_result = boundary_row.get("validator_result") if isinstance(boundary_row, Mapping) else None
        valid = boundary_row.get("validator_valid") is True if isinstance(boundary_row, Mapping) else False
        if isinstance(validator_result, Mapping):
            judgment = text(validator_result.get("boundary_judgment"))
            confidence = text(validator_result.get("confidence"))
    final = copy.deepcopy(primary)
    applied = False
    if boundary and valid:
        if judgment == "event_participant":
            final["narrative_function"] = "participant"
            applied = True
        elif judgment == "referential_only":
            final["narrative_function"] = "reference"
            applied = True
        elif judgment == "uncertain":
            pass
        else:
            valid = False
    final_function = text(final.get("narrative_function"))
    provenance = text(packet.get("provenance_layer"))
    return {
        "case_id": case_id,
        "cohort": bundle["primary_rows"][case_id].get("cohort"),
        "story_id": text(packet.get("story_id")),
        "surface": text((packet.get("target") or {}).get("surface")),
        "exact_occurrence_key": exact_occurrence_key(packet),
        "provenance_layer": provenance,
        "primary_semantic": primary,
        "primary_function": p_function,
        "boundary_validator_result": copy.deepcopy(validator_result),
        "boundary_judgment": judgment,
        "boundary_confidence": confidence,
        "boundary_validator_applied": applied,
        "final_semantic": final,
        "primary_legacy_occurrence_role": project_legacy_occurrence_role(provenance, p_function) if p_function else None,
        "final_legacy_occurrence_role": project_legacy_occurrence_role(provenance, final_function) if final_function else None,
        "valid": valid,
        "identity_preserved": True,
        "provenance_preserved": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _accuracy(records: list[Mapping[str, Any]], field: str) -> dict[str, Any]:
    values = [row.get(field) for row in records if row.get(field) is not None]
    correct = sum(value is True for value in values)
    return {"correct": correct, "evaluable": len(values), "accuracy": round(correct / len(values), 4) if values else None}


def _evaluate(bundle: Mapping[str, Any], boundary_rows: Mapping[str, Mapping[str, Any]], finals: list[Mapping[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    gold = by_case(read_json(GOLD_PATH, {}))
    records: list[dict[str, Any]] = []
    for final in finals:
        case_id = text(final.get("case_id"))
        expected = gold[case_id]
        primary = final.get("primary_semantic") if isinstance(final.get("primary_semantic"), Mapping) else {}
        output = final.get("final_semantic") if isinstance(final.get("final_semantic"), Mapping) else {}
        expected_function = text(expected.get("expected_narrative_function"))
        primary_function_value = text(primary.get("narrative_function"))
        final_function_value = text(output.get("narrative_function"))
        boundary_expected = {"participant": "event_participant", "reference": "referential_only"}.get(expected_function)
        boundary_row = boundary_rows.get(case_id)
        validator_result = boundary_row.get("validator_result") if isinstance(boundary_row, Mapping) else None
        validator_judgment = text(validator_result.get("boundary_judgment")) if isinstance(validator_result, Mapping) else None
        records.append({
            "case_id": case_id,
            "cohort": final.get("cohort"),
            "story_id": final.get("story_id"),
            "surface": final.get("surface"),
            "exact_occurrence_key": copy.deepcopy(final.get("exact_occurrence_key")),
            "provenance_layer": final.get("provenance_layer"),
            "primary_function": primary_function_value,
            "final_function": final_function_value,
            "primary_legacy_occurrence_role": final.get("primary_legacy_occurrence_role"),
            "final_legacy_occurrence_role": final.get("final_legacy_occurrence_role"),
            "expected_provenance_layer": expected.get("expected_provenance_layer"),
            "expected_narrative_function": expected_function,
            "expected_legacy_occurrence_role": expected.get("expected_legacy_occurrence_role"),
            "primary_narrative_function_correct": primary_function_value == expected_function,
            "final_narrative_function_correct": final_function_value == expected_function if final.get("valid") else None,
            "primary_legacy_role_correct": final.get("primary_legacy_occurrence_role") == expected.get("expected_legacy_occurrence_role"),
            "final_legacy_role_correct": final.get("final_legacy_occurrence_role") == expected.get("expected_legacy_occurrence_role") if final.get("valid") else None,
            "provenance_correct": final.get("provenance_layer") == expected.get("expected_provenance_layer"),
            "identity_preserved": final.get("identity_preserved") is True,
            "valid": final.get("valid") is True,
            "boundary_cohort": case_id in boundary_rows,
            "boundary_judgment": validator_judgment,
            "expected_boundary_judgment": boundary_expected,
            "boundary_judgment_correct": validator_judgment == boundary_expected if case_id in boundary_rows and boundary_expected else None,
            "validator_confidence": (validator_result or {}).get("confidence") if isinstance(validator_result, Mapping) else None,
            "validator_reason_summary": (validator_result or {}).get("reason_summary") if isinstance(validator_result, Mapping) else None,
        })
    reviewed_role = [row for row in records if row.get("cohort") == "reviewed_role"]
    challenge = [row for row in records if row.get("cohort") == "challenge"]
    by_cohort = {}
    for name, subset in (("all", records), ("reviewed_role", reviewed_role), ("challenge", challenge)):
        by_cohort[name] = {
            "case_count": len(subset),
            "primary_narrative_function": _accuracy(subset, "primary_narrative_function_correct"),
            "final_narrative_function": _accuracy(subset, "final_narrative_function_correct"),
            "primary_legacy_role": _accuracy(subset, "primary_legacy_role_correct"),
            "final_legacy_role": _accuracy(subset, "final_legacy_role_correct"),
            "provenance": _accuracy(subset, "provenance_correct"),
        }
    by_layer: dict[str, Any] = {}
    for layer in sorted({text(row.get("expected_provenance_layer")) for row in records}):
        subset = [row for row in records if text(row.get("expected_provenance_layer")) == layer]
        by_layer[layer] = {
            "case_count": len(subset),
            "primary": _accuracy(subset, "primary_narrative_function_correct"),
            "final": _accuracy(subset, "final_narrative_function_correct"),
            "provenance": _accuracy(subset, "provenance_correct"),
        }
    by_function: dict[str, Any] = {}
    for function in sorted({text(row.get("expected_narrative_function")) for row in records}):
        subset = [row for row in records if text(row.get("expected_narrative_function")) == function]
        by_function[function] = {
            "case_count": len(subset),
            "primary_correct": sum(row.get("primary_narrative_function_correct") is True for row in subset),
            "final_correct": sum(row.get("final_narrative_function_correct") is True for row in subset),
            "final_accuracy": round(sum(row.get("final_narrative_function_correct") is True for row in subset) / len(subset), 4) if subset else None,
        }
    boundary_records = [row for row in records if row.get("boundary_cohort")]
    boundary_valid = [row for row in boundary_records if row.get("valid") is True and row.get("boundary_judgment")]
    boundary_eval = {
        "schema": "sfh2-a2ovb-boundary-evaluation-v1",
        "cohort_count": len(boundary_records),
        "valid_records": sum(row.get("valid") is True for row in boundary_records),
        "evaluable_records": sum(row.get("expected_boundary_judgment") is not None for row in boundary_records),
        "correct": sum(row.get("boundary_judgment_correct") is True for row in boundary_records),
        "accuracy": round(sum(row.get("boundary_judgment_correct") is True for row in boundary_records) / len([row for row in boundary_records if row.get("expected_boundary_judgment") is not None]), 4) if [row for row in boundary_records if row.get("expected_boundary_judgment") is not None] else None,
        "prediction_counts": dict(sorted(Counter(row.get("boundary_judgment") or "invalid" for row in boundary_records).items())),
        "gold_boundary_counts": dict(sorted(Counter(row.get("expected_boundary_judgment") or "not_boundary_evaluable" for row in boundary_records).items())),
        "records": boundary_records,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    full = {
        "schema": "sfh2-a2ovb-full-evaluation-v1",
        "case_count": len(records),
        "records": records,
        "metrics": {
            "valid_boundary_records": sum(row.get("valid") is True for row in boundary_records),
            "boundary_cohort_count": len(boundary_records),
            "valid_final_records": sum(row.get("valid") is True for row in records),
            "primary_narrative_function": _accuracy(records, "primary_narrative_function_correct"),
            "final_narrative_function": _accuracy(records, "final_narrative_function_correct"),
            "primary_legacy_role": _accuracy(records, "primary_legacy_role_correct"),
            "final_legacy_role": _accuracy(records, "final_legacy_role_correct"),
            "provenance": _accuracy(records, "provenance_correct"),
            "identity_preservation": _accuracy(records, "identity_preserved"),
            "annotation_to_scene_collapse": sum(row.get("expected_legacy_occurrence_role") == "annotation_person" and row.get("final_legacy_occurrence_role") == "scene_participant" for row in records),
            "unresolved": sum(row.get("valid") is not True for row in records),
        },
        "by_cohort": by_cohort,
        "by_provenance_layer": by_layer,
        "by_narrative_function": by_function,
        "gold_loaded_after_provider_inference": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    return boundary_eval, full


def _override_value(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    result: list[dict[str, Any]] = []
    counts = Counter()
    for row in evaluation["records"]:
        if not row.get("boundary_cohort"):
            continue
        primary_correct = row.get("primary_narrative_function_correct") is True
        final_correct = row.get("final_narrative_function_correct") is True
        judgment = row.get("boundary_judgment")
        if row.get("valid") is not True:
            category = "transport_unresolved"
        elif judgment == "uncertain":
            category = "uncertain_preserved_correct" if primary_correct else "uncertain_preserved_wrong"
        elif not primary_correct and final_correct:
            category = "helpful_override"
        elif primary_correct and not final_correct:
            category = "harmful_override"
        elif primary_correct and final_correct:
            category = "unchanged_correct"
        else:
            category = "unchanged_wrong"
        counts[category] += 1
        result.append({
            "case_id": row.get("case_id"),
            "exact_occurrence_key": copy.deepcopy(row.get("exact_occurrence_key")),
            "primary_function": row.get("primary_function"),
            "boundary_judgment": judgment,
            "final_function": row.get("final_function"),
            "expected_function": row.get("expected_narrative_function"),
            "primary_correct": primary_correct,
            "final_correct": final_correct if row.get("valid") is not None else None,
            "classification": category,
        })
    helpful = counts["helpful_override"]
    harmful = counts["harmful_override"]
    return {
        "schema": "sfh2-a2ovb-override-value-analysis-v1",
        "boundary_case_count": sum(counts.values()),
        "counts": dict(sorted(counts.items())),
        "helpful_override_count": helpful,
        "harmful_override_count": harmful,
        "net_boundary_gain": helpful - harmful,
        "records": result,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _damage_audit(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    records = []
    for row in evaluation["records"]:
        if row.get("primary_narrative_function_correct") is True:
            records.append({
                "case_id": row.get("case_id"),
                "boundary_cohort": row.get("boundary_cohort"),
                "primary_function": row.get("primary_function"),
                "boundary_judgment": row.get("boundary_judgment"),
                "final_function": row.get("final_function"),
                "expected_function": row.get("expected_narrative_function"),
                "primary_correct": True,
                "final_correct": row.get("final_narrative_function_correct"),
                "harmful": row.get("final_narrative_function_correct") is False,
            })
    return {
        "schema": "sfh2-a2ovb-damage-audit-v1",
        "baseline_correct_case_count": len(records),
        "harmful_override_count": sum(row["harmful"] for row in records),
        "records": records,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _residual_recovery(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    records = []
    for row in evaluation["records"]:
        if row.get("primary_narrative_function_correct") is False:
            records.append({
                "case_id": row.get("case_id"),
                "surface": row.get("surface"),
                "exact_occurrence_key": copy.deepcopy(row.get("exact_occurrence_key")),
                "primary_function": row.get("primary_function"),
                "boundary_judgment": row.get("boundary_judgment"),
                "final_function": row.get("final_function"),
                "gold_function": row.get("expected_narrative_function"),
                "recovered": row.get("final_narrative_function_correct") is True,
                "confidence": row.get("validator_confidence"),
                "reason": row.get("validator_reason_summary"),
            })
    return {
        "schema": "sfh2-a2ovb-residual-recovery-v1",
        "primary_error_count": len(records),
        "recovered_count": sum(row["recovered"] for row in records),
        "records": records,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _historical_trajectory(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    a2o = by_case(read_json(A2O_ROOT / "occurrence-results.json", {}))
    a2or = by_case(read_json(A2OR_ROOT / "evaluation.json", {}))
    a2ov = by_case(read_json(A2OV_ROOT / "reviewer-final-results.json", {}))
    records = []
    for row in evaluation["records"]:
        if row.get("primary_narrative_function_correct") is not False:
            continue
        case_id = text(row.get("case_id"))
        a2o_result = a2o.get(case_id, {}).get("occurrence_result") if isinstance(a2o.get(case_id), Mapping) else {}
        a2or_result = a2or.get(case_id, {})
        a2ov_result = a2ov.get(case_id, {})
        a2ov_final = a2ov_result.get("final_semantic") if isinstance(a2ov_result, Mapping) else {}
        records.append({
            "case_id": case_id,
            "surface": row.get("surface"),
            "exact_occurrence_key": copy.deepcopy(row.get("exact_occurrence_key")),
            "a2o_v1_function": a2o_result.get("narrative_function") if isinstance(a2o_result, Mapping) else None,
            "a2or_v2_function": (a2or_result.get("predicted_narrative_function") or a2or_result.get("final_function")) if isinstance(a2or_result, Mapping) else None,
            "a2ov_reviewer_decision": a2ov_result.get("reviewer_decision") if isinstance(a2ov_result, Mapping) else None,
            "a2ov_final_function": a2ov_final.get("narrative_function") if isinstance(a2ov_final, Mapping) else None,
            "a2ovb_boundary_judgment": row.get("boundary_judgment"),
            "a2ovb_final_function": row.get("final_function"),
            "gold_function": row.get("expected_narrative_function"),
            "recovered": row.get("final_narrative_function_correct") is True,
        })
    return {
        "schema": "sfh2-a2ovb-historical-trajectory-v1",
        "post_inference_residual_case_count": len(records),
        "records": records,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _confidence_analysis(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    distributions: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in evaluation["records"]:
        confidence = text(row.get("validator_confidence")) or "not_called"
        outcome = "helpful" if row.get("primary_narrative_function_correct") is False and row.get("final_narrative_function_correct") is True else "harmful" if row.get("primary_narrative_function_correct") is True and row.get("final_narrative_function_correct") is False else "unchanged_correct" if row.get("final_narrative_function_correct") is True else "wrong_or_unresolved"
        distributions[confidence][outcome] += 1
    return {
        "schema": "sfh2-a2ovb-confidence-analysis-v1",
        "validator_confidence_outcomes": {key: dict(value) for key, value in sorted(distributions.items())},
        "threshold_not_selected": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _recommendation(evaluation: Mapping[str, Any], boundary_eval: Mapping[str, Any], value: Mapping[str, Any], transport: Mapping[str, Any], safety: Mapping[str, Any]) -> dict[str, Any]:
    metrics = evaluation["metrics"]
    residual = _residual_recovery(evaluation)
    final_accuracy = metrics["final_narrative_function"].get("accuracy") or 0
    damage = value.get("harmful_override_count", 0)
    helpful = value.get("helpful_override_count", 0)
    transport_ok = (
        transport.get("provider_failures", 0) == 0
        and transport.get("invalid_payloads", 0) == 0
        and transport.get("truncations", 0) == 0
        and transport.get("schema_probe_calls") == 1
        and transport.get("boundary_validator_calls") == transport.get("expected_boundary_validator_calls")
        and (
            transport.get("parsed_calls") == transport.get("provider_calls")
            if transport.get("live") is True
            else transport.get("parsed_calls") == transport.get("expected_boundary_validator_calls", 0) + 1
        )
    )
    all_residuals_recovered = residual["primary_error_count"] > 0 and residual["recovered_count"] == residual["primary_error_count"]
    base_safety = safety.get("canonical_writes") == 0 and safety.get("identity_replacements") == 0 and safety.get("provenance_replacements") == 0 and safety.get("name_specific_python_semantic_rules") == 0
    qualified = (
        transport_ok
        and metrics["valid_boundary_records"] == len([row for row in evaluation["records"] if row.get("boundary_cohort")])
        and final_accuracy == 1.0
        and metrics["provenance"].get("accuracy") == 1.0
        and metrics["identity_preservation"].get("accuracy") == 1.0
        and evaluation["by_cohort"].get("reviewed_role", {}).get("final_narrative_function", {}).get("accuracy") == 1.0
        and metrics["annotation_to_scene_collapse"] == 0
        and damage == 0
        and all_residuals_recovered
        and base_safety
    )
    promising = (
        transport_ok
        and metrics["valid_boundary_records"] == len([row for row in evaluation["records"] if row.get("boundary_cohort")])
        and final_accuracy >= 25 / 26
        and metrics["provenance"].get("accuracy") == 1.0
        and metrics["identity_preservation"].get("accuracy") == 1.0
        and evaluation["by_cohort"].get("reviewed_role", {}).get("final_narrative_function", {}).get("accuracy") == 1.0
        and metrics["annotation_to_scene_collapse"] == 0
        and damage == 0
        and helpful >= 1
        and base_safety
    )
    if not transport_ok:
        recommendation = "sfh2_occurrence_boundary_validator_transport_failure"
        next_stage = "repair A2OVB transport before semantic conclusion"
    elif damage > 0:
        recommendation = "sfh2_occurrence_boundary_validator_causes_damage"
        next_stage = "redesign conservative boundary validation before scaling"
    elif qualified:
        recommendation = "sfh2_occurrence_boundary_validator_qualified"
        next_stage = "SFH2.2-F-prep"
    elif promising:
        recommendation = "sfh2_occurrence_boundary_validator_promising"
        next_stage = "SFH2.2-A2OVX"
    elif helpful == 0:
        recommendation = "sfh2_occurrence_same_model_boundary_unresolved"
        next_stage = "SFH2.2-A2OVX"
    else:
        recommendation = "sfh2_occurrence_same_model_boundary_unresolved"
        next_stage = "SFH2.2-A2OVX"
    return {
        "schema": "sfh2-a2ovb-recommendation-v1",
        "recommendation": recommendation,
        "qualified": qualified,
        "next_stage": next_stage,
        "boundary_accuracy": boundary_eval.get("accuracy"),
        "criteria": {
            "all_boundary_records_valid": transport_ok and metrics["valid_boundary_records"] == len([row for row in evaluation["records"] if row.get("boundary_cohort")]),
            "provenance_100_percent": metrics["provenance"].get("accuracy") == 1.0,
            "identity_preserved_100_percent": metrics["identity_preservation"].get("accuracy") == 1.0,
            "six_reviewed_cases_6_of_6": evaluation["by_cohort"].get("reviewed_role", {}).get("final_narrative_function", {}).get("accuracy") == 1.0,
            "final_at_least_25_of_26": final_accuracy >= 25 / 26,
            "harmful_overrides_zero": damage == 0,
            "at_least_one_residual_recovered": helpful >= 1,
            "both_residuals_recovered": all_residuals_recovered,
            "annotation_main_text_collapse_zero": metrics["annotation_to_scene_collapse"] == 0,
            "candidate_only_safety": base_safety,
            "transport_valid": transport_ok,
        },
        "primary_error_count": residual["primary_error_count"],
        "recovered_count": residual["recovered_count"],
        "helpful_override_count": helpful,
        "harmful_override_count": damage,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _metrics(evaluation: Mapping[str, Any], boundary_eval: Mapping[str, Any], value: Mapping[str, Any], transport: Mapping[str, Any], recommendation: Mapping[str, Any]) -> dict[str, Any]:
    a2ov_document = read_json(A2OV_ROOT / "evaluation.json", {}) or {}
    a2ov_metrics = a2ov_document.get("metrics", {}).get("final_narrative_function") if isinstance(a2ov_document, Mapping) else None
    if not isinstance(a2ov_metrics, Mapping):
        a2ov_metrics = {}
    return {
        "schema": "sfh2-a2ovb-metrics-v1",
        "boundary_cohort": {
            "case_count": boundary_eval.get("cohort_count"),
            "valid_records": boundary_eval.get("valid_records"),
            "accuracy": boundary_eval.get("accuracy"),
            "prediction_counts": boundary_eval.get("prediction_counts"),
        },
        "a2or_primary": evaluation["metrics"]["primary_narrative_function"],
        "a2ov_reviewer_final_frozen_baseline": {**dict(a2ov_metrics), "source": "data/generated/sfh2-a2ov/evaluation.json"},
        "a2ovb_final": evaluation["metrics"]["final_narrative_function"],
        "a2ovb_final_legacy_role": evaluation["metrics"]["final_legacy_role"],
        "provenance": evaluation["metrics"]["provenance"],
        "identity_preservation": evaluation["metrics"]["identity_preservation"],
        "helpful_overrides": value.get("helpful_override_count"),
        "harmful_overrides": value.get("harmful_override_count"),
        "net_boundary_gain": value.get("net_boundary_gain"),
        "provider": {key: transport.get(key) for key in ("provider_calls", "provider_attempts", "schema_probe_calls", "boundary_validator_calls", "non_boundary_calls", "parsed_calls", "provider_failures", "invalid_payloads", "truncations", "retries", "prompt_tokens", "completion_tokens", "total_tokens", "median_latency_seconds", "max_latency_seconds")},
        "recommendation": recommendation.get("recommendation"),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _storage_safety(boundary_rows: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    forbidden = {"identity", "referent", "canonical_hint", "semantic_kind", "occurrence_role", "provenance_layer", "relations"}
    leaks = sum(bool(forbidden.intersection((row.get("validator_result") or {}).keys())) for row in boundary_rows.values())
    return {
        "schema": "sfh2-a2ovb-storage-safety-v1",
        "production_person_creations": 0,
        "canonical_writes": 0,
        "alias_mutations": 0,
        "profile_mutations": 0,
        "identity_replacements": 0,
        "provenance_replacements": 0,
        "retrieval_candidate_identity_gating": 0,
        "substring_identity_creation": 0,
        "related_person_unsafe_promotion": 0,
        "attribute_as_person_unsafe_promotion": 0,
        "collective_as_person_unsafe_promotion": 0,
        "name_specific_python_semantic_rules": 0,
        "surface_specific_role_rules": 0,
        "identity_or_provenance_output_leaks": leaks,
        "candidate_only": True,
        "canonical_write_back": False,
        "protected_hashes": protected_hashes(),
    }


def _write_derived(output: Path, bundle: Mapping[str, Any], boundary_rows: Mapping[str, Mapping[str, Any]], transport: Mapping[str, Any]) -> dict[str, Any]:
    finals = [_final_row(case_id, bundle, boundary_rows) for case_id in bundle["case_ids"]]
    boundary_eval, evaluation = _evaluate(bundle, boundary_rows, finals)
    value = _override_value(evaluation)
    safety = _storage_safety(boundary_rows)
    recommendation = _recommendation(evaluation, boundary_eval, value, transport, safety)
    write_json(output / "final-results.json", {
        "schema": "sfh2-a2ovb-final-results-v1",
        "case_count": len(finals),
        "records": finals,
        "mechanical_finalization": {
            "event_participant": "copy frozen A2OR primary and replace only narrative_function with participant",
            "referential_only": "copy frozen A2OR primary and replace only narrative_function with reference",
            "uncertain": "deepcopy frozen A2OR primary unchanged",
            "non_boundary": "deepcopy frozen A2OR primary unchanged",
        },
        "candidate_only": True,
        "canonical_write_back": False,
    })
    write_json(output / "boundary-evaluation.json", boundary_eval)
    write_json(output / "full-evaluation.json", evaluation)
    write_json(output / "override-value-analysis.json", value)
    write_json(output / "damage-audit.json", _damage_audit(evaluation))
    write_json(output / "residual-recovery.json", _residual_recovery(evaluation))
    write_json(output / "historical-trajectory.json", _historical_trajectory(evaluation))
    write_json(output / "confidence-analysis.json", _confidence_analysis(evaluation))
    write_json(output / "metrics.json", _metrics(evaluation, boundary_eval, value, transport, recommendation))
    write_json(output / "recommendation.json", recommendation)
    write_json(output / "storage-safety-audit.json", safety)
    write_json(output / "provider-accounting.json", transport)
    write_json(output / "validation-summary.json", {
        "schema": "sfh2-a2ovb-validation-summary-v1",
        "stage": "SFH2.2-A2OVB",
        "case_count": CASE_COUNT,
        "boundary_cohort_count": boundary_eval.get("cohort_count"),
        "provider_calls": transport.get("provider_calls", 0),
        "valid_boundary_records": boundary_eval.get("valid_records"),
        "valid_final_records": evaluation["metrics"]["final_narrative_function"].get("evaluable"),
        "gold_loaded_after_provider_inference": True,
        "a2or_primary_reused": True,
        "new_primary_provider_calls": 0,
        "candidate_only": True,
        "canonical_write_back": False,
        "recommendation": recommendation.get("recommendation"),
    })
    return {"finals": finals, "boundary_evaluation": boundary_eval, "evaluation": evaluation, "value": value, "safety": safety, "recommendation": recommendation}


def _write_basic_preflight_failure(output: Path, bundle: Mapping[str, Any], tool: Mapping[str, Any], probe_row: Mapping[str, Any], probe_valid: bool, errors: list[str]) -> None:
    write_json(output / "provider-preflight.json", {
        "schema": "sfh2-a2ovb-provider-preflight-v1",
        "stage": "SFH2.2-A2OVB",
        "model": MODEL,
        "temperature": TEMPERATURE,
        "thinking": dict(THINKING),
        "tool_function": FUNCTION_NAME,
        "schema_validated_locally": not validate_deepseek_strict_schema(tool["function"]["parameters"]),
        "result": _stable_transport(probe_row),
        "valid": False,
        "provider_schema_accepted": probe_row.get("valid") is True,
        "local_contract_valid": probe_valid,
        "errors": errors,
        "candidate_only": True,
        "canonical_write_back": False,
    })


def run(*, live: bool, output: Path = OUT, run_id: str = "sfh2-a2ovb-live-v1") -> dict[str, Any]:
    bundle = load_frozen_bundle()
    output.mkdir(parents=True, exist_ok=True)
    tool = boundary_tool()
    _write_preparation(output, bundle, tool)
    boundary_ids = boundary_case_ids(bundle)
    transport_rows: list[dict[str, Any]] = []
    if live:
        client = BoundaryClient(live=True, tool=tool)
        probe_payload, probe_row = client.probe(probe_messages())
        probe_validation = validate_probe_payload(probe_payload)
        probe_row["local_contract_valid"] = probe_validation.get("valid") is True
        transport_rows.append(probe_row)
        write_json(output / "provider-preflight.json", {
            "schema": "sfh2-a2ovb-provider-preflight-v1",
            "stage": "SFH2.2-A2OVB",
            "attempts": 1,
            "model": MODEL,
            "temperature": TEMPERATURE,
            "thinking": dict(THINKING),
            "tool_function": FUNCTION_NAME,
            "schema_validated_locally": not validate_deepseek_strict_schema(tool["function"]["parameters"]),
            "result": _stable_transport(probe_row),
            "valid": probe_row.get("valid") is True and probe_row.get("local_contract_valid") is True,
            "provider_schema_accepted": probe_row.get("valid") is True,
            "probe_fixture_semantic_conditionals_checked": False,
            "candidate_only": True,
            "canonical_write_back": False,
        })
        if probe_row.get("valid") is not True or probe_row.get("local_contract_valid") is not True:
            transport = summarize(transport_rows, live=True, provider_attempts=client.attempts, boundary_count=len(boundary_ids))
            write_json(output / "provider-accounting.json", transport)
            _write_basic_preflight_failure(output, bundle, tool, probe_row, probe_validation.get("valid") is True, probe_validation.get("errors", []))
            write_json(output / "recommendation.json", {
                "schema": "sfh2-a2ovb-recommendation-v1",
                "recommendation": "sfh2_occurrence_boundary_validator_transport_failure",
                "qualified": False,
                "next_stage": "repair A2OVB transport before semantic conclusion",
                "provider_calls": client.attempts,
                "candidate_only": True,
                "canonical_write_back": False,
            })
            raise RuntimeError("sfh2_a2ovb_provider_probe_failed")
        boundary_rows: dict[str, dict[str, Any]] = {}
        packet_map = {row["case_id"]: row["provider_payload"] for row in _boundary_packets(bundle)["records"]}
        for case_id in boundary_ids:
            response, row = client.call(case_id=case_id, system=HISTORIAN_SYSTEM, payload=packet_map[case_id])
            transport_rows.append(row)
            result = _result_row(case_id, bundle["packets"][case_id], response, row)
            result["cohort"] = bundle["primary_rows"][case_id].get("cohort")
            result["primary_function_for_routing_only"] = primary_function(bundle["primary_rows"][case_id])
            boundary_rows[case_id] = result
        transport = summarize(transport_rows, live=True, provider_attempts=client.attempts, boundary_count=len(boundary_ids))
    else:
        source = read_json(OUT / "boundary-results.json", {}) or {}
        cached = by_case(source)
        if set(cached) != set(boundary_ids):
            raise RuntimeError("sfh2_a2ovb_offline_boundary_result_case_set_changed")
        boundary_rows = cached
        source_transport = read_json(OUT / "provider-accounting.json", {}) or {}
        transport = copy.deepcopy(source_transport)
        transport["live"] = False
        transport["provider_calls"] = 0
        transport["provider_attempts"] = 0
        transport["new_provider_calls"] = 0
        transport["offline_replay"] = True
        source_preflight = read_json(OUT / "provider-preflight.json", {}) or {}
        write_json(output / "provider-preflight.json", {
            "schema": "sfh2-a2ovb-provider-preflight-v1",
            "stage": "SFH2.2-A2OVB",
            "source": "cached live probe",
            "valid": source_preflight.get("valid") is True,
            "offline_replay": True,
            "new_provider_calls": 0,
            "candidate_only": True,
            "canonical_write_back": False,
        })
    write_json(output / "boundary-results.json", {
        "schema": "sfh2-a2ovb-boundary-results-v1",
        "case_count": len(boundary_rows),
        "records": [copy.deepcopy(boundary_rows[case_id]) for case_id in boundary_ids],
        "primary_cache_reused_for_routing": True,
        "primary_not_sent_to_provider": True,
        "gold_not_sent_to_provider": True,
        "residual_error_labels_not_sent_to_provider": True,
        "candidate_only": True,
        "canonical_write_back": False,
    })
    documents = _write_derived(output, bundle, boundary_rows, transport)
    return {"bundle": bundle, "boundary_rows": boundary_rows, "transport": transport, **documents}
