#!/usr/bin/env python3
"""Offline tests for HNG2-SL; no API calls are made here."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts import historical_entity_schema as schema
from scripts import run_hng2_schema_live as live


class HNG2SchemaLiveTests(unittest.TestCase):
    def test_selection_is_open_gap_only_and_frozen(self) -> None:
        selection = live.build_selection()
        self.assertEqual(selection["selected_case_count"], 18)
        base = json.loads((live.BASE / "research-gaps.json").read_text(encoding="utf-8"))
        gaps = {str(row["case_id"]): row for row in base["gaps"]}
        self.assertTrue(all(gaps[row["case_id"]]["status"] == "open" for row in selection["live_cases"]))
        self.assertTrue(selection["frozen"])
        self.assertTrue(selection["no_frontier_expansion"])

    def test_model_enum_validation_is_fail_closed(self) -> None:
        case = {
            "case_id": "case",
            "candidates": [{"candidate_key": "c0", "person_id": "person-1"}],
            "interpretation": {"mention_scope": "narrative"},
        }
        passages = {"r1": {"text": "庾太尉"}}
        bad = {
            "semantic_assessment": {"assessment_status": "free_text", "semantic_fit": "supported", "observed_role": "unknown", "evidence_spans": [], "summary": "x"},
            "identity_recommendation": {"decision": "choose_candidate", "chosen_candidate_key": "c9", "confidence": "certain", "evidence_spans": [], "new_entity_key": None},
            "research_gap": {"status": "open", "missing_constraints": [], "blocking_question": "x", "next_best_action": "human_review", "candidate_keys": [], "stop_condition": "x"},
        }
        result = live.validate_model_payload(bad, case, passages)
        self.assertFalse(result["valid"])
        self.assertTrue(result["invalid_enum_outputs"])
        self.assertTrue(result["invented_candidate_attempts"])

    def test_metatextual_role_invariant(self) -> None:
        case = {"case_id": "case", "candidates": [], "interpretation": {"mention_scope": "metatextual"}}
        payload = {
            "semantic_assessment": {"assessment_status": "assessed", "semantic_fit": "support", "observed_role": "event_participant", "evidence_spans": [{"ref": "r1", "span": "袁宏《紀》"}], "summary": "cited"},
            "identity_recommendation": {"decision": "ambiguous", "chosen_candidate_key": None, "confidence": "low", "reason_codes": [], "evidence_spans": [], "new_entity_key": None, "summary": ""},
            "research_gap": {"status": "open", "missing_constraints": [], "blocking_question": "x", "next_best_action": "human_review", "candidate_keys": [], "stop_condition": "x"},
        }
        result = live.validate_model_payload(payload, case, {"r1": {"text": "袁宏《紀》"}})
        self.assertIn("metatextual_role_invariant", result["errors"])

    def test_graph_id_is_not_identity_decision_id(self) -> None:
        case = {"case_id": "case", "candidates": [{"candidate_key": "c0", "person_id": None, "canonical_name": "卞敦"}], "interpretation": {"entity_kind": "named_person"}}
        recommendation = {"decision": "new_person_candidate", "chosen_candidate_key": "c0", "confidence": "medium", "reason_codes": [], "summary": "", "new_entity_key": "n0"}
        decision, action, gap = live._project_decision(case, recommendation, {"validated_assessment_evidence": [], "validated_recommendation_evidence": []}, [])
        self.assertEqual(decision["identity_status"], "resolved_new_candidate")
        self.assertEqual(decision["new_entity_key"], "n0")
        self.assertNotIn("provisional_person_id", decision)
        self.assertEqual(action["node_type"], "provisional_person")
        self.assertTrue(action["provisional_person_id"])
        self.assertEqual(gap["status"], "closed")

    def test_search_plan_cannot_expand_frontier(self) -> None:
        case = {"candidates": [{"candidate_key": "c0"}]}
        bad = {"search_plan": {"target_constraint": "x", "goal": "x", "candidate_keys": ["c0"], "preferred_sources": ["晉書"], "search_entities": ["人"], "search_patterns": ["父"], "temporal_scope": {}, "graph_neighborhood_scope": "recursive", "stop_condition": "x"}}
        plan, errors = live._validate_search_plan(bad, case)
        self.assertIsNone(plan)
        self.assertIn("search_plan_recursive_graph_scope", errors)

    def test_search_plan_packet_is_compact_and_does_not_send_provenance(self) -> None:
        case = {"case_id": "case", "observation": {"surface": "文帝", "exact_span": "文帝", "source_work": "晉書"}, "interpretation": {}, "candidates": [], "constraint_checks": []}
        packet = live._model_packet(case, {"status": "open"}, {"r1": {"ref": "r1", "work": "晉書", "layer": "main", "source_form": "punctuated", "text": "文帝", "original_text": "SHOULD_NOT_BE_SENT"}}, round_no=1)
        self.assertNotIn("original_text", json.dumps(packet, ensure_ascii=False))
        self.assertNotIn("SHOULD_NOT_BE_SENT", json.dumps(packet, ensure_ascii=False))

    def test_live_projection_keeps_graph_action_separate(self) -> None:
        decisions = json.loads((live.OUT / "identity-decisions.json").read_text(encoding="utf-8"))
        actions = json.loads((live.OUT / "graph-actions.json").read_text(encoding="utf-8"))
        self.assertTrue(all("graph_action" not in row for row in decisions["decisions"]))
        self.assertEqual(len(decisions["decisions"]), len(actions["actions"]))

    def test_schema_enums_and_scopes(self) -> None:
        assessment = schema.SemanticAssessment("m", "assessed", "support", "cited_author")
        self.assertEqual(assessment.assessment_status, "assessed")
        check = schema.ConstraintCheck("temporal", None, "unknown", "python", constraint_scope="seed")
        self.assertEqual(check.constraint_scope, "seed")
        with self.assertRaises(ValueError):
            schema.SemanticAssessment("m", "offline_replayed", "supported", "unknown")

    def test_replay_has_no_literal_named_special_case(self) -> None:
        text = Path(live.ROOT / "scripts/build_hng2_schema_replay.py").read_text(encoding="utf-8")
        self.assertNotIn('surface == "袁宏"', text)
        self.assertNotIn('surface == "喜弟預女"', text)


if __name__ == "__main__":
    unittest.main()
