#!/usr/bin/env python3
"""Segment the reviewed entry boundaries for Shishuo Xinyu 雅量第六.

The boundary manifest is the only source of entry boundaries.  This script
does not infer boundaries from physical lines or page markers.  It copies the
exact source span into every entry, then derives separate main-text,
top-level-parenthesis, and page-marker views from that span.
"""

from __future__ import annotations

import argparse
from bisect import bisect_right
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Sequence


DEFAULT_MANIFEST = Path("content/curated/shishuo/boundaries/06-yaliang.yaml")
DEFAULT_CHAPTER = Path("content/processed/shishuo/chapters/chapter-06.md")
DEFAULT_OUTPUT = Path("content/processed/shishuo/entries/06-yaliang")

PAGE_COMMENT_RE = re.compile(
    r"<!-- kanripo-page source-line=(?P<source_line>\d+): "
    r"(?P<marker><pb:[^>]+>) -->"
)


def _yaml_scalar(token: str) -> Any:
    token = token.strip()
    if token.startswith('"'):
        return json.loads(token)
    if token == "null":
        return None
    try:
        return int(token)
    except ValueError:
        return token


@dataclass(frozen=True)
class Boundary:
    entry_id: str
    ordinal: int
    opening_text: str
    source_normalized_line: int
    source_line: int | None
    source_page_marker: str
    confidence: str
    note: str = ""


@dataclass(frozen=True)
class SourceLine:
    start: int
    end: int
    normalized_line: int
    source_line: int
    page_marker: str
    text: str


@dataclass(frozen=True)
class ChapterMetadata:
    chapter_id: str
    heading: str
    source_chapter: str
    normalized_filename: str
    source_path: str
    source_sha256: str
    file_section: str
    title: str
    kanripo_id: str
    baseedition: str
    witness: str
    start_normalized_line: int
    start_source_line: int
    start_page_marker: str


@dataclass(frozen=True)
class AnnotationBlock:
    ordinal: int
    text: str
    start: int
    end: int
    source_line: int
    normalized_line: int
    page_marker: str


@dataclass(frozen=True)
class PageMarker:
    ordinal: int
    marker: str
    comment: str
    start: int
    end: int
    source_line: int
    normalized_line: int


@dataclass(frozen=True)
class Entry:
    boundary: Boundary
    start: int
    end: int
    source_text: str
    main_text: str
    annotations: tuple[AnnotationBlock, ...]
    page_markers: tuple[PageMarker, ...]
    start_line: SourceLine
    end_line: SourceLine


@dataclass(frozen=True)
class SegmentationResult:
    manifest_path: Path
    chapter_path: Path
    output_dir: Path
    metadata: ChapterMetadata
    chapter_frontmatter: str
    chapter_body: str
    prefix: str
    suffix: str
    entries: tuple[Entry, ...]
    source_body_sha256: str
    reconstructed_body_sha256: str
    source_body_bytes: int
    page_marker_count: int
    annotation_count: int


def _parse_manifest(path: Path) -> tuple[dict[str, Any], list[Boundary]]:
    """Read the deliberately small, review-oriented YAML manifest format."""

    top: dict[str, Any] = {}
    raw_entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith("  - "):
            if current is not None:
                raw_entries.append(current)
            current = {}
            key, separator, value = raw_line[4:].partition(":")
            if not separator:
                raise ValueError(f"invalid manifest entry at line {line_number}")
            current[key.strip()] = _yaml_scalar(value)
            continue
        if raw_line.startswith("    "):
            if current is None:
                raise ValueError(f"entry field outside entries at line {line_number}")
            key, separator, value = raw_line[4:].partition(":")
            if not separator:
                raise ValueError(f"invalid manifest field at line {line_number}")
            current[key.strip()] = _yaml_scalar(value)
            continue
        if raw_line.startswith("  "):
            raise ValueError(f"unsupported manifest indentation at line {line_number}")

        key, separator, value = raw_line.partition(":")
        if not separator:
            raise ValueError(f"invalid manifest field at line {line_number}")
        if key.strip() == "entries":
            continue
        top[key.strip()] = _yaml_scalar(value)

    if current is not None:
        raw_entries.append(current)

    required_top = {"schema", "chapter_id", "chapter_heading", "source_chapter"}
    missing_top = sorted(required_top - top.keys())
    if missing_top:
        raise ValueError(f"manifest is missing top-level fields: {', '.join(missing_top)}")

    boundaries: list[Boundary] = []
    for expected_ordinal, item in enumerate(raw_entries, start=1):
        required = {
            "id",
            "ordinal",
            "opening_text",
            "source_normalized_line",
            "boundary_confidence",
        }
        missing = sorted(required - item.keys())
        if missing:
            raise ValueError(
                f"manifest entry {expected_ordinal} is missing: {', '.join(missing)}"
            )
        boundary = Boundary(
            entry_id=str(item["id"]),
            ordinal=int(item["ordinal"]),
            opening_text=str(item["opening_text"]),
            source_normalized_line=int(item["source_normalized_line"]),
            source_line=(
                int(item["source_line"]) if item.get("source_line") is not None else None
            ),
            source_page_marker=str(item.get("source_page_marker", "")),
            confidence=str(item["boundary_confidence"]),
            note=str(item.get("note", "")),
        )
        if boundary.ordinal != expected_ordinal:
            raise ValueError(
                f"manifest ordinal {boundary.ordinal} is not {expected_ordinal}"
            )
        if not boundary.entry_id or not boundary.opening_text:
            raise ValueError(f"manifest entry {expected_ordinal} has an empty id or anchor")
        boundaries.append(boundary)

    if not boundaries:
        raise ValueError("manifest contains no entries")
    if len({boundary.entry_id for boundary in boundaries}) != len(boundaries):
        raise ValueError("manifest entry ids are not unique")
    return top, boundaries


def _split_frontmatter(text: str) -> tuple[str, str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("chapter source has no YAML front matter")
    closing_index = next(
        (index for index in range(1, len(lines)) if lines[index].strip() == "---"),
        None,
    )
    if closing_index is None:
        raise ValueError("chapter source has unterminated YAML front matter")
    body_start = closing_index + 1
    if body_start < len(lines) and lines[body_start].strip() == "":
        body_start += 1
    return "".join(lines[: closing_index + 1]), "".join(lines[body_start:])


def _quoted_field(frontmatter: str, field: str) -> str:
    match = re.search(rf"^{re.escape(field)}: (\".*\")$", frontmatter, re.MULTILINE)
    if match is None:
        raise ValueError(f"chapter front matter has no {field}")
    return str(json.loads(match.group(1)))


def _first_list_field(frontmatter: str, field: str) -> str:
    match = re.search(
        rf"^{re.escape(field)}:\n  - (\".*\")$",
        frontmatter,
        re.MULTILINE,
    )
    if match is None:
        raise ValueError(f"chapter front matter has no {field} list")
    return str(json.loads(match.group(1)))


def _read_chapter_metadata(
    frontmatter: str, manifest: dict[str, Any]
) -> ChapterMetadata:
    source_segment = re.search(
        r"source_segments:\n(?P<section>.*?)(?:\nboundary_status:|\n---$)",
        frontmatter,
        re.MULTILINE | re.DOTALL,
    )
    if source_segment is None:
        raise ValueError("chapter front matter has no source_segments")
    start = re.search(
        r"^    start:\n"
        r"      normalized_line: (\d+)\n"
        r"      source_line: (\d+)\n"
        r"      page_marker: (\".*\")$",
        source_segment.group("section"),
        re.MULTILINE,
    )
    if start is None:
        raise ValueError("chapter front matter has no source segment start")
    file_match = re.search(
        r"^    FILE: (\".*\")$", source_segment.group("section"), re.MULTILINE
    )
    if file_match is None:
        raise ValueError("chapter front matter has no FILE value")

    metadata = ChapterMetadata(
        chapter_id=str(manifest["chapter_id"]),
        heading=str(manifest["chapter_heading"]),
        source_chapter=str(manifest["source_chapter"]),
        normalized_filename=_first_list_field(frontmatter, "source_normalized_files"),
        source_path=_first_list_field(frontmatter, "source_paths"),
        source_sha256=_first_list_field(frontmatter, "source_sha256"),
        file_section=str(json.loads(file_match.group(1))),
        title=_quoted_field(frontmatter, "kanripo_title"),
        kanripo_id=_quoted_field(frontmatter, "kanripo_id"),
        baseedition=_quoted_field(frontmatter, "kanripo_baseedition"),
        witness=_quoted_field(frontmatter, "kanripo_witness"),
        start_normalized_line=int(start.group(1)),
        start_source_line=int(start.group(2)),
        start_page_marker=str(json.loads(start.group(3))),
    )
    if metadata.heading != _quoted_field(frontmatter, "canonical_heading"):
        raise ValueError("manifest chapter heading does not match chapter source")
    return metadata


def _build_source_lines(
    body: str, start_normalized_line: int, start_source_line: int, start_page_marker: str
) -> list[SourceLine]:
    result: list[SourceLine] = []
    offset = 0
    current_source_line = start_source_line
    current_page_marker = start_page_marker
    for index, raw_line in enumerate(body.splitlines(keepends=True)):
        line_text = raw_line[:-1] if raw_line.endswith("\n") else raw_line
        if line_text.endswith("\r"):
            line_text = line_text[:-1]
        page_match = PAGE_COMMENT_RE.fullmatch(line_text)
        if page_match is not None:
            source_line = int(page_match.group("source_line"))
            current_page_marker = page_match.group("marker")
        else:
            source_line = current_source_line
        result.append(
            SourceLine(
                start=offset,
                end=offset + len(raw_line),
                normalized_line=start_normalized_line + index,
                source_line=source_line,
                page_marker=current_page_marker,
                text=line_text,
            )
        )
        offset += len(raw_line)
        current_source_line = source_line + 1
    if not result:
        raise ValueError("chapter source body is empty")
    return result


def _line_at(lines: Sequence[SourceLine], offset: int) -> SourceLine:
    starts = [line.start for line in lines]
    index = bisect_right(starts, offset) - 1
    if index < 0:
        index = 0
    if index >= len(lines):
        index = len(lines) - 1
    return lines[index]


def _find_boundaries(
    body: str, boundaries: Sequence[Boundary], lines: Sequence[SourceLine]
) -> list[int]:
    positions: list[int] = []
    previous = -1
    for boundary in boundaries:
        matches: list[int] = []
        cursor = 0
        while True:
            position = body.find(boundary.opening_text, cursor)
            if position < 0:
                break
            matches.append(position)
            cursor = position + 1
        if len(matches) != 1:
            raise ValueError(
                f"anchor {boundary.entry_id} occurs {len(matches)} times; expected exactly once"
            )
        position = matches[0]
        if position <= previous:
            raise ValueError(f"anchor order is not increasing at {boundary.entry_id}")
        line = _line_at(lines, position)
        if line.normalized_line != boundary.source_normalized_line:
            raise ValueError(
                f"source normalized line mismatch for {boundary.entry_id}: "
                f"manifest {boundary.source_normalized_line}, actual {line.normalized_line}"
            )
        if boundary.source_line is not None and line.source_line != boundary.source_line:
            raise ValueError(
                f"source line mismatch for {boundary.entry_id}: "
                f"manifest {boundary.source_line}, actual {line.source_line}"
            )
        if boundary.source_page_marker and line.page_marker != boundary.source_page_marker:
            raise ValueError(
                f"page marker mismatch for {boundary.entry_id}: "
                f"manifest {boundary.source_page_marker}, actual {line.page_marker}"
            )
        positions.append(position)
        previous = position
    return positions


def _separate_structure(
    source: str,
    global_start: int,
    lines: Sequence[SourceLine],
) -> tuple[str, tuple[AnnotationBlock, ...], tuple[PageMarker, ...]]:
    annotations: list[AnnotationBlock] = []
    page_markers: list[PageMarker] = []
    excluded: list[tuple[int, int]] = []
    depth = 0
    annotation_start: int | None = None
    index = 0

    while index < len(source):
        page_match = PAGE_COMMENT_RE.match(source, index)
        if page_match is not None:
            if depth == 0:
                start = index
                end = page_match.end()
                absolute_line = _line_at(lines, global_start + start)
                page_markers.append(
                    PageMarker(
                        ordinal=len(page_markers) + 1,
                        marker=page_match.group("marker"),
                        comment=source[start:end],
                        start=start,
                        end=end,
                        source_line=int(page_match.group("source_line")),
                        normalized_line=absolute_line.normalized_line,
                    )
                )
                excluded.append((start, end))
            index = page_match.end()
            continue

        character = source[index]
        if character == "(":
            if depth == 0:
                annotation_start = index
            depth += 1
        elif character == ")":
            if depth == 0:
                absolute_line = _line_at(lines, global_start + index)
                raise ValueError(
                    "unmatched closing parenthesis at "
                    f"normalized line {absolute_line.normalized_line}"
                )
            depth -= 1
            if depth == 0:
                assert annotation_start is not None
                end = index + 1
                absolute_line = _line_at(lines, global_start + annotation_start)
                annotation = AnnotationBlock(
                    ordinal=len(annotations) + 1,
                    text=source[annotation_start:end],
                    start=annotation_start,
                    end=end,
                    source_line=absolute_line.source_line,
                    normalized_line=absolute_line.normalized_line,
                    page_marker=absolute_line.page_marker,
                )
                annotations.append(annotation)
                excluded.append((annotation_start, end))
                annotation_start = None
        index += 1

    if depth != 0:
        absolute_line = _line_at(lines, global_start + (annotation_start or 0))
        raise ValueError(
            "unmatched opening parenthesis at "
            f"normalized line {absolute_line.normalized_line}"
        )

    excluded.sort()
    main_parts: list[str] = []
    cursor = 0
    for start, end in excluded:
        if start < cursor:
            raise ValueError("overlapping structural spans")
        main_parts.append(source[cursor:start])
        cursor = end
    main_parts.append(source[cursor:])
    return "".join(main_parts), tuple(annotations), tuple(page_markers)


def _position_yaml(lines: list[str], label: str, line: SourceLine, indent: str = "  ") -> None:
    lines.extend(
        [
            f"{indent}{label}:",
            f"{indent}  normalized_line: {line.normalized_line}",
            f"{indent}  source_line: {line.source_line}",
            f"{indent}  page_marker: {json.dumps(line.page_marker, ensure_ascii=False)}",
        ]
    )


def _entry_frontmatter(entry: Entry, metadata: ChapterMetadata) -> str:
    start_line = entry.start_line
    end_line = entry.end_line
    lines = [
        "---",
        "schema: 1",
        "stage: entry-segmentation",
        "segment_type: \"shishuo-entry\"",
        f"entry_id: {json.dumps(entry.boundary.entry_id, ensure_ascii=False)}",
        f"ordinal: {entry.boundary.ordinal}",
        f"chapter_id: {json.dumps(metadata.chapter_id, ensure_ascii=False)}",
        f"chapter_heading: {json.dumps(metadata.heading, ensure_ascii=False)}",
        f"opening_text: {json.dumps(entry.boundary.opening_text, ensure_ascii=False)}",
        f"boundary_confidence: {json.dumps(entry.boundary.confidence, ensure_ascii=False)}",
        f"source_chapter: {json.dumps(metadata.source_chapter, ensure_ascii=False)}",
        f"source_normalized_filename: {json.dumps(metadata.normalized_filename, ensure_ascii=False)}",
        f"source_path: {json.dumps(metadata.source_path, ensure_ascii=False)}",
        f"source_sha256: {json.dumps(metadata.source_sha256, ensure_ascii=False)}",
        f"FILE: {json.dumps(metadata.file_section, ensure_ascii=False)}",
        f"kanripo_title: {json.dumps(metadata.title, ensure_ascii=False)}",
        f"kanripo_id: {json.dumps(metadata.kanripo_id, ensure_ascii=False)}",
        f"kanripo_baseedition: {json.dumps(metadata.baseedition, ensure_ascii=False)}",
        f"kanripo_witness: {json.dumps(metadata.witness, ensure_ascii=False)}",
        f"source_body_offset_start: {entry.start}",
        f"source_body_offset_end_exclusive: {entry.end}",
    ]
    _position_yaml(lines, "start", start_line)
    _position_yaml(lines, "end", end_line)
    lines.extend(
        [
            f"annotation_block_count: {len(entry.annotations)}",
            f"page_marker_count: {len(entry.page_markers)}",
            "source_section_exact: true",
            "entry_boundary_source: \"curated manifest exact anchor\"",
        ]
    )
    if entry.boundary.note:
        lines.append(f"boundary_note: {json.dumps(entry.boundary.note, ensure_ascii=False)}")
    lines.extend(["---", ""])
    return "\n".join(lines)


def _render_entry(entry: Entry, metadata: ChapterMetadata) -> str:
    lines = [_entry_frontmatter(entry, metadata), "## Original source (exact)", ""]
    lines.append(entry.source_text)
    if not entry.source_text.endswith("\n"):
        lines.append("")
    lines.extend(["## Main text", "", entry.main_text])
    if not entry.main_text.endswith("\n"):
        lines.append("")
    lines.extend(["## Top-level parenthetical annotation blocks", ""])
    if entry.annotations:
        for annotation in entry.annotations:
            lines.extend(
                [
                    f"### annotation-{annotation.ordinal:03d}",
                    f"entry_relative_start: {annotation.start}",
                    f"entry_relative_end_exclusive: {annotation.end}",
                    f"source_normalized_line: {annotation.normalized_line}",
                    f"source_line: {annotation.source_line}",
                    f"page_marker: {json.dumps(annotation.page_marker, ensure_ascii=False)}",
                    "",
                    annotation.text,
                    "",
                ]
            )
    else:
        lines.append("No top-level parenthetical annotation blocks.")
    lines.extend(["## Kanripo page markers", ""])
    if entry.page_markers:
        for marker in entry.page_markers:
            lines.extend(
                [
                    f"### page-marker-{marker.ordinal:03d}",
                    f"entry_relative_start: {marker.start}",
                    f"entry_relative_end_exclusive: {marker.end}",
                    f"marker: {json.dumps(marker.marker, ensure_ascii=False)}",
                    f"source_normalized_line: {marker.normalized_line}",
                    f"source_line: {marker.source_line}",
                    f"comment: {json.dumps(marker.comment, ensure_ascii=False)}",
                    "",
                ]
            )
    else:
        lines.append("No Kanripo page marker occurs inside this entry span.")
    return "\n".join(lines) + "\n"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _render_report(result: SegmentationResult) -> str:
    source_page_markers = list(PAGE_COMMENT_RE.finditer(result.chapter_body))
    entry_page_markers = sum(len(entry.page_markers) for entry in result.entries)
    context_page_markers = len(PAGE_COMMENT_RE.findall(result.prefix + result.suffix))
    reconstructed = result.prefix + "".join(entry.source_text for entry in result.entries) + result.suffix
    source_parentheses = result.chapter_body.count("(")
    source_closing_parentheses = result.chapter_body.count(")")
    lines = [
        "---",
        "schema: 1",
        "stage: entry-segmentation",
        "report_type: shishuo-entry-validation",
        f"chapter_source: {json.dumps(str(result.chapter_path), ensure_ascii=False)}",
        f"boundary_manifest: {json.dumps(str(result.manifest_path), ensure_ascii=False)}",
        f"entry_count: {len(result.entries)}",
        f"source_body_bytes: {result.source_body_bytes}",
        f"source_body_sha256: {json.dumps(result.source_body_sha256)}",
        f"reconstructed_body_sha256: {json.dumps(result.reconstructed_body_sha256)}",
        f"source_page_marker_count: {len(source_page_markers)}",
        f"entry_page_marker_count: {entry_page_markers}",
        f"context_page_marker_count: {context_page_markers}",
        f"source_parenthesis_open_count: {source_parentheses}",
        f"source_parenthesis_close_count: {source_closing_parentheses}",
        "text_conservation: passed",
        "parentheses_balanced: passed",
        "page_markers_traceable: passed",
        "manifest_boundaries: passed",
        "entry_segmentation: reviewed anchors only",
        "relationship_extraction: not performed",
        "---",
        "",
        "# 雅量第六 entry-segmentation validation",
        "",
        "The chapter source is read-only. Entry spans are cut only at the exact "
        "opening-text anchors in the curated manifest; physical line breaks and "
        "Kanripo page markers do not define entries.",
        "",
        "## Conservation checks",
        "",
        f"- Entries: {len(result.entries)}",
        f"- Source body bytes: {result.source_body_bytes}",
        f"- Source and reconstructed SHA-256 equal: "
        f"{result.source_body_sha256 == result.reconstructed_body_sha256}",
        f"- Page markers in chapter body: {len(source_page_markers)}",
        f"- Page markers in entry spans: {entry_page_markers}",
        f"- Page markers in unsegmented context: {context_page_markers}",
        f"- Parenthesis pairs: {source_parentheses}",
        "",
        "## Entries",
        "",
        "| # | Entry id | Opening anchor | Start | End | Annotations | Page markers | Confidence |",
        "|---:|---|---|---|---|---:|---:|---|",
    ]
    for entry in result.entries:
        boundary = entry.boundary
        start = (
            f"normalized-line={entry.start_line.normalized_line};"
            f"source-line={entry.start_line.source_line};"
            f"page={entry.start_line.page_marker}"
        )
        end = (
            f"normalized-line={entry.end_line.normalized_line};"
            f"source-line={entry.end_line.source_line};"
            f"page={entry.end_line.page_marker}"
        )
        lines.append(
            f"| {boundary.ordinal} | {boundary.entry_id} | {boundary.opening_text} | "
            f"{start} | {end} | {len(entry.annotations)} | "
            f"{len(entry.page_markers)} | {boundary.confidence} |"
        )
    lines.extend(
        [
            "",
            "## Reviewed boundary notes",
            "",
            "- The 郗太傅在京口... / 東床坦腹 entry is entry 019 and is kept as one span.",
            "- Entry 032 begins mid-normalized line 741; this confirms that a physical "
            "line break is not being used as an entry boundary.",
            "- Parentheses are balanced structurally at depth zero; nested parentheses "
            "remain inside their top-level annotation block.",
            "",
        ]
    )
    return "\n".join(lines)


def segment_entries(
    manifest_path: Path | str = DEFAULT_MANIFEST,
    chapter_path: Path | str = DEFAULT_CHAPTER,
    output_dir: Path | str = DEFAULT_OUTPUT,
) -> SegmentationResult:
    manifest_file = Path(manifest_path)
    chapter_file = Path(chapter_path)
    output_root = Path(output_dir)
    manifest, boundaries = _parse_manifest(manifest_file)
    chapter_text = chapter_file.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(chapter_text)
    metadata = _read_chapter_metadata(frontmatter, manifest)
    lines = _build_source_lines(
        body,
        metadata.start_normalized_line,
        metadata.start_source_line,
        metadata.start_page_marker,
    )
    positions = _find_boundaries(body, boundaries, lines)
    spans = list(zip(positions, positions[1:] + [len(body)]))

    entries: list[Entry] = []
    for boundary, (start, end) in zip(boundaries, spans):
        source_text = body[start:end]
        start_line = _line_at(lines, start)
        end_line = _line_at(lines, max(start, end - 1))
        main_text, annotations, page_markers = _separate_structure(
            source_text, start, lines
        )
        if not source_text.startswith(boundary.opening_text):
            raise ValueError(f"entry {boundary.entry_id} does not start with its anchor")
        entries.append(
            Entry(
                boundary=boundary,
                start=start,
                end=end,
                source_text=source_text,
                main_text=main_text,
                annotations=annotations,
                page_markers=page_markers,
                start_line=start_line,
                end_line=end_line,
            )
        )

    prefix = body[: positions[0]]
    suffix = body[spans[-1][1] :]
    reconstructed = prefix + "".join(entry.source_text for entry in entries) + suffix
    if reconstructed != body:
        raise ValueError("source text was lost while reconstructing entry spans")
    if hashlib.sha256(reconstructed.encode("utf-8")).hexdigest() != hashlib.sha256(
        body.encode("utf-8")
    ).hexdigest():
        raise ValueError("source reconstruction hash mismatch")

    source_page_markers = list(PAGE_COMMENT_RE.finditer(body))
    entry_page_markers = sum(len(entry.page_markers) for entry in entries)
    context_page_markers = len(PAGE_COMMENT_RE.findall(prefix + suffix))
    if entry_page_markers + context_page_markers != len(source_page_markers):
        raise ValueError("not all Kanripo page markers are traceable")

    output_root.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        _write_text(
            output_root / f"entry-{entry.boundary.ordinal:03d}.md",
            _render_entry(entry, metadata),
        )
    _write_text(output_root / "unsegmented-prefix.md", prefix)
    _write_text(output_root / "unsegmented-suffix.md", suffix)

    source_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    result = SegmentationResult(
        manifest_path=manifest_file,
        chapter_path=chapter_file,
        output_dir=output_root,
        metadata=metadata,
        chapter_frontmatter=frontmatter,
        chapter_body=body,
        prefix=prefix,
        suffix=suffix,
        entries=tuple(entries),
        source_body_sha256=source_hash,
        reconstructed_body_sha256=hashlib.sha256(reconstructed.encode("utf-8")).hexdigest(),
        source_body_bytes=len(body.encode("utf-8")),
        page_marker_count=len(source_page_markers),
        annotation_count=sum(len(entry.annotations) for entry in entries),
    )
    _write_text(output_root / "validation-report.md", _render_report(result))
    return result


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--chapter", type=Path, default=DEFAULT_CHAPTER)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    try:
        result = segment_entries(args.manifest, args.chapter, args.output_dir)
    except (OSError, UnicodeDecodeError, ValueError) as error:
        parser.error(str(error))
        return 2
    print(f"entries: {len(result.entries)}")
    print(f"annotations: {result.annotation_count}")
    print(f"page markers: {result.page_marker_count}")
    print(f"output: {result.output_dir}")
    print(f"validation report: {result.output_dir / 'validation-report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
