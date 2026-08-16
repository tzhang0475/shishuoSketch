from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import unittest

from scripts.audit_x1_2p import build as build_audit
from scripts.build_x1_2p_review import build as build_review
from scripts.validate_x1_2p import validate
from scripts.x1_2p_common import (
    CHANNEL_PATH,
    DEPENDENCY_PATH,
    ELIGIBILITY_PATH,
    GATE_AUDIT_PATH,
    NEXT_STEP_PATH,
    PUNCTUATION_PATH,
    READINESS_PATH,
    STORY_REVIEW_PATH,
    SUMMARY_PATH,
    X1_1_INPUTS,
    X1_2A_INPUTS,
    read,
    selection_by_story,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = (
    GATE_AUDIT_PATH,
    STORY_REVIEW_PATH,
    DEPENDENCY_PATH,
    ELIGIBILITY_PATH,
    CHANNEL_PATH,
    READINESS_PATH,
    NEXT_STEP_PATH,
    SUMMARY_PATH,
)


class X12PContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.selection = read(X1_1_INPUTS["selection_manifest"])
        cls.pool = read(X1_1_INPUTS["candidate_pool"])
        cls.story = read(STORY_REVIEW_PATH)
        cls.gate = read(GATE_AUDIT_PATH)
        cls.dependency = read(DEPENDENCY_PATH)
        cls.eligibility = read(ELIGIBILITY_PATH)
        cls.channel = read(CHANNEL_PATH)
        cls.readiness = read(READINESS_PATH)
        cls.summary = read(SUMMARY_PATH)

    def test_scope_is_exactly_the_frozen_x1_1_selection(self) -> None:
        selected = set(selection_by_story())
        self.assertEqual(len(selected), 20)
        self.assertEqual({row["story_id"] for row in self.story["records"]}, selected)
        self.assertEqual(self.selection["selection_status"], "frozen")
        self.assertEqual(self.gate["scope"]["replacement_selection"], False)
        self.assertEqual(self.gate["scope"]["x1_1_disputed_28_reopened"], False)

    def test_gate_contract_is_intentional_two_tier_policy(self) -> None:
        classification = self.gate["classification"]
        self.assertEqual(classification["type"], "intentional_two_tier_policy")
        self.assertFalse(classification["implementation_bug"])
        self.assertFalse(classification["stale_metadata"])
        self.assertEqual(self.gate["summary"]["candidate_gate_pass_count"], 20)
        self.assertEqual(self.gate["summary"]["production_punctuation_gate_pass_count"], 0)

    def test_every_story_has_explicit_conservative_review(self) -> None:
        self.assertEqual(self.story["counts"], {"unresolved": 20})
        reasons = Counter(row["punctuation_review"]["reason_code"] for row in self.story["records"])
        self.assertEqual(reasons, {
            "unresolved_insufficient_local_evidence": 3,
            "unresolved_source_witness_conflict": 17,
        })
        for row in self.story["records"]:
            self.assertIn(row["review_status"], {"accepted", "unresolved", "rejected"})
            self.assertFalse(row["punctuation_review"]["change_applied"])
            self.assertTrue(row["selection_does_not_affect_textual_judgment"])
            self.assertTrue(all(ref["hash_matches"] for ref in row["punctuation_record"]["reference_audit"]))

    def test_source_punctuation_and_x1_2a_extension_are_unchanged(self) -> None:
        self.assertEqual(
            sha256_file(PUNCTUATION_PATH),
            self.pool["source_artifact_hashes"]["punctuation"],
        )
        extension = read(X1_2A_INPUTS["canonical_facts"])
        self.assertEqual(len(extension["fact_index"]), 9)
        self.assertEqual(len(extension["entities"]), 3)
        self.assertTrue(self.summary["protected_x1_2a"]["canonical_extension_unchanged"])

    def test_dependency_audit_covers_unresolved_facts_and_identities(self) -> None:
        self.assertEqual(len(self.dependency["fact_records"]), 58)
        self.assertEqual(len(self.dependency["identity_records"]), 3)
        self.assertEqual(self.dependency["summary"]["facts_blocked_by_story_punctuation"], 58)
        self.assertEqual(self.dependency["summary"]["identities_blocked_by_story_punctuation"], 3)
        for row in self.dependency["fact_records"] + self.dependency["identity_records"]:
            self.assertIn("blocked_by_story_punctuation", row["blocking_factors"])
            self.assertEqual(row["materialization_status"], "not_materialized")

    def test_no_rematerialization_and_channel_neutrality(self) -> None:
        self.assertEqual(self.eligibility["counts"], {
            "eligible_for_rematerialization": 0,
            "still_unresolved": 20,
            "rejected": 0,
            "stories_released": 0,
            "facts_released": 0,
            "persons_released": 0,
        })
        self.assertFalse(self.channel["channel_neutrality"]["selection_mode_influenced_outcome"])
        expected = {"graph_guided": 8, "coverage_guided": 6, "stratified_random": 3, "counter_model": 3}
        for row in self.channel["channels"]:
            self.assertEqual(row["selected_story_count"], expected[row["selection_mode"]])
            self.assertEqual(row["accepted_count"], 0)
            self.assertEqual(row["unresolved_count"], expected[row["selection_mode"]])

    def test_future_candidate_readiness_is_a_non_mutating_overlay(self) -> None:
        self.assertEqual(len(self.readiness["records"]), len(self.pool["records"]))
        self.assertEqual(self.readiness["candidate_pool_sha256"], sha256_file(X1_1_INPUTS["candidate_pool"]))
        selected = set(selection_by_story())
        rows = {row["story_id"]: row for row in self.readiness["records"]}
        self.assertTrue(all(rows[story_id]["x1_2p_selected"] for story_id in selected))
        self.assertTrue(all(not rows[story_id]["production_punctuation_ready"] for story_id in selected))

    def test_validator_and_rebuild_are_deterministic(self) -> None:
        self.assertEqual(validate(), [])
        before = {str(path): hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in OUTPUTS}
        build_review()
        build_audit()
        after = {str(path): hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in OUTPUTS}
        self.assertEqual(before, after)
        self.assertEqual(validate(), [])


if __name__ == "__main__":
    unittest.main()
