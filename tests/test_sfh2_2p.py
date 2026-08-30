from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_2p.common import load_inputs  # noqa: E402
from sfh2_2p.pipeline import _evaluate  # noqa: E402
from sfh2_2p.retrieval import build_candidate_set  # noqa: E402
from sfh2_2p.schemas import validate_identity_payload  # noqa: E402
from sfh2_2p.selection import build_selection  # noqa: E402


class SFH22PPilotTests(unittest.TestCase):
    def test_selection_is_frozen_at_bounded_size_and_is_repeatable(self) -> None:
        selection_path = ROOT / "data/annotation/sfh2-2p-selection.json"
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
        self.assertEqual(selection, build_selection(load_inputs()))
        self.assertEqual(30, selection["case_count"])
        self.assertEqual(25, selection["gold_case_count"])
        self.assertEqual(5, selection["blind_case_count"])

    def test_semantic_referent_hint_creates_candidate_only_entity(self) -> None:
        inputs = copy.deepcopy(load_inputs())
        # Isolate the bridge itself from local full-name retrieval so this
        # regression proves that the validated L3 hint is retained as a
        # candidate source, rather than merely finding an incidental witness.
        target_mention = next(row for row in inputs["mentions"]["records"] if row.get("mention_id") == "sfh1-mention-3c86c11ce0a815d781eeb75c")
        inputs["mentions"] = {"records": [target_mention]}
        source_packet = next(row for row in inputs["packets"]["packets"] if row.get("story_id") == "01-dexing-028")
        inputs["packets"] = {"packets": [source_packet]}
        case = {
            "case_id": "hint-test",
            "story_id": "01-dexing-028",
            "mention_id": "sfh1-mention-3c86c11ce0a815d781eeb75c",
            "surface": "勒",
        }
        result = build_candidate_set(
            case,
            {
                "semantic_type": "abbreviated_person_reference",
                "referent_hint": "石勒",
                "supporting_evidence_ids": ["sfh1-ev-01-dexing-028-liu-annotation-004"],
                "network_role": "narrative_reference",
            },
            inputs,
        )
        shile = [row for row in result["candidates"] if row.get("display_name") == "石勒"]
        self.assertEqual(1, len(shile))
        self.assertEqual("candidate_historical_person", shile[0]["entity_type"])
        self.assertIn("semantic_referent_hint", shile[0]["retrieval_basis"])
        self.assertTrue(result["candidate_only"])
        self.assertFalse(result["canonical_write_back"])
        self.assertFalse(any(row.get("person_id") == "person-054" for row in result["candidates"]))

    def test_direct_full_name_uses_existing_registry_before_candidate_creation(self) -> None:
        inputs = load_inputs()
        synthetic = copy.deepcopy(inputs)
        synthetic["mentions"] = {"records": [{
            "mention_id": "synthetic-full-name",
            "story_id": "synthetic-story",
            "surface": "王羲之",
            "source_evidence_id": "synthetic-evidence",
            "entity_kind": "person",
            "reference_form": "full_name",
        }]}
        synthetic["packets"] = {"packets": [{
            "story_id": "synthetic-story",
            "evidence": [{"evidence_id": "synthetic-evidence", "source_layer": "main_text", "text": "王羲之"}],
        }]}
        result = build_candidate_set(
            {"case_id": "synthetic", "story_id": "synthetic-story", "mention_id": "synthetic-full-name", "surface": "王羲之"},
            {"semantic_type": "direct_person_form", "referent_hint": "", "network_role": "narrative_participant"},
            synthetic,
        )
        matches = [row for row in result["candidates"] if row.get("person_id") == "person-001"]
        self.assertEqual(1, len(matches))
        self.assertFalse(any(row.get("entity_type") == "candidate_historical_person" and row.get("display_name") == "王羲之" for row in result["candidates"]))

    def test_unvalidated_context_substring_cannot_create_candidate(self) -> None:
        inputs = load_inputs()
        synthetic = copy.deepcopy(inputs)
        synthetic["mentions"] = {"records": [{
            "mention_id": "synthetic-target",
            "story_id": "synthetic-story",
            "surface": "某",
            "source_evidence_id": "synthetic-evidence",
            "entity_kind": "person",
            "reference_form": "abbreviated_reference",
        }]}
        synthetic["packets"] = {"packets": [{
            "story_id": "synthetic-story",
            "evidence": [{"evidence_id": "synthetic-evidence", "source_layer": "main_text", "text": "某人與王隱相見"}],
        }]}
        result = build_candidate_set(
            {"case_id": "synthetic", "story_id": "synthetic-story", "mention_id": "synthetic-target", "surface": "某"},
            {"semantic_type": "uncertain", "referent_hint": "", "network_role": "uncertain"},
            synthetic,
        )
        self.assertFalse(any(row.get("person_id") == "person-054" for row in result["candidates"]))
        self.assertFalse(result["candidates"])

    def test_explicit_semantic_distinctness_is_carried_as_a_hard_veto(self) -> None:
        inputs = load_inputs()
        case = next(row for row in build_selection(inputs)["cases"] if row["case_family"] == "negative_control" and row["surface"] == "潁")
        result = build_candidate_set(case, {
            "semantic_type": "direct_person_form",
            "referent_hint": "",
            "network_role": "narrative_reference",
            "distinct_from": ["sfh1-mention-a03cf9b55016268f8bf01cae"],
        }, inputs)
        self.assertIn("person-022", result["hard_veto_person_ids"])
        self.assertTrue(any(item["distinct_surface"] == "鄧伯道" for item in result["hard_vetoes"]))

    def test_literal_null_or_unknown_candidate_fails_closed(self) -> None:
        inputs = load_inputs()
        packet = next(row for row in inputs["packets"]["packets"] if row["story_id"] == "01-dexing-028")
        candidate_sets = {"records": [{"unit_id": "m0", "candidates": [{"candidate_key": "c0", "evidence": []}]}]}
        payload = {"judgments": [{
            "unit_id": "m0",
            "candidate_assessments": [{"candidate_key": "c9", "verdict": "support", "supporting_evidence_ids": [], "contradicting_evidence_ids": [], "reason_types": []}],
            "preferred_candidate_key": "null",
            "resolution": "candidate_supported",
            "explanation": "invalid",
        }]}
        result = validate_identity_payload(candidate_sets, packet, payload)
        self.assertFalse(result["judgments"])
        self.assertTrue(result["rejected"])
        self.assertIn("literal_null_candidate_key", result["rejected"][0]["errors"])

    def test_pilot_does_not_mutate_alias_registry(self) -> None:
        audit = json.loads((ROOT / "data/generated/sfh2-2p/alias-safety-audit.json").read_text(encoding="utf-8"))
        self.assertEqual(audit["aliases_before_sha256"], audit["aliases_after_sha256"])
        self.assertEqual(0, audit["new_global_aliases"])
        self.assertEqual(0, audit["substring_derived_candidates"])

    def test_non_identity_gold_controls_do_not_hide_candidate_promotions(self) -> None:
        selection = {"cases": [{
            "case_id": "structural-control",
            "evaluation_mode": "reviewed_gold",
            "expected_identity_type": "structural",
            "expected_identity": None,
        }]}
        final = [{
            "case_id": "structural-control",
            "final_state": "local_candidate_resolved",
            "selected_candidate": {"candidate_key": "c0", "display_name": "不應被接受"},
            "failure_stage": None,
        }]
        metrics, rows = _evaluate(selection, {"structural-control": {}}, final)
        self.assertEqual("semantic_identity_failure", rows[0]["category"])
        self.assertEqual(1, metrics["semantic_false_positive_count"])
        self.assertEqual(1, metrics["high_confidence_false_positives"])

    def test_non_identity_gold_controls_accept_safe_abstention(self) -> None:
        selection = {"cases": [{
            "case_id": "contextual-control",
            "evaluation_mode": "reviewed_gold",
            "expected_identity_type": "contextual",
            "expected_identity": None,
        }]}
        final = [{
            "case_id": "contextual-control",
            "final_state": "review_required",
            "selected_candidate": None,
            "failure_stage": "identity_evidence_insufficient",
        }]
        metrics, rows = _evaluate(selection, {"contextual-control": {}}, final)
        self.assertEqual("appropriate_abstention", rows[0]["category"])
        self.assertEqual(0, metrics["semantic_false_positive_count"])


if __name__ == "__main__":
    unittest.main()
