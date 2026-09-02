from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from scripts.build_sc1_frontend_data import _output_path
from scripts.sc1_paths import (
    CURRENT_SC1_DERIVED_PATH,
    CURRENT_SC1_VITE_PATH,
    FROZEN_SC1_DERIVED_PATH,
    FROZEN_SC1_MANIFEST_PATH,
    FROZEN_SC1_SHA256,
    FROZEN_SC1_VITE_PATH,
)
from scripts.validate_sc1_frozen import validate as validate_frozen
from scripts.validate_sc1_frontend_data import SC1_PATH, VITE_PATH


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SC1MContractTests(unittest.TestCase):
    def test_frozen_v1_integrity_is_explicit_and_stable(self) -> None:
        self.assertEqual(validate_frozen(ROOT), [])
        manifest = json.loads((ROOT / FROZEN_SC1_MANIFEST_PATH).read_text(encoding="utf-8"))
        self.assertEqual(manifest["logical_name"], "FROZEN_SC1_V1")
        self.assertEqual(sha256(ROOT / FROZEN_SC1_DERIVED_PATH), FROZEN_SC1_SHA256)
        self.assertEqual(sha256(ROOT / FROZEN_SC1_VITE_PATH), FROZEN_SC1_SHA256)

    def test_current_projection_has_distinct_named_views(self) -> None:
        current_derived = ROOT / CURRENT_SC1_DERIVED_PATH
        current_vite = ROOT / CURRENT_SC1_VITE_PATH
        self.assertTrue(current_derived.is_file())
        self.assertTrue(current_vite.is_file())
        self.assertEqual(current_derived.read_bytes(), current_vite.read_bytes())
        self.assertNotEqual(sha256(current_derived), FROZEN_SC1_SHA256)

    def test_current_builder_rejects_frozen_write_targets(self) -> None:
        with self.assertRaises(ValueError):
            _output_path(ROOT, ROOT / FROZEN_SC1_DERIVED_PATH)
        with self.assertRaises(ValueError):
            _output_path(ROOT, ROOT / FROZEN_SC1_VITE_PATH)

    def test_current_validator_uses_current_projection(self) -> None:
        self.assertEqual(SC1_PATH, ROOT / CURRENT_SC1_DERIVED_PATH)
        self.assertEqual(VITE_PATH, ROOT / CURRENT_SC1_VITE_PATH)

    def test_frontend_loader_uses_current_projection(self) -> None:
        source = (ROOT / "site/src/data.ts").read_text(encoding="utf-8")
        self.assertIn('./generated/sc1-current-site.json"', source)
        self.assertNotIn('./generated/sc1-site.json"', source)

    def test_delta_reports_explained_semantic_changes(self) -> None:
        delta = json.loads(
            (ROOT / "data/derived/sc1m-v1-to-current-delta.json").read_text(encoding="utf-8")
        )
        self.assertEqual(delta["classification"], "SEMANTIC_CHANGE")
        self.assertEqual(delta["frozen"]["sha256"], FROZEN_SC1_SHA256)
        self.assertEqual(delta["summary"]["semantic_changed_record_count"], 13)
        self.assertEqual(delta["summary"]["serialization_order_only_difference_count"], 0)
        self.assertEqual(delta["unexplained_material_differences"], [])
        self.assertTrue(delta["authority_traceability"])
        self.assertEqual(
            {section["path"] for section in delta["semantic_differences"]},
            {"people", "display.people"},
        )

    def test_pages_build_and_frozen_validation_are_separate(self) -> None:
        workflow = (ROOT / ".github/workflows/deploy-pages.yml").read_text(encoding="utf-8")
        self.assertIn("build_sc1_frontend_data.py --target current", workflow)
        self.assertIn("scripts/validate_sc1_frozen.py", workflow)
        self.assertNotIn("build_sc1_frontend_data.py --target frozen", workflow)


if __name__ == "__main__":
    unittest.main()
