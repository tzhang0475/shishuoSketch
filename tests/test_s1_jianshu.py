from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from scripts.s1_jianshu_common import discover_payloads, primary_witness_snapshot
from tests.support import skip_if_portable_payload_missing


ROOT = Path(__file__).resolve().parents[1]


def read_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class S1JianshuIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registration = read_json("data/derived/s1-jianshu-source-registration.json")
        cls.structure = read_json("data/derived/s1-jianshu-structure-audit.json")
        cls.alignment = read_json("data/derived/s1-jianshu-story-alignment.json")
        cls.backlog = read_json("data/derived/s1-jianshu-backlog-reresolution.json")
        cls.gate = read_json("data/derived/s1-jianshu-punctuation-gate-audit.json")
        cls.readiness = read_json("data/derived/s1-jianshu-candidate-punctuation-readiness.json")

    def test_local_source_registration_contract(self):
        payloads = self.registration["payloads"]
        self.assertEqual({row["source_id"] for row in payloads}, {
            "shishuo-jianshu-yujiaxi-local-epub",
            "shishuo-jianshu-yujiaxi-local-pdf",
        })
        self.assertEqual({row["role"] for row in payloads}, {"scholarly-reference-machine", "scholarly-reference-visual"})
        self.assertEqual({row["source_family"] for row in payloads}, {"shishuo-jianshu-yujiaxi-local"})
        tracked = subprocess.run(["git", "ls-files", "sources/downloads/shishuo"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        self.assertNotIn(".epub", tracked)
        self.assertNotIn(".pdf", tracked)

    def test_local_source_payload_discovery_and_hashes(self):
        payloads = self.registration["payloads"]
        paths = [row["local_path"] for row in payloads]
        skip_if_portable_payload_missing(self, ROOT, *paths)
        discovered = discover_payloads()
        self.assertEqual(set(discovered), {"epub", "pdf"})
        self.assertEqual(discovered["epub"].suffix, ".epub")
        self.assertEqual(discovered["pdf"].suffix, ".pdf")
        by_format = {row["format"]: row for row in payloads}
        for kind, path in discovered.items():
            record = by_format[kind]
            self.assertEqual(path.relative_to(ROOT).as_posix(), record["local_path"])
            self.assertEqual(path.stat().st_size, record["byte_size"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record["sha256"])

    def test_epub_structure_covers_all_categories_and_story_entries(self):
        self.assertEqual(self.structure["chapters_detected"], 36)
        self.assertEqual(self.structure["chapter_count_expected"], 36)
        self.assertEqual(self.structure["story_entries_detected"], 1130)
        self.assertGreater(self.structure["block_counts"]["liu_annotation"], 0)
        self.assertGreater(self.structure["block_counts"]["collation_note"], 0)
        self.assertGreater(self.structure["block_counts"]["jianshu_note"], 0)
        self.assertTrue(self.structure["appendices_detected"])

    def test_structured_cache_retains_concrete_editorial_layers(self):
        cache = ROOT / ".cache/shishuo-reference/jianshu/story-records.jsonl"
        skip_if_portable_payload_missing(self, ROOT, ".cache/shishuo-reference/jianshu/story-records.jsonl")
        records = [json.loads(line) for line in cache.read_text(encoding="utf-8").splitlines()]

        note_only = next(
            row for row in records
            if any(block.get("block_type") == "jianshu_note" for block in row["blocks"])
            and not any(block.get("block_type") == "collation_note" for block in row["blocks"])
        )
        collated = next(
            row for row in records
            if any(block.get("block_type") == "collation_note" for block in row["blocks"])
            and any(block.get("block_type") == "jianshu_note" for block in row["blocks"])
        )
        jiaxi = next(
            row for row in records
            if any("嘉錫案" in str(block.get("text", "")) for block in row["blocks"])
        )
        self.assertTrue(any(block.get("block_type") == "jianshu_note" for block in note_only["blocks"]))
        self.assertTrue(any(block.get("block_type") == "collation_note" for block in collated["blocks"]))
        self.assertTrue(any(block.get("attribution") == "余嘉錫" for block in jiaxi["blocks"]))
        self.assertNotEqual(note_only["story_key"], collated["story_key"])

    def test_alignment_is_production_plus_frozen_x1_1_only(self):
        self.assertEqual(len(self.alignment["records"]), 163)
        self.assertFalse(self.alignment["scope"]["new_story_selection_performed"])
        selected = {row["story_id"] for row in read_json("data/derived/x1-1-selection-manifest.json")["records"]}
        aligned_selected = {row["story_id"] for row in self.alignment["records"] if row["scope"] == "x1_1_frozen_selection"}
        self.assertEqual(aligned_selected, selected)
        self.assertTrue(all(row["selection_provenance"]["selection_epoch"] == "X1.1" for row in self.alignment["records"] if row["selection_provenance"]))

    def test_jian_shu_policy_clears_only_editorial_gate(self):
        self.assertEqual(self.gate["classification"]["result"], "intentional_two_tier_policy_resolved_by_s1_source_policy")
        self.assertEqual(self.backlog["counts"]["stories_total"], 20)
        self.assertEqual(self.backlog["counts"]["stories_punctuation_accepted"], 20)
        self.assertEqual(self.backlog["counts"]["stories_production_eligible"], 0)
        self.assertEqual(self.backlog["counts"]["stories_materialized"], 0)
        self.assertTrue(all("participant_review_not_evaluated" in row["blocking_reasons"] for row in self.backlog["stories"]))

    def test_backlog_is_complete_and_unresolved_facts_do_not_leak(self):
        self.assertEqual(self.backlog["counts"]["facts_total"], 58)
        self.assertEqual(self.backlog["counts"]["facts_accepted"], 0)
        self.assertEqual(self.backlog["counts"]["facts_unresolved"], 58)
        self.assertEqual(self.backlog["counts"]["identities_total"], 3)
        self.assertEqual(self.backlog["counts"]["identities_unresolved"], 3)
        materialization = read_json("data/derived/s1-jianshu-materialization-manifest.json")
        for key in ("canonical_story_additions", "canonical_person_additions", "canonical_fact_additions", "canonical_entity_additions"):
            self.assertEqual(materialization[key], [])

    def test_prospective_candidate_readiness_is_separate_from_publication(self):
        self.assertEqual(self.readiness["counts"]["candidate_records"], 417)
        self.assertEqual(self.readiness["counts"]["production_punctuation_ready_under_s1"], 417)
        self.assertTrue(all("participant" in row["policy_note"] or "publication" in row["policy_note"] for row in self.readiness["records"]))

    def test_modality_and_source_layers_are_retained(self):
        aliases = read_json("data/derived/s1-jianshu-alias-candidates.json")
        self.assertIn("existing_mapping", aliases["counts"])
        self.assertIn("ambiguous", aliases["counts"])
        self.assertTrue(all(row["review_required"] for row in aliases["records"]))
        assertions = read_json("data/derived/s1-jianshu-historical-assertions.json")
        layers = {row["layer"] for row in assertions["records"]}
        modalities = {row["modality"] for row in assertions["records"]}
        self.assertTrue({"liu_annotation", "collation_note", "jianshu_note"} <= layers)
        self.assertTrue({"explicit", "probable", "possible", "disputed", "unknown"} <= modalities)
        self.assertTrue(all(row["candidate_status"] == "candidate" for row in assertions["records"]))
        citations = read_json("data/derived/s1-jianshu-source-citations.json")
        self.assertGreater(citations["counts"]["total"], 0)
        self.assertTrue(all(row["review_status"] == "candidate" for row in citations["records"]))

    def test_x1_2a_and_x1_2p_are_protected(self):
        protected = self.registration["protected_input_hashes"]
        for path, digest in protected.items():
            actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            self.assertEqual(actual, digest, path)
        self.assertTrue(self.backlog["existing_x1_2a_extension"]["preserved_without_mutation"])
        self.assertTrue(self.registration["primary_shishuo_witness_unchanged"])

    def test_primary_witness_lock_contract_is_committed(self):
        lock_path = ROOT / "sources/registry/shishuo-provenance.lock.json"
        lock = read_json("sources/registry/shishuo-provenance.lock.json")
        witness = self.registration["primary_shishuo_witness"]
        self.assertEqual(witness["witness_id"], lock["witness_id"])
        self.assertEqual(witness["lock_path"], "sources/registry/shishuo-provenance.lock.json")
        self.assertEqual(witness["lock_sha256"], hashlib.sha256(lock_path.read_bytes()).hexdigest())
        expected_files = [
            {
                "path": row["path"],
                "expected_size": row["size"],
                "expected_sha256": row["sha256"],
            }
            for row in lock["files"]
        ]
        actual_files = [
            {
                "path": row["path"],
                "expected_size": row["expected_size"],
                "expected_sha256": row["expected_sha256"],
            }
            for row in witness["files"]
        ]
        self.assertEqual(actual_files, expected_files)

    def test_live_primary_witness_snapshot_matches_lock(self):
        lock = read_json("sources/registry/shishuo-provenance.lock.json")
        skip_if_portable_payload_missing(self, ROOT, *(row["path"] for row in lock["files"]))
        self.assertEqual(self.registration["primary_shishuo_witness"], primary_witness_snapshot())


if __name__ == "__main__":
    unittest.main()
