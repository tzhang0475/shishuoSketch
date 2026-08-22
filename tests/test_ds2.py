from __future__ import annotations

import json
import unittest

from scripts.ds1_2_common import DS1_2_TOOLS, ROOT, build_evidence_registry, project_status_for_record, run_tool_loop
from scripts.ds2_common import (
    EPISTEMIC_STATUSES,
    PILOT_STORIES,
    PROJECT_STATUSES,
    DeduplicatingLocalEvidenceSearch,
    build_initial_messages,
    build_story_minimal_input,
    normalize_ds2_result,
    normalize_epistemic_status,
    project_status_for_refs,
    review_template,
    validate_ds2_result,
)


def empty_result(ref: str, project_status: str) -> dict[str, object]:
    return {
        "historical_situation": {
            "immediate_precondition": "supported context",
            "stakes": None,
            "scene_power_structure": None,
            "evidence_refs": [ref],
            "epistemic_status": "attested",
            "project_status": project_status,
        },
        "participant_historical_states": [],
        "relationship_state": [],
        "reader_needed_context": [{
            "text": "context",
            "why_needed": "needed for the scene",
            "evidence_refs": [ref],
            "epistemic_status": "attested",
            "project_status": project_status,
        }],
        "context_to_text_links": [],
        "uncertainties": [],
        "data_conflicts": [],
    }


class DS2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry, _ = build_evidence_registry(ROOT)

    def test_pilot_scope_and_minimal_inputs_are_generic(self) -> None:
        self.assertEqual(len(PILOT_STORIES), 7)
        self.assertEqual(
            [build_story_minimal_input(ROOT, story_id)["story_id"] for story_id in PILOT_STORIES],
            list(PILOT_STORIES),
        )
        self.assertTrue(all(build_story_minimal_input(ROOT, story_id)["story_text_original"] for story_id in PILOT_STORIES))

    def test_not_materialized_is_project_status_not_epistemic_dispute(self) -> None:
        record = next(
            record
            for record in self.registry.values()
            if record.review_status == "not_materialized" and (record.assertion_status or "").lower() == "explicit"
        )
        ref = record.evidence_ref
        self.assertEqual(project_status_for_record(record), "not_materialized")
        self.assertEqual(normalize_epistemic_status("attested", [ref], self.registry), "attested")
        self.assertNotEqual(project_status_for_refs([ref], self.registry), "disputed")

        disputed = next(record for record in self.registry.values() if (record.assertion_status or "").lower() == "disputed")
        self.assertEqual(normalize_epistemic_status("attested", [disputed.evidence_ref], self.registry), "conflicted")

    def test_model_result_is_normalized_to_four_reader_items_and_separate_statuses(self) -> None:
        ref = next(iter(self.registry))
        project = project_status_for_refs([ref], self.registry)
        raw = empty_result(ref, project)
        raw["reader_needed_context"] = [dict(raw["reader_needed_context"][0], text=f"context-{i}") for i in range(5)]
        normalized, adjustments = normalize_ds2_result(raw, [ref], self.registry)
        self.assertEqual(len(normalized["reader_needed_context"]), 4)
        self.assertTrue(adjustments)
        self.assertEqual(validate_ds2_result(normalized, [ref], self.registry), [])
        self.assertIn(normalized["historical_situation"]["epistemic_status"], EPISTEMIC_STATUSES)
        self.assertIn(normalized["historical_situation"]["project_status"], PROJECT_STATUSES)

    def test_mocked_ds2_tool_loop_uses_only_local_tools(self) -> None:
        story_id = PILOT_STORIES[1]
        minimal = build_story_minimal_input(ROOT, story_id)
        session = DeduplicatingLocalEvidenceSearch(self.registry, story_id=story_id)
        preview = session.search("人物 背景", top_k=1)
        ref = preview["hits"][0]["evidence_ref"]
        project = project_status_for_refs([ref], self.registry)
        responses = [
            {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "ds2-search",
                            "type": "function",
                            "function": {
                                "name": "search_local_evidence",
                                "arguments": json.dumps({"query": "人物 背景", "top_k": 1}, ensure_ascii=False),
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
                        "content": json.dumps(empty_result(ref, project), ensure_ascii=False),
                    }
                }],
                "usage": {"total_tokens": 20},
            },
        ]

        def fake_model(_messages, **_kwargs):
            return responses.pop(0)

        result, steps, summary = run_tool_loop(
            messages=build_initial_messages(minimal),
            search=session,
            tools=DS1_2_TOOLS,
            model_call=fake_model,
            max_tool_rounds=6,
        )
        self.assertEqual(summary["tool_rounds"], 1)
        self.assertEqual(len(steps), 1)
        normalized, _ = normalize_ds2_result(result, summary["returned_evidence_refs"], self.registry)
        self.assertEqual(validate_ds2_result(normalized, summary["returned_evidence_refs"], self.registry), [])

    def test_review_template_is_exact_pilot_and_has_no_gold_fields(self) -> None:
        template = review_template()
        self.assertEqual([row["story_id"] for row in template["records"]], list(PILOT_STORIES))
        self.assertTrue(all("gold" not in json.dumps(row, ensure_ascii=False).lower() for row in template["records"]))


if __name__ == "__main__":
    unittest.main()
