import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import hdb2_psl1_3b_common as common  # noqa: E402
import hdb2_psl1_3_common as psl1_3  # noqa: E402
import run_hdb2_psl1_3b as runner  # noqa: E402


def fixture_case(surface, text, *, occurrence_type="unclear", local_neighbors=(), candidates=()):
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


def person(name, person_id=None):
    row = {"display_name": name, "semantic_type": "person"}
    if person_id:
        row["person_id"] = person_id
    return row


class HDB2PSL13BTests(unittest.TestCase):
    def test_selection_is_exactly_ten_distinct_new_stories(self):
        selection = common.freeze_selection()
        story_ids = [str(row["story_id"]) for row in selection["independent_cases"]]
        self.assertEqual(len(story_ids), 10)
        self.assertEqual(len(set(story_ids)), 10)
        self.assertEqual(selection["overlap_with_prior_story_ids"], [])
        self.assertTrue(set(story_ids).isdisjoint(common.previous_story_ids()))
        self.assertEqual(selection["candidate_only"], True)
        self.assertEqual(selection["canonical_write_back"], False)

    def test_adjacent_office_holder_after_surface_is_grounded(self):
        current = fixture_case("僕射", "命駕見僕射羊祜尚書山濤", local_neighbors=[person("羊祜")])
        structure = common.finalize_reference_structure(current)
        self.assertEqual(structure["surface_structure"], "office_holder_reference")
        self.assertEqual(structure["holder"], "羊祜")
        self.assertEqual(structure["anchor_person"], "羊祜")
        self.assertTrue(structure["holder_evidence_satisfied"])
        self.assertTrue(structure["holder_assignment_evidence_ids"])

    def test_explicit_before_office_and_patron_are_separate(self):
        current = fixture_case("敦主簿", "何充爲敦主簿", local_neighbors=[person("何充")])
        structure = common.finalize_reference_structure(current)
        self.assertEqual(structure["surface_structure"], "patron_plus_office")
        self.assertEqual(structure["holder"], "何充")
        self.assertEqual(structure["patron_or_possessor"], "敦")
        self.assertEqual(structure["explicit_distinct_mentions"], ["何充", "敦"])

    def test_unproven_office_holder_is_null_and_neutral(self):
        current = fixture_case(
            "司空", "王敦在此，後稱司空而未具其人",
            local_neighbors=[person("王敦", "person-011")],
        )
        structure = common.finalize_reference_structure(current)
        self.assertEqual(structure["surface_structure"], "office_holder_reference")
        self.assertIsNone(structure["holder"])
        self.assertIsNone(structure["anchor_person"])
        self.assertFalse(structure["holder_evidence_satisfied"])
        self.assertEqual(structure["holder_assignment_evidence_ids"], [])

    def test_generic_surface_does_not_become_lexical_alias_automatically(self):
        current = fixture_case("王", "王在坐", candidates=[person("王敦", "person-011")])
        info = common.reference_hypotheses(current)
        self.assertNotIn("lexicalized_personal_form", {row["surface_structure"] for row in info["hypotheses"]})
        self.assertFalse(info["deterministic"])

    def test_required_reference_regressions_pass(self):
        regression = common.reference_regression_records()
        self.assertTrue(regression["all_pass"], regression)
        by_key = {(row.get("story_id"), row.get("surface")): row for row in regression["records"]}
        self.assertEqual(by_key[("07-shijian-005", "僕射")]["actual"]["holder"], "羊祜")
        self.assertEqual(by_key[("08-shangyu-043", "司空")]["actual"]["holder"], "劉琨")
        self.assertEqual(by_key[("05-fangzheng-028", "敦主簿")]["actual"]["holder"], "何充")

    def test_strict_semantic_contract_is_reused(self):
        function = common.semantic_tool()["function"]
        self.assertTrue(function["strict"])
        parameters = function["parameters"]
        self.assertFalse(parameters["additionalProperties"])
        self.assertEqual(set(parameters["required"]), set(parameters["properties"]))
        self.assertNotIn("person_id", json.dumps(function, ensure_ascii=False))
        self.assertEqual(
            common.semantic_tool_choice(),
            {"type": "function", "function": {"name": common.FUNCTION_NAME}},
        )

    def test_output_namespace_rewrite_preserves_frozen_prompt_version(self):
        document = {
            "schema": "hdb2-psl1-3a-example-v1",
            "prompt_version": common.PROMPT_VERSION,
            "nested": {"schema": "hdb2-psl1-3a-nested-v1"},
        }
        rewritten = runner._replace_schema_names(document)
        self.assertEqual(rewritten["schema"], "hdb2-psl1-3b-example-v1")
        self.assertEqual(rewritten["nested"]["schema"], "hdb2-psl1-3b-nested-v1")
        self.assertEqual(rewritten["prompt_version"], common.PROMPT_VERSION)

    def test_frozen_one_three_selection_remains_a_different_contract(self):
        old = psl1_3.freeze_selection()
        self.assertEqual(old["schema"], "hdb2-psl1-3-selection-v1")
        self.assertNotEqual(common.freeze_selection()["selection_hash"], old["selection_hash"])


if __name__ == "__main__":
    unittest.main()
