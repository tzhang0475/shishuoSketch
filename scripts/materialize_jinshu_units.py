#!/usr/bin/env python3
"""Materialize reversible structural units from normalized Jinshu Markdown.

The parser is deliberately conservative.  It recognizes only volume headers,
the four source-visible major categories, explicit ``考證`` blocks, and short
stand-alone headings in 列傳 whose following source line supports the heading.
It never consults a secondary witness and never edits the normalized source.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = REPOSITORY_ROOT / "content/processed/jinshu"
DEFAULT_OUTPUT_DIR = REPOSITORY_ROOT / "content/processed/jinshu/units"
DEFAULT_INDEX_PATH = REPOSITORY_ROOT / "data/jinshu-unit-index.json"
DEFAULT_REPORT_PATH = REPOSITORY_ROOT / "content/curated/jinshu/structural-report.md"
PRIMARY_WITNESS = "jinshu-wikisource-siku"
WORK = "晉書"

CHINESE_DIGITS = {
    "〇": 0,
    "零": 0,
    "○": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
CHINESE_UNITS = {"十": 10, "百": 100, "千": 1000, "萬": 10000, "万": 10000}
VOLUME_NUMBER = r"[〇零○一二三四五六七八九十百千万萬]+"
MAIN_VOLUME_RE = re.compile(rf"^[晉晋]書[卷巻](?P<number>{VOLUME_NUMBER})$")
EDITORIAL_VOLUME_RE = re.compile(rf"^[晉晋]書[卷巻](?P<number>{VOLUME_NUMBER})考證$")
CATEGORY_RE = re.compile(
    rf"^(?P<label>帝紀|本紀|志|列傳|載記)(?:(?:第|弟){VOLUME_NUMBER})?(?:[　 ]|$)"
)
PAGE_MARKER_RE = re.compile(r"<pb:([^>]+)>")
PAGE_COMMENT_RE = re.compile(r"^<!--\s*kanripo-page\b")
WIKISOURCE_VOLUME_MARKER_RE = re.compile(
    r"^<!--\s*wikisource-volume-start:\s*(?P<data>\{.*\})\s*-->$"
)
WIKISOURCE_METADATA_COMMENT_RE = re.compile(r"^<!--\s*wikisource-[^>]+-->$")
PUNCTUATION = set("，。！？：；、()（）「」『』《》〈〉〔〕【】…—-·")
SECTION_TITLES = {"后妃上", "后妃下"}
EXPECTED_MAIN_VOLUMES = set(range(1, 131))


def chinese_numeral_value(value: str) -> int:
    """Return a small or traditional Chinese numeral as an integer."""

    if value.isdigit():
        return int(value)
    total = 0
    section = 0
    number = 0
    for character in value:
        if character in CHINESE_DIGITS:
            number = CHINESE_DIGITS[character]
            continue
        unit = CHINESE_UNITS.get(character)
        if unit is None:
            raise ValueError(f"unsupported Chinese numeral character: {character}")
        if unit >= 10000:
            section = (section + number) * unit
            total += section
            section = 0
            number = 0
        else:
            section += (number or 1) * unit
            number = 0
    return total + section + number


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def quote_yaml(value: str | None) -> str:
    if value is None:
        return "null"
    return json.dumps(value, ensure_ascii=False)


def parse_simple_frontmatter(text: str) -> tuple[dict[str, str], int]:
    """Read the normalizer's scalar front-matter fields and body start."""

    if not text.startswith("---\n"):
        raise ValueError("normalized Jinshu file has no YAML front matter")
    closing = re.search(r"\n---\n", text[4:])
    if closing is None:
        raise ValueError("normalized Jinshu file has no front-matter terminator")
    closing_end = 4 + closing.end()
    fields: dict[str, str] = {}
    for line in text[4 : 4 + closing.start()].splitlines():
        if not line or line[0].isspace() or ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        value = raw_value.strip()
        if value.startswith('"') and value.endswith('"'):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = value[1:-1]
        fields[key.strip()] = value
    body_start = closing_end
    if text.startswith("\n", body_start):
        body_start += 1
    return fields, body_start


def visible_line(text: str) -> str:
    """Return source-visible text for structural recognition only.

    Structured Wikisource comments remain in the emitted source spans.  They
    must not make a notes-only line look like a biography heading, and they
    must not prevent a heading with an inline note from being recognized.
    """

    pieces: list[str] = []
    cursor = 0
    while cursor < len(text):
        start = text.find("<!--", cursor)
        if start < 0:
            pieces.append(text[cursor:])
            break
        pieces.append(text[cursor:start])
        depth = 1
        cursor = start + 4
        while cursor < len(text) and depth:
            if text.startswith("<!--", cursor):
                depth += 1
                cursor += 4
            elif text.startswith("-->", cursor):
                depth -= 1
                cursor += 3
            else:
                cursor += 1
        if depth:
            # An unclosed comment is markup-only for structural recognition;
            # do not expose its payload as a possible heading.
            cursor = len(text)
    return "".join(pieces).strip()


def is_edition_header(text: str) -> bool:
    # 卷八十八 has the source-visible circle after the edition header.  The
    # circle remains in the normalized source; this helper only recognizes the
    # structural header without editing it.
    return visible_line(text).rstrip("○") == "欽定四庫全書"


def wikisource_volume_marker(text: str) -> dict[str, Any] | None:
    match = WIKISOURCE_VOLUME_MARKER_RE.fullmatch(text.strip())
    if match is None:
        return None
    try:
        value = json.loads(match.group("data"))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


@dataclass(frozen=True)
class SourceLine:
    index: int
    number: int
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class SourceFile:
    path: Path
    relative_path: str
    full_text: str
    body: str
    body_start_line: int
    fields: Mapping[str, str]
    lines: tuple[SourceLine, ...]
    normalized_sha256: str

    @property
    def raw_source_path(self) -> str:
        return str(self.fields.get("source_path") or self.fields.get("source_text_path", ""))

    @property
    def raw_source_sha256(self) -> str:
        return str(self.fields.get("source_sha256") or self.fields.get("source_text_sha256", ""))


@dataclass
class VolumeOccurrence:
    source: SourceFile
    number: int
    volume_heading: str
    start_index: int
    end_index: int
    category: str
    category_heading: str
    category_index: int
    occurrence: int = 1
    editorial_start_index: int | None = None

    @property
    def main_end_index(self) -> int:
        return self.editorial_start_index or self.end_index

    @property
    def volume_label(self) -> str:
        return f"卷{self.number}"

    @property
    def occurrence_key(self) -> str:
        if self.occurrence == 1:
            return f"{self.number:03d}"
        return f"{self.number:03d}-occ{self.occurrence}"


@dataclass
class Unit:
    unit_id: str
    work: str
    volume: str
    volume_number: int | None
    volume_occurrence: int | None
    category: str
    category_heading: str
    title: str
    heading_text: str
    unit_kind: str
    parent_unit: str | None
    source: SourceFile
    source_text: str
    start_index: int
    end_index: int
    confidence: str
    note: str | None = None

    @property
    def start_offset(self) -> int:
        return self.source.lines[self.start_index].start

    @property
    def end_offset(self) -> int:
        if self.end_index < len(self.source.lines):
            return self.source.lines[self.end_index].start
        return len(self.source.body)

    @property
    def source_line_start(self) -> int:
        return self.source.lines[self.start_index].number

    @property
    def source_line_end(self) -> int:
        if self.end_index > self.start_index:
            return self.source.lines[self.end_index - 1].number
        return self.source.lines[self.start_index].number

    @property
    def source_text_sha256(self) -> str:
        return sha256_text(self.source_text)

    @property
    def page_markers(self) -> list[str]:
        return list(dict.fromkeys(PAGE_MARKER_RE.findall(self.source_text)))


def load_source_file(path: Path, root: Path = REPOSITORY_ROOT) -> SourceFile:
    full_text = path.read_text(encoding="utf-8")
    fields, body_start = parse_simple_frontmatter(full_text)
    body = full_text[body_start:]
    body_start_line = full_text[:body_start].count("\n") + 1
    lines: list[SourceLine] = []
    offset = 0
    for index, raw_line in enumerate(body.splitlines(keepends=True)):
        line = raw_line.removesuffix("\n").removesuffix("\r")
        lines.append(
            SourceLine(
                index=index,
                number=body_start_line + index,
                text=line,
                start=offset,
                end=offset + len(raw_line),
            )
        )
        offset += len(raw_line)
    if offset < len(body):
        lines.append(
            SourceLine(
                index=len(lines),
                number=body_start_line + len(lines),
                text=body[offset:],
                start=offset,
                end=len(body),
            )
        )
    return SourceFile(
        path=path,
        relative_path=path.relative_to(root).as_posix(),
        full_text=full_text,
        body=body,
        body_start_line=body_start_line,
        fields=fields,
        lines=tuple(lines),
        normalized_sha256=sha256_text(full_text),
    )


def significant_line(lines: Sequence[SourceLine], index: int, direction: int) -> int | None:
    cursor = index + direction
    while 0 <= cursor < len(lines):
        stripped = visible_line(lines[cursor].text)
        if stripped and not PAGE_COMMENT_RE.match(stripped):
            return cursor
        cursor += direction
    return None


def is_main_volume_start(lines: Sequence[SourceLine], index: int) -> bool:
    if wikisource_volume_marker(lines[index].text) is not None:
        return True
    match = MAIN_VOLUME_RE.fullmatch(visible_line(lines[index].text))
    if match is None:
        return False
    previous = significant_line(lines, index, -1)
    return previous is not None and is_edition_header(lines[previous].text)


def volume_header_start(lines: Sequence[SourceLine], volume_index: int) -> int:
    """Include the page marker and edition header preceding a volume heading."""

    if wikisource_volume_marker(lines[volume_index].text) is not None:
        cursor = volume_index - 1
        while cursor >= 0 and (
            not visible_line(lines[cursor].text)
            or WIKISOURCE_METADATA_COMMENT_RE.match(lines[cursor].text.strip())
        ):
            cursor -= 1
        return cursor + 1

    cursor = volume_index - 1
    while cursor >= 0 and not visible_line(lines[cursor].text):
        cursor -= 1
    if cursor >= 0 and is_edition_header(lines[cursor].text):
        header = cursor
        preceding = cursor - 1
        while preceding >= 0 and not visible_line(lines[preceding].text):
            preceding -= 1
        if preceding >= 0 and (
            PAGE_COMMENT_RE.match(lines[preceding].text.strip())
            or WIKISOURCE_METADATA_COMMENT_RE.match(lines[preceding].text.strip())
        ):
            return preceding
        return header
    return volume_index


def category_from_heading(heading: str) -> str:
    match = CATEGORY_RE.match(heading)
    if match is None:
        return "unknown"
    return {
        "帝紀": "benji",
        "本紀": "benji",
        "志": "zhi",
        "列傳": "liezhuan",
        "載記": "zaiji",
    }[match.group("label")]


def find_category(lines: Sequence[SourceLine], volume_index: int) -> tuple[int, str, str]:
    marker = wikisource_volume_marker(lines[volume_index].text)
    if marker is not None and marker.get("category") in {"benji", "zhi", "liezhuan", "zaiji"}:
        return (
            volume_index,
            str(marker["category"]),
            str(marker.get("category_heading", "")),
        )
    cursor = volume_index + 1
    inspected = 0
    while cursor < len(lines) and inspected < 12:
        stripped = visible_line(lines[cursor].text)
        if stripped and not PAGE_COMMENT_RE.match(stripped):
            match = CATEGORY_RE.match(stripped)
            if match:
                return cursor, category_from_heading(stripped), stripped
            inspected += 1
        cursor += 1
    return volume_index, "unknown", ""


def find_editorial_start(
    lines: Sequence[SourceLine], start: int, end: int, number: int
) -> int | None:
    for index in range(start + 1, end):
        stripped = visible_line(lines[index].text)
        match = EDITORIAL_VOLUME_RE.fullmatch(stripped)
        if match and chinese_numeral_value(match.group("number")) == number:
            previous = significant_line(lines, index, -1)
            if previous is not None and previous >= start:
                previous_match = MAIN_VOLUME_RE.fullmatch(visible_line(lines[previous].text))
                if previous_match and chinese_numeral_value(previous_match.group("number")) == number:
                    return previous
            return index
        match = MAIN_VOLUME_RE.fullmatch(stripped)
        if match and chinese_numeral_value(match.group("number")) == number:
            following = significant_line(lines, index, 1)
            if following is not None and EDITORIAL_VOLUME_RE.fullmatch(visible_line(lines[following].text)):
                return index
    return None


def find_main_occurrences(source: SourceFile) -> list[VolumeOccurrence]:
    volume_indices = [
        line.index
        for line in source.lines
        if is_main_volume_start(source.lines, line.index)
    ]
    starts = [volume_header_start(source.lines, index) for index in volume_indices]
    occurrences: list[VolumeOccurrence] = []
    occurrence_counts: defaultdict[int, int] = defaultdict(int)
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(source.lines)
        volume_index = volume_indices[position]
        marker = wikisource_volume_marker(source.lines[volume_index].text)
        if marker is not None:
            number = int(marker["volume"])
            volume_heading = f"晉書卷{number}（Wikisource section marker）"
        else:
            volume_match = MAIN_VOLUME_RE.fullmatch(visible_line(source.lines[volume_index].text))
            assert volume_match is not None
            number = chinese_numeral_value(volume_match.group("number"))
            volume_heading = visible_line(source.lines[volume_index].text)
        category_index, category, category_heading = find_category(source.lines, volume_index)
        occurrence_counts[number] += 1
        occurrence = VolumeOccurrence(
            source=source,
            number=number,
            volume_heading=volume_heading,
            start_index=start,
            end_index=end,
            category=category,
            category_heading=category_heading,
            category_index=category_index,
            occurrence=occurrence_counts[number],
        )
        occurrence.editorial_start_index = find_editorial_start(source.lines, start, end, number)
        occurrences.append(occurrence)
    return occurrences


def standalone_editorial_volume(source: SourceFile) -> int | None:
    for line in source.lines:
        match = EDITORIAL_VOLUME_RE.fullmatch(visible_line(line.text))
        if match:
            return chinese_numeral_value(match.group("number"))
    return None


def heading_candidate(
    lines: Sequence[SourceLine], index: int, category_index: int
) -> tuple[str, str, str, bool] | None:
    text = lines[index].text
    stripped = visible_line(text)
    if not stripped or PAGE_COMMENT_RE.match(stripped):
        return None
    if index <= category_index or len(stripped) > 16:
        return None
    if any(character in stripped for character in PUNCTUATION):
        return None
    if stripped in SECTION_TITLES:
        return stripped, text, "high", True
    following = significant_line(lines, index, 1)
    if following is None:
        return None
    following_text = visible_line(lines[following].text)
    if following_text.startswith(stripped):
        return stripped, text, "high", False
    if len(stripped) >= 2 and following_text.startswith(stripped[-1]):
        return (
            stripped,
            text,
            "medium",
            False,
        )
    return None


def find_liezhuan_headings(
    source: SourceFile, occurrence: VolumeOccurrence
) -> list[tuple[int, str, str, str, bool]]:
    result: list[tuple[int, str, str, str, bool]] = []
    for index in range(occurrence.category_index + 1, occurrence.main_end_index):
        candidate = heading_candidate(source.lines, index, occurrence.category_index)
        if candidate is None:
            continue
        title, heading_text, confidence, section = candidate
        note = None
        if confidence == "medium":
            note = "The following source line begins with the heading's final character rather than repeating the full heading."
        result.append((index, title, heading_text, confidence, section))
    return result


def line_span(source: SourceFile, start_index: int, end_index: int) -> str:
    start = source.lines[start_index].start
    end = source.lines[end_index].start if end_index < len(source.lines) else len(source.body)
    return source.body[start:end]


def source_anchor(source: SourceFile, start_index: int, end_index: int) -> tuple[str, str]:
    start = source.lines[start_index].text
    end_line = source.lines[max(start_index, end_index - 1)].text
    return start, end_line


def make_unit(
    *,
    unit_id: str,
    occurrence: VolumeOccurrence | None,
    source: SourceFile,
    start_index: int,
    end_index: int,
    category: str,
    category_heading: str,
    title: str,
    heading_text: str,
    unit_kind: str,
    parent_unit: str | None,
    confidence: str,
    note: str | None = None,
    volume_number: int | None = None,
    volume_occurrence: int | None = None,
    volume: str | None = None,
) -> Unit:
    return Unit(
        unit_id=unit_id,
        work=WORK,
        volume=volume or (occurrence.volume_label if occurrence else "前置材料"),
        volume_number=volume_number if volume_number is not None else (occurrence.number if occurrence else None),
        volume_occurrence=volume_occurrence if volume_occurrence is not None else (occurrence.occurrence if occurrence else None),
        category=category,
        category_heading=category_heading,
        title=title,
        heading_text=heading_text,
        unit_kind=unit_kind,
        parent_unit=parent_unit,
        source=source,
        source_text=line_span(source, start_index, end_index),
        start_index=start_index,
        end_index=end_index,
        confidence=confidence,
        note=note,
    )


def materialize_main_occurrence(occurrence: VolumeOccurrence) -> list[Unit]:
    source = occurrence.source
    main_end = occurrence.main_end_index
    unit_prefix = occurrence.occurrence_key
    if occurrence.category != "liezhuan":
        marker = next(
            (
                wikisource_volume_marker(source.lines[index].text)
                for index in range(occurrence.start_index, min(occurrence.category_index + 1, len(source.lines)))
                if wikisource_volume_marker(source.lines[index].text) is not None
            ),
            None,
        )
        title_index = None if marker is not None else significant_line(source.lines, occurrence.category_index, 1)
        if title_index is None or title_index >= main_end:
            title = occurrence.category_heading or occurrence.volume_heading
            heading_text = title if marker is not None else source.lines[occurrence.category_index].text
            title_index = occurrence.category_index
        else:
            title = source.lines[title_index].text.strip()
            heading_text = source.lines[title_index].text
        note = None
        confidence = "high" if occurrence.category != "unknown" else "low"
        if occurrence.category == "unknown":
            note = "No supported major category heading was found immediately after the volume heading."
        return [
            make_unit(
                unit_id=f"{unit_prefix}-{occurrence.category}-001",
                occurrence=occurrence,
                source=source,
                start_index=occurrence.start_index,
                end_index=main_end,
                category=occurrence.category,
                category_heading=occurrence.category_heading,
                title=title,
                heading_text=heading_text,
                unit_kind="volume",
                parent_unit=None,
                confidence=confidence,
                note=note,
            )
        ]

    headings = find_liezhuan_headings(source, occurrence)
    if not headings:
        return [
            make_unit(
                unit_id=f"{unit_prefix}-liezhuan-001",
                occurrence=occurrence,
                source=source,
                start_index=occurrence.start_index,
                end_index=main_end,
                category="liezhuan",
                category_heading=occurrence.category_heading,
                title=occurrence.category_heading or occurrence.volume_heading,
                heading_text=occurrence.category_heading or occurrence.volume_heading,
                unit_kind="volume",
                parent_unit=None,
                confidence="low",
                note="No deterministic biography heading was recognized; the volume remains combined.",
            )
        ]

    units: list[Unit] = []
    parent_unit: str | None = None
    for ordinal, heading in enumerate(headings, start=1):
        heading_index, title, heading_text, confidence, is_section = heading
        end_index = headings[ordinal][0] if ordinal < len(headings) else main_end
        unit_id = f"{unit_prefix}-liezhuan-{ordinal:03d}"
        unit_kind = "section" if is_section else "biography"
        unit_parent = parent_unit if not is_section else None
        unit = make_unit(
            unit_id=unit_id,
            occurrence=occurrence,
            source=source,
            start_index=occurrence.start_index if ordinal == 1 else heading_index,
            end_index=end_index,
            category="liezhuan",
            category_heading=occurrence.category_heading,
            title=title,
            heading_text=heading_text,
            unit_kind=unit_kind,
            parent_unit=unit_parent,
            confidence=confidence,
            note=(
                "Explicit subsection heading; preceding introductory text is retained in this unit."
                if is_section
                else (
                    "The boundary is based on a short stand-alone heading followed by its biography text."
                    if confidence == "high"
                    else "The boundary is structurally plausible but the following line does not repeat the full heading."
                )
            ),
        )
        units.append(unit)
        if is_section:
            parent_unit = unit_id
    return units


def make_editorial_unit(
    source: SourceFile,
    start_index: int,
    end_index: int,
    volume_number: int | None,
    volume_occurrence: int | None,
) -> Unit:
    heading_index = start_index
    for index in range(start_index, end_index):
        if EDITORIAL_VOLUME_RE.fullmatch(visible_line(source.lines[index].text)):
            heading_index = index
            break
    title = visible_line(source.lines[heading_index].text)
    match = EDITORIAL_VOLUME_RE.fullmatch(title)
    if match:
        volume_number = chinese_numeral_value(match.group("number"))
    volume = f"卷{volume_number}" if volume_number is not None else "未知卷"
    prefix = f"{volume_number:03d}" if volume_number is not None else "unknown"
    if volume_occurrence and volume_occurrence > 1:
        prefix += f"-occ{volume_occurrence}"
    return make_unit(
        unit_id=f"{prefix}-editorial-001",
        occurrence=None,
        source=source,
        start_index=start_index,
        end_index=end_index,
        category="editorial",
        category_heading=title,
        title=title,
        heading_text=source.lines[heading_index].text,
        unit_kind="editorial",
        parent_unit=None,
        confidence="high" if volume_number is not None else "low",
        note="Explicit 晉書考證 material retained as editorial source text; it is not silently merged into the main unit.",
        volume_number=volume_number,
        volume_occurrence=volume_occurrence,
        volume=volume,
    )


def make_catalogue_unit(
    source: SourceFile,
    start_index: int = 0,
    end_index: int | None = None,
    unit_id: str = "catalogue-000-001",
) -> Unit:
    end_index = len(source.lines) if end_index is None else end_index
    title = next(
        (
            visible_line(line.text)
            for line in source.lines[start_index:end_index]
            if visible_line(line.text).endswith("目錄")
        ),
        "前置材料",
    )
    heading = next(
        (
            line.text
            for line in source.lines[start_index:end_index]
            if visible_line(line.text) == title
        ),
        source.lines[start_index].text,
    )
    return make_unit(
        unit_id=unit_id,
        occurrence=None,
        source=source,
        start_index=start_index,
        end_index=end_index,
        category="catalogue",
        category_heading=title,
        title=title,
        heading_text=heading,
        unit_kind="catalogue",
        parent_unit=None,
        confidence="high",
        note="Catalogue and prefatory material retained as one source unit; no historical unit boundaries are inferred here.",
        volume=None,
    )


def parse_sources(source_dir: Path, root: Path = REPOSITORY_ROOT) -> tuple[list[SourceFile], list[Unit], list[str]]:
    sources = [load_source_file(path, root) for path in sorted(source_dir.glob("*.md"))]
    units: list[Unit] = []
    anomalies: list[str] = []
    volume_occurrences: defaultdict[int, int] = defaultdict(int)
    seen_main_numbers: list[int] = []
    for source in sources:
        occurrences = find_main_occurrences(source)
        if source.path.name.endswith("_000.md") and not occurrences:
            units.append(make_catalogue_unit(source))
            continue
        if occurrences and occurrences[0].start_index > 0:
            units.append(
                make_catalogue_unit(
                    source,
                    0,
                    occurrences[0].start_index,
                    unit_id="catalogue-000-001",
                )
            )
        for occurrence in occurrences:
            volume_occurrences[occurrence.number] += 1
            occurrence.occurrence = volume_occurrences[occurrence.number]
            seen_main_numbers.append(occurrence.number)
            units.extend(materialize_main_occurrence(occurrence))
            if occurrence.editorial_start_index is not None:
                units.append(
                    make_editorial_unit(
                        source,
                        occurrence.editorial_start_index,
                        occurrence.end_index,
                        occurrence.number,
                        occurrence.occurrence,
                    )
                )
        if not occurrences:
            editorial_volume = standalone_editorial_volume(source)
            if editorial_volume is not None:
                occurrence = volume_occurrences[editorial_volume] or 1
                units.append(make_editorial_unit(source, 0, len(source.lines), editorial_volume, occurrence))
            elif source.body.strip():
                anomalies.append(f"{source.relative_path}: non-empty source body has no recognized volume or catalogue heading")
    for number, count in sorted(volume_occurrences.items()):
        if count > 1:
            anomalies.append(
                f"卷{number} occurs {count} times as an explicit main-volume block; occurrences were retained separately."
            )
    return sources, units, anomalies


def catalogue_volume_numbers(sources: Iterable[SourceFile]) -> set[int]:
    values: set[int] = set()
    for source in sources:
        for line in source.lines:
            match = re.match(rf"^[晉晋]書[卷巻](?P<number>{VOLUME_NUMBER})$", visible_line(line.text))
            if match:
                values.add(chinese_numeral_value(match.group("number")))
    return values


def source_span_dict(unit: Unit) -> dict[str, Any]:
    text_before_start = unit.source.body[: unit.start_offset]
    text_before_end = unit.source.body[: unit.end_offset]
    start_anchor, end_anchor = source_anchor(unit.source, unit.start_index, unit.end_index)
    return {
        "coordinate": "normalized_body",
        "start_char": unit.start_offset,
        "end_char_exclusive": unit.end_offset,
        "start_utf8_byte": len(text_before_start.encode("utf-8")),
        "end_utf8_byte_exclusive": len(text_before_end.encode("utf-8")),
        "source_line_start": unit.source_line_start,
        "source_line_end": unit.source_line_end,
        "start_anchor": start_anchor,
        "end_anchor": end_anchor,
    }


def unit_metadata(unit: Unit) -> dict[str, Any]:
    return {
        "schema": 1,
        "unit_id": unit.unit_id,
        "work": unit.work,
        "volume": unit.volume,
        "volume_number": unit.volume_number,
        "volume_occurrence": unit.volume_occurrence,
        "category": unit.category,
        "category_heading": unit.category_heading,
        "title": unit.title,
        "heading_text": unit.heading_text,
        "unit_kind": unit.unit_kind,
        "parent_unit": unit.parent_unit,
        "source_witness": PRIMARY_WITNESS,
        "source_file": unit.source.relative_path,
        "source_path": unit.source.raw_source_path,
        "source_sha256": unit.source.raw_source_sha256,
        "normalized_file_sha256": unit.source.normalized_sha256,
        "source_span": source_span_dict(unit),
        "page_marker_ids": unit.page_markers,
        "unit_text_sha256": unit.source_text_sha256,
        "character_count": len(unit.source_text),
        "boundary_confidence": unit.confidence,
        "note": unit.note,
        "text_policy": "verbatim substring of normalized primary-witness Markdown body; no reference-witness text inserted",
    }


def emit_yaml_mapping(data: Mapping[str, Any], indent: int = 0) -> list[str]:
    """Emit the small nested YAML subset used by unit front matter."""

    lines: list[str] = []
    prefix = " " * indent
    for key, value in data.items():
        if isinstance(value, Mapping):
            lines.append(f"{prefix}{key}:")
            lines.extend(emit_yaml_mapping(value, indent + 2))
        elif isinstance(value, list):
            if not value:
                lines.append(f"{prefix}{key}: []")
            else:
                lines.append(f"{prefix}{key}:")
                for item in value:
                    lines.append(f"{prefix}  - {quote_yaml(str(item))}")
        elif value is None:
            lines.append(f"{prefix}{key}: null")
        elif isinstance(value, bool):
            lines.append(f"{prefix}{key}: {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{prefix}{key}: {value}")
        else:
            lines.append(f"{prefix}{key}: {quote_yaml(str(value))}")
    return lines


def unit_markdown(unit: Unit) -> str:
    metadata = unit_metadata(unit)
    return "---\n" + "\n".join(emit_yaml_mapping(metadata)) + "\n---\n\n## Original source (exact)\n\n" + unit.source_text


def index_record(unit: Unit, output_path: Path, root: Path) -> dict[str, Any]:
    headings = [unit.title]
    if unit.category_heading and unit.category_heading not in headings:
        headings.insert(0, unit.category_heading)
    if unit.heading_text.strip() not in headings:
        headings.append(unit.heading_text.strip())
    try:
        file_path = output_path.relative_to(root).as_posix()
    except ValueError:
        file_path = output_path.as_posix()
    return {
        "unit_id": unit.unit_id,
        "work": unit.work,
        "volume": unit.volume,
        "volume_number": unit.volume_number,
        "volume_occurrence": unit.volume_occurrence,
        "category": unit.category,
        "title": unit.title,
        "aliases": [],
        "headings": list(dict.fromkeys(headings)),
        "unit_kind": unit.unit_kind,
        "parent_unit": unit.parent_unit,
        "file_path": file_path,
        "source_file": unit.source.relative_path,
        "source_span": source_span_dict(unit),
        "character_count": len(unit.source_text),
        "unit_text_sha256": unit.source_text_sha256,
        "source_witness": PRIMARY_WITNESS,
        "source_sha256": unit.source.raw_source_sha256,
        "boundary_confidence": unit.confidence,
    }


def write_units(
    units: Sequence[Unit], output_dir: Path, index_path: Path, root: Path = REPOSITORY_ROOT
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for unit in sorted(units, key=lambda item: (item.source.relative_path, item.start_offset, item.unit_id)):
        destination = output_dir / unit.category / f"{unit.unit_id}.md"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(unit_markdown(unit), encoding="utf-8", newline="\n")
        records.append(index_record(unit, destination, root))
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index = {
        "schema": 1,
        "stage": "jinshu-structural-units",
        "work": WORK,
        "source_witness": PRIMARY_WITNESS,
        "reference_witnesses": ["jinshu-jiaozhu"],
        "unit_count": len(records),
        "units": records,
    }
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return records


def validate_units(
    sources: Sequence[SourceFile], units: Sequence[Unit], root: Path = REPOSITORY_ROOT
) -> list[str]:
    errors: list[str] = []
    by_file: defaultdict[str, list[Unit]] = defaultdict(list)
    for unit in units:
        by_file[unit.source.relative_path].append(unit)
        if not unit.unit_id or not unit.source.relative_path or not unit.source.raw_source_sha256:
            errors.append(f"{unit.unit_id}: incomplete provenance")
        if unit.source.body[unit.start_offset : unit.end_offset] != unit.source_text:
            errors.append(f"{unit.unit_id}: source substring mismatch")
        if unit.end_offset <= unit.start_offset:
            errors.append(f"{unit.unit_id}: empty or inverted source span")
    ids = [unit.unit_id for unit in units]
    duplicates = sorted(unit_id for unit_id, count in Counter(ids).items() if count > 1)
    errors.extend(f"duplicate unit id: {unit_id}" for unit_id in duplicates)
    main_units = [unit for unit in units if unit.category not in {"catalogue", "editorial"}]
    main_numbers = {unit.volume_number for unit in main_units if unit.volume_number is not None}
    missing_volumes = sorted(EXPECTED_MAIN_VOLUMES - main_numbers)
    unexpected_volumes = sorted(main_numbers - EXPECTED_MAIN_VOLUMES)
    if missing_volumes:
        errors.append("missing canonical volume(s): " + ", ".join(f"卷{number}" for number in missing_volumes))
    if unexpected_volumes:
        errors.append("unexpected canonical volume(s): " + ", ".join(f"卷{number}" for number in unexpected_volumes))
    occurrence_values: defaultdict[int, set[int | None]] = defaultdict(set)
    for unit in main_units:
        if unit.volume_number is not None:
            occurrence_values[unit.volume_number].add(unit.volume_occurrence)
    for number in sorted(main_numbers & EXPECTED_MAIN_VOLUMES):
        if occurrence_values[number] != {1}:
            values = ", ".join("null" if value is None else str(value) for value in sorted(occurrence_values[number], key=lambda value: value or -1))
            errors.append(f"卷{number} has duplicate or non-canonical source occurrences: {values}")
    for source in sources:
        file_units = sorted(by_file[source.relative_path], key=lambda item: item.start_offset)
        if not file_units:
            errors.append(f"{source.relative_path}: no unit covers source body")
            continue
        cursor = 0
        reconstructed: list[str] = []
        for unit in file_units:
            if unit.start_offset != cursor:
                errors.append(
                    f"{source.relative_path}: gap or overlap before {unit.unit_id} at {cursor}->{unit.start_offset}"
                )
            reconstructed.append(unit.source_text)
            cursor = unit.end_offset
        if cursor != len(source.body):
            errors.append(f"{source.relative_path}: source suffix not covered at {cursor}->{len(source.body)}")
        if "".join(reconstructed) != source.body:
            errors.append(f"{source.relative_path}: concatenated unit text differs from normalized body")
        raw_path = root / source.raw_source_path if source.raw_source_path else None
        if raw_path is not None and raw_path.is_file() and source.raw_source_sha256:
            actual = sha256_bytes(raw_path.read_bytes())
            if actual != source.raw_source_sha256:
                errors.append(f"{source.relative_path}: raw source SHA-256 differs from normalized metadata")
    return errors


def structural_report(
    sources: Sequence[SourceFile], units: Sequence[Unit], anomalies: Sequence[str], errors: Sequence[str]
) -> str:
    main_units = [unit for unit in units if unit.category not in {"catalogue", "editorial"}]
    volumes = sorted({unit.volume_number for unit in main_units if unit.volume_number is not None})
    occurrence_counts = Counter(
        (unit.volume_number, unit.volume_occurrence)
        for unit in main_units
        if unit.volume_number is not None
    )
    canonical_occurrences = {
        number: {unit.volume_occurrence for unit in main_units if unit.volume_number == number}
        for number in volumes
    }
    counts = Counter(unit.category for unit in units)
    uncertain = [unit for unit in units if unit.confidence != "high"]
    catalogue_numbers = catalogue_volume_numbers(sources)
    missing = sorted(catalogue_numbers - set(volumes))
    catalogue_text = "\n".join(
        source.body for source in sources if source.path.name.endswith("_000.md")
    )
    catalogue_count_anomaly = (
        "晉書一百三十卷" in catalogue_text and len(catalogue_numbers) != 130
    )
    lines = [
        "# Jinshu structural report",
        "",
        "This report was generated from the normalized primary witness only:",
        f"`{PRIMARY_WITNESS}`. Raw and normalized source files were not modified.",
        "Reference witnesses, including 《晉書斠注》, were not used to create or correct units.",
        "",
        "## Validation",
        "",
        f"- normalized source files: {len(sources)}",
        f"- materialized units: {len(units)}",
        f"- result: {'passed' if not errors else 'failed'}",
        "- validation checks exact normalized-body substring coverage, non-overlap, provenance, and source hashes; it does not assert historical correctness.",
        "",
        "## Volumes detected",
        "",
        f"- unique main-volume numbers detected: {len(volumes)}",
        f"- canonical coverage check (卷1-卷130 exactly once): {'passed' if set(volumes) == EXPECTED_MAIN_VOLUMES and all(values == {1} for values in canonical_occurrences.values()) else 'failed'}",
        f"- detected range/list: {', '.join(f'卷{n}' for n in volumes) if volumes else 'none'}",
        f"- main-volume occurrences (including repeated source blocks): {len(occurrence_counts)}",
        f"- catalogue volume numbers detected: {len(catalogue_numbers)}",
    ]
    if missing:
        lines.append(
            "- catalogue-listed volume numbers without a corresponding explicit main block: "
            + ", ".join(f"卷{number}" for number in missing)
        )
    lines.extend(["", "## Units by category", "", "| category | units |", "|---|---:|"])
    for category in ("catalogue", "benji", "zhi", "liezhuan", "zaiji", "editorial", "unknown"):
        lines.append(f"| `{category}` | {counts[category]} |")
    lines.extend(["", "## Uncertain structural boundaries", ""])
    if uncertain:
        for unit in uncertain:
            lines.append(
                f"- `{unit.unit_id}` ({unit.volume} / {unit.category} / {unit.title}): "
                + (unit.note or "confidence is not high")
            )
    else:
        lines.append("None.")
    lines.extend(["", "## Source anomalies", ""])
    if anomalies:
        lines.extend(f"- {anomaly}" for anomaly in anomalies)
    else:
        lines.append("None detected by the structural parser.")
    if catalogue_count_anomaly:
        lines.append(
            "The 提要 states 晉書一百三十卷, while the explicit 目錄 contains "
            f"{len(catalogue_numbers)} distinct volume headings; the displayed sequence "
            "also repeats 卷四十三至卷四十五 and jumps to 卷五十. This is retained as "
            "a catalogue-source anomaly, not repaired or used to invent units."
        )
    if errors:
        lines.extend(["", "## Validation errors", ""])
        lines.extend(f"- {error}" for error in errors)
    return "\n".join(lines) + "\n"


def materialize(
    *,
    root: Path = REPOSITORY_ROOT,
    source_dir: Path = DEFAULT_SOURCE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    index_path: Path = DEFAULT_INDEX_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
) -> tuple[list[SourceFile], list[Unit], list[str], list[str]]:
    sources, units, anomalies = parse_sources(source_dir, root)
    errors = validate_units(sources, units, root)
    if not errors:
        write_units(units, output_dir, index_path, root)
    else:
        # Still write a report, but do not materialize an invalid corpus.
        report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(structural_report(sources, units, anomalies, errors), encoding="utf-8", newline="\n")
    if errors:
        raise ValueError("Jinshu structural validation failed:\n" + "\n".join(errors))
    return sources, units, anomalies, errors


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        sources, units, anomalies, _errors = materialize(
            root=args.root,
            source_dir=args.source_dir,
            output_dir=args.output_dir,
            index_path=args.index,
            report_path=args.report,
        )
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"processed {len(sources)} normalized files; generated {len(units)} units")
    if anomalies:
        print(f"reported {len(anomalies)} structural anomalies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
