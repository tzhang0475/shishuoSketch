#!/usr/bin/env python3
"""Run the generic Person expansion materializer for a frozen M2 wave.

The historical Wave-1 command remains available and byte-compatible.  This
entry point supplies only the Wave-2 data configuration, so future waves are
data changes rather than copies of the six-person pilot.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from . import materialize_person_expansion as materializer
except ImportError:  # direct execution
    import materialize_person_expansion as materializer


ROOT = Path(__file__).resolve().parents[1]
WAVE_PATH = Path("data/annotation/person-expansion-wave-2.json")
RANKING_PATH = Path("data/derived/m2-person-expansion-ranking.json")
MATERIALIZATION_PATH = Path("data/derived/person-expansion-wave-2-materialization.json")
REPORT_PATH = Path("docs/person-expansion-wave-2.md")
ALLOCATION_PATH = Path("data/derived/person-id-allocation-state.json")
SOURCE_REGISTRY_PATH = Path("data/sources/wp1-sources.json")
OCCURRENCES_PATH = Path("data/derived/person-candidate-occurrences.json")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def configure() -> None:
    materializer.WAVE_PATH = WAVE_PATH
    materializer.RANKING_PATH = RANKING_PATH
    # The M2 ranking is already the frozen source artifact.  Keeping the
    # snapshot path equal to it makes the hash authority explicit without
    # creating a second mutable copy.
    materializer.RANKING_SNAPSHOT_PATH = RANKING_PATH
    materializer.MATERIALIZATION_PATH = MATERIALIZATION_PATH
    materializer.REPORT_PATH = REPORT_PATH
    materializer.WAVE_ID = "p3b-wave-2"
    materializer.WAVE_LABEL = "M2A Wave 2"
    materializer.MATERIALIZATION_STAGE = "m2a-person-expansion-wave-2-materialization"
    materializer.EXPECTED_WAVE_SIZE = 18
    materializer.EVIDENCE_PREFIX = "evidence-p3b-wave-2-"
    materializer.MENTION_PREFIX = "shishuo-p3b-wave-2-"
    materializer.ALIAS_PREFIX = "alias-p3b-wave-2-"


def update_allocation_state(root: Path = ROOT) -> dict[str, Any]:
    state_path = root / ALLOCATION_PATH
    state = read_json(state_path)
    wave = read_json(root / WAVE_PATH)
    by_id = {str(item["person_id"]): dict(item) for item in state.get("allocations", [])}
    for member in sorted(wave.get("members", []), key=lambda item: int(item["rank_at_selection"])):
        person_id = str(member["person_id"])
        record = {
            "person_id": person_id,
            "canonical_name": str(member["preferred_name"]),
            "allocation_basis": "m2a_wave_2_rank_order",
            "source_wave_id": str(wave["wave_id"]),
        }
        if person_id in by_id and by_id[person_id] != record:
            raise ValueError(f"Person ID allocation drift for {person_id}")
        by_id[person_id] = record
    allocations = sorted(by_id.values(), key=lambda item: item["person_id"])
    expected_ids = [f"person-{index:03d}" for index in range(1, len(allocations) + 1)]
    if [item["person_id"] for item in allocations] != expected_ids:
        raise ValueError("production Person ID allocation has a gap or duplicate")
    state["allocations"] = allocations
    state["next_person_sequence"] = len(allocations) + 1
    state["notes"] = [
        "Opaque Person IDs are assigned once and never generated from names or display text.",
        "This state artifact is updated only by an explicit materialization wave.",
    ]
    write_json(state_path, state)
    return state


def _span(mention: dict[str, Any]) -> tuple[str, str, int, int] | None:
    offset = mention.get("evidence", {}).get("section_offset")
    surface = mention.get("surface")
    if not isinstance(offset, int) or not isinstance(surface, str):
        return None
    return (
        str(mention.get("entry_id") or mention.get("source_id")),
        str(mention.get("section")),
        offset,
        offset + len(surface),
    )


def _overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    a = _span(left)
    b = _span(right)
    return bool(a and b and a[:2] == b[:2] and a[2] < b[3] and b[2] < a[3])


def repair_wave2_overlaps(root: Path = ROOT) -> list[str]:
    """Remove unsafe Wave-2 overlaps after an idempotent rebuild.

    This is a migration guard for the first generic-wave run.  Candidate
    occurrences at incompatible ranges are withheld rather than choosing a
    Person by rank.  Existing non-Wave-2 Mentions are never removed.
    """

    mentions_path = root / materializer.MENTIONS_PATH
    document = read_json(mentions_path)
    mentions = [dict(item) for item in document.get("mentions", [])]
    wave_mentions = [
        item for item in mentions
        if item.get("materialization", {}).get("wave_id") == "p3b-wave-2"
    ]
    by_location: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in wave_mentions:
        span = _span(item)
        if span:
            by_location.setdefault(span[:2], []).append(item)

    conflict_ids: set[str] = set()
    for rows in by_location.values():
        for index, left in enumerate(rows):
            for right in rows[index + 1 :]:
                if left.get("person_id") != right.get("person_id") and _overlap(left, right):
                    conflict_ids.update({str(left["mention_id"]), str(right["mention_id"])})

    existing_by_location: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in mentions:
        if item in wave_mentions:
            continue
        span = _span(item)
        if span:
            existing_by_location.setdefault(span[:2], []).append(item)

    removed: list[dict[str, Any]] = []
    for location, rows in by_location.items():
        accepted = list(existing_by_location.get(location, []))
        candidates = sorted(
            [item for item in rows if str(item["mention_id"]) not in conflict_ids],
            key=lambda item: (
                int(item["evidence"]["section_offset"]),
                -len(str(item.get("surface", ""))),
                str(item["mention_id"]),
            ),
        )
        for item in candidates:
            if any(_overlap(item, prior) for prior in accepted):
                removed.append({
                    "mention": item,
                    "reason": "overlapping_existing_or_nested_wave2_mention",
                })
            else:
                accepted.append(item)
    for item in wave_mentions:
        if str(item["mention_id"]) in conflict_ids:
            removed.append({
                "mention": item,
                "reason": "incompatible_overlapping_wave2_candidate_ranges",
            })

    removed_ids = {str(item["mention"]["mention_id"]) for item in removed}
    if not removed_ids:
        return []
    document["mentions"] = [item for item in mentions if str(item.get("mention_id")) not in removed_ids]
    document["mention_count"] = len(document["mentions"])
    document["mentions"].sort(key=lambda item: (
        str(item.get("entry_id") or item.get("source_id")),
        0 if item.get("section") == "main_text" else 1,
        int(item.get("evidence", {}).get("section_offset", 10**9)),
        str(item.get("mention_id")),
    ))
    write_json(mentions_path, document)

    removed_by_occurrence = {
        str(item["mention"].get("materialization", {}).get("candidate_occurrence_id")): item
        for item in removed
    }
    materialization_path = root / MATERIALIZATION_PATH
    materialization = read_json(materialization_path)
    wave_path = root / WAVE_PATH
    wave = read_json(wave_path)
    for owner in (materialization, wave):
        for member in owner.get("members", []):
            retained_mentions = [
                str(item) for item in member.get("promoted_mention_ids", [])
                if str(item) not in removed_ids
            ]
            retained_occurrences = [
                str(item) for item in member.get("promoted_occurrence_ids", [])
                if str(item) not in removed_by_occurrence
            ]
            member["promoted_mention_ids"] = retained_mentions
            member["promoted_occurrence_ids"] = retained_occurrences
            member["promoted_occurrence_count"] = len(retained_occurrences)
            withheld = list(member.get("withheld_occurrences", []))
            for occurrence_id, removed_item in removed_by_occurrence.items():
                mention = removed_item["mention"]
                if mention.get("materialization", {}).get("candidate_id") != member.get("candidate_id"):
                    continue
                if any(str(item.get("occurrence_id")) == occurrence_id for item in withheld):
                    continue
                withheld.append({
                    "occurrence_id": occurrence_id,
                    "source_id": mention.get("entry_id") or mention.get("source_id"),
                    "section": mention.get("section"),
                    "surface": mention.get("surface"),
                    "association_mode": "exact",
                    "confidence": mention.get("confidence"),
                    "reason": removed_item["reason"],
                    "evidence_ids": list(mention.get("evidence", {}).get("evidence_ids", [])),
                })
            member["withheld_occurrences"] = sorted(withheld, key=lambda item: str(item.get("occurrence_id")))
            member["withheld_occurrence_count"] = len(member["withheld_occurrences"])
    materialization["promoted_mention_count"] = sum(
        len(member.get("promoted_mention_ids", [])) for member in materialization.get("members", [])
    )
    materialization["withheld_occurrence_count"] = sum(
        int(member.get("withheld_occurrence_count", 0)) for member in materialization.get("members", [])
    )
    write_json(materialization_path, materialization)
    write_json(wave_path, wave)
    return sorted(removed_ids)


def _production_evidence_safety(root: Path) -> tuple[set[str], dict[str, str]]:
    """Return Wave-2 evidence IDs safe for the registered production sources.

    P3A.1 deliberately retains repaired-entry evidence from supplemental
    witnesses.  The production WP1 evidence registry, however, has one
    canonical source identity per work.  A candidate occurrence is not
    promoted when its witness disagrees with that registered identity.  This
    keeps the portable/full provenance validator strict while preserving the
    discovery evidence in P3A.1.
    """

    sources = read_json(root / SOURCE_REGISTRY_PATH).get("records", [])
    witness_by_source = {
        str(item.get("id")): str(item.get("witness_id"))
        for item in sources
        if isinstance(item, dict) and item.get("id") and item.get("witness_id")
    }
    evidence_document = read_json(root / materializer.EVIDENCE_PATH)
    unsafe: set[str] = set()
    reason_by_id: dict[str, str] = {}
    for record in evidence_document.get("records", []):
        evidence_id = str(record.get("id", ""))
        if not evidence_id.startswith("evidence-p3b-wave-2-"):
            continue
        source_id = str(record.get("source_id", ""))
        expected_witness = witness_by_source.get(source_id)
        actual_witness = str(
            record.get("locator", {})
            .get("source_provenance", {})
            .get("witness_id", "")
        )
        if not expected_witness or actual_witness != expected_witness:
            unsafe.add(evidence_id)
            reason_by_id[evidence_id] = "source_provenance_not_registered_for_production"
    return unsafe, reason_by_id


def sanitize_wave2_provenance(root: Path = ROOT) -> list[str]:
    """Withhold Wave-2 projections whose source witness is not registered.

    This is intentionally a production-projection boundary, not a rewrite of
    P3A.1 discovery data.  Candidate Evidence and candidate occurrences remain
    available in their derived artifacts; only production Evidence, Alias,
    Mention, and PersonStory projections are filtered.
    """

    unsafe_ids, reason_by_evidence = _production_evidence_safety(root)
    if not unsafe_ids:
        return []

    evidence_path = root / materializer.EVIDENCE_PATH
    evidence_document = read_json(evidence_path)
    evidence_document["records"] = [
        record
        for record in evidence_document.get("records", [])
        if str(record.get("id")) not in unsafe_ids
    ]
    evidence_document["records"].sort(key=lambda item: str(item.get("id")))
    write_json(evidence_path, evidence_document)

    aliases_path = root / materializer.ALIASES_PATH
    aliases_document = read_json(aliases_path)
    for alias in aliases_document.get("aliases", []):
        if not isinstance(alias, dict):
            continue
        if not str(alias.get("alias_id", "")).startswith("alias-p3b-wave-2-"):
            continue
        alias["source_evidence"] = [
            item
            for item in alias.get("source_evidence", [])
            if str(item.get("evidence_id")) not in unsafe_ids
        ]
    write_json(aliases_path, aliases_document)

    people_path = root / materializer.PEOPLE_PATH
    people_document = read_json(people_path)
    for person in people_document.get("people", []):
        if not isinstance(person, dict):
            continue
        if person.get("materialization", {}).get("wave_id") != "p3b-wave-2":
            continue
        person["source_evidence"] = [
            item
            for item in person.get("source_evidence", [])
            if str(item.get("evidence_id")) not in unsafe_ids
        ]
        materialization = person.get("materialization", {})
        materialization["identity_evidence_ids"] = [
            str(item)
            for item in materialization.get("identity_evidence_ids", [])
            if str(item) not in unsafe_ids
        ]
    write_json(people_path, people_document)

    occurrences = {
        str(item.get("occurrence_id")): item
        for item in read_json(root / OCCURRENCES_PATH).get("occurrences", [])
        if isinstance(item, dict) and item.get("occurrence_id")
    }
    mentions_path = root / materializer.MENTIONS_PATH
    mentions_document = read_json(mentions_path)
    removed: list[dict[str, Any]] = []
    retained_mentions: list[dict[str, Any]] = []
    for mention in mentions_document.get("mentions", []):
        materialization = mention.get("materialization", {})
        evidence_ids = {
            str(item)
            for item in mention.get("evidence", {}).get("evidence_ids", [])
        }
        if (
            materialization.get("wave_id") == "p3b-wave-2"
            and evidence_ids & unsafe_ids
        ):
            removed.append({
                "mention": mention,
                "occurrence": occurrences.get(str(materialization.get("candidate_occurrence_id")), {}),
                "reason": "source_provenance_not_registered_for_production",
            })
        else:
            retained_mentions.append(mention)
    mentions_document["mentions"] = retained_mentions
    mentions_document["mention_count"] = len(retained_mentions)
    write_json(mentions_path, mentions_document)

    materialization_path = root / MATERIALIZATION_PATH
    materialization = read_json(materialization_path)
    wave_path = root / WAVE_PATH
    wave = read_json(wave_path)
    removed_occurrence_ids = {
        str(item["mention"].get("materialization", {}).get("candidate_occurrence_id"))
        for item in removed
    }
    for owner in (materialization, wave):
        for member in owner.get("members", []):
            member["promoted_mention_ids"] = [
                str(item)
                for item in member.get("promoted_mention_ids", [])
                if str(item) not in {str(row["mention"].get("mention_id")) for row in removed}
            ]
            member["promoted_occurrence_ids"] = [
                str(item)
                for item in member.get("promoted_occurrence_ids", [])
                if str(item) not in removed_occurrence_ids
            ]
            member["promoted_occurrence_count"] = len(member["promoted_occurrence_ids"])
            member["production_identity_evidence_ids"] = [
                str(item)
                for item in member.get("production_identity_evidence_ids", [])
                if str(item) not in unsafe_ids
            ]
            withheld = list(member.get("withheld_occurrences", []))
            for row in removed:
                mention = row["mention"]
                occurrence = row["occurrence"]
                candidate_id = mention.get("materialization", {}).get("candidate_id")
                if candidate_id != member.get("candidate_id"):
                    continue
                occurrence_id = str(mention.get("materialization", {}).get("candidate_occurrence_id"))
                if any(str(item.get("occurrence_id")) == occurrence_id for item in withheld):
                    continue
                withheld.append({
                    "occurrence_id": occurrence_id,
                    "source_id": occurrence.get("source_id") or mention.get("entry_id"),
                    "section": occurrence.get("section") or mention.get("section"),
                    "surface": occurrence.get("surface") or mention.get("surface"),
                    "association_mode": occurrence.get("association_mode", "exact"),
                    "confidence": occurrence.get("confidence", mention.get("confidence")),
                    "reason": row["reason"],
                    "evidence_ids": [
                        str(item)
                        for item in mention.get("evidence", {}).get("evidence_ids", [])
                        if str(item) not in unsafe_ids
                    ],
                })
            member["withheld_occurrences"] = sorted(
                withheld, key=lambda item: str(item.get("occurrence_id"))
            )
            member["withheld_occurrence_count"] = len(member["withheld_occurrences"])
    materialization["promoted_mention_count"] = sum(
        len(member.get("promoted_mention_ids", []))
        for member in materialization.get("members", [])
    )
    materialization["withheld_occurrence_count"] = sum(
        int(member.get("withheld_occurrence_count", 0))
        for member in materialization.get("members", [])
    )
    materialization["production_evidence_ids"] = [
        str(item)
        for item in materialization.get("production_evidence_ids", [])
        if str(item) not in unsafe_ids
    ]
    write_json(materialization_path, materialization)
    wave["members"] = materialization["members"]
    write_json(wave_path, wave)

    return sorted(unsafe_ids)


def _repeated_units(surface: str) -> list[str]:
    """Return repeated units only when the surface is exact concatenation."""

    for repeat_count in range(2, len(surface) + 1):
        if len(surface) % repeat_count:
            continue
        unit_length = len(surface) // repeat_count
        unit = surface[:unit_length]
        if unit_length > 1 and surface == unit * repeat_count:
            return [unit] * repeat_count
    return []


def repair_repeated_alias_occurrences(root: Path = ROOT) -> list[str]:
    """Repair stale Wave-2 audit rows created by an adjacent-alias merge.

    Wave-2 had already been materialized when P3A.1 was corrected, so its
    candidate-occurrence artifact intentionally no longer contained rows for
    already-materialized Persons.  Rebuild the stale withheld row from the
    refreshed P3A.1 Evidence locators instead of dropping the two source
    occurrences or inventing a production Mention.
    """

    candidates_document = read_json(root / "data/derived/person-identity-candidates.json")
    candidates = {
        str(item.get("candidate_id")): item
        for item in candidates_document.get("candidates", [])
        if isinstance(item, dict) and item.get("candidate_id")
    }
    candidate_evidence = {
        str(item.get("id")): item
        for item in candidates_document.get("evidence", [])
        if isinstance(item, dict) and item.get("id")
    }
    materialization_path = root / MATERIALIZATION_PATH
    wave_path = root / WAVE_PATH
    materialization = read_json(materialization_path)
    wave = read_json(wave_path)
    replacements: list[str] = []

    for owner in (materialization, wave):
        for member in owner.get("members", []):
            candidate_id = str(member.get("candidate_id"))
            candidate = candidates.get(candidate_id)
            if candidate is None:
                continue
            retained: list[dict[str, Any]] = []
            for row in member.get("withheld_occurrences", []):
                surface = str(row.get("surface", ""))
                units = _repeated_units(surface)
                if not units:
                    retained.append(row)
                    continue

                unit_rows: list[dict[str, Any]] = []
                used_unit_evidence: dict[str, int] = {}
                for unit in units:
                    matches = []
                    for evidence_id in candidate.get("evidence_ids", []):
                        evidence = candidate_evidence.get(str(evidence_id))
                        locator = evidence.get("locator", {}) if isinstance(evidence, dict) else {}
                        if (
                            isinstance(evidence, dict)
                            and evidence.get("source_id") == row.get("source_id")
                            and evidence.get("section") == row.get("section")
                            and evidence.get("surface") == unit
                            and isinstance(locator.get("section_offset"), int)
                        ):
                            matches.append((str(evidence_id), evidence, locator))
                    matches.sort(
                        key=lambda item: (
                            int(item[2]["section_offset"]),
                            item[0],
                        )
                    )
                    match_index = used_unit_evidence.get(unit, 0)
                    if match_index >= len(matches):
                        raise ValueError(
                            "repeated alias cannot be repaired deterministically: "
                            f"{candidate_id}/{row.get('source_id')}/{surface}/{unit}"
                        )
                    used_unit_evidence[unit] = match_index + 1
                    source_evidence_id, evidence, locator = matches[match_index]
                    offset = int(locator["section_offset"])
                    occurrence_id = (
                        "occurrence-p3a1-"
                        + materializer.stable_hash(
                            candidate_id,
                            row.get("source_id"),
                            row.get("section"),
                            unit,
                            offset,
                        )[:20]
                    )
                    unit_rows.append(
                        {
                            "occurrence_id": occurrence_id,
                            "source_id": row.get("source_id"),
                            "section": row.get("section"),
                            "surface": unit,
                            "offset": offset,
                            "association_mode": "contextual",
                            "confidence": "candidate",
                            "reason": "contextual_association",
                            "evidence_ids": [
                                materializer.production_evidence_id(source_evidence_id)
                            ],
                        }
                    )
                retained.extend(sorted(unit_rows, key=lambda item: (item["offset"], item["occurrence_id"])))
                replacements.append(
                    f"{row.get('source_id')}:{surface} -> "
                    + ",".join(item["occurrence_id"] for item in unit_rows)
                )
            member["withheld_occurrences"] = sorted(
                retained,
                key=lambda item: (
                    str(item.get("source_id")),
                    str(item.get("section")),
                    int(item.get("offset", 10**9)) if isinstance(item.get("offset"), int) else 10**9,
                    str(item.get("occurrence_id")),
                ),
            )
            member["withheld_occurrence_count"] = len(member["withheld_occurrences"])

    materialization["withheld_occurrence_count"] = sum(
        int(member.get("withheld_occurrence_count", 0))
        for member in materialization.get("members", [])
    )
    valid_wave_evidence_ids = {
        materializer.production_evidence_id(str(evidence_id))
        for evidence_id in materializer._wave_source_evidence_ids(
            candidates,
            wave.get("members", []),
        )
        if str(evidence_id) in candidate_evidence
    }
    materialization["production_evidence_ids"] = sorted(valid_wave_evidence_ids)
    wave["members"] = materialization["members"]
    write_json(materialization_path, materialization)
    write_json(wave_path, wave)
    return replacements


def build(root: Path = ROOT) -> dict[str, Any]:
    configure()
    materialization = materializer.build(root)
    repair_wave2_overlaps(root)
    repair_repeated_alias_occurrences(root)
    sanitize_wave2_provenance(root)
    update_allocation_state(root)
    try:
        from . import person_resolution
    except ImportError:  # direct execution
        import person_resolution
    # Build the ER1 overlay after materialization has settled the canonical
    # Mention registry and before PersonStory derives production links.
    person_resolution.build(root)
    # PersonStory is a derived navigation index.  Rebuild it after any
    # production Mention is withheld so the index cannot retain a stale link.
    try:
        from . import build_person_story_index
    except ImportError:  # direct execution
        import build_person_story_index
    links, index, report = build_person_story_index.build(root)
    build_person_story_index.write_json(root / "data/derived/person-story-links.json", links)
    build_person_story_index.write_json(root / "data/derived/person-story-index.json", index)
    (root / "docs/person-story-pilot.md").write_text(report, encoding="utf-8")
    return read_json(root / MATERIALIZATION_PATH)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    result = build(args.root)
    print(
        f"materialized {result['wave_id']}: {len(result['members'])} Persons, "
        f"{result['promoted_mention_count']} promoted Mentions, "
        f"{result['withheld_occurrence_count']} withheld occurrences"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
