from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from scripts.render_shishuo_manual_review import (
    DEFAULT_BOUNDARY_DIR,
    _han_count,
    _high_samples,
    _parse_boundary_manifest,
    _source_body,
    _source_path,
    collect_review_items,
    render_manual_review,
    write_manual_review,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_DIR = REPO_ROOT / DEFAULT_BOUNDARY_DIR
CHAPTER_DIR = REPO_ROOT / "content/processed/shishuo/chapters"
ENTRY_DIR = REPO_ROOT / "content/processed/shishuo/entries/06-yaliang"


class RenderShishuoManualReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest_paths = sorted(BOUNDARY_DIR.glob("*.yaml"))
        cls.source_paths = sorted(CHAPTER_DIR.glob("chapter-*.md"))
        cls.golden_paths = sorted(ENTRY_DIR.glob("*.md"))
        cls.before_hashes = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (*cls.manifest_paths, *cls.source_paths, *cls.golden_paths)
        }
        cls.items = collect_review_items(boundary_dir=BOUNDARY_DIR, root=REPO_ROOT)
        cls.rendered = render_manual_review(boundary_dir=BOUNDARY_DIR, root=REPO_ROOT)

    def test_all_nonhigh_boundaries_and_structural_samples_are_present(self) -> None:
        self.assertEqual(len(self.manifest_paths), 36)
        self.assertEqual(len(self.items), 257)
        self.assertEqual(
            {item.selection_kind for item in self.items},
            {"low", "medium", "high-sample"},
        )
        self.assertEqual(
            sum(item.selection_kind == "low" for item in self.items), 4
        )
        self.assertEqual(
            sum(item.selection_kind == "medium" for item in self.items), 238
        )
        self.assertEqual(
            sum(item.selection_kind == "high-sample" for item in self.items), 15
        )

        expected_nonhigh: set[str] = set()
        expected_samples: set[str] = set()
        for manifest_path in self.manifest_paths:
            top, boundaries, _statuses = _parse_boundary_manifest(manifest_path)
            source = _source_body(
                _source_path(REPO_ROOT, str(top["source_chapter"]))
            )
            for boundary in boundaries:
                if boundary.confidence in {"low", "medium"}:
                    expected_nonhigh.add(boundary.entry_id)
            chapter_number = int(str(top["chapter_id"]).split("-", 1)[0])
            if chapter_number in {5, 8, 18, 19, 25}:
                expected_samples.update(
                    boundary.entry_id
                    for boundary in _high_samples(boundaries, body=source)
                )

        actual_nonhigh = {
            item.entry_id
            for item in self.items
            if item.selection_kind in {"low", "medium"}
        }
        actual_samples = {
            item.entry_id
            for item in self.items
            if item.selection_kind == "high-sample"
        }
        self.assertEqual(actual_nonhigh, expected_nonhigh)
        self.assertEqual(actual_samples, expected_samples)
        self.assertEqual(
            [item.entry_id for item in self.items[:2]],
            ["08-shangyu-086", "18-qiyi-012"],
        )

    def test_contexts_are_exact_source_slices_and_status_is_preserved(self) -> None:
        for item in self.items:
            source_path = _source_path(REPO_ROOT, item.source_chapter)
            body = _source_body(source_path)
            offset = body.find(item.opening_text)
            self.assertEqual(body.count(item.opening_text), 1, item.entry_id)
            self.assertGreaterEqual(offset, 0)
            self.assertTrue(body[:offset].endswith(item.context_before))
            self.assertTrue(body[offset:].startswith(item.context_after))
            self.assertEqual(_han_count(item.context_before), item.before_han_count)
            self.assertEqual(_han_count(item.context_after), item.after_han_count)
            self.assertIn(item.review_status, {"auto", "repaired"})
            self.assertTrue(item.reason)

    def test_review_order_and_context_limitations_are_explicit(self) -> None:
        low_position = self.rendered.index("## LOW confidence")
        medium_position = self.rendered.index("## MEDIUM confidence")
        high_position = self.rendered.index("## HIGH-confidence structural samples")
        self.assertLess(low_position, medium_position)
        self.assertLess(medium_position, high_position)
        self.assertIn("Total review items: 257.", self.rendered)
        self.assertIn("context availability:", self.rendered)
        self.assertIn("19-xianyuan-006", self.rendered)
        self.assertIn("25-paidiao-019", self.rendered)

    def test_regeneration_does_not_modify_manifests_sources_or_golden_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "manual-review.md"
            items = write_manual_review(
                boundary_dir=BOUNDARY_DIR,
                output_path=output,
                root=REPO_ROOT,
            )
            self.assertEqual(len(items), 257)
            self.assertEqual(output.read_text(encoding="utf-8"), self.rendered)

        after_hashes = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.before_hashes
        }
        self.assertEqual(after_hashes, self.before_hashes)


if __name__ == "__main__":
    unittest.main()
