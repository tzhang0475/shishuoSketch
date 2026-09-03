"""Strict compact contract for the A2O occurrence-function historian."""

from __future__ import annotations

from typing import Any, Mapping

from sfh2_a0r.contracts import validate_deepseek_strict_schema

from .provenance import NARRATIVE_FUNCTIONS, text


CONFIDENCES = frozenset({"high", "medium", "low"})
FUNCTION_NAME = "submit_sfh2_a2o_occurrence_function_v1"


def _object(properties: Mapping[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": dict(properties),
        "required": list(required),
    }


def occurrence_function_tool() -> dict[str, Any]:
    parameters = _object({
        "case_id": {"type": "string"},
        "narrative_function": {"type": "string", "enum": sorted(NARRATIVE_FUNCTIONS)},
        "confidence": {"type": "string", "enum": sorted(CONFIDENCES)},
        "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
        "reason_summary": {"type": "string"},
    }, ["case_id", "narrative_function", "confidence", "supporting_evidence_ids", "reason_summary"])
    tool = {
        "type": "function",
        "function": {
            "name": FUNCTION_NAME,
            "description": "Return only the narrative function of the supplied occurrence; frozen identity is not under review.",
            "strict": True,
            "parameters": parameters,
        },
    }
    errors = validate_deepseek_strict_schema(parameters)
    if errors:
        raise ValueError("invalid_deepseek_strict_schema:" + ";".join(errors))
    return tool


def validate_occurrence_payload(packet: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate structure and evidence grounding without interpreting history."""

    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": ["provider_or_schema_failure"], "result": None}
    required = {"case_id", "narrative_function", "confidence", "supporting_evidence_ids", "reason_summary"}
    extra = sorted(set(payload) - required)
    missing = sorted(required - set(payload))
    errors: list[str] = []
    if extra:
        errors.append("unexpected_occurrence_fields:" + ",".join(map(str, extra)))
    if missing:
        errors.append("missing_occurrence_fields:" + ",".join(missing))
    case_id = text(payload.get("case_id"))
    expected_case_id = text(packet.get("case_id"))
    if case_id != expected_case_id:
        errors.append("case_id_mismatch")
    function = text(payload.get("narrative_function"))
    if function not in NARRATIVE_FUNCTIONS:
        errors.append("invalid_narrative_function")
    confidence = text(payload.get("confidence"))
    if confidence not in CONFIDENCES:
        errors.append("invalid_confidence")
    evidence_ids = {
        text(row.get("evidence_id"))
        for row in packet.get("source_evidence", []) or []
        if isinstance(row, Mapping) and text(row.get("evidence_id"))
    }
    supplied = payload.get("supporting_evidence_ids")
    if not isinstance(supplied, list) or not all(isinstance(item, str) for item in supplied):
        errors.append("supporting_evidence_ids_not_string_array")
        supplied = []
    cleaned_ids = sorted({text(item) for item in supplied if text(item)})
    if any(item not in evidence_ids for item in cleaned_ids):
        errors.append("invalid_supporting_evidence_ids")
    reason = payload.get("reason_summary")
    if not isinstance(reason, str):
        errors.append("reason_summary_not_string")
        reason = ""
    result = {
        "case_id": case_id,
        "narrative_function": function,
        "confidence": confidence,
        "supporting_evidence_ids": cleaned_ids,
        "reason_summary": text(reason),
    }
    return {"valid": not errors, "errors": sorted(set(errors)), "result": result if not errors else None}
