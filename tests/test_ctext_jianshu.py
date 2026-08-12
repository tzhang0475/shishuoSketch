from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts import download_witnesses as downloader


def response(
    urn: str,
    title: str,
    *,
    fulltext: tuple[str, ...] = (),
    subsections: tuple[str, ...] = (),
) -> downloader.CTextAPIResponse:
    payload: dict[str, object] = {"id": urn, "title": title}
    if fulltext:
        payload["fulltext"] = list(fulltext)
    if subsections:
        payload["subsections"] = list(subsections)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return downloader.CTextAPIResponse(
        urn=urn,
        api_url=downloader.ctext_api_url(urn),
        response_identifier=urn,
        title=title,
        fulltext=fulltext,
        subsections=subsections,
        raw_bytes=raw,
        payload=payload,
    )


class CTextJianshuTests(unittest.TestCase):
    def test_api_url_and_error_parser_do_not_use_html(self) -> None:
        url = downloader.ctext_api_url("ctp:wb40889")
        self.assertEqual(url, "https://api.ctext.org/gettext?urn=ctp%3Awb40889")
        authenticated = downloader.ctext_api_url("ctp:wb40889", api_key="secret")
        self.assertIn("apikey=secret", authenticated)
        self.assertNotIn("secret", url)
        with self.assertRaises(downloader.CTextAPIError) as context:
            downloader.parse_ctext_gettext(
                {"error": {"code": "ERR_REQUIRES_AUTHENTICATION", "description": "auth"}},
                urn="ctp:wb40889",
            )
        self.assertEqual(context.exception.code, "ERR_REQUIRES_AUTHENTICATION")

    def test_recursive_gettext_preserves_raw_responses_and_hashes(self) -> None:
        responses = {
            "ctp:wb40889": response(
                "ctp:wb40889",
                "世說新語箋疏",
                subsections=("ctp:wb40889/xu-mu", "ctp:wb40889/juan-1"),
            ),
            "ctp:wb40889/xu-mu": response(
                "ctp:wb40889/xu-mu", "序目", fulltext=("序甲", "目乙")
            ),
            "ctp:wb40889/juan-1": response(
                "ctp:wb40889/juan-1", "卷一", fulltext=("正文丙",)
            ),
        }

        with tempfile.TemporaryDirectory() as temporary:
            lock_path, manifest = downloader.run_shishuo_jianshu(
                Path(temporary),
                api_key="test-key",
                fetcher=lambda urn: responses[urn],
            )
            self.assertIsNotNone(lock_path)
            assert lock_path is not None
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(manifest["response_count"], 3)
            self.assertEqual(manifest["total_characters"], 7)
            self.assertEqual(
                downloader.verify_ctext_lock_manifest(Path(temporary), lock_path), []
            )
            self.assertEqual(
                set(manifest["section_titles"]), {"世說新語箋疏", "序目", "卷一"}
            )
            for record in manifest["records"]:
                for file_record in record["files"]:
                    path = Path(temporary, file_record["path"])
                    self.assertTrue(path.is_file())
                    data = path.read_bytes()
                    self.assertEqual(len(data), file_record["size"])
                    self.assertEqual(
                        hashlib.sha256(data).hexdigest(), file_record["sha256"]
                    )
            text_record = next(
                record for record in manifest["records"] if record["title"] == "序目"
            )
            text_path = next(
                file_record["path"]
                for file_record in text_record["files"]
                if file_record["kind"] == "derived-text"
            )
            self.assertEqual(Path(temporary, text_path).read_text(encoding="utf-8"), "序甲\n\n目乙")
            hierarchy = json.loads(
                Path(temporary, downloader.CTEXT_JIANSHU_ROOT, "text/hierarchy.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(hierarchy["root_urn"], "ctp:wb40889")
            self.assertEqual(len(hierarchy["nodes"]), 3)
            self.assertNotIn("test-key", (lock_path).read_text(encoding="utf-8"))

    def test_authentication_failure_does_not_create_partial_local_copy(self) -> None:
        def fail(_urn: str) -> downloader.CTextAPIResponse:
            raise downloader.CTextAPIError(
                "ERR_REQUIRES_AUTHENTICATION", "authorization required"
            )

        with tempfile.TemporaryDirectory() as temporary:
            lock_path, manifest = downloader.run_shishuo_jianshu(
                Path(temporary), fetcher=fail
            )
            self.assertIsNone(lock_path)
            self.assertEqual(manifest["status"], "blocked_requires_authentication")
            self.assertFalse(
                Path(temporary, downloader.CTEXT_JIANSHU_ROOT).exists()
            )


if __name__ == "__main__":
    unittest.main()
