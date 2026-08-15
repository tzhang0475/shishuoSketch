from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_json(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class E0EraCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = read_json("data/derived/sc1-site.json")
        cls.people_registry = read_json("data/people.json")["people"]
        cls.identities = read_json("data/annotation/ruler-identities-e0.json")["records"]
        cls.cards = read_json("data/annotation/era-cards-e0.json")["records"]
        cls.audit = read_json("data/derived/e0-ruler-mention-audit.json")
        cls.metrics = read_json("data/derived/e0-metrics.json")
        cls.audit_by_story = {}
        for item in cls.audit["records"]:
            cls.audit_by_story.setdefault(item["story_id"], []).append(item)

    def test_ruler_namespace_is_separate_from_people(self) -> None:
        person_ids = {item["id"] for item in self.bundle["people"]}
        ruler_ids = {item["ruler_id"] for item in self.identities}
        self.assertTrue(ruler_ids)
        self.assertTrue(ruler_ids.isdisjoint(person_ids))
        self.assertEqual(
            {item["id"] for item in self.bundle["people"]},
            {item["person_id"] for item in self.people_registry},
        )

    def test_current_story_scope_is_audited_without_changing_story_set(self) -> None:
        story_ids = {item["id"] for item in self.bundle["stories"]}
        self.assertEqual(set(self.audit["scope"]["story_ids"]), story_ids)
        self.assertEqual(len(story_ids), len(self.bundle["stories"]))

    def test_pilot_cards_are_the_minimum_reviewed_ruler_set(self) -> None:
        resolved_card_rulers = {
            item["ruler_id"]
            for item in self.audit["records"]
            if item["resolution_status"] == "resolved" and item["era_card_exists"]
        }
        self.assertEqual({item["ruler_id"] for item in self.cards}, resolved_card_rulers)
        self.assertTrue(resolved_card_rulers)
        self.assertEqual(len({item["era_card_id"] for item in self.cards}), len(self.cards))
        for card in self.cards:
            self.assertLessEqual(card["reign_start_year"], card["reign_end_year"])
            self.assertTrue(card["era_names"])

    def test_direct_and_referenced_story_links_remain_distinct(self) -> None:
        story_links = {
            (card["ruler_id"], link["story_id"], link["link_type"])
            for card in self.cards
            for link in card["ruler_story_links"]
        }
        self.assertIn(("ruler-jin-wudi", "01-dexing-017", "appears"), story_links)
        self.assertIn(("ruler-jin-wudi", "02-yanyu-078", "referenced"), story_links)
        self.assertIn(("ruler-jin-yuandi", "05-fangzheng-023", "appears"), story_links)
        self.assertIn(("ruler-jin-mingdi", "05-fangzheng-023", "referenced"), story_links)
        self.assertIn(("ruler-jin-mingdi", "09-pinzao-014", "reign_context"), story_links)

    def test_ambiguous_imperial_titles_do_not_become_clickable(self) -> None:
        bare = [
            item
            for item in self.audit["records"]
            if item["story_id"] == "02-yanyu-078" and item["section"] == "liu_annotation" and item["surface"] == "武帝"
        ]
        self.assertEqual(len(bare), 1)
        self.assertNotEqual(bare[0]["resolution_status"], "resolved")
        self.assertFalse(bare[0]["era_card_exists"])
        another = [
            item
            for item in self.audit["records"]
            if item["story_id"] == "11-jiewu-005" and item["surface"] == "明帝"
        ]
        self.assertEqual(another[0]["resolution_status"], "ambiguous")

    def test_gold_ruler_mentions_project_once_and_keep_source_surface(self) -> None:
        ruler_mentions = {item["mention_id"]: item for item in self.bundle["ruler_mentions"]}
        placed = {}
        for story in self.bundle["stories"]:
            segments = list(story["reading"]["main_text"]["segments"])
            for annotation in story["reading"]["annotations"]:
                segments.extend(annotation["segments"])
            for segment in segments:
                if segment.get("type") == "ruler_mention":
                    placed[segment["mention_id"]] = placed.get(segment["mention_id"], 0) + 1
                    self.assertIn(segment["mention_id"], ruler_mentions)
        self.assertEqual(set(placed), set(ruler_mentions))
        self.assertTrue(all(count == 1 for count in placed.values()))
        for story_id, surface, ruler_id in (
            ("01-dexing-017", "武帝", "ruler-jin-wudi"),
            ("05-fangzheng-023", "元皇帝", "ruler-jin-yuandi"),
            ("09-pinzao-014", "明帝", "ruler-jin-mingdi"),
        ):
            matches = [item for item in ruler_mentions.values() if item["story_id"] == story_id and item["surface"] == surface]
            self.assertTrue(matches)
            self.assertTrue(all(item["ruler_id"] == ruler_id for item in matches))

    def test_person_intersections_are_story_derived_not_relations(self) -> None:
        self.assertEqual(len(self.bundle["relations"]), len(read_json("data/annotation/wp1-relations.json")["records"]))
        person_ids = {item["id"] for item in self.bundle["people"]}
        for card in self.cards:
            for intersection in card["person_intersections"]:
                self.assertIn(intersection["person_id"], person_ids)
                for story_id in intersection["story_ids"]:
                    story = next(item for item in self.bundle["stories"] if item["id"] == story_id)
                    self.assertIn(intersection["person_id"], story["person_ids"])

    def test_reader_projection_has_distinct_era_navigation(self) -> None:
        app = (ROOT / "site/src/App.tsx").read_text(encoding="utf-8")
        self.assertIn('type: "ruler_mention"', (ROOT / "site/src/types.ts").read_text(encoding="utf-8"))
        self.assertIn("onEraFocus", app)
        self.assertIn("EraCardDetail", app)
        self.assertIn("紀元", app)
        self.assertIn("focusedEraFromExploration", app)
        self.assertNotIn('person_id: segment.ruler_id', app)

    def test_identity_regressions_remain_untouched(self) -> None:
        mentions = self.bundle["mentions"]
        zhongrong = next(item for item in mentions if item.get("story_id") == "23-rendan-013" and item.get("surface") == "仲容")
        self.assertIsNone(zhongrong.get("person_id"))
        self.assertEqual(zhongrong.get("resolution_target", {}).get("canonical_name"), "阮咸")
        self.assertFalse(any(item.get("story_id") == "01-dexing-026" and item.get("surface") == "少孤" and item.get("person_id") == "person-032" for item in mentions))


if __name__ == "__main__":
    unittest.main()
