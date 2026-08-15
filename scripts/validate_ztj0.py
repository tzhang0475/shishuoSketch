#!/usr/bin/env python3
"""Validate ZTJ0 acquisition locks, processed records, and indexes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/derived/ztj0-processed-corpus.json"
CHRONOLOGY_INDEX = ROOT / "data/derived/ztj0-chronology-index.json"
KAOYI_INDEX = ROOT / "data/derived/ztj0-kaoyi-index.json"
WEIJIN_RANGE = ROOT / "data/derived/ztj0-weijin-range.json"
REGISTRY = ROOT / "sources/registry/zizhi-tongjian.yaml"

LOCKS = {
    "kanripo-wyg": ROOT / "sources/downloads/zizhi-tongjian/kanripo-wyg/manifest.lock.json",
    "kaoyi-kanripo": ROOT / "sources/downloads/zizhi-tongjian/kaoyi-kanripo/manifest.lock.json",
    "mulu-kanripo": ROOT / "sources/downloads/zizhi-tongjian/mulu-kanripo/manifest.lock.json",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check_hash(path: Path, expected: str, errors: list[str], label: str) -> None:
    if not path.is_file():
        errors.append(f"missing {label}: {path.relative_to(ROOT)}")
        return
    actual = sha256_file(path)
    if actual != expected:
        errors.append(f"{label} hash mismatch: {path.relative_to(ROOT)}")


def validate_lock(slug: str, errors: list[str], mode: str) -> dict[str, Any] | None:
    lock_path = LOCKS[slug]
    if not lock_path.is_file():
        errors.append(f"missing source lock: {lock_path.relative_to(ROOT)}")
        return None
    try:
        lock = read_json(lock_path)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid source lock {slug}: {exc}")
        return None
    records = lock.get("records", [])
    source_paths: set[str] = set()
    for record in records:
        source_path = str(record.get("source_path", ""))
        if source_path in source_paths:
            errors.append(f"duplicate locked source path: {source_path}")
        source_paths.add(source_path)
        raw_path = ROOT / source_path
        if raw_path.is_file():
            if sha256_file(raw_path) != record.get("source_sha256"):
                errors.append(f"source payload hash mismatch: {source_path}")
            if raw_path.stat().st_size != record.get("source_bytes"):
                errors.append(f"source payload byte-size mismatch: {source_path}")
        elif mode == "full":
            errors.append(f"full validation requires source payload: {source_path}")
    return lock


def lock_inventory_hash(lock: dict[str, Any]) -> str:
    inventory = [
        {
            "source_file": item.get("source_file"),
            "source_bytes": item.get("source_bytes"),
            "source_sha256": item.get("source_sha256"),
            "source_path": item.get("source_path"),
        }
        for item in lock.get("records", [])
    ]
    inventory.sort(key=lambda item: str(item["source_file"]))
    return sha256_bytes(json.dumps(inventory, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def validate_registry(errors: list[str]) -> None:
    if not REGISTRY.is_file():
        errors.append("missing ZTJ0 source registry")
        return
    text = REGISTRY.read_text(encoding="utf-8")
    required = (
        "zizhi-tongjian-kanripo-wyg",
        "zizhi-tongjian-kanripo-sbck",
        "zizhi-tongjian-kaoyi-kanripo",
        "zizhi-tongjian-mulu-kanripo",
        "KR2b0007",
        "KR2b0008",
        "KR2b0010",
        "文淵閣四庫全書 / WYG",
        "四部叢刊 / SBCK",
    )
    for marker in required:
        if marker not in text:
            errors.append(f"ZTJ0 registry missing required marker: {marker}")
    if "zizhi-tongjian-kanripo-wyg" in text and "zizhi-tongjian-kanripo-sbck" in text:
        # The registry must keep these witness identities distinct even though
        # the inspected Kanripo tree exposes only one file family.
        wyg_section = text.split("id: zizhi-tongjian-kanripo-wyg", 1)[1].split("\n  - id:", 1)[0]
        sbck_section = text.split("id: zizhi-tongjian-kanripo-sbck", 1)[1].split("\n  - id:", 1)[0]
        if wyg_section == sbck_section:
            errors.append("WYG and SBCK registry sections were collapsed")


def validate_primary(manifest: dict[str, Any], locks: dict[str, Any], errors: list[str]) -> None:
    primary = manifest.get("primary", {})
    if primary.get("volume_count") != 294:
        errors.append(f"ZTJ0 primary volume count is not 294: {primary.get('volume_count')}")
    records = primary.get("records", [])
    volume_records = [item for item in records if item.get("kind") == "volume"]
    numbers = sorted(int(item.get("file_number")) for item in volume_records)
    if numbers != list(range(1, 295)):
        errors.append("ZTJ0 primary does not cover exactly juan 1..294")
    if sum(item.get("kind") == "unassigned_source_stub" for item in records) != 1:
        errors.append("ZTJ0 primary extra-file handling is not exactly one unassigned stub")
    lock_by_path = {item.get("source_path"): item for item in locks["kanripo-wyg"].get("records", [])}
    block_ids: set[str] = set()
    observed_blocks = 0
    for summary in records:
        processed_path = ROOT / str(summary.get("processed_path", ""))
        check_hash(processed_path, str(summary.get("processed_sha256", "")), errors, "processed primary record")
        if not processed_path.is_file():
            continue
        try:
            record = read_json(processed_path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid processed primary record {processed_path}: {exc}")
            continue
        source_text = record.get("source_text")
        if not isinstance(source_text, str):
            errors.append(f"processed primary record has no source_text: {processed_path}")
            continue
        source_hash = sha256_bytes(source_text.encode("utf-8"))
        if source_hash != summary.get("source_sha256"):
            errors.append(f"processed source_text does not preserve source bytes: {processed_path}")
        lock_record = lock_by_path.get(summary.get("source_path"))
        if lock_record is None:
            errors.append(f"primary processed source is absent from lock: {summary.get('source_path')}")
        elif lock_record.get("source_sha256") != summary.get("source_sha256"):
            errors.append(f"primary processed/lock source hash mismatch: {summary.get('source_path')}")
        if summary.get("kind") == "volume":
            if record.get("layer_status", {}).get("status") != "reliable_balanced_parentheses_one_level":
                errors.append(f"primary Hu segmentation is not reliable: {processed_path}")
            blocks = record.get("chronicle_blocks", [])
            if len(blocks) != 1:
                errors.append(f"primary volume does not have one observed chronicle block: {processed_path}")
            observed_blocks += len(blocks)
            last_annotation_end = -1
            for block in blocks:
                block_id = block.get("block_id")
                if block_id in block_ids:
                    errors.append(f"duplicate chronology block ID: {block_id}")
                block_ids.add(str(block_id))
                span = block.get("source_span", {})
                if not isinstance(span.get("char_start"), int) or not isinstance(span.get("char_end_exclusive"), int):
                    errors.append(f"chronology block lacks source span: {block_id}")
                elif not (0 <= span["char_start"] < span["char_end_exclusive"] <= len(source_text)):
                    errors.append(f"chronology block source span is outside source: {block_id}")
                if not block.get("chronicle_name"):
                    errors.append(f"chronology block lacks observed chronicle heading: {block_id}")
                for annotation in block.get("annotations", []):
                    if annotation.get("annotation_author") != "胡三省":
                        errors.append(f"primary annotation is not Hu Sanxing: {annotation.get('annotation_id')}")
                    annotation_span = annotation.get("source_span", {})
                    start = annotation_span.get("char_start")
                    end = annotation_span.get("char_end_exclusive")
                    if not isinstance(start, int) or not isinstance(end, int) or not (0 <= start < end <= len(source_text)):
                        errors.append(f"invalid Hu annotation source span: {annotation.get('annotation_id')}")
                    elif start < last_annotation_end:
                        errors.append(f"overlapping Hu annotation spans: {annotation.get('annotation_id')}")
                    else:
                        last_annotation_end = end
                    if annotation.get("parse_status") != "separated_by_balanced_parentheses":
                        errors.append(f"Hu annotation was silently promoted from uncertain syntax: {annotation.get('annotation_id')}")
    if observed_blocks != primary.get("chronicle_block_count"):
        errors.append("primary chronology block count mismatch")
    if observed_blocks != 294:
        errors.append(f"expected one chronology block per juan, observed {observed_blocks}")


def validate_kaoyi(manifest: dict[str, Any], lock: dict[str, Any], errors: list[str]) -> None:
    summary = manifest.get("kaoyi", {})
    if summary.get("juan_count") != 30 or summary.get("block_count") != 30:
        errors.append("Kaoyi does not contain the expected 30 source blocks")
    lock_by_path = {item.get("source_path"): item for item in lock.get("records", [])}
    for item in summary.get("records", []):
        path = ROOT / str(item.get("processed_path", ""))
        check_hash(path, str(item.get("processed_sha256", "")), errors, "processed Kaoyi record")
        if not path.is_file():
            continue
        record = read_json(path)
        source_text = record.get("source_text")
        if not isinstance(source_text, str) or sha256_bytes(source_text.encode("utf-8")) != item.get("source_sha256"):
            errors.append(f"Kaoyi source_text is not byte-preserving: {path}")
        if record.get("parse_status") != "source_evidence_only":
            errors.append(f"Kaoyi record is not evidence-only: {path}")
        if item.get("source_path") not in lock_by_path:
            errors.append(f"Kaoyi record is absent from lock: {item.get('source_path')}")


def validate_mulu(manifest: dict[str, Any], errors: list[str]) -> None:
    summary = manifest.get("mulu", {})
    if summary.get("file_count") != 27:
        errors.append(f"Mulu acquired file count changed unexpectedly: {summary.get('file_count')}")
    if summary.get("expected_juan_count") != 30:
        errors.append("Mulu expected juan metadata is missing")
    if summary.get("sparse_volume_count", 0) < 1:
        errors.append("Mulu sparse coverage was not recorded")
    for item in summary.get("records", []):
        path = ROOT / str(item.get("processed_path", ""))
        check_hash(path, str(item.get("processed_sha256", "")), errors, "processed Mulu record")
        if path.is_file():
            record = read_json(path)
            if record.get("coverage_status") not in {"usable_machine_text", "sparse_or_page_marker_only"}:
                errors.append(f"Mulu coverage status is invalid: {path}")


def validate_indexes(manifest: dict[str, Any], errors: list[str]) -> None:
    for key, path, field in (
        ("chronology_index", CHRONOLOGY_INDEX, "record_count"),
        ("kaoyi_index", KAOYI_INDEX, "record_count"),
        ("weijin_range", WEIJIN_RANGE, None),
    ):
        expected = manifest.get(key, {}).get("sha256")
        if not isinstance(expected, str):
            errors.append(f"ZTJ0 manifest lacks {key} hash")
        else:
            check_hash(path, expected, errors, f"{key} artifact")
        if path.is_file():
            try:
                data = read_json(path)
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"invalid {key}: {exc}")
                continue
            if field and data.get(field) != manifest.get(key, {}).get(field):
                errors.append(f"{key} record count mismatch")
    if CHRONOLOGY_INDEX.is_file():
        index = read_json(CHRONOLOGY_INDEX)
        records = index.get("records", [])
        if len(records) != 294:
            errors.append("chronology index does not contain 294 blocks")
        if len({item.get("block_id") for item in records}) != len(records):
            errors.append("chronology index block IDs are not unique")
        for item in records:
            if not item.get("source_span") or not item.get("source_file"):
                errors.append(f"chronology index record lacks provenance: {item.get('block_id')}")


def validate_acquisition(manifest: dict[str, Any], locks: dict[str, Any], errors: list[str]) -> None:
    acquisition = manifest.get("acquisition", {})
    for key, slug in (("primary", "kanripo-wyg"), ("kaoyi", "kaoyi-kanripo"), ("mulu", "mulu-kanripo")):
        summary = acquisition.get(key, {})
        lock = locks.get(slug) or {}
        if summary.get("upstream_commit") != lock.get("upstream_commit"):
            errors.append(f"ZTJ0 acquisition commit mismatch: {key}")
        if summary.get("source_file_count") != len(lock.get("records", [])):
            errors.append(f"ZTJ0 acquisition file count mismatch: {key}")
        if summary.get("source_inventory_sha256") != lock_inventory_hash(lock):
            errors.append(f"ZTJ0 acquisition inventory hash mismatch: {key}")


def validate(mode: str = "portable") -> list[str]:
    errors: list[str] = []
    validate_registry(errors)
    try:
        manifest = read_json(MANIFEST)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"ZTJ0 manifest cannot be read: {exc}"]
    if manifest.get("stage") != "ztj0-zizhi-tongjian-processed-corpus":
        errors.append("ZTJ0 manifest stage is invalid")
    locks = {slug: validate_lock(slug, errors, mode) for slug in LOCKS}
    if any(lock is None for lock in locks.values()):
        return sorted(set(errors))
    validate_acquisition(manifest, locks, errors)
    validate_primary(manifest, locks, errors)
    validate_kaoyi(manifest, locks["kaoyi-kanripo"], errors)
    validate_mulu(manifest, errors)
    validate_indexes(manifest, errors)
    # ZTJ0 is explicitly source infrastructure, not a historical-event or
    # Story-temporal mutation stage.
    if manifest.get("processing_policy", {}).get("historical_event_creation") != "disabled":
        errors.append("ZTJ0 historical-event creation is not disabled")
    return sorted(set(errors))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("full", "portable"), default="portable")
    args = parser.parse_args()
    problems = validate(args.mode)
    if problems:
        print("ZTJ0 validation failed:")
        print("\n".join(f"- {item}" for item in problems))
        raise SystemExit(1)
    print("ZTJ0 validation passed")
