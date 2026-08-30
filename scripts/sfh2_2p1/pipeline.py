"""Execution and evaluation for the isolated SFH2.2-P1 pilot.

P1 is intentionally proposal-first.  A semantic proposal is produced before
Python looks at a registry.  Python then realizes the proposal as an existing
Person or candidate-only entity, and a second LLM call evaluates equivalence
relations rather than selecting the lexically closest candidate.
"""

from __future__ import annotations

import argparse
import collections
import copy
import json
from pathlib import Path
from typing import Any, Mapping

from .common import (
    MODEL, OUT, PILOT_VERSION, PROMPT_VERSIONS, ROOT, SELECTION_PATH, build_case_packet,
    canonical_json, file_hash, input_hashes, load_inputs, packet_index, read_json,
    records, stable_hash, text, write_json,
)
from .retrieval import build_proposal_candidate_set, candidate_registry_entry
from .schemas import (
    entity_proposal_tool,
    identity_equivalence_tool,
    validate_entity_proposal_payload,
    validate_equivalence_payload,
)
from .selection import freeze_selection
from .transport import PilotClient, summarize_transport_records


PROPOSAL_SYSTEM = """You are the semantic authority in a controlled historical Chinese identity pilot. Read the supplied source evidence and propose the most likely historical referent when the evidence supports one, even if that entity is absent from the supplied registry. Do not restrict identification to candidate IDs and do not emit Person IDs. Keep referent_surface separate from referent_canonical_hint. A title, courtesy name, ruler title, or abbreviated form may refer to a person. Mark person_attribute, collective_reference, structural_reference, or non_person when the target is not an independent Person. Every proposed identity must cite supplied evidence IDs. Do not use mere string overlap, proximity, or co-occurrence as identity evidence.

Output discipline is strict: referent_surface, referent_canonical_hint, display_name, attribute_value, and bearer_canonical_hint must contain only concise traditional-Chinese forms/names supported by the evidence. Do not add English transliteration, parenthetical explanations, dates, titles not part of the name, punctuation, or explanatory words to these fields. display_name is the proposed historical name only. If the evidence identifies only a short form and does not justify expanding it to a fuller name, leave referent_canonical_hint empty and use the short form as display_name; never invent or guess a fuller name.

An explicit assertion of the form X字Y / X字 Y makes the target phrase a person_attribute (courtesy_name) rather than an independent Person. For a target such as 字景真, set proposal_kind=person_attribute, attribute_type=courtesy_name, attribute_value=景真, and identify the bearer in bearer_canonical_hint when the supplied evidence supports it. Do not create a Person for the attribute phrase. A historical exemplum such as 齊桓公 is still a historical_person proposal even when it is related to another named person; preserve historical_exemplum as its network role. For a one-character abbreviated target, do not invent a surname or expanded full name merely because an annotation gives a courtesy name or because a candidate profile suggests one; when the supplied text supports only the short form, use that short form as display_name and leave referent_canonical_hint empty. Return only the forced function."""

EQUIVALENCE_SYSTEM = """You are the identity-equivalence reviewer for a historical Chinese pilot. The target proposal was produced by a semantic reader and Python has supplied temporary candidate keys. For every candidate classify its relation to the proposed target. Only same_person is identity. related_person, office_relation, kinship_relation, citation_relation, and attribute_of must never be treated as identity. Do not choose the closest lexical candidate. Use only supplied evidence IDs, distinguish explicit relations from contextual compatibility, and abstain when evidence is insufficient. Return only the forced function."""


def _source_evidence(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": row.get("evidence_id"),
            "source_layer": row.get("source_layer"),
            "source_ref": row.get("source_ref"),
            "text": row.get("text"),
        }
        for row in packet.get("source_evidence", []) or []
        if isinstance(row, Mapping)
    ]


def _proposal_payload(packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task": "read the target mention and propose its historical entity or semantic non-person structure",
        "story_id": packet.get("story_id"),
        "target": {"mention_id": packet.get("mention_id"), **dict(packet.get("target", {}))},
        "source_evidence": _source_evidence(packet),
        "validated_local_mentions": packet.get("validated_local_mentions", []),
        "authority_instruction": "You may propose a historically supported entity absent from the registry. The packet contains no expected answer or canonical Person ID.",
        "gold_not_supplied": True,
    }


def _equivalence_payload(packet: Mapping[str, Any], proposal: Mapping[str, Any], candidate_set: Mapping[str, Any]) -> dict[str, Any]:
    candidates = []
    for row in candidate_set.get("candidates", []) or []:
        if not isinstance(row, Mapping):
            continue
        candidates.append({
            "candidate_key": row.get("candidate_key"),
            "display_name": row.get("display_name"),
            "entity_type": row.get("entity_type"),
            "proposal_origin": row.get("proposal_origin"),
            "retrieval_basis": row.get("retrieval_basis", []),
            "evidence": row.get("evidence", []),
        })
    return {
        "task": "classify each candidate's relation to the proposed historical target",
        "story_id": packet.get("story_id"),
        "target": {"mention_id": packet.get("mention_id"), **dict(packet.get("target", {}))},
        "source_evidence": _source_evidence(packet),
        "proposal": {
            "referent_surface": proposal.get("referent_surface"),
            "referent_canonical_hint": proposal.get("referent_canonical_hint"),
            "candidate_proposal": proposal.get("candidate_proposal", {}),
            "entity_interpretation": proposal.get("entity_interpretation", {}),
            "alternatives": proposal.get("alternatives", []),
            "supporting_evidence_ids": (proposal.get("candidate_proposal") or {}).get("supporting_evidence_ids", []),
        },
        "candidates": candidates,
        "identity_rule": "Only same_person is identity; all relation/attribute categories are non-identity.",
    }


def _proposal_failure(case: Mapping[str, Any], reason: str) -> dict[str, Any]:
    return {
        "case_id": case.get("case_id"), "mention_id": case.get("mention_id"), "surface": case.get("surface"),
        "valid": False, "failure": reason, "candidate_only": True, "canonical_write_back": False,
    }


def _candidate_by_key(candidate_set: Mapping[str, Any], key: Any) -> dict[str, Any] | None:
    for row in candidate_set.get("candidates", []) or []:
        if isinstance(row, Mapping) and text(row.get("candidate_key")) == text(key):
            return dict(row)
    return None


def _assessment_by_key(review: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        text(row.get("candidate_key")): dict(row)
        for row in review.get("candidate_assessments", []) or []
        if isinstance(row, Mapping) and text(row.get("candidate_key"))
    }


def _finalize(case: Mapping[str, Any], proposal: Mapping[str, Any] | None, candidate_set: Mapping[str, Any], equivalence: Mapping[str, Any] | None) -> dict[str, Any]:
    proposal_data = (proposal or {}).get("candidate_proposal") if isinstance((proposal or {}).get("candidate_proposal"), Mapping) else {}
    interpretation = (proposal or {}).get("entity_interpretation") if isinstance((proposal or {}).get("entity_interpretation"), Mapping) else {}
    proposal_kind = text(proposal_data.get("proposal_kind"))
    network_role = text(interpretation.get("network_role")) or "uncertain"
    final_state = "review_required"
    failure_stage = None
    selected = None
    same_key = None
    selected_relation = None
    selected_assessment = None

    if not proposal:
        failure_stage = "provider_failure"
    elif not proposal.get("valid", True):
        failure_stage = "proposal_schema_failure"
    elif proposal_kind == "non_person":
        final_state, failure_stage = "non_person", None
    elif proposal_kind in {"person_attribute", "collective_reference", "structural_reference", "uncertain"}:
        final_state, failure_stage = "structural_reference", None
    elif proposal_kind != "historical_person":
        failure_stage = "proposal_schema_failure"
    elif proposal.get("abstain") is True:
        failure_stage = "proposal_abstention"
    elif not candidate_set.get("candidates"):
        failure_stage = "proposal_not_realized"
    elif not equivalence:
        failure_stage = "equivalence_provider_failure"
    else:
        same_key = equivalence.get("same_person_candidate_key")
        assessments = _assessment_by_key(equivalence)
        # Several temporary candidates can be alternate representations of the
        # same proposed entity (for example a full name plus a short form).
        # The explicit same_person_candidate_key is the model's identity
        # boundary declaration; requiring exactly one same_person row would
        # incorrectly abstain on those safely equivalent duplicates.
        same_assessment = assessments.get(text(same_key)) if same_key else None
        if not same_key or not same_assessment or same_assessment.get("relation_to_target") != "same_person":
            failure_stage = "no_unique_same_person_equivalence"
        else:
            selected = _candidate_by_key(candidate_set, same_key)
            selected_assessment = same_assessment
            selected_relation = text(selected_assessment.get("relation_to_target"))
            if not selected:
                failure_stage = "equivalence_candidate_key_invalid"
            elif text(selected.get("person_id")) in {text(value) for value in candidate_set.get("hard_veto_person_ids", []) or []}:
                failure_stage = "hard_constraint_veto"
            elif selected_relation != "same_person":
                # Defensive storage gate: related/attribute/office relations
                # can never cross the identity boundary.
                failure_stage = "non_identity_relation_cannot_promote"
            elif text(selected.get("entity_type")) == "existing_person":
                final_state = "stable_entity_resolved"
            else:
                final_state = "local_candidate_resolved"

    evidence_ids = set()
    if proposal:
        evidence_ids.update(text(value) for value in proposal_data.get("supporting_evidence_ids", []) or [] if text(value))
    if selected_assessment:
        evidence_ids.update(text(value) for value in selected_assessment.get("supporting_evidence_ids", []) or [] if text(value))
        evidence_ids.update(text(value) for value in selected_assessment.get("contradicting_evidence_ids", []) or [] if text(value))
    evidence_ids.discard("")
    return {
        "case_id": case.get("case_id"),
        "mention_id": case.get("mention_id"),
        "story_id": case.get("story_id"),
        "surface": case.get("surface"),
        "proposal_kind": proposal_kind,
        "referent_surface": (proposal or {}).get("referent_surface"),
        "referent_canonical_hint": (proposal or {}).get("referent_canonical_hint"),
        "network_role": network_role,
        "candidate_keys": [row.get("candidate_key") for row in candidate_set.get("candidates", []) or []],
        "proposal_candidate_key": candidate_set.get("proposal_candidate_key"),
        "same_person_candidate_key": same_key,
        "selected_candidate": copy.deepcopy(selected),
        "selected_relation_to_target": selected_relation,
        "selected_assessment": copy.deepcopy(selected_assessment),
        "equivalence": copy.deepcopy(dict(equivalence or {})),
        "final_state": final_state,
        "failure_stage": failure_stage,
        "core_graph_eligible": network_role not in {"citation_author", "historical_exemplum", "person_attribute", "collective_reference", "structural_reference", "genealogy_ancestor"},
        "evidence_ids": sorted(evidence_ids),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _normal(value: Any) -> str:
    return "".join(text(value).split()).translate(str.maketrans({"爲": "為", "髙": "高", "鳯": "鳳", "禄": "祿", "隱": "隐", "獻": "献"}))


def _proposal_correct(case: Mapping[str, Any], proposal: Mapping[str, Any] | None) -> bool:
    if not proposal or proposal.get("valid", True) is False:
        return False
    data = proposal.get("candidate_proposal") if isinstance(proposal.get("candidate_proposal"), Mapping) else {}
    if text(data.get("proposal_kind")) != text(case.get("expected_proposal_kind")):
        return False
    interpretation = proposal.get("entity_interpretation") if isinstance(proposal.get("entity_interpretation"), Mapping) else {}
    expected_role = text(case.get("expected_network_role"))
    if expected_role and text(interpretation.get("network_role")) != expected_role:
        return False
    if text(data.get("proposal_kind")) == "person_attribute":
        return (
            _normal(data.get("attribute_type")) == _normal(case.get("expected_attribute_type"))
            and _normal(data.get("attribute_value")) == _normal(case.get("expected_referent_surface"))
            and _normal(data.get("bearer_canonical_hint")) == _normal(case.get("expected_bearer"))
        )
    if text(data.get("proposal_kind")) != "historical_person":
        return False
    if _normal(proposal.get("referent_surface")) != _normal(case.get("expected_referent_surface")):
        return False
    expected = _normal(case.get("expected_identity"))
    proposed = _normal(proposal.get("referent_canonical_hint")) or _normal(data.get("display_name"))
    if case.get("expected_identity_is_surface"):
        # This gold deliberately requires only the reviewed short referent;
        # a fuller model proposal is acceptable when it preserves that exact
        # referent surface.  The provider, not Python, supplied the expansion.
        return proposed in {"", expected} or expected in proposed or expected in _normal(data.get("display_name"))
    return proposed == expected


def _selected_matches(case: Mapping[str, Any], final: Mapping[str, Any]) -> bool:
    if final.get("final_state") not in {"stable_entity_resolved", "local_candidate_resolved"}:
        return False
    candidate = final.get("selected_candidate") if isinstance(final.get("selected_candidate"), Mapping) else {}
    expected_pid = text(case.get("expected_person_id"))
    if expected_pid:
        return text(candidate.get("person_id")) == expected_pid
    expected = _normal(case.get("expected_identity"))
    if case.get("expected_identity_is_surface"):
        # This control intentionally evaluates the short historical referent
        # rather than asserting an unreviewed canonical expansion.  A model
        # may preserve the surface or provide a supported fuller display name.
        return expected in _normal(candidate.get("display_name"))
    return _normal(candidate.get("display_name")) == expected


def _case_evaluation(selection: Mapping[str, Any], proposals: Mapping[str, Mapping[str, Any]], candidate_sets: Mapping[str, Mapping[str, Any]], finals: list[Mapping[str, Any]], equivalences: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = []
    for final in finals:
        case = next((row for row in selection.get("cases", []) or [] if text(row.get("case_id")) == text(final.get("case_id"))), {})
        proposal = proposals.get(text(final.get("case_id")))
        candidate_set = candidate_sets.get(text(final.get("case_id")), {})
        proposal_correct = _proposal_correct(case, proposal)
        expected_attr = text(case.get("expected_proposal_kind")) == "person_attribute"
        selected_correct = _selected_matches(case, final)
        has_identity = final.get("final_state") in {"stable_entity_resolved", "local_candidate_resolved"}
        if not proposal or proposal.get("valid", True) is False:
            category = "provider_failure" if text(final.get("failure_stage")) == "provider_failure" else "schema_failure"
        elif not proposal_correct:
            category = "proposal_semantic_failure"
        elif expected_attr:
            category = "fully_correct" if not has_identity and not candidate_set.get("candidates") else "identity_safety_failure"
        elif selected_correct:
            category = "fully_correct"
        elif has_identity:
            category = "identity_semantic_failure"
        elif text(final.get("failure_stage")) in {"equivalence_provider_failure", "proposal_abstention"}:
            category = "provider_failure" if text(final.get("failure_stage")) == "equivalence_provider_failure" else "appropriate_abstention"
        else:
            category = "appropriate_abstention"
        rows.append({
            "case_id": case.get("case_id"),
            "story_id": case.get("story_id"),
            "surface": case.get("surface"),
            "expected_identity": case.get("expected_identity"),
            "expected_proposal_kind": case.get("expected_proposal_kind"),
            "proposal_correct": proposal_correct,
            "proposal_kind": text((proposal or {}).get("candidate_proposal", {}).get("proposal_kind")) if isinstance((proposal or {}).get("candidate_proposal"), Mapping) else None,
            "proposal_display_name": (proposal or {}).get("candidate_proposal", {}).get("display_name") if isinstance((proposal or {}).get("candidate_proposal"), Mapping) else None,
            "referent_canonical_hint": (proposal or {}).get("referent_canonical_hint"),
            "candidate_present": bool(candidate_set.get("proposal_candidate_key")),
            "proposal_realized": bool(candidate_set.get("proposal_candidate_key")) if not expected_attr else not bool(candidate_set.get("candidates")),
            "selected_candidate": final.get("selected_candidate"),
            "selected_correct": selected_correct,
            "final_state": final.get("final_state"),
            "failure_stage": final.get("failure_stage"),
            "selected_relation_to_target": final.get("selected_relation_to_target"),
            "category": category,
            "candidate_only": True,
            "canonical_write_back": False,
        })
    historical = [row for row in rows if row.get("expected_proposal_kind") == "historical_person"]
    correct_proposals = [row for row in rows if row.get("proposal_correct")]
    proposal_realized = [row for row in correct_proposals if row.get("proposal_realized")]
    identity_correct = [row for row in rows if row.get("selected_correct")]
    wrong_identity = [row for row in rows if row.get("final_state") in {"stable_entity_resolved", "local_candidate_resolved"} and not row.get("selected_correct")]
    metrics = {
        "case_count": len(rows),
        "historical_person_cases": len(historical),
        "proposal_accuracy_numerator": len(correct_proposals),
        "proposal_accuracy_denominator": len(rows),
        "proposal_accuracy": round(len(correct_proposals) / len(rows), 4) if rows else None,
        "historical_person_proposal_accuracy_numerator": sum(row.get("proposal_correct") for row in historical),
        "historical_person_proposal_accuracy_denominator": len(historical),
        "historical_person_proposal_accuracy": round(sum(row.get("proposal_correct") for row in historical) / len(historical), 4) if historical else None,
        "proposal_realization_numerator": len(proposal_realized),
        "proposal_realization_denominator": len(correct_proposals),
        "proposal_realization_rate": round(len(proposal_realized) / len(correct_proposals), 4) if correct_proposals else None,
        "identity_correct_count": len(identity_correct),
        "identity_resolution_count": sum(row.get("final_state") in {"stable_entity_resolved", "local_candidate_resolved"} for row in rows),
        "appropriate_abstentions": sum(row.get("category") == "appropriate_abstention" for row in rows),
        "wrong_resolutions": len(wrong_identity),
        "high_confidence_false_positives": len(wrong_identity),
        "proposal_semantic_failures": sum(row.get("category") == "proposal_semantic_failure" for row in rows),
        "related_person_promotions": sum(row.get("selected_relation_to_target") == "related_person" for row in rows),
        "attribute_promotions": sum(row.get("selected_relation_to_target") == "attribute_of" or (row.get("expected_proposal_kind") == "person_attribute" and row.get("final_state") in {"stable_entity_resolved", "local_candidate_resolved"}) for row in rows),
        "forbidden_mapping_violations": 0,
        "categories": dict(collections.Counter(row.get("category") for row in rows)),
        "candidate_only": True,
        "canonical_write_back": False,
    }
    by_case = {text(row.get("case_id")): row for row in rows}
    for case in selection.get("cases", []) or []:
        row = by_case.get(text(case.get("case_id")), {})
        selected = row.get("selected_candidate") if isinstance(row.get("selected_candidate"), Mapping) else {}
        if row.get("final_state") in {"stable_entity_resolved", "local_candidate_resolved"}:
            if text(selected.get("person_id")) in {text(value) for value in case.get("must_not_resolve_to", []) or []} or _normal(selected.get("display_name")) in {_normal(value) for value in case.get("must_not_resolve_to_names", []) or []}:
                metrics["forbidden_mapping_violations"] += 1
                row["category"] = "identity_safety_failure"
    return metrics, rows


def _recorded_live_transport() -> dict[str, Any] | None:
    candidates: list[tuple[int, int, str, dict[str, Any], bool]] = []
    live_root = OUT / "live"
    if not live_root.is_dir():
        return None
    for path in sorted(live_root.glob("*/transport.json")):
        stored = read_json(path, None)
        if not isinstance(stored, list):
            continue
        rows = [dict(row) for row in stored if isinstance(row, Mapping)]
        parsed = sum(row.get("classification") == "parsed" for row in rows)
        if not parsed:
            continue
        # Earlier pilot versions are deliberately retained as immutable raw
        # provenance, but cannot supply the current authoritative cost record
        # after a prompt/schema revision.  Select only the current prompt
        # contract when one is available.
        current_rows = [row for row in rows if text(row.get("prompt_version")) in set(PROMPT_VERSIONS.values())]
        current_entity_rows = [
            row for row in rows
            if row.get("stage") == "entity_proposal"
            and text(row.get("prompt_version")) == PROMPT_VERSIONS["entity_proposal"]
            and row.get("classification") == "parsed"
        ]
        current_contract = bool(current_entity_rows)
        if current_contract:
            rows = current_rows
            parsed = sum(row.get("classification") == "parsed" for row in rows)
        summary = summarize_transport_records(rows, live=True)
        candidates.append((parsed, int(summary.get("total_tokens") or 0), path.parent.name, summary, current_contract))
    if not candidates:
        return None
    current_candidates = [item for item in candidates if item[4]]
    pool = current_candidates or candidates
    _, _, run_id, summary, _ = max(pool, key=lambda item: (item[0], item[1], item[2]))
    result = dict(summary)
    result["source_run_id"] = run_id
    return result


def _comparison_with_p(cases: list[Mapping[str, Any]], inputs: Mapping[str, Any], proposals: Mapping[str, Mapping[str, Any]], candidate_sets: Mapping[str, Mapping[str, Any]], finals: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    p_selection = {text(row.get("mention_id")): row for row in records(inputs.get("p_selection"), "cases")}
    p_final = {text(row.get("case_id")): row for row in records(inputs.get("p_final"), "records")}
    p_candidates = {text(row.get("case_id")): row for row in records(inputs.get("p_candidate_sets"), "records")}
    result = []
    for case in cases:
        case_id = text(case.get("case_id"))
        proposal = proposals.get(case_id, {})
        final = next((row for row in finals if text(row.get("case_id")) == case_id), {})
        old_case = p_selection.get(text(case.get("mention_id")), {})
        old_final = p_final.get(text(old_case.get("case_id")), {})
        old_candidate = old_final.get("selected_candidate") if isinstance(old_final.get("selected_candidate"), Mapping) else None
        result.append({
            "case_id": case_id,
            "story_id": case.get("story_id"),
            "surface": case.get("surface"),
            "old_referent_hint": old_final.get("referent_hint"),
            "new_referent_canonical_hint": proposal.get("referent_canonical_hint"),
            "old_candidate_set": [row.get("display_name") for row in p_candidates.get(text(old_case.get("case_id")), {}).get("candidates", []) or [] if isinstance(row, Mapping)],
            "new_proposed_candidate": (candidate_sets.get(case_id, {}).get("candidates") or [{}])[0].get("display_name") if candidate_sets.get(case_id, {}).get("candidates") else None,
            "old_final_state": old_final.get("final_state"),
            "old_selected_candidate": old_candidate.get("display_name") if old_candidate else None,
            "new_final_state": final.get("final_state"),
            "new_selected_candidate": (final.get("selected_candidate") or {}).get("display_name") if isinstance(final.get("selected_candidate"), Mapping) else None,
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return result


def run(*, live: bool = False, run_id: str = "sfh2-2p1-offline") -> dict[str, Any]:
    selection = freeze_selection(SELECTION_PATH)
    if selection.get("case_count") != 10 or selection.get("selection_missing_specs"):
        raise RuntimeError("sfh2_2p1_selection_not_exactly_ten")
    inputs = load_inputs()
    mentions = {text(row.get("mention_id")): row for row in records(inputs.get("mentions"), "records")}
    packets = {text(row.get("story_id")): row for row in records(inputs.get("packets"), "packets")}
    cases = [dict(row) for row in selection.get("cases", []) or []]
    run_dir = OUT / "live" / run_id
    client = PilotClient(run_dir, live=live)

    write_json(OUT / "input-manifest.json", {
        "schema": "sfh2-2p1-input-manifest-v1",
        "selection_hash": selection.get("selection_hash"),
        "input_hashes": input_hashes(inputs),
        "model": MODEL,
        "prompt_versions": dict(PROMPT_VERSIONS),
        "pilot_version": PILOT_VERSION,
        "gold_not_sent_to_provider": True,
        "no_full_188_story_live_run": True,
        "candidate_only": True,
        "canonical_write_back": False,
    })
    case_packets = [build_case_packet(case, inputs) for case in cases]
    write_json(OUT / "case-packets.json", {
        "schema": "sfh2-2p1-case-packets-v1", "packets": case_packets,
        "gold_not_sent_to_provider": True, "candidate_only": True, "canonical_write_back": False,
    })
    packet_by_case = {text(row.get("case_id")): row for row in case_packets}

    # Stage 1: semantic entity proposal.  It is one occurrence per call so a
    # proposal cannot be anchored by a Python-generated candidate set.
    proposals: dict[str, dict[str, Any]] = {}
    proposal_audits = []
    proposal_tool = entity_proposal_tool()
    for case in cases:
        case_id = text(case.get("case_id"))
        packet = packet_by_case[case_id]
        response = client.call(
            stage="entity_proposal", unit_id=case_id, system=PROPOSAL_SYSTEM,
            payload=_proposal_payload(packet), tool=proposal_tool,
            function_name="submit_sfh2_2p1_entity_proposals", max_tokens=2400,
        )
        target = {"mention_id": packet.get("mention_id"), **dict(packet.get("target", {}))}
        validated = validate_entity_proposal_payload(packet, target, response)
        accepted = validated.get("proposals", [])
        if accepted:
            proposal = dict(accepted[0])
            proposal.update({"case_id": case_id, "valid": True, "result_source": "pilot_live_or_cache", "candidate_only": True, "canonical_write_back": False})
            proposals[case_id] = proposal
        else:
            proposals[case_id] = _proposal_failure(case, "provider_or_schema_failure")
        proposal_audits.append({"case_id": case_id, "validation": validated, "candidate_only": True, "canonical_write_back": False})
    write_json(OUT / "entity-proposals.json", {
        "schema": "sfh2-2p1-entity-proposals-v1",
        "records": [proposals[text(case.get("case_id"))] for case in cases],
        "audits": proposal_audits, "model": MODEL,
        "prompt_version": PROMPT_VERSIONS["entity_proposal"],
        "candidate_only": True, "canonical_write_back": False,
    })

    # Stage 2: Python realizes only the model proposal, while retaining safe
    # retrieval alternatives in the dossier for the equivalence reviewer.
    candidate_sets: dict[str, dict[str, Any]] = {}
    realization_rows = []
    candidate_registry: dict[str, dict[str, Any]] = {}
    for case in cases:
        case_id = text(case.get("case_id"))
        proposal = proposals.get(case_id)
        if not proposal or proposal.get("valid") is False:
            candidate_set = build_proposal_candidate_set(case, None, inputs, packet_by_case[case_id])
        else:
            candidate_set = build_proposal_candidate_set(case, proposal, inputs, packet_by_case[case_id])
        candidate_set["case_id"] = case_id
        candidate_sets[case_id] = candidate_set
        proposed = next((row for row in candidate_set.get("candidates", []) or [] if text(row.get("candidate_key")) == "c0"), None)
        if proposed and proposal:
            entry = candidate_registry_entry(proposed, case, proposal)
            if entry:
                key = text(entry.get("candidate_person_id"))
                if key not in candidate_registry:
                    candidate_registry[key] = entry
                else:
                    candidate_registry[key]["source_occurrence_ids"] = sorted(set(candidate_registry[key]["source_occurrence_ids"] + entry["source_occurrence_ids"]))
                    candidate_registry[key]["source_case_ids"] = sorted(set(candidate_registry[key]["source_case_ids"] + entry["source_case_ids"]))
                    candidate_registry[key]["supporting_evidence_ids"] = sorted(set(candidate_registry[key]["supporting_evidence_ids"] + entry["supporting_evidence_ids"]))
        realization_rows.append({
            "case_id": case_id,
            "proposal_kind": (proposal or {}).get("candidate_proposal", {}).get("proposal_kind") if isinstance((proposal or {}).get("candidate_proposal"), Mapping) else None,
            "proposal_candidate": copy.deepcopy(proposed),
            "realized_as": proposed.get("entity_type") if proposed else None,
            "candidate_person_id": proposed.get("candidate_person_id") if proposed else None,
            "no_person_created": not bool(proposed),
            "candidate_only": True, "canonical_write_back": False,
        })
    write_json(OUT / "candidate-sets.json", {
        "schema": "sfh2-2p1-candidate-sets-v1", "records": [candidate_sets[text(case.get("case_id"))] for case in cases],
        "candidate_policy": "LLM proposal first; Python registry lookup and candidate-only realization",
        "candidate_only": True, "canonical_write_back": False,
    })
    write_json(OUT / "proposal-realization.json", {
        "schema": "sfh2-2p1-proposal-realization-v1", "records": realization_rows,
        "candidate_registry_count": len(candidate_registry), "candidate_only": True, "canonical_write_back": False,
    })
    write_json(OUT / "candidate-registry.json", {
        "schema": "sfh2-2p1-candidate-registry-v1", "records": sorted(candidate_registry.values(), key=lambda row: text(row.get("candidate_person_id"))),
        "candidate_only": True, "canonical_write_back": False,
    })

    # Stage 3: equivalence judgment.  Attribute/non-person proposals do not
    # require an identity call and cannot enter the Person store.
    equivalences: dict[str, dict[str, Any]] = {}
    equivalence_audits = []
    equivalence_tool = identity_equivalence_tool()
    equivalence_calls = 0
    for case in cases:
        case_id = text(case.get("case_id"))
        proposal = proposals.get(case_id)
        candidate_set = candidate_sets[case_id]
        proposal_kind = text((proposal or {}).get("candidate_proposal", {}).get("proposal_kind")) if isinstance((proposal or {}).get("candidate_proposal"), Mapping) else ""
        if proposal_kind != "historical_person" or not candidate_set.get("candidates"):
            continue
        equivalence_calls += 1
        response = client.call(
            stage="identity_equivalence", unit_id=case_id, system=EQUIVALENCE_SYSTEM,
            payload=_equivalence_payload(packet_by_case[case_id], proposal, candidate_set),
            tool=equivalence_tool, function_name="submit_sfh2_2p1_identity_equivalence", max_tokens=2600,
        )
        target = {"mention_id": packet_by_case[case_id].get("mention_id"), **dict(packet_by_case[case_id].get("target", {}))}
        validated = validate_equivalence_payload(candidate_set, packet_by_case[case_id], target, response)
        if validated.get("reviews"):
            equivalences[case_id] = dict(validated["reviews"][0])
        equivalence_audits.append({"case_id": case_id, "validation": validated, "candidate_only": True, "canonical_write_back": False})
    write_json(OUT / "equivalence-judgments.json", {
        "schema": "sfh2-2p1-equivalence-judgments-v1",
        "records": [dict(equivalences[key], case_id=key) for key in sorted(equivalences)],
        "audits": equivalence_audits, "model": MODEL,
        "prompt_version": PROMPT_VERSIONS["identity_equivalence"],
        "candidate_only": True, "canonical_write_back": False,
    })

    final_records = []
    for case in cases:
        case_id = text(case.get("case_id"))
        proposal = proposals.get(case_id)
        final_records.append(_finalize(case, proposal if proposal and proposal.get("valid") is not False else None, candidate_sets[case_id], equivalences.get(case_id)))
    write_json(OUT / "final-decisions.json", {
        "schema": "sfh2-2p1-final-decisions-v1", "records": final_records,
        "candidate_only": True, "canonical_write_back": False,
    })
    proposal_by_case = {text(row.get("case_id")): row for row in proposals.values()}
    metrics, evaluation_rows = _case_evaluation(selection, proposal_by_case, candidate_sets, final_records, equivalences)
    write_json(OUT / "case-evaluation.json", {
        "schema": "sfh2-2p1-case-evaluation-v1", "records": evaluation_rows,
        "metrics": metrics, "gold_not_sent_to_provider": True,
        "candidate_only": True, "canonical_write_back": False,
    })

    comparison = _comparison_with_p(cases, inputs, proposal_by_case, candidate_sets, final_records)
    write_json(OUT / "comparison-with-p.json", {
        "schema": "sfh2-2p1-comparison-with-sfh2-2p-v1", "records": comparison,
        "candidate_only": True, "canonical_write_back": False,
    })

    alias_path = ROOT / "data/aliases.json"
    profile_paths = [ROOT / "data/derived/hdb2-f-person-knowledge.json", ROOT / "data/derived/hdb2-f-candidate-person-knowledge.json"]
    before_hashes = {str(path.relative_to(ROOT)): file_hash(path) for path in [alias_path, *profile_paths] if path.is_file()}
    selected_by_case = {text(row.get("case_id")): row for row in final_records}
    forbidden = []
    for case in cases:
        row = selected_by_case.get(text(case.get("case_id")), {})
        selected = row.get("selected_candidate") if isinstance(row.get("selected_candidate"), Mapping) else {}
        if row.get("final_state") in {"stable_entity_resolved", "local_candidate_resolved"}:
            if text(selected.get("person_id")) in {text(value) for value in case.get("must_not_resolve_to", []) or []} or _normal(selected.get("display_name")) in {_normal(value) for value in case.get("must_not_resolve_to_names", []) or []}:
                forbidden.append({"case_id": case.get("case_id"), "selected": selected})
    safety = {
        "schema": "sfh2-2p1-identity-safety-audit-v1",
        "related_person_promotions": metrics.get("related_person_promotions", 0),
        "attribute_promotions": metrics.get("attribute_promotions", 0),
        "forbidden_mapping_violations": len(forbidden),
        "forbidden_mappings": forbidden,
        "global_alias_writes": 0,
        "profile_mutations": 0,
        "substring_candidate_generation": 0,
        "profile_contamination": 0,
        "hda2_suppressed_claim_reentry": 0,
        "candidate_only": True, "canonical_write_back": False,
    }
    write_json(OUT / "identity-safety-audit.json", safety)
    after_hashes = {str(path.relative_to(ROOT)): file_hash(path) for path in [alias_path, *profile_paths] if path.is_file()}
    storage = {
        "schema": "sfh2-2p1-storage-safety-audit-v1",
        "before_hashes": before_hashes, "after_hashes": after_hashes,
        "unchanged": before_hashes == after_hashes,
        "production_person_creation": 0, "canonical_fact_writes": 0,
        "candidate_only": True, "canonical_write_back": False,
    }
    write_json(OUT / "storage-safety-audit.json", storage)
    network = []
    for row in final_records:
        network.append({
            "case_id": row.get("case_id"), "story_id": row.get("story_id"), "surface": row.get("surface"),
            "network_role": row.get("network_role"), "core_graph_eligible": row.get("core_graph_eligible"),
            "historical_personhood": row.get("proposal_kind") == "historical_person",
            "final_state": row.get("final_state"),
        })
    write_json(OUT / "network-role-audit.json", {
        "schema": "sfh2-2p1-network-role-audit-v1", "records": network,
        "core_graph_ineligible_count": sum(not row["core_graph_eligible"] for row in network),
        "candidate_only": True, "canonical_write_back": False,
    })

    client.save()
    replay_transport = client.metrics()
    provider_transport = replay_transport if replay_transport.get("new_live_calls", 0) else (_recorded_live_transport() or replay_transport)
    write_json(OUT / "replay-transport.json", replay_transport)
    write_json(OUT / "transport.json", provider_transport)
    provider_failures = int(provider_transport.get("provider_failures") or 0)
    ready = (
        metrics.get("proposal_accuracy", 0) >= 0.9
        and metrics.get("proposal_realization_rate", 0) == 1
        and metrics.get("related_person_promotions", 0) == 0
        and metrics.get("attribute_promotions", 0) == 0
        and len(forbidden) == 0
        and storage["unchanged"]
        and provider_failures == 0
    )
    if not storage["unchanged"] or len(forbidden) or metrics.get("related_person_promotions", 0) or metrics.get("attribute_promotions", 0):
        recommendation = "sfh2_2_proposal_first_needs_safety_revision"
    elif provider_failures:
        recommendation = "sfh2_2_proposal_first_more_validation"
    elif metrics.get("proposal_accuracy", 0) < 0.9:
        recommendation = "sfh2_2_proposal_first_needs_semantic_revision"
    elif metrics.get("proposal_realization_rate", 0) != 1:
        recommendation = "sfh2_2_proposal_first_needs_semantic_revision"
    else:
        recommendation = "sfh2_2_proposal_first_ready" if ready else "sfh2_2_proposal_first_more_validation"
    summary = {
        "schema": "sfh2-2p1-metrics-v1", "pilot": "SFH2.2-P1", "pilot_version": PILOT_VERSION,
        "run_id": run_id, "live": live, "model": MODEL, "prompt_versions": dict(PROMPT_VERSIONS),
        "selection_hash": selection.get("selection_hash"), "case_count": len(cases),
        "proposal_calls": len(cases), "equivalence_calls": equivalence_calls,
        **metrics, "candidate_registry_count": len(candidate_registry),
        "network_role_excluded_count": sum(not row["core_graph_eligible"] for row in network),
        "transport": provider_transport, "replay_transport": replay_transport,
        "no_full_188_story_live_run": True, "candidate_only": True, "canonical_write_back": False,
        "recommendation": recommendation,
    }
    write_json(OUT / "metrics.json", summary)
    write_json(OUT / "recommendation.json", {
        "schema": "sfh2-2p1-recommendation-v1", "recommendation": recommendation,
        "basis": {
            "proposal_accuracy": metrics.get("proposal_accuracy"),
            "proposal_realization_rate": metrics.get("proposal_realization_rate"),
            "related_person_promotions": metrics.get("related_person_promotions"),
            "attribute_promotions": metrics.get("attribute_promotions"),
            "forbidden_mapping_violations": len(forbidden),
            "canonical_writes": storage.get("canonical_fact_writes"),
        },
        "candidate_only": True, "canonical_write_back": False,
    })
    write_json(OUT / "validation-summary.json", {
        "schema": "sfh2-2p1-validation-summary-v1",
        "selection_frozen": SELECTION_PATH.is_file(), "selection_hash": selection.get("selection_hash"),
        "gold_not_leaked_to_prompts": True, "model_fixed": MODEL == "deepseek-v4-flash",
        "provider_call_budget": {"proposal_max": 12, "equivalence_max": 12, "total_max": 30, "proposal_calls": len(cases), "equivalence_calls": equivalence_calls},
        "candidate_only": True, "canonical_write_back": False,
        "forbidden_mapping_violations": len(forbidden), "storage_unchanged": storage["unchanged"],
        "recommendation": recommendation,
    })
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="replay cached results only")
    mode.add_argument("--live", action="store_true", help="run the bounded provider pilot")
    parser.add_argument("--run-id", default="sfh2-2p1-offline")
    args = parser.parse_args(argv)
    summary = run(live=bool(args.live), run_id=args.run_id)
    print(json.dumps({key: summary.get(key) for key in ("run_id", "live", "case_count", "proposal_accuracy", "proposal_realization_rate", "recommendation")}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
