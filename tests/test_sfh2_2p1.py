from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_2p.common import load_inputs  # noqa: E402
from sfh2_2p1.pipeline import _equivalence_payload, _finalize, _proposal_payload  # noqa: E402
from sfh2_2p1.retrieval import build_proposal_candidate_set  # noqa: E402
from sfh2_2p1.schemas import (  # noqa: E402
    entity_proposal_tool,
    identity_equivalence_tool,
    validate_entity_proposal_payload,
    validate_equivalence_payload,
)
from sfh2_2p1.selection import build_selection  # noqa: E402


class SFH22P1PilotTests(unittest.TestCase):
    def test_selection_is_exactly_the_ten_frozen_primary_cases(self) -> None:
        selection = build_selection(load_inputs())
        self.assertEqual(10, selection["case_count"])
        self.assertEqual(10, selection["gold_case_count"])
        self.assertEqual(0, selection["blind_case_count"])
        by_surface = {row["surface"]: row for row in selection["cases"]}
        self.assertEqual("王獻之", by_surface["王子敬"]["expected_identity"])
        self.assertEqual("historical_person", by_surface["潁"]["expected_proposal_kind"])
        self.assertEqual("person_attribute", by_surface["字景真"]["expected_proposal_kind"])

    def test_proposal_packet_has_no_evaluation_gold(self) -> None:
        inputs = load_inputs()
        case = next(row for row in build_selection(inputs)["cases"] if row["surface"] == "勒")
        from sfh2_2p1.common import build_case_packet

        packet = build_case_packet(case, inputs)
        payload = _proposal_payload(packet)
        encoded = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("expected_identity", encoded)
        self.assertNotIn("must_not_resolve_to", encoded)
        self.assertTrue(payload["gold_not_supplied"])

    def test_proposal_schema_accepts_registry_miss_without_person_id(self) -> None:
        packet = {"evidence": [{"evidence_id": "ev-1", "source_layer": "main_text", "text": "勒為石勒所獲"}]}
        target = {"mention_id": "m-1", "surface": "勒"}
        payload = {
            "proposals": [{
                "mention_id": "m-1", "surface": "勒",
                "entity_interpretation": {"entity_kind": "person", "reference_type": "abbreviated_reference", "network_role": "narrative_reference"},
                "referent_surface": "勒", "referent_canonical_hint": "石勒",
                "candidate_proposal": {"proposal_kind": "historical_person", "display_name": "石勒", "confidence": "high", "attribute_type": "", "attribute_value": "", "bearer_canonical_hint": "", "supporting_evidence_ids": ["ev-1"]},
                "alternatives": [], "abstain": False, "explanation": "The source names the referent.",
            }]
        }
        result = validate_entity_proposal_payload(packet, target, payload)
        self.assertFalse(result["rejected"])
        self.assertEqual("石勒", result["proposals"][0]["referent_canonical_hint"])
        self.assertNotIn("person-", json.dumps(result["proposals"][0], ensure_ascii=False))

    def test_proposal_candidate_is_first_and_deterministic(self) -> None:
        inputs = load_inputs()
        case = next(row for row in build_selection(inputs)["cases"] if row["surface"] == "勒")
        proposal = {
            "case_id": case["case_id"], "mention_id": case["mention_id"], "surface": "勒", "valid": True,
            "referent_surface": "勒", "referent_canonical_hint": "石勒",
            "entity_interpretation": {"network_role": "narrative_reference", "reference_type": "abbreviated_reference"},
            "candidate_proposal": {"proposal_kind": "historical_person", "display_name": "石勒", "supporting_evidence_ids": [case["source_evidence_id"]]},
            "alternatives": [], "abstain": False,
        }
        result_a = build_proposal_candidate_set(case, proposal, inputs, next(row for row in inputs["packets"]["packets"] if row["story_id"] == case["story_id"]))
        result_b = build_proposal_candidate_set(case, proposal, inputs, next(row for row in inputs["packets"]["packets"] if row["story_id"] == case["story_id"]))
        self.assertEqual("c0", result_a["candidates"][0]["candidate_key"])
        self.assertEqual("石勒", result_a["candidates"][0]["display_name"])
        self.assertEqual(result_a, result_b)
        self.assertTrue(result_a["candidates"][0]["candidate_person_id"].startswith("sfh2-2p1-candidate-person-"))
        self.assertFalse(any(row.get("person_id") == "person-054" for row in result_a["candidates"]))

    def test_person_attribute_proposal_never_creates_person_candidate(self) -> None:
        inputs = load_inputs()
        case = next(row for row in build_selection(inputs)["cases"] if row["surface"] == "字景真")
        proposal = {
            "case_id": case["case_id"], "mention_id": case["mention_id"], "surface": "字景真", "valid": True,
            "referent_surface": "景真", "referent_canonical_hint": "",
            "entity_interpretation": {"network_role": "person_attribute", "reference_type": "person_attribute"},
            "candidate_proposal": {"proposal_kind": "person_attribute", "display_name": "", "attribute_type": "courtesy_name", "attribute_value": "景真", "bearer_canonical_hint": "桓亮", "supporting_evidence_ids": [case["source_evidence_id"]]},
            "alternatives": [], "abstain": False,
        }
        packet = next(row for row in inputs["packets"]["packets"] if row["story_id"] == case["story_id"])
        result = build_proposal_candidate_set(case, proposal, inputs, packet)
        self.assertFalse(result["candidates"])
        final = _finalize(case, proposal, result, None)
        self.assertEqual("structural_reference", final["final_state"])
        self.assertIsNone(final["selected_candidate"])

    def test_related_person_cannot_promote_identity(self) -> None:
        case = {"case_id": "synthetic", "mention_id": "m-1", "story_id": "s-1", "surface": "齊桓公"}
        proposal = {
            "valid": True, "referent_surface": "齊桓公", "referent_canonical_hint": "齊桓公",
            "entity_interpretation": {"network_role": "historical_exemplum"},
            "candidate_proposal": {"proposal_kind": "historical_person"}, "abstain": False,
        }
        candidates = {"candidates": [{"candidate_key": "c0", "display_name": "管仲", "entity_type": "candidate_historical_person"}], "hard_veto_person_ids": [], "proposal_candidate_key": "c0"}
        equivalence = {"same_person_candidate_key": None, "candidate_assessments": [{"candidate_key": "c0", "relation_to_target": "related_person", "supporting_evidence_ids": ["ev"], "contradicting_evidence_ids": [], "confidence": "high"}]}
        final = _finalize(case, proposal, candidates, equivalence)
        self.assertNotIn(final["final_state"], {"stable_entity_resolved", "local_candidate_resolved"})

    def test_declared_same_person_key_handles_duplicate_candidate_representations(self) -> None:
        case = {"case_id": "synthetic-duplicate", "mention_id": "m-1", "story_id": "s-1", "surface": "車騎"}
        proposal = {
            "valid": True, "referent_surface": "車騎", "referent_canonical_hint": "謝玄",
            "entity_interpretation": {"network_role": "narrative_reference"},
            "candidate_proposal": {"proposal_kind": "historical_person"}, "abstain": False,
        }
        candidates = {
            "candidates": [
                {"candidate_key": "c0", "display_name": "謝玄", "entity_type": "candidate_historical_person", "candidate_person_id": "sfh2-2p1-candidate-person-x"},
                {"candidate_key": "c1", "display_name": "玄", "entity_type": "candidate_historical_person", "candidate_person_id": "sfh2-candidate-person-y"},
            ],
            "hard_veto_person_ids": [], "proposal_candidate_key": "c0",
        }
        equivalence = {
            "same_person_candidate_key": "c0",
            "candidate_assessments": [
                {"candidate_key": "c0", "relation_to_target": "same_person", "supporting_evidence_ids": ["ev"], "contradicting_evidence_ids": []},
                {"candidate_key": "c1", "relation_to_target": "same_person", "supporting_evidence_ids": ["ev"], "contradicting_evidence_ids": []},
            ],
        }
        final = _finalize(case, proposal, candidates, equivalence)
        self.assertEqual("local_candidate_resolved", final["final_state"])
        self.assertEqual("c0", final["selected_candidate"]["candidate_key"])

    def test_equivalence_validator_rejects_literal_null_and_missing_candidate_assessment(self) -> None:
        candidate_set = {"candidates": [{"candidate_key": "c0", "evidence": []}, {"candidate_key": "c1", "evidence": []}]}
        packet = {"evidence": [{"evidence_id": "ev-1", "text": "source"}]}
        target = {"mention_id": "m-1"}
        result = validate_equivalence_payload(candidate_set, packet, target, {
            "reviews": [{
                "mention_id": "m-1", "target_proposal": "X", "candidate_assessments": [{"candidate_key": "c0", "relation_to_target": "same_person", "confidence": "high", "supporting_evidence_ids": ["ev-1"], "contradicting_evidence_ids": []}],
                "same_person_candidate_key": "null", "abstain": False, "explanation": "bad",
            }]
        })
        self.assertTrue(result["rejected"])
        self.assertIn("literal_null_candidate_key", result["rejected"][0]["errors"])

    def test_equivalence_packet_does_not_expose_internal_person_ids(self) -> None:
        packet = {"target": {"surface": "齊桓公"}, "source_evidence": [{"evidence_id": "ev", "text": "source"}]}
        proposal = {"referent_surface": "齊桓公", "referent_canonical_hint": "齊桓公", "candidate_proposal": {"proposal_kind": "historical_person", "supporting_evidence_ids": ["ev"]}, "entity_interpretation": {}, "alternatives": []}
        candidate_set = {"candidates": [{"candidate_key": "c0", "display_name": "齊桓公", "person_id": "person-001", "candidate_person_id": "", "entity_type": "existing_person", "evidence": []}]}
        payload = _equivalence_payload(packet, proposal, candidate_set)
        encoded = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("person-001", encoded)
        self.assertIn("c0", encoded)


if __name__ == "__main__":
    unittest.main()
