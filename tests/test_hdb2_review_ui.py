import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import hdb2_full_frontier_common as common  # noqa: E402


REVIEW_ROOT = ROOT / "site/public/generated/review/hdb2"
RUN_ROOT = ROOT / "data/generated/hdb2-f/live"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)


class HDB2ReviewProjectionTests(unittest.TestCase):
    def test_compaction_report_records_material_reduction(self):
        report = load(ROOT / "data/generated/hdb2-f/review-build-report.json")
        self.assertEqual(len(report["compaction"]), 2)
        for entry in report["compaction"]:
            self.assertGreater(entry["old_bytes"], 50 * 1024 * 1024)
            self.assertLess(entry["new_bytes"], 50 * 1024 * 1024)
            self.assertGreater(entry["reduction_ratio"], 0.8)

    def test_review_index_has_structural_queue(self):
        index = load(REVIEW_ROOT / "index.json")
        self.assertEqual(index["item_count"], 73)
        self.assertTrue(index["candidate_only"])
        self.assertFalse(index["canonical_write_back"])
        self.assertEqual(sum(index["counts_by_type"].values()), 73)
        self.assertEqual(sum(index["counts_by_priority"].values()), 73)
        self.assertTrue(index["items"][0]["item_path"].startswith("items/"))

    def test_review_items_do_not_expose_raw_traces(self):
        index = load(REVIEW_ROOT / "index.json")
        forbidden = {"hits", "evidence_text", "raw_api", "source_indexes", "debug_trace"}
        for entry in index["items"]:
            item = load(REVIEW_ROOT / entry["item_path"])
            self.assertTrue(set(item) >= {
                "review_id", "priority", "review_type", "occurrence_id", "story_id",
                "story_context", "candidate_people", "selected_evidence", "affected_facts",
                "current_state",
            })
            self.assertTrue(forbidden.isdisjoint(set(walk_keys(item))))
            self.assertTrue(item["current_state"]["candidate_only"])
            self.assertFalse(item["current_state"]["canonical_write_back"])

    def test_compact_rescue_trace_keeps_selection_refs(self):
        for run_id in ("20260826T-HDB2-F-02", "20260826T-HDB2-F-03"):
            run = RUN_ROOT / run_id
            search = load(run / "rescue-search-results.json")
            selected = load(run / "rescue-selected-passages.json")
            selected_by_occurrence = {}
            for row in selected["records"]:
                selected_by_occurrence.setdefault(str(row.get("occurrence_id")), set()).add(str(row.get("ref")))
            self.assertEqual(search["schema"], "hdb2-f-rescue-search-results-compact-v1")
            for row in search["records"]:
                self.assertNotIn("hits", row)
                self.assertNotIn("evidence_text", row)
                self.assertEqual(row["selected_count"], len(row["selected_refs"]))
                self.assertTrue(set(row["selected_refs"]).issubset(selected_by_occurrence.get(str(row["occurrence_id"]), set())))
            self.assertLess((run / "rescue-search-results.json").stat().st_size, 50 * 1024 * 1024)

    def test_compaction_helper_is_body_free(self):
        row = {
            "occurrence_id": "occ-1",
            "queries": [{"term": "康伯", "category": "observed_surface"}],
            "hits": [
                {"ref": "r1", "source_work": "晉書", "source_layer": "biography", "score": 10, "evidence_text": "full" , "query": {"term": "康伯"}},
                {"ref": "r2", "source_work": "劉注", "source_layer": "liu_annotation", "score": 9, "evidence_text": "full2", "query": {"term": "字康伯"}},
            ],
            "selected_passages": [{"ref": "r1", "evidence_text": "full"}],
        }
        compact = common.compact_rescue_search_result(row)
        self.assertEqual(compact["total_hit_count"], 2)
        self.assertEqual(compact["selected_refs"], ["r1"])
        self.assertEqual(compact["unselected_hits"][0]["ref"], "r2")
        self.assertNotIn("evidence_text", json.dumps(compact, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
