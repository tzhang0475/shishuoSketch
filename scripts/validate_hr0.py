#!/usr/bin/env python3
"""Validate the HR0 HistoricalSituation v0 Gold Set."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_hr0_historical_situations import (  # noqa: E402
    GOLD_PATH,
    METRICS_PATH,
    PARTICIPANT_PATH,
    PROTECTION_PATH,
    SC1_PATH,
    SCENE_SOURCE_PATH,
    SCHEMA_PATH,
    SELECTION_PATH,
    SOURCE_LAYER,
    SPEC_PATH,
    build_documents,
    quote_sha256,
)


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


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    required = [SPEC_PATH, SC1_PATH, PARTICIPANT_PATH, SCENE_SOURCE_PATH, SCHEMA_PATH, GOLD_PATH, SELECTION_PATH, METRICS_PATH, PROTECTION_PATH]
    for relative in required:
        if not (root / relative).is_file():
            add(errors, f"missing HR0 input/output: {relative}")
    if errors:
        return errors

    schema = read_json(root, SCHEMA_PATH)
    gold = read_json(root, GOLD_PATH)
    spec = read_json(root, SPEC_PATH)
    sc1 = read_json(root, SC1_PATH)
    selection = read_json(root, SELECTION_PATH)
    metrics = read_json(root, METRICS_PATH)
    protection = read_json(root, PROTECTION_PATH)

    schema_errors = sorted(Draft202012Validator(schema).iter_errors(gold), key=lambda error: list(error.absolute_path))
    errors.extend(f"schema: {error.message} at /{'/'.join(str(part) for part in error.absolute_path)}" for error in schema_errors)
    errors.extend(walk_forbidden_dates(gold))

    stories = {str(row.get("id")) for row in sc1.get("stories", [])}
    people = {str(row.get("id")) for row in sc1.get("people", [])}
    rulers = {str(row.get("ruler_id", row.get("id"))) for row in sc1.get("ruler_identities", [])}
    evidence = {str(row.get("id")): row for row in sc1.get("evidence", [])}
    spec_records = {str(row.get("story_id")): row for row in spec.get("records", [])}
    gold_records = list(gold.get("records", []))
    gold_by_story = {str(row.get("story_id")): row for row in gold_records}

    if not 15 <= len(gold_records) <= 20:
        add(errors, f"Gold pilot size is outside 15–20: {len(gold_records)}")
    if len(gold_by_story) != len(gold_records):
        add(errors, "Gold records contain duplicate Story IDs")
    if set(gold_by_story) != set(spec_records):
        add(errors, "Gold Story universe differs from tracked reviewed spec")
    if gold.get("scope", {}).get("selected_story_ids") != sorted(gold_by_story):
        add(errors, "Gold scope Story ordering/universe is inconsistent")
    if gold.get("scope", {}).get("story_count") != len(gold_records):
        add(errors, "Gold scope.story_count is inconsistent")
    if selection.get("story_count") != len(gold_records):
        add(errors, "selection manifest story count is inconsistent")
    if [row.get("story_id") for row in selection.get("records", [])] != sorted(gold_by_story):
        add(errors, "selection manifest Story ordering differs from Gold set")

    # The generated source hashes are portable relative paths and must point
    # to the exact inputs used for this reviewed snapshot.
    expected_hashes = {str(path): sha256_file(root, path) for path in [SPEC_PATH, SC1_PATH, PARTICIPANT_PATH, SCENE_SOURCE_PATH, SCHEMA_PATH]}
    if gold.get("source_hashes") != expected_hashes:
        add(errors, "Gold source_hashes do not match current HR0 inputs")
    if selection.get("source_hashes") != expected_hashes or metrics.get("source_hashes") != expected_hashes:
        add(errors, "HR0 derived artifacts do not share the current input hash set")
    if any(Path(str(path)).is_absolute() for path in gold.get("source_hashes", {})):
        add(errors, "HR0 source hashes contain an absolute path")

    usage_names = {
        "episodes": "episode",
        "participant_states": "participant_state",
        "person_states": "person_state",
        "title_mentions": "title_mention",
        "temporal_relations": "temporal_relation",
        "uncertainties": "uncertainty",
    }
    item_id_fields = {
        "episodes": "episode_id",
        "participant_states": "state_id",
        "person_states": "state_id",
        "title_mentions": "title_mention_id",
        "temporal_relations": "temporal_relation_id",
        "uncertainties": "uncertainty_id",
    }
    for record in gold_records:
        story_id = str(record.get("story_id"))
        if story_id not in stories:
            add(errors, f"unknown Story endpoint: {story_id}")
        source_record = spec_records.get(story_id, {})
        if record.get("selection_categories") != sorted(set(source_record.get("selection_categories", []))):
            add(errors, f"selection categories changed for {story_id}")
        if record.get("selection_reason") != source_record.get("selection_reason"):
            add(errors, f"selection reason changed for {story_id}")

        episode_ids = {str(row.get("episode_id")) for row in record.get("episodes", [])}
        if len(episode_ids) != len(record.get("episodes", [])):
            add(errors, f"duplicate episode IDs in {story_id}")
        nested_usage: dict[str, set[str]] = {}
        for field, usage_name in usage_names.items():
            item_ids: set[str] = set()
            for item in record.get(field, []):
                id_field = item_id_fields[field]
                if id_field:
                    item_id = str(item[id_field])
                    if item_id in item_ids:
                        add(errors, f"duplicate {id_field} in {story_id}: {item_id}")
                    item_ids.add(item_id)
                if item.get("review_status") != "reviewed":
                    add(errors, f"unreviewed HR0 item in {story_id}: {field}")
                for evidence_id in item.get("evidence_ids", []):
                    nested_usage.setdefault(str(evidence_id), set()).add(usage_name)
                if field in {"episodes", "participant_states", "person_states", "title_mentions", "temporal_relations", "uncertainties"} and not item.get("evidence_ids"):
                    add(errors, f"{field} item has no evidence in {story_id}")

            if field == "temporal_relations":
                for relation in record.get(field, []):
                    if relation.get("from_episode_id") not in episode_ids:
                        add(errors, f"temporal relation has an orphan from episode in {story_id}")
                    if relation.get("to_episode_id") is not None and relation.get("to_episode_id") not in episode_ids:
                        add(errors, f"temporal relation has an orphan to episode in {story_id}")

        for item in record.get("participant_states", []):
            if item.get("episode_id") not in episode_ids:
                add(errors, f"participant state has an orphan episode in {story_id}")
            if item.get("person_id") is not None and item.get("person_id") not in people:
                add(errors, f"participant state has an unknown Person in {story_id}")
            if item.get("person_id") is None:
                candidates = set(item.get("candidate_person_ids", []))
                if not candidates.issubset(people):
                    add(errors, f"participant state has an unknown Person candidate in {story_id}")
                if item.get("resolution_status") == "resolved":
                    resolved_title_surfaces = {str(title.get("surface")) for title in record.get("title_mentions", []) if title.get("resolution_status") == "resolved" and title.get("entity_id") in rulers}
                    if item.get("surface") not in resolved_title_surfaces:
                        add(errors, f"resolved participant lacks a Person endpoint or resolved ruler title in {story_id}: {item.get('surface')}")

        for item in record.get("person_states", []):
            if item.get("person_id") not in people:
                add(errors, f"person state has an unknown Person in {story_id}: {item.get('person_id')}")
        for item in record.get("title_mentions", []):
            entity_type = item.get("entity_type")
            entity_id = item.get("entity_id")
            if entity_type == "person" and entity_id is not None and entity_id not in people:
                add(errors, f"title mention has an unknown Person in {story_id}: {entity_id}")
            if entity_type == "ruler" and entity_id is not None and entity_id not in rulers:
                add(errors, f"title mention has an unknown ruler in {story_id}: {entity_id}")
            if not set(item.get("candidate_entity_ids", [])).issubset(people | rulers):
                add(errors, f"title mention has an unknown candidate endpoint in {story_id}")

        refs = {str(ref.get("evidence_id")): ref for ref in record.get("evidence_refs", [])}
        if len(refs) != len(record.get("evidence_refs", [])):
            add(errors, f"duplicate evidence refs in {story_id}")
        if set(refs) != set(nested_usage):
            add(errors, f"evidence refs are orphaned or incomplete in {story_id}")
        for evidence_id, ref in refs.items():
            source = evidence.get(evidence_id)
            if source is None:
                add(errors, f"unknown evidence endpoint in {story_id}: {evidence_id}")
                continue
            if ref.get("usage") != sorted(nested_usage[evidence_id]):
                add(errors, f"evidence usage mismatch in {story_id}: {evidence_id}")
            for field in ("source_id", "evidence_type", "review_status", "assertion_status", "locator"):
                if ref.get(field) != source.get(field):
                    add(errors, f"evidence provenance mismatch in {story_id}: {evidence_id}/{field}")
            if ref.get("source_layer") != SOURCE_LAYER.get(str(source.get("evidence_type")), "unknown"):
                add(errors, f"evidence source layer mismatch in {story_id}: {evidence_id}")
            if ref.get("quote_sha256") != quote_sha256(str(source.get("quote", ""))):
                add(errors, f"evidence quote fingerprint mismatch in {story_id}: {evidence_id}")
            if Path(str(ref.get("locator", {}).get("artifact_path", ""))).is_absolute() or Path(str(ref.get("locator", {}).get("source_provenance", {}).get("source_path", ""))).is_absolute():
                add(errors, f"evidence locator contains an absolute path in {story_id}: {evidence_id}")

    # The output must be a downstream situation set, not a second canonical
    # fact/relation/person store.
    forbidden_keys = {"fact_id", "relation_id", "canonical_fact", "canonical_relation", "new_person"}
    if any(key in forbidden_keys for record in gold_records for key in record):
        add(errors, "HR0 Gold record contains a canonical mutation field")
    if gold.get("policy") != {
        "canonical_data_write_back": False,
        "canonical_fact_materialization": False,
        "inference": False,
        "derived_story_dates_as_answers": False,
        "evidence_required": True,
        "review_model": "reviewed_deterministic_gold",
    }:
        add(errors, "HR0 policy flags changed")

    protected = protection.get("protected_input_hashes", {})
    for relative, expected in protected.items():
        path = Path(str(relative))
        if path.is_absolute() or not (root / path).is_file() or sha256_file(root, path) != expected:
            add(errors, f"protected HR0 input hash mismatch: {relative}")
    if any(protection.get("write_back", {}).values()):
        add(errors, "HR0 protection manifest permits write-back")

    # Building twice in memory catches unordered source traversal and any
    # accidental volatile field before the test layer sees the output files.
    first = build_documents(root)
    second = build_documents(root)
    if first != second:
        add(errors, "HR0 builder is not deterministic")

    return errors


if __name__ == "__main__":
    problems = validate()
    if problems:
        print("\n".join(f"ERROR: {problem}" for problem in problems))
        raise SystemExit(1)
    print("HR0 validation passed")
