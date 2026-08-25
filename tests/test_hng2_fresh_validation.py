from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import historical_context_algorithm as algorithm  # noqa: E402
import run_hng2_algorithm_closeout as closeout  # noqa: E402
import run_hng2_fresh_validation as fresh  # noqa: E402


class HNG2V1SelectionTests(unittest.TestCase):
    def test_selection_is_24_fresh_stories_and_immutable(self) -> None:
        selection = fresh.load_frozen_selection()
        self.assertEqual(selection["story_count"], 24)
        self.assertEqual(len(selection["stories"]), 24)
        self.assertEqual(selection["overlap_with_previous_hng2"], [])
        self.assertEqual(len({row["story_id"] for row in selection["stories"]}), 24)
        self.assertEqual(selection["selection_hash"], fresh.stable_hash({key: value for key, value in selection.items() if key != "selection_hash"}))

    def test_selection_has_four_per_available_temporal_stratum(self) -> None:
        selection = fresh.load_frozen_selection()
        counts = selection["temporal_strata_actual"]
        self.assertEqual(set(counts), set(fresh.TEMPORAL_STRATA))
        self.assertEqual(counts, {key: 4 for key in fresh.TEMPORAL_STRATA})

    def test_exclusion_manifest_has_file_hash_evidence(self) -> None:
        selection = fresh.load_frozen_selection()
        exclusion = selection["previous_hng2_exclusion"]
        self.assertGreater(exclusion["story_count"], 0)
        self.assertTrue(exclusion["files"])
        self.assertTrue(exclusion["exclusion_hash"])
        self.assertTrue(exclusion["files_hash"])


class HNG2V1BoundaryTests(unittest.TestCase):
    def test_contextual_projection_has_distinct_basis(self) -> None:
        replay = closeout.replay_person_outputs()
        yi = [
            entity
            for row in replay["results"]
            if row.get("target", {}).get("surface") == "廙"
            for entity in (row.get("normalization") or {}).get("entities", [])
            if entity.get("surface") == "廙"
        ]
        self.assertEqual(len(yi), 1)
        self.assertEqual(yi[0]["resolved_person_id"], "person-053")
        self.assertEqual(yi[0]["identity_resolution_basis"], "contextual_name_projection")
        self.assertNotEqual(yi[0]["identity_resolution_basis"], "evidence_identity_assertion")

    def test_direct_identity_assertion_keeps_direct_basis(self) -> None:
        windows = [algorithm.prepare_evidence_window({"ref": "r", "text": "廙即王廙", "evidence_text": "廙即王廙"})]
        validation = {
            "valid_entities": [
                {"entity_key": "e0", "surface": "廙", "entity_kind": "abbreviated_name", "reference_form": "abbreviated", "evidence_refs": ["r"]},
                {"entity_key": "e1", "surface": "王廙", "entity_kind": "named_person", "reference_form": "full_name", "evidence_refs": ["r"]},
            ],
            "valid_relations": [{"relation_id": "r0", "subject_entity_key": "e0", "object_entity_key": "e1", "relation_surface": "即", "relation_class": "identity_name", "evidence_ref": "r", "exact_span": "廙即王廙", "confidence": "high"}],
        }
        case = {"observation": {"surface": "廙"}, "candidates": [{"candidate_key": "c0", "person_id": "person-053", "canonical_name": "王廙", "known_forms": ["王廙"]}], "constraint_checks": [], "seed": {}}
        result = algorithm.normalize_person_fill(validation, case=case, windows=windows)
        target = next(entity for entity in result["entities"] if entity["surface"] == "廙")
        self.assertEqual(target["identity_resolution_basis"], "evidence_identity_assertion")

    def test_scanner_scope_is_explicit_and_not_universal(self) -> None:
        windows = [algorithm.prepare_evidence_window({"ref": "r", "text": "武帝時，今日相見", "evidence_text": "武帝時，今日相見"})]
        hints = algorithm.scan_visible_temporal_anchors(windows)
        self.assertTrue(any(row["surface"] == "武帝" for row in hints))
        self.assertFalse(any(row["surface"] == "今日" for row in hints))
        self.assertEqual(closeout.VISIBLE_ANCHOR_SCANNER_SCOPE, "H0A historical registry + explicit date patterns")
        self.assertTrue(closeout._surface_in_declared_scanner_scope("武帝"))
        self.assertFalse(closeout._surface_in_declared_scanner_scope("薨"))


if __name__ == "__main__":
    unittest.main()
