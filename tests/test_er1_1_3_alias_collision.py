from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.person_resolution import apply_reviewed_decision, resolve_mention


ROOT = Path(__file__).resolve().parents[1]
RUAN_XIAN = {
    "target_kind": "identity_candidate",
    "candidate_id": "candidate-identity-er1-1-3-39b990b1195ed57c4fec0e84",
    "canonical_name": "阮咸",
}
SHI_BAO = {
    "target_kind": "production_person",
    "person_id": "person-037",
    "canonical_name": "石苞",
}


def association(
    target: dict[str, str],
    surface: str,
    mode: str = "exact",
    alias_type: str = "courtesy_name",
) -> dict[str, object]:
    return {
        "target": target,
        "surface": surface,
        "alias_type": alias_type,
        "association_mode": mode,
        "association_strength": "strong",
        "evidence_ids": ["fixture-evidence"],
        "basis": "synthetic_test_fixture",
    }


class Er113AliasCollisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        effective = json.loads(
            (ROOT / "data/derived/person-resolution-effective.json").read_text(encoding="utf-8")
        )
        cls.rows = effective["mentions"] + effective.get("derived_mentions", [])
        cls.bundle = json.loads(
            (ROOT / "data/derived/sc1-site.json").read_text(encoding="utf-8")
        )
        cls.links = json.loads(
            (ROOT / "data/derived/person-story-links.json").read_text(encoding="utf-8")
        )["links"]

    def test_gold_story_23_rendan_013_resolves_to_nonproduction_ruan_xian(self) -> None:
        row = next(
            row
            for row in self.rows
            if row.get("mention_id") == "shishuo-w3-38231138347d766d147ad8bc"
        )
        self.assertEqual(row["surface"], "仲容")
        self.assertEqual(row["resolution_status"], "resolved")
        self.assertEqual(row["resolution_target"], RUAN_XIAN)
        self.assertEqual(row["resolution_decision_source"], "human_review")
        self.assertIsNone(row["person_id"])
        self.assertNotEqual(row["person_id"], "person-037")

        story = next(item for item in self.bundle["stories"] if item["id"] == "23-rendan-013")
        segment = next(
            item
            for item in story["reading"]["main_text"]["segments"]
            if item.get("mention_id") == row["mention_id"]
        )
        self.assertEqual(segment["type"], "identity_mention")
        self.assertEqual(segment["target_kind"], "identity_candidate")
        self.assertEqual(segment["canonical_name"]["original"], "阮咸")
        self.assertNotEqual(segment.get("person_id"), "person-037")

    def test_false_shi_bao_person_story_link_is_removed(self) -> None:
        self.assertFalse(
            any(
                link["person_id"] == "person-037"
                and link["entry_id"] == "23-rendan-013"
                for link in self.links
            )
        )

    def test_full_ruan_and_shi_appellations_choose_their_own_identity(self) -> None:
        targets = {
            "identity_candidate:candidate-identity-er1-1-3-39b990b1195ed57c4fec0e84": RUAN_XIAN,
            "production_person:person-037": SHI_BAO,
        }
        result = resolve_mention(
            {"mention_id": "fixture-ruan-zhongrong", "surface": "仲容", "evidence": {"section_offset": 1}},
            text="阮仲容",
            alias_index={
                "仲容": [association(RUAN_XIAN, "仲容", "contextual"), association(SHI_BAO, "仲容")],
                "阮仲容": [association(RUAN_XIAN, "阮仲容", alias_type="surname_plus_courtesy_name")],
            },
            targets_by_key=targets,
        )
        self.assertEqual(result["target"], RUAN_XIAN)
        self.assertEqual(result["semantic_span"]["text"], "阮仲容")

        result = resolve_mention(
            {"mention_id": "fixture-shi-zhongrong", "surface": "仲容", "evidence": {"section_offset": 1}},
            text="石仲容",
            alias_index={
                "仲容": [association(RUAN_XIAN, "仲容", "contextual"), association(SHI_BAO, "仲容")],
                "石仲容": [association(SHI_BAO, "石仲容", alias_type="surname_plus_courtesy_name")],
            },
            targets_by_key=targets,
        )
        self.assertEqual(result["target"], SHI_BAO)
        self.assertEqual(result["semantic_span"]["text"], "石仲容")

    def test_bare_shared_alias_never_uses_production_status_as_identity_evidence(self) -> None:
        result = resolve_mention(
            {"mention_id": "fixture-bare-zhongrong", "surface": "仲容", "person_id": "person-037", "evidence": {}},
            text="仲容",
            alias_index={"仲容": [association(RUAN_XIAN, "仲容", "contextual"), association(SHI_BAO, "仲容")]},
            targets_by_key={
                "identity_candidate:candidate-identity-er1-1-3-39b990b1195ed57c4fec0e84": RUAN_XIAN,
                "production_person:person-037": SHI_BAO,
            },
        )
        self.assertEqual(result["status"], "candidate_for_review")
        self.assertIsNone(result["target"])

    def test_reviewed_ruan_decision_is_stable_when_shi_is_also_known(self) -> None:
        decision = {
            "mention_id": "fixture-reviewed-zhongrong",
            "resolution_status": "resolved",
            "target": RUAN_XIAN,
            "review_status": "reviewed",
            "review_note": "阮咸",
            "evidence_ids": ["fixture-evidence"],
        }
        result = resolve_mention(
            {"mention_id": decision["mention_id"], "surface": "仲容", "person_id": "person-037", "evidence": {}},
            text="仲容",
            alias_index={"仲容": [association(RUAN_XIAN, "仲容", "contextual"), association(SHI_BAO, "仲容")]},
            targets_by_key={
                "identity_candidate:candidate-identity-er1-1-3-39b990b1195ed57c4fec0e84": RUAN_XIAN,
                "production_person:person-037": SHI_BAO,
            },
            decision=decision,
        )
        self.assertEqual(result["decision_source"], "human_review")
        self.assertEqual(result["target"], RUAN_XIAN)
        self.assertEqual(apply_reviewed_decision(result, result)["target"], RUAN_XIAN)


if __name__ == "__main__":
    unittest.main()
