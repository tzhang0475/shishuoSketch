"""Generate the offline SFH2.2-A2OS exact-occurrence audit."""

from __future__ import annotations

import copy
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from .common import (
    A2O_ROOT,
    A2OR_ROOT,
    A2OT_ROOT,
    A2OT_AUDIT_PATH,
    BASELINE_COMMIT,
    CASE_COUNT,
    CASE_GU,
    CASE_KANG,
    CASE_QI,
    CASE_WENDU,
    GOLD_PATH,
    IDENTITY_MANIFEST_PATH,
    MENTIONS_PATH,
    OUT,
    PACKETS_PATH,
    PROTECTED_IDENTITY_SHA256,
    PROTECTED_SC1_CURRENT_SHA256,
    PROTECTED_SC1_SHA256,
    ROOT,
    SELECTION_PATH,
    A2OR_EVALUATION_PATH,
    A2OR_RESULTS_PATH,
    A2O_EVALUATION_PATH,
    A2O_RESULTS_PATH,
    by_case,
    file_hash,
    interval_overlaps,
    load_bundle,
    occurrence_key,
    read_json,
    source_evidence,
    stable_hash,
    text,
    text_offsets,
    target_context,
    write_json,
)


# These are offline human-audit conclusions for the frozen pilot, not runtime
# semantic rules.  They are kept keyed by immutable case ID so the audit can
# report the known selection-intent defect without changing production logic.
ALIGNMENT_NOTES: dict[str, dict[str, Any]] = {
    CASE_GU: {
        "selection_intent_target_alignment": "misaligned",
        "gold_occurrence_alignment": "wrong_occurrence",
        "gold_taxonomy_status": "review_required",
        "root_cause": "target_gold_alignment_error",
        "review_basis": "The pinned mention is the opening occurrence at source_start=0, while the Gold semantic basis describes the later occurrence that introduces 顧曰.",
        "human_review_required": True,
    },
    CASE_QI: {
        "selection_intent_target_alignment": "aligned",
        "gold_occurrence_alignment": "correct",
        "gold_taxonomy_status": "review_required",
        "root_cause": "gold_taxonomy_review_required",
        "review_basis": "The pinned occurrence is exactly the entity inside the 史記 biographical sentence. The audit questions whether historical_exemplum belongs to this entity occurrence or to the invoked 管仲 example.",
        "human_review_required": True,
    },
}

REVIEW_CANDIDATES: dict[str, dict[str, Any]] = {
    CASE_GU: {
        "proposed_narrative_function": "participant",
        "proposed_legacy_occurrence_role": "scene_participant",
        "reason": "The selected opening 顧 is the participant reference in the narrator-framed event; the speaker interpretation belongs to the later 顧曰 occurrence.",
        "ontology_principle": "Evaluation labels must describe the exact pinned occurrence, not another same-surface occurrence in the source evidence.",
        "root_cause": "target_gold_alignment_error",
    },
    CASE_QI: {
        "proposed_narrative_function": "reference",
        "proposed_legacy_occurrence_role": "annotation_person",
        "reason": "齊桓公 is mentioned inside the 史記 material explaining 管仲; the occurrence itself is a reference to that ruler, while the historical exemplum in the main discourse is the invoked 管仲/管夷吾 comparison.",
        "ontology_principle": "An entity inside cited or explanatory historical content does not inherit historical_exemplum merely from the surrounding exemplum or source layer.",
        "root_cause": "gold_taxonomy_review_required",
    },
}

RESIDUAL_ERROR_CATEGORIES = {
    CASE_KANG: "reference_to_participant_overreach",
    CASE_WENDU: "reference_to_participant_overreach",
}


def _same_tuple_mentions(bundle: Mapping[str, Any], selection: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in bundle["mention_rows"]
        if text(row.get("story_id")) == text(selection.get("story_id"))
        and text(row.get("source_evidence_id")) == text(selection.get("source_evidence_id"))
        and text(row.get("surface")) == text(selection.get("surface"))
    ]


def _overlapping_mentions(bundle: Mapping[str, Any], selection: Mapping[str, Any], target: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = []
    for row in bundle["mention_rows"]:
        if text(row.get("story_id")) != text(selection.get("story_id")):
            continue
        if text(row.get("source_evidence_id")) != text(selection.get("source_evidence_id")):
            continue
        if text(row.get("mention_id")) == text(selection.get("mention_id")):
            continue
        if interval_overlaps(target.get("source_start"), target.get("source_end"), row.get("source_start"), row.get("source_end")):
            result.append({
                "mention_id": row.get("mention_id"),
                "surface": row.get("surface"),
                "source_start": row.get("source_start"),
                "source_end": row.get("source_end"),
                "reference_form": row.get("reference_form"),
                "entity_kind": row.get("entity_kind"),
            })
    return sorted(result, key=lambda row: (text(row.get("mention_id")), row.get("source_start", -1)))


def exact_occurrence_records(bundle: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for selection in bundle["selections"]:
        case_id = text(selection.get("case_id"))
        packet = bundle["packets"][case_id]
        target = packet.get("target") if isinstance(packet.get("target"), Mapping) else {}
        context = target_context(packet, selection)
        evidence = context["target_evidence"]
        mention = bundle["mentions"].get(text(selection.get("mention_id")))
        gold = bundle["gold"][case_id]
        a2o_result = bundle["a2o_results"][case_id]
        a2or_result = bundle["a2or_results"][case_id]
        a2or_evaluation = bundle["a2or_evaluation"][case_id]
        a2o_occurrence = a2o_result.get("occurrence_result") if isinstance(a2o_result.get("occurrence_result"), Mapping) else {}
        a2or_occurrence = a2or_result.get("occurrence_result") if isinstance(a2or_result.get("occurrence_result"), Mapping) else {}
        same_tuple = _same_tuple_mentions(bundle, selection)
        sorted_same_tuple = sorted(same_tuple, key=lambda row: (text(row.get("mention_id")), row.get("source_start", -1)))
        target_surface = text(target.get("surface"))
        source_text = context["source_text"]
        key = occurrence_key(selection, target)
        target_fields_match = (
            text(selection.get("mention_id")) == text(target.get("mention_id"))
            if target.get("mention_id") is not None
            else True
        )
        mention_matches = isinstance(mention, Mapping) and all([
            text(mention.get("story_id")) == text(selection.get("story_id")),
            text(mention.get("surface")) == target_surface,
            text(mention.get("source_evidence_id")) == text(target.get("source_evidence_id")),
            mention.get("source_start") == target.get("source_start"),
            mention.get("source_end") == target.get("source_end"),
        ])
        structural_valid = all([
            context["offsets_valid"],
            context["matched_source_text"] == target_surface,
            text(selection.get("surface")) == target_surface,
            text(selection.get("source_evidence_id")) == text(target.get("source_evidence_id")),
            target_fields_match,
            mention_matches,
            text(gold.get("story_id")) == text(selection.get("story_id")),
            text(gold.get("surface")) == target_surface,
            text(gold.get("source_evidence_id")) == text(target.get("source_evidence_id")),
            bool(text(gold.get("semantic_basis"))),
        ])
        audit = ALIGNMENT_NOTES.get(case_id, {
            "selection_intent_target_alignment": "aligned",
            "gold_occurrence_alignment": "correct",
            "gold_taxonomy_status": "consistent",
            "root_cause": None,
            "review_basis": "The exact case, mention, evidence, surface, and offsets align; no separate occurrence is identified by the frozen Gold basis in this audit.",
            "human_review_required": False,
        })
        records.append({
            "case_id": case_id,
            "cohort": selection.get("cohort"),
            "story_id": selection.get("story_id"),
            "surface": selection.get("surface"),
            "exact_occurrence_key": key,
            "exact_source_context": {
                "source_evidence_id": evidence.get("evidence_id"),
                "source_layer": evidence.get("source_layer"),
                "source_ref": evidence.get("source_ref"),
                "text": source_text,
                "matched_target": context["matched_source_text"],
                "context_window": context["context_window"],
            },
            "mention_record": copy.deepcopy(mention) if isinstance(mention, Mapping) else None,
            "selection_record": copy.deepcopy(selection),
            "gold_record": copy.deepcopy(gold),
            "gold_semantic_basis_is_evidence_only": True,
            "gold_basis_used_for_target_resolution": False,
            "a2o_interpretation": copy.deepcopy(a2o_occurrence),
            "a2or_interpretation": copy.deepcopy(a2or_occurrence),
            "a2or_evaluation": {
                "valid": a2or_evaluation.get("valid"),
                "confidence": a2or_evaluation.get("confidence"),
                "predicted_narrative_function": a2or_evaluation.get("predicted_narrative_function"),
                "predicted_legacy_occurrence_role": a2or_evaluation.get("predicted_legacy_occurrence_role"),
                "expected_narrative_function": a2or_evaluation.get("expected_narrative_function"),
                "expected_legacy_occurrence_role": a2or_evaluation.get("expected_legacy_occurrence_role"),
                "narrative_function_correct": a2or_evaluation.get("narrative_function_correct"),
                "legacy_occurrence_role_correct": a2or_evaluation.get("legacy_occurrence_role_correct"),
                "reason_summary": a2or_evaluation.get("reason_summary"),
            },
            "validated_mention_tuple": {
                "match_count": len(same_tuple),
                "matching_mention_ids": [row.get("mention_id") for row in sorted_same_tuple],
                "selected_order": next((index + 1 for index, row in enumerate(sorted_same_tuple) if text(row.get("mention_id")) == text(selection.get("mention_id"))), None),
            },
            "text_surface_occurrences": text_offsets(source_text, target_surface),
            "overlapping_validated_mentions": _overlapping_mentions(bundle, selection, target),
            "integrity": {
                "target_span_exists": context["offsets_valid"],
                "target_matches_source_text": context["matched_source_text"] == target_surface,
                "mention_id_matches_exact_span": mention_matches,
                "selection_fields_match_target": context["selection_surface_matches_target"] and context["selection_evidence_matches_target"] and target_fields_match,
                "gold_case_matches_target": text(gold.get("story_id")) == text(selection.get("story_id")) and text(gold.get("surface")) == target_surface and text(gold.get("source_evidence_id")) == text(target.get("source_evidence_id")),
                "structural_valid": structural_valid,
            },
            "selection_intent_target_alignment": audit["selection_intent_target_alignment"],
            "gold_occurrence_alignment": audit["gold_occurrence_alignment"],
            "gold_taxonomy_status": audit["gold_taxonomy_status"],
            "alignment_root_cause": audit["root_cause"],
            "alignment_review_basis": audit["review_basis"],
            "human_review_required": audit["human_review_required"],
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return records


def selection_intent_document(records: list[Mapping[str, Any]], bundle: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "sfh2-a2os-selection-intent-alignment-v1",
        "historical_selector": "scripts/sfh2_a0r_l/selection.py",
        "historical_matching_fields": ["story_id", "surface", "source_evidence_id"],
        "historical_sort_fields": ["mention_id", "source_start"],
        "historical_mention_id_pinned": False,
        "prospective_rule": "Pin every semantic challenge and Gold case by mention_id plus source_evidence_id/source_start/source_end/surface; reject ambiguous surface-only resolution.",
        "prospective_rule_is_selection_integrity_only": True,
        "selection_hash": bundle["selection_document"].get("selection_hash"),
        "case_count": len(records),
        "records": [
            {
                "case_id": row["case_id"],
                "exact_occurrence_key": row["exact_occurrence_key"],
                "selection_reason": row["selection_record"].get("selection_reason"),
                "selection_intent_target_alignment": row["selection_intent_target_alignment"],
                "gold_occurrence_alignment": row["gold_occurrence_alignment"],
                "gold_basis_used_for_target_resolution": row["gold_basis_used_for_target_resolution"],
                "alignment_review_basis": row["alignment_review_basis"],
            }
            for row in records
        ],
        "counts": dict(Counter(row["selection_intent_target_alignment"] for row in records)),
        "misaligned_case_ids": [row["case_id"] for row in records if row["selection_intent_target_alignment"] == "misaligned"],
        "ambiguous_case_ids": [row["case_id"] for row in records if row["selection_intent_target_alignment"] == "ambiguous"],
        "candidate_only": True,
        "canonical_write_back": False,
    }


def duplicate_surface_document(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    exact_groups = []
    collision_cases = []
    for row in records:
        tuple_info = row["validated_mention_tuple"]
        textual = row["text_surface_occurrences"]
        overlaps = row["overlapping_validated_mentions"]
        if tuple_info["match_count"] > 1:
            exact_groups.append({
                "tuple": {
                    "story_id": row["story_id"],
                    "source_evidence_id": row["exact_occurrence_key"]["source_evidence_id"],
                    "surface": row["surface"],
                },
                "case_ids": [row["case_id"]],
                "mention_ids": tuple_info["matching_mention_ids"],
                "selected_mention_id": row["exact_occurrence_key"]["mention_id"],
                "selection_order": tuple_info["selected_order"],
            })
        if len(textual) > 1 or overlaps:
            collision_cases.append({
                "case_id": row["case_id"],
                "story_id": row["story_id"],
                "surface": row["surface"],
                "source_evidence_id": row["exact_occurrence_key"]["source_evidence_id"],
                "selected_mention_id": row["exact_occurrence_key"]["mention_id"],
                "selected_offsets": {
                    "source_start": row["exact_occurrence_key"]["source_start"],
                    "source_end": row["exact_occurrence_key"]["source_end"],
                },
                "validated_same_tuple_mentions": tuple_info["matching_mention_ids"],
                "validated_same_tuple_count": tuple_info["match_count"],
                "selection_order": tuple_info["selected_order"],
                "selection_reason": row["selection_record"].get("selection_reason"),
                "text_surface_offsets": textual,
                "overlapping_validated_mentions": overlaps,
                "selection_intent_target_alignment": row["selection_intent_target_alignment"],
                "selection_reason_matches_selected_occurrence": row["selection_intent_target_alignment"] == "aligned",
            })
    return {
        "schema": "sfh2-a2os-duplicate-surface-audit-v1",
        "case_count": len(records),
        "tuple_definition": ["story_id", "source_evidence_id", "surface"],
        "exact_validated_tuple_duplicate_group_count": len(exact_groups),
        "exact_validated_tuple_duplicate_groups": exact_groups,
        "textually_repeated_or_overlapping_case_count": len(collision_cases),
        "textually_repeated_or_overlapping_cases": collision_cases,
        "interpretation": "A repeated source-text surface or nested validated span is a collision signal, not an identity or semantic decision. Exact mention_id and offsets remain the evaluation key.",
        "candidate_only": True,
        "canonical_write_back": False,
    }


def gold_alignment_document(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "sfh2-a2os-gold-alignment-audit-v1",
        "case_count": len(records),
        "records": [
            {
                "case_id": row["case_id"],
                "exact_occurrence_key": row["exact_occurrence_key"],
                "gold_occurrence_alignment": row["gold_occurrence_alignment"],
                "gold_taxonomy_status": row["gold_taxonomy_status"],
                "current_gold": copy.deepcopy(row["gold_record"]),
                "semantic_basis": row["gold_record"].get("semantic_basis"),
                "alignment_review_basis": row["alignment_review_basis"],
                "review_required": row["human_review_required"],
                "gold_basis_used_for_target_resolution": row["gold_basis_used_for_target_resolution"],
            }
            for row in records
        ],
        "counts": {
            "gold_occurrence_alignment": dict(Counter(row["gold_occurrence_alignment"] for row in records)),
            "gold_taxonomy_status": dict(Counter(row["gold_taxonomy_status"] for row in records)),
        },
        "gold_mutated": False,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def gold_review_candidates(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    by_id = {row["case_id"]: row for row in records}
    output = []
    for case_id, proposal in REVIEW_CANDIDATES.items():
        row = by_id[case_id]
        gold = row["gold_record"]
        output.append({
            "case_id": case_id,
            "story_id": row["story_id"],
            "surface": row["surface"],
            "exact_occurrence_key": row["exact_occurrence_key"],
            "exact_source_context": row["exact_source_context"],
            "previous_gold": {
                "narrative_function": gold.get("expected_narrative_function"),
                "legacy_occurrence_role": gold.get("expected_legacy_occurrence_role"),
                "semantic_basis": gold.get("semantic_basis"),
            },
            "proposed_gold": {
                "narrative_function": proposal["proposed_narrative_function"],
                "legacy_occurrence_role": proposal["proposed_legacy_occurrence_role"],
            },
            "reason": proposal["reason"],
            "ontology_principle": proposal["ontology_principle"],
            "root_cause": proposal["root_cause"],
            "confidence": "high",
            "human_review_required": True,
            "gold_mutation_performed": False,
        })
    return {
        "schema": "sfh2-a2os-gold-review-candidates-v1",
        "candidate_count": len(output),
        "records": output,
        "active_gold_unchanged": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def residual_model_errors(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    wrong = [row for row in records if row["a2or_evaluation"].get("narrative_function_correct") is False]
    residual = []
    reclassified = []
    for row in wrong:
        if row["case_id"] in REVIEW_CANDIDATES:
            reclassified.append({
                "case_id": row["case_id"],
                "surface": row["surface"],
                "classification": "alignment_or_gold_taxonomy_candidate",
                "root_cause": row["alignment_root_cause"],
                "not_counted_as_genuine_model_error": True,
            })
            continue
        residual.append({
            "case_id": row["case_id"],
            "story_id": row["story_id"],
            "surface": row["surface"],
            "exact_occurrence_key": row["exact_occurrence_key"],
            "gold_occurrence_alignment": row["gold_occurrence_alignment"],
            "gold_taxonomy_status": row["gold_taxonomy_status"],
            "gold": {
                "narrative_function": row["gold_record"].get("expected_narrative_function"),
                "legacy_occurrence_role": row["gold_record"].get("expected_legacy_occurrence_role"),
            },
            "a2or": {
                "narrative_function": row["a2or_evaluation"].get("predicted_narrative_function"),
                "legacy_occurrence_role": row["a2or_evaluation"].get("predicted_legacy_occurrence_role"),
                "confidence": row["a2or_evaluation"].get("confidence"),
                "reason_summary": row["a2or_evaluation"].get("reason_summary"),
            },
            "error_category": RESIDUAL_ERROR_CATEGORIES.get(row["case_id"], "genuine_model_mismatch_pending_audit"),
            "interpretation": "The exact target and Gold basis align; the A2OR function mismatch remains a model error candidate after alignment audit.",
        })
    return {
        "schema": "sfh2-a2os-residual-model-errors-v1",
        "current_a2or_wrong_count": len(wrong),
        "alignment_or_gold_reclassified_count": len(reclassified),
        "remaining_genuine_model_error_count": len(residual),
        "alignment_or_gold_reclassified": reclassified,
        "records": residual,
        "known_residual_cases": [CASE_KANG, CASE_WENDU],
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _scenario_score(records: list[Mapping[str, Any]], overrides: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    scored = []
    for row in records:
        gold = row["gold_record"]
        override = overrides.get(row["case_id"], {})
        expected_function = override.get("narrative_function", gold.get("expected_narrative_function"))
        expected_role = override.get("legacy_occurrence_role", gold.get("expected_legacy_occurrence_role"))
        predicted_function = row["a2or_evaluation"].get("predicted_narrative_function")
        predicted_role = row["a2or_evaluation"].get("predicted_legacy_occurrence_role")
        scored.append({
            "case_id": row["case_id"],
            "narrative_function_correct": predicted_function == expected_function,
            "legacy_occurrence_role_correct": predicted_role == expected_role,
        })
    def cohort(name: str | None) -> dict[str, Any]:
        members = [item for item, row in zip(scored, records) if name is None or row.get("cohort") == name]
        return {
            "correct": sum(bool(item["narrative_function_correct"]) for item in members),
            "evaluable": len(members),
            "accuracy": round(sum(bool(item["narrative_function_correct"]) for item in members) / len(members), 4) if members else None,
            "legacy_role_correct": sum(bool(item["legacy_occurrence_role_correct"]) for item in members),
            "legacy_role_accuracy": round(sum(bool(item["legacy_occurrence_role_correct"]) for item in members) / len(members), 4) if members else None,
        }
    return {
        "all": cohort(None),
        "reviewed_role": cohort("reviewed_role"),
        "challenge": cohort("challenge"),
        "correct_case_ids": [item["case_id"] for item in scored if item["narrative_function_correct"]],
        "incorrect_case_ids": [item["case_id"] for item in scored if not item["narrative_function_correct"]],
        "overrides": copy.deepcopy(dict(overrides)),
    }


def counterfactual_document(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    scenarios = [{"name": "current_a2or", "overrides": {}}]
    for case_id, proposal in REVIEW_CANDIDATES.items():
        scenarios.append({
            "name": f"candidate_{case_id}",
            "overrides": {
                case_id: {
                    "narrative_function": proposal["proposed_narrative_function"],
                    "legacy_occurrence_role": proposal["proposed_legacy_occurrence_role"],
                }
            },
        })
    scenarios.append({
        "name": "all_high_confidence_candidates",
        "overrides": {
            case_id: {
                "narrative_function": proposal["proposed_narrative_function"],
                "legacy_occurrence_role": proposal["proposed_legacy_occurrence_role"],
            }
            for case_id, proposal in REVIEW_CANDIDATES.items()
        },
    })
    evaluated = []
    for scenario in scenarios:
        evaluated.append({"name": scenario["name"], "score": _scenario_score(records, scenario["overrides"])})
    current = evaluated[0]["score"]
    corrected = evaluated[-1]["score"]
    return {
        "schema": "sfh2-a2os-counterfactual-evaluation-v1",
        "historical_a2or_outputs_unchanged": True,
        "current_a2or": current,
        "scenarios": evaluated,
        "current_score": current,
        "after_all_high_confidence_candidates": corrected,
        "current_vs_semantically_corrected_interpretation": {
            "current_wrong_case_ids": current["incorrect_case_ids"],
            "remaining_genuine_model_error_case_ids": [CASE_KANG, CASE_WENDU],
            "alignment_or_gold_cases_removed_from_model_error_count": [CASE_GU, CASE_QI],
            "interpretation": "Counterfactual scores alter evaluation labels only; they do not modify active Gold or semantic outputs.",
        },
        "candidate_only": True,
        "canonical_write_back": False,
    }


def metrics_document(records: list[Mapping[str, Any]], duplicate: Mapping[str, Any], residual: Mapping[str, Any], counterfactual: Mapping[str, Any]) -> dict[str, Any]:
    selection_counts = dict(Counter(row["selection_intent_target_alignment"] for row in records))
    alignment_counts = dict(Counter(row["gold_occurrence_alignment"] for row in records))
    taxonomy_counts = dict(Counter(row["gold_taxonomy_status"] for row in records))
    current = counterfactual["current_score"]["all"]
    corrected = counterfactual["after_all_high_confidence_candidates"]["all"]
    return {
        "schema": "sfh2-a2os-metrics-v1",
        "case_count": len(records),
        "exact_occurrence_spans_valid": sum(bool(row["integrity"]["structural_valid"]) for row in records),
        "selection_intent_alignment": selection_counts,
        "gold_occurrence_alignment": alignment_counts,
        "gold_taxonomy_status": taxonomy_counts,
        "gold_review_candidate_count": len(REVIEW_CANDIDATES),
        "exact_validated_tuple_duplicate_groups": duplicate["exact_validated_tuple_duplicate_group_count"],
        "textually_repeated_or_overlapping_cases": duplicate["textually_repeated_or_overlapping_case_count"],
        "current_a2or": {
            "correct": current["correct"],
            "evaluable": current["evaluable"],
            "accuracy": current["accuracy"],
            "challenge": counterfactual["current_score"]["challenge"],
            "reviewed_role": counterfactual["current_score"]["reviewed_role"],
        },
        "counterfactual_after_all_candidates": {
            "correct": corrected["correct"],
            "evaluable": corrected["evaluable"],
            "accuracy": corrected["accuracy"],
            "challenge": counterfactual["after_all_high_confidence_candidates"]["challenge"],
            "reviewed_role": counterfactual["after_all_high_confidence_candidates"]["reviewed_role"],
        },
        "remaining_genuine_model_errors": residual["remaining_genuine_model_error_count"],
        "provider_calls": 0,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def recommendation_document(metrics: Mapping[str, Any], residual: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "sfh2-a2os-recommendation-v1",
        "recommendation": "sfh2_occurrence_gold_alignment_review_required",
        "qualified": False,
        "next_stage": "Human review of Gold/target candidates, then A2OR rerun only after approved Gold/selection correction.",
        "model_quality_diagnosis": {
            "prior_a2or_model_quality_insufficient": True,
            "survives_without_reclassification": False,
            "reason": "Two of four apparent A2OR mismatches are evaluation-target/taxonomy candidates; two exact-aligned mismatches remain genuine model-error candidates.",
            "remaining_genuine_model_error_count": residual["remaining_genuine_model_error_count"],
        },
        "gate_status": {
            "provider_calls_zero": True,
            "exact_occurrence_spans_valid": metrics["exact_occurrence_spans_valid"] == CASE_COUNT,
            "active_gold_unchanged": True,
            "historical_outputs_unchanged": True,
        },
        "candidate_only": True,
        "canonical_write_back": False,
    }


def architecture_document(bundle: Mapping[str, Any], records: list[Mapping[str, Any]]) -> dict[str, Any]:
    paths = [SELECTION_PATH, PACKETS_PATH, A2O_RESULTS_PATH, A2O_EVALUATION_PATH, A2OT_AUDIT_PATH, A2OR_RESULTS_PATH, A2OR_EVALUATION_PATH, GOLD_PATH, MENTIONS_PATH]
    return {
        "schema": "sfh2-a2os-architecture-v1",
        "stage": "SFH2.2-A2OS",
        "baseline_commit": BASELINE_COMMIT,
        "offline": True,
        "provider_calls": 0,
        "purpose": "exact occurrence identity, selection-intent, and Gold alignment audit",
        "case_count": len(records),
        "frozen_selection_hash": bundle["selection_document"].get("selection_hash"),
        "input_hashes": {str(path.relative_to(ROOT)): file_hash(path) for path in paths if path.is_file()},
        "historical_inputs_immutable": True,
        "gold_mutated": False,
        "gold_loaded_for_audit_only": True,
        "gold_basis_used_for_target_resolution": False,
        "python_semantic_inference": False,
        "prospective_selection_rule": "mention_id plus exact source evidence and offsets",
        "protected_hashes": {
            "data/derived/sc1-site.json": PROTECTED_SC1_SHA256,
            "data/derived/sc1-current-site.json": PROTECTED_SC1_CURRENT_SHA256,
            "data/frozen/sfh2/identity-v1/manifest.json": PROTECTED_IDENTITY_SHA256,
        },
        "candidate_only": True,
        "canonical_write_back": False,
    }


def run(output: Path = OUT) -> dict[str, Any]:
    bundle = load_bundle()
    records = exact_occurrence_records(bundle)
    duplicate = duplicate_surface_document(records)
    alignment = selection_intent_document(records, bundle)
    gold_alignment = gold_alignment_document(records)
    candidates = gold_review_candidates(records)
    residual = residual_model_errors(records)
    counterfactual = counterfactual_document(records)
    metrics = metrics_document(records, duplicate, residual, counterfactual)
    recommendation = recommendation_document(metrics, residual)
    documents = {
        "architecture.json": architecture_document(bundle, records),
        "exact-occurrence-audit.json": {
            "schema": "sfh2-a2os-exact-occurrence-audit-v1",
            "case_count": len(records),
            "records": records,
            "all_structurally_valid": all(row["integrity"]["structural_valid"] for row in records),
            "candidate_only": True,
            "canonical_write_back": False,
        },
        "duplicate-surface-audit.json": duplicate,
        "selection-intent-alignment.json": alignment,
        "gold-alignment-audit.json": gold_alignment,
        "gold-review-candidates.json": candidates,
        "residual-model-errors.json": residual,
        "counterfactual-evaluation.json": counterfactual,
        "metrics.json": metrics,
        "recommendation.json": recommendation,
    }
    for name, document in documents.items():
        write_json(output / name, document)
    return documents
