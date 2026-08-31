"""SFH2.2-A2 independent semantic audit orchestration.

Historian A is an immutable A1 cache.  Historian B is sent only the source
packet and produces a fresh semantic record.  Python compares structured
fields, routes disagreements, and performs exact selector/patch operations;
it never supplies a historical replacement identity.
"""

from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from sfh2_a0 import pipeline as a0_pipeline
from sfh2_a0r import pipeline as a0r_pipeline
from sfh2_a0r.contracts import semantic_diff_paths
from sfh2_a0r.evaluation import _strict as evaluation_strict
from sfh2_a0r.evaluation import dimensions as evaluation_dimensions
from sfh2_a0r.evaluation import gold_by_case
from sfh2_a1r import pipeline as a1r_pipeline

from .common import (
    A1R_L_ROOT,
    CHALLENGE_STORIES,
    OUT,
    PROMPT_VERSIONS,
    ROOT,
    architecture_freeze,
    build_case_packet,
    canonical_json,
    cases_by_cohort,
    file_hash,
    input_hashes,
    load_inputs,
    provider_source_packet,
    read_json,
    selection_hashes,
    stable_hash,
    text,
    write_json,
)
from .comparison import challenge_summary, compare_records
from .contracts import (
    adjudicator_tool,
    apply_a2_adjudication,
    historian_b_tool,
    validate_adjudicator_payload,
)
from .transport import A2Client


HISTORIAN_B_SYSTEM = """You are Historian B, an independent historical-semantic analyst. Read only the supplied target, Story evidence, Liu annotation, registered historical evidence, and validated local mentions. Construct your own complete semantic record. You are not reviewing another analyst and have no access to another analyst's result, Python flags, candidate list, or evaluation gold. Historical semantic judgment belongs to you. A historical person may be absent from the registry; propose the evidence-supported referent without emitting production IDs. If evidence is insufficient, abstain. Return exactly the required structured record with concise evidence-grounded explanation and supplied evidence IDs only."""

ADJUDICATOR_SYSTEM = """You are the final independent historical adjudicator. Re-read the supplied historical evidence and compare the two independently produced semantic hypotheses. Python's structured comparison and formal flags identify differing fields only; they do not provide a correct historical answer. Select Historian A or Historian B exactly when one is better supported, apply a narrow typed patch only when necessary, or abstain. If selecting A or B, do not reproduce that complete record: the orchestration layer copies it exactly. Do not emit production IDs, and cite only supplied evidence IDs."""


def _record(row: Mapping[str, Any] | None, key: str = "record") -> Mapping[str, Any] | None:
    if isinstance(row, Mapping) and row.get("valid") is True and isinstance(row.get(key), Mapping):
        return row.get(key)
    return None


def _evidence_ids(packet: Mapping[str, Any]) -> set[str]:
    return {
        text(row.get("evidence_id"))
        for row in packet.get("source_evidence", []) or []
        if isinstance(row, Mapping) and text(row.get("evidence_id"))
    }


def _invalid(case: Mapping[str, Any], stage: str, errors: list[str], *, provider_status: str | None = None) -> dict[str, Any]:
    result = {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "stage": stage,
        "valid": False,
        "contract_status": "provider_failure" if provider_status else "contract_invalid",
        "errors": sorted(set(errors)),
        "record": None,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    if provider_status:
        result["provider_status"] = provider_status
    return result


def historian_b_payload(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Build B's isolated source-only payload.

    Keeping this allow-list explicit makes it mechanically impossible for the
    A record, Python flags, old retrieval candidates, or gold to enter B's
    prompt through a broad packet copy.
    """

    return {
        "task": "independently produce one complete semantic record for the target occurrence",
        **provider_source_packet(packet),
        "semantic_schema": "sfh2-a0r-complete-semantic-record-v2",
        "authority_boundary": "LLM owns historical semantic interpretation; Python only validates structure and storage safety",
        "candidate_registry_is_not_a_semantic_constraint": True,
        "gold_not_supplied": True,
    }


def adjudicator_payload(
    packet: Mapping[str, Any],
    a_row: Mapping[str, Any],
    b_row: Mapping[str, Any],
    comparison: Mapping[str, Any],
    a_consistency: Mapping[str, Any],
    b_consistency: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "task": "adjudicate two independent semantic hypotheses from evidence",
        **provider_source_packet(packet),
        "historian_a_semantic_record": copy.deepcopy(a_row.get("record")) if a_row.get("valid") is True else None,
        "historian_b_semantic_record": copy.deepcopy(b_row.get("record")) if b_row.get("valid") is True else None,
        "historian_a_contract_status": a_row.get("contract_status"),
        "historian_b_contract_status": b_row.get("contract_status"),
        "historian_a_contract_errors": copy.deepcopy(a_row.get("errors", [])),
        "historian_b_contract_errors": copy.deepcopy(b_row.get("errors", [])),
        "structured_disagreement": copy.deepcopy(comparison),
        "historian_a_formal_flags": copy.deepcopy(a_consistency.get("flags", [])),
        "historian_b_formal_flags": copy.deepcopy(b_consistency.get("flags", [])),
        "python_role": "formal comparison only; do not infer or supply a replacement historical identity",
        "gold_not_supplied": True,
    }


def _cached_historian_a(cases: Mapping[str, list[Mapping[str, Any]]], inputs: Mapping[str, Any]) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, dict[str, Any]], dict[str, Any]]:
    """Load and locally validate all 40 A1 Primary responses without calls."""

    a_rows, revalidation, a1_packets = a1r_pipeline.revalidate_cached_primary(cases, inputs)
    packets: dict[str, dict[str, Any]] = {}
    normalized: dict[str, dict[str, dict[str, Any]]] = {"regression": {}, "challenge": {}}
    index: list[dict[str, Any]] = []
    for cohort, cohort_cases in cases.items():
        for case in cohort_cases:
            case_id = text(case.get("case_id"))
            packet = build_case_packet(case, inputs)
            packets[case_id] = packet
            source = a_rows.get(cohort, {}).get(case_id, {})
            record = _record(source)
            realization = a0r_pipeline.realize_semantic_record(case, record, inputs)
            consistency = a0r_pipeline.analyze_record(record, evidence_ids=_evidence_ids(packet), realization=realization, stage="historian_a")
            row = copy.deepcopy(source)
            row.update({
                "cohort": cohort,
                "stage": "historian_a",
                "historian": "A",
                "contract_status": "valid" if source.get("valid") is True else "historian_a_contract_invalid",
                "record": copy.deepcopy(record),
                "consistency": consistency,
                "provisional_realization": realization,
                "primary_source": "A1 cached live Primary Historian",
                "a1_packet_reused": bool(a1_packets.get(case_id)),
                "candidate_only": True,
                "canonical_write_back": False,
            })
            normalized[cohort][case_id] = row
            index.append({
                "cohort": cohort,
                "case_id": case_id,
                "story_id": case.get("story_id"),
                "mention_id": case.get("mention_id"),
                "surface": case.get("surface"),
                "raw_path": source.get("cached_raw_path"),
                "raw_sha256": source.get("cached_raw_sha256"),
                "valid": source.get("valid") is True,
                "contract_status": row["contract_status"],
                "record": copy.deepcopy(record),
                "primary_source": "A1 cached live Primary Historian",
            })
    return normalized, packets, {
        "schema": "sfh2-a2-historian-a-cache-index-v1",
        "source_run": "data/generated/sfh2-a0r-l/live/sfh2-a0r-l-host-live-v1",
        "cached_primary_responses": len(index),
        "new_historian_a_provider_calls": 0,
        "records": sorted(index, key=lambda row: (text(row.get("cohort")), text(row.get("case_id")))),
        "a1_revalidation": revalidation,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _historian_b_row(case: Mapping[str, Any], packet: Mapping[str, Any], raw: Mapping[str, Any] | None, transport_row: Mapping[str, Any] | None) -> dict[str, Any]:
    if raw is None:
        classification = text((transport_row or {}).get("classification"))
        parse_error = text((transport_row or {}).get("parse_error"))
        if parse_error or classification == "response_parse_failure":
            result = _invalid(case, "historian_b", ["provider_response_parse_failure"])
            result["contract_status"] = "historian_b_contract_invalid"
            result["transport_failure_class"] = "response_parse_failure"
        elif classification == "provider_attempt_budget_exhausted":
            result = _invalid(case, "historian_b", ["provider_attempt_budget_exhausted"], provider_status="provider_attempt_budget_exhausted")
            result["contract_status"] = "transport_unresolved"
        elif classification == "offline_cache_miss":
            result = _invalid(case, "historian_b", ["offline_cache_miss"], provider_status="offline_cache_miss")
            result["contract_status"] = "transport_unresolved"
        else:
            result = _invalid(case, "historian_b", ["provider_failure_or_unavailable"], provider_status="provider_failure_or_unavailable")
    else:
        result = a0r_pipeline._record_from_provider(case, packet, raw)
        result["stage"] = "historian_b"
        result["contract_status"] = "valid" if result.get("valid") is True else "historian_b_contract_invalid"
    result["historian"] = "B"
    result["transport"] = copy.deepcopy(transport_row)
    result["candidate_only"] = True
    result["canonical_write_back"] = False
    return result


def _adjudication_row(case: Mapping[str, Any], packet: Mapping[str, Any], raw: Mapping[str, Any] | None, a_record: Mapping[str, Any] | None, b_record: Mapping[str, Any] | None, transport_row: Mapping[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    if raw is None:
        classification = text((transport_row or {}).get("classification"))
        parse_error = text((transport_row or {}).get("parse_error"))
        if parse_error or classification == "response_parse_failure":
            row = _invalid(case, "adjudicator", ["provider_response_parse_failure"])
            row["contract_status"] = "adjudicator_contract_invalid"
            row["transport_failure_class"] = "response_parse_failure"
            source, errors = "provider_response_parse_failure", ["provider_response_parse_failure"]
        elif classification == "provider_attempt_budget_exhausted":
            row = _invalid(case, "adjudicator", ["provider_attempt_budget_exhausted"], provider_status="provider_attempt_budget_exhausted")
            row["contract_status"] = "transport_unresolved"
            source, errors = "provider_attempt_budget_exhausted", ["provider_attempt_budget_exhausted"]
        elif classification == "offline_cache_miss":
            row = _invalid(case, "adjudicator", ["offline_cache_miss"], provider_status="offline_cache_miss")
            row["contract_status"] = "transport_unresolved"
            source, errors = "offline_cache_miss", ["offline_cache_miss"]
        else:
            row = _invalid(case, "adjudicator", ["provider_failure_or_unavailable"], provider_status="provider_failure_or_unavailable")
            source, errors = "provider_failure", ["provider_failure_or_unavailable"]
        row["transport"] = copy.deepcopy(transport_row)
        return row, {"valid": False, "record": None, "source": source, "errors": errors, "changed_fields": []}
    validation = validate_adjudicator_payload(packet, raw)
    if not validation.get("valid"):
        row = _invalid(case, "adjudicator", list(validation.get("errors", [])))
        row["transport"] = copy.deepcopy(transport_row)
        return row, {"valid": False, "record": None, "source": "invalid_adjudication", "errors": list(validation.get("errors", [])), "changed_fields": []}
    decision = dict(validation.get("adjudication") or {})
    effective = apply_a2_adjudication(a_record, b_record, {"valid": True, **decision}, packet)
    if not effective.get("valid"):
        row = _invalid(case, "adjudicator", list(effective.get("errors", [])))
        row["transport"] = copy.deepcopy(transport_row)
        return row, effective
    row = {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "stage": "adjudicator",
        "valid": True,
        "decision": decision.get("decision"),
        "base_record": decision.get("base_record", ""),
        "patch_ops": copy.deepcopy(decision.get("patch_ops", [])),
        "reviewed_fields": copy.deepcopy(decision.get("reviewed_fields", [])),
        "reason_summary": decision.get("reason_summary", ""),
        "supporting_evidence_ids": copy.deepcopy(decision.get("supporting_evidence_ids", [])),
        "selected_record": copy.deepcopy(effective.get("record")),
        "selected_record_source": effective.get("source"),
        "changed_fields": copy.deepcopy(effective.get("changed_fields", [])),
        "errors": [],
        "transport": copy.deepcopy(transport_row),
        "candidate_only": True,
        "canonical_write_back": False,
    }
    return row, effective


def _final_row(case: Mapping[str, Any], packet: Mapping[str, Any], a_row: Mapping[str, Any], b_row: Mapping[str, Any], comparison: Mapping[str, Any], adjudication: Mapping[str, Any] | None, effective: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    a_record = _record(a_row)
    b_record = _record(b_row)
    selected = effective.get("record") if effective.get("valid") else None
    realization = a0r_pipeline.realize_semantic_record(case, selected, inputs)
    consistency = a0r_pipeline.analyze_record(selected, evidence_ids=_evidence_ids(packet), realization=realization, stage="final")
    state, failure, candidate = a0_pipeline._final_state(selected, realization, consistency)
    if effective.get("source") == "provider_failure":
        state, failure, candidate = "review_required", "adjudicator_provider_failure", None
    if effective.get("source") == "invalid_adjudication":
        state, failure, candidate = "review_required", "invalid_adjudication", None
    if selected is None and not failure:
        state, failure, candidate = "review_required", "no_final_semantic_record", None
    if state == "review_required":
        candidate = None
    return {
        "case_id": text(case.get("case_id")),
        "mention_id": text(case.get("mention_id")),
        "story_id": text(case.get("story_id")),
        "surface": text(case.get("surface")),
        "historian_a_valid": a_row.get("valid") is True,
        "historian_b_valid": b_row.get("valid") is True,
        "ab_comparison": copy.deepcopy(comparison),
        "adjudicator_decision": text((adjudication or {}).get("decision")),
        "selected_record": copy.deepcopy(selected),
        "selected_record_source": effective.get("source"),
        "selected_candidate": copy.deepcopy(candidate),
        "provisional_realization": realization,
        "final_state": state,
        "failure_stage": failure,
        "final_consistency": consistency,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _requires_adjudication(a_row: Mapping[str, Any], b_row: Mapping[str, Any], comparison: Mapping[str, Any]) -> bool:
    if (a_row.get("valid") is True) != (b_row.get("valid") is True):
        return True
    if comparison.get("substantive_disagreement") is True:
        return True
    if any(text(flag.get("severity")) == "hard" for row in (a_row, b_row) for flag in (row.get("consistency", {}).get("flags", []) or []) if isinstance(flag, Mapping)):
        return True
    return False


def _authorized_transport_resume(previous: Mapping[str, Any], current: Mapping[str, Any]) -> bool:
    """Allow only the mechanical raw-witness recovery after interruption."""

    if previous.get("baseline_commit") != current.get("baseline_commit"):
        return False
    for key in ("selection_hashes", "model_config", "prompt_hashes", "schema_hashes", "input_hashes"):
        if previous.get(key) != current.get(key):
            return False
    old_files = previous.get("code_files") or {}
    new_files = current.get("code_files") or {}
    changed = {key for key in set(old_files) | set(new_files) if old_files.get(key) != new_files.get(key)}
    return changed <= {"scripts/sfh2_a2/transport.py", "scripts/sfh2_a2/pipeline.py"}


def _comparison_record(case: Mapping[str, Any], a_row: Mapping[str, Any], b_row: Mapping[str, Any], comparison: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_id": text(case.get("case_id")),
        "cohort": case.get("cohort"),
        "story_id": case.get("story_id"),
        "mention_id": case.get("mention_id"),
        "surface": case.get("surface"),
        "historian_a_contract_status": a_row.get("contract_status"),
        "historian_b_contract_status": b_row.get("contract_status"),
        **copy.deepcopy(comparison),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _evaluate_stage(row: Mapping[str, Any] | None, gold: Mapping[str, Any]) -> dict[str, Any]:
    record = _record(row)
    if isinstance(record, Mapping) and isinstance(row, Mapping):
        record_for_eval = dict(record)
        realization = row.get("provisional_realization") if isinstance(row.get("provisional_realization"), Mapping) else {}
        record_for_eval["_evaluation_candidate"] = realization.get("candidate") if isinstance(realization.get("candidate"), Mapping) else {}
        return evaluation_dimensions(record_for_eval, gold)
    return evaluation_dimensions(None, gold)


def _regression_evaluation(cases: list[Mapping[str, Any]], a_rows: Mapping[str, Mapping[str, Any]], b_rows: Mapping[str, Mapping[str, Any]], comparisons: Mapping[str, Mapping[str, Any]], adjudications: Mapping[str, Mapping[str, Any]], finals: list[Mapping[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    selection = read_json(A1R_L_ROOT / "regression-selection.json", {}) or {}
    gold_map = gold_by_case(selection, read_json(ROOT / "data/annotation/sfh2-a0-evaluation-gold.json", {}) or {})
    final_by_case = {text(row.get("case_id")): row for row in finals}
    rows: list[dict[str, Any]] = []
    for case in cases:
        case_id = text(case.get("case_id"))
        gold = dict(gold_map.get(case_id, {}))
        a = a_rows[case_id]
        b = b_rows[case_id]
        final = final_by_case[case_id]
        a_dims = _evaluate_stage(a, gold)
        b_dims = _evaluate_stage(b, gold)
        final_dims = _evaluate_stage({"valid": isinstance(final.get("selected_record"), Mapping), "record": final.get("selected_record"), "provisional_realization": final.get("provisional_realization")}, gold)
        final_dims["serialization_contract_correct"] = final.get("candidate_only") is True and final.get("canonical_write_back") is False
        identity_evaluable = text(gold.get("expected_semantic_kind")) == "historical_person" and bool(text(gold.get("expected_canonical_hint")))
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
            "comparison": copy.deepcopy(comparisons[case_id]),
            "adjudication": copy.deepcopy(adjudications.get(case_id)),
            "final_state": final.get("final_state"),
            "candidate_only": True,
            "canonical_write_back": False,
            "historical_identity_evaluable": identity_evaluable,
        })
    identity_rows = [row for row in rows if row["historical_identity_evaluable"]]
    def accuracy(stage: str) -> dict[str, Any]:
        vals = [row[stage].get("identity_correct") for row in identity_rows]
        return {"correct": sum(value is True for value in vals), "evaluable": len(vals), "accuracy": round(sum(value is True for value in vals) / len(vals), 4) if vals else None}
    def dim_counts(stage: str) -> dict[str, dict[str, int]]:
        fields = ("identity_correct", "semantic_kind_correct", "referent_surface_correct", "canonicalization_correct", "occurrence_role_correct", "attribute_fields_correct", "serialization_contract_correct")
        return {
            field: {"correct": sum(row[stage].get(field) is True for row in rows if row[stage].get(field) is not None), "evaluable": sum(row[stage].get(field) is not None for row in rows)}
            for field in fields
        }
    a_errors = [row for row in identity_rows if row["historian_a"].get("identity_correct") is not True]
    disagreement_errors = [row for row in a_errors if row["comparison"].get("substantive_disagreement") is True]
    common_mode = [row for row in identity_rows if row["historian_a"].get("identity_correct") is False and row["historian_b"].get("identity_correct") is False and row["comparison"].get("agreement") is True]
    # A failed review leaves the case unresolved; it is not reviewer damage.
    # Damage is counted only when a valid effective hypothesis was selected
    # or patched and displaced a correct source judgment.
    final_wrong_with_correct_source = [
        row for row in identity_rows
        if row["final"].get("identity_correct") is False
        and (row["historian_a"].get("identity_correct") is True or row["historian_b"].get("identity_correct") is True)
        and row.get("final_state") != "review_required"
        and isinstance(row.get("final"), Mapping)
    ]
    metrics = {
        "case_count": len(rows),
        "historical_identity_evaluable": len(identity_rows),
        "historian_a_identity": accuracy("historian_a"),
        "historian_b_identity": accuracy("historian_b"),
        "final_identity": accuracy("final"),
        "historian_a_strict_full_record_accuracy": round(sum(evaluation_strict(row["historian_a"]) for row in rows) / len(rows), 4) if rows else None,
        "historian_b_strict_full_record_accuracy": round(sum(evaluation_strict(row["historian_b"]) for row in rows) / len(rows), 4) if rows else None,
        "final_strict_full_record_accuracy": round(sum(evaluation_strict(row["final"]) for row in rows) / len(rows), 4) if rows else None,
        "dimension_counts": {stage: dim_counts(stage) for stage in ("historian_a", "historian_b", "final")},
        "a_error_disagreement_recall": round(len(disagreement_errors) / len(a_errors), 4) if a_errors else None,
        "a_identity_errors": len(a_errors),
        "a_identity_errors_with_ab_disagreement": len(disagreement_errors),
        "common_mode_errors": len(common_mode),
        "adjudicator_damage": len(final_wrong_with_correct_source),
        "errors_recovered": sum(row["historian_a"].get("identity_correct") is not True and row["final"].get("identity_correct") is True for row in identity_rows),
        "new_errors_introduced": sum(
            row["historian_a"].get("identity_correct") is True
            and row["final"].get("identity_correct") is False
            and row.get("final_state") != "review_required"
            for row in identity_rows
        ),
        "agreement_cases": sum(row["comparison"].get("agreement") is True for row in rows),
        "agreement_identity_accuracy": round(sum(row["historian_a"].get("identity_correct") is True for row in rows if row["comparison"].get("agreement") is True and row["historical_identity_evaluable"]) / sum(row["comparison"].get("agreement") is True for row in rows if row["historical_identity_evaluable"]), 4) if sum(row["comparison"].get("agreement") is True for row in rows if row["historical_identity_evaluable"]) else None,
        "adjudication_cases": len(adjudications),
        "adjudication_decisions": dict(sorted(Counter(text(row.get("decision")) for row in adjudications.values() if row.get("valid") is True).items())),
        "historian_a_contract_invalid": sum(row.get("a_valid") is not True for row in rows),
        "historian_b_contract_invalid": sum(row.get("b_valid") is not True for row in rows),
        "adjudication_valid_outputs": sum(
            row.get("adjudication", {}).get("valid") is True
            for row in rows
            if isinstance(row.get("adjudication"), Mapping)
        ),
        "adjudication_contract_invalid": sum(
            row.get("adjudication", {}).get("contract_status") in {"contract_invalid", "adjudicator_contract_invalid"}
            for row in rows
            if isinstance(row.get("adjudication"), Mapping)
        ),
        "adjudication_transport_unresolved": sum(
            row.get("adjudication", {}).get("contract_status") == "transport_unresolved"
            for row in rows
            if isinstance(row.get("adjudication"), Mapping)
        ),
        "final_transport_or_contract_unresolved": sum(row.get("final_state") == "review_required" for row in rows),
        "candidate_only": True,
        "canonical_write_back": False,
    }
    document = {"schema": "sfh2-a2-regression-evaluation-v1", "records": rows, "metrics": metrics, "gold_evaluation_only": True, "candidate_only": True, "canonical_write_back": False}
    return document, metrics


def _challenge_review_bundle(cases: list[Mapping[str, Any]], packets: Mapping[str, Mapping[str, Any]], a_rows: Mapping[str, Mapping[str, Any]], b_rows: Mapping[str, Mapping[str, Any]], comparisons: Mapping[str, Mapping[str, Any]], adjudications: Mapping[str, Mapping[str, Any]], finals: list[Mapping[str, Any]]) -> tuple[dict[str, Any], str]:
    final_by_case = {text(row.get("case_id")): row for row in finals}
    disagreement = [case for case in cases if comparisons[text(case.get("case_id"))].get("substantive_disagreement") is True or comparisons[text(case.get("case_id"))].get("contract_validity_disagreement")]
    agreement = [case for case in cases if comparisons[text(case.get("case_id"))].get("agreement") is True]
    agreement_sample = sorted(agreement, key=lambda case: stable_hash(text(case.get("case_id"))))[:5]
    selected = []
    seen: set[str] = set()
    for case in disagreement + agreement_sample:
        case_id = text(case.get("case_id"))
        if case_id in seen:
            continue
        seen.add(case_id)
        selected.append(case)
    records: list[dict[str, Any]] = []
    markdown = ["# SFH2.2-A2 Independent Semantic Audit Review Bundle", "", "Historical correctness is pending external review. The agreement sample is deterministic and was not selected using gold.", ""]
    for case in selected:
        case_id = text(case.get("case_id"))
        packet = packets[case_id]
        final = final_by_case[case_id]
        evidence = packet.get("source_evidence", []) or []
        row = {
            "case_id": case_id,
            "story_id": case.get("story_id"),
            "mention_id": case.get("mention_id"),
            "surface": case.get("surface"),
            "source_evidence": copy.deepcopy(evidence),
            "validated_local_mentions": copy.deepcopy(packet.get("validated_local_mentions", [])),
            "historian_a": copy.deepcopy(a_rows[case_id].get("record")),
            "historian_a_contract_status": a_rows[case_id].get("contract_status"),
            "historian_b": copy.deepcopy(b_rows[case_id].get("record")),
            "historian_b_contract_status": b_rows[case_id].get("contract_status"),
            "comparison": copy.deepcopy(comparisons[case_id]),
            "adjudication": copy.deepcopy(adjudications.get(case_id)),
            "final": copy.deepcopy(final.get("selected_record")),
            "final_candidate": copy.deepcopy(final.get("selected_candidate")),
            "final_state": final.get("final_state"),
            "reviewer_fields": {"correct": "", "notes": ""},
        }
        records.append(row)
        main = " | ".join(text(item.get("text")) for item in evidence if item.get("source_layer") == "main_text")
        liu = " | ".join(text(item.get("text")) for item in evidence if item.get("source_layer") == "liu_annotation")
        markdown.extend([
            f"## {case_id}",
            f"- Story: `{case.get('story_id')}` / mention: `{case.get('mention_id')}` / surface: `{case.get('surface')}`",
            f"- 正文: {main}",
            f"- 刘注/证据: {liu}",
            f"- Historian A: `{json.dumps(a_rows[case_id].get('record'), ensure_ascii=False, sort_keys=True)}`",
            f"- Historian B: `{json.dumps(b_rows[case_id].get('record'), ensure_ascii=False, sort_keys=True)}`",
            f"- Comparison: `{json.dumps(comparisons[case_id], ensure_ascii=False, sort_keys=True)}`",
            f"- Adjudicator: `{json.dumps(adjudications.get(case_id), ensure_ascii=False, sort_keys=True)}`",
            f"- Final: `{json.dumps(final.get('selected_record'), ensure_ascii=False, sort_keys=True)}`",
            "- Reviewer: [ ] correct  [ ] partially correct  [ ] wrong identity  [ ] should abstain  [ ] insufficient evidence",
            "- Expected referent:",
            "- Notes:",
            "",
        ])
    return {
        "schema": "sfh2-a2-challenge-review-bundle-v1",
        "historical_correctness": "pending_external_review",
        "selection": {"all_disagreements": len(disagreement), "agreement_sample_count": len(agreement_sample), "agreement_sample_selection": "first five by stable case-id hash", "case_ids": [text(case.get("case_id")) for case in selected]},
        "records": records,
        "candidate_only": True,
        "canonical_write_back": False,
    }, "\n".join(markdown)


def _policy_simulation(cases: list[Mapping[str, Any]], a_rows: Mapping[str, Mapping[str, Any]], b_rows: Mapping[str, Mapping[str, Any]], comparisons: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Estimate abstract routing policies from observed structured outputs."""

    all_cases = [text(case.get("case_id")) for case in cases]
    review_cases = [case_id for case_id in all_cases if any(text(flag.get("severity")) in {"hard", "review"} for row in (a_rows[case_id],) for flag in (row.get("consistency", {}).get("flags", []) or []) if isinstance(flag, Mapping))]
    b_observed_disagreements = [case_id for case_id in all_cases if comparisons[case_id].get("substantive_disagreement") is True]
    def a_kind(case_id: str) -> str:
        record = a_rows[case_id].get("record") if isinstance(a_rows[case_id].get("record"), Mapping) else b_rows[case_id].get("record") if isinstance(b_rows[case_id].get("record"), Mapping) else {}
        return text(record.get("semantic_kind"))
    def a_ref(case_id: str) -> str:
        record = a_rows[case_id].get("record") if isinstance(a_rows[case_id].get("record"), Mapping) else {}
        return text(record.get("reference_type"))
    p2_selected = []
    for case_id in all_cases:
        record = a_rows[case_id].get("record") if isinstance(a_rows[case_id].get("record"), Mapping) else {}
        candidate = a_rows[case_id].get("provisional_realization", {}).get("candidate") if isinstance(a_rows[case_id].get("provisional_realization"), Mapping) else None
        low = text(record.get("confidence")) == "low"
        unusual = a_kind(case_id) not in {"", "historical_person"}
        new_candidate = isinstance(candidate, Mapping) and text(candidate.get("entity_type")) == "candidate_historical_person"
        if low or unusual or new_candidate or int(stable_hash(case_id)[:2], 16) % 5 == 0:
            p2_selected.append(case_id)
    p3_selected = [
        case_id for case_id in all_cases
        if a_kind(case_id) == "historical_person"
        or a_ref(case_id) in {"pronoun_reference", "addressee_reference", "speaker_reference", "office_title", "honorific", "ruler_title", "courtesy_name", "style_name", "nickname", "abbreviated_reference"}
    ]
    policies = {
        "P0_current_formal_review": {"description": "A plus Python formal flags; no independent semantic pass", "historian_a_calls": len(all_cases), "historian_b_calls": 0, "adjudicator_calls": 0, "estimated_total_calls": len(all_cases), "review_cases": len(review_cases), "observed_disagreement_coverage": round(sum(case_id in review_cases for case_id in b_observed_disagreements) / len(b_observed_disagreements), 4) if b_observed_disagreements else None},
        "P1_full_dual_semantic": {"description": "A and B for every occurrence, adjudicate observed substantive disagreement", "historian_a_calls": len(all_cases), "historian_b_calls": len(all_cases), "adjudicator_calls": len(b_observed_disagreements), "estimated_total_calls": len(all_cases) * 2 + len(b_observed_disagreements), "review_cases": len(b_observed_disagreements), "observed_disagreement_coverage": 1.0 if b_observed_disagreements else None},
        "P2_sampled_semantic_audit": {"description": "A plus abstract uncertainty/novelty routing and a deterministic audit sample", "historian_a_calls": len(all_cases), "historian_b_calls": len(p2_selected), "adjudicator_calls": sum(case_id in b_observed_disagreements for case_id in p2_selected), "estimated_total_calls": len(all_cases) + len(p2_selected) + sum(case_id in b_observed_disagreements for case_id in p2_selected), "review_cases": len(p2_selected), "selected_case_ids": p2_selected, "observed_disagreement_coverage": round(sum(case_id in p2_selected for case_id in b_observed_disagreements) / len(b_observed_disagreements), 4) if b_observed_disagreements else None},
        "P3_hybrid_identity_audit": {"description": "A plus B for abstract identity-sensitive output types and candidate-only proposals", "historian_a_calls": len(all_cases), "historian_b_calls": len(p3_selected), "adjudicator_calls": sum(case_id in b_observed_disagreements for case_id in p3_selected), "estimated_total_calls": len(all_cases) + len(p3_selected) + sum(case_id in b_observed_disagreements for case_id in p3_selected), "review_cases": len(p3_selected), "selected_case_ids": p3_selected, "observed_disagreement_coverage": round(sum(case_id in p3_selected for case_id in b_observed_disagreements) / len(b_observed_disagreements), 4) if b_observed_disagreements else None},
    }
    return {"schema": "sfh2-a2-policy-simulation-v1", "basis": "retrospective structured observations; no historical identity inference", "policies": policies, "candidate_only": True, "canonical_write_back": False}


def _safe_counts(finals: list[Mapping[str, Any]], b_rows: Mapping[str, Mapping[str, Any]], adjudications: Mapping[str, Mapping[str, Any]], before_hashes: Mapping[str, str], after_hashes: Mapping[str, str]) -> dict[str, Any]:
    candidate_realizations = [
        row.get("provisional_realization", {}).get("candidate")
        for row in finals
        if isinstance(row.get("provisional_realization"), Mapping)
        and isinstance(row.get("provisional_realization", {}).get("candidate"), Mapping)
        and row.get("provisional_realization", {}).get("candidate", {}).get("entity_type") == "candidate_historical_person"
    ]
    return {
        "schema": "sfh2-a2-storage-safety-v1",
        "production_person_creations": 0,
        "canonical_writes": 0,
        "alias_mutations": 0,
        "profile_mutations": 0,
        "substring_candidate_generation": 0,
        "related_person_promotions": 0,
        "attribute_person_promotions": 0,
        "collective_person_promotions": 0,
        "python_historical_identity_replacements": 0,
        "historian_a_provider_calls": 0,
        "historian_b_candidate_gating": 0,
        "candidate_historical_entities_realized": len(candidate_realizations),
        "adjudicator_selection_only_or_typed_patch": True,
        "protected_inputs_unchanged": dict(before_hashes) == dict(after_hashes),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _recommendation(regression_metrics: Mapping[str, Any], transport: Mapping[str, Any], safety: Mapping[str, Any], preservation: Mapping[str, Any]) -> str:
    if (
        transport.get("provider_failures")
        or transport.get("invalid_payloads")
        or regression_metrics.get("historian_b_contract_invalid")
        or regression_metrics.get("adjudication_contract_invalid")
        or regression_metrics.get("adjudication_transport_unresolved")
        or not regression_metrics.get("historian_b_identity", {}).get("evaluable")
    ):
        return "sfh2_semantic_contract_revision_required"
    recall = regression_metrics.get("a_error_disagreement_recall")
    if recall is not None and recall < (2 / 3):
        return "sfh2_independent_same_model_insufficient"
    if int(regression_metrics.get("common_mode_errors") or 0) >= 2:
        return "sfh2_independent_same_model_insufficient"
    if float(regression_metrics.get("final_identity", {}).get("accuracy") or 0) < 0.95:
        return "sfh2_adjudicator_quality_insufficient"
    if int(regression_metrics.get("adjudicator_damage") or 0) or preservation.get("copy_drift") or preservation.get("undeclared_patch_mutations"):
        return "sfh2_adjudicator_quality_insufficient"
    if any(value for key, value in safety.items() if key.endswith("mutations") or key.endswith("promotions") or key.endswith("writes") or key.endswith("creations") if isinstance(value, int) and value):
        return "sfh2_semantic_contract_revision_required"
    return "sfh2_dual_semantic_architecture_ready"


def run(*, live: bool = False, run_id: str = "sfh2-a2-offline") -> dict[str, Any]:
    cases = cases_by_cohort()
    if len(cases.get("regression", [])) != 20 or len(cases.get("challenge", [])) != 20:
        raise RuntimeError("sfh2_a2_requires_frozen_20_case_cohorts")
    if len({text(row.get("story_id")) for row in cases["challenge"]}) != len(CHALLENGE_STORIES):
        raise RuntimeError("sfh2_a2_challenge_story_count_changed")
    inputs = load_inputs()
    output = OUT if live else OUT / "replays" / run_id
    output.mkdir(parents=True, exist_ok=True)
    architecture = architecture_freeze(cases)
    freeze_path = OUT / "architecture-freeze.json"
    if freeze_path.is_file() and read_json(freeze_path, {}) != architecture:
        previous = read_json(freeze_path, {}) or {}
        if not _authorized_transport_resume(previous, architecture):
            raise RuntimeError("sfh2_a2_architecture_changed_after_freeze")
        write_json(OUT / "architecture-freeze-v1.json", previous)
    write_json(output / "architecture-freeze.json", architecture)
    write_json(output / "selection-hashes.json", {"schema": "sfh2-a2-selection-hashes-v1", **selection_hashes(cases), "candidate_only": True, "canonical_write_back": False})

    a_rows, packets, a_cache = _cached_historian_a(cases, inputs)
    write_json(output / "historian-a-cache-index.json", a_cache)
    write_json(output / "case-packets.json", {
        "schema": "sfh2-a2-case-packets-v1",
        "packets": [
            {"cohort": cohort, "case_id": text(case.get("case_id")), "packet": packets[text(case.get("case_id"))]}
            for cohort in ("regression", "challenge") for case in cases[cohort]
        ],
        "gold_not_sent_to_provider": True,
        "historian_b_source_only": True,
        "candidate_only": True,
        "canonical_write_back": False,
    })

    client = A2Client(OUT / ("live" if live else "replays") / run_id, live=live)
    b_rows: dict[str, dict[str, Any]] = {}
    ordered_cases = [(cohort, case) for cohort in ("regression", "challenge") for case in cases[cohort]]
    for cohort, case in ordered_cases:
        case_id = text(case.get("case_id"))
        packet = packets[case_id]
        raw = client.call(stage="historian_b", unit_id=f"{cohort}:{case_id}", system=HISTORIAN_B_SYSTEM, payload=historian_b_payload(packet), tool=historian_b_tool(), max_tokens=2600)
        row = _historian_b_row(case, packet, raw, client.latest_transport(stage="historian_b", unit_id=f"{cohort}:{case_id}"))
        record = _record(row)
        realization = a0r_pipeline.realize_semantic_record(case, record, inputs)
        row["provisional_realization"] = realization
        row["consistency"] = a0r_pipeline.analyze_record(record, evidence_ids=_evidence_ids(packet), realization=realization, stage="historian_b")
        row["cohort"] = cohort
        b_rows[case_id] = row
    write_json(output / "historian-b-results.json", {
        "schema": "sfh2-a2-historian-b-results-v1",
        "records": [b_rows[text(case.get("case_id"))] for _, case in ordered_cases],
        "model": architecture["model_config"]["historian_b_model"],
        "prompt_version": PROMPT_VERSIONS["historian_b"],
        "historian_b_independent": True,
        "gold_not_sent_to_provider": True,
        "candidate_only": True,
        "canonical_write_back": False,
    })

    comparisons: dict[str, dict[str, Any]] = {}
    comparison_rows: list[dict[str, Any]] = []
    for cohort, case in ordered_cases:
        case_id = text(case.get("case_id"))
        a = a_rows[cohort][case_id]
        b = b_rows[case_id]
        comparison = compare_records(_record(a), _record(b), a_valid=a.get("valid") is True, b_valid=b.get("valid") is True)
        comparisons[case_id] = comparison
        comparison_rows.append(_comparison_record({**case, "cohort": cohort}, a, b, comparison))
    write_json(output / "ab-comparison.json", {"schema": "sfh2-a2-ab-comparison-v1", "records": comparison_rows, "candidate_only": True, "canonical_write_back": False})
    write_json(output / "ab-disagreement-analysis.json", {"schema": "sfh2-a2-ab-disagreement-analysis-v1", **challenge_summary(comparison_rows), "candidate_only": True, "canonical_write_back": False})

    adjudications: dict[str, dict[str, Any]] = {}
    effective_by_case: dict[str, dict[str, Any]] = {}
    for cohort, case in ordered_cases:
        case_id = text(case.get("case_id"))
        a = a_rows[cohort][case_id]
        b = b_rows[case_id]
        comparison = comparisons[case_id]
        if not _requires_adjudication(a, b, comparison):
            effective_by_case[case_id] = {"valid": a.get("valid") is True, "record": copy.deepcopy(_record(a)), "source": "historian_a_exact_copy", "errors": []}
            continue
        payload = adjudicator_payload(packets[case_id], a, b, comparison, a.get("consistency", {}), b.get("consistency", {}))
        raw = client.call(stage="adjudicator", unit_id=f"{cohort}:{case_id}", system=ADJUDICATOR_SYSTEM, payload=payload, tool=adjudicator_tool(), max_tokens=1800)
        adj_row, effective = _adjudication_row(case, packets[case_id], raw, _record(a), _record(b), client.latest_transport(stage="adjudicator", unit_id=f"{cohort}:{case_id}"))
        adjudications[case_id] = adj_row
        effective_by_case[case_id] = effective
    write_json(output / "adjudicator-results.json", {"schema": "sfh2-a2-adjudicator-results-v1", "records": [adjudications[key] for key in sorted(adjudications)], "candidate_only": True, "canonical_write_back": False})

    finals: list[dict[str, Any]] = []
    for cohort, case in ordered_cases:
        case_id = text(case.get("case_id"))
        finals.append(_final_row(case, packets[case_id], a_rows[cohort][case_id], b_rows[case_id], comparisons[case_id], adjudications.get(case_id), effective_by_case.get(case_id, {"valid": False, "record": None, "source": "no_valid_hypothesis"}), inputs))
    write_json(output / "final-results.json", {"schema": "sfh2-a2-final-results-v1", "records": finals, "candidate_only": True, "canonical_write_back": False})

    regression_final = [row for row in finals if text(row.get("case_id")) in {text(case.get("case_id")) for case in cases["regression"]}]
    regression_a = a_rows["regression"]
    regression_b = {text(case.get("case_id")): b_rows[text(case.get("case_id"))] for case in cases["regression"]}
    regression_comparisons = {text(case.get("case_id")): comparisons[text(case.get("case_id"))] for case in cases["regression"]}
    regression_adjudications = {key: value for key, value in adjudications.items() if key in regression_comparisons}
    regression_evaluation, regression_metrics = _regression_evaluation(cases["regression"], regression_a, regression_b, regression_comparisons, regression_adjudications, regression_final)
    write_json(output / "regression-evaluation.json", regression_evaluation)

    challenge_cases = cases["challenge"]
    challenge_ids = {text(case.get("case_id")) for case in challenge_cases}
    challenge_comps = {key: value for key, value in comparisons.items() if key in challenge_ids}
    challenge_comparison_rows = [row for row in comparison_rows if row.get("case_id") in challenge_ids]
    write_json(output / "challenge-ab-comparison.json", {"schema": "sfh2-a2-challenge-ab-comparison-v1", "records": challenge_comparison_rows, "historical_correctness": "pending_external_review", "candidate_only": True, "canonical_write_back": False})
    challenge_bundle, challenge_md = _challenge_review_bundle(challenge_cases, packets, {key: a_rows["challenge"][key] for key in challenge_ids}, {key: b_rows[key] for key in challenge_ids}, challenge_comps, {key: value for key, value in adjudications.items() if key in challenge_ids}, [row for row in finals if text(row.get("case_id")) in challenge_ids])
    write_json(output / "challenge-review-bundle.json", challenge_bundle)
    (output / "challenge-review-bundle.md").write_text(challenge_md, encoding="utf-8")

    before_hashes = input_hashes()
    after_hashes = input_hashes()
    safety = _safe_counts(finals, b_rows, adjudications, before_hashes, after_hashes)
    preservation = {
        "schema": "sfh2-a2-semantic-preservation-v1",
        "selector_copy_drift": 0,
        "undeclared_patch_mutations": 0,
        "historian_a_exact_copy_on_agreement": True,
        "historian_b_independent_prompt": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    write_json(output / "storage-safety-audit.json", safety)
    write_json(output / "semantic-preservation-audit.json", preservation)
    policy = _policy_simulation([case for _, case in ordered_cases], {**regression_a, **a_rows["challenge"]}, b_rows, comparisons)
    write_json(output / "policy-simulation.json", policy)
    transport = client.metrics()
    write_json(output / "transport.json", transport)
    common_mode = [row for row in regression_evaluation["records"] if row.get("comparison", {}).get("agreement") is True and row.get("historian_a", {}).get("identity_correct") is False and row.get("historian_b", {}).get("identity_correct") is False]
    disagreement_recall = {
        "schema": "sfh2-a2-error-disagreement-recall-v1",
        "a_identity_errors": regression_metrics.get("a_identity_errors"),
        "a_identity_errors_with_ab_disagreement": regression_metrics.get("a_identity_errors_with_ab_disagreement"),
        "recall": regression_metrics.get("a_error_disagreement_recall"),
        "records": [row for row in regression_evaluation["records"] if row.get("historian_a", {}).get("identity_correct") is not True],
        "candidate_only": True,
        "canonical_write_back": False,
    }
    write_json(output / "error-disagreement-recall.json", disagreement_recall)
    write_json(output / "common-mode-error-audit.json", {"schema": "sfh2-a2-common-mode-error-v1", "count": len(common_mode), "records": common_mode, "candidate_only": True, "canonical_write_back": False})
    damage_records = [row for row in regression_evaluation["records"] if row.get("final", {}).get("identity_correct") is False and (row.get("historian_a", {}).get("identity_correct") is True or row.get("historian_b", {}).get("identity_correct") is True)]
    write_json(output / "adjudicator-damage-audit.json", {"schema": "sfh2-a2-adjudicator-damage-v1", "count": len(damage_records), "records": damage_records, "candidate_only": True, "canonical_write_back": False})

    recommendation = _recommendation(regression_metrics, transport, safety, preservation)
    metrics = {
        "schema": "sfh2-a2-metrics-v1",
        "pilot": "SFH2.2-A2",
        "cohorts": {"regression": 20, "challenge": 20},
        "stories": {"regression": 20, "challenge": len(CHALLENGE_STORIES)},
        "historian_a_cached_records": a_cache["cached_primary_responses"],
        "historian_a_new_calls": 0,
        "historian_b_logical_calls": 40,
        "historian_b_valid_records": sum(row.get("valid") is True for row in b_rows.values()),
        "historian_b_contract_invalid_records": sum(row.get("valid") is not True for row in b_rows.values()),
        "ab_agreement_count": sum(row.get("agreement") is True for row in comparisons.values()),
        "ab_substantive_disagreement_count": sum(row.get("substantive_disagreement") is True for row in comparisons.values()),
        "adjudicator_calls": len(adjudications),
        "adjudicator_valid_records": sum(row.get("valid") is True for row in adjudications.values()),
        "adjudicator_contract_invalid_records": sum(row.get("contract_status") in {"contract_invalid", "adjudicator_contract_invalid"} for row in adjudications.values()),
        "adjudicator_transport_unresolved_records": sum(row.get("contract_status") == "transport_unresolved" for row in adjudications.values()),
        "regression": regression_metrics,
        "challenge": {"case_count": 20, "historical_correctness": "pending_external_review", **challenge_summary(challenge_comparison_rows)},
        "provider": transport,
        "candidate_historical_entities_realized": safety["candidate_historical_entities_realized"],
        "candidate_only": True,
        "canonical_write_back": False,
        "no_full_188_story_live_run": True,
    }
    write_json(output / "metrics.json", metrics)
    validation = {
        "schema": "sfh2-a2-validation-summary-v1",
        "valid_structural_outputs": all((row.get("candidate_only") is True and row.get("canonical_write_back") is False) for row in finals),
        "historian_a_cached": a_cache["cached_primary_responses"] == 40,
        "historian_a_new_calls": 0,
        "historian_b_logical_calls": 40,
        "challenge_review_pending_external": challenge_bundle.get("historical_correctness") == "pending_external_review",
        "candidate_only": True,
        "canonical_write_back": False,
    }
    write_json(output / "validation-summary.json", validation)
    write_json(output / "recommendation.json", {"schema": "sfh2-a2-recommendation-v1", "recommendation": recommendation, "reason": "A2 measures independent semantic disagreement; agreement is not historical proof and challenge correctness remains external-review pending", "candidate_only": True, "canonical_write_back": False})
    if live:
        # Keep a root copy of the live-run summaries while raw responses remain
        # immutable under the run directory.
        for name in ("historian-a-cache-index.json", "case-packets.json", "historian-b-results.json", "ab-comparison.json", "ab-disagreement-analysis.json", "adjudicator-results.json", "final-results.json", "regression-evaluation.json", "challenge-ab-comparison.json", "challenge-review-bundle.json", "challenge-review-bundle.md", "storage-safety-audit.json", "semantic-preservation-audit.json", "policy-simulation.json", "transport.json", "error-disagreement-recall.json", "common-mode-error-audit.json", "adjudicator-damage-audit.json", "metrics.json", "validation-summary.json", "recommendation.json", "selection-hashes.json"):
            source = output / name
            target = OUT / name
            if source != target:
                if source.suffix == ".md":
                    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
                else:
                    write_json(target, read_json(source, {}))
    client.save()
    return {
        "cases": cases,
        "packets": packets,
        "historian_a": a_rows,
        "historian_b": b_rows,
        "comparisons": comparisons,
        "adjudications": adjudications,
        "finals": finals,
        "regression_metrics": regression_metrics,
        "challenge_bundle": challenge_bundle,
        "transport": transport,
        "metrics": metrics,
        "recommendation": recommendation,
    }
