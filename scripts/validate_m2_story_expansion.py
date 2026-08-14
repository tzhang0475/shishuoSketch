#!/usr/bin/env python3
"""Validate the deterministic M2A Story publication union."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = Path("data/annotation/story-expansion-wave-1.json")
RANKING_PATH = Path("data/derived/m2-story-expansion-ranking.json")
GOLD_PATH = Path("data/story-chain-gold-set.json")
SC1_PATH = Path("data/derived/sc1-site.json")
SCENE_PATH = Path("data/annotation/story-scene-contexts.json")


def read(root: Path, path: Path) -> Any:
    return json.loads((root / path).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        manifest = read(root, MANIFEST_PATH)
        ranking = read(root, RANKING_PATH)
        gold = read(root, GOLD_PATH)
        bundle = read(root, SC1_PATH)
        scenes = read(root, SCENE_PATH)
        schema = read(root, Path("schema/story-expansion-wave-m2.schema.json"))
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        return [f"M2 Story expansion artifact cannot be read: {exc}"]

    errors.extend(f"Story expansion schema: {e.message}" for e in Draft202012Validator(schema).iter_errors(manifest))
    gold_ids = [str(x.get("entry_id")) for x in gold.get("records", []) if isinstance(x, Mapping)]
    if len(gold_ids) != 16 or len(set(gold_ids)) != 16:
        errors.append("SC0 Gold Set is not the frozen 16-story set")
    if manifest.get("gold_story_ids") != gold_ids:
        errors.append("M2 manifest does not preserve the exact ordered SC0 Gold Set")
    if sha256(root / RANKING_PATH) != manifest.get("source_ranking_sha256"):
        errors.append("M2 Story source ranking hash does not match")

    records = manifest.get("records", [])
    expansion_ids = [str(x.get("story_id")) for x in records]
    if expansion_ids != list(manifest.get("expansion_story_ids", [])):
        errors.append("M2 expansion_story_ids do not match manifest record order")
    if len(expansion_ids) != len(set(expansion_ids)):
        errors.append("M2 expansion Story IDs are not unique")
    if set(expansion_ids) & set(gold_ids):
        errors.append("M2 expansion overlaps the frozen SC0 Gold Set")
    if [x.get("selection_rank") for x in records] != list(range(1, len(records) + 1)):
        errors.append("M2 Story selection ranks are not sequential")

    ranking_rows = {str(x.get("story_id")): x for x in ranking.get("stories", []) if isinstance(x, Mapping)}
    if list(ranking.get("selected_expansion_story_ids", [])) != expansion_ids:
        errors.append("M2 manifest selection differs from deterministic ranking selection")
    for record in records:
        row = ranking_rows.get(record.get("story_id"))
        if row is None:
            errors.append(f"M2 selected Story is absent from ranking: {record.get('story_id')}")
            continue
        if row.get("selected") is not True or row.get("eligible") is not True:
            errors.append(f"M2 selected Story is not eligible: {record.get('story_id')}")
        if row.get("score") != record.get("score") or row.get("components") != record.get("score_components"):
            errors.append(f"M2 selected Story score snapshot differs: {record.get('story_id')}")
        if record.get("publication_state") != row.get("publication_state"):
            errors.append(f"M2 selected Story publication state differs: {record.get('story_id')}")

    story_rows = [x for x in bundle.get("stories", []) if isinstance(x, Mapping)]
    frontend_ids = [str(x.get("id")) for x in story_rows]
    expected_ids = gold_ids + expansion_ids
    if set(frontend_ids) != set(expected_ids) or len(frontend_ids) != len(expected_ids):
        errors.append("SC1 frontend Story set is not exactly SC0 union M2 expansion")
    if len(frontend_ids) != 60:
        errors.append(f"M2 frontend Story count is {len(frontend_ids)}, expected 60 for the frozen selection")
    people_ids = {str(x.get("id")) for x in bundle.get("people", []) if isinstance(x, Mapping)}
    for story in story_rows:
        if not set(story.get("person_ids", [])) <= people_ids:
            errors.append(f"Story has an unknown production Person reference: {story.get('id')}")
    scene_ids = {str(x.get("story_id")) for x in scenes.get("records", []) if isinstance(x, Mapping)}
    if not scene_ids <= set(frontend_ids):
        errors.append("Scene Context references a Story outside the frontend publication union")
    if len(scene_ids) < 20 or len(scene_ids) > 30:
        errors.append(f"M2 Scene Context count is outside the 20–30 pilot expansion range: {len(scene_ids)}")
    return sorted(set(errors))


if __name__ == "__main__":
    problems = validate()
    if problems:
        print("M2 Story expansion validation failed:")
        print("\n".join(f"- {problem}" for problem in problems))
        raise SystemExit(1)
    print("M2 Story expansion validation passed")
