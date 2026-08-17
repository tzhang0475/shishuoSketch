#!/usr/bin/env python3
"""Deterministically export reviewed F0 feedback without touching Gold data."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from .feedback_store import (
        RAW_RELATIVE_PATH,
        REVIEWED_RELATIVE_PATH,
        REVIEWED_SCHEMA,
        REVIEWED_STATUSES,
        ROOT,
        LocalFeedbackRepository,
        reviewed_export_record,
        stable_json,
    )
except ImportError:  # direct ``python3 scripts/export_user_feedback.py``
    from feedback_store import (  # type: ignore[no-redef]
        RAW_RELATIVE_PATH,
        REVIEWED_RELATIVE_PATH,
        REVIEWED_SCHEMA,
        REVIEWED_STATUSES,
        ROOT,
        LocalFeedbackRepository,
        reviewed_export_record,
        stable_json,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_document(root: Path = ROOT) -> dict[str, Any]:
    repository = LocalFeedbackRepository(root=root)
    reviewed = [
        reviewed_export_record(record)
        for record in repository._load()  # noqa: SLF001 - export is the repository boundary
        if record.get("status") in REVIEWED_STATUSES
    ]
    reviewed.sort(key=lambda record: (str(record.get("created_at", "")), str(record.get("feedback_id", ""))))
    raw_path = root / RAW_RELATIVE_PATH
    return {
        "schema": REVIEWED_SCHEMA,
        "schema_version": 1,
        "document_kind": "user_feedback_reviewed",
        "policy": {
            "canonical_write_back": False,
            "gold_write_back": False,
            "model_training": False,
            "identifying_fields_exported": False,
        },
        "source": {
            "raw_store": RAW_RELATIVE_PATH.as_posix(),
            "raw_store_sha256": sha256_file(raw_path) if raw_path.is_file() else None,
        },
        "records": reviewed,
    }


def write_document(root: Path = ROOT) -> dict[str, Any]:
    document = build_document(root)
    path = root / REVIEWED_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(document), encoding="utf-8")
    return document


def main() -> int:
    document = write_document(ROOT)
    print(json.dumps({"status": "pass", "reviewed_records": len(document["records"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

