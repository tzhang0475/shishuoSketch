#!/usr/bin/env python3
"""Validate the frozen W3 Person/Story expansion and SGZ0-facing contracts."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
WAVE_PATH = Path("data/annotation/person-expansion-wave-3.json")
STORY_WAVE_PATH = Path("data/annotation/story-expansion-wave-3.json")
SC1_PATH = Path("data/derived/sc1-site.json")
SC0_PATH = Path("data/story-chain-gold-set.json")
M2_PATH = Path("data/annotation/story-expansion-wave-1.json")
SCENE_PATH = Path("data/annotation/story-scene-contexts-w3.json")
PEOPLE_PATH = Path("data/people.json")
CORPUS_PATH = Path("data/shishuo-corpus-index.json")
RELATIONS_PATH = Path("data/annotation/wp1-relations.json")


def read(path: Path) -> Any:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _git_json(path: Path) -> Any | None:
    result = subprocess.run(
        ["git", "show", f"HEAD:{path.as_posix()}"],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        return None


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    wave = read(WAVE_PATH)
    story_wave = read(STORY_WAVE_PATH)
    bundle = read(SC1_PATH)
    people = read(PEOPLE_PATH).get("people", [])
    canonical_story_ids = {
        str(item.get("id"))
        for item in read(CORPUS_PATH).get("entries", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    gold_ids = [str(item["entry_id"]) for item in read(SC0_PATH).get("records", [])]
    m2_ids = [str(item["story_id"]) for item in read(M2_PATH).get("records", [])]
    w3_members = sorted(wave.get("members", []), key=lambda item: int(item.get("rank_at_selection", 10**9)))
    w3_person_ids = [str(item.get("person_id")) for item in w3_members]
    if len(w3_members) != 15:
        errors.append(f"W3 Person wave size is {len(w3_members)}, expected the frozen 15")
    if w3_person_ids != [f"person-{index:03d}" for index in range(36, 51)]:
        errors.append("W3 Person IDs are not the contiguous person-036..person-050 allocation")
    if len(set(w3_person_ids)) != len(w3_person_ids):
        errors.append("W3 Person IDs are duplicated")
    person_ids = {
        str(item.get("person_id"))
        for item in people
        if isinstance(item, Mapping) and isinstance(item.get("person_id"), str)
    }
    if not set(w3_person_ids) <= person_ids:
        errors.append("W3 Person wave contains an ID absent from the production registry")
    sketches = set(bundle.get("person_sketches", {}).keys())
    if not set(w3_person_ids) <= sketches:
        errors.append("W3 Person wave contains a Person without a Person Sketch projection")

    w3_story_ids = [str(item.get("story_id")) for item in story_wave.get("records", [])]
    if not 20 <= len(w3_story_ids) <= 30:
        errors.append(f"W3 Story wave size is {len(w3_story_ids)}, outside the evidence-safe 20–30 range")
    if len(set(w3_story_ids)) != len(w3_story_ids):
        errors.append("W3 Story IDs are duplicated")
    if not set(w3_story_ids) <= canonical_story_ids:
        errors.append("W3 Story wave contains a non-canonical Story ID")
    if set(w3_story_ids) & (set(gold_ids) | set(m2_ids)):
        errors.append("W3 Story wave overlaps SC0 or M2 publication")
    withheld_story_ids = {str(item) for item in story_wave.get("withheld_story_ids", [])}
    if "18-qiyi-002" not in withheld_story_ids:
        errors.append("W3 provenance audit does not record the withheld supplemental-only Story")
    if withheld_story_ids & set(w3_story_ids):
        errors.append("W3 withheld Story appears in the published expansion wave")
    frontend_story_ids = {
        str(item.get("id"))
        for item in bundle.get("stories", [])
        if isinstance(item, Mapping) and item.get("publication_state") != "blocked"
    }
    expected_frontend = set(gold_ids) | set(m2_ids) | set(w3_story_ids)
    if frontend_story_ids != expected_frontend:
        errors.append("SC1 Story set is not SC0 ∪ M2 ∪ W3")

    scenes = read(SCENE_PATH).get("records", [])
    scene_ids = [str(item.get("story_id")) for item in scenes]
    if set(scene_ids) != set(w3_story_ids):
        errors.append("W3 Scene Context coverage is not exactly the W3 Story wave")
    evidence_ids = {
        str(item.get("id"))
        for item in bundle.get("evidence", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    for record in scenes:
        if record.get("review_status") != "candidate":
            errors.append(f"W3 Scene Context is not candidate review status: {record.get('story_id')}")
        if record.get("relation_ids"):
            errors.append(f"W3 Scene Context creates Relation IDs: {record.get('story_id')}")
        if not record.get("narrative_layers", {}).get("scene_focus"):
            errors.append(f"W3 Story lacks a basic 舞台 audit: {record.get('story_id')}")
        for evidence_id in record.get("evidence_ids", []):
            if evidence_id not in evidence_ids:
                errors.append(f"W3 Scene Context Evidence does not resolve: {record.get('story_id')}/{evidence_id}")
        for layer in record.get("narrative_layers", {}).values():
            for claim in layer if isinstance(layer, list) else []:
                for evidence_id in claim.get("evidence_ids", []):
                    if evidence_id not in evidence_ids:
                        errors.append(f"W3 narrative Evidence does not resolve: {record.get('story_id')}/{evidence_id}")

    for story in bundle.get("stories", []):
        if story.get("id") in w3_story_ids:
            if not story.get("reading", {}).get("main_text", {}).get("original"):
                errors.append(f"W3 Story has no readable main text: {story.get('id')}")
            for person_id in story.get("person_ids", []):
                if person_id not in person_ids:
                    errors.append(f"W3 Story points to unknown production Person: {story.get('id')}/{person_id}")
            if story.get("period_id") and not story.get("period_label"):
                errors.append(f"W3 period ID has no reader label: {story.get('id')}")

    relations = read(RELATIONS_PATH).get("records", [])
    baseline_relations = _git_json(RELATIONS_PATH)
    if isinstance(baseline_relations, Mapping) and relations != baseline_relations.get("records", []):
        errors.append("W3 changed existing production Relation records")

    # I-HOTFIX: the ordinary lexical phrase must not become a Person link.
    effective = read(Path("data/derived/person-resolution-effective.json"))
    lexical_alias_mentions = [
        item for item in effective.get("mentions", [])
        if item.get("surface") == "少孤"
    ]
    dexing = [item for item in lexical_alias_mentions if item.get("entry_id") == "01-dexing-026"]
    if not dexing or any(item.get("person_id") == "person-032" for item in dexing):
        errors.append("01-dexing-026 少孤 is still projected to person-032")
    qiyi = [item for item in lexical_alias_mentions if item.get("entry_id") == "18-qiyi-010"]
    if not qiyi or any(item.get("person_id") != "person-032" for item in qiyi):
        errors.append("孟陋字少孤 identity evidence no longer resolves in its supported Story context")
    return sorted(set(errors))


if __name__ == "__main__":
    problems = validate()
    if problems:
        print("W3 validation failed:")
        print("\n".join(f"- {item}" for item in problems))
        raise SystemExit(1)
    print("W3 validation passed")
