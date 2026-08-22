#!/usr/bin/env python3
"""Validate the isolated SRM0.3B semantic-delta experiment."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ds1_common import ROOT, sha256_file  # noqa: E402
from srm0_3b_common import (  # noqa: E402
    OUTPUT_ROOT,
    REVIEW_PATH,
    STORY_ID,
    build_commentary_messages,
    build_commentary_payload,
    build_initial_messages,
    build_initial_payload,
    derive_events,
    derive_state,
    normalize_initial,
    normalize_semantic_delta,
    resolve_commentary_material,
    validate_initial,
    validate_semantic_delta,
)
from run_srm0_3b import build_comparison  # noqa: E402


REVIEW_VALUES = {None, "good", "mixed", "poor", "not_applicable"}


def load(relative: Path) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _document_errors(document: Mapping[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    if document.get("story_id") != STORY_ID:
        errors.append(f"{label} has wrong Story identity")
    if document.get("canonical_write_back") is not False:
        errors.append(f"{label} permits canonical write-back")
    if document.get("external_search_performed") is not False:
        errors.append(f"{label} marks external search")
    return errors


def validate() -> list[str]:
    errors: list[str] = []
    required = [
        "round-00-main-input.json",
        "round-00-main-output.json",
        "round-01-commentary-input.json",
        "round-01-commentary-output.json",
        "research-state.json",
        "events.jsonl",
        "comparison-with-0.3a.json",
        "usage.json",
        "manifest.json",
    ]
    missing = [name for name in required if not (ROOT / OUTPUT_ROOT / name).is_file()]
    if missing:
        return [f"missing SRM0.3B artifact: {name}" for name in missing]
    if not (ROOT / REVIEW_PATH).is_file():
        errors.append("missing SRM0.3B review template")

    material = resolve_commentary_material(ROOT)
    main_input = load(OUTPUT_ROOT / "round-00-main-input.json")
    main_output = load(OUTPUT_ROOT / "round-00-main-output.json")
    commentary_input = load(OUTPUT_ROOT / "round-01-commentary-input.json")
    commentary_output = load(OUTPUT_ROOT / "round-01-commentary-output.json")
    state = load(OUTPUT_ROOT / "research-state.json")
    comparison = load(OUTPUT_ROOT / "comparison-with-0.3a.json")
    usage = load(OUTPUT_ROOT / "usage.json")
    manifest = load(OUTPUT_ROOT / "manifest.json")

    for document, label in (
        (main_input, "main input"),
        (main_output, "main output"),
        (commentary_input, "commentary input"),
        (commentary_output, "commentary output"),
        (state, "research state"),
        (comparison, "comparison"),
        (usage, "usage"),
        (manifest, "manifest"),
    ):
        errors.extend(_document_errors(document, label))

    execution_kind = manifest.get("execution_kind")
    if execution_kind not in {"fixture", "real_model", "replay"}:
        errors.append("manifest has invalid execution_kind")
    expected_completion_count = 0 if execution_kind in {"fixture", "replay"} else 2
    if manifest.get("completion_count") != expected_completion_count:
        errors.append("manifest completion count is invalid")
    if manifest.get("tool_call_count") != 0:
        errors.append("SRM0.3B used tool calls")
    if manifest.get("artifact_hashes", {}).get("manifest.json") is not None:
        errors.append("manifest contains a self-hash")

    if len(material.get("early_notes", [])) != 10:
        errors.append("canonical Liu annotation count is not ten")
    if any(note.get("layer") == "liu_annotation" for note in material.get("later_notes", [])):
        errors.append("duplicate Liu-derived Jianshu note leaked into later commentary")
    if len(material.get("later_notes", [])) + len(material.get("duplicate_notes", [])) != material.get("all_note_count"):
        errors.append("commentary layer partition is not deterministic")
    if not material.get("later_notes") or not material.get("duplicate_notes"):
        errors.append("commentary layer partition lacks both later and duplicate material")

    main_messages = main_input.get("messages")
    if main_messages != build_initial_messages(material):
        errors.append("Completion 1 messages are not deterministic")
    main_payload: dict[str, Any] = {}
    try:
        main_payload = json.loads(main_messages[1]["content"])
    except (TypeError, KeyError, IndexError, json.JSONDecodeError):
        errors.append("Completion 1 payload is not JSON")
    if main_payload != build_initial_payload(material):
        errors.append("Completion 1 payload is not main-text-only")
    if set(main_payload) != {"story_id", "primary_text"}:
        errors.append("Completion 1 payload contains extra fields")
    if isinstance(main_payload.get("primary_text"), Mapping) and set(main_payload["primary_text"]) != {"label", "text"}:
        errors.append("Completion 1 primary text has extra fields")
    serialized_main = json.dumps(main_payload, ensure_ascii=False).lower()
    for forbidden in ("liu", "笺疏", "jian", "person", "relation", "prior", "why_unclear", "historical"):
        if forbidden in serialized_main:
            errors.append(f"Completion 1 payload contains forbidden context: {forbidden}")
    if main_input.get("parameters", {}).get("tools") != []:
        errors.append("Completion 1 has tools")

    main_raw = main_output.get("raw_output") if isinstance(main_output.get("raw_output"), Mapping) else {}
    main_normalized = main_output.get("normalized_output") if isinstance(main_output.get("normalized_output"), Mapping) else {}
    errors.extend(validate_initial(main_raw, main_normalized, material))
    if main_output.get("validation_errors") != []:
        errors.append("Completion 1 recorded validation errors")
    if len(main_normalized.get("gaps", [])) != len(main_raw.get("gaps", [])):
        errors.append("Completion 1 normalization dropped a gap")

    frozen_questions = [
        {"question_id": row.get("question_id"), "gap": row.get("gap")}
        for row in main_normalized.get("gaps", [])
        if isinstance(row, Mapping)
    ]
    commentary_messages = commentary_input.get("messages")
    if commentary_messages != build_commentary_messages(material, frozen_questions):
        errors.append("Completion 2 messages are not deterministic")
    commentary_payload: dict[str, Any] = {}
    try:
        commentary_payload = json.loads(commentary_messages[1]["content"])
    except (TypeError, KeyError, IndexError, json.JSONDecodeError):
        errors.append("Completion 2 payload is not JSON")
    if commentary_payload != build_commentary_payload(material, frozen_questions):
        errors.append("Completion 2 payload is not deterministic")
    if any(set(row) != {"question_id", "gap"} for row in commentary_payload.get("frozen_questions", []) if isinstance(row, Mapping)):
        errors.append("Completion 2 received immutable explanation or span fields")
    if any("why" in json.dumps(row, ensure_ascii=False).lower() for row in commentary_payload.get("frozen_questions", [])):
        errors.append("Completion 1 explanation leaked into Completion 2")
    sent_refs = {
        note.get("ref")
        for group in (commentary_payload.get("early_commentary", {}), commentary_payload.get("later_commentary", {}))
        for note in group.get("notes", [])
        if isinstance(note, Mapping)
    }
    expected_refs = {note["ref"] for note in material["early_notes"] + material["later_notes"]}
    if sent_refs != expected_refs:
        errors.append("Completion 2 commentary refs are incomplete or extra")
    if any(note.get("ref") in sent_refs for note in material["duplicate_notes"]):
        errors.append("Completion 2 received duplicate Liu-derived Jianshu refs")
    if commentary_input.get("parameters", {}).get("tools") != []:
        errors.append("Completion 2 has tools")

    delta_raw = commentary_output.get("raw_output") if isinstance(commentary_output.get("raw_output"), Mapping) else {}
    delta_normalized = commentary_output.get("normalized_output") if isinstance(commentary_output.get("normalized_output"), Mapping) else {}
    errors.extend(validate_semantic_delta(delta_raw, delta_normalized, material, main_normalized))
    if commentary_output.get("validation_errors") != []:
        errors.append("Completion 2 recorded validation errors")

    if state.get("stage") == "commentary_resolution_failed":
        recorded = state.get("validation_errors", [])
        errors.extend(f"run failed closed: {error}" for error in recorded)
        return sorted(set(errors))

    expected_state = derive_state(main_normalized, delta_normalized)
    if state != expected_state:
        errors.append("research-state is not a deterministic Python projection")
    if "quote" in json.dumps(state, ensure_ascii=False) or "evidence_quote" in json.dumps(state, ensure_ascii=False):
        errors.append("research-state copied source quotations")

    expected_events = derive_events(main_normalized, delta_normalized, state)
    try:
        actual_events = [json.loads(line) for line in (ROOT / OUTPUT_ROOT / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    except json.JSONDecodeError:
        actual_events = []
        errors.append("events.jsonl contains invalid JSON")
    if actual_events != expected_events:
        errors.append("events.jsonl is not deterministic")
    if any(term in json.dumps(actual_events, ensure_ascii=False).lower() for term in ("chain_of_thought", "思维链", "hidden_reasoning")):
        errors.append("events contain hidden reasoning")

    expected_comparison = build_comparison(main_output, commentary_output, usage)
    if comparison != expected_comparison:
        errors.append("comparison-with-0.3a is not deterministic")

    char_metrics = usage.get("character_metrics", {})
    required_metric_keys = {
        "main_text_chars", "liu_chars", "later_commentary_chars", "duplicate_commentary_chars_removed",
        "completion_1_instruction_chars", "completion_2_instruction_chars",
        "completion_1_payload_chars", "completion_2_payload_chars",
        "completion_1_serialized_prompt_chars", "completion_2_serialized_prompt_chars",
    }
    if not required_metric_keys.issubset(char_metrics):
        errors.append("usage character metrics are incomplete")
    for field in ("completion_1_api_usage", "completion_2_api_usage"):
        if field not in usage:
            errors.append(f"usage missing {field}")
    if usage.get("normalization_count") is None or usage.get("json_repair_count") is None:
        errors.append("usage normalization/repair accounting is incomplete")
    if usage.get("tool_call_count") != 0:
        errors.append("usage records tool calls")

    artifact_names = [
        "round-00-main-input.json", "round-00-main-output.json",
        "round-01-commentary-input.json", "round-01-commentary-output.json",
        "research-state.json", "events.jsonl", "comparison-with-0.3a.json", "usage.json",
    ]
    artifact_hashes = manifest.get("artifact_hashes", {})
    for name in artifact_names:
        if artifact_hashes.get(name) != sha256_file(ROOT, OUTPUT_ROOT / name):
            errors.append(f"manifest hash mismatch: {name}")
    if "manifest.json" in artifact_hashes:
        errors.append("manifest self-reference is forbidden")

    review = load(REVIEW_PATH) if (ROOT / REVIEW_PATH).is_file() else {}
    for field, value in review.items():
        if field not in {"schema", "schema_version", "story_id", "notes"} and value not in REVIEW_VALUES:
            errors.append(f"invalid review value: {field}")
    if review.get("story_id") != STORY_ID:
        errors.append("review template has wrong Story identity")
    return sorted(set(errors))


def main() -> int:
    errors = validate()
    if errors:
        print("SRM0.3B validation failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("SRM0.3B validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
