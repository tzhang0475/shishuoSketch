#!/usr/bin/env python3
"""Validate the frozen M2A Person Wave 2 without changing production data."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
WAVE_PATH = Path("data/annotation/person-expansion-wave-2.json")
RANKING_PATH = Path("data/derived/m2-person-expansion-ranking.json")
MATERIALIZATION_PATH = Path("data/derived/person-expansion-wave-2-materialization.json")
PEOPLE_PATH = Path("data/people.json")
ALIASES_PATH = Path("data/aliases.json")
MENTIONS_PATH = Path("data/mentions/shishuo.json")
EVIDENCE_PATH = Path("data/evidence/wp1-evidence.json")
LINKS_PATH = Path("data/derived/person-story-links.json")
SKETCH_PATH = Path("data/annotation/person-sketches.json")
RELATIONS_PATH = Path("data/annotation/wp1-relations.json")
ALLOCATION_PATH = Path("data/derived/person-id-allocation-state.json")


def read(root: Path, path: Path) -> Any:
    return json.loads((root / path).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        wave = read(root, WAVE_PATH)
        ranking = read(root, RANKING_PATH)
        materialization = read(root, MATERIALIZATION_PATH)
        people = read(root, PEOPLE_PATH).get("people", [])
        aliases = read(root, ALIASES_PATH).get("aliases", [])
        mentions = read(root, MENTIONS_PATH).get("mentions", [])
        evidence = read(root, EVIDENCE_PATH).get("records", [])
        links = read(root, LINKS_PATH).get("links", [])
        sketches = read(root, SKETCH_PATH).get("records", [])
        relations = read(root, RELATIONS_PATH).get("records", [])
        allocation = read(root, ALLOCATION_PATH)
        wave_schema = read(root, Path("schema/person-expansion-wave-m2.schema.json"))
        materialization_schema = read(root, Path("schema/person-expansion-materialization-m2.schema.json"))
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        return [f"M2 Person expansion artifact cannot be read: {exc}"]

    errors.extend(f"Wave schema: {e.message}" for e in Draft202012Validator(wave_schema).iter_errors(wave))
    errors.extend(f"Materialization schema: {e.message}" for e in Draft202012Validator(materialization_schema).iter_errors(materialization))
    if sha256(root / RANKING_PATH) != wave.get("source_ranking_sha256"):
        errors.append("Wave 2 source ranking hash does not match")
    if sha256(root / RANKING_PATH) != materialization.get("source_ranking_sha256"):
        errors.append("Wave 2 materialization ranking hash does not match")

    members = wave.get("members", [])
    materialized = materialization.get("members", [])
    if [m.get("rank_at_selection") for m in members] != list(range(1, 19)):
        errors.append("Wave 2 ranks are not sequential 1–18")
    expected_ids = [f"person-{i:03d}" for i in range(18, 36)]
    if [m.get("person_id") for m in members] != expected_ids:
        errors.append("Wave 2 Person IDs are not person-018..person-035 in frozen rank order")
    if {m.get("candidate_id") for m in members} != {m.get("candidate_id") for m in materialized}:
        errors.append("Wave 2 manifest/materialization candidate sets differ")

    ranking_by_id = {str(x.get("candidate_id")): x for x in ranking.get("candidates", []) if isinstance(x, Mapping)}
    member_by_id = {str(x.get("candidate_id")): x for x in members if isinstance(x, Mapping)}
    for candidate_id, member in member_by_id.items():
        row = ranking_by_id.get(candidate_id)
        if row is None:
            errors.append(f"Wave 2 candidate is absent from ranking: {candidate_id}")
            continue
        if row.get("rank") != member.get("rank_at_selection") or row.get("eligible") is not True:
            errors.append(f"Wave 2 member does not match frozen eligible ranking row: {candidate_id}")
        if row.get("status") not in {"strong_candidate", "already_materialized"}:
            errors.append(f"Wave 2 member is not a strong identity candidate: {candidate_id}")
        if not row.get("identity_evidence_ids"):
            errors.append(f"Wave 2 member has no identity Evidence: {candidate_id}")
        if any(flag in set(row.get("risk_flags", [])) for flag in {"conflicting_identity_evidence", "multiple_possible_people", "unresolved_identity", "no_full_name"}):
            errors.append(f"Wave 2 member has a blocking identity risk: {candidate_id}")

    people_by_id = {str(x.get("person_id")): x for x in people if isinstance(x, Mapping)}
    wave_ids = set(expected_ids)
    # Later frozen waves extend the registry; the M2 checkpoint remains
    # authoritative for its own 18 IDs without rejecting a valid W3 suffix.
    if len(people) < 35 or not wave_ids <= set(people_by_id):
        errors.append("Production registry does not contain the complete 17+18 M2 Person scope")
    if materialization.get("people_before") != 17 or materialization.get("people_after") != 35:
        errors.append("Wave 2 people_before/after does not record 17→35")
    for person_id in expected_ids:
        person = people_by_id.get(person_id, {})
        if person.get("materialization", {}).get("wave_id") != "p3b-wave-2":
            errors.append(f"Wave 2 Person lacks materialization provenance: {person_id}")
        if person.get("review_status") != "candidate":
            errors.append(f"Wave 2 Person review status was promoted: {person_id}")

    aliases_by_id = {str(x.get("alias_id")): x for x in aliases if isinstance(x, Mapping)}
    for person_id in expected_ids:
        person = people_by_id.get(person_id, {})
        for alias_id in person.get("alias_ids", []):
            alias = aliases_by_id.get(str(alias_id))
            if alias is None:
                errors.append(f"Wave 2 Alias is missing: {person_id}/{alias_id}")
                continue
            if alias.get("review_status") != "candidate":
                errors.append(f"Wave 2 Alias review status was promoted: {alias_id}")
            if alias.get("alias_type") in {"office_title", "contextual_title", "posthumous_title"} and alias.get("resolution_mode") == "exact":
                errors.append(f"Wave 2 contextual Alias became exact: {alias_id}")
            if alias.get("person_ids") != [person_id]:
                errors.append(f"Wave 2 Alias endpoint is not unique: {alias_id}")
            for source in alias.get("source_evidence", []):
                if source.get("evidence_id") not in {x.get("id") for x in evidence}:
                    errors.append(f"Wave 2 Alias Evidence does not resolve: {alias_id}")

    mention_by_id = {str(x.get("mention_id")): x for x in mentions if isinstance(x, Mapping)}
    promoted_ids = {str(x) for m in materialized for x in m.get("promoted_mention_ids", [])}
    for mention_id in promoted_ids:
        mention = mention_by_id.get(mention_id)
        if mention is None:
            errors.append(f"Wave 2 promoted Mention is missing: {mention_id}")
        elif mention.get("person_id") not in wave_ids:
            errors.append(f"Wave 2 promoted Mention has a non-Wave endpoint: {mention_id}")
    occurrence_keys: dict[tuple[str, str, int, str], str] = {}
    for mention_id, mention in mention_by_id.items():
        if mention.get("person_id") not in wave_ids:
            continue
        offset = mention.get("evidence", {}).get("section_offset")
        if not isinstance(offset, int):
            continue
        key = (str(mention.get("entry_id") or mention.get("source_id")), str(mention.get("section")), offset, str(mention.get("surface")))
        if key in occurrence_keys and occurrence_keys[key] != mention_id:
            errors.append(f"duplicate Wave 2 Mention occurrence: {key}")
        occurrence_keys[key] = mention_id

    evidence_ids = {str(x.get("id")) for x in evidence if isinstance(x, Mapping)}
    for member in members:
        if not set(member.get("identity_evidence_ids", [])) <= evidence_ids:
            errors.append(f"Wave 2 identity Evidence does not resolve: {member.get('candidate_id')}")
    if materialization.get("production_evidence_ids") and not set(materialization["production_evidence_ids"]) <= evidence_ids:
        errors.append("Wave 2 production Evidence inventory has missing IDs")

    sketch_ids = {str(x.get("person_id")) for x in sketches if isinstance(x, Mapping)}
    if not wave_ids <= sketch_ids:
        errors.append("Not every Wave 2 Person has a Person Sketch")
    link_ids = {str(x.get("person_id")) for x in links if isinstance(x, Mapping)}
    if not wave_ids <= link_ids:
        errors.append("Not every Wave 2 Person has a PersonStory projection")
    if any((x.get("subject_id") in wave_ids or x.get("object_id") in wave_ids) for x in relations if isinstance(x, Mapping)):
        # This is allowed only for a relation that existed before M2.  The
        # current production Relation layer is unchanged, so no new relation
        # may carry an M2 materialization marker.
        if any("p3b-wave-2" in json.dumps(x, ensure_ascii=False) or "m2a" in json.dumps(x, ensure_ascii=False) for x in relations):
            errors.append("Wave 2 materialization introduced a Relation record")
    if not isinstance(allocation.get("next_person_sequence"), int) or allocation.get("next_person_sequence") < 36:
        errors.append("M2 allocation state next_person_sequence must not move backwards")
    return sorted(set(errors))


if __name__ == "__main__":
    problems = validate()
    if problems:
        print("M2 Person expansion validation failed:")
        print("\n".join(f"- {problem}" for problem in problems))
        raise SystemExit(1)
    print("M2 Person expansion Wave 2 validation passed")
