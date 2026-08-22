#!/usr/bin/env python3
"""Focused offline contracts for SRM0.3B."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.run_srm0_3b import fixture_delta, fixture_initial
from scripts.srm0_3b_common import (
    build_commentary_payload,
    build_initial_payload,
    derive_state,
    normalize_initial,
    normalize_semantic_delta,
    resolve_commentary_material,
    validate_initial,
    validate_semantic_delta,
    working_answer,
)
from scripts.ds1_common import ROOT, stable_json


class SRM03BTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.material = resolve_commentary_material(ROOT)

    def test_commentary_layers_are_partitioned_without_duplicate_liu(self) -> None:
        self.assertEqual(len(self.material["early_notes"]), 10)
        self.assertTrue(self.material["later_notes"])
        self.assertTrue(self.material["duplicate_notes"])
        self.assertFalse(any(note.get("layer") == "liu_annotation" for note in self.material["later_notes"]))

    def test_initial_payload_contains_only_primary_text(self) -> None:
        payload = build_initial_payload(self.material)
        self.assertEqual(set(payload), {"story_id", "primary_text"})
        self.assertNotIn("liu_annotations", json.dumps(payload, ensure_ascii=False))

    def test_commentary_payload_freezes_only_question_id_and_gap(self) -> None:
        initial = normalize_initial(fixture_initial(self.material), self.material)
        payload = build_commentary_payload(self.material, initial["gaps"])
        self.assertTrue(payload["frozen_questions"])
        self.assertTrue(all(set(row) == {"question_id", "gap"} for row in payload["frozen_questions"]))
        self.assertNotIn("why_unclear", json.dumps(payload, ensure_ascii=False))
        refs = {note["ref"] for note in self.material["early_notes"] + self.material["later_notes"]}
        sent = {note["ref"] for group in (payload["early_commentary"], payload["later_commentary"]) for note in group["notes"]}
        self.assertEqual(sent, refs)

    def test_initial_explanation_leak_is_rejected(self) -> None:
        raw = {
            "gaps": [{
                "question_id": "Q1",
                "story_span": self.material["entry"]["story_text"].splitlines()[0],
                "gap": "『知管時任』可能是掌选之意。",
            }]
        }
        normalized = normalize_initial(raw, self.material)
        self.assertIn("gap contains explanation or attempted answer", validate_initial(raw, normalized, self.material))

    def test_fixture_semantic_delta_has_exact_evidence(self) -> None:
        initial = normalize_initial(fixture_initial(self.material), self.material)
        raw = fixture_delta(self.material, initial)
        normalized = normalize_semantic_delta(raw, self.material, initial)
        self.assertEqual(validate_semantic_delta(raw, normalized, self.material, initial), [])

    def test_invalid_evidence_fails_closed_without_provenance_reconstruction(self) -> None:
        initial = normalize_initial(fixture_initial(self.material), self.material)
        raw = fixture_delta(self.material, initial)
        raw["updates"][0]["answered_aspects"][0]["evidence"][0] = {"ref": "J99", "quote": "猜测"}
        normalized = normalize_semantic_delta(raw, self.material, initial)
        errors = validate_semantic_delta(raw, normalized, self.material, initial)
        self.assertIn("evidence ref is invalid", errors)
        raw["updates"][0]["answered_aspects"][0]["evidence"][0] = {
            "ref": self.material["later_notes"][-1]["ref"],
            "quote": "猜测",
        }
        normalized = normalize_semantic_delta(raw, self.material, initial)
        errors = validate_semantic_delta(raw, normalized, self.material, initial)
        self.assertIn("evidence quote is not an exact substring", errors)

    def test_python_derives_state_and_next_action(self) -> None:
        initial = {"gaps": [{"question_id": "Q1", "story_span": "甲", "gap": "甲为何如此？"}]}
        base = {
            "question_id": "Q1",
            "answered_aspects": [],
            "unanswered_aspects": ["仍不清楚"],
            "conflicts": [],
            "reading_sufficient": False,
            "historical_verification_open": False,
            "remaining_reading_gap": "仍不清楚",
            "refined_question": "甲为何如此？",
        }
        state = derive_state(initial, {"updates": [base], "relation_candidates": [], "appraisal_candidates": []})
        self.assertEqual(state["questions"][0]["state"], "unexplained")
        self.assertEqual(state["questions"][0]["next_action"], "refine_question")

        sufficient = dict(base, answered_aspects=[{"claim": "注释给出线索", "evidence": [{"ref": "J1", "quote": "引文"}]}], unanswered_aspects=[], reading_sufficient=True, historical_verification_open=True, remaining_reading_gap=None, refined_question=None)
        state = derive_state(initial, {"updates": [sufficient], "relation_candidates": [], "appraisal_candidates": []})
        self.assertEqual(state["questions"][0]["state"], "substantially_explained")
        self.assertEqual(state["questions"][0]["next_action"], "stop")
        self.assertTrue(state["questions"][0]["historical_verification_open"])

        conflicted = dict(sufficient, conflicts=[{"description": "两种解释冲突", "evidence": [{"ref": "J1", "quote": "引文"}]}])
        state = derive_state(initial, {"updates": [conflicted], "relation_candidates": [], "appraisal_candidates": []})
        self.assertEqual(state["questions"][0]["state"], "conflicted")

    def test_working_answer_is_compact_and_state_has_no_quotes(self) -> None:
        answer = working_answer([{"claim": "第一条"}, {"claim": "第二条"}, {"claim": "第三条"}])
        self.assertEqual(answer, "第一条。第二条。")

    def test_model_contract_schema_is_valid_json(self) -> None:
        schema = json.loads((ROOT / "schema/srm0-3b-semantic-delta.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertIn("oneOf", schema)

    def test_input_projection_is_deterministic(self) -> None:
        initial = normalize_initial(fixture_initial(self.material), self.material)
        first = stable_json(build_commentary_payload(self.material, initial["gaps"]))
        second = stable_json(build_commentary_payload(resolve_commentary_material(ROOT), initial["gaps"]))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
