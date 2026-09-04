from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.sfh2_f1r import audit


class SFH22F1RAuditTests(unittest.TestCase):
    def _tree_snapshot(self, directory: Path) -> dict[str, str]:
        return {
            str(path.relative_to(directory)): audit.f1.file_hash(path)
            for path in sorted(directory.rglob("*"))
            if path.is_file()
        }

    def test_offline_audit_covers_exact_f1_wave_and_never_uses_gold(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            documents = audit.run(Path(temporary))
        metrics = documents["metrics.json"]
        exact = documents["exact-occurrence-audit.json"]
        gold = documents["gold-alignment-audit.json"]
        self.assertEqual(metrics["provider_calls"], 0)
        self.assertTrue(metrics["all_30_reviewed_exactly_once"])
        self.assertEqual(exact["record_count"], 30)
        self.assertTrue(exact["all_structurally_valid"])
        self.assertTrue(all(row["gold_evaluation_available"] is False for row in exact["records"]))
        self.assertFalse(gold["active_gold_loaded"])
        self.assertTrue(all(row["gold_used_by_f1r"] is False for row in documents["semantic-acceptance-review.json"]["records"]))

    def test_all_audit_keys_and_target_reason_findings_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            documents = audit.run(Path(temporary))
        required = {
            "occurrence_id", "mention_id", "story_id", "source_evidence_id",
            "source_start", "source_end", "surface",
        }
        exact = documents["exact-occurrence-audit.json"]["records"]
        self.assertTrue(all(required.issubset(row["occurrence_key"]) for row in exact))
        self.assertTrue(all(row["target_integrity"]["valid"] for row in exact))
        reasons = documents["reason-target-alignment-audit.json"]
        self.assertEqual(reasons["drift_count"], 3)
        drift_stories = {
            row["occurrence_key"]["story_id"]
            for row in reasons["records"]
            if row["classification"] in {"wrong_occurrence", "partially_drifted"}
        }
        self.assertEqual(drift_stories, {"05-fangzheng-055", "01-dexing-014", "14-rongzhi-005"})
        self.assertEqual(documents["selection-intent-alignment.json"]["misalignment_count"], 0)

    def test_f1_transport_and_review_workload_are_fully_accounted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            documents = audit.run(Path(temporary))
        metrics = documents["metrics.json"]
        transport = documents["transport-failure-audit.json"]
        people = documents["new-person-review-groups.json"]
        matrix = documents["review-trigger-matrix.json"]
        self.assertEqual(transport["f1_accounted_invalid_semantic_payload_count"], 5)
        self.assertEqual(transport["terminal_identity_block_count"], 3)
        self.assertEqual(people["occurrence_level_new_person_review_count"], 12)
        self.assertEqual(people["deduplicated_entity_review_count"], 11)
        self.assertEqual(metrics["current_mandatory_review_count"], 25)
        self.assertEqual(metrics["proposed_policy_mandatory_review_count"], 22)
        self.assertEqual(metrics["identity_applicability_counts"], {
            "ambiguous": 1,
            "identity_not_applicable": 6,
            "person_identity_required": 23,
        })
        self.assertEqual(metrics["identity_applicability_routing_mismatch_count"], 2)
        self.assertEqual(metrics["identity_applicability_candidate_count"], 4)
        self.assertFalse(documents["review-policy-v2-candidate.json"]["activated"])
        self.assertEqual(matrix["policy_defined_stage_disagreement_count"], 20)

    def test_protected_artifacts_are_unchanged_by_offline_run(self) -> None:
        before = audit._protected_snapshot()
        with tempfile.TemporaryDirectory() as temporary:
            documents = audit.run(Path(temporary))
        after = audit._protected_snapshot()
        self.assertEqual(before, after)
        protected = documents["metrics.json"]["protected_hash_audit"]
        self.assertTrue(protected["unchanged"])
        self.assertEqual(protected["changed_paths"], [])
        self.assertEqual(
            protected["protected_hashes"]["sc1_frozen"],
            "cc82c6738fcbf4fc14c12005a459048e71ce329492867d0910562fc6fdfda0d8",
        )
        self.assertEqual(
            protected["protected_hashes"]["sc1_current"],
            "b916530264285dd7fa1d2e27a7a1dff8cd2ed794dfb3b84985881f8f209d8f6a",
        )

    def test_audit_is_byte_deterministic_and_contains_no_provider_path(self) -> None:
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            audit.run(Path(left))
            audit.run(Path(right))
            left_files = self._tree_snapshot(Path(left))
            right_files = self._tree_snapshot(Path(right))
        self.assertEqual(left_files, right_files)
        source = (audit.ROOT / "scripts/sfh2_f1r/audit.py").read_text(encoding="utf-8")
        self.assertNotIn("F1Client", source)
        self.assertNotIn("from .transport", source)
        self.assertNotIn("surface ==", source)
        self.assertNotIn("surface !=", source)
        self.assertEqual(json.loads((audit.ROOT / "data/generated/sfh2-f-prep/production-scope.json").read_text(encoding="utf-8"))["total_validated_occurrences"], 3303)


if __name__ == "__main__":
    unittest.main()
