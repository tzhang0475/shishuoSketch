from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from scripts.reading_layers import (
    build_display_reading,
    effective_annotation_id,
    normalize_reader_whitespace,
    strip_display_punctuation,
)
from scripts.validate_sc1_frontend_data import validate_inline_mention_projection


ROOT = Path(__file__).resolve().parents[1]


class SC111InlineMentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = json.loads((ROOT / "data/derived/sc1-current-site.json").read_text(encoding="utf-8"))
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

    def test_fangzheng_025_reader_text_does_not_leak_physical_source_lines(self) -> None:
        story = self.story("05-fangzheng-025")
        main = story["reading"]["main_text"]
        rendered = "".join(item["display"]["original"] for item in main["segments"])

        self.assertNotRegex(rendered, r"[\r\n]")
        compact = strip_display_punctuation(rendered)
        for left, right in (("看", "新婦"), ("于時", "謝尚書"), ("我顧", "伊庾家"), ("我", "在遣女")):
            self.assertIn(left + right, compact)

        mention_index = next(
            index
            for index, item in enumerate(main["segments"])
            if item.get("mention_id") == "shishuo-05-fangzheng-025-main-text-001"
        )
        self.assertEqual(main["segments"][mention_index]["display"]["original"], "王右軍")
        self.assertIn("往謝家看新婦", main["segments"][mention_index + 1]["display"]["original"].replace(" ", ""))

        # The source/provenance representation remains diplomatic.  The
        # reader projection is the only layer normalized by this regression.
        entry = next(
            item
            for item in json.loads((ROOT / "data/shishuo-corpus-index.json").read_text(encoding="utf-8"))["entries"]
            if item["id"] == "05-fangzheng-025"
        )
        source_bytes = (ROOT / entry["path"]).read_bytes()
        self.assertIn("於是王右軍往謝家看\n新婦".encode("utf-8"), source_bytes)
        self.assertEqual(hashlib.sha256(source_bytes).hexdigest(), entry["entry_sha256"])
        self.assertEqual(story["text"].count("於是王右軍往謝家看\n新婦"), 1)

    def test_reading_projection_collapses_source_line_break_but_preserves_source_quote(self) -> None:
        class IdentityConverter:
            @staticmethod
            def convert(value: str) -> str:
                return value

        canonical = "於是王右軍往謝家看\n新婦猶有恢之遺法"
        mention = {
            "mention_id": "fixture-main-001",
            "entry_id": "fixture-story",
            "surface": "王右軍",
            "section": "main_text",
            "evidence": {"section_offset": canonical.index("王右軍")},
            "person_id": "person-001",
            "confidence": "high",
        }
        record = {
            "entry_id": "fixture-story",
            "status": "candidate",
            "id": "fixture-punctuation",
            "base_canonical_entry_sha256": "fixture",
            "sections": {
                "main_text": {"canonical_text": canonical, "punctuated_text": canonical},
                "liu_annotation": {},
            },
            "display_overrides": [],
        }
        reading = build_display_reading(
            record,
            IdentityConverter(),
            mentions=[mention],
            placement_mentions=[mention],
            evidence=[{"id": "fixture-evidence", "quote": "看\n新婦"}],
        )
        rendered = "".join(item["display"]["original"] for item in reading["main_text"]["segments"])
        self.assertEqual(rendered, "於是王右軍往謝家看 新婦猶有恢之遺法")
        self.assertNotRegex(rendered, r"[\r\n]")
        self.assertEqual(
            next(item for item in reading["main_text"]["segments"] if item.get("mention_id") == "fixture-main-001")["display"]["original"],
            "王右軍",
        )
        self.assertEqual(reading["evidence_display"]["fixture-evidence"]["original"], "看\n新婦")
        self.assertEqual(record["sections"]["main_text"]["canonical_text"], canonical)
        self.assertEqual(record["sections"]["main_text"]["punctuated_text"], canonical)
        self.assertEqual(normalize_reader_whitespace(canonical), "於是王右軍往謝家看 新婦猶有恢之遺法")

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

    def test_yanyu_036_uses_explicit_annotation_ownership_not_mention_ordinal(self) -> None:
        story = self.story("02-yanyu-036")
        mention_id = "shishuo-02-yanyu-036-liu-annotation-004"
        mention = self.mentions[mention_id]
        self.assertEqual(mention["surface"], "王丞相")
        self.assertEqual(mention["section"], "liu_annotation")
        annotation = next(item for item in story["reading"]["annotations"] if item["id"] == "annotation-003")
        target_segments = [item for item in annotation["segments"] if item.get("mention_id") == mention_id]
        self.assertEqual(len(target_segments), 1)
        self.assertEqual(target_segments[0]["type"], "identity_mention")
        self.assertEqual(target_segments[0]["annotation_id"], "annotation-003")
        self.assertEqual(target_segments[0]["resolution_status"], "candidate_for_review")
        annotation_four = next(item for item in story["reading"]["annotations"] if item["id"] == "annotation-004")
        self.assertFalse(any(item.get("mention_id") == mention_id for item in annotation_four["segments"]))

        canonical_mention = self.canonical_mentions[mention_id]
        without_metadata = deepcopy(canonical_mention)
        without_metadata.pop("source_section_metadata", None)
        self.assertEqual(
            effective_annotation_id(without_metadata, story["annotations"]),
            "annotation-003",
        )

    def test_all_visible_mentions_have_exactly_one_projection_or_suppression(self) -> None:
        visible = placed = suppressed = orphan = 0
        for story in self.bundle["stories"]:
            story_mentions = {
                mention_id: self.mentions[mention_id]
                for mention_id in story.get("mention_ids", [])
                if mention_id in self.mentions
            }
            placed_ids = {
                segment["mention_id"]
                for segment in [
                    *story["reading"]["main_text"]["segments"],
                    *[
                        segment
                        for annotation in story["reading"]["annotations"]
                        for segment in annotation["segments"]
                    ],
                ]
                if segment.get("type") in {"person_mention", "identity_mention"}
                and isinstance(segment.get("mention_id"), str)
            }
            suppressed_ids = {
                item["mention_id"]
                for item in story["reading"]["mention_projection"]["suppressed"]
                if isinstance(item.get("mention_id"), str)
            }
            visible_ids = {
                mention_id
                for mention_id, mention in story_mentions.items()
                if (
                    isinstance(mention.get("person_id"), str)
                    and mention.get("confidence") != "unresolved"
                ) or mention.get("resolution_status") in {"resolved", "candidate_for_review"}
            }
            visible += len(visible_ids)
            placed += len(visible_ids & placed_ids)
            suppressed += len(visible_ids & suppressed_ids)
            orphan += len(visible_ids - placed_ids - suppressed_ids)
            self.assertFalse(placed_ids & suppressed_ids, story["id"])
        self.assertEqual(orphan, 0)
        self.assertEqual(visible, placed + suppressed)

    def test_build_projection_derives_unique_annotation_block_without_id_suffix(self) -> None:
        class IdentityConverter:
            @staticmethod
            def convert(value: str) -> str:
                return value

        mention = {
            "mention_id": "fixture-liu-annotation-004",
            "entry_id": "fixture-story",
            "surface": "甲",
            "section": "liu_annotation",
            "evidence": {"section_offset": 0},
            "resolution_status": "candidate_for_review",
            "resolution_candidates": [{"target_kind": "identity_candidate", "canonical_name": "甲某", "candidate_id": "candidate-甲"}],
        }
        reading = build_display_reading(
            {
                "entry_id": "fixture-story",
                "status": "candidate",
                "id": "fixture-punctuation",
                "base_canonical_entry_sha256": "fixture",
                "sections": {
                    "main_text": {"canonical_text": "", "punctuated_text": ""},
                    "liu_annotation": {},
                },
                "display_overrides": [],
            },
            IdentityConverter(),
            mentions=[mention],
            placement_mentions=[mention],
            canonical_annotations=[
                {"id": "annotation-003", "text": "甲"},
                {"id": "annotation-004", "text": "乙"},
            ],
        )
        first = next(item for item in reading["annotations"] if item["id"] == "annotation-003")
        fourth = next(item for item in reading["annotations"] if item["id"] == "annotation-004")
        self.assertEqual(
            [item["mention_id"] for item in first["segments"] if item.get("type") == "identity_mention"],
            ["fixture-liu-annotation-004"],
        )
        self.assertFalse(any(item.get("mention_id") == "fixture-liu-annotation-004" for item in fourth["segments"]))
        self.assertFalse(reading["mention_projection"]["suppressed"])

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

    def test_yaliang_017_uses_maximal_person_spans_and_local_coreference(self) -> None:
        story = self.story("06-yaliang-017")
        segments = self.person_segments(story["reading"]["main_text"]["segments"])
        visible = [item["display"]["original"] for item in segments]
        self.assertIn("庾太尉", visible)
        self.assertIn("温太真", visible)
        self.assertEqual(visible.count("亮"), 2)
        self.assertNotIn("太真", visible)
        by_surface = {item["display"]["original"]: item for item in segments if item["display"]["original"] != "亮"}
        self.assertEqual(by_surface["庾太尉"]["person_id"], "person-010")
        self.assertEqual(by_surface["温太真"]["person_id"], "person-013")
        for item in segments:
            if item["display"]["original"] == "亮":
                mention = self.mentions[item["mention_id"]]
                self.assertEqual(mention["resolution_method"], "er1_1_story_local_coreference")
                self.assertEqual(mention["resolution_target"]["canonical_name"], "庾亮")

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
