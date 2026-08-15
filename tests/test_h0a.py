from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_json(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class H0ATemporalBackboneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = read_json("data/derived/sc1-site.json")
        cls.coordinates = read_json("data/derived/h0a-temporal-coordinates.json")
        cls.evidence = read_json("data/annotation/story-temporal-evidence-h0a.json")
        cls.events = read_json("data/annotation/historical-events-h0a.json")
        cls.anchors = read_json("data/annotation/story-temporal-anchors-h0a.json")
        cls.gap = read_json("data/derived/h0a-temporal-gap-audit.json")

    def test_exactly_one_anchor_for_current_published_story_set(self) -> None:
        story_ids = {story["id"] for story in self.bundle["stories"]}
        anchors = self.anchors["records"]
        self.assertEqual({item["story_id"] for item in anchors}, story_ids)
        self.assertEqual(len(anchors), len(story_ids))

    def test_unknown_is_legal_and_has_no_reader_label(self) -> None:
        anchors = {item["story_id"]: item for item in self.anchors["records"]}
        for story_id, anchor in anchors.items():
            if anchor["precision"] == "unknown":
                self.assertFalse(anchor["reader_projection"]["show"], story_id)
                story = next(item for item in self.bundle["stories"] if item["id"] == story_id)
                self.assertNotIn("temporal_orientation", story)

    def test_gold_temporal_direction_cases(self) -> None:
        anchors = {item["story_id"]: item for item in self.anchors["records"]}
        evidence = self.evidence["records"]

        fangzheng = anchors["05-fangzheng-031"]
        self.assertEqual(fangzheng["precision"], "event_bounded")
        self.assertIn("event-wang-dun-rebellion", fangzheng["event_ids"])

        yaliang = anchors["06-yaliang-017"]
        self.assertNotEqual(yaliang["precision"], "exact_year")
        later = [
            item for item in evidence
            if item["story_id"] == "06-yaliang-017" and item["relation_to_story"] == "later_outcome"
        ]
        self.assertTrue(any(item["raw_surface"] == "咸和" or "咸和" in item["raw_surface"] for item in later))

        self.assertEqual(anchors["05-fangzheng-055"]["precision"], "unknown")
        self.assertEqual(anchors["01-dexing-026"]["precision"], "unknown")

    def test_w3_phase_regressions(self) -> None:
        anchors = {item["story_id"]: item for item in self.anchors["records"]}
        self.assertEqual(anchors["01-dexing-012"]["phase_id"], "phase-1")
        self.assertEqual(anchors["01-dexing-015"]["phase_id"], "phase-3")
        self.assertEqual(anchors["01-dexing-025"]["phase_id"], "phase-4")
        self.assertEqual({item["phase_id"] for item in self.coordinates["phases"]}, {f"phase-{n}" for n in range(1, 6)})

    def test_later_outcome_and_background_do_not_promote_exact_dates(self) -> None:
        anchors = {item["story_id"]: item for item in self.anchors["records"]}
        evidence = self.evidence["records"]
        for story_id in ("06-yaliang-017", "01-dexing-026"):
            relevant = [item for item in evidence if item["story_id"] == story_id]
            self.assertTrue(any(item["relation_to_story"] in {"later_outcome", "earlier_background"} for item in relevant))
            self.assertNotEqual(anchors[story_id]["precision"], "exact_year")

    def test_event_records_do_not_mutate_relations(self) -> None:
        relation_ids = {item["id"] for item in self.bundle["relations"]}
        production_relation_ids = {item["id"] for item in read_json("data/annotation/wp1-relations.json")["records"]}
        self.assertEqual(relation_ids, production_relation_ids)
        self.assertTrue(all("production_relation_id" not in item for item in self.events["records"]))

    def test_ztj_and_sgz_source_layers_remain_distinct(self) -> None:
        ztj = read_json("data/derived/ztj0-processed-corpus.json")
        sgz = read_json("data/derived/sgz0-processed-corpus.json")
        self.assertEqual(ztj["primary"]["volume_count"], 294)
        self.assertGreater(ztj["primary"]["hu_annotation_unit_count"], 0)
        self.assertGreater(sgz["main_text_unit_count"], 0)
        self.assertGreater(sgz["pei_annotation_unit_count"], 0)
        self.assertNotEqual(ztj["primary_machine_witness"], sgz["primary_witness"])

    def test_no_false_identity_hotfix_regressions_are_reintroduced(self) -> None:
        mentions = self.bundle["mentions"]
        self.assertFalse(
            any(
                mention.get("story_id") == "01-dexing-026"
                and mention.get("surface") == "少孤"
                and mention.get("person_id") == "person-032"
                for mention in mentions
            )
        )
        self.assertFalse(
            any(
                mention.get("story_id") in {"05-fangzheng-055", "23-rendan-033", "23-rendan-042", "23-rendan-049", "26-qingdi-020"}
                and mention.get("surface") in {"桓子", "桓子野", "桓子野家", "桓子野每聞清歌", "桓子野善吹笛"}
                and mention.get("person_id") == "person-016"
                for mention in mentions
            )
        )

    def test_zhongrong_correction_does_not_seed_stone_bao_temporal_activity(self) -> None:
        story = next(item for item in self.bundle["stories"] if item["id"] == "23-rendan-013")
        self.assertNotIn("person-037", story.get("person_ids", []))
        activity = read_json("data/annotation/person-activity-anchors-h0a.json")["records"]
        self.assertFalse(
            any(
                item.get("story_id") == "23-rendan-013" and item.get("person_id") == "person-037"
                for item in activity
            )
        )


if __name__ == "__main__":
    unittest.main()
