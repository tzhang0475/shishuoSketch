#!/usr/bin/env python3
"""Build the deterministic ZTJ0 processed source corpora and indexes.

This processor is deliberately structural.  It preserves the exact decoded
source text and source coordinates, removes only Kanripo layout marks from
convenience projections, and does not assign dates, events, or cross-source
historical conclusions.

The inspected KR2b0007 witness uses balanced one-level parentheses for Hu
Sanxing's 音註.  That boundary is promoted to a separate annotation layer
only when the complete source file is balanced at depth one.  Kaoyi is kept
as critical prose rather than being over-parsed into competing claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "sources/downloads/zizhi-tongjian"
OUTPUT_ROOT = ROOT / "content/processed/zizhi-tongjian"
MANIFEST_PATH = ROOT / "data/derived/ztj0-processed-corpus.json"
CHRONOLOGY_INDEX_PATH = ROOT / "data/derived/ztj0-chronology-index.json"
KAOYI_INDEX_PATH = ROOT / "data/derived/ztj0-kaoyi-index.json"
WEIJIN_RANGE_PATH = ROOT / "data/derived/ztj0-weijin-range.json"

PROPERTY_RE = re.compile(r"^#\+PROPERTY:\s+(\S+)(?:\s+(.*))?$")
KEYWORD_RE = re.compile(r"^#\+([A-Za-z][A-Za-z0-9_-]*):(?:\s+(.*))?$")
PAGE_RE = re.compile(r"<pb:[^>]+>")
CHRONICLE_RE = re.compile(
    r"(?P<chronicle>(?:後唐|後晉|後晋|後漢|後周|後?漢|周|秦|魏|晉|晋|宋|齊|梁|陳|隋|唐)"
    r"[紀記][一二三四五六七八九十百〇0-9]*)"
)
ERA_SURFACE_RE = re.compile(r"[\u4e00-\u9fff]{1,8}[元一二三四五六七八九十百廿卅〇0-9]+年")
RULER_RE = re.compile(r"[\u4e00-\u9fff]{1,12}(?:皇帝|帝|王)")
HAN_RE = re.compile(r"[\u4e00-\u9fff]+")

PRIMARY_SLUG = "kanripo-wyg"
KAOYI_SLUG = "kaoyi-kanripo"
MULU_SLUG = "mulu-kanripo"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def stable_id(prefix: str, *parts: object) -> str:
    canonical = "\x1f".join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:20]}"


def json_write(path: Path, value: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.write_bytes(payload)
    return sha256_bytes(payload)


def acquisition_summary(slug: str) -> dict[str, Any]:
    lock_path = SOURCE_ROOT / slug / "manifest.lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
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
    inventory_hash = sha256_bytes(
        json.dumps(inventory, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    return {
        "witness_id": lock.get("witness_id"),
        "lock_path": str(lock_path.relative_to(ROOT)).replace("\\", "/"),
        "repository": lock.get("repository"),
        "upstream_commit": lock.get("upstream_commit"),
        "source_file_count": len(inventory),
        "source_inventory_sha256": inventory_hash,
    }


def line_records(text: str) -> list[tuple[int, int, str]]:
    records: list[tuple[int, int, str]] = []
    cursor = 0
    for raw in text.splitlines(keepends=True):
        end = cursor + len(raw)
        records.append((cursor, end, raw.rstrip("\r\n")))
        cursor = end
    if cursor < len(text):
        records.append((cursor, len(text), text[cursor:]))
    return records


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def page_markers(text: str, start: int, end: int) -> list[str]:
    return [match.group(0) for match in PAGE_RE.finditer(text, start, end)]


def normalize_layout(value: str) -> str:
    """Remove only Kanripo layout marks from a convenience text projection."""

    return PAGE_RE.sub("", value).replace("¶", "")


def parse_metadata(text: str) -> dict[str, Any]:
    properties: dict[str, list[str]] = {}
    keywords: dict[str, list[str]] = {}
    headers: list[str] = []
    body_start = 0
    first_page = PAGE_RE.search(text)
    if first_page:
        body_start = first_page.start()
    for raw in text[:body_start].splitlines():
        if raw.startswith("# -*-") or raw.startswith("# -"):
            headers.append(raw)
            continue
        property_match = PROPERTY_RE.match(raw)
        if property_match:
            key, value = property_match.group(1), (property_match.group(2) or "")
            properties.setdefault(key, []).append(value)
            continue
        keyword_match = KEYWORD_RE.match(raw)
        if keyword_match:
            key, value = keyword_match.group(1), (keyword_match.group(2) or "")
            keywords.setdefault(key, []).append(value)
    return {
        "properties": properties,
        "keywords": keywords,
        "headers": headers,
        "body_start": body_start,
        "juan_surface": (properties.get("JUAN") or [""])[0],
        "baseedition_surface": (properties.get("BASEEDITION") or [""])[0].strip(),
        "file_surfaces": properties.get("FILE", []),
    }


def source_span(text: str, start: int, end: int) -> dict[str, Any]:
    return {
        "char_start": start,
        "char_end_exclusive": end,
        "line_start": line_number(text, start),
        "line_end": line_number(text, max(start, end - 1)),
        "page_markers": page_markers(text, start, end),
    }


def split_balanced_layers(
    text: str,
    *,
    source_file: str,
    body_start: int,
    witness_id: str,
    annotation_layer: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Split one-level balanced parenthetical spans without editing source text."""

    segments: list[dict[str, Any]] = []
    depth = 0
    maximum_depth = 0
    start = body_start
    malformed = False

    def emit(segment_start: int, segment_end: int, layer: str) -> None:
        if segment_end <= segment_start:
            return
        raw = text[segment_start:segment_end]
        if not normalize_layout(raw).strip():
            return
        inner = raw[1:-1] if layer == annotation_layer and raw.startswith("(") and raw.endswith(")") else raw
        segments.append(
            {
                "unit_id": stable_id(
                    "ztj0-unit", witness_id, source_file, segment_start, segment_end, layer
                ),
                "layer": layer,
                "author_layer": "司馬光" if layer == "main_text" else "胡三省",
                "source_file": source_file,
                "source_span": source_span(text, segment_start, segment_end),
                "raw_text": raw,
                "text": normalize_layout(inner),
            }
        )

    for index in range(body_start, len(text)):
        character = text[index]
        if character == "(":
            if depth == 0:
                emit(start, index, "main_text")
                start = index
            depth += 1
            maximum_depth = max(maximum_depth, depth)
        elif character == ")":
            if depth == 0:
                malformed = True
                continue
            depth -= 1
            if depth == 0:
                emit(start, index + 1, annotation_layer)
                start = index + 1
    if depth != 0:
        malformed = True
    emit(start, len(text), "main_text" if depth == 0 else "interleaved_unresolved")
    status = (
        "reliable_balanced_parentheses_one_level"
        if not malformed and maximum_depth <= 1
        else "unresolved_interleaved_parentheses"
    )
    return segments, {
        "status": status,
        "maximum_parenthesis_depth": maximum_depth,
        "balanced": not malformed and depth == 0,
        "annotation_boundary_basis": "balanced_parentheses" if status.startswith("reliable") else "not_promoted",
    }


def normalized_main_text(units: Iterable[Mapping[str, Any]]) -> str:
    return "".join(str(unit["text"]) for unit in units if unit.get("layer") == "main_text")


def unit_slice(units: Iterable[Mapping[str, Any]], start: int, end: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for unit in units:
        span = unit["source_span"]
        if span["char_end_exclusive"] > start and span["char_start"] < end:
            result.append(dict(unit))
    return result


def clean_source_line(value: str) -> str:
    return normalize_layout(value).strip()


def first_chronicle_match(text: str, units: Iterable[Mapping[str, Any]]) -> tuple[re.Match[str], Mapping[str, Any]] | None:
    for unit in units:
        if unit.get("layer") != "main_text":
            continue
        match = CHRONICLE_RE.search(str(unit.get("text", "")))
        if match:
            # The normalized unit text has page/layout marks removed but its
            # character offsets still begin at the unit source start.  The
            # heading is only used as an observed surface; block coordinates
            # use the containing unit start to avoid false precision after
            # structural-mark removal.
            return match, unit
    return None


def chronology_block(text: str, units: list[dict[str, Any]], *, volume: int, source_file: str) -> dict[str, Any] | None:
    found = first_chronicle_match(text, units)
    if found is None:
        return None
    match, unit = found
    raw_unit = str(unit["raw_text"])
    raw_match_offset = raw_unit.find(match.group("chronicle"))
    observed_offset = int(unit["source_span"]["char_start"]) + max(raw_match_offset, 0)
    preceding_pages = list(PAGE_RE.finditer(text, int(unit["source_span"]["char_start"]), observed_offset + 1))
    if preceding_pages:
        # A chronology block begins at the page marker introducing its
        # heading, so the page coordinate remains attached to the block.
        start = preceding_pages[-1].start()
    else:
        start = next(
            (line_start for line_start, line_end, _line in line_records(text) if line_start <= observed_offset < line_end),
            int(unit["source_span"]["char_start"]),
        )
    end = len(text)
    block_units = unit_slice(units, start, end)
    main_units = [item for item in block_units if item.get("layer") == "main_text"]
    note_units = [item for item in block_units if item.get("layer") == "hu_annotation"]
    raw_lines = line_records(text)
    heading_line = next((line for line_start, line_end, line in raw_lines if line_start <= observed_offset < line_end), "")
    heading_surface = clean_source_line(heading_line)
    context_text = "".join(str(item["text"]) for item in main_units[:8])
    ruler_candidates = sorted(set(RULER_RE.findall(context_text)), key=lambda item: (context_text.find(item), item))
    era_candidates = sorted(set(ERA_SURFACE_RE.findall(context_text)), key=lambda item: (context_text.find(item), item))
    chronicle_name = match.group("chronicle")
    block_id = stable_id("ztj0-block", "zizhi-tongjian-kanripo-wyg", volume, start, end)
    return {
        "block_id": block_id,
        "volume": volume,
        "chronicle_name": chronicle_name,
        "ruler_surface": ruler_candidates[0] if ruler_candidates else None,
        "ruler_surface_candidates": ruler_candidates,
        "era_name_surface": era_candidates[0] if era_candidates else None,
        "era_year_surface_candidates": era_candidates,
        "volume_chronology_heading": heading_surface,
        "main_text": "".join(str(item["text"]) for item in main_units),
        "annotations": [
            {
                "annotation_id": item["unit_id"],
                "annotation_author": "胡三省",
                "text": item["text"],
                "source_span": item["source_span"],
                "parse_status": "separated_by_balanced_parentheses",
            }
            for item in note_units
        ],
        "source_span": source_span(text, start, end),
        "source_file": source_file,
        "parse_status": "source_block_heading_observed",
        "chronology_normalization": "surface_only_no_gregorian_conversion",
    }


def file_number(path: Path, prefix: str) -> int:
    match = re.fullmatch(re.escape(prefix) + r"(\d+)\.txt", path.name)
    if not match:
        raise ValueError(f"unexpected ZTJ0 source filename: {path.name}")
    return int(match.group(1))


def source_record(path: Path, *, prefix: str, witness_id: str, annotation_layer: str) -> dict[str, Any]:
    raw_bytes = path.read_bytes()
    text = raw_bytes.decode("utf-8")
    metadata = parse_metadata(text)
    units, layer_status = split_balanced_layers(
        text,
        source_file=path.name,
        body_start=int(metadata["body_start"]),
        witness_id=witness_id,
        annotation_layer=annotation_layer,
    )
    number = file_number(path, prefix)
    return {
        "source_file": path.name,
        "source_path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": sha256_bytes(raw_bytes),
        "source_bytes": len(raw_bytes),
        "source_line_count": text.count("\n") + 1,
        "file_number": number,
        "juan_surface": metadata["juan_surface"],
        "baseedition_surface": metadata["baseedition_surface"],
        "properties": metadata["properties"],
        "keywords": metadata["keywords"],
        "headers": metadata["headers"],
        "source_text": text,
        "layer_status": layer_status,
        "units": units,
    }


def render_primary_record(record: Mapping[str, Any]) -> dict[str, Any]:
    number = int(record["file_number"])
    output: dict[str, Any] = dict(record)
    # The exact source_text is retained once.  Layer text is represented by
    # the block main_text/annotations below; repeating 133k unit strings in
    # every volume would make the committed processed corpus needlessly
    # large.  Source coordinates remain on every annotation and block.
    output.pop("units", None)
    output["layer_counts"] = {
        "main_text": sum(item["layer"] == "main_text" for item in record["units"]),
        "hu_annotation": sum(item["layer"] == "hu_annotation" for item in record["units"]),
    }
    output["schema"] = 1
    output["work"] = "資治通鑑"
    output["source_witness"] = "zizhi-tongjian-kanripo-wyg"
    output["edition"] = "文淵閣四庫全書 / WYG"
    output["source_grammar"] = {
        "metadata": "Kanripo Org headers and #+PROPERTY directives",
        "physical_line_marker": "¶",
        "page_marker": "<pb:...>",
        "hu_annotation_delimiter": "balanced one-level parentheses",
        "observed_payload_baseedition": record["baseedition_surface"],
    }
    output["kind"] = "front_matter" if number == 0 else "volume" if 1 <= number <= 294 else "unassigned_source_stub"
    output["juan_number"] = number if 1 <= number <= 294 else None
    if output["kind"] == "volume":
        output["chronicle_blocks"] = [chronology_block(record["source_text"], record["units"], volume=number, source_file=record["source_file"])]
        output["chronicle_blocks"] = [item for item in output["chronicle_blocks"] if item is not None]
    else:
        output["chronicle_blocks"] = []
    if output["kind"] == "unassigned_source_stub":
        output["parse_status"] = "acquired_extra_file_not_assigned_to_juan"
    else:
        output["parse_status"] = "processed_source_record"
    return output


def write_primary() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_dir = SOURCE_ROOT / PRIMARY_SLUG
    paths = sorted(source_dir.glob("KR2b0007_*.txt"), key=lambda path: file_number(path, "KR2b0007_"))
    if not paths:
        raise FileNotFoundError(f"ZTJ0 primary source payload is missing: {source_dir}")
    volume_dir = OUTPUT_ROOT / "volumes"
    volume_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    for path in paths:
        record = source_record(
            path,
            prefix="KR2b0007_",
            witness_id="zizhi-tongjian-kanripo-wyg",
            annotation_layer="hu_annotation",
        )
        output = render_primary_record(record)
        number = int(record["file_number"])
        if output["kind"] == "volume":
            output_name = f"volume-{number:03d}.json"
        elif output["kind"] == "front_matter":
            output_name = "front-matter.json"
        else:
            output_name = f"unassigned-{number:03d}.json"
        output_path = volume_dir / output_name
        processed_hash = json_write(output_path, output)
        summary = {
            "source_file": record["source_file"],
            "source_path": record["source_path"],
            "source_sha256": record["source_sha256"],
            "source_bytes": record["source_bytes"],
            "file_number": number,
            "juan_surface": record["juan_surface"],
            "kind": output["kind"],
            "processed_path": str(output_path.relative_to(ROOT)).replace("\\", "/"),
            "processed_sha256": processed_hash,
            "unit_count": len(record["units"]),
            "main_text_unit_count": sum(item["layer"] == "main_text" for item in record["units"]),
            "hu_annotation_unit_count": sum(item["layer"] == "hu_annotation" for item in record["units"]),
            "chronicle_block_ids": [item["block_id"] for item in output["chronicle_blocks"]],
            "layer_status": record["layer_status"],
        }
        summaries.append(summary)
        blocks.extend(output["chronicle_blocks"])
    summaries.sort(key=lambda item: int(item["file_number"]))
    return {
        "witness_id": "zizhi-tongjian-kanripo-wyg",
        "source_registry_id": "zizhi-tongjian-kanripo-wyg",
        "file_count": len(summaries),
        "front_matter_count": sum(item["kind"] == "front_matter" for item in summaries),
        "volume_count": sum(item["kind"] == "volume" for item in summaries),
        "expected_juan_count": 294,
        "unassigned_source_file_count": sum(item["kind"] == "unassigned_source_stub" for item in summaries),
        "main_text_unit_count": sum(item["main_text_unit_count"] for item in summaries),
        "hu_annotation_unit_count": sum(item["hu_annotation_unit_count"] for item in summaries),
        "chronicle_block_count": len(blocks),
        "annotation_segmentation_status": "reliable_balanced_parentheses_one_level",
        "records": summaries,
    }, blocks


def kaoyi_record(path: Path) -> dict[str, Any]:
    raw_bytes = path.read_bytes()
    text = raw_bytes.decode("utf-8")
    metadata = parse_metadata(text)
    body_start = int(metadata["body_start"])
    body_end = len(text)
    body = text[body_start:body_end]
    number = file_number(path, "KR2b0008_")
    block_id = stable_id("ztj0-kaoyi", "zizhi-tongjian-kaoyi-kanripo", number, body_start, body_end)
    block = {
        "kaoyi_id": block_id,
        "kaoyi_volume": number,
        "source_file": path.name,
        "chronology_surface": normalize_layout(body)[:160],
        "topic_surface": None,
        "text": normalize_layout(body),
        "raw_text": body,
        "source_span": source_span(text, body_start, body_end),
        "parse_status": "whole_kaoyi_unit_preserved; topic_not_overparsed",
    }
    return {
        "schema": 1,
        "work": "資治通鑑考異",
        "source_witness": "zizhi-tongjian-kaoyi-kanripo",
        "edition": "四部叢刊 / SBCK",
        "source_file": path.name,
        "source_path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": sha256_bytes(raw_bytes),
        "source_bytes": len(raw_bytes),
        "juan_surface": metadata["juan_surface"],
        "properties": metadata["properties"],
        "keywords": metadata["keywords"],
        "source_text": text,
        "blocks": [block],
        "parse_status": "source_evidence_only",
        "annotation_segmentation": "not_promoted; parenthesized text retained inside whole Kaoyi block",
    }


def write_kaoyi() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_dir = SOURCE_ROOT / KAOYI_SLUG
    paths = sorted(source_dir.glob("KR2b0008_*.txt"), key=lambda path: file_number(path, "KR2b0008_"))
    if not paths:
        raise FileNotFoundError(f"ZTJ0 Kaoyi source payload is missing: {source_dir}")
    output_dir = OUTPUT_ROOT / "kaoyi"
    output_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    for path in paths:
        record = kaoyi_record(path)
        output_path = output_dir / f"kaoyi-{int(record['source_file'].split('_')[-1].split('.')[0]):03d}.json"
        processed_hash = json_write(output_path, record)
        block = record["blocks"][0]
        summaries.append(
            {
                "kaoyi_volume": block["kaoyi_volume"],
                "source_file": record["source_file"],
                "source_path": record["source_path"],
                "source_sha256": record["source_sha256"],
                "source_bytes": record["source_bytes"],
                "processed_path": str(output_path.relative_to(ROOT)).replace("\\", "/"),
                "processed_sha256": processed_hash,
                "kaoyi_id": block["kaoyi_id"],
            }
        )
        blocks.append(block)
    summaries.sort(key=lambda item: int(item["kaoyi_volume"]))
    blocks.sort(key=lambda item: int(item["kaoyi_volume"]))
    return {
        "witness_id": "zizhi-tongjian-kaoyi-kanripo",
        "juan_count": len(summaries),
        "expected_juan_count": 30,
        "block_count": len(blocks),
        "records": summaries,
    }, blocks


def mulu_record(path: Path) -> dict[str, Any]:
    raw_bytes = path.read_bytes()
    text = raw_bytes.decode("utf-8")
    metadata = parse_metadata(text)
    body = text[int(metadata["body_start"]):]
    normalized = normalize_layout(body)
    machine_text = re.sub(r"\s+", "", normalized)
    character_count = sum(len(run) for run in HAN_RE.findall(machine_text))
    number = file_number(path, "KR2b0010_")
    return {
        "schema": 1,
        "work": "資治通鑑目錄",
        "source_witness": "zizhi-tongjian-mulu-kanripo",
        "edition": "文淵閣四庫全書 / WYG",
        "source_file": path.name,
        "source_path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": sha256_bytes(raw_bytes),
        "source_bytes": len(raw_bytes),
        "file_number": number,
        "juan_surface": metadata["juan_surface"],
        "properties": metadata["properties"],
        "source_text": text,
        "body_text": normalized,
        "source_span": source_span(text, int(metadata["body_start"]), len(text)),
        "machine_text_character_count": character_count,
        "coverage_status": "usable_machine_text" if character_count >= 30 else "sparse_or_page_marker_only",
        "parse_status": "lightweight_source_preservation_no_ocr",
    }


def write_mulu() -> dict[str, Any]:
    source_dir = SOURCE_ROOT / MULU_SLUG
    paths = sorted(source_dir.glob("KR2b0010_*.txt"), key=lambda path: file_number(path, "KR2b0010_"))
    if not paths:
        raise FileNotFoundError(f"ZTJ0 Mulu source payload is missing: {source_dir}")
    output_dir = OUTPUT_ROOT / "mulu"
    output_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, Any]] = []
    for path in paths:
        record = mulu_record(path)
        number = int(record["file_number"])
        output_name = "front-matter.json" if number == 0 else f"volume-{number:03d}.json"
        output_path = output_dir / output_name
        processed_hash = json_write(output_path, record)
        summaries.append(
            {
                "file_number": number,
                "juan_surface": record["juan_surface"],
                "source_file": record["source_file"],
                "source_path": record["source_path"],
                "source_sha256": record["source_sha256"],
                "source_bytes": record["source_bytes"],
                "processed_path": str(output_path.relative_to(ROOT)).replace("\\", "/"),
                "processed_sha256": processed_hash,
                "machine_text_character_count": record["machine_text_character_count"],
                "coverage_status": record["coverage_status"],
            }
        )
    summaries.sort(key=lambda item: int(item["file_number"]))
    return {
        "witness_id": "zizhi-tongjian-mulu-kanripo",
        "file_count": len(summaries),
        "expected_juan_count": 30,
        "front_matter_count": sum(item["file_number"] == 0 for item in summaries),
        "usable_machine_text_volume_count": sum(item["file_number"] > 0 and item["coverage_status"] == "usable_machine_text" for item in summaries),
        "sparse_volume_count": sum(item["file_number"] > 0 and item["coverage_status"] != "usable_machine_text" for item in summaries),
        "records": summaries,
    }


def build_chronology_index(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    token_index: dict[str, list[str]] = {}
    for block in sorted(blocks, key=lambda item: (int(item["volume"]), item["source_span"]["char_start"], item["block_id"])):
        search_text = str(block.get("main_text", ""))
        # Chinese source text is not whitespace-tokenized.  Keep only short
        # exact surfaces here so this remains a lightweight lookup aid; the
        # complete source text and source spans remain in the volume records.
        tokens = sorted({token for token in HAN_RE.findall(search_text) if 1 <= len(token) <= 12})
        record = {
            "block_id": block["block_id"],
            "volume": block["volume"],
            "chronicle_name": block["chronicle_name"],
            "ruler_surface": block["ruler_surface"],
            "era_name_surface": block["era_name_surface"],
            "era_year_surface_candidates": block["era_year_surface_candidates"],
            "volume_chronology_heading": block["volume_chronology_heading"],
            "source_file": block["source_file"],
            "source_span": block["source_span"],
            "source_witness": "zizhi-tongjian-kanripo-wyg",
            "text_token_surfaces": tokens,
        }
        records.append(record)
        for token in tokens:
            token_index.setdefault(token, []).append(block["block_id"])
    for token in token_index:
        token_index[token] = sorted(token_index[token])
    return {
        "schema": 1,
        "stage": "ztj0-chronology-index",
        "source_witness": "zizhi-tongjian-kanripo-wyg",
        "index_policy": "source order; structural surfaces and exact source spans only; no normalized dates",
        "record_count": len(records),
        "records": records,
        "token_index": {key: token_index[key] for key in sorted(token_index)},
    }


def build_kaoyi_index(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    records = [
        {
            "kaoyi_id": block["kaoyi_id"],
            "kaoyi_volume": block["kaoyi_volume"],
            "chronology_surface": block["chronology_surface"],
            "source_file": block["source_file"] if "source_file" in block else None,
            "source_span": block["source_span"],
            "source_witness": "zizhi-tongjian-kaoyi-kanripo",
            "parse_status": block["parse_status"],
        }
        for block in sorted(blocks, key=lambda item: int(item["kaoyi_volume"]))
    ]
    return {
        "schema": 1,
        "stage": "ztj0-kaoyi-index",
        "source_witness": "zizhi-tongjian-kaoyi-kanripo",
        "index_policy": "whole source block order; Kaoyi text remains evidence and is not adjudicated",
        "record_count": len(records),
        "records": records,
    }


def build_weijin_range(chronology_index: Mapping[str, Any]) -> dict[str, Any]:
    records = list(chronology_index["records"])
    grouped: dict[str, list[int]] = {}
    for record in records:
        chronicle = str(record.get("chronicle_name") or "")
        family = next(
            (
                prefix
                for prefix in ("漢紀", "魏紀", "晉紀", "晉記")
                if chronicle.startswith(prefix)
            ),
            None,
        )
        if family:
            grouped.setdefault(family, []).append(int(record["volume"]))
    for key in grouped:
        grouped[key] = sorted(set(grouped[key]))
    relevant = sorted({volume for values in grouped.values() for volume in values})
    return {
        "schema": 1,
        "stage": "ztj0-weijin-range-audit",
        "source_witness": "zizhi-tongjian-kanripo-wyg",
        "purpose": "future H0A search scope; not Story temporal resolution",
        "phase_method": "group observed chronicle-name surfaces; no assumed volume boundaries and no Gregorian conversion",
        "chronicle_family_volumes": grouped,
        "relevant_volume_numbers": relevant,
        "relevant_volume_range": [min(relevant), max(relevant)] if relevant else None,
        "records": [
            {
                "volume": record["volume"],
                "chronicle_name": record["chronicle_name"],
                "raw_start_chronology": record["volume_chronology_heading"],
                "raw_end_chronology": record["volume_chronology_heading"],
                "era_surfaces_found": record["era_year_surface_candidates"],
                "source_span": record["source_span"],
            }
            for record in records
            if int(record["volume"]) in relevant
        ],
        "limitations": [
            "The range is organized by observed 通鑑紀 headings, not a normalized historical period model.",
            "The 83 Shishuo Stories are not assigned temporal anchors in ZTJ0.",
            "Chronology surfaces remain witness text; H0A owns later comparison and normalization.",
        ],
    }


def build() -> dict[str, Any]:
    primary_summary, blocks = write_primary()
    kaoyi_summary, kaoyi_blocks = write_kaoyi()
    mulu_summary = write_mulu()
    chronology_index = build_chronology_index(blocks)
    kaoyi_index = build_kaoyi_index(kaoyi_blocks)
    weijin_range = build_weijin_range(chronology_index)
    chronology_hash = json_write(CHRONOLOGY_INDEX_PATH, chronology_index)
    kaoyi_hash = json_write(KAOYI_INDEX_PATH, kaoyi_index)
    range_hash = json_write(WEIJIN_RANGE_PATH, weijin_range)
    manifest = {
        "schema": 1,
        "stage": "ztj0-zizhi-tongjian-processed-corpus",
        "processor": "scripts/build_ztj0_corpus.py",
        "work": "資治通鑑",
        "source_registry": "sources/registry/zizhi-tongjian.yaml",
        "acquisition": {
            "primary": acquisition_summary(PRIMARY_SLUG),
            "kaoyi": acquisition_summary(KAOYI_SLUG),
            "mulu": acquisition_summary(MULU_SLUG),
            "policy": "lock retrieval metadata is excluded from processed hashes",
        },
        "primary_machine_witness": "zizhi-tongjian-kanripo-wyg",
        "primary": primary_summary,
        "kaoyi": kaoyi_summary,
        "mulu": mulu_summary,
        "chronology_index": {
            "path": str(CHRONOLOGY_INDEX_PATH.relative_to(ROOT)).replace("\\", "/"),
            "sha256": chronology_hash,
            "record_count": chronology_index["record_count"],
        },
        "kaoyi_index": {
            "path": str(KAOYI_INDEX_PATH.relative_to(ROOT)).replace("\\", "/"),
            "sha256": kaoyi_hash,
            "record_count": kaoyi_index["record_count"],
        },
        "weijin_range": {
            "path": str(WEIJIN_RANGE_PATH.relative_to(ROOT)).replace("\\", "/"),
            "sha256": range_hash,
            "volume_range": weijin_range["relevant_volume_range"],
        },
        "processing_policy": {
            "source_text": "exact decoded UTF-8 text retained in each processed record; source SHA covers original bytes",
            "hu_annotation_layer": "balanced one-level parenthesized spans only when the file is balanced; otherwise unresolved interleaving is retained",
            "kaoyi": "whole evidence blocks retained; no source-choice adjudication",
            "mulu": "sparse/page-marker-only coverage recorded without OCR",
            "chronology": "surface extraction only; no Gregorian normalization and no Story temporal anchors",
            "historical_event_creation": "disabled",
        },
    }
    json_write(MANIFEST_PATH, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    manifest = build()
    print(
        "built ZTJ0: "
        f"juan={manifest['primary']['volume_count']}; "
        f"blocks={manifest['primary']['chronicle_block_count']}; "
        f"hu={manifest['primary']['hu_annotation_unit_count']}; "
        f"kaoyi={manifest['kaoyi']['block_count']}; "
        f"mulu_usable={manifest['mulu']['usable_machine_text_volume_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
