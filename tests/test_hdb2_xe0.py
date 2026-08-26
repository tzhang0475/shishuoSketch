from __future__ import annotations

import json
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_hdb2_xe0 as xe0  # noqa: E402


class HDB2XE0Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = xe0.freeze_baseline()
        cls.selection = xe0.build_selection()

    def test_baseline_is_the_frozen_73_item_projection(self) -> None:
        self.assertEqual(self.baseline["baseline_review_items"], 73)
        self.assertEqual(sum(self.baseline["fingerprint"]["counts_by_type"].values()), 73)
        self.assertTrue(self.baseline["frozen_before_live"])
        self.assertTrue(self.baseline["candidate_only"])
        self.assertFalse(self.baseline["canonical_write_back"])

    def test_selection_is_deterministic_and_outside_production(self) -> None:
        story_ids = [str(row["story_id"]) for row in self.selection["stories"]]
        self.assertEqual(len(story_ids), 24)
        self.assertEqual(len(story_ids), len(set(story_ids)))
        self.assertTrue(set(story_ids).isdisjoint(xe0._production_story_ids()))
        self.assertEqual(
            self.selection["selection_hash"],
            xe0.stable_hash({key: value for key, value in self.selection.items() if key != "selection_hash"}),
        )
        rebuilt = xe0.build_selection()
        self.assertEqual(rebuilt, self.selection)

    def test_target_plan_is_bounded(self) -> None:
        self.assertLessEqual(self.selection["target_count"], 2 * self.selection["selected_story_count"])
        selected = {str(row["story_id"]) for row in self.selection["stories"]}
        self.assertTrue(all(str(row["story_id"]) in selected for row in self.selection["target_plan"]))
        self.assertTrue(all(row.get("candidate_only") is not False for row in self.selection["target_plan"]))

    def test_live_audit_formula_and_projection_are_isolated(self) -> None:
        run_dir = xe0.XE0_ROOT / "live/20260826T-HDB2-XE0-02"
        self.assertTrue((run_dir / "audit.json").is_file())
        audit = json.loads((run_dir / "audit.json").read_text(encoding="utf-8"))
        self.assertEqual(
            audit["net_review_reduction"],
            audit["old_review_items_resolved"] - audit["new_review_items_created"],
        )
        self.assertEqual(audit["baseline_review_items"], 73)
        self.assertTrue(audit["candidate_only"])
        self.assertFalse(audit["canonical_write_back"])
        baseline_index = json.loads((xe0.BASELINE_REVIEW_ROOT / "index.json").read_text(encoding="utf-8"))
        xe0_index = json.loads((xe0.SITE_REVIEW_ROOT / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(baseline_index["item_count"], 73)
        self.assertEqual(xe0_index["baseline_review_items"], 73)
        self.assertNotEqual(xe0.SITE_REVIEW_ROOT, xe0.BASELINE_REVIEW_ROOT)

    def test_no_protected_hdb2_f_hash_drift(self) -> None:
        manifest = json.loads((xe0.XE0_ROOT / "live/20260826T-HDB2-XE0-02/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["protected_hashes_before"], manifest["protected_hashes_after"])
        self.assertEqual(manifest["protected_hashes_after"], xe0._protected_hashes())


if __name__ == "__main__":
    unittest.main()
