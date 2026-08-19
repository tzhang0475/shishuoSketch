#!/usr/bin/env python3
"""Score IRR0.3 model outputs and span transitions without an LLM judge."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from irr0_3_common import (
        CONTEXT_REVIEW_PATH,
        MODES,
        OUTPUT_DIR,
        PILOT_STORY_IDS,
        PUBLIC_OUTPUT_DIR,
        ROOT,
        build_irr0_3_inputs,
        load_context_review,
        output_path,
        read_json,
        stable_json,
        write_json,
    )
except ModuleNotFoundError:
    from scripts.irr0_3_common import (
        CONTEXT_REVIEW_PATH,
        MODES,
        OUTPUT_DIR,
        PILOT_STORY_IDS,
        PUBLIC_OUTPUT_DIR,
        ROOT,
        build_irr0_3_inputs,
        load_context_review,
        output_path,
        read_json,
        stable_json,
        write_json,
    )

try:
    from score_irr0_2 import (
        METRIC_KEYS,
        distraction_errors,
        score_record as score_condition_record,
    )
except ModuleNotFoundError:
    from scripts.score_irr0_2 import (
        METRIC_KEYS,
        distraction_errors,
        score_record as score_condition_record,
    )


GOLD_PATH = Path("data/derived/irr0-iterative-reading-gold.json")
HUMAN_REVIEW_PATH = Path("data/annotation/irr0-3-span-review.json")
DEPTH_KEYS = ("historical_depth", "aesthetic_depth", "question_depth")


def average(values: Iterable[float]) -> float:
    rows = list(values)
    return round(sum(rows) / len(rows), 6) if rows else 0.0


def text_tokens(value: Any) -> set[str]:
    text = str(value or "")
    chinese = {char for char in text if "\u3400" <= char <= "\u9fff"}
    latin = set(re.findall(r"[A-Za-z0-9]{2,}", text.lower()))
    return chinese | latin


def span_match(left: str, right: str) -> bool:
    left = str(left)
    right = str(right)
    if not left or not right:
        return False
    if left in right or right in left:
        return True
    left_tokens = text_tokens(left)
    right_tokens = text_tokens(right)
    return bool(left_tokens and right_tokens and len(left_tokens & right_tokens) / len(left_tokens | right_tokens) >= 0.55)


def output_depth(output: Mapping[str, Any], critical_spans: list[str]) -> float:
    rows = output.get("text_reading", {}).get("salient_spans", [])
    matched = [
        float(row.get("depth_self_assessment", 0))
        for target in critical_spans
        for row in rows
        if span_match(target, str(row.get("span", "")))
    ]
    return average(matched or [float(row.get("depth_self_assessment", 0)) for row in rows])


def critical_coverage(output: Mapping[str, Any], critical_spans: list[str]) -> float:
    rows = [str(row.get("span", "")) for row in output.get("text_reading", {}).get("salient_spans", [])]
    if not critical_spans:
        return 0.0
    return round(sum(any(span_match(target, row) for row in rows) for target in critical_spans) / len(critical_spans), 6)


def question_depth(question: str) -> int:
    text = str(question or "").strip()
    if len(text) < 3:
        return 0
    if any(token in text for token in ("为何省略", "为何这样写", "如何写", "措辞", "写法", "审美", "选择", "压缩", "意味", "语气")):
        return 4
    if any(token in text for token in ("为何", "为什么", "何以", "因何", "背景", "政治", "局势", "影响", "因果")):
        return 3
    if any(token in text for token in ("谁", "身份", "关系", "何时", "年代", "称谓", "父", "子", "官", "地点", "何人")):
        return 2
    return 1


def output_question_depth(output: Mapping[str, Any]) -> int:
    questions = [
        str(row.get("question", ""))
        for row in output.get("open_questions", []) + output.get("new_questions", [])
        if isinstance(row, Mapping)
    ]
    return max((question_depth(row) for row in questions), default=0)


def automatic_aesthetic_depth(output: Mapping[str, Any], gold_round: Mapping[str, Any]) -> int:
    gold_ops = {
        str(operation)
        for row in gold_round.get("aesthetic_reading", [])
        for operation in row.get("operations", [])
    }
    model_ops = {
        str(operation)
        for row in output.get("aesthetic_reading", [])
        for operation in row.get("operations", [])
    }
    overlap = len(gold_ops & model_ops)
    return min(4, overlap) if overlap else 0


def model_gain_vector(
    output: Mapping[str, Any],
    previous: Mapping[str, Any] | None,
    allowed_refs: set[str],
) -> dict[str, float]:
    keys = ("G_H", "G_L", "G_A", "G_C", "G_U", "G_D", "MRG")
    if previous is None:
        return {key: 0.0 for key in keys}
    delta = output.get("reading_delta") or {}
    depth_gain = max(
        0.0,
        output_depth(output, []) - output_depth(previous, []),
    ) / 3
    values = {
        "G_H": min(1.0, len(delta.get("historical_changes", [])) / 3),
        "G_L": min(1.0, depth_gain),
        "G_A": min(
            1.0,
            (
                len(delta.get("newly_understood_omissions", []))
                + len(delta.get("reinterpretations", []))
            ) / 2,
        ),
        "G_C": min(1.0, len(delta.get("new_connections", [])) / 2),
        "G_U": min(1.0, len(delta.get("resolved_questions", [])) / 2),
        "G_D": min(1.0, distraction_errors(output, allowed_refs) / 2),
    }
    values["MRG"] = sum(values[key] for key in keys[:5]) - values["G_D"]
    return {key: round(float(value), 6) for key, value in values.items()}


def transition_metrics(
    transition: Mapping[str, Any] | None,
    previous_question_depth: int,
    output: Mapping[str, Any],
    gold_round: Mapping[str, Any],
) -> dict[str, Any]:
    affected = list(transition.get("affected_spans", [])) if transition else []
    if affected:
        historical = average(float(item.get("historical_depth", 0)) for item in affected)
        aesthetic = average(float(item.get("aesthetic_depth", 0)) for item in affected)
    else:
        historical = output_depth(output, [])
        aesthetic = float(automatic_aesthetic_depth(output, gold_round))
    current_question_depth = output_question_depth(output)
    unsupported = sum(
        1
        for item in affected
        if item.get("unsupported_interpretation") in (1, 2)
    )
    return {
        "affected_span_count": len(affected),
        "historical_depth": round(historical, 6),
        "aesthetic_depth": round(aesthetic, 6),
        "question_depth": current_question_depth,
        "question_gain": max(0, current_question_depth - previous_question_depth),
        "unsupported_interpretation_count": unsupported,
        "automatic_aesthetic_operation_depth": automatic_aesthetic_depth(output, gold_round),
    }


def human_records(root: Path) -> dict[tuple[str, int], Mapping[str, Any]]:
    path = root / HUMAN_REVIEW_PATH
    if not path.is_file():
        return {}
    document = read_json(root, HUMAN_REVIEW_PATH)
    return {
        (str(row["story_id"]), int(row["round"])): row
        for row in document.get("records", [])
        if isinstance(row, Mapping)
    }


def human_metrics(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {
            "status": "pending",
            "selected_span_count": 0,
            "historical_depth": None,
            "aesthetic_depth": None,
            "unsupported_interpretation_count": None,
            "continue_reading": None,
        }
    spans = row.get("span_reviews", [])
    aesthetic = [
        min(4, sum(int(value) for value in review.get("aesthetic_dimensions", {}).values()))
        for review in spans
    ]
    return {
        "status": "reviewed",
        "selected_span_count": len(row.get("selected_spans", [])),
        "historical_depth": average(float(review.get("interpretation_depth", 0)) for review in spans),
        "aesthetic_depth": average(aesthetic),
        "unsupported_interpretation_count": sum(
            1 for review in spans if int(review.get("unsupported_interpretation", 0)) > 0
        ),
        "continue_reading": row.get("continue_reading"),
    }


def score_story(
    root: Path,
    story_id: str,
    pilots: Mapping[str, Mapping[str, Any]],
    gold: Mapping[str, Any],
    documents: Mapping[str, Mapping[str, Any]],
    human_by_round: Mapping[tuple[str, int], Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    gold_record = next(row for row in gold["records"] if row["story_id"] == story_id)
    critical = [str(value) for value in gold_record.get("critical_spans", [])]
    condition_results: dict[str, Any] = {}
    span_rows: list[dict[str, Any]] = []
    question_rows: list[dict[str, Any]] = []
    for mode in MODES:
        record = next(row for row in documents[mode]["records"] if row["story_id"] == story_id)
        if mode != "iterative":
            output = record["output"]
            gold_round = gold_record["rounds"][-1 if mode == "all_at_once" else 0]
            allowed_refs = set(pilots[story_id]["context_refs"]) if mode == "all_at_once" else set()
            condition_scores = score_condition_record(
                output,
                gold_record,
                gold_round,
                allowed_refs,
            )
            questions = output_question_depth(output)
            condition_results[mode] = {
                "final": {
                    "historical_depth": output_depth(output, critical),
                    "aesthetic_depth": automatic_aesthetic_depth(output, gold_round),
                    "question_depth": questions,
                    "critical_span_coverage": critical_coverage(output, critical),
                    "unsupported_interpretation_count": 0,
                    "historical_gain": 0.0,
                    "aesthetic_gain": 0.0,
                    "human_span_rereading_gain": None,
                    **condition_scores["metrics"],
                    "predicted_reading_depth": condition_scores["predicted_reading_depth"],
                    "gold_reading_depth": condition_scores["gold_reading_depth"],
                },
                "human_review_status": "not_applicable",
            }
            question_rows.append({
                "story_id": story_id,
                "condition": mode,
                "round": 0,
                "question_depth": questions,
                "question_gain": questions,
            })
            continue

        rounds = []
        previous_question = 0
        previous_output: Mapping[str, Any] | None = None
        previous_historical_depth = 0.0
        previous_aesthetic_depth = 0.0
        previous_human_historical: float | None = None
        previous_human_aesthetic: float | None = None
        for current in record["rounds"]:
            number = int(current["round"])
            gold_round = gold_record["rounds"][min(number, len(gold_record["rounds"]) - 1)]
            transition = current.get("transition")
            metrics = transition_metrics(transition, previous_question, current["output"], gold_round)
            if number > 0 and metrics["affected_span_count"] == 0:
                metrics["historical_depth"] = previous_historical_depth
                metrics["aesthetic_depth"] = previous_aesthetic_depth
            metrics["critical_span_coverage"] = critical_coverage(current["output"], critical)
            metrics["model_output_depth"] = output_depth(current["output"], critical)
            allowed_refs = {
                str(item.get("evidence_ref"))
                for item in current.get("inference_input", {}).get("evidence", [])
                if isinstance(item, Mapping)
            }
            condition_scores = score_condition_record(
                current["output"],
                gold_record,
                gold_round,
                allowed_refs,
            )
            metrics.update(condition_scores["metrics"])
            metrics["predicted_reading_depth"] = condition_scores["predicted_reading_depth"]
            metrics["gold_reading_depth"] = condition_scores["gold_reading_depth"]
            human = human_metrics(human_by_round.get((story_id, number)) if number > 0 else None)
            metrics["historical_gain"] = round(
                float(metrics["historical_depth"]) - previous_historical_depth,
                6,
            )
            metrics["aesthetic_gain"] = round(
                float(metrics["aesthetic_depth"]) - previous_aesthetic_depth,
                6,
            )
            metrics["model_gain_vector"] = model_gain_vector(current["output"], previous_output, allowed_refs)
            metrics["gold_gain_vector"] = gold_round.get("gain_vector", {})
            if human["status"] == "reviewed":
                human_historical = float(human["historical_depth"] or 0.0)
                human_aesthetic = float(human["aesthetic_depth"] or 0.0)
                metrics["human_span_rereading_gain"] = {
                    "historical_depth": human_historical,
                    "aesthetic_depth": human_aesthetic,
                    "historical_gain": round(
                        human_historical - (previous_human_historical or 0.0),
                        6,
                    ),
                    "aesthetic_gain": round(
                        human_aesthetic - (previous_human_aesthetic or 0.0),
                        6,
                    ),
                }
                previous_human_historical = human_historical
                previous_human_aesthetic = human_aesthetic
            else:
                metrics["human_span_rereading_gain"] = None
            row = {
                "story_id": story_id,
                "round": number,
                "evidence_ids": list(transition.get("evidence_ids", [])) if transition else [],
                "affected_spans": list(transition.get("affected_spans", [])) if transition else [],
                "metrics": metrics,
                "human": human,
                "gold_target_depth": average(
                    float(item.get("depth", 0))
                    for item in gold_round.get("text_reading", {}).get("salient_spans", [])
                    if item.get("critical")
                ),
            }
            span_rows.append(row)
            question_rows.append({
                "story_id": story_id,
                "condition": mode,
                "round": number,
                "question_depth": metrics["question_depth"],
                "question_gain": metrics["question_gain"],
                "human_continue_reading": human["continue_reading"],
            })
            rounds.append(row)
            previous_question = metrics["question_depth"]
            previous_output = current["output"]
            previous_historical_depth = float(metrics["historical_depth"])
            previous_aesthetic_depth = float(metrics["aesthetic_depth"])
        final = rounds[-1]
        condition_results[mode] = {
            "rounds": rounds,
            "final": final["metrics"],
            "human_review_status": "reviewed" if any(row["human"]["status"] == "reviewed" for row in rounds) else "pending",
        }
    return {"story_id": story_id, "conditions": condition_results}, span_rows, question_rows


def score_all(root: Path = ROOT) -> dict[str, Any]:
    gold = read_json(root, GOLD_PATH)
    pilots = build_irr0_3_inputs(root)
    documents = {
        mode: read_json(root, output_path(mode))
        for mode in MODES
    }
    human = human_records(root)
    per_story: list[dict[str, Any]] = []
    span_rows: list[dict[str, Any]] = []
    question_rows: list[dict[str, Any]] = []
    for story_id in PILOT_STORY_IDS:
        story_result, story_spans, story_questions = score_story(
            root,
            story_id,
            pilots,
            gold,
            documents,
            human,
        )
        per_story.append(story_result)
        span_rows.extend(story_spans)
        question_rows.extend(story_questions)

    summaries: dict[str, Any] = {}
    summary_keys = (
        "historical_depth",
        "aesthetic_depth",
        "question_depth",
        "critical_span_coverage",
        *METRIC_KEYS,
    )
    for mode in MODES:
        finals = [row["conditions"][mode]["final"] for row in per_story]
        human_gains = [
            row["human_span_rereading_gain"]
            for row in finals
            if isinstance(row.get("human_span_rereading_gain"), Mapping)
        ]
        summaries[mode] = {
            "historical_depth": average(row["historical_depth"] for row in finals),
            "aesthetic_depth": average(row["aesthetic_depth"] for row in finals),
            "question_depth": average(row["question_depth"] for row in finals),
            "critical_span_coverage": average(row["critical_span_coverage"] for row in finals),
            "unsupported_interpretation_count": sum(
                int(row["unsupported_interpretation_count"]) for row in finals
            ),
            "story_count": len(finals),
            "human_span_rereading_gain": (
                {
                    "reviewed_story_count": len(human_gains),
                    "historical_gain": average(row["historical_gain"] for row in human_gains),
                    "aesthetic_gain": average(row["aesthetic_gain"] for row in human_gains),
                }
                if human_gains
                else None
            ),
        }
        for key in summary_keys:
            if key not in summaries[mode]:
                summaries[mode][key] = average(float(row.get(key, 0.0)) for row in finals)

    hard_negative_cases: list[dict[str, Any]] = []
    for story_id in PILOT_STORY_IDS:
        pilot = pilots[story_id]
        for round_number, added in enumerate(pilot["iterative_rounds"]):
            hard_ids = sorted(set(added["evidence_added"]) & set(pilot["hard_negative_refs"]))
            if not hard_ids or round_number == 0:
                continue
            row = next(item for item in span_rows if item["story_id"] == story_id and item["round"] == round_number)
            metrics = row["metrics"]
            hard_negative_cases.append({
                "story_id": story_id,
                "round": round_number,
                "evidence_ids": hard_ids,
                "recognized": metrics["affected_span_count"] == 0 and metrics["unsupported_interpretation_count"] == 0,
                "affected_span_count": metrics["affected_span_count"],
                "historical_depth": metrics["historical_depth"],
                "aesthetic_depth": metrics["aesthetic_depth"],
            })

    def pair(left: str, right: str) -> dict[str, Any]:
        return {
            "left": left,
            "right": right,
            "delta_definition": f"{right} - {left}",
            "deltas": {
                key: round(float(summaries[right][key]) - float(summaries[left][key]), 6)
                for key in (
                    "historical_depth",
                    "aesthetic_depth",
                    "question_depth",
                    "critical_span_coverage",
                    *METRIC_KEYS,
                )
            },
        }

    run_types = {
        documents[mode].get("execution", {}).get("run_type")
        for mode in MODES
    }
    real_model = run_types == {"real_model"}
    comparison = {
        "schema": "irr0.3-comparison",
        "stage": "IRR0.3",
        "schema_version": "v0",
        "run_type": "real_model" if real_model else "fixture",
        "scientific_status": "real_model_scored" if real_model else "fixture_pipeline_only",
        "scope": {"story_count": len(PILOT_STORY_IDS), "story_ids": list(PILOT_STORY_IDS)},
        "primary_metrics": [
            "human_span_rereading_gain",
            "historical_depth",
            "aesthetic_depth",
            "question_depth",
            "unsupported_interpretation_count",
            "human_continue_stop",
        ],
        "condition_summary": summaries,
        "pairwise": {
            "text_only_vs_all_at_once": pair("text_only", "all_at_once"),
            "text_only_vs_iterative": pair("text_only", "iterative"),
            "all_at_once_vs_iterative": pair("all_at_once", "iterative"),
        },
        "hard_negative_analysis": hard_negative_cases,
        "human_review": {
            "status": "reviewed" if human else "pending",
            "review_record_count": len(human),
            "gold_is_scoring_only": True,
        },
        "questions": {
            "context_improves_over_text_only": summaries["iterative"]["historical_score"] > summaries["text_only"]["historical_score"],
            "context_improves_historically": summaries["iterative"]["historical_score"] > summaries["text_only"]["historical_score"],
            "context_improves_aesthetically": summaries["iterative"]["aesthetic_operation_score"] > summaries["text_only"]["aesthetic_operation_score"],
            "iterative_outperforms_all_at_once": summaries["iterative"]["historical_score"] > summaries["all_at_once"]["historical_score"],
            "iterative_outperforms_all_at_once_aesthetically": summaries["iterative"]["aesthetic_operation_score"] > summaries["all_at_once"]["aesthetic_operation_score"],
            "hard_negative_recognized": bool(hard_negative_cases) and all(row["recognized"] for row in hard_negative_cases),
            "unsupported_interpretation_increases": summaries["iterative"]["unsupported_interpretation_count"] > summaries["all_at_once"]["unsupported_interpretation_count"],
            "human_stop_available": bool(human),
        },
    }
    span_report = {
        "schema": "irr0.3-span-gain-report",
        "stage": "IRR0.3",
        "schema_version": "v0",
        "run_type": comparison["run_type"],
        "scope": comparison["scope"],
        "human_review_required": not bool(human),
        "records": span_rows,
    }
    question_report = {
        "schema": "irr0.3-question-gain-report",
        "stage": "IRR0.3",
        "schema_version": "v0",
        "run_type": comparison["run_type"],
        "scope": comparison["scope"],
        "records": question_rows,
    }
    write_json(root, OUTPUT_DIR / "comparison.json", comparison)
    write_json(root, OUTPUT_DIR / "span-gain-report.json", span_report)
    write_json(root, OUTPUT_DIR / "question-gain-report.json", question_report)
    write_json(root, OUTPUT_DIR / "per-story-report.json", {"schema": "irr0.3-per-story-report", "records": per_story})
    for filename in ("comparison.json", "span-gain-report.json", "question-gain-report.json", "per-story-report.json"):
        write_json(root, PUBLIC_OUTPUT_DIR / filename, read_json(root, OUTPUT_DIR / filename))
    return comparison


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    comparison = score_all(args.root)
    print(stable_json({"comparison": "data/derived/irr0-3/comparison.json", "scientific_status": comparison["scientific_status"]}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
