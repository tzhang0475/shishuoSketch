from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import historical_context_algorithm as algorithm  # noqa: E402
import run_hng2_algorithm_closeout as closeout  # noqa: E402


class VisibleTemporalAnchorTests(unittest.TestCase):
    def test_scanner_reports_only_literal_lexical_occurrences(self) -> None:
        windows = [algorithm.prepare_evidence_window({"ref": "r", "text": "正始之音；武帝時", "evidence_text": "正始之音；武帝時"})]
        rows = algorithm.scan_visible_temporal_anchors(windows)
        by_surface = {row["surface"]: row for row in rows}
        self.assertIn("正始", by_surface)
        self.assertIn("武帝", by_surface)
        for row in rows:
            self.assertIn(row["exact_occurrence"], windows[0]["evidence_text"])
            self.assertNotIn("temporal_role", row)
            self.assertNotIn("scene_time", row)
            self.assertNotIn("normalized_year", row)

    def test_temporal_prompt_marks_visible_surfaces_as_hints(self) -> None:
        windows = [algorithm.prepare_evidence_window({"ref": "r", "text": "武帝時", "evidence_text": "武帝時"})]
        hints = algorithm.scan_visible_temporal_anchors(windows)
        prompt = algorithm.temporal_read_prompt({"story_id": "s"}, windows, hints)
        self.assertEqual(prompt["visible_temporal_surfaces"], hints)
        self.assertIn("recall hints", algorithm.TEMPORAL_ANCHOR_ATOM_SYSTEM)
        self.assertIn("不是历史结论".replace("历", "歷"), algorithm.TEMPORAL_ANCHOR_ATOM_SYSTEM.replace("历", "歷"))

    def test_h0a_matching_prefers_exact_story_layer_and_longest_surface(self) -> None:
        item = {
            "temporal_surface": "永嘉六年",
            "temporal_role": "scene_time",
            "evidence_ref": "hng2c1-shishuo-17-shangshi-006-main",
            "exact_span": "衛洗馬以永嘉六年喪",
        }
        result = algorithm.story_temporal_h0a_compatibility(item, "17-shangshi-006")
        self.assertEqual(result["status"], "compatible")
        self.assertEqual(result["raw_surface"], "衛洗馬以永嘉六年")


class CloseoutReplayTests(unittest.TestCase):
    def test_selection_is_frozen_h0a_set(self) -> None:
        selection = closeout.build_selection()
        self.assertEqual(selection["story_count"], 10)
        self.assertEqual(selection["semantic_call_count"], 20)
        story_ids = [row["story_id"] for row in selection["stories"]]
        self.assertEqual(len(story_ids), len(set(story_ids)))
        for required in ("01-dexing-017", "04-wenxue-022", "06-yaliang-017"):
            self.assertIn(required, story_ids)

    def test_person_replay_uses_no_api_and_fixes_generic_identity_chain(self) -> None:
        replay = closeout.replay_person_outputs()
        self.assertEqual(replay["api_calls"], 0)
        self.assertTrue(replay["regression_checks"]["yi_resolves_person_053"])
        self.assertTrue(replay["regression_checks"]["yu_taiwei_unchanged"])
        self.assertTrue(replay["regression_checks"]["shan_tao_unchanged"])
        self.assertTrue(replay["regression_checks"]["chen_qian_candidate_only"])
        self.assertTrue(replay["regression_checks"]["xuan_unresolved"])
        self.assertTrue(replay["regression_checks"]["yu_unresolved"])
        self.assertEqual(replay["metrics"]["nonperson_person_id_anomalies"], 0)
        self.assertEqual(replay["metrics"]["collapsed_nonidentity_self_relations"], 0)
        self.assertTrue(replay["person_lane_frozen"])

    def test_source_expansion_requires_separate_abbreviation_occurrence(self) -> None:
        case = {
            "observation": {"surface": "廙"},
            "candidates": [{"candidate_key": "c0", "person_id": "person-053", "canonical_name": "王廙", "known_forms": ["王廙"]}],
            "constraint_checks": [],
            "seed": {},
        }
        validation = {
            "valid_entities": [{"entity_key": "e0", "surface": "廙", "entity_kind": "abbreviated_name", "reference_form": "abbreviated", "evidence_refs": ["r"]}],
            "valid_relations": [],
        }
        only_full = [algorithm.prepare_evidence_window({"ref": "r", "text": "眾拒王廙", "evidence_text": "眾拒王廙"})]
        result = algorithm.normalize_person_fill(validation, case=case, windows=only_full)
        self.assertEqual(result["source_grounded_identity_expansions"], [])
        target = next(row for row in result["entities"] if row["surface"] == "廙")
        self.assertIsNone(target["resolved_person_id"])


if __name__ == "__main__":
    unittest.main()
