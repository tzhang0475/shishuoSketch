from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_a2osp.common import (  # noqa: E402
    A2O_ROOT,
    A2OR_ROOT,
    A2OS_ROOT,
    A2OT_ROOT,
    AUTHORITY_PATH,
    CASE_GU,
    CASE_QI,
    GOLD_PATH,
    FROZEN_SC1_SHA256,
    CURRENT_SC1_SHA256,
    IDENTITY_MANIFEST_SHA256,
    file_hash,
    load_inputs,
    occurrence_key,
    rows,
    text,
)
from sfh2_a2osp.pipeline import run  # noqa: E402


class SFH22A2OSPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inputs = load_inputs()

    def test_exactly_two_authorized_record_mutations(self) -> None:
        before = self.inputs["frozen_gold"]
        after = self.inputs["active_gold"]
        changed = [case_id for case_id in before if before[case_id] != after[case_id]]
        self.assertEqual([CASE_QI, CASE_GU], changed)
        self.assertEqual(2, len(changed))
        authority = json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(2, authority["substantive_gold_mutation_count"])
        self.assertFalse(authority["model_output_used_as_authority"])

    def test_exact_keys_and_reviewed_labels_are_preserved(self) -> None:
        authority = json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))
        exact = self.inputs["exact"]
        by_id = {text(row.get("case_id")): row for row in authority["records"]}
        for case_id in (CASE_GU, CASE_QI):
            self.assertEqual(by_id[case_id]["exact_occurrence_key"], occurrence_key(exact[case_id]))
        self.assertEqual("participant", self.inputs["active_gold"][CASE_GU]["expected_narrative_function"])
        self.assertEqual("scene_participant", self.inputs["active_gold"][CASE_GU]["expected_legacy_occurrence_role"])
        self.assertEqual("reference", self.inputs["active_gold"][CASE_QI]["expected_narrative_function"])
        self.assertEqual("annotation_person", self.inputs["active_gold"][CASE_QI]["expected_legacy_occurrence_role"])

    def test_other_24_gold_records_are_semantically_unchanged(self) -> None:
        before = self.inputs["frozen_gold"]
        after = self.inputs["active_gold"]
        unchanged = [case_id for case_id in before if case_id not in {CASE_GU, CASE_QI} and before[case_id] == after[case_id]]
        self.assertEqual(24, len(unchanged))

    def test_frozen_a2or_is_reused_and_post_metrics_are_derived(self) -> None:
        protected = [A2O_ROOT, A2OT_ROOT, A2OR_ROOT, A2OS_ROOT]
        before = {
            str(path): file_hash(path)
            for root in protected
            for path in root.rglob("*")
            if path.is_file()
        }
        with tempfile.TemporaryDirectory() as directory:
            documents = run(Path(directory))
        after = {
            str(path): file_hash(path)
            for root in protected
            for path in root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(before, after)
        evaluation = documents["a2or-post-promotion-evaluation.json"]
        self.assertEqual(24, evaluation["post_promotion_metrics"]["narrative_function"]["correct"])
        self.assertEqual(26, evaluation["post_promotion_metrics"]["resolution_coverage"]["correct"])
        self.assertEqual(0, documents["metrics.json"]["provider_calls"])
        self.assertFalse(documents["metrics.json"]["single_historian_fully_qualified"])

    def test_residuals_are_aligned_valid_and_one_family(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            documents = run(Path(directory))
        residual = documents["residual-error-qualification.json"]
        self.assertEqual(2, residual["qualified_genuine_error_count"])
        self.assertEqual({"reference_to_participant_overreach": 2}, residual["error_family_counts"])
        self.assertTrue(all(row["qualified_as_genuine_semantic_error"] for row in residual["records"]))
        self.assertTrue(all(all(row["qualification_checks"].values()) for row in residual["records"]))

    def test_selection_invariant_is_structural_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            invariant = run(Path(directory))["selection-integrity-invariant.json"]
        self.assertEqual(["mention_id", "source_evidence_id", "source_start", "source_end", "surface"], invariant["required_target_fields"])
        self.assertFalse(invariant["python_may_infer_semantic_role_from_offsets"])
        self.assertFalse(invariant["historical_selector_rewritten"])

    def test_offline_outputs_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_documents = run(Path(first))
            second_documents = run(Path(second))
            self.assertEqual(set(first_documents), set(second_documents))
            for name in first_documents:
                self.assertEqual(
                    (Path(first) / name).read_bytes(),
                    (Path(second) / name).read_bytes(),
                    name,
                )

    def test_storage_and_protected_hash_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            documents = run(Path(directory))
        for document in documents.values():
            if isinstance(document, dict):
                self.assertEqual(0, document.get("provider_calls", 0))
                if "candidate_only" in document:
                    self.assertTrue(document["candidate_only"])
                if "canonical_write_back" in document:
                    self.assertFalse(document["canonical_write_back"])
        self.assertEqual(FROZEN_SC1_SHA256, file_hash(ROOT / "data/derived/sc1-site.json"))
        self.assertEqual(CURRENT_SC1_SHA256, file_hash(ROOT / "data/derived/sc1-current-site.json"))
        self.assertEqual(IDENTITY_MANIFEST_SHA256, file_hash(ROOT / "data/frozen/sfh2/identity-v1/manifest.json"))


if __name__ == "__main__":
    unittest.main()
