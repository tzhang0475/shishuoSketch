#!/usr/bin/env python3
"""Run the bounded SRM0.4A multi-Story convergence pilot.

The runner keeps model outputs in an experimental generated tree.  It only
reads registered local source projections and never writes canonical or Gold
artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ds1_common import ROOT, sha256_file, stable_json, write_json  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402
from srm0_1_common import parse_json_content  # noqa: E402
from srm0_4a_common import (  # noqa: E402
    BATCH_SUMMARY_PATH,
    MAX_EVIDENCE_ROUNDS,
    MODEL,
    PROMPT_VERSION,
    PROVIDER,
    SCHEMA_VERSION,
    SELECTION_PATH,
    apply_gap_gates,
    boundary_normalization_count,
    build_commentary_messages,
    build_initial_messages,
    build_retrieval_messages,
    build_retrieval_registry,
    derive_question_state,
    evidence_novelty,
    make_refined_questions,
    normalize_delta,
    normalize_initial,
    open_candidates,
    review_template,
    saturation,
    search_registry,
    selection,
    semantic_delta_changed,
    story_material,
    validate_delta,
    validate_initial,
)


REVIEW_PATH = Path("data/annotation/srm0-4a-review.json")
OUTPUT_BASE = Path("data/generated/srm0")
SEARCHED_CORPORA = [
    "世說新語",
    "余嘉錫箋疏",
    "晉書",
    "三國志",
    "資治通鑑",
    "資治通鑑考異",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--batch", action="store_true", help="run all six selected Stories (the default)")
    group.add_argument("--story", help="run one Story only; it must be in the deterministic selection")
    parser.add_argument("--fixture", action="store_true", help="use deterministic local fixtures; never calls DeepSeek")
    parser.add_argument("--replay-existing", action="store_true", help="reuse saved raw model outputs without API calls")
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


def _json_file(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _fixture_initial(material: Mapping[str, Any]) -> dict[str, Any]:
    text = str(material.get("main_text", ""))
    span = text[: min(18, len(text))]
    return {
        "gaps": [
            {
                "question_id": "Q1",
                "story_span": span,
                "gap": "这段行动或处境为何会改变读者对本故事的理解？",
            }
        ] if span else []
    }


def _fixture_delta(material: Mapping[str, Any], questions: Sequence[Mapping[str, Any]], *, retrieval: bool, candidates: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    updates: list[dict[str, Any]] = []
    later = list(material.get("jianshu_notes", []))
    early = list(material.get("liu_notes", []))
    fallback = (later + early)[-1:] if (later or early) else []
    by_question = {}
    for candidate in candidates:
        if isinstance(candidate, Mapping) and candidate.get("ref"):
            by_question.setdefault(str(candidate.get("ref")), candidate)
    for question in questions:
        row: dict[str, Any] = {
            "question_id": question["question_id"],
            "answered_aspects": [],
            "unanswered_aspects": [],
            "conflicts": [],
            "reading_sufficient": False,
            "historical_verification_open": False,
        }
        evidence_row = next(iter(by_question.values()), None) if retrieval else (fallback[0] if fallback else None)
        if evidence_row:
            quote = str(evidence_row.get("snippet") or evidence_row.get("text") or "")[:80]
            row["answered_aspects"] = [{
                "aspect_id": f"{question['question_id']}-A1",
                "claim": "本轮材料提供了与该阅读缺口直接相关的考证线索。",
                "evidence": [{"ref": evidence_row["ref"], "quote": quote}],
            }]
            row["reading_sufficient"] = not retrieval or bool(evidence_row)
            row["historical_verification_open"] = bool(retrieval)
        if not row["reading_sufficient"]:
            row["unanswered_aspects"] = [{
                "aspect_id": f"{question['question_id']}-U1",
                "gap": "仍缺少能直接改变该段阅读的具体历史材料。",
                "reading_impact": "high",
            }]
        updates.append(row)
    return {"updates": updates}


def _load_saved_raw(path: Path) -> tuple[dict[str, Any], dict[str, Any] | None, str, str]:
    document = _json_file(path)
    content = str(document.get("raw_content") or "")
    if not content:
        raise ValueError(f"saved model output has no raw_content: {path}")
    raw, repair = parse_json_content(content)
    response = document.get("raw_response")
    return raw, dict(response) if isinstance(response, Mapping) else None, content, repair


def _call_stage(
    *,
    stage: str,
    round_number: int,
    messages: Sequence[Mapping[str, Any]],
    output_dir: Path,
    execution_kind: str,
    fixture_value: Mapping[str, Any] | None,
    replay_document: Mapping[str, Any] | None,
    timeout: int,
) -> tuple[dict[str, Any], dict[str, Any] | None, str, str, int]:
    input_name = f"round-{round_number:02d}-input.json"
    output_name = f"round-{round_number:02d}-output.json"
    input_artifact = {
        "schema": "srm0-4a-model-input",
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
    write_json(ROOT, output_dir / input_name, input_artifact)
    response: dict[str, Any] | None = None
    content = ""
    repair = "none"
    api_calls = 0
    try:
        if fixture_value is not None:
            raw = dict(fixture_value)
            content = stable_json(raw)
            repair = "fixture"
        elif execution_kind == "replay":
            if replay_document is None:
                raise ValueError(f"saved model output is missing: {output_dir / output_name}")
            content = str(replay_document.get("raw_content") or "")
            if not content:
                raise ValueError(f"saved model output has no raw_content: {output_dir / output_name}")
            raw, repair = parse_json_content(content)
            saved_response = replay_document.get("raw_response")
            response = dict(saved_response) if isinstance(saved_response, Mapping) else None
        else:
            response = call_deepseek(
                messages,
                model=MODEL,
                temperature=0,
                response_format={"type": "json_object"},
                tools=[],
                timeout=timeout,
            )
            api_calls = 1
            content = response_content(response)
            raw, repair = parse_json_content(content)
    except Exception as error:  # noqa: BLE001 - persist a fail-closed artifact
        raw = {}
        if not content:
            try:
                choices = response.get("choices", []) if isinstance(response, Mapping) else []
                message = choices[0].get("message", {}) if choices and isinstance(choices[0], Mapping) else {}
                content = str(message.get("content") or "") if isinstance(message, Mapping) else ""
            except (IndexError, TypeError, AttributeError):
                content = ""
        repair = "error"
        if response is None:
            response = {"error": str(error)}
        else:
            response = {**dict(response), "client_error": str(error)}

    output_artifact = {
        "schema": "srm0-4a-model-output",
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "round": round_number,
        "execution_kind": execution_kind,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "raw_response": dict(response or {}),
        "raw_content": content,
        "raw_output": dict(raw),
        "json_repair": repair,
        "json_repair_count": int(repair not in {"none", "fixture"}),
        "api_usage": usage_fields(response),
        "canonical_write_back": False,
        "external_search_performed": False,
    }
    write_json(ROOT, output_dir / output_name, output_artifact)
    return raw, response, content, repair, api_calls


def _event(path: Path, events: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in events),
        encoding="utf-8",
    )


def _reset_convergence_artifacts(output_dir: Path) -> None:
    """Remove only stale artifacts from this SRM0.4A generated run."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in output_dir.glob("round-*.json"):
        path.unlink()
    for name in ("research-state.json", "events.jsonl", "search-trace.jsonl", "convergence.json", "usage.json", "manifest.json"):
        path = output_dir / name
        if path.is_file():
            path.unlink()


def _question_update_record(question: Mapping[str, Any], update: Mapping[str, Any], round_number: int, prior: Mapping[str, Any] | None) -> dict[str, Any]:
    record = derive_question_state(question, update, prior)
    record["last_round"] = round_number
    record["evidence_rounds"] = int(question.get("evidence_rounds", 0)) + 1
    return record


def _compact_state_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: record.get(key)
        for key in (
            "question_id", "parent_question_id", "parent_aspect_id", "story_span", "gap", "state",
            "working_answer", "supporting_refs", "remaining_gap", "reading_sufficient",
            "historical_verification_open", "next_action", "terminal_reason", "active", "last_round",
            "evidence_rounds", "conflict_ids",
        )
    }


def _state_artifact(story_id: str, status: str, questions: Mapping[str, Mapping[str, Any]], seen_refs: set[str], round_metrics: Sequence[Mapping[str, Any]], validation_errors: Sequence[str] = ()) -> dict[str, Any]:
    rows = [_compact_state_record(questions[key]) for key in sorted(questions)]
    active = [row["question_id"] for row in rows if row.get("active")]
    terminal = [row["question_id"] for row in rows if row.get("terminal_reason") in {"reading_sufficient", "evidence_saturated", "stable_conflict", "unresolved_no_evidence", "not_worth_pursuing", "hard_cap"}]
    return {
        "schema": "srm0-4a-research-state",
        "schema_version": SCHEMA_VERSION,
        "story_id": story_id,
        "stage": "convergence_complete" if status == "converged" else status,
        "story_status": status,
        "questions": rows,
        "active_questions": sorted(active),
        "terminal_questions": sorted(terminal),
        "seen_evidence_refs": sorted(seen_refs),
        "round_metrics": [dict(row) for row in round_metrics],
        "validation_errors": sorted(set(validation_errors)),
        "canonical_write_back": False,
        "external_search_performed": False,
    }


def _apply_update(
    *,
    question: Mapping[str, Any],
    update: Mapping[str, Any],
    round_number: int,
    questions: dict[str, dict[str, Any]],
    histories: dict[str, list[dict[str, Any]]],
    seen_refs: set[str],
    used_refs: Sequence[str],
    retrieval_attempts: dict[str, int],
    evidence_found: dict[str, int],
    events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, float, list[str]]:
    qid = str(question["question_id"])
    prior = questions.get(qid)
    current = _question_update_record(question, update, round_number, prior)
    novelty, new_refs = evidence_novelty(used_refs, seen_refs)
    changed = semantic_delta_changed(prior, current)
    histories.setdefault(qid, []).append({"D_t": changed, "N_t": novelty, "round": round_number, "conflict_ids": current.get("conflict_ids", [])})
    seen_refs.update(str(ref) for ref in used_refs)
    current["active"] = False
    current["terminal_reason"] = None
    questions[qid] = current
    if update.get("reading_sufficient") is True:
        current["terminal_reason"] = "reading_sufficient"
        events.append({"event": "reading_converged", "round": round_number, "question_id": qid})
    elif saturation(histories[qid]):
        current["terminal_reason"] = "evidence_saturated"
        events.append({"event": "evidence_saturated", "round": round_number, "question_id": qid})
    else:
        conflict_history = histories[qid]
        if len(conflict_history) >= 2 and conflict_history[-1]["conflict_ids"] and conflict_history[-1]["conflict_ids"] == conflict_history[-2]["conflict_ids"]:
            current["terminal_reason"] = "stable_conflict"
            events.append({"event": "stable_conflict", "round": round_number, "question_id": qid})
        elif retrieval_attempts.get(qid, 0) >= 2 and evidence_found.get(qid, 0) == 0:
            current["terminal_reason"] = "unresolved_no_evidence"
            events.append({"event": "unresolved_no_evidence", "round": round_number, "question_id": qid})
        elif round_number >= MAX_EVIDENCE_ROUNDS:
            current["terminal_reason"] = "hard_cap"
            events.append({"event": "hard_cap", "round": round_number, "question_id": qid})
        else:
            children = make_refined_questions(question, update)
            if children:
                current["terminal_reason"] = "refined_to_child"
                for child in children:
                    child_record = dict(child)
                    child_record.update({
                        "state": "unexplained",
                        "working_answer": "",
                        "supporting_refs": [],
                        "remaining_gap": child["gap"],
                        "reading_sufficient": False,
                        "historical_verification_open": False,
                        "next_action": "retrieve_local",
                        "terminal_reason": None,
                        "active": True,
                        "last_round": round_number,
                        "evidence_rounds": 0,
                        "conflict_ids": [],
                    })
                    questions[child["question_id"]] = child_record
                    events.append({
                        "event": "refined_question_created",
                        "round": round_number,
                        "question_id": child["question_id"],
                        "parent_question_id": child["parent_question_id"],
                        "parent_aspect_id": child["parent_aspect_id"],
                    })
            else:
                current["terminal_reason"] = "not_worth_pursuing"
                events.append({"event": "not_worth_pursuing", "round": round_number, "question_id": qid})
    questions[qid] = current
    events.append({"event": "semantic_delta_recorded", "round": round_number, "question_id": qid, "changed": changed, "new_evidence_refs": new_refs})
    return make_refined_questions(question, update), changed, novelty, new_refs


def _run_story(material: Mapping[str, Any], selection_row: Mapping[str, Any], args: argparse.Namespace, registry: Mapping[str, Mapping[str, Any]] | None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    story_id = str(material["story_id"])
    output_dir = OUTPUT_BASE / story_id / "convergence"
    saved_outputs = {
        path.name: _json_file(ROOT / path)
        for path in (ROOT / output_dir).glob("round-*-output.json")
    } if args.replay_existing else {}
    _reset_convergence_artifacts(ROOT / output_dir)
    source_fingerprint = stable_json({"story_id": story_id, "source_sha256": material.get("source_sha256"), "source_artifacts": material.get("source_artifacts")})
    run_id = "srm0-4a-" + __import__("hashlib").sha256(source_fingerprint.encode("utf-8")).hexdigest()[:16]
    execution_kind = "fixture" if args.fixture else "replay" if args.replay_existing else "real_model"
    questions: dict[str, dict[str, Any]] = {}
    histories: dict[str, list[dict[str, Any]]] = {}
    seen_refs: set[str] = set()
    retrieval_attempts: dict[str, int] = {}
    evidence_found: dict[str, int] = {}
    round_metrics: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    search_trace: list[dict[str, Any]] = []
    usage_rows: list[dict[str, Any]] = []
    validation_errors: list[str] = []
    actual_api_calls = 0
    total_json_repairs = 0
    boundary_normalizations = 0

    initial_messages = build_initial_messages(material)
    initial_fixture = _fixture_initial(material) if args.fixture else None
    initial_raw, initial_response, initial_content, initial_repair, api_calls = _call_stage(
        stage="main_text_gap_discovery", round_number=0, messages=initial_messages, output_dir=output_dir,
        execution_kind=execution_kind, fixture_value=initial_fixture,
        replay_document=saved_outputs.get("round-00-output.json"), timeout=args.timeout,
    )
    actual_api_calls += api_calls
    total_json_repairs += int(initial_repair not in {"none", "fixture"})
    initial_normalized = normalize_initial(initial_raw, material)
    initial_errors = validate_initial(initial_raw, initial_normalized, material)
    validation_errors.extend(initial_errors)
    usage_rows.append({"round": 0, "stage": "main_text_gap_discovery", "api_usage": usage_fields(initial_response), "json_repair": initial_repair})
    accepted_gaps, gate_audit = apply_gap_gates(initial_normalized.get("gaps", []), material)
    frozen_questions: list[dict[str, Any]] = []
    for row in accepted_gaps:
        frozen = dict(row)
        frozen.update({"parent_question_id": None, "parent_aspect_id": None, "evidence_rounds": 0, "last_round": 0, "active": True})
        frozen_questions.append(frozen)
        questions[str(frozen["question_id"])] = {
            **frozen,
            "state": "unexplained",
            "working_answer": "",
            "supporting_refs": [],
            "remaining_gap": frozen["gap"],
            "reading_sufficient": False,
            "historical_verification_open": False,
            "next_action": "commentary",
            "terminal_reason": None,
            "conflict_ids": [],
        }
        events.append({"event": "question_created", "round": 0, "question_id": frozen["question_id"], "story_span": frozen["story_span"]})
    write_json(ROOT, output_dir / "round-00-output.json", {
        "schema": "srm0-4a-gap-output",
        "schema_version": SCHEMA_VERSION,
        "story_id": story_id,
        "run_id": run_id,
        "execution_kind": execution_kind,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "raw_response": dict(initial_response or {}),
        "raw_content": initial_content,
        "raw_output": initial_raw,
        "normalized_output": initial_normalized,
        "gate_audit": gate_audit,
        "frozen_questions": frozen_questions,
        "validation_errors": sorted(set(initial_errors)),
        "json_repair": initial_repair,
        "json_repair_count": int(initial_repair not in {"none", "fixture"}),
        "api_usage": usage_fields(initial_response),
        "canonical_write_back": False,
        "external_search_performed": False,
    })

    if not initial_errors and frozen_questions:
        commentary_messages = build_commentary_messages(material, frozen_questions)
        commentary_fixture = _fixture_delta(material, frozen_questions, retrieval=False) if args.fixture else None
        commentary_raw, commentary_response, commentary_content, commentary_repair, api_calls = _call_stage(
            stage="attached_commentary_delta", round_number=1, messages=commentary_messages, output_dir=output_dir,
            execution_kind=execution_kind, fixture_value=commentary_fixture,
            replay_document=saved_outputs.get("round-01-output.json"), timeout=args.timeout,
        )
        actual_api_calls += api_calls
        total_json_repairs += int(commentary_repair not in {"none", "fixture"})
        attached_sources = {str(row["ref"]): str(row.get("text", "")) for row in list(material.get("liu_notes", [])) + list(material.get("jianshu_notes", []))}
        commentary_normalized, commentary_normalizations = normalize_delta(commentary_raw, attached_sources)
        commentary_errors = validate_delta(commentary_raw, commentary_normalized, attached_sources, {str(row["question_id"]) for row in frozen_questions})
        validation_errors.extend(commentary_errors)
        boundary_normalizations += boundary_normalization_count(commentary_normalizations)
        usage_rows.append({"round": 1, "stage": "attached_commentary_delta", "api_usage": usage_fields(commentary_response), "json_repair": commentary_repair})
        write_json(ROOT, output_dir / "round-01-output.json", {
            "schema": "srm0-4a-delta-output",
            "schema_version": SCHEMA_VERSION,
            "story_id": story_id,
            "run_id": run_id,
            "execution_kind": execution_kind,
            "model": MODEL,
            "provider": PROVIDER,
            "prompt_version": PROMPT_VERSION,
            "raw_response": dict(commentary_response or {}),
            "raw_content": commentary_content,
            "raw_output": commentary_raw,
            "normalized_output": commentary_normalized,
            "boundary_normalizations": commentary_normalizations,
            "validation_errors": sorted(set(commentary_errors)),
            "json_repair": commentary_repair,
            "json_repair_count": int(commentary_repair not in {"none", "fixture"}),
            "api_usage": usage_fields(commentary_response),
            "canonical_write_back": False,
            "external_search_performed": False,
        })
        if not commentary_errors:
            for update in commentary_normalized["updates"]:
                question = dict(questions[str(update["question_id"])])
                _apply_update(
                    question=question, update=update, round_number=1, questions=questions, histories=histories,
                    seen_refs=seen_refs,
                    used_refs=[str(item.get("ref")) for aspect in update.get("answered_aspects", []) if isinstance(aspect, Mapping) for item in aspect.get("evidence", []) if isinstance(item, Mapping)],
                    retrieval_attempts=retrieval_attempts, evidence_found=evidence_found, events=events,
                )
            used = sorted(seen_refs)
            history_rows = [metric for metrics in histories.values() for metric in metrics]
            round_metrics.append({"round": 1, "G_t": len(frozen_questions), "D_t": int(any(metric.get("D_t") for metric in history_rows)), "N_t": 1.0 if used else 0.0, "used_evidence_refs": used, "new_used_evidence_refs": used, "retrieval": False})
        else:
            validation_errors.extend(commentary_errors)

    current_round = 2
    if registry is None and any(row.get("active") for row in questions.values()) and not validation_errors:
        registry = build_retrieval_registry(ROOT)
    while not validation_errors and any(row.get("active") for row in questions.values()) and current_round <= MAX_EVIDENCE_ROUNDS:
        active_questions = [questions[key] for key in sorted(questions) if questions[key].get("active")]
        retrieved_by_ref: dict[str, dict[str, Any]] = {}
        per_question_search: dict[str, dict[str, Any]] = {}
        for question in active_questions:
            query = f"{question.get('gap', '')} {question.get('story_span', '')}"
            result = search_registry(registry or {}, query=query, exclude_story=story_id)
            opened = open_candidates(result)
            for row in opened:
                retrieved_by_ref.setdefault(str(row["ref"]), dict(row))
            retrieval_attempts[str(question["question_id"])] = retrieval_attempts.get(str(question["question_id"]), 0) + 1
            per_question_search[str(question["question_id"])] = {"result": result, "opened": opened}
        candidates = [retrieved_by_ref[key] for key in sorted(retrieved_by_ref, key=lambda ref: (-int(retrieved_by_ref[ref].get("score", 0)), str(retrieved_by_ref[ref].get("work", "")), ref))]
        # Keep the model packet bounded even when several child questions
        # search the registry in the same retrieval round.  The trace still
        # retains each question's complete retrieved/opened ref lists.
        candidates = candidates[:5]
        retrieval_messages = build_retrieval_messages(material, active_questions, candidates, questions)
        retrieval_fixture = _fixture_delta(material, active_questions, retrieval=True, candidates=candidates) if args.fixture else None
        retrieval_raw, retrieval_response, retrieval_content, retrieval_repair, api_calls = _call_stage(
            stage="local_retrieval_delta", round_number=current_round, messages=retrieval_messages, output_dir=output_dir,
            execution_kind=execution_kind, fixture_value=retrieval_fixture,
            replay_document=saved_outputs.get(f"round-{current_round:02d}-output.json"), timeout=args.timeout,
        )
        actual_api_calls += api_calls
        total_json_repairs += int(retrieval_repair not in {"none", "fixture"})
        candidate_sources = {str(row["ref"]): str(row.get("text", "")) for row in candidates}
        retrieval_normalized, retrieval_normalizations = normalize_delta(retrieval_raw, candidate_sources)
        retrieval_errors = validate_delta(retrieval_raw, retrieval_normalized, candidate_sources, {str(row["question_id"]) for row in active_questions})
        validation_errors.extend(retrieval_errors)
        boundary_normalizations += boundary_normalization_count(retrieval_normalizations)
        usage_rows.append({"round": current_round, "stage": "local_retrieval_delta", "api_usage": usage_fields(retrieval_response), "json_repair": retrieval_repair})
        write_json(ROOT, output_dir / f"round-{current_round:02d}-output.json", {
            "schema": "srm0-4a-delta-output",
            "schema_version": SCHEMA_VERSION,
            "story_id": story_id,
            "run_id": run_id,
            "execution_kind": execution_kind,
            "model": MODEL,
            "provider": PROVIDER,
            "prompt_version": PROMPT_VERSION,
            "raw_response": dict(retrieval_response or {}),
            "raw_content": retrieval_content,
            "raw_output": retrieval_raw,
            "normalized_output": retrieval_normalized,
            "boundary_normalizations": retrieval_normalizations,
            "candidate_refs": [str(row["ref"]) for row in candidates],
            "validation_errors": sorted(set(retrieval_errors)),
            "json_repair": retrieval_repair,
            "json_repair_count": int(retrieval_repair not in {"none", "fixture"}),
            "api_usage": usage_fields(retrieval_response),
            "canonical_write_back": False,
            "external_search_performed": False,
        })
        if retrieval_errors:
            break
        round_used: set[str] = set()
        round_new: set[str] = set()
        changed_values: list[int] = []
        for update in retrieval_normalized["updates"]:
            qid = str(update["question_id"])
            used_refs = [str(item.get("ref")) for aspect in update.get("answered_aspects", []) if isinstance(aspect, Mapping) for item in aspect.get("evidence", []) if isinstance(item, Mapping)]
            round_used.update(used_refs)
            evidence_found[qid] = evidence_found.get(qid, 0) + len(set(used_refs))
            prior = questions[qid]
            _, changed, novelty, new_refs = _apply_update(
                question=dict(prior), update=update, round_number=current_round, questions=questions, histories=histories,
                seen_refs=seen_refs, used_refs=used_refs, retrieval_attempts=retrieval_attempts,
                evidence_found=evidence_found, events=events,
            )
            changed_values.append(changed)
            round_new.update(new_refs)
            for ref in new_refs:
                _ = ref
        for qid, search_data in sorted(per_question_search.items()):
            result = search_data["result"]
            opened = search_data["opened"]
            q_used = sorted({ref for ref in round_used if any(str(row.get("ref")) == ref for row in opened)})
            q_new = sorted({ref for ref in round_new if ref in q_used})
            search_trace.append({
                "round": current_round,
                "question_id": qid,
                "searched_corpora": list(SEARCHED_CORPORA),
                "retrieved_refs": [str(row.get("ref")) for row in result.get("hits", [])],
                "opened_refs": [str(row.get("ref")) for row in opened],
                "used_refs": q_used,
                "new_used_refs": q_new,
            })
        round_metrics.append({
            "round": current_round,
            "G_t": len(active_questions),
            "D_t": int(any(changed_values)),
            "N_t": round(len(round_new) / len(round_used), 6) if round_used else 0.0,
            "used_evidence_refs": sorted(round_used),
            "new_used_evidence_refs": sorted(round_new),
            "retrieved_evidence_count": len(candidates),
            "opened_evidence_count": len(candidates),
            "retrieval": True,
        })
        current_round += 1

    if validation_errors:
        status = "validation_failed"
    elif any(row.get("active") for row in questions.values()):
        status = "hard_cap"
        for row in questions.values():
            if row.get("active"):
                row["active"] = False
                row["terminal_reason"] = "hard_cap"
    else:
        status = "converged"
    state = _state_artifact(story_id, status, questions, seen_refs, round_metrics, validation_errors)
    write_json(ROOT, output_dir / "research-state.json", state)
    _event(ROOT / output_dir / "events.jsonl", events)
    _event(ROOT / output_dir / "search-trace.jsonl", search_trace)
    total_tokens = sum((row.get("api_usage") or {}).get("total_tokens") or 0 for row in usage_rows)
    usage = {
        "schema": "srm0-4a-usage",
        "schema_version": SCHEMA_VERSION,
        "story_id": story_id,
        "run_id": run_id,
        "execution_kind": execution_kind,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "rounds": usage_rows,
        "total_tokens": total_tokens,
        "completion_count": actual_api_calls,
        "json_repair_count": total_json_repairs,
        "boundary_normalization_count": boundary_normalizations,
        "character_metrics": {
            "main_text_chars": material["main_text_chars"],
            "liu_chars": material["liu_chars"],
            "jianshu_chars": material["jianshu_chars"],
            "round_input_chars": {
                str(round_number): len(stable_json((ROOT / output_dir / f"round-{round_number:02d}-input.json").read_text(encoding="utf-8")))
                for round_number in range(current_round) if (ROOT / output_dir / f"round-{round_number:02d}-input.json").is_file()
            },
        },
        "retrieval": {
            "searched_corpora": list(SEARCHED_CORPORA),
            "trace_rows": len(search_trace),
            "seen_evidence_refs": sorted(seen_refs),
        },
        "validation_errors": sorted(set(validation_errors)),
        "canonical_write_back": False,
        "external_search_performed": False,
        "tool_call_count": 0,
    }
    write_json(ROOT, output_dir / "convergence.json", {
        "schema": "srm0-4a-convergence",
        "schema_version": SCHEMA_VERSION,
        "story_id": story_id,
        "story_status": status,
        "round_metrics": round_metrics,
        "question_terminals": {qid: questions[qid].get("terminal_reason") for qid in sorted(questions) if questions[qid].get("terminal_reason") not in {None, "refined_to_child"}},
        "canonical_write_back": False,
        "external_search_performed": False,
    })
    write_json(ROOT, output_dir / "usage.json", usage)
    artifact_names = sorted(path.name for path in (ROOT / output_dir).iterdir() if path.is_file() and path.name != "manifest.json")
    manifest = {
        "schema": "srm0-4a-manifest",
        "schema_version": SCHEMA_VERSION,
        "story_id": story_id,
        "run_id": run_id,
        "execution_kind": execution_kind,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "source_artifacts": material.get("source_artifacts", {}),
        "artifact_hashes": {name: sha256_file(ROOT, output_dir / name) for name in artifact_names},
        "completion_count": actual_api_calls,
        "tool_call_count": 0,
        "external_search_performed": False,
        "canonical_write_back": False,
        "validation_errors": sorted(set(validation_errors)),
    }
    write_json(ROOT, output_dir / "manifest.json", manifest)
    summary = {
        "story_id": story_id,
        "class": selection_row.get("class"),
        "main_text_chars": material["main_text_chars"],
        "liu_block_count": material["liu_block_count"],
        "jianshu_chars": material["jianshu_chars"],
        "initial_gap_count": len(initial_normalized.get("gaps", [])),
        "self_resolved_gaps_removed": sum(1 for row in gate_audit if "same-story" in str(row.get("gate_reason"))),
        "low_leverage_gaps_removed": sum(1 for row in gate_audit if "biographical" in str(row.get("gate_reason"))),
        "accepted_gap_count": len(frozen_questions),
        "rounds_executed": sorted({int(row.get("round", 0)) for row in usage_rows}),
        "searched_corpora": list(SEARCHED_CORPORA) if search_trace else [],
        "retrieved_refs": sorted({ref for row in search_trace for ref in row.get("retrieved_refs", [])}),
        "opened_refs": sorted({ref for row in search_trace for ref in row.get("opened_refs", [])}),
        "used_refs": sorted(seen_refs),
        "new_used_refs": sorted({ref for row in round_metrics for ref in row.get("new_used_evidence_refs", [])}),
        "round_metrics": round_metrics,
        "terminal_reasons": {qid: questions[qid].get("terminal_reason") for qid in sorted(questions) if questions[qid].get("terminal_reason")},
        "story_status": status,
        "token_usage": {"total_tokens": total_tokens, "completion_count": actual_api_calls},
        "validation_errors": sorted(set(validation_errors)),
    }
    return summary, manifest


def _batch_summary(selection_doc: Mapping[str, Any], stories: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    terminal_counts = {name: 0 for name in ("reading_sufficient", "evidence_saturated", "stable_conflict", "unresolved_no_evidence", "not_worth_pursuing", "hard_cap")}
    for story in stories:
        for reason in (story.get("terminal_reasons") or {}).values():
            if reason in terminal_counts:
                terminal_counts[reason] += 1
    count = len(stories)
    terminal_total = sum(
        1
        for story in stories
        for reason in (story.get("terminal_reasons") or {}).values()
        if reason in terminal_counts
    )
    round_values = [len(story.get("rounds_executed", [])) - 1 for story in stories]
    return {
        "schema": "srm0-4a-batch-summary",
        "schema_version": SCHEMA_VERSION,
        "selection": selection_doc,
        "stories": sorted((dict(row) for row in stories), key=lambda row: str(row.get("story_id"))),
        "aggregate": {
            "story_count": count,
            "average_evidence_rounds_per_story": round(sum(round_values) / count, 3) if count else 0,
            "reading_convergence_rate": round(terminal_counts["reading_sufficient"] / max(1, terminal_total), 3),
            "evidence_saturation_rate": round(terminal_counts["evidence_saturated"] / max(1, terminal_total), 3),
            "stable_conflict_rate": round(terminal_counts["stable_conflict"] / max(1, terminal_total), 3),
            "unresolved_no_evidence_rate": round(terminal_counts["unresolved_no_evidence"] / max(1, terminal_total), 3),
            "terminal_question_counts": terminal_counts,
            "premature_stop_candidates": [],
            "unnecessary_continuation_candidates": [],
        },
        "canonical_write_back": False,
        "external_search_performed": False,
    }


def run(args: argparse.Namespace) -> int:
    if args.fixture and args.replay_existing:
        raise SystemExit("--fixture cannot be combined with --replay-existing")
    selection_doc = selection(ROOT)
    write_json(ROOT, SELECTION_PATH, selection_doc)
    selected = selection_doc.get("selected", []) if isinstance(selection_doc, Mapping) else []
    selected_ids = {str(row.get("story_id")) for row in selected if isinstance(row, Mapping)}
    story_ids = [args.story] if args.story else [str(row["story_id"]) for row in selected]
    if args.story and args.story not in selected_ids:
        raise SystemExit(f"Story is not in deterministic SRM0.4A selection: {args.story}")
    if not story_ids:
        raise SystemExit("deterministic selection produced no Stories")
    selected_by_id = {str(row["story_id"]): row for row in selected if isinstance(row, Mapping)}
    registry: Mapping[str, Mapping[str, Any]] | None = None
    summaries: list[dict[str, Any]] = []
    for story_id in story_ids:
        material = story_material(ROOT, story_id)
        summary, _manifest = _run_story(material, selected_by_id[story_id], args, registry)
        summaries.append(summary)
        # The registry is immutable for this run and may be reused across all
        # Stories once one local retrieval round is needed.
        if registry is None and any(summary.get("rounds_executed", [])[1:] if summary.get("rounds_executed") else []):
            registry = build_retrieval_registry(ROOT)
    if not (ROOT / REVIEW_PATH).is_file():
        write_json(ROOT, REVIEW_PATH, review_template(story_ids))
    batch = _batch_summary(selection_doc, summaries)
    write_json(ROOT, BATCH_SUMMARY_PATH, batch)
    failed = [row for row in summaries if row.get("validation_errors")]
    print(f"SRM0.4A completed ({'fixture' if args.fixture else 'replay' if args.replay_existing else 'real_model'})")
    print("selected:", ", ".join(story_ids))
    for row in summaries:
        print(f"{row['story_id']}: status={row['story_status']} rounds={row['rounds_executed']} used={len(row['used_refs'])} tokens={row['token_usage']['total_tokens']}")
    print(f"batch: {BATCH_SUMMARY_PATH.as_posix()}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
