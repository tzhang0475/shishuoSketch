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

    def test_baseline_is_the_frozen_73_item_semantic_frontier(self) -> None:
        self.assertEqual(self.baseline["schema"], xe0.SEMANTIC_BASELINE_SCHEMA)
        self.assertEqual(self.baseline["baseline_review_items"], 73)
        semantic = self.baseline["semantic_fingerprint"]
        self.assertEqual(semantic["record_count"], 73)
        self.assertEqual(sum(semantic["counts_by_status"].values()), 73)
        self.assertEqual(sum(semantic["counts_by_priority"].values()), 73)
        self.assertEqual(semantic, xe0.semantic_frontier_fingerprint())
        self.assertEqual(self.baseline["baseline_hash"], xe0.baseline_contract_hash(self.baseline))
        self.assertTrue(self.baseline["frozen_before_live"])
        self.assertTrue(self.baseline["candidate_only"])
        self.assertFalse(self.baseline["canonical_write_back"])

    def test_review_projection_covers_exactly_the_frozen_frontier(self) -> None:
        self.assertEqual(xe0.validate_review_projection(), [])
        frontier = {str(row["occurrence_id"]) for row in xe0._semantic_frontier_rows()}
        _, items = xe0._baseline_items()
        projected = {str(row["occurrence_id"]) for row in items}
        self.assertEqual(projected, frontier)
        self.assertEqual(len({str(row["review_id"]) for row in items}), 73)

    def test_reviewer_facing_enrichment_does_not_change_semantic_fingerprint(self) -> None:
        queue = xe0.read_json(xe0.BASELINE_QUEUE_PATH, {})
        records = [dict(row) for row in queue["records"]]
        before = xe0.semantic_frontier_fingerprint(records)
        records[0]["ui_note"] = "presentation-only enrichment"
        self.assertEqual(before, xe0.semantic_frontier_fingerprint(records))

    def test_semantic_frontier_fields_change_the_fingerprint(self) -> None:
        rows = xe0._semantic_frontier_rows()
        for field in ("occurrence_id", "story_id", "surface", "status"):
            changed = [dict(row) for row in rows]
            changed[0][field] = f"changed-{field}"
            self.assertNotEqual(
                xe0.semantic_frontier_fingerprint(rows),
                xe0.semantic_frontier_fingerprint(changed),
                field,
            )

    def test_selection_is_deterministic_and_outside_production(self) -> None:
        story_ids = [str(row["story_id"]) for row in self.selection["stories"]]
        self.assertEqual(len(story_ids), 24)
        self.assertEqual(len(story_ids), len(set(story_ids)))
        self.assertTrue(set(story_ids).isdisjoint(xe0._production_story_ids()))
        self.assertEqual(
            self.selection["selection_hash"],
            xe0.stable_hash({key: value for key, value in self.selection.items() if key != "selection_hash"}),
        )
        self.assertEqual(self.selection["baseline_hash"], self.baseline["selection_baseline_hash"])
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
        self.assertTrue(xe0.protected_hashes_match_manifest(manifest["protected_hashes_after"]))
        self.assertTrue(xe0.authorized_derived_projection_matches_manifest(manifest))

    def test_canonical_drift_is_distinct_from_authorized_derived_profile_transition(self) -> None:
        manifest = json.loads((xe0.XE0_ROOT / "live/20260826T-HDB2-XE0-02/manifest.json").read_text(encoding="utf-8"))
        derived = dict(manifest["authorized_derived_projection_hashes"])
        derived["data/derived/hdb2-f-person-knowledge.json"] = "authorized-transition-recorded-hash"

        # A derived projection is not part of the immutable HDB2-F snapshot;
        # its intentional rebuild is validated through an explicit versioned
        # baseline instead.
        immutable = dict(manifest["protected_hashes_after"])
        self.assertTrue(xe0.protected_hashes_match_manifest(immutable))
        self.assertFalse(xe0.protected_hashes_match_manifest({**immutable, "data/people.json": "canonical-drift"}))

        transitioned = dict(manifest)
        transitioned["authorized_derived_projection_hashes"] = xe0._authorized_derived_projection_hashes()
        self.assertTrue(xe0.authorized_derived_projection_matches_manifest(transitioned))
        transitioned["authorized_derived_projection_version"] = "unrecorded-profile-version"
        self.assertFalse(xe0.authorized_derived_projection_matches_manifest(transitioned))
        self.assertNotEqual(derived, xe0._authorized_derived_projection_hashes())


if __name__ == "__main__":
    unittest.main()
