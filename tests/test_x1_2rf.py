from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

from scripts.validate_x1_2rf import validate


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = tuple(
    f"data/derived/x1-2rf-{name}.json"
    for name in (
        "policy",
        "assertion-review",
        "original-candidate-review",
        "materialized-facts",
        "corroboration",
        "scholarly-assertions",
        "summary",
        "next-step-recommendation",
    )
)


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class X12RFTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = load("data/derived/x1-2rf-policy.json")
        cls.assertions = load("data/derived/x1-2rf-assertion-review.json")
        cls.original = load("data/derived/x1-2rf-original-candidate-review.json")
        cls.facts = load("data/derived/x1-2rf-materialized-facts.json")
        cls.corroboration = load("data/derived/x1-2rf-corroboration.json")
        cls.scholarly = load("data/derived/x1-2rf-scholarly-assertions.json")
        cls.summary = load("data/derived/x1-2rf-summary.json")

    def test_scope_and_policy_are_frozen(self) -> None:
        self.assertFalse(self.policy["automatic_acceptance"])
        self.assertEqual(self.policy["scope"]["selected_story_count"], 20)
        self.assertEqual(self.policy["scope"]["x1_2r_reopened_fact_count"], 34)
        self.assertFalse(self.policy["scope"]["new_story_selection_performed"])
        self.assertEqual(len(self.original["records"]), 34)
        self.assertEqual(self.summary["scope"]["stories_added_to_production"], 0)
        self.assertEqual(self.summary["scope"]["persons_added"], 0)

    def test_all_frozen_assertions_are_reviewed(self) -> None:
        source_rows = [row for row in self.assertions["records"] if row["source_assertion_record"]]
        self.assertEqual(len(source_rows), 132)
        self.assertEqual(self.assertions["counts"]["source_assertions_reviewed"], 132)
        self.assertEqual(len({row["source_assertion_id"] for row in source_rows}), 132)
        self.assertTrue(all(row["source_locator"] and row["evidence_hash"] for row in self.assertions["records"]))

    def test_explicit_units_can_materialize_without_accepting_parent_block(self) -> None:
        accepted = [row for row in self.assertions["records"] if row["review_status"] == "accepted"]
        self.assertEqual(len(accepted), 4)
        self.assertTrue(all(row["modality"] == "explicit" for row in accepted))
        danyang = next(row for row in accepted if row["source_assertion_id"] == "s1-assertion-40d736dd768f591858b2")
        self.assertEqual(danyang["quoted_source"], "王隱晉書")
        self.assertEqual(danyang["parent_modality"], "disputed")
        parent = next(
            row for row in self.assertions["records"]
            if row["source_assertion_id"] == "s1-assertion-40d736dd768f591858b2" and row["assertion_unit_id"] == "block"
        )
        self.assertEqual(parent["review_status"], "scholarly_assertion_only")
        self.assertEqual(len(self.facts["facts"]), 3)

    def test_transmission_and_duplicate_policy(self) -> None:
        facts = self.facts["facts"]
        self.assertEqual({row["fact_type"] for row in facts}, {"office_tenure", "location_fact"})
        self.assertTrue(all(row["source_family"] == "shishuo-jianshu-yujiaxi-local" for row in facts))
        self.assertTrue(all(row["evidence_ids"] and row["evidence_refs"] for row in facts))
        self.assertTrue(any(row["transmission_status"] == "quoted_via_liu_annotation" for row in facts))
        self.assertEqual(self.corroboration["counts"]["same_epoch_support_records"], 1)
        self.assertEqual(self.corroboration["counts"]["pre_existing_canonical_facts_corrobated"], 0)
        self.assertTrue(all(row["materialization_status"] != "materialized" for row in self.scholarly["records"]))

    def test_original_candidate_and_independent_yield_are_separate(self) -> None:
        self.assertEqual(self.original["counts"]["unresolved"], 34)
        self.assertEqual(self.original["counts"]["independent_new_fact_units"], 1)
        row = next(row for row in self.original["records"] if row["story_id"] == "07-shijian-016")
        self.assertEqual(row["original_candidate_outcome"]["review_status"], "unresolved")
        self.assertEqual(row["independent_assertion_yield"]["new_fact_accepted"], 1)
        self.assertTrue(row["no_candidate_mutation"])

    def test_validator_and_rebuild_are_deterministic(self) -> None:
        self.assertEqual(validate(), [])
        before = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in OUTPUTS}
        result = subprocess.run(
            [sys.executable, "scripts/build_x1_2rf.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        after = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in OUTPUTS}
        self.assertEqual(before, after)
        self.assertEqual(validate(), [])


if __name__ == "__main__":
    unittest.main()
