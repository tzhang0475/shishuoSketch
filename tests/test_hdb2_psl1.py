import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import hdb2_psl1_common as common  # noqa: E402
import validate_hdb2_psl1 as validator  # noqa: E402


class HDB2PSL1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selection = common.freeze_experiment_selection()
        cls.regression_input = common.load_regression_cases()
        cls.holdout_input = common.load_holdout_cases({"holdout_cases": cls.selection["holdout_cases"]})
        cls.regression = common.build_graph_cases(cls.regression_input)
        cls.holdout = common.build_graph_cases(cls.holdout_input)

    def test_selection_is_frozen_and_disjoint(self):
        self.assertTrue(self.selection["frozen_before_live"])
        self.assertTrue(self.selection["candidate_only"])
        self.assertFalse(self.selection["canonical_write_back"])
        regression = {row["occurrence_id"] for row in self.selection["regression_cases"]}
        holdout = {row["occurrence_id"] for row in self.selection["holdout_cases"]}
        psl0 = {row["occurrence_id"] for row in json.loads(common.PSL0_SELECTION.read_text())["cases"]}
        self.assertEqual(len(regression), 24)
        self.assertEqual(len(holdout), 20)
        self.assertFalse(regression & holdout)
        self.assertFalse(holdout & psl0)
        rebuilt = common.freeze_experiment_selection()
        self.assertEqual(rebuilt, self.selection)

    def test_closed_predicate_contract_has_no_psl0_compatibility_predicates(self):
        predicates = set(self.regression["predicate_set"])
        self.assertIn("IdentityContextSupport", predicates)
        self.assertIn("CrossStoryIdentitySupport", predicates)
        self.assertIn("IdentityContradiction", predicates)
        self.assertIn("Distinct", predicates)
        self.assertNotIn("ContextCompatible", predicates)
        self.assertNotIn("CrossStoryCompatible", predicates)
        tool = common.predicate_tool()["function"]
        self.assertTrue(tool["strict"])
        self.assertFalse(tool["parameters"]["additionalProperties"])
        self.assertEqual(set(tool["parameters"]["required"]), set(tool["parameters"]["properties"]))

    def test_packets_do_not_expose_provider_ids_or_old_predicates(self):
        for graph in (self.regression, self.holdout):
            for case in graph["cases"]:
                packet = common.wire_packet(case, graph["cases"], graph)
                rendered = json.dumps(packet, ensure_ascii=False, sort_keys=True)
                for forbidden in common.FORBIDDEN_ID_KEYS:
                    self.assertNotIn(forbidden, rendered)
                self.assertNotIn("ContextCompatible", rendered)
                self.assertNotIn("CrossStoryCompatible", rendered)
                self.assertIn("local_relation_context", packet)

    def test_coreference_is_requested_once_per_unordered_pair(self):
        pairs = self.regression["coreference_pairs"]
        self.assertTrue(pairs)
        pair = pairs[0]
        owners = []
        for case in self.regression["cases"]:
            packet = common.wire_packet(case, self.regression["cases"], self.regression)
            if any(
                row.get("predicate") == "Coreference"
                and {row.get("mention_id"), row.get("other_mention_id")} == {pair["left_mention_id"], pair["right_mention_id"]}
                for row in packet["request_predicates"]
            ):
                owners.append(case["mention_id"])
        self.assertEqual(owners, [pair["left_mention_id"]])

    def test_yanyu_distinctness_vetoes_shared_liutan_candidate(self):
        wang = next(row for row in self.regression["cases"] if row["story_id"] == "02-yanyu-054" and row["target_surface"] == "王長史")
        liu = next(row for row in self.regression["cases"] if row["story_id"] == "02-yanyu-054" and row["target_surface"] == "劉尹")
        decisions = common.infer_graph(self.regression, [{
            "mention_id": liu["mention_id"],
            "predicate": "IdentityContextSupport",
            "candidate_key": "c0",
            "value": 1.0,
            "evidence_ids": ["ev0"],
        }])
        by_surface = {row["surface"]: row for row in decisions["records"] if row["story_id"] == "02-yanyu-054"}
        self.assertEqual(len(self.regression["distinct_pairs"]), 1)
        self.assertTrue(by_surface["王長史"]["candidate_rankings"][0]["hard_conflict"])
        self.assertIn("Distinct", {row["predicate"] for row in by_surface["王長史"]["candidate_rankings"][0]["contradicting_predicates"]})
        self.assertFalse(by_surface["劉尹"]["candidate_rankings"][0]["hard_conflict"])
        self.assertEqual(by_surface["王長史"]["result_state"], "genuinely_unresolved")
        self.assertEqual(by_surface["劉尹"]["result_state"], "stable_entity_resolved")

    def test_identity_contradiction_is_negative_and_can_veto(self):
        graph = {
            "cases": [{
                "mention_id": "m1",
                "occurrence_id": "o1",
                "story_id": "s1",
                "target_surface": "甲",
                "occurrence_type": "abbreviated_person_name",
                "candidates": [{"candidate_key": "c0", "display_name": "甲人", "person_id": "person-a", "candidate_node_id": "person:person-a"}],
                "deterministic_predicates": [],
                "psl1_hard_vetoes": {},
            }],
            "distinct_pairs": [],
        }
        decisions = common.infer_graph(graph, [{
            "mention_id": "m1",
            "predicate": "IdentityContradiction",
            "candidate_key": "c0",
            "value": 1.0,
            "evidence_ids": ["ev0"],
        }])
        row = decisions["records"][0]
        self.assertTrue(row["candidate_rankings"][0]["hard_conflict"])
        self.assertEqual(row["result_state"], "genuinely_unresolved")
        self.assertFalse(row["direct_identity_support"])

    def test_zero_predicate_value_without_evidence_is_explicit_absence(self):
        case = next(case for case in self.regression["cases"] if case["candidates"])
        packet = common.wire_packet(case, self.regression["cases"], self.regression)
        predicates = []
        for request in packet["request_predicates"]:
            predicates.append({
                **request,
                "value": 0 if request["predicate"] != "Coreference" else 0.5,
                "evidence_ids": [],
            })
        result = common.validate_predicates({"predicates": predicates, "note": ""}, packet)
        self.assertTrue(result["valid"], result["errors"])

    def test_strict_predicate_rows_reject_undeclared_fields(self):
        case = next(case for case in self.regression["cases"] if case["candidates"])
        packet = common.wire_packet(case, self.regression["cases"], self.regression)
        row = dict(packet["request_predicates"][0])
        row.update({"value": 0, "evidence_ids": [], "unexpected": True})
        result = common.validate_predicates({"predicates": [row], "note": ""}, packet)
        self.assertFalse(result["valid"])
        self.assertIn("unknown_predicate_field:0:unexpected", result["errors"])

    def test_time_and_same_story_do_not_resolve_alone(self):
        graph = {
            "cases": [{
                "mention_id": "m1",
                "occurrence_id": "o1",
                "story_id": "s1",
                "target_surface": "甲",
                "occurrence_type": "abbreviated_person_name",
                "candidates": [{"candidate_key": "c0", "display_name": "甲人", "person_id": "person-a", "candidate_node_id": "person:person-a"}],
                "deterministic_predicates": [
                    {"predicate": "TimeCompatible", "candidate_key": "c0", "value": 1.0},
                    {"predicate": "SameStory", "candidate_key": "c0", "value": 1.0},
                ],
                "psl1_hard_vetoes": {},
            }],
            "distinct_pairs": [],
        }
        row = common.infer_graph(graph, [])["records"][0]
        self.assertNotIn(row["result_state"], {"stable_entity_resolved", "local_candidate_resolved"})
        self.assertEqual(row["candidate_rankings"][0]["raw_score"], 0.0)

    def test_direct_identity_support_can_stably_resolve_existing_candidate(self):
        graph = {
            "cases": [{
                "mention_id": "m1",
                "occurrence_id": "o1",
                "story_id": "s1",
                "target_surface": "甲",
                "occurrence_type": "abbreviated_person_name",
                "candidates": [
                    {"candidate_key": "c0", "display_name": "甲人", "person_id": "person-a", "candidate_node_id": "person:person-a"},
                    {"candidate_key": "c1", "display_name": "乙人", "person_id": "person-b", "candidate_node_id": "person:person-b"},
                ],
                "deterministic_predicates": [],
                "psl1_hard_vetoes": {},
            }],
            "distinct_pairs": [],
        }
        row = common.infer_graph(graph, [{
            "mention_id": "m1",
            "predicate": "IdentityContextSupport",
            "candidate_key": "c0",
            "value": 1.0,
            "evidence_ids": ["ev0"],
        }])["records"][0]
        self.assertEqual(row["result_state"], "stable_entity_resolved")
        self.assertEqual(row["top_candidate_key"], "c0")

    def test_reviewer_literal_null_and_unknown_evidence_fail_closed(self):
        case = next(row for row in self.regression["cases"] if row["candidates"])
        initial = common.infer_graph({"cases": [case], "distinct_pairs": []}, [])["records"][0]
        packet = common.reviewer_packet(case, [case], {"cases": [case], "distinct_pairs": []}, initial)
        result = common.validate_reviewer({
            "verdict": "resolve",
            "accepted_candidate_key": "null",
            "direct_identity_support": ["not-supplied"],
            "identity_contradictions": [],
            "reason_types": ["direct_identity_evidence"],
        }, packet)
        self.assertFalse(result["valid"])
        self.assertIn("literal_null_invalid:accepted_candidate_key", result["errors"])
        self.assertTrue(any(error.startswith("evidence_reference_invalid") for error in result["errors"]))

    def test_invalid_reviewer_payload_does_not_change_identity_state(self):
        graph = {
            "cases": [{
                "mention_id": "m1",
                "occurrence_id": "o1",
                "story_id": "s1",
                "target_surface": "甲",
                "occurrence_type": "abbreviated_person_name",
                "candidates": [{"candidate_key": "c0", "display_name": "甲人", "person_id": "person-a", "candidate_node_id": "person:person-a"}],
                "deterministic_predicates": [],
                "psl1_hard_vetoes": {},
            }],
            "distinct_pairs": [],
        }
        initial = common.infer_graph(graph, [])["records"]
        final = common.apply_reviewer(initial and {"records": initial}, [{
            "mention_id": "m1",
            "validation": {"valid": False, "errors": ["accepted_candidate_key_invalid"]},
            "payload": {"verdict": "resolve", "accepted_candidate_key": "null"},
        }], graph)
        self.assertEqual(final["records"][0]["result_state"], initial[0]["result_state"])
        self.assertFalse(final["records"][0].get("reviewer_resolved", False))

    def test_contradictory_coreference_orientations_are_excluded(self):
        graph = {
            "cases": [
                {"mention_id": "m1", "occurrence_id": "o1", "story_id": "s", "target_surface": "甲", "candidates": [{"candidate_key": "c0", "display_name": "甲人", "person_id": "p", "candidate_node_id": "person:p"}], "deterministic_predicates": [], "psl1_hard_vetoes": {}},
                {"mention_id": "m2", "occurrence_id": "o2", "story_id": "s", "target_surface": "其", "candidates": [{"candidate_key": "c0", "display_name": "甲人", "person_id": "p", "candidate_node_id": "person:p"}], "deterministic_predicates": [], "psl1_hard_vetoes": {}},
            ],
            "distinct_pairs": [],
        }
        result = common.infer_graph(graph, [
            {"predicate": "Coreference", "mention_id": "m1", "other_mention_id": "m2", "value": 1.0, "evidence_ids": ["e0"]},
            {"predicate": "Coreference", "mention_id": "m2", "other_mention_id": "m1", "value": 0.0, "evidence_ids": ["e1"]},
        ])
        self.assertEqual(len(result["coreference_pair_conflicts"]), 1)
        self.assertEqual(result["records"][0]["coreference_pair_conflicts"][0]["reason"], "contradictory_duplicate_orientations")

    def test_validator_accepts_frozen_graphs(self):
        result = validator.validate(self.selection, self.regression, self.holdout)
        self.assertTrue(result["valid"], result["errors"])

    def test_safety_metrics_have_no_false_surface_merge(self):
        decisions = common.infer_graph(self.regression, [])
        safety = common.safety_metrics([self.regression, self.holdout], decisions["records"], [])
        self.assertEqual(safety["same_surface_automatic_merges"], 0)
        self.assertEqual(safety["compositional_base_person_collapses"], 0)
        self.assertEqual(safety["nonperson_person_id_anomalies"], 0)
        self.assertEqual(safety["non_identity_self_relations"], 0)

    def test_safety_metrics_detect_non_identity_self_relation_edges(self):
        graph = {
            "cases": [{
                "mention_id": "m1",
                "known_relation_predicates": [{
                    "other_mention_id": "m2",
                    "candidate_node_id": "person:p",
                    "other_candidate_node_id": "person:p",
                }],
            }],
        }
        safety = common.safety_metrics([graph], [], [])
        self.assertEqual(safety["non_identity_self_relations"], 1)


if __name__ == "__main__":
    unittest.main()
