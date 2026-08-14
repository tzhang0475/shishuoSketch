#!/usr/bin/env python3
"""Validate the S2.2 selection and Person life-glimpse overlays."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SELECTION_PATH = Path("data/annotation/s2-narrative-density-selection.json")
SELECTION_SCHEMA = Path("schema/s2-narrative-density-selection.schema.json")
LIFE_PATH = Path("data/annotation/s2-person-life-glimpses.json")
LIFE_SCHEMA = Path("schema/s2-person-life-glimpse.schema.json")
SC1_PATH = Path("data/derived/sc1-site.json")
SCENE_PATH = Path("data/annotation/story-scene-contexts.json")


def read(root: Path, path: Path) -> Any:
    return json.loads((root / path).read_text(encoding="utf-8"))


def _schema_errors(root: Path, document: Mapping[str, Any], schema_path: Path, label: str) -> list[str]:
    schema = read(root, schema_path)
    Draft202012Validator.check_schema(schema)
    return [f"{label}: {error.message}" for error in Draft202012Validator(schema).iter_errors(document)]


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        selection = read(root, SELECTION_PATH)
        life = read(root, LIFE_PATH)
        bundle = read(root, SC1_PATH)
        scenes = read(root, SCENE_PATH)
    except (OSError, ValueError) as exc:
        return [f"S2.2 input cannot be read: {exc}"]
    errors.extend(_schema_errors(root, selection, SELECTION_SCHEMA, "S2 selection"))
    errors.extend(_schema_errors(root, life, LIFE_SCHEMA, "S2 life glimpse"))
    stories = {
        str(story["id"]): story
        for story in bundle.get("stories", [])
        if isinstance(story, Mapping) and story.get("publication_state") != "blocked"
    }
    people = {
        str(person["id"])
        for person in bundle.get("people", [])
        if isinstance(person, Mapping) and isinstance(person.get("id"), str)
    }
    evidence = {
        str(item["id"])
        for item in bundle.get("evidence", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    records = selection.get("records", [])
    ranks = [item.get("selection_rank") for item in records]
    if ranks != list(range(1, len(records) + 1)):
        errors.append("S2 selection ranks are not contiguous and deterministic")
    story_ids = [item.get("story_id") for item in records]
    if len(story_ids) != len(set(story_ids)):
        errors.append("S2 selection contains duplicate Story IDs")
    for required in ("06-yaliang-017", "05-fangzheng-031", "02-yanyu-036"):
        if required not in story_ids:
            errors.append(f"S2 selection misses mandatory Story: {required}")
    for record in records:
        if record.get("story_id") not in stories:
            errors.append(f"S2 selection references unknown or unpublished Story: {record.get('story_id')}")
        for evidence_id in record.get("evidence_ids", []):
            if evidence_id not in evidence:
                errors.append(f"S2 selection Evidence does not resolve: {record.get('story_id')}/{evidence_id}")
    scenes_by_story = {
        str(record.get("story_id")): record
        for record in scenes.get("records", [])
        if isinstance(record, Mapping) and isinstance(record.get("story_id"), str)
    }
    for story_id in story_ids:
        scene = scenes_by_story.get(str(story_id))
        if not isinstance(scene, Mapping):
            errors.append(f"S2 selected Story lacks a Scene Context record: {story_id}")
            continue
        layers = scene.get("narrative_layers")
        if not isinstance(layers, Mapping) or not isinstance(layers.get("scene_focus"), list) or not layers["scene_focus"]:
            errors.append(f"S2 selected Story lacks a substantive 舞台 claim: {story_id}")
    life_people: set[str] = set()
    for record in life.get("records", []):
        person_id = record.get("person_id")
        life_people.add(str(person_id))
        if person_id not in people:
            errors.append(f"S2 life glimpse references unknown Person: {person_id}")
        points = record.get("points", [])
        if len(points) > 4:
            errors.append(f"S2 life glimpse has too many overlay points: {person_id}")
        for index, point in enumerate(points):
            for evidence_id in point.get("evidence_ids", []):
                if evidence_id not in evidence:
                    errors.append(f"S2 life Evidence does not resolve: {person_id}/{index}/{evidence_id}")
            for story_id in point.get("story_ids", []):
                if story_id not in stories:
                    errors.append(f"S2 life Story does not resolve: {person_id}/{index}/{story_id}")
            if point.get("review_status") != "candidate":
                errors.append(f"S2 generated life prose must remain candidate: {person_id}/{index}")
    if not 10 <= len(life_people) <= 15:
        errors.append(f"S2 life glimpse Person coverage should be 10–15, got {len(life_people)}")
    if any("relation" in key for record in records for key in record.get("dimensions", {})):
        errors.append("S2 selection must not use a Relation field as a factual assertion")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = validate(args.root)
    if errors:
        print("S2.2 validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("S2.2 narrative density artifacts valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
