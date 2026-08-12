from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.validate_wp1 import OBJECTS, validate_references, validate_repository, validate_schema


ROOT = Path(__file__).resolve().parents[1]


class WP1Tests(unittest.TestCase):
    def records_by_kind(self) -> dict[str, list[dict[str, object]]]:
        records: dict[str, list[dict[str, object]]] = {}
        for _, (_, data_rel, kind) in OBJECTS.items():
            document = json.loads((ROOT / data_rel).read_text(encoding="utf-8"))
            records[kind] = document["records"]
        return records

    def provenance_errors(self, mutate) -> list[str]:
        records = self.records_by_kind()
        mutate(records)
        return validate_references(records, root=ROOT)

    def test_all_wp1_object_records_validate(self) -> None:
        self.assertEqual(validate_repository(ROOT), [])

    def test_invalid_record_reports_field_and_constraint(self) -> None:
        errors = validate_schema(schema_path=ROOT / "schema/person.schema.json", records=[{"id": "bad"}], label="Person")
        self.assertTrue(errors)
        self.assertTrue(any("canonical_name" in error for error in errors))

    def test_first_story_is_generated_from_canonical_entry(self) -> None:
        story = json.loads(
            (ROOT / "data/annotation/wp1-stories.json").read_text(encoding="utf-8")
        )["records"][0]
        entry = (ROOT / "content/processed/shishuo/entries/06-yaliang/entry-019.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(story["id"], "06-yaliang-019")
        self.assertIn("郗太傅在京口", story["text"])
        self.assertIn(story["text"], entry)
        self.assertEqual(story["review_status"], "reviewed")

    def test_static_bundle_exposes_all_wp1_object_kinds(self) -> None:
        bundle = json.loads((ROOT / "data/derived/wp1-site.json").read_text(encoding="utf-8"))
        self.assertEqual(
            {"stories", "people", "mentions", "relations", "eras", "evidence", "sources"},
            set(bundle) - {"schema", "generated_from"},
        )
        self.assertTrue(bundle["stories"])
        self.assertTrue(bundle["people"])
        self.assertTrue(bundle["relations"])
        self.assertTrue(bundle["eras"])
        self.assertTrue(bundle["evidence"])

    def test_nonexistent_shishuo_entry_is_rejected(self) -> None:
        errors = self.provenance_errors(
            lambda records: records["stories"][0].__setitem__("source_entry_id", "99-missing-001")
        )
        self.assertTrue(any("source_entry_id does not exist" in error for error in errors))

    def test_nonexistent_jinshu_unit_is_rejected(self) -> None:
        def mutate(records):
            evidence = next(item for item in records["evidence"] if item["id"] == "evidence-004")
            evidence["locator"]["unit_id"] = "999-liezhuan-999"

        errors = self.provenance_errors(mutate)
        self.assertTrue(any("nonexistent Jinshu unit" in error for error in errors))

    def test_wrong_locator_path_is_rejected(self) -> None:
        def mutate(records):
            evidence = next(item for item in records["evidence"] if item["id"] == "evidence-004")
            evidence["locator"]["artifact_path"] = "content/processed/jinshu/units/missing.md"

        errors = self.provenance_errors(mutate)
        self.assertTrue(any("artifact_path" in error and "does not exist" in error for error in errors))

    def test_wrong_locator_sha256_is_rejected(self) -> None:
        def mutate(records):
            evidence = next(item for item in records["evidence"] if item["id"] == "evidence-004")
            evidence["locator"]["artifact_sha256"] = "0" * 64

        errors = self.provenance_errors(mutate)
        self.assertTrue(any("artifact_sha256 does not match" in error for error in errors))

    def test_wrong_source_provenance_sha256_is_rejected(self) -> None:
        def mutate(records):
            evidence = next(item for item in records["evidence"] if item["id"] == "evidence-004")
            evidence["locator"]["source_provenance"]["source_sha256"] = "0" * 64

        errors = self.provenance_errors(mutate)
        self.assertTrue(any("source_sha256 does not match" in error for error in errors))

    def test_mismatched_entry_id_and_path_is_rejected(self) -> None:
        def mutate(records):
            evidence = next(item for item in records["evidence"] if item["id"] == "evidence-001")
            evidence["locator"]["entry_id"] = "01-dexing-001"

        errors = self.provenance_errors(mutate)
        self.assertTrue(any("artifact_path does not match" in error for error in errors))

    def test_attested_person_without_evidence_is_rejected(self) -> None:
        errors = self.provenance_errors(
            lambda records: records["people"][2].__setitem__("evidence_ids", [])
        )
        self.assertTrue(any("is attested but has no evidence_ids" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
