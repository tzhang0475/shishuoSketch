from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_sfh2_a1 import validate  # noqa: E402


class SFH22A1Tests(unittest.TestCase):
    def test_host_preflight_is_successful_and_one_shot(self):
        document = json.loads((ROOT / "data/generated/sfh2-a1/host-preflight.json").read_text(encoding="utf-8"))
        record = document["record"]
        self.assertTrue(record["live_provider_available"])
        self.assertEqual(1, record["attempts"])
        self.assertEqual("deepseek-v4-flash", record["model"])
        self.assertEqual(0, record["temperature"])
        self.assertEqual({"type": "disabled"}, record["thinking"])

    def test_challenge_review_queue_is_pending_and_gold_free(self):
        document = json.loads((ROOT / "data/annotation/sfh2-a1-challenge-external-review.json").read_text(encoding="utf-8"))
        self.assertEqual("pending_external_review", document["status"])
        self.assertEqual(20, len(document["cases"]))
        self.assertTrue(all(row["status"] == "pending_external_review" for row in document["cases"]))
        encoded = json.dumps(document, ensure_ascii=False)
        self.assertNotIn("expected_identity", encoded)
        self.assertNotIn("expected_canonical_hint", encoded)

    def test_provider_accounting_keeps_bounded_failed_review_attempts(self):
        document = json.loads((ROOT / "data/generated/sfh2-a1/provider-accounting.json").read_text(encoding="utf-8"))
        self.assertTrue(document["budget_respected"])
        self.assertEqual(80, document["total_authoritative_attempts"])
        self.assertEqual(40, document["total_successful_parsed_calls"])
        self.assertEqual(40, document["total_provider_failures"])
        self.assertEqual(20, document["total_retries"])

    def test_a1_validator_passes_without_semantic_gold(self):
        result = validate()
        self.assertTrue(result["valid"], result)
        self.assertTrue(result["candidate_only"])
        self.assertFalse(result["canonical_write_back"])


if __name__ == "__main__":
    unittest.main()
