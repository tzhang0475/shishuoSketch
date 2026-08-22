#!/usr/bin/env python3
"""Validate the isolated SRM0.2M layered-commentary experiment."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ds1_common import ROOT, sha256_file  # noqa: E402
from run_srm0_2m import comparison_with_0_2b, material_resolution  # noqa: E402
from srm0_2m_common import (  # noqa: E402
    ENTRY_PATH,
    OUTPUT_ROOT,
    REVIEW_PATH,
    STORY_ID,
    build_messages,
    build_model_payload,
    load_entry,
    normalize_layered,
    resolve_jianshu_material,
    validate_layered,
)


REVIEW_VALUES = {None, "good", "mixed", "poor", "not_applicable"}


def load(relative: Path) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def validate() -> list[str]:
    errors: list[str] = []
    required = [
        "material-resolution.json",
        "model-input.json",
        "model-output.json",
        "discovery-state.json",
        "usage.json",
        "manifest.json",
        "comparison-with-0.2b.json",
    ]
    for name in required:
        if not (ROOT / OUTPUT_ROOT / name).is_file():
            errors.append(f"missing SRM0.2M artifact: {name}")
    if errors:
        return errors

    material = resolve_jianshu_material(ROOT)
    entry = material["entry"]
    model_input = load(OUTPUT_ROOT / "model-input.json")
    model_output = load(OUTPUT_ROOT / "model-output.json")
    state = load(OUTPUT_ROOT / "discovery-state.json")
    usage = load(OUTPUT_ROOT / "usage.json")
    manifest = load(OUTPUT_ROOT / "manifest.json")
    resolution = load(OUTPUT_ROOT / "material-resolution.json")
    comparison = load(OUTPUT_ROOT / "comparison-with-0.2b.json")

    for value, label in ((model_input, "model-input"), (model_output, "model-output"), (state, "state"), (usage, "usage"), (manifest, "manifest"), (resolution, "material-resolution"), (comparison, "comparison")):
        if value.get("story_id") != STORY_ID:
            errors.append(f"{label} has wrong Story identity")
        if value.get("canonical_write_back") is not False:
            errors.append(f"{label} permits canonical write-back")

    if resolution != material_resolution(material):
        errors.append("material resolution is not deterministic")
    if material["jianshu_mode"] != "full" or material["jianshu_chars"] > 2500:
        errors.append("resolved Jianshu mode/length policy is incorrect")
    if len(material["entry"]["liu_annotations"]) != 10:
        errors.append("canonical Liu annotation count changed")
    if len(material["notes"]) == 0:
        errors.append("no local Jianshu notes were resolved")

    messages = model_input.get("messages")
    if not isinstance(messages, list) or messages != build_messages(material):
        errors.append("model messages do not match the layered Story/Liu/Jianshu packet")
    else:
        try:
            payload = json.loads(messages[1]["content"])
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            payload = {}
            errors.append(f"layered model payload is not JSON: {exc}")
        if payload != build_model_payload(material):
            errors.append("model payload differs from deterministic layered packet")
        serialized = json.dumps(payload, ensure_ascii=False).lower()
        for forbidden in ("source_sha256", "source_path", "person_id", "personstory", "relation_graph", "era_card", "historical_fact", "prior_srm", "search_rank", "retrieval_score"):
            if forbidden in serialized:
                errors.append(f"forbidden metadata leaked into layered model payload: {forbidden}")
        if "data/generated" in serialized or "data/annotation" in serialized:
            errors.append("generated/annotation path leaked into layered model payload")
    if model_input.get("parameters", {}).get("tools") != [] or model_input.get("external_search_performed") is not False:
        errors.append("model input violates no-tools/no-search boundary")

    raw = model_output.get("raw_layered_discovery")
    normalized = model_output.get("normalized_output")
    if not isinstance(raw, dict) or not isinstance(normalized, dict):
        errors.append("raw/normalized layered output is missing")
        raw = raw if isinstance(raw, dict) else {}
        normalized = normalized if isinstance(normalized, dict) else {}
    errors.extend(validate_layered(raw, normalized, material))
    expected_normalized = normalize_layered(raw, material)
    if normalized != expected_normalized:
        errors.append("normalized layered output is not deterministic")
    if model_output.get("validation_errors") != []:
        errors.append("model output records validation errors")
    if model_output.get("external_search_performed") is not False:
        errors.append("model output marks external search")
    if model_output.get("execution_kind") == "real_model" and not str(model_output.get("raw_content") or "").strip():
        errors.append("real model output does not preserve raw JSON content")

    expected_state_keys = {"schema", "schema_version", "story_id", "stage", "reading_questions", "commentary_issues", "person_connections", "appraisals", "canonical_write_back"}
    if set(state) != expected_state_keys:
        errors.append("state contains fields outside layered first-reading output")
    if state.get("stage") != "layered_first_reading_complete":
        errors.append("state has wrong stage")
    if {key: state.get(key) for key in ("reading_questions", "commentary_issues", "person_connections", "appraisals")} != normalized:
        errors.append("state does not equal normalized layered result")
    for forbidden in ("active_question", "search_probes", "search_results", "claims", "reading_links"):
        if forbidden in state:
            errors.append(f"state contains forbidden research field: {forbidden}")

    api_usage = usage.get("api_usage", {})
    for field in ("prompt_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens", "total_tokens"):
        if field not in api_usage:
            errors.append(f"missing API usage field: {field}")
    metrics = usage.get("character_metrics", {})
    for field in ("main_text_chars", "liu_chars", "jianshu_full_available_chars", "jianshu_model_chars", "instruction_chars", "serialized_payload_chars"):
        if field not in metrics:
            errors.append(f"missing layered character metric: {field}")
    if usage.get("tool_call_count") != 0 or usage.get("external_search_performed") is not False:
        errors.append("usage violates zero retrieval boundary")

    expected_comparison = comparison_with_0_2b(ROOT, material, normalized, api_usage)
    if comparison != expected_comparison:
        errors.append("comparison artifact is not deterministic Python output")

    if manifest.get("source_artifacts") != material["source_artifacts"]:
        errors.append("manifest source artifacts changed")
    if manifest.get("completion_count") not in {0, 1} or manifest.get("tool_call_count") != 0 or manifest.get("external_search_performed") is not False:
        errors.append("manifest violates run boundary")
    artifact_names = ["material-resolution.json", "model-input.json", "model-output.json", "discovery-state.json", "usage.json", "comparison-with-0.2b.json"]
    for name in artifact_names:
        if manifest.get("artifact_hashes", {}).get(name) != sha256_file(ROOT, OUTPUT_ROOT / name):
            errors.append(f"artifact hash mismatch: {name}")

    if not (ROOT / REVIEW_PATH).is_file():
        errors.append("missing manual review artifact")
    else:
        review = load(REVIEW_PATH)
        if review.get("story_id") != STORY_ID:
            errors.append("review artifact has wrong Story identity")
        for field in (
            "main_text_centrality",
            "reading_question_quality",
            "liu_usage",
            "jianshu_usage",
            "commentary_issue_separation",
            "person_connection_precision",
            "appraisal_precision",
            "overinterpretation",
            "token_efficiency",
        ):
            if field not in review or review[field] not in REVIEW_VALUES:
                errors.append(f"invalid review field: {field}")
    return sorted(set(errors))


def main() -> int:
    errors = validate()
    if errors:
        print("SRM0.2M validation failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("SRM0.2M validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
