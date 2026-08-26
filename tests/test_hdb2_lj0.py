import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import hdb2_lj0_common as common  # noqa: E402
import validate_hdb2_lj0 as validator  # noqa: E402


class HDB2LJ0Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selection_path = ROOT / "data/annotation/hdb2-lj0-selection.json"
        cls.selection = json.loads(cls.selection_path.read_text(encoding="utf-8"))
        cls.cases = common.build_cases(cls.selection)["cases"]

    def test_selection_is_frozen_and_representative(self):
        self.assertTrue(self.selection["frozen_before_live"])
        self.assertTrue(self.selection["candidate_only"])
        self.assertFalse(self.selection["canonical_write_back"])
        self.assertEqual(len(self.selection["cases"]), 24)
        self.assertEqual(len({row["occurrence_id"] for row in self.selection["cases"]}), 24)
        self.assertTrue(any(row["story_id"] == "05-fangzheng-011" and row["surface"] == "武帝" for row in self.selection["cases"]))
        categories = {row["selection_category"] for row in self.selection["cases"]}
        self.assertTrue({"candidate_person", "compositional_reference", "office_title_holder", "ambiguous_identity"} <= categories)

    def test_selection_rebuild_is_byte_stable(self):
        rebuilt = common.build_selection(common.load_review_items(), limit=24)
        self.assertEqual(rebuilt, self.selection)

    def test_model_packet_uses_local_candidate_keys_only(self):
        for case in self.cases:
            packet = common.wire_packet(case)
            rendered = json.dumps(packet, ensure_ascii=False, sort_keys=True)
            self.assertNotIn("person_id", rendered)
            self.assertNotIn("provisional_person_id", rendered)
            self.assertNotIn("relation_id", rendered)
            self.assertTrue(all(str(row.get("candidate_key", "")).startswith("c") for row in packet["candidates"]))
            self.assertTrue(all(row.get("evidence_id") for row in packet["evidence_items"]))

    def test_strict_tools_have_closed_required_objects(self):
        for tool in (common.evaluation_tool(), common.falsification_tool()):
            params = tool["function"]["parameters"]
            self.assertFalse(params["additionalProperties"])
            self.assertEqual(set(params["required"]), set(params["properties"]))

    def test_unknown_candidate_and_evidence_are_rejected(self):
        case = next(case for case in self.cases if len(case["candidate_keys"]) >= 1 and case["evidence_items"])
        key = case["candidate_keys"][0]
        payload = {
            "candidate_evaluations": [{
                "candidate_key": "c999",
                "family_assessments": [{"family": "story_local_context", "state": "support", "evidence_ids": ["ev999"]}],
                "cross_story_consistency": "compatible",
                "hard_conflict": False,
            }],
            "leading_candidate_key": "null",
            "note": "",
        }
        result = common.validate_evaluation(payload, {**case, "candidate_keys": [key]})
        self.assertFalse(result["valid"])
        self.assertIn("candidate_key_invalid:c999", result["errors"])
        self.assertIn("evidence_reference_invalid:ev999", result["errors"])
        self.assertIn("leading_candidate_key_invalid", result["errors"])

    def test_score_can_resolve_without_explicit_name_family(self):
        case = next(case for case in self.cases if len(case["candidate_keys"]) >= 2 and len(case["evidence_items"]) >= 2)
        keys = case["candidate_keys"]
        ids = [row["evidence_id"] for row in case["evidence_items"][:2]]
        rows = []
        for key in keys:
            rows.append({
                "candidate_key": key,
                "family_assessments": [],
                "cross_story_consistency": "compatible",
                "hard_conflict": False,
            })
        rows[0]["family_assessments"] = [
            {"family": "relevant_source_evidence", "state": "strong_support", "evidence_ids": [ids[0]]},
            {"family": "person_relations_network", "state": "support", "evidence_ids": [ids[1]]},
        ]
        payload = {"candidate_evaluations": rows, "leading_candidate_key": keys[0], "note": ""}
        validation = common.validate_evaluation(payload, case)
        self.assertTrue(validation["valid"], validation["errors"])
        falsification = {"leading_candidate_key": keys[0], "contradiction_evidence_ids": [], "comparably_plausible_candidate_keys": [], "outcome": "survives", "note": ""}
        falsification_validation = common.validate_falsification(falsification, case, keys[0])
        self.assertTrue(falsification_validation["valid"], falsification_validation["errors"])
        result = common.score_evaluations(case, payload, falsification)
        self.assertEqual(result["result_state"], "high_confidence_contextual")
        self.assertGreaterEqual(result["ranked_candidates"][0]["identity_score"], common.MIN_HIGH_SCORE)

    def test_hard_falsification_vetoes_leading_candidate(self):
        case = next(case for case in self.cases if len(case["candidate_keys"]) >= 1 and len(case["evidence_items"]) >= 1)
        key = case["candidate_keys"][0]
        evidence_id = case["evidence_items"][0]["evidence_id"]
        rows = [{
            "candidate_key": candidate_key,
            "family_assessments": ([{"family": "story_local_context", "state": "strong_support", "evidence_ids": [evidence_id]}] if candidate_key == key else []),
            "cross_story_consistency": "compatible",
            "hard_conflict": False,
        } for candidate_key in case["candidate_keys"]]
        payload = {
            "candidate_evaluations": rows,
            "leading_candidate_key": key,
            "note": "",
        }
        self.assertTrue(common.validate_evaluation(payload, case)["valid"])
        falsification = {"leading_candidate_key": key, "contradiction_evidence_ids": [evidence_id], "comparably_plausible_candidate_keys": [], "outcome": "falsified", "note": ""}
        self.assertTrue(common.validate_falsification(falsification, case, key)["valid"])
        result = common.score_evaluations(case, payload, falsification)
        self.assertEqual(result["result_state"], "genuinely_unresolved")
        self.assertGreaterEqual(result["hard_conflicts_found"], 1)

    def test_grounded_strong_contradiction_vetoes_candidate(self):
        case = next(case for case in self.cases if len(case["candidate_keys"]) >= 1 and case["evidence_items"])
        key = case["candidate_keys"][0]
        evidence_id = case["evidence_items"][0]["evidence_id"]
        payload = {
            "candidate_evaluations": [{
                "candidate_key": candidate_key,
                "family_assessments": ([{
                    "family": "era_chronology",
                    "state": "strong_contradiction",
                    "evidence_ids": [evidence_id],
                }] if candidate_key == key else []),
                "cross_story_consistency": "compatible",
                "hard_conflict": False,
            } for candidate_key in case["candidate_keys"]],
            "leading_candidate_key": key,
            "note": "",
        }
        self.assertTrue(common.validate_evaluation(payload, case)["valid"])
        result = common.score_evaluations(case, payload, {"outcome": "inconclusive"})
        lead = next(row for row in result["ranked_candidates"] if row["candidate_key"] == key)
        self.assertTrue(lead["hard_conflict"])
        self.assertEqual(lead["identity_score"], -10000)

    def test_validator_accepts_frozen_selection(self):
        result = validator.validate(self.selection, {"cases": self.cases})
        self.assertTrue(result["valid"], result["errors"])


if __name__ == "__main__":
    unittest.main()
