from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from jsonschema import Draft202012Validator

from scripts.build_irr0 import (
    GOLD_PATH,
    PILOT_STORY_IDS,
    REPORT_PATH,
    ROOT,
    SCHEMA_PATH,
    build_documents,
    stable_json,
)
from scripts.validate_irr0 import validate


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class IRR01Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gold = read_json(ROOT / GOLD_PATH)
        cls.report = read_json(ROOT / REPORT_PATH)
        cls.schema = read_json(ROOT / SCHEMA_PATH)

    def test_validator_passes(self) -> None:
        self.assertEqual(validate(ROOT), [])

    def test_fixed_pilot_scope_and_rounds(self) -> None:
        self.assertEqual(self.gold["scope"]["story_ids"], list(PILOT_STORY_IDS))
        self.assertEqual(len(self.gold["records"]), 5)
        for record in self.gold["records"]:
            self.assertEqual([row["round"] for row in record["rounds"]], [0, 1, 2])
            self.assertEqual(record["rounds"][0]["evidence_added"], [])
            self.assertTrue(record["rounds"][1]["evidence_added"])
            self.assertTrue(record["rounds"][2]["evidence_added"])

    def test_schema_and_required_critical_spans(self) -> None:
        self.assertEqual(list(Draft202012Validator(self.schema).iter_errors(self.gold)), [])
        serialized = json.dumps(self.gold, ensure_ascii=False)
        for phrase in ("陶公起止拜", "引咎自谢", "一丘一壑，自谓过之", "不意天壤之中，乃有王郎！"):
            self.assertIn(phrase, serialized)
        for record in self.gold["records"]:
            self.assertTrue(record["critical_spans"])
            self.assertTrue(all(row.get("critical") for current in record["rounds"] for row in current["text_reading"]["salient_spans"] if row["span"] in record["critical_spans"]))

    def test_gain_progression_and_control_round(self) -> None:
        progressive = []
        hard_negative = []
        for record in self.gold["records"]:
            depths = []
            for current in record["rounds"]:
                critical = [row["depth"] for row in current["text_reading"]["salient_spans"] if row.get("critical")]
                depths.append(sum(critical) / len(critical))
                for item in current["evidence_added"]:
                    if item["expected_role"] == "hard_negative":
                        hard_negative.append((record["story_id"], current["round"]))
            if depths[0] < depths[1] < depths[2]:
                progressive.append(record["story_id"])
        self.assertGreaterEqual(len(progressive), 3)
        self.assertTrue(hard_negative)
        self.assertTrue(any(row["gain_vector"]["G_D"] > 0 for record in self.gold["records"] for row in record["rounds"]))

    def test_evidence_index_and_no_write_back(self) -> None:
        protected = [
            ROOT / "data/derived/sc1-site.json",
            ROOT / "data/derived/hr0-historical-situations.json",
            ROOT / "data/derived/hr0-1-ambiguity-benchmark.json",
            ROOT / "data/derived/nl0-story-sketch-gold.json",
            ROOT / "data/derived/nl1-narrative-context.json",
        ]
        before = {path: sha256(path) for path in protected}
        build_documents(ROOT)
        after = {path: sha256(path) for path in protected}
        self.assertEqual(before, after)
        for record in self.gold["records"]:
            refs = {row["evidence_ref"] for row in record["evidence_index"]}
            self.assertTrue(refs)
            for current in record["rounds"]:
                for item in current["evidence_added"]:
                    self.assertIn(item["evidence_ref"], refs)

    def test_projection_rebuild_is_byte_identical(self) -> None:
        def snapshot() -> dict[str, str]:
            return {relative: sha256(ROOT / relative) for relative in (str(GOLD_PATH), str(REPORT_PATH))}

        subprocess.run(["python3", "scripts/build_irr0.py"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        first = snapshot()
        subprocess.run(["python3", "scripts/build_irr0.py"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        second = snapshot()
        self.assertEqual(first, second)
        first_documents = build_documents(ROOT)
        second_documents = build_documents(ROOT)
        self.assertEqual(stable_json(first_documents[0]), stable_json(second_documents[0]))
        self.assertEqual(stable_json(first_documents[1]), stable_json(second_documents[1]))


if __name__ == "__main__":
    unittest.main()
