from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class LexicalAliasCollisionTests(unittest.TestCase):
    def test_望之_in_08_shangyu_079_is_lexical_and_not_person_029(self) -> None:
        rows = [
            item
            for item in read("data/derived/person-resolution-effective.json")["mentions"]
            if item.get("entry_id") == "08-shangyu-079" and item.get("surface") == "望之"
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("resolution_status"), "unresolved")
        self.assertIsNone(rows[0].get("resolution_target"))
        self.assertIsNone(rows[0].get("person_id"))

        audit_rows = [
            item
            for item in read("data/derived/person-resolution-lexical-collision-audit.json")["records"]
            if item.get("story_id") == "08-shangyu-079"
        ]
        self.assertEqual(len(audit_rows), 1)
        self.assertEqual(audit_rows[0].get("classification"), "lexical_verb_pronoun")
        self.assertIsNone(audit_rows[0].get("target_person_id"))

    def test_explicit_bian_wangzhi_remains_a_positive_identity_control(self) -> None:
        rows = [
            item
            for item in read("data/derived/person-resolution-effective.json")["mentions"]
            if item.get("surface") == "卞望之"
        ]
        self.assertTrue(rows)
        self.assertTrue(all(item.get("person_id") == "person-029" for item in rows))
        audit_rows = read("data/derived/person-resolution-lexical-collision-audit.json")["records"]
        self.assertTrue(
            any(
                item.get("classification") == "identity_name"
                and item.get("target_person_id") == "person-029"
                for item in audit_rows
            )
        )

    def test_望之_alias_remains_in_registry(self) -> None:
        aliases = read("data/aliases.json")["aliases"]
        self.assertTrue(
            any(
                item.get("surface") == "望之"
                and "person-029" in item.get("person_ids", [])
                for item in aliases
            )
        )

    def test_false_story_link_and_temporal_participation_are_removed(self) -> None:
        links = read("data/derived/person-story-links.json")["links"]
        self.assertFalse(
            any(item.get("person_id") == "person-029" and item.get("entry_id") == "08-shangyu-079" for item in links)
        )
        gap = next(
            item
            for item in read("data/derived/h0a-temporal-gap-audit.json")["records"]
            if item.get("story_id") == "08-shangyu-079"
        )
        self.assertNotIn("person-029", gap.get("people_involved", []))
        sc1_story = next(
            item
            for item in read("data/derived/sc1-site.json")["stories"]
            if item.get("id") == "08-shangyu-079"
        )
        self.assertNotIn("person-029", sc1_story.get("person_ids", []))
        lexical_mention_id = next(
            item["mention_id"]
            for item in read("data/derived/person-resolution-effective.json")["mentions"]
            if item.get("entry_id") == "08-shangyu-079" and item.get("surface") == "望之"
        )
        clickable_segments = [
            item
            for item in sc1_story["reading"]["main_text"]["segments"]
            if item.get("mention_id") == lexical_mention_id
        ]
        self.assertEqual(clickable_segments, [])


if __name__ == "__main__":
    unittest.main()
