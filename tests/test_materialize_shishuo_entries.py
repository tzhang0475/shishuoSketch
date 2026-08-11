from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from scripts.materialize_shishuo_entries import (
    ENTRY_ROOT,
    INDEX_PATH,
    build_index,
    materialize_missing,
    validate_corpus,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def directory_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(child for child in path.rglob("*") if child.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


class ShishuoMaterializationTests(unittest.TestCase):
    def test_frozen_corpus_validates_globally(self) -> None:
        validation = validate_corpus()
        self.assertEqual(validation["chapter_count"], 36)
        self.assertEqual(validation["entry_count"], 1130)
        self.assertEqual(validation["supplement_count"], 6)
        self.assertEqual(len(validation["entries"]), 1130)
        self.assertEqual(
            [record["global_ordinal"] for record in validation["entries"]],
            list(range(1, 1131)),
        )

    def test_index_matches_validation_and_has_all_chapter_directories(self) -> None:
        validation = validate_corpus()
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        self.assertEqual(index, build_index(validation))
        self.assertEqual(
            {path.name for path in ENTRY_ROOT.iterdir() if path.is_dir()},
            {record["id"] for record in validation["chapters"]},
        )
        self.assertEqual(
            sum(1 for path in ENTRY_ROOT.rglob("entry-*.md") if path.is_file()),
            1130,
        )

    def test_existing_materialized_chapters_are_not_rewritten(self) -> None:
        expected = {
            "05-fangzheng": "a9d9b9e61970daabf0aaf312931045c69f7f7a675a0a11df9b47ed9b6cd96215",
            "06-yaliang": "386f7115759c328c24ba72f7c35e732b705a38a6a3a8c4446345312b382e7c88",
            "08-shangyu": "c5f46f440e40dfa5bb2d991bff594725e1b970f9e6a1a18aa13502cb38528da2",
            "18-qiyi": "cf418428b7829412195c0c6a38a8aa74fee477c2d8dcc3daa62f580be043b8e2",
            "19-xianyuan": "31e22bde8ab771a2979ad16946fac31bbdd4f2953adb101334404ca8dda10afa",
            "25-paidiao": "60982d296e7e2ad94bb88cb6664f4fafff8901e82f0f12902b47dd59ca40cff1",
        }
        # The six directories are the reviewed/golden outputs.  A materialize
        # pass may create missing chapters, but must never rewrite these.
        before = {name: directory_hash(ENTRY_ROOT / name) for name in expected}
        self.assertEqual(materialize_missing(), [])
        after = {name: directory_hash(ENTRY_ROOT / name) for name in expected}
        self.assertEqual(before, after)
        self.assertEqual(before, expected)

    def test_six_supplement_provenance_records_are_in_index(self) -> None:
        validation = validate_corpus()
        supplements = {
            record["id"]: record
            for record in validation["entries"]
            if record["primary_witness_status"] == "gap"
        }
        self.assertEqual(
            set(supplements),
            {
                "05-fangzheng-014",
                "08-shangyu-084",
                "08-shangyu-085",
                "18-qiyi-002",
                "18-qiyi-011",
                "19-xianyuan-005",
            },
        )
        for record in supplements.values():
            self.assertEqual(record["supplement"]["witness_id"], "shishuo-wikisource-sbck")
            self.assertEqual(record["supplement"]["reason"], "kanripo_digitization_gap")
            self.assertTrue(record["supplement"]["source_url"])


if __name__ == "__main__":
    unittest.main()
