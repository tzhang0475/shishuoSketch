"""Strict structured contracts for the three A0 semantic passes.

The enums here describe the semantic ontology exposed to the provider.  They
are not a table of Chinese forms and contain no historical identity rules.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from .common import evidence_index, text

SEMANTIC_KINDS = {
    "historical_person", "person_attribute", "collective", "office", "place",
    "work", "structural", "other", "uncertain",
}
REFERENCE_TYPES = {
    "full_name", "personal_name", "courtesy_name", "style_name", "nickname",
    "surname_reference", "abbreviated_reference", "office_title", "honorific",
    "ruler_title", "kinship_reference", "pronoun_reference", "addressee_reference",
    "speaker_reference", "attribute_reference", "collective_reference",
    "structural_reference", "citation_reference", "descriptive_reference", "uncertain",
}
OCCURRENCE_ROLES = {
    "scene_participant", "scene_reference", "annotation_person", "citation_source_person",
    "historical_exemplum", "genealogy_reference", "person_attribute", "collective_reference",
    "speaker_reference", "addressee_reference", "structural", "other",
}
RELATIONS = {
    "same_person", "different_person", "related_person", "kinship_relation", "office_relation",
    "citation_relation", "attribute_of", "other", "uncertain",
}
CONFIDENCES = {"high", "medium", "low"}
REVIEW_DECISIONS = {"confirm", "revise", "abstain"}
ADJUDICATION_DECISIONS = {"select_pass1", "select_pass2", "revise", "abstain"}
PRODUCTION_ID_RE = re.compile(r"(?:^|[^A-Za-z0-9])person-[0-9A-Za-z_-]+(?:$|[^A-Za-z0-9])")
CONCISE_FORM_PATTERN = r"^[^A-Za-z0-9()（）\[\]【】,，.。:：;；/／\\\n\r]*$"


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


def semantic_record_schema() -> dict[str, Any]:
    confidence = {"type": "string", "enum": sorted(CONFIDENCES)}
    relation = _object({
        "target_hint": {"type": "string", "pattern": CONCISE_FORM_PATTERN},
        "relation": {"type": "string", "enum": sorted(RELATIONS)},
        "confidence": confidence,
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
    }, ["target_hint", "relation", "confidence", "evidence_ids"])
    referent = _object({
        "surface_form": {"type": "string", "pattern": CONCISE_FORM_PATTERN},
        "canonical_hint": {"type": "string", "pattern": CONCISE_FORM_PATTERN},
        "confidence": confidence,
    }, ["surface_form", "canonical_hint", "confidence"])
    discourse = _object({
        "speaker_hint": {"type": "string"},
        "addressee_hint": {"type": "string"},
        "antecedent_hint": {"type": "string"},
        "self_reference_hint": {"type": "string"},
    }, ["speaker_hint", "addressee_hint", "antecedent_hint", "self_reference_hint"])
    return _object({
        "mention_id": {"type": "string"},
        "surface": {"type": "string"},
        "semantic_kind": {"type": "string", "enum": sorted(SEMANTIC_KINDS)},
        "reference_type": {"type": "string", "enum": sorted(REFERENCE_TYPES)},
        "referent": referent,
        "occurrence_role": {"type": "string", "enum": sorted(OCCURRENCE_ROLES)},
        "discourse": discourse,
        "relations": {"type": "array", "items": relation},
        "confidence": confidence,
        "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
        "attribute_type": {"type": "string"},
        "attribute_value": {"type": "string", "pattern": CONCISE_FORM_PATTERN},
        "bearer_hint": {"type": "string", "pattern": CONCISE_FORM_PATTERN},
        "abstain": {"type": "boolean"},
        "explanation": {"type": "string"},
    }, [
        "mention_id", "surface", "semantic_kind", "reference_type", "referent",
        "occurrence_role", "discourse", "relations", "confidence",
        "supporting_evidence_ids", "attribute_type", "attribute_value", "bearer_hint",
        "abstain", "explanation",
    ])


def semantic_record_tool() -> dict[str, Any]:
    return _tool(
        "submit_sfh2_a0_primary_semantics_v2",
        "Return one evidence-grounded semantic record for the supplied mention. The historical referent may be absent from the registry; do not emit production IDs.",
        {"record": semantic_record_schema()},
        ["record"],
    )


def critical_review_tool() -> dict[str, Any]:
    return _tool(
        "submit_sfh2_a0_critical_review_v2",
        "Independently review the primary semantic record against the original evidence and return confirm, revise, or abstain. Return the complete revised semantic record.",
        {
            "decision": {"type": "string", "enum": sorted(REVIEW_DECISIONS)},
            "revised_semantic_record": semantic_record_schema(),
            "reason_summary": {"type": "string"},
            "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
        },
        ["decision", "revised_semantic_record", "reason_summary", "supporting_evidence_ids"],
    )


def adjudication_tool() -> dict[str, Any]:
    return _tool(
        "submit_sfh2_a0_adjudication_v2",
        "Adjudicate two semantic records from the original evidence. Select a supported record, revise it, or abstain. Do not emit production IDs.",
        {
            "decision": {"type": "string", "enum": sorted(ADJUDICATION_DECISIONS)},
            "semantic_record": semantic_record_schema(),
            "reason_summary": {"type": "string"},
            "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
        },
        ["decision", "semantic_record", "reason_summary", "supporting_evidence_ids"],
    )


def _ids(value: Any) -> list[str]:
    return sorted({text(item) for item in value or [] if text(item)}) if isinstance(value, list) else []


def _contains_production_id(value: Any) -> bool:
    if isinstance(value, str):
        return bool(PRODUCTION_ID_RE.search(value))
    if isinstance(value, Mapping):
        return any(_contains_production_id(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_production_id(child) for child in value)
    return False


def _concise_form(value: Any) -> bool:
    value = text(value)
    return not value or bool(re.fullmatch(CONCISE_FORM_PATTERN, value))


def _validate_record(raw: Any, packet: Mapping[str, Any], target: Mapping[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    evidence_ids = set(evidence_index(packet))
    if not isinstance(raw, Mapping):
        return ["record_not_object"], {}
    if _contains_production_id(raw):
        errors.append("production_person_id_in_semantic_output")
    referent = raw.get("referent")
    discourse = raw.get("discourse")
    if not isinstance(referent, Mapping):
        errors.append("referent_not_object")
        referent = {}
    if not isinstance(discourse, Mapping):
        errors.append("discourse_not_object")
        discourse = {}
    semantic_kind = text(raw.get("semantic_kind"))
    reference_type = text(raw.get("reference_type"))
    role = text(raw.get("occurrence_role"))
    confidence = text(raw.get("confidence"))
    if semantic_kind not in SEMANTIC_KINDS:
        errors.append("invalid_semantic_kind")
    if reference_type not in REFERENCE_TYPES:
        errors.append("invalid_reference_type")
    if role not in OCCURRENCE_ROLES:
        errors.append("invalid_occurrence_role")
    if confidence not in CONFIDENCES:
        errors.append("invalid_confidence")
    ref_confidence = text(referent.get("confidence"))
    if ref_confidence not in CONFIDENCES:
        errors.append("invalid_referent_confidence")
    for field, value in (
        ("referent.surface_form", referent.get("surface_form")),
        ("referent.canonical_hint", referent.get("canonical_hint")),
        ("attribute_value", raw.get("attribute_value")),
        ("bearer_hint", raw.get("bearer_hint")),
    ):
        if not _concise_form(value):
            errors.append(f"non_concise_{field.replace('.', '_')}")
    support = raw.get("supporting_evidence_ids")
    if not isinstance(support, list) or not all(text(item) in evidence_ids for item in support):
        errors.append("invalid_supporting_evidence_ids")
        support = []
    relation_rows = raw.get("relations")
    if not isinstance(relation_rows, list):
        errors.append("relations_not_array")
        relation_rows = []
    relations: list[dict[str, Any]] = []
    for relation in relation_rows:
        if not isinstance(relation, Mapping):
            errors.append("relation_not_object")
            continue
        relation_name = text(relation.get("relation"))
        relation_confidence = text(relation.get("confidence"))
        relation_evidence = relation.get("evidence_ids")
        if relation_name not in RELATIONS:
            errors.append("invalid_relation")
        if relation_confidence not in CONFIDENCES:
            errors.append("invalid_relation_confidence")
        if not isinstance(relation_evidence, list) or not all(text(item) in evidence_ids for item in relation_evidence):
            errors.append("invalid_relation_evidence_ids")
            relation_evidence = []
        relations.append({
            "target_hint": text(relation.get("target_hint")),
            "relation": relation_name,
            "confidence": relation_confidence,
            "evidence_ids": _ids(relation_evidence),
        })
    abstain = raw.get("abstain")
    if not isinstance(abstain, bool):
        errors.append("invalid_abstain")
        abstain = True
    cleaned = {
        "mention_id": text(raw.get("mention_id")),
        "surface": text(raw.get("surface")),
        "semantic_kind": semantic_kind,
        "reference_type": reference_type,
        "referent": {
            "surface_form": text(referent.get("surface_form")),
            "canonical_hint": text(referent.get("canonical_hint")),
            "confidence": ref_confidence,
        },
        "occurrence_role": role,
        "discourse": {key: text(discourse.get(key)) for key in ("speaker_hint", "addressee_hint", "antecedent_hint", "self_reference_hint")},
        "relations": relations,
        "confidence": confidence,
        "supporting_evidence_ids": _ids(support),
        "attribute_type": text(raw.get("attribute_type")),
        "attribute_value": text(raw.get("attribute_value")),
        "bearer_hint": text(raw.get("bearer_hint")),
        "abstain": abstain,
        "explanation": text(raw.get("explanation")),
    }
    if cleaned["mention_id"] != text(target.get("mention_id")):
        errors.append("mention_id_mismatch")
    if cleaned["surface"] != text(target.get("surface")):
        errors.append("surface_mismatch")
    if cleaned["semantic_kind"] == "historical_person" and not cleaned["abstain"]:
        if not cleaned["referent"]["surface_form"] and not cleaned["referent"]["canonical_hint"]:
            errors.append("historical_person_missing_referent")
        if not cleaned["supporting_evidence_ids"]:
            errors.append("historical_person_missing_evidence")
    if cleaned["semantic_kind"] == "person_attribute" and not cleaned["attribute_value"]:
        errors.append("person_attribute_missing_value")
    return errors, cleaned


def validate_semantic_payload(packet: Mapping[str, Any], target: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = payload.get("record") if isinstance(payload, Mapping) else None
    errors, record = _validate_record(raw, packet, target)
    if errors:
        return {"valid": False, "record": None, "errors": sorted(set(errors))}
    return {"valid": True, "record": record, "errors": []}


def _review_record_payload(payload: Mapping[str, Any] | None, key: str) -> tuple[list[str], dict[str, Any]]:
    if not isinstance(payload, Mapping):
        return ["provider_or_schema_failure"], {}
    decision = text(payload.get("decision"))
    if decision not in REVIEW_DECISIONS and key == "review":
        return ["invalid_review_decision"], {}
    if decision not in ADJUDICATION_DECISIONS and key == "adjudication":
        return ["invalid_adjudication_decision"], {}
    record_key = "revised_semantic_record" if key == "review" else "semantic_record"
    if not isinstance(payload.get(record_key), Mapping):
        return ["review_record_missing"], {}
    supporting = payload.get("supporting_evidence_ids")
    if not isinstance(supporting, list):
        return ["review_supporting_evidence_ids_not_array"], {}
    return [], {
        "decision": decision,
        record_key: dict(payload[record_key]),
        "reason_summary": text(payload.get("reason_summary")),
        "supporting_evidence_ids": _ids(supporting),
    }


def validate_critical_review_payload(packet: Mapping[str, Any], target: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    errors, cleaned = _review_record_payload(payload, "review")
    if errors:
        return {"valid": False, "review": None, "errors": sorted(set(errors))}
    record_result = validate_semantic_payload(packet, target, {"record": cleaned["revised_semantic_record"]})
    if not record_result["valid"]:
        return {"valid": False, "review": None, "errors": [f"revised_record:{error}" for error in record_result["errors"]]}
    cleaned["revised_semantic_record"] = record_result["record"]
    evidence_ids = set(evidence_index(packet))
    if not all(value in evidence_ids for value in cleaned["supporting_evidence_ids"]):
        return {"valid": False, "review": None, "errors": ["invalid_review_supporting_evidence_ids"]}
    return {"valid": True, "review": cleaned, "errors": []}


def validate_adjudication_payload(packet: Mapping[str, Any], target: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    errors, cleaned = _review_record_payload(payload, "adjudication")
    if errors:
        return {"valid": False, "adjudication": None, "errors": sorted(set(errors))}
    record_result = validate_semantic_payload(packet, target, {"record": cleaned["semantic_record"]})
    if not record_result["valid"]:
        return {"valid": False, "adjudication": None, "errors": [f"semantic_record:{error}" for error in record_result["errors"]]}
    cleaned["semantic_record"] = record_result["record"]
    evidence_ids = set(evidence_index(packet))
    if not all(value in evidence_ids for value in cleaned["supporting_evidence_ids"]):
        return {"valid": False, "adjudication": None, "errors": ["invalid_adjudication_supporting_evidence_ids"]}
    return {"valid": True, "adjudication": cleaned, "errors": []}
