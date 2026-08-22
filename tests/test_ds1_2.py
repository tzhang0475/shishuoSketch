from __future__ import annotations

import json
import unittest

from scripts.ds1_2_common import (
    DS1_2_TOOLS,
    ROOT,
    STORY_ID,
    LocalEvidenceSearch,
    build_evidence_registry,
    build_initial_messages,
    build_minimal_story_input,
    parse_dsml_tool_calls,
    run_tool_loop,
    validate_final_result,
)
from scripts.validate_ds1_2 import validate


class DS12Tests(unittest.TestCase):
    def test_minimal_input_does_not_include_ds1_context_bundle(self) -> None:
        value = build_minimal_story_input(ROOT, STORY_ID)
        self.assertEqual(value["story_id"], STORY_ID)
        self.assertTrue(value["story_text_original"])
        self.assertTrue(value["reviewed_participants"])
        self.assertNotIn("evidence_index", value)
        self.assertNotIn("jianshu_evidence", value)
        self.assertNotIn("reviewed_facts", value)
        self.assertNotIn("data/generated/ds1", json.dumps(value, ensure_ascii=False))

    def test_registry_is_registered_and_excludes_generated_material(self) -> None:
        registry, source_hashes = build_evidence_registry(ROOT)
        self.assertGreater(len(registry), 100)
        self.assertEqual(list(registry), sorted(registry))
        self.assertIn("data/evidence/wp1-evidence.json", source_hashes)
        self.assertIn("data/derived/s1-jianshu-historical-assertions.json", source_hashes)
        self.assertTrue(any(record.source_layer == "jianshu_note" for record in registry.values()))
        for record in registry.values():
            self.assertNotIn("data/generated", record.source_path)
            self.assertNotIn("data/annotation", record.source_path)
            self.assertNotIn("site/public/generated", record.source_path)

    def test_search_and_open_are_bounded_and_provenance_bearing(self) -> None:
        registry, _ = build_evidence_registry(ROOT)
        session = LocalEvidenceSearch(registry)
        result = session.search(
            "庾亮 陶侃 苏峻",
            entity_hints=["庾亮", "陶侃"],
            source_layers=["liu_annotation", "jianshu_note"],
            top_k=5,
        )
        self.assertGreater(result["result_count"], 0)
        self.assertLessEqual(result["result_count"], 5)
        hit = result["hits"][0]
        self.assertIn("evidence_ref", hit)
        self.assertIn("locator", hit)
        self.assertIn("quote", hit)
        opened = session.open(hit["evidence_ref"])
        self.assertEqual(opened["evidence_ref"], hit["evidence_ref"])
        with self.assertRaises(ValueError):
            session.open("not-returned-by-search")

    def test_only_the_two_controlled_tools_are_exposed(self) -> None:
        self.assertEqual(
            [tool["function"]["name"] for tool in DS1_2_TOOLS],
            ["search_local_evidence", "open_local_evidence"],
        )
        serialized = json.dumps(DS1_2_TOOLS, ensure_ascii=False)
        self.assertNotIn("read_file", serialized)
        self.assertNotIn("shell", serialized)
        self.assertNotIn("web", serialized)

    def test_provider_dsml_tool_calls_are_translated_only_to_allowed_function_calls(self) -> None:
        content = (
            '<｜｜DSML｜｜invoke name="search_local_evidence">'
            '<｜｜DSML｜｜parameter name="query" string="true">庾亮 陶侃</｜｜DSML｜｜parameter>'
            '<｜｜DSML｜｜parameter name="entity_hints" string="false">["庾亮", "陶侃"]</｜｜DSML｜｜parameter>'
            '</｜｜DSML｜｜invoke>'
        )
        calls = parse_dsml_tool_calls(content)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["function"]["name"], "search_local_evidence")
        self.assertEqual(calls[0]["function"]["arguments"]["entity_hints"], ["庾亮", "陶侃"])

    def test_mocked_tool_loop_records_search_then_open_without_api_call(self) -> None:
        registry, _ = build_evidence_registry(ROOT)
        session = LocalEvidenceSearch(registry)
        preview = LocalEvidenceSearch(registry).search(
            "庾亮 陶侃 苏峻",
            entity_hints=["庾亮", "陶侃"],
            top_k=5,
        )
        first_ref = preview["hits"][0]["evidence_ref"]
        responses = [
            {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "call-search",
                            "type": "function",
                            "function": {
                                "name": "search_local_evidence",
                                "arguments": json.dumps({"query": "庾亮 陶侃 苏峻", "entity_hints": ["庾亮", "陶侃"], "top_k": 5}, ensure_ascii=False),
                            },
                        }],
                    }
                }],
                "usage": {"total_tokens": 10},
            },
            {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "call-open",
                            "type": "function",
                            "function": {
                                "name": "open_local_evidence",
                                "arguments": json.dumps({"evidence_ref": first_ref}, ensure_ascii=False),
                            },
                        }],
                    }
                }],
                "usage": {"total_tokens": 20},
            },
            {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": json.dumps({
                            "historical_preconditions": [{"text": "有待检索的政治背景。", "evidence_refs": [first_ref]}],
                            "participant_historical_states": [],
                            "relationship_state_before_scene": [],
                            "reader_needed_context": [],
                            "context_to_text_links": [],
                            "uncertainties": [],
                        }, ensure_ascii=False),
                    }
                }],
                "usage": {"total_tokens": 30},
            },
        ]

        def fake_model(_messages, **_kwargs):
            return responses.pop(0)

        result, steps, summary = run_tool_loop(
            messages=build_initial_messages(build_minimal_story_input(ROOT, STORY_ID)),
            search=session,
            model_call=fake_model,
            max_tool_rounds=6,
        )
        self.assertEqual(summary["tool_rounds"], 2)
        self.assertEqual(summary["tool_calls"], 2)
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0]["tool_name"], "search_local_evidence")
        self.assertEqual(steps[1]["tool_name"], "open_local_evidence")
        self.assertIn(first_ref, summary["returned_evidence_refs"])
        self.assertIn(first_ref, summary["opened_evidence_refs"])
        self.assertEqual(validate_final_result(result, summary["returned_evidence_refs"]), [])

    def test_final_claim_cannot_cite_unretrieved_evidence(self) -> None:
        value = {
            "historical_preconditions": [{"text": "unsupported", "evidence_refs": ["not-retrieved"]}],
            "participant_historical_states": [],
            "relationship_state_before_scene": [],
            "reader_needed_context": [],
            "context_to_text_links": [],
            "uncertainties": [],
        }
        self.assertTrue(validate_final_result(value, set()))

    def test_validator_passes_before_real_run(self) -> None:
        self.assertEqual(validate(ROOT), [])


if __name__ == "__main__":
    unittest.main()
