from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import lookup_shishuo_reference as lookup


REPO_ROOT = Path(__file__).resolve().parents[1]


class ShishuoReferenceLookupTests(unittest.TestCase):
    def test_local_entry_context_uses_exact_entry_source(self) -> None:
        context = lookup.load_local_context("謝太傅", "06-yaliang-019")
        self.assertEqual(context.status, "entry_loaded")
        self.assertIn("entry_id: 06-yaliang-019", context.text)
        self.assertIn("郗太傅在京口遣門生與王丞相書求女壻", context.text)
        self.assertIn("唯有一郎在東牀上", context.text)

    def test_codex_command_and_markdown_sections_are_explicit(self) -> None:
        output = """## person_entity_resolution
謝太傅：待核对的候选人物。
## scholarly_reference
余嘉錫箋疏检索结果，需以来源页面复核。
## official_history
晉書相关记载，见所列链接。
## web_search_inference
这是搜索证据基础上的谨慎推断。
## source_urls
- https://example.org/history
## confidence
medium
## unresolved_ambiguity
名字与官称仍需核验。
"""
        calls: list[list[str]] = []

        def runner(command: list[str], **_kwargs):
            calls.append(command)
            return type("Completed", (), {"returncode": 0, "stdout": output, "stderr": ""})()

        with patch.object(lookup.shutil, "which", return_value="/usr/bin/codex"):
            result = lookup.run_codex_search("prompt", runner=runner)
        self.assertEqual(result.status, "ok")
        self.assertEqual(calls[0][:6], list(lookup.CODEX_COMMAND))
        self.assertIn("--search", calls[0])
        self.assertIn("--ephemeral", calls[0])
        self.assertIn("--sandbox", calls[0])
        self.assertIn("read-only", calls[0])

        with tempfile.TemporaryDirectory() as temporary:
            local = lookup.load_local_context("謝太傅", "06-yaliang-019")
            report = lookup.render_report(
                "謝太傅",
                "06-yaliang-019",
                local,
                result,
                cache_file=Path(temporary) / ".cache/shishuo-reference/report.md",
            )
            self.assertIn("## local_source", report)
            self.assertIn("## scholarly_reference", report)
            self.assertIn("## official_history", report)
            self.assertIn("## web_search_inference", report)
            self.assertIn("## unresolved_ambiguity", report)
            self.assertIn("https://example.org/history", report)
            self.assertIn("local_corpus_modified: false", report)

    def test_cache_hit_and_no_cache_behavior(self) -> None:
        output = """## person_entity_resolution
No firm resolution.
## scholarly_reference
No result.
## official_history
No result.
## web_search_inference
No inference.
## source_urls
## confidence
low
## unresolved_ambiguity
Unresolved.
"""
        calls = 0

        def runner(_command, **_kwargs):
            nonlocal calls
            calls += 1
            return type("Completed", (), {"returncode": 0, "stdout": output, "stderr": ""})()

        with tempfile.TemporaryDirectory() as temporary, patch.object(
            lookup.shutil, "which", return_value="/usr/bin/codex"
        ):
            root = Path(temporary)
            first, cache_file, from_cache = lookup.lookup(
                "謝太傅", root=root, runner=runner
            )
            self.assertFalse(from_cache)
            self.assertIsNotNone(cache_file)
            self.assertTrue(cache_file.is_file())
            second, second_path, second_from_cache = lookup.lookup(
                "謝太傅", root=root, runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    AssertionError("cache should have been used")
                )
            )
            self.assertTrue(second_from_cache)
            self.assertEqual(first, second)
            self.assertEqual(cache_file, second_path)
            self.assertEqual(calls, 1)

            no_cache, no_cache_path, no_cache_hit = lookup.lookup(
                "謝太傅", root=root, no_cache=True, runner=runner
            )
            self.assertFalse(no_cache_hit)
            self.assertIsNone(no_cache_path)
            self.assertIn("status: \"ok\"", no_cache)
            self.assertEqual(calls, 2)

    def test_failure_is_reported_without_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.object(
            lookup.shutil, "which", return_value=None
        ):
            report, cache_file, from_cache = lookup.lookup(
                "謝太傅", root=Path(temporary)
            )
            self.assertFalse(from_cache)
            self.assertIsNone(cache_file)
            self.assertIn('status: "codex_unavailable"', report)
            self.assertFalse((Path(temporary) / ".cache/shishuo-reference").exists())

    def test_cache_directory_is_git_ignored(self) -> None:
        result = subprocess.run(
            ["git", "check-ignore", "-q", "--", ".cache/shishuo-reference/example.md"],
            cwd=REPO_ROOT,
            check=False,
        )
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
