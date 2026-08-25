from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_hng0_2 as hng02
import hdb2_p1_common as common
import solve_hdb2_constraints as solver


class HDB2ConstraintFusionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = hng02.person_catalog()
        self.case = {
            "case_id": "fixture-case",
            "target_surfaces": ["康伯"],
            "story_ids": ["fixture-story"],
            "current_candidate_person_ids": [],
            "observation_ids": [],
            "blocked_relations": [],
            "blocked_kinship": [],
            "blocked_marriage": [],
            "story_temporal_constraints": [],
        }
        self.passages = [{"ref": "fixture-ref", "source_work": "晉書", "evidence_text": "韓伯字康伯"}]

    def test_selection_is_frozen_and_structural(self) -> None:
        selection = common.read_json(common.ANNOTATION / "hdb2-p1-selection.json", {})
        self.assertEqual(selection["selected_case_count"], 24)
        self.assertEqual(selection["selection_hash"], common.stable_hash({k: v for k, v in selection.items() if k != "selection_hash"}))
        self.assertEqual({row["current_status"] for row in selection["cases"]}, {"unresolved_surface_cluster"})

    def test_strict_tool_has_closed_atom_schema(self) -> None:
        tool = common.strict_atom_tool()
        parameters = tool["function"]["parameters"]
        self.assertFalse(parameters["additionalProperties"])
        self.assertEqual(parameters["required"], ["atoms"])
        atom = parameters["properties"]["atoms"]["items"]
        self.assertFalse(atom["additionalProperties"])
        self.assertEqual(set(atom["required"]), set(atom["properties"]))
        self.assertNotIn("person_id", json.dumps(tool, ensure_ascii=False))

    def test_grounding_rejects_one_bad_atom_without_discarding_good_atom(self) -> None:
        payload = {
            "atoms": [
                {"atom_id": "a0", "atom_kind": "identity_name", "subject_surface": "韓伯", "predicate_surface": "字", "object_surface": "康伯", "temporal_surface": "", "evidence_ref": "fixture-ref", "exact_span": "韓伯字康伯", "certainty": "explicit"},
                {"atom_id": "a1", "atom_kind": "office", "subject_surface": "韓伯", "predicate_surface": "任命", "object_surface": "", "temporal_surface": "", "evidence_ref": "fixture-ref", "exact_span": "韓伯字康伯", "certainty": "explicit"},
            ]
        }
        result = common.validate_atoms(payload, self.passages)
        self.assertEqual(len(result["valid_atoms"]), 1)
        self.assertEqual(result["rejected_atoms"][0]["reason"], "predicate_surface_not_in_span")

    def test_explicit_identity_evidence_resolves_existing_person(self) -> None:
        atom = {"atom_id": "a0", "atom_kind": "identity_name", "subject_surface": "韓伯", "predicate_surface": "字", "object_surface": "康伯", "temporal_surface": "", "evidence_ref": "fixture-ref", "exact_span": "韓伯字康伯", "certainty": "explicit"}
        result = solver.solve_case(self.case, [atom], self.passages, self.catalog)
        self.assertEqual(result["decision"]["status"], "resolved_existing")
        self.assertEqual(result["decision"]["resolved_person_id"], "person-024")
        self.assertEqual(result["decision"]["identity_resolution_basis"], "evidence_identity_assertion")
        self.assertTrue(result["candidate_only"])

    def test_identity_basis_is_not_flattened_into_catalogue_evidence(self) -> None:
        atom = {"atom_id": "a0", "atom_kind": "identity_name", "subject_surface": "廙", "predicate_surface": "字", "object_surface": "王廙", "temporal_surface": "", "evidence_ref": "fixture-ref", "exact_span": "廙字王廙", "certainty": "explicit"}
        case = dict(self.case); case["target_surfaces"] = ["廙"]
        result = solver.solve_case(case, [atom], [{"ref": "fixture-ref", "source_work": "晉書", "evidence_text": "廙字王廙"}], self.catalog)
        supports = result["decision"]["identity_support"]
        self.assertTrue(all(x["basis"] in {"evidence_identity_assertion", "contextual_name_projection"} for x in supports))
        self.assertNotEqual(result["decision"]["identity_resolution_basis"], "explicit_name_evidence")

    def test_nonidentity_self_relation_is_rejected_after_endpoint_resolution(self) -> None:
        case = dict(self.case)
        case["target_surfaces"] = ["康伯"]
        case["observation_ids"] = ["obs"]
        case["blocked_relations"] = [{"candidate_id": "rel-self", "subject_ref": "unresolved:obs", "object_person_id": "person-024", "relation_class": "interaction"}]
        atom = {"atom_id": "a0", "atom_kind": "identity_name", "subject_surface": "韓伯", "predicate_surface": "字", "object_surface": "康伯", "temporal_surface": "", "evidence_ref": "fixture-ref", "exact_span": "韓伯字康伯", "certainty": "explicit"}
        result = solver.solve_case(case, [atom], self.passages, self.catalog)
        self.assertEqual(result["newly_unblocked_candidate_facts"], [])
        self.assertEqual(result["rejected_relations"][0]["reason"], "collapsed_nonidentity_self_relation")

    def test_same_surface_alone_does_not_resolve(self) -> None:
        case = dict(self.case); case["target_surfaces"] = ["康伯"]
        passage = [{"ref": "fixture-ref", "source_work": "世說正文", "evidence_text": "康伯與友人語"}]
        atom = {"atom_id": "a0", "atom_kind": "person_mention", "subject_surface": "康伯", "predicate_surface": "", "object_surface": "", "temporal_surface": "", "evidence_ref": "fixture-ref", "exact_span": "康伯", "certainty": "explicit"}
        result = solver.solve_case(case, [atom], passage, self.catalog)
        self.assertNotEqual(result["decision"]["status"], "resolved_existing")

    def test_temporal_only_cannot_resolve(self) -> None:
        atom = {"atom_id": "a0", "atom_kind": "temporal_activity", "subject_surface": "康伯", "predicate_surface": "為", "object_surface": "", "temporal_surface": "咸和", "evidence_ref": "fixture-ref", "exact_span": "康伯為咸和", "certainty": "explicit"}
        passage = [{"ref": "fixture-ref", "source_work": "晉書", "evidence_text": "康伯為咸和"}]
        result = solver.solve_case(self.case, [atom], passage, self.catalog)
        self.assertNotEqual(result["decision"]["status"], "resolved_existing")

    def test_no_canonical_write_or_production_allocation(self) -> None:
        result = solver.solve_case(self.case, [], [], self.catalog)
        self.assertFalse(result["canonical_write_back"])
        self.assertIsNone(result["decision"]["resolved_person_id"])
        self.assertNotIn("person-076", json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
