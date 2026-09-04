"""Strict contract and structural validation for the A2OV reviewer."""

from __future__ import annotations

from typing import Any, Mapping

from .common import FUNCTION_NAME, NARRATIVE_FUNCTIONS, text


CONFIDENCES = ("low", "medium", "high")
DECISIONS = ("confirm_primary", "revise_function", "abstain")


def _object(properties: Mapping[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": dict(properties),
        "required": list(required),
        "additionalProperties": False,
    }


def validate_deepseek_strict_schema(schema: Mapping[str, Any], *, path: str = "$", _root: bool = True) -> list[str]:
    """Validate the provider-compatible closed-object subset.

    A2OV owns this wrapper so nullable ``revised_narrative_function`` remains
    a real JSON null without changing the frozen A2OR validator.
    """

    allowed = {"type", "properties", "required", "additionalProperties", "items", "enum", "anyOf"}
    if not isinstance(schema, Mapping):
        return [f"{path}:schema_not_object"]
    errors = [f"{path}:unsupported_keyword:{key}" for key in sorted(set(schema) - allowed)]
    if "anyOf" in schema:
        variants = schema.get("anyOf")
        if not isinstance(variants, list) or not variants:
            errors.append(f"{path}.anyOf:not_nonempty_array")
        else:
            for index, variant in enumerate(variants):
                errors.extend(validate_deepseek_strict_schema(variant, path=f"{path}.anyOf[{index}]", _root=False))
    schema_type = schema.get("type")
    supported = {"object", "array", "string", "boolean", "null"}
    if schema_type is None and "anyOf" not in schema:
        errors.append(f"{path}:type_missing")
    elif schema_type not in supported and schema_type is not None:
        errors.append(f"{path}:unsupported_type:{schema_type}")
    if "anyOf" in schema and schema_type is not None:
        errors.append(f"{path}:anyOf_type_combination_unsupported")
    if schema_type == "object":
        properties = schema.get("properties")
        required = schema.get("required")
        if not isinstance(properties, Mapping):
            errors.append(f"{path}.properties:not_object")
            properties = {}
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            errors.append(f"{path}.required:not_string_array")
            required = []
        if schema.get("additionalProperties") is not False:
            errors.append(f"{path}.additionalProperties:must_be_false")
        if set(properties) != set(required):
            errors.append(f"{path}:required_must_equal_properties")
        for key, child in properties.items():
            errors.extend(validate_deepseek_strict_schema(child, path=f"{path}.properties.{key}", _root=False))
    elif schema_type == "array":
        if "items" not in schema:
            errors.append(f"{path}.items:missing")
        else:
            errors.extend(validate_deepseek_strict_schema(schema["items"], path=f"{path}.items", _root=False))
    elif schema_type == "string" and "enum" in schema:
        enum = schema.get("enum")
        if not isinstance(enum, list) or not all(isinstance(value, str) for value in enum):
            errors.append(f"{path}.enum:must_be_string_array")
    return sorted(set(errors))


def reviewer_tool() -> dict[str, Any]:
    parameters = _object(
        {
            "case_id": {"type": "string"},
            "decision": {"type": "string", "enum": list(DECISIONS)},
            "revised_narrative_function": {
                "anyOf": [
                    {"type": "string", "enum": list(NARRATIVE_FUNCTIONS)},
                    {"type": "null"},
                ]
            },
            "confidence": {"type": "string", "enum": list(CONFIDENCES)},
            "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
            "reason_summary": {"type": "string"},
        },
        [
            "case_id",
            "decision",
            "revised_narrative_function",
            "confidence",
            "supporting_evidence_ids",
            "reason_summary",
        ],
    )
    errors = validate_deepseek_strict_schema(parameters)
    if errors:
        raise ValueError("invalid_deepseek_strict_schema:" + ";".join(errors))
    return {
        "type": "function",
        "function": {
            "name": FUNCTION_NAME,
            "description": "Critically review only the primary narrative function of the exact target occurrence.",
            "strict": True,
            "parameters": parameters,
        },
    }


def validate_reviewer_payload(
    packet: Mapping[str, Any],
    payload: Mapping[str, Any] | None,
    primary_function: str,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": ["provider_or_schema_failure"], "result": None}
    required = {
        "case_id",
        "decision",
        "revised_narrative_function",
        "confidence",
        "supporting_evidence_ids",
        "reason_summary",
    }
    errors: list[str] = []
    extra = sorted(set(payload) - required)
    missing = sorted(required - set(payload))
    if extra:
        errors.append("unexpected_reviewer_fields:" + ",".join(map(str, extra)))
    if missing:
        errors.append("missing_reviewer_fields:" + ",".join(missing))
    if text(payload.get("case_id")) != text(packet.get("case_id")):
        errors.append("case_id_mismatch")
    decision = text(payload.get("decision"))
    if decision not in DECISIONS:
        errors.append("invalid_reviewer_decision")
    revised = payload.get("revised_narrative_function")
    if revised is not None and (not isinstance(revised, str) or revised not in NARRATIVE_FUNCTIONS):
        errors.append("invalid_revised_narrative_function")
    if decision in {"confirm_primary", "abstain"} and revised is not None:
        errors.append("non_null_revision_on_non_revision")
    if decision == "revise_function" and (revised is None or revised == primary_function):
        errors.append("revision_must_change_primary_function")
    confidence = text(payload.get("confidence"))
    if confidence not in CONFIDENCES:
        errors.append("invalid_reviewer_confidence")
    supplied = payload.get("supporting_evidence_ids")
    evidence_ids = {
        text(row.get("evidence_id"))
        for row in packet.get("source_evidence", []) or []
        if isinstance(row, Mapping) and text(row.get("evidence_id"))
    }
    if not isinstance(supplied, list) or not all(isinstance(value, str) for value in supplied):
        errors.append("supporting_evidence_ids_not_string_array")
        supplied = []
    evidence = sorted({text(value) for value in supplied if text(value)})
    if any(value not in evidence_ids for value in evidence):
        errors.append("invalid_supporting_evidence_ids")
    reason = payload.get("reason_summary")
    if not isinstance(reason, str):
        errors.append("reason_summary_not_string")
        reason = ""
    result = {
        "case_id": text(payload.get("case_id")),
        "decision": decision,
        "revised_narrative_function": revised,
        "confidence": confidence,
        "supporting_evidence_ids": evidence,
        "reason_summary": text(reason),
    }
    return {"valid": not errors, "errors": sorted(set(errors)), "result": result if not errors else None}


def validate_probe_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Check only the transport/schema shape of the probe response.

    A probe has no semantic target, so the conditional decision rule is not
    evaluated here.  Case-level calls are validated against their primary
    function by ``validate_reviewer_payload``.
    """

    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": ["provider_or_schema_failure"]}
    required = {
        "case_id",
        "decision",
        "revised_narrative_function",
        "confidence",
        "supporting_evidence_ids",
        "reason_summary",
    }
    errors: list[str] = []
    if set(payload) != required:
        errors.append("probe_properties_not_exact")
    if not isinstance(payload.get("case_id"), str):
        errors.append("probe_case_id_not_string")
    if payload.get("decision") not in DECISIONS:
        errors.append("probe_decision_invalid")
    revised = payload.get("revised_narrative_function")
    if revised is not None and (not isinstance(revised, str) or revised not in NARRATIVE_FUNCTIONS):
        errors.append("probe_revised_function_invalid")
    if payload.get("confidence") not in CONFIDENCES:
        errors.append("probe_confidence_invalid")
    if not isinstance(payload.get("supporting_evidence_ids"), list) or not all(isinstance(value, str) for value in payload.get("supporting_evidence_ids", [])):
        errors.append("probe_evidence_ids_invalid")
    if not isinstance(payload.get("reason_summary"), str):
        errors.append("probe_reason_invalid")
    return {"valid": not errors, "errors": sorted(set(errors))}
