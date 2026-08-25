import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_hdb2_full_frontier as builder
import hdb2_full_frontier_common as common
import hdb2_occurrence_common as occurrence
import hdb2_p2t_common as p2t


class HDB2FullFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger, cls.selection, cls.cases = builder.build(write=False)

    def test_frontier_partition_and_frozen_counts(self):
        self.assertEqual(self.ledger["counts"]["total"], 425)
        self.assertEqual(self.ledger["counts"]["hdb1_direct_existing"], 198)
        self.assertEqual(self.ledger["counts"]["prior_decisions_reused"], 65)
        self.assertEqual(self.ledger["counts"]["hdb2_f_live_frontier"], 162)
        self.assertEqual(self.selection["remaining_hdb2_f_live_frontier"], 162)
        self.assertEqual(self.cases["occurrence_count"], 162)

    def test_frontier_excludes_prior_occurrence_decisions(self):
        selected = {str(x["identity_observation_id"]) for x in self.selection["cases"]}
        prior = set()
        for path in (common.ANNOTATION / "hdb2-p1-1-occurrence-selection.json", common.ANNOTATION / "hdb2-p2t-occurrence-selection.json"):
            doc = common.read_json(path, {}) or {}
            prior |= {str(x.get("identity_observation_id")) for x in doc.get("cases", [])}
        self.assertTrue(selected.isdisjoint(prior))

    def test_model_packets_are_local_key_only(self):
        for case in self.cases["cases"]:
            packet = occurrence.user_prompt(case)
            rendered = json.dumps(packet, ensure_ascii=False, sort_keys=True)
            self.assertNotIn("person_id", rendered)
            self.assertNotIn("provisional_person_id", rendered)
            self.assertNotIn("person-", rendered)
            self.assertTrue(all(str(x.get("candidate_key", "")).startswith("c") for x in case.get("candidates", [])))

    def test_compositional_occurrences_do_not_resolve_base(self):
        cases = [x for x in self.cases["cases"] if x.get("occurrence_type") == "kinship_compositional_reference"]
        self.assertGreaterEqual(len(cases), 5)
        for case in cases:
            result = common.deterministic_cascade(case)
            self.assertEqual(result.get("status"), "compositional_reference")
            self.assertIsNone(result.get("resolved_person_id"))

    def test_contextual_threshold_is_frozen(self):
        case = next(x for x in self.cases["cases"] if p2t.deterministic_cascade(x).get("llm_called"))
        candidate = case["candidates"][0]
        evidence = case["evidence_items"][0]["evidence_id"]
        payload = {"decision": "candidate", "candidate_key": candidate["candidate_key"], "confidence": "high", "support": [{"support_type": "social_context", "evidence_ids": [evidence]}], "against": [], "reason_code": "single_context_support"}
        validation = occurrence.validate_model_payload(payload, case)
        result = common.apply_contextual(case, payload, validation)
        self.assertEqual(result["status"], "contextually_preferred")

    def test_endpoint_self_relations_are_rejected(self):
        from build_hdb2_full_projection import _endpoint_state
        self.assertEqual(_endpoint_state({"type": "existing", "person_id": "person-001"}, {"type": "existing", "person_id": "person-001"}), "rejected_self_relation")


if __name__ == "__main__":
    unittest.main()

