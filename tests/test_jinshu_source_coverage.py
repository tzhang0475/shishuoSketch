from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts import audit_jinshu_source_coverage as audit
from scripts import download_witnesses as downloader


class JinshuSourceCoverageTests(unittest.TestCase):
    def test_scan_uses_explicit_headings_and_reports_repeated_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "KR2a0015_000.txt").write_text(
                "晉書一百三十卷¶\n晉書卷一¶\n晉書卷三十四¶\n",
                encoding="utf-8",
            )
            (root / "KR2a0015_001.txt").write_text(
                "#+PROPERTY: JUAN 卷一\n晉書巻一\n本文\n晉書卷一\n",
                encoding="utf-8",
            )
            (root / "KR2a0015_033.txt").write_text(
                "#+PROPERTY: JUAN 卷三十三\n晉書卷三十三\n晉書卷三十二\n",
                encoding="utf-8",
            )
            scan = audit.scan_source_tree(root)
            self.assertEqual(scan["main_volumes"], [1, 32, 33])
            self.assertEqual(scan["catalogue_volumes"], [1, 34])
            self.assertEqual(len(scan["main_by_volume"][33]), 1)
            self.assertEqual(scan["properties"]["KR2a0015_001.txt"], "卷一")

    def test_wikisource_discovery_filters_nonvolume_pages(self) -> None:
        base = downloader.JINSHU_WIKISOURCE_BASE_TITLE
        payload = {
            "query": {
                "allpages": [
                    {"title": f"{base}/卷002"},
                    {"title": f"{base}/卷130"},
                    {"title": f"{base}/音義卷之上"},
                ]
            }
        }
        parsed = downloader.parse_jinshu_wikisource_discovery(payload)
        self.assertEqual(parsed["discovered_volumes"], [2, 130])
        self.assertEqual(parsed["duplicate_volumes"], [])
        self.assertEqual(parsed["unexpected_pages"], [f"{base}/音義卷之上"])

    def test_fixture_wikisource_download_writes_lock_and_hashes(self) -> None:
        base = downloader.JINSHU_WIKISOURCE_BASE_TITLE

        def discovery_fetcher() -> tuple[bytes, dict[str, object]]:
            payload = {
                "query": {
                    "allpages": [
                        {"title": f"{base}/卷{number:03d}"}
                        for number in range(2, 131)
                    ]
                }
            }
            return json.dumps(payload, ensure_ascii=False).encode("utf-8"), payload

        def batch_fetcher(
            titles: list[str] | tuple[str, ...],
        ) -> tuple[list[downloader.WikisourceRevision], bytes, str]:
            revisions = []
            for title in titles:
                number = 1 if title == base else int(title.rsplit("卷", 1)[1])
                revisions.append(
                    downloader.WikisourceRevision(
                        page_title=title,
                        source_url=downloader.wikisource_page_url(title),
                        api_url="https://example.invalid/api",
                        page_id=1000 + number,
                        revision_id=2000 + number,
                        parent_revision_id=1999 + number,
                        timestamp="2026-01-01T00:00:00Z",
                        content=f"晉書卷{'一' if number == 1 else number}\n原始測試內容",
                    )
                )
            raw = json.dumps(
                {"titles": list(titles)}, ensure_ascii=False
            ).encode("utf-8")
            return revisions, raw, "https://example.invalid/api"

        with tempfile.TemporaryDirectory() as temporary:
            lock_path, manifest = downloader.run_jinshu_wikisource(
                Path(temporary),
                discovery_fetcher=discovery_fetcher,
                batch_fetcher=batch_fetcher,
            )
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(manifest["retrieved_volume_count"], 130)
            self.assertEqual([record["volume"] for record in manifest["records"]], list(range(1, 131)))
            self.assertEqual(downloader.verify_lock_manifest(Path(temporary), lock_path), [])
            self.assertEqual(
                (Path(temporary) / "sources/downloads/jinshu/wikisource-siku/text/volume-001.txt").read_text(encoding="utf-8"),
                "晉書卷一\n原始測試內容",
            )


if __name__ == "__main__":
    unittest.main()
