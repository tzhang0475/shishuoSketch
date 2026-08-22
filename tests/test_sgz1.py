from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts import build_sgz1_corpus as builder
from scripts import download_witnesses as downloader


def _section(global_juan: int) -> tuple[str, int]:
    return downloader.sanguozhi_section_for_juan(global_juan)


def _revision(global_juan: int) -> downloader.WikisourceRevision:
    section, section_juan = _section(global_juan)
    header_section = f"{section}{section_juan} 測試傳"
    content = (
        "{{header\n"
        f"| section = {header_section}\n"
        "}}\n"
        f"正文{global_juan}\n"
        f"{{{{*|裴注{global_juan}}}}}\n"
    )
    title = f"三國志/卷{global_juan:02d}"
    return downloader.WikisourceRevision(
        page_title=title,
        source_url=downloader.wikisource_page_url(title),
        api_url=downloader.wikisource_api_url(title),
        page_id=1000 + global_juan,
        revision_id=2000 + global_juan,
        parent_revision_id=1900 + global_juan,
        timestamp="2026-01-01T00:00:00Z",
        content=content,
    )


class SGZ1Tests(unittest.TestCase):
    def test_global_juan_section_mapping_is_explicit(self) -> None:
        self.assertEqual(downloader.sanguozhi_section_for_juan(1), ("魏書", 1))
        self.assertEqual(downloader.sanguozhi_section_for_juan(30), ("魏書", 30))
        self.assertEqual(downloader.sanguozhi_section_for_juan(31), ("蜀書", 1))
        self.assertEqual(downloader.sanguozhi_section_for_juan(45), ("蜀書", 15))
        self.assertEqual(downloader.sanguozhi_section_for_juan(46), ("吳書", 1))
        self.assertEqual(downloader.sanguozhi_section_for_juan(65), ("吳書", 20))
        self.assertEqual(
            downloader.sanguozhi_wikisource_volume_titles()[65], "三國志/卷65"
        )

    def test_raw_wikisource_payload_layout_is_git_ignored(self) -> None:
        result = subprocess.run(
            [
                "git",
                "check-ignore",
                "-q",
                "--",
                "sources/downloads/sanguozhi/wikisource/text/volume-001.wikitext",
            ],
            check=False,
        )
        self.assertEqual(result.returncode, 0)

    def test_structured_header_and_explicit_pei_template_are_separated(self) -> None:
        revision = _revision(31)
        units, status = builder.parse_sgz1_layers(
            revision.content,
            global_juan=31,
            source_path="fixture/volume-031.wikitext",
            source_sha256="fixture",
        )
        self.assertEqual(status, "structurally_segmented")
        self.assertEqual(
            [unit["layer"] for unit in units],
            ["metadata", "main_text", "pei_annotation", "main_text"],
        )
        self.assertEqual("".join(unit["raw_text"] for unit in units), revision.content)
        self.assertEqual(units[2]["author_layer"], "裴松之")

    def test_wikisource_editorial_markup_has_no_author_layer(self) -> None:
        content = (
            "{{header\n"
            "| section = 蜀書一 測試\n"
            "}}\n"
            "__FORCETOC__\n"
            "<onlyinclude>\n"
            "==人物甲==\n"
            "陳壽正文{{YL|建安十五年}}。\n"
            "{{*|裴松之注。}}\n"
            "\n==【評】==\n"
            "評曰：正文。\n\n"
            "</onlyinclude>\n"
            "{{footer}}\n"
            "{{西晉作品}}\n"
        )
        units, status = builder.parse_sgz1_layers(content, global_juan=31)
        self.assertEqual(status, "structurally_segmented")
        self.assertEqual("".join(unit["raw_text"] for unit in units), content)

        def matching(raw: str) -> list[dict[str, object]]:
            return [unit for unit in units if raw in str(unit["raw_text"])]

        for markup in (
            "__FORCETOC__",
            "<onlyinclude>",
            "==人物甲==",
            "==【評】==",
            "</onlyinclude>",
            "{{footer}}",
            "{{西晉作品}}",
        ):
            found = matching(markup)
            self.assertEqual(len(found), 1, markup)
            self.assertEqual(found[0]["layer"], "metadata")
            self.assertIsNone(found[0]["author_layer"])
            self.assertEqual(found[0]["segmentation_status"], "source_editorial_markup")

        main_units = matching("陳壽正文") + matching("評曰：正文")
        self.assertTrue(main_units)
        self.assertTrue(all(unit["layer"] == "main_text" for unit in main_units))
        self.assertTrue(all(unit["author_layer"] == "陳壽" for unit in main_units))
        self.assertTrue(any("{{YL|建安十五年}}" in str(unit["raw_text"]) for unit in main_units))

        pei_units = matching("{{*|裴松之注。}}")
        self.assertEqual(len(pei_units), 1)
        self.assertEqual(pei_units[0]["layer"], "pei_annotation")
        self.assertEqual(pei_units[0]["author_layer"], "裴松之")
        self.assertEqual(
            [span["kind"] for span in builder.recognized_editorial_spans(content)],
            [
                "magic_word",
                "include_wrapper",
                "section_heading",
                "section_heading",
                "include_wrapper",
                "page_template",
                "page_template",
            ],
        )

    def test_no_annotation_marker_remains_unparsed(self) -> None:
        content = "{{header|section=魏書一 測試}}\n正文"
        units, status = builder.parse_sgz1_layers(content, global_juan=1)
        self.assertEqual(status, "unresolved_unparsed")
        self.assertIn("unparsed", {unit["layer"] for unit in units})
        self.assertTrue(all(unit["author_layer"] is None for unit in units))

    def test_downloader_requires_all_65_and_records_revision_provenance(self) -> None:
        revisions = {revision.page_title: revision for revision in (_revision(i) for i in range(1, 66))}

        def batch_fetcher(titles: list[str]):
            selected = [revisions[title] for title in titles]
            raw = json.dumps(
                {"titles": list(titles), "revision_ids": [item.revision_id for item in selected]},
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
            return selected, raw, "https://fixture.invalid/w/api.php"

        with tempfile.TemporaryDirectory() as temporary:
            lock_path, manifest = downloader.run_sanguozhi_wikisource(
                Path(temporary), batch_fetcher=batch_fetcher
            )
            self.assertTrue(lock_path.exists())
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(len(manifest["records"]), 65)
            self.assertEqual(manifest["section_counts"], {"魏書": 30, "蜀書": 15, "吳書": 20})
            record = manifest["records"][30]
            self.assertEqual(record["global_juan"], 31)
            self.assertEqual(record["section"], "蜀書")
            self.assertEqual(record["revision_id"], 2031)
            self.assertRegex(record["source_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(downloader.verify_lock_manifest(Path(temporary), lock_path), [])

    def test_downloader_marks_missing_or_mislabeled_batch_incomplete(self) -> None:
        revisions = {revision.page_title: revision for revision in (_revision(i) for i in range(1, 66))}

        def missing_batch(titles: list[str]):
            selected = [revisions[title] for title in titles[1:]]
            return selected, b"{}", "https://fixture.invalid/w/api.php"

        with tempfile.TemporaryDirectory() as temporary:
            _lock, manifest = downloader.run_sanguozhi_wikisource(
                Path(temporary), batch_fetcher=missing_batch
            )
            self.assertEqual(manifest["status"], "incomplete")
            self.assertTrue(manifest["missing_juans"])
            self.assertTrue(manifest["errors"])

    def test_sgz1_build_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_root = root / "sources/downloads/sanguozhi/wikisource"
            text_root = source_root / "text"
            source_records = []
            for global_juan in range(1, 66):
                revision = _revision(global_juan)
                payload = revision.content.encode("utf-8")
                source_path = text_root / f"volume-{global_juan:03d}.wikitext"
                source_path.parent.mkdir(parents=True, exist_ok=True)
                source_path.write_bytes(payload)
                source_records.append(
                    {
                        "global_juan": global_juan,
                        "section": _section(global_juan)[0],
                        "section_juan": _section(global_juan)[1],
                        "page_title": revision.page_title,
                        "source_url": revision.source_url,
                        "api_url": revision.api_url,
                        "page_id": revision.page_id,
                        "revision_id": revision.revision_id,
                        "source_revision": revision.revision_id,
                        "revision_timestamp": revision.timestamp,
                        "source_path": source_path.relative_to(root).as_posix(),
                        "source_size": len(payload),
                        "source_sha256": hashlib.sha256(payload).hexdigest(),
                    }
                )
            source_manifest_path = source_root / "manifest.lock.json"
            source_manifest_path.write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "witness_id": "sanguozhi-wikisource",
                        "coverage": "1-65",
                        "status": "complete",
                        "records": source_records,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            output_dir = root / "content/processed/sanguozhi/sgz1"
            output_manifest = root / "data/derived/sgz1.json"
            builder.build(
                root,
                source_manifest_path=source_manifest_path,
                output_dir=output_dir,
                output_manifest_path=output_manifest,
            )
            first = {
                path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in [output_manifest, *sorted(output_dir.glob("*.md"))]
            }
            builder.build(
                root,
                source_manifest_path=source_manifest_path,
                output_dir=output_dir,
                output_manifest_path=output_manifest,
            )
            second = {
                path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in [output_manifest, *sorted(output_dir.glob("*.md"))]
            }
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
