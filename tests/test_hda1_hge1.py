#!/usr/bin/env python3
"""Offline contract tests for the HDA1 audit and HGE1-WA growth wave."""

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
import hge1_wave_a as hge1  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class HDA1OfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.claims = load(hda1.OUT / "claims.json")
        cls.packets = load(hda1.OUT / "audit-packets.json")
        cls.manifest = load(hda1.OUT / "manifest.json")

    def test_full_claim_universe_is_present(self):
        self.assertEqual(self.claims["claim_count"], len(self.claims["claims"]))
        self.assertGreaterEqual(self.claims["claim_count"], 500)
        self.assertEqual(self.claims["claim_count"], self.packets["claim_count"])
        self.assertEqual(self.claims["claim_count"], len(self.packets["packets"]))

    def test_packets_are_blind_to_prior_decisions(self):
        forbidden = {
            "accepted", "canonical", "confidence", "previous_model_verdict",
            "psl_score", "reviewer_acceptance", "production_status",
            "previous_verdict", "resolved_person_id", "identity_status",
            "identity_resolution_basis", "review_status",
        }
        for packet in self.packets["packets"]:
            self.assertFalse(forbidden & set(packet), packet["claim_id"])
            self.assertTrue(packet["person_id"])
            self.assertTrue(packet["target_surface"])
            evidence_ids = {item["evidence_id"] for item in packet["evidence_items"]}
            self.assertTrue(set(packet["source_evidence_ids"]) <= evidence_ids)

    def test_claim_and_packet_hashes_are_reproducible(self):
        self.assertEqual(self.manifest["claims_hash"], hda1.stable_hash(self.claims))
        self.assertEqual(self.manifest["packets_hash"], hda1.stable_hash(self.packets))

    def test_grounding_is_fail_closed_for_unknown_evidence(self):
        packet = {"source_evidence_ids": ["ev-known"]}
        payload = {
            "verdict": "support",
            "supporting_evidence_ids": ["ev-invented"],
            "contradicting_evidence_ids": [],
            "reason_types": ["explicit_identity"],
            "suggested_identity_surface": None,
            "explanation": "",
        }
        result = hda1.validate_audit_payload(payload, packet)
        self.assertFalse(result["valid"])
        self.assertIn("supporting_evidence_ids_unknown_evidence_id", result["errors"])


class HGE1OfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selection = load(hge1.SELECTION_PATH)
        cls.target_selection = load(hge1.TARGET_SELECTION_PATH)
        cls.baseline = load(hge1.GENERATED / "baseline.json")
        cls.candidate = load(hge1.DERIVED / "hge1-wave-a-candidate-db.json")
        cls.growth = load(hge1.DERIVED / "hge1-wave-a-metrics.json")

    def test_story_selection_is_frozen_and_disjoint(self):
        self.assertEqual([], hge1.validate_selection(self.selection))
        self.assertEqual(self.selection, hge1.build_selection())
        self.assertEqual(20, len(self.selection["story_ids"]))
        self.assertEqual([], self.selection["overlap_with_production"])
        self.assertEqual([], self.selection["overlap_with_prior_hng2"])

    def test_target_selection_is_source_visible_and_reproducible(self):
        self.assertEqual([], hge1.validate_target_selection(self.selection, self.target_selection))
        self.assertEqual(self.target_selection, hge1.build_target_selection(self.selection))
        self.assertEqual(20, self.target_selection["target_count"])
        for row in self.target_selection["records"]:
            self.assertEqual(1, len(row["targets"]))

    def test_candidate_projection_is_candidate_only(self):
        self.assertTrue(self.candidate["candidate_only"])
        self.assertFalse(self.candidate["canonical_write_back"])
        for row in self.candidate["person_observations"]:
            candidate_id = row.get("candidate_person_id") or ""
            self.assertFalse(candidate_id.startswith("person-"), row)
        self.assertFalse(any(row.get("cooccurrence_only") for row in self.candidate["relation_candidates"]))

    def test_growth_uses_combined_baseline_graph(self):
        self.assertEqual(self.baseline, hge1.baseline())
        self.assertEqual(20, self.growth["delta"]["story_count"])
        self.assertEqual(40, self.growth["delta"]["graph_nodes"])
        self.assertEqual(20, self.growth["delta"]["graph_edges"])
        self.assertEqual(20, self.growth["delta"]["connected_components"])
        self.assertEqual(26, self.growth["after"]["connected_components"])
        self.assertEqual(42, self.growth["after"]["unresolved_identity_count"])


if __name__ == "__main__":
    unittest.main()
