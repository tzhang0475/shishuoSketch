#!/usr/bin/env python3
"""Process the locally available registered Sanguozhi Kanripo witness.

Kanripo's source grammar is not Shishuo's Markdown grammar: parenthesized
spans are Pei Songzhi annotations, ``¶`` is a physical line terminator, and
``<pb:...>`` carries page coordinates.  This builder keeps raw spans and
separates the two author layers without editing the ignored upstream files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "shishuoSources/sanguozhi"
OUTPUT_DIR = ROOT / "content/processed/sanguozhi"
MANIFEST_PATH = ROOT / "data/derived/sgz0-processed-corpus.json"
LOCK_PATH = ROOT / "sources/registry/sanguozhi-provenance.lock.json"

PROPERTY_RE = re.compile(r"^#\+PROPERTY:\s+(\S+)(?:\s+(.*))?$")
PAGE_RE = re.compile(r"<pb:[^>]+>")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def metadata(text: str) -> dict[str, Any]:
    fields: dict[str, Any] = {"properties": {}}
    for line in text.splitlines():
        match = PROPERTY_RE.match(line)
        if match:
            key, value = match.group(1), (match.group(2) or "").strip()
            fields["properties"][key] = value
    fields["title"] = "三國志"
    fields["juan"] = fields["properties"].get("JUAN", "")
    return fields


def normalize_fragment(value: str) -> str:
    # Only structural witness marks are removed from this convenience text;
    # the exact raw fragment and source coordinates remain alongside it.
    return PAGE_RE.sub("", value).replace("¶", "")


def render_text(value: str) -> str:
    """Keep rendered convenience Markdown free of witness trailing spaces.

    Exact witness bytes remain in ``raw_text`` and are covered by the source
    hash; this only keeps the human-readable processed projection diff-clean.
    """

    return "\n".join(line.rstrip() for line in value.splitlines())


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def page_markers(text: str, start: int, end: int) -> list[str]:
    return [match.group(0) for match in PAGE_RE.finditer(text, start, end)]


def parse_layers(text: str, source_file: str) -> list[dict[str, Any]]:
    """Split balanced parenthesized Pei notes from outside main text.

    The local witness has a maximum parenthesis depth of one.  We still track
    depth explicitly and fail on malformed balance rather than silently
    assigning text to the wrong author layer.
    """

    units: list[dict[str, Any]] = []
    depth = 0
    start = 0
    sequence = 0

    def emit(end: int, layer: str) -> None:
        nonlocal sequence
        if end <= start:
            return
        raw = text[start:end]
        if not normalize_fragment(raw).strip("\n "):
            return
        sequence += 1
        inner = raw[1:-1] if layer == "pei_annotation" and raw.startswith("(") and raw.endswith(")") else raw
        unit_id = f"sgz0-{source_file.removesuffix('.txt')}-{sequence:06d}"
        units.append(
            {
                "unit_id": unit_id,
                "layer": layer,
                "author_layer": "陳壽" if layer == "main_text" else "裴松之",
                "source_file": source_file,
                "source_span": {
                    "char_start": start,
                    "char_end_exclusive": end,
                    "line_start": line_number(text, start),
                    "line_end": line_number(text, max(start, end - 1)),
                    "page_markers": page_markers(text, start, end),
                },
                "raw_text": raw,
                "text": normalize_fragment(inner),
                "cited_work": None,
                "cited_work_status": "unparsed",
            }
        )

    for index, character in enumerate(text):
        if character == "(":
            if depth == 0:
                emit(index, "main_text")
                start = index
            depth += 1
        elif character == ")":
            if depth == 0:
                raise ValueError(f"unbalanced closing parenthesis in {source_file} at {index}")
            depth -= 1
            if depth == 0:
                emit(index + 1, "pei_annotation")
                start = index + 1
        elif depth > 1:
            # Nested annotation punctuation is not expected in this witness;
            # retaining depth makes the malformed case explicit to callers.
            pass
    if depth != 0:
        raise ValueError(f"unbalanced opening parenthesis in {source_file}")
    emit(len(text), "main_text")
    return units


def source_files() -> list[Path]:
    files = sorted(SOURCE_DIR.glob("KR2a0012_*.txt"))
    if not files:
        raise FileNotFoundError(f"registered Sanguozhi source directory is empty: {SOURCE_DIR}")
    return files


def render_volume(record: Mapping[str, Any]) -> str:
    lines = [
        "---",
        "schema: 1",
        "processor: scripts/build_sgz0_corpus.py",
        f"source_file: {json.dumps(record['source_file'], ensure_ascii=False)}",
        f"source_sha256: {json.dumps(record['source_sha256'])}",
        f"juan: {json.dumps(record.get('juan', ''), ensure_ascii=False)}",
        "---",
        "",
        f"# {record.get('juan') or '三國志前置材料'}",
        "",
        "## 陈寿正文",
        "",
    ]
    main_units = [item for item in record["units"] if item["layer"] == "main_text"]
    pei_units = [item for item in record["units"] if item["layer"] == "pei_annotation"]
    lines.extend(render_text(item["text"]) for item in main_units)
    lines.extend(["", "## 裴松之注", ""])
    for item in pei_units:
        lines.append(f"### {item['unit_id']}")
        lines.append("")
        lines.append(render_text(item["text"]))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for path in source_files():
        raw_bytes = path.read_bytes()
        text = raw_bytes.decode("utf-8")
        file_name = path.name
        file_number = int(path.stem.rsplit("_", 1)[1])
        fields = metadata(text)
        units = parse_layers(text, file_name)
        layer_counts = {
            "main_text": sum(item["layer"] == "main_text" for item in units),
            "pei_annotation": sum(item["layer"] == "pei_annotation" for item in units),
        }
        record = {
            "source_file": file_name,
            "source_path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "source_sha256": sha256_bytes(raw_bytes),
            "source_bytes": len(raw_bytes),
            "source_line_count": text.count("\n") + 1,
            "juan": fields.get("juan", ""),
            "file_number": file_number,
            "kind": "front_matter" if file_number == 0 else "volume",
            "witness_id": "sanguozhi-kanripo-wyg",
            "base_edition": "WYG",
            "grammar": {
                "physical_line_marker": "¶",
                "page_marker": "<pb:...>",
                "pei_annotation_delimiter": "balanced_parentheses",
            },
            "layer_counts": layer_counts,
            "units": units,
        }
        output_name = "front-matter.md" if file_number == 0 else f"volume-{file_number:03d}.md"
        output_path = OUTPUT_DIR / output_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(render_volume(record), encoding="utf-8")
        record["processed_path"] = str(output_path.relative_to(ROOT)).replace("\\", "/")
        record["processed_sha256"] = sha256_bytes(render_volume(record).encode("utf-8"))
        records.append(record)

    records.sort(key=lambda item: int(item["file_number"]))
    available_volumes = [item["file_number"] for item in records if item["kind"] == "volume"]
    manifest = {
        "schema": 1,
        "stage": "sgz0-sanguozhi-processed-corpus",
        "processor": "scripts/build_sgz0_corpus.py",
        "work": "三國志",
        "primary_witness": "sanguozhi-kanripo-wyg",
        "witness_coverage": {
            "work": "三國志",
            "section": "魏書",
            "global_juan": "1-30",
            "section_juan": "1-30",
        },
        "source_registry": "sources/registry/sanguozhi.yaml",
        "observed_grammar": {
            "front_matter": "Org/Emacs properties before page markers",
            "volume_marker": "#+PROPERTY: JUAN 卷N",
            "main_author_marker": "陳壽撰",
            "annotation_author_marker": "裴松之注",
            "pei_annotation": "balanced one-level parenthesized spans",
            "physical_line_marker": "¶",
            "page_marker": "<pb:...>",
        },
        "local_payload_coverage": {
            "front_matter": 1 if any(item["kind"] == "front_matter" for item in records) else 0,
            "volumes": available_volumes,
            "registered_expected_volume_range": [1, 30],
            "missing_local_volumes": [item for item in range(1, 31) if item not in available_volumes],
            "note": "KR2a0012 is the registered 魏書 30卷 witness. SGZ1 supplies 蜀書 and 吳書 coverage; volumes outside 1–30 are not missing files from this witness.",
        },
        "volume_count": len(available_volumes),
        "main_text_unit_count": sum(item["layer_counts"]["main_text"] for item in records),
        "pei_annotation_unit_count": sum(item["layer_counts"]["pei_annotation"] for item in records),
        "records": records,
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lock = {
        "schema": 1,
        "stage": "sgz0-sanguozhi-source-provenance-lock",
        "witness_id": "sanguozhi-kanripo-wyg",
        "source_registry": "sources/registry/sanguozhi.yaml",
        "availability": "git-ignored-upstream-payload",
        "records": [
            {
                "source_path": item["source_path"],
                "source_sha256": item["source_sha256"],
                "witness_id": item["witness_id"],
                "file_number": item["file_number"],
                "juan": item["juan"],
                "availability": "git-ignored-upstream-payload",
            }
            for item in records
        ],
    }
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    manifest = build()
    print(
        f"built SGZ0: {manifest['volume_count']} volumes; "
        f"main={manifest['main_text_unit_count']}; pei={manifest['pei_annotation_unit_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
