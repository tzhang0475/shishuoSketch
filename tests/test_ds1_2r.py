from __future__ import annotations

import json
import unittest

from scripts.ds1_2_common import (
    ROOT,
    STORY_ID,
    EvidenceRecord,
    LocalEvidenceSearch,
    build_evidence_registry,
    build_minimal_story_input,
    validate_tool_call,
)
from scripts.ds1_2r_common import (
    CANDIDATE_PATH,
    DeduplicatingLocalEvidenceSearch,
    ensure_identity_conflict,
    known_identity_conflict,
    normalize_epistemic_statuses,
    protected_hashes,
    required_identity_conflict_present,
    validate_final_result_r,
)
from scripts.validate_ds1_2r import validate


class DS12RTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry, cls.source_hashes = build_evidence_registry(ROOT)
        cls.minimal = build_minimal_story_input(ROOT, STORY_ID)
        cls.target_ref = next(
            ref
            for ref, record in cls.registry.items()
            if record.source_layer == "base_text"
            and record.locator.get("entry_id") == STORY_ID
            and "士衡" in record.quote
        )

    def test_required_shiheng_identity_conflict_is_explicit_and_non_mutating(self) -> None:
        before = json.dumps(self.minimal, ensure_ascii=False, sort_keys=True)
        protected_before = protected_hashes(ROOT)
        conflict = known_identity_conflict(self.minimal, [self.target_ref], self.registry)
        self.assertIsNotNone(conflict)
        assert conflict is not None
        self.assertEqual(conflict["conflict_type"], "identity_resolution")
        self.assertEqual(conflict["existing_record"]["person_id"], "person-026")
        self.assertEqual(conflict["suggested_resolution"]["contextual_person_id"], "person-064")
        self.assertTrue(conflict["suggested_resolution"]["not_applied"])
        self.assertEqual(conflict["action"], "human_review_required")
        self.assertEqual(conflict["evidence_refs"], [self.target_ref])

        result = {
            "historical_preconditions": [],
            "participant_historical_states": [],
            "relationship_state_before_scene": [],
            "reader_needed_context": [],
            "context_to_text_links": [],
            "uncertainties": [],
            "data_conflicts": [],
        }
        hardened = ensure_identity_conflict(result, self.minimal, [self.target_ref], self.registry)
        self.assertTrue(required_identity_conflict_present(hardened))
        self.assertEqual(json.dumps(self.minimal, ensure_ascii=False, sort_keys=True), before)
        self.assertEqual(protected_hashes(ROOT), protected_before)
        self.assertEqual(CANDIDATE_PATH.as_posix(), "data/generated/ds1-2r/27-jiajue-008.json")

        malformed_model_result = dict(result)
        malformed_model_result["data_conflicts"] = [{
            "conflict_type": "identity_mapping_conflict",
            "existing_record": "士衡 → 陆机",
            "suggested_resolution": "陶士衡 → 陶侃",
            "reason": "model conflict",
            "evidence_refs": [self.target_ref],
            "confidence": "high",
            "action": "human_review_required",
        }]
        normalized = ensure_identity_conflict(
            malformed_model_result,
            self.minimal,
            [self.target_ref],
            self.registry,
        )
        self.assertEqual(len(normalized["data_conflicts"]), 1)
        self.assertTrue(required_identity_conflict_present(normalized))

    def test_evidence_metadata_is_preserved_in_search_hits(self) -> None:
        search = DeduplicatingLocalEvidenceSearch(self.registry)
        result = search.search("陶侃 庾亮", entity_hints=["陶侃"], top_k=5)
        self.assertGreater(result["result_count"], 0)
        self.assertTrue(
            all(
                {"source_layer", "locator", "evidence_ref", "quote"}.issubset(hit)
                for hit in result["hits"]
            )
        )
        self.assertTrue(any("review_status" in hit or "assertion_status" in hit for hit in result["hits"]))

    def test_not_materialized_is_separate_from_disputed_evidence(self) -> None:
        ref = next(
            ref
            for ref, record in self.registry.items()
            if record.review_status == "not_materialized" and (record.assertion_status or "").lower() == "explicit"
        )
        result = {
            "historical_preconditions": [
                {"text": "source-backed claim", "evidence_refs": [ref], "epistemic_status": "attested"}
            ],
            "participant_historical_states": [],
            "relationship_state_before_scene": [],
            "reader_needed_context": [],
            "context_to_text_links": [],
            "uncertainties": [],
            "data_conflicts": [],
        }
        normalized, adjustments = normalize_epistemic_statuses(result, self.registry)
        self.assertEqual(normalized["historical_preconditions"][0]["epistemic_status"], "attested")
        self.assertEqual(adjustments, [])
        self.assertEqual(validate_final_result_r(result, [ref], self.registry), [])

        disputed_ref = next(
            ref
            for ref, record in self.registry.items()
            if (record.assertion_status or "").lower() == "disputed"
        )
        disputed_result = dict(result)
        disputed_result["historical_preconditions"] = [
            {"text": "disputed source claim", "evidence_refs": [disputed_ref], "epistemic_status": "attested"}
        ]
        conflicted, conflict_adjustments = normalize_epistemic_statuses(disputed_result, self.registry)
        self.assertEqual(conflicted["historical_preconditions"][0]["epistemic_status"], "conflicted")
        self.assertTrue(conflict_adjustments)
        self.assertTrue(validate_final_result_r(disputed_result, [disputed_ref], self.registry))
        self.assertEqual(validate_final_result_r(conflicted, [disputed_ref], self.registry), [])

    def test_duplicate_passages_keep_best_stable_result(self) -> None:
        records = {
            "evidence-z": EvidenceRecord(
                evidence_ref="evidence-z",
                source="local witness",
                source_layer="base_text",
                locator={"entry_id": STORY_ID, "block_index": 2},
                quote="陶侃 庾亮",
                searchable_text="陶侃 庾亮",
                source_path="data/evidence/wp1-evidence.json",
            ),
            "evidence-a": EvidenceRecord(
                evidence_ref="evidence-a",
                source="local witness",
                source_layer="base_text",
                locator={"entry_id": STORY_ID, "block_index": 2},
                quote="陶侃 庾亮",
                searchable_text="陶侃 庾亮",
                source_path="data/evidence/wp1-evidence.json",
            ),
        }
        result = DeduplicatingLocalEvidenceSearch(records).search("陶侃", top_k=5)
        self.assertEqual(result["raw_match_count"], 2)
        self.assertEqual(result["deduplicated_match_count"], 1)
        self.assertEqual(result["duplicate_match_count"], 1)
        self.assertEqual([hit["evidence_ref"] for hit in result["hits"]], ["evidence-a"])

    def test_open_safety_and_tool_limits_remain_enforced(self) -> None:
        session = LocalEvidenceSearch(self.registry)
        with self.assertRaises(ValueError):
            session.open(self.target_ref)
        with self.assertRaises(ValueError):
            validate_tool_call("search_local_evidence", {"query": "陶侃", "top_k": 6})
        with self.assertRaises(ValueError):
            validate_tool_call("read_file", {"path": "data/generated/ds1-2/27-jiajue-008.json"})

    def test_validator_has_no_generated_source_boundary(self) -> None:
        self.assertEqual(validate(ROOT), [])
        for record in self.registry.values():
            self.assertNotIn("data/generated", record.source_path)
            self.assertNotIn("data/annotation", record.source_path)


if __name__ == "__main__":
    unittest.main()
