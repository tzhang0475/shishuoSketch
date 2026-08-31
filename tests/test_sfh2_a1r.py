from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_a0r.contracts import (  # noqa: E402
    adjudication_tool,
    critical_review_tool,
    validate_adjudication_payload,
    validate_critical_review_payload,
    validate_deepseek_strict_schema,
    semantic_record_tool,
)
from sfh2_a1r import transport  # noqa: E402
from sfh2_a1r.common import MODEL  # noqa: E402


def _packet() -> dict:
    return {"source_evidence": [{"evidence_id": "ev-1", "text": "甲"}]}


class SFH22A1RTests(unittest.TestCase):
    def test_every_provider_strict_object_is_closed_and_exactly_required(self):
        for tool in (semantic_record_tool(), critical_review_tool(), adjudication_tool()):
            self.assertEqual([], validate_deepseek_strict_schema(tool["function"]["parameters"]))
        for tool in (critical_review_tool(), adjudication_tool()):
            self.assertNotIn("reviewed_fields", tool["function"]["parameters"]["properties"])
            self.assertNotIn("patch", tool["function"]["parameters"]["properties"])

    def test_typed_patch_operations_validate_and_reviewed_fields_are_derived(self):
        result = validate_critical_review_payload(_packet(), {"decision": "revise", "patch_ops": [{"path": "occurrence_role", "value": "speaker_reference"}], "reason_summary": "r", "supporting_evidence_ids": ["ev-1"]})
        self.assertTrue(result["valid"])
        self.assertEqual(["occurrence_role"], result["review"]["reviewed_fields"])
        self.assertEqual("speaker_reference", result["review"]["patch_ops"][0]["value"])

    def test_confirm_and_selection_use_empty_patch_operations(self):
        review = validate_critical_review_payload(_packet(), {"decision": "confirm", "patch_ops": [], "reason_summary": "ok", "supporting_evidence_ids": []})
        adjudication = validate_adjudication_payload(_packet(), {"decision": "select_pass1", "base_record": "", "patch_ops": [], "reason_summary": "ok", "supporting_evidence_ids": []})
        self.assertTrue(review["valid"])
        self.assertTrue(adjudication["valid"])
        self.assertEqual([], review["review"]["reviewed_fields"])
        self.assertEqual([], adjudication["adjudication"]["patch_ops"])

    def test_old_partial_patch_shape_is_not_a_provider_contract(self):
        old = {"decision": "confirm", "reviewed_fields": [], "patch": {}, "reason_summary": "", "supporting_evidence_ids": []}
        self.assertFalse(validate_critical_review_payload(_packet(), old)["valid"])

    def test_http_400_is_not_retried_and_body_is_bounded(self):
        error = RuntimeError("DeepSeek API request failed with HTTP 400")
        error.http_status = 400  # type: ignore[attr-defined]
        error.provider_error_body = json.dumps({"error": {"code": "invalid_request", "message": "schema rejected", "secret": "do-not-copy"}})  # type: ignore[attr-defined]
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            client = transport.ReviewClient(Path(directory), live=True)
            with patch("smoke_deepseek.call_deepseek", side_effect=error):
                result = client.call(stage="critical_reviewer", unit_id="u", system="s", payload={}, tool=critical_review_tool(), max_tokens=10)
            self.assertIsNone(result)
            self.assertEqual(1, len(client.records))
            self.assertEqual(400, client.records[0]["http_status"])
            self.assertEqual("invalid_request", client.records[0]["provider_error_code"])
            self.assertNotIn("do-not-copy", client.records[0]["provider_error_body"])

    def test_http_500_may_retry_once(self):
        error = RuntimeError("server error")
        error.http_status = 500  # type: ignore[attr-defined]
        error.provider_error_body = "{}"  # type: ignore[attr-defined]
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            client = transport.ReviewClient(Path(directory), live=True)
            with patch("smoke_deepseek.call_deepseek", side_effect=error):
                client.call(stage="critical_reviewer", unit_id="u", system="s", payload={}, tool=critical_review_tool(), max_tokens=10)
            self.assertEqual(2, len(client.records))
            self.assertEqual(1, client.records[0]["attempt"])
            self.assertEqual(2, client.records[1]["attempt"])

    def test_http_429_may_retry_once(self):
        error = RuntimeError("rate limited")
        error.http_status = 429  # type: ignore[attr-defined]
        error.provider_error_body = "{}"  # type: ignore[attr-defined]
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            client = transport.ReviewClient(Path(directory), live=True)
            with patch("smoke_deepseek.call_deepseek", side_effect=error):
                client.call(stage="critical_reviewer", unit_id="rate", system="s", payload={}, tool=critical_review_tool(), max_tokens=10)
            self.assertEqual(2, len(client.records))

    def test_model_is_fixed(self):
        self.assertEqual("deepseek-v4-flash", MODEL)


if __name__ == "__main__":
    unittest.main()
