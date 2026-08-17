#!/usr/bin/env python3
"""Validate the UX2 Person/Story index projection contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

try:
    from .build_ux2_index import (
        PERSON_DERIVED_PATH,
        PERSON_PUBLIC_PATH,
        ROOT,
        SC1_PATH,
        STORY_DERIVED_PATH,
        STORY_PUBLIC_PATH,
        build_documents,
        stable_json,
    )
except ImportError:  # direct ``python3 scripts/validate_ux2.py`` execution
    from build_ux2_index import (  # type: ignore[no-redef]
        PERSON_DERIVED_PATH,
        PERSON_PUBLIC_PATH,
        ROOT,
        SC1_PATH,
        STORY_DERIVED_PATH,
        STORY_PUBLIC_PATH,
        build_documents,
        stable_json,
    )


BASELINE_PATH = Path("data/derived/ux1-frontend-size-baseline.json")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    paths = [
        SC1_PATH,
        BASELINE_PATH,
        PERSON_DERIVED_PATH,
        PERSON_PUBLIC_PATH,
        STORY_DERIVED_PATH,
        STORY_PUBLIC_PATH,
    ]
    for relative in paths:
        if not (root / relative).is_file():
            errors.append(f"missing UX2 artifact: {relative.as_posix()}")
    if errors:
        return errors

    sc1_path = root / SC1_PATH
    sc1 = read_json(sc1_path)
    baseline = read_json(root / BASELINE_PATH)
    baseline_sha = baseline.get("sc1_site", {}).get("sha256")
    if baseline_sha and sha256(sc1_path) != baseline_sha:
        errors.append("SC1 bundle differs from the protected UX1 baseline")

    documents = {
        "people": read_json(root / PERSON_DERIVED_PATH),
        "stories": read_json(root / STORY_DERIVED_PATH),
    }
    for kind, public_path in (("people", PERSON_PUBLIC_PATH), ("stories", STORY_PUBLIC_PATH)):
        derived_path = root / (PERSON_DERIVED_PATH if kind == "people" else STORY_DERIVED_PATH)
        public_path = root / public_path
        if derived_path.read_bytes() != public_path.read_bytes():
            errors.append(f"{kind} derived/public projections are not byte-identical")
        expected = build_documents(root)[kind]
        if documents[kind] != expected:
            errors.append(f"{kind} projection is not the deterministic SC1-derived result")
        if documents[kind].get("source_bundle", {}).get("sha256") != sha256(sc1_path):
            errors.append(f"{kind} source bundle hash is stale")
        if documents[kind].get("source_bundle", {}).get("path") != SC1_PATH.as_posix():
            errors.append(f"{kind} source path is not repository-relative")
        if documents[kind].get("projection") != "ux2_production_index":
            errors.append(f"{kind} projection label is invalid")
        if any(str(key).startswith("/") for key in json.dumps(documents[kind], ensure_ascii=False).split('"')):
            errors.append(f"{kind} projection contains an absolute-looking path")

    people = documents["people"].get("records", [])
    stories = documents["stories"].get("records", [])
    person_ids = [row.get("person_id") for row in people if isinstance(row, Mapping)]
    story_ids = [row.get("story_id") for row in stories if isinstance(row, Mapping)]
    if len(person_ids) != len(set(person_ids)):
        errors.append("Person index contains duplicate IDs")
    if len(story_ids) != len(set(story_ids)):
        errors.append("Story index contains duplicate IDs")
    sc1_people = {str(row.get("id")): row for row in sc1.get("people", []) if isinstance(row, Mapping)}
    sc1_stories = {str(row.get("id")): row for row in sc1.get("stories", []) if isinstance(row, Mapping)}
    expected_people = {
        person_id for person_id, row in sc1_people.items()
        if row.get("scope_role") in {"primary", "supporting"} and row.get("scope") in {"primary", "supporting"}
    }
    expected_stories = {
        story_id for story_id, row in sc1_stories.items()
        if row.get("publication_state") in {"production_ready", "preview_ready"} and row.get("title_source") != "candidate"
    }
    if set(person_ids) != expected_people:
        errors.append("Person index does not cover exactly the exposed SC1 Person IDs")
    if set(story_ids) != expected_stories:
        errors.append("Story index does not cover exactly the reader-ready SC1 Story IDs")
    if documents["people"].get("count") != len(expected_people):
        errors.append("Person count is inconsistent")
    if documents["stories"].get("count") != len(expected_stories):
        errors.append("Story count is inconsistent")

    for row in people:
        if not isinstance(row, Mapping) or set(row) != {"person_id", "name", "surname"}:
            errors.append(f"Person index row has unexpected fields: {row}")
            continue
        if not isinstance(row.get("name"), Mapping) or not isinstance(row.get("surname"), Mapping):
            errors.append(f"Person index row has incomplete display: {row.get('person_id')}")
    for row in stories:
        if not isinstance(row, Mapping):
            errors.append("Story index row is not an object")
            continue
        required = {"story_id", "category_id", "category", "category_number", "reference", "publication_state"}
        if set(row) != required:
            errors.append(f"Story index row has unexpected fields: {row.get('story_id')}")
            continue
        source = sc1_stories.get(str(row["story_id"]))
        if not source or row["category_number"] != source.get("ordinal"):
            errors.append(f"Story category-local number mismatch: {row.get('story_id')}")
        if row["publication_state"] not in {"production_ready", "preview_ready"}:
            errors.append(f"Story index includes non-reader-ready state: {row.get('story_id')}")

    serialized = json.dumps(documents, ensure_ascii=False)
    for forbidden in ("candidate_for_review", "unresolved", "annotation_only", "nl1", "s1"):
        if forbidden in serialized.lower():
            errors.append(f"UX2 index contains non-production marker: {forbidden}")
    if stable_json(documents["people"]) != (root / PERSON_DERIVED_PATH).read_text(encoding="utf-8"):
        errors.append("Person index serialization is not canonical")
    if stable_json(documents["stories"]) != (root / STORY_DERIVED_PATH).read_text(encoding="utf-8"):
        errors.append("Story index serialization is not canonical")
    return errors


def main() -> int:
    errors = validate(ROOT)
    if errors:
        for error in errors:
            print(f"UX2 validation failed: {error}")
        return 1
    documents = build_documents(ROOT)
    print(json.dumps({"status": "pass", "people": documents["people"]["count"], "stories": documents["stories"]["count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
