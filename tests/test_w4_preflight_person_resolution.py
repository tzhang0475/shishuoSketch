from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from scripts.build_w4_preflight_person_resolution_gap_audit import build as build_audit
from scripts.person_resolution import _published_story_ids, resolve_mention
from scripts.validate_w4_preflight_person_resolution_gap_audit import validate


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "data/derived/w4-preflight-person-resolution-gap-audit.json"


def read(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class W4PreflightPersonResolutionTests(unittest.TestCase):
    def test_rongzhi_024_yu_taiwei_and_local_yu_gong_resolve_to_yu_liang(self) -> None:
        effective = read("data/derived/person-resolution-effective.json")
        derived = {
            row["surface"]: row
            for row in effective["derived_mentions"]
            if row.get("entry_id") == "14-rongzhi-024"
        }
        self.assertEqual(derived["庾太尉"]["resolution_target"]["person_id"], "person-010")
        self.assertEqual(derived["庾公"]["resolution_target"]["person_id"], "person-010")
        self.assertEqual(derived["庾太尉"]["display_span"]["text"], "庾太尉")
        self.assertEqual(derived["庾公"]["display_span"]["text"], "庾公")

        canonical = [
            row
            for row in effective["mentions"]
            if row.get("entry_id") == "14-rongzhi-024" and row.get("surface") == "元規"
        ]
        self.assertEqual(len(canonical), 1)
        self.assertEqual(canonical[0]["resolution_target"]["person_id"], "person-010")

    def test_rongzhi_024_person_story_edge_is_not_duplicated(self) -> None:
        links = read("data/derived/person-story-links.json")["links"]
        matching = [
            row
            for row in links
            if row.get("person_id") == "person-010" and row.get("entry_id") == "14-rongzhi-024"
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(read("data/derived/person-story-links.json")["link_count"], len(links))

    def test_audit_covers_all_published_stories_and_closes_confirmed_gap(self) -> None:
        audit = read("data/derived/w4-preflight-person-resolution-gap-audit.json")
        published = _published_story_ids(ROOT)
        self.assertEqual(audit["scope"]["published_story_ids"], sorted(published))
        self.assertEqual(audit["scope"]["published_story_count"], len(published))
        self.assertEqual(audit["scope"]["audited_story_count"], len(published))
        rows = [
            row
            for row in audit["records"]
            if row.get("story_id") == "14-rongzhi-024" and row.get("surface") == "庾太尉"
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "safe_story_local")
        self.assertEqual(rows[0]["existing_effective_resolution"]["resolution_target"]["person_id"], "person-010")
        self.assertTrue(any(row.get("surface") == "王胡之" and row.get("status") == "unresolved" for row in audit["records"] if row.get("story_id") == "14-rongzhi-024"))

    def test_bare_titles_do_not_resolve_to_yu_liang_without_context(self) -> None:
        target = {"target_kind": "production_person", "person_id": "person-010", "canonical_name": "庾亮"}
        association = {
            "target": target,
            "surface": "公",
            "alias_type": "contextual_title",
            "association_mode": "contextual",
            "association_strength": "medium",
            "evidence_ids": ["fixture"],
            "basis": "fixture",
        }
        for surface in ("太尉", "公"):
            result = resolve_mention(
                {"mention_id": f"fixture-{surface}", "surface": surface, "person_id": None, "evidence": {}},
                text=surface,
                alias_index={surface: [{**association, "surface": surface}]},
                targets_by_key={"production_person:person-010": target},
            )
            self.assertNotEqual(result["status"], "resolved")

    def test_audit_validator_passes(self) -> None:
        self.assertEqual(validate(ROOT), [])

    def test_audit_build_is_byte_deterministic(self) -> None:
        before = hashlib.sha256(AUDIT_PATH.read_bytes()).hexdigest()
        build_audit(ROOT)
        first = hashlib.sha256(AUDIT_PATH.read_bytes()).hexdigest()
        build_audit(ROOT)
        second = hashlib.sha256(AUDIT_PATH.read_bytes()).hexdigest()
        self.assertEqual(before, first)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
