#!/usr/bin/env python3
"""Run exactly one SRM0.1 cycle for 27-jiajue-008.

The default path performs two DeepSeek completions with local retrieval
between them.  ``--fixture`` exercises the same normalization and memory
materialization path without making an API call.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ds1_common import write_json  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402
from srm0_1_common import (  # noqa: E402
    MODEL,
    OUTPUT_ROOT,
    PROMPT_VERSION,
    PROVIDER,
    REVIEW_PATH,
    ROOT,
    STORY_ID,
    build_initial_packet,
    build_memory_state,
    build_source_registry,
    compression_metrics,
    input_hash,
    memory_messages,
    normalize_memory_patch,
    normalize_question_output,
    parse_json_content,
    question_messages,
    retrieve_windows,
    sha256_file,
    usage_record,
    validate_memory_patch,
    validate_question_output,
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", default=STORY_ID, choices=[STORY_ID])
    parser.add_argument("--fixture", action="store_true", help="use deterministic local fixture responses; never calls DeepSeek")
    parser.add_argument("--timeout", type=int, default=120)
    return parser.parse_args()


def fixture_question(story_text: str) -> dict[str, Any]:
    return normalize_question_output(
        {
            "textual_puzzles": [
                {"span": "陶自起止之", "category": "relationship_state", "unexplained": "陶公为何起身止拜，礼势如何转变？", "reading_target": "陶自起止之", "importance": "high"},
                {"span": "庾乃引咎責躬，深相遜謝", "category": "causal_precondition", "unexplained": "引咎与逊谢对应的政治处境尚未解释。", "reading_target": "庾乃引咎責躬，深相遜謝", "importance": "high"},
                {"span": "庾元規何縁拜陶士衡", "category": "identity", "unexplained": "复合称谓与拜礼对象的身份关系仍有冲突。", "reading_target": "庾元規何縁拜陶士衡", "importance": "medium"},
            ],
            "active_question": {
                "question": "蘇峻之難与庾亮当时的处境，如何使陶公止拜、庾亮引咎这一连串行动具有特定的关系含义？",
                "derived_from": ["P1", "P2"],
                "why_needed": "若不了解危机、责任与双方位置，读者只能看到礼节动作，不能解释动作链的转折。",
                "reading_target": "陶自起止之，曰：“庾元規何縁拜陶士衡？”畢，又降就下坐。陶又自要起同坐。坐定，庾乃引咎責躬，深相遜謝。",
                "importance": "high",
            },
            "search_probes": ["蘇峻之難", "陶侃盟主", "庾亮敗績", "陶士衡", "引咎責躬"],
        },
        story_text,
    )


def fixture_patch(candidate_refs: list[str], story_text: str) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []
    for index, ref in enumerate(candidate_refs):
        decisions.append(
            {
                "evidence_ref": ref,
                "decision": "keep" if index < 3 else ("later_only" if index == 3 else "discard"),
                "reason": "与当前问题有字符层相关性，保留为待人工核查的证据线索。" if index < 3 else "本轮不纳入当前研究记忆。",
            }
        )
    kept = candidate_refs[:3]
    return {
        "evidence_decisions": decisions,
        "claim_updates": [
            {
                "claim_id": "C1",
                "operation": "add",
                "update_type": "new_evidence",
                "text": "检索片段提供了与蘇峻之難及相关人物处境有关的史料线索，仍需人工核查。",
                "evidence_refs": kept[:1],
                "epistemic_status": "uncertain",
            }
        ] if kept else [],
        "question_updates": [{"question_id": "Q1", "status": "superseded", "reason": "本轮形成更窄的身份核查问题。"}],
        "new_questions": [
            {
                "question_id": "Q2",
                "question": "“陶士衡”这一复合称谓的身份关系如何在现有证据中进一步核查？",
                "derived_from": ["Q1", "P3"],
                "why_needed": "身份冲突可能改变对拜礼对象和称谓转折的理解。",
                "reading_target": "庾元規何縁拜陶士衡",
                "importance": "medium",
                "next_active_question": True,
            }
        ],
        "reading_link_updates": [
            {
                "text_span": "陶自起止之",
                "reading_effect": "礼节动作可作为关系转折的重读入口，但本轮只保留有证据的研究线索。",
                "evidence_refs": kept[:1],
            },
            {
                "text_span": "庾乃引咎責躬，深相遜謝",
                "reading_effect": "引咎与逊谢应连同危机处境核查，不把线索直接写成定论。",
                "evidence_refs": kept[1:2] or kept[:1],
            },
        ] if kept else [],
        "stop_recommendation": {"stop": True, "reason": "SRM0.1 只记录 Q2，不执行下一问题。"},
    }


def _response_content(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("DeepSeek response has no choices")
    message = choices[0].get("message", {}) if isinstance(choices[0], Mapping) else {}
    content = message.get("content") if isinstance(message, Mapping) else None
    if not isinstance(content, str) or not content.strip():
        raise ValueError("DeepSeek response has no JSON content")
    return content


def _write_packet(relative: Path, value: Mapping[str, Any]) -> None:
    write_json(ROOT, relative, value)


def _ensure_clean_output() -> None:
    if (ROOT / OUTPUT_ROOT / "state.json").exists() or (ROOT / OUTPUT_ROOT / "events.jsonl").exists():
        raise SystemExit(f"SRM0.1 output already exists at {OUTPUT_ROOT}; preserve it and review it before rerunning")


def _make_output_review() -> None:
    if (ROOT / REVIEW_PATH).is_file():
        return
    write_json(
        ROOT,
        REVIEW_PATH,
        {
            "schema": "srm0-1-review",
            "schema_version": 1,
            "stage": "SRM0.1",
            "records": [
                {
                    "story_id": STORY_ID,
                    "decision": "pending",
                    "initial_question_quality": None,
                    "retrieval_quality": None,
                    "evidence_selection": None,
                    "memory_patch_quality": None,
                    "question_evolution": None,
                    "reading_relevance": None,
                    "restraint": None,
                    "token_efficiency": None,
                    "notes": "",
                }
            ],
            "canonical_write_back": False,
        },
    )


def run_cycle(args: argparse.Namespace) -> int:
    _ensure_clean_output()
    packet, packet_metrics = build_initial_packet(ROOT, args.story)
    execution_kind = "fixture" if args.fixture else "real_model"
    started_at = utc_now()
    run_id = "srm0-" + input_hash({"story_id": args.story, "prompt_version": PROMPT_VERSION, "started_at": started_at})[:20]
    first_messages = question_messages(packet)
    first_metrics = compression_metrics(
        int(packet_metrics["raw_input_chars"]),
        sum(len(str(message.get("content", ""))) for message in first_messages),
        0,
        0,
    )
    first_input = {
        "schema": "srm0-1-round-input",
        "stage": "completion_1_question_generation",
        "execution_kind": execution_kind,
        "story_id": args.story,
        "run_id": run_id,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "parameters": {"temperature": 0, "response_format": {"type": "json_object"}, "tools": []},
        "messages": first_messages,
        "input_hash": input_hash(packet),
        "canonical_write_back": False,
        "metrics": first_metrics,
    }
    _write_packet(OUTPUT_ROOT / "round-00-input.json", first_input)

    first_response: dict[str, Any] | None = None
    first_repair = "fixture"
    first_raw_content: str | None = None
    if args.fixture:
        question = fixture_question(str(packet["story_text"]))
    else:
        first_response = call_deepseek(
            first_messages,
            model=MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            thinking={"type": "disabled"},
            timeout=args.timeout,
        )
        first_raw_content = _response_content(first_response)
        raw, first_repair = parse_json_content(first_raw_content)
        try:
            question = normalize_question_output(raw, str(packet["story_text"]))
        except ValueError as error:
            _write_packet(
                OUTPUT_ROOT / "round-00-output.json",
                {
                    "schema": "srm0-1-round-output",
                    "stage": "completion_1_question_generation",
                    "execution_kind": execution_kind,
                    "story_id": args.story,
                    "run_id": run_id,
                    "model": MODEL,
                    "provider": PROVIDER,
                    "prompt_version": PROMPT_VERSION,
                    "json_repair": first_repair,
                    "api_usage": usage_record(first_response),
                    "raw_content": first_raw_content,
                    "output": raw,
                    "validation_errors": [str(error)],
                    "canonical_write_back": False,
                },
            )
            raise
    question_errors = validate_question_output(question, str(packet["story_text"]))
    _write_packet(
        OUTPUT_ROOT / "round-00-output.json",
        {
            "schema": "srm0-1-round-output",
            "stage": "completion_1_question_generation",
            "execution_kind": execution_kind,
            "story_id": args.story,
            "run_id": run_id,
            "model": MODEL,
            "provider": PROVIDER,
            "prompt_version": PROMPT_VERSION,
            "json_repair": first_repair,
            "api_usage": usage_record(first_response),
            "output": question,
            "validation_errors": question_errors,
            "canonical_write_back": False,
        },
    )
    if question_errors:
        raise SystemExit("Completion 1 validation failed: " + "; ".join(question_errors))

    registry, source_hashes = build_source_registry(ROOT)
    entity_hints = [card["canonical_name"] for card in packet["person_orientation_cards"]]
    for card in packet["person_orientation_cards"]:
        entity_hints.extend(card.get("aliases", []))
    retrieval = retrieve_windows(
        registry,
        question["search_probes"],
        entity_hints=entity_hints,
        exclude_story_id=args.story,
    )
    _write_packet(
        OUTPUT_ROOT / "round-01-search-trace.json",
        {
            "schema": "srm0-1-search-trace",
            "stage": "local_retrieval",
            "execution_kind": execution_kind,
            "story_id": args.story,
            "run_id": run_id,
            "prompt_version": PROMPT_VERSION,
            "source_hashes": source_hashes,
            "candidate_registry_count": len(registry),
            "search_trace": retrieval,
            "canonical_write_back": False,
        },
    )

    story_text = str(packet["story_text"])
    second_messages = memory_messages(args.story, story_text, question["active_question"], retrieval["model_candidates"])
    model_input_chars = sum(len(str(message.get("content", ""))) for message in second_messages)
    second_metrics = compression_metrics(
        int(packet_metrics["raw_input_chars"]),
        model_input_chars,
        int(retrieval["raw_retrieval_chars"]),
        int(retrieval["model_evidence_chars"]),
    )
    _write_packet(
        OUTPUT_ROOT / "round-01-model-input.json",
        {
            "schema": "srm0-1-round-input",
            "stage": "completion_2_memory_patch",
            "execution_kind": execution_kind,
            "story_id": args.story,
            "run_id": run_id,
            "model": MODEL,
            "provider": PROVIDER,
            "prompt_version": PROMPT_VERSION,
            "parameters": {"temperature": 0, "response_format": {"type": "json_object"}, "tools": []},
            "messages": second_messages,
            "input_hash": input_hash(second_messages),
            "metrics": second_metrics,
            "canonical_write_back": False,
        },
    )

    second_response: dict[str, Any] | None = None
    second_repair = "fixture"
    second_raw_content: str | None = None
    if args.fixture:
        patch = fixture_patch([str(row["ref"]) for row in retrieval["model_candidates"]], story_text)
    else:
        second_response = call_deepseek(
            second_messages,
            model=MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            thinking={"type": "disabled"},
            timeout=args.timeout,
        )
        second_raw_content = _response_content(second_response)
        raw, second_repair = parse_json_content(second_raw_content)
        try:
            patch = normalize_memory_patch(raw, [str(row["ref"]) for row in retrieval["model_candidates"]], story_text)
        except ValueError as error:
            _write_packet(
                OUTPUT_ROOT / "round-01-model-output.json",
                {
                    "schema": "srm0-1-round-output",
                    "stage": "completion_2_memory_patch",
                    "execution_kind": execution_kind,
                    "story_id": args.story,
                    "run_id": run_id,
                    "model": MODEL,
                    "provider": PROVIDER,
                    "prompt_version": PROMPT_VERSION,
                    "json_repair": second_repair,
                    "api_usage": usage_record(second_response),
                    "raw_content": second_raw_content,
                    "output": raw,
                    "validation_errors": [str(error)],
                    "canonical_write_back": False,
                },
            )
            raise
    patch_errors = validate_memory_patch(patch, [str(row["ref"]) for row in retrieval["model_candidates"]], story_text)
    _write_packet(
        OUTPUT_ROOT / "round-01-model-output.json",
        {
            "schema": "srm0-1-round-output",
            "stage": "completion_2_memory_patch",
            "execution_kind": execution_kind,
            "story_id": args.story,
            "run_id": run_id,
            "model": MODEL,
            "provider": PROVIDER,
            "prompt_version": PROMPT_VERSION,
            "json_repair": second_repair,
            "api_usage": usage_record(second_response),
            "output": patch,
            "validation_errors": patch_errors,
            "canonical_write_back": False,
        },
    )
    if patch_errors:
        raise SystemExit("Completion 2 validation failed: " + "; ".join(patch_errors))

    state, events = build_memory_state(args.story, question["active_question"], retrieval, patch, execution_kind=execution_kind, run_id=run_id)
    write_json(ROOT, OUTPUT_ROOT / "state.json", state)
    events_path = ROOT / OUTPUT_ROOT / "events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    events_path.write_text("".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in events), encoding="utf-8")
    _make_output_review()

    manifest = {
        "schema": "srm0-1-manifest",
        "schema_version": 1,
        "story_id": args.story,
        "run_id": run_id,
        "execution_kind": execution_kind,
        "prompt_version": PROMPT_VERSION,
        "artifact_paths": {
            "round_00_input": (OUTPUT_ROOT / "round-00-input.json").as_posix(),
            "round_00_output": (OUTPUT_ROOT / "round-00-output.json").as_posix(),
            "search_trace": (OUTPUT_ROOT / "round-01-search-trace.json").as_posix(),
            "round_01_input": (OUTPUT_ROOT / "round-01-model-input.json").as_posix(),
            "round_01_output": (OUTPUT_ROOT / "round-01-model-output.json").as_posix(),
            "state": (OUTPUT_ROOT / "state.json").as_posix(),
            "events": (OUTPUT_ROOT / "events.jsonl").as_posix(),
        },
        "source_hashes": source_hashes,
        "candidate_hashes": {
            relative: sha256_file(ROOT, Path(relative))
            for relative in [
                (OUTPUT_ROOT / "round-00-input.json").as_posix(),
                (OUTPUT_ROOT / "round-00-output.json").as_posix(),
                (OUTPUT_ROOT / "round-01-search-trace.json").as_posix(),
                (OUTPUT_ROOT / "round-01-model-input.json").as_posix(),
                (OUTPUT_ROOT / "round-01-model-output.json").as_posix(),
                (OUTPUT_ROOT / "state.json").as_posix(),
                (OUTPUT_ROOT / "events.jsonl").as_posix(),
            ]
        },
        "canonical_write_back": False,
        "next_question_executed": False,
    }
    write_json(ROOT, OUTPUT_ROOT / "manifest.json", manifest)
    print(f"SRM0.1 completed ({execution_kind})")
    print(f"Q1: {question['active_question']['question']}")
    print(f"retrieval candidates: {len(retrieval['model_candidates'])} / {retrieval['model_evidence_chars']} chars")
    print(f"Q2 pending: {[row['question'] for row in patch['new_questions'] if row.get('next_active_question')]}")
    print(f"state: {(OUTPUT_ROOT / 'state.json').as_posix()}")
    print(f"review: {REVIEW_PATH.as_posix()}")
    return 0


def main() -> int:
    args = parse_args()
    return run_cycle(args)


if __name__ == "__main__":
    raise SystemExit(main())
