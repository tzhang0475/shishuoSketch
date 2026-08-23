from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hng0_1_common import (  # noqa: E402
    build_search_profiles,
    find_passages,
    open_passages,
    quote_matches,
    resolve_counterpart,
)
from run_hng0_1 import merge_relations, validate_and_project_response  # noqa: E402


class HNG01Tests(unittest.TestCase):
    def test_frozen_scope_and_profile_determinism(self):
        first = build_search_profiles(ROOT)
        second = build_search_profiles(ROOT)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 24)
        self.assertTrue(all(row["one_hop_only"] for row in first.values()))
        self.assertTrue(all("search_terms_original" in row and "search_terms_normalized" in row for row in first.values()))

    def test_find_open_is_source_layered_and_not_sentence_based(self):
        units = [
            {
                "source_ref": "u1",
                "work": "晉書",
                "source_layer": "primary_text",
                "text": "甲與乙友善。這是一個不依賴句號的原文窗口",
                "normalized_search_text": "甲與乙友善。這是一個不依賴句號的原文窗口",
                "source_path": "content/processed/jinshu/unit.md",
                "locator": {"unit_id": "u1"},
            }
        ]
        result = find_passages({"person_id": "p0", "canonical_name": "甲", "search_terms_original": ["甲與乙"]}, units, top_k=3)
        opened = open_passages(result, {"u1": units[0]}, max_passages=1, window_chars=12)
        self.assertEqual(result["hits"][0]["source_ref"], "u1")
        self.assertEqual(len(opened), 1)
        self.assertIn("甲", opened[0]["snippet"])
        self.assertIn("u1", opened[0]["source_ref"])

    def test_quote_validation_only_allows_safe_boundary_normalization(self):
        self.assertTrue(quote_matches("正文：甲與乙。", "甲與乙"))
        self.assertTrue(quote_matches("正文：甲 與乙。", "甲與乙"))
        self.assertTrue(quote_matches("正文：『甲與乙』。", "『甲與乙』"))
        self.assertFalse(quote_matches("正文：甲與丙。", "甲與乙"))

    def test_entity_resolution_is_deterministic_and_ambiguous_is_preserved(self):
        catalog = {
            "p1": {"canonical_name": "陶侃", "courtesy_name": ["士衡"], "aliases": [], "office_titles": []},
            "p2": {"canonical_name": "陸機", "courtesy_name": ["士衡"], "aliases": [], "office_titles": []},
        }
        ambiguous = resolve_counterpart("士衡", catalog)
        self.assertEqual(ambiguous["resolution_status"], "ambiguous_identity")
        resolved = resolve_counterpart("陶侃", catalog)
        self.assertEqual(resolved["resolution_status"], "resolved_existing_person")
        unresolved = resolve_counterpart("未登记人物", catalog)
        self.assertEqual(unresolved["resolution_status"], "unresolved_identity")

    def test_claim_level_evidence_validation_and_cooccurrence_rejection(self):
        opened = [{
            "source_ref": "ref-1",
            "work": "晉書",
            "source_layer": "primary_text",
            "locator": {"unit_id": "u1"},
            "snippet": "甲與乙友善。",
        }]
        catalog = {
            "p0": {"canonical_name": "甲", "courtesy_name": [], "aliases": [], "office_titles": []},
            "p1": {"canonical_name": "乙", "courtesy_name": [], "aliases": [], "office_titles": []},
        }
        response = {
            "relation_candidates": [
                {"seed_person_id": "p0", "counterpart_surface": "乙", "relation_type": "explicit_friendship_association", "direction": "undirected", "claim": "甲与乙友善", "evidence_ref": "ref-1", "exact_quote": "甲與乙友善。", "confidence": "medium"},
                {"seed_person_id": "p0", "counterpart_surface": "乙", "relation_type": "explicit_friendship_association", "direction": "undirected", "claim": "仅同现", "evidence_ref": "ref-1", "exact_quote": "甲與乙友善。", "basis": "cooccurrence"},
                {"seed_person_id": "p0", "counterpart_surface": "乙", "relation_type": "explicit_friendship_association", "direction": "undirected", "claim": "错误引文", "evidence_ref": "ref-1", "exact_quote": "甲與丙。"},
            ],
            "temporal_candidates": [],
        }
        projected = validate_and_project_response(seed_id="p0", response_doc=response, opened=opened, catalog=catalog, seed_ids={"p0"}, temporal_by_person={})
        self.assertEqual(len(projected["relations"]), 1)
        reasons = {item["reason"] for item in projected["rejected"]}
        self.assertIn("cooccurrence_only", reasons)
        self.assertIn("exact_quote_not_in_opened_passage", reasons)

    def test_relation_deduplication_merges_evidence_without_new_edge(self):
        rows = [
            {"person_a": "p0", "person_b": "p1", "relation_type": "marriage", "direction": {"kind": "undirected"}, "claim": "一", "evidence_refs": ["r1"], "evidence_quotes": [{"ref": "r1", "quote": "甲妻乙"}], "source_works": ["晉書"]},
            {"person_a": "p0", "person_b": "p1", "relation_type": "marriage", "direction": {"kind": "undirected"}, "claim": "二", "evidence_refs": ["r2"], "evidence_quotes": [{"ref": "r2", "quote": "甲娶乙"}], "source_works": ["世說新語"]},
        ]
        merged = merge_relations(rows)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["evidence_refs"], ["r1", "r2"])
        self.assertIn("conflicts", merged[0])

    def test_generated_unavailable_projection_is_candidate_only(self):
        result = subprocess.run(["python3", "scripts/validate_hng0_1.py"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((ROOT / "data/generated/hng0-1/manifest.json").read_text(encoding="utf-8"))
        self.assertFalse(manifest["canonical_write_back"])
        self.assertTrue(manifest["one_hop_only"])
        if manifest["execution_kind"] == "live_model_unavailable":
            candidates = json.loads((ROOT / "data/generated/hng0-1/candidate-relations.json").read_text(encoding="utf-8"))
            self.assertEqual(candidates["relations"], [])


if __name__ == "__main__":
    unittest.main()
