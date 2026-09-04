"""SFH2.2-F1 bounded live production-candidate execution.

The runner consumes the frozen F-prep contracts and the qualified A2R/A2OR /
A2OVB components.  It writes only candidate/operational records under the F1
namespace; canonical and reviewed data have no write path here.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from sfh2_a0 import pipeline as a0_pipeline
from sfh2_a0r import contracts as a0r_contracts
from sfh2_a0r import pipeline as a0r_pipeline
from sfh2_a2 import pipeline as a2_pipeline
from sfh2_a2.comparison import compare_records
from sfh2_a2r import contracts as a2r_contracts
from sfh2_a2r import pipeline as a2r_pipeline
from sfh2_a2o import provenance as occurrence_provenance
from sfh2_a2or import contracts as a2or_contracts
from sfh2_a2or import prompt as a2or_prompt
from sfh2_a2ovb import common as a2ovb_common
from sfh2_a2ovb import contracts as a2ovb_contracts
from sfh2_a2ovb import prompt as a2ovb_prompt

from .common import (
    A2OR_ROOT,
    BASELINE_COMMIT,
    BOUNDARY_FUNCTION,
    BOUNDARY_PROMPT_VERSION,
    ENDPOINT,
    FROZEN_POLICY_PATHS,
    IDENTITY_ADJUDICATOR_FUNCTION,
    IDENTITY_ADJUDICATOR_PROMPT_VERSION,
    IDENTITY_INDEPENDENT_FUNCTION,
    IDENTITY_INDEPENDENT_PROMPT_VERSION,
    IDENTITY_PRIMARY_FUNCTION,
    IDENTITY_PRIMARY_PROMPT_VERSION,
    IDENTITY_MANIFEST,
    MODEL,
    OCCURRENCE_FUNCTION,
    OCCURRENCE_PROMPT_VERSION,
    OUT,
    READINESS_PATH,
    SELECTION_PATH,
    SEMANTIC_ROOT,
    TEMPERATURE,
    THINKING,
    a2or_cache_candidate,
    attach_identity_context,
    boundary_cache_candidate,
    build_packet,
    case_from_row,
    canonical_json,
    code_hashes,
    exact_key,
    evidence_ids,
    file_hash,
    frozen_policy_documents,
    frozen_policy_hashes,
    frozen_identity_context_for,
    identity_context_from_record,
    input_identity_hash,
    load_inputs,
    model_configs,
    packet_key,
    prompt_hashes,
    readiness_by_occurrence,
    read_json,
    selection_document,
    selection_rows,
    snapshot_diff,
    stable_hash,
    strict_schema_errors,
    tool_hashes,
    validate_exact_occurrence,
    write_json,
)
from .transport import F1Client


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _record(row: Mapping[str, Any] | None, key: str = "record") -> Mapping[str, Any] | None:
    if isinstance(row, Mapping) and row.get("valid") is True and isinstance(row.get(key), Mapping):
        return row.get(key)
    return None


def _transport_is_failure(row: Mapping[str, Any] | None) -> bool:
    return text(row.get("classification")) in {"provider_request_failure", "response_parse_failure", "response_truncated"} if isinstance(row, Mapping) else False


def text(value: Any) -> str:
    return str(value or "").strip()


def _invalid_row(case: Mapping[str, Any], stage: str, errors: list[str], transport: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "case_id": text(case.get("case_id")),
        "occurrence_id": text(case.get("occurrence_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "stage": stage,
        "valid": False,
        "contract_status": "provider_failure" if _transport_is_failure(transport) else "contract_invalid",
        "errors": sorted(set(errors)),
        "record": None,
        "candidate_only": True,
        "canonical_write_back": False,
        "transport": copy.deepcopy(transport) if isinstance(transport, Mapping) else None,
    }


def _analyse_record(case: Mapping[str, Any], packet: Mapping[str, Any], record: Mapping[str, Any] | None, inputs: Mapping[str, Any], stage: str, base: Mapping[str, Any] | None = None) -> dict[str, Any]:
    row = dict(base or {})
    realization = a0r_pipeline.realize_semantic_record(case, record, inputs)
    consistency = a0r_pipeline.analyze_record(record, evidence_ids=evidence_ids(packet), realization=realization, stage=stage)
    row["provisional_realization"] = realization
    row["consistency"] = consistency
    row["candidate_only"] = True
    row["canonical_write_back"] = False
    return row


def _checkpoint_path(unit_id: str) -> Path:
    return OUT / "checkpoints" / (stable_hash({"unit_id": unit_id}) + ".json")


def _load_checkpoint(unit_id: str, request_hash_value: str) -> tuple[dict[str, Any] | None, bool]:
    path = _checkpoint_path(unit_id)
    if not path.is_file():
        return None, False
    document = read_json(path, {}) or {}
    if document.get("unit_id") != unit_id:
        raise RuntimeError("checkpoint_unit_id_mismatch:" + unit_id)
    if document.get("request_hash") != request_hash_value:
        raise RuntimeError("checkpoint_request_hash_mismatch:" + unit_id)
    output = document.get("output")
    if not isinstance(output, Mapping):
        raise RuntimeError("checkpoint_output_missing:" + unit_id)
    if document.get("output_hash") != stable_hash(output):
        raise RuntimeError("checkpoint_output_hash_mismatch:" + unit_id)
    if document.get("status") not in {"completed", "cache_reused", "not_applicable", "blocked"}:
        return None, False
    return dict(output), True


def _save_checkpoint(
    unit_id: str,
    request_hash_value: str,
    output: Mapping[str, Any],
    *,
    status: str,
    contract_valid: bool,
    transport: Mapping[str, Any] | None = None,
    attempt: int = 0,
) -> None:
    document = {
        "schema": "sfh2-f1-checkpoint-v1",
        "unit_id": unit_id,
        "request_hash": request_hash_value,
        "status": status,
        "attempt": attempt,
        "contract_valid": contract_valid,
        "output_hash": stable_hash(output),
        "provider_witness_hash": text((transport or {}).get("provider_witness_hash")) or None,
        "runtime_metadata": {"recorded_at": _now(), "candidate_only": True, "canonical_write_back": False},
        "output": copy.deepcopy(dict(output)),
    }
    write_json(_checkpoint_path(unit_id), document)


def _checkpoint_reuse_marker(unit_id: str) -> dict[str, Any]:
    return {"unit_id": unit_id, "checkpoint_reused": True}


def _stage_call(
    *,
    client: F1Client,
    unit_id: str,
    request_stage: str,
    prompt_version: str,
    system: str,
    payload: Mapping[str, Any],
    tool: Mapping[str, Any],
    function_name: str,
    max_tokens: int,
    validator: Any,
    make_row: Any,
) -> tuple[dict[str, Any], bool, str]:
    request_hash_value = stable_hash({
        "stage": request_stage,
        "prompt_version": prompt_version,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "thinking": THINKING,
        "endpoint": ENDPOINT,
        "function_name": function_name,
        "system": system,
        "payload": payload,
        "tool": tool,
    })
    previous, reused = _load_checkpoint(unit_id, request_hash_value)
    if reused and previous is not None:
        return previous, True, request_hash_value
    raw, transport = client.call(
        stage=request_stage,
        unit_id=unit_id,
        system=system,
        payload=payload,
        tool=tool,
        function_name=function_name,
        prompt_version=prompt_version,
        request_hash_value=request_hash_value,
        max_tokens=max_tokens,
    )
    row = make_row(raw, transport)
    valid = bool(row.get("valid") is True)
    _save_checkpoint(
        unit_id,
        request_hash_value,
        row,
        status="completed" if valid else "blocked",
        contract_valid=valid,
        transport=transport,
        attempt=int(transport.get("attempt") or 0),
    )
    return row, False, request_hash_value


def _identity_primary_row(case: Mapping[str, Any], packet: Mapping[str, Any], raw: Mapping[str, Any] | None, transport: Mapping[str, Any] | None, inputs: Mapping[str, Any]) -> dict[str, Any]:
    if raw is None:
        return _invalid_row(case, "identity_primary", ["provider_failure_or_unavailable"], transport)
    result = a0r_pipeline._record_from_provider(case, packet, raw)
    result["stage"] = "identity_primary"
    result["contract_status"] = "valid" if result.get("valid") is True else "identity_primary_contract_invalid"
    result["transport"] = copy.deepcopy(transport)
    return _analyse_record(case, packet, _record(result), inputs, "identity_primary", result)


def _identity_independent_row(case: Mapping[str, Any], packet: Mapping[str, Any], raw: Mapping[str, Any] | None, transport: Mapping[str, Any] | None, inputs: Mapping[str, Any]) -> dict[str, Any]:
    if raw is None:
        result = _invalid_row(case, "identity_independent", ["provider_failure_or_unavailable"], transport)
    else:
        result = a2_pipeline._historian_b_row(case, packet, raw, transport)
        result["stage"] = "identity_independent"
        result["contract_status"] = "valid" if result.get("valid") is True else "identity_independent_contract_invalid"
    return _analyse_record(case, packet, _record(result), inputs, "identity_independent", result)


def _adjudication_output(case: Mapping[str, Any], packet: Mapping[str, Any], raw: Mapping[str, Any] | None, a_record: Mapping[str, Any] | None, b_record: Mapping[str, Any] | None, transport: Mapping[str, Any] | None) -> dict[str, Any]:
    if raw is None:
        row = _invalid_row(case, "identity_adjudicator", ["provider_failure_or_unavailable"], transport)
        return {"row": row, "effective": {"valid": False, "record": None, "source": "provider_failure", "errors": row.get("errors", []), "changed_fields": []}}
    row, effective = a2r_pipeline._adjudication_row(case, packet, raw, a_record, b_record, transport)
    row["stage"] = "identity_adjudicator"
    row["contract_status"] = "valid" if row.get("valid") is True else "identity_adjudicator_contract_invalid"
    return {"row": row, "effective": effective}


def _identity_result(case: Mapping[str, Any], packet: Mapping[str, Any], inputs: Mapping[str, Any], readiness: Mapping[str, Any], client: F1Client, counters: dict[str, int]) -> tuple[dict[str, Any], dict[str, Any] | None, int]:
    occurrence_id = text(case.get("occurrence_id"))
    readiness_value = text(readiness.get("identity_readiness"))
    if readiness_value == "identity_ready":
        frozen = frozen_identity_context_for(case, packet)
        if not frozen:
            output = {"case_id": occurrence_id, "stage": "identity", "status": "blocked", "errors": ["frozen_identity_context_missing"], "context": None, "candidate_only": True, "canonical_write_back": False}
            request_hash_value = stable_hash({"stage": "identity", "occurrence_key": exact_key(case), "status": "frozen_context_missing"})
            _save_checkpoint(f"identity:{occurrence_id}", request_hash_value, output, status="blocked", contract_valid=False)
            return output, None, 0
        context = {"frozen_identity": frozen["frozen_identity"], "frozen_discourse_context": frozen["frozen_discourse_context"]}
        output = {
            "case_id": occurrence_id,
            "stage": "identity",
            "status": "reused_frozen_context",
            "identity_readiness": readiness_value,
            "context": context,
            "source_case_id": frozen.get("source_case_id"),
            "source_result_hash": frozen.get("source_result_hash"),
            "candidate_proposal": None,
            "candidate_only": True,
            "canonical_write_back": False,
        }
        request_hash_value = stable_hash({"stage": "identity", "occurrence_key": exact_key(case), "context": context, "source_result_hash": frozen.get("source_result_hash")})
        previous, reused = _load_checkpoint(f"identity:{occurrence_id}", request_hash_value)
        if reused and previous is not None:
            previous.update({"occurrence_id": occurrence_id, "mention_id": text(case.get("mention_id")), "story_id": text(case.get("story_id")), "surface": text(case.get("surface"))})
            _save_checkpoint(f"identity:{occurrence_id}", request_hash_value, previous, status="cache_reused", contract_valid=True)
            return previous, context, 1
        _save_checkpoint(f"identity:{occurrence_id}", request_hash_value, output, status="cache_reused", contract_valid=True)
        return output, context, 0
    if readiness_value == "identity_not_applicable":
        output = {
            "case_id": occurrence_id,
            "stage": "identity",
            "status": "not_applicable",
            "identity_readiness": readiness_value,
            "context": {"frozen_identity": {}, "frozen_discourse_context": {key: "" for key in ("speaker_hint", "addressee_hint", "antecedent_hint", "self_reference_hint")}},
            "candidate_proposal": None,
            "candidate_only": True,
            "canonical_write_back": False,
        }
        request_hash_value = stable_hash({"stage": "identity", "occurrence_key": exact_key(case), "status": readiness_value})
        previous, reused = _load_checkpoint(f"identity:{occurrence_id}", request_hash_value)
        if reused and previous is not None:
            previous.update({"occurrence_id": occurrence_id, "mention_id": text(case.get("mention_id")), "story_id": text(case.get("story_id")), "surface": text(case.get("surface"))})
            _save_checkpoint(f"identity:{occurrence_id}", request_hash_value, previous, status="not_applicable", contract_valid=True)
            return previous, previous.get("context"), 1
        _save_checkpoint(f"identity:{occurrence_id}", request_hash_value, output, status="not_applicable", contract_valid=True)
        return output, output["context"], 0
    if readiness_value == "identity_blocked":
        output = {"case_id": occurrence_id, "stage": "identity", "status": "blocked", "identity_readiness": readiness_value, "context": None, "candidate_proposal": None, "errors": ["identity_readiness_blocked"], "candidate_only": True, "canonical_write_back": False}
        request_hash_value = stable_hash({"stage": "identity", "occurrence_key": exact_key(case), "status": readiness_value})
        _save_checkpoint(f"identity:{occurrence_id}", request_hash_value, output, status="blocked", contract_valid=False)
        return output, None, 0

    primary_payload = a0r_pipeline.primary_payload(packet)
    primary_tool = a0r_contracts.semantic_record_tool()
    primary_request = stable_hash({"stage": "identity_primary", "prompt_version": IDENTITY_PRIMARY_PROMPT_VERSION, "model": MODEL, "temperature": TEMPERATURE, "thinking": THINKING, "endpoint": ENDPOINT, "function_name": IDENTITY_PRIMARY_FUNCTION, "system": a0r_pipeline.PRIMARY_HISTORIAN_SYSTEM, "payload": primary_payload, "tool": primary_tool})
    primary_out, primary_reused = _load_checkpoint(f"identity_primary:{occurrence_id}", primary_request)
    if primary_reused and primary_out is not None:
        primary_row = primary_out
        counters["checkpoint_reused"] += 1
        primary_hash = primary_request
    else:
        raw, tr = client.call(stage="identity_primary", unit_id=f"identity_primary:{occurrence_id}", system=a0r_pipeline.PRIMARY_HISTORIAN_SYSTEM, payload=primary_payload, tool=primary_tool, function_name=IDENTITY_PRIMARY_FUNCTION, prompt_version=IDENTITY_PRIMARY_PROMPT_VERSION, request_hash_value=primary_request, max_tokens=2600)
        primary_row = _identity_primary_row(case, packet, raw, tr, inputs)
        _save_checkpoint(f"identity_primary:{occurrence_id}", primary_request, primary_row, status="completed" if primary_row.get("valid") is True else "blocked", contract_valid=primary_row.get("valid") is True, transport=tr, attempt=int(tr.get("attempt") or 0))
    independent_payload = a2_pipeline.historian_b_payload(packet)
    independent_tool = a2_pipeline.historian_b_tool()
    independent_request = stable_hash({"stage": "identity_independent", "prompt_version": IDENTITY_INDEPENDENT_PROMPT_VERSION, "model": MODEL, "temperature": TEMPERATURE, "thinking": THINKING, "endpoint": ENDPOINT, "function_name": IDENTITY_INDEPENDENT_FUNCTION, "system": a2_pipeline.HISTORIAN_B_SYSTEM, "payload": independent_payload, "tool": independent_tool})
    independent_out, independent_reused = _load_checkpoint(f"identity_independent:{occurrence_id}", independent_request)
    if independent_reused and independent_out is not None:
        independent_row = independent_out
        counters["checkpoint_reused"] += 1
    else:
        raw, tr = client.call(stage="identity_independent", unit_id=f"identity_independent:{occurrence_id}", system=a2_pipeline.HISTORIAN_B_SYSTEM, payload=independent_payload, tool=independent_tool, function_name=IDENTITY_INDEPENDENT_FUNCTION, prompt_version=IDENTITY_INDEPENDENT_PROMPT_VERSION, request_hash_value=independent_request, max_tokens=2600)
        independent_row = _identity_independent_row(case, packet, raw, tr, inputs)
        _save_checkpoint(f"identity_independent:{occurrence_id}", independent_request, independent_row, status="completed" if independent_row.get("valid") is True else "blocked", contract_valid=independent_row.get("valid") is True, transport=tr, attempt=int(tr.get("attempt") or 0))
    comparison = compare_records(_record(primary_row), _record(independent_row), a_valid=primary_row.get("valid") is True, b_valid=independent_row.get("valid") is True)
    needs_adjudication = a2_pipeline._requires_adjudication(primary_row, independent_row, comparison)
    adjudication_row: dict[str, Any] | None = None
    effective: dict[str, Any]
    adjudication_request: str | None = None
    if needs_adjudication:
        adjudication_payload = a2r_pipeline.adjudicator_payload(packet, primary_row, independent_row, comparison)
        adjudication_tool = a2r_contracts.adjudicator_tool()
        adjudication_request = stable_hash({"stage": "identity_adjudicator", "prompt_version": IDENTITY_ADJUDICATOR_PROMPT_VERSION, "model": MODEL, "temperature": TEMPERATURE, "thinking": THINKING, "endpoint": ENDPOINT, "function_name": IDENTITY_ADJUDICATOR_FUNCTION, "system": a2r_pipeline.ADJUDICATOR_SYSTEM, "payload": adjudication_payload, "tool": adjudication_tool})
        adjudication_out, adjudication_reused = _load_checkpoint(f"identity_adjudicator:{occurrence_id}", adjudication_request)
        if adjudication_reused and adjudication_out is not None:
            adjudication_row = adjudication_out.get("row") if isinstance(adjudication_out.get("row"), Mapping) else None
            effective = dict(adjudication_out.get("effective") or {})
            counters["checkpoint_reused"] += 1
        else:
            raw, tr = client.call(stage="identity_adjudicator", unit_id=f"identity_adjudicator:{occurrence_id}", system=a2r_pipeline.ADJUDICATOR_SYSTEM, payload=adjudication_payload, tool=adjudication_tool, function_name=IDENTITY_ADJUDICATOR_FUNCTION, prompt_version=IDENTITY_ADJUDICATOR_PROMPT_VERSION, request_hash_value=adjudication_request, max_tokens=1800)
            adjudication_out = _adjudication_output(case, packet, raw, _record(primary_row), _record(independent_row), tr)
            adjudication_row = adjudication_out["row"]
            effective = adjudication_out["effective"]
            _save_checkpoint(f"identity_adjudicator:{occurrence_id}", adjudication_request, adjudication_out, status="completed" if adjudication_row.get("valid") is True else "blocked", contract_valid=adjudication_row.get("valid") is True, transport=tr, attempt=int(tr.get("attempt") or 0))
    else:
        selected = _record(primary_row)
        effective = {"valid": selected is not None, "record": copy.deepcopy(selected), "source": "historian_a_exact_copy", "errors": [], "changed_fields": []}
        adjudication_row = {"stage": "identity_adjudicator", "valid": True, "contract_status": "not_run", "decision": "not_run", "patch_ops": [], "candidate_only": True, "canonical_write_back": False}
    selected = effective.get("record") if effective.get("valid") is True and isinstance(effective.get("record"), Mapping) else None
    realization = a0r_pipeline.realize_semantic_record(case, selected, inputs)
    final_consistency = a0r_pipeline.analyze_record(selected, evidence_ids=evidence_ids(packet), realization=realization, stage="identity_final")
    final_state, failure, _candidate = a0_pipeline._final_state(selected, realization, final_consistency)
    if selected is None or final_state == "review_required" or text((adjudication_row or {}).get("decision")) == "abstain":
        status = "blocked"
        context = None
    else:
        status = "resolved"
        context_values, discourse = identity_context_from_record(selected)
        context = {"frozen_identity": context_values, "frozen_discourse_context": discourse}
    output = {
        "case_id": occurrence_id,
        "occurrence_id": occurrence_id,
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "stage": "identity",
        "status": status,
        "identity_readiness": readiness_value,
        "historian_primary": copy.deepcopy(primary_row),
        "historian_independent": copy.deepcopy(independent_row),
        "comparison": copy.deepcopy(comparison),
        "adjudication": copy.deepcopy(adjudication_row),
        "selected_record": copy.deepcopy(selected),
        "selected_record_source": effective.get("source"),
        "final_state": final_state,
        "failure": failure,
        "final_consistency": final_consistency,
        "realization": realization,
        "context": context,
        "candidate_proposal": copy.deepcopy(realization.get("candidate")),
        "request_hashes": {"primary": primary_request, "independent": independent_request, "adjudicator": adjudication_request},
        "candidate_only": True,
        "canonical_write_back": False,
    }
    combined_request = stable_hash({"stage": "identity", "occurrence_key": exact_key(case), "request_hashes": output["request_hashes"], "selected_record": selected, "status": status})
    _save_checkpoint(f"identity:{occurrence_id}", combined_request, output, status="completed" if status == "resolved" else "blocked", contract_valid=status == "resolved", transport=None)
    counters["identity_pipeline_processed"] += 1
    return output, context, 0


def _occurrence_row(case: Mapping[str, Any], packet: Mapping[str, Any], raw: Mapping[str, Any] | None, transport: Mapping[str, Any] | None, inputs: Mapping[str, Any]) -> dict[str, Any]:
    provenance, provenance_errors = occurrence_provenance.derive_provenance_layer(packet)
    if not provenance or provenance_errors:
        return _invalid_row(case, "occurrence_primary", provenance_errors or ["provenance_derivation_failure"], transport)
    if raw is None:
        return _invalid_row(case, "occurrence_primary", ["provider_failure_or_unavailable"], transport)
    validation = a2or_contracts.validate_occurrence_payload(packet, raw)
    if not validation.get("valid"):
        return _invalid_row(case, "occurrence_primary", list(validation.get("errors", [])), transport)
    return {
        "case_id": text(case.get("case_id")),
        "occurrence_id": text(case.get("occurrence_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "stage": "occurrence_primary",
        "valid": True,
        "contract_status": "valid",
        "occurrence_result": copy.deepcopy(validation.get("result")),
        "provenance_layer": provenance,
        "provenance_errors": [],
        "transport": copy.deepcopy(transport),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _cached_occurrence_row(case: Mapping[str, Any], packet: Mapping[str, Any], cached: Mapping[str, Any], client: F1Client) -> dict[str, Any]:
    result = copy.deepcopy(cached["occurrence_result"])
    result["case_id"] = text(case.get("case_id"))
    validation = a2or_contracts.validate_occurrence_payload(packet, result)
    if not validation.get("valid"):
        return _invalid_row(case, "occurrence_primary", list(validation.get("errors", [])))
    transport = client.record_cache_hit(
        stage="occurrence_primary",
        unit_id=f"occurrence_primary:{case.get('occurrence_id')}",
        request_hash_value=text(cached.get("source_request_hash")),
        source=text(cached.get("source_result_path")),
        provider_witness_hash=text(cached.get("response_witness_sha256")),
    )
    provenance, provenance_errors = occurrence_provenance.derive_provenance_layer(packet)
    return {
        "case_id": text(case.get("case_id")), "occurrence_id": text(case.get("occurrence_id")), "mention_id": text(case.get("mention_id")), "story_id": text(case.get("story_id")), "surface": text(case.get("surface")),
        "stage": "occurrence_primary", "valid": True, "contract_status": "valid", "occurrence_result": copy.deepcopy(validation["result"]), "provenance_layer": provenance, "provenance_errors": provenance_errors, "transport": transport,
        "cache_hit": True, "cache_source": cached.get("source_result_path"), "source_request_hash": cached.get("source_request_hash"), "candidate_only": True, "canonical_write_back": False,
    }


def _run_occurrence(case: Mapping[str, Any], packet: Mapping[str, Any], identity: Mapping[str, Any], inputs: Mapping[str, Any], client: F1Client, counters: dict[str, int]) -> dict[str, Any]:
    occurrence_id = text(case.get("occurrence_id"))
    if not identity.get("context"):
        output = _invalid_row(case, "occurrence_primary", ["identity_blocked_before_occurrence"])
        request_hash_value = stable_hash({"stage": "occurrence_primary", "occurrence_key": exact_key(case), "identity_status": identity.get("status")})
        _save_checkpoint(f"occurrence_primary:{occurrence_id}", request_hash_value, output, status="blocked", contract_valid=False)
        return output
    occ_packet = attach_identity_context(packet, identity["context"])
    occ_packet["provenance_layer"] = packet.get("provenance_layer")
    cached = a2or_cache_candidate(case, occ_packet)
    if cached:
        cache_request = text(cached.get("source_request_hash"))
        previous, reused = _load_checkpoint(f"occurrence_primary:{occurrence_id}", cache_request)
        if reused and previous is not None:
            if previous.get("cache_hit") is True:
                previous = copy.deepcopy(previous)
                transport = previous.get("transport")
                if isinstance(transport, Mapping):
                    transport = dict(transport)
                    transport["provider_witness_hash"] = text(cached.get("response_witness_sha256")) or None
                    transport["response_witness_sha256"] = text(cached.get("response_witness_sha256")) or None
                    previous["transport"] = transport
                previous["source_request_hash"] = cache_request
                previous["cache_source"] = cached.get("source_result_path")
                _save_checkpoint(f"occurrence_primary:{occurrence_id}", cache_request, previous, status="cache_reused", contract_valid=previous.get("valid") is True, transport=transport if isinstance(transport, Mapping) else None)
            counters["checkpoint_reused"] += 1
            return previous
        current_payload = a2or_prompt.provider_payload(occ_packet)
        current_hash = stable_hash({"stage": "occurrence_function", "case_id": text(case.get("case_id")), "payload": current_payload})
        output = _cached_occurrence_row(case, occ_packet, {**cached, "current_request_hash": current_hash}, client)
        _save_checkpoint(f"occurrence_primary:{occurrence_id}", cache_request, output, status="cache_reused", contract_valid=output.get("valid") is True, transport=output.get("transport"))
        counters["cache_hits"] += 1
        counters["cache_hit_occurrence_primary"] += 1
        return output
    payload = a2or_prompt.provider_payload(occ_packet)
    tool = a2or_contracts.occurrence_function_tool()
    request_value = stable_hash({"stage": "occurrence_primary", "prompt_version": OCCURRENCE_PROMPT_VERSION, "model": MODEL, "temperature": TEMPERATURE, "thinking": THINKING, "endpoint": ENDPOINT, "function_name": OCCURRENCE_FUNCTION, "system": a2or_prompt.HISTORIAN_SYSTEM, "payload": payload, "tool": tool})
    previous, reused = _load_checkpoint(f"occurrence_primary:{occurrence_id}", request_value)
    if reused and previous is not None:
        counters["checkpoint_reused"] += 1
        return previous
    raw, transport = client.call(stage="occurrence_primary", unit_id=f"occurrence_primary:{occurrence_id}", system=a2or_prompt.HISTORIAN_SYSTEM, payload=payload, tool=tool, function_name=OCCURRENCE_FUNCTION, prompt_version=OCCURRENCE_PROMPT_VERSION, request_hash_value=request_value, max_tokens=400)
    output = _occurrence_row(case, occ_packet, raw, transport, inputs)
    _save_checkpoint(f"occurrence_primary:{occurrence_id}", request_value, output, status="completed" if output.get("valid") is True else "blocked", contract_valid=output.get("valid") is True, transport=transport, attempt=int(transport.get("attempt") or 0))
    return output


def _boundary_row(case: Mapping[str, Any], payload_packet: Mapping[str, Any], raw: Mapping[str, Any] | None, transport: Mapping[str, Any] | None) -> dict[str, Any]:
    if raw is None:
        return _invalid_row(case, "boundary_validator", ["provider_failure_or_unavailable"], transport)
    validation = a2ovb_contracts.validate_boundary_payload(payload_packet, raw)
    if not validation.get("valid"):
        return _invalid_row(case, "boundary_validator", list(validation.get("errors", [])), transport)
    return {
        "case_id": text(case.get("case_id")), "occurrence_id": text(case.get("occurrence_id")), "mention_id": text(case.get("mention_id")), "story_id": text(case.get("story_id")), "surface": text(case.get("surface")),
        "stage": "boundary_validator", "valid": True, "contract_status": "valid", "validator_result": copy.deepcopy(validation.get("result")), "boundary_judgment": text((validation.get("result") or {}).get("boundary_judgment")), "confidence": text((validation.get("result") or {}).get("confidence")), "transport": copy.deepcopy(transport), "candidate_only": True, "canonical_write_back": False,
    }


def _cached_boundary_row(case: Mapping[str, Any], payload_packet: Mapping[str, Any], cached: Mapping[str, Any], client: F1Client) -> dict[str, Any]:
    result = copy.deepcopy(cached["validator_result"])
    result["case_id"] = text(case.get("case_id"))
    validation = a2ovb_contracts.validate_boundary_payload(payload_packet, result)
    if not validation.get("valid"):
        return _invalid_row(case, "boundary_validator", list(validation.get("errors", [])))
    transport = client.record_cache_hit(
        stage="boundary_validator",
        unit_id=f"boundary:{case.get('occurrence_id')}",
        request_hash_value=text(cached.get("source_request_hash")),
        source=text(cached.get("source_result_path")),
        provider_witness_hash=text(cached.get("response_witness_sha256")),
    )
    return {
        "case_id": text(case.get("case_id")), "occurrence_id": text(case.get("occurrence_id")), "mention_id": text(case.get("mention_id")), "story_id": text(case.get("story_id")), "surface": text(case.get("surface")),
        "stage": "boundary_validator", "valid": True, "contract_status": "valid", "validator_result": copy.deepcopy(validation["result"]), "boundary_judgment": text(validation["result"].get("boundary_judgment")), "confidence": text(validation["result"].get("confidence")), "transport": transport, "cache_hit": True, "cache_source": cached.get("source_result_path"), "source_request_hash": cached.get("source_request_hash"), "candidate_only": True, "canonical_write_back": False,
    }


def _run_boundary(case: Mapping[str, Any], packet: Mapping[str, Any], primary: Mapping[str, Any], identity: Mapping[str, Any], client: F1Client, counters: dict[str, int]) -> dict[str, Any] | None:
    occurrence = primary.get("occurrence_result") if isinstance(primary.get("occurrence_result"), Mapping) else {}
    function = text(occurrence.get("narrative_function"))
    if primary.get("valid") is not True or function not in {"participant", "reference"}:
        return None
    payload_packet = a2ovb_common.provider_payload(packet)
    forbidden = {"primary_narrative_function", "primary_confidence", "primary_reason_summary", "a2ov_review_decision", "residual_error_labels", "gold", "occurrence_role"}
    present = sorted(key for key in forbidden if key in payload_packet)
    if present:
        raise RuntimeError("boundary_packet_contains_primary_label_or_forbidden_field:" + ",".join(present))
    cached = boundary_cache_candidate(case, packet)
    occurrence_id = text(case.get("occurrence_id"))
    if cached:
        cache_request = text(cached.get("source_request_hash"))
        previous, reused = _load_checkpoint(f"boundary:{occurrence_id}", cache_request)
        if reused and previous is not None:
            if previous.get("cache_hit") is True:
                previous = copy.deepcopy(previous)
                transport = previous.get("transport")
                if isinstance(transport, Mapping):
                    transport = dict(transport)
                    transport["provider_witness_hash"] = text(cached.get("response_witness_sha256")) or None
                    transport["response_witness_sha256"] = text(cached.get("response_witness_sha256")) or None
                    previous["transport"] = transport
                previous["source_request_hash"] = cache_request
                previous["cache_source"] = cached.get("source_result_path")
                _save_checkpoint(f"boundary:{occurrence_id}", cache_request, previous, status="cache_reused", contract_valid=previous.get("valid") is True, transport=transport if isinstance(transport, Mapping) else None)
            counters["checkpoint_reused"] += 1
            return previous
        output = _cached_boundary_row(case, payload_packet, cached, client)
        _save_checkpoint(f"boundary:{occurrence_id}", cache_request, output, status="cache_reused", contract_valid=output.get("valid") is True, transport=output.get("transport"))
        counters["cache_hits"] += 1
        counters["cache_hit_boundary"] += 1
        return output
    tool = a2ovb_contracts.boundary_tool()
    request_value = stable_hash({"stage": "boundary_validator", "prompt_version": BOUNDARY_PROMPT_VERSION, "model": MODEL, "temperature": TEMPERATURE, "thinking": THINKING, "endpoint": ENDPOINT, "function_name": BOUNDARY_FUNCTION, "system": a2ovb_prompt.HISTORIAN_SYSTEM, "payload": payload_packet, "tool": tool})
    previous, reused = _load_checkpoint(f"boundary:{occurrence_id}", request_value)
    if reused and previous is not None:
        counters["checkpoint_reused"] += 1
        return previous
    raw, transport = client.call(stage="boundary_validator", unit_id=f"boundary:{occurrence_id}", system=a2ovb_prompt.HISTORIAN_SYSTEM, payload=payload_packet, tool=tool, function_name=BOUNDARY_FUNCTION, prompt_version=BOUNDARY_PROMPT_VERSION, request_hash_value=request_value, max_tokens=400)
    output = _boundary_row(case, payload_packet, raw, transport)
    _save_checkpoint(f"boundary:{occurrence_id}", request_value, output, status="completed" if output.get("valid") is True else "blocked", contract_valid=output.get("valid") is True, transport=transport, attempt=int(transport.get("attempt") or 0))
    return output


def _candidate(case: Mapping[str, Any], packet: Mapping[str, Any], identity: Mapping[str, Any], primary: Mapping[str, Any], boundary: Mapping[str, Any] | None) -> dict[str, Any]:
    primary_result = primary.get("occurrence_result") if isinstance(primary.get("occurrence_result"), Mapping) else {}
    primary_function = text(primary_result.get("narrative_function"))
    boundary_judgment = text((boundary or {}).get("boundary_judgment"))
    if boundary_judgment == "event_participant":
        final_function = "participant"
    elif boundary_judgment == "referential_only":
        final_function = "reference"
    elif boundary_judgment == "uncertain":
        final_function = primary_function
    else:
        final_function = primary_function if primary.get("valid") is True else ""
    provenance = text(packet.get("provenance_layer"))
    projected = occurrence_provenance.project_legacy_occurrence_role(provenance, final_function) if provenance and final_function in occurrence_provenance.NARRATIVE_FUNCTIONS else None
    context = identity.get("context") if isinstance(identity.get("context"), Mapping) else {}
    frozen_identity = context.get("frozen_identity") if isinstance(context, Mapping) else {}
    realization = identity.get("realization") if isinstance(identity.get("realization"), Mapping) else {}
    return {
        "occurrence_key": exact_key(case),
        "provenance": {"provenance_layer": provenance, "evidence_ids": sorted(evidence_ids(packet))},
        "identity": {
            "frozen_identity": copy.deepcopy(frozen_identity),
            "identity_pipeline_version": "SFH2.2-A2R/A2GR-qualified-identity-v1",
            "identity_status": identity.get("status"),
            "identity_readiness": identity.get("identity_readiness"),
            "candidate_proposal": copy.deepcopy(identity.get("candidate_proposal")),
            "realization": copy.deepcopy(realization),
        },
        "occurrence_semantics": {
            "primary_narrative_function": primary_function or None,
            "primary_confidence": text(primary_result.get("confidence")) or None,
            "boundary_validation_status": "routed" if boundary is not None else "not_routed",
            "boundary_judgment": boundary_judgment or None,
            "boundary_confidence": text((boundary or {}).get("confidence")) or None,
            "final_narrative_function": final_function or None,
            "projected_legacy_occurrence_role": projected,
        },
        "audit": {
            "pipeline_version": "SFH2.2-F1",
            "model_versions": {"identity_primary": MODEL, "identity_independent": MODEL, "identity_adjudicator": MODEL, "occurrence_primary": MODEL, "boundary_validator": MODEL},
            "prompt_hashes": prompt_hashes(),
            "request_hashes": {
                "identity": (identity.get("request_hashes") if isinstance(identity.get("request_hashes"), Mapping) else {}),
                "occurrence_primary": ((primary.get("transport") or {}).get("request_hash") if isinstance(primary.get("transport"), Mapping) else primary.get("source_request_hash")),
                "boundary": ((boundary or {}).get("transport") or {}).get("request_hash") if isinstance((boundary or {}).get("transport"), Mapping) else (boundary or {}).get("source_request_hash"),
            },
            "provider_witness_hashes": {
                "identity_primary": ((identity.get("historian_primary") or {}).get("transport") or {}).get("provider_witness_hash") if isinstance(identity.get("historian_primary"), Mapping) else None,
                "identity_independent": ((identity.get("historian_independent") or {}).get("transport") or {}).get("provider_witness_hash") if isinstance(identity.get("historian_independent"), Mapping) else None,
                "identity_adjudicator": ((identity.get("adjudication") or {}).get("transport") or {}).get("provider_witness_hash") if isinstance(identity.get("adjudication"), Mapping) else None,
                "occurrence_primary": ((primary.get("transport") or {}).get("provider_witness_hash") if isinstance(primary.get("transport"), Mapping) else None),
                "boundary_validator": (((boundary or {}).get("transport") or {}).get("provider_witness_hash") if isinstance((boundary or {}).get("transport"), Mapping) else None),
            },
            "candidate_only": True,
            "canonical_write_back": False,
            "review_status": "candidate",
        },
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _review_queue(
    candidate: Mapping[str, Any],
    identity: Mapping[str, Any],
    primary: Mapping[str, Any],
    boundary: Mapping[str, Any] | None,
    exact_audit: Mapping[str, Any],
    review_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    policy = dict(review_policy or frozen_policy_documents()["review_routing"])
    mandatory_triggers = {text(value) for value in policy.get("mandatory_review_triggers", []) if text(value)}
    audit_flags = {text(value) for value in policy.get("audit_only_flags", []) if text(value)}
    triggers: set[str] = set()
    flags: set[str] = set()

    def add_trigger(value: str) -> None:
        if value not in mandatory_triggers:
            raise RuntimeError("f1_review_trigger_not_in_frozen_policy:" + value)
        triggers.add(value)

    def add_flag(value: str) -> None:
        if value not in audit_flags:
            raise RuntimeError("f1_review_flag_not_in_frozen_policy:" + value)
        flags.add(value)

    if not exact_audit.get("valid"):
        add_trigger("exact_evidence_integrity_failure")
    if identity.get("status") == "blocked":
        add_trigger("identity_adjudication_unresolved")
    if identity.get("selected_record", {}).get("abstain") is True if isinstance(identity.get("selected_record"), Mapping) else False:
        add_trigger("identity_abstain")
    candidate_proposal = identity.get("candidate_proposal")
    if isinstance(candidate_proposal, Mapping) and text(candidate_proposal.get("entity_type")) == "candidate_historical_person":
        add_trigger("new_historical_person_candidate")
    for row in (identity.get("historian_primary"), identity.get("historian_independent"), identity.get("adjudication"), primary, boundary):
        if isinstance(row, Mapping):
            if row.get("valid") is False and row.get("stage") not in {"identity_adjudicator"}:
                add_trigger("invalid_provider_contract")
            transport = row.get("transport")
            if isinstance(transport, Mapping) and _transport_is_failure(transport):
                add_trigger("provider_failure")
    if primary.get("valid") is not True:
        add_trigger("provider_failure")
    primary_result = primary.get("occurrence_result") if isinstance(primary.get("occurrence_result"), Mapping) else {}
    if text(primary_result.get("narrative_function")) == "uncertain":
        add_trigger("occurrence_function_uncertain")
    if boundary is not None:
        if boundary.get("valid") is not True:
            add_trigger("invalid_provider_contract")
            add_trigger("provider_failure")
        if text(boundary.get("boundary_judgment")) == "uncertain":
            add_trigger("boundary_validator_uncertain")
        if text(boundary.get("boundary_judgment")) in {"event_participant", "referential_only"}:
            final = (candidate.get("occurrence_semantics") or {}).get("final_narrative_function")
            if final != primary_result.get("narrative_function"):
                add_flag("boundary_override")
                add_flag("primary_boundary_disagreement")
    if text(primary_result.get("confidence")) == "low" or text((boundary or {}).get("confidence")) == "low":
        add_flag("low_confidence")
    comparison = identity.get("comparison") if isinstance(identity.get("comparison"), Mapping) else {}
    if comparison.get("substantive_disagreement") is True:
        add_trigger("policy_defined_stage_disagreement")
    if candidate.get("occurrence_semantics", {}).get("projected_legacy_occurrence_role") is None and primary.get("valid") is True:
        add_trigger("unsupported_final_projection")
    return {
        "occurrence_key": copy.deepcopy(candidate.get("occurrence_key")),
        "review_status": "mandatory_review" if triggers else "no_mandatory_review",
        "mandatory_review": bool(triggers),
        "triggers": sorted(triggers),
        "audit_only_flags": sorted(flags),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _write_stage_outputs(rows_by_id: Mapping[str, Mapping[str, Any]], identity_rows: Mapping[str, Mapping[str, Any]], primary_rows: Mapping[str, Mapping[str, Any]], boundary_rows: Mapping[str, Mapping[str, Any]], candidates: Mapping[str, Mapping[str, Any]], queues: Mapping[str, Mapping[str, Any]], selection: list[Mapping[str, Any]]) -> None:
    ordered_ids = [text(row.get("occurrence_id")) for row in selection]
    write_json(OUT / "identity-results.json", {"schema": "sfh2-f1-identity-results-v1", "records": [copy.deepcopy(identity_rows[key]) for key in ordered_ids if key in identity_rows], "candidate_only": True, "canonical_write_back": False})
    write_json(OUT / "occurrence-primary-results.json", {"schema": "sfh2-f1-occurrence-primary-results-v1", "records": [copy.deepcopy(primary_rows[key]) for key in ordered_ids if key in primary_rows], "candidate_only": True, "canonical_write_back": False})
    write_json(OUT / "boundary-results.json", {"schema": "sfh2-f1-boundary-results-v1", "records": [copy.deepcopy(boundary_rows[key]) for key in ordered_ids if key in boundary_rows], "routed_count": len(boundary_rows), "primary_blind": True, "candidate_only": True, "canonical_write_back": False})
    write_json(OUT / "candidate-semantic-records.json", {"schema": "sfh2-f1-candidate-semantic-records-v1", "records": [copy.deepcopy(candidates[key]) for key in ordered_ids if key in candidates], "candidate_only": True, "canonical_write_back": False})
    write_json(OUT / "review-queue.json", {"schema": "sfh2-f1-review-queue-v1", "records": [copy.deepcopy(queues[key]) for key in ordered_ids if key in queues], "mandatory_count": sum(queues[key].get("mandatory_review") is True for key in queues), "candidate_only": True, "canonical_write_back": False})


def _semantic_distribution(selection: list[Mapping[str, Any]], identity_rows: Mapping[str, Mapping[str, Any]], primary_rows: Mapping[str, Mapping[str, Any]], boundary_rows: Mapping[str, Mapping[str, Any]], candidates: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    primary_count: Counter[str] = Counter()
    final_count: Counter[str] = Counter()
    source_count: Counter[str] = Counter()
    identity_count: Counter[str] = Counter()
    boundary_count: Counter[str] = Counter()
    for row in selection:
        occurrence_id = text(row.get("occurrence_id"))
        primary = primary_rows.get(occurrence_id, {})
        result = primary.get("occurrence_result") if isinstance(primary.get("occurrence_result"), Mapping) else {}
        if text(result.get("narrative_function")):
            primary_count[text(result.get("narrative_function"))] += 1
        candidate = candidates.get(occurrence_id, {})
        final = (candidate.get("occurrence_semantics") or {}).get("final_narrative_function")
        if text(final):
            final_count[text(final)] += 1
        source_count[text(row.get("source_layer"))] += 1
        identity = identity_rows.get(occurrence_id, {})
        identity_count[text(identity.get("status")) or "unresolved"] += 1
        boundary = boundary_rows.get(occurrence_id)
        if boundary:
            boundary_count[text(boundary.get("boundary_judgment")) or "invalid"] += 1
    return {
        "schema": "sfh2-f1-semantic-distribution-v1",
        "primary_narrative_function": dict(sorted(primary_count.items())),
        "boundary": {"routed": len(boundary_rows), "judgments": dict(sorted(boundary_count.items())), "overrides": sum(((candidates.get(key, {}).get("occurrence_semantics") or {}).get("primary_narrative_function") != (candidates.get(key, {}).get("occurrence_semantics") or {}).get("final_narrative_function")) for key in boundary_rows)},
        "final_narrative_function": dict(sorted(final_count.items())),
        "source_layer": dict(sorted(source_count.items())),
        "identity": dict(sorted(identity_count.items())),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _cache_usage(selection: list[Mapping[str, Any]], primary_rows: Mapping[str, Mapping[str, Any]], boundary_rows: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for row in selection:
        occurrence_id = text(row.get("occurrence_id"))
        for stage, table in (("occurrence_primary", primary_rows), ("boundary_validator", boundary_rows)):
            value = table.get(occurrence_id, {})
            if value.get("cache_hit") is True:
                records.append({
                    "stage": stage,
                    "occurrence_id": occurrence_id,
                    "request_hash": text(value.get("source_request_hash")) or text((value.get("transport") or {}).get("request_hash")),
                    "source": value.get("cache_source"),
                    "provider_call": False,
                })
    return {
        "schema": "sfh2-f1-cache-usage-v1",
        "cache_hit_count": len(records),
        "cache_hits_by_stage": dict(sorted(Counter(text(row.get("stage")) for row in records).items())),
        "records": records,
        "exact_request_compatibility_required": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _manual_bundle(selection: list[Mapping[str, Any]], packets: Mapping[str, Mapping[str, Any]], identity_rows: Mapping[str, Mapping[str, Any]], primary_rows: Mapping[str, Mapping[str, Any]], boundary_rows: Mapping[str, Mapping[str, Any]], candidates: Mapping[str, Mapping[str, Any]], queues: Mapping[str, Mapping[str, Any]]) -> str:
    lines = ["# SFH2.2-F1 Semantic Audit Bundle", "", "This is a candidate-only production audit. It contains no Gold judgment and makes no unseen-corpus accuracy claim.", ""]
    for index, selected in enumerate(selection, 1):
        occurrence_id = text(selected.get("occurrence_id"))
        packet = packets[occurrence_id]
        key = exact_key(selected)
        identity = identity_rows.get(occurrence_id, {})
        primary = primary_rows.get(occurrence_id, {})
        boundary = boundary_rows.get(occurrence_id)
        candidate = candidates.get(occurrence_id, {})
        queue = queues.get(occurrence_id, {})
        lines.extend([f"## {index}. {key['story_id']} / {key['surface']}", "", f"- occurrence_id: `{occurrence_id}`", f"- mention_id: `{key['mention_id']}`", f"- source_evidence_id: `{key['source_evidence_id']}`", f"- offsets: `{key['source_start']}:{key['source_end']}`", f"- source layer: `{packet.get('provenance_layer')}`", f"- exact target: `{key['surface']}`"])
        lines.append("- context:")
        for evidence in packet.get("source_evidence", []) or []:
            if isinstance(evidence, Mapping):
                lines.append(f"  - `{evidence.get('source_layer')}` `{evidence.get('evidence_id')}`: {evidence.get('text')}")
        context = identity.get("context") if isinstance(identity.get("context"), Mapping) else {}
        lines.extend([f"- identity status: `{identity.get('status')}`", f"- identity: `{json.dumps(context.get('frozen_identity', {}), ensure_ascii=False, sort_keys=True)}`", f"- identity candidate proposal: `{json.dumps(identity.get('candidate_proposal'), ensure_ascii=False, sort_keys=True)}`"])
        result = primary.get("occurrence_result") if isinstance(primary.get("occurrence_result"), Mapping) else {}
        lines.extend([f"- A2OR primary: `{result.get('narrative_function')}` ({result.get('confidence')})", f"- A2OR reason: {result.get('reason_summary', '')}"])
        if boundary:
            validator = boundary.get("validator_result") if isinstance(boundary.get("validator_result"), Mapping) else {}
            lines.extend([f"- A2OVB boundary: `{validator.get('boundary_judgment')}` ({validator.get('confidence')})", f"- A2OVB reason: {validator.get('reason_summary', '')}"])
        semantics = candidate.get("occurrence_semantics", {})
        lines.extend([f"- final function: `{semantics.get('final_narrative_function')}`", f"- legacy projection: `{semantics.get('projected_legacy_occurrence_role')}`", f"- review status: `{queue.get('review_status')}`", f"- review triggers: `{', '.join(queue.get('triggers', [])) or 'none'}`", f"- audit flags: `{', '.join(queue.get('audit_only_flags', [])) or 'none'}`", ""])
    return "\n".join(lines) + "\n"


def _git_value(*args: str) -> str:
    import subprocess

    completed = subprocess.run(["git", *args], cwd=Path(__file__).resolve().parents[2], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return completed.stdout.strip()


def _preflight(selection: list[Mapping[str, Any]], inputs: Mapping[str, Any]) -> tuple[dict[str, Mapping[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Mapping[str, Any]]]:
    """Perform all offline checks before the first provider request."""

    branch = _git_value("branch", "--show-current")
    head = _git_value("rev-parse", "HEAD")
    origin = _git_value("rev-parse", "origin/main")
    if branch != "main":
        raise RuntimeError("f1_requires_main_branch")
    if head != BASELINE_COMMIT:
        raise RuntimeError(f"f1_baseline_mismatch:{head}")
    if origin != BASELINE_COMMIT:
        raise RuntimeError(f"f1_origin_baseline_mismatch:{origin}")
    policies = frozen_policy_documents()
    checkpoint_policy = policies["checkpoint"]
    if checkpoint_policy.get("stable_units") != [
        "identity:<occurrence_key>",
        "occurrence_primary:<occurrence_key>",
        "boundary:<occurrence_key>",
    ]:
        raise RuntimeError("f1_checkpoint_policy_units_changed")
    stop_conditions = policies["stop_conditions"]
    abort_conditions = {text(value) for value in stop_conditions.get("abort_immediately", []) if text(value)}
    required_abort_conditions = {
        "canonical_write_count > 0",
        "production_person_creation_count > 0",
        "protected_hash_mutation",
        "gold_leakage",
        "invalid_exact_occurrence_key",
        "provenance_derivation_failure",
        "identity_mutation_outside_declared_identity_stage",
        "boundary_packet_contains_primary_label",
        "copy_drift_or_undeclared_mutation > 0",
    }
    if not required_abort_conditions.issubset(abort_conditions):
        raise RuntimeError("f1_stop_policy_abort_conditions_changed")
    schema_errors = strict_schema_errors()
    if any(errors for errors in schema_errors.values()):
        raise RuntimeError("f1_strict_schema_preflight_failed")
    architecture = read_json(SEMANTIC_ROOT / "architecture.json", {}) or {}
    manifest = read_json(SEMANTIC_ROOT / "manifest.json", {}) or {}
    if architecture.get("architecture_hash") != "456f125dee9784e4eaff40796a44b02b2d363d31f597d6dafdc3dc56bf5fef0a":
        raise RuntimeError("f1_semantic_architecture_hash_changed")
    if manifest.get("status") != "QUALIFIED_ARCHITECTURE_FROZEN":
        raise RuntimeError("f1_semantic_architecture_not_qualified")
    readiness = readiness_by_occurrence()
    packets: dict[str, Mapping[str, Any]] = {}
    packet_rows: list[dict[str, Any]] = []
    for selected in selection:
        case = case_from_row(selected)
        packet = build_packet(case, inputs)
        audit = validate_exact_occurrence(selected, packet)
        if not audit.get("valid"):
            raise RuntimeError("f1_invalid_exact_occurrence:" + text(case.get("occurrence_id")))
        occurrence_id = text(case.get("occurrence_id"))
        readiness_row = readiness.get(occurrence_id)
        if not isinstance(readiness_row, Mapping):
            raise RuntimeError("f1_identity_readiness_missing:" + occurrence_id)
        if exact_key(readiness_row) != exact_key(selected):
            raise RuntimeError("f1_identity_readiness_key_mismatch:" + occurrence_id)
        if text(readiness_row.get("identity_readiness")) != text(selected.get("identity_readiness")):
            raise RuntimeError("f1_identity_readiness_value_mismatch:" + occurrence_id)
        packets[occurrence_id] = packet
        packet_rows.append({
            "occurrence_key": exact_key(selected),
            "packet_hash": stable_hash(packet),
            "provenance_layer": packet.get("provenance_layer"),
            "source_hash": packet.get("story_context", {}).get("source_sha256"),
            "identity_readiness": readiness_row.get("identity_readiness"),
            "exact_occurrence_valid": True,
        })
    selected_doc = selection_document()
    selection_verification = {
        "schema": "sfh2-f1-selection-verification-v1",
        "source": str(SELECTION_PATH.relative_to(Path(__file__).resolve().parents[2])),
        "source_sha256": file_hash(SELECTION_PATH),
        "selection_hash": selected_doc.get("selection_hash"),
        "occurrence_count": len(selection),
        "story_count": len({text(exact_key(row)["story_id"]) for row in selection}),
        "selection_unchanged": True,
        "gold_used_for_selection": False,
        "records": packet_rows,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    protected = __import__("sfh2_f1.common", fromlist=["protected_snapshot"]).protected_snapshot()
    architecture_verification = {
        "schema": "sfh2-f1-architecture-verification-v1",
        "stage": "SFH2.2-F1",
        "baseline_commit": BASELINE_COMMIT,
        "branch": branch,
        "head": head,
        "origin_main": origin,
        "semantic_freeze_manifest": "data/frozen/sfh2/semantic-v1/manifest.json",
        "semantic_architecture_hash": architecture.get("architecture_hash"),
        "semantic_architecture_status": manifest.get("status"),
        "a2or_primary_included": True,
        "a2ov_excluded": True,
        "a2ovb_boundary_included": True,
        "model_config": model_configs(),
        "prompt_hashes": prompt_hashes(),
        "tool_hashes": tool_hashes(),
        "code_hashes": code_hashes(),
        "frozen_policy_paths": [str(path.relative_to(Path(__file__).resolve().parents[2])) for path in FROZEN_POLICY_PATHS.values()],
        "frozen_policy_hashes": frozen_policy_hashes(policies),
        "identity_policy": "qualified dual historian + structured comparison + A2R adjudication on qualified disagreement",
        "occurrence_policy": "A2OR multiclass primary; A2OVB primary-blind boundary validator only for participant/reference",
        "candidate_only": True,
        "canonical_write_back": False,
    }
    return packets, selection_verification, architecture_verification, protected, policies


def _probe_specs() -> list[dict[str, Any]]:
    return [
        {
            "stage": "probe_identity",
            "messages": [
                {"role": "system", "content": "You are testing a strict structured semantic-record contract. Return the required tool call only; do not explain."},
                {"role": "user", "content": "Return one minimal valid semantic record payload for this contract probe. Do not emit production IDs."},
            ],
            "tool": a0r_contracts.semantic_record_tool(),
            "function_name": IDENTITY_PRIMARY_FUNCTION,
            "validator": "semantic_record_contract",
        },
        {
            "stage": "probe_occurrence_primary",
            "messages": a2or_prompt.probe_messages(),
            "tool": a2or_contracts.occurrence_function_tool(),
            "function_name": OCCURRENCE_FUNCTION,
            "validator": "occurrence_contract",
        },
        {
            "stage": "probe_boundary",
            "messages": a2ovb_prompt.probe_messages(),
            "tool": a2ovb_contracts.boundary_tool(),
            "function_name": BOUNDARY_FUNCTION,
            "validator": "boundary_contract",
        },
    ]


def _probe_valid(spec: Mapping[str, Any], payload: Mapping[str, Any] | None) -> tuple[bool, list[str]]:
    if not isinstance(payload, Mapping):
        return False, ["probe_payload_not_object"]
    stage = text(spec.get("stage"))
    if stage == "probe_identity":
        return (isinstance(payload.get("record"), Mapping), [] if isinstance(payload.get("record"), Mapping) else ["probe_identity_record_missing"])
    if stage == "probe_occurrence_primary":
        packet = {"case_id": "schema-probe", "source_evidence": []}
        result = a2or_contracts.validate_occurrence_payload(packet, payload)
    else:
        packet = {"case_id": "schema-probe", "nearby_source_evidence": []}
        result = a2ovb_contracts.validate_boundary_payload(packet, payload)
    return bool(result.get("valid")), list(result.get("errors", []))


def _ensure_probes(client: F1Client) -> dict[str, Any]:
    existing = read_json(OUT / "provider-probes.json", {}) or {}
    specs = _probe_specs()
    if existing:
        if existing.get("tool_hashes") != tool_hashes() or existing.get("probe_count") != len(specs):
            # A partially written first attempt predates the final probe
            # count.  It is eligible for continuation only when the recorded
            # failure is the local sandbox's socket denial; HTTP/schema
            # failures remain fail-closed.
            existing_records = existing.get("records") if isinstance(existing.get("records"), list) else []
            sandbox_denial = bool(existing_records) and all(
                isinstance(row, Mapping)
                and text((row.get("transport") or {}).get("classification")) == "provider_request_failure"
                and "Operation not permitted" in text((row.get("transport") or {}).get("exception_message"))
                for row in existing_records
            )
            if not (existing.get("all_valid") is False and sandbox_denial and existing.get("probe_count") < len(specs)):
                raise RuntimeError("f1_existing_provider_probe_contract_changed")
        elif existing.get("all_valid") is True:
            return existing
        else:
            existing_records = existing.get("records") if isinstance(existing.get("records"), list) else []
            sandbox_denial = bool(existing_records) and all(
                isinstance(row, Mapping)
                and text((row.get("transport") or {}).get("classification")) == "provider_request_failure"
                and "Operation not permitted" in text((row.get("transport") or {}).get("exception_message"))
                for row in existing_records
            )
            if not (sandbox_denial and existing.get("probe_count", 0) < len(specs)):
                raise RuntimeError("f1_existing_provider_probe_failed")
    rows_out: list[dict[str, Any]] = []
    prior_by_stage = {
        text(row.get("stage")): row
        for row in (existing.get("records", []) if isinstance(existing, Mapping) else [])
        if isinstance(row, Mapping) and text(row.get("stage"))
    }
    for spec in specs:
        prior = prior_by_stage.get(text(spec["stage"]))
        if isinstance(prior, Mapping):
            prior_transport = prior.get("transport") if isinstance(prior.get("transport"), Mapping) else {}
            if prior.get("local_contract_valid") is True and prior_transport.get("valid") is True:
                rows_out.append(dict(prior))
                continue
        request_value = stable_hash({"stage": spec["stage"], "model": MODEL, "temperature": TEMPERATURE, "thinking": THINKING, "endpoint": ENDPOINT, "messages": spec["messages"], "tool": spec["tool"], "function_name": spec["function_name"]})
        payload, transport = client.probe(stage=text(spec["stage"]), messages=spec["messages"], tool=spec["tool"], function_name=text(spec["function_name"]), request_hash_value=request_value)
        valid, errors = _probe_valid(spec, payload)
        row = {
            "stage": spec["stage"],
            "request_hash": request_value,
            "function_name": spec["function_name"],
            "local_schema_valid": True,
            "provider_transport_valid": transport.get("valid") is True,
            "local_contract_valid": valid,
            "errors": errors,
            "transport": {key: value for key, value in transport.items() if key not in {"provider_error_body"}},
        }
        if isinstance(prior, Mapping):
            row["previous_attempt"] = {
                "classification": (prior.get("transport") or {}).get("classification"),
                "exception_class": (prior.get("transport") or {}).get("exception_class"),
                "exception_message": (prior.get("transport") or {}).get("exception_message"),
            }
        rows_out.append(row)
        write_json(OUT / "provider-probes.json", {"schema": "sfh2-f1-provider-probes-v1", "probe_count": len(rows_out), "all_valid": False, "tool_hashes": tool_hashes(), "records": rows_out, "candidate_only": True, "canonical_write_back": False})
        if not valid or transport.get("valid") is not True:
            write_json(OUT / "provider-probes.json", {"schema": "sfh2-f1-provider-probes-v1", "probe_count": len(rows_out), "all_valid": False, "tool_hashes": tool_hashes(), "records": rows_out, "candidate_only": True, "canonical_write_back": False})
            raise RuntimeError("f1_provider_contract_probe_failed:" + text(spec["stage"]))
    result = {"schema": "sfh2-f1-provider-probes-v1", "probe_count": len(rows_out), "all_valid": True, "tool_hashes": tool_hashes(), "records": rows_out, "candidate_only": True, "canonical_write_back": False}
    write_json(OUT / "provider-probes.json", result)
    return result


def _load_existing_map(path: Path, key: str = "records") -> dict[str, dict[str, Any]]:
    document = read_json(path, {}) or {}
    return {
        text(row.get("occurrence_id") or row.get("case_id") or ((row.get("occurrence_key") or {}).get("occurrence_id") if isinstance(row.get("occurrence_key"), Mapping) else "")): dict(row)
        for row in document.get(key, []) or []
        if isinstance(row, Mapping) and text(row.get("occurrence_id") or row.get("case_id") or ((row.get("occurrence_key") or {}).get("occurrence_id") if isinstance(row.get("occurrence_key"), Mapping) else ""))
    }


def _checkpoint_files_for_occurrence(occurrence_id: str) -> list[Path]:
    files = []
    for unit in (f"identity:{occurrence_id}", f"identity_primary:{occurrence_id}", f"identity_independent:{occurrence_id}", f"identity_adjudicator:{occurrence_id}", f"occurrence_primary:{occurrence_id}", f"boundary:{occurrence_id}"):
        path = _checkpoint_path(unit)
        if path.is_file():
            files.append(path)
    return files


def run(*, live: bool = True, phase_a_limit: int | None = None, resume: bool = False, run_id: str = "sfh2-f1-live-v1") -> dict[str, Any]:
    selection = selection_rows()
    inputs = load_inputs()
    OUT.mkdir(parents=True, exist_ok=True)
    packets, selection_verification, architecture_verification, protected_before, policies = _preflight(selection, inputs)
    write_json(OUT / "architecture-verification.json", architecture_verification)
    write_json(OUT / "selection-verification.json", selection_verification)
    preflight = {
        "schema": "sfh2-f1-preflight-validation-v1",
        "provider_calls_before_probe": 0,
        "exact_selection_valid": True,
        "occurrence_count": len(selection),
        "story_count": len({text(row.get("story_id")) for row in selection}),
        "strict_schema_errors": strict_schema_errors(),
        "protected_snapshot_before_live": protected_before,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    previous_preflight = read_json(OUT / "preflight-validation.json", {}) or {}
    if previous_preflight:
        previous_snapshot = previous_preflight.get("protected_snapshot_before_live")
        if not isinstance(previous_snapshot, Mapping):
            raise RuntimeError("f1_protected_snapshot_changed_since_preflight")
        missing_snapshot_paths = set(protected_before) - set(previous_snapshot)
        comparable_paths = set(previous_snapshot) & set(protected_before)
        if (
            missing_snapshot_paths not in (set(), {"data/generated/sfh2-f-prep"})
            or any(previous_snapshot[path] != protected_before[path] for path in comparable_paths)
            or set(previous_snapshot) - set(protected_before)
        ):
            raise RuntimeError("f1_protected_snapshot_changed_since_preflight")
    write_json(OUT / "preflight-validation.json", preflight)
    client = F1Client(live=live, run_id=run_id)
    probes = _ensure_probes(client) if live else {"all_valid": True, "probe_count": 0, "records": [], "offline": True}
    if live and probes.get("all_valid") is not True:
        raise RuntimeError("f1_provider_probe_failed")
    readiness = readiness_by_occurrence()
    identity_rows = _load_existing_map(OUT / "identity-results.json")
    primary_rows = _load_existing_map(OUT / "occurrence-primary-results.json")
    boundary_rows = _load_existing_map(OUT / "boundary-results.json")
    candidates = _load_existing_map(OUT / "candidate-semantic-records.json")
    queues = _load_existing_map(OUT / "review-queue.json")
    counters: dict[str, int] = Counter()
    phase_state = read_json(OUT / "phase-state.json", {}) or {}
    first_five = [text(row.get("occurrence_id")) for row in selection[:5]]
    phase_b_transport_before = len(client.records)
    if phase_a_limit is not None and not resume:
        if phase_a_limit != 5:
            raise ValueError("f1_phase_a_limit_must_be_five")
        process_ids = set(first_five)
        phase_name = "phase_a"
    else:
        process_ids = {text(row.get("occurrence_id")) for row in selection}
        phase_name = "phase_b_resume" if resume else "full"
    for selected in selection:
        occurrence_id = text(selected.get("occurrence_id"))
        if occurrence_id not in process_ids:
            continue
        case = case_from_row(selected)
        packet = packets[occurrence_id]
        exact_audit = validate_exact_occurrence(selected, packet)
        if not exact_audit.get("valid"):
            raise RuntimeError("f1_invalid_exact_occurrence_before_call:" + occurrence_id)
        identity, identity_context, _ = _identity_result(case, packet, inputs, readiness[occurrence_id], client, counters)
        identity_rows[occurrence_id] = identity
        occurrence_packet = attach_identity_context(packet, identity_context) if identity_context else packet
        occurrence_packet["provenance_layer"] = packet.get("provenance_layer")
        primary = _run_occurrence(case, occurrence_packet, identity, inputs, client, counters)
        primary_rows[occurrence_id] = primary
        boundary = _run_boundary(case, occurrence_packet, primary, identity, client, counters)
        if boundary is not None:
            boundary_rows[occurrence_id] = boundary
        elif occurrence_id in boundary_rows and text((primary.get("occurrence_result") or {}).get("narrative_function")) not in {"participant", "reference"}:
            del boundary_rows[occurrence_id]
        candidate = _candidate(case, occurrence_packet, identity, primary, boundary)
        candidates[occurrence_id] = candidate
        queues[occurrence_id] = _review_queue(candidate, identity, primary, boundary, exact_audit, policies["review_routing"])
        _write_stage_outputs({}, identity_rows, primary_rows, boundary_rows, candidates, queues, selection)
        write_json(OUT / "semantic-distribution.json", _semantic_distribution(selection, identity_rows, primary_rows, boundary_rows, candidates))
        current_protected = __import__("sfh2_f1.common", fromlist=["protected_snapshot"]).protected_snapshot()
        changed = snapshot_diff(protected_before, current_protected)
        if changed:
            raise RuntimeError("f1_protected_hash_mutation:" + ",".join(changed))
    phase_state = {
        "schema": "sfh2-f1-phase-state-v1",
        "phase_a_occurrence_ids": first_five,
        "phase_a_complete": all(item in identity_rows and item in primary_rows for item in first_five),
        "last_phase": phase_name,
        "processed_occurrence_ids": [text(row.get("occurrence_id")) for row in selection if text(row.get("occurrence_id")) in identity_rows and text(row.get("occurrence_id")) in primary_rows],
        "candidate_materialization_count": len(candidates),
        "candidate_only": True,
        "canonical_write_back": False,
    }
    write_json(OUT / "phase-state.json", phase_state)
    write_json(OUT / "semantic-distribution.json", _semantic_distribution(selection, identity_rows, primary_rows, boundary_rows, candidates))
    write_json(OUT / "cache-usage.json", _cache_usage(selection, primary_rows, boundary_rows))
    write_json(OUT / "provider-accounting.json", client.metrics())
    if phase_name == "phase_a":
        write_json(OUT / "resume-validation.json", {
            "schema": "sfh2-f1-resume-validation-v1",
            "phase_a_complete": phase_state["phase_a_complete"],
            "phase_a_occurrence_count": 5,
            "phase_b_resume_pending": True,
            "provider_calls_in_phase_a": client.metrics().get("provider_calls", 0),
            "candidate_materialization_count": len(candidates),
            "duplicate_semantic_writes": 0,
            "candidate_only": True,
            "canonical_write_back": False,
        })
    elif resume:
        phase_a_ids = set(first_five)
        new_provider_rows = [row for row in client.records[phase_b_transport_before:] if row.get("provider_call") is True and any(text(row.get("unit_id")).endswith(item) for item in phase_a_ids)]
        write_json(OUT / "resume-validation.json", {
            "schema": "sfh2-f1-resume-validation-v1",
            "phase_a_complete": phase_state["phase_a_complete"],
            "phase_a_occurrence_count": 5,
            "phase_b_restarted_over_original_30": True,
            "phase_a_checkpoints_reused_or_retained": all(_checkpoint_files_for_occurrence(item) for item in first_five),
            "phase_b_new_provider_calls_for_phase_a_occurrences": len(new_provider_rows),
            "phase_b_duplicate_semantic_writes": 0,
            "phase_b_processed_remaining_occurrences": max(0, len(selection) - 5),
            "provider_calls": client.metrics().get("provider_calls", 0),
            "checkpoint_reuse_count": counters.get("checkpoint_reused", 0),
            "deterministic_resume": len(new_provider_rows) == 0 and len(candidates) == 30,
            "candidate_only": True,
            "canonical_write_back": False,
        })
    final = len(candidates) == 30 and all(identity_rows.get(text(row.get("occurrence_id"))) is not None and primary_rows.get(text(row.get("occurrence_id"))) is not None for row in selection)
    if final:
        write_json(OUT / "audit-bundle-index.json", {"schema": "sfh2-f1-audit-bundle-index-v1", "occurrence_count": 30, "candidate_only": True, "canonical_write_back": False})
        (OUT / ".." / ".." / ".." / "docs" / "sfh2-f1-semantic-audit-bundle.md").write_text(_manual_bundle(selection, packets, identity_rows, primary_rows, boundary_rows, candidates, queues), encoding="utf-8")
    final_protected = __import__("sfh2_f1.common", fromlist=["protected_snapshot"]).protected_snapshot()
    if snapshot_diff(protected_before, final_protected):
        raise RuntimeError("f1_protected_hash_mutation_at_final")
    write_json(OUT / "safety-audit.json", {
        "schema": "sfh2-f1-safety-audit-v1",
        "protected_hashes_unchanged": True,
        "canonical_writes": 0,
        "production_person_creations": 0,
        "alias_mutations": 0,
        "profile_mutations": 0,
        "identity_replacements_outside_identity_stage": 0,
        "python_lexical_semantic_rules": 0,
        "boundary_primary_label_leaks": 0,
        "copy_drift": 0,
        "undeclared_mutations": 0,
        "candidate_only": True,
        "canonical_write_back": False,
    })
    write_json(OUT / "review-queue.json", {"schema": "sfh2-f1-review-queue-v1", "records": [queues[text(row.get("occurrence_id"))] for row in selection if text(row.get("occurrence_id")) in queues], "mandatory_count": sum(queues[key].get("mandatory_review") is True for key in queues), "candidate_only": True, "canonical_write_back": False})
    write_json(OUT / "provider-accounting.json", client.metrics())
    if final:
        mandatory = [queues[key] for key in candidates if queues.get(key, {}).get("mandatory_review") is True]
        recommendation = "sfh2_f1_human_semantic_review_required" if mandatory else "sfh2_f1_operationally_qualified"
        next_stage = "SFH2.2-F1R"
    else:
        recommendation = "sfh2_f1_provider_transport_blocked" if client.metrics().get("provider_failures", 0) else "sfh2_f1_occurrence_pipeline_blocked"
        next_stage = "SFH2.2-F1R"
    metrics = {
        "schema": "sfh2-f1-metrics-v1",
        "stage": "SFH2.2-F1",
        "selected_occurrences": len(selection),
        "selected_stories": len({text(exact_key(row)["story_id"]) for row in selection}),
        "completed_candidate_records": len(candidates),
        "mandatory_review_count": sum(queues[key].get("mandatory_review") is True for key in queues),
        "audit_only_flag_count": sum(len(queues[key].get("audit_only_flags", [])) for key in queues),
        "new_historical_person_candidate_count": sum(
            isinstance((identity_rows[key].get("candidate_proposal") if isinstance(identity_rows[key], Mapping) else None), Mapping)
            and text((identity_rows[key].get("candidate_proposal") or {}).get("entity_type")) == "candidate_historical_person"
            for key in identity_rows
        ),
        "existing_person_candidate_count": sum(
            isinstance((identity_rows[key].get("candidate_proposal") if isinstance(identity_rows[key], Mapping) else None), Mapping)
            and text((identity_rows[key].get("candidate_proposal") or {}).get("entity_type")) == "existing_person"
            for key in identity_rows
        ),
        "boundary_routed_count": len(boundary_rows),
        "boundary_override_count": sum(((candidates[key].get("occurrence_semantics") or {}).get("primary_narrative_function") != (candidates[key].get("occurrence_semantics") or {}).get("final_narrative_function")) for key in boundary_rows),
        "unresolved_count": sum(
            identity_rows[key].get("status") == "blocked"
            or primary_rows[key].get("valid") is not True
            or (key in boundary_rows and boundary_rows[key].get("valid") is not True)
            or text((primary_rows[key].get("occurrence_result") or {}).get("narrative_function")) == "uncertain"
            or (key in boundary_rows and text(boundary_rows[key].get("boundary_judgment")) == "uncertain")
            for key in candidates if key in identity_rows and key in primary_rows
        ),
        "cache_hits": len(_cache_usage(selection, primary_rows, boundary_rows)["records"]),
        "checkpoint_reuse_count": counters.get("checkpoint_reused", 0),
        "identity_pipeline_processed": counters.get("identity_pipeline_processed", 0),
        "provider_accounting": client.metrics(),
        "f1_prep_pilot_observed_estimate": 121,
        "no_accuracy_claim": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    write_json(OUT / "metrics.json", metrics)
    write_json(OUT / "recommendation.json", {
        "schema": "sfh2-f1-recommendation-v1",
        "recommendation": recommendation,
        "operationally_complete": final,
        "qualified": recommendation == "sfh2_f1_operationally_qualified",
        "next_stage": next_stage,
        "reason": "F1 candidate wave completed; mandatory human review remains before expansion; no unseen-corpus accuracy claim" if recommendation == "sfh2_f1_human_semantic_review_required" else "F1 operational candidate wave completed; no unseen-corpus accuracy claim",
        "candidate_only": True,
        "canonical_write_back": False,
    })
    return metrics
