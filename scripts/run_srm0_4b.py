#!/usr/bin/env python3
"""Run the SRM0.4B robust live/fixture convergence protocol."""

from __future__ import annotations

import argparse
import json
import os
import signal
import shutil
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
from smoke_deepseek import call_deepseek  # noqa: E402
from srm0_4b_common import (  # noqa: E402
    FIXED_STORIES,
    FIXTURE_SUMMARY_PATH,
    LIVE_SUMMARY_PATH,
    MAX_EVIDENCE_ROUNDS,
    MODEL,
    OUTPUT_BASE,
    PROMPT_VERSION,
    PROVIDER,
    REVIEW_PATH,
    SCHEMA_VERSION,
    SEARCHED_CORPORA,
    STATUS_PATH,
    TRANSPORT_FAILURE_CLASSES,
    build_commentary_messages,
    build_initial_messages,
    build_registry,
    build_retrieval_messages,
    classify_deepseek_exception,
    derive_state_b,
    evidence_novelty_b,
    fixture_version,
    make_children_b,
    material_delta_b,
    normalize_delta_fail_soft,
    normalize_initial_fail_soft,
    open_candidates,
    output_directory,
    parse_json_any,
    review_template_b,
    run_id_for,
    search_registry,
    stop_reason_b,
    story_material,
    write_status,
)

PREFLIGHT_PATH = Path("/tmp/srm0-4b-live-preflight.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--batch", action="store_true", help="run all six frozen Stories (default)")
    group.add_argument("--story", help="run one frozen Story")
    parser.add_argument("--fixture", action="store_true", help="run deterministic plumbing fixtures, never the API")
    parser.add_argument("--replay-existing", action="store_true", help="replay saved live raw outputs without an API call")
    parser.add_argument("--timeout", type=int, default=120)
    return parser.parse_args()


def response_content(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("DeepSeek response has no choices")
    message = choices[0].get("message", {}) if isinstance(choices[0], Mapping) else {}
    content = message.get("content") if isinstance(message, Mapping) else None
    if not isinstance(content, str) or not content.strip():
        raise ValueError("DeepSeek response has no JSON content")
    return content


def usage_fields(response: Mapping[str, Any] | None) -> dict[str, Any]:
    usage = response.get("usage", {}) if isinstance(response, Mapping) else {}
    if not isinstance(usage, Mapping):
        usage = {}
    return {
        "prompt_tokens": usage.get("prompt_tokens"),
        "prompt_cache_hit_tokens": usage.get("prompt_cache_hit_tokens"),
        "prompt_cache_miss_tokens": usage.get("prompt_cache_miss_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "raw_usage": dict(usage),
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _exception_http_status(exc: BaseException) -> int | None:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        code = getattr(current, "code", None)
        if isinstance(code, int):
            return code
        current = current.__cause__ or current.__context__
    return None


def _preflight_report(timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    report: dict[str, Any] = {
        "endpoint": "https://api.deepseek.com/chat/completions",
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "start_time": datetime.now(timezone.utc).isoformat(),
        "timeout_seconds": timeout,
    }
    try:
        response = call_deepseek(
            [{"role": "user", "content": 'Return JSON: {"status":"connected"}'}],
            model=MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            tools=[],
            timeout=timeout,
        )
        choices = response.get("choices") if isinstance(response, Mapping) else None
        if not isinstance(choices, list) or not choices:
            raise ValueError("DeepSeek preflight response has no choices")
        usage = response.get("usage", {}) if isinstance(response, Mapping) else {}
        report.update({
            "classification": "reachable",
            "success": True,
            "http_status": 200,
            "response_model": response.get("model") if isinstance(response, Mapping) else None,
            "api_usage": dict(usage) if isinstance(usage, Mapping) else {},
        })
    except Exception as exc:  # noqa: BLE001 - preflight must classify every failure
        classification = classify_deepseek_exception(exc) or "other_transport_failure"
        message = str(exc)
        secret = os.environ.get("DEEPSEEK_API_KEY")
        if secret:
            message = message.replace(secret, "[REDACTED]")
        report.update({
            "classification": classification,
            "success": False,
            "http_status": _exception_http_status(exc),
            "exception_class": type(exc).__name__,
            "exception_message": message,
        })
    report["end_time"] = datetime.now(timezone.utc).isoformat()
    report["elapsed_seconds"] = round(time.monotonic() - started, 6)
    PREFLIGHT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def run_live_preflight(timeout: int) -> dict[str, Any]:
    """Abort live execution before Story artifacts if the API is unusable."""
    report = _preflight_report(timeout)
    if report.get("classification") != "reachable":
        print("live_network_unavailable")
        print(f"preflight_classification: {report.get('classification')}")
        print("rerun the same live command with approved network access")
    else:
        print("live_network_preflight: reachable")
    return report


def _reset_target(target: Path) -> None:
    """Remove only this protocol's generated run directory."""
    absolute = ROOT / target
    expected = "/convergence/live/" in absolute.as_posix() or "/convergence/fixture/" in absolute.as_posix()
    if not expected:
        raise ValueError(f"refusing to clean non-SRM0.4B path: {target}")
    if absolute.is_dir():
        shutil.rmtree(absolute)


def _event_write(path: Path, events: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in events),
        encoding="utf-8",
    )


def _fixture_initial(material: Mapping[str, Any]) -> dict[str, Any]:
    text = str(material.get("main_text", ""))
    return {"gaps": [{
        "question_id": "Q1",
        "story_span": text[: min(18, len(text))],
        "gap": "这段行动或处境为何影响正文理解？",
    }]} if text else {"gaps": []}


def _fixture_delta(material: Mapping[str, Any], questions: Sequence[Mapping[str, Any]], *, retrieval: bool, candidates: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    notes = list(material.get("jianshu_notes", [])) + list(material.get("liu_notes", []))
    evidence = next((row for row in candidates if isinstance(row, Mapping) and row.get("ref")), None) if retrieval else next((row for row in notes if row.get("text")), None)
    updates: list[dict[str, Any]] = []
    for question in questions:
        row: dict[str, Any] = {
            "question_id": question["question_id"],
            "answered_aspects": [],
            "unanswered_aspects": [],
            "conflicts": [],
            "reading_sufficient": False,
            "historical_verification_open": False,
        }
        if evidence:
            ref = str(evidence.get("ref"))
            quote = str(evidence.get("snippet") or evidence.get("text") or "")[:80]
            row["answered_aspects"] = [{
                "aspect_id": f"{question['question_id']}-A1",
                "claim": "本轮本地证据为该阅读缺口提供了可核查线索。",
                "evidence": [{"ref": ref, "quote": quote}],
            }]
            if retrieval:
                row["reading_sufficient"] = True
                row["historical_verification_open"] = True
            else:
                row["unanswered_aspects"] = [{
                    "aspect_id": f"{question['question_id']}-U1",
                    "gap": "仍需一轮本地史料检索确认其对正文理解的具体作用。",
                    "reading_impact": "high",
                }]
        else:
            row["unanswered_aspects"] = [{
                "aspect_id": f"{question['question_id']}-U1",
                "gap": "仍缺少能直接改变该段阅读的具体历史材料。",
                "reading_impact": "high",
            }]
        updates.append(row)
    return {"updates": updates}


def _stage_call(
    *,
    stage: str,
    round_number: int,
    messages: Sequence[Mapping[str, Any]],
    output_dir: Path,
    execution_kind: str,
    fixture_value: Any | None,
    replay: bool,
    timeout: int,
) -> dict[str, Any]:
    input_path = output_dir / f"round-{round_number:02d}-input.json"
    output_path = output_dir / f"round-{round_number:02d}-output.json"
    input_artifact = {
        "schema": "srm0-4b-model-input",
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "round": round_number,
        "execution_kind": execution_kind,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "parameters": {"temperature": 0, "response_format": {"type": "json_object"}, "tools": []},
        "messages": [dict(message) for message in messages],
        "canonical_write_back": False,
        "external_search_performed": False,
    }
    write_json(ROOT, input_path, input_artifact)
    raw: Any = None
    response: dict[str, Any] | None = None
    content = ""
    repair = "none"
    error: str | None = None
    failure_class: str | None = None
    api_calls = 0
    try:
        if fixture_value is not None:
            raw = fixture_value
            content = stable_json(raw)
            repair = "fixture"
        elif replay:
            # Replay reports the original live attempt in usage, but makes no
            # new network call.  This keeps a transport failure visible in
            # the batch accounting without counting the replay itself.
            api_calls = int(execution_kind == "live_model")
            saved = _read_json(ROOT / output_path)
            content = str(saved.get("raw_content") or "")
            if not content:
                raise ValueError(f"saved live output has no raw_content: {output_path}")
            raw, repair = parse_json_any(content)
            saved_response = saved.get("raw_response")
            response = dict(saved_response) if isinstance(saved_response, Mapping) else None
        else:
            api_calls = 1
            response = _call_with_deadline(messages, timeout)
            content = response_content(response)
            raw, repair = parse_json_any(content)
    except Exception as exc:  # noqa: BLE001 - persist protocol failure visibly
        error = str(exc)
        failure_class = classify_deepseek_exception(exc) or "protocol_failure"
        repair = "error"
        if response is not None:
            try:
                content = response_content(response)
            except Exception:  # noqa: BLE001
                content = ""
        raw = None
    artifact = {
        "schema": "srm0-4b-model-output",
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "round": round_number,
        "execution_kind": execution_kind,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "raw_response": dict(response or {}),
        "raw_content": content,
        "raw_output": raw,
        "json_repair": repair,
        "json_repair_count": int(repair not in {"none", "fixture"}),
        "api_usage": usage_fields(response),
        "api_attempted": bool(api_calls),
        "protocol_error": error if failure_class == "protocol_failure" else None,
        "transport_error": error if failure_class in TRANSPORT_FAILURE_CLASSES else None,
        "failure_class": failure_class,
        "canonical_write_back": False,
        "external_search_performed": False,
    }
    write_json(ROOT, output_path, artifact)
    return {"raw": raw, "response": response, "content": content, "repair": repair, "error": error, "failure_class": failure_class, "api_calls": api_calls, "output_path": output_path}


def _update_stage_artifact(path: Path, updates: Mapping[str, Any]) -> None:
    artifact = _read_json(ROOT / path)
    artifact.update(dict(updates))
    write_json(ROOT, path, artifact)


def _record_stage_failure(stage: str, result: Mapping[str, Any], protocol_errors: list[str], transport_errors: list[dict[str, Any]]) -> None:
    error = result.get("error")
    if not error:
        return
    failure_class = str(result.get("failure_class") or "protocol_failure")
    if failure_class in TRANSPORT_FAILURE_CLASSES:
        transport_errors.append({"stage": stage, "failure_class": failure_class, "message": str(error)})
    else:
        protocol_errors.append(f"{stage}: {error}")


def _call_with_deadline(messages: Sequence[Mapping[str, Any]], timeout: int) -> dict[str, Any]:
    """Bound both connection and response-body waits of the stdlib client."""
    if timeout <= 0 or not hasattr(signal, "setitimer"):
        return call_deepseek(
            messages,
            model=MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            tools=[],
            timeout=timeout,
        )

    def deadline(_signum: int, _frame: Any) -> None:
        raise TimeoutError(f"DeepSeek API request exceeded {timeout}s deadline")

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, float(timeout))
    try:
        return call_deepseek(
            messages,
            model=MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            tools=[],
            timeout=timeout,
        )
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def _refs_from_update(update: Mapping[str, Any]) -> list[str]:
    return sorted({str(item.get("ref")) for aspect in update.get("answered_aspects", []) if isinstance(aspect, Mapping) for item in aspect.get("evidence", []) if isinstance(item, Mapping) and item.get("ref")} | {str(item.get("ref")) for conflict in update.get("conflicts", []) if isinstance(conflict, Mapping) for item in conflict.get("evidence", []) if isinstance(item, Mapping) and item.get("ref")})


def _compact_question(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "question_id", "parent_question_id", "parent_aspect_id", "story_span", "gap", "state",
        "working_answer", "supporting_refs", "remaining_gap", "reading_sufficient",
        "historical_verification_open", "next_action", "terminal_reason", "active", "last_round",
        "evidence_rounds", "claim_fingerprints", "conflict_fingerprints", "conflict_ids",
    )
    return {key: row.get(key) for key in keys}


def _apply_update(
    question: Mapping[str, Any],
    update: Mapping[str, Any],
    *,
    round_number: int,
    prior: Mapping[str, Any] | None,
    seen_refs: set[str],
    histories: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    used = _refs_from_update(update)
    current = derive_state_b(question, update)
    d_value = material_delta_b(prior, current, used_refs=used)
    novelty, new_refs = evidence_novelty_b(used, seen_refs)
    seen_refs.update(used)
    current["last_round"] = round_number
    current["evidence_rounds"] = int(question.get("evidence_rounds", 0)) + 1
    metric = {
        "question_id": str(question["question_id"]),
        "round": round_number,
        "D_t": int(d_value),
        "N_t": round(novelty, 6),
        "Q_t": 0,
        "used_evidence_refs": used,
        "new_used_evidence_refs": new_refs,
        "conflict_fingerprints": current.get("conflict_fingerprints", []),
        "reading_sufficient": current.get("reading_sufficient"),
        "active": current.get("active"),
        "d_basis": "validated_evidence_change" if d_value else "none",
    }
    histories.setdefault(str(question["question_id"]), []).append(metric)
    return current, metric


def _mark_stop(record: dict[str, Any], histories: Mapping[str, Sequence[Mapping[str, Any]]], *, retrieval_attempts: int, adequate_attempts: int, evidence_round_count: int) -> str | None:
    reason = stop_reason_b(histories.get(str(record["question_id"]), []), retrieval_attempts=retrieval_attempts, adequate_attempts=adequate_attempts, evidence_round_count=evidence_round_count)
    if reason:
        record["active"] = False
        record["terminal_reason"] = reason
    return reason


def _fixture_or_live_summary(story_id: str, material: Mapping[str, Any], *, execution_kind: str, run_id: str | None, output_dir: Path, status: str, questions: Mapping[str, Mapping[str, Any]], accepted: Sequence[Mapping[str, Any]], rejected_gaps: Sequence[Mapping[str, Any]], round_metrics: Sequence[Mapping[str, Any]], search_trace: Sequence[Mapping[str, Any]], normalizations: Sequence[Mapping[str, Any]], rejected_claims: Sequence[Mapping[str, Any]], rejected_evidence: Sequence[Mapping[str, Any]], protocol_errors: Sequence[str], transport_errors: Sequence[Mapping[str, Any]], semantic_failed_questions: Sequence[str], usage_rows: Sequence[Mapping[str, Any]], initial_rounds: Sequence[int]) -> dict[str, Any]:
    terminal_reasons = {qid: row.get("terminal_reason") for qid, row in sorted(questions.items()) if row.get("terminal_reason")}
    retrieved = sorted({str(ref) for trace in search_trace for ref in trace.get("retrieved_refs", [])})
    opened = sorted({str(ref) for trace in search_trace for ref in trace.get("opened_refs", [])})
    used = sorted({str(ref) for trace in search_trace for ref in trace.get("used_refs", [])})
    new_used = sorted({str(ref) for metric in round_metrics for ref in metric.get("new_used_evidence_refs", [])})
    total_tokens = sum((row.get("api_usage") or {}).get("total_tokens") or 0 for row in usage_rows)
    return {
        "story_id": story_id,
        "execution_kind": execution_kind,
        "run_id": run_id,
        "main_text_chars": material["main_text_chars"],
        "liu_block_count": material["liu_block_count"],
        "jianshu_chars": material["jianshu_chars"],
        "initial_gaps": [dict(row) for row in accepted],
        "accepted_gaps": [dict(row) for row in accepted],
        "rejected_gaps": [dict(row) for row in rejected_gaps],
        "evidence_rounds": [dict(row) for row in round_metrics],
        "rounds_executed": list(initial_rounds),
        "searched_corpora": list(SEARCHED_CORPORA) if search_trace else [],
        "retrieved_refs": retrieved,
        "opened_refs": opened,
        "used_evidence": used,
        "new_used_evidence": new_used,
        "terminal_reason_per_question": terminal_reasons,
        "convergence_status": "converged" if status == "converged" else status,
        "story_status": status,
        "structural_normalizations": [dict(row) for row in normalizations],
        "rejected_claims": [dict(row) for row in rejected_claims],
        "rejected_evidence": [dict(row) for row in rejected_evidence],
        "protocol_errors": list(protocol_errors),
        "transport_errors": [dict(row) for row in transport_errors],
        "semantic_failed_questions": sorted(set(semantic_failed_questions)),
        "protocol_failure_count": int(bool(protocol_errors)),
        "api_transport_failure_count": len(transport_errors),
        "semantic_failure_count": len(set(semantic_failed_questions)),
        "token_usage": {"total_tokens": total_tokens, "completion_count": sum(int(row.get("api_calls", 0)) for row in usage_rows)},
        "validation_errors": [],
    }


def _write_state_and_aux(
    *,
    story_id: str,
    material: Mapping[str, Any],
    output_dir: Path,
    execution_kind: str,
    run_id: str | None,
    status: str,
    questions: Mapping[str, Mapping[str, Any]],
    seen_refs: set[str],
    round_metrics: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    search_trace: Sequence[Mapping[str, Any]],
    usage_rows: Sequence[Mapping[str, Any]],
    protocol_errors: Sequence[str],
    transport_errors: Sequence[Mapping[str, Any]],
    semantic_failed_questions: Sequence[str],
    total_normalizations: Sequence[Mapping[str, Any]],
    total_rejected_claims: Sequence[Mapping[str, Any]],
    total_rejected_evidence: Sequence[Mapping[str, Any]],
    api_calls: int,
    json_repairs: int,
) -> None:
    state = {
        "schema": "srm0-4b-research-state",
        "schema_version": SCHEMA_VERSION,
        "story_id": story_id,
        "execution_kind": execution_kind,
        "run_id": run_id,
        "stage": "convergence_complete" if status in {"converged", "no_valid_reading_gap"} else status,
        "story_status": status,
        "questions": [_compact_question(questions[key]) for key in sorted(questions)],
        "active_questions": sorted(key for key, row in questions.items() if row.get("active")),
        "terminal_questions": sorted(key for key, row in questions.items() if row.get("terminal_reason")),
        "seen_evidence_refs": sorted(seen_refs),
        "canonical_write_back": False,
        "external_search_performed": False,
        "protocol_errors": sorted(set(protocol_errors)),
        "transport_errors": [dict(row) for row in transport_errors],
        "semantic_failed_questions": sorted(set(semantic_failed_questions)),
    }
    write_json(ROOT, output_dir / "research-state.json", state)
    _event_write(ROOT / output_dir / "events.jsonl", events)
    _event_write(ROOT / output_dir / "search-trace.jsonl", search_trace)
    total_tokens = sum((row.get("api_usage") or {}).get("total_tokens") or 0 for row in usage_rows)
    usage = {
        "schema": "srm0-4b-usage",
        "schema_version": SCHEMA_VERSION,
        "story_id": story_id,
        "execution_kind": execution_kind,
        "run_id": run_id,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "rounds": [dict(row) for row in usage_rows],
        "total_tokens": total_tokens,
        "completion_count": api_calls,
        "json_repair_count": json_repairs,
        "structural_normalization_count": len(total_normalizations),
        "rejected_claim_count": len(total_rejected_claims),
        "rejected_evidence_count": len(total_rejected_evidence),
        "character_metrics": {
            "main_text_chars": material["main_text_chars"],
            "liu_chars": material["liu_chars"],
            "jianshu_chars": material["jianshu_chars"],
            "round_input_chars": {
                str(round_number): len(stable_json(_read_json(ROOT / output_dir / f"round-{round_number:02d}-input.json")))
                for round_number in range(0, MAX_EVIDENCE_ROUNDS + 1)
                if (ROOT / output_dir / f"round-{round_number:02d}-input.json").is_file()
            },
        },
        "retrieval": {"searched_corpora": list(SEARCHED_CORPORA), "trace_rows": len(search_trace), "seen_evidence_refs": sorted(seen_refs)},
        "protocol_errors": sorted(set(protocol_errors)),
        "transport_errors": [dict(row) for row in transport_errors],
        "semantic_failed_questions": sorted(set(semantic_failed_questions)),
        "canonical_write_back": False,
        "external_search_performed": False,
    }
    write_json(ROOT, output_dir / "usage.json", usage)
    convergence = {
        "schema": "srm0-4b-convergence",
        "schema_version": SCHEMA_VERSION,
        "story_id": story_id,
        "execution_kind": execution_kind,
        "run_id": run_id,
        "story_status": status,
        "round_metrics": [dict(row) for row in round_metrics],
        "question_terminals": {key: questions[key].get("terminal_reason") for key in sorted(questions)},
        "canonical_write_back": False,
        "external_search_performed": False,
        "transport_errors": [dict(row) for row in transport_errors],
    }
    write_json(ROOT, output_dir / "convergence.json", convergence)
    artifact_names = sorted(path.name for path in (ROOT / output_dir).iterdir() if path.is_file() and path.name != "manifest.json")
    manifest = {
        "schema": "srm0-4b-manifest",
        "schema_version": SCHEMA_VERSION,
        "story_id": story_id,
        "execution_kind": execution_kind,
        "run_id": run_id,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "source_artifacts": material.get("source_artifacts", {}),
        "artifact_hashes": {name: sha256_file(ROOT, output_dir / name) for name in artifact_names},
        "completion_count": api_calls,
        "tool_call_count": 0,
        "external_search_performed": False,
        "canonical_write_back": False,
        "protocol_errors": sorted(set(protocol_errors)),
        "transport_errors": [dict(row) for row in transport_errors],
        "semantic_failed_questions": sorted(set(semantic_failed_questions)),
    }
    write_json(ROOT, output_dir / "manifest.json", manifest)


def _run_story(material: Mapping[str, Any], *, args: argparse.Namespace, registry: Mapping[str, Mapping[str, Any]] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    story_id = str(material["story_id"])
    if args.fixture:
        execution_kind = "fixture"
        run_id = None
        output_dir = output_directory(story_id, execution_kind="fixture", fixture_version=fixture_version())
    else:
        execution_kind = "live_model"
        run_id = run_id_for(material)
        output_dir = output_directory(story_id, execution_kind="live_model", run_id=run_id)
    if not args.replay_existing:
        _reset_target(output_dir)
    (ROOT / output_dir).mkdir(parents=True, exist_ok=True)

    questions: dict[str, dict[str, Any]] = {}
    histories: dict[str, list[dict[str, Any]]] = {}
    seen_refs: set[str] = set()
    events: list[dict[str, Any]] = []
    search_trace: list[dict[str, Any]] = []
    round_metrics: list[dict[str, Any]] = []
    usage_rows: list[dict[str, Any]] = []
    all_normalizations: list[dict[str, Any]] = []
    all_rejected_claims: list[dict[str, Any]] = []
    all_rejected_evidence: list[dict[str, Any]] = []
    protocol_errors: list[str] = []
    transport_errors: list[dict[str, Any]] = []
    semantic_failed_questions: list[str] = []
    api_calls = 0
    json_repairs = 0

    initial = _stage_call(
        stage="main_text_gap_discovery", round_number=0, messages=build_initial_messages(material), output_dir=output_dir,
        execution_kind=execution_kind, fixture_value=_fixture_initial(material) if args.fixture else None,
        replay=args.replay_existing, timeout=args.timeout,
    )
    api_calls += int(initial["api_calls"])
    json_repairs += int(initial["repair"] not in {"none", "fixture"})
    usage_rows.append({"round": 0, "stage": "main_text_gap_discovery", "api_usage": usage_fields(initial["response"]), "json_repair": initial["repair"], "api_calls": initial["api_calls"]})
    _record_stage_failure("round 0", initial, protocol_errors, transport_errors)
    initial_normalized, initial_audit = normalize_initial_fail_soft(initial["raw"], material)
    all_normalizations.extend(initial_audit["normalizations"])
    accepted = initial_normalized.get("gaps", [])
    rejected_gaps = initial_audit["rejected_gaps"]
    _update_stage_artifact(output_dir / "round-00-output.json", {
        "normalized_output": initial_normalized,
        "accepted_gaps": accepted,
        "rejected_gaps": rejected_gaps,
        "structural_normalizations": initial_audit["normalizations"],
        "protocol_error": initial["error"],
        "canonical_write_back": False,
        "external_search_performed": False,
    })
    for row in rejected_gaps:
        events.append({"event": "gap_rejected", "story_id": story_id, "index": row.get("index"), "question_id": row.get("question_id"), "reason": row.get("reason")})
    for row in accepted:
        record = {
            **dict(row), "state": "unexplained", "working_answer": "", "supporting_refs": [], "remaining_gap": row["gap"],
            "reading_sufficient": False, "historical_verification_open": False, "next_action": "retrieve_local", "terminal_reason": None,
            "active": True, "last_round": 0, "evidence_rounds": 0, "claim_fingerprints": [], "conflict_fingerprints": [], "conflict_ids": [],
        }
        questions[str(row["question_id"])] = record
        histories[str(row["question_id"])] = []
        events.append({"event": "gap_accepted", "story_id": story_id, "question_id": row["question_id"], "story_span": row["story_span"]})

    status = "api_transport_failed" if transport_errors else "protocol_failed" if protocol_errors else "converged"
    if not accepted and not protocol_errors and not transport_errors:
        status = "no_valid_reading_gap"
    elif accepted and not protocol_errors and not transport_errors:
        frozen = [dict(row) for row in accepted]
        commentary = _stage_call(
            stage="attached_commentary_delta", round_number=1, messages=build_commentary_messages(material, frozen), output_dir=output_dir,
            execution_kind=execution_kind, fixture_value=_fixture_delta(material, frozen, retrieval=False) if args.fixture else None,
            replay=args.replay_existing, timeout=args.timeout,
        )
        api_calls += int(commentary["api_calls"])
        json_repairs += int(commentary["repair"] not in {"none", "fixture"})
        usage_rows.append({"round": 1, "stage": "attached_commentary_delta", "api_usage": usage_fields(commentary["response"]), "json_repair": commentary["repair"], "api_calls": commentary["api_calls"]})
        _record_stage_failure("round 1", commentary, protocol_errors, transport_errors)
        attached_sources = {str(row["ref"]): str(row.get("text", "")) for row in list(material.get("liu_notes", [])) + list(material.get("jianshu_notes", []))}
        delta, audit = normalize_delta_fail_soft(commentary["raw"], attached_sources, set(questions))
        all_normalizations.extend(audit["normalizations"])
        all_rejected_claims.extend(audit["rejected_claims"])
        all_rejected_evidence.extend(audit["rejected_evidence"])
        _update_stage_artifact(output_dir / "round-01-output.json", {
            "normalized_output": delta,
            "structural_normalizations": audit["normalizations"],
            "rejected_evidence": audit["rejected_evidence"],
            "rejected_claims": audit["rejected_claims"],
            "rejected_aspects": audit["rejected_aspects"],
            "rejected_updates": audit["rejected_updates"],
            "canonical_write_back": False,
            "external_search_performed": False,
        })
        updates = {str(row["question_id"]): row for row in delta.get("updates", []) if isinstance(row, Mapping)}
        q_metrics: list[dict[str, Any]] = []
        children_added: list[dict[str, Any]] = []
        for qid in sorted(list(questions)):
            if qid not in updates:
                questions[qid]["active"] = False
                if commentary["error"]:
                    questions[qid]["terminal_reason"] = "api_transport_failure" if commentary.get("failure_class") in TRANSPORT_FAILURE_CLASSES else "protocol_failure"
                else:
                    questions[qid]["terminal_reason"] = "semantic_update_failed"
                    semantic_failed_questions.append(qid)
                continue
            prior = dict(questions[qid])
            current, metric = _apply_update(questions[qid], updates[qid], round_number=1, prior=prior, seen_refs=seen_refs, histories=histories)
            questions[qid] = current
            q_metrics.append(metric)
            children, rejected_children = make_children_b(prior, updates[qid], set(questions))
            for rejected in rejected_children:
                events.append({"event": "child_question_rejected", "story_id": story_id, "question_id": qid, **rejected})
            if children:
                current["active"] = False
                current["terminal_reason"] = "refined_to_child"
                for child in children:
                    child_record = {
                        **child, "state": "unexplained", "working_answer": "", "supporting_refs": [], "remaining_gap": child["gap"],
                        "reading_sufficient": False, "historical_verification_open": False, "next_action": "retrieve_local", "terminal_reason": None,
                        "active": True, "last_round": 1, "evidence_rounds": 0, "claim_fingerprints": [], "conflict_fingerprints": [], "conflict_ids": [],
                    }
                    questions[child["question_id"]] = child_record
                    histories[child["question_id"]] = []
                    children_added.append(child)
                    events.append({"event": "child_question_created", "story_id": story_id, "question_id": child["question_id"], "parent_question_id": child["parent_question_id"], "parent_aspect_id": child["parent_aspect_id"]})
            else:
                _mark_stop(questions[qid], histories, retrieval_attempts=0, adequate_attempts=0, evidence_round_count=1)
        for metric in q_metrics:
            metric["Q_t"] = int(any(child.get("parent_question_id") == metric["question_id"] for child in children_added))
        used = sorted({ref for metric in q_metrics for ref in metric.get("used_evidence_refs", [])})
        new = sorted({ref for metric in q_metrics for ref in metric.get("new_used_evidence_refs", [])})
        round_metrics.append({
            "round": 1, "G_t": len(accepted), "D_t": int(any(metric.get("D_t") for metric in q_metrics)),
            "N_t": round(len(new) / len(used), 6) if used else 0.0, "Q_t": int(bool(children_added)),
            "used_evidence_refs": used, "new_used_evidence_refs": new, "question_metrics": q_metrics, "retrieval": False,
        })
        events.append({"event": "semantic_delta_processed", "story_id": story_id, "round": 1, "used_refs": used, "D_t": round_metrics[-1]["D_t"]})

        current_round = 2
        if not protocol_errors and registry is None and any(row.get("active") for row in questions.values()):
            registry = build_registry(ROOT)
        retrieval_attempts: dict[str, int] = {qid: 0 for qid in questions}
        adequate_attempts: dict[str, int] = {qid: 0 for qid in questions}
        while not protocol_errors and not transport_errors and any(row.get("active") for row in questions.values()) and current_round <= MAX_EVIDENCE_ROUNDS:
            active = [questions[qid] for qid in sorted(questions) if questions[qid].get("active")]
            retrieved_by_ref: dict[str, dict[str, Any]] = {}
            per_question: dict[str, dict[str, Any]] = {}
            for question in active:
                qid = str(question["question_id"])
                query = f"{question.get('gap', '')} {question.get('story_span', '')}"
                result = search_registry(registry or {}, query=query, exclude_story=story_id)
                opened = open_candidates(result)
                for row in opened:
                    if row.get("ref"):
                        retrieved_by_ref.setdefault(str(row["ref"]), dict(row))
                retrieval_attempts[qid] = retrieval_attempts.get(qid, 0) + 1
                per_question[qid] = {"result": result, "opened": opened}
            candidates = sorted(retrieved_by_ref.values(), key=lambda row: (-int(row.get("score", 0)), str(row.get("work", "")), str(row.get("ref", ""))))[:5]
            retrieval_messages = build_retrieval_messages(material, active, candidates, questions)
            retrieval = _stage_call(
                stage="local_retrieval_delta", round_number=current_round, messages=retrieval_messages, output_dir=output_dir,
                execution_kind=execution_kind, fixture_value=_fixture_delta(material, active, retrieval=True, candidates=candidates) if args.fixture else None,
                replay=args.replay_existing, timeout=args.timeout,
            )
            api_calls += int(retrieval["api_calls"])
            json_repairs += int(retrieval["repair"] not in {"none", "fixture"})
            usage_rows.append({"round": current_round, "stage": "local_retrieval_delta", "api_usage": usage_fields(retrieval["response"]), "json_repair": retrieval["repair"], "api_calls": retrieval["api_calls"]})
            _record_stage_failure(f"round {current_round}", retrieval, protocol_errors, transport_errors)
            if retrieval["error"]:
                break
            candidate_sources = {str(row["ref"]): str((registry or {}).get(str(row["ref"]), {}).get("text", "")) for row in candidates}
            delta, audit = normalize_delta_fail_soft(retrieval["raw"], candidate_sources, {str(row["question_id"]) for row in active})
            all_normalizations.extend(audit["normalizations"])
            all_rejected_claims.extend(audit["rejected_claims"])
            all_rejected_evidence.extend(audit["rejected_evidence"])
            _update_stage_artifact(output_dir / f"round-{current_round:02d}-output.json", {
                "candidate_refs": [str(row["ref"]) for row in candidates],
                "normalized_output": delta,
                "structural_normalizations": audit["normalizations"],
                "rejected_evidence": audit["rejected_evidence"],
                "rejected_claims": audit["rejected_claims"],
                "rejected_aspects": audit["rejected_aspects"],
                "rejected_updates": audit["rejected_updates"],
                "canonical_write_back": False,
                "external_search_performed": False,
            })
            updates = {str(row["question_id"]): row for row in delta.get("updates", []) if isinstance(row, Mapping)}
            q_metrics = []
            children_added = []
            round_used: set[str] = set()
            for question in active:
                qid = str(question["question_id"])
                if qid not in updates:
                    questions[qid]["active"] = False
                    if retrieval["error"]:
                        questions[qid]["terminal_reason"] = "api_transport_failure" if retrieval.get("failure_class") in TRANSPORT_FAILURE_CLASSES else "protocol_failure"
                    else:
                        questions[qid]["terminal_reason"] = "semantic_update_failed"
                        semantic_failed_questions.append(qid)
                    continue
                prior = dict(questions[qid])
                current, metric = _apply_update(questions[qid], updates[qid], round_number=current_round, prior=prior, seen_refs=seen_refs, histories=histories)
                questions[qid] = current
                q_metrics.append(metric)
                round_used.update(metric.get("used_evidence_refs", []))
                if metric.get("used_evidence_refs"):
                    adequate_attempts[qid] = adequate_attempts.get(qid, 0) + 1
                children, rejected_children = make_children_b(prior, updates[qid], set(questions))
                for rejected in rejected_children:
                    events.append({"event": "child_question_rejected", "story_id": story_id, "question_id": qid, "round": current_round, **rejected})
                if children:
                    current["active"] = False
                    current["terminal_reason"] = "refined_to_child"
                    for child in children:
                        child_record = {
                            **child, "state": "unexplained", "working_answer": "", "supporting_refs": [], "remaining_gap": child["gap"],
                            "reading_sufficient": False, "historical_verification_open": False, "next_action": "retrieve_local", "terminal_reason": None,
                            "active": True, "last_round": current_round, "evidence_rounds": 0, "claim_fingerprints": [], "conflict_fingerprints": [], "conflict_ids": [],
                        }
                        questions[child["question_id"]] = child_record
                        histories[child["question_id"]] = []
                        children_added.append(child)
                        events.append({"event": "child_question_created", "story_id": story_id, "round": current_round, "question_id": child["question_id"], "parent_question_id": child["parent_question_id"], "parent_aspect_id": child["parent_aspect_id"]})
                _mark_stop(questions[qid], histories, retrieval_attempts=retrieval_attempts.get(qid, 0), adequate_attempts=adequate_attempts.get(qid, 0), evidence_round_count=current_round)
            for metric in q_metrics:
                metric["Q_t"] = int(any(child.get("parent_question_id") == metric["question_id"] for child in children_added))
            round_new = sorted({ref for metric in q_metrics for ref in metric.get("new_used_evidence_refs", [])})
            for qid, search_data in sorted(per_question.items()):
                result = search_data["result"]
                opened = search_data["opened"]
                q_used = sorted(set(round_used).intersection(str(row.get("ref")) for row in opened))
                q_new = sorted(set(round_new).intersection(q_used))
                rejected_for_q = [dict(row) for row in audit["rejected_evidence"] if str(row.get("path", "")).startswith(f"$.updates[")]
                search_trace.append({
                    "round": current_round, "question_id": qid, "searched_corpora": list(SEARCHED_CORPORA),
                    "retrieved_refs": [str(row.get("ref")) for row in result.get("hits", [])],
                    "opened_refs": [str(row.get("ref")) for row in opened], "used_refs": q_used, "new_used_refs": q_new,
                    "rejected_evidence": rejected_for_q,
                })
            round_metrics.append({
                "round": current_round, "G_t": len(active), "D_t": int(any(metric.get("D_t") for metric in q_metrics)),
                "N_t": round(len(round_new) / len(round_used), 6) if round_used else 0.0, "Q_t": int(bool(children_added)),
                "used_evidence_refs": sorted(round_used), "new_used_evidence_refs": round_new,
                "retrieved_evidence_count": len(retrieved_by_ref), "opened_evidence_count": len(candidates), "question_metrics": q_metrics, "retrieval": True,
            })
            events.append({"event": "retrieval_round_processed", "story_id": story_id, "round": current_round, "used_refs": sorted(round_used), "D_t": round_metrics[-1]["D_t"], "N_t": round_metrics[-1]["N_t"]})
            current_round += 1

        if transport_errors:
            for row in questions.values():
                if row.get("active"):
                    row["active"] = False
                    row["terminal_reason"] = "api_transport_failure"
            status = "api_transport_failed"
        elif protocol_errors:
            for row in questions.values():
                if row.get("active"):
                    row["active"] = False
                    row["terminal_reason"] = "protocol_failure"
            status = "protocol_failed"
        elif semantic_failed_questions:
            status = "semantic_partial_failure" if any(not row.get("active") for row in questions.values()) else "semantic_failed"
        elif any(row.get("active") for row in questions.values()):
            for row in questions.values():
                if row.get("active"):
                    row["active"] = False
                    row["terminal_reason"] = "hard_cap"
            status = "hard_cap"
        else:
            status = "converged"

    all_rounds = [0] + [int(row["round"]) for row in round_metrics]
    summary = _fixture_or_live_summary(
        story_id, material, execution_kind=execution_kind, run_id=run_id, output_dir=output_dir, status=status,
        questions=questions, accepted=accepted, rejected_gaps=rejected_gaps, round_metrics=round_metrics, search_trace=search_trace,
        normalizations=all_normalizations, rejected_claims=all_rejected_claims, rejected_evidence=all_rejected_evidence,
        protocol_errors=protocol_errors, transport_errors=transport_errors, semantic_failed_questions=semantic_failed_questions, usage_rows=usage_rows, initial_rounds=all_rounds,
    )
    _write_state_and_aux(
        story_id=story_id, material=material, output_dir=output_dir, execution_kind=execution_kind, run_id=run_id, status=status,
        questions=questions, seen_refs=seen_refs, round_metrics=round_metrics, events=events, search_trace=search_trace,
        usage_rows=usage_rows, protocol_errors=protocol_errors, transport_errors=transport_errors, semantic_failed_questions=semantic_failed_questions,
        total_normalizations=all_normalizations, total_rejected_claims=all_rejected_claims, total_rejected_evidence=all_rejected_evidence,
        api_calls=api_calls, json_repairs=json_repairs,
    )
    return summary, {"output_dir": output_dir.as_posix(), "execution_kind": execution_kind, "run_id": run_id}


def _batch_summary(stories: Sequence[Mapping[str, Any]], *, execution_kind: str) -> dict[str, Any]:
    rows = [dict(row) for row in stories]
    terminal_counter = Counter(str(reason) for row in rows for reason in (row.get("terminal_reason_per_question") or {}).values() if reason)
    normalization_counter = Counter(str(row.get("action")) for story in rows for row in story.get("structural_normalizations", []) if row.get("action"))
    evidence_rounds = [len(row.get("evidence_rounds", [])) for row in rows]
    total_terminal = sum(terminal_counter.values())
    converged_stories = sum(row.get("convergence_status") == "converged" for row in rows)
    protocol_failures = sum(bool(row.get("protocol_errors")) for row in rows)
    transport_failures = sum(bool(row.get("transport_errors")) for row in rows)
    semantic_failures = sum(bool(row.get("semantic_failed_questions")) for row in rows)
    evaluable_rows = [row for row in rows if not row.get("transport_errors")]
    aggregate: dict[str, Any] = {
        "protocol_failure_count": protocol_failures,
        "api_transport_failure_count": transport_failures,
        "semantic_failure_count": semantic_failures,
        "evaluable_story_count": len(evaluable_rows),
        "reading_convergence_rate": round(sum(row.get("convergence_status") == "converged" for row in evaluable_rows) / max(1, len(evaluable_rows)), 3),
        "saturation_rate": round(terminal_counter["evidence_saturated"] / max(1, total_terminal), 3),
        "stable_conflict_rate": round(terminal_counter["stable_conflict"] / max(1, total_terminal), 3),
        "unresolved_no_evidence_rate": round(terminal_counter["unresolved_no_evidence"] / max(1, total_terminal), 3),
        "average_evidence_rounds": round(sum(evidence_rounds) / max(1, len(rows)), 3),
        "average_used_refs": round(sum(len(row.get("used_evidence", [])) for row in rows) / max(1, len(rows)), 3),
        "terminal_reason_counts": dict(sorted(terminal_counter.items())),
        "normalization_counts": dict(sorted(normalization_counter.items())),
        "rejected_claim_count": sum(len(row.get("rejected_claims", [])) for row in rows),
        "rejected_evidence_count": sum(len(row.get("rejected_evidence", [])) for row in rows),
        "valid_live_story_count": sum(not row.get("protocol_errors") and not row.get("transport_errors") and not row.get("semantic_failed_questions") for row in rows),
    }
    if execution_kind == "live_model":
        aggregate = {"live_story_count": len(rows), **aggregate}
    else:
        aggregate.pop("valid_live_story_count", None)
        aggregate = {"fixture_story_count": len(rows), "model_findings_count": 0, "fixture_is_plumbing_only": True, **aggregate}
    return {
        "schema": "srm0-4b-batch-summary",
        "schema_version": SCHEMA_VERSION,
        "execution_kind": execution_kind,
        "stories": rows,
        "aggregate": aggregate,
        "canonical_write_back": False,
        "external_search_performed": False,
    }


def run(args: argparse.Namespace) -> int:
    if args.fixture and args.replay_existing:
        raise SystemExit("--fixture cannot be combined with --replay-existing")
    story_ids = [args.story] if args.story else list(FIXED_STORIES)
    invalid = [story_id for story_id in story_ids if story_id not in FIXED_STORIES]
    if invalid:
        raise SystemExit(f"Story is not in frozen SRM0.4B set: {', '.join(invalid)}")
    if not args.fixture and not args.replay_existing:
        preflight = run_live_preflight(args.timeout)
        if preflight.get("classification") != "reachable":
            return 2
    registry: Mapping[str, Mapping[str, Any]] | None = None
    summaries: list[dict[str, Any]] = []
    for story_id in story_ids:
        summary, _ = _run_story(story_material(ROOT, story_id), args=args, registry=registry)
        summaries.append(summary)
        if registry is None and summary.get("evidence_rounds"):
            registry = build_registry(ROOT)
    if not (ROOT / REVIEW_PATH).is_file():
        write_json(ROOT, REVIEW_PATH, review_template_b(story_ids))
    execution_kind = "fixture" if args.fixture else "live_model"
    path = FIXTURE_SUMMARY_PATH if args.fixture else LIVE_SUMMARY_PATH
    write_json(ROOT, path, _batch_summary(summaries, execution_kind=execution_kind))
    previous_status = _read_json(ROOT / STATUS_PATH)
    fixture_present = bool(previous_status.get("fixture_results_present")) or args.fixture
    if args.fixture:
        write_status(ROOT, stage="fixture_validated", fixture_results_present=True, live_results_present=False)
    elif not args.replay_existing:
        write_status(ROOT, stage="live_run_complete", fixture_results_present=fixture_present, live_results_present=True)
    print(f"SRM0.4B completed ({execution_kind})")
    print("stories:", ", ".join(story_ids))
    for row in summaries:
        print(f"{row['story_id']}: status={row['story_status']} accepted={len(row['accepted_gaps'])} rounds={len(row['evidence_rounds'])} used={len(row['used_evidence'])} protocol={row['protocol_failure_count']} semantic={row['semantic_failure_count']}")
    print("summary:", path.as_posix())
    return 1 if any(row.get("protocol_errors") or row.get("transport_errors") for row in summaries) else 0


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
