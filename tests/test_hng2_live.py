"""Focused offline tests for HNG2-L plumbing and frozen post-processing."""

from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_hng2_live as live  # noqa: E402


class HNG2LiveSelectionTests(unittest.TestCase):
    def test_selection_is_frozen_24_with_required_composition(self):
        selection = live.build_live_selection()
        self.assertEqual(selection["selected_count"], 24)
        self.assertEqual(selection["actual_composition"], {
            "canonical_existing": 6,
            "complex_title_or_kinship": 4,
            "high_confidence_provisional": 6,
            "same_name_or_temporal_risk": 4,
            "sparse_low_connectivity": 4,
        })
        ids = [row["frontier_id"] for row in selection["people"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(selection["frozen"])
        self.assertFalse(selection["canonical_write_back"])

    def test_selection_replay_is_byte_stable(self):
        first = live.build_live_selection()
        second = live.build_live_selection()
        self.assertEqual(
            json.dumps(first, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            json.dumps(second, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )


class HNG2LiveEvidenceTests(unittest.TestCase):
    def test_exact_quote_and_boundary_punctuation(self):
        evidence = {"r": {"model_snippet": "甲乙。", "original_text": "甲乙。"}}
        self.assertEqual(live._valid_quote("r", "甲乙。", evidence), (True, ""))
        self.assertEqual(live._valid_quote("r", "『甲乙』", evidence), (True, "quote_boundary_trimmed"))
        self.assertFalse(live._valid_quote("r", "甲丙", evidence)[0])

    def test_seed_gate_rejects_passage_without_identity_form(self):
        profile = {"forms": ["王導"], "canonical_name": "王導"}
        decision = live._seed_identity_gate(profile, {"text": "此為另一人之傳"})
        self.assertEqual(decision["status"], "conflict")

    def test_llm_identity_validation_is_candidate_and_quote_closed(self):
        item = {"evidence_ref": "r", "temporal_status": "unknown"}
        evidence = {"r": {"model_snippet": "王導與人議", "original_text": "王導與人議"}}
        catalog = {"person-1": {"canonical_name": "王導"}}
        ok, reason, projected = live._validate_assist_output(
            {"entity_type": "person", "chosen_candidate_key": "c0", "evidence_span": "王導", "confidence": "high"},
            {"c0": "person-1"}, item, evidence, catalog,
        )
        self.assertTrue(ok)
        self.assertEqual(projected["chosen_person_id"], "person-1")
        bad, reason, _ = live._validate_assist_output(
            {"entity_type": "person", "chosen_candidate_key": "invented", "evidence_span": "王導", "confidence": "high"},
            {"c0": "person-1"}, item, evidence, catalog,
        )
        self.assertFalse(bad)
        self.assertEqual(reason, "model_invented_candidate_key")

    def test_relation_merge_does_not_promote_unresolved_identity(self):
        rows = [{
            "relation_id": "r1", "person_a": "person-1", "counterpart_surface": "某人",
            "relation_type": "visit_or_association", "direction": "undirected", "identity_occurrence_id": "i1",
            "evidence_refs": ["e"], "evidence_quotes": [{"ref": "e", "quote": "某人"}], "one_hop_only": True,
        }]
        result = live._merge_relations(rows, {"i1": {"final_status": "rejected", "final_person_id": None}})
        self.assertEqual(result, [])

    def test_wave2_only_promotes_eligible_identity_states_and_caps_at_eight(self):
        catalog = {"person-1": {"canonical_name": "甲"}}
        identities = []
        relations = []
        for i in range(10):
            oid = f"i{i}"
            identities.append({"occurrence_id": oid, "final_status": "provisional" if i < 9 else "unresolved", "final_person_id": None})
            relations.append({"relation_id": f"r{i}", "identity_occurrence_id": oid, "person_a": "seed", "counterpart_surface": f"人{i}", "evidence_refs": [f"e{i}"], "one_hop_only": True})
        selected = live._wave2_selection(relations, identities, catalog, {"seed"})
        self.assertLessEqual(len(selected["frontiers"]), 8)
        self.assertFalse(selected["wave_3_created"])


class HNG2LiveBoundaryTests(unittest.TestCase):
    def test_artifact_contract_has_no_canonical_write_back(self):
        selection = live.build_live_selection()
        self.assertFalse(selection["canonical_write_back"])
        self.assertEqual(selection["wave_cap"], 2)
        self.assertTrue(selection["one_hop_only"])

    def test_selection_records_unchanged_hng2_baseline_hashes(self):
        selection = live.build_live_selection()
        for rel, expected in selection["source_hashes"].items():
            self.assertEqual(live.sha256_file(ROOT / rel), expected)


if __name__ == "__main__":
    unittest.main()
