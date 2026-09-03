from __future__ import annotations

import copy
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_a2o.common import all_cases, build_case_packet, load_inputs, provider_payload  # noqa: E402
from sfh2_a2o.contracts import occurrence_function_tool, validate_occurrence_payload  # noqa: E402
from sfh2_a2o.pipeline import confusion_matrix  # noqa: E402
from sfh2_a2o.provenance import derive_provenance_layer, project_legacy_occurrence_role  # noqa: E402
from sfh2_a2o.transport import is_retryable  # noqa: E402


class SFH22A2OTests(unittest.TestCase):
    def test_cohort_is_deterministic_and_balanced(self):
        cases = all_cases()
        self.assertEqual(26, len(cases))
        self.assertEqual(6, sum(row["cohort"] == "reviewed_role" for row in cases))
        self.assertEqual(20, sum(row["cohort"] == "challenge" for row in cases))
        self.assertEqual({"09-pinzao-063", "25-paidiao-015", "21-qiaoyi-011", "10-guizhen-011", "02-yanyu-060"}, {row["story_id"] for row in cases if row["cohort"] == "challenge"})

    def test_provenance_comes_only_from_target_evidence_metadata(self):
        packet = {"target": {"source_evidence_id": "ev-b"}, "source_evidence": [{"evidence_id": "ev-a", "source_layer": "main_text", "text": "任意"}, {"evidence_id": "ev-b", "source_layer": "liu_annotation", "text": "任意"}]}
        self.assertEqual(("liu_annotation", []), derive_provenance_layer(packet))
        packet["source_evidence"][1]["source_layer"] = "new_structural_layer"
        self.assertEqual(("new_structural_layer", []), derive_provenance_layer(packet))

    def test_projection_is_generic_and_has_no_surface_argument(self):
        self.assertEqual("annotation_person", project_legacy_occurrence_role("liu_annotation", "participant"))
        self.assertEqual("annotation_person", project_legacy_occurrence_role("liu_annotation", "reference"))
        self.assertEqual("citation_source_person", project_legacy_occurrence_role("liu_annotation", "citation_source"))
        self.assertEqual("historical_exemplum", project_legacy_occurrence_role("main_text", "historical_exemplum"))
        self.assertEqual("collective_reference", project_legacy_occurrence_role("main_text", "collective_reference"))
        self.assertEqual("person_attribute", project_legacy_occurrence_role("liu_annotation", "person_attribute"))
        self.assertEqual("scene_participant", project_legacy_occurrence_role("main_text", "participant"))
        self.assertEqual("scene_reference", project_legacy_occurrence_role("main_text", "reference"))
        self.assertEqual("speaker_reference", project_legacy_occurrence_role("main_text", "speaker"))
        self.assertEqual("addressee_reference", project_legacy_occurrence_role("main_text", "addressee"))

    def test_contrastive_reviewed_projections(self):
        cases = {row["surface"]: row for row in all_cases() if row["cohort"] == "reviewed_role"}
        expected = {"滔": ("liu_annotation", "participant", "annotation_person"), "嘏": ("liu_annotation", "participant", "annotation_person"), "薛瑩": ("liu_annotation", "citation_source", "citation_source_person"), "王師": ("liu_annotation", "collective_reference", "collective_reference"), "齊桓公": ("liu_annotation", "historical_exemplum", "historical_exemplum"), "字景真": ("liu_annotation", "person_attribute", "person_attribute")}
        for surface, (layer, function, role) in expected.items():
            self.assertIn(surface, cases)
            self.assertEqual(role, project_legacy_occurrence_role(layer, function))

    def test_occurrence_tool_is_strict_and_identity_free(self):
        parameters = occurrence_function_tool()["function"]["parameters"]
        self.assertEqual(set(parameters["properties"]), set(parameters["required"]))
        self.assertFalse(parameters["additionalProperties"])
        self.assertNotIn("semantic_kind", parameters["properties"])
        self.assertNotIn("referent", parameters["properties"])
        self.assertNotIn("occurrence_role", parameters["properties"])

    def test_occurrence_payload_rejects_identity_replacement_fields(self):
        packet = {"case_id": "case", "source_evidence": [{"evidence_id": "ev"}]}
        payload = {"case_id": "case", "narrative_function": "participant", "confidence": "high", "supporting_evidence_ids": ["ev"], "reason_summary": "", "referent": "某人"}
        result = validate_occurrence_payload(packet, payload)
        self.assertFalse(result["valid"])
        self.assertIn("unexpected_occurrence_fields:referent", result["errors"])

    def test_provider_packet_contains_frozen_identity_but_no_gold_or_legacy_role(self):
        case = all_cases()[0]
        packet = build_case_packet(case, load_inputs())
        payload = provider_payload(packet)
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        self.assertTrue(payload["identity_not_under_review"])
        self.assertNotIn("expected_narrative_function", encoded)
        self.assertNotIn("expected_legacy_occurrence_role", encoded)
        self.assertNotIn("occurrence_role", encoded)
        self.assertNotIn("review_status", encoded)

    def test_six_role_gold_cases_have_expected_structural_layers(self):
        inputs = load_inputs()
        for case in all_cases():
            if case["cohort"] != "reviewed_role":
                continue
            packet = build_case_packet(case, inputs)
            self.assertEqual("liu_annotation", packet["provenance_layer"])

    def test_identity_is_not_a_model_output_field(self):
        names = set(occurrence_function_tool()["function"]["parameters"]["properties"])
        self.assertTrue(names.isdisjoint({"identity", "canonical_hint", "referent", "semantic_kind", "occurrence_role"}))

    def test_transport_400_is_not_retryable_and_transient_status_is(self):
        bad = RuntimeError("HTTP 400")
        bad.http_status = 400
        self.assertFalse(is_retryable(bad))
        transient = RuntimeError("HTTP 500")
        transient.http_status = 500
        self.assertTrue(is_retryable(transient))

    def test_no_surface_specific_semantic_rules_in_runtime_modules(self):
        for path in (ROOT / "scripts/sfh2_a2o").glob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotRegex(source, re.compile(r"surface\s*==|surface\s+in"))

    def test_a2o_result_wrapper_keeps_candidate_only_boundary(self):
        for path in (ROOT / "scripts/sfh2_a2o").glob("*.py"):
            source = path.read_text(encoding="utf-8")
            if "write_json" in source:
                self.assertIn("candidate_only", source)
                self.assertIn("canonical_write_back", source)

    def test_annotation_collapse_comparison_uses_frozen_a2r_baseline(self):
        evaluation = {
            "records": [
                {
                    "case_id": "sfh2-a0-689a835b331402ae9189",
                    "reviewed_for_primary_metrics": True,
                    "expected_legacy_occurrence_role": "annotation_person",
                    "projected_legacy_occurrence_role": "annotation_person",
                },
                {
                    "case_id": "sfh2-a0-b05e327c31dcf07e9e68",
                    "reviewed_for_primary_metrics": True,
                    "expected_legacy_occurrence_role": "annotation_person",
                    "projected_legacy_occurrence_role": "annotation_person",
                },
            ]
        }
        comparison = confusion_matrix(evaluation)["annotation_participant_collapsed_to_scene_participant"]
        self.assertEqual(2, comparison["before_a2r_six_case_count"])
        self.assertEqual(0, comparison["after_a2o_count"])


if __name__ == "__main__":
    unittest.main()
