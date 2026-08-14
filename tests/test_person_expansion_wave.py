from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from scripts.validate_person_expansion_wave import validate


ROOT = Path(__file__).resolve().parents[1]
WAVE_PATH = ROOT / "data/annotation/person-expansion-wave-1.json"
MATERIALIZATION_PATH = ROOT / "data/derived/person-expansion-wave-1-materialization.json"
RANKING_PATH = ROOT / "data/derived/person-expansion-wave-1-ranking.json"
P3A_PATH = ROOT / "data/derived/person-expansion-candidates.json"
P3A1_PATH = ROOT / "data/derived/person-identity-candidates.json"
PEOPLE_PATH = ROOT / "data/people.json"
ALIASES_PATH = ROOT / "data/aliases.json"
MENTIONS_PATH = ROOT / "data/mentions/shishuo.json"
LINKS_PATH = ROOT / "data/derived/person-story-links.json"
SC1_PATH = ROOT / "data/derived/sc1-site.json"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PersonExpansionWaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.wave = read(WAVE_PATH)
        cls.materialization = read(MATERIALIZATION_PATH)
        cls.ranking = read(RANKING_PATH)
        cls.p3a = read(P3A_PATH)
        cls.p3a1 = read(P3A1_PATH)
        cls.people = read(PEOPLE_PATH)["people"]
        cls.aliases = read(ALIASES_PATH)["aliases"]
        cls.mentions = read(MENTIONS_PATH)["mentions"]
        cls.links = read(LINKS_PATH)["links"]
        cls.sc1 = read(SC1_PATH)

        cls.wave_members = sorted(
            cls.wave["members"], key=lambda item: item["rank_at_selection"]
        )
        cls.wave_ids = {item["candidate_id"] for item in cls.wave_members}
        cls.wave_person_ids = {item["person_id"] for item in cls.wave_members}
        cls.people_by_id = {item["person_id"]: item for item in cls.people}
        cls.aliases_by_id = {item["alias_id"]: item for item in cls.aliases}
        cls.mentions_by_id = {item["mention_id"]: item for item in cls.mentions}
        cls.p3a1_by_id = {item["candidate_id"]: item for item in cls.p3a1["candidates"]}

    def test_wave_manifest_freezes_the_original_ranks_and_hash(self) -> None:
        self.assertEqual(self.wave["source_ranking_sha256"], sha256(RANKING_PATH))
        ranking_by_id = {item["candidate_id"]: item for item in self.ranking["candidates"]}
        self.assertEqual(
            [item["rank_at_selection"] for item in self.wave_members],
            list(range(1, 11)),
        )
        for member in self.wave_members:
            source = ranking_by_id[member["candidate_id"]]
            self.assertEqual(source["rank"], member["rank_at_selection"])
            self.assertEqual(source["canonical_name"], member["preferred_name"])
            self.assertEqual(member["candidate_status"], "strong_candidate")
            self.assertEqual(member["review_status"], "candidate")

    def test_exactly_ten_unique_wave_persons_are_materialized(self) -> None:
        self.assertEqual(len(self.wave_members), 10)
        self.assertEqual(len(self.wave_person_ids), 10)
        self.assertEqual(self.materialization["people_before"], 7)
        self.assertEqual(self.materialization["people_after"], 17)
        for person_id in self.wave_person_ids:
            person = self.people_by_id[person_id]
            self.assertEqual(person["review_status"], "candidate")
            self.assertEqual(person["materialization"]["wave_id"], "p3b-wave-1")

    def test_p3a1_identity_provenance_is_retained(self) -> None:
        for member in self.wave_members:
            candidate = self.p3a1_by_id[member["candidate_id"]]
            person = self.people_by_id[member["person_id"]]
            self.assertEqual(candidate["preferred_name"], person["canonical_name"])
            self.assertEqual(candidate["status"], "already_materialized")
            self.assertEqual(candidate["matched_person_id"], member["person_id"])
            self.assertEqual(
                person["materialization"]["candidate_id"], member["candidate_id"]
            )
            self.assertTrue(person["materialization"]["identity_evidence_ids"])

    def test_alias_promotion_preserves_exact_and_contextual_semantics(self) -> None:
        wave_aliases = [
            self.aliases_by_id[alias_id]
            for person_id in self.wave_person_ids
            for alias_id in self.people_by_id[person_id]["alias_ids"]
        ]
        self.assertTrue(
            any(
                item["alias_type"] == "personal_name"
                and item["resolution_mode"] == "exact"
                for item in wave_aliases
            )
        )
        self.assertTrue(
            any(
                item["alias_type"] == "courtesy_name"
                and item["resolution_mode"] == "exact"
                for item in wave_aliases
            )
        )
        title_aliases = [
            item
            for item in wave_aliases
            if item["alias_type"]
            in {"office_title", "contextual_title", "posthumous_title"}
        ]
        self.assertTrue(title_aliases)
        self.assertTrue(all(item["resolution_mode"] != "exact" for item in title_aliases))
        self.assertTrue(all(item["review_status"] == "candidate" for item in wave_aliases))

    def test_promoted_occurrences_are_exact_high_confidence_and_anchored(self) -> None:
        promoted = [
            mention
            for mention in self.mentions
            if mention.get("materialization", {}).get("wave_id") == "p3b-wave-1"
        ]
        self.assertEqual(len(promoted), self.materialization["promoted_mention_count"])
        self.assertGreater(len(promoted), 0)
        for mention in promoted:
            self.assertIn(mention["person_id"], self.wave_person_ids)
            self.assertEqual(mention["confidence"], "high")
            self.assertTrue(mention["resolution_method"].startswith("exact"))
            self.assertEqual(mention["review_status"], "candidate")
            self.assertEqual(mention["materialization"]["wave_id"], "p3b-wave-1")
            self.assertTrue(mention["evidence"]["evidence_ids"])

    def test_withheld_occurrences_are_not_promoted_as_production_mentions(self) -> None:
        promoted_occurrences = {
            mention["materialization"]["candidate_occurrence_id"]
            for mention in self.mentions
            if mention.get("materialization", {}).get("wave_id") == "p3b-wave-1"
        }
        withheld = [
            item
            for member in self.materialization["members"]
            for item in member.get("withheld_occurrences", [])
        ]
        self.assertEqual(len(withheld), self.materialization["withheld_occurrence_count"])
        self.assertTrue(withheld)
        self.assertTrue(
            all(item["occurrence_id"] not in promoted_occurrences for item in withheld)
        )
        self.assertTrue(
            all(item["reason"] in {"contextual_association", "unsafe_anchor", "ambiguous_anchor", "non_strong_candidate_confidence", "title_or_non_exact_surface_type"} for item in withheld)
        )

    def test_person_story_links_are_derived_from_mentions_without_relations(self) -> None:
        p3_mention_ids = {
            mention["mention_id"]
            for mention in self.mentions
            if mention.get("materialization", {}).get("wave_id") == "p3b-wave-1"
        }
        wave_links = [link for link in self.links if link["person_id"] in self.wave_person_ids]
        self.assertTrue(wave_links)
        for link in wave_links:
            self.assertNotIn("relation_id", link)
            self.assertNotIn("participant", {presence["presence_kind"] for presence in link["presences"]})
            linked_mentions = set(link.get("supporting_mention_ids", [])) | set(
                link.get("candidate_mention_ids", [])
            )
            self.assertTrue(linked_mentions <= p3_mention_ids)

    def test_current_sc1_projection_contains_wave_persons_and_mentions(self) -> None:
        self.assertTrue(self.wave_person_ids <= {item["id"] for item in self.sc1["people"]})
        wave_mentions = [
            mention
            for mention in self.sc1["mentions"]
            if mention.get("person_id") in self.wave_person_ids
        ]
        self.assertTrue(wave_mentions)
        self.assertTrue(
            all(mention["person_id"] in self.wave_person_ids for mention in wave_mentions)
        )

    def test_p3a1_and_p3a_exclude_wave_persons_after_materialization(self) -> None:
        self.assertEqual(
            {
                item["candidate_id"]
                for item in self.p3a1["candidates"]
                if item["status"] == "already_materialized"
            } & self.wave_ids,
            self.wave_ids,
        )
        self.assertFalse(
            self.wave_ids & {item["candidate_id"] for item in self.p3a["candidates"]}
        )

    def test_protected_relation_and_publication_inputs_are_hash_pinned(self) -> None:
        for relative_path, expected_hash in self.materialization["protected_hashes"].items():
            # R3B intentionally extends the production Relation registry.
            # The original seven Relation records remain semantic controls,
            # but the registry file is no longer a P3B.1 byte-frozen input.
            if relative_path == "data/annotation/wp1-relations.json":
                continue
            self.assertEqual(sha256(ROOT / relative_path), expected_hash)
        self.assertEqual(self.materialization["promoted_mention_count"], 354)

    def test_wave_validator_passes_and_no_raw_source_payload_is_tracked(self) -> None:
        self.assertEqual(validate(ROOT), [])
        tracked = __import__("subprocess").check_output(
            ["git", "ls-files", "shishuoSources/shishuo"],
            cwd=ROOT,
            text=True,
        )
        self.assertEqual(tracked.strip(), "")


if __name__ == "__main__":
    unittest.main()
