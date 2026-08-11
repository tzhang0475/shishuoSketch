#!/usr/bin/env python3
"""Materialize the frozen, reviewed Shishuo Xinyu entry corpus.

This script treats the chapter manifests as the complete boundary authority.
It never infers a boundary from a line break or a page marker.  Existing entry
directories are validated but not rewritten; only missing chapter directories
are materialized.  The six explicit same-edition supplement segments remain
separate from the primary Kanripo spans.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable

import yaml

try:  # Import works both as a repository module and as a script.
    from scripts import segment_shishuo_entries as segmentation
except ImportError:  # pragma: no cover - exercised when run directly
    import segment_shishuo_entries as segmentation


REPO_ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_ROOT = REPO_ROOT / "content/curated/shishuo/boundaries"
CHAPTER_ROOT = REPO_ROOT / "content/processed/shishuo/chapters"
ENTRY_ROOT = REPO_ROOT / "content/processed/shishuo/entries"
SUPPLEMENT_PATH = REPO_ROOT / "content/curated/shishuo/collation/supplemented-segments.yaml"
INDEX_PATH = REPO_ROOT / "data/shishuo-corpus-index.json"

ENTRY_FILE_RE = re.compile(r"entry-(?P<ordinal>\d{3})\.md\Z")


@dataclass(frozen=True)
class ChapterMaterial:
    manifest_path: Path
    chapter_path: Path
    document: dict[str, Any]
    metadata: segmentation.ChapterMetadata
    body: str
    lines: list[segmentation.SourceLine]
    positions: dict[str, int]
    primary_entries: tuple[dict[str, Any], ...]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected YAML mapping: {path}")
    return value


def _split_entry_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("entry has no YAML front matter")
    closing = next(
        (index for index in range(1, len(lines)) if lines[index].strip() == "---"),
        None,
    )
    if closing is None:
        raise ValueError("entry front matter is unterminated")
    # The historical renderer stores the human-readable ``start`` and
    # ``end`` provenance blocks at two-space indentation without a wrapper
    # mapping.  That is valid for the repository's front-matter convention,
    # but not for a strict YAML document.  Parse root fields individually and
    # leave those nested display blocks untouched.
    value: dict[str, Any] = {}
    for raw_line in lines[1:closing]:
        if not raw_line.strip() or raw_line[0].isspace():
            continue
        key, separator, token = raw_line.rstrip("\r\n").partition(":")
        if not separator:
            continue
        value[key.strip()] = yaml.safe_load(token.strip()) if token.strip() else None
    return value, "".join(lines[closing + 1 :])


def _entry_original_source(rest: str, expected: str | None = None) -> str:
    marker = "## Original source (exact)\n\n"
    if marker not in rest:
        raise ValueError("primary entry has no exact source section")
    start = rest.index(marker) + len(marker)
    end_marker = "\n## Main text\n\n"
    end = rest.find(end_marker, start)
    if end < 0:
        raise ValueError("primary entry has no main-text section")
    source = rest[start:end]
    # Renderers add a Markdown separator newline when an exact source span
    # does not itself end in one.  If the caller knows the expected immutable
    # span, remove only that separator and never a source newline.
    if expected is not None and source != expected:
        if source.endswith("\n") and source[:-1] == expected:
            return expected
    return source


def _chapter_number(chapter_id: str) -> int:
    match = re.match(r"^(\d+)-", chapter_id)
    if match is None:
        raise ValueError(f"chapter id has no canonical number: {chapter_id}")
    return int(match.group(1))


def _manifest_entries(document: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    entries = document.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"manifest has no entries: {path}")
    expected_ids: list[str] = []
    for expected_ordinal, item in enumerate(entries, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"manifest entry is not a mapping: {path}:{expected_ordinal}")
        if int(item.get("ordinal", -1)) != expected_ordinal:
            raise ValueError(f"non-continuous ordinal in {path}: {item.get('ordinal')}")
        entry_id = str(item.get("id", ""))
        chapter_id = str(document.get("chapter_id", ""))
        if entry_id != f"{chapter_id}-{expected_ordinal:03d}":
            raise ValueError(f"non-canonical entry id in {path}: {entry_id}")
        if not str(item.get("opening_text", "")):
            raise ValueError(f"empty opening anchor in {path}:{expected_ordinal}")
        expected_ids.append(entry_id)
    if len(expected_ids) != len(set(expected_ids)):
        raise ValueError(f"duplicate entry id in {path}")
    return entries


def _find_anchor(body: str, anchor: str, entry_id: str) -> int:
    positions: list[int] = []
    cursor = 0
    while True:
        position = body.find(anchor, cursor)
        if position < 0:
            break
        positions.append(position)
        cursor = position + 1
    if len(positions) != 1:
        raise ValueError(f"anchor {entry_id} occurs {len(positions)} times")
    return positions[0]


def _load_supplements() -> dict[str, dict[str, Any]]:
    if not SUPPLEMENT_PATH.exists():
        return {}
    document = _load_yaml(SUPPLEMENT_PATH)
    segments = document.get("segments", [])
    if not isinstance(segments, list):
        raise ValueError("supplement manifest segments is not a list")
    result: dict[str, dict[str, Any]] = {}
    for segment in segments:
        if not isinstance(segment, dict):
            raise ValueError("supplement segment is not a mapping")
        entry_id = str(segment.get("canonical_entry_id", ""))
        text = str(segment.get("exact_text", ""))
        if not entry_id or not text:
            raise ValueError("supplement segment lacks id or exact text")
        if _sha256_text(text) != str(segment.get("exact_text_sha256", "")):
            raise ValueError(f"supplement text hash mismatch: {entry_id}")
        if segment.get("primary_witness_status") != "gap":
            raise ValueError(f"supplement is not marked as a primary gap: {entry_id}")
        if entry_id in result:
            raise ValueError(f"duplicate supplement: {entry_id}")
        result[entry_id] = segment
    return result


def _chapter_material(manifest_path: Path, supplements: dict[str, dict[str, Any]]) -> ChapterMaterial:
    document = _load_yaml(manifest_path)
    chapter_id = str(document.get("chapter_id", ""))
    if not chapter_id:
        raise ValueError(f"manifest has no chapter_id: {manifest_path}")
    entries = _manifest_entries(document, manifest_path)
    chapter_path = REPO_ROOT / str(document.get("source_chapter", ""))
    if not chapter_path.exists():
        raise FileNotFoundError(chapter_path)
    chapter_text = chapter_path.read_text(encoding="utf-8")
    frontmatter, body = segmentation._split_frontmatter(chapter_text)
    metadata = segmentation._read_chapter_metadata(frontmatter, document)
    lines = segmentation._build_source_lines(
        body,
        metadata.start_normalized_line,
        metadata.start_source_line,
        metadata.start_page_marker,
    )

    positions: dict[str, int] = {}
    previous = -1
    primary_entries: list[dict[str, Any]] = []
    for item in entries:
        entry_id = str(item["id"])
        is_gap = item.get("primary_witness_status") == "gap"
        if is_gap:
            supplement = supplements.get(entry_id)
            if supplement is None:
                raise ValueError(f"manifest gap has no supplement record: {entry_id}")
            if str(item.get("supplement_witness")) != str(supplement.get("supplement_witness")):
                raise ValueError(f"supplement witness mismatch: {entry_id}")
            continue
        position = _find_anchor(body, str(item["opening_text"]), entry_id)
        if position <= previous:
            raise ValueError(f"manifest anchors are not ordered: {entry_id}")
        line = segmentation._line_at(lines, position)
        if int(item["source_normalized_line"]) != line.normalized_line:
            raise ValueError(
                f"normalized line mismatch for {entry_id}: "
                f"manifest={item['source_normalized_line']} actual={line.normalized_line}"
            )
        # Some proposal manifests retain the raw source-line estimate from
        # before page-marker comments were represented in the chapter.  The
        # normalized line and page marker are checked here; the entry output
        # records the actual source line resolved from the immutable chapter.
        if item.get("source_page_marker") and str(item["source_page_marker"]) != line.page_marker:
            raise ValueError(f"page marker mismatch for {entry_id}")
        positions[entry_id] = position
        previous = position
        primary_entries.append(item)

    for item in entries:
        if item.get("primary_witness_status") == "gap":
            continue
        entry_id = str(item["id"])
        if entry_id not in positions:
            raise ValueError(f"missing source position: {entry_id}")

    return ChapterMaterial(
        manifest_path=manifest_path,
        chapter_path=chapter_path,
        document=document,
        metadata=metadata,
        body=body,
        lines=lines,
        positions=positions,
        primary_entries=tuple(primary_entries),
    )


def _boundary(item: dict[str, Any]) -> segmentation.Boundary:
    return segmentation.Boundary(
        entry_id=str(item["id"]),
        ordinal=int(item["ordinal"]),
        opening_text=str(item["opening_text"]),
        source_normalized_line=int(item["source_normalized_line"]),
        source_line=(int(item["source_line"]) if item.get("source_line") is not None else None),
        source_page_marker=str(item.get("source_page_marker") or ""),
        confidence=str(item.get("boundary_confidence", "high")),
        note=str(item.get("note", "")),
    )


def _source_spans(material: ChapterMaterial) -> dict[str, tuple[int, int]]:
    ordered = sorted(material.primary_entries, key=lambda item: material.positions[str(item["id"])])
    spans: dict[str, tuple[int, int]] = {}
    for index, item in enumerate(ordered):
        start = material.positions[str(item["id"])]
        end = (
            material.positions[str(ordered[index + 1]["id"])]
            if index + 1 < len(ordered)
            else len(material.body)
        )
        if end <= start:
            raise ValueError(f"empty primary source span: {item['id']}")
        spans[str(item["id"])] = (start, end)
    return spans


def _render_validation_report(
    material: ChapterMaterial,
    entries: list[dict[str, Any]],
    spans: dict[str, tuple[int, int]],
    prefix: str,
    suffix: str,
) -> str:
    body = material.body
    primary_count = len(spans)
    supplement_count = len(entries) - primary_count
    partial_count = sum(1 for item in entries if item.get("primary_witness_status") == "partial")
    entry_page_markers = sum(
        len(segmentation.PAGE_COMMENT_RE.findall(body[start:end]))
        for start, end in spans.values()
    )
    reconstructed = prefix + "".join(body[start:end] for start, end in sorted(spans.values())) + suffix
    lines = [
        "---",
        "schema: 1",
        "stage: entry-segmentation-materialization",
        f"chapter: {json.dumps(str(material.document['chapter_id']), ensure_ascii=False)}",
        f"boundary_manifest: {json.dumps(str(material.manifest_path.relative_to(REPO_ROOT)), ensure_ascii=False)}",
        f"entry_count: {len(entries)}",
        f"primary_source_entry_count: {primary_count}",
        f"supplement_entry_count: {supplement_count}",
        f"partial_primary_entry_count: {partial_count}",
        f"source_body_sha256: {json.dumps(_sha256_text(body))}",
        f"reconstructed_body_sha256: {json.dumps(_sha256_text(reconstructed))}",
        f"source_page_marker_count: {len(segmentation.PAGE_COMMENT_RE.findall(body))}",
        f"entry_page_marker_count: {entry_page_markers}",
        f"source_parenthesis_open_count: {body.count('(')}",
        f"source_parenthesis_close_count: {body.count(')')}",
        "text_conservation: passed",
        "parentheses_balanced: passed",
        "page_markers_traceable: passed",
        "manifest_boundaries: passed",
        "raw_primary_witness_modified: false",
        "relationship_extraction: not performed",
        "---",
        "",
        f"# {material.metadata.heading} entry materialization validation",
        "",
        "Primary source spans are cut only at the exact anchors in the reviewed canonical manifest. Physical line breaks and Kanripo page markers are not entry boundaries.",
        "",
        f"- Entries: {len(entries)}",
        f"- Primary source spans: {primary_count}",
        f"- Explicit supplement segments: {supplement_count}",
        f"- Source and reconstructed SHA-256 equal: {_sha256_text(body) == _sha256_text(reconstructed)}",
        f"- Parenthesis pairs: {body.count('(')}",
        f"- Kanripo page markers: {len(segmentation.PAGE_COMMENT_RE.findall(body))}",
        "",
    ]
    return "\n".join(lines)


def _add_frontmatter_field(base: str, key: str, value: Any) -> str:
    """Add one deterministic field to an already-rendered entry front matter."""

    lines = base.splitlines(keepends=True)
    closing = next(
        (index for index in range(1, len(lines)) if lines[index].strip() == "---"),
        None,
    )
    if closing is None:
        raise ValueError("cannot add frontmatter field to entry without closing marker")
    if isinstance(value, bool):
        rendered = "true" if value else "false"
    elif isinstance(value, int):
        rendered = str(value)
    else:
        rendered = json.dumps(str(value), ensure_ascii=False)
    lines.insert(closing, f"{key}: {rendered}\n")
    return "".join(lines)


def _write_new_chapter(material: ChapterMaterial, supplements: dict[str, dict[str, Any]]) -> None:
    output_dir = ENTRY_ROOT / str(material.document["chapter_id"])
    if output_dir.exists():
        raise FileExistsError(f"refusing to rewrite existing entry directory: {output_dir}")
    entries = _manifest_entries(material.document, material.manifest_path)
    if any(item.get("primary_witness_status") == "gap" for item in entries):
        raise ValueError("new-chapter materializer does not emit supplement overlays")
    spans = _source_spans(material)
    first_start = min(start for start, _end in spans.values())
    last_end = max(end for _start, end in spans.values())
    prefix = material.body[:first_start]
    suffix = material.body[last_end:]
    reconstructed = prefix + "".join(
        material.body[start:end] for start, end in sorted(spans.values())
    ) + suffix
    if reconstructed != material.body:
        raise ValueError(f"source conservation failed before writing: {material.document['chapter_id']}")

    rendered: dict[str, str] = {}
    for item in entries:
        entry_id = str(item["id"])
        start, end = spans[entry_id]
        source_text = material.body[start:end]
        anchor = str(item["opening_text"])
        anchor_crosses_source_end = not source_text.startswith(anchor)
        if anchor_crosses_source_end and not material.body[start:].startswith(anchor):
            raise ValueError(f"entry does not start with manifest anchor: {entry_id}")
        main_text, annotations, page_markers = segmentation._separate_structure(
            source_text, start, material.lines
        )
        entry = segmentation.Entry(
            boundary=_boundary(item),
            start=start,
            end=end,
            source_text=source_text,
            main_text=main_text,
            annotations=annotations,
            page_markers=page_markers,
            start_line=segmentation._line_at(material.lines, start),
            end_line=segmentation._line_at(material.lines, max(start, end - 1)),
        )
        entry_text = segmentation._render_entry(
            entry, material.metadata
        )
        if anchor_crosses_source_end:
            entry_text = _add_frontmatter_field(
                entry_text, "boundary_anchor_crosses_source_end", True
            )
        rendered[f"entry-{int(item['ordinal']):03d}.md"] = entry_text

    output_dir.mkdir(parents=True, exist_ok=False)
    for filename, text in rendered.items():
        (output_dir / filename).write_text(text, encoding="utf-8", newline="\n")
    (output_dir / "unsegmented-prefix.md").write_text(prefix, encoding="utf-8", newline="\n")
    (output_dir / "unsegmented-suffix.md").write_text(suffix, encoding="utf-8", newline="\n")
    (output_dir / "validation-report.md").write_text(
        _render_validation_report(material, entries, spans, prefix, suffix),
        encoding="utf-8",
        newline="\n",
    )


def _validate_entry_directory(
    material: ChapterMaterial,
    supplements: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    output_dir = ENTRY_ROOT / str(material.document["chapter_id"])
    if not output_dir.is_dir():
        raise FileNotFoundError(f"missing entry directory: {output_dir}")
    manifest_entries = _manifest_entries(material.document, material.manifest_path)
    expected_ordinals = {int(item["ordinal"]) for item in manifest_entries}
    files: dict[int, Path] = {}
    for path in output_dir.glob("entry-*.md"):
        match = ENTRY_FILE_RE.fullmatch(path.name)
        if match is None:
            raise ValueError(f"unexpected entry filename: {path}")
        ordinal = int(match.group("ordinal"))
        if ordinal in files:
            raise ValueError(f"duplicate entry file: {path}")
        files[ordinal] = path
    if set(files) != expected_ordinals:
        raise ValueError(
            f"entry file ordinals differ in {output_dir}: "
            f"expected={sorted(expected_ordinals)} actual={sorted(files)}"
        )

    by_id = {str(item["id"]): item for item in manifest_entries}
    source_spans: dict[str, tuple[int, int]] = {}
    for ordinal in sorted(files):
        path = files[ordinal]
        frontmatter, rest = _split_entry_frontmatter(path.read_text(encoding="utf-8"))
        entry_id = str(frontmatter.get("entry_id", ""))
        item = by_id.get(entry_id)
        if item is None or int(item["ordinal"]) != ordinal:
            raise ValueError(f"entry metadata does not match manifest: {path}")
        if str(frontmatter.get("opening_text", item["opening_text"])) != str(item["opening_text"]):
            raise ValueError(f"opening anchor changed in {path}")
        is_gap = item.get("primary_witness_status") == "gap"
        if is_gap:
            supplement = supplements.get(entry_id)
            if supplement is None:
                raise ValueError(f"missing supplement for {entry_id}")
            exact_text = str(supplement["exact_text"])
            if exact_text not in path.read_text(encoding="utf-8"):
                raise ValueError(f"supplement text missing from {path}")
            if frontmatter.get("primary_witness_status") != "gap":
                raise ValueError(f"gap status missing from {path}")
            if frontmatter.get("supplement_witness") != supplement.get("supplement_witness"):
                raise ValueError(f"supplement witness missing or changed in {path}")
            if frontmatter.get("reason") != "kanripo_digitization_gap":
                raise ValueError(f"supplement reason missing from {path}")
            continue

        start = frontmatter.get("source_body_offset_start")
        end = frontmatter.get("source_body_offset_end_exclusive")
        if not isinstance(start, int) or not isinstance(end, int) or end <= start:
            raise ValueError(f"invalid source span in {path}")
        if end > len(material.body):
            raise ValueError(f"source span exceeds chapter body in {path}")
        source_text = _entry_original_source(rest, material.body[start:end])
        if source_text != material.body[start:end]:
            raise ValueError(f"primary source text differs from chapter source in {path}")
        anchor = str(item["opening_text"])
        anchor_crosses_source_end = not source_text.startswith(anchor)
        if anchor_crosses_source_end and not material.body[start:].startswith(anchor):
            raise ValueError(f"primary entry anchor is not at span start in {path}")
        if anchor_crosses_source_end and frontmatter.get("boundary_anchor_crosses_source_end") is not True:
            raise ValueError(f"cross-boundary anchor is not explicitly recorded in {path}")
        source_spans[entry_id] = (start, end)
        segmentation._separate_structure(source_text, start, material.lines)

    if not source_spans:
        raise ValueError(f"no primary source spans in {output_dir}")
    ordered_spans = sorted(source_spans.values())
    first_start = ordered_spans[0][0]
    last_end = ordered_spans[-1][1]
    prefix_path = output_dir / "unsegmented-prefix.md"
    suffix_path = output_dir / "unsegmented-suffix.md"
    if not prefix_path.exists() or not suffix_path.exists():
        raise ValueError(f"unsegmented context files missing in {output_dir}")
    prefix = prefix_path.read_text(encoding="utf-8")
    suffix = suffix_path.read_text(encoding="utf-8")
    if prefix != material.body[:first_start] or suffix != material.body[last_end:]:
        raise ValueError(f"unsegmented context differs from chapter source in {output_dir}")
    reconstructed = prefix + "".join(material.body[start:end] for start, end in ordered_spans) + suffix
    if reconstructed != material.body:
        raise ValueError(f"primary source spans do not conserve chapter text in {output_dir}")
    if _sha256_text(reconstructed) != _sha256_text(material.body):
        raise ValueError(f"primary source reconstruction hash mismatch in {output_dir}")

    source_markers = len(segmentation.PAGE_COMMENT_RE.findall(material.body))
    reconstructed_markers = sum(
        len(segmentation.PAGE_COMMENT_RE.findall(material.body[start:end]))
        for start, end in ordered_spans
    ) + len(segmentation.PAGE_COMMENT_RE.findall(prefix + suffix))
    if source_markers != reconstructed_markers:
        raise ValueError(f"page markers are not traceable in {output_dir}")
    if material.body.count("(") != material.body.count(")"):
        raise ValueError(f"chapter parentheses are not balanced: {material.chapter_path}")

    report_path = output_dir / "validation-report.md"
    if not report_path.exists():
        raise ValueError(f"validation report missing in {output_dir}")
    report_frontmatter, _report_rest = _split_entry_frontmatter(
        report_path.read_text(encoding="utf-8")
    )
    if report_frontmatter.get("source_body_sha256") != _sha256_text(material.body):
        raise ValueError(f"validation report source hash mismatch in {output_dir}")
    if report_frontmatter.get("reconstructed_body_sha256") != _sha256_text(material.body):
        raise ValueError(f"validation report reconstruction hash mismatch in {output_dir}")

    return {
        "entry_count": len(manifest_entries),
        "primary_source_entry_count": len(source_spans),
        "supplement_entry_count": len(manifest_entries) - len(source_spans),
        "source_body_sha256": _sha256_text(material.body),
        "source_body_bytes": len(material.body.encode("utf-8")),
    }


def _entry_file_records(
    material: ChapterMaterial,
    supplements: dict[str, dict[str, Any]],
    global_start: int,
) -> list[dict[str, Any]]:
    output_dir = ENTRY_ROOT / str(material.document["chapter_id"])
    records: list[dict[str, Any]] = []
    for item in _manifest_entries(material.document, material.manifest_path):
        ordinal = int(item["ordinal"])
        path = output_dir / f"entry-{ordinal:03d}.md"
        frontmatter, _rest = _split_entry_frontmatter(path.read_text(encoding="utf-8"))
        record: dict[str, Any] = {
            "id": str(item["id"]),
            "ordinal": ordinal,
            "global_ordinal": global_start + ordinal,
            "path": str(path.relative_to(REPO_ROOT)),
            "opening_text": str(item["opening_text"]),
            "boundary_confidence": str(item.get("boundary_confidence", "")),
            "review_status": str(item.get("review_status", "")),
            "source_normalized_line": item.get("source_normalized_line"),
            "source_line": item.get("source_line"),
            "source_page_marker": item.get("source_page_marker"),
            "primary_witness_status": str(
                frontmatter.get("primary_witness_status", item.get("primary_witness_status", "present"))
            ),
            "entry_sha256": _sha256_bytes(path.read_bytes()),
        }
        if "source_body_offset_start" in frontmatter:
            record["source_body_offset_start"] = frontmatter["source_body_offset_start"]
            record["source_body_offset_end_exclusive"] = frontmatter["source_body_offset_end_exclusive"]
        if frontmatter.get("boundary_anchor_crosses_source_end") is True:
            record["boundary_anchor_crosses_source_end"] = True
        if record["primary_witness_status"] == "gap":
            supplement = supplements[str(item["id"])]
            source = supplement.get("source", {})
            record["supplement"] = {
                "witness_id": supplement.get("supplement_witness"),
                "reason": supplement.get("reason"),
                "exact_text_sha256": supplement.get("exact_text_sha256"),
                "source_manifest": source.get("manifest"),
                "source_url": source.get("source_url"),
                "source_revision_id": source.get("revision_id"),
                "locations": source.get("locations", []),
            }
        records.append(record)
    return records


def _manifest_paths() -> list[Path]:
    paths = sorted(BOUNDARY_ROOT.glob("*.yaml"), key=lambda path: _chapter_number(path.stem))
    if len(paths) != 36:
        raise ValueError(f"expected 36 chapter manifests, found {len(paths)}")
    return paths


def validate_corpus() -> dict[str, Any]:
    supplements = _load_supplements()
    paths = _manifest_paths()
    materials = [_chapter_material(path, supplements) for path in paths]
    expected_chapters = {str(material.document["chapter_id"]) for material in materials}
    actual_chapters = {path.name for path in ENTRY_ROOT.iterdir() if path.is_dir()}
    if actual_chapters != expected_chapters:
        raise ValueError(
            f"entry directory set differs: missing={sorted(expected_chapters - actual_chapters)} "
            f"extra={sorted(actual_chapters - expected_chapters)}"
        )

    all_ids: list[str] = []
    chapter_reports: list[dict[str, Any]] = []
    entry_records: list[dict[str, Any]] = []
    global_start = 0
    for material in materials:
        report = _validate_entry_directory(material, supplements)
        chapter_reports.append(
            {
                "id": str(material.document["chapter_id"]),
                "heading": str(material.document["chapter_heading"]),
                "entry_count": report["entry_count"],
                "entry_directory": str((ENTRY_ROOT / str(material.document["chapter_id"])).relative_to(REPO_ROOT)),
                "source_chapter": str(material.chapter_path.relative_to(REPO_ROOT)),
                "source_body_sha256": report["source_body_sha256"],
                "source_body_bytes": report["source_body_bytes"],
                "primary_source_entry_count": report["primary_source_entry_count"],
                "supplement_entry_count": report["supplement_entry_count"],
            }
        )
        records = _entry_file_records(material, supplements, global_start)
        entry_records.extend(records)
        all_ids.extend(record["id"] for record in records)
        global_start += len(records)

    if len(all_ids) != 1130:
        raise ValueError(f"expected 1130 entries, found {len(all_ids)}")
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("duplicate canonical entry ids")
    expected_global = list(range(1, 1131))
    if [record["global_ordinal"] for record in entry_records] != expected_global:
        raise ValueError("global canonical ordinals are not continuous")
    expected_supplements = {
        "05-fangzheng-014",
        "08-shangyu-084",
        "08-shangyu-085",
        "18-qiyi-002",
        "18-qiyi-011",
        "19-xianyuan-005",
    }
    actual_supplements = {
        record["id"] for record in entry_records if record["primary_witness_status"] == "gap"
    }
    if actual_supplements != expected_supplements:
        raise ValueError(f"supplement set differs: {sorted(actual_supplements)}")

    return {
        "chapter_count": len(chapter_reports),
        "entry_count": len(entry_records),
        "supplement_count": len(actual_supplements),
        "chapters": chapter_reports,
        "entries": entry_records,
    }


def build_index(validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": 1,
        "stage": "frozen-canonical-entry-corpus",
        "work": "世説新語",
        "structure_status": "reviewed-canonical",
        "boundary_inference": False,
        "entity_extraction": False,
        "relationship_extraction": False,
        "primary_witness": "shishuo-kanripo-wyg",
        "chapter_count": validation["chapter_count"],
        "entry_count": validation["entry_count"],
        "supplemented_entry_count": validation["supplement_count"],
        "chapters": validation["chapters"],
        "entries": validation["entries"],
    }


def materialize_missing() -> list[str]:
    supplements = _load_supplements()
    created: list[str] = []
    for manifest_path in _manifest_paths():
        material = _chapter_material(manifest_path, supplements)
        output_dir = ENTRY_ROOT / str(material.document["chapter_id"])
        if output_dir.exists():
            continue
        _write_new_chapter(material, supplements)
        created.append(str(material.document["chapter_id"]))
    return created


def write_index(validation: dict[str, Any]) -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(
        json.dumps(build_index(validation), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the materialized corpus without writing entries or the index",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_argument_parser().parse_args(list(argv) if argv is not None else None)
    try:
        created = [] if args.check else materialize_missing()
        validation = validate_corpus()
        if not args.check:
            write_index(validation)
    except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError) as error:
        print(f"materialization failed: {error}", file=sys.stderr)
        return 2
    print(f"chapters materialized: {len(created)}")
    if created:
        print("created: " + ", ".join(created))
    print(f"chapters validated: {validation['chapter_count']}")
    print(f"entries validated: {validation['entry_count']}")
    print(f"supplements validated: {validation['supplement_count']}")
    if not args.check:
        print(f"index: {INDEX_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
