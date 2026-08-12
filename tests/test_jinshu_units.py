from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.materialize_jinshu_units import (
    DEFAULT_SOURCE_DIR,
    REPOSITORY_ROOT,
    materialize,
    parse_sources,
    validate_units,
)
from scripts.search_jinshu import load_index, search_records


class JinshuStructuralUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        root = Path(cls.temporary.name)
        cls.output_dir = root / "units"
        cls.index_path = root / "jinshu-unit-index.json"
        cls.report_path = root / "structural-report.md"
        cls.sources, cls.units, cls.anomalies, cls.errors = materialize(
            root=REPOSITORY_ROOT,
            source_dir=DEFAULT_SOURCE_DIR,
            output_dir=cls.output_dir,
            index_path=cls.index_path,
            report_path=cls.report_path,
        )
        cls.index = load_index(cls.index_path)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_all_normalized_source_bodies_are_covered(self) -> None:
        self.assertEqual(self.errors, [])
        self.assertEqual(validate_units(self.sources, self.units, REPOSITORY_ROOT), [])
        self.assertEqual(len(self.sources), 130)
        self.assertEqual(sorted({unit.volume_number for unit in self.units if unit.volume_number}), list(range(1, 131)))

    def test_category_counts_and_repeated_occurrences_are_explicit(self) -> None:
        categories = {}
        for record in self.index["units"]:
            categories[record["category"]] = categories.get(record["category"], 0) + 1
        self.assertEqual(categories["catalogue"], 1)
        self.assertEqual(categories["benji"], 10)
        self.assertEqual(categories["zhi"], 20)
        self.assertEqual(categories["liezhuan"], 480)
        self.assertEqual(categories["zaiji"], 30)
        self.assertEqual(categories["editorial"], 90)
        ids = [record["unit_id"] for record in self.index["units"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(
            {record["volume_number"] for record in self.index["units"] if record["category"] not in {"catalogue", "editorial"}},
            set(range(1, 131)),
        )

    def test_units_have_primary_provenance_and_exact_source_hashes(self) -> None:
        for record in self.index["units"]:
            self.assertEqual(record["source_witness"], "jinshu-wikisource-siku")
            self.assertTrue(record["source_file"])
            self.assertTrue(record["source_sha256"])
            self.assertTrue(record["unit_text_sha256"])
            self.assertGreater(record["character_count"], 0)
            path = Path(record["file_path"])
            self.assertTrue(path.is_file())
            self.assertIn("## Original source (exact)", path.read_text(encoding="utf-8"))

    def test_liezhuan_heading_and_parent_unit_are_structural(self) -> None:
        by_id = {record["unit_id"]: record for record in self.index["units"]}
        self.assertEqual(by_id["031-liezhuan-001"]["title"], "后妃上")
        self.assertEqual(by_id["031-liezhuan-002"]["title"], "宣穆張皇后")
        self.assertEqual(by_id["031-liezhuan-002"]["parent_unit"], "031-liezhuan-001")
        self.assertEqual(by_id["033-liezhuan-002"]["title"], "王覽")
        self.assertEqual(by_id["033-liezhuan-002"]["boundary_confidence"], "medium")

    def test_search_reads_only_local_materialized_units(self) -> None:
        results = search_records(
            "王祥",
            index_path=self.index_path,
            category="liezhuan",
            context=20,
            root=REPOSITORY_ROOT,
        )
        self.assertTrue(results)
        self.assertTrue(all(result["category"] == "liezhuan" for result in results))
        self.assertTrue(any(result["title"] == "王祥" for result in results))
        self.assertTrue(all("http" not in str(result["file_path"]) for result in results))

    def test_report_records_complete_canonical_coverage(self) -> None:
        report = self.report_path.read_text(encoding="utf-8")
        self.assertIn("catalogue volume numbers detected: 130", report)
        self.assertIn("canonical coverage check (卷1-卷130 exactly once): passed", report)
        self.assertIn("result: passed", report)


if __name__ == "__main__":
    unittest.main()
