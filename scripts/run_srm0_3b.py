#!/usr/bin/env python3
"""Run the isolated SRM0.3B two-completion semantic-delta pilot.

The model supplies only reading gaps and commentary deltas.  Python freezes
the first completion's question fields and derives persistent state.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ds1_common import ROOT, sha256_file, stable_json, write_json  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402
from srm0_1_common import parse_json_content  # noqa: E402
from srm0_3b_common import (  # noqa: E402
    COMMENTARY_SYSTEM_PROMPT,
    INITIAL_SYSTEM_PROMPT,
    MODEL,
    OUTPUT_ROOT,
    PROMPT_VERSION,
    PROVIDER,
    REVIEW_PATH,
    SCHEMA_VERSION,
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
    review_template,
    stable_json,
    validate_initial,
    validate_semantic_delta,
)


PREVIOUS_OUTPUT_ROOT = Path("data/generated/srm0") / STORY_ID / "commentary-resolution"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", default=STORY_ID, choices=[STORY_ID])
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--fixture", action="store_true", help="use local contract fixtures without API calls")
    parser.add_argument("--replay-existing", action="store_true", help="rebuild projections from saved raw outputs")
    return parser.parse_args()


def response_content(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("DeepSeek response has no choices")
    message = choices[0].get("message", {}) if isinstance(choices[0], Mapping) else {}
    content = message.get("content") if isinstance(message, Mapping) else None
    if not isinstance(content, str) or not content.strip():
        raise ValueError("DeepSeek response has no JSON content")
    return content


def usage_fields(response: Mapping[str, Any] | None) -> dict[str, Any]:
    usage = response.get("usage", {}) if isinstance(response, Mapping) else {}
    if not isinstance(usage, Mapping):
        usage = {}
    return {
        "prompt_tokens": usage.get("prompt_tokens"),
        "prompt_cache_hit_tokens": usage.get("prompt_cache_hit_tokens"),
        "prompt_cache_miss_tokens": usage.get("prompt_cache_miss_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "raw_usage": dict(usage),
    }


def fixture_initial(material: Mapping[str, Any]) -> dict[str, Any]:
    span = str(material["entry"]["story_text"]).splitlines()[0]
    return {
        "gaps": [
            {
                "question_id": "Q1",
                "story_span": span,
                "gap": "『知管時任』具体指何种职任与职责？",
            }
        ]
    }


def fixture_delta(material: Mapping[str, Any], initial: Mapping[str, Any]) -> dict[str, Any]:
    gap = initial["gaps"][0]
    note = material["later_notes"][-1]
    quote = str(note["text"])[:16]
    return {
        "updates": [
            {
                "question_id": gap["question_id"],
                "answered_aspects": [
                    {
                        "claim": "所附笺疏提供了与相关职任及掌选状态相连的考证线索。",
                        "evidence": [{"ref": note["ref"], "quote": quote}],
                    }
                ],
                "unanswered_aspects": [],
                "conflicts": [],
                "reading_sufficient": True,
                "historical_verification_open": True,
                "remaining_reading_gap": None,
                "refined_question": None,
            }
        ],
        "relation_candidates": [],
        "appraisal_candidates": [],
    }


def _load_saved_output(path: Path) -> tuple[dict[str, Any], dict[str, Any] | None, str]:
    document = json.loads(path.read_text(encoding="utf-8"))
    raw_content = str(document.get("raw_content") or "")
    if not raw_content:
        raise ValueError(f"saved output has no raw_content: {path}")
    raw, _ = parse_json_content(raw_content)
    response = document.get("raw_response")
    return raw, dict(response) if isinstance(response, Mapping) else None, raw_content


def _model_output(
    *,
    stage: str,
    raw: Mapping[str, Any],
    raw_content: str | None,
    response: Mapping[str, Any] | None,
    normalized: Mapping[str, Any],
    validation_errors: list[str],
    repair: str,
    run_id: str,
    execution_kind: str,
) -> dict[str, Any]:
    return {
        "schema": "srm0-3b-model-output",
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "artifact_kind": "generated_experimental_output",
        "story_id": STORY_ID,
        "run_id": run_id,
        "execution_kind": execution_kind,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "json_repair": repair,
        "json_repair_count": 0 if repair in {"none", "fixture"} else 1,
        "raw_response": dict(response or {}),
        "raw_content": raw_content,
        "raw_output": dict(raw),
        "normalized_output": dict(normalized),
        "validation_errors": sorted(set(validation_errors)),
        "api_usage": usage_fields(response),
        "canonical_write_back": False,
        "external_search_performed": False,
    }


def _write_events(events: list[dict[str, Any]]) -> None:
    path = ROOT / OUTPUT_ROOT / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for event in events),
        encoding="utf-8",
    )


def _raw_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _explanation_leaks(value: Any) -> int:
    patterns = (
        "可能是", "可能为", "可能指", "应为", "應為", "应该是", "應該是",
        "即是", "即为", "即為", "也就是", "换言之", "換言之", "意为", "意為",
        "解释为", "解釋為", "可理解为", "可理解為", "实为", "實為", "当指", "當指",
    )
    if not isinstance(value, str):
        return 0
    return int(any(pattern in value for pattern in patterns))


def build_comparison(initial_output: Mapping[str, Any], delta_output: Mapping[str, Any], usage: Mapping[str, Any]) -> dict[str, Any]:
    current = initial_output.get("normalized_output", {})
    current_gaps = current.get("gaps", []) if isinstance(current, Mapping) else []
    current_errors = delta_output.get("validation_errors", [])
    previous_main = _raw_json(ROOT / PREVIOUS_OUTPUT_ROOT / "round-00-main-output.json")
    previous_normalized = previous_main.get("normalized_output", {}) if isinstance(previous_main, Mapping) else {}
    previous_questions = previous_normalized.get("questions", []) if isinstance(previous_normalized, Mapping) else []
    previous_leaks = 0
    for row in previous_questions if isinstance(previous_questions, list) else []:
        if isinstance(row, Mapping):
            previous_leaks += _explanation_leaks(row.get("question"))
            previous_leaks += _explanation_leaks(row.get("why_unclear_from_main_text"))
    state = usage.get("derived_state", {}) if isinstance(usage.get("derived_state"), Mapping) else {}
    questions = state.get("questions", []) if isinstance(state, Mapping) else []
    counts = {name: 0 for name in ("substantially_explained", "partially_explained", "conflicted", "unexplained")}
    stop_count = refined_count = external_count = 0
    for row in questions if isinstance(questions, list) else []:
        if not isinstance(row, Mapping):
            continue
        if row.get("state") in counts:
            counts[str(row["state"])] += 1
        if row.get("next_action") == "stop":
            stop_count += 1
        elif row.get("next_action") == "refine_question":
            refined_count += 1
        elif row.get("next_action") == "external_search":
            external_count += 1
    missing_fields = [
        error for error in current_errors
        if any(term in str(error) for term in ("required", "array", "boolean", "semantic delta", "question_id"))
    ]
    evidence_failures = [error for error in current_errors if "evidence" in str(error) or "quote" in str(error)]
    return {
        "schema": "srm0-3b-comparison-with-0-3a",
        "schema_version": SCHEMA_VERSION,
        "story_id": STORY_ID,
        "completion_1_question_count": len(current_gaps) if isinstance(current_gaps, list) else 0,
        "completion_1_average_gap_chars": round(
            sum(len(str(row.get("gap") or "")) for row in current_gaps if isinstance(row, Mapping)) / len(current_gaps), 2
        ) if current_gaps else 0,
        "completion_1_explanation_leak_count": sum(_explanation_leaks(row.get("gap")) for row in current_gaps if isinstance(row, Mapping)),
        "previous_0_3a_question_count": len(previous_questions) if isinstance(previous_questions, list) else 0,
        "previous_0_3a_explanation_leak_count": previous_leaks,
        "completion_2_missing_required_semantic_fields": len(missing_fields),
        "evidence_validation_failures": len(evidence_failures),
        **counts,
        "stop_count": stop_count,
        "refined_question_count": refined_count,
        "external_search_recommended_count": external_count,
        "completion_1_tokens": (usage.get("completion_1_api_usage") or {}).get("total_tokens"),
        "completion_2_tokens": (usage.get("completion_2_api_usage") or {}).get("total_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "canonical_write_back": False,
        "external_search_performed": False,
    }


def _normalization_count(initial_raw: Mapping[str, Any], initial: Mapping[str, Any], delta_raw: Mapping[str, Any], delta: Mapping[str, Any]) -> int:
    count = 0
    raw_gaps = initial_raw.get("gaps", []) if isinstance(initial_raw.get("gaps"), list) else []
    normalized_gaps = initial.get("gaps", []) if isinstance(initial.get("gaps"), list) else []
    for raw, normalized in zip(raw_gaps, normalized_gaps):
        if isinstance(raw, Mapping) and isinstance(normalized, Mapping) and str(raw.get("story_span") or raw.get("span") or "").strip() != normalized.get("story_span"):
            count += 1
    raw_updates = delta_raw.get("updates", []) if isinstance(delta_raw.get("updates"), list) else []
    normalized_updates = delta.get("updates", []) if isinstance(delta.get("updates"), list) else []
    for raw_update, normalized_update in zip(raw_updates, normalized_updates):
        if not isinstance(raw_update, Mapping) or not isinstance(normalized_update, Mapping):
            continue
        for field in ("answered_aspects", "conflicts"):
            raw_groups = raw_update.get(field, []) if isinstance(raw_update.get(field), list) else []
            norm_groups = normalized_update.get(field, []) if isinstance(normalized_update.get(field), list) else []
            for raw_group, norm_group in zip(raw_groups, norm_groups):
                if not isinstance(raw_group, Mapping) or not isinstance(norm_group, Mapping):
                    continue
                raw_evidence = raw_group.get("evidence", []) if isinstance(raw_group.get("evidence"), list) else []
                norm_evidence = norm_group.get("evidence", []) if isinstance(norm_group.get("evidence"), list) else []
                for raw_item, norm_item in zip(raw_evidence, norm_evidence):
                    if isinstance(raw_item, Mapping) and isinstance(norm_item, Mapping) and str(raw_item.get("quote") or "").strip() != norm_item.get("quote"):
                        count += 1
    return count


def _artifact_hashes(names: list[str]) -> dict[str, str]:
    return {name: sha256_file(ROOT, OUTPUT_ROOT / name) for name in names}


def run(args: argparse.Namespace) -> int:
    if args.replay_existing and args.fixture:
        raise SystemExit("--replay-existing cannot be combined with --fixture")
    material = resolve_commentary_material(ROOT)
    run_id = "srm0-3b-" + str(material["entry"]["entry_sha256"])[:16]
    if args.replay_existing:
        existing_manifest_path = ROOT / OUTPUT_ROOT / "manifest.json"
        try:
            existing_manifest = json.loads(existing_manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing_manifest = {}
        execution_kind = str(existing_manifest.get("execution_kind") or "replay")
    else:
        execution_kind = "fixture" if args.fixture else "real_model"
    initial_messages = build_initial_messages(material)
    write_json(
        ROOT,
        OUTPUT_ROOT / "round-00-main-input.json",
        {
            "schema": "srm0-3b-main-input",
            "schema_version": SCHEMA_VERSION,
            "story_id": STORY_ID,
            "run_id": run_id,
            "execution_kind": execution_kind,
            "model": MODEL,
            "provider": PROVIDER,
            "prompt_version": PROMPT_VERSION,
            "parameters": {"temperature": 0, "response_format": {"type": "json_object"}, "tools": []},
            "messages": initial_messages,
            "canonical_write_back": False,
            "external_search_performed": False,
        },
    )

    initial_response: dict[str, Any] | None = None
    initial_content: str | None = None
    if args.fixture:
        initial_raw = fixture_initial(material)
        initial_content = stable_json(initial_raw)
        initial_repair = "fixture"
    elif args.replay_existing:
        initial_raw, initial_response, initial_content = _load_saved_output(ROOT / OUTPUT_ROOT / "round-00-main-output.json")
        initial_raw, initial_repair = parse_json_content(initial_content)
    else:
        initial_response = call_deepseek(
            initial_messages,
            model=MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            tools=[],
            thinking={"type": "disabled"},
            timeout=args.timeout,
        )
        initial_content = response_content(initial_response)
        initial_raw, initial_repair = parse_json_content(initial_content)
    initial_normalized = normalize_initial(initial_raw, material)
    initial_errors = validate_initial(initial_raw, initial_normalized, material)
    initial_output = _model_output(
        stage="main_text_gap_discovery",
        raw=initial_raw,
        raw_content=initial_content,
        response=initial_response,
        normalized=initial_normalized,
        validation_errors=initial_errors,
        repair=initial_repair,
        run_id=run_id,
        execution_kind=execution_kind,
    )
    write_json(ROOT, OUTPUT_ROOT / "round-00-main-output.json", initial_output)

    frozen_questions = [
        {"question_id": row.get("question_id"), "gap": row.get("gap")}
        for row in initial_normalized.get("gaps", [])
        if isinstance(row, Mapping)
    ]
    commentary_messages = build_commentary_messages(material, frozen_questions)
    write_json(
        ROOT,
        OUTPUT_ROOT / "round-01-commentary-input.json",
        {
            "schema": "srm0-3b-commentary-input",
            "schema_version": SCHEMA_VERSION,
            "story_id": STORY_ID,
            "run_id": run_id,
            "execution_kind": execution_kind,
            "model": MODEL,
            "provider": PROVIDER,
            "prompt_version": PROMPT_VERSION,
            "parameters": {"temperature": 0, "response_format": {"type": "json_object"}, "tools": []},
            "messages": commentary_messages,
            "canonical_write_back": False,
            "external_search_performed": False,
        },
    )

    commentary_response: dict[str, Any] | None = None
    commentary_content: str | None = None
    if args.fixture:
        commentary_raw = fixture_delta(material, initial_normalized)
        commentary_content = stable_json(commentary_raw)
        commentary_repair = "fixture"
    elif args.replay_existing:
        commentary_raw, commentary_response, commentary_content = _load_saved_output(ROOT / OUTPUT_ROOT / "round-01-commentary-output.json")
        commentary_raw, commentary_repair = parse_json_content(commentary_content)
    else:
        commentary_response = call_deepseek(
            commentary_messages,
            model=MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            tools=[],
            thinking={"type": "disabled"},
            timeout=args.timeout,
        )
        commentary_content = response_content(commentary_response)
        commentary_raw, commentary_repair = parse_json_content(commentary_content)
    commentary_normalized = normalize_semantic_delta(commentary_raw, material, initial_normalized)
    commentary_errors = validate_semantic_delta(commentary_raw, commentary_normalized, material, initial_normalized)
    commentary_output = _model_output(
        stage="commentary_semantic_delta",
        raw=commentary_raw,
        raw_content=commentary_content,
        response=commentary_response,
        normalized=commentary_normalized,
        validation_errors=commentary_errors,
        repair=commentary_repair,
        run_id=run_id,
        execution_kind=execution_kind,
    )
    write_json(ROOT, OUTPUT_ROOT / "round-01-commentary-output.json", commentary_output)

    all_errors = sorted(set(initial_errors + commentary_errors))
    initial_api = usage_fields(initial_response)
    commentary_api = usage_fields(commentary_response)
    derived_state: dict[str, Any] = {}
    derived_events: list[dict[str, Any]] = []
    if not all_errors:
        derived_state = derive_state(initial_normalized, commentary_normalized)
        derived_events = derive_events(initial_normalized, commentary_normalized, derived_state)
        write_json(ROOT, OUTPUT_ROOT / "research-state.json", derived_state)
        _write_events(derived_events)
    else:
        derived_state = {
            "schema": "srm0-3b-research-state",
            "schema_version": SCHEMA_VERSION,
            "story_id": STORY_ID,
            "stage": "commentary_resolution_failed",
            "questions": [],
            "relation_candidates": [],
            "appraisal_candidates": [],
            "validation_errors": all_errors,
            "canonical_write_back": False,
            "external_search_performed": False,
        }
        derived_events = [{"event": "experiment_validation_failed", "validation_errors": all_errors}]
        write_json(ROOT, OUTPUT_ROOT / "research-state.json", derived_state)
        _write_events(derived_events)

    raw_payload_1 = stable_json(build_initial_payload(material))
    raw_payload_2 = stable_json(build_commentary_payload(material, frozen_questions))
    metrics = {
        "main_text_chars": material["main_text_chars"],
        "liu_chars": material["liu_chars"],
        "later_commentary_chars": material["later_commentary_chars"],
        "duplicate_commentary_chars_removed": material["duplicate_commentary_chars_removed"],
        "completion_1_instruction_chars": len(INITIAL_SYSTEM_PROMPT),
        "completion_2_instruction_chars": len(COMMENTARY_SYSTEM_PROMPT),
        "completion_1_payload_chars": len(raw_payload_1),
        "completion_2_payload_chars": len(raw_payload_2),
        "completion_1_serialized_prompt_chars": sum(len(str(message.get("content", ""))) for message in initial_messages),
        "completion_2_serialized_prompt_chars": sum(len(str(message.get("content", ""))) for message in commentary_messages),
    }
    total_tokens = sum(value or 0 for value in (initial_api.get("total_tokens"), commentary_api.get("total_tokens")))
    usage = {
        "schema": "srm0-3b-usage",
        "schema_version": SCHEMA_VERSION,
        "story_id": STORY_ID,
        "run_id": run_id,
        "execution_kind": execution_kind,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "completion_1_api_usage": initial_api,
        "completion_2_api_usage": commentary_api,
        "total_tokens": total_tokens,
        "character_metrics": metrics,
        "json_repair_count": initial_output["json_repair_count"] + commentary_output["json_repair_count"],
        "normalization_count": _normalization_count(initial_raw, initial_normalized, commentary_raw, commentary_normalized),
        "derived_state": derived_state,
        "validation_errors": all_errors,
        "canonical_write_back": False,
        "external_search_performed": False,
        "tool_call_count": 0,
    }
    write_json(ROOT, OUTPUT_ROOT / "usage.json", usage)
    comparison = build_comparison(initial_output, commentary_output, usage)
    write_json(ROOT, OUTPUT_ROOT / "comparison-with-0.3a.json", comparison)
    if not (ROOT / REVIEW_PATH).is_file():
        write_json(ROOT, REVIEW_PATH, review_template())

    artifact_names = [
        "round-00-main-input.json",
        "round-00-main-output.json",
        "round-01-commentary-input.json",
        "round-01-commentary-output.json",
        "research-state.json",
        "events.jsonl",
        "comparison-with-0.3a.json",
        "usage.json",
    ]
    manifest = {
        "schema": "srm0-3b-manifest",
        "schema_version": SCHEMA_VERSION,
        "story_id": STORY_ID,
        "run_id": run_id,
        "execution_kind": execution_kind,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "source_artifacts": material["source_artifacts"],
        "artifact_hashes": _artifact_hashes(artifact_names),
        "completion_count": 0 if execution_kind in {"fixture", "replay"} else 2,
        "tool_call_count": 0,
        "external_search_performed": False,
        "canonical_write_back": False,
        "validation_errors": all_errors,
    }
    write_json(ROOT, OUTPUT_ROOT / "manifest.json", manifest)
    if all_errors:
        print("SRM0.3B validation failed")
        for error in all_errors:
            print(f"- {error}")
        return 1
    print(f"SRM0.3B completed ({execution_kind})")
    print(f"gaps: {len(initial_normalized['gaps'])}")
    print(f"updates: {len(commentary_normalized['updates'])}")
    print(f"tokens: {total_tokens}")
    print(f"state: {(OUTPUT_ROOT / 'research-state.json').as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
