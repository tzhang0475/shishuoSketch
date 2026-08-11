#!/usr/bin/env python3
"""Deterministically segment normalized Shishuo Xinyu Markdown.

This stage reads only ``content/processed/shishuo/*.md`` and writes semantic
segments below ``chapters/`` and ``editorial/``.  It never edits the normalized
inputs.  FILE comments determine concatenated source sections; only explicit
canonical chapter headings in sections classified as main text are used as
chapter boundaries.

No people, relationships, facts, or individual-entry records are extracted.
Parenthesized Liu Xiaobiao annotations remain byte-for-byte unchanged in the
chapter bodies.
"""

from __future__ import annotations

import argparse
from collections import OrderedDict
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping, Sequence


DEFAULT_INPUT_DIR = Path("content/processed/shishuo")
NORMALIZED_SUFFIX = ".md"

PAGE_MARKER_RE = re.compile(r"<pb:[^>]+>")
SOURCE_LINE_RE = re.compile(
    r"<!-- kanripo-(?:page|directive) source-line=(\d+):"
)
FILE_DIRECTIVE_RE = re.compile(
    r"<!-- kanripo-directive source-line=(\d+): "
    r"#\+PROPERTY: FILE (?P<file>.*?) -->\s*$"
)
CHAPTER_HEADING_RE = re.compile(
    r"^(?P<name>[^()（）\s第]+)"
    r"第(?P<number>[一二三四五六七八九十百]+)"
    r"(?P<part>[（(][上下][）)])?$"
)


# These are the observed source spellings in main-text FILE sections.  The
# aliases intentionally accommodate source variants such as 企羡/企羨 and
# 巧蓺/巧藝 without changing either spelling in output.
CANONICAL_CHAPTERS: OrderedDict[int, tuple[str, ...]] = OrderedDict(
    [
        (1, ("德行",)),
        (2, ("言語",)),
        (3, ("政事",)),
        (4, ("文學",)),
        (5, ("方正",)),
        (6, ("雅量",)),
        (7, ("識鑒",)),
        (8, ("賞譽",)),
        (9, ("品藻",)),
        (10, ("規箴",)),
        (11, ("捷悟",)),
        (12, ("夙惠",)),
        (13, ("豪爽",)),
        (14, ("容止",)),
        (15, ("自新",)),
        (16, ("企羡", "企羨")),
        (17, ("傷逝",)),
        (18, ("棲逸",)),
        (19, ("賢媛",)),
        (20, ("術解",)),
        (21, ("巧蓺", "巧藝")),
        (22, ("寵禮",)),
        (23, ("任誕",)),
        (24, ("簡傲",)),
        (25, ("排調",)),
        (26, ("輕詆",)),
        (27, ("假譎",)),
        (28, ("黜免",)),
        (29, ("儉嗇",)),
        (30, ("汰侈",)),
        (31, ("忿狷",)),
        (32, ("讒險",)),
        (33, ("尤悔",)),
        (34, ("紕漏",)),
        (35, ("惑溺",)),
        (36, ("仇隟",)),
    ]
)

SECTION_PREFACE = "preface"
SECTION_CATALOGUE = "catalogue"
SECTION_COLLATION = "collation_notes"
SECTION_MAIN = "main_text"
SECTION_UNKNOWN = "ambiguous"


def _yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _yaml_key(value: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", value):
        return value
    return _yaml_string(value)


def _yaml_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return _yaml_string(str(value))


def _append_yaml_list(lines: list[str], values: Iterable[Any], indent: str = "  ") -> None:
    values = list(values)
    if not values:
        lines.append(f"{indent}[]")
        return
    for value in values:
        lines.append(f"{indent}- {_yaml_value(value)}")


def _parse_yaml_value(token: str) -> Any:
    token = token.strip()
    if token in {"[]", "{}"}:
        return [] if token == "[]" else {}
    if token == "null":
        return None
    if token.startswith('"'):
        return json.loads(token)
    try:
        return int(token)
    except ValueError:
        return token


def _parse_frontmatter(lines: Sequence[str]) -> tuple[dict[str, Any], int]:
    if not lines or lines[0].strip() != "---":
        raise ValueError("normalized file has no YAML front matter")
    end = next(
        (index for index in range(1, len(lines)) if lines[index].strip() == "---"),
        None,
    )
    if end is None:
        raise ValueError("normalized file has unterminated YAML front matter")

    map_sections = {"kanripo_keywords", "kanripo_properties", "text_policy"}
    list_sections = {"kanripo_juans", "kanripo_files", "kanripo_headers"}
    data: dict[str, Any] = {}
    current_top: str | None = None
    current_nested: str | None = None

    for raw_line in lines[1:end]:
        line = raw_line.rstrip("\r\n")
        if not line.strip():
            continue
        if line.startswith("    - "):
            if current_top is None or current_nested is None:
                raise ValueError(f"invalid nested front matter line: {line}")
            nested = data.setdefault(current_top, {})
            if not isinstance(nested, dict):
                raise ValueError(f"front matter section is not a map: {current_top}")
            nested.setdefault(current_nested, []).append(_parse_yaml_value(line[6:]))
            continue
        if line.startswith("  - "):
            if current_top is None:
                raise ValueError(f"invalid list front matter line: {line}")
            values = data.setdefault(current_top, [])
            if not isinstance(values, list):
                raise ValueError(f"front matter section is not a list: {current_top}")
            values.append(_parse_yaml_value(line[4:]))
            continue
        if line.startswith("  "):
            key, separator, value = line[2:].partition(":")
            if not separator or current_top is None:
                raise ValueError(f"invalid nested front matter line: {line}")
            section = data.setdefault(current_top, {})
            if not isinstance(section, dict):
                raise ValueError(f"front matter section is not a map: {current_top}")
            current_nested = key
            section[key] = _parse_yaml_value(value) if value.strip() else []
            continue

        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError(f"invalid front matter line: {line}")
        current_top = key
        current_nested = None
        if value.strip():
            data[key] = _parse_yaml_value(value)
        elif key in map_sections:
            data[key] = {}
        elif key in list_sections:
            data[key] = []
        else:
            data[key] = ""

    return data, end


def _as_strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _as_property_map(value: Any) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, dict):
        return {}
    return {str(key): _as_strings(items) for key, items in value.items()}


def _first(mapping: Mapping[str, Sequence[str]], key: str) -> str:
    values = mapping.get(key, ())
    return values[0] if values else ""


def _clean(value: str) -> str:
    return value.strip()


def _classify_file_section(file_value: str) -> str:
    value = file_value.strip()
    if "校語" in value:
        return SECTION_COLLATION
    if "世説新語-序" in value:
        return SECTION_PREFACE
    if "目録" in value:
        return SECTION_CATALOGUE
    if "世説新語-卷" in value:
        return SECTION_MAIN
    return SECTION_UNKNOWN


def _chinese_number(value: str) -> int | None:
    digits = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    units = {"十": 10, "百": 100}
    total = 0
    section = 0
    for character in value:
        if character in digits:
            section = digits[character]
        elif character in units:
            section = (section or 1) * units[character]
            total += section
            section = 0
        else:
            return None
    return total + section


def _detect_heading(text: str) -> tuple[int, str, str, str] | None:
    candidate = text.strip()
    match = CHAPTER_HEADING_RE.fullmatch(candidate)
    if not match:
        return None
    number = _chinese_number(match.group("number"))
    if number not in CANONICAL_CHAPTERS:
        return None
    name = match.group("name")
    if name not in CANONICAL_CHAPTERS[number]:
        return None
    part = match.group("part") or ""
    return number, name, part, candidate


@dataclass
class NormalizedMetadata:
    normalized_filename: str
    source_path: str
    source_sha256: str
    title: str
    kanripo_id: str
    baseedition: str
    witness: str
    properties: dict[str, tuple[str, ...]]
    keywords: dict[str, tuple[str, ...]]


@dataclass
class BodyLine:
    body_index: int
    normalized_line: int
    text: str
    source_line: int | None
    page_markers: tuple[str, ...]
    file_section: str
    section_kind: str
    section_index: int | None = None
    is_file_directive: bool = False

    @property
    def raw(self) -> str:
        return self.text + "\n"


@dataclass
class FileSection:
    document: "NormalizedDocument"
    file_value: str
    kind: str
    start_index: int
    end_index: int
    section_index: int

    @property
    def normalized_start(self) -> int | None:
        if self.start_index > self.end_index:
            return None
        return self.document.body_lines[self.start_index].normalized_line

    @property
    def normalized_end(self) -> int | None:
        if self.start_index > self.end_index:
            return None
        return self.document.body_lines[self.end_index].normalized_line


@dataclass
class NormalizedDocument:
    path: Path
    metadata: NormalizedMetadata
    body_lines: list[BodyLine]
    sections: list[FileSection]
    order: int


@dataclass
class ChapterOccurrence:
    document: NormalizedDocument
    section: FileSection
    body_index: int
    number: int
    name: str
    part: str
    heading_text: str

    @property
    def line(self) -> BodyLine:
        return self.document.body_lines[self.body_index]


@dataclass
class ChapterPart:
    occurrence: ChapterOccurrence
    end_index: int

    @property
    def document(self) -> NormalizedDocument:
        return self.occurrence.document

    @property
    def section(self) -> FileSection:
        return self.occurrence.section

    @property
    def start_line(self) -> BodyLine:
        return self.occurrence.line

    @property
    def end_line(self) -> BodyLine:
        return self.document.body_lines[self.end_index]

    @property
    def body(self) -> str:
        return "".join(
            line.raw
            for line in self.document.body_lines[self.occurrence.body_index : self.end_index + 1]
        )


@dataclass
class Chapter:
    number: int
    canonical_name: str
    parts: list[ChapterPart]

    @property
    def occurrences(self) -> list[ChapterOccurrence]:
        return [part.occurrence for part in self.parts]

    @property
    def observed_headings(self) -> list[str]:
        return [occurrence.heading_text for occurrence in self.occurrences]


@dataclass
class SegmentationResult:
    documents: list[NormalizedDocument]
    sections: list[FileSection]
    chapters: list[Chapter]
    missing: list[int]
    duplicates: list[int]
    ambiguities: list[str]
    chapter_paths: list[Path]
    editorial_paths: list[Path]
    report_path: Path


def _parse_document(path: Path, order: int) -> NormalizedDocument:
    lines = path.read_text(encoding="utf-8").splitlines()
    frontmatter, frontmatter_end = _parse_frontmatter(lines)
    properties = _as_property_map(frontmatter.get("kanripo_properties"))
    keywords = _as_property_map(frontmatter.get("kanripo_keywords"))
    metadata = NormalizedMetadata(
        normalized_filename=path.name,
        source_path=str(frontmatter.get("source_path", "")),
        source_sha256=str(frontmatter.get("source_sha256", "")),
        title=str(frontmatter.get("kanripo_title", "")),
        kanripo_id=str(frontmatter.get("kanripo_id", "")),
        baseedition=str(frontmatter.get("kanripo_baseedition", "")),
        witness=str(frontmatter.get("kanripo_witness", "")),
        properties=properties,
        keywords=keywords,
    )

    body_start = frontmatter_end + 1
    if body_start < len(lines) and lines[body_start] == "":
        body_start += 1
    body_text = lines[body_start:]
    initial_file = _first(properties, "FILE")
    current_file = initial_file
    current_kind = _classify_file_section(current_file)
    current_page_markers: tuple[str, ...] = ()
    last_source_line: int | None = None
    body_lines: list[BodyLine] = []
    section_starts: list[tuple[str, int]] = [(current_file, 0)]
    sections: list[FileSection] = []

    for body_index, text in enumerate(body_text):
        normalized_line = body_start + body_index + 1
        explicit_source_lines = SOURCE_LINE_RE.findall(text)
        if explicit_source_lines:
            source_line = int(explicit_source_lines[0])
        elif last_source_line is not None:
            source_line = last_source_line + 1
        else:
            source_line = None
        if source_line is not None:
            last_source_line = source_line

        markers = tuple(PAGE_MARKER_RE.findall(text))
        if markers:
            current_page_markers = markers

        file_match = FILE_DIRECTIVE_RE.fullmatch(text)
        is_file_directive = file_match is not None
        line_file = current_file
        line_kind = current_kind
        if file_match:
            line_file = file_match.group("file")
            line_kind = _classify_file_section(line_file)

        body_lines.append(
            BodyLine(
                body_index=body_index,
                normalized_line=normalized_line,
                text=text,
                source_line=source_line,
                page_markers=current_page_markers,
                file_section=line_file,
                section_kind=line_kind,
                is_file_directive=is_file_directive,
            )
        )

        if file_match:
            previous_file, previous_start = section_starts[-1]
            previous_end = body_index - 1
            if previous_start <= previous_end:
                section_index = len(sections)
                sections.append(
                    FileSection(
                        document=None,  # replaced below after document construction
                        file_value=previous_file,
                        kind=_classify_file_section(previous_file),
                        start_index=previous_start,
                        end_index=previous_end,
                        section_index=section_index,
                    )
                )
            current_file = file_match.group("file")
            current_kind = _classify_file_section(current_file)
            current_page_markers = ()
            section_starts.append((current_file, body_index + 1))

    if section_starts:
        final_file, final_start = section_starts[-1]
        final_end = len(body_lines) - 1
        if final_start <= final_end:
            sections.append(
                FileSection(
                    document=None,
                    file_value=final_file,
                    kind=_classify_file_section(final_file),
                    start_index=final_start,
                    end_index=final_end,
                    section_index=len(sections),
                )
            )

    document = NormalizedDocument(
        path=path,
        metadata=metadata,
        body_lines=body_lines,
        sections=sections,
        order=order,
    )
    for section in sections:
        section.document = document
        for index in range(section.start_index, section.end_index + 1):
            body_lines[index].section_index = section.section_index
            body_lines[index].file_section = section.file_value
            body_lines[index].section_kind = section.kind
    return document


def _find_occurrences(documents: Sequence[NormalizedDocument]) -> list[ChapterOccurrence]:
    occurrences: list[ChapterOccurrence] = []
    for document in documents:
        for section in document.sections:
            if section.kind != SECTION_MAIN:
                continue
            for body_index in range(section.start_index, section.end_index + 1):
                line = document.body_lines[body_index]
                heading = _detect_heading(line.text)
                if heading is None:
                    continue
                number, name, part, heading_text = heading
                occurrences.append(
                    ChapterOccurrence(
                        document=document,
                        section=section,
                        body_index=body_index,
                        number=number,
                        name=name,
                        part=part,
                        heading_text=heading_text,
                    )
                )
    return sorted(
        occurrences,
        key=lambda occurrence: (occurrence.document.order, occurrence.body_index),
    )


def _build_chapters(occurrences: Sequence[ChapterOccurrence]) -> list[Chapter]:
    by_number: dict[int, list[ChapterOccurrence]] = {number: [] for number in CANONICAL_CHAPTERS}
    for occurrence in occurrences:
        by_number[occurrence.number].append(occurrence)

    chapters: list[Chapter] = []
    for number, aliases in CANONICAL_CHAPTERS.items():
        ordered = sorted(
            by_number[number],
            key=lambda occurrence: (occurrence.document.order, occurrence.body_index),
        )
        parts: list[ChapterPart] = []
        for occurrence in ordered:
            same_section = [
                candidate
                for candidate in occurrences
                if candidate.section is occurrence.section
                and candidate.body_index > occurrence.body_index
            ]
            next_index = min(
                (candidate.body_index for candidate in same_section),
                default=occurrence.section.end_index + 1,
            )
            parts.append(ChapterPart(occurrence=occurrence, end_index=next_index - 1))
        chapters.append(
            Chapter(
                number=number,
                canonical_name=aliases[0],
                parts=parts,
            )
        )
    return chapters


def _source_documents(parts: Sequence[ChapterPart]) -> list[NormalizedDocument]:
    result: list[NormalizedDocument] = []
    seen: set[Path] = set()
    for part in parts:
        if part.document.path in seen:
            continue
        seen.add(part.document.path)
        result.append(part.document)
    return result


def _source_position(line: BodyLine) -> dict[str, Any]:
    return {
        "normalized_line": line.normalized_line,
        "source_line": line.source_line,
        "page_marker": line.page_markers[-1] if line.page_markers else "",
    }


def _append_position(lines: list[str], label: str, position: Mapping[str, Any], indent: str = "    ") -> None:
    lines.append(f"{indent}{label}:")
    lines.append(f"{indent}  normalized_line: {_yaml_value(position.get('normalized_line'))}")
    lines.append(f"{indent}  source_line: {_yaml_value(position.get('source_line'))}")
    lines.append(f"{indent}  page_marker: {_yaml_value(str(position.get('page_marker', '')))}")


def _append_document_properties(lines: list[str], documents: Sequence[NormalizedDocument]) -> None:
    lines.append("source_kanripo_properties:")
    if not documents:
        lines.append("  []")
        return
    for document in documents:
        lines.append(f"  - normalized_filename: {_yaml_string(document.metadata.normalized_filename)}")
        lines.append("    properties:")
        for key, values in document.metadata.properties.items():
            lines.append(f"      {_yaml_key(key)}:")
            _append_yaml_list(lines, values, "        ")


def _common_segment_frontmatter(
    *,
    segment_type: str,
    documents: Sequence[NormalizedDocument],
    parts: Sequence[ChapterPart],
) -> list[str]:
    first = documents[0].metadata
    lines = [
        "---",
        "schema: 1",
        "stage: semantic-segmentation",
        f"segment_type: {_yaml_string(segment_type)}",
        f"kanripo_title: {_yaml_string(first.title)}",
        f"kanripo_id: {_yaml_string(first.kanripo_id)}",
        f"kanripo_baseedition: {_yaml_string(first.baseedition)}",
        f"kanripo_witness: {_yaml_string(first.witness)}",
        "source_normalized_files:",
    ]
    _append_yaml_list(lines, [document.metadata.normalized_filename for document in documents])
    lines.append("source_paths:")
    _append_yaml_list(lines, [document.metadata.source_path for document in documents])
    lines.append("source_sha256:")
    _append_yaml_list(lines, [document.metadata.source_sha256 for document in documents])
    _append_document_properties(lines, documents)
    lines.append("source_segments:")
    if not parts:
        lines.append("  []")
    for part in parts:
        occurrence = part.occurrence
        lines.append(
            "  - normalized_filename: "
            f"{_yaml_string(occurrence.document.metadata.normalized_filename)}"
        )
        lines.append(f"    source_path: {_yaml_string(occurrence.document.metadata.source_path)}")
        lines.append(f"    source_sha256: {_yaml_string(occurrence.document.metadata.source_sha256)}")
        lines.append(f"    FILE: {_yaml_string(part.section.file_value)}")
        lines.append(f"    heading: {_yaml_string(occurrence.heading_text)}")
        _append_position(lines, "start", _source_position(part.start_line), "    ")
        _append_position(lines, "end", _source_position(part.end_line), "    ")
    return lines


def _chapter_frontmatter(chapter: Chapter) -> str:
    documents = _source_documents(chapter.parts)
    lines = _common_segment_frontmatter(
        segment_type="shishuo-chapter",
        documents=documents,
        parts=chapter.parts,
    )
    lines[4:4] = [
        f"chapter_number: {chapter.number}",
        f"canonical_heading: {_yaml_string(chapter.canonical_name + '第' + _number_to_chinese(chapter.number))}",
        "observed_headings:",
    ]
    # The insertion above places observed_headings before the source fields;
    # append its values at the correct position by rebuilding that short block.
    observed_index = lines.index("observed_headings:")
    lines[observed_index + 1:observed_index + 1] = [
        f"  - {_yaml_string(heading)}" for heading in chapter.observed_headings
    ]
    lines.extend(
        [
            f"boundary_status: {_yaml_string('multipart-explicit' if len(chapter.parts) > 1 else 'resolved')}",
            "entry_segmentation: \"not performed\"",
            "ambiguities:",
        ]
    )
    if len(chapter.parts) > 1:
        lines.append(
            "  - "
            + _yaml_string(
                "賞譽第八 is represented by explicit 上/下 headings in separate "
                "main-text FILE sections; both parts are grouped as canonical chapter 8."
            )
        )
    else:
        lines.append("  []")
    lines.extend(["---", ""])
    return "\n".join(lines)


def _number_to_chinese(number: int) -> str:
    explicit = {
        1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九",
        10: "十", 11: "十一", 12: "十二", 13: "十三", 14: "十四", 15: "十五", 16: "十六",
        17: "十七", 18: "十八", 19: "十九", 20: "二十", 21: "二十一", 22: "二十二",
        23: "二十三", 24: "二十四", 25: "二十五", 26: "二十六", 27: "二十七",
        28: "二十八", 29: "二十九", 30: "三十", 31: "三十一", 32: "三十二",
        33: "三十三", 34: "三十四", 35: "三十五", 36: "三十六",
    }
    return explicit[number]


def _editorial_frontmatter(section: FileSection) -> str:
    document = section.document
    lines = _common_segment_frontmatter(
        segment_type="shishuo-editorial",
        documents=[document],
        parts=[],
    )
    lines[4:4] = [f"editorial_kind: {_yaml_string(section.kind)}"]
    lines.append("section_position:")
    first_line = document.body_lines[section.start_index]
    last_line = document.body_lines[section.end_index]
    _append_position(lines, "start", _source_position(first_line), "  ")
    _append_position(lines, "end", _source_position(last_line), "  ")
    lines.extend(
        [
            f"FILE: {_yaml_string(section.file_value)}",
            "entry_segmentation: \"not applicable\"",
            "---",
            "",
        ]
    )
    return "\n".join(lines)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _write_chapter(chapter: Chapter, chapters_dir: Path) -> Path:
    path = chapters_dir / f"chapter-{chapter.number:02d}.md"
    body_parts: list[str] = []
    for index, part in enumerate(chapter.parts):
        if index:
            previous = chapter.parts[index - 1]
            body_parts.append(
                "<!-- segmentation-file-boundary: "
                f"normalized_filename={part.document.metadata.normalized_filename}; "
                f"FILE={part.section.file_value} -->\n"
            )
        body_parts.append(part.body)
    _write_text(path, _chapter_frontmatter(chapter) + "".join(body_parts))
    return path


def _write_editorial(section: FileSection, editorial_dir: Path, ordinal: int) -> Path:
    names = {
        SECTION_PREFACE: "preface",
        SECTION_CATALOGUE: "catalogue",
        SECTION_COLLATION: "collation-notes",
    }
    stem = names.get(section.kind, f"ambiguous-{ordinal:02d}")
    path = editorial_dir / f"{stem}.md"
    body = "".join(
        line.raw for line in section.document.body_lines[section.start_index : section.end_index + 1]
    )
    _write_text(path, _editorial_frontmatter(section) + body)
    return path


def _position_text(part: ChapterPart, which: str) -> str:
    line = part.start_line if which == "start" else part.end_line
    page = line.page_markers[-1] if line.page_markers else "—"
    source = str(line.source_line) if line.source_line is not None else "?"
    return (
        f"{part.document.metadata.normalized_filename}:"
        f"normalized-line={line.normalized_line};source-line={source};page={page}"
    )


def _report(result: SegmentationResult) -> str:
    textual_occurrences = sum(len(chapter.parts) for chapter in result.chapters)
    lines = [
        "---",
        "schema: 1",
        "stage: semantic-segmentation",
        "report_type: shishuo-chapter-validation",
        f"normalized_input_count: {len(result.documents)}",
        f"textual_heading_occurrence_count: {textual_occurrences}",
        f"canonical_chapter_count: {len(result.chapters)}",
        f"missing_chapters: {json.dumps(result.missing, ensure_ascii=False)}",
        f"duplicate_chapters: {json.dumps(result.duplicates, ensure_ascii=False)}",
        f"ambiguous_boundary_count: {len(result.ambiguities)}",
        "---",
        "",
        "# Shishuo Xinyu semantic-segmentation validation",
        "",
        "The normalized Markdown inputs are read-only.  Chapter boundaries are "
        "taken only from explicit headings in main-text FILE sections.  Entry "
        "splitting and knowledge extraction are intentionally not performed.",
        "",
        "## Summary",
        "",
        f"- Canonical chapters expected: {len(CANONICAL_CHAPTERS)}",
        f"- Canonical chapters detected: {len(result.chapters)}",
        f"- Textual heading occurrences: {textual_occurrences}",
        f"- Missing chapters: {', '.join(map(str, result.missing)) or 'none'}",
        f"- Unintentional duplicate chapters: {', '.join(map(str, result.duplicates)) or 'none'}",
        "",
        "## Canonical chapters",
        "",
        "| # | Canonical heading | Observed heading(s) | Normalized file(s) | FILE section(s) | Start | End | Status |",
        "|---:|---|---|---|---|---|---|---|",
    ]
    for chapter in result.chapters:
        observed = "<br>".join(chapter.observed_headings)
        files = "<br>".join(
            part.document.metadata.normalized_filename for part in chapter.parts
        )
        file_sections = "<br>".join(part.section.file_value for part in chapter.parts)
        start = _position_text(chapter.parts[0], "start")
        end = _position_text(chapter.parts[-1], "end")
        status = "multipart explicit 上/下" if len(chapter.parts) > 1 else "detected"
        lines.append(
            f"| {chapter.number} | {chapter.canonical_name}第{_number_to_chinese(chapter.number)} "
            f"| {observed} | {files} | {file_sections} | {start} | {end} | {status} |"
        )

    lines.extend(["", "## FILE section classification", "", "| Type | Normalized file | FILE value | Start | End |", "|---|---|---|---:|---:|"])
    for section in result.sections:
        start = section.normalized_start if section.normalized_start is not None else "?"
        end = section.normalized_end if section.normalized_end is not None else "?"
        lines.append(
            f"| {section.kind} | {section.document.metadata.normalized_filename} "
            f"| {section.file_value} | {start} | {end} |"
        )

    lines.extend(["", "## Ambiguous or intentionally deferred boundaries", ""])
    if result.ambiguities:
        lines.extend(f"- {ambiguity}" for ambiguity in result.ambiguities)
    else:
        lines.append("- None beyond the explicitly grouped chapter 8 split.")
    lines.extend(
        [
            "",
            "## Editorial material excluded from chapter files",
            "",
            "- `preface`: the FILE section ending in `序`.",
            "- `catalogue`: the FILE section containing `目録`.",
            "- `collation_notes`: the FILE section named `世説新語校語`.",
            "",
            "All excluded material remains available in the corresponding files "
            "under `../editorial/` and in the untouched normalized inputs.",
            "",
        ]
    )
    return "\n".join(lines)


def segment_collection(
    input_dir: Path | str = DEFAULT_INPUT_DIR,
    output_dir: Path | str | None = None,
) -> SegmentationResult:
    """Segment the normalized Shishuo collection without editing its inputs."""

    input_root = Path(input_dir)
    output_root = input_root if output_dir is None else Path(output_dir)
    paths = sorted(input_root.glob(f"*{NORMALIZED_SUFFIX}"), key=lambda path: path.name)
    if not paths:
        raise FileNotFoundError(f"no normalized Markdown files found in {input_root}")
    documents = [_parse_document(path, order) for order, path in enumerate(paths)]
    sections = [section for document in documents for section in document.sections]
    occurrences = _find_occurrences(documents)
    chapters = _build_chapters(occurrences)
    missing = [number for number, chapter in zip(CANONICAL_CHAPTERS, chapters) if not chapter.parts]
    duplicates = [
        chapter.number
        for chapter in chapters
        if len(chapter.parts) > 1
        and not (
            chapter.number == 8
            and len(chapter.parts) == 2
            and {part.occurrence.part for part in chapter.parts} == {"(上)", "(下)"}
        )
    ]
    ambiguities = [
        "Chapter 8 has explicit 賞譽第八(上) and 賞譽第八(下) headings in "
        "different main-text FILE sections; they are grouped as one canonical "
        "chapter and both source positions are retained.",
        "Main-text source spellings 企羡第十六 and 巧蓺第二十一 are matched "
        "as observed; no character normalization is applied.",
        "Individual Shishuo entry boundaries are intentionally not inferred; "
        "each chapter file retains its contiguous source span and annotations.",
    ]
    unknown_sections = [section for section in sections if section.kind == SECTION_UNKNOWN]
    ambiguities.extend(
        "FILE section could not be classified deterministically: "
        f"{section.document.metadata.normalized_filename} / {section.file_value}"
        for section in unknown_sections
    )

    chapters_dir = output_root / "chapters"
    editorial_dir = output_root / "editorial"
    chapter_paths = [_write_chapter(chapter, chapters_dir) for chapter in chapters if chapter.parts]
    editorial_sections = [
        section
        for section in sections
        if section.kind in {SECTION_PREFACE, SECTION_CATALOGUE, SECTION_COLLATION}
    ]
    editorial_paths = [
        _write_editorial(section, editorial_dir, ordinal)
        for ordinal, section in enumerate(editorial_sections, start=1)
    ]
    report_path = chapters_dir / "validation-report.md"
    provisional = SegmentationResult(
        documents=documents,
        sections=sections,
        chapters=[chapter for chapter in chapters if chapter.parts],
        missing=missing,
        duplicates=duplicates,
        ambiguities=ambiguities,
        chapter_paths=chapter_paths,
        editorial_paths=editorial_paths,
        report_path=report_path,
    )
    _write_text(report_path, _report(provisional))
    return provisional


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="normalized Shishuo directory (default: content/processed/shishuo)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="segment output root (default: input directory; only chapters/editorial are written)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    try:
        result = segment_collection(args.input_dir, args.output_dir)
    except (FileNotFoundError, OSError, UnicodeDecodeError, ValueError) as error:
        parser.error(str(error))
        return 2
    print(f"chapters: {len(result.chapter_paths)}")
    print(f"editorial sections: {len(result.editorial_paths)}")
    print(f"validation report: {result.report_path}")
    if result.missing or result.duplicates:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
