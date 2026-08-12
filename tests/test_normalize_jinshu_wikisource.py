from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.normalize_jinshu_wikisource import (
    DEFAULT_SOURCE_ROOT,
    REPOSITORY_ROOT,
    normalize_all,
    normalize_body,
)
from tests.support import skip_if_portable_payload_missing


class JinshuWikisourceNormalizationTests(unittest.TestCase):
    def test_markup_policy_preserves_text_and_structured_metadata(self) -> None:
        raw = """<!-- presentation note -->{{SKQS header|title=晉書}}<onlyinclude><poem>\ufeff\u3000\u3000欽定四庫全書
{{SK anchor|晉書卷一}}
{{SK anchor|帝紀第一}}
王導{{SK notes|子{{SKchar|2593}}之}}字茂{{SKchar2|334}}
<史部,正史類,晉書,卷一>
正文{{YL|永和二年}}{{SKchar|2592}}
</poem></onlyinclude>{{SKQS footer|title=晉書}}{{PD-old}}"""
        body, counts, notes = normalize_body(raw)
        self.assertIn("晉書卷一", body)
        self.assertIn("帝紀第一", body)
        self.assertIn("王導", body)
        self.assertIn("正文永和二年", body)
        self.assertIn("wikisource-note", body)
        self.assertIn("{{SKchar|2593}}", body)
        self.assertIn("wikisource-SKchar2", body)
        self.assertIn("wikisource-section", body)
        self.assertNotIn("<onlyinclude>", body)
        self.assertNotIn("{{SKQS header", body)
        self.assertEqual(counts["SK notes"], 1)
        self.assertEqual(notes, [])

    def test_complete_local_lock_normalizes_exactly_130_volumes(self) -> None:
        skip_if_portable_payload_missing(
            self,
            REPOSITORY_ROOT,
            "sources/downloads/jinshu/wikisource-siku/text/volume-001.txt",
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "normalized"
            manifest_path = Path(temporary) / "normalization-manifest.lock.json"
            result = normalize_all(
                source_root=DEFAULT_SOURCE_ROOT,
                output_dir=output,
                manifest_path=manifest_path,
                root=REPOSITORY_ROOT,
            )
            self.assertEqual(result["volume_count"], 130)
            self.assertEqual([record["volume"] for record in result["volumes"]], list(range(1, 131)))
            for volume in (1, 65, 67, 79, 80, 130):
                record = result["volumes"][volume - 1]
                path = output / f"volume-{volume:03d}.md"
                data = path.read_bytes()
                self.assertEqual(record["normalized_output_sha256"], hashlib.sha256(data).hexdigest())
                self.assertEqual(record["source_witness"], "jinshu-wikisource-siku")
                self.assertIn("source_page_title", path.read_text(encoding="utf-8"))
            self.assertEqual(
                json.loads(manifest_path.read_text(encoding="utf-8"))["volume_count"],
                130,
            )


if __name__ == "__main__":
    unittest.main()
