#!/usr/bin/env python3
"""Validate IRR0.3 input isolation, span transitions and artifact integrity."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

try:
    from irr0_3_common import (
        CONTEXT_REVIEW_PATH,
        MODES,
        OUTPUT_DIR,
        PILOT_STORY_IDS,
        PUBLIC_OUTPUT_DIR,
        ROOT,
        SPAN_REVIEW_SCHEMA_PATH,
        build_irr0_3_inputs,
        load_context_review,
        output_path,
        read_json,
        source_hashes,
        validate_model_output,
        validate_span_transition,
    )
except ModuleNotFoundError:
    from scripts.irr0_3_common import (
        CONTEXT_REVIEW_PATH,
        MODES,
        OUTPUT_DIR,
        PILOT_STORY_IDS,
        PUBLIC_OUTPUT_DIR,
        ROOT,
        SPAN_REVIEW_SCHEMA_PATH,
        build_irr0_3_inputs,
        load_context_review,
        output_path,
        read_json,
        source_hashes,
        validate_model_output,
        validate_span_transition,
    )

try:
    from irr0_2_common import forbidden_input_keys, model_input_hash
except ModuleNotFoundError:
    from scripts.irr0_2_common import forbidden_input_keys, model_input_hash


GOLD_PATH = Path("data/derived/irr0-iterative-reading-gold.json")
HUMAN_REVIEW_PATH = Path("data/annotation/irr0-3-span-review.json")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _walk_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, Mapping):
        if isinstance(value.get("evidence_refs"), list):
            refs.update(str(item) for item in value["evidence_refs"])
        for child in value.values():
            refs.update(_walk_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.update(_walk_refs(child))
    return refs


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []

    def add(message: str) -> None:
        errors.append(message)

    required = [
        OUTPUT_DIR / "manifest.json",
        *(OUTPUT_DIR / filename for filename in ("text-only.json", "all-at-once.json", "iterative.json")),
        *(OUTPUT_DIR / filename for filename in ("comparison.json", "span-gain-report.json", "question-gain-report.json", "per-story-report.json")),
    ]
    missing = [path.as_posix() for path in required if not (root / path).is_file()]
    if missing:
        return [f"missing IRR0.3 artifact: {path}" for path in missing]

    manifest = read_json(root, OUTPUT_DIR / "manifest.json")
    context = load_context_review(root)
    pilots = build_irr0_3_inputs(root)
    current_hashes = source_hashes(root)
    documents = {
        mode: read_json(root, output_path(mode))
        for mode in MODES
    }
    if manifest.get("schema") != "irr0.3-manifest":
        add("manifest schema is incorrect")
    if manifest.get("stage") != "IRR0.3":
        add("manifest stage is incorrect")
    if manifest.get("scope", {}).get("story_ids") != list(PILOT_STORY_IDS):
        add("manifest Story scope changed")
    if manifest.get("conditions") != list(MODES):
        add("manifest condition order changed")
    if manifest.get("source_hashes") != current_hashes:
        add("manifest source hashes are stale")
    if manifest.get("self_hash") is not None:
        add("manifest must not contain a self-reference")

    if context.get("scope", {}).get("story_ids") != list(PILOT_STORY_IDS):
        add("context review Story scope changed")
    context_records = context.get("records", [])
    if [row.get("story_id") for row in context_records] != list(PILOT_STORY_IDS):
        add("context review record order changed")
    for story_id in PILOT_STORY_IDS:
        record = next(row for row in context_records if row.get("story_id") == story_id)
        hard = [
            item
            for current in record.get("rounds", [])
            for item in current.get("evidence_added", [])
            if item.get("expected_role") == "hard_negative"
        ]
        if not hard:
            add(f"missing reviewed hard negative: {story_id}")
        refs = [
            str(item.get("evidence_ref"))
            for current in record.get("rounds", [])
            for item in current.get("evidence_added", [])
        ]
        if len(refs) != len(set(refs)):
            add(f"context evidence is repeated across rounds: {story_id}")

    run_types = {document.get("execution", {}).get("run_type") for document in documents.values()}
    if run_types not in ({"fixture"}, {"real_model"}):
        add(f"condition run types differ or are invalid: {sorted(run_types)}")
    if manifest.get("execution", {}).get("run_type") not in run_types:
        add("manifest execution run_type disagrees with conditions")

    for mode, document in documents.items():
        if document.get("schema") != "irr0.3-model-reading-output":
            add(f"{mode} output schema is incorrect")
        if document.get("condition") != mode:
            add(f"{mode} condition is incorrect")
        if document.get("scope", {}).get("story_ids") != list(PILOT_STORY_IDS):
            add(f"{mode} scope is not the frozen five Stories")
        if document.get("source_hashes") != current_hashes:
            add(f"{mode} source hashes are stale")
        rows = document.get("records", [])
        if [row.get("story_id") for row in rows] != list(PILOT_STORY_IDS):
            add(f"{mode} record order/scope changed")
        for record in rows:
            story_id = str(record.get("story_id"))
            pilot = pilots.get(story_id)
            if not pilot:
                add(f"{mode} unknown Story: {story_id}")
                continue
            current_rounds = record.get("rounds") if mode == "iterative" else [record]
            if mode == "iterative" and len(current_rounds) != len(pilot["iterative_rounds"]):
                add(f"{mode} round count differs from context schedule: {story_id}")
            previous_refs: set[str] = set()
            for current in current_rounds:
                round_number = int(current.get("round", 0))
                payload = current.get("inference_input", {})
                if forbidden_input_keys(payload):
                    add(f"review/Gold fields leaked into input: {mode}/{story_id}/R{round_number}")
                if current.get("input_hash") != model_input_hash(payload):
                    add(f"input hash mismatch: {mode}/{story_id}/R{round_number}")
                allowed = {
                    str(item.get("evidence_ref"))
                    for item in payload.get("evidence", [])
                    if isinstance(item, Mapping)
                }
                expected = (
                    set()
                    if mode == "text_only"
                    else set(pilot["context_refs"])
                    if mode == "all_at_once"
                    else set(pilot["iterative_rounds"][round_number]["evidence_refs"])
                )
                if allowed != expected:
                    add(f"input evidence set mismatch: {mode}/{story_id}/R{round_number}")
                if mode == "iterative":
                    expected_added = set(pilot["iterative_rounds"][round_number]["evidence_added"])
                    transition = current.get("transition")
                    if round_number == 0:
                        if transition is not None:
                            add(f"R0 must not have a transition: {story_id}")
                    else:
                        if not isinstance(transition, Mapping):
                            add(f"iterative transition missing: {story_id}/R{round_number}")
                        else:
                            try:
                                validate_span_transition(transition)
                            except ValueError as exc:
                                add(str(exc))
                            if set(transition.get("evidence_ids", [])) != expected_added:
                                add(f"transition evidence IDs mismatch: {story_id}/R{round_number}")
                    previous_refs = allowed
                try:
                    validate_model_output(root, current.get("output", {}))
                except ValueError as exc:
                    add(f"{mode}/{story_id}/R{round_number}: {exc}")
                cited = _walk_refs(current.get("output", {}))
                if cited - allowed:
                    add(f"model cites evidence outside input: {mode}/{story_id}/R{round_number}")
                model_metadata = current.get("model_metadata", {})
                for field in ("provider", "model", "parameters", "run_id", "run_type", "input_hash"):
                    if field not in model_metadata:
                        add(f"model metadata lacks {field}: {mode}/{story_id}/R{round_number}")
                if model_metadata.get("input_hash") != current.get("input_hash"):
                    add(f"model metadata hash mismatch: {mode}/{story_id}/R{round_number}")

            if mode == "all_at_once":
                all_refs = {
                    str(item.get("evidence_ref"))
                    for item in rows[[row["story_id"] for row in rows].index(story_id)].get("inference_input", {}).get("evidence", [])
                }
                iterative = next(row for row in documents["iterative"]["records"] if row["story_id"] == story_id)
                iterative_refs = {
                    str(item.get("evidence_ref"))
                    for item in iterative["rounds"][-1]["inference_input"].get("evidence", [])
                }
                if all_refs != iterative_refs:
                    add(f"all-at-once evidence is not the iterative union: {story_id}")

    try:
        schema = read_json(root, SPAN_REVIEW_SCHEMA_PATH)
        human = read_json(root, HUMAN_REVIEW_PATH)
        schema_errors = list(Draft202012Validator(schema).iter_errors(human))
        if schema_errors:
            add(f"human span review schema error: {schema_errors[0].message}")
        if human.get("scope", {}).get("story_ids") != list(PILOT_STORY_IDS):
            add("human span review scope changed")
        for review in human.get("records", []):
            story_id = str(review.get("story_id"))
            pilot = pilots.get(story_id)
            if pilot is None:
                add(f"human span review has unknown Story: {story_id}")
                continue
            round_number = int(review.get("round", 0))
            round_rows = {
                int(row["round"]): row
                for row in pilot["iterative_rounds"]
            }
            scheduled = round_rows.get(round_number)
            if scheduled is None or round_number == 0:
                add(f"human span review has invalid transition round: {story_id}/R{round_number}")
                continue
            expected_added = set(scheduled["evidence_added"])
            review_evidence = set(str(item) for item in review.get("evidence_ids", []))
            if review_evidence != expected_added:
                add(f"human span review evidence mismatch: {story_id}/R{round_number}")
            selected = set(str(item) for item in review.get("selected_spans", []))
            span_reviews = review.get("span_reviews", [])
            reviewed_spans = [str(item.get("span")) for item in span_reviews if isinstance(item, Mapping)]
            if len(reviewed_spans) != len(set(reviewed_spans)):
                add(f"human span review repeats a span: {story_id}/R{round_number}")
            if not selected and span_reviews:
                add(f"human span review has span details without selection: {story_id}/R{round_number}")
            if not selected and not bool(review.get("no_effect")) and span_reviews:
                add(f"human span review has unclassified span details: {story_id}/R{round_number}")
            if bool(review.get("no_effect")) and selected:
                add(f"human span review marks no_effect with selected spans: {story_id}/R{round_number}")
            if selected and not selected.issuperset(reviewed_spans):
                add(f"human span review detail is not among selected spans: {story_id}/R{round_number}")
            cumulative_allowed = set(scheduled["evidence_refs"])
            for span_review in span_reviews:
                if not isinstance(span_review, Mapping):
                    continue
                refs = set(str(item) for item in span_review.get("evidence_refs", []))
                if not refs or not refs.issubset(cumulative_allowed):
                    add(f"human span review evidence provenance is invalid: {story_id}/R{round_number}")
    except (OSError, ValueError, KeyError) as exc:
        add(f"human span review cannot be read: {exc}")

    comparison = read_json(root, OUTPUT_DIR / "comparison.json")
    if comparison.get("scope", {}).get("story_ids") != list(PILOT_STORY_IDS):
        add("comparison scope changed")
    if comparison.get("run_type") not in ("fixture", "real_model"):
        add("comparison run_type is invalid")
    for filename in (
        "manifest.json",
        "text-only.json",
        "all-at-once.json",
        "iterative.json",
        "comparison.json",
        "span-gain-report.json",
        "question-gain-report.json",
        "per-story-report.json",
    ):
        derived = root / OUTPUT_DIR / filename
        public = root / PUBLIC_OUTPUT_DIR / filename
        if not public.is_file() or public.read_bytes() != derived.read_bytes():
            add(f"public IRR0.3 artifact is not byte-identical: {filename}")
    expected_artifacts = manifest.get("artifact_hashes_excluding_manifest", {})
    for relative, expected in expected_artifacts.items():
        path = root / relative
        if not path.is_file() or sha256(path) != expected:
            add(f"manifest artifact hash mismatch: {relative}")
    if manifest.get("context_review_source", {}).get(CONTEXT_REVIEW_PATH.as_posix()) != sha256(root / CONTEXT_REVIEW_PATH):
        add("context review hash is stale")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = validate(args.root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("IRR0.3 validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
