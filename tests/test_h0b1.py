"""Focused H0B-1 social/temporal safety regressions."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts.build_h0b1_social_temporal_backbone import (
    activated_office_constraint,
    intersect_intervals,
)


ROOT = Path(__file__).resolve().parents[1]


def read_json(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class H0B1SocialTemporalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.participants = read_json("data/derived/h0b1-story-participants.json")
        cls.constraints = read_json("data/derived/h0b1-social-temporal-constraints.json")
        cls.backbone = read_json("data/derived/h0b1-social-backbone.json")
        cls.metrics = read_json("data/derived/h0b1-metrics.json")
        cls.upgrades = read_json("data/derived/h0b1-h0a-upgrade-queue.json")
        cls.effective = read_json("data/derived/person-resolution-effective.json")

    def test_all_current_scope_stories_have_a_participant_record(self) -> None:
        self.assertEqual(len(self.participants["records"]), 143)
        self.assertEqual(
            {row["story_id"] for row in self.participants["records"]},
            {row["story_id"] for row in self.constraints["records"]},
        )

    def test_mention_is_not_story_participation(self) -> None:
        story = next(row for row in self.participants["records"] if row["story_id"] == "14-rongzhi-024")
        by_person = {row["person_id"]: row for row in story["participants"]}
        # 王逸少 is a later report in this Story, not a current-scene actor.
        self.assertIn("person-001", by_person)
        self.assertFalse(by_person["person-001"]["hard_temporal_eligible"])
        self.assertEqual(by_person["person-001"]["role"], "referenced")
        self.assertTrue(any(row["person_id"] == "person-010" and row["hard_temporal_eligible"] for row in story["participants"]))

    def test_望之_lexical_collision_cannot_reenter_participation(self) -> None:
        story = next(row for row in self.participants["records"] if row["story_id"] == "08-shangyu-079")
        self.assertNotIn("person-029", {row["person_id"] for row in story["participants"]})
        self.assertFalse(
            any(
                row.get("source_id") == "08-shangyu-079"
                and row.get("surface") == "望之"
                and row.get("person_id") == "person-029"
                for row in self.effective.get("mentions", []) + self.effective.get("derived_mentions", [])
            )
        )

    def test_non_hard_participant_roles_never_enter_participant_constraints(self) -> None:
        hard_by_story = {
            row["story_id"]: set(row["hard_participant_ids"])
            for row in self.participants["records"]
        }
        for row in self.constraints["records"]:
            constrained = {item.get("person_id") for item in row["participant_constraints"]}
            self.assertTrue(constrained <= hard_by_story[row["story_id"]])
            self.assertFalse(row["marriage_constraints"])
            self.assertFalse(row["kinship_constraints"])

    def test_off_frame_and_annotation_only_people_cannot_date_a_story(self) -> None:
        for story in self.participants["records"]:
            contextual = {
                row["person_id"]
                for row in story["participants"]
                if row["role"] in {"off_frame", "annotation_only"}
            }
            constraint = next(row for row in self.constraints["records"] if row["story_id"] == story["story_id"])
            constrained = {
                item.get("person_id")
                for item in constraint["participant_constraints"]
            }
            self.assertTrue(contextual.isdisjoint(constrained), story["story_id"])

    def test_clan_membership_has_no_temporal_constraint_basis(self) -> None:
        for row in self.constraints["records"]:
            for group_name in ("participant_constraints", "office_constraints", "relation_constraints"):
                self.assertFalse(
                    any("clan" in str(item.get("basis", "")).lower() for item in row[group_name]),
                    row["story_id"],
                )

    def test_candidate_office_fact_is_deferred_not_hard(self) -> None:
        row = next(row for row in self.constraints["records"] if row["story_id"] == "05-fangzheng-034")
        self.assertEqual(row["office_constraints"], [])
        self.assertEqual(row["candidate_office_constraints"][0]["tenure_id"], "h0b1-office-003")
        self.assertFalse(row["candidate_office_constraints"][0]["hard_temporal_eligible"])

    def test_reviewed_story_activated_office_can_constrain(self) -> None:
        office = next(row for row in self.backbone["office_tenures"] if row["tenure_id"] == "h0b1-office-003")
        reviewed_office = copy.deepcopy(office)
        reviewed_office["review_status"] = "reviewed"
        result = activated_office_constraint(
            reviewed_office,
            {"person_id": "person-058", "role": "present", "evidence_ids": ["local-test-evidence"]},
        )
        self.assertIsNotNone(result)
        self.assertEqual((result["start_year_ce"], result["end_year_ce"]), (328, 329))
        self.assertIsNone(
            activated_office_constraint(
                reviewed_office,
                {"person_id": "person-058", "role": "referenced", "evidence_ids": []},
            )
        )

    def test_rejected_office_fact_cannot_constrain(self) -> None:
        office = next(row for row in self.backbone["office_tenures"] if row["tenure_id"] == "h0b1-office-003")
        rejected_office = copy.deepcopy(office)
        rejected_office["review_status"] = "rejected"
        self.assertIsNone(
            activated_office_constraint(
                rejected_office,
                {"person_id": "person-058", "role": "actor", "evidence_ids": []},
            )
        )

    def test_multiple_present_activity_intersection_is_ordered(self) -> None:
        candidates = [row for row in self.constraints["records"] if len(row["participant_constraints"]) >= 2]
        self.assertTrue(candidates)
        for row in candidates:
            intervals = [
                (item["start_year_ce"], item["end_year_ce"])
                for item in row["participant_constraints"]
            ]
            intersection = intersect_intervals(intervals)
            self.assertIsNotNone(intersection)
            self.assertLessEqual(intersection[0], intersection[1])
            self.assertGreaterEqual(row["valid_intersection"]["start_year_ce"], intersection[0])
            self.assertLessEqual(row["valid_intersection"]["end_year_ce"], intersection[1])

    def test_empty_intersection_is_not_a_compromise_date(self) -> None:
        self.assertIsNone(intersect_intervals([(307, 317), (328, 329)]))

    def test_h0a_unknown_can_coexist_with_reader_orientation_and_upgrade_queue(self) -> None:
        row = next(row for row in self.constraints["records"] if row["story_id"] == "06-yaliang-023")
        self.assertEqual(row["h0a_precision"], "unknown")
        self.assertTrue(row["h0a_upgrade_candidate"])
        self.assertIsNotNone(row["primary_era_card_id"])
        self.assertFalse(self.metrics["h0a"]["anchor_layer_rewritten"])
        self.assertEqual(self.upgrades["h0a_rewritten"], False)

    def test_clan_and_relation_context_do_not_date_by_themselves(self) -> None:
        contexts = read_json("data/derived/h0b1-relation-temporal-contexts.json")["records"]
        friendship = next(row for row in contexts if row["relation_id"] == "relation-r3b-001")
        self.assertEqual(friendship["scope_status"], "intentionally_unscoped")
        self.assertEqual(friendship["temporal_precision"], "unknown")
        self.assertEqual(self.metrics["social"]["kinship_derived_count"], 0)

    def test_gap_catalog_and_frozen_reconciliation_are_explicit(self) -> None:
        gaps = read_json("data/derived/h0b1-gap-audit.json")
        self.assertEqual(
            gaps["category_catalog"],
            [
                "missing_structural_endpoint",
                "missing_family_bridge",
                "marriage_endpoint_not_production",
                "clan_branch_unresolved",
                "office_chronology_incomplete",
                "relation_temporal_scope_missing",
                "participant_role_uncertain",
                "identity_compatibility_gap",
                "source_conflict",
                "temporal_conflict",
                "evidence_too_broad",
            ],
        )
        reconciliation = read_json("data/derived/h0b1-h0b0-reconciliation.json")
        self.assertTrue(reconciliation["h0b0_artifact_unchanged"])

    def test_protected_production_metrics(self) -> None:
        protected = self.metrics["protected_baseline"]
        self.assertEqual(protected["production_person_count"], 75)
        self.assertEqual(protected["production_story_count"], 143)
        self.assertEqual(protected["person_story_link_count"], 875)
        self.assertEqual(protected["reviewed_person_story_link_count"], 870)
        self.assertEqual(protected["random_person_eligible_count"], 69)
        self.assertEqual(protected["reviewed_relation_count"], 12)
        self.assertEqual(protected["scene_context_count"], 44)
        self.assertEqual(protected["orphan_mention_count"], 0)
        self.assertEqual(protected["primary_era_orientation_count"], 143)


if __name__ == "__main__":
    unittest.main()
