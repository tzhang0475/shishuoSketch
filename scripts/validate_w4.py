#!/usr/bin/env python3
"""Validate the W4 frozen expansion and its derived projections."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    story_wave = read(root / "data/annotation/story-expansion-wave-4.json")
    person_wave = read(root / "data/annotation/person-expansion-wave-4.json")
    story_ids = [str(item["story_id"]) for item in story_wave.get("records", []) if isinstance(item, Mapping)]
    person_members = [item for item in person_wave.get("members", []) if isinstance(item, Mapping)]
    if story_wave.get("selection_status") != "frozen":
        errors.append("W4 Story selection is not frozen")
    if len(story_ids) != len(set(story_ids)):
        errors.append("W4 Story selection contains duplicate IDs")
    gold = {str(item["entry_id"]) for item in read(root / "data/story-chain-gold-set.json").get("records", []) if isinstance(item, Mapping)}
    previous = {
        str(item["story_id"])
        for path in ("data/annotation/story-expansion-wave-1.json", "data/annotation/story-expansion-wave-3.json")
        for item in read(root / path).get("records", [])
        if isinstance(item, Mapping)
    }
    corpus = {str(item["id"]): item for item in read(root / "data/shishuo-corpus-index.json").get("entries", []) if isinstance(item, Mapping)}
    punctuation = {str(item["entry_id"]): item for item in read(root / "data/annotation/wp1-punctuation.json").get("records", []) if isinstance(item, Mapping)}
    story_records = {
        str(item.get("story_id")): item
        for item in story_wave.get("records", [])
        if isinstance(item, Mapping) and isinstance(item.get("story_id"), str)
    }
    for story_id in story_ids:
        if story_id not in corpus:
            errors.append(f"W4 Story is not canonical: {story_id}")
        if story_id in gold or story_id in previous:
            errors.append(f"W4 Story duplicates an earlier publication: {story_id}")
        if story_id not in punctuation:
            errors.append(f"W4 Story has no punctuation record: {story_id}")
        if not isinstance(story_records.get(story_id, {}).get("canonical_entry_sha256"), str):
            errors.append(f"W4 Story lacks canonical source hash: {story_id}")

    person_ids = [str(item.get("person_id")) for item in person_members]
    if len(person_ids) != len(set(person_ids)):
        errors.append("W4 Person selection contains duplicate IDs")
    if any(int(value.split("-")[-1]) <= 50 for value in person_ids):
        errors.append("W4 allocated a Person ID inside the frozen 001-050 range")
    allocation = read(root / "data/derived/person-id-allocation-state.json").get("allocations", [])
    allocation_ids = {str(item.get("person_id")) for item in allocation if isinstance(item, Mapping)}
    for person_id in person_ids:
        if person_id not in allocation_ids:
            errors.append(f"W4 Person missing allocation state: {person_id}")
    people = read(root / "data/people.json").get("people", [])
    registry_ids = {str(item.get("person_id")) for item in people if isinstance(item, Mapping)}
    if not set(person_ids) <= registry_ids:
        errors.append("W4 Person selection is not materialized in the registry")
    if len(registry_ids) != len(people):
        errors.append("Person registry has duplicate IDs")
    names = [str(item.get("canonical_name")) for item in people if isinstance(item, Mapping)]
    if len(names) != len(set(names)):
        errors.append("Person registry has duplicate canonical names")

    bundle = read(root / "data/derived/sc1-site.json")
    bundle_stories = {str(item.get("id")): item for item in bundle.get("stories", []) if isinstance(item, Mapping)}
    if not set(story_ids) <= set(bundle_stories):
        errors.append("SC1 bundle is missing a selected W4 Story")
    anchors = {str(item.get("story_id")): item for item in read(root / "data/annotation/story-temporal-anchors-h0a.json").get("records", []) if isinstance(item, Mapping)}
    orientations = {str(item.get("story_id")): item for item in read(root / "data/derived/e0-story-era-orientations.json").get("records", []) if isinstance(item, Mapping)}
    for story_id in story_ids:
        if story_id not in anchors:
            errors.append(f"W4 Story has no H0A StoryTemporalAnchor: {story_id}")
        if story_id not in orientations:
            errors.append(f"W4 Story has no E0.1 orientation: {story_id}")
        if story_id in bundle_stories and not bundle_stories[story_id].get("primary_era_card_id"):
            errors.append(f"W4 Story has no primary Era orientation: {story_id}")

    identity = read(root / "data/derived/w4-identity-coverage.json")
    if identity.get("counts", {}).get("unexpected_safe_omission", 0) != 0:
        errors.append("W4 identity coverage has unexpected safe omissions")
    if set(identity.get("scope", {}).get("story_ids", [])) != set(story_ids):
        errors.append("W4 identity coverage scope does not match frozen Stories")
    temporal = read(root / "data/derived/w4-social-temporal-constraints.json")
    if set(item.get("story_id") for item in temporal.get("records", []) if isinstance(item, Mapping)) != set(story_ids):
        errors.append("W4 social-temporal constraint scope does not match frozen Stories")

    links = read(root / "data/derived/person-story-links.json")
    if links.get("link_count", 0) < links.get("reviewed_link_count", 0):
        errors.append("PersonStory link count is below reviewed count")
    reviewed_relations = [item for item in read(root / "data/annotation/wp1-relations.json").get("records", []) if isinstance(item, Mapping) and item.get("review_status") == "reviewed"]
    if len(reviewed_relations) != 12:
        errors.append(f"W4 changed the reviewed Relation count: {len(reviewed_relations)}")
    metrics = read(root / "data/derived/w4-metrics.json")
    if metrics.get("protected", {}).get("orphan_mentions") != 0:
        errors.append("W4 metrics report orphan Mentions")
    if metrics.get("protected", {}).get("era_orientation_coverage") != len(bundle_stories):
        errors.append("W4 Era orientation coverage is not complete")

    # Identity regressions remain checked from the effective resolution layer.
    effective_document = read(root / "data/derived/person-resolution-effective.json")
    effective = [
        *effective_document.get("mentions", []),
        *effective_document.get("derived_mentions", []),
    ]
    def rows(story: str, surface: str) -> list[Mapping[str, Any]]:
        return [item for item in effective if isinstance(item, Mapping) and (item.get("entry_id") or item.get("source_id")) == story and item.get("surface") == surface]
    if any(item.get("person_id") == "person-037" for item in rows("23-rendan-013", "仲容")):
        errors.append("仲容 regression: 23-rendan-013 resolves to 石苞")
    if any(item.get("person_id") == "person-032" for item in rows("01-dexing-026", "少孤")):
        errors.append("少孤 regression: 01-dexing-026 resolves to 孟陋")
    if not any(item.get("person_id") == "person-010" for item in rows("14-rongzhi-024", "庾太尉")):
        errors.append("14-rongzhi-024 庾太尉 no longer resolves to 庾亮")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print("ERROR:", error)
        return 1
    print("W4 validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
