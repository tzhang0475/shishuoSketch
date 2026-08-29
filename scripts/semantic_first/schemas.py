"""Strict function schemas and semantic enums for SFH1 model stages."""

from __future__ import annotations

from typing import Any

ENTITY_KINDS = {"person", "collective_person_reference", "non_person"}
REFERENCE_FORMS = {
    "full_name", "personal_name", "courtesy_name", "style_name", "nickname",
    "surname_reference", "abbreviated_reference", "office_title", "honorific",
    "ruler_title", "kinship_reference", "pronoun_reference",
    "descriptive_person_reference", "uncertain",
}
CONFIDENCES = {"high", "medium", "low"}
SEMANTIC_TYPES = {
    "direct_person_form", "office_holder_reference", "ruler_reference",
    "local_anaphoric_reference", "abbreviated_person_reference",
    "compositional_kinship", "honorific_reference", "patron_plus_office",
    "descriptive_person_reference", "uncertain",
}
RELATION_TYPES = {"comparison", "kinship", "marriage", "office", "social", "speech", "co_presence", "other"}
ASSESSMENT_VERDICTS = {"support", "contradict", "plausible", "insufficient"}
RESOLUTIONS = {"candidate_supported", "candidate_ambiguous", "candidate_missing", "insufficient_evidence", "reference_not_person"}
REVIEW_VERDICTS = {"accept", "reject", "review_required"}
FINAL_STATES = {
    "stable_entity_resolved", "local_candidate_resolved", "review_required",
    "genuinely_unresolved", "structural_reference", "non_person",
}
FAILURE_STAGES = {
    "mention_missing", "mention_boundary_error", "entity_type_uncertain",
    "reference_semantics_uncertain", "candidate_recall_failure",
    "identity_evidence_insufficient", "hard_constraint_veto", "PSL ambiguity",
    "reviewer_rejection", "provider_failure",
}


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "strict": True,
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": properties,
                "required": required,
            },
        },
    }


def mention_tool() -> dict[str, Any]:
    item = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "mention_id_local": {"type": "string"},
            "surface": {"type": "string"},
            "source_evidence_id": {"type": "string"},
            "source_start": {"type": ["integer", "null"]},
            "source_end": {"type": ["integer", "null"]},
            "entity_kind": {"type": "string", "enum": sorted(ENTITY_KINDS)},
            "reference_form": {"type": "string", "enum": sorted(REFERENCE_FORMS)},
            "confidence": {"type": "string", "enum": sorted(CONFIDENCES)},
            "local_explanation": {"type": "string"},
        },
        "required": ["mention_id_local", "surface", "source_evidence_id", "source_start", "source_end", "entity_kind", "reference_form", "confidence", "local_explanation"],
    }
    return _tool("submit_sfh1_mentions", "Return all person-related and explicitly evaluated non-person mentions.", {"mentions": {"type": "array", "maxItems": 50, "items": item}}, ["mentions"])


def reference_tool() -> dict[str, Any]:
    relation = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "type": {"type": "string", "enum": sorted(RELATION_TYPES)},
            "subject_mention_id": {"type": "string"},
            "object_mention_id": {"type": "string"},
            "predicate_surface": {"type": "string"},
            "evidence_id": {"type": "string"},
        },
        "required": ["type", "subject_mention_id", "object_mention_id", "predicate_surface", "evidence_id"],
    }
    item = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "mention_id": {"type": "string"},
            "semantic_type": {"type": "string", "enum": sorted(SEMANTIC_TYPES)},
            "referent_role": {"type": "string"},
            "anchor_mentions": {"type": "array", "items": {"type": "string"}},
            "holder_mentions": {"type": "array", "items": {"type": "string"}},
            "patron_or_possessor_mentions": {"type": "array", "items": {"type": "string"}},
            "coreference_with": {"type": "array", "items": {"type": "string"}},
            "distinct_from": {"type": "array", "items": {"type": "string"}},
            "semantic_relations": {"type": "array", "items": relation},
            "confidence": {"type": "string", "enum": sorted(CONFIDENCES)},
            "explanation": {"type": "string"},
        },
        "required": ["mention_id", "semantic_type", "referent_role", "anchor_mentions", "holder_mentions", "patron_or_possessor_mentions", "coreference_with", "distinct_from", "semantic_relations", "confidence", "explanation"],
    }
    return _tool("submit_sfh1_reference_semantics", "Interpret reference structure and source-grounded relations for supplied mentions.", {"records": {"type": "array", "items": item}}, ["records"])


def identity_tool() -> dict[str, Any]:
    assessment = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "candidate_key": {"type": "string"},
            "verdict": {"type": "string", "enum": sorted(ASSESSMENT_VERDICTS)},
            "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
            "contradicting_evidence_ids": {"type": "array", "items": {"type": "string"}},
            "reason_types": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["candidate_key", "verdict", "supporting_evidence_ids", "contradicting_evidence_ids", "reason_types"],
    }
    item = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "mention_id": {"type": "string"},
            "candidate_assessments": {"type": "array", "items": assessment},
            "preferred_candidate_key": {"type": ["string", "null"]},
            "resolution": {"type": "string", "enum": sorted(RESOLUTIONS)},
            "alternative_search_surfaces": {"type": "array", "items": {"type": "string"}},
            "explanation": {"type": "string"},
        },
        "required": ["mention_id", "candidate_assessments", "preferred_candidate_key", "resolution", "alternative_search_surfaces", "explanation"],
    }
    return _tool("submit_sfh1_identity_judgments", "Assess only Python-supplied candidate keys against supplied evidence.", {"judgments": {"type": "array", "items": item}}, ["judgments"])


def review_tool() -> dict[str, Any]:
    item = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "mention_id": {"type": "string"},
            "candidate_key": {"type": "string"},
            "verdict": {"type": "string", "enum": sorted(REVIEW_VERDICTS)},
            "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
            "contradicting_evidence_ids": {"type": "array", "items": {"type": "string"}},
            "reason_types": {"type": "array", "items": {"type": "string"}},
            "explanation": {"type": "string"},
        },
        "required": ["mention_id", "candidate_key", "verdict", "supporting_evidence_ids", "contradicting_evidence_ids", "reason_types", "explanation"],
    }
    return _tool("submit_sfh1_adversarial_reviews", "Try to falsify risky proposed identity resolutions.", {"reviews": {"type": "array", "items": item}}, ["reviews"])


def temporal_tool() -> dict[str, Any]:
    item = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "temporal_id_local": {"type": "string"},
            "surface": {"type": "string"},
            "evidence_id": {"type": "string"},
            "exact_span": {"type": "string"},
            "semantic_role": {"type": "string", "enum": ["scene_time", "background_context", "later_outcome", "quoted_precedent", "relative_person_time", "office_context", "uncertain"]},
            "interpretation": {"type": "string"},
            "confidence": {"type": "string", "enum": sorted(CONFIDENCES)},
        },
        "required": ["temporal_id_local", "surface", "evidence_id", "exact_span", "semantic_role", "interpretation", "confidence"],
    }
    return _tool("submit_sfh1_temporal_semantics", "Return source-grounded semantic temporal assertions without assigning canonical dates.", {"assertions": {"type": "array", "maxItems": 20, "items": item}}, ["assertions"])
