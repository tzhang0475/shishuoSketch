from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from scripts.build_hr0_1_resolution_benchmark import (
    BENCHMARK_PATH,
    METRICS_PATH,
    PROTECTION_PATH,
    SCHEMA_PATH,
    build_documents,
)
from scripts.validate_hr0_1 import validate


ROOT = Path(__file__).resolve().parents[1]


class HR01ResolutionBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.benchmark = json.loads((ROOT / BENCHMARK_PATH).read_text(encoding="utf-8"))
        cls.schema = json.loads((ROOT / SCHEMA_PATH).read_text(encoding="utf-8"))
        cls.metrics = json.loads((ROOT / METRICS_PATH).read_text(encoding="utf-8"))

    def test_validator_passes(self) -> None:
        self.assertEqual(validate(ROOT), [])

    def test_exact_hr0_story_universe_has_two_views(self) -> None:
        self.assertEqual(self.benchmark["scope"]["story_count"], 19)
        self.assertEqual(len(self.benchmark["records"]), 19)
        for record in self.benchmark["records"]:
            self.assertIn("shishuo_only_gold", record)
            self.assertIn("evidence_resolved_gold", record)
            self.assertEqual(record["shishuo_only_gold"]["view_name"], "shishuo_only")
            self.assertEqual(record["evidence_resolved_gold"]["view_name"], "evidence_resolved")
            self.assertEqual(record["case_ids"], record["shishuo_only_gold"]["case_ids"])
            self.assertEqual(record["case_ids"], record["evidence_resolved_gold"]["case_ids"])

    def test_all_hr0_uncertainties_and_explicit_cases_are_present(self) -> None:
        hr0 = json.loads((ROOT / "data/derived/hr0-historical-situations.json").read_text(encoding="utf-8"))
        cases = [case for record in self.benchmark["records"] for case in record["resolution_cases"]]
        self.assertEqual(self.benchmark["counts"]["original_hr0_uncertainty_cases"], 37)
        self.assertEqual(self.benchmark["counts"]["additional_explicit_cases"], 9)
        self.assertEqual(len(cases), 46)
        actual = {
            (record["story_id"], case["resolution_dependency"]["uncertainty_id"])
            for record in self.benchmark["records"]
            for case in record["resolution_cases"]
            if case["case_id"] not in {
                "erc-hr0-1-05-fangzheng-032-mingdi-title",
                "erc-hr0-1-05-fangzheng-032-wentaizhen-identity",
                "erc-hr0-1-02-yanyu-083-yanbo-identity",
                "erc-hr0-1-06-yaliang-017-wentaizhen-identity",
                "erc-hr0-1-05-fangzheng-031-beren-identity",
                "erc-hr0-1-19-xianyuan-026-yishao-identity",
                "erc-hr0-1-09-pinzao-017-mingdi-title",
                "erc-hr0-1-02-yanyu-036-wang-chengxiang-title",
                "erc-hr0-1-06-yaliang-029-huangong-title",
            }
        }
        expected = {
            (record["story_id"], uncertainty["uncertainty_id"])
            for record in hr0["records"]
            for uncertainty in record["uncertainties"]
        }
        self.assertEqual(actual, expected)

    def test_shishuo_only_preserves_ambiguity_and_evidence_view_resolves_explicit_case(self) -> None:
        record = next(row for row in self.benchmark["records"] if row["story_id"] == "05-fangzheng-032")
        base_title = next(row for row in record["shishuo_only_gold"]["title_mentions"] if row["surface"] == "明帝")
        resolved_title = next(row for row in record["evidence_resolved_gold"]["title_mentions"] if row["surface"] == "明帝")
        self.assertIsNone(base_title["entity_id"])
        self.assertEqual(base_title["resolution_status"], "unresolved")
        self.assertEqual(resolved_title["entity_id"], "ruler-jin-mingdi")
        self.assertEqual(resolved_title["resolution_status"], "resolved")

        base_person = next(row for row in record["shishuo_only_gold"]["participant_states"] if row["surface"] == "温太真")
        resolved_person = next(row for row in record["evidence_resolved_gold"]["participant_states"] if row["surface"] == "温太真")
        self.assertIsNone(base_person["person_id"])
        self.assertEqual(resolved_person["person_id"], "person-013")
        self.assertEqual(base_person["surface"], resolved_person["surface"])

    def test_unresolved_case_remains_explicit(self) -> None:
        record = next(row for row in self.benchmark["records"] if row["story_id"] == "02-yanyu-069")
        case = next(
            row
            for row in record["resolution_cases"]
            if row["resolution_dependency"]["dimension"] == "identity"
        )
        self.assertIn(
            case["resolution_dependency"]["resolved_status"],
            {"unresolved", "unresolved_even_with_available_evidence"},
        )
        self.assertIsNone(case["resolution_dependency"]["resolved_value"])
        title = next(row for row in record["shishuo_only_gold"]["title_mentions"] if row["surface"] == "玄度")
        self.assertEqual(title["resolution_status"], "unresolved")

    def test_case_dependencies_are_evidence_traceable(self) -> None:
        for record in self.benchmark["records"]:
            record_evidence = {ref["evidence_id"] for ref in record["evidence_refs"]}
            for case in record["resolution_cases"]:
                dependency = case["resolution_dependency"]
                self.assertTrue(set(dependency["evidence_refs"]).issubset(record_evidence))
                self.assertEqual(
                    set(dependency["evidence_refs"]),
                    set(case["shishuo_evidence_refs"]) | set(case["resolution_evidence_refs"]),
                )
                if dependency["resolved_status"] in {"resolved", "refined"}:
                    self.assertIsNotNone(dependency["resolved_value"])

    def test_schema_is_valid(self) -> None:
        self.assertEqual(list(Draft202012Validator(self.schema).iter_errors(self.benchmark)), [])

    def test_builder_is_deterministic(self) -> None:
        first = build_documents(ROOT)
        second = build_documents(ROOT)
        self.assertEqual(first, second)
        first_bytes = json.dumps(first[0], ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        second_bytes = json.dumps(second[0], ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        self.assertEqual(hashlib.sha256(first_bytes).hexdigest(), hashlib.sha256(second_bytes).hexdigest())

    def test_no_write_back_and_dependency_summary(self) -> None:
        protection = json.loads((ROOT / PROTECTION_PATH).read_text(encoding="utf-8"))
        self.assertFalse(any(protection["write_back"].values()))
        self.assertTrue(self.benchmark["policy"]["hr0_input_immutable"])
        self.assertGreater(self.metrics["counts"]["dependency_counts"].get("liu_annotation", 0), 0)
        self.assertGreater(self.metrics["counts"]["dependency_counts"].get("canonical_fact", 0), 0)
        self.assertEqual(self.metrics["counts"], self.benchmark["counts"])


if __name__ == "__main__":
    unittest.main()
