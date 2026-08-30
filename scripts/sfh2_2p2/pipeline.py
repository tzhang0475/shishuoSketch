"""Execution and structural reporting for the SFH2.2-P2 blind pilot.

The semantic mechanism is imported from SFH2.2-P1 unchanged.  This module
does not score historical correctness; that remains pending external review.
"""

from __future__ import annotations

import argparse
import collections
import copy
import json
from pathlib import Path
from typing import Any, Mapping

from sfh2_2p1 import pipeline as p1_pipeline
from sfh2_2p1 import schemas as p1_schemas
from sfh2_2p1.retrieval import candidate_registry_entry as p1_candidate_registry_entry

from .common import (
    MODEL, OUT, PILOT_VERSION, PROMPT_VERSIONS, ROOT, SELECTION_PATH, build_case_packet,
    architecture_freeze, canonical_json, file_hash, input_hashes, load_inputs,
    packet_source_evidence, read_json, records, stable_hash, story_excerpt, text,
    write_architecture_freeze, write_json,
)
from .retrieval import build_candidate_set
from .schemas import entity_proposal_tool, identity_equivalence_tool, validate_entity_proposal_payload, validate_equivalence_payload
from .selection import freeze_selection
from .transport import PilotClient, summarize_transport_records


# These aliases make it explicit that P2 uses the P1 semantic contracts.
PROPOSAL_SYSTEM = p1_pipeline.PROPOSAL_SYSTEM
EQUIVALENCE_SYSTEM = p1_pipeline.EQUIVALENCE_SYSTEM
_proposal_payload = p1_pipeline._proposal_payload
_equivalence_payload = p1_pipeline._equivalence_payload


def _finalize(case: Mapping[str, Any], proposal: Mapping[str, Any] | None, candidate_set: Mapping[str, Any], equivalence: Mapping[str, Any] | None) -> dict[str, Any]:
    """Apply the unchanged P1 identity gate with P2's fail-closed rendering.

    P1 correctly demotes a hard-vetoed candidate to ``review_required``.  It
    retains the rejected candidate in the diagnostic field, however, which is
    useful for P1 audit output but unsafe as a P2 final decision.  P2 clears
    that selected value only after the P1 gate has rejected the resolution;
    prompts, schemas, candidate ordering, and identity semantics remain P1.
    """
    result = p1_pipeline._finalize(case, proposal, candidate_set, equivalence)
    if result.get("final_state") == "review_required" and result.get("failure_stage") in {
        "hard_constraint_veto", "non_identity_relation_cannot_promote",
    }:
        result["selected_candidate"] = None
        result["selected_relation_to_target"] = None
        result["selected_assessment"] = None
    return result


def _rows(document: Any, key: str = "records") -> list[dict[str, Any]]:
    value = document.get(key) if isinstance(document, Mapping) else None
    return [dict(row) for row in value or [] if isinstance(row, Mapping)]


def _proposal_failure(case: Mapping[str, Any], reason: str) -> dict[str, Any]:
    return {
        "case_id": case.get("case_id"), "mention_id": case.get("mention_id"),
        "story_id": case.get("story_id"), "surface": case.get("surface"),
        "valid": False, "failure": reason, "candidate_only": True,
        "canonical_write_back": False,
    }


def _find_candidate(candidate_set: Mapping[str, Any], key: Any) -> dict[str, Any] | None:
    for row in candidate_set.get("candidates", []) or []:
        if isinstance(row, Mapping) and text(row.get("candidate_key")) == text(key):
            return dict(row)
    return None


def _assessment(candidate_set: Mapping[str, Any], key: Any) -> dict[str, Any] | None:
    for row in candidate_set.get("candidates", []) or []:
        if isinstance(row, Mapping) and text(row.get("candidate_key")) == text(key):
            return dict(row)
    return None


def _recorded_live_transport() -> dict[str, Any] | None:
    candidates: list[tuple[int, int, str, dict[str, Any]]] = []
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
        current = [row for row in rows if text(row.get("prompt_version")) in set(PROMPT_VERSIONS.values())]
        if current:
            rows = current
            parsed = sum(row.get("classification") == "parsed" for row in rows)
        summary = summarize_transport_records(rows, live=True)
        candidates.append((parsed, int(summary.get("total_tokens") or 0), path.parent.name, summary))
    if not candidates:
        return None
    _, _, run_id, summary = max(candidates, key=lambda item: (item[0], item[1], item[2]))
    result = dict(summary)
    result["source_run_id"] = run_id
    return result


def _internal_consistency(proposals: Mapping[str, Mapping[str, Any]], candidate_sets: Mapping[str, Mapping[str, Any]], equivalences: Mapping[str, Mapping[str, Any]], finals: list[Mapping[str, Any]]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    for final in finals:
        case_id = text(final.get("case_id"))
        proposal = proposals.get(case_id, {})
        proposal_data = proposal.get("candidate_proposal") if isinstance(proposal.get("candidate_proposal"), Mapping) else {}
        proposal_kind = text(proposal_data.get("proposal_kind"))
        final_state = text(final.get("final_state"))
        identity_state = final_state in {"stable_entity_resolved", "local_candidate_resolved"}
        if proposal.get("abstain") is True and identity_state:
            errors.append({"case_id": case_id, "error": "abstain_became_identity"})
        if proposal_kind == "person_attribute" and (identity_state or candidate_sets.get(case_id, {}).get("candidates")):
            errors.append({"case_id": case_id, "error": "person_attribute_created_person"})
        if proposal_kind in {"collective_reference", "non_person", "structural_reference"} and identity_state:
            errors.append({"case_id": case_id, "error": "non_personal_proposal_promoted"})
        if identity_state and text(final.get("selected_relation_to_target")) != "same_person":
            errors.append({"case_id": case_id, "error": "non_identity_relation_promoted"})
        role = text(final.get("network_role"))
        if role in {"citation_author", "historical_exemplum", "person_attribute", "collective_reference", "structural_reference", "genealogy_ancestor"} and final.get("core_graph_eligible") is True:
            errors.append({"case_id": case_id, "error": "excluded_network_role_graph_eligible"})
    for case_id, review in equivalences.items():
        key = review.get("same_person_candidate_key")
        if key is None:
            continue
        assessment_rows = [row for row in review.get("candidate_assessments", []) or [] if isinstance(row, Mapping) and text(row.get("candidate_key")) == text(key)]
        if not assessment_rows or text(assessment_rows[0].get("relation_to_target")) != "same_person":
            errors.append({"case_id": case_id, "error": "declared_same_person_not_same_person"})
    return {
        "schema": "sfh2-2p2-internal-consistency-audit-v1",
        "errors": errors,
        "error_count": len(errors),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _human_review(cases: list[Mapping[str, Any]], packets: Mapping[str, Mapping[str, Any]], proposals: Mapping[str, Mapping[str, Any]], candidate_sets: Mapping[str, Mapping[str, Any]], equivalences: Mapping[str, Mapping[str, Any]], finals: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], str]:
    rows = []
    markdown: list[str] = ["# SFH2.2-P2 Blind Review Sheet", "", "Historical correctness is intentionally pending external review.", ""]
    for case in cases:
        case_id = text(case.get("case_id"))
        packet = packets.get(case_id, {})
        proposal = proposals.get(case_id, {})
        candidate_set = candidate_sets.get(case_id, {})
        equivalence = equivalences.get(case_id, {})
        final = finals.get(case_id, {})
        proposal_data = proposal.get("candidate_proposal") if isinstance(proposal.get("candidate_proposal"), Mapping) else {}
        interpretation = proposal.get("entity_interpretation") if isinstance(proposal.get("entity_interpretation"), Mapping) else {}
        candidate_rows = [
            {
                "candidate_key": row.get("candidate_key"),
                "display_name": row.get("display_name"),
                "entity_type": row.get("entity_type"),
                "retrieval_basis": row.get("retrieval_basis", []),
                "evidence": row.get("evidence", []),
            }
            for row in candidate_set.get("candidates", []) or []
            if isinstance(row, Mapping)
        ]
        item = {
            "case_id": case_id,
            "story_id": case.get("story_id"),
            "surface": case.get("surface"),
            "main_text_excerpt": story_excerpt(packet),
            "liu_annotation": [row for row in packet_source_evidence(packet) if text(row.get("source_layer")) == "liu_annotation"],
            "other_relevant_registered_evidence": packet_source_evidence(packet),
            "entity_proposal": {
                "proposal_kind": proposal_data.get("proposal_kind"),
                "display_name": proposal_data.get("display_name"),
                "referent_surface": proposal.get("referent_surface"),
                "referent_canonical_hint": proposal.get("referent_canonical_hint"),
                "network_role": interpretation.get("network_role"),
                "confidence": proposal_data.get("confidence"),
                "supporting_evidence_ids": proposal_data.get("supporting_evidence_ids", []),
                "abstain": proposal.get("abstain"),
            },
            "realized_candidate": next((row for row in candidate_rows if text(row.get("candidate_key")) == "c0"), None),
            "alternative_candidates": [row for row in candidate_rows if text(row.get("candidate_key")) != "c0"],
            "equivalence_judgment": equivalence,
            "final_system_decision": {
                "final_state": final.get("final_state"),
                "failure_stage": final.get("failure_stage"),
                "selected_candidate": final.get("selected_candidate"),
                "selected_relation_to_target": final.get("selected_relation_to_target"),
                "core_graph_eligible": final.get("core_graph_eligible"),
            },
            "supporting_evidence_ids": sorted(set(text(value) for value in (proposal_data.get("supporting_evidence_ids", []) or []))),
            "candidate_only": True,
            "canonical_write_back": False,
        }
        rows.append(item)
        markdown.extend([
            f"## {case_id}",
            f"- Story: `{case.get('story_id')}`",
            f"- Surface: `{case.get('surface')}`",
            "",
            "### 正文 / evidence",
            f"{story_excerpt(packet) or '(no main-text excerpt)'}",
            "",
            "### Liu annotation / registered evidence",
            "\n".join(f"- `{row.get('evidence_id')}`: {row.get('text')}" for row in item["liu_annotation"]) or "- (none)",
            "",
            "### LLM entity proposal",
            f"- kind: `{proposal_data.get('proposal_kind')}`",
            f"- referent surface: `{proposal.get('referent_surface')}`",
            f"- canonical hint: `{proposal.get('referent_canonical_hint')}`",
            f"- network role: `{interpretation.get('network_role')}`",
            f"- confidence: `{proposal_data.get('confidence')}`",
            "",
            "### Candidate realization",
            canonical_json(item["realized_candidate"] or {}) or "{}",
            "",
            "### Equivalence judgment",
            canonical_json(equivalence) or "{}",
            "",
            "### Final decision",
            canonical_json(item["final_system_decision"]),
            "",
            "### Reviewer",
            "[ ] correct",
            "[ ] partially correct",
            "[ ] wrong identity",
            "[ ] should abstain",
            "[ ] insufficient evidence",
            "Reviewer expected referent:",
            "Reviewer notes:",
            "",
        ])
    return {
        "schema": "sfh2-2p2-human-review-v1",
        "records": rows,
        "historical_correctness": "pending_external_review",
        "candidate_only": True,
        "canonical_write_back": False,
    }, "\n".join(markdown)


def _metrics(cases: list[Mapping[str, Any]], proposals: Mapping[str, Mapping[str, Any]], candidate_sets: Mapping[str, Mapping[str, Any]], equivalences: Mapping[str, Mapping[str, Any]], finals: list[Mapping[str, Any]], transport: Mapping[str, Any], replay_transport: Mapping[str, Any]) -> dict[str, Any]:
    proposal_rows = [row for row in proposals.values() if row.get("valid") is not False]
    proposal_data = [row.get("candidate_proposal") if isinstance(row.get("candidate_proposal"), Mapping) else {} for row in proposal_rows]
    interpretations = [row.get("entity_interpretation") if isinstance(row.get("entity_interpretation"), Mapping) else {} for row in proposal_rows]
    assessments = [item for review in equivalences.values() for item in review.get("candidate_assessments", []) or [] if isinstance(item, Mapping)]
    states = collections.Counter(text(row.get("final_state")) for row in finals)
    kinds = collections.Counter(text(row.get("proposal_kind")) for row in proposal_data)
    relations = collections.Counter(text(row.get("relation_to_target")) for row in assessments)
    confidence = collections.Counter(text(row.get("confidence")) for row in proposal_data)
    c0 = []
    for row in candidate_sets.values():
        c0.extend(candidate for candidate in row.get("candidates", []) or [] if isinstance(candidate, Mapping) and text(candidate.get("candidate_key")) == "c0")
    production = sum(text(row.get("entity_type")) == "existing_person" for row in c0)
    registry_misses = sum(text(row.get("entity_type")) == "candidate_historical_person" for row in c0)
    return {
        "schema": "sfh2-2p2-metrics-pre-review-v1",
        "pilot": "SFH2.2-P2",
        "case_count": len(cases),
        "story_count": len({text(row.get("story_id")) for row in cases}),
        "proposal_kind_distribution": dict(sorted(kinds.items())),
        "historical_person_proposals": kinds.get("historical_person", 0),
        "person_attribute_proposals": kinds.get("person_attribute", 0),
        "structural_non_person_proposals": sum(kinds.get(key, 0) for key in ("collective_reference", "non_person", "structural_reference")),
        "uncertain_proposals": kinds.get("uncertain", 0),
        "abstentions": sum(row.get("abstain") is True for row in proposals.values()),
        "proposal_confidence_distribution": dict(sorted(confidence.items())),
        "high_confidence_proposals": confidence.get("high", 0),
        "existing_person_realizations": production,
        "candidate_historical_person_realizations": registry_misses,
        "registry_misses": registry_misses,
        "equivalence_case_count": len(equivalences),
        "equivalence_relation_distribution": dict(sorted(relations.items())),
        "same_person_judgments": relations.get("same_person", 0),
        "related_person_judgments": relations.get("related_person", 0),
        "different_person_judgments": relations.get("different_person", 0),
        "insufficient_judgments": relations.get("insufficient", 0),
        "final_state_distribution": dict(sorted(states.items())),
        "candidate_only": True,
        "canonical_write_back": False,
        "historical_accuracy": "pending_external_review",
        "production_person_creations": 0,
        "canonical_writes": 0,
        "global_alias_writes": 0,
        "profile_mutations": 0,
        "substring_derived_candidates": 0,
        "transport": transport,
        "replay_transport": replay_transport,
        "no_full_188_story_live_run": True,
    }


def _safety(before_hashes: Mapping[str, str], after_hashes: Mapping[str, str], candidate_sets: Mapping[str, Mapping[str, Any]], finals: list[Mapping[str, Any]], internal: Mapping[str, Any]) -> dict[str, Any]:
    invalid_candidate_ids = []
    unsafe_basis = []
    for row in candidate_sets.values():
        for candidate in row.get("candidates", []) or []:
            if not isinstance(candidate, Mapping):
                continue
            if text(candidate.get("candidate_key")) == "c0" and text(candidate.get("entity_type")) == "candidate_historical_person" and text(candidate.get("candidate_person_id")).startswith("person-"):
                invalid_candidate_ids.append(candidate.get("candidate_person_id"))
            basis = " ".join(text(item) for item in candidate.get("retrieval_basis", []) or []).lower()
            if any(token in basis for token in ("substring", "co_occurrence", "local_context_scan", "nearest")):
                unsafe_basis.append({"case_id": row.get("case_id"), "candidate_key": candidate.get("candidate_key"), "basis": candidate.get("retrieval_basis")})
    selected_non_identity = [row.get("case_id") for row in finals if row.get("final_state") in {"stable_entity_resolved", "local_candidate_resolved"} and text(row.get("selected_relation_to_target")) != "same_person"]
    return {
        "schema": "sfh2-2p2-automatic-safety-audit-v1",
        "production_person_creation": 0,
        "canonical_fact_writes": 0,
        "global_alias_writes": 0,
        "profile_mutations": 0,
        "occurrence_derived_alias_creation": 0,
        "substring_candidate_creation": 0,
        "related_person_promotions": 0,
        "attribute_person_promotions": 0,
        "invalid_candidate_ids": invalid_candidate_ids,
        "unsafe_retrieval_bases": unsafe_basis,
        "non_identity_promotions": selected_non_identity,
        "internal_consistency_error_count": int(internal.get("error_count") or 0),
        "protected_storage_unchanged": dict(before_hashes) == dict(after_hashes),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def run(*, live: bool = False, run_id: str = "sfh2-2p2-offline") -> dict[str, Any]:
    selection = freeze_selection(SELECTION_PATH)
    if selection.get("case_count") != 24 or selection.get("blind_case_count") != 24 or selection.get("gold_case_count") != 0:
        raise RuntimeError("sfh2_2p2_selection_not_exactly_blind")
    selection_hash = text(selection.get("selection_hash"))
    expected_architecture = architecture_freeze(selection_hash)
    freeze_path = OUT / "architecture-freeze.json"
    if freeze_path.is_file() and read_json(freeze_path, {}) != expected_architecture:
        raise RuntimeError("sfh2_2p2_architecture_changed")
    write_architecture_freeze(selection_hash)
    # Keep a generated, isolated copy for downstream validation/replay while
    # retaining the annotation path as the human-readable frozen selection.
    write_json(OUT / "selection.json", selection)
    inputs = load_inputs()
    hashes = input_hashes()
    manifest = {
        "schema": "sfh2-2p2-input-manifest-v1",
        "selection_hash": selection_hash,
        "input_hashes": hashes,
        "model": MODEL,
        "prompt_versions": dict(PROMPT_VERSIONS),
        "pilot_version": PILOT_VERSION,
        "gold_not_sent_to_provider": True,
        "selection_blind": True,
        "no_full_188_story_live_run": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    manifest_path = OUT / "input-manifest.json"
    if manifest_path.is_file() and read_json(manifest_path, {}) != manifest:
        raise RuntimeError("sfh2_2p2_input_manifest_changed")
    write_json(manifest_path, manifest)

    cases = [dict(row) for row in selection.get("cases", []) or []]
    write_json(OUT / "eligibility-audit.json", {
        "schema": "sfh2-2p2-eligibility-audit-v1",
        "selection_seed": selection.get("selection_seed"),
        "eligible_count": selection.get("eligible_count"),
        "excluded_count": selection.get("excluded_count"),
        "exclusion_counts": selection.get("exclusion_counts", {}),
        "stratum_quotas": selection.get("stratum_quotas", {}),
        "stratum_counts": selection.get("stratum_counts", {}),
        "quota_shortfalls": selection.get("quota_shortfalls", {}),
        "selected_case_ids": [text(row.get("case_id")) for row in cases],
        "selected_mention_ids": [text(row.get("mention_id")) for row in cases],
        "selection_basis": selection.get("selection_basis"),
        "answers_inspected": False,
        "candidate_only": True,
        "canonical_write_back": False,
    })
    packets = [build_case_packet(case, inputs) for case in cases]
    packet_by_case = {text(row.get("case_id")): row for row in packets}
    write_json(OUT / "case-packets.json", {
        "schema": "sfh2-2p2-case-packets-v1", "packets": packets,
        "gold_not_sent_to_provider": True, "candidate_only": True,
        "canonical_write_back": False,
    })
    client = PilotClient(OUT / "live" / run_id, live=live)

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
            proposal.update({"case_id": case_id, "valid": True, "result_source": "p2_live_or_cache", "candidate_only": True, "canonical_write_back": False})
            proposals[case_id] = proposal
        else:
            proposals[case_id] = _proposal_failure(case, "provider_or_schema_failure")
        proposal_audits.append({"case_id": case_id, "validation": validated, "candidate_only": True, "canonical_write_back": False})
    write_json(OUT / "entity-proposals.json", {
        "schema": "sfh2-2p2-entity-proposals-v1", "records": [proposals[text(case.get("case_id"))] for case in cases],
        "audits": proposal_audits, "model": MODEL, "prompt_version": PROMPT_VERSIONS["entity_proposal"],
        "gold_not_sent_to_provider": True, "candidate_only": True, "canonical_write_back": False,
    })

    candidate_sets: dict[str, dict[str, Any]] = {}
    candidate_registry: dict[str, dict[str, Any]] = {}
    realization_rows = []
    for case in cases:
        case_id = text(case.get("case_id"))
        proposal = proposals.get(case_id)
        candidate_set = build_candidate_set(case, proposal if proposal and proposal.get("valid") is not False else None, inputs, packet_by_case[case_id])
        candidate_set["case_id"] = case_id
        candidate_sets[case_id] = candidate_set
        proposed = _find_candidate(candidate_set, "c0")
        if proposed and proposal:
            entry = p1_candidate_registry_entry(proposed, case, proposal)
            if entry:
                key = text(entry.get("candidate_person_id"))
                if key not in candidate_registry:
                    candidate_registry[key] = entry
                else:
                    candidate_registry[key]["source_occurrence_ids"] = sorted(set(candidate_registry[key]["source_occurrence_ids"] + entry["source_occurrence_ids"]))
                    candidate_registry[key]["source_case_ids"] = sorted(set(candidate_registry[key]["source_case_ids"] + entry["source_case_ids"]))
                    candidate_registry[key]["supporting_evidence_ids"] = sorted(set(candidate_registry[key]["supporting_evidence_ids"] + entry["supporting_evidence_ids"]))
        proposal_data = proposal.get("candidate_proposal") if isinstance((proposal or {}).get("candidate_proposal"), Mapping) else {}
        realization_rows.append({
            "case_id": case_id,
            "proposal_kind": proposal_data.get("proposal_kind"),
            "proposal_candidate": copy.deepcopy(proposed),
            "realized_as": proposed.get("entity_type") if proposed else None,
            "candidate_person_id": proposed.get("candidate_person_id") if proposed else None,
            "no_person_created": not bool(proposed),
            "candidate_only": True, "canonical_write_back": False,
        })
    write_json(OUT / "candidate-sets.json", {
        "schema": "sfh2-2p2-candidate-sets-v1", "records": [candidate_sets[text(case.get("case_id"))] for case in cases],
        "candidate_policy": "frozen P1 proposal-first realization; P2-only candidate namespace",
        "candidate_only": True, "canonical_write_back": False,
    })
    write_json(OUT / "proposal-realization.json", {
        "schema": "sfh2-2p2-proposal-realization-v1", "records": realization_rows,
        "candidate_registry_count": len(candidate_registry), "candidate_only": True, "canonical_write_back": False,
    })
    write_json(OUT / "candidate-registry.json", {
        "schema": "sfh2-2p2-candidate-registry-v1", "records": sorted(candidate_registry.values(), key=lambda row: text(row.get("candidate_person_id"))),
        "candidate_only": True, "canonical_write_back": False,
    })

    equivalences: dict[str, dict[str, Any]] = {}
    equivalence_audits = []
    equivalence_tool = identity_equivalence_tool()
    for case in cases:
        case_id = text(case.get("case_id"))
        proposal = proposals.get(case_id)
        candidate_set = candidate_sets[case_id]
        proposal_data = proposal.get("candidate_proposal") if isinstance((proposal or {}).get("candidate_proposal"), Mapping) else {}
        if text(proposal_data.get("proposal_kind")) != "historical_person" or not candidate_set.get("candidates"):
            continue
        response = client.call(
            stage="identity_equivalence", unit_id=case_id, system=EQUIVALENCE_SYSTEM,
            payload=_equivalence_payload(packet_by_case[case_id], proposal, candidate_set), tool=equivalence_tool,
            function_name="submit_sfh2_2p1_identity_equivalence", max_tokens=2600,
        )
        target = {"mention_id": packet_by_case[case_id].get("mention_id"), **dict(packet_by_case[case_id].get("target", {}))}
        validated = validate_equivalence_payload(candidate_set, packet_by_case[case_id], target, response)
        if validated.get("reviews"):
            equivalences[case_id] = dict(validated["reviews"][0])
        equivalence_audits.append({"case_id": case_id, "validation": validated, "candidate_only": True, "canonical_write_back": False})
    write_json(OUT / "equivalence-judgments.json", {
        "schema": "sfh2-2p2-equivalence-judgments-v1", "records": [dict(equivalences[key], case_id=key) for key in sorted(equivalences)],
        "audits": equivalence_audits, "model": MODEL, "prompt_version": PROMPT_VERSIONS["identity_equivalence"],
        "gold_not_sent_to_provider": True, "candidate_only": True, "canonical_write_back": False,
    })

    final_records = []
    for case in cases:
        case_id = text(case.get("case_id"))
        proposal = proposals.get(case_id)
        final_records.append(_finalize(case, proposal if proposal and proposal.get("valid") is not False else None, candidate_sets[case_id], equivalences.get(case_id)))
    write_json(OUT / "final-decisions.json", {
        "schema": "sfh2-2p2-final-decisions-v1", "records": final_records,
        "candidate_only": True, "canonical_write_back": False,
    })

    finals_by_case = {text(row.get("case_id")): row for row in final_records}
    internal = _internal_consistency(proposals, candidate_sets, equivalences, final_records)
    write_json(OUT / "internal-consistency-audit.json", internal)
    before_hashes = input_hashes()
    after_hashes = input_hashes()
    safety = _safety(before_hashes, after_hashes, candidate_sets, final_records, internal)
    write_json(OUT / "automatic-safety-audit.json", safety)

    network_rows = []
    for row in final_records:
        network_rows.append({
            "case_id": row.get("case_id"), "story_id": row.get("story_id"), "surface": row.get("surface"),
            "network_role": row.get("network_role"), "core_graph_eligible": row.get("core_graph_eligible"),
            "final_state": row.get("final_state"), "historical_person_proposal": row.get("proposal_kind") == "historical_person",
        })
    write_json(OUT / "network-role-audit.json", {
        "schema": "sfh2-2p2-network-role-audit-v1", "records": network_rows,
        "core_graph_ineligible_count": sum(row.get("core_graph_eligible") is False for row in network_rows),
        "candidate_only": True, "canonical_write_back": False,
    })
    review, review_md = _human_review(cases, packet_by_case, proposals, candidate_sets, equivalences, finals_by_case)
    write_json(OUT / "human-review.json", review)
    (OUT / "human-review.md").write_text(review_md.rstrip("\n") + "\n", encoding="utf-8")

    client.save()
    replay_transport = client.metrics()
    provider_transport = replay_transport if replay_transport.get("new_live_calls", 0) else (_recorded_live_transport() or replay_transport)
    write_json(OUT / "replay-transport.json", replay_transport)
    write_json(OUT / "transport.json", provider_transport)
    metrics = _metrics(cases, proposals, candidate_sets, equivalences, final_records, provider_transport, replay_transport)
    write_json(OUT / "metrics-pre-review.json", metrics)
    structural_valid = not internal.get("errors") and safety.get("protected_storage_unchanged") and not safety.get("invalid_candidate_ids") and not safety.get("unsafe_retrieval_bases") and not safety.get("non_identity_promotions")
    recommendation = "sfh2_2p2_pending_external_review" if structural_valid else "sfh2_2p2_structural_failure"
    recommendation_doc = {
        "schema": "sfh2-2p2-recommendation-pre-review-v1",
        "recommendation": recommendation,
        "historical_accuracy": "pending_external_review",
        "structural_valid": structural_valid,
        "candidate_only": True, "canonical_write_back": False,
    }
    write_json(OUT / "recommendation-pre-review.json", recommendation_doc)
    write_json(OUT / "validation-summary.json", {
        "schema": "sfh2-2p2-validation-summary-v1",
        "selection_frozen": True,
        "selection_hash": selection_hash,
        "architecture_hash": expected_architecture.get("architecture_hash"),
        "historical_correctness": "pending_external_review",
        "structural_valid": structural_valid,
        "candidate_only": True, "canonical_write_back": False,
    })
    return {
        "selection": selection,
        "metrics": metrics,
        "recommendation": recommendation_doc,
        "transport": provider_transport,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--offline", action="store_true")
    parser.add_argument("--run-id", default="sfh2-2p2-offline")
    args = parser.parse_args(argv)
    result = run(live=bool(args.live), run_id=args.run_id)
    print(json.dumps({"selection_hash": result["selection"].get("selection_hash"), "case_count": result["selection"].get("case_count"), "recommendation": result["recommendation"].get("recommendation"), "transport": result["transport"]}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["recommendation"].get("recommendation") == "sfh2_2p2_pending_external_review" else 1


if __name__ == "__main__":
    raise SystemExit(main())
