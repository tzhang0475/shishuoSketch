#!/usr/bin/env python3
"""Run one SRM0.2B blind Story-plus-Liu discovery completion."""

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
from srm0_2b_common import (  # noqa: E402
    ENTRY_PATH,
    MODEL,
    OUTPUT_ROOT,
    PROMPT_VERSION,
    PROVIDER,
    REVIEW_PATH,
    STORY_ID,
    build_messages,
    character_metrics,
    load_entry,
    model_payload,
    normalize_discovery,
    normalization_repairs,
    parse_json_content,
    review_template,
    validate_discovery,
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", default=STORY_ID, choices=[STORY_ID])
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--fixture", action="store_true", help="use a local valid fixture; never calls DeepSeek")
    parser.add_argument(
        "--replay-existing",
        action="store_true",
        help="re-materialize the saved real response; never calls DeepSeek",
    )
    return parser.parse_args()


def fixture_result(entry: Mapping[str, Any]) -> dict[str, Any]:
    trigger = str(entry["story_text"]).splitlines()[0].strip()
    return {
        "questions": [
            {
                "question": "正文为什么先写山公年踰七十而仍知管时任？",
                "trigger_text": trigger,
                "why_it_matters": "这句话把年齿、声望与仍在任联系在一起，可能决定故事的观察重点。",
                "what_more_evidence_is_needed": "需要同时代的任职记录或传记材料。",
            }
        ],
        "person_connections": [],
        "appraisals": [],
    }


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


def run(args: argparse.Namespace) -> int:
    entry = load_entry(ROOT)
    messages = build_messages(entry)
    metrics = character_metrics(entry, messages)
    existing_output: dict[str, Any] | None = None
    if args.replay_existing:
        if args.fixture:
            raise SystemExit("--replay-existing cannot be combined with --fixture")
        existing_path = ROOT / OUTPUT_ROOT / "model-output.json"
        if not existing_path.is_file():
            raise SystemExit(f"cannot replay missing artifact: {existing_path}")
        existing_output = json.loads(existing_path.read_text(encoding="utf-8"))
        if existing_output.get("execution_kind") != "real_model":
            raise SystemExit("--replay-existing requires a saved real_model response")
        run_id = str(existing_output.get("run_id") or "")
        if not run_id:
            raise SystemExit("saved real_model response has no run_id")
        created_at = "replayed"
    else:
        created_at = utc_now()
        run_id = "srm0-2b-" + sha256_file(ROOT, ENTRY_PATH)[:12] + "-" + created_at.replace("-", "").replace(":", "").replace("T", "").replace("Z", "")
    execution_kind = "fixture" if args.fixture else "real_model"

    model_input = {
        "schema": "srm0-2b-model-input",
        "schema_version": 1,
        "stage": "blind_rich_story_discovery",
        "artifact_kind": "generated_discovery_input",
        "story_id": STORY_ID,
        "run_id": run_id,
        "execution_kind": execution_kind,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "parameters": {"temperature": 0, "response_format": {"type": "json_object"}, "tools": []},
        "messages": messages,
        "character_metrics": metrics,
        "canonical_write_back": False,
    }
    write_json(ROOT, OUTPUT_ROOT / "model-input.json", model_input)

    response: dict[str, Any] | None = None
    raw_content: str | None = None
    repair = "fixture"
    if args.fixture:
        raw = fixture_result(entry)
    elif args.replay_existing:
        raw_content = str(existing_output.get("raw_content") or "")
        if not raw_content.strip():
            raise SystemExit("saved real_model response has no raw_content")
        raw, repair = parse_json_content(raw_content)
        saved_response = existing_output.get("raw_response")
        response = dict(saved_response) if isinstance(saved_response, Mapping) else {}
    else:
        response = call_deepseek(
            messages,
            model=MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            tools=[],
            thinking={"type": "disabled"},
            timeout=args.timeout,
        )
        raw_content = response_content(response)
        raw, repair = parse_json_content(raw_content)

    normalized = normalize_discovery(raw, entry)
    validation_errors = validate_discovery(raw, normalized, entry)
    repairs = normalization_repairs(raw, normalized)
    model_output = {
        "schema": "srm0-2b-model-output",
        "schema_version": 1,
        "stage": "blind_rich_story_discovery",
        "artifact_kind": "generated_discovery_output",
        "story_id": STORY_ID,
        "run_id": run_id,
        "execution_kind": execution_kind,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "json_repair": repair,
        "json_repair_count": 0 if repair == "none" else (0 if repair == "fixture" else 1),
        "raw_response": response or {},
        "raw_content": raw_content,
        "raw_discovery": raw,
        "normalized_output": normalized,
        "normalization_repairs": repairs,
        "validation_errors": validation_errors,
        "api_usage": usage_fields(response),
        "canonical_write_back": False,
        "search_performed": False,
    }
    write_json(ROOT, OUTPUT_ROOT / "model-output.json", model_output)
    if validation_errors:
        raise SystemExit("SRM0.2B validation failed: " + "; ".join(validation_errors))

    state = {
        "schema": "srm0-2b-discovery-state",
        "schema_version": 1,
        "story_id": STORY_ID,
        "stage": "blind_discovery_complete",
        "questions": normalized["questions"],
        "person_connections": normalized["person_connections"],
        "appraisals": normalized["appraisals"],
        "canonical_write_back": False,
    }
    write_json(ROOT, OUTPUT_ROOT / "discovery-state.json", state)

    usage = {
        "schema": "srm0-2b-usage",
        "schema_version": 1,
        "story_id": STORY_ID,
        "run_id": run_id,
        "execution_kind": execution_kind,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "temperature": 0,
        "api_usage": model_output["api_usage"],
        "character_metrics": metrics,
        "json_repair_count": model_output["json_repair_count"],
        "tool_call_count": 0,
        "search_performed": False,
        "canonical_write_back": False,
    }
    write_json(ROOT, OUTPUT_ROOT / "usage.json", usage)

    if not (ROOT / REVIEW_PATH).is_file():
        write_json(ROOT, REVIEW_PATH, review_template())

    artifact_names = ["model-input.json", "model-output.json", "discovery-state.json", "usage.json"]
    manifest = {
        "schema": "srm0-2b-manifest",
        "schema_version": 1,
        "story_id": STORY_ID,
        "run_id": run_id,
        "created_at": created_at,
        "execution_kind": execution_kind,
        "prompt_version": PROMPT_VERSION,
        "source_entry": ENTRY_PATH.as_posix(),
        "source_entry_sha256": entry["entry_sha256"],
        "artifact_hashes": {name: sha256_file(ROOT, OUTPUT_ROOT / name) for name in artifact_names},
        "completion_count": 0 if args.fixture else 1,
        "tool_call_count": 0,
        "search_performed": False,
        "canonical_write_back": False,
    }
    write_json(ROOT, OUTPUT_ROOT / "manifest.json", manifest)

    api_usage = model_output["api_usage"]
    print(f"SRM0.2B completed ({execution_kind})")
    print(f"questions: {len(normalized['questions'])}")
    print(f"person_connections: {len(normalized['person_connections'])}")
    print(f"appraisals: {len(normalized['appraisals'])}")
    print(f"tokens: {api_usage.get('total_tokens')}")
    print(f"output: {(OUTPUT_ROOT / 'model-output.json').as_posix()}")
    print(f"state: {(OUTPUT_ROOT / 'discovery-state.json').as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
