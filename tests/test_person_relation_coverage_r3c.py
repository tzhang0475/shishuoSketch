from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from scripts.person_relation_coverage_r3c import (
    CANDIDATE_PATH,
    COVERAGE_PATH,
    detect_relation_hits,
    project,
    stable_candidate_id,
)
from scripts.validate_person_relation_coverage_r3c import validate


ROOT = Path(__file__).resolve().parents[1]


class PersonRelationCoverageR3CTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.coverage = json.loads((ROOT / COVERAGE_PATH).read_text(encoding="utf-8"))
        cls.candidates = json.loads((ROOT / CANDIDATE_PATH).read_text(encoding="utf-8"))
        cls.bundle = json.loads((ROOT / "data/derived/sc1-site.json").read_text(encoding="utf-8"))
        cls.relations = json.loads((ROOT / "data/annotation/wp1-relations.json").read_text(encoding="utf-8"))["records"]
        cls.r3b = json.loads((ROOT / "data/annotation/person-relation-review-r3b.json").read_text(encoding="utf-8"))

    def test_scope_comes_from_current_data_and_covers_all_people_and_stories(self) -> None:
        people = {person["id"] for person in self.bundle["people"]}
        stories = {
            story["id"]
            for story in self.bundle["stories"]
            if story["publication_state"] in {"production_ready", "preview_ready"}
        }
        self.assertEqual(self.coverage["scope"]["production_person_ids"], sorted(people))
        self.assertEqual(self.coverage["scope"]["published_story_ids"], sorted(stories))
        self.assertEqual(self.coverage["scope"]["production_person_count"], len(people))
        self.assertEqual(self.coverage["scope"]["published_story_count"], len(stories))

    def test_pair_universe_is_derived_not_a_hardcoded_count(self) -> None:
        count = self.coverage["scope"]["production_person_count"]
        self.assertEqual(self.coverage["scope"]["person_pair_universe"], count * (count - 1) // 2)

    def test_existing_reviewed_relations_are_controls_not_new_candidates(self) -> None:
        reviewed = {
            tuple(sorted((relation["subject_id"], relation["object_id"])))
            for relation in self.relations
            if relation["review_status"] == "reviewed"
        }
        candidate_pairs = {
            tuple(sorted((candidate["person_a_id"], candidate["person_b_id"])))
            for candidate in self.candidates["records"]
        }
        self.assertEqual(self.coverage["summary"]["already_reviewed_rediscovery_count"], len(reviewed))
        self.assertEqual(self.coverage["summary"]["existing_reviewed_relation_count"], len(self.relations))
        self.assertFalse(reviewed & candidate_pairs)

    def test_r3b_deferred_decisions_remain_deferred(self) -> None:
        deferred_ids = {
            record["candidate_id"]
            for record in self.r3b["records"]
            if record["decision"] == "deferred"
        }
        deferred_attention = {
            candidate_id
            for record in self.coverage["attention_records"]
            if record["disposition"] == "existing_deferred"
            for candidate_id in record["existing_r3a_candidate_ids"]
        }
        self.assertEqual(deferred_attention, deferred_ids)
        self.assertEqual(self.coverage["summary"]["existing_deferred_candidate_count"], len(deferred_ids))
        self.assertFalse(any(record.get("production_relation_id") for record in self.candidates["records"]))

    def test_fangzheng_031_scene_tension_is_not_relation(self) -> None:
        rows = [
            record
            for record in self.coverage["attention_records"]
            if record["disposition"] == "scene_only"
            and record["person_a_id"] == "person-011"
            and record["person_b_id"] == "person-019"
        ]
        self.assertEqual(len(rows), 1)
        self.assertTrue(any("scene_not_relation" in flag for flag in rows[0]["risk_flags"]))
        self.assertFalse(
            any(
                {relation["subject_id"], relation["object_id"]} == {"person-011", "person-019"}
                for relation in self.relations
            )
        )

    def test_cooccurrence_does_not_create_candidate(self) -> None:
        for candidate in self.candidates["records"]:
            self.assertTrue(candidate["discovery_basis"].startswith("explicit_"))
            self.assertNotIn("cooccurrence", " ".join(candidate["risk_flags"]))
            self.assertTrue(candidate["evidence_ids"])

    def test_explicit_relation_families_are_detectable_in_isolated_fixtures(self) -> None:
        fixtures = [
            (
                "甲為乙之父",
                [{"person_id": "person-001", "surface": "甲", "start": 0, "end": 1}, {"person_id": "person-002", "surface": "乙", "start": 2, "end": 3}],
                "kinship",
            ),
            (
                "甲妻乙",
                [{"person_id": "person-001", "surface": "甲", "start": 0, "end": 1}, {"person_id": "person-002", "surface": "乙", "start": 2, "end": 3}],
                "marriage",
            ),
            (
                "甲與乙善",
                [{"person_id": "person-001", "surface": "甲", "start": 0, "end": 1}, {"person_id": "person-002", "surface": "乙", "start": 2, "end": 3}],
                "social",
            ),
            (
                "甲為乙長史",
                [{"person_id": "person-001", "surface": "甲", "start": 0, "end": 1}, {"person_id": "person-002", "surface": "乙", "start": 2, "end": 3}],
                "institutional",
            ),
            (
                "甲與蘇峻戰",
                [{"person_id": "person-001", "surface": "甲", "start": 0, "end": 1}, {"person_id": "person-017", "surface": "蘇峻", "start": 2, "end": 4}],
                "political",
            ),
        ]
        for text, hits, family in fixtures:
            result = detect_relation_hits(text, hits)
            self.assertTrue(any(item["family"] == family for item in result), (text, result))

    def test_ambiguous_identity_is_blocked_from_relation_candidates(self) -> None:
        self.assertGreaterEqual(self.coverage["summary"]["identity_blocked_count"], 1)
        self.assertFalse(
            any(
                candidate["person_a_id"] == "person-003"
                and candidate["person_b_id"] == "person-015"
                for candidate in self.candidates["records"]
            )
        )

    def test_candidate_ids_are_deterministic_and_pair_order_safe(self) -> None:
        first = project(ROOT)
        second = project(ROOT)
        encoded_first = json.dumps(first, ensure_ascii=False, sort_keys=True).encode("utf-8")
        encoded_second = json.dumps(second, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.assertEqual(encoded_first, encoded_second)
        self.assertEqual(hashlib.sha256(encoded_first).hexdigest(), hashlib.sha256(encoded_second).hexdigest())
        record = deepcopy(self.candidates["records"][0])
        swapped = deepcopy(record)
        swapped["person_a_id"], swapped["person_b_id"] = swapped["person_b_id"], swapped["person_a_id"]
        self.assertEqual(stable_candidate_id(record), stable_candidate_id(swapped))

    def test_new_candidates_are_review_only_and_evidence_backed(self) -> None:
        evidence_ids = {item["id"] for item in self.bundle["evidence"]}
        people_ids = {item["id"] for item in self.bundle["people"]}
        for candidate in self.candidates["records"]:
            self.assertEqual(candidate["review_status"], "candidate")
            self.assertNotIn("production_relation_id", candidate)
            self.assertIn(candidate["person_a_id"], people_ids)
            self.assertIn(candidate["person_b_id"], people_ids)
            self.assertTrue(set(candidate["evidence_ids"]) <= evidence_ids)

    def test_r3c_does_not_change_production_relation_count(self) -> None:
        reviewed_count = sum(relation["review_status"] == "reviewed" for relation in self.relations)
        self.assertEqual(self.coverage["summary"]["already_reviewed_rediscovery_count"], reviewed_count)
        self.assertEqual(validate(ROOT), [])


if __name__ == "__main__":
    unittest.main()
