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
from hng1r_common import (  # noqa: E402
    CONTEXTUAL_SHORT_RESOLVER_VERSION,
    GENERIC_ROLE_SURFACES,
    hash_tree,
    resolve_contextual_short_name,
)


class HNG1RTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {
            "person-w": {
                "person_id": "person-w",
                "canonical_name": "温嶠",
                "canonical_forms": ["温嶠"],
                "forms": ["温嶠"],
                "courtesy_forms": [],
                "alias_forms": [],
                "office_titles": [],
            },
            "person-h": {
                "person_id": "person-h",
                "canonical_name": "和嶠",
                "canonical_forms": ["和嶠"],
                "forms": ["和嶠"],
                "courtesy_forms": [],
                "alias_forms": [],
                "office_titles": [],
            },
            "person-s": {
                "person_id": "person-s",
                "canonical_name": "山濤",
                "canonical_forms": ["山濤"],
                "forms": ["山濤"],
                "courtesy_forms": [],
                "alias_forms": [],
                "office_titles": [],
            },
        }

    def _resolve(self, surface: str, source: str, *, locator=None):
        evidence = {"r": {
            "source_work": "晉書",
            "source_layer": "primary_text",
            "source_path": "content/processed/test.md",
            "locator": locator or {},
            "original_text": source,
            "model_snippet": source,
        }}
        candidate = {
            "person_a": "seed",
            "counterpart_surface": surface,
            "evidence_refs": ["r"],
            "evidence_quotes": [{"ref": "r", "quote": surface + "見於此"}],
            "claim": surface + "見於此",
            "temporal_warnings": [],
        }
        old = {
            "candidate_id": "candidate-1",
            "surface": surface,
            "seed_person_id": "seed",
            "resolution_status": "unresolved_identity",
            "resolution_method": "unresolved",
            "supporting_evidence_refs": ["r"],
            "matches": [],
        }
        return resolve_contextual_short_name(
            old_resolution=old,
            candidate=candidate,
            evidence=evidence,
            catalog=self.catalog,
            neighborhoods={},
        )

    def test_contextual_short_name_resolves_generic_suffix_with_heading(self):
        row = self._resolve("嶠", "==溫嶠==\n嶠見於此")
        self.assertEqual(row["resolution_method"], "contextual_short_name")
        self.assertEqual(row["resolved_person_id"], "person-w")
        self.assertEqual(row["normalized_person_surface"], "温嶠")
        self.assertEqual(row["candidate_set"], ["person-h", "person-w"])

    def test_tied_context_fails_closed_as_ambiguous(self):
        row = self._resolve("嶠", "温嶠與和嶠，嶠見於此")
        self.assertEqual(row["resolution_status"], "ambiguous_identity")
        self.assertIsNone(row["resolved_person_id"])

    def test_generic_role_surface_remains_unresolved(self):
        self.catalog["person-c"] = {
            "person_id": "person-c", "canonical_name": "某客",
            "canonical_forms": ["某客"], "forms": ["某客"],
        }
        row = self._resolve("客", "==某客==\n客見於此")
        self.assertIn("客", GENERIC_ROLE_SURFACES)
        self.assertEqual(row["resolution_status"], "unresolved_identity")
        self.assertNotEqual(row.get("resolution_method"), "contextual_short_name")

    def test_no_person_specific_mapping_is_needed(self):
        self.catalog = {
            "p": {
                "person_id": "p", "canonical_name": "甲嶠",
                "canonical_forms": ["甲嶠"], "forms": ["甲嶠"],
            }
        }
        row = self._resolve("嶠", "==甲嶠==\n嶠見於此")
        self.assertEqual(row["resolved_person_id"], "p")
        self.assertEqual(row["resolution_method"], "contextual_short_name")

    def test_actual_projection_targets_and_manifest(self):
        output = ROOT / "data/generated/hng1r"
        self.assertTrue((output / "manifest.json").is_file())
        identities = json.loads((output / "identity-resolution.json").read_text(encoding="utf-8"))["resolutions"]
        contextual = {(row.get("surface"), row.get("resolved_label")) for row in identities if row.get("resolution_method") == "contextual_short_name"}
        self.assertIn(("嶠", "温嶠"), contextual)
        self.assertIn(("濤", "山濤"), contextual)
        self.assertIn(("隗", "劉隗"), contextual)
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["resolver_version"], CONTEXTUAL_SHORT_RESOLVER_VERSION)
        self.assertEqual(manifest["model_calls"], 0)
        self.assertEqual(manifest["hng1_artifact_hashes"], hash_tree(ROOT / "data/generated/hng1"))

    def test_offline_rebuild_is_deterministic_and_hng1_unchanged(self):
        output = ROOT / "data/generated/hng1r"
        before = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(output.glob("*.json"))}
        hng1_before = hash_tree(ROOT / "data/generated/hng1")
        result = subprocess.run([sys.executable, "scripts/build_hng1r.py", "--quiet"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        after = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(output.glob("*.json"))}
        self.assertEqual(before, after)
        self.assertEqual(hng1_before, hash_tree(ROOT / "data/generated/hng1"))

    def test_validator_passes(self):
        result = subprocess.run([sys.executable, "scripts/validate_hng1r.py", "--mode", "portable"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
