from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.build_six_person_pilot import parse_shishuo_sections
from scripts.person_identity_discovery import _find_title_like_surfaces
from scripts.validate_person_alias_segmentation import validate


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class RepeatedAliasSegmentationTests(unittest.TestCase):
    def test_source_scanner_segments_adjacent周侯_occurrences(self) -> None:
        path = ROOT / "content/processed/shishuo/entries/33-youhui/entry-006.md"
        raw = path.read_text(encoding="utf-8")
        main_text = next(
            text
            for section, text, _metadata in parse_shishuo_sections(raw)
            if section == "main_text"
        )
        rows = [
            row
            for row in _find_title_like_surfaces(main_text)
            if row[2] == "周侯"
            and row[0] >= main_text.index("周侯周侯")
        ]
        self.assertEqual([(row[0], row[2]) for row in rows], [(148, "周侯"), (150, "周侯")])
        self.assertNotIn("周侯周侯", [row[2] for row in _find_title_like_surfaces(main_text)])

    def test_canonical_source_retains_exact_adjacent_characters(self) -> None:
        raw = (ROOT / "content/processed/shishuo/entries/33-youhui/entry-006.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("我不殺周侯周侯由我而死", raw.replace("\n", ""))

    def test周顗_has_two_non_overlapping_contextual_occurrences(self) -> None:
        materialization = read("data/derived/person-expansion-wave-2-materialization.json")
        member = next(item for item in materialization["members"] if item["person_id"] == "person-019")
        rows = [
            item
            for item in member["withheld_occurrences"]
            if item.get("source_id") == "33-youhui-006"
            and item.get("section") == "main_text"
            and item.get("surface") == "周侯"
        ]
        self.assertEqual(len(rows), 2)
        self.assertEqual(sorted(item["offset"] for item in rows), [148, 150])
        spans = sorted((item["offset"], item["offset"] + len(item["surface"])) for item in rows)
        self.assertLessEqual(spans[0][1], spans[1][0])
        self.assertTrue(all(item["association_mode"] == "contextual" for item in rows))
        self.assertNotIn(
            "周侯周侯",
            [item.get("surface") for item in member["withheld_occurrences"]],
        )

    def test_synthetic_alias_is_absent_from_registry_and_person_sketch(self) -> None:
        aliases = read("data/aliases.json")["aliases"]
        self.assertFalse(any(item.get("surface") == "周侯周侯" for item in aliases))
        bundle = read("data/derived/sc1-site.json")
        sketch = bundle["person_sketches"]["person-019"]
        self.assertNotIn(
            "周侯周侯",
            [item["surface"]["original"] for item in sketch["aliases"]],
        )
        self.assertTrue(all(item["occurrence_count"] > 0 for item in sketch["aliases"]))

    def test_all_current_production_aliases_pass_repetition_validator(self) -> None:
        self.assertEqual(validate(ROOT), [])


if __name__ == "__main__":
    unittest.main()
