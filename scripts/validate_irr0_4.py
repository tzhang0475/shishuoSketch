#!/usr/bin/env python3
"""Validate IRR0.4 semantic-ladder isolation, branching and artifacts."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

try:
    from irr0_4_common import (
        CONDITIONS,
        HUMAN_REVIEW_PATH,
        HUMAN_SCHEMA_PATH,
        IRR04_STORY_IDS,
        MODEL_SCHEMA_PATH,
        OUTPUT_DIR,
        PUBLIC_OUTPUT_DIR,
        ROOT,
        SEMANTIC_REVIEW_PATH,
        build_irr0_4_inputs,
        forbidden_input_keys,
        load_semantic_review,
        model_input_hash,
        output_path,
        read_json,
        source_hashes,
        validate_model_output,
    )
except ModuleNotFoundError:
    from scripts.irr0_4_common import (
        CONDITIONS,
        HUMAN_REVIEW_PATH,
        HUMAN_SCHEMA_PATH,
        IRR04_STORY_IDS,
        MODEL_SCHEMA_PATH,
        OUTPUT_DIR,
        PUBLIC_OUTPUT_DIR,
        ROOT,
        SEMANTIC_REVIEW_PATH,
        build_irr0_4_inputs,
        forbidden_input_keys,
        load_semantic_review,
        model_input_hash,
        output_path,
        read_json,
        source_hashes,
        validate_model_output,
    )


REQUIRED_OUTPUTS = (
    "manifest.json",
    "semantic-ladders.json",
    "memory-vs-fresh.json",
    "negative-controls.json",
    "span-trajectories.json",
    "human-review-template.json",
    "summary.json",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _walk(value: Any) -> list[Any]:
    if isinstance(value, Mapping):
        return [value, *[child for item in value.values() for child in _walk(item)]]
    if isinstance(value, list):
        return [child for item in value for child in _walk(item)]
    return []


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []

    def add(message: str) -> None:
        errors.append(message)

    missing = [name for name in REQUIRED_OUTPUTS if not (root / OUTPUT_DIR / name).is_file()]
    if missing:
        return [f"missing IRR0.4 artifact: {name}" for name in missing]

    inputs = build_irr0_4_inputs(root)
    review = load_semantic_review(root)
    current_hashes = source_hashes(root)
    document = read_json(root, output_path())
    manifest = read_json(root, OUTPUT_DIR / "manifest.json")
    if document.get("schema") != "irr0.4-semantic-ladders":
        add("semantic-ladders schema is incorrect")
    if document.get("scope", {}).get("story_ids") != list(IRR04_STORY_IDS):
        add("semantic-ladders scope changed")
    if document.get("source_hashes") != current_hashes:
        add("semantic-ladders source hashes are stale")
    if manifest.get("schema") != "irr0.4-manifest":
        add("manifest schema is incorrect")
    if manifest.get("scope", {}).get("story_ids") != list(IRR04_STORY_IDS):
        add("manifest scope changed")
    if manifest.get("conditions") != list(CONDITIONS):
        add("manifest condition order changed")
    if manifest.get("source_hashes") != current_hashes:
        add("manifest source hashes are stale")
    if manifest.get("self_hash") is not None:
        add("manifest must not contain a self-reference")
    if review.get("scope", {}).get("story_ids") != list(IRR04_STORY_IDS):
        add("semantic review scope changed")

    execution_types = {document.get("execution", {}).get("run_type")}
    if execution_types not in ({"fixture"}, {"real_model"}):
        add("semantic-ladders execution type is invalid")

    records = document.get("records", [])
    if [row.get("story_id") for row in records] != list(IRR04_STORY_IDS):
        add("semantic-ladders record order changed")
    for story_id in IRR04_STORY_IDS:
        record = next((row for row in records if row.get("story_id") == story_id), None)
        pilot = inputs[story_id]
        if record is None:
            add(f"semantic-ladders record missing: {story_id}")
            continue
        if record.get("critical_spans") != pilot["critical_spans"]:
            add(f"critical span set changed: {story_id}")
        rounds = record.get("rounds", [])
        if [row.get("round") for row in rounds] != [0, 1, 2, 3]:
            add(f"round sequence changed: {story_id}")
        for round_record, round_spec in zip(rounds, pilot["rounds"]):
            if round_record.get("semantic_stage") != round_spec["semantic_stage"]:
                add(f"semantic stage changed: {story_id}/R{round_record.get('round')}")
            if round_record.get("evidence_bundle") != round_spec["evidence_bundle"]:
                add(f"evidence bundle changed: {story_id}/R{round_record.get('round')}")
            if round_record.get("evidence_refs") != round_spec["evidence_refs"]:
                add(f"cumulative evidence changed: {story_id}/R{round_record.get('round')}")
            if round_record.get("gold", {}).get("target_spans") != round_spec["gold_target_spans"]:
                add(f"Gold target span changed: {story_id}/R{round_record.get('round')}")
            for condition in CONDITIONS:
                envelope = round_record.get(f"{condition}_reading", {})
                payload = envelope.get("inference_input", {})
                expected_previous = condition == "memory" and int(round_record["round"]) > 0
                if forbidden_input_keys(payload):
                    add(f"Gold/review field leaked into input: {story_id}/R{round_record['round']}/{condition}")
                serialized_input = str(payload)
                if "gold_expected_effect" in serialized_input or "gold_target_spans" in serialized_input:
                    add(f"semantic Gold leaked into input: {story_id}/R{round_record['round']}/{condition}")
                if ("previous_reading" in payload) != expected_previous:
                    add(f"memory/fresh previous-reading contract failed: {story_id}/R{round_record['round']}/{condition}")
                if payload.get("semantic_stage") != round_spec["semantic_stage"] or payload.get("driving_question") != round_spec["driving_question"]:
                    add(f"semantic prompt metadata mismatch: {story_id}/R{round_record['round']}/{condition}")
                if payload.get("round") != f"R{round_record['round']}" or payload.get("branch") != "main" or payload.get("condition") != condition:
                    add(f"semantic branch metadata mismatch: {story_id}/R{round_record['round']}/{condition}")
                allowed = {
                    str(item.get("evidence_ref"))
                    for item in payload.get("evidence", [])
                    if isinstance(item, Mapping)
                }
                if allowed != set(round_spec["evidence_refs"]):
                    add(f"semantic evidence input mismatch: {story_id}/R{round_record['round']}/{condition}")
                if envelope.get("input_hash") != model_input_hash(payload):
                    add(f"semantic input hash mismatch: {story_id}/R{round_record['round']}/{condition}")
                try:
                    validate_model_output(root, envelope.get("output", {}))
                except ValueError as exc:
                    add(f"{story_id}/R{round_record['round']}/{condition}: {exc}")
                output_refs = {
                    str(ref)
                    for node in _walk(envelope.get("output", {}))
                    if isinstance(node, Mapping)
                    for ref in node.get("supporting_evidence_ids", [])
                    if isinstance(node.get("supporting_evidence_ids"), list)
                }
                if output_refs - allowed:
                    add(f"model cites evidence outside input: {story_id}/R{round_record['round']}/{condition}")
                metadata = envelope.get("model_metadata", {})
                for field in ("provider", "model", "parameters", "run_id", "run_type", "input_hash", "condition", "branch", "round"):
                    if field not in metadata:
                        add(f"model metadata lacks {field}: {story_id}/R{round_record['round']}/{condition}")
                if metadata.get("input_hash") != envelope.get("input_hash"):
                    add(f"model metadata hash mismatch: {story_id}/R{round_record['round']}/{condition}")

        negative = record.get("negative_control", {})
        negative_spec = pilot["negative_control"]
        if negative.get("evidence_bundle") != negative_spec["evidence_bundle"]:
            add(f"negative evidence bundle changed: {story_id}")
        for condition in CONDITIONS:
            envelope = negative.get(f"{condition}_reading", {})
            payload = envelope.get("inference_input", {})
            if ("previous_reading" in payload) != (condition == "memory"):
                add(f"negative memory/fresh contract failed: {story_id}/{condition}")
            if payload.get("branch") != "negative_control" or payload.get("round") != negative_spec["round_label"]:
                add(f"negative branch metadata mismatch: {story_id}/{condition}")
            allowed = {
                str(item.get("evidence_ref"))
                for item in payload.get("evidence", [])
                if isinstance(item, Mapping)
            }
            if allowed != set(negative_spec["evidence_refs"]):
                add(f"negative evidence input mismatch: {story_id}/{condition}")
            if envelope.get("input_hash") != model_input_hash(payload):
                add(f"negative input hash mismatch: {story_id}/{condition}")
            try:
                validate_model_output(root, envelope.get("output", {}))
            except ValueError as exc:
                add(f"{story_id}/negative/{condition}: {exc}")

    try:
        human_schema = read_json(root, HUMAN_SCHEMA_PATH)
        human = read_json(root, HUMAN_REVIEW_PATH)
        schema_errors = list(Draft202012Validator(human_schema).iter_errors(human))
        if schema_errors:
            add(f"human review schema error: {schema_errors[0].message}")
        if human.get("scope", {}).get("story_ids") != list(IRR04_STORY_IDS):
            add("human review scope changed")
        allowed_keys = {
            (story_id, branch, round_label, condition)
            for story_id in IRR04_STORY_IDS
            for branch, labels in (
                ("main", ("R1", "R2", "R3")),
                ("negative_control", ("1N",)),
            )
            for round_label in labels
            for condition in CONDITIONS
        }
        for row in human.get("records", []):
            key = (
                str(row.get("story_id")),
                str(row.get("branch")),
                str(row.get("round_label")),
                str(row.get("condition")),
            )
            if key not in allowed_keys:
                add(f"human review key is outside IRR0.4 transitions: {key}")
    except (OSError, ValueError, KeyError) as exc:
        add(f"human review cannot be read: {exc}")

    for name in REQUIRED_OUTPUTS:
        derived = root / OUTPUT_DIR / name
        public = root / PUBLIC_OUTPUT_DIR / name
        if not public.is_file() or public.read_bytes() != derived.read_bytes():
            add(f"public artifact is not byte-identical: {name}")
    for relative, expected in manifest.get("artifact_hashes_excluding_manifest", {}).items():
        path = root / relative
        if not path.is_file() or sha256(path) != expected:
            add(f"manifest artifact hash mismatch: {relative}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = validate(args.root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("IRR0.4 validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
