from __future__ import annotations

import json
from pathlib import Path
import unittest

import yaml

from scripts import compare_shishuo_witnesses as comparison


REPO_ROOT = Path(__file__).resolve().parents[1]
KNOWN_REPORT = REPO_ROOT / "content/curated/shishuo/collation/known-anomalies.yaml"
CORPUS_REPORT = REPO_ROOT / "content/curated/shishuo/collation/corpus-discrepancies.yaml"


class ShishuoComparisonTests(unittest.TestCase):
    def test_alignment_key_preserves_character_variants(self) -> None:
        self.assertNotEqual(comparison.alignment_key("勖"), comparison.alignment_key("朂"))
        self.assertEqual(
            comparison.alignment_key("&KR0679;"), comparison.ALIGNMENT_GLYPH
        )
        self.assertEqual(
            comparison.alignment_key("⟦{{SKchar|302}}⟧"), comparison.ALIGNMENT_GLYPH
        )

    def test_wikisource_fixture_parser_keeps_annotations_and_glyph_markers(self) -> None:
        record = {
            "page_title": "Page:fixture/1",
            "page_number": 1,
            "path": "fixture.wikitext",
            "source_url": "https://example.invalid/Page:fixture/1",
            "revision_id": 7,
        }
        page = comparison._extract_wikisource_page(
            "正文{{雙行註文|甲|乙}}{{SKchar|302}}尾", record
        )
        raw = "".join(unit.raw for unit in page.main_units)
        key = "".join(unit.key for unit in page.main_units)
        self.assertIn("正文", raw)
        self.assertIn("⟦{{SKchar|302}}⟧", raw)
        self.assertIn("尾", raw)
        self.assertEqual(page.annotations, ("{{雙行註文|甲|乙}}",))
        self.assertEqual(key, "正文" + comparison.ALIGNMENT_GLYPH + "尾")

    def test_known_anomaly_regressions(self) -> None:
        report = yaml.safe_load(KNOWN_REPORT.read_text(encoding="utf-8"))
        records = {record["id"]: record for record in report["records"]}
        expected_ids = {
            "05-fangzheng-014",
            "08-shangyu-084",
            "08-shangyu-085",
            "18-qiyi-002",
            "18-qiyi-011",
            "19-xianyuan-005",
            "18-qiyi-010",
            "18-qiyi-015",
            "25-paidiao-019",
        }
        self.assertEqual(set(records), expected_ids)
        for case_id in (
            "05-fangzheng-014",
            "08-shangyu-084",
            "08-shangyu-085",
            "18-qiyi-002",
            "18-qiyi-011",
            "19-xianyuan-005",
        ):
            self.assertEqual(records[case_id]["classification"], "kanripo_digitization_gap")
            self.assertEqual(records[case_id]["confidence"], "high")
            self.assertEqual(records[case_id]["wikisource_sbck"]["status"], "located")
        for case_id in (
            "18-qiyi-010",
            "18-qiyi-015",
            "25-paidiao-019",
        ):
            self.assertEqual(records[case_id]["classification"], "boundary_shift")
            self.assertEqual(records[case_id]["confidence"], "high")
            self.assertEqual(records[case_id]["wikisource_sbck"]["status"], "located")

        self.assertIn("病篤", records["18-qiyi-010"]["kanripo"]["source_context"])
        self.assertIn("郄尚書", records["18-qiyi-015"]["wikisource_sbck"]["reading"])
        self.assertIn("于寳向劉真長", records["25-paidiao-019"]["wikisource_sbck"]["reading"])

    def test_corpus_scan_has_all_chapters_and_allowed_classifications(self) -> None:
        report = yaml.safe_load(CORPUS_REPORT.read_text(encoding="utf-8"))
        self.assertEqual(report["scan"]["chapter_count"], 36)
        self.assertEqual(len(report["scan"]["summaries"]), 36)
        allowed = {
            "kanripo_digitization_gap",
            "kanripo_transcription_error",
            "boundary_shift",
            "textual_variant",
            "witness_specific_gap",
            "structural_difference",
            "unresolved",
        }
        for record in report["records"]:
            self.assertIn(record["classification"], allowed)

    def test_derived_outputs_are_disjoint_from_source_trees(self) -> None:
        self.assertTrue(comparison.OUTPUT_ROOT.is_relative_to(REPO_ROOT / "content"))
        self.assertTrue(comparison.REPORT_ROOT.is_relative_to(REPO_ROOT / "content"))
        self.assertFalse(comparison.OUTPUT_ROOT.is_relative_to(comparison.CHAPTER_ROOT))
        self.assertFalse(comparison.OUTPUT_ROOT.is_relative_to(comparison.WIKISOURCE_ROOT))
        self.assertFalse(comparison.REPORT_ROOT.is_relative_to(comparison.BOUNDARY_ROOT))
        self.assertTrue(
            (comparison.OUTPUT_ROOT / "structural-reference" / "shishuo.txt").exists()
        )
        report = yaml.safe_load(CORPUS_REPORT.read_text(encoding="utf-8"))
        self.assertTrue(all(record.get("requires_visual_verification") for record in report["records"]))


if __name__ == "__main__":
    unittest.main()
