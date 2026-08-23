#!/usr/bin/env python3
"""Validate the two WREF1 Wikisource reference locks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.download_witnesses import (
    JINSHU_WIKISOURCE_PUNCTUATED_ROOT,
    JINSHU_WIKISOURCE_PUNCTUATED_WITNESS_ID,
    ZTJ_WIKISOURCE_HU_ROOT,
    ZTJ_WIKISOURCE_HU_WITNESS_ID,
    jinshu_wikisource_punctuated_volume_titles,
    verify_lock_manifest,
    zizhi_tongjian_wikisource_hu_volume_titles,
)


def _targets() -> tuple[tuple[str, str, int, Mapping[int, str]], ...]:
    return (
        (
            JINSHU_WIKISOURCE_PUNCTUATED_WITNESS_ID,
            JINSHU_WIKISOURCE_PUNCTUATED_ROOT,
            130,
            jinshu_wikisource_punctuated_volume_titles(),
        ),
        (
            ZTJ_WIKISOURCE_HU_WITNESS_ID,
            ZTJ_WIKISOURCE_HU_ROOT,
            294,
            zizhi_tongjian_wikisource_hu_volume_titles(),
        ),
    )


def _read_json(path: Path) -> Mapping[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return value if isinstance(value, Mapping) else None


def validate(root: Path = ROOT, *, mode: str = "full") -> list[str]:
    """Validate WREF1 manifest structure, and hashes in full mode."""

    errors: list[str] = []
    for witness_id, relative_root, expected_count, titles in _targets():
        lock_path = root / relative_root / "manifest.lock.json"
        if not lock_path.exists():
            errors.append(f"{witness_id}: missing lock manifest: {lock_path}")
            continue
        manifest = _read_json(lock_path)
        if manifest is None:
            errors.append(f"{witness_id}: lock manifest is not valid JSON")
            continue
        if manifest.get("witness_id") != witness_id:
            errors.append(f"{witness_id}: witness_id mismatch")
        if manifest.get("expected_juan_count") != expected_count:
            errors.append(f"{witness_id}: expected_juan_count mismatch")
        if manifest.get("coverage") != f"1-{expected_count}":
            errors.append(f"{witness_id}: coverage mismatch")
        if manifest.get("status") != "complete":
            errors.append(f"{witness_id}: status is {manifest.get('status')!r}")
        if manifest.get("missing_juans") != []:
            errors.append(f"{witness_id}: missing_juans is not empty")
        if manifest.get("duplicate_juans") != []:
            errors.append(f"{witness_id}: duplicate_juans is not empty")
        records = manifest.get("records")
        if not isinstance(records, list) or len(records) != expected_count:
            errors.append(f"{witness_id}: record count is not {expected_count}")
            continue
        numbers: list[int] = []
        for record in records:
            if not isinstance(record, Mapping):
                errors.append(f"{witness_id}: non-object record")
                continue
            number = record.get("global_juan")
            numbers.append(number if isinstance(number, int) else -1)
            if record.get("work") not in {"晉書", "資治通鑑", "資治通鑒"}:
                errors.append(f"{witness_id}: unexpected work")
            expected_title = titles.get(number)
            if expected_title is None or record.get("page_title") != expected_title:
                errors.append(f"{witness_id}: page title mismatch for juan {number}")
            for field in (
                "page_id",
                "revision_id",
                "revision_timestamp",
                "source_path",
                "source_size",
                "source_sha256",
                "raw_api_path",
                "raw_api_size",
                "raw_api_sha256",
            ):
                if record.get(field) in (None, ""):
                    errors.append(f"{witness_id}: record {number} lacks {field}")
            source_path = str(record.get("source_path") or "")
            raw_path = str(record.get("raw_api_path") or "")
            if not source_path.startswith(relative_root + "/"):
                errors.append(f"{witness_id}: source path escapes witness root")
            if not raw_path.startswith(relative_root + "/"):
                errors.append(f"{witness_id}: raw API path escapes witness root")
        if numbers != list(range(1, expected_count + 1)):
            errors.append(f"{witness_id}: global juan sequence is not complete")
        if mode == "full":
            errors.extend(verify_lock_manifest(root, lock_path))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--mode", choices=("portable", "full"), default="full")
    args = parser.parse_args()
    errors = validate(args.root.resolve(), mode=args.mode)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"WREF1 validation passed ({args.mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
