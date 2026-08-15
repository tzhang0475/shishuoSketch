from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from scripts.story_scene_contexts import DERIVED_PATH, SOURCE_PATH, derive_age_range, project, validate_source
from scripts.validate_sc1_frontend_data import validate
from tests.support import repository_validation_mode


ROOT = Path(__file__).resolve().parents[1]


class StorySceneContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = json.loads((ROOT / SOURCE_PATH).read_text(encoding="utf-8"))
        cls.derived = json.loads((ROOT / DERIVED_PATH).read_text(encoding="utf-8"))
        cls.bundle = json.loads((ROOT / "data/derived/sc1-site.json").read_text(encoding="utf-8"))

    def test_pilot_selection_is_evidence_bounded_and_includes_mandatory_story(self) -> None:
        ids = [record["story_id"] for record in self.source["records"]]
        self.assertGreaterEqual(len(ids), 20)
        self.assertLessEqual(len(ids), 30)
        self.assertIn("06-yaliang-029", ids)
        self.assertEqual(ids[0], "06-yaliang-029")

    def test_scene_card_does_not_expose_internal_relation_model_disclaimer(self) -> None:
        source_text = json.dumps(self.source, ensure_ascii=False)
        bundle_text = (ROOT / "data/derived/sc1-site.json").read_text(encoding="utf-8")
        for phrase in (
            "不新增长期人物关系",
            "不新增人物关系",
            "不據這段送別文字推定",
            "正文中被談及而未列入當前參與者的身份，仍留在本則的畫外。",
            "正文中被谈及而未列入当前参与者的身份，仍留在本则的画外。",
        ):
            self.assertNotIn(phrase, source_text)
            self.assertNotIn(phrase, bundle_text)

    def test_off_frame_people_render_without_generic_ontology_explanation(self) -> None:
        w3_source = json.loads(
            (ROOT / "data/annotation/story-scene-contexts-w3.json").read_text(encoding="utf-8")
        )
        w3_story_ids = {record["story_id"] for record in w3_source["records"]}
        context = next(
            context
            for story_id, context in self.derived["contexts"].items()
            if story_id in w3_story_ids
            and any(person["scene_role"] != "present" for person in context["people_at_scene"])
        )
        self.assertTrue(context["people_at_scene"])
        self.assertFalse(context["narrative_layers"]["off_frame_context"])
        self.assertTrue(any(person["scene_role"] != "present" for person in context["people_at_scene"]))

    def test_scene_contexts_resolve_only_published_stories_and_people(self) -> None:
        self.assertEqual(validate_source(ROOT), [])
        story_ids = {story["id"] for story in self.bundle["stories"]}
        people_ids = {person["id"] for person in self.bundle["people"]}
        self.assertTrue(set(self.derived["contexts"]).issubset(story_ids))
        for context in self.derived["contexts"].values():
            for person in context["people_at_scene"]:
                self.assertIn(person["person_id"], people_ids)
            self.assertEqual(context["review_status"], "candidate")

    def test_scene_claims_are_evidence_backed_and_ages_are_explicitly_unknown(self) -> None:
        evidence_ids = {item["id"] for item in self.bundle["evidence"]}
        for context in self.derived["contexts"].values():
            for evidence_id in context["evidence_ids"]:
                self.assertIn(evidence_id, evidence_ids)
            for person in context["people_at_scene"]:
                self.assertEqual(person["age"]["status"], "unknown")
                self.assertIsNone(person["age"]["start_year"])
                self.assertIsNone(person["age"]["end_year"])
                for evidence_id in person["evidence_ids"]:
                    self.assertIn(evidence_id, evidence_ids)
            for claim in context["event_background"]:
                self.assertTrue(claim["evidence_ids"])

    def test_ink_wash_layers_and_yaliang_017_resonance_are_evidence_backed(self) -> None:
        context = self.derived["contexts"]["06-yaliang-017"]
        self.assertEqual(
            set(context["narrative_layers"]),
            {"scene_focus", "off_frame_context", "historical_ground", "resonance"},
        )
        self.assertTrue(context["narrative_layers"]["scene_focus"])
        self.assertTrue(context["narrative_layers"]["off_frame_context"])
        resonance = context["narrative_layers"]["resonance"]
        self.assertTrue(any("十九" in item["text"]["original"] for item in resonance))
        self.assertTrue(any("遇害" in item["text"]["original"] for item in resonance))
        for layer in context["narrative_layers"].values():
            for claim in layer:
                self.assertTrue(claim["evidence_ids"])
                self.assertEqual(claim["review_status"], "candidate")

    def test_reader_labels_use_ink_wash_vocabulary(self) -> None:
        labels = self.bundle["ui"]
        self.assertEqual(labels["scene_heading"]["original"], "舞臺")
        self.assertEqual(labels["scene_focus_heading"]["original"], "舞臺")
        self.assertEqual(labels["scene_people_heading"]["original"], "入畫")
        self.assertEqual(labels["scene_position_heading"]["original"], "舞臺")
        self.assertEqual(labels["scene_off_frame_heading"]["original"], "畫外")
        self.assertEqual(labels["scene_ground_heading"]["original"], "底色")
        self.assertEqual(labels["scene_resonance_heading"]["original"], "餘韻")
        self.assertEqual(labels["person_sketch_life_glimpse"]["original"], "一瞥")
        app = (ROOT / "site/src/App.tsx").read_text(encoding="utf-8")
        for phrase in ("这一幕里", "背景提及", "人物一瞥"):
            self.assertNotIn(phrase, app)

    def test_age_derivation_preserves_exact_and_range_uncertainty(self) -> None:
        self.assertEqual(
            derive_age_range(372, 372, 320, 320),
            {"status": "exact", "start_year": 52, "end_year": 52},
        )
        self.assertEqual(
            derive_age_range(371, 372, 320, 322),
            {"status": "range", "start_year": 49, "end_year": 52},
        )
        self.assertEqual(
            derive_age_range(None, None, 320, 320),
            {"status": "unknown", "start_year": None, "end_year": None},
        )

    def test_mandatory_story_preserves_unmaterialized_wang_tanzhi(self) -> None:
        context = self.derived["contexts"]["06-yaliang-029"]
        self.assertEqual([person["person_id"] for person in context["people_at_scene"]], ["person-008", "person-006"])
        self.assertEqual(
            [person["surface"]["original"] for person in context["unmaterialized_people"]],
            ["王坦之"],
        )
        self.assertEqual(context["places"][0]["name"]["original"], "新亭")
        self.assertTrue(any("簡文帝" in claim["text"]["original"] for claim in context["event_background"]))

    def test_scene_context_does_not_change_relation_layer(self) -> None:
        production = json.loads((ROOT / "data/annotation/wp1-relations.json").read_text(encoding="utf-8"))
        self.assertEqual(self.bundle["relations"], production["records"])
        for context in self.source["records"]:
            self.assertNotIn("relation_ids", context)

    def test_scene_records_remain_story_owned_and_do_not_project_relations(self) -> None:
        w3_source = json.loads(
            (ROOT / "data/annotation/story-scene-contexts-w3.json").read_text(encoding="utf-8")
        )
        expected_context_ids = {
            record["story_id"] for record in self.source["records"]
        } | {
            record["story_id"] for record in w3_source["records"]
        }
        self.assertEqual(set(self.derived["contexts"]), expected_context_ids)
        self.assertGreaterEqual(len(self.source["records"]), 20)
        self.assertGreaterEqual(len(w3_source["records"]), 20)
        self.assertTrue({"02-yanyu-069", "04-wenxue-036", "05-fangzheng-055", "06-yaliang-027", "08-shangyu-077", "19-xianyuan-026", "02-yanyu-035", "05-fangzheng-032", "11-jiewu-005", "27-jiajue-008"} <= set(self.derived["contexts"]))
        self.assertIn("02-yanyu-036", self.derived["contexts"])
        self.assertFalse(any("relations" in context or "relation_ids" in context for context in self.derived["contexts"].values()))

    def test_s2_selected_stories_have_a_story_local_stage_claim(self) -> None:
        selected = json.loads((ROOT / "data/annotation/s2-narrative-density-selection.json").read_text(encoding="utf-8"))
        for record in selected["records"]:
            context = self.derived["contexts"][record["story_id"]]
            self.assertTrue(context["narrative_layers"]["scene_focus"], record["story_id"])

    def test_fangzheng_031_political_prose_is_scene_focus_not_people_heading(self) -> None:
        context = self.derived["contexts"]["05-fangzheng-031"]
        self.assertTrue(context["narrative_layers"]["scene_focus"])
        self.assertEqual([person["person_id"] for person in context["people_at_scene"]], ["person-019", "person-011"])
        self.assertEqual(context["people_at_scene"][1]["scene_role"], "referenced_in_context")

    def test_sc1_validation_includes_scene_projection_in_repository_mode(self) -> None:
        mode = repository_validation_mode()
        self.assertEqual(validate(ROOT, mode=mode), [])
        if mode == "full":
            self.assertEqual(validate(ROOT, mode="portable"), [])

    def test_scene_projection_is_byte_stable(self) -> None:
        evidence_ids = {item["id"] for item in self.bundle["evidence"]}
        stories = {story["id"] for story in self.bundle["stories"] if story["publication_state"] != "blocked"}
        first = project(self.source, story_ids=stories, people=self.bundle["people"], evidence_ids=evidence_ids)
        second = project(self.source, story_ids=stories, people=self.bundle["people"], evidence_ids=evidence_ids)
        self.assertEqual(first, second)
        self.assertEqual(
            hashlib.sha256(json.dumps(first, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
            hashlib.sha256(json.dumps(second, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
