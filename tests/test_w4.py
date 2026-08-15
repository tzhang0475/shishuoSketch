from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.validate_w4 import validate as validate_w4


ROOT = Path(__file__).resolve().parents[1]


def read_json(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class W4StructuralTemporalExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.story_wave = read_json("data/annotation/story-expansion-wave-4.json")
        cls.person_wave = read_json("data/annotation/person-expansion-wave-4.json")
        cls.bundle = read_json("data/derived/sc1-site.json")
        cls.people = read_json("data/people.json")["people"]
        cls.links = read_json("data/derived/person-story-links.json")
        cls.anchors = read_json("data/annotation/story-temporal-anchors-h0a.json")["records"]
        cls.orientations = read_json("data/derived/e0-story-era-orientations.json")["records"]
        cls.identity = read_json("data/derived/w4-identity-coverage.json")
        cls.temporal = read_json("data/derived/w4-social-temporal-constraints.json")
        effective = read_json("data/derived/person-resolution-effective.json")
        cls.effective_mentions = [
            *effective.get("mentions", []),
            *effective.get("derived_mentions", []),
        ]

    def test_dedicated_validator_passes(self) -> None:
        self.assertEqual(validate_w4(ROOT), [])

    def test_w4_selection_is_frozen_and_in_scope(self) -> None:
        self.assertEqual(self.story_wave["selection_status"], "frozen")
        story_ids = [item["story_id"] for item in self.story_wave["records"]]
        self.assertGreaterEqual(len(story_ids), 45)
        self.assertLessEqual(len(story_ids), 75)
        self.assertEqual(len(story_ids), len(set(story_ids)))
        self.assertEqual(self.story_wave["expansion_story_ids"], story_ids)

    def test_new_people_use_opaque_ids_after_frozen_baseline(self) -> None:
        members = self.person_wave["members"]
        person_ids = [item["person_id"] for item in members]
        self.assertGreaterEqual(len(person_ids), 20)
        self.assertLessEqual(len(person_ids), 35)
        self.assertEqual(len(person_ids), len(set(person_ids)))
        self.assertTrue(all(int(value.split("-")[-1]) > 50 for value in person_ids))
        self.assertEqual(len(self.people), 50 + len(person_ids))
        self.assertTrue({f"person-{index:03d}" for index in range(1, 51)} <= {item["person_id"] for item in self.people})

    def test_every_new_story_has_temporal_and_era_projections(self) -> None:
        story_ids = {item["story_id"] for item in self.story_wave["records"]}
        anchors = {item["story_id"]: item for item in self.anchors}
        orientations = {item["story_id"]: item for item in self.orientations}
        bundle_stories = {item["id"]: item for item in self.bundle["stories"]}
        self.assertTrue(story_ids <= set(anchors))
        self.assertTrue(story_ids <= set(orientations))
        for story_id in story_ids:
            self.assertIn("primary_era_card_id", bundle_stories[story_id])
            self.assertTrue(bundle_stories[story_id]["primary_era_card_id"])

    def test_identity_publication_gate_has_no_unexpected_omission(self) -> None:
        self.assertEqual(self.identity["counts"]["unexpected_safe_omission"], 0)
        self.assertEqual(
            set(self.identity["scope"]["story_ids"]),
            {item["story_id"] for item in self.story_wave["records"]},
        )

    def test_social_temporal_projection_is_research_only(self) -> None:
        story_ids = {item["story_id"] for item in self.story_wave["records"]}
        self.assertEqual(
            {item["story_id"] for item in self.temporal["records"]},
            story_ids,
        )
        self.assertTrue(all("h0a_upgrade_candidate" in item for item in self.temporal["records"]))
        self.assertEqual(self.temporal["h0a_upgrade_candidate_count"], 0)

    def test_person_story_links_remain_one_edge_per_pair(self) -> None:
        pairs = {(item["person_id"], item["entry_id"]) for item in self.links["links"]}
        self.assertEqual(len(pairs), self.links["link_count"])
        self.assertEqual(self.links["reviewed_link_count"] + self.links["candidate_link_count"], self.links["link_count"])

    def _mention_rows(self, story_id: str, surface: str):
        return [
            item
            for item in self.effective_mentions
            if (item.get("entry_id") or item.get("source_id")) == story_id
            and item.get("surface") == surface
        ]

    def test_identity_hotfixes_remain_safe_after_expansion(self) -> None:
        yutaiwei = self._mention_rows("14-rongzhi-024", "庾太尉")
        self.assertTrue(yutaiwei)
        self.assertTrue(all(item.get("person_id") == "person-010" for item in yutaiwei))
        zhongrong = self._mention_rows("23-rendan-013", "仲容")
        self.assertTrue(zhongrong)
        self.assertFalse(any(item.get("person_id") == "person-037" for item in zhongrong))
        self.assertTrue(any(item.get("resolution_target", {}).get("canonical_name") == "阮咸" for item in zhongrong))
        shaogu = self._mention_rows("01-dexing-026", "少孤")
        self.assertFalse(any(item.get("person_id") == "person-032" for item in shaogu))

    def test_contextual_titles_are_not_global_aliases(self) -> None:
        bare_taiwei = [
            item for item in self.effective_mentions
            if item.get("surface") == "太尉" and item.get("person_id") == "person-010"
        ]
        bare_gong = [
            item for item in self.effective_mentions
            if item.get("surface") == "公" and item.get("person_id") == "person-010"
        ]
        self.assertFalse(bare_taiwei)
        self.assertFalse(bare_gong)

    def test_h0b_relation_and_scene_baselines_are_unchanged(self) -> None:
        relations = read_json("data/annotation/wp1-relations.json")["records"]
        self.assertEqual(sum(item.get("review_status") == "reviewed" for item in relations), 12)
        scene_count = sum(
            len(read_json(path)["records"])
            for path in (
                "data/annotation/story-scene-contexts.json",
                "data/annotation/story-scene-contexts-w3.json",
            )
        )
        self.assertEqual(scene_count, 44)


if __name__ == "__main__":
    unittest.main()
