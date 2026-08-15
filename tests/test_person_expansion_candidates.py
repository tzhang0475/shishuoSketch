from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.person_expansion import (
    P3A_PATH,
    REPORT_PATH,
    UNRESOLVED_PATH,
    WEIGHTS,
    build_analysis,
    calculate_score,
)
from scripts.validate_person_expansion_candidates import validate


ROOT = Path(__file__).resolve().parents[1]


class PersonExpansionCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads((ROOT / P3A_PATH).read_text(encoding="utf-8"))
        cls.unresolved = json.loads((ROOT / UNRESOLVED_PATH).read_text(encoding="utf-8"))
        cls.report = (ROOT / REPORT_PATH).read_text(encoding="utf-8")
        cls.people = json.loads((ROOT / "data/people.json").read_text(encoding="utf-8"))["people"]
        cls.shishuo_mentions = json.loads(
            (ROOT / "data/mentions/shishuo.json").read_text(encoding="utf-8")
        )["mentions"]

    def test_artifacts_validate_and_scoped_people_are_excluded(self) -> None:
        self.assertEqual(validate(ROOT), [])
        scoped = {
            person["person_id"]
            for person in self.people
            if person["person_id"] in self.document["candidate_identity_policy"]["scoped_person_ids_excluded"]
        }
        self.assertTrue(scoped)
        self.assertEqual(
            scoped,
            set(self.document["candidate_identity_policy"]["scoped_person_ids_excluded"]),
        )
        self.assertLess(len(scoped), len(self.people))
        self.assertFalse(
            scoped.intersection(
                {candidate["source_person_id"] for candidate in self.document["candidates"]}
            )
        )

    def test_p3a_consumes_strong_open_world_candidates_without_materializing_them(self) -> None:
        # P3A.1 supplies review keys, not production Person IDs. The P3A
        # ranking should now be non-empty while the current registry remains
        # excluded from its output.
        self.assertGreater(self.document["candidate_count"], 0)
        self.assertGreater(self.document["input_counts"]["p3a1_eligible_candidate_count"], 0)
        self.assertTrue(all(candidate["identity_kind"] == "p3a1_candidate" for candidate in self.document["candidates"]))
        self.assertIn("王公", {row["surface"] for row in self.unresolved["surfaces"]})
        self.assertNotIn("王公", {candidate["canonical_name"] for candidate in self.document["candidates"]})

    def test_unresolved_surface_clusters_are_explicitly_not_persons(self) -> None:
        for row in self.unresolved["surfaces"]:
            self.assertTrue(row["not_ranked_as_person"])
            self.assertGreaterEqual(row["mention_count"], 2)
            self.assertEqual(
                row["story_count"],
                len(set(row["story_ids"])),
            )

    def test_score_is_interpretable_and_recomputable(self) -> None:
        components = {name: 1.0 for name in WEIGHTS}
        components["ambiguity_risk"] = 0.0
        self.assertEqual(calculate_score(components), 100.0)
        components["ambiguity_risk"] = 1.0
        self.assertEqual(calculate_score(components), 85.0)

    def test_closed_world_mentions_remain_unchanged_while_open_world_gaps_are_reported(self) -> None:
        scoped = {person["person_id"] for person in self.people}
        resolved_ids = {
            mention["person_id"]
            for mention in self.shishuo_mentions
            if isinstance(mention.get("person_id"), str)
        }
        self.assertTrue(resolved_ids.issubset(scoped))
        self.assertTrue(self.document["current_live_story_gaps"])
        self.assertGreater(self.document["candidate_count"], 0)

    def test_current_story_candidate_gets_coverage_without_synthesized_relation(self) -> None:
        current_story_candidate = next(
            candidate
            for candidate in self.document["candidates"]
            if candidate["metrics"]["current_liu_annotation_story_count"] > 0
        )
        self.assertGreater(
            current_story_candidate["metrics"]["current_liu_annotation_story_count"],
            0,
        )
        self.assertEqual(current_story_candidate["metrics"]["direct_relation_to_current_count"], 0)
        self.assertEqual(current_story_candidate["direct_relation_ids"], [])

    def test_build_is_byte_deterministic_without_frontend_mutation(self) -> None:
        rebuilt, rebuilt_unresolved, rebuilt_report = build_analysis(ROOT)
        self.assertEqual(
            json.dumps(rebuilt, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            (ROOT / P3A_PATH).read_text(encoding="utf-8"),
        )
        self.assertEqual(
            json.dumps(rebuilt_unresolved, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            (ROOT / UNRESOLVED_PATH).read_text(encoding="utf-8"),
        )
        self.assertEqual(rebuilt_report, self.report)


if __name__ == "__main__":
    unittest.main()
