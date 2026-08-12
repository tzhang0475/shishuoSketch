from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from scripts.validate_wp1 import OBJECTS, validate_references, validate_repository


ROOT = Path(__file__).resolve().parents[1]


class RelationGoldPilotTests(unittest.TestCase):
    def records_by_kind(self) -> dict[str, list[dict[str, object]]]:
        records: dict[str, list[dict[str, object]]] = {}
        for _, (_, data_rel, kind) in OBJECTS.items():
            document = json.loads((ROOT / data_rel).read_text(encoding="utf-8"))
            records[kind] = document["records"]
        return records

    def errors_after(self, mutate) -> list[str]:
        records = deepcopy(self.records_by_kind())
        mutate(records)
        return validate_references(records, root=ROOT, mode="full")

    def test_reviewed_r1_relations_validate(self) -> None:
        self.assertEqual(validate_repository(ROOT, mode="full"), [])
        relations = json.loads(
            (ROOT / "data/annotation/wp1-relations.json").read_text(encoding="utf-8")
        )["records"]
        self.assertEqual(
            [record["id"] for record in relations if record["relation_basis"] == "direct"],
            [
                "relation-gold-001",
                "relation-gold-002",
                "relation-gold-003",
                "relation-gold-004",
                "relation-gold-005",
                "relation-gold-006",
            ],
        )

    def test_relation_001_is_the_single_reviewed_derived_relation(self) -> None:
        relations = json.loads(
            (ROOT / "data/annotation/wp1-relations.json").read_text(encoding="utf-8")
        )["records"]
        relation = next(item for item in relations if item["id"] == "relation-001")
        self.assertEqual(relation["review_status"], "reviewed")
        self.assertEqual(relation["assertion_status"], "inferred")
        self.assertEqual(relation["relation_basis"], "derived")
        self.assertEqual(
            relation["derived_from_relation_ids"],
            ["relation-gold-006", "relation-gold-005"],
        )
        self.assertEqual(relation["evidence_ids"], [])
        self.assertEqual(len(relations), 7)

    def test_supporting_bridge_person_is_evidence_backed(self) -> None:
        registry = json.loads((ROOT / "data/people.json").read_text(encoding="utf-8"))["people"]
        registry_bridge = next(person for person in registry if person["person_id"] == "person-007")
        self.assertEqual(registry_bridge["scope_role"], "supporting")
        self.assertTrue(registry_bridge["source_evidence"])
        people = json.loads(
            (ROOT / "data/annotation/wp1-people.json").read_text(encoding="utf-8")
        )["records"]
        self.assertEqual(
            {person["person_id"] for person in registry},
            {person["id"] for person in people},
        )
        bridge = next(person for person in people if person.get("scope_role") == "supporting")
        self.assertEqual(bridge["id"], "person-007")
        self.assertTrue(bridge["evidence_ids"])

    def test_self_relation_is_rejected(self) -> None:
        errors = self.errors_after(
            lambda records: records["relations"][1].__setitem__(
                "object_id", records["relations"][1]["subject_id"]
            )
        )
        self.assertTrue(any("must not connect a person to themself" in error for error in errors))

    def test_duplicate_reviewed_semantic_edge_is_rejected(self) -> None:
        def mutate(records):
            duplicate = deepcopy(next(item for item in records["relations"] if item["id"] == "relation-gold-003"))
            duplicate["id"] = "relation-gold-duplicate"
            records["relations"].append(duplicate)

        errors = self.errors_after(mutate)
        self.assertTrue(any("duplicate the same semantic edge" in error for error in errors))

    def test_incompatible_relation_roles_are_rejected(self) -> None:
        errors = self.errors_after(
            lambda records: records["relations"][3].__setitem__("role_a", "父")
        )
        self.assertTrue(any("incompatible relation subtype/roles" in error for error in errors))

    def test_reviewed_relation_without_evidence_is_rejected(self) -> None:
        errors = self.errors_after(
            lambda records: records["relations"][1].__setitem__("evidence_ids", [])
        )
        self.assertTrue(any("relation-gold-001" in error and "has no evidence_ids" in error for error in errors))

    def test_reviewed_relation_without_source_anchor_is_rejected(self) -> None:
        def mutate(records):
            relation = next(item for item in records["relations"] if item["id"] == "relation-gold-001")
            relation["source_unit_ids"] = []

        errors = self.errors_after(mutate)
        self.assertTrue(any("must identify at least one source" in error for error in errors))

    def test_nonexistent_relation_source_entry_is_rejected(self) -> None:
        def mutate(records):
            relation = next(item for item in records["relations"] if item["id"] == "relation-gold-005")
            relation["source_entry_ids"] = ["99-missing-001"]

        errors = self.errors_after(mutate)
        self.assertTrue(any("nonexistent Shishuo entry" in error for error in errors))

    def test_nonexistent_relation_source_unit_is_rejected(self) -> None:
        def mutate(records):
            relation = next(item for item in records["relations"] if item["id"] == "relation-gold-001")
            relation["source_unit_ids"] = ["999-liezhuan-999"]

        errors = self.errors_after(mutate)
        self.assertTrue(any("nonexistent Jinshu unit" in error for error in errors))

    def test_relation_endpoint_must_resolve_through_unified_registry(self) -> None:
        errors = self.errors_after(
            lambda records: records["relations"][1].__setitem__("subject_id", "person-999")
        )
        self.assertTrue(any("absent from unified Person registry" in error for error in errors))

    def test_editorial_or_cooccurrence_only_evidence_cannot_review_a_relation(self) -> None:
        def mutate(records):
            relation = next(item for item in records["relations"] if item["id"] == "relation-gold-001")
            relation["evidence_ids"] = ["evidence-003"]

        errors = self.errors_after(mutate)
        self.assertTrue(any("direct primary-text or annotation evidence" in error for error in errors))

    def test_derived_relation_with_direct_evidence_is_rejected(self) -> None:
        def mutate(records):
            relation = next(item for item in records["relations"] if item["id"] == "relation-001")
            relation["evidence_ids"] = ["evidence-002"]

        errors = self.errors_after(mutate)
        self.assertTrue(any("must not carry direct evidence_ids" in error for error in errors))

    def test_direct_relation_with_derivation_is_rejected(self) -> None:
        def mutate(records):
            relation = next(item for item in records["relations"] if item["id"] == "relation-gold-001")
            relation["derived_from_relation_ids"] = ["relation-gold-002"]

        errors = self.errors_after(mutate)
        self.assertTrue(any("cannot declare derived_from_relation_ids" in error for error in errors))

    def test_derived_relation_requires_reviewed_direct_sources(self) -> None:
        def mutate(records):
            source = next(item for item in records["relations"] if item["id"] == "relation-gold-006")
            source["review_status"] = "candidate"

        errors = self.errors_after(mutate)
        self.assertTrue(any("source Relation relation-gold-006 is not reviewed" in error for error in errors))

    def test_derived_edge_cannot_duplicate_an_atomic_direct_edge(self) -> None:
        def mutate(records):
            relation = next(item for item in records["relations"] if item["id"] == "relation-001")
            relation["subject_id"] = "xi-jian"
            relation["object_id"] = "person-007"
            relation["relation_type"] = "kinship"
            relation["relation_subtype"] = "parent_child"

        errors = self.errors_after(mutate)
        self.assertTrue(any("duplicate the same semantic edge" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
