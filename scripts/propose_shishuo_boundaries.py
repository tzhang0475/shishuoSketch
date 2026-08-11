#!/usr/bin/env python3
"""Propose reviewed-style Shishuo entry boundaries for chapters 01--35.

This is a proposal stage only.  It never edits a normalized chapter and it
never writes entry Markdown.  The exact anchors in the generated manifests
are sliced from the traditional normalized chapter body.

The local ``content/shishuo.txt`` file is used only as a structural guide for
the order and approximate count of entries.  Its text is not copied to any
output.  ICU's ``uconv`` command is used only to compare that guide with the
traditional source; all emitted text and provenance come from
``content/processed/shishuo/chapters``.  The command is required so that a
missing conversion tool cannot silently change the proposal result.

Some Kanripo main-text sections do not contain every entry present in the
structural guide.  Those guide candidates are omitted from manifests and are
reported explicitly.  If only a later continuation survives in the source,
the continuation is emitted as a low-confidence, human-reviewable anchor.
"""

from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass, field
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Iterable, Sequence


DEFAULT_CHAPTER_DIR = Path("content/processed/shishuo/chapters")
DEFAULT_REFERENCE = Path("content/shishuo.txt")
DEFAULT_OUTPUT_DIR = Path("content/curated/shishuo/boundaries")
DEFAULT_REPORT = DEFAULT_OUTPUT_DIR / "boundary-review-report.md"

HAN_RE = re.compile(r"[\u3400-\u9fff\U00020000-\U0002ffff]")
PAGE_COMMENT_RE = re.compile(
    r"^<!-- kanripo-page source-line=(?P<source_line>\d+): "
    r"(?P<marker><pb:[^>]+>) -->$"
)
FILE_BOUNDARY_RE = re.compile(
    r"^<!-- segmentation-file-boundary: normalized_filename=(?P<filename>[^;]+); "
    r"FILE=(?P<file>.*?) -->$"
)
DIRECTIVE_RE = re.compile(r"^<!-- kanripo-directive source-line=\d+: .+ -->$")

CHAPTER_HEADINGS: tuple[str, ...] = (
    "德行第一",
    "言語第二",
    "政事第三",
    "文學第四",
    "方正第五",
    "雅量第六",
    "識鑒第七",
    "賞譽第八",
    "品藻第九",
    "規箴第十",
    "捷悟第十一",
    "夙惠第十二",
    "豪爽第十三",
    "容止第十四",
    "自新第十五",
    "企羡第十六",
    "傷逝第十七",
    "棲逸第十八",
    "賢媛第十九",
    "術解第二十",
    "巧蓺第二十一",
    "寵禮第二十二",
    "任誕第二十三",
    "簡傲第二十四",
    "排調第二十五",
    "輕詆第二十六",
    "假譎第二十七",
    "黜免第二十八",
    "儉嗇第二十九",
    "汰侈第三十",
    "忿狷第三十一",
    "讒險第三十二",
    "尤悔第三十三",
    "紕漏第三十四",
    "惑溺第三十五",
    "仇隟第三十六",
)

REFERENCE_HEADINGS: tuple[str, ...] = (
    "德行第一",
    "言语第二",
    "政事第三",
    "文学第四",
    "方正第五",
    "雅量第六",
    "识鉴第七",
    "赏誉第八",
    "品藻第九",
    "规箴第十",
    "捷悟第十一",
    "夙惠第十二",
    "豪爽第十三",
    "容止第十四",
    "自新第十五",
    "企羡第十六",
    "伤逝第十七",
    "栖逸第十八",
    "贤媛第十九",
    "术解第二十",
    "巧艺第二十一",
    "宠礼第二十二",
    "任诞第二十三",
    "简傲第二十四",
    "排调第二十五",
    "轻诋第二十六",
    "假谲第二十七",
    "黜免第二十八",
    "俭啬第二十九",
    "汰侈第三十",
    "忿狷第三十一",
    "谗险第三十二",
    "尤悔第三十三",
    "纰漏第三十四",
    "惑溺第三十五",
    "仇隙第三十六",
)

CHAPTER_SLUGS: tuple[str, ...] = (
    "dexing",
    "yanyu",
    "zhengshi",
    "wenxue",
    "fangzheng",
    "yaliang",
    "shijian",
    "shangyu",
    "pinzao",
    "guizhen",
    "jiewu",
    "suhui",
    "haoshuang",
    "rongzhi",
    "zixin",
    "qixian",
    "shangshi",
    "qiyi",
    "xianyuan",
    "shujie",
    "qiaoyi",
    "chongli",
    "rendan",
    "jianao",
    "paidiao",
    "qingdi",
    "jiajue",
    "chumian",
    "jianshe",
    "taichi",
    "fenjuan",
    "chanxian",
    "youhui",
    "pilou",
    "huoni",
    "chouxi",
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _is_han(character: str) -> bool:
    return bool(HAN_RE.fullmatch(character))


def _han(text: str) -> str:
    return "".join(HAN_RE.findall(text))


def _split_frontmatter(text: str) -> tuple[str, str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("chapter source has no YAML front matter")
    closing = next(
        (index for index in range(1, len(lines)) if lines[index].strip() == "---"),
        None,
    )
    if closing is None:
        raise ValueError("chapter source has unterminated YAML front matter")
    return "".join(lines[: closing + 1]), "".join(lines[closing + 1 :])


def _quoted(frontmatter: str, field: str) -> str:
    match = re.search(
        rf"^{re.escape(field)}: (?P<value>\".*\")$", frontmatter, re.MULTILINE
    )
    if match is None:
        raise ValueError(f"chapter front matter has no {field}")
    return str(json.loads(match.group("value")))


def _integer(frontmatter: str, field: str) -> int:
    match = re.search(rf"^{re.escape(field)}: (?P<value>\d+)$", frontmatter, re.MULTILINE)
    if match is None:
        raise ValueError(f"chapter front matter has no integer {field}")
    return int(match.group("value"))


def _list_field(frontmatter: str, field: str) -> tuple[str, ...]:
    match = re.search(
        rf"^{re.escape(field)}:\n(?P<items>(?:  - \".*\"\n?)+)",
        frontmatter,
        re.MULTILINE,
    )
    if match is None:
        return ()
    return tuple(
        str(json.loads(item))
        for item in re.findall(r"^  - (\".*\")$", match.group("items"), re.MULTILINE)
    )


@dataclass(frozen=True)
class SourceSegment:
    normalized_filename: str
    source_path: str
    source_sha256: str
    file_section: str
    heading: str
    start_normalized_line: int
    start_source_line: int
    start_page_marker: str


@dataclass(frozen=True)
class SourceChar:
    character: str
    body_offset: int
    normalized_line: int
    source_line: int
    page_marker: str
    normalized_filename: str
    file_section: str


@dataclass(frozen=True)
class SourceChapter:
    path: Path
    frontmatter: str
    body: str
    chapter_number: int
    heading: str
    source_segments: tuple[SourceSegment, ...]
    title: str
    kanripo_id: str
    baseedition: str
    witness: str
    source_normalized_files: tuple[str, ...]
    source_paths: tuple[str, ...]
    source_sha256: tuple[str, ...]
    main_text: str
    main_chars: tuple[SourceChar, ...]


@dataclass(frozen=True)
class ReferenceEntry:
    ordinal: int
    main_text: str
    opening_text: str


@dataclass(frozen=True)
class ReferenceChapter:
    chapter_number: int
    heading: str
    entries: tuple[ReferenceEntry, ...]


@dataclass(frozen=True)
class MatchScore:
    ratio: float
    common_prefix: int
    exact_count: int
    position: int


@dataclass(frozen=True)
class Candidate:
    reference_ordinal: int
    position: int
    score: MatchScore
    kind: str
    note: str = ""


@dataclass(frozen=True)
class BoundaryProposal:
    entry_id: str
    ordinal: int
    opening_text: str
    source_normalized_line: int
    source_line: int
    source_page_marker: str
    normalized_filename: str
    file_section: str
    confidence: str
    note: str = ""
    source_main_offset: int = field(default=-1, repr=False)
    body_offset: int = field(default=-1, repr=False)
    anchor_count: int = field(default=0, repr=False)


@dataclass(frozen=True)
class GuideException:
    reference_ordinal: int
    reason: str
    context: str


@dataclass(frozen=True)
class ProposalValidation:
    anchor_errors: tuple[str, ...]
    duplicate_anchors: tuple[str, ...]
    ordinal_errors: tuple[str, ...]
    empty_entries: tuple[str, ...]
    page_marker_errors: tuple[str, ...]
    parenthesis_balanced: bool

    @property
    def passed(self) -> bool:
        return not (
            self.anchor_errors
            or self.duplicate_anchors
            or self.ordinal_errors
            or self.empty_entries
            or self.page_marker_errors
            or not self.parenthesis_balanced
        )


@dataclass(frozen=True)
class ChapterProposal:
    chapter: SourceChapter
    chapter_id: str
    slug: str
    reference_count: int
    boundaries: tuple[BoundaryProposal, ...]
    guide_exceptions: tuple[GuideException, ...]
    validation: ProposalValidation
    alignment_ratio: float


def _parse_source_segments(frontmatter: str) -> tuple[SourceSegment, ...]:
    pattern = re.compile(
        r"  - normalized_filename: (?P<filename>\".*\")\n"
        r"    source_path: (?P<path>\".*\")\n"
        r"    source_sha256: (?P<sha>\".*\")\n"
        r"    FILE: (?P<file>\".*\")\n"
        r"    heading: (?P<heading>\".*\")\n"
        r"    start:\n"
        r"      normalized_line: (?P<nline>\d+)\n"
        r"      source_line: (?P<sline>\d+)\n"
        r"      page_marker: (?P<marker>\".*\")",
        re.MULTILINE,
    )
    segments: list[SourceSegment] = []
    for match in pattern.finditer(frontmatter):
        segments.append(
            SourceSegment(
                normalized_filename=str(json.loads(match.group("filename"))),
                source_path=str(json.loads(match.group("path"))),
                source_sha256=str(json.loads(match.group("sha"))),
                file_section=str(json.loads(match.group("file"))),
                heading=str(json.loads(match.group("heading"))),
                start_normalized_line=int(match.group("nline")),
                start_source_line=int(match.group("sline")),
                start_page_marker=str(json.loads(match.group("marker"))),
            )
        )
    if not segments:
        raise ValueError("chapter front matter has no source_segments")
    return tuple(segments)


def _is_heading_line(text: str, heading: str) -> bool:
    candidate = text.strip()
    candidate = candidate.replace("（", "(").replace("）", ")")
    base = heading.replace("（", "(").replace("）", ")")
    return candidate == base or candidate in {f"{base}(上)", f"{base}(下)"}


def _is_editorial_title_line(text: str) -> bool:
    candidate = text.strip()
    return bool(
        candidate
        and (candidate.startswith("世說新語") or candidate.startswith("世説新語"))
        and "第" not in candidate
    )


def load_source_chapter(path: Path) -> SourceChapter:
    raw = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(raw)
    segments = _parse_source_segments(frontmatter)
    chapter_number = _integer(frontmatter, "chapter_number")
    heading = _quoted(frontmatter, "canonical_heading")
    source_files = _list_field(frontmatter, "source_normalized_files")
    source_paths = _list_field(frontmatter, "source_paths")
    source_hashes = _list_field(frontmatter, "source_sha256")

    body_lines = body.splitlines(keepends=True)
    main_chars: list[SourceChar] = []
    body_offset = 0
    segment_index = 0
    segment_line_index = 0
    current_source_line = segments[0].start_source_line
    current_page_marker = segments[0].start_page_marker
    parenthesis_depth = 0

    for raw_line in body_lines:
        line = raw_line.rstrip("\r\n")
        page_match = PAGE_COMMENT_RE.fullmatch(line)
        boundary_match = FILE_BOUNDARY_RE.fullmatch(line)
        is_structural = (
            _is_heading_line(line, heading)
            or _is_editorial_title_line(line)
            or not line.strip()
        )

        if page_match is not None:
            current_source_line = int(page_match.group("source_line"))
            current_page_marker = page_match.group("marker")
        elif not boundary_match:
            current_source_line_for_line = current_source_line
            if not is_structural and not DIRECTIVE_RE.fullmatch(line):
                for local_offset, character in enumerate(line):
                    if character == "(":
                        parenthesis_depth += 1
                        continue
                    if character == ")":
                        if parenthesis_depth:
                            parenthesis_depth -= 1
                        continue
                    if parenthesis_depth == 0 and _is_han(character):
                        main_chars.append(
                            SourceChar(
                                character=character,
                                body_offset=body_offset + local_offset,
                                normalized_line=(
                                    segments[segment_index].start_normalized_line
                                    + segment_line_index
                                ),
                                source_line=current_source_line_for_line,
                                page_marker=current_page_marker,
                                normalized_filename=segments[
                                    segment_index
                                ].normalized_filename,
                                file_section=segments[segment_index].file_section,
                            )
                        )
            current_source_line += 1

        if boundary_match is not None:
            filename = boundary_match.group("filename")
            next_index = next(
                (
                    index
                    for index, segment in enumerate(segments)
                    if segment.normalized_filename == filename
                ),
                None,
            )
            if next_index is None:
                raise ValueError(
                    f"file boundary names an unknown normalized file: {filename}"
                )
            segment_index = next_index
            segment_line_index = 0
            current_source_line = segments[segment_index].start_source_line
            current_page_marker = segments[segment_index].start_page_marker
        else:
            segment_line_index += 1
        body_offset += len(raw_line)

    if parenthesis_depth != 0:
        # Keep loading deterministic; validation reports the imbalance.
        pass

    return SourceChapter(
        path=path,
        frontmatter=frontmatter,
        body=body,
        chapter_number=chapter_number,
        heading=heading,
        source_segments=segments,
        title=_quoted(frontmatter, "kanripo_title"),
        kanripo_id=_quoted(frontmatter, "kanripo_id"),
        baseedition=_quoted(frontmatter, "kanripo_baseedition"),
        witness=_quoted(frontmatter, "kanripo_witness"),
        source_normalized_files=source_files,
        source_paths=source_paths,
        source_sha256=source_hashes,
        main_text="".join(item.character for item in main_chars),
        main_chars=tuple(main_chars),
    )


def _reference_heading_positions(lines: Sequence[str], heading: str) -> list[int]:
    positions = [index for index, line in enumerate(lines) if heading in line and index > 180]
    if not positions and heading == "夙惠第十二":
        positions = [
            index
            for index, line in enumerate(lines)
            if "夙惠[1]第十二" in line and index > 180
        ]
    return positions


def _logical_reference_lines(
    lines: Sequence[str], start: int, end: int
) -> list[tuple[int, str]]:
    """Return reference rows, splitting a marker concatenated to note text.

    The checked-in structural guide is useful for locating likely entries, but
    it contains one known formatting defect in 賞譽第八: entry 100 follows the
    closing quote of a preceding note on the same physical line.  Keep the
    physical line number for diagnostics while making the entry marker a
    logical row.  The expected ordinal guard prevents note references such as
    ``(1)`` from being mistaken for entry markers.
    """
    start_pattern = re.compile(
        r"^(\d+)(?:　|(?=[\u3400-\u9fff\U00020000-\U0002ffff]))"
    )
    embedded_pattern = re.compile(
        r"(?<!\d)(\d+)(?=[\u3400-\u9fff\U00020000-\U0002ffff])"
    )
    logical: list[tuple[int, str]] = []
    expected_ordinal = 1
    for line_number in range(start + 1, end):
        line = lines[line_number]
        start_match = start_pattern.match(line)
        if start_match is not None:
            logical.append((line_number, line))
            expected_ordinal = int(start_match.group(1)) + 1
            continue

        embedded = embedded_pattern.search(line)
        if embedded is not None and int(embedded.group(1)) == expected_ordinal:
            prefix = line[: embedded.start()]
            marker_and_text = line[embedded.start() :]
            if prefix:
                logical.append((line_number, prefix))
            logical.append((line_number, marker_and_text))
            expected_ordinal += 1
        else:
            logical.append((line_number, line))
    return logical


def _reference_entry_lines(
    lines: Sequence[tuple[int, str]],
) -> list[tuple[int, int, str]]:
    entries: list[tuple[int, int, str]] = []
    # A few reference rows omit the ideographic space after the ordinal.  The
    # Han look-ahead keeps those rows while excluding ordinary note text.
    pattern = re.compile(r"^(\d+)(?:　|(?=[\u3400-\u9fff\U00020000-\U0002ffff]))(.*)$")
    for logical_index, (_physical_line_number, line) in enumerate(lines):
        match = pattern.match(line)
        if match is not None:
            entries.append((logical_index, int(match.group(1)), match.group(2)))
    return entries


def _convert_reference(text: str) -> str:
    executable = shutil.which("uconv")
    if executable is None:
        raise RuntimeError(
            "ICU uconv is required for deterministic structural-reference "
            "alignment (install ICU tools and ensure uconv is on PATH)"
        )
    result = subprocess.run(
        [executable, "-x", "Simplified-Traditional"],
        input=text,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout


def load_reference_chapter(path: Path, chapter_number: int) -> ReferenceChapter:
    lines = path.read_text(encoding="utf-8").splitlines()
    heading = REFERENCE_HEADINGS[chapter_number - 1]
    starts = _reference_heading_positions(lines, heading)
    if not starts:
        raise ValueError(f"reference has no full-text heading for chapter {chapter_number}")
    start = starts[0]

    next_heading = REFERENCE_HEADINGS[chapter_number] if chapter_number < 36 else None
    ends = (
        _reference_heading_positions(lines, next_heading)
        if next_heading is not None
        else []
    )
    if not ends and chapter_number + 1 == 12:
        ends = [
            index
            for index, line in enumerate(lines)
            if "夙惠[1]第十二" in line and index > start
        ]
    end = next((index for index in ends if index > start), len(lines))
    logical_lines = _logical_reference_lines(lines, start, end)
    entry_lines = _reference_entry_lines(logical_lines)
    entries: list[ReferenceEntry] = []
    for index, (logical_index, ordinal, first_line) in enumerate(entry_lines):
        stop = (
            entry_lines[index + 1][0]
            if index + 1 < len(entry_lines)
            else len(logical_lines)
        )
        main_lines = [first_line]
        for _physical_line_number, candidate_line in logical_lines[logical_index + 1 : stop]:
            if re.match(r"^\(\d+\)", candidate_line):
                break
            main_lines.append(candidate_line)
        without_note_refs = re.sub(r"\(\d+\)", "", "".join(main_lines))
        converted = _han(_convert_reference(without_note_refs))
        opening = _han(_convert_reference(re.sub(r"\(\d+\)", "", first_line)))
        entries.append(
            ReferenceEntry(ordinal=ordinal, main_text=converted, opening_text=opening)
        )
    return ReferenceChapter(
        chapter_number=chapter_number,
        heading=heading,
        entries=tuple(entries),
    )


def _alignment_map(source: str, reference: str) -> tuple[list[int], float]:
    matcher = difflib.SequenceMatcher(None, source, reference, autojunk=False)
    positions: list[int | None] = [None] * len(reference)
    for tag, source_start, source_end, ref_start, ref_end in matcher.get_opcodes():
        if tag == "equal":
            for delta in range(ref_end - ref_start):
                positions[ref_start + delta] = source_start + delta
        elif tag == "replace":
            for delta in range(ref_end - ref_start):
                denominator = max(1, ref_end - ref_start - 1)
                numerator = delta * max(0, source_end - source_start - 1)
                positions[ref_start + delta] = source_start + round(numerator / denominator)

    fallback_scale = len(source) / max(1, len(reference))
    result: list[int] = []
    for index, position in enumerate(positions):
        result.append(
            position
            if position is not None
            else min(len(source), round(index * fallback_scale))
        )
    return result, matcher.ratio()


def _score_at(source: str, opening: str, position: int) -> MatchScore:
    if not opening:
        return MatchScore(0.0, 0, 0, position)
    size = min(36, len(opening))
    source_slice = source[position : position + size]
    ratio = difflib.SequenceMatcher(
        None, source_slice, opening[:size], autojunk=False
    ).ratio()
    common_prefix = 0
    for source_character, reference_character in zip(source_slice, opening[:size]):
        if source_character != reference_character:
            break
        common_prefix += 1
    exact_count = sum(
        source_character == reference_character
        for source_character, reference_character in zip(source_slice, opening[:size])
    )
    return MatchScore(ratio, common_prefix, exact_count, position)


def _best_opening_score(
    source: str,
    opening: str,
    approximate: int,
    lower_bound: int,
    upper_bound: int | None = None,
) -> MatchScore:
    if not source or not opening:
        return MatchScore(0.0, 0, 0, max(0, lower_bound))
    upper = len(source) if upper_bound is None else min(len(source), upper_bound)
    low = max(lower_bound, approximate - 70)
    high = min(upper, approximate + 71)
    if low >= high:
        low = max(lower_bound, min(len(source) - 1, approximate))
        high = min(len(source), low + 1)
    scores = [_score_at(source, opening, position) for position in range(low, high)]
    return max(
        scores,
        key=lambda score: (
            score.ratio,
            score.common_prefix,
            score.exact_count,
            -abs(score.position - approximate),
        ),
    )


def _best_common_block(
    reference_text: str,
    source: str,
    approximate: int,
    lower_bound: int,
    upper_bound: int | None = None,
) -> tuple[int, int]:
    upper = len(source) if upper_bound is None else min(len(source), upper_bound)
    low = max(lower_bound, approximate - 110)
    high = min(upper, approximate + 180)
    if low >= high:
        return lower_bound, 0
    matcher = difflib.SequenceMatcher(
        None, reference_text, source[low:high], autojunk=False
    )
    block = max(matcher.get_matching_blocks(), key=lambda item: item.size, default=None)
    if block is None:
        return lower_bound, 0
    return low + block.b, block.size


def _candidate_kind(score: MatchScore, common_size: int) -> str:
    if score.ratio >= 0.50 or score.common_prefix >= 4 or score.exact_count >= 6:
        return "opening"
    if common_size >= 18:
        return "partial"
    return "absent"


def _context(body: str, offset: int, width: int = 90) -> str:
    start = max(0, offset - width // 2)
    end = min(len(body), offset + width)
    return body[start:end].replace("\n", "↵")


def _raw_anchor(
    chapter: SourceChapter, main_offset: int
) -> tuple[str, int, bool, str]:
    start = chapter.main_chars[main_offset].body_offset
    targets = (12, 18, 24, 32, 48, 72, 108)
    selected = chapter.body[start : start + 1]
    unique = False
    for target in targets:
        index = start
        depth = 0
        count = 0
        while index < len(chapter.body):
            if chapter.body.startswith("<!--", index):
                break
            character = chapter.body[index]
            if character == "(":
                depth += 1
            elif character == ")" and depth:
                depth -= 1
            elif depth == 0 and _is_han(character):
                count += 1
            index += 1
            if count >= target:
                break
        candidate = chapter.body[start:index]
        if candidate:
            selected = candidate
        if selected and chapter.body.count(selected) == 1:
            unique = True
            break
    first_line_end = len(chapter.body)
    for boundary in ("\n", "\r", "<!--"):
        candidate = chapter.body.find(boundary, start)
        if candidate >= 0:
            first_line_end = min(first_line_end, candidate)
    first_line_han_count = len(_han(chapter.body[start:first_line_end]))
    if first_line_han_count < 4:
        unique = False
        return (
            selected,
            start,
            unique,
            "The candidate begins with fewer than four source characters before the next physical line break; the line break is not treated as a boundary, but the candidate start requires manual review.",
        )
    return selected, start, unique, ""


def _parentheses_balanced(text: str) -> bool:
    depth = 0
    for character in text:
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _validate(
    chapter: SourceChapter, boundaries: Sequence[BoundaryProposal]
) -> ProposalValidation:
    anchor_errors: list[str] = []
    duplicate_anchors: list[str] = []
    ordinal_errors: list[str] = []
    empty_entries: list[str] = []
    page_marker_errors: list[str] = []

    expected_ordinals = list(range(1, len(boundaries) + 1))
    actual_ordinals = [boundary.ordinal for boundary in boundaries]
    if actual_ordinals != expected_ordinals:
        ordinal_errors.append(
            f"expected continuous ordinals {expected_ordinals[:3]}...; got {actual_ordinals[:3]}..."
        )

    segment_markers = {
        segment.start_page_marker for segment in chapter.source_segments
    }
    anchor_ids: dict[str, list[str]] = {}
    previous_position = -1
    for boundary in boundaries:
        anchor_ids.setdefault(boundary.opening_text, []).append(boundary.entry_id)
        count = chapter.body.count(boundary.opening_text)
        if count != 1:
            message = f"{boundary.entry_id}: anchor occurs {count} times"
            anchor_errors.append(message)
            if count > 1:
                duplicate_anchors.append(message)
        if boundary.body_offset <= previous_position:
            empty_entries.append(f"{boundary.entry_id}: non-increasing source position")
        previous_position = boundary.body_offset
        if not boundary.source_page_marker or (
            boundary.source_page_marker not in chapter.body
            and boundary.source_page_marker not in segment_markers
        ):
            page_marker_errors.append(f"{boundary.entry_id}: page marker is not traceable")

    for anchor, entry_ids in anchor_ids.items():
        if len(entry_ids) > 1:
            duplicate_anchors.append(
                f"entries {', '.join(entry_ids)} share the same opening anchor "
                f"{anchor!r}"
            )

    return ProposalValidation(
        anchor_errors=tuple(anchor_errors),
        duplicate_anchors=tuple(duplicate_anchors),
        ordinal_errors=tuple(ordinal_errors),
        empty_entries=tuple(empty_entries),
        page_marker_errors=tuple(page_marker_errors),
        parenthesis_balanced=_parentheses_balanced(chapter.body),
    )


def _resolve_candidates(
    chapter: SourceChapter,
    reference: ReferenceChapter,
) -> tuple[list[Candidate], list[GuideException], float]:
    source = chapter.main_text
    active = list(reference.entries)
    exceptions: list[GuideException] = []
    alignment_ratio = 0.0

    for _iteration in range(8):
        reference_text = "".join(entry.main_text for entry in active)
        positions, alignment_ratio = _alignment_map(source, reference_text)
        candidates: list[Candidate] = []
        reference_offset = 0
        previous_position = -1
        remove: list[ReferenceEntry] = []

        for index, entry in enumerate(active):
            approximate = positions[min(reference_offset, len(positions) - 1)] if positions else 0
            next_reference_offset = reference_offset + len(entry.main_text)
            next_approximate = (
                positions[min(next_reference_offset, len(positions) - 1)]
                if positions
                else len(source)
            )
            score = _best_opening_score(
                source,
                entry.opening_text,
                approximate,
                previous_position + 1,
                next_approximate + 75,
            )
            partial_position, common_size = _best_common_block(
                entry.main_text,
                source,
                approximate,
                previous_position + 1,
                next_approximate + 120,
            )
            kind = _candidate_kind(score, common_size)

            if kind == "absent":
                remove.append(entry)
                exceptions.append(
                    GuideException(
                        reference_ordinal=entry.ordinal,
                        reason="reference opening is absent from normalized main text",
                        context=_context(
                            chapter.body,
                            chapter.main_chars[min(max(previous_position + 1, 0), len(chapter.main_chars) - 1)].body_offset
                            if chapter.main_chars
                            else 0,
                        ),
                    )
                )
            else:
                if kind == "partial":
                    score = MatchScore(
                        ratio=score.ratio,
                        common_prefix=score.common_prefix,
                        exact_count=score.exact_count,
                        position=partial_position,
                    )
                    candidate_position = partial_position
                    note = "Only a later continuation of the structural reference entry survives in the normalized main text."
                else:
                    candidate_position = score.position
                    note = ""

                if candidate_position <= previous_position:
                    remove.append(entry)
                    exceptions.append(
                        GuideException(
                            reference_ordinal=entry.ordinal,
                            reason="reference candidate has no distinct increasing source position",
                            context=_context(
                                chapter.body,
                                chapter.main_chars[min(max(previous_position, 0), len(chapter.main_chars) - 1)].body_offset
                                if chapter.main_chars
                                else 0,
                            ),
                        )
                    )
                else:
                    candidates.append(
                        Candidate(
                            reference_ordinal=entry.ordinal,
                            position=candidate_position,
                            score=score,
                            kind=kind,
                            note=note,
                        )
                    )
                    previous_position = candidate_position
            reference_offset = next_reference_offset

        if not remove:
            return candidates, exceptions, alignment_ratio
        remove_ids = {id(entry) for entry in remove}
        active = [entry for entry in active if id(entry) not in remove_ids]

    return candidates, exceptions, alignment_ratio


def _confidence(
    candidate: Candidate, unique: bool, anchor_note: str = ""
) -> tuple[str, str]:
    if candidate.kind == "partial":
        return (
            "low",
            candidate.note
            + " The emitted anchor is the exact surviving source text and requires manual review.",
        )
    if anchor_note:
        return "low", anchor_note
    if not unique:
        return (
            "low",
            "The exact source anchor is not unique; review the boundary before use.",
        )
    if candidate.score.ratio >= 0.78 and candidate.score.common_prefix >= 4:
        return "high", ""
    return (
        "medium",
        "The opening is present, but structural-reference alignment is weaker than the high-confidence threshold; review the exact source span.",
    )


def propose_chapter(chapter: SourceChapter, reference: ReferenceChapter) -> ChapterProposal:
    if chapter.chapter_number != reference.chapter_number:
        raise ValueError("source and structural reference chapter numbers differ")
    candidates, guide_exceptions, alignment_ratio = _resolve_candidates(chapter, reference)
    slug = CHAPTER_SLUGS[chapter.chapter_number - 1]
    chapter_id = f"{chapter.chapter_number:02d}-{slug}"
    boundaries: list[BoundaryProposal] = []

    for ordinal, candidate in enumerate(candidates, start=1):
        source_char = chapter.main_chars[candidate.position]
        anchor, body_offset, unique, anchor_note = _raw_anchor(
            chapter, candidate.position
        )
        confidence, note = _confidence(candidate, unique, anchor_note)
        if candidate.kind == "opening" and candidate.note:
            note = f"{candidate.note} {note}".strip()
        boundaries.append(
            BoundaryProposal(
                entry_id=f"{chapter_id}-{ordinal:03d}",
                ordinal=ordinal,
                opening_text=anchor,
                source_normalized_line=source_char.normalized_line,
                source_line=source_char.source_line,
                source_page_marker=source_char.page_marker,
                normalized_filename=source_char.normalized_filename,
                file_section=source_char.file_section,
                confidence=confidence,
                note=note,
                source_main_offset=candidate.position,
                body_offset=body_offset,
                anchor_count=chapter.body.count(anchor),
            )
        )

    validation = _validate(chapter, boundaries)
    return ChapterProposal(
        chapter=chapter,
        chapter_id=chapter_id,
        slug=slug,
        reference_count=len(reference.entries),
        boundaries=tuple(boundaries),
        guide_exceptions=tuple(guide_exceptions),
        validation=validation,
        alignment_ratio=alignment_ratio,
    )


def _yaml_list(lines: list[str], key: str, values: Iterable[str]) -> None:
    lines.append(f"{key}:")
    for value in values:
        lines.append(f"  - {_json(value)}")


def render_manifest(proposal: ChapterProposal) -> str:
    chapter = proposal.chapter
    lines = [
        "schema: 1",
        'stage: "boundary-proposal"',
        'chapter_id: ' + _json(proposal.chapter_id),
        'chapter_heading: ' + _json(chapter.heading),
        'source_chapter: ' + _json(str(chapter.path)),
        'review_status: "auto"',
        'boundary_method: ' + _json(
            "Structural-reference alignment for proposals; exact anchors are sliced from normalized traditional source. Physical lines and page markers are not boundaries."
        ),
        'reference_source: ' + _json("content/shishuo.txt (structural guide only; not emitted)"),
        f"reference_entry_count: {proposal.reference_count}",
        f"proposed_entry_count: {len(proposal.boundaries)}",
        'alignment_ratio: ' + _json(f"{proposal.alignment_ratio:.6f}"),
    ]
    _yaml_list(lines, "source_normalized_files", chapter.source_normalized_files)
    _yaml_list(lines, "source_paths", chapter.source_paths)
    _yaml_list(lines, "source_sha256", chapter.source_sha256)
    _yaml_list(lines, "file_sections", tuple(segment.file_section for segment in chapter.source_segments))
    lines.extend(
        [
            'kanripo_title: ' + _json(chapter.title),
            'kanripo_id: ' + _json(chapter.kanripo_id),
            'kanripo_baseedition: ' + _json(chapter.baseedition),
            'kanripo_witness: ' + _json(chapter.witness),
            'entries:',
        ]
    )
    for boundary in proposal.boundaries:
        lines.extend(
            [
                f"  - id: {_json(boundary.entry_id)}",
                f"    ordinal: {boundary.ordinal}",
                f"    opening_text: {_json(boundary.opening_text)}",
                f"    source_normalized_filename: {_json(boundary.normalized_filename)}",
                f"    file_section: {_json(boundary.file_section)}",
                f"    source_normalized_line: {boundary.source_normalized_line}",
                f"    source_line: {boundary.source_line}",
                f"    source_page_marker: {_json(boundary.source_page_marker)}",
                f"    boundary_confidence: {_json(boundary.confidence)}",
                '    review_status: "auto"',
            ]
        )
        if boundary.note:
            lines.append(f"    note: {_json(boundary.note)}")
    return "\n".join(lines) + "\n"


def _confidence_counts(proposal: ChapterProposal) -> dict[str, int]:
    counts = {"high": 0, "medium": 0, "low": 0}
    for boundary in proposal.boundaries:
        counts[boundary.confidence] += 1
    return counts


def _report_boundary(proposal: ChapterProposal, boundary: BoundaryProposal) -> list[str]:
    context = _context(proposal.chapter.body, boundary.body_offset)
    lines = [
        f"#### {boundary.entry_id} ({boundary.confidence})",
        "",
        f"- source: `{boundary.normalized_filename}`, FILE `{boundary.file_section}`, normalized line `{boundary.source_normalized_line}`, source line `{boundary.source_line}`, page `{boundary.source_page_marker}`",
        f"- opening anchor: `{boundary.opening_text.replace(chr(10), '↵')}`",
        f"- context: `{context}`",
        f"- note: {boundary.note}",
        "",
    ]
    return lines


def render_report(proposals: Sequence[ChapterProposal]) -> str:
    total_counts = Counter(
        boundary.confidence
        for proposal in proposals
        for boundary in proposal.boundaries
    )
    lines = [
        "# Shishuo Xinyu proposed entry-boundary review",
        "",
        "This is a Phase 1 proposal report.  No new entry Markdown was generated.",
        "All emitted anchors are exact substrings of the normalized traditional chapter source.  The local `content/shishuo.txt` file was used only as a read-only structural guide; its simplified text is not emitted.",
        "",
        "## Summary by chapter",
        "",
        "| chapter | proposed entries | high | medium | low | reference guide entries | alignment | validation |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for proposal in proposals:
        counts = _confidence_counts(proposal)
        validation = "passed" if proposal.validation.passed else "exceptions"
        lines.append(
            f"| {proposal.chapter_id} ({proposal.chapter.heading}) | {len(proposal.boundaries)} | {counts['high']} | {counts['medium']} | {counts['low']} | {proposal.reference_count} | {proposal.alignment_ratio:.3f} | {validation} |"
        )

    lines.extend(
        [
            "",
            f"Overall proposed boundaries: {sum(total_counts.values())}; high: {total_counts['high']}; medium: {total_counts['medium']}; low: {total_counts['low']}.",
            "",
        ]
    )

    lines.extend(["", "## Validation results", ""])
    for proposal in proposals:
        result = proposal.validation
        lines.append(f"### {proposal.chapter_id}")
        lines.append("")
        lines.append(f"- anchors exactly once: {'passed' if not result.anchor_errors else 'exceptions'}")
        lines.append(f"- unique anchors: {'passed' if not result.duplicate_anchors else 'exceptions'}")
        lines.append(f"- continuous ordinals: {'passed' if not result.ordinal_errors else 'exceptions'}")
        lines.append(f"- no empty entries: {'passed' if not result.empty_entries else 'exceptions'}")
        lines.append(f"- page markers traceable: {'passed' if not result.page_marker_errors else 'exceptions'}")
        lines.append(f"- parentheses balanced: {'passed' if result.parenthesis_balanced else 'exceptions'}")
        for error in (
            *result.anchor_errors,
            *result.ordinal_errors,
            *result.empty_entries,
            *result.page_marker_errors,
        ):
            lines.append(f"- exception: {error}")
        lines.append("")

    lines.extend(["## Medium- and low-confidence boundaries", ""])
    review_count = 0
    for proposal in proposals:
        for boundary in proposal.boundaries:
            if boundary.confidence in {"medium", "low"}:
                lines.extend(_report_boundary(proposal, boundary))
                review_count += 1
    if review_count == 0:
        lines.extend(["No medium- or low-confidence boundaries were emitted.", ""])

    lines.extend(["## Structural-reference exceptions not emitted as boundaries", ""])
    exception_count = 0
    for proposal in proposals:
        if not proposal.guide_exceptions:
            continue
        lines.append(f"### {proposal.chapter_id} ({proposal.chapter.heading})")
        lines.append("")
        for exception in proposal.guide_exceptions:
            lines.append(
                f"- reference ordinal `{exception.reference_ordinal}`: {exception.reason}; context: `{exception.context}`"
            )
            exception_count += 1
        lines.append("")
    if exception_count == 0:
        lines.extend(["No structural-reference exceptions were detected.", ""])

    lines.extend(["## Duplicate or non-unique anchors", ""])
    duplicate_count = 0
    for proposal in proposals:
        for duplicate in proposal.validation.duplicate_anchors:
            lines.append(f"- {proposal.chapter_id}: {duplicate}")
            duplicate_count += 1
    if duplicate_count == 0:
        lines.extend(["None detected.", ""])

    lines.extend(["## Structurally unusual chapters", ""])
    unusual = [
        proposal
        for proposal in proposals
        if len(proposal.chapter.source_segments) > 1
        or proposal.guide_exceptions
        or any(boundary.confidence == "low" for boundary in proposal.boundaries)
    ]
    if not unusual:
        lines.extend(["None detected.", ""])
    else:
        for proposal in unusual:
            reasons: list[str] = []
            if len(proposal.chapter.source_segments) > 1:
                reasons.append("canonical chapter spans multiple normalized FILE sections")
            if proposal.guide_exceptions:
                reasons.append("structural-guide entries are absent or have no distinct source position")
            if any(boundary.confidence == "low" for boundary in proposal.boundaries):
                reasons.append("a surviving continuation is emitted as a low-confidence boundary")
            lines.append(f"- {proposal.chapter_id}: {'; '.join(reasons)}.")
        lines.append("")

    lines.extend(["## Manual-review chapters", ""])
    review_chapters = [
        proposal.chapter_id
        for proposal in proposals
        if any(boundary.confidence in {"medium", "low"} for boundary in proposal.boundaries)
        or proposal.guide_exceptions
        or not proposal.validation.passed
    ]
    lines.append(", ".join(review_chapters) if review_chapters else "None.")
    lines.append("")
    lines.extend(
        [
            "## Scope boundary",
            "",
            "These manifests propose only source entry anchors.  They do not extract people, aliases, relationships, summaries, translations, or historical interpretations, and they do not generate final entry Markdown.",
            "",
        ]
    )
    return "\n".join(lines)


def generate_proposals(
    chapter_dir: Path = DEFAULT_CHAPTER_DIR,
    reference_path: Path = DEFAULT_REFERENCE,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    report_path: Path = DEFAULT_REPORT,
) -> tuple[ChapterProposal, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    proposals: list[ChapterProposal] = []
    for chapter_number in range(1, 37):
        if chapter_number == 6:
            continue
        chapter_path = chapter_dir / f"chapter-{chapter_number:02d}.md"
        chapter = load_source_chapter(chapter_path)
        reference = load_reference_chapter(reference_path, chapter_number)
        proposal = propose_chapter(chapter, reference)
        (output_dir / f"{chapter_number:02d}-{CHAPTER_SLUGS[chapter_number - 1]}.yaml").write_text(
            render_manifest(proposal), encoding="utf-8"
        )
        proposals.append(proposal)
    report_path.write_text(render_report(proposals), encoding="utf-8")
    return tuple(proposals)


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chapter-dir", type=Path, default=DEFAULT_CHAPTER_DIR)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    proposals = generate_proposals(
        chapter_dir=args.chapter_dir,
        reference_path=args.reference,
        output_dir=args.output_dir,
        report_path=args.report,
    )
    total = sum(len(proposal.boundaries) for proposal in proposals)
    counts = {"high": 0, "medium": 0, "low": 0}
    for proposal in proposals:
        for boundary in proposal.boundaries:
            counts[boundary.confidence] += 1
    print(
        f"generated {len(proposals)} manifests; total={total}; "
        f"high={counts['high']}; medium={counts['medium']}; low={counts['low']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
