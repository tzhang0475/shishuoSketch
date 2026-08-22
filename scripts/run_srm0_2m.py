#!/usr/bin/env python3
"""Run one SRM0.2M layered-commentary first-reading completion."""

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
from srm0_1_common import parse_json_content  # noqa: E402
from srm0_2m_common import (  # noqa: E402
    BASELINE_ROOT,
    ENTRY_PATH,
    MODEL,
    OUTPUT_ROOT,
    PROMPT_VERSION,
    PROVIDER,
    REVIEW_PATH,
    STORY_ID,
    build_messages,
    build_model_payload,
    character_metrics,
    load_entry,
    normalization_repairs,
    normalize_layered,
    read_json,
    resolve_jianshu_material,
    review_template,
    validate_layered,
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", default=STORY_ID, choices=[STORY_ID])
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--fixture", action="store_true", help="use a local contract fixture; never calls DeepSeek")
    parser.add_argument("--replay-existing", action="store_true", help="re-materialize saved real output; never calls DeepSeek")
    return parser.parse_args()


def fixture_result(material: Mapping[str, Any]) -> dict[str, Any]:
    story_text = str(material["entry"]["story_text"])
    return {
        "reading_questions": [
            {
                "story_span": story_text.splitlines()[0].strip(),
                "question": "年踰七十而猶知管時任，正文在强调什么？",
                "why_it_matters": "它是正文对山公的第一层定位。",
                "commentary_clues": [{"ref": "L01", "effect": "刘注补出字与出处。"}],
                "reading_change_if_answered": "可以更准确理解开头对人物的限定。",
                "additional_evidence_needed": "同时代任职材料。",
            }
        ],
        "commentary_issues": [],
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


def material_resolution(material: Mapping[str, Any]) -> dict[str, Any]:
    entry = material["entry"]
    return {
        "schema": "srm0-2m-material-resolution",
        "schema_version": 1,
        "story_id": STORY_ID,
        "main_text_chars": len(str(entry["story_text"])),
        "liu_block_count": len(entry["liu_annotations"]),
        "liu_chars": sum(len(str(row["text"])) for row in entry["liu_annotations"]),
        "jianshu_note_count": len(material["notes"]),
        "jianshu_chars": material["jianshu_chars"],
        "jianshu_mode": material["jianshu_mode"],
        "resolved_notes": [
            {
                "note_id": note["note_id"],
                "local_ref": note["local_ref"],
                "layer": note["layer"],
                "speaker": note["speaker"],
                "source_labels": note["source_labels"],
                "anchor": note["anchor"],
                "source_locator": note["source_locator"],
                "text": note["text"],
                "text_sha256": note["text_sha256"],
                "full_char_count": len(note["text"]),
                "modality": note["modality"],
                "canonicalization_status": note["canonicalization_status"],
            }
            for note in material["notes"]
        ],
        "source_artifacts": material["source_artifacts"],
        "canonical_write_back": False,
    }


def comparison_with_0_2b(root: Path, material: Mapping[str, Any], current: Mapping[str, Any], current_usage: Mapping[str, Any]) -> dict[str, Any]:
    baseline_input = read_json(root, BASELINE_ROOT / "model-input.json")
    baseline_output = read_json(root, BASELINE_ROOT / "model-output.json")
    baseline_usage = read_json(root, BASELINE_ROOT / "usage.json")
    baseline_payload = json.loads(baseline_input["messages"][1]["content"])
    prior_questions = baseline_output.get("normalized_output", {}).get("questions", [])
    current_questions = current.get("reading_questions", [])
    prior_main = str(baseline_payload.get("story_text") or "")
    current_main = str(material["entry"]["story_text"])
    prior_commentary_only = sum(1 for row in prior_questions if isinstance(row, Mapping) and str(row.get("trigger_text") or "") not in prior_main)
    current_commentary_only = sum(1 for row in current_questions if isinstance(row, Mapping) and str(row.get("story_span") or "") not in current_main)
    return {
        "schema": "srm0-2m-comparison-with-0-2b",
        "schema_version": 1,
        "story_id": STORY_ID,
        "prior_stage": "SRM0.2B",
        "current_stage": "SRM0.2M",
        "prior_reading_question_count": len(prior_questions),
        "current_reading_question_count": len(current_questions),
        "prior_questions_triggered_only_by_commentary": prior_commentary_only,
        "current_questions_triggered_only_by_commentary": current_commentary_only,
        "prior_main_text_span_coverage": None,
        "main_text_span_coverage": round((len(current_questions) - current_commentary_only) / len(current_questions), 6) if current_questions else 0,
        "prior_person_connections_count": len(baseline_output.get("normalized_output", {}).get("person_connections", [])),
        "current_person_connections_count": len(current.get("person_connections", [])),
        "prior_appraisals_count": len(baseline_output.get("normalized_output", {}).get("appraisals", [])),
        "current_appraisals_count": len(current.get("appraisals", [])),
        "prior_input_tokens": baseline_usage.get("api_usage", {}).get("prompt_tokens"),
        "current_input_tokens": current_usage.get("prompt_tokens"),
        "prior_output_tokens": baseline_usage.get("api_usage", {}).get("completion_tokens"),
        "current_output_tokens": current_usage.get("completion_tokens"),
        "semantic_score": None,
        "canonical_write_back": False,
    }


def run(args: argparse.Namespace) -> int:
    material = resolve_jianshu_material(ROOT)
    messages = build_messages(material)
    metrics = character_metrics(material, messages)
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
        created_at = "replayed"
        if not run_id:
            raise SystemExit("saved real_model response has no run_id")
    else:
        created_at = utc_now()
        run_id = "srm0-2m-" + material["entry"]["entry_sha256"][:12] + "-" + created_at.replace("-", "").replace(":", "").replace("T", "").replace("Z", "")
    execution_kind = "fixture" if args.fixture else "real_model"

    model_input = {
        "schema": "srm0-2m-model-input",
        "schema_version": 1,
        "stage": "layered_commentary_first_reading",
        "artifact_kind": "generated_layered_input",
        "story_id": STORY_ID,
        "run_id": run_id,
        "execution_kind": execution_kind,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "parameters": {"temperature": 0, "response_format": {"type": "json_object"}, "tools": []},
        "messages": messages,
        "jianshu_mode": material["jianshu_mode"],
        "character_metrics": metrics,
        "canonical_write_back": False,
        "external_search_performed": False,
    }
    write_json(ROOT, OUTPUT_ROOT / "material-resolution.json", material_resolution(material))
    write_json(ROOT, OUTPUT_ROOT / "model-input.json", model_input)

    response: dict[str, Any] | None = None
    raw_content: str | None = None
    repair = "fixture"
    if args.fixture:
        raw = fixture_result(material)
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

    normalized = normalize_layered(raw, material)
    validation_errors = validate_layered(raw, normalized, material)
    repairs = normalization_repairs(raw, normalized)
    model_output = {
        "schema": "srm0-2m-model-output",
        "schema_version": 1,
        "stage": "layered_commentary_first_reading",
        "artifact_kind": "generated_layered_output",
        "story_id": STORY_ID,
        "run_id": run_id,
        "execution_kind": execution_kind,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "json_repair": repair,
        "json_repair_count": 0 if repair in {"none", "fixture"} else 1,
        "raw_response": response or {},
        "raw_content": raw_content,
        "raw_layered_discovery": raw,
        "normalized_output": normalized,
        "normalization_repairs": repairs,
        "validation_errors": validation_errors,
        "api_usage": usage_fields(response),
        "canonical_write_back": False,
        "external_search_performed": False,
    }
    write_json(ROOT, OUTPUT_ROOT / "model-output.json", model_output)
    if validation_errors:
        raise SystemExit("SRM0.2M validation failed: " + "; ".join(validation_errors))

    state = {
        "schema": "srm0-2m-discovery-state",
        "schema_version": 1,
        "story_id": STORY_ID,
        "stage": "layered_first_reading_complete",
        "reading_questions": normalized["reading_questions"],
        "commentary_issues": normalized["commentary_issues"],
        "person_connections": normalized["person_connections"],
        "appraisals": normalized["appraisals"],
        "canonical_write_back": False,
    }
    write_json(ROOT, OUTPUT_ROOT / "discovery-state.json", state)

    usage = {
        "schema": "srm0-2m-usage",
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
        "normalization_repairs": repairs,
        "tool_call_count": 0,
        "external_search_performed": False,
        "canonical_write_back": False,
    }
    write_json(ROOT, OUTPUT_ROOT / "usage.json", usage)
    comparison = comparison_with_0_2b(ROOT, material, normalized, model_output["api_usage"])
    write_json(ROOT, OUTPUT_ROOT / "comparison-with-0.2b.json", comparison)
    if not (ROOT / REVIEW_PATH).is_file():
        write_json(ROOT, REVIEW_PATH, review_template())

    artifact_names = ["material-resolution.json", "model-input.json", "model-output.json", "discovery-state.json", "usage.json", "comparison-with-0.2b.json"]
    manifest = {
        "schema": "srm0-2m-manifest",
        "schema_version": 1,
        "story_id": STORY_ID,
        "run_id": run_id,
        "created_at": created_at,
        "execution_kind": execution_kind,
        "prompt_version": PROMPT_VERSION,
        "source_artifacts": material["source_artifacts"],
        "artifact_hashes": {name: sha256_file(ROOT, OUTPUT_ROOT / name) for name in artifact_names},
        "completion_count": 0 if args.fixture else 1,
        "tool_call_count": 0,
        "external_search_performed": False,
        "canonical_write_back": False,
    }
    write_json(ROOT, OUTPUT_ROOT / "manifest.json", manifest)

    print(f"SRM0.2M completed ({execution_kind})")
    print(f"Jianshu mode: {material['jianshu_mode']} ({material['jianshu_chars']} chars)")
    print(f"reading questions: {len(normalized['reading_questions'])}")
    print(f"commentary issues: {len(normalized['commentary_issues'])}")
    print(f"tokens: {model_output['api_usage'].get('total_tokens')}")
    print(f"output: {(OUTPUT_ROOT / 'model-output.json').as_posix()}")
    print(f"state: {(OUTPUT_ROOT / 'discovery-state.json').as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
