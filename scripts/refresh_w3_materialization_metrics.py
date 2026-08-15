#!/usr/bin/env python3
"""Refresh W3 materialization metrics against the current SC1 bundle.

Person materialization intentionally runs before the Story publication
projection.  This small deterministic post-build step keeps the frozen W3
audit report's SC1 story/occurrence columns tied to the final frontend set;
it does not change identity membership or promote any Mention.
"""

from __future__ import annotations

import json
from pathlib import Path

try:
    from . import materialize_person_expansion as materializer
    from . import materialize_w3_person_expansion as w3
except ImportError:  # direct execution
    import materialize_person_expansion as materializer
    import materialize_w3_person_expansion as w3


ROOT = Path(__file__).resolve().parents[1]
MATERIALIZATION_PATH = ROOT / w3.MATERIALIZATION_PATH
WAVE_PATH = ROOT / w3.WAVE_PATH
SC1_PATH = ROOT / "data/derived/sc1-site.json"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


REPORT_SUFFIX = """
## C1 reading integration and provenance boundary

The frozen W3 projection currently adds 15 Persons and 23 evidence-safe
Stories to the existing 35-Person / 60-Story experience. Each added Story has
a build-time punctuation and Mention projection and a candidate Scene Context;
the Scene layer remains separate from PersonStory and Relation semantics.
The 23 basic scene records include 舞台、入画、画外 where the source supports
them; eight high-value records also carry richer 底色 / 余韵 claims. Ten W3
Persons receive compact candidate 一瞥 coordinates with evidence references.

One initially selected Story, `18-qiyi-002`, is deliberately withheld from the
published wave because its available local witness is the unregistered
`shishuo-wikisource-sbck` supplemental payload. No raw payload was added and
the evidence was not rewritten to appear as the registered WYG witness. This
is an evidence-safety reduction, not a quota failure. SGZ0 remains a separate
30-volume local processing layer; it does not create W3 Persons, Relations, or
an H0 chronology.
""".strip()


def build() -> None:
    w3.configure()
    materialization = read(MATERIALIZATION_PATH)
    wave = read(WAVE_PATH)
    bundle = read(SC1_PATH)
    w3_ids = {str(item.get("person_id")) for item in materialization.get("members", [])}
    story_ids_by_person: dict[str, set[str]] = {person_id: set() for person_id in w3_ids}
    occurrence_count_by_person: dict[str, int] = {person_id: 0 for person_id in w3_ids}
    for story in bundle.get("stories", []):
        if story.get("publication_state") not in {"production_ready", "preview_ready"}:
            continue
        story_id = str(story.get("id"))
        for person_id in story.get("person_ids", []):
            person_id = str(person_id)
            if person_id in story_ids_by_person:
                story_ids_by_person[person_id].add(story_id)
    for mention in bundle.get("mentions", []):
        person_id = str(mention.get("person_id"))
        if person_id in occurrence_count_by_person:
            occurrence_count_by_person[person_id] += 1
    members_by_person = {
        str(item.get("person_id")): item
        for item in materialization.get("members", [])
    }
    for person_id, member in members_by_person.items():
        member["current_sc1_story_ids"] = sorted(story_ids_by_person[person_id])
        member["current_sc1_occurrence_count"] = occurrence_count_by_person[person_id]
    materialization["members"] = [
        members_by_person[str(item.get("person_id"))]
        for item in materialization.get("members", [])
    ]
    report_wave = dict(wave)
    wave_members_by_person = {
        str(item.get("person_id")): item
        for item in wave.get("members", [])
    }
    for person_id, member in members_by_person.items():
        if person_id in wave_members_by_person:
            wave_members_by_person[person_id]["current_sc1_story_ids"] = list(member["current_sc1_story_ids"])
            wave_members_by_person[person_id]["current_sc1_occurrence_count"] = member["current_sc1_occurrence_count"]
    report_wave["members"] = [
        wave_members_by_person[str(item.get("person_id"))]
        for item in wave.get("members", [])
    ]
    write(MATERIALIZATION_PATH, materialization)
    report = materializer._render_report(
        report_wave,
        materialization,
        int(materialization["people_before"]),
        int(materialization["people_after"]),
    )
    (ROOT / w3.REPORT_PATH).write_text(report.rstrip() + "\n\n" + REPORT_SUFFIX + "\n", encoding="utf-8")
    print(
        f"refreshed W3 SC1 metrics: {sum(bool(item['current_sc1_story_ids']) for item in materialization['members'])} Persons with published Story paths"
    )


if __name__ == "__main__":
    build()
