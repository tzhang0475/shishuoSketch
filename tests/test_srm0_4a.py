#!/usr/bin/env python3
"""Offline contract tests for SRM0.4A."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import srm0_4a_common as common  # noqa: E402


class SRM04ATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selection = common.selection(ROOT)
        cls.registry = common.build_retrieval_registry(ROOT)

    def test_selection_is_deterministic_and_excludes_prior_stories(self):
        self.assertEqual(self.selection, common.selection(ROOT))
        selected = self.selection["selected"]
        self.assertEqual(len(selected), 6)
        self.assertEqual({row["class"] for row in selected}, {"rich_commentary", "medium_commentary", "low_context_control"})
        self.assertEqual(sum(row["class"] == "rich_commentary" for row in selected), 3)
        self.assertEqual(sum(row["class"] == "medium_commentary" for row in selected), 2)
        self.assertEqual(sum(row["class"] == "low_context_control" for row in selected), 1)
        self.assertTrue({row["story_id"] for row in selected}.isdisjoint(common.EXCLUDED_STORIES))

    def test_jianshu_attached_material_excludes_duplicate_liu_layer(self):
        story = common.story_material(ROOT, self.selection["selected"][0]["story_id"])
        self.assertTrue(all(row["source_layer"] != "liu_annotation" for row in story["jianshu_notes"]))
        refs = set(story["attached"])
        self.assertEqual(refs, {"MAIN", *(row["ref"] for row in story["liu_notes"]), *(row["ref"] for row in story["jianshu_notes"])})

    def test_gap_gates_keep_high_leverage_and_remove_direct_story_answer(self):
        material = {"main_text": "甲即乙丙"}
        span = "甲"
        accepted, audit = common.apply_gap_gates(
            [
                {"question_id": "Q1", "story_span": span, "gap": "人物处境为何改变？"},
                {"question_id": "Q2", "story_span": span, "gap": "『乙丙』指什么？"},
            ],
            material,
        )
        self.assertEqual([row["question_id"] for row in accepted], ["Q1"])
        self.assertEqual(audit[1]["gate"], "removed")

    def test_boundary_quote_normalization_is_audited(self):
        source = "甲乙丙。"
        value, method = common._normalize_quote("甲乙丙。》", source)
        self.assertEqual(value, source)
        self.assertEqual(method, "boundary_punctuation_trimmed")

    def test_retrieval_is_local_deterministic_and_has_provenance(self):
        first = common.search_registry(self.registry, "蘇峻", top_k=8)
        second = common.search_registry(self.registry, "蘇峻", top_k=8)
        self.assertEqual(first, second)
        self.assertTrue(first["hits"])
        for row in first["hits"]:
            self.assertIn("ref", row)
            self.assertIn("work", row)
            self.assertIn("source_layer", row)
            self.assertIn("snippet", row)
            self.assertNotIn("data/generated/", str(row.get("source_path", "")))

    def test_state_and_convergence_metrics(self):
        question = {"question_id": "Q1", "story_span": "甲", "gap": "甲为何如此？"}
        update = {
            "answered_aspects": [{"aspect_id": "Q1-A1", "claim": "证据说明。", "evidence": [{"ref": "x", "quote": "甲"}]}],
            "unanswered_aspects": [],
            "conflicts": [],
            "reading_sufficient": True,
            "historical_verification_open": True,
        }
        state = common.derive_question_state(question, update)
        self.assertEqual(state["state"], "substantially_explained")
        self.assertEqual(state["terminal_reason"], "reading_sufficient")
        self.assertEqual(common.semantic_delta_changed(None, state), 1)
        self.assertAlmostEqual(common.evidence_novelty(["a", "a"], set())[0], 1.0)
        self.assertTrue(common.saturation([{"D_t": 0, "N_t": 0.1}, {"D_t": 0, "N_t": 0.0}]))

    def test_refined_question_keeps_parent_and_aspect_link(self):
        question = {"question_id": "Q1", "story_span": "甲乙", "gap": "为何如此？"}
        update = {
            "unanswered_aspects": [{"aspect_id": "Q1-U1", "gap": "更窄的缺口", "reading_impact": "high"}],
        }
        children = common.make_refined_questions(question, update)
        self.assertEqual(children[0]["question_id"], "Q1.1")
        self.assertEqual(children[0]["parent_question_id"], "Q1")
        self.assertEqual(children[0]["parent_aspect_id"], "Q1-U1")
        self.assertEqual(children[0]["story_span"], question["story_span"])

    def test_retrieval_registry_excludes_model_output_sources(self):
        self.assertFalse(any("data/generated" in str(row.get("source_path", "")) for row in self.registry.values()))
        self.assertFalse(any("data/annotation" in str(row.get("source_path", "")) for row in self.registry.values()))


if __name__ == "__main__":
    unittest.main()
