#!/usr/bin/env python3
"""Build and validate the small Story-owned Scene Card pilot projection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator
from opencc import OpenCC


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = Path("data/annotation/story-scene-contexts.json")
SCHEMA_PATH = Path("schema/story-scene-context.schema.json")
DERIVED_PATH = Path("data/derived/story-scene-contexts.json")
SC1_PATH = Path("data/derived/sc1-site.json")

ROLE_LABELS = {
    "present": ("在場", "在场"),
    "discussed": ("被討論", "被讨论"),
    "referenced_in_context": ("畫外", "画外"),
    "unknown": ("位置未詳", "位置未详"),
}

CLASSIFICATION_LABELS = {
    "formal_hierarchy": ("正式位階", "正式位阶"),
    "service_under": ("任職關係", "任职关系"),
    "court_relation": ("朝廷場景", "朝廷场景"),
    "peer": ("同儕場景", "同侪场景"),
    "same_office_context": ("同署場景", "同署场景"),
    "political_counterposition": ("政治對峙場景", "政治对峙场景"),
    "no_formal_hierarchy_established": ("未建立正式位階", "未建立正式位阶"),
    "unknown": ("位置未詳", "位置未详"),
}


def derive_age_range(
    story_start_year: int | None,
    story_end_year: int | None,
    birth_start_year: int | None,
    birth_end_year: int | None,
) -> dict[str, int | str | None]:
    """Derive a conservative age range without inventing precision.

    The pilot currently has no supported birth-year inputs, so its published
    cards remain unknown.  This helper makes the arithmetic explicit for a
    later evidence-backed record: the youngest possible age is the latest
    possible birth year subtracted from the earliest story year, and the
    oldest is the earliest birth year subtracted from the latest story year.
    """

    if not all(isinstance(value, int) for value in (story_start_year, story_end_year, birth_start_year, birth_end_year)):
        return {"status": "unknown", "start_year": None, "end_year": None}
    assert story_start_year is not None
    assert story_end_year is not None
    assert birth_start_year is not None
    assert birth_end_year is not None
    if story_start_year > story_end_year or birth_start_year > birth_end_year:
        raise ValueError("age derivation requires ordered date ranges")
    start = story_start_year - birth_end_year
    end = story_end_year - birth_start_year
    return {
        "status": "exact" if start == end else "range",
        "start_year": start,
        "end_year": end,
    }


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pair(value: str | None, converter: OpenCC) -> dict[str, str] | None:
    if value is None:
        return None
    return {"original": value, "simplified": converter.convert(value)}


def validate_source(root: Path = ROOT) -> list[str]:
    source = read_json(root / SOURCE_PATH)
    schema = read_json(root / SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    errors = [error.message for error in Draft202012Validator(schema).iter_errors(source)]

    def check_range(owner: str, value: Mapping[str, Any]) -> None:
        status = value.get("status")
        start = value.get("start_year")
        end = value.get("end_year")
        if status == "exact" and (not isinstance(start, int) or start != end):
            errors.append(f"{owner}: exact value requires equal start_year/end_year")
        if status == "range" and (not isinstance(start, int) or not isinstance(end, int) or start > end):
            errors.append(f"{owner}: range value requires ordered integer bounds")
        if status == "unknown" and (start is not None or end is not None):
            errors.append(f"{owner}: unknown value cannot carry year bounds")

    for record in source.get("records", []):
        story_id = record.get("story_id", "?")
        check_range(f"{story_id}.date", record["date"])
        for index, person in enumerate(record.get("people_at_scene", [])):
            check_range(f"{story_id}.people_at_scene[{index}].age", person["age"])
    return errors


def _all_evidence_ids(value: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()

    def visit(node: Any) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                if key == "evidence_ids" and isinstance(child, list):
                    ids.update(str(item) for item in child if isinstance(item, str))
                else:
                    visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return ids


def _claim_projection(claim: Mapping[str, Any], converter: OpenCC) -> dict[str, Any]:
    return {
        "text": pair(str(claim["text"]), converter),
        "assertion_status": claim["assertion_status"],
        "review_status": claim["review_status"],
        "evidence_ids": list(claim.get("evidence_ids", [])),
    }


def project(
    source: Mapping[str, Any],
    *,
    story_ids: set[str],
    people: list[Mapping[str, Any]],
    evidence_ids: set[str],
    converter: OpenCC | None = None,
) -> dict[str, Any]:
    converter = converter or OpenCC("t2s")
    people_by_id = {
        str(person.get("id")): person
        for person in people
        if isinstance(person, Mapping) and isinstance(person.get("id"), str)
    }
    records = source.get("records", [])
    contexts: dict[str, dict[str, Any]] = {}
    for record in records:
        story_id = str(record["story_id"])
        if story_id not in story_ids:
            raise ValueError(f"Scene Context references a non-published or unknown Story: {story_id}")
        if story_id in contexts:
            raise ValueError(f"duplicate Scene Context: {story_id}")

        record_evidence = _all_evidence_ids(record)
        missing = sorted(record_evidence - evidence_ids)
        if missing:
            raise ValueError(f"Scene Context {story_id} references missing Evidence: {', '.join(missing)}")

        date = record["date"]
        projected_people: list[dict[str, Any]] = []
        for person in record.get("people_at_scene", []):
            person_id = str(person["person_id"])
            if person_id not in people_by_id:
                raise ValueError(f"Scene Context {story_id} references unknown Person: {person_id}")
            role = str(person["scene_role"])
            status = person.get("status")
            projected_people.append(
                {
                    "person_id": person_id,
                    "surface": pair(str(person["surface"]), converter),
                    "scene_role": role,
                    "scene_role_label": pair(ROLE_LABELS[role][0], converter),
                    "source_layers": list(person["source_layers"]),
                    "age": {
                        "status": person["age"]["status"],
                        "label": pair(person["age"].get("label"), converter),
                        "start_year": person["age"].get("start_year"),
                        "end_year": person["age"].get("end_year"),
                        "assertion_status": person["age"]["assertion_status"],
                        "review_status": person["age"]["review_status"],
                        "evidence_ids": list(person["age"].get("evidence_ids", [])),
                    },
                    "status": _claim_projection(status, converter) if isinstance(status, Mapping) else None,
                    "assertion_status": person["assertion_status"],
                    "review_status": person["review_status"],
                    "evidence_ids": list(person.get("evidence_ids", [])),
                }
            )

        projected_unmaterialized = []
        for person in record.get("unmaterialized_people", []):
            role = str(person["scene_role"])
            projected_unmaterialized.append(
                {
                    "surface": pair(str(person["surface"]), converter),
                    "scene_role": role,
                    "scene_role_label": pair(ROLE_LABELS[role][0], converter),
                    "source_layers": list(person["source_layers"]),
                    "reason": pair(str(person["reason"]), converter),
                    "assertion_status": person["assertion_status"],
                    "review_status": person["review_status"],
                    "evidence_ids": list(person.get("evidence_ids", [])),
                }
            )

        projected_positions = []
        for position in record.get("positional_context", []):
            unknown_people = sorted(set(position["person_ids"]) - set(people_by_id))
            if unknown_people:
                raise ValueError(
                    f"Scene Context {story_id} positional context references unknown Person: {', '.join(unknown_people)}"
                )
            classification = str(position["classification"])
            projected_positions.append(
                {
                    "person_ids": list(position["person_ids"]),
                    "classification": classification,
                    "classification_label": pair(CLASSIFICATION_LABELS[classification][0], converter),
                    **_claim_projection(position, converter),
                }
            )

        narrative_source = record.get("narrative_layers", {})
        if not isinstance(narrative_source, Mapping):
            narrative_source = {}

        def claims_for(key: str, fallback: list[Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
            value = narrative_source.get(key)
            if not isinstance(value, list):
                value = fallback or []
            return [_claim_projection(claim, converter) for claim in value if isinstance(claim, Mapping)]

        narrative_layers = {
            "scene_focus": claims_for("scene_focus"),
            "off_frame_context": claims_for("off_frame_context"),
            "historical_ground": claims_for("historical_ground", record.get("event_background", [])),
            "resonance": claims_for("resonance"),
        }

        contexts[story_id] = {
            "story_id": story_id,
            "review_status": record["review_status"],
            "date": {
                "status": date["status"],
                "label": pair(date.get("label"), converter),
                "start_year": date.get("start_year"),
                "end_year": date.get("end_year"),
                "assertion_status": date["assertion_status"],
                "review_status": date["review_status"],
                "evidence_ids": list(date.get("evidence_ids", [])),
            },
            "places": [
                {
                    "name": pair(str(place["name"]), converter),
                    "assertion_status": place["assertion_status"],
                    "review_status": place["review_status"],
                    "evidence_ids": list(place.get("evidence_ids", [])),
                }
                for place in record.get("places", [])
            ],
            "people_at_scene": projected_people,
            "unmaterialized_people": projected_unmaterialized,
            "positional_context": projected_positions,
            "event_background": [_claim_projection(claim, converter) for claim in record["event_background"]],
            "narrative_layers": narrative_layers,
            "evidence_ids": list(record.get("evidence_ids", [])),
            "notes": [pair(str(note), converter) for note in record.get("notes", [])],
        }
    return {story_id: contexts[story_id] for story_id in sorted(contexts)}


def build(root: Path = ROOT) -> dict[str, Any]:
    source = read_json(root / SOURCE_PATH)
    errors = validate_source(root)
    if errors:
        raise ValueError("Story Scene Context schema validation failed: " + "; ".join(errors))
    bundle = read_json(root / SC1_PATH)
    story_ids = {
        str(story["id"])
        for story in bundle.get("stories", [])
        if isinstance(story, Mapping) and story.get("publication_state") != "blocked"
    }
    evidence_ids = {
        str(item["id"])
        for item in bundle.get("evidence", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    contexts = project(
        source,
        story_ids=story_ids,
        people=bundle.get("people", []),
        evidence_ids=evidence_ids,
    )
    expected = {str(record["story_id"]) for record in source.get("records", [])}
    if set(contexts) != expected:
        raise ValueError("derived Scene Context keys differ from curated source")
    result = {
        "schema": 1,
        "stage": "story-scene-context-pilot-derived",
        "generated_from": [str(SOURCE_PATH), str(SC1_PATH)],
        "contexts": contexts,
    }
    write_json(root / DERIVED_PATH, result)
    return result
