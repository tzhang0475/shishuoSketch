from __future__ import annotations

import hashlib
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_a2ot.common import A2O_GOLD_PATH, BASELINE_COMMIT, A2O_PROTECTED_FILES, load_frozen_bundle  # noqa: E402
from sfh2_a2ot.pipeline import audit_record, function_consistency_matrix, gold_review_candidates, run  # noqa: E402
from sfh2_a2ot.taxonomy import NARRATIVE_FUNCTIONS, taxonomy_document  # noqa: E402


class SFH22A2OTTests(unittest.TestCase):
    def test_audit_covers_all_frozen_cases_and_exact_offsets(self):
        bundle = load_frozen_bundle()
        records = [
            audit_record({
                "selection": selection,
                "packet": bundle["packets"][selection["case_id"]],
                "result": bundle["results"][selection["case_id"]],
                "evaluation": bundle["evaluation"][selection["case_id"]],
                "gold": bundle["gold"][selection["case_id"]],
            })
            for selection in bundle["selection"]
        ]
        self.assertEqual(26, len(records))
        self.assertTrue(all(row["target_span"]["offsets_valid"] for row in records))
        self.assertTrue(all(row["target_span"]["matched_source_text"] == row["target_span"]["exact_span"] for row in records))
        self.assertEqual({"sfh2-a0r-l-challenge-c07bd51ac298529ddbc6"}, {row["case_id"] for row in records if row["ontology_audit"]["review_required"]})
        self.assertEqual(1, len([row for row in records if row["ontology_audit"]["review_required"]]))

    def test_taxonomy_is_explicit_and_occurrence_centric(self):
        document = taxonomy_document()
        self.assertEqual(list(NARRATIVE_FUNCTIONS), document["functions"])
        self.assertTrue(document["occurrence_centric"])
        self.assertTrue(document["semantic_guidance_not_runtime_rules"])
        self.assertTrue(document["no_surface_specific_logic"])
        self.assertTrue(document["no_automatic_object_to_addressee_rule"])

    def test_only_summon_case_is_a_gold_review_candidate(self):
        bundle = load_frozen_bundle()
        records = [
            audit_record({
                "selection": selection,
                "packet": bundle["packets"][selection["case_id"]],
                "result": bundle["results"][selection["case_id"]],
                "evaluation": bundle["evaluation"][selection["case_id"]],
                "gold": bundle["gold"][selection["case_id"]],
            })
            for selection in bundle["selection"]
        ]
        candidates = gold_review_candidates(records)
        self.assertEqual(1, candidates["candidate_count"])
        candidate = candidates["records"][0]
        self.assertEqual("sfh2-a0r-l-challenge-c07bd51ac298529ddbc6", candidate["case_id"])
        self.assertEqual("addressee", candidate["previous_label"]["narrative_function"])
        self.assertEqual("participant", candidate["proposed_label"]["narrative_function"])
        self.assertTrue(candidate["human_review_required"])
        self.assertFalse(candidate["gold_mutation_performed"])

    def test_mismatch_classes_and_counterfactual_score_are_derived(self):
        bundle = load_frozen_bundle()
        records = [
            audit_record({
                "selection": selection,
                "packet": bundle["packets"][selection["case_id"]],
                "result": bundle["results"][selection["case_id"]],
                "evaluation": bundle["evaluation"][selection["case_id"]],
                "gold": bundle["gold"][selection["case_id"]],
            })
            for selection in bundle["selection"]
        ]
        classes = [row["ontology_audit"]["audit_class"] for row in records if row["ontology_audit"]["a2o_mismatch"]]
        self.assertEqual({"model_source_scope_error", "gold_requires_human_review", "model_discourse_role_error", "model_target_attribute_confusion"}, set(classes))
        self.assertEqual(21, sum(row["a2o_evaluation"]["narrative_function_correct"] for row in records))
        self.assertEqual(22, sum(
            (row["a2o_interpretation"]["narrative_function"] == ("participant" if row["case_id"] == "sfh2-a0r-l-challenge-c07bd51ac298529ddbc6" else row["current_gold"]["expected_narrative_function"]))
            for row in records
        ))
        self.assertEqual([], function_consistency_matrix(records)["latent_inconsistency_findings"])

    def test_a2o_inputs_are_not_mutated_and_no_provider_is_used(self):
        before = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in A2O_PROTECTED_FILES}
        with tempfile.TemporaryDirectory() as directory:
            result = run(Path(directory))
            self.assertEqual(0, result["current_correct"] - 21)
        after = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in A2O_PROTECTED_FILES}
        self.assertEqual(before, after)
        self.assertEqual(before["data/annotation/sfh2-a2o-evaluation-gold.json"], hashlib.sha256(A2O_GOLD_PATH.read_bytes()).hexdigest())
        source = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "scripts/sfh2_a2ot").glob("*.py"))
        self.assertNotIn("DEEPSEEK_API_KEY", source)
        self.assertNotIn("api.deepseek.com", source)
        self.assertNotRegex(source, re.compile(r"surface\s*(?:==|!=|in\b)"))

    def test_derived_outputs_are_deterministic(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            run(Path(first))
            run(Path(second))
            first_files = sorted(Path(first).iterdir())
            second_files = sorted(Path(second).iterdir())
            self.assertEqual([path.name for path in first_files], [path.name for path in second_files])
            for left, right in zip(first_files, second_files):
                self.assertEqual(left.read_bytes(), right.read_bytes(), left.name)

    def test_frozen_baseline_is_explicit(self):
        self.assertEqual("1ac588e8ae54bd4745f3d091360d02e65e3f55ac", BASELINE_COMMIT)
        self.assertEqual(26, len(load_frozen_bundle()["selection"]))


if __name__ == "__main__":
    unittest.main()
