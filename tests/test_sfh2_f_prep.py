from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_f_prep.common import (  # noqa: E402
    BASELINE_COMMIT,
    FROZEN_OUT,
    OUT,
    SC1_CURRENT,
    SC1_FROZEN,
    file_hash,
    protected_hashes,
    read_json,
)


class SFH22FPrepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scope = read_json(OUT / "production-scope.json", {})
        cls.occurrence_audit = read_json(OUT / "exact-occurrence-audit.json", {})
        cls.occurrence_manifest = read_json(OUT / "occurrence-manifest.json", {})
        cls.readiness = read_json(OUT / "identity-readiness.json", {})
        cls.architecture = read_json(FROZEN_OUT / "architecture.json", {})
        cls.dag = read_json(OUT / "production-dag.json", {})
        cls.cache = read_json(OUT / "cache-reuse-plan.json", {})
        cls.preflight = read_json(OUT / "preflight-validation.json", {})

    def test_scope_is_derived_and_exact(self) -> None:
        self.assertEqual(self.scope["authoritative_story_source"], {
            "path": "data/generated/sfh1/story-packets.json",
            "sha256": self.scope["authoritative_story_source"]["sha256"],
            "size_bytes": self.scope["authoritative_story_source"]["size_bytes"],
            "exists": True,
        })
        self.assertEqual(self.scope["total_stories"], 188)
        self.assertEqual(self.scope["eligible_story_count"], 188)
        self.assertEqual(self.scope["published_runtime_story_count"], 143)
        self.assertEqual(self.scope["research_only_story_count"], 45)
        self.assertEqual(self.scope["total_validated_occurrences"], 3303)

    def test_exact_occurrence_integrity_and_repeated_spans_are_explicit(self) -> None:
        self.assertEqual(self.occurrence_audit["occurrence_count"], 3303)
        self.assertEqual(self.occurrence_audit["invalid_occurrence_count"], 0)
        self.assertEqual(self.occurrence_audit["duplicate_exact_key_count"], 0)
        self.assertGreater(self.occurrence_audit["overlap_pair_count"], 0)
        self.assertGreater(self.occurrence_audit["repeated_surface_group_count"], 0)
        self.assertTrue(self.occurrence_manifest["surface_only_selection_forbidden"])
        self.assertEqual(
            set(self.occurrence_manifest["occurrence_key_fields"]),
            {"occurrence_id", "case_id", "mention_id", "story_id", "source_evidence_id", "source_start", "source_end", "surface"},
        )

    def test_qualified_architecture_excludes_primary_aware_reviewer(self) -> None:
        self.assertEqual(self.architecture["occurrence_multiclass"]["source_stage"], "SFH2.2-A2OR")
        self.assertEqual(self.architecture["boundary_validator"]["source_stage"], "SFH2.2-A2OVB")
        self.assertTrue(self.architecture["boundary_validator"]["primary_blind"])
        self.assertFalse(self.architecture["excluded_components"]["a2ov_primary_aware_reviewer"]["included_in_production"])
        self.assertNotIn("a2ov", {node["id"] for node in self.dag["nodes"]})

    def test_boundary_routing_is_structured_and_old_role_is_not_authority(self) -> None:
        self.assertTrue(self.dag["boundary_routing_is_structured_output_only"])
        self.assertTrue(self.dag["old_occurrence_role_is_not_authority"])
        boundary_edges = [edge for edge in self.dag["edges"] if edge[1] == "a2ovb_boundary"]
        self.assertEqual(len(boundary_edges), 1)
        self.assertIn("participant/reference", boundary_edges[0][2])

    def test_identity_readiness_is_partitioned_without_person_creation(self) -> None:
        counts = self.readiness["counts"]
        self.assertEqual(sum(counts.values()), 3303)
        self.assertEqual(counts["identity_ready"], 26)
        self.assertEqual(counts["identity_requires_pipeline"], 2842)
        self.assertEqual(counts["identity_not_applicable"], 435)
        self.assertEqual(counts.get("identity_blocked", 0), 0)
        for row in self.readiness["records"]:
            self.assertTrue(row["candidate_only"])
            self.assertFalse(row["canonical_write_back"])

    def test_cache_reuse_requires_all_exact_components(self) -> None:
        self.assertEqual(self.cache["exact_reusable_provider_result_count"], 41)
        self.assertEqual(self.cache["counts_by_stage"], {"boundary_validator": 15, "occurrence_primary": 26})
        self.assertTrue(self.cache["policy"]["reuse_requires_all_components"])
        for component in (
            "stage", "prompt_version", "schema_hash", "model", "temperature",
            "thinking", "exact_provider_packet", "exact_occurrence_key",
            "relevant_source_hashes", "frozen_identity_input_hash", "request_hash",
        ):
            self.assertIn(component, self.cache["policy"]["components"])
        for row in self.cache["entries"]:
            self.assertTrue(row["exact_reuse_candidate"])
            self.assertTrue(row["reuse_requires_current_request_hash_equality"])
            self.assertTrue(row["request_hash"])
            self.assertEqual(len(row["matching_key_fields"]), 6)

    def test_checkpoint_and_failure_policy_are_fail_closed(self) -> None:
        checkpoint = read_json(OUT / "checkpoint-policy.json", {})
        failure = read_json(OUT / "provider-failure-policy.json", {})
        self.assertIn("request_hash", checkpoint["checkpoint_fields"])
        self.assertIn("different_request_hash_rule", checkpoint)
        self.assertIn("never silently reuse", checkpoint["different_request_hash_rule"])
        self.assertFalse(failure["http_400"]["retry"])
        self.assertEqual(failure["transient_429_5xx_timeout_connection_reset"]["max_retries"], 1)
        self.assertFalse(failure["malformed_semantic_output"]["coerce"])

    def test_f1_is_bounded_unexecuted_and_gold_blind(self) -> None:
        f1 = read_json(OUT / "f1-selection.json", {})
        self.assertTrue(f1["not_executed"])
        self.assertFalse(f1["gold_used_for_selection"])
        self.assertFalse(f1["answer_leakage"])
        self.assertGreater(f1["occurrence_count"], 0)
        self.assertLessEqual(f1["occurrence_count"], 30)
        keys = [
            tuple(row["exact_occurrence_key"].get(field) for field in (
                "mention_id", "story_id", "source_evidence_id", "source_start", "source_end", "surface",
            ))
            for row in f1["records"]
        ]
        self.assertEqual(len(keys), len(set(keys)))
        coverage = f1["semantic_coverage_requirements"]
        self.assertTrue(coverage["selection_is_answer_blind"])
        self.assertTrue(coverage["semantic_categories_are_not_used_as_gold_selection_labels"])
        self.assertIn("citation_source", coverage["semantic_functions_to_audit_in_f1"])
        self.assertIn("historical_exemplum", coverage["semantic_functions_to_audit_in_f1"])
        self.assertIn("person_attribute", coverage["semantic_functions_to_audit_in_f1"])
        self.assertIn("collective_reference", coverage["semantic_functions_to_audit_in_f1"])

    def test_no_provider_or_lexical_semantics_in_f_prep_code(self) -> None:
        source = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "scripts/sfh2_f_prep").glob("*.py"))
        self.assertNotRegex(source, r"(?:^|\n)\s*(?:from|import)\s+(?:requests|httpx|openai|urllib)\b")
        self.assertNotRegex(source, r"surface\s*(?:==|!=|\bin\b)")
        self.assertNotRegex(source, r"(?:康伯|文度|齊桓公|太丘長)")

    def test_candidate_safety_and_no_provider_calls(self) -> None:
        self.assertEqual(self.preflight["baseline_commit"], BASELINE_COMMIT)
        self.assertEqual(self.preflight["provider_calls"], 0)
        self.assertEqual(self.preflight["provider_api_calls"], 0)
        self.assertTrue(self.preflight["candidate_only"])
        self.assertFalse(self.preflight["canonical_write_back"])
        for path in list(OUT.glob("*.json")) + list(FROZEN_OUT.glob("*.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            encoded = json.dumps(value, ensure_ascii=False)
            self.assertNotIn('"canonical_write_back": true', encoded)
        self.assertEqual(file_hash(SC1_FROZEN), "cc82c6738fcbf4fc14c12005a459048e71ce329492867d0910562fc6fdfda0d8")
        self.assertEqual(file_hash(SC1_CURRENT), "b916530264285dd7fa1d2e27a7a1dff8cd2ed794dfb3b84985881f8f209d8f6a")

    def test_protected_hash_witness_matches_worktree(self) -> None:
        witness = read_json(FROZEN_OUT / "protected-hashes.json", {})
        actual = protected_hashes()
        self.assertEqual(witness["files"], actual["files"])
        self.assertEqual(witness["trees"], actual["trees"])


if __name__ == "__main__":
    unittest.main()
