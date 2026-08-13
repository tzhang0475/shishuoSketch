from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.validate_frontend_artifact import generated_errors, sc1_generated_errors


ROOT = Path(__file__).resolve().parents[1]


class R20FrontendDataTests(unittest.TestCase):
    def test_vite_input_is_exactly_the_builder_derived_bundle(self) -> None:
        self.assertEqual(generated_errors(ROOT), [])

    def test_generated_bundle_contains_the_complete_story_reading_contract(self) -> None:
        bundle = json.loads(
            (ROOT / "site/src/generated/wp1-site.json").read_text(encoding="utf-8")
        )
        story = next(story for story in bundle["stories"] if story["id"] == "06-yaliang-019")
        reading = story["reading"]
        self.assertTrue(reading["main_text"]["original"])
        self.assertTrue(reading["main_text"]["simplified"])
        for key in (
            "relation_display",
            "evidence_display",
            "person_display",
            "mention_display",
            "source_display",
        ):
            self.assertTrue(reading[key])
        self.assertEqual(
            {relation["id"] for relation in bundle["relations"]},
            {
                "relation-001",
                "relation-gold-001",
                "relation-gold-002",
                "relation-gold-003",
                "relation-gold-004",
                "relation-gold-005",
                "relation-gold-006",
            },
        )

    def test_sc1_bundle_is_the_actual_frontend_input(self) -> None:
        self.assertEqual(sc1_generated_errors(ROOT), [])
        source = (ROOT / "site/src/data.ts").read_text(encoding="utf-8")
        self.assertIn('"./generated/sc1-site.json"', source)

    def test_frontend_loader_has_no_runtime_bundle_fetch(self) -> None:
        source = (ROOT / "site/src/data.ts").read_text(encoding="utf-8")
        self.assertNotIn("fetch(", source)
        self.assertNotIn("data/wp1-site.json", source)


if __name__ == "__main__":
    unittest.main()
