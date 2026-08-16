#!/usr/bin/env python3
"""Validate the HR0.1 two-pass ambiguity/evidence benchmark."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_hr0_1_resolution_benchmark import (  # noqa: E402
    BENCHMARK_PATH,
    EXTRA_SPEC_PATH,
    HG0_GRAPH_PATH,
    H0C_FACTS_PATH,
    HR0_PATH,
    HR0_SCHEMA_PATH,
    ML0_METRICS_PATH,
    PARTICIPANT_PATH,
    PROTECTION_PATH,
    SC1_PATH,
    SCHEMA_PATH,
    build_documents,
)


ALLOWED_REQUIRES = {"liu_annotation", "jianshu", "external_source", "canonical_fact"}
VIEW_FIELDS = ("episodes", "participant_states", "temporal_relations", "person_states", "title_mentions", "uncertainties")
ITEM_ID_FIELDS = {
    "episodes": "episode_id",
    "participant_states": "state_id",
    "temporal_relations": "temporal_relation_id",
    "person_states": "state_id",
    "title_mentions": "title_mention_id",
    "uncertainties": "uncertainty_id",
}


def read_json(root: Path, relative: Path) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def sha256_file(root: Path, relative: Path) -> str:
    return hashlib.sha256((root / relative).read_bytes()).hexdigest()


def add(errors: list[str], message: str) -> None:
    errors.append(message)


def walk_forbidden_dates(value: Any, path: str = "document") -> list[str]:
    forbidden = {"start_year", "end_year", "start_year_ce", "end_year_ce", "date", "date_or_age", "year"}
    errors: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) in forbidden:
                errors.append(f"derived/date answer field present at {path}.{key}")
            errors.extend(walk_forbidden_dates(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(walk_forbidden_dates(child, f"{path}[{index}]"))
    return errors


def view_item_id(field: str, item: Mapping[str, Any]) -> str:
    return str(item.get(ITEM_ID_FIELDS[field], ""))


def validate_endpoint_ids(errors: list[str], story_id: str, view_name: str, view: Mapping[str, Any], people: set[str], rulers: set[str]) -> None:
    for item in view.get("participant_states", []):
        person_id = item.get("person_id")
        if person_id is not None and person_id not in people:
            add(errors, f"unknown Person endpoint in {story_id}/{view_name}: {person_id}")
        candidates = set(str(value) for value in item.get("candidate_person_ids", []))
        if not candidates.issubset(people):
            add(errors, f"unknown Person candidate in {story_id}/{view_name}: {sorted(candidates - people)}")
    for item in view.get("title_mentions", []):
        entity_id = item.get("entity_id")
        entity_type = item.get("entity_type")
        if entity_id is not None and entity_type == "person" and entity_id not in people:
            add(errors, f"unknown title Person endpoint in {story_id}/{view_name}: {entity_id}")
        if entity_id is not None and entity_type == "ruler" and entity_id not in rulers:
            add(errors, f"unknown title ruler endpoint in {story_id}/{view_name}: {entity_id}")
        candidates = set(str(value) for value in item.get("candidate_entity_ids", []))
        if not candidates.issubset(people | rulers):
            add(errors, f"unknown title candidate in {story_id}/{view_name}: {sorted(candidates - people - rulers)}")
    for item in view.get("person_states", []):
        person_id = item.get("person_id")
        if person_id is not None and person_id not in people:
            add(errors, f"unknown person-state endpoint in {story_id}/{view_name}: {person_id}")


def validate_view_invariants(
    errors: list[str],
    story_id: str,
    view_name: str,
    source_record: Mapping[str, Any],
    view: Mapping[str, Any],
    record_evidence_ids: set[str],
    people: set[str],
    rulers: set[str],
) -> None:
    expected_ids = set(record_evidence_ids) if view_name == "evidence_resolved" else {
        str(ref["evidence_id"]) for ref in source_record.get("evidence_refs", []) if ref.get("source_layer") == "base_text"
    }
    if set(view.get("evidence_ids", [])) != expected_ids:
        add(errors, f"wrong view evidence universe in {story_id}/{view_name}")
    validate_endpoint_ids(errors, story_id, view_name, view, people, rulers)
    for field in VIEW_FIELDS:
        source_rows = {str(row.get(ITEM_ID_FIELDS[field])): row for row in source_record.get(field, [])}
        view_rows = {view_item_id(field, row): row for row in view.get(field, [])}
        if set(view_rows) != set(source_rows):
            add(errors, f"view item universe changed in {story_id}/{view_name}/{field}")
        if len(view_rows) != len(view.get(field, [])):
            add(errors, f"duplicate view item IDs in {story_id}/{view_name}/{field}")
        for item_id, row in view_rows.items():
            if not isinstance(row.get("availability"), str):
                add(errors, f"missing availability in {story_id}/{view_name}/{field}/{item_id}")
            evidence_ids = set(str(value) for value in row.get("evidence_ids", []))
            if not evidence_ids.issubset(expected_ids):
                add(errors, f"view item references evidence outside its view in {story_id}/{view_name}/{field}/{item_id}")
            source = source_rows.get(item_id, {})
            for key in ("surface", "episode_id", "role", "presence_status", "state_kind", "title_mention_id", "temporal_relation_id", "uncertainty_id"):
                if key in source and row.get(key) != source.get(key):
                    add(errors, f"view changed observable field {key} in {story_id}/{view_name}/{field}/{item_id}")
            if view_name == "evidence_resolved":
                for key, value in source.items():
                    if key == "availability":
                        continue
                    if key not in {"evidence_ids"} and row.get(key) != value:
                        add(errors, f"evidence-resolved view changed HR0 field {key} in {story_id}/{field}/{item_id}")


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    required = [
        HR0_PATH,
        EXTRA_SPEC_PATH,
        SC1_PATH,
        HR0_SCHEMA_PATH,
        SCHEMA_PATH,
        BENCHMARK_PATH,
        PROTECTION_PATH,
    ]
    for relative in required:
        if not (root / relative).is_file():
            add(errors, f"missing HR0.1 input/output: {relative}")
    if errors:
        return errors

    benchmark = read_json(root, BENCHMARK_PATH)
    schema = read_json(root, SCHEMA_PATH)
    hr0 = read_json(root, HR0_PATH)
    extra_spec = read_json(root, EXTRA_SPEC_PATH)
    sc1 = read_json(root, SC1_PATH)
    protection = read_json(root, PROTECTION_PATH)

    schema_errors = sorted(Draft202012Validator(schema).iter_errors(benchmark), key=lambda error: list(error.absolute_path))
    errors.extend(f"schema: {error.message} at /{'/'.join(str(part) for part in error.absolute_path)}" for error in schema_errors)
    errors.extend(walk_forbidden_dates(benchmark))

    people = {str(row.get("id")) for row in sc1.get("people", [])}
    rulers = {str(row.get("ruler_id", row.get("id"))) for row in sc1.get("ruler_identities", [])}
    evidence = {str(row.get("id")) for row in sc1.get("evidence", [])}
    hr0_by_story = {str(row.get("story_id")): row for row in hr0.get("records", [])}
    records = list(benchmark.get("records", []))
    by_story = {str(row.get("story_id")): row for row in records}
    if len(by_story) != len(records):
        add(errors, "HR0.1 contains duplicate Story records")
    if set(by_story) != set(hr0_by_story):
        add(errors, "HR0.1 Story universe differs from HR0")
    if benchmark.get("scope", {}).get("selected_story_ids") != sorted(hr0_by_story):
        add(errors, "HR0.1 Story ordering/universe is inconsistent")
    if benchmark.get("scope", {}).get("story_count") != len(records):
        add(errors, "HR0.1 story_count is inconsistent")
    if benchmark.get("scope", {}).get("pass_a") != "shishuo_only" or benchmark.get("scope", {}).get("pass_b") != "evidence_augmented":
        add(errors, "HR1 pass labels are not explicit")

    expected_source_hashes = {
        str(path): sha256_file(root, path)
        for path in [HR0_PATH, EXTRA_SPEC_PATH, SC1_PATH, HR0_SCHEMA_PATH, SCHEMA_PATH]
    }
    if benchmark.get("source_hashes") != expected_source_hashes:
        add(errors, "HR0.1 source_hashes do not match current inputs")
    if any(Path(str(path)).is_absolute() for path in benchmark.get("source_hashes", {})):
        add(errors, "HR0.1 source hashes contain an absolute path")

    expected_extra = {str(row.get("case_id")): row for row in extra_spec.get("additional_cases", [])}
    expected_case_keys: set[tuple[str, str]] = set()
    expected_extra_ids: set[str] = set()
    for story_id, source in hr0_by_story.items():
        for uncertainty in source.get("uncertainties", []):
            expected_case_keys.add((story_id, str(uncertainty.get("uncertainty_id"))))
    for row in extra_spec.get("additional_cases", []):
        expected_extra_ids.add(str(row.get("case_id")))

    seen_cases: set[str] = set()
    actual_original_keys: set[tuple[str, str]] = set()
    actual_extra_ids: set[str] = set()
    for story_id, output in by_story.items():
        source = hr0_by_story[story_id]
        source_evidence_refs = {str(ref["evidence_id"]): ref for ref in source.get("evidence_refs", [])}
        output_evidence_refs = {str(ref["evidence_id"]): ref for ref in output.get("evidence_refs", [])}
        if output_evidence_refs != source_evidence_refs:
            add(errors, f"HR0 evidence reference payload changed in {story_id}")
        if set(output.get("case_ids", [])) != {str(case.get("case_id")) for case in output.get("resolution_cases", [])}:
            add(errors, f"case_ids mismatch in {story_id}")
        for case in output.get("resolution_cases", []):
            case_id = str(case.get("case_id"))
            if case_id in seen_cases:
                add(errors, f"duplicate resolution case ID: {case_id}")
            seen_cases.add(case_id)
            if str(case.get("story_id")) != story_id or str(case.get("situation_id")) != str(output.get("situation_id")):
                add(errors, f"case Story/situation endpoint mismatch: {case_id}")
            dep = case.get("resolution_dependency", {})
            uncertainty_id = str(dep.get("uncertainty_id"))
            original_uncertainty_ids = {str(row.get("uncertainty_id")) for row in source.get("uncertainties", [])}
            if case_id in expected_extra_ids:
                actual_extra_ids.add(case_id)
                if str(expected_extra[case_id].get("uncertainty_id")) != uncertainty_id:
                    add(errors, f"extra case uncertainty lineage changed: {case_id}")
            else:
                actual_original_keys.add((story_id, uncertainty_id))
                if uncertainty_id not in original_uncertainty_ids:
                    add(errors, f"case does not resolve an HR0 uncertainty: {case_id}")
            shishuo_refs = set(str(value) for value in case.get("shishuo_evidence_refs", []))
            resolution_refs = set(str(value) for value in case.get("resolution_evidence_refs", []))
            dependency_refs = set(str(value) for value in dep.get("evidence_refs", []))
            if not shishuo_refs or not resolution_refs:
                add(errors, f"case lacks both evidence views: {case_id}")
            if dependency_refs != shishuo_refs | resolution_refs:
                add(errors, f"dependency evidence_refs are not the case evidence union: {case_id}")
            if not dependency_refs.issubset(set(source_evidence_refs)):
                add(errors, f"case references evidence outside its Story: {case_id}")
            if not dependency_refs.issubset(evidence):
                add(errors, f"case references unknown SC1 evidence: {case_id}")
            requires = set(str(value) for value in dep.get("requires", []))
            if not requires.issubset(ALLOWED_REQUIRES):
                add(errors, f"unsupported dependency type in {case_id}")
            layers = {source_evidence_refs[evidence_id].get("source_layer") for evidence_id in dependency_refs if evidence_id in source_evidence_refs}
            if "liu_annotation" in requires and "liu_annotation" not in layers:
                add(errors, f"liu_annotation dependency lacks annotation evidence: {case_id}")
            if "external_source" in requires and "secondary_reference" not in layers:
                add(errors, f"external_source dependency lacks secondary evidence: {case_id}")
            status = dep.get("resolved_status")
            value = dep.get("resolved_value")
            if status in {"resolved", "refined"} and value is None:
                add(errors, f"resolved case has no resolved value: {case_id}")
            if status in {"unresolved", "unresolved_even_with_available_evidence"} and value is not None:
                add(errors, f"unresolved case has a resolved value: {case_id}")
            for affected in case.get("affected_items", []):
                field = str(affected.get("field"))
                item_key = str(affected.get("item_id"))
                if field not in VIEW_FIELDS or item_key not in {str(row.get(ITEM_ID_FIELDS[field])) for row in source.get(field, [])}:
                    add(errors, f"case has an orphan affected item: {case_id}/{field}/{item_key}")

        record_evidence_ids = set(source_evidence_refs)
        for view_name in ("shishuo_only_gold", "evidence_resolved_gold"):
            view = output.get(view_name, {})
            if view.get("case_ids") != sorted(output.get("case_ids", [])):
                add(errors, f"view case_ids mismatch in {story_id}/{view_name}")
            validate_view_invariants(errors, story_id, "evidence_resolved" if view_name == "evidence_resolved_gold" else "shishuo_only", source, view, record_evidence_ids, people, rulers)

        base = output.get("shishuo_only_gold", {})
        augmented = output.get("evidence_resolved_gold", {})
        for field in VIEW_FIELDS:
            base_rows = {view_item_id(field, row): row for row in base.get(field, [])}
            augmented_rows = {view_item_id(field, row): row for row in augmented.get(field, [])}
            for key in base_rows.keys() & augmented_rows.keys():
                left = base_rows[key]
                right = augmented_rows[key]
                for endpoint in ("person_id", "entity_id"):
                    if left.get(endpoint) is not None and left.get(endpoint) != right.get(endpoint):
                        add(errors, f"two views contradict a Shishuo-visible endpoint in {story_id}/{field}/{key}")
                if left.get("surface") != right.get("surface"):
                    add(errors, f"two views contradict a surface in {story_id}/{field}/{key}")

    if actual_original_keys != expected_case_keys:
        add(errors, "not every HR0 uncertainty has exactly one resolution case")
    if actual_extra_ids != expected_extra_ids:
        add(errors, "not every explicit HR0.1 resolution case was emitted")
    if len(seen_cases) != len(expected_case_keys) + len(expected_extra_ids):
        add(errors, "resolution case count does not match HR0 uncertainties plus explicit cases")

    if benchmark.get("policy") != {
        "canonical_data_write_back": False,
        "hr0_input_immutable": True,
        "resolution_requires_explicit_evidence": True,
        "unresolved_preserved": True,
        "llm": False,
        "rag": False,
        "temporal_solver": False,
    }:
        add(errors, "HR0.1 policy flags changed")

    protected = protection.get("protected_input_hashes", {})
    for relative, expected in protected.items():
        path = Path(str(relative))
        if path.is_absolute() or not (root / path).is_file() or sha256_file(root, path) != expected:
            add(errors, f"protected HR0/HG0/ML0 input hash mismatch: {relative}")
    if any(protection.get("write_back", {}).values()):
        add(errors, "HR0.1 protection manifest permits write-back")
    if protection.get("protected_input_hashes", {}).get(str(HR0_PATH)) != sha256_file(root, HR0_PATH):
        add(errors, "HR0 Gold Set is not protected by its current hash")

    # Rebuilding twice is part of the validator, not merely a test fixture.
    first = build_documents(root)
    second = build_documents(root)
    if first != second:
        add(errors, "HR0.1 builder is not deterministic")
    if benchmark != first[0]:
        add(errors, "committed HR0.1 benchmark does not match the deterministic builder")

    return errors


if __name__ == "__main__":
    problems = validate()
    if problems:
        print("\n".join(f"ERROR: {problem}" for problem in problems))
        raise SystemExit(1)
    print("HR0.1 validation passed")
