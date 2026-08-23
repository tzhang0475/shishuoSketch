#!/usr/bin/env python3
"""Resume only SRM0.4B transport failures with a bounded transport retry.

The runner intentionally reuses SRM0.4B's prompts, normalizers, state
derivation, retrieval, and stopping functions.  It writes only under each
existing live run's ``continuation`` directory and never rewrites the old
round artifacts.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ds1_common import ROOT, sha256_file, stable_json, write_json  # noqa: E402
import run_srm0_4b as b  # noqa: E402
from srm0_4b_common import (  # noqa: E402
    FIXED_STORIES,
    LIVE_SUMMARY_PATH,
    MAX_EVIDENCE_ROUNDS,
    MODEL,
    OUTPUT_BASE,
    PROMPT_VERSION,
    PROVIDER,
    SCHEMA_VERSION,
    SEARCHED_CORPORA,
    TRANSPORT_FAILURE_CLASSES,
    build_commentary_messages,
    build_retrieval_messages,
    build_registry,
    derive_state_b,
    evidence_novelty_b,
    make_children_b,
    material_delta_b,
    normalize_delta_fail_soft,
    normalize_initial_fail_soft,
    open_candidates,
    output_directory,
    run_id_for,
    search_registry,
    stop_reason_b,
    story_material,
)
from srm0_4c_transport import (  # noqa: E402
    API_URL,
    CONNECT_TIMEOUT,
    READ_TIMEOUT,
    DeepSeekTransport,
    preserved_attempt,
)


ELIGIBLE_STORIES = (
    "19-xianyuan-010",
    "01-dexing-040",
    "09-pinzao-038",
    "33-youhui-012",
)
PREFLIGHT_PATH = Path("/tmp/srm0-4c-live-preflight.json")


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
    material = story_material(ROOT, story_id)
    return ROOT / output_directory(story_id, execution_kind="live_model", run_id=run_id_for(material))


def _continuation_dir(run_dir: Path) -> Path:
    return run_dir / "continuation"


def _input_artifact(stage: str, number: int, messages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "srm0-4c-model-input",
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "round": number,
        "execution_kind": "live_model",
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "parameters": {"temperature": 0, "response_format": {"type": "json_object"}, "tools": [], "connect_timeout": CONNECT_TIMEOUT, "read_timeout": READ_TIMEOUT},
        "messages": [dict(message) for message in messages],
        "canonical_write_back": False,
        "external_search_performed": False,
    }


def _save_attempt(path: Path, record: Mapping[str, Any], *, response: Mapping[str, Any] | None = None, content: str = "", raw: Any = None, source_output: str | None = None) -> None:
    value = {"schema": "srm0-4c-transport-attempt", "schema_version": SCHEMA_VERSION, **dict(record)}
    if response is not None:
        value["raw_response"] = dict(response)
    if content:
        value["raw_content"] = content
    if raw is not None:
        value["raw_output"] = raw
    if source_output:
        value["source_output"] = source_output
    _write(path, value)


def _preserve_old_attempt(cdir: Path, *, story_id: str, number: int, stage: str, old: Mapping[str, Any], source: Path) -> None:
    target = cdir / "attempts" / f"round-{number:02d}-attempt-01.json"
    if target.exists():
        return
    record = preserved_attempt(story_id=story_id, round_number=number, completion_kind=stage, attempt=1, artifact=old)
    _save_attempt(target, record, source_output=source.as_posix())


def _parse_response(content: str) -> tuple[Any, str, str | None]:
    try:
        raw, repair = b.parse_json_any(content)
        return raw, repair, None
    except Exception as exc:  # noqa: BLE001 - persisted as protocol result
        return None, "error", str(exc)


def _response_content(response: Mapping[str, Any] | None) -> str:
    choices = response.get("choices") if isinstance(response, Mapping) else None
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
        return ""
    message = choices[0].get("message")
    content = message.get("content") if isinstance(message, Mapping) else None
    return content if isinstance(content, str) else ""


def _stage_call(
    *, story_id: str, number: int, stage: str, messages: Sequence[Mapping[str, Any]],
    run_dir: Path, cdir: Path, transport: DeepSeekTransport,
) -> dict[str, Any]:
    """Load a prior stage, or perform only the one permitted continuation."""
    output = run_dir / f"round-{number:02d}-output.json"
    old = _read(output) if output.is_file() else {}
    projected = cdir / f"round-{number:02d}-output.json"
    if projected.is_file():
        saved = _read(projected)
        saved_response = saved.get("raw_response") if isinstance(saved.get("raw_response"), Mapping) else None
        content = _response_content(saved_response) or str(saved.get("raw_content") or "")
        saved_raw = saved.get("raw_output")
        if isinstance(saved_raw, Mapping) and "choices" in saved_raw:
            saved_raw, repair, parse_error = _parse_response(content)
        else:
            repair, parse_error = str(saved.get("json_repair") or "none"), None
        raw = saved_raw
        return {
            "raw": raw, "response": saved.get("raw_response") if isinstance(saved.get("raw_response"), Mapping) else None,
            "content": content, "repair": repair,
            "error": parse_error or saved.get("protocol_error") or saved.get("transport_error"), "failure_class": "protocol_failure" if parse_error else saved.get("failure_class"),
            "api_calls": sum(int(bool(row.get("actual_request"))) for row in saved.get("transport_attempts", []) if isinstance(row, Mapping)), "attempts": [], "reused_continuation": True,
        }
    old_exists = output.is_file()
    old_failure = str(old.get("failure_class") or "")
    old_valid = old_exists and not old_failure and old.get("raw_output") is not None
    input_path = run_dir / f"round-{number:02d}-input.json"
    if input_path.is_file():
        input_doc = _read(input_path)
        old_messages = input_doc.get("messages")
        if isinstance(old_messages, list):
            messages = [dict(row) for row in old_messages if isinstance(row, Mapping)]
        _write(cdir / f"round-{number:02d}-input.json", input_doc)
    else:
        _write(cdir / f"round-{number:02d}-input.json", _input_artifact(stage, number, messages))

    if old_valid:
        _preserve_old_attempt(cdir, story_id=story_id, number=number, stage=stage, old=old, source=output)
        raw = old.get("raw_output")
        response = old.get("raw_response") if isinstance(old.get("raw_response"), Mapping) else None
        content = str(old.get("raw_content") or "")
        result = {"raw": raw, "response": response, "content": content, "repair": old.get("json_repair", "none"), "error": None, "failure_class": None, "api_calls": 0, "attempts": [], "reused_continuation": False}
    elif old_exists and old_failure in TRANSPORT_FAILURE_CLASSES:
        _preserve_old_attempt(cdir, story_id=story_id, number=number, stage=stage, old=old, source=output)
        result = transport.call(story_id=story_id, round_number=number, completion_kind=stage, messages=messages, attempt_start=2, max_retries=0)
        for record in result["attempts"]:
            _save_attempt(cdir / "attempts" / f"round-{number:02d}-attempt-{int(record['attempt']):02d}.json", record, response=result.get("response"), content=result.get("content", "") if record is result["attempts"][-1] else "")
        raw, repair, parse_error = _parse_response(str(result.get("content") or "")) if result.get("success") else (None, "error", None)
        result = {**result, "raw": raw, "repair": repair, "error": parse_error or result.get("error"), "failure_class": "protocol_failure" if parse_error else result.get("failure_class"), "api_calls": len(result["attempts"]), "reused_continuation": False}
    else:
        result = transport.call(story_id=story_id, round_number=number, completion_kind=stage, messages=messages, attempt_start=1, max_retries=1)
        for record in result["attempts"]:
            attempt = int(record["attempt"])
            _save_attempt(cdir / "attempts" / f"round-{number:02d}-attempt-{attempt:02d}.json", record, response=result.get("response") if attempt == int(result["attempts"][-1]["attempt"]) else None, content=result.get("content", "") if attempt == int(result["attempts"][-1]["attempt"]) else "")
        raw, repair, parse_error = _parse_response(str(result.get("content") or "")) if result.get("success") else (None, "error", None)
        result = {**result, "raw": raw, "repair": repair, "error": parse_error or result.get("error"), "failure_class": "protocol_failure" if parse_error else result.get("failure_class"), "api_calls": len(result["attempts"]), "reused_continuation": False}

    projection = {
        "schema": "srm0-4c-model-output",
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "round": number,
        "execution_kind": "live_model",
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "raw_response": dict(result.get("response") or {}),
        "raw_content": result.get("content", ""),
        "raw_output": result.get("raw"),
        "json_repair": result.get("repair", "none"),
        "json_repair_count": int(result.get("repair") not in {"none", ""}),
        "api_usage": dict((result.get("response") or {}).get("usage", {})) if isinstance(result.get("response"), Mapping) else {},
        "api_attempted": bool(result.get("api_calls")),
        "selected_attempt": int(result["attempts"][-1]["attempt"]) if result.get("attempts") else 1,
        "transport_attempts": [dict(row) for row in result.get("attempts", [])],
        "protocol_error": result.get("error") if result.get("failure_class") == "protocol_failure" else None,
        "transport_error": result.get("error") if result.get("failure_class") in TRANSPORT_FAILURE_CLASSES else None,
        "failure_class": result.get("failure_class"),
        "canonical_write_back": False,
        "external_search_performed": False,
    }
    _write(projected, projection)
    return result


def _question_record(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **dict(row), "state": "unexplained", "working_answer": "", "supporting_refs": [], "remaining_gap": row["gap"],
        "reading_sufficient": False, "historical_verification_open": False, "next_action": "retrieve_local", "terminal_reason": None,
        "active": True, "last_round": 0, "evidence_rounds": 0, "claim_fingerprints": [], "conflict_fingerprints": [], "conflict_ids": [],
    }


def _process_delta(
    *, story_id: str, number: int, stage_result: Mapping[str, Any], material: Mapping[str, Any],
    questions: dict[str, dict[str, Any]], histories: dict[str, list[dict[str, Any]]], seen_refs: set[str],
    events: list[dict[str, Any]], round_metrics: list[dict[str, Any]],
    normalizations: list[dict[str, Any]], rejected_claims: list[dict[str, Any]], rejected_evidence: list[dict[str, Any]],
    semantic_failed: list[str], protocol_errors: list[str], transport_errors: list[dict[str, Any]],
    candidates: Sequence[Mapping[str, Any]] | None = None,
    per_question: Mapping[str, Mapping[str, Any]] | None = None,
    search_trace: list[dict[str, Any]] | None = None,
) -> bool:
    failure = stage_result.get("failure_class")
    error = stage_result.get("error")
    if error:
        if failure in TRANSPORT_FAILURE_CLASSES:
            transport_errors.append({"round": number, "failure_class": failure, "message": str(error)})
        else:
            protocol_errors.append(f"round {number}: {error}")
        for row in questions.values():
            if row.get("active"):
                row["active"] = False
                row["terminal_reason"] = "api_transport_failure" if failure in TRANSPORT_FAILURE_CLASSES else "protocol_failure"
        return False
    if number == 1:
        sources = {str(row["ref"]): str(row.get("text", "")) for row in list(material.get("liu_notes", [])) + list(material.get("jianshu_notes", []))}
    else:
        sources = {str(row["ref"]): str(row.get("text", "")) for row in (candidates or [])}
    delta, audit = normalize_delta_fail_soft(stage_result.get("raw"), sources, {qid for qid, row in questions.items() if row.get("active")})
    normalizations.extend(audit["normalizations"])
    rejected_claims.extend(audit["rejected_claims"])
    rejected_evidence.extend(audit["rejected_evidence"])
    projected = _read(_continuation_dir(_run_dir(story_id)) / f"round-{number:02d}-output.json")
    projected.update({"normalized_output": delta, "structural_normalizations": audit["normalizations"], "rejected_evidence": audit["rejected_evidence"], "rejected_claims": audit["rejected_claims"], "rejected_aspects": audit["rejected_aspects"], "rejected_updates": audit["rejected_updates"], "canonical_write_back": False, "external_search_performed": False})
    _write(_continuation_dir(_run_dir(story_id)) / f"round-{number:02d}-output.json", projected)
    updates = {str(row["question_id"]): row for row in delta.get("updates", []) if isinstance(row, Mapping)}
    active = [qid for qid, row in questions.items() if row.get("active")]
    q_metrics: list[dict[str, Any]] = []
    children_added: list[dict[str, Any]] = []
    round_used: set[str] = set()
    for qid in sorted(active):
        if qid not in updates:
            questions[qid]["active"] = False
            questions[qid]["terminal_reason"] = "semantic_update_failed"
            semantic_failed.append(qid)
            continue
        prior = dict(questions[qid])
        current, metric = b._apply_update(questions[qid], updates[qid], round_number=number, prior=prior, seen_refs=seen_refs, histories=histories)
        questions[qid] = current
        q_metrics.append(metric)
        round_used.update(metric.get("used_evidence_refs", []))
        children, rejected_children = make_children_b(prior, updates[qid], set(questions))
        for rejected in rejected_children:
            events.append({"event": "child_question_rejected", "story_id": story_id, "round": number, "question_id": qid, **rejected})
        if children:
            current["active"] = False
            current["terminal_reason"] = "refined_to_child"
            for child in children:
                child_record = _question_record(child)
                child_record["last_round"] = number
                questions[child["question_id"]] = child_record
                histories[child["question_id"]] = []
                children_added.append(child)
                events.append({"event": "child_question_created", "story_id": story_id, "round": number, "question_id": child["question_id"], "parent_question_id": child["parent_question_id"], "parent_aspect_id": child["parent_aspect_id"]})
        else:
            # Match SRM0.4B's stopping inputs exactly.
            b._mark_stop(questions[qid], histories, retrieval_attempts=0, adequate_attempts=0, evidence_round_count=number)
    for metric in q_metrics:
        metric["Q_t"] = int(any(child.get("parent_question_id") == metric["question_id"] for child in children_added))
    round_new = sorted({ref for metric in q_metrics for ref in metric.get("new_used_evidence_refs", [])})
    used = sorted(round_used)
    row: dict[str, Any] = {"round": number, "G_t": len(active), "D_t": int(any(metric.get("D_t") for metric in q_metrics)), "N_t": round(len(round_new) / len(used), 6) if used else 0.0, "Q_t": int(bool(children_added)), "used_evidence_refs": used, "new_used_evidence_refs": round_new, "question_metrics": q_metrics, "retrieval": number >= 2}
    if candidates is not None:
        row["retrieved_evidence_count"] = len(candidates)
        row["opened_evidence_count"] = len(candidates)
    round_metrics.append(row)
    if search_trace is not None and per_question is not None:
        for qid, data in sorted(per_question.items()):
            result = data.get("result", {})
            opened = data.get("opened", [])
            q_used = sorted(set(used).intersection(str(item.get("ref")) for item in opened if isinstance(item, Mapping)))
            q_new = sorted(set(round_new).intersection(q_used))
            search_trace.append({"round": number, "question_id": qid, "searched_corpora": list(SEARCHED_CORPORA), "retrieved_refs": [str(item.get("ref")) for item in result.get("hits", []) if isinstance(item, Mapping)], "opened_refs": [str(item.get("ref")) for item in opened if isinstance(item, Mapping)], "used_refs": q_used, "new_used_refs": q_new, "rejected_evidence": [dict(item) for item in rejected_evidence if str(item.get("path", "")).startswith("$.updates[")]})
    round_metrics[-1] = row
    events.append({"event": "retrieval_round_processed" if number >= 2 else "semantic_delta_processed", "story_id": story_id, "round": number, "used_refs": used, "D_t": row["D_t"], "N_t": row["N_t"]})
    return True


def _initial_projection(story_id: str, stage_result: Mapping[str, Any], material: Mapping[str, Any], cdir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    normalized, audit = normalize_initial_fail_soft(stage_result.get("raw"), material)
    accepted = normalized.get("gaps", [])
    projection = _read(cdir / "round-00-output.json")
    projection.update({"normalized_output": normalized, "accepted_gaps": accepted, "rejected_gaps": audit["rejected_gaps"], "structural_normalizations": audit["normalizations"], "canonical_write_back": False, "external_search_performed": False})
    _write(cdir / "round-00-output.json", projection)
    return accepted, audit["rejected_gaps"], audit["normalizations"]


def _old_transport_counts(run_dir: Path) -> dict[str, Any]:
    request = success = retry = tls = read_timeout = connect = server = 0
    for output in sorted(run_dir.glob("round-*-output.json")):
        row = _read(output)
        if not row.get("api_attempted"):
            continue
        request += 1
        failure = row.get("failure_class")
        if failure in TRANSPORT_FAILURE_CLASSES:
            if failure == "tls_failure": tls += 1
            elif failure == "read_timeout": read_timeout += 1
            elif failure == "connect_timeout": connect += 1
            elif failure == "server_error": server += 1
        else:
            success += 1
    return {"transport_request_count": request, "transport_retry_count": retry, "transport_success_count": success, "tls_failure_count": tls, "read_timeout_count": read_timeout, "connect_timeout_count": connect, "server_error_count": server, "successful_latencies_seconds": []}


def _transport_metrics(run_dir: Path, cdir: Path) -> dict[str, Any]:
    result = _old_transport_counts(run_dir)
    latencies: list[float] = []
    for path in sorted((cdir / "attempts").glob("round-*-attempt-*.json")):
        row = _read(path)
        if not row.get("actual_request"):
            continue
        result["transport_request_count"] += 1
        if int(row.get("attempt", 1)) > 1:
            result["transport_retry_count"] += 1
        failure = row.get("failure_class")
        if not failure:
            result["transport_success_count"] += 1
            if isinstance(row.get("elapsed_seconds"), (int, float)):
                latencies.append(float(row["elapsed_seconds"]))
        elif failure == "tls_failure": result["tls_failure_count"] += 1
        elif failure == "read_timeout": result["read_timeout_count"] += 1
        elif failure == "connect_timeout": result["connect_timeout_count"] += 1
        elif failure == "server_error": result["server_error_count"] += 1
    result["successful_latencies_seconds"] = [round(value, 6) for value in latencies]
    result["median_successful_latency_seconds"] = round(statistics.median(latencies), 6) if latencies else None
    result["max_successful_latency_seconds"] = round(max(latencies), 6) if latencies else None
    return result


def _question_metrics(questions: Mapping[str, Mapping[str, Any]], semantic_failed: Sequence[str], protocol_errors: Sequence[str], transport_errors: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    failed = set(semantic_failed)
    transport = bool(transport_errors)
    protocol = bool(protocol_errors)
    evaluable = [row for qid, row in questions.items() if qid not in failed and not transport and not protocol]
    return {
        "evaluable_question_count": len(evaluable),
        "valid_question_count": len(evaluable),
        "reading_sufficient_question_count": sum(row.get("state") == "substantially_explained" for row in evaluable),
        "conflicted_question_count": sum(row.get("state") == "conflicted" for row in evaluable),
        "unresolved_question_count": sum(row.get("state") in {"unexplained", "partially_explained"} for row in evaluable),
        "semantic_failed_question_count": len(failed),
    }


def _persist_aux(story_id: str, material: Mapping[str, Any], cdir: Path, *, status: str, questions: Mapping[str, Mapping[str, Any]], seen_refs: set[str], round_metrics: Sequence[Mapping[str, Any]], events: Sequence[Mapping[str, Any]], search_trace: Sequence[Mapping[str, Any]], usage_rows: Sequence[Mapping[str, Any]], protocol_errors: Sequence[str], transport_errors: Sequence[Mapping[str, Any]], semantic_failed: Sequence[str], normalizations: Sequence[Mapping[str, Any]], rejected_claims: Sequence[Mapping[str, Any]], rejected_evidence: Sequence[Mapping[str, Any]], run_dir: Path, api_calls: int) -> None:
    state = {
        "schema": "srm0-4c-research-state", "schema_version": SCHEMA_VERSION, "story_id": story_id, "execution_kind": "live_model", "run_id": run_dir.name,
        "stage": "continuation_complete", "story_status": status, "questions": [b._compact_question(questions[key]) for key in sorted(questions)],
        "active_questions": sorted(qid for qid, row in questions.items() if row.get("active")), "terminal_questions": sorted(qid for qid, row in questions.items() if row.get("terminal_reason")),
        "seen_evidence_refs": sorted(seen_refs), "canonical_write_back": False, "external_search_performed": False,
        "protocol_errors": sorted(set(protocol_errors)), "transport_errors": [dict(row) for row in transport_errors], "semantic_failed_questions": sorted(set(semantic_failed)),
    }
    _write(cdir / "research-state.json", state)
    cdir.joinpath("events.jsonl").write_text("".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in events), encoding="utf-8")
    cdir.joinpath("search-trace.jsonl").write_text("".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in search_trace), encoding="utf-8")
    total_tokens = sum(int((row.get("api_usage") or {}).get("total_tokens") or 0) for row in usage_rows)
    completion_count = sum(int(bool(row.get("response_present"))) for row in usage_rows)
    usage = {"schema": "srm0-4c-usage", "schema_version": SCHEMA_VERSION, "story_id": story_id, "run_id": run_dir.name, "rounds": [dict(row) for row in usage_rows], "total_tokens": total_tokens, "completion_count": completion_count, "network_attempt_count": api_calls, "json_repair_count": len(normalizations), "canonical_write_back": False, "external_search_performed": False}
    _write(cdir / "usage.json", usage)
    _write(cdir / "convergence.json", {"schema": "srm0-4c-convergence", "schema_version": SCHEMA_VERSION, "story_id": story_id, "story_status": status, "round_metrics": [dict(row) for row in round_metrics], "question_metrics": _question_metrics(questions, semantic_failed, protocol_errors, transport_errors), "question_terminals": {qid: row.get("terminal_reason") for qid, row in sorted(questions.items())}, "canonical_write_back": False, "external_search_performed": False})
    _write(cdir / "manifest.json", {"schema": "srm0-4c-manifest", "schema_version": SCHEMA_VERSION, "story_id": story_id, "run_id": run_dir.name, "source_run": run_dir.relative_to(ROOT).as_posix(), "source_artifact_hashes": {path.name: sha256_file(ROOT, run_dir / path.name) for path in sorted(run_dir.glob("round-*-input.json")) + sorted(run_dir.glob("round-*-output.json"))}, "transport_metrics": _transport_metrics(run_dir, cdir), "normalization_count": len(normalizations), "rejected_claim_count": len(rejected_claims), "rejected_evidence_count": len(rejected_evidence), "canonical_write_back": False, "external_search_performed": False})


def _run_story(story_id: str, transport: DeepSeekTransport) -> dict[str, Any]:
    material = story_material(ROOT, story_id)
    run_dir = _run_dir(story_id)
    cdir = _continuation_dir(run_dir)
    cdir.mkdir(parents=True, exist_ok=True)
    registry = build_registry(ROOT)
    questions: dict[str, dict[str, Any]] = {}
    histories: dict[str, list[dict[str, Any]]] = {}
    seen_refs: set[str] = set()
    events: list[dict[str, Any]] = []
    search_trace: list[dict[str, Any]] = []
    round_metrics: list[dict[str, Any]] = []
    usage_rows: list[dict[str, Any]] = []
    normalizations: list[dict[str, Any]] = []
    rejected_claims: list[dict[str, Any]] = []
    rejected_evidence: list[dict[str, Any]] = []
    protocol_errors: list[str] = []
    transport_errors: list[dict[str, Any]] = []
    semantic_failed: list[str] = []
    api_calls = 0

    initial_messages = b.build_initial_messages(material)
    initial = _stage_call(story_id=story_id, number=0, stage="main_text_gap_discovery", messages=initial_messages, run_dir=run_dir, cdir=cdir, transport=transport)
    api_calls += int(initial.get("api_calls", 0))
    usage_rows.append({"round": 0, "stage": "main_text_gap_discovery", "api_usage": dict((initial.get("response") or {}).get("usage", {})) if isinstance(initial.get("response"), Mapping) else {}, "api_calls": initial.get("api_calls", 0), "response_present": bool(initial.get("response")), "selected_attempt": initial.get("attempts", [{}])[-1].get("attempt") if initial.get("attempts") else 1})
    if initial.get("error"):
        if initial.get("failure_class") in TRANSPORT_FAILURE_CLASSES:
            transport_errors.append({"round": 0, "failure_class": initial.get("failure_class"), "message": str(initial.get("error"))})
        else:
            protocol_errors.append(f"round 0: {initial.get('error')}")
    accepted, rejected_gaps, initial_norm = _initial_projection(story_id, initial, material, cdir)
    normalizations.extend(initial_norm)
    for row in rejected_gaps:
        events.append({"event": "gap_rejected", "story_id": story_id, "index": row.get("index"), "question_id": row.get("question_id"), "reason": row.get("reason")})
    for row in accepted:
        questions[str(row["question_id"])] = _question_record(row)
        histories[str(row["question_id"])] = []
        events.append({"event": "gap_accepted", "story_id": story_id, "question_id": row["question_id"], "story_span": row["story_span"]})

    current_round = 1
    while accepted and not protocol_errors and not transport_errors and any(row.get("active") for row in questions.values()) and current_round <= MAX_EVIDENCE_ROUNDS:
        active = [questions[qid] for qid in sorted(questions) if questions[qid].get("active")]
        if current_round == 1:
            messages = build_commentary_messages(material, active)
            stage = "attached_commentary_delta"
            candidates = None
            per_question = None
        else:
            per_question = {}
            retrieved: dict[str, dict[str, Any]] = {}
            for question in active:
                qid = str(question["question_id"])
                result = search_registry(registry, query=f"{question.get('gap', '')} {question.get('story_span', '')}", exclude_story=story_id)
                opened = open_candidates(result)
                for row in opened:
                    if row.get("ref"):
                        retrieved.setdefault(str(row["ref"]), dict(row))
                per_question[qid] = {"result": result, "opened": opened}
            candidates = sorted(retrieved.values(), key=lambda row: (-int(row.get("score", 0)), str(row.get("work", "")), str(row.get("ref", ""))))[:5]
            messages = build_retrieval_messages(material, active, candidates, questions)
            stage = "local_retrieval_delta"
        result = _stage_call(story_id=story_id, number=current_round, stage=stage, messages=messages, run_dir=run_dir, cdir=cdir, transport=transport)
        api_calls += int(result.get("api_calls", 0))
        usage_rows.append({"round": current_round, "stage": stage, "api_usage": dict((result.get("response") or {}).get("usage", {})) if isinstance(result.get("response"), Mapping) else {}, "api_calls": result.get("api_calls", 0), "response_present": bool(result.get("response")), "selected_attempt": result.get("attempts", [{}])[-1].get("attempt") if result.get("attempts") else 1})
        ok = _process_delta(story_id=story_id, number=current_round, stage_result=result, material=material, questions=questions, histories=histories, seen_refs=seen_refs, events=events, round_metrics=round_metrics, normalizations=normalizations, rejected_claims=rejected_claims, rejected_evidence=rejected_evidence, semantic_failed=semantic_failed, protocol_errors=protocol_errors, transport_errors=transport_errors, candidates=candidates, per_question=per_question, search_trace=search_trace)
        if not ok:
            break
        current_round += 1

    if transport_errors:
        status = "api_transport_failed"
        for row in questions.values():
            if row.get("active"):
                row["active"] = False
                row["terminal_reason"] = "api_transport_failure"
    elif protocol_errors:
        status = "protocol_failed"
        for row in questions.values():
            if row.get("active"):
                row["active"] = False
                row["terminal_reason"] = "protocol_failure"
    elif semantic_failed:
        status = "semantic_partial_failure" if any(not row.get("active") for row in questions.values()) else "semantic_failed"
    elif not accepted:
        status = "no_valid_reading_gap"
    elif any(row.get("active") for row in questions.values()):
        for row in questions.values():
            if row.get("active"):
                row["active"] = False
                row["terminal_reason"] = "hard_cap"
        status = "hard_cap"
    else:
        status = "converged"
    metrics = _question_metrics(questions, semantic_failed, protocol_errors, transport_errors)
    _persist_aux(story_id, material, cdir, status=status, questions=questions, seen_refs=seen_refs, round_metrics=round_metrics, events=events, search_trace=search_trace, usage_rows=usage_rows, protocol_errors=protocol_errors, transport_errors=transport_errors, semantic_failed=semantic_failed, normalizations=normalizations, rejected_claims=rejected_claims, rejected_evidence=rejected_evidence, run_dir=run_dir, api_calls=api_calls)
    old_summary_row = {}
    live_summary = _read(ROOT / LIVE_SUMMARY_PATH)
    if isinstance(live_summary.get("stories"), list):
        old_summary_row = next((dict(row) for row in live_summary["stories"] if isinstance(row, Mapping) and row.get("story_id") == story_id), {})
    summary = b._fixture_or_live_summary(story_id, material, execution_kind="live_model", run_id=run_dir.name, output_dir=run_dir, status=status, questions=questions, accepted=accepted, rejected_gaps=rejected_gaps, round_metrics=round_metrics, search_trace=search_trace, normalizations=normalizations, rejected_claims=rejected_claims, rejected_evidence=rejected_evidence, protocol_errors=protocol_errors, transport_errors=transport_errors, semantic_failed_questions=semantic_failed, usage_rows=usage_rows, initial_rounds=[0] + [int(row["round"]) for row in round_metrics])
    summary["continuation_dir"] = cdir.relative_to(ROOT).as_posix()
    summary["question_metrics"] = metrics
    summary["transport_metrics"] = _transport_metrics(run_dir, cdir)
    summary["used_evidence"] = sorted({str(ref) for metric in round_metrics for ref in metric.get("used_evidence_refs", [])})
    summary["new_used_evidence"] = sorted({str(ref) for metric in round_metrics for ref in metric.get("new_used_evidence_refs", [])})
    summary["token_usage"]["completion_count"] = sum(int(bool(row.get("response_present"))) for row in usage_rows)
    summary["token_usage"]["network_attempt_count"] = api_calls
    summary["preserved_prior_summary"] = bool(old_summary_row)
    return summary


def _augment_preserved_row(row: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(row)
    story_id = str(value.get("story_id"))
    run_dir = _run_dir(story_id)
    state = _read(run_dir / "research-state.json")
    questions = {str(item.get("question_id")): item for item in state.get("questions", []) if isinstance(item, Mapping) and item.get("question_id")}
    semantic_failed = value.get("semantic_failed_questions", []) if isinstance(value.get("semantic_failed_questions"), list) else []
    value["question_metrics"] = _question_metrics(questions, semantic_failed, value.get("protocol_errors", []) or [], value.get("transport_errors", []) or [])
    value["transport_metrics"] = _transport_metrics(run_dir, run_dir / "continuation")
    return value


def _batch_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = [dict(row) for row in rows]
    terminal = Counter(str(reason) for row in values for reason in (row.get("terminal_reason_per_question") or {}).values() if reason)
    qkeys = ("evaluable_question_count", "valid_question_count", "reading_sufficient_question_count", "conflicted_question_count", "unresolved_question_count", "semantic_failed_question_count")
    qmetrics = {key: sum(int((row.get("question_metrics") or {}).get(key, 0)) for row in values) for key in qkeys}
    tkeys = ("transport_request_count", "transport_retry_count", "transport_success_count", "tls_failure_count", "read_timeout_count", "connect_timeout_count", "server_error_count")
    transport_metrics = {key: sum(int((row.get("transport_metrics") or {}).get(key, 0)) for row in values) for key in tkeys}
    latencies = [float(value) for row in values for value in (row.get("transport_metrics") or {}).get("successful_latencies_seconds", []) if isinstance(value, (int, float))]
    transport_metrics["median_successful_latency_seconds"] = round(statistics.median(latencies), 6) if latencies else None
    transport_metrics["max_successful_latency_seconds"] = round(max(latencies), 6) if latencies else None
    protocol = sum(bool(row.get("protocol_errors")) for row in values)
    semantic = sum(bool(row.get("semantic_failed_questions")) for row in values)
    transport = sum(bool(row.get("transport_errors")) for row in values)
    evaluable_stories = [row for row in values if not row.get("transport_errors")]
    aggregate = {"live_story_count": len(values), "protocol_failure_count": protocol, "api_transport_failure_count": transport, "semantic_failure_count": semantic, "evaluable_story_count": len(evaluable_stories), "valid_live_story_count": sum(not row.get("protocol_errors") and not row.get("transport_errors") and not row.get("semantic_failed_questions") for row in values), "reading_convergence_rate": round(sum(row.get("convergence_status") == "converged" for row in evaluable_stories) / max(1, len(evaluable_stories)), 3), "terminal_reason_counts": dict(sorted(terminal.items())), "average_evidence_rounds": round(sum(len(row.get("evidence_rounds", [])) for row in values) / max(1, len(values)), 3), "average_used_refs": round(sum(len(row.get("used_evidence", [])) for row in values) / max(1, len(values)), 3), "rejected_claim_count": sum(len(row.get("rejected_claims", [])) for row in values), "rejected_evidence_count": sum(len(row.get("rejected_evidence", [])) for row in values), **qmetrics, **transport_metrics}
    return {"schema": "srm0-4c-live-summary", "schema_version": SCHEMA_VERSION, "execution_kind": "live_model", "stories": values, "aggregate": aggregate, "canonical_write_back": False, "external_search_performed": False}


def _preflight(transport: DeepSeekTransport) -> dict[str, Any]:
    started = time.monotonic()
    result = transport.call(story_id="__preflight__", round_number=-1, completion_kind="preflight", messages=[{"role": "user", "content": 'Return JSON: {"status":"connected"}'}], max_retries=0)
    row = {"endpoint": API_URL, "model": MODEL, "start_time": datetime.now(timezone.utc).isoformat(), "success": bool(result.get("success")), "classification": "reachable" if result.get("success") else result.get("failure_class"), "http_status": result.get("attempts", [{}])[-1].get("http_status") if result.get("attempts") else None, "elapsed_seconds": round(time.monotonic() - started, 6), "attempts": result.get("attempts", [])}
    _write(PREFLIGHT_PATH, row)
    return row


class _NoCallTransport:
    """Fail loudly if an offline replay ever reaches a missing model stage."""

    def call(self, **_: Any) -> dict[str, Any]:
        raise AssertionError("SRM0.4C offline replay attempted a DeepSeek call")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", choices=ELIGIBLE_STORIES, action="append")
    parser.add_argument("--continue", dest="continue_run", action="store_true", help="resume the four transport-failed Stories")
    parser.add_argument("--replay-existing", action="store_true", help="rebuild projections without network calls")
    return parser.parse_args()


def run(args: argparse.Namespace, *, transport: DeepSeekTransport | None = None) -> int:
    stories = list(args.story or ELIGIBLE_STORIES)
    if not args.continue_run and not args.story:
        raise SystemExit("use --continue to resume only transport-failed Stories")
    if any(story not in ELIGIBLE_STORIES for story in stories):
        raise SystemExit("SRM0.4C accepts only the four transport-failed Stories")
    client = transport or (_NoCallTransport() if args.replay_existing else DeepSeekTransport())
    if args.replay_existing:
        preflight = {"classification": "replay"}
    else:
        preflight = _preflight(client)
        if preflight.get("classification") != "reachable":
            print("live_network_unavailable")
            print(f"preflight_classification: {preflight.get('classification')}")
            print("rerun the same continuation command with approved network access")
            return 2
    rows = [_run_story(story, client) for story in stories]
    old = _read(ROOT / LIVE_SUMMARY_PATH)
    preserved = [_augment_preserved_row(row) for row in old.get("stories", []) if isinstance(row, Mapping) and row.get("story_id") in {"25-paidiao-007", "02-yanyu-053"}]
    all_rows = preserved + rows
    all_rows.sort(key=lambda row: FIXED_STORIES.index(str(row.get("story_id"))) if row.get("story_id") in FIXED_STORIES else 999)
    _write(ROOT / LIVE_SUMMARY_PATH, _batch_summary(all_rows))
    print("SRM0.4C completed")
    for row in rows:
        tm = row.get("transport_metrics", {})
        print(f"{row['story_id']}: status={row['story_status']} rounds={len(row.get('evidence_rounds', []))} requests={tm.get('transport_request_count')} retries={tm.get('transport_retry_count')} question_metrics={row.get('question_metrics')}")
    print("summary:", LIVE_SUMMARY_PATH.as_posix())
    return 1 if any(row.get("protocol_errors") or row.get("transport_errors") for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
