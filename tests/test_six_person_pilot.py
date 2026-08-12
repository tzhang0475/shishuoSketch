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

    def test_only_the_six_target_people_are_registered(self) -> None:
        expected = {
            "wang-xizhi",
            "xi-jian",
            "wang-dao",
            "wang-ningzhi",
            "xie-daoyun",
            "xie-an",
        }
        actual = {person["person_id"] for person in self.people["people"]}
        self.assertEqual(actual, expected)

    def test_aliases_have_source_evidence_and_preserve_orthographic_variant(self) -> None:
        records = {alias["alias_id"]: alias for alias in self.aliases["aliases"]}
        self.assertIn("xi-jian-variant-name", records)
        self.assertEqual(records["xi-jian-variant-name"]["surface"], "郄鑒")
        self.assertTrue(records["xi-jian-variant-name"]["source_evidence"])
        self.assertTrue(all(alias["source_evidence"] for alias in records.values()))

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
            "wang-xizhi": "080-liezhuan-001",
            "xi-jian": "067-liezhuan-002",
            "wang-dao": "065-liezhuan-001",
            "xie-an": "079-liezhuan-002",
            "xie-daoyun": "096-liezhuan-016",
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
        with tempfile.TemporaryDirectory() as temporary:
            generated = build_outputs(
                root=Path(temporary),
                shishuo_root=self.root / "content/processed/shishuo/entries",
                jinshu_root=self.root / "content/processed/jinshu/units",
            )
        self.assertEqual(generated["people"], self.people)
        self.assertEqual(generated["aliases"], self.aliases)
        self.assertEqual(generated["shishuo"], self.shishuo)
        self.assertEqual(generated["jinshu"], self.jinshu)

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
