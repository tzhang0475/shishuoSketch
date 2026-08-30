from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import manual_semantic_authority as authority  # noqa: E402
import validate_sfh2r  # noqa: E402
import sfh2r_contract  # noqa: E402


OUT = ROOT / "data/generated/sfh2r"


def load(name: str):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


class SFH2RTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        missing = [name for name in validate_sfh2r.REQUIRED if not (OUT / name).is_file()]
        if missing:
            raise unittest.SkipTest("SFH2R projection is not built: " + ", ".join(missing))

    def test_validator_passes_mechanical_authority_contract(self):
        result = validate_sfh2r.validate()
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(32, result["manual_regression_count"])

    def test_alias_repair_downgrades_shared_forms_and_preserves_safe_w4(self):
        aliases = json.loads((ROOT / "data/aliases.json").read_text(encoding="utf-8"))
        by_surface = {(row.get("surface"), person): row for row in aliases["aliases"] for person in row.get("person_ids", [])}
        for row in authority.alias_repairs():
            surface = row.get("corrected_surface") or row.get("surface")
            active = by_surface.get((surface, row.get("current_person_id")))
            self.assertIsNotNone(active, row["alias_id"])
            if row.get("corrected_resolution_mode"):
                self.assertEqual(row["corrected_resolution_mode"], active["resolution_mode"])
            current_ids = {item.get("evidence_id") for item in active.get("source_evidence", [])}
            self.assertTrue(current_ids.isdisjoint(set(row.get("remove_evidence_ids", []))))
        for row in authority.load_authority().get("audited_safe_w4_aliases", []):
            self.assertIn((row["surface"], row["person_id"]), by_surface)

    def test_rejected_profiles_and_source_rows_are_absent(self):
        profiles = load("profile-before-after.json")
        after = {row["person_id"]: row["after"] for row in profiles["records"]}
        self.assertNotIn("桓亮", set(after["person-070"]["identity"]["aliases"]))
        self.assertNotIn("桓景真", set(after["person-070"]["identity"]["aliases"]))
        current = json.loads((ROOT / "data/derived/hdb2-f-person-knowledge.json").read_text(encoding="utf-8"))
        for row in current["records"]:
            if row.get("canonical_name") == "郭象":
                forms = set(row.get("identity", {}).get("aliases", [])) | set(row.get("identity", {}).get("courtesy_names", []))
                self.assertNotIn("子少", forms)

    def test_reviewed_occurrence_repairs_have_expected_structures(self):
        document = load("occurrence-before-after.json")
        rows = {row["observation_id"]: row["after"] for row in document["records"]}
        repairs = authority.occurrence_repairs()
        self.assertEqual(set(repairs), set(rows))
        self.assertEqual("桓亮", rows["sfh2-observation-15912a1494e17cfe36fc35ce"]["previous_identity_decision"]["candidate_display_name"])
        self.assertEqual("non_person", rows["sfh2-observation-8c7d20a52559830123ec7e3d"]["classification"])
        self.assertEqual("non_person", rows["sfh2-observation-f35d3060607ce7bf220c40ff"]["classification"])
        self.assertEqual("historical_context_reference", rows["sfh2-observation-56258cfd1fea21b43f10f1ad"]["classification"])

    def test_candidate_entities_are_candidate_only_and_grounded(self):
        document = load("candidate-registry-repairs.json")
        self.assertEqual({"石勒", "孫綽", "桓亮"}, {row["display_name"] for row in document["records"]})
        for row in document["records"]:
            self.assertFalse(row["candidate_person_id"].startswith("person-"))
            self.assertTrue(row["evidence_ids"])
            self.assertTrue(row["candidate_only"])
            self.assertFalse(row["canonical_write_back"])

    def test_offline_replay_does_not_mutate_old_sfh2_and_covers_188_stories(self):
        replay = load("offline-replay-effects.json")
        self.assertEqual(188, replay["stories"])
        self.assertEqual(3303, replay["observation_count_before"])
        self.assertEqual(3303, replay["observation_count_after"])
        self.assertFalse(replay["old_sfh2_artifacts_mutated"])
        self.assertEqual(0, load("metrics.json")["llm_calls"])

    def test_all_artifacts_remain_candidate_only(self):
        for path in OUT.glob("*.json"):
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(document.get("candidate_only"), path.name)
            self.assertFalse(document.get("canonical_write_back"), path.name)

    def test_derived_input_transition_is_explicit_and_fail_closed(self):
        manifest = load("repair-manifest.json")
        transition = manifest["active_input_transition"]
        # SFH2R.1 is an explicit second derived-input transition.  The first
        # manifest remains immutable; its after-image is now the second
        # manifest's before-image, while the chained after-image is current.
        chain = sfh2r_contract.transition_manifests()
        self.assertEqual(2, len(chain))
        self.assertEqual(
            transition["after_hashes"],
            chain[1]["active_input_transition"]["before_hashes"],
        )
        self.assertEqual(
            chain[1]["active_input_transition"]["after_hashes"],
            sfh2r_contract.current_repair_input_hashes(),
        )
        self.assertTrue(
            sfh2r_contract.frozen_hashes_are_current_or_authorized(
                transition["before_hashes"], transition["after_hashes"]
            )
        )
        changed = dict(transition["before_hashes"])
        first = next(iter(changed))
        changed[first] = "unrecorded-drift"
        self.assertFalse(
            sfh2r_contract.frozen_hashes_are_current_or_authorized(
                changed, transition["after_hashes"]
            )
        )


if __name__ == "__main__":
    unittest.main()
