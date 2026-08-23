#!/usr/bin/env python3
"""Offline SRM0.4C transport/resume tests; no DeepSeek calls."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_srm0_4c as runner  # noqa: E402
from srm0_4c_transport import DeepSeekTransport, preserved_attempt  # noqa: E402


class _FakeTransport(DeepSeekTransport):
    def __init__(self, outcomes):
        super().__init__(backoff_seconds=0)
        self.outcomes = list(outcomes)

    def _one_request(self, payload):  # noqa: D401
        return self.outcomes.pop(0)


class SRM04CTests(unittest.TestCase):
    def test_transport_retries_one_transient_failure_and_records_both(self):
        client = _FakeTransport([
            (None, "", None, TimeoutError("read timed out")),
            ({"model": "deepseek-v4-flash", "choices": [], "usage": {"total_tokens": 2}}, "{}", 200, None),
        ])
        result = client.call(story_id="s", round_number=1, completion_kind="commentary", messages=[], max_retries=1)
        self.assertTrue(result["success"])
        self.assertEqual([row["attempt"] for row in result["attempts"]], [1, 2])
        self.assertEqual(result["attempts"][0]["failure_class"], "read_timeout")
        self.assertEqual(result["attempts"][1]["http_status"], 200)

    def test_transport_does_not_retry_auth_failure(self):
        error = RuntimeError("DeepSeek API request failed with HTTP 401")
        error.http_status = 401
        client = _FakeTransport([(None, "", 401, error)])
        result = client.call(story_id="s", round_number=0, completion_kind="initial", messages=[], max_retries=1)
        self.assertFalse(result["success"])
        self.assertEqual(len(result["attempts"]), 1)
        self.assertEqual(result["failure_class"], "auth_failure")

    def test_transport_maximum_is_original_plus_one_retry(self):
        error = TimeoutError("read timeout")
        client = _FakeTransport([(None, "", None, error), (None, "", None, error)])
        result = client.call(story_id="s", round_number=0, completion_kind="initial", messages=[], max_retries=1)
        self.assertFalse(result["success"])
        self.assertEqual(len(result["attempts"]), 2)

    def test_http_success_with_invalid_json_is_protocol_not_transport_retry(self):
        from srm0_4c_transport import DeepSeekProtocolError

        client = _FakeTransport([(None, "not-json", 200, DeepSeekProtocolError("invalid"))])
        result = client.call(story_id="s", round_number=0, completion_kind="initial", messages=[], max_retries=1)
        self.assertFalse(result["success"])
        self.assertEqual(len(result["attempts"]), 1)
        self.assertEqual(result["failure_class"], "protocol_failure")

    def test_preserved_attempt_is_not_a_new_request(self):
        row = preserved_attempt(story_id="s", round_number=1, completion_kind="commentary", attempt=1, artifact={"failure_class": "read_timeout", "transport_error": "old"})
        self.assertFalse(row["actual_request"])
        self.assertEqual(row["failure_class"], "read_timeout")

    def test_question_metrics_separate_semantic_and_transport_failures(self):
        questions = {
            "Q1": {"state": "substantially_explained"},
            "Q2": {"state": "conflicted"},
            "Q3": {"state": "unexplained"},
        }
        metrics = runner._question_metrics(questions, ["Q3"], [], [])
        self.assertEqual(metrics["evaluable_question_count"], 2)
        self.assertEqual(metrics["reading_sufficient_question_count"], 1)
        self.assertEqual(metrics["conflicted_question_count"], 1)
        self.assertEqual(metrics["semantic_failed_question_count"], 1)
        transport_metrics = runner._question_metrics(questions, [], [], [{"failure_class": "read_timeout"}])
        self.assertEqual(transport_metrics["evaluable_question_count"], 0)
        self.assertEqual(transport_metrics["semantic_failed_question_count"], 0)

    def test_preflight_failure_aborts_before_story_runs(self):
        args = type("Args", (), {"continue_run": True, "story": None, "replay_existing": False})()
        fake = _FakeTransport([])
        with patch.object(runner, "_preflight", return_value={"classification": "sandbox_denied"}), patch.object(runner, "_run_story") as run_story:
            self.assertEqual(runner.run(args, transport=fake), 2)
        run_story.assert_not_called()

    def test_fixture_and_live_paths_are_disjoint(self):
        self.assertIn("/live/", runner._run_dir("19-xianyuan-010").as_posix())
        self.assertNotIn("fixture", runner._run_dir("19-xianyuan-010").as_posix())

    def test_offline_replay_skips_preflight_and_cannot_call_model(self):
        args = type("Args", (), {"continue_run": True, "story": ["19-xianyuan-010"], "replay_existing": True})()
        with patch.object(runner, "_run_story", return_value={"story_id": "19-xianyuan-010", "story_status": "converged", "evidence_rounds": [], "transport_metrics": {}, "question_metrics": {}, "protocol_errors": [], "transport_errors": []}) as run_story, patch.object(runner, "_preflight") as preflight, patch.object(runner, "_write"):
            self.assertEqual(runner.run(args), 0)
        preflight.assert_not_called()
        run_story.assert_called_once()


if __name__ == "__main__":
    unittest.main()
