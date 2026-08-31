"""A0R structured contracts and deterministic record-selection helpers.

The provider returns semantic records only in Pass 1.  Review stages return a
decision plus, at most, a narrow field patch.  This module owns validation and
record copying; it does not interpret historical language.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping

from sfh2_a0.schemas import (
    CONFIDENCES,
    OCCURRENCE_ROLES,
    REFERENCE_TYPES,
    RELATIONS,
    SEMANTIC_KINDS,
    semantic_record_schema,
    validate_semantic_payload,
)

from .common import text

REVIEW_DECISIONS = {"confirm", "revise", "abstain"}
ADJUDICATION_DECISIONS = {"select_pass1", "select_pass2", "revise", "abstain"}

# Paths are deliberately structural.  They are not a catalogue of historical
# forms and contain no language-specific semantics.
PATCHABLE_PATHS = frozenset({
    "semantic_kind",
    "reference_type",
    "referent.surface_form",
    "referent.canonical_hint",
    "referent.confidence",
    "occurrence_role",
    "discourse.speaker_hint",
    "discourse.addressee_hint",
    "discourse.antecedent_hint",
    "discourse.self_reference_hint",
    "relations",
    "confidence",
    "supporting_evidence_ids",
    "attribute_type",
    "attribute_value",
    "bearer_hint",
    "abstain",
})

SEMANTIC_COMPARISON_PATHS = frozenset(PATCHABLE_PATHS)

# Confidence/evidence-list edits are auditable metadata, but do not by
# themselves constitute a competing historical hypothesis.  A0R may record
# such a patch without spending a third semantic pass.  Any change to an
# interpretation, role, discourse field, relation, or abstention remains
# substantive and can require adjudication.
SUBSTANTIVE_SEMANTIC_PATHS = frozenset(SEMANTIC_COMPARISON_PATHS - {
    "confidence",
    "referent.confidence",
    "supporting_evidence_ids",
})


def _object(properties: Mapping[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": dict(properties),
        "required": list(required),
    }


def _tool(name: str, description: str, properties: Mapping[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "strict": True,
            "parameters": _object(properties, required),
        },
    }


def semantic_record_tool() -> dict[str, Any]:
    schema = semantic_record_schema()
    return _tool(
        "submit_sfh2_a0r_primary_semantics_v1",
        "Return one complete evidence-grounded semantic record. Do not emit production Person IDs.",
        {"record": schema},
        ["record"],
    )


def _patch_schema() -> dict[str, Any]:
    record = semantic_record_schema()["properties"]
    relation_schema = record["relations"]["items"]
    return _object({
        "semantic_kind": {"type": "string", "enum": sorted(SEMANTIC_KINDS)},
        "reference_type": {"type": "string", "enum": sorted(REFERENCE_TYPES)},
        "referent.surface_form": {"type": "string"},
        "referent.canonical_hint": {"type": "string"},
        "referent.confidence": {"type": "string", "enum": sorted(CONFIDENCES)},
        "occurrence_role": {"type": "string", "enum": sorted(OCCURRENCE_ROLES)},
        "discourse.speaker_hint": {"type": "string"},
        "discourse.addressee_hint": {"type": "string"},
        "discourse.antecedent_hint": {"type": "string"},
        "discourse.self_reference_hint": {"type": "string"},
        "relations": {"type": "array", "items": relation_schema},
        "confidence": {"type": "string", "enum": sorted(CONFIDENCES)},
        "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
        "attribute_type": {"type": "string"},
        "attribute_value": {"type": "string"},
        "bearer_hint": {"type": "string"},
        "abstain": {"type": "boolean"},
    }, [])


def _review_properties() -> dict[str, Any]:
    return {
        "decision": {"type": "string", "enum": sorted(REVIEW_DECISIONS)},
        "reviewed_fields": {"type": "array", "items": {"type": "string", "enum": sorted(PATCHABLE_PATHS)}},
        "patch": _patch_schema(),
        "reason_summary": {"type": "string"},
        "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
    }


def critical_review_tool() -> dict[str, Any]:
    return _tool(
        "submit_sfh2_a0r_critical_review_patch_v1",
        "Return confirm, a narrow field-level revision patch, or abstain. Never regenerate the complete semantic record.",
        _review_properties(),
        ["decision", "reviewed_fields", "patch", "reason_summary", "supporting_evidence_ids"],
    )


def adjudication_tool() -> dict[str, Any]:
    properties = {
        "decision": {"type": "string", "enum": sorted(ADJUDICATION_DECISIONS)},
        "base_record": {"type": "string", "enum": ["", "pass1", "pass2"]},
        "reviewed_fields": {"type": "array", "items": {"type": "string", "enum": sorted(PATCHABLE_PATHS)}},
        "patch": _patch_schema(),
        "reason_summary": {"type": "string"},
        "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
    }
    return _tool(
        "submit_sfh2_a0r_adjudication_selector_v1",
        "Select an existing semantic record exactly, apply a narrow revision patch, or abstain. When selecting, do not reproduce the selected record.",
        properties,
        ["decision", "base_record", "reviewed_fields", "patch", "reason_summary", "supporting_evidence_ids"],
    )


def _ids(value: Any) -> list[str]:
    return sorted({text(item) for item in value or [] if text(item)}) if isinstance(value, list) else []


def validate_review_payload(packet: Mapping[str, Any], payload: Mapping[str, Any] | None, *, adjudication: bool = False) -> dict[str, Any]:
    """Validate a decision/patch envelope without applying semantic judgment."""

    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": ["provider_or_schema_failure"], "review": None}
    allowed = {"decision", "base_record", "reviewed_fields", "patch", "reason_summary", "supporting_evidence_ids"}
    extra = sorted(set(payload) - allowed)
    if extra:
        return {"valid": False, "errors": ["unexpected_review_fields:" + ",".join(map(str, extra))], "review": None}
    decision = text(payload.get("decision"))
    decisions = ADJUDICATION_DECISIONS if adjudication else REVIEW_DECISIONS
    if decision not in decisions:
        return {"valid": False, "errors": ["invalid_adjudication_decision" if adjudication else "invalid_review_decision"], "review": None}
    fields = payload.get("reviewed_fields")
    patch = payload.get("patch")
    support = payload.get("supporting_evidence_ids")
    errors: list[str] = []
    if not isinstance(fields, list) or not all(isinstance(value, str) and text(value) in PATCHABLE_PATHS for value in fields):
        errors.append("invalid_reviewed_fields")
        fields = []
    fields = [text(value) for value in fields]
    if len(set(fields)) != len(fields):
        errors.append("duplicate_reviewed_fields")
    if not isinstance(patch, Mapping):
        errors.append("patch_not_object")
        patch = {}
    patch = {text(key): copy.deepcopy(value) for key, value in patch.items()}
    if any(key not in PATCHABLE_PATHS for key in patch):
        errors.append("patch_path_not_allowed")
    if set(fields) != set(patch):
        if decision == "revise":
            errors.append("reviewed_fields_patch_mismatch")
        elif fields or patch:
            errors.append("selection_must_not_contain_patch")
    if not isinstance(support, list):
        errors.append("supporting_evidence_ids_not_array")
        support = []
    evidence_ids = {
        text(row.get("evidence_id"))
        for row in (packet.get("source_evidence") or packet.get("evidence") or [])
        if isinstance(row, Mapping) and text(row.get("evidence_id"))
    }
    support = _ids(support)
    if any(value not in evidence_ids for value in support):
        errors.append("invalid_review_supporting_evidence_ids")
    base = text(payload.get("base_record"))
    if adjudication:
        if decision == "revise" and base not in {"pass1", "pass2"}:
            errors.append("revision_base_record_missing")
        if decision != "revise" and base:
            errors.append("selection_base_record_must_be_empty")
    elif "base_record" in payload:
        errors.append("unexpected_base_record")
    if decision in ({"confirm", "select_pass1", "select_pass2", "abstain"}):
        if fields or patch:
            errors.append("non_revision_must_not_patch")
    if decision == "revise" and not patch:
        errors.append("revision_patch_empty")
    cleaned = {
        "decision": decision,
        "base_record": base,
        "reviewed_fields": fields,
        "patch": patch,
        "reason_summary": text(payload.get("reason_summary")),
        "supporting_evidence_ids": support,
    }
    return {"valid": not errors, "errors": sorted(set(errors)), "review": cleaned if not errors else None}


def validate_critical_review_payload(packet: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    return validate_review_payload(packet, payload, adjudication=False)


def validate_adjudication_payload(packet: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    result = validate_review_payload(packet, payload, adjudication=True)
    return {"valid": result["valid"], "errors": result["errors"], "adjudication": result.get("review")}


def _get_path(record: Mapping[str, Any], path: str) -> Any:
    value: Any = record
    for part in path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return None
        value = value[part]
    return value


def _set_path(record: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    target = record
    for part in parts[:-1]:
        child = target.get(part)
        if not isinstance(child, dict):
            child = {}
            target[part] = child
        target = child
    target[parts[-1]] = copy.deepcopy(value)


def semantic_diff_paths(left: Mapping[str, Any] | None, right: Mapping[str, Any] | None) -> list[str]:
    """Return semantic field paths, excluding explanatory prose."""

    if not isinstance(left, Mapping) or not isinstance(right, Mapping):
        return ["record"]
    changed: list[str] = []
    for path in sorted(SEMANTIC_COMPARISON_PATHS):
        if _get_path(left, path) != _get_path(right, path):
            changed.append(path)
    return changed


def semantic_equal(left: Mapping[str, Any] | None, right: Mapping[str, Any] | None) -> bool:
    return not semantic_diff_paths(left, right)


def substantive_semantic_diff_paths(left: Mapping[str, Any] | None, right: Mapping[str, Any] | None) -> list[str]:
    """Return only changes that alter a semantic hypothesis.

    This is a structural comparison helper, not a historical judgment.  It
    prevents confidence/evidence bookkeeping from causing a redundant Pass 3
    while preserving escalation for interpretation or role changes.
    """

    if not isinstance(left, Mapping) or not isinstance(right, Mapping):
        return ["record"]
    return [
        path for path in semantic_diff_paths(left, right)
        if path in SUBSTANTIVE_SEMANTIC_PATHS
    ]


def apply_patch(base: Mapping[str, Any] | None, patch: Mapping[str, Any] | None, reviewed_fields: list[str], packet: Mapping[str, Any]) -> dict[str, Any]:
    """Apply and validate a provider patch; no semantic value is invented."""

    if not isinstance(base, Mapping):
        return {"valid": False, "errors": ["patch_base_record_missing"], "record": None, "changed_fields": []}
    if not isinstance(patch, Mapping) or not patch:
        return {"valid": False, "errors": ["patch_empty"], "record": None, "changed_fields": []}
    paths = [text(value) for value in reviewed_fields]
    if set(paths) != {text(key) for key in patch} or any(path not in PATCHABLE_PATHS for path in paths):
        return {"valid": False, "errors": ["patch_reviewed_fields_mismatch"], "record": None, "changed_fields": []}
    result = copy.deepcopy(dict(base))
    for path, value in patch.items():
        _set_path(result, text(path), value)
    changed = semantic_diff_paths(base, result)
    if not set(changed).issubset(set(paths)):
        return {"valid": False, "errors": ["undeclared_patch_mutation"], "record": None, "changed_fields": changed}
    target = {
        "mention_id": result.get("mention_id"),
        "surface": result.get("surface"),
    }
    validated = validate_semantic_payload(packet, target, {"record": result})
    if not validated.get("valid"):
        return {"valid": False, "errors": [f"patched_record:{error}" for error in validated.get("errors", [])], "record": None, "changed_fields": changed}
    return {"valid": True, "errors": [], "record": validated.get("record"), "changed_fields": changed}


def effective_review_record(pass1_record: Mapping[str, Any] | None, review: Mapping[str, Any] | None, packet: Mapping[str, Any]) -> dict[str, Any]:
    """Return the deterministic effective record for Pass 2."""

    if not isinstance(review, Mapping) or not review.get("valid"):
        return {"record": None, "source": "invalid_review", "errors": ["review_invalid"]}
    decision = text(review.get("decision"))
    if decision == "confirm":
        return {"record": copy.deepcopy(pass1_record) if isinstance(pass1_record, Mapping) else None, "source": "pass1_confirmed_exact", "errors": []}
    if decision == "abstain":
        return {"record": None, "source": "review_abstained", "errors": []}
    applied = apply_patch(pass1_record, review.get("patch"), list(review.get("reviewed_fields") or []), packet)
    return {"record": applied.get("record"), "source": "pass2_validated_patch" if applied.get("valid") else "invalid_patch", "errors": list(applied.get("errors", [])), "changed_fields": applied.get("changed_fields", [])}


def effective_adjudication(pass1_record: Mapping[str, Any] | None, pass2_record: Mapping[str, Any] | None, adjudication: Mapping[str, Any] | None, packet: Mapping[str, Any]) -> dict[str, Any]:
    """Select or patch an existing record without semantic regeneration."""

    if not isinstance(adjudication, Mapping) or not adjudication.get("valid"):
        return {"record": None, "source": "invalid_adjudication", "errors": ["adjudication_invalid"]}
    decision = text(adjudication.get("decision"))
    if decision == "select_pass1":
        return {"record": copy.deepcopy(pass1_record) if isinstance(pass1_record, Mapping) else None, "source": "pass1_exact_copy", "errors": []}
    if decision == "select_pass2":
        return {"record": copy.deepcopy(pass2_record) if isinstance(pass2_record, Mapping) else None, "source": "pass2_exact_copy", "errors": []}
    if decision == "abstain":
        return {"record": None, "source": "adjudication_abstained", "errors": []}
    base_name = text(adjudication.get("base_record"))
    base = pass1_record if base_name == "pass1" else pass2_record if base_name == "pass2" else None
    applied = apply_patch(base, adjudication.get("patch"), list(adjudication.get("reviewed_fields") or []), packet)
    return {"record": applied.get("record"), "source": "adjudication_validated_patch" if applied.get("valid") else "invalid_adjudication_patch", "errors": list(applied.get("errors", [])), "changed_fields": applied.get("changed_fields", [])}


# Public compatibility alias makes the validated-patch contract explicit to
# callers and tests without exposing any semantic policy.
apply_validated_patch = apply_patch
