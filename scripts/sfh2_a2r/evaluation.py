"""Evaluation-only helpers for the A2R regression.

This module reads the frozen A0R evaluation authority after semantic outputs
are materialized.  It never participates in provider prompts or runtime
identity selection.
"""

from __future__ import annotations

import copy
from collections import Counter
from typing import Any, Mapping

from sfh2_a0r.evaluation import _strict, dimensions, gold_by_case

from .common import A2_ROOT, ROOT, text, read_json


def _record(row: Mapping[str, Any] | None, key: str = "record") -> Mapping[str, Any] | None:
    if isinstance(row, Mapping) and row.get("valid") is True and isinstance(row.get(key), Mapping):
        return row.get(key)
    return None


def _unresolved_dimensions() -> dict[str, bool | None]:
    return {
        "identity_correct": None,
        "semantic_kind_correct": None,
        "referent_surface_correct": None,
        "canonicalization_correct": None,
        "occurrence_role_correct": None,
        "attribute_fields_correct": None,
        "discourse_correct": None,
        "relation_correct": None,
        "serialization_contract_correct": False,
    }


def stage_dimensions(row: Mapping[str, Any] | None, gold: Mapping[str, Any], *, record_key: str = "record") -> dict[str, bool | None]:
    record = _record(row, record_key)
    if record is None:
        return _unresolved_dimensions()
    for_eval = dict(record)
    if isinstance(row, Mapping):
        realization = row.get("provisional_realization") if isinstance(row.get("provisional_realization"), Mapping) else {}
        candidate = realization.get("candidate") if isinstance(realization.get("candidate"), Mapping) else {}
        for_eval["_evaluation_candidate"] = candidate
    dims = dimensions(for_eval, gold)
    dims["serialization_contract_correct"] = True
    return dims


def is_common_mode_identity_error(row: Mapping[str, Any]) -> bool:
    """Detect two wrong historians sharing an identity hypothesis.

    Whole-record agreement is intentionally not required: role, discourse,
    relation, or evidence metadata can differ while both records still make
    the same wrong identity claim.  This is an evaluation predicate only; it
    does not infer identity from record content.
    """

    comparison = row.get("comparison") if isinstance(row.get("comparison"), Mapping) else {}
    historian_a = row.get("historian_a") if isinstance(row.get("historian_a"), Mapping) else {}
    historian_b = row.get("historian_b") if isinstance(row.get("historian_b"), Mapping) else {}
    return (
        historian_a.get("identity_correct") is False
        and historian_b.get("identity_correct") is False
        and comparison.get("historical_identity_disagreement") is False
    )


def _gold_map(cases: list[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    selection = read_json(A2_ROOT / "selection-hashes.json", {}) or {}
    # A2's immutable selection hash file intentionally contains hashes only;
    # the actual frozen selection is supplied by the A1R-L authority.
    selection = read_json(ROOT / "data/generated/sfh2-a0r-l/regression-selection.json", {}) or {}
    authority = read_json(ROOT / "data/annotation/sfh2-a0-evaluation-gold.json", {}) or {}
    return gold_by_case(selection, authority)


def evaluate_regression(
    cases: list[Mapping[str, Any]],
    a_rows: Mapping[str, Mapping[str, Any]],
    b_rows: Mapping[str, Mapping[str, Any]],
    comparisons: Mapping[str, Mapping[str, Any]],
    adjudications: Mapping[str, Mapping[str, Any]],
    finals: list[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    golds = _gold_map(cases)
    final_map = {text(row.get("case_id")): row for row in finals}
    rows: list[dict[str, Any]] = []
    for case in cases:
        case_id = text(case.get("case_id"))
        gold = dict(golds.get(case_id, {}))
        a = a_rows[case_id]
        b = b_rows[case_id]
        final = final_map.get(case_id, {})
        a_dims = stage_dimensions(a, gold)
        b_dims = stage_dimensions(b, gold)
        final_wrapper = {
            "valid": isinstance(final.get("selected_record"), Mapping),
            "record": final.get("selected_record"),
            "provisional_realization": final.get("provisional_realization"),
        }
        final_dims = stage_dimensions(final_wrapper, gold)
        identity_evaluable = text(gold.get("expected_semantic_kind")) == "historical_person" and bool(text(gold.get("expected_canonical_hint")))
        resolved = identity_evaluable and final.get("final_state") != "review_required" and isinstance(final.get("selected_record"), Mapping)
        rows.append({
            "case_id": case_id,
            "story_id": case.get("story_id"),
            "surface": case.get("surface"),
            "gold": gold,
            "historian_a": a_dims,
            "historian_b": b_dims,
            "final": final_dims,
            "a_valid": a.get("valid") is True,
            "b_valid": b.get("valid") is True,
            "comparison": copy.deepcopy(comparisons.get(case_id, {})),
            "adjudication": copy.deepcopy(adjudications.get(case_id)),
            "final_state": final.get("final_state"),
            "final_resolution_status": "resolved" if resolved else "unresolved" if identity_evaluable else "not_identity_evaluable",
            "candidate_only": True,
            "canonical_write_back": False,
            "historical_identity_evaluable": identity_evaluable,
        })

    identity_rows = [row for row in rows if row["historical_identity_evaluable"]]

    def identity_stats(stage: str) -> dict[str, Any]:
        values = [row[stage].get("identity_correct") for row in identity_rows]
        resolved_values = [value for value in values if value is not None]
        return {
            "correct": sum(value is True for value in values),
            "wrong": sum(value is False for value in values),
            "unresolved": sum(value is None for value in values),
            "evaluable": len(values),
            "resolved": len(resolved_values),
            "resolution_coverage": round(len(resolved_values) / len(values), 4) if values else None,
            "accuracy_on_resolved": round(sum(value is True for value in resolved_values) / len(resolved_values), 4) if resolved_values else None,
            "full_cohort_accuracy": round(sum(value is True for value in values) / len(values), 4) if values else None,
        }

    def dimension_counts(stage: str) -> dict[str, dict[str, Any]]:
        fields = ("identity_correct", "semantic_kind_correct", "referent_surface_correct", "canonicalization_correct", "occurrence_role_correct", "discourse_correct", "relation_correct", "attribute_fields_correct", "serialization_contract_correct")
        return {
            field: {
                "correct": sum(row[stage].get(field) is True for row in rows),
                "incorrect": sum(row[stage].get(field) is False for row in rows),
                "evaluable": sum(row[stage].get(field) is not None for row in rows),
            }
            for field in fields
        }

    a_errors = [row for row in identity_rows if row["historian_a"].get("identity_correct") is False]
    a_noncorrect = [row for row in identity_rows if row["historian_a"].get("identity_correct") is not True]
    error_disagreements = [row for row in a_errors if row["comparison"].get("historical_identity_disagreement") is True or row["comparison"].get("contract_validity_disagreement")]
    noncorrect_disagreements = [row for row in a_noncorrect if row["comparison"].get("historical_identity_disagreement") is True or row["comparison"].get("contract_validity_disagreement")]
    common_mode = [row for row in identity_rows if is_common_mode_identity_error(row)]
    damage = [
        row for row in identity_rows
        if row["final"].get("identity_correct") is False
        and (row["historian_a"].get("identity_correct") is True or row["historian_b"].get("identity_correct") is True)
        and row.get("final_resolution_status") == "resolved"
    ]
    valid_adj = [row for row in adjudications.values() if row.get("valid") is True]
    metrics: dict[str, Any] = {
        "case_count": len(rows),
        "historical_identity_evaluable": len(identity_rows),
        "historian_a_identity": identity_stats("historian_a"),
        "historian_b_identity": identity_stats("historian_b"),
        "final_identity": identity_stats("final"),
        "resolution_coverage": identity_stats("final")["resolution_coverage"],
        "identity_accuracy_on_resolved": identity_stats("final")["accuracy_on_resolved"],
        "full_cohort_identity_accuracy": identity_stats("final")["full_cohort_accuracy"],
        "historian_a_strict_full_record_accuracy": round(sum(_strict(row["historian_a"]) for row in rows) / len(rows), 4) if rows else None,
        "historian_b_strict_full_record_accuracy": round(sum(_strict(row["historian_b"]) for row in rows) / len(rows), 4) if rows else None,
        "final_strict_full_record_accuracy": round(sum(_strict(row["final"]) for row in rows) / len(rows), 4) if rows else None,
        "dimension_counts": {stage: dimension_counts(stage) for stage in ("historian_a", "historian_b", "final")},
        "a_identity_errors": len(a_errors),
        "a_identity_errors_with_ab_disagreement": len(error_disagreements),
        "a_error_disagreement_recall": round(len(error_disagreements) / len(a_errors), 4) if a_errors else None,
        "a_identity_unresolved": sum(row["historian_a"].get("identity_correct") is None for row in identity_rows),
        "a_identity_noncorrect_cases": len(a_noncorrect),
        "a_identity_noncorrect_with_ab_disagreement": len(noncorrect_disagreements),
        "a_noncorrect_disagreement_recall": round(len(noncorrect_disagreements) / len(a_noncorrect), 4) if a_noncorrect else None,
        "common_mode_errors": len(common_mode),
        "adjudicator_damage": len(damage),
        "errors_recovered": sum(row["historian_a"].get("identity_correct") is False and row["final"].get("identity_correct") is True for row in identity_rows),
        "new_errors_introduced": sum(row["historian_a"].get("identity_correct") is True and row["final"].get("identity_correct") is False and row.get("final_resolution_status") == "resolved" for row in identity_rows),
        "adjudication_cases": len(adjudications),
        "adjudication_decisions": dict(sorted(Counter(text(row.get("decision")) for row in valid_adj).items())),
        "adjudication_valid_outputs": len(valid_adj),
        "adjudication_contract_invalid": sum(row.get("contract_status") == "contract_invalid" for row in adjudications.values()),
        "adjudication_transport_unresolved": sum(row.get("contract_status") == "transport_unresolved" for row in adjudications.values()),
        "final_unresolved_identity_cases": sum(row.get("final_resolution_status") == "unresolved" for row in rows),
        "noncorrect_outcomes_recovered": sum(row["historian_a"].get("identity_correct") is not True and row["final"].get("identity_correct") is True for row in identity_rows),
        "candidate_only": True,
        "canonical_write_back": False,
    }
    document = {
        "schema": "sfh2-a2r-regression-evaluation-v1",
        "records": rows,
        "metrics": metrics,
        "gold_evaluation_only": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    return document, metrics
