from __future__ import annotations

import hashlib
from pathlib import Path
import unittest
import yaml

from scripts.audit_shishuo_boundaries import audit_workspace, render_report


REPO_ROOT = Path(__file__).resolve().parents[1]


class ShishuoBoundaryAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        tracked_inputs = [
            *sorted(
                (REPO_ROOT / "content/processed/shishuo/chapters").glob(
                    "chapter-*.md"
                )
            ),
            *sorted(
                (REPO_ROOT / "content/curated/shishuo/boundaries").glob("*.yaml")
            ),
            REPO_ROOT / "content/curated/shishuo/boundaries/boundary-review-report.md",
            REPO_ROOT / "content/curated/shishuo/boundaries/manual-review.md",
        ]
        cls.input_hashes = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in tracked_inputs
            if path.exists()
        }
        cls.audit = audit_workspace(REPO_ROOT)

    def test_guide_and_manifest_completeness_are_computed(self) -> None:
        self.assertEqual(len(self.audit.chapters), 36)
        self.assertEqual(self.audit.guide_non_yaliang, 1088)
        self.assertEqual(self.audit.guide_yaliang, 42)
        self.assertEqual(self.audit.guide_total, 1130)
        self.assertEqual(self.audit.manifest_total, 1130)

    def test_confirmed_boundary_shift_findings(self) -> None:
        qiyi = yaml.safe_load(
            (REPO_ROOT / "content/curated/shishuo/boundaries/18-qiyi.yaml").read_text(
                encoding="utf-8"
            )
        )
        qiyi_entries = {item["ordinal"]: item for item in qiyi["entries"]}
        self.assertEqual(qiyi_entries[10]["opening_text"], "孟萬年及弟少孤居武昌陽新")
        self.assertNotIn(
            "病篤狼狽至都時賢見之者莫",
            [item["opening_text"] for item in qiyi["entries"]],
        )
        self.assertEqual(
            qiyi_entries[17]["opening_text"], "郄尚書與謝居士善常稱謝慶緒"
        )

        paidiao = yaml.safe_load(
            (REPO_ROOT / "content/curated/shishuo/boundaries/25-paidiao.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            paidiao["entries"][18]["opening_text"], "于寳向劉真長"
        )

    def test_structural_gaps_and_page_marker_findings(self) -> None:
        by_number = {audit.number: audit for audit in self.audit.chapters}
        expected = {5: (14,), 8: (84, 85), 18: (2, 11), 19: (5,)}
        for number, ordinals in expected.items():
            audit = by_number[number]
            self.assertEqual(
                tuple(gap.exception.reference_ordinal for gap in audit.guide_gaps),
                ordinals,
            )
            for gap in audit.guide_gaps:
                self.assertTrue(gap.second_witness_required)
                self.assertTrue(gap.preceding_text)
                self.assertTrue(gap.following_text)

        self.assertTrue(
            any("002-8b" in finding for finding in by_number[5].guide_gaps[0].marker_findings)
        )
        self.assertTrue(
            any("duplicated marker" in finding for finding in by_number[8].guide_gaps[0].marker_findings)
        )
        self.assertTrue(
            any("002-14b" in finding for finding in by_number[18].guide_gaps[0].marker_findings)
        )
        self.assertTrue(
            any("duplicated marker" in finding for finding in by_number[18].guide_gaps[1].marker_findings)
        )
        self.assertTrue(
            any("002-20b" in finding for finding in by_number[19].guide_gaps[0].marker_findings)
        )

    def test_all_mechanical_validations_pass_but_report_keeps_semantic_caveat(self) -> None:
        self.assertTrue(all(audit.mechanical.passed for audit in self.audit.chapters))
        report = render_report(self.audit)
        self.assertIn("Mechanical validation does **not** prove semantic boundary correctness.", report)
        self.assertIn("18-qiyi-010", report)
        self.assertIn("25-paidiao-019", report)

    def test_audit_does_not_modify_manifests_or_chapter_sources(self) -> None:
        after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.input_hashes
        }
        self.assertEqual(after, self.input_hashes)


if __name__ == "__main__":
    unittest.main()
