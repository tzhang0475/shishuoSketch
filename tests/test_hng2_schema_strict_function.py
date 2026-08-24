"""Offline contract tests for HNG2-SC strict Function Calling."""

from __future__ import annotations

import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import hng2_schema_controller as controller  # noqa: E402
import hng2_schema_strict_tools as strict_tools  # noqa: E402
import historical_entity_schema as schema  # noqa: E402
import run_hng2_schema_controller_hardening as hardening  # noqa: E402
import smoke_deepseek  # noqa: E402


class HNG2StrictFunctionTests(unittest.TestCase):
    def test_schema_is_generated_from_current_enums_and_strict_objects(self):
        root = strict_tools.card_parameters_schema()
        self.assertEqual(set(root["properties"]), {"evidence_interpretation", "semantic_assessment", "identity_recommendation", "research_gap"})

        def visit(node: dict):
            if node.get("type") == "object":
                self.assertFalse(node.get("additionalProperties"))
                self.assertEqual(set(node.get("properties", {})), set(node.get("required", [])))
                self.assertTrue(node.get("description"))
                for child in node.get("properties", {}).values():
                    visit(child)
            elif node.get("type") == "array":
                self.assertTrue(node.get("description"))
                visit(node["items"])
            elif node.get("type") == "string":
                self.assertTrue(node.get("description"))

        visit(root)
        entity = root["properties"]["evidence_interpretation"]["properties"]["entities"]["items"]
        assertion = root["properties"]["evidence_interpretation"]["properties"]["assertions"]["items"]
        self.assertEqual(set(entity["properties"]["entity_kind"]["enum"]), schema.ENTITY_KINDS)
        self.assertEqual(set(entity["properties"]["reference_form"]["enum"]), schema.REFERENCE_FORMS)
        self.assertEqual(set(assertion["properties"]["assertion_type"]["enum"]), schema.EVIDENCE_ASSERTION_TYPES)

    def test_forced_function_definition_and_beta_choice(self):
        tool = strict_tools.strict_function_definition()
        self.assertEqual(tool["type"], "function")
        self.assertTrue(tool["function"]["strict"])
        self.assertEqual(tool["function"]["name"], strict_tools.FUNCTION_NAME)
        self.assertEqual(strict_tools.strict_tool_choice(), {"type": "function", "function": {"name": strict_tools.FUNCTION_NAME}})
        self.assertEqual(strict_tools.STRICT_ENDPOINT, "https://api.deepseek.com/beta")
        self.assertTrue(strict_tools.STRICT_COMPLETIONS_ENDPOINT.endswith("/chat/completions"))

    def test_tool_call_parser_rejects_assistant_prose(self):
        payload = {"evidence_interpretation": {"entities": [], "assertions": [], "target_entity_key": "", "summary": ""}}
        response = {"choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False), "tool_calls": []}}]}
        parsed, channel, error = controller.extract_strict_tool_payload(response)
        self.assertIsNone(parsed)
        self.assertEqual(channel, "none")
        self.assertEqual(error, "tool_calls_missing")

    def test_tool_call_parser_requires_exact_function(self):
        response = {"choices": [{"message": {"tool_calls": [{"function": {"name": "other", "arguments": "{}"}}]}}]}
        parsed, channel, error = controller.extract_strict_tool_payload(response)
        self.assertIsNone(parsed)
        self.assertEqual(channel, "tool_call")
        self.assertEqual(error, "unexpected_function_name")

    def test_wire_empty_sentinels_round_trip_to_existing_nullable_shape(self):
        payload = {
            "evidence_interpretation": {
                "target_entity_key": "",
                "entities": [],
                "assertions": [{"object_entity_key": "", "value": "", "direction": ""}],
                "summary": "",
            },
            "identity_recommendation": {
                "chosen_candidate_key": "",
                "new_entity_key": "",
                "new_entity_candidate": {"surface": ""},
            },
        }
        converted = strict_tools.wire_to_controller_payload(payload)
        self.assertIsNone(converted["evidence_interpretation"]["target_entity_key"])
        self.assertIsNone(converted["evidence_interpretation"]["assertions"][0]["object_entity_key"])
        self.assertIsNone(converted["identity_recommendation"]["chosen_candidate_key"])
        self.assertIsNone(converted["identity_recommendation"]["new_entity_candidate"])

    def test_offline_fixture_cards_pass_through_strict_envelope(self):
        cases, gaps, sources = hardening.load_inputs()
        catalog = hardening.hng02.person_catalog()
        rows, counts = hardening_fixture_rows(cases, sources, catalog)
        self.assertEqual(len(rows), 8)
        self.assertEqual(counts.get("valid_card"), 8)
        self.assertTrue(all(row["response_channel"] == "tool_call" for row in rows))

    def test_live_controller_has_no_literal_surface_fixture_rules(self):
        source = inspect.getsource(hardening.target_interpretation)
        self.assertNotIn('surface == "虞喜"', source)
        self.assertNotIn('surface == "廙"', source)

    def test_client_accepts_explicit_endpoint_without_changing_default(self):
        signature = inspect.signature(smoke_deepseek.call_deepseek)
        self.assertIn("endpoint", signature.parameters)
        self.assertEqual(smoke_deepseek.API_URL, "https://api.deepseek.com/chat/completions")

    def test_semantic_call_uses_beta_tool_without_json_mode(self):
        captured = {}
        original = hardening.call_deepseek

        def fake_call(messages, **kwargs):
            captured.update(kwargs)
            return {"choices": [{"finish_reason": "tool_calls", "message": {"tool_calls": [{"function": {"name": strict_tools.FUNCTION_NAME, "arguments": "{}"}}]}}]}

        hardening.call_deepseek = fake_call
        try:
            with tempfile.TemporaryDirectory() as directory:
                hardening.call_live_record("semantic", "case", {"x": 1}, Path(directory), 1)
        finally:
            hardening.call_deepseek = original
        self.assertNotIn("response_format", captured)
        self.assertEqual(captured["endpoint"], strict_tools.STRICT_COMPLETIONS_ENDPOINT)
        self.assertEqual(captured["tool_choice"], strict_tools.strict_tool_choice())
        self.assertTrue(captured["tools"][0]["function"]["strict"])


def hardening_fixture_rows(cases, sources, catalog):
    rows = []
    for fixture in hardening.fixture_suite(cases, sources, catalog):
        payload = strict_tools.controller_payload_to_wire(fixture["payload"])
        envelope = {"choices": [{"finish_reason": "stop", "message": {"tool_calls": [{"function": {"name": strict_tools.FUNCTION_NAME, "arguments": json.dumps(payload, ensure_ascii=False)}}]}}]}
        rows.append(hardening.classify_response({"status": "response", "response": envelope}, fixture["case"], fixture["passages"], require_target=True, candidate_rows=fixture.get("prior_candidates", []), strict_function=True))
    counts = {}
    for row in rows:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
    return rows, counts


if __name__ == "__main__":
    unittest.main()
