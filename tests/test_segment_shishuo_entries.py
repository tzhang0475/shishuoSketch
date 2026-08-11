from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from scripts.segment_shishuo_entries import (
    DEFAULT_CHAPTER,
    DEFAULT_MANIFEST,
    segment_entries,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CHAPTER_PATH = REPO_ROOT / DEFAULT_CHAPTER
MANIFEST_PATH = REPO_ROOT / DEFAULT_MANIFEST


class SegmentShishuoEntryTests(unittest.TestCase):
    def test_reviewed_manifest_has_42_boundaries_and_conserves_source(self) -> None:
        before = hashlib.sha256(CHAPTER_PATH.read_bytes()).digest()

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "06-yaliang"
            result = segment_entries(MANIFEST_PATH, CHAPTER_PATH, output_dir)

            self.assertEqual(len(result.entries), 42)
            self.assertEqual(
                [entry.boundary.ordinal for entry in result.entries],
                list(range(1, 43)),
            )
            self.assertEqual(
                result.prefix + "".join(entry.source_text for entry in result.entries) + result.suffix,
                result.chapter_body,
            )
            self.assertEqual(result.source_body_sha256, result.reconstructed_body_sha256)
            self.assertEqual(result.chapter_body.count("("), result.chapter_body.count(")"))
            self.assertEqual(result.page_marker_count, 23)
            self.assertEqual(
                sum(len(entry.page_markers) for entry in result.entries),
                result.page_marker_count,
            )
            self.assertEqual(result.annotation_count, 141)
            self.assertEqual(len(list(output_dir.glob("entry-*.md"))), 42)
            report = (output_dir / "validation-report.md").read_text(encoding="utf-8")
            self.assertIn("text_conservation: passed", report)
            self.assertIn("parentheses_balanced: passed", report)
            self.assertIn("page_markers_traceable: passed", report)
            self.assertIn("manifest_boundaries: passed", report)

            prefix = (output_dir / "unsegmented-prefix.md").read_text(encoding="utf-8")
            suffix = (output_dir / "unsegmented-suffix.md").read_text(encoding="utf-8")
            self.assertEqual(prefix, result.prefix)
            self.assertEqual(suffix, result.suffix)

        self.assertEqual(before, hashlib.sha256(CHAPTER_PATH.read_bytes()).digest())

    def test_dongchuang_entry_is_one_manifest_span(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = segment_entries(
                MANIFEST_PATH,
                CHAPTER_PATH,
                Path(temporary) / "06-yaliang",
            )

        entry = result.entries[18]
        self.assertEqual(entry.boundary.entry_id, "06-yaliang-019")
        self.assertEqual(entry.boundary.opening_text, "郗太傅在京口遣門生與王丞相書求女壻")
        self.assertIn("郗太傅在京口遣門生與王丞相書求女壻", entry.source_text)
        self.assertIn("唯有一郎在東牀上\n坦腹卧如不聞", entry.source_text)
        self.assertEqual(len(entry.annotations), 1)
        self.assertNotIn("過江初拜官輿飾供饌", entry.source_text)
        self.assertEqual(result.entries[19].boundary.entry_id, "06-yaliang-020")
        self.assertTrue(result.entries[19].source_text.startswith("過江初拜官輿飾供饌"))


if __name__ == "__main__":
    unittest.main()
