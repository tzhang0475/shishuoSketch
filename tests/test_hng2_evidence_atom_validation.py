from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import historical_context_algorithm as algorithm  # noqa: E402
import run_hng2_evidence_atom_validation as runner  # noqa: E402


class EvidenceAtomContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.windows = [
            algorithm.prepare_evidence_window(
                {
                    "ref": "r0",
                    "text": "車騎將軍陳騫爲高平公；正始之音；年十九，咸和六年遇害。",
                    "evidence_text": "車騎將軍陳騫爲高平公；正始之音；年十九，咸和六年遇害。",
                }
            )
        ]

    def test_strict_read_schemas_are_closed(self) -> None:
        for lane, expected in (
            ("person_read", algorithm.PERSON_ATOM_FUNCTION),
            ("temporal_read", algorithm.TEMPORAL_ATOM_FUNCTION),
        ):
            function = algorithm.evidence_atom_function_definition(lane)["function"]
            self.assertEqual(function["name"], expected)
            self.assertTrue(function["strict"])

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

    def test_person_atom_rejection_reasons_are_exact(self) -> None:
        base = {
            "atom_id": "p0",
            "atom_kind": "office_title",
            "subject_surface": "陳騫",
            "predicate_surface": "車騎將軍",
            "object_surface": "高平公",
            "evidence_ref": "r0",
            "exact_span": "車騎將軍陳騫爲高平公",
            "certainty": "explicit",
        }
        self.assertEqual(len(algorithm.validate_person_atoms({"atoms": [base]}, self.windows)["valid_atoms"]), 1)
        mutations = (
            ({"exact_span": "不存在"}, "exact_span_missing"),
            ({"subject_surface": "司馬炎"}, "subject_not_in_span"),
            ({"predicate_surface": "任命"}, "predicate_not_in_span"),
            ({"object_surface": "太尉"}, "object_not_in_span"),
        )
        for mutation, expected in mutations:
            result = algorithm.validate_person_atoms({"atoms": [{**base, **mutation}]}, self.windows)
            self.assertEqual(result["rejected_atoms"][0]["reason"], expected)

    def test_temporal_atom_rejection_reasons_and_quoted_precedent(self) -> None:
        base = {
            "atom_id": "t0",
            "temporal_surface": "正始",
            "reference_surface": "正始之音",
            "role_hint": "quoted_precedent",
            "evidence_ref": "r0",
            "exact_span": "正始之音",
            "certainty": "explicit",
        }
        result = algorithm.validate_temporal_atoms({"atoms": [base]}, self.windows)
        self.assertEqual(result["valid_atoms"], [base])
        mutations = (
            ({"exact_span": "正始之聲"}, "exact_span_missing"),
            ({"temporal_surface": "嘉平"}, "temporal_surface_not_in_span"),
            ({"reference_surface": "清談"}, "reference_surface_not_in_span"),
        )
        for mutation, expected in mutations:
            result = algorithm.validate_temporal_atoms({"atoms": [{**base, **mutation}]}, self.windows)
            self.assertEqual(result["rejected_atoms"][0]["reason"], expected)

    def test_fill_receives_only_validated_atom_windows(self) -> None:
        grounded = {
            "valid_atoms": [
                {
                    "atom_id": "p0", "atom_kind": "identity_name",
                    "subject_surface": "陳騫", "predicate_surface": "", "object_surface": "",
                    "evidence_ref": "r0", "exact_span": "陳騫", "certainty": "explicit",
                }
            ]
        }
        prompt = algorithm.person_atom_fill_prompt({"surface": "陳騫"}, grounded, self.windows)
        self.assertEqual(prompt["validated_evidence_atoms"], grounded["valid_atoms"])
        self.assertEqual([row["ref"] for row in prompt["source_passages"]], ["r0"])
        empty = algorithm.person_atom_fill_prompt({"surface": "陳騫"}, {"valid_atoms": []}, self.windows)
        self.assertEqual(empty["source_passages"], [])


class NormalizationGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.windows = [algorithm.prepare_evidence_window({"ref": "r", "text": "少孤與孟陋居武昌陽新縣", "evidence_text": "少孤與孟陋居武昌陽新縣"})]
        self.case = {"observation": {"surface": "少孤"}, "seed": {}, "candidates": []}

    def test_nonperson_never_enters_person_resolver(self) -> None:
        validation = {
            "valid_entities": [
                {"entity_key": "e0", "surface": "少孤", "entity_kind": "not_person", "reference_form": "full_name", "evidence_refs": ["r"]}
            ],
            "valid_relations": [],
        }
        result = algorithm.normalize_person_fill(validation, case=self.case, windows=self.windows)
        entity = result["entities"][0]
        self.assertEqual(entity["person_resolution"], "not_applicable")
        self.assertIsNone(entity["resolved_person_id"])
        self.assertEqual(entity["identity_status"], "not_person")

    def test_normalized_nonidentity_self_relation_is_rejected(self) -> None:
        validation = {
            "valid_entities": [
                {"entity_key": "e0", "surface": "少孤", "entity_kind": "courtesy_name", "reference_form": "courtesy", "evidence_refs": ["r"]},
                {"entity_key": "e1", "surface": "孟陋", "entity_kind": "named_person", "reference_form": "full_name", "evidence_refs": ["r"]},
            ],
            "valid_relations": [
                {"relation_id": "r0", "subject_entity_key": "e0", "object_entity_key": "e1", "relation_surface": "與", "relation_class": "interaction", "evidence_ref": "r", "exact_span": "少孤與孟陋", "confidence": "high"}
            ],
        }
        result = algorithm.normalize_person_fill(validation, case=self.case, windows=self.windows)
        self.assertEqual(result["relations"], [])
        self.assertEqual(result["rejected_normalized_relations"][0]["reason"], "collapsed_self_relation")
        self.assertEqual(result["rejected_normalized_relations"][0]["relation"]["relation_id"], "r0")

    def test_unique_visible_full_name_propagates_identity_to_abbreviation(self) -> None:
        windows = [algorithm.prepare_evidence_window({"ref": "r", "text": "眾拒王廙，廙遂行", "evidence_text": "眾拒王廙，廙遂行"})]
        case = {
            "observation": {"surface": "廙"},
            "candidates": [{"candidate_key": "c0", "person_id": "person-053", "canonical_name": "王廙", "known_forms": ["王廙", "世將"]}],
            "constraint_checks": [],
            "seed": {},
        }
        validation = {
            "valid_entities": [{"entity_key": "e0", "surface": "廙", "entity_kind": "abbreviated_name", "reference_form": "abbreviated", "evidence_refs": ["r"]}],
            "valid_relations": [],
        }
        result = algorithm.normalize_person_fill(validation, case=case, windows=windows)
        target = next(row for row in result["entities"] if row["surface"] == "廙")
        self.assertEqual(target["resolved_person_id"], "person-053")
        self.assertEqual(target["resolution_method"], "identity_name_assertion")
        self.assertEqual(result["source_grounded_identity_expansions"][0]["full_name_surface"], "王廙")

    def test_nonidentity_edges_and_hard_conflicts_do_not_propagate(self) -> None:
        base_case = {
            "observation": {"surface": "廙"},
            "candidates": [{"candidate_key": "c0", "person_id": "person-053", "canonical_name": "王廙", "known_forms": ["王廙"]}],
            "constraint_checks": [],
            "seed": {},
        }
        for relation_class in ("interaction", "kinship", "institutional"):
            windows = [algorithm.prepare_evidence_window({"ref": "r", "text": "廙與甲", "evidence_text": "廙與甲"})]
            validation = {
                "valid_entities": [
                    {"entity_key": "e0", "surface": "廙", "entity_kind": "abbreviated_name", "reference_form": "abbreviated", "evidence_refs": ["r"]},
                    {"entity_key": "e1", "surface": "甲", "entity_kind": "named_person", "reference_form": "full_name", "evidence_refs": ["r"]},
                ],
                "valid_relations": [{"relation_id": "r0", "subject_entity_key": "e0", "object_entity_key": "e1", "relation_surface": "與", "relation_class": relation_class, "evidence_ref": "r", "exact_span": "廙與甲", "confidence": "high"}],
            }
            result = algorithm.normalize_person_fill(validation, case=base_case, windows=windows)
            target = next(row for row in result["entities"] if row["surface"] == "廙")
            self.assertIsNone(target["resolved_person_id"])
            self.assertEqual(result["source_grounded_identity_expansions"], [])

        conflict_case = {**base_case, "constraint_checks": [{"candidate_key": "c0", "constraint_type": "temporal", "status": "conflict"}]}
        windows = [algorithm.prepare_evidence_window({"ref": "r", "text": "王廙，廙遂行", "evidence_text": "王廙，廙遂行"})]
        validation = {"valid_entities": [{"entity_key": "e0", "surface": "廙", "entity_kind": "abbreviated_name", "reference_form": "abbreviated", "evidence_refs": ["r"]}], "valid_relations": []}
        result = algorithm.normalize_person_fill(validation, case=conflict_case, windows=windows)
        self.assertEqual(result["source_grounded_identity_expansions"], [])
        self.assertIsNone(result["entities"][0]["resolved_person_id"])


class EvidenceAtomRunnerTests(unittest.TestCase):
    def test_selection_is_exact_c1_set_and_44_calls(self) -> None:
        selection = runner.build_selection()
        self.assertEqual(selection["person_regression_count"], 8)
        self.assertEqual(selection["temporal_regression_count"], 4)
        self.assertEqual(selection["heldout_count"], 5)
        self.assertEqual(selection["semantic_call_count"], 44)
        self.assertEqual(
            [(row["story_id"], row["target_surface"]) for row in selection["heldout"]],
            [
                ("05-fangzheng-025", "鄧攸"),
                ("25-paidiao-009", "張茂先"),
                ("19-xianyuan-014", "賈充"),
                ("31-fenjuan-006", "習鑿齒"),
                ("18-qiyi-010", "少孤"),
            ],
        )

    def test_offline_replay_makes_no_api_calls(self) -> None:
        selection = runner.build_selection()
        result = runner.run(selection, live=False, run_id="test-deterministic")
        self.assertEqual(result["metrics"]["semantic_calls"], 44)
        self.assertEqual(result["metrics"]["preflight"]["api_calls"], 0)
        self.assertFalse(result["metrics"]["canonical_write_back"])


if __name__ == "__main__":
    unittest.main()
