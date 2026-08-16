from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read_json(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class D10BundleAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit = read_json("data/derived/d1-0-bundle-size-audit.json")
        cls.dependencies = read_json("data/derived/d1-0-dependency-audit.json")

    def test_bundle_views_are_byte_identical(self) -> None:
        derived = (ROOT / "data/derived/sc1-site.json").read_bytes()
        generated = (ROOT / "site/src/generated/sc1-site.json").read_bytes()
        self.assertEqual(derived, generated)
        self.assertEqual(self.audit["inputs"]["byte_identical"], True)
        self.assertEqual(self.audit["inputs"]["derived_sha256"], self.audit["inputs"]["generated_sha256"])

    def test_required_fields_and_byte_totals(self) -> None:
        required = self.audit["inputs"]["required_top_level_fields"]
        measured = [row["path"] for row in self.audit["top_level_fields"]]
        self.assertEqual(measured, required)
        size = self.audit["bundle_size"]
        self.assertEqual(
            sum(row["serialized_bytes"] for row in self.audit["top_level_fields"]),
            size["top_level_field_serialized_bytes"],
        )
        self.assertEqual(
            size["top_level_field_serialized_bytes"] + size["top_level_syntax_overhead_bytes"],
            size["compact_serialized_bytes"],
        )

    def test_evidence_display_is_measured_as_repeated_projection(self) -> None:
        finding = self.audit["duplication_findings"]["story_reading_evidence_display"]
        self.assertEqual(finding["story_count"], 143)
        self.assertEqual(finding["unique_evidence_ids"], 1513)
        self.assertGreater(finding["entry_occurrences"], finding["unique_evidence_ids"])
        self.assertGreater(finding["repeat_value_bytes_upper_bound"], 0)

    def test_dependency_paths_are_unique(self) -> None:
        paths = [row["path"] for row in self.dependencies["consumers"]]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual(self.dependencies["duplicate_path_count"], 0)
        self.assertGreater(self.dependencies["direct_literal_bundle_consumer_count"], 0)

    def test_protected_hash_manifest_is_present(self) -> None:
        manifest = self.audit["protection_manifest"]
        self.assertTrue(manifest)
        self.assertTrue(all(row["exists"] and row["sha256"] for row in manifest))


if __name__ == "__main__":
    unittest.main()

