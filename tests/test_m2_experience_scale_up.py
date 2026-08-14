from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from scripts.validate_m2_person_expansion import validate as validate_person_wave
from scripts.validate_m2_story_expansion import validate as validate_story_wave


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class M2ExperienceScaleUpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.people = read("data/people.json")["people"]
        cls.bundle = read("data/derived/sc1-site.json")
        cls.wave = read("data/annotation/person-expansion-wave-2.json")
        cls.story_wave = read("data/annotation/story-expansion-wave-1.json")
        cls.metrics = read("data/derived/m2-experience-metrics.json")
        cls.relations = read("data/annotation/wp1-relations.json")["records"]
        cls.evidence = read("data/evidence/wp1-evidence.json")["records"]
        cls.sources = {
            item["id"]: item["witness_id"]
            for item in read("data/sources/wp1-sources.json")["records"]
        }

    def test_wave_two_is_exactly_the_next_opaque_person_sequence(self) -> None:
        self.assertEqual(
            [item["person_id"] for item in sorted(self.wave["members"], key=lambda item: item["rank_at_selection"])],
            [f"person-{index:03d}" for index in range(18, 36)],
        )
        self.assertEqual({item["person_id"] for item in self.people}, {f"person-{index:03d}" for index in range(1, 36)})
        self.assertEqual(validate_person_wave(ROOT), [])

    def test_story_publication_is_sc0_union_frozen_expansion(self) -> None:
        gold = {item["entry_id"] for item in read("data/story-chain-gold-set.json")["records"]}
        expansion = set(self.story_wave["expansion_story_ids"])
        frontend = {story["id"] for story in self.bundle["stories"]}
        self.assertEqual(len(gold), 16)
        self.assertEqual(len(expansion), 44)
        self.assertEqual(frontend, gold | expansion)
        self.assertTrue(gold.isdisjoint(expansion))
        self.assertEqual(validate_story_wave(ROOT), [])

    def test_random_person_eligibility_is_generated_and_reachable(self) -> None:
        story_people = {
            person_id
            for story in self.bundle["stories"]
            if story.get("publication_state") in {"production_ready", "preview_ready"}
            for person_id in story.get("person_ids", [])
        }
        sketches = set(self.bundle["person_sketches"])
        eligible = story_people & sketches
        # ER1 deliberately removes the only unsafe Story path for 孫晷 /
        # person-015.  Eligibility remains derived from the generated bundle;
        # a Person without a safe published navigation path is not made
        # eligible merely to preserve the pre-resolution count.
        self.assertEqual(len(eligible), self.metrics["after"]["random_person_eligible_count"])
        self.assertNotIn("person-015", eligible)
        self.assertEqual(self.metrics["after"]["random_person_eligible_count"], len(eligible))

    def test_er_identity_correction_does_not_restore_an_unsafe_sun_gui_path(self) -> None:
        stories = {story["id"]: story for story in self.bundle["stories"]}
        corrected_story = stories["05-fangzheng-058"]
        self.assertNotIn("person-015", corrected_story["person_ids"])

        corrected_mentions = [
            mention
            for mention in self.bundle["mentions"]
            if mention.get("story_id") == "05-fangzheng-058"
            and mention.get("surface") == "文度"
        ]
        self.assertTrue(corrected_mentions)
        self.assertTrue(all(mention.get("person_id") != "person-015" for mention in corrected_mentions))
        self.assertTrue(
            all(
                mention.get("resolution_target", {}).get("canonical_name") == "王坦之"
                for mention in corrected_mentions
            )
        )

        # A candidate_for_review occurrence may list 孫晷 as one possible
        # identity, but it is not a safe production navigation edge.
        candidate_review_count = 0
        for mention in self.bundle["mentions"]:
            if mention.get("resolution_status") != "candidate_for_review":
                continue
            candidates = mention.get("resolution_candidates", [])
            if not any(candidate.get("person_id") == "person-015" for candidate in candidates):
                continue
            candidate_review_count += 1
            story = stories[mention["story_id"]]
            self.assertNotIn("person-015", story["person_ids"])
        self.assertGreater(candidate_review_count, 0)

    def test_m2_metrics_show_scale_without_relation_inflation(self) -> None:
        self.assertEqual(self.metrics["before"]["production_person_count"], 17)
        self.assertEqual(self.metrics["after"]["production_person_count"], 35)
        self.assertEqual(self.metrics["before"]["published_story_count"], 16)
        self.assertEqual(self.metrics["after"]["published_story_count"], 60)
        self.assertEqual(self.metrics["after"]["scene_card_count"], 21)
        self.assertEqual(len(self.relations), 12)
        self.assertEqual(self.metrics["after"]["reviewed_relation_count"], 12)
        self.assertGreater(self.metrics["after"]["story_mediated_person_pair_count"], 0)

    def test_wave_two_production_evidence_uses_registered_witnesses(self) -> None:
        wave_evidence = [item for item in self.evidence if str(item["id"]).startswith("evidence-p3b-wave-2-")]
        self.assertTrue(wave_evidence)
        for item in wave_evidence:
            self.assertEqual(
                item["locator"]["source_provenance"]["witness_id"],
                self.sources[item["source_id"]],
            )

    def test_supplemental_discovery_evidence_is_withheld_not_rewritten(self) -> None:
        candidate_evidence = read("data/derived/person-identity-candidates.json")["evidence"]
        supplemental = {
            item["id"]
            for item in candidate_evidence
            if item.get("source") == "shishuo"
            and item.get("locator", {}).get("source_provenance", {}).get("witness_id") == "shishuo-wikisource-sbck"
        }
        production_ids = {item["id"] for item in self.evidence}
        self.assertTrue(supplemental)
        self.assertTrue(
            all(
                "evidence-p3b-wave-2-" + hashlib.sha256((source_id + "\0").encode()).hexdigest()[:24]
                not in production_ids
                for source_id in supplemental
            )
        )
        withheld = [
            occurrence
            for member in read("data/derived/person-expansion-wave-2-materialization.json")["members"]
            for occurrence in member.get("withheld_occurrences", [])
        ]
        self.assertTrue(any(item["reason"] == "source_provenance_not_registered_for_production" for item in withheld))


if __name__ == "__main__":
    unittest.main()
