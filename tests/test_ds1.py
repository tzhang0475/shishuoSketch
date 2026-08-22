from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.ds1_common import (
    CONTEXT_PATH,
    ROOT,
    STORY_ID,
    build_context_bundle,
    validate_scene_context,
)
from scripts.validate_ds1 import validate


class DS1Tests(unittest.TestCase):
    def test_context_bundle_is_story_scoped_and_deterministic(self) -> None:
        first = build_context_bundle(ROOT, STORY_ID)
        second = build_context_bundle(ROOT, STORY_ID)
        self.assertEqual(first, second)
        self.assertEqual(first["story_id"], STORY_ID)
        self.assertIn("陶公自上流來赴蘇峻之難", first["story"]["original"])
        self.assertGreaterEqual(len(first["evidence_bundle_ids"]), 5)
        self.assertTrue(first["jianshu_evidence"])
        self.assertTrue(first["reviewed_facts"])

    def test_all_context_references_resolve(self) -> None:
        context = json.loads((ROOT / CONTEXT_PATH).read_text(encoding="utf-8"))
        evidence_ids = set(context["evidence_bundle_ids"])
        self.assertEqual(evidence_ids, set(context["evidence_index"]))
        for field in ("participants", "episodes", "person_states", "temporal_relations", "uncertainties"):
            for row in context[field]:
                self.assertTrue(set(row["evidence_refs"]).issubset(evidence_ids), (field, row))

    def test_model_contract_requires_traceable_claims(self) -> None:
        context = json.loads((ROOT / CONTEXT_PATH).read_text(encoding="utf-8"))
        evidence_ref = context["evidence_bundle_ids"][0]
        evidence_ids = context["evidence_bundle_ids"]
        valid = {
            "scene_summary": {"text": "现场行动受到事件背景约束。", "evidence_refs": [evidence_ref]},
            "participant_states": [{"person_id": "person-064", "surface": "陶公", "state": "行动者", "evidence_refs": [evidence_ref]}],
            "relationship_context": [],
            "reader_needed_context": [],
            "uncertainties": [{"text": None, "evidence_refs": []}],
        }
        self.assertEqual(validate_scene_context(valid, evidence_ids), [])
        invalid = dict(valid)
        invalid["scene_summary"] = {"text": "无来源的补充", "evidence_refs": []}
        self.assertTrue(validate_scene_context(invalid, evidence_ids))

    def test_validator_passes_without_an_api_call(self) -> None:
        self.assertEqual(validate(ROOT), [])

    def test_frontend_exposes_only_optional_reviewed_preview(self) -> None:
        loader = (ROOT / "site/src/ds1.ts").read_text(encoding="utf-8")
        app = (ROOT / "site/src/App.tsx").read_text(encoding="utf-8")
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertIn("fetch(ds1PreviewUrl", loader)
        self.assertIn("ds1PreviewCache", loader)
        self.assertIn('value.story_id !== "27-jiajue-008"', app)
        self.assertIn("loadDs1Preview", app)
        self.assertIn("build_ds1_preview.py", package["scripts"]["build:site"])
        self.assertNotIn("data/generated/ds1", app)


if __name__ == "__main__":
    unittest.main()
