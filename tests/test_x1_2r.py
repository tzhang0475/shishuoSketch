from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

from tests.support import skip_if_portable_payload_missing


ROOT = Path(__file__).resolve().parents[1]
SELECTED_PATH = ROOT / "data/derived/x1-1-selection-manifest.json"
OUTPUTS = (
    "data/derived/x1-2r-jianshu-evidence-bundles.json",
    "data/derived/x1-2r-participant-review.json",
    "data/derived/x1-2r-identity-review.json",
    "data/derived/x1-2r-fact-reopen-manifest.json",
    "data/derived/x1-2r-fact-review.json",
    "data/derived/x1-2r-citation-candidates.json",
    "data/derived/x1-2r-conflict-audit.json",
    "data/derived/x1-2r-canonical-extension.json",
    "data/derived/x1-2r-materialization-manifest.json",
    "data/derived/x1-2r-realized-yield.json",
    "data/derived/x1-2r-channel-audit.json",
    "data/derived/x1-2r-summary.json",
)


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class X12RTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.selected = [row["story_id"] for row in load("data/derived/x1-1-selection-manifest.json")["records"]]
        cls.bundles = load("data/derived/x1-2r-jianshu-evidence-bundles.json")
        cls.participant = load("data/derived/x1-2r-participant-review.json")
        cls.identity = load("data/derived/x1-2r-identity-review.json")
        cls.reopen = load("data/derived/x1-2r-fact-reopen-manifest.json")
        cls.facts = load("data/derived/x1-2r-fact-review.json")
        cls.citations = load("data/derived/x1-2r-citation-candidates.json")
        cls.extension = load("data/derived/x1-2r-canonical-extension.json")
        cls.materialization = load("data/derived/x1-2r-materialization-manifest.json")
        cls.summary = load("data/derived/x1-2r-summary.json")

    def test_exact_frozen_scope_and_no_new_selection(self) -> None:
        self.assertEqual(len(self.selected), 20)
        selected = set(self.selected)
        self.assertEqual(set(self.bundles["scope"]["selected_story_ids"]), selected)
        self.assertEqual({row["story_id"] for row in self.participant["records"]}, selected)
        self.assertFalse(self.bundles["scope"]["new_story_selection_performed"])
        self.assertFalse(self.summary["scope"]["new_story_selection_performed"])
        production = set(row["id"] for row in load("data/derived/sc1-site.json")["stories"])
        self.assertTrue(selected.isdisjoint(production))

    def test_source_layers_and_locators_remain_separate(self) -> None:
        layers = {"base_text", "liu_annotation", "jianshu_note", "collation_note", "other_scholar_note"}
        for story in self.bundles["records"]:
            self.assertEqual(set(story["blocks"]) , layers)
            for layer, blocks in story["blocks"].items():
                for block in blocks:
                    self.assertEqual(block["layer"], layer)
                    self.assertTrue(block["source_locator"])
                    self.assertTrue(block["text_sha256"])
        self.assertTrue(any(story["blocks"]["liu_annotation"] for story in self.bundles["records"]))
        self.assertTrue(any(story["blocks"]["jianshu_note"] for story in self.bundles["records"]))
        self.assertTrue(any(story["blocks"]["collation_note"] for story in self.bundles["records"]))

    def test_all_participants_reviewed_and_annotation_only_is_not_hard(self) -> None:
        self.assertEqual(self.participant["counts"]["stories_reviewed"], 20)
        for story in self.participant["records"]:
            for row in story["all_reviewed_surfaces"]:
                self.assertEqual(row["review_status"], "reviewed")
                if row["role"] == "annotation_only":
                    self.assertFalse(row["hard_participation"])
                if row["hard_participation"]:
                    self.assertEqual(row["source_section"], "main_text")
            self.assertIn(story["participant_gate"], {"pass", "unresolved"})
        self.assertEqual(self.participant["counts"]["participant_gate_pass"] + self.participant["counts"]["participant_gate_unresolved"], 20)

    def test_identity_and_fact_lineage_is_complete(self) -> None:
        self.assertEqual(len(self.identity["records"]), 3)
        self.assertTrue(all(row["previous_review_history"]["stage"] == "X1.2A" for row in self.identity["records"]))
        self.assertEqual(len(self.facts["records"]), 58)
        self.assertTrue(all(row["previous_review_history"]["stage"] == "X1.2A" for row in self.facts["records"]))
        for row in self.facts["records"]:
            if row["reopen_status"] == "reopened_due_to_new_source":
                self.assertTrue(row["new_evidence_assertion_ids"])
            self.assertIn(row["review_status"], {"accepted", "unresolved", "rejected"})
            if row["review_status"] != "accepted":
                self.assertEqual(row["materialization_status"], "not_materialized")

    def test_citations_are_research_only(self) -> None:
        self.assertTrue(self.citations["records"])
        self.assertTrue(all(row["verification_status"] == "citation_only" for row in self.citations["records"]))
        self.assertTrue(all(row["research_only"] for row in self.citations["records"]))
        self.assertTrue(all(not row["canonical_fact_created"] for row in self.citations["records"]))

    def test_extension_is_non_mutating_and_does_not_duplicate_x1_2a(self) -> None:
        old = load("data/derived/x1-2a-canonical-facts.json")
        old_ids = {row.get("fact_id") for row in old["fact_index"]}
        new_ids = {row.get("fact_id") for row in self.extension["fact_index"]}
        self.assertFalse(old_ids & new_ids)
        self.assertEqual(self.extension["prior_extension"]["fact_count"], len(old["fact_index"]))
        self.assertTrue(self.extension["prior_extension"]["preserved_without_copy"])
        self.assertTrue(self.materialization["preservation"]["x1_2a_extension_unchanged"])
        self.assertEqual(self.materialization["counts"]["stories_added_to_production_scope"], 0)
        self.assertTrue(self.materialization["preservation"]["no_ml_write_back"])

    def test_extension_participant_projection_is_traceable(self) -> None:
        stories = {row["story_id"]: row for row in self.extension["stories"]}
        participants = {row["participant_id"]: row for row in self.extension["participant_records"]}
        links = {row["link_id"]: row for row in self.extension["person_story_links"]}
        mentions = {row["mention_id"]: row for row in self.extension["mention_projections"]}
        self.assertEqual(len(stories), self.extension["counts"]["stories"])
        self.assertEqual(len(participants), self.extension["counts"]["participant_records"])
        self.assertEqual(len(links), self.extension["counts"]["person_story_links"])
        self.assertEqual(len(mentions), self.extension["counts"]["mention_projections"])
        for story in stories.values():
            self.assertTrue(all(value in participants for value in story["participant_record_ids"]))
            self.assertTrue(all(value in links for value in story["person_story_link_ids"]))
        self.assertTrue(all(not row["hard_participation"] for row in participants.values() if row["role"] == "annotation_only"))

    def test_validator_and_deterministic_rebuild(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/validate_x1_2r.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        skip_if_portable_payload_missing(
            self,
            ROOT,
            ".cache/shishuo-reference/jianshu/story-records.jsonl",
        )
        before = {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in OUTPUTS
        }
        result = subprocess.run(
            [sys.executable, "scripts/build_x1_2r.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        after = {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in OUTPUTS
        }
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
