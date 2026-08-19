#!/usr/bin/env python3
"""Run IRR0.3 under identical text-only, all-at-once and iterative inputs."""

from __future__ import annotations

import argparse
import copy
import hashlib
from pathlib import Path
from typing import Any, Mapping

try:
    from irr0_3_common import (
        CONTEXT_REVIEW_PATH,
        MODES,
        OUTPUT_DIR,
        PILOT_STORY_IDS,
        PUBLIC_OUTPUT_DIR,
        ROOT,
        added_refs_for_round,
        build_irr0_3_inputs,
        context_refs_for_round,
        execution_run_id,
        execution_timestamp,
        forbidden_input_keys,
        inference_input,
        metadata,
        model_input_hash,
        output_filename,
        output_path,
        provider_from_environment,
        read_json,
        source_hashes,
        stable_json,
        validate_model_output,
        validate_span_transition,
        write_json,
    )
except ModuleNotFoundError:  # imported as scripts.run_irr0_3 by tests
    from scripts.irr0_3_common import (
        CONTEXT_REVIEW_PATH,
        MODES,
        OUTPUT_DIR,
        PILOT_STORY_IDS,
        PUBLIC_OUTPUT_DIR,
        ROOT,
        added_refs_for_round,
        build_irr0_3_inputs,
        context_refs_for_round,
        execution_run_id,
        execution_timestamp,
        forbidden_input_keys,
        inference_input,
        metadata,
        model_input_hash,
        output_filename,
        output_path,
        provider_from_environment,
        read_json,
        source_hashes,
        stable_json,
        validate_model_output,
        validate_span_transition,
        write_json,
    )


def build_execution(provider: Any, run_type: str, run_id: str, created_at: str) -> dict[str, Any]:
    return {
        "run_type": run_type,
        "execution_kind": "fixture" if run_type == "fixture" else "provider",
        "real_model_run": run_type == "real_model",
        "provider": str(provider.provider),
        "model": str(provider.model),
        "run_id": run_id,
        "created_at": created_at,
        "parameters": {"temperature": 0, "prompt_version": "irr0.3-v0"},
    }


def build_mode_document(
    root: Path,
    pilots: Mapping[str, Mapping[str, Any]],
    mode: str,
    story_ids: list[str],
    provider: Any,
    execution: Mapping[str, Any],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for story_id in story_ids:
        pilot = pilots[story_id]
        if mode == "iterative":
            rounds: list[dict[str, Any]] = []
            previous_output: Mapping[str, Any] | None = None
            for round_number in range(len(pilot["iterative_rounds"])):
                refs = context_refs_for_round(pilot, round_number)
                added_refs = added_refs_for_round(pilot, round_number)
                payload = inference_input(pilot, refs, previous_output)
                leaked = forbidden_input_keys(payload)
                if leaked:
                    raise ValueError(f"Gold/review fields leaked into IRR0.3 input: {leaked}")
                input_hash = model_input_hash(payload)
                result = provider.generate(
                    pilot["story"],
                    payload["evidence"],
                    payload.get("previous_reading"),
                    mode,
                    round_number,
                    added_refs,
                    bool(set(added_refs) & set(pilot["hard_negative_refs"])),
                )
                output = copy.deepcopy(dict(result["output"]))
                validate_model_output(root, output)
                transition = None
                if round_number > 0:
                    transition = {
                        "evidence_ids": sorted(added_refs),
                        "affected_spans": copy.deepcopy(result.get("affected_spans", [])),
                    }
                    validate_span_transition(transition)
                rounds.append(
                    {
                        "round": round_number,
                        "evidence_added": [
                            copy.deepcopy(pilot["evidence_catalog"][ref])
                            for ref in added_refs
                        ],
                        "inference_input": payload,
                        "input_hash": input_hash,
                        "model_metadata": metadata(
                            provider,
                            str(execution["run_type"]),
                            str(execution["run_id"]),
                            str(execution["created_at"]),
                            input_hash,
                        ),
                        "output": output,
                        "transition": transition,
                    }
                )
                previous_output = output
            records.append({"story_id": story_id, "condition": mode, "rounds": rounds})
        else:
            refs = [] if mode == "text_only" else list(pilot["context_refs"])
            payload = inference_input(pilot, refs)
            leaked = forbidden_input_keys(payload)
            if leaked:
                raise ValueError(f"Gold/review fields leaked into IRR0.3 input: {leaked}")
            input_hash = model_input_hash(payload)
            result = provider.generate(
                pilot["story"],
                payload["evidence"],
                None,
                mode,
                0,
                [],
                False,
            )
            output = copy.deepcopy(dict(result["output"]))
            validate_model_output(root, output)
            records.append(
                {
                    "story_id": story_id,
                    "condition": mode,
                    "inference_input": payload,
                    "input_hash": input_hash,
                    "model_metadata": metadata(
                        provider,
                        str(execution["run_type"]),
                        str(execution["run_id"]),
                        str(execution["created_at"]),
                        input_hash,
                    ),
                    "output": output,
                }
            )
    return {
        "schema": "irr0.3-model-reading-output",
        "stage": "IRR0.3",
        "schema_version": "v0",
        "condition": mode,
        "execution": copy.deepcopy(dict(execution)),
        "scope": {"story_count": len(story_ids), "story_ids": list(story_ids)},
        "input_contract": {
            "gold_used_for_scoring_only": True,
            "review_roles_used_for_fixture_control_only": True,
            "forbidden_inference_keys": sorted(
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
                    "continue_reading",
                    "unsupported_interpretation",
                ]
            ),
        },
        "source_hashes": source_hashes(root),
        "records": records,
    }


def merge_story_document(
    root: Path,
    mode: str,
    document: dict[str, Any],
    story_id: str | None,
) -> dict[str, Any]:
    if not story_id:
        return document
    path = root / output_path(mode)
    if not path.is_file():
        return document
    existing = read_json(root, output_path(mode))
    existing_rows = {
        str(row["story_id"]): row
        for row in existing.get("records", [])
        if isinstance(row, Mapping) and row.get("story_id")
    }
    for row in document.get("records", []):
        existing_rows[str(row["story_id"])] = row
    document["records"] = [
        existing_rows[current]
        for current in PILOT_STORY_IDS
        if current in existing_rows
    ]
    document["scope"] = {
        "story_count": len(document["records"]),
        "story_ids": [row["story_id"] for row in document["records"]],
    }
    return document


def write_manifest(
    root: Path,
    documents: Mapping[str, Mapping[str, Any]],
    execution: Mapping[str, Any],
) -> dict[str, Any]:
    artifact_hashes: dict[str, str] = {}
    for mode, document in documents.items():
        write_json(root, output_path(mode), document)
        artifact_hashes[output_path(mode).as_posix()] = hashlib.sha256(
            (root / output_path(mode)).read_bytes()
        ).hexdigest()
    manifest = {
        "schema": "irr0.3-manifest",
        "stage": "IRR0.3",
        "schema_version": "v0",
        "execution": copy.deepcopy(dict(execution)),
        "scope": {"story_count": len(PILOT_STORY_IDS), "story_ids": list(PILOT_STORY_IDS)},
        "conditions": list(MODES),
        "context_review_source": {
            CONTEXT_REVIEW_PATH.as_posix(): hashlib.sha256(
                (root / CONTEXT_REVIEW_PATH).read_bytes()
            ).hexdigest()
        },
        "source_hashes": source_hashes(root),
        "artifact_hashes_excluding_manifest": artifact_hashes,
        "self_hash": None,
    }
    write_json(root, OUTPUT_DIR / "manifest.json", manifest)
    return manifest


def copy_public(root: Path, documents: Mapping[str, Mapping[str, Any]], manifest: Mapping[str, Any]) -> None:
    for mode, document in documents.items():
        write_json(root, PUBLIC_OUTPUT_DIR / output_filename(mode), document)
    write_json(root, PUBLIC_OUTPUT_DIR / "manifest.json", manifest)


def run_experiment(
    root: Path = ROOT,
    mode: str = "all",
    story_id: str | None = None,
    fixture: bool = False,
    provider_module: str | None = None,
    model: str | None = None,
    run_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    if mode != "all" and mode not in MODES:
        raise ValueError(f"invalid IRR0.3 mode: {mode}")
    if story_id is not None and story_id not in PILOT_STORY_IDS:
        raise ValueError(f"Story is outside the frozen IRR0.1 pilot: {story_id}")
    provider = provider_from_environment(
        fixture=fixture,
        provider_module=provider_module,
        model=model,
    )
    run_type = "fixture" if provider.provider == "fixture" else "real_model"
    execution = build_execution(
        provider,
        run_type,
        execution_run_id(run_type, run_id),
        execution_timestamp(run_type, timestamp),
    )
    pilots = build_irr0_3_inputs(root)
    story_ids = [story_id] if story_id else list(PILOT_STORY_IDS)
    selected_modes = list(MODES) if mode == "all" else [mode]
    generated = {
        current: build_mode_document(root, pilots, current, story_ids, provider, execution)
        for current in selected_modes
    }
    documents: dict[str, Mapping[str, Any]] = {}
    for current in MODES:
        if current in generated:
            documents[current] = merge_story_document(root, current, generated[current], story_id)
        elif (root / output_path(current)).is_file():
            documents[current] = read_json(root, output_path(current))
    if len(documents) != len(MODES):
        documents = generated
    manifest = write_manifest(root, documents, execution)
    copy_public(root, documents, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("all", *MODES), default="all")
    parser.add_argument("--story", choices=PILOT_STORY_IDS)
    parser.add_argument("--fixture", action="store_true", help="use deterministic fixture output")
    parser.add_argument("--provider-module", help="module exposing run_reading(payload)")
    parser.add_argument("--model", help="provider model label")
    parser.add_argument("--run-id", help="recorded experiment run identifier")
    parser.add_argument("--timestamp", help="explicit run timestamp")
    args = parser.parse_args()
    manifest = run_experiment(
        mode=args.mode,
        story_id=args.story,
        fixture=args.fixture,
        provider_module=args.provider_module,
        model=args.model,
        run_id=args.run_id,
        timestamp=args.timestamp,
    )
    print(
        stable_json(
            {
                "manifest": "data/derived/irr0-3/manifest.json",
                "execution": manifest["execution"],
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
