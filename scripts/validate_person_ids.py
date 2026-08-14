#!/usr/bin/env python3
"""Validate the P-ID1 opaque production Person ID migration."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping

from jsonschema import Draft202012Validator

try:
    from .migrate_person_ids import JSON_PATHS, PERSON_KEY_MAP_FIELDS, PERSON_VALUE_FIELDS, load_manifest
except ImportError:  # direct execution
    from migrate_person_ids import JSON_PATHS, PERSON_KEY_MAP_FIELDS, PERSON_VALUE_FIELDS, load_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = Path("data/migrations/person-id-canonicalization-v1.json")
SCHEMA_PATH = Path("schema/person-id-canonicalization.schema.json")
ALLOCATION_STATE_PATH = Path("data/derived/person-id-allocation-state.json")
WAVE1_PATH = Path("data/annotation/person-expansion-wave-1.json")
WAVE2_PATH = Path("data/annotation/person-expansion-wave-2.json")
PERSON_ID_RE = re.compile(r"^person-[0-9]{3}$")
PID1_IDS = {f"person-{index:03d}" for index in range(1, 18)}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_errors(root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = root / MANIFEST_PATH
    schema_path = root / SCHEMA_PATH
    try:
        schema = read_json(schema_path)
        document = read_json(manifest_path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"P-ID1 manifest/schema cannot be read: {exc}"]
    errors.extend(str(error.message) for error in Draft202012Validator(schema).iter_errors(document))
    try:
        loaded = load_manifest(root)
    except ValueError as exc:
        return errors + [str(exc)]
    records = loaded["records"]
    old_ids = {str(record["old_person_id"]) for record in records}
    new_ids = {str(record["new_person_id"]) for record in records}
    if len(old_ids) != 17:
        errors.append(f"P-ID1 old ID set is not a 17-ID set: {sorted(old_ids)}")
    if new_ids != PID1_IDS:
        errors.append("P-ID1 new ID set is not exactly person-001..person-017")
    if len(records) != 17 or len(old_ids) != 17 or len(new_ids) != 17:
        errors.append("P-ID1 manifest is not a 17-row bijection")
    return errors


def _production_people(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    try:
        people = read_json(root / "data/people.json").get("people", [])
    except (OSError, json.JSONDecodeError) as exc:
        return [], [f"data/people.json cannot be read: {exc}"]
    if not isinstance(people, list):
        return [], ["data/people.json.people is not a list"]
    ids = [item.get("person_id") for item in people if isinstance(item, Mapping)]
    if len(people) < 17:
        errors.append(f"production Person count is {len(people)}, below the frozen P-ID1 baseline")
    if len(ids) != len(set(ids)):
        errors.append("production Person IDs are not unique")
    expected_ids = {f"person-{index:03d}" for index in range(1, len(people) + 1)}
    if set(ids) != expected_ids:
        errors.append(f"production Person IDs are not contiguous person-001..person-{len(people):03d}: {sorted(ids)}")
    if any(not isinstance(value, str) or not PERSON_ID_RE.fullmatch(value) for value in ids):
        errors.append("production Person ID does not match ^person-[0-9]{3}$")
    manifest = read_json(root / MANIFEST_PATH)
    by_new = {record["new_person_id"]: record for record in manifest["records"]}
    for person in people:
        if not isinstance(person, Mapping):
            continue
        pid = person.get("person_id")
        record = by_new.get(pid)
        if record is not None and person.get("canonical_name") != record.get("canonical_name"):
            errors.append(f"canonical_name mismatch for {pid}")
    try:
        allocation = read_json(root / ALLOCATION_STATE_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"allocation state cannot be read: {exc}")
    else:
        allocations = allocation.get("allocations", [])
        allocation_by_id = {
            str(item.get("person_id")): item
            for item in allocations
            if isinstance(item, Mapping) and isinstance(item.get("person_id"), str)
        }
        if allocation.get("next_person_sequence") != len(people) + 1:
            errors.append("allocation state next_person_sequence does not follow the current registry")
        if set(allocation_by_id) != expected_ids or len(allocations) != len(people):
            errors.append("allocation state is not a complete current Person registry")
        for person in people:
            if not isinstance(person, Mapping):
                continue
            pid = str(person.get("person_id"))
            item = allocation_by_id.get(pid)
            if item is not None and item.get("canonical_name") != person.get("canonical_name"):
                errors.append(f"allocation canonical_name mismatch for {pid}")
        try:
            wave1 = read_json(root / WAVE1_PATH)
            wave2 = read_json(root / WAVE2_PATH)
            wave1_ids = [
                item.get("person_id")
                for item in sorted(wave1.get("members", []), key=lambda item: item.get("rank_at_selection", 0))
            ]
            wave2_ids = [
                item.get("person_id")
                for item in sorted(wave2.get("members", []), key=lambda item: item.get("rank_at_selection", 0))
            ]
            if wave1_ids != [f"person-{index:03d}" for index in range(8, 18)]:
                errors.append("Wave-1 allocation order is not person-008..person-017")
            if wave2_ids != [f"person-{index:03d}" for index in range(18, 18 + len(wave2_ids))]:
                errors.append("Wave-2 allocation does not begin at person-018 sequentially")
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            errors.append(f"expansion wave allocation metadata cannot be read: {exc}")
    return [dict(item) for item in people if isinstance(item, Mapping)], errors


def _map_fields(value: Any, *, field: str, relative: Path, path: tuple[str, ...], person_ids: set[str], old_ids: set[str], errors: list[str]) -> None:
    if field in PERSON_VALUE_FIELDS:
        values = value if isinstance(value, list) else [value]
        for item in values:
            if not isinstance(item, str):
                continue
            if item in old_ids:
                errors.append(f"legacy Person ID {item!r} remains in {relative}:{'.'.join(path)}")
            elif item not in person_ids:
                errors.append(f"unknown Person ID {item!r} in {relative}:{'.'.join(path)}")


def _structured_reference_errors(root: Path, person_ids: set[str], old_ids: set[str]) -> list[str]:
    errors: list[str] = []
    for relative in JSON_PATHS:
        path = root / relative
        if not path.is_file():
            continue
        try:
            document = read_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{relative} cannot be read: {exc}")
            continue

        def walk(value: Any, location: tuple[str, ...] = ()) -> None:
            if isinstance(value, Mapping):
                for key, child in value.items():
                    child_location = location + (str(key),)
                    _map_fields(child, field=str(key), relative=relative, path=child_location, person_ids=person_ids, old_ids=old_ids, errors=errors)
                    if str(key) in PERSON_KEY_MAP_FIELDS and isinstance(child, Mapping):
                        for person_key in child:
                            if person_key in old_ids:
                                errors.append(f"legacy Person ID {person_key!r} remains as a key in {relative}:{'.'.join(child_location)}")
                            elif person_key not in person_ids:
                                errors.append(f"unknown Person ID key {person_key!r} in {relative}:{'.'.join(child_location)}")
                    if str(key) == "id" and "people" in location:
                        _map_fields(child, field="person_id", relative=relative, path=child_location, person_ids=person_ids, old_ids=old_ids, errors=errors)
                    walk(child, child_location)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    walk(child, location + (str(index),))

        walk(document)
    return errors


def validate(root: Path = ROOT) -> list[str]:
    errors = _manifest_errors(root)
    people, people_errors = _production_people(root)
    errors.extend(people_errors)
    person_ids = {str(item.get("person_id")) for item in people}
    manifest = read_json(root / MANIFEST_PATH)
    old_ids = {str(record["old_person_id"]) for record in manifest.get("records", [])}
    errors.extend(_structured_reference_errors(root, person_ids, old_ids - {"person-007"}))
    return sorted(set(errors))


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = validate(args.root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("P-ID1 validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
