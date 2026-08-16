from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from scripts.build_hr0_historical_situations import (
    GOLD_PATH,
    PROTECTION_PATH,
    SC1_PATH,
    SCHEMA_PATH,
    build_documents,
)
from scripts.validate_hr0 import validate


ROOT = Path(__file__).resolve().parents[1]


class HR0HistoricalSituationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gold = json.loads((ROOT / GOLD_PATH).read_text(encoding="utf-8"))
        cls.schema = json.loads((ROOT / SCHEMA_PATH).read_text(encoding="utf-8"))
        cls.bundle = json.loads((ROOT / SC1_PATH).read_text(encoding="utf-8"))

    def test_hr0_validator_passes(self) -> None:
        self.assertEqual(validate(ROOT), [])

    def test_representative_pilot_has_nineteen_stories_and_required_categories(self) -> None:
        self.assertEqual(self.gold["scope"]["story_count"], 19)
        self.assertEqual(len(self.gold["records"]), 19)
        categories = set(self.gold["scope"]["selection_categories"])
        self.assertTrue(
            {
                "simple_single_episode",
                "multi_episode",
                "retrospective_reported",
                "presence_reference",
                "ambiguous_title",
                "liu_dependent_interpretation",
                "identity_ambiguity",
                "comparative_evaluation",
            }.issubset(categories)
        )

    def test_every_substantive_record_is_evidence_traceable(self) -> None:
        evidence_ids = {row["id"] for row in self.bundle["evidence"]}
        for record in self.gold["records"]:
            self.assertTrue(record["evidence_refs"], record["story_id"])
            ref_ids = {ref["evidence_id"] for ref in record["evidence_refs"]}
            self.assertTrue(ref_ids <= evidence_ids)
            for field in (
                "episodes",
                "participant_states",
                "temporal_relations",
                "person_states",
                "title_mentions",
                "uncertainties",
            ):
                for item in record[field]:
                    self.assertTrue(item["evidence_ids"], (record["story_id"], field, item))
                    self.assertTrue(set(item["evidence_ids"]) <= ref_ids)

    def test_unknown_and_ambiguous_endpoints_are_visible(self) -> None:
        participant_states = [item for record in self.gold["records"] for item in record["participant_states"]]
        titles = [item for record in self.gold["records"] for item in record["title_mentions"]]
        self.assertTrue(any(item["resolution_status"] != "resolved" for item in participant_states))
        self.assertTrue(any(item["resolution_status"] != "resolved" for item in titles))
        self.assertTrue(any(item["uncertainty_type"] == "identity" for record in self.gold["records"] for item in record["uncertainties"]))

    def test_temporal_annotations_do_not_copy_derived_dates(self) -> None:
        serialized = json.dumps(self.gold, ensure_ascii=False)
        for forbidden in ("start_year", "end_year", "date_or_age", "start_year_ce", "end_year_ce"):
            self.assertNotIn(forbidden, serialized)
        for record in self.gold["records"]:
            for relation in record["temporal_relations"]:
                self.assertNotIn("year", relation)
                self.assertNotIn("date", relation)

    def test_annotation_and_base_text_layers_remain_distinguishable(self) -> None:
        layers = {ref["source_layer"] for record in self.gold["records"] for ref in record["evidence_refs"]}
        self.assertIn("base_text", layers)
        self.assertIn("liu_annotation", layers)
        self.assertNotEqual(
            self.gold["records"][0]["evidence_refs"][0].get("source_layer"),
            None,
        )

    def test_schema_validation_is_strict(self) -> None:
        self.assertEqual(list(Draft202012Validator(self.schema).iter_errors(self.gold)), [])

    def test_builder_is_deterministic(self) -> None:
        first = build_documents(ROOT)
        second = build_documents(ROOT)
        self.assertEqual(first, second)
        first_gold = json.dumps(first[0], ensure_ascii=False, sort_keys=True).encode("utf-8")
        second_gold = json.dumps(second[0], ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.assertEqual(hashlib.sha256(first_gold).hexdigest(), hashlib.sha256(second_gold).hexdigest())

    def test_protection_manifest_does_not_permit_write_back(self) -> None:
        protection = json.loads((ROOT / PROTECTION_PATH).read_text(encoding="utf-8"))
        self.assertFalse(any(protection["write_back"].values()))
        self.assertFalse(self.gold["policy"]["canonical_data_write_back"])
        self.assertFalse(self.gold["policy"]["canonical_fact_materialization"])


if __name__ == "__main__":
    unittest.main()
