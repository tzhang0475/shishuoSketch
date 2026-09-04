"""Strict narrow contract for the blind A2OVB boundary validator."""

from __future__ import annotations

from typing import Any, Mapping

from .common import BOUNDARY_JUDGMENTS, CONFIDENCES, FUNCTION_NAME, text


def _object(properties: Mapping[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": dict(properties),
        "required": list(required),
        "additionalProperties": False,
    }


def validate_deepseek_strict_schema(schema: Mapping[str, Any], *, path: str = "$") -> list[str]:
    allowed = {"type", "properties", "required", "additionalProperties", "items", "enum"}
    if not isinstance(schema, Mapping):
        return [f"{path}:schema_not_object"]
    errors = [f"{path}:unsupported_keyword:{key}" for key in sorted(set(schema) - allowed)]
    schema_type = schema.get("type")
    if schema_type not in {"object", "array", "string", "boolean"}:
        errors.append(f"{path}:unsupported_or_missing_type:{schema_type}")
    if schema_type == "object":
        properties = schema.get("properties")
        required = schema.get("required")
        if not isinstance(properties, Mapping):
            errors.append(f"{path}.properties:not_object")
            properties = {}
        if not isinstance(required, list) or not all(isinstance(value, str) for value in required):
            errors.append(f"{path}.required:not_string_array")
            required = []
        if schema.get("additionalProperties") is not False:
            errors.append(f"{path}.additionalProperties:must_be_false")
        if set(properties) != set(required):
            errors.append(f"{path}:required_must_equal_properties")
        for key, child in properties.items():
            errors.extend(validate_deepseek_strict_schema(child, path=f"{path}.properties.{key}"))
    elif schema_type == "array":
        if "items" not in schema:
            errors.append(f"{path}.items:missing")
        else:
            errors.extend(validate_deepseek_strict_schema(schema["items"], path=f"{path}.items"))
    elif schema_type == "string" and "enum" in schema:
        enum = schema.get("enum")
        if not isinstance(enum, list) or not all(isinstance(value, str) for value in enum):
            errors.append(f"{path}.enum:must_be_string_array")
    return sorted(set(errors))


def boundary_tool() -> dict[str, Any]:
    parameters = _object(
        {
            "case_id": {"type": "string"},
            "boundary_judgment": {"type": "string", "enum": list(BOUNDARY_JUDGMENTS)},
            "confidence": {"type": "string", "enum": list(CONFIDENCES)},
            "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
            "reason_summary": {"type": "string"},
        },
        ["case_id", "boundary_judgment", "confidence", "supporting_evidence_ids", "reason_summary"],
    )
    errors = validate_deepseek_strict_schema(parameters)
    if errors:
        raise ValueError("invalid_deepseek_strict_schema:" + ";".join(errors))
    return {
        "type": "function",
        "function": {
            "name": FUNCTION_NAME,
            "description": "Return only the event-participation boundary judgment for the exact target occurrence.",
            "strict": True,
            "parameters": parameters,
        },
    }


def validate_probe_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": ["provider_or_schema_failure"]}
    required = {"case_id", "boundary_judgment", "confidence", "supporting_evidence_ids", "reason_summary"}
    errors: list[str] = []
    if set(payload) != required:
        errors.append("probe_properties_not_exact")
    if not isinstance(payload.get("case_id"), str):
        errors.append("probe_case_id_not_string")
    if payload.get("boundary_judgment") not in BOUNDARY_JUDGMENTS:
        errors.append("probe_boundary_judgment_invalid")
    if payload.get("confidence") not in CONFIDENCES:
        errors.append("probe_confidence_invalid")
    if not isinstance(payload.get("supporting_evidence_ids"), list) or not all(isinstance(value, str) for value in payload.get("supporting_evidence_ids", [])):
        errors.append("probe_evidence_ids_invalid")
    if not isinstance(payload.get("reason_summary"), str):
        errors.append("probe_reason_invalid")
    return {"valid": not errors, "errors": sorted(set(errors))}


def validate_boundary_payload(packet: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": ["provider_or_schema_failure"], "result": None}
    required = {"case_id", "boundary_judgment", "confidence", "supporting_evidence_ids", "reason_summary"}
    errors: list[str] = []
    extra = sorted(set(payload) - required)
    missing = sorted(required - set(payload))
    if extra:
        errors.append("unexpected_boundary_fields:" + ",".join(map(str, extra)))
    if missing:
        errors.append("missing_boundary_fields:" + ",".join(missing))
    case_id = text(payload.get("case_id"))
    if case_id != text(packet.get("case_id")):
        errors.append("case_id_mismatch")
    judgment = text(payload.get("boundary_judgment"))
    if judgment not in BOUNDARY_JUDGMENTS:
        errors.append("invalid_boundary_judgment")
    confidence = text(payload.get("confidence"))
    if confidence not in CONFIDENCES:
        errors.append("invalid_confidence")
    evidence_ids = {
        text(row.get("evidence_id"))
        for row in packet.get("nearby_source_evidence", []) or []
        if isinstance(row, Mapping) and text(row.get("evidence_id"))
    }
    supplied = payload.get("supporting_evidence_ids")
    if not isinstance(supplied, list) or not all(isinstance(value, str) for value in supplied):
        errors.append("supporting_evidence_ids_not_string_array")
        supplied = []
    cleaned = sorted({text(value) for value in supplied if text(value)})
    if any(value not in evidence_ids for value in cleaned):
        errors.append("invalid_supporting_evidence_ids")
    reason = payload.get("reason_summary")
    if not isinstance(reason, str):
        errors.append("reason_summary_not_string")
        reason = ""
    result = {
        "case_id": case_id,
        "boundary_judgment": judgment,
        "confidence": confidence,
        "supporting_evidence_ids": cleaned,
        "reason_summary": text(reason),
    }
    return {"valid": not errors, "errors": sorted(set(errors)), "result": result if not errors else None}
