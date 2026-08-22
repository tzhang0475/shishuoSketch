"""Focused SRM0.2M contract tests; no API calls."""

from __future__ import annotations

import unittest
from pathlib import Path

from scripts.srm0_2m_common import (
    STORY_ID,
    SYSTEM_PROMPT,
    build_messages,
    build_model_payload,
    load_entry,
    normalize_layered,
    resolve_jianshu_material,
    validate_layered,
)
from scripts.run_srm0_2m import comparison_with_0_2b


ROOT = Path(__file__).resolve().parents[1]


class SRM02MTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.material = resolve_jianshu_material(ROOT)

    def test_resolves_same_story_liu_and_jianshu_deterministically(self) -> None:
        first = resolve_jianshu_material(ROOT)
        second = resolve_jianshu_material(ROOT)
        self.assertEqual(first, second)
        self.assertEqual(first["story_id"], STORY_ID)
        self.assertEqual(len(first["entry"]["liu_annotations"]), 10)
        self.assertEqual(len(first["notes"]), 14)
        self.assertEqual(first["jianshu_chars"], 1629)
        self.assertEqual(first["jianshu_mode"], "full")
        self.assertIn("collation_note", {note["layer"] for note in first["notes"]})
        self.assertIn("程炎震", {note["speaker"] for note in first["notes"] if note["speaker"]})

    def test_model_packet_has_explicit_layers_and_no_audit_metadata(self) -> None:
        payload = build_model_payload(self.material)
        self.assertEqual(set(payload), {"story_id", "primary_text", "early_commentary", "later_commentary"})
        self.assertEqual(payload["later_commentary"]["mode"], "full")
        self.assertEqual(len(payload["early_commentary"]["notes"]), 10)
        self.assertEqual(len(payload["later_commentary"]["notes"]), 14)
        serialized = str(payload)
        for forbidden in ("source_sha256", "source_path", "person_id", "relation_graph", "historical_fact", "prior_srm"):
            self.assertNotIn(forbidden, serialized)

    def test_prompt_does_not_import_prior_question_taxonomy(self) -> None:
        for forbidden in ("identity", "participant_state", "causal_precondition", "search_probes", "active_question"):
            self.assertNotIn(forbidden, SYSTEM_PROMPT)
        self.assertIn("正文", SYSTEM_PROMPT)
        self.assertIn("刘孝标注", SYSTEM_PROMPT)
        self.assertIn("余嘉锡", SYSTEM_PROMPT)

    def test_main_text_anchor_is_required_and_commentary_issue_is_separate(self) -> None:
        raw = {
            "reading_questions": [
                {
                    "story_span": "山公以器重朝望年踰七十猶知管時任",
                    "question": "开头如何定位山公？",
                    "why_it_matters": "正文开头建立人物位置。",
                    "commentary_clues": [{"ref": "L01", "effect": "补充字与出处。"}],
                    "reading_change_if_answered": "会改变对开头人物定位的理解。",
                    "additional_evidence_needed": "同时代任职材料。",
                }
            ],
            "commentary_issues": [
                {
                    "issue": "引文作者存在差异",
                    "trigger_ref": "J02",
                    "trigger_text": "王隱晉書曰",
                    "relevance_to_story_reading": "medium",
                    "reason": "可能影响对谣作者的判断。",
                }
            ],
            "person_connections": [],
            "appraisals": [],
        }
        normalized = normalize_layered(raw, self.material)
        self.assertEqual(validate_layered(raw, normalized, self.material), [])

        commentary_only = dict(raw)
        commentary_only["reading_questions"] = [dict(raw["reading_questions"][0], story_span="王隱晉書曰")]
        invalid = normalize_layered(commentary_only, self.material)
        self.assertTrue(any("primary text" in error for error in validate_layered(commentary_only, invalid, self.material)))

    def test_weak_relation_is_downgraded_and_authorship_is_not_a_relation(self) -> None:
        raw = {
            "reading_questions": [],
            "commentary_issues": [],
            "person_connections": [
                {
                    "persons": ["山涛", "和峤"],
                    "observation": "二人关系密切，只因同出现在诗句中。",
                    "basis_refs": ["MAIN"],
                    "evidence_strength": "explicit",
                    "needs_verification": False,
                },
                {
                    "persons": ["潘岳", "潘尼"],
                    "observation": "二人可能同族，且一处说潘岳、一处说潘尼作谣。",
                    "basis_refs": ["J07"],
                    "evidence_strength": "suggested",
                    "needs_verification": True,
                },
            ],
            "appraisals": [],
        }
        normalized = normalize_layered(raw, self.material)
        self.assertEqual(len(normalized["person_connections"]), 1)
        self.assertEqual(normalized["person_connections"][0]["evidence_strength"], "suggested")
        self.assertTrue(normalized["person_connections"][0]["needs_verification"])
        self.assertEqual(validate_layered(raw, normalized, self.material), [])

    def test_provider_aliases_align_spans_and_resolve_local_provenance(self) -> None:
        raw = {
            "reading_questions": [
                {
                    "anchor": "閣東有大牛和嶠鞅裴楷鞦王濟剔嬲不得休",
                    "question": "比喻如何理解？",
                    "why_unclear": "正文没有解释这些字词。",
                    "clues": "劉注引王隱晉書，余嘉錫箋疏引惠士奇說明鞅、鞦。",
                    "impact": "会改变对谣言的理解。",
                }
            ],
            "commentary_issues": [
                {"note_id": "J07", "issue": "版本异文", "detail": "需要核对版本。"}
            ],
            "person_connections": [
                {
                    "person_a": "山濤",
                    "person_b": "和嶠",
                    "connection": "同朝为官，正文并列。",
                    "evidence": "正文和嶠鞅；程炎震考证和嶠为中书令。",
                }
            ],
            "appraisals": [
                {"person": "山濤", "appraisal": "器重朝望", "source": "正文"}
            ],
        }
        normalized = normalize_layered(raw, self.material)
        self.assertEqual(validate_layered(raw, normalized, self.material), [])
        self.assertIn("\n", normalized["reading_questions"][0]["story_span"])
        self.assertTrue(normalized["reading_questions"][0]["commentary_clues"])
        self.assertEqual(normalized["commentary_issues"][0]["trigger_ref"], "J07")
        self.assertEqual(normalized["person_connections"][0]["persons"], ["山濤", "和嶠"])
        self.assertEqual(normalized["appraisals"][0]["basis_ref"], "MAIN")

    def test_comparison_is_python_deterministic(self) -> None:
        current = {"reading_questions": [], "person_connections": [], "appraisals": []}
        usage = {"prompt_tokens": 1, "completion_tokens": 2}
        self.assertEqual(
            comparison_with_0_2b(ROOT, self.material, current, usage),
            comparison_with_0_2b(ROOT, self.material, current, usage),
        )


if __name__ == "__main__":
    unittest.main()
