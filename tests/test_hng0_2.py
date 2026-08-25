from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_hng0_2 as hng02  # noqa: E402
from tests.support import skip_if_portable_payload_missing  # noqa: E402


class HNG02Tests(unittest.TestCase):
    def test_frozen_inputs_and_generated_counts(self):
        manifest = json.loads((ROOT / "data/generated/hng0-2/manifest.json").read_text(encoding="utf-8"))
        metrics = json.loads((ROOT / "data/generated/hng0-2/metrics.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["one_hop_only"])
        self.assertFalse(manifest["canonical_write_back"])
        self.assertEqual(len(manifest["seed_person_ids"]), 24)
        self.assertEqual(metrics["input_relation_candidates"], 160)
        self.assertEqual(metrics["input_temporal_candidates"], 83)
        self.assertEqual(metrics["unresolved_provisional_neighbor_count_before"], 117)
        self.assertEqual(metrics["model_calls"], 0)

    def test_contextual_tao_shiheng_resolution_does_not_change_global_alias(self):
        catalog = {
            "person-026": {"person_id": "person-026", "canonical_name": "陸機", "forms": ["陸機", "士衡"], "surname": "陸"},
            "person-064": {"person_id": "person-064", "canonical_name": "陶侃", "forms": ["陶侃"], "surname": "陶"},
        }
        exact = {"士衡": ["person-026"], "陸機": ["person-026"], "陶侃": ["person-064"]}
        candidate = {"evidence_quotes": [{"quote": "陶士衡"}]}
        resolved = hng02.resolve_identity(
            surface="士衡",
            seed={"canonical_name": "庾亮"},
            candidate=candidate,
            context="陶士衡至庾亮門",
            evidence_records=[{"evidence_ref": "r1"}],
            catalog=catalog,
            exact_index=exact,
        )
        self.assertEqual(resolved["resolved_person_id"], "person-064")
        self.assertEqual(resolved["resolution_method"], "biography_local_context")
        self.assertEqual(exact["士衡"], ["person-026"])

    def test_resolution_method_preserves_catalogue_basis(self):
        person = {
            "canonical_forms": ["陸機"],
            "courtesy_forms": ["士衡"],
            "alias_forms": ["平原"],
            "office_titles": ["陸太傅"],
        }
        self.assertEqual(hng02.exact_resolution_method(person, "陸機"), "exact_name")
        self.assertEqual(hng02.exact_resolution_method(person, "士衡"), "courtesy_name")
        self.assertEqual(hng02.exact_resolution_method(person, "平原"), "alias")
        self.assertEqual(hng02.exact_resolution_method(person, "陸太傅"), "title")

    def test_ambiguous_surface_is_preserved(self):
        catalog = {
            "p1": {"person_id": "p1", "canonical_name": "陶侃", "forms": ["陶侃", "士衡"], "surname": "陶"},
            "p2": {"person_id": "p2", "canonical_name": "陸機", "forms": ["陸機", "士衡"], "surname": "陸"},
        }
        resolved = hng02.resolve_identity(
            surface="士衡",
            seed={"canonical_name": "庾亮"},
            candidate={"evidence_quotes": [{"quote": "士衡"}]},
            context="士衡",
            evidence_records=[],
            catalog=catalog,
            exact_index={"士衡": ["p1", "p2"]},
        )
        self.assertEqual(resolved["resolution_status"], "ambiguous_identity")
        self.assertEqual(resolved["resolution_method"], "ambiguous")

    def test_relation_levels_and_kinship_repair(self):
        rows = json.loads((ROOT / "data/generated/hng0-2/normalized-relations.json").read_text(encoding="utf-8"))["relations"]
        self.assertEqual(sum(row["relation_type"] == "grandparent_grandchild" for row in rows), 4)
        self.assertFalse(any(row["relation_type"] == "same_clan" and "祖" in row.get("claim", "") for row in rows))
        self.assertTrue(any(row["semantic_level"] == "documented_interaction" and row["original_relation_type"] == "explicit_political_cooperation_opposition" for row in rows))
        self.assertTrue(all(row["review_status"] == "candidate" for row in rows))

    def test_punctuated_windows_are_small_and_comparison_is_offline(self):
        comparison = json.loads((ROOT / "data/generated/hng0-2/retrieval-comparison.json").read_text(encoding="utf-8"))
        punctuated = comparison["modes"]["punctuated_first"]
        self.assertLessEqual(punctuated["average_open_chars"], 520)
        self.assertEqual(punctuated["elapsed_seconds"], 0.0)
        self.assertEqual(comparison["model_calls"], 0)
        self.assertGreater(comparison["delta"]["open_chars_reduction_percent"], 0)

    def test_validator_passes_without_model_or_network(self):
        result = subprocess.run([sys.executable, "scripts/validate_hng0_2.py", "--mode", "portable"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rebuild_is_byte_identical(self):
        skip_if_portable_payload_missing(
            self,
            ROOT,
            "sources/downloads/jinshu/wikisource-punctuated/text/volume-001.wikitext",
        )
        output_paths = sorted((ROOT / "data/generated/hng0-2").glob("*.json")) + [ROOT / "data/annotation/hng0-2-review.json", ROOT / "site/src/generated/hng0-2-site.json"]
        before = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in output_paths}
        result = subprocess.run([sys.executable, "scripts/build_hng0_2.py", "--quiet"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        after = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in output_paths}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
