from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import historical_context_algorithm as algorithm  # noqa: E402
import run_hng2_read_fill_validation as runner  # noqa: E402
import run_hng2_schema_controller_hardening as hardening  # noqa: E402


class HistoricalReadFillAlgorithmTests(unittest.TestCase):
    def setUp(self) -> None:
        self.windows = [
            algorithm.prepare_evidence_window(
                {
                    "ref": "ref-1",
                    "work": "晉書",
                    "source_form": "punctuated",
                    "text": "車騎將軍陳騫爲高平公。",
                    "evidence_text": "車騎將軍陳騫爲高平公。",
                }
            )
        ]

    def test_four_strict_tools_have_closed_required_objects(self) -> None:
        names = set()
        for lane in ("person_read", "person_fill", "temporal_read", "temporal_fill"):
            function = algorithm.read_fill_function_definition(lane)["function"]
            self.assertTrue(function["strict"])
            names.add(function["name"])

            def check(value):
                if not isinstance(value, dict):
                    return
                if value.get("type") == "object":
                    self.assertFalse(value["additionalProperties"])
                    self.assertEqual(set(value["properties"]), set(value["required"]))
                for child in value.values():
                    if isinstance(child, dict):
                        check(child)
                    elif isinstance(child, list):
                        for item in child:
                            check(item)

            check(function["parameters"])
        self.assertEqual(len(names), 4)

    def test_model_visible_projection_and_exact_validation_share_text(self) -> None:
        projected = algorithm.prepare_evidence_window(
            {"ref": "r", "text": "{{YL|太康元年}}，[[王廙|世將]]至。"}
        )
        self.assertEqual(projected["evidence_text"], "太康元年，世將至。")
        valid = algorithm.validate_temporal_read(
            {
                "observations": [
                    {
                        "observation_id": "t0",
                        "temporal_surface": "太康元年",
                        "temporal_kind": "era_year",
                        "temporal_role": "scene_time",
                        "reference_surface": "",
                        "evidence_ref": "r",
                        "exact_span": "太康元年",
                        "certainty": "explicit",
                    }
                ]
            },
            [projected],
        )
        self.assertEqual(len(valid["valid_observations"]), 1)
        invalid = algorithm.validate_temporal_read(
            {"observations": [{**valid["valid_observations"][0], "exact_span": "{{YL|太康元年}}"}]},
            [projected],
        )
        self.assertEqual(invalid["rejected_observations"][0]["reason"], "evidence_span_not_found")

    def test_person_read_rejects_one_bad_observation_only(self) -> None:
        payload = {
            "observations": [
                {
                    "observation_id": "o0", "observation_kind": "office_title",
                    "subject_surface": "陳騫", "predicate_surface": "車騎將軍", "object_surface": "",
                    "evidence_ref": "ref-1", "exact_span": "車騎將軍陳騫", "certainty": "explicit",
                },
                {
                    "observation_id": "o1", "observation_kind": "office_title",
                    "subject_surface": "陳騫", "predicate_surface": "太尉", "object_surface": "",
                    "evidence_ref": "ref-1", "exact_span": "不存在", "certainty": "explicit",
                },
            ]
        }
        result = algorithm.validate_person_read(payload, self.windows)
        self.assertEqual(len(result["valid_observations"]), 1)
        self.assertEqual(len(result["rejected_observations"]), 1)

    def test_person_fill_uses_grounded_entities_and_broad_relation(self) -> None:
        payload = {
            "entities": [
                {"entity_key": "e0", "surface": "陳騫", "entity_kind": "named_person", "reference_form": "full_name", "evidence_refs": ["ref-1"]},
                {"entity_key": "e1", "surface": "高平公", "entity_kind": "person_title", "reference_form": "title_only", "evidence_refs": ["ref-1"]},
            ],
            "relations": [
                {
                    "relation_id": "r0", "subject_entity_key": "e0", "object_entity_key": "e1",
                    "relation_surface": "爲", "relation_class": "institutional", "evidence_ref": "ref-1",
                    "exact_span": "陳騫爲高平公", "confidence": "high",
                }
            ],
        }
        result = algorithm.validate_person_fill(payload, self.windows)
        self.assertEqual(len(result["valid_entities"]), 2)
        self.assertEqual(len(result["valid_relations"]), 1)

    def test_contextual_structural_entity_does_not_replace_person_target(self) -> None:
        windows = [algorithm.prepare_evidence_window({"ref": "r", "text": "虞喜弟預女。", "evidence_text": "虞喜弟預女。"})]
        payload = {
            "entities": [
                {"entity_key": "e0", "surface": "虞喜", "entity_kind": "named_person", "reference_form": "full_name", "evidence_refs": ["r"]},
                {"entity_key": "e1", "surface": "喜弟預女", "entity_kind": "structural_kinship_expression", "reference_form": "kinship_plus_name", "evidence_refs": ["r"]},
            ],
            "relations": [],
        }
        result = algorithm.validate_person_fill(payload, windows)
        case = {"observation": {"surface": "虞喜"}, "seed": {}, "candidates": []}
        normalized = algorithm.normalize_person_fill(result, case=case, windows=windows)
        by_surface = {row["surface"]: row["identity_status"] for row in normalized["entities"]}
        self.assertNotEqual(by_surface["虞喜"], "not_single_person")
        self.assertEqual(by_surface["喜弟預女"], "not_single_person")

    def test_later_outcome_is_not_scene_constraint(self) -> None:
        windows = [algorithm.prepare_evidence_window({"ref": "hng2c1-shishuo-06-yaliang-017-liu-annotation-001", "text": "咸和六年遇害", "evidence_text": "咸和六年遇害"})]
        payload = {
            "temporal_assertions": [
                {
                    "temporal_id": "t0", "temporal_surface": "咸和六年", "temporal_type": "exact_year",
                    "temporal_role": "later_outcome", "reference_surface": "遇害", "evidence_ref": windows[0]["ref"],
                    "exact_span": "咸和六年遇害", "confidence": "high",
                }
            ]
        }
        validation = algorithm.validate_temporal_fill(payload, windows)
        projection = algorithm.normalize_story_temporal(validation, story_id="06-yaliang-017")
        self.assertFalse(projection["temporal_assertions"][0]["scene_constraint_candidate"])


class ReadFillSelectionTests(unittest.TestCase):
    def test_five_heldout_pairs_are_deterministic_and_fresh(self) -> None:
        cases, _, _ = hardening.load_inputs()
        first = runner.derive_heldout_selection(cases)
        second = runner.derive_heldout_selection(cases)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 5)
        self.assertEqual(len({row["story_id"] for row in first}), 5)
        self.assertEqual(len({row["person_id"] for row in first}), 5)
        hng0 = runner.read_json(ROOT / "data/generated/hng0/hng0-selection.json", {})
        hng1 = runner.read_json(ROOT / "data/generated/hng1/hng1-selection.json", {})
        excluded = {row["person_id"] for row in hng0["people"] + hng1["people"]}
        self.assertFalse(excluded & {row["person_id"] for row in first})

    def test_selection_freezes_exactly_twenty_heldout_semantic_calls(self) -> None:
        selection = runner.build_selection()
        self.assertEqual(selection["heldout_count"], 5)
        self.assertEqual(selection["heldout_semantic_call_count"], 20)
        self.assertTrue(selection["frozen_before_live"])
        for row in selection["temporal_regression"]:
            if row["category"] not in {"reign_bounded", "event_bounded"}:
                continue
            anchor = runner._h0a_expected(row["story_id"])["anchor"]
            self.assertIsNotNone(anchor)
            self.assertEqual(anchor["precision"], row["category"])


if __name__ == "__main__":
    unittest.main()
