#!/usr/bin/env python3
"""Offline protocol tests for SRM0.4B (no DeepSeek calls)."""

from __future__ import annotations

import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import srm0_4b_common as common  # noqa: E402
import run_srm0_4b as runner  # noqa: E402


class SRM04BTests(unittest.TestCase):
    def test_frozen_story_set_and_live_fixture_isolation(self):
        self.assertEqual(common.FIXED_STORIES, (
            "25-paidiao-007", "19-xianyuan-010", "02-yanyu-053",
            "01-dexing-040", "09-pinzao-038", "33-youhui-012",
        ))
        live = common.output_directory("25-paidiao-007", execution_kind="live_model", run_id="run-x")
        fixture = common.output_directory("25-paidiao-007", execution_kind="fixture")
        self.assertIn("/live/run-x", live.as_posix())
        self.assertIn("/fixture/fixture-v1", fixture.as_posix())
        self.assertNotEqual(live, fixture)
        self.assertNotIn("/convergence/round-", live.as_posix())

    def test_initial_gaps_are_rejected_individually(self):
        material = {"main_text": "甲乙丙丁戊己庚辛。另有即答案。"}
        normalized, audit = common.normalize_initial_fail_soft({
            "gaps": [
                {"question_id": "Q1", "story_span": "甲乙", "gap": "人物处境为何影响正文？", "state": "unwanted"},
                {"question_id": "Q2", "story_span": "不存在", "gap": "另一个问题"},
                {"question_id": "Q3", "story_span": "丙丁", "gap": "可能是某种答案"},
            ],
            "harmless_extra": True,
        }, material)
        self.assertEqual([row["question_id"] for row in normalized["gaps"]], ["Q1"])
        reasons = {row["question_id"]: row["reason"] for row in audit["rejected_gaps"]}
        self.assertEqual(reasons["Q2"], "story_span_not_found")
        self.assertEqual(reasons["Q3"], "answer_or_explanation_leakage")
        self.assertTrue(any(row["action"] == "drop_extra_fields" for row in audit["normalizations"]))

    def test_singletons_extra_python_fields_and_quote_boundary_are_fail_soft(self):
        sources = {"J1": "甲乙丙。", "J2": "另一段。"}
        raw = {
            "updates": {
                "question_id": "Q1",
                "state": "model-owned-no",
                "next_action": "retrieve_local",
                "answered_aspects": {
                    "aspect_id": "Q1-A1",
                    "claim": "甲乙丙可提供直接线索。",
                    "evidence": [
                        {"ref": "J1", "quote": "甲乙丙。》"},
                        {"ref": "BAD", "quote": "不存在"},
                    ],
                },
                "unanswered_aspects": {"aspect_id": "Q1-U1", "gap": "仍有窄缺口", "reading_impact": "high"},
                "conflicts": [],
                "reading_sufficient": False,
                "historical_verification_open": False,
            },
            "harmless": "drop",
        }
        normalized, audit = common.normalize_delta_fail_soft(raw, sources, {"Q1"})
        update = normalized["updates"][0]
        self.assertEqual(update["answered_aspects"][0]["evidence"][0]["quote"], "甲乙丙。")
        self.assertEqual(update["unanswered_aspects"][0]["aspect_id"], "Q1-U1")
        self.assertTrue(any(row["action"] == "wrap_singleton_array" for row in audit["normalizations"]))
        self.assertTrue(any(row.get("reason") == "unknown_evidence_ref" for row in audit["rejected_evidence"]))
        self.assertTrue(any(row["action"] == "drop_extra_fields" for row in audit["normalizations"]))

    def test_invalid_claim_is_dropped_but_valid_update_survives(self):
        raw = {"updates": [{
            "question_id": "Q1", "answered_aspects": [
                {"aspect_id": "Q1-A1", "claim": "有效", "evidence": [{"ref": "J1", "quote": "甲"}]},
                {"aspect_id": "Q1-A2", "claim": "无效", "evidence": [{"ref": "BAD", "quote": "乙"}]},
            ],
            "unanswered_aspects": [], "conflicts": [], "reading_sufficient": False, "historical_verification_open": False,
        }]}
        normalized, audit = common.normalize_delta_fail_soft(raw, {"J1": "甲"}, {"Q1"})
        self.assertEqual(len(normalized["updates"]), 1)
        self.assertEqual(len(normalized["updates"][0]["answered_aspects"]), 1)
        self.assertEqual(len(audit["rejected_claims"]), 1)

    def test_material_delta_requires_validated_evidence(self):
        previous = {
            "question_id": "Q1", "story_span": "甲", "gap": "缺口", "supporting_refs": ["J1"],
            "claim_fingerprints": ["same"], "conflict_fingerprints": [], "working_answer": "原结论。",
            "reading_sufficient": False, "remaining_gap": "缺口",
        }
        current = dict(previous)
        self.assertEqual(common.material_delta_b(previous, current, used_refs=["J1"]), 0)
        changed = dict(current, claim_fingerprints=["new"], working_answer="新结论。")
        self.assertEqual(common.material_delta_b(previous, changed, used_refs=["J1"]), 1)
        no_evidence = dict(previous, claim_fingerprints=["new"], working_answer="新结论。")
        self.assertEqual(common.material_delta_b(previous, no_evidence, used_refs=[]), 0)

    def test_child_question_has_parent_aspect_and_q_indicator(self):
        parent = {"question_id": "Q1", "story_span": "甲乙", "gap": "原缺口"}
        children, rejected = common.make_children_b(parent, {"unanswered_aspects": [{"aspect_id": "Q1-U1", "gap": "更窄缺口", "reading_impact": "high"}]}, {"Q1"})
        self.assertFalse(rejected)
        self.assertEqual(children[0]["parent_question_id"], "Q1")
        self.assertEqual(children[0]["parent_aspect_id"], "Q1-U1")
        self.assertEqual(children[0]["story_span"], "甲乙")
        bad_children, bad_rejected = common.make_children_b(parent, {"unanswered_aspects": [{"aspect_id": "Q1-U2", "gap": "原缺口", "reading_impact": "high"}]}, {"Q1"})
        self.assertEqual(bad_children, [])
        self.assertEqual(bad_rejected[0]["reason"], "not_a_narrowing")

    def test_stop_rules_and_metric_bounds(self):
        history = [
            {"D_t": 0, "N_t": 0.1, "conflict_fingerprints": [], "reading_sufficient": False, "active": True},
            {"D_t": 0, "N_t": 0.0, "conflict_fingerprints": [], "reading_sufficient": False, "active": True},
        ]
        self.assertEqual(common.stop_reason_b(history, retrieval_attempts=2, adequate_attempts=0, evidence_round_count=2), "evidence_saturated")
        self.assertEqual(common.stop_reason_b([{**history[-1], "reading_sufficient": True}], retrieval_attempts=0, adequate_attempts=0, evidence_round_count=1), "reading_sufficient")
        conflict = [
            {"D_t": 1, "N_t": 1.0, "conflict_fingerprints": ["c"], "reading_sufficient": False, "active": True},
            {"D_t": 0, "N_t": 0.0, "conflict_fingerprints": ["c"], "reading_sufficient": False, "active": True},
        ]
        self.assertEqual(common.stop_reason_b(conflict, retrieval_attempts=2, adequate_attempts=1, evidence_round_count=2), "stable_conflict")
        self.assertEqual(common.stop_reason_b([{**history[-1], "D_t": 1}], retrieval_attempts=2, adequate_attempts=0, evidence_round_count=2), "unresolved_no_evidence")
        self.assertEqual(common.stop_reason_b([{**history[-1]}], retrieval_attempts=0, adequate_attempts=0, evidence_round_count=4), "hard_cap")

    def test_registry_excludes_generated_sources(self):
        registry = common.build_registry(ROOT)
        self.assertFalse(any("data/generated" in str(row.get("source_path", "")) for row in registry.values()))
        self.assertFalse(any("data/annotation" in str(row.get("source_path", "")) for row in registry.values()))

    def test_fixture_summary_cannot_enter_live_metrics(self):
        row = {
            "story_id": "25-paidiao-007", "protocol_errors": [], "semantic_failed_questions": [],
            "convergence_status": "converged", "terminal_reason_per_question": {"Q1": "reading_sufficient"},
            "evidence_rounds": [], "used_evidence": [], "structural_normalizations": [],
            "rejected_claims": [], "rejected_evidence": [],
        }
        fixture = runner._batch_summary([row], execution_kind="fixture")
        live = runner._batch_summary([row], execution_kind="live_model")
        self.assertEqual(fixture["aggregate"]["model_findings_count"], 0)
        self.assertNotIn("valid_live_story_count", fixture["aggregate"])
        self.assertEqual(live["aggregate"]["live_story_count"], 1)
        self.assertNotIn("fixture_story_count", live["aggregate"])

    def test_sandbox_denial_is_transport_class_not_protocol(self):
        error = RuntimeError("DeepSeek API request failed: [Errno 1] Operation not permitted")
        error.__cause__ = urllib.error.URLError(OSError("[Errno 1] Operation not permitted"))
        self.assertEqual(common.classify_deepseek_exception(error), "sandbox_denied")

    def test_live_preflight_aborts_before_story_artifacts(self):
        args = type("Args", (), {
            "fixture": False,
            "replay_existing": False,
            "story": None,
            "batch": True,
            "timeout": 1,
        })()
        with patch.object(runner, "run_live_preflight", return_value={"classification": "sandbox_denied"}) as preflight, patch.object(runner, "_run_story") as run_story:
            self.assertEqual(runner.run(args), 2)
        preflight.assert_called_once_with(1)
        run_story.assert_not_called()

    def test_reset_removes_only_srm04_results_and_preserves_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            selection = root / "data/generated/srm0/srm0-4a-selection.json"
            selection.parent.mkdir(parents=True, exist_ok=True)
            selection.write_text("{}", encoding="utf-8")
            (root / "data/generated/srm0/srm0-4a-batch-summary.json").write_text("{}", encoding="utf-8")
            (root / "data/generated/srm0/srm0-4b-live-summary.json").write_text("{}", encoding="utf-8")
            (root / "data/generated/srm0/srm0-4b-fixture-summary.json").write_text("{}", encoding="utf-8")
            for story_id in common.FIXED_STORIES:
                target = root / common.OUTPUT_BASE / story_id / "convergence"
                target.mkdir(parents=True, exist_ok=True)
                (target / "old.json").write_text("{}", encoding="utf-8")
            unrelated = root / "data/generated/srm0/other/convergence/keep.json"
            unrelated.parent.mkdir(parents=True, exist_ok=True)
            unrelated.write_text("{}", encoding="utf-8")
            removed = common.reset_srm0_4_results(root)
            self.assertEqual(len(removed), 9)
            self.assertTrue(selection.is_file())
            self.assertTrue(unrelated.is_file())
            status = json.loads((root / common.STATUS_PATH).read_text(encoding="utf-8"))
            self.assertEqual(status["stage"], "awaiting_clean_live_run")
            self.assertFalse(status["live_results_present"])
            self.assertFalse(status["fixture_results_present"])

    def test_transport_failure_is_excluded_from_protocol_metrics(self):
        row = {
            "story_id": "25-paidiao-007", "protocol_errors": [],
            "transport_errors": [{"failure_class": "read_timeout"}],
            "semantic_failed_questions": [], "convergence_status": "api_transport_failed",
            "terminal_reason_per_question": {"Q1": "api_transport_failure"},
            "evidence_rounds": [], "used_evidence": [], "structural_normalizations": [],
            "rejected_claims": [], "rejected_evidence": [],
        }
        summary = runner._batch_summary([row], execution_kind="live_model")
        self.assertEqual(summary["aggregate"]["api_transport_failure_count"], 1)
        self.assertEqual(summary["aggregate"]["protocol_failure_count"], 0)
        self.assertEqual(summary["aggregate"]["evaluable_story_count"], 0)


if __name__ == "__main__":
    unittest.main()
