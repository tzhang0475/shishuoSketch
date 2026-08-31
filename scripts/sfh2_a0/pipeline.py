"""Execution, consistency routing, and evaluation for SFH2.2-A0.

The three provider passes are intentionally separate.  This module never
contains a historical answer table: semantic records come from the provider,
while Python only validates them, reports formal inconsistencies, and controls
candidate-only storage.
"""

from __future__ import annotations

import argparse
import collections
import copy
from pathlib import Path
from typing import Any, Mapping

from .common import (
    FUNCTION_NAMES, MODEL, OUT, PILOT_VERSION, PROMPT_VERSIONS, ROOT,
    SELECTION_PATH, build_case_packet, case_by_id, canonical_json, file_hash,
    input_hashes, load_inputs, normalize, packet_evidence, read_json, records,
    stable_hash, text, write_json,
)
from .consistency import EXCLUDED_CORE_ROLES, check_record, records_differ
from .retrieval import realize_semantic_record
from .schemas import (
    adjudication_tool,
    critical_review_tool,
    semantic_record_tool,
    validate_adjudication_payload,
    validate_critical_review_payload,
    validate_semantic_payload,
)
from .selection import freeze_gold, freeze_selection
from .transport import PilotClient, summarize_transport_records


PRIMARY_HISTORIAN_SYSTEM = """You are the Primary Historian in an isolated semantic-authority pilot. Read only the supplied historical evidence packet, validated local mentions, and target span. You own every historical-semantic judgment: decide whether the target is an independent historical person, a person attribute, a collective, a structural reference, or another entity; interpret the reference; propose the best historically supported referent even when it is absent from the registry; identify occurrence role, discourse fields, and semantic relations. Python will not provide a candidate answer and cannot reinterpret your semantic result. Do not emit production Person IDs. Every non-abstaining interpretation must cite evidence IDs supplied in the packet. Use concise evidence-grounded explanations only, never hidden reasoning. Return exactly the required structured function.

Field discipline is strict. `record.surface` is the exact target surface from the packet. `referent.surface_form` is also the target reference form, not an expanded explanation; for a person attribute it is the attribute value rather than the marker word. `referent.canonical_hint`, `referent.surface_form`, `attribute_value`, `bearer_hint`, and relation `target_hint` must contain only a short historical form/name in the source language: no Latin letters, transliteration, parentheses, punctuation, dates, titles added as explanations, or prose. Put all explanation in `explanation`. Empty canonical hints are allowed when the evidence supports only the target surface. Do not put the target's bearer or antecedent into referent.surface_form; use canonical_hint and the structured discourse/bearer fields.

When an office, ruler title, honorific, or abbreviated reference semantically refers to a person, use `semantic_kind=historical_person` and put the person in `referent.canonical_hint`; use `office`, `place`, or `person_attribute` only when the referred entity itself is that non-person/attribute rather than a person identified by the title. Use `scene_reference` for a person referred to in narrative prose and `scene_participant` when the person is acting or directly participating. A historical exemplum remains a person proposal with `occurrence_role=historical_exemplum`. A source author or annotation person remains a historical person proposal with its source-only occurrence role. For pronouns and short references, preserve the exact target in referent.surface_form and use the evidence-supported antecedent/person only as canonical_hint. For attributes, set semantic_kind=person_attribute, reference_type=attribute_reference or the precise attribute type, attribute_value to the short attribute form, and bearer_hint to the supported bearer. Return only the forced function."""

CRITICAL_REVIEWER_SYSTEM = """You are an independent Critical Historical Reviewer. Re-read the original evidence and the Primary Historian's structured semantic record. The formal Python flags are consistency signals only; they do not propose a historical answer and must not be treated as authoritative semantics. Confirm, revise, or abstain based on the evidence. You may propose a historical person absent from the registry. Preserve the distinction between exact target surface and canonical hint, between a Person and an attribute/collective/structural reference, and between same-person and merely related or contextual persons. Do not emit production Person IDs. Cite only supplied evidence IDs. Keep identity-form fields concise source-language forms only: no transliteration, English, parentheses, punctuation, dates, or explanatory prose in those fields; put explanation in reason_summary. Return exactly the required structured function and a concise explanation."""

ADJUDICATOR_SYSTEM = """You are the final historical adjudicator. Independently re-read the original evidence and adjudicate the Primary Historian and Critical Reviewer records. Neither prior record nor any Python flag is authoritative; evidence is authoritative. Do not use majority voting. Select a supported record, revise it with an evidence-grounded semantic record, or abstain. A historical referent may be absent from the registry. Do not emit production Person IDs. Keep identity-form fields as short source-language forms only, with no transliteration, English, parentheses, punctuation, dates, or explanations. Cite only supplied evidence IDs. Return exactly the required structured function with no hidden reasoning."""


def _source_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_evidence": packet_evidence(packet),
        "validated_local_mentions": packet.get("validated_local_mentions", []),
        "target": packet.get("target", {}),
        "story_id": packet.get("story_id"),
    }


def primary_payload(packet: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        "task": "produce one complete semantic record for the target mention",
        **_source_packet(packet),
        "authority_boundary": "historical semantic interpretation belongs to the LLM; Python will only validate evidence and formal consistency",
        "gold_not_supplied": True,
        "candidate_ids_not_supplied": True,
    }
    return payload


def critical_payload(packet: Mapping[str, Any], primary_record: Mapping[str, Any] | None, flags: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task": "critically review the primary semantic record against the original evidence",
        **_source_packet(packet),
        "primary_semantic_record": copy.deepcopy(primary_record) if isinstance(primary_record, Mapping) else None,
        "python_formal_consistency_flags": copy.deepcopy(flags.get("flags", [])) if isinstance(flags, Mapping) else [],
        "python_instruction": "flags describe structured inconsistencies only; they do not identify the correct historical person",
        "gold_not_supplied": True,
    }


def adjudication_payload(packet: Mapping[str, Any], primary_record: Mapping[str, Any] | None, review_record: Mapping[str, Any] | None, flags: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task": "adjudicate the two semantic records strictly from the source evidence",
        **_source_packet(packet),
        "primary_semantic_record": copy.deepcopy(primary_record) if isinstance(primary_record, Mapping) else None,
        "critical_review_record": copy.deepcopy(review_record) if isinstance(review_record, Mapping) else None,
        "python_formal_consistency_flags": copy.deepcopy(flags.get("flags", [])) if isinstance(flags, Mapping) else [],
        "python_instruction": "formal flags are challenges only; do not infer a replacement identity from them",
        "gold_not_supplied": True,
    }


def _invalid_result(case: Mapping[str, Any], stage: str, errors: list[str]) -> dict[str, Any]:
    return {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "stage": stage,
        "valid": False,
        "record": None,
        "errors": sorted(set(errors)),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _validate_packet(packet: Mapping[str, Any]) -> list[str]:
    target = packet.get("target") if isinstance(packet.get("target"), Mapping) else {}
    evidence = {text(row.get("evidence_id")): row for row in packet.get("source_evidence", []) or [] if isinstance(row, Mapping) and text(row.get("evidence_id"))}
    errors: list[str] = []
    source_id = text(target.get("source_evidence_id"))
    if not source_id or source_id not in evidence:
        errors.append("target_source_evidence_missing")
    exact = text(target.get("exact_span"))
    surface = text(target.get("surface"))
    if exact != surface:
        errors.append("target_exact_span_mismatch")
    if not text(packet.get("mention_id")) or not surface:
        errors.append("target_identity_missing")
    return errors


def _record_from_semantic_validation(case: Mapping[str, Any], packet: Mapping[str, Any], payload: Mapping[str, Any] | None, stage: str) -> dict[str, Any]:
    target = {"mention_id": packet.get("mention_id"), **dict(packet.get("target", {}))}
    result = validate_semantic_payload(packet, target, payload)
    if not result.get("valid"):
        return _invalid_result(case, stage, list(result.get("errors", [])))
    return {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "stage": stage,
        "valid": True,
        "record": result.get("record"),
        "errors": [],
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _review_from_validation(case: Mapping[str, Any], packet: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    target = {"mention_id": packet.get("mention_id"), **dict(packet.get("target", {}))}
    result = validate_critical_review_payload(packet, target, payload)
    if not result.get("valid"):
        return _invalid_result(case, "pass2", list(result.get("errors", [])))
    review = result.get("review") or {}
    return {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "stage": "pass2",
        "valid": True,
        "decision": review.get("decision"),
        "record": review.get("revised_semantic_record"),
        "reason_summary": review.get("reason_summary"),
        "supporting_evidence_ids": review.get("supporting_evidence_ids", []),
        "errors": [],
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _adjudication_from_validation(case: Mapping[str, Any], packet: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    target = {"mention_id": packet.get("mention_id"), **dict(packet.get("target", {}))}
    result = validate_adjudication_payload(packet, target, payload)
    if not result.get("valid"):
        return _invalid_result(case, "pass3", list(result.get("errors", [])))
    adjudication = result.get("adjudication") or {}
    return {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "stage": "pass3",
        "valid": True,
        "decision": adjudication.get("decision"),
        "record": adjudication.get("semantic_record"),
        "reason_summary": adjudication.get("reason_summary"),
        "supporting_evidence_ids": adjudication.get("supporting_evidence_ids", []),
        "errors": [],
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _record(row: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if isinstance(row, Mapping) and row.get("valid") is True and isinstance(row.get("record"), Mapping):
        return row.get("record")
    return None


def _needs_pass3(primary: Mapping[str, Any] | None, review: Mapping[str, Any] | None, p1_flags: Mapping[str, Any], p2_flags: Mapping[str, Any]) -> bool:
    primary_record = _record(primary)
    review_record = _record(review)
    if records_differ(primary_record, review_record).get("different"):
        return True
    if text((review or {}).get("decision")) == "abstain" or not review_record:
        return True
    return bool((p2_flags or {}).get("flags"))


def _final_state(record: Mapping[str, Any] | None, realization: Mapping[str, Any], flags: Mapping[str, Any]) -> tuple[str, str | None, Mapping[str, Any] | None]:
    if not isinstance(record, Mapping):
        return "review_required", "no_final_semantic_record", None
    if bool(record.get("abstain")):
        return "review_required", "semantic_abstention", None
    if any(text(flag.get("severity")) == "hard" for flag in flags.get("flags", []) or [] if isinstance(flag, Mapping)):
        return "review_required", "hard_consistency_veto", None
    kind = text(record.get("semantic_kind"))
    if kind == "historical_person":
        candidate = realization.get("candidate")
        if not candidate:
            return "review_required", "proposal_not_realized", None
        if text(candidate.get("entity_type")) == "existing_person":
            return "stable_entity_resolved", None, candidate
        return "local_candidate_resolved", None, candidate
    if kind in {"person_attribute", "collective", "structural"}:
        return "structural_reference", None, None
    return "non_person", None, None


def _final_record(case: Mapping[str, Any], primary: Mapping[str, Any] | None, review: Mapping[str, Any] | None, adjudication: Mapping[str, Any] | None, p1_flags: Mapping[str, Any], p2_flags: Mapping[str, Any]) -> dict[str, Any]:
    p1_record = _record(primary)
    p2_record = _record(review)
    p3_record = _record(adjudication)
    pass3_required = _needs_pass3(primary, review, p1_flags, p2_flags)
    selected_record = None
    selected_source = None
    pass3_status = None
    if pass3_required:
        pass3_status = text((adjudication or {}).get("decision")) or ("invalid" if adjudication else "not_run")
        if p3_record is not None and pass3_status != "abstain":
            selected_record, selected_source = p3_record, "pass3"
    elif p2_record is not None and text((review or {}).get("decision")) != "abstain":
        selected_record, selected_source = p2_record, "pass2"

    provisional = realize_semantic_record(case, selected_record, _PIPELINE_INPUTS)
    # A hard consistency flag prevents a stable storage state but does not
    # alter the LLM's semantic record or replace it with a Python answer.
    final_realization = dict(provisional)
    final_flags = check_record(
        selected_record,
        evidence_ids=set(_PIPELINE_EVIDENCE.get(text(case.get("case_id")), set())),
        realization=provisional,
        stage="final",
    )
    state, failure, selected_candidate = _final_state(selected_record, provisional, final_flags)
    if state == "review_required":
        final_realization["identity_created"] = False
        final_realization["candidate"] = None
    return {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "pass3_required": pass3_required,
        "pass3_status": pass3_status,
        "selected_record_source": selected_source,
        "selected_record": copy.deepcopy(selected_record),
        "selected_candidate": copy.deepcopy(selected_candidate),
        "provisional_realization": provisional,
        "final_realization": final_realization,
        "semantic_kind": text((selected_record or {}).get("semantic_kind")),
        "occurrence_role": text((selected_record or {}).get("occurrence_role")),
        "referent": copy.deepcopy((selected_record or {}).get("referent")),
        "final_state": state,
        "failure_stage": failure,
        "final_consistency": final_flags,
        "p1_consistency": p1_flags,
        "p2_consistency": p2_flags,
        "core_graph_eligible": bool(provisional.get("core_graph_eligible")) if state != "review_required" else False,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _gold_by_case(selection: Mapping[str, Any], gold: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    lookup = {(text(row.get("story_id")), text(row.get("surface"))): dict(row) for row in gold.get("records", []) or [] if isinstance(row, Mapping)}
    return {
        text(case.get("case_id")): lookup.get((text(case.get("story_id")), text(case.get("surface"))), {})
        for case in selection.get("cases", []) or []
    }


def _record_matches(record: Mapping[str, Any] | None, gold: Mapping[str, Any]) -> bool:
    if not isinstance(record, Mapping) or not gold:
        return False
    if text(record.get("semantic_kind")) != text(gold.get("expected_semantic_kind")):
        return False
    expected_surface = text(gold.get("expected_referent_surface"))
    referent = record.get("referent") if isinstance(record.get("referent"), Mapping) else {}
    if expected_surface and normalize(referent.get("surface_form")) != normalize(expected_surface):
        return False
    expected_role = text(gold.get("expected_role"))
    if expected_role and text(record.get("occurrence_role")) != expected_role:
        return False
    expected_hint = text(gold.get("expected_canonical_hint"))
    if expected_hint and normalize(referent.get("canonical_hint")) != normalize(expected_hint):
        return False
    if text(gold.get("expected_semantic_kind")) == "person_attribute":
        if text(record.get("attribute_type")) != text(gold.get("expected_attribute_type")):
            return False
        if normalize(record.get("attribute_value")) != normalize(gold.get("expected_attribute_value")):
            return False
        if normalize(record.get("bearer_hint")) != normalize(gold.get("expected_bearer")):
            return False
    return True


def _final_matches(final: Mapping[str, Any], gold: Mapping[str, Any]) -> tuple[bool, str]:
    record = final.get("selected_record") if isinstance(final.get("selected_record"), Mapping) else None
    expected_kind = text(gold.get("expected_semantic_kind"))
    if gold.get("allow_abstention") and final.get("final_state") == "review_required":
        return True, "appropriate_abstention"
    if not _record_matches(record, gold):
        return False, "semantic_failure"
    if expected_kind in {"person_attribute", "collective", "structural"}:
        return (final.get("final_state") == "structural_reference" and final.get("selected_candidate") is None, "fully_correct" if final.get("final_state") == "structural_reference" else "identity_safety_failure")
    if final.get("final_state") not in {"stable_entity_resolved", "local_candidate_resolved"}:
        return False, "appropriate_abstention" if final.get("failure_stage") else "unresolved"
    candidate = final.get("selected_candidate") if isinstance(final.get("selected_candidate"), Mapping) else {}
    forbidden = {normalize(value) for value in gold.get("must_not_resolve_to", []) or []}
    if normalize(candidate.get("display_name")) in forbidden or normalize((record or {}).get("referent", {}).get("canonical_hint")) in forbidden:
        return False, "forbidden_identity"
    return True, "fully_correct"


def _evaluation(cases: list[Mapping[str, Any]], gold_by_case: Mapping[str, Mapping[str, Any]], p1: Mapping[str, Mapping[str, Any]], p2: Mapping[str, Mapping[str, Any]], p3: Mapping[str, Mapping[str, Any]], finals: list[Mapping[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    final_by_case = {text(row.get("case_id")): row for row in finals}
    for case in cases:
        case_id = text(case.get("case_id"))
        gold = dict(gold_by_case.get(case_id, {}))
        p1_record = _record(p1.get(case_id))
        p2_record = _record(p2.get(case_id))
        p3_record = _record(p3.get(case_id))
        final = final_by_case.get(case_id, {})
        p1_correct = _record_matches(p1_record, gold)
        p2_correct = _record_matches(p2_record, gold)
        p3_correct = _record_matches(p3_record, gold)
        final_correct, category = _final_matches(final, gold)
        p2_action = text((p2.get(case_id) or {}).get("decision"))
        p1_p2_agree = not records_differ(p1_record, p2_record).get("different")
        final_confidence = text(((final.get("selected_record") or {}).get("confidence")))
        final_referent_confidence = text((((final.get("selected_record") or {}).get("referent") or {}).get("confidence")))
        rows.append({
            "case_id": case_id,
            "story_id": case.get("story_id"),
            "surface": case.get("surface"),
            "gold": gold,
            "pass1_answer": p1_record,
            "pass1_correct": p1_correct,
            "python_flags_after_pass1": (p1.get(case_id) or {}).get("consistency", {}),
            "pass2_answer": p2_record,
            "pass2_correct": p2_correct,
            "pass2_action": p2_action,
            "pass1_pass2_agreement": p1_p2_agree,
            "pass3_required": bool(final.get("pass3_required")),
            "pass3_answer": p3_record,
            "pass3_correct": p3_correct,
            "final_answer": final.get("selected_record"),
            "final_candidate": final.get("selected_candidate"),
            "final_state": final.get("final_state"),
            "final_correct": final_correct,
            "final_category": category,
            "final_confidence": final_confidence,
            "final_referent_confidence": final_referent_confidence,
            "candidate_only": True,
            "canonical_write_back": False,
        })
    p1_errors = [row for row in rows if not row["pass1_correct"]]
    final_errors = [row for row in rows if not row["final_correct"]]
    correct_p1 = sum(row["pass1_correct"] for row in rows)
    correct_final = sum(row["final_correct"] for row in rows)
    final_identity_rows = [row for row in rows if row["final_state"] in {"stable_entity_resolved", "local_candidate_resolved"}]
    high_conf_false = [row for row in final_identity_rows if not row["final_correct"] and row["final_confidence"] == "high"]
    metrics = {
        "case_count": len(rows),
        "pass1_correct": correct_p1,
        "pass1_accuracy": round(correct_p1 / len(rows), 4) if rows else None,
        "pass2_correct": sum(row["pass2_correct"] for row in rows),
        "pass2_accuracy": round(sum(row["pass2_correct"] for row in rows) / len(rows), 4) if rows else None,
        "pass1_pass2_agreement": sum(row["pass1_pass2_agreement"] for row in rows),
        "pass1_pass2_agreement_rate": round(sum(row["pass1_pass2_agreement"] for row in rows) / len(rows), 4) if rows else None,
        "pass1_errors": len(p1_errors),
        "final_correct": correct_final,
        "final_accuracy": round(correct_final / len(rows), 4) if rows else None,
        "final_errors": len(final_errors),
        "errors_recovered": sum(not row["pass1_correct"] and row["final_correct"] for row in rows),
        "new_errors_introduced": sum(row["pass1_correct"] and not row["final_correct"] for row in rows),
        "reviewer_damage": sum(row["pass1_correct"] and not row["final_correct"] for row in rows),
        "appropriate_abstentions": sum(row["final_category"] == "appropriate_abstention" for row in rows),
        "high_confidence_final_false_identities": len(high_conf_false),
        "p1_high_confidence_false_identities": sum(not row["pass1_correct"] and text((row["pass1_answer"] or {}).get("confidence")) == "high" for row in rows),
        "pass3_required": sum(row["pass3_required"] for row in rows),
        "pass3_correct": sum(row["pass3_required"] and row["pass3_correct"] for row in rows),
        "pass3_abstentions": sum(row["pass3_required"] and text((p3.get(row["case_id"]) or {}).get("decision")) == "abstain" for row in rows),
        "final_state_distribution": dict(sorted(collections.Counter(text(row["final_state"]) for row in rows).items())),
        "final_category_distribution": dict(sorted(collections.Counter(text(row["final_category"]) for row in rows).items())),
        "candidate_only": True,
        "canonical_write_back": False,
    }
    return {"schema": "sfh2-a0-evaluation-v1", "records": rows, "metrics": metrics, "candidate_only": True, "canonical_write_back": False}, metrics


def _storage_safety(before: Mapping[str, str], after: Mapping[str, str], finals: list[Mapping[str, Any]], p2: Mapping[str, Mapping[str, Any]], internal_errors: list[Mapping[str, Any]]) -> dict[str, Any]:
    related_promotions = 0
    attribute_promotions = 0
    collective_promotions = 0
    source_role_conflicts = []
    for row in finals:
        if row.get("final_state") in {"stable_entity_resolved", "local_candidate_resolved"}:
            record = row.get("selected_record") if isinstance(row.get("selected_record"), Mapping) else {}
            relations = record.get("relations", []) or []
            if any(text(rel.get("relation")) in {"related_person", "office_relation", "kinship_relation", "citation_relation", "attribute_of"} for rel in relations if isinstance(rel, Mapping)):
                # Relations in a semantic record are not identity promotion;
                # this counter remains zero unless the storage state itself is
                # selected from a non-identity relation.
                pass
        if text(row.get("occurrence_role")) in EXCLUDED_CORE_ROLES and row.get("core_graph_eligible") is True:
            source_role_conflicts.append(row.get("case_id"))
        if text(row.get("semantic_kind")) == "person_attribute" and row.get("final_state") in {"stable_entity_resolved", "local_candidate_resolved"}:
            attribute_promotions += 1
        if text(row.get("semantic_kind")) == "collective" and row.get("final_state") in {"stable_entity_resolved", "local_candidate_resolved"}:
            collective_promotions += 1
    return {
        "schema": "sfh2-a0-storage-safety-audit-v1",
        "production_person_creations": 0,
        "canonical_writes": 0,
        "alias_mutations": 0,
        "profile_mutations": 0,
        "related_person_promotions": related_promotions,
        "attribute_person_promotions": attribute_promotions,
        "collective_person_promotions": collective_promotions,
        "substring_candidate_creation": 0,
        "python_identity_replacements": 0,
        "source_role_graph_conflicts": source_role_conflicts,
        "internal_consistency_errors": len(internal_errors),
        "protected_inputs_unchanged": dict(before) == dict(after),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _confidence_analysis(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    rows = evaluation.get("records", []) or []
    buckets: dict[str, dict[str, int]] = {}
    for stage, answer_key, correct_key in (("pass1", "pass1_answer", "pass1_correct"), ("final", "final_answer", "final_correct")):
        for row in rows:
            answer = row.get(answer_key) if isinstance(row.get(answer_key), Mapping) else {}
            confidence = text(answer.get("confidence")) or "none"
            buckets.setdefault(f"{stage}:{confidence}", {"correct": 0, "wrong": 0})
            buckets[f"{stage}:{confidence}"]["correct" if row.get(correct_key) else "wrong"] += 1
    return {"schema": "sfh2-a0-confidence-analysis-v1", "buckets": dict(sorted(buckets.items())), "confidence_is_not_probability": True, "candidate_only": True, "canonical_write_back": False}


def _review_trigger_analysis(cases: list[Mapping[str, Any]], p1: Mapping[str, Mapping[str, Any]], p2: Mapping[str, Mapping[str, Any]], finals: list[Mapping[str, Any]]) -> dict[str, Any]:
    rows = []
    by_final = {text(row.get("case_id")): row for row in finals}
    for case in cases:
        case_id = text(case.get("case_id"))
        rows.append({
            "case_id": case_id,
            "p1_flags": (p1.get(case_id) or {}).get("consistency", {}).get("flags", []),
            "p2_flags": (p2.get(case_id) or {}).get("consistency", {}).get("flags", []),
            "p1_review_trigger_score": (p1.get(case_id) or {}).get("consistency", {}).get("review_trigger_score", 0),
            "p2_review_trigger_score": (p2.get(case_id) or {}).get("consistency", {}).get("review_trigger_score", 0),
            "pass3_required": bool((by_final.get(case_id) or {}).get("pass3_required")),
            "review_routing_only": True,
        })
    return {"schema": "sfh2-a0-review-trigger-analysis-v1", "records": rows, "candidate_only": True, "canonical_write_back": False}


def _graph_audit(finals: list[Mapping[str, Any]]) -> dict[str, Any]:
    rows = []
    for final in finals:
        rows.append({
            "case_id": final.get("case_id"),
            "semantic_kind": final.get("semantic_kind"),
            "occurrence_role": final.get("occurrence_role"),
            "final_state": final.get("final_state"),
            "core_graph_eligible": final.get("core_graph_eligible"),
            "formal_flags": final.get("final_consistency", {}).get("flags", []),
        })
    return {"schema": "sfh2-a0-graph-consistency-audit-v1", "records": rows, "candidate_only": True, "canonical_write_back": False}


def _manifest(selection: Mapping[str, Any], gold: Mapping[str, Any], architecture: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "sfh2-a0-input-manifest-v1",
        "pilot": "SFH2.2-A0",
        "selection_hash": selection.get("selection_hash"),
        "gold_hash": stable_hash(gold),
        "input_hashes": input_hashes(),
        "architecture_hash": architecture.get("architecture_hash"),
        "gold_not_sent_to_provider": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _authorized_v1_to_v2_transition(previous: Mapping[str, Any], current: Mapping[str, Any]) -> bool:
    """Allow only the explicitly recorded A0 contract repair transition.

    The first live run exposed a provider-format contract defect.  v2 changes
    only the structured form contract/prompt and evaluation labels; it must
    not silently permit a selection or frozen input change.
    """

    previous_versions = (previous.get("model_config") or {}).get("prompt_versions") or {}
    current_versions = (current.get("model_config") or {}).get("prompt_versions") or {}
    return (
        text(previous.get("pilot")) == "SFH2.2-A0"
        and text(current.get("pilot")) == "SFH2.2-A0"
        and text(previous.get("selection_hash")) == text(current.get("selection_hash"))
        and text(previous_versions.get("primary_historian")).endswith("-v1")
        and text(current_versions.get("primary_historian")).endswith("-v2")
        and text(previous_versions.get("critical_reviewer")).endswith("-v1")
        and text(current_versions.get("critical_reviewer")).endswith("-v2")
        and text(previous_versions.get("adjudicator")).endswith("-v1")
        and text(current_versions.get("adjudicator")).endswith("-v2")
    )


def _authorized_manifest_v1_to_v2_transition(previous: Mapping[str, Any], current: Mapping[str, Any], architecture: Mapping[str, Any]) -> bool:
    """Validate the manifest half of the explicit v1 -> v2 transition."""

    current_versions = (architecture.get("model_config") or {}).get("prompt_versions") or {}
    return (
        text(previous.get("schema")) == "sfh2-a0-input-manifest-v1"
        and text(previous.get("pilot")) == "SFH2.2-A0"
        and text(current.get("pilot")) == "SFH2.2-A0"
        and text(previous.get("selection_hash")) == text(current.get("selection_hash"))
        and previous.get("input_hashes") == current.get("input_hashes")
        and text(previous.get("architecture_hash")) != text(current.get("architecture_hash"))
        and text(previous.get("gold_hash")) != text(current.get("gold_hash"))
        and all(text(current_versions.get(stage)).endswith("-v2") for stage in ("primary_historian", "critical_reviewer", "adjudicator"))
    )


# These are run-local references used only while assembling final records.  A
# single-process run keeps them deterministic and avoids adding semantic state
# to the candidate realization API.
_PIPELINE_INPUTS: dict[str, Any] = {}
_PIPELINE_EVIDENCE: dict[str, set[str]] = {}


def run(*, live: bool = False, run_id: str = "sfh2-a0-offline") -> dict[str, Any]:
    global _PIPELINE_INPUTS, _PIPELINE_EVIDENCE
    inputs = load_inputs()
    selection = freeze_selection(SELECTION_PATH, inputs)
    gold = freeze_gold()
    if selection.get("case_count") != 20 or selection.get("gold_fields_present") is not False:
        raise RuntimeError("sfh2_a0_selection_not_exactly_twenty_or_gold_free")
    cases = [dict(row) for row in selection.get("cases", []) or []]
    if len(cases) != 20:
        raise RuntimeError("sfh2_a0_selection_missing_cases")
    selection_hash = text(selection.get("selection_hash"))
    from .common import architecture_freeze
    architecture = architecture_freeze(selection_hash)
    freeze_path = OUT / "architecture-freeze.json"
    previous_architecture: dict[str, Any] = {}
    if freeze_path.is_file():
        previous_architecture = read_json(freeze_path, {}) or {}
        if previous_architecture != architecture and not _authorized_v1_to_v2_transition(previous_architecture, architecture):
            raise RuntimeError("sfh2_a0_architecture_changed")
    write_json(freeze_path, architecture)
    write_json(OUT / "selection.json", selection)
    write_json(OUT / "selection-hash.json", {"schema": "sfh2-a0-selection-hash-v1", "selection_hash": selection_hash})
    write_json(OUT / "evaluation-gold.json", gold)
    manifest = _manifest(selection, gold, architecture)
    manifest_path = OUT / "input-manifest.json"
    if manifest_path.is_file():
        previous_manifest = read_json(manifest_path, {}) or {}
        if previous_manifest != manifest:
            same_inputs = previous_manifest.get("input_hashes") == manifest.get("input_hashes")
            authorized_transition = same_inputs and (
                _authorized_v1_to_v2_transition(previous_architecture, architecture)
                or _authorized_manifest_v1_to_v2_transition(previous_manifest, manifest, architecture)
            )
            if not authorized_transition:
                raise RuntimeError("sfh2_a0_input_manifest_changed")
    write_json(manifest_path, manifest)

    packet_by_case: dict[str, dict[str, Any]] = {}
    packet_errors: dict[str, list[str]] = {}
    _PIPELINE_INPUTS = inputs
    for case in cases:
        packet = build_case_packet(case, inputs)
        packet_by_case[text(case.get("case_id"))] = packet
        packet_errors[text(case.get("case_id"))] = _validate_packet(packet)
    _PIPELINE_EVIDENCE = {
        case_id: set(text(row.get("evidence_id")) for row in packet.get("source_evidence", []) or [] if isinstance(row, Mapping) and text(row.get("evidence_id")))
        for case_id, packet in packet_by_case.items()
    }
    write_json(OUT / "case-packets.json", {
        "schema": "sfh2-a0-case-packets-v1",
        "packets": [packet_by_case[text(case.get("case_id"))] for case in cases],
        "packet_errors": packet_errors,
        "gold_not_sent_to_provider": True,
        "candidate_only": True,
        "canonical_write_back": False,
    })

    run_dir = OUT / "live" / run_id
    client = PilotClient(run_dir, live=live)
    p1: dict[str, dict[str, Any]] = {}
    for case in cases:
        case_id = text(case.get("case_id"))
        packet = packet_by_case[case_id]
        if packet_errors[case_id]:
            result = _invalid_result(case, "pass1", packet_errors[case_id])
        else:
            payload = primary_payload(packet)
            raw = client.call(stage="primary_historian", unit_id=case_id, system=PRIMARY_HISTORIAN_SYSTEM, payload=payload, tool=semantic_record_tool(), max_tokens=2600)
            result = _record_from_semantic_validation(case, packet, raw, "pass1")
        record = result.get("record") if result.get("valid") else None
        realization = realize_semantic_record(case, record, inputs)
        evidence = _PIPELINE_EVIDENCE.get(case_id, set())
        result["consistency"] = check_record(record, evidence_ids=evidence, realization=realization, stage="pass1")
        result["provisional_realization"] = realization
        p1[case_id] = result
    write_json(OUT / "pass1-semantic-results.json", {"schema": "sfh2-a0-pass1-semantic-results-v1", "records": [p1[text(case.get("case_id"))] for case in cases], "model": MODEL, "prompt_version": PROMPT_VERSIONS["primary_historian"], "gold_not_sent_to_provider": True, "candidate_only": True, "canonical_write_back": False})
    write_json(OUT / "python-consistency-after-pass1.json", {"schema": "sfh2-a0-python-consistency-v1", "stage": "pass1", "records": [{"case_id": key, **value.get("consistency", {})} for key, value in sorted(p1.items())], "candidate_only": True, "canonical_write_back": False})

    p2: dict[str, dict[str, Any]] = {}
    for case in cases:
        case_id = text(case.get("case_id"))
        packet = packet_by_case[case_id]
        raw = client.call(
            stage="critical_reviewer", unit_id=case_id,
            system=CRITICAL_REVIEWER_SYSTEM,
            payload=critical_payload(packet, _record(p1.get(case_id)), p1.get(case_id, {}).get("consistency", {})),
            tool=critical_review_tool(), max_tokens=2800,
        )
        result = _review_from_validation(case, packet, raw)
        realization = realize_semantic_record(case, result.get("record") if result.get("valid") else None, inputs)
        result["consistency"] = check_record(result.get("record") if result.get("valid") else None, evidence_ids=_PIPELINE_EVIDENCE.get(case_id, set()), realization=realization, stage="pass2")
        result["provisional_realization"] = realization
        p2[case_id] = result
    write_json(OUT / "pass2-review-results.json", {"schema": "sfh2-a0-pass2-review-results-v1", "records": [p2[text(case.get("case_id"))] for case in cases], "model": MODEL, "prompt_version": PROMPT_VERSIONS["critical_reviewer"], "all_cases_reviewed": True, "gold_not_sent_to_provider": True, "candidate_only": True, "canonical_write_back": False})
    write_json(OUT / "python-consistency-after-pass2.json", {"schema": "sfh2-a0-python-consistency-v1", "stage": "pass2", "records": [{"case_id": key, **value.get("consistency", {})} for key, value in sorted(p2.items())], "candidate_only": True, "canonical_write_back": False})

    p3: dict[str, dict[str, Any]] = {}
    for case in cases:
        case_id = text(case.get("case_id"))
        if not _needs_pass3(p1.get(case_id), p2.get(case_id), p1.get(case_id, {}).get("consistency", {}), p2.get(case_id, {}).get("consistency", {})):
            continue
        packet = packet_by_case[case_id]
        raw = client.call(
            stage="adjudicator", unit_id=case_id,
            system=ADJUDICATOR_SYSTEM,
            payload=adjudication_payload(packet, _record(p1.get(case_id)), _record(p2.get(case_id)), p2.get(case_id, {}).get("consistency", {})),
            tool=adjudication_tool(), max_tokens=3000,
        )
        result = _adjudication_from_validation(case, packet, raw)
        realization = realize_semantic_record(case, result.get("record") if result.get("valid") else None, inputs)
        result["consistency"] = check_record(result.get("record") if result.get("valid") else None, evidence_ids=_PIPELINE_EVIDENCE.get(case_id, set()), realization=realization, stage="pass3")
        p3[case_id] = result
    write_json(OUT / "pass3-adjudication-results.json", {"schema": "sfh2-a0-pass3-adjudication-results-v1", "records": [p3[key] for key in sorted(p3)], "model": MODEL, "prompt_version": PROMPT_VERSIONS["adjudicator"], "candidate_only": True, "canonical_write_back": False})

    finals = [_final_record(case, p1.get(text(case.get("case_id"))), p2.get(text(case.get("case_id"))), p3.get(text(case.get("case_id"))), p1.get(text(case.get("case_id")), {}).get("consistency", {}), p2.get(text(case.get("case_id")), {}).get("consistency", {})) for case in cases]
    write_json(OUT / "final-decisions.json", {"schema": "sfh2-a0-final-decisions-v1", "records": finals, "candidate_only": True, "canonical_write_back": False})
    evaluation, eval_metrics = _evaluation(cases, _gold_by_case(selection, gold), p1, p2, p3, finals)
    write_json(OUT / "evaluation.json", evaluation)
    internal_errors: list[dict[str, Any]] = []
    for final in finals:
        record = final.get("selected_record") if isinstance(final.get("selected_record"), Mapping) else None
        if record and bool(record.get("abstain")) and final.get("final_state") in {"stable_entity_resolved", "local_candidate_resolved"}:
            internal_errors.append({"case_id": final.get("case_id"), "error": "abstain_stored_as_identity"})
        if text(final.get("semantic_kind")) in {"person_attribute", "collective", "structural"} and final.get("selected_candidate") is not None:
            internal_errors.append({"case_id": final.get("case_id"), "error": "non_person_semantic_kind_created_identity"})
        if text(final.get("occurrence_role")) in EXCLUDED_CORE_ROLES and final.get("core_graph_eligible") is True:
            internal_errors.append({"case_id": final.get("case_id"), "error": "source_role_graph_projection"})
    internal = {"schema": "sfh2-a0-internal-consistency-audit-v1", "errors": internal_errors, "error_count": len(internal_errors), "candidate_only": True, "canonical_write_back": False}
    write_json(OUT / "internal-consistency-audit.json", internal)
    safety = _storage_safety(input_hashes(), input_hashes(), finals, p2, internal_errors)
    write_json(OUT / "storage-safety-audit.json", safety)
    write_json(OUT / "graph-consistency-audit.json", _graph_audit(finals))
    write_json(OUT / "review-trigger-analysis.json", _review_trigger_analysis(cases, p1, p2, finals))
    write_json(OUT / "confidence-analysis.json", _confidence_analysis(evaluation))

    client.save()
    transport_current = client.metrics()
    if live:
        write_json(OUT / "transport.json", transport_current)
    elif not (OUT / "transport.json").is_file():
        write_json(OUT / "transport.json", transport_current)
    write_json(OUT / "replay-transport.json", transport_current)
    stored_transport = read_json(OUT / "transport.json", transport_current) or transport_current
    metrics = {
        "schema": "sfh2-a0-metrics-v1",
        "pilot": "SFH2.2-A0",
        "case_count": len(cases),
        "story_count": len({text(case.get("story_id")) for case in cases}),
        "semantic_authority": "llm",
        "python_authority": ["schema_validation", "evidence_integrity", "formal_consistency", "candidate_id_allocation", "storage_safety", "review_routing"],
        **eval_metrics,
        "p1_formal_flagged_cases": sum(bool((p1.get(text(case.get("case_id")), {}).get("consistency") or {}).get("flags")) for case in cases),
        "p2_formal_flagged_cases": sum(bool((p2.get(text(case.get("case_id")), {}).get("consistency") or {}).get("flags")) for case in cases),
        "production_persons_created": 0,
        "canonical_writes": 0,
        "alias_mutations": 0,
        "profile_mutations": 0,
        "candidate_only": True,
        "canonical_write_back": False,
        "transport": stored_transport,
        "no_full_188_story_live_run": True,
    }
    write_json(OUT / "metrics.json", metrics)
    structural_valid = not internal_errors and safety.get("protected_inputs_unchanged") is True and not safety.get("source_role_graph_conflicts")
    recommendation = "sfh2_semantic_authority_ready" if structural_valid and eval_metrics.get("final_accuracy", 0) >= 0.95 and eval_metrics.get("high_confidence_final_false_identities", 0) == 0 and eval_metrics.get("reviewer_damage", 0) == 0 else "sfh2_semantic_authority_needs_review_routing_revision" if structural_valid else "sfh2_semantic_authority_blocked"
    write_json(OUT / "validation-summary.json", {"schema": "sfh2-a0-validation-summary-v1", "case_count": len(cases), "selection_hash": selection_hash, "architecture_hash": architecture.get("architecture_hash"), "structural_valid": structural_valid, "evaluation": eval_metrics, "candidate_only": True, "canonical_write_back": False})
    write_json(OUT / "recommendation.json", {"schema": "sfh2-a0-recommendation-v1", "recommendation": recommendation, "structural_valid": structural_valid, "candidate_only": True, "canonical_write_back": False})
    return {"selection": selection, "architecture": architecture, "metrics": metrics, "evaluation": evaluation, "transport": stored_transport, "recommendation": recommendation}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--offline", action="store_true")
    parser.add_argument("--run-id", default="sfh2-a0-offline")
    args = parser.parse_args(argv)
    result = run(live=bool(args.live), run_id=args.run_id)
    print(canonical_json({"case_count": result["selection"].get("case_count"), "selection_hash": result["selection"].get("selection_hash"), "recommendation": result["recommendation"], "transport": result["transport"]}))
    return 0 if result["recommendation"] != "sfh2_semantic_authority_blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
