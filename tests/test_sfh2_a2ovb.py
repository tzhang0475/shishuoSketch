from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_a2o.provenance import project_legacy_occurrence_role  # noqa: E402
from sfh2_a2o.provenance import derive_provenance_layer  # noqa: E402
from sfh2_a2ovb.common import (  # noqa: E402
    ACTIVE_GOLD_SHA256,
    A2OSP_ROOT,
    CASE_COUNT,
    CURRENT_SC1_SHA256,
    FROZEN_SC1_SHA256,
    GOLD_PATH,
    IDENTITY_MANIFEST_SHA256,
    boundary_case_ids,
    exact_occurrence_key,
    file_hash,
    load_frozen_bundle,
    primary_function,
    protected_hashes,
    provider_payload,
)
from sfh2_a2ovb.contracts import BOUNDARY_JUDGMENTS, boundary_tool, validate_boundary_payload, validate_deepseek_strict_schema  # noqa: E402
from sfh2_a2ovb.pipeline import _final_row  # noqa: E402
from sfh2_a2ovb.prompt import HISTORIAN_SYSTEM  # noqa: E402


class SFH22A2OVBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = load_frozen_bundle()

    def test_boundary_cohort_comes_only_from_frozen_a2or_output(self) -> None:
        expected = [case_id for case_id in self.bundle["case_ids"] if primary_function(self.bundle["primary_rows"][case_id]) in {"participant", "reference"}]
        self.assertEqual(expected, boundary_case_ids(self.bundle))
        self.assertEqual(CASE_COUNT, len(self.bundle["case_ids"]))

    def test_exact_occurrence_keys_match_a2osp_witness(self) -> None:
        witness = {
            row["case_id"]: row["exact_occurrence_key"]
            for row in json.loads((A2OSP_ROOT / "a2or-post-promotion-evaluation.json").read_text(encoding="utf-8"))["records"]
        }
        for case_id in self.bundle["case_ids"]:
            self.assertEqual(witness[case_id], exact_occurrence_key(self.bundle["packets"][case_id]))

    def test_provenance_is_derived_from_evidence_metadata_only(self) -> None:
        case_id = self.bundle["case_ids"][0]
        packet = json.loads(json.dumps(self.bundle["packets"][case_id], ensure_ascii=False))
        layer, errors = derive_provenance_layer(packet)
        self.assertFalse(errors)
        target_id = packet["target"]["source_evidence_id"]
        for evidence in packet["source_evidence"]:
            if evidence["evidence_id"] == target_id:
                evidence["source_layer"] = "synthetic_structural_layer"
        changed_layer, changed_errors = derive_provenance_layer(packet)
        self.assertFalse(changed_errors)
        self.assertNotEqual(layer, changed_layer)

    def test_provider_packet_is_blind_to_prior_semantics_and_gold(self) -> None:
        for case_id in boundary_case_ids(self.bundle):
            payload = provider_payload(self.bundle["packets"][case_id])
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            for forbidden in (
                "primary_function", "primary_confidence", "primary_reason_summary", "occurrence_role",
                "legacy_occurrence_role", "expected_narrative_function", "expected_legacy", "residual_error",
                "reviewer_decision", "gold_alignment",
            ):
                self.assertNotIn(forbidden, encoded)
            self.assertNotIn("primary", encoded.lower())
            self.assertNotIn("gold", encoded.lower())
            self.assertNotIn("residual", encoded.lower())

    def test_prompt_has_no_known_case_leakage(self) -> None:
        for forbidden in ("康伯", "文度", "庾道季", "吾愧", "09-pinzao-063", "expected_narrative_function"):
            self.assertNotIn(forbidden, HISTORIAN_SYSTEM)
        self.assertNotIn("primary", HISTORIAN_SYSTEM.lower())

    def test_narrow_contract_is_closed(self) -> None:
        tool = boundary_tool()
        parameters = tool["function"]["parameters"]
        self.assertEqual(set(parameters["properties"]), set(parameters["required"]))
        self.assertFalse(parameters["additionalProperties"])
        self.assertEqual([], validate_deepseek_strict_schema(parameters))
        self.assertEqual(set(BOUNDARY_JUDGMENTS), set(parameters["properties"]["boundary_judgment"]["enum"]))
        self.assertNotIn("narrative_function", parameters["properties"])
        self.assertNotIn("occurrence_role", parameters["properties"])
        self.assertNotIn("identity", parameters["properties"])
        self.assertNotIn("provenance_layer", parameters["properties"])

    def test_output_validation_rejects_semantic_replacement_fields(self) -> None:
        case_id = boundary_case_ids(self.bundle)[0]
        packet = provider_payload(self.bundle["packets"][case_id])
        good = {"case_id": case_id, "boundary_judgment": "uncertain", "confidence": "low", "supporting_evidence_ids": [], "reason_summary": "insufficient"}
        self.assertTrue(validate_boundary_payload(packet, good)["valid"])
        self.assertFalse(validate_boundary_payload(packet, dict(good, narrative_function="reference"))["valid"])
        self.assertFalse(validate_boundary_payload(packet, dict(good, provenance_layer="main_text"))["valid"])

    def test_uncertain_preserves_primary_and_projection_is_generic(self) -> None:
        case_id = boundary_case_ids(self.bundle)[0]
        packet = self.bundle["packets"][case_id]
        primary = self.bundle["primary_rows"][case_id]["occurrence_result"]
        row = {"case_id": case_id, "validator_valid": True, "validator_result": {"case_id": case_id, "boundary_judgment": "uncertain", "confidence": "low", "supporting_evidence_ids": [], "reason_summary": "uncertain"}}
        final = _final_row(case_id, self.bundle, {case_id: dict(row)})
        self.assertEqual(primary, final["final_semantic"])
        self.assertEqual(project_legacy_occurrence_role(packet["provenance_layer"], primary["narrative_function"]), final["final_legacy_occurrence_role"])

    def test_non_boundary_is_exact_primary_copy(self) -> None:
        case_id = next(case_id for case_id in self.bundle["case_ids"] if case_id not in boundary_case_ids(self.bundle))
        primary = self.bundle["primary_rows"][case_id]["occurrence_result"]
        final = _final_row(case_id, self.bundle, {})
        self.assertEqual(primary, final["final_semantic"])

    def test_protected_hashes_and_no_surface_rule(self) -> None:
        hashes = protected_hashes()
        self.assertEqual(ACTIVE_GOLD_SHA256, hashes[GOLD_PATH.relative_to(ROOT).as_posix()]["sha256"])
        self.assertEqual(FROZEN_SC1_SHA256, hashes["data/derived/sc1-site.json"]["sha256"])
        self.assertEqual(CURRENT_SC1_SHA256, hashes["data/derived/sc1-current-site.json"]["sha256"])
        self.assertEqual(IDENTITY_MANIFEST_SHA256, hashes["data/frozen/sfh2/identity-v1/manifest.json"]["sha256"])
        for path in (ROOT / "scripts/sfh2_a2ovb").glob("*.py"):
            self.assertIsNone(re.search(r"surface\s*(?:==|in)", path.read_text(encoding="utf-8")), path.name)

    def test_live_output_if_present_has_expected_coverage(self) -> None:
        output = ROOT / "data/generated/sfh2-a2ovb"
        accounting_path = output / "provider-accounting.json"
        if not accounting_path.is_file():
            return
        accounting = json.loads(accounting_path.read_text(encoding="utf-8"))
        boundary_count = len(boundary_case_ids(self.bundle))
        self.assertEqual(boundary_count + 1, accounting.get("provider_calls"))
        self.assertEqual(boundary_count, accounting.get("boundary_validator_calls"))


if __name__ == "__main__":
    unittest.main()
