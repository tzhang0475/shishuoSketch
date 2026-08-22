"""Focused SRM0.1R contract tests; no API calls."""

from __future__ import annotations

import unittest
from pathlib import Path

from scripts.srm0_1r_common import (
    FROZEN_QUESTION,
    FROZEN_READING_TARGET,
    build_model_payload,
    build_state_events,
    load_frozen_inputs,
    normalize_semantic_result,
    validate_semantic_result,
)


ROOT = Path(__file__).resolve().parents[1]


class SRM01RTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.frozen = load_frozen_inputs(ROOT)
        cls.refs = [row["ref"] for row in cls.frozen["candidates"]]

    def valid_raw(self) -> dict:
        return {
            "useful_evidence": [{"ref": self.refs[0], "finding": "直接支持责任冲突。", "role": "direct_support"}],
            "question_resolution": {
                "question_id": "Q1",
                "status": "partially_resolved",
                "current_answer": "证据支持责任回应，但不能确定心理机制。",
                "remaining_gap": "原文省略了谈判细节。",
                "evidence_refs": [self.refs[0]],
            },
            "reading_links": [{"context": "责任背景", "text_span": FROZEN_READING_TARGET, "reading_effect": "保留原文省略。", "refs": [self.refs[0]]}],
            "static_relation_candidates": [],
            "appraisal_candidates": [],
            "candidate_subquestion": None,
            "deprioritized_associations": [{"idea": "后文治理材料解释此前释然", "reason": "时间方向不成立。", "trigger_refs": [self.refs[0]]}],
            "stop_recommendation": {"stop": True, "reason": "Q1部分回答，停止。"},
        }

    def test_freezes_q1_and_exactly_eight_candidates(self) -> None:
        self.assertEqual(self.frozen["question"], FROZEN_QUESTION)
        self.assertEqual(self.frozen["reading_target"], FROZEN_READING_TARGET)
        self.assertEqual(len(self.frozen["candidates"]), 8)
        self.assertEqual(self.frozen["candidate_hash"], load_frozen_inputs(ROOT)["candidate_hash"])

    def test_valid_semantic_result_and_python_events(self) -> None:
        result = normalize_semantic_result(self.valid_raw(), self.frozen["story_text"], self.refs)
        self.assertEqual(validate_semantic_result(result, self.frozen["story_text"], self.refs), [])
        state, events = build_state_events(self.frozen, result, run_id="test", execution_kind="fixture")
        self.assertEqual(state["seen_evidence_refs"], self.refs)
        self.assertEqual(state["seen_not_selected_refs"], self.refs[1:])
        self.assertFalse(state["canonical_write_back"])
        self.assertEqual([event["sequence"] for event in events], list(range(1, len(events) + 1)))
        self.assertIn("evidence_kept", {event["event_type"] for event in events})
        self.assertIn("seen_not_selected", {event["event_type"] for event in events})

    def test_old_database_style_shell_is_rejected(self) -> None:
        value = self.valid_raw()
        value["claim_updates"] = []
        value["evidence_decisions"] = []
        normalized = normalize_semantic_result(value, self.frozen["story_text"], self.refs)
        self.assertTrue(validate_semantic_result({**normalized, "claim_updates": [], "evidence_decisions": []}, self.frozen["story_text"], self.refs))

    def test_empty_finding_and_missing_resolution_are_rejected(self) -> None:
        value = self.valid_raw()
        value["useful_evidence"] = [{"ref": self.refs[0], "finding": "", "role": "context"}]
        value["question_resolution"] = {"question_id": "Q1", "status": "partially_resolved", "current_answer": "", "remaining_gap": "", "evidence_refs": []}
        normalized = normalize_semantic_result(value, self.frozen["story_text"], self.refs)
        errors = validate_semantic_result(normalized, self.frozen["story_text"], self.refs)
        self.assertTrue(any("current_answer" in error for error in errors))
        self.assertTrue(any("remaining_gap" in error for error in errors))

    def test_dynamic_relation_and_unknown_refs_are_rejected(self) -> None:
        value = self.valid_raw()
        value["useful_evidence"] = [{"ref": "not-frozen", "finding": "x", "role": "context"}]
        value["static_relation_candidates"] = [{"persons": ["person-001", "person-002"], "relation_type": "trust", "description": "关系密切", "evidence_refs": [self.refs[0]], "status": "candidate"}]
        value["reading_links"] = [{"context": "x", "text_span": FROZEN_READING_TARGET, "reading_effect": "x", "refs": ["not-frozen"]}]
        normalized = normalize_semantic_result(value, self.frozen["story_text"], self.refs)
        # Normalization drops unsafe optional candidates, while direct
        # validation still rejects an unsafe object if it reaches the boundary.
        self.assertEqual(normalized["useful_evidence"], [])
        self.assertEqual(normalized["static_relation_candidates"], [])
        direct = dict(normalized)
        direct["static_relation_candidates"] = value["static_relation_candidates"]
        self.assertTrue(validate_semantic_result(direct, self.frozen["story_text"], self.refs))

    def test_model_payload_contains_no_audit_metadata(self) -> None:
        payload = build_model_payload(self.frozen)
        self.assertEqual(set(payload), {"story_id", "story_text", "question", "evidence"})
        self.assertNotIn("source_path", str(payload))
        self.assertNotIn("source_sha256", str(payload))
        self.assertEqual([row["ref"] for row in payload["evidence"]], self.refs)

    def test_string_deprioritized_association_is_bound_to_frozen_evidence(self) -> None:
        value = self.valid_raw()
        value["deprioritized_associations"] = ["陶侃重视实际治理（噉薤留白）是否解释此前释然"]
        normalized = normalize_semantic_result(
            value,
            self.frozen["story_text"],
            self.refs,
            self.frozen["candidates"],
        )
        self.assertEqual(validate_semantic_result(normalized, self.frozen["story_text"], self.refs), [])
        self.assertEqual(len(normalized["deprioritized_associations"]), 1)
        self.assertIn("s1-assertion-1cc16661eadaf2634b20", normalized["deprioritized_associations"][0]["trigger_refs"])


if __name__ == "__main__":
    unittest.main()
