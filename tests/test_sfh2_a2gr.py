from __future__ import annotations

import hashlib
import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_sfh2_a2gr as stage  # noqa: E402


class SFH22A2GRTests(unittest.TestCase):
    def test_gold_has_one_substantive_mutation_and_three_reaffirmations(self) -> None:
        delta = stage.read_json(stage.OUT / "reviewed-gold-delta.json")
        authority = stage.read_json(stage.AUTHORITY_PATH)
        self.assertEqual(1, delta["substantive_mutation_count"])
        self.assertEqual(3, delta["reaffirmed_case_count"])
        self.assertEqual(1, len(delta["changed_cases"]))
        self.assertEqual(3, sum(row["decision"] == "reaffirm_gold" for row in authority["records"]))
        self.assertEqual(1, sum(row["decision"] == "revise_gold" for row in authority["records"]))

    def test_reviewed_office_case_is_not_identity_evaluable(self) -> None:
        evaluation = stage.read_json(stage.OUT / "identity-re-evaluation.json")
        row = next(row for row in evaluation["records"] if row["surface"] == "太丘長")
        self.assertFalse(row["historical_identity_evaluable"])
        self.assertEqual("office", row["gold_reviewed"]["expected_semantic_kind"])
        self.assertIsNone(row["final"]["dimensions"]["identity_correct"])

    def test_reaffirmed_gold_cases_are_byte_semantically_unchanged(self) -> None:
        authority = stage.read_json(stage.AUTHORITY_PATH)
        for row in authority["records"]:
            if row["decision"] == "reaffirm_gold":
                self.assertEqual(row["previous_gold"], row["reviewed_gold"])

    def test_frozen_identity_gate_is_deterministic_and_passed(self) -> None:
        qualification = stage.read_json(stage.OUT / "identity-qualification.json")
        recommendation = stage.read_json(stage.OUT / "recommendation.json")
        self.assertTrue(qualification["gate_passed"])
        self.assertEqual("qualified_and_frozen", qualification["identity_pipeline_status"])
        self.assertEqual("sfh2_identity_pipeline_frozen", recommendation["recommendation"])
        self.assertEqual("SFH2.2-A2O", recommendation["next_stage"])
        self.assertEqual(17, qualification["final_identity"]["evaluable"])
        self.assertEqual(17, qualification["final_identity"]["correct"])

    def test_zero_provider_calls_and_candidate_storage_boundary(self) -> None:
        for path in stage.OUT.glob("*.json"):
            document = stage.read_json(path)
            self.assertEqual(0, document.get("provider_calls", 0), path.name)
            self.assertTrue(document.get("candidate_only"), path.name)
            self.assertFalse(document.get("canonical_write_back"), path.name)
        freeze = stage.read_json(stage.FREEZE_PATH)
        self.assertEqual(0, freeze["provider_calls"])
        self.assertTrue(freeze["candidate_only"])
        self.assertFalse(freeze["canonical_write_back"])
        authority = stage.read_json(stage.AUTHORITY_PATH)
        self.assertFalse(authority["candidate_only"])
        self.assertFalse(authority["canonical_write_back"])

    def test_a2_a2r_a2g_and_protected_inputs_are_not_mutated_by_replay(self) -> None:
        first = stage.build_outputs()
        before = first["protected-hash-snapshot.json"]["trees"]
        second = stage.build_outputs()
        self.assertEqual(
            {key: stage.canonical_json(value) for key, value in first.items()},
            {key: stage.canonical_json(value) for key, value in second.items()},
        )
        self.assertEqual(before, second["protected-hash-snapshot.json"]["trees"])

    def test_freeze_manifest_hashes_match_current_files(self) -> None:
        freeze = stage.read_json(stage.FREEZE_PATH)
        self.assertEqual(hashlib.sha256(stage.GOLD_PATH.read_bytes()).hexdigest(), freeze["reviewed_gold_sha256"])
        for relative, expected in freeze["protected_file_hashes"].items():
            self.assertEqual(expected, stage.file_hash(ROOT / relative), relative)
        for relative, snapshot in freeze["protected_experiment_trees"].items():
            self.assertEqual(snapshot, stage._snapshot_tree(ROOT / relative), relative)

    def test_gold_builder_matches_promoted_active_authority(self) -> None:
        from sfh2_a0.selection import build_evaluation_gold

        self.assertEqual(build_evaluation_gold(), stage.read_json(stage.GOLD_PATH))
        self.assertEqual("fee2063baf59676054fd9e31265dff92bd58d605b7f06303572497ca13369565", stage.file_hash(stage.GOLD_PATH))

    def test_a2gr_runtime_has_no_lexical_semantic_rule(self) -> None:
        source = (ROOT / "scripts/run_sfh2_a2gr.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"surface\s*==", source))
        self.assertIsNone(re.search(r"surface\s+in\s+", source))
        self.assertNotIn("replacement_identity", source)


if __name__ == "__main__":
    unittest.main()
