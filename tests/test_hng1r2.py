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
from hng1r_common import hash_tree  # noqa: E402
from hng1r2_common import GENERIC_ROLE_SURFACES, replay_identity  # noqa: E402


OUTPUT = ROOT / "data/generated/hng1r2"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class HNG1R2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.identity_doc = json.loads((OUTPUT / "identity-resolution.json").read_text(encoding="utf-8"))
        cls.rows = cls.identity_doc["resolutions"]

    def test_full_replay_uses_schema_consistent_catalog(self):
        manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["resolver_catalog"], "build_hng0_2.person_catalog")
        self.assertEqual(manifest["forms_index"], "build_hng0_2.forms_index")
        self.assertEqual(len(self.rows), 103)
        self.assertEqual(manifest["model_calls"], 0)
        self.assertEqual(manifest["api_calls"], 0)

    def test_existing_full_names_resolve_without_false_splits(self):
        expected = {
            hng02.lookup("王敦"): "person-011",
            hng02.lookup("王導"): "person-003",
            hng02.lookup("桓温"): "person-008",
            hng02.lookup("郗鑒"): "person-002",
            hng02.lookup("王戎"): "person-020",
            hng02.lookup("劉伶"): "person-047",
            hng02.lookup("蘇峻"): "person-017",
        }
        seen: set[str] = set()
        for row in self.rows:
            folded = hng02.lookup(row.get("surface"))
            if folded in expected:
                seen.add(folded)
                self.assertEqual(row["resolution_status"], "resolved_existing_person")
                self.assertEqual(row["resolved_person_id"], expected[folded])
        self.assertEqual(seen, set(expected))

    def test_kinship_surname_guard_prevents_wang_dun_false_merge(self):
        matches = [
            row for row in self.rows
            if row.get("surface") == "敦"
            and any("從父兄敦" in str(context.get("exact_quote") or "") for context in row.get("local_resolver_context", []))
        ]
        self.assertEqual(len(matches), 1)
        row = matches[0]
        self.assertNotEqual(row.get("resolved_person_id"), "person-011")
        self.assertEqual(row["resolution_method"], "kinship_context")
        self.assertEqual(row["resolved_label"], "卞敦")
        self.assertEqual(row["resolution_status"], "resolved_provisional_person")

    def test_kinship_guard_is_generic_not_person_specific(self):
        catalog = {
            "seed": {
                "person_id": "seed", "canonical_name": "甲丙", "surname": "甲",
                "forms": ["甲丙"], "canonical_forms": ["甲丙"],
                "courtesy_forms": [], "alias_forms": [], "office_titles": [],
            },
            "unrelated": {
                "person_id": "unrelated", "canonical_name": "乙丁", "surname": "乙",
                "forms": ["乙丁"], "canonical_forms": ["乙丁"],
                "courtesy_forms": [], "alias_forms": [], "office_titles": [],
            },
        }
        candidate = {
            "candidate_ids": ["candidate"],
            "person_a": "seed",
            "counterpart_surface": "丁",
            "relation_type": "cousin_clan_kin",
            "normalized_relation_type": "cousin_clan_kin",
            "evidence_refs": ["ref"],
            "evidence_quotes": [{"ref": "ref", "quote": "甲丙（從父兄丁）"}],
        }
        old = {
            "candidate_id": "candidate", "candidate_kind": "relation",
            "seed_person_id": "seed", "surface": "丁",
        }
        evidence = {"ref": {
            "source_work": "測試", "source_layer": "reference_text",
            "source_path": "fixture", "original_text": "==甲丙==\n甲丙（從父兄丁）",
            "model_snippet": "unrelated material", "locator": {},
        }}
        row = replay_identity(
            old_resolution=old,
            projected_candidate=candidate,
            evidence=evidence,
            catalog=catalog,
            exact_index=hng02.forms_index(catalog),
            neighborhoods={"seed": {"unrelated"}},
        )
        self.assertEqual(row["resolved_label"], "甲丁")
        self.assertEqual(row["resolution_status"], "resolved_provisional_person")
        self.assertIsNone(row["resolved_person_id"])

    def test_contextual_short_names_are_preserved_and_replayed(self):
        observed = {
            (row.get("surface"), row.get("resolved_label"))
            for row in self.rows
            if row.get("resolution_status") == "resolved_existing_person"
        }
        for pair in (("嶠", "温嶠"), ("濤", "山濤"), ("巨源", "山濤"), ("隗", "劉隗"), ("廙", "王廙")):
            self.assertIn(pair, observed)

    def test_generic_roles_remain_fail_closed(self):
        generic = {hng02.lookup(value) for value in GENERIC_ROLE_SURFACES}
        role_rows = [row for row in self.rows if hng02.lookup(row.get("surface")) in generic]
        self.assertTrue(role_rows)
        self.assertTrue(all(row.get("resolution_status") == "unresolved_identity" for row in role_rows))

    def test_audit_uses_exact_quote_and_local_source_context(self):
        audit = json.loads((OUTPUT / "audit-sample.json").read_text(encoding="utf-8"))
        self.assertIn("false_split", audit["allowed_review_values"])
        self.assertGreaterEqual(len(audit["items"]), 20)
        for row in audit["items"]:
            self.assertTrue(row["exact_quote"])
            self.assertTrue(row["local_resolver_context"])
            self.assertNotIn("model_snippet", row)
            self.assertEqual(row["review"], "not_reviewed")

    def test_rebuild_is_deterministic_and_protected_inputs_are_immutable(self):
        before_output = hash_tree(OUTPUT)
        before_hng1 = hash_tree(ROOT / "data/generated/hng1")
        before_hng1r = hash_tree(ROOT / "data/generated/hng1r")
        protected = [
            ROOT / "data/people.json",
            ROOT / "data/aliases.json",
            ROOT / "data/story-chain-gold-set.json",
            ROOT / "data/derived/person-story-links.json",
            ROOT / "data/derived/h0c-protection-manifest.json",
            ROOT / "data/derived/hg0-protection-manifest.json",
            ROOT / "data/derived/hr0-protection-manifest.json",
            ROOT / "data/derived/nl1-protection-manifest.json",
        ]
        before_protected = {path: digest(path) for path in protected}
        result = subprocess.run(
            [sys.executable, "scripts/build_hng1r2.py", "--quiet"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before_output, hash_tree(OUTPUT))
        self.assertEqual(before_hng1, hash_tree(ROOT / "data/generated/hng1"))
        self.assertEqual(before_hng1r, hash_tree(ROOT / "data/generated/hng1r"))
        self.assertEqual(before_protected, {path: digest(path) for path in protected})

    def test_validator_passes(self):
        result = subprocess.run(
            [sys.executable, "scripts/validate_hng1r2.py", "--mode", "portable"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
