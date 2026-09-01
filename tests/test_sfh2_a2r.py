from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_a0r.contracts import semantic_diff_paths  # noqa: E402
from sfh2_a2r import contracts  # noqa: E402
from sfh2_a2r.evaluation import is_common_mode_identity_error  # noqa: E402
from sfh2_a2r.transport import is_retryable  # noqa: E402


def _record() -> dict:
    return {
        "mention_id": "m",
        "surface": "甲",
        "semantic_kind": "historical_person",
        "reference_type": "full_name",
        "referent": {"surface_form": "甲", "canonical_hint": "乙", "confidence": "high"},
        "occurrence_role": "scene_reference",
        "discourse": {"speaker_hint": "", "addressee_hint": "", "antecedent_hint": "", "self_reference_hint": ""},
        "relations": [],
        "confidence": "high",
        "supporting_evidence_ids": ["ev"],
        "attribute_type": "",
        "attribute_value": "",
        "bearer_hint": "",
        "abstain": False,
        "explanation": "",
    }


class SFH22A2RTests(unittest.TestCase):
    def setUp(self) -> None:
        self.packet = {"source_evidence": [{"evidence_id": "ev", "text": "甲"}]}
        self.a = _record()
        self.b = copy.deepcopy(self.a)
        self.b["referent"] = {"surface_form": "甲", "canonical_hint": "丙", "confidence": "high"}

    def test_new_adjudicator_schema_has_no_redundant_base_record(self):
        tool = contracts.adjudicator_tool()
        encoded = json.dumps(tool, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("base_record", encoded)
        self.assertEqual([], contracts.validate_deepseek_strict_schema(tool["function"]["parameters"]))
        required = set(tool["function"]["parameters"]["required"])
        self.assertEqual(required, set(tool["function"]["parameters"]["properties"]))

    def test_decision_encoded_patch_conditions(self):
        common = {"reason_summary": "", "supporting_evidence_ids": []}
        for decision in ("select_a", "select_b", "abstain"):
            result = contracts.validate_adjudicator_payload(self.packet, {"decision": decision, "patch_ops": [], **common})
            self.assertTrue(result["valid"], (decision, result))
        for decision in ("revise_a", "revise_b"):
            result = contracts.validate_adjudicator_payload(self.packet, {"decision": decision, "patch_ops": [{"path": "referent.canonical_hint", "value": "丁"}], **common})
            self.assertTrue(result["valid"], (decision, result))
        invalid = contracts.validate_adjudicator_payload(self.packet, {"decision": "select_a", "patch_ops": [{"path": "referent.canonical_hint", "value": "丁"}], **common})
        self.assertFalse(invalid["valid"])
        invalid = contracts.validate_adjudicator_payload(self.packet, {"decision": "revise_a", "patch_ops": [], **common})
        self.assertFalse(invalid["valid"])

    def test_base_record_is_rejected_from_provider_payload(self):
        payload = {"decision": "select_a", "base_record": "historian_a", "patch_ops": [], "reason_summary": "", "supporting_evidence_ids": []}
        result = contracts.validate_adjudicator_payload(self.packet, payload)
        self.assertFalse(result["valid"])
        self.assertIn("base_record_forbidden", result["errors"])

    def test_select_a_and_select_b_are_exact_copies(self):
        for decision, source in (("select_a", self.a), ("select_b", self.b)):
            validated = contracts.validate_adjudicator_payload(self.packet, {"decision": decision, "patch_ops": [], "reason_summary": "", "supporting_evidence_ids": []})
            effective = contracts.apply_a2r_adjudication(self.a, self.b, {"valid": True, **validated["adjudication"]}, self.packet)
            self.assertTrue(effective["valid"])
            self.assertEqual(source, effective["record"])
            self.assertEqual([], semantic_diff_paths(source, effective["record"]))

    def test_revise_a_and_revise_b_change_only_declared_path(self):
        for decision, source, expected in (("revise_a", self.a, "丁"), ("revise_b", self.b, "戊")):
            validated = contracts.validate_adjudicator_payload(self.packet, {"decision": decision, "patch_ops": [{"path": "referent.canonical_hint", "value": expected}], "reason_summary": "", "supporting_evidence_ids": ["ev"]})
            self.assertTrue(validated["valid"], validated)
            effective = contracts.apply_a2r_adjudication(self.a, self.b, {"valid": True, **validated["adjudication"]}, self.packet)
            self.assertTrue(effective["valid"])
            self.assertEqual(["referent.canonical_hint"], effective["changed_fields"])
            self.assertEqual(expected, effective["record"]["referent"]["canonical_hint"])
            self.assertEqual(source["surface"], effective["record"]["surface"])

    def test_abstain_has_no_materialized_record(self):
        validated = contracts.validate_adjudicator_payload(self.packet, {"decision": "abstain", "patch_ops": [], "reason_summary": "", "supporting_evidence_ids": []})
        effective = contracts.apply_a2r_adjudication(self.a, self.b, {"valid": True, **validated["adjudication"]}, self.packet)
        self.assertTrue(effective["valid"])
        self.assertIsNone(effective["record"])

    def test_historian_b_recovery_uses_frozen_a2_tool(self):
        tool = contracts.historian_b_tool()
        self.assertEqual("submit_sfh2_a2_independent_historian_v1", tool["function"]["name"])
        self.assertEqual([], contracts.validate_deepseek_strict_schema(tool["function"]["parameters"]))

    def test_http_400_is_not_retryable_but_transient_statuses_are(self):
        class Failure(Exception):
            pass

        bad = Failure("schema rejected")
        bad.http_status = 400
        self.assertFalse(is_retryable(bad))
        throttled = Failure("throttled")
        throttled.http_status = 429
        self.assertTrue(is_retryable(throttled))
        server = Failure("server")
        server.http_status = 503
        self.assertTrue(is_retryable(server))

    def test_patch_paths_are_unique_and_typed(self):
        duplicate = contracts.validate_adjudicator_payload(self.packet, {
            "decision": "revise_a",
            "patch_ops": [
                {"path": "confidence", "value": "high"},
                {"path": "confidence", "value": "low"},
            ],
            "reason_summary": "",
            "supporting_evidence_ids": [],
        })
        self.assertFalse(duplicate["valid"])
        typed = contracts.validate_adjudicator_payload(self.packet, {
            "decision": "revise_a",
            "patch_ops": [{"path": "abstain", "value": True}],
            "reason_summary": "",
            "supporting_evidence_ids": [],
        })
        self.assertTrue(typed["valid"], typed)

    def test_runtime_contract_has_no_surface_identity_table(self):
        for path in (ROOT / "scripts/sfh2_a2r").glob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotRegex(source, r"surface\s*==|surface\s+in")

    def test_common_mode_uses_identity_agreement_not_whole_record_agreement(self):
        row = {
            "historian_a": {"identity_correct": False},
            "historian_b": {"identity_correct": False},
            "comparison": {
                "agreement": False,
                "historical_identity_disagreement": False,
            },
        }
        self.assertTrue(is_common_mode_identity_error(row))


if __name__ == "__main__":
    unittest.main()
