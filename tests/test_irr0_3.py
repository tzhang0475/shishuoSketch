from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from jsonschema import Draft202012Validator

from scripts.irr0_2_common import GOLD_PATH, SC1_PATH, forbidden_input_keys
from scripts.irr0_3_common import (
    CONTEXT_REVIEW_PATH,
    MODES,
    OUTPUT_DIR,
    PILOT_STORY_IDS,
    SPAN_REVIEW_SCHEMA_PATH,
    build_irr0_3_inputs,
    output_path,
)
from scripts.validate_irr0_3 import validate


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "site/public/generated/irr0-3"
ARTIFACTS = (
    OUTPUT_DIR / "manifest.json",
    OUTPUT_DIR / "text-only.json",
    OUTPUT_DIR / "all-at-once.json",
    OUTPUT_DIR / "iterative.json",
    OUTPUT_DIR / "comparison.json",
    OUTPUT_DIR / "span-gain-report.json",
    OUTPUT_DIR / "question-gain-report.json",
    OUTPUT_DIR / "per-story-report.json",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class IRR03Tests(unittest.TestCase):
    def test_validator_passes_and_scope_is_frozen(self) -> None:
        self.assertEqual(validate(ROOT), [])
        manifest = read(ROOT / OUTPUT_DIR / "manifest.json")
        self.assertEqual(manifest["scope"]["story_ids"], list(PILOT_STORY_IDS))
        self.assertEqual(manifest["conditions"], list(MODES))

    def test_all_at_once_is_exact_iterative_union(self) -> None:
        pilots = build_irr0_3_inputs(ROOT)
        for story_id, pilot in pilots.items():
            self.assertEqual(
                set(pilot["context_refs"]),
                set(pilot["iterative_rounds"][-1]["evidence_refs"]),
                story_id,
            )
            self.assertTrue(pilot["hard_negative_refs"], story_id)

    def test_inference_inputs_have_no_gold_or_review_roles(self) -> None:
        for mode in MODES:
            document = read(ROOT / output_path(mode))
            for record in document["records"]:
                rounds = record["rounds"] if mode == "iterative" else [record]
                for current in rounds:
                    self.assertEqual(forbidden_input_keys(current["inference_input"]), [])
                    self.assertNotIn("expected_role", json.dumps(current["inference_input"], ensure_ascii=False))

    def test_transition_is_evidence_to_span_delta(self) -> None:
        document = read(ROOT / output_path("iterative"))
        for record in document["records"]:
            for index, current in enumerate(record["rounds"]):
                if index == 0:
                    self.assertIsNone(current["transition"])
                    continue
                transition = current["transition"]
                self.assertEqual(
                    transition["evidence_ids"],
                    [item["evidence_ref"] for item in current["evidence_added"]],
                )
                for span in transition["affected_spans"]:
                    self.assertIn("before_interpretation", span)
                    self.assertIn("after_interpretation", span)
                    self.assertIn("historical_depth", span)
                    self.assertIn("aesthetic_depth", span)
                    self.assertIn("unsupported_interpretation", span)

    def test_human_span_schema_is_separate_and_initially_pending(self) -> None:
        schema = read(ROOT / SPAN_REVIEW_SCHEMA_PATH)
        review = read(ROOT / "data/annotation/irr0-3-span-review.json")
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(review)), [])
        self.assertEqual(review["records"], [])
        self.assertNotEqual(CONTEXT_REVIEW_PATH, GOLD_PATH)

    def test_fixture_is_not_presented_as_real_model_result(self) -> None:
        comparison = read(ROOT / OUTPUT_DIR / "comparison.json")
        self.assertEqual(comparison["run_type"], "fixture")
        self.assertEqual(comparison["scientific_status"], "fixture_pipeline_only")
        self.assertFalse(read(ROOT / OUTPUT_DIR / "manifest.json")["execution"]["real_model_run"])

    def test_comparison_keeps_primary_and_legacy_metrics(self) -> None:
        comparison = read(ROOT / OUTPUT_DIR / "comparison.json")
        required = {
            "historical_score",
            "critical_span_score",
            "linguistic_salience_score",
            "aesthetic_operation_score",
            "omission_context_score",
            "uncertainty_score",
            "distraction_error_count",
            "historical_depth",
            "aesthetic_depth",
            "question_depth",
        }
        for summary in comparison["condition_summary"].values():
            self.assertTrue(required.issubset(summary))
        self.assertEqual(
            {row["story_id"] for row in comparison["hard_negative_analysis"]},
            set(PILOT_STORY_IDS),
        )

    def test_rebuild_is_byte_identical_and_protected_inputs_are_unchanged(self) -> None:
        protected = {path: sha256(ROOT / path) for path in (SC1_PATH, GOLD_PATH)}
        subprocess.run(
            ["python3", "scripts/run_irr0_3.py", "--mode", "all", "--fixture"],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(["python3", "scripts/score_irr0_3.py"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        first = {path: sha256(ROOT / path) for path in ARTIFACTS}
        subprocess.run(
            ["python3", "scripts/run_irr0_3.py", "--mode", "all", "--fixture"],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(["python3", "scripts/score_irr0_3.py"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        second = {path: sha256(ROOT / path) for path in ARTIFACTS}
        self.assertEqual(first, second)
        self.assertEqual(protected, {path: sha256(ROOT / path) for path in protected})

    def test_frontend_span_review_is_additive_and_local_only(self) -> None:
        page = (ROOT / "site/src/IRRReviewPage.tsx").read_text(encoding="utf-8")
        loader = (ROOT / "site/src/irr03Review.ts").read_text(encoding="utf-8")
        self.assertIn("Span Review", page)
        self.assertIn("没有影响", page)
        self.assertIn("continue_reading", page)
        self.assertIn("localStorage", page)
        self.assertIn("generated/irr0-3/", loader)
        self.assertNotIn("irr0-3", (ROOT / "data/derived/sc1-site.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
