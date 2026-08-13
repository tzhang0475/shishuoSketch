from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.person_identity_discovery import OCCURRENCES_PATH, OUTPUT_PATH
from scripts.validate_person_identity_candidates import (
    KANRIPO_SHISHUO_PREFIX,
    validate,
    validate_primary_shishuo_lock_coverage,
)
from scripts.validate_wp1 import _trusted_source_records, validate_source_provenance


ROOT = Path(__file__).resolve().parents[1]


class PersonIdentityDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads((ROOT / OUTPUT_PATH).read_text(encoding="utf-8"))
        cls.occurrence_document = json.loads(
            (ROOT / OCCURRENCES_PATH).read_text(encoding="utf-8")
        )
        cls.people = json.loads((ROOT / "data/people.json").read_text(encoding="utf-8"))["people"]

    def test_artifacts_validate_in_portable_mode(self) -> None:
        self.assertEqual(validate(ROOT, mode="portable"), [])

    def test_all_primary_shishuo_evidence_paths_have_trusted_lock_coverage(self) -> None:
        evidence = self.document["evidence"]
        references = {
            (
                row["locator"]["source_provenance"]["source_path"],
                row["locator"]["source_provenance"]["witness_id"],
                row["locator"]["source_provenance"]["source_sha256"],
            )
            for row in evidence
            if row.get("locator", {}).get("source_provenance", {}).get("source_path", "").startswith(
                KANRIPO_SHISHUO_PREFIX
            )
        }
        self.assertTrue(references)
        lock_errors: list[str] = []
        trusted = _trusted_source_records(ROOT, lock_errors)
        self.assertEqual(lock_errors, [])
        self.assertEqual(
            validate_primary_shishuo_lock_coverage(
                ROOT,
                evidence,
                trusted_records=trusted,
            ),
            [],
        )
        for source_path, witness_id, source_sha256 in sorted(references):
            matches = [
                record
                for record in trusted.get(source_path, [])
                if record.get("witness_id") == witness_id and record.get("source_sha256") == source_sha256
            ]
            self.assertEqual(len(matches), 1, source_path)
            local_payload = ROOT / source_path
            if local_payload.is_file():
                digest = hashlib.sha256(local_payload.read_bytes()).hexdigest()
                self.assertEqual(digest, source_sha256)

    def test_portable_kanripo_lock_coverage_does_not_require_local_payload(self) -> None:
        source_path = "shishuoSources/shishuo/KR3l0002_001.txt"
        trusted = _trusted_source_records(ROOT, [])
        record = dict(trusted[source_path][0])
        record["registry_path"] = None
        provenance = {
            "source_path": source_path,
            "source_sha256": record["source_sha256"],
            "witness_id": record["witness_id"],
        }
        with tempfile.TemporaryDirectory() as temporary:
            errors = validate_source_provenance(
                Path(temporary),
                provenance,
                label="test Kanripo source",
                mode="portable",
                trusted_records={source_path: [record]},
            )
        self.assertEqual(errors, [])

    def test_all_committed_derived_primary_shishuo_paths_have_trusted_lock_coverage(self) -> None:
        """Keep future derived artifacts from bypassing the Kanripo lock baseline."""
        records: list[dict[str, object]] = []

        def collect(value: object, where: str) -> None:
            if isinstance(value, dict):
                provenance = value.get("source_provenance")
                if isinstance(provenance, dict) and str(provenance.get("source_path", "")).startswith(
                    KANRIPO_SHISHUO_PREFIX
                ):
                    records.append({"id": where, "locator": {"source_provenance": provenance}})
                for key, child in value.items():
                    collect(child, f"{where}.{key}")
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    collect(child, f"{where}[{index}]")

        derived_paths = subprocess.check_output(
            ["git", "ls-files", "data/derived"],
            cwd=ROOT,
            text=True,
        ).splitlines()
        for relative in derived_paths:
            if not relative.endswith(".json"):
                continue
            collect(json.loads((ROOT / relative).read_text(encoding="utf-8")), relative)

        self.assertTrue(records)
        lock_errors: list[str] = []
        trusted = _trusted_source_records(ROOT, lock_errors)
        self.assertEqual(lock_errors, [])
        self.assertEqual(
            validate_primary_shishuo_lock_coverage(
                ROOT,
                records,
                trusted_records=trusted,
            ),
            [],
        )

    def test_missing_primary_shishuo_lock_record_is_rejected(self) -> None:
        evidence = self.document["evidence"]
        lock_errors: list[str] = []
        trusted = _trusted_source_records(ROOT, lock_errors)
        self.assertEqual(lock_errors, [])
        path = next(
            row["locator"]["source_provenance"]["source_path"]
            for row in evidence
            if row.get("locator", {}).get("source_provenance", {}).get("source_path", "").startswith(
                KANRIPO_SHISHUO_PREFIX
            )
        )
        mutated = {key: value for key, value in trusted.items() if key != path}
        errors = validate_primary_shishuo_lock_coverage(
            ROOT,
            evidence,
            trusted_records=mutated,
        )
        self.assertTrue(any(path in error for error in errors))

    def test_wikisource_sbck_lock_availability_is_required_in_portable_mode(self) -> None:
        sbck_evidence = next(
            row
            for row in self.document["evidence"]
            if "sources/downloads/shishuo/wikisource-sbck/" in row["locator"]["source_provenance"].get("source_path", "")
        )
        provenance = dict(sbck_evidence["locator"]["source_provenance"])
        source_path = provenance["source_path"]
        lock_errors: list[str] = []
        trusted = _trusted_source_records(ROOT, lock_errors)
        self.assertEqual(lock_errors, [])
        record = dict(trusted[source_path][0])
        record["registry_path"] = None

        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(
                validate_source_provenance(
                    Path(temporary),
                    provenance,
                    label="test Wikisource-SBCK source",
                    mode="portable",
                    trusted_records={source_path: [record]},
                ),
                [],
            )
            without_availability = dict(record)
            without_availability.pop("availability", None)
            errors = validate_source_provenance(
                Path(temporary),
                provenance,
                label="test Wikisource-SBCK source without availability",
                mode="portable",
                trusted_records={source_path: [without_availability]},
            )
        self.assertTrue(any("not explicitly registered" in error for error in errors))

    def test_discovery_is_open_world_and_excludes_materialized_people(self) -> None:
        candidates = self.document["candidates"]
        self.assertGreater(self.document["discovery_counts"]["candidate_identity_count"], 0)
        materialized = [row for row in candidates if row["status"] == "already_materialized"]
        self.assertEqual(len(materialized), len(self.people))
        self.assertTrue(all(row["materialization_state"] == "already_materialized" for row in materialized))
        self.assertTrue(
            all(row["materialization_state"] == "new_candidate" for row in candidates if row not in materialized)
        )

    def test_explicit_jinshu_identity_seed_clusters_name_and_contextual_surface(self) -> None:
        桓溫 = next(row for row in self.document["candidates"] if row["preferred_name"] == "桓溫")
        self.assertIn(桓溫["status"], {"strong_candidate", "already_materialized"})
        if 桓溫["status"] == "already_materialized":
            self.assertEqual(桓溫["matched_person_id"], "huan-wen")
        surfaces = {row["surface"]: row for row in 桓溫["surfaces"]}
        self.assertEqual(surfaces["桓溫"]["association_mode"], "exact")
        self.assertEqual(surfaces["桓公"]["association_mode"], "contextual")
        self.assertIn("structured_jinshu_biography_subject", 桓溫["identity_basis"])

    def test_generic_title_is_not_a_person_candidate(self) -> None:
        preferred_names = {row["preferred_name"] for row in self.document["candidates"]}
        unresolved = {row["surface"]: row for row in self.document["unresolved_surface_clusters"]}
        self.assertNotIn("太傅", preferred_names)
        self.assertIn("太傅", unresolved)
        self.assertTrue(unresolved["太傅"]["not_ranked_as_person"])

    def test_current_story_gap_is_open_world_audit(self) -> None:
        gaps = self.document["current_sc1_open_world_gaps"]
        self.assertTrue(gaps)
        wang_tanzhi = [
            candidate
            for gap in gaps
            for candidate in gap["candidates"]
            if candidate["preferred_name"] == "王坦之"
        ]
        self.assertTrue(wang_tanzhi)
        self.assertIn("main_text", wang_tanzhi[0]["sections"])

    def test_strong_corpus_identity_outside_current_stories_keeps_zero_current_coverage(self) -> None:
        meng_jia = next(row for row in self.document["candidates"] if row["preferred_name"] == "孟嘉")
        self.assertEqual(meng_jia["status"], "strong_candidate")
        self.assertGreater(meng_jia["metrics"]["shishuo_main_story_count"], 0)
        self.assertEqual(meng_jia["metrics"]["current_sc1_story_count"], 0)

    def test_contextual_surface_never_becomes_an_exact_identity_alias(self) -> None:
        huan_wen = next(row for row in self.document["candidates"] if row["preferred_name"] == "桓溫")
        huan_gong = next(row for row in huan_wen["surfaces"] if row["surface"] == "桓公")
        self.assertEqual(huan_gong["association_mode"], "contextual")
        self.assertNotEqual(huan_gong["surface_type"], "personal_name")

    def test_source_layers_and_occurrences_remain_separate(self) -> None:
        occurrences = self.occurrence_document["occurrences"]
        self.assertTrue(any(row["section"] == "main_text" for row in occurrences))
        self.assertTrue(any(row["section"] == "liu_annotation" for row in occurrences))
        self.assertTrue(all("person_id" not in row for row in occurrences))
        self.assertTrue(all(row["association_mode"] in {"exact", "contextual", "ambiguous"} for row in occurrences))

    def test_candidate_ids_and_surface_order_are_deterministic(self) -> None:
        candidate_keys = [(row["preferred_name"], row["candidate_id"]) for row in self.document["candidates"]]
        self.assertEqual(candidate_keys, sorted(candidate_keys))
        for candidate in self.document["candidates"]:
            surfaces = candidate["surfaces"]
            self.assertEqual(
                [(row["surface"], row["surface_type"]) for row in surfaces],
                [(row["surface"], row["surface_type"]) for row in sorted(
                    surfaces,
                    key=lambda row: (
                        {"personal_name": 0, "courtesy_name": 1, "surname_plus_courtesy_name": 2}.get(row["surface_type"], 9),
                        row["surface"],
                    )
                )],
            )


if __name__ == "__main__":
    unittest.main()
