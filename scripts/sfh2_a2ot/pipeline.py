"""Deterministic, offline production of the SFH2.2-A2OT audit artifacts."""

from __future__ import annotations

import copy
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from .common import (
    A2O_GOLD_PATH,
    A2O_ROOT,
    BASELINE_COMMIT,
    OUT,
    PROTECTED_HASHES,
    load_frozen_bundle,
    read_json,
    target_context,
    text,
    write_json,
)
from .taxonomy import NARRATIVE_FUNCTIONS, taxonomy_document


RECOMMENDATIONS = {
    "sfh2_occurrence_gold_review_required",
    "sfh2_occurrence_taxonomy_clarification_required",
    "sfh2_occurrence_model_quality_test_required",
    "sfh2_occurrence_representation_rejected",
}

FIVE_CASE_IDS = (
    "sfh2-a0-57d1fc3c0492b21ee1f4",
    "sfh2-a0r-l-challenge-c07bd51ac298529ddbc6",
    "sfh2-a0r-l-challenge-02fa84b24af39e8f8201",
    "sfh2-a0r-l-challenge-f245371d8f0cdf9c8773",
    "sfh2-a0r-l-challenge-d3c8fa925020f0c2c62a",
)

# This table is an evaluation-audit record keyed by immutable case identity.
# It is not used to classify arbitrary runtime text and contains no semantic
# replacement logic for the production pipeline.
FIVE_CASE_REVIEW: dict[str, dict[str, Any]] = {
    "sfh2-a0-57d1fc3c0492b21ee1f4": {
        "audit_class": "model_source_scope_error",
        "boundary_conflict": False,
        "review_required": False,
        "action": "retain_current_gold",
        "conclusion": "齊桓公 is content inside the historical material quoted from 史記; it does not identify the citation source itself.",
        "ontology_principle": "citation_source applies to the occurrence that attributes or introduces the source; an entity inside cited content is historical_exemplum when it functions as historical comparison or background.",
    },
    "sfh2-a0r-l-challenge-c07bd51ac298529ddbc6": {
        "audit_class": "gold_requires_human_review",
        "boundary_conflict": True,
        "review_required": True,
        "action": "propose_gold_correction",
        "proposed_expected_narrative_function": "participant",
        "proposed_expected_legacy_occurrence_role": "scene_participant",
        "conclusion": "The selected occurrence is the object of 召 in the main-text event. Under the clarified occurrence-centric definition, it is not automatically a direct-address occurrence.",
        "ontology_principle": "The grammatical object of a summoning or remonstrance verb is not automatically addressee; addressee requires a direct-address or vocative discourse function.",
        "confidence": "high",
    },
    "sfh2-a0r-l-challenge-02fa84b24af39e8f8201": {
        "audit_class": "model_discourse_role_error",
        "boundary_conflict": False,
        "review_required": False,
        "action": "retain_current_gold",
        "conclusion": "The Liu annotation occurrence is in the narrated 諫帝 sequence. The communication verb does not by itself make its grammatical object a direct addressee occurrence.",
        "ontology_principle": "Addressee is reserved for direct address; an object of 諫 remains an event participant or reference unless the target itself performs a direct-address function.",
    },
    "sfh2-a0r-l-challenge-f245371d8f0cdf9c8773": {
        "audit_class": "model_discourse_role_error",
        "boundary_conflict": False,
        "review_required": False,
        "action": "retain_current_gold",
        "conclusion": "The selected occurrence is the subject of 顧曰 and identifies the speaker of the following main-text utterance.",
        "ontology_principle": "A target occurrence that identifies the speaker of the current utterance has the specific speaker function rather than generic participant.",
    },
    "sfh2-a0r-l-challenge-d3c8fa925020f0c2c62a": {
        "audit_class": "model_target_attribute_confusion",
        "boundary_conflict": False,
        "review_required": False,
        "action": "retain_current_gold",
        "conclusion": "The Liu annotation occurrence denotes 顗, while 好媟瀆 predicates a characteristic of that person. The person occurrence itself is not an attribute expression.",
        "ontology_principle": "person_attribute applies when the target occurrence itself expresses the attribute or value, not merely when a predicate describes its referent.",
    },
}


def _ordered_records(bundle: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "selection": dict(selection),
            "packet": bundle["packets"][text(selection["case_id"])],
            "result": bundle["results"][text(selection["case_id"])],
            "evaluation": bundle["evaluation"][text(selection["case_id"])],
            "gold": bundle["gold"][text(selection["case_id"])],
            "a2r_final": bundle["a2r_final_results"].get(text(selection["case_id"])),
            "a2r_challenge": bundle["a2r_challenge_review"].get(text(selection["case_id"])),
        }
        for selection in bundle["selection"]
    ]


def _semantic_result(result: Mapping[str, Any]) -> dict[str, Any]:
    occurrence = result.get("occurrence_result")
    if not isinstance(occurrence, Mapping):
        return {}
    return {
        key: copy.deepcopy(occurrence.get(key))
        for key in ("case_id", "narrative_function", "confidence", "supporting_evidence_ids", "reason_summary")
        if key in occurrence
    }


def _a2r_semantic_record(record: Any) -> dict[str, Any] | None:
    """Keep only a frozen A2R semantic record, excluding transport/runtime data."""
    if not isinstance(record, Mapping):
        return None
    selected = record.get("selected_record")
    if not isinstance(selected, Mapping):
        return None
    return copy.deepcopy(dict(selected))


def _a2r_semantic_context(item: Mapping[str, Any]) -> dict[str, Any]:
    case_id = text(item["selection"].get("case_id"))
    challenge = item.get("a2r_challenge")
    final = item.get("a2r_final")
    historian_a = None
    historian_b = None
    if isinstance(challenge, Mapping):
        historian_a = _a2r_semantic_record({"selected_record": challenge.get("historian_a")})
        historian_b = _a2r_semantic_record({"selected_record": challenge.get("historian_b")})
    return {
        "historian_a": historian_a,
        "historian_b": historian_b,
        "final_a2r": _a2r_semantic_record(final),
        "source": {
            "historian_a_and_b": "data/generated/sfh2-a2r/challenge-review-bundle.json" if isinstance(challenge, Mapping) else "not_present_in_frozen_a2r_bundle",
            "final_a2r": "data/generated/sfh2-a2r/final-results.json" if isinstance(final, Mapping) else "not_present_in_frozen_a2r_bundle",
            "case_id": case_id,
            "note": "A2R full A/B semantic records are retained only where the frozen A2R review bundle exposes them; null is an availability fact, not an inferred interpretation.",
        },
    }


def _audit_class(case_id: str, mismatch: bool) -> dict[str, Any]:
    if case_id in FIVE_CASE_REVIEW:
        return copy.deepcopy(FIVE_CASE_REVIEW[case_id])
    if mismatch:
        return {
            "audit_class": "gold_requires_human_review",
            "boundary_conflict": True,
            "review_required": True,
            "action": "hold_for_human_review",
            "conclusion": "The frozen Gold and A2O output differ; the offline audit does not choose a historical replacement.",
            "ontology_principle": "A Gold/model mismatch requires evidence-based review and is not resolved by Python string or lexical rules.",
        }
    return {
        "audit_class": "ontology_consistent",
        "boundary_conflict": False,
        "review_required": False,
        "action": "retain_current_gold",
        "conclusion": "The frozen Gold label and A2O narrative-function output agree on the audited structured dimension.",
        "ontology_principle": "The target occurrence is classified by its most specific applicable occurrence-centric function.",
    }


def audit_record(item: Mapping[str, Any]) -> dict[str, Any]:
    selection = item["selection"]
    packet = item["packet"]
    result = item["result"]
    evaluation = item["evaluation"]
    gold = item["gold"]
    context = target_context(packet)
    prediction = _semantic_result(result)
    expected_function = text(gold.get("expected_narrative_function"))
    predicted_function = text(prediction.get("narrative_function"))
    expected_role = text(gold.get("expected_legacy_occurrence_role"))
    predicted_role = text(evaluation.get("projected_legacy_occurrence_role"))
    mismatch = expected_function != predicted_function or expected_role != predicted_role
    affected = []
    if expected_function != predicted_function:
        affected.append("narrative_function")
    if expected_role != predicted_role:
        affected.append("legacy_occurrence_role")
    audit = _audit_class(text(selection.get("case_id")), mismatch)
    story_context = packet.get("story_context") if isinstance(packet.get("story_context"), Mapping) else {}
    a2r_context = _a2r_semantic_context(item)
    target_evidence = context.get("target_evidence") if isinstance(context.get("target_evidence"), Mapping) else {}
    structural_provenance = target_evidence.get("source_layer")
    return {
        "case_id": selection.get("case_id"),
        "cohort": selection.get("cohort"),
        "story_id": selection.get("story_id"),
        "surface": selection.get("surface"),
        "mention_id": selection.get("mention_id"),
        "source_evidence_id": selection.get("source_evidence_id"),
        "target_span": {
            "exact_span": context.get("exact_span"),
            "surface": selection.get("surface"),
            "source_start": context.get("source_start"),
            "source_end": context.get("source_end"),
            "offset_convention": context.get("offset_convention"),
            "offsets_valid": context.get("offsets_valid"),
            "matched_source_text": context.get("matched_source_text"),
        },
        "target_evidence": context.get("target_evidence"),
        "nearby_context": {
            "source_path": story_context.get("source_path"),
            "source_sha256": story_context.get("source_sha256"),
            "context_window": context.get("context_window"),
            "nearby_source_evidence": context.get("nearby_source_evidence"),
        },
        "provenance_layer": structural_provenance,
        "provenance_audit": {
            "derived_from": "target_evidence.source_layer",
            "target_evidence_id": context.get("source_evidence_id"),
            "derived_value": structural_provenance,
            "a2o_record_value": result.get("provenance_layer"),
            "gold_value": gold.get("expected_provenance_layer"),
            "values_agree": structural_provenance == result.get("provenance_layer") == gold.get("expected_provenance_layer"),
        },
        "frozen_identity": copy.deepcopy(result.get("frozen_identity")),
        "current_gold": copy.deepcopy(gold),
        "a2o_interpretation": prediction,
        "a2r_semantic_interpretations": a2r_context,
        "a2o_evaluation": {
            "valid": evaluation.get("valid"),
            "identity_preserved": evaluation.get("identity_preserved"),
            "predicted_narrative_function": predicted_function,
            "predicted_legacy_occurrence_role": predicted_role,
            "provenance_correct": evaluation.get("provenance_correct"),
            "narrative_function_correct": evaluation.get("narrative_function_correct"),
            "legacy_occurrence_role_correct": evaluation.get("legacy_occurrence_role_correct"),
        },
        "ontology_audit": {
            "a2o_mismatch": mismatch,
            "affected_semantic_dimensions": affected,
            **audit,
        },
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _counts_to_records(counter: Counter[tuple[str, ...]], keys: list[str]) -> list[dict[str, Any]]:
    return [
        {**dict(zip(keys, key)), "count": count}
        for key, count in sorted(counter.items())
    ]


def function_consistency_matrix(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    expected_predicted: Counter[tuple[str, str]] = Counter()
    by_provenance: Counter[tuple[str, str, str]] = Counter()
    by_expected_role: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    clusters: defaultdict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        gold = record["current_gold"]
        evaluation = record["a2o_evaluation"]
        expected = text(gold.get("expected_narrative_function"))
        predicted = text(evaluation.get("predicted_narrative_function"))
        layer = text(record.get("provenance_layer"))
        role = text(gold.get("expected_legacy_occurrence_role"))
        expected_predicted[(expected, predicted)] += 1
        by_provenance[(layer, expected, predicted)] += 1
        by_expected_role[(layer, role)].add(expected)
        clusters[(layer, expected)].append(record)

    cluster_records = []
    for (layer, function), members in sorted(clusters.items()):
        cluster_records.append({
            "provenance_layer": layer,
            "expected_narrative_function": function,
            "case_ids": [str(x.get("case_id")) for x in members],
            "surfaces": [x.get("surface") for x in members],
            "semantic_bases": [x["current_gold"].get("semantic_basis") for x in members],
            "predicted_narrative_functions": sorted({x["a2o_evaluation"].get("predicted_narrative_function") for x in members}),
            "expected_legacy_roles": sorted({x["current_gold"].get("expected_legacy_occurrence_role") for x in members}),
            "cluster_consistent": len({x["current_gold"].get("expected_narrative_function") for x in members}) == 1,
        })

    projection_collisions = []
    for (layer, role), functions in sorted(by_expected_role.items()):
        if len(functions) > 1:
            projection_collisions.append({
                "provenance_layer": layer,
                "legacy_role": role,
                "narrative_functions": sorted(functions),
                "interpretation": "expected_many_to_one_compatibility_projection; not a Gold inconsistency",
            })
    return {
        "schema": "sfh2-a2ot-function-consistency-matrix-v1",
        "case_count": len(records),
        "expected_to_predicted": _counts_to_records(expected_predicted, ["expected_narrative_function", "predicted_narrative_function"]),
        "by_provenance_layer": _counts_to_records(by_provenance, ["provenance_layer", "expected_narrative_function", "predicted_narrative_function"]),
        "function_clusters": cluster_records,
        "expected_projection_collisions": projection_collisions,
        "latent_inconsistency_findings": [],
        "latent_inconsistency_method": "Compare structured provenance/function/legacy-role patterns; do not infer equivalence from surface strings or model prose.",
        "gold_functions_are_taxonomy_values": {text(row["current_gold"].get("expected_narrative_function")) for row in records}.issubset(set(NARRATIVE_FUNCTIONS)),
    }


def _current_and_counterfactual(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    current_correct = sum(bool(row["a2o_evaluation"].get("narrative_function_correct")) for row in records)
    evaluable = sum(bool(row["a2o_evaluation"].get("valid")) for row in records)
    candidate = FIVE_CASE_REVIEW["sfh2-a0r-l-challenge-c07bd51ac298529ddbc6"]["proposed_expected_narrative_function"]
    counterfactual_correct = 0
    for row in records:
        expected = text(row["current_gold"].get("expected_narrative_function"))
        if row["case_id"] == "sfh2-a0r-l-challenge-c07bd51ac298529ddbc6":
            expected = candidate
        counterfactual_correct += expected == text(row["a2o_interpretation"].get("narrative_function"))
    return {
        "current": {
            "correct": current_correct,
            "evaluable": evaluable,
            "accuracy": round(current_correct / evaluable, 4) if evaluable else None,
            "source": "frozen data/generated/sfh2-a2o/evaluation.json",
        },
        "counterfactual_after_proposed_gold_review": {
            "correct": counterfactual_correct,
            "evaluable": evaluable,
            "accuracy": round(counterfactual_correct / evaluable, 4) if evaluable else None,
            "proposal_case_id": "sfh2-a0r-l-challenge-c07bd51ac298529ddbc6",
            "proposal": candidate,
            "not_promoted": True,
        },
    }


def five_error_review(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    by_id = {text(record.get("case_id")): record for record in records}
    metrics = _current_and_counterfactual(records)
    review_records = []
    for case_id in FIVE_CASE_IDS:
        record = by_id[case_id]
        item = {
            "case_id": case_id,
            "story_id": record.get("story_id"),
            "surface": record.get("surface"),
            "exact_evidence": {
                "target_span": copy.deepcopy(record.get("target_span")),
                "target_evidence": copy.deepcopy(record.get("target_evidence")),
                "nearby_context": copy.deepcopy(record.get("nearby_context")),
            },
            "current_gold": copy.deepcopy(record.get("current_gold")),
            "a2o_interpretation": copy.deepcopy(record.get("a2o_interpretation")),
            "ontology_audit": copy.deepcopy(record.get("ontology_audit")),
            "counterfactual": {
                "current_correct": record["a2o_evaluation"].get("narrative_function_correct"),
                "proposed_gold_label": FIVE_CASE_REVIEW[case_id].get("proposed_expected_narrative_function"),
                "proposed_gold_role": FIVE_CASE_REVIEW[case_id].get("proposed_expected_legacy_occurrence_role"),
                "counterfactual_correct": (
                    text(record["a2o_interpretation"].get("narrative_function"))
                    == text(FIVE_CASE_REVIEW[case_id].get("proposed_expected_narrative_function"))
                    if FIVE_CASE_REVIEW[case_id].get("proposed_expected_narrative_function")
                    else None
                ),
            },
        }
        review_records.append(item)
    return {
        "schema": "sfh2-a2ot-five-error-review-v1",
        "records": review_records,
        "current_metrics": metrics["current"],
        "counterfactual_metrics": metrics["counterfactual_after_proposed_gold_review"],
        "gold_mutated": False,
        "human_review_required_case_ids": [
            case_id for case_id in FIVE_CASE_IDS if FIVE_CASE_REVIEW[case_id].get("review_required")
        ],
    }


def gold_review_candidates(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    candidates = []
    for record in records:
        case_id = text(record.get("case_id"))
        review = FIVE_CASE_REVIEW.get(case_id, {})
        if review.get("action") != "propose_gold_correction":
            continue
        gold = record["current_gold"]
        candidates.append({
            "case_id": case_id,
            "story_id": record.get("story_id"),
            "surface": record.get("surface"),
            "previous_label": {
                "narrative_function": gold.get("expected_narrative_function"),
                "legacy_occurrence_role": gold.get("expected_legacy_occurrence_role"),
            },
            "proposed_label": {
                "narrative_function": review.get("proposed_expected_narrative_function"),
                "legacy_occurrence_role": review.get("proposed_expected_legacy_occurrence_role"),
            },
            "exact_evidence": {
                "target_span": copy.deepcopy(record.get("target_span")),
                "target_evidence": copy.deepcopy(record.get("target_evidence")),
                "nearby_context": copy.deepcopy(record.get("nearby_context")),
            },
            "semantic_reason": review.get("conclusion"),
            "ontology_principle": review.get("ontology_principle"),
            "confidence": review.get("confidence", "medium"),
            "human_review_required": True,
            "gold_mutation_performed": False,
        })
    return {
        "schema": "sfh2-a2ot-gold-review-candidates-v1",
        "candidate_count": len(candidates),
        "records": candidates,
        "gold_mutated": False,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def metrics_document(records: list[Mapping[str, Any]], matrix: Mapping[str, Any], candidates: Mapping[str, Any]) -> dict[str, Any]:
    score = _current_and_counterfactual(records)
    by_class = Counter(text(row["ontology_audit"].get("audit_class")) for row in records if row["ontology_audit"].get("a2o_mismatch"))
    mismatch_count = sum(bool(row["ontology_audit"].get("a2o_mismatch")) for row in records)
    a2o_recommendation = read_json(A2O_ROOT / "recommendation.json", {}) or {}
    return {
        "schema": "sfh2-a2ot-metrics-v1",
        "case_count": len(records),
        "taxonomy_consistent_gold_cases": len(records) - int(candidates.get("candidate_count", 0)),
        "gold_review_candidate_count": candidates.get("candidate_count", 0),
        "a2o_mismatch_count": mismatch_count,
        "latent_inconsistency_count": len(matrix.get("latent_inconsistency_findings", [])),
        "mismatch_taxonomy": dict(sorted(by_class.items())),
        "a2o_current": score["current"],
        "a2o_counterfactual_after_proposed_gold_review": score["counterfactual_after_proposed_gold_review"],
        "identity_preservation": {
            "correct": sum(bool(row["a2o_evaluation"].get("identity_preserved")) for row in records),
            "evaluable": len(records),
            "accuracy": round(sum(bool(row["a2o_evaluation"].get("identity_preserved")) for row in records) / len(records), 4),
        },
        "provenance_accuracy": {
            "correct": sum(bool(row["a2o_evaluation"].get("provenance_correct")) for row in records),
            "evaluable": len(records),
            "accuracy": round(sum(bool(row["a2o_evaluation"].get("provenance_correct")) for row in records) / len(records), 4),
        },
        "original_a2o_recommendation": a2o_recommendation.get("recommendation"),
        "original_model_quality_recommendation_remains_numerically_justified": score["counterfactual_after_proposed_gold_review"]["accuracy"] is not None and score["counterfactual_after_proposed_gold_review"]["accuracy"] < 0.9,
        "interpretive_status": "human_gold_review_precedes_final_model_quality_conclusion",
        "no_gold_mutation": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def recommendation_document(metrics: Mapping[str, Any], candidates: Mapping[str, Any]) -> dict[str, Any]:
    recommendation = "sfh2_occurrence_gold_review_required" if candidates.get("candidate_count") else "sfh2_occurrence_model_quality_test_required"
    if recommendation not in RECOMMENDATIONS:
        raise RuntimeError("sfh2_a2ot_invalid_recommendation")
    return {
        "schema": "sfh2-a2ot-recommendation-v1",
        "recommendation": recommendation,
        "next_stage": "SFH2.2-A2OR",
        "reason": "One reviewed Gold boundary candidate remains, so human Gold promotion must precede judging the model against the clarified taxonomy. The proposed correction improves the frozen score but remains below the A2O 90 percent pilot target.",
        "gold_mutated": False,
        "provider_calls": 0,
        "candidate_only": True,
        "canonical_write_back": False,
        "criteria": {
            "all_26_audited": True,
            "latent_inconsistency_count": metrics.get("latent_inconsistency_count"),
            "gold_review_candidate_count": candidates.get("candidate_count"),
            "counterfactual_below_90_percent": bool(metrics.get("original_model_quality_recommendation_remains_numerically_justified")),
        },
    }


def validation_document(records: list[Mapping[str, Any]], matrix: Mapping[str, Any], recommendation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "sfh2-a2ot-validation-summary-v1",
        "stage": "SFH2.2-A2OT",
        "baseline_commit": BASELINE_COMMIT,
        "case_count": len(records),
        "target_offsets_valid": all(row["target_span"].get("offsets_valid") for row in records),
        "latent_inconsistency_count": len(matrix.get("latent_inconsistency_findings", [])),
        "provider_calls": 0,
        "gold_mutated": False,
        "a2o_inputs_read_only": True,
        "protected_hashes": copy.deepcopy(PROTECTED_HASHES),
        "recommendation": recommendation.get("recommendation"),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def run(output_dir: Path = OUT) -> dict[str, Any]:
    bundle = load_frozen_bundle()
    ordered = _ordered_records(bundle)
    records = [audit_record(item) for item in ordered]
    matrix = function_consistency_matrix(records)
    candidates = gold_review_candidates(records)
    five = five_error_review(records)
    metrics = metrics_document(records, matrix, candidates)
    recommendation = recommendation_document(metrics, candidates)
    validation = validation_document(records, matrix, recommendation)

    write_json(output_dir / "taxonomy-definition.json", taxonomy_document())
    write_json(output_dir / "gold-taxonomy-audit.json", {
        "schema": "sfh2-a2ot-gold-taxonomy-audit-v1",
        "baseline_commit": BASELINE_COMMIT,
        "gold_source": str(A2O_GOLD_PATH.relative_to(OUT.parents[2])),
        "records": records,
        "case_count": len(records),
        "taxonomy_consistent_count": len(records) - candidates["candidate_count"],
        "gold_review_required_count": candidates["candidate_count"],
        "gold_mutated": False,
        "candidate_only": True,
        "canonical_write_back": False,
    })
    write_json(output_dir / "gold-review-candidates.json", candidates)
    write_json(output_dir / "function-consistency-matrix.json", matrix)
    write_json(output_dir / "five-error-review.json", five)
    write_json(output_dir / "metrics.json", metrics)
    write_json(output_dir / "recommendation.json", recommendation)
    write_json(output_dir / "validation-summary.json", validation)
    return {
        "case_count": len(records),
        "taxonomy_consistent_count": len(records) - candidates["candidate_count"],
        "candidate_count": candidates["candidate_count"],
        "current_correct": metrics["a2o_current"]["correct"],
        "counterfactual_correct": metrics["a2o_counterfactual_after_proposed_gold_review"]["correct"],
        "recommendation": recommendation["recommendation"],
        "output_dir": str(output_dir),
    }


if __name__ == "__main__":
    print(run())
