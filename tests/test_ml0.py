import json
from pathlib import Path
import unittest

from scripts.build_ml0_pilot import (
    ABLATION_LAYERS,
    EXTERNAL_LAYERS,
    HG0_INPUTS,
    OUTPUTS,
    PRIMARY_VIEWS,
    ranking_metrics,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]


def load_output(key):
    return json.loads((ROOT / OUTPUTS[key]).read_text(encoding="utf-8"))


class ML0ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hg0 = json.loads((ROOT / HG0_INPUTS["graph"]).read_text(encoding="utf-8"))
        cls.dataset = load_output("dataset")
        cls.experiments = load_output("experiments")
        cls.gnn = load_output("gnn")
        cls.link = load_output("link")
        cls.temporal = load_output("temporal")
        cls.metrics = load_output("metrics")
        cls.protection = load_output("protection")

    def test_deterministic_node_mapping_is_type_then_id(self):
        rows = self.dataset["mapping"]["nodes"]
        self.assertEqual([row["ml_index"] for row in rows], list(range(len(rows))))
        self.assertEqual(
            [(row["node_type"], row["node_id"]) for row in rows],
            sorted((row["node_type"], row["node_id"]) for row in rows),
        )
        self.assertEqual(len(rows), 347)

    def test_required_views_and_external_separation(self):
        views = {row["view_id"]: row for row in self.dataset["views"]}
        self.assertEqual(
            set(views),
            set(PRIMARY_VIEWS) | {f"G_all_minus_{layer}" for layer in ABLATION_LAYERS},
        )
        node_types = [(row["node_type"], row["node_id"]) for row in self.dataset["mapping"]["nodes"]]
        by_id = {edge["edge_id"]: edge for edge in self.hg0["edges"]}
        external = views["G_external"]["encoded_edges"]
        for edge in external:
            original = by_id[edge["edge_id"]]
            self.assertTrue(set(original["layer_memberships"]) & EXTERNAL_LAYERS)
            self.assertNotIn("story", original["layer_memberships"])
            self.assertNotEqual(node_types[edge["source_index"]][0], "Story")
            self.assertNotEqual(node_types[edge["target_index"]][0], "Story")
        self.assertTrue(all("story" in by_id[edge["edge_id"]]["layer_memberships"] for edge in views["G_story"]["encoded_edges"]))

    def test_review_and_temporal_filters_are_strict(self):
        views = {row["view_id"]: row for row in self.dataset["views"]}
        by_id = {edge["edge_id"]: edge for edge in self.hg0["edges"]}
        self.assertTrue(all(by_id[edge["edge_id"]]["review_status"] == "reviewed" for edge in views["G_reviewed"]["encoded_edges"]))
        self.assertTrue(all(by_id[edge["edge_id"]]["temporal"]["temporal_state"] in {"bounded", "one_sided"} for edge in views["G_temporal_bounded"]["encoded_edges"]))
        self.assertGreater(views["G_all"]["unknown_temporal_edge_count"], 0)
        self.assertEqual(views["G_temporal_bounded"]["unknown_temporal_edge_count"], 0)

    def test_missing_edges_are_not_negative_and_corruptions_are_ml_only(self):
        self.assertFalse(self.dataset["missingness"]["missing_edge_is_negative"])
        self.assertFalse(self.dataset["missingness"]["generated_negative_facts"])
        self.assertTrue(self.dataset["missingness"]["ml_corruptions_are_separate"])
        self.assertTrue(self.link["protocol"]["generated_corruptions_are_not_historical_negatives"])
        self.assertFalse(self.metrics["negative_facts_generated"])

    def test_average_rank_ties_do_not_look_like_perfect_prediction(self):
        positive = [{"source_index": 1, "target_index": 2}]
        corruptions = {(1, 2): [3, 4, 5]}
        scores = {(1, 2): 0.0, (1, 3): 0.0, (1, 4): 0.0, (1, 5): 0.0}
        metrics = ranking_metrics(scores, positive, corruptions)
        self.assertEqual(metrics["mean_rank"], 2.5)
        self.assertEqual(metrics["mrr"], 0.4)
        self.assertEqual(metrics["hits_at_1"], 0.0)

    def test_link_split_is_observed_positive_only(self):
        split = self.link["split"]
        self.assertTrue(set(split["train_edge_ids"]))
        self.assertTrue(set(split["test_edge_ids"]))
        self.assertFalse(set(split["train_edge_ids"]) & set(split["test_edge_ids"]))
        by_id = {edge["edge_id"]: edge for edge in self.hg0["edges"]}
        self.assertTrue(all(by_id[edge_id]["edge_type"] == "person_story_link" for edge_id in split["train_edge_ids"] + split["test_edge_ids"]))

    def test_temporal_feasibility_excludes_unknown_from_pre_cutoff(self):
        checks = self.temporal["leakage_checks"]
        self.assertTrue(checks["unknown_excluded_from_pre"])
        self.assertTrue(checks["pre_max_end_respects_cutoff"])
        self.assertTrue(checks["future_start_excluded_from_pre"])
        self.assertGreater(len(self.temporal["unknown_or_relative_bucket"]["edge_ids"]), 0)

    def test_gnn_is_research_only_and_seed_stable_contract_is_present(self):
        self.assertEqual(self.gnn["implementation"]["write_back"], False)
        self.assertEqual(len(self.gnn["views"]), len(PRIMARY_VIEWS) + len(ABLATION_LAYERS))
        self.assertTrue(all(row["completed_count"] > 0 for row in self.gnn["views"]))
        self.assertTrue(all(row["seed_policy"] for row in self.gnn["views"]))
        self.assertTrue(self.experiments["random_seed_policy"]["same_seeds_across_views"])

    def test_hg0_hashes_and_counts_are_protected(self):
        for name, path in HG0_INPUTS.items():
            self.assertEqual(self.protection["hg0_input_hashes"][name], sha256_file(path), name)
        self.assertEqual(self.protection["protected_counts"], {"persons": 75, "stories": 143, "hg0_nodes": 347, "hg0_edges": 996})
        self.assertFalse(self.protection["canonical_negative_facts_generated"])
        self.assertFalse(self.protection["embeddings_persisted"])


if __name__ == "__main__":
    unittest.main()
