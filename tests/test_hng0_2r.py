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


class HNG02RTests(unittest.TestCase):
    def test_generic_decorated_suffix_examples(self):
        catalog = {
            "person-009": {"person_id": "person-009", "canonical_name": "劉惔", "canonical_forms": ["劉惔"], "forms": ["劉惔"], "surname": "劉"},
            "person-006": {"person_id": "person-006", "canonical_name": "謝安", "canonical_forms": ["謝安"], "forms": ["謝安"], "surname": "謝"},
            "person-076": {"person_id": "person-076", "canonical_name": "王彪之", "canonical_forms": ["王彪之"], "forms": ["王彪之"], "surname": "王"},
        }
        exact = {"劉惔": ["person-009"], "謝安": ["person-006"], "王彪之": ["person-076"]}
        for surface, pid, decorator, kind in (
            ("沛國劉惔", "person-009", "沛國", "geographic"),
            ("陳郡謝安", "person-006", "陳郡", "geographic"),
            ("尚書令王彪之", "person-076", "尚書令", "office"),
            ("太傅謝安", "person-006", "太傅", "office"),
        ):
            quote = f"{surface}見於此。"
            row = hng02.resolve_identity(
                surface=surface,
                seed={"canonical_name": "王導"},
                candidate={"claim": quote, "evidence_quotes": [{"ref": "r", "quote": quote}]},
                context=quote,
                evidence_records=[{"evidence_ref": "r", "original_text": quote}],
                catalog=catalog,
                exact_index=exact,
                allow_decorated=True,
            )
            self.assertEqual(row["resolution_status"], "resolved_existing_person")
            self.assertEqual(row["resolved_person_id"], pid)
            self.assertEqual(row["resolution_method"], "decorated_name_suffix")
            self.assertEqual(row["decorator_surface"], decorator)
            self.assertEqual(row["decorator_type"], kind)

    def test_ambiguous_longest_suffix_fails_closed(self):
        catalog = {
            "p1": {"person_id": "p1", "canonical_name": "謝安", "canonical_forms": ["謝安"], "forms": ["謝安"], "surname": "謝"},
            "p2": {"person_id": "p2", "canonical_name": "謝安", "canonical_forms": ["謝安"], "forms": ["謝安"], "surname": "謝"},
        }
        quote = "陳郡謝安見於此。"
        row = hng02.resolve_identity(
            surface="陳郡謝安",
            seed={"canonical_name": "王導"},
            candidate={"claim": quote, "evidence_quotes": [{"ref": "r", "quote": quote}]},
            context=quote,
            evidence_records=[{"evidence_ref": "r", "original_text": quote}],
            catalog=catalog,
            exact_index={"謝安": ["p1", "p2"]},
            allow_decorated=True,
        )
        self.assertEqual(row["resolution_status"], "ambiguous_identity")
        self.assertIsNone(row.get("resolved_person_id"))

    def test_hng_only_surface_remains_provisional(self):
        catalog = {
            "p1": {"person_id": "p1", "canonical_name": "王導", "canonical_forms": ["王導"], "forms": ["王導"], "surname": "王"},
        }
        row = hng02.resolve_identity(
            surface="未登記人物",
            seed={"canonical_name": "王導"},
            candidate={"claim": "未登記人物有事", "evidence_quotes": [{"ref": "r", "quote": "未登記人物有事"}]},
            context="未登記人物有事",
            evidence_records=[{"evidence_ref": "r", "original_text": "未登記人物有事"}],
            catalog=catalog,
            exact_index={"王導": ["p1"]},
            allow_decorated=True,
        )
        self.assertEqual(row["resolution_status"], "resolved_provisional_person")
        self.assertNotEqual(row["resolution_method"], "decorated_name_suffix")
        self.assertTrue(str(row["provisional_person_id"]).startswith("hng02-provisional-"))

    def test_hng02r_validator_and_baseline_hashes(self):
        result = subprocess.run([sys.executable, "scripts/validate_hng0_2r.py", "--mode", "portable"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((ROOT / "data/generated/hng0-2r/manifest.json").read_text(encoding="utf-8"))
        for rel, expected in manifest["hng02_baseline_artifact_hashes"].items():
            self.assertEqual(hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), expected)

    def test_hng02r_rebuild_is_byte_identical(self):
        output_paths = sorted((ROOT / "data/generated/hng0-2r").glob("*.json")) + [ROOT / "data/annotation/hng0-2r-review.json"]
        before = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in output_paths}
        result = subprocess.run([sys.executable, "scripts/build_hng0_2r.py", "--quiet"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        after = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in output_paths}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
