#!/usr/bin/env python3
"""SRM0.5 fresh-story evaluation runner.

This module is an evaluation wrapper around the frozen SRM0.4 contracts.  It
does not edit those contracts or their generated artifacts.  Selection is
local and deterministic; live execution requires a reachable DeepSeek API and
is kept in a new ``srm0-5`` namespace.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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

from ds1_common import ROOT, sha256_file, stable_json  # noqa: E402
import run_srm0_4b as frozen  # noqa: E402
from srm0_4a_common import (  # noqa: E402
    EXCLUDED_STORIES as RECORDED_EXCLUSIONS,
    classify_metrics,
    story_ids_from_corpus,
    story_material,
)
from srm0_4b_common import (  # noqa: E402
    FIXED_STORIES as PRIOR_SELECTED_STORIES,
    MAX_EVIDENCE_ROUNDS,
    MODEL,
    PROMPT_VERSION,
    PROVIDER,
    SEARCHED_CORPORA,
    TRANSPORT_FAILURE_CLASSES,
    build_commentary_messages,
    build_initial_messages,
    build_registry,
    build_retrieval_messages,
    derive_state_b,
    make_children_b,
    material_delta_b,
    normalize_delta_fail_soft,
    normalize_initial_fail_soft,
    open_candidates,
    search_registry,
    stop_reason_b,
)
from srm0_4c_transport import (  # noqa: E402
    API_URL,
    CONNECT_TIMEOUT,
    READ_TIMEOUT,
    DeepSeekTransport,
)


SCHEMA_VERSION = 1
STAGE = "srm0.5-fresh-story-generalization"
SELECTION_PATH = Path("data/generated/srm0/srm0-5-selection.json")
OUTPUT_ROOT = Path("data/generated/srm0/srm0-5")
SUMMARY_PATH = OUTPUT_ROOT / "summary.json"
METRICS_PATH = OUTPUT_ROOT / "metrics.json"
FAILURE_REVIEW_PATH = Path("data/annotation/srm0-5-failure-review.json")
HUMAN_REVIEW_PATH = Path("data/annotation/srm0-5-human-review.json")
PREFLIGHT_PATH = Path("/tmp/srm0-5-live-preflight.json")
FIXTURE_VERSION = "fixture-v1"
MAX_INITIAL_GAPS = 3

_STORY_PATTERN = re.compile(r"\b\d{2}-[a-z][a-z-]+-\d{3}\b")
STRATA = ("rich_commentary", "medium_commentary", "low_context_control")
TARGETS = {"rich_commentary": 5, "medium_commentary": 5, "low_context_control": 5}
TERMINAL_STATES = {
    "reading_sufficient",
    "evidence_saturated",
    "stable_conflict",
    "unresolved_no_evidence",
    "not_worth_pursuing",
    "hard_cap",
}


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(value), encoding="utf-8")


def _hash_value(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def _selection_key(story_id: str) -> str:
    return hashlib.sha256(story_id.encode("utf-8")).hexdigest()


def prior_srm_story_ids(root: Path = ROOT) -> set[str]:
    """Return all Story IDs recorded by earlier SRM artifacts.

    Retrieval-hit Stories are included deliberately: they were exposed to a
    previous model packet, so excluding them gives the fresh evaluation the
    stricter interpretation of "previously unseen".  The current namespace
    is never scanned as an input to its own selection.
    """
    excluded = set(RECORDED_EXCLUSIONS) | set(PRIOR_SELECTED_STORIES)
    roots = [root / "data" / "generated" / "srm0", root / "data" / "annotation"]
    for base in roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or "srm0-5" in path.as_posix():
                continue
            if base.name == "annotation" and "srm" not in path.name.lower():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            excluded.update(_STORY_PATTERN.findall(text))
    return excluded


def _algorithm_snapshot(root: Path = ROOT) -> dict[str, str]:
    paths = (
        Path("scripts/srm0_4a_common.py"),
        Path("scripts/srm0_4b_common.py"),
        Path("scripts/run_srm0_4b.py"),
        Path("scripts/srm0_4c_transport.py"),
    )
    return {path.as_posix(): sha256_file(root, path) for path in paths if (root / path).is_file()}


def selection_document(root: Path = ROOT) -> dict[str, Any]:
    excluded = prior_srm_story_ids(root)
    rows: list[dict[str, Any]] = []
    for story_id in story_ids_from_corpus(root):
        if story_id in excluded:
            continue
        material = story_material(root, story_id)
        stratum = classify_metrics(material)
        if stratum not in TARGETS:
            continue
        rows.append({
            "story_id": story_id,
            "stratum": stratum,
            "main_text_chars": int(material["main_text_chars"]),
            "liu_block_count": int(material["liu_block_count"]),
            "jianshu_chars": int(material["jianshu_chars"]),
            "exclusion_basis": "fresh: absent from all recorded prior SRM Story/evidence IDs",
            "deterministic_selection_key": _selection_key(story_id),
        })
    selected: list[dict[str, Any]] = []
    candidate_counts: dict[str, int] = {}
    for stratum in STRATA:
        candidates = sorted(
            (row for row in rows if row["stratum"] == stratum),
            key=lambda row: (row["deterministic_selection_key"], row["story_id"]),
        )
        candidate_counts[stratum] = len(candidates)
        selected.extend(candidates[: TARGETS[stratum]])
    selected.sort(key=lambda row: (STRATA.index(str(row["stratum"])), row["deterministic_selection_key"], row["story_id"]))
    return {
        "schema": "srm0-5-selection",
        "schema_version": SCHEMA_VERSION,
        "stage": "deterministic_fresh_story_selection",
        "selected": selected,
        "selected_story_ids": [row["story_id"] for row in selected],
        "stratum_targets": dict(TARGETS),
        "candidate_counts_after_exclusion": candidate_counts,
        "excluded_stories": sorted(excluded),
        "exclusion_policy": "all Story IDs recorded by prior SRM artifacts, including retrieved evidence hits, are excluded",
        "richness_rules": {
            "rich_commentary": {"main_text_chars_min": 50, "liu_blocks_min": 4, "jianshu_chars_min": 500},
            "medium_commentary": {"liu_blocks_min": 1, "jianshu_chars_min": 100, "not_rich": True},
            "low_context_control": {"liu_blocks_max": 1, "jianshu_chars_max": 99},
        },
        "selection_rationale": "Within each deterministic commentary stratum, SHA-256(Story ID) ordering selects the first five eligible records; no model output or success signal participates.",
        "prompt_version": PROMPT_VERSION,
        "max_evidence_rounds": MAX_EVIDENCE_ROUNDS,
        "algorithm_snapshot": _algorithm_snapshot(root),
        "canonical_write_back": False,
    }


def ensure_selection(root: Path = ROOT, *, write: bool = True) -> dict[str, Any]:
    expected = selection_document(root)
    if (root / SELECTION_PATH).is_file():
        current = _read(root / SELECTION_PATH)
        if current.get("selected_story_ids") != expected.get("selected_story_ids"):
            raise RuntimeError("existing SRM0.5 selection differs from deterministic fresh selection")
        return current
    if write:
        _write(root / SELECTION_PATH, expected)
        _write(root / OUTPUT_ROOT / "selection.json", expected)
    return expected


def protocol_freeze_document(root: Path = ROOT, selection: Mapping[str, Any] | None = None) -> dict[str, Any]:
    selection = selection or ensure_selection(root, write=False)
    return {
        "schema": "srm0-5-protocol-freeze",
        "schema_version": SCHEMA_VERSION,
        "stage": STAGE,
        "prompt_version": PROMPT_VERSION,
        "model": MODEL,
        "provider": PROVIDER,
        "parameters": {
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "tools": [],
            "connect_timeout": CONNECT_TIMEOUT,
            "read_timeout": READ_TIMEOUT,
            "max_evidence_rounds": MAX_EVIDENCE_ROUNDS,
        },
        "selection_hash": _hash_value(selection.get("selected_story_ids", [])),
        "algorithm_snapshot": dict(selection.get("algorithm_snapshot") or _algorithm_snapshot(root)),
        "canonical_write_back": False,
    }


def _run_id(material: Mapping[str, Any], protocol: Mapping[str, Any]) -> str:
    value = {"story_id": material["story_id"], "source_sha256": material.get("source_sha256"), "prompt_version": PROMPT_VERSION, "selection_hash": protocol.get("selection_hash")}
    return f"srm0-5-live-{_hash_value(value)[:16]}"


def _output_dir(root: Path, story_id: str, *, execution_kind: str, run_id: str | None = None) -> Path:
    if execution_kind == "fixture":
        return root / OUTPUT_ROOT / "fixture" / FIXTURE_VERSION / story_id
    if not run_id:
        raise ValueError("live output requires run_id")
    return root / OUTPUT_ROOT / "live" / story_id / run_id


def _response_content(response: Mapping[str, Any] | None) -> str:
    choices = response.get("choices") if isinstance(response, Mapping) else None
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
        return ""
    message = choices[0].get("message")
    content = message.get("content") if isinstance(message, Mapping) else None
    return content if isinstance(content, str) else ""


def _usage(response: Mapping[str, Any] | None) -> dict[str, Any]:
    value = response.get("usage", {}) if isinstance(response, Mapping) else {}
    return dict(value) if isinstance(value, Mapping) else {}


def _save_transport_attempts(run_dir: Path, result: Mapping[str, Any], *, round_number: int, stage: str) -> None:
    attempts = result.get("attempts") if isinstance(result.get("attempts"), list) else []
    final_attempt = int(attempts[-1].get("attempt", -1)) if attempts and isinstance(attempts[-1], Mapping) else -1
    for record in attempts:
        if not isinstance(record, Mapping):
            continue
        value = {"schema": "srm0-5-transport-attempt", "schema_version": SCHEMA_VERSION, "stage": stage, "round": round_number, **dict(record)}
        if int(record.get("attempt", -2)) == final_attempt and result.get("response") is not None:
            value["raw_response"] = dict(result["response"])
            value["raw_content"] = str(result.get("content") or "")
        _write(run_dir / "attempts" / f"round-{round_number:02d}-attempt-{int(record.get('attempt', 0)):02d}.json", value)


def _stage_call(
    *, root: Path, run_dir: Path, story_id: str, round_number: int, stage: str,
    messages: Sequence[Mapping[str, Any]], transport: DeepSeekTransport | None,
    fixture_value: Any | None = None,
) -> dict[str, Any]:
    input_artifact = {
        "schema": "srm0-5-model-input",
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "round": round_number,
        "execution_kind": "fixture" if fixture_value is not None else "live_model",
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "parameters": {"temperature": 0, "response_format": {"type": "json_object"}, "tools": [], "connect_timeout": CONNECT_TIMEOUT, "read_timeout": READ_TIMEOUT},
        "messages": [dict(row) for row in messages],
        "canonical_write_back": False,
        "external_search_performed": False,
    }
    _write(run_dir / f"round-{round_number:02d}-input.json", input_artifact)
    if fixture_value is not None:
        raw = fixture_value
        content = stable_json(raw)
        response = None
        result = {"success": True, "raw": raw, "content": content, "response": response, "attempts": [], "api_calls": 0, "failure_class": None, "error": None, "json_repair": "fixture"}
    else:
        if transport is None:
            raise RuntimeError("live stage requires transport")
        response_result = transport.call(story_id=story_id, round_number=round_number, completion_kind=stage, messages=messages, max_retries=1)
        _save_transport_attempts(run_dir, response_result, round_number=round_number, stage=stage)
        content = str(response_result.get("content") or "")
        raw: Any = None
        parse_error: str | None = None
        repair = "none"
        if response_result.get("success"):
            try:
                raw, repair = frozen.parse_json_any(content)
            except Exception as exc:  # protocol failure, raw content remains immutable
                parse_error = str(exc)
                repair = "error"
        result = {
            **dict(response_result),
            "raw": raw,
            "content": content,
            "json_repair": repair,
            "error": parse_error or response_result.get("error"),
            "failure_class": "protocol_failure" if parse_error else response_result.get("failure_class"),
            "api_calls": sum(int(bool(row.get("actual_request"))) for row in response_result.get("attempts", []) if isinstance(row, Mapping)),
        }
        response = response_result.get("response")
    artifact = {
        "schema": "srm0-5-model-output",
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "round": round_number,
        "execution_kind": "fixture" if fixture_value is not None else "live_model",
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "raw_response": dict(response or {}) if isinstance(response, Mapping) else {},
        "raw_content": str(result.get("content") or ""),
        "raw_output": result.get("raw"),
        "json_repair": result.get("json_repair", "none"),
        "json_repair_count": int(result.get("json_repair") not in {"none", "fixture", ""}),
        "api_usage": _usage(response if isinstance(response, Mapping) else None),
        "api_attempted": bool(result.get("api_calls")),
        "transport_attempts": [dict(row) for row in result.get("attempts", []) if isinstance(row, Mapping)],
        "protocol_error": result.get("error") if result.get("failure_class") == "protocol_failure" else None,
        "transport_error": result.get("error") if result.get("failure_class") in TRANSPORT_FAILURE_CLASSES else None,
        "failure_class": result.get("failure_class"),
        "canonical_write_back": False,
        "external_search_performed": False,
    }
    _write(run_dir / f"round-{round_number:02d}-output.json", artifact)
    return result


def _question_record(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **dict(row),
        "state": "unexplained",
        "working_answer": "",
        "supporting_refs": [],
        "remaining_gap": row.get("gap"),
        "reading_sufficient": False,
        "historical_verification_open": False,
        "next_action": "retrieve_local",
        "terminal_reason": None,
        "active": True,
        "last_round": 0,
        "evidence_rounds": 0,
        "claim_fingerprints": [],
        "conflict_fingerprints": [],
        "conflict_ids": [],
        "evidence_round_refs": [],
        "failure_type": None,
    }


def _compact_question(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "question_id", "parent_question_id", "parent_aspect_id", "story_span", "gap", "state", "working_answer",
        "supporting_refs", "remaining_gap", "reading_sufficient", "historical_verification_open", "next_action",
        "terminal_reason", "active", "last_round", "evidence_rounds", "evidence_round_refs", "failure_type",
    )
    return {key: row.get(key) for key in keys}


def _refs_from_update(update: Mapping[str, Any]) -> list[str]:
    refs: set[str] = set()
    for aspect in update.get("answered_aspects", []) if isinstance(update.get("answered_aspects"), list) else []:
        if isinstance(aspect, Mapping):
            refs.update(str(item.get("ref")) for item in aspect.get("evidence", []) if isinstance(item, Mapping) and item.get("ref"))
    for conflict in update.get("conflicts", []) if isinstance(update.get("conflicts"), list) else []:
        if isinstance(conflict, Mapping):
            refs.update(str(item.get("ref")) for item in conflict.get("evidence", []) if isinstance(item, Mapping) and item.get("ref"))
    return sorted(refs)


def _apply_update(question: dict[str, Any], update: Mapping[str, Any], *, round_number: int, seen_refs: set[str], histories: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, Any], dict[str, Any]]:
    used = _refs_from_update(update)
    current = derive_state_b(question, update)
    previous = question
    d_value = material_delta_b(previous if int(question.get("evidence_rounds", 0)) else None, current, used_refs=used)
    unique = sorted(set(used))
    new_refs = [ref for ref in unique if ref not in seen_refs]
    novelty = len(new_refs) / len(unique) if unique else 0.0
    seen_refs.update(unique)
    current.update({
        "last_round": round_number,
        "evidence_rounds": int(question.get("evidence_rounds", 0)) + 1,
        "evidence_round_refs": [*list(question.get("evidence_round_refs") or []), {"round": round_number, "refs": unique}],
        "failure_type": None,
    })
    metric = {
        "question_id": str(question["question_id"]),
        "round": round_number,
        "D_t": int(d_value),
        "N_t": round(novelty, 6),
        "Q_t": 0,
        "used_evidence_refs": unique,
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


def _source_family(ref: str, registry: Mapping[str, Mapping[str, Any]]) -> str:
    if ref.startswith("L"):
        return "liu_resolved"
    if ref.startswith("J"):
        return "jianshu_resolved"
    row = registry.get(ref, {}) if isinstance(registry, Mapping) else {}
    work = str(row.get("work") or "")
    if "晉書" in work:
        return "jinshu_resolved"
    if "三國志" in work:
        return "sanguozhi_resolved"
    if "資治通鑑" in work:
        return "zztj_resolved"
    if ref.startswith("shishuo:"):
        return "shishuo_resolved"
    if work == "世說新語":
        return "main_text_self_resolved"
    return "other_local_resolved"


def _question_resolution_source(row: Mapping[str, Any], registry: Mapping[str, Mapping[str, Any]]) -> list[str]:
    refs = sorted({
        ref
        for item in row.get("evidence_round_refs", [])
        if isinstance(item, Mapping)
        for ref in item.get("refs", [])
    })
    if refs:
        families = sorted({_source_family(ref, registry) for ref in refs})
        return ["multi_source_resolved"] if len(families) > 1 else families
    if row.get("terminal_reason") == "reading_sufficient" and not row.get("failure_type"):
        return ["main_text_self_resolved"]
    return ["unresolved"]


def _question_metrics(questions: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(questions.values())
    failures = {"semantic_failed", "protocol_failed", "transport_failed"}
    evaluable_rows = [row for row in rows if row.get("terminal_reason") != "refined_to_child"]
    valid = [row for row in evaluable_rows if row.get("failure_type") not in failures]
    terminal = [row for row in valid if row.get("terminal_reason") in TERMINAL_STATES]
    counts = Counter(str(row.get("terminal_reason")) for row in terminal)
    evaluable = len(evaluable_rows)
    return {
        "evaluable_question_count": evaluable,
        "valid_question_count": len(valid),
        "converged_question_count": len(terminal),
        "reading_sufficient_question_count": counts["reading_sufficient"],
        "evidence_saturated_question_count": counts["evidence_saturated"],
        "stable_conflict_question_count": counts["stable_conflict"],
        "unresolved_terminal_question_count": counts["unresolved_no_evidence"],
        "not_worth_pursuing_question_count": counts["not_worth_pursuing"],
        "hard_cap_question_count": counts["hard_cap"],
        "unresolved_question_count": sum(int(bool(row.get("active"))) for row in evaluable_rows),
        "semantic_failed_question_count": sum(row.get("failure_type") == "semantic_failed" for row in evaluable_rows),
        "protocol_failed_question_count": sum(row.get("failure_type") == "protocol_failed" for row in evaluable_rows),
        "transport_failed_question_count": sum(row.get("failure_type") == "transport_failed" for row in evaluable_rows),
        "terminal_state_counts": dict(sorted(counts.items())),
    }


def _story_status(questions: Mapping[str, Mapping[str, Any]], *, protocol_errors: Sequence[str], transport_errors: Sequence[Mapping[str, Any]], semantic_failed: Sequence[str], accepted: Sequence[Mapping[str, Any]]) -> str:
    if transport_errors:
        return "transport_failed"
    if protocol_errors:
        return "protocol_failed"
    if semantic_failed:
        return "semantic_partial_failure" if any(row.get("terminal_reason") in TERMINAL_STATES for row in questions.values()) else "semantic_failed"
    if not accepted:
        return "no_valid_reading_gap"
    return "converged" if not any(row.get("active") for row in questions.values()) else "active_unresolved"


def _jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def _story_transport_metrics(usage_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    attempts = [attempt for row in usage_rows for attempt in row.get("transport_attempts", []) if isinstance(attempt, Mapping)]
    successful = [float(attempt["elapsed_seconds"]) for attempt in attempts if attempt.get("failure_class") is None and isinstance(attempt.get("elapsed_seconds"), (int, float))]
    classes = Counter(str(attempt.get("failure_class")) for attempt in attempts if attempt.get("failure_class"))
    return {
        "transport_request_count": len(attempts),
        "transport_retry_count": max(0, len(attempts) - len(usage_rows)),
        "transport_success_count": len(successful),
        "tls_failure_count": classes["tls_failure"],
        "read_timeout_count": classes["read_timeout"],
        "connect_timeout_count": classes["connect_timeout"],
        "server_error_count": classes["server_error"],
        "failure_classes": dict(sorted(classes.items())),
        "successful_latencies_seconds": successful,
        "median_successful_latency_seconds": statistics.median(successful) if successful else None,
        "max_successful_latency_seconds": max(successful) if successful else None,
    }


def _retrieval_need_count(retrieval_attempts: Mapping[str, Any]) -> int:
    """Count questions that actually entered post-commentary retrieval."""
    return sum(1 for value in retrieval_attempts.values() if int(value or 0) > 0)


def _commentary_only_count(questions: Mapping[str, Mapping[str, Any]], retrieval_attempts: Mapping[str, Any]) -> int:
    return sum(
        1
        for qid, row in questions.items()
        if row.get("terminal_reason") == "reading_sufficient"
        and int(retrieval_attempts.get(qid, 0) or 0) == 0
    )


def _persist_story(root: Path, run_dir: Path, material: Mapping[str, Any], protocol: Mapping[str, Any], *, status: str, questions: Mapping[str, Mapping[str, Any]], events: Sequence[Mapping[str, Any]], search_trace: Sequence[Mapping[str, Any]], round_metrics: Sequence[Mapping[str, Any]], usage_rows: Sequence[Mapping[str, Any]], normalizations: Sequence[Mapping[str, Any]], rejected_gaps: Sequence[Mapping[str, Any]], rejected_claims: Sequence[Mapping[str, Any]], rejected_evidence: Sequence[Mapping[str, Any]], protocol_errors: Sequence[str], transport_errors: Sequence[Mapping[str, Any]], semantic_failed: Sequence[str], seen_refs: set[str], accepted: Sequence[Mapping[str, Any]], retrieval_attempts: Mapping[str, int], registry: Mapping[str, Mapping[str, Any]], execution_kind: str) -> dict[str, Any]:
    state = {
        "schema": "srm0-5-research-state",
        "schema_version": SCHEMA_VERSION,
        "story_id": material["story_id"],
        "execution_kind": execution_kind,
        "run_id": run_dir.name,
        "stage": "convergence_complete" if status == "converged" else status,
        "story_status": status,
        "questions": [_compact_question(questions[key]) for key in sorted(questions)],
        "active_questions": sorted(key for key, row in questions.items() if row.get("active")),
        "terminal_questions": sorted(key for key, row in questions.items() if row.get("terminal_reason") in TERMINAL_STATES),
        "seen_evidence_refs": sorted(seen_refs),
        "canonical_write_back": False,
        "external_search_performed": False,
        "protocol_errors": sorted(set(protocol_errors)),
        "transport_errors": [dict(row) for row in transport_errors],
        "semantic_failed_questions": sorted(set(semantic_failed)),
    }
    _write(run_dir / "research-state.json", state)
    _jsonl(run_dir / "events.jsonl", events)
    _jsonl(run_dir / "search-trace.jsonl", search_trace)
    usage = {
        "schema": "srm0-5-usage",
        "schema_version": SCHEMA_VERSION,
        "story_id": material["story_id"],
        "execution_kind": state["execution_kind"],
        "run_id": run_dir.name,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "rounds": [dict(row) for row in usage_rows],
        "total_tokens": sum(int((row.get("api_usage") or {}).get("total_tokens") or 0) for row in usage_rows),
        "prompt_tokens": sum(int((row.get("api_usage") or {}).get("prompt_tokens") or 0) for row in usage_rows),
        "completion_tokens": sum(int((row.get("api_usage") or {}).get("completion_tokens") or 0) for row in usage_rows),
        "successful_latencies_seconds": [float(v) for row in usage_rows for v in row.get("successful_latencies_seconds", [])],
        "canonical_write_back": False,
        "external_search_performed": False,
    }
    _write(run_dir / "usage.json", usage)
    convergence = {
        "schema": "srm0-5-convergence",
        "schema_version": SCHEMA_VERSION,
        "story_id": material["story_id"],
        "execution_kind": state["execution_kind"],
        "run_id": run_dir.name,
        "story_status": status,
        "round_metrics": [dict(row) for row in round_metrics],
        "question_metrics": _question_metrics(questions),
        "question_terminals": {key: questions[key].get("terminal_reason") for key in sorted(questions)},
        "canonical_write_back": False,
        "external_search_performed": False,
    }
    _write(run_dir / "convergence.json", convergence)
    artifact_hashes = {}
    for path in sorted(run_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            artifact_hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "schema": "srm0-5-manifest",
        "schema_version": SCHEMA_VERSION,
        "story_id": material["story_id"],
        "execution_kind": state["execution_kind"],
        "run_id": run_dir.name,
        "prompt_version": PROMPT_VERSION,
        "protocol_hash": _hash_value(protocol),
        "source_story_sha256": material.get("source_sha256"),
        "source_artifact_hashes": material.get("source_artifacts", {}),
        "artifact_hashes": artifact_hashes,
        "transport_attempt_count": sum(len(row.get("transport_attempts", [])) for row in usage_rows),
        "canonical_write_back": False,
        "external_search_performed": False,
    }
    _write(run_dir / "manifest.json", manifest)
    used = sorted({ref for row in round_metrics for ref in row.get("used_evidence_refs", [])})
    new_used = sorted({ref for row in round_metrics for ref in row.get("new_used_evidence_refs", [])})
    source_families = set()
    for ref in used:
        source_families.add(_source_family(ref, registry))
    qmetrics = _question_metrics(questions)
    latencies = [value for row in usage_rows for value in row.get("successful_latencies_seconds", [])]
    question_resolution_sources: dict[str, list[str]] = {}
    commentary_only_count = _commentary_only_count(questions, retrieval_attempts)
    external_retrieval_count = _retrieval_need_count(retrieval_attempts)
    for qid, row in questions.items():
        refs = sorted({ref for item in row.get("evidence_round_refs", []) if isinstance(item, Mapping) for ref in item.get("refs", [])})
        families = sorted({_source_family(ref, registry) for ref in refs})
        question_resolution_sources[qid] = _question_resolution_source(row, registry)
    transport_metrics = _story_transport_metrics(usage_rows)
    summary = {
        "story_id": material["story_id"],
        "stratum": None,
        "execution_kind": state["execution_kind"],
        "run_id": run_dir.name,
        "story_status": status,
        "convergence_status": "converged" if status == "converged" else status,
        "main_text_chars": material["main_text_chars"],
        "liu_block_count": material["liu_block_count"],
        "jianshu_chars": material["jianshu_chars"],
        "initial_gaps": [dict(row) for row in accepted],
        "accepted_gaps": [dict(row) for row in accepted],
        "rejected_gaps": [dict(row) for row in rejected_gaps],
        "story_text": material["main_text"],
        "questions": [_compact_question(questions[key]) for key in sorted(questions)],
        "rounds_executed": sorted({int(row.get("round", 0)) for row in round_metrics} | {0}),
        "evidence_rounds": [dict(row) for row in round_metrics],
        "searched_corpora": list(SEARCHED_CORPORA) if search_trace else [],
        "search_trace_count": len(search_trace),
        "retrieved_refs": sorted({ref for row in search_trace for ref in row.get("retrieved_refs", [])}),
        "opened_refs": sorted({ref for row in search_trace for ref in row.get("opened_refs", [])}),
        "used_evidence": used,
        "new_used_evidence": new_used,
        "resolution_sources": sorted(source_families),
        "question_resolution_sources": question_resolution_sources,
        "commentary_only_resolution_count": commentary_only_count,
        "external_retrieval_required_count": external_retrieval_count,
        "question_metrics": qmetrics,
        "terminal_reason_per_question": {key: questions[key].get("terminal_reason") for key in sorted(questions)},
        "round_metrics": [dict(row) for row in round_metrics],
        "protocol_errors": sorted(set(protocol_errors)),
        "transport_errors": [dict(row) for row in transport_errors],
        "semantic_failed_questions": sorted(set(semantic_failed)),
        "structural_normalizations": [dict(row) for row in normalizations],
        "rejected_claims": [dict(row) for row in rejected_claims],
        "rejected_evidence": [dict(row) for row in rejected_evidence],
        "token_usage": {
            "prompt_tokens": sum(int((row.get("api_usage") or {}).get("prompt_tokens") or 0) for row in usage_rows),
            "completion_tokens": sum(int((row.get("api_usage") or {}).get("completion_tokens") or 0) for row in usage_rows),
            "total_tokens": sum(int((row.get("api_usage") or {}).get("total_tokens") or 0) for row in usage_rows),
        },
        "latency_seconds": {"successful": latencies, "mean": statistics.mean(latencies) if latencies else None, "median": statistics.median(latencies) if latencies else None, "max": max(latencies) if latencies else None},
        "retrieval_attempts": dict(sorted(retrieval_attempts.items())),
        "transport_metrics": transport_metrics,
        "canonical_write_back": False,
        "external_search_performed": False,
    }
    return summary


def _record_failure(story_id: str, round_number: int, stage_result: Mapping[str, Any], protocol_errors: list[str], transport_errors: list[dict[str, Any]]) -> None:
    error = stage_result.get("error")
    if not error:
        return
    failure = str(stage_result.get("failure_class") or "protocol_failure")
    if failure in TRANSPORT_FAILURE_CLASSES:
        transport_errors.append({"story_id": story_id, "round": round_number, "failure_class": failure, "message": str(error)})
    else:
        protocol_errors.append(f"round {round_number}: {error}")


def run_story(root: Path, story_id: str, protocol: Mapping[str, Any], *, transport: DeepSeekTransport | None, fixture: bool = False, registry: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    material = story_material(root, story_id)
    run_id = f"srm0-5-fixture-{FIXTURE_VERSION}" if fixture else _run_id(material, protocol)
    run_dir = _output_dir(root, story_id, execution_kind="fixture" if fixture else "live_model", run_id=run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    registry = registry if registry is not None else build_registry(root)
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
    rejected_gaps: list[dict[str, Any]] = []
    protocol_errors: list[str] = []
    transport_errors: list[dict[str, Any]] = []
    semantic_failed: list[str] = []
    retrieval_attempts: dict[str, int] = {}
    adequate_attempts: dict[str, int] = {}

    initial_messages = build_initial_messages(material)
    initial = _stage_call(root=root, run_dir=run_dir, story_id=story_id, round_number=0, stage="main_text_gap_discovery", messages=initial_messages, transport=transport, fixture_value=frozen._fixture_initial(material) if fixture else None)
    usage_rows.append({"round": 0, "stage": "main_text_gap_discovery", "api_usage": _usage(initial.get("response")), "transport_attempts": initial.get("attempts", []), "successful_latencies_seconds": [float(row.get("elapsed_seconds")) for row in initial.get("attempts", []) if isinstance(row, Mapping) and row.get("failure_class") is None], "api_calls": initial.get("api_calls", 0)})
    _record_failure(story_id, 0, initial, protocol_errors, transport_errors)
    normalized, audit = normalize_initial_fail_soft(initial.get("raw"), material)
    normalizations.extend(audit.get("normalizations", []))
    rejected_gaps.extend(audit.get("rejected_gaps", []))
    accepted = normalized.get("gaps", []) if isinstance(normalized.get("gaps"), list) else []
    output = _read(run_dir / "round-00-output.json")
    output.update({"normalized_output": normalized, "accepted_gaps": accepted, "rejected_gaps": rejected_gaps, "structural_normalizations": audit.get("normalizations", [])})
    _write(run_dir / "round-00-output.json", output)
    for row in accepted:
        qid = str(row["question_id"])
        questions[qid] = _question_record(row)
        histories[qid] = []
        retrieval_attempts[qid] = 0
        adequate_attempts[qid] = 0
        events.append({"event": "gap_accepted", "story_id": story_id, "question_id": qid, "story_span": row["story_span"]})
    for row in rejected_gaps:
        events.append({"event": "gap_rejected", "story_id": story_id, **dict(row)})

    if initial.get("error"):
        for row in questions.values():
            row["active"] = False
            row["failure_type"] = "transport_failed" if initial.get("failure_class") in TRANSPORT_FAILURE_CLASSES else "protocol_failed"
            row["terminal_reason"] = row["failure_type"]
    current_round = 1
    while accepted and not protocol_errors and not transport_errors and any(row.get("active") for row in questions.values()) and current_round <= MAX_EVIDENCE_ROUNDS:
        active = [questions[qid] for qid in sorted(questions) if questions[qid].get("active")]
        if not active:
            break
        per_question: dict[str, dict[str, Any]] | None = None
        candidates: list[dict[str, Any]] | None = None
        if current_round == 1:
            stage = "attached_commentary_delta"
            messages = build_commentary_messages(material, active)
        else:
            stage = "local_retrieval_delta"
            retrieved: dict[str, dict[str, Any]] = {}
            per_question = {}
            for question in active:
                qid = str(question["question_id"])
                query = f"{question.get('gap', '')} {question.get('story_span', '')}"
                result = search_registry(registry, query=query, exclude_story=story_id)
                opened = open_candidates(result)
                for row in opened:
                    if row.get("ref"):
                        retrieved.setdefault(str(row["ref"]), dict(row))
                retrieval_attempts[qid] = retrieval_attempts.get(qid, 0) + 1
                per_question[qid] = {"result": result, "opened": opened}
            candidates = sorted(retrieved.values(), key=lambda row: (-int(row.get("score", 0)), str(row.get("work", "")), str(row.get("ref", ""))))[:5]
            messages = build_retrieval_messages(material, active, candidates, questions)
        result = _stage_call(root=root, run_dir=run_dir, story_id=story_id, round_number=current_round, stage=stage, messages=messages, transport=transport, fixture_value=frozen._fixture_delta(material, active, retrieval=current_round >= 2, candidates=candidates or []) if fixture else None)
        usage_rows.append({"round": current_round, "stage": stage, "api_usage": _usage(result.get("response")), "transport_attempts": result.get("attempts", []), "successful_latencies_seconds": [float(row.get("elapsed_seconds")) for row in result.get("attempts", []) if isinstance(row, Mapping) and row.get("failure_class") is None], "api_calls": result.get("api_calls", 0)})
        _record_failure(story_id, current_round, result, protocol_errors, transport_errors)
        if result.get("error"):
            for row in active:
                row["active"] = False
                row["failure_type"] = "transport_failed" if result.get("failure_class") in TRANSPORT_FAILURE_CLASSES else "protocol_failed"
                row["terminal_reason"] = row["failure_type"]
            break
        if current_round == 1:
            sources = {str(row["ref"]): str(row.get("text", "")) for row in list(material.get("liu_notes", [])) + list(material.get("jianshu_notes", []))}
        else:
            sources = {str(row["ref"]): str((registry.get(str(row["ref"]), {}) or {}).get("text", "")) for row in candidates or []}
        delta, audit = normalize_delta_fail_soft(result.get("raw"), sources, {str(row["question_id"]) for row in active})
        normalizations.extend(audit.get("normalizations", []))
        rejected_claims.extend(audit.get("rejected_claims", []))
        rejected_evidence.extend(audit.get("rejected_evidence", []))
        output = _read(run_dir / f"round-{current_round:02d}-output.json")
        output.update({"normalized_output": delta, "structural_normalizations": audit.get("normalizations", []), "rejected_evidence": audit.get("rejected_evidence", []), "rejected_claims": audit.get("rejected_claims", []), "rejected_aspects": audit.get("rejected_aspects", []), "rejected_updates": audit.get("rejected_updates", [])})
        _write(run_dir / f"round-{current_round:02d}-output.json", output)
        updates = {str(row["question_id"]): row for row in delta.get("updates", []) if isinstance(row, Mapping)}
        qmetrics: list[dict[str, Any]] = []
        children_added: list[dict[str, Any]] = []
        round_used: set[str] = set()
        for question in active:
            qid = str(question["question_id"])
            if qid not in updates:
                questions[qid]["active"] = False
                questions[qid]["failure_type"] = "semantic_failed"
                questions[qid]["terminal_reason"] = "semantic_failed"
                semantic_failed.append(qid)
                continue
            prior = dict(questions[qid])
            current, metric = _apply_update(questions[qid], updates[qid], round_number=current_round, seen_refs=seen_refs, histories=histories)
            questions[qid] = current
            qmetrics.append(metric)
            round_used.update(metric["used_evidence_refs"])
            if current_round >= 2 and metric["used_evidence_refs"]:
                adequate_attempts[qid] = adequate_attempts.get(qid, 0) + 1
            children, rejected_children = make_children_b(prior, updates[qid], set(questions))
            for child_rejection in rejected_children:
                events.append({"event": "child_question_rejected", "story_id": story_id, "round": current_round, "question_id": qid, **dict(child_rejection)})
            if children:
                current["active"] = False
                current["terminal_reason"] = "refined_to_child"
                for child in children:
                    child_record = _question_record(child)
                    child_record["last_round"] = current_round
                    questions[child["question_id"]] = child_record
                    histories[child["question_id"]] = []
                    retrieval_attempts[child["question_id"]] = 0
                    adequate_attempts[child["question_id"]] = 0
                    children_added.append(child)
                    events.append({"event": "child_question_created", "story_id": story_id, "round": current_round, "question_id": child["question_id"], "parent_question_id": child["parent_question_id"], "parent_aspect_id": child["parent_aspect_id"]})
            else:
                _mark_stop(questions[qid], histories, retrieval_attempts=retrieval_attempts.get(qid, 0), adequate_attempts=adequate_attempts.get(qid, 0), evidence_round_count=current_round)
        for metric in qmetrics:
            metric["Q_t"] = int(any(child.get("parent_question_id") == metric["question_id"] for child in children_added))
        round_new = sorted({ref for metric in qmetrics for ref in metric.get("new_used_evidence_refs", [])})
        used = sorted(round_used)
        round_row = {
            "round": current_round,
            "G_t": len(active),
            "D_t": int(any(metric.get("D_t") for metric in qmetrics)),
            "N_t": round(len(round_new) / len(used), 6) if used else 0.0,
            "Q_t": int(bool(children_added)),
            "used_evidence_refs": used,
            "new_used_evidence_refs": round_new,
            "question_metrics": qmetrics,
            "retrieval": current_round >= 2,
        }
        if candidates is not None:
            round_row["retrieved_evidence_count"] = len({ref for row in per_question.values() for ref in [hit.get("ref") for hit in row["result"].get("hits", [])] if ref}) if per_question else 0
            round_row["opened_evidence_count"] = len(candidates)
        round_metrics.append(round_row)
        if per_question is not None:
            for qid, data in sorted(per_question.items()):
                result_data = data["result"]
                opened = data["opened"]
                q_used = sorted(set(round_used).intersection(str(row.get("ref")) for row in opened))
                q_new = sorted(set(round_new).intersection(q_used))
                search_trace.append({
                    "round": current_round,
                    "question_id": qid,
                    "searched_corpora": list(SEARCHED_CORPORA),
                    "retrieved_refs": [str(row.get("ref")) for row in result_data.get("hits", []) if row.get("ref")],
                    "opened_refs": [str(row.get("ref")) for row in opened if row.get("ref")],
                    "used_refs": q_used,
                    "new_used_refs": q_new,
                    "rejected_evidence": [dict(row) for row in rejected_evidence if str(row.get("ref")) in set(str(item.get("ref")) for item in opened)],
                })
        events.append({"event": "semantic_delta_processed", "story_id": story_id, "round": current_round, "used_refs": used, "D_t": round_row["D_t"], "N_t": round_row["N_t"], "Q_t": round_row["Q_t"]})
        current_round += 1

    if accepted and any(row.get("active") for row in questions.values()) and current_round > MAX_EVIDENCE_ROUNDS:
        for row in questions.values():
            if row.get("active"):
                row["active"] = False
                row["terminal_reason"] = "hard_cap"
    status = _story_status(questions, protocol_errors=protocol_errors, transport_errors=transport_errors, semantic_failed=semantic_failed, accepted=accepted)
    for row in questions.values():
        if row.get("terminal_reason") == "refined_to_child":
            row["active"] = False
    summary = _persist_story(root, run_dir, material, protocol, status=status, questions=questions, events=events, search_trace=search_trace, round_metrics=round_metrics, usage_rows=usage_rows, normalizations=normalizations, rejected_gaps=rejected_gaps, rejected_claims=rejected_claims, rejected_evidence=rejected_evidence, protocol_errors=protocol_errors, transport_errors=transport_errors, semantic_failed=semantic_failed, seen_refs=seen_refs, accepted=accepted, retrieval_attempts=retrieval_attempts, registry=registry, execution_kind="fixture" if fixture else "live_model")
    return summary


def _preflight(transport: DeepSeekTransport) -> dict[str, Any]:
    started = time.monotonic()
    result = transport.call(story_id="__preflight__", round_number=-1, completion_kind="preflight", messages=[{"role": "user", "content": 'Return JSON: {"status":"connected"}'}], max_retries=0)
    attempts = result.get("attempts", []) if isinstance(result.get("attempts"), list) else []
    final = attempts[-1] if attempts and isinstance(attempts[-1], Mapping) else {}
    report = {
        "schema": "srm0-5-preflight",
        "endpoint": API_URL,
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "start_time": final.get("start_time"),
        "end_time": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "success": bool(result.get("success")),
        "classification": "reachable" if result.get("success") else result.get("failure_class"),
        "http_status": final.get("http_status"),
        "exception_class": final.get("exception_class"),
        "exception_message": final.get("exception_message"),
        "response_model": (result.get("response") or {}).get("model") if isinstance(result.get("response"), Mapping) else None,
        "api_usage": _usage(result.get("response") if isinstance(result.get("response"), Mapping) else None),
        "attempts": [dict(row) for row in attempts if isinstance(row, Mapping)],
    }
    _write(PREFLIGHT_PATH, report)
    return report


def _transport_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    attempts = [attempt for row in rows for attempt in (row.get("transport_metrics") or {}).get("successful_latencies_seconds", [])]
    classes = Counter()
    for row in rows:
        classes.update((row.get("transport_metrics") or {}).get("failure_classes", {}))
    request_count = sum(int((row.get("transport_metrics") or {}).get("transport_request_count", 0)) for row in rows)
    retry_count = sum(int((row.get("transport_metrics") or {}).get("transport_retry_count", 0)) for row in rows)
    return {
        "transport_request_count": request_count,
        "transport_retry_count": retry_count,
        "transport_success_count": sum(int((row.get("transport_metrics") or {}).get("transport_success_count", 0)) for row in rows),
        "tls_failure_count": classes["tls_failure"],
        "read_timeout_count": classes["read_timeout"],
        "connect_timeout_count": classes["connect_timeout"],
        "server_error_count": classes["server_error"],
        "failure_classes": dict(sorted(classes.items())),
        "successful_latencies_seconds": attempts,
        "median_successful_latency_seconds": statistics.median(attempts) if attempts else None,
        "max_successful_latency_seconds": max(attempts) if attempts else None,
    }


def _batch_summary(selection: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], protocol: Mapping[str, Any]) -> dict[str, Any]:
    values = [dict(row) for row in rows]
    # Recompute these reporting projections from the persisted controller
    # attempts so offline replay cannot confuse "retrieved but unused" with
    # "no retrieval was needed".
    for value in values:
        attempts = value.get("retrieval_attempts")
        if isinstance(attempts, Mapping):
            value["external_retrieval_required_count"] = _retrieval_need_count(attempts)
            questions = {
                str(q.get("question_id")): q
                for q in value.get("questions", [])
                if isinstance(q, Mapping) and q.get("question_id")
            }
            value["commentary_only_resolution_count"] = _commentary_only_count(questions, attempts)
    qmetrics = [row.get("question_metrics", {}) for row in values]
    def total(key: str) -> int:
        return sum(int(metric.get(key, 0) or 0) for metric in qmetrics)
    evaluable = total("evaluable_question_count")
    converged = total("converged_question_count")
    terminal = Counter(str(reason) for row in values for reason in (row.get("terminal_reason_per_question") or {}).values() if reason in TERMINAL_STATES)
    source_counts = Counter()
    for row in values:
        question_rows = {
            str(q.get("question_id")): q
            for q in row.get("questions", [])
            if isinstance(q, Mapping) and q.get("question_id")
        }
        for qid, sources in (row.get("question_resolution_sources") or {}).items():
            # Refined parent nodes are controller bookkeeping, not
            # evaluable questions in the frozen SRM0.4 convention.
            if question_rows.get(str(qid), {}).get("terminal_reason") == "refined_to_child":
                continue
            if isinstance(sources, list):
                source_counts.update(sources)
    commentary_only = sum(int(row.get("commentary_only_resolution_count", 0) or 0) for row in values)
    external = sum(int(row.get("external_retrieval_required_count", 0) or 0) for row in values)
    latencies = [float(value) for row in values for value in (row.get("latency_seconds") or {}).get("successful", [])]
    tokens = {key: sum(int((row.get("token_usage") or {}).get(key) or 0) for row in values) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    by_stratum: dict[str, dict[str, Any]] = {}
    for stratum in STRATA:
        subset = [row for row in values if row.get("stratum") == stratum]
        subq = [row.get("question_metrics", {}) for row in subset]
        subeval = sum(int(metric.get("evaluable_question_count", 0)) for metric in subq)
        subconverged = sum(int(metric.get("converged_question_count", 0)) for metric in subq)
        by_stratum[stratum] = {
            "story_count": len(subset),
            "evaluable_questions": subeval,
            "convergence_rate": subconverged / subeval if subeval else None,
            "reading_sufficient_rate": sum(int(metric.get("reading_sufficient_question_count", 0)) for metric in subq) / subeval if subeval else None,
            "external_evidence_need_rate": sum(int(row.get("external_retrieval_required_count", 0) or 0) for row in subset) / subeval if subeval else None,
            "mean_evidence_rounds": statistics.mean([len(row.get("evidence_rounds", [])) for row in subset]) if subset else None,
            "tokens_per_converged_question": sum(int((row.get("token_usage") or {}).get("total_tokens") or 0) for row in subset) / subconverged if subconverged else None,
        }
    return {
        "schema": "srm0-5-summary",
        "schema_version": SCHEMA_VERSION,
        "stage": STAGE,
        "execution_kind": "live_model",
        "selected_story_ids": list(selection.get("selected_story_ids", [])),
        "stories": values,
        "aggregate": {
            "story_count": len(values),
            "evaluable_question_count": evaluable,
            "converged_question_count": converged,
            "question_convergence_rate": converged / evaluable if evaluable else None,
            "reading_sufficient_rate": terminal["reading_sufficient"] / evaluable if evaluable else None,
            "evidence_saturated_rate": terminal["evidence_saturated"] / evaluable if evaluable else None,
            "stable_conflict_rate": terminal["stable_conflict"] / evaluable if evaluable else None,
            "unresolved_terminal_rate": (terminal["unresolved_no_evidence"] + terminal["not_worth_pursuing"]) / evaluable if evaluable else None,
            "active_unresolved_rate": total("unresolved_question_count") / evaluable if evaluable else None,
            "protocol_failure_rate": sum(bool(row.get("protocol_errors")) for row in values) / len(values) if values else None,
            "semantic_failure_rate": sum(bool(row.get("semantic_failed_questions")) for row in values) / len(values) if values else None,
            "transport_failure_rate": sum(bool(row.get("transport_errors")) for row in values) / len(values) if values else None,
            "valid_question_count": total("valid_question_count"),
            "terminal_state_distribution": dict(sorted(terminal.items())),
            "commentary_only_resolution_count": commentary_only,
            "external_retrieval_required_count": external,
            "external_evidence_need_rate": external / evaluable if evaluable else None,
            "resolution_source_counts": dict(sorted(source_counts.items())),
            "prompt_tokens": tokens["prompt_tokens"],
            "completion_tokens": tokens["completion_tokens"],
            "total_api_tokens": tokens["total_tokens"],
            "tokens_per_story": tokens["total_tokens"] / len(values) if values else None,
            "tokens_per_evaluable_question": tokens["total_tokens"] / evaluable if evaluable else None,
            "tokens_per_converged_question": tokens["total_tokens"] / converged if converged else None,
            "mean_evidence_rounds": statistics.mean([len(row.get("evidence_rounds", [])) for row in values]) if values else None,
            "median_evidence_rounds": statistics.median([len(row.get("evidence_rounds", [])) for row in values]) if values else None,
            "max_evidence_rounds": max([len(row.get("evidence_rounds", [])) for row in values], default=0),
            "mean_successful_api_latency": statistics.mean(latencies) if latencies else None,
            "median_successful_api_latency": statistics.median(latencies) if latencies else None,
            "max_successful_api_latency": max(latencies) if latencies else None,
            "transport_metrics": _transport_metrics(values),
            "by_stratum": by_stratum,
            "no_opaque_convergence_score": True,
        },
        "protocol_hash": _hash_value(protocol),
        "canonical_write_back": False,
        "external_search_performed": False,
    }


def _metrics_document(summary: Mapping[str, Any]) -> dict[str, Any]:
    stories = summary.get("stories", []) if isinstance(summary.get("stories"), list) else []
    trajectories = []
    for story in stories:
        for row in story.get("evidence_rounds", []) if isinstance(story, Mapping) else []:
            trajectories.append({"story_id": story.get("story_id"), "stratum": story.get("stratum"), "round": row.get("round"), "G_t": row.get("G_t"), "D_t": row.get("D_t"), "N_t": row.get("N_t"), "Q_t": row.get("Q_t")})
    return {
        "schema": "srm0-5-metrics",
        "schema_version": SCHEMA_VERSION,
        "question_convergence": summary.get("aggregate", {}),
        "round_trajectories": trajectories,
        "terminal_states": summary.get("aggregate", {}).get("terminal_state_distribution", {}),
        "projection_notes": [
            "Post-live deterministic replay excludes refined_to_child parent nodes from the evaluable-question denominator, matching the SRM0.4D question-level convention; raw live responses and semantic logic were not changed."
        ],
        "canonical_write_back": False,
    }


def _failure_root_cause(root: Path, story: Mapping[str, Any], question_id: str | None, failure_type: str) -> str:
    if failure_type == "protocol_failed":
        return "malformed_model_output"
    if failure_type != "semantic_failed":
        return "other"
    run_dir = root / OUTPUT_ROOT / "live" / str(story.get("story_id")) / str(story.get("run_id"))
    for output_path in sorted(run_dir.glob("round-*-output.json")):
        output = _read(output_path)
        normalized = output.get("normalized_output") if isinstance(output, Mapping) else None
        updates = normalized.get("updates", []) if isinstance(normalized, Mapping) else []
        if question_id and any(isinstance(update, Mapping) and update.get("question_id") == question_id for update in updates):
            continue
        if output.get("rejected_evidence"):
            return "evidence_quote_rejection"
        if output.get("rejected_claims") or output.get("rejected_aspects"):
            return "unsupported_claim"
    return "evidence_consumption_failure"


def _failure_review(summary: Mapping[str, Any], root: Path = ROOT) -> dict[str, Any]:
    records = []
    for story in summary.get("stories", []) if isinstance(summary.get("stories"), list) else []:
        question_rows = sorted((story.get("terminal_reason_per_question") or {}).items())
        for question_id, reason in question_rows:
            failure_type = None
            if reason in {"semantic_failed", "protocol_failed", "transport_failed"}:
                failure_type = reason
            if failure_type or story.get("protocol_errors") or story.get("transport_errors"):
                records.append({
                    "story_id": story.get("story_id"),
                    "question_id": question_id,
                    "round": None,
                    "current_failure_type": failure_type or ("transport_failed" if story.get("transport_errors") else "protocol_failed"),
                    "root_cause": _failure_root_cause(root, story, str(question_id) if question_id is not None else None, str(failure_type or "")),
                    "model_output_present": bool(story.get("rounds_executed")),
                    "valid_evidence_present": bool(story.get("used_evidence")),
                    "semantic_delta_present": bool(story.get("round_metrics")),
                    "current_state": reason,
                    "expected_state": reason,
                    "repair_action": "review_only",
                    "rerun_required": False,
                })
        if not question_rows and (story.get("protocol_errors") or story.get("semantic_failed_questions") or story.get("transport_errors")):
            failure_type = "transport_failed" if story.get("transport_errors") else "protocol_failed" if story.get("protocol_errors") else "semantic_failed"
            records.append({
                "story_id": story.get("story_id"),
                "question_id": None,
                "round": None,
                "current_failure_type": failure_type,
                "root_cause": _failure_root_cause(root, story, None, failure_type),
                "model_output_present": bool(story.get("rounds_executed")),
                "valid_evidence_present": bool(story.get("used_evidence")),
                "semantic_delta_present": bool(story.get("round_metrics")),
                "current_state": story.get("story_status"),
                "expected_state": story.get("story_status"),
                "repair_action": "review_only",
                "rerun_required": False,
            })
    return {"schema": "srm0-5-failure-review", "schema_version": SCHEMA_VERSION, "stage": "post_batch_review_only", "records": records, "canonical_write_back": False}


def _human_review(summary: Mapping[str, Any], root: Path = ROOT) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    categories = ("reading_sufficient", "evidence_saturated", "unresolved")
    for category in categories:
        rows = []
        for story in summary.get("stories", []) if isinstance(summary.get("stories"), list) else []:
            for qid, terminal in sorted((story.get("terminal_reason_per_question") or {}).items()):
                is_active_unresolved = category == "unresolved" and terminal is None and any(q.get("question_id") == qid and q.get("active") for q in story.get("questions", []))
                if (category == "reading_sufficient" and terminal == "reading_sufficient") or (category == "evidence_saturated" and terminal == "evidence_saturated") or (category == "unresolved" and terminal in {"stable_conflict", "unresolved_no_evidence"}) or is_active_unresolved:
                    question = next((q for q in story.get("questions", []) if q.get("question_id") == qid), {})
                    rows.append({"story_id": story.get("story_id"), "story_text": story.get("story_text") or story_material(root, str(story.get("story_id"))).get("main_text", ""), "question_id": qid, "category": category, "original_gap": question.get("gap"), "evidence_used": question.get("supporting_refs", []), "working_answer": question.get("working_answer", ""), "terminal_state": terminal, "stop_reason": terminal})
        candidates.extend(rows[: 3 if category == "reading_sufficient" else 2 if category == "evidence_saturated" else 2])
    for story in summary.get("stories", []) if isinstance(summary.get("stories"), list) else []:
        if story.get("protocol_errors") or story.get("semantic_failed_questions"):
            failed_ids = story.get("semantic_failed_questions") or [None]
            for failed_id in failed_ids:
                question = next((q for q in story.get("questions", []) if q.get("question_id") == failed_id), {})
                candidates.append({"story_id": story.get("story_id"), "story_text": story.get("story_text") or story_material(root, str(story.get("story_id"))).get("main_text", ""), "question_id": failed_id, "category": "failure", "original_gap": question.get("gap"), "evidence_used": question.get("supporting_refs", []), "working_answer": question.get("working_answer", ""), "terminal_state": "semantic_failed" if story.get("semantic_failed_questions") else "protocol_failed", "stop_reason": "failure_review"})
    return {"schema": "srm0-5-human-review", "schema_version": SCHEMA_VERSION, "stage": "manual_review_template", "sample": candidates, "canonical_write_back": False}


def build_postrun_artifacts(root: Path = ROOT) -> None:
    summary = _read(root / SUMMARY_PATH)
    if not summary:
        return
    _write(root / METRICS_PATH, _metrics_document(summary))
    _write(root / FAILURE_REVIEW_PATH, _failure_review(summary, root))
    _write(root / HUMAN_REVIEW_PATH, _human_review(summary, root))


def run_batch(root: Path = ROOT, *, fixture: bool = False, story_ids: Sequence[str] | None = None) -> int:
    selection = ensure_selection(root, write=True)
    protocol = protocol_freeze_document(root, selection)
    freeze_path = root / OUTPUT_ROOT / "protocol-freeze.json"
    if freeze_path.is_file():
        existing_protocol = _read(freeze_path)
        if existing_protocol != protocol:
            raise RuntimeError("SRM0.5 protocol freeze differs; stop before live evaluation")
    else:
        _write(freeze_path, protocol)
    selected = list(story_ids or selection.get("selected_story_ids", []))
    if set(selected) - set(selection.get("selected_story_ids", [])):
        raise SystemExit("story is not in frozen SRM0.5 selection")
    if fixture:
        rows = []
        shared_registry = build_registry(root)
        for story_id in selected:
            row = run_story(root, story_id, protocol, transport=None, fixture=True, registry=shared_registry)
            row["stratum"] = next((item.get("stratum") for item in selection.get("selected", []) if item.get("story_id") == story_id), None)
            rows.append(row)
        fixture_summary = _batch_summary(selection, rows, protocol)
        fixture_summary["execution_kind"] = "fixture"
        fixture_summary["fixture_only"] = True
        _write(root / OUTPUT_ROOT / "fixture-summary.json", fixture_summary)
        return 0
    transport = DeepSeekTransport()
    preflight = _preflight(transport)
    if preflight.get("classification") != "reachable":
        print("live_network_unavailable")
        print(f"preflight_classification: {preflight.get('classification')}")
        print("rerun the same command with approved network access")
        return 2
    shared_registry = build_registry(root)
    rows = []
    for story_id in selected:
        row = run_story(root, story_id, protocol, transport=transport, fixture=False, registry=shared_registry)
        row["stratum"] = next((item.get("stratum") for item in selection.get("selected", []) if item.get("story_id") == story_id), None)
        rows.append(row)
        print(f"{story_id}: status={row.get('story_status')} questions={row.get('question_metrics', {}).get('evaluable_question_count')} rounds={len(row.get('evidence_rounds', []))}", flush=True)
    summary = _batch_summary(selection, rows, protocol)
    _write(root / SUMMARY_PATH, summary)
    build_postrun_artifacts(root)
    print(f"summary: {SUMMARY_PATH.as_posix()}")
    return 1 if any(row.get("protocol_errors") or row.get("transport_errors") or row.get("semantic_failed_questions") for row in rows) else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--select", action="store_true", help="write the deterministic 5/5/5 selection")
    parser.add_argument("--batch", action="store_true", help="run the selected Stories live")
    parser.add_argument("--fixture", action="store_true", help="run isolated plumbing fixtures; never counted as live findings")
    parser.add_argument("--story", action="append", help="run one or more selected Stories")
    parser.add_argument("--replay-existing", action="store_true", help="rebuild derived review projections without API calls")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.select:
        selection = ensure_selection(ROOT, write=True)
        _write(ROOT / OUTPUT_ROOT / "protocol-freeze.json", protocol_freeze_document(ROOT, selection))
        print(stable_json({"selected": selection.get("selected_story_ids"), "counts": selection.get("candidate_counts_after_exclusion")}))
        return 0
    if args.fixture:
        return run_batch(ROOT, fixture=True, story_ids=args.story)
    if args.replay_existing:
        summary_path = ROOT / SUMMARY_PATH
        summary = _read(summary_path)
        if summary.get("execution_kind") == "live_model" and isinstance(summary.get("stories"), list):
            selection = ensure_selection(ROOT, write=False)
            protocol = protocol_freeze_document(ROOT, selection)
            rows = []
            for row in summary["stories"]:
                value = dict(row)
                questions = {str(q.get("question_id")): q for q in value.get("questions", []) if isinstance(q, Mapping) and q.get("question_id")}
                value["question_metrics"] = _question_metrics(questions)
                registry = build_registry(ROOT)
                value["question_resolution_sources"] = {
                    qid: _question_resolution_source(question, registry)
                    for qid, question in questions.items()
                }
                value["resolution_sources"] = sorted({
                    source
                    for sources in value["question_resolution_sources"].values()
                    for source in sources
                })
                rows.append(value)
            rebuilt = _batch_summary(selection, rows, protocol)
            _write(summary_path, rebuilt)
        build_postrun_artifacts(ROOT)
        print("SRM0.5 replay completed without API calls")
        return 0
    if args.batch or args.story:
        return run_batch(ROOT, fixture=False, story_ids=args.story)
    raise SystemExit("use --select, --fixture, --batch, or --story")


if __name__ == "__main__":
    raise SystemExit(main())
