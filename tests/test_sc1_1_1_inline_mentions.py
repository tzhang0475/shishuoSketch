from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from scripts.reading_layers import strip_display_punctuation
from scripts.validate_sc1_frontend_data import validate_inline_mention_projection


ROOT = Path(__file__).resolve().parents[1]


class SC111InlineMentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = json.loads((ROOT / "data/derived/sc1-site.json").read_text(encoding="utf-8"))
        cls.mentions = {item["id"]: item for item in cls.bundle["mentions"]}
        cls.people = {item["id"] for item in cls.bundle["people"]}
        cls.app = (ROOT / "site/src/App.tsx").read_text(encoding="utf-8")
        cls.canonical_mentions = {
            item["mention_id"]: item
            for item in json.loads((ROOT / "data/mentions/shishuo.json").read_text(encoding="utf-8"))["mentions"]
            if item.get("mention_id") in cls.mentions
        }

    def story(self, story_id: str) -> dict:
        return next(item for item in self.bundle["stories"] if item["id"] == story_id)

    @staticmethod
    def person_segments(segments: list[dict]) -> list[dict]:
        return [item for item in segments if item.get("type") == "person_mention"]

    def test_all_display_segments_reconstruct_both_reading_modes(self) -> None:
        for story in self.bundle["stories"]:
            main = story["reading"]["main_text"]
            self.assertEqual("".join(item["display"]["original"] for item in main["segments"]), main["original"])
            self.assertEqual("".join(item["display"]["simplified"] for item in main["segments"]), main["simplified"])
            for annotation in story["reading"]["annotations"]:
                self.assertEqual(
                    "".join(item["display"]["original"] for item in annotation["segments"]),
                    annotation["original"],
                )
                self.assertEqual(
                    "".join(item["display"]["simplified"] for item in annotation["segments"]),
                    annotation["simplified"],
                )

    def test_main_text_mention_is_an_inline_segment_without_replacing_surface(self) -> None:
        story = self.story("02-yanyu-069")
        segments = self.person_segments(story["reading"]["main_text"]["segments"])
        alias_segments = [
            item
            for item in segments
            if item["mention_id"] == "shishuo-02-yanyu-069-main-text-001"
        ]
        self.assertEqual(len(alias_segments), 1)
        self.assertEqual(alias_segments[0]["display"]["original"], "王逸少")
        self.assertEqual(alias_segments[0]["person_id"], "person-001")

    def test_25_paidiao_wang_ningzhi_is_annotation_only_and_clickable_there(self) -> None:
        story = self.story("25-paidiao-026")
        mention_id = "shishuo-25-paidiao-026-liu-annotation-004"
        main_ids = {item["mention_id"] for item in self.person_segments(story["reading"]["main_text"]["segments"])}
        annotation = next(item for item in story["reading"]["annotations"] if item["id"] == "annotation-001")
        annotation_ids = {item["mention_id"] for item in self.person_segments(annotation["segments"])}
        self.assertNotIn(mention_id, main_ids)
        self.assertIn(mention_id, annotation_ids)
        self.assertEqual(self.mentions[mention_id]["section"], "liu_annotation")
        self.assertIn(
            "shishuo-25-paidiao-026-liu-annotation-003",
            {item["mention_id"] for item in story["reading"]["mention_projection"]["suppressed"]},
        )
        self.assertEqual(
            next(item for item in annotation["segments"] if item.get("type") == "person_mention")["display"]["original"],
            "王凝之",
        )

    def test_annotation_only_person_is_not_mislabeled_as_main_text(self) -> None:
        story = self.story("25-paidiao-026")
        errors = validate_inline_mention_projection(story, self.mentions, self.people)
        self.assertEqual(errors, [])
        wang = self.mentions["shishuo-25-paidiao-026-liu-annotation-004"]
        self.assertEqual(wang["section"], "liu_annotation")

    def test_unresolved_mentions_remain_ordinary_text(self) -> None:
        story = self.story("06-yaliang-019")
        unresolved = {
            item["id"]
            for item in self.bundle["mentions"]
            if item["story_id"] == story["id"] and item["person_id"] is None
        }
        rendered = {
            item["mention_id"]
            for item in self.person_segments(story["reading"]["main_text"]["segments"])
        }
        rendered.update(
            item["mention_id"]
            for annotation in story["reading"]["annotations"]
            for item in self.person_segments(annotation["segments"])
        )
        self.assertTrue(unresolved.isdisjoint(rendered))

    def test_projection_uses_same_semantic_mentions_in_both_modes(self) -> None:
        for story in self.bundle["stories"]:
            original_ids = {
                item["mention_id"]
                for item in self.person_segments(story["reading"]["main_text"]["segments"])
            }
            simplified_ids = original_ids.copy()
            for annotation in story["reading"]["annotations"]:
                annotation_ids = {
                    item["mention_id"]
                    for item in self.person_segments(annotation["segments"])
                }
                simplified_ids.update(annotation_ids)
            self.assertEqual(original_ids | {
                item["mention_id"]
                for annotation in story["reading"]["annotations"]
                for item in self.person_segments(annotation["segments"])
            }, simplified_ids)

    def test_simplified_display_changes_only_the_derived_segment_form(self) -> None:
        story = self.story("25-paidiao-026")
        segment = next(
            item
            for item in story["reading"]["main_text"]["segments"]
            if item.get("type") == "person_mention" and item["mention_id"].endswith("main-text-001")
        )
        self.assertEqual(segment["display"]["original"], "謝公")
        self.assertEqual(segment["display"]["simplified"], "谢公")
        self.assertEqual(segment["person_id"], "person-006")

    def test_duplicate_surfaces_use_distinct_anchored_segments(self) -> None:
        story = self.story("05-fangzheng-023")
        segments = [
            item
            for item in story["reading"]["main_text"]["segments"]
            if item.get("type") == "person_mention" and item["display"]["original"] == "丞相"
        ]
        self.assertEqual(
            [item["mention_id"] for item in segments],
            [
                "shishuo-05-fangzheng-023-main-text-001",
                "shishuo-05-fangzheng-023-main-text-002",
            ],
        )

    def test_segmented_original_text_preserves_canonical_characters(self) -> None:
        for story in self.bundle["stories"]:
            rendered = "".join(
                item["display"]["original"]
                for item in story["reading"]["main_text"]["segments"]
            )
            self.assertEqual(strip_display_punctuation(rendered), strip_display_punctuation(story["text"]))

    def test_canonical_mention_anchors_are_not_rewritten(self) -> None:
        for mention_id, mention in self.mentions.items():
            source = self.canonical_mentions.get(mention_id)
            if source is None:
                continue
            self.assertEqual(mention["anchor"], {
                "text": source["surface"],
                "section": source["section"],
                "offset": source["evidence"]["section_offset"],
            })

    def test_invalid_segment_reconstruction_is_rejected(self) -> None:
        story = deepcopy(self.story("02-yanyu-069"))
        story["reading"]["main_text"]["segments"][0]["display"]["original"] += "王"
        errors = validate_inline_mention_projection(story, self.mentions, self.people)
        self.assertTrue(any("segments do not reconstruct" in error for error in errors))

    def test_frontend_uses_build_time_segments_and_existing_focus_path(self) -> None:
        self.assertIn("InlineReadingSegments", self.app)
        self.assertIn("story.reading.main_text.segments", self.app)
        self.assertIn("annotation.segments", self.app)
        self.assertIn("onFocus(segment.person_id, { via_mention_id: segment.mention_id", self.app)
        self.assertNotIn("indexOf(mention.surface)", self.app)
        self.assertNotIn("inlineSelectedPersonId", self.app)
        self.assertNotIn("mentionPersonId", self.app)

    def test_summary_separates_main_text_and_liu_annotation_mentions(self) -> None:
        self.assertIn('uiLabel(data, "primary_story_label"', self.app)
        self.assertIn('uiLabel(data, "annotation_story_label"', self.app)
        self.assertIn('"story_people_heading"', self.app)


if __name__ == "__main__":
    unittest.main()
