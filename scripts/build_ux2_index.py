#!/usr/bin/env python3
"""Build the deterministic production Person/Story index projections.

UX2 is a reader-facing index over the already published SC1 projection.  It
does not read candidate queues or historical research layers and it does not
modify the initial SC1 bundle.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SC1_PATH = Path("data/derived/sc1-site.json")
DERIVED_ROOT = Path("data/derived")
PUBLIC_ROOT = Path("site/public/generated/ux2")
PERSON_DERIVED_PATH = DERIVED_ROOT / "ux2-person-index.json"
STORY_DERIVED_PATH = DERIVED_ROOT / "ux2-story-index.json"
PERSON_PUBLIC_PATH = PUBLIC_ROOT / "person-index.json"
STORY_PUBLIC_PATH = PUBLIC_ROOT / "story-index.json"
PUBLISHED_STATES = {"production_ready", "preview_ready"}


def read_json(root: Path, relative: Path) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_file(root: Path, relative: Path) -> str:
    digest = hashlib.sha256()
    with (root / relative).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pair(value: Any, fallback: Any = "") -> dict[str, str]:
    if isinstance(value, Mapping):
        original = str(value.get("original") or value.get("simplified") or "")
        simplified = str(value.get("simplified") or value.get("original") or "")
        return {"original": original, "simplified": simplified}
    text = str(value if value is not None else fallback)
    return {"original": text, "simplified": text}


def exposed_persons(sc1: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return the canonical Person rows the current SC1 reader exposes.

    The SC1 ``people`` array is the production frontend identity registry.
    Scope metadata is checked here so candidate/research-only rows cannot be
    accidentally added if the upstream projection grows another row type.
    """

    rows = [
        row for row in sc1.get("people", [])
        if isinstance(row, Mapping)
        and isinstance(row.get("id"), str)
        and row.get("scope_role") in {"primary", "supporting"}
        and row.get("scope") in {"primary", "supporting"}
    ]
    return sorted(rows, key=lambda row: (str(row["id"]), str(row.get("canonical_name", ""))))


def exposed_stories(sc1: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return the same reader-ready Story universe used by exploration."""

    rows = [
        row for row in sc1.get("stories", [])
        if isinstance(row, Mapping)
        and isinstance(row.get("id"), str)
        and row.get("publication_state") in PUBLISHED_STATES
        and row.get("title_source") != "candidate"
    ]
    return sorted(
        rows,
        key=lambda row: (
            int(row.get("global_ordinal")) if isinstance(row.get("global_ordinal"), int) else 10**9,
            str(row["id"]),
        ),
    )


def category_id(story_id: str) -> str:
    parts = story_id.split("-")
    return "-".join(parts[:2]) if len(parts) >= 2 else story_id


def category_number(story: Mapping[str, Any]) -> int:
    value = story.get("ordinal")
    if isinstance(value, int) and value > 0:
        return value
    story_id = str(story.get("id", ""))
    try:
        return int(story_id.rsplit("-", 1)[-1])
    except ValueError as error:
        raise ValueError(f"Story {story_id} has no deterministic category-local number") from error


def build_documents(root: Path = ROOT) -> dict[str, dict[str, Any]]:
    sc1 = read_json(root, SC1_PATH)
    source_hash = sha256_file(root, SC1_PATH)
    display = sc1.get("display", {})
    display_people = display.get("people", {}) if isinstance(display, Mapping) else {}

    people: list[dict[str, Any]] = []
    for person in exposed_persons(sc1):
        person_id = str(person["id"])
        person_display = display_people.get(person_id, {}) if isinstance(display_people, Mapping) else {}
        name = pair(person_display.get("name") if isinstance(person_display, Mapping) else None, person.get("canonical_name", person_id))
        surname = {
            "original": name["original"][:1],
            "simplified": name["simplified"][:1],
        }
        people.append({
            "person_id": person_id,
            "name": name,
            "surname": surname,
        })
    people.sort(key=lambda row: (row["surname"]["simplified"], row["name"]["simplified"], row["person_id"]))

    stories: list[dict[str, Any]] = []
    for story in exposed_stories(sc1):
        story_id = str(story["id"])
        number = category_number(story)
        label = pair(story.get("chapter_display"), story.get("chapter_heading") or story.get("title") or category_id(story_id))
        reference = {
            "original": f"{label['original']} · {number:03d}",
            "simplified": f"{label['simplified']} · {number:03d}",
        }
        stories.append({
            "story_id": story_id,
            "category_id": category_id(story_id),
            "category": label,
            "category_number": number,
            "reference": reference,
            "publication_state": str(story["publication_state"]),
        })
    stories.sort(key=lambda row: (row["category_id"], row["category_number"], row["story_id"]))

    common = {
        "schema": 1,
        "projection": "ux2_production_index",
        "source_bundle": {
            "path": SC1_PATH.as_posix(),
            "sha256": source_hash,
        },
        "scope": {
            "person_policy": "SC1 people with primary/supporting scope",
            "story_policy": "SC1 production_ready/preview_ready Stories",
        },
    }
    return {
        "people": {
            **common,
            "index_type": "person",
            "count": len(people),
            "records": people,
        },
        "stories": {
            **common,
            "index_type": "story",
            "count": len(stories),
            "records": stories,
        },
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(value), encoding="utf-8")


def build(root: Path = ROOT) -> dict[str, dict[str, Any]]:
    documents = build_documents(root)
    outputs = {
        "people": (PERSON_DERIVED_PATH, PERSON_PUBLIC_PATH),
        "stories": (STORY_DERIVED_PATH, STORY_PUBLIC_PATH),
    }
    for key, document in documents.items():
        derived, public = outputs[key]
        write_json(root / derived, document)
        write_json(root / public, document)
        if (root / derived).read_bytes() != (root / public).read_bytes():
            raise RuntimeError(f"UX2 derived/public projection mismatch: {derived} vs {public}")
    return documents


def main() -> int:
    documents = build(ROOT)
    print(json.dumps({key: value["count"] for key, value in documents.items()}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
