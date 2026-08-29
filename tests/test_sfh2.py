from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2.common import canonical_json, stable_hash  # noqa: E402


SFH2 = ROOT / "data/generated/sfh2"


def load(name: str) -> dict:
    return json.loads((SFH2 / name).read_text(encoding="utf-8"))


class SFH2HIR1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        required = [
            "input-manifest.json",
            "candidate-observations.json",
            "existing-person-link-candidates.json",
            "existing-person-link-results.json",
            "candidate-blocking.json",
            "candidate-pair-judgments.json",
            "entity-consolidation.json",
            "relation-endpoint-reprojection.json",
            "consolidated-graph.json",
            "growth-series.json",
            "metrics.json",
        ]
        missing = [name for name in required if not (SFH2 / name).is_file()]
        if missing:
            raise unittest.SkipTest("SFH2 projection is not built: " + ", ".join(missing))

    def test_frozen_input_universe_and_candidate_entity_distinction(self):
        manifest = load("input-manifest.json")
        observations = load("candidate-observations.json")
        metrics = load("metrics.json")
        self.assertEqual(188, manifest["story_count"])
        self.assertEqual(3303, observations["observation_count"])
        self.assertEqual(597, observations["candidate_observation_count"])
        self.assertEqual(594, observations["entity_resolution_candidate_observation_count"])
        self.assertEqual(542, observations["source_candidate_person_id_count"])
        self.assertEqual(542, metrics["original_sfh1_candidate_person_ids"])
        self.assertNotEqual(metrics["candidate_observations"], metrics["unique_new_candidate_entities"])

    def test_all_outputs_are_candidate_only(self):
        for path in SFH2.glob("*.json"):
            if path.name in {"input-manifest.json", "cost-metrics.json", "cache-index.json"}:
                continue
            document = load(path.name)
            self.assertTrue(document.get("candidate_only"), path.name)
            self.assertFalse(document.get("canonical_write_back"), path.name)

    def test_production_person_links_use_catalogue_ids_only(self):
        people = {row["person_id"] for row in json.loads((ROOT / "data/people.json").read_text(encoding="utf-8"))["people"]}
        links = load("existing-person-link-results.json")
        for row in links["records"]:
            selected = row.get("selected_person_id")
            if selected:
                self.assertIn(selected, people)
                self.assertFalse(selected.startswith("hdb2-candidate-person-"))

    def test_semantic_dossiers_do_not_expose_production_ids_as_answer_labels(self):
        from sfh2.consolidation import _link_payload, build_existing_link_candidates
        from sfh2.inputs import build_candidate_observations, load_documents

        documents = load_documents()
        observations = build_candidate_observations(documents)
        candidates = build_existing_link_candidates(observations, documents)
        record = next((row for row in candidates["records"] if row.get("candidates")), None)
        self.assertIsNotNone(record)
        observation = next(row for row in observations["records"] if row.get("observation_id") == record["observation_id"])
        prompt = canonical_json(_link_payload(observation, record))
        self.assertIsNone(re.search(r"\bperson-\d+\b", prompt))

    def test_hda2_suppressed_forms_do_not_reenter(self):
        audit = load("hda2-suppression-audit.json")
        self.assertEqual(0, audit["reintroduced_count"])
        metrics = load("metrics.json")
        self.assertEqual(0, metrics["suppressed_hda2_claim_reentry_count"])

    def test_explicit_distinctness_is_never_clustered(self):
        blocking = load("candidate-blocking.json")
        clusters = load("candidate-clusters.json")["records"]
        distinct = {
            tuple(sorted((row["left"], row["right"])))
            for row in blocking["explicit_distinct_pairs"]
        }
        for cluster in clusters:
            members = set(cluster["member_observation_ids"])
            for left, right in distinct:
                self.assertFalse({left, right} <= members, cluster["cluster_id"])
        self.assertEqual(0, load("cluster-validation.json")["violation_count"])

    def test_relation_endpoints_are_consolidated_and_non_self(self):
        relation = load("relation-endpoint-reprojection.json")
        consolidation = load("entity-consolidation.json")
        valid = {row.get("entity_id") for row in consolidation["observation_entities"] if row.get("entity_id")}
        for row in relation["records"]:
            for key in ("subject_endpoint", "object_endpoint"):
                if row.get(key):
                    self.assertIn(row[key], valid)
            if row.get("relation_type") != "other" and row.get("subject_endpoint") and row.get("object_endpoint"):
                self.assertNotEqual(row.get("subject_endpoint"), row.get("object_endpoint"))

    def test_growth_series_preserves_sfH1_reference_and_three_points(self):
        growth = load("growth-series.json")
        self.assertEqual(["baseline", "HGE1-WA-SFH2", "HGE1-WB-SFH2"], [row["wave"] for row in growth["series"]])
        self.assertEqual(["baseline", "HGE1-WA-SFH1", "HGE1-WB-SFH1"], [row["wave"] for row in growth["sfh1_reference_series"]])
        self.assertTrue(growth["candidate_observation_is_not_person_metric"])

    def test_replay_cost_is_separate_from_new_provider_cost(self):
        cost = load("cost-metrics.json")
        self.assertEqual(0, cost["new_live_calls"])
        self.assertGreaterEqual(cost["cache_hits"], 1)
        self.assertGreater(cost["replayed_total_tokens"], 0)
        self.assertEqual(0, cost["provider_total_tokens"])

    def test_sparse_blocking_is_not_all_pairs(self):
        blocking = load("candidate-blocking.json")
        self.assertLess(blocking["blocked_pair_count"], blocking["total_possible_pairs"])
        self.assertGreater(blocking["discarded_deterministic_non_candidate_pairs"], 0)

    def test_human_audit_sample_has_requested_strata_when_available(self):
        audit = load("human-audit-sample.json")
        self.assertEqual(
            {
                "candidate_candidate_merges": 30,
                "candidate_to_existing_links": 30,
                "distinct_person_decisions": 20,
                "unresolved_cases": 20,
            },
            audit["actual_counts"],
        )

    def test_canonical_json_hash_is_order_independent(self):
        left = {"z": [2, 1], "a": {"b": "史", "a": 1}}
        right = {"a": {"a": 1, "b": "史"}, "z": [2, 1]}
        self.assertEqual(canonical_json(left), canonical_json(right))
        self.assertEqual(stable_hash(left), stable_hash(right))

    def test_forbidden_regression_merges_are_absent(self):
        metrics = load("metrics.json")
        self.assertEqual(0, metrics["forbidden_identity_merge_count"])
        self.assertEqual(0, metrics["explicit_distinct_cluster_violations"])
        self.assertEqual(0, metrics["suppressed_hda2_claim_reentry_count"])


if __name__ == "__main__":
    unittest.main()
