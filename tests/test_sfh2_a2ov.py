from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_a2o.provenance import project_legacy_occurrence_role  # noqa: E402
from sfh2_a2ov.common import (  # noqa: E402
    ACTIVE_GOLD_SHA256,
    A2OS_ROOT,
    A2OR_ROOT,
    A2OSP_ROOT,
    CASE_COUNT,
    CURRENT_SC1_SHA256,
    FROZEN_SC1_SHA256,
    GOLD_PATH,
    IDENTITY_MANIFEST_SHA256,
    load_frozen_bundle,
    protected_hashes,
    reviewer_payload,
    stable_hash,
)
from sfh2_a2ov.contracts import (  # noqa: E402
    DECISIONS,
    NARRATIVE_FUNCTIONS,
    reviewer_tool,
    validate_deepseek_strict_schema,
    validate_probe_payload,
    validate_reviewer_payload,
)
from sfh2_a2ov.pipeline import _primary_final_result, exact_occurrence_key_for_packet  # noqa: E402
from sfh2_a2ov.prompt import HISTORIAN_SYSTEM  # noqa: E402


class SFH22A2OVTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = load_frozen_bundle()

    def test_exact_same_26_occurrence_keys_are_reused(self) -> None:
        self.assertEqual(CASE_COUNT, len(self.bundle["case_ids"]))
        witness = {
            row["case_id"]: row["exact_occurrence_key"]
            for row in json.loads((A2OSP_ROOT / "a2or-post-promotion-evaluation.json").read_text(encoding="utf-8"))["records"]
        }
        for case_id in self.bundle["case_ids"]:
            self.assertEqual(witness[case_id], exact_occurrence_key_for_packet(self.bundle["packets"][case_id]))

    def test_reviewer_packet_contains_primary_but_not_gold_or_residual_labels(self) -> None:
        case_id = self.bundle["case_ids"][0]
        primary = self.bundle["primary_rows"][case_id]["occurrence_result"]
        payload = reviewer_payload(self.bundle["packets"][case_id], primary)
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        self.assertIn('"primary"', encoded)
        self.assertIn(primary["narrative_function"], encoded)
        for forbidden in (
            "expected_narrative_function",
            "expected_legacy_occurrence_role",
            "review_status",
            "qualified_genuine_semantic_error",
            "gold_alignment",
            "residual_error_family",
        ):
            self.assertNotIn(forbidden, encoded)

    def test_prompt_is_primary_aware_but_has_no_evaluation_names(self) -> None:
        self.assertIn("primary", HISTORIAN_SYSTEM.lower())
        self.assertIn("Do not rewrite a plausible primary answer", HISTORIAN_SYSTEM)
        for forbidden in ("康伯", "文度", "庾道季", "吾愧", "expected_narrative_function"):
            self.assertNotIn(forbidden, HISTORIAN_SYSTEM)

    def test_reviewer_contract_is_closed_and_nullable(self) -> None:
        tool = reviewer_tool()
        parameters = tool["function"]["parameters"]
        self.assertEqual(set(parameters["properties"]), set(parameters["required"]))
        self.assertFalse(parameters["additionalProperties"])
        self.assertEqual([], validate_deepseek_strict_schema(parameters))
        self.assertEqual(set(DECISIONS), set(parameters["properties"]["decision"]["enum"]))
        self.assertEqual({"type": "null"}, parameters["properties"]["revised_narrative_function"]["anyOf"][1])
        self.assertNotIn("identity", parameters["properties"])
        self.assertNotIn("provenance_layer", parameters["properties"])
        self.assertNotIn("occurrence_role", parameters["properties"])

    def test_contract_conditionals_and_identity_output_rejection(self) -> None:
        packet = {"case_id": "case", "source_evidence": [{"evidence_id": "ev"}]}
        base = {"case_id": "case", "confidence": "high", "supporting_evidence_ids": ["ev"], "reason_summary": "ok"}
        confirm = dict(base, decision="confirm_primary", revised_narrative_function=None)
        abstain = dict(base, decision="abstain", revised_narrative_function=None)
        revise = dict(base, decision="revise_function", revised_narrative_function="reference")
        self.assertTrue(validate_reviewer_payload(packet, confirm, "participant")["valid"])
        self.assertTrue(validate_reviewer_payload(packet, abstain, "participant")["valid"])
        self.assertTrue(validate_reviewer_payload(packet, revise, "participant")["valid"])
        self.assertFalse(validate_reviewer_payload(packet, dict(confirm, revised_narrative_function="reference"), "participant")["valid"])
        self.assertFalse(validate_reviewer_payload(packet, dict(base, decision="revise_function", revised_narrative_function=None), "participant")["valid"])
        self.assertFalse(validate_reviewer_payload(packet, dict(revise, identity="x"), "participant")["valid"])

    def test_probe_validates_schema_shape_without_case_semantics(self) -> None:
        probe = {"case_id": "schema-probe", "decision": "revise_function", "revised_narrative_function": "reference", "confidence": "high", "supporting_evidence_ids": [], "reason_summary": "schema"}
        self.assertTrue(validate_probe_payload(probe)["valid"])

    def test_confirm_and_abstain_copy_primary_exactly(self) -> None:
        packet = {"case_id": "case", "target": {"surface": "甲"}, "provenance_layer": "main_text"}
        primary = {"case_id": "case", "narrative_function": "reference", "confidence": "high", "supporting_evidence_ids": [], "reason_summary": "primary"}
        for decision in ("confirm_primary", "abstain"):
            row = {"case_id": "case", "exact_occurrence_key": {}, "story_id": "s", "mention_id": "m", "surface": "甲", "provenance_layer": "main_text", "primary": primary, "reviewer_valid": True, "reviewer_result": {"case_id": "case", "decision": decision, "revised_narrative_function": None, "confidence": "high", "supporting_evidence_ids": [], "reason_summary": "review"}, "identity_preserved": True, "provenance_preserved": True}
            final = _primary_final_result(row, packet)
            self.assertEqual(primary, final["final_semantic"])
            self.assertEqual(decision == "abstain", final["reviewer_abstained"])

    def test_revision_changes_only_narrative_function(self) -> None:
        packet = {"case_id": "case", "target": {"surface": "甲"}, "provenance_layer": "main_text"}
        primary = {"case_id": "case", "narrative_function": "participant", "confidence": "high", "supporting_evidence_ids": [], "reason_summary": "primary"}
        row = {"case_id": "case", "exact_occurrence_key": {}, "story_id": "s", "mention_id": "m", "surface": "甲", "provenance_layer": "main_text", "primary": primary, "reviewer_valid": True, "reviewer_result": {"case_id": "case", "decision": "revise_function", "revised_narrative_function": "reference", "confidence": "high", "supporting_evidence_ids": [], "reason_summary": "clear"}, "identity_preserved": True, "provenance_preserved": True}
        final = _primary_final_result(row, packet)
        changed = [key for key in set(primary) | set(final["final_semantic"]) if primary.get(key) != final["final_semantic"].get(key)]
        self.assertEqual(["narrative_function"], changed)
        self.assertEqual("reference", final["final_semantic"]["narrative_function"])

    def test_projection_is_generic_and_identity_is_not_changed(self) -> None:
        self.assertEqual("annotation_person", project_legacy_occurrence_role("liu_annotation", "participant"))
        self.assertEqual("scene_reference", project_legacy_occurrence_role("main_text", "reference"))
        self.assertEqual(set(NARRATIVE_FUNCTIONS), set(reviewer_tool()["function"]["parameters"]["properties"]["revised_narrative_function"]["anyOf"][0]["enum"]))

    def test_no_surface_specific_semantic_runtime_rule(self) -> None:
        for path in (ROOT / "scripts/sfh2_a2ov").glob("*.py"):
            self.assertIsNone(re.search(r"surface\s*(?:==|in)", path.read_text(encoding="utf-8")), path.name)

    def test_protected_hashes_are_unchanged(self) -> None:
        self.assertEqual(ACTIVE_GOLD_SHA256, protected_hashes()["data/annotation/sfh2-a2o-evaluation-gold.json"]["sha256"])
        self.assertEqual(FROZEN_SC1_SHA256, protected_hashes()["data/derived/sc1-site.json"]["sha256"])
        self.assertEqual(CURRENT_SC1_SHA256, protected_hashes()["data/derived/sc1-current-site.json"]["sha256"])
        self.assertEqual(IDENTITY_MANIFEST_SHA256, protected_hashes()["data/frozen/sfh2/identity-v1/manifest.json"]["sha256"])

    def test_historical_a2ov_inputs_have_not_been_rewritten(self) -> None:
        for root in (A2OS_ROOT, A2OR_ROOT, A2OSP_ROOT):
            self.assertTrue(root.is_dir())
        self.assertEqual(stable_hash(self.bundle["selection_integrity"]), stable_hash(json.loads((A2OSP_ROOT / "selection-integrity-invariant.json").read_text(encoding="utf-8"))))
        self.assertEqual(GOLD_PATH, ROOT / "data/annotation/sfh2-a2o-evaluation-gold.json")


if __name__ == "__main__":
    unittest.main()
