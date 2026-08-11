from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.propose_shishuo_boundaries import (
    CHAPTER_SLUGS,
    DEFAULT_CHAPTER_DIR,
    DEFAULT_REFERENCE,
    _validate,
    _convert_reference,
    generate_proposals,
    load_source_chapter,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CHAPTER_DIR = REPO_ROOT / DEFAULT_CHAPTER_DIR
REFERENCE = REPO_ROOT / DEFAULT_REFERENCE
GOLDEN_CHAPTER = CHAPTER_DIR / "chapter-06.md"
GOLDEN_MANIFEST = REPO_ROOT / "content/curated/shishuo/boundaries/06-yaliang.yaml"
GOLDEN_ENTRIES = REPO_ROOT / "content/processed/shishuo/entries/06-yaliang"

EXPECTED_COUNTS = {
    1: 47,
    2: 108,
    3: 26,
    4: 104,
    5: 65,
    7: 28,
    8: 154,
    9: 88,
    10: 27,
    11: 7,
    12: 7,
    13: 13,
    14: 39,
    15: 2,
    16: 6,
    17: 19,
    18: 15,
    19: 31,
    20: 11,
    21: 14,
    22: 6,
    23: 54,
    24: 17,
    25: 65,
    26: 33,
    27: 14,
    28: 9,
    29: 9,
    30: 12,
    31: 8,
    32: 4,
    33: 17,
    34: 8,
    35: 7,
    36: 8,
}


class ProposeShishuoBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.chapter_hashes = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(CHAPTER_DIR.glob("chapter-*.md"))
        }
        cls.golden_paths = [GOLDEN_CHAPTER, GOLDEN_MANIFEST, *sorted(GOLDEN_ENTRIES.glob("*.md"))]
        cls.golden_hashes = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in cls.golden_paths
        }
        cls.temporary = tempfile.TemporaryDirectory()
        cls.output_dir = Path(cls.temporary.name) / "boundaries"
        cls.report_path = cls.output_dir / "boundary-review-report.md"
        cls.proposals = generate_proposals(
            chapter_dir=CHAPTER_DIR,
            reference_path=REFERENCE,
            output_dir=cls.output_dir,
            report_path=cls.report_path,
        )
        cls.by_number = {
            proposal.chapter.chapter_number: proposal for proposal in cls.proposals
        }

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_generates_only_the_remaining_35_manifests(self) -> None:
        self.assertEqual(len(self.proposals), 35)
        self.assertNotIn(6, self.by_number)
        self.assertEqual(
            {path.name for path in self.output_dir.glob("*.yaml")},
            {
                f"{number:02d}-{CHAPTER_SLUGS[number - 1]}.yaml"
                for number in EXPECTED_COUNTS
            },
        )
        self.assertFalse((self.output_dir / "06-yaliang.yaml").exists())
        self.assertFalse((self.output_dir / "entries").exists())

    def test_counts_validation_and_manifest_anchors(self) -> None:
        for number, expected_count in EXPECTED_COUNTS.items():
            proposal = self.by_number[number]
            self.assertEqual(len(proposal.boundaries), expected_count, number)
            self.assertTrue(proposal.validation.passed, number)
            chapter = load_source_chapter(CHAPTER_DIR / f"chapter-{number:02d}.md")

            self.assertEqual(
                [boundary.ordinal for boundary in proposal.boundaries],
                list(range(1, expected_count + 1)),
            )
            for boundary in proposal.boundaries:
                self.assertEqual(
                    boundary.entry_id,
                    f"{proposal.chapter_id}-{boundary.ordinal:03d}",
                )
                self.assertEqual(chapter.body.count(boundary.opening_text), 1)
                self.assertEqual(
                    chapter.body.find(boundary.opening_text), boundary.body_offset
                )
                self.assertNotIn("<pb:", boundary.opening_text)
                self.assertNotIn("<!--", boundary.opening_text)
                self.assertIn(boundary.confidence, {"high", "medium", "low"})
                if boundary.confidence != "high":
                    self.assertTrue(boundary.note)
                self.assertGreater(boundary.source_normalized_line, 0)
                self.assertGreater(boundary.source_line, 0)
                self.assertTrue(boundary.source_page_marker)

            manifest = (
                self.output_dir
                / f"{number:02d}-{CHAPTER_SLUGS[number - 1]}.yaml"
            ).read_text(encoding="utf-8")
            self.assertEqual(
                manifest.count('review_status: "auto"'), expected_count + 1
            )

    def test_reference_exceptions_and_continuation_are_explicit(self) -> None:
        self.assertEqual(self.by_number[8].reference_count, 156)
        self.assertEqual(
            [item.reference_ordinal for item in self.by_number[5].guide_exceptions],
            [14],
        )
        self.assertEqual(
            [item.reference_ordinal for item in self.by_number[8].guide_exceptions],
            [84, 85],
        )
        self.assertEqual(
            [item.reference_ordinal for item in self.by_number[18].guide_exceptions],
            [2, 11],
        )
        self.assertEqual(
            [item.reference_ordinal for item in self.by_number[19].guide_exceptions],
            [5],
        )
        low = [
            boundary
            for boundary in self.by_number[19].boundaries
            if boundary.confidence == "low"
        ]
        self.assertEqual(len(low), 1)
        self.assertIn("婦", low[0].opening_text)
        self.assertIn("surviving source text", low[0].note)

    def test_report_lists_every_review_boundary_and_overall_totals(self) -> None:
        report = self.report_path.read_text(encoding="utf-8")
        self.assertIn("Overall proposed boundaries: 1082; high: 840; medium: 240; low: 2.", report)
        self.assertIn("## Duplicate or non-unique anchors", report)
        self.assertIn("## Structurally unusual chapters", report)
        self.assertIn("05-fangzheng", report)
        self.assertIn("08-shangyu", report)
        self.assertIn("18-qiyi", report)
        self.assertIn("19-xianyuan", report)
        for proposal in self.proposals:
            for boundary in proposal.boundaries:
                if boundary.confidence in {"medium", "low"}:
                    heading = f"#### {boundary.entry_id} ({boundary.confidence})"
                    self.assertIn(heading, report)
                    section = report[report.index(heading) :]
                    self.assertIn("- context:", section)

    def test_duplicate_manifest_anchors_fail_validation(self) -> None:
        proposal = self.by_number[1]
        chapter = proposal.chapter
        first, second = proposal.boundaries[:2]
        duplicate = replace(
            first,
            opening_text=second.opening_text,
            body_offset=first.body_offset,
        )
        validation = _validate(chapter, (duplicate, second))
        self.assertFalse(validation.passed)
        self.assertTrue(validation.duplicate_anchors)

    def test_missing_conversion_tool_cannot_change_proposals_silently(self) -> None:
        with patch("scripts.propose_shishuo_boundaries.shutil.which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "uconv is required"):
                _convert_reference("简体")

    def test_generation_does_not_modify_sources_or_golden_entry_segmentation(self) -> None:
        self.assertEqual(
            {
                path: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in self.chapter_hashes
            },
            self.chapter_hashes,
        )
        self.assertEqual(
            {
                path: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in self.golden_hashes
            },
            self.golden_hashes,
        )


if __name__ == "__main__":
    unittest.main()
