"""Proposal realization and alternative retrieval for SFH2.2-P1.

This module deliberately does not infer identity.  The proposal is copied from
validated LLM output, then Python looks up a matching registry entry or
allocates a deterministic candidate-only ID.  Legacy retrieval is retained as
an alternative dossier and can never replace the proposal candidate.
"""

from __future__ import annotations

from typing import Any, Mapping

from sfh2_2p.retrieval import build_candidate_set as build_legacy_candidate_set

from .common import evidence_index, normalize, stable_hash, text


HISTORICAL_PROPOSAL = "historical_person"
NON_PERSON_PROPOSALS = {"person_attribute", "collective_reference", "non_person", "structural_reference", "uncertain"}


def _people(inputs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        text(row.get("person_id")): dict(row)
        for row in (inputs.get("people") or {}).get("people", []) or []
        if isinstance(row, Mapping) and text(row.get("person_id"))
    }


def _aliases(inputs: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in (inputs.get("aliases") or {}).get("aliases", []) or [] if isinstance(row, Mapping)]


def _valid_exact_aliases(inputs: Mapping[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    people = _people(inputs)
    for row in _aliases(inputs):
        if text(row.get("resolution_mode")) != "exact":
            continue
        if text(row.get("status")) in {"suppressed_wrong_bearer", "suppressed", "rejected"}:
            continue
        surface = normalize(row.get("surface"))
        if not surface:
            continue
        for person_id in row.get("resolved_person_ids", []) or []:
            person_id = text(person_id)
            if person_id in people:
                result.setdefault(surface, set()).add(person_id)
    return result


def _candidate_id(display_name: str) -> str:
    return "sfh2-2p1-candidate-person-" + stable_hash({"display_name": normalize(display_name), "namespace": "historical-person-proposal"})[:20]


def _evidence_rows(packet: Mapping[str, Any], evidence_ids: list[str]) -> list[dict[str, Any]]:
    index = evidence_index(packet)
    result = []
    for evidence_id in sorted(set(text(value) for value in evidence_ids if text(value))):
        source = index.get(evidence_id)
        if not source:
            continue
        result.append({
            "evidence_id": evidence_id,
            "source_layer": source.get("source_layer"),
            "source_ref": source.get("source_ref"),
            "text": source.get("text"),
        })
    return result


def _legacy_alternatives(case: Mapping[str, Any], proposal: Mapping[str, Any], inputs: Mapping[str, Any], packet: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    # Pass a proposal-neutral semantic record into the old safe retriever.  It
    # is only an alternative source; the proposal candidate is inserted first.
    neutral = {
        "semantic_type": text((proposal.get("entity_interpretation") or {}).get("reference_type")) or "uncertain",
        "referent_hint": "",
        "supporting_evidence_ids": [],
        "network_role": text((proposal.get("entity_interpretation") or {}).get("network_role")) or "uncertain",
    }
    legacy = build_legacy_candidate_set(case, neutral, inputs)
    alternatives = []
    for old in legacy.get("candidates", []) or []:
        if not isinstance(old, Mapping):
            continue
        evidence_ids = [text(item.get("evidence_id")) for item in old.get("evidence", []) or [] if isinstance(item, Mapping)]
        # The LLM sees only evidence that is actually in its packet.  Registry
        # metadata remains visible as a candidate label/basis, not as an
        # unsupported source assertion.
        alternatives.append({
            "display_name": text(old.get("display_name")),
            "entity_type": text(old.get("entity_type")) or "existing_person",
            "person_id": text(old.get("person_id")),
            "candidate_person_id": text(old.get("candidate_person_id")),
            "retrieval_basis": sorted(set(text(value) for value in old.get("retrieval_basis", []) or [] if text(value))),
            "evidence": _evidence_rows(packet, evidence_ids),
            "legacy_candidate_key": text(old.get("candidate_key")),
        })
    return alternatives, list(legacy.get("hard_veto_person_ids", []) or []), list(legacy.get("hard_vetoes", []) or [])


def build_proposal_candidate_set(case: Mapping[str, Any], proposal: Mapping[str, Any] | None, inputs: Mapping[str, Any], packet: Mapping[str, Any]) -> dict[str, Any]:
    if not proposal:
        return {
            "case_id": case.get("case_id"), "mention_id": case.get("mention_id"), "story_id": case.get("story_id"),
            "surface": case.get("surface"), "proposal_candidate_key": None, "candidates": [],
            "hard_veto_person_ids": [], "hard_vetoes": [], "candidate_only": True, "canonical_write_back": False,
        }
    proposal_data = proposal.get("candidate_proposal") if isinstance(proposal.get("candidate_proposal"), Mapping) else {}
    proposal_kind = text(proposal_data.get("proposal_kind"))
    if proposal_kind != HISTORICAL_PROPOSAL or proposal.get("abstain") is True:
        return {
            "case_id": case.get("case_id"), "mention_id": case.get("mention_id"), "story_id": case.get("story_id"),
            "surface": case.get("surface"), "proposal_candidate_key": None, "candidates": [],
            "hard_veto_person_ids": [], "hard_vetoes": [], "proposal_kind": proposal_kind,
            "candidate_only": True, "canonical_write_back": False,
        }

    people = _people(inputs)
    exact_aliases = _valid_exact_aliases(inputs)
    canonical_hint = text(proposal.get("referent_canonical_hint"))
    display_name = text(proposal_data.get("display_name")) or canonical_hint or text(proposal.get("referent_surface")) or text(case.get("surface"))
    lookup_forms = [canonical_hint, display_name]
    existing_ids: list[str] = []
    for form in lookup_forms:
        norm = normalize(form)
        for person_id, person in people.items():
            if norm and normalize(person.get("canonical_name")) == norm and person_id not in existing_ids:
                existing_ids.append(person_id)
        for person_id in sorted(exact_aliases.get(norm, set())) if norm else []:
            if person_id not in existing_ids:
                existing_ids.append(person_id)
    # A proposal may name an existing person, but the proposal itself remains
    # the authority to interpret the target.  Python is only resolving the
    # registry key after the semantic proposal.
    if existing_ids:
        entity_type = "existing_person"
        person_id = existing_ids[0]
        candidate_person_id = ""
        registry_basis = ["llm_entity_proposal", "canonical_registry_lookup"]
    else:
        entity_type = "candidate_historical_person"
        person_id = ""
        candidate_person_id = _candidate_id(display_name)
        registry_basis = ["llm_entity_proposal", "candidate_historical_registry_miss"]
    proposal_evidence = [text(value) for value in proposal_data.get("supporting_evidence_ids", []) or [] if text(value)]
    proposal_candidate = {
        "candidate_key": "c0",
        "display_name": display_name,
        "entity_type": entity_type,
        "person_id": person_id,
        "candidate_person_id": candidate_person_id,
        "matched_surface": text(proposal.get("referent_surface")) or text(case.get("surface")),
        "retrieval_basis": registry_basis,
        "proposal_origin": "llm_entity_proposal",
        "evidence": _evidence_rows(packet, proposal_evidence),
        "proposal_evidence_ids": sorted(set(proposal_evidence)),
        "candidate_only": True,
        "canonical_write_back": False,
    }
    alternatives, veto_ids, vetoes = _legacy_alternatives(case, proposal, inputs, packet)
    candidates = [proposal_candidate]
    seen = {(entity_type, person_id, candidate_person_id, normalize(display_name))}
    for old in alternatives:
        signature = (old.get("entity_type"), old.get("person_id"), old.get("candidate_person_id"), normalize(old.get("display_name")))
        if signature in seen or not normalize(old.get("display_name")):
            continue
        seen.add(signature)
        candidates.append({
            "candidate_key": f"c{len(candidates)}",
            "display_name": old.get("display_name"),
            "entity_type": old.get("entity_type"),
            "person_id": old.get("person_id"),
            "candidate_person_id": old.get("candidate_person_id"),
            "matched_surface": old.get("display_name"),
            "retrieval_basis": old.get("retrieval_basis", []),
            "proposal_origin": "python_retrieval_alternative",
            "evidence": old.get("evidence", []),
            "proposal_evidence_ids": [],
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return {
        "case_id": case.get("case_id"), "mention_id": case.get("mention_id"), "story_id": case.get("story_id"),
        "surface": case.get("surface"), "proposal_candidate_key": "c0", "candidates": candidates,
        "hard_veto_person_ids": sorted(set(text(value) for value in veto_ids if text(value))),
        "hard_vetoes": vetoes,
        "proposal_display_name": display_name,
        "proposal_canonical_hint": canonical_hint,
        "candidate_only": True, "canonical_write_back": False,
    }


def candidate_registry_entry(candidate: Mapping[str, Any], case: Mapping[str, Any], proposal: Mapping[str, Any]) -> dict[str, Any] | None:
    if text(candidate.get("entity_type")) != "candidate_historical_person":
        return None
    if text((proposal.get("candidate_proposal") or {}).get("proposal_kind")) != HISTORICAL_PROPOSAL:
        return None
    return {
        "candidate_person_id": candidate.get("candidate_person_id"),
        "display_name": candidate.get("display_name"),
        "source_occurrence_ids": [text(case.get("mention_id"))],
        "source_case_ids": [text(case.get("case_id"))],
        "supporting_evidence_ids": sorted(set(text(value) for value in candidate.get("proposal_evidence_ids", []) or [] if text(value))),
        "semantic_referent_hints": sorted(set(value for value in [text(proposal.get("referent_canonical_hint")), text(proposal.get("referent_surface"))] if value)),
        "network_role": text((proposal.get("entity_interpretation") or {}).get("network_role")) or "uncertain",
        "candidate_only": True,
        "canonical_write_back": False,
    }
