from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import unittest

import yaml

from scripts import review_shishuo_structural as review
from tests.support import skip_if_portable_payload_missing


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = REPO_ROOT / "content/curated/shishuo/collation/structural-review.yaml"
MARKDOWN_PATH = REPO_ROOT / "content/curated/shishuo/collation/structural-review.md"


def _tree_digest(*roots: Path) -> str:
    digest = sha256()
    for root in roots:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            digest.update(str(path.relative_to(REPO_ROOT)).encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


class ShishuoStructuralReviewTests(unittest.TestCase):
    def test_generated_review_has_exact_scope_and_allowed_classes(self) -> None:
        document = yaml.safe_load(REPORT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(document["scope"]["source_record_count"], 90)
        self.assertEqual(document["summary"]["record_count"], 90)
        self.assertEqual(len(document["records"]), 90)
        self.assertEqual(
            set(document["summary"]) & set(review.CLASSIFICATIONS),
            set(review.CLASSIFICATIONS),
        )
        for record in document["records"]:
            self.assertIn(record["classification"], review.CLASSIFICATIONS)
        self.assertEqual(
            sum(document["summary"][name] for name in review.CLASSIFICATIONS),
            90,
        )

    def test_structural_summary_and_known_gap_provenance(self) -> None:
        document = yaml.safe_load(REPORT_PATH.read_text(encoding="utf-8"))
        summary = document["summary"]
        self.assertEqual(summary["true_boundary_error"], 0)
        self.assertEqual(summary["extra_boundary"], 0)
        self.assertEqual(summary["unresolved"], 0)
        self.assertEqual(summary["current_canonical_entry_count"], 1130)
        self.assertTrue(summary["current_canonical_entry_count_supported"])
        self.assertEqual(summary["current_canonical_gap_entry_count"], 6)
        missing = [
            record
            for record in document["records"]
            if record["classification"] == "missing_entry"
        ]
        self.assertEqual(len(missing), 5)
        affected = {
            boundary["entry_id"]
            for record in missing
            for boundary in record["canonical_boundary"].get("affected_boundaries", [])
        }
        self.assertEqual(
            affected,
            {
                "05-fangzheng-014",
                "08-shangyu-084",
                "08-shangyu-085",
                "18-qiyi-002",
                "18-qiyi-011",
                "19-xianyuan-005",
            },
        )
        for record in document["records"]:
            self.assertEqual(record["fallback_witnesses_used"], [])

    def test_report_rendering_and_review_are_deterministic(self) -> None:
        skip_if_portable_payload_missing(
            self,
            REPO_ROOT,
            "sources/downloads/shishuo/wikisource-sbck/pages",
        )
        before = _tree_digest(
            REPO_ROOT / "content/processed/shishuo/chapters",
            REPO_ROOT / "content/processed/shishuo/entries",
            REPO_ROOT / "content/curated/shishuo/boundaries",
        )
        first = review.build_review()
        second = review.build_review()
        after = _tree_digest(
            REPO_ROOT / "content/processed/shishuo/chapters",
            REPO_ROOT / "content/processed/shishuo/entries",
            REPO_ROOT / "content/curated/shishuo/boundaries",
        )
        self.assertEqual(before, after)
        self.assertEqual(first, second)
        self.assertTrue(MARKDOWN_PATH.exists())
        markdown = MARKDOWN_PATH.read_text(encoding="utf-8")
        self.assertIn("90 records", markdown)
        self.assertIn("1130", markdown)
        self.assertIn("discrepancy-249", markdown)


if __name__ == "__main__":
    unittest.main()
