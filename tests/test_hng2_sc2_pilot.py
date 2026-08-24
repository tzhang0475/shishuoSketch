"""Offline contract tests for the isolated HNG2-SC2-P pilot."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_hng0_2 as hng02  # noqa: E402
import hng2_schema_controller as controller  # noqa: E402
import hng2_schema_strict_tools as strict_tools  # noqa: E402
import run_hng2_schema_controller_hardening as hardening  # noqa: E402
import run_hng2_sc2_pilot as pilot  # noqa: E402


class HNG2SC2PilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases, cls.gaps, cls.sources = hardening.load_inputs()
        cls.catalog = hng02.person_catalog()
        cls.index = hng02.forms_index(cls.catalog)
        cls.selection = pilot.build_selection(cls.cases, cls.gaps)

    def test_selection_is_frozen_balanced_and_includes_required_chen_qian(self) -> None:
        self.assertEqual(self.selection["selected_case_count"], 7)
        self.assertTrue(self.selection["frozen"])
        self.assertIn("hng2-live-hng2-live-w1-identity-33afe84247b036e9d9cb", {row["case_id"] for row in self.selection["cases"]})
        self.assertEqual([row["selection_key"] for row in self.selection["cases"]], sorted(row["selection_key"] for row in self.selection["cases"]))
        self.assertEqual(len({row["case_id"] for row in self.selection["cases"]}), 7)

    def test_extended_schema_is_strict_and_only_adds_observation_field(self) -> None:
        base = strict_tools.small_card_parameters_schema()
        extended = strict_tools.small_card_with_observations_parameters_schema()
        self.assertEqual(set(extended["properties"]), set(base["properties"]) | {"unresolved_observations"})
        self.assertEqual(set(extended["properties"]), set(extended["required"]))
        self.assertFalse(extended["additionalProperties"])
        observation = extended["properties"]["unresolved_observations"]["items"]
        self.assertFalse(observation["additionalProperties"])
        self.assertEqual(set(observation["properties"]), set(observation["required"]))
        self.assertEqual(strict_tools.small_card_with_observations_function_definition()["function"]["strict"], True)
        self.assertEqual(strict_tools.strict_tool_choice()["function"]["name"], strict_tools.FUNCTION_NAME)
        self.assertEqual(strict_tools.round2_tool_choice()["function"]["name"], strict_tools.ROUND2_FUNCTION_NAME)

    def test_candidate_blind_packet_has_no_old_model_state(self) -> None:
        selected = self.selection["cases"][0]
        case = self.cases[selected["case_id"]]
        passages = hardening.passages_for(selected["case_id"], case, self.sources)
        packet = pilot.candidate_blind_packet(selected, case, passages)
        self.assertEqual(set(packet), {"target", "source_passages"})
        encoded = json.dumps(packet, ensure_ascii=False)
        self.assertNotIn("candidate", encoded)
        self.assertNotIn("ResearchGap", encoded)
        self.assertNotIn("constraint", encoded)

    def test_observation_requires_supplied_exact_span_and_bounds(self) -> None:
        selected = self.selection["cases"][0]
        case = self.cases[selected["case_id"]]
        passages = hardening.passages_for(selected["case_id"], case, self.sources)
        ref = selected["source_ref"]
        span = selected["surface"]
        valid = {"unresolved_observations": [{"source_ref": ref, "exact_span": span, "observation": "directly anchored", "search_terms": [span]}]}
        self.assertTrue(pilot.validate_unresolved_observations(valid, passages)["valid"])
        bad = copy.deepcopy(valid)
        bad["unresolved_observations"][0]["exact_span"] = "not in source"
        self.assertFalse(pilot.validate_unresolved_observations(bad, passages)["valid"])
        too_many = {"unresolved_observations": [valid["unresolved_observations"][0]] * 3}
        self.assertFalse(pilot.validate_unresolved_observations(too_many, passages)["valid"])

    def test_observations_are_removed_before_baseline_python_projection(self) -> None:
        selected = next(row for row in self.selection["cases"] if row["category"] == "control_title_known")
        case = copy.deepcopy(self.cases[selected["case_id"]])
        case["research_gap"] = dict(self.gaps[selected["case_id"]])
        passages = hardening.passages_for(selected["case_id"], case, self.sources)
        ref = selected["source_ref"]
        card = {
            "target_entity_key": "e0",
            "entities": [{"entity_key": "e0", "surface": "庾太尉", "entity_kind": "person_office_title", "reference_form": "office_title_only", "evidence_refs": [ref]}],
            "assertions": [{"assertion_id": "a0", "assertion_type": "person_mention", "subject_entity_key": "e0", "object_entity_key": "", "evidence_refs": [ref], "confidence": "medium"}],
            "note": "ignored",
            "unresolved_observations": [{"source_ref": ref, "exact_span": "庾太尉", "observation": "follow-up hint", "search_terms": ["庾亮"]}],
        }
        self.assertTrue(pilot.validate_unresolved_observations(card, passages)["valid"])
        base_card = pilot.base_card_from_extended(card)
        self.assertNotIn("unresolved_observations", base_card)
        validation = controller.validate_small_card_payload(base_card, case, passages)
        self.assertTrue(validation["valid"], validation)

    def test_round2_exact_evidence_and_unknown_fields_fail_closed(self) -> None:
        ref = "fixture-ref"
        passages = {ref: {"ref": ref, "text": "陳騫為車騎將軍"}}
        valid = {"status": "resolved", "findings": [{"subject_surface": "陳騫", "predicate": "為", "object_surface": "車騎將軍", "fact_kind": "office", "source_ref": ref, "exact_span": "陳騫為車騎將軍", "confidence": "high"}]}
        self.assertTrue(pilot.validate_round2_payload(valid, passages)["valid"])
        bad_span = copy.deepcopy(valid)
        bad_span["findings"][0]["exact_span"] = "陳騫是車騎將軍"
        self.assertFalse(pilot.validate_round2_payload(bad_span, passages)["valid"])
        unknown = copy.deepcopy(valid)
        unknown["findings"][0]["person_id"] = "person-1"
        self.assertFalse(pilot.validate_round2_payload(unknown, passages)["valid"])

    def test_round2_tool_envelope_uses_its_own_function_name(self) -> None:
        payload = {"status": "unresolved", "findings": []}
        envelope = {"choices": [{"message": {"tool_calls": [{"function": {"name": strict_tools.ROUND2_FUNCTION_NAME, "arguments": json.dumps(payload)}}]}}]}
        parsed, channel, error = controller.extract_strict_tool_payload(envelope, expected_function_name=strict_tools.ROUND2_FUNCTION_NAME)
        self.assertEqual(channel, "tool_call")
        self.assertIsNone(error)
        self.assertEqual(parsed, payload)
        wrong, _, wrong_error = controller.extract_strict_tool_payload(envelope)
        self.assertIsNone(wrong)
        self.assertEqual(wrong_error, "unexpected_function_name")


if __name__ == "__main__":
    unittest.main()

