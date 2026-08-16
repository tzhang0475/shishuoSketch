from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

from scripts.validate_hg1_1 import validate


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data/derived"
HISTORY = ROOT / "site/public/generated/history"


def read(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class HG1HistoricalDensificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.candidates = read("data/derived/hg1-1-relation-candidates.json")
        cls.review = read("data/derived/hg1-1-relation-review.json")
        cls.materialization = read("data/derived/hg1-1-relation-materialization.json")
        cls.graph = read("data/derived/hg1-1-graph-projection.json")
        cls.temporal = read("data/derived/hg1-1-temporal-constraints.json")
        cls.delta = read("data/derived/hg1-1-hg0-delta.json")
        cls.coverage = read("data/derived/hg1-1-relation-depth-coverage.json")
        cls.ux_delta = read("data/derived/hg1-1-ux-coverage-delta.json")

    def test_validator_passes(self) -> None:
        self.assertEqual(validate(), [])

    def test_relation_review_is_explicit_and_endpoint_conservative(self) -> None:
        self.assertEqual(self.candidates["scope"]["production_person_count"], 75)
        self.assertEqual(self.candidates["scope"]["production_story_count"], 143)
        self.assertEqual(self.candidates["scope"]["selected_x1_1_story_count"], 20)
        self.assertEqual(self.candidates["candidate_count"], 73)
        self.assertEqual(self.review["counts"], {
            "accepted": 12,
            "direct_projection_additions": 3,
            "rejected": 0,
            "unresolved": 61,
        })
        self.assertTrue(all(row["review_status"] == "unresolved" for row in self.candidates["source_scan"]))
        self.assertEqual(
            {row["relation_id"] for row in self.materialization["records"] if row["direct_projection_status"] == "add_hg1_1_direct_edge"},
            {"relation-r3b-003", "relation-r3b-004", "relation-r3b-005"},
        )

    def test_direct_relations_and_contextual_edges_remain_separate(self) -> None:
        new_edges = [edge for edge in self.graph["edges"] if edge["edge_id"] in set(self.graph["new_edge_ids"])]
        direct = [edge for edge in new_edges if edge["projection_role"] == "semantic_direct" and edge["source"]["node_type"] == "Person" and edge["target"]["node_type"] == "Person"]
        self.assertEqual({edge["edge_type"] for edge in direct}, {"relation_institutional", "relation_political"})
        self.assertTrue(any(edge["edge_type"] == "service_context_in_story" for edge in self.graph["edges"]))
        self.assertTrue(any(edge["edge_type"] == "service_context_in_event" for edge in self.graph["edges"]))
        self.assertEqual(self.coverage["before"]["direct_person_relation_edges"], 10)
        self.assertEqual(self.coverage["after"]["direct_person_relation_edges"], 13)
        self.assertEqual(self.coverage["delta"]["direct_person_relation_edges"], 3)

    def test_temporal_backfill_preserves_unknown_and_does_not_use_tenure_alone(self) -> None:
        self.assertEqual(len(self.temporal["records"]), 143)
        self.assertEqual(self.temporal["counts"]["resolved"], 11)
        self.assertEqual(self.temporal["counts"]["unknown"], 132)
        self.assertEqual(self.temporal["counts"]["exact"], 1)
        self.assertEqual(self.temporal["counts"]["bounded"], 10)
        self.assertEqual(self.temporal["counts"]["person_tenure_only_resolutions"], 0)
        self.assertTrue(all(row["resolution_status"] == "unknown" or row["review_status"] == "reviewed" for row in self.temporal["records"]))
        self.assertTrue(all(row["start_year_ce"] is None for row in self.temporal["records"] if row["resolution_status"] == "unknown"))

    def test_reviewed_extension_facts_are_projected_without_write_back(self) -> None:
        self.assertEqual(self.delta["counts"]["added_nodes"], 2)
        self.assertEqual(self.delta["counts"]["added_edges"], 8)
        self.assertEqual(self.delta["counts"]["inherited_x1_reviewed_facts"], 3)
        protection = read("data/derived/hg1-1-protection-manifest.json")
        self.assertFalse(any(protection["write_back"].values()))
        self.assertEqual(self.graph["graph_id"], "hg1-1-published-story-scope")

    def test_ux_refresh_exposes_hg1_reviewed_coverage(self) -> None:
        self.assertEqual(self.ux_delta["after"]["relation_shards_with_evidence"], 12)
        self.assertEqual(self.ux_delta["after"]["story_temporal_context_rows"], 11)
        self.assertGreater(self.ux_delta["after"]["era_cards_with_people"], 0)
        relation = read("site/public/generated/history/relation/relation-r3b-004.json")
        self.assertEqual(relation["review_status"], "reviewed")
        self.assertEqual(relation["time"]["status"], "event_bounded")
        self.assertEqual(relation["time"]["label"]["original"], "蘇峻之亂")
        story = read("site/public/generated/history/story/06-yaliang-023.json")
        self.assertEqual(story["historical_context"][0]["review_status"], "reviewed")
        self.assertEqual(story["historical_context"][0]["start_year_ce"], 328)

    def test_hg1_projection_rebuild_is_deterministic(self) -> None:
        output_paths = sorted(
            [path for path in (DERIVED).glob("hg1-1-*.json")]
            + [path for path in HISTORY.rglob("*.json")]
        )

        def snapshot() -> dict[str, str]:
            return {path.relative_to(ROOT).as_posix(): sha256(path) for path in output_paths}

        before = snapshot()
        for _ in range(2):
            subprocess.run(["python3", "scripts/build_hg1_1_historical_densification.py"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["python3", "scripts/build_ux1_historical_projection.py"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        after = snapshot()
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
