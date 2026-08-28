import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import hdb2_full_frontier_common as common  # noqa: E402
import rebuild_hdb2_f_profiles as profiles  # noqa: E402
import run_hdb2_psl1_3d as closeout  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class HDB2PSL13DTests(unittest.TestCase):
    def test_source_level_catalogue_collision_is_audited_and_rejected(self):
        audit = load(profiles.IDENTITY_CLAIM_AUDIT_PATH)
        rows = [
            row
            for row in audit["audited_identity_claims"]
            if row.get("story_id") == "09-pinzao-088"
            and row.get("surface") == "仲文"
            and row.get("target_person_id") == "person-031"
        ]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertFalse(row["source_claim_supported"])
        self.assertFalse(row["profile_form_retained"])
        self.assertIn("source_local_full_form_conflict", row["rejection_reasons"])
        self.assertIn("殷仲文", row["source_local_context"])

    def test_valid_and_invalid_same_surface_claims_remain_occurrence_scoped(self):
        audit = load(profiles.IDENTITY_CLAIM_AUDIT_PATH)
        valid = [
            row for row in audit["retained_source_identity_claims"]
            if row.get("surface") == "仲文" and row.get("story_id") == "09-pinzao-045"
        ]
        invalid = [
            row for row in audit["invalid_source_identity_claims"]
            if row.get("surface") == "仲文" and row.get("story_id") == "09-pinzao-088"
        ]
        self.assertTrue(valid)
        self.assertTrue(invalid)
        self.assertEqual({row["target_person_id"] for row in valid}, {"person-031"})
        self.assertEqual({row["target_person_id"] for row in invalid}, {"person-031"})
        profile = next(row for row in load(profiles.EXISTING_PROFILE)["records"] if row.get("person_id") == "person-031")
        provenance = profile["identity"]["form_provenance"]
        valid_claim = valid[0]
        invalid_claim = invalid[0]
        self.assertTrue(any(
            row.get("surface") == "仲文"
            and row.get("evidence_ref") == valid_claim["evidence_ref"]
            and row.get("occurrence_id") == valid_claim["occurrence_id"]
            for row in provenance
        ))
        self.assertFalse(any(
            row.get("surface") == "仲文"
            and row.get("evidence_ref") == invalid_claim["evidence_ref"]
            and row.get("occurrence_id") == invalid_claim["occurrence_id"]
            for row in provenance
        ))

    def test_profile_forms_have_exact_identity_provenance(self):
        audit = load(profiles.AUDIT_PATH)
        self.assertEqual(audit["forms_without_identity_provenance"], 0)
        self.assertEqual(audit["orphan_profile_forms"], 0)
        self.assertEqual(audit["known_contamination_remaining"], [])
        claim_audit = load(profiles.IDENTITY_CLAIM_AUDIT_PATH)
        self.assertTrue(claim_audit["invalid_source_identity_claims"])
        self.assertTrue(claim_audit["retained_source_identity_claims"])

    def test_offline_replay_has_no_api_calls_and_preserves_c_safety(self):
        run = closeout.OUT_ROOT / closeout.DEFAULT_RUN_ID
        self.assertTrue((run / "manifest.json").is_file())
        manifest = load(run / "manifest.json")
        self.assertTrue(manifest["replayed_without_api"])
        self.assertEqual(manifest["api_calls_this_run"], 0)
        self.assertTrue(manifest["source_decisions_unchanged"])
        summary = load(run / "validation-summary.json")
        self.assertTrue(summary["safety_gates_pass"], summary)
        self.assertFalse(summary["canonical_write_back"])

    def test_known_c_safety_rows_are_not_stable_wrong_resolutions(self):
        rows = load(closeout.OUT_ROOT / closeout.DEFAULT_RUN_ID / "python-decisions.json")["records"]
        for row in rows:
            forbidden = closeout.FORBIDDEN_STABLE_RESOLUTIONS.get((row.get("story_id"), row.get("surface")), set())
            if str(row.get("result_state")) in {"stable_entity_resolved", "local_candidate_resolved"}:
                self.assertNotIn(row.get("top_candidate"), forbidden)

    def test_no_canonical_write_flags_and_no_person_id_allocation(self):
        for path in (profiles.EXISTING_PROFILE, profiles.CANDIDATE_PROFILE, profiles.AUDIT_PATH, profiles.IDENTITY_CLAIM_AUDIT_PATH):
            document = load(path)
            self.assertTrue(document.get("candidate_only"))
            self.assertFalse(document.get("canonical_write_back"))
        self.assertTrue(all(not str(row.get("candidate_person_id") or "").startswith("person-") for row in load(closeout.OUT_ROOT / closeout.DEFAULT_RUN_ID / "python-decisions.json")["records"]))


if __name__ == "__main__":
    unittest.main()
