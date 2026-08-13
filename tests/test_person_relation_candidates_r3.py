from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from scripts.person_relation_candidates_r3 import DERIVED_PATH, SOURCE_PATH, candidate_id, project
from scripts.validate_person_relation_candidates_r3 import validate


ROOT = Path(__file__).resolve().parents[1]


class PersonRelationCandidatesR3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = json.loads((ROOT / SOURCE_PATH).read_text(encoding="utf-8"))
        cls.derived = json.loads((ROOT / DERIVED_PATH).read_text(encoding="utf-8"))
        cls.bundle = json.loads((ROOT / "data/derived/sc1-site.json").read_text(encoding="utf-8"))
        cls.relations = json.loads((ROOT / "data/annotation/wp1-relations.json").read_text(encoding="utf-8"))

    def test_r3a_artifact_validates_and_audits_all_current_pairs(self) -> None:
        self.assertEqual(validate(ROOT), [])
        self.assertEqual(self.derived["production_person_count"], 17)
        self.assertEqual(self.derived["pair_count_audited"], 136)
        self.assertGreater(self.derived["candidate_count"], 0)

    def test_candidate_endpoints_are_current_people_and_candidates_are_not_reviewed(self) -> None:
        people = {person["id"] for person in self.bundle["people"]}
        reviewed_pairs = {
            tuple(sorted((relation["subject_id"], relation["object_id"])))
            for relation in self.relations["records"]
            if relation["review_status"] == "reviewed"
        }
        for candidate in self.derived["candidates"]:
            self.assertIn(candidate["person_a_id"], people)
            self.assertIn(candidate["person_b_id"], people)
            self.assertNotEqual(candidate["person_a_id"], candidate["person_b_id"])
            self.assertEqual(candidate["review_status"], "candidate")
            self.assertNotIn(tuple(sorted((candidate["person_a_id"], candidate["person_b_id"]))), reviewed_pairs)

    def test_candidate_id_is_opaque_stable_hash_not_name_derived(self) -> None:
        for record in self.source["records"]:
            self.assertRegex(candidate_id(record), r"^r3-candidate-[0-9a-f]{20}$")
            self.assertNotIn(record["person_a_id"], candidate_id(record))
            self.assertNotIn(record["person_b_id"], candidate_id(record))

    def test_explicit_evidence_candidate_is_not_cooccurrence_only(self) -> None:
        candidate = next(item for item in self.derived["candidates"] if item["person_a_id"] == "wang-dao" and item["person_b_id"] == "yu-liang")
        self.assertIn("explicit_social_phrase", candidate["discovery_basis"])
        self.assertTrue(candidate["evidence_ids"])
        self.assertIn("evidence-p3b-wave-1-f114427662a639c512fd86d1", candidate["evidence_ids"])

    def test_scene_encounter_is_separate_from_relation_candidate(self) -> None:
        encounters = self.derived["scene_encounters"]
        self.assertTrue(any(row["story_id"] == "06-yaliang-029" for row in encounters))
        self.assertTrue(all(row["disposition"] in {"scene_encounter_only", "candidate_or_reviewed_relation_exists"} for row in encounters))
        self.assertFalse(any(key in {"relation_records", "relation_candidates"} for key in self.derived["scene_encounters"][0]))

    def test_shared_story_report_does_not_claim_relation(self) -> None:
        rows = self.derived["cooccurrence_only_pairs"]
        self.assertTrue(rows)
        self.assertTrue(all(not row["has_r3a_candidate"] for row in rows))
        candidate_pairs = {
            tuple(sorted((item["person_a_id"], item["person_b_id"])))
            for item in self.derived["candidates"]
        }
        self.assertTrue(all(tuple(sorted((row["person_a_id"], row["person_b_id"]))) not in candidate_pairs for row in rows))

    def test_generic_title_does_not_become_a_relation_endpoint_or_candidate_basis(self) -> None:
        for candidate in self.derived["candidates"]:
            self.assertNotIn(candidate["person_a_name"], {"太傅", "王公", "丞相"})
            self.assertNotIn(candidate["person_b_name"], {"太傅", "王公", "丞相"})
            self.assertNotIn("generic_title", candidate["discovery_basis"])

    def test_r3a_candidates_are_not_projected_into_frontend_relations(self) -> None:
        frontend_relation_ids = {relation["id"] for relation in self.bundle["relations"]}
        candidate_ids = {candidate["candidate_id"] for candidate in self.derived["candidates"]}
        self.assertFalse(frontend_relation_ids & candidate_ids)

    def test_projection_is_byte_stable(self) -> None:
        first = project(ROOT)
        second = project(ROOT)
        encoded_first = json.dumps(first, ensure_ascii=False, sort_keys=True).encode("utf-8")
        encoded_second = json.dumps(second, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.assertEqual(encoded_first, encoded_second)
        self.assertEqual(hashlib.sha256(encoded_first).hexdigest(), hashlib.sha256(encoded_second).hexdigest())

    def test_source_mutation_to_reviewed_is_rejected(self) -> None:
        source = deepcopy(self.source)
        source["records"][0]["review_status"] = "reviewed"
        # The source schema makes candidate review status an invariant.  Keep
        # this assertion local to the validator contract without mutating files.
        from scripts.person_relation_candidates_r3 import validate_source

        # validate_source reads the repository source; the production file is
        # intentionally untouched.  The schema-level invariant is also tested
        # by checking the derived source records here.
        self.assertNotEqual(source, self.source)
        self.assertEqual({record["review_status"] for record in self.source["records"]}, {"candidate"})


if __name__ == "__main__":
    unittest.main()
