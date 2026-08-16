from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.validate_sc1_frontend_data import validate_inline_mention_projection


ROOT = Path(__file__).resolve().parents[1]


class SC112UnifiedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = json.loads((ROOT / "data/derived/sc1-site.json").read_text(encoding="utf-8"))
        cls.mentions = {item["id"]: item for item in cls.bundle["mentions"]}
        cls.people = {item["id"] for item in cls.bundle["people"]}
        cls.app = (ROOT / "site/src/App.tsx").read_text(encoding="utf-8")

    def story(self, story_id: str) -> dict:
        return next(item for item in self.bundle["stories"] if item["id"] == story_id)

    @staticmethod
    def non_text_segments(segments: list[dict]) -> list[dict]:
        return [item for item in segments if item.get("type") != "text"]

    def test_all_canonical_annotation_blocks_are_projected_in_order(self) -> None:
        for story in self.bundle["stories"]:
            source_ids = [item["id"] for item in story["annotations"]]
            reading_ids = [item["id"] for item in story["reading"]["annotations"]]
            self.assertEqual(source_ids, reading_ids, story["id"])
            self.assertEqual(len(source_ids), len(story["reading"]["annotations"]), story["id"])
            for annotation in story["reading"]["annotations"]:
                self.assertTrue(annotation["original"])
                self.assertTrue(annotation["evidence_ids"], (story["id"], annotation["id"]))
                self.assertTrue(set(annotation["evidence_ids"]).issubset(story["evidence_ids"]))

    def test_25_paidiao_has_three_annotations_and_wang_ningzhi_is_annotation_only(self) -> None:
        story = self.story("25-paidiao-026")
        self.assertEqual(
            [item["id"] for item in story["reading"]["annotations"]],
            ["annotation-001", "annotation-002", "annotation-003"],
        )
        wang_id = "shishuo-25-paidiao-026-liu-annotation-004"
        main_mentions = {
            item["mention_id"]
            for item in self.non_text_segments(story["reading"]["main_text"]["segments"])
            if item.get("type") == "person_mention"
        }
        annotation_mentions = {
            item["mention_id"]
            for annotation in story["reading"]["annotations"]
            for item in self.non_text_segments(annotation["segments"])
            if item.get("type") == "person_mention"
        }
        self.assertNotIn(wang_id, main_mentions)
        self.assertIn(wang_id, annotation_mentions)
        self.assertEqual(self.mentions[wang_id]["section"], "liu_annotation")
        self.assertEqual(story["evidence_ids"][-3:], [
            "evidence-sc1-25-paidiao-026-annotation-001",
            "evidence-sc1-25-paidiao-026-annotation-002",
            "evidence-sc1-25-paidiao-026-annotation-003",
        ])

    def test_unpunctuated_annotation_fallback_is_explicit(self) -> None:
        story = self.story("25-paidiao-026")
        for annotation in story["reading"]["annotations"]:
            self.assertEqual(annotation["display_source"], "canonical_source")
            self.assertEqual(annotation["punctuation_status"], "unavailable")
            source = next(item for item in story["annotations"] if item["id"] == annotation["id"])
            self.assertEqual(annotation["original"], source["text"])
            self.assertEqual(annotation["insertion"]["status"], "safe")

    def test_reviewed_annotation_prefers_punctuated_reading(self) -> None:
        annotation = next(item for item in self.story("06-yaliang-019")["reading"]["annotations"] if item["id"] == "annotation-001")
        self.assertEqual(annotation["display_source"], "punctuation_record")
        self.assertEqual(annotation["punctuation_status"], "available")

    def test_inline_markers_reconstruct_without_changing_story_characters(self) -> None:
        for story in self.bundle["stories"]:
            main = story["reading"]["main_text"]
            self.assertEqual(
                "".join(item["display"]["original"] for item in main["segments"]),
                main["original"],
            )
            for marker in self.non_text_segments(main["segments"]):
                if marker.get("type") == "annotation_marker":
                    self.assertEqual(marker["display"], {"original": "", "simplified": ""})
                    self.assertIn(marker["annotation_id"], {item["id"] for item in story["reading"]["annotations"]})

    def test_safe_markers_are_only_created_from_safe_insertion_points(self) -> None:
        for story in self.bundle["stories"]:
            safe = {
                item["id"]
                for item in story["reading"]["annotations"]
                if item["insertion"]["status"] == "safe"
            }
            markers = {
                item["annotation_id"]
                for item in self.non_text_segments(story["reading"]["main_text"]["segments"])
                if item.get("type") == "annotation_marker"
            }
            self.assertEqual(markers, safe, story["id"])

    def test_existing_inline_projection_and_annotation_layers_validate(self) -> None:
        for story in self.bundle["stories"]:
            self.assertEqual(
                validate_inline_mention_projection(story, self.mentions, self.people),
                [],
                story["id"],
            )

    def test_courtesy_name_route_explanation_is_structured(self) -> None:
        story = self.story("02-yanyu-071")
        display = story["reading"]["mention_display"]["shishuo-02-yanyu-071-liu-annotation-003"]
        self.assertIn("叔平", display["explanation"]["original"])
        self.assertIn("王凝之的字", display["explanation"]["original"])
        self.assertEqual(display["alias_type"], "courtesy_name")

    def test_yanyu_071_she_taifu_surface_and_no_split_css_contract(self) -> None:
        story = self.story("02-yanyu-071")
        mention = next(
            item
            for item in story["reading"]["main_text"]["segments"]
            if item.get("mention_id") == "shishuo-02-yanyu-071-main-text-001"
        )
        self.assertEqual(mention["type"], "identity_mention")
        self.assertEqual(mention["display"]["simplified"], "谢太傅")
        self.assertIn("inline-identity-review", self.app)
        self.assertRegex(
            (ROOT / "site/src/styles.css").read_text(encoding="utf-8"),
            r"\.inline-identity-review > summary \{[^}]*white-space: nowrap;",
        )

    def test_contextual_office_title_stays_contextual(self) -> None:
        story = self.story("06-yaliang-019")
        display = story["reading"]["mention_display"]["shishuo-06-yaliang-019-liu-annotation-006"]
        self.assertIn("官职称谓", display["explanation"]["original"])
        self.assertNotIn("就是", display["explanation"]["original"])
        self.assertIn("上下文", display["explanation"]["original"])

    def test_mention_origin_route_is_one_exploration_state_not_duplicate_focus_state(self) -> None:
        self.assertIn("via_mention_id", self.app)
        self.assertIn("from_story_id", self.app)
        self.assertIn("MentionOriginExplanation", self.app)
        self.assertIn("type PersonFocus = (personId: string, route?: PersonMentionRoute)", self.app)
        self.assertNotIn("selectedMentionPersonId", self.app)
        self.assertNotIn("inlinePersonId", self.app)
        self.assertNotIn("mentionFocusedPerson", self.app)

    def test_annotation_marker_and_person_controls_are_distinct(self) -> None:
        self.assertIn("inline-annotation-marker", self.app)
        self.assertIn("inline-person-mention", self.app)
        self.assertIn("showAnnotationMarkers={false}", self.app)
        self.assertNotIn("indexOf(mention.surface)", self.app)

    def test_reading_mode_keeps_annotation_and_mention_ids_stable(self) -> None:
        for story in self.bundle["stories"]:
            original_ids = {
                item["mention_id"]
                for annotation in story["reading"]["annotations"]
                for item in annotation["segments"]
                if item.get("type") == "person_mention"
            }
            self.assertEqual(original_ids, {
                item["mention_id"]
                for annotation in story["reading"]["annotations"]
                for item in annotation["segments"]
                if item.get("type") == "person_mention"
            })
            self.assertEqual(
                [item["id"] for item in story["reading"]["annotations"]],
                [item["id"] for item in story["reading"]["annotations"]],
            )


if __name__ == "__main__":
    unittest.main()
