#!/usr/bin/env python3
"""Run the IRR0.2 model re-reading conditions.

The default is a deterministic fixture because a model provider is an
environment concern.  A real provider can be injected with
IRR0_2_PROVIDER_MODULE; its ``run_reading(payload)`` function receives only a
sanitized Story/evidence payload.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
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
        PUBLIC_OUTPUT_DIR,
        ROOT,
        REVIEW_PATH,
        SC1_PATH,
        S1_ASSERTIONS_PATH,
        build_pilot_inputs,
        context_refs_for_condition,
        execution_timestamp,
        forbidden_input_keys,
        inference_input,
        model_input_hash,
        provider_from_environment,
        read_json,
        run_reading,
        sha256_file,
        stable_json,
        write_json,
    )
except ModuleNotFoundError:  # imported as scripts.run_irr0_2 by tests
    from scripts.irr0_2_common import (
        GOLD_PATH,
        MODEL_SCHEMA_PATH,
        MODES,
        OUTPUT_DIR,
        PILOT_STORY_IDS,
        PUBLIC_OUTPUT_DIR,
        ROOT,
        REVIEW_PATH,
        SC1_PATH,
        S1_ASSERTIONS_PATH,
        build_pilot_inputs,
        context_refs_for_condition,
        execution_timestamp,
        forbidden_input_keys,
        inference_input,
        model_input_hash,
        provider_from_environment,
        read_json,
        run_reading,
        sha256_file,
        stable_json,
        write_json,
    )


def output_path(mode: str) -> Path:
    return {
        "text_only": OUTPUT_DIR / "text-only.json",
        "all_at_once": OUTPUT_DIR / "all-at-once.json",
        "iterative": OUTPUT_DIR / "iterative.json",
    }[mode]


def public_output_path(mode: str) -> Path:
    return PUBLIC_OUTPUT_DIR / output_path(mode).name


def provider_metadata(provider: Any, timestamp: str, input_hash: str) -> dict[str, Any]:
    return {
        "provider": str(provider.provider),
        "model": str(provider.model),
        "parameters": {
            "temperature": 0,
            "prompt_version": "irr0.2-v0",
        },
        "created_at": timestamp,
        "input_hash": input_hash,
    }


def validate_model_output(root: Path, output: Mapping[str, Any]) -> None:
    schema = read_json(root, MODEL_SCHEMA_PATH)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(output),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        locations = ", ".join(
            f"/{'/'.join(str(part) for part in error.absolute_path)}: {error.message}"
            for error in errors[:3]
        )
        raise ValueError(f"model output does not match IRR0.2 schema: {locations}")


def build_mode_document(
    root: Path,
    pilots: Mapping[str, Mapping[str, Any]],
    mode: str,
    story_ids: list[str],
    provider: Any,
    timestamp: str,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for story_id in story_ids:
        pilot = pilots[story_id]
        if mode == "iterative":
            rounds: list[dict[str, Any]] = []
            previous: Mapping[str, Any] | None = None
            for round_number in range(len(pilot["iterative_round_refs"])):
                refs = context_refs_for_condition(pilot, mode, round_number)
                payload = inference_input(pilot, refs, previous)
                forbidden = forbidden_input_keys(payload)
                if forbidden:
                    raise ValueError(f"Gold-only fields leaked into model input: {forbidden}")
                input_hash = model_input_hash(payload)
                raw_output = run_reading(
                    pilot["story"],
                    payload["evidence"],
                    payload.get("previous_reading"),
                    mode,
                    provider,
                    round_number,
                )
                output = copy.deepcopy(dict(raw_output))
                validate_model_output(root, output)
                added_refs = sorted(
                    set(refs)
                    - set(context_refs_for_condition(pilot, mode, max(0, round_number - 1)))
                )
                rounds.append(
                    {
                        "round": round_number,
                        "evidence_added": [
                            copy.deepcopy(pilot["evidence_catalog"][ref]) for ref in added_refs
                        ],
                        "inference_input": payload,
                        "input_hash": input_hash,
                        "model_metadata": provider_metadata(provider, timestamp, input_hash),
                        "output": output,
                    }
                )
                previous = output
            records.append({"story_id": story_id, "condition": mode, "rounds": rounds})
        else:
            refs = context_refs_for_condition(pilot, mode)
            payload = inference_input(pilot, refs)
            forbidden = forbidden_input_keys(payload)
            if forbidden:
                raise ValueError(f"Gold-only fields leaked into model input: {forbidden}")
            input_hash = model_input_hash(payload)
            output = copy.deepcopy(
                dict(run_reading(pilot["story"], payload["evidence"], None, mode, provider, 0))
            )
            validate_model_output(root, output)
            records.append(
                {
                    "story_id": story_id,
                    "condition": mode,
                    "inference_input": payload,
                    "input_hash": input_hash,
                    "model_metadata": provider_metadata(provider, timestamp, input_hash),
                    "output": output,
                }
            )
    return {
        "schema": "irr0.2-model-reading-output",
        "stage": "IRR0.2",
        "schema_version": "v0",
        "condition": mode,
        "execution": {
            "execution_kind": "fixture" if provider.provider == "fixture" else "provider",
            "real_model_run": provider.provider != "fixture",
            "provider": provider.provider,
            "model": provider.model,
            "created_at": timestamp,
        },
        "scope": {
            "story_count": len(story_ids),
            "story_ids": story_ids,
            "rounds_per_story": 3 if mode == "iterative" else 1,
        },
        "input_contract": {
            "gold_used_for_scoring_only": True,
            "forbidden_gold_keys": sorted(
                [
                    "gold",
                    "expected_role",
                    "gain_vector",
                    "critical_spans",
                    "target_depth",
                    "reviewed_phrase",
                    "human_annotation",
                    "grounding",
                    "evidence_index",
                    "distraction_flags",
                    "delta_annotations",
                    "review_status",
                    "selection_reason",
                    "annotation",
                ]
            ),
        },
        "source_hashes": {
            SC1_PATH.as_posix(): sha256_file(root, SC1_PATH),
            REVIEW_PATH.as_posix(): sha256_file(root, REVIEW_PATH),
            S1_ASSERTIONS_PATH.as_posix(): sha256_file(root, S1_ASSERTIONS_PATH),
            MODEL_SCHEMA_PATH.as_posix(): sha256_file(root, MODEL_SCHEMA_PATH),
        },
        "records": records,
    }


def build_manifest(root: Path, documents: Mapping[str, Mapping[str, Any]], provider: Any, timestamp: str) -> dict[str, Any]:
    artifact_hashes: dict[str, str] = {}
    for mode, document in documents.items():
        path = root / output_path(mode)
        write_json(root, output_path(mode), document)
        artifact_hashes[output_path(mode).as_posix()] = sha256_file(root, output_path(mode))
    return {
        "schema": "irr0.2-manifest",
        "stage": "IRR0.2",
        "schema_version": "v0",
        "execution": {
            "execution_kind": "fixture" if provider.provider == "fixture" else "provider",
            "real_model_run": provider.provider != "fixture",
            "provider": provider.provider,
            "model": provider.model,
            "created_at": timestamp,
        },
        "scope": {"story_count": len(PILOT_STORY_IDS), "story_ids": list(PILOT_STORY_IDS)},
        "conditions": list(documents),
        "gold_scoring_source": {
            GOLD_PATH.as_posix(): sha256_file(root, GOLD_PATH),
        },
        "inference_source_hashes": {
            SC1_PATH.as_posix(): sha256_file(root, SC1_PATH),
            REVIEW_PATH.as_posix(): sha256_file(root, REVIEW_PATH),
            S1_ASSERTIONS_PATH.as_posix(): sha256_file(root, S1_ASSERTIONS_PATH),
            MODEL_SCHEMA_PATH.as_posix(): sha256_file(root, MODEL_SCHEMA_PATH),
        },
        "forbidden_gold_keys": sorted(
            [
                "gold",
                "expected_role",
                "gain_vector",
                "critical_spans",
                "target_depth",
                "reviewed_phrase",
                "human_annotation",
                "grounding",
                "evidence_index",
                "distraction_flags",
                "delta_annotations",
                "review_status",
                "selection_reason",
                "annotation",
            ]
        ),
        "artifact_hashes_excluding_manifest": artifact_hashes,
        "self_hash": None,
    }


def copy_public_artifacts(root: Path, documents: Mapping[str, Mapping[str, Any]], manifest: Mapping[str, Any]) -> None:
    for mode, document in documents.items():
        write_json(root, public_output_path(mode), document)
    write_json(root, PUBLIC_OUTPUT_DIR / "manifest.json", manifest)
    write_json(root, PUBLIC_OUTPUT_DIR / "gold.json", read_json(root, GOLD_PATH))


def run_experiment(
    root: Path = ROOT,
    mode: str = "all",
    story_id: str | None = None,
    fixture: bool = False,
    provider_module: str | None = None,
    model: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    if mode != "all" and mode not in MODES:
        raise ValueError(f"invalid IRR0.2 mode: {mode}")
    if story_id is not None and story_id not in PILOT_STORY_IDS:
        raise ValueError(f"Story is outside the frozen IRR0.1 pilot: {story_id}")
    story_ids = [story_id] if story_id else list(PILOT_STORY_IDS)
    provider = provider_from_environment(fixture=fixture, provider_module=provider_module, model=model)
    created_at = execution_timestamp("fixture" if provider.provider == "fixture" else "provider", timestamp)
    pilots = build_pilot_inputs(root)
    modes = list(MODES) if mode == "all" else [mode]
    generated_documents = {
        current: build_mode_document(root, pilots, current, story_ids, provider, created_at)
        for current in modes
    }
    documents: dict[str, Mapping[str, Any]] = {}
    for current in MODES:
        existing_path = root / output_path(current)
        if current in generated_documents:
            current_document = dict(generated_documents[current])
            if story_id and existing_path.is_file():
                existing = read_json(root, output_path(current))
                existing_records = {
                    str(row["story_id"]): row
                    for row in existing.get("records", [])
                    if isinstance(row, Mapping) and row.get("story_id")
                }
                for row in current_document.get("records", []):
                    existing_records[str(row["story_id"])] = row
                current_document["records"] = [
                    existing_records[current_story]
                    for current_story in PILOT_STORY_IDS
                    if current_story in existing_records
                ]
                current_document["scope"] = {
                    "story_count": len(current_document["records"]),
                    "story_ids": [row["story_id"] for row in current_document["records"]],
                    "rounds_per_story": 3 if current == "iterative" else 1,
                }
            documents[current] = current_document
        elif existing_path.is_file():
            documents[current] = read_json(root, output_path(current))
    if len(documents) != len(MODES):
        # A partial run in a fresh checkout is still useful for provider
        # debugging, but the full validator correctly requires all conditions.
        documents = generated_documents
    manifest = build_manifest(root, documents, provider, created_at)
    write_json(root, OUTPUT_DIR / "manifest.json", manifest)
    copy_public_artifacts(root, documents, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("all", *MODES), default="all")
    parser.add_argument("--story", choices=PILOT_STORY_IDS)
    parser.add_argument("--fixture", action="store_true", help="use the deterministic non-scientific fixture provider")
    parser.add_argument("--provider-module", help="module exposing run_reading(payload)")
    parser.add_argument("--model", help="provider model label recorded in artifacts")
    parser.add_argument("--timestamp", help="explicit run timestamp; fixture defaults to a stable value")
    args = parser.parse_args()
    manifest = run_experiment(
        mode=args.mode,
        story_id=args.story,
        fixture=args.fixture,
        provider_module=args.provider_module,
        model=args.model,
        timestamp=args.timestamp,
    )
    print(stable_json({"manifest": "data/derived/irr0-2/manifest.json", "execution": manifest["execution"]}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
