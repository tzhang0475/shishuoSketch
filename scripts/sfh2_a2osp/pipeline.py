"""Offline Gold promotion and residual qualification for SFH2.2-A2OSP."""

from __future__ import annotations

import copy
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from .common import (
    A2OS_ROOT,
    A2OR_ROOT,
    AUTHORITY_PATH,
    BASELINE_COMMIT,
    CASE_COUNT,
    EXPECTED_CHANGED_CASES,
    FROZEN_SC1_SHA256,
    CURRENT_SC1_SHA256,
    GOLD_PATH,
    IDENTITY_MANIFEST_PATH,
    IDENTITY_MANIFEST_SHA256,
    OUT,
    PREVIOUS_GOLD_SHA256,
    ROOT,
    by_case,
    changed_fields,
    file_hash,
    load_inputs,
    occurrence_key,
    protected_hashes,
    score,
    stable_hash,
    text,
    write_json,
)


def _authority_by_case(inputs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        text(row.get("case_id")): row
        for row in inputs["authority"].get("records", [])
        if isinstance(row, Mapping) and text(row.get("case_id"))
    }


def _a2os_by_case(inputs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return inputs["exact"]


def _gold_delta(inputs: Mapping[str, Any]) -> dict[str, Any]:
    before = inputs["frozen_gold"]
    after = inputs["active_gold"]
    changed = [case_id for case_id in (text(row.get("case_id")) for row in inputs["selection"]) if before[case_id] != after[case_id]]
    authority_rows = _authority_by_case(inputs)
    records: list[dict[str, Any]] = []
    for case_id in changed:
        authority = authority_rows.get(case_id, {})
        records.append({
            "case_id": case_id,
            "exact_occurrence_key": copy.deepcopy(authority.get("exact_occurrence_key")),
            "changed_fields": changed_fields(before[case_id], after[case_id]),
            "previous_gold": copy.deepcopy(before[case_id]),
            "reviewed_gold": copy.deepcopy(after[case_id]),
            "human_authority": copy.deepcopy({
                "authority": authority.get("authority"),
                "review_status": authority.get("review_status"),
                "semantic_basis": authority.get("semantic_basis"),
                "root_cause": authority.get("root_cause"),
            }),
        })
    unchanged = [case_id for case_id in before if case_id not in changed and before[case_id] == after[case_id]]
    return {
        "schema": "sfh2-a2osp-reviewed-gold-delta-v1",
        "stage": "SFH2.2-A2OSP",
        "predecessor_stage": "SFH2.2-A2OS",
        "baseline_commit": BASELINE_COMMIT,
        "previous_gold_sha256": PREVIOUS_GOLD_SHA256,
        "new_gold_sha256": file_hash(GOLD_PATH),
        "active_gold_revision": copy.deepcopy(read_gold_revision()),
        "changed_case_ids": changed,
        "substantive_mutation_count": len(changed),
        "unchanged_case_count": len(unchanged),
        "other_24_records_unchanged": len(unchanged) == CASE_COUNT - 2,
        "records": records,
        "model_output_used_as_authority": False,
        "canonical_write_back": False,
        "candidate_only": True,
        "provider_calls": 0,
    }


def read_gold_revision() -> dict[str, Any]:
    document = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    revision = document.get("gold_revision")
    return copy.deepcopy(revision) if isinstance(revision, Mapping) else {}


def _post_alignment(case_id: str, exact: Mapping[str, Any], authority: Mapping[str, Any]) -> dict[str, Any]:
    actual = occurrence_key(exact)
    if authority:
        pinned = authority.get("exact_occurrence_key")
        key_matches = isinstance(pinned, Mapping) and actual == {field: pinned.get(field) for field in actual}
        source = "A2OSP human authority exact occurrence key"
    else:
        key_matches = exact.get("gold_occurrence_alignment") == "correct"
        source = "immutable A2OS exact-occurrence audit"
    integrity = exact.get("integrity") if isinstance(exact.get("integrity"), Mapping) else {}
    selection = exact.get("selection_intent_target_alignment")
    return {
        "gold_occurrence_alignment": "correct" if key_matches else "review_required",
        "gold_taxonomy_status": "consistent" if key_matches else "review_required",
        "target_key_matches_reviewed_authority": key_matches,
        "target_ambiguity": selection == "ambiguous" or not integrity.get("structural_valid", False),
        "source": source,
    }


def _evaluation_rows(inputs: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    authority = _authority_by_case(inputs)
    a2os = _a2os_by_case(inputs)
    pre_rows: list[dict[str, Any]] = []
    post_rows: list[dict[str, Any]] = []
    for selection in inputs["selection"]:
        case_id = text(selection.get("case_id"))
        exact = a2os[case_id]
        frozen_gold = inputs["frozen_gold"][case_id]
        active_gold = inputs["active_gold"][case_id]
        a2or = inputs["a2or_evaluation"][case_id]
        result = inputs["a2or_results"][case_id]
        projection = inputs["a2or_projection"][case_id]
        predicted_function = a2or.get("predicted_narrative_function")
        predicted_role = a2or.get("predicted_legacy_occurrence_role")
        valid = a2or.get("valid") is True and result.get("valid") is True
        common = {
            "case_id": case_id,
            "cohort": selection.get("cohort"),
            "story_id": selection.get("story_id"),
            "surface": selection.get("surface"),
            "exact_occurrence_key": occurrence_key(exact),
            "predicted_narrative_function": predicted_function,
            "predicted_legacy_occurrence_role": predicted_role,
            "confidence": a2or.get("confidence"),
            "provider_output_valid": valid,
            "provenance_layer": a2or.get("provenance_layer"),
            "expected_provenance_layer": active_gold.get("expected_provenance_layer"),
            "provenance_correct": valid and a2or.get("provenance_correct") is True,
            "identity_preserved": a2or.get("identity_preserved") is True,
            "candidate_only": True,
            "canonical_write_back": False,
        }
        pre_rows.append({
            **copy.deepcopy(common),
            "expected_narrative_function": frozen_gold.get("expected_narrative_function"),
            "expected_legacy_occurrence_role": frozen_gold.get("expected_legacy_occurrence_role"),
            "narrative_function_correct": valid and predicted_function == frozen_gold.get("expected_narrative_function"),
            "legacy_occurrence_role_correct": valid and predicted_role == frozen_gold.get("expected_legacy_occurrence_role"),
            "gold_revision_view": "A2OS/A2OR pre-promotion Gold witness",
        })
        alignment = _post_alignment(case_id, exact, authority.get(case_id, {}))
        post_rows.append({
            **copy.deepcopy(common),
            "expected_narrative_function": active_gold.get("expected_narrative_function"),
            "expected_legacy_occurrence_role": active_gold.get("expected_legacy_occurrence_role"),
            "narrative_function_correct": valid and predicted_function == active_gold.get("expected_narrative_function"),
            "legacy_occurrence_role_correct": valid and predicted_role == active_gold.get("expected_legacy_occurrence_role"),
            "pre_promotion_expected_narrative_function": frozen_gold.get("expected_narrative_function"),
            "pre_promotion_expected_legacy_occurrence_role": frozen_gold.get("expected_legacy_occurrence_role"),
            "gold_occurrence_alignment": alignment["gold_occurrence_alignment"],
            "gold_taxonomy_status": alignment["gold_taxonomy_status"],
            "target_key_matches_reviewed_authority": alignment["target_key_matches_reviewed_authority"],
            "target_ambiguity": alignment["target_ambiguity"],
            "alignment_source": alignment["source"],
            "reason_summary": a2or.get("reason_summary"),
            "errors": copy.deepcopy(a2or.get("errors", [])),
            "gold_revision_view": "A2OSP promoted Gold",
        })
    return pre_rows, post_rows


def _cohort_metrics(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    by_cohort: dict[str, Any] = {}
    for cohort in sorted({text(row.get("cohort")) for row in records}):
        subset = [row for row in records if text(row.get("cohort")) == cohort]
        by_cohort[cohort] = {
            "case_count": len(subset),
            "narrative_function": score(subset, "narrative_function_correct"),
            "legacy_occurrence_role": score(subset, "legacy_occurrence_role_correct"),
            "provenance": score(subset, "provenance_correct"),
            "identity_preservation": score(subset, "identity_preserved"),
            "resolution_coverage": score(subset, "provider_output_valid"),
        }
    return by_cohort


def evaluation_document(inputs: Mapping[str, Any]) -> dict[str, Any]:
    pre_rows, post_rows = _evaluation_rows(inputs)
    metrics = {
        "pre_promotion": {
            "narrative_function": score(pre_rows, "narrative_function_correct"),
            "legacy_occurrence_role": score(pre_rows, "legacy_occurrence_role_correct"),
            "resolution_coverage": score(pre_rows, "provider_output_valid"),
        },
        "post_promotion": {
            "narrative_function": score(post_rows, "narrative_function_correct"),
            "legacy_occurrence_role": score(post_rows, "legacy_occurrence_role_correct"),
            "provenance": score(post_rows, "provenance_correct"),
            "identity_preservation": score(post_rows, "identity_preserved"),
            "resolution_coverage": score(post_rows, "provider_output_valid"),
        },
    }
    return {
        "schema": "sfh2-a2osp-a2or-post-promotion-evaluation-v1",
        "stage": "SFH2.2-A2OSP",
        "case_count": len(post_rows),
        "pre_promotion_metrics": metrics["pre_promotion"],
        "post_promotion_metrics": metrics["post_promotion"],
        "by_cohort": _cohort_metrics(post_rows),
        "records": post_rows,
        "pre_promotion_records": pre_rows,
        "provider_calls": 0,
        "gold_loaded_after_frozen_inference": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _error_family(expected: Any, predicted: Any) -> str:
    if expected == "reference" and predicted == "participant":
        return "reference_to_participant_overreach"
    return "semantic_function_mismatch"


def residual_document(inputs: Mapping[str, Any], evaluation: Mapping[str, Any]) -> dict[str, Any]:
    residuals: list[dict[str, Any]] = []
    for row in evaluation["records"]:
        if row.get("narrative_function_correct") and row.get("legacy_occurrence_role_correct"):
            continue
        checks = {
            "exact_occurrence_alignment": row.get("gold_occurrence_alignment") == "correct" and row.get("target_key_matches_reviewed_authority") is True,
            "gold_taxonomy_consistent": row.get("gold_taxonomy_status") == "consistent",
            "frozen_identity_preserved": row.get("identity_preserved") is True,
            "provenance_correct": row.get("provenance_correct") is True,
            "provider_output_valid": row.get("provider_output_valid") is True,
            "target_unambiguous": row.get("target_ambiguity") is False,
        }
        family = _error_family(row.get("expected_narrative_function"), row.get("predicted_narrative_function"))
        residuals.append({
            "case_id": row.get("case_id"),
            "story_id": row.get("story_id"),
            "surface": row.get("surface"),
            "exact_occurrence_key": copy.deepcopy(row.get("exact_occurrence_key")),
            "expected_narrative_function": row.get("expected_narrative_function"),
            "predicted_narrative_function": row.get("predicted_narrative_function"),
            "expected_legacy_occurrence_role": row.get("expected_legacy_occurrence_role"),
            "predicted_legacy_occurrence_role": row.get("predicted_legacy_occurrence_role"),
            "confidence": row.get("confidence"),
            "error_family": family,
            "qualification_checks": checks,
            "qualified_as_genuine_semantic_error": all(checks.values()),
            "interpretation": "The pinned occurrence and reviewed Gold align; the remaining mismatch is semantic rather than target or transport failure." if all(checks.values()) else "The mismatch remains unresolved because at least one alignment, Gold, identity, provenance, provider, or ambiguity check failed.",
        })
    families = Counter(row["error_family"] for row in residuals)
    qualified = [row for row in residuals if row["qualified_as_genuine_semantic_error"]]
    return {
        "schema": "sfh2-a2osp-residual-error-qualification-v1",
        "case_count": len(evaluation["records"]),
        "wrong_case_count": len(residuals),
        "qualified_genuine_error_count": len(qualified),
        "records": residuals,
        "error_family_counts": dict(sorted(families.items())),
        "high_confidence_qualified_error_count": sum(row.get("confidence") == "high" for row in qualified),
        "coherent_single_family": len(families) == 1 and bool(families),
        "candidate_only": True,
        "canonical_write_back": False,
        "provider_calls": 0,
    }


def assessment_document(evaluation: Mapping[str, Any], residual: Mapping[str, Any]) -> dict[str, Any]:
    post = evaluation["post_promotion_metrics"]
    six = next((value for key, value in evaluation["by_cohort"].items() if key == "reviewed_role"), {})
    adequate = post["narrative_function"]["accuracy"] is not None and post["narrative_function"]["accuracy"] >= 0.9
    full_coverage = post["resolution_coverage"]["accuracy"] == 1.0
    single_qualified = adequate and full_coverage and residual["qualified_genuine_error_count"] == 0
    return {
        "schema": "sfh2-a2osp-single-historian-assessment-v1",
        "overall_pilot_accuracy_adequate": adequate,
        "six_reviewed_role_cases": six,
        "resolution_coverage": post["resolution_coverage"],
        "residual_error_count": residual["qualified_genuine_error_count"],
        "residual_error_families": residual["error_family_counts"],
        "high_confidence_systematic_boundary_error": residual["high_confidence_qualified_error_count"] >= 2 and residual["coherent_single_family"],
        "a2or_predictions_changed": False,
        "single_historian_fully_qualified": single_qualified,
        "qualification_interpretation": "Overall pilot accuracy is adequate, but the single historian is not fully qualified because high-confidence residual errors share one reference-to-participant boundary family." if not single_qualified else "No qualified residual semantic errors remain.",
        "recommended_next_stage": "SFH2.2-A2OV" if not single_qualified else None,
        "candidate_only": True,
        "canonical_write_back": False,
        "provider_calls": 0,
    }


def selection_integrity_document(inputs: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "sfh2-a2osp-selection-integrity-invariant-v1",
        "historical_selector": "scripts/sfh2_a0r_l/selection.py",
        "historical_selector_rewritten": False,
        "required_target_fields": ["mention_id", "source_evidence_id", "source_start", "source_end", "surface"],
        "story_id_is_context_not_sufficient_identity": True,
        "surface_only_resolution_forbidden_when_multiple_matches": True,
        "python_may_enforce_exact_occurrence_identity": True,
        "python_may_infer_semantic_role_from_offsets": False,
        "all_current_cases_have_exact_keys": len(inputs["exact"]) == CASE_COUNT,
        "prospective_rule": "Pin every semantic evaluation or production target by mention_id, source_evidence_id, source_start, source_end, and surface; reject unresolved ambiguity before semantic evaluation.",
        "candidate_only": True,
        "canonical_write_back": False,
        "provider_calls": 0,
    }


def metrics_document(delta: Mapping[str, Any], evaluation: Mapping[str, Any], residual: Mapping[str, Any], assessment: Mapping[str, Any]) -> dict[str, Any]:
    post = evaluation["post_promotion_metrics"]
    cohorts = evaluation["by_cohort"]
    return {
        "schema": "sfh2-a2osp-metrics-v1",
        "provider_calls": 0,
        "gold_mutations": delta["substantive_mutation_count"],
        "other_gold_records_unchanged": delta["unchanged_case_count"],
        "a2or_pre_promotion": evaluation["pre_promotion_metrics"],
        "a2or_post_promotion": post,
        "six_reviewed_role_cases": cohorts.get("reviewed_role", {}),
        "challenge_cases": cohorts.get("challenge", {}),
        "remaining_genuine_semantic_errors": residual["qualified_genuine_error_count"],
        "residual_error_family_counts": residual["error_family_counts"],
        "resolution_coverage": post["resolution_coverage"],
        "provenance_accuracy": post["provenance"],
        "identity_preservation": post["identity_preservation"],
        "single_historian_fully_qualified": assessment["single_historian_fully_qualified"],
        "candidate_only": True,
        "canonical_write_back": False,
    }


def recommendation_document(assessment: Mapping[str, Any], residual: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "sfh2-a2osp-recommendation-v1",
        "recommendation": "sfh2_occurrence_single_historian_qualified" if assessment["single_historian_fully_qualified"] else "sfh2_occurrence_semantic_reviewer_test_required",
        "qualified": assessment["single_historian_fully_qualified"],
        "next_stage": assessment["recommended_next_stage"],
        "reason": assessment["qualification_interpretation"],
        "residual_error_count": residual["qualified_genuine_error_count"],
        "residual_error_families": residual["error_family_counts"],
        "gold_alignment_promoted": True,
        "provider_calls": 0,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def protected_input_snapshot() -> dict[str, Any]:
    paths = [
        "data/generated/sfh2-a2o",
        "data/generated/sfh2-a2ot",
        "data/generated/sfh2-a2or",
        "data/generated/sfh2-a2os",
        "data/frozen/sfh2/identity-v1/manifest.json",
        "data/derived/sc1-site.json",
        "data/derived/sc1-current-site.json",
        "data/people.json",
        "data/aliases.json",
    ]
    result: dict[str, Any] = {}
    for relative in paths:
        path = ROOT / relative
        if path.is_file():
            result[relative] = {"sha256": file_hash(path), "size_bytes": path.stat().st_size}
        elif path.is_dir():
            files = sorted(file for file in path.rglob("*") if file.is_file())
            result[relative] = {
                "file_count": len(files),
                "sha256_by_file": {str(file.relative_to(ROOT)): file_hash(file) for file in files},
            }
    return result


def run(output: Path = OUT) -> dict[str, Any]:
    inputs = load_inputs()
    delta = _gold_delta(inputs)
    evaluation = evaluation_document(inputs)
    residual = residual_document(inputs, evaluation)
    assessment = assessment_document(evaluation, residual)
    documents = {
        "reviewed-gold-delta.json": delta,
        "a2or-post-promotion-evaluation.json": evaluation,
        "residual-error-qualification.json": residual,
        "single-historian-assessment.json": assessment,
        "selection-integrity-invariant.json": selection_integrity_document(inputs),
        "metrics.json": metrics_document(delta, evaluation, residual, assessment),
        "recommendation.json": recommendation_document(assessment, residual),
    }
    for name, document in documents.items():
        write_json(output / name, document)
    return documents
