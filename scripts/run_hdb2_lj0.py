#!/usr/bin/env python3
"""Run the isolated HDB2-LJ0 grounded identity inference experiment.

This runner never calls the HDB2 controller, never updates its queue, and
never writes canonical data.  It freezes a small review-queue selection,
performs one evidence-scoring call plus one independent falsification call
for cases with plausible candidates, and stores immutable raw responses in a
separate LJ0 namespace.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hdb2_lj0_common as common  # noqa: E402
import hng2_schema_controller as controller  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402


OUT_ROOT = ROOT / "data/generated/hdb2-lj0"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def usage(response: Mapping[str, Any] | None) -> dict[str, int]:
    raw = response.get("usage") if isinstance(response, Mapping) and isinstance(response.get("usage"), Mapping) else {}
    return {key: int(raw.get(key) or 0) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}


def finish_reason(response: Mapping[str, Any]) -> str | None:
    choices = response.get("choices") if isinstance(response, Mapping) else None
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        return str(choices[0].get("finish_reason") or "") or None
    return None


def safe_error(exc: Exception) -> dict[str, Any]:
    message = str(exc)
    secret = os.environ.get("DEEPSEEK_API_KEY")
    if secret:
        message = message.replace(secret, "[REDACTED]")
    return {
        "exception_class": type(exc).__name__,
        "exception_message": message[:1000],
        "http_status": getattr(exc, "http_status", None),
        "provider_error_body": str(getattr(exc, "provider_error_body", "") or "")[:1000],
    }


def protected_hashes() -> dict[str, str]:
    names = [
        "data/people.json",
        "data/relations.json",
        "data/personStory.json",
        "data/annotation/hdb2-f-review-queue.json",
        "data/derived/hdb2-f-occurrence-ledger.json",
        "data/derived/hdb2-f-occurrence-cases.json",
        "data/derived/hdb2-f-occurrence-decisions.json",
        "data/derived/hdb2-f-relation-projection.json",
        "data/derived/hdb2-f-kinship-projection.json",
        "data/derived/hdb2-f-marriage-projection.json",
        "data/derived/hdb2-f-office-projection.json",
        "data/derived/hdb2-f-person-knowledge.json",
        "site/public/generated/review/hdb2/index.json",
    ]
    return {name: common.file_hash(ROOT / name) for name in names}


def preflight() -> dict[str, Any]:
    started = time.monotonic()
    record: dict[str, Any] = {
        "status": "unknown",
        "model": common.MODEL,
        "endpoint": common.STRICT_ENDPOINT,
        "started_at": utc_now(),
    }
    try:
        response = call_deepseek(
            [{"role": "user", "content": "Reply only with OK."}],
            model=common.MODEL,
            temperature=0,
            thinking={"type": "disabled"},
            max_tokens=16,
            timeout=60,
            endpoint=common.STRICT_ENDPOINT,
        )
        record.update({"status": "reachable", "response_model": response.get("model"), "usage": usage(response)})
    except Exception as exc:
        record.update({"status": "provider_request_failure", **safe_error(exc)})
    record.update({"elapsed_seconds": round(time.monotonic() - started, 3), "ended_at": utc_now()})
    return record


def _raw_path(raw_dir: Path, sequence: int, call_type: str, attempt: int) -> Path:
    return raw_dir / f"{sequence:04d}-{call_type}-attempt{attempt}.json"


def _call(
    *,
    case: Mapping[str, Any],
    packet: Mapping[str, Any],
    call_type: str,
    sequence: int,
    raw_dir: Path,
    tool: Mapping[str, Any],
    tool_choice: Mapping[str, Any],
    system_prompt: str,
    max_tokens: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    request = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(packet, ensure_ascii=False, sort_keys=True)},
        ],
        "model": common.MODEL,
        "temperature": 0,
        "thinking": {"type": "disabled"},
        "max_tokens": max_tokens,
        "endpoint": common.STRICT_ENDPOINT,
        "tools": [dict(tool)],
        "tool_choice": dict(tool_choice),
    }
    record: dict[str, Any] = {
        "sequence": sequence,
        "call_type": call_type,
        "occurrence_id": case.get("occurrence_id"),
        "story_id": case.get("story_id"),
        "target_surface": case.get("target_surface"),
        "model": common.MODEL,
        "prompt_version": common.PROMPT_VERSION,
        "input_hash": common.stable_hash(packet),
        "attempts": [],
    }
    payload: dict[str, Any] = {}
    validation: dict[str, Any] = {"valid": False, "errors": ["not_called"]}
    for attempt in (1, 2):
        started = time.monotonic()
        attempt_row: dict[str, Any] = {"attempt": attempt, "started_at": utc_now()}
        try:
            response = call_deepseek(
                request["messages"],
                model=common.MODEL,
                temperature=0,
                thinking={"type": "disabled"},
                max_tokens=max_tokens,
                timeout=180,
                endpoint=common.STRICT_ENDPOINT,
                tools=[dict(tool)],
                tool_choice=dict(tool_choice),
            )
            path = _raw_path(raw_dir, sequence, call_type, attempt)
            if path.exists():
                raise RuntimeError(f"immutable_raw_response_exists:{path.name}")
            common.write_json(path, response)
            finish = finish_reason(response)
            attempt_row.update({
                "classification": "response",
                "finish_reason": finish,
                "usage": usage(response),
                "raw_path": str(path.relative_to(ROOT)),
            })
            if finish == "length":
                attempt_row["classification"] = "response_truncated"
                record["attempts"].append(attempt_row)
                break
            expected = common.EVALUATION_FUNCTION if call_type == "evaluation" else common.FALSIFICATION_FUNCTION
            extracted, channel, parse_error = controller.extract_strict_tool_payload(response, expected_function_name=expected)
            attempt_row["response_channel"] = channel
            if parse_error or not isinstance(extracted, Mapping):
                attempt_row.update({"classification": "response_parse_failure", "parse_error": parse_error or "payload_not_object"})
                record["attempts"].append(attempt_row)
                if attempt == 1:
                    continue
                break
            payload = dict(extracted)
            leading = None
            if call_type == "falsification":
                leading = str(packet.get("falsification_target", {}).get("leading_candidate_key") or "") or None
                validation = common.validate_falsification(payload, case, leading)
            else:
                validation = common.validate_evaluation(payload, case)
            attempt_row.update({
                "classification": "parsed",
                "validation": {"valid": validation.get("valid"), "errors": validation.get("errors", [])},
            })
            record["attempts"].append(attempt_row)
            break
        except Exception as exc:
            attempt_row.update({"classification": "provider_request_failure", **safe_error(exc)})
            record["attempts"].append(attempt_row)
            if attempt == 1:
                continue
        finally:
            attempt_row["elapsed_seconds"] = round(time.monotonic() - started, 3)
            attempt_row["ended_at"] = utc_now()
    record["classification"] = record["attempts"][-1].get("classification") if record["attempts"] else "provider_request_failure"
    record["retry_count"] = max(0, len(record["attempts"]) - 1)
    record["usage"] = {
        key: sum(int((row.get("usage") or {}).get(key) or 0) for row in record["attempts"])
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }
    record["elapsed_seconds"] = round(sum(float(row.get("elapsed_seconds") or 0) for row in record["attempts"]), 3)
    record["request_hash"] = common.stable_hash(request)
    model_record = {
        "sequence": sequence,
        "call_type": call_type,
        "occurrence_id": case.get("occurrence_id"),
        "payload": payload,
        "validation": validation,
        "classification": record["classification"],
        "request_hash": record["request_hash"],
    }
    return record, model_record


def _empty_decision(case: Mapping[str, Any], reason: str, errors: list[str] | None = None) -> dict[str, Any]:
    return {
        "occurrence_id": case.get("occurrence_id"),
        "story_id": case.get("story_id"),
        "surface": case.get("target_surface"),
        "ranked_candidates": [],
        "leading_candidate_key": None,
        "result_state": "genuinely_unresolved",
        "reason": reason,
        "validation_errors": list(errors or []),
        "hard_conflicts_found": 0,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def build_comparison(cases: list[Mapping[str, Any]], decisions: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Compare the experimental result with the frozen HDB2 review proposal.

    This is deliberately a diagnostic projection.  It does not alter the
    HDB2 queue and it does not treat the current reviewer proposal as gold
    truth; it only records agreement/disagreement for audit.
    """
    review_items = {str(row.get("occurrence_id")): row for row in common.load_review_items()}
    rows: list[dict[str, Any]] = []
    for case, decision in zip(cases, decisions):
        occurrence_id = str(case.get("occurrence_id"))
        item = review_items.get(occurrence_id, {})
        proposed = item.get("proposed_identity") or {}
        ranked = list(decision.get("ranked_candidates") or [])
        top = ranked[0] if ranked else {}
        current_label = str(proposed.get("label") or "") or None
        experimental_label = str(top.get("candidate") or "") or None
        agrees = bool(
            current_label
            and experimental_label
            and common.matching(current_label) == common.matching(experimental_label)
        )
        rows.append({
            "occurrence_id": occurrence_id,
            "story_id": case.get("story_id"),
            "surface": case.get("target_surface"),
            "review_type": case.get("current_review_type"),
            "current_status": item.get("status") or (item.get("current_state") or {}).get("status"),
            "current_proposed_label": current_label,
            "current_proposed_person_id": proposed.get("person_id"),
            "experimental_state": decision.get("result_state"),
            "experimental_top_candidate": experimental_label,
            "experimental_top_candidate_person_id": top.get("candidate_person_id"),
            "experimental_top_score": top.get("identity_score"),
            "agrees_with_current_proposal": agrees,
            "comparison": "proposal_agreement" if agrees else "proposal_not_confirmed",
            "candidate_only": True,
            "canonical_write_back": False,
        })
    agreement = sum(bool(row.get("agrees_with_current_proposal")) for row in rows)
    return {
        "schema": "hdb2-lj0-comparison-v1",
        "note": "Comparison with the current HDB2 reviewer proposal is diagnostic, not a gold label.",
        "records": rows,
        "experiment_item_count": len(rows),
        "high_confidence_current_proposal_agreement": sum(
            row.get("experimental_state") == "high_confidence_contextual"
            and row.get("agrees_with_current_proposal")
            for row in rows
        ),
        "proposal_agreement_count": agreement,
        "proposal_disagreement_count": len(rows) - agreement,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def replay(run_dir: Path) -> Path:
    """Revalidate and rescore frozen LJ0 responses without any API call."""
    cases_doc = common.read_json(run_dir / "cases.json", {}) or {}
    cases = list(cases_doc.get("cases", []))
    case_by_id = {str(case.get("occurrence_id")): case for case in cases}
    eval_doc = common.read_json(run_dir / "evaluation-results.json", {}) or {}
    fals_doc = common.read_json(run_dir / "falsification-results.json", {}) or {}
    eval_rows = [dict(row) for row in eval_doc.get("records", [])]
    fals_rows = [dict(row) for row in fals_doc.get("records", [])]
    eval_by_id: dict[str, dict[str, Any]] = {}
    fals_by_id: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    for row in eval_rows:
        case = case_by_id.get(str(row.get("occurrence_id")))
        if not case:
            continue
        validation = common.validate_evaluation(row.get("payload") or {}, case)
        row["validation"] = validation
        eval_by_id[str(row.get("occurrence_id"))] = row
        if validation.get("valid") is not True:
            failures.append({"occurrence_id": row.get("occurrence_id"), "call_type": "evaluation", "errors": list(validation.get("errors", []))})
    for row in fals_rows:
        case = case_by_id.get(str(row.get("occurrence_id")))
        if not case:
            continue
        payload = row.get("payload") or {}
        leading = str(payload.get("leading_candidate_key") or "") or None
        validation = common.validate_falsification(payload, case, leading)
        row["validation"] = validation
        fals_by_id[str(row.get("occurrence_id"))] = row
        if validation.get("valid") is not True:
            failures.append({"occurrence_id": row.get("occurrence_id"), "call_type": "falsification", "errors": list(validation.get("errors", []))})
    decisions: list[dict[str, Any]] = []
    for case in cases:
        occurrence_id = str(case.get("occurrence_id"))
        evaluation_row = eval_by_id.get(occurrence_id)
        if not evaluation_row or (evaluation_row.get("validation") or {}).get("valid") is not True:
            reason = "no_evaluation_call" if not evaluation_row else "evaluation_validation_failure"
            errors = [] if not evaluation_row else list((evaluation_row.get("validation") or {}).get("errors", []))
            decisions.append(_empty_decision(case, reason, errors))
            continue
        payload = evaluation_row.get("payload") or {}
        initial = common.score_evaluations(case, payload, {"outcome": "inconclusive", "comparably_plausible_candidate_keys": []})
        leading = initial.get("leading_candidate_key")
        fals_row = fals_by_id.get(occurrence_id)
        fals_valid = bool(fals_row and (fals_row.get("validation") or {}).get("valid") is True)
        fals_payload = dict(fals_row.get("payload") or {}) if fals_valid and fals_row else {}
        result = common.score_evaluations(case, payload, fals_payload)
        if leading is not None and not fals_valid:
            result["result_state"] = "review_required"
            result["reason"] = "falsification_validation_failure"
        result["evaluation_call_valid"] = True
        result["falsification_call_valid"] = fals_valid
        result["candidate_only"] = True
        result["canonical_write_back"] = False
        decisions.append(result)
    old_metrics = common.read_json(run_dir / "metrics.json", {}) or {}
    metrics = dict(old_metrics)
    refreshed = common.aggregate_metrics(cases, decisions, total_review_count=int(old_metrics.get("current_review_count") or 73), call_records=[])
    for key in ("current_review_count", "experiment_item_count", "experiment_baseline_review_count", "new_review_count", "pilot_net_review_reduction", "high_confidence_resolutions", "true_ambiguities", "hard_conflicts_found", "result_states", "review_types", "median_latency_seconds", "max_latency_seconds"):
        metrics[key] = refreshed[key]
    comparison = build_comparison(cases, decisions)
    metrics["high_confidence_current_proposal_agreement"] = comparison["high_confidence_current_proposal_agreement"]
    metrics["proposal_agreement_count"] = comparison["proposal_agreement_count"]
    metrics["proposal_disagreement_count"] = comparison["proposal_disagreement_count"]
    metrics["validation_failures"] = len(failures)
    metrics["replayed_without_api"] = True
    common.write_json(run_dir / "evaluation-results.json", {"records": eval_rows, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "falsification-results.json", {"records": fals_rows, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "decisions.json", {"records": decisions, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "comparison.json", comparison)
    common.write_json(run_dir / "validation-failures.json", {"records": failures, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "metrics.json", metrics)
    summary = common.read_json(run_dir / "validation-summary.json", {}) or {}
    summary["validation_failures"] = len(failures)
    summary["replayed_without_api"] = True
    common.write_json(run_dir / "validation-summary.json", summary)
    manifest = common.read_json(run_dir / "manifest.json", {}) or {}
    manifest["replayed_without_api"] = True
    manifest["postprocessing_replay_hash"] = common.stable_hash({"cases": cases_doc, "evaluations": eval_rows, "falsifications": fals_rows, "decisions": decisions})
    common.write_json(run_dir / "manifest.json", manifest)
    print(json.dumps({"run_dir": str(run_dir.relative_to(ROOT)), "replayed_without_api": True, "high_confidence": metrics.get("high_confidence_resolutions", 0), "new_review_count": metrics.get("new_review_count")}, ensure_ascii=False, indent=2, sort_keys=True))
    return run_dir


def run(args: argparse.Namespace) -> Path:
    selection_path = ANNOTATION_SELECTION = ROOT / "data/annotation/hdb2-lj0-selection.json"
    items = common.load_review_items()
    selection = common.freeze_selection(selection_path, items, limit=args.selection_count)
    cases_doc = common.build_cases(selection)
    cases = list(cases_doc.get("cases", []))
    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-HDB2-LJ0"
    run_dir = OUT_ROOT / "live" / run_id
    if run_dir.exists():
        raise RuntimeError(f"hdb2_lj0_run_exists:{run_dir}")
    raw_dir = run_dir / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=False)
    before = protected_hashes()
    packets = []
    for case in cases:
        packets.append({"occurrence_id": case.get("occurrence_id"), "evaluation": common.wire_packet(case)})
    common.write_json(run_dir / "selection.json", selection)
    common.write_json(run_dir / "cases.json", cases_doc)
    common.write_json(run_dir / "prompt-packets.json", {"records": packets, "candidate_only": True, "canonical_write_back": False})

    preflight_record = preflight()
    common.write_json(run_dir / "preflight.json", preflight_record)
    if preflight_record.get("status") != "reachable":
        manifest = {
            "schema": "hdb2-lj0-live-manifest-v1",
            "status": "live_network_unavailable",
            "run_id": run_id,
            "selection_hash": selection.get("selection_hash"),
            "model": common.MODEL,
            "endpoint": common.STRICT_ENDPOINT,
            "semantic_calls": 0,
            "candidate_only": True,
            "canonical_write_back": False,
            "protected_hashes_before": before,
            "protected_hashes_after": protected_hashes(),
            "preflight": preflight_record,
        }
        common.write_json(run_dir / "manifest.json", manifest)
        common.write_json(run_dir / "decisions.json", {"records": [], "candidate_only": True, "canonical_write_back": False})
        common.write_json(run_dir / "metrics.json", common.aggregate_metrics(cases, [], total_review_count=len(items), call_records=[]))
        return run_dir

    call_records: list[dict[str, Any]] = []
    model_evaluations: list[dict[str, Any]] = []
    model_falsifications: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    validation_failures: list[dict[str, Any]] = []
    sequence = 0
    for case in cases:
        if not case.get("candidate_keys"):
            decisions.append(_empty_decision(case, "no_plausible_candidates_after_python_hard_exclusions"))
            continue
        sequence += 1
        eval_record, eval_model = _call(
            case=case,
            packet=common.wire_packet(case),
            call_type="evaluation",
            sequence=sequence,
            raw_dir=raw_dir,
            tool=common.evaluation_tool(),
            tool_choice=common.evaluation_tool_choice(),
            system_prompt=common.EVALUATION_SYSTEM,
            max_tokens=1600,
        )
        call_records.append(eval_record)
        model_evaluations.append(eval_model)
        eval_validation = eval_model.get("validation") or {}
        if eval_validation.get("valid") is not True:
            errors = list(eval_validation.get("errors", []))
            validation_failures.append({"occurrence_id": case.get("occurrence_id"), "call_type": "evaluation", "errors": errors})
            decisions.append(_empty_decision(case, "evaluation_validation_failure", errors))
            continue
        payload = eval_model.get("payload") or {}
        initial = common.score_evaluations(case, payload, {"outcome": "inconclusive", "comparably_plausible_candidate_keys": []})
        leading = initial.get("leading_candidate_key")
        falsification_payload: dict[str, Any] = {}
        falsification_valid = False
        if leading is not None:
            sequence += 1
            falsification_record, falsification_model = _call(
                case=case,
                packet=common.falsification_packet(case, str(leading)),
                call_type="falsification",
                sequence=sequence,
                raw_dir=raw_dir,
                tool=common.falsification_tool(),
                tool_choice=common.falsification_tool_choice(),
                system_prompt=common.FALSIFICATION_SYSTEM,
                max_tokens=800,
            )
            call_records.append(falsification_record)
            model_falsifications.append(falsification_model)
            falsification_valid = (falsification_model.get("validation") or {}).get("valid") is True
            if falsification_valid:
                falsification_payload = dict(falsification_model.get("payload") or {})
            else:
                errors = list((falsification_model.get("validation") or {}).get("errors", []))
                validation_failures.append({"occurrence_id": case.get("occurrence_id"), "call_type": "falsification", "errors": errors})
        result = common.score_evaluations(case, payload, falsification_payload)
        if leading is not None and not falsification_valid:
            result["result_state"] = "review_required"
            result["reason"] = "falsification_validation_failure"
        result["evaluation_call_valid"] = True
        result["falsification_call_valid"] = falsification_valid
        result["candidate_only"] = True
        result["canonical_write_back"] = False
        decisions.append(result)

    after = protected_hashes()
    if before != after:
        raise RuntimeError("hdb2_lj0_protected_input_changed")
    metrics = common.aggregate_metrics(cases, decisions, total_review_count=len(items), call_records=call_records)
    metrics.update({
        "preflight": preflight_record,
        "retries": sum(int(row.get("retry_count") or 0) for row in call_records),
        "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in call_records),
        "parse_failures": sum(row.get("classification") == "response_parse_failure" for row in call_records),
        "truncated_responses": sum(row.get("classification") == "response_truncated" for row in call_records),
        "validation_failures": len(validation_failures),
        "candidate_hard_exclusions": sum(len(case.get("hard_exclusions", [])) for case in cases),
        "high_confidence_threshold": {"min_score": common.MIN_HIGH_SCORE, "min_margin": common.MIN_HIGH_MARGIN, "min_support_families": common.MIN_HIGH_SUPPORT_FAMILIES},
    })
    comparison = build_comparison(cases, decisions)
    metrics.update({
        "high_confidence_current_proposal_agreement": comparison["high_confidence_current_proposal_agreement"],
        "proposal_agreement_count": comparison["proposal_agreement_count"],
        "proposal_disagreement_count": comparison["proposal_disagreement_count"],
    })
    common.write_json(run_dir / "evaluation-results.json", {"records": model_evaluations, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "falsification-results.json", {"records": model_falsifications, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "decisions.json", {"records": decisions, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "comparison.json", comparison)
    common.write_json(run_dir / "validation-failures.json", {"records": validation_failures, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "metrics.json", metrics)
    common.write_json(run_dir / "validation-summary.json", {
        "schema": "hdb2-lj0-validation-summary-v1",
        "selection_hash": selection.get("selection_hash"),
        "review_frontier_unchanged": before == after,
        "hdb2_decisions_modified": False,
        "canonical_write_back": False,
        "candidate_only": True,
        "validation_failures": len(validation_failures),
    })
    manifest = {
        "schema": "hdb2-lj0-live-manifest-v1",
        "run_id": run_id,
        "run_version": common.RUN_VERSION,
        "prompt_version": common.PROMPT_VERSION,
        "model": common.MODEL,
        "temperature": 0,
        "thinking": "disabled",
        "endpoint": common.STRICT_ENDPOINT,
        "selection_hash": selection.get("selection_hash"),
        "occurrence_count": len(cases),
        "semantic_calls": len(call_records),
        "candidate_only": True,
        "canonical_write_back": False,
        "hdb2_decisions_modified": False,
        "protected_hashes_before": before,
        "protected_hashes_after": after,
        "preflight": preflight_record,
        "created_at": utc_now(),
        "raw_api_hashes": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(raw_dir.glob("*.json"))},
    }
    common.write_json(run_dir / "manifest.json", manifest)
    print(json.dumps({"run_dir": str(run_dir.relative_to(ROOT)), "selected": len(cases), "semantic_calls": len(call_records), "high_confidence": metrics.get("high_confidence_resolutions", 0), "new_review_count": metrics.get("new_review_count", len(cases))}, ensure_ascii=False, indent=2, sort_keys=True))
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id")
    parser.add_argument("--selection-count", type=int, default=24)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()
    if args.replay:
        replay(args.replay if args.replay.is_absolute() else ROOT / args.replay)
        return 0
    items = common.load_review_items()
    selection_path = ROOT / "data/annotation/hdb2-lj0-selection.json"
    selection = common.freeze_selection(selection_path, items, limit=args.selection_count)
    cases = common.build_cases(selection)
    if args.prepare_only:
        print(json.dumps({"selection": str(selection_path.relative_to(ROOT)), "selection_hash": selection.get("selection_hash"), "selected": len(cases.get("cases", []))}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
