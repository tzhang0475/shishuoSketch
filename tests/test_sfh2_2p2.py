from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_2p.common import build_case_packet as base_build_case_packet  # noqa: E402
from sfh2_2p1.pipeline import _equivalence_payload, _proposal_payload  # noqa: E402
from sfh2_2p2.common import architecture_freeze, load_inputs, read_json, stable_hash  # noqa: E402
from sfh2_2p2.pipeline import _finalize, _human_review  # noqa: E402
from sfh2_2p2.retrieval import build_candidate_set  # noqa: E402
from sfh2_2p2.selection import build_selection  # noqa: E402
from sfh2_2p2.schemas import validate_equivalence_payload  # noqa: E402


FORBIDDEN_GOLD_KEYS = {
    "expected_identity", "expected_person_id", "expected_proposal_kind",
    "expected_identity_type", "expected_bearer", "expected_attribute_type",
    "expected_network_role", "must_not_resolve_to", "evaluation_mode",
}


def _keys(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        return set(value).union(*(set(_keys(child)) for child in value.values()))
    if isinstance(value, list):
        return set().union(*(set(_keys(child)) for child in value))
    return set()


class SFH22P2PilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inputs = load_inputs()
        cls.selection = read_json(ROOT / "data/annotation/sfh2-2p2-selection.json", {})

    def test_selection_is_exactly_frozen_blind_and_stratified(self) -> None:
        self.assertEqual(self.selection, build_selection(self.inputs))
        self.assertEqual(24, self.selection["case_count"])
        self.assertEqual(24, self.selection["blind_case_count"])
        self.assertEqual(0, self.selection["gold_case_count"])
        self.assertFalse(self.selection["gold_fields_present"])
        self.assertEqual(24, len({row["case_id"] for row in self.selection["cases"]}))
        self.assertEqual(24, len({row["mention_id"] for row in self.selection["cases"]}))
        self.assertEqual(self.selection["stratum_quotas"], self.selection["stratum_counts"])
        self.assertEqual("sfh2-2p2-blind-v1", self.selection["selection_seed"])

    def test_selection_and_frozen_artifacts_contain_no_gold_fields(self) -> None:
        self.assertFalse(FORBIDDEN_GOLD_KEYS.intersection(_keys(self.selection)))
        architecture = read_json(ROOT / "data/generated/sfh2-2p2/architecture-freeze.json", {})
        expected = architecture_freeze(self.selection["selection_hash"])
        self.assertEqual(expected, architecture)
        selection_hash = read_json(ROOT / "data/generated/sfh2-2p2/selection-hash.json", {})
        self.assertEqual(self.selection["selection_hash"], selection_hash["selection_hash"])

    def test_proposal_payload_is_blind(self) -> None:
        case = self.selection["cases"][0]
        packet = base_build_case_packet(case, self.inputs)
        payload = _proposal_payload(packet)
        self.assertTrue(payload["gold_not_supplied"])
        self.assertFalse(FORBIDDEN_GOLD_KEYS.intersection(_keys(payload)))
        encoded = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("expected_identity", encoded)
        self.assertNotIn("must_not_resolve_to", encoded)

    def test_proposal_candidate_is_first_and_candidate_only_on_registry_miss(self) -> None:
        # This uses the existing source packet only as a deterministic transport
        # fixture.  The proposal is intentionally supplied by the test, just as
        # the validated LLM response will be supplied during the pilot.
        packet = next(row for row in self.inputs["packets"]["packets"] if row.get("story_id") == "01-dexing-028")
        mention = next(row for row in self.inputs["mentions"]["records"] if row.get("story_id") == "01-dexing-028")
        case = {"case_id": "synthetic-proposal", "story_id": "01-dexing-028", "mention_id": mention["mention_id"], "surface": mention["surface"]}
        proposal = {
            "valid": True,
            "referent_surface": "勒",
            "referent_canonical_hint": "石勒",
            "entity_interpretation": {"reference_type": "abbreviated_reference", "network_role": "narrative_reference"},
            "candidate_proposal": {"proposal_kind": "historical_person", "display_name": "石勒", "supporting_evidence_ids": []},
            "abstain": False,
        }
        result_a = build_candidate_set(case, proposal, self.inputs, packet)
        result_b = build_candidate_set(case, proposal, self.inputs, packet)
        self.assertEqual(result_a, result_b)
        self.assertTrue(result_a["candidates"])
        self.assertEqual("c0", result_a["candidates"][0]["candidate_key"])
        self.assertEqual("llm_entity_proposal", result_a["candidates"][0]["proposal_origin"])
        self.assertTrue(result_a["candidates"][0]["candidate_person_id"].startswith("sfh2-2p2-candidate-person-"))
        self.assertTrue(all(row.get("candidate_only") is True and row.get("canonical_write_back") is False for row in result_a["candidates"]))

    def test_registry_lookup_does_not_replace_proposal_with_lexical_alternative(self) -> None:
        packet = {
            "story_id": "synthetic-story",
            "evidence": [{"evidence_id": "synthetic-evidence", "source_layer": "main_text", "text": "王獻之"}],
        }
        inputs = copy.deepcopy(self.inputs)
        inputs["mentions"] = {"records": [{
            "mention_id": "synthetic-mention", "story_id": "synthetic-story", "surface": "王子敬",
            "source_evidence_id": "synthetic-evidence", "entity_kind": "person", "reference_form": "courtesy_name",
        }]}
        inputs["packets"] = {"packets": [packet]}
        case = {"case_id": "proposal-over-retrieval", "story_id": "synthetic-story", "mention_id": "synthetic-mention", "surface": "王子敬"}
        proposal = {
            "valid": True, "referent_surface": "王子敬", "referent_canonical_hint": "王獻之",
            "entity_interpretation": {"reference_type": "courtesy_name", "network_role": "narrative_reference"},
            "candidate_proposal": {"proposal_kind": "historical_person", "display_name": "王獻之", "supporting_evidence_ids": ["synthetic-evidence"]},
            "abstain": False,
        }
        result = build_candidate_set(case, proposal, inputs, packet)
        self.assertEqual("王獻之", result["candidates"][0]["display_name"])
        self.assertEqual("llm_entity_proposal", result["candidates"][0]["proposal_origin"])

    def test_related_person_cannot_become_identity(self) -> None:
        case = {"case_id": "related-control", "mention_id": "m-1", "story_id": "s-1", "surface": "齊桓公"}
        proposal = {
            "valid": True, "referent_surface": "齊桓公", "referent_canonical_hint": "齊桓公",
            "entity_interpretation": {"network_role": "historical_exemplum"},
            "candidate_proposal": {"proposal_kind": "historical_person"}, "abstain": False,
        }
        candidate_set = {
            "candidates": [{"candidate_key": "c0", "display_name": "管仲", "entity_type": "existing_person", "person_id": "person-001"}],
            "hard_veto_person_ids": [], "proposal_candidate_key": "c0",
        }
        equivalence = {"same_person_candidate_key": None, "candidate_assessments": [{
            "candidate_key": "c0", "relation_to_target": "related_person", "confidence": "high",
            "supporting_evidence_ids": ["ev"], "contradicting_evidence_ids": [],
        }]}
        final = _finalize(case, proposal, candidate_set, equivalence)
        self.assertNotIn(final["final_state"], {"stable_entity_resolved", "local_candidate_resolved"})

    def test_hard_veto_demotes_instead_of_selecting_another_candidate(self) -> None:
        case = {"case_id": "veto-control", "mention_id": "m-1", "story_id": "s-1", "surface": "X"}
        proposal = {
            "valid": True, "referent_surface": "X", "referent_canonical_hint": "A",
            "entity_interpretation": {"network_role": "narrative_reference"},
            "candidate_proposal": {"proposal_kind": "historical_person"}, "abstain": False,
        }
        candidate_set = {
            "candidates": [
                {"candidate_key": "c0", "display_name": "A", "entity_type": "existing_person", "person_id": "person-a"},
                {"candidate_key": "c1", "display_name": "B", "entity_type": "existing_person", "person_id": "person-b"},
            ],
            "hard_veto_person_ids": ["person-a"], "proposal_candidate_key": "c0",
        }
        equivalence = {"same_person_candidate_key": "c0", "candidate_assessments": [{
            "candidate_key": "c0", "relation_to_target": "same_person", "confidence": "high",
            "supporting_evidence_ids": ["ev"], "contradicting_evidence_ids": [],
        }]}
        final = _finalize(case, proposal, candidate_set, equivalence)
        self.assertEqual("review_required", final["final_state"])
        self.assertEqual("hard_constraint_veto", final["failure_stage"])
        self.assertIsNone(final["selected_candidate"])

    def test_person_attribute_never_creates_a_person(self) -> None:
        case = {"case_id": "attribute-control", "mention_id": "m-1", "story_id": "s-1", "surface": "字景真"}
        proposal = {
            "valid": True, "referent_surface": "景真", "referent_canonical_hint": "",
            "entity_interpretation": {"network_role": "person_attribute"},
            "candidate_proposal": {"proposal_kind": "person_attribute", "attribute_type": "courtesy_name", "attribute_value": "景真"},
            "abstain": False,
        }
        final = _finalize(case, proposal, {"candidates": [], "hard_veto_person_ids": []}, None)
        self.assertEqual("structural_reference", final["final_state"])
        self.assertIsNone(final["selected_candidate"])

    def test_equivalence_schema_rejects_non_candidate_and_literal_null(self) -> None:
        result = validate_equivalence_payload(
            {"candidates": [{"candidate_key": "c0", "evidence": []}]},
            {"evidence": [{"evidence_id": "ev", "text": "source"}]},
            {"mention_id": "m"},
            {"reviews": [{
                "mention_id": "m", "target_proposal": "A",
                "candidate_assessments": [{"candidate_key": "c9", "relation_to_target": "related_person", "confidence": "high", "supporting_evidence_ids": [], "contradicting_evidence_ids": []}],
                "same_person_candidate_key": "null", "abstain": False, "explanation": "invalid",
            }]},
        )
        self.assertTrue(result["rejected"])
        self.assertFalse(result["reviews"])

    def test_human_review_bundle_has_no_gold_or_answer_labels(self) -> None:
        case = {"case_id": "blind", "story_id": "s", "mention_id": "m", "surface": "X"}
        packet = {"source_evidence": [{"evidence_id": "ev", "source_layer": "main_text", "text": "X"}], "target": {"surface": "X"}}
        review, markdown = _human_review([case], {"blind": packet}, {"blind": {}}, {"blind": {"candidates": []}}, {}, {"blind": {"final_state": "review_required"}})
        self.assertEqual("pending_external_review", review["historical_correctness"])
        self.assertFalse(FORBIDDEN_GOLD_KEYS.intersection(_keys(review)))
        self.assertNotIn("expected_identity", markdown)
        self.assertIn("Reviewer expected referent", markdown)

    def test_p2_candidate_namespace_is_deterministic(self) -> None:
        self.assertEqual(stable_hash({"x": "same"}), stable_hash({"x": "same"}))
        candidate_ids = [row.get("candidate_person_id") for row in read_json(ROOT / "data/generated/sfh2-2p2/candidate-registry.json", {"records": []}).get("records", [])]
        self.assertEqual(len(candidate_ids), len(set(candidate_ids)))


if __name__ == "__main__":
    unittest.main()
