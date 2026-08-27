import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import hdb2_psl1_3_common as common  # noqa: E402
import validate_hdb2_psl1_3 as validator  # noqa: E402


class HDB2PSL13Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selection = common.freeze_selection()
        cls.interfaces = common.interface_regression_records()

    def _packet(self, *, surface="康伯", candidates=None):
        return {
            "task": "candidate rescue interface classification",
            "mention": {"surface": surface},
            "candidates": candidates if candidates is not None else [{
                "candidate_key": "c0",
                "name": "韓伯",
                "aliases": ["康伯"],
                "courtesy_names": [],
                "titles": [],
            }],
            "evidence_items": [
                {
                    "evidence_id": "ev0",
                    "family": "relevant_source_evidence",
                    "text": "韓伯字康伯",
                },
                {
                    "evidence_id": "ev1",
                    "family": "story_local_context",
                    "text": "康伯與客語",
                },
            ],
            "candidate_only": True,
            "canonical_write_back": False,
        }

    def _valid(self, **updates):
        payload = {
            "surface_type": "courtesy_name",
            "referent_type": "person",
            "candidate_assessments": [{
                "candidate_key": "c0",
                "supported_as_referent": True,
                "supporting_evidence_ids": ["ev0"],
            }],
            "candidate_set_supported": True,
            "diagnosis": "candidate_set_sufficient",
            "proposed_identity_surface": None,
            "search_hints": [],
            "supporting_evidence_ids": ["ev0"],
        }
        payload.update(updates)
        return payload

    def test_selection_is_frozen_exactly_ten_distinct_unseen_stories(self):
        self.assertEqual(self.selection.get("schema"), "hdb2-psl1-3-selection-v1")
        self.assertEqual(self.selection.get("independent_count"), 10)
        self.assertEqual(self.selection.get("distinct_story_count"), 10)
        self.assertTrue(self.selection.get("frozen_before_live"))
        self.assertTrue(self.selection.get("candidate_only"))
        self.assertFalse(self.selection.get("canonical_write_back"))
        rows = self.selection["independent_cases"]
        self.assertEqual(len({row["occurrence_id"] for row in rows}), 10)
        self.assertEqual(len({row["story_id"] for row in rows}), 10)
        excluded = set(self.selection["excluded_previous_occurrence_ids"])
        self.assertFalse(excluded & {row["occurrence_id"] for row in rows})
        self.assertTrue(all(row["previous_hng2_excluded"] is False for row in rows))
        with tempfile.TemporaryDirectory() as directory:
            rebuilt = common.build_selection(Path(directory) / "selection.json")
        self.assertEqual(rebuilt, self.selection)

    def test_rescue_function_is_strict_and_every_wire_field_is_described(self):
        function = common.rescue_tool()["function"]
        self.assertTrue(function["strict"])
        parameters = function["parameters"]
        self.assertFalse(parameters["additionalProperties"])
        self.assertEqual(set(parameters["required"]), set(parameters["properties"]))
        self.assertEqual(common.rescue_tool_choice()["function"]["name"], common.RESCUE_FUNCTION_NAME)
        for name, schema in parameters["properties"].items():
            self.assertTrue(schema.get("description"), name)
        nested = parameters["properties"]["candidate_assessments"]["items"]
        self.assertFalse(nested["additionalProperties"])
        self.assertEqual(set(nested["required"]), set(nested["properties"]))

    def test_valid_explicit_candidate_support_and_ruler_reference(self):
        result = common.validate_rescue_interface(self._valid(), self._packet())
        self.assertTrue(result["valid"], result["errors"])
        ruler_packet = self._packet(surface="陛下", candidates=[])
        ruler = {
            "surface_type": "ruler_title",
            "referent_type": "ruler",
            "candidate_assessments": [],
            "candidate_set_supported": False,
            "diagnosis": "insufficient_evidence",
            "proposed_identity_surface": None,
            "search_hints": [],
            "supporting_evidence_ids": [],
        }
        ruler_packet["evidence_items"] = [{"evidence_id": "ev0", "family": "story_local_context", "text": "陛下"}]
        result = common.validate_rescue_interface(ruler, ruler_packet)
        self.assertTrue(result["valid"], result["errors"])

    def test_candidate_set_sufficient_requires_direct_grounded_support(self):
        payload = self._valid(candidate_assessments=[{
            "candidate_key": "c0",
            "supported_as_referent": True,
            "supporting_evidence_ids": ["ev1"],
        }])
        result = common.validate_rescue_interface(payload, self._packet())
        self.assertFalse(result["valid"])
        self.assertIn("candidate_support_not_explicit:c0", result["errors"])

    def test_missing_candidate_surface_and_hints_must_be_visible(self):
        payload = self._valid(
            candidate_assessments=[],
            candidate_set_supported=False,
            diagnosis="candidate_missing_likely",
            proposed_identity_surface="韓伯",
            search_hints=["韓伯"],
            supporting_evidence_ids=["ev0"],
        )
        self.assertTrue(common.validate_rescue_interface(payload, self._packet())["valid"])
        invalid = copy.deepcopy(payload)
        invalid["proposed_identity_surface"] = "外部人物"
        invalid["search_hints"] = ["外部人物"]
        result = common.validate_rescue_interface(invalid, self._packet())
        self.assertFalse(result["valid"])
        self.assertIn("proposed_identity_surface_not_grounded", result["errors"])
        self.assertIn("search_hint_not_grounded:外部人物", result["errors"])

    def test_unknown_candidate_evidence_literal_null_and_fields_fail_closed(self):
        payload = self._valid(
            candidate_assessments=[{
                "candidate_key": "null",
                "supported_as_referent": True,
                "supporting_evidence_ids": ["not-supplied"],
            }],
            proposed_identity_surface="null",
            unexpected=True,
        )
        result = common.validate_rescue_interface(payload, self._packet())
        self.assertFalse(result["valid"])
        self.assertIn("candidate_key_invalid:null", result["errors"])
        self.assertIn("evidence_reference_invalid:candidate:not-supplied", result["errors"])
        self.assertIn("literal_null_invalid:proposed_identity_surface", result["errors"])
        self.assertIn("unknown_field:unexpected", result["errors"])
        with_id = copy.deepcopy(self._valid())
        with_id["person_id"] = "person-001"
        self.assertIn("forbidden_id_field:person_id", common.validate_rescue_interface(with_id, self._packet())["errors"])

    def test_reference_not_person_requires_non_person_referent(self):
        payload = self._valid(
            candidate_assessments=[],
            candidate_set_supported=False,
            diagnosis="reference_not_person",
            proposed_identity_surface=None,
        )
        result = common.validate_rescue_interface(payload, self._packet())
        self.assertFalse(result["valid"])
        self.assertIn("reference_not_person_requires_non_person_referent", result["errors"])
        payload["referent_type"] = "non_person"
        result = common.validate_rescue_interface(payload, self._packet())
        self.assertTrue(result["valid"], result["errors"])

    def test_required_false_and_interface_regressions_pass_offline(self):
        self.assertTrue(common.required_regression_records()["all_pass"])
        self.assertTrue(common.false_resolution_regression()["all_pass"])
        self.assertTrue(self.interfaces["all_pass"], self.interfaces)
        expected = {"劉尹", "朕", "陛下", "中丞", "阮光禄", "聘", "鳯"}
        self.assertEqual({row["surface"] for row in self.interfaces["records"]}, expected)

    def test_grounded_interface_regressions_include_direction_and_variant_candidates(self):
        records = {row["surface"]: row for row in self.interfaces["records"]}
        self.assertIn("謝聘", records["聘"]["grounded_candidates"] + records["聘"]["grounded_resource_candidates"])
        self.assertIn("謝鳳", records["鳯"]["grounded_candidates"] + records["鳯"]["grounded_resource_candidates"])
        self.assertIn("阮裕", records["阮光禄"]["grounded_candidates"] + records["阮光禄"]["grounded_resource_candidates"])
        self.assertIn("髙靈", records["中丞"]["grounded_resource_candidates"])

    def test_rescue_packet_is_candidate_only_and_has_no_provider_identity_id(self):
        graph = common.build_graph(self.selection)
        packet = common.rescue_packet(graph["cases"][0], {"result_state": "review_required", "candidate_rankings": []}, graph)
        rendered = json.dumps(packet, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("person_id", rendered)
        self.assertNotIn("candidate_id", rendered)
        self.assertTrue(packet["candidate_only"])
        self.assertFalse(packet["canonical_write_back"])

    def test_offline_validator_passes(self):
        result = validator.validate()
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["selection_count"], 10)


if __name__ == "__main__":
    unittest.main()
