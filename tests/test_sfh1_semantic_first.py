from __future__ import annotations

import sys
import unittest
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from semantic_first import candidate_retrieval, hard_constraints, identity_judgment, mention_validation, reference_semantics, storage_gate
from semantic_first.analysis import heuristic_audit
from semantic_first.source_packets import validation_universe
from semantic_first.common import OUT, stable_hash


def packet(text: str = "顧長康畫裴叔則頰") -> dict:
    return {"story_id": "test-story", "evidence": [{"evidence_id": "e0", "source_layer": "main_text", "text": text}]}


class SFH1LayerTests(unittest.TestCase):
    def test_validation_universe_is_frozen_187(self):
        universe = validation_universe()
        self.assertEqual(143, universe["production_story_count"])
        self.assertEqual(20, universe["wave_a_story_count"])
        self.assertEqual(24, universe["wave_b_story_count"])
        self.assertEqual(187, universe["current_story_count"])
        self.assertEqual(188, universe["story_count"])
        self.assertEqual(["04-wenxue-023"], universe["extra_regression_story_ids"])

    def test_multiple_mentions_are_exactly_grounded(self):
        payload = {"mentions": [
            {"mention_id_local": "m0", "surface": "顧長康", "source_evidence_id": "e0", "source_start": 0, "source_end": 3, "entity_kind": "person", "reference_form": "courtesy_name", "confidence": "high", "local_explanation": "畫者"},
            {"mention_id_local": "m1", "surface": "裴叔則", "source_evidence_id": "e0", "source_start": 4, "source_end": 7, "entity_kind": "person", "reference_form": "courtesy_name", "confidence": "high", "local_explanation": "被畫者"},
        ]}
        ledger = mention_validation.validate_mentions(packet(), payload)
        self.assertEqual(["顧長康", "裴叔則"], [row["surface"] for row in ledger["valid_mentions"]])
        self.assertFalse(ledger["rejected_mentions"])

    def test_absent_surface_fails_closed(self):
        payload = {"mentions": [{"mention_id_local": "m0", "surface": "佛經", "source_evidence_id": "e0", "source_start": None, "source_end": None, "entity_kind": "person", "reference_form": "full_name", "confidence": "high", "local_explanation": "bad"}]}
        ledger = mention_validation.validate_mentions(packet("殷中軍見經"), payload)
        self.assertFalse(ledger["valid_mentions"])
        self.assertEqual("surface_not_in_source", ledger["rejected_mentions"][0]["reasons"][0])

    def test_non_person_never_enters_storage(self):
        mention = {"mention_id": "m0", "story_id": "s", "surface": "佛經", "entity_kind": "non_person", "reference_form": "uncertain", "source_evidence_id": "e0"}
        final = storage_gate.finalize_story({"story_id": "s", "valid_mentions": [mention]}, {"records": []}, {"records": [{"mention_id": "m0", "candidates": []}]}, {"decisions": []}, {"reviews": [], "required_mentions": []})
        self.assertEqual("non_person", final["records"][0]["final_state"])
        self.assertIsNone(final["records"][0]["person_id"])

    def test_holder_patron_semantics_are_model_supplied_and_veto_whole_compound(self):
        ledger = {"story_id": "s", "valid_mentions": [{"mention_id": "m0", "story_id": "s", "surface": "敦主簿", "entity_kind": "person", "reference_form": "office_title"}]}
        semantics = {"records": [{"mention_id": "m0", "semantic_type": "patron_plus_office", "confidence": "high", "anchor_mentions": [], "holder_mentions": [], "patron_or_possessor_mentions": []}]}
        sets = {"records": [{"mention_id": "m0", "candidates": [{"candidate_key": "c0", "entity_type": "existing_person", "person_id": "person-001"}]}]}
        constrained = hard_constraints.constrain_candidates(ledger, semantics, sets, {"judgments": [{"mention_id": "m0", "preferred_candidate_key": "c0", "resolution": "candidate_supported", "candidate_assessments": []}]})
        self.assertIn("structural_holder_patron_mismatch", constrained["records"][0]["hard_vetoes"]["c0"])

    def test_reference_relation_requires_valid_mentions_and_grounded_predicate(self):
        p = packet("舊以桓謙比殷仲文")
        ledger = {"valid_mentions": [
            {"mention_id": "m0", "surface": "桓謙", "entity_kind": "person"},
            {"mention_id": "m1", "surface": "殷仲文", "entity_kind": "person"},
        ]}
        payload = {"records": [
            {"mention_id": "m0", "semantic_type": "direct_person_form", "referent_role": "comparison participant", "anchor_mentions": [], "holder_mentions": [], "patron_or_possessor_mentions": [], "coreference_with": [], "distinct_from": ["m1"], "semantic_relations": [{"type": "comparison", "subject_mention_id": "m0", "object_mention_id": "m1", "predicate_surface": "比", "evidence_id": "e0"}], "confidence": "high", "explanation": "comparison"},
            {"mention_id": "m1", "semantic_type": "direct_person_form", "referent_role": "comparison participant", "anchor_mentions": [], "holder_mentions": [], "patron_or_possessor_mentions": [], "coreference_with": [], "distinct_from": ["m0"], "semantic_relations": [], "confidence": "high", "explanation": "comparison"},
        ]}
        result = reference_semantics.validate_reference_semantics(p, ledger, payload)
        self.assertEqual(1, len(result["relations"]))
        self.assertEqual("comparison", result["relations"][0]["relation_type"])

    def test_reviewer_required_failure_demotes(self):
        mention = {"mention_id": "m0", "story_id": "s", "surface": "逸少", "entity_kind": "person", "reference_form": "courtesy_name", "source_evidence_id": "e0"}
        semantic = {"records": [{"mention_id": "m0", "semantic_type": "direct_person_form", "confidence": "high"}]}
        constrained = {"records": [{"mention_id": "m0", "candidates": [{"candidate_key": "c0", "entity_type": "existing_person", "person_id": "person-001", "display_name": "王羲之"}], "judgment": {"preferred_candidate_key": "c0", "resolution": "candidate_supported"}, "hard_vetoes": {}}]}
        final = storage_gate.finalize_story({"story_id": "s", "valid_mentions": [mention]}, semantic, constrained, {"decisions": []}, {"reviews": [], "required_mentions": ["m0"], "provider_failure": True})
        self.assertEqual("review_required", final["records"][0]["final_state"])

    def test_semantic_heuristics_are_not_core_authorities(self):
        audit = heuristic_audit()
        forbidden = {"_trim_target_surface", "kinship suffix rules", "single-character special cases"}
        index = {row["heuristic"]: row["classification"] for row in audit["records"]}
        self.assertTrue(all(index[name] in {"deprecated", "compatibility_only", "remove_from_core_path"} for name in forbidden))

    def test_candidate_lookup_searches_existing_person_before_local_candidate(self):
        p = packet("王羲之善書")
        ledger = {"valid_mentions": [{"mention_id": "m0", "story_id": "test-story", "surface": "王羲之", "source_evidence_id": "e0", "entity_kind": "person", "reference_form": "full_name", "confidence": "high"}]}
        semantics = {"records": [{"mention_id": "m0", "semantic_type": "direct_person_form", "confidence": "high", "coreference_with": []}]}
        result = candidate_retrieval.build_candidate_sets(p, ledger, semantics)
        candidates = result["records"][0]["candidates"]
        self.assertTrue(any(row.get("person_id") == "person-001" for row in candidates))
        self.assertFalse(any(row.get("entity_type") == "local_candidate_person" for row in candidates))

    def test_hda2_suppression_overlay_blocks_contaminated_profile_form(self):
        p = packet("舊以桓謙比殷仲文")
        ledger = {"valid_mentions": [{"mention_id": "m0", "story_id": "test-story", "surface": "仲文", "source_evidence_id": "e0", "entity_kind": "person", "reference_form": "courtesy_name", "confidence": "high"}]}
        semantics = {"records": [{"mention_id": "m0", "semantic_type": "direct_person_form", "confidence": "high", "coreference_with": []}]}
        candidates = candidate_retrieval.build_candidate_sets(p, ledger, semantics)["records"][0]["candidates"]
        self.assertFalse(any(row.get("person_id") == "person-031" for row in candidates))

    def test_identity_payload_with_unknown_candidate_key_fails_closed(self):
        sets = {"records": [{"mention_id": "m0", "candidates": [{"candidate_key": "c0", "evidence": []}]}]}
        payload = {"judgments": [{
            "mention_id": "m0", "candidate_assessments": [{"candidate_key": "c9", "verdict": "support", "supporting_evidence_ids": [], "contradicting_evidence_ids": [], "reason_types": []}],
            "preferred_candidate_key": "c9", "resolution": "candidate_supported", "alternative_search_surfaces": [], "explanation": "invalid",
        }]}
        result = identity_judgment.validate_identity_judgments(packet(), sets, payload)
        self.assertFalse(result["judgments"])
        self.assertIn("invalid_preferred_candidate_key", result["rejected"][0]["errors"])

    def test_compositional_anchor_cannot_be_stored_as_referent(self):
        mention = {"mention_id": "m0", "story_id": "s", "surface": "家兄", "entity_kind": "person", "reference_form": "kinship_reference", "source_evidence_id": "e0"}
        semantic = {"records": [{"mention_id": "m0", "semantic_type": "compositional_kinship", "confidence": "high"}]}
        constrained = {"records": [{"mention_id": "m0", "candidates": [{"candidate_key": "c0", "entity_type": "existing_person", "person_id": "person-001"}], "judgment": {"preferred_candidate_key": "c0", "resolution": "candidate_supported"}, "hard_vetoes": {"c0": ["compositional_anchor_is_not_referent"]}}]}
        final = storage_gate.finalize_story({"story_id": "s", "valid_mentions": [mention]}, semantic, constrained, {"decisions": []}, {"reviews": [], "required_mentions": []})["records"][0]
        self.assertEqual("structural_reference", final["final_state"])
        self.assertIsNone(final["person_id"])

    def test_committed_projection_is_candidate_only_and_hash_locked(self):
        if not (OUT / "manifest.json").is_file():
            self.skipTest("SFH1 live projection not present")
        manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
        decisions = json.loads((OUT / "final-decisions.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["candidate_only"])
        self.assertFalse(manifest["canonical_write_back"])
        self.assertTrue(all(row["candidate_only"] and not row["canonical_write_back"] for row in decisions["records"]))
        self.assertEqual(manifest["artifact_hashes"]["final-decisions.json"], stable_hash(decisions))

    def test_no_mechanical_one_candidate_per_story(self):
        if not (OUT / "final-decisions.json").is_file():
            self.skipTest("SFH1 live projection not present")
        decisions = json.loads((OUT / "final-decisions.json").read_text(encoding="utf-8"))["records"]
        counts = {}
        for row in decisions:
            counts.setdefault(row["story_id"], 0)
            counts[row["story_id"]] += bool(row.get("candidate_person_id"))
        self.assertGreater(len(set(counts.values())), 1)

    def test_recalibrated_growth_preserves_old_series_separately(self):
        if not (OUT / "hge1-recalibrated-growth-series.json").is_file():
            self.skipTest("SFH1 live projection not present")
        result = json.loads((OUT / "hge1-recalibrated-growth-series.json").read_text(encoding="utf-8"))
        self.assertEqual(["baseline", "HGE1-WA-SFH1", "HGE1-WB-SFH1"], [row["wave"] for row in result["series"]])
        self.assertEqual(["baseline", "HGE1-WA", "HGE1-WB"], [row["wave"] for row in result["old_series"]])

    def test_provider_pending_controls_are_not_silently_passed(self):
        if not (OUT / "mention-audit.json").is_file():
            self.skipTest("SFH1 live projection not present")
        audit = json.loads((OUT / "mention-audit.json").read_text(encoding="utf-8"))["known_regressions"]
        self.assertEqual(0, audit["known_boundary_failures"])
        pending = [row for row in audit["checks"] if row["pending_provider"]]
        self.assertEqual(audit["pending_provider_controls"], sum(len(row["pending_provider"]) for row in pending))
        self.assertTrue(all(not row["passed"] for row in pending))


if __name__ == "__main__":
    unittest.main()
