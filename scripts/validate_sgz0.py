#!/usr/bin/env python3
"""Validate the SGZ0 processed Sanguozhi corpus and provenance lock."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path("data/derived/sgz0-processed-corpus.json")
LOCK = Path("sources/registry/sanguozhi-provenance.lock.json")


def read(path: Path) -> Any:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate(mode: str = "portable") -> list[str]:
    errors: list[str] = []
    try:
        manifest = read(MANIFEST)
        lock = read(LOCK)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"SGZ0 artifact cannot be read: {exc}"]
    if manifest.get("stage") != "sgz0-sanguozhi-processed-corpus":
        errors.append("SGZ0 manifest stage is invalid")
    if lock.get("witness_id") != manifest.get("primary_witness"):
        errors.append("SGZ0 provenance lock witness does not match manifest")
    lock_by_path = {str(item.get("source_path")): item for item in lock.get("records", [])}
    seen_source: set[str] = set()
    for record in manifest.get("records", []):
        source_path = str(record.get("source_path", ""))
        processed_path = ROOT / str(record.get("processed_path", ""))
        source_hash = str(record.get("source_sha256", ""))
        if source_path in seen_source:
            errors.append(f"duplicate SGZ0 source path: {source_path}")
        seen_source.add(source_path)
        if not processed_path.is_file():
            errors.append(f"missing SGZ0 processed file: {processed_path}")
        elif sha256(processed_path) != record.get("processed_sha256"):
            errors.append(f"processed SGZ0 hash mismatch: {processed_path}")
        lock_record = lock_by_path.get(source_path)
        if lock_record is None:
            errors.append(f"source path is absent from SGZ0 provenance lock: {source_path}")
        elif lock_record.get("source_sha256") != source_hash:
            errors.append(f"source SHA mismatch between manifest and lock: {source_path}")
        source_file = ROOT / source_path
        if source_file.is_file():
            if sha256(source_file) != source_hash:
                errors.append(f"upstream Sanguozhi source hash mismatch: {source_path}")
        elif mode == "full":
            errors.append(f"full SGZ0 validation requires source payload: {source_path}")
        units = record.get("units", [])
        last_end = -1
        layers: set[str] = set()
        for unit in units:
            layer = unit.get("layer")
            if layer not in {"main_text", "pei_annotation"}:
                errors.append(f"invalid SGZ0 unit layer: {unit.get('unit_id')}")
            layers.add(str(layer))
            span = unit.get("source_span", {})
            start = span.get("char_start")
            end = span.get("char_end_exclusive")
            if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
                errors.append(f"invalid SGZ0 source span: {unit.get('unit_id')}")
            elif start < last_end:
                errors.append(f"overlapping SGZ0 source spans: {unit.get('unit_id')}")
            else:
                last_end = end
            if not isinstance(unit.get("raw_text"), str) or not isinstance(unit.get("text"), str):
                errors.append(f"SGZ0 unit lacks raw/text projection: {unit.get('unit_id')}")
            if layer == "main_text" and unit.get("author_layer") != "陳壽":
                errors.append(f"SGZ0 main unit author layer is not 陈寿: {unit.get('unit_id')}")
            if layer == "pei_annotation" and unit.get("author_layer") != "裴松之":
                errors.append(f"SGZ0 Pei unit author layer is not 裴松之: {unit.get('unit_id')}")
        counts = record.get("layer_counts", {})
        if counts.get("main_text") != sum(unit.get("layer") == "main_text" for unit in units):
            errors.append(f"SGZ0 main unit count mismatch: {source_path}")
        if counts.get("pei_annotation") != sum(unit.get("layer") == "pei_annotation" for unit in units):
            errors.append(f"SGZ0 Pei unit count mismatch: {source_path}")
    if manifest.get("volume_count") != len([item for item in manifest.get("records", []) if item.get("kind") == "volume"]):
        errors.append("SGZ0 volume_count mismatch")
    if manifest.get("main_text_unit_count") != sum(item.get("layer_counts", {}).get("main_text", 0) for item in manifest.get("records", [])):
        errors.append("SGZ0 main_text_unit_count mismatch")
    if manifest.get("pei_annotation_unit_count") != sum(item.get("layer_counts", {}).get("pei_annotation", 0) for item in manifest.get("records", [])):
        errors.append("SGZ0 pei_annotation_unit_count mismatch")
    return sorted(set(errors))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("full", "portable"), default="portable")
    args = parser.parse_args()
    problems = validate(args.mode)
    if problems:
        print("SGZ0 validation failed:")
        print("\n".join(f"- {item}" for item in problems))
        raise SystemExit(1)
    print("SGZ0 validation passed")
