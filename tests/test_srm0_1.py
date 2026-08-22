"""Focused SRM0.1 tests; no paid API calls are made here."""

from __future__ import annotations

import unittest
from pathlib import Path

from scripts.srm0_1_common import (
    STORY_ID,
    build_initial_packet,
    build_memory_state,
    build_source_registry,
    compression_metrics,
    normalize_memory_patch,
    normalize_question_output,
    retrieve_windows,
    validate_memory_patch,
    validate_question_output,
)


ROOT = Path(__file__).resolve().parents[1]
STORY_TEXT = "陶自起止之。庾乃引咎責躬，深相遜謝。"


class SRM01Tests(unittest.TestCase):
    def test_initial_packet_is_narrow_and_deduplicated(self) -> None:
        packet, metrics = build_initial_packet(ROOT, STORY_ID)
        self.assertEqual(packet["story_id"], STORY_ID)
        person_ids = [row["person_id"] for row in packet["person_orientation_cards"]]
        self.assertEqual(len(person_ids), len(set(person_ids)))
        self.assertEqual(len(packet["liu_annotations"]), 4)
        self.assertTrue(packet["known_conflict_notices"])
        self.assertNotIn("historical_facts", packet)
        self.assertNotIn("biography", packet)
        self.assertGreater(metrics["raw_input_chars"], 0)

    def test_question_contract_has_exact_spans_one_active_and_three_to_five_probes(self) -> None:
        value = normalize_question_output(
            {
                "textual_puzzles": [
                    {"span": "陶自起止之", "category": "relationship_state", "unexplained": "x", "reading_target": "陶自起止之", "importance": "high"},
                    {"span": "庾乃引咎責躬", "category": "causal_precondition", "unexplained": "y", "reading_target": "庾乃引咎責躬", "importance": "medium"},
                ],
                "active_question": {"question": "为什么？", "derived_from": ["P1"], "why_needed": "需要", "reading_target": "陶自起止之", "importance": "high"},
                "search_probes": ["蘇峻之難", "陶侃盟主", "庾亮敗績"],
            },
            STORY_TEXT,
        )
        self.assertEqual(validate_question_output(value, STORY_TEXT), [])
        self.assertEqual(value["active_question"]["status"], "active")
        self.assertEqual(len(value["textual_puzzles"]), 2)

    def test_retrieval_is_deterministic_and_does_not_need_punctuation(self) -> None:
        registry, _ = build_source_registry(ROOT)
        first = retrieve_windows(registry, ["蘇峻之難"], entity_hints=["庾亮"], exclude_story_id=STORY_ID)
        second = retrieve_windows(registry, ["蘇峻之難"], entity_hints=["庾亮"], exclude_story_id=STORY_ID)
        punctuation = retrieve_windows(registry, ["蘇峻之難。"], entity_hints=["庾亮"], exclude_story_id=STORY_ID)
        self.assertEqual(first, second)
        self.assertGreater(first["selected_candidate_count"], 0)
        self.assertGreater(punctuation["selected_candidate_count"], 0)
        self.assertLessEqual(len(first["model_candidates"]), 8)
        self.assertLessEqual(first["model_evidence_chars"], 2000)
        self.assertTrue(all(not row["ref"].startswith("data/generated") for row in first["model_candidates"]))

    def test_memory_patch_cannot_keep_unretrieved_refs(self) -> None:
        patch = normalize_memory_patch(
            {
                "evidence_decisions": [{"evidence_ref": "ok", "decision": "keep", "reason": "x"}, {"evidence_ref": "bad", "decision": "keep"}],
                "claim_updates": [{"claim_id": "C1", "operation": "add", "update_type": "new_evidence", "text": "x", "evidence_refs": ["ok"], "epistemic_status": "uncertain"}],
                "question_updates": [],
                "new_questions": [{"question_id": "Q2", "question": "如何核查？", "derived_from": ["Q1"], "why_needed": "需要", "reading_target": "陶自起止之", "importance": "medium", "next_active_question": True}],
                "reading_link_updates": [{"text_span": "陶自起止之", "reading_effect": "x", "evidence_refs": ["ok"]}],
                "stop_recommendation": {"stop": True},
            },
            ["ok"],
            STORY_TEXT,
        )
        self.assertEqual([row["evidence_ref"] for row in patch["evidence_decisions"]], ["ok"])
        self.assertEqual(validate_memory_patch(patch, ["ok"], STORY_TEXT), [])

    def test_state_events_are_external_and_ordered(self) -> None:
        patch = {
            "evidence_decisions": [{"evidence_ref": "r1", "decision": "keep", "reason": "supported"}],
            "claim_updates": [{"claim_id": "C1", "operation": "add", "update_type": "new_evidence", "text": "线索", "evidence_refs": ["r1"], "epistemic_status": "uncertain"}],
            "question_updates": [{"question_id": "Q1", "status": "superseded", "reason": "narrowed"}],
            "new_questions": [{"question_id": "Q2", "question": "如何核查？", "derived_from": ["Q1"], "why_needed": "需要", "reading_target": "陶自起止之", "importance": "medium", "next_active_question": True}],
            "reading_link_updates": [{"text_span": "陶自起止之", "reading_effect": "重读", "evidence_refs": ["r1"]}],
        }
        state, events = build_memory_state(STORY_ID, {"question_id": "Q1"}, {"model_candidates": [{"ref": "r1"}]}, patch, execution_kind="fixture", run_id="test")
        self.assertFalse(state["canonical_write_back"])
        self.assertEqual(state["iteration"], 1)
        self.assertEqual([event["sequence"] for event in events], list(range(1, len(events) + 1)))
        self.assertEqual(len({event["event_id"] for event in events}), len(events))
        self.assertFalse(any("chain_of_thought" in event for event in events))

    def test_usage_and_compression_fields_are_present(self) -> None:
        metrics = compression_metrics(100, 50, 80, 40)
        self.assertEqual(set(metrics), {"raw_input_chars", "model_input_chars", "compression_ratio", "raw_retrieval_chars", "model_evidence_chars"})
        self.assertEqual(metrics["compression_ratio"], 0.5)


if __name__ == "__main__":
    unittest.main()
