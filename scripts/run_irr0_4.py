#!/usr/bin/env python3
"""Run the IRR0.4 semantic escalation ladder with memory/fresh branches."""

from __future__ import annotations

import argparse
import copy
import hashlib
from pathlib import Path
from typing import Any, Mapping

try:
    from irr0_4_common import (
        CONDITIONS,
        IRR04_STORY_IDS,
        OUTPUT_DIR,
        PUBLIC_OUTPUT_DIR,
        ROOT,
        build_irr0_4_inputs,
        execution_run_id,
        execution_timestamp,
        forbidden_input_keys,
        inference_input,
        metadata,
        model_input_hash,
        output_path,
        provider_from_environment,
        public_output_path,
        read_json,
        source_hashes,
        stable_json,
        validate_model_output,
        write_json,
    )
except ModuleNotFoundError:
    from scripts.irr0_4_common import (
        CONDITIONS,
        IRR04_STORY_IDS,
        OUTPUT_DIR,
        PUBLIC_OUTPUT_DIR,
        ROOT,
        build_irr0_4_inputs,
        execution_run_id,
        execution_timestamp,
        forbidden_input_keys,
        inference_input,
        metadata,
        model_input_hash,
        output_path,
        provider_from_environment,
        public_output_path,
        read_json,
        source_hashes,
        stable_json,
        validate_model_output,
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
        "parameters": {"temperature": 0, "prompt_version": "irr0.4-v0"},
    }


def run_reading(
    root: Path,
    pilot: Mapping[str, Any],
    provider: Any,
    execution: Mapping[str, Any],
    evidence_refs: list[str],
    semantic_stage: str,
    driving_question: str,
    round_label: str,
    branch: str,
    condition: str,
    target_spans: list[str],
    previous_reading: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = inference_input(
        pilot,
        evidence_refs,
        semantic_stage,
        driving_question,
        round_label,
        branch,
        condition,
        previous_reading,
    )
    leaked = forbidden_input_keys(payload)
    if leaked:
        raise ValueError(f"Gold/review fields leaked into IRR0.4 input: {leaked}")
    input_hash = model_input_hash(payload)
    result = provider.generate(
        pilot["story"],
        payload["evidence"],
        payload.get("previous_reading"),
        semantic_stage,
        driving_question,
        round_label,
        branch,
        condition,
        target_spans,
    )
    output = copy.deepcopy(dict(result["output"]))
    validate_model_output(root, output)
    return {
        "inference_input": payload,
        "input_hash": input_hash,
        "model_metadata": metadata(
            provider,
            str(execution["run_type"]),
            str(execution["run_id"]),
            str(execution["created_at"]),
            input_hash,
            condition,
            branch,
            round_label,
        ),
        "output": output,
    }


def build_round(
    root: Path,
    pilot: Mapping[str, Any],
    provider: Any,
    execution: Mapping[str, Any],
    round_spec: Mapping[str, Any],
    previous_memory: Mapping[str, Any] | None,
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    round_number = int(round_spec["round"])
    target_spans = list(round_spec["gold_target_spans"])
    if round_number == 0:
        if baseline is None:
            baseline = run_reading(
                root,
                pilot,
                provider,
                execution,
                list(round_spec["evidence_refs"]),
                str(round_spec["semantic_stage"]),
                str(round_spec["driving_question"]),
                "R0",
                "main",
                "memory",
                target_spans,
                None,
            )
        fresh = run_reading(
            root,
            pilot,
            provider,
            execution,
            list(round_spec["evidence_refs"]),
            str(round_spec["semantic_stage"]),
            str(round_spec["driving_question"]),
            "R0",
            "main",
            "fresh",
            target_spans,
            None,
        )
        return {
            "round": round_number,
            "round_label": "R0",
            "semantic_stage": round_spec["semantic_stage"],
            "driving_question": round_spec["driving_question"],
            "evidence_bundle": list(round_spec["evidence_bundle"]),
            "evidence_refs": list(round_spec["evidence_refs"]),
            "gold": {
                "expected_effect": round_spec["gold_expected_effect"],
                "target_spans": target_spans,
            },
            "shared_baseline": False,
            "memory_reading": baseline,
            "fresh_reading": fresh,
        }
    memory = run_reading(
        root,
        pilot,
        provider,
        execution,
        list(round_spec["evidence_refs"]),
        str(round_spec["semantic_stage"]),
        str(round_spec["driving_question"]),
        f"R{round_number}",
        "main",
        "memory",
        target_spans,
        previous_memory,
    )
    fresh = run_reading(
        root,
        pilot,
        provider,
        execution,
        list(round_spec["evidence_refs"]),
        str(round_spec["semantic_stage"]),
        str(round_spec["driving_question"]),
        f"R{round_number}",
        "main",
        "fresh",
        target_spans,
        None,
    )
    return {
        "round": round_number,
        "round_label": f"R{round_number}",
        "semantic_stage": round_spec["semantic_stage"],
        "driving_question": round_spec["driving_question"],
        "evidence_bundle": list(round_spec["evidence_bundle"]),
        "evidence_refs": list(round_spec["evidence_refs"]),
        "gold": {
            "expected_effect": round_spec["gold_expected_effect"],
            "target_spans": target_spans,
        },
        "shared_baseline": False,
        "memory_reading": memory,
        "fresh_reading": fresh,
    }


def build_negative_control(
    root: Path,
    pilot: Mapping[str, Any],
    provider: Any,
    execution: Mapping[str, Any],
    negative: Mapping[str, Any],
    previous_memory: Mapping[str, Any],
) -> dict[str, Any]:
    target_spans = list(negative["gold_target_spans"])
    memory = run_reading(
        root,
        pilot,
        provider,
        execution,
        list(negative["evidence_refs"]),
        str(negative["semantic_stage"]),
        str(negative["driving_question"]),
        str(negative["round_label"]),
        "negative_control",
        "memory",
        target_spans,
        previous_memory,
    )
    fresh = run_reading(
        root,
        pilot,
        provider,
        execution,
        list(negative["evidence_refs"]),
        str(negative["semantic_stage"]),
        str(negative["driving_question"]),
        str(negative["round_label"]),
        "negative_control",
        "fresh",
        target_spans,
        None,
    )
    return {
        "round": negative["round_label"],
        "round_label": negative["round_label"],
        "base_round": negative["base_round"],
        "semantic_stage": negative["semantic_stage"],
        "driving_question": negative["driving_question"],
        "evidence_bundle": list(negative["evidence_bundle"]),
        "evidence_refs": list(negative["evidence_refs"]),
        "branch_role": negative["branch_role"],
        "gold": {
            "expected_effect": negative["gold_expected_effect"],
            "target_spans": target_spans,
        },
        "memory_reading": memory,
        "fresh_reading": fresh,
    }


def build_story_record(
    root: Path,
    story_id: str,
    pilot: Mapping[str, Any],
    provider: Any,
    execution: Mapping[str, Any],
) -> dict[str, Any]:
    rounds: list[dict[str, Any]] = []
    previous_memory: Mapping[str, Any] | None = None
    for round_spec in pilot["rounds"]:
        current = build_round(
            root,
            pilot,
            provider,
            execution,
            round_spec,
            previous_memory,
        )
        rounds.append(current)
        previous_memory = current["memory_reading"]["output"]
    negative = build_negative_control(
        root,
        pilot,
        provider,
        execution,
        pilot["negative_control"],
        rounds[1]["memory_reading"]["output"],
    )
    return {
        "story_id": story_id,
        "critical_spans": list(pilot["critical_spans"]),
        "rounds": rounds,
        "negative_control": negative,
    }


def write_manifest(root: Path, execution: Mapping[str, Any]) -> dict[str, Any]:
    artifact_hashes: dict[str, str] = {}
    for path in sorted((root / OUTPUT_DIR).glob("*.json")):
        if path.name == "manifest.json":
            continue
        artifact_hashes[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "schema": "irr0.4-manifest",
        "stage": "IRR0.4",
        "schema_version": "v0",
        "execution": copy.deepcopy(dict(execution)),
        "scope": {"story_count": len(IRR04_STORY_IDS), "story_ids": list(IRR04_STORY_IDS)},
        "conditions": list(CONDITIONS),
        "source_hashes": source_hashes(root),
        "artifact_hashes_excluding_manifest": artifact_hashes,
        "self_hash": None,
    }
    write_json(root, OUTPUT_DIR / "manifest.json", manifest)
    return manifest


def copy_public(root: Path) -> None:
    public = root / PUBLIC_OUTPUT_DIR
    public.mkdir(parents=True, exist_ok=True)
    for path in sorted((root / OUTPUT_DIR).glob("*.json")):
        write_json(root, public_output_path(path.name), read_json(root, OUTPUT_DIR / path.name))


def run_experiment(
    root: Path = ROOT,
    fixture: bool = False,
    provider_module: str | None = None,
    model: str | None = None,
    run_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    provider = provider_from_environment(fixture, provider_module, model)
    run_type = "fixture" if provider.provider == "fixture" else "real_model"
    execution = build_execution(
        provider,
        run_type,
        execution_run_id(run_type, run_id),
        execution_timestamp(run_type, timestamp),
    )
    pilots = build_irr0_4_inputs(root)
    records = [
        build_story_record(root, story_id, pilots[story_id], provider, execution)
        for story_id in IRR04_STORY_IDS
    ]
    document = {
        "schema": "irr0.4-semantic-ladders",
        "stage": "IRR0.4",
        "schema_version": "v0",
        "execution": copy.deepcopy(execution),
        "scope": {"story_count": len(IRR04_STORY_IDS), "story_ids": list(IRR04_STORY_IDS)},
        "input_contract": {
            "gold_used_for_scoring_only": True,
            "semantic_review_used_for_fixture_control_only": True,
            "fresh_omits_previous_reading": True,
            "forbidden_inference_keys": sorted([
                "gold_expected_effect",
                "gold_target_spans",
                "expected_role",
                "branch_role",
                "human_review",
                "IRR0.1_Gold",
                "IRR0.3_scores",
            ]),
        },
        "source_hashes": source_hashes(root),
        "records": records,
    }
    write_json(root, output_path(), document)
    manifest = write_manifest(root, execution)
    copy_public(root)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", action="store_true", help="use deterministic fixture output")
    parser.add_argument("--provider-module", help="module exposing run_reading(payload)")
    parser.add_argument("--model", help="provider model label")
    parser.add_argument("--run-id", help="recorded experiment run identifier")
    parser.add_argument("--timestamp", help="explicit run timestamp")
    args = parser.parse_args()
    manifest = run_experiment(
        fixture=args.fixture,
        provider_module=args.provider_module,
        model=args.model,
        run_id=args.run_id,
        timestamp=args.timestamp,
    )
    print(stable_json({"manifest": "data/derived/irr0-4/manifest.json", "execution": manifest["execution"]}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
