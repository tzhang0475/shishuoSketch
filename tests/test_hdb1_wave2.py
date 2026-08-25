#!/usr/bin/env python3
"""Focused offline tests for HDB1-W2 and cross-wave safety boundaries."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_hdb1_cross_wave_database as cross  # noqa: E402
import run_hdb1_wave2 as wave2  # noqa: E402
from hdb1_common import stable_hash  # noqa: E402


class HDB1W2SelectionTests(unittest.TestCase):
    def test_remaining_scope_is_computed_and_disjoint(self):
        selection = wave2.load_frozen_selection()
        self.assertEqual(143, selection["production_story_count"])
        self.assertEqual(54, selection["prior_hng2_story_count"])
        self.assertEqual(48, selection["hdb1_w1_story_count"])
        self.assertEqual(73, selection["remaining_story_count"])
        self.assertEqual([], selection["overlap_with_prior_hng2"])
        self.assertEqual([], selection["overlap_with_hdb1_w1"])
        self.assertEqual(2 * selection["person_target_count"] + 2 * selection["story_count"], selection["expected_semantic_calls"])

    def test_selection_rebuild_is_byte_stable(self):
        self.assertEqual(wave2.load_frozen_selection(), wave2.build_selection())

    def test_targets_are_bounded_main_text_targets(self):
        for story in wave2.load_frozen_selection()["stories"]:
            self.assertGreaterEqual(len(story["targets"]), 1)
            self.assertLessEqual(len(story["targets"]), 2)
            for target in story["targets"]:
                self.assertEqual("main_text", target["source_section"])


def _wave(wave_id: str, story_id: str, observations: list[dict], relations: list[dict] | None = None) -> dict:
    return {
        "wave_id": wave_id,
        "run_id": wave_id + "-run",
        "selection": {"selection_hash": wave_id + "-selection", "stories": [{"story_id": story_id}]},
        "person_candidates": observations,
        "identity_candidates": observations,
        "identity_assertions": [],
        "relation_candidates": relations or [],
        "kinship_candidates": [],
        "marriage_candidates": [],
        "office_candidates": [],
        "temporal_candidates": [],
        "review_queue": [],
    }


class HDB1W2AggregationTests(unittest.TestCase):
    def test_same_surface_is_only_a_surface_bucket(self):
        rows = [
            {
                "candidate_id": "obs-a",
                "identity_observation_id": "id-a",
                "story_id": "a",
                "unit_id": "u-a",
                "entity_key": "e0",
                "surface": "王某",
                "identity_status": "unresolved",
                "identity_resolution_basis": "unresolved",
                "evidence_ref": "r-a",
            },
            {
                "candidate_id": "obs-b",
                "identity_observation_id": "id-b",
                "story_id": "b",
                "unit_id": "u-b",
                "entity_key": "e0",
                "surface": "王某",
                "identity_status": "unresolved",
                "identity_resolution_basis": "unresolved",
                "evidence_ref": "r-b",
            },
        ]
        aggregate = cross.aggregate([_wave("HDB1-W1", "a", [rows[0]]), _wave("HDB1-W2", "b", [rows[1]])])
        registry = aggregate["candidate_identity_registry"]
        self.assertTrue(all(row["status"] == "unresolved_surface_cluster" for row in registry))
        self.assertTrue(all(row["surface_bucket_only"] for row in registry))
        self.assertEqual(0, aggregate["metrics"]["cross_story_candidate_clusters"])

    def test_existing_person_observations_share_safe_cluster(self):
        rows = [
            {"candidate_id": "obs-a", "identity_observation_id": "id-a", "story_id": "a", "unit_id": "u-a", "entity_key": "e0", "surface": "王導", "identity_status": "resolved_existing", "identity_resolution_basis": "catalogue_exact_match", "resolved_person_id": "person-003", "evidence_ref": "r-a"},
            {"candidate_id": "obs-b", "identity_observation_id": "id-b", "story_id": "b", "unit_id": "u-b", "entity_key": "e0", "surface": "王導", "identity_status": "resolved_existing", "identity_resolution_basis": "catalogue_exact_match", "resolved_person_id": "person-003", "evidence_ref": "r-b"},
        ]
        aggregate = cross.aggregate([_wave("HDB1-W1", "a", [rows[0]]), _wave("HDB1-W2", "b", [rows[1]])])
        existing = [row for row in aggregate["candidate_identity_registry"] if row["status"] == "resolved_existing"]
        self.assertEqual(1, len(existing))
        self.assertEqual(2, existing[0]["occurrence_count"])

    def test_aggregate_is_deterministic(self):
        row = {"candidate_id": "obs-a", "identity_observation_id": "id-a", "story_id": "a", "unit_id": "u-a", "entity_key": "e0", "surface": "甲", "identity_status": "resolved_new_candidate", "identity_resolution_basis": "new_candidate", "evidence_ref": "r-a"}
        waves = [_wave("HDB1-W1", "a", [row]), _wave("HDB1-W2", "b", [])]
        self.assertEqual(stable_hash(cross.aggregate(waves)), stable_hash(cross.aggregate(waves)))

    def test_same_surface_cannot_unblock_prior_relation(self):
        w1_subject = {
            "candidate_id": "obs-w1-subject",
            "identity_observation_id": "id-w1-subject",
            "story_id": "a",
            "unit_id": "u-a",
            "entity_key": "e0",
            "surface": "王某",
            "identity_status": "unresolved",
            "identity_resolution_basis": "unresolved",
            "evidence_ref": "r-a",
        }
        w1_object = {
            "candidate_id": "obs-w1-object",
            "identity_observation_id": "id-w1-object",
            "story_id": "a",
            "unit_id": "u-a",
            "entity_key": "e1",
            "surface": "王導",
            "identity_status": "resolved_existing",
            "identity_resolution_basis": "catalogue_exact_match",
            "resolved_person_id": "person-003",
            "evidence_ref": "r-a",
        }
        w2_subject = {
            "candidate_id": "obs-w2-subject",
            "identity_observation_id": "id-w2-subject",
            "story_id": "b",
            "unit_id": "u-b",
            "entity_key": "e0",
            "surface": "王某",
            "identity_status": "resolved_existing",
            "identity_resolution_basis": "catalogue_exact_match",
            "resolved_person_id": "person-099",
            "evidence_ref": "r-b",
        }
        relation = {
            "candidate_id": "rel-w1",
            "story_id": "a",
            "unit_id": "u-a",
            "subject_entity_key": "e0",
            "object_entity_key": "e1",
            "subject_ref": "unresolved:id-w1-subject",
            "object_ref": "person:person-003",
            "subject_person_id": None,
            "object_person_id": "person-003",
            "relation_class": "interaction",
            "relation_surface": "語",
            "evidence_ref": "r-a",
            "exact_span": "王某語王導",
            "novelty": "unresolved_endpoint",
        }
        aggregate = cross.aggregate([
            _wave("HDB1-W1", "a", [w1_subject, w1_object], [relation]),
            _wave("HDB1-W2", "b", [w2_subject]),
        ])
        self.assertEqual(0, aggregate["metrics"]["W1_blocked_relations_unblocked_by_W2"])
        self.assertEqual([], aggregate["newly_unblocked_relation_candidates"])


if __name__ == "__main__":
    unittest.main()
