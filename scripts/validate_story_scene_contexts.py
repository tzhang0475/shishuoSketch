#!/usr/bin/env python3
"""Validate curated and generated Story Scene Context data."""

from __future__ import annotations

import json
from pathlib import Path

from story_scene_contexts import DERIVED_PATH, SC1_PATH, SOURCE_PATH, project, read_json, validate_source


ROOT = Path(__file__).resolve().parents[1]


def validate(root: Path = ROOT) -> list[str]:
    errors = validate_source(root)
    source = read_json(root / SOURCE_PATH)
    bundle = read_json(root / SC1_PATH)
    story_ids = {
        str(story["id"])
        for story in bundle.get("stories", [])
        if isinstance(story, dict) and story.get("publication_state") != "blocked"
    }
    people = bundle.get("people", [])
    evidence_ids = {
        str(item["id"])
        for item in bundle.get("evidence", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    try:
        expected = project(source, story_ids=story_ids, people=people, evidence_ids=evidence_ids)
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"Scene Context projection failed: {exc}")
        return errors
    try:
        derived = read_json(root / DERIVED_PATH)
        if derived.get("contexts") != expected:
            errors.append("derived Story Scene Context projection is not deterministic")
        if derived.get("generated_from") != [str(SOURCE_PATH), str(SC1_PATH)]:
            errors.append("derived Story Scene Context provenance is incorrect")
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"cannot read derived Story Scene Context artifact: {exc}")

    if set(expected) != {str(record["story_id"]) for record in source.get("records", [])}:
        errors.append("Scene Context source/projection keys differ")
    if "06-yaliang-029" not in expected:
        errors.append("mandatory 06-yaliang-029 Scene Context is missing")
    if len(expected) < 3 or len(expected) > 5:
        errors.append(f"Scene Context pilot must contain 3–5 Stories, found {len(expected)}")

    for story_id, context in expected.items():
        for person in context["people_at_scene"]:
            if not any(item.get("id") == person["person_id"] for item in people if isinstance(item, dict)):
                errors.append(f"Scene Context {story_id} has unresolved materialized Person {person['person_id']}")
        for position in context["positional_context"]:
            for person_id in position["person_ids"]:
                if not any(item.get("id") == person_id for item in people if isinstance(item, dict)):
                    errors.append(f"Scene Context {story_id} positional context has unresolved Person {person_id}")
        for person in context["people_at_scene"]:
            if person["scene_role"] == "present" and not person["evidence_ids"]:
                errors.append(f"Scene Context {story_id} present Person lacks Evidence: {person['person_id']}")
        for claim in context["event_background"]:
            if claim["text"]["original"] and not claim["evidence_ids"]:
                errors.append(f"Scene Context {story_id} background claim lacks Evidence")
    return errors


if __name__ == "__main__":
    problems = validate()
    if problems:
        print("Story Scene Context validation failed:")
        print("\n".join(f"- {problem}" for problem in problems))
        raise SystemExit(1)
    print("Story Scene Context validation passed")
