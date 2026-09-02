from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.validate_sc1_frontend_data import (
    collect_sc1_source_provenance,
    validate,
    validate_sc1_source_provenance_coverage,
)
from scripts.validate_wp1 import _trusted_source_records
from tests.support import repository_validation_mode


ROOT = Path(__file__).resolve().parents[1]


class SC1StoryChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = json.loads((ROOT / "data/derived/sc1-current-site.json").read_text(encoding="utf-8"))
        cls.gold = json.loads((ROOT / "data/story-chain-gold-set.json").read_text(encoding="utf-8"))
        cls.base = json.loads((ROOT / "data/derived/wp1-site.json").read_text(encoding="utf-8"))

    def test_sc1_bundle_publishes_the_sc0_union_of_the_frozen_expansion_manifests(self) -> None:
        self.assertEqual(validate(ROOT, mode=repository_validation_mode()), [])
        expected = [item["entry_id"] for item in self.gold["records"]]
        expansion = json.loads(
            (ROOT / "data/annotation/story-expansion-wave-1.json").read_text(encoding="utf-8")
        )
        expected.extend(item["story_id"] for item in expansion["records"])
        w3_expansion = json.loads(
            (ROOT / "data/annotation/story-expansion-wave-3.json").read_text(encoding="utf-8")
        )
        expected.extend(item["story_id"] for item in w3_expansion["records"])
        w4_path = ROOT / "data/annotation/story-expansion-wave-4.json"
        if w4_path.is_file():
            w4_expansion = json.loads(w4_path.read_text(encoding="utf-8"))
            expected.extend(item["story_id"] for item in w4_expansion["records"])
        expected.sort(
            key=lambda story_id: next(
                story["global_ordinal"]
                for story in self.bundle["stories"]
                if story["id"] == story_id
            )
        )
        self.assertEqual(self.bundle["story_chain"]["story_ids"], expected)
        self.assertEqual([item["id"] for item in self.bundle["stories"]], expected)

    def test_every_sc1_source_path_has_trusted_portable_coverage(self) -> None:
        references = collect_sc1_source_provenance(self.bundle)
        self.assertTrue(references)
        self.assertEqual(
            validate_sc1_source_provenance_coverage(ROOT, self.bundle, mode="portable"),
            [],
        )
        lock_errors: list[str] = []
        trusted = _trusted_source_records(ROOT, lock_errors)
        self.assertEqual(lock_errors, [])
        for witness_id, source_path, source_sha256 in references:
            matches = trusted.get(source_path, [])
            self.assertTrue(
                any(
                    item.get("witness_id") == witness_id
                    and item.get("source_sha256") == source_sha256
                    for item in matches
                ),
                source_path,
            )

    def _kanripo_source_bundle(self) -> tuple[dict[str, object], dict[str, object]]:
        evidence = next(
            item
            for item in self.bundle["evidence"]
            if item["locator"].get("source_provenance", {}).get("source_path", "").endswith("KR3l0002_001.txt")
        )
        provenance = deepcopy(evidence["locator"]["source_provenance"])
        bundle = {
            "sources": [{"id": evidence["source_id"], "witness_id": provenance["witness_id"]}],
            "evidence": [{
                "id": evidence["id"],
                "source_id": evidence["source_id"],
                "locator": {"source_provenance": provenance},
            }],
        }
        return bundle, provenance

    def _portable_lock_root(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        registry = root / "sources/registry"
        registry.mkdir(parents=True)
        shutil.copy2(
            ROOT / "sources/registry/shishuo-provenance.lock.json",
            registry / "shishuo-provenance.lock.json",
        )
        shutil.copy2(ROOT / "sources/registry/shishuo.yaml", registry / "shishuo.yaml")
        return temporary, root

    def test_portable_sc1_accepts_missing_ignored_kanripo_payload_from_lock(self) -> None:
        bundle, _provenance = self._kanripo_source_bundle()
        temporary, root = self._portable_lock_root()
        try:
            self.assertEqual(validate_sc1_source_provenance_coverage(root, bundle, mode="portable"), [])
        finally:
            temporary.cleanup()

    def test_sc1_source_provenance_rejects_missing_lock_path(self) -> None:
        bundle, provenance = self._kanripo_source_bundle()
        provenance["source_path"] = "shishuoSources/shishuo/unknown.txt"
        temporary, root = self._portable_lock_root()
        try:
            errors = validate_sc1_source_provenance_coverage(root, bundle, mode="portable")
            self.assertTrue(any("no committed trusted provenance record" in error for error in errors))
        finally:
            temporary.cleanup()

    def test_sc1_source_provenance_rejects_wrong_hash(self) -> None:
        bundle, provenance = self._kanripo_source_bundle()
        provenance["source_sha256"] = "0" * 64
        temporary, root = self._portable_lock_root()
        try:
            errors = validate_sc1_source_provenance_coverage(root, bundle, mode="portable")
            self.assertTrue(any("source_sha256 does not match committed trusted metadata" in error for error in errors))
        finally:
            temporary.cleanup()

    def test_sc1_source_provenance_rejects_wrong_witness(self) -> None:
        bundle, provenance = self._kanripo_source_bundle()
        provenance["witness_id"] = "wrong-witness"
        temporary, root = self._portable_lock_root()
        try:
            errors = validate_sc1_source_provenance_coverage(root, bundle, mode="portable")
            self.assertTrue(any("witness_id" in error for error in errors))
        finally:
            temporary.cleanup()

    def test_sc1_full_mode_requires_physical_source_payload(self) -> None:
        bundle, _provenance = self._kanripo_source_bundle()
        temporary, root = self._portable_lock_root()
        try:
            errors = validate_sc1_source_provenance_coverage(root, bundle, mode="full")
            self.assertTrue(any("source_path: file does not exist" in error for error in errors))
        finally:
            temporary.cleanup()

    def test_publication_state_does_not_change_editorial_punctuation_status(self) -> None:
        stories = {item["id"]: item for item in self.bundle["stories"]}
        punctuation = {
            item["entry_id"]: item
            for item in json.loads((ROOT / "data/annotation/wp1-punctuation.json").read_text(encoding="utf-8"))["records"]
        }
        self.assertEqual(stories["06-yaliang-019"]["publication_state"], "production_ready")
        self.assertEqual(punctuation["06-yaliang-019"]["review_status"], "reviewed")
        self.assertEqual(punctuation["06-yaliang-019"]["punctuation_basis"], "human_reviewed")
        for story in self.bundle["stories"]:
            if story["id"] == "06-yaliang-019":
                continue
            self.assertEqual(story["publication_state"], "preview_ready")
            self.assertEqual(punctuation[story["id"]]["review_status"], "unreviewed")
            self.assertEqual(punctuation[story["id"]]["punctuation_basis"], "reference_candidate")

    def test_person_story_projection_uses_sc0_links_and_separates_annotation_only(self) -> None:
        refs = {item["person_id"]: item for item in self.bundle["story_chain"]["person_story_refs"]}
        frozen_sc0_refs = {
            "02-yanyu-069", "04-wenxue-036", "06-yaliang-019",
            "14-rongzhi-024", "19-xianyuan-026",
        }
        # The M2 frontend projection extends the frozen SC0 references with
        # published expansion Stories; SC0 itself remains the regression
        # gold set and must still be wholly represented here.
        self.assertTrue(frozen_sc0_refs <= set(refs["person-001"]["story_ids"]))
        published = {story["id"] for story in self.bundle["stories"]}
        self.assertTrue(set(refs["person-001"]["story_ids"]) <= published)
        self.assertEqual(refs["person-007"]["main_text_story_ids"], [])
        self.assertEqual(refs["person-007"]["liu_annotation_only_story_ids"], ["06-yaliang-019"])
        self.assertIn("25-paidiao-026", refs["person-005"]["liu_annotation_only_story_ids"])

    def test_shared_wp1_person_relation_source_records_are_unchanged(self) -> None:
        # P3B intentionally extends the SC1 Person projection and R3B now
        # extends the production Relation registry. The WP1 sample's existing
        # seven Person and Relation records remain byte-stable.
        base_people = {item["id"]: item for item in self.base["people"]}
        current_people = {item["id"]: item for item in self.bundle["people"]}
        self.assertTrue(set(base_people) <= set(current_people))
        for person_id, person in base_people.items():
            self.assertEqual(current_people[person_id], person)
        base_relations = {item["id"]: item for item in self.base["relations"]}
        current_relations = {item["id"]: item for item in self.bundle["relations"]}
        for relation_id, relation in base_relations.items():
            self.assertEqual(current_relations.get(relation_id), relation, relation_id)
        for key in ("sources", "eras"):
            self.assertEqual(self.bundle[key], self.base[key], key)
        self.assertEqual(
            {item["id"] for item in self.base["relations"]},
            {
                "relation-001",
                "relation-gold-001",
                "relation-gold-002",
                "relation-gold-003",
                "relation-gold-004",
                "relation-gold-005",
                "relation-gold-006",
            },
        )
        self.assertEqual(
            {item["id"] for item in self.bundle["relations"] if item["id"].startswith("relation-r3b-")},
            {f"relation-r3b-{index:03d}" for index in range(1, 6)},
        )

    def test_story_and_person_navigation_contract_is_data_driven(self) -> None:
        app = (ROOT / "site/src/App.tsx").read_text(encoding="utf-8")
        self.assertIn("appendExploration", app)
        self.assertIn("backExploration", app)
        self.assertIn("PersonStories", app)
        self.assertIn("story_chain?.person_story_refs", app)
        self.assertNotIn("25-paidiao-026", app)
        self.assertNotIn("王羲之", app)

    def test_r2_relation_basis_remains_direct_vs_derived(self) -> None:
        relations = {item["id"]: item for item in self.bundle["relations"]}
        direct = [item for item in relations.values() if item["review_status"] == "reviewed" and item["relation_basis"] == "direct"]
        self.assertEqual(len(direct), 11)
        self.assertEqual(
            sum(
                item["review_status"] == "reviewed"
                and item["relation_basis"] == "direct"
                and not item["id"].startswith("relation-r3b-")
                for item in relations.values()
            ),
            6,
        )
        self.assertEqual(relations["relation-001"]["relation_basis"], "derived")
        self.assertEqual(relations["relation-001"]["derived_from_relation_ids"], ["relation-gold-006", "relation-gold-005"])


if __name__ == "__main__":
    unittest.main()
