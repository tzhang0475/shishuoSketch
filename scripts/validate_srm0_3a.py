#!/usr/bin/env python3
"""Validate the isolated SRM0.3A two-completion experiment."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ds1_common import ROOT, sha256_file  # noqa: E402
from srm0_3a_common import (  # noqa: E402
    OUTPUT_ROOT,
    REVIEW_PATH,
    STORY_ID,
    build_commentary_messages,
    build_commentary_payload,
    build_initial_messages,
    build_initial_payload,
    normalize_commentary,
    normalize_initial,
    project_events,
    project_state,
    resolve_commentary_material,
    source_text,
    validate_commentary,
    validate_initial,
)


REVIEW_VALUES = {None, "good", "mixed", "poor", "not_applicable"}


def load(path: Path) -> Any:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def validate() -> list[str]:
    errors: list[str] = []
    required = [
        "round-00-main-input.json",
        "round-00-main-output.json",
        "round-01-commentary-input.json",
        "round-01-commentary-output.json",
        "research-state.json",
        "events.jsonl",
        "usage.json",
        "manifest.json",
    ]
    missing = [name for name in required if not (ROOT / OUTPUT_ROOT / name).is_file()]
    if missing:
        return [f"missing SRM0.3A artifact: {name}" for name in missing]

    material = resolve_commentary_material(ROOT)
    main_input = load(OUTPUT_ROOT / "round-00-main-input.json")
    main_output = load(OUTPUT_ROOT / "round-00-main-output.json")
    commentary_input = load(OUTPUT_ROOT / "round-01-commentary-input.json")
    commentary_output = load(OUTPUT_ROOT / "round-01-commentary-output.json")
    state = load(OUTPUT_ROOT / "research-state.json")
    usage = load(OUTPUT_ROOT / "usage.json")
    manifest = load(OUTPUT_ROOT / "manifest.json")

    for document, label in (
        (main_input, "main input"),
        (main_output, "main output"),
        (commentary_input, "commentary input"),
        (commentary_output, "commentary output"),
        (state, "research state"),
        (usage, "usage"),
        (manifest, "manifest"),
    ):
        if document.get("story_id") != STORY_ID:
            errors.append(f"{label} has wrong Story identity")
        if document.get("canonical_write_back") is not False:
            errors.append(f"{label} permits canonical write-back")
        if "external_search_performed" in document and document.get("external_search_performed") is not False:
            errors.append(f"{label} marks external search")

    if state.get("stage") == "commentary_resolution_failed":
        recorded = state.get("validation_errors", [])
        return ["the two-completion run did not satisfy the semantic output contract"] + [f"model contract: {error}" for error in recorded]

    if len(material["early_notes"]) != 10:
        errors.append("canonical Liu annotation count is not ten")
    if any(note.get("layer") == "liu_annotation" for note in material["later_notes"]):
        errors.append("duplicate Liu-layer Jianshu note leaked into later commentary")
    if len(material["later_notes"]) + len(material["duplicate_notes"]) != material.get("all_note_count"):
        errors.append("commentary layer partition is not structurally valid")
    if not material["later_notes"] or not material["duplicate_notes"]:
        errors.append("later commentary does not resolve the expected non-Liu local blocks")
    if material["duplicate_commentary_chars_removed"] <= 0:
        errors.append("duplicate Liu commentary was not removed")

    main_messages = main_input.get("messages")
    if main_messages != build_initial_messages(material):
        errors.append("Completion 1 messages are not deterministic")
    try:
        main_payload = json.loads(main_messages[1]["content"])
    except (TypeError, KeyError, IndexError, json.JSONDecodeError):
        main_payload = {}
        errors.append("Completion 1 payload is not JSON")
    if main_payload != build_initial_payload(material):
        errors.append("Completion 1 payload is not main-text-only")
    serialized_main = json.dumps(main_payload, ensure_ascii=False).lower()
    for forbidden in ("liu", "笺疏", "jian", "person", "relation", "prior", "why_unclear"):
        if forbidden in serialized_main:
            errors.append(f"Completion 1 payload contains forbidden context: {forbidden}")
    if main_input.get("parameters", {}).get("tools") != []:
        errors.append("Completion 1 has tools")

    main_raw = main_output.get("raw_output")
    main_normalized = main_output.get("normalized_output")
    if not isinstance(main_raw, dict) or not isinstance(main_normalized, dict):
        errors.append("Completion 1 raw/normalized output missing")
        main_raw = main_raw if isinstance(main_raw, dict) else {}
        main_normalized = main_normalized if isinstance(main_normalized, dict) else {}
    errors.extend(validate_initial(main_raw, main_normalized, material))
    if main_output.get("validation_errors") != []:
        errors.append("Completion 1 recorded validation errors")

    question_packet = [
        {"question_id": row.get("question_id"), "story_span": row.get("story_span"), "question": row.get("question")}
        for row in main_normalized.get("questions", []) if isinstance(row, dict)
    ]
    commentary_messages = commentary_input.get("messages")
    if commentary_messages != build_commentary_messages(material, question_packet):
        errors.append("Completion 2 messages are not deterministic")
    try:
        commentary_payload = json.loads(commentary_messages[1]["content"])
    except (TypeError, KeyError, IndexError, json.JSONDecodeError):
        commentary_payload = {}
        errors.append("Completion 2 payload is not JSON")
    if commentary_payload != build_commentary_payload(material, question_packet):
        errors.append("Completion 2 payload is not deterministic")
    serialized_questions = json.dumps(commentary_payload.get("questions", []), ensure_ascii=False)
    if "why_unclear_from_main_text" in serialized_questions or "why_unclear" in serialized_questions:
        errors.append("Completion 1 self-explanation leaked into Completion 2")
    sent_refs = {note.get("ref") for note in commentary_payload.get("early_commentary", {}).get("notes", [])}
    sent_refs.update(note.get("ref") for note in commentary_payload.get("later_commentary", {}).get("notes", []))
    if sent_refs != {note["ref"] for note in material["early_notes"] + material["later_notes"]}:
        errors.append("Completion 2 commentary ref set is incorrect")
    if any(ref in sent_refs for ref in {note["ref"] for note in material["duplicate_notes"]}):
        errors.append("Completion 2 received duplicate Liu-derived Jianshu refs")

    commentary_raw = commentary_output.get("raw_output")
    commentary_normalized = commentary_output.get("normalized_output")
    if not isinstance(commentary_raw, dict) or not isinstance(commentary_normalized, dict):
        errors.append("Completion 2 raw/normalized output missing")
        commentary_raw = commentary_raw if isinstance(commentary_raw, dict) else {}
        commentary_normalized = commentary_normalized if isinstance(commentary_normalized, dict) else {}
    errors.extend(validate_commentary(commentary_raw, commentary_normalized, material, main_normalized))
    if commentary_output.get("validation_errors") != []:
        errors.append("Completion 2 recorded validation errors")

    expected_state = project_state(main_normalized, commentary_normalized)
    if state != expected_state:
        errors.append("research-state is not deterministic Python projection")
    state_text = json.dumps(state, ensure_ascii=False)
    if "quote" in state_text or "evidence_quote" in state_text:
        errors.append("research-state copied source quotations")
    expected_events = project_events(main_normalized, commentary_normalized)
    actual_event_lines = (ROOT / OUTPUT_ROOT / "events.jsonl").read_text(encoding="utf-8").splitlines()
    try:
        actual_events = [json.loads(line) for line in actual_event_lines if line.strip()]
    except json.JSONDecodeError:
        actual_events = []
        errors.append("events.jsonl contains invalid JSON")
    if actual_events != expected_events:
        errors.append("events.jsonl is not deterministic Python projection")
    if any("chain" in line.lower() or "reasoning" in line.lower() for line in actual_event_lines):
        errors.append("events.jsonl contains hidden reasoning fields")

    for field in ("completion_1_api_usage", "completion_2_api_usage"):
        if field not in usage:
            errors.append(f"missing usage field: {field}")
        else:
            for usage_field in ("prompt_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens", "total_tokens"):
                if usage_field not in usage[field]:
                    errors.append(f"missing {field}.{usage_field}")
    for metric in ("main_text_chars", "liu_chars", "later_commentary_chars", "duplicate_commentary_chars_removed"):
        if metric not in usage.get("character_metrics", {}):
            errors.append(f"missing character metric: {metric}")
    if usage.get("tool_call_count") != 0:
        errors.append("usage has tool calls")

    artifact_names = [
        "round-00-main-input.json",
        "round-00-main-output.json",
        "round-01-commentary-input.json",
        "round-01-commentary-output.json",
        "research-state.json",
        "events.jsonl",
        "usage.json",
    ]
    for name in artifact_names:
        if manifest.get("artifact_hashes", {}).get(name) != sha256_file(ROOT, OUTPUT_ROOT / name):
            errors.append(f"manifest hash mismatch: {name}")
    if manifest.get("completion_count") not in {0, 2} or manifest.get("tool_call_count") != 0:
        errors.append("manifest violates exactly-two-completion/no-tool boundary")
    if manifest.get("source_artifacts") != material["source_artifacts"]:
        errors.append("manifest source artifacts changed")

    if not (ROOT / REVIEW_PATH).is_file():
        errors.append("missing manual review artifact")
    else:
        review = load(REVIEW_PATH)
        if review.get("story_id") != STORY_ID:
            errors.append("review artifact has wrong Story identity")
        for field in (
            "initial_question_quality",
            "commentary_consumption",
            "working_answer_precision",
            "sufficiency_judgment",
            "remaining_gap_quality",
            "refined_question_quality",
            "stop_restraint",
            "relation_precision",
            "appraisal_precision",
            "self_reinforcement_control",
            "token_efficiency",
        ):
            if field not in review or review[field] not in REVIEW_VALUES:
                errors.append(f"invalid review field: {field}")
    return sorted(set(errors))


def main() -> int:
    errors = validate()
    if errors:
        print("SRM0.3A validation failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("SRM0.3A validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
