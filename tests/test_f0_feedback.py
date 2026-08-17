from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.export_user_feedback import build_document
from scripts.feedback_store import FeedbackValidationError, LocalFeedbackRepository, RAW_RELATIVE_PATH
from scripts.validate_feedback import validate


ROOT = Path(__file__).resolve().parents[1]


def draft(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "story_id": "02-yanyu-071",
        "target_type": "story",
        "target_id": "02-yanyu-071",
        "category": "narrative",
        "reason_code": "missing_context",
        "comment": "<script>alert(1)</script>请补充依据",
        "page_url": "https://example.test/shishuoSketch/#story=02-yanyu-071",
        "frontend_version": "dev",
        "data_version": "sc1-schema-1",
        "target_text_snapshot": "谢太傅寒雪日内集",
    }
    value.update(overrides)
    return value


class F0FeedbackTests(unittest.TestCase):
    def test_local_store_sanitizes_and_captures_submission_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = LocalFeedbackRepository(root=root, now=lambda: "2026-08-17T00:00:00Z")
            record = repository.submit(draft())
            self.assertEqual(record["story_id"], "02-yanyu-071")
            self.assertEqual(record["status"], "new")
            self.assertNotIn("<script>", record["comment"])
            self.assertEqual(record["data_version"], "sc1-schema-1")
            self.assertEqual(record["target_text_snapshot"], "谢太傅寒雪日内集")
            raw = (root / RAW_RELATIVE_PATH).read_text(encoding="utf-8")
            self.assertEqual(len(raw.splitlines()), 1)
            self.assertNotIn("email", raw)

    def test_duplicate_protection_and_review_status_transition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = LocalFeedbackRepository(root=root, now=lambda: "2026-08-17T00:00:00Z")
            first = repository.submit(draft())
            second = repository.submit(draft())
            self.assertEqual(second["status"], "duplicate")
            self.assertEqual(second["duplicate_of"], first["feedback_id"])
            updated = repository.update_review(first["feedback_id"], "accepted", "依据充分")
            self.assertEqual(updated["status"], "accepted")
            listed = {record["feedback_id"]: record for record in repository.list_for_target("02-yanyu-071")}
            self.assertEqual(listed[first["feedback_id"]]["status"], "accepted")

    def test_rate_limit_hook_is_boundary_not_canonical_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = LocalFeedbackRepository(root=Path(directory), rate_limit_hook=lambda _payload: False)
            with self.assertRaises(FeedbackValidationError):
                repository.submit(draft())

    def test_target_validation_rejects_orphans(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = LocalFeedbackRepository(root=Path(directory))
            with self.assertRaises(FeedbackValidationError):
                repository.submit(draft(target_type="evidence", target_id=None))

    def test_checked_in_export_and_validator_pass(self) -> None:
        self.assertEqual(validate(ROOT), [])
        first = build_document(ROOT)
        second = build_document(ROOT)
        self.assertEqual(first, second)
        self.assertEqual(first["document_kind"], "user_feedback_reviewed")
        self.assertFalse(first["policy"]["canonical_write_back"])
        self.assertFalse(first["policy"]["gold_write_back"])

    def test_reviewed_export_keeps_only_non_identifying_feedback_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = LocalFeedbackRepository(root=root, now=lambda: "2026-08-17T00:00:00Z")
            record = repository.submit(draft())
            repository.update_review(record["feedback_id"], "accepted", "保留待后续核查")
            document = build_document(root)
            self.assertEqual(len(document["records"]), 1)
            exported = document["records"][0]
            self.assertNotIn("page_url", exported)
            self.assertNotIn("fingerprint", exported)
            self.assertEqual(exported["status"], "accepted")
            self.assertEqual(document, build_document(root))

    def test_frontend_has_page_and_targeted_feedback_contract(self) -> None:
        app = (ROOT / "site/src/App.tsx").read_text(encoding="utf-8")
        feedback = (ROOT / "site/src/Feedback.tsx").read_text(encoding="utf-8")
        self.assertIn("反馈此页", feedback)
        self.assertIn('targetType="evidence"', app)
        self.assertIn('targetType="narrative"', app)
        self.assertIn("FeedbackReviewPanel", app)
        self.assertIn("data_version", (ROOT / "site/src/feedback.ts").read_text(encoding="utf-8"))
        self.assertNotIn("loadSiteBundle", feedback)
        self.assertNotIn("person-resolution", feedback)


if __name__ == "__main__":
    unittest.main()
