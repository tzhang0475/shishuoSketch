#!/usr/bin/env python3
"""HNG2-SC.1 offline controller-hardening tests."""

from __future__ import annotations

import json
import unittest

from scripts import build_hng0_2 as hng02
from scripts import hng2_schema_controller as controller
from scripts import run_hng2_schema_controller as base
from scripts import run_hng2_schema_controller_hardening as hardening


class HNG2SC1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases, cls.gaps, cls.sources = hardening.load_inputs()
        cls.catalog = hng02.person_catalog()
        cls.index = hng02.forms_index(cls.catalog)

    def test_required_fixtures_are_valid_and_target_bound(self) -> None:
        rows = hardening.fixture_suite(self.cases, self.sources, self.catalog)
        self.assertEqual(len(rows), 8)
        for row in rows:
            result = hardening.process_fixture(row)
            self.assertTrue(result["validation"]["valid"], (row["fixture_id"], result["validation"]))
            self.assertEqual(result["projection"]["card"]["target_entity_key"], "e0")

    def test_identity_equivalence_propagates_to_existing_person(self) -> None:
        row = next(r for r in hardening.fixture_suite(self.cases, self.sources, self.catalog) if r["fixture_id"] == "wu-emperor-propagation")
        result = hardening.process_fixture(row)
        projection = result["projection"]
        self.assertEqual(projection["identity_decision"]["identity_status"], "resolved_existing")
        self.assertEqual(projection["identity_decision"]["person_id"], "person-fixture-sima-yan")
        self.assertTrue(projection["candidate_info"]["identity_propagations"])

    def test_contextual_structural_entity_cannot_change_named_target(self) -> None:
        row = next(r for r in hardening.fixture_suite(self.cases, self.sources, self.catalog) if r["fixture_id"] == "yuxi-target-separation")
        result = hardening.process_fixture(row)
        self.assertEqual(result["projection"]["card"]["target_entity_key"], "e0")
        self.assertEqual(result["projection"]["identity_decision"]["identity_status"], "resolved_new_candidate")

    def test_structural_target_is_not_single_person(self) -> None:
        row = next(r for r in hardening.fixture_suite(self.cases, self.sources, self.catalog) if r["fixture_id"] == "structural-target")
        result = hardening.process_fixture(row)
        self.assertEqual(result["projection"]["identity_decision"]["identity_status"], "not_single_person")
        self.assertEqual(result["projection"]["graph_action"]["action"], "no_person_node")

    def test_existing_match_upgrades_local_candidate_before_new_null_candidate(self) -> None:
        row = next(r for r in hardening.fixture_suite(self.cases, self.sources, self.catalog) if r["fixture_id"] == "known-person-candidate-upgrade")
        result = hardening.process_fixture(row)
        self.assertEqual(result["projection"]["state_delta"]["upgraded_candidates"], ["c0"])
        c0 = next(item for item in result["projection"]["candidates"] if item["candidate_key"] == "c0")
        self.assertEqual(c0["person_id"], "person-053")

    def test_prior_temporal_constraint_is_preserved_value_for_value(self) -> None:
        row = next(r for r in hardening.fixture_suite(self.cases, self.sources, self.catalog) if r["fixture_id"] == "prior-temporal-preservation")
        result = hardening.process_fixture(row)
        prior = row["prior_constraints"][0]
        self.assertIn(prior, result["projection"]["constraints"])
        self.assertEqual(json.dumps(prior, ensure_ascii=False, sort_keys=True), json.dumps(result["projection"]["constraints"][0], ensure_ascii=False, sort_keys=True))
        self.assertTrue(result["prior_constraints_preserved"])

    def test_truncation_is_envelope_failure_not_card_failure(self) -> None:
        case = {"case_id": "case", "candidates": [], "research_gap": {"status": "open"}}
        record = {"status": "response", "response": {"choices": [{"finish_reason": "length", "message": {"content": "{\"incomplete\":"}}]}}
        result = hardening.classify_response(record, case, {}, require_target=True)
        self.assertEqual(result["classification"], "response_truncated")
        self.assertIsNone(result["validation"])

    def test_reasoning_content_is_parsed_by_same_card_validator(self) -> None:
        case = {"case_id": "case", "candidates": [], "research_gap": {"status": "open"}}
        passage = {"r": {"ref": "r", "text": "宣"}}
        payload = hardening.fixture_payload("unresolved", "r", "宣")
        response = {"choices": [{"finish_reason": "stop", "message": {"content": "", "reasoning_content": json.dumps(payload, ensure_ascii=False)}}]}
        result = hardening.classify_response({"status": "response", "response": response}, case, passage, require_target=True)
        self.assertEqual(result["response_channel"], "reasoning_content")
        self.assertEqual(result["classification"], "valid_card")

    def test_invalid_card_does_not_project_state(self) -> None:
        case = {"case_id": "case", "candidates": [], "research_gap": {"status": "open"}}
        payload = hardening.fixture_payload("unresolved", "r", "宣")
        payload["evidence_interpretation"]["entities"][0]["evidence_span"] = "不存在"
        result = controller.validate_card_payload(payload, case, {"r": {"ref": "r", "text": "宣"}}, require_target=True)
        self.assertFalse(result["valid"])

    def test_search_packet_carries_explicit_allowed_sources(self) -> None:
        packet = hardening.search_plan_packet({"observation": {"surface": "庾太尉", "source_work": "晉書"}}, {"status": "open"}, [], {})
        self.assertEqual(packet["allowed_sources"], list(hardening.ALLOWED_SOURCES))

    def test_frozen_selection_is_existing_open_gap_only(self) -> None:
        selection = hardening.build_selection(self.cases, self.gaps)
        self.assertEqual(selection["selected_case_count"], 5)
        self.assertTrue(selection["frozen"])
        self.assertTrue(all(row["case_id"] in self.cases and self.gaps[row["case_id"]]["status"] == "open" for row in selection["cases"]))


if __name__ == "__main__":
    unittest.main()
