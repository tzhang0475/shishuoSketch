from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_a0r.common import read_json  # noqa: E402
from sfh2_a0r.consistency import analyze_record, review_required  # noqa: E402
from sfh2_a0r.contracts import (  # noqa: E402
    adjudication_tool,
    apply_patch,
    critical_review_tool,
    effective_adjudication,
    effective_review_record,
    semantic_diff_paths,
    semantic_equal,
    substantive_semantic_diff_paths,
    validate_adjudication_payload,
    validate_critical_review_payload,
)
from sfh2_a0r.pipeline import _authorized_protocol_restart, needs_pass3, primary_payload, critical_payload, adjudication_payload, select_record  # noqa: E402


def _record(**overrides):
    record = {
        "mention_id": "m-1",
        "surface": "甲",
        "semantic_kind": "historical_person",
        "reference_type": "full_name",
        "referent": {"surface_form": "甲", "canonical_hint": "乙", "confidence": "high"},
        "occurrence_role": "scene_reference",
        "discourse": {"speaker_hint": "", "addressee_hint": "", "antecedent_hint": "", "self_reference_hint": ""},
        "relations": [],
        "confidence": "high",
        "supporting_evidence_ids": ["ev-1"],
        "attribute_type": "",
        "attribute_value": "",
        "bearer_hint": "",
        "abstain": False,
        "explanation": "initial explanation",
    }
    record.update(overrides)
    return record


def _packet():
    return {
        "mention_id": "m-1",
        "target": {"mention_id": "m-1", "surface": "甲", "exact_span": "甲", "source_evidence_id": "ev-1"},
        "source_evidence": [{"evidence_id": "ev-1", "source_layer": "main_text", "text": "甲"}],
    }


class SFH22A0RTests(unittest.TestCase):
    def test_review_and_adjudication_contracts_do_not_accept_complete_records(self):
        review_properties = critical_review_tool()["function"]["parameters"]["properties"]
        adjudication_properties = adjudication_tool()["function"]["parameters"]["properties"]
        self.assertNotIn("revised_semantic_record", review_properties)
        self.assertNotIn("semantic_record", adjudication_properties)
        bad = {"decision": "confirm", "revised_semantic_record": _record(), "reviewed_fields": [], "patch": {}, "reason_summary": "", "supporting_evidence_ids": []}
        self.assertFalse(validate_critical_review_payload(_packet(), bad)["valid"])
        bad_adjudication = {"decision": "select_pass1", "base_record": "", "semantic_record": _record(), "reviewed_fields": [], "patch": {}, "reason_summary": "", "supporting_evidence_ids": []}
        self.assertFalse(validate_adjudication_payload(_packet(), bad_adjudication)["valid"])

    def test_confirm_reuses_pass1_exactly(self):
        first = _record()
        review = {"valid": True, "decision": "confirm", "reviewed_fields": [], "patch": {}, "supporting_evidence_ids": [], "reason_summary": "confirmed"}
        result = effective_review_record(first, review, _packet())
        self.assertEqual(first, result["record"])
        self.assertEqual("pass1_confirmed_exact", result["source"])

    def test_revision_changes_only_declared_field_and_rejects_undeclared_change(self):
        first = _record()
        patch = {"referent.canonical_hint": "丙"}
        applied = apply_patch(first, patch, ["referent.canonical_hint"], _packet())
        self.assertTrue(applied["valid"])
        self.assertEqual(["referent.canonical_hint"], applied["changed_fields"])
        self.assertEqual("丙", applied["record"]["referent"]["canonical_hint"])
        self.assertFalse(apply_patch(first, {"referent.canonical_hint": "丙"}, ["confidence"], _packet())["valid"])

    def test_selector_copies_selected_record_without_regeneration(self):
        first = _record()
        second = _record(referent={"surface_form": "甲", "canonical_hint": "丙", "confidence": "high"})
        p3 = {"valid": True, "decision": "select_pass1", "base_record": "", "reviewed_fields": [], "patch": {}, "selected_record": None}
        selected = effective_adjudication(first, second, p3, _packet())
        self.assertEqual(first, selected["record"])
        self.assertEqual("pass1_exact_copy", selected["source"])
        selected2 = effective_adjudication(first, second, {**p3, "decision": "select_pass2"}, _packet())
        self.assertEqual(second, selected2["record"])
        self.assertEqual("pass2_exact_copy", selected2["source"])

    def test_explanation_only_difference_is_not_semantic_disagreement(self):
        first = _record()
        second = copy.deepcopy(first)
        second["explanation"] = "different wording"
        self.assertEqual([], semantic_diff_paths(first, second))
        self.assertTrue(semantic_equal(first, second))
        review = {"valid": True, "decision": "confirm", "effective_record": first}
        self.assertFalse(needs_pass3({"valid": True, "record": first}, review, {"flags": [], "has_hard_flags": False}))

    def test_metadata_only_revision_does_not_require_pass3(self):
        first = _record()
        second = copy.deepcopy(first)
        second["confidence"] = "medium"
        second["referent"]["confidence"] = "medium"
        second["supporting_evidence_ids"] = ["ev-1"]
        self.assertEqual(["confidence", "referent.confidence"], semantic_diff_paths(first, second))
        self.assertEqual([], substantive_semantic_diff_paths(first, second))
        review = {"valid": True, "decision": "revise", "effective_record": second}
        self.assertFalse(needs_pass3({"valid": True, "record": first}, review, {"flags": [], "has_hard_flags": False}))

    def test_mechanical_protocol_restart_preserves_frozen_inputs_and_schema(self):
        previous = {
            "pilot": "SFH2.2-A0R",
            "selection_hash": "selection",
            "input_hashes": {"frozen": "hash"},
            "model_config": {"model": "deepseek-v4-flash", "temperature": 0},
            "schema_hashes": {"semantic_record": "hash"},
        }
        current = {**previous, "protocol_revision": "sfh2-a0r-contract-repair-v2"}
        self.assertTrue(_authorized_protocol_restart(previous, current))

    def test_diagnostic_flags_do_not_escalate_but_hard_flags_do(self):
        first = _record()
        review = {"valid": True, "decision": "confirm", "effective_record": first}
        diagnostic = {"flags": [{"flag_type": "new_candidate", "severity": "diagnostic"}], "has_hard_flags": False, "has_review_flags": False}
        self.assertFalse(needs_pass3({"valid": True, "record": first}, review, diagnostic))
        hard = {"flags": [{"flag_type": "identity_distinctness_conflict", "severity": "hard"}], "has_hard_flags": True, "has_review_flags": False}
        self.assertTrue(needs_pass3({"valid": True, "record": first}, review, hard))

    def test_review_routing_only_uses_hard_or_review_severity(self):
        first = _record()
        result = analyze_record(first, evidence_ids={"ev-1"})
        self.assertFalse(review_required(result))
        self.assertTrue(review_required({"flags": [{"severity": "review"}], "has_review_flags": True, "has_hard_flags": False}))

    def test_invalid_adjudication_payload_is_fail_closed(self):
        payload = {"decision": "select_pass1", "base_record": "", "reviewed_fields": ["confidence"], "patch": {"confidence": "low"}, "reason_summary": "", "supporting_evidence_ids": []}
        result = validate_adjudication_payload(_packet(), payload)
        self.assertFalse(result["valid"])

    def test_a0r_payloads_never_include_evaluation_gold(self):
        packet = _packet()
        primary = primary_payload(packet)
        review = critical_payload(packet, _record(), {"flags": []})
        adjudication = adjudication_payload(packet, _record(), {"decision": "confirm", "patch": {}, "reviewed_fields": []}, _record(), {"flags": []})
        encoded = json.dumps([primary, review, adjudication], ensure_ascii=False)
        self.assertNotIn("expected_canonical_hint", encoded)
        self.assertNotIn("must_not_resolve_to", encoded)

    def test_runtime_has_no_surface_identity_answer_rules(self):
        for path in (ROOT / "scripts/sfh2_a0r").glob("*.py"):
            content = path.read_text(encoding="utf-8")
            self.assertNotRegex(content, r"surface\s*==")
            self.assertNotRegex(content, r"surface\s+in\s+")

    def test_offline_counterfactual_removes_copy_drift(self):
        result = read_json(ROOT / "data/generated/sfh2-a0r/offline-counterfactual.json", {})
        self.assertEqual(0, result.get("counterfactual_reviewer_damage"))
        self.assertEqual(0.7, result.get("old_final_strict_accuracy"))
        self.assertEqual(0.75, result.get("counterfactual_final_strict_accuracy"))
        changed = result.get("cases_changed_solely_by_selector_copy_repair", [])
        self.assertEqual(1, len(changed))
        self.assertEqual(["referent.surface_form"], changed[0].get("semantic_changed_fields"))


if __name__ == "__main__":
    unittest.main()
