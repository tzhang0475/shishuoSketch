#!/usr/bin/env python3
"""Build read-only Shishuo witness comparison views and discrepancy reports.

This is the first comparison layer after normalization and segmentation.  It
does not edit a witness, a chapter, an entry, or a boundary manifest.  The
derived files deliberately retain the source characters and represent
unrendered Wikisource glyph templates as explicit alignment tokens rather
than guessing a character.

The script is intentionally deterministic and network-free.  It consumes the
already downloaded/registered witnesses and records unavailable external
witnesses as unavailable instead of scraping them.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Sequence

import yaml

try:
    from . import propose_shishuo_boundaries as proposal
    from . import segment_shishuo_entries as segmentation
except ImportError:  # pragma: no cover - direct script execution
    import propose_shishuo_boundaries as proposal
    import segment_shishuo_entries as segmentation


REPO_ROOT = Path(__file__).resolve().parents[1]
CHAPTER_ROOT = REPO_ROOT / "content/processed/shishuo/chapters"
BOUNDARY_ROOT = REPO_ROOT / "content/curated/shishuo/boundaries"
WIKISOURCE_ROOT = REPO_ROOT / "sources/downloads/shishuo/wikisource-sbck"
LING_ROOT = REPO_ROOT / "sources/downloads/shishuo/ling-1615"
REFERENCE_PATH = REPO_ROOT / "sources/local/shishuo/reference-txt/shishuo.txt"
OUTPUT_ROOT = REPO_ROOT / "content/processed/shishuo/collation"
REPORT_ROOT = REPO_ROOT / "content/curated/shishuo/collation"

CHAPTERS: tuple[tuple[int, str, str], ...] = tuple(
    (number, proposal.CHAPTER_SLUGS[number - 1], proposal.CHAPTER_HEADINGS[number - 1])
    for number in range(1, 37)
)

SECTION_ORDER = (
    "卷上之上",
    "卷上之下",
    "卷中之上",
    "卷中之下",
    "卷下之上",
    "卷下之下",
)

ALIGNMENT_GLYPH = "\ue000"
KR_ENTITY_RE = re.compile(r"&KR[0-9A-Za-z]+;")
WIKISOURCE_GLYPH_RE = re.compile(r"⟦\{\{SKchar\|[^{}]*\}\}⟧")
PAGE_COMMENT_RE = segmentation.PAGE_COMMENT_RE

KNOWN_CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "05-fangzheng-014",
        "chapter": 5,
        "expected_ordinal": 14,
        "kind": "guide_gap",
        "wikisource_anchor": "晉武帝時荀朂爲中書監",
    },
    {
        "id": "08-shangyu-084",
        "chapter": 8,
        "expected_ordinal": 84,
        "kind": "guide_gap",
        "wikisource_anchor": "王長史道江道羣人所應有",
    },
    {
        "id": "08-shangyu-085",
        "chapter": 8,
        "expected_ordinal": 85,
        "kind": "guide_gap",
        "wikisource_anchor": "會稽孔沉魏顗虞球虞存謝奉",
    },
    {
        "id": "18-qiyi-002",
        "chapter": 18,
        "expected_ordinal": 2,
        "kind": "guide_gap",
        "wikisource_anchor": "嵇康遊於汲郡山中遇道士孫登",
    },
    {
        "id": "18-qiyi-011",
        "chapter": 18,
        "expected_ordinal": 11,
        "kind": "guide_gap",
        "wikisource_anchor": "康僧淵在豫章去郭數十里立精舍",
    },
    {
        "id": "19-xianyuan-005",
        "chapter": 19,
        "expected_ordinal": 5,
        "kind": "guide_gap",
        "wikisource_anchor": "趙母嫁女女臨去敕之曰慎勿為好",
    },
    {
        "id": "18-qiyi-010",
        "chapter": 18,
        "expected_ordinal": 10,
        "kind": "boundary_shift",
        "wikisource_anchor": "孟萬年及弟少孤居武昌陽新縣萬年遊宦",
    },
    {
        "id": "18-qiyi-015",
        "chapter": 18,
        "expected_ordinal": 15,
        "kind": "boundary_shift",
        "wikisource_anchor": "郄尚書與謝居士善常稱謝慶緒",
    },
    {
        "id": "25-paidiao-019",
        "chapter": 25,
        "expected_ordinal": 19,
        "kind": "boundary_shift",
        "wikisource_anchor": "于寳向劉真長",
    },
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def compact(text: str) -> str:
    return "".join(character for character in text if not character.isspace())


def alignment_key(text: str) -> str:
    """Return a comparison key without changing the emitted source copy.

    Wikisource has explicit ``SKchar`` templates and the Kanripo normalized
    text can contain ``&KR....;`` placeholders.  Both are represented by one
    private-use token only in this alignment key.  The derived source copy
    keeps the original marker spelling, and reports call the token out.
    """

    text = compact(text)
    text = WIKISOURCE_GLYPH_RE.sub(ALIGNMENT_GLYPH, text)
    text = KR_ENTITY_RE.sub(ALIGNMENT_GLYPH, text)
    return text


def strip_parenthetical(text: str) -> str:
    """Remove balanced top-level and nested ASCII parenthetical annotations."""

    result: list[str] = []
    depth = 0
    for character in text:
        if character == "(":
            depth += 1
        elif character == ")" and depth:
            depth -= 1
        elif depth == 0:
            result.append(character)
    return "".join(result)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


@dataclass(frozen=True)
class KUnit:
    raw: str
    key: str
    body_offset: int
    normalized_line: int
    source_line: int
    page_marker: str


@dataclass(frozen=True)
class WUnit:
    raw: str
    key: str
    page_title: str
    page_number: int
    path: str
    source_url: str
    revision_id: int | None


@dataclass(frozen=True)
class KEntryView:
    entry_id: str
    ordinal: int
    opening_text: str
    opening_key: str
    start_body_offset: int
    start_unit: int
    end_unit: int
    source_normalized_line: int
    source_line: int | None
    page_marker: str
    main_raw: str
    main_key: str


@dataclass(frozen=True)
class KChapter:
    number: int
    slug: str
    heading: str
    chapter_path: Path
    manifest_path: Path
    metadata: dict[str, Any]
    body: str
    main_units: tuple[KUnit, ...]
    comparison_units: tuple[KUnit, ...]
    annotations: tuple[str, ...]
    page_markers: tuple[str, ...]
    entries: tuple[KEntryView, ...]


@dataclass(frozen=True)
class WPage:
    record: dict[str, Any]
    raw_text: str
    main_units: tuple[WUnit, ...]
    annotations: tuple[str, ...]


@dataclass(frozen=True)
class WChapter:
    number: int
    slug: str
    heading: str
    global_start: int
    global_end: int
    main_units: tuple[WUnit, ...]
    comparison_units: tuple[WUnit, ...]
    annotation_count: int

    @property
    def key_text(self) -> str:
        return "".join(unit.key for unit in self.comparison_units)

    @property
    def raw_text(self) -> str:
        return "".join(unit.raw for unit in self.comparison_units)


@dataclass(frozen=True)
class WMatch:
    index: int
    length: int
    match_type: str
    candidate: str


def _line_is_layout(line: str, heading: str) -> bool:
    stripped = line.strip()
    if not stripped or PAGE_COMMENT_RE.fullmatch(stripped):
        return True
    if stripped.startswith("<!--") and stripped.endswith("-->"):
        return True
    if stripped.startswith("世說新語") or stripped.startswith("世説新語"):
        return "第" not in stripped
    return False


def _layout_spans(body: str, heading: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    offset = 0
    for raw_line in body.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        if _line_is_layout(line, heading):
            spans.append((offset, offset + len(raw_line)))
        offset += len(raw_line)
    return spans


def _in_spans(offset: int, spans: Sequence[tuple[int, int]], cursor: int) -> tuple[bool, int]:
    while cursor < len(spans) and offset >= spans[cursor][1]:
        cursor += 1
    return cursor < len(spans) and spans[cursor][0] <= offset < spans[cursor][1], cursor


def _parse_kanripo_main(
    body: str,
    heading: str,
    metadata: dict[str, Any],
) -> tuple[tuple[KUnit, ...], tuple[str, ...], tuple[str, ...]]:
    spans = _layout_spans(body, heading)
    frontmatter_start = metadata["start_normalized_line"]
    source_start = metadata["start_source_line"]
    page_start = metadata["start_page_marker"]
    lines = segmentation._build_source_lines(body, frontmatter_start, source_start, page_start)
    units: list[KUnit] = []
    annotations: list[str] = []
    page_markers = tuple(match.group("marker") for match in PAGE_COMMENT_RE.finditer(body))
    depth = 0
    annotation_start: int | None = None
    span_cursor = 0
    offset = 0
    while offset < len(body):
        layout, span_cursor = _in_spans(offset, spans, span_cursor)
        if layout:
            offset += 1
            continue
        page_match = PAGE_COMMENT_RE.match(body, offset)
        if page_match is not None:
            offset = page_match.end()
            continue
        if body.startswith("<!--", offset):
            end = body.find("-->", offset + 4)
            offset = len(body) if end < 0 else end + 3
            continue
        entity = KR_ENTITY_RE.match(body, offset)
        if entity is not None and depth == 0:
            line = segmentation._line_at(lines, offset)
            raw = entity.group(0)
            units.append(
                KUnit(
                    raw=raw,
                    key=ALIGNMENT_GLYPH,
                    body_offset=offset,
                    normalized_line=line.normalized_line,
                    source_line=line.source_line,
                    page_marker=line.page_marker,
                )
            )
            offset = entity.end()
            continue
        character = body[offset]
        if character == "(":
            if depth == 0:
                annotation_start = offset
            depth += 1
        elif character == ")" and depth:
            depth -= 1
            if depth == 0 and annotation_start is not None:
                annotations.append(body[annotation_start : offset + 1])
                annotation_start = None
        elif depth == 0 and not character.isspace():
            line = segmentation._line_at(lines, offset)
            units.append(
                KUnit(
                    raw=character,
                    key=alignment_key(character),
                    body_offset=offset,
                    normalized_line=line.normalized_line,
                    source_line=line.source_line,
                    page_marker=line.page_marker,
                )
            )
        offset += 1
    if depth:
        raise ValueError(f"unbalanced Kanripo annotations in {heading}")
    return tuple(units), tuple(annotations), page_markers


def _layout_patterns() -> tuple[str, ...]:
    titles = (
        "世說新語卷上之上",
        "世説新語卷上之上",
        "世說新語卷上之下",
        "世説新語卷上之下",
        "世說新語中之上",
        "世説新語中之上",
        "世說新語卷中之上",
        "世説新語卷中之上",
        "世說新語中之下",
        "世説新語中之下",
        "世說新語卷中之下",
        "世説新語卷中之下",
        "世說新語卷下之上",
        "世説新語卷下之上",
        "世說新語卷下之下",
        "世説新語卷下之下",
        "世說新語卷之下",
        "世説新語卷之下",
    )
    return tuple(sorted(set(titles + proposal.CHAPTER_HEADINGS), key=len, reverse=True))


def remove_layout_units(units: Sequence[KUnit | WUnit]) -> tuple[KUnit | WUnit, ...]:
    patterns = tuple(alignment_key(pattern) for pattern in _layout_patterns())
    keys = [unit.key for unit in units]
    kept: list[KUnit | WUnit] = []
    index = 0
    while index < len(units):
        matched = False
        for pattern in patterns:
            if pattern and "".join(keys[index : index + len(pattern)]) == pattern:
                index += len(pattern)
                matched = True
                break
        if not matched:
            kept.append(units[index])
            index += 1
    return tuple(kept)


def _parse_manifest(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("entries"), list):
        raise ValueError(f"invalid boundary manifest: {path}")
    return document


def _chapter_metadata(frontmatter: str, manifest: dict[str, Any]) -> dict[str, Any]:
    meta = segmentation._read_chapter_metadata(frontmatter, manifest)
    return {
        "source_normalized_filename": meta.normalized_filename,
        "source_path": meta.source_path,
        "source_sha256": meta.source_sha256,
        "FILE": meta.file_section,
        "kanripo_title": meta.title,
        "kanripo_id": meta.kanripo_id,
        "kanripo_baseedition": meta.baseedition,
        "kanripo_witness": meta.witness,
        "start_normalized_line": meta.start_normalized_line,
        "start_source_line": meta.start_source_line,
        "start_page_marker": meta.start_page_marker,
    }


def _body_anchor_positions(body: str, anchor: str) -> list[int]:
    positions: list[int] = []
    cursor = 0
    while True:
        position = body.find(anchor, cursor)
        if position < 0:
            return positions
        positions.append(position)
        cursor = position + 1


def load_kanripo_chapter(number: int, slug: str, heading: str) -> KChapter:
    chapter_path = CHAPTER_ROOT / f"chapter-{number:02d}.md"
    manifest_path = next(BOUNDARY_ROOT.glob(f"{number:02d}-*.yaml"))
    chapter_text = chapter_path.read_text(encoding="utf-8")
    frontmatter, body = segmentation._split_frontmatter(chapter_text)
    manifest = _parse_manifest(manifest_path)
    metadata = _chapter_metadata(frontmatter, manifest)
    main_units, annotations, page_markers = _parse_kanripo_main(body, heading, metadata)
    comparison_units = tuple(remove_layout_units(main_units))
    raw_offsets = [unit.body_offset for unit in main_units]
    comparison_raw_indexes = {id(unit): index for index, unit in enumerate(comparison_units)}
    entries_raw: list[tuple[dict[str, Any], int, int]] = []
    for item in manifest["entries"]:
        anchor = str(item["opening_text"])
        positions = _body_anchor_positions(body, anchor)
        if len(positions) != 1:
            raise ValueError(
                f"{item['id']}: expected one source anchor, found {len(positions)}"
            )
        entries_raw.append((item, positions[0], bisect_left(raw_offsets, positions[0])))
    entry_views: list[KEntryView] = []
    for index, (item, body_offset, raw_index) in enumerate(entries_raw):
        next_raw_index = (
            entries_raw[index + 1][2] if index + 1 < len(entries_raw) else len(main_units)
        )
        # Find the corresponding indices after editorial/layout strings have
        # been removed.  Boundaries begin in main text in the current proposal
        # set; if one falls inside an annotation, this deliberately selects the
        # first surviving main character after it rather than inventing text.
        start_unit = next(
            (i for i, unit in enumerate(comparison_units) if unit.body_offset >= body_offset),
            len(comparison_units),
        )
        end_body = (
            entries_raw[index + 1][1] if index + 1 < len(entries_raw) else len(body)
        )
        end_unit = next(
            (i for i, unit in enumerate(comparison_units) if unit.body_offset >= end_body),
            len(comparison_units),
        )
        main_raw = "".join(unit.raw for unit in comparison_units[start_unit:end_unit])
        entry_views.append(
            KEntryView(
                entry_id=str(item["id"]),
                ordinal=int(item["ordinal"]),
                opening_text=str(item["opening_text"]),
                opening_key=alignment_key(strip_parenthetical(str(item["opening_text"]))),
                start_body_offset=body_offset,
                start_unit=start_unit,
                end_unit=end_unit,
                source_normalized_line=int(item["source_normalized_line"]),
                source_line=(int(item["source_line"]) if item.get("source_line") is not None else None),
                page_marker=str(item.get("source_page_marker", "")),
                main_raw=main_raw,
                main_key=alignment_key(main_raw),
            )
        )
    return KChapter(
        number=number,
        slug=slug,
        heading=heading,
        chapter_path=chapter_path,
        manifest_path=manifest_path,
        metadata=metadata,
        body=body,
        main_units=tuple(main_units),
        comparison_units=tuple(comparison_units),
        annotations=annotations,
        page_markers=page_markers,
        entries=tuple(entry_views),
    )


def _template_end(text: str, start: int) -> int:
    depth = 1
    index = start + 2
    while index < len(text) and depth:
        if text.startswith("{{", index):
            depth += 1
            index += 2
        elif text.startswith("}}", index):
            depth -= 1
            index += 2
        else:
            index += 1
    return index


def _extract_wikisource_page(text: str, record: dict[str, Any]) -> WPage:
    # noinclude contains page-quality and footer/layout declarations, not the
    # page's textual witness.  It is removed only from this derived view.
    text = re.sub(r"<noinclude>.*?</noinclude>", "", text, flags=re.DOTALL)
    text = re.sub(r"<includeonly>.*?</includeonly>", "", text, flags=re.DOTALL)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    fragments: list[str] = []
    annotations: list[str] = []
    index = 0
    while index < len(text):
        start = text.find("{{", index)
        if start < 0:
            fragments.append(text[index:])
            break
        fragments.append(text[index:start])
        end = _template_end(text, start)
        raw = text[start:end]
        inner = raw[2:-2] if raw.endswith("}}") else raw[2:]
        name = inner.split("|", 1)[0].strip()
        if "雙行註文" in name:
            annotations.append(raw)
        elif "SKchar" in name:
            # Keep the marker visible in the derived copy.  alignment_key()
            # maps this explicit marker to ALIGNMENT_GLYPH.
            fragments.append("⟦" + raw + "⟧")
        # Other templates in these Page records are layout helpers and are
        # omitted from the alignment stream.
        index = end
    clean_text = "".join(fragments)
    clean_text = re.sub(r"<[^>]+>", "", clean_text)
    clean_text = clean_text.replace("[[", "").replace("]]", "")
    units: list[WUnit] = []
    entity_match = re.compile(r"&KR[0-9A-Za-z]+;")
    index = 0
    while index < len(clean_text):
        glyph = WIKISOURCE_GLYPH_RE.match(clean_text, index)
        if glyph is not None:
            raw = glyph.group(0)
            units.append(
                WUnit(
                    raw=raw,
                    key=ALIGNMENT_GLYPH,
                    page_title=str(record.get("page_title", "")),
                    page_number=int(record.get("page_number", 0)),
                    path=str(record["path"]),
                    source_url=str(record.get("source_url", "")),
                    revision_id=(int(record["revision_id"]) if record.get("revision_id") else None),
                )
            )
            index = glyph.end()
            continue
        entity = entity_match.match(clean_text, index)
        if entity is not None:
            raw = entity.group(0)
            units.append(
                WUnit(
                    raw=raw,
                    key=ALIGNMENT_GLYPH,
                    page_title=str(record.get("page_title", "")),
                    page_number=int(record.get("page_number", 0)),
                    path=str(record["path"]),
                    source_url=str(record.get("source_url", "")),
                    revision_id=(int(record["revision_id"]) if record.get("revision_id") else None),
                )
            )
            index = entity.end()
            continue
        character = clean_text[index]
        if not character.isspace():
            units.append(
                WUnit(
                    raw=character,
                    key=alignment_key(character),
                    page_title=str(record.get("page_title", "")),
                    page_number=int(record.get("page_number", 0)),
                    path=str(record["path"]),
                    source_url=str(record.get("source_url", "")),
                    revision_id=(int(record["revision_id"]) if record.get("revision_id") else None),
                )
            )
        index += 1
    return WPage(record=record, raw_text=text, main_units=tuple(units), annotations=tuple(annotations))


def load_wikisource() -> tuple[tuple[WUnit, ...], tuple[WPage, ...], dict[str, Any]]:
    lock_path = WIKISOURCE_ROOT / "manifest.lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    records = [record for record in lock["records"] if record.get("kind") == "page"]
    order = {section: index for index, section in enumerate(SECTION_ORDER)}
    records.sort(key=lambda record: (order.get(str(record.get("section_title")), 99), int(record.get("page_number", 0)), str(record.get("page_title", ""))))
    pages: list[WPage] = []
    units: list[WUnit] = []
    for record in records:
        path = REPO_ROOT / str(record["path"])
        page = _extract_wikisource_page(path.read_text(encoding="utf-8"), record)
        pages.append(page)
        units.extend(page.main_units)
    return tuple(units), tuple(pages), lock


def make_wikisource_chapters(
    global_units: Sequence[WUnit],
    page_annotation_counts: dict[str, int] | None = None,
) -> dict[int, WChapter]:
    global_keys = "".join(unit.key for unit in global_units)
    chapter_positions: list[tuple[int, int]] = []
    cursor = 0
    for number, _slug, heading in CHAPTERS:
        heading_key = alignment_key(heading)
        start = global_keys.find(heading_key, cursor)
        if start < 0:
            chapter_positions.append((-1, -1))
            continue
        chapter_positions.append((start, start + len(heading_key)))
        cursor = start + len(heading_key)
    result: dict[int, WChapter] = {}
    for index, (number, slug, heading) in enumerate(CHAPTERS):
        start, _heading_end = chapter_positions[index]
        if start < 0:
            result[number] = WChapter(number, slug, heading, -1, -1, (), (), 0)
            continue
        following = [item[0] for item in chapter_positions[index + 1 :] if item[0] >= 0]
        end = following[0] if following else len(global_units)
        chapter_units = tuple(global_units[start:end])
        comparison_units = tuple(remove_layout_units(chapter_units))
        pages = {unit.page_title for unit in chapter_units}
        # Page-level count is intentionally conservative: a page at a chapter
        # boundary may contain material from both adjacent headings.
        annotation_count = sum(
            (page_annotation_counts or {}).get(page_title, 0) for page_title in pages
        )
        result[number] = WChapter(
            number=number,
            slug=slug,
            heading=heading,
            global_start=start,
            global_end=end,
            main_units=chapter_units,
            comparison_units=comparison_units,
            annotation_count=annotation_count,
        )
    return result


def _find_all(text: str, needle: str, lower: int = 0) -> list[int]:
    if not needle:
        return []
    result: list[int] = []
    cursor = lower
    while True:
        position = text.find(needle, cursor)
        if position < 0:
            return result
        result.append(position)
        cursor = position + 1


def find_witness_match(view: WChapter, anchor: str, lower: int = 0) -> WMatch | None:
    key = alignment_key(anchor)
    text = view.key_text
    exact = _find_all(text, key, lower)
    if len(exact) == 1:
        return WMatch(exact[0], len(key), "exact", key)
    if len(exact) > 1:
        return WMatch(exact[0], len(key), "duplicate-exact", key)
    for length in range(min(len(key), 36), 7, -1):
        prefix = key[:length]
        candidates = _find_all(text, prefix, lower)
        if len(candidates) == 1:
            return WMatch(candidates[0], length, "prefix", prefix)
    for length in range(min(len(key), 36), 7, -1):
        suffix = key[-length:]
        candidates = _find_all(text, suffix, lower)
        if len(candidates) == 1:
            return WMatch(candidates[0], length, "suffix", suffix)
    return None


def _unit_context(units: Sequence[KUnit | WUnit], index: int, before: int = 80, after: int = 180) -> str:
    start = max(0, index - before)
    end = min(len(units), index + after)
    return "".join(unit.raw for unit in units[start:end])


def _source_context(body: str, offset: int, before: int = 220, after: int = 320) -> str:
    return body[max(0, offset - before) : min(len(body), offset + after)]


def _page_record_for_match(view: WChapter, match: WMatch) -> dict[str, Any]:
    if not view.comparison_units:
        return {}
    unit = view.comparison_units[min(match.index, len(view.comparison_units) - 1)]
    return {
        "page_title": unit.page_title,
        "page_number": unit.page_number,
        "path": unit.path,
        "source_url": unit.source_url,
        "revision_id": unit.revision_id,
    }


def _reference_entries() -> dict[int, tuple[Any, ...]]:
    if not REFERENCE_PATH.exists():
        return {}
    return {
        number: proposal.load_reference_chapter(REFERENCE_PATH, number).entries
        for number, _slug, _heading in CHAPTERS
    }


def _ling_evidence(chapter: int) -> dict[str, Any]:
    volume = 1 if chapter <= 4 else 2 if chapter <= 13 else 3
    ocr_path = LING_ROOT / "ocr" / f"shishuoxinyu3jua0{volume}liuy_djvu.txt"
    pdf_path = LING_ROOT / "pdf" / f"shishuoxinyu3jua0{volume}liuy.pdf"
    ocr_text = ocr_path.read_text(encoding="utf-8", errors="replace") if ocr_path.exists() else ""
    pdf_status = "available"
    pdf_size: int | None = None
    pdf_sha256: str | None = None
    pdf_readability: str | None = None
    lock_path = LING_ROOT / "manifest.lock.json"
    if lock_path.exists():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        locked_record = next(
            (record for record in lock.get("records", []) if int(record.get("volume", 0)) == volume),
            {},
        )
        locked_pdf = next(
            (item for item in locked_record.get("files", []) if item.get("kind") == "pdf"),
            {},
        )
        pdf_size = locked_pdf.get("size")
        pdf_sha256 = locked_pdf.get("sha256")
        pdf_readability = locked_pdf.get("pdf_readability")
        if locked_pdf.get("status") == "refreshed" and pdf_readability == "passed":
            pdf_status = "available_readable"
    return {
        "witness_id": "shishuo-ling-1615",
        "volume": volume,
        "ocr_path": str(ocr_path.relative_to(REPO_ROOT)) if ocr_path.exists() else None,
        "ocr_search": "no reliable exact Chinese hit for the anomaly anchor in the downloaded OCR",
        "ocr_character_count": len(ocr_text),
        "pdf_path": str(pdf_path.relative_to(REPO_ROOT)) if pdf_path.exists() else None,
        "pdf_status": pdf_status,
        "pdf_readability": pdf_readability,
        "pdf_size": pdf_size,
        "pdf_sha256": pdf_sha256,
        "pdf_authority": "page image is authoritative; OCR is search convenience only",
        "reading": None,
        "confidence": "low",
        "note": (
            "The OCR derivative is not usable for locating these anchors. "
            + ("The refreshed volume-3 PDF passed readability checks; no reading is asserted from it without direct page inspection." if volume == 3 and pdf_status == "available_readable" else "The local volume-3 PDF is not verified readable; no reading is asserted from it." if volume == 3 else "The volume PDF is readable, but no anomaly page was deterministically located from the failed OCR; no reading is asserted from OCR.")
        ),
    }


def _siku_evidence() -> dict[str, Any]:
    return {
        "witness_id": "shishuo-siku",
        "status": "external_only_not_scraped",
        "reading": None,
        "ctext_visual_url": "https://ctext.org/library.pl?if=gb&remap=gb&res=5115",
        "wikisource_record": "https://zh.wikisource.org/zh/世說新語_%28四庫全書本%29",
        "note": "The 四庫本 family is registered externally; no bulk scrape or local comparison copy was made.",
    }


def _known_context_k(chapter: KChapter, ordinal: int) -> dict[str, Any]:
    item = chapter.entries[ordinal - 1] if 0 < ordinal <= len(chapter.entries) else None
    if item is None:
        return {"status": "not_present", "reading": None}
    body_context = _source_context(chapter.body, item.start_body_offset)
    marker_window = tuple(dict.fromkeys(PAGE_COMMENT_RE.findall(body_context)))
    return {
        "status": "present_as_current_proposal",
        "entry_id": item.entry_id,
        "opening_text": item.opening_text,
        "main_reading": item.main_raw[:220],
        "source_chapter": str(chapter.chapter_path.relative_to(REPO_ROOT)),
        "source_normalized_line": item.source_normalized_line,
        "source_line": item.source_line,
        "page_marker": item.page_marker,
        "source_context": body_context,
        "page_markers_in_context": list(marker_window),
    }


def _witness_reading(view: WChapter, anchor: str) -> dict[str, Any]:
    match = find_witness_match(view, anchor)
    if match is None:
        return {"status": "not_located", "anchor": anchor, "reading": None}
    page = _page_record_for_match(view, match)
    context = _unit_context(view.comparison_units, match.index, 80, max(220, match.length + 140))
    return {
        "status": "located",
        "anchor_used": anchor,
        "match_type": match.match_type,
        "reading": context,
        "page": page,
        "note": "Whitespace/layout was removed in this derived view; marker templates remain explicit.",
    }


def build_known_anomaly_records(
    kanripo: dict[int, KChapter],
    wikisource: dict[int, WChapter],
    references: dict[int, tuple[Any, ...]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for case in KNOWN_CASES:
        chapter = kanripo[case["chapter"]]
        wchapter = wikisource[case["chapter"]]
        reference_items = references.get(case["chapter"], ())
        reference = next(
            (item for item in reference_items if item.ordinal == case["expected_ordinal"]),
            None,
        )
        k_context = _known_context_k(chapter, case["expected_ordinal"])
        if case["kind"] == "guide_gap":
            classification = "kanripo_digitization_gap"
            confidence = "high" if find_witness_match(wchapter, case["wikisource_anchor"]) else "medium"
            recommended = (
                "Retain the Kanripo source unchanged. Use the Wikisource same-edition page witness as missing-text evidence, then verify against Ling page images and/or 四庫本 before any future reviewed repair."
            )
            missing_supplier = "shishuo-wikisource-sbck"
            k_context["status"] = "structural_reference_opening_absent"
        else:
            classification = "boundary_shift"
            confidence = "high"
            recommended = "Do not edit the source in this task. Review only the boundary manifest: remove the false continuation boundary or move it to the surviving entry opening described by the same-edition witness."
            missing_supplier = None
        w_evidence = _witness_reading(wchapter, case["wikisource_anchor"])
        if case["id"] == "18-qiyi-010":
            w_evidence["boundary_observation"] = "The full 孟萬年 / 少孤 continuation remains contiguous before the next independent 康僧淵 entry; 病篤... is not supported as an opening."
        elif case["id"] == "18-qiyi-015":
            w_evidence["boundary_observation"] = "The page witness begins 郄尚書與謝居士善..., including 郄 before the Kanripo proposed anchor 尚書...."
        elif case["id"] == "25-paidiao-019":
            w_evidence["boundary_observation"] = "The page witness has the preceding 王丞相 / 周伯仁 text ending before 于寳向劉真長; the Kanripo 人 is not the new-entry opening."
        record = {
            "id": case["id"],
            "chapter": f"{chapter.number:02d}-{chapter.slug}",
            "chapter_slug": chapter.slug,
            "canonical_heading": chapter.heading,
            "expected_ordinal": case["expected_ordinal"],
            "classification": classification,
            "confidence": confidence,
            "recommended_resolution": recommended,
            "missing_text_supplier": missing_supplier,
            "kanripo": k_context,
            "wikisource_sbck": w_evidence,
            "ling_1615": _ling_evidence(case["chapter"]),
            "siku": _siku_evidence(),
            "structural_reference": {
                "status": "alignment_guide_only" if reference else "not_located",
                "ordinal": case["expected_ordinal"],
                "opening_reading": reference.opening_text if reference else None,
                "main_reading": reference.main_text[:280] if reference else None,
                "authority": "low textual authority; high structural comparison utility",
                "note": "The checked-in reference is simplified-or-mixed; the displayed reading is the deterministic ICU alignment form and is not a textual emendation.",
            },
            "provenance": {
                "primary_source": str(chapter.chapter_path.relative_to(REPO_ROOT)),
                "boundary_manifest": str(chapter.manifest_path.relative_to(REPO_ROOT)),
                "wikisource_lock": str((WIKISOURCE_ROOT / "manifest.lock.json").relative_to(REPO_ROOT)),
            },
        }
        records.append(record)
    return records


def _entry_scan_records(
    chapter: KChapter,
    wchapter: WChapter,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    lower = 0
    matched = 0
    duplicate = 0
    prefix = 0
    suffix = 0
    unmatched = 0
    for entry in chapter.entries:
        match = find_witness_match(wchapter, entry.opening_key, lower)
        if match is None:
            unmatched += 1
            records.append(
                {
                    "chapter": f"{chapter.number:02d}-{chapter.slug}",
                    "chapter_slug": chapter.slug,
                    "entry_id": entry.entry_id,
                    "ordinal": entry.ordinal,
                    "discrepancy_type": "unmatched_entry_opening",
                    "classification": "unresolved",
                    "confidence": "low",
                    "kanripo_location": {
                        "source": str(chapter.chapter_path.relative_to(REPO_ROOT)),
                        "source_normalized_line": entry.source_normalized_line,
                        "source_line": entry.source_line,
                        "page_marker": entry.page_marker,
                    },
                    "kanripo_reading": entry.opening_key,
                    "kanripo_reading_raw": entry.opening_text,
                    "wikisource_location": None,
                    "wikisource_reading": None,
                    "requires_visual_verification": True,
                    "recommended_action": "Inspect the same-edition page witness and the relevant glyph/character reading before classifying as a textual variant or source gap.",
                }
            )
            continue
        if match.match_type == "duplicate-exact":
            duplicate += 1
        elif match.match_type == "prefix":
            prefix += 1
        elif match.match_type == "suffix":
            suffix += 1
        else:
            matched += 1
        if match.index < lower:
            classification = "boundary_shift"
            discrepancy_type = "non_monotonic_entry_opening"
            confidence = "medium"
        elif match.match_type == "exact":
            classification = None
            discrepancy_type = None
            confidence = None
        else:
            classification = "unresolved"
            discrepancy_type = "non_exact_entry_opening"
            confidence = "low"
        if discrepancy_type:
            page = _page_record_for_match(wchapter, match)
            records.append(
                {
                    "chapter": f"{chapter.number:02d}-{chapter.slug}",
                    "chapter_slug": chapter.slug,
                    "entry_id": entry.entry_id,
                    "ordinal": entry.ordinal,
                    "discrepancy_type": discrepancy_type,
                    "classification": classification,
                    "confidence": confidence,
                    "kanripo_location": {
                        "source": str(chapter.chapter_path.relative_to(REPO_ROOT)),
                        "source_normalized_line": entry.source_normalized_line,
                        "source_line": entry.source_line,
                        "page_marker": entry.page_marker,
                    },
                    "kanripo_reading": entry.opening_key,
                    "kanripo_reading_raw": entry.opening_text,
                    "wikisource_location": page,
                    "wikisource_reading": _unit_context(wchapter.comparison_units, match.index, 60, max(160, match.length + 80)),
                    "match_type": match.match_type,
                    "requires_visual_verification": True,
                    "recommended_action": "Review the exact character/glyph and boundary context; no automatic repair is made.",
                }
            )
        lower = max(lower, match.index + max(1, match.length))
    summary = {
        "kanripo_entry_count": len(chapter.entries),
        "wikisource_exact_opening_matches": matched,
        "wikisource_prefix_matches": prefix,
        "wikisource_suffix_matches": suffix,
        "wikisource_duplicate_opening_matches": duplicate,
        "unmatched_openings": unmatched,
    }
    return records, summary


def _chapter_discrepancy(
    chapter: KChapter,
    wchapter: WChapter,
    entry_summary: dict[str, Any],
) -> dict[str, Any] | None:
    k_text = "".join(unit.key for unit in chapter.comparison_units)
    w_text = wchapter.key_text
    matcher = difflib.SequenceMatcher(None, k_text, w_text, autojunk=False)
    ratio = matcher.ratio()
    length_delta = len(w_text) - len(k_text)
    threshold = max(60, int(min(len(k_text), len(w_text)) * 0.10))
    k_annotation_count = len(chapter.annotations)
    annotation_delta = wchapter.annotation_count - k_annotation_count
    annotation_difference = abs(annotation_delta) >= max(3, int(k_annotation_count * 0.20))
    if (
        abs(length_delta) <= threshold
        and ratio >= 0.90
        and entry_summary["unmatched_openings"] == 0
        and not annotation_difference
    ):
        return None
    largest = max(
        (opcode for opcode in matcher.get_opcodes() if opcode[0] != "equal"),
        key=lambda opcode: max(opcode[2] - opcode[1], opcode[4] - opcode[3]),
        default=None,
    )
    discrepancy_type = "major_length_difference"
    if largest is not None:
        tag, k_start, k_end, w_start, w_end = largest
        if tag == "delete" and k_end - k_start >= 8:
            discrepancy_type = "extra_kanripo_passage"
        elif tag == "insert" and w_end - w_start >= 8:
            discrepancy_type = "missing_kanripo_passage"
        elif tag == "replace" and max(k_end - k_start, w_end - w_start) <= 3:
            discrepancy_type = "probable_one_character_shift"
    if annotation_difference and abs(length_delta) <= threshold and ratio >= 0.90:
        discrepancy_type = "annotation_range_difference"
    w_pages = list(dict.fromkeys(unit.page_title for unit in wchapter.main_units if unit.page_title))
    w_urls = list(dict.fromkeys(unit.source_url for unit in wchapter.main_units if unit.source_url))
    if largest is not None:
        _tag, k_start, k_end, w_start, w_end = largest
        kanripo_context = _unit_context(
            chapter.comparison_units,
            k_start,
            before=120,
            after=max(220, k_end - k_start + 160),
        )
        wikisource_context = _unit_context(
            wchapter.comparison_units,
            w_start,
            before=120,
            after=max(220, w_end - w_start + 160),
        )
    else:
        kanripo_context = "".join(unit.raw for unit in chapter.comparison_units[:120])
        wikisource_context = "".join(unit.raw for unit in wchapter.comparison_units[:120])
    return {
        "chapter": f"{chapter.number:02d}-{chapter.slug}",
        "chapter_slug": chapter.slug,
        "canonical_heading": chapter.heading,
        "discrepancy_type": discrepancy_type,
        "classification": "structural_difference" if "length" in discrepancy_type else "unresolved",
        "confidence": "low" if ratio < 0.90 else "medium",
        "kanripo_entry_count": len(chapter.entries),
        "kanripo_main_characters": len(k_text),
        "wikisource_main_characters": len(w_text),
        "length_delta_wikisource_minus_kanripo": length_delta,
        "sequence_match_ratio": round(ratio, 6),
        "kanripo_parenthetical_blocks": k_annotation_count,
        "wikisource_contributing_page_annotation_blocks": wchapter.annotation_count,
        "annotation_count_delta_wikisource_minus_kanripo": annotation_delta,
        "kanripo_location": {
            "source": str(chapter.chapter_path.relative_to(REPO_ROOT)),
            "page_markers": list(chapter.page_markers),
        },
        "wikisource_location": {
            "page_start": w_pages[0] if w_pages else None,
            "page_end": w_pages[-1] if w_pages else None,
            "page_count": len(w_pages),
            "source_url_start": w_urls[0] if w_urls else None,
            "source_url_end": w_urls[-1] if w_urls else None,
        },
        "entry_summary": entry_summary,
        "kanripo_context": kanripo_context,
        "wikisource_context": wikisource_context,
        "requires_visual_verification": True,
        "recommended_action": "Use page-level visual witnesses to determine whether this is a missing/extra passage, a glyph/character variant, or a segmentation difference. No textual repair is performed.",
    }


def scan_corpus(kanripo: dict[int, KChapter], wikisource: dict[int, WChapter]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for number, slug, _heading in CHAPTERS:
        entry_records, entry_summary = _entry_scan_records(kanripo[number], wikisource[number])
        records.extend(entry_records)
        chapter_record = _chapter_discrepancy(kanripo[number], wikisource[number], entry_summary)
        if chapter_record is not None:
            records.append(chapter_record)
        summaries.append({"chapter": f"{number:02d}-{slug}", **entry_summary, "has_chapter_discrepancy": chapter_record is not None})
    aggregate = {
        "chapter_count": 36,
        "chapters_with_discrepancies": sum(item["has_chapter_discrepancy"] for item in summaries),
        "total_kanripo_entries": sum(item["kanripo_entry_count"] for item in summaries),
        "total_exact_opening_matches": sum(item["wikisource_exact_opening_matches"] for item in summaries),
        "total_prefix_matches": sum(item["wikisource_prefix_matches"] for item in summaries),
        "total_suffix_matches": sum(item["wikisource_suffix_matches"] for item in summaries),
        "total_unmatched_openings": sum(item["unmatched_openings"] for item in summaries),
        "summaries": summaries,
    }
    return records, aggregate


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _frontmatter(fields: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, (dict, list, tuple)):
            lines.append(f"{key}: {_json(value)}")
        elif value is None:
            lines.append(f"{key}: null")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{key}: {_json(str(value))}")
    lines.extend(["---", ""])
    return "\n".join(lines)


def write_derived_views(
    kanripo: dict[int, KChapter],
    wikisource_units: Sequence[WUnit],
    wikisource_pages: Sequence[WPage],
    wikisource: dict[int, WChapter],
) -> dict[str, Any]:
    # The files below are derived comparison views only.  No path under
    # sources/downloads is written by this function.
    for number, slug, heading in CHAPTERS:
        chapter = kanripo[number]
        lines = [
            _frontmatter(
                {
                    "schema": 1,
                    "stage": "multi-witness-comparison-view",
                    "witness": "shishuo-kanripo-wyg",
                    "chapter": slug,
                    "canonical_heading": heading,
                    "source_chapter": str(chapter.chapter_path.relative_to(REPO_ROOT)),
                    "source_manifest": str(chapter.manifest_path.relative_to(REPO_ROOT)),
                    "source_sha256": chapter.metadata["source_sha256"],
                    "normalization": [
                        "removed whitespace for the main alignment stream",
                        "removed Kanripo page/directive/editorial layout from the main stream",
                        "removed top-level parenthetical blocks from the main stream; exact blocks follow",
                        "preserved traditional characters, punctuation, and placeholder spellings",
                    ],
                }
            ),
            "## Main text (alignment view)",
            "",
            "".join(unit.raw for unit in chapter.main_units),
            "",
            "## Top-level parenthetical annotation blocks (source spelling)",
            "",
        ]
        lines.extend(chapter.annotations or ("No top-level parenthetical blocks.",))
        lines.extend(["", "## Kanripo page markers", ""])
        lines.extend(chapter.page_markers or ("No page markers.",))
        _write(OUTPUT_ROOT / "kanripo" / f"{slug}.md", "\n".join(lines) + "\n")

        wchapter = wikisource[number]
        wpages = sorted({unit.page_title for unit in wchapter.main_units})
        w_annotations = [
            annotation
            for page in wikisource_pages
            if page.record.get("page_title") in wpages
            for annotation in page.annotations
        ]
        lines = [
            _frontmatter(
                {
                    "schema": 1,
                    "stage": "multi-witness-comparison-view",
                    "witness": "shishuo-wikisource-sbck",
                    "chapter": slug,
                    "canonical_heading": heading,
                    "source_lock": str((WIKISOURCE_ROOT / "manifest.lock.json").relative_to(REPO_ROOT)),
                    "source_pages": wpages,
                    "normalization": [
                        "removed MediaWiki layout/noinclude markup",
                        "removed whitespace for the main alignment stream",
                        "removed 雙行註文 templates from main text; raw templates follow",
                        "kept SKchar/entity markers explicit; alignment key uses a private-use placeholder only",
                        "made no character-variant substitution or textual correction",
                    ],
                }
            ),
            "## Main text (alignment view)",
            "",
            wchapter.raw_text,
            "",
            "## Annotation templates (source spelling)",
            "",
        ]
        lines.extend(w_annotations or ("No annotation templates in the contributing pages.",))
        _write(OUTPUT_ROOT / "wikisource-sbck" / f"{slug}.md", "\n".join(lines) + "\n")

    ling_records: list[dict[str, Any]] = []
    lock_path = LING_ROOT / "manifest.lock.json"
    if lock_path.exists():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        for record in lock.get("records", []):
            volume = int(record["volume"])
            ocr_file = next((item for item in record.get("files", []) if item.get("kind") == "ocr"), None)
            if not ocr_file:
                continue
            source_path = REPO_ROOT / ocr_file["path"]
            text_value = source_path.read_text(encoding="utf-8", errors="replace")
            normalized = compact(text_value)
            output = OUTPUT_ROOT / "ling-1615" / f"volume-{volume:02d}-ocr.txt"
            _write(
                output,
                _frontmatter(
                    {
                        "schema": 1,
                        "stage": "multi-witness-comparison-view",
                        "witness": "shishuo-ling-1615",
                        "volume": volume,
                        "source_file": str(source_path.relative_to(REPO_ROOT)),
                        "source_sha256": ocr_file.get("sha256"),
                        "authority": "OCR is search/alignment convenience only; PDF/page image is authoritative",
                        "normalization": ["removed OCR whitespace/layout only", "preserved OCR characters exactly"],
                    }
                )
                + normalized
                + "\n",
            )
            ling_records.append({"volume": volume, "source": ocr_file, "derived": str(output.relative_to(REPO_ROOT))})

    siku_metadata = {
        "schema": 1,
        "witness_family": "shishuo-siku",
        "status": "external_not_scraped",
        "ctext_visual_url": "https://ctext.org/library.pl?if=gb&remap=gb&res=5115",
        "wikisource_url": "https://zh.wikisource.org/zh/世說新語_%28四庫全書本%29",
        "note": "No local text is asserted; external records remain visual/alignment references only.",
    }
    _write(OUTPUT_ROOT / "siku" / "external-reference.yaml", yaml.safe_dump(siku_metadata, allow_unicode=True, sort_keys=False))
    structural_text = REFERENCE_PATH.read_text(encoding="utf-8")
    structural_output = OUTPUT_ROOT / "structural-reference" / "shishuo.txt"
    _write(structural_output, compact(structural_text) + "\n")
    _write(
        OUTPUT_ROOT / "structural-reference" / "README.md",
        "\n".join(
            [
                "# Structural-reference comparison view",
                "",
                "This is a derived alignment copy of the local structural-reference witness.",
                "Whitespace is compacted for comparison only; characters and character variants are preserved.",
                "The witness remains low text authority and is never used to overwrite Kanripo text.",
                "",
                f"- source: `{REFERENCE_PATH.relative_to(REPO_ROOT)}`",
                f"- source SHA-256: `{sha256_file(REFERENCE_PATH)}`",
                f"- derived text: `{structural_output.relative_to(REPO_ROOT)}`",
                "",
            ]
        ),
    )
    manifest = {
        "schema": 1,
        "stage": "multi-witness-comparison-view",
        "policy": "derived, reversible, read-only comparison copies; no source replacement",
        "character_policy": "traditional characters and witness-specific variants are preserved; only whitespace/layout and explicit glyph markers receive alignment treatment",
        "witnesses": {
            "kanripo": "shishuo-kanripo-wyg",
            "wikisource": "shishuo-wikisource-sbck",
            "ling": "shishuo-ling-1615",
            "siku": "shishuo-siku (external only)",
            "structural_reference": "shishuo-local-reference-txt",
            "scholarly_reference": "shishuo-jianshu-yujiaxi (not used as text)",
        },
        "derived_files": {
            "kanripo_chapters": 36,
            "wikisource_chapters": sum(1 for chapter in wikisource.values() if chapter.global_start >= 0),
            "ling_ocr_volumes": ling_records,
            "siku": "siku/external-reference.yaml",
            "structural_reference": [
                "structural-reference/shishuo.txt",
                "structural-reference/README.md",
            ],
        },
    }
    _write(OUTPUT_ROOT / "comparison-manifest.yaml", yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False))
    _write(
        OUTPUT_ROOT / "README.md",
        """# Shishuo multi-witness comparison views

These files are deterministic derived alignment views. The raw Kanripo,
Wikisource, Ling, and local structural-reference witness files remain
unchanged. Whitespace and layout markup are removed only for alignment;
character variants are not modernized. Parenthetical/MediaWiki annotation
material is retained in the corresponding annotation section. OCR is
non-authoritative.

The comparison stage does not repair text or boundary manifests.
""",
    )
    return manifest


def _known_markdown(records: Sequence[dict[str, Any]]) -> str:
    lines = [
        "# Shishuo known-anomaly multi-witness comparison",
        "",
        "This report is a read-only comparison layer. It does not modify raw or downloaded witnesses, normalized chapters, entries, manifests, or prior audit reports. The Kanripo/SBCK witness remains primary. Wikisource is a same-edition machine reference; Ling OCR is search-only and its PDF/page image is authoritative; 四庫 is external and was not bulk-scraped; the local TXT is structural reference only.",
        "",
        "## Classification summary",
        "",
        "| classification | cases |",
        "|---|---:|",
    ]
    counts: dict[str, int] = {}
    for record in records:
        counts[record["classification"]] = counts.get(record["classification"], 0) + 1
    for key in sorted(counts):
        lines.append(f"| `{key}` | {counts[key]} |")
    lines.extend(["", "## Cases", ""])
    for record in records:
        lines.extend(
            [
                f"### {record['id']} — `{record['classification']}` ({record['confidence']} confidence)",
                "",
                f"- chapter: `{record['chapter']}` ({record['canonical_heading']})",
                f"- expected ordinal: `{record['expected_ordinal']}`",
                f"- recommended resolution: {record['recommended_resolution']}",
                f"- missing-text supplier, if any: `{record['missing_text_supplier'] or 'none; this is a boundary case'}`",
                "",
                "#### Kanripo/SBCK primary witness",
                "",
                f"- status: `{record['kanripo'].get('status')}`",
                f"- proposed/opening reading: `{record['kanripo'].get('opening_text')}`",
                f"- source location: `{record['kanripo'].get('source_chapter')}`; normalized line `{record['kanripo'].get('source_normalized_line')}`; page `{record['kanripo'].get('page_marker')}`",
                "",
                "```text",
                str(record["kanripo"].get("source_context") or record["kanripo"].get("main_reading") or "No surviving reading at the expected position."),
                "```",
                "",
                "#### Wikisource 四部叢刊 same-edition machine witness",
                "",
                f"- status: `{record['wikisource_sbck'].get('status')}`; match type: `{record['wikisource_sbck'].get('match_type', 'n/a')}`",
                f"- page: `{record['wikisource_sbck'].get('page', {}).get('page_title', 'not located')}`",
                f"- page source: `{record['wikisource_sbck'].get('page', {}).get('source_url', '')}`",
                "",
                "```text",
                str(record["wikisource_sbck"].get("reading") or "No local Wikisource reading located."),
                "```",
                "",
            ]
        )
        if record["wikisource_sbck"].get("boundary_observation"):
            lines.extend([f"- boundary observation: {record['wikisource_sbck']['boundary_observation']}", ""])
        lines.extend(
            [
                "#### Ling 1615 independent OCR + visual witness",
                "",
                f"- volume: `{record['ling_1615']['volume']}`",
                f"- OCR result: {record['ling_1615']['ocr_search']}",
                f"- PDF status: `{record['ling_1615']['pdf_status']}`",
                f"- reading asserted from Ling: `{record['ling_1615']['reading'] or 'none'}`",
                f"- note: {record['ling_1615']['note']}",
                "",
                "#### 四庫本 witness family",
                "",
                f"- status: `{record['siku']['status']}`",
                f"- CText visual record: `{record['siku']['ctext_visual_url']}`",
                f"- reading asserted: `{record['siku']['reading'] or 'none'}`",
                "",
                "#### Structural-reference TXT",
                "",
                f"- status: `{record['structural_reference']['status']}`; authority: `{record['structural_reference']['authority']}`",
                f"- alignment reading: `{record['structural_reference']['opening_reading']}`",
                "",
                "```text",
                str(record["structural_reference"].get("main_reading") or "No structural-reference entry located."),
                "```",
                "",
                "The structural-reference reading is diagnostic only and is not used to overwrite Kanripo text.",
                "",
            ]
        )
    lines.extend(
        [
            "## Interpretation limits",
            "",
            "The six guide-gap cases are classified as `kanripo_digitization_gap` because the same-edition Wikisource page witness contains the expected passages while the current Kanripo witness does not. This identifies a likely digitization/source-file omission, not permission to patch the primary text. The three known boundary cases are `boundary_shift`; no textual source repair has been made. Ling and 四庫 readings remain unasserted where local/allowed machine evidence was insufficient.",
            "",
            "No entity extraction, relationship extraction, translation, summary, or historical interpretation was performed.",
            "",
        ]
    )
    return "\n".join(lines)


def _corpus_markdown(records: Sequence[dict[str, Any]], aggregate: dict[str, Any]) -> str:
    lines = [
        "# Shishuo Kanripo ↔ Wikisource corpus discrepancy scan",
        "",
        "This is a deterministic machine-level scan of the 36 normalized chapter views and proposed entry openings. It compares Kanripo/SBCK to the Wikisource 四部叢刊 page witness after removing whitespace/layout and treating explicit unrendered glyph markers as alignment tokens. It does not prove semantic boundary correctness and it performs no repair.",
        "",
        "## Aggregate",
        "",
        f"- chapters scanned: {aggregate['chapter_count']}",
        f"- proposed Kanripo entries: {aggregate['total_kanripo_entries']}",
        f"- exact opening matches: {aggregate['total_exact_opening_matches']}",
        f"- prefix opening matches (character/markup difference remains): {aggregate['total_prefix_matches']}",
        f"- suffix opening matches (possible shifted/partial opening): {aggregate['total_suffix_matches']}",
        f"- unmatched openings: {aggregate['total_unmatched_openings']}",
        f"- chapters with aggregate discrepancies: {aggregate['chapters_with_discrepancies']}",
        "",
        "## Per-chapter summary",
        "",
        "| chapter | Kanripo entries | exact | prefix | suffix | unmatched | aggregate discrepancy |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for summary in aggregate["summaries"]:
        lines.append(
            f"| `{summary['chapter']}` | {summary['kanripo_entry_count']} | {summary['wikisource_exact_opening_matches']} | {summary['wikisource_prefix_matches']} | {summary['wikisource_suffix_matches']} | {summary['unmatched_openings']} | {'yes' if summary['has_chapter_discrepancy'] else 'no'} |"
        )
    lines.extend(["", "## Discrepancy records", ""])
    if not records:
        lines.append("No discrepancy records met the scan thresholds.")
    for record in records:
        lines.extend(
            [
                f"### {record['chapter']}" + (f" — {record['entry_id']}" if record.get("entry_id") else "") + f" — `{record['discrepancy_type']}`",
                "",
                f"- classification: `{record['classification']}`",
                f"- confidence: `{record['confidence']}`",
                f"- requires visual verification: `{record.get('requires_visual_verification', True)}`",
                f"- recommended action: {record['recommended_action']}",
            ]
        )
        if record.get("entry_id"):
            lines.extend(
                [
                    f"- Kanripo opening key: `{record.get('kanripo_reading')}`",
                    f"- Kanripo opening text (source spelling): `{record.get('kanripo_reading_raw')}`",
                    f"- Kanripo location: `{record.get('kanripo_location', {}).get('source')}`; normalized line `{record.get('kanripo_location', {}).get('source_normalized_line')}`; page `{record.get('kanripo_location', {}).get('page_marker')}`",
                    f"- Wikisource match type: `{record.get('match_type', 'none')}`",
                    f"- Wikisource page: `{record.get('wikisource_location', {}).get('page_title', 'not located') if record.get('wikisource_location') else 'not located'}`",
                    "",
                    "```text",
                    str(record.get("wikisource_reading") or "No aligned Wikisource reading."),
                    "```",
                ]
            )
        else:
            lines.extend(
                [
                    f"- Kanripo main characters: {record['kanripo_main_characters']}",
                    f"- Wikisource main characters: {record['wikisource_main_characters']}",
                    f"- length delta (Wikisource − Kanripo): {record['length_delta_wikisource_minus_kanripo']}",
                    f"- sequence ratio: {record['sequence_match_ratio']}",
                    f"- Kanripo location: `{record['kanripo_location']['source']}`; page markers `{record['kanripo_location']['page_markers']}`",
                    f"- Wikisource page range: `{record['wikisource_location']['page_start']}` through `{record['wikisource_location']['page_end']}` ({record['wikisource_location']['page_count']} pages)",
                    f"- Wikisource source URL range: `{record['wikisource_location']['source_url_start']}` through `{record['wikisource_location']['source_url_end']}`",
                    "",
                    "```text",
                    str(record.get("kanripo_context") or ""),
                    "```",
                    "",
                    "```text",
                    str(record.get("wikisource_context") or ""),
                    "```",
                ]
            )
        lines.extend(["", "---", ""])
    lines.extend(
        [
            "## Mechanical-validation limitation",
            "",
            "Exact/prefix/suffix matches and sequence ratios are evidence for review, not semantic proof. Page markers, annotation templates, glyph placeholders, one-character shifts, and entry-boundary differences can all produce a non-exact alignment. No corpus source or manifest was changed.",
            "",
        ]
    )
    return "\n".join(lines)


def run() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    kanripo = {number: load_kanripo_chapter(number, slug, heading) for number, slug, heading in CHAPTERS}
    w_units, w_pages, _lock = load_wikisource()
    page_annotation_counts = {
        str(page.record.get("page_title", "")): len(page.annotations) for page in w_pages
    }
    wikisource = make_wikisource_chapters(w_units, page_annotation_counts)
    references = _reference_entries()
    write_derived_views(kanripo, w_units, w_pages, wikisource)
    known = build_known_anomaly_records(kanripo, wikisource, references)
    discrepancies, aggregate = scan_corpus(kanripo, wikisource)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    _write(REPORT_ROOT / "known-anomalies.yaml", yaml.safe_dump({"schema": 1, "records": known}, allow_unicode=True, sort_keys=False))
    _write(REPORT_ROOT / "known-anomalies.md", _known_markdown(known))
    _write(REPORT_ROOT / "corpus-discrepancies.yaml", yaml.safe_dump({"schema": 1, "scan": aggregate, "records": discrepancies}, allow_unicode=True, sort_keys=False))
    _write(REPORT_ROOT / "corpus-discrepancies.md", _corpus_markdown(discrepancies, aggregate))
    return known, discrepancies, aggregate


def main(argv: Sequence[str] | None = None) -> int:
    try:
        known, discrepancies, aggregate = run()
    except (OSError, UnicodeError, ValueError, KeyError) as error:
        print(f"compare_shishuo_witnesses: {error}", file=sys.stderr)
        return 2
    print(f"known anomalies: {len(known)}")
    print(f"corpus discrepancy records: {len(discrepancies)}")
    print(f"unmatched openings: {aggregate['total_unmatched_openings']}")
    print(f"outputs: {OUTPUT_ROOT} and {REPORT_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
