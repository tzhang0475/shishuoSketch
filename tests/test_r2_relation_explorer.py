from __future__ import annotations

import json
from pathlib import Path
import unittest

from opencc import OpenCC



ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / "data/derived/wp1-site.json"


class R2RelationExplorerDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
        cls.people = {person["id"]: person for person in cls.bundle["people"]}
        cls.relations = {relation["id"]: relation for relation in cls.bundle["relations"]}
        cls.reading = cls.bundle["stories"][0]["reading"]

    def direct_perspectives(self, person_id: str) -> list[tuple[str, str]]:
        result = []
        for relation in self.bundle["relations"]:
            if relation["review_status"] != "reviewed" or relation["relation_basis"] != "direct":
                continue
            if relation["subject_id"] == person_id:
                result.append((relation["object_id"], relation.get("role_b", "")))
            elif relation["object_id"] == person_id:
                result.append((relation["subject_id"], relation.get("role_a", "")))
        return result

    def test_only_reviewed_direct_relations_are_exposed(self) -> None:
        self.assertEqual(
            {
                relation["id"]
                for relation in self.bundle["relations"]
                if relation["review_status"] == "reviewed" and relation["relation_basis"] == "direct"
            },
            {
                "relation-gold-001",
                "relation-gold-002",
                "relation-gold-003",
                "relation-gold-004",
                "relation-gold-005",
                "relation-gold-006",
            },
        )
        self.assertNotIn(
            "relation-001",
            {
                relation["id"]
                for relation in self.bundle["relations"]
                if relation["relation_basis"] == "direct"
            },
        )

    def test_derived_relation_path_resolves_without_quotation(self) -> None:
        derived = self.relations["relation-001"]
        path = [self.relations[relation_id] for relation_id in derived["derived_from_relation_ids"]]
        self.assertEqual(
            [(relation["subject_id"], relation["object_id"]) for relation in path],
            [("xi-jian", "person-007"), ("person-007", "wang-xizhi")],
        )
        self.assertEqual(derived["evidence_ids"], [])

    def test_perspective_roles_are_counterpart_roles(self) -> None:
        self.assertEqual(
            dict(self.direct_perspectives("wang-xizhi")),
            {"wang-dao": "從伯", "wang-ningzhi": "子", "person-007": "配偶"},
        )
        self.assertEqual(
            dict(self.direct_perspectives("wang-ningzhi")),
            {"wang-xizhi": "父", "xie-daoyun": "配偶"},
        )
        self.assertEqual(
            dict(self.direct_perspectives("person-007")),
            {"wang-xizhi": "配偶", "xi-jian": "父"},
        )

    def test_all_relation_endpoints_and_supporting_person_resolve(self) -> None:
        for relation in self.bundle["relations"]:
            self.assertIn(relation["subject_id"], self.people)
            self.assertIn(relation["object_id"], self.people)
        self.assertEqual(self.people["person-007"]["scope_role"], "supporting")
        self.assertIn("person-007", self.reading["person_display"])

    def test_no_duplicate_reverse_direct_edges(self) -> None:
        seen = set()
        for relation in self.bundle["relations"]:
            if relation["relation_basis"] != "direct":
                continue
            key = (frozenset((relation["subject_id"], relation["object_id"])), relation.get("relation_subtype"))
            self.assertNotIn(key, seen)
            seen.add(key)

    def test_relation_display_has_original_and_simplified_forms(self) -> None:
        converter = OpenCC("t2s")
        for relation in self.bundle["relations"]:
            display = self.reading["relation_display"][relation["id"]]
            self.assertEqual(display["label"]["original"], relation["label"])
            self.assertEqual(display["label"]["simplified"], converter.convert(relation["label"]))
            for role_key in ("role_a", "role_b"):
                if relation.get(role_key) is not None:
                    self.assertEqual(display[role_key]["original"], relation[role_key])
                    self.assertEqual(display[role_key]["simplified"], converter.convert(relation[role_key]))

    def test_relation_evidence_is_available_only_for_direct_edges(self) -> None:
        evidence_ids = {evidence["id"] for evidence in self.bundle["evidence"]}
        for relation in self.bundle["relations"]:
            for evidence_id in relation["evidence_ids"]:
                self.assertIn(evidence_id, evidence_ids)
            if relation["relation_basis"] == "derived":
                self.assertFalse(relation["evidence_ids"])

    def test_empty_direct_relation_state_is_safe(self) -> None:
        synthetic = {"review_status": "candidate", "relation_basis": "direct"}
        direct = [
            relation
            for relation in [synthetic]
            if relation["review_status"] == "reviewed" and relation["relation_basis"] == "direct"
        ]
        self.assertEqual(direct, [])

    def test_navigation_history_is_local_and_reversible(self) -> None:
        history = ["wang-xizhi"]
        history = history + ["person-007"]
        history = history + ["xi-jian"]
        self.assertEqual(history[:-1], ["wang-xizhi", "person-007"])
        self.assertEqual(history[-2], "person-007")

    def test_reader_display_quotes_hide_machine_comments(self) -> None:
        for evidence in self.bundle["evidence"]:
            quote = self.reading["evidence_display"][evidence["id"]]["original"]
            self.assertNotIn("<!--", quote)
            self.assertNotIn("wikisource-SKchar", quote)


if __name__ == "__main__":
    unittest.main()
