from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / "data/derived/sc1-site.json"


def read_bundle() -> dict:
    return json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))


def reading_segments(story: dict) -> list[dict]:
    layers = [story["reading"]["main_text"], *story["reading"]["annotations"]]
    return [segment for layer in layers for segment in layer.get("segments", [])]


class D11RuntimeDisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = read_bundle()
        cls.display = cls.bundle["display"]

    def test_shared_registry_covers_global_entities(self) -> None:
        self.assertEqual(set(self.display["people"]), {item["id"] for item in self.bundle["people"]})
        self.assertEqual(set(self.display["relations"]), {item["id"] for item in self.bundle["relations"]})
        self.assertEqual(set(self.display["sources"]), {item["id"] for item in self.bundle["sources"]})
        self.assertEqual(set(self.display["evidence"]), {item["id"] for item in self.bundle["evidence"]})
        self.assertTrue(self.display["labels"])

    def test_stories_do_not_retain_global_display_maps(self) -> None:
        repeated = {"labels", "person_display", "relation_display", "source_display", "evidence_display"}
        for story in self.bundle["stories"]:
            self.assertTrue(repeated.isdisjoint(story["reading"]))
            self.assertIn("mention_display", story["reading"])

    def test_reader_surfaces_and_ruler_target_are_unchanged(self) -> None:
        examples = {
            "温太真": ("05-fangzheng-032", "person-013"),
            "明帝": ("05-fangzheng-032", "ruler-jin-mingdi"),
            "王右軍": ("05-fangzheng-025", None),
            "右軍": ("14-rongzhi-024", "person-001"),
        }
        for surface, (story_id, target_id) in examples.items():
            story = next(item for item in self.bundle["stories"] if item["id"] == story_id)
            matches = [segment for segment in reading_segments(story) if segment.get("display", {}).get("original") == surface]
            self.assertTrue(matches, surface)
            if target_id is not None:
                target_fields = {matches[0].get("person_id"), matches[0].get("ruler_id")}
                self.assertIn(target_id, target_fields)

    def test_evidence_used_by_story_person_and_relation_views_is_shared(self) -> None:
        story_evidence = {
            evidence_id
            for story in self.bundle["stories"]
            for evidence_id in story.get("evidence_ids", [])
        }
        sketch_evidence = {
            evidence_id
            for sketch in self.bundle["person_sketches"].values()
            for evidence_id in sketch.get("identity", {}).get("evidence_ids", [])
        }
        relation_evidence = {
            evidence_id
            for relation in self.bundle["relations"]
            for evidence_id in relation.get("evidence_ids", [])
        }
        for evidence_id in story_evidence | sketch_evidence | relation_evidence:
            self.assertIn(evidence_id, self.display["evidence"])

    def test_story_person_relation_story_ids_remain_navigable(self) -> None:
        people = {item["id"] for item in self.bundle["people"]}
        stories = {item["id"] for item in self.bundle["stories"]}
        relations = {
            item["id"]: item
            for item in self.bundle["relations"]
            if item.get("review_status") == "reviewed"
        }
        chain = self.bundle["story_chain"]
        person_story = {
            item["person_id"]: set(item["story_ids"])
            for item in chain["person_story_refs"]
        }
        for relation in relations.values():
            self.assertIn(relation["subject_id"], people)
            self.assertIn(relation["object_id"], people)
            self.assertTrue(person_story.get(relation["subject_id"], set()) <= stories)
            self.assertTrue(person_story.get(relation["object_id"], set()) <= stories)

    def test_semantic_equivalence_validator_passes(self) -> None:
        result = subprocess.run(
            ["python3", "scripts/validate_d1_1.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_semantic_baseline_is_committed_and_history_independent(self) -> None:
        baseline = json.loads(
            (ROOT / "data/derived/d1-0-semantic-baseline.json").read_text(encoding="utf-8")
        )
        self.assertEqual(baseline["schema"], 1)
        self.assertEqual(set(baseline["display_tables"]), {
            "labels", "people", "relations", "sources", "evidence"
        })
        validator = (ROOT / "scripts/validate_d1_1.py").read_text(encoding="utf-8")
        self.assertNotIn("git show", validator)


if __name__ == "__main__":
    unittest.main()
