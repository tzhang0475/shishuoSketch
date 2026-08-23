"""Focused offline tests for SRM0.4D projection repair."""

from __future__ import annotations

import unittest

from scripts.run_srm0_4d import (
    TERMINAL_STATES,
    _conflict_is_genuine,
    _apply_repaired_update,
    _question_metrics,
    normalize_delta_repair,
    saturation_from_metrics,
    stable_conflict_from_metrics,
)


class SRM04DTests(unittest.TestCase):
    def test_valid_claim_survives_invalid_claim(self):
        raw = {
            "updates": [{
                "question_id": "Q1",
                "answered_aspects": [
                    {"aspect": "有效解释", "evidence": [{"ref": "E1", "quote": "甲乙"}]},
                    {"claim": "无效解释", "evidence": [{"ref": "E1", "quote": "不存在"}]},
                ],
                "unanswered_aspects": [],
                "conflicts": [],
                "reading_sufficient": False,
                "historical_verification_open": True,
            }]
        }
        normalized, audit = normalize_delta_repair(raw, {"E1": "甲乙丙"}, {"Q1"})
        self.assertEqual(len(normalized["updates"]), 1)
        self.assertEqual(normalized["updates"][0]["answered_aspects"][0]["claim"], "有效解释")
        self.assertTrue(any(row["reason"] == "quote_not_found" for row in audit["rejected_evidence"]))

    def test_aspect_alias_is_structural_only(self):
        raw = {"updates": {"question_id": "Q1", "answered_aspects": {"aspect": "说明", "evidence": {"ref": "E1", "quote": "甲"}}, "unanswered_aspects": [], "conflicts": [], "reading_sufficient": True, "historical_verification_open": True}}
        normalized, audit = normalize_delta_repair(raw, {"E1": "甲乙"}, {"Q1"})
        self.assertEqual(normalized["updates"][0]["answered_aspects"][0]["claim"], "说明")
        self.assertTrue(any(row["action"] == "field_alias" for row in audit["normalizations"]))

    def test_invalid_evidence_cannot_become_a_claim(self):
        raw = {"updates": [{"question_id": "Q1", "answered_aspects": [{"claim": "猜测", "evidence": [{"ref": "generated", "quote": "甲"}]}], "unanswered_aspects": [], "conflicts": [], "reading_sufficient": False, "historical_verification_open": False}]}
        normalized, _ = normalize_delta_repair(raw, {"E1": "甲"}, {"Q1"})
        self.assertEqual(normalized["updates"], [])

    def test_question_metrics_count_only_terminal_leaves(self):
        questions = {
            "Q1": {"question_id": "Q1", "terminal_state": None},
            "Q1.1": {"question_id": "Q1.1", "parent_question_id": "Q1", "terminal_state": "evidence_saturated"},
            "Q2": {"question_id": "Q2", "terminal_state": "reading_sufficient"},
        }
        metrics = _question_metrics(questions, semantic_failed=[], protocol_failed=[])
        self.assertEqual(metrics["evaluable_question_count"], 2)
        self.assertEqual(metrics["converged_question_count"], 2)
        self.assertEqual(metrics["evidence_saturated_question_count"], 1)
        self.assertEqual(set(TERMINAL_STATES), {"reading_sufficient", "evidence_saturated", "stable_conflict", "unresolved_no_evidence", "not_worth_pursuing", "hard_cap"})

    def test_two_zero_delta_rounds_saturate(self):
        rows = [
            {"round": 1, "D_t": 0, "N_t": 0.0, "question_metrics": [{"question_id": "Q1", "D_t": 0, "N_t": 0.0}]},
            {"round": 2, "D_t": 0, "N_t": 0.0, "question_metrics": []},
        ]
        self.assertTrue(saturation_from_metrics(rows, {"question_id": "Q1"}, 2))

    def test_incomplete_evidence_is_not_conflict(self):
        self.assertFalse(_conflict_is_genuine({"conflicts": [{"description": "未说明", "evidence": [{"ref": "E1"}]}]}))

    def test_stable_conflict_requires_same_conflict_twice(self):
        fingerprint = "same"
        self.assertTrue(stable_conflict_from_metrics([
            {"D_t": 0, "conflict_fingerprints": [fingerprint]},
            {"D_t": 0, "conflict_fingerprints": [fingerprint]},
        ]))
        self.assertFalse(stable_conflict_from_metrics([
            {"D_t": 1, "conflict_fingerprints": [fingerprint]},
            {"D_t": 0, "conflict_fingerprints": [fingerprint]},
        ]))

    def test_reading_sufficiency_preserves_open_verification(self):
        current, _ = _apply_repaired_update(
            {"question_id": "Q1", "story_span": "甲", "gap": "含义", "remaining_gap": "含义", "claim_fingerprints": [], "conflict_fingerprints": [], "reading_sufficient": False, "last_round": 0, "evidence_rounds": 0},
            {"question_id": "Q1", "answered_aspects": [{"aspect_id": "Q1-A1", "claim": "当前阅读足够", "evidence": [{"ref": "E1", "quote": "甲"}]}], "unanswered_aspects": [], "conflicts": [], "reading_sufficient": True, "historical_verification_open": True},
            used_refs_seen=set(),
        )
        self.assertEqual(current["terminal_state"], "reading_sufficient")
        self.assertTrue(current["historical_verification_open"])


if __name__ == "__main__":
    unittest.main()
