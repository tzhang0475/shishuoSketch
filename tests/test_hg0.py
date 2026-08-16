import json
from pathlib import Path
import unittest

from scripts.build_hg0_historical_graph import INPUTS, OUTPUTS, interval_overlaps


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / OUTPUTS[name]).read_text(encoding="utf-8"))


class HG0FoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ontology = load("ontology")
        cls.universe = load("universe")
        cls.graph = load("graph")
        cls.temporal = load("temporal")
        cls.audit = load("graph_audit")
        cls.sufficiency = load("sufficiency")
        cls.bias = load("bias")
        cls.gaps = load("gaps")
        cls.contract = load("ml_contract")
        cls.protection = load("protection")

    def test_graph_universe_separates_published_scope_boundary(self):
        self.assertEqual(self.universe["default_scope_id"], "published_story_scope")
        counts = self.universe["protected_counts"]
        self.assertEqual(counts["production_persons"], 75)
        self.assertEqual(counts["published_stories"], 143)
        self.assertEqual(counts["global_person_story_links"], 875)
        self.assertEqual(counts["published_person_story_links"], 330)
        self.assertEqual(counts["excluded_person_story_links"], 545)
        boundary = next(row for row in self.universe["scopes"] if row["scope_id"] == "global_person_story_index_boundary")
        self.assertEqual(boundary["outside_story_id_count"], 417)
        self.assertEqual(boundary["story_node_count"], 0)

    def test_node_ontology_and_reification_are_explicit(self):
        node_types = {row["node_type"] for row in self.ontology["node_types"]}
        self.assertTrue({"Person", "Story", "Location", "Event", "Office", "Clan", "Regime"} <= node_types)
        self.assertTrue({"OfficeTenure", "PersonActivity", "EventParticipation", "ServicePoliticalFact"} <= node_types)
        decisions = {row["fact_type"]: row["decision"] for row in self.ontology["reification_audit"]}
        self.assertEqual(decisions["office_tenure"], "reified_node")
        self.assertEqual(decisions["person_activity"], "reified_node")
        self.assertEqual(decisions["marriage"], "direct_typed_edge_with_fact_reference")
        self.assertTrue(any(node.get("reified_fact_node") and node["node_type"] == "OfficeTenure" for node in self.graph["nodes"]))
        self.assertTrue(any(edge["projection_role"] == "reified_support" for edge in self.graph["edges"]))

    def test_every_edge_is_traceable_and_layers_remain_typed(self):
        fact_keys = {
            row["fact_key"]
            for row in json.loads((ROOT / INPUTS["h0c_facts"]).read_text(encoding="utf-8"))["fact_index"]
        }
        for edge in self.graph["edges"]:
            self.assertTrue(edge["source_facts"])
            self.assertTrue(edge["evidence_ids"])
            self.assertTrue(edge["fact_ids"])
            self.assertTrue(all(ref["fact_key"] in fact_keys for ref in edge["source_facts"]))
            self.assertIn(edge["graph_layer"], edge["layer_memberships"])
        edge_types = {edge["edge_type"] for edge in self.graph["edges"]}
        self.assertIn("person_story_link", edge_types)
        self.assertIn("story_participant_present", edge_types)
        self.assertIn("parent_of", edge_types)
        self.assertIn("spouse_union", edge_types)
        self.assertNotEqual("person_story_link", "story_participant_present")

    def test_temporal_projection_preserves_unknown_and_interval_overlap(self):
        self.assertTrue(interval_overlaps({"start_year_ce": 322, "end_year_ce": 324}, 323, 329))
        self.assertFalse(interval_overlaps({"start_year_ce": 322, "end_year_ce": 324}, 325, 329))
        self.assertFalse(interval_overlaps({"start_year_ce": None, "end_year_ce": None}, 322, 329))
        self.assertEqual(len(self.temporal["edge_temporal_index"]), len(self.graph["edges"]))
        self.assertGreater(self.temporal["coverage"]["unknown_edge_count"], 0)
        self.assertIn("temporal_leakage_rule", self.temporal["slice_query_contract"])
        self.assertIn("no_exactness_upgrade", self.temporal["slice_query_contract"])

    def test_isolated_nodes_are_visible_not_repaired(self):
        expected = {
            "Person:person-016",
            "Person:person-032",
            "Person:person-037",
            "Person:person-074",
            "Story:27-jiajue-012",
        }
        self.assertEqual(set(self.sufficiency["graph_summary"]["isolated_nodes"]), expected)
        self.assertEqual(self.sufficiency["graph_summary"]["isolated_node_count"], 5)
        self.assertTrue(any(row["category"] == "isolated_node" for row in self.gaps["records"]))

    def test_multiplex_layers_and_research_classifications(self):
        self.assertGreater(self.bias["story_layer_dominance"]["story_related_edge_ratio"], 0.70)
        self.assertEqual(self.sufficiency["layers"]["story"]["classification"], "usable")
        self.assertEqual(self.sufficiency["layers"]["family"]["classification"], "pilot_only")
        self.assertEqual(self.sufficiency["layers"]["service_political"]["classification"], "insufficient")
        self.assertTrue(any("G_story" == value for value in self.ontology["multiplex_policy"]["layer_views"]))
        self.assertTrue(self.ontology["multiplex_policy"]["same_endpoint_different_type"])

    def test_graph_audit_has_no_integrity_failures(self):
        for issue in [
            "dangling_edges",
            "dangling_fact_references",
            "unsupported_edges",
            "duplicate_edge_ids",
            "duplicate_semantic_edges",
            "symmetric_reverse_duplicates",
            "invalid_edge_types",
            "invalid_node_types",
            "invalid_temporal_intervals",
            "ontology_endpoint_conflicts",
            "unsupported_nodes",
            "family_cycle_anomalies",
        ]:
            self.assertEqual(self.audit["issue_counts"].get(issue, 0), 0, issue)

    def test_alias_collisions_are_not_resolved_by_topology(self):
        collisions = self.audit["inherited_h0c_issues"]["identity_collision_surfaces"]
        surfaces = {row["surface"] for row in collisions}
        self.assertIn("太傅", surfaces)
        self.assertIn("王公", surfaces)
        self.assertTrue(any(row["category"] == "alias_collision" for row in self.gaps["records"]))

    def test_missing_edges_are_not_negative_and_no_models_are_generated(self):
        self.assertTrue(self.contract["framework_neutral"])
        self.assertFalse(self.contract["missingness_contract"]["missing_edge_is_negative"])
        self.assertFalse(self.contract["missingness_contract"]["negative_facts_generated"])
        self.assertFalse(self.contract["model_artifacts_generated"])
        self.assertFalse(self.contract["embeddings_generated"])
        self.assertFalse(self.contract["training_split_generated"])
        self.assertEqual(self.contract["research_question_readiness"][-1]["classification"], "not_supported")

    def test_h0c_protection_hashes_are_recorded(self):
        self.assertEqual(self.protection["baseline_h0c_commit"], "4854d3d1997300c9039d8093c0c7114cb00c47d1")
        self.assertEqual(self.protection["participant_freeze_sha256"], "462373a4d1be83f1751bd3037024cf6e0620dd7e35401b35f8f1b09c340f2bb0")
        self.assertEqual(self.protection["protected_counts"]["persons"], 75)
        self.assertEqual(self.protection["protected_counts"]["published_stories"], 143)

    def test_temporal_example_slices_are_potential_not_exact_dates(self):
        for example in self.temporal["example_queries"]:
            self.assertGreaterEqual(example["start_year_ce"], 300)
            self.assertLessEqual(example["start_year_ce"], example["end_year_ce"])
            self.assertIn("potentially_active_edge_count", example)
        self.assertIn("potential-overlap", self.temporal["slice_query_contract"]["interval_semantics"])


if __name__ == "__main__":
    unittest.main()
