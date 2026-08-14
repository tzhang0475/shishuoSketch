from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from scripts.person_relation_review_r3b import project, validate_source
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]


class PersonRelationReviewR3BTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.decisions = json.loads((ROOT / "data/annotation/person-relation-review-r3b.json").read_text(encoding="utf-8"))
        cls.projection = json.loads((ROOT / "data/derived/person-relations-r3b.json").read_text(encoding="utf-8"))
        cls.relations = json.loads((ROOT / "data/annotation/wp1-relations.json").read_text(encoding="utf-8"))["records"]
        cls.bundle = json.loads((ROOT / "data/derived/sc1-site.json").read_text(encoding="utf-8"))

    def test_review_file_is_complete_and_schema_valid(self) -> None:
        schema = json.loads((ROOT / "schema/person-relation-review-r3b.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(self.decisions)), [])
        self.assertEqual(validate_source(ROOT), [])
        self.assertEqual(len(self.decisions["records"]), 7)

    def test_only_approved_decisions_materialize(self) -> None:
        self.assertEqual(self.projection["approved_count"], 5)
        self.assertEqual(self.projection["deferred_count"], 2)
        materialized = {item["id"] for item in self.projection["materialized_relations"]}
        self.assertEqual(materialized, {f"relation-r3b-{index:03d}" for index in range(1, 6)})
        production = {item["id"] for item in self.relations}
        self.assertTrue(materialized <= production)
        deferred_ids = {
            item["candidate_id"] for item in self.decisions["records"] if item["decision"] == "deferred"
        }
        self.assertFalse(
            deferred_ids & {item.get("source_candidate_id") for item in self.relations if item.get("source_candidate_id")}
        )

    def test_materialized_relation_semantics_are_bounded_and_evidence_backed(self) -> None:
        evidence_ids = {item["id"] for item in self.bundle["evidence"]}
        by_id = {item["id"]: item for item in self.projection["materialized_relations"]}
        for relation in by_id.values():
            self.assertEqual(relation["review_status"], "reviewed")
            self.assertEqual(relation["relation_basis"], "direct")
            self.assertTrue(set(relation["evidence_ids"]) <= evidence_ids)
            self.assertIn(relation["subject_id"], {person["id"] for person in self.bundle["people"]})
            self.assertIn(relation["object_id"], {person["id"] for person in self.bundle["people"]})
        for relation_id in ("relation-r3b-004", "relation-r3b-005"):
            relation = by_id[relation_id]
            self.assertEqual(relation["relation_type"], "political")
            self.assertEqual(relation["relation_scope"], "event_bounded")
            self.assertEqual(relation["scope_event"], "蘇峻之亂")

    def test_scene_political_counterposition_does_not_create_relation(self) -> None:
        scene = json.loads((ROOT / "data/derived/story-scene-contexts.json").read_text(encoding="utf-8"))["contexts"]["05-fangzheng-031"]
        self.assertTrue(any(item["classification"] == "political_counterposition" for item in scene["positional_context"]))
        pair = {"person-019", "person-011"}
        self.assertFalse(
            any({relation["subject_id"], relation["object_id"]} == pair for relation in self.relations)
        )

    def test_r3b_projection_is_deterministic(self) -> None:
        first = project(ROOT)
        second = project(ROOT)
        encoded_first = json.dumps(first, ensure_ascii=False, sort_keys=True).encode("utf-8")
        encoded_second = json.dumps(second, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.assertEqual(encoded_first, encoded_second)
        self.assertEqual(hashlib.sha256(encoded_first).hexdigest(), hashlib.sha256(encoded_second).hexdigest())


if __name__ == "__main__":
    unittest.main()
