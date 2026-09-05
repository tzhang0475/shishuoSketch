from __future__ import annotations

import copy
import sys
import unittest
import importlib.util
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from sfh2_f1rt import common  # noqa: E402

_RUNNER_SPEC = importlib.util.spec_from_file_location(
    "sfh2_f1rt_runner", Path(__file__).resolve().parents[1] / "scripts/run_sfh2_f1rt.py"
)
assert _RUNNER_SPEC and _RUNNER_SPEC.loader
_RUNNER = importlib.util.module_from_spec(_RUNNER_SPEC)
_RUNNER_SPEC.loader.exec_module(_RUNNER)


class SFH2F1RTTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = common.load_bundle()
        inventory = common.failure_inventory(cls.bundle)
        cls.inventory = common.failure_inventory_with_requests(cls.bundle, inventory)

    def test_full_invalid_stage_inventory_is_accounted(self) -> None:
        self.assertEqual(self.inventory["full_invalid_stage_unit_count"], 15)
        self.assertEqual(self.inventory["terminal_identity_block_count"], 6)
        self.assertEqual(self.inventory["terminal_identity_block_case_count"], 3)
        self.assertEqual(sum(row["original_request"]["hash_matches"] for row in self.inventory["records"]), 15)
        self.assertEqual(sum(row["stage"].startswith("identity_") for row in self.inventory["records"]), 14)

    def test_body_schema_excludes_provider_routing_envelope(self) -> None:
        document = common.body_schema_document()
        for tool_name in ("primary_tool", "independent_tool"):
            record = document[tool_name]["function"]["parameters"]["properties"]["record"]
            self.assertNotIn("mention_id", record["properties"])
            self.assertNotIn("surface", record["properties"])
            self.assertNotIn("mention_id", record["required"])
            self.assertNotIn("surface", record["required"])
        self.assertIn("mention_id", document["python_owned_immutable_envelope_fields"])
        self.assertIn("request_hash", document["python_owned_immutable_envelope_fields"])

    def test_body_validation_attaches_ids_only_after_body_validation(self) -> None:
        occurrence_id = "sfh1-mention-ba0a6bfd3b70867199867b3a"
        row = self.bundle["identity_results"][occurrence_id]["historian_primary"]
        record = copy.deepcopy(row["record"])
        record.pop("mention_id")
        record.pop("surface")
        valid = common.validate_semantic_body(self.bundle["packets"][occurrence_id], {"record": record})
        self.assertTrue(valid["valid"])
        self.assertEqual(valid["record"]["mention_id"], occurrence_id)
        self.assertEqual(valid["record"]["surface"], "孔巖")
        invalid = copy.deepcopy(record)
        invalid["mention_id"] = "wrong"
        rejected = common.validate_semantic_body(self.bundle["packets"][occurrence_id], {"record": invalid})
        self.assertFalse(rejected["valid"])
        self.assertTrue(any("body_forbidden" in error for error in rejected["errors"]))

    def test_recovery_hash_is_distinct_and_attempt_is_bounded(self) -> None:
        for row in self.inventory["records"]:
            self.assertNotEqual(row["request_hash"], row["recovery_request_hash"])
            self.assertEqual(row["recovery_attempt"], "recovery_replay_1")
        policy = common.ROOT / "data/generated/sfh2-f-prep/provider-failure-policy.json"
        self.assertTrue(policy.is_file())

    def test_length_termination_is_truncation_not_generic_invalid_json(self) -> None:
        self.assertEqual(
            common.classify_transport_failure(
                {"finish_reason": "length", "parse_error": "function_arguments_invalid_json"},
                ["provider_failure_or_unavailable"],
            ),
            common.TRUNCATED_OUTPUT,
        )

    def test_controls_are_deterministic_and_transport_valid(self) -> None:
        first = common.control_selection(self.bundle)
        second = common.control_selection(self.bundle)
        self.assertEqual(first, second)
        self.assertEqual(first["control_count"], 6)
        self.assertEqual(len({item["occurrence_id"] for item in first["records"]}), 6)
        for item in first["records"]:
            self.assertTrue(item["primary_transport_valid"])
            self.assertTrue(item["independent_transport_valid"])

    def test_identity_packets_do_not_contain_prior_answers(self) -> None:
        forbidden = {"primary_narrative_function", "primary_confidence", "primary_reason_summary", "gold", "human_answer", "residual_error_labels"}
        for occurrence_id, packet in self.bundle["packets"].items():
            primary, independent = common.identity_payloads(packet)
            for payload in (primary, independent):
                keys = set(payload)
                self.assertTrue(keys.isdisjoint(forbidden), occurrence_id)
                self.assertNotIn("occurrence_role", keys)

    def test_no_malformed_output_coercion(self) -> None:
        packet = self.bundle["packets"]["sfh1-mention-250c0ae68551d8dab4943ed8"]
        self.assertFalse(common.validate_semantic_body(packet, {"record": "{\"semantic_kind\":\"historical_person\"}"})["valid"])
        self.assertFalse(common.validate_semantic_body(packet, {"record": {}})["valid"])

    def test_control_comparison_separates_compatible_surface_drift(self) -> None:
        old = {
            "valid": True,
            "record": {
                "semantic_kind": "historical_person",
                "reference_type": "courtesy_name",
                "occurrence_role": "scene_participant",
                "referent": {"surface_form": "桓伊", "canonical_hint": "桓伊", "confidence": "high"},
                "bearer_hint": "",
                "attribute_type": "",
                "attribute_value": "",
                "abstain": False,
                "discourse": {"speaker_hint": "桓公", "addressee_hint": "桓子野"},
            },
        }
        new = copy.deepcopy(old)
        new["record"]["referent"]["surface_form"] = "子野"
        new["record"]["discourse"]["speaker_hint"] = "敘述者"
        comparison = _RUNNER._compare_control(old, new, "control", "identity_primary", "test")
        self.assertEqual(comparison["classification"], "compatible_semantic_match")
        self.assertEqual(comparison["core_difference_fields"], [])
        new["record"]["referent"]["canonical_hint"] = "另一人"
        disagreement = _RUNNER._compare_control(old, new, "control", "identity_primary", "test")
        self.assertEqual(disagreement["classification"], "semantic_disagreement")
        self.assertEqual(disagreement["core_difference_fields"], ["referent_canonical_hint"])

    def test_protected_snapshot_and_candidate_flags(self) -> None:
        snapshot = common.protected_snapshot()
        self.assertIn("data/generated/sfh2-f1", snapshot)
        self.assertIn("data/frozen/sfh2/semantic-v1", snapshot)
        envelope = common.candidate_envelope(self.bundle["cases"]["sfh1-mention-ba0a6bfd3b70867199867b3a"], "a" * 64, "identity_primary")
        self.assertTrue(envelope["candidate_only"])
        self.assertFalse(envelope["canonical_write_back"])


if __name__ == "__main__":
    unittest.main()
