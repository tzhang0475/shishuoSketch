#!/usr/bin/env python3
"""Offline HNG2-SC controller tests; no model/network calls."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts import build_hng0_2 as hng02
from scripts import build_hng2_schema_replay as replay
from scripts import historical_entity_schema as schema
from scripts import hng2_schema_controller as controller


class HNG2SchemaControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = hng02.person_catalog()
        self.index = hng02.forms_index(self.catalog)
        self.case = {"case_id": "case", "observation": {"surface": "新人物", "exact_span": "新人物", "source_ref": "r1", "source_work": "晉書"}, "interpretation": {"entity_kind": "named_person", "mention_scope": "narrative"}, "candidates": [], "research_gap": {"status": "open", "missing_constraints": ["identity_evidence"], "blocking_question": "who", "next_best_action": "search_biography_context", "candidate_keys": [], "stop_condition": "evidence"}}
        self.passages = {"r1": {"ref": "r1", "work": "晉書", "text": "新人物與某人同事", "source_form": "punctuated"}}

    def test_reasoning_content_fallback(self) -> None:
        payload = {"evidence_interpretation": {"entities": [], "assertions": []}}
        response = {"choices": [{"message": {"content": "", "reasoning_content": json.dumps(payload, ensure_ascii=False)}}]}
        value, channel, error = controller.extract_response_payload(response)
        self.assertEqual(channel, "reasoning_content")
        self.assertIsNone(error)
        self.assertEqual(value, payload)

    def test_card_requires_exact_evidence_and_rejects_ids(self) -> None:
        payload = {"evidence_interpretation": {"entities": [{"entity_key": "e0", "surface": "新人物", "entity_kind": "named_person", "reference_form": "full_name", "evidence_ref": "r1", "evidence_span": "不存在"}], "assertions": []}, "semantic_assessment": {"assessment_status": "assessed", "semantic_fit": "support", "observed_role": "referenced_person", "evidence_spans": [], "summary": "x"}, "identity_recommendation": {"decision": "unresolved", "chosen_candidate_key": None, "confidence": "low", "reason_codes": [], "evidence_spans": [], "new_entity_key": None, "summary": "x"}, "research_gap": {"status": "open", "missing_constraints": ["identity_evidence"], "blocking_question": "x", "next_best_action": "search_biography_context", "candidate_keys": [], "stop_condition": "x"}, "person_id": "person-1"}
        result = controller.validate_card_payload(payload, self.case, self.passages)
        self.assertFalse(result["valid"])
        self.assertTrue(any("evidence_span" in error for error in result["errors"]))
        self.assertTrue(result["invented_id_attempts"])

    def test_new_person_transition_does_not_require_candidate(self) -> None:
        payload = {"evidence_interpretation": {"entities": [{"entity_key": "e0", "surface": "新人物", "entity_kind": "named_person", "reference_form": "full_name", "evidence_ref": "r1", "evidence_span": "新人物"}], "assertions": [{"assertion_id": "a0", "assertion_type": "person_mention", "subject_entity_key": "e0", "evidence_ref": "r1", "evidence_span": "新人物", "confidence": "high"}]}, "semantic_assessment": {"assessment_status": "assessed", "semantic_fit": "support", "observed_role": "referenced_person", "evidence_spans": [{"ref": "r1", "span": "新人物"}], "summary": "named"}, "identity_recommendation": {"decision": "new_person_candidate", "chosen_candidate_key": None, "confidence": "medium", "reason_codes": [], "evidence_spans": [{"ref": "r1", "span": "新人物"}], "new_entity_candidate": {"surface": "新人物"}, "new_entity_key": "n0", "summary": "new"}, "research_gap": {"status": "open", "missing_constraints": ["identity_evidence"], "blocking_question": "x", "next_best_action": "search_biography_context", "candidate_keys": [], "stop_condition": "x"}}
        prior = [{"candidate_key": "c0", "person_id": None, "canonical_name": "新人物", "known_forms": ["新人物"]}]
        valid = controller.validate_card_payload(payload, self.case, self.passages, candidate_rows=prior)
        self.assertTrue(valid["valid"], valid)
        projection = controller.project_valid_card(self.case, payload, self.passages, prior, [], [], self.catalog, self.index)
        self.assertEqual(projection["identity_decision"]["identity_status"], "resolved_new_candidate")
        self.assertEqual(projection["identity_decision"]["new_entity_key"], "n0")
        self.assertNotIn("provisional_person_id", projection["identity_decision"])
        self.assertTrue(projection["graph_action"]["provisional_person_id"])

    def test_catalogueless_chosen_candidate_does_not_close_gap(self) -> None:
        payload = {"evidence_interpretation": {"entities": [{"entity_key": "e0", "surface": "新人物", "entity_kind": "named_person", "reference_form": "full_name", "evidence_ref": "r1", "evidence_span": "新人物"}], "assertions": [{"assertion_id": "a0", "assertion_type": "person_mention", "subject_entity_key": "e0", "evidence_ref": "r1", "evidence_span": "新人物", "confidence": "high"}]}, "semantic_assessment": {"assessment_status": "assessed", "semantic_fit": "support", "observed_role": "referenced_person", "evidence_spans": [{"ref": "r1", "span": "新人物"}], "summary": "named"}, "identity_recommendation": {"decision": "choose_candidate", "chosen_candidate_key": "c0", "confidence": "high", "reason_codes": [], "evidence_spans": [{"ref": "r1", "span": "新人物"}], "new_entity_key": None, "summary": "chosen"}, "research_gap": {"status": "open", "missing_constraints": ["identity_evidence"], "blocking_question": "x", "next_best_action": "search_biography_context", "candidate_keys": [], "stop_condition": "x"}}
        prior = [{"candidate_key": "c0", "person_id": None, "canonical_name": "新人物", "known_forms": ["新人物"]}]
        valid = controller.validate_card_payload(payload, self.case, self.passages, candidate_rows=prior)
        self.assertTrue(valid["valid"], valid)
        projection = controller.project_valid_card(self.case, payload, self.passages, prior, [], [], self.catalog, self.index)
        self.assertEqual(projection["research_gap"]["status"], "open")
        self.assertEqual(projection["identity_decision"]["identity_status"], "unresolved")

    def test_ambiguous_new_entity_key_is_rejected(self) -> None:
        payload = {"evidence_interpretation": {"entities": [], "assertions": []}, "semantic_assessment": {"assessment_status": "assessed", "semantic_fit": "unknown", "observed_role": "unknown", "evidence_spans": [], "summary": "x"}, "identity_recommendation": {"decision": "ambiguous", "chosen_candidate_key": None, "confidence": "low", "reason_codes": [], "evidence_spans": [], "new_entity_key": "n9", "summary": "x"}, "research_gap": {"status": "open", "missing_constraints": ["identity_evidence"], "blocking_question": "x", "next_best_action": "search_biography_context", "candidate_keys": [], "stop_condition": "x"}}
        result = controller.validate_card_payload(payload, self.case, self.passages)
        self.assertFalse(result["valid"])
        self.assertIn("new_entity_key_without_new_person_decision", result["errors"])

    def test_contextual_kinship_does_not_reclassify虞喜(self) -> None:
        interpretation = replay._interpretation(mention_id="m", surface="虞喜", quote="虞喜", context="會稽虞喜隱居海嵎，娉喜弟預女為妻", source_ref="r", source_work="晉書", raw={}, catalog=self.catalog, index=self.index)
        self.assertEqual(interpretation.entity_kind, "named_person")
        structural = replay._interpretation(mention_id="m2", surface="喜弟預女", quote="喜弟預女", context="娉喜弟預女為妻", source_ref="r", source_work="晉書", raw={}, catalog=self.catalog, index=self.index)
        self.assertEqual(structural.entity_kind, "structural_kinship_expression")

    def test_metatextual_role_fails_closed(self) -> None:
        case = {**self.case, "interpretation": {"mention_scope": "metatextual"}}
        payload = {"evidence_interpretation": {"entities": [{"entity_key": "e0", "surface": "袁宏《紀》", "entity_kind": "named_person", "reference_form": "full_name", "evidence_ref": "r1", "evidence_span": "新人物"}], "assertions": []}, "semantic_assessment": {"assessment_status": "assessed", "semantic_fit": "support", "observed_role": "event_participant", "evidence_spans": [{"ref": "r1", "span": "新人物"}], "summary": "x"}, "identity_recommendation": {"decision": "unresolved", "chosen_candidate_key": None, "confidence": "low", "reason_codes": [], "evidence_spans": [], "new_entity_key": None, "summary": "x"}, "research_gap": {"status": "open", "missing_constraints": ["identity_evidence"], "blocking_question": "x", "next_best_action": "search_biography_context", "candidate_keys": [], "stop_condition": "x"}}
        result = controller.validate_card_payload(payload, case, self.passages)
        self.assertIn("metatextual_role_invariant", result["errors"])

    def test_constraints_keep_assertion_provenance_and_candidate_delta(self) -> None:
        card = {"entities": [{"entity_key": "e0", "surface": "新人物", "entity_kind": "named_person", "reference_form": "full_name", "evidence_ref": "r1", "evidence_span": "新人物"}], "assertions": [{"assertion_id": "a0", "assertion_type": "person_mention", "subject_entity_key": "e0", "evidence_ref": "r1", "evidence_span": "新人物", "confidence": "high"}]}
        candidates, info = controller.generate_candidates(self.case, card, self.passages, [], self.catalog, self.index)
        checks = controller.translate_constraints(card, info, candidates, self.passages)
        self.assertTrue(any(row.get("assertion_id") == "a0" for row in checks))
        delta = controller.state_delta([], candidates, [], checks, [], ["r1"])
        self.assertTrue(delta["new_candidates"])
        self.assertTrue(delta["material"])

    def test_typed_search_plan_fallback(self) -> None:
        plan = controller.typed_fallback_search_plan(self.case, {"missing_constraints": ["temporal"], "blocking_question": "when", "stop_condition": "evidence"}, [])
        self.assertEqual(plan["gap_type"], "temporal")
        self.assertNotEqual(plan["search_patterns"], ["父", "子", "兄", "弟", "官"])
        self.assertEqual(plan["graph_neighborhood_scope"], "case_only")

    def test_constraint_schema_scopes_and_evidence_card_enums(self) -> None:
        entity = schema.EvidenceEntity("e0", "人", "named_person", "full_name", "r1", "人")
        assertion = schema.EvidenceAssertion("person_mention", "e0", evidence_ref="r1", evidence_span="人", confidence="high", assertion_id="a0")
        card = schema.EvidenceInterpretation([entity], [assertion])
        self.assertEqual(card.entities[0].entity_key, "e0")
        with self.assertRaises(ValueError):
            schema.EvidenceAssertion("not_valid", "e0", evidence_ref="r1", evidence_span="人")
        check = schema.ConstraintCheck("temporal", None, "unknown", "python", constraint_scope="passage", assertion_id="a0")
        self.assertEqual(check.assertion_id, "a0")

    def test_live_reprojection_is_controller_only(self) -> None:
        root = Path("data/generated/hng2-schema-controller-live")
        metrics = json.loads((root / "metrics.json").read_text(encoding="utf-8"))
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(metrics.get("postprocessed_without_api_calls"))
        self.assertEqual(metrics.get("postprocessing_api_calls"), 0)
        self.assertEqual(metrics.get("gaps_remaining_open"), 6)
        self.assertTrue(manifest.get("raw_api_root"))


if __name__ == "__main__":
    unittest.main()
