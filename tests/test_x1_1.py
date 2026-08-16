from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.build_x1_1_candidate_pool import build as build_pool
from scripts.select_x1_1_expansion import build as build_selection
from scripts.validate_x1_1 import validate
from scripts.x1_1_common import BATCH_SIZE, CHANNEL_ORDER, POOL_PATH, RATIOS, SEED, SELECTION_PATH, sha256_file


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class X11ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pool = read("data/derived/x1-1-candidate-pool.json")
        cls.selection = read("data/derived/x1-1-selection-manifest.json")
        cls.review = read("data/derived/x1-1-review-results.json")
        cls.info = read("data/derived/x1-1-information-gain.json")
        cls.bias = read("data/derived/x1-1-bias-audit.json")

    def test_candidate_universe_is_the_global_boundary_and_excludes_published(self) -> None:
        self.assertEqual(self.pool["counts"]["audited_story_count"], 417)
        self.assertEqual(self.pool["counts"]["qualified_story_count"], 388)
        self.assertEqual(self.pool["counts"]["out_of_scope_story_count"] if "out_of_scope_story_count" in self.pool["counts"] else self.pool["candidate_universe"]["out_of_scope_story_count"], 417)
        production = {row["id"] for row in read("data/derived/sc1-site.json")["stories"]}
        self.assertFalse(production & {row["story_id"] for row in self.pool["records"]})
        self.assertEqual(self.pool["counts"]["rejection_reasons"].get("punctuation_record_disputed"), 28)

    def test_four_channels_are_disjoint_and_follow_default_allocation(self) -> None:
        records = self.selection["records"]
        by_channel = {channel: [row for row in records if row["selection_mode"] == channel] for channel in CHANNEL_ORDER}
        self.assertEqual({channel: len(rows) for channel, rows in by_channel.items()}, {
            "graph_guided": 8,
            "coverage_guided": 6,
            "stratified_random": 3,
            "counter_model": 3,
        })
        sets = [set(row["story_id"] for row in rows) for rows in by_channel.values()]
        self.assertEqual(sum(map(len, sets)), len(set().union(*sets)))
        self.assertEqual(len(records), BATCH_SIZE)
        self.assertEqual(self.selection["batch_policy"]["ratios"], RATIOS)
        self.assertTrue(self.selection["frozen_before_enrichment"])

    def test_seeded_random_channel_does_not_use_model_score(self) -> None:
        rows = [row for row in self.selection["records"] if row["selection_mode"] == "stratified_random"]
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertIsNone(row["selection_score"])
            self.assertIsNotNone(row["stratum"])
            self.assertEqual(row["selection_seed"], SEED)
            self.assertNotIn("model", " ".join(row["selection_inputs"]).lower())

    def test_counter_model_requires_independent_signals_and_lower_half(self) -> None:
        rows = [row for row in self.selection["records"] if row["selection_mode"] == "counter_model"]
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertGreaterEqual(len(row["counter_model_reason"]), 2)
            self.assertGreater(row["model_proxy_rank"], self.pool["counts"]["qualified_story_count"] // 2)
            self.assertIn("qualified_local_source_and_evidence", row["counter_model_reason"])

    def test_selection_rebuild_and_snapshot_are_deterministic(self) -> None:
        self.assertEqual(build_pool(), self.pool)
        self.assertEqual(build_selection(BATCH_SIZE, SEED), self.selection)
        self.assertEqual(self.selection["candidate_pool"]["sha256"], sha256_file(POOL_PATH))
        self.assertEqual(self.selection["source_versions"]["input_artifact_hashes"]["candidate_pool"], sha256_file(POOL_PATH))

    def test_review_keeps_actions_separate_and_does_not_write_back(self) -> None:
        self.assertEqual(self.review["counts"]["selected_story_count"], 20)
        self.assertEqual(self.review["counts"]["canonical_fact_addition_count"], 0)
        self.assertEqual(self.review["counts"]["canonical_story_addition_count"], 0)
        self.assertEqual(self.review["counts"]["canonical_person_addition_count"], 0)
        self.assertEqual(self.review["review_policy"]["model_output_does_not_create_facts"], True)
        self.assertEqual(self.review["review_policy"]["missing_edges_are_not_negative_facts"], True)
        for row in self.review["records"]:
            self.assertEqual(row["selection_status"], "selected")
            self.assertEqual(row["review_status"], "candidate")
            self.assertEqual(row["canonical_status"], "not_materialized")
            action_order = {"ADD_FACT": 0, "ADD_STORY": 1, "ADD_PERSON": 2}
            order = [action_order[action["action"]] for action in row["actions"]]
            self.assertEqual(order, sorted(order))
            self.assertTrue(any(action["action"] == "ADD_STORY" for action in row["actions"]))
            self.assertTrue(row["identity_review"]["person_story_is_not_participation"])

    def test_audit_contains_all_channels_and_independent_floors(self) -> None:
        self.assertEqual({row["selection_mode"] for row in self.info["channels"]}, set(CHANNEL_ORDER))
        self.assertEqual(len(self.bias["channels"]), 4)
        recommendation = read("data/derived/x1-1-next-epoch-recommendation.json")
        self.assertGreaterEqual(recommendation["recommended_x1_2_ratios"]["stratified_random"], 0.10)
        self.assertGreaterEqual(recommendation["recommended_x1_2_ratios"]["counter_model"], 0.10)

    def test_validator_passes_and_protected_counts_remain(self) -> None:
        result = validate()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["selected_stories"], 20)
        self.assertEqual(len(read("data/people.json")["people"]), 75)
        self.assertEqual(len(read("data/derived/sc1-site.json")["stories"]), 143)
        self.assertEqual(read("data/derived/person-story-links.json")["link_count"], 875)


if __name__ == "__main__":
    unittest.main()
