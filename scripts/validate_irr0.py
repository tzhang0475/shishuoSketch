#!/usr/bin/env python3
"""Validate the isolated IRR0.1 iterative-reading experiment."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_irr0 import (  # noqa: E402
    ALLOWED_DELTA_FIELDS,
    GOLD_PATH,
    HR01_PATH,
    HR0_PATH,
    INPUT_PATHS,
    NL0_GOLD_PATH,
    NL1_CONTEXT_PATH,
    NL1_SELECTION_PATH,
    PILOT_STORY_IDS,
    REPORT_PATH,
    SC1_PATH,
    SCHEMA_PATH,
    S1_ASSERTIONS_PATH,
    build_documents,
    stable_json,
)


def read_json(root: Path, relative: Path) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def sha256_file(root: Path, relative: Path) -> str:
    digest = hashlib.sha256()
    with (root / relative).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add(errors: list[str], message: str) -> None:
    errors.append(message)


def collect_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, Mapping):
        if isinstance(value.get("evidence_refs"), list):
            refs.update(str(item) for item in value["evidence_refs"])
        if isinstance(value.get("evidence_ref"), str):
            refs.add(value["evidence_ref"])
        for child in value.values():
            refs.update(collect_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.update(collect_refs(child))
    return refs


def check_claim_refs(value: Any, path: str, errors: list[str]) -> None:
    """Require provenance for textual claims in the derived states."""

    if isinstance(value, Mapping):
        claim_keys = {"text", "description", "question", "state", "literal_meaning", "contextual_meaning"}
        has_claim = any(key in value and value[key] not in (None, "") for key in claim_keys)
        if has_claim and not value.get("evidence_refs"):
            add(errors, f"claim has no evidence_refs at {path}")
        for key, child in value.items():
            check_claim_refs(child, f"{path}.{key}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            check_claim_refs(child, f"{path}[{index}]", errors)


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    required = [*INPUT_PATHS, GOLD_PATH, REPORT_PATH]
    for relative in required:
        if not (root / relative).is_file():
            add(errors, f"missing IRR0.1 input/output: {relative}")
    if errors:
        return errors

    schema = read_json(root, SCHEMA_PATH)
    gold = read_json(root, GOLD_PATH)
    report = read_json(root, REPORT_PATH)
    review = read_json(root, INPUT_PATHS[0])
    sc1 = read_json(root, SC1_PATH)
    hr0 = read_json(root, HR0_PATH)
    hr01 = read_json(root, HR01_PATH)
    nl0 = read_json(root, NL0_GOLD_PATH)
    nl1_context = read_json(root, NL1_CONTEXT_PATH)
    nl1_selection = read_json(root, NL1_SELECTION_PATH)
    s1 = read_json(root, S1_ASSERTIONS_PATH)

    schema_errors = sorted(Draft202012Validator(schema).iter_errors(gold), key=lambda error: list(error.absolute_path))
    errors.extend(
        f"schema: {error.message} at /{'/'.join(str(part) for part in error.absolute_path)}"
        for error in schema_errors
    )

    story_by_id = {str(row.get("id")): row for row in sc1.get("stories", [])}
    people = {str(row.get("id")) for row in sc1.get("people", [])}
    story_evidence = {str(row.get("id")): row for row in sc1.get("evidence", [])}
    assertions = {str(row.get("assertion_id")): row for row in s1.get("records", [])}
    hr0_by_story = {str(row.get("story_id")): row for row in hr0.get("records", [])}
    hr01_by_story = {str(row.get("story_id")): row for row in hr01.get("records", [])}
    nl0_by_story = {str(row.get("story_id")): row for row in nl0.get("records", [])}
    nl1_context_by_story = {str(row.get("story_id")): row for row in nl1_context.get("records", [])}
    nl1_selection_by_story = {str(row.get("story_id")): row for row in nl1_selection.get("records", [])}

    review_ids = [str(row.get("story_id")) for row in review.get("records", [])]
    gold_ids = [str(row.get("story_id")) for row in gold.get("records", [])]
    if review_ids != sorted(review_ids):
        add(errors, "IRR0.1 review records are not stably sorted")
    if gold_ids != list(PILOT_STORY_IDS):
        add(errors, "IRR0.1 Gold Story order/scope changed")
    if set(review_ids) != set(PILOT_STORY_IDS) or set(gold_ids) != set(PILOT_STORY_IDS):
        add(errors, "IRR0.1 does not contain exactly the fixed five pilot Stories")
    if gold.get("scope", {}).get("story_count") != 5 or gold.get("scope", {}).get("story_ids") != list(PILOT_STORY_IDS):
        add(errors, "IRR0.1 Gold scope is inconsistent")

    expected_hashes = {path.as_posix(): sha256_file(root, path) for path in INPUT_PATHS}
    for label, document in (("gold", gold), ("report", report)):
        if document.get("source_hashes") != expected_hashes:
            add(errors, f"{label} source_hashes do not match current inputs")
        if any(Path(str(path)).is_absolute() for path in document.get("source_hashes", {})):
            add(errors, f"{label} contains an absolute source-hash path")
    if gold.get("policy") != {
        "canonical_data_write_back": False,
        "canonical_fact_materialization": False,
        "llm_calls": False,
        "retrieval": False,
        "persistent_memory": False,
        "frontend_changes": False,
        "new_historical_facts": False,
        "review_model": "reviewed_deterministic_annotation",
    }:
        add(errors, "IRR0.1 policy permits a forbidden operation")
    if report.get("schema") != "irr0-gain-report":
        add(errors, "IRR0.1 gain report schema is incorrect")

    for story_id in PILOT_STORY_IDS:
        if story_id not in story_by_id:
            add(errors, f"unknown pilot Story: {story_id}")
        if story_id not in hr0_by_story or story_id not in hr01_by_story:
            add(errors, f"missing HR0/HR0.1 input record: {story_id}")
        if story_id not in nl0_by_story or story_id not in nl1_context_by_story or story_id not in nl1_selection_by_story:
            add(errors, f"missing NL0/NL1 grounding input record: {story_id}")

    report_by_story = {str(row.get("story_id")): row for row in report.get("per_story", [])}
    if set(report_by_story) != set(PILOT_STORY_IDS):
        add(errors, "gain report Story universe differs from Gold")

    expected_phrases = ("陶公起止拜", "引咎自谢", "一丘一壑，自谓过之", "不意天壤之中，乃有王郎！")
    gold_text = json.dumps(gold, ensure_ascii=False)
    for phrase in expected_phrases:
        if phrase not in gold_text:
            add(errors, f"expected critical reading phrase is missing: {phrase}")

    progression_stories: list[str] = []
    hard_negative_count = 0
    for record in gold.get("records", []):
        story_id = str(record.get("story_id"))
        if story_id not in story_by_id:
            add(errors, f"Gold record has unknown Story: {story_id}")
            continue
        if record.get("review_status") != "reviewed_gold":
            add(errors, f"Gold record is not reviewed_gold: {story_id}")
        grounding = record.get("grounding", {})
        if grounding.get("hr0_situation_id") != hr0_by_story.get(story_id, {}).get("situation_id"):
            add(errors, f"HR0 grounding mismatch: {story_id}")
        if set(grounding.get("hr0_1_case_ids", [])) - set(hr01_by_story.get(story_id, {}).get("case_ids", [])):
            add(errors, f"HR0.1 grounding mismatch: {story_id}")
        if grounding.get("nl0_story_sketch_id") != f"story-sketch-nl0-{story_id}":
            add(errors, f"NL0 grounding mismatch: {story_id}")
        if grounding.get("nl1_context_id") != nl1_context_by_story.get(story_id, {}).get("context_id"):
            add(errors, f"NL1 context grounding mismatch: {story_id}")
        if grounding.get("nl1_selection_id") != nl1_selection_by_story.get(story_id, {}).get("selection_id"):
            add(errors, f"NL1 selection grounding mismatch: {story_id}")

        refs = collect_refs(record)
        descriptors = {str(row.get("evidence_ref")): row for row in record.get("evidence_index", [])}
        if refs != set(descriptors):
            add(errors, f"evidence index is not exact for {story_id}")
        for ref, descriptor in descriptors.items():
            if ref.startswith("evidence-sc1-"):
                source = story_evidence.get(ref)
                if source is None:
                    add(errors, f"unknown Story evidence: {story_id}/{ref}")
                elif descriptor.get("quote_sha256") != hashlib.sha256(str(source.get("quote", "")).encode("utf-8")).hexdigest():
                    add(errors, f"Story evidence fingerprint mismatch: {story_id}/{ref}")
            elif ref.startswith("s1-assertion-"):
                source = assertions.get(ref)
                if source is None:
                    add(errors, f"unknown S1 assertion: {story_id}/{ref}")
                elif str(source.get("story_id")) != story_id:
                    add(errors, f"S1 assertion belongs to another Story: {story_id}/{ref}")
                elif descriptor.get("quote_sha256") != str(source.get("text_sha256")):
                    add(errors, f"S1 assertion fingerprint mismatch: {story_id}/{ref}")
            else:
                add(errors, f"unsupported IRR0.1 evidence namespace: {story_id}/{ref}")

        if len(record.get("rounds", [])) != 3:
            add(errors, f"IRR0.1 pilot Story must have R0/R1/R2: {story_id}")
        depths: list[float] = []
        for index, current in enumerate(record.get("rounds", [])):
            if current.get("round") != index:
                add(errors, f"non-contiguous round number: {story_id}/{index}")
            if index == 0 and current.get("evidence_added"):
                add(errors, f"R0 contains added evidence: {story_id}")
            if index > 0 and not current.get("evidence_added"):
                add(errors, f"context round has no evidence: {story_id}/R{index}")
            for item in current.get("evidence_added", []):
                if item.get("review_status") != "reviewed":
                    add(errors, f"unreviewed added evidence: {story_id}/R{index}")
                if item.get("expected_role") == "hard_negative":
                    hard_negative_count += 1
                for assertion_id in item.get("source_assertion_ids", []):
                    if assertion_id not in assertions:
                        add(errors, f"unknown source assertion lineage: {story_id}/{assertion_id}")
                    elif assertion_id != item.get("evidence_ref"):
                        add(errors, f"source assertion lineage does not match evidence_ref: {story_id}/{assertion_id}")
            for span in current.get("text_reading", {}).get("salient_spans", []):
                source_text = str(story_by_id[story_id].get("reading", {}).get("main_text", {}).get("original", ""))
                if span.get("span") not in source_text:
                    add(errors, f"salient span is not in canonical Story text: {story_id}/{span.get('span')}")
            critical = [int(span["depth"]) for span in current.get("text_reading", {}).get("salient_spans", []) if span.get("critical")]
            if not critical:
                add(errors, f"round has no critical span: {story_id}/R{index}")
            else:
                depths.append(round(sum(critical) / len(critical), 6))
            if index == 0 and current.get("reading_delta") is not None:
                add(errors, f"R0 must not have a reading delta: {story_id}")
            if index > 0:
                delta = current.get("reading_delta")
                if not isinstance(delta, Mapping) or set(delta) != set(ALLOWED_DELTA_FIELDS):
                    add(errors, f"R{index} reading delta is incomplete: {story_id}")
                for field in ALLOWED_DELTA_FIELDS:
                    for row in (delta or {}).get(field, []):
                        if not row.get("evidence_refs"):
                            add(errors, f"R{index} delta item lacks evidence: {story_id}/{field}")
            vector = current.get("gain_vector", {})
            for key in ("G_H", "G_L", "G_A", "G_C", "G_U", "G_D"):
                if not 0 <= float(vector.get(key, -1)) <= 1:
                    add(errors, f"gain component outside [0,1]: {story_id}/R{index}/{key}")
            expected_mrg = round(sum(float(vector.get(key, 0)) for key in ("G_H", "G_L", "G_A", "G_C", "G_U")) - float(vector.get("G_D", 0)), 6)
            if float(vector.get("MRG", 999)) != expected_mrg:
                add(errors, f"MRG does not equal gain vector: {story_id}/R{index}")
        if len(depths) >= 3 and depths[0] < depths[1] < depths[2]:
            progression_stories.append(story_id)
        check_claim_refs(record.get("rounds", []), f"{story_id}.rounds", errors)

    if len(progression_stories) < 3:
        add(errors, "IRR0.1 does not demonstrate R0 < R1 < R2 for at least three Stories")
    if hard_negative_count < 1:
        add(errors, "IRR0.1 lacks a hard-negative/low-gain context round")
    if gold.get("counts", {}).get("progressive_depth_stories") != len(progression_stories):
        add(errors, "Gold progression count is inconsistent")
    if report.get("summary", {}).get("progressive_depth_stories") != progression_stories:
        add(errors, "gain report progression list is inconsistent")

    # No volatile values or absolute paths are allowed in deterministic output.
    for label, document in (("gold", gold), ("report", report)):
        text = stable_json(document)
        for volatile in ("generated_at", "timestamp", "build_time", "built_at"):
            if volatile in text:
                add(errors, f"{label} contains volatile field: {volatile}")
        if str(root) in text:
            add(errors, f"{label} contains an absolute repository path")

    first_gold, first_report = build_documents(root)
    second_gold, second_report = build_documents(root)
    if stable_json(first_gold) != stable_json(second_gold) or stable_json(first_report) != stable_json(second_report):
        add(errors, "IRR0.1 builder is nondeterministic")
    if first_gold != gold or first_report != report:
        add(errors, "committed IRR0.1 derived artifacts do not match builder output")

    return errors


if __name__ == "__main__":
    problems = validate()
    if problems:
        print("\n".join(f"ERROR: {problem}" for problem in problems))
        raise SystemExit(1)
    print("IRR0.1 validation passed")
