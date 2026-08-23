from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HNG_ROOT = ROOT / "data/generated/hng0"


def read(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class HNG0Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(["python3", "scripts/build_hng0.py"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)

    def test_selection_is_deterministic_and_stratified(self):
        selection = read("data/generated/hng0/hng0-selection.json")
        ids = [row["person_id"] for row in selection["people"]]
        self.assertGreaterEqual(len(ids), 20)
        self.assertLessEqual(len(ids), 30)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("high_connectivity", {row["stratum"] for row in selection["people"]})
        self.assertIn("low_connectivity", {row["stratum"] for row in selection["people"]})
        people = {row["person_id"] for row in read("data/people.json")["people"]}
        self.assertTrue(set(ids) <= people)

    def test_relations_are_evidence_backed_and_one_hop(self):
        candidates = read("data/generated/hng0/hng0-candidates.json")
        seeds = set(candidates["scope"]["seed_person_ids"])
        people = {row["person_id"] for row in read("data/people.json")["people"]}
        for relation in candidates["relations"]:
            self.assertIn(relation["relation_type"], {
                "parent_child", "sibling", "uncle_nephew", "cousin_clan_kin", "marriage",
                "affinal_relation", "same_clan", "superior_subordinate", "recruitment_served_under",
                "teacher_student", "explicit_friendship_association",
                "explicit_political_cooperation_opposition", "shared_explicit_event",
            })
            self.assertIn(relation["person_a"], people)
            self.assertIn(relation["person_b"], people)
            self.assertTrue(relation["person_a"] in seeds or relation["person_b"] in seeds)
            self.assertTrue(relation["evidence_refs"])
            self.assertNotIn(relation["extraction_method"], {"cooccurrence", "story_cooccurrence"})

    def test_story_layers_and_scope_remain_explicit(self):
        candidates = read("data/generated/hng0/hng0-candidates.json")
        found = {story["source_presence"] for person in candidates["people"].values() for story in person["stories"]}
        self.assertTrue(found <= {"main_text", "liu_annotation_only", "both"})
        self.assertTrue(found & {"main_text", "liu_annotation_only"})
        scopes = {story["research_scope"] for person in candidates["people"].values() for story in person["stories"]}
        self.assertIn("published", scopes)
        self.assertIn("research_only", scopes)

    def test_temporal_precision_and_evidence(self):
        candidates = read("data/generated/hng0/hng0-candidates.json")
        allowed = {"exact", "circa", "before", "after", "between", "reign_period", "unknown"}
        for item in candidates["temporal_items"]:
            self.assertIn(item["precision"], allowed)
            self.assertTrue(item["evidence_refs"])
            if item["precision"] == "exact":
                self.assertEqual(item["start_year"], item["end_year"])

    def test_candidate_review_and_projection_are_separate(self):
        candidates = read("data/generated/hng0/hng0-candidates.json")
        review = read("data/annotation/hng0-review.json")
        projection = read("data/generated/hng0/hng0-reviewed-projection.json")
        self.assertFalse(candidates["canonical_write_back"])
        self.assertFalse(review["canonical_write_back"])
        self.assertFalse(projection["canonical_write_back"])
        self.assertEqual(set(review["relation_decisions"]), {row["relation_id"] for row in candidates["relations"]})
        self.assertEqual(set(review["temporal_decisions"]), {row["temporal_id"] for row in candidates["temporal_items"]})

    def test_frontend_bundle_is_research_only(self):
        bundle = read("site/src/generated/hng0-site.json")
        self.assertEqual(bundle["stage"], "hng0-frontend-review")
        self.assertFalse(bundle["canonical_write_back"])
        self.assertEqual(set(bundle["people"]), set(read("data/generated/hng0/hng0-selection.json")["people"][i]["person_id"] for i in range(len(read("data/generated/hng0/hng0-selection.json")["people"]))))
        self.assertIn("localStorage", bundle["review_storage"])

    def test_local_retrieval_trace_has_no_llm_and_preserves_provenance_sets(self):
        trace = read("data/generated/hng0/hng0-retrieval-trace.json")
        candidates = read("data/generated/hng0/hng0-candidates.json")
        self.assertFalse(trace["canonical_write_back"])
        self.assertEqual(trace["method"], "existing_local_projection")
        self.assertEqual(set(trace["people"]), set(candidates["scope"]["seed_person_ids"]))
        for row in trace["people"].values():
            self.assertEqual(row["llm_calls"], 0)
            searched = set(row["searched_refs"])
            retrieved = set(row["retrieved_refs"])
            used = set(row["used_evidence_refs"])
            self.assertTrue(retrieved <= searched)
            self.assertTrue(used <= retrieved)

    def test_rebuild_is_byte_identical_and_does_not_change_inputs(self):
        protected = [ROOT / "data/people.json", ROOT / "data/derived/person-story-links.json", ROOT / "data/derived/sc1-site.json"]
        before_inputs = {path: digest(path) for path in protected}
        before = {path.relative_to(HNG_ROOT).as_posix(): digest(path) for path in HNG_ROOT.glob("*.json")}
        subprocess.run(["python3", "scripts/build_hng0.py"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        first = {path.relative_to(HNG_ROOT).as_posix(): digest(path) for path in HNG_ROOT.glob("*.json")}
        subprocess.run(["python3", "scripts/build_hng0.py"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        second = {path.relative_to(HNG_ROOT).as_posix(): digest(path) for path in HNG_ROOT.glob("*.json")}
        self.assertEqual(before, first)
        self.assertEqual(first, second)
        self.assertEqual(before_inputs, {path: digest(path) for path in protected})


if __name__ == "__main__":
    unittest.main()
