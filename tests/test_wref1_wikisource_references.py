from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts import download_witnesses as downloader
from scripts.validate_wref1 import validate


class Wref1ReferenceTests(unittest.TestCase):
    def test_title_generation_and_expected_coverage(self) -> None:
        jinshu = downloader.jinshu_wikisource_punctuated_volume_titles()
        self.assertEqual(len(jinshu), 130)
        self.assertEqual(jinshu[1], "晉書/卷001")
        self.assertEqual(jinshu[130], "晉書/卷130")

        ztj = downloader.zizhi_tongjian_wikisource_hu_volume_titles()
        self.assertEqual(len(ztj), 294)
        self.assertEqual(ztj[1], "資治通鑒 (胡三省音注)/卷001")
        self.assertEqual(ztj[294], "資治通鑒 (胡三省音注)/卷294")

    @staticmethod
    def _batch_fetcher(titles):
        revisions = []
        for title in titles:
            number = int(title.rsplit("卷", 1)[1])
            revisions.append(
                downloader.WikisourceRevision(
                    page_title=title,
                    source_url=downloader.wikisource_page_url(title),
                    api_url="https://example.invalid/w/api.php?fixture=1",
                    page_id=10000 + number,
                    revision_id=20000 + number,
                    parent_revision_id=19999 + number,
                    timestamp="2026-01-01T00:00:00Z",
                    content=f"卷{number:03d} 原始標點測試。{{{{header}}}}\n",
                )
            )
        return (
            revisions,
            json.dumps({"titles": list(titles)}, ensure_ascii=False).encode("utf-8"),
            "https://example.invalid/w/api.php?fixture=1",
        )

    def test_reference_manifest_provenance_and_determinism(self) -> None:
        titles = {number: f"測試書/卷{number:03d}" for number in range(1, 4)}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock_path, first = downloader.run_wikisource_reference_witness(
                root,
                witness_id="fixture-reference",
                work="測試書",
                role="punctuated-reference",
                edition="fixture",
                source_record="https://example.invalid/wiki/測試書",
                base_title="測試書",
                root_relative="sources/downloads/test-wref",
                volume_titles=titles,
                batch_size=2,
                text_authority="reference only",
                structure_authority="page title",
                notes=("fixture",),
                batch_fetcher=self._batch_fetcher,
                retrieval_timestamp="2026-01-02T00:00:00+00:00",
            )
            self.assertEqual(first["status"], "complete")
            self.assertEqual(first["missing_juans"], [])
            self.assertEqual(first["duplicate_juans"], [])
            record = first["records"][0]
            for field in (
                "work",
                "witness_id",
                "global_juan",
                "page_title",
                "source_url",
                "api_url",
                "page_id",
                "revision_id",
                "parent_revision_id",
                "revision_timestamp",
                "source_path",
                "source_size",
                "source_sha256",
            ):
                self.assertIn(field, record)
            self.assertEqual(downloader.verify_lock_manifest(root, lock_path), [])
            first_lock = lock_path.read_bytes()
            first_metadata = (lock_path.parent / "metadata.yaml").read_bytes()

            _lock_path, second = downloader.run_wikisource_reference_witness(
                root,
                witness_id="fixture-reference",
                work="測試書",
                role="punctuated-reference",
                edition="fixture",
                source_record="https://example.invalid/wiki/測試書",
                base_title="測試書",
                root_relative="sources/downloads/test-wref",
                volume_titles=titles,
                batch_size=2,
                text_authority="reference only",
                structure_authority="page title",
                notes=("fixture",),
                batch_fetcher=self._batch_fetcher,
                retrieval_timestamp="2099-01-01T00:00:00+00:00",
            )
            self.assertEqual(second["status"], "complete")
            self.assertEqual(first_lock, lock_path.read_bytes())
            self.assertEqual(first_metadata, (lock_path.parent / "metadata.yaml").read_bytes())

    def test_missing_and_duplicate_volume_failures_are_locked(self) -> None:
        titles = {number: f"測試書/卷{number:03d}" for number in range(1, 4)}

        def missing_fetcher(requested):
            revisions, raw, api_url = self._batch_fetcher(requested[:-1])
            return revisions, raw, api_url

        def duplicate_fetcher(requested):
            revisions, raw, api_url = self._batch_fetcher(requested)
            return revisions + [revisions[0]], raw, api_url

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _lock, missing = downloader.run_wikisource_reference_witness(
                root,
                witness_id="missing-reference",
                work="測試書",
                role="reference",
                edition="fixture",
                source_record="https://example.invalid",
                base_title="測試書",
                root_relative="sources/downloads/test-missing",
                volume_titles=titles,
                batch_size=3,
                text_authority="reference",
                structure_authority="page title",
                notes=(),
                batch_fetcher=missing_fetcher,
                retrieval_timestamp="2026-01-02T00:00:00+00:00",
            )
            self.assertEqual(missing["status"], "incomplete")
            self.assertEqual(missing["missing_juans"], [3])

            _lock, duplicate = downloader.run_wikisource_reference_witness(
                root,
                witness_id="duplicate-reference",
                work="測試書",
                role="reference",
                edition="fixture",
                source_record="https://example.invalid",
                base_title="測試書",
                root_relative="sources/downloads/test-duplicate",
                volume_titles=titles,
                batch_size=3,
                text_authority="reference",
                structure_authority="page title",
                notes=(),
                batch_fetcher=duplicate_fetcher,
                retrieval_timestamp="2026-01-02T00:00:00+00:00",
            )
            self.assertEqual(duplicate["status"], "incomplete")
            self.assertEqual(duplicate["duplicate_juans"], [1])

    def test_validator_requires_both_wref1_locks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            errors = validate(Path(temporary), mode="portable")
            self.assertEqual(len(errors), 2)
            self.assertIn("jinshu-wikisource-punctuated", errors[0])
            self.assertIn("zizhi-tongjian-wikisource-hu", errors[1])


if __name__ == "__main__":
    unittest.main()
