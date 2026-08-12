from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from copy import deepcopy
from unittest.mock import patch

from opencc import OpenCC

import scripts.validate_wp1 as validate_wp1_module

from scripts.validate_wp1 import (
    OBJECTS,
    validate_references,
    validate_repository,
    validate_schema,
    validate_source_provenance,
    validate_punctuation,
    validate_punctuation_reference,
)
from scripts.reading_layers import canonical_sections, validate_punctuation_round_trip


ROOT = Path(__file__).resolve().parents[1]


class WP1Tests(unittest.TestCase):
    def records_by_kind(self) -> dict[str, list[dict[str, object]]]:
        records: dict[str, list[dict[str, object]]] = {}
        for _, (_, data_rel, kind) in OBJECTS.items():
            document = json.loads((ROOT / data_rel).read_text(encoding="utf-8"))
            records[kind] = document["records"]
        return records

    def provenance_errors(self, mutate, mode: str | None = None) -> list[str]:
        records = self.records_by_kind()
        mutate(records)
        validation_mode = mode or os.environ.get("WP1_PROVENANCE_MODE", "full")
        return validate_references(records, root=ROOT, mode=validation_mode)

    def test_all_wp1_object_records_validate(self) -> None:
        mode = os.environ.get("WP1_PROVENANCE_MODE", "full")
        self.assertEqual(validate_repository(ROOT, mode=mode), [])

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

    def test_reader_display_layer_converts_people_mentions_labels_and_sources(self) -> None:
        bundle = json.loads((ROOT / "data/derived/wp1-site.json").read_text(encoding="utf-8"))
        story = bundle["stories"][0]
        reading = story["reading"]
        converter = OpenCC("t2s")
        people = {record["id"]: record for record in bundle["people"]}
        mentions = {record["id"]: record for record in bundle["mentions"]}
        sources = {record["id"]: record for record in bundle["sources"]}

        for person_id, person in people.items():
            display = reading["person_display"][person_id]
            self.assertEqual(display["name"]["original"], person["canonical_name"])
            self.assertEqual(display["name"]["simplified"], converter.convert(person["canonical_name"]))
            self.assertEqual(len(display["aliases"]), len(person["aliases"]))
            for display_alias, alias in zip(display["aliases"], person["aliases"]):
                self.assertEqual(display_alias["surface"]["original"], alias["surface"])
                self.assertEqual(display_alias["surface"]["simplified"], converter.convert(alias["surface"]))

        for mention_id, mention in mentions.items():
            display = reading["mention_display"][mention_id]["surface"]
            self.assertEqual(display["original"], mention["surface"])
            self.assertEqual(display["simplified"], converter.convert(mention["surface"]))

        self.assertEqual(reading["labels"]["resolved_mentions_heading"]["original"], "文中已解析的稱謂")
        self.assertEqual(reading["labels"]["resolved_mentions_heading"]["simplified"], "文中已解析的称谓")
        for source_id, source in sources.items():
            display = reading["source_display"][source_id]
            for field in ("work", "edition"):
                self.assertEqual(display[field]["original"], source[field])
                self.assertEqual(display[field]["simplified"], converter.convert(source[field]))

        # 郗/郄 remain textual distinctions; this layer only converts 鑒.
        self.assertEqual(reading["person_display"]["xi-jian"]["name"]["original"], "郗鑒")
        self.assertEqual(reading["person_display"]["xi-jian"]["name"]["simplified"], "郗鉴")
        self.assertNotIn("郄", reading["person_display"]["xi-jian"]["name"]["simplified"])

    def _punctuation_record(self) -> tuple[dict[str, object], dict[str, str]]:
        document = json.loads(
            (ROOT / "data/annotation/wp1-punctuation.json").read_text(encoding="utf-8")
        )
        record = deepcopy(document["records"][0])
        canonical = canonical_sections(
            ROOT / "content/processed/shishuo/entries/06-yaliang/entry-019.md"
        )
        return record, canonical

    def test_reviewed_punctuation_passes_canonical_round_trip(self) -> None:
        mode = os.environ.get("WP1_PROVENANCE_MODE", "full")
        self.assertEqual(validate_punctuation(ROOT, mode=mode), [])

    def _punctuation_reference(self) -> dict[str, object]:
        document = json.loads(
            (ROOT / "data/annotation/wp1-punctuation.json").read_text(encoding="utf-8")
        )
        return deepcopy(
            next(
                reference
                for reference in document["records"][0]["references"]
                if reference["witness_id"] == "shishuo-wikisource-sbck"
            )
        )

    def _punctuation_lock_root(self) -> tuple[tempfile.TemporaryDirectory, dict[str, object]]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        lock_path = root / "sources/downloads/shishuo/wikisource-sbck/manifest.lock.json"
        lock_path.parent.mkdir(parents=True)
        shutil.copy2(
            ROOT / "sources/downloads/shishuo/wikisource-sbck/manifest.lock.json",
            lock_path,
        )
        return temporary, self._punctuation_reference()

    def test_full_punctuation_reference_mode_requires_physical_file(self) -> None:
        temporary, reference = self._punctuation_lock_root()
        try:
            errors = validate_punctuation_reference(
                Path(temporary.name),
                reference,
                label="test punctuation reference",
                mode="full",
                trusted_records=None,
            )
            self.assertTrue(any("file does not exist" in error for error in errors))
        finally:
            temporary.cleanup()

    def test_portable_punctuation_reference_uses_committed_lock(self) -> None:
        temporary, reference = self._punctuation_lock_root()
        try:
            self.assertEqual(
                validate_punctuation_reference(
                    Path(temporary.name),
                    reference,
                    label="test punctuation reference",
                    mode="portable",
                    trusted_records=None,
                ),
                [],
            )
        finally:
            temporary.cleanup()

    def test_portable_punctuation_reference_rejects_wrong_hash_path_and_witness(self) -> None:
        temporary, reference = self._punctuation_lock_root()
        try:
            for field, value in (
                ("sha256", "0" * 64),
                ("path", "sources/downloads/shishuo/wikisource-sbck/pages/missing.wikitext"),
                ("witness_id", "wrong-witness"),
            ):
                mutated = deepcopy(reference)
                mutated[field] = value
                errors = validate_punctuation_reference(
                    Path(temporary.name),
                    mutated,
                    label=f"test punctuation reference {field}",
                    mode="portable",
                    trusted_records=None,
                )
                self.assertTrue(errors, field)
        finally:
            temporary.cleanup()

    def test_punctuation_inserting_character_is_rejected(self) -> None:
        record, canonical = self._punctuation_record()
        record["sections"]["main_text"]["punctuated_text"] += "王"
        errors = validate_punctuation_round_trip(record, canonical)
        self.assertTrue(any("round-trip" in error for error in errors))

    def test_punctuation_deleting_character_is_rejected(self) -> None:
        record, canonical = self._punctuation_record()
        punctuated = record["sections"]["main_text"]["punctuated_text"]
        record["sections"]["main_text"]["punctuated_text"] = punctuated.replace("郗", "", 1)
        errors = validate_punctuation_round_trip(record, canonical)
        self.assertTrue(any("round-trip" in error for error in errors))

    def test_punctuation_variant_substitution_is_rejected(self) -> None:
        record, canonical = self._punctuation_record()
        punctuated = record["sections"]["main_text"]["punctuated_text"]
        record["sections"]["main_text"]["punctuated_text"] = punctuated.replace("郗", "郄", 1)
        errors = validate_punctuation_round_trip(record, canonical)
        self.assertTrue(any("round-trip" in error for error in errors))

    def test_punctuation_round_trip_failures_are_mode_independent(self) -> None:
        document = json.loads(
            (ROOT / "data/annotation/wp1-punctuation.json").read_text(encoding="utf-8")
        )
        document["records"][0]["sections"]["main_text"]["punctuated_text"] = (
            document["records"][0]["sections"]["main_text"]["punctuated_text"].replace("郗", "郄", 1)
        )
        original_read_json = validate_wp1_module.read_json

        def read_json_with_mutated_punctuation(path: Path):
            if path == ROOT / "data/annotation/wp1-punctuation.json":
                return document
            return original_read_json(path)

        with patch.object(
            validate_wp1_module,
            "read_json",
            side_effect=read_json_with_mutated_punctuation,
        ):
            for mode in ("full", "portable"):
                errors = validate_punctuation(ROOT, mode=mode)
                self.assertTrue(any("round-trip" in error for error in errors), mode)

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

    def test_full_mode_fails_when_required_source_is_absent(self) -> None:
        def mutate(records):
            evidence = next(item for item in records["evidence"] if item["id"] == "evidence-001")
            evidence["locator"]["source_provenance"]["source_path"] = (
                "shishuoSources/shishuo/does-not-exist.txt"
            )

        records = self.records_by_kind()
        mutate(records)
        errors = validate_references(records, root=ROOT, mode="full")
        self.assertTrue(any("source_path: file does not exist" in error for error in errors))

    def _portable_lock_root(self) -> tuple[tempfile.TemporaryDirectory, dict[str, str]]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "sources/registry").mkdir(parents=True)
        shutil.copy2(
            ROOT / "sources/registry/shishuo-provenance.lock.json",
            root / "sources/registry/shishuo-provenance.lock.json",
        )
        (root / "sources/registry/shishuo.yaml").write_text("schema: 1\n", encoding="utf-8")
        provenance = {
            "witness_id": "shishuo-kanripo-wyg",
            "source_path": "shishuoSources/shishuo/KR3l0002_002.txt",
            "source_sha256": "6b8a3fcf4fb07152c567a25fe56e9511f45a9748b83c107e6a8956aa7e65367a",
        }
        return temporary, provenance

    def test_portable_mode_accepts_missing_ignored_source_from_trusted_lock(self) -> None:
        temporary, provenance = self._portable_lock_root()
        try:
            self.assertEqual(
                validate_source_provenance(
                    Path(temporary.name),
                    provenance,
                    label="test source",
                    mode="portable",
                ),
                [],
            )
        finally:
            temporary.cleanup()

    def test_portable_mode_rejects_wrong_missing_source_hash(self) -> None:
        temporary, provenance = self._portable_lock_root()
        try:
            provenance["source_sha256"] = "0" * 64
            errors = validate_source_provenance(
                Path(temporary.name), provenance, label="test source", mode="portable"
            )
            self.assertTrue(any("source_sha256 does not match committed trusted metadata" in error for error in errors))
        finally:
            temporary.cleanup()

    def test_portable_mode_rejects_wrong_missing_source_witness(self) -> None:
        temporary, provenance = self._portable_lock_root()
        try:
            provenance["witness_id"] = "wrong-witness"
            errors = validate_source_provenance(
                Path(temporary.name), provenance, label="test source", mode="portable"
            )
            self.assertTrue(any("witness_id does not match committed trusted metadata" in error for error in errors))
        finally:
            temporary.cleanup()

    def test_portable_mode_rejects_unknown_missing_source_path(self) -> None:
        temporary, provenance = self._portable_lock_root()
        try:
            provenance["source_path"] = "shishuoSources/shishuo/unknown.txt"
            errors = validate_source_provenance(
                Path(temporary.name), provenance, label="test source", mode="portable"
            )
            self.assertTrue(any("no committed trusted provenance record" in error for error in errors))
        finally:
            temporary.cleanup()

    def test_portable_mode_never_allows_missing_artifact_payload(self) -> None:
        def mutate(records):
            evidence = next(item for item in records["evidence"] if item["id"] == "evidence-004")
            evidence["locator"]["artifact_path"] = "content/processed/jinshu/units/missing.md"

        records = self.records_by_kind()
        mutate(records)
        errors = validate_references(records, root=ROOT, mode="portable")
        self.assertTrue(any("artifact_path: file does not exist" in error for error in errors))

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
