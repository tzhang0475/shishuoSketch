#!/usr/bin/env python3
"""Run one SRM0.1R Completion-2 evidence-consumption retest."""

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

from ds1_common import ROOT, sha256_file, stable_json, write_json  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402
from srm0_1_common import input_hash, parse_json_content  # noqa: E402
from srm0_1r_common import (  # noqa: E402
    MODEL,
    ORIGINAL_ROOT,
    PROMPT_VERSION,
    PROVIDER,
    RETEST_ROOT,
    REVIEW_PATH,
    STORY_ID,
    build_messages,
    build_state_events,
    character_metrics,
    load_frozen_inputs,
    normalize_semantic_result,
    review_template,
    validate_semantic_result,
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", default=STORY_ID, choices=[STORY_ID])
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--fixture", action="store_true", help="use a local contract fixture; never calls DeepSeek")
    parser.add_argument(
        "--replay-existing",
        action="store_true",
        help="re-materialize the saved real response in retest/model-output.json; never calls DeepSeek",
    )
    return parser.parse_args()


def fixture_result(frozen: Mapping[str, Any]) -> dict[str, Any]:
    candidates = list(frozen["candidates"])
    first = candidates[0]["ref"]
    second = candidates[1]["ref"]
    later = next((row["ref"] for row in candidates if row["ref"].startswith("s1-assertion-1cc")), first)
    return {
        "useful_evidence": [
            {"ref": first, "finding": "材料直接呈现庾亮与陶公之间因蘇峻之難而产生的责任冲突。", "role": "direct_support"},
            {"ref": second, "finding": "后续史料补充了庾亮引咎后陶侃释然的叙述，但仍需注意传递层次。", "role": "context"},
        ],
        "question_resolution": {
            "question_id": "Q1",
            "status": "partially_resolved",
            "current_answer": "现有材料支持把释然理解为对庾亮引咎谢罪及当前危机责任的回应，但不能仅凭这些片段确定陶公的内在心理机制。",
            "remaining_gap": "原文省略了双方言语与责任谈判的具体内容。",
            "evidence_refs": [first, second],
        },
        "reading_links": [
            {"context": "危机责任的背景", "text_span": "陶不覺釋然", "reading_effect": "不覺保留了转折的简略性；证据使读者看见责任回应，而不把它扩写成心理独白。", "refs": [first, second]}
        ],
        "static_relation_candidates": [],
        "appraisal_candidates": [],
        "candidate_subquestion": None,
        "deprioritized_associations": [
            {"idea": "陶侃重视实际治理是否直接解释本场释然", "reason": "相关噉薤留白材料出现在所给晋书片段的释然后，存在时间方向风险，不能作为此前释然的直接原因。", "trigger_refs": [later]}
        ],
        "stop_recommendation": {"stop": True, "reason": "Q1已有部分回答；剩余缺口需要新的证据阶段，本次 retest 不启动新问题。"},
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


def run(args: argparse.Namespace) -> int:
    frozen = load_frozen_inputs(ROOT)
    messages = build_messages(frozen)
    metrics = character_metrics(frozen, messages)
    existing_output: dict[str, Any] | None = None
    if args.replay_existing:
        if args.fixture:
            raise SystemExit("--replay-existing cannot be combined with --fixture")
        existing_path = ROOT / RETEST_ROOT / "model-output.json"
        if not existing_path.is_file():
            raise SystemExit(f"cannot replay missing artifact: {existing_path}")
        existing_output = json.loads(existing_path.read_text(encoding="utf-8"))
        if existing_output.get("execution_kind") != "real_model":
            raise SystemExit("--replay-existing requires a saved real_model response")
        run_id = str(existing_output.get("run_id") or "")
        if not run_id:
            raise SystemExit("saved real_model response has no run_id")
    else:
        started_at = utc_now()
        run_id = "srm0-1r-" + input_hash({"story_id": STORY_ID, "candidate_hash": frozen["candidate_hash"], "started_at": started_at})[:20]
    execution_kind = "fixture" if args.fixture else "real_model"
    model_input = {
        "schema": "srm0-1r-model-input",
        "schema_version": 1,
        "stage": "completion_2_evidence_consumption_retest",
        "artifact_kind": "generated_retest_input",
        "candidate_status": "candidate",
        "story_id": STORY_ID,
        "run_id": run_id,
        "execution_kind": execution_kind,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "parameters": {"temperature": 0, "response_format": {"type": "json_object"}, "tools": []},
        "messages": messages,
        "payload_hash": input_hash(messages[1]["content"]),
        "frozen_candidate_hash": frozen["candidate_hash"],
        "character_metrics": metrics,
        "canonical_write_back": False,
    }
    write_json(ROOT, RETEST_ROOT / "model-input.json", model_input)

    response: dict[str, Any] | None = None
    repair = "fixture"
    raw_content = None
    api_usage: dict[str, Any] = {}
    if args.fixture:
        raw = fixture_result(frozen)
        api_usage = {
            "prompt_tokens": None,
            "prompt_cache_hit_tokens": None,
            "prompt_cache_miss_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "raw_usage": {},
        }
    elif args.replay_existing:
        raw_content = str(existing_output.get("raw_content") or "")
        if not raw_content.strip():
            raise SystemExit("saved real_model response has no raw_content")
        raw, repair = parse_json_content(raw_content)
        saved_usage = existing_output.get("api_usage", {})
        api_usage = dict(saved_usage) if isinstance(saved_usage, Mapping) else {}
    else:
        response = call_deepseek(
            messages,
            model=MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            thinking={"type": "disabled"},
            timeout=args.timeout,
        )
        raw_content = _response_content(response)
        raw, repair = parse_json_content(raw_content)
        response_usage = response.get("usage", {})
        api_usage = {
            "prompt_tokens": response_usage.get("prompt_tokens") if isinstance(response_usage, Mapping) else None,
            "prompt_cache_hit_tokens": response_usage.get("prompt_cache_hit_tokens") if isinstance(response_usage, Mapping) else None,
            "prompt_cache_miss_tokens": response_usage.get("prompt_cache_miss_tokens") if isinstance(response_usage, Mapping) else None,
            "completion_tokens": response_usage.get("completion_tokens") if isinstance(response_usage, Mapping) else None,
            "total_tokens": response_usage.get("total_tokens") if isinstance(response_usage, Mapping) else None,
            "raw_usage": response_usage if isinstance(response_usage, Mapping) else {},
        }
    candidate_refs = [row["ref"] for row in frozen["candidates"]]
    normalized = normalize_semantic_result(raw, str(frozen["story_text"]), candidate_refs, frozen["candidates"])
    validation_errors = validate_semantic_result(normalized, str(frozen["story_text"]), candidate_refs)
    model_output = {
        "schema": "srm0-1r-model-output",
        "schema_version": 1,
        "stage": "completion_2_evidence_consumption_retest",
        "artifact_kind": "generated_retest_output",
        "candidate_status": "candidate",
        "story_id": STORY_ID,
        "run_id": run_id,
        "execution_kind": execution_kind,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "json_repair": repair,
        "api_usage": api_usage,
        "raw_content": raw_content,
        "normalized_output": normalized,
        "validation_errors": validation_errors,
        "canonical_write_back": False,
    }
    write_json(ROOT, RETEST_ROOT / "model-output.json", model_output)
    if validation_errors:
        raise SystemExit("SRM0.1R validation failed: " + "; ".join(validation_errors))

    state, events = build_state_events(frozen, normalized, run_id=run_id, execution_kind=execution_kind)
    write_json(ROOT, RETEST_ROOT / "state.json", state)
    events_path = ROOT / RETEST_ROOT / "events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    events_path.write_text("".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in events), encoding="utf-8")

    usage = {
        "schema": "srm0-1r-usage",
        "story_id": STORY_ID,
        "run_id": run_id,
        "execution_kind": execution_kind,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "temperature": 0,
        "api_usage": model_output["api_usage"],
        "completion_output_tokens": model_output["api_usage"].get("completion_tokens"),
        "character_metrics": metrics,
        "serialized_output_chars": len(stable_json(normalized)),
        "canonical_write_back": False,
    }
    write_json(ROOT, RETEST_ROOT / "usage.json", usage)
    if not (ROOT / REVIEW_PATH).is_file():
        write_json(ROOT, REVIEW_PATH, review_template())

    artifact_paths = ["model-input.json", "model-output.json", "state.json", "events.jsonl", "usage.json"]
    manifest = {
        "schema": "srm0-1r-manifest",
        "schema_version": 1,
        "story_id": STORY_ID,
        "run_id": run_id,
        "execution_kind": execution_kind,
        "prompt_version": PROMPT_VERSION,
        "retest_of": ORIGINAL_ROOT.as_posix(),
        "frozen_candidate_hash": frozen["candidate_hash"],
        "source_artifacts": frozen["source_artifacts"],
        "artifact_hashes": {name: sha256_file(ROOT, RETEST_ROOT / name) for name in artifact_paths},
        "canonical_write_back": False,
        "completion_count": 0 if args.fixture else 1,
        "retrieval_rerun": False,
        "candidate_subquestion_executed": False,
    }
    write_json(ROOT, RETEST_ROOT / "manifest.json", manifest)
    usage_api = model_output["api_usage"]
    print(f"SRM0.1R completed ({execution_kind})")
    print(f"Q1 status: {normalized['question_resolution']['status']}")
    print(f"useful evidence: {[row['ref'] for row in normalized['useful_evidence']]}")
    print(f"candidate subquestion: {normalized['candidate_subquestion']}")
    print(f"tokens: {usage_api.get('total_tokens')}")
    print(f"output: {(RETEST_ROOT / 'model-output.json').as_posix()}")
    print(f"state: {(RETEST_ROOT / 'state.json').as_posix()}")
    print(f"review: {REVIEW_PATH.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
