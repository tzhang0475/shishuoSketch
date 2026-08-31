"""Post-semantic registry lookup and candidate-only realization.

This module never chooses between historical interpretations.  It receives a
validated LLM record and only maps its proposed canonical hint to an existing
registry entry or allocates a deterministic candidate-only entity.
"""

from __future__ import annotations

from typing import Any, Mapping

from .common import normalize, stable_hash, text

HISTORICAL_PERSON = "historical_person"
NON_PERSON_KINDS = {"person_attribute", "collective", "office", "place", "work", "structural", "other", "uncertain"}
CORE_EXCLUDED_ROLES = {
    "citation_source_person", "historical_exemplum", "person_attribute",
    "annotation_person", "collective_reference", "structural", "genealogy_reference",
}


def _people(inputs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    document = inputs.get("people") or {}
    rows = document.get("people", []) if isinstance(document, Mapping) else []
    return {text(row.get("person_id")): dict(row) for row in rows if isinstance(row, Mapping) and text(row.get("person_id"))}


def _exact_aliases(inputs: Mapping[str, Any]) -> dict[str, list[str]]:
    document = inputs.get("aliases") or {}
    rows = document.get("aliases", []) if isinstance(document, Mapping) else []
    result: dict[str, list[str]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or text(row.get("resolution_mode")) != "exact":
            continue
        if text(row.get("status")) in {"suppressed", "suppressed_wrong_bearer", "rejected"}:
            continue
        surface = normalize(row.get("surface"))
        if not surface:
            continue
        for person_id in row.get("resolved_person_ids", []) or []:
            if text(person_id):
                result.setdefault(surface, []).append(text(person_id))
    return {key: sorted(set(value)) for key, value in result.items()}


def _candidate_id(display_name: str) -> str:
    return "sfh2-a0-candidate-person-" + stable_hash({"namespace": "semantic-proposal", "display_name": normalize(display_name)})[:20]


def _core_eligible(role: str) -> bool:
    return role not in CORE_EXCLUDED_ROLES


def realize_semantic_record(case: Mapping[str, Any], record: Mapping[str, Any] | None, inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Materialize one LLM semantic proposal without semantic reinterpretation."""

    base = {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "identity_created": False,
        "candidate": None,
        "candidate_only": True,
        "canonical_write_back": False,
        "core_graph_eligible": False,
        "realization_basis": [],
    }
    if not isinstance(record, Mapping):
        base["realization_basis"] = ["no_valid_semantic_record"]
        return base
    semantic_kind = text(record.get("semantic_kind"))
    role = text(record.get("occurrence_role"))
    base["semantic_kind"] = semantic_kind
    base["occurrence_role"] = role
    base["core_graph_eligible"] = _core_eligible(role)
    if semantic_kind != HISTORICAL_PERSON or bool(record.get("abstain")):
        base["realization_basis"] = ["semantic_kind_does_not_create_person"]
        return base

    referent = record.get("referent") if isinstance(record.get("referent"), Mapping) else {}
    canonical_hint = text(referent.get("canonical_hint"))
    display_name = canonical_hint or text(referent.get("surface_form"))
    if not display_name:
        base["realization_basis"] = ["semantic_record_has_no_entity_label"]
        return base
    people = _people(inputs)
    aliases = _exact_aliases(inputs)
    matches: list[str] = []
    target = normalize(display_name)
    for person_id, person in people.items():
        if target and normalize(person.get("canonical_name")) == target:
            matches.append(person_id)
    matches.extend(person_id for person_id in aliases.get(target, []) if person_id in people)
    matches = sorted(set(matches))
    if matches:
        person_id = matches[0]
        candidate = {
            "entity_type": "existing_person",
            "person_id": person_id,
            "candidate_person_id": "",
            "display_name": people[person_id].get("canonical_name"),
            "proposed_display_name": display_name,
            "referent_canonical_hint": canonical_hint,
            "candidate_origin": "python_registry_lookup_after_llm_semantics",
            "candidate_only": True,
            "canonical_write_back": False,
        }
        base.update({"identity_created": True, "candidate": candidate, "realization_basis": ["llm_semantic_proposal", "canonical_registry_lookup"]})
        return base
    candidate_id = _candidate_id(display_name)
    candidate = {
        "entity_type": "candidate_historical_person",
        "person_id": "",
        "candidate_person_id": candidate_id,
        "display_name": display_name,
        "proposed_display_name": display_name,
        "referent_canonical_hint": canonical_hint,
        "source_occurrence_ids": [text(case.get("mention_id"))],
        "supporting_evidence_ids": sorted(set(text(value) for value in record.get("supporting_evidence_ids", []) or [] if text(value))),
        "candidate_origin": "llm_semantic_proposal_registry_miss",
        "candidate_only": True,
        "canonical_write_back": False,
    }
    base.update({"identity_created": True, "candidate": candidate, "realization_basis": ["llm_semantic_proposal", "candidate_registry_miss"]})
    return base
