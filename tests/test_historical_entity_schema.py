"""Focused offline tests for Historical Entity Schema V1 and replay."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from historical_entity_schema import (  # noqa: E402
    EntityInterpretation,
    IdentityDecision,
    MentionObservation,
    to_dict,
)
from build_hng2_schema_replay import hash_tree  # noqa: E402


OUT = ROOT / "data/generated/hng2-schema"


class HistoricalEntitySchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validation = json.loads((OUT / "validation-cases.json").read_text(encoding="utf-8"))
        cls.cases = json.loads((OUT / "cases.json").read_text(encoding="utf-8"))["cases"] + cls.validation["regression_case_records"]
        cls.manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))

    def test_mention_observation_contains_only_observed_fields(self):
        mention = MentionObservation("m1", "文帝", "文帝甚悦", "ref", "晉書")
        self.assertNotIn("entity_kind", to_dict(mention))
        with self.assertRaises(TypeError):
            MentionObservation("m2", "文帝", "文帝", "ref", "晉書", entity_kind="person_title")  # type: ignore[call-arg]

    def test_controlled_interpretation_enums_and_provisional_is_not_status(self):
        interpretation = EntityInterpretation("m1", "person_title", "title_only", "narrative", "office_holder")
        self.assertEqual(interpretation.entity_kind, "person_title")
        with self.assertRaises(ValueError):
            IdentityDecision("provisional")

    def test_regression_cases_pass(self):
        self.assertTrue(self.validation["all_passed"])
        self.assertTrue(all(row["passed"] for row in self.validation["regression_cases"]))

    def _case(self, prefix: str):
        return next(row for row in self.cases if row["case_id"] == prefix)

    def test_required_identity_boundaries(self):
        mount = self._case("regression-mount-tao")
        self.assertEqual(mount["interpretation"]["entity_kind"], "named_person")
        self.assertEqual(mount["decision"]["identity_status"], "resolved_existing")
        self.assertEqual(mount["decision"]["person_id"], "person-043")
        self.assertEqual(mount["graph_action"]["action"], "link_existing")

        title = self._case("regression-title-wendi")
        self.assertEqual(title["interpretation"]["entity_kind"], "person_title")
        self.assertEqual(title["decision"]["identity_status"], "ambiguous")
        self.assertNotEqual(title["graph_action"]["frontier_status"], "eligible")

        structural = self._case("regression-structural-kinship")
        self.assertEqual(structural["interpretation"]["entity_kind"], "structural_kinship_expression")
        self.assertEqual(structural["decision"]["identity_status"], "not_single_person")
        self.assertEqual(structural["graph_action"]["action"], "no_person_node")
        self.assertEqual(structural["graph_action"]["frontier_status"], "blocked")

        bian = self._case("regression-bian-dun")
        self.assertEqual(bian["decision"]["identity_status"], "resolved_new_candidate")
        self.assertNotEqual(bian["decision"].get("person_id"), "person-011")
        self.assertIn("卞敦", [row["canonical_name"] for row in bian["candidates"]])

    def test_metatext_and_relation_semantics_are_separate(self):
        yuan = self._case("regression-metatext-yuanhong")
        self.assertEqual(yuan["interpretation"]["mention_scope"], "metatextual")
        self.assertEqual(yuan["interpretation"]["discourse_role"], "cited_author")
        self.assertNotEqual(yuan["interpretation"]["discourse_role"], "event_participant")
        relation = next(row for row in self.validation["regression_cases"] if row["case_id"] == "regression-relation-zhongya")
        self.assertEqual(relation["details"]["semantic_level"], "documented_interaction")
        self.assertEqual(relation["details"]["relation_semantics_description"], "co-participants in military command")

    def test_python_owns_hard_constraints(self):
        constraints = json.loads((OUT / "constraint-checks.json").read_text(encoding="utf-8"))
        for group in constraints["case_constraints"]:
            self.assertTrue(all(check["computed_by"] == "python" for check in group["checks"]))
        for case in self.cases:
            self.assertTrue(case["semantic_assessment"]["hard_constraints_immutable"])

    def test_no_model_calls_or_canonical_write_back(self):
        self.assertEqual(self.manifest["model"]["model_calls"], 0)
        self.assertEqual(self.manifest["model"]["api_calls"], 0)
        self.assertFalse(self.manifest["canonical_write_back"])
        for name in ("cases.json", "mentions.json", "identity-decisions.json", "graph-actions.json", "relation-assertions.json"):
            self.assertFalse(json.loads((OUT / name).read_text(encoding="utf-8")).get("canonical_write_back"))

    def test_deterministic_rebuild_and_frozen_inputs(self):
        before = hash_tree(OUT)
        result = subprocess.run([sys.executable, "scripts/build_hng2_schema_replay.py", "--quiet"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, hash_tree(OUT))
        for label, expected in self.manifest["protected_artifact_hashes"].items():
            from build_hng2_schema_replay import ROOT as PROJECT_ROOT
            root = PROJECT_ROOT / "data/generated" / label
            if label == "srm0":
                root = PROJECT_ROOT / "data/generated/srm0"
            self.assertEqual(expected, hash_tree(root), label)


if __name__ == "__main__":
    unittest.main()
