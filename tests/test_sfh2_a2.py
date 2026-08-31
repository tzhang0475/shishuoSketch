from __future__ import annotations

import copy
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_a0r import pipeline as a0r_pipeline  # noqa: E402
from sfh2_a0r.contracts import semantic_diff_paths  # noqa: E402
from sfh2_a0r_l.common import CHALLENGE_STORIES, build_case_packet, load_inputs  # noqa: E402
from sfh2_a2 import contracts  # noqa: E402
from sfh2_a2.comparison import compare_records  # noqa: E402
from sfh2_a2.common import cases_by_cohort, provider_source_packet  # noqa: E402
from sfh2_a2.pipeline import HISTORIAN_B_SYSTEM, historian_b_payload  # noqa: E402


def _record(**overrides):
    result = {
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
    for key, value in overrides.items():
        result[key] = value
    return result


class SFH22A2Tests(unittest.TestCase):
    def test_frozen_cohorts_are_20_and_challenge_stories_are_fixed(self):
        cohorts = cases_by_cohort()
        self.assertEqual(20, len(cohorts["regression"]))
        self.assertEqual(20, len(cohorts["challenge"]))
        self.assertEqual(set(CHALLENGE_STORIES), {row["story_id"] for row in cohorts["challenge"]})

    def test_historian_b_payload_isolated_from_a_flags_candidates_and_gold(self):
        case = cases_by_cohort()["regression"][0]
        packet = build_case_packet(case, load_inputs())
        payload = historian_b_payload(packet)
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        for forbidden in ("historian_a", "primary_semantic_record", "python_formal_consistency_flags", "expected_canonical_hint", "must_not_resolve_to", "candidate_sets"):
            self.assertNotIn(forbidden, encoded)
        self.assertNotIn("Historian A", HISTORIAN_B_SYSTEM)
        self.assertTrue(payload["gold_not_supplied"])

    def test_historian_b_payload_allow_list_contains_only_source_fields(self):
        case = cases_by_cohort()["challenge"][0]
        packet = build_case_packet(case, load_inputs())
        source = provider_source_packet(packet)
        self.assertEqual({"source_evidence", "validated_local_mentions", "target", "story_id"}, set(source))

    def test_b_does_not_require_existing_candidates(self):
        encoded = json.dumps(historian_b_payload(build_case_packet(cases_by_cohort()["regression"][0], load_inputs())), ensure_ascii=False)
        self.assertNotIn("candidate_sets", encoded)
        self.assertNotIn("candidate_person_id", encoded)

    def test_structural_comparison_ignores_metadata_only_differences(self):
        left = _record()
        right = copy.deepcopy(left)
        right["confidence"] = "medium"
        right["supporting_evidence_ids"] = []
        result = compare_records(left, right, a_valid=True, b_valid=True)
        self.assertTrue(result["agreement"])
        self.assertTrue(result["metadata_only_difference"])
        self.assertFalse(result["substantive_disagreement"])

    def test_structural_comparison_classifies_identity_kind_role_and_discourse(self):
        left = _record()
        right = copy.deepcopy(left)
        right["referent"]["canonical_hint"] = "丙"
        right["semantic_kind"] = "collective"
        right["occurrence_role"] = "collective_reference"
        right["discourse"]["speaker_hint"] = "丁"
        result = compare_records(left, right, a_valid=True, b_valid=True)
        self.assertTrue(result["substantive_disagreement"])
        self.assertIn("identity_disagreement", result["disagreement_classes"])
        self.assertIn("semantic_kind_disagreement", result["disagreement_classes"])
        self.assertIn("occurrence_role_disagreement", result["disagreement_classes"])
        self.assertIn("discourse_disagreement", result["disagreement_classes"])

    def test_invalid_a_and_valid_b_is_contract_disagreement(self):
        result = compare_records(None, _record(), a_valid=False, b_valid=True)
        self.assertFalse(result["agreement"])
        self.assertIn("contract_validity_disagreement", result["disagreement_classes"])

    def test_adjudicator_schema_is_strict_and_a2_decisions_are_distinct(self):
        tool = contracts.adjudicator_tool()
        self.assertEqual([], contracts.validate_deepseek_strict_schema(tool["function"]["parameters"]))
        enum = tool["function"]["parameters"]["properties"]["decision"]["enum"]
        self.assertEqual({"select_a", "select_b", "revise", "abstain"}, set(enum))

    def test_adjudicator_selection_exact_copy_and_revision_contract(self):
        packet = {"source_evidence": [{"evidence_id": "ev", "text": "甲"}]}
        a = _record()
        b = copy.deepcopy(a)
        b["referent"]["canonical_hint"] = "丙"
        select_a = contracts.validate_adjudicator_payload(packet, {"decision": "select_a", "base_record": "", "patch_ops": [], "reason_summary": "", "supporting_evidence_ids": []})
        self.assertTrue(select_a["valid"])
        effective = contracts.apply_a2_adjudication(a, b, {"valid": True, **select_a["adjudication"]}, packet)
        self.assertEqual(a, effective["record"])
        self.assertEqual([], semantic_diff_paths(a, effective["record"]))
        revise = contracts.validate_adjudicator_payload(packet, {"decision": "revise", "base_record": "historian_b", "patch_ops": [{"path": "referent.canonical_hint", "value": "丁"}], "reason_summary": "", "supporting_evidence_ids": ["ev"]})
        self.assertTrue(revise["valid"])
        patched = contracts.apply_a2_adjudication(a, b, {"valid": True, **revise["adjudication"]}, packet)
        self.assertEqual(["referent.canonical_hint"], patched["changed_fields"])
        self.assertEqual("丁", patched["record"]["referent"]["canonical_hint"])

    def test_invalid_adjudicator_cannot_select_invalid_source(self):
        packet = {"source_evidence": [{"evidence_id": "ev", "text": "甲"}]}
        result = contracts.apply_a2_adjudication(None, _record(), {"valid": True, "decision": "select_a", "base_record": "", "patch_ops": []}, packet)
        self.assertFalse(result["valid"])
        self.assertIsNone(result["record"])

    def test_no_a2_runtime_surface_specific_rules(self):
        for path in (ROOT / "scripts/sfh2_a2").glob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotRegex(source, re.compile(r"surface\s*==|surface\s+in"))


if __name__ == "__main__":
    unittest.main()
