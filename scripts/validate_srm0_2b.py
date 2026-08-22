#!/usr/bin/env python3
"""Validate the isolated SRM0.2B blind discovery packet and output."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ds1_common import ROOT, sha256_file  # noqa: E402
from srm0_2b_common import (  # noqa: E402
    ENTRY_PATH,
    OUTPUT_ROOT,
    REVIEW_PATH,
    STORY_ID,
    build_messages,
    load_entry,
    model_payload,
    normalize_discovery,
    stable_json,
    validate_discovery,
)


REVIEW_VALUES = {None, "good", "mixed", "poor", "not_applicable"}


def load(relative: Path) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def validate() -> list[str]:
    errors: list[str] = []
    required = ["model-input.json", "model-output.json", "discovery-state.json", "usage.json", "manifest.json"]
    for name in required:
        if not (ROOT / OUTPUT_ROOT / name).is_file():
            errors.append(f"missing SRM0.2B artifact: {name}")
    if errors:
        return errors

    entry = load_entry(ROOT)
    model_input = load(OUTPUT_ROOT / "model-input.json")
    model_output = load(OUTPUT_ROOT / "model-output.json")
    state = load(OUTPUT_ROOT / "discovery-state.json")
    usage = load(OUTPUT_ROOT / "usage.json")
    manifest = load(OUTPUT_ROOT / "manifest.json")

    for value, label in ((model_input, "model-input"), (model_output, "model-output"), (state, "state"), (usage, "usage"), (manifest, "manifest")):
        if value.get("story_id") != STORY_ID:
            errors.append(f"{label} has wrong Story identity")
        if value.get("canonical_write_back") is not False:
            errors.append(f"{label} permits canonical write-back")

    if model_input.get("parameters", {}).get("tools") != []:
        errors.append("model input exposes tools")
    messages = model_input.get("messages")
    if not isinstance(messages, list) or messages != build_messages(entry):
        errors.append("model input messages do not match the clean canonical Story/Liu packet")
    else:
        try:
            payload = json.loads(messages[1]["content"])
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            payload = {}
            errors.append(f"model payload is not JSON: {exc}")
        if payload != model_payload(entry):
            errors.append("model payload differs from the canonical Story/Liu packet")
        serialized = json.dumps(payload, ensure_ascii=False).lower()
        for forbidden in (
            "source_sha256",
            "source_path",
            "evidence_ref",
            "review_status",
            "publication_scope",
            "relation",
            "person_id",
            "era",
            "historical_fact",
            "search_probe",
            "active_question",
        ):
            if forbidden in serialized:
                errors.append(f"forbidden metadata leaked into model payload: {forbidden}")
        if "data/generated" in serialized or "data/annotation" in serialized:
            errors.append("generated or annotation path leaked into model payload")

    raw_response = model_output.get("raw_response")
    if not isinstance(raw_response, dict):
        errors.append("raw provider response is not preserved as an object")
    raw = model_output.get("raw_discovery")
    if not isinstance(raw, dict):
        errors.append("parsed raw discovery result is not preserved as an object")
    normalized = model_output.get("normalized_output")
    if not isinstance(normalized, dict):
        errors.append("normalized discovery output is missing")
        normalized = {}
    raw_content = model_output.get("raw_content")
    if model_output.get("execution_kind") == "real_model" and (not isinstance(raw_content, str) or not raw_content.strip()):
        errors.append("real-model output does not preserve raw JSON content")
    raw_value = raw if isinstance(raw, dict) else {}
    expected_normalized = normalize_discovery(raw_value, entry)
    errors.extend(validate_discovery(raw_value, normalized, entry))
    if normalized != expected_normalized:
        errors.append("normalized discovery output is not the deterministic boundary normalization")
    if model_output.get("validation_errors") != []:
        errors.append("model-output records validation errors")
    if model_output.get("search_performed") is not False:
        errors.append("model-output marks search as performed")

    expected_state_keys = {"schema", "schema_version", "story_id", "stage", "questions", "person_connections", "appraisals", "canonical_write_back"}
    if set(state) != expected_state_keys:
        errors.append("discovery-state contains research-memory or extra fields")
    if state.get("stage") != "blind_discovery_complete":
        errors.append("discovery-state has wrong stage")
    if {key: state.get(key) for key in ("questions", "person_connections", "appraisals")} != normalized:
        errors.append("discovery-state does not equal normalized discovery output")
    for forbidden in ("active_question", "claims", "reading_links", "search_results", "next_question"):
        if forbidden in state:
            errors.append(f"discovery-state contains forbidden research field: {forbidden}")

    api_usage = usage.get("api_usage", {})
    for field in ("prompt_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens", "total_tokens"):
        if field not in api_usage:
            errors.append(f"missing API usage field: {field}")
    metrics = usage.get("character_metrics", {})
    for field in ("story_chars", "liu_annotation_chars", "instruction_chars", "serialized_payload_chars"):
        if field not in metrics:
            errors.append(f"missing character metric: {field}")
    if usage.get("tool_call_count") != 0 or usage.get("search_performed") is not False:
        errors.append("usage does not prove zero retrieval/tool calls")
    if model_output.get("json_repair_count") not in {0, 1}:
        errors.append("invalid JSON repair count")

    if manifest.get("source_entry") != ENTRY_PATH.as_posix() or manifest.get("source_entry_sha256") != entry["entry_sha256"]:
        errors.append("manifest source entry provenance does not match the locked local entry")
    if manifest.get("completion_count") not in {0, 1} or manifest.get("tool_call_count") != 0 or manifest.get("search_performed") is not False:
        errors.append("manifest run boundary is invalid")
    artifact_hashes = manifest.get("artifact_hashes", {})
    for name in ("model-input.json", "model-output.json", "discovery-state.json", "usage.json"):
        if artifact_hashes.get(name) != sha256_file(ROOT, OUTPUT_ROOT / name):
            errors.append(f"artifact hash mismatch: {name}")

    if not (ROOT / REVIEW_PATH).is_file():
        errors.append("missing SRM0.2B manual review artifact")
    else:
        review = load(REVIEW_PATH)
        if review.get("story_id") != STORY_ID:
            errors.append("review artifact has wrong Story identity")
        for field in (
            "question_naturalness",
            "question_text_grounding",
            "question_research_value",
            "person_connection_discovery",
            "appraisal_discovery",
            "overinterpretation",
            "restraint",
            "token_efficiency",
        ):
            if field not in review or review[field] not in REVIEW_VALUES:
                errors.append(f"invalid review field: {field}")

    return sorted(set(errors))


def main() -> int:
    errors = validate()
    if errors:
        print("SRM0.2B validation failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("SRM0.2B validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
