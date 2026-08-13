#!/usr/bin/env python3
"""Validate the curated Person Sketch v1 layer and its SC1 projection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

try:
    from .person_sketch import build_person_sketches, load_source
except ImportError:  # direct execution
    from person_sketch import build_person_sketches, load_source


ROOT = Path(__file__).resolve().parents[1]


def read_json(root: Path, relative: str) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def _person_ids(people: list[Any]) -> list[str]:
    return [
        str(item.get("id", item.get("person_id")))
        for item in people
        if isinstance(item, Mapping) and isinstance(item.get("id", item.get("person_id")), str)
    ]


def validate_source(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        source = load_source(root)
        people = read_json(root, "data/people.json").get("people", [])
        aliases = read_json(root, "data/aliases.json").get("aliases", [])
        evidence = read_json(root, "data/evidence/wp1-evidence.json").get("records", [])
        schema = read_json(root, "schema/person-sketch.schema.json")
    except (OSError, ValueError, KeyError) as exc:
        return [f"Person Sketch cannot read required input: {exc}"]

    try:
        Draft202012Validator.check_schema(schema)
        errors.extend(
            f"Person Sketch schema: {error.message}"
            for error in Draft202012Validator(schema).iter_errors(source)
        )
    except (OSError, ValueError) as exc:
        errors.append(f"Person Sketch schema cannot be validated: {exc}")

    canonical_ids = _person_ids(people)
    if source.get("person_scope") != canonical_ids:
        errors.append("Person Sketch scope must exactly follow the unified Person registry")
    records = source.get("records", [])
    records_by_id = {
        str(item.get("person_id")): item
        for item in records
        if isinstance(item, Mapping) and isinstance(item.get("person_id"), str)
    }
    if len(records) != len(records_by_id) or set(records_by_id) != set(canonical_ids):
        errors.append("Person Sketch must contain exactly one record for every scoped Person")
    evidence_ids = {
        str(item.get("id"))
        for item in evidence
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    people_by_id = {
        str(item.get("id", item.get("person_id"))): item
        for item in people
        if isinstance(item, Mapping) and isinstance(item.get("id", item.get("person_id")), str)
    }
    alias_ids = {
        str(item.get("alias_id"))
        for item in aliases
        if isinstance(item, Mapping) and isinstance(item.get("alias_id"), str)
    }
    for person_id in canonical_ids:
        record = records_by_id.get(person_id)
        if not isinstance(record, Mapping):
            continue
        person = people_by_id[person_id]
        for alias_id in person.get("alias_ids", []):
            if alias_id not in alias_ids:
                errors.append(f"Person registry Alias does not resolve: {person_id}/{alias_id}")
        identity = record.get("identity", {})
        if not isinstance(identity, Mapping):
            continue
        if identity.get("canonical_name") != person.get("canonical_name"):
            errors.append(f"Person Sketch canonical identity differs: {person_id}")
        identity_evidence = identity.get("evidence_ids", [])
        profile_evidence = record.get("profile_evidence_ids", [])
        if not identity_evidence:
            errors.append(f"Person Sketch identity has no evidence: {person_id}")
        for field in ("courtesy_name", "clan", "identity_roles", "brief_intro"):
            value = identity.get(field)
            if value not in (None, [], "") and not identity_evidence:
                errors.append(f"Person Sketch identity field is unsupported: {person_id}/{field}")
        if isinstance(identity.get("brief_intro"), str) and len(identity["brief_intro"]) > 120:
            errors.append(f"Person Sketch brief_intro is too long: {person_id}")
        for evidence_id in [*identity_evidence, *profile_evidence]:
            if evidence_id not in evidence_ids:
                errors.append(f"Person Sketch Evidence does not resolve: {person_id}/{evidence_id}")
        forbidden = {"relations", "relation_ids", "story_ids", "person_story_ids"}
        if forbidden.intersection(record):
            errors.append(f"Person Sketch redefines another factual layer: {person_id}")
    return errors


def validate_bundle(root: Path = ROOT) -> list[str]:
    errors = validate_source(root)
    try:
        bundle = read_json(root, "data/derived/sc1-site.json")
    except (OSError, ValueError) as exc:
        return errors + [f"Person Sketch cannot read SC1 bundle: {exc}"]
    people = bundle.get("people", [])
    mentions = {
        str(item["id"]): item
        for item in bundle.get("mentions", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    raw_mentions = {
        str(item["mention_id"]): item
        for item in read_json(root, "data/mentions/shishuo.json").get("mentions", [])
        if isinstance(item, Mapping) and isinstance(item.get("mention_id"), str)
    }
    try:
        expected = build_person_sketches(
            root,
            people=people,
            frontend_mentions=mentions,
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return errors + [f"Person Sketch projection cannot be rebuilt: {exc}"]
    if bundle.get("person_sketches") != expected:
        errors.append("SC1 person_sketches is not the deterministic projection of curated data")

    evidence_ids = {
        str(item.get("id"))
        for item in bundle.get("evidence", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    sketch_map = bundle.get("person_sketches")
    if not isinstance(sketch_map, Mapping):
        return errors + ["SC1 bundle lacks person_sketches object"]
    people_ids = set(_person_ids(people))
    if set(sketch_map) != people_ids:
        errors.append("SC1 person_sketches keys do not match frontend Persons")
    for person_id, sketch in sketch_map.items():
        if not isinstance(sketch, Mapping):
            errors.append(f"SC1 Person Sketch is not an object: {person_id}")
            continue
        identity = sketch.get("identity", {})
        if isinstance(identity, Mapping):
            for evidence_id in [*identity.get("evidence_ids", []), *sketch.get("profile_evidence_ids", [])]:
                if evidence_id not in evidence_ids:
                    errors.append(f"SC1 Person Sketch Evidence does not resolve: {person_id}/{evidence_id}")
        for alias in sketch.get("aliases", []):
            if not isinstance(alias, Mapping):
                continue
            for mention_id in alias.get("mention_ids", []):
                mention = mentions.get(mention_id)
                raw_mention = raw_mentions.get(mention_id)
                if mention is None or raw_mention is None:
                    errors.append(f"SC1 Person Sketch Alias Mention does not resolve: {person_id}/{mention_id}")
                elif raw_mention.get("alias_id") != alias.get("alias_id"):
                    errors.append(f"SC1 Person Sketch Alias does not match Mention alias: {person_id}/{mention_id}")
                elif person_id not in [raw_mention.get("person_id"), *raw_mention.get("candidate_person_ids", [])]:
                    errors.append(f"SC1 Person Sketch Alias Mention points to another Person: {person_id}/{mention_id}")
            for evidence_id in alias.get("evidence_ids", []):
                if evidence_id not in evidence_ids:
                    errors.append(f"SC1 Person Sketch Alias Evidence does not resolve: {person_id}/{evidence_id}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", action="store_true", help="also validate the generated SC1 projection")
    args = parser.parse_args()
    errors = validate_bundle() if args.bundle else validate_source()
    if errors:
        print("Person Sketch validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("Person Sketch validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
