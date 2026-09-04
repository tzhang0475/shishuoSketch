"""Strict, identity-free A2OR occurrence-function contract."""

from __future__ import annotations

from typing import Any, Mapping

from sfh2_a0r.contracts import validate_deepseek_strict_schema
from sfh2_a2o.contracts import validate_occurrence_payload as _validate_a2o_payload
from sfh2_a2o.provenance import NARRATIVE_FUNCTIONS


CONFIDENCES = frozenset({"high", "medium", "low"})


def _object(properties: Mapping[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": dict(properties),
        "required": list(required),
        "additionalProperties": False,
    }


def occurrence_function_tool() -> dict[str, Any]:
    parameters = _object(
        {
            "case_id": {"type": "string"},
            "narrative_function": {"type": "string", "enum": sorted(NARRATIVE_FUNCTIONS)},
            "confidence": {"type": "string", "enum": sorted(CONFIDENCES)},
            "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
            "reason_summary": {"type": "string"},
        },
        ["case_id", "narrative_function", "confidence", "supporting_evidence_ids", "reason_summary"],
    )
    errors = validate_deepseek_strict_schema(parameters)
    if errors:
        raise ValueError("invalid_deepseek_strict_schema:" + ";".join(errors))
    return {
        "type": "function",
        "function": {
            "name": "submit_sfh2_a2or_occurrence_function_v2",
            "description": "Return only the target occurrence narrative function; identity and provenance are frozen inputs.",
            "strict": True,
            "parameters": parameters,
        },
    }


def validate_occurrence_payload(packet: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Reuse the proven structural validator with the A2OR local contract."""

    return _validate_a2o_payload(packet, payload)
