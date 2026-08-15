from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from scripts.validate_sgz0 import validate as validate_sgz0
from scripts.validate_w3_expansion import validate as validate_w3


def read(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class W3ExpansionTests(unittest.TestCase):
    def test_w3_and_sgz0_validators_pass(self) -> None:
        self.assertEqual(validate_w3(ROOT), [])
        self.assertEqual(validate_sgz0("portable"), [])

    def test_w3_ids_are_monotonic_and_story_union_is_canonical(self) -> None:
        wave = read("data/annotation/person-expansion-wave-3.json")
        self.assertEqual(
            [item["person_id"] for item in wave["members"]],
            [f"person-{index:03d}" for index in range(36, 51)],
        )
        stories = read("data/annotation/story-expansion-wave-3.json")
        canonical = {item["id"] for item in read("data/shishuo-corpus-index.json")["entries"]}
        self.assertTrue(set(stories["expansion_story_ids"]) <= canonical)

    def test_w3_selection_manifest_is_not_mutated_by_projection_metrics(self) -> None:
        wave = read("data/annotation/person-expansion-wave-3.json")
        self.assertTrue(all("current_sc1_story_ids" not in item for item in wave["members"]))
        self.assertTrue(all("current_sc1_occurrence_count" not in item for item in wave["members"]))
        materialization = read("data/derived/person-expansion-wave-3-materialization.json")
        self.assertTrue(all("current_sc1_story_ids" in item for item in materialization["members"]))

    def test_sanguozhi_keeps_author_layers_and_source_trace(self) -> None:
        document = read("data/derived/sgz0-processed-corpus.json")
        layers = {
            unit["layer"]
            for record in document["records"]
            for unit in record["units"]
        }
        self.assertEqual(layers, {"main_text", "pei_annotation"})
        self.assertTrue(all(unit["source_span"]["char_end_exclusive"] > unit["source_span"]["char_start"] for record in document["records"] for unit in record["units"]))
        self.assertTrue(all(record["source_sha256"] for record in document["records"]))

    def test_sanguozhi_rebuild_is_byte_deterministic_when_payload_is_available(self) -> None:
        source_dir = ROOT / "shishuoSources/sanguozhi"
        if not list(source_dir.glob("KR2a0012_*.txt")):
            self.skipTest("portable checkout has no ignored Sanguozhi payload")
        paths = [
            ROOT / "data/derived/sgz0-processed-corpus.json",
            ROOT / "sources/registry/sanguozhi-provenance.lock.json",
        ]
        paths.extend(sorted((ROOT / "content/processed/sanguozhi").glob("*.md")))
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
        subprocess.run(["python3", "scripts/build_sgz0_corpus.py"], cwd=ROOT, check=True, capture_output=True)
        after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
        self.assertEqual(before, after)

    def test少孤_homographic_alias_guard_preserves_supported_identity(self) -> None:
        mentions = [
            item for item in read("data/derived/person-resolution-effective.json")["mentions"]
            if item.get("surface") == "少孤"
        ]
        ordinary = [item for item in mentions if item.get("entry_id") == "01-dexing-026"]
        self.assertTrue(ordinary)
        self.assertTrue(all(item.get("person_id") is None for item in ordinary))
        supported = [item for item in mentions if item.get("entry_id") == "18-qiyi-010"]
        self.assertTrue(supported)
        self.assertTrue(all(item.get("person_id") == "person-032" for item in supported))

    def test_w3_scene_context_does_not_create_relation(self) -> None:
        scenes = read("data/annotation/story-scene-contexts-w3.json")["records"]
        self.assertTrue(scenes)
        self.assertTrue(all(not item.get("relation_ids") for item in scenes))


if __name__ == "__main__":
    unittest.main()
