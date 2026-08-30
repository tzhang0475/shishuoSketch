from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.build_six_person_pilot import REPOSITORY_ROOT, build_outputs
from tests.support import skip_if_portable_payload_missing


class SixPersonPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = REPOSITORY_ROOT
        cls.people = json.loads((cls.root / "data/people.json").read_text(encoding="utf-8"))
        cls.aliases = json.loads((cls.root / "data/aliases.json").read_text(encoding="utf-8"))
        cls.shishuo = json.loads(
            (cls.root / "data/mentions/shishuo.json").read_text(encoding="utf-8")
        )
        cls.jinshu = json.loads(
            (cls.root / "data/mentions/jinshu.json").read_text(encoding="utf-8")
        )

    def test_six_primary_people_and_explicit_r1_supporting_person_are_registered(self) -> None:
        expected = {
            "person-001",
            "person-002",
            "person-003",
            "person-004",
            "person-005",
            "person-006",
        }
        primary = {
            person["person_id"]
            for person in self.people["people"]
            if person.get("scope_role") == "primary"
        }
        supporting = {
            person["person_id"]
            for person in self.people["people"]
            if person.get("scope_role") == "supporting"
        }
        self.assertTrue(expected <= primary)
        self.assertEqual(
            {
                person["person_id"]
                for person in self.people["people"]
                if isinstance(person.get("materialization"), dict)
                and person["materialization"].get("wave_id") == "p3b-wave-1"
            },
            {
                "person-008",
                "person-009",
                "person-010",
                "person-011",
                "person-012",
                "person-013",
                "person-014",
                "person-015",
                "person-016",
                "person-017",
            },
        )
        self.assertEqual(supporting, {"person-007"})

    def test_aliases_have_source_evidence_and_preserve_orthographic_variant(self) -> None:
        records = {alias["alias_id"]: alias for alias in self.aliases["aliases"]}
        self.assertIn("xi-jian-variant-name", records)
        self.assertEqual(records["xi-jian-variant-name"]["surface"], "郄鑒")
        self.assertTrue(records["xi-jian-variant-name"]["source_evidence"])
        # SFH2R may retain an explicitly suppressed wrong-bearer alias row for
        # provenance.  It is not an active alias and therefore intentionally
        # has an empty source_evidence list; active rows remain provenance-
        # complete.
        self.assertTrue(
            all(
                alias["source_evidence"]
                or alias.get("status") in {"suppressed_wrong_bearer", "collective_reference"}
                for alias in records.values()
            )
        )

    def test_shishuo_sections_and_jinshu_biography_scopes_are_explicit(self) -> None:
        self.assertEqual(self.shishuo["scanned_entry_count"], 1130)
        self.assertEqual(self.jinshu["scanned_unit_count"], 631)
        self.assertTrue(self.shishuo["mentions"])
        self.assertTrue(
            all(mention["section"] in {"main_text", "liu_annotation"} for mention in self.shishuo["mentions"])
        )
        scopes = {mention["biography_scope"] for mention in self.jinshu["mentions"]}
        self.assertTrue(scopes <= {"own_biography", "other_biography", "other_unit"})
        own_units = {
            "person-001": "080-liezhuan-001",
            "person-002": "067-liezhuan-002",
            "person-003": "065-liezhuan-001",
            "person-006": "079-liezhuan-002",
            "person-005": "096-liezhuan-016",
        }
        for person_id, unit_id in own_units.items():
            self.assertTrue(
                any(
                    mention["person_id"] == person_id
                    and mention["unit_id"] == unit_id
                    and mention["biography_scope"] == "own_biography"
                    for mention in self.jinshu["mentions"]
                )
            )

    def test_resolved_mentions_are_in_scope_and_have_provenance(self) -> None:
        person_ids = {person["person_id"] for person in self.people["people"]}
        for document in (self.shishuo, self.jinshu):
            for mention in document["mentions"]:
                if mention["person_id"] is not None:
                    self.assertIn(mention["person_id"], person_ids)
                self.assertTrue(mention["context"])
                provenance = mention["evidence"]["provenance"]
                self.assertTrue(provenance["source_sha256"])
                self.assertTrue(provenance["source_path"])

    def test_contextual_titles_never_resolve_without_identity_evidence(self) -> None:
        for document in (self.shishuo, self.jinshu):
            for mention in document["mentions"]:
                if mention["alias_type"] in {"office_title", "contextual_title"}:
                    if mention["person_id"] is not None:
                        self.assertTrue(mention["context_identity_hits"])

    def test_source_hashes_in_mention_provenance_match_files(self) -> None:
        source_paths = {
            mention["evidence"]["provenance"]["source_path"]
            for document in (self.shishuo, self.jinshu)
            for mention in document["mentions"]
        }
        skip_if_portable_payload_missing(self, self.root, *sorted(source_paths))
        checked: dict[Path, str] = {}
        for document in (self.shishuo, self.jinshu):
            for mention in document["mentions"]:
                provenance = mention["evidence"]["provenance"]
                path = self.root / provenance["source_path"]
                self.assertTrue(path.is_file(), path)
                if path not in checked:
                    checked[path] = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(checked[path], provenance["source_sha256"])

    def test_generation_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            generated_first = build_outputs(
                root=Path(first),
                shishuo_root=self.root / "content/processed/shishuo/entries",
                jinshu_root=self.root / "content/processed/jinshu/units",
            )
            generated_second = build_outputs(
                root=Path(second),
                shishuo_root=self.root / "content/processed/shishuo/entries",
                jinshu_root=self.root / "content/processed/jinshu/units",
            )
        self.assertEqual(generated_first, generated_second)
        self.assertEqual(generated_first["people"]["stage"], "six-person-pilot")
        self.assertEqual(len(generated_first["people"]["people"]), 7)

    def test_legacy_builder_cannot_overwrite_materialized_registry(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "cannot overwrite a materialized"):
            build_outputs(
                root=self.root,
                shishuo_root=self.root / "content/processed/shishuo/entries",
                jinshu_root=self.root / "content/processed/jinshu/units",
            )

    def test_unresolved_mentions_are_retained_and_not_forced(self) -> None:
        unresolved = [
            mention
            for document in (self.shishuo, self.jinshu)
            for mention in document["mentions"]
            if mention["person_id"] is None
        ]
        self.assertTrue(unresolved)
        self.assertTrue(all(mention["confidence"] == "unresolved" for mention in unresolved))


if __name__ == "__main__":
    unittest.main()
