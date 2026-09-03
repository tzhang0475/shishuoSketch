from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PREDECESSOR_GOLD_SHA256 = "82f36497b632032bc164c09fd5db97e35e20c256fc9654ac0d2c9b4c704b0b93"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_sfh2_a2g as audit  # noqa: E402


class SFH22A2GAuditTests(unittest.TestCase):
    def test_joint_failure_does_not_require_ab_identity_string_agreement(self) -> None:
        row = {
            "historical_identity_evaluable": True,
            "historian_a": {"identity_correct": False},
            "historian_b": {
                "identity_correct": False,
                "identity_string": "a different wrong representation",
            },
        }
        self.assertTrue(audit.identity_joint_failure(row))

    def test_boundary_observation_is_ontology_based(self) -> None:
        gold = {"expected_semantic_kind": "historical_person"}
        a = {"valid": True, "record": {"semantic_kind": "office"}}
        b = {"valid": True, "record": {"semantic_kind": "office"}}
        final = {"selected_record": {"semantic_kind": "office"}}

        result = audit.boundary_observation(gold, a, b, final)

        self.assertTrue(result["apparent_gold_ontology_boundary_conflict"])
        self.assertEqual(result["boundary_type"], "historical_person_vs_office")

    def test_final_selected_record_is_not_dropped_as_invalid(self) -> None:
        result = audit.stage_view(
            {"selected_record": {"semantic_kind": "collective"}},
            record_key="selected_record",
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["semantic_record"]["semantic_kind"], "collective")

    def test_disagreement_taxonomy_keeps_contract_category_separate(self) -> None:
        rows = [
            {
                "case_id": "contract",
                "substantive_disagreement": True,
                "disagreement_classes": ["contract_validity_disagreement"],
                "substantive_fields": ["contract_validity"],
            },
            {
                "case_id": "identity",
                "substantive_disagreement": True,
                "disagreement_classes": ["identity_disagreement"],
                "substantive_fields": ["referent.canonical_hint"],
            },
            {
                "case_id": "role",
                "substantive_disagreement": True,
                "disagreement_classes": ["occurrence_role_disagreement"],
                "substantive_fields": ["occurrence_role"],
            },
            {
                "case_id": "discourse",
                "substantive_disagreement": True,
                "disagreement_classes": ["discourse_disagreement"],
                "substantive_fields": ["discourse.speaker_hint"],
            },
        ]
        result = audit.build_disagreement_taxonomy(rows)
        self.assertEqual(result["substantive_disagreement_count"], 4)
        self.assertEqual(result["requested_buckets"]["contract_validity_critical"], 1)
        self.assertEqual(result["requested_buckets"]["identity_or_semantic_kind_critical"], 1)
        self.assertEqual(result["requested_buckets"]["occurrence_role_critical"], 1)
        self.assertEqual(result["requested_buckets"]["discourse_or_relation_only"], 1)

    def test_a2g_build_is_deterministic(self) -> None:
        first = audit.build_outputs()
        second = audit.build_outputs()
        self.assertEqual(
            {name: audit.canonical_json(value) for name, value in first.items()},
            {name: audit.canonical_json(value) for name, value in second.items()},
        )

    def test_a2g_does_not_mutate_frozen_inputs(self) -> None:
        before = audit.protected_input_hashes()
        audit.build_outputs()
        after = audit.protected_input_hashes()
        self.assertEqual(before, after)

    def test_provider_free_outputs_and_no_surface_rules(self) -> None:
        metrics = audit.load_json(audit.OUT / "metrics.json")
        architecture = audit.load_json(audit.OUT / "architecture-freeze.json")
        self.assertEqual(metrics["provider_calls"], 0)
        self.assertFalse(metrics["provider_or_network_used"])
        self.assertFalse(architecture["gold_in_provider_prompt"])
        source = (ROOT / "scripts/run_sfh2_a2g.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"surface\s*==|surface\s+in", source))

    def test_a2g_retains_predecessor_gold_witness_after_reviewed_promotion(self) -> None:
        path = ROOT / "data/annotation/sfh2-a0-evaluation-gold.json"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertNotEqual(digest, PREDECESSOR_GOLD_SHA256)
        self.assertEqual("sfh2-a0-evaluation-gold-v3", json.loads(path.read_text(encoding="utf-8"))["schema"])
        witness = audit.load_json(audit.OUT / "input-hashes.json")
        self.assertEqual(PREDECESSOR_GOLD_SHA256, witness["files"]["data/annotation/sfh2-a0-evaluation-gold.json"])


if __name__ == "__main__":
    unittest.main()
