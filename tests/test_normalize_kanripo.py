from __future__ import annotations

import hashlib
from pathlib import Path
import re
import tempfile
import unittest

from scripts.normalize_kanripo import discover_configured_sources, normalize_file


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"
PAGE_OR_DIRECTIVE_COMMENT_RE = re.compile(r"<!-- .*? -->")
PAGE_MARKER_RE = re.compile(r"<pb:[^>]+>")


def _source_text_without_structure(raw: str) -> str:
    """The source character stream, excluding Kanripo structure lines."""

    chunks: list[str] = []
    for raw_line in raw.splitlines(keepends=True):
        line = raw_line.removesuffix("\n").removesuffix("\r")
        if line.startswith("# -*-") or line.startswith("#+"):
            continue
        line = PAGE_MARKER_RE.sub("", line)
        if line.endswith("¶"):
            line = line[:-1]
        chunks.append(line)
    return "".join(chunks)


def _normalized_body(markdown: str) -> str:
    _, separator, body = markdown.partition("\n---\n\n")
    if not separator:
        raise AssertionError("normalized output has no YAML front matter terminator")
    body_without_comments = PAGE_OR_DIRECTIVE_COMMENT_RE.sub("", body)
    return "".join(body_without_comments.splitlines())


class NormalizeKanripoTests(unittest.TestCase):
    def test_configured_source_discovery_matches_existing_primary_trees(self) -> None:
        config = REPO_ROOT / "config" / "sources.yaml"
        configured = discover_configured_sources(config)
        # The configured Kanripo TXT collections still cover Shishuo.  Jinshu
        # now resolves to the Wikisource tree, whose source TXT files live
        # below its ``text/`` directory and are handled by its dedicated
        # normalizer.
        self.assertEqual(len(configured), 4)
        self.assertEqual(
            {path.parent.name for path in configured},
            {"shishuo"},
        )
        self.assertEqual(configured, sorted(configured, key=lambda path: path.as_posix()))

    def test_shishuo_preserves_text_pages_and_repeated_properties(self) -> None:
        source = FIXTURES / "shishuo_sample.txt"
        raw_bytes = source.read_bytes()
        raw = raw_bytes.decode("utf-8")

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "shishuo.md"
            normalize_file(source, output)
            normalized = output.read_text(encoding="utf-8")

        self.assertIn("source_path: \"tests/fixtures/shishuo_sample.txt\"", normalized)
        self.assertIn(
            f'source_sha256: "{hashlib.sha256(raw_bytes).hexdigest()}"',
            normalized,
        )
        self.assertIn(
            "<!-- kanripo-page source-line=9: "
            "<pb:KR3l0002_SBCK_001-1a> -->",
            normalized,
        )
        self.assertIn(
            "<!-- kanripo-page source-line=15: "
            "<pb:KR3l0002_SBCK_001-1b> -->",
            normalized,
        )
        self.assertIn(
            "<!-- kanripo-page source-line=15: "
            "<pb:KR3l0002_SBCK_001-1b-copy> -->",
            normalized,
        )
        self.assertIn('kanripo_juans:\n  - "1"\n  - "1"', normalized)
        self.assertIn("<!-- kanripo-directive source-line=13: #+PROPERTY: JUAN 1 -->", normalized)
        self.assertIn("&KR0680;", normalized)
        self.assertNotIn("¶", normalized)
        self.assertEqual(_normalized_body(normalized), _source_text_without_structure(raw))

    def test_jinshu_retains_juan_boundaries_without_extraction(self) -> None:
        source = FIXTURES / "jinshu_sample.txt"

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "jinshu.md"
            normalize_file(source, output)
            normalized = output.read_text(encoding="utf-8")

        self.assertIn('kanripo_title: "晉書"', normalized)
        self.assertIn('kanripo_juans:\n  - "卷一"\n  - "卷二"', normalized)
        self.assertIn("　晉書卷一", normalized)
        self.assertIn("　晉書卷二考證", normalized)
        self.assertIn("&KR2192;", normalized)
        self.assertIn(
            "<!-- kanripo-page source-line=12: "
            "<pb:KR2a0015_WYG_1a> -->",
            normalized,
        )
        self.assertIn(
            "<!-- kanripo-page source-line=12: "
            "<pb:KR2a0015_WYG_001-2a> -->",
            normalized,
        )
        self.assertNotIn("relationship", normalized.lower())
        self.assertEqual(
            _normalized_body(normalized),
            _source_text_without_structure(source.read_text(encoding="utf-8")),
        )

    def test_output_guard_rejects_immutable_source_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "shishuoSources"
            output_root = source_root / "processed"
            source_root.mkdir()
            source = source_root / "sample.txt"
            source.write_text("sample\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                normalize_file(source, output_root / "sample.md", source_root=source_root)


if __name__ == "__main__":
    unittest.main()
