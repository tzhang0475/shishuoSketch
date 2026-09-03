#!/usr/bin/env python3
"""Generate the offline SFH2.2-A2G Gold/ontology boundary audit.

This module intentionally has no provider, transport, or network dependency.
It reads the frozen A0 Gold, A2/A2R records, and A2 source packets, then
performs evaluation-only structural comparisons.  It never changes Gold,
historical records, or runtime identity decisions.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

try:  # Works both as a script and when imported by focused repository tests.
    from sfh2_a0.schemas import (
        CONFIDENCES,
        OCCURRENCE_ROLES,
        REFERENCE_TYPES,
        RELATIONS,
        SEMANTIC_KINDS,
    )
except ModuleNotFoundError:  # pragma: no cover - import-mode compatibility
    from scripts.sfh2_a0.schemas import (
        CONFIDENCES,
        OCCURRENCE_ROLES,
        REFERENCE_TYPES,
        RELATIONS,
        SEMANTIC_KINDS,
    )


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/generated/sfh2-a2g"
A2_ROOT = ROOT / "data/generated/sfh2-a2"
A2R_ROOT = ROOT / "data/generated/sfh2-a2r"
GOLD_PATH = ROOT / "data/annotation/sfh2-a0-evaluation-gold.json"
SELECTION_PATH = ROOT / "data/annotation/sfh2-a0-selection.json"
PACKETS_PATH = A2_ROOT / "case-packets.json"
SCHEMA_PATH = ROOT / "scripts/sfh2_a0/schemas.py"
PROMPT_PATH = ROOT / "scripts/sfh2_a0/pipeline.py"
BASELINE_COMMIT = "57af9d9bb4b418b15cc9b5aff7f4b2390d8c7608"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def text(value: Any) -> str:
    return str(value or "").strip()


def record_from(row: Mapping[str, Any] | None, key: str = "record") -> dict[str, Any] | None:
    if not isinstance(row, Mapping):
        return None
    value = row.get(key)
    # A2/A2R cache rows expose ``valid`` for their provider records.  A2R
    # final rows instead expose the selected semantic record directly.  The
    # latter is still frozen input for this audit; treating its absent
    # ``valid`` marker as invalid would erase every final interpretation from
    # the comparison.  This is a record-shape distinction, not a semantic
    # decision.
    is_valid = row.get("valid") is True or (
        key == "selected_record" and isinstance(value, Mapping)
    )
    return copy.deepcopy(value) if is_valid and isinstance(value, Mapping) else None


def semantic_record(record: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Return the complete structured semantic record.

    Explanations are retained because they are part of the frozen semantic
    output contract and are concise evidence-grounded text, not hidden
    reasoning.  No provider envelope or transport metadata is copied.
    """

    return copy.deepcopy(dict(record)) if isinstance(record, Mapping) else None


def stage_view(row: Mapping[str, Any] | None, *, record_key: str = "record") -> dict[str, Any]:
    row = row if isinstance(row, Mapping) else {}
    record = record_from(row, record_key)
    return {
        "valid": record is not None,
        "contract_status": row.get("contract_status"),
        "semantic_record": semantic_record(record),
        "source": row.get("primary_source") or row.get("selected_record_source"),
        "final_state": row.get("final_state"),
        "failure_stage": row.get("failure_stage"),
    }


def stage_kind(row: Mapping[str, Any] | None, *, record_key: str = "record") -> str | None:
    record = record_from(row, record_key)
    return text(record.get("semantic_kind")) if isinstance(record, Mapping) else None


def stage_field(row: Mapping[str, Any] | None, path: str, *, record_key: str = "record") -> Any:
    record = record_from(row, record_key)
    if not isinstance(record, Mapping):
        return None
    if path.startswith("referent."):
        referent = record.get("referent")
        return referent.get(path.split(".", 1)[1]) if isinstance(referent, Mapping) else None
    if path.startswith("discourse."):
        discourse = record.get("discourse")
        return discourse.get(path.split(".", 1)[1]) if isinstance(discourse, Mapping) else None
    return record.get(path)


def source_layers(packet: Mapping[str, Any]) -> list[str]:
    return sorted({
        text(row.get("source_layer"))
        for row in packet.get("source_evidence", []) or []
        if isinstance(row, Mapping) and text(row.get("source_layer"))
    })


def source_context(packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "story_context": copy.deepcopy(packet.get("story_context", {})),
        "target": copy.deepcopy(packet.get("target", {})),
        "source_evidence": copy.deepcopy(packet.get("source_evidence", [])),
        "validated_local_mentions": copy.deepcopy(packet.get("validated_local_mentions", [])),
    }


def identity_joint_failure(evaluation_row: Mapping[str, Any]) -> bool:
    """Count both-wrong identity outcomes without requiring string agreement."""

    if evaluation_row.get("historical_identity_evaluable") is not True:
        return False
    a = evaluation_row.get("historian_a")
    b = evaluation_row.get("historian_b")
    return (
        isinstance(a, Mapping)
        and isinstance(b, Mapping)
        and a.get("identity_correct") is False
        and b.get("identity_correct") is False
    )


def _valid_stage_names(
    a_row: Mapping[str, Any],
    b_row: Mapping[str, Any],
    final_row: Mapping[str, Any],
) -> list[tuple[str, Mapping[str, Any], str]]:
    return [
        ("historian_a", a_row, "record"),
        ("historian_b", b_row, "record"),
        ("final", final_row, "selected_record"),
    ]


def boundary_observation(
    gold: Mapping[str, Any],
    a_row: Mapping[str, Any],
    b_row: Mapping[str, Any],
    final_row: Mapping[str, Any],
) -> dict[str, Any]:
    expected_kind = text(gold.get("expected_semantic_kind"))
    kinds = {
        name: stage_kind(row, record_key=record_key)
        for name, row, record_key in _valid_stage_names(a_row, b_row, final_row)
    }
    mismatches = [
        name for name, kind in kinds.items()
        if kind is not None and expected_kind and kind != expected_kind
    ]
    valid_kinds = [kind for kind in kinds.values() if kind is not None]
    # This is a generic ontology-boundary signal: all available semantic
    # hypotheses classify the target as an office while frozen Gold classifies
    # it as a person.  It does not choose which interpretation is correct.
    apparent_boundary_conflict = (
        expected_kind == "historical_person"
        and bool(valid_kinds)
        and all(kind == "office" for kind in valid_kinds)
    )
    return {
        "expected_semantic_kind": expected_kind or None,
        "stage_semantic_kinds": kinds,
        "stage_kind_mismatch": mismatches,
        "apparent_gold_ontology_boundary_conflict": apparent_boundary_conflict,
        "boundary_type": (
            "historical_person_vs_office"
            if apparent_boundary_conflict
            else None
        ),
        "ontology_authority_note": (
            "The current prompt distinguishes an office entity from a title "
            "that semantically identifies a person; this record is surfaced "
            "for human review and no replacement Gold is inferred."
            if apparent_boundary_conflict
            else None
        ),
    }


def expected_field_observations(
    gold: Mapping[str, Any],
    a_row: Mapping[str, Any],
    b_row: Mapping[str, Any],
    final_row: Mapping[str, Any],
) -> dict[str, Any]:
    fields = {
        "semantic_kind": "expected_semantic_kind",
        "referent.surface_form": "expected_referent_surface",
        "referent.canonical_hint": "expected_canonical_hint",
        "occurrence_role": "expected_role",
        "attribute_type": "expected_attribute_type",
        "attribute_value": "expected_attribute_value",
        "bearer_hint": "expected_bearer",
    }
    observations: dict[str, Any] = {}
    for field, gold_key in fields.items():
        expected = gold.get(gold_key)
        if expected is None or expected == "":
            continue
        values = {}
        for name, row, record_key in _valid_stage_names(a_row, b_row, final_row):
            value = stage_field(row, field, record_key=record_key)
            values[name] = {
                "value": value,
                "matches_frozen_gold": value == expected,
            }
        observations[field] = {
            "gold_field": gold_key,
            "expected": expected,
            "stage_values": values,
        }
    return observations


def review_reasons(
    gold: Mapping[str, Any],
    evaluation_row: Mapping[str, Any],
    boundary: Mapping[str, Any],
    a_row: Mapping[str, Any],
    b_row: Mapping[str, Any],
    final_row: Mapping[str, Any],
) -> list[str]:
    reasons: list[str] = []
    if boundary.get("apparent_gold_ontology_boundary_conflict"):
        reasons.append("gold_ontology_boundary_candidate")
    for stage_name in ("historian_a", "historian_b", "final"):
        dimensions = evaluation_row.get(stage_name)
        if isinstance(dimensions, Mapping):
            false_fields = sorted(
                field for field, value in dimensions.items() if value is False
            )
            if false_fields:
                reasons.append(
                    "frozen_gold_dimension_mismatch:"
                    + stage_name
                    + ":"
                    + ",".join(false_fields)
                )
    for stage_name, row, record_key in _valid_stage_names(a_row, b_row, final_row):
        if record_from(row, record_key) is None:
            reasons.append("contract_or_record_invalid:" + stage_name)
    expected_role = text(gold.get("expected_role"))
    if expected_role:
        roles = {
            name: stage_field(row, "occurrence_role", record_key=record_key)
            for name, row, record_key in _valid_stage_names(a_row, b_row, final_row)
        }
        if any(value not in {None, expected_role} for value in roles.values()):
            reasons.append("occurrence_role_requires_review")
    return sorted(set(reasons))


def build_case_audit(
    case: Mapping[str, Any],
    gold: Mapping[str, Any],
    packet: Mapping[str, Any],
    a_row: Mapping[str, Any],
    b_row: Mapping[str, Any],
    final_row: Mapping[str, Any],
    evaluation_row: Mapping[str, Any],
) -> dict[str, Any]:
    boundary = boundary_observation(gold, a_row, b_row, final_row)
    reasons = review_reasons(gold, evaluation_row, boundary, a_row, b_row, final_row)
    return {
        "case_id": case.get("case_id"),
        "story_id": case.get("story_id"),
        "surface": case.get("surface"),
        "source_context": source_context(packet),
        "current_gold_fields": copy.deepcopy(gold),
        "historian_a": stage_view(a_row),
        "historian_b": stage_view(b_row),
        "final_a2r": stage_view(final_row, record_key="selected_record"),
        "dimension_evaluation_from_a2r": {
            "historian_a": copy.deepcopy(evaluation_row.get("historian_a", {})),
            "historian_b": copy.deepcopy(evaluation_row.get("historian_b", {})),
            "final": copy.deepcopy(evaluation_row.get("final", {})),
        },
        "gold_ontology_boundary": boundary,
        "gold_field_observations": expected_field_observations(
            gold, a_row, b_row, final_row
        ),
        "source_layers": source_layers(packet),
        "review_required": bool(reasons),
        "review_reasons": reasons,
        "replacement_historical_answer": None,
        "gold_mutated": False,
    }


def build_role_audit(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    role_rows: list[dict[str, Any]] = []
    for row in rows:
        gold = row.get("current_gold_fields", {})
        expected = text(gold.get("expected_role"))
        if not expected:
            continue
        stage_values = {}
        for stage_name in ("historian_a", "historian_b", "final_a2r"):
            stage = row.get(stage_name, {})
            record = stage.get("semantic_record") if isinstance(stage, Mapping) else None
            stage_values[stage_name] = (
                record.get("occurrence_role")
                if isinstance(record, Mapping)
                else None
            )
        nonmatching = [
            name for name, value in stage_values.items()
            if value is not None and value != expected
        ]
        if not nonmatching:
            finding = "consistent_with_frozen_gold"
        elif len(set(value for value in stage_values.values() if value is not None)) > 1:
            finding = "stage_disagreement_requires_human_review"
        else:
            finding = "model_semantic_error_candidate"
        role_rows.append({
            "case_id": row.get("case_id"),
            "story_id": row.get("story_id"),
            "surface": row.get("surface"),
            "gold_role": expected,
            "stage_roles": stage_values,
            "source_layers": row.get("source_layers", []),
            "source_evidence_ids": [
                item.get("evidence_id")
                for item in row.get("source_context", {}).get("source_evidence", [])
                if isinstance(item, Mapping) and item.get("evidence_id")
            ],
            "nonmatching_stages": nonmatching,
            "finding": finding,
            "historical_answer_replacement": None,
        })
    return {
        "schema": "sfh2-a2g-occurrence-role-audit-v1",
        "gold_role_case_count": len(role_rows),
        "records": role_rows,
        "gold_mutated": False,
    }


def primary_disagreement_category(comparison: Mapping[str, Any]) -> str:
    classes = set(comparison.get("disagreement_classes", []) or [])
    if not comparison.get("substantive_disagreement"):
        return "metadata_only_difference" if comparison.get("metadata_only_difference") else "no_disagreement"
    if "contract_validity_disagreement" in classes:
        return "contract_validity_critical"
    if {"identity_disagreement", "semantic_kind_disagreement"} & classes:
        return "identity_or_semantic_kind_critical"
    if "occurrence_role_disagreement" in classes:
        return "occurrence_role_critical"
    if {"discourse_disagreement", "relation_disagreement"} & classes:
        return "discourse_or_relation_only"
    return "other_substantive"


def build_disagreement_taxonomy(comparison_rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    for row in comparison_rows:
        category = primary_disagreement_category(row)
        counts[category] += 1
        for label in row.get("disagreement_classes", []) or []:
            class_counts[text(label)] += 1
        records.append({
            "case_id": row.get("case_id"),
            "cohort": row.get("cohort"),
            "story_id": row.get("story_id"),
            "surface": row.get("surface"),
            "substantive_disagreement": row.get("substantive_disagreement") is True,
            "metadata_only_difference": row.get("metadata_only_difference") is True,
            "disagreement_classes": copy.deepcopy(row.get("disagreement_classes", [])),
            "semantic_fields": copy.deepcopy(row.get("semantic_fields", [])),
            "substantive_fields": copy.deepcopy(row.get("substantive_fields", [])),
            "primary_category": category,
        })
    substantive_count = sum(
        row.get("substantive_disagreement") is True for row in comparison_rows
    )
    return {
        "schema": "sfh2-a2g-disagreement-taxonomy-v1",
        "source": "data/generated/sfh2-a2r/ab-comparison.json",
        "total_comparisons": len(comparison_rows),
        "substantive_disagreement_count": substantive_count,
        "metadata_only_difference_count": sum(
            row.get("metadata_only_difference") is True for row in comparison_rows
        ),
        "primary_category_counts": dict(sorted(counts.items())),
        "requested_buckets": {
            "identity_or_semantic_kind_critical": counts["identity_or_semantic_kind_critical"],
            "occurrence_role_critical": counts["occurrence_role_critical"],
            "discourse_or_relation_only": counts["discourse_or_relation_only"],
            "metadata_only_difference_within_substantive": 0,
            "contract_validity_critical": counts["contract_validity_critical"],
        },
        "raw_class_counts": dict(sorted(class_counts.items())),
        "records": records,
        "identity_equivalence_inferred_by_python": False,
    }


def protected_input_hashes() -> dict[str, str]:
    paths = [
        GOLD_PATH,
        SELECTION_PATH,
        PACKETS_PATH,
        A2_ROOT / "historian-a-cache-index.json",
        A2_ROOT / "historian-b-results.json",
        A2_ROOT / "final-results.json",
        A2R_ROOT / "regression-evaluation.json",
        A2R_ROOT / "selection-matrix.json",
        A2R_ROOT / "ab-comparison.json",
        A2R_ROOT / "final-results.json",
        ROOT / "data/derived/sc1-site.json",
        ROOT / "data/derived/sc1-current-site.json",
        ROOT / "site/src/generated/sc1-site.json",
        ROOT / "site/src/generated/sc1-current-site.json",
    ]
    return {str(path.relative_to(ROOT)): file_hash(path) for path in paths}


def build_metrics(
    case_audits: list[Mapping[str, Any]],
    role_audit: Mapping[str, Any],
    taxonomy: Mapping[str, Any],
    regression_evaluation: Mapping[str, Any],
    comparison_rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    joint_cases = [
        row.get("case_id")
        for row in regression_evaluation.get("records", [])
        if isinstance(row, Mapping) and identity_joint_failure(row)
    ]
    eval_metrics = regression_evaluation.get("metrics", {})
    return {
        "schema": "sfh2-a2g-metrics-v1",
        "provider_calls": 0,
        "provider_calls_allowed": 0,
        "case_count": len(case_audits),
        "historical_identity_evaluable": sum(
            row.get("historical_identity_evaluable") is True
            for row in regression_evaluation.get("records", [])
            if isinstance(row, Mapping)
        ),
        "gold_evaluable_role_case_count": role_audit.get("gold_role_case_count", 0),
        "gold_ontology_boundary_conflict_count": sum(
            row.get("gold_ontology_boundary", {}).get(
                "apparent_gold_ontology_boundary_conflict"
            ) is True
            for row in case_audits
        ),
        "gold_ontology_boundary_conflict_cases": [
            row.get("case_id")
            for row in case_audits
            if row.get("gold_ontology_boundary", {}).get(
                "apparent_gold_ontology_boundary_conflict"
            ) is True
        ],
        "review_required_case_count": sum(
            row.get("review_required") is True for row in case_audits
        ),
        "joint_identity_failure_count": len(joint_cases),
        "joint_identity_failure_cases": joint_cases,
        "a2r_substantive_disagreement_count": sum(
            row.get("substantive_disagreement") is True for row in comparison_rows
        ),
        "a2r_disagreement_taxonomy": taxonomy.get("primary_category_counts", {}),
        "a2r_requested_disagreement_buckets": taxonomy.get("requested_buckets", {}),
        "historian_a_identity": copy.deepcopy(eval_metrics.get("historian_a_identity", {})),
        "historian_b_identity": copy.deepcopy(eval_metrics.get("historian_b_identity", {})),
        "final_identity": copy.deepcopy(eval_metrics.get("final_identity", {})),
        "dimension_counts_from_a2r": copy.deepcopy(eval_metrics.get("dimension_counts", {})),
        "a2r_metrics_reference": "data/generated/sfh2-a2r/regression-evaluation.json",
        "joint_failure_definition": (
            "historian_a.identity_correct is false AND "
            "historian_b.identity_correct is false for an identity-evaluable case; "
            "A/B string disagreement does not cancel the joint failure."
        ),
        "gold_mutated": False,
        "provider_or_network_used": False,
    }


def build_outputs() -> dict[str, Any]:
    gold_doc = load_json(GOLD_PATH)
    selection_doc = load_json(SELECTION_PATH)
    packet_doc = load_json(PACKETS_PATH)
    a_doc = load_json(A2R_ROOT / "historian-a-cache-index.json")
    b_doc = load_json(A2R_ROOT / "historian-b-cache-reuse.json")
    final_doc = load_json(A2R_ROOT / "final-results.json")
    evaluation_doc = load_json(A2R_ROOT / "regression-evaluation.json")
    comparison_doc = load_json(A2R_ROOT / "ab-comparison.json")

    selection_cases = [
        copy.deepcopy(row)
        for row in selection_doc.get("cases", [])
        if isinstance(row, Mapping)
    ]
    if len(selection_cases) != 20:
        raise ValueError(f"expected 20 frozen A0 cases, found {len(selection_cases)}")
    selection_ids = [text(row.get("case_id")) for row in selection_cases]
    gold_by_story_surface = {
        (text(row.get("story_id")), text(row.get("surface"))): row
        for row in gold_doc.get("records", [])
        if isinstance(row, Mapping)
    }
    packets = {
        text(row.get("case_id")): row.get("packet", {})
        for row in packet_doc.get("packets", [])
        if isinstance(row, Mapping) and row.get("cohort") == "regression"
    }
    a_rows = {
        text(row.get("case_id")): row
        for row in a_doc.get("records", [])
        if isinstance(row, Mapping) and row.get("cohort") == "regression"
    }
    b_rows = {
        text(row.get("case_id")): row
        for row in b_doc.get("records", [])
        if isinstance(row, Mapping) and row.get("cohort") == "regression"
    }
    final_rows = {
        text(row.get("case_id")): row
        for row in final_doc.get("records", [])
        if isinstance(row, Mapping)
    }
    evaluation_rows = {
        text(row.get("case_id")): row
        for row in evaluation_doc.get("records", [])
        if isinstance(row, Mapping)
    }
    comparison_rows = [
        copy.deepcopy(row)
        for row in comparison_doc.get("records", [])
        if isinstance(row, Mapping)
    ]

    audits: list[dict[str, Any]] = []
    for case in selection_cases:
        case_id = text(case.get("case_id"))
        key = (text(case.get("story_id")), text(case.get("surface")))
        if case_id not in packets or case_id not in a_rows or case_id not in b_rows:
            raise ValueError(f"missing frozen A2 source row for {case_id}")
        if case_id not in final_rows or case_id not in evaluation_rows:
            raise ValueError(f"missing frozen A2R result row for {case_id}")
        audit = build_case_audit(
            case,
            gold_by_story_surface.get(key, {}),
            packets[case_id],
            a_rows[case_id],
            b_rows[case_id],
            final_rows[case_id],
            evaluation_rows[case_id],
        )
        audit["historical_identity_evaluable"] = (
            evaluation_rows[case_id].get("historical_identity_evaluable") is True
        )
        audits.append(audit)

    role_audit = build_role_audit(audits)
    taxonomy = build_disagreement_taxonomy(comparison_rows)
    metrics = build_metrics(
        audits, role_audit, taxonomy, evaluation_doc, comparison_rows
    )
    selection_hash = selection_doc.get("selection_hash")
    ontology_snapshot = {
        "schema_source": str(SCHEMA_PATH.relative_to(ROOT)),
        "schema_file_sha256": file_hash(SCHEMA_PATH),
        "primary_prompt_source": str(PROMPT_PATH.relative_to(ROOT)),
        "primary_prompt_file_sha256": file_hash(PROMPT_PATH),
        "semantic_kinds": sorted(SEMANTIC_KINDS),
        "reference_types": sorted(REFERENCE_TYPES),
        "occurrence_roles": sorted(OCCURRENCE_ROLES),
        "relations": sorted(RELATIONS),
        "confidences": sorted(CONFIDENCES),
        "field_boundary_contract": {
            "target_surface": "record.surface is the exact supplied occurrence surface",
            "referent_surface": "referent.surface_form is the target reference form",
            "canonical_hint": "referent.canonical_hint is the supported normalized historical referent",
            "office_boundary": "use office when the referred entity itself is an office; a title that identifies a person remains historical_person",
            "attribute_boundary": "person_attribute carries attribute_type/attribute_value and bearer_hint; it is not an independent Person",
        },
    }
    architecture = {
        "schema": "sfh2-a2g-architecture-freeze-v1",
        "stage": "SFH2.2-A2G",
        "baseline_commit": BASELINE_COMMIT,
        "mode": "offline_evaluation_only",
        "provider_calls": 0,
        "gold_in_provider_prompt": False,
        "gold_used_for": "post-inference evaluation and ontology audit only",
        "selection_path": str(SELECTION_PATH.relative_to(ROOT)),
        "selection_hash": selection_hash,
        "selection_case_count": len(selection_cases),
        "a2r_sources": {
            "historian_a": str((A2R_ROOT / "historian-a-cache-index.json").relative_to(ROOT)),
            "historian_b": str((A2R_ROOT / "historian-b-cache-reuse.json").relative_to(ROOT)),
            "final": str((A2R_ROOT / "final-results.json").relative_to(ROOT)),
        },
        "ontology": ontology_snapshot,
        "identity_equivalence_inferred_by_python": False,
        "historical_answer_replacements": 0,
    }
    gold_audit = {
        "schema": "sfh2-a2g-gold-ontology-audit-v1",
        "stage": "SFH2.2-A2G",
        "selection_hash": selection_hash,
        "gold_source": str(GOLD_PATH.relative_to(ROOT)),
        "gold_source_sha256": file_hash(GOLD_PATH),
        "ontology_authority": ontology_snapshot,
        "records": audits,
        "review_required_count": sum(row["review_required"] for row in audits),
        "apparent_gold_ontology_boundary_conflict_count": metrics[
            "gold_ontology_boundary_conflict_count"
        ],
        "gold_mutated": False,
        "provider_calls": 0,
    }
    review_candidates = {
        "schema": "sfh2-a2g-gold-review-candidates-v1",
        "purpose": "human review routing only; no replacement Gold is proposed",
        "records": [
            {
                "case_id": row["case_id"],
                "story_id": row["story_id"],
                "surface": row["surface"],
                "review_required": True,
                "review_reasons": row["review_reasons"],
                "affected_dimensions": sorted({
                    field
                    for stage in row["dimension_evaluation_from_a2r"].values()
                    if isinstance(stage, Mapping)
                    for field, value in stage.items()
                    if value is False
                }),
                "gold_ontology_boundary": row["gold_ontology_boundary"],
                "source_evidence_ids": [
                    item.get("evidence_id")
                    for item in row["source_context"].get("source_evidence", [])
                    if isinstance(item, Mapping) and item.get("evidence_id")
                ],
                "replacement_historical_answer": None,
            }
            for row in audits
            if row["review_required"]
        ],
        "count": sum(row["review_required"] for row in audits),
        "gold_mutated": False,
    }
    return {
        "architecture-freeze.json": architecture,
        "gold-ontology-audit.json": gold_audit,
        "gold-review-candidates.json": review_candidates,
        "occurrence-role-audit.json": role_audit,
        "disagreement-taxonomy.json": taxonomy,
        "metrics.json": metrics,
        "recommendation.json": {
            "schema": "sfh2-a2g-recommendation-v1",
            "recommendation": "gold_review_required",
            "reason": (
                "The frozen Gold has an explicit historical_person versus "
                "office boundary conflict candidate for 太丘長, and the "
                "corrected joint identity metric finds one both-wrong case. "
                "Human semantic review must decide whether Gold or the model "
                "interpretation should be qualified; this audit changes neither."
            ),
            "human_gold_promotion_required": True,
            "provider_calls": 0,
            "gold_mutated": False,
            "next_stage": "Do not enter SFH2.2-F until Gold/ontology review is resolved.",
        },
        "input-hashes.json": {
            "schema": "sfh2-a2g-input-hashes-v1",
            "files": protected_input_hashes(),
            "selection_hash": selection_hash,
            "gold_mutated": False,
        },
    }


def run() -> Path:
    outputs = build_outputs()
    for name, value in outputs.items():
        write_json(OUT / name, value)
    return OUT


if __name__ == "__main__":
    print(f"wrote offline SFH2.2-A2G audit to {run()}")
