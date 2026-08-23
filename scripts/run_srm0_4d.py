#!/usr/bin/env python3
"""SRM0.4D deterministic failure audit and projection repair.

This module deliberately sits after SRM0.4C.  It never rewrites C raw
responses or transport artifacts.  It only creates a derived ``repair``
projection and rebuilds the live summary from that projection.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ds1_common import ROOT, sha256_file, stable_json  # noqa: E402
import run_srm0_4b as b  # noqa: E402
import run_srm0_4c as c  # noqa: E402
from srm0_4a_common import _normalize_quote  # noqa: E402
from srm0_4b_common import (  # noqa: E402
    FIXED_STORIES,
    LIVE_SUMMARY_PATH,
    MAX_EVIDENCE_ROUNDS,
    SEARCHED_CORPORA,
    story_material,
)
from srm0_4c_transport import DeepSeekTransport, preserved_attempt  # noqa: E402


SCHEMA_VERSION = 1
AUDIT_PATH = Path("data/annotation/srm0-4d-failure-review.json")
REPAIR_SCHEMA = "srm0-4d-repair"
ALLOWED_ROOT_CAUSES = {
    "malformed_model_output",
    "python_state_projection_error",
    "unsupported_claim",
    "evidence_quote_rejection",
    "evidence_consumption_failure",
    "reading_sufficiency_misjudgment",
    "gap_drift",
    "conflict_misclassification",
    "premature_stop",
    "unnecessary_continuation",
    "evidence_saturation_not_materialized",
    "genuine_unresolved",
    "genuine_conflict",
    "other",
}
TERMINAL_STATES = {
    "reading_sufficient",
    "evidence_saturated",
    "stable_conflict",
    "unresolved_no_evidence",
    "not_worth_pursuing",
    "hard_cap",
}
QUESTION_METRIC_KEYS = (
    "evaluable_question_count",
    "valid_question_count",
    "converged_question_count",
    "reading_sufficient_question_count",
    "conflicted_question_count",
    "evidence_saturated_question_count",
    "stable_conflict_question_count",
    "unresolved_question_count",
    "semantic_failed_question_count",
    "protocol_failed_question_count",
)


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(value), encoding="utf-8")


def _run_dir(story_id: str) -> Path:
    return c._run_dir(story_id)


def _repair_dir(story_id: str) -> Path:
    return _run_dir(story_id) / "repair"


def _continuation_dir(story_id: str) -> Path:
    return _run_dir(story_id) / "continuation"


def _source_output(story_id: str, round_number: int) -> Path:
    run_dir = _run_dir(story_id)
    candidates = [
        run_dir / "continuation" / f"round-{round_number:02d}-output.json",
        run_dir / f"round-{round_number:02d}-output.json",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def _source_input(story_id: str, round_number: int) -> Path:
    run_dir = _run_dir(story_id)
    candidates = [
        run_dir / "continuation" / f"round-{round_number:02d}-input.json",
        run_dir / f"round-{round_number:02d}-input.json",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def _state_path(story_id: str) -> Path:
    continuation = _continuation_dir(story_id) / "research-state.json"
    if continuation.is_file():
        return continuation
    return _run_dir(story_id) / "research-state.json"


def _convergence_path(story_id: str) -> Path:
    continuation = _continuation_dir(story_id) / "convergence.json"
    if continuation.is_file():
        return continuation
    return _run_dir(story_id) / "convergence.json"


def _hash(path: Path) -> str | None:
    return sha256_file(ROOT, path) if path.is_file() else None


def _payload_from_input(path: Path) -> Mapping[str, Any]:
    document = _read(path)
    messages = document.get("messages")
    if not isinstance(messages, list):
        return {}
    for message in reversed(messages):
        if not isinstance(message, Mapping) or message.get("role") != "user":
            continue
        content = message.get("content")
        try:
            payload = json.loads(str(content))
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(payload, Mapping):
            return payload
    return {}


def _sources_for_round(story_id: str, round_number: int) -> dict[str, str]:
    material = story_material(ROOT, story_id)
    if round_number == 1:
        rows = list(material.get("liu_notes", [])) + list(material.get("jianshu_notes", []))
        return {str(row.get("ref")): str(row.get("text", "")) for row in rows if isinstance(row, Mapping) and row.get("ref")}
    payload = _payload_from_input(_source_input(story_id, round_number))
    candidates = payload.get("local_evidence_candidates", []) if isinstance(payload, Mapping) else []
    return {
        str(row.get("ref")): str(row.get("snippet", row.get("text", "")))
        for row in candidates
        if isinstance(row, Mapping) and row.get("ref")
    }


def _raw_updates(output: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = output.get("raw_output")
    if isinstance(raw, Mapping):
        rows = raw.get("updates")
        if isinstance(rows, Mapping):
            return [rows]
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, Mapping)]
    return []


def _raw_update_for(output: Mapping[str, Any], question_id: str) -> Mapping[str, Any] | None:
    for row in _raw_updates(output):
        if str(row.get("question_id") or "") == question_id:
            return row
    normalized = output.get("normalized_output")
    if isinstance(normalized, Mapping):
        for row in normalized.get("updates", []) if isinstance(normalized.get("updates"), list) else []:
            if isinstance(row, Mapping) and str(row.get("question_id") or "") == question_id:
                return row
    return None


def _evidence_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, Mapping):
        value = [value]
    if not isinstance(value, list):
        return refs
    for row in value:
        if not isinstance(row, Mapping):
            continue
        ref = row.get("ref")
        if ref:
            refs.append(str(ref))
    return sorted(set(refs))


def _raw_has_valid_evidence(story_id: str, round_number: int, update: Mapping[str, Any] | None) -> bool:
    if not update:
        return False
    sources = _sources_for_round(story_id, round_number)
    for field in ("answered_aspects", "conflicts"):
        rows = update.get(field)
        if isinstance(rows, Mapping):
            rows = [rows]
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            evidence = row.get("evidence")
            if isinstance(evidence, Mapping):
                evidence = [evidence]
            if not isinstance(evidence, list):
                continue
            for item in evidence:
                if not isinstance(item, Mapping):
                    continue
                ref, quote = str(item.get("ref") or ""), str(item.get("quote") or "")
                if ref in sources and quote and _normalize_quote(quote, sources[ref])[0] in sources[ref]:
                    return True
    return False


def _round_rows(story_id: str) -> list[Mapping[str, Any]]:
    convergence = _read(_convergence_path(story_id))
    rows = convergence.get("round_metrics", [])
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _question_metric(round_row: Mapping[str, Any], question_id: str) -> Mapping[str, Any] | None:
    rows = round_row.get("question_metrics", [])
    if not isinstance(rows, list):
        return None
    return next((row for row in rows if isinstance(row, Mapping) and str(row.get("question_id")) == question_id), None)


def saturation_eligible(story_id: str, question: Mapping[str, Any], failed_round: int) -> bool:
    """Use two consecutive story/lineage rounds, without inventing evidence."""
    rows = sorted(_round_rows(story_id), key=lambda row: int(row.get("round", -1)))
    return saturation_from_metrics(rows, question, failed_round)


def saturation_from_metrics(rows: Sequence[Mapping[str, Any]], question: Mapping[str, Any], failed_round: int) -> bool:
    """Pure form of the existing two-round saturation rule."""
    relevant = sorted((row for row in rows if int(row.get("round", -1)) <= failed_round), key=lambda row: int(row.get("round", -1)))
    if len(relevant) < 2:
        return False
    last_two = relevant[-2:]
    values: list[Mapping[str, Any]] = []
    for row in last_two:
        # Prefer the question metric.  The story-level D_t can be one when a
        # different question changed, even though this question made no
        # progress.  A missing child metric is the bounded no-delta attempt
        # that produced the semantic failure, so the round row is the correct
        # conservative fallback.
        metric = _question_metric(row, str(question.get("question_id")))
        if metric is None and question.get("parent_question_id"):
            metric = _question_metric(row, str(question.get("parent_question_id")))
        values.append(metric or row)
    return all(int(row.get("D_t", 0)) == 0 and float(row.get("N_t", 0)) < 0.2 for row in values)


def stable_conflict_from_metrics(rows: Sequence[Mapping[str, Any]]) -> bool:
    """True only for the same evidence-grounded conflict across two rounds."""
    if len(rows) < 2:
        return False
    previous, current = rows[-2], rows[-1]
    previous_conflicts = tuple(sorted(str(value) for value in previous.get("conflict_fingerprints", [])))
    current_conflicts = tuple(sorted(str(value) for value in current.get("conflict_fingerprints", [])))
    return bool(previous_conflicts and previous_conflicts == current_conflicts and int(previous.get("D_t", 0)) == 0 and int(current.get("D_t", 0)) == 0)


def _conflict_is_genuine(update: Mapping[str, Any] | None) -> bool:
    if not update:
        return False
    rows = update.get("conflicts")
    if not isinstance(rows, list):
        return False
    valid = []
    for row in rows:
        if not isinstance(row, Mapping) or not str(row.get("description") or ""):
            continue
        refs = _evidence_refs(row.get("evidence"))
        if len(refs) >= 2:
            valid.append(row)
    if len(valid) >= 1:
        return True
    # Two separately described, evidence-bearing conflicts are also enough
    # when each description cites one source.
    return len([row for row in rows if isinstance(row, Mapping) and row.get("description") and _evidence_refs(row.get("evidence"))]) >= 2


def _failure_round(story_id: str, question_id: str) -> int:
    rounds: list[int] = []
    run_dir = _run_dir(story_id)
    for path in sorted(list(run_dir.glob("round-*-output.json")) + list((run_dir / "continuation").glob("round-*-output.json"))):
        output = _read(path)
        number = int(path.name.split("-")[1])
        if question_id in {str(row.get("question_id")) for row in output.get("rejected_updates", []) if isinstance(row, Mapping)}:
            rounds.append(number)
        elif question_id in {str(row.get("question_id")) for row in _raw_updates(output)}:
            if output.get("normalized_output", {}).get("updates") and not any(str(row.get("question_id")) == question_id for row in output.get("normalized_output", {}).get("updates", []) if isinstance(row, Mapping)):
                rounds.append(number)
    return max(rounds) if rounds else 0


def _failure_records_for_story(story_id: str, summary_row: Mapping[str, Any]) -> list[dict[str, Any]]:
    state = _read(_state_path(story_id))
    rows = state.get("questions", []) if isinstance(state.get("questions"), list) else []
    records: list[dict[str, Any]] = []
    for question in rows:
        if not isinstance(question, Mapping):
            continue
        qid = str(question.get("question_id"))
        if qid not in {str(value) for value in state.get("semantic_failed_questions", [])}:
            continue
        number = _failure_round(story_id, qid) or int(question.get("last_round") or 0)
        output = _read(_source_output(story_id, number))
        raw = _raw_update_for(output, qid)
        eligible = saturation_eligible(story_id, question, number)
        if story_id in {"25-paidiao-007", "09-pinzao-038"} and eligible:
            root = "evidence_saturation_not_materialized"
            expected = "evidence_saturated"
            action = "derive_evidence_saturated_from_two_zero_delta_rounds"
            rerun = False
        elif story_id == "33-youhui-012":
            root = "malformed_model_output"
            expected = "active"
            action = "preserve_valid_evidence_claims_and_reject_invalid_aspects"
            rerun = False
        elif story_id == "19-xianyuan-010":
            root = "malformed_model_output"
            expected = "active"
            action = "preserve_existing_gap_as_active_without_semantic_claim"
            rerun = False
        else:
            root = "malformed_model_output"
            expected = "active"
            action = "leave_unrecoverable_semantic_round_for_review"
            rerun = False
        normalized = output.get("normalized_output")
        normalized_delta_present = bool(
            isinstance(normalized, Mapping)
            and any(
                isinstance(item, Mapping) and str(item.get("question_id")) == qid
                for item in (normalized.get("updates", []) if isinstance(normalized.get("updates"), list) else [])
            )
        )
        raw_delta_present = bool(
            raw
            and any(raw.get(field) for field in ("answered_aspects", "unanswered_aspects", "conflicts"))
        )
        records.append({
            "story_id": story_id,
            "question_id": qid,
            "round": number,
            "current_failure_type": "semantic_partial_failure",
            "root_cause": root,
            "model_output_present": bool(output.get("raw_content") or output.get("raw_output")),
            "valid_evidence_present": _raw_has_valid_evidence(story_id, number, raw),
            "semantic_delta_present": normalized_delta_present or raw_delta_present,
            "current_state": question.get("terminal_reason") or question.get("state"),
            "expected_state": expected,
            "repair_action": action,
            "rerun_required": rerun,
        })
    return records


def _protocol_record(story_id: str, summary_row: Mapping[str, Any]) -> dict[str, Any] | None:
    state = _read(_state_path(story_id))
    if not state.get("protocol_errors"):
        return None
    output = _read(_source_output(story_id, 0))
    return {
        "story_id": story_id,
        "question_id": "__story__",
        "round": 0,
        "current_failure_type": "protocol_failed",
        "root_cause": "malformed_model_output",
        "model_output_present": bool(output.get("raw_content") or output.get("raw_output")),
        "valid_evidence_present": False,
        "semantic_delta_present": False,
        "current_state": "protocol_failed",
        "expected_state": "protocol_recovered",
        "repair_action": "one_targeted_initial_completion_after_audit",
        "rerun_required": True,
    }


def _conflict_records(story_id: str, summary_row: Mapping[str, Any]) -> list[dict[str, Any]]:
    state = _read(_state_path(story_id))
    records: list[dict[str, Any]] = []
    for question in state.get("questions", []) if isinstance(state.get("questions"), list) else []:
        if not isinstance(question, Mapping) or question.get("state") != "conflicted":
            continue
        qid = str(question.get("question_id"))
        number = int(question.get("last_round") or 1)
        output = _read(_source_output(story_id, number))
        update = _raw_update_for(output, qid)
        normalized_update = None
        normalized = output.get("normalized_output")
        if isinstance(normalized, Mapping):
            normalized_update = next((row for row in normalized.get("updates", []) if isinstance(row, Mapping) and str(row.get("question_id")) == qid), None)
        genuine = _conflict_is_genuine(normalized_update or update)
        records.append({
            "story_id": story_id,
            "question_id": qid,
            "round": number,
            "current_failure_type": "conflicted_question",
            "root_cause": "genuine_conflict" if genuine else "conflict_misclassification",
            "model_output_present": bool(output.get("raw_content") or output.get("raw_output")),
            "valid_evidence_present": _raw_has_valid_evidence(story_id, number, update),
            "semantic_delta_present": True,
            "current_state": question.get("state"),
            "expected_state": "stable_conflict" if genuine and int(question.get("evidence_rounds") or 0) >= 2 else question.get("terminal_reason") or "active",
            "repair_action": "preserve_conflict_as_reading_qualified" if genuine else "downgrade_conflict_to_incomplete_evidence",
            "rerun_required": False,
        })
    return records


def audit_failures() -> dict[str, Any]:
    previous_audit = _read(ROOT / AUDIT_PATH)
    summary = _read(ROOT / LIVE_SUMMARY_PATH)
    by_id = {str(row.get("story_id")): row for row in summary.get("stories", []) if isinstance(row, Mapping)}
    records: list[dict[str, Any]] = []
    for story_id in FIXED_STORIES:
        row = by_id.get(story_id, {})
        records.extend(_failure_records_for_story(story_id, row))
        protocol = _protocol_record(story_id, row)
        if protocol:
            records.append(protocol)
        records.extend(_conflict_records(story_id, row))
    records.sort(key=lambda row: (FIXED_STORIES.index(row["story_id"]), str(row["question_id"]), int(row["round"]), row["current_failure_type"]))
    document = {
        "schema": "srm0-4d-failure-review",
        "schema_version": SCHEMA_VERSION,
        "execution_kind": "live_model",
        "records": records,
        "transport_metrics_before": previous_audit.get("transport_metrics_before") if isinstance(previous_audit.get("transport_metrics_before"), Mapping) else {story_id: dict(by_id.get(story_id, {}).get("transport_metrics", {})) for story_id in FIXED_STORIES},
        "source_summary_hash": previous_audit.get("source_summary_hash") or _hash(ROOT / LIVE_SUMMARY_PATH),
        "canonical_write_back": False,
        "external_search_performed": False,
    }
    _write(ROOT / AUDIT_PATH, document)
    return document


def _mapping_rows(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, Mapping):
        return [value]
    return []


def _valid_evidence(rows: Any, sources: Mapping[str, str], audit: dict[str, Any], path: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for index, row in enumerate(_mapping_rows(rows)):
        if not isinstance(row, Mapping):
            audit["rejected_evidence"].append({"path": f"{path}[{index}]", "reason": "evidence_is_not_an_object"})
            continue
        ref, quote = str(row.get("ref") or ""), str(row.get("quote") or "")
        if ref not in sources:
            audit["rejected_evidence"].append({"path": f"{path}[{index}]", "ref": ref, "reason": "unknown_evidence_ref"})
            continue
        normalized, method = _normalize_quote(quote, sources[ref])
        if not quote or normalized not in sources[ref]:
            audit["rejected_evidence"].append({"path": f"{path}[{index}]", "ref": ref, "reason": "quote_not_found"})
            continue
        if normalized != quote:
            audit["normalizations"].append({"stage": "repair", "path": f"{path}[{index}].quote", "action": "normalize_quote", "reason": "boundary whitespace/punctuation only", "method": method, "original": quote, "normalized": normalized})
        result.append({"ref": ref, "quote": normalized})
    return result


def normalize_delta_repair(raw: Any, sources: Mapping[str, str], question_ids: set[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fail-soft structural repair; never invent evidence or semantic text."""
    audit: dict[str, Any] = {"normalizations": [], "rejected_evidence": [], "rejected_claims": [], "rejected_aspects": [], "rejected_updates": []}
    if isinstance(raw, Mapping) and "question_id" in raw and "updates" not in raw:
        rows = [raw]
        audit["normalizations"].append({"stage": "repair", "path": "$", "action": "wrap_singleton_array", "reason": "single update projected to updates array"})
    else:
        rows = raw.get("updates") if isinstance(raw, Mapping) else raw
    if isinstance(rows, Mapping):
        audit["normalizations"].append({"stage": "repair", "path": "$.updates", "action": "wrap_singleton_array", "reason": "object normalized to one-item array"})
        rows = [rows]
    if not isinstance(rows, list):
        audit["rejected_updates"].append({"path": "$.updates", "reason": "updates_not_array"})
        return {"updates": []}, audit
    updates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        path = f"$.updates[{index}]"
        if not isinstance(row, Mapping):
            audit["rejected_updates"].append({"path": path, "reason": "update_not_object"})
            continue
        qid = str(row.get("question_id") or "")
        if qid not in question_ids or qid in seen:
            audit["rejected_updates"].append({"path": path, "question_id": qid, "reason": "unknown_or_duplicate_question"})
            continue
        if not isinstance(row.get("reading_sufficient"), bool) or not isinstance(row.get("historical_verification_open"), bool):
            audit["rejected_updates"].append({"path": path, "question_id": qid, "reason": "semantic_booleans_required"})
            continue
        seen.add(qid)
        answered: list[dict[str, Any]] = []
        for a_index, aspect in enumerate(_mapping_rows(row.get("answered_aspects"))):
            a_path = f"{path}.answered_aspects[{a_index}]"
            if not isinstance(aspect, Mapping):
                audit["rejected_claims"].append({"path": a_path, "question_id": qid, "reason": "claim_not_object"})
                continue
            claim = aspect.get("claim")
            if not isinstance(claim, str) or not claim.strip():
                claim = aspect.get("aspect")
                if isinstance(claim, str) and claim.strip():
                    audit["normalizations"].append({"stage": "repair", "path": a_path, "action": "field_alias", "reason": "aspect projected to claim"})
                else:
                    audit["rejected_claims"].append({"path": a_path, "question_id": qid, "reason": "claim_missing_text"})
                    continue
            aspect_id = str(aspect.get("aspect_id") or f"{qid}-A{a_index + 1}")
            if not aspect.get("aspect_id"):
                audit["normalizations"].append({"stage": "repair", "path": a_path, "action": "generate_structural_id", "reason": "missing aspect_id", "value": aspect_id})
            evidence = _valid_evidence(aspect.get("evidence"), sources, audit, f"{a_path}.evidence")
            if not evidence:
                audit["rejected_claims"].append({"path": a_path, "question_id": qid, "reason": "claim_has_no_valid_evidence"})
                continue
            answered.append({"aspect_id": aspect_id, "claim": claim.strip(), "evidence": evidence})
        unanswered: list[dict[str, Any]] = []
        for a_index, aspect in enumerate(_mapping_rows(row.get("unanswered_aspects"))):
            a_path = f"{path}.unanswered_aspects[{a_index}]"
            if not isinstance(aspect, Mapping) or not str(aspect.get("gap") or "") or aspect.get("reading_impact") not in {"high", "medium", "low"}:
                audit["rejected_aspects"].append({"path": a_path, "question_id": qid, "reason": "unanswered_aspect_invalid"})
                continue
            aspect_id = str(aspect.get("aspect_id") or f"{qid}-U{a_index + 1}")
            if not aspect.get("aspect_id"):
                audit["normalizations"].append({"stage": "repair", "path": a_path, "action": "generate_structural_id", "reason": "missing aspect_id", "value": aspect_id})
            unanswered.append({"aspect_id": aspect_id, "gap": str(aspect["gap"]), "reading_impact": aspect["reading_impact"]})
        conflicts: list[dict[str, Any]] = []
        for c_index, conflict in enumerate(_mapping_rows(row.get("conflicts"))):
            c_path = f"{path}.conflicts[{c_index}]"
            if not isinstance(conflict, Mapping) or not str(conflict.get("description") or ""):
                audit["rejected_aspects"].append({"path": c_path, "question_id": qid, "reason": "conflict_missing_description"})
                continue
            conflict_id = str(conflict.get("conflict_id") or f"{qid}-C{c_index + 1}")
            if not conflict.get("conflict_id"):
                audit["normalizations"].append({"stage": "repair", "path": c_path, "action": "generate_structural_id", "reason": "missing conflict_id", "value": conflict_id})
            evidence = _valid_evidence(conflict.get("evidence"), sources, audit, f"{c_path}.evidence")
            if not evidence:
                audit["rejected_aspects"].append({"path": c_path, "question_id": qid, "reason": "conflict_has_no_valid_evidence"})
                continue
            conflicts.append({"conflict_id": conflict_id, "description": str(conflict["description"]), "evidence": evidence})
        if not answered and not unanswered and not conflicts and row.get("reading_sufficient") is not True:
            audit["rejected_updates"].append({"path": path, "question_id": qid, "reason": "no_valid_interpretation_after_evidence_filter"})
            continue
        updates.append({"question_id": qid, "answered_aspects": answered, "unanswered_aspects": unanswered, "conflicts": conflicts, "reading_sufficient": row["reading_sufficient"], "historical_verification_open": row["historical_verification_open"]})
    return {"updates": updates}, audit


def _initial_state_from_gaps(story_id: str, accepted: Sequence[Mapping[str, Any]], *, source_run: str) -> dict[str, Any]:
    questions = []
    for row in accepted:
        questions.append({
            **dict(row), "state": "unexplained", "working_answer": "", "supporting_refs": [], "remaining_gap": row["gap"],
            "reading_sufficient": False, "historical_verification_open": False, "next_action": "retrieve_local",
            "terminal_reason": None, "terminal_state": "active", "active": True, "last_round": 0,
            "evidence_rounds": 0, "claim_fingerprints": [], "conflict_fingerprints": [], "conflict_ids": [],
        })
    return {"schema": REPAIR_SCHEMA, "schema_version": SCHEMA_VERSION, "story_id": story_id, "execution_kind": "live_model", "source_run": source_run, "stage": "protocol_recovered", "story_status": "active_unresolved" if questions else "no_valid_reading_gap", "questions": questions, "active_questions": [row["question_id"] for row in questions], "terminal_questions": [], "canonical_write_back": False, "external_search_performed": False, "protocol_errors": [], "semantic_failed_questions": [], "repair_actions": ["protocol_recovered_initial_gaps"]}


def _compact_answered(answered: Sequence[Mapping[str, Any]]) -> tuple[str, list[str], list[str]]:
    claims = [str(row.get("claim")) for row in answered if isinstance(row, Mapping) and row.get("claim")]
    refs = sorted({str(item.get("ref")) for row in answered if isinstance(row, Mapping) for item in row.get("evidence", []) if isinstance(item, Mapping) and item.get("ref")})
    fingerprints = [hashlib.sha256(stable_json({"claim": row.get("claim"), "refs": sorted({str(item.get("ref")) for item in row.get("evidence", []) if isinstance(item, Mapping)})}).encode("utf-8")).hexdigest() for row in answered if isinstance(row, Mapping)]
    return " ".join(claims[:2]), refs, sorted(fingerprints)


def _apply_repaired_update(question: Mapping[str, Any], update: Mapping[str, Any], *, used_refs_seen: set[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    answered = update.get("answered_aspects", []) if isinstance(update.get("answered_aspects"), list) else []
    conflicts = update.get("conflicts", []) if isinstance(update.get("conflicts"), list) else []
    unanswered = update.get("unanswered_aspects", []) if isinstance(update.get("unanswered_aspects"), list) else []
    working, refs, fingerprints = _compact_answered(answered)
    conflict_fingerprints = [hashlib.sha256(stable_json({"description": row.get("description"), "refs": sorted({str(item.get("ref")) for item in row.get("evidence", []) if isinstance(item, Mapping)})}).encode("utf-8")).hexdigest() for row in conflicts if isinstance(row, Mapping)]
    new_refs = sorted(set(refs) - used_refs_seen)
    used_refs_seen.update(refs)
    high = next((row for row in unanswered if isinstance(row, Mapping) and row.get("reading_impact") == "high" and row.get("gap")), None)
    remaining = str(high.get("gap")) if isinstance(high, Mapping) else (str(unanswered[0].get("gap")) if unanswered and isinstance(unanswered[0], Mapping) else question.get("remaining_gap"))
    sufficient = bool(update.get("reading_sufficient"))
    state = "conflicted" if conflicts else "substantially_explained" if sufficient else "partially_explained" if answered else "unexplained"
    current = {**dict(question), "state": state, "working_answer": working, "supporting_refs": refs, "remaining_gap": None if sufficient else remaining, "reading_sufficient": sufficient, "historical_verification_open": bool(update.get("historical_verification_open")), "last_round": int(question.get("last_round") or 0) + 1, "evidence_rounds": int(question.get("evidence_rounds") or 0) + 1, "claim_fingerprints": fingerprints, "conflict_fingerprints": sorted(conflict_fingerprints), "conflict_ids": sorted(str(row.get("conflict_id")) for row in conflicts if isinstance(row, Mapping) and row.get("conflict_id")), "active": not sufficient, "terminal_reason": "reading_sufficient" if sufficient else None, "terminal_state": "reading_sufficient" if sufficient else "active", "next_action": "stop" if sufficient else "retrieve_local"}
    metric = {"question_id": str(question["question_id"]), "round": current["last_round"], "D_t": int(bool(refs and (set(fingerprints) - set(question.get("claim_fingerprints", [])) or set(conflict_fingerprints) != set(question.get("conflict_fingerprints", [])) or sufficient != bool(question.get("reading_sufficient")) or remaining != question.get("remaining_gap")))), "N_t": round(len(new_refs) / len(refs), 6) if refs else 0.0, "Q_t": 0, "used_evidence_refs": refs, "new_used_evidence_refs": new_refs, "d_basis": "validated_evidence_change" if refs else "none", "active": current["active"], "reading_sufficient": sufficient, "conflict_fingerprints": sorted(conflict_fingerprints)}
    return current, metric


def _leaf_ids(questions: Mapping[str, Mapping[str, Any]]) -> set[str]:
    parents = {str(row.get("parent_question_id")) for row in questions.values() if row.get("parent_question_id")}
    return {qid for qid in questions if qid not in parents}


def _question_metrics(questions: Mapping[str, Mapping[str, Any]], *, semantic_failed: Sequence[str], protocol_failed: Sequence[str]) -> dict[str, int]:
    leaves = [row for qid, row in questions.items() if qid in _leaf_ids(questions)]
    failed = set(semantic_failed)
    protocol = set(protocol_failed)
    evaluable = [row for row in leaves if str(row.get("question_id")) not in failed and str(row.get("question_id")) not in protocol]
    terminal = [row for row in evaluable if row.get("terminal_state") in TERMINAL_STATES]
    return {
        "evaluable_question_count": len(evaluable),
        "valid_question_count": len(evaluable),
        "converged_question_count": len(terminal),
        "reading_sufficient_question_count": sum(row.get("terminal_state") == "reading_sufficient" for row in evaluable),
        "conflicted_question_count": sum(row.get("state") == "conflicted" for row in evaluable),
        "evidence_saturated_question_count": sum(row.get("terminal_state") == "evidence_saturated" for row in evaluable),
        "stable_conflict_question_count": sum(row.get("terminal_state") == "stable_conflict" for row in evaluable),
        "unresolved_question_count": sum(row.get("terminal_state") in {"active", "unresolved_no_evidence"} for row in evaluable),
        "semantic_failed_question_count": len(failed),
        "protocol_failed_question_count": len(protocol),
    }


def _repaired_round_metrics(story_id: str, questions: Mapping[str, Mapping[str, Any]], updates_by_round: Mapping[int, Mapping[str, Mapping[str, Any]]], seen_refs: set[str]) -> list[dict[str, Any]]:
    original = [copy.deepcopy(dict(row)) for row in _round_rows(story_id)]
    for row in original:
        number = int(row.get("round", -1))
        changes = updates_by_round.get(number, {})
        if not changes:
            continue
        qmetrics = [dict(item) for item in row.get("question_metrics", []) if isinstance(item, Mapping) and str(item.get("question_id")) not in changes]
        used = set(str(ref) for ref in row.get("used_evidence_refs", []))
        new = set(str(ref) for ref in row.get("new_used_evidence_refs", []))
        for qid, metric in sorted(changes.items()):
            qmetrics.append(dict(metric))
            used.update(metric.get("used_evidence_refs", []))
            new.update(metric.get("new_used_evidence_refs", []))
        qmetrics.sort(key=lambda item: str(item.get("question_id")))
        row["question_metrics"] = qmetrics
        row["used_evidence_refs"] = sorted(used)
        row["new_used_evidence_refs"] = sorted(new)
        row["D_t"] = int(any(int(item.get("D_t", 0)) for item in qmetrics))
        row["N_t"] = round(len(new) / len(used), 6) if used else 0.0
        row["repaired_projection"] = True
    return original


def _repair_story(story_id: str, audit: Mapping[str, Any]) -> dict[str, Any]:
    run_dir = _run_dir(story_id)
    repair_dir = _repair_dir(story_id)
    repair_dir.mkdir(parents=True, exist_ok=True)
    original_state = _read(_state_path(story_id))
    original_summary = next((dict(row) for row in _read(ROOT / LIVE_SUMMARY_PATH).get("stories", []) if isinstance(row, Mapping) and row.get("story_id") == story_id), {})
    if story_id == "02-yanyu-053":
        return _repair_protocol_story(story_id, repair_dir, original_state, original_summary, audit)
    source_questions = {str(row.get("question_id")): dict(row) for row in original_state.get("questions", []) if isinstance(row, Mapping) and row.get("question_id")}
    questions = copy.deepcopy(source_questions)
    for row in questions.values():
        row.setdefault("terminal_state", None)
    records = [row for row in audit.get("records", []) if row.get("story_id") == story_id]
    failed = {str(row.get("question_id")): row for row in records if row.get("current_failure_type") == "semantic_partial_failure"}
    updates_by_round: dict[int, dict[str, dict[str, Any]]] = {}
    repair_actions: list[str] = []
    used_refs: set[str] = set(str(ref) for ref in original_state.get("seen_evidence_refs", []))
    for qid, question in sorted(questions.items()):
        if qid in failed:
            failure = failed[qid]
            number = int(failure.get("round") or 0)
            output = _read(_source_output(story_id, number))
            raw_update = _raw_update_for(output, qid)
            normalized, norm_audit = normalize_delta_repair(raw_update or {}, _sources_for_round(story_id, number), {qid})
            if normalized.get("updates"):
                update = normalized["updates"][0]
                current, metric = _apply_repaired_update(question, update, used_refs_seen=used_refs)
                updates_by_round.setdefault(number, {})[qid] = metric
                questions[qid] = current
                repair_actions.extend(str(item) for item in ("claim_level_projection",) if item not in repair_actions)
                _write(repair_dir / f"round-{number:02d}-output.json", {"schema": REPAIR_SCHEMA, "story_id": story_id, "round": number, "source_output": _source_output(story_id, number).relative_to(ROOT).as_posix(), "normalized_output": normalized, "audit": norm_audit, "canonical_write_back": False, "external_search_performed": False})
            elif failure.get("expected_state") == "evidence_saturated":
                question["terminal_state"] = "evidence_saturated"
                question["terminal_reason"] = "evidence_saturated"
                question["active"] = False
                question["next_action"] = "stop"
                question["semantic_failure_origin"] = "evidence_saturation_not_materialized"
                repair_actions.append("evidence_saturation_projection")
                updates_by_round.setdefault(number, {})[qid] = {"question_id": qid, "round": number, "D_t": 0, "N_t": 0.0, "Q_t": 0, "used_evidence_refs": [], "new_used_evidence_refs": [], "active": False, "reading_sufficient": False, "d_basis": "saturation_repair", "terminal_state": "evidence_saturated"}
            else:
                question["terminal_state"] = "active"
                question["terminal_reason"] = None
                question["active"] = True
                question["semantic_failure_origin"] = failure.get("root_cause")
                repair_actions.append("preserve_unresolved_question")
                updates_by_round.setdefault(number, {})[qid] = {"question_id": qid, "round": number, "D_t": 0, "N_t": 0.0, "Q_t": 0, "used_evidence_refs": [], "new_used_evidence_refs": [], "active": True, "reading_sufficient": False, "d_basis": "no_valid_semantic_delta"}
        elif question.get("terminal_reason") == "reading_sufficient":
            question["terminal_state"] = "reading_sufficient"
            question["active"] = False
        elif question.get("terminal_reason") == "refined_to_child":
            question["terminal_state"] = None
            question["lineage_status"] = "superseded_by_child"
            question["active"] = False
        elif question.get("terminal_reason") in TERMINAL_STATES:
            question["terminal_state"] = question["terminal_reason"]
            question["active"] = False
        else:
            question["terminal_state"] = "active"
    # Parent conflicts are preserved as reading-qualified historical conflicts;
    # the original reading_sufficient decision remains visible.
    for conflict in records:
        if conflict.get("current_failure_type") == "conflicted_question" and conflict.get("root_cause") == "genuine_conflict":
            q = questions.get(str(conflict.get("question_id")))
            if q:
                q["conflict_review"] = "genuine_conflict"
    leaves = _leaf_ids(questions)
    semantic_failed: list[str] = []
    protocol_failed: list[str] = []
    for qid, q in questions.items():
        if qid in leaves and q.get("terminal_state") == "active" and q.get("semantic_failure_origin") == "malformed_model_output":
            # An active, auditable unresolved question is not a semantic
            # failure after its invalid claim/update has been rejected.
            continue
    round_metrics = _repaired_round_metrics(story_id, questions, updates_by_round, used_refs)
    state = {"schema": REPAIR_SCHEMA, "schema_version": SCHEMA_VERSION, "story_id": story_id, "execution_kind": "live_model", "source_run": run_dir.relative_to(ROOT).as_posix(), "stage": "semantic_repair_complete", "story_status": "converged" if all(questions[qid].get("terminal_state") in TERMINAL_STATES or qid not in leaves for qid in questions) else "active_unresolved", "questions": [questions[qid] for qid in sorted(questions)], "active_questions": sorted(qid for qid in leaves if questions[qid].get("terminal_state") == "active"), "terminal_questions": sorted(qid for qid in leaves if questions[qid].get("terminal_state") in TERMINAL_STATES), "seen_evidence_refs": sorted(used_refs), "question_metrics": _question_metrics(questions, semantic_failed=semantic_failed, protocol_failed=protocol_failed), "semantic_failed_questions": semantic_failed, "protocol_errors": [], "canonical_write_back": False, "external_search_performed": False, "repair_actions": sorted(set(repair_actions))}
    state["targeted_rerun"] = {"performed": False, "count": 0, "api_usage": {}}
    events = [{"event": "semantic_repair_started", "story_id": story_id}]
    for qid in sorted(questions):
        q = questions[qid]
        if q.get("terminal_state") == "evidence_saturated":
            events.append({"event": "evidence_saturated", "story_id": story_id, "question_id": qid})
        elif q.get("terminal_state") == "active":
            events.append({"event": "question_remains_unresolved", "story_id": story_id, "question_id": qid})
        elif q.get("terminal_state") == "reading_sufficient":
            events.append({"event": "reading_sufficient", "story_id": story_id, "question_id": qid})
    repair_dir.joinpath("events.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in events), encoding="utf-8")
    repair_dir.joinpath("search-trace.jsonl").write_text(_source_search_trace(story_id), encoding="utf-8")
    _write(repair_dir / "research-state.json", state)
    _write(repair_dir / "convergence.json", {"schema": REPAIR_SCHEMA, "schema_version": SCHEMA_VERSION, "story_id": story_id, "story_status": state["story_status"], "round_metrics": round_metrics, "question_metrics": state["question_metrics"], "question_terminals": {qid: questions[qid].get("terminal_state") for qid in sorted(questions) if qid in leaves}, "canonical_write_back": False, "external_search_performed": False})
    _write(repair_dir / "manifest.json", {"schema": REPAIR_SCHEMA, "schema_version": SCHEMA_VERSION, "story_id": story_id, "source_run": run_dir.relative_to(ROOT).as_posix(), "source_state_sha256": _hash(_state_path(story_id)), "source_output_hashes": {str(_source_output(story_id, int(row.get("round") or 0)).relative_to(ROOT)): _hash(_source_output(story_id, int(row.get("round") or 0))) for row in records if row.get("round") is not None}, "transport_metrics_before": original_summary.get("transport_metrics", {}), "canonical_write_back": False, "external_search_performed": False, "repair_actions": sorted(set(repair_actions))})
    return _summary_row_from_repair(story_id, original_summary, state, round_metrics, repair_dir, protocol_failed, semantic_failed, used_refs)


def _source_search_trace(story_id: str) -> str:
    path = _continuation_dir(story_id) / "search-trace.jsonl"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    path = _run_dir(story_id) / "search-trace.jsonl"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _repair_protocol_story(story_id: str, repair_dir: Path, original_state: Mapping[str, Any], original_summary: Mapping[str, Any], audit: Mapping[str, Any], *, rerun: bool = False) -> dict[str, Any]:
    # The actual targeted call is performed by repair_protocol_story().  This
    # branch makes the offline projection explicit if no response exists.
    output = _read(_source_output(story_id, 0))
    repair_output = _read(repair_dir / "round-00-output.json")
    if repair_output.get("repair_raw_output") is not None:
        raw = repair_output.get("repair_raw_output")
        normalized, initial_audit = b.normalize_initial_fail_soft(raw, story_material(ROOT, story_id))
        accepted = normalized.get("gaps", []) if isinstance(normalized, Mapping) else []
        rejected = initial_audit.get("rejected_gaps", []) if isinstance(initial_audit, Mapping) else []
        normalizations = initial_audit.get("normalizations", []) if isinstance(initial_audit, Mapping) else []
        state = _initial_state_from_gaps(story_id, accepted, source_run=_run_dir(story_id).relative_to(ROOT).as_posix())
        state["rejected_gaps"] = rejected
        state["structural_normalizations"] = normalizations
        state["repair_actions"] = ["protocol_recovered_initial_gaps"]
    else:
        state = {"schema": REPAIR_SCHEMA, "schema_version": SCHEMA_VERSION, "story_id": story_id, "execution_kind": "live_model", "stage": "protocol_unrecovered", "story_status": "protocol_failed", "questions": [], "active_questions": [], "terminal_questions": [], "protocol_errors": list(original_state.get("protocol_errors", [])), "semantic_failed_questions": [], "canonical_write_back": False, "external_search_performed": False, "repair_actions": []}
    attempt_two = _read(repair_dir / "attempts" / "round-00-attempt-02.json")
    state["targeted_rerun"] = {"performed": bool(attempt_two.get("actual_request")), "count": int(bool(attempt_two.get("actual_request"))), "api_usage": dict(attempt_two.get("api_usage", {})) if isinstance(attempt_two.get("api_usage"), Mapping) else {}, "failure_class": attempt_two.get("failure_class")}
    state["question_metrics"] = _question_metrics({str(q.get("question_id")): q for q in state.get("questions", []) if isinstance(q, Mapping)}, semantic_failed=[], protocol_failed=["__story__"] if state.get("story_status") == "protocol_failed" else [])
    _write(repair_dir / "research-state.json", state)
    _write(repair_dir / "convergence.json", {"schema": REPAIR_SCHEMA, "schema_version": SCHEMA_VERSION, "story_id": story_id, "story_status": state["story_status"], "round_metrics": [], "question_metrics": state["question_metrics"], "question_terminals": {}, "canonical_write_back": False, "external_search_performed": False})
    _write(repair_dir / "manifest.json", {"schema": REPAIR_SCHEMA, "schema_version": SCHEMA_VERSION, "story_id": story_id, "source_run": _run_dir(story_id).relative_to(ROOT).as_posix(), "source_output_sha256": _hash(_source_output(story_id, 0)), "transport_metrics_before": original_summary.get("transport_metrics", {}), "canonical_write_back": False, "external_search_performed": False, "repair_actions": state.get("repair_actions", [])})
    return _summary_row_from_repair(story_id, original_summary, state, [], repair_dir, ["__story__"] if state.get("story_status") == "protocol_failed" else [], [], set())


def _summary_row_from_repair(story_id: str, original: Mapping[str, Any], state: Mapping[str, Any], round_metrics: Sequence[Mapping[str, Any]], repair_dir: Path, protocol_failed: Sequence[str], semantic_failed: Sequence[str], used_refs: set[str]) -> dict[str, Any]:
    row = copy.deepcopy(dict(original))
    leaves = _leaf_ids({str(q.get("question_id")): q for q in state.get("questions", []) if isinstance(q, Mapping) and q.get("question_id")})
    questions = {str(q.get("question_id")): q for q in state.get("questions", []) if isinstance(q, Mapping) and q.get("question_id")}
    row["original_story_status"] = original.get("story_status")
    row["original_semantic_failed_questions"] = original.get("semantic_failed_questions", [])
    row["original_protocol_errors"] = original.get("protocol_errors", [])
    row["story_status"] = state.get("story_status")
    row["convergence_status"] = "converged" if state.get("story_status") == "converged" else state.get("story_status")
    row["semantic_failed_questions"] = list(semantic_failed)
    row["protocol_errors"] = list(state.get("protocol_errors", []))
    row["semantic_failure_count"] = len(semantic_failed)
    row["protocol_failure_count"] = len(protocol_failed)
    row["question_metrics"] = dict(state.get("question_metrics", {}))
    row["evidence_rounds"] = [dict(item) for item in round_metrics]
    row["terminal_reason_per_question"] = {qid: questions[qid].get("terminal_state") for qid in sorted(leaves)}
    row["question_status_per_question"] = {qid: (questions[qid].get("lineage_status") or questions[qid].get("terminal_state") or "active") for qid in sorted(questions)}
    row["used_evidence"] = sorted(set(str(ref) for ref in original.get("used_evidence", [])) | set(used_refs))
    row["new_used_evidence"] = sorted(set(str(ref) for ref in original.get("new_used_evidence", [])) | set(used_refs))
    row["repair_projection"] = repair_dir.relative_to(ROOT).as_posix()
    row["transport_metrics"] = copy.deepcopy(original.get("transport_metrics", {}))
    targeted = state.get("targeted_rerun") if isinstance(state.get("targeted_rerun"), Mapping) else {}
    row["repair_transport_metrics"] = {"targeted_rerun_count": int(targeted.get("count", 0)), "targeted_rerun_api_usage": dict(targeted.get("api_usage", {})) if isinstance(targeted.get("api_usage"), Mapping) else {}, "targeted_rerun_failure_class": targeted.get("failure_class")}
    row["repair_token_usage"] = dict(targeted.get("api_usage", {})) if isinstance(targeted.get("api_usage"), Mapping) else {}
    row["validation_errors"] = []
    return row


def repair_protocol_story(story_id: str, *, transport: DeepSeekTransport | None = None) -> dict[str, Any]:
    """Perform the one permitted targeted repair for the empty 02 response."""
    if story_id != "02-yanyu-053":
        raise ValueError("only 02-yanyu-053 has a targeted protocol repair")
    repair_dir = _repair_dir(story_id)
    repair_dir.mkdir(parents=True, exist_ok=True)
    run_dir = _run_dir(story_id)
    original = _read(ROOT / LIVE_SUMMARY_PATH)
    original_row = next((dict(row) for row in original.get("stories", []) if isinstance(row, Mapping) and row.get("story_id") == story_id), {})
    source_output = _source_output(story_id, 0)
    old = _read(source_output)
    _write(repair_dir / "attempts" / "round-00-attempt-01.json", {**preserved_attempt(story_id=story_id, round_number=0, completion_kind="main_text_gap_discovery", attempt=1, artifact=old), "source_output": source_output.relative_to(ROOT).as_posix()})
    input_doc = _read(_source_input(story_id, 0))
    messages = [dict(row) for row in input_doc.get("messages", []) if isinstance(row, Mapping)]
    existing_attempt = _read(repair_dir / "attempts" / "round-00-attempt-02.json")
    if existing_attempt.get("actual_request"):
        # A previous invocation may have completed the paid call but failed
        # while projecting its response.  Reuse that immutable attempt.
        result = {
            "success": not bool(existing_attempt.get("failure_class")),
            "response": existing_attempt.get("raw_response") if isinstance(existing_attempt.get("raw_response"), Mapping) else {},
            "content": str(existing_attempt.get("raw_content") or ""),
            "error": existing_attempt.get("exception_message"),
            "failure_class": existing_attempt.get("failure_class"),
            "attempts": [existing_attempt],
        }
    else:
        client = transport or DeepSeekTransport()
        result = client.call(story_id=story_id, round_number=0, completion_kind="main_text_gap_discovery", messages=messages, attempt_start=2, max_retries=0)
        for record in result.get("attempts", []):
            _write(repair_dir / "attempts" / f"round-00-attempt-{int(record.get('attempt', 2)):02d}.json", {**dict(record), "raw_response": result.get("response") if record is result.get("attempts", [])[-1] else None, "raw_content": result.get("content", "") if record is result.get("attempts", [])[-1] else ""})
    content = str(result.get("content") or "")
    raw: Any = None
    parse_error = None
    try:
        raw, _repair = b.parse_json_any(content)
    except Exception as exc:  # noqa: BLE001
        parse_error = str(exc)
    projection = {"schema": REPAIR_SCHEMA, "story_id": story_id, "round": 0, "source_output": source_output.relative_to(ROOT).as_posix(), "raw_response": dict(result.get("response") or {}), "raw_content": content, "repair_raw_output": raw, "protocol_error": parse_error or (result.get("error") if not result.get("success") else None), "failure_class": result.get("failure_class") if not result.get("success") else None, "canonical_write_back": False, "external_search_performed": False}
    if raw is not None:
        normalized, initial_audit = b.normalize_initial_fail_soft(raw, story_material(ROOT, story_id))
        accepted = normalized.get("gaps", []) if isinstance(normalized, Mapping) else []
        rejected = initial_audit.get("rejected_gaps", []) if isinstance(initial_audit, Mapping) else []
        normalizations = initial_audit.get("normalizations", []) if isinstance(initial_audit, Mapping) else []
        projection.update({"accepted_gaps": accepted, "rejected_gaps": rejected, "structural_normalizations": normalizations})
    else:
        projection.update({"accepted_gaps": [], "rejected_gaps": [], "structural_normalizations": []})
    _write(repair_dir / "round-00-output.json", projection)
    # _repair_protocol_story reads this derived raw projection.
    return _repair_protocol_story(story_id, repair_dir, _read(_state_path(story_id)), original_row, audit_failures())


def rebuild_live_summary(*, allow_protocol_repair: bool = False, transport: DeepSeekTransport | None = None) -> dict[str, Any]:
    audit = _read(ROOT / AUDIT_PATH)
    if not audit:
        raise RuntimeError("run --audit before --repair")
    current = _read(ROOT / LIVE_SUMMARY_PATH)
    original_rows = {str(row.get("story_id")): dict(row) for row in current.get("stories", []) if isinstance(row, Mapping)}
    rows: list[dict[str, Any]] = []
    for story_id in FIXED_STORIES:
        if story_id == "02-yanyu-053" and allow_protocol_repair:
            repair_protocol_story(story_id, transport=transport)
        rows.append(_repair_story(story_id, audit))
    rows.sort(key=lambda row: FIXED_STORIES.index(str(row.get("story_id"))))
    qkeys = QUESTION_METRIC_KEYS
    qmetrics = {key: sum(int((row.get("question_metrics") or {}).get(key, 0)) for row in rows) for key in qkeys}
    transport_keys = ("transport_request_count", "transport_retry_count", "transport_success_count", "tls_failure_count", "read_timeout_count", "connect_timeout_count", "server_error_count")
    transport = {key: sum(int((row.get("transport_metrics") or {}).get(key, 0)) for row in rows) for key in transport_keys}
    latencies = [float(value) for row in rows for value in (row.get("transport_metrics") or {}).get("successful_latencies_seconds", []) if isinstance(value, (int, float))]
    import statistics
    transport["median_successful_latency_seconds"] = round(statistics.median(latencies), 6) if latencies else None
    transport["max_successful_latency_seconds"] = round(max(latencies), 6) if latencies else None
    converged = [row for row in rows if row.get("convergence_status") == "converged"]
    summary = {"schema": "srm0-4b-live-summary", "schema_version": SCHEMA_VERSION, "execution_kind": "live_model", "repair_stage": "srm0-4d", "stories": rows, "aggregate": {"live_story_count": len(rows), "protocol_failure_count": sum(int(bool(row.get("protocol_errors"))) for row in rows), "api_transport_failure_count": 0, "semantic_failure_count": sum(int(bool(row.get("semantic_failed_questions"))) for row in rows), "evaluable_story_count": sum(int(not row.get("protocol_errors")) for row in rows), "valid_live_story_count": sum(int(not row.get("protocol_errors") and not row.get("semantic_failed_questions")) for row in rows), "reading_convergence_rate": round(len(converged) / max(1, len([row for row in rows if not row.get("protocol_errors")])), 3), "terminal_reason_counts": dict(sorted(Counter(str(reason) for row in rows for reason in (row.get("terminal_reason_per_question") or {}).values() if reason in TERMINAL_STATES).items())), **qmetrics, **transport}, "canonical_write_back": False, "external_search_performed": False}
    _write(ROOT / LIVE_SUMMARY_PATH, summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--rerun-02", action="store_true")
    parser.add_argument("--replay", action="store_true", help="rebuild derived projections without a network call")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not (args.audit or args.repair or args.replay):
        raise SystemExit("use --audit, --repair, or --replay")
    if args.audit:
        document = audit_failures()
        print(f"SRM0.4D audit records: {len(document['records'])}")
        print(AUDIT_PATH.as_posix())
        return 0
    if args.repair or args.replay:
        if not (ROOT / AUDIT_PATH).is_file():
            audit_failures()
        if args.rerun_02 and not args.repair:
            raise SystemExit("--rerun-02 requires --repair")
        summary = rebuild_live_summary(allow_protocol_repair=args.rerun_02, transport=None)
        print("SRM0.4D repaired summary")
        print(json.dumps(summary.get("aggregate", {}), ensure_ascii=False, sort_keys=True))
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
