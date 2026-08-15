from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from scripts.build_ztj0_corpus import stable_id
from scripts.validate_ztj0 import validate
from tests.support import repository_validation_mode


ROOT = Path(__file__).resolve().parents[1]


def read_json(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class ZTJ0SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = read_json("data/derived/ztj0-processed-corpus.json")

    def test_registry_keeps_approved_witnesses_distinct(self) -> None:
        text = (ROOT / "sources/registry/zizhi-tongjian.yaml").read_text(encoding="utf-8")
        for marker in (
            "zizhi-tongjian-kanripo-wyg",
            "zizhi-tongjian-kanripo-sbck",
            "zizhi-tongjian-kaoyi-kanripo",
            "zizhi-tongjian-mulu-kanripo",
            "KR2b0007",
            "KR2b0008",
            "KR2b0010",
        ):
            self.assertIn(marker, text)
        self.assertIn("registered-but-not-independent-in-checked-tree", text)

    def test_primary_has_294_juan_and_unique_stable_blocks(self) -> None:
        primary = self.manifest["primary"]
        self.assertEqual(primary["volume_count"], 294)
        self.assertEqual(
            sorted(item["file_number"] for item in primary["records"] if item["kind"] == "volume"),
            list(range(1, 295)),
        )
        self.assertEqual(primary["chronicle_block_count"], 294)
        index = read_json("data/derived/ztj0-chronology-index.json")
        ids = [item["block_id"] for item in index["records"]]
        self.assertEqual(len(ids), 294)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(stable_id("ztj0-block", "witness", 1, 2, 3), stable_id("ztj0-block", "witness", 1, 2, 3))

    def test_source_text_and_processed_hashes_are_preserved(self) -> None:
        primary = self.manifest["primary"]
        for summary in primary["records"]:
            path = ROOT / summary["processed_path"]
            record = read_json(summary["processed_path"])
            source_text = record["source_text"].encode("utf-8")
            self.assertEqual(hashlib.sha256(source_text).hexdigest(), summary["source_sha256"])
            processed_bytes = path.read_bytes()
            self.assertEqual(hashlib.sha256(processed_bytes).hexdigest(), summary["processed_sha256"])

    def test_hu_sanxing_layer_is_distinct_from_main_text(self) -> None:
        record = read_json("content/processed/zizhi-tongjian/volumes/volume-069.json")
        block = record["chronicle_blocks"][0]
        self.assertEqual(block["chronicle_name"], "魏紀一")
        self.assertIn("<pb:KR2b0007_WYG_069-1a>", block["source_span"]["page_markers"])
        self.assertTrue(block["main_text"])
        self.assertTrue(block["annotations"])
        self.assertTrue(all(item["annotation_author"] == "胡三省" for item in block["annotations"]))
        self.assertTrue(all(item["parse_status"] == "separated_by_balanced_parentheses" for item in block["annotations"]))

    def test_chronology_surfaces_are_not_gregorian_normalized(self) -> None:
        record = read_json("content/processed/zizhi-tongjian/volumes/volume-069.json")
        block = record["chronicle_blocks"][0]
        self.assertIn("魏紀一", block["volume_chronology_heading"])
        self.assertIn("黄初元年", block["era_year_surface_candidates"])
        self.assertEqual(
            self.manifest["processing_policy"]["chronology"],
            "surface extraction only; no Gregorian normalization and no Story temporal anchors",
        )

    def test_kaoyi_is_separate_evidence_and_mulu_can_be_sparse(self) -> None:
        self.assertEqual(self.manifest["kaoyi"]["juan_count"], 30)
        kaoyi = read_json("content/processed/zizhi-tongjian/kaoyi/kaoyi-001.json")
        self.assertEqual(kaoyi["source_witness"], "zizhi-tongjian-kaoyi-kanripo")
        self.assertEqual(kaoyi["parse_status"], "source_evidence_only")
        self.assertEqual(self.manifest["mulu"]["expected_juan_count"], 30)
        self.assertGreater(self.manifest["mulu"]["sparse_volume_count"], 0)

    def test_validator_passes_in_current_mode(self) -> None:
        mode = repository_validation_mode()
        problems = validate(mode)
        self.assertEqual(problems, [], "\n".join(problems))

    def test_ztj0_does_not_create_h0_artifacts_or_change_product_ids(self) -> None:
        self.assertFalse((ROOT / "data/derived/story-temporal-anchors.json").exists())
        self.assertFalse((ROOT / "data/derived/historical-events.json").exists())
        people = read_json("data/people.json")["people"]
        self.assertEqual(len(people), 50)
        self.assertEqual([item["person_id"] for item in people], [f"person-{index:03d}" for index in range(1, 51)])


if __name__ == "__main__":
    unittest.main()
