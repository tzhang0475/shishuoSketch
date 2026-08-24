"""Offline contract tests for the consolidated HNG2 mainline."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import historical_context_algorithm as algorithm  # noqa: E402
import historical_entity_schema as schema  # noqa: E402
import run_hng2_consolidation as runner  # noqa: E402


class HNG2ConsolidationTests(unittest.TestCase):
    def test_strict_card_schema_is_closed_and_fully_required(self) -> None:
        parameters = algorithm.card_parameters_schema()
        self.assertFalse(parameters["additionalProperties"])
        self.assertEqual(set(parameters["properties"]), set(parameters["required"]))
        for array_name in ("entities", "relations", "temporal_assertions"):
            item = parameters["properties"][array_name]["items"]
            self.assertFalse(item["additionalProperties"])
            self.assertEqual(set(item["properties"]), set(item["required"]))
            self.assertTrue(item["description"])
            for field in item["properties"].values():
                self.assertTrue(field.get("description"))
        self.assertEqual(algorithm.function_definition()["function"]["strict"], True)
        self.assertEqual(algorithm.tool_choice()["function"]["name"], algorithm.FUNCTION_NAME)

    def test_candidate_blind_prompt_contains_only_target_and_passages(self) -> None:
        selection = runner.build_selection()
        cases, _, sources = runner.load_frozen_inputs()
        selected = selection["cases"][0]
        bundle = algorithm.select_evidence_bundle(
            cases[selected["case_id"]],
            runner.source_passages(selected["case_id"], cases[selected["case_id"]], sources),
        )
        payload = algorithm.prompt_payload(cases[selected["case_id"]], bundle)
        self.assertEqual(set(payload), {"target", "source_passages"})
        encoded = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("ResearchGap", encoded)
        self.assertNotIn("candidate_key", encoded)
        self.assertNotIn("person_id", encoded)
        self.assertNotIn("hard_constraints", encoded)

    def test_large_frozen_passage_is_compacted_without_losing_target_context(self) -> None:
        selection = runner.build_selection()
        cases, _, sources = runner.load_frozen_inputs()
        selected = next(row for row in selection["cases"] if row["surface"] == "廙")
        original = runner.source_passages(selected["case_id"], cases[selected["case_id"]], sources)
        bundle = algorithm.select_evidence_bundle(cases[selected["case_id"]], original)
        self.assertLessEqual(len(bundle["passages"]), 4)
        self.assertLessEqual(max(len(row["text"]) for row in bundle["passages"]), 900)
        self.assertGreater(bundle["original_total_chars"], bundle["selected_total_chars"])
        self.assertTrue(any("廙" in row["text"] for row in bundle["passages"]))

    def test_evidence_validation_rejects_items_independently(self) -> None:
        ref = "fixture"
        passages = {ref: {"ref": ref, "text": "王導父王敦年太康元年"}}
        payload = {
            "entities": [
                {"entity_key": "e0", "surface": "王導", "entity_kind": "named_person", "reference_form": "full_name", "evidence_ref": ref, "exact_span": "王導"},
                {"entity_key": "e1", "surface": "王敦", "entity_kind": "named_person", "reference_form": "full_name", "evidence_ref": ref, "exact_span": "王敦"},
            ],
            "relations": [
                {"relation_id": "r0", "subject_entity_key": "e0", "object_entity_key": "e1", "relation_surface": "父", "relation_class": "kinship", "evidence_ref": ref, "exact_span": "王導父王敦", "confidence": "high"},
            ],
            "temporal_assertions": [
                {"temporal_id": "t0", "subject_entity_key": "e0", "temporal_surface": "太康元年", "temporal_type": "reign_period", "reference_surface": "", "evidence_ref": ref, "exact_span": "not in source", "confidence": "medium"},
            ],
        }
        result = algorithm.validate_card(payload, passages)
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["valid_entities"]), 2)
        self.assertEqual(len(result["valid_relations"]), 1)
        self.assertEqual(len(result["valid_temporal_assertions"]), 0)
        self.assertEqual(len(result["rejected_temporal_assertions"]), 1)

    def test_identity_name_relation_propagates_existing_person(self) -> None:
        ref = "fixture"
        passages = {ref: {"ref": ref, "text": "廙即王廙"}}
        payload = {
            "entities": [
                {"entity_key": "e0", "surface": "廙", "entity_kind": "abbreviated_name", "reference_form": "abbreviated", "evidence_ref": ref, "exact_span": "廙"},
                {"entity_key": "e1", "surface": "王廙", "entity_kind": "named_person", "reference_form": "full_name", "evidence_ref": ref, "exact_span": "王廙"},
            ],
            "relations": [
                {"relation_id": "r0", "subject_entity_key": "e0", "object_entity_key": "e1", "relation_surface": "即", "relation_class": "identity_name", "evidence_ref": ref, "exact_span": "廙即王廙", "confidence": "high"},
            ],
            "temporal_assertions": [],
        }
        case = {
            "observation": {"surface": "廙", "source_ref": ref, "source_work": "fixture"},
            "candidates": [{"candidate_key": "c0", "canonical_name": "王廙", "known_forms": ["王廙"], "person_id": "person-053"}],
        }
        bundle = {"passages": [{"ref": ref, "text": passages[ref]["text"], "work": "fixture"}]}
        validation = algorithm.validate_card(payload, passages)
        projection = algorithm.normalize_card(validation, case=case, bundle=bundle)
        by_key = {row["entity_key"]: row for row in projection["entities"]}
        self.assertEqual(by_key["e1"]["identity_status"], "resolved_existing")
        self.assertEqual(by_key["e0"]["identity_status"], "resolved_existing")
        self.assertEqual(by_key["e0"]["resolved_person_id"], "person-053")
        self.assertFalse(projection["canonical_write_back"])

    def test_temporal_normalization_uses_h0a_era_cards(self) -> None:
        normalized = algorithm.normalize_temporal_surface("太康元年", algorithm._load_era_index())
        self.assertEqual(normalized["status"], "normalized_by_h0a_era")
        self.assertEqual(normalized["year"], 280)

    def test_offline_replay_has_no_api_or_controller_loop(self) -> None:
        selection = runner.ensure_selection()
        result = runner.run_offline(selection)
        self.assertEqual(result["api_calls"], 0)
        self.assertTrue(result["invariants"]["no_research_gap"])
        self.assertTrue(result["invariants"]["no_search_plan"])
        self.assertTrue(result["invariants"]["no_frontier_expansion"])

    def test_card_does_not_expand_schema_semantics(self) -> None:
        self.assertEqual(schema.ENTITY_KINDS & {"named_person"}, {"named_person"})
        self.assertNotIn("IdentityRecommendation", algorithm.card_parameters_schema()["description"])


if __name__ == "__main__":
    unittest.main()
