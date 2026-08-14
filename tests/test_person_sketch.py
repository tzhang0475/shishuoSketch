from __future__ import annotations

import json
from pathlib import Path
import unittest

from opencc import OpenCC

from scripts.validate_person_sketch import validate_bundle, validate_source
from tests.support import repository_validation_mode
from scripts.validate_sc1_frontend_data import validate


ROOT = Path(__file__).resolve().parents[1]


class PersonSketchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = json.loads((ROOT / "data/derived/sc1-site.json").read_text(encoding="utf-8"))
        cls.source = json.loads((ROOT / "data/annotation/person-sketches.json").read_text(encoding="utf-8"))
        cls.people = json.loads((ROOT / "data/people.json").read_text(encoding="utf-8"))["people"]
        cls.person_story_index = json.loads((ROOT / "data/derived/person-story-index.json").read_text(encoding="utf-8"))
        cls.app = (ROOT / "site/src/App.tsx").read_text(encoding="utf-8")

    def test_source_and_bundle_have_one_sketch_per_scoped_person(self) -> None:
        expected = [item["person_id"] for item in self.people]
        self.assertEqual(self.source["person_scope"], expected)
        self.assertEqual([item["person_id"] for item in self.source["records"]], expected)
        self.assertEqual(set(self.bundle["person_sketches"]), set(expected))
        self.assertEqual(validate_source(ROOT), [])
        self.assertEqual(validate_bundle(ROOT), [])

    def test_wang_xizhi_aliases_are_structured_and_ordered(self) -> None:
        sketch = self.bundle["person_sketches"]["person-001"]
        self.assertGreaterEqual(len(sketch["aliases"]), 4)
        self.assertEqual(
            [item["surface"]["original"] for item in sketch["aliases"][:4]],
            ["王羲之", "逸少", "王逸少", "王右軍"],
        )
        self.assertTrue(all("semantic_status" in item and "label" in item for item in sketch["aliases"]))
        self.assertFalse("、" in sketch["identity"]["canonical_name"]["original"])

    def test_contextual_aliases_are_not_projected_as_exact(self) -> None:
        for person_id in ("person-006", "person-002", "person-001"):
            rows = self.bundle["person_sketches"][person_id]["aliases"]
            for alias in rows:
                if alias["alias_type"] in {"office_title", "contextual_title", "textual_shorthand"}:
                    self.assertIn(alias["semantic_status"], {"contextual", "ambiguous"})
                    self.assertNotEqual(alias["semantic_label"]["original"], "明确称谓")

    def test_intro_is_short_and_evidenced(self) -> None:
        evidence_ids = {item["id"] for item in self.bundle["evidence"]}
        for sketch in self.bundle["person_sketches"].values():
            intro = sketch["identity"]["brief_intro"]
            if intro is not None:
                self.assertLessEqual(len(intro["original"]), 120)
                self.assertTrue(sketch["identity"]["evidence_ids"])
            self.assertTrue(set(sketch["identity"]["evidence_ids"]).issubset(evidence_ids))

    def test_original_and_simplified_profile_fields_share_semantic_rows(self) -> None:
        converter = OpenCC("t2s")
        for sketch in self.bundle["person_sketches"].values():
            identity = sketch["identity"]
            for key in ("canonical_name", "courtesy_name", "clan", "brief_intro"):
                value = identity[key]
                if value is not None:
                    self.assertEqual(value["simplified"], converter.convert(value["original"]))
            for alias in sketch["aliases"]:
                self.assertEqual(alias["surface"]["simplified"], converter.convert(alias["surface"]["original"]))
                self.assertEqual(alias["label"]["simplified"], converter.convert(alias["label"]["original"]))
                self.assertEqual(len(alias["mention_ids"]), len(set(alias["mention_ids"])))

    def test_story_counts_project_person_story_index(self) -> None:
        expected = {item["person_id"]: item for item in self.person_story_index["persons"]}
        for person_id, sketch in self.bundle["person_sketches"].items():
            refs = expected[person_id]["story_refs"]
            main = sum("main_text" in item["source_layers"] for item in refs)
            annotation_only = sum(
                "main_text" not in item["source_layers"] and "liu_annotation" in item["source_layers"]
                for item in refs
            )
            ready = sum(bool(item["reader_ready"]) for item in refs)
            self.assertEqual(sketch["story_counts"], {
                "total": len(refs),
                "main_text": main,
                "liu_annotation_only": annotation_only,
                "reader_ready": ready,
            })

    def test_sketch_does_not_redefine_relations_or_story_links(self) -> None:
        for sketch in self.source["records"]:
            self.assertFalse({"relations", "relation_ids", "story_ids", "person_story_ids"}.intersection(sketch))
        self.assertIn("PersonStories", self.app)
        self.assertIn("directRelationPerspectives", self.app)

    def test_route_context_and_relation_navigation_remain_distinct(self) -> None:
        self.assertIn("MentionOriginExplanation", self.app)
        self.assertIn("routeNode={focusedPersonNode}", self.app)
        self.assertIn("onClick={() => onFocus(perspective.neighbor.id)}", self.app)
        self.assertIn("via_mention_id", self.app)

    def test_full_sc1_validation_uses_existing_project_mode(self) -> None:
        self.assertEqual(validate(ROOT, mode=repository_validation_mode()), [])


if __name__ == "__main__":
    unittest.main()
