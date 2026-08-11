from __future__ import annotations

from pathlib import Path
import hashlib
import unittest

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_ROOT = REPO_ROOT / "content/curated/shishuo/boundaries"
COLLATION_ROOT = REPO_ROOT / "content/curated/shishuo/collation"
ENTRY_ROOT = REPO_ROOT / "content/processed/shishuo/entries"


class ShishuoRepairOverlayTests(unittest.TestCase):
    def test_canonical_count_ids_and_supplement_provenance(self) -> None:
        entries = []
        for path in sorted(BOUNDARY_ROOT.glob("*.yaml")):
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(document, dict) and isinstance(document.get("entries"), list):
                entries.extend(document["entries"])
        self.assertEqual(len(entries), 1130)
        ids = [item["id"] for item in entries]
        self.assertEqual(len(ids), len(set(ids)))
        supplements = [
            item for item in entries if item.get("primary_witness_status") == "gap"
        ]
        self.assertEqual(
            {item["id"] for item in supplements},
            {
                "05-fangzheng-014",
                "08-shangyu-084",
                "08-shangyu-085",
                "18-qiyi-002",
                "18-qiyi-011",
                "19-xianyuan-005",
            },
        )
        for item in supplements:
            self.assertEqual(item["supplement_witness"], "shishuo-wikisource-sbck")
            self.assertEqual(item["reason"], "kanripo_digitization_gap")
            self.assertIsNotNone(item["supplement_source"])

    def test_known_boundary_repairs_are_exact(self) -> None:
        qiyi = yaml.safe_load(
            (BOUNDARY_ROOT / "18-qiyi.yaml").read_text(encoding="utf-8")
        )
        qiyi_by_ordinal = {item["ordinal"]: item for item in qiyi["entries"]}
        self.assertEqual(qiyi_by_ordinal[10]["opening_text"], "孟萬年及弟少孤居武昌陽新")
        self.assertEqual(
            qiyi_by_ordinal[17]["opening_text"], "郄尚書與謝居士善常稱謝慶緒"
        )
        self.assertEqual(
            qiyi_by_ordinal[12]["primary_witness_status"], "partial"
        )
        self.assertNotIn(
            "病篤狼狽至都時賢見之者莫",
            [item["opening_text"] for item in qiyi["entries"]],
        )

        paidiao = yaml.safe_load(
            (BOUNDARY_ROOT / "25-paidiao.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(paidiao["entries"][18]["opening_text"], "于寳向劉真長")

    def test_source_conservation_reports_and_triage(self) -> None:
        for chapter in ("05-fangzheng", "08-shangyu", "18-qiyi", "19-xianyuan", "25-paidiao"):
            report = (ENTRY_ROOT / chapter / "validation-report.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("text_conservation: passed", report)
            self.assertIn("parentheses_balanced: passed", report)
            self.assertIn("page_markers_traceable: passed", report)
            self.assertIn("raw_primary_witness_modified: false", report)

        triage = yaml.safe_load(
            (COLLATION_ROOT / "discrepancy-triage.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(triage["source_record_count"], 249)
        self.assertEqual(
            triage["summary"],
            {
                "record_count": 249,
                "structural_high": 90,
                "textual_medium": 112,
                "formatting_low": 47,
            },
        )
        self.assertFalse(triage["policy"]["repairs_applied"])

    def test_supplement_text_hashes_and_entry_outputs(self) -> None:
        document = yaml.safe_load(
            (COLLATION_ROOT / "supplemented-segments.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(document["segments"]), 6)
        for segment in document["segments"]:
            text = segment["exact_text"]
            self.assertEqual(
                hashlib.sha256(text.encode("utf-8")).hexdigest(),
                segment["exact_text_sha256"],
            )
            path = ENTRY_ROOT / segment["chapter"] / f"entry-{segment['ordinal']:03d}.md"
            emitted = path.read_text(encoding="utf-8")
            self.assertIn(text, emitted)
            self.assertIn("primary_witness_status: \"gap\"", emitted)
            self.assertIn("supplement_witness: \"shishuo-wikisource-sbck\"", emitted)

    def test_explicit_boundary_regressions_are_reflected_in_entries(self) -> None:
        paidiao_previous = (
            ENTRY_ROOT / "25-paidiao" / "entry-018.md"
        ).read_text(encoding="utf-8")
        paidiao_next = (
            ENTRY_ROOT / "25-paidiao" / "entry-019.md"
        ).read_text(encoding="utf-8")
        self.assertIn("此中空洞無物然容卿輩數百人", paidiao_previous)
        self.assertIn("opening_text: \"于寳向劉真長\"", paidiao_next)

        qiyi_tenth = (
            ENTRY_ROOT / "18-qiyi" / "entry-010.md"
        ).read_text(encoding="utf-8")
        qiyi_twelfth = (
            ENTRY_ROOT / "18-qiyi" / "entry-012.md"
        ).read_text(encoding="utf-8")
        self.assertIn("opening_text: \"孟萬年及弟少孤居武昌陽新\"", qiyi_tenth)
        self.assertIn("病篤狼狽至都", qiyi_tenth)
        self.assertIn("opening_text: \"謝太傅曰卿兄弟志業何其太\"", qiyi_twelfth)

        qiyi_seventeenth = (
            ENTRY_ROOT / "18-qiyi" / "entry-017.md"
        ).read_text(encoding="utf-8")
        self.assertIn("opening_text: \"郄尚書與謝居士善常稱謝慶緒\"", qiyi_seventeenth)


if __name__ == "__main__":
    unittest.main()
