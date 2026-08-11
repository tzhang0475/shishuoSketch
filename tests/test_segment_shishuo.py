from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from scripts.segment_shishuo import CANONICAL_CHAPTERS, segment_collection


REPO_ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_ROOT = REPO_ROOT / "content" / "processed" / "shishuo"


class SegmentShishuoTests(unittest.TestCase):
    def test_exactly_36_canonical_chapters_and_no_normalized_writes(self) -> None:
        source_files = sorted(NORMALIZED_ROOT.glob("*.md"))
        before = {path: hashlib.sha256(path.read_bytes()).digest() for path in source_files}

        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary)
            result = segment_collection(NORMALIZED_ROOT, output_root)

            self.assertEqual(len(CANONICAL_CHAPTERS), 36)
            self.assertEqual(len(result.chapters), 36)
            self.assertEqual(result.missing, [])
            self.assertEqual(result.duplicates, [])
            self.assertEqual(len(result.chapter_paths), 36)
            self.assertEqual(
                len(list((output_root / "chapters").glob("chapter-*.md"))),
                36,
            )
            self.assertEqual(
                {path.name for path in result.editorial_paths},
                {"preface.md", "catalogue.md", "collation-notes.md"},
            )
            self.assertTrue(result.report_path.exists())
            report = result.report_path.read_text(encoding="utf-8")
            self.assertIn("textual_heading_occurrence_count: 37", report)
            self.assertIn("missing_chapters: []", report)
            self.assertIn("duplicate_chapters: []", report)
            for number in CANONICAL_CHAPTERS:
                self.assertIn(f"| {number} |", report)

            chapter_eight = result.chapters[7]
            self.assertEqual(chapter_eight.number, 8)
            self.assertEqual(
                chapter_eight.observed_headings,
                ["賞譽第八(上)", "賞譽第八(下)"],
            )
            self.assertEqual(len(chapter_eight.parts), 2)
            chapter_eight_text = (output_root / "chapters" / "chapter-08.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("賞譽第八(上)", chapter_eight_text)
            self.assertIn("賞譽第八(下)", chapter_eight_text)
            self.assertIn("source_line: 958", chapter_eight_text)
            self.assertIn("<pb:KR3l0002_SBCK_002-46a>", chapter_eight_text)
            self.assertIn("FILE: \"SB03n0058-003世説新語-卷中之下.\"", chapter_eight_text)
            self.assertFalse((output_root / "entries").exists())

        after = {path: hashlib.sha256(path.read_bytes()).digest() for path in source_files}
        self.assertEqual(before, after)

    def test_editorial_sections_are_not_used_as_chapters(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = segment_collection(NORMALIZED_ROOT, Path(temporary))

        kinds = {section.kind for section in result.sections}
        self.assertEqual(kinds, {"preface", "catalogue", "collation_notes", "main_text"})
        self.assertEqual(len(result.sections), 9)
        self.assertEqual(
            [section.file_value for section in result.sections],
            [
                "SB03n0058-000世説新語-序.",
                "SB03n0058-000世説新語-目録.",
                "SB03n0059-001世説新語校語-一卷.",
                "SB03n0058-001世説新語-卷上之上.",
                "SB03n0058-001世説新語-卷上之下.",
                "SB03n0058-003世説新語-卷中之上.",
                "SB03n0058-002世説新語-卷下之上.",
                "SB03n0058-002世説新語-卷下之下.",
                "SB03n0058-003世説新語-卷中之下.",
            ],
        )
        self.assertEqual(
            result.chapters[0].observed_headings,
            ["德行第一"],
        )
        self.assertEqual(result.chapters[-1].observed_headings, ["仇隟第三十六"])


if __name__ == "__main__":
    unittest.main()
