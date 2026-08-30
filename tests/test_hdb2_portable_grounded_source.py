import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import hdb2_p1_common as p1  # noqa: E402
import hdb2_portable_grounded_source as portable  # noqa: E402
import hdb2_psl1_2_common as psl1_2  # noqa: E402
import hdb2_psl1_3_common as psl1_3  # noqa: E402
from build_hdb2_portable_grounded_source_index import build_projection  # noqa: E402


class HDB2PortableGroundedSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = json.loads(portable.INDEX_PATH.read_text(encoding="utf-8"))
        cls.full_units = [dict(row) for row in p1.build_source_index()]
        cls.required_psl1_2 = (
            ("宣王", "司馬懿"),
            ("祖車騎", "祖逖"),
            ("孔廷尉", "孔坦"),
            ("劉尹", "劉惔"),
        )
        cls.required_psl1_3 = (
            ("劉尹", "劉惔"),
            ("朕", "康帝"),
            ("中丞", "髙靈"),
            ("阮光禄", "阮裕"),
            ("聘", "謝聘"),
            ("鳯", "謝鳳"),
        )

    @staticmethod
    def _direct_candidates(builder, surface):
        return sorted({
            str(row.get("candidate_surface"))
            for row in builder([surface])
            if row.get("direct_identity_support") and row.get("candidate_surface")
        })

    def _with_physical_filter(self, include, callback):
        filtered = [dict(unit) for unit in self.full_units if include(unit)]
        portable.load_portable_source_units.cache_clear()
        psl1_3._source_units.cache_clear()
        try:
            with patch.object(p1, "build_source_index", return_value=filtered):
                return callback()
        finally:
            portable.load_portable_source_units.cache_clear()
            psl1_3._source_units.cache_clear()

    def test_projection_has_source_provenance_and_no_identity_answer_table(self):
        self.assertEqual(self.index.get("schema"), portable.SCHEMA)
        self.assertTrue(self.index.get("candidate_only"))
        self.assertFalse(self.index.get("canonical_write_back"))
        self.assertEqual(self.index.get("record_count"), len(self.index.get("records", [])))
        self.assertEqual(portable.validate_index(self.index), [])
        for row in self.index["records"]:
            for key in (
                "source_ref", "source_work", "source_layer", "source_locator",
                "source_sha256", "evidence_text", "source_form", "window_sha256",
                "window_start", "window_end",
            ):
                self.assertIn(key, row)
            self.assertNotIn("candidate_surface", row)
            self.assertNotIn("person_id", row)
            self.assertNotIn("expected", row)

    def test_projection_rebuild_is_byte_deterministic(self):
        first = build_projection(self.full_units)
        second = build_projection(self.full_units)
        self.assertEqual(first, second)
        self.assertEqual(first, self.index)

    def test_projection_windows_are_exact_substrings_of_full_witnesses(self):
        by_ref = {str(row.get("ref")): row for row in self.full_units}
        for record in self.index["records"]:
            source = by_ref.get(str(record["source_ref"]))
            self.assertIsNotNone(source, record["source_ref"])
            self.assertIn(record["evidence_text"], str(source["evidence_text"]))
            self.assertEqual(record["source_sha256"], source["source_sha256"])

    def test_physical_unit_wins_over_same_ref_portable_window(self):
        physical = {"ref": "same", "evidence_text": "physical", "source_form": "legacy_local"}
        fallback = {"ref": "same", "evidence_text": "window", "source_form": portable.PORTABLE_SOURCE_FORM}
        merged = portable.merge_source_units([physical], [fallback])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["evidence_text"], "physical")

    def test_without_fallback_simulated_missing_payload_reproduces_missing_resource(self):
        def no_fallback():
            with patch.object(portable, "load_portable_source_units", return_value=[]):
                return psl1_2.build_grounded_resource_index(["祖車騎"])

        rows = self._with_physical_filter(
            lambda unit: unit.get("source_work") not in {"箋疏", "箋疏正文", "晉書"},
            no_fallback,
        )
        self.assertEqual(rows, [])

    def test_portable_fallback_recovers_required_generic_candidates(self):
        include_committed = lambda unit: unit.get("source_work") not in {"箋疏", "箋疏正文", "晉書"}

        def run():
            psl1_2_results = {
                surface: self._direct_candidates(psl1_2.build_grounded_resource_index, surface)
                for surface, _ in self.required_psl1_2
            }
            psl1_3_results = {
                surface: self._direct_candidates(psl1_3.build_grounded_resource_index, surface)
                for surface, _ in self.required_psl1_3
            }
            return psl1_2_results, psl1_3_results

        full = self._with_physical_filter(lambda unit: True, run)
        fallback = self._with_physical_filter(include_committed, run)
        for surface, expected in self.required_psl1_2:
            self.assertIn(expected, full[0][surface])
            self.assertIn(expected, fallback[0][surface])
        for surface, expected in self.required_psl1_3:
            self.assertIn(expected, full[1][surface])
            self.assertIn(expected, fallback[1][surface])

    def test_required_fallback_rows_preserve_source_refs_and_exact_spans(self):
        include_committed = lambda unit: unit.get("source_work") not in {"箋疏", "箋疏正文", "晉書"}

        def run():
            rows = {}
            for surface, expected in (*self.required_psl1_2, *self.required_psl1_3):
                builder = (
                    psl1_2.build_grounded_resource_index
                    if (surface, expected) in self.required_psl1_2
                    else psl1_3.build_grounded_resource_index
                )
                rows[surface] = next(
                    row for row in builder([surface])
                    if row.get("direct_identity_support")
                    and str(row.get("candidate_surface")) == expected
                )
            return rows

        rows = self._with_physical_filter(include_committed, run)
        by_ref = {str(row.get("ref")): row for row in self.full_units}
        for row in rows.values():
            source = by_ref[str(row["source_ref"])]
            self.assertIn(row["exact_span"], str(source["evidence_text"]))
            self.assertRegex(str(row.get("source_sha256")), r"^[0-9a-f]{64}$")
            self.assertTrue(row.get("source_locator"))

    def test_invalid_projection_fails_closed(self):
        invalid = copy.deepcopy(self.index)
        invalid["records"] = list(invalid["records"])
        invalid["records"][0] = dict(invalid["records"][0])
        invalid["records"][0]["evidence_text"] += "外部"
        self.assertTrue(portable.validate_index(invalid))
        self.assertEqual(
            portable.load_portable_source_units(Path("/tmp/does-not-exist-hdb2-index.json")),
            [],
        )


if __name__ == "__main__":
    unittest.main()
