from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml

from scripts import download_witnesses as downloader


REPO_ROOT = Path(__file__).resolve().parents[1]
WIKISOURCE_FIXTURE = REPO_ROOT / "tests/fixtures/wikisource_revision.json"


def _ling_item(volume: int) -> downloader.IAMetadata:
    identifier = f"shishuoxinyu3jua0{volume}liuy"
    files = tuple(
        downloader.IAFile(
            name=name,
            size=len(name),
            file_format="PDF" if name.endswith(".pdf") else "text",
            source="original",
            raw={},
        )
        for name in (
            f"{identifier}.pdf",
            f"{identifier}_djvu.txt",
            f"{identifier}_hocr.html",
            f"{identifier}_scandata.xml",
            f"{identifier}_jp2.zip",
        )
    )
    return downloader.IAMetadata(
        identifier=identifier,
        title="Shi shuo xin yu : 3 juan",
        metadata={
            "identifier": identifier,
            "date": "1615",
            "call_number": "PL2666 .L55 S56 1615",
            "volume": str(volume),
        },
        files=files,
        raw={},
    )


class ShishuoWitnessTests(unittest.TestCase):
    def test_registry_contains_only_active_shishuo_hierarchy(self) -> None:
        registry = yaml.safe_load(
            (REPO_ROOT / "sources/registry/shishuo.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(downloader.validate_registry_document(registry), [])
        witnesses = {witness["id"]: witness for witness in registry["witnesses"]}
        self.assertEqual(witnesses["shishuo-kanripo-wyg"]["role"], "primary")
        self.assertEqual(witnesses["shishuo-wikisource-sbck"]["role"], "same-edition-machine")
        self.assertEqual(witnesses["shishuo-ling-1615"]["role"], "secondary-ocr-visual")
        self.assertEqual(witnesses["shishuo-siku"]["role"], "secondary")
        self.assertEqual(witnesses["shishuo-local-reference-txt"]["role"], "structural-reference")
        self.assertEqual(witnesses["shishuo-jianshu-yujiaxi"]["role"], "scholarly-reference")
        self.assertNotIn("shishuo-jiaqu-tang-ncl", witnesses)

        external = yaml.safe_load(
            (REPO_ROOT / "sources/external/shishuo/jianshu-yujiaxi.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(external["author"], "余嘉錫")
        self.assertEqual(external["electronic_base_edition"], "unspecified")
        self.assertFalse(external["bulk_download"])

    def test_wikisource_revision_parser_preserves_raw_content(self) -> None:
        payload = json.loads(WIKISOURCE_FIXTURE.read_text(encoding="utf-8"))
        title = "世説新語 (四部叢刊本)/卷上之上"
        revision = downloader.parse_wikisource_revision(payload, title=title)
        self.assertEqual(revision.revision_id, 1398281)
        self.assertEqual(revision.parent_revision_id, 1398280)
        self.assertEqual(revision.content, "{{四部叢刊|世説新語}}\n德行第一\n")
        self.assertIn("rvprop=ids%7Ctimestamp%7Ccontent", downloader.wikisource_api_url(title))
        self.assertIn("%E5%8D%B7", revision.source_url)

        ranges = downloader.parse_wikisource_page_ranges(
            '<pages from="10" to="109" index="Sibu.djvu" />',
            section_title="卷上之上",
        )
        self.assertEqual((ranges[0].first_page, ranges[0].last_page), (10, 109))
        self.assertEqual(ranges[0].index_title, "Sibu.djvu")

    def test_ling_metadata_selection_and_validation(self) -> None:
        item = _ling_item(3)
        self.assertEqual(downloader.require_shishuo_ling_metadata(item), 3)
        selected = downloader.select_shishuo_ling_files(item)
        self.assertEqual(selected["pdf"].name, "shishuoxinyu3jua03liuy.pdf")
        self.assertEqual(selected["ocr"].name, "shishuoxinyu3jua03liuy_djvu.txt")
        self.assertEqual(selected["hocr"].name, "shishuoxinyu3jua03liuy_hocr.html")
        self.assertEqual(selected["page_index"].name, "shishuoxinyu3jua03liuy_scandata.xml")
        self.assertNotIn("jp2", selected)

        wrong = _ling_item(3)
        wrong.metadata["call_number"] = "wrong"
        with self.assertRaises(downloader.NonMatchingItemError):
            downloader.require_shishuo_ling_metadata(wrong)

    def test_ling_discovery_uses_search_results_and_reports_extras(self) -> None:
        items = {_ling_item(volume).identifier: _ling_item(volume) for volume in (1, 2, 3)}
        extra = _ling_item(3)
        extra = replace(
            extra,
            identifier="shishuoxinyu3jua04liuy",
            metadata={**extra.metadata, "identifier": "shishuoxinyu3jua04liuy", "volume": "4"},
        )
        items[extra.identifier] = extra
        search = {
            "response": {
                "numFound": 4,
                "docs": [{"identifier": identifier} for identifier in items],
            }
        }
        discovery = downloader.discover_shishuo_ling(
            searcher=lambda: search,
            fetcher=lambda identifier: items[identifier],
        )
        self.assertEqual(discovery["discovered_volumes"], [1, 2, 3])
        self.assertEqual(discovery["missing_volumes"], [])
        self.assertEqual(len(discovery["excluded"]), 1)
        self.assertTrue(discovery["complete"])

    def test_wikisource_lock_records_revisions_hashes_and_paths(self) -> None:
        def fetcher(title: str) -> downloader.WikisourceRevision:
            short = title.rsplit("/", 1)[-1]
            return downloader.WikisourceRevision(
                page_title=title,
                source_url=downloader.wikisource_page_url(title),
                api_url=downloader.wikisource_api_url(title),
                page_id=1,
                revision_id=2,
                parent_revision_id=1,
                timestamp="2026-01-01T00:00:00Z",
                content=(
                    f'<pages from="1" to="1" index="Index-{short}.djvu" />\n'
                    if not title.startswith("Page:")
                    else short + "\n"
                ),
            )

        def batch_fetcher(titles: list[str]) -> list[downloader.WikisourceRevision]:
            return [
                downloader.WikisourceRevision(
                    page_title=title,
                    source_url=downloader.wikisource_page_url(title),
                    api_url=downloader.wikisource_api_url(title),
                    page_id=3,
                    revision_id=4,
                    parent_revision_id=2,
                    timestamp="2026-01-01T00:00:00Z",
                    content=title + "\n",
                )
                for title in titles
            ]

        with tempfile.TemporaryDirectory() as temporary:
            lock_path, manifest = downloader.run_shishuo_wikisource(
                Path(temporary), fetcher=fetcher, batch_fetcher=batch_fetcher
            )
            self.assertTrue(lock_path.exists())
            self.assertEqual(len(manifest["records"]), 18)
            record = next(item for item in manifest["records"] if item["kind"] == "section")
            self.assertEqual(record["revision_id"], 2)
            path = Path(temporary, record["path"])
            self.assertEqual(record["size"], path.stat().st_size)
            self.assertEqual(record["sha256"], downloader.sha256_file(path))
            self.assertEqual(downloader.verify_lock_manifest(Path(temporary), lock_path), [])

    def test_ling_lock_records_all_selected_derivatives(self) -> None:
        items = {_ling_item(volume).identifier: _ling_item(volume) for volume in (1, 2, 3)}
        search = {
            "response": {
                "numFound": 3,
                "docs": [{"identifier": identifier} for identifier in items],
            }
        }

        def fake_download(url: str, destination: Path, **_kwargs):
            content = ("downloaded from " + url).encode("utf-8")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            return "downloaded", len(content), hashlib.sha256(content).hexdigest()

        with tempfile.TemporaryDirectory() as temporary, patch.object(
            downloader, "stream_download", side_effect=fake_download
        ):
            lock_path, manifest = downloader.run_shishuo_ling(
                Path(temporary),
                searcher=lambda: search,
                fetcher=lambda identifier: items[identifier],
            )
            self.assertTrue(lock_path.exists())
            self.assertEqual(manifest["discovered_volumes"], [1, 2, 3])
            self.assertEqual(len(manifest["records"]), 3)
            for record in manifest["records"]:
                self.assertEqual({file["kind"] for file in record["files"]}, {"pdf", "ocr", "hocr", "page_index"})
            self.assertEqual(downloader.verify_lock_manifest(Path(temporary), lock_path), [])

    def test_config_paths_and_gitignore_protection(self) -> None:
        config = yaml.safe_load((REPO_ROOT / "config/sources.yaml").read_text(encoding="utf-8"))
        self.assertEqual(config["downloads"]["shishuo_wikisource"], "sources/downloads/shishuo/wikisource-sbck")
        self.assertEqual(config["downloads"]["shishuo_ling"], "sources/downloads/shishuo/ling-1615")
        self.assertEqual(config["sources"]["shishuo"]["scholarly_reference"], config["external"]["shishuo_jianshu"])
        self.assertNotIn("shishuo_jiaqu", config["downloads"])
        self.assertFalse((REPO_ROOT / "sources/downloads/shishuo/jiaqu-tang-ncl").exists())

        def ignored(path: str) -> bool:
            result = subprocess.run(
                ["git", "check-ignore", "-q", "--", path],
                cwd=REPO_ROOT,
                check=False,
            )
            return result.returncode == 0

        self.assertTrue(ignored("sources/downloads/shishuo/ling-1615/pdf/volume.pdf"))
        self.assertTrue(ignored("sources/downloads/shishuo/wikisource-sbck/卷上之上.wikitext"))
        self.assertFalse(ignored("sources/downloads/shishuo/ling-1615/manifest.lock.json"))
        self.assertFalse(ignored("sources/downloads/shishuo/wikisource-sbck/manifest.lock.json"))

    def test_cli_exposes_only_new_shishuo_download_modes(self) -> None:
        parser = downloader.build_argument_parser()
        self.assertTrue(parser.parse_args(["--shishuo-wikisource"]).shishuo_wikisource)
        self.assertTrue(parser.parse_args(["--shishuo-ling"]).shishuo_ling)
        self.assertEqual(parser.parse_args(["--shishuo-ling-volume", "3"]).shishuo_ling_volume, 3)
        self.assertTrue(parser.parse_args(["--shishuo"]).shishuo)
        with self.assertRaises(SystemExit):
            parser.parse_args(["--shishuo-jiaqu"])


if __name__ == "__main__":
    unittest.main()
