from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from scripts.build_nl1_narrative_corpus import (
    CONTEXT_PATH,
    PROTECTED_PATHS,
    ROOT,
    SCHEMA_PATH,
    SELECTION_PATH,
    build_documents,
    stable_json,
)
from scripts.validate_nl1 import validate


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class NL1NarrativeCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.context = read_json(ROOT / CONTEXT_PATH)
        cls.selection = read_json(ROOT / SELECTION_PATH)
        cls.schema = read_json(ROOT / SCHEMA_PATH)

    def test_validator_passes(self) -> None:
        self.assertEqual(validate(ROOT), [])

    def test_scope_is_thirty_existing_stories_and_includes_hr0_nl0_regressions(self) -> None:
        expected = {
            "01-dexing-014",
            "01-dexing-016",
            "01-dexing-025",
            "02-yanyu-035",
            "02-yanyu-036",
            "02-yanyu-069",
            "02-yanyu-079",
            "02-yanyu-083",
            "04-wenxue-036",
            "04-wenxue-094",
            "05-fangzheng-012",
            "05-fangzheng-023",
            "05-fangzheng-025",
            "05-fangzheng-028",
            "05-fangzheng-031",
            "05-fangzheng-032",
            "05-fangzheng-055",
            "06-yaliang-017",
            "06-yaliang-027",
            "06-yaliang-029",
            "07-shijian-005",
            "08-shangyu-077",
            "09-pinzao-017",
            "11-jiewu-005",
            "17-shangshi-002",
            "19-xianyuan-026",
            "20-shujie-005",
            "25-paidiao-009",
            "27-jiajue-008",
            "35-huoni-003",
        }
        self.assertEqual(set(self.context["scope"]["selected_story_ids"]), expected)
        self.assertEqual(len(self.context["records"]), 30)
        self.assertEqual(set(self.context["scope"]["selected_story_ids"]), set(self.selection["scope"]["selected_story_ids"]))
        for story_id in ("05-fangzheng-032", "02-yanyu-036", "06-yaliang-017", "09-pinzao-017", "19-xianyuan-026", "27-jiajue-008"):
            self.assertIn(story_id, expected)

    def test_both_views_are_schema_valid(self) -> None:
        for document in (self.context, self.selection):
            self.assertEqual(list(Draft202012Validator(self.schema).iter_errors(document)), [])

    def test_every_role_has_selected_or_abstained_and_rejected_guard(self) -> None:
        roles = {"background", "in_scene", "off_scene", "person_glimpse", "resonance"}
        selected = rejected = abstained = 0
        for record in self.selection["records"]:
            self.assertEqual(set(record["roles"]), roles)
            for role, value in record["roles"].items():
                self.assertGreaterEqual(len(value["rejected_candidate_ids"]), 1)
                self.assertEqual(value["role"], role)
                if value["selection_state"] == "selected":
                    self.assertTrue(value["selected_candidate_ids"])
                else:
                    self.assertFalse(value["selected_candidate_ids"])
                selected += len(value["selected_candidate_ids"])
                rejected += len(value["rejected_candidate_ids"])
                abstained += len(value["abstained_candidate_ids"])
        self.assertEqual(selected, 91)
        self.assertEqual(rejected, 150)
        self.assertEqual(abstained, 59)

    def test_selected_and_rejected_context_is_evidence_traceable(self) -> None:
        story_evidence = {
            row["id"]: set(row.get("evidence_ids", []))
            for row in read_json(ROOT / "data/derived/sc1-site.json")["stories"]
        }
        for record in self.selection["records"]:
            for role in record["roles"].values():
                for candidate in role["candidates"]:
                    self.assertTrue(candidate["supporting_evidence"])
                    self.assertTrue(set(candidate["supporting_evidence"]).issubset(story_evidence[record["story_id"]]))
                    if candidate["candidate_status"] == "rejected":
                        self.assertTrue(candidate["rejection_reason"])
        for record in self.context["records"]:
            self.assertTrue(record["current_scene"]["evidence_ids"])
            self.assertTrue(record["uncertainties"])
            for span in record["key_source_spans"]:
                self.assertTrue(span["locator"])

    def test_known_nl0_boundary_cases_remain_explicit(self) -> None:
        by_story = {row["story_id"]: row for row in self.context["records"]}
        # The known title/presence case is still explicit rather than flattened
        # into a generic Person paragraph.
        self.assertTrue(any(row["presence_status"] == "referenced" for row in by_story["05-fangzheng-032"]["current_scene"]["participant_states"]))
        self.assertTrue(by_story["05-fangzheng-032"]["uncertainties"])
        # The annotation-only political background remains outside the scene.
        self.assertTrue(any(row["presence_status"] == "contextual" for row in by_story["05-fangzheng-031"]["current_scene"]["participant_states"]))
        # The control Story explicitly abstains from resonance.
        resonance = next(row for row in self.selection["records"] if row["story_id"] == "25-paidiao-009")["roles"]["resonance"]
        self.assertEqual(resonance["selection_state"], "abstained")

    def test_jianshu_lineage_is_retained_without_fact_promotion(self) -> None:
        lineage = read_json(ROOT / "data/derived/nl1-metrics.json")["s1_lineage"]
        self.assertEqual(lineage["stories_with_assertions"], 26)
        self.assertEqual(lineage["stories_with_citations"], 21)
        self.assertFalse(lineage["promotion_to_canonical_fact"])
        for record in self.context["records"]:
            self.assertIn("s1_assertion_ids", record["grounded_inputs"])
            self.assertIn("s1_citation_ids", record["grounded_inputs"])

    def test_protected_inputs_are_not_rewritten(self) -> None:
        protection = read_json(ROOT / "data/derived/nl1-protection-manifest.json")
        for relative in PROTECTED_PATHS:
            self.assertEqual(protection["protected_inputs"][relative.as_posix()], sha256(ROOT / relative))
        self.assertFalse(any(protection["write_back"].values()))

    def test_builder_is_deterministic(self) -> None:
        first = build_documents(ROOT)
        second = build_documents(ROOT)
        self.assertEqual(first, second)
        for key in first:
            self.assertEqual(stable_json(first[key]), stable_json(second[key]))


if __name__ == "__main__":
    unittest.main()
