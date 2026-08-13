#!/usr/bin/env python3
"""Validate the deterministic P3A Person expansion analysis artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

try:
    from .person_expansion import (
        ALIASES_PATH,
        CORPUS_INDEX_PATH,
        JINSHU_MENTIONS_PATH,
        PEOPLE_PATH,
        P3A_PATH,
        P3A1_PATH,
        RELATIONS_PATH,
        SHISHUO_MENTIONS_PATH,
        UNRESOLVED_PATH,
        calculate_score,
        assign_tier,
    )
except ImportError:  # direct execution: python scripts/validate_person_expansion_candidates.py
    from person_expansion import (
        ALIASES_PATH,
        CORPUS_INDEX_PATH,
        JINSHU_MENTIONS_PATH,
        PEOPLE_PATH,
        P3A_PATH,
        P3A1_PATH,
        RELATIONS_PATH,
        SHISHUO_MENTIONS_PATH,
        UNRESOLVED_PATH,
        calculate_score,
        assign_tier,
    )


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema/person-expansion-candidates.schema.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _candidate_sort_key(candidate: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        -float(candidate["score"]),
        -float(candidate["components"]["current_story_coverage"]),
        -float(candidate["components"]["story_unlock_potential"]),
        -float(candidate["components"]["corpus_story_coverage"]),
        str(candidate["canonical_name"]),
        str(candidate["person_key"]),
    )


def validate(
    root: Path = ROOT,
    *,
    document: dict[str, Any] | None = None,
    unresolved: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    try:
        document = document or read_json(root / P3A_PATH)
        unresolved = unresolved or read_json(root / UNRESOLVED_PATH)
    except (OSError, ValueError) as exc:
        return [str(exc)]

    try:
        schema = read_json(root / SCHEMA_PATH)
        errors.extend(error.message for error in Draft202012Validator(schema).iter_errors(document))
    except Exception as exc:
        errors.append(f"P3A schema validation failed: {exc}")
        return errors

    people = read_json(root / PEOPLE_PATH).get("people", [])
    scoped_ids = {
        str(person.get("person_id"))
        for person in people
        if isinstance(person, Mapping) and isinstance(person.get("person_id"), str)
    }
    corpus_entries = read_json(root / CORPUS_INDEX_PATH).get("entries", [])
    story_ids = {
        str(entry.get("id"))
        for entry in corpus_entries
        if isinstance(entry, Mapping) and isinstance(entry.get("id"), str)
    }
    aliases = read_json(root / ALIASES_PATH).get("aliases", [])
    p3a1_candidate_ids: set[str] = set()
    p3a1_path = root / P3A1_PATH
    if p3a1_path.is_file():
        p3a1_document = read_json(p3a1_path)
        p3a1_candidate_ids = {
            str(candidate.get("candidate_id"))
            for candidate in p3a1_document.get("candidates", [])
            if isinstance(candidate, Mapping)
            and isinstance(candidate.get("candidate_id"), str)
            and candidate.get("materialization_state") == "new_candidate"
        }
    known_source_ids = set(scoped_ids)
    for alias in aliases:
        if isinstance(alias, Mapping):
            for key in ("person_ids", "resolved_person_ids"):
                values = alias.get(key, [])
                if isinstance(values, list):
                    known_source_ids.update(value for value in values if isinstance(value, str))
    for relative in (SHISHUO_MENTIONS_PATH, JINSHU_MENTIONS_PATH):
        for mention in read_json(root / relative).get("mentions", []):
            if isinstance(mention, Mapping) and isinstance(mention.get("person_id"), str):
                known_source_ids.add(mention["person_id"])
    for relation in read_json(root / RELATIONS_PATH).get("records", []):
        if isinstance(relation, Mapping):
            known_source_ids.update(
                value for value in (relation.get("subject_id"), relation.get("object_id"))
                if isinstance(value, str)
            )

    candidates = document.get("candidates", [])
    if document.get("candidate_count") != len(candidates):
        errors.append("candidate_count does not equal candidates length")
    if document.get("candidate_identity_policy", {}).get("scoped_person_ids_excluded") != sorted(scoped_ids):
        errors.append("candidate identity policy does not list the current scoped registry deterministically")
    keys: set[str] = set()
    source_person_ids: set[str] = set()
    ranked_p3a1_candidate_ids: set[str] = set()
    for candidate in candidates:
        key = candidate.get("person_key")
        source_id = candidate.get("source_person_id")
        if key in keys:
            errors.append(f"duplicate candidate key: {key}")
        keys.add(str(key))
        identity_kind = candidate.get("identity_kind", "existing_structured_candidate")
        candidate_id = candidate.get("candidate_id")
        if identity_kind == "p3a1_candidate":
            if not isinstance(candidate_id, str) or not candidate_id.startswith("candidate-identity-"):
                errors.append(f"P3A.1 candidate lacks a derived candidate_id: {key!r}")
            if source_id is not None:
                errors.append(f"P3A.1 candidate exposes a production source_person_id: {key!r}")
            if key != "candidate:" + str(candidate_id):
                errors.append(f"P3A.1 candidate key does not match candidate_id: {key!r} / {candidate_id!r}")
            if isinstance(candidate_id, str):
                ranked_p3a1_candidate_ids.add(candidate_id)
        else:
            if not isinstance(source_id, str) or source_id in scoped_ids:
                errors.append(f"candidate is scoped or has invalid source Person ID: {source_id!r}")
            elif source_id not in known_source_ids:
                errors.append(f"candidate source Person ID is not present in existing structured data: {source_id}")
            source_person_ids.add(str(source_id))
            if key != "candidate:" + str(source_id):
                errors.append(f"candidate key does not match source identity: {key!r} / {source_id!r}")
        for name, value in candidate.get("metrics", {}).items():
            if isinstance(value, (int, float)) and value < 0:
                errors.append(f"candidate {key} metric {name} is negative")
        components = candidate.get("components", {})
        for name in document.get("weights", {}):
            if name not in components:
                errors.append(f"candidate {key} lacks score component {name}")
        recomputed = calculate_score(components, document.get("weights", {}))
        if abs(float(candidate.get("score", -1)) - recomputed) > 0.00001:
            errors.append(f"candidate {key} score does not recompute: {candidate.get('score')} != {recomputed}")
        expected_tier = assign_tier(float(candidate["score"]), float(components["ambiguity_risk"]))
        if candidate.get("tier") != expected_tier:
            errors.append(f"candidate {key} tier does not follow documented rule")
        for story_id in candidate.get("top_current_story_ids", []) + candidate.get("top_unlock_story_ids", []):
            if story_id not in story_ids:
                errors.append(f"candidate {key} references unknown Story: {story_id}")
        if not set(candidate.get("connected_current_person_ids", [])).issubset(scoped_ids):
            errors.append(f"candidate {key} connects to a non-scoped Person")

    for gap in document.get("current_live_story_gaps", []):
        if gap.get("story_id") not in story_ids:
            errors.append(f"current live Story gap references unknown Story: {gap.get('story_id')}")
        if not set(gap.get("unscoped_resolved_candidate_person_ids", [])).issubset((known_source_ids - scoped_ids) | p3a1_candidate_ids):
            errors.append(f"current live Story gap contains an unknown/non-expanded identity: {gap.get('story_id')}")

    if [candidate.get("rank") for candidate in candidates] != list(range(1, len(candidates) + 1)):
        errors.append("candidate ranks are not sequential")
    if candidates and candidates != sorted(candidates, key=_candidate_sort_key):
        errors.append("candidate order does not follow the documented deterministic tie-break")

    direct_relation_map: dict[str, set[str]] = {}
    for relation in read_json(root / RELATIONS_PATH).get("records", []):
        if relation.get("relation_basis") != "direct" or relation.get("review_status") != "reviewed":
            continue
        subject, object_id = relation.get("subject_id"), relation.get("object_id")
        if subject in source_person_ids and object_id in scoped_ids:
            direct_relation_map.setdefault(str(subject), set()).add(str(relation.get("id")))
        if object_id in source_person_ids and subject in scoped_ids:
            direct_relation_map.setdefault(str(object_id), set()).add(str(relation.get("id")))
    for candidate in candidates:
        expected = direct_relation_map.get(candidate["source_person_id"], set()) if candidate.get("source_person_id") else set()
        actual = set(candidate.get("direct_relation_ids", []))
        if actual != expected:
            errors.append(f"candidate {candidate['person_key']} direct Relation metric is not derived from reviewed direct Relations")
        if candidate["metrics"]["direct_relation_to_current_count"] != len(actual):
            errors.append(f"candidate {candidate['person_key']} direct Relation count mismatch")

    if not isinstance(unresolved, Mapping) or unresolved.get("not_person_candidates") is not True:
        errors.append("unresolved surface artifact is not marked as non-Person analysis")
    if isinstance(unresolved, Mapping):
        surfaces = unresolved.get("surfaces", [])
        if unresolved.get("surface_count") != len(surfaces):
            errors.append("unresolved surface count mismatch")
        if document.get("unresolved_surface_count") != len(surfaces):
            errors.append("ranking document unresolved surface count mismatch")
        if document.get("unresolved_surface_artifact") != "data/derived/person-expansion-unresolved-surfaces.json":
            errors.append("ranking document points to an unexpected unresolved surface artifact")
        for row in surfaces:
            if row.get("not_ranked_as_person") is not True:
                errors.append(f"unresolved surface is not explicitly excluded: {row.get('surface')}")
            if row.get("surface") in {candidate.get("canonical_name") for candidate in candidates}:
                errors.append(f"unresolved surface was silently ranked as a Person: {row.get('surface')}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = validate(args.root)
    if errors:
        for error in errors:
            print(error)
        return 1
    print("P3A person expansion artifacts valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
