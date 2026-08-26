import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import hdb2_psl0_common as common  # noqa: E402
import validate_hdb2_psl0 as validator  # noqa: E402


class HDB2PSL0Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selection = common.freeze_selection()
        cls.frozen = common.load_frozen_lj0_cases()
        cls.graph = common.build_graph_cases(cls.frozen)

    def test_same_frozen_lj0_selection(self):
        self.assertEqual(self.selection["case_count"], 24)
        self.assertEqual(
            {row["occurrence_id"] for row in self.selection["cases"]},
            {row["occurrence_id"] for row in json.loads(common.LJ0_SELECTION.read_text())["cases"]},
        )
        self.assertTrue(self.selection["frozen_before_live"])
        self.assertTrue(self.selection["candidate_only"])
        self.assertFalse(self.selection["canonical_write_back"])

    def test_candidate_nodes_do_not_merge_no_id_surface_occurrences(self):
        no_id = {}
        for case in self.graph["cases"]:
            for candidate in case["candidates"]:
                if candidate.get("person_id") is None and not str(candidate["candidate_node_id"]).startswith("ruler:"):
                    no_id.setdefault((common.matching(candidate.get("display_name")), candidate.get("display_name")), []).append(candidate["candidate_node_id"])
        for nodes in no_id.values():
            self.assertEqual(len(nodes), len(set(nodes)))
            self.assertTrue(all(node.startswith("local:") for node in nodes))

    def test_wudi_registry_bridge_is_existing_data_not_person_id(self):
        rows = [row for row in self.graph["cases"] if row.get("story_id") == "05-fangzheng-011"]
        self.assertEqual(len(rows), 2)
        wudi = next(row for row in rows if row.get("target_surface") == "武帝")
        wudi_candidate = next(row for row in wudi["candidates"] if row.get("display_name") == "世祖武皇帝")
        self.assertEqual(wudi_candidate["candidate_node_id"], "ruler:ruler-jin-wudi")
        self.assertIsNone(wudi_candidate.get("person_id"))
        emperor = next(row for row in rows if row.get("target_surface") == "帝")
        emperor_candidate = next(row for row in emperor["candidates"] if row.get("display_name") == "世祖武皇帝")
        self.assertEqual(emperor_candidate["candidate_node_id"], wudi_candidate["candidate_node_id"])

    def test_model_packet_has_only_local_keys_and_closed_tool(self):
        tool = common.predicate_tool()["function"]
        self.assertTrue(tool["strict"])
        params = tool["parameters"]
        self.assertFalse(params["additionalProperties"])
        self.assertEqual(set(params["required"]), set(params["properties"]))
        for case in self.graph["cases"]:
            packet = common.wire_packet(case, self.graph["cases"], self.graph)
            rendered = json.dumps(packet, ensure_ascii=False, sort_keys=True)
            for forbidden in ("person_id", "provisional_person_id", "relation_id", "graph_id", "canonical_person_id"):
                self.assertNotIn(forbidden, rendered)
            request_ids = [row["predicate_id"] for row in packet["request_predicates"]]
            self.assertEqual(len(request_ids), len(set(request_ids)))

    def test_predicate_validation_rejects_unknown_or_unrequested_values(self):
        case = next(case for case in self.graph["cases"] if case["candidates"])
        packet = common.wire_packet(case, self.graph["cases"], self.graph)
        result = common.validate_predicates({"predicates": [{
            "predicate_id": "q999",
            "predicate": "ContextCompatible",
            "mention_id": case["mention_id"],
            "other_mention_id": None,
            "candidate_key": "c999",
            "value": 1,
            "evidence_ids": ["ev999"],
        }], "note": ""}, packet)
        self.assertFalse(result["valid"])
        self.assertIn("predicate_id_invalid:q999", result["errors"])
        self.assertIn("evidence_reference_invalid:q999:ev999", result["errors"])
        self.assertIn("predicate_request_not_fully_covered", result["errors"])

    def test_collective_inference_uses_coreference_and_known_relation(self):
        graph = {
            "selection_hash": "test",
            "cases": [
                {"mention_id": "m1", "occurrence_id": "m1", "story_id": "s", "target_surface": "甲", "occurrence_type": "abbreviated_person_name", "candidates": [{"candidate_key": "c0", "display_name": "甲人", "person_id": "person-a", "candidate_node_id": "person:person-a"}], "deterministic_predicates": [{"predicate": "AliasMatch", "candidate_key": "c0", "value": 1, "evidence_ids": ["e0"]}], "known_relation_predicates": [], "same_story_predicates": []},
                {"mention_id": "m2", "occurrence_id": "m2", "story_id": "s", "target_surface": "其", "occurrence_type": "abbreviated_person_name", "candidates": [{"candidate_key": "c0", "display_name": "甲人", "person_id": "person-a", "candidate_node_id": "person:person-a"}], "deterministic_predicates": [], "known_relation_predicates": [], "same_story_predicates": []},
            ],
            "context_mentions": [],
            "coreference_pairs": [],
        }
        result = common.infer_graph(graph, [{"mention_id": "m1", "predicate_id": "q0", "predicate": "ContextCompatible", "candidate_key": "c0", "other_mention_id": None, "value": 0.8, "evidence_ids": ["e0"]}, {"mention_id": "m1", "predicate_id": "q1", "predicate": "Coreference", "candidate_key": None, "other_mention_id": "m2", "value": 1, "evidence_ids": ["e0"]}])
        m2 = next(row for row in result["records"] if row["mention_id"] == "m2")
        self.assertEqual(m2["candidate_rankings"][0]["candidate_key"], "c0")
        self.assertIn("Coreference", m2["collective_support_predicates"])

    def test_validator_accepts_candidate_only_graph(self):
        result = validator.validate(self.selection, self.graph)
        self.assertTrue(result["valid"], result["errors"])

    def test_safety_metrics_are_explicit_and_zero_for_prepared_graph(self):
        decisions = common.infer_graph(self.graph, [])
        safety = common.safety_metrics(self.graph, decisions, [])
        for key in (
            "same_surface_automatic_merges",
            "compositional_base_person_collapses",
            "nonperson_person_id_anomalies",
            "hard_veto_promotions",
            "invalid_candidate_keys",
            "invalid_evidence_references",
            "confidence_only_resolutions",
        ):
            self.assertEqual(safety[key], 0, key)
        self.assertTrue(safety["candidate_only"])
        self.assertFalse(safety["canonical_write_back"])


if __name__ == "__main__":
    unittest.main()
