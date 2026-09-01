"""A2R adjudicator contract and structural selector mechanics.

The provider contract contains no redundant base selector.  ``revise_a`` and
``revise_b`` encode the patch base in the decision itself.  This module only
validates types/paths and copies or patches records; it makes no historical
interpretation.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping

from sfh2_a0r import contracts as a0r_contracts
from .common import text

A2R_DECISIONS = {"select_a", "select_b", "revise_a", "revise_b", "abstain"}


def validate_deepseek_strict_schema(schema: Mapping[str, Any], *, path: str = "$", _root: bool = True) -> list[str]:
    return a0r_contracts.validate_deepseek_strict_schema(schema, path=path, _root=_root)


def historian_b_tool() -> dict[str, Any]:
    # The replacement B call must use precisely the frozen A2 tool.
    from sfh2_a2.contracts import historian_b_tool as frozen_tool
    return copy.deepcopy(frozen_tool())


def adjudicator_tool() -> dict[str, Any]:
    parameters = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "decision": {"type": "string", "enum": sorted(A2R_DECISIONS)},
            "patch_ops": copy.deepcopy(a0r_contracts._patch_schema()),
            "reason_summary": {"type": "string"},
            "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["decision", "patch_ops", "reason_summary", "supporting_evidence_ids"],
    }
    tool = {
        "type": "function",
        "function": {
            "name": "submit_sfh2_a2r_adjudication_v2",
            "description": "Select Historian A or B exactly, apply a narrow typed patch to A or B, or abstain. Never reproduce a selected complete record.",
            "strict": True,
            "parameters": parameters,
        },
    }
    errors = validate_deepseek_strict_schema(parameters)
    if errors:
        raise ValueError("invalid_deepseek_strict_schema:" + ";".join(errors))
    return tool


def _mapped_review(decision: str) -> str:
    return "revise" if decision in {"revise_a", "revise_b"} else "confirm" if decision in {"select_a", "select_b"} else "abstain"


def validate_adjudicator_payload(packet: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": ["provider_or_schema_failure"], "adjudication": None}
    required = {"decision", "patch_ops", "reason_summary", "supporting_evidence_ids"}
    errors: list[str] = []
    extra = sorted(set(payload) - required)
    missing = sorted(required - set(payload))
    if extra:
        errors.append("unexpected_adjudication_fields:" + ",".join(map(str, extra)))
    if missing:
        errors.append("missing_adjudication_fields:" + ",".join(missing))
    if "base_record" in payload:
        errors.append("base_record_forbidden")
    decision = text(payload.get("decision"))
    if decision not in A2R_DECISIONS:
        errors.append("invalid_a2r_adjudication_decision")
    mapped = {
        "decision": _mapped_review(decision),
        "patch_ops": copy.deepcopy(payload.get("patch_ops")),
        "reason_summary": text(payload.get("reason_summary")),
        "supporting_evidence_ids": copy.deepcopy(payload.get("supporting_evidence_ids")),
    }
    review_result = a0r_contracts.validate_review_payload(packet, mapped, adjudication=False)
    errors.extend(review_result.get("errors", []))
    review = review_result.get("review")
    if errors or not isinstance(review, Mapping):
        return {"valid": False, "errors": sorted(set(errors)), "adjudication": None}
    cleaned = {
        "decision": decision,
        "patch_ops": copy.deepcopy(review.get("patch_ops", [])),
        "reviewed_fields": copy.deepcopy(review.get("reviewed_fields", [])),
        "reason_summary": text(payload.get("reason_summary")),
        "supporting_evidence_ids": copy.deepcopy(review.get("supporting_evidence_ids", [])),
    }
    return {"valid": True, "errors": [], "adjudication": cleaned}


def apply_a2r_adjudication(
    historian_a: Mapping[str, Any] | None,
    historian_b: Mapping[str, Any] | None,
    adjudication: Mapping[str, Any] | None,
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(adjudication, Mapping) or adjudication.get("valid") is not True:
        return {"valid": False, "record": None, "source": "invalid_adjudication", "errors": ["adjudication_invalid"], "changed_fields": []}
    decision = text(adjudication.get("decision"))
    if decision == "select_a":
        valid = isinstance(historian_a, Mapping)
        return {"valid": valid, "record": copy.deepcopy(historian_a) if valid else None, "source": "historian_a_exact_copy", "errors": [] if valid else ["selected_a_invalid"], "changed_fields": []}
    if decision == "select_b":
        valid = isinstance(historian_b, Mapping)
        return {"valid": valid, "record": copy.deepcopy(historian_b) if valid else None, "source": "historian_b_exact_copy", "errors": [] if valid else ["selected_b_invalid"], "changed_fields": []}
    if decision == "abstain":
        return {"valid": True, "record": None, "source": "adjudication_abstained", "errors": [], "changed_fields": []}
    base = historian_a if decision == "revise_a" else historian_b if decision == "revise_b" else None
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
