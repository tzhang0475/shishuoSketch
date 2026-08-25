import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import hdb2_occurrence_common as common


class HDB2OccurrenceDisambiguationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = common.build_cases()

    def test_selection_is_occurrence_level_and_covers_required_surfaces(self):
        cases = self.document["cases"]
        self.assertGreaterEqual(len(cases), 20)
        self.assertLessEqual(len(cases), 30)
        self.assertEqual(len({case["occurrence_id"] for case in cases}), len(cases))
        surfaces = {case["target_surface"] for case in cases}
        self.assertTrue(set(common.REQUIRED_SURFACES).issubset(surfaces))
        qiao_cases = [case for case in cases if case["target_surface"] == "嶠"]
        self.assertGreaterEqual(len(qiao_cases), 2)
        self.assertGreaterEqual(len({case["story_id"] for case in qiao_cases}), 2)

    def test_wire_case_does_not_expose_production_person_ids(self):
        for case in self.document["cases"]:
            wire = common.wire_case(case)
            rendered = str(wire)
            self.assertNotIn("person_id", rendered)
            self.assertNotIn("provisional_person_id", rendered)
            self.assertNotIn("person-", rendered)
            self.assertTrue(all(str(key).startswith("c") and str(key)[1:].isdigit() for key in case["candidate_keys"]))

    def test_strict_function_is_closed_and_local(self):
        function = common.strict_tool()["function"]
        params = function["parameters"]
        self.assertTrue(function["strict"])
        self.assertFalse(params["additionalProperties"])
        self.assertEqual(set(params["required"]), set(params["properties"]))
        self.assertNotIn("person_id", str(function))
        self.assertEqual(common.tool_choice(), {"type": "function", "function": {"name": "submit_hdb2_occurrence_identity_decision"}})

    def test_compositional_kinship_never_resolves_base(self):
        case = next(case for case in self.document["cases"] if case["target_surface"] == "庾亮兒")
        base = next(candidate for candidate in case["candidates"] if candidate.get("person_id") == "person-010")
        payload = {
            "decision": "candidate",
            "candidate_key": base["candidate_key"],
            "confidence": "high",
            "support": [{"support_type": "kinship_context", "evidence_ids": [case["evidence_items"][0]["evidence_id"]]}],
            "against": [],
            "reason_code": "single_context_support",
        }
        validation = common.validate_model_payload(payload, case)
        result = common.python_decision(case, payload, validation)
        self.assertTrue(validation["valid"])
        self.assertEqual(result["status"], "compositional_reference")
        self.assertIsNone(result["resolved_person_id"])
        self.assertIn("compositional_base_person_rejected", result["hard_constraint_rejections"])

    def test_support_family_threshold_is_python_owned(self):
        case = next(case for case in self.document["cases"] if case["target_surface"] == "嶠")
        candidate = case["candidates"][0]
        evidence_ids = [item["evidence_id"] for item in case["evidence_items"]]
        one_family = {
            "decision": "candidate", "candidate_key": candidate["candidate_key"], "confidence": "high",
            "support": [{"support_type": "social_context", "evidence_ids": evidence_ids[:1]}],
            "against": [], "reason_code": "single_context_support",
        }
        two_families = dict(one_family)
        two_families["support"] = [
            {"support_type": "social_context", "evidence_ids": evidence_ids[:1]},
            {"support_type": "annotation_context", "evidence_ids": evidence_ids[:1]},
        ]
        self.assertEqual(common.python_decision(case, one_family, common.validate_model_payload(one_family, case))["status"], "contextually_preferred")
        self.assertEqual(common.python_decision(case, two_families, common.validate_model_payload(two_families, case))["status"], "contextually_resolved")

    def test_invalid_candidate_and_evidence_are_rejected(self):
        case = self.document["cases"][0]
        payload = {
            "decision": "candidate", "candidate_key": "c999", "confidence": "high",
            "support": [{"support_type": "social_context", "evidence_ids": ["missing"]}],
            "against": [], "reason_code": "single_context_support",
        }
        result = common.validate_model_payload(payload, case)
        self.assertFalse(result["valid"])
        self.assertIn("candidate_key_invalid", result["errors"])
        self.assertIn("evidence_reference_invalid", result["errors"])

    def test_non_person_and_ruler_type_gates_are_generic(self):
        case = next(case for case in self.document["cases"] if case["target_surface"] == "帝")
        person = next((candidate for candidate in case["candidates"] if candidate.get("semantic_type") == "person"), None)
        if person:
            evidence_id = case["evidence_items"][0]["evidence_id"]
            payload = {
                "decision": "candidate", "candidate_key": person["candidate_key"], "confidence": "high",
                "support": [{"support_type": "ruler_context", "evidence_ids": [evidence_id]}],
                "against": [], "reason_code": "single_context_support",
            }
            result = common.python_decision(case, payload, common.validate_model_payload(payload, case))
            self.assertEqual(result["status"], "unresolved")
            self.assertIn("ruler_reference_candidate_type_conflict", result["hard_constraint_rejections"])


if __name__ == "__main__":
    unittest.main()
