"""Strict pilot schemas and fail-closed validators."""

from __future__ import annotations

from typing import Any, Mapping

from .common import evidence_index, text

SEMANTIC_TYPES = {
    "direct_person_form", "office_holder_reference", "ruler_reference",
    "local_anaphoric_reference", "abbreviated_person_reference",
    "compositional_kinship", "honorific_reference", "patron_plus_office",
    "descriptive_person_reference", "uncertain",
}
NETWORK_ROLES = {
    "narrative_participant", "narrative_reference", "annotation_biographical_person",
    "citation_author", "historical_exemplum", "genealogy_ancestor", "anonymous_person",
    "person_attribute", "structural_reference", "collective_reference", "uncertain",
}
CONFIDENCES = {"high", "medium", "low"}
ASSESSMENTS = {"support", "contradict", "plausible", "insufficient"}
RESOLUTIONS = {"candidate_supported", "candidate_ambiguous", "candidate_missing", "insufficient_evidence", "reference_not_person"}


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
def reference_semantics_tool() -> dict[str, Any]:
    record = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "mention_id": {"type": "string"},
            "semantic_type": {"type": "string", "enum": sorted(SEMANTIC_TYPES)},
            "referent_role": {"type": "string"},
            "referent_hint": {"type": "string"},
            "network_role": {"type": "string", "enum": sorted(NETWORK_ROLES)},
            "anchor_mentions": {"type": "array", "items": {"type": "string"}},
            "holder_mentions": {"type": "array", "items": {"type": "string"}},
            "patron_or_possessor_mentions": {"type": "array", "items": {"type": "string"}},
            "coreference_with": {"type": "array", "items": {"type": "string"}},
            "distinct_from": {"type": "array", "items": {"type": "string"}},
            "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "string", "enum": sorted(CONFIDENCES)},
            "explanation": {"type": "string"},
        },
        "required": [
            "mention_id", "semantic_type", "referent_role", "referent_hint", "network_role",
            "anchor_mentions", "holder_mentions", "patron_or_possessor_mentions",
            "coreference_with", "distinct_from", "supporting_evidence_ids", "confidence", "explanation",
        ],
    }
    return _tool("submit_sfh2_2p_reference_semantics", "Interpret supplied historical reference semantics without assigning canonical IDs.", {"records": {"type": "array", "items": record}}, ["records"])


def identity_judgment_tool() -> dict[str, Any]:
    assessment = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "candidate_key": {"type": "string"},
            "verdict": {"type": "string", "enum": sorted(ASSESSMENTS)},
            "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
            "contradicting_evidence_ids": {"type": "array", "items": {"type": "string"}},
            "reason_types": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["candidate_key", "verdict", "supporting_evidence_ids", "contradicting_evidence_ids", "reason_types"],
    }
    item = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "unit_id": {"type": "string"},
            "candidate_assessments": {"type": "array", "items": assessment},
            "preferred_candidate_key": {"type": ["string", "null"]},
            "resolution": {"type": "string", "enum": sorted(RESOLUTIONS)},
            "explanation": {"type": "string"},
        },
        "required": ["unit_id", "candidate_assessments", "preferred_candidate_key", "resolution", "explanation"],
    }
    return _tool("submit_sfh2_2p_identity_judgments", "Judge only Python-supplied candidate keys using supplied evidence.", {"judgments": {"type": "array", "items": item}}, ["judgments"])


def _ids(value: Any) -> list[str]:
    return sorted({text(item) for item in value or [] if text(item)}) if isinstance(value, list) else []


def validate_reference_payload(packet: Mapping[str, Any], target_ids: set[str], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    source_ids = set(evidence_index(packet))
    rows = payload.get("records") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        return {"records": [], "rejected": [{"reason": "provider_or_schema_failure"}], "provider_failure": True, "invalid_payloads": 1}
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(rows):
        errors: list[str] = []
        if not isinstance(raw, Mapping):
            rejected.append({"index": index, "errors": ["record_not_object"]})
            continue
        mention_id = text(raw.get("mention_id"))
        if mention_id not in target_ids or mention_id in seen:
            errors.append("unknown_or_duplicate_target")
        semantic_type = text(raw.get("semantic_type"))
        network_role = text(raw.get("network_role"))
        confidence = text(raw.get("confidence"))
        if semantic_type not in SEMANTIC_TYPES:
            errors.append("invalid_semantic_type")
        if network_role not in NETWORK_ROLES:
            errors.append("invalid_network_role")
        if confidence not in CONFIDENCES:
            errors.append("invalid_confidence")
        local_ids: dict[str, list[str]] = {}
        for field in ("anchor_mentions", "holder_mentions", "patron_or_possessor_mentions", "coreference_with", "distinct_from"):
            value = raw.get(field)
            if not isinstance(value, list):
                errors.append(f"{field}_not_array")
                value = []
            local_ids[field] = _ids(value)
            if mention_id in local_ids[field]:
                errors.append(f"{field}_self_link")
        evidence = raw.get("supporting_evidence_ids")
        if not isinstance(evidence, list) or not all(text(value) in source_ids for value in evidence):
            errors.append("invalid_supporting_evidence")
            evidence = []
        if errors:
            rejected.append({"index": index, "mention_id": mention_id, "errors": sorted(set(errors))})
            continue
        seen.add(mention_id)
        accepted.append({
            "mention_id": mention_id,
            "semantic_type": semantic_type,
            "referent_role": text(raw.get("referent_role")),
            "referent_hint": text(raw.get("referent_hint")),
            "network_role": network_role,
            **local_ids,
            "supporting_evidence_ids": sorted(set(text(value) for value in evidence)),
            "confidence": confidence,
            "explanation": text(raw.get("explanation")),
            "candidate_only": True, "canonical_write_back": False,
        })
    missing = sorted(target_ids - seen)
    return {
        "records": sorted(accepted, key=lambda row: row["mention_id"]),
        "rejected": rejected,
        "missing_target_ids": missing,
        "provider_failure": bool(missing),
        "invalid_payloads": len(rejected),
    }


def candidate_evidence_ids(candidate: Mapping[str, Any]) -> set[str]:
    result: set[str] = set()
    for item in candidate.get("evidence", []) or []:
        if isinstance(item, Mapping) and text(item.get("evidence_id")):
            result.add(text(item.get("evidence_id")))
    return result


def validate_identity_payload(candidate_sets: Mapping[str, Any], packet: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    records = {text(row.get("unit_id")): dict(row) for row in candidate_sets.get("records", []) or [] if text(row.get("unit_id"))}
    source_ids = set(evidence_index(packet))
    rows = payload.get("judgments") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        return {"judgments": [], "rejected": [{"reason": "provider_or_schema_failure"}], "provider_failure": True, "invalid_payloads": 1}
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(rows):
        errors: list[str] = []
        if not isinstance(raw, Mapping):
            rejected.append({"index": index, "errors": ["judgment_not_object"]})
            continue
        unit_id = text(raw.get("unit_id"))
        record = records.get(unit_id)
        if not record or unit_id in seen:
            errors.append("unknown_or_duplicate_unit")
            record = {"candidates": []}
        candidates = record.get("candidates", []) or []
        keys = {text(row.get("candidate_key")) for row in candidates if isinstance(row, Mapping)}
        allowed_evidence = source_ids | {item for candidate in candidates if isinstance(candidate, Mapping) for item in candidate_evidence_ids(candidate)}
        assessments = raw.get("candidate_assessments")
        if not isinstance(assessments, list):
            errors.append("candidate_assessments_not_array")
            assessments = []
        cleaned: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        for assessment in assessments:
            if not isinstance(assessment, Mapping):
                errors.append("assessment_not_object")
                continue
            key = text(assessment.get("candidate_key"))
            verdict = text(assessment.get("verdict"))
            support = assessment.get("supporting_evidence_ids")
            contradict = assessment.get("contradicting_evidence_ids")
            if key not in keys or key in seen_keys:
                errors.append("invalid_or_duplicate_candidate_key")
            if verdict not in ASSESSMENTS:
                errors.append("invalid_assessment_verdict")
            if not isinstance(support, list) or not all(text(item) in allowed_evidence for item in support):
                errors.append("invalid_supporting_evidence")
                support = []
            if not isinstance(contradict, list) or not all(text(item) in allowed_evidence for item in contradict):
                errors.append("invalid_contradicting_evidence")
                contradict = []
            seen_keys.add(key)
            cleaned.append({
                "candidate_key": key, "verdict": verdict,
                "supporting_evidence_ids": sorted(set(text(item) for item in support)),
                "contradicting_evidence_ids": sorted(set(text(item) for item in contradict)),
                "reason_types": sorted({text(item) for item in assessment.get("reason_types", []) or [] if text(item)}),
            })
        preferred = raw.get("preferred_candidate_key")
        if preferred == "null":
            errors.append("literal_null_candidate_key")
        if preferred is not None and text(preferred) not in keys:
            errors.append("invalid_preferred_candidate_key")
        resolution = text(raw.get("resolution"))
        if resolution not in RESOLUTIONS:
            errors.append("invalid_resolution")
        if resolution == "candidate_supported" and not any(
            row["candidate_key"] == preferred and row["verdict"] == "support" and row["supporting_evidence_ids"]
            for row in cleaned
        ):
            errors.append("supported_resolution_requires_grounded_support")
        if errors:
            rejected.append({"index": index, "unit_id": unit_id, "errors": sorted(set(errors))})
            continue
        seen.add(unit_id)
        accepted.append({
            "unit_id": unit_id,
            "candidate_assessments": cleaned,
            "preferred_candidate_key": preferred,
            "resolution": resolution,
            "explanation": text(raw.get("explanation")),
            "candidate_only": True, "canonical_write_back": False,
        })
    return {
        "judgments": sorted(accepted, key=lambda row: row["unit_id"]),
        "rejected": rejected,
        "missing_unit_ids": sorted(set(records) - seen),
        "provider_failure": bool(set(records) - seen),
        "invalid_payloads": len(rejected),
    }
