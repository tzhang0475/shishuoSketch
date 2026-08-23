from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_hng0_2 as hng02  # noqa: E402
from hng1_common import build_fresh_profiles, build_hng1_selection, find_punctuated_first, open_short_hits  # noqa: E402
from run_hng1 import project_response  # noqa: E402


class HNG1Tests(unittest.TestCase):
    def test_fresh_selection_is_deterministic_and_excludes_hng0(self):
        first = build_hng1_selection()
        second = build_hng1_selection()
        self.assertEqual(first, second)
        self.assertEqual(first["selected_seed_count"], 36)
        selected = {row["person_id"] for row in first["people"]}
        hng0 = {row["person_id"] for row in json.loads((ROOT / "data/generated/hng0/hng0-selection.json").read_text())["people"]}
        self.assertFalse(selected & hng0)
        self.assertEqual({row["stratum"] for row in first["people"]}, {"high_connectivity", "medium_connectivity", "low_connectivity"})
        self.assertTrue(all(row["one_hop_only"] if "one_hop_only" in row else True for row in [first]))

    def test_fresh_profiles_do_not_import_hng0_story_research(self):
        selection = build_hng1_selection()
        profiles = build_fresh_profiles(selection)
        self.assertEqual(set(profiles), {row["person_id"] for row in selection["people"]})
        self.assertTrue(all(profile["seed"] and profile["one_hop_only"] for profile in profiles.values()))
        self.assertTrue(all("stories" not in profile and "relations" not in profile for profile in profiles.values()))

    def test_punctuated_first_retrieval_and_short_open(self):
        profile = {"person_id": "seed", "canonical_name": "甲", "search_terms_original": ["甲乙"], "search_terms_normalized": ["甲乙"]}
        punctuated = [{"source_ref": "p1", "work": "晉書", "source_layer": "primary_text", "text": "甲乙友善。其後各行。", "source_form": "punctuated", "locator": {"unit_id": "p1"}, "source_path": "content/processed/p.md"}]
        legacy = [{"source_ref": "l1", "work": "晉書", "source_layer": "primary_text", "text": "甲乙。舊文。", "source_form": "legacy_local", "locator": {"unit_id": "l1"}, "source_path": "content/processed/l.md"}]
        found = find_punctuated_first(profile, punctuated, legacy, top_k=1)
        opened = open_short_hits(found, punctuated, legacy, max_passages=1)
        self.assertEqual(found["hits"][0]["source_form"], "punctuated")
        self.assertEqual(opened[0]["source_ref"], "p1")
        self.assertLessEqual(opened[0]["snippet_chars"], 520)

    def test_claim_level_evidence_rejection_keeps_valid_claim(self):
        opened = [{
            "source_ref": "r1", "work": "晉書", "source_layer": "primary_text", "source_form": "punctuated",
            "snippet": "甲與乙友善。", "original_text": "甲與乙友善。", "source_path": "content/processed/p.md",
        }]
        profiles = {"seed": {"person_id": "seed", "canonical_name": "甲"}}
        catalog = {
            "seed": {"person_id": "seed", "canonical_name": "甲", "canonical_forms": ["甲"], "forms": ["甲"], "surname": "甲"},
            "person-b": {"person_id": "person-b", "canonical_name": "乙", "canonical_forms": ["乙"], "forms": ["乙"], "surname": "乙"},
        }
        result = project_response(
            seed_id="seed",
            profiles=profiles,
            catalog=catalog,
            opened=opened,
            response_doc={
                "relation_candidates": [
                    {"seed_person_id": "seed", "counterpart_surface": "乙", "relation_type": "explicit_friendship_association", "direction": "undirected", "claim": "有效", "evidence_ref": "r1", "exact_quote": "甲與乙友善。"},
                    {"seed_person_id": "seed", "counterpart_surface": "乙", "relation_type": "explicit_friendship_association", "direction": "undirected", "claim": "无效", "evidence_ref": "r1", "exact_quote": "甲與丙。"},
                ],
                "temporal_candidates": [],
            },
        )
        self.assertEqual(len(result["relations"]), 1)
        self.assertTrue(any(item["reason"] == "exact_quote_not_in_opened_passage" for item in result["rejected"]))

    def test_model_cannot_assign_person_id(self):
        opened = [{"source_ref": "r1", "work": "晉書", "source_layer": "primary_text", "source_form": "punctuated", "snippet": "甲與乙友善。", "original_text": "甲與乙友善。", "source_path": "content/processed/p.md"}]
        result = project_response(
            seed_id="seed",
            profiles={"seed": {"person_id": "seed", "canonical_name": "甲"}},
            catalog={"seed": {"person_id": "seed", "canonical_name": "甲", "canonical_forms": ["甲"], "forms": ["甲"], "surname": "甲"}},
            opened=opened,
            response_doc={"relation_candidates": [{"seed_person_id": "seed", "person_id": "person-b", "counterpart_surface": "乙", "relation_type": "shared_explicit_event", "claim": "x", "evidence_ref": "r1", "exact_quote": "甲與乙友善。"}], "temporal_candidates": []},
        )
        self.assertEqual(result["relations"], [])
        self.assertEqual(result["rejected"][0]["reason"], "model_assigned_person_id")


if __name__ == "__main__":
    unittest.main()
