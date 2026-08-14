#!/usr/bin/env python3
"""Validate the frozen P3B.1 Person Expansion Wave 1 materialization."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, RefResolver

try:
    from .build_six_person_pilot import parse_frontmatter, parse_shishuo_sections
    from .validate_person_sketch import validate_source as validate_person_sketch_source
except ImportError:  # direct execution
    from build_six_person_pilot import parse_frontmatter, parse_shishuo_sections
    from validate_person_sketch import validate_source as validate_person_sketch_source


ROOT = Path(__file__).resolve().parents[1]
WAVE_PATH = Path("data/annotation/person-expansion-wave-1.json")
RANKING_PATH = Path("data/derived/person-expansion-wave-1-ranking.json")
P3A1_PATH = Path("data/derived/person-identity-candidates.json")
MATERIALIZATION_PATH = Path("data/derived/person-expansion-wave-1-materialization.json")
PEOPLE_PATH = Path("data/people.json")
ALIASES_PATH = Path("data/aliases.json")
MENTIONS_PATH = Path("data/mentions/shishuo.json")
EVIDENCE_PATH = Path("data/evidence/wp1-evidence.json")
LINKS_PATH = Path("data/derived/person-story-links.json")
SC1_PATH = Path("data/derived/sc1-site.json")
RELATIONS_PATH = Path("data/annotation/wp1-relations.json")
SCHEMA_PATH = Path("schema/person-expansion-wave.schema.json")
MATERIALIZATION_SCHEMA_PATH = Path("schema/person-expansion-materialization.schema.json")
WAVE_ID = "p3b-wave-1"
EVIDENCE_PREFIX = "evidence-p3b-wave-1-"
MENTION_PREFIX = "shishuo-p3b-wave-1-"
ALIAS_PREFIX = "alias-p3b-wave-1-"


def read_json(root: Path, path: Path) -> Any:
    return json.loads((root / path).read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _entry_sections(root: Path, entry: Mapping[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    path = root / str(entry["path"])
    return parse_shishuo_sections(path.read_text(encoding="utf-8"))


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        wave = read_json(root, WAVE_PATH)
        ranking = read_json(root, RANKING_PATH)
        p3a1 = read_json(root, P3A1_PATH)
        materialization = read_json(root, MATERIALIZATION_PATH)
        people = read_json(root, PEOPLE_PATH).get("people", [])
        aliases = read_json(root, ALIASES_PATH).get("aliases", [])
        mentions = read_json(root, MENTIONS_PATH).get("mentions", [])
        evidence = read_json(root, EVIDENCE_PATH).get("records", [])
        links = read_json(root, LINKS_PATH).get("links", [])
        sc1 = read_json(root, SC1_PATH)
        entries = read_json(root, Path("data/shishuo-corpus-index.json")).get("entries", [])
    except (OSError, ValueError, KeyError) as exc:
        return [f"P3B.1 cannot read required artifact: {exc}"]

    try:
        schema = read_json(root, SCHEMA_PATH)
        errors.extend(
            f"Wave schema: {error.message}"
            for error in Draft202012Validator(schema).iter_errors(wave)
        )
        materialization_schema = read_json(root, MATERIALIZATION_SCHEMA_PATH)
        resolver = RefResolver.from_schema(
            materialization_schema,
            store={schema["$id"]: schema},
        )
        errors.extend(
            f"Materialization schema: {error.message}"
            for error in Draft202012Validator(
                materialization_schema,
                resolver=resolver,
            ).iter_errors(materialization)
        )
    except (OSError, ValueError) as exc:
        errors.append(f"Wave schema cannot be validated: {exc}")

    if wave.get("wave_id") != WAVE_ID or materialization.get("wave_id") != WAVE_ID:
        errors.append("P3B.1 wave/materialization IDs do not match")
    ranking_path = root / str(wave.get("source_ranking_artifact", ""))
    if not ranking_path.is_file():
        errors.append("P3B.1 frozen ranking snapshot is missing")
    else:
        ranking_hash = sha256_file(ranking_path)
        if ranking_hash != wave.get("source_ranking_sha256"):
            errors.append("P3B.1 frozen ranking hash does not match the wave manifest")
        if ranking_hash != materialization.get("source_ranking_sha256"):
            errors.append("P3B.1 materialization does not retain the frozen ranking hash")

    members = wave.get("members", [])
    materialized_members = materialization.get("members", [])
    if len(members) != 10 or len(materialized_members) != 10:
        errors.append("P3B.1 must contain exactly 10 materialized Wave 1 members")
    ranks = [item.get("rank_at_selection") for item in members if isinstance(item, Mapping)]
    if ranks != list(range(1, 11)):
        errors.append(f"P3B.1 ranks are not sequential 1-10: {ranks}")
    member_by_candidate = {
        str(item.get("candidate_id")): item
        for item in members
        if isinstance(item, Mapping) and isinstance(item.get("candidate_id"), str)
    }
    materialized_by_candidate = {
        str(item.get("candidate_id")): item
        for item in materialized_members
        if isinstance(item, Mapping) and isinstance(item.get("candidate_id"), str)
    }
    if set(member_by_candidate) != set(materialized_by_candidate):
        errors.append("Wave manifest and materialization member sets differ")
    if len({item.get("person_id") for item in members}) != len(members):
        errors.append("Wave 1 production Person IDs are not unique")

    ranking_by_candidate = {
        str(item.get("candidate_id")): item
        for item in ranking.get("candidates", [])
        if isinstance(item, Mapping) and isinstance(item.get("candidate_id"), str)
    }
    candidates_by_id = {
        str(item.get("candidate_id")): item
        for item in p3a1.get("candidates", [])
        if isinstance(item, Mapping) and isinstance(item.get("candidate_id"), str)
    }
    for candidate_id, member in member_by_candidate.items():
        rank_row = ranking_by_candidate.get(candidate_id)
        candidate = candidates_by_id.get(candidate_id)
        if rank_row is None:
            errors.append(f"Wave member is absent from the frozen ranking: {candidate_id}")
        elif rank_row.get("rank") != member.get("rank_at_selection"):
            errors.append(f"Wave member rank changed: {candidate_id}")
        if candidate is None:
            errors.append(f"Wave member is absent from P3A.1: {candidate_id}")
        else:
            if candidate.get("status") not in {"already_materialized", "strong_candidate"}:
                errors.append(f"Wave member has an invalid current P3A.1 status: {candidate_id}")
            if candidate.get("matched_person_id") != member.get("person_id"):
                errors.append(f"Wave candidate-to-Person mapping disagrees: {candidate_id}")
        materialized = materialized_by_candidate.get(candidate_id, {})
        if materialized.get("materialization_status") != "materialized":
            errors.append(f"Wave member is not materialized: {candidate_id}")
        if materialized.get("person_id") != member.get("person_id"):
            errors.append(f"Wave materialization Person ID disagrees: {candidate_id}")

    people_by_id = {str(item.get("person_id")): item for item in people if isinstance(item, Mapping)}
    wave_person_ids = {str(item.get("person_id")) for item in members}
    # P3B.1 records the registry size at the end of Wave 1.  Later explicit
    # materialization waves may extend the unified registry, so the historical
    # Wave-1 snapshot must remain an exact lower-bound checkpoint rather than
    # rejecting valid descendants of that registry.
    if len(people) < materialization.get("people_after"):
        errors.append("P3B.1 people_after exceeds the current production registry")
    if not wave_person_ids.issubset(people_by_id):
        errors.append("P3B.1 production Person registry is missing a Wave Person")
    for person_id in wave_person_ids:
        person = people_by_id.get(person_id, {})
        metadata = person.get("materialization", {})
        if metadata.get("wave_id") != WAVE_ID:
            errors.append(f"Wave Person lacks materialization provenance: {person_id}")
        if person.get("review_status") != "candidate":
            errors.append(f"Wave Person review status was silently promoted: {person_id}")

    evidence_by_id = {str(item.get("id")): item for item in evidence if isinstance(item, Mapping)}
    p3b_evidence_ids = {
        evidence_id for evidence_id in evidence_by_id if evidence_id.startswith(EVIDENCE_PREFIX)
    }
    if set(materialization.get("production_evidence_ids", [])) != p3b_evidence_ids:
        errors.append("P3B.1 production Evidence inventory differs from materialization output")
    for evidence_id in p3b_evidence_ids:
        item = evidence_by_id[evidence_id]
        if item.get("review_status") != "candidate":
            errors.append(f"P3B.1 Evidence review status was silently promoted: {evidence_id}")
        if not isinstance(item.get("locator", {}).get("source_provenance"), Mapping):
            errors.append(f"P3B.1 Evidence lacks source provenance: {evidence_id}")

    aliases_by_id = {str(item.get("alias_id")): item for item in aliases if isinstance(item, Mapping)}
    wave_alias_ids: set[str] = set()
    for person_id in wave_person_ids:
        person = people_by_id.get(person_id, {})
        for alias_id in person.get("alias_ids", []):
            alias = aliases_by_id.get(str(alias_id))
            if alias is None:
                errors.append(f"Wave Person references missing Alias: {person_id}/{alias_id}")
                continue
            wave_alias_ids.add(str(alias_id))
            if not str(alias_id).startswith(ALIAS_PREFIX):
                errors.append(f"Wave Alias is not traceable to P3B.1: {alias_id}")
            if alias.get("person_ids") != [person_id]:
                errors.append(f"Wave Alias endpoint is not unique: {alias_id}")
            mode = alias.get("resolution_mode")
            if alias.get("alias_type") in {"office_title", "contextual_title", "posthumous_title"} and mode == "exact":
                errors.append(f"Contextual/title Alias was promoted as exact: {alias_id}")
            if alias.get("review_status") != "candidate":
                errors.append(f"Wave Alias review status was silently promoted: {alias_id}")
            for source in alias.get("source_evidence", []):
                if source.get("evidence_id") not in evidence_by_id:
                    errors.append(f"Wave Alias Evidence does not resolve: {alias_id}/{source.get('evidence_id')}")

    mentions_by_id = {str(item.get("mention_id")): item for item in mentions if isinstance(item, Mapping)}
    occurrence_keys: dict[tuple[str, str, int, str], str] = {}
    for mention_id, mention in mentions_by_id.items():
        evidence_data = mention.get("evidence", {})
        offset = evidence_data.get("section_offset") if isinstance(evidence_data, Mapping) else None
        if not isinstance(offset, int):
            continue
        key = (
            str(mention.get("entry_id") or mention.get("source_id")),
            str(mention.get("section")),
            offset,
            str(mention.get("surface")),
        )
        previous = occurrence_keys.get(key)
        if previous is not None and previous != mention_id:
            errors.append(f"duplicate production Mention occurrence: {previous}/{mention_id}")
        occurrence_keys[key] = mention_id

    promoted_ids: set[str] = set()
    for candidate_id, member in materialized_by_candidate.items():
        for mention_id in member.get("promoted_mention_ids", []):
            promoted_ids.add(str(mention_id))
            mention = mentions_by_id.get(str(mention_id))
            if mention is None:
                errors.append(f"promoted Mention does not resolve: {mention_id}")
                continue
            if mention.get("person_id") != member.get("person_id"):
                errors.append(f"promoted Mention points to the wrong Person: {mention_id}")
            if mention.get("confidence") != "high" or not str(mention.get("resolution_method", "")).startswith("exact"):
                errors.append(f"promoted Mention is not exact/high-confidence: {mention_id}")
            if mention.get("review_status") != "candidate":
                errors.append(f"promoted Mention review status was silently promoted: {mention_id}")
            if not mention_id.startswith(MENTION_PREFIX):
                errors.append(f"Wave Mention is not traceable to P3B.1: {mention_id}")
            for evidence_id in mention.get("evidence", {}).get("evidence_ids", []):
                if evidence_id not in evidence_by_id:
                    errors.append(f"promoted Mention Evidence does not resolve: {mention_id}/{evidence_id}")

    entry_by_id = {str(item.get("id")): item for item in entries if isinstance(item, Mapping)}
    for mention_id in sorted(promoted_ids):
        mention = mentions_by_id.get(mention_id, {})
        entry = entry_by_id.get(str(mention.get("entry_id")))
        if entry is None:
            continue
        offset = mention.get("evidence", {}).get("section_offset")
        surface = mention.get("surface", "")
        section = mention.get("section")
        matches = []
        for section_name, text, _metadata in _entry_sections(root, entry):
            if section_name == section and isinstance(offset, int) and text[offset : offset + len(surface)] == surface:
                matches.append(True)
        if len(matches) != 1:
            errors.append(f"promoted Mention anchor is not unique in canonical text: {mention_id}")

    link_by_person = {}
    for link in links:
        person_id = link.get("person_id")
        if person_id in wave_person_ids:
            link_by_person.setdefault(person_id, []).append(link)
            if link.get("relation_id") is not None:
                errors.append(f"Wave PersonStory link carries a Relation assertion: {link.get('id')}")
            for mention_id in [*link.get("supporting_mention_ids", []), *link.get("candidate_mention_ids", [])]:
                if mention_id not in promoted_ids:
                    errors.append(f"Wave PersonStory link uses a non-promoted Mention: {link.get('id')}/{mention_id}")
            for presence in link.get("presences", []):
                if presence.get("presence_kind") == "participant":
                    errors.append(f"Wave PersonStory link inferred participant status: {link.get('id')}")
    # A materialized Person may legitimately have no current PersonStory
    # link after a later identity-correction pass.  Materialization preserves
    # the production identity; it must not preserve an unsafe navigation edge
    # merely to satisfy the historical Wave-1 snapshot.  Validate every link
    # that does exist above, while allowing an empty post-correction topology.

    sketch_errors = validate_person_sketch_source(root)
    errors.extend(f"Person Sketch: {error}" for error in sketch_errors)
    sketch_records = read_json(root, Path("data/annotation/person-sketches.json")).get("records", [])
    sketch_ids = {str(item.get("person_id")) for item in sketch_records if isinstance(item, Mapping)}
    if not wave_person_ids.issubset(sketch_ids):
        errors.append("P3B.1 Person Sketch coverage is incomplete")

    protected_hashes = materialization.get("protected_hashes", {})
    for relative_path, expected_hash in protected_hashes.items():
        if relative_path == str(RELATIONS_PATH):
            # R3B intentionally appends reviewed production Relations to the
            # registry.  Preserve the P3B.1 legacy Relation facts by checking
            # the unchanged WP1 sample projection record-by-record rather
            # than requiring the now-expanded registry hash to remain frozen.
            try:
                legacy_relations = read_json(root, Path("data/derived/wp1-site.json")).get("relations", [])
                current_relations = {
                    str(item.get("id")): item
                    for item in read_json(root, RELATIONS_PATH).get("records", [])
                    if isinstance(item, Mapping) and item.get("id")
                }
                for legacy in legacy_relations:
                    relation_id = str(legacy.get("id"))
                    if current_relations.get(relation_id) != legacy:
                        errors.append(f"protected P3B.1 Relation fact changed: {relation_id}")
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append(f"protected P3B.1 Relation baseline cannot be checked: {exc}")
            continue
        path = root / relative_path
        if not path.is_file() or sha256_file(path) != expected_hash:
            errors.append(f"protected P3B.1 input changed: {relative_path}")

    sc1_people = {str(item.get("id")) for item in sc1.get("people", []) if isinstance(item, Mapping)}
    if not wave_person_ids.issubset(sc1_people):
        errors.append("SC1 frontend projection is missing a Wave Person")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("P3B.1 validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("P3B.1 Wave 1 validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
