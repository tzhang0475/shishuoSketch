"""Focused H0C historical-context and graph-readiness regressions."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.validate_h0c import validate


ROOT = Path(__file__).resolve().parents[1]


def read_json(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class H0CHistoricalContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.freeze = read_json("data/derived/h0c-participant-freeze.json")
        cls.locations = read_json("data/derived/h0c-locations.json")
        cls.offices = read_json("data/derived/h0c-offices.json")
        cls.activities = read_json("data/derived/h0c-person-activities.json")
        cls.event_participations = read_json("data/derived/h0c-event-participations.json")
        cls.facts = read_json("data/derived/h0c-historical-facts.json")
        cls.anchors = read_json("data/annotation/story-temporal-anchors-h0a.json")
        cls.graph = read_json("data/derived/h0c-graph-projection.json")
        cls.audit = read_json("data/derived/h0c-graph-audit.json")
        cls.readiness = read_json("data/derived/h0c-ml-readiness.json")
        cls.metrics = read_json("data/derived/h0c-metrics.json")

    def test_validator_passes(self) -> None:
        self.assertEqual(validate(), [])

    def test_all_production_stories_are_frozen_once(self) -> None:
        self.assertEqual(len(self.freeze["story_records"]), 143)
        self.assertEqual(len({row["story_id"] for row in self.freeze["story_records"]}), 143)
        self.assertEqual(self.freeze["participant_count"], 334)
        self.assertEqual(self.freeze["reviewed_role_count"], 334)
        self.assertEqual(self.freeze["unreviewed_uncertainty_count"], 0)
        self.assertEqual(self.freeze["hard_provenance_complete_count"], 52)

    def test_participant_roles_are_not_mentions(self) -> None:
        rows = self.freeze["records"]
        self.assertTrue(all(row["review_status"] == "reviewed" for row in rows))
        self.assertTrue(all(row["hard_temporal_eligible"] == (row["role"] in {"present", "speaker", "actor"}) for row in rows))
        self.assertNotIn(
            "person-029",
            {row["person_id"] for row in rows if row["story_id"] == "08-shangyu-079"},
        )

    def test_hard_participants_have_textual_provenance(self) -> None:
        hard = [row for row in self.freeze["records"] if row["hard_temporal_eligible"]]
        self.assertTrue(hard)
        self.assertTrue(all(row["mention_provenance"] or row["basis"] == "reviewed_scene_context" for row in hard))
        self.assertTrue(all(row["provenance_complete"] for row in hard))
        self.assertTrue(all(row["evidence_ids"] or row["provenance_refs"] for row in hard))

    def test_location_is_first_class_without_fake_modern_coordinates(self) -> None:
        self.assertGreaterEqual(self.locations["count"], 5)
        self.assertEqual(len({row["location_id"] for row in self.locations["records"]}), self.locations["count"])
        self.assertTrue(all(row["modern_mapping"]["status"] == "unknown" for row in self.locations["records"]))
        self.assertTrue(all(row["modern_mapping"]["latitude"] is None for row in self.locations["records"]))

    def test_office_entities_reuse_tenure_ids_and_unknown_dates_stay_unknown(self) -> None:
        tenure_ids = {row["tenure_id"] for row in self.offices["tenures"]}
        self.assertEqual(self.offices["tenure_count"], 26)
        self.assertEqual(
            set().union(*(set(row["tenure_ids"]) for row in self.offices["entities"])),
            tenure_ids,
        )
        for row in self.offices["tenures"]:
            if row["temporal_precision"] == "unknown":
                self.assertIsNone(row["start_year_ce"])
                self.assertIsNone(row["end_year_ce"])

    def test_duplicate_h0a_activity_source_is_not_a_duplicate_fact(self) -> None:
        self.assertEqual(self.activities["source_duplicate_count"], 1)
        self.assertEqual(self.activities["count"], 24)
        self.assertEqual(len({row["activity_id"] for row in self.activities["records"]}), 24)

    def test_contextual_event_reference_is_not_hard_event_participation(self) -> None:
        self.assertTrue(any(row["participation_type"] == "story_event_reference" for row in self.event_participations["records"]))
        self.assertTrue(all(row["hard_temporal_eligible"] == (row["story_role"] in {"present", "speaker", "actor"}) for row in self.event_participations["records"]))

    def test_every_graph_edge_traces_to_fact_and_evidence_or_source_provenance(self) -> None:
        self.assertEqual(self.audit["issue_counts"]["dangling_edges"], 0)
        self.assertEqual(self.audit["issue_counts"]["unsupported_edges"], 0)
        fact_keys = {row["fact_key"] for row in self.facts["fact_index"]}
        for edge in self.graph["edges"]:
            self.assertTrue(edge["source_facts"])
            self.assertTrue(edge["evidence_ids"] or edge.get("provenance_refs"))
            self.assertTrue(all(ref["fact_key"] in fact_keys for ref in edge["source_facts"]))

    def test_orphans_are_reported_not_repaired(self) -> None:
        self.assertEqual(
            set(self.audit["issues"]["orphan_nodes"]),
            {"Person:person-016", "Person:person-032", "Person:person-037", "Person:person-074", "Story:27-jiajue-012"},
        )
        self.assertEqual(self.audit["scope"]["person_story_links_out_of_production_scope"], 545)

    def test_readiness_contract_is_framework_neutral_and_not_ml(self) -> None:
        contract = self.readiness["contract"]
        self.assertTrue(contract["framework_neutral"])
        self.assertFalse(contract["model_artifacts_generated"])
        self.assertFalse(contract["embeddings_generated"])
        self.assertFalse(contract["training_split_generated"])
        self.assertEqual(len(self.readiness["person_records"]), 75)
        self.assertEqual(self.metrics["future_boundary"], {"hg0_implemented": False, "ml_implemented": False, "er2_implemented": False})

    def test_h0a_unknown_remains_an_explicit_historical_state(self) -> None:
        unknown_stories = {row["story_id"] for row in self.anchors["records"] if row["precision"] == "unknown"}
        self.assertTrue(unknown_stories)
        anchor_facts = {
            row["subject_ids"][0]
            for row in self.facts["fact_index"]
            if row["fact_type"] == "story_temporal_anchor" and row["temporal_precision"] == "unknown"
        }
        self.assertTrue(anchor_facts)
        self.assertFalse(self.metrics["future_boundary"]["hg0_implemented"])

    def test_protected_baseline_is_unchanged(self) -> None:
        protected = self.metrics["protected"]
        self.assertEqual(protected["production_person_count"], 75)
        self.assertEqual(protected["production_story_count"], 143)
        self.assertEqual(protected["person_story_link_count"], 875)
        self.assertEqual(protected["reviewed_person_story_link_count"], 870)
        self.assertEqual(protected["reviewed_relation_count"], 12)
        self.assertEqual(protected["scene_context_count"], 44)
        self.assertEqual(protected["orphan_mention_count"], 0)
        self.assertEqual(protected["primary_era_orientation_count"], 143)


if __name__ == "__main__":
    unittest.main()
