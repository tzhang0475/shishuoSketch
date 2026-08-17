from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from scripts.build_ux2_index import (
    PERSON_DERIVED_PATH,
    PERSON_PUBLIC_PATH,
    ROOT,
    STORY_DERIVED_PATH,
    STORY_PUBLIC_PATH,
    build_documents,
)
from scripts.validate_ux2 import validate


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class UX2IndexTests(unittest.TestCase):
    def test_validator_passes(self) -> None:
        self.assertEqual(validate(ROOT), [])

    def test_person_index_covers_exposed_people_exactly_once(self) -> None:
        sc1 = read(ROOT / "data/derived/sc1-site.json")
        index = read(ROOT / PERSON_DERIVED_PATH)
        expected = {
            row["id"] for row in sc1["people"]
            if row.get("scope_role") in {"primary", "supporting"} and row.get("scope") in {"primary", "supporting"}
        }
        ids = [row["person_id"] for row in index["records"]]
        self.assertEqual(set(ids), expected)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(index["count"], len(expected))

    def test_story_index_preserves_category_and_local_order(self) -> None:
        index = read(ROOT / STORY_DERIVED_PATH)
        by_category: dict[str, list[dict]] = {}
        for row in index["records"]:
            by_category.setdefault(row["category_id"], []).append(row)
            self.assertEqual(row["reference"]["simplified"].split(" · ")[-1], f"{row['category_number']:03d}")
        for rows in by_category.values():
            self.assertEqual([row["category_number"] for row in rows], sorted(row["category_number"] for row in rows))
        self.assertEqual(sum(len(rows) for rows in by_category.values()), 143)

    def test_public_and_derived_indexes_are_identical(self) -> None:
        self.assertEqual((ROOT / PERSON_DERIVED_PATH).read_bytes(), (ROOT / PERSON_PUBLIC_PATH).read_bytes())
        self.assertEqual((ROOT / STORY_DERIVED_PATH).read_bytes(), (ROOT / STORY_PUBLIC_PATH).read_bytes())

    def test_index_projection_is_deterministic(self) -> None:
        first = build_documents(ROOT)
        second = build_documents(ROOT)
        self.assertEqual(first, second)

    def test_index_is_runtime_fetched_and_reuses_existing_flow(self) -> None:
        app = (ROOT / "site/src/App.tsx").read_text(encoding="utf-8")
        loader = (ROOT / "site/src/indexData.ts").read_text(encoding="utf-8")
        self.assertIn('href={`${import.meta.env.BASE_URL}index`}', app)
        self.assertIn('target="_blank"', app)
        self.assertIn("loadUX2Index", app)
        self.assertIn("fetch(projectionUrl(name)", loader)
        self.assertIn("setStack([{ kind: \"story\", id: storyId }, { kind: \"person\", id: personId }])", app)
        self.assertIn("onStorySelect={selectStoryFromIndex}", app)
        self.assertNotIn('import "./generated/ux2', app)

    def test_rebuilding_projection_keeps_bytes_stable(self) -> None:
        before = {path: sha256(ROOT / path) for path in (PERSON_DERIVED_PATH, PERSON_PUBLIC_PATH, STORY_DERIVED_PATH, STORY_PUBLIC_PATH)}
        subprocess.run(["python3", "scripts/build_ux2_index.py"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        first = {path: sha256(ROOT / path) for path in before}
        subprocess.run(["python3", "scripts/build_ux2_index.py"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        second = {path: sha256(ROOT / path) for path in before}
        self.assertEqual(before, first)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
