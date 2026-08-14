#!/usr/bin/env python3
"""Validate the R3A explicit Person Relation candidate artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

try:
    from .person_relation_candidates_r3 import (
        DERIVED_PATH,
        RELATIONS_PATH,
        SC1_PATH,
        SCHEMA_PATH,
        SOURCE_PATH,
        candidate_id,
        project,
        validate_source,
    )
except ImportError:
    from person_relation_candidates_r3 import (
        DERIVED_PATH,
        RELATIONS_PATH,
        SC1_PATH,
        SCHEMA_PATH,
        SOURCE_PATH,
        candidate_id,
        project,
        validate_source,
    )


ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(root: Path = ROOT, *, document: Mapping[str, Any] | None = None) -> list[str]:
    errors = validate_source(root)
    try:
        source = read_json(root / SOURCE_PATH)
        bundle = read_json(root / SC1_PATH)
        relations = read_json(root / RELATIONS_PATH)
        actual = document or read_json(root / DERIVED_PATH)
        schema = read_json(root / Path("schema/person-relation-candidates-r3.schema.json"))
        errors.extend(error.message for error in Draft202012Validator(schema).iter_errors(actual))
    except (OSError, ValueError, KeyError) as exc:
        return errors + [f"R3A artifact could not be read: {exc}"]

    people = {
        str(person["id"]): person
        for person in bundle.get("people", [])
        if isinstance(person, Mapping) and isinstance(person.get("id"), str)
    }
    evidence_ids = {
        str(item["id"])
        for item in bundle.get("evidence", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    story_ids = {
        str(story["id"])
        for story in bundle.get("stories", [])
        if isinstance(story, Mapping) and isinstance(story.get("id"), str)
    }
    reviewed_pairs: set[tuple[str, str]] = set()
    reviewed_ids: set[str] = set()
    for relation in relations.get("records", []):
        if relation.get("review_status") == "reviewed":
            a, b = sorted((str(relation.get("subject_id")), str(relation.get("object_id"))))
            reviewed_pairs.add((a, b))
            reviewed_ids.add(str(relation["id"]))

    if actual != project(root):
        errors.append("derived R3A projection is not deterministic")
    if actual.get("production_person_count") != len(people):
        errors.append("R3A production Person count does not match the current registry")
    if actual.get("production_person_ids") != sorted(people):
        errors.append("R3A production Person ordering is not deterministic")
    if actual.get("candidate_count") != len(actual.get("candidates", [])):
        errors.append("R3A candidate_count mismatch")
    if actual.get("pair_count_audited") != len(people) * (len(people) - 1) // 2:
        errors.append("R3A pair audit does not cover every unordered Person pair")
    if actual.get("already_reviewed_rediscovery_count") != len(actual.get("already_reviewed_rediscoveries", [])):
        errors.append("R3A rediscovery count mismatch")

    source_records = source.get("records", [])
    if len(source_records) != len(actual.get("candidates", [])):
        errors.append("R3A source and derived candidate counts differ")
    source_by_id = {
        candidate_id(record): record
        for record in source_records
    }
    seen_pairs: set[tuple[str, str]] = set()
    seen_ids: set[str] = set()
    for item in actual.get("candidates", []):
        a, b = item.get("person_a_id"), item.get("person_b_id")
        pair = tuple(sorted((str(a), str(b))))
        if a not in people or b not in people:
            errors.append(f"R3A candidate endpoint does not resolve: {a}, {b}")
        if a == b:
            errors.append(f"R3A candidate is a self relation: {a}")
        if pair in seen_pairs:
            errors.append(f"duplicate R3A semantic pair: {pair}")
        seen_pairs.add(pair)
        if pair in reviewed_pairs:
            errors.append(f"R3A duplicates an existing reviewed Relation pair: {pair}")
        if item.get("review_status") != "candidate":
            errors.append(f"R3A candidate is not review_status=candidate: {item.get('candidate_id')}")
        if item.get("candidate_id") in seen_ids:
            errors.append(f"duplicate R3A candidate ID: {item.get('candidate_id')}")
        seen_ids.add(str(item.get("candidate_id")))
        record = source_by_id.get(item.get("candidate_id"))
        if record is None:
            errors.append(f"R3A candidate ID has no source record: {item.get('candidate_id')}")
        else:
            if record.get("review_status") != "candidate":
                errors.append(f"R3A source candidate is not candidate: {item.get('candidate_id')}")
            if candidate_id(record) != item.get("candidate_id"):
                errors.append(f"R3A candidate ID is not the stable semantic hash: {item.get('candidate_id')}")
        if not set(item.get("evidence_ids", [])) <= evidence_ids:
            errors.append(f"R3A candidate references missing Evidence: {item.get('candidate_id')}")
        if set(item.get("existing_reviewed_relation_ids", [])) & reviewed_ids:
            errors.append(f"R3A candidate incorrectly carries reviewed relation IDs: {item.get('candidate_id')}")
        if not item.get("source_entry_ids") and not item.get("source_unit_ids"):
            errors.append(f"R3A candidate has no source anchor: {item.get('candidate_id')}")
        if any("cooccurrence" in str(flag) for flag in item.get("risk_flags", [])):
            errors.append(f"co-occurrence-only basis cannot be an R3A candidate: {item.get('candidate_id')}")
        for story_id in item.get("current_story_ids", []):
            if story_id not in story_ids:
                errors.append(f"R3A candidate references unknown Story: {story_id}")

    expected_ranks = list(range(1, len(actual.get("candidates", [])) + 1))
    if [item.get("rank") for item in actual.get("candidates", [])] != expected_ranks:
        errors.append("R3A candidate ranks are not sequential")
    if set(actual.get("wave1_person_ids", [])) - set(people):
        errors.append("R3A Wave-1 audit references an unknown Person")
    if set(actual.get("wave2_person_ids", [])) - set(people):
        errors.append("R3A Wave-2 audit references an unknown Person")
    if not set(actual.get("wave1_persons_with_candidate_relation", [])) <= set(actual.get("wave1_person_ids", [])):
        errors.append("R3A Wave-1 candidate endpoint summary is invalid")
    if not set(actual.get("wave2_persons_with_candidate_relation", [])) <= set(actual.get("wave2_person_ids", [])):
        errors.append("R3A Wave-2 candidate endpoint summary is invalid")
    if not set(actual.get("isolated_person_ids_by_reviewed_relation", [])) <= set(people):
        errors.append("R3A isolated Person summary references an unknown Person")
    for row in actual.get("cooccurrence_only_pairs", []):
        pair = tuple(sorted((row.get("person_a_id"), row.get("person_b_id"))))
        if row.get("has_r3a_candidate") or pair in seen_pairs:
            errors.append(f"R3A co-occurrence-only report contains a candidate pair: {pair}")
    for row in actual.get("scene_encounters", []):
        if row.get("story_id") not in story_ids:
            errors.append(f"R3A Scene cross-audit references unknown Story: {row.get('story_id')}")
        if row.get("person_a_id") not in people or row.get("person_b_id") not in people:
            errors.append(f"R3A Scene cross-audit references unknown Person: {row.get('story_id')}")
        if row.get("disposition") == "scene_encounter_only" and (row.get("r3a_candidate_id") or row.get("reviewed_relation_ids")):
            errors.append(f"R3A Scene encounter disposition is inconsistent: {row.get('story_id')}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = validate(args.root)
    if errors:
        print("R3A validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("R3A Person Relation candidate artifacts valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
