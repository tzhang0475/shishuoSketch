"""Evaluation-only dimension bookkeeping for the A0R regression.

Gold labels are consumed here after inference.  Nothing in this module is
imported by provider payload construction or record realization.
"""

from __future__ import annotations

import collections
from typing import Any, Mapping

from .common import normalize, text
from .contracts import semantic_equal


def _record(row: Mapping[str, Any] | None, *, key: str = "record") -> Mapping[str, Any] | None:
    if not isinstance(row, Mapping):
        return None
    value = row.get(key)
    return value if isinstance(value, Mapping) else None


def gold_by_case(selection: Mapping[str, Any], gold: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    lookup = {
        (text(row.get("story_id")), text(row.get("surface"))): dict(row)
        for row in gold.get("records", []) or []
        if isinstance(row, Mapping)
    }
    return {
        text(case.get("case_id")): lookup.get((text(case.get("story_id")), text(case.get("surface"))), {})
        for case in selection.get("cases", []) or []
        if isinstance(case, Mapping)
    }


def _referent(record: Mapping[str, Any] | None) -> Mapping[str, Any]:
    value = record.get("referent") if isinstance(record, Mapping) else None
    return value if isinstance(value, Mapping) else {}


def dimensions(record: Mapping[str, Any] | None, gold: Mapping[str, Any]) -> dict[str, bool | None]:
    """Compare independently observable fields to evaluation-only labels."""

    if not isinstance(record, Mapping) or not gold:
        return {
            "identity_correct": False,
            "semantic_kind_correct": False,
            "referent_surface_correct": False,
            "canonicalization_correct": False,
            "occurrence_role_correct": False,
            "discourse_correct": None,
            "relation_correct": None,
            "serialization_contract_correct": False,
        }
    referent = _referent(record)
    expected_kind = text(gold.get("expected_semantic_kind"))
    expected_surface = text(gold.get("expected_referent_surface"))
    expected_hint = text(gold.get("expected_canonical_hint"))
    expected_role = text(gold.get("expected_role"))
    kind_ok = text(record.get("semantic_kind")) == expected_kind if expected_kind else None
    surface_ok = normalize(referent.get("surface_form")) == normalize(expected_surface) if expected_surface else None
    canonical_ok = normalize(referent.get("canonical_hint")) == normalize(expected_hint) if expected_hint else None
    role_ok = text(record.get("occurrence_role")) == expected_role if expected_role else None
    attr_ok: bool | None = True
    if expected_kind == "person_attribute":
        attr_ok = (
            text(record.get("attribute_type")) == text(gold.get("expected_attribute_type"))
            and normalize(record.get("attribute_value")) == normalize(gold.get("expected_attribute_value"))
            and normalize(record.get("bearer_hint")) == normalize(gold.get("expected_bearer"))
        )
    forbidden = {normalize(value) for value in gold.get("must_not_resolve_to", []) or []}
    forbidden_hit = normalize(referent.get("canonical_hint")) in forbidden
    candidate = record.get("_evaluation_candidate") if isinstance(record.get("_evaluation_candidate"), Mapping) else {}
    forbidden_hit = forbidden_hit or normalize(candidate.get("display_name")) in forbidden
    # This is an evaluation comparison against reviewed gold and the realized
    # candidate, not an identity inference rule.  Accepted identity aliases
    # could be supplied by a future evaluation authority without changing the
    # runtime path.
    identity_ok = bool(canonical_ok) and not forbidden_hit if canonical_ok is not None else (not forbidden_hit if expected_kind in {"person_attribute", "collective", "structural"} else None)
    return {
        "identity_correct": identity_ok,
        "semantic_kind_correct": kind_ok,
        "referent_surface_correct": surface_ok,
        "canonicalization_correct": canonical_ok,
        "occurrence_role_correct": role_ok,
        "discourse_correct": None,
        "relation_correct": None,
        "serialization_contract_correct": True,
        "attribute_fields_correct": attr_ok,
    }


def _strict(dims: Mapping[str, bool | None]) -> bool:
    relevant = [
        dims.get("semantic_kind_correct"),
        dims.get("referent_surface_correct"),
        dims.get("canonicalization_correct"),
        dims.get("occurrence_role_correct"),
        dims.get("attribute_fields_correct"),
    ]
    return all(value is not False for value in relevant)


def evaluate(
    cases: list[Mapping[str, Any]],
    gold_by_case_map: Mapping[str, Mapping[str, Any]],
    p1: Mapping[str, Mapping[str, Any]],
    p2: Mapping[str, Mapping[str, Any]],
    p3: Mapping[str, Mapping[str, Any]],
    finals: list[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    final_by_case = {text(row.get("case_id")): row for row in finals}
    rows: list[dict[str, Any]] = []
    for case in cases:
        case_id = text(case.get("case_id"))
        gold = dict(gold_by_case_map.get(case_id, {}))
        p1_record = _record(p1.get(case_id))
        p2_record = _record(p2.get(case_id), key="effective_record")
        p3_record = _record(p3.get(case_id), key="selected_record")
        final = final_by_case.get(case_id, {})
        final_record = final.get("selected_record") if isinstance(final.get("selected_record"), Mapping) else None
        p1_dims = dimensions(p1_record, gold)
        p2_dims = dimensions(p2_record, gold)
        p3_dims = dimensions(p3_record, gold)
        final_dims = dimensions(final_record, gold)
        candidate = final.get("selected_candidate") if isinstance(final.get("selected_candidate"), Mapping) else None
        if final_record is not None:
            final_record_for_eval = dict(final_record)
            final_record_for_eval["_evaluation_candidate"] = candidate or {}
            final_dims = dimensions(final_record_for_eval, gold)
        final_dims["serialization_contract_correct"] = bool(final.get("candidate_only") is True and final.get("canonical_write_back") is False)
        allow_abstention = bool(gold.get("allow_abstention")) and final.get("final_state") == "review_required"
        strict = _strict(final_dims) or allow_abstention
        historical_identity_evaluable = text(gold.get("expected_semantic_kind")) == "historical_person" and bool(text(gold.get("expected_canonical_hint")))
        identity_ok = final_dims.get("identity_correct")
        if allow_abstention:
            identity_ok = True
        final_dims["identity_correct"] = identity_ok
        rows.append({
            "case_id": case_id,
            "story_id": case.get("story_id"),
            "surface": case.get("surface"),
            "gold": gold,
            "pass1_answer": p1_record,
            "pass1_dimensions": p1_dims,
            "pass1_strict_full_record_correct": _strict(p1_dims),
            "python_flags_after_pass1": (p1.get(case_id) or {}).get("consistency", {}),
            "pass2_action": text((p2.get(case_id) or {}).get("decision")),
            "pass2_effective_record": p2_record,
            "pass2_dimensions": p2_dims,
            "pass1_pass2_semantic_agreement": semantic_equal(p1_record, p2_record),
            "pass3_required": bool(final.get("pass3_required")),
            "pass3_decision": text((p3.get(case_id) or {}).get("decision")),
            "pass3_selected_record": p3_record,
            "pass3_dimensions": p3_dims,
            "final_answer": final_record,
            "final_candidate": candidate,
            "final_state": final.get("final_state"),
            "final_dimensions": final_dims,
            "final_strict_full_record_correct": strict,
            "historical_identity_evaluable": historical_identity_evaluable,
            "final_correct": strict,
            "candidate_only": True,
            "canonical_write_back": False,
        })
    def count_dimension(stage: str, field: str) -> tuple[int, int]:
        values = [row.get(stage, {}).get(field) for row in rows]
        evaluable = [value for value in values if value is not None]
        return sum(value is True for value in evaluable), len(evaluable)

    p1_errors = [row for row in rows if not row["pass1_strict_full_record_correct"]]
    final_errors = [row for row in rows if not row["final_strict_full_record_correct"]]
    final_identity_rows = [row for row in rows if row["historical_identity_evaluable"]]
    final_identity_correct = sum(row["final_dimensions"].get("identity_correct") is True for row in final_identity_rows)
    p1_identity_correct = sum(row["pass1_dimensions"].get("identity_correct") is True for row in final_identity_rows)
    final_identity_wrong_high = sum(
        row["final_dimensions"].get("identity_correct") is False
        and text((row.get("final_answer") or {}).get("confidence")) == "high"
        for row in final_identity_rows
    )
    pass1_correct = sum(row["pass1_strict_full_record_correct"] for row in rows)
    final_correct = sum(row["final_strict_full_record_correct"] for row in rows)
    metrics: dict[str, Any] = {
        "case_count": len(rows),
        "pass1_strict_full_record_correct": pass1_correct,
        "pass1_strict_full_record_accuracy": round(pass1_correct / len(rows), 4) if rows else None,
        "final_strict_full_record_correct": final_correct,
        "final_strict_full_record_accuracy": round(final_correct / len(rows), 4) if rows else None,
        "historical_identity_correct": final_identity_correct,
        "historical_identity_evaluable": len(final_identity_rows),
        "historical_identity_accuracy": round(final_identity_correct / len(final_identity_rows), 4) if final_identity_rows else None,
        "pass1_historical_identity_correct": p1_identity_correct,
        "pass1_historical_identity_accuracy": round(p1_identity_correct / len(final_identity_rows), 4) if final_identity_rows else None,
        "errors_recovered": sum(not row["pass1_strict_full_record_correct"] and row["final_strict_full_record_correct"] for row in rows),
        "new_errors_introduced": sum(row["pass1_strict_full_record_correct"] and not row["final_strict_full_record_correct"] for row in rows),
        "reviewer_damage": sum(row["pass1_strict_full_record_correct"] and not row["final_strict_full_record_correct"] for row in rows),
        "identity_reviewer_damage": sum(row["pass1_dimensions"].get("identity_correct") is True and row["final_dimensions"].get("identity_correct") is False for row in final_identity_rows),
        "high_confidence_final_false_identities": final_identity_wrong_high,
        "pass1_errors": len(p1_errors),
        "final_errors": len(final_errors),
        "pass1_pass2_semantic_agreement": sum(row["pass1_pass2_semantic_agreement"] for row in rows),
        "pass1_pass2_semantic_agreement_rate": round(sum(row["pass1_pass2_semantic_agreement"] for row in rows) / len(rows), 4) if rows else None,
        "pass3_required": sum(row["pass3_required"] for row in rows),
        "pass3_abstentions": sum(row["pass3_decision"] == "abstain" for row in rows if row["pass3_required"]),
        "dimension_counts": {
            stage: {field: {"correct": count_dimension(stage, field)[0], "evaluable": count_dimension(stage, field)[1]} for field in ("identity_correct", "semantic_kind_correct", "referent_surface_correct", "canonicalization_correct", "occurrence_role_correct", "attribute_fields_correct", "serialization_contract_correct")}
            for stage in ("pass1_dimensions", "pass2_dimensions", "pass3_dimensions", "final_dimensions")
        },
        "final_state_distribution": dict(sorted(collections.Counter(text(row.get("final_state")) for row in rows).items())),
        "candidate_only": True,
        "canonical_write_back": False,
    }
    document = {
        "schema": "sfh2-a0r-dimension-evaluation-v1",
        "records": rows,
        "metrics": metrics,
        "gold_evaluation_only": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    return document, metrics
