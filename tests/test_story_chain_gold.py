from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.build_story_chain_gold import build
from scripts.validate_story_chain_gold import validate
from scripts.reading_layers import strip_display_punctuation
from scripts.build_six_person_pilot import parse_shishuo_sections
from opencc import OpenCC


ROOT = Path(__file__).resolve().parents[1]


def canonical_main(path: Path) -> str:
    return next(
        body.strip("\n")
        for section, body, _metadata in parse_shishuo_sections(path.read_text(encoding="utf-8"))
        if section == "main_text"
    )


class StoryChainGoldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gold = json.loads((ROOT / "data/story-chain-gold-set.json").read_text(encoding="utf-8"))
        self.chain = json.loads((ROOT / "data/derived/story-chain-gold-index.json").read_text(encoding="utf-8"))
        self.connectivity = json.loads((ROOT / "data/derived/story-chain-connectivity.json").read_text(encoding="utf-8"))
        self.links = json.loads((ROOT / "data/derived/person-story-links.json").read_text(encoding="utf-8"))["links"]
        self.people = {
            person["person_id"]: person
            for person in json.loads((ROOT / "data/people.json").read_text(encoding="utf-8"))["people"]
        }
        self.entries = {
            entry["id"]: entry
            for entry in json.loads((ROOT / "data/shishuo-corpus-index.json").read_text(encoding="utf-8"))["entries"]
        }
        self.punctuation = {
            record["entry_id"]: record
            for record in json.loads((ROOT / "data/annotation/wp1-punctuation.json").read_text(encoding="utf-8"))["records"]
        }
        self.reading = {
            record["entry_id"]: record
            for record in json.loads((ROOT / "data/derived/shishuo-reading-layer.json").read_text(encoding="utf-8"))["records"]
        }

    def test_gold_set_is_small_and_stable(self) -> None:
        ids = [record["entry_id"] for record in self.gold["records"]]
        self.assertEqual(len(ids), 16)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids, sorted(ids, key=lambda item: self.entries[item]["global_ordinal"]))
        self.assertIn("06-yaliang-019", ids)

    def test_selected_people_and_stories_resolve_from_existing_links(self) -> None:
        reviewed = [link for link in self.links if link["review_status"] == "reviewed"]
        by_entry = {}
        for link in reviewed:
            by_entry.setdefault(link["entry_id"], set()).add(link["person_id"])
        for record in self.gold["records"]:
            self.assertIn(record["entry_id"], self.entries)
            self.assertTrue(set(record["linked_person_ids"]).issubset(self.people))
            self.assertTrue(
                set(record["linked_person_ids"]).issubset(by_entry[record["entry_id"]])
            )

    def test_annotation_only_presence_is_not_promoted_to_main_text(self) -> None:
        anchor = next(item for item in self.chain["stories"] if item["entry_id"] == "06-yaliang-019")
        self.assertEqual(anchor["main_text_person_ids"], ["wang-xizhi"])
        self.assertEqual(set(anchor["liu_annotation_only_person_ids"]), {"person-007", "xi-jian"})
        annotation_bridge = next(item for item in self.chain["stories"] if item["entry_id"] == "06-yaliang-029")
        self.assertNotIn("wang-dao", annotation_bridge["main_text_person_ids"])
        self.assertIn("wang-dao", annotation_bridge["liu_annotation_only_person_ids"])

    def test_selected_reading_round_trip_and_opencc_are_deterministic(self) -> None:
        converter = OpenCC("t2s")
        for record in self.gold["records"]:
            entry = self.entries[record["entry_id"]]
            punctuation = self.punctuation[record["entry_id"]]
            reading = self.reading[record["entry_id"]]
            proposed = punctuation["sections"]["main_text"].get("punctuated_text")
            if proposed:
                canonical = canonical_main(ROOT / entry["path"])
                self.assertEqual(strip_display_punctuation(proposed), strip_display_punctuation(canonical))
                self.assertEqual(reading["main_text"]["simplified"], converter.convert(proposed))
            self.assertEqual(record["reading_layer_status"]["story_reader_ready"], reading["story_reader_ready"])

    def test_only_anchor_is_currently_reader_ready_and_new_items_remain_candidates(self) -> None:
        for record in self.gold["records"]:
            if record["entry_id"] == "06-yaliang-019":
                self.assertEqual(record["selection_status"], "gold_anchor")
                self.assertTrue(record["reading_layer_status"]["story_reader_ready"])
            else:
                self.assertEqual(record["selection_status"], "candidate_for_review")
                self.assertFalse(record["reading_layer_status"]["story_reader_ready"])

    def test_chain_index_exactly_projects_gold_set(self) -> None:
        gold_ids = [record["entry_id"] for record in self.gold["records"]]
        self.assertEqual([story["entry_id"] for story in self.chain["stories"]], gold_ids)
        refs = {item["person_id"]: item["entry_ids"] for item in self.chain["person_story_refs"]}
        expected = {}
        for story in self.chain["stories"]:
            for person_id in story["linked_person_ids"]:
                expected.setdefault(person_id, []).append(story["entry_id"])
        for person_id, entry_ids in expected.items():
            self.assertEqual(refs[person_id], sorted(entry_ids, key=lambda item: self.entries[item]["global_ordinal"]))

    def test_connectivity_is_one_component_without_relation_inference(self) -> None:
        self.assertEqual(self.connectivity["gold_set_count"], 16)
        self.assertEqual(self.connectivity["multi_person_story_count"], 4)
        self.assertEqual(self.connectivity["main_component_count"], 1)
        self.assertEqual(self.connectivity["unique_person_count"], 7)
        self.assertEqual(self.connectivity["covered_direct_relation_count"], 6)
        self.assertEqual(
            self.connectivity["covered_direct_relation_ids"],
            [
                "relation-gold-001",
                "relation-gold-002",
                "relation-gold-003",
                "relation-gold-004",
                "relation-gold-005",
                "relation-gold-006",
            ],
        )
        self.assertEqual(self.connectivity["covered_derived_relation_ids"], ["relation-001"])
        for record in self.gold["records"]:
            self.assertFalse(any(key.startswith("relation") for key in record))

    def test_sc0_validator_passes(self) -> None:
        self.assertEqual(validate(ROOT), [])

    def test_build_is_deterministic_and_preserves_person_story_inputs(self) -> None:
        input_paths = (
            ROOT / "data/derived/person-story-links.json",
            ROOT / "data/derived/person-story-index.json",
        )
        before = {path: path.read_bytes() for path in input_paths}
        output_paths = (
            ROOT / "data/story-chain-gold-set.json",
            ROOT / "data/derived/story-chain-gold-index.json",
            ROOT / "data/derived/story-chain-connectivity.json",
            ROOT / "docs/story-chain-gold-review.md",
        )
        first = build(ROOT)
        first_bytes = {path: path.read_bytes() for path in output_paths}
        second = build(ROOT)
        second_bytes = {path: path.read_bytes() for path in output_paths}
        self.assertEqual(first, second)
        self.assertEqual(first_bytes, second_bytes)
        self.assertEqual(before, {path: path.read_bytes() for path in input_paths})

    def test_reviewed_anchor_semantics_remain_unchanged(self) -> None:
        record = self.punctuation["06-yaliang-019"]
        self.assertEqual(record["status"], "reviewed")
        self.assertEqual(record["punctuation_basis"], "human_reviewed")
        self.assertTrue(self.reading["06-yaliang-019"]["story_reader_ready"])


if __name__ == "__main__":
    unittest.main()
