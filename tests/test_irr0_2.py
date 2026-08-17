from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from jsonschema import Draft202012Validator

from scripts.irr0_2_common import (
    GOLD_PATH,
    MODEL_SCHEMA_PATH,
    MODES,
    OUTPUT_DIR,
    PILOT_STORY_IDS,
    SC1_PATH,
    build_pilot_inputs,
    forbidden_input_keys,
    model_input_hash,
    read_json,
    stable_json,
)
from scripts.run_irr0_2 import run_experiment
from scripts.score_irr0_2 import score_all
from scripts.validate_irr0_2 import validate


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class IRR02Tests(unittest.TestCase):
    def test_validator_passes_and_scope_is_fixed(self) -> None:
        self.assertEqual(validate(ROOT), [])
        manifest = read_json(ROOT, OUTPUT_DIR / "manifest.json")
        self.assertEqual(manifest["scope"]["story_ids"], list(PILOT_STORY_IDS))
        self.assertEqual(manifest["conditions"], list(MODES))
        self.assertFalse(manifest["execution"]["real_model_run"])

    def test_public_review_artifacts_match_derived_artifacts(self) -> None:
        for filename in (
            "manifest.json",
            "text-only.json",
            "all-at-once.json",
            "iterative.json",
            "comparison.json",
            "per-story-report.json",
        ):
            self.assertEqual(
                (ROOT / OUTPUT_DIR / filename).read_bytes(),
                (ROOT / "site/public/generated/irr0-2" / filename).read_bytes(),
            )
        self.assertEqual(
            (ROOT / "data/derived/irr0-iterative-reading-gold.json").read_bytes(),
            (ROOT / "site/public/generated/irr0-2/gold.json").read_bytes(),
        )

    def test_model_inputs_exclude_gold_only_fields(self) -> None:
        pilots = build_pilot_inputs(ROOT)
        for mode, filename in {
            "text_only": "text-only.json",
            "all_at_once": "all-at-once.json",
            "iterative": "iterative.json",
        }.items():
            document = read_json(ROOT, OUTPUT_DIR / filename)
            for record in document["records"]:
                rounds = record["rounds"] if mode == "iterative" else [record]
                for current in rounds:
                    self.assertEqual(forbidden_input_keys(current["inference_input"]), [])
                    self.assertEqual(current["input_hash"], model_input_hash(current["inference_input"]))
                    allowed = set(pilots[record["story_id"]]["context_refs"])
                    if mode == "iterative":
                        allowed = set(pilots[record["story_id"]]["iterative_round_refs"][current["round"]])
                    output_refs = set()

                    def walk(value):
                        if isinstance(value, dict):
                            output_refs.update(str(item) for item in value.get("evidence_refs", []))
                            for child in value.values():
                                walk(child)
                        elif isinstance(value, list):
                            for child in value:
                                walk(child)

                    walk(current["output"])
                    self.assertTrue(output_refs <= allowed)

    def test_model_schema_and_iterative_delta_contract(self) -> None:
        schema = read_json(ROOT, MODEL_SCHEMA_PATH)
        validator = Draft202012Validator(schema)
        iterative = read_json(ROOT, OUTPUT_DIR / "iterative.json")
        for record in iterative["records"]:
            self.assertEqual([row["round"] for row in record["rounds"]], [0, 1, 2])
            for index, current in enumerate(record["rounds"]):
                self.assertEqual(list(validator.iter_errors(current["output"])), [])
                if index == 0:
                    self.assertIsNone(current["output"]["reading_delta"])
                else:
                    self.assertIsNotNone(current["output"]["reading_delta"])

    def test_comparison_answers_experiment_questions(self) -> None:
        comparison = read_json(ROOT, OUTPUT_DIR / "comparison.json")
        self.assertEqual(comparison["scientific_status"], "fixture_pipeline_only")
        self.assertIn("text_only_vs_iterative", comparison["pairwise"])
        self.assertIn("all_at_once_vs_iterative", comparison["pairwise"])
        self.assertTrue(comparison["iterative_analysis"]["hard_negative_cases"])
        self.assertIn("any_degradation", comparison["questions"])

    def test_fixture_rebuild_is_byte_identical_and_does_not_write_back(self) -> None:
        protected = {relative: sha256(ROOT / relative) for relative in (SC1_PATH, GOLD_PATH)}
        paths = [
            OUTPUT_DIR / "manifest.json",
            OUTPUT_DIR / "text-only.json",
            OUTPUT_DIR / "all-at-once.json",
            OUTPUT_DIR / "iterative.json",
        ]
        run_experiment(root=ROOT, mode="all", fixture=True)
        score_all(ROOT)
        first = {path: sha256(ROOT / path) for path in paths}
        run_experiment(root=ROOT, mode="all", fixture=True)
        score_all(ROOT)
        second = {path: sha256(ROOT / path) for path in paths}
        self.assertEqual(first, second)
        self.assertEqual(protected, {relative: sha256(ROOT / relative) for relative in protected})

    def test_review_route_is_lazy_artifact_ui_only(self) -> None:
        app = (ROOT / "site/src/App.tsx").read_text(encoding="utf-8")
        loader = (ROOT / "site/src/irrReview.ts").read_text(encoding="utf-8")
        page = (ROOT / "site/src/IRRReviewPage.tsx").read_text(encoding="utf-8")
        self.assertIn("/review/irr0", app)
        self.assertIn("generated/irr0-2/", loader)
        self.assertNotIn("from \"./generated/irr0-2", loader)
        self.assertIn("Blind review", page)
        self.assertIn("localStorage", page)
        self.assertNotIn("run_irr0_2", page)


if __name__ == "__main__":
    unittest.main()
