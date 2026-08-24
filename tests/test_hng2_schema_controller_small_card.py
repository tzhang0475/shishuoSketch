"""Offline tests for the candidate-blind small Historical Evidence Card."""

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
import run_hng2_schema_controller_small_card as small  # noqa: E402
import historical_entity_schema as schema  # noqa: E402


class HNG2SmallCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases, cls.gaps, cls.sources = hardening.load_inputs()
        cls.catalog = hng02.person_catalog()
        cls.index = hng02.forms_index(cls.catalog)
        cls.selection = hardening.build_selection(cls.cases, cls.gaps)

    def test_small_schema_is_strict_and_minimal(self) -> None:
        root = strict_tools.small_card_parameters_schema()
        self.assertEqual(set(root["properties"]), {"target_entity_key", "entities", "assertions", "note"})
        self.assertEqual(set(root["properties"]), set(root["required"]))
        self.assertFalse(root["additionalProperties"])
        entity = root["properties"]["entities"]["items"]
        assertion = root["properties"]["assertions"]["items"]
        self.assertEqual(set(entity["properties"]["entity_kind"]["enum"]), schema.ENTITY_KINDS)
        self.assertEqual(set(entity["properties"]["reference_form"]["enum"]), schema.REFERENCE_FORMS)
        self.assertEqual(set(assertion["properties"]["assertion_type"]["enum"]), strict_tools.SMALL_ASSERTION_TYPES)
        for atype in strict_tools.SMALL_ASSERTION_TYPES:
            self.assertIn(atype, assertion["properties"]["assertion_type"]["description"])
        self.assertEqual(strict_tools.strict_function_definition()["function"]["parameters"], root)
        self.assertEqual(strict_tools.legacy_strict_function_definition()["function"]["parameters"], strict_tools.card_parameters_schema())

    def test_every_small_schema_object_is_strict(self) -> None:
        def visit(node: dict) -> None:
            self.assertTrue(node.get("description"))
            if node.get("type") == "object":
                self.assertFalse(node.get("additionalProperties"))
                self.assertEqual(set(node.get("properties", {})), set(node.get("required", [])))
                for child in node.get("properties", {}).values():
                    visit(child)
            elif node.get("type") == "array":
                visit(node["items"])

        visit(strict_tools.small_card_parameters_schema())

    def test_candidate_blind_packet_contains_only_target_and_passages(self) -> None:
        selected = self.selection["cases"][0]
        case = self.cases[selected["case_id"]]
        passages = hardening.passages_for(selected["case_id"], case, self.sources)
        packet = small.candidate_blind_packet(selected, case, passages)
        self.assertEqual(set(packet), {"target", "source_passages"})
        self.assertNotIn("candidates", json.dumps(packet, ensure_ascii=False))
        self.assertNotIn("research_gap", json.dumps(packet, ensure_ascii=False))
        self.assertNotIn("constraint_checks", json.dumps(packet, ensure_ascii=False))

    def test_small_cards_for_five_frozen_cases_project_without_model_decision(self) -> None:
        expected = {
            "title_existing": "resolved_existing",
            "genuine_unresolved": "unresolved",
            "abbreviated_existing": "resolved_existing",
            "new_person": "resolved_new_candidate",
            "kinship_target_separation": "resolved_new_candidate",
        }
        for selected in self.selection["cases"]:
            case = copy.deepcopy(self.cases[selected["case_id"]])
            case["research_gap"] = dict(self.gaps[selected["case_id"]])
            passages = hardening.passages_for(selected["case_id"], case, self.sources)
            row = small.process_small_card(case, small.make_small_fixture(selected["category"], selected["source_ref"]), passages, self.catalog, self.index)
            self.assertTrue(row["validation"]["valid"], (selected["category"], row["validation"]))
            projection = row["projection"]
            self.assertEqual(projection["identity_decision"]["identity_status"], expected[selected["category"]])
            self.assertNotIn("identity_recommendation", json.dumps(projection["card"], ensure_ascii=False))

    def test_target_contextual_kinship_does_not_change_target_class(self) -> None:
        selected = next(row for row in self.selection["cases"] if row["category"] == "kinship_target_separation")
        case = copy.deepcopy(self.cases[selected["case_id"]])
        case["research_gap"] = dict(self.gaps[selected["case_id"]])
        passages = hardening.passages_for(selected["case_id"], case, self.sources)
        card = small.make_small_fixture(selected["category"], selected["source_ref"])
        projected = small.process_small_card(case, card, passages, self.catalog, self.index)["projection"]
        self.assertEqual(projected["card"]["target_entity_key"], "e0")
        self.assertEqual(projected["identity_decision"]["identity_status"], "resolved_new_candidate")
        structural = copy.deepcopy(card)
        structural["target_entity_key"] = "e1"
        structural_projected = small.process_small_card(case, structural, passages, self.catalog, self.index)["projection"]
        self.assertEqual(structural_projected["identity_decision"]["identity_status"], "not_single_person")

    def test_invalid_fields_and_refs_fail_closed(self) -> None:
        selected = self.selection["cases"][0]
        case = self.cases[selected["case_id"]]
        passages = hardening.passages_for(selected["case_id"], case, self.sources)
        card = small.make_small_fixture(selected["category"], selected["source_ref"])
        card["undefined"] = True
        card["entities"][0]["evidence_refs"] = ["not-supplied"]
        result = controller.validate_small_card_payload(card, case, passages, require_target=True)
        self.assertFalse(result["valid"])
        self.assertTrue(any("unknown_top_field" in error for error in result["errors"]))
        self.assertTrue(any("unknown:not-supplied" in error for error in result["errors"]))

    def test_note_is_not_used_for_python_state(self) -> None:
        selected = next(row for row in self.selection["cases"] if row["category"] == "new_person")
        case = copy.deepcopy(self.cases[selected["case_id"]])
        case["research_gap"] = dict(self.gaps[selected["case_id"]])
        passages = hardening.passages_for(selected["case_id"], case, self.sources)
        first = small.make_small_fixture(selected["category"], selected["source_ref"])
        second = copy.deepcopy(first)
        second["note"] = "完全不同的人工备注，不得控制状态"
        p1 = small.process_small_card(case, first, passages, self.catalog, self.index)["projection"]
        p2 = small.process_small_card(case, second, passages, self.catalog, self.index)["projection"]
        self.assertEqual(p1["identity_decision"], p2["identity_decision"])
        self.assertEqual(p1["research_gap"], p2["research_gap"])

    def test_strict_envelope_parser_reads_only_function_arguments(self) -> None:
        selected = self.selection["cases"][0]
        card = small.make_small_fixture(selected["category"], selected["source_ref"])
        envelope = {"choices": [{"message": {"content": "ignore", "tool_calls": [{"function": {"name": strict_tools.FUNCTION_NAME, "arguments": json.dumps(card, ensure_ascii=False)}}]}}]}
        parsed, channel, error = controller.extract_strict_tool_payload(envelope)
        self.assertEqual(channel, "tool_call")
        self.assertIsNone(error)
        self.assertEqual(parsed["target_entity_key"], "e0")


if __name__ == "__main__":
    unittest.main()
