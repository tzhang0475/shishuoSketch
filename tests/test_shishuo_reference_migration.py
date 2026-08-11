from __future__ import annotations

import hashlib
from pathlib import Path
import unittest

import yaml

from scripts.audit_shishuo_boundaries import DEFAULT_REFERENCE as AUDIT_REFERENCE
from scripts.propose_shishuo_boundaries import DEFAULT_REFERENCE as PROPOSAL_REFERENCE
from scripts.source_paths import resolve_structural_reference


REPO_ROOT = Path(__file__).resolve().parents[1]
OLD_PATH = REPO_ROOT / "content/shishuo.txt"
NEW_PATH = REPO_ROOT / "sources/local/shishuo/reference-txt/shishuo.txt"
METADATA_PATH = NEW_PATH.with_name("metadata.yaml")
EXPECTED_SHA256 = "843c8c55956454b623a4d6f28e3e5b6ce5e7c8722aecf24822eb605914b1a205"
EXPECTED_BYTES = 824964
EXPECTED_LINES = 23992


class ShishuoReferenceMigrationTests(unittest.TestCase):
    def test_witness_was_moved_without_byte_or_line_ending_changes(self) -> None:
        self.assertFalse(OLD_PATH.exists())
        data = NEW_PATH.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), EXPECTED_SHA256)
        self.assertEqual(len(data), EXPECTED_BYTES)
        self.assertEqual(len(data.splitlines(keepends=True)), EXPECTED_LINES)
        data.decode("utf-8")
        self.assertFalse(data.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(data.count(b"\r\n"), EXPECTED_LINES)
        self.assertEqual(data.count(b"\n"), EXPECTED_LINES)

    def test_metadata_records_intrinsic_facts_and_unresolved_provenance(self) -> None:
        metadata = yaml.safe_load(METADATA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(metadata["id"], "shishuo-local-reference-txt")
        self.assertEqual(metadata["previous_id"], "shishuo-structural-reference")
        self.assertEqual(metadata["work"], "世说新语")
        self.assertEqual(metadata["role"], "structural-reference")
        self.assertEqual(metadata["edition"], "unresolved")
        self.assertEqual(metadata["source_provider"], "local repository")
        self.assertEqual(metadata["script"], "simplified-or-mixed")
        self.assertEqual(metadata["provenance_status"], "unresolved")
        self.assertEqual(metadata["text_authority"], "low")
        self.assertEqual(metadata["structure_authority"], "high")
        self.assertEqual(metadata["sha256"], EXPECTED_SHA256)
        self.assertEqual(metadata["byte_size"], EXPECTED_BYTES)
        self.assertEqual(metadata["line_count"], EXPECTED_LINES)
        self.assertEqual(metadata["encoding"], "UTF-8")
        self.assertEqual(metadata["line_ending"], "CRLF")
        notes = metadata["notes"]
        for phrase in (
            "entry-count comparison",
            "entry-boundary comparison",
            "missing-entry detection",
            "structural anomaly detection",
            "must not silently replace",
            "content/shishuo.txt",
        ):
            self.assertIn(phrase, notes)

    def test_registry_keeps_primary_and_registers_migrated_witness(self) -> None:
        registry = yaml.safe_load(
            (REPO_ROOT / "sources/registry/shishuo.yaml").read_text(encoding="utf-8")
        )
        primary = next(
            witness for witness in registry["witnesses"] if witness["role"] == "primary"
        )
        self.assertEqual(primary["id"], "shishuo-kanripo-wyg")
        self.assertEqual(primary["local_path"], "shishuoSources/shishuo")

        reference = next(
            witness
            for witness in registry["witnesses"]
            if witness["id"] == "shishuo-local-reference-txt"
        )
        self.assertEqual(reference["previous_id"], "shishuo-structural-reference")
        self.assertEqual(
            reference["local_path"],
            "sources/local/shishuo/reference-txt/shishuo.txt",
        )
        self.assertEqual(reference["provenance_status"], "unresolved")
        self.assertEqual(reference["text_authority"], "low")
        self.assertEqual(reference["structure_authority"], "high")
        self.assertNotIn("shishuo-structural-reference", {
            witness["id"] for witness in registry["witnesses"]
        })

    def test_config_and_script_defaults_resolve_the_migrated_witness(self) -> None:
        config = yaml.safe_load(
            (REPO_ROOT / "config/sources.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(
            config["sources"]["shishuo"]["structural_reference"],
            "sources/local/shishuo/reference-txt/shishuo.txt",
        )
        self.assertEqual(
            resolve_structural_reference(REPO_ROOT / "config/sources.yaml"),
            NEW_PATH,
        )
        self.assertEqual(PROPOSAL_REFERENCE.as_posix(), "sources/local/shishuo/reference-txt/shishuo.txt")
        self.assertEqual(AUDIT_REFERENCE, PROPOSAL_REFERENCE)

    def test_other_work_config_paths_remain_unchanged(self) -> None:
        config = yaml.safe_load(
            (REPO_ROOT / "config/sources.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(
            config["sources"]["jinshu"],
            {
                "primary": "shishuoSources/jinshu",
                "critical": "sources/downloads/jinshu/jinshu-jiaozhu",
                "visual_reference": "external:jinshu-wuyingdian",
            },
        )
        self.assertEqual(
            config["sources"]["sanguozhi"],
            {
                "primary": "shishuoSources/sanguozhi",
                "secondary": "sources/downloads/sanguozhi/song-edition",
                "visual_reference": "external:sanguozhi-wuyingdian",
            },
        )


if __name__ == "__main__":
    unittest.main()
