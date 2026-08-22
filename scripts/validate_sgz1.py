#!/usr/bin/env python3
"""Validate the complete SGZ1 Sanguozhi source/evidence projection."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

try:
    import yaml
except ImportError:  # pragma: no cover - repository validators normally have PyYAML
    yaml = None  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = Path("sources/registry/sanguozhi.yaml")
CONFIG_PATH = Path("config/sources.yaml")
SGZ0_PATH = Path("data/derived/sgz0-processed-corpus.json")
SOURCE_MANIFEST_PATH = Path("sources/downloads/sanguozhi/wikisource/manifest.lock.json")
SGZ1_PATH = Path("data/derived/sgz1-sanguozhi-complete-corpus.json")
EXPECTED_SECTIONS = {
    "魏書": (1, 30),
    "蜀書": (31, 45),
    "吳書": (46, 65),
}
ALLOWED_LAYERS = {"metadata", "main_text", "pei_annotation", "unparsed"}
PROHIBITED_TOP_LEVEL_KEYS = {
    "persons",
    "relations",
    "facts",
    "events",
    "person_story",
    "mentions",
    "canonical_facts",
}


def read_json(path: Path) -> Any:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _registry() -> tuple[Mapping[str, Any], list[str]]:
    if yaml is None:
        return {}, ["PyYAML is required to validate the SGZ1 source registry"]
    try:
        registry = yaml.safe_load((ROOT / REGISTRY_PATH).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return {}, [f"SGZ1 registry cannot be read: {exc}"]
    if not isinstance(registry, Mapping):
        return {}, ["SGZ1 registry is not a mapping"]
    return registry, []


def _safe_relative(root: Path, relative: str) -> Path | None:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        return None
    return root / path


def _validate_source_manifest(mode: str) -> tuple[dict[int, Mapping[str, Any]], list[str]]:
    errors: list[str] = []
    try:
        manifest = read_json(SOURCE_MANIFEST_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"SGZ1 source manifest cannot be read: {exc}"]
    if manifest.get("witness_id") != "sanguozhi-wikisource":
        errors.append("SGZ1 source manifest witness id is invalid")
    if manifest.get("status") != "complete":
        errors.append("SGZ1 source manifest is not complete")
    if manifest.get("coverage") != "1-65":
        errors.append("SGZ1 source manifest coverage is not 1-65")
    records = manifest.get("records")
    if not isinstance(records, list):
        return {}, errors + ["SGZ1 source manifest records are not a list"]
    by_juan: dict[int, Mapping[str, Any]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            errors.append("SGZ1 source manifest contains a non-object record")
            continue
        try:
            juan = int(record.get("global_juan"))
        except (TypeError, ValueError):
            errors.append("SGZ1 source record has no integer global_juan")
            continue
        if juan in by_juan:
            errors.append(f"duplicate SGZ1 source global juan: {juan}")
        by_juan[juan] = record
        if record.get("source_revision") is None or record.get("revision_id") is None:
            errors.append(f"SGZ1 source revision is unresolved: juan {juan}")
        source_path = str(record.get("source_path", ""))
        source_file = _safe_relative(ROOT, source_path)
        if source_file is None:
            errors.append(f"SGZ1 source path is unsafe: {source_path}")
        elif source_file.is_file():
            if sha256(source_file) != record.get("source_sha256"):
                errors.append(f"SGZ1 source SHA-256 mismatch: {source_path}")
        elif mode == "full":
            errors.append(f"full SGZ1 validation requires source payload: {source_path}")
    if set(by_juan) != set(range(1, 66)):
        errors.append("SGZ1 source manifest does not cover exactly global juan 1-65")
    for auxiliary in manifest.get("auxiliary_files", []):
        if not isinstance(auxiliary, Mapping):
            errors.append("SGZ1 auxiliary file record is not an object")
            continue
        path = _safe_relative(ROOT, str(auxiliary.get("path", "")))
        if path is None:
            errors.append(f"SGZ1 auxiliary path is unsafe: {auxiliary.get('path')}")
        elif path.is_file():
            if sha256(path) != auxiliary.get("sha256"):
                errors.append(f"SGZ1 auxiliary SHA-256 mismatch: {path}")
        elif mode == "full":
            errors.append(f"full SGZ1 validation requires auxiliary payload: {path}")
    return by_juan, errors


def _validate_units(
    record: Mapping[str, Any],
    *,
    source_content: str | None,
) -> list[str]:
    errors: list[str] = []
    units = record.get("units")
    if not isinstance(units, list) or not units:
        return [f"SGZ1 juan {record.get('global_juan')} has no units"]
    seen_ids: set[str] = set()
    last_end = 0
    reconstructed: list[str] = []
    counts = {layer: 0 for layer in ALLOWED_LAYERS}
    for unit in units:
        if not isinstance(unit, Mapping):
            errors.append("SGZ1 unit is not an object")
            continue
        unit_id = str(unit.get("unit_id", ""))
        if not unit_id or unit_id in seen_ids:
            errors.append(f"duplicate/empty SGZ1 unit id: {unit_id}")
        seen_ids.add(unit_id)
        layer = unit.get("layer")
        if layer not in ALLOWED_LAYERS:
            errors.append(f"invalid SGZ1 unit layer: {unit_id}")
        else:
            counts[layer] += 1
        span = unit.get("source_span", {})
        start = span.get("char_start") if isinstance(span, Mapping) else None
        end = span.get("char_end_exclusive") if isinstance(span, Mapping) else None
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
            errors.append(f"invalid SGZ1 unit span: {unit_id}")
            continue
        if start != last_end:
            errors.append(f"SGZ1 unit spans are not contiguous: {unit_id}")
        last_end = end
        raw = unit.get("raw_text")
        text = unit.get("text")
        if not isinstance(raw, str) or not isinstance(text, str):
            errors.append(f"SGZ1 unit lacks raw/text projection: {unit_id}")
        else:
            reconstructed.append(raw)
        author = unit.get("author_layer")
        if layer == "main_text" and author != "陳壽":
            errors.append(f"SGZ1 main unit author layer is invalid: {unit_id}")
        if layer == "pei_annotation" and author != "裴松之":
            errors.append(f"SGZ1 Pei unit author layer is invalid: {unit_id}")
        if layer in {"metadata", "unparsed"} and author is not None:
            errors.append(f"SGZ1 unresolved/metadata unit has an author layer: {unit_id}")
    if record.get("layer_counts") != {key: counts[key] for key in ("main_text", "pei_annotation", "metadata", "unparsed")}:
        errors.append(f"SGZ1 layer count mismatch: juan {record.get('global_juan')}")
    if source_content is not None:
        if last_end != len(source_content):
            errors.append(f"SGZ1 unit spans do not cover source: juan {record.get('global_juan')}")
        if "".join(reconstructed) != source_content:
            errors.append(f"SGZ1 raw unit reconstruction differs from source: juan {record.get('global_juan')}")
    return errors


def validate(mode: str = "portable") -> list[str]:
    errors: list[str] = []
    registry, registry_errors = _registry()
    errors.extend(registry_errors)
    witnesses = {
        str(item.get("id")): item
        for item in registry.get("witnesses", [])
        if isinstance(item, Mapping) and item.get("id")
    }
    wikisource = witnesses.get("sanguozhi-wikisource")
    kanripo = witnesses.get("sanguozhi-kanripo-wyg")
    song = witnesses.get("sanguozhi-song-shoryobu")
    if not isinstance(wikisource, Mapping):
        errors.append("SGZ1 Wikisource witness is not registered")
    else:
        if wikisource.get("coverage", {}).get("global_juan") != "1-65":
            errors.append("registered SGZ1 Wikisource coverage is not 1-65")
    if not isinstance(kanripo, Mapping) or kanripo.get("coverage", {}).get("global_juan") != "1-30":
        errors.append("SGZ0 Kanripo witness does not declare 魏書 1-30 coverage")
    if not isinstance(song, Mapping) or song.get("coverage", {}).get("global_juan") != "1-65":
        errors.append("South-Song witness does not declare visual 1-65 coverage")

    source_by_juan, source_errors = _validate_source_manifest(mode)
    errors.extend(source_errors)
    try:
        manifest = read_json(SGZ1_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        return sorted(set(errors + [f"SGZ1 derived manifest cannot be read: {exc}"]))
    if manifest.get("stage") != "sgz1-sanguozhi-complete-corpus":
        errors.append("SGZ1 derived manifest stage is invalid")
    if manifest.get("primary_machine_witness") != "sanguozhi-wikisource":
        errors.append("SGZ1 primary machine witness is invalid")
    if PROHIBITED_TOP_LEVEL_KEYS & set(manifest):
        errors.append("SGZ1 manifest contains a prohibited historical-materialization key")
    coverage = manifest.get("coverage", {})
    if coverage.get("total_juan") != 65 or coverage.get("global_juan") != [1, 65]:
        errors.append("SGZ1 derived coverage is not 65 juan")
    if coverage.get("sections") != {
        "魏書": [1, 30],
        "蜀書": [31, 45],
        "吳書": [46, 65],
    }:
        errors.append("SGZ1 derived section ranges are invalid")
    records = manifest.get("records")
    if not isinstance(records, list) or len(records) != 65:
        errors.append("SGZ1 derived manifest does not contain 65 records")
        records = records if isinstance(records, list) else []
    seen_juans: list[int] = []
    section_counts = {section: 0 for section in EXPECTED_SECTIONS}
    for record in records:
        if not isinstance(record, Mapping):
            errors.append("SGZ1 derived record is not an object")
            continue
        try:
            global_juan = int(record.get("global_juan"))
        except (TypeError, ValueError):
            errors.append("SGZ1 derived record has no integer global_juan")
            continue
        seen_juans.append(global_juan)
        expected_section, expected_section_juan = (
            ("魏書", global_juan)
            if 1 <= global_juan <= 30
            else ("蜀書", global_juan - 30)
            if 31 <= global_juan <= 45
            else ("吳書", global_juan - 45)
            if 46 <= global_juan <= 65
            else ("", 0)
        )
        if record.get("section") != expected_section or record.get("section_juan") != expected_section_juan:
            errors.append(f"SGZ1 section mapping is invalid: juan {global_juan}")
        if expected_section in section_counts:
            section_counts[expected_section] += 1
        if record.get("primary_machine_witness") != "sanguozhi-wikisource":
            errors.append(f"SGZ1 record witness is invalid: juan {global_juan}")
        source = source_by_juan.get(global_juan)
        if source is None:
            errors.append(f"SGZ1 record has no source manifest record: juan {global_juan}")
        else:
            if record.get("source_sha256") != source.get("source_sha256"):
                errors.append(f"SGZ1 record/source SHA mismatch: juan {global_juan}")
            if record.get("source_path") != source.get("source_path"):
                errors.append(f"SGZ1 record/source path mismatch: juan {global_juan}")
        processed_path = _safe_relative(ROOT, str(record.get("processed_path", "")))
        if processed_path is None or not processed_path.is_file():
            errors.append(f"missing SGZ1 processed file: {record.get('processed_path')}")
        elif sha256(processed_path) != record.get("processed_sha256"):
            errors.append(f"SGZ1 processed SHA mismatch: {processed_path}")
        source_content: str | None = None
        source_path = _safe_relative(ROOT, str(record.get("source_path", "")))
        if source_path is not None and source_path.is_file():
            try:
                source_content = source_path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                errors.append(f"SGZ1 source is not UTF-8: {source_path}: {exc}")
        errors.extend(_validate_units(record, source_content=source_content))
    if seen_juans != list(range(1, 66)):
        errors.append("SGZ1 derived global juan sequence has gaps or duplicates")
    if section_counts != {"魏書": 30, "蜀書": 15, "吳書": 20}:
        errors.append(f"SGZ1 derived section counts are invalid: {section_counts}")
    return sorted(set(errors))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("full", "portable"), default="portable")
    args = parser.parse_args()
    problems = validate(args.mode)
    if problems:
        print("SGZ1 validation failed:")
        print("\n".join(f"- {problem}" for problem in problems))
        raise SystemExit(1)
    print(f"SGZ1 validation passed ({args.mode})")
