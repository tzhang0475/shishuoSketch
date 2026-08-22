#!/usr/bin/env python3
"""Validate the isolated SRM0.1R retest and its frozen inputs."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ds1_common import ROOT  # noqa: E402
from srm0_1r_common import (  # noqa: E402
    ORIGINAL_ROOT,
    REVIEW_PATH,
    RETEST_ROOT,
    STORY_ID,
    build_model_payload,
    load_frozen_inputs,
    validate_semantic_result,
)


EVENT_TYPES = {
    "question_resolution",
    "evidence_kept",
    "seen_not_selected",
    "reading_link_added",
    "static_relation_candidate_added",
    "appraisal_candidate_added",
    "question_candidate_added",
    "association_deprioritized",
}
REVIEW_VALUES = {None, "good", "mixed", "poor", "not_applicable"}


def load(relative: Path) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def validate() -> list[str]:
    errors: list[str] = []
    required = ["model-input.json", "model-output.json", "state.json", "events.jsonl", "usage.json", "manifest.json"]
    for name in required:
        if not (ROOT / RETEST_ROOT / name).is_file():
            errors.append(f"missing SRM0.1R artifact: {name}")
    if errors:
        return errors

    frozen = load_frozen_inputs(ROOT)
    frozen_refs = [row["ref"] for row in frozen["candidates"]]
    model_input = load(RETEST_ROOT / "model-input.json")
    model_output = load(RETEST_ROOT / "model-output.json")
    state = load(RETEST_ROOT / "state.json")
    usage = load(RETEST_ROOT / "usage.json")
    manifest = load(RETEST_ROOT / "manifest.json")

    for value, label in ((model_input, "model-input"), (model_output, "model-output"), (state, "state"), (usage, "usage"), (manifest, "manifest")):
        if value.get("story_id") != STORY_ID:
            errors.append(f"{label} has wrong Story identity")
        if value.get("canonical_write_back") is not False:
            errors.append(f"{label} permits canonical write-back")

    if model_input.get("frozen_candidate_hash") != frozen["candidate_hash"]:
        errors.append("frozen candidate hash changed")
    if manifest.get("frozen_candidate_hash") != frozen["candidate_hash"]:
        errors.append("manifest frozen candidate hash changed")
    if manifest.get("retest_of") != ORIGINAL_ROOT.as_posix() or manifest.get("retrieval_rerun") is not False:
        errors.append("retest boundary is not preserved")
    if manifest.get("candidate_subquestion_executed") is not False:
        errors.append("candidate subquestion was executed")

    messages = model_input.get("messages", [])
    if not isinstance(messages, list) or len(messages) != 2:
        errors.append("model input must contain exactly system and user messages")
    else:
        try:
            payload = json.loads(messages[1]["content"])
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            payload = {}
            errors.append(f"model user payload is not JSON: {exc}")
        expected_payload = build_model_payload(frozen)
        if payload != expected_payload:
            errors.append("model payload differs from frozen Story/Q1/evidence packet")
        serialized = json.dumps(payload, ensure_ascii=False).lower()
        for forbidden in ("source_path", "source_sha256", "retrieval_score", "audit", "person_research", "full_provenance"):
            if forbidden in serialized:
                errors.append(f"audit/provenance field leaked into model payload: {forbidden}")

    normalized = model_output.get("normalized_output", {})
    errors.extend(validate_semantic_result(normalized, str(frozen["story_text"]), frozen_refs))
    if "claim_updates" in normalized or "evidence_decisions" in normalized:
        errors.append("old database-style memory fields leaked into SRM0.1R output")
    for row in normalized.get("useful_evidence", []):
        if row.get("ref") not in frozen_refs:
            errors.append("useful evidence ref is outside the frozen eight")
    if len(normalized.get("useful_evidence", [])) > 4:
        errors.append("more than four useful evidence items")

    state_refs = state.get("seen_evidence_refs", [])
    if state_refs != frozen_refs:
        errors.append("state seen_evidence_refs does not preserve all eight frozen candidates")
    unselected_expected = [ref for ref in frozen_refs if ref not in {row.get("ref") for row in normalized.get("useful_evidence", [])}]
    if state.get("seen_not_selected_refs") != unselected_expected:
        errors.append("state seen_not_selected_refs does not match useful evidence selection")
    if state.get("research_status") != "retest_complete_next_question_not_executed":
        errors.append("state does not stop after the retest")

    events = []
    for line_number, line in enumerate((ROOT / RETEST_ROOT / "events.jsonl").read_text(encoding="utf-8").splitlines(), start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid events line {line_number}: {exc}")
            continue
        events.append(event)
        if event.get("event_type") not in EVENT_TYPES:
            errors.append(f"invalid SRM0.1R event type: {event.get('event_type')}")
        if event.get("story_id") != STORY_ID:
            errors.append("event has wrong Story identity")
    if [event.get("sequence") for event in events] != list(range(1, len(events) + 1)):
        errors.append("events are not sequential")
    if len({event.get("event_id") for event in events}) != len(events):
        errors.append("event IDs are not unique")
    selected = {row.get("ref") for row in normalized.get("useful_evidence", [])}
    for event in events:
        if event.get("event_type") == "evidence_kept" and event.get("evidence_ref") not in selected:
            errors.append("evidence_kept event is not in useful_evidence")
        if event.get("event_type") == "seen_not_selected" and event.get("evidence_ref") in selected:
            errors.append("seen_not_selected event is selected as useful evidence")

    api_usage = usage.get("api_usage", {})
    for field in ("prompt_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens", "total_tokens"):
        if field not in api_usage:
            errors.append(f"missing API usage field: {field}")
    metrics = usage.get("character_metrics", {})
    for field in ("source_material_chars", "projected_payload_chars", "instruction_chars", "serialized_prompt_chars", "compression_ratio"):
        if field not in metrics:
            errors.append(f"missing character metric: {field}")
    if api_usage.get("completion_tokens") is not None and api_usage["completion_tokens"] < 0:
        errors.append("invalid completion token count")

    if not (ROOT / REVIEW_PATH).is_file():
        errors.append("missing SRM0.1R review template")
    else:
        review = load(REVIEW_PATH)
        record = next((row for row in review.get("records", []) if row.get("story_id") == STORY_ID), None)
        if record is None:
            errors.append("review template lacks the pilot Story")
        else:
            for key in ("evidence_consumption", "question_resolution", "reading_link_quality", "next_question_restraint", "temporal_reasoning", "static_relation_extraction", "appraisal_extraction", "token_efficiency"):
                if key not in record or record[key] not in REVIEW_VALUES:
                    errors.append(f"invalid review field: {key}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("SRM0.1R validation failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("SRM0.1R validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
