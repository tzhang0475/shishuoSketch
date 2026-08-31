"""Formal consistency checks for SFH2.2-A0.

This module intentionally contains no Chinese lexical rules and no historical
identity mapping.  It reports contradictions in structured fields supplied by
the semantic passes; it never supplies a replacement answer.
"""

from __future__ import annotations

from typing import Any, Mapping

from .common import normalize, text

CONSISTENCY_CONTRACT = "formal_fields_and_graph_only_v1"
EXCLUDED_CORE_ROLES = {
    "citation_source_person", "historical_exemplum", "person_attribute",
    "annotation_person", "collective_reference", "structural", "genealogy_reference",
}
IDENTITY_RELATIONS = {"same_person", "different_person"}


def _flag(flag_type: str, involved: list[Any], evidence_ids: list[str], reason: str, severity: str = "review") -> dict[str, Any]:
    return {
        "flag_type": flag_type,
        "involved": involved,
        "evidence_ids": sorted({text(value) for value in evidence_ids if text(value)}),
        "formal_reason": reason,
        "severity": severity,
    }


def _record_evidence(record: Mapping[str, Any]) -> list[str]:
    values = [text(value) for value in record.get("supporting_evidence_ids", []) or [] if text(value)]
    for relation in record.get("relations", []) or []:
        if isinstance(relation, Mapping):
            values.extend(text(value) for value in relation.get("evidence_ids", []) or [] if text(value))
    return sorted(set(values))


def _identity_relation_conflicts(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, set[str]] = {}
    evidence: dict[str, list[str]] = {}
    for relation in record.get("relations", []) or []:
        if not isinstance(relation, Mapping):
            continue
        target = normalize(relation.get("target_hint"))
        relation_name = text(relation.get("relation"))
        if not target or relation_name not in IDENTITY_RELATIONS:
            continue
        grouped.setdefault(target, set()).add(relation_name)
        evidence.setdefault(target, []).extend(text(value) for value in relation.get("evidence_ids", []) or [])
    return [
        _flag(
            "identity_distinctness_conflict",
            [target, sorted(relations)],
            evidence.get(target, []),
            "the same structured target has both same_person and different_person relations",
            "hard",
        )
        for target, relations in sorted(grouped.items())
        if IDENTITY_RELATIONS.issubset(relations)
    ]


def check_record(record: Mapping[str, Any] | None, *, evidence_ids: set[str] | None = None, realization: Mapping[str, Any] | None = None, graph_facts: list[Mapping[str, Any]] | None = None, stage: str = "pass1") -> dict[str, Any]:
    """Return formal flags and a review-routing score for one semantic record."""

    flags: list[dict[str, Any]] = []
    if not isinstance(record, Mapping):
        flags.append(_flag("evidence_grounding_failure", [], [], "semantic record is not an object", "hard"))
        return {"stage": stage, "flags": flags, "review_trigger_score": 100, "candidate_only": True, "canonical_write_back": False}
    supplied = set(evidence_ids or set())
    support = _record_evidence(record)
    if supplied and any(value not in supplied for value in support):
        flags.append(_flag("evidence_grounding_failure", ["supporting_evidence_ids"], [value for value in support if value not in supplied], "a semantic record cites an evidence ID outside the source packet", "hard"))
    if not bool(record.get("abstain")) and not support:
        flags.append(_flag("evidence_grounding_failure", ["supporting_evidence_ids"], [], "a non-abstaining semantic record has no supporting evidence", "hard"))

    confidence = text(record.get("confidence"))
    referent = record.get("referent") if isinstance(record.get("referent"), Mapping) else {}
    if confidence == "low" or text(referent.get("confidence")) == "low":
        flags.append(_flag("low_confidence", ["confidence", "referent.confidence"], support, "a semantic pass marked the interpretation low confidence", "review"))

    semantic_kind = text(record.get("semantic_kind"))
    role = text(record.get("occurrence_role"))
    identity_realization = bool((realization or {}).get("identity_created"))
    if bool(record.get("abstain")) and identity_realization:
        flags.append(_flag("entity_storage_type_conflict", ["abstain", "identity_created"], support, "an abstaining semantic record cannot have an identity realization", "hard"))
    if semantic_kind != "historical_person" and identity_realization:
        flags.append(_flag("entity_storage_type_conflict", [semantic_kind, "identity_created"], support, "only a historical_person semantic kind may create an identity realization", "hard"))
    if role in EXCLUDED_CORE_ROLES and bool((realization or {}).get("core_graph_eligible")):
        flags.append(_flag("source_role_projection_conflict", [role, "core_graph_eligible"], support, "an explicitly source/structural role was marked core-graph eligible", "hard"))

    reference_type = text(record.get("reference_type"))
    discourse = record.get("discourse") if isinstance(record.get("discourse"), Mapping) else {}
    canonical_hint = normalize(referent.get("canonical_hint"))
    if reference_type == "addressee_reference" and canonical_hint and normalize(discourse.get("addressee_hint")) and canonical_hint != normalize(discourse.get("addressee_hint")):
        flags.append(_flag("internal_field_conflict", ["referent.canonical_hint", "discourse.addressee_hint"], support, "an addressee reference has unequal structured referent and addressee fields", "review"))
    if reference_type == "speaker_reference" and canonical_hint and normalize(discourse.get("speaker_hint")) and canonical_hint != normalize(discourse.get("speaker_hint")):
        flags.append(_flag("internal_field_conflict", ["referent.canonical_hint", "discourse.speaker_hint"], support, "a speaker reference has unequal structured referent and speaker fields", "review"))

    flags.extend(_identity_relation_conflicts(record))
    # Graph facts are only formal challenges.  No graph-neighborhood or text
    # similarity is used to select an identity here.
    for fact in graph_facts or []:
        if not isinstance(fact, Mapping):
            continue
        if text(fact.get("constraint")) == "same_person_and_explicit_distinct":
            flags.append(_flag("graph_relation_conflict", [fact.get("source"), fact.get("target")], [text(value) for value in fact.get("evidence_ids", []) or []], "supplied graph constraints contain an explicit identity/distinctness conflict", "hard"))
        if text(fact.get("constraint")) in {"self_parenthood", "self_marriage", "self_kinship"}:
            flags.append(_flag("graph_relation_conflict", [fact.get("constraint")], [text(value) for value in fact.get("evidence_ids", []) or []], "supplied graph constraints contain a prohibited reflexive relation", "hard"))

    weights = {"hard": 5, "review": 2}
    score = sum(weights.get(text(flag.get("severity")), 1) for flag in flags)
    if len({normalize(relation.get("target_hint")) for relation in record.get("relations", []) or [] if isinstance(relation, Mapping) and normalize(relation.get("target_hint"))}) > 1:
        # This is a review signal for multiple structured alternatives, not a
        # semantic conclusion about which alternative is correct.
        flags.append(_flag("multi_candidate_ambiguity", ["relations"], support, "the record supplies more than one structured relation target", "review"))
        score += 2
    return {
        "stage": stage,
        "flags": flags,
        "review_trigger_score": score,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def records_differ(left: Mapping[str, Any] | None, right: Mapping[str, Any] | None) -> dict[str, Any]:
    """Describe structured disagreement without choosing a semantic winner."""

    if not isinstance(left, Mapping) or not isinstance(right, Mapping):
        return {"different": True, "fields": ["record"]}
    fields = []
    for field in ("semantic_kind", "reference_type", "referent", "occurrence_role", "discourse", "relations", "confidence", "attribute_type", "attribute_value", "bearer_hint", "abstain"):
        if left.get(field) != right.get(field):
            fields.append(field)
    return {"different": bool(fields), "fields": fields}
