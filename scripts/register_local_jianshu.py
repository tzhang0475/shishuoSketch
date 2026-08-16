#!/usr/bin/env python3
"""Register the user-provided local Jianshu EPUB/PDF pair.

This stage records only deterministic local metadata.  It never copies,
renames, edits, or adds the ignored binary payloads to Git.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

from s1_jianshu_common import (
    EPUB_ID,
    EPUB_SOURCE_DIR,
    PDF_ID,
    PDF_SOURCE_DIR,
    REGISTRATION_PATH,
    SOURCE_FAMILY,
    discover_payloads,
    epub_layout,
    hash_value,
    primary_witness_snapshot,
    pdf_metadata,
    protected_s1_input_hashes,
    relative_path,
    sha256_path,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]


def write_text(relative: Path, text: str) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def register() -> dict:
    payloads = discover_payloads()
    epub_path = payloads["epub"]
    pdf_path = payloads["pdf"]
    layout = epub_layout(epub_path)
    pdf = pdf_metadata(pdf_path)
    epub_stat = epub_path.stat()
    pdf_stat = pdf_path.stat()

    epub_payload = {
        "source_family": SOURCE_FAMILY,
        "source_id": EPUB_ID,
        "work": "世說新語",
        "role": "scholarly-reference-machine",
        "authority_scope": ["machine parsing", "search", "structure", "historical commentary"],
        "local_path": relative_path(epub_path),
        "filename": epub_path.name,
        "format": "epub",
        "byte_size": epub_stat.st_size,
        "sha256": sha256_path(epub_path),
        "acquisition": "user_provided_local",
        "container_valid": True,
        "container_rootfile": layout["container_rootfile"],
        "spine_document_count": layout["spine_document_count"],
        "internal_title": (layout.get("metadata", {}).get("title") or [None])[0],
        "internal_creator": (layout.get("metadata", {}).get("creator") or [None])[0],
        "internal_date": (layout.get("metadata", {}).get("date") or [None])[0],
        "internal_publisher": (layout.get("metadata", {}).get("publisher") or [None])[0],
        "internal_metadata": layout.get("metadata", {}),
        "notes": "A local scholarly working reference; not the primary Shishuo textual witness.",
    }
    pdf_payload = {
        "source_family": SOURCE_FAMILY,
        "source_id": PDF_ID,
        "work": "世說新語",
        "role": "scholarly-reference-visual",
        "authority_scope": ["page verification", "special glyph fallback", "ambiguous structure"],
        "local_path": relative_path(pdf_path),
        "filename": pdf_path.name,
        "format": "pdf",
        "byte_size": pdf_stat.st_size,
        "sha256": sha256_path(pdf_path),
        "acquisition": "user_provided_local",
        "page_count": pdf.get("page_count"),
        "page_count_method": pdf.get("page_count_method"),
        "has_text_layer": pdf.get("has_text_layer"),
        "text_layer_probe": pdf.get("text_layer_probe"),
        "notes": "Selective visual/page fallback; no OCR is used by S1.",
    }

    common_manifest = (
        "schema: 1\n"
        f"source_family: {SOURCE_FAMILY}\n"
        "work: \"世說新語\"\n"
        "edition: \"世說新語箋疏\"\n"
        "source_provider: \"user-provided local scholarly reference\"\n"
        "acquisition: user_provided_local\n"
        "payload_policy: \"Binary payload remains ignored; deterministic metadata and lock files are tracked.\"\n"
    )
    write_text(
        EPUB_SOURCE_DIR / "README.md",
        """# 世說新語箋疏 — local EPUB

This user-provided EPUB is registered as the machine-readable member of the
`shishuo-jianshu-yujiaxi-local` scholarly-reference family.  It is used for
deterministic structure, search, punctuation/segmentation review, and
historical candidate extraction.  It is not the primary Shishuo witness.

The binary payload is ignored by Git; `metadata.yaml`, `manifest.yaml`, and
`manifest.lock.json` record its local identity and digest.
""",
    )
    write_text(
        PDF_SOURCE_DIR / "README.md",
        """# 世說新語箋疏 — local PDF

This user-provided PDF is the visual/page fallback for the same
`shishuo-jianshu-yujiaxi-local` scholarly-reference family as the EPUB.  It is
used selectively for difficult glyphs, ambiguous structure, and high-value
verification.  It is not a second independent historical source and does not
replace the primary Shishuo witness.

The binary payload is ignored by Git; `metadata.yaml`, `manifest.yaml`, and
`manifest.lock.json` record its local identity and digest.
""",
    )
    write_text(
        EPUB_SOURCE_DIR / "metadata.yaml",
        common_manifest
        + f"source_id: {EPUB_ID}\nrole: scholarly-reference-machine\nformat: epub\nlocal_path: \"{relative_path(epub_path)}\"\n",
    )
    write_text(
        PDF_SOURCE_DIR / "metadata.yaml",
        common_manifest
        + f"source_id: {PDF_ID}\nrole: scholarly-reference-visual\nformat: pdf\nlocal_path: \"{relative_path(pdf_path)}\"\n",
    )
    write_text(
        EPUB_SOURCE_DIR / "manifest.yaml",
        common_manifest
        + f"source_id: {EPUB_ID}\npayload_path: \"{relative_path(epub_path)}\"\n",
    )
    write_text(
        PDF_SOURCE_DIR / "manifest.yaml",
        common_manifest
        + f"source_id: {PDF_ID}\npayload_path: \"{relative_path(pdf_path)}\"\n",
    )

    epub_lock = {
        "schema": 1,
        "source_family": SOURCE_FAMILY,
        "source_id": EPUB_ID,
        "status": "verified-existing",
        "payload": epub_payload,
        "epub_layout_sha256": hash_value(layout),
        "protected_input_hashes": protected_s1_input_hashes(),
    }
    pdf_lock = {
        "schema": 1,
        "source_family": SOURCE_FAMILY,
        "source_id": PDF_ID,
        "status": "verified-existing",
        "payload": pdf_payload,
        "protected_input_hashes": protected_s1_input_hashes(),
    }
    primary_witness = primary_witness_snapshot()
    write_text(EPUB_SOURCE_DIR / "manifest.lock.json", json.dumps(epub_lock, ensure_ascii=False, indent=2, sort_keys=True))
    write_text(PDF_SOURCE_DIR / "manifest.lock.json", json.dumps(pdf_lock, ensure_ascii=False, indent=2, sort_keys=True))

    registration = {
        "schema": "s1-local-jianshu-registration-1",
        "stage": "S1.1",
        "source_family": SOURCE_FAMILY,
        "primary_shishuo_witness": primary_witness,
        "primary_shishuo_witness_unchanged": primary_witness["status"] == "verified",
        "external_ctext_registration_retained": True,
        "payloads": [epub_payload, pdf_payload],
        "epub_layout": layout,
        "pdf_probe": pdf,
        "protected_input_hashes": protected_s1_input_hashes(),
    }
    write_json(REGISTRATION_PATH, registration)
    return registration


def main() -> int:
    try:
        result = register()
    except Exception as exc:  # clear command-line failure for ambiguous inputs
        print(f"S1 source registration failed: {exc}", file=sys.stderr)
        return 2
    for payload in result["payloads"]:
        print(f"{payload['source_id']}: {payload['byte_size']} bytes {payload['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
