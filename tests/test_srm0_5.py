#!/usr/bin/env python3
"""Focused offline SRM0.5 protocol tests; no DeepSeek calls."""

from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_srm0_5 as srm  # noqa: E402


class SRM05Tests(unittest.TestCase):
    def test_selection_is_five_by_five_by_five_and_reproducible(self) -> None:
        document = srm.selection_document(ROOT)
        selected = document["selected"]
        self.assertEqual(len(selected), 15)
        self.assertEqual({row["stratum"] for row in selected}, set(srm.STRATA))
        for stratum in srm.STRATA:
            self.assertEqual(sum(row["stratum"] == stratum for row in selected), 5)
        self.assertEqual(document["selected_story_ids"], [row["story_id"] for row in selected])
        self.assertEqual(document["selected_story_ids"], srm.selection_document(ROOT)["selected_story_ids"])
        self.assertFalse(set(document["selected_story_ids"]) & set(document["excluded_stories"]))

    def test_selection_has_deterministic_keys_and_protocol_snapshot(self) -> None:
        selection = json.loads((ROOT / srm.SELECTION_PATH).read_text(encoding="utf-8"))
        self.assertEqual(selection["prompt_version"], srm.PROMPT_VERSION)
        self.assertEqual(selection["selected_story_ids"], [row["story_id"] for row in selection["selected"]])
        for row in selection["selected"]:
            self.assertEqual(row["deterministic_selection_key"], srm._selection_key(row["story_id"]))
        freeze = json.loads((ROOT / srm.OUTPUT_ROOT / "protocol-freeze.json").read_text(encoding="utf-8"))
        self.assertEqual(freeze["prompt_version"], srm.PROMPT_VERSION)
        self.assertEqual(freeze["selection_hash"], srm._hash_value(selection["selected_story_ids"]))
        self.assertFalse(freeze["canonical_write_back"])

    def test_fixture_isolation(self) -> None:
        fixture = json.loads((ROOT / srm.OUTPUT_ROOT / "fixture-summary.json").read_text(encoding="utf-8"))
        self.assertEqual(fixture["execution_kind"], "fixture")
        self.assertTrue(fixture["fixture_only"])
        self.assertNotIn("live_model", {row.get("execution_kind") for row in fixture["stories"]})
        live = ROOT / srm.SUMMARY_PATH
        if live.exists():
            live_doc = json.loads(live.read_text(encoding="utf-8"))
            self.assertEqual(live_doc.get("execution_kind"), "live_model")
            self.assertFalse(live_doc.get("fixture_only", False))

    def test_question_metrics_are_question_level(self) -> None:
        questions = {
            "Q1": {"failure_type": None, "terminal_reason": "refined_to_child", "active": False},
            "Q1.1": {"failure_type": None, "terminal_reason": "evidence_saturated", "active": False},
            "Q2": {"failure_type": "semantic_failed", "terminal_reason": "semantic_failed", "active": False},
            "Q3": {"failure_type": None, "terminal_reason": None, "active": True},
        }
        metrics = srm._question_metrics(questions)
        self.assertEqual(metrics["evaluable_question_count"], 3)
        self.assertEqual(metrics["valid_question_count"], 2)
        self.assertEqual(metrics["converged_question_count"], 1)
        self.assertEqual(metrics["semantic_failed_question_count"], 1)
        self.assertEqual(metrics["unresolved_question_count"], 1)

    def test_transport_metrics_are_not_protocol_metrics(self) -> None:
        metrics = srm._transport_metrics([
            {"transport_metrics": {"transport_request_count": 2, "transport_retry_count": 1, "transport_success_count": 1, "failure_classes": {"read_timeout": 1}, "successful_latencies_seconds": [1.25]}},
            {"transport_metrics": {"transport_request_count": 1, "transport_retry_count": 0, "transport_success_count": 1, "failure_classes": {}, "successful_latencies_seconds": [2.0]}},
        ])
        self.assertEqual(metrics["transport_request_count"], 3)
        self.assertEqual(metrics["transport_retry_count"], 1)
        self.assertEqual(metrics["read_timeout_count"], 1)
        self.assertEqual(metrics["transport_success_count"], 2)

    def test_retrieval_need_counts_attempts_without_accepted_hits(self) -> None:
        self.assertEqual(srm._retrieval_need_count({"Q1": 0, "Q1.1": 1, "Q2": 2}), 2)
        questions = {
            "Q1": {"terminal_reason": "reading_sufficient"},
            "Q1.1": {"terminal_reason": "not_worth_pursuing"},
        }
        self.assertEqual(srm._commentary_only_count(questions, {"Q1": 0, "Q1.1": 1}), 1)

    def test_resolution_source_requires_evidence_or_explicit_self_resolution(self) -> None:
        self.assertEqual(
            srm._question_resolution_source({"terminal_reason": "not_worth_pursuing", "evidence_round_refs": []}, {}),
            ["unresolved"],
        )
        self.assertEqual(
            srm._question_resolution_source({"terminal_reason": "reading_sufficient", "evidence_round_refs": []}, {}),
            ["main_text_self_resolved"],
        )
        self.assertEqual(
            srm._question_resolution_source(
                {"terminal_reason": "reading_sufficient", "evidence_round_refs": [{"refs": ["L01"]}]},
                {},
            ),
            ["liu_resolved"],
        )

    def test_preflight_environment_failure_is_not_a_story_protocol_failure(self) -> None:
        class DeniedTransport:
            def call(self, **_: object) -> dict[str, object]:
                return {
                    "success": False,
                    "failure_class": "sandbox_denied",
                    "attempts": [{"attempt": 1, "failure_class": "sandbox_denied", "http_status": None}],
                    "response": None,
                }

        report = srm._preflight(DeniedTransport())  # type: ignore[arg-type]
        self.assertFalse(report["success"])
        self.assertEqual(report["classification"], "sandbox_denied")
        self.assertNotEqual(report["classification"], "protocol_failure")

    def test_fixture_raw_artifact_is_unchanged_by_projection_replay(self) -> None:
        output = next((ROOT / srm.OUTPUT_ROOT / "fixture" / srm.FIXTURE_VERSION).glob("*/round-00-output.json"))
        before = hashlib.sha256(output.read_bytes()).hexdigest()
        srm.build_postrun_artifacts(ROOT)
        after = hashlib.sha256(output.read_bytes()).hexdigest()
        self.assertEqual(before, after)

    def test_protocol_freeze_uses_current_frozen_helper_hashes(self) -> None:
        freeze = srm.protocol_freeze_document(ROOT)
        self.assertEqual(freeze["algorithm_snapshot"], srm._algorithm_snapshot(ROOT))
        self.assertEqual(freeze["parameters"]["max_evidence_rounds"], srm.MAX_EVIDENCE_ROUNDS)


if __name__ == "__main__":
    unittest.main()
