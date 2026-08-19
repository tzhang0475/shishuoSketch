from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from jsonschema import Draft202012Validator

from scripts.irr0_2_common import SC1_PATH
from scripts.irr0_4_common import (
    CONDITIONS,
    HUMAN_REVIEW_PATH,
    HUMAN_SCHEMA_PATH,
    IRR04_STORY_IDS,
    MODEL_SCHEMA_PATH,
    OUTPUT_DIR,
    PUBLIC_OUTPUT_DIR,
    build_irr0_4_inputs,
    forbidden_input_keys,
    model_input_hash,
    output_path,
)
from scripts.validate_irr0_4 import validate


ROOT = Path(__file__).resolve().parents[1]
DERIVED_OUTPUTS = (
    OUTPUT_DIR / "manifest.json",
    OUTPUT_DIR / "semantic-ladders.json",
    OUTPUT_DIR / "memory-vs-fresh.json",
    OUTPUT_DIR / "negative-controls.json",
    OUTPUT_DIR / "span-trajectories.json",
    OUTPUT_DIR / "human-review-template.json",
    OUTPUT_DIR / "summary.json",
)


def read(relative: Path) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def sha256(relative: Path) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


class IRR04Tests(unittest.TestCase):
    def test_validator_passes_and_primary_scope_is_exact(self) -> None:
        self.assertEqual(validate(ROOT), [])
        inputs = build_irr0_4_inputs(ROOT)
        self.assertEqual(tuple(inputs), IRR04_STORY_IDS)
        manifest = read(OUTPUT_DIR / "manifest.json")
        self.assertEqual(manifest["scope"]["story_ids"], list(IRR04_STORY_IDS))
        self.assertEqual(manifest["conditions"], list(CONDITIONS))

    def test_semantic_stages_and_critical_spans_are_complete(self) -> None:
        inputs = build_irr0_4_inputs(ROOT)
        document = read(output_path())
        for story_id in IRR04_STORY_IDS:
            pilot = inputs[story_id]
            record = next(row for row in document["records"] if row["story_id"] == story_id)
            self.assertEqual(
                [row["semantic_stage"] for row in record["rounds"]],
                ["literal", "event_context", "relational_context", "aesthetic_rereading"],
            )
            self.assertEqual(record["critical_spans"], pilot["critical_spans"])
            for round_record in record["rounds"]:
                self.assertTrue(set(pilot["critical_spans"]).issubset(round_record["gold"]["target_spans"]))
            self.assertEqual(record["negative_control"]["round_label"], "1N")
            self.assertEqual(record["negative_control"]["branch_role"], "hard_negative")

    def test_inference_is_gold_isolated_and_memory_fresh_contract_is_explicit(self) -> None:
        document = read(output_path())
        for record in document["records"]:
            for round_record in [*record["rounds"], record["negative_control"]]:
                label = round_record["round_label"]
                for condition in CONDITIONS:
                    envelope = round_record[f"{condition}_reading"]
                    payload = envelope["inference_input"]
                    self.assertEqual(forbidden_input_keys(payload), [])
                    serialized = json.dumps(payload, ensure_ascii=False)
                    self.assertNotIn("gold_expected_effect", serialized)
                    self.assertNotIn("gold_target_spans", serialized)
                    self.assertEqual(envelope["input_hash"], model_input_hash(payload))
                    if condition == "fresh" or label == "R0":
                        self.assertNotIn("previous_reading", payload)
                    else:
                        self.assertIn("previous_reading", payload)

    def test_model_and_human_schemas_are_separate(self) -> None:
        model_schema = read(MODEL_SCHEMA_PATH)
        human_schema = read(HUMAN_SCHEMA_PATH)
        model = read(OUTPUT_DIR / "semantic-ladders.json")
        human = read(HUMAN_REVIEW_PATH)
        model_validator = Draft202012Validator(model_schema)
        for record in model["records"]:
            for round_record in [*record["rounds"], record["negative_control"]]:
                for condition in CONDITIONS:
                    output = round_record[f"{condition}_reading"]["output"]
                    self.assertEqual(list(model_validator.iter_errors(output)), [])
        self.assertEqual(list(Draft202012Validator(human_schema).iter_errors(human)), [])
        self.assertEqual(human["records"], [])

    def test_negative_controls_are_separate_and_fixture_recognizes_no_change(self) -> None:
        negative = read(OUTPUT_DIR / "negative-controls.json")
        self.assertEqual(negative["record_count"], len(IRR04_STORY_IDS) * 2)
        self.assertEqual(negative["recognized_count"], negative["record_count"])
        self.assertTrue(all(row["negative"]["visible_change_count"] == 0 for row in negative["records"]))

    def test_public_artifacts_match_and_manifest_has_no_self_hash(self) -> None:
        manifest = read(OUTPUT_DIR / "manifest.json")
        self.assertIsNone(manifest["self_hash"])
        for relative in DERIVED_OUTPUTS:
            public = PUBLIC_OUTPUT_DIR / relative.name
            self.assertEqual((ROOT / relative).read_bytes(), (ROOT / public).read_bytes())

    def test_rebuild_is_byte_identical_and_protected_sc1_is_unchanged(self) -> None:
        protected = sha256(SC1_PATH)
        subprocess.run(["python3", "scripts/run_irr0_4.py", "--fixture"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["python3", "scripts/score_irr0_4.py"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        first = {relative: sha256(relative) for relative in DERIVED_OUTPUTS}
        subprocess.run(["python3", "scripts/run_irr0_4.py", "--fixture"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["python3", "scripts/score_irr0_4.py"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        second = {relative: sha256(relative) for relative in DERIVED_OUTPUTS}
        self.assertEqual(first, second)
        self.assertEqual(protected, sha256(SC1_PATH))

    def test_review_ui_exposes_ladder_controls_without_production_data_import(self) -> None:
        page = (ROOT / "site/src/IRRReviewPage.tsx").read_text(encoding="utf-8")
        ladder = (ROOT / "site/src/IRR04SemanticLadder.tsx").read_text(encoding="utf-8")
        loader = (ROOT / "site/src/irr04Review.ts").read_text(encoding="utf-8")
        self.assertIn("Semantic Ladder", page)
        self.assertIn("Memory", ladder)
        self.assertIn("Fresh", ladder)
        self.assertIn("Negative Control", ladder)
        self.assertIn("anchoring_detected", ladder)
        self.assertIn("localStorage", ladder)
        self.assertIn("generated/irr0-4/", loader)
        self.assertNotIn("irr0-4", (ROOT / "data/derived/sc1-site.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
