#!/usr/bin/env python3
"""Shared contracts for the IRR0.2 model re-reading experiment.

The module deliberately keeps inference inputs separate from IRR0.1 Gold.  It
uses the Gold file only to select the frozen pilot and to enumerate the
already-reviewed evidence references that form each experimental condition.
Gold reading states, target depths, expected roles and gains are never put in
an inference input.
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Callable, Iterable, Mapping, Protocol


ROOT = Path(__file__).resolve().parents[1]
SC1_PATH = Path("data/derived/sc1-site.json")
REVIEW_PATH = Path("data/annotation/irr0-iterative-reading-review.json")
GOLD_PATH = Path("data/derived/irr0-iterative-reading-gold.json")
MODEL_SCHEMA_PATH = Path("schema/model-iterative-reading.schema.json")
S1_ASSERTIONS_PATH = Path("data/derived/s1-jianshu-historical-assertions.json")
OUTPUT_DIR = Path("data/derived/irr0-2")
PUBLIC_OUTPUT_DIR = Path("site/public/generated/irr0-2")

PILOT_STORY_IDS: tuple[str, ...] = (
    "27-jiajue-008",
    "06-yaliang-017",
    "09-pinzao-017",
    "19-xianyuan-026",
    "05-fangzheng-032",
)

MODES: tuple[str, ...] = ("text_only", "all_at_once", "iterative")
FORBIDDEN_INPUT_KEYS = frozenset(
    {
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
    }
)
ALLOWED_OPERATIONS = frozenset(
    {
        "selection",
        "compression",
        "omission",
        "juxtaposition",
        "action_substitution",
        "speaker_exposure",
        "delayed_revelation",
    }
)
SOURCE_LAYER_MAP = {
    "primary_text": "base_text",
    "annotation": "liu_annotation",
    "editorial": "editorial",
    "secondary_reference": "secondary_reference",
}


def read_json(root: Path, relative: Path) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_json(root: Path, relative: Path, value: Any) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(value), encoding="utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(stable_json(value).encode("utf-8"))


def sha256_file(root: Path, relative: Path) -> str:
    digest = hashlib.sha256()
    with (root / relative).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_hashes(root: Path) -> dict[str, str]:
    return {
        relative.as_posix(): sha256_file(root, relative)
        for relative in (SC1_PATH, REVIEW_PATH, MODEL_SCHEMA_PATH, S1_ASSERTIONS_PATH)
    }


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def safe_locator(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """Keep stable source coordinates without exposing annotation metadata."""

    if not isinstance(raw, Mapping):
        return {}
    allowed = (
        "artifact_type",
        "source_path",
        "source_normalized_filename",
        "witness_id",
        "chapter_id",
        "entry_id",
        "epub_file",
        "spine_index",
        "block_index",
        "tag",
        "page",
        "physical_page",
    )
    return {key: copy.deepcopy(raw[key]) for key in allowed if key in raw}


def _story_text(story: Mapping[str, Any]) -> dict[str, str]:
    reading = story.get("reading", {})
    pair = reading.get("main_text", {}) if isinstance(reading, Mapping) else {}
    if not isinstance(pair, Mapping):
        pair = {}
    return {
        "original": str(pair.get("original", story.get("text", ""))),
        "simplified": str(pair.get("simplified", story.get("text", ""))),
    }


def _source_layer(evidence_type: str) -> str:
    return SOURCE_LAYER_MAP.get(evidence_type, "unknown")


def _story_evidence_descriptor(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "evidence_ref": str(row["id"]),
        "source": str(row.get("source_id", "")),
        "source_layer": _source_layer(str(row.get("evidence_type", ""))),
        "quote": str(row.get("quote", "")),
        "locator": safe_locator(row.get("locator")),
    }


def _assertion_descriptor(row: Mapping[str, Any]) -> dict[str, Any]:
    descriptor: dict[str, Any] = {
        "evidence_ref": str(row["assertion_id"]),
        "source": str(row.get("attribution") or "世说新语笺疏"),
        "source_layer": str(row.get("layer", "unknown")),
        "quote": str(row.get("text", "")),
        "locator": safe_locator(row.get("source_locator")),
    }
    if row.get("quoted_source"):
        descriptor["quoted_source"] = str(row["quoted_source"])
    if row.get("modality"):
        descriptor["modality"] = str(row["modality"])
    return descriptor


def build_source_catalog(root: Path = ROOT) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    sc1 = read_json(root, SC1_PATH)
    s1 = read_json(root, S1_ASSERTIONS_PATH)
    story_evidence = {
        str(row["id"]): _story_evidence_descriptor(row)
        for row in sc1.get("evidence", [])
        if isinstance(row, Mapping) and row.get("id")
    }
    assertions = {
        str(row["assertion_id"]): _assertion_descriptor(row)
        for row in s1.get("records", [])
        if isinstance(row, Mapping) and row.get("assertion_id")
    }
    return story_evidence, assertions


def build_pilot_inputs(root: Path = ROOT) -> dict[str, dict[str, Any]]:
    """Build the only information the model runner is allowed to receive."""

    sc1 = read_json(root, SC1_PATH)
    review = read_json(root, REVIEW_PATH)
    story_by_id = {str(row["id"]): row for row in sc1.get("stories", [])}
    review_by_id = {str(row["story_id"]): row for row in review.get("records", [])}
    story_evidence, assertions = build_source_catalog(root)
    result: dict[str, dict[str, Any]] = {}
    for story_id in PILOT_STORY_IDS:
        story = story_by_id.get(story_id)
        record = review_by_id.get(story_id)
        if not story or not record:
            raise ValueError(f"IRR0.2 pilot input is missing: {story_id}")
        evidence_refs: set[str] = set()

        def collect_review_refs(value: Any) -> None:
            if isinstance(value, Mapping):
                if isinstance(value.get("evidence_ref"), str):
                    evidence_refs.add(str(value["evidence_ref"]))
                if isinstance(value.get("evidence_refs"), list):
                    evidence_refs.update(str(item) for item in value["evidence_refs"])
                for child in value.values():
                    collect_review_refs(child)
            elif isinstance(value, list):
                for child in value:
                    collect_review_refs(child)

        collect_review_refs(record)
        catalog: dict[str, dict[str, Any]] = {}
        for ref in sorted(evidence_refs):
            descriptor = story_evidence.get(ref) or assertions.get(ref)
            if descriptor is None:
                raise ValueError(f"IRR0.2 evidence is not resolvable: {story_id}/{ref}")
            catalog[ref] = copy.deepcopy(descriptor)
        context_refs = [
            ref for ref in sorted(catalog)
            if catalog[ref].get("source_layer") != "base_text"
        ]
        rounds: list[list[str]] = [[]]
        cumulative: list[str] = []
        for current in record.get("rounds", [])[1:]:
            additions = sorted(
                str(item["evidence_ref"])
                for item in current.get("evidence_added", [])
                if isinstance(item, Mapping) and item.get("evidence_ref")
            )
            cumulative = sorted(set(cumulative).union(additions))
            rounds.append(list(cumulative))
        result[story_id] = {
            "story": {
                "story_id": story_id,
                "chapter": copy.deepcopy(story.get("chapter_display") or story.get("chapter_heading") or story_id),
                "ordinal": int(story.get("ordinal") or 0),
                "text": _story_text(story),
            },
            "evidence_catalog": catalog,
            "context_refs": context_refs,
            "iterative_round_refs": rounds,
        }
    return result


def inference_input(
    pilot: Mapping[str, Any],
    evidence_refs: Iterable[str],
    previous_reading: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    catalog = pilot["evidence_catalog"]
    evidence = [copy.deepcopy(catalog[ref]) for ref in sorted(set(evidence_refs))]
    payload: dict[str, Any] = {
        "story": copy.deepcopy(pilot["story"]),
        "evidence": evidence,
    }
    if previous_reading is not None:
        payload["previous_reading"] = copy.deepcopy(previous_reading)
    return payload


def collect_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, Mapping):
        keys.update(str(key) for key in value)
        for child in value.values():
            keys.update(collect_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(collect_keys(child))
    return keys


def forbidden_input_keys(value: Any) -> list[str]:
    return sorted(collect_keys(value) & FORBIDDEN_INPUT_KEYS)


def model_input_hash(value: Mapping[str, Any]) -> str:
    return sha256_json(value)


def context_refs_for_condition(pilot: Mapping[str, Any], mode: str, round_number: int = 0) -> list[str]:
    if mode == "text_only":
        return []
    if mode == "all_at_once":
        return list(pilot["context_refs"])
    if mode == "iterative":
        rounds = pilot["iterative_round_refs"]
        if round_number < 0 or round_number >= len(rounds):
            raise ValueError(f"invalid IRR0.2 round: {round_number}")
        return list(rounds[round_number])
    raise ValueError(f"unknown IRR0.2 mode: {mode}")


def execution_timestamp(kind: str, requested: str | None = None) -> str:
    if requested:
        return requested
    if kind == "fixture":
        # A fixed ISO value keeps fixture artifacts byte-identical while still
        # satisfying the run-metadata timestamp contract.
        return "1970-01-01T00:00:00Z"
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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
    ) -> Mapping[str, Any]: ...


def _claim(text: str, refs: list[str], status: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"text": text, "evidence_refs": sorted(set(refs))}
    if status:
        result["status"] = status
    return result


def _delta_item(text: str, refs: list[str]) -> dict[str, Any]:
    return {"text": text, "evidence_refs": sorted(set(refs))}


def _split_spans(text: str) -> list[str]:
    pieces = [normalize_text(piece) for piece in re.split(r"[。！？；]", text) if normalize_text(piece)]
    if not pieces:
        return [normalize_text(text) or "原文"]
    # Keep the fixture bounded and derive spans from the supplied Story only.
    selected = pieces[-2:] if len(pieces) > 1 else pieces
    return [piece[-24:] for piece in selected]


class FixtureProvider:
    """A deterministic structural fixture, never presented as model science."""

    provider = "fixture"
    model = "fixture-reading-v0"

    def generate(
        self,
        story: Mapping[str, Any],
        evidence: list[Mapping[str, Any]],
        previous_reading: Mapping[str, Any] | None,
        mode: str,
        round_number: int,
    ) -> Mapping[str, Any]:
        refs = sorted(str(row["evidence_ref"]) for row in evidence)
        text = str(story["text"]["simplified"])
        spans = _split_spans(text)
        hard_negative_signal = any(
            "阿恭" in str(row.get("quote", "")) or "小字" in str(row.get("quote", ""))
            for row in evidence
        )
        if mode == "text_only":
            depth = 1
        elif mode == "all_at_once":
            depth = 2 if refs else 1
        elif round_number == 0:
            depth = 1
        elif hard_negative_signal and round_number > 1:
            depth = 2
        else:
            depth = min(4, 1 + round_number)
        contextual = "所给材料补充了阅读背景，但仍保留需要核对的部分。" if refs else None
        span_rows = [
            {
                "span": span,
                "literal_meaning": span,
                "contextual_meaning": contextual,
                "depth_self_assessment": depth,
                "evidence_refs": refs,
            }
            for span in spans
        ]
        history_refs = refs[:1]
        historical = {
            "era": None,
            "participant_states": [_claim("人物身份以原文表面为准。", history_refs, "observed")],
            "relationship_states": [],
            "prior_events": [],
            "later_events": [],
            "scene_pressure": [_claim("当前场景的压力需要结合原文动作阅读。", history_refs, "contextual")],
            "uncertainties": [_claim("绝对年代仍未由当前输入完全确定。", history_refs, "open")],
        }
        aesthetic = [
            {
                "span": spans[-1],
                "operations": ["selection", "compression"] if len(text) > 30 else ["selection"],
                "omitted_context": [],
                "interpretation": None,
                "evidence_refs": refs,
            }
        ]
        questions = [{
            "question": "还需要什么材料才能把场景放入更窄的时间范围？",
            "evidence_refs": sorted(set(refs)),
        }]
        new_questions = questions if mode == "iterative" and round_number > 0 else []
        delta: dict[str, Any] | None = None
        if mode == "iterative" and round_number > 0:
            previous_depth = 0
            if previous_reading:
                previous_spans = previous_reading.get("text_reading", {}).get("salient_spans", [])
                if previous_spans:
                    previous_depth = max(int(row.get("depth_self_assessment", 0)) for row in previous_spans)
            delta = {
                "historical_changes": [_delta_item("新增材料进入当前阅读条件。", refs)] if refs else [],
                "newly_salient_spans": [_delta_item(spans[-1], refs)] if depth > previous_depth else [],
                "reinterpretations": [_delta_item("重新检查原文动作与语境的关系。", refs)] if depth > previous_depth else [],
                "newly_understood_omissions": [],
                "new_connections": [],
                "resolved_questions": [],
                "new_questions": [_delta_item("新增材料是否改变了场景重心？", refs)],
            }
        return {
            "historical_reading": historical,
            "text_reading": {"salient_spans": span_rows},
            "aesthetic_reading": aesthetic,
            "open_questions": questions,
            "new_questions": new_questions,
            "reading_delta": delta,
        }


class ModuleProvider:
    """Adapter for a user-supplied provider module.

    The module is named by IRR0_2_PROVIDER_MODULE and must expose
    ``run_reading(payload)``.  This keeps credentials and provider SDK choices
    outside the repository.
    """

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
    ) -> Mapping[str, Any]:
        payload = {
            "story": copy.deepcopy(story),
            "evidence": copy.deepcopy(evidence),
            "previous_reading": copy.deepcopy(previous_reading),
            "mode": mode,
            "round": round_number,
            "prompt_version": "irr0.2-v0",
            "output_schema": "schema/model-iterative-reading.schema.json",
            "task_instructions": "Read only the supplied Story and evidence; preserve uncertainty and return the structured model-reading schema.",
        }
        return self._function(payload)


def provider_from_environment(
    fixture: bool = False,
    provider_module: str | None = None,
    model: str | None = None,
) -> ReadingProvider:
    module_name = provider_module or os.environ.get("IRR0_2_PROVIDER_MODULE")
    resolved_model = model or os.environ.get("IRR0_2_MODEL") or "external-model"
    if fixture or not module_name:
        return FixtureProvider()
    return ModuleProvider(module_name, resolved_model)


def run_reading(
    story: Mapping[str, Any],
    evidence: list[Mapping[str, Any]],
    previous_reading: Mapping[str, Any] | None = None,
    mode: str = "text_only",
    provider: ReadingProvider | None = None,
    round_number: int = 0,
) -> Mapping[str, Any]:
    """Provider-independent runner entry point used by the CLI and tests."""

    selected = provider or FixtureProvider()
    return selected.generate(story, evidence, previous_reading, mode, round_number)
