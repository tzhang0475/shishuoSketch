#!/usr/bin/env python3
"""Validate IRR0.2 isolation, structure and deterministic fixture contracts."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

try:
    from irr0_2_common import (
        GOLD_PATH,
        MODEL_SCHEMA_PATH,
        MODES,
        OUTPUT_DIR,
        PILOT_STORY_IDS,
        ROOT,
        REVIEW_PATH,
        SC1_PATH,
        S1_ASSERTIONS_PATH,
        build_pilot_inputs,
        forbidden_input_keys,
        model_input_hash,
        read_json,
        sha256_file,
    )
except ModuleNotFoundError:
    from scripts.irr0_2_common import (
        GOLD_PATH,
        MODEL_SCHEMA_PATH,
        MODES,
        OUTPUT_DIR,
        PILOT_STORY_IDS,
        ROOT,
        REVIEW_PATH,
        SC1_PATH,
        S1_ASSERTIONS_PATH,
        build_pilot_inputs,
        forbidden_input_keys,
        model_input_hash,
        read_json,
        sha256_file,
    )


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []

    def add(message: str) -> None:
        errors.append(message)

    required = [
        OUTPUT_DIR / "manifest.json",
        OUTPUT_DIR / "text-only.json",
        OUTPUT_DIR / "all-at-once.json",
        OUTPUT_DIR / "iterative.json",
        OUTPUT_DIR / "comparison.json",
        OUTPUT_DIR / "per-story-report.json",
    ]
    missing = [path.as_posix() for path in required if not (root / path).is_file()]
    if missing:
        return [f"missing IRR0.2 artifact: {path}" for path in missing]

    manifest = read_json(root, OUTPUT_DIR / "manifest.json")
    documents = {
        "text_only": read_json(root, OUTPUT_DIR / "text-only.json"),
        "all_at_once": read_json(root, OUTPUT_DIR / "all-at-once.json"),
        "iterative": read_json(root, OUTPUT_DIR / "iterative.json"),
    }
    comparison = read_json(root, OUTPUT_DIR / "comparison.json")
    report = read_json(root, OUTPUT_DIR / "per-story-report.json")
    schema = read_json(root, MODEL_SCHEMA_PATH)
    pilots = build_pilot_inputs(root)
    current_input_hashes = {
        SC1_PATH.as_posix(): sha256_file(root, SC1_PATH),
        REVIEW_PATH.as_posix(): sha256_file(root, REVIEW_PATH),
        S1_ASSERTIONS_PATH.as_posix(): sha256_file(root, S1_ASSERTIONS_PATH),
        MODEL_SCHEMA_PATH.as_posix(): sha256_file(root, MODEL_SCHEMA_PATH),
    }

    if manifest.get("schema") != "irr0.2-manifest":
        add("manifest schema is incorrect")
    if manifest.get("stage") != "IRR0.2":
        add("manifest stage is incorrect")
    if manifest.get("scope", {}).get("story_ids") != list(PILOT_STORY_IDS):
        add("manifest pilot Story scope changed")
    if manifest.get("conditions") != list(MODES):
        add("manifest condition order/scope changed")
    if manifest.get("self_hash") is not None:
        add("manifest must not contain a self-referential hash")
    if manifest.get("inference_source_hashes") != current_input_hashes:
        add("manifest inference source hashes are stale")
    if manifest.get("gold_scoring_source", {}).get(GOLD_PATH.as_posix()) != sha256_file(root, GOLD_PATH):
        add("manifest Gold scoring hash is stale")

    for mode, document in documents.items():
        if document.get("schema") != "irr0.2-model-reading-output":
            add(f"{mode} schema is incorrect")
        if document.get("condition") != mode:
            add(f"{mode} condition is incorrect")
        if document.get("scope", {}).get("story_ids") != list(PILOT_STORY_IDS):
            add(f"{mode} Story scope is not the fixed five-Story pilot")
        if document.get("source_hashes") != current_input_hashes:
            add(f"{mode} source hashes are stale")
        record_ids = [str(row.get("story_id")) for row in document.get("records", [])]
        if record_ids != list(PILOT_STORY_IDS):
            add(f"{mode} record order/scope changed: {record_ids}")
        for record in document.get("records", []):
            story_id = str(record.get("story_id"))
            pilot = pilots.get(story_id)
            if not pilot:
                add(f"{mode} unknown Story: {story_id}")
                continue
            rounds = record.get("rounds") if mode == "iterative" else [record]
            if mode == "iterative" and [row.get("round") for row in rounds] != [0, 1, 2]:
                add(f"iterative rounds are not exactly R0/R1/R2: {story_id}")
            for current in rounds:
                payload = current.get("inference_input", {})
                leaked = forbidden_input_keys(payload)
                if leaked:
                    add(f"Gold-only inference fields leaked in {mode}/{story_id}: {leaked}")
                expected_hash = model_input_hash(payload)
                if current.get("input_hash") != expected_hash:
                    add(f"input hash mismatch: {mode}/{story_id}/R{current.get('round', 0)}")
                metadata = current.get("model_metadata", {})
                if metadata.get("input_hash") != expected_hash:
                    add(f"model metadata input hash mismatch: {mode}/{story_id}")
                allowed_ids = {
                    str(item.get("evidence_ref"))
                    for item in payload.get("evidence", [])
                    if isinstance(item, Mapping)
                }
                output = current.get("output", {})
                schema_errors = sorted(
                    Draft202012Validator(schema).iter_errors(output),
                    key=lambda error: list(error.absolute_path),
                )
                if schema_errors:
                    add(f"model output schema error {mode}/{story_id}: {schema_errors[0].message}")
                output_refs = set()
                if isinstance(output, Mapping):
                    # Use the same explicit reference convention as the scorer.
                    def walk(value: Any) -> None:
                        if isinstance(value, Mapping):
                            if isinstance(value.get("evidence_refs"), list):
                                output_refs.update(str(item) for item in value["evidence_refs"])
                            for child in value.values():
                                walk(child)
                        elif isinstance(value, list):
                            for child in value:
                                walk(child)
                    walk(output)
                if output_refs - allowed_ids:
                    add(f"model output cites evidence outside current input: {mode}/{story_id}")
                if mode == "iterative" and int(current.get("round", 0)) == 0 and output.get("reading_delta") is not None:
                    add(f"iterative R0 must not contain a reading_delta: {story_id}")
                if mode == "iterative" and int(current.get("round", 0)) > 0 and output.get("reading_delta") is None:
                    add(f"iterative later round lacks reading_delta: {story_id}")

    expected_artifacts = manifest.get("artifact_hashes_excluding_manifest", {})
    for relative, expected in expected_artifacts.items():
        path = root / relative
        if not path.is_file() or sha256_file(root, Path(relative)) != expected:
            add(f"manifest artifact hash mismatch: {relative}")

    for filename in (
        "manifest.json",
        "text-only.json",
        "all-at-once.json",
        "iterative.json",
        "comparison.json",
        "per-story-report.json",
    ):
        derived = root / OUTPUT_DIR / filename
        public = root / "site/public/generated/irr0-2" / filename
        if not public.is_file() or public.read_bytes() != derived.read_bytes():
            add(f"public IRR0.2 artifact is not byte-identical: {filename}")
    public_gold = root / "site/public/generated/irr0-2/gold.json"
    if not public_gold.is_file() or public_gold.read_bytes() != (root / GOLD_PATH).read_bytes():
        add("public IRR0.2 Gold artifact is not byte-identical to IRR0.1 Gold")

    if comparison.get("scope", {}).get("story_ids") != list(PILOT_STORY_IDS):
        add("comparison Story scope changed")
    if [row.get("story_id") for row in report.get("records", [])] != list(PILOT_STORY_IDS):
        add("per-story report scope/order changed")
    if comparison.get("source_hashes", {}).get(GOLD_PATH.as_posix()) != sha256_file(root, GOLD_PATH):
        add("comparison Gold hash is stale")
    if comparison.get("scientific_status") == "fixture_pipeline_only" and manifest.get("execution", {}).get("real_model_run"):
        add("fixture comparison conflicts with provider manifest")

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
    print("IRR0.2 validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
