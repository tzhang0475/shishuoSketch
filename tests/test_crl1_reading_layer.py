from __future__ import annotations

import json
from pathlib import Path
import unittest

from opencc import OpenCC

from scripts.build_shishuo_reading_layer import (
    _machine_punctuation_basis,
    build,
    classify_alignment,
    punctuation_from_reference,
)
from scripts.build_six_person_pilot import parse_shishuo_sections
from scripts.reading_layers import strip_display_punctuation, validate_punctuation_round_trip
from scripts.validate_shishuo_reading_layer import validate_reading_layer


ROOT = Path(__file__).resolve().parents[1]


def canonical_main(path: Path) -> str:
    return next(
        body.strip("\n")
        for section, body, _metadata in parse_shishuo_sections(path.read_text(encoding="utf-8"))
        if section == "main_text"
    )


class CRL1ReadingLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.index = json.loads((ROOT / "data/shishuo-corpus-index.json").read_text(encoding="utf-8"))
        self.punctuation = json.loads(
            (ROOT / "data/annotation/wp1-punctuation.json").read_text(encoding="utf-8")
        )
        self.derived = json.loads(
            (ROOT / "data/derived/shishuo-reading-layer.json").read_text(encoding="utf-8")
        )

    def test_all_1130_entries_are_represented(self) -> None:
        expected = [entry["id"] for entry in self.index["entries"]]
        actual = [record["entry_id"] for record in self.derived["records"]]
        self.assertEqual(actual, expected)
        self.assertEqual(len(self.punctuation["records"]), 1130)

    def test_available_punctuation_round_trips_for_every_entry(self) -> None:
        index_by_id = {entry["id"]: entry for entry in self.index["entries"]}
        for record in self.punctuation["records"]:
            entry = index_by_id[record["entry_id"]]
            canonical = canonical_main(ROOT / entry["path"])
            errors = validate_punctuation_round_trip(
                record,
                {"main_text": canonical},
                section_names=("main_text",),
                allow_missing_punctuated=True,
            )
            self.assertEqual(errors, [], record["entry_id"])

    def test_character_insertion_deletion_and_variant_are_rejected(self) -> None:
        canonical = {"main_text": "甲乙"}
        valid = {"id": "test", "sections": {"main_text": {"canonical_text": "甲乙", "punctuated_text": "甲，乙"}}}
        self.assertEqual(
            validate_punctuation_round_trip(valid, canonical, section_names=("main_text",)), []
        )
        for punctuated in ("甲，乙丙", "甲", "甲，丙"):
            mutated = {"id": "test", "sections": {"main_text": {"canonical_text": "甲乙", "punctuated_text": punctuated}}}
            errors = validate_punctuation_round_trip(mutated, canonical, section_names=("main_text",))
            self.assertTrue(any("round-trip" in error for error in errors), punctuated)

    def test_exact_alignment_requires_two_punctuation_references_for_aligned(self) -> None:
        converter = OpenCC("t2s")
        reference = {"characters": "甲乙", "punctuation": [{"offset": 1, "text": "。"}]}
        self.assertEqual(classify_alignment("甲乙", reference, converter)["status"], "candidate")
        self.assertEqual(
            classify_alignment(
                "甲乙", reference, converter, punctuation_reference_count=2
            )["status"],
            "aligned",
        )

    def test_punctuation_boundary_disagreement_is_not_aligned(self) -> None:
        converter = OpenCC("t2s")
        reference = {"characters": "甲乙丙", "punctuation": []}
        result = classify_alignment(
            "甲乙丙",
            reference,
            converter,
            punctuation_reference_count=2,
            punctuation_boundaries=((1,), (2,)),
        )
        self.assertEqual(result["status"], "disputed")
        self.assertIn("punctuation_boundary_disagreement", result["reason_codes"])

    def test_length_mismatch_and_missing_reference_are_disputed(self) -> None:
        converter = OpenCC("t2s")
        mismatch = classify_alignment("甲乙丙", {"characters": "甲乙", "punctuation": []}, converter)
        missing = classify_alignment("甲乙", None, converter)
        self.assertEqual(mismatch["status"], "disputed")
        self.assertEqual(missing["status"], "disputed")

    def test_reviewed_baseline_is_preserved_and_reader_ready(self) -> None:
        record = next(item for item in self.punctuation["records"] if item["entry_id"] == "06-yaliang-019")
        derived = next(item for item in self.derived["records"] if item["entry_id"] == "06-yaliang-019")
        self.assertEqual(record["id"], "punctuation-06-yaliang-019")
        self.assertEqual(record["status"], "reviewed")
        self.assertTrue(derived["story_reader_ready"])
        self.assertEqual(derived["automatic_comparison"]["status"], "disputed")

    def test_crl1_1_separates_review_status_and_punctuation_basis(self) -> None:
        reviewed = next(item for item in self.punctuation["records"] if item["entry_id"] == "06-yaliang-019")
        self.assertEqual(reviewed["review_status"], "reviewed")
        self.assertEqual(reviewed["punctuation_basis"], "human_reviewed")
        candidates = [item for item in self.punctuation["records"] if item["review_status"] == "unreviewed"]
        self.assertTrue(candidates)
        self.assertTrue(all(item["punctuation_basis"] != "human_reviewed" for item in candidates))

    def test_crl1_1_exact_transfer_is_distinct_from_publication_trust(self) -> None:
        exact = [
            item for item in self.punctuation["records"]
            if item.get("exact_transfer") is True
        ]
        self.assertEqual(len(exact), 348)
        self.assertTrue(all(item["punctuation_basis"] == "reference_candidate" for item in exact))
        self.assertTrue(all(item["review_status"] == "unreviewed" for item in exact))
        self.assertTrue(
            all(
                not item.get("story_reader_ready", False)
                for item in self.derived["records"]
                if item["entry_id"] != "06-yaliang-019"
            )
        )

    def test_crl1_1_bucket_projection_is_complete_and_mutually_consistent(self) -> None:
        queue = json.loads(
            (ROOT / "data/derived/punctuation-review-queue.json").read_text(encoding="utf-8")
        )
        self.assertEqual(queue["entry_count"], 1130)
        self.assertEqual(queue["bucket_counts"], {
            "A_trusted_reference_ready": 1,
            "B_exact_transfer_awaiting_source_qualification": 348,
            "C_punctuation_review_candidate": 721,
            "D_disputed_structural_review": 60,
        })
        self.assertEqual(len({item["entry_id"] for item in queue["records"]}), 1130)

    def test_crl1_1_source_qualification_is_provisional(self) -> None:
        qualification = json.loads(
            (ROOT / "data/reading-source-qualification.json").read_text(encoding="utf-8")
        )["records"][0]
        self.assertEqual(qualification["qualification"], "provisionally_qualified")
        self.assertFalse(qualification["allows_trusted_reference_promotion"])

    def test_crl1_1_source_qualification_controls_publication_basis(self) -> None:
        provisional = {
            "qualification": "provisionally_qualified",
            "allows_trusted_reference_promotion": False,
        }
        qualified = {
            "qualification": "qualified",
            "allows_trusted_reference_promotion": True,
        }
        self.assertEqual(
            _machine_punctuation_basis(status="candidate", exact_transfer=True, qualification=provisional),
            "reference_candidate",
        )
        self.assertEqual(
            _machine_punctuation_basis(status="candidate", exact_transfer=True, qualification=qualified),
            "trusted_reference_exact",
        )

    def test_crl1_1_disputed_records_are_not_promoted(self) -> None:
        disputed = [item for item in self.punctuation["records"] if item["status"] == "disputed"]
        self.assertEqual(len(disputed), 60)
        self.assertTrue(all(item["punctuation_basis"] == "disputed" for item in disputed))
        self.assertTrue(all(item["review_status"] == "unreviewed" for item in disputed))

    def test_simplified_reading_is_deterministic(self) -> None:
        converter = OpenCC("t2s")
        for record in self.derived["records"]:
            original = record["main_text"]["original"]
            simplified = record["main_text"]["simplified"]
            if original is not None:
                self.assertEqual(converter.convert(original), simplified, record["entry_id"])

    def test_review_queue_exactly_matches_non_ready_records(self) -> None:
        import yaml

        queue = yaml.safe_load(
            (ROOT / "content/curated/shishuo/reading-layer/review-queue.yaml").read_text(encoding="utf-8")
        )
        expected = {
            record["entry_id"]
            for record in self.derived["records"]
            if record["punctuation_basis"] in {"reference_candidate", "disputed"}
            and not (
                record["punctuation_basis"] == "reference_candidate"
                and record["exact_transfer"] is True
            )
        }
        self.assertEqual({record["entry_id"] for record in queue["records"]}, expected)

    def test_crl1_validator_passes(self) -> None:
        self.assertEqual(validate_reading_layer(ROOT, mode="full"), [])

    def test_build_is_deterministic(self) -> None:
        before = {
            path: (ROOT / path).read_bytes()
            for path in (
                "data/annotation/wp1-punctuation.json",
                "data/derived/shishuo-reading-layer.json",
                "content/curated/shishuo/reading-layer/review-queue.yaml",
                "content/curated/shishuo/reading-layer/review-queue.md",
                "docs/corpus-reading-layer-audit.md",
                "data/derived/punctuation-review-queue.json",
                "docs/crl1-1-punctuation-qualification-sample.md",
            )
        }
        first = build(ROOT)
        after_first = {
            path: (ROOT / path).read_bytes()
            for path in before
        }
        second = build(ROOT)
        after_second = {
            path: (ROOT / path).read_bytes()
            for path in before
        }
        self.assertEqual(first, second)
        self.assertEqual(after_first, after_second)
        self.assertEqual(after_first["data/derived/shishuo-reading-layer.json"], before["data/derived/shishuo-reading-layer.json"])

    def test_protected_hash_scope_is_explicit_and_reproducible(self) -> None:
        document = json.loads(
            (ROOT / "data/derived/protected-hash-scopes.json").read_text(encoding="utf-8")
        )
        scopes = {item["name"]: item for item in document["scopes"]}
        self.assertEqual(scopes["canonical-processed-shishuo-jinshu"]["file_count"], 2124)
        self.assertEqual(scopes["historical-wp1-baseline-processed-shishuo-jinshu"]["file_count"], 1396)
        self.assertTrue(document["comparisons"]["working_tree_equals_head_same_scope"])
        self.assertTrue(document["comparisons"]["shishuo_unchanged_since_baseline"])

    def test_punctuation_transfer_preserves_canonical_sequence(self) -> None:
        output = punctuation_from_reference("甲乙丙", [{"offset": 1, "text": "，"}, {"offset": 3, "text": "。"}])
        self.assertEqual(strip_display_punctuation(output), "甲乙丙")


if __name__ == "__main__":
    unittest.main()
