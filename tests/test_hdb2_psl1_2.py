import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import hdb2_psl1_2_common as common  # noqa: E402
import hdb2_psl1_common as psl1  # noqa: E402
import validate_hdb2_psl1_2 as validator  # noqa: E402


class HDB2PSL12Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selection = common.freeze_selection()

    def test_selection_is_exactly_twelve_and_frozen(self):
        self.assertEqual(self.selection.get("independent_count"), 12)
        self.assertEqual(len(self.selection.get("independent_cases", [])), 12)
        self.assertTrue(self.selection.get("frozen_before_live"))
        self.assertTrue(self.selection.get("candidate_only"))
        self.assertFalse(self.selection.get("canonical_write_back"))
        ids = [row.get("occurrence_id") for row in self.selection["independent_cases"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertFalse(set(ids) & set(self.selection["excluded_previous_occurrence_ids"]))
        rebuilt = common.freeze_selection()
        self.assertEqual(rebuilt, self.selection)

    def test_rescue_function_is_strict_and_closed(self):
        function = common.rescue_tool()["function"]
        self.assertTrue(function["strict"])
        parameters = function["parameters"]
        self.assertFalse(parameters["additionalProperties"])
        self.assertEqual(set(parameters["required"]), set(parameters["properties"]))
        self.assertEqual(common.rescue_tool_choice()["function"]["name"], common.RESCUE_FUNCTION_NAME)

    def _packet(self):
        return {
            "evidence_items": [
                {"evidence_id": "ev0", "text": "韓伯字康伯"},
                {"evidence_id": "ev1", "text": "康伯"},
            ],
        }

    def _valid_diagnosis(self, **updates):
        payload = {
            "diagnosis": "candidate_missing_likely",
            "proposed_identity_surface": "韓伯",
            "reference_type": "person",
            "search_hints": ["韓伯"],
            "supporting_evidence_ids": ["ev0"],
        }
        payload.update(updates)
        return payload

    def test_rescue_diagnosis_requires_grounded_proposed_surface(self):
        result = common.validate_rescue_diagnosis(self._valid_diagnosis(), self._packet())
        self.assertTrue(result["valid"], result["errors"])
        result = common.validate_rescue_diagnosis(
            self._valid_diagnosis(proposed_identity_surface="外部人物"), self._packet()
        )
        self.assertFalse(result["valid"])
        self.assertIn("proposed_identity_surface_not_grounded", result["errors"])

    def test_rescue_diagnosis_rejects_literal_null_unknown_evidence_and_fields(self):
        result = common.validate_rescue_diagnosis(
            self._valid_diagnosis(
                proposed_identity_surface="null",
                supporting_evidence_ids=["not-supplied"],
                unexpected=True,
            ),
            self._packet(),
        )
        self.assertFalse(result["valid"])
        self.assertIn("literal_null_invalid:proposed_identity_surface", result["errors"])
        self.assertIn("evidence_reference_invalid:not-supplied", result["errors"])
        self.assertIn("unknown_field:unexpected", result["errors"])

    def test_rescue_trigger_is_limited_to_open_or_rejected_states(self):
        self.assertTrue(common.rescue_trigger({"result_state": "review_required"}))
        self.assertTrue(common.rescue_trigger({"result_state": "genuinely_unresolved"}))
        self.assertTrue(common.rescue_trigger({"result_state": "stable_entity_resolved", "reviewer_rejected_top_candidate": True}))
        self.assertFalse(common.rescue_trigger({"result_state": "stable_entity_resolved"}))

    def test_non_missing_diagnoses_do_not_propose_a_surface(self):
        payload = self._valid_diagnosis(
            diagnosis="candidate_set_sufficient",
            proposed_identity_surface=None,
        )
        result = common.validate_rescue_diagnosis(payload, self._packet())
        self.assertTrue(result["valid"], result["errors"])

    def test_non_direct_resources_cannot_add_rescue_candidates(self):
        case = {
            "target_surface": "帝",
            "candidates": [],
        }
        diagnosis = {
            "diagnosis": "candidate_missing_likely",
            "proposed_identity_surface": "晉明帝",
        }
        resources = [{
            "target_surface": "帝",
            "candidate_surface": "晉明帝",
            "person_id": None,
            "direct_identity_support": False,
            "basis": "ruler_registry_projection",
        }]
        found = common.find_grounded_rescue_candidates(case, diagnosis, resources)
        self.assertEqual(found["candidates"], [])

    def test_invalid_rescue_payload_is_not_state_mutation(self):
        graph = {
            "cases": [{
                "occurrence_id": "o1",
                "mention_id": "m1",
                "candidates": [],
                "candidate_keys": [],
            }],
            "candidate_only": True,
            "canonical_write_back": False,
        }
        record = {
            "mention_id": "m1",
            "payload": self._valid_diagnosis(proposed_identity_surface="not-visible"),
            "validation": {"valid": False, "errors": ["proposed_identity_surface_not_grounded"]},
        }
        updated, diagnoses, provenance = __import__("run_hdb2_psl1_2")._add_grounded_candidates(graph, [record], [])
        self.assertEqual(updated, graph)
        self.assertEqual(provenance, [])
        self.assertFalse(diagnoses[0]["validation"]["valid"])

    def test_required_recovery_and_false_resolution_regressions_pass_offline(self):
        required = common.required_regression_records()
        self.assertTrue(required["all_pass"], required)
        self.assertEqual({row["surface"] for row in required["records"]}, {"宣王", "祖車騎", "孔廷尉", "劉尹"})
        false_cases = common.false_resolution_regression()
        self.assertTrue(false_cases["all_pass"], false_cases)
        self.assertEqual(len(false_cases["records"]), 3)

    def test_rescue_candidate_is_candidate_only_and_source_provenanced(self):
        graph = {
            "cases": [{
                "occurrence_id": "o1",
                "mention_id": "m1",
                "target_surface": "康伯",
                "occurrence_type": "abbreviated_person_name",
                "candidates": [],
                "candidate_keys": [],
                "evidence_items": [],
                "psl1_hard_vetoes": {},
                "psl1_1_role_vetoes": {},
            }],
            "candidate_only": True,
            "canonical_write_back": False,
        }
        grounded = {
            "candidates": [{
                "candidate_surface": "韓伯",
                "person_id": None,
                "candidate_kind": "source_named_entity",
                "basis": "grounded_identity_statement",
                "direct_identity_support": True,
                "evidence": [{
                    "resource_id": "res0",
                    "source_ref": "jinshu-1",
                    "exact_span": "韓伯字康伯",
                }],
            }],
        }
        updated, provenance = common.add_rescue_candidates(graph, "o1", grounded)
        candidate = updated["cases"][0]["candidates"][0]
        self.assertEqual(candidate["display_name"], "韓伯")
        self.assertIsNone(candidate["person_id"])
        self.assertTrue(candidate["candidate_node_id"].startswith("local:"))
        self.assertTrue(updated["candidate_only"])
        self.assertFalse(updated["canonical_write_back"])
        self.assertEqual(provenance[0]["basis"], "grounded_identity_statement")
        self.assertEqual(updated["cases"][0]["evidence_items"][0]["text"], "韓伯字康伯")

    def test_validator_passes_frozen_offline_contract(self):
        result = validator.validate()
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["selection_count"], 12)

    def test_rescue_packet_does_not_expose_provider_ids(self):
        selection = self.selection
        graph = common.build_graph(selection)
        case = graph["cases"][0]
        decision = {"result_state": "review_required", "candidate_rankings": []}
        packet = common.rescue_packet(case, decision, graph)
        rendered = json.dumps(packet, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("person_id", rendered)
        self.assertNotIn("candidate_id", rendered)
        self.assertTrue(packet["candidate_only"])
        self.assertFalse(packet["canonical_write_back"])

    def test_rescue_audit_keeps_initial_candidates_separate_from_rescued_candidates(self):
        runner = __import__("run_hdb2_psl1_2")
        graph = {
            "cases": [{
                "mention_id": "m1",
                "occurrence_id": "o1",
                "story_id": "story-1",
                "target_surface": "康伯",
                "candidates": [],
            }],
        }
        before = {
            "records": [{
                "mention_id": "m1",
                "result_state": "review_required",
                "top_candidate": "甲",
                "candidate_rankings": [{
                    "candidate_key": "c0",
                    "candidate": "甲",
                    "candidate_person_id": "person-1",
                    "candidate_node_id": "person:person-1",
                }],
            }],
        }
        final = {
            "records": [{
                "mention_id": "m1",
                "result_state": "stable_entity_resolved",
                "top_candidate": "乙",
                "top_candidate_person_id": None,
                "reviewer_verdict": "resolve",
            }],
        }
        audit = runner._rescue_audit(
            graph=graph,
            after_review=before,
            final=final,
            diagnoses=[{
                "mention_id": "m1",
                "diagnosis": "candidate_missing_likely",
                "proposed_identity_surface": "乙",
                "validation": {"valid": True, "errors": []},
            }],
            provenance=[{
                "mention_id": "m1",
                "occurrence_id": "o1",
                "candidate_surface": "乙",
                "person_id": None,
                "direct_identity_support": True,
                "evidence": [],
            }],
        )
        row = audit["records"][0]
        self.assertEqual(row["initial_candidate_set"][0]["candidate"], "甲")
        self.assertEqual(row["rescued_candidates"][0]["candidate_surface"], "乙")
        self.assertTrue(row["rescue_changed_decision"])
        self.assertTrue(audit["candidate_only"])
        self.assertFalse(audit["canonical_write_back"])


if __name__ == "__main__":
    unittest.main()
