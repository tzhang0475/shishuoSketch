#!/usr/bin/env python3
"""Score IRR0.4 span trajectories without tuning MRG or using an LLM judge."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from irr0_4_common import (
        CONDITIONS,
        HUMAN_REVIEW_PATH,
        IRR04_STORY_IDS,
        OUTPUT_DIR,
        PUBLIC_OUTPUT_DIR,
        ROOT,
        build_irr0_4_inputs,
        output_path,
        read_json,
        stable_json,
        write_json,
    )
    from run_irr0_4 import copy_public, write_manifest
except ModuleNotFoundError:
    from scripts.irr0_4_common import (
        CONDITIONS,
        HUMAN_REVIEW_PATH,
        IRR04_STORY_IDS,
        OUTPUT_DIR,
        PUBLIC_OUTPUT_DIR,
        ROOT,
        build_irr0_4_inputs,
        output_path,
        read_json,
        stable_json,
        write_json,
    )
    from scripts.run_irr0_4 import copy_public, write_manifest


DEPTH_FIELDS = (
    "scene_historical_depth",
    "relational_depth",
    "retrospective_depth",
    "aesthetic_depth",
)


def average(values: Iterable[float]) -> float:
    rows = list(values)
    return round(sum(rows) / len(rows), 6) if rows else 0.0


def span_match(left: str, right: str) -> bool:
    left = str(left)
    right = str(right)
    return bool(left and right and (left == right or left in right or right in left))


def find_span_reading(output: Mapping[str, Any], target: str) -> Mapping[str, Any] | None:
    rows = output.get("span_readings", [])
    exact = [row for row in rows if isinstance(row, Mapping) and str(row.get("span")) == target]
    if exact:
        return exact[0]
    return next(
        (
            row
            for row in rows
            if isinstance(row, Mapping) and span_match(target, str(row.get("span", "")))
        ),
        None,
    )


def span_state(output: Mapping[str, Any], target: str) -> dict[str, Any]:
    row = find_span_reading(output, target)
    if row is None:
        return {
            "span": target,
            "present": False,
            "literal_reading": "",
            "current_interpretation": "",
            "changed_from_previous": False,
            "change_type": "none",
            "supporting_evidence_ids": [],
            "unsupported_inference": False,
            **{field: 0 for field in DEPTH_FIELDS},
        }
    return {
        "span": target,
        "present": True,
        "literal_reading": str(row.get("literal_reading", "")),
        "current_interpretation": str(row.get("current_interpretation", "")),
        "changed_from_previous": bool(row.get("changed_from_previous", False)),
        "change_type": str(row.get("change_type", "none")),
        "supporting_evidence_ids": [str(ref) for ref in row.get("supporting_evidence_ids", [])],
        "unsupported_inference": bool(row.get("unsupported_inference", False)),
        **{field: int(row.get(field, 0)) for field in DEPTH_FIELDS},
    }


def review_records(root: Path) -> dict[tuple[str, str, str, str], Mapping[str, Any]]:
    document = read_json(root, HUMAN_REVIEW_PATH)
    return {
        (
            str(row["story_id"]),
            str(row["branch"]),
            str(row["round_label"]),
            str(row["condition"]),
        ): row
        for row in document.get("records", [])
        if isinstance(row, Mapping)
    }


def human_review_template(inputs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for story_id in IRR04_STORY_IDS:
        pilot = inputs[story_id]
        labels = [f"R{row['round']}" for row in pilot["rounds"] if int(row["round"]) > 0]
        labels.append(str(pilot["negative_control"]["round_label"]))
        for branch, round_labels in (("main", labels[:-1]), ("negative_control", labels[-1:])):
            for label in round_labels:
                for condition in CONDITIONS:
                    records.append({
                        "review_key": f"{story_id}:{branch}:{label}:{condition}",
                        "story_id": story_id,
                        "branch": branch,
                        "round_label": label,
                        "condition": condition,
                        "visible_deepening": None,
                        "historical_depth": None,
                        "aesthetic_depth": None,
                        "unsupported_interpretation": None,
                        "anchoring_detected": None,
                        "continue_reading": None,
                    })
    return {
        "schema": "irr0.4-human-review-template",
        "stage": "IRR0.4",
        "schema_version": "v0",
        "scope": {"story_ids": list(IRR04_STORY_IDS)},
        "records": records,
    }


def score_envelope(
    envelope: Mapping[str, Any],
    targets: list[str],
    previous_output: Mapping[str, Any] | None,
) -> dict[str, Any]:
    output = envelope["output"]
    spans = [span_state(output, target) for target in targets]
    if previous_output is None:
        previous = {target: None for target in targets}
    else:
        previous = {target: span_state(previous_output, target) for target in targets}
    changes = [
        row
        for row in spans
        if row["changed_from_previous"] or (
            previous[row["span"]] is not None
            and row["current_interpretation"] != previous[row["span"]]["current_interpretation"]
        )
    ]
    return {
        "spans": spans,
        "matched_span_count": sum(1 for row in spans if row["present"]),
        "target_span_count": len(targets),
        "visible_change_count": len(changes),
        "unsupported_interpretation_count": sum(1 for row in spans if row["unsupported_inference"]),
        "depths": {
            field: average(float(row[field]) for row in spans)
            for field in DEPTH_FIELDS
        },
    }


def score_all(root: Path = ROOT) -> dict[str, Any]:
    inputs = build_irr0_4_inputs(root)
    document = read_json(root, output_path())
    human = review_records(root)
    memory_rows: list[dict[str, Any]] = []
    negative_rows: list[dict[str, Any]] = []
    trajectories: list[dict[str, Any]] = []

    for story_id in IRR04_STORY_IDS:
        record = next(row for row in document["records"] if row["story_id"] == story_id)
        pilot = inputs[story_id]
        previous_outputs: dict[str, Mapping[str, Any] | None] = {"memory": None, "fresh": None}
        target_trajectory: dict[str, list[dict[str, Any]]] = {
            target: [] for target in pilot["critical_spans"]
        }
        for round_record in record["rounds"]:
            label = str(round_record["round_label"])
            targets = [str(target) for target in round_record["gold"]["target_spans"]]
            condition_scores: dict[str, dict[str, Any]] = {}
            for condition in CONDITIONS:
                envelope = round_record[f"{condition}_reading"]
                scored = score_envelope(envelope, targets, previous_outputs[condition])
                condition_scores[condition] = scored
                for state in scored["spans"]:
                    target_trajectory_for(target_trajectory, state["span"]).append({
                        "round_label": label,
                        "semantic_stage": round_record["semantic_stage"],
                        "condition": condition,
                        **state,
                    })
                previous_outputs[condition] = envelope["output"]
            memory = condition_scores["memory"]
            fresh = condition_scores["fresh"]
            memory_rows.append({
                "story_id": story_id,
                "round_label": label,
                "semantic_stage": round_record["semantic_stage"],
                "target_spans": targets,
                "memory": memory,
                "fresh": fresh,
                "differences": {
                    "interpretation_change_count": sum(
                        1
                        for left, right in zip(memory["spans"], fresh["spans"])
                        if left["current_interpretation"] != right["current_interpretation"]
                    ),
                    "depth_deltas": {
                        field: round(fresh["depths"][field] - memory["depths"][field], 6)
                        for field in DEPTH_FIELDS
                    },
                    "anchoring_signal": any(
                        not left["changed_from_previous"] and right["changed_from_previous"]
                        for left, right in zip(memory["spans"], fresh["spans"])
                    ),
                },
                "human_review": {
                    condition: human.get((story_id, "main", label, condition))
                    for condition in CONDITIONS
                },
            })

        negative = record["negative_control"]
        base = record["rounds"][int(negative["base_round"])]
        for condition in CONDITIONS:
            base_scored = score_envelope(
                base[f"{condition}_reading"],
                list(base["gold"]["target_spans"]),
                record["rounds"][0][f"{condition}_reading"]["output"],
            )
            negative_scored = score_envelope(
                negative[f"{condition}_reading"],
                list(negative["gold"]["target_spans"]),
                base[f"{condition}_reading"]["output"],
            )
            negative_rows.append({
                "story_id": story_id,
                "round_label": negative["round_label"],
                "condition": condition,
                "target_spans": list(negative["gold"]["target_spans"]),
                "base_round": base["round_label"],
                "base": base_scored,
                "negative": negative_scored,
                "recognized": all(
                    not row["changed_from_previous"]
                    and not row["unsupported_inference"]
                    and row["current_interpretation"] == base_row["current_interpretation"]
                    for row, base_row in zip(negative_scored["spans"], base_scored["spans"])
                ),
                "human_review": human.get((story_id, "negative_control", str(negative["round_label"]), condition)),
            })

        for target, rows in target_trajectory.items():
            lines = [f"SPAN: {target}"]
            for row in rows:
                lines.append(f"{row['round_label']}-{row['condition']}: {row['current_interpretation']}")
            trajectories.append({
                "story_id": story_id,
                "span": target,
                "stages": rows,
                "human_readable": "\n".join(lines),
            })

    comparison = {
        "schema": "irr0.4-memory-vs-fresh",
        "stage": "IRR0.4",
        "schema_version": "v0",
        "run_type": document["execution"]["run_type"],
        "scope": {"story_count": len(IRR04_STORY_IDS), "story_ids": list(IRR04_STORY_IDS)},
        "records": memory_rows,
    }
    negative_report = {
        "schema": "irr0.4-negative-controls",
        "stage": "IRR0.4",
        "schema_version": "v0",
        "run_type": document["execution"]["run_type"],
        "scope": {"story_count": len(IRR04_STORY_IDS), "story_ids": list(IRR04_STORY_IDS)},
        "records": negative_rows,
        "recognized_count": sum(1 for row in negative_rows if row["recognized"]),
        "record_count": len(negative_rows),
    }
    trajectory_report = {
        "schema": "irr0.4-span-trajectories",
        "stage": "IRR0.4",
        "schema_version": "v0",
        "run_type": document["execution"]["run_type"],
        "scope": {"story_count": len(IRR04_STORY_IDS), "story_ids": list(IRR04_STORY_IDS)},
        "records": trajectories,
    }
    human_template = human_review_template(inputs)
    summary = {
        "schema": "irr0.4-summary",
        "stage": "IRR0.4",
        "schema_version": "v0",
        "run_type": document["execution"]["run_type"],
        "scientific_status": "real_model_scored" if document["execution"]["run_type"] == "real_model" else "fixture_pipeline_only",
        "scope": {"story_count": len(IRR04_STORY_IDS), "story_ids": list(IRR04_STORY_IDS)},
        "primary_unit": "same critical span across semantic stages",
        "metrics": {
            "stories": len(IRR04_STORY_IDS),
            "critical_spans": sum(len(inputs[story_id]["critical_spans"]) for story_id in IRR04_STORY_IDS),
            "main_transitions": len(memory_rows),
            "negative_control_transitions": len(negative_rows),
            "negative_controls_recognized": negative_report["recognized_count"],
            "human_review_records": len(human),
        },
        "questions": {
            "semantic_ladders_present": True,
            "negative_controls_present": bool(negative_rows),
            "memory_fresh_comparison_present": bool(memory_rows),
            "anchoring_signal_count": sum(1 for row in memory_rows if row["differences"]["anchoring_signal"]),
            "human_stop_data_available": any(
                row.get("continue_reading") in ("yes", "no")
                for row in human.values()
            ),
        },
    }
    write_json(root, OUTPUT_DIR / "memory-vs-fresh.json", comparison)
    write_json(root, OUTPUT_DIR / "negative-controls.json", negative_report)
    write_json(root, OUTPUT_DIR / "span-trajectories.json", trajectory_report)
    write_json(root, OUTPUT_DIR / "human-review-template.json", human_template)
    write_json(root, OUTPUT_DIR / "summary.json", summary)
    execution = document["execution"]
    manifest = write_manifest(root, execution)
    copy_public(root)
    return {
        "comparison": comparison,
        "negative_controls": negative_report,
        "trajectories": trajectory_report,
        "summary": summary,
        "manifest": manifest,
    }


def target_trajectory_for(trajectory: dict[str, list[dict[str, Any]]], target: str) -> list[dict[str, Any]]:
    if target not in trajectory:
        trajectory[target] = []
    return trajectory[target]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    result = score_all(args.root)
    print(
        stable_json({
            "comparison": "data/derived/irr0-4/memory-vs-fresh.json",
            "negative_controls": result["negative_controls"]["recognized_count"],
            "scientific_status": result["summary"]["scientific_status"],
        }),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
