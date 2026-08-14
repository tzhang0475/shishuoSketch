#!/usr/bin/env python3
"""Apply the one-time P-ID1 Person primary-key migration.

This utility deliberately migrates only structured Person foreign keys.  It
does not replace strings inside aliases, Mention IDs, Evidence IDs, source
text, or generated prose.  The manifest is the only authority for the
old-to-new identity mapping.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = Path("data/migrations/person-id-canonicalization-v1.json")

# These are fields whose values are Person IDs in the repository's structured
# data contracts.  `id` is intentionally excluded and handled only in the
# narrow record contexts below.
PERSON_VALUE_FIELDS = frozenset(
    {
        "person_id",
        "person_ids",
        "person_scope",
        "candidate_person_ids",
        "resolved_person_ids",
        "linked_person_ids",
        "main_text_person_ids",
        "liu_annotation_only_person_ids",
        "matched_person_id",
        "connected_current_person_ids",
        "scoped_person_ids_excluded",
        "production_person_ids",
        "wave1_person_ids",
        "wave1_persons_with_candidate_relation",
        "wave2_person_ids",
        "wave2_persons_with_candidate_relation",
        "selected_person_ids",
        "main_materialized_person_ids",
        "current_production_person_ids",
        "isolated_person_ids_by_reviewed_relation",
        "subject_id",
        "object_id",
        "person_a_id",
        "person_b_id",
    }
)
PERSON_KEY_MAP_FIELDS = frozenset({"person_display", "person_sketches"})

# Explicitly enumerated generated/annotation JSON inputs.  Canonical source
# payloads and all files whose IDs have different semantics are excluded.
JSON_PATHS = (
    Path("data/people.json"),
    Path("data/aliases.json"),
    Path("data/mentions/shishuo.json"),
    Path("data/mentions/jinshu.json"),
    Path("data/annotation/person-sketches.json"),
    Path("data/annotation/wp1-people.json"),
    Path("data/annotation/wp1-mentions.json"),
    Path("data/annotation/wp1-relations.json"),
    Path("data/annotation/wp1-stories.json"),
    Path("data/annotation/wp1-eras.json"),
    Path("data/annotation/person-expansion-wave-1.json"),
    Path("data/annotation/person-expansion-wave-2.json"),
    Path("data/annotation/story-expansion-wave-1.json"),
    Path("data/annotation/person-relation-candidates-r3.json"),
    Path("data/annotation/story-scene-contexts.json"),
    Path("data/derived/person-story-links.json"),
    Path("data/derived/person-story-index.json"),
    Path("data/derived/story-chain-gold-index.json"),
    Path("data/derived/story-chain-connectivity.json"),
    Path("data/derived/person-expansion-candidates.json"),
    Path("data/derived/person-identity-candidates.json"),
    Path("data/derived/person-candidate-occurrences.json"),
    Path("data/derived/person-expansion-wave-1-materialization.json"),
    Path("data/derived/person-expansion-wave-2-materialization.json"),
    Path("data/derived/m2-person-expansion-ranking.json"),
    Path("data/derived/m2-story-expansion-ranking.json"),
    Path("data/derived/person-expansion-wave-1-ranking.json"),
    Path("data/derived/person-relation-candidates-r3.json"),
    Path("data/derived/story-scene-contexts.json"),
    Path("data/derived/wp1-site.json"),
    Path("data/derived/sc1-site.json"),
    Path("data/derived/person-expansion-unresolved-surfaces.json"),
    Path("data/derived/person-id-allocation-state.json"),
    Path("data/story-chain-gold-set.json"),
    Path("data/manifest/milestone-1.json"),
    Path("site/src/generated/wp1-site.json"),
    Path("site/src/generated/sc1-site.json"),
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_manifest(root: Path = ROOT) -> dict[str, Any]:
    document = read_json(root / MANIFEST_PATH)
    records = document.get("records")
    if not isinstance(records, list) or len(records) != 17:
        raise ValueError("P-ID1 manifest must contain exactly 17 records")
    old_ids = [record.get("old_person_id") for record in records]
    new_ids = [record.get("new_person_id") for record in records]
    if any(not isinstance(value, str) or not value for value in old_ids + new_ids):
        raise ValueError("P-ID1 manifest contains an empty Person ID")
    if len(set(old_ids)) != len(old_ids) or len(set(new_ids)) != len(new_ids):
        raise ValueError("P-ID1 manifest is not bijective")
    expected = {f"person-{index:03d}" for index in range(1, 18)}
    if set(new_ids) != expected:
        raise ValueError("P-ID1 manifest targets must be person-001..person-017")
    if document.get("next_person_sequence") != 18:
        raise ValueError("P-ID1 next_person_sequence must be 18")
    for record in records:
        if not record.get("canonical_name") or not record.get("allocation_basis"):
            raise ValueError(f"P-ID1 manifest record is incomplete: {record!r}")
    return document


def mapping_from_manifest(document: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(record["old_person_id"]): str(record["new_person_id"])
        for record in document["records"]
    }


def _map_value(value: Any, mapping: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [_map_value(item, mapping) for item in value]
    return value


def _is_person_record_id(path: tuple[str, ...], relative: Path) -> bool:
    if path[-1:] != ("id",):
        return False
    # WP1 annotation records and generated bundle people use `id` for the
    # Person primary key.  No other generic `id` field is rewritten.
    if relative in {
        Path("data/annotation/wp1-people.json"),
    }:
        return True
    return "people" in path[:-1]


def transform(value: Any, mapping: Mapping[str, str], relative: Path, path: tuple[str, ...] = ()) -> Any:
    if isinstance(value, list):
        return [transform(item, mapping, relative, path + (str(index),)) for index, item in enumerate(value)]
    if not isinstance(value, dict):
        return value

    result: dict[str, Any] = {}
    for key, child in value.items():
        if key in PERSON_KEY_MAP_FIELDS and isinstance(child, dict):
            result[key] = {
                mapping.get(str(child_key), child_key): transform(child_value, mapping, relative, path + (key, str(child_key)))
                for child_key, child_value in child.items()
            }
            continue
        child_path = path + (key,)
        if key in PERSON_VALUE_FIELDS:
            result[key] = _map_value(child, mapping)
        elif key == "ids" and path[-2:] == ("scope", "people"):
            result[key] = _map_value(child, mapping)
        elif key == "id" and _is_person_record_id(child_path, relative):
            result[key] = _map_value(child, mapping)
        else:
            result[key] = transform(child, mapping, relative, child_path)
    return result


def migrate(root: Path = ROOT, *, apply: bool = False) -> dict[str, Any]:
    manifest = load_manifest(root)
    mapping = mapping_from_manifest(manifest)
    changed: list[str] = []
    missing: list[str] = []
    for relative in JSON_PATHS:
        path = root / relative
        if not path.is_file():
            missing.append(str(relative))
            continue
        before = read_json(path)
        after = transform(before, mapping, relative)
        if before != after:
            changed.append(str(relative))
            if apply:
                write_json(path, after)
    return {"changed": changed, "missing": missing, "mapping": mapping}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--apply", action="store_true", help="write the structured JSON migrations")
    args = parser.parse_args()
    result = migrate(args.root, apply=args.apply)
    action = "migrated" if args.apply else "would migrate"
    print(f"P-ID1 {action} {len(result['changed'])} JSON files")
    for path in result["changed"]:
        print(f"- {path}")
    if result["missing"]:
        print("missing optional inputs:")
        for path in result["missing"]:
            print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
