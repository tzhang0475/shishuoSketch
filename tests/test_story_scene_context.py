from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from scripts.story_scene_contexts import DERIVED_PATH, SOURCE_PATH, derive_age_range, project, validate_source
from scripts.validate_sc1_frontend_data import validate
from tests.support import repository_validation_mode


ROOT = Path(__file__).resolve().parents[1]


class StorySceneContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = json.loads((ROOT / SOURCE_PATH).read_text(encoding="utf-8"))
        cls.derived = json.loads((ROOT / DERIVED_PATH).read_text(encoding="utf-8"))
        cls.bundle = json.loads((ROOT / "data/derived/sc1-site.json").read_text(encoding="utf-8"))

    def test_pilot_selection_is_small_and_includes_mandatory_story(self) -> None:
        ids = [record["story_id"] for record in self.source["records"]]
        self.assertGreaterEqual(len(ids), 3)
        self.assertLessEqual(len(ids), 5)
        self.assertIn("06-yaliang-029", ids)
        self.assertEqual(ids[0], "06-yaliang-029")

    def test_scene_contexts_resolve_only_published_stories_and_people(self) -> None:
        self.assertEqual(validate_source(ROOT), [])
        story_ids = {story["id"] for story in self.bundle["stories"]}
        people_ids = {person["id"] for person in self.bundle["people"]}
        self.assertTrue(set(self.derived["contexts"]).issubset(story_ids))
        for context in self.derived["contexts"].values():
            for person in context["people_at_scene"]:
                self.assertIn(person["person_id"], people_ids)
            self.assertEqual(context["review_status"], "candidate")

    def test_scene_claims_are_evidence_backed_and_ages_are_explicitly_unknown(self) -> None:
        evidence_ids = {item["id"] for item in self.bundle["evidence"]}
        for context in self.derived["contexts"].values():
            for evidence_id in context["evidence_ids"]:
                self.assertIn(evidence_id, evidence_ids)
            for person in context["people_at_scene"]:
                self.assertEqual(person["age"]["status"], "unknown")
                self.assertIsNone(person["age"]["start_year"])
                self.assertIsNone(person["age"]["end_year"])
                for evidence_id in person["evidence_ids"]:
                    self.assertIn(evidence_id, evidence_ids)
            for claim in context["event_background"]:
                self.assertTrue(claim["evidence_ids"])

    def test_age_derivation_preserves_exact_and_range_uncertainty(self) -> None:
        self.assertEqual(
            derive_age_range(372, 372, 320, 320),
            {"status": "exact", "start_year": 52, "end_year": 52},
        )
        self.assertEqual(
            derive_age_range(371, 372, 320, 322),
            {"status": "range", "start_year": 49, "end_year": 52},
        )
        self.assertEqual(
            derive_age_range(None, None, 320, 320),
            {"status": "unknown", "start_year": None, "end_year": None},
        )

    def test_mandatory_story_preserves_unmaterialized_wang_tanzhi(self) -> None:
        context = self.derived["contexts"]["06-yaliang-029"]
        self.assertEqual([person["person_id"] for person in context["people_at_scene"]], ["huan-wen", "xie-an"])
        self.assertEqual(
            [person["surface"]["original"] for person in context["unmaterialized_people"]],
            ["王坦之"],
        )
        self.assertEqual(context["places"][0]["name"]["original"], "新亭")
        self.assertTrue(any("簡文帝" in claim["text"]["original"] for claim in context["event_background"]))

    def test_scene_context_does_not_change_relation_layer(self) -> None:
        base = json.loads((ROOT / "data/derived/wp1-site.json").read_text(encoding="utf-8"))
        self.assertEqual(self.bundle["relations"], base["relations"])
        for context in self.source["records"]:
            self.assertNotIn("relation_ids", context)

    def test_sc1_validation_includes_scene_projection_in_repository_mode(self) -> None:
        mode = repository_validation_mode()
        self.assertEqual(validate(ROOT, mode=mode), [])
        if mode == "full":
            self.assertEqual(validate(ROOT, mode="portable"), [])

    def test_scene_projection_is_byte_stable(self) -> None:
        evidence_ids = {item["id"] for item in self.bundle["evidence"]}
        stories = {story["id"] for story in self.bundle["stories"] if story["publication_state"] != "blocked"}
        first = project(self.source, story_ids=stories, people=self.bundle["people"], evidence_ids=evidence_ids)
        second = project(self.source, story_ids=stories, people=self.bundle["people"], evidence_ids=evidence_ids)
        self.assertEqual(first, second)
        self.assertEqual(
            hashlib.sha256(json.dumps(first, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
            hashlib.sha256(json.dumps(second, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
