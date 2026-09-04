from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_a2os.common import (  # noqa: E402
    A2O_ROOT,
    A2OR_ROOT,
    A2OT_ROOT,
    CASE_GU,
    CASE_QI,
    GOLD_PATH,
    PROTECTED_IDENTITY_SHA256,
    PROTECTED_SC1_CURRENT_SHA256,
    PROTECTED_SC1_SHA256,
    file_hash,
    load_bundle,
)
from sfh2_a2os.pipeline import duplicate_surface_document, exact_occurrence_records, run  # noqa: E402


class SFH22A2OSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = load_bundle()
        cls.records = exact_occurrence_records(cls.bundle)
        cls.by_id = {row["case_id"]: row for row in cls.records}

    def test_all_frozen_cases_have_exact_occurrence_keys(self):
        self.assertEqual(26, len(self.records))
        self.assertTrue(all(row["integrity"]["structural_valid"] for row in self.records))
        self.assertEqual(26, len({tuple(row["exact_occurrence_key"].items()) for row in self.records}))

    def test_gu_exact_target_is_pinned_by_mention_and_offsets(self):
        row = self.by_id[CASE_GU]
        key = row["exact_occurrence_key"]
        self.assertEqual("sfh1-mention-7bf42600cd19ef3230d8b8fb", key["mention_id"])
        self.assertEqual(0, key["source_start"])
        self.assertEqual(1, key["source_end"])
        self.assertEqual("顧", key["surface"])
        self.assertEqual("顧", row["exact_source_context"]["matched_target"])
        self.assertEqual("wrong_occurrence", row["gold_occurrence_alignment"])
        self.assertEqual("misaligned", row["selection_intent_target_alignment"])

    def test_repeated_and_nested_surface_visibility_is_structural(self):
        document = duplicate_surface_document(self.records)
        self.assertEqual(0, document["exact_validated_tuple_duplicate_group_count"])
        self.assertEqual(10, document["textually_repeated_or_overlapping_case_count"])
        gu = next(row for row in document["textually_repeated_or_overlapping_cases"] if row["case_id"] == CASE_GU)
        self.assertEqual([{"source_start": 0, "source_end": 1}, {"source_start": 22, "source_end": 23}], gu["text_surface_offsets"])
        self.assertEqual("sfh1-mention-5db99dfc07c09df5bc76055d", gu["overlapping_validated_mentions"][0]["mention_id"])

    def test_gold_basis_is_not_used_as_target_or_identity_proof(self):
        for row in self.records:
            self.assertTrue(row["gold_semantic_basis_is_evidence_only"])
            self.assertFalse(row["gold_basis_used_for_target_resolution"])
        self.assertEqual("target_gold_alignment_error", self.by_id[CASE_GU]["alignment_root_cause"])
        self.assertEqual("gold_taxonomy_review_required", self.by_id[CASE_QI]["alignment_root_cause"])

    def test_review_candidates_are_human_only_and_counterfactual_is_derived(self):
        with tempfile.TemporaryDirectory() as directory:
            documents = run(Path(directory))
        candidates = documents["gold-review-candidates.json"]["records"]
        self.assertEqual({CASE_GU, CASE_QI}, {row["case_id"] for row in candidates})
        self.assertTrue(all(row["human_review_required"] and not row["gold_mutation_performed"] for row in candidates))
        scenarios = documents["counterfactual-evaluation.json"]["scenarios"]
        self.assertEqual(22, scenarios[0]["score"]["all"]["correct"])
        self.assertEqual(24, scenarios[-1]["score"]["all"]["correct"])

    def test_audit_is_offline_and_does_not_mutate_frozen_inputs(self):
        paths = [
            GOLD_PATH,
            A2O_ROOT / "selection.json",
            A2OT_ROOT / "gold-taxonomy-audit.json",
            A2OR_ROOT / "evaluation.json",
        ]
        before = {str(path): file_hash(path) for path in paths}
        with tempfile.TemporaryDirectory() as directory:
            documents = run(Path(directory))
        after = {str(path): file_hash(path) for path in paths}
        self.assertEqual(before, after)
        self.assertEqual(0, documents["metrics.json"]["provider_calls"])
        self.assertEqual(PROTECTED_SC1_SHA256, file_hash(ROOT / "data/derived/sc1-site.json"))
        self.assertEqual(PROTECTED_SC1_CURRENT_SHA256, file_hash(ROOT / "data/derived/sc1-current-site.json"))
        self.assertEqual(PROTECTED_IDENTITY_SHA256, file_hash(ROOT / "data/frozen/sfh2/identity-v1/manifest.json"))

    def test_no_surface_specific_semantic_runtime_or_provider_path(self):
        source = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "scripts/sfh2_a2os").glob("*.py"))
        self.assertNotRegex(source, re.compile(r"surface\s*(?:==|!=)|surface\s+in\b"))
        self.assertNotRegex(source, re.compile(r"DEEPSEEK_API_KEY|api\.deepseek\.com|requests|urllib|openai", re.IGNORECASE))

    def test_output_json_is_deterministic(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            run(Path(first))
            run(Path(second))
            first_paths = sorted(Path(first).glob("*.json"))
            second_paths = sorted(Path(second).glob("*.json"))
            self.assertEqual([path.name for path in first_paths], [path.name for path in second_paths])
            for left, right in zip(first_paths, second_paths):
                self.assertEqual(left.read_bytes(), right.read_bytes(), left.name)


if __name__ == "__main__":
    unittest.main()
