"""Focused SRM0.3A contract tests; no API calls."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.srm0_3a_common import (
    build_commentary_payload,
    build_initial_payload,
    normalize_commentary,
    normalize_initial,
    project_events,
    project_state,
    resolve_commentary_material,
    validate_commentary,
    validate_initial,
)


ROOT = Path(__file__).resolve().parents[1]


class SRM03ATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.material = resolve_commentary_material(ROOT)
        cls.span = cls.material["entry"]["story_text"].splitlines()[0]
        cls.initial_raw = {
            "questions": [
                {
                    "question_id": "Q1",
                    "story_span": cls.span,
                    "question": "正文如何定位山公？",
                    "why_unclear_from_main_text": "正文未说明具体职任。",
                }
            ]
        }
        cls.initial = normalize_initial(cls.initial_raw)

    def test_commentary_partition_is_structural_and_deterministic(self) -> None:
        first = resolve_commentary_material(ROOT)
        second = resolve_commentary_material(ROOT)
        self.assertEqual(first, second)
        self.assertEqual(len(first["early_notes"]), 10)
        self.assertEqual(len(first["later_notes"]), 8)
        self.assertTrue(all(note["layer"] != "liu_annotation" for note in first["later_notes"]))
        self.assertEqual(first["duplicate_commentary_chars_removed"], 417)
        self.assertEqual(first["later_commentary_chars"], 1212)

    def test_round_one_payload_excludes_initial_explanation_and_duplicate_notes(self) -> None:
        payload = build_commentary_payload(self.material, self.initial["questions"])
        self.assertEqual(set(payload["questions"][0]), {"question_id", "story_span", "question"})
        self.assertEqual(len(payload["early_commentary"]["notes"]), 10)
        self.assertEqual(len(payload["later_commentary"]["notes"]), 8)
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("why_unclear_from_main_text", serialized)
        self.assertNotIn("source_locator", serialized)
        self.assertNotIn("text_sha256", serialized)
        self.assertNotIn("J01", serialized)
        self.assertNotIn("J06", serialized)

    def test_initial_span_and_commentary_quote_are_source_bound(self) -> None:
        self.assertEqual(validate_initial(self.initial_raw, self.initial, self.material), [])
        note = self.material["later_notes"][-1]
        commentary_raw = {
            "question_updates": [
                {
                    "question_id": "Q1",
                    "story_span": self.span,
                    "question": "正文如何定位山公？",
                    "state": "substantially_explained",
                    "working_answer": "程炎震提供了相关时段与职任线索。",
                    "evidence": [{"ref": note["ref"], "quote": note["text"][:12], "role": "supports"}],
                    "remaining_gap": "",
                    "next_action": "stop",
                    "refined_question": None,
                }
            ],
            "relation_candidates": [],
            "appraisal_candidates": [],
        }
        normalized = normalize_commentary(commentary_raw, self.material, self.initial)
        self.assertEqual(validate_commentary(commentary_raw, normalized, self.material, self.initial), [])

        wrong_ref = json.loads(json.dumps(commentary_raw, ensure_ascii=False))
        wrong_ref["question_updates"][0]["evidence"][0]["quote"] = "不属于该注的文字"
        wrong_normalized = normalize_commentary(wrong_ref, self.material, self.initial)
        self.assertTrue(any("exact substring" in error for error in validate_commentary(wrong_ref, wrong_normalized, self.material, self.initial)))

    def test_substantial_state_must_stop_and_clear_gap(self) -> None:
        raw = {
            "question_updates": [
                {
                    "question_id": "Q1",
                    "story_span": self.span,
                    "question": "正文如何定位山公？",
                    "state": "substantially_explained",
                    "working_answer": "注释给出足够线索。",
                    "evidence": [{"ref": "J14", "quote": self.material["later_notes"][-1]["text"][:8], "role": "supports"}],
                    "remaining_gap": "还可以查更多",
                    "next_action": "refine_question",
                    "refined_question": "正文如何定位山公？还需要查什么？",
                }
            ],
            "relation_candidates": [],
            "appraisal_candidates": [],
        }
        normalized = normalize_commentary(raw, self.material, self.initial)
        errors = validate_commentary(raw, normalized, self.material, self.initial)
        self.assertIn("substantially explained question has a remaining gap", errors)
        self.assertIn("substantially explained question must stop", errors)
        self.assertIn("substantially explained question cannot be refined", errors)

    def test_refined_question_must_remain_on_same_span(self) -> None:
        raw = {
            "question_updates": [
                {
                    "question_id": "Q1",
                    "story_span": self.span,
                    "question": "正文如何定位山公？",
                    "state": "partially_explained",
                    "working_answer": "注释只说明了一部分。",
                    "evidence": [{"ref": "J14", "quote": self.material["later_notes"][-1]["text"][:8], "role": "limits"}],
                    "remaining_gap": "职任与正文的关系仍不清楚。",
                    "next_action": "refine_question",
                    "refined_question": self.span + "的职任线索如何改变理解？",
                }
            ],
            "relation_candidates": [],
            "appraisal_candidates": [],
        }
        normalized = normalize_commentary(raw, self.material, self.initial)
        self.assertEqual(validate_commentary(raw, normalized, self.material, self.initial), [])

    def test_state_and_events_are_compact_deterministic_projections(self) -> None:
        commentary = {
            "question_updates": [
                {
                    "question_id": "Q1",
                    "story_span": self.span,
                    "question": "正文如何定位山公？",
                    "state": "substantially_explained",
                    "working_answer": "注释给出足够线索。",
                    "evidence": [{"ref": "J14", "quote": self.material["later_notes"][-1]["text"][:8], "role": "supports"}],
                    "remaining_gap": "",
                    "next_action": "stop",
                    "refined_question": None,
                }
            ],
            "relation_candidates": [],
            "appraisal_candidates": [],
        }
        state1 = project_state(self.initial, commentary)
        state2 = project_state(self.initial, commentary)
        self.assertEqual(state1, state2)
        self.assertEqual(project_events(self.initial, commentary), project_events(self.initial, commentary))
        self.assertNotIn("quote", json.dumps(state1, ensure_ascii=False))
        self.assertIn("question_substantially_explained", {event["event"] for event in project_events(self.initial, commentary)})


if __name__ == "__main__":
    unittest.main()
