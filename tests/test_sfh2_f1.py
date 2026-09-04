from __future__ import annotations

import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_a2o import provenance  # noqa: E402
from sfh2_a2or import prompt as a2or_prompt  # noqa: E402
from sfh2_a2ovb import common as a2ovb_common  # noqa: E402
from sfh2_a2ovb import prompt as a2ovb_prompt  # noqa: E402
from sfh2_f1 import common as f1_common  # noqa: E402
from sfh2_f1 import pipeline as f1_pipeline  # noqa: E402


class SFH22F1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.selection = f1_common.selection_rows()
        cls.inputs = f1_common.load_inputs()
        cls.packets = {
            row["occurrence_id"]: f1_common.build_packet(f1_common.case_from_row(row), cls.inputs)
            for row in cls.selection
        }

    def test_frozen_selection_is_exactly_30_occurrences_and_25_stories(self) -> None:
        self.assertEqual(len(self.selection), 30)
        self.assertEqual(len({row["exact_occurrence_key"]["story_id"] for row in self.selection}), 25)
        keys = [f1_common.exact_key(row) for row in self.selection]
        self.assertEqual(len(keys), len({json.dumps(key, ensure_ascii=False, sort_keys=True) for key in keys}))
        self.assertTrue(all(f1_common.validate_exact_occurrence(row, self.packets[row["occurrence_id"]])["valid"] for row in self.selection))

    def test_provenance_is_structural_and_provider_packets_are_gold_free(self) -> None:
        for row in self.selection:
            packet = self.packets[row["occurrence_id"]]
            derived, errors = provenance.derive_provenance_layer(packet)
            self.assertFalse(errors)
            self.assertEqual(derived, packet["provenance_layer"])
            occurrence_payload = a2or_prompt.provider_payload(packet)
            encoded_occurrence = json.dumps(occurrence_payload, ensure_ascii=False, sort_keys=True).lower()
            self.assertNotIn('"gold"', encoded_occurrence)
            self.assertNotIn('"expected_', encoded_occurrence)

    def test_boundary_packet_has_no_primary_or_gold_hypothesis(self) -> None:
        packet = next(iter(self.packets.values()))
        payload = a2ovb_common.provider_payload(packet)
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
        for forbidden in (
            "primary_narrative_function",
            "primary_confidence",
            "primary_reason_summary",
            "a2ov_review",
            "residual_error",
            "occurrence_role",
            '"gold"',
        ):
            self.assertNotIn(forbidden, encoded)
        self.assertNotIn("primary", encoded)
        self.assertNotIn("residual", encoded)
        self.assertNotIn("gold", encoded)
        self.assertTrue(a2ovb_prompt.HISTORIAN_SYSTEM)

    def test_frozen_dag_routes_only_structured_primary_boundary_functions(self) -> None:
        functions = ["participant", "reference", "speaker", "addressee", "collective_reference"]
        self.assertEqual(
            [function in {"participant", "reference"} for function in functions],
            [True, True, False, False, False],
        )
        self.assertNotRegex(f1_pipeline._run_boundary.__code__.co_consts.__repr__(), re.compile(r"\b(?:康伯|文度|齊桓公)\b"))

    def test_checkpoint_matching_hash_reuses_and_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_out = Path(temporary)
            with patch.object(f1_pipeline, "OUT", temporary_out):
                unit_id = "occurrence_primary:test-occurrence"
                request_hash = f1_common.stable_hash({"request": 1})
                output = {"valid": True, "candidate_only": True, "canonical_write_back": False}
                f1_pipeline._save_checkpoint(unit_id, request_hash, output, status="completed", contract_valid=True)
                reused, valid = f1_pipeline._load_checkpoint(unit_id, request_hash)
                self.assertTrue(valid)
                self.assertEqual(output, reused)
                with self.assertRaisesRegex(RuntimeError, "checkpoint_request_hash_mismatch"):
                    f1_pipeline._load_checkpoint(unit_id, f1_common.stable_hash({"request": 2}))

    def test_boundary_mapping_and_projection_are_generic(self) -> None:
        case = {
            "case_id": "c",
            "occurrence_id": "o",
            "mention_id": "m",
            "story_id": "s",
            "source_evidence_id": "e",
            "source_start": 0,
            "source_end": 1,
            "surface": "甲",
        }
        packet = {
            "provenance_layer": "liu_annotation",
            "source_evidence": [{"evidence_id": "e", "source_layer": "liu_annotation"}],
        }
        identity = {"context": {"frozen_identity": {}, "frozen_discourse_context": {}}, "status": "not_applicable"}
        primary = {"valid": True, "occurrence_result": {"narrative_function": "participant", "confidence": "high"}}
        boundary = {"valid": True, "boundary_judgment": "referential_only", "confidence": "high"}
        candidate = f1_pipeline._candidate(case, packet, identity, primary, boundary)
        self.assertEqual(candidate["occurrence_semantics"]["final_narrative_function"], "reference")
        self.assertEqual(candidate["occurrence_semantics"]["projected_legacy_occurrence_role"], "annotation_person")
        self.assertEqual(provenance.project_legacy_occurrence_role("liu_annotation", "reference"), "annotation_person")

    def test_candidate_safety_and_no_surface_specific_semantics(self) -> None:
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "scripts" / "sfh2_f1").glob("*.py")
        )
        self.assertNotRegex(source, r"surface\s*(?:==|!=|\bin\b)")
        self.assertNotRegex(source, r"(?:康伯|文度|齊桓公|顧|王師)")
        self.assertNotIn("canonical_write_back\\\": true", source)
        for row in self.selection:
            self.assertTrue(row["candidate_only"])
            self.assertFalse(row["canonical_write_back"])

    def test_frozen_hashes_are_known_before_live_run(self) -> None:
        self.assertEqual(
            f1_common.file_hash(ROOT / "data/derived/sc1-site.json"),
            "cc82c6738fcbf4fc14c12005a459048e71ce329492867d0910562fc6fdfda0d8",
        )
        self.assertEqual(
            f1_common.file_hash(ROOT / "data/derived/sc1-current-site.json"),
            "b916530264285dd7fa1d2e27a7a1dff8cd2ed794dfb3b84985881f8f209d8f6a",
        )

    def test_frozen_prep_policies_are_loaded_and_recorded(self) -> None:
        policies = f1_common.frozen_policy_documents()
        self.assertEqual(
            set(policies),
            {"checkpoint", "cache_reuse", "provider_failure", "review_routing", "stop_conditions", "success_gate"},
        )
        architecture = f1_common.read_json(f1_common.OUT / "architecture-verification.json", {})
        self.assertEqual(architecture.get("frozen_policy_hashes"), f1_common.frozen_policy_hashes(policies))
        self.assertEqual(len(architecture.get("frozen_policy_paths", [])), 6)

    def test_completed_wave_resume_and_candidate_safety_are_recorded(self) -> None:
        metrics = f1_common.read_json(f1_common.OUT / "metrics.json", {})
        resume = f1_common.read_json(f1_common.OUT / "resume-validation.json", {})
        self.assertEqual(metrics.get("selected_occurrences"), 30)
        self.assertEqual(metrics.get("selected_stories"), 25)
        self.assertEqual(metrics.get("completed_candidate_records"), 30)
        self.assertEqual(metrics.get("new_historical_person_candidate_count"), 12)
        self.assertTrue(resume.get("deterministic_resume"))
        self.assertEqual(resume.get("phase_b_new_provider_calls_for_phase_a_occurrences"), 0)
        self.assertEqual(resume.get("phase_b_duplicate_semantic_writes"), 0)
        self.assertEqual(metrics.get("provider_accounting", {}).get("cache_hits"), 1)

    def test_checkpoint_schema_and_cached_provider_witness_are_preserved(self) -> None:
        checkpoint_paths = sorted((f1_common.OUT / "checkpoints").glob("*.json"))
        self.assertEqual(len(checkpoint_paths), 147)
        required = {
            "unit_id", "request_hash", "status", "attempt", "contract_valid",
            "output_hash", "provider_witness_hash", "runtime_metadata", "output",
        }
        for path in checkpoint_paths:
            checkpoint = f1_common.read_json(path, {})
            self.assertTrue(required.issubset(checkpoint))
            self.assertEqual(checkpoint.get("output_hash"), f1_common.stable_hash(checkpoint.get("output")))
        occurrence = f1_common.read_json(f1_common.OUT / "occurrence-primary-results.json", {})
        cache_rows = [row for row in occurrence.get("records", []) if row.get("cache_hit") is True]
        self.assertEqual(len(cache_rows), 1)
        self.assertTrue(cache_rows[0].get("transport", {}).get("provider_witness_hash"))

    def test_f1_does_not_import_a2ov_or_add_surface_semantics(self) -> None:
        source = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "scripts" / "sfh2_f1").glob("*.py"))
        self.assertNotRegex(source, r"\bsfh2_a2ov(?:\W|$)")
        self.assertNotRegex(source, r"surface\s*(?:==|!=|\bin\b)")


if __name__ == "__main__":
    unittest.main()
