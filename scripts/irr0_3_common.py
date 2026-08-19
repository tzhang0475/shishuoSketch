#!/usr/bin/env python3
"""Shared contracts for IRR0.3 real-model span-gain experiments."""

from __future__ import annotations

import copy
import importlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from jsonschema import Draft202012Validator

try:
    from irr0_2_common import (
        MODEL_SCHEMA_PATH,
        PILOT_STORY_IDS,
        ROOT,
        S1_ASSERTIONS_PATH,
        SC1_PATH,
        REVIEW_PATH,
        build_pilot_inputs,
        build_source_catalog,
        forbidden_input_keys,
        model_input_hash,
        read_json,
        sha256_file,
        stable_json,
        write_json,
    )
except ModuleNotFoundError:  # imported as scripts.irr0_3_common by tests
    from scripts.irr0_2_common import (
        MODEL_SCHEMA_PATH,
        PILOT_STORY_IDS,
        ROOT,
        S1_ASSERTIONS_PATH,
        SC1_PATH,
        REVIEW_PATH,
        build_pilot_inputs,
        build_source_catalog,
        forbidden_input_keys,
        model_input_hash,
        read_json,
        sha256_file,
        stable_json,
        write_json,
    )


CONTEXT_REVIEW_PATH = Path("data/annotation/irr0-3-context-review.json")
SPAN_REVIEW_SCHEMA_PATH = Path("schema/irr0-3-span-review.schema.json")
OUTPUT_DIR = Path("data/derived/irr0-3")
PUBLIC_OUTPUT_DIR = Path("site/public/generated/irr0-3")
PROMPT_VERSION = "irr0.3-v0"
MODES: tuple[str, ...] = ("text_only", "all_at_once", "iterative")


def source_hashes(root: Path = ROOT) -> dict[str, str]:
    return {
        relative.as_posix(): sha256_file(root, relative)
        for relative in (
            SC1_PATH,
            REVIEW_PATH,
            S1_ASSERTIONS_PATH,
            MODEL_SCHEMA_PATH,
            CONTEXT_REVIEW_PATH,
            SPAN_REVIEW_SCHEMA_PATH,
        )
    }


def load_context_review(root: Path = ROOT) -> dict[str, Any]:
    return read_json(root, CONTEXT_REVIEW_PATH)


def build_irr0_3_inputs(root: Path = ROOT) -> dict[str, dict[str, Any]]:
    """Build source-only inputs from the separately reviewed context schedule."""

    context = load_context_review(root)
    if context.get("scope", {}).get("story_ids") != list(PILOT_STORY_IDS):
        raise ValueError("IRR0.3 context review does not cover the frozen five Stories")
    context_by_story = {str(row["story_id"]): row for row in context.get("records", [])}
    if list(context_by_story) != list(PILOT_STORY_IDS):
        raise ValueError("IRR0.3 context review record order/scope changed")

    pilots = build_pilot_inputs(root)
    story_evidence, assertions = build_source_catalog(root)
    result: dict[str, dict[str, Any]] = {}
    for story_id in PILOT_STORY_IDS:
        pilot = pilots[story_id]
        review_record = context_by_story[story_id]
        catalog = copy.deepcopy(pilot["evidence_catalog"])
        rounds: list[dict[str, Any]] = []
        cumulative: list[str] = []
        seen: set[str] = set()
        for raw_round in sorted(review_record.get("rounds", []), key=lambda row: int(row["round"])):
            round_number = int(raw_round["round"])
            additions: list[str] = []
            for item in raw_round.get("evidence_added", []):
                ref = str(item["evidence_ref"])
                if ref in seen:
                    raise ValueError(f"IRR0.3 evidence is added more than once: {story_id}/{ref}")
                descriptor = story_evidence.get(ref) or assertions.get(ref)
                if descriptor is None:
                    raise ValueError(f"IRR0.3 evidence is not resolvable: {story_id}/{ref}")
                catalog[ref] = copy.deepcopy(descriptor)
                additions.append(ref)
                seen.add(ref)
            cumulative = sorted(set(cumulative).union(additions))
            rounds.append(
                {
                    "round": round_number,
                    "evidence_added": additions,
                    "evidence_refs": list(cumulative),
                }
            )
        if not rounds or rounds[0]["round"] != 0 or rounds[0]["evidence_added"]:
            raise ValueError(f"IRR0.3 must start with an empty R0: {story_id}")
        context_refs = sorted(cumulative)
        hard_negative_refs = sorted(
            str(item["evidence_ref"])
            for raw_round in review_record.get("rounds", [])
            for item in raw_round.get("evidence_added", [])
            if item.get("expected_role") == "hard_negative"
        )
        if not hard_negative_refs:
            raise ValueError(f"IRR0.3 has no reviewed hard-negative evidence: {story_id}")
        result[story_id] = {
            "story": copy.deepcopy(pilot["story"]),
            "evidence_catalog": catalog,
            "context_refs": context_refs,
            "iterative_rounds": rounds,
            "hard_negative_refs": hard_negative_refs,
        }
    return result


def context_refs_for_round(pilot: Mapping[str, Any], round_number: int) -> list[str]:
    rounds = pilot["iterative_rounds"]
    if round_number < 0 or round_number >= len(rounds):
        raise ValueError(f"invalid IRR0.3 round: {round_number}")
    return list(rounds[round_number]["evidence_refs"])


def added_refs_for_round(pilot: Mapping[str, Any], round_number: int) -> list[str]:
    rounds = pilot["iterative_rounds"]
    if round_number < 0 or round_number >= len(rounds):
        raise ValueError(f"invalid IRR0.3 round: {round_number}")
    return list(rounds[round_number]["evidence_added"])


def inference_input(
    pilot: Mapping[str, Any],
    evidence_refs: list[str],
    previous_reading: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "story": copy.deepcopy(pilot["story"]),
        "evidence": [
            copy.deepcopy(pilot["evidence_catalog"][ref])
            for ref in sorted(set(evidence_refs))
        ],
    }
    if previous_reading is not None:
        payload["previous_reading"] = copy.deepcopy(previous_reading)
    return payload


def execution_timestamp(run_type: str, requested: str | None = None) -> str:
    if requested:
        return requested
    if run_type == "fixture":
        return "1970-01-01T00:00:00Z"
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def execution_run_id(run_type: str, requested: str | None = None) -> str:
    if requested:
        return requested
    if run_type == "fixture":
        return "irr0-3-fixture"
    return os.environ.get("IRR0_3_RUN_ID") or "irr0-3-provider-run"


class ReadingProvider(Protocol):
    provider: str
    model: str

    def generate(
        self,
        story: Mapping[str, Any],
        evidence: list[Mapping[str, Any]],
        previous_reading: Mapping[str, Any] | None,
        mode: str,
        round_number: int,
        transition_evidence_ids: list[str],
        hard_negative: bool,
    ) -> Mapping[str, Any]: ...


def _empty_delta() -> dict[str, list[dict[str, Any]]]:
    return {
        "historical_changes": [],
        "newly_salient_spans": [],
        "reinterpretations": [],
        "newly_understood_omissions": [],
        "new_connections": [],
        "resolved_questions": [],
        "new_questions": [],
    }


def _model_depth(output: Mapping[str, Any]) -> int:
    rows = output.get("text_reading", {}).get("salient_spans", [])
    return max((int(row.get("depth_self_assessment", 0)) for row in rows), default=0)


def _fixture_transition(
    previous: Mapping[str, Any] | None,
    current: Mapping[str, Any],
    evidence_ids: list[str],
    hard_negative: bool,
) -> list[dict[str, Any]]:
    if not evidence_ids or hard_negative or previous is None:
        return []
    before_rows = previous.get("text_reading", {}).get("salient_spans", [])
    after_rows = current.get("text_reading", {}).get("salient_spans", [])
    if not before_rows or not after_rows or _model_depth(current) <= _model_depth(previous):
        return []
    before = before_rows[0]
    after = after_rows[0]
    return [
        {
            "span": str(after.get("span", "")),
            "before_interpretation": str(before.get("contextual_meaning") or before.get("literal_meaning", "")),
            "after_interpretation": str(after.get("contextual_meaning") or after.get("literal_meaning", "")),
            "historical_depth": min(4, _model_depth(current)),
            "aesthetic_depth": 1 if _model_depth(current) >= 3 else 0,
            "unsupported_interpretation": False,
        }
    ]


class FixtureProvider:
    """Deterministic plumbing fixture, never presented as real-model science."""

    provider = "fixture"
    model = "fixture-reading-irr0-3-v0"

    def __init__(self) -> None:
        try:
            from irr0_2_common import FixtureProvider as BaseFixtureProvider
        except ModuleNotFoundError:
            from scripts.irr0_2_common import FixtureProvider as BaseFixtureProvider
        self._base = BaseFixtureProvider()

    def generate(
        self,
        story: Mapping[str, Any],
        evidence: list[Mapping[str, Any]],
        previous_reading: Mapping[str, Any] | None,
        mode: str,
        round_number: int,
        transition_evidence_ids: list[str],
        hard_negative: bool,
    ) -> Mapping[str, Any]:
        output = copy.deepcopy(
            self._base.generate(story, evidence, previous_reading, mode, round_number)
        )
        if hard_negative and previous_reading is not None and mode == "iterative":
            previous_depth = _model_depth(previous_reading)
            for row in output.get("text_reading", {}).get("salient_spans", []):
                row["depth_self_assessment"] = previous_depth
            output["reading_delta"] = _empty_delta()
        return {
            "output": output,
            "affected_spans": _fixture_transition(
                previous_reading,
                output,
                transition_evidence_ids,
                hard_negative,
            ),
        }


class ModuleProvider:
    """Provider-neutral adapter for a user-supplied real model module."""

    def __init__(self, module_name: str, model: str) -> None:
        module = importlib.import_module(module_name)
        function = getattr(module, "run_reading", None)
        if not callable(function):
            raise ValueError(f"provider module has no callable run_reading: {module_name}")
        self._function: Callable[[Mapping[str, Any]], Mapping[str, Any]] = function
        self.provider = module_name
        self.model = model

    def generate(
        self,
        story: Mapping[str, Any],
        evidence: list[Mapping[str, Any]],
        previous_reading: Mapping[str, Any] | None,
        mode: str,
        round_number: int,
        transition_evidence_ids: list[str],
        hard_negative: bool,
    ) -> Mapping[str, Any]:
        payload = {
            "story": copy.deepcopy(story),
            "evidence": copy.deepcopy(evidence),
            "previous_reading": copy.deepcopy(previous_reading),
            "mode": mode,
            "round": round_number,
            "transition_evidence_ids": list(transition_evidence_ids),
            "prompt_version": PROMPT_VERSION,
            "output_schema": "schema/model-iterative-reading.schema.json",
            "span_transition_schema": "schema/irr0-3-span-review.schema.json",
            "task_instructions": (
                "Read only the supplied Story and evidence. Preserve uncertainty. "
                "Return the IRR0.2 structured model reading plus affected_spans for "
                "iterative transitions. Do not infer from outside knowledge."
            ),
        }
        raw = self._function(payload)
        if not isinstance(raw, Mapping):
            raise ValueError("IRR0.3 provider must return an object")
        if isinstance(raw.get("model_output"), Mapping):
            output = copy.deepcopy(dict(raw["model_output"]))
        elif isinstance(raw.get("output"), Mapping):
            output = copy.deepcopy(dict(raw["output"]))
        else:
            output = copy.deepcopy(dict(raw))
        spans = raw.get("affected_spans")
        if spans is None:
            spans = output.pop("affected_spans", None)
        if spans is None:
            if mode == "iterative" and round_number > 0:
                raise ValueError("IRR0.3 provider must return affected_spans for iterative transitions")
            spans = []
        if not isinstance(spans, list):
            raise ValueError("IRR0.3 provider affected_spans must be an array")
        return {"output": output, "affected_spans": copy.deepcopy(spans)}


def provider_from_environment(
    fixture: bool = False,
    provider_module: str | None = None,
    model: str | None = None,
) -> ReadingProvider:
    module_name = provider_module or os.environ.get("IRR0_3_PROVIDER_MODULE")
    resolved_model = model or os.environ.get("IRR0_3_MODEL") or "external-model"
    if fixture or not module_name:
        return FixtureProvider()
    return ModuleProvider(module_name, resolved_model)


def validate_model_output(root: Path, output: Mapping[str, Any]) -> None:
    schema = read_json(root, MODEL_SCHEMA_PATH)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(output),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        location = "/" + "/".join(str(part) for part in errors[0].absolute_path)
        raise ValueError(f"IRR0.3 model output schema error at {location}: {errors[0].message}")


def validate_span_transition(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("IRR0.3 transition must be an object")
    evidence_ids = value.get("evidence_ids")
    affected = value.get("affected_spans")
    if not isinstance(evidence_ids, list) or any(not isinstance(item, str) or not item for item in evidence_ids):
        raise ValueError("IRR0.3 transition evidence_ids must be non-empty strings")
    if not isinstance(affected, list):
        raise ValueError("IRR0.3 transition affected_spans must be an array")
    for item in affected:
        if not isinstance(item, Mapping):
            raise ValueError("IRR0.3 affected span must be an object")
        required = (
            "span",
            "before_interpretation",
            "after_interpretation",
            "historical_depth",
            "aesthetic_depth",
            "unsupported_interpretation",
        )
        missing = [key for key in required if key not in item]
        if missing:
            raise ValueError(f"IRR0.3 affected span lacks: {missing}")
        if not isinstance(item["span"], str) or not item["span"]:
            raise ValueError("IRR0.3 affected span text is empty")
        if not isinstance(item["before_interpretation"], str) or not isinstance(item["after_interpretation"], str):
            raise ValueError("IRR0.3 affected span interpretations must be strings")
        if not isinstance(item["historical_depth"], int) or not 0 <= item["historical_depth"] <= 4:
            raise ValueError("IRR0.3 historical_depth must be an integer from 0 to 4")
        if not isinstance(item["aesthetic_depth"], int) or not 0 <= item["aesthetic_depth"] <= 4:
            raise ValueError("IRR0.3 aesthetic_depth must be an integer from 0 to 4")
        if item["unsupported_interpretation"] not in (False, 0, 1, 2):
            raise ValueError("IRR0.3 unsupported_interpretation must be false/0/1/2")


def metadata(
    provider: ReadingProvider,
    run_type: str,
    run_id: str,
    created_at: str,
    input_hash: str,
) -> dict[str, Any]:
    return {
        "provider": provider.provider,
        "model": provider.model,
        "parameters": {"temperature": 0, "prompt_version": PROMPT_VERSION},
        "run_id": run_id,
        "run_type": run_type,
        "created_at": created_at,
        "input_hash": input_hash,
    }


def output_filename(mode: str) -> str:
    return {
        "text_only": "text-only.json",
        "all_at_once": "all-at-once.json",
        "iterative": "iterative.json",
    }[mode]


def public_output_path(mode: str) -> Path:
    return PUBLIC_OUTPUT_DIR / output_filename(mode)


def output_path(mode: str) -> Path:
    return OUTPUT_DIR / output_filename(mode)
