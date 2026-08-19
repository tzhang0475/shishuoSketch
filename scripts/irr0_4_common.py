#!/usr/bin/env python3
"""Shared deterministic contracts for IRR0.4 semantic-ladder experiments."""

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
        MODEL_SCHEMA_PATH as IRR02_MODEL_SCHEMA_PATH,
        ROOT,
        S1_ASSERTIONS_PATH,
        SC1_PATH,
        build_pilot_inputs,
        build_source_catalog,
        forbidden_input_keys,
        model_input_hash,
        read_json,
        sha256_file,
        stable_json,
        write_json,
    )
except ModuleNotFoundError:
    from scripts.irr0_2_common import (
        MODEL_SCHEMA_PATH as IRR02_MODEL_SCHEMA_PATH,
        ROOT,
        S1_ASSERTIONS_PATH,
        SC1_PATH,
        build_pilot_inputs,
        build_source_catalog,
        forbidden_input_keys,
        model_input_hash,
        read_json,
        sha256_file,
        stable_json,
        write_json,
    )


IRR04_STORY_IDS: tuple[str, ...] = (
    "27-jiajue-008",
    "09-pinzao-017",
    "06-yaliang-017",
)
SEMANTIC_REVIEW_PATH = Path("data/annotation/irr0-4-semantic-review.json")
HUMAN_REVIEW_PATH = Path("data/annotation/irr0-4-human-review.json")
MODEL_SCHEMA_PATH = Path("schema/model-irr0-4-semantic-ladder.schema.json")
HUMAN_SCHEMA_PATH = Path("schema/irr0-4-human-review.schema.json")
IRR03_MANIFEST_PATH = Path("data/derived/irr0-3/manifest.json")
OUTPUT_DIR = Path("data/derived/irr0-4")
PUBLIC_OUTPUT_DIR = Path("site/public/generated/irr0-4")
PROMPT_VERSION = "irr0.4-v0"
STAGES: tuple[str, ...] = (
    "literal",
    "event_context",
    "relational_context",
    "aesthetic_rereading",
)
CONDITIONS: tuple[str, ...] = ("memory", "fresh")


def source_hashes(root: Path = ROOT) -> dict[str, str]:
    return {
        relative.as_posix(): sha256_file(root, relative)
        for relative in (
            SC1_PATH,
            S1_ASSERTIONS_PATH,
            IRR02_MODEL_SCHEMA_PATH,
            IRR03_MANIFEST_PATH,
            SEMANTIC_REVIEW_PATH,
            MODEL_SCHEMA_PATH,
            HUMAN_SCHEMA_PATH,
        )
    }


def load_semantic_review(root: Path = ROOT) -> dict[str, Any]:
    return read_json(root, SEMANTIC_REVIEW_PATH)


def _descriptor_catalog(root: Path) -> dict[str, Mapping[str, Any]]:
    story_evidence, assertions = build_source_catalog(root)
    return {
        **{str(key): value for key, value in story_evidence.items()},
        **{str(key): value for key, value in assertions.items()},
    }


def build_irr0_4_inputs(root: Path = ROOT) -> dict[str, dict[str, Any]]:
    review = load_semantic_review(root)
    if review.get("scope", {}).get("story_ids") != list(IRR04_STORY_IDS):
        raise ValueError("IRR0.4 scope is not the frozen three-Story pilot")
    records = review.get("records", [])
    if [row.get("story_id") for row in records] != list(IRR04_STORY_IDS):
        raise ValueError("IRR0.4 semantic review record order/scope changed")

    pilots = build_pilot_inputs(root)
    catalog = _descriptor_catalog(root)
    result: dict[str, dict[str, Any]] = {}
    for raw in records:
        story_id = str(raw["story_id"])
        if story_id not in pilots:
            raise ValueError(f"IRR0.4 Story is not present in the existing pilot: {story_id}")
        raw_rounds = sorted(raw.get("rounds", []), key=lambda row: int(row["round"]))
        if [int(row["round"]) for row in raw_rounds] != [0, 1, 2, 3]:
            raise ValueError(f"IRR0.4 requires R0-R3: {story_id}")
        critical_spans = [str(span) for span in raw.get("critical_spans", [])]
        if not critical_spans or len(critical_spans) != len(set(critical_spans)):
            raise ValueError(f"IRR0.4 critical span set is invalid: {story_id}")
        cumulative: list[str] = []
        seen: set[str] = set()
        rounds: list[dict[str, Any]] = []
        for raw_round in raw_rounds:
            stage = str(raw_round.get("semantic_stage"))
            if stage not in STAGES:
                raise ValueError(f"IRR0.4 stage is invalid: {story_id}/R{raw_round['round']}")
            bundle = [str(ref) for ref in raw_round.get("evidence_bundle", [])]
            if len(bundle) != len(set(bundle)):
                raise ValueError(f"IRR0.4 evidence bundle repeats a reference: {story_id}/R{raw_round['round']}")
            for ref in bundle:
                if ref in seen:
                    raise ValueError(f"IRR0.4 evidence is repeated across stages: {story_id}/{ref}")
                if ref not in catalog:
                    raise ValueError(f"IRR0.4 evidence is not resolvable: {story_id}/{ref}")
                seen.add(ref)
            cumulative = sorted(set(cumulative).union(bundle))
            rounds.append({
                "round": int(raw_round["round"]),
                "semantic_stage": stage,
                "driving_question": str(raw_round["driving_question"]),
                "evidence_bundle": bundle,
                "evidence_refs": list(cumulative),
                "gold_expected_effect": str(raw_round["gold_expected_effect"]),
                "gold_target_spans": [str(span) for span in raw_round.get("gold_target_spans", [])],
            })
        if any(
            not set(critical_spans).issubset(set(round_spec["gold_target_spans"]))
            for round_spec in rounds
        ):
            raise ValueError(f"IRR0.4 critical spans are not tracked through every round: {story_id}")
        negative_raw = raw.get("negative_control")
        if not isinstance(negative_raw, Mapping):
            raise ValueError(f"IRR0.4 negative control is missing: {story_id}")
        negative_bundle = [str(ref) for ref in negative_raw.get("evidence_bundle", [])]
        if not negative_bundle or len(negative_bundle) != len(set(negative_bundle)):
            raise ValueError(f"IRR0.4 negative control bundle is invalid: {story_id}")
        for ref in negative_bundle:
            if ref in seen or ref not in catalog:
                raise ValueError(f"IRR0.4 negative control evidence is invalid: {story_id}/{ref}")
        base_round = int(negative_raw.get("base_round", 1))
        if base_round != 1:
            raise ValueError(f"IRR0.4 negative control must branch after R1: {story_id}")
        if str(negative_raw.get("semantic_stage")) not in STAGES:
            raise ValueError(f"IRR0.4 negative control stage is invalid: {story_id}")
        if not set(critical_spans).issubset({str(span) for span in negative_raw.get("gold_target_spans", [])}):
            raise ValueError(f"IRR0.4 negative control does not track all critical spans: {story_id}")
        negative = {
            "base_round": base_round,
            "round_label": str(negative_raw["round_label"]),
            "semantic_stage": str(negative_raw["semantic_stage"]),
            "driving_question": str(negative_raw["driving_question"]),
            "evidence_bundle": negative_bundle,
            "evidence_refs": sorted(set(rounds[base_round]["evidence_refs"]).union(negative_bundle)),
            "branch_role": str(negative_raw.get("branch_role", "hard_negative")),
            "gold_expected_effect": str(negative_raw["gold_expected_effect"]),
            "gold_target_spans": [str(span) for span in negative_raw.get("gold_target_spans", [])],
        }
        result[story_id] = {
            "story": copy.deepcopy(pilots[story_id]["story"]),
            "critical_spans": critical_spans,
            "evidence_catalog": copy.deepcopy(catalog),
            "rounds": rounds,
            "negative_control": negative,
        }
    return result


def inference_input(
    pilot: Mapping[str, Any],
    evidence_refs: list[str],
    semantic_stage: str,
    driving_question: str,
    round_label: str,
    branch: str,
    condition: str,
    previous_reading: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "story": copy.deepcopy(pilot["story"]),
        "evidence": [
            copy.deepcopy(pilot["evidence_catalog"][ref])
            for ref in sorted(set(evidence_refs))
        ],
        "semantic_stage": semantic_stage,
        "driving_question": driving_question,
        "round": round_label,
        "branch": branch,
        "condition": condition,
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
        return "irr0-4-fixture"
    return os.environ.get("IRR0_4_RUN_ID") or "irr0-4-provider-run"


class SemanticProvider(Protocol):
    provider: str
    model: str

    def generate(
        self,
        story: Mapping[str, Any],
        evidence: list[Mapping[str, Any]],
        previous_reading: Mapping[str, Any] | None,
        semantic_stage: str,
        driving_question: str,
        round_label: str,
        branch: str,
        condition: str,
        target_spans: list[str],
    ) -> Mapping[str, Any]: ...


def _fixture_reading(
    story_id: str,
    target_spans: list[str],
    semantic_stage: str,
    round_label: str,
    branch: str,
    evidence_ids: list[str],
) -> dict[str, Any]:
    is_negative = branch == "negative_control"
    stage_depths: dict[str, tuple[int, int, int, int]] = {
        "27-jiajue-008": {
            "literal": (1, 0, 0, 0),
            "event_context": (2, 1, 0, 0),
            "relational_context": (2, 3, 0, 1),
            "aesthetic_rereading": (2, 3, 0, 4),
        },
        "09-pinzao-017": {
            "literal": (1, 0, 0, 0),
            "event_context": (2, 1, 0, 0),
            "relational_context": (2, 3, 0, 1),
            "aesthetic_rereading": (2, 3, 0, 4),
        },
        "06-yaliang-017": {
            "literal": (1, 0, 0, 0),
            "event_context": (2, 1, 0, 0),
            "relational_context": (2, 1, 3, 2),
            "aesthetic_rereading": (2, 1, 3, 4),
        },
    }
    stage = stage_depths[story_id][semantic_stage]
    if is_negative:
        stage = stage_depths[story_id]["event_context"]
    interpretations = {
        "27-jiajue-008": {
            "literal": "原文连续写出拜、止、同坐与引咎，先按动作顺序理解。",
            "event_context": "引咎责躬落在苏峻之乱和庾亮辅政的政治责任中。",
            "relational_context": "止拜、同坐和逊谢构成陶侃与庾亮在危局中的关系动作链。",
            "aesthetic_rereading": "叙事不解释关系变化，只用止拜、同坐、引咎的动作压缩出释然。",
        },
        "09-pinzao-017": {
            "literal": "谢鲲说自己在一丘一壑上胜过庾亮。",
            "event_context": "这是明帝询问谢鲲与庾亮优劣时的具体自评。",
            "relational_context": "一丘一壑借班嗣论庄周，成为庙堂功业之外的生活方式对照。",
            "aesthetic_rereading": "短句把比较留在原处，不替谢鲲把丘壑改写成抽象结论。",
        },
        "06-yaliang-017": {
            "literal": "孩子受惊扰时神色恬然，随后从容跪答。",
            "event_context": "庾会的身份和年龄使这份镇定落在一个具体幼子身上。",
            "relational_context": "后来遇害与童年神色形成回望关系，但没有改变当时的现场动作。",
            "aesthetic_rereading": "原文让童年镇定与后来命运并置，却不把镇定解释成预兆。",
        },
    }
    current = interpretations[story_id][semantic_stage]
    if is_negative:
        current = interpretations[story_id]["event_context"]
    changed = semantic_stage != "literal" and not is_negative
    change_type = {
        "literal": "none",
        "event_context": "historical",
        "relational_context": "relational",
        "aesthetic_rereading": "aesthetic",
    }[semantic_stage]
    if is_negative:
        change_type = "none"
    observations = []
    if semantic_stage == "aesthetic_rereading" and not is_negative:
        observations = [{
            "span": target_spans[0],
            "operations": ["selection", "compression", "omission"],
            "observation": "原文以保留的动作/短语和未说出的解释构成余韵。",
            "evidence_ids": sorted(set(evidence_ids)),
        }]
    return {
        "span_readings": [
            {
                "span": span,
                "literal_reading": "按原文的字面动作和语句理解。",
                "current_interpretation": current,
                "changed_from_previous": changed,
                "change_type": change_type,
                "supporting_evidence_ids": sorted(set(evidence_ids)) if changed else [],
                "unsupported_inference": False,
                "scene_historical_depth": stage[0],
                "relational_depth": stage[1],
                "retrospective_depth": stage[2],
                "aesthetic_depth": stage[3],
            }
            for span in target_spans
        ],
        "historical_situation_delta": [] if is_negative or semantic_stage == "literal" else [{
            "text": current,
            "evidence_ids": sorted(set(evidence_ids)),
        }],
        "new_questions": [],
        "aesthetic_observations": observations,
    }


class FixtureProvider:
    provider = "fixture"
    model = "fixture-reading-irr0-4-v0"

    def generate(
        self,
        story: Mapping[str, Any],
        evidence: list[Mapping[str, Any]],
        previous_reading: Mapping[str, Any] | None,
        semantic_stage: str,
        driving_question: str,
        round_label: str,
        branch: str,
        condition: str,
        target_spans: list[str],
    ) -> Mapping[str, Any]:
        del previous_reading, driving_question, condition
        evidence_ids = [str(item.get("evidence_ref")) for item in evidence]
        return {
            "output": _fixture_reading(
                str(story["story_id"]),
                target_spans,
                semantic_stage,
                round_label,
                branch,
                evidence_ids,
            )
        }


class ModuleProvider:
    """Provider-neutral adapter for a user-supplied run_reading(payload) module."""

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
        semantic_stage: str,
        driving_question: str,
        round_label: str,
        branch: str,
        condition: str,
        target_spans: list[str],
    ) -> Mapping[str, Any]:
        del target_spans
        payload: dict[str, Any] = {
            "story": copy.deepcopy(story),
            "evidence": copy.deepcopy(evidence),
            "semantic_stage": semantic_stage,
            "driving_question": driving_question,
            "round": round_label,
            "branch": branch,
            "condition": condition,
            "prompt_version": PROMPT_VERSION,
            "output_schema": MODEL_SCHEMA_PATH.as_posix(),
            "task_instructions": (
                "Re-read the original Shishuo passage from the beginning. "
                "Do not merely append information to a previous interpretation. "
                "If new evidence changes an earlier interpretation, replace it. "
                "If it does not change the target passage, say so explicitly. "
                "Do not create deeper meaning merely because another round occurred. "
                "Keep literal, historical, relational, retrospective and aesthetic "
                "depth distinct; preserve uncertainty and cite only supplied evidence."
            ),
        }
        if previous_reading is not None:
            payload["previous_reading"] = copy.deepcopy(previous_reading)
        raw = self._function(payload)
        if not isinstance(raw, Mapping):
            raise ValueError("IRR0.4 provider must return an object")
        if isinstance(raw.get("semantic_output"), Mapping):
            return {"output": copy.deepcopy(dict(raw["semantic_output"]))}
        if isinstance(raw.get("output"), Mapping):
            return {"output": copy.deepcopy(dict(raw["output"]))}
        return {"output": copy.deepcopy(dict(raw))}


def provider_from_environment(
    fixture: bool = False,
    provider_module: str | None = None,
    model: str | None = None,
) -> SemanticProvider:
    module_name = provider_module or os.environ.get("IRR0_4_PROVIDER_MODULE") or os.environ.get("IRR0_3_PROVIDER_MODULE")
    resolved_model = model or os.environ.get("IRR0_4_MODEL") or os.environ.get("IRR0_3_MODEL") or "external-model"
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
        raise ValueError(f"IRR0.4 model output schema error at {location}: {errors[0].message}")


def metadata(
    provider: SemanticProvider,
    run_type: str,
    run_id: str,
    created_at: str,
    input_hash: str,
    condition: str,
    branch: str,
    round_label: str,
) -> dict[str, Any]:
    return {
        "provider": provider.provider,
        "model": provider.model,
        "parameters": {"temperature": 0, "prompt_version": PROMPT_VERSION},
        "run_id": run_id,
        "run_type": run_type,
        "created_at": created_at,
        "input_hash": input_hash,
        "condition": condition,
        "branch": branch,
        "round": round_label,
    }


def output_path(name: str = "semantic-ladders.json") -> Path:
    return OUTPUT_DIR / name


def public_output_path(name: str = "semantic-ladders.json") -> Path:
    return PUBLIC_OUTPUT_DIR / name
