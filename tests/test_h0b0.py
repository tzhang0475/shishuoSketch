from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_h0b0_social_backbone import OUTPUTS  # noqa: E402


def load(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class H0B0SocialBackboneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        subprocess.run(
            [sys.executable, "scripts/build_h0b0_social_backbone.py"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        cls.people = {
            item["person_id"]
            for item in load("data/people.json")["people"]
        }
        cls.backbone = load("data/derived/h0b0-social-backbone.json")
        cls.metrics = load("data/derived/h0b0-metrics.json")

    def test_frozen_pilot_is_current_production_scope(self):
        selected = self.backbone["pilot_person_ids"]
        self.assertGreaterEqual(len(selected), 15)
        self.assertLessEqual(len(selected), 20)
        self.assertEqual(len(selected), len(set(selected)))
        self.assertTrue(set(selected) <= self.people)
        frozen_people = set(self.backbone["production_person_ids"])
        self.assertEqual(len(frozen_people), 50)
        self.assertTrue(frozen_people <= self.people)
        self.assertGreaterEqual(len(self.people), len(frozen_people))
        self.assertEqual(self.backbone["counts"]["pilot_person_count"], len(selected))

    def test_four_atomic_families_are_separate(self):
        self.assertEqual(len(self.backbone["clans"]), 3)
        self.assertEqual(len(self.backbone["clan_memberships"]), 7)
        self.assertEqual(len(self.backbone["kinship"]), 5)
        self.assertEqual(len(self.backbone["marriages"]), 2)
        self.assertEqual(len(self.backbone["office_tenures"]), 17)
        self.assertFalse(any(
            item.get("membership_basis") == "shared_surname"
            for item in self.backbone["clan_memberships"]
        ))
        self.assertTrue(all(
            "relation_type" not in item
            for item in self.backbone["office_tenures"]
        ))

    def test_direct_kinship_and_marriage_examples_are_evidenced(self):
        kinship = {item["id"]: item for item in self.backbone["kinship"]}
        self.assertEqual(
            (kinship["h0b0-kinship-002"]["person_a_id"], kinship["h0b0-kinship-002"]["person_b_id"]),
            ("person-001", "person-004"),
        )
        self.assertEqual(kinship["h0b0-kinship-002"]["kinship_type"], "parent_child")
        self.assertEqual(kinship["h0b0-kinship-002"]["relation_basis"], "direct")
        self.assertIn("evidence-008", kinship["h0b0-kinship-002"]["evidence_ids"])
        marriages = {
            (item["spouse_a_id"], item["spouse_b_id"])
            for item in self.backbone["marriages"]
        }
        self.assertEqual(
            marriages,
            {("person-001", "person-007"), ("person-004", "person-005")},
        )
        self.assertTrue(all(
            item["evidence_ids"] and item["review_status"] == "candidate"
            for item in self.backbone["marriages"]
        ))

    def test_office_tenure_is_honestly_incomplete(self):
        offices = {item["person_id"]: item for item in self.backbone["office_tenures"]}
        self.assertEqual(offices["person-003"]["office_title"], "丞相")
        self.assertEqual(offices["person-045"]["office_title"], "步兵校尉")
        self.assertTrue(all(
            item["temporal_precision"] == "unknown"
            and item["start_year_ce"] is None
            and item["end_year_ce"] is None
            for item in self.backbone["office_tenures"]
        ))

    def test_existing_relations_are_covered_without_duplication(self):
        relations = load("data/annotation/wp1-relations.json")["records"]
        compatibility = self.backbone["existing_relation_compatibility"]
        self.assertEqual(len(relations), 12)
        self.assertEqual(
            {item["relation_id"] for item in compatibility},
            {item["id"] for item in relations},
        )
        self.assertIn(
            "h0b0-kinship-001",
            next(item for item in compatibility if item["relation_id"] == "relation-gold-001")["h0b0_fact_ids"],
        )
        self.assertEqual(
            next(item for item in compatibility if item["relation_id"] == "relation-r3b-001")["compatibility"],
            "relation_not_an_h0b_atomic_fact",
        )
        self.assertEqual(self.metrics["invariants"]["new_reviewed_relation_count"], 0)

    def test_gaps_and_w4_are_non_production(self):
        gaps = load("data/derived/h0b0-structural-gap-audit.json")
        self.assertEqual(gaps["summary"]["gap_count"], 7)
        categories = {item["category"] for item in gaps["records"]}
        self.assertIn("missing_bridge_identity", categories)
        self.assertIn("marriage_spouse_not_production", categories)
        w4 = load("data/derived/h0b0-w4-readiness.json")
        self.assertTrue(w4["recommendations"])
        self.assertTrue(all(
            item["production_effect"] == "none"
            and item["person_id_allocation"] == "forbidden_in_h0b0"
            for item in w4["recommendations"]
        ))

    def test_protected_production_metrics_remain_unchanged(self):
        protected = self.metrics["protected_baseline"]
        self.assertEqual(protected["production_person_count"], 50)
        self.assertEqual(protected["production_story_count"], 83)
        self.assertEqual(protected["person_story_link_count"], 704)
        self.assertEqual(protected["random_person_eligible_count"], 45)
        self.assertEqual(protected["scene_context_count"], 44)
        self.assertEqual(protected["reviewed_relation_count"], 12)
        self.assertEqual(protected["primary_era_orientation_count"], 83)
        self.assertEqual(protected["orphan_mention_count"], 0)

    def test_identity_hotfixes_are_not_reintroduced(self):
        bundle = load("data/derived/sc1-site.json")
        story = next(item for item in bundle["stories"] if item["id"] == "23-rendan-013")
        zhongrong_segments = [
            item for item in story["reading"]["main_text"]["segments"]
            if item.get("display", {}).get("original") == "仲容"
        ]
        self.assertTrue(zhongrong_segments)
        self.assertTrue(all(item.get("person_id") != "person-037" for item in zhongrong_segments))
        story = next(item for item in bundle["stories"] if item["id"] == "01-dexing-026")
        self.assertIn("少孤", story["reading"]["main_text"]["segments"][0]["display"]["original"])
        shaogu_segments = [
            item for item in story["reading"]["main_text"]["segments"]
            if item.get("display", {}).get("original") == "少孤"
        ]
        self.assertFalse(shaogu_segments)
        self.assertTrue(all(item.get("person_id") != "person-032" for item in shaogu_segments))
        story = next(item for item in bundle["stories"] if item["id"] == "05-fangzheng-055")
        long_alias = [
            item for item in story["reading"]["main_text"]["segments"]
            if item.get("display", {}).get("original") == "桓子野"
        ]
        self.assertTrue(long_alias)
        self.assertTrue(all(item.get("person_id") != "person-016" for item in long_alias))

    def test_repeated_build_is_byte_identical_and_source_is_unchanged(self):
        output_paths = [ROOT / relative for relative in OUTPUTS.values()]
        before = {path: digest(path) for path in output_paths}
        evidence_path = ROOT / "data/evidence/wp1-evidence.json"
        people_path = ROOT / "data/people.json"
        source_hashes = (digest(evidence_path), digest(people_path))
        subprocess.run(
            [sys.executable, "scripts/build_h0b0_social_backbone.py"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        after = {path: digest(path) for path in output_paths}
        self.assertEqual(before, after)
        self.assertEqual(source_hashes, (digest(evidence_path), digest(people_path)))

    def test_validator_passes(self):
        result = subprocess.run(
            [sys.executable, "scripts/validate_h0b0.py"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
