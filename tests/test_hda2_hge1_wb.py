#!/usr/bin/env python3
"""Offline contracts for HDA2 remediation and HGE1-WB growth artifacts."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hda1_identity_audit as hda1  # noqa: E402
import hda2_identity_remediation as hda2  # noqa: E402
import hge1_wave_a as wave_a  # noqa: E402
import hge1_wave_b as wave_b  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class HDA2Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selection = load(hda2.OUT / "remediation-selection.json")
        cls.packets_doc = load(hda2.OUT / "remediation-packets.json")
        cls.metrics = load(hda2.OUT / "metrics.json")
        cls.overlay = load(hda2.OUT / "repair-overlay.json")
        cls.grounded = load(hda2.OUT / "grounded-alternatives.json")
        cls.queue = load(hda2.OUT / "human-review-queue.json")

    def test_selection_and_packets_are_frozen_candidate_only(self):
        self.assertEqual(self.selection, hda2.build_selection())
        self.assertEqual(32, self.selection["selected_claim_count"])
        self.assertEqual(self.selection["selected_claim_count"], self.packets_doc["packet_count"])
        self.assertTrue(self.selection["frozen_before_live"])
        self.assertTrue(self.selection["candidate_only"])
        self.assertFalse(self.selection["canonical_write_back"])
        for packet in self.packets_doc["packets"]:
            prompt = hda2.remediation_prompt(packet)
            prompt_json = json.dumps(prompt, ensure_ascii=False, sort_keys=True)
            self.assertTrue(prompt["claim"]["flagged_for_reevaluation"])
            self.assertNotIn("hda1_verdict_for_audit", prompt_json)
            self.assertNotIn("identity_resolution_basis", prompt_json)

    def test_hda2_live_projection_is_fail_closed_and_null_safe(self):
        self.assertTrue(self.metrics["candidate_only"])
        self.assertFalse(self.metrics["canonical_write_back"])
        self.assertEqual(32, self.metrics["semantic_calls"])
        self.assertFalse(any(row.get("alternative_surface") == "null" for row in self.grounded))
        for row in self.overlay:
            self.assertTrue(row["candidate_only"])
            self.assertFalse(row["canonical_write_back"])
            self.assertNotEqual("null", row.get("alternative_surface"))
        self.assertEqual(32, len(self.overlay))
        self.assertTrue(self.queue["candidate_only"])
        self.assertFalse(self.queue["canonical_write_back"])

    def test_protected_inputs_match_hda2_snapshot(self):
        manifest = load(hda2.OUT / "manifest.json")
        self.assertEqual(manifest["protected_hashes_before"], hda2.protected_hashes())


class HGE1WaveBContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selection = load(wave_b.SELECTION_PATH)
        cls.target_selection = load(wave_b.TARGET_SELECTION_PATH)
        cls.database = load(wave_b.DERIVED / "hge1-wave-b-candidate-db.json")
        cls.growth = load(wave_b.DERIVED / "hge1-wave-b-metrics.json")
        cls.series = load(wave_b.SERIES_PATH)
        cls.run_base = wave_b.GENERATED / "live" / "hge1-wb-final-live"
        cls.run_manifest = load(cls.run_base / "manifest.json")

    def test_selection_is_frozen_and_disjoint_from_snapshot(self):
        self.assertEqual(self.selection, wave_b.build_selection())
        self.assertEqual([], wave_b.validate_selection(self.selection))
        prior = wave_b.previous_story_snapshot()
        self.assertEqual(prior["hash"], self.selection["prior_story_hash"])
        self.assertFalse(set(self.selection["story_ids"]) & set(prior["story_ids"]))
        self.assertEqual([], self.selection["overlap_with_production"])
        self.assertEqual([], self.selection["overlap_with_prior"])
        self.assertTrue(self.selection["frozen_before_live"])
        self.assertTrue(self.selection["candidate_only"])
        self.assertFalse(self.selection["canonical_write_back"])
        self.assertEqual(24, len(self.selection["story_ids"]))

    def test_target_selection_is_reproducible_and_source_visible(self):
        self.assertEqual(self.target_selection, wave_b.build_target_selection(self.selection))
        self.assertEqual([], wave_b.validate_target_selection(self.selection, self.target_selection))
        self.assertEqual(24, self.target_selection["target_count"])

    def test_live_manifest_and_candidate_projection_boundaries(self):
        self.assertEqual(self.selection["selection_hash"], self.run_manifest["selection_hash"])
        self.assertEqual(self.target_selection["target_selection_hash"], self.run_manifest["target_selection_hash"])
        self.assertTrue(self.run_manifest["candidate_only"])
        self.assertFalse(self.run_manifest["canonical_write_back"])
        self.assertTrue(self.database["candidate_only"])
        self.assertFalse(self.database["canonical_write_back"])
        self.assertEqual(24, len(self.database["person_observations"]))
        for row in self.database["candidate_persons"]:
            self.assertFalse(str(row["candidate_person_id"]).startswith("person-"))
        self.assertFalse(any(row.get("cooccurrence_only") for row in self.database["relation_candidates"]))

    def test_a_b_series_preserves_wave_a_and_adds_wave_b(self):
        rows = {row["wave"]: row for row in self.series["series"]}
        self.assertEqual({"baseline", "HGE1-WA", "HGE1-WB"}, set(rows))
        wave_a_metrics = load(wave_b.DERIVED / "hge1-wave-a-metrics.json")
        for key in ("story_count", "candidate_person_count", "graph_nodes", "graph_edges"):
            self.assertEqual(wave_a_metrics["after"][key], rows["HGE1-WA"][key])
        self.assertEqual(187, rows["HGE1-WB"]["story_count"])
        self.assertEqual(57, rows["HGE1-WB"]["candidate_person_count"])
        self.assertTrue(self.series["wave_a_values_preserved"])
        self.assertTrue(self.series["candidate_only"])
        self.assertFalse(self.series["canonical_write_back"])

    def test_projection_rebuild_is_byte_stable_without_api(self):
        person_units, temporal_units = wave_b.build_wave_units(self.selection, self.target_selection)
        run = {
            "base": self.run_base,
            "person_results": load(self.run_base / "person-results.json"),
            "temporal_results": load(self.run_base / "temporal-results.json"),
            "transport": load(self.run_base / "transport.json"),
            "preflight": self.run_manifest.get("preflight", {}),
            "person_units": person_units,
            "temporal_units": temporal_units,
            "target_selection": self.target_selection,
        }
        first = wave_b.build_projection(self.selection, run)
        second = wave_b.build_projection(self.selection, run)
        self.assertEqual(wave_b.stable_hash(first), wave_b.stable_hash(second))
        self.assertEqual(self.growth["after"], wave_b.growth_projection(
            wave_a.baseline(),
            load(wave_a.SELECTION_PATH),
            load(wave_b.DERIVED / "hge1-wave-a-candidate-db.json"),
            load(wave_b.DERIVED / "hge1-wave-a-metrics.json"),
            self.selection,
            first,
            run,
        )["after"])


if __name__ == "__main__":
    unittest.main()
