"""Focused SRM0.2B discovery-contract tests; no API calls."""

from __future__ import annotations

import unittest
from pathlib import Path

from scripts.srm0_2b_common import (
    STORY_ID,
    SYSTEM_PROMPT,
    build_messages,
    character_metrics,
    load_entry,
    model_payload,
    normalize_discovery,
    validate_discovery,
)


ROOT = Path(__file__).resolve().parents[1]


class SRM02BTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.entry = load_entry(ROOT)

    def test_packet_is_exactly_story_plus_all_liu_annotations(self) -> None:
        payload = model_payload(self.entry)
        self.assertEqual(payload["story_id"], STORY_ID)
        self.assertEqual(payload["chapter"], "政事第三")
        self.assertEqual(len(payload["liu_annotations"]), 10)
        self.assertEqual(payload["liu_annotations"][0]["annotation_id"], "annotation-001")
        self.assertEqual(payload["liu_annotations"][-1]["annotation_id"], "annotation-010")
        serialized = str(payload)
        for forbidden in ("source_sha256", "source_path", "evidence_ref", "person_id", "review_status"):
            self.assertNotIn(forbidden, serialized)

    def test_packet_construction_is_deterministic(self) -> None:
        self.assertEqual(model_payload(load_entry(ROOT)), model_payload(load_entry(ROOT)))
        first = build_messages(self.entry)
        second = build_messages(load_entry(ROOT))
        self.assertEqual(first, second)
        self.assertEqual(character_metrics(self.entry, first), character_metrics(load_entry(ROOT), second))

    def test_system_prompt_is_blind_and_has_no_prior_taxonomy(self) -> None:
        for forbidden in ("identity", "temporal", "participant_state", "relationship_state", "causal_precondition", "search_probes", "active_question"):
            self.assertNotIn(forbidden, SYSTEM_PROMPT)

    def test_valid_weak_discovery_result(self) -> None:
        trigger = self.entry["story_text"].splitlines()[0].strip()
        raw = {
            "questions": [
                {
                    "question": "为什么这样写？",
                    "trigger_text": trigger,
                    "why_it_matters": "触发了一个文本观察。",
                    "what_more_evidence_is_needed": "需要相关史料。",
                }
            ],
            "person_connections": [],
            "appraisals": [],
        }
        normalized = normalize_discovery(raw)
        self.assertEqual(validate_discovery(raw, normalized, self.entry), [])

    def test_empty_arrays_are_allowed_but_invalid_question_is_not(self) -> None:
        empty = {"questions": [], "person_connections": [], "appraisals": []}
        self.assertEqual(validate_discovery(empty, normalize_discovery(empty), self.entry), [])
        raw = {
            "questions": [
                {
                    "question": "泛泛问题",
                    "trigger_text": "不在材料中的文字",
                    "why_it_matters": "原因",
                    "what_more_evidence_is_needed": "史料",
                }
            ],
            "person_connections": [],
            "appraisals": [],
        }
        errors = validate_discovery(raw, normalize_discovery(raw), self.entry)
        self.assertTrue(any("trigger_text" in error for error in errors))

    def test_forbidden_taxonomy_ids_and_search_fields_are_rejected(self) -> None:
        trigger = self.entry["story_text"].splitlines()[0].strip()
        raw = {
            "questions": [
                {
                    "question": "问题",
                    "trigger_text": trigger,
                    "why_it_matters": "原因",
                    "what_more_evidence_is_needed": "史料",
                    "question_type": "identity",
                }
            ],
            "person_connections": [
                {
                    "persons": ["person-001", "某人"],
                    "observation": "关系",
                    "basis": "文字",
                    "needs_verification": True,
                    "relation_type": "kinship",
                }
            ],
            "appraisals": [],
            "search_probes": ["山公"],
        }
        errors = validate_discovery(raw, normalize_discovery(raw), self.entry)
        self.assertTrue(any("forbidden discovery field" in error for error in errors))
        self.assertTrue(any("Person ID" in error for error in errors))

    def test_natural_provider_aliases_are_normalized_without_new_semantics(self) -> None:
        raw = {
            "questions": [
                {
                    "question": "潘岳与潘尼的记载为何不同？",
                    "trigger": "刘注引王隐晋书：初涛领吏部，潘岳内非之，密为作谣",
                    "why": "正文与刘注形成差异。",
                    "needed_sources": "需要版本或传记材料。",
                }
            ],
            "person_connections": [
                {
                    "connection": "山涛与嵇康：刘注称二人相善。",
                    "evidence": "好荘老与嵇康善",
                }
            ],
            "appraisals": [
                {
                    "evaluator": "文士传",
                    "object": "潘尼",
                    "appraisal": "少有清才，文词温雅。",
                    "basis": "尼少有清才文詞溫雅",
                }
            ],
        }
        normalized = normalize_discovery(raw, self.entry)
        self.assertEqual(validate_discovery(raw, normalized, self.entry), [])
        self.assertTrue(normalized["questions"][0]["trigger_text"] in self.entry["liu_annotations"][6]["text"])
        self.assertEqual(normalized["person_connections"][0]["persons"], ["山涛", "嵇康"])
        self.assertEqual(normalized["appraisals"][0]["target"], "潘尼")


if __name__ == "__main__":
    unittest.main()
