#!/usr/bin/env python3
"""Validate the isolated SRM0.1 generated research-memory cycle."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from srm0_1_common import (  # noqa: E402
    EVENT_TYPES,
    MAX_CANDIDATES,
    MAX_MODEL_EVIDENCE_CHARS,
    OUTPUT_ROOT,
    REVIEW_PATH,
    ROOT,
    STORY_ID,
    build_initial_packet,
    build_source_registry,
    input_hash,
    validate_memory_patch,
    validate_question_output,
)


FORBIDDEN_KEYS = {"chain_of_thought", "reasoning_content", "private_reasoning"}


def load(relative: Path) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def validate() -> list[str]:
    errors: list[str] = []
    required = [
        "round-00-input.json",
        "round-00-output.json",
        "round-01-search-trace.json",
        "round-01-model-input.json",
        "round-01-model-output.json",
        "state.json",
        "events.jsonl",
    ]
    for name in required:
        if not (ROOT / OUTPUT_ROOT / name).is_file():
            errors.append(f"missing SRM0.1 artifact: {name}")
    if errors:
        return errors

    packet, _ = build_initial_packet(ROOT, STORY_ID)
    story_text = str(packet["story_text"])
    registry, _ = build_source_registry(ROOT)
    first_input = load(OUTPUT_ROOT / "round-00-input.json")
    first_output = load(OUTPUT_ROOT / "round-00-output.json")
    trace = load(OUTPUT_ROOT / "round-01-search-trace.json")
    second_input = load(OUTPUT_ROOT / "round-01-model-input.json")
    second_output = load(OUTPUT_ROOT / "round-01-model-output.json")
    state = load(OUTPUT_ROOT / "state.json")
    manifest = load(OUTPUT_ROOT / "manifest.json") if (ROOT / OUTPUT_ROOT / "manifest.json").is_file() else {}

    for value, label in ((first_input, "round-00-input"), (first_output, "round-00-output"), (trace, "search-trace"), (second_input, "round-01-input"), (second_output, "round-01-output"), (state, "state")):
        if value.get("story_id") != STORY_ID:
            errors.append(f"{label} has wrong Story identity")
        if value.get("canonical_write_back") is not False:
            errors.append(f"{label} permits canonical write-back")
        serialized = json.dumps(value, ensure_ascii=False).lower()
        for key in FORBIDDEN_KEYS:
            if key in serialized:
                errors.append(f"{label} contains forbidden private reasoning field: {key}")

    question = first_output.get("output", {})
    errors.extend(validate_question_output(question, story_text))
    if first_input.get("input_hash") != input_hash(packet):
        errors.append("Completion 1 input hash does not match the packet")
    if len(question.get("search_probes", [])) > 5:
        errors.append("more than five search probes")

    candidates = trace.get("search_trace", {}).get("model_candidates", [])
    candidate_refs = [row.get("ref") for row in candidates if isinstance(row, dict)]
    if len(candidates) > MAX_CANDIDATES:
        errors.append("more than eight model-facing evidence windows")
    if sum(len(str(row.get("snippet", ""))) for row in candidates) > MAX_MODEL_EVIDENCE_CHARS:
        errors.append("model-facing evidence exceeds 2000 Chinese characters")
    if trace.get("search_trace", {}).get("segmentation_method") != "source_unit_character_window_no_sentence_segmentation":
        errors.append("retrieval is not marked segmentation-free")
    for row in trace.get("search_trace", {}).get("candidates", []):
        ref = row.get("ref")
        if ref not in registry:
            errors.append(f"trace candidate ref does not resolve: {ref}")
            continue
        unit = registry[ref]
        if unit.source_path.startswith("data/generated/") or unit.source_path.startswith("data/annotation/"):
            errors.append(f"generated/model source entered registry: {unit.source_path}")
        text = str(row.get("window_text", ""))
        if text and text not in unit.text:
            errors.append(f"candidate window is not an exact source substring: {ref}")
        snippet = row.get("model_snippet")
        if snippet and snippet not in text:
            errors.append(f"model snippet is not an exact candidate substring: {ref}")
    for row in candidates:
        if row.get("ref") not in registry:
            errors.append(f"model candidate ref does not resolve: {row.get('ref')}")

    patch = second_output.get("output", {})
    errors.extend(validate_memory_patch(patch, candidate_refs, story_text))
    if len([row for row in patch.get("evidence_decisions", []) if row.get("decision") == "keep"]) > 3:
        errors.append("more than three evidence refs kept")

    events_path = ROOT / OUTPUT_ROOT / "events.jsonl"
    events = []
    for line_number, line in enumerate(events_path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid events.jsonl line {line_number}: {exc}")
            continue
        events.append(event)
        if event.get("event_type") not in EVENT_TYPES:
            errors.append(f"unknown event type: {event.get('event_type')}")
        if event.get("story_id") != STORY_ID:
            errors.append("event has wrong Story identity")
    sequences = [event.get("sequence") for event in events]
    if sequences != list(range(1, len(events) + 1)):
        errors.append("events are not append-ordered")
    if len({event.get("event_id") for event in events}) != len(events):
        errors.append("event IDs are not unique")

    usage_fields = {"prompt_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens", "total_tokens"}
    for output, label in ((first_output, "Completion 1"), (second_output, "Completion 2")):
        if not usage_fields.issubset(output.get("api_usage", {})):
            errors.append(f"{label} lacks API usage accounting fields")
    for packet_value, label in ((first_input, "Completion 1"), (second_input, "Completion 2")):
        metrics = packet_value.get("metrics", {})
        for field in ("raw_input_chars", "model_input_chars", "compression_ratio", "raw_retrieval_chars", "model_evidence_chars"):
            if field not in metrics:
                errors.append(f"{label} lacks compression metric {field}")

    if not (ROOT / REVIEW_PATH).is_file():
        errors.append("missing manual SRM0.1 review template")
    else:
        review = load(REVIEW_PATH)
        records = review.get("records", [])
        if not any(row.get("story_id") == STORY_ID and row.get("decision") == "pending" for row in records if isinstance(row, dict)):
            errors.append("review template does not contain pending pilot record")
    if state.get("research_status") != "next_question_pending_not_executed":
        errors.append("SRM0.1 state does not stop with a pending next question")
    if manifest.get("next_question_executed") is not False:
        errors.append("manifest does not explicitly confirm that Q2 was not executed")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("SRM0.1 validation failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("SRM0.1 validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
