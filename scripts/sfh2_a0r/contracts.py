"""A0R structured contracts and deterministic record-selection helpers.

The provider returns semantic records only in Pass 1.  Review stages return a
decision plus, at most, typed narrow patch operations.  This module owns
validation and record copying; it does not interpret historical language.

DeepSeek's strict function mode requires every property of every object to be
required and every object to reject additional properties.  In particular, a
partially populated patch object is not a valid strict schema.  The operation
union below keeps patches narrow without asking the model to reproduce an
entire semantic record.
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


def validate_deepseek_strict_schema(schema: Mapping[str, Any], *, path: str = "$", _root: bool = True) -> list[str]:
    """Return structural errors for the provider's strict JSON-schema subset.

    This is deliberately a schema validator, not a semantic validator.  It
    checks the contract that the provider enforces before a network request:
    closed objects, exact required-property coverage, typed arrays/unions, and
    the small keyword subset used by the frozen semantic schema.  ``pattern``
    is retained because the already accepted primary schema uses it.
    """

    allowed = {"type", "properties", "required", "additionalProperties", "items", "enum", "anyOf", "pattern"}
    errors: list[str] = []
    if not isinstance(schema, Mapping):
        return [f"{path}:schema_not_object"]
    unknown = sorted(set(schema) - allowed)
    errors.extend(f"{path}:unsupported_keyword:{key}" for key in unknown)
    if "anyOf" in schema:
        variants = schema.get("anyOf")
        if not isinstance(variants, list) or not variants:
            errors.append(f"{path}.anyOf:not_nonempty_array")
        else:
            for index, variant in enumerate(variants):
                errors.extend(validate_deepseek_strict_schema(variant, path=f"{path}.anyOf[{index}]", _root=False))
    schema_type = schema.get("type")
    if schema_type is None and "anyOf" not in schema:
        errors.append(f"{path}:unsupported_or_missing_type")
    elif schema_type not in {None, "object", "array", "string", "boolean"}:
        errors.append(f"{path}:unsupported_or_missing_type")
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
            errors.extend(validate_deepseek_strict_schema(schema.get("items"), path=f"{path}.items", _root=False))
    elif schema_type == "string":
        if "enum" in schema and (not isinstance(schema.get("enum"), list) or not all(isinstance(item, str) for item in schema.get("enum", []))):
            errors.append(f"{path}.enum:must_be_string_array")
    if "anyOf" in schema and schema_type is not None:
        errors.append(f"{path}:anyOf_type_combination_unsupported")
    return sorted(set(errors))


def _strict_tool_or_raise(tool: dict[str, Any]) -> dict[str, Any]:
    errors = validate_deepseek_strict_schema(tool["function"]["parameters"])
    if errors:
        raise ValueError("invalid_deepseek_strict_schema:" + ";".join(errors))
    return tool


def _string_operation(path: str, value_schema: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return _object({
        "path": {"type": "string", "enum": [path]},
        "value": dict(value_schema or {"type": "string"}),
    }, ["path", "value"])


def _patch_schema() -> dict[str, Any]:
    """Strict typed operation union; no optional object properties."""

    record = semantic_record_schema()["properties"]
    relation_schema = record["relations"]["items"]
    string_paths = {
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
        "confidence": {"type": "string", "enum": sorted(CONFIDENCES)},
        "attribute_type": {"type": "string"},
        "attribute_value": {"type": "string"},
        "bearer_hint": {"type": "string"},
    }
    variants = [_string_operation(path, value_schema) for path, value_schema in sorted(string_paths.items())]
    variants.extend([
        _object({"path": {"type": "string", "enum": ["abstain"]}, "value": {"type": "boolean"}}, ["path", "value"]),
        _object({"path": {"type": "string", "enum": ["supporting_evidence_ids"]}, "value": {"type": "array", "items": {"type": "string"}}}, ["path", "value"]),
        _object({"path": {"type": "string", "enum": ["relations"]}, "value": {"type": "array", "items": relation_schema}}, ["path", "value"]),
    ])
    return {"type": "array", "items": {"anyOf": variants}}


def _review_properties() -> dict[str, Any]:
    return {
        "decision": {"type": "string", "enum": sorted(REVIEW_DECISIONS)},
        "patch_ops": _patch_schema(),
        "reason_summary": {"type": "string"},
        "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
    }


def critical_review_tool() -> dict[str, Any]:
    return _strict_tool_or_raise(_tool(
        "submit_sfh2_a0r_critical_review_patch_v1",
        "Return confirm, a narrow field-level revision patch, or abstain. Never regenerate the complete semantic record.",
        _review_properties(),
        ["decision", "patch_ops", "reason_summary", "supporting_evidence_ids"],
    ))


def adjudication_tool() -> dict[str, Any]:
    properties = {
        "decision": {"type": "string", "enum": sorted(ADJUDICATION_DECISIONS)},
        "base_record": {"type": "string", "enum": ["", "pass1", "pass2"]},
        "patch_ops": _patch_schema(),
        "reason_summary": {"type": "string"},
        "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
    }
    return _strict_tool_or_raise(_tool(
        "submit_sfh2_a0r_adjudication_selector_v1",
        "Select an existing semantic record exactly, apply a narrow revision patch, or abstain. When selecting, do not reproduce the selected record.",
        properties,
        ["decision", "base_record", "patch_ops", "reason_summary", "supporting_evidence_ids"],
    ))


def _ids(value: Any) -> list[str]:
    return sorted({text(item) for item in value or [] if text(item)}) if isinstance(value, list) else []


def _patch_value_errors(path: str, value: Any) -> list[str]:
    enum_paths = {
        "semantic_kind": SEMANTIC_KINDS,
        "reference_type": REFERENCE_TYPES,
        "referent.confidence": CONFIDENCES,
        "occurrence_role": OCCURRENCE_ROLES,
        "confidence": CONFIDENCES,
    }
    if path in enum_paths:
        return [] if isinstance(value, str) and value in enum_paths[path] else [f"patch_value_invalid_enum:{path}"]
    if path == "abstain":
        return [] if isinstance(value, bool) else ["patch_value_invalid_boolean:abstain"]
    if path in {"relations", "supporting_evidence_ids"}:
        if not isinstance(value, list):
            return [f"patch_value_not_array:{path}"]
        if path == "supporting_evidence_ids" and not all(isinstance(item, str) for item in value):
            return ["patch_value_invalid_string_array:supporting_evidence_ids"]
        if path == "relations" and not all(isinstance(item, Mapping) for item in value):
            return ["patch_value_invalid_relation_array"]
        return []
    return [] if isinstance(value, str) else [f"patch_value_not_string:{path}"]


def _normalize_patch_ops(value: Any, *, packet: Mapping[str, Any], errors: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(value, list):
        errors.append("patch_ops_not_array")
        return [], []
    evidence_ids = {
        text(row.get("evidence_id"))
        for row in (packet.get("source_evidence") or packet.get("evidence") or [])
        if isinstance(row, Mapping) and text(row.get("evidence_id"))
    }
    normalized: list[dict[str, Any]] = []
    paths: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping) or set(item) != {"path", "value"}:
            errors.append(f"patch_ops[{index}]:must_have_exact_path_value")
            continue
        path = text(item.get("path"))
        if path not in PATCHABLE_PATHS:
            errors.append(f"patch_path_not_allowed:{path}")
            continue
        if path in paths:
            errors.append(f"duplicate_patch_path:{path}")
        paths.append(path)
        value_copy = copy.deepcopy(item.get("value"))
        errors.extend(_patch_value_errors(path, value_copy))
        if path == "supporting_evidence_ids" and isinstance(value_copy, list):
            if any(text(item_id) not in evidence_ids for item_id in value_copy):
                errors.append("invalid_patch_supporting_evidence_ids")
            value_copy = _ids(value_copy)
        normalized.append({"path": path, "value": value_copy})
    # Operation ordering is not semantic; canonical ordering makes replay and
    # hashing deterministic while retaining every model-supplied value.
    return sorted(normalized, key=lambda row: row["path"]), sorted(set(paths))


def _legacy_patch_ops(payload: Mapping[str, Any]) -> list[dict[str, Any]] | None:
    """Read the pre-A1R shape only for old local compatibility inputs.

    Provider payload validation deliberately rejects this shape.  The helper
    lets already-materialized offline compatibility rows continue to pass
    through the deterministic selector while the live tool never advertises
    or accepts it.
    """

    if "patch_ops" in payload:
        return None
    patch = payload.get("patch")
    fields = payload.get("reviewed_fields")
    if not isinstance(patch, Mapping) or not isinstance(fields, list):
        return None
    return [{"path": text(path), "value": copy.deepcopy(patch[path])} for path in fields if path in patch]


def validate_review_payload(packet: Mapping[str, Any], payload: Mapping[str, Any] | None, *, adjudication: bool = False) -> dict[str, Any]:
    """Validate a decision/patch envelope without applying semantic judgment."""

    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": ["provider_or_schema_failure"], "review": None}
    allowed = {"decision", "patch_ops", "reason_summary", "supporting_evidence_ids"} | ({"base_record"} if adjudication else set())
    extra = sorted(set(payload) - allowed)
    if extra:
        return {"valid": False, "errors": ["unexpected_review_fields:" + ",".join(map(str, extra))], "review": None}
    decision = text(payload.get("decision"))
    decisions = ADJUDICATION_DECISIONS if adjudication else REVIEW_DECISIONS
    if decision not in decisions:
        return {"valid": False, "errors": ["invalid_adjudication_decision" if adjudication else "invalid_review_decision"], "review": None}
    patch_ops = payload.get("patch_ops")
    support = payload.get("supporting_evidence_ids")
    errors: list[str] = []
    patch_ops, fields = _normalize_patch_ops(patch_ops, packet=packet, errors=errors)
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
        if patch_ops:
            errors.append("non_revision_must_not_patch")
    if decision == "revise" and not patch_ops:
        errors.append("revision_patch_empty")
    cleaned = {
        "decision": decision,
        "base_record": base,
        "reviewed_fields": fields,
        "patch_ops": patch_ops,
        # Derived compatibility view.  It is never sent to the provider.
        "patch": {row["path"]: copy.deepcopy(row["value"]) for row in patch_ops},
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


def apply_patch_ops(base: Mapping[str, Any] | None, patch_ops: list[Mapping[str, Any]] | None, packet: Mapping[str, Any]) -> dict[str, Any]:
    """Apply validated typed operations without inventing semantic values."""

    if not isinstance(base, Mapping):
        return {"valid": False, "errors": ["patch_base_record_missing"], "record": None, "changed_fields": []}
    errors: list[str] = []
    normalized, paths = _normalize_patch_ops(patch_ops, packet=packet, errors=errors)
    if not normalized:
        errors.append("patch_empty")
    if errors:
        return {"valid": False, "errors": sorted(set(errors)), "record": None, "changed_fields": []}
    result = copy.deepcopy(dict(base))
    for operation in normalized:
        _set_path(result, operation["path"], operation["value"])
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


def apply_patch(base: Mapping[str, Any] | None, patch: Mapping[str, Any] | None, reviewed_fields: list[str], packet: Mapping[str, Any]) -> dict[str, Any]:
    """Compatibility adapter for pre-A1R offline rows and unit tests."""

    operations = [{"path": text(path), "value": copy.deepcopy(patch[path])} for path in reviewed_fields if isinstance(patch, Mapping) and path in patch]
    return apply_patch_ops(base, operations, packet)


def effective_review_record(pass1_record: Mapping[str, Any] | None, review: Mapping[str, Any] | None, packet: Mapping[str, Any]) -> dict[str, Any]:
    """Return the deterministic effective record for Pass 2."""

    if not isinstance(review, Mapping) or not review.get("valid"):
        return {"record": None, "source": "invalid_review", "errors": ["review_invalid"]}
    decision = text(review.get("decision"))
    if decision == "confirm":
        return {"record": copy.deepcopy(pass1_record) if isinstance(pass1_record, Mapping) else None, "source": "pass1_confirmed_exact", "errors": []}
    if decision == "abstain":
        return {"record": None, "source": "review_abstained", "errors": []}
    operations = review.get("patch_ops")
    if operations is None:
        operations = _legacy_patch_ops(review)
    applied = apply_patch_ops(pass1_record, operations, packet)
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
    operations = adjudication.get("patch_ops")
    if operations is None:
        operations = _legacy_patch_ops(adjudication)
    applied = apply_patch_ops(base, operations, packet)
    return {"record": applied.get("record"), "source": "adjudication_validated_patch" if applied.get("valid") else "invalid_adjudication_patch", "errors": list(applied.get("errors", [])), "changed_fields": applied.get("changed_fields", [])}


# Public compatibility alias makes the validated-patch contract explicit to
# callers and tests without exposing any semantic policy.
apply_validated_patch = apply_patch
