#!/usr/bin/env python3
"""Focused offline tests for HDB1-W1 selection and candidate boundaries."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_hdb1_candidate_database as builder  # noqa: E402
from hdb1_common import (  # noqa: E402
    PERSON_LIKE_KINDS,
    build_selection,
    hdb_stable_id,
    load_frozen_selection,
    production_story_rows,
)


class HDB1SelectionTests(unittest.TestCase):
    def test_production_scope_is_current_143_story_set(self):
        rows = production_story_rows()
        self.assertEqual(143, len(rows))
        self.assertEqual(143, len({row["id"] for row in rows}))

    def test_selection_is_frozen_48_and_stratified(self):
        selection = load_frozen_selection()
        self.assertTrue(selection["frozen_before_live"])
        self.assertEqual(48, selection["story_count"])
        self.assertEqual({"social-density": 16, "temporal-gap": 16, "baseline": 16}, selection["stratum_actual"])
        self.assertEqual(48, len({row["story_id"] for row in selection["stories"]}))
        self.assertEqual(2 * selection["person_target_count"] + 96, selection["expected_semantic_calls"])

    def test_targets_are_main_text_and_bounded(self):
        selection = load_frozen_selection()
        for story in selection["stories"]:
            self.assertGreaterEqual(len(story["targets"]), 1)
            self.assertLessEqual(len(story["targets"]), 2)
            for target in story["targets"]:
                self.assertEqual("main_text", target["source_section"])
                self.assertTrue(target["surface"])

    def test_selection_rebuild_is_byte_stable(self):
        selection = load_frozen_selection()
        rebuilt = build_selection()
        self.assertEqual(selection, rebuilt)


class HDB1ProjectionTests(unittest.TestCase):
    def test_new_person_candidate_never_allocates_production_id(self):
        token, data = builder._candidate_person_token(
            {
                "identity_status": "resolved_new_candidate",
                "identity_resolution_basis": "new_candidate",
                "entity_key": "e0",
                "surface": "陳騫",
                "evidence_ref": "r",
                "exact_span": "陳騫",
            },
            "c0",
            "01-dexing-001",
            "hdb1-target-01-dexing-001-p1",
        )
        self.assertTrue(token.startswith("provisional:hdb1-person-"))
        self.assertIsNone(data["person_id"])
        self.assertFalse(token.split(":", 1)[1].startswith("person-"))

    def test_non_person_entity_cannot_enter_person_candidate_projection(self):
        person, identities, endpoints, rejected, evaluation = builder._identity_and_entities(
            [
                {
                    "story_id": "01-dexing-001",
                    "unit_id": "hdb1-target-01-dexing-001-p1",
                    "selection": {"target_id": "t", "surface": "洛陽", "reference_person_id": None},
                    "evidence_windows": [{"ref": "r", "evidence_text": "洛陽"}],
                    "normalization": {"entities": [{"entity_key": "e0", "surface": "洛陽", "entity_kind": "location", "identity_status": "resolved_existing", "resolved_person_id": "person-001", "evidence_ref": "r", "exact_span": "洛陽"}]},
                }
            ],
            {"person-001": {"canonical_name": "王羲之"}},
        )
        self.assertEqual([], person)
        self.assertEqual([], identities)
        self.assertEqual({}, endpoints)
        self.assertEqual("nonperson_person_id_anomaly", rejected[0]["reason"])

    def test_explicit_interaction_is_candidate_and_self_relation_is_rejected(self):
        result = {
            "story_id": "01-dexing-001",
            "unit_id": "u1",
            "evidence_windows": [{"ref": "r", "evidence_text": "甲詣乙"}],
            "normalization": {
                "entities": [
                    {"entity_key": "e0", "surface": "甲", "entity_kind": "named_person"},
                    {"entity_key": "e1", "surface": "乙", "entity_kind": "named_person"},
                ],
                "relations": [{"relation_id": "r0", "subject_entity_key": "e0", "object_entity_key": "e1", "relation_surface": "詣", "relation_class": "interaction", "evidence_ref": "r", "exact_span": "甲詣乙", "confidence": "high", "semantic_level": "documented_interaction"}],
            },
        }
        endpoints = {("u1", "e0"): {"token": "person:person-001", "person_id": "person-001", "provisional_person_id": "", "entity_kind": "named_person"}, ("u1", "e1"): {"token": "person:person-002", "person_id": "person-002", "provisional_person_id": "", "entity_kind": "named_person"}}
        relations, *_rest = builder._relation_projection([result], endpoints, {"relations": {}, "kinship": {}, "marriage": {}, "office": {}})
        self.assertEqual(1, len(relations))
        self.assertTrue(relations[0]["graph_candidate"])
        self.assertEqual("interaction", relations[0]["relation_class"])

        result["normalization"]["relations"][0]["object_entity_key"] = "e0"
        relations, kinship, marriage, offices, identities, rejected, stats = builder._relation_projection([result], endpoints, {"relations": {}, "kinship": {}, "marriage": {}, "office": {}})
        self.assertEqual([], relations)
        self.assertEqual(1, stats["self"])
        self.assertEqual("collapsed_self_relation", rejected[0]["reason"])

    def test_stable_candidate_ids_use_evidence_coordinates(self):
        material = {"object_type": "relation", "story_id": "01-dexing-001", "exact_span": "甲詣乙"}
        self.assertEqual(hdb_stable_id("relation", material), hdb_stable_id("relation", material))
        self.assertNotEqual(hdb_stable_id("relation", material), hdb_stable_id("relation", {**material, "exact_span": "甲問乙"}))


if __name__ == "__main__":
    unittest.main()
