import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import hdb2_psl1_3a_common as common  # noqa: E402
import hdb2_psl1_3_common as psl1_3  # noqa: E402
import hdb2_psl1_1_common as psl1_1  # noqa: E402


def case(surface, text, *, occurrence_type="unclear", local_neighbors=(), candidates=()):
    return {
        "mention_id": f"m-{surface}",
        "occurrence_id": f"o-{surface}",
        "story_id": "fixture-story",
        "target_surface": surface,
        "occurrence_type": occurrence_type,
        "story_context": text,
        "annotation_context": [],
        "local_neighbors": list(local_neighbors),
        "candidates": list(candidates),
        "evidence_items": [{
            "evidence_id": "ev0",
            "family": "relevant_source_evidence",
            "source_ref": "fixture-source",
            "text": text,
        }],
    }


class HDB2PSL13ATests(unittest.TestCase):
    @staticmethod
    def _frozen_case(story_id, surface):
        graphs = [psl1_3.build_graph(psl1_3.freeze_selection()), *psl1_1.load_psl1_graphs()]
        for graph in graphs:
            for current in graph.get("cases", []):
                if current.get("story_id") == story_id and current.get("target_surface") == surface:
                    return current
        raise AssertionError(f"missing frozen case: {story_id}/{surface}")

    def test_strict_semantic_tool_is_closed(self):
        function = common.semantic_tool()["function"]
        parameters = function["parameters"]
        self.assertTrue(function["strict"])
        self.assertFalse(parameters["additionalProperties"])
        self.assertEqual(set(parameters["required"]), set(parameters["properties"]))
        self.assertEqual(
            common.semantic_tool_choice(),
            {"type": "function", "function": {"name": common.FUNCTION_NAME}},
        )
        self.assertNotIn("person_id", json.dumps(function, ensure_ascii=False))

    def test武子_suffix_is_hypothesis_not_forced_kinship(self):
        current = case("武子", "武帝語和嶠曰王武子然後爵之")
        info = common.reference_hypotheses(current)
        self.assertTrue(info["ambiguous"])
        self.assertEqual(
            {row["surface_structure"] for row in info["hypotheses"]},
            {"compositional_kinship", "lexicalized_personal_form"},
        )
        self.assertIsNone(common.finalize_reference_structure(current)["semantic_arbitration_confidence"])
        payload = common.arbitration_regression_payload(current, info["hypotheses"])
        packet = common.semantic_packet(current, info["hypotheses"])
        validation = common.validate_semantic_arbitration(payload, packet)
        finalized = common.finalize_reference_structure(current, payload, validation)
        self.assertTrue(validation["valid"], validation)
        self.assertEqual(finalized["surface_structure"], "lexicalized_personal_form")
        self.assertNotEqual(finalized["surface_structure"], "compositional_kinship")

    def test_actual_frozen_regressions_use_the_new_structure_boundary(self):
        wuzi = self._frozen_case("05-fangzheng-011", "武子")
        wuzi_info = common.reference_hypotheses(wuzi)
        self.assertTrue(wuzi_info["ambiguous"])
        wuzi_payload = common.arbitration_regression_payload(wuzi, wuzi_info["hypotheses"])
        wuzi_packet = common.semantic_packet(wuzi, wuzi_info["hypotheses"])
        wuzi_validation = common.validate_semantic_arbitration(wuzi_payload, wuzi_packet)
        self.assertTrue(wuzi_validation["valid"], wuzi_validation)
        self.assertEqual(
            common.finalize_reference_structure(wuzi, wuzi_payload, wuzi_validation)["surface_structure"],
            "lexicalized_personal_form",
        )

        expected = {
            ("05-fangzheng-028", "敦主簿"): ("patron_plus_office", "何充", "敦"),
            ("34-pilou-001", "主"): ("non_person", "王敦", ""),
            ("02-yanyu-046", "謝豫章"): ("surname_plus_title", "", ""),
        }
        for key, (surface_structure, anchor, patron) in expected.items():
            structure = common.finalize_reference_structure(self._frozen_case(*key))
            self.assertEqual(structure["surface_structure"], surface_structure, key)
            self.assertEqual(structure["anchor_person"], anchor, key)
            self.assertEqual(structure["patron_or_possessor"], patron, key)

    def test_explicit之_kinship_keeps_the_real_anchor(self):
        current = case("庾亮之子", "庾亮之子見於史", local_neighbors=[{"display_name": "庾亮"}])
        structure = common.finalize_reference_structure(current)
        self.assertEqual(structure["surface_structure"], "compositional_kinship")
        self.assertEqual(structure["anchor_person"], "庾亮")
        self.assertEqual(structure["components"][1], {"text": "之子", "role": "kinship_marker"})

    def test_explicit_name_statement_is_deterministic_structure_only(self):
        current = case("康伯", "韓伯字康伯")
        info = common.reference_hypotheses(current)
        self.assertTrue(info["deterministic"])
        self.assertEqual(info["deterministic_hypothesis"]["surface_structure"], "lexicalized_personal_form")
        self.assertEqual(
            info["deterministic_hypothesis"]["components"],
            [
                {"text": "韓伯", "role": "personal_form"},
                {"text": "康伯", "role": "personal_form"},
            ],
        )

    def test_deterministic_structures_keep_components_separate(self):
        kinship = case("庾亮兒", "諸葛恢大女適太尉庾亮兒", local_neighbors=[{"display_name": "庾亮"}])
        kin = common.reference_hypotheses(kinship)
        self.assertTrue(kin["deterministic"])
        self.assertEqual(kin["deterministic_hypothesis"]["surface_structure"], "compositional_kinship")
        self.assertEqual(common.finalize_reference_structure(kinship)["anchor_person"], "庾亮")

        household = case("家兄", "王敦護其兄，故於衆坐稱家兄在郡定佳", local_neighbors=[{"display_name": "王敦"}])
        household_structure = common.finalize_reference_structure(household)
        self.assertEqual(household_structure["surface_structure"], "compositional_kinship")
        self.assertEqual(household_structure["anchor_person"], "王敦")
        self.assertIsNone(household_structure["referent_candidate"])

        office = case("敦主簿", "何充爲敦主簿", local_neighbors=[{"display_name": "何充"}])
        office_structure = common.finalize_reference_structure(office)
        self.assertEqual(office_structure["surface_structure"], "patron_plus_office")
        self.assertEqual(office_structure["holder"], "何充")
        self.assertEqual(office_structure["patron_or_possessor"], "敦")
        self.assertIsNone(office_structure["referent_candidate"])

    def test_title_ruler_and_surname_title_are_not_substring_aliases(self):
        title = case("謝豫章", "謝仁祖年八歲，謝豫章將送客", occurrence_type="title_reference")
        structure = common.finalize_reference_structure(title)
        self.assertEqual(structure["surface_structure"], "surname_plus_title")
        self.assertEqual(structure["reference_type"], "title_reference")

        ruler = case("陛下", "陛下龍飛")
        ruler_structure = common.finalize_reference_structure(ruler)
        self.assertEqual(ruler_structure["surface_structure"], "honorific_person_reference")
        self.assertEqual(ruler_structure["referent_type"], "ruler")

        office = case("中丞", "髙靈時為中丞", local_neighbors=[{"display_name": "髙靈"}])
        office_structure = common.finalize_reference_structure(office)
        self.assertEqual(office_structure["surface_structure"], "office_holder_reference")
        self.assertEqual(office_structure["holder"], "髙靈")

    def test_invalid_evidence_or_components_fail_closed(self):
        current = case("武子", "王武子")
        hypotheses = common.build_reference_hypotheses(current)
        packet = common.semantic_packet(current, hypotheses)
        payload = {
            "surface_structure": "lexicalized_personal_form",
            "referent_type": "person",
            "components": [{"text": "invented", "role": "personal_form"}],
            "supporting_evidence_ids": ["not-supplied"],
            "confidence": "high",
        }
        result = common.validate_semantic_arbitration(payload, packet)
        self.assertFalse(result["valid"])
        self.assertIn("evidence_reference_invalid:not-supplied", result["errors"])
        self.assertIn("component_text_not_grounded:0", result["errors"])

        malformed = dict(payload)
        malformed["surface_structure"] = []
        malformed["referent_type"] = []
        malformed["confidence"] = []
        malformed_result = common.validate_semantic_arbitration(malformed, packet)
        self.assertFalse(malformed_result["valid"])
        self.assertIn("surface_structure_invalid", malformed_result["errors"])
        self.assertIn("referent_type_invalid", malformed_result["errors"])
        self.assertIn("confidence_invalid", malformed_result["errors"])

    def test_structural_cleanup_does_not_leave_anchor_as_final_candidate(self):
        graph = psl1_3.build_graph(psl1_3.freeze_selection())
        structures = {}
        for current in graph["cases"]:
            structures[str(current["mention_id"])] = common.finalize_reference_structure(current)
        patched = common.apply_reference_structures(graph, structures)
        decisions = psl1_1.infer_graph(patched, [])
        cleaned = common.clean_structural_decisions(decisions, patched)
        household = next(row for row in cleaned["records"] if row.get("surface") == "家兄")
        self.assertEqual(household["result_state"], "structural_reference")
        self.assertIsNone(household.get("top_candidate"))
        self.assertIsNone(household.get("final_candidate"))
        self.assertTrue(household.get("structural_candidate_suppressed"))


if __name__ == "__main__":
    unittest.main()
