from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.migrate_person_ids import migrate
from scripts.validate_person_ids import validate


ROOT = Path(__file__).resolve().parents[1]


def read_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class PersonIdCanonicalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = read_json("data/migrations/person-id-canonicalization-v1.json")
        cls.people = read_json("data/people.json")["people"]

    def test_registry_is_exactly_opaque_person_sequence(self) -> None:
        self.assertEqual(
            [person["person_id"] for person in self.people],
            [f"person-{index:03d}" for index in range(1, 36)],
        )
        self.assertEqual(self.manifest["next_person_sequence"], 18)
        allocation = read_json("data/derived/person-id-allocation-state.json")
        self.assertEqual(allocation["next_person_sequence"], 36)

    def test_manifest_is_bijective_and_identity_preserving(self) -> None:
        records = self.manifest["records"]
        self.assertEqual(len(records), 17)
        self.assertEqual(len({record["old_person_id"] for record in records}), 17)
        self.assertEqual(len({record["new_person_id"] for record in records}), 17)
        by_id = {person["person_id"]: person for person in self.people}
        for record in records:
            self.assertEqual(by_id[record["new_person_id"]]["canonical_name"], record["canonical_name"])

    def test_supporting_person_and_wave_order_are_frozen(self) -> None:
        by_name = {person["canonical_name"]: person["person_id"] for person in self.people}
        self.assertEqual(by_name["郗璿"], "person-007")
        wave = read_json("data/annotation/person-expansion-wave-1.json")
        self.assertEqual(
            [item["person_id"] for item in sorted(wave["members"], key=lambda item: item["rank_at_selection"])],
            [f"person-{index:03d}" for index in range(8, 18)],
        )

    def test_structured_foreign_keys_validate_and_migration_is_idempotent(self) -> None:
        self.assertEqual(validate(ROOT), [])
        result = migrate(ROOT, apply=False)
        self.assertEqual(result["changed"], [])

    def test_semantic_person_name_set_and_story_selection_are_unchanged(self) -> None:
        names = {person["canonical_name"] for person in self.people}
        self.assertEqual(
            names,
            {
                "王羲之", "郗鑒", "王導", "王凝之", "謝道韞", "謝安", "郗璿",
                "桓溫", "劉惔", "庾亮", "王敦", "袁宏", "温嶠", "王濛", "孫晷", "王遐", "蘇峻",
                "謝尚", "周顗", "王戎", "劉琨", "鄧攸", "謝鯤", "韓伯", "何充", "陸機", "向秀",
                "殷浩", "卞壼", "王恭", "朱伺", "孟陋", "孫恩", "伏滔", "和嶠",
            },
        )
        story_ids = [record["entry_id"] for record in read_json("data/story-chain-gold-set.json")["records"]]
        self.assertEqual(len(story_ids), 16)
        self.assertEqual(len(set(story_ids)), 16)


if __name__ == "__main__":
    unittest.main()
