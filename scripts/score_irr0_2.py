#!/usr/bin/env python3
"""Deterministically score IRR0.2 outputs against the frozen IRR0.1 Gold.

These are transparent annotation-overlap diagnostics, not an LLM judge and
not a historical-truth score.  Gold is read only in this post-inference
stage.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

try:
    from irr0_2_common import (
        GOLD_PATH,
        MODES,
        OUTPUT_DIR,
        PILOT_STORY_IDS,
        PUBLIC_OUTPUT_DIR,
        ROOT,
        build_pilot_inputs,
        read_json,
        sha256_file,
        stable_json,
        write_json,
    )
except ModuleNotFoundError:
    from scripts.irr0_2_common import (
        GOLD_PATH,
        MODES,
        OUTPUT_DIR,
        PILOT_STORY_IDS,
        PUBLIC_OUTPUT_DIR,
        ROOT,
        build_pilot_inputs,
        read_json,
        sha256_file,
        stable_json,
        write_json,
    )


METRIC_KEYS = (
    "historical_score",
    "critical_span_score",
    "linguistic_salience_score",
    "aesthetic_operation_score",
    "omission_context_score",
    "uncertainty_score",
    "distraction_error_count",
)


def text_tokens(value: Any) -> set[str]:
    text = str(value or "")
    chinese = {char for char in text if "\u3400" <= char <= "\u9fff"}
    latin = set(re.findall(r"[A-Za-z0-9]{2,}", text.lower()))
    return chinese | latin


def flatten_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return " ".join(flatten_text(child) for child in value.values())
    if isinstance(value, list):
        return " ".join(flatten_text(child) for child in value)
    return ""


def evidence_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, Mapping):
        current = value.get("evidence_refs")
        if isinstance(current, list):
            refs.update(str(item) for item in current)
        for child in value.values():
            refs.update(evidence_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.update(evidence_refs(child))
    return refs


def average(values: Iterable[float]) -> float:
    rows = list(values)
    return round(sum(rows) / len(rows), 6) if rows else 0.0


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def target_gold(record: Mapping[str, Any], mode: str, round_number: int = 0) -> Mapping[str, Any]:
    if mode == "text_only":
        return record["rounds"][0]
    if mode == "all_at_once":
        return record["rounds"][-1]
    return record["rounds"][round_number]


def model_depth(output: Mapping[str, Any]) -> float:
    rows = output.get("text_reading", {}).get("salient_spans", [])
    return average(float(row.get("depth_self_assessment", 0)) for row in rows)


def gold_depth(gold_round: Mapping[str, Any]) -> float:
    rows = [row for row in gold_round.get("text_reading", {}).get("salient_spans", []) if row.get("critical")]
    return average(float(row.get("depth", 0)) for row in rows)


def critical_score(output: Mapping[str, Any], gold_record: Mapping[str, Any], gold_round: Mapping[str, Any]) -> float:
    model_spans = [str(row.get("span", "")) for row in output.get("text_reading", {}).get("salient_spans", [])]
    serialized = flatten_text(output)
    hits = 0
    for target in gold_record.get("critical_spans", []):
        if any(str(target) in span or span in str(target) for span in model_spans) or str(target) in serialized:
            hits += 1
    return round(hits / len(gold_record.get("critical_spans", [])), 6) if gold_record.get("critical_spans") else 0.0


def historical_score(output: Mapping[str, Any], gold_round: Mapping[str, Any], allowed_refs: set[str]) -> float:
    gold_history = gold_round.get("historical_reading", {})
    gold_text = flatten_text(gold_history)
    model_text = flatten_text(output.get("historical_reading", {}))
    token_recall = len(text_tokens(gold_text) & text_tokens(model_text)) / max(1, len(text_tokens(gold_text)))
    target_refs = evidence_refs(gold_history)
    model_refs = evidence_refs(output.get("historical_reading", {}))
    ref_recall = len(target_refs & model_refs & allowed_refs) / max(1, len(target_refs))
    return round(min(1.0, (token_recall + ref_recall) / 2), 6)


def aesthetic_score(output: Mapping[str, Any], gold_round: Mapping[str, Any]) -> float:
    model_ops = {
        str(operation)
        for row in output.get("aesthetic_reading", [])
        for operation in row.get("operations", [])
    }
    gold_ops = {
        str(operation)
        for row in gold_round.get("aesthetic_reading", [])
        for operation in row.get("operations", [])
    }
    return round(jaccard(model_ops, gold_ops), 6)


def omission_score(output: Mapping[str, Any], gold_round: Mapping[str, Any]) -> float:
    model_items = {
        token
        for row in output.get("aesthetic_reading", [])
        for item in row.get("omitted_context", [])
        for token in text_tokens(item)
    }
    gold_items = {
        token
        for row in gold_round.get("aesthetic_reading", [])
        for item in row.get("omitted_context", [])
        for token in text_tokens(item)
    }
    if not gold_items:
        return 1.0 if not model_items else 0.5
    return round(len(model_items & gold_items) / len(gold_items), 6)


def uncertainty_score(output: Mapping[str, Any], gold_round: Mapping[str, Any]) -> float:
    model_questions = output.get("open_questions", [])
    model_uncertainties = output.get("historical_reading", {}).get("uncertainties", [])
    gold_questions = gold_round.get("open_questions", [])
    gold_uncertainties = gold_round.get("historical_reading", {}).get("uncertainties", [])
    model_count = len(model_questions) + len(model_uncertainties)
    gold_count = len(gold_questions) + len(gold_uncertainties)
    if gold_count == 0:
        return 1.0 if model_count == 0 else 0.5
    return round(min(1.0, model_count / gold_count), 6)


def distraction_errors(output: Mapping[str, Any], allowed_refs: set[str]) -> int:
    referenced = evidence_refs(output)
    return len(referenced - allowed_refs)


def score_record(
    output: Mapping[str, Any],
    gold_record: Mapping[str, Any],
    gold_round: Mapping[str, Any],
    allowed_refs: set[str],
) -> dict[str, Any]:
    metrics = {
        "historical_score": historical_score(output, gold_round, allowed_refs),
        "critical_span_score": critical_score(output, gold_record, gold_round),
        "linguistic_salience_score": round(
            critical_score(output, gold_record, gold_round) * model_depth(output) / 4,
            6,
        ),
        "aesthetic_operation_score": aesthetic_score(output, gold_round),
        "omission_context_score": omission_score(output, gold_round),
        "uncertainty_score": uncertainty_score(output, gold_round),
        "distraction_error_count": distraction_errors(output, allowed_refs),
    }
    return {
        "metrics": metrics,
        "predicted_reading_depth": round(model_depth(output), 6),
        "gold_reading_depth": round(gold_depth(gold_round), 6),
    }


def model_mrg(output: Mapping[str, Any], previous: Mapping[str, Any] | None, allowed_refs: set[str]) -> dict[str, float]:
    if previous is None:
        return {key: 0.0 for key in ("G_H", "G_L", "G_A", "G_C", "G_U", "G_D", "MRG")}
    delta = output.get("reading_delta") or {}
    depth_gain = max(0.0, model_depth(output) - model_depth(previous)) / 3
    values = {
        "G_H": min(1.0, len(delta.get("historical_changes", [])) / 3),
        "G_L": min(1.0, depth_gain),
        "G_A": min(1.0, (len(delta.get("newly_understood_omissions", [])) + len(delta.get("reinterpretations", []))) / 2),
        "G_C": min(1.0, len(delta.get("new_connections", [])) / 2),
        "G_U": min(1.0, len(delta.get("resolved_questions", [])) / 2),
        "G_D": min(1.0, distraction_errors(output, allowed_refs) / 2),
    }
    values["MRG"] = sum(values[key] for key in ("G_H", "G_L", "G_A", "G_C", "G_U")) - values["G_D"]
    return {key: round(float(value), 6) for key, value in values.items()}


def score_all(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    gold = read_json(root, GOLD_PATH)
    gold_by_id = {str(row["story_id"]): row for row in gold["records"]}
    pilots = build_pilot_inputs(root)
    documents = {mode: read_json(root, OUTPUT_DIR / file_name) for mode, file_name in {
        "text_only": "text-only.json",
        "all_at_once": "all-at-once.json",
        "iterative": "iterative.json",
    }.items()}
    scored: dict[str, dict[str, Any]] = {mode: {} for mode in MODES}
    per_story: dict[str, Any] = {}
    for mode in MODES:
        records = {str(row["story_id"]): row for row in documents[mode].get("records", [])}
        for story_id in PILOT_STORY_IDS:
            if story_id not in records:
                raise ValueError(f"IRR0.2 output missing Story: {mode}/{story_id}")
            gold_record = gold_by_id[story_id]
            allowed = set(pilots[story_id]["context_refs"])
            if mode == "text_only":
                row = records[story_id]
                scored_row = score_record(row["output"], gold_record, target_gold(gold_record, mode), allowed)
                scored[mode][story_id] = {"condition": mode, **scored_row}
            elif mode == "all_at_once":
                row = records[story_id]
                scored_row = score_record(row["output"], gold_record, target_gold(gold_record, mode), allowed)
                scored[mode][story_id] = {"condition": mode, **scored_row}
            else:
                rounds: list[dict[str, Any]] = []
                previous_output: Mapping[str, Any] | None = None
                for current in records[story_id]["rounds"]:
                    round_number = int(current["round"])
                    output = current["output"]
                    refs = set(pilots[story_id]["iterative_round_refs"][round_number])
                    scored_row = score_record(output, gold_record, target_gold(gold_record, mode, round_number), refs)
                    # Learning/degradation is compared against one fixed
                    # final Gold target.  Otherwise a changing Gold target
                    # would make a round look worse merely because the target
                    # itself became more demanding.
                    fixed_target = score_record(output, gold_record, gold_record["rounds"][-1], refs)
                    scored_row["fixed_final_target_metrics"] = fixed_target["metrics"]
                    scored_row["round"] = round_number
                    scored_row["model_gain_vector"] = model_mrg(output, previous_output, refs)
                    scored_row["gold_gain_vector"] = target_gold(gold_record, mode, round_number).get("gain_vector", {})
                    rounds.append(scored_row)
                    previous_output = output
                scored[mode][story_id] = {"condition": mode, "rounds": rounds, "final": rounds[-1]}
            per_story.setdefault(story_id, {"story_id": story_id, "conditions": {}})
            per_story[story_id]["conditions"][mode] = scored[mode][story_id]

    summaries: dict[str, Any] = {}
    for mode in MODES:
        rows: list[Mapping[str, Any]] = []
        for story_id in PILOT_STORY_IDS:
            row = scored[mode][story_id]
            rows.append(row["final"] if mode == "iterative" else row)
        summaries[mode] = {
            key: average(float(row["metrics"][key]) for row in rows)
            for key in METRIC_KEYS
        }
        summaries[mode]["story_count"] = len(rows)

    pairwise: dict[str, Any] = {}
    pairs = (("text_only", "all_at_once"), ("text_only", "iterative"), ("all_at_once", "iterative"))
    for left, right in pairs:
        deltas: dict[str, float] = {}
        for key in METRIC_KEYS:
            left_value = summaries[left][key]
            right_value = summaries[right][key]
            deltas[key] = round(float(right_value) - float(left_value), 6)
        pairwise[f"{left}_vs_{right}"] = {
            "delta_definition": f"{right} - {left}; positive is higher except distraction_error_count",
            "deltas": deltas,
        }

    iterative_analysis: dict[str, Any] = {"stories": {}, "monotonic_stories": [], "hard_negative_cases": [], "degradation_cases": []}
    for story_id in PILOT_STORY_IDS:
        rounds = per_story[story_id]["conditions"]["iterative"]["rounds"]
        depths = [float(row["predicted_reading_depth"]) for row in rounds]
        monotonic = all(left <= right for left, right in zip(depths, depths[1:]))
        iterative_analysis["stories"][story_id] = {
            "predicted_depths": depths,
            "gold_depths": [float(row["gold_reading_depth"]) for row in rounds],
            "monotonic_non_decreasing": monotonic,
            "strict_progression": all(left < right for left, right in zip(depths, depths[1:])),
        }
        if monotonic:
            iterative_analysis["monotonic_stories"].append(story_id)
        gold_record = gold_by_id[story_id]
        for current in gold_record["rounds"]:
            if any(item.get("expected_role") == "hard_negative" for item in current.get("evidence_added", [])):
                round_number = int(current["round"])
                before = depths[round_number - 1] if round_number else depths[round_number]
                after = depths[round_number]
                iterative_analysis["hard_negative_cases"].append({
                    "story_id": story_id,
                    "round": round_number,
                    "recognized": after <= before,
                    "model_depth_before": before,
                    "model_depth_after": after,
                })
        aggregate = [
            average(float(round_row["fixed_final_target_metrics"][key]) for key in METRIC_KEYS if key != "distraction_error_count")
            for round_row in rounds
        ]
        for number, (before, after) in enumerate(zip(aggregate, aggregate[1:]), start=1):
            if after < before:
                iterative_analysis["degradation_cases"].append({
                    "story_id": story_id,
                    "transition": f"R{number - 1}->R{number}",
                    "before": round(before, 6),
                    "after": round(after, 6),
                })

    execution_kinds = {documents[mode].get("execution", {}).get("execution_kind") for mode in MODES}
    fixture_only = execution_kinds == {"fixture"}
    comparison = {
        "schema": "irr0.2-comparison",
        "stage": "IRR0.2",
        "schema_version": "v0",
        "scientific_status": "fixture_pipeline_only" if fixture_only else "provider_output_scored",
        "scoring_policy": {
            "primary_judge": "deterministic annotation overlap and structure checks; no LLM judge",
            "historical_score": "evidence-reference and grounded-claim token coverage against condition-matched Gold round",
            "mrg": "diagnostic vector; never an authoritative scalar or historical-importance score",
        },
        "scope": {"story_count": len(PILOT_STORY_IDS), "story_ids": list(PILOT_STORY_IDS)},
        "condition_summary": summaries,
        "pairwise": pairwise,
        "iterative_analysis": iterative_analysis,
        "questions": {
            "context_improves_over_text_only": pairwise["text_only_vs_iterative"]["deltas"]["historical_score"] > 0,
            "iterative_outperforms_all_at_once": pairwise["all_at_once_vs_iterative"]["deltas"]["historical_score"] > 0,
            "hard_negative_recognized": all(row["recognized"] for row in iterative_analysis["hard_negative_cases"]),
            "any_degradation": bool(iterative_analysis["degradation_cases"]),
        },
        "source_hashes": {
            GOLD_PATH.as_posix(): sha256_file(root, GOLD_PATH),
        },
    }
    report = {
        "schema": "irr0.2-per-story-report",
        "stage": "IRR0.2",
        "schema_version": "v0",
        "records": [per_story[story_id] for story_id in PILOT_STORY_IDS],
        "source_hashes": comparison["source_hashes"],
    }
    return comparison, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    comparison, report = score_all(args.root)
    write_json(args.root, OUTPUT_DIR / "comparison.json", comparison)
    write_json(args.root, OUTPUT_DIR / "per-story-report.json", report)
    write_json(args.root, PUBLIC_OUTPUT_DIR / "comparison.json", comparison)
    write_json(args.root, PUBLIC_OUTPUT_DIR / "per-story-report.json", report)
    print(stable_json({"comparison": "data/derived/irr0-2/comparison.json", "status": comparison["scientific_status"]}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
