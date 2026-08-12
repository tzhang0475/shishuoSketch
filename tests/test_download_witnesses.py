from __future__ import annotations

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
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "ia_metadata.json"
REQUIRED_FIELDS = downloader.REQUIRED_REGISTRY_FIELDS


def _fixture_items() -> tuple[downloader.IAMetadata, downloader.IAMetadata]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return (
        downloader.parse_ia_metadata(payload["jinshu"]),
        downloader.parse_ia_metadata(payload["songkeben"]),
    )


class DownloadWitnessTests(unittest.TestCase):
    def test_registry_schema_and_required_fields(self) -> None:
        for path in sorted((REPO_ROOT / "sources/registry").glob("*.yaml")):
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(downloader.validate_registry_document(document), [], path)
            for witness in document["witnesses"]:
                self.assertTrue(REQUIRED_FIELDS <= set(witness), witness["id"])

        jinshu = yaml.safe_load(
            (REPO_ROOT / "sources/registry/jinshu.yaml").read_text(encoding="utf-8")
        )
        ctext = next(item for item in jinshu["witnesses"] if item["id"] == "jinshu-wuyingdian")
        self.assertEqual(
            ctext["remote_record"],
            "https://ctext.org/library.pl?if=gb&remap=gb&res=77692",
        )
        completion = next(
            item for item in jinshu["witnesses"] if item["id"] == "jinshu-wikisource-siku"
        )
        self.assertEqual(completion["role"], "primary-machine")
        self.assertEqual(completion["coverage"], "1-130")

    def test_config_paths_are_repository_relative_and_registered(self) -> None:
        config = yaml.safe_load(
            (REPO_ROOT / "config/sources.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(config["sources"]["shishuo"]["primary"], "shishuoSources/shishuo")
        self.assertEqual(config["sources"]["jinshu"]["primary"], "sources/downloads/jinshu/wikisource-siku")
        self.assertEqual(
            config["sources"]["jinshu"]["same_edition_machine_completion"],
            "sources/downloads/jinshu/wikisource-siku",
        )
        self.assertEqual(config["sources"]["sanguozhi"]["primary"], "shishuoSources/sanguozhi")
        for relative in config["downloads"].values():
            self.assertFalse(Path(relative).is_absolute())

    def test_ia_metadata_parsing_and_volume_extraction(self) -> None:
        jinshu, _song = _fixture_items()
        self.assertEqual(jinshu.identifier, "02077718.cn")
        self.assertEqual(jinshu.title, "晉書斠注(一)")
        self.assertEqual(len(jinshu.files), 3)
        self.assertEqual(downloader.extract_volume_number("晉書斠注(一)"), 1)
        self.assertEqual(downloader.extract_volume_number("晉書斠注(十一)"), 11)
        self.assertEqual(downloader.extract_volume_number("第廿一卷"), None)
        self.assertEqual(downloader.extract_volume_number("卷二十八"), 28)

    def test_nonmatching_ia_item_is_refused(self) -> None:
        jinshu, _song = _fixture_items()
        wrong = downloader.IAMetadata(
            identifier="02077718.cn",
            title="不是目标书目",
            metadata=jinshu.metadata,
            files=jinshu.files,
            raw=jinshu.raw,
        )
        with self.assertRaises(downloader.NonMatchingItemError):
            downloader.require_title(wrong, "晉書斠注")

        discovery = downloader.discover_jinshu(
            fetcher=lambda _identifier: wrong,
            first=18,
            last=18,
        )
        self.assertEqual(discovery["accepted"], [])
        self.assertEqual(len(discovery["rejected"]), 1)

    def test_file_selection_is_deterministic_and_excludes_archival_payloads(self) -> None:
        jinshu, song = _fixture_items()
        selected_jinshu = downloader.select_jinshu_files(jinshu)
        self.assertEqual(selected_jinshu["pdf"].name, "02077718.cn.pdf")
        self.assertEqual(selected_jinshu["ocr"].name, "02077718.cn_djvu.txt")

        selected_song = downloader.select_sanguozhi_files(song)
        self.assertTrue(selected_song["pdf"].name.endswith("_text.pdf"))
        self.assertTrue(selected_song["ocr"].name.endswith("_djvu.txt"))
        self.assertNotIn("archival", selected_song)
        self.assertTrue(
            downloader.select_sanguozhi_files(song, include_archival=True)["archival"].name.endswith(
                "_jp2.zip"
            )
        )

        ambiguous = [
            downloader.IAFile("a.pdf", 1, "PDF", "", {}),
            downloader.IAFile("b.pdf", 1, "PDF", "", {}),
        ]
        with self.assertRaises(downloader.AmbiguousFileError):
            downloader.select_deterministic_file(ambiguous, suffix=".pdf")

    def test_sha256_generation_and_safe_stream_download(self) -> None:
        content = b"witness fixture\n"
        expected = hashlib.sha256(content).hexdigest()

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _size: int = -1) -> bytes:
                nonlocal content
                value, content = content, b""
                return value

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "payload.bin"
            status, size, digest = downloader.stream_download(
                "https://example.invalid/payload.bin",
                destination,
                expected_sha256=expected,
                opener=lambda _request, **_kwargs: Response(),
            )
            self.assertEqual(status, "downloaded")
            self.assertEqual(size, len(b"witness fixture\n"))
            self.assertEqual(digest, expected)
            self.assertEqual(downloader.sha256_file(destination), expected)
            with self.assertRaises(FileExistsError):
                downloader.stream_download(
                    "https://example.invalid/payload.bin",
                    destination,
                    opener=lambda _request, **_kwargs: Response(),
                )

    def test_manifest_lock_generation_records_provenance(self) -> None:
        _jinshu, song = _fixture_items()

        def fake_fetcher(identifier: str) -> downloader.IAMetadata:
            self.assertEqual(identifier, "songkeben")
            return song

        def fake_download(url: str, destination: Path, **_kwargs):
            data = ("downloaded from " + url).encode("utf-8")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            return "downloaded", len(data), hashlib.sha256(data).hexdigest()

        with tempfile.TemporaryDirectory() as temporary, patch.object(
            downloader, "stream_download", side_effect=fake_download
        ):
            lock_path, manifest = downloader.run_sanguozhi(Path(temporary), fetcher=fake_fetcher)
            self.assertTrue(lock_path.exists())
            self.assertEqual(manifest["records"][0]["identifier"], "songkeben")
            file_record = manifest["records"][0]["files"][0]
            self.assertTrue(file_record["source_url"].startswith("https://archive.org/download/songkeben/"))
            self.assertEqual(file_record["size"], Path(temporary, file_record["path"]).stat().st_size)
            self.assertRegex(file_record["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(file_record["retrieved_at"])

    def test_duplicate_and_missing_volume_detection(self) -> None:
        jinshu, _song = _fixture_items()

        def item(identifier: str, title: str) -> downloader.IAMetadata:
            return downloader.IAMetadata(
                identifier=identifier,
                title=title,
                metadata=jinshu.metadata,
                files=jinshu.files,
                raw=jinshu.raw,
            )

        by_identifier = {
            "02077718.cn": item("02077718.cn", "晉書斠注(一)"),
            "02077719.cn": item("02077719.cn", "晉書斠注(三)"),
        }

        def fetcher(identifier: str) -> downloader.IAMetadata:
            if identifier not in by_identifier:
                raise downloader.HTTPError(
                    "https://archive.org/metadata/" + identifier, 404, "missing", {}, None
                )
            return by_identifier[identifier]

        discovery = downloader.discover_jinshu(fetcher=fetcher, first=18, last=20)
        self.assertEqual(discovery["discovered_volumes"], [1, 3])
        self.assertEqual(discovery["missing_volumes"], [2])

        by_identifier["02077719.cn"] = item("02077719.cn", "晉書斠注(一)")
        duplicate = downloader.discover_jinshu(fetcher=fetcher, first=18, last=19)
        self.assertEqual(duplicate["duplicate_volumes"], [1])

    def test_gitignore_protects_sources_and_download_payloads(self) -> None:
        def ignored(path: str) -> bool:
            result = subprocess.run(
                ["git", "check-ignore", "-q", "--", path],
                cwd=REPO_ROOT,
                check=False,
            )
            return result.returncode == 0

        self.assertTrue(ignored("shishuoSources/shishuo/example.txt"))
        self.assertTrue(ignored("sources/downloads/jinshu/jinshu-jiaozhu/pdf/book.pdf"))
        self.assertFalse(ignored("sources/downloads/jinshu/jinshu-jiaozhu/README.md"))
        self.assertFalse(ignored("sources/downloads/jinshu/jinshu-jiaozhu/manifest.yaml"))
        self.assertFalse(ignored("sources/downloads/jinshu/jinshu-jiaozhu/manifest.lock.json"))
        self.assertTrue(ignored("sources/downloads/jinshu/wikisource-siku/text/volume-001.txt"))
        self.assertFalse(ignored("sources/downloads/jinshu/wikisource-siku/metadata.yaml"))
        self.assertFalse(ignored("sources/downloads/jinshu/wikisource-siku/manifest.lock.json"))


if __name__ == "__main__":
    unittest.main()
