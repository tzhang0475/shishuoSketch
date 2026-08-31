"""A2 strict contracts and exact selector operations.

This module contains structural validation only.  It has no historical name
or surface rules.  The semantic record ontology is the frozen A0R ontology;
only the independent stage/function labels and adjudicator decisions differ.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping

from sfh2_a0r import contracts as a0r_contracts

from .common import text

A2_ADJUDICATION_DECISIONS = {"select_a", "select_b", "revise", "abstain"}


def validate_deepseek_strict_schema(schema: Mapping[str, Any], *, path: str = "$", _root: bool = True) -> list[str]:
    return a0r_contracts.validate_deepseek_strict_schema(schema, path=path, _root=_root)


def historian_b_tool() -> dict[str, Any]:
    tool = copy.deepcopy(a0r_contracts.semantic_record_tool())
    tool["function"]["name"] = "submit_sfh2_a2_independent_historian_v1"
    tool["function"]["description"] = "Return one complete independent evidence-grounded semantic record. Do not emit production Person IDs."
    errors = validate_deepseek_strict_schema(tool["function"]["parameters"])
    if errors:
        raise ValueError("invalid_deepseek_strict_schema:" + ";".join(errors))
    return tool


def _object(properties: Mapping[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": dict(properties),
        "required": list(required),
    }


def adjudicator_tool() -> dict[str, Any]:
    parameters = _object({
        "decision": {"type": "string", "enum": sorted(A2_ADJUDICATION_DECISIONS)},
        "base_record": {"type": "string", "enum": ["", "historian_a", "historian_b"]},
        "patch_ops": copy.deepcopy(a0r_contracts._patch_schema()),
        "reason_summary": {"type": "string"},
        "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
    }, ["decision", "base_record", "patch_ops", "reason_summary", "supporting_evidence_ids"])
    tool = {
        "type": "function",
        "function": {
            "name": "submit_sfh2_a2_disagreement_adjudication_v1",
            "description": "Select Historian A or B exactly, apply a narrow typed patch, or abstain. Never reproduce a selected complete record.",
            "strict": True,
            "parameters": parameters,
        },
    }
    errors = validate_deepseek_strict_schema(parameters)
    if errors:
        raise ValueError("invalid_deepseek_strict_schema:" + ";".join(errors))
    return tool


def _mapped_payload(payload: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    decision = text(payload.get("decision"))
    mapped = dict(payload)
    if decision == "select_a":
        mapped["decision"] = "select_pass1"
    elif decision == "select_b":
        mapped["decision"] = "select_pass2"
    base = text(payload.get("base_record"))
    if base == "historian_a":
        mapped["base_record"] = "pass1"
    elif base == "historian_b":
        mapped["base_record"] = "pass2"
    return mapped, decision


def validate_adjudicator_payload(packet: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": ["provider_or_schema_failure"], "adjudication": None}
    required = {"decision", "base_record", "patch_ops", "reason_summary", "supporting_evidence_ids"}
    extra = sorted(set(payload) - required)
    missing = sorted(required - set(payload))
    errors = ["unexpected_adjudication_fields:" + ",".join(map(str, extra))] if extra else []
    if missing:
        errors.append("missing_adjudication_fields:" + ",".join(missing))
    decision = text(payload.get("decision"))
    base = text(payload.get("base_record"))
    if decision not in A2_ADJUDICATION_DECISIONS:
        errors.append("invalid_a2_adjudication_decision")
    if decision == "revise" and base not in {"historian_a", "historian_b"}:
        errors.append("revision_base_record_missing")
    if decision != "revise" and base:
        errors.append("selection_base_record_must_be_empty")
    mapped, _ = _mapped_payload(payload)
    mapped_result = a0r_contracts.validate_review_payload(packet, mapped, adjudication=True)
    errors.extend(mapped_result.get("errors", []))
    review = mapped_result.get("review")
    if errors or not isinstance(review, Mapping):
        return {"valid": False, "errors": sorted(set(errors)), "adjudication": None}
    cleaned = {
        "decision": decision,
        "base_record": base,
        "patch_ops": copy.deepcopy(review.get("patch_ops", [])),
        "reviewed_fields": copy.deepcopy(review.get("reviewed_fields", [])),
        "patch": copy.deepcopy(review.get("patch", {})),
        "reason_summary": text(payload.get("reason_summary")),
        "supporting_evidence_ids": copy.deepcopy(review.get("supporting_evidence_ids", [])),
    }
    return {"valid": True, "errors": [], "adjudication": cleaned}


def apply_a2_adjudication(
    historian_a: Mapping[str, Any] | None,
    historian_b: Mapping[str, Any] | None,
    adjudication: Mapping[str, Any] | None,
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    """Perform exact selection or a validated narrow patch."""

    if not isinstance(adjudication, Mapping) or adjudication.get("valid") is not True:
        return {"valid": False, "record": None, "source": "invalid_adjudication", "errors": ["adjudication_invalid"], "changed_fields": []}
    decision = text(adjudication.get("decision"))
    if decision == "select_a":
        return {"valid": isinstance(historian_a, Mapping), "record": copy.deepcopy(historian_a) if isinstance(historian_a, Mapping) else None, "source": "historian_a_exact_copy", "errors": [] if isinstance(historian_a, Mapping) else ["selected_a_invalid"], "changed_fields": []}
    if decision == "select_b":
        return {"valid": isinstance(historian_b, Mapping), "record": copy.deepcopy(historian_b) if isinstance(historian_b, Mapping) else None, "source": "historian_b_exact_copy", "errors": [] if isinstance(historian_b, Mapping) else ["selected_b_invalid"], "changed_fields": []}
    if decision == "abstain":
        return {"valid": True, "record": None, "source": "adjudication_abstained", "errors": [], "changed_fields": []}
    base_name = text(adjudication.get("base_record"))
    base = historian_a if base_name == "historian_a" else historian_b if base_name == "historian_b" else None
    applied = a0r_contracts.apply_patch_ops(base, adjudication.get("patch_ops"), packet)
    return {
        "valid": applied.get("valid") is True,
        "record": copy.deepcopy(applied.get("record")) if applied.get("valid") else None,
        "source": "adjudication_validated_patch" if applied.get("valid") else "invalid_adjudication_patch",
        "errors": list(applied.get("errors", [])),
        "changed_fields": list(applied.get("changed_fields", [])),
    }


def exact_copy_ok(selected: Mapping[str, Any] | None, source: Mapping[str, Any] | None) -> bool:
    return isinstance(selected, Mapping) and isinstance(source, Mapping) and dict(selected) == dict(source)
