#!/usr/bin/env python3
"""Query the local DS2.1A Person research surface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

try:
    from .build_ds2_1a_person_research import OUTPUT_PATH, PRIORITY_ORDER, ROOT
except ImportError:  # direct execution: python scripts/query_person_research.py
    from build_ds2_1a_person_research import OUTPUT_PATH, PRIORITY_ORDER, ROOT


def research_priority_key(row: dict[str, Any]) -> tuple[int, str, int, str]:
    priority = PRIORITY_ORDER.get(str(row.get("research_priority_class")), 99)
    ordinal = row.get("story_ordinal")
    ordinal_value = ordinal if isinstance(ordinal, int) else 10**9
    return (priority, str(row.get("chapter_id", "")), ordinal_value, str(row.get("story_id", "")))


def query_document(document: dict[str, Any], person_id: str, story_id: str) -> dict[str, Any]:
    person = document.get("people", {}).get(person_id)
    if not isinstance(person, dict):
        raise ValueError(f"unknown exposed Person: {person_id}")
    related = [
        dict(row, current_story=str(row.get("story_id")) == story_id)
        for row in person.get("shishuo_stories", [])
        if isinstance(row, dict)
    ]
    related.sort(key=research_priority_key)
    current = next((row for row in related if row.get("current_story")), None)
    if current is None:
        raise ValueError(f"Story {story_id} is not an existing Shishuo link for {person_id}")
    return {
        "current_story": current,
        "person": {
            "person_id": person["person_id"],
            "canonical_name": person["canonical_name"],
            "story_count_total": person.get("story_count_total", len(related)),
            "story_count_published": person.get("story_count_published", 0),
            "story_count_research_only": person.get("story_count_research_only", 0),
            "main_text_story_count": person.get("main_text_story_count", 0),
            "liu_annotation_only_story_count": person.get("liu_annotation_only_story_count", 0),
            "both_layer_story_count": person.get("both_layer_story_count", 0),
            "reviewed_link_count": person.get("reviewed_link_count", 0),
            "candidate_link_count": person.get("candidate_link_count", 0),
        },
        "related_shishuo": related,
        "biography_entries": person.get("historical_biography_entries", []),
        "reviewed_context": person.get("reviewed_context", {}),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--person", required=True)
    parser.add_argument("--story", required=True)
    parser.add_argument("--surface", type=Path, default=ROOT / OUTPUT_PATH)
    args = parser.parse_args(argv)
    try:
        document = json.loads(args.surface.read_text(encoding="utf-8"))
        result = query_document(document, args.person, args.story)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
