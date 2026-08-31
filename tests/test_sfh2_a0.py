from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_a0.common import build_case_packet, load_inputs, stable_hash  # noqa: E402
from sfh2_a0.consistency import check_record, records_differ  # noqa: E402
from sfh2_a0.pipeline import (  # noqa: E402
    _final_state,
    critical_payload,
    primary_payload,
)
from sfh2_a0.retrieval import realize_semantic_record  # noqa: E402
from sfh2_a0.schemas import (  # noqa: E402
    adjudication_tool,
    critical_review_tool,
    semantic_record_tool,
    validate_semantic_payload,
)
from sfh2_a0.selection import build_selection, build_evaluation_gold  # noqa: E402


def _record(**overrides):
    value = {
        "mention_id": "m-1",
        "surface": "甲",
        "semantic_kind": "historical_person",
        "reference_type": "full_name",
        "referent": {"surface_form": "甲", "canonical_hint": "乙", "confidence": "high"},
        "occurrence_role": "scene_reference",
        "discourse": {"speaker_hint": "", "addressee_hint": "", "antecedent_hint": "", "self_reference_hint": ""},
        "relations": [],
        "confidence": "high",
        "supporting_evidence_ids": ["ev-1"],
        "attribute_type": "",
        "attribute_value": "",
        "bearer_hint": "",
        "abstain": False,
        "explanation": "evidence",
    }
    value.update(overrides)
    return value


class SFH22A0Tests(unittest.TestCase):
    def test_selection_is_exactly_the_fixed_twenty_cases_without_gold(self):
        selection = build_selection(load_inputs())
        self.assertEqual(20, selection["case_count"])
        self.assertFalse(any(key.startswith("expected_") for row in selection["cases"] for key in row))
        self.assertEqual(selection["selection_hash"], stable_hash({key: value for key, value in selection.items() if key != "selection_hash"}))
        self.assertEqual([], selection["selection_missing_specs"])

    def test_tools_are_strict_and_use_separate_pass_contracts(self):
        self.assertTrue(semantic_record_tool()["function"]["strict"])
        self.assertNotEqual(semantic_record_tool()["function"]["name"], critical_review_tool()["function"]["name"])
        self.assertNotEqual(critical_review_tool()["function"]["name"], adjudication_tool()["function"]["name"])
        self.assertEqual(
            {"record"},
            set(semantic_record_tool()["function"]["parameters"]["properties"]),
        )

    def test_exact_evidence_grounding_and_invalid_ids_fail_closed(self):
        packet = {"evidence": [{"evidence_id": "ev-1", "source_layer": "main_text", "text": "甲"}]}
        target = {"mention_id": "m-1", "surface": "甲"}
        payload = {"record": _record()}
        self.assertTrue(validate_semantic_payload(packet, target, payload)["valid"])
        bad = copy.deepcopy(payload)
        bad["record"]["supporting_evidence_ids"] = ["not-in-packet"]
        self.assertFalse(validate_semantic_payload(packet, target, bad)["valid"])
        bad_id = copy.deepcopy(payload)
        bad_id["record"]["referent"]["canonical_hint"] = "person-001"
        self.assertFalse(validate_semantic_payload(packet, target, bad_id)["valid"])

    def test_gold_never_enters_semantic_payload(self):
        inputs = load_inputs()
        selection = build_selection(inputs)
        case = selection["cases"][0]
        packet = build_case_packet(case, inputs)
        encoded = json.dumps(primary_payload(packet), ensure_ascii=False)
        self.assertNotIn("expected_identity", encoded)
        self.assertNotIn("expected_canonical_hint", encoded)
        self.assertTrue(packet["gold_visible_to_model"] is False)
        self.assertTrue(build_evaluation_gold()["evaluation_only"])

    def test_realization_allocates_candidate_after_semantic_proposal_on_registry_miss(self):
        inputs = {"people": {"people": []}, "aliases": {"aliases": []}}
        case = {"case_id": "c", "mention_id": "m", "story_id": "s", "surface": "short"}
        record = _record(mention_id="m", surface="short", referent={"surface_form": "short", "canonical_hint": "Absent Person", "confidence": "high"})
        result = realize_semantic_record(case, record, inputs)
        self.assertTrue(result["identity_created"])
        self.assertEqual("candidate_historical_person", result["candidate"]["entity_type"])
        self.assertTrue(result["candidate"]["candidate_person_id"].startswith("sfh2-a0-candidate-person-"))
        self.assertTrue(result["candidate_only"])
        self.assertFalse(result["canonical_write_back"])

    def test_registry_lookup_is_not_semantic_replacement(self):
        inputs = {"people": {"people": [{"person_id": "person-001", "canonical_name": "Retrieval Neighbor"}]}, "aliases": {"aliases": []}}
        case = {"case_id": "c", "mention_id": "m", "story_id": "s", "surface": "short"}
        record = _record(mention_id="m", surface="short", referent={"surface_form": "short", "canonical_hint": "Absent Person", "confidence": "high"})
        result = realize_semantic_record(case, record, inputs)
        self.assertEqual("Absent Person", result["candidate"]["display_name"])
        self.assertNotEqual("person-001", result["candidate"].get("person_id"))

    def test_consistency_only_reports_structured_conflict(self):
        record = _record(
            reference_type="addressee_reference",
            discourse={"speaker_hint": "", "addressee_hint": "Other", "antecedent_hint": "", "self_reference_hint": ""},
        )
        result = check_record(record, evidence_ids={"ev-1"})
        self.assertIn("internal_field_conflict", {flag["flag_type"] for flag in result["flags"]})
        self.assertNotIn("replacement_identity", json.dumps(result, ensure_ascii=False))

    def test_identity_distinctness_and_storage_safety_flags(self):
        record = _record(relations=[
            {"target_hint": "Z", "relation": "same_person", "confidence": "high", "evidence_ids": ["ev-1"]},
            {"target_hint": "Z", "relation": "different_person", "confidence": "high", "evidence_ids": ["ev-1"]},
        ])
        result = check_record(record, evidence_ids={"ev-1"})
        self.assertIn("identity_distinctness_conflict", {flag["flag_type"] for flag in result["flags"]})
        attr = _record(semantic_kind="person_attribute", occurrence_role="person_attribute")
        realization = {"identity_created": True, "core_graph_eligible": True}
        attr_result = check_record(attr, evidence_ids={"ev-1"}, realization=realization)
        kinds = {flag["flag_type"] for flag in attr_result["flags"]}
        self.assertIn("entity_storage_type_conflict", kinds)
        self.assertIn("source_role_projection_conflict", kinds)

    def test_non_person_and_source_roles_are_not_core_eligible(self):
        inputs = {"people": {"people": []}, "aliases": {"aliases": []}}
        case = {"case_id": "c", "mention_id": "m", "story_id": "s", "surface": "X"}
        for role, kind in (("citation_source_person", "historical_person"), ("annotation_person", "historical_person"), ("historical_exemplum", "historical_person"), ("person_attribute", "person_attribute"), ("collective_reference", "collective")):
            record = _record(semantic_kind=kind, occurrence_role=role, referent={"surface_form": "X", "canonical_hint": "X", "confidence": "high"})
            result = realize_semantic_record(case, record, inputs)
            self.assertFalse(result["core_graph_eligible"])
            if kind != "historical_person":
                self.assertFalse(result["identity_created"])

    def test_disagreement_is_formal_and_does_not_select_an_answer(self):
        left = _record()
        right = _record(referent={"surface_form": "甲", "canonical_hint": "他", "confidence": "high"})
        difference = records_differ(left, right)
        self.assertTrue(difference["different"])
        self.assertIn("referent", difference["fields"])
        state, failure, selected = _final_state(None, {}, {"flags": []})
        self.assertEqual("review_required", state)
        self.assertIsNone(selected)
        self.assertEqual("no_final_semantic_record", failure)

    def test_a0_runtime_has_no_surface_answer_table(self):
        for path in (ROOT / "scripts/sfh2_a0").glob("*.py"):
            content = path.read_text(encoding="utf-8")
            self.assertNotRegex(content, r"surface\s*==")
            self.assertNotRegex(content, r"surface\s+in\s+")


if __name__ == "__main__":
    unittest.main()
