import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import hdb2_occurrence_common as occurrence
import hdb2_p2t_common as p2t


class HDB2P2TTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = p2t.build_cases()
        cls.selection = p2t.build_selection(cls.document)

    def test_exactly_forty_new_occurrences(self):
        self.assertEqual(self.document["occurrence_count"], 40)
        self.assertEqual(len(self.selection["cases"]), 40)
        p11 = occurrence.read_json(occurrence.ANNOTATION / "hdb2-p1-1-occurrence-selection.json", {}) or {}
        p11_ids = {str(row.get("identity_observation_id")) for row in p11.get("cases", [])}
        selected_ids = {str(row.get("identity_observation_id")) for row in self.selection["cases"]}
        self.assertTrue(selected_ids.isdisjoint(p11_ids))
        self.assertEqual(len(selected_ids), 40)
        self.assertTrue(self.selection["candidate_only"])
        self.assertFalse(self.selection["canonical_write_back"])

    def test_registered_normalized_witness_preserves_frozen_occurrence_span(self):
        case = next(row for row in self.document["cases"] if row.get("target_surface") == "即公大兄無奕女")
        self.assertTrue(any(
            row.get("source_layer") == "legacy_local_normalized"
            and case["exact_span"] in str(row.get("text") or "")
            for row in case.get("evidence_items", [])
        ))

    def test_cascade_has_python_and_llm_branches(self):
        results = [p2t.deterministic_cascade(case) for case in self.document["cases"]]
        stages = {str(row.get("cascade_stage")) for row in results}
        self.assertIn("python_explicit", stages)
        self.assertIn("python_structural", stages)
        self.assertIn("llm_contextual", stages)
        self.assertTrue(any(row.get("status") == "compositional_reference" for row in results))

    def test_compositional_reference_never_resolves_base(self):
        cases = [case for case in self.document["cases"] if case.get("occurrence_type") == "kinship_compositional_reference"]
        self.assertGreaterEqual(len(cases), 5)
        for case in cases:
            result = p2t.deterministic_cascade(case)
            self.assertEqual(result["status"], "compositional_reference")
            self.assertIsNone(result.get("resolved_person_id"))
            self.assertFalse(result.get("llm_called"))

    def test_wire_packets_do_not_expose_person_ids_or_prior_answers(self):
        for case in self.document["cases"]:
            packet = occurrence.wire_case(case)
            rendered = str(packet)
            self.assertNotIn("person_id", rendered)
            self.assertNotIn("provisional_person_id", rendered)
            self.assertNotIn("surface_cluster_decision", rendered)
            self.assertNotIn("person-", rendered)

    def test_literal_null_candidate_key_is_rejected(self):
        case = next(case for case in self.document["cases"] if p2t.deterministic_cascade(case).get("cascade_stage") == "llm_contextual")
        evidence_id = case["evidence_items"][0]["evidence_id"]
        payload = {
            "decision": "unresolved",
            "candidate_key": "null",
            "confidence": "low",
            "support": [{"support_type": "annotation_context", "evidence_ids": [evidence_id]}],
            "against": [],
            "reason_code": "insufficient_context",
        }
        validation = occurrence.validate_model_payload(payload, case)
        self.assertFalse(validation["valid"])
        self.assertIn("candidate_key_must_be_null_outside_candidate", validation["errors"])
        result = p2t.apply_llm_result(case, payload, validation)
        self.assertEqual(result["status"], "unresolved")

    def test_two_support_families_are_required_for_contextual_resolution(self):
        case = next(case for case in self.document["cases"] if p2t.deterministic_cascade(case).get("cascade_stage") == "llm_contextual" and len(case.get("candidates", [])) >= 2)
        candidate = case["candidates"][0]
        evidence_id = case["evidence_items"][0]["evidence_id"]
        payload = {
            "decision": "candidate",
            "candidate_key": candidate["candidate_key"],
            "confidence": "high",
            "support": [{"support_type": "social_context", "evidence_ids": [evidence_id]}],
            "against": [],
            "reason_code": "single_context_support",
        }
        validation = occurrence.validate_model_payload(payload, case)
        self.assertEqual(p2t.apply_llm_result(case, payload, validation)["status"], "contextually_preferred")

    def test_candidate_only_outputs_have_final_state_enum(self):
        allowed = p2t.FINAL_STATUSES
        for case in self.document["cases"]:
            result = p2t.deterministic_cascade(case)
            if result.get("llm_called"):
                continue
            self.assertIn(result.get("status"), allowed)
            self.assertTrue(result.get("candidate_only"))
            self.assertFalse(result.get("canonical_write_back"))


if __name__ == "__main__":
    unittest.main()
