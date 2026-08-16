from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from scripts.validate_x1_2a import validate
from scripts.x1_2a_common import (
    CANONICAL_FACTS_PATH,
    FACT_REVIEW_PATH,
    MATERIALIZATION_PATH,
    ONTOLOGY_REVIEW_PATH,
    PERSON_REVIEW_PATH,
    REVIEW_MANIFEST_PATH,
    STORY_REVIEW_PATH,
    SUMMARY_PATH,
    all_production_ids,
    read,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = (
    REVIEW_MANIFEST_PATH,
    STORY_REVIEW_PATH,
    PERSON_REVIEW_PATH,
    FACT_REVIEW_PATH,
    ONTOLOGY_REVIEW_PATH,
    MATERIALIZATION_PATH,
    CANONICAL_FACTS_PATH,
    Path("data/derived/x1-2a-conflict-audit.json"),
    Path("data/derived/x1-2a-gap-audit.json"),
    Path("data/derived/x1-2a-realized-yield.json"),
    Path("data/derived/x1-2a-counter-model-audit.json"),
    Path("data/derived/x1-2a-bias-audit.json"),
    Path("data/derived/x1-2a-next-epoch-recommendation.json"),
    SUMMARY_PATH,
)


def load(relative: str | Path):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class X12AContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.review = load(REVIEW_MANIFEST_PATH)
        cls.stories = load(STORY_REVIEW_PATH)["records"]
        cls.persons = load(PERSON_REVIEW_PATH)["records"]
        cls.facts = load(FACT_REVIEW_PATH)["records"]
        cls.ontology = load(ONTOLOGY_REVIEW_PATH)
        cls.materialization = load(MATERIALIZATION_PATH)
        cls.extension = load(CANONICAL_FACTS_PATH)
        cls.summary = load(SUMMARY_PATH)

    def test_all_candidate_classes_have_complete_terminal_review(self) -> None:
        self.assertEqual(self.review["counts"]["story_candidate_count"], 20)
        self.assertEqual(self.review["counts"]["person_identity_candidate_count"], 8)
        self.assertEqual(self.review["counts"]["fact_candidate_count"], 88)
        self.assertEqual(self.review["counts"]["ontology_gap_candidate_count"], 7)
        for rows in (self.stories, self.persons, self.facts, self.ontology["records"]):
            self.assertTrue(rows)
            for row in rows:
                self.assertIn(row["review_status"], {"accepted", "unresolved", "rejected"})
                self.assertTrue(row["review_reason"])

    def test_selection_is_frozen_and_story_gate_blocks_production_additions(self) -> None:
        self.assertTrue(self.review["selection_frozen_before_review"])
        self.assertTrue(self.review["research_selection_provenance_only"])
        self.assertEqual(self.review["counts"]["story_review_status"], {"unresolved": 20})
        self.assertEqual(self.materialization["counts"]["stories_added"], 0)
        self.assertEqual(self.materialization["counts"]["persons_added"], 0)
        self.assertEqual(self.materialization["canonical_story_additions"], [])

    def test_only_reviewed_facts_materialize_and_retain_evidence(self) -> None:
        accepted = {row["review_item_id"] for row in self.facts if row["review_status"] == "accepted"}
        self.assertEqual(len(accepted), 7)
        self.assertEqual(self.materialization["counts"]["facts_added"], 9)
        self.assertEqual(len(self.extension["fact_index"]), 9)
        for row in self.extension["fact_index"]:
            self.assertTrue(set(row["evidence_ids"]))
            self.assertTrue(set(row["evidence_ids"]) <= {
                ref["evidence_id"]
                for ref in row["evidence_refs"]
                if ref["valid"]
            })
            self.assertIn(row["provenance_refs"][0]["review_item_id"], accepted)
            self.assertNotIn("selection_score", json.dumps(row, ensure_ascii=False))
            self.assertNotIn("model_score", json.dumps(row, ensure_ascii=False))

    def test_temporal_and_semantic_safeguards_remain_conservative(self) -> None:
        facts = self.extension["fact_index"]
        office = next(row for row in facts if row["fact_type"] == "office_tenure")
        self.assertEqual(office["temporal_precision"], "unknown")
        self.assertIsNone(office["start_year_ce"])
        self.assertIsNone(office["end_year_ce"])
        event_contexts = [row for row in facts if row["fact_type"] == "event_story_context"]
        self.assertEqual(len(event_contexts), 4)
        self.assertTrue(all(row["hard_temporal_eligible"] is False for row in event_contexts))
        self.assertTrue(all(row["person_participation_created"] is False for row in event_contexts))
        self.assertEqual(self.ontology["ontology_change_count"], 0)

    def test_selection_channel_provenance_and_realized_yield_are_separate(self) -> None:
        channels = self.summary["realized_yield"]
        self.assertEqual(set(channels), {"graph_guided", "coverage_guided", "stratified_random", "counter_model"})
        self.assertEqual(channels["graph_guided"]["canonical_facts"], 2)
        self.assertEqual(channels["coverage_guided"]["canonical_facts"], 5)
        self.assertEqual(channels["stratified_random"]["canonical_facts"], 2)
        self.assertEqual(channels["counter_model"]["canonical_facts"], 0)
        for row in self.extension["fact_index"]:
            provenance = row["provenance_refs"][0]
            self.assertIn(provenance["selection_mode"], {"graph_guided", "coverage_guided", "stratified_random", "counter_model"})
            self.assertEqual(provenance["selection_epoch"], "X1.1")

    def test_no_new_person_and_protected_production_scope(self) -> None:
        people, stories = all_production_ids()
        self.assertEqual(len(people), 75)
        self.assertEqual(len(stories), 143)
        self.assertEqual(self.materialization["canonical_person_additions"], [])
        self.assertEqual(self.materialization["canonical_story_additions"], [])

    def test_validator_and_output_snapshot_are_reproducible(self) -> None:
        self.assertEqual(validate(), [])
        snapshots = {}
        for path in OUTPUTS:
            absolute = ROOT / path
            self.assertTrue(absolute.is_file(), path)
            snapshots[str(path)] = hashlib.sha256(absolute.read_bytes()).hexdigest()
        for path in OUTPUTS:
            self.assertEqual(snapshots[str(path)], sha256_file(path), path)


if __name__ == "__main__":
    unittest.main()
