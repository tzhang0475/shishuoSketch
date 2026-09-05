#!/usr/bin/env python3
"""Run or replay the bounded SFH2.2-F1RT transport experiment.

``--live`` is the only mode that can contact DeepSeek.  ``--offline`` reads
the compact artifacts produced by a live run and performs deterministic
replay checks without any provider call.
"""

from __future__ import annotations

import argparse
import copy
import json
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from sfh2_a0 import pipeline as a0_pipeline
from sfh2_a0 import schemas as a0_schemas
from sfh2_a0r import pipeline as a0r_pipeline
from sfh2_a2 import pipeline as a2_pipeline
from sfh2_a2.comparison import compare_records
from sfh2_a2r import pipeline as a2r_pipeline
from sfh2_a2r import contracts as a2r_contracts
from sfh2_a2ovb import common as a2ovb_common
from sfh2_a2ovb import contracts as a2ovb_contracts
from sfh2_a2ovb import prompt as a2ovb_prompt

from sfh2_f1rt import common
from sfh2_f1rt.transport import F1RTClient


def _now_hashable(value: Any) -> str:
    return common.stable_hash(value)


def _record(row: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if isinstance(row, Mapping) and row.get("valid") is True and isinstance(row.get("record"), Mapping):
        return row["record"]
    return None


def _git_state() -> dict[str, Any]:
    def run(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=common.ROOT, text=True).strip()

    return {
        "branch": run("branch", "--show-current"),
        "head": run("rev-parse", "HEAD"),
        "origin_main": run("rev-parse", "origin/main"),
    }


def _assert_baseline() -> dict[str, Any]:
    state = _git_state()
    if state["branch"] != "main":
        raise RuntimeError("f1rt_requires_main_branch")
    if state["head"] != common.BASELINE_COMMIT:
        raise RuntimeError("f1rt_head_mismatch:" + state["head"])
    if state["origin_main"] != common.BASELINE_COMMIT:
        raise RuntimeError("f1rt_origin_main_mismatch:" + state["origin_main"])
    return state


def _assert_no_leakage(payload: Mapping[str, Any], *, allow_case: bool = True, allow_semantic_hypotheses: bool = False) -> None:
    """Check packet field names, not Chinese text, for authority leakage."""

    forbidden_keys = {
        "gold", "gold_record", "expected_gold", "human_answer", "f1rp_human_answer",
        "residual_error_labels", "historical_error_class", "a2ov_review_decision",
        "primary_narrative_function", "primary_confidence", "primary_reason_summary",
    }
    if not allow_semantic_hypotheses:
        forbidden_keys.add("occurrence_role")
    if not allow_case:
        forbidden_keys.add("case_id")
    stack: list[Mapping[str, Any]] = [payload]
    while stack:
        current = stack.pop()
        for key, value in current.items():
            if str(key).lower() in forbidden_keys:
                raise RuntimeError("f1rt_provider_packet_leakage:" + str(key))
            if isinstance(value, Mapping):
                stack.append(value)
            elif isinstance(value, list):
                stack.extend(item for item in value if isinstance(item, Mapping))


def _request_material(bundle: Mapping[str, Any], row: Mapping[str, Any]) -> dict[str, Any]:
    material = common.failure_request_material(bundle, row)
    if not material["original_request_hash_matches"]:
        raise RuntimeError("f1rt_original_request_hash_mismatch:" + text(row.get("occurrence_id")) + ":" + text(row.get("stage")))
    _assert_no_leakage(material["payload"])
    return material


def text(value: Any) -> str:
    return str(value or "").strip()


def _architecture(bundle: Mapping[str, Any], inventory: Mapping[str, Any], body_schema: Mapping[str, Any], state: Mapping[str, Any]) -> dict[str, Any]:
    old_tools = common.old_contracts()
    return {
        "schema": "sfh2-f1rt-architecture-v1",
        "stage": "SFH2.2-F1RT",
        "baseline_commit": common.BASELINE_COMMIT,
        "git_state_at_start": dict(state),
        "purpose": "bounded structured-output recovery qualification; semantic architecture remains frozen",
        "arms": {
            "arm_a": {"name": "exact_replay", "semantic_prompt_unchanged": True, "contract": "historical full semantic record contract", "recovery_attempt": "exact_replay_1"},
            "arm_b": {"name": "semantic_body_transport_v2", "semantic_prompt_unchanged": True, "contract": common.BODY_CONTRACT_VERSION, "python_owns_envelope": True},
        },
        "frozen_semantic_components": {
            "identity_primary_prompt_version": "sfh2-a0r-primary-historian-v1",
            "identity_independent_prompt_version": "sfh2-a2-independent-historian-v1",
            "identity_adjudication_prompt_version": "sfh2-a2r-adjudicator-v2",
            "model": common.MODEL,
            "temperature": common.TEMPERATURE,
            "thinking": dict(common.THINKING),
            "endpoint": common.ENDPOINT,
            "semantic_schema_hash": common.stable_hash(old_tools["identity_primary"]),
            "semantic_body_schema_hash": body_schema["primary_tool_hash"],
        },
        "identity_semantic_fields_unchanged": sorted(set(a0_schemas.semantic_record_schema()["properties"]) - {"mention_id", "surface"}),
        "python_owned_immutable_envelope": list(common.BODY_ENVELOPE_FIELDS),
        "qualified_identity_reconstruction": "existing A2R comparison/adjudication policy; no identity shortcut",
        "boundary_failure_scope": "剌史 is transport-only because F1RP human semantic authority outranks replay output",
        "excluded": ["A2OR occurrence semantics", "A2OVB semantic rerun", "F1/F2 production", "canonical promotion", "Gold/human authority input"],
        "historical_invalid_stage_units": inventory["full_invalid_stage_unit_count"],
        "source_hashes": common.source_hashes(bundle),
        "code_hashes": common.code_hashes(),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _arm_a_selection(bundle: Mapping[str, Any], inventory: Mapping[str, Any]) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    materials: dict[tuple[str, str], dict[str, Any]] = {}
    for row in inventory["records"]:
        material = _request_material(bundle, row)
        key = (text(row.get("occurrence_id")), text(row.get("stage")))
        materials[key] = material
        records.append({
            "occurrence_id": text(row.get("occurrence_id")),
            "stage": text(row.get("stage")),
            "exact_occurrence_key": copy.deepcopy(row["exact_occurrence_key"]),
            "failure_class": row.get("failure_class"),
            "recovery_class_original": row.get("recovery_class"),
            "original_request_hash": material["original_request_hash_stored"],
            "recovery_request_hash": common.recovery_request(material["original_request_hash_stored"], material["payload"]),
            "recovery_attempt": "exact_replay_1",
            "semantic_prompt_unchanged": True,
            "provider_packet_hash": common.stable_hash(material["payload"]),
            "one_semantic_replay_maximum": True,
        })
    return {
        "schema": "sfh2-f1rt-arm-a-exact-replay-selection-v1",
        "selection_rule": "all and only the 15 historical invalid stage units retained by F1R; exactly one semantic recovery replay per unit",
        "stage_unit_count": len(records),
        "records": records,
        "candidate_only": True,
        "canonical_write_back": False,
    }, materials


def _identity_body_selection(bundle: Mapping[str, Any], control_doc: Mapping[str, Any], inventory: Mapping[str, Any]) -> dict[str, Any]:
    invalid = [
        {
            "occurrence_id": text(row.get("occurrence_id")),
            "stage": text(row.get("stage")),
            "exact_occurrence_key": copy.deepcopy(row["exact_occurrence_key"]),
            "failure_class": row.get("failure_class"),
            "recovery_attempt": "semantic_body_transport_v2",
        }
        for row in inventory["records"]
        if text(row.get("stage")).startswith("identity_")
    ]
    controls = []
    for item in control_doc["records"]:
        case = item["case"]
        controls.append({
            "occurrence_id": text(item["occurrence_id"]),
            "exact_occurrence_key": common.exact_key(case),
            "identity_form_category": item["identity_form_category"],
            "selection_basis": item["selection_basis"],
        })
    return {
        "schema": "sfh2-f1rt-arm-b-selection-v1",
        "invalid_identity_stage_unit_count": len(invalid),
        "invalid_identity_stage_units": invalid,
        "control_count": len(controls),
        "controls": controls,
        "provider_packet_gold_blind": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _body_request(material: Mapping[str, Any], stage: str, tool: Mapping[str, Any], function_name: str) -> str:
    return common.stable_hash({
        "stage": stage,
        "prompt_version": common.BODY_CONTRACT_VERSION,
        "model": common.MODEL,
        "temperature": common.TEMPERATURE,
        "thinking": common.THINKING,
        "endpoint": common.ENDPOINT,
        "function_name": function_name,
        "system": material["system"],
        "payload": material["payload"],
        "tool": tool,
        "transport_contract": common.BODY_CONTRACT_VERSION,
    })


def _terminal_row(bundle: Mapping[str, Any], occurrence_id: str, stage: str, raw_row: Mapping[str, Any], transport: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    case = bundle["cases"][occurrence_id]
    packet = bundle["packets"][occurrence_id]
    return common.identity_result_from_body(case, packet, raw_row, transport, inputs, stage)


def _run_arm_a(bundle: Mapping[str, Any], inventory: Mapping[str, Any], materials: Mapping[tuple[str, str], Mapping[str, Any]], client: F1RTClient) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for item in inventory["records"]:
        occurrence_id = text(item.get("occurrence_id"))
        stage = text(item.get("stage"))
        material = materials[(occurrence_id, stage)]
        request_hash = common.recovery_request(material["original_request_hash_stored"], material["payload"])
        case = bundle["cases"][occurrence_id]
        packet = bundle["packets"][occurrence_id]
        raw, transport = client.call(
            stage=stage,
            unit_id="arm_a:" + stage + ":" + occurrence_id,
            system=material["system"],
            payload=material["payload"],
            tool=material["tool"],
            function_name=material["function_name"],
            prompt_version=material["prompt_version"],
            request_hash=request_hash,
            max_tokens=400 if stage == "boundary_validator" else 2600,
            attempt_class="exact_replay_1",
        )
        if stage == "boundary_validator":
            context_packet = common.attach_identity_context(packet, bundle["identity_results"][occurrence_id])
            validation = a2ovb_contracts.validate_boundary_payload(a2ovb_common.provider_payload(context_packet), raw)
            valid = validation.get("valid") is True
            row = {
                "case_id": text(case.get("case_id")), "occurrence_id": occurrence_id, "stage": stage,
                "valid": valid, "contract_status": "valid" if valid else "boundary_contract_invalid",
                "boundary_result": copy.deepcopy(validation.get("result")) if valid else None,
                "errors": sorted(set(validation.get("errors", []))),
                "transport": copy.deepcopy(transport),
                "candidate_only": True, "canonical_write_back": False,
            }
        else:
            row = common.identity_result_from_full(case, packet, raw, transport, bundle["inputs"], stage)
        row.update({
            "original_failure_class": item.get("failure_class"),
            "original_recovery_class": item.get("recovery_class"),
            "original_request_hash": material["original_request_hash_stored"],
            "recovery_request_hash": request_hash,
            "replay_transport_success": transport.get("classification") in {"parsed", "response_truncated"},
            "replay_parse_success": transport.get("classification") == "parsed",
            "replay_contract_valid": valid if stage == "boundary_validator" else row.get("valid") is True,
            "replay_semantic_record_available": (row.get("valid") is True and (stage == "boundary_validator" or isinstance(row.get("record"), Mapping))),
            "recovery_attempt": "exact_replay_1",
        })
        results.append(row)
        by_key[(occurrence_id, stage)] = row
    return {
        "schema": "sfh2-f1rt-arm-a-results-v1",
        "records": results,
        "logical_replay_count": len(results),
        "valid_contract_count": sum(row.get("replay_contract_valid") is True for row in results),
        "recovery_rate": round(sum(row.get("replay_contract_valid") is True for row in results) / len(results), 6) if results else 0,
        "by_failure_class": _failure_recovery_counts(results),
        "candidate_only": True,
        "canonical_write_back": False,
    }, by_key


def _failure_recovery_counts(rows_: list[Mapping[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for failure_class in common.FAILURE_CLASSES:
        selected = [row for row in rows_ if text(row.get("original_failure_class")) == failure_class]
        if selected:
            result[failure_class] = {
                "units": len(selected),
                "valid_recoveries": sum(row.get("replay_contract_valid") is True for row in selected),
                "recovery_rate": round(sum(row.get("replay_contract_valid") is True for row in selected) / len(selected), 6),
            }
    return result


def _run_body_call(
    *,
    bundle: Mapping[str, Any],
    occurrence_id: str,
    stage: str,
    material: Mapping[str, Any],
    tool: Mapping[str, Any],
    function_name: str,
    client: F1RTClient,
    arm_label: str,
    attempt_class: str,
) -> dict[str, Any]:
    case = bundle["cases"][occurrence_id]
    packet = bundle["packets"][occurrence_id]
    request_hash = _body_request(material, stage, tool, function_name)
    raw, transport = client.call(
        stage=stage,
        unit_id=arm_label + ":" + stage + ":" + occurrence_id,
        system=material["system"],
        payload=material["payload"],
        tool=tool,
        function_name=function_name,
        prompt_version=common.BODY_CONTRACT_VERSION,
        request_hash=request_hash,
        max_tokens=2600,
        attempt_class=attempt_class,
    )
    row = common.identity_result_from_body(case, packet, raw, transport, bundle["inputs"], stage)
    row.update({
        "request_hash": request_hash,
        "provider_packet_hash": common.stable_hash(material["payload"]),
        "transport_contract": common.BODY_CONTRACT_VERSION,
        "python_owned_envelope": common.candidate_envelope(case, request_hash, stage, row.get("record")),
        "candidate_only": True,
        "canonical_write_back": False,
    })
    return row


def _run_arm_b(bundle: Mapping[str, Any], inventory: Mapping[str, Any], control_doc: Mapping[str, Any], materials: Mapping[tuple[str, str], Mapping[str, Any]], client: F1RTClient) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, Any]]]:
    tools = common.body_tools()
    invalid_results: list[dict[str, Any]] = []
    control_results: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for item in inventory["records"]:
        stage = text(item.get("stage"))
        if not stage.startswith("identity_"):
            continue
        occurrence_id = text(item.get("occurrence_id"))
        material = materials[(occurrence_id, stage)]
        tool = tools[stage]
        function_name = text(tool["function"]["name"])
        row = _run_body_call(
            bundle=bundle, occurrence_id=occurrence_id, stage=stage, material=material,
            tool=tool, function_name=function_name, client=client, arm_label="arm_b_invalid",
            attempt_class="semantic_body_transport_v2",
        )
        row["historical_failure_class"] = item.get("failure_class")
        row["historical_recovery_class"] = item.get("recovery_class")
        invalid_results.append(row)
        by_key[(occurrence_id, stage)] = row
    for item in control_doc["records"]:
        occurrence_id = text(item["occurrence_id"])
        case = bundle["cases"][occurrence_id]
        packet = bundle["packets"][occurrence_id]
        primary_payload, independent_payload = common.identity_payloads(packet)
        for stage, payload in (("identity_primary", primary_payload), ("identity_independent", independent_payload)):
            material = {
                "system": a0r_pipeline.PRIMARY_HISTORIAN_SYSTEM if stage == "identity_primary" else a2_pipeline.HISTORIAN_B_SYSTEM,
                "payload": payload,
            }
            _assert_no_leakage(payload)
            tool = tools[stage]
            function_name = text(tool["function"]["name"])
            row = _run_body_call(
                bundle=bundle, occurrence_id=occurrence_id, stage=stage, material=material,
                tool=tool, function_name=function_name, client=client, arm_label="arm_b_control",
                attempt_class="control_semantic_body_v2",
            )
            row["control_identity_form_category"] = item["identity_form_category"]
            control_results.append(row)
            by_key[("control:" + occurrence_id, stage)] = row
    return {
        "schema": "sfh2-f1rt-arm-b-results-v1",
        "contract": common.BODY_CONTRACT_VERSION,
        "invalid_identity_records": invalid_results,
        "control_records": control_results,
        "invalid_identity_count": len(invalid_results),
        "invalid_identity_valid_body_count": sum(row.get("valid") is True for row in invalid_results),
        "control_count": len(control_results),
        "control_valid_body_count": sum(row.get("valid") is True for row in control_results),
        "provider_owned_fields": sorted(set(a0_schemas.semantic_record_schema()["properties"]) - {"mention_id", "surface"}),
        "python_owned_envelope_fields": list(common.BODY_ENVELOPE_FIELDS),
        "candidate_only": True,
        "canonical_write_back": False,
    }, by_key


def _identity_body_record_map(arm_b: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    result = {}
    for row in arm_b.get("invalid_identity_records", []) or []:
        result[(text(row.get("occurrence_id")), text(row.get("stage")))] = row
    return result


def _adjudicate_terminal(bundle: Mapping[str, Any], occurrence_id: str, primary_row: Mapping[str, Any], independent_row: Mapping[str, Any], client: F1RTClient) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    case = bundle["cases"][occurrence_id]
    packet = bundle["packets"][occurrence_id]
    comparison = compare_records(_record(primary_row), _record(independent_row), a_valid=primary_row.get("valid") is True, b_valid=independent_row.get("valid") is True)
    needs = a2_pipeline._requires_adjudication(primary_row, independent_row, comparison)
    if not needs:
        selected = _record(primary_row)
        effective = {"valid": selected is not None, "record": copy.deepcopy(selected), "source": "historian_a_exact_copy", "errors": [], "changed_fields": []}
        row = {"stage": "identity_adjudicator", "valid": True, "contract_status": "not_run", "decision": "not_run", "candidate_only": True, "canonical_write_back": False}
        return row, {"comparison": comparison, "needs_adjudication": False, "effective": effective, "row": row}
    payload = a2r_pipeline.adjudicator_payload(packet, primary_row, independent_row, comparison)
    _assert_no_leakage(payload, allow_semantic_hypotheses=True)
    tool = a2r_contracts.adjudicator_tool()
    request_hash = common.stable_hash({
        "stage": "identity_adjudicator",
        "prompt_version": "sfh2-a2r-adjudicator-v2",
        "model": common.MODEL,
        "temperature": common.TEMPERATURE,
        "thinking": common.THINKING,
        "endpoint": common.ENDPOINT,
        "function_name": text(tool["function"]["name"]),
        "system": a2r_pipeline.ADJUDICATOR_SYSTEM,
        "payload": payload,
        "tool": tool,
        "recovery_policy_version": common.RECOVERY_POLICY_VERSION,
        "attempt_class": "terminal_identity_reconstruction",
    })
    raw, transport = client.call(
        stage="identity_adjudicator",
        unit_id="terminal_adjudicator:" + occurrence_id,
        system=a2r_pipeline.ADJUDICATOR_SYSTEM,
        payload=payload,
        tool=tool,
        function_name=text(tool["function"]["name"]),
        prompt_version="sfh2-a2r-adjudicator-v2",
        request_hash=request_hash,
        max_tokens=1800,
        attempt_class="terminal_identity_reconstruction",
    )
    adjudication_row, effective = a2r_pipeline._adjudication_row(case, packet, raw, _record(primary_row), _record(independent_row), transport)
    adjudication_row["request_hash"] = request_hash
    adjudication_row["candidate_only"] = True
    adjudication_row["canonical_write_back"] = False
    return adjudication_row, {"comparison": comparison, "needs_adjudication": True, "effective": effective, "row": adjudication_row}


def _recovered_status(effective: Mapping[str, Any]) -> str:
    record = effective.get("record") if effective.get("valid") is True else None
    if isinstance(record, Mapping):
        if record.get("abstain") is True:
            return "abstained"
        return "resolved_candidate"
    if text(effective.get("source")) in {"adjudication_abstained", "invalid_adjudication", "transport_unresolved"}:
        return "abstained" if text(effective.get("source")) == "adjudication_abstained" else "still_blocked"
    return "contract_invalid"


def _terminal_recovery(bundle: Mapping[str, Any], arm_a: Mapping[tuple[str, str], Mapping[str, Any]], arm_b: Mapping[tuple[str, str], Mapping[str, Any]], client: F1RTClient) -> dict[str, Any]:
    terminal_ids = sorted({text(row.get("occurrence_id")) for row in bundle["failure_inventory"]["records"] if row.get("recovery_class") == "terminal_identity_block"})
    records = []
    for occurrence_id in terminal_ids:
        original = bundle["identity_results"][occurrence_id]
        a = {
            "valid": arm_b.get((occurrence_id, "identity_primary"), {}).get("valid") is True,
            "record": arm_b.get((occurrence_id, "identity_primary"), {}).get("record"),
            "contract_status": arm_b.get((occurrence_id, "identity_primary"), {}).get("contract_status"),
            "errors": arm_b.get((occurrence_id, "identity_primary"), {}).get("errors", []),
            "consistency": arm_b.get((occurrence_id, "identity_primary"), {}).get("consistency", {}),
        }
        b = {
            "valid": arm_b.get((occurrence_id, "identity_independent"), {}).get("valid") is True,
            "record": arm_b.get((occurrence_id, "identity_independent"), {}).get("record"),
            "contract_status": arm_b.get((occurrence_id, "identity_independent"), {}).get("contract_status"),
            "errors": arm_b.get((occurrence_id, "identity_independent"), {}).get("errors", []),
            "consistency": arm_b.get((occurrence_id, "identity_independent"), {}).get("consistency", {}),
        }
        adj_row, adj_info = _adjudicate_terminal(bundle, occurrence_id, a, b, client)
        effective = adj_info["effective"]
        selected = effective.get("record") if effective.get("valid") else None
        realization = a0r_pipeline.realize_semantic_record(bundle["cases"][occurrence_id], selected, bundle["inputs"])
        records.append({
            "occurrence_id": occurrence_id,
            "exact_occurrence_key": common.exact_key(bundle["cases"][occurrence_id]),
            "original_primary_status": _compact_historical_stage(original.get("historian_primary")),
            "original_independent_status": _compact_historical_stage(original.get("historian_independent")),
            "original_adjudication": _compact_historical_stage(original.get("adjudication")),
            "arm_a_primary": copy.deepcopy(arm_a.get((occurrence_id, "identity_primary"))),
            "arm_a_independent": copy.deepcopy(arm_a.get((occurrence_id, "identity_independent"))),
            "arm_b_primary": copy.deepcopy(arm_b.get((occurrence_id, "identity_primary"))),
            "arm_b_independent": copy.deepcopy(arm_b.get((occurrence_id, "identity_independent"))),
            "comparison": copy.deepcopy(adj_info["comparison"]),
            "needs_adjudication_under_frozen_policy": adj_info["needs_adjudication"],
            "adjudication": copy.deepcopy(adj_row),
            "selected_record": copy.deepcopy(selected),
            "selected_record_source": effective.get("source"),
            "recovered_identity_status": _recovered_status(effective),
            "candidate_proposal": copy.deepcopy(realization.get("candidate")),
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return {
        "schema": "sfh2-f1rt-terminal-identity-recovery-v1",
        "terminal_count": len(records),
        "records": records,
        "resolved_candidate_count": sum(row.get("recovered_identity_status") == "resolved_candidate" for row in records),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _compact_historical_stage(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        return {"valid": False, "contract_status": "missing"}
    transport = row.get("transport") if isinstance(row.get("transport"), Mapping) else {}
    return {
        "valid": row.get("valid") is True,
        "contract_status": row.get("contract_status"),
        "errors": copy.deepcopy(row.get("errors", [])),
        "request_hash": transport.get("request_hash"),
        "classification": transport.get("classification"),
        "parse_error": transport.get("parse_error"),
    }


def _compare_control(historical: Mapping[str, Any] | None, prospective: Mapping[str, Any] | None, case_id: str, stage: str, source: str) -> dict[str, Any]:
    old = common.normalized_semantic(_record(historical) if historical else None)
    new = common.normalized_semantic(_record(prospective) if prospective else None)
    if old is None or new is None:
        return {"case_id": case_id, "stage": stage, "source": source, "classification": "abstain_difference" if old != new else "semantic_disagreement", "historical_valid": old is not None, "prospective_valid": new is not None, "historical": old, "prospective": new}
    old_core = common.normalized_semantic_core(_record(historical))
    new_core = common.normalized_semantic_core(_record(prospective))
    all_equal = old == new
    difference_fields = sorted(key for key in old if old.get(key) != new.get(key))
    core_difference_fields = sorted(key for key in (old_core or {}) if (old_core or {}).get(key) != (new_core or {}).get(key))
    core_equal = not core_difference_fields
    return {
        "case_id": case_id,
        "stage": stage,
        "source": source,
        "classification": "exact_semantic_match" if all_equal else "compatible_semantic_match" if core_equal else "semantic_disagreement",
        "abstain_difference": old.get("abstain") != new.get("abstain"),
        "difference_fields": difference_fields,
        "core_difference_fields": core_difference_fields,
        "comparison_core": [
            "semantic_kind", "reference_type", "referent_canonical_hint", "occurrence_role",
            "bearer_hint", "attribute_type", "attribute_value", "abstain",
        ],
        "historical": old,
        "prospective": new,
    }


def _control_comparison(bundle: Mapping[str, Any], control_doc: Mapping[str, Any], arm_b: Mapping[str, Any]) -> dict[str, Any]:
    result_rows: list[dict[str, Any]] = []
    prospective = {(text(row.get("occurrence_id")), text(row.get("stage"))): row for row in arm_b.get("control_records", []) or []}
    for item in control_doc["records"]:
        occurrence_id = text(item["occurrence_id"])
        historical = bundle["identity_results"][occurrence_id]
        for stage in ("identity_primary", "identity_independent"):
            historical_stage = historical.get("historian_primary" if stage == "identity_primary" else "historian_independent")
            result_rows.append(_compare_control(historical_stage, prospective.get((occurrence_id, stage)), occurrence_id, stage, "historical_F1_matching_stage_record_vs_semantic_body_v2"))
    counts = Counter(text(row.get("classification")) for row in result_rows)
    disagreement_families = Counter(
        ",".join(row.get("core_difference_fields") or ["unclassified_core_difference"])
        for row in result_rows
        if row.get("classification") == "semantic_disagreement"
    )
    repeated_families = {
        family: count for family, count in sorted(disagreement_families.items()) if count > 1
    }
    return {
        "schema": "sfh2-f1rt-control-semantic-comparison-v1",
        "comparison_count": len(result_rows),
        "records": result_rows,
        "counts": dict(sorted(counts.items())),
        "core_difference_families": dict(sorted(disagreement_families.items())),
        "repeated_core_difference_families": repeated_families,
        "systematic_semantic_drift": bool(repeated_families),
        "systematic_definition": "a core semantic difference family repeated across at least two control stage comparisons",
        "free_text_reason_comparison": False,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _boundary_recovery(bundle: Mapping[str, Any], arm_a: Mapping[tuple[str, str], Mapping[str, Any]]) -> dict[str, Any]:
    key = next((key for key in arm_a if key[1] == "boundary_validator"), None)
    row = arm_a.get(key) if key else None
    return {
        "schema": "sfh2-f1rt-boundary-transport-recovery-v1",
        "occurrence_id": key[0] if key else None,
        "exact_replay_performed": key is not None,
        "valid_contract": bool(row and row.get("valid") is True),
        "transport_classification": (row.get("transport") or {}).get("classification") if row else "missing",
        "boundary_result": copy.deepcopy((row or {}).get("boundary_result")),
        "human_f1rp_authority_preserved": True,
        "replay_output_has_no_semantic_authority_over_human_decision": True,
        "compact_result": copy.deepcopy(row),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _request_hashing(materials: Mapping[tuple[str, str], Mapping[str, Any]], arm_a_selection: Mapping[str, Any], arm_b: Mapping[str, Any], terminal: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    for row in arm_a_selection["records"]:
        rows.append({
            "occurrence_id": row["occurrence_id"], "stage": row["stage"], "attempt_class": "exact_replay_1",
            "original_request_hash": row["original_request_hash"], "recovery_request_hash": row["recovery_request_hash"],
            "distinct": row["original_request_hash"] != row["recovery_request_hash"],
        })
    for source_key in ("invalid_identity_records", "control_records"):
        for row in arm_b.get(source_key, []) or []:
            rows.append({
                "occurrence_id": row.get("occurrence_id"), "stage": row.get("stage"), "attempt_class": row.get("transport_contract"),
                "request_hash": row.get("request_hash"), "distinct_from_arm_a_when_overlap": all(row.get("request_hash") != item.get("recovery_request_hash") for item in arm_a_selection["records"] if item.get("occurrence_id") == row.get("occurrence_id") and item.get("stage") == row.get("stage")),
            })
    for row in terminal.get("records", []) or []:
        adj = row.get("adjudication") or {}
        if adj.get("request_hash"):
            rows.append({"occurrence_id": row.get("occurrence_id"), "stage": "identity_adjudicator", "attempt_class": "terminal_identity_reconstruction", "request_hash": adj.get("request_hash")})
    return {
        "schema": "sfh2-f1rt-prospective-request-hashing-v1",
        "normal_request_hash_components": ["stage", "prompt_version", "model", "temperature", "thinking", "endpoint", "function_name", "system", "semantic_packet", "schema"],
        "recovery_request_hash_components": ["original_semantic_request_hash", "semantic_request", "recovery_policy_version", "attempt_class"],
        "semantic_body_request_rule": "same semantic packet/system/config; new body contract/function/schema hash; Python-owned envelope is excluded from provider body",
        "records": rows,
        "all_recovery_hashes_distinct_from_original": all(item.get("distinct") is not False for item in rows if "distinct" in item),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _checkpoint_policy() -> dict[str, Any]:
    return {
        "schema": "sfh2-f1rt-prospective-checkpoint-policy-v1",
        "stable_units": ["identity:<occurrence_key>", "occurrence_primary:<occurrence_key>", "boundary:<occurrence_key>"],
        "statuses": ["valid", "invalid_terminal", "recovery_eligible", "recovery_succeeded", "recovery_failed"],
        "required_fields": ["unit_id", "request_hash", "status", "attempt", "contract_valid", "output_hash", "provider_witness_hash", "runtime_metadata"],
        "recovered_result_fields": ["original_failed_request_hash", "recovery_request_hash", "recovery_reason", "output_hash", "provider_witness_hash", "contract_valid"],
        "resume": {"matching_valid_request_hash": "reuse", "different_request_hash": "never silently reuse", "duplicate_semantic_write": "forbidden"},
        "semantic_recovery_replay_limit": 1,
        "network_retry_is_separate": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _transport_policy(body: Mapping[str, Any], controls: Mapping[str, Any], terminal: Mapping[str, Any], boundary: Mapping[str, Any], accounting: Mapping[str, Any]) -> dict[str, Any]:
    body_valid = int(body.get("invalid_identity_valid_body_count", 0)) == int(body.get("invalid_identity_count", 0))
    control_valid = int(body.get("control_valid_body_count", 0)) == int(body.get("control_count", 0))
    control_drift = int((controls.get("counts") or {}).get("semantic_disagreement", 0))
    control_systematic_drift = bool(controls.get("systematic_semantic_drift"))
    resolved = int(terminal.get("resolved_candidate_count", 0))
    terminal_count = int(terminal.get("terminal_count", 0))
    safety_clean = True
    if body_valid and control_valid and not control_systematic_drift and resolved == terminal_count and terminal_count == 3:
        status = "qualified"
        recommendation = "sfh2_transport_recovery_qualified"
        next_stage = "SFH2.2-F2-prep"
    elif control_valid and not control_systematic_drift and resolved >= 2:
        status = "promising_but_incomplete"
        recommendation = "sfh2_transport_recovery_promising_but_incomplete"
        next_stage = "SFH2.2-F1RTR"
    elif not control_valid or control_systematic_drift:
        status = "identity_transport_contract_repair_required"
        recommendation = "sfh2_identity_transport_contract_repair_required"
        next_stage = "SFH2.2-F1RTR"
    elif accounting.get("provider_failures", 0) and not body_valid:
        status = "failed"
        recommendation = "sfh2_transport_recovery_failed"
        next_stage = "SFH2.2-F1RTR"
    else:
        status = "promising_but_incomplete"
        recommendation = "sfh2_transport_recovery_promising_but_incomplete"
        next_stage = "SFH2.2-F1RTR"
    return {
        "schema": "sfh2-f1rt-transport-policy-v3-candidate",
        "status": status,
        "recommendation": recommendation,
        "next_stage": next_stage,
        "normal_provider_call": "valid -> use candidate result",
        "semantic_invalid_recovery": "one bounded semantic recovery replay; valid -> recovered_transport flag; invalid again -> terminal review block",
        "network_retry": "existing qualified transient policy, separately accounted; no nested semantic replay",
        "malformed_output": "remain invalid; no regex/prose extraction or JSON repair",
        "body_contract_v2": "qualified only if immutable envelope is Python-owned, body controls are valid, and semantic controls show no systematic drift",
        "body_valid_all_invalid_units": body_valid,
        "control_transport_valid": control_valid,
        "control_semantic_disagreement_count": control_drift,
        "control_semantic_drift_systematic": control_systematic_drift,
        "terminal_resolved_count": resolved,
        "terminal_count": terminal_count,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _terminal_metrics(terminal: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "terminal_blocks_before": 3,
        "terminal_blocks_after_still_blocked": sum(row.get("recovered_identity_status") in {"still_blocked", "contract_invalid"} for row in terminal.get("records", []) or []),
        "resolved_candidate": sum(row.get("recovered_identity_status") == "resolved_candidate" for row in terminal.get("records", []) or []),
        "abstained": sum(row.get("recovered_identity_status") == "abstained" for row in terminal.get("records", []) or []),
    }


def _metrics(
    bundle: Mapping[str, Any], inventory: Mapping[str, Any], arm_a: Mapping[str, Any], arm_b: Mapping[str, Any], controls: Mapping[str, Any], terminal: Mapping[str, Any], boundary: Mapping[str, Any], accounting: Mapping[str, Any], policy: Mapping[str, Any], protected_diff: list[str], probes: list[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": "sfh2-f1rt-metrics-v1",
        "historical": {"f1_invalid_response_payloads": 5, "full_invalid_stage_units": inventory["full_invalid_stage_unit_count"], "terminal_identity_blocks": inventory.get("terminal_identity_block_case_count", 3), "terminal_identity_block_stage_units": inventory.get("terminal_identity_block_stage_unit_count", 0)},
        "arm_a": {"calls": arm_a.get("logical_replay_count", 0), "valid_recoveries": arm_a.get("valid_contract_count", 0), "recovery_rate": arm_a.get("recovery_rate", 0), "by_failure_class": arm_a.get("by_failure_class", {})},
        "arm_b": {"invalid_identity_units_tested": arm_b.get("invalid_identity_count", 0), "valid_semantic_bodies": arm_b.get("invalid_identity_valid_body_count", 0), "invalid_unit_valid_rate": round(arm_b.get("invalid_identity_valid_body_count", 0) / arm_b.get("invalid_identity_count", 1), 6) if arm_b.get("invalid_identity_count") else 0, "control_units": arm_b.get("control_count", 0), "control_valid_bodies": arm_b.get("control_valid_body_count", 0), "control_comparison": controls.get("counts", {})},
        "terminal_recovery": _terminal_metrics(terminal),
        "boundary": {"exact_replay_valid": boundary.get("valid_contract"), "human_authority_preserved": boundary.get("human_f1rp_authority_preserved")},
        "accounting": {"probes": sum(row.get("provider_call") is True for row in probes), "provider_calls": accounting.get("provider_calls", 0), "provider_attempts": accounting.get("provider_attempts", 0), "prompt_tokens": accounting.get("prompt_tokens", 0), "completion_tokens": accounting.get("completion_tokens", 0), "total_tokens": accounting.get("total_tokens", 0), "median_latency_seconds": accounting.get("median_latency_seconds", 0), "max_latency_seconds": accounting.get("max_latency_seconds", 0), "network_retries": accounting.get("network_retries", 0), "provider_failures": accounting.get("provider_failures", 0)},
        "safety": {"canonical_writes": 0, "canonical_person_creations": 0, "semantic_authority_violations": 0, "protected_hash_mutations": protected_diff},
        "qualification": {"transport_policy_status": policy.get("status"), "recommendation": policy.get("recommendation")},
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _safety_audit(before: Mapping[str, Any], after: Mapping[str, Any], accounting: Mapping[str, Any], arm_b: Mapping[str, Any], terminal: Mapping[str, Any]) -> dict[str, Any]:
    diff = common.snapshot_diff(before, after)
    return {
        "schema": "sfh2-f1rt-safety-audit-v1",
        "canonical_writes": 0,
        "canonical_person_creation": 0,
        "candidate_person_creation": 0,
        "gold_leakage_to_provider": 0,
        "human_answer_leakage_to_provider": 0,
        "semantic_coercion_count": 0,
        "regex_or_prose_extraction_count": 0,
        "provider_envelope_overwrite_count": 0,
        "f1rp_authority_violation_count": 0,
        "protected_hash_mutations": diff,
        "protected_snapshot_digest_before": common.stable_hash(before),
        "protected_snapshot_digest_after": common.stable_hash(after),
        "protected_snapshot_entry_count": len(set(before) | set(after)),
        "all_provider_calls_candidate_only": True,
        "arm_b_body_fields_exclude_envelope": sorted(common.BODY_FORBIDDEN_PROVIDER_FIELDS),
        "terminal_candidate_outputs_candidate_only": all(row.get("candidate_only") is True and row.get("canonical_write_back") is False for row in terminal.get("records", []) or []),
        "accounting": {"provider_calls": accounting.get("provider_calls", 0)},
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _write_pre_provider(bundle: Mapping[str, Any], inventory: Mapping[str, Any], state: Mapping[str, Any], control_doc: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    body_schema = common.body_schema_document()
    architecture = _architecture(bundle, inventory, body_schema, state)
    arm_a_selection, materials = _arm_a_selection(bundle, inventory)
    body_selection = _identity_body_selection(bundle, control_doc, inventory)
    common.write_json(common.OUT / "architecture.json", architecture)
    common.write_json(common.OUT / "failure-inventory.json", inventory)
    common.write_json(common.OUT / "arm-a-exact-replay-selection.json", arm_a_selection)
    common.write_json(common.OUT / "identity-body-v2-schema.json", body_schema)
    common.write_json(common.OUT / "arm-b-control-selection.json", body_selection)
    common.write_json(common.OUT / "prospective-checkpoint-policy.json", _checkpoint_policy())
    return arm_a_selection, materials


def _write_live_outputs(
    *, bundle: Mapping[str, Any], inventory: Mapping[str, Any], architecture: Mapping[str, Any], arm_a_selection: Mapping[str, Any], arm_a: Mapping[str, Any], body_schema: Mapping[str, Any], body_selection: Mapping[str, Any], arm_b: Mapping[str, Any], controls: Mapping[str, Any], terminal: Mapping[str, Any], boundary: Mapping[str, Any], hashing: Mapping[str, Any], client: F1RTClient, protected_before: Mapping[str, Any], state: Mapping[str, Any], probes: list[Mapping[str, Any]], run_id: str,
) -> None:
    accounting = client.accounting()
    protected_after = common.protected_snapshot()
    protected_diff = common.snapshot_diff(protected_before, protected_after)
    policy = _transport_policy(arm_b, controls, terminal, boundary, accounting)
    safety = _safety_audit(protected_before, protected_after, accounting, arm_b, terminal)
    metrics = _metrics(bundle, inventory, arm_a, arm_b, controls, terminal, boundary, accounting, policy, protected_diff, probes)
    recommendation = {
        "schema": "sfh2-f1rt-recommendation-v1",
        "recommendation": policy["recommendation"],
        "next_stage": policy["next_stage"],
        "reason": "computed from semantic-body controls, terminal recovery, safety, and bounded recovery policy; historical semantic outputs remain immutable",
        "policy_status": policy["status"],
        "candidate_only": True,
        "canonical_write_back": False,
    }
    common.write_json(common.OUT / "arm-a-results.json", arm_a)
    common.write_json(common.OUT / "arm-b-results.json", arm_b)
    common.write_json(common.OUT / "control-semantic-comparison.json", controls)
    common.write_json(common.OUT / "terminal-identity-recovery.json", terminal)
    common.write_json(common.OUT / "boundary-transport-recovery.json", boundary)
    common.write_json(common.OUT / "prospective-request-hashing.json", hashing)
    common.write_json(common.OUT / "transport-policy-v3-candidate.json", policy)
    common.write_json(common.OUT / "provider-accounting.json", {**accounting, "probe_records": probes, "run_id": run_id})
    common.write_json(common.OUT / "safety-audit.json", safety)
    common.write_json(common.OUT / "metrics.json", metrics)
    common.write_json(common.OUT / "recommendation.json", recommendation)


def _stable_artifact_hashes() -> dict[str, str]:
    names = [
        "architecture.json", "failure-inventory.json", "arm-a-exact-replay-selection.json", "arm-a-results.json",
        "identity-body-v2-schema.json", "arm-b-control-selection.json", "arm-b-results.json", "control-semantic-comparison.json",
        "terminal-identity-recovery.json", "boundary-transport-recovery.json", "prospective-request-hashing.json",
        "prospective-checkpoint-policy.json", "transport-policy-v3-candidate.json", "safety-audit.json", "metrics.json", "recommendation.json",
    ]
    return {name: common.file_hash(common.OUT / name) for name in names if (common.OUT / name).is_file()}


def _refresh_derived_offline() -> None:
    """Recompute post-hoc reports from stored compact F1RT results only.

    This deliberately does not instantiate a provider client.  Arm A/Arm B
    result records and terminal adjudication are historical F1RT evidence;
    only deterministic comparison, policy, and metric projections are
    refreshed here.
    """

    bundle = common.load_bundle()
    inventory = common.failure_inventory_with_requests(bundle, common.failure_inventory(bundle))
    common.write_json(common.OUT / "failure-inventory.json", inventory)

    arm_a = common.read_json(common.OUT / "arm-a-results.json", {}) or {}
    arm_b = common.read_json(common.OUT / "arm-b-results.json", {}) or {}
    terminal = common.read_json(common.OUT / "terminal-identity-recovery.json", {}) or {}
    boundary = common.read_json(common.OUT / "boundary-transport-recovery.json", {}) or {}
    accounting = common.read_json(common.OUT / "provider-accounting.json", {}) or {}
    control_selection_doc = common.read_json(common.OUT / "arm-b-control-selection.json", {}) or {}
    expected_control_selection = common.control_selection(bundle)
    stored_controls = [
        (text(row.get("occurrence_id")), text(row.get("identity_form_category")))
        for row in control_selection_doc.get("controls", []) or []
    ]
    expected_controls = [
        (text(row.get("occurrence_id")), text(row.get("identity_form_category")))
        for row in expected_control_selection.get("records", []) or []
    ]
    if stored_controls != expected_controls:
        raise RuntimeError("f1rt_offline_control_selection_drift")

    failure_by_key = {
        (text(row.get("occurrence_id")), text(row.get("stage"))): row
        for row in inventory.get("records", []) or []
    }
    for row in arm_a.get("records", []) or []:
        failure = failure_by_key.get((text(row.get("occurrence_id")), text(row.get("stage"))))
        if failure is not None:
            # Refresh only the deterministic historical-failure labels; the
            # provider replay result and witness remain untouched.
            row["original_failure_class"] = failure.get("failure_class")
            row["original_recovery_class"] = failure.get("recovery_class")
    arm_a["by_failure_class"] = _failure_recovery_counts(arm_a.get("records", []) or [])
    arm_a_selection = common.read_json(common.OUT / "arm-a-exact-replay-selection.json", {}) or {}
    for row in arm_a_selection.get("records", []) or []:
        failure = failure_by_key.get((text(row.get("occurrence_id")), text(row.get("stage"))))
        if failure is not None:
            row["failure_class"] = failure.get("failure_class")
            row["recovery_class_original"] = failure.get("recovery_class")
    common.write_json(common.OUT / "arm-a-results.json", arm_a)
    common.write_json(common.OUT / "arm-a-exact-replay-selection.json", arm_a_selection)

    controls = _control_comparison(bundle, expected_control_selection, arm_b)
    policy = _transport_policy(arm_b, controls, terminal, boundary, accounting)
    protected_before = common.protected_snapshot()
    protected_after = common.protected_snapshot()
    protected_diff = common.snapshot_diff(protected_before, protected_after)
    probes = accounting.get("probe_records", []) if isinstance(accounting.get("probe_records"), list) else []
    safety = _safety_audit(protected_before, protected_after, accounting, arm_b, terminal)
    metrics = _metrics(
        bundle, inventory, arm_a, arm_b, controls, terminal, boundary,
        accounting, policy, protected_diff, probes,
    )
    recommendation = {
        "schema": "sfh2-f1rt-recommendation-v1",
        "recommendation": policy["recommendation"],
        "next_stage": policy["next_stage"],
        "reason": "computed offline from stored Arm A/Arm B results, terminal recovery, controls, safety, and bounded recovery policy; no provider call or historical semantic result was regenerated",
        "policy_status": policy["status"],
        "candidate_only": True,
        "canonical_write_back": False,
    }
    common.write_json(common.OUT / "control-semantic-comparison.json", controls)
    common.write_json(common.OUT / "transport-policy-v3-candidate.json", policy)
    common.write_json(common.OUT / "safety-audit.json", safety)
    common.write_json(common.OUT / "metrics.json", metrics)
    common.write_json(common.OUT / "recommendation.json", recommendation)


def offline_replay() -> int:
    required = [
        "architecture.json", "failure-inventory.json", "arm-a-results.json", "arm-b-results.json", "control-semantic-comparison.json",
        "terminal-identity-recovery.json", "boundary-transport-recovery.json", "transport-policy-v3-candidate.json", "metrics.json", "recommendation.json",
    ]
    missing = [name for name in required if not (common.OUT / name).is_file()]
    if missing:
        raise RuntimeError("f1rt_offline_replay_missing:" + ",".join(missing))
    before = common.protected_snapshot()
    _refresh_derived_offline()
    hashes = _stable_artifact_hashes()
    # Re-read and validate the stable result shapes.  No provider client is
    # instantiated and no historical result is reconstructed from raw output.
    arm_a = common.read_json(common.OUT / "arm-a-results.json", {}) or {}
    arm_b = common.read_json(common.OUT / "arm-b-results.json", {}) or {}
    terminal = common.read_json(common.OUT / "terminal-identity-recovery.json", {}) or {}
    if arm_a.get("logical_replay_count") != len(arm_a.get("records", []) or []):
        raise RuntimeError("f1rt_offline_arm_a_count_drift")
    if arm_b.get("invalid_identity_count") != len(arm_b.get("invalid_identity_records", []) or []):
        raise RuntimeError("f1rt_offline_arm_b_count_drift")
    if any(row.get("canonical_write_back") is not False for row in (arm_b.get("invalid_identity_records", []) or []) + (arm_b.get("control_records", []) or [])):
        raise RuntimeError("f1rt_offline_candidate_safety_drift")
    after = common.protected_snapshot()
    diff = common.snapshot_diff(before, after)
    replay = {
        "schema": "sfh2-f1rt-offline-replay-v1",
        "provider_calls": 0,
        "provider_attempts": 0,
        "revalidated": ["compact counts", "candidate safety", "terminal recovery shape", "protected hashes"],
        "stable_artifact_hashes": hashes,
        "protected_hash_mutations": diff,
        "deterministic": not diff,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    common.write_json(common.OUT / "offline-replay.json", replay)
    # A second offline run produces the same replay document; the result is
    # intentionally not timestamped.
    print(json.dumps(replay, ensure_ascii=False, sort_keys=True))
    return 0


def run_live(run_id: str) -> int:
    state = _assert_baseline()
    bundle = common.load_bundle()
    inventory = common.failure_inventory(bundle)
    inventory = common.failure_inventory_with_requests(bundle, inventory)
    bundle = {**bundle, "failure_inventory": inventory}
    control_doc = common.control_selection(bundle)
    protected_before = common.protected_snapshot()
    arm_a_selection, materials = _write_pre_provider(bundle, inventory, state, control_doc)
    body_schema = common.body_schema_document()
    body_selection = common.read_json(common.OUT / "arm-b-control-selection.json", {}) or {}
    old_tools = common.old_contracts()

    client = F1RTClient(live=True, run_id=run_id)
    probes: list[Mapping[str, Any]] = []
    # Each required contract family is probed once.  Probe outputs are
    # transport evidence only and never become semantic records.
    probe_specs = [
        ("probe_identity_full", old_tools["identity_primary"], text(old_tools["identity_primary"]["function"]["name"]), [{"role": "system", "content": "Return one syntactically valid full semantic-record tool result for this transport probe. Do not emit production IDs."}, {"role": "user", "content": '{"task":"contract_probe","gold_not_supplied":true}'}], 2600),
        ("probe_identity_body_v2", body_schema and body_schema["primary_tool"], BODY_FUNCTION_NAME(body_schema["primary_tool"]), [{"role": "system", "content": "Return one syntactically valid semantic-body tool result for this transport probe. Python owns routing IDs; do not emit production IDs."}, {"role": "user", "content": '{"task":"contract_probe","gold_not_supplied":true}'}], 2600),
        ("probe_boundary", old_tools["boundary_validator"], text(old_tools["boundary_validator"]["function"]["name"]), [{"role": "system", "content": "Return one syntactically valid boundary tool result for this transport probe. Do not emit identity or production fields."}, {"role": "user", "content": '{"task":"contract_probe","gold_not_supplied":true}'}], 500),
    ]
    for stage, tool, function_name, messages, max_tokens in probe_specs:
        probe_hash = common.stable_hash({"stage": stage, "model": common.MODEL, "temperature": common.TEMPERATURE, "thinking": common.THINKING, "endpoint": common.ENDPOINT, "function_name": function_name, "messages": messages, "tool": tool})
        _payload, row = client.probe(stage=stage, messages=messages, tool=tool, function_name=function_name, request_hash=probe_hash, max_tokens=max_tokens)
        probes.append(row)
        if row.get("provider_call") is True and row.get("valid") is not True:
            raise RuntimeError("f1rt_required_contract_probe_failed:" + stage)

    arm_a, arm_a_map = _run_arm_a(bundle, inventory, materials, client)
    arm_b, arm_b_map = _run_arm_b(bundle, inventory, control_doc, materials, client)
    arm_b_invalid_map = _identity_body_record_map(arm_b)
    terminal = _terminal_recovery(bundle, arm_a_map, arm_b_invalid_map, client)
    controls = _control_comparison(bundle, control_doc, arm_b)
    boundary = _boundary_recovery(bundle, arm_a_map)
    hashing = _request_hashing(materials, arm_a_selection, arm_b, terminal)
    architecture = common.read_json(common.OUT / "architecture.json", {}) or {}
    _write_live_outputs(
        bundle=bundle, inventory=inventory, architecture=architecture, arm_a_selection=arm_a_selection,
        arm_a=arm_a, body_schema=body_schema, body_selection=body_selection, arm_b=arm_b,
        controls=controls, terminal=terminal, boundary=boundary, hashing=hashing, client=client,
        protected_before=protected_before, state=state, probes=probes, run_id=run_id,
    )
    print(json.dumps({"stage": "SFH2.2-F1RT", "provider_calls": client.accounting()["provider_calls"], "recommendation": (common.read_json(common.OUT / "recommendation.json", {}) or {}).get("recommendation")}, ensure_ascii=False, sort_keys=True))
    return 0


def prepare_only() -> int:
    """Materialize the pre-provider selection/schema witness without calls."""

    state = _assert_baseline()
    bundle = common.load_bundle()
    inventory = common.failure_inventory_with_requests(bundle, common.failure_inventory(bundle))
    control_doc = common.control_selection(bundle)
    _write_pre_provider({**bundle, "failure_inventory": inventory}, inventory, state, control_doc)
    print(json.dumps({"stage": "SFH2.2-F1RT", "provider_calls": 0, "invalid_stage_units": inventory["full_invalid_stage_unit_count"], "controls": control_doc["control_count"]}, ensure_ascii=False, sort_keys=True))
    return 0


def BODY_FUNCTION_NAME(tool: Mapping[str, Any]) -> str:
    return text((tool.get("function") or {}).get("name"))


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--offline", action="store_true")
    mode.add_argument("--prepare", action="store_true")
    parser.add_argument("--run-id", default="sfh2-f1rt-live-v1")
    args = parser.parse_args()
    if args.offline:
        return offline_replay()
    if args.prepare:
        return prepare_only()
    return run_live(args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())
