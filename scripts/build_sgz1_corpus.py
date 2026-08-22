#!/usr/bin/env python3
"""Build the complete, provenance-preserving SGZ1 Sanguozhi corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

try:
    from .download_witnesses import (
        SANGUOZHI_WIKISOURCE_ROOT,
        SANGUOZHI_WIKISOURCE_WITNESS_ID,
        parse_sanguozhi_wikisource_section,
        sanguozhi_section_for_juan,
    )
except ImportError:  # pragma: no cover - direct script execution
    from download_witnesses import (
        SANGUOZHI_WIKISOURCE_ROOT,
        SANGUOZHI_WIKISOURCE_WITNESS_ID,
        parse_sanguozhi_wikisource_section,
        sanguozhi_section_for_juan,
    )


ROOT = Path(__file__).resolve().parents[1]
SOURCE_MANIFEST = Path(SANGUOZHI_WIKISOURCE_ROOT) / "manifest.lock.json"
OUTPUT_DIR = Path("content/processed/sanguozhi/sgz1")
OUTPUT_MANIFEST = Path("data/derived/sgz1-sanguozhi-complete-corpus.json")
HEADER_START_RE = re.compile(r"\{\{header2?\b")
PEI_TEMPLATE_RE = re.compile(r"\{\{\s*\*\s*\|")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def balanced_template_end(text: str, start: int) -> int:
    """Return the exclusive end of a balanced MediaWiki template."""

    if not text.startswith("{{", start):
        raise ValueError(f"template does not start at offset {start}")
    depth = 0
    index = start
    while index < len(text) - 1:
        token = text[index : index + 2]
        if token == "{{":
            depth += 1
            index += 2
            continue
        if token == "}}":
            depth -= 1
            index += 2
            if depth == 0:
                return index
            continue
        index += 1
    raise ValueError(f"unbalanced MediaWiki template at offset {start}")


def _unit(
    *,
    sequence: int,
    global_juan: int,
    source_path: str,
    source_sha256: str,
    content: str,
    start: int,
    end: int,
    layer: str,
    author_layer: str | None,
    text: str,
    segmentation_status: str,
) -> dict[str, Any]:
    raw = content[start:end]
    return {
        "unit_id": f"sgz1-juan-{global_juan:03d}-{sequence:06d}",
        "global_juan": global_juan,
        "layer": layer,
        "author_layer": author_layer,
        "segmentation_status": segmentation_status,
        "source_path": source_path,
        "source_sha256": source_sha256,
        "source_span": {
            "char_start": start,
            "char_end_exclusive": end,
            "line_start": line_number(content, start),
            "line_end": line_number(content, max(start, end - 1)),
        },
        "raw_text": raw,
        "text": text,
    }


def parse_sgz1_layers(
    content: str,
    *,
    global_juan: int,
    source_path: str = "",
    source_sha256: str = "",
) -> tuple[list[dict[str, Any]], str]:
    """Split only explicit Wikisource annotation templates.

    ``{{*|...}}`` is the observed structural marker for Pei Songzhi notes.
    No punctuation, parentheses, or semantic heuristics are used.  If no
    marker is present, the body remains one ``unparsed`` unit instead of being
    assigned to either author layer.
    """

    units: list[dict[str, Any]] = []
    sequence = 0
    cursor = 0
    body_start = 0
    header_match = HEADER_START_RE.search(content[:200])
    if header_match is not None and header_match.start() <= len(content[:200].lstrip()):
        header_start = header_match.start()
        header_end = balanced_template_end(content, header_start)
        if header_start > 0:
            sequence += 1
            units.append(
                _unit(
                    sequence=sequence,
                    global_juan=global_juan,
                    source_path=source_path,
                    source_sha256=source_sha256,
                    content=content,
                    start=0,
                    end=header_start,
                    layer="metadata",
                    author_layer=None,
                    text=content[:header_start],
                    segmentation_status="source_metadata",
                )
            )
        sequence += 1
        units.append(
            _unit(
                sequence=sequence,
                global_juan=global_juan,
                source_path=source_path,
                source_sha256=source_sha256,
                content=content,
                start=header_start,
                end=header_end,
                layer="metadata",
                author_layer=None,
                text=content[header_start:header_end],
                segmentation_status="source_metadata",
            )
        )
        body_start = header_end
        cursor = header_end

    note_count = 0
    for match in PEI_TEMPLATE_RE.finditer(content, body_start):
        start = match.start()
        if start < cursor:
            continue
        if start > cursor:
            sequence += 1
            units.append(
                _unit(
                    sequence=sequence,
                    global_juan=global_juan,
                    source_path=source_path,
                    source_sha256=source_sha256,
                    content=content,
                    start=cursor,
                    end=start,
                    layer="main_text",
                    author_layer="陳壽",
                    text=content[cursor:start],
                    segmentation_status="structural_template_marker",
                )
            )
        end = balanced_template_end(content, start)
        raw_note = content[start:end]
        pipe = raw_note.find("|")
        inner = raw_note[pipe + 1 : -2] if pipe >= 0 and raw_note.endswith("}}") else raw_note
        sequence += 1
        units.append(
            _unit(
                sequence=sequence,
                global_juan=global_juan,
                source_path=source_path,
                source_sha256=source_sha256,
                content=content,
                start=start,
                end=end,
                layer="pei_annotation",
                author_layer="裴松之",
                text=inner,
                segmentation_status="structural_template_marker",
            )
        )
        note_count += 1
        cursor = end

    if cursor < len(content):
        sequence += 1
        units.append(
            _unit(
                sequence=sequence,
                global_juan=global_juan,
                source_path=source_path,
                source_sha256=source_sha256,
                content=content,
                start=cursor,
                end=len(content),
                layer="main_text" if note_count else "unparsed",
                author_layer="陳壽" if note_count else None,
                text=content[cursor:],
                segmentation_status=(
                    "structural_template_marker"
                    if note_count
                    else "unresolved_no_structural_pei_marker"
                ),
            )
        )
    if not units and content:
        sequence += 1
        units.append(
            _unit(
                sequence=sequence,
                global_juan=global_juan,
                source_path=source_path,
                source_sha256=source_sha256,
                content=content,
                start=0,
                end=len(content),
                layer="unparsed",
                author_layer=None,
                text=content,
                segmentation_status="unresolved_no_structural_pei_marker",
            )
        )
    status = "structurally_segmented" if note_count else "unresolved_unparsed"
    return units, status


def render_processed_record(record: Mapping[str, Any]) -> str:
    lines = [
        "---",
        "schema: 1",
        "processor: scripts/build_sgz1_corpus.py",
        f"global_juan: {record['global_juan']}",
        f"section: {record['section']}",
        f"section_juan: {record['section_juan']}",
        f"title: {json.dumps(record['title'], ensure_ascii=False)}",
        f"source_path: {json.dumps(record['source_path'], ensure_ascii=False)}",
        f"source_sha256: {record['source_sha256']}",
        f"segmentation_status: {record['segmentation_status']}",
        "---",
        "",
        f"# {record['section']} 卷{record['section_juan']} · {record['title']}",
        "",
    ]
    for unit in record["units"]:
        lines.extend(
            [
                f"## {unit['layer']} · {unit['unit_id']}",
                "",
                unit["text"],
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build(
    root: Path = ROOT,
    *,
    source_manifest_path: Path = SOURCE_MANIFEST,
    output_dir: Path = OUTPUT_DIR,
    output_manifest_path: Path = OUTPUT_MANIFEST,
) -> dict[str, Any]:
    source_manifest_path = root / source_manifest_path if not source_manifest_path.is_absolute() else source_manifest_path
    output_dir = root / output_dir if not output_dir.is_absolute() else output_dir
    output_manifest_path = root / output_manifest_path if not output_manifest_path.is_absolute() else output_manifest_path
    source_manifest = _read_json(source_manifest_path)
    if source_manifest.get("witness_id") != SANGUOZHI_WIKISOURCE_WITNESS_ID:
        raise ValueError("SGZ1 source manifest witness id is not sanguozhi-wikisource")
    if source_manifest.get("status") != "complete":
        raise ValueError("SGZ1 requires a complete Wikisource source manifest")
    records_by_juan = {
        int(record["global_juan"]): record
        for record in source_manifest.get("records", [])
        if isinstance(record, Mapping) and record.get("global_juan") is not None
    }
    if set(records_by_juan) != set(range(1, 66)):
        raise ValueError("SGZ1 source manifest does not contain exactly global juan 1-65")

    output_records: list[dict[str, Any]] = []
    section_counts = {"魏書": 0, "蜀書": 0, "吳書": 0}
    author_layer_counts = {"陳壽": 0, "裴松之": 0, "unresolved": 0}
    segmentation_counts: dict[str, int] = {}
    for global_juan in range(1, 66):
        source_record = records_by_juan[global_juan]
        source_path = Path(str(source_record.get("source_path", "")))
        source_file = source_path if source_path.is_absolute() else root / source_path
        if not source_file.is_file():
            raise FileNotFoundError(f"SGZ1 source payload is missing: {source_file}")
        raw_bytes = source_file.read_bytes()
        source_sha256 = sha256_bytes(raw_bytes)
        if source_sha256 != source_record.get("source_sha256"):
            raise ValueError(f"SGZ1 source SHA-256 mismatch: {source_path}")
        content = raw_bytes.decode("utf-8")
        section_info = parse_sanguozhi_wikisource_section(
            content, global_juan=global_juan
        )
        expected_section, expected_section_juan = sanguozhi_section_for_juan(global_juan)
        if source_record.get("section") != expected_section:
            raise ValueError(f"SGZ1 source manifest section mismatch: juan {global_juan}")
        units, segmentation_status = parse_sgz1_layers(
            content,
            global_juan=global_juan,
            source_path=source_path.as_posix(),
            source_sha256=source_sha256,
        )
        processed_record: dict[str, Any] = {
            "global_juan": global_juan,
            "section": expected_section,
            "section_juan": expected_section_juan,
            "title": section_info["header_section"],
            "primary_machine_witness": SANGUOZHI_WIKISOURCE_WITNESS_ID,
            "source_revision": {
                "page_id": source_record.get("page_id"),
                "revision_id": source_record.get("revision_id"),
                "timestamp": source_record.get("revision_timestamp"),
            },
            "source_sha256": source_sha256,
            "source_path": source_path.as_posix(),
            "source_coordinates": {
                "page_title": source_record.get("page_title"),
                "source_url": source_record.get("source_url"),
                "api_url": source_record.get("api_url"),
                "global_juan": global_juan,
                "section": expected_section,
                "section_juan": expected_section_juan,
            },
            "segmentation_status": segmentation_status,
            "layer_counts": {
                "main_text": sum(unit["layer"] == "main_text" for unit in units),
                "pei_annotation": sum(unit["layer"] == "pei_annotation" for unit in units),
                "metadata": sum(unit["layer"] == "metadata" for unit in units),
                "unparsed": sum(unit["layer"] == "unparsed" for unit in units),
            },
            "units": units,
        }
        processed_path = output_dir / f"volume-{global_juan:03d}.md"
        rendered = render_processed_record(processed_record)
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        processed_path.write_text(rendered, encoding="utf-8", newline="\n")
        processed_record["processed_path"] = processed_path.relative_to(root).as_posix()
        processed_record["processed_sha256"] = sha256_bytes(rendered.encode("utf-8"))
        output_records.append(processed_record)
        section_counts[expected_section] += 1
        segmentation_counts[segmentation_status] = segmentation_counts.get(segmentation_status, 0) + 1
        for unit in units:
            if unit["author_layer"] in author_layer_counts:
                author_layer_counts[unit["author_layer"]] += 1
            elif unit["layer"] not in {"metadata"}:
                author_layer_counts["unresolved"] += 1

    manifest = {
        "schema": 1,
        "stage": "sgz1-sanguozhi-complete-corpus",
        "processor": "scripts/build_sgz1_corpus.py",
        "work": "三國志",
        "coverage": {
            "total_juan": 65,
            "global_juan": [1, 65],
            "sections": {
                "魏書": [1, 30],
                "蜀書": [31, 45],
                "吳書": [46, 65],
            },
        },
        "primary_machine_witness": SANGUOZHI_WIKISOURCE_WITNESS_ID,
        "witness_roles": {
            "sanguozhi-kanripo-wyg": "魏書 machine witness, 1-30",
            "sanguozhi-wikisource": "complete machine witness, 1-65",
            "sanguozhi-song-shoryobu": "complete visual/reference witness, 1-65; OCR non-authoritative",
        },
        "source_registry": "sources/registry/sanguozhi.yaml",
        "source_manifest": source_manifest_path.relative_to(root).as_posix(),
        "section_counts": section_counts,
        "author_layer_policy": {
            "main_text": "陳壽 when source structure is explicit",
            "pei_annotation": "裴松之 only for explicit {{*|...}} templates",
            "unparsed": "no author layer assigned when no safe structural boundary exists",
        },
        "author_layer_unit_counts": author_layer_counts,
        "segmentation_counts": segmentation_counts,
        "records": output_records,
        "notes": [
            "SGZ1 is evidence infrastructure; it does not create Persons, Relations, Events, PersonStory links, Mentions, or canonical facts.",
            "Raw Wikisource wikitext remains in the ignored source download area; this processed projection preserves source hashes and coordinates.",
            "Pei Songzhi notes are separated only by the observed explicit {{*|...}} template marker. No punctuation or parenthesis heuristic is used.",
        ],
    }
    output_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    output_manifest_path.write_text(stable_json(manifest), encoding="utf-8", newline="\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    manifest = build(args.root.resolve())
    print(
        f"built SGZ1: {manifest['section_counts']} total={manifest['coverage']['total_juan']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
