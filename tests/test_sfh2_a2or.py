from __future__ import annotations

import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_a0r.contracts import validate_deepseek_strict_schema  # noqa: E402
from sfh2_a2o.provenance import project_legacy_occurrence_role  # noqa: E402
from sfh2_a2or.common import (  # noqa: E402
    A2O_ROOT,
    GOLD_PATH,
    load_frozen_a2o,
    old_gold_map,
    protected_hashes,
    read_json,
    stable_hash,
    text,
)
from sfh2_a2or.contracts import occurrence_function_tool, validate_occurrence_payload  # noqa: E402
from sfh2_a2or.pipeline import _architecture, _case_packets_document, _selection_verification  # noqa: E402
from sfh2_a2or.prompt import HISTORIAN_SYSTEM, provider_payload  # noqa: E402
from sfh2_a2or.transport import is_retryable  # noqa: E402


class SFH22A2ORTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = load_frozen_a2o()

    def test_exact_frozen_26_case_selection_and_packets_are_reused(self):
        self.assertEqual(26, len(self.bundle["selections"]))
        source_rows = read_json(A2O_ROOT / "case-packets.json", {}).get("packets", [])
        source_map = {text(row.get("case_id")): row.get("packet") for row in source_rows}
        for case_id, packet in self.bundle["packets"].items():
            self.assertEqual(stable_hash(source_map[case_id]), stable_hash(packet))
        self.assertEqual(self.bundle["selection_document"]["selection_hash"], _selection_verification(self.bundle)["selection_hash"])

    def test_new_contract_is_strict_and_identity_free(self):
        tool = occurrence_function_tool()
        parameters = tool["function"]["parameters"]
        self.assertEqual(set(parameters["properties"]), set(parameters["required"]))
        self.assertFalse(parameters["additionalProperties"])
        self.assertEqual([], validate_deepseek_strict_schema(parameters))
        self.assertNotIn("referent", parameters["properties"])
        self.assertNotIn("semantic_kind", parameters["properties"])
        self.assertNotIn("occurrence_role", parameters["properties"])

    def test_provider_payload_contains_no_gold(self):
        packet = self.bundle["packets"][text(self.bundle["selections"][0]["case_id"])]
        encoded = json.dumps(provider_payload(packet), ensure_ascii=False, sort_keys=True)
        self.assertNotIn("expected_narrative_function", encoded)
        self.assertNotIn("expected_legacy_occurrence_role", encoded)
        self.assertNotIn("review_status", encoded)

    def test_v2_prompt_has_abstract_clarifications_without_gold_case_names(self):
        for forbidden in ("宣武", "齊桓公", "滔", "嘏", "王師", "薛瑩", "字景真", "expected_narrative_function"):
            self.assertNotIn(forbidden, HISTORIAN_SYSTEM)
        self.assertIn("grammatical object of a communication or interaction verb is not automatically an addressee", HISTORIAN_SYSTEM)
        self.assertIn("entity merely appearing inside cited material is not the citation source", HISTORIAN_SYSTEM)

    def test_gold_has_exactly_one_substantive_record_mutation(self):
        active = {text(row.get("case_id")): row for row in read_json(GOLD_PATH, {}).get("records", [])}
        previous = old_gold_map(self.bundle)
        differences = [case_id for case_id in previous if active.get(case_id) != previous[case_id]]
        self.assertEqual(["sfh2-a0r-l-challenge-c07bd51ac298529ddbc6"], differences)
        changed = active[differences[0]]
        self.assertEqual("participant", changed["expected_narrative_function"])
        self.assertEqual("scene_participant", changed["expected_legacy_occurrence_role"])
        self.assertEqual(1, read_json(GOLD_PATH, {})["gold_revision"]["substantive_mutation_count"])

    def test_human_authority_records_gold_promotion_hashes(self):
        authority = read_json(ROOT / "data/annotation/sfh2-a2or-human-semantic-authority.json", {})
        self.assertEqual("human_semantic_review", authority["authority"])
        self.assertEqual("SFH2.2-A2OT", authority["predecessor_stage"])
        self.assertEqual(hashlib.sha256((ROOT / "data/annotation/sfh2-a2o-evaluation-gold.json").read_bytes()).hexdigest(), authority["new_gold_sha256"])
        self.assertEqual(1, authority["substantive_gold_mutation_count"])
        record = authority["records"][0]
        self.assertEqual(8, record["source_start"])
        self.assertEqual(10, record["source_end"])

    def test_identity_is_only_frozen_input(self):
        packet = self.bundle["packets"][text(self.bundle["selections"][0]["case_id"])]
        payload = {"case_id": packet["case_id"], "narrative_function": "reference", "confidence": "high", "supporting_evidence_ids": [], "reason_summary": ""}
        validated = validate_occurrence_payload(packet, payload)
        self.assertTrue(validated["valid"])
        self.assertIn("referent", packet["frozen_identity_context"])
        self.assertNotIn("referent", validated["result"])

    def test_compatibility_projection_remains_generic(self):
        self.assertEqual("annotation_person", project_legacy_occurrence_role("liu_annotation", "participant"))
        self.assertEqual("citation_source_person", project_legacy_occurrence_role("liu_annotation", "citation_source"))
        self.assertEqual("scene_participant", project_legacy_occurrence_role("main_text", "participant"))
        self.assertEqual("addressee_reference", project_legacy_occurrence_role("main_text", "addressee"))

    def test_transport_400_is_not_retried_but_transient_is(self):
        bad = RuntimeError("HTTP 400")
        bad.http_status = 400
        self.assertFalse(is_retryable(bad))
        transient = RuntimeError("HTTP 503")
        transient.http_status = 503
        self.assertTrue(is_retryable(transient))

    def test_a2or_runtime_has_no_surface_specific_semantic_rule(self):
        for path in (ROOT / "scripts/sfh2_a2or").glob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotRegex(source, re.compile(r"surface\s*==|surface\s+in"))

    def test_preparation_is_candidate_only_and_protected(self):
        architecture = _architecture(self.bundle)
        packets = _case_packets_document(self.bundle)
        self.assertTrue(architecture["candidate_only"])
        self.assertFalse(architecture["canonical_write_back"])
        self.assertTrue(packets["same_packets_as_a2o"])
        hashes = protected_hashes()
        self.assertEqual("cc82c6738fcbf4fc14c12005a459048e71ce329492867d0910562fc6fdfda0d8", hashes["data/derived/sc1-site.json"])
        self.assertEqual("b916530264285dd7fa1d2e27a7a1dff8cd2ed794dfb3b84985881f8f209d8f6a", hashes["data/derived/sc1-current-site.json"])


if __name__ == "__main__":
    unittest.main()
