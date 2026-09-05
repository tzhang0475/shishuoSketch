from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_f1 import common as f1
from sfh2_f1rp import audit


class SFH22F1RPAuditTests(unittest.TestCase):
    def _run(self) -> dict[str, dict]:
        with tempfile.TemporaryDirectory() as temporary:
            return audit.run(Path(temporary), materialize_repository_overlays=False)

    def test_human_overlay_has_exactly_nine_decisions_without_gold_mutation(self) -> None:
        inputs = audit._load_inputs()
        authority, by_id = audit._human_authority(inputs)
        self.assertEqual(authority["record_count"], 9)
        self.assertEqual(len(by_id), 9)
        self.assertFalse(authority["active_gold_mutated"])
        self.assertEqual(authority["active_gold_sha256"], "177ab3018e6741c3deaf3b5f957bc177df8c4f416ee9a9035bdf6027f7d7e3a7")
        for row in authority["records"]:
            self.assertTrue(row["candidate_only"])
            self.assertFalse(row["canonical_write_back"])
            self.assertEqual(row["review_status"], "reviewed")
            self.assertEqual(set(row["occurrence_key"]), set(audit.EXACT_KEY_FIELDS))

    def test_candidate_registry_confirms_exactly_eleven_structured_groups(self) -> None:
        registry = audit._candidate_registry(audit._load_inputs())
        self.assertEqual(registry["group_count"], 11)
        self.assertEqual(registry["occurrence_level_proposal_count"], 12)
        self.assertTrue(registry["lookup_semantics"]["exact_structured_identity_only"])
        self.assertFalse(registry["lookup_semantics"]["fuzzy_matching"])
        self.assertFalse(registry["canonical_write_back"])
        self.assertEqual(registry["canonical_person_creation"], 0)
        huan_yi = next(group for group in registry["groups"] if group["proposed_canonical_identity"] == "桓伊")
        self.assertEqual(len(huan_yi["occurrence_members"]), 2)
        self.assertTrue(all(group["human_entity_review"] == "confirmed_candidate_identity" for group in registry["groups"]))

    def test_controls_include_eight_reviewed_and_one_upstream_block(self) -> None:
        inputs = audit._load_inputs()
        authority, _ = audit._human_authority(inputs)
        controls = audit._controls(authority)
        self.assertEqual(controls["record_count"], 9)
        reviewed = [row for row in controls["records"] if row["control_status"] == "reviewed_production_control"]
        blocked = [row for row in controls["records"] if row["control_status"] == "invalid/upstream-target-control"]
        self.assertEqual(len(reviewed), 8)
        self.assertEqual(len(blocked), 1)
        self.assertIsNone(blocked[0]["human_decision"])
        self.assertEqual(blocked[0]["occurrence_key"]["surface"], "康")

    def test_approved_policy_keeps_historical_rules_and_marks_transport_gate(self) -> None:
        routing = audit._review_routing_policy()
        projection = audit._compatibility_projection_policy()
        consistency = audit._semantic_consistency_policy()
        self.assertEqual(routing["policy_status"], "approved")
        self.assertTrue(routing["activated_for_future_waves"])
        self.assertIn("new_historical_person_entity", routing["mandatory_review_triggers"])
        self.assertIn("reviewed_candidate_entity_reuse", routing["audit_only_triggers"])
        self.assertIn("upstream_mention_repair_required", routing["mandatory_review_triggers"])
        self.assertTrue(projection["historical_projection_mutated"] is False)
        self.assertEqual(projection["reviewed_control"]["legacy_occurrence_role"], "other")
        self.assertTrue(consistency["office_invariant"]["python_may_correct"] is False)
        historical = (ROOT / "scripts/sfh2_a2o/provenance.py").read_text(encoding="utf-8")
        self.assertIn("def project_legacy_occurrence_role", historical)

    def test_post_review_queue_preserves_transport_and_removes_reviewed_entity_trigger(self) -> None:
        documents = self._run()
        metrics = documents["metrics.json"]
        queue = documents["post-review-queue.json"]
        self.assertEqual(metrics["provider_calls"], 0)
        self.assertEqual(metrics["current_f1_mandatory_occurrences"], 25)
        self.assertEqual(metrics["f1r_policy_v2_before_human_decisions_mandatory_occurrences"], 22)
        self.assertEqual(metrics["post_review_mandatory_occurrences"], 13)
        self.assertEqual(metrics["post_review_entity_review_units"], 0)
        self.assertEqual(len(queue["records"]), 30)
        for row in queue["records"]:
            if row["candidate_entity_group_id"]:
                self.assertNotIn("new_historical_person_entity", row["post_review_mandatory_reasons"])
        kang = next(row for row in queue["records"] if row["occurrence_key"]["surface"] == "康")
        self.assertIn("upstream_mention_repair_required", kang["post_review_mandatory_reasons"])
        self.assertIn("terminal_or_degraded_provider_contract", next(row for row in queue["records"] if row["occurrence_key"]["surface"] == "殷公")["post_review_mandatory_reasons"])

    def test_v2_projection_is_structured_and_historical_projector_is_unchanged(self) -> None:
        self.assertEqual(audit.project_legacy_occurrence_role_v2("liu_annotation", "reference", "non_person", ""), "other")
        self.assertEqual(audit.project_legacy_occurrence_role_v2("liu_annotation", "person_attribute", "person", "office"), "person_attribute")
        self.assertEqual(audit.project_legacy_occurrence_role_v2("liu_annotation", "reference", "person", "office"), "other")
        self.assertEqual(audit.project_legacy_occurrence_role_v2("main_text", "participant", "person", "historical_person"), "scene_participant")
        self.assertEqual(audit.project_legacy_occurrence_role_v2("liu_annotation", "reference", "person", "historical_person"), "annotation_person")
        manifest = json.loads((ROOT / "data/frozen/sfh2/semantic-v1/architecture.json").read_text(encoding="utf-8"))
        historical_path = ROOT / "scripts/sfh2_a2o/provenance.py"
        self.assertEqual(f1.file_hash(historical_path), manifest["code_hashes"]["scripts/sfh2_a2o/provenance.py"])

    def test_upstream_target_has_no_promoted_semantic_label(self) -> None:
        documents = self._run()
        authority, by_id = audit._human_authority(audit._load_inputs())
        self.assertIsNone(by_id["sfh1-mention-55b97afde3e7fb4c074361b8"]["narrative_function"])
        repair = documents["upstream-mention-repair-candidates.json"]
        self.assertEqual(repair["record_count"], 1)
        self.assertIsNone(repair["records"][0]["semantic_label"])
        self.assertTrue(repair["records"][0]["semantic_promotion_blocked"])

    def test_protected_snapshot_and_required_hashes_are_unchanged(self) -> None:
        before = audit._protected_snapshot()
        documents = self._run()
        after = audit._protected_snapshot()
        self.assertEqual(before, after)
        protected = documents["metrics.json"]["protected_hash_audit"]
        self.assertTrue(protected["unchanged"])
        self.assertEqual(protected["changed_paths"], [])
        self.assertEqual(protected["protected_hashes"]["sc1_frozen"], "cc82c6738fcbf4fc14c12005a459048e71ce329492867d0910562fc6fdfda0d8")
        self.assertEqual(protected["protected_hashes"]["sc1_current"], "b916530264285dd7fa1d2e27a7a1dff8cd2ed794dfb3b84985881f8f209d8f6a")

    def test_offline_generation_is_byte_deterministic_and_has_no_provider_client(self) -> None:
        def snapshot(path: Path) -> dict[str, str]:
            return {str(child.relative_to(path)): f1.file_hash(child) for child in sorted(path.rglob("*")) if child.is_file()}

        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            audit.run(Path(left), materialize_repository_overlays=False)
            audit.run(Path(right), materialize_repository_overlays=False)
            self.assertEqual(snapshot(Path(left)), snapshot(Path(right)))
        source = (ROOT / "scripts/sfh2_f1rp/audit.py").read_text(encoding="utf-8")
        for forbidden in ("requests", "openai", "F1Client", "surface ==", "surface !="):
            self.assertNotIn(forbidden, source)
        for path in Path(ROOT / "data/generated/sfh2-f1rp").glob("**/raw-api*"):
            self.fail(f"raw provider artifact committed: {path}")

    def test_all_outputs_remain_candidate_only_and_cannot_write_canonical_data(self) -> None:
        documents = self._run()
        for document in documents.values():
            self.assertTrue(document["candidate_only"])
            self.assertFalse(document["canonical_write_back"])
        self.assertEqual(documents["metrics.json"]["canonical_person_creation"], 0)
        self.assertEqual(documents["metrics.json"]["canonical_writes"], 0)


if __name__ == "__main__":
    unittest.main()
