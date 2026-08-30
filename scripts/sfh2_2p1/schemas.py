"""Strict proposal-first schemas and fail-closed validators."""

from __future__ import annotations

from typing import Any, Mapping

from .common import evidence_index, text

PROPOSAL_KINDS = {
    "historical_person", "person_attribute", "collective_reference",
    "non_person", "structural_reference", "uncertain",
}
ENTITY_KINDS = {"person", "person_attribute", "collective", "non_person", "structural", "uncertain"}
REFERENCE_TYPES = {
    "full_name", "personal_name", "courtesy_name", "style_name", "nickname",
    "surname_reference", "abbreviated_reference", "office_title", "honorific",
    "ruler_title", "kinship_reference", "pronoun_reference",
    "descriptive_person_reference", "person_attribute", "collective_reference", "uncertain",
}
NETWORK_ROLES = {
    "narrative_participant", "narrative_reference", "annotation_biographical_person",
    "citation_author", "historical_exemplum", "genealogy_ancestor", "anonymous_person",
    "person_attribute", "structural_reference", "collective_reference", "uncertain",
}
CONFIDENCES = {"high", "medium", "low"}
EQUIVALENCE_RELATIONS = {
    "same_person", "different_person", "related_person", "office_relation",
    "kinship_relation", "citation_relation", "attribute_of", "insufficient",
}


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "strict": True,
            "parameters": {
                "type": "object", "additionalProperties": False,
                "properties": properties, "required": required,
            },
        },
    }


def entity_proposal_tool() -> dict[str, Any]:
    alternative = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "surface": {"type": "string"},
            "reason": {"type": "string"},
            "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["surface", "reason", "supporting_evidence_ids"],
    }
    interpretation = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "entity_kind": {"type": "string", "enum": sorted(ENTITY_KINDS)},
            "reference_type": {"type": "string", "enum": sorted(REFERENCE_TYPES)},
            "network_role": {"type": "string", "enum": sorted(NETWORK_ROLES)},
        },
        "required": ["entity_kind", "reference_type", "network_role"],
    }
    proposal = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "proposal_kind": {"type": "string", "enum": sorted(PROPOSAL_KINDS)},
            "display_name": {"type": "string"},
            "confidence": {"type": "string", "enum": sorted(CONFIDENCES)},
            "attribute_type": {"type": "string"},
            "attribute_value": {"type": "string"},
            "bearer_canonical_hint": {"type": "string"},
            "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "proposal_kind", "display_name", "confidence", "attribute_type",
            "attribute_value", "bearer_canonical_hint", "supporting_evidence_ids",
        ],
    }
    item = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "mention_id": {"type": "string"},
            "surface": {"type": "string"},
            "entity_interpretation": interpretation,
            "referent_surface": {"type": "string"},
            "referent_canonical_hint": {"type": "string"},
            "candidate_proposal": proposal,
            "alternatives": {"type": "array", "items": alternative},
            "abstain": {"type": "boolean"},
            "explanation": {"type": "string"},
        },
        "required": [
            "mention_id", "surface", "entity_interpretation", "referent_surface",
            "referent_canonical_hint", "candidate_proposal", "alternatives", "abstain", "explanation",
        ],
    }
    return _tool(
        "submit_sfh2_2p1_entity_proposals",
        "Interpret the supplied source and propose a historical entity or a non-person/attribute structure. A proposed entity may be absent from the registry. Never emit a production Person ID.",
        {"proposals": {"type": "array", "items": item}},
        ["proposals"],
    )


def identity_equivalence_tool() -> dict[str, Any]:
    assessment = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "candidate_key": {"type": "string"},
            "relation_to_target": {"type": "string", "enum": sorted(EQUIVALENCE_RELATIONS)},
            "confidence": {"type": "string", "enum": sorted(CONFIDENCES)},
            "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
            "contradicting_evidence_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "candidate_key", "relation_to_target", "confidence",
            "supporting_evidence_ids", "contradicting_evidence_ids",
        ],
    }
    item = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "mention_id": {"type": "string"},
            "target_proposal": {"type": "string"},
            "candidate_assessments": {"type": "array", "items": assessment},
            "same_person_candidate_key": {"type": ["string", "null"]},
            "abstain": {"type": "boolean"},
            "explanation": {"type": "string"},
        },
        "required": [
            "mention_id", "target_proposal", "candidate_assessments",
            "same_person_candidate_key", "abstain", "explanation",
        ],
    }
    return _tool(
        "submit_sfh2_2p1_identity_equivalence",
        "Assess the relation of each supplied candidate to the proposed target. Only same_person is identity; related, office, kinship, citation, and attribute relations are not identity.",
        {"reviews": {"type": "array", "items": item}},
        ["reviews"],
    )


def _ids(value: Any) -> list[str]:
    return sorted({text(item) for item in value or [] if text(item)}) if isinstance(value, list) else []


def _type_errors(raw: Mapping[str, Any], evidence_ids: set[str]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    interpretation = raw.get("entity_interpretation")
    proposal = raw.get("candidate_proposal")
    if not isinstance(interpretation, Mapping):
        errors.append("entity_interpretation_not_object")
        interpretation = {}
    if not isinstance(proposal, Mapping):
        errors.append("candidate_proposal_not_object")
        proposal = {}
    entity_kind = text(interpretation.get("entity_kind"))
    reference_type = text(interpretation.get("reference_type"))
    network_role = text(interpretation.get("network_role"))
    proposal_kind = text(proposal.get("proposal_kind"))
    confidence = text(proposal.get("confidence"))
    if entity_kind not in ENTITY_KINDS:
        errors.append("invalid_entity_kind")
    if reference_type not in REFERENCE_TYPES:
        errors.append("invalid_reference_type")
    if network_role not in NETWORK_ROLES:
        errors.append("invalid_network_role")
    if proposal_kind not in PROPOSAL_KINDS:
        errors.append("invalid_proposal_kind")
    if confidence not in CONFIDENCES:
        errors.append("invalid_proposal_confidence")
    for field in ("supporting_evidence_ids",):
        value = proposal.get(field)
        if not isinstance(value, list) or not all(text(item) in evidence_ids for item in value):
            errors.append(f"invalid_proposal_{field}")
    referent_hint = text(raw.get("referent_canonical_hint"))
    bearer_hint = text(proposal.get("bearer_canonical_hint"))
    if referent_hint.startswith("person-") or bearer_hint.startswith("person-"):
        errors.append("production_person_id_in_semantic_output")
    cleaned = {
        "mention_id": text(raw.get("mention_id")),
        "surface": text(raw.get("surface")),
        "entity_interpretation": {
            "entity_kind": entity_kind, "reference_type": reference_type, "network_role": network_role,
        },
        "referent_surface": text(raw.get("referent_surface")),
        "referent_canonical_hint": referent_hint,
        "candidate_proposal": {
            "proposal_kind": proposal_kind,
            "display_name": text(proposal.get("display_name")),
            "confidence": confidence,
            "attribute_type": text(proposal.get("attribute_type")),
            "attribute_value": text(proposal.get("attribute_value")),
            "bearer_canonical_hint": bearer_hint,
            "supporting_evidence_ids": _ids(proposal.get("supporting_evidence_ids")),
        },
        "alternatives": [],
        "abstain": raw.get("abstain") if isinstance(raw.get("abstain"), bool) else None,
        "explanation": text(raw.get("explanation")),
    }
    if not isinstance(cleaned["abstain"], bool):
        errors.append("invalid_abstain")
        cleaned["abstain"] = True
    alternatives = raw.get("alternatives")
    if not isinstance(alternatives, list):
        errors.append("alternatives_not_array")
        alternatives = []
    for alternative in alternatives:
        if not isinstance(alternative, Mapping):
            errors.append("alternative_not_object")
            continue
        ids = alternative.get("supporting_evidence_ids")
        if not isinstance(ids, list) or not all(text(item) in evidence_ids for item in ids):
            errors.append("invalid_alternative_evidence")
            ids = []
        cleaned["alternatives"].append({
            "surface": text(alternative.get("surface")),
            "reason": text(alternative.get("reason")),
            "supporting_evidence_ids": _ids(ids),
        })
    if proposal_kind == "historical_person" and not text(proposal.get("display_name")):
        errors.append("historical_person_requires_display_name")
    if proposal_kind == "historical_person" and not cleaned["candidate_proposal"]["supporting_evidence_ids"] and not cleaned["abstain"]:
        errors.append("historical_person_requires_grounded_support")
    return errors, cleaned


def validate_entity_proposal_payload(packet: Mapping[str, Any], target: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    evidence_ids = set(evidence_index(packet))
    rows = payload.get("proposals") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        return {"proposals": [], "rejected": [{"reason": "provider_or_schema_failure"}], "provider_failure": True, "invalid_payloads": 1}
    target_id, target_surface = text(target.get("mention_id")), text(target.get("surface"))
    accepted, rejected = [], []
    seen = set()
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            rejected.append({"index": index, "errors": ["proposal_not_object"]})
            continue
        errors, cleaned = _type_errors(raw, evidence_ids)
        if cleaned["mention_id"] != target_id or cleaned["mention_id"] in seen:
            errors.append("unknown_or_duplicate_target")
        if cleaned["surface"] != target_surface:
            errors.append("surface_does_not_match_validated_mention")
        if errors:
            rejected.append({"index": index, "mention_id": cleaned["mention_id"], "errors": sorted(set(errors))})
            continue
        seen.add(cleaned["mention_id"])
        accepted.append(cleaned)
    missing = sorted({target_id} - seen)
    return {
        "proposals": accepted,
        "rejected": rejected,
        "missing_target_ids": missing,
        "provider_failure": bool(missing),
        "invalid_payloads": len(rejected),
    }

def candidate_evidence_ids(candidate: Mapping[str, Any]) -> set[str]:
    return {text(item.get("evidence_id")) for item in candidate.get("evidence", []) or [] if isinstance(item, Mapping) and text(item.get("evidence_id"))}


def validate_equivalence_payload(candidate_set: Mapping[str, Any], packet: Mapping[str, Any], target: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    rows = payload.get("reviews") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        return {"reviews": [], "rejected": [{"reason": "provider_or_schema_failure"}], "provider_failure": True, "invalid_payloads": 1}
    candidates = [row for row in candidate_set.get("candidates", []) or [] if isinstance(row, Mapping)]
    keys = {text(row.get("candidate_key")) for row in candidates}
    source_ids = set(evidence_index(packet)) | {value for row in candidates for value in candidate_evidence_ids(row)}
    target_id = text(target.get("mention_id"))
    accepted, rejected, seen = [], [], set()
    for index, raw in enumerate(rows):
        errors: list[str] = []
        if not isinstance(raw, Mapping):
            rejected.append({"index": index, "errors": ["review_not_object"]})
            continue
        mention_id = text(raw.get("mention_id"))
        if mention_id != target_id or mention_id in seen:
            errors.append("unknown_or_duplicate_target")
        assessments = raw.get("candidate_assessments")
        if not isinstance(assessments, list):
            errors.append("candidate_assessments_not_array")
            assessments = []
        cleaned_assessments, seen_keys = [], set()
        for assessment in assessments:
            if not isinstance(assessment, Mapping):
                errors.append("assessment_not_object")
                continue
            key = text(assessment.get("candidate_key"))
            relation = text(assessment.get("relation_to_target"))
            confidence = text(assessment.get("confidence"))
            support = assessment.get("supporting_evidence_ids")
            contradict = assessment.get("contradicting_evidence_ids")
            if key not in keys or key in seen_keys:
                errors.append("invalid_or_duplicate_candidate_key")
            if relation not in EQUIVALENCE_RELATIONS:
                errors.append("invalid_equivalence_relation")
            if confidence not in CONFIDENCES:
                errors.append("invalid_equivalence_confidence")
            if not isinstance(support, list) or not all(text(item) in source_ids for item in support):
                errors.append("invalid_supporting_evidence")
                support = []
            if not isinstance(contradict, list) or not all(text(item) in source_ids for item in contradict):
                errors.append("invalid_contradicting_evidence")
                contradict = []
            seen_keys.add(key)
            cleaned_assessments.append({
                "candidate_key": key,
                "relation_to_target": relation,
                "confidence": confidence,
                "supporting_evidence_ids": _ids(support),
                "contradicting_evidence_ids": _ids(contradict),
            })
        if seen_keys != keys:
            errors.append("candidate_assessment_coverage_incomplete")
        same_key = raw.get("same_person_candidate_key")
        if same_key == "null":
            errors.append("literal_null_candidate_key")
        if same_key is not None and text(same_key) not in keys:
            errors.append("invalid_same_person_candidate_key")
        same_rows = [row for row in cleaned_assessments if row["candidate_key"] == same_key and row["relation_to_target"] == "same_person"]
        abstain = raw.get("abstain")
        if not isinstance(abstain, bool):
            errors.append("invalid_abstain")
            abstain = True
        if same_key is not None and (not same_rows or abstain):
            errors.append("same_person_requires_non_abstaining_grounded_assessment")
        if same_rows and not same_rows[0]["supporting_evidence_ids"]:
            errors.append("same_person_requires_grounded_support")
        if errors:
            rejected.append({"index": index, "mention_id": mention_id, "errors": sorted(set(errors))})
            continue
        seen.add(mention_id)
        accepted.append({
            "mention_id": mention_id,
            "target_proposal": text(raw.get("target_proposal")),
            "candidate_assessments": sorted(cleaned_assessments, key=lambda row: row["candidate_key"]),
            "same_person_candidate_key": same_key,
            "abstain": abstain,
            "explanation": text(raw.get("explanation")),
            "candidate_only": True, "canonical_write_back": False,
        })
    missing = sorted({target_id} - seen)
    return {
        "reviews": accepted,
        "rejected": rejected,
        "missing_target_ids": missing,
        "provider_failure": bool(missing),
        "invalid_payloads": len(rejected),
    }
