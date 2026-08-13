from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.validate_sc1_frontend_data import validate
from tests.support import repository_validation_mode


ROOT = Path(__file__).resolve().parents[1]


class SC1StoryChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = json.loads((ROOT / "data/derived/sc1-site.json").read_text(encoding="utf-8"))
        cls.gold = json.loads((ROOT / "data/story-chain-gold-set.json").read_text(encoding="utf-8"))
        cls.base = json.loads((ROOT / "data/derived/wp1-site.json").read_text(encoding="utf-8"))

    def test_sc1_bundle_validates_and_publishes_exactly_the_sixteen_gold_stories(self) -> None:
        self.assertEqual(validate(ROOT, mode=repository_validation_mode()), [])
        expected = [item["entry_id"] for item in self.gold["records"]]
        self.assertEqual(self.bundle["story_chain"]["story_ids"], expected)
        self.assertEqual([item["id"] for item in self.bundle["stories"]], expected)

    def test_publication_state_does_not_change_editorial_punctuation_status(self) -> None:
        stories = {item["id"]: item for item in self.bundle["stories"]}
        punctuation = {
            item["entry_id"]: item
            for item in json.loads((ROOT / "data/annotation/wp1-punctuation.json").read_text(encoding="utf-8"))["records"]
        }
        self.assertEqual(stories["06-yaliang-019"]["publication_state"], "production_ready")
        self.assertEqual(punctuation["06-yaliang-019"]["review_status"], "reviewed")
        self.assertEqual(punctuation["06-yaliang-019"]["punctuation_basis"], "human_reviewed")
        for story in self.bundle["stories"]:
            if story["id"] == "06-yaliang-019":
                continue
            self.assertEqual(story["publication_state"], "preview_ready")
            self.assertEqual(punctuation[story["id"]]["review_status"], "unreviewed")
            self.assertEqual(punctuation[story["id"]]["punctuation_basis"], "reference_candidate")

    def test_person_story_projection_uses_sc0_links_and_separates_annotation_only(self) -> None:
        refs = {item["person_id"]: item for item in self.bundle["story_chain"]["person_story_refs"]}
        self.assertEqual(refs["wang-xizhi"]["story_ids"], [
            "02-yanyu-069", "04-wenxue-036", "06-yaliang-019", "19-xianyuan-026",
        ])
        self.assertEqual(refs["person-007"]["main_text_story_ids"], [])
        self.assertEqual(refs["person-007"]["liu_annotation_only_story_ids"], ["06-yaliang-019"])
        self.assertIn("25-paidiao-026", refs["xie-daoyun"]["liu_annotation_only_story_ids"])

    def test_shared_wp1_person_relation_source_records_are_unchanged(self) -> None:
        for key in ("people", "relations", "sources", "eras"):
            self.assertEqual(self.bundle[key], self.base[key], key)
        self.assertEqual(
            {item["id"] for item in self.bundle["relations"]},
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

    def test_story_and_person_navigation_contract_is_data_driven(self) -> None:
        app = (ROOT / "site/src/App.tsx").read_text(encoding="utf-8")
        self.assertIn("appendExploration", app)
        self.assertIn("backExploration", app)
        self.assertIn("PersonStories", app)
        self.assertIn("story_chain?.person_story_refs", app)
        self.assertNotIn("25-paidiao-026", app)
        self.assertNotIn("王羲之", app)

    def test_r2_relation_basis_remains_direct_vs_derived(self) -> None:
        relations = {item["id"]: item for item in self.bundle["relations"]}
        direct = [item for item in relations.values() if item["review_status"] == "reviewed" and item["relation_basis"] == "direct"]
        self.assertEqual(len(direct), 6)
        self.assertEqual(relations["relation-001"]["relation_basis"], "derived")
        self.assertEqual(relations["relation-001"]["derived_from_relation_ids"], ["relation-gold-006", "relation-gold-005"])


if __name__ == "__main__":
    unittest.main()
