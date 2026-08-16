from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from jsonschema import Draft202012Validator

from scripts.build_nl0_story_sketch import (
    CANDIDATES_PATH,
    GOLD_PATH,
    PUBLIC_MANIFEST_PATH,
    ROOT,
    SCHEMA_PATH,
    build_documents,
)
from scripts.validate_nl0 import validate


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class NL0StorySketchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gold = read_json(ROOT / GOLD_PATH)
        cls.candidates = read_json(ROOT / CANDIDATES_PATH)
        cls.schema = read_json(ROOT / SCHEMA_PATH)

    def test_validator_passes(self) -> None:
        self.assertEqual(validate(ROOT), [])

    def test_representative_reviewed_slice_is_seven_stories(self) -> None:
        expected = {
            "02-yanyu-035",
            "02-yanyu-036",
            "05-fangzheng-032",
            "06-yaliang-017",
            "09-pinzao-017",
            "19-xianyuan-026",
            "27-jiajue-008",
        }
        self.assertEqual(set(self.gold["scope"]["selected_story_ids"]), expected)
        self.assertEqual(len(self.gold["records"]), 7)
        self.assertTrue(all(row["review_status"] == "accepted" for row in self.gold["records"]))
        self.assertTrue(all(row["review_status"] == "reviewed" for row in self.candidates["records"]))
        self.assertTrue(all(row["review_decision"] == "accepted" for row in self.candidates["records"]))

    def test_claims_are_evidence_traceable_and_background_is_bounded(self) -> None:
        for record in self.gold["records"]:
            support = {row["evidence_id"] for row in record["supporting_evidence"]}
            claims = []
            if record["era_profile"]:
                claims.append(record["era_profile"])
            claims.append(record["scene_core"])
            claims.extend(record["essential_background"])
            if record["resonance"]:
                claims.append(record["resonance"])
            self.assertLessEqual(len(record["essential_background"]), 2)
            for claim in claims:
                self.assertTrue(claim["evidence_ids"])
                self.assertTrue(set(claim["evidence_ids"]).issubset(support))
        self.assertEqual(self.gold["counts"]["abstained_era_profiles"], 1)
        self.assertEqual(self.gold["counts"]["abstained_resonance"], 5)

    def test_schema_and_frontend_shards_are_isolated(self) -> None:
        self.assertEqual(list(Draft202012Validator(self.schema).iter_errors(self.gold)), [])
        self.assertEqual(list(Draft202012Validator(self.schema).iter_errors(self.candidates)), [])
        manifest = read_json(ROOT / PUBLIC_MANIFEST_PATH)
        self.assertNotIn("manifest.json", manifest["shards"])
        self.assertEqual(len(manifest["shards"]), 18)
        for path in (ROOT / "site/public/generated/nl0/story-sketch").glob("*.json"):
            payload = read_json(path)
            self.assertEqual(payload["projection"], "nl0_story_sketch")
            self.assertEqual(payload["review_status"], "accepted")
            self.assertNotIn("grounded_inputs", payload)
            self.assertNotIn("review_note", payload)

    def test_builder_is_deterministic(self) -> None:
        first = build_documents(ROOT)
        second = build_documents(ROOT)
        self.assertEqual(first, second)

        def snapshot() -> dict[str, str]:
            return {
                path.relative_to(ROOT / "site/public/generated/nl0").as_posix(): sha256(path)
                for path in (ROOT / "site/public/generated/nl0").rglob("*.json")
            }

        subprocess.run(["python3", "scripts/build_nl0_story_sketch.py"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        first_hashes = snapshot()
        subprocess.run(["python3", "scripts/build_nl0_story_sketch.py"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        second_hashes = snapshot()
        self.assertEqual(first_hashes, second_hashes)

    def test_frontend_uses_explicit_lazy_feature_flag(self) -> None:
        app = (ROOT / "site/src/App.tsx").read_text(encoding="utf-8")
        loader = (ROOT / "site/src/storySketch.ts").read_text(encoding="utf-8")
        self.assertIn("VITE_NL0_STORY_SKETCH", app)
        self.assertIn(">\n                Original\n", app)
        self.assertIn(">\n                Sketch\n", app)
        self.assertIn("loadStorySketch", app)
        self.assertIn("fetch(storySketchUrl", loader)
        self.assertIn("storySketchCache", loader)
        self.assertNotIn('import("./generated/nl0', loader)
        self.assertNotIn("fetchStorySketchOnMount", app)

    def test_canonical_sc1_bytes_are_untouched(self) -> None:
        bundle = ROOT / "site/src/generated/sc1-site.json"
        baseline = read_json(ROOT / "data/derived/ux1-frontend-size-baseline.json")
        self.assertEqual(sha256(bundle), baseline["sc1_site"]["sha256"])
        self.assertEqual(bundle.stat().st_size, baseline["sc1_site"]["bytes"])


if __name__ == "__main__":
    unittest.main()
