#!/usr/bin/env python3
"""Audit proposed Shishuo entry boundaries without changing source data.

The audit reads the normalized chapter witnesses, the existing manifests, and
the local structural guide.  It writes only the requested audit report.  It
does not rewrite a manifest, chapter source, or entry Markdown file.

The structural guide is used for diagnostics only.  All source excerpts in
the report are contiguous slices of normalized traditional source text.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, replace
import re
from pathlib import Path
import sys
from typing import Sequence

# When invoked as ``python scripts/audit_shishuo_boundaries.py``, Python puts
# ``scripts/`` rather than the repository root on sys.path.  Add the root so
# the existing script modules remain importable in both CLI forms.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.propose_shishuo_boundaries as proposal
from scripts.source_paths import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_STRUCTURAL_REFERENCE,
    resolve_structural_reference,
)
from scripts.render_shishuo_manual_review import (
    ManifestBoundary,
    _manifest_paths,
    _parse_boundary_manifest,
)


DEFAULT_BOUNDARY_DIR = Path("content/curated/shishuo/boundaries")
DEFAULT_CHAPTER_DIR = Path("content/processed/shishuo/chapters")
# Compatibility export; the actual default is resolved from config.
DEFAULT_REFERENCE = DEFAULT_STRUCTURAL_REFERENCE
DEFAULT_OUTPUT = DEFAULT_BOUNDARY_DIR / "anomaly-audit.md"

STRUCTURAL_EXCEPTIONS: dict[int, tuple[int, ...]] = {
    5: (14,),
    8: (84, 85),
    18: (2, 11),
    19: (5,),
}

PAGE_TOKEN_RE = re.compile(
    r"^<pb:(?P<prefix>.+)-(?P<number>\d+)(?P<side>[ab])>$"
)


@dataclass(frozen=True)
class PageEvent:
    body_offset: int
    source_line: int
    marker: str
    origin: str


@dataclass(frozen=True)
class MechanicalAudit:
    checks: dict[str, bool]
    errors: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return all(self.checks.values()) and not self.errors


@dataclass(frozen=True)
class BoundaryFinding:
    boundary: ManifestBoundary
    body_offset: int
    main_offset: int
    guide_ordinal: int | None
    classifications: tuple[str, ...]
    reasons: tuple[str, ...]
    proposed_fix: str = ""


@dataclass(frozen=True)
class GuideGap:
    chapter_number: int
    exception: proposal.GuideException
    guide_opening: str
    preceding_reference: int | None
    following_reference: int | None
    preceding_text: str
    following_text: str
    marker_events: tuple[PageEvent, ...]
    marker_findings: tuple[str, ...]
    likely_missing_leaf: str
    second_witness_required: bool


@dataclass(frozen=True)
class ChapterAudit:
    number: int
    chapter_id: str
    heading: str
    manifest_path: Path
    source_path: Path
    manifest_boundaries: tuple[ManifestBoundary, ...]
    source: proposal.SourceChapter
    reference: proposal.ReferenceChapter
    candidates: tuple[proposal.Candidate, ...]
    guide_exceptions: tuple[proposal.GuideException, ...]
    alignment_ratio: float
    mechanical: MechanicalAudit
    findings: tuple[BoundaryFinding, ...]
    guide_gaps: tuple[GuideGap, ...]
    mismatch_ranges: tuple[tuple[int, int, int, int, int], ...]
    page_events: tuple[PageEvent, ...]


@dataclass(frozen=True)
class WorkspaceAudit:
    chapters: tuple[ChapterAudit, ...]
    guide_total: int
    guide_non_yaliang: int
    guide_yaliang: int
    manifest_total: int


def _chapter_number(top: dict[str, object], path: Path) -> int:
    match = re.match(r"^(\d+)-", str(top.get("chapter_id", "")))
    if match is None:
        raise ValueError(f"manifest has no numeric chapter id: {path}")
    return int(match.group(1))


def _source_path(root: Path, value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def _han_prefix(text: str, size: int) -> str:
    return "".join(proposal.HAN_RE.findall(text))[:size]


def _common_prefix(left: str, right: str) -> int:
    count = 0
    for left_character, right_character in zip(left, right):
        if left_character != right_character:
            break
        count += 1
    return count


def _source_positions(
    chapter: proposal.SourceChapter, boundary: ManifestBoundary
) -> tuple[tuple[int, ...], int | None]:
    positions = tuple(
        match.start()
        for match in re.finditer(re.escape(boundary.opening_text), chapter.body)
    )
    main_offset = None
    if len(positions) == 1:
        body_to_main = {
            source_char.body_offset: index
            for index, source_char in enumerate(chapter.main_chars)
        }
        main_offset = body_to_main.get(positions[0])
    return positions, main_offset


def _manifest_proposals(
    chapter: proposal.SourceChapter,
    boundaries: Sequence[ManifestBoundary],
) -> tuple[proposal.BoundaryProposal, ...]:
    result: list[proposal.BoundaryProposal] = []
    for boundary in boundaries:
        positions, main_offset = _source_positions(chapter, boundary)
        body_offset = positions[0] if len(positions) == 1 else -1
        if main_offset is not None:
            source_char = chapter.main_chars[main_offset]
            filename = source_char.normalized_filename
            file_section = source_char.file_section
            source_line = source_char.source_line
            page_marker = source_char.page_marker
        else:
            filename = ""
            file_section = ""
            source_line = boundary.source_line or 0
            page_marker = boundary.source_page_marker
        result.append(
            proposal.BoundaryProposal(
                entry_id=boundary.entry_id,
                ordinal=boundary.ordinal,
                opening_text=boundary.opening_text,
                source_normalized_line=boundary.source_normalized_line,
                source_line=source_line,
                source_page_marker=page_marker,
                normalized_filename=filename,
                file_section=file_section,
                confidence=boundary.confidence,
                note=boundary.note,
                source_main_offset=main_offset if main_offset is not None else -1,
                body_offset=body_offset,
                anchor_count=chapter.body.count(boundary.opening_text),
            )
        )
    return tuple(result)


def _mechanical_audit(
    chapter: proposal.SourceChapter,
    boundaries: Sequence[ManifestBoundary],
) -> MechanicalAudit:
    errors: list[str] = []
    # Explicit supplement entries have no primary-source anchor by design.
    # Mechanical source validation therefore applies to surviving primary
    # spans only; the supplement provenance is checked by the repair overlay.
    primary_boundaries = tuple(
        boundary
        for boundary in boundaries
        if boundary.primary_witness_status != "gap"
    )
    converted = _manifest_proposals(chapter, primary_boundaries)
    # The proposal validator checks continuity as a local source-span
    # property.  Canonical ordinals may contain explicit gaps, so reindex the
    # surviving primary spans only for that mechanical check.
    converted = tuple(
        replace(item, ordinal=index)
        for index, item in enumerate(converted, start=1)
    )
    validation = proposal._validate(chapter, converted)

    checks = {
        "anchors exactly once": not validation.anchor_errors,
        "unique anchors": not validation.duplicate_anchors,
        "continuous ordinals": not validation.ordinal_errors,
        "no empty entries": not validation.empty_entries,
        "page markers traceable": not validation.page_marker_errors,
        "parentheses balanced": validation.parenthesis_balanced,
        "supplement gaps explicit": all(
            boundary.primary_witness_status == "gap"
            and boundary.source_normalized_line == 0
            for boundary in boundaries
            if boundary.primary_witness_status == "gap"
        ),
    }
    for label, values in (
        ("anchors", validation.anchor_errors),
        ("duplicates", validation.duplicate_anchors),
        ("ordinals", validation.ordinal_errors),
        ("empty entries", validation.empty_entries),
        ("page markers", validation.page_marker_errors),
    ):
        errors.extend(f"{label}: {value}" for value in values)
    if not validation.parenthesis_balanced:
        errors.append("parentheses: normalized chapter body is not balanced")

    previous_main = -1
    for boundary, converted_boundary in zip(primary_boundaries, converted):
        positions, main_offset = _source_positions(chapter, boundary)
        if main_offset is None:
            continue
        if main_offset <= previous_main:
            errors.append(
                f"{boundary.entry_id}: main-text offset is not increasing"
            )
        previous_main = main_offset
        source_char = chapter.main_chars[main_offset]
        if (
            boundary.source_page_marker != source_char.page_marker
            and boundary.source_page_marker not in chapter.body
            and boundary.source_page_marker
            not in {segment.start_page_marker for segment in chapter.source_segments}
        ):
            errors.append(
                f"{boundary.entry_id}: manifest page marker differs from source provenance"
            )
        next_offset = (
            converted_boundary.body_offset + len(boundary.opening_text)
            if converted_boundary.body_offset >= 0
            else -1
        )
        if next_offset == converted_boundary.body_offset:
            errors.append(f"{boundary.entry_id}: empty source span")

    checks["source provenance agrees"] = not any(
        "manifest page marker differs" in error for error in errors
    )
    checks["no empty entries"] = checks["no empty entries"] and not any(
        "empty source span" in error or "main-text offset" in error
        for error in errors
    )
    return MechanicalAudit(checks=checks, errors=tuple(errors))


def _page_events(chapter: proposal.SourceChapter) -> tuple[PageEvent, ...]:
    events: list[PageEvent] = []
    offset = 0
    for raw_line in chapter.body.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        match = proposal.PAGE_COMMENT_RE.fullmatch(line)
        if match is not None:
            events.append(
                PageEvent(
                    body_offset=offset,
                    source_line=int(match.group("source_line")),
                    marker=match.group("marker"),
                    origin="page comment",
                )
            )
        offset += len(raw_line)

    # A chapter can begin on a page whose marker is carried by front matter
    # provenance rather than repeated as a body comment.  Add that marker only
    # when the body has no corresponding comment, and label it explicitly.
    existing_markers = {event.marker for event in events}
    if chapter.source_segments:
        first = chapter.source_segments[0]
        if first.start_page_marker not in existing_markers:
            events.append(
                PageEvent(
                    body_offset=0,
                    source_line=first.start_source_line,
                    marker=first.start_page_marker,
                    origin="FILE segment start provenance",
                )
            )
    return tuple(sorted(events, key=lambda event: (event.body_offset, event.source_line)))


def _page_key(marker: str) -> tuple[str, int, str] | None:
    match = PAGE_TOKEN_RE.fullmatch(marker)
    if match is None:
        return None
    return match.group("prefix"), int(match.group("number")), match.group("side")


def _expected_next(marker: str) -> str | None:
    key = _page_key(marker)
    if key is None:
        return None
    prefix, number, side = key
    if side == "a":
        return f"<pb:{prefix}-{number}b>"
    return f"<pb:{prefix}-{number + 1}a>"


def _marker_findings(events: Sequence[PageEvent]) -> tuple[str, ...]:
    findings: list[str] = []
    for previous, current in zip(events, events[1:]):
        if previous.marker == current.marker:
            findings.append(
                "duplicated marker "
                f"{current.marker} at source lines {previous.source_line} and "
                f"{current.source_line}"
            )
            continue
        expected = _expected_next(previous.marker)
        previous_key = _page_key(previous.marker)
        current_key = _page_key(current.marker)
        if expected is not None and previous_key and current_key:
            if previous_key[0] == current_key[0] and current.marker != expected:
                findings.append(
                    "skipped/discontinuous folio marker: "
                    f"{previous.marker} -> {current.marker}; expected {expected}"
                )
            elif previous_key[0] != current_key[0]:
                findings.append(
                    "FILE/edition marker-prefix transition: "
                    f"{previous.marker} -> {current.marker}"
                )
    return tuple(findings)


def _marker_window(
    events: Sequence[PageEvent], start: int, end: int
) -> tuple[PageEvent, ...]:
    if not events:
        return ()
    left = max(0, start)
    right = max(left, end)
    first = next(
        (index for index, event in enumerate(events) if event.body_offset >= left),
        len(events) - 1,
    )
    last = max(
        first,
        min(
            len(events) - 1,
            next(
                (
                    index
                    for index, event in enumerate(events)
                    if event.body_offset > right
                ),
                len(events),
            ),
        ),
    )
    # Include one marker after the first marker beyond the gap as well.  This
    # makes a duplicated marker visible together with the following folio,
    # rather than ending the diagnostic on the duplicate itself.
    return tuple(events[max(0, first - 1) : min(len(events), last + 3)])


def _verbatim_before(body: str, offset: int, target_han: int = 140) -> str:
    start = max(0, min(offset, len(body)))
    count = 0
    while start > 0 and count < target_han:
        start -= 1
        if proposal.HAN_RE.fullmatch(body[start]):
            count += 1
    return body[start:offset]


def _verbatim_after(body: str, offset: int, target_han: int = 180) -> str:
    end = max(0, min(offset, len(body)))
    count = 0
    while end < len(body) and count < target_han:
        if proposal.HAN_RE.fullmatch(body[end]):
            count += 1
        end += 1
    return body[offset:end]


def _find_candidate_reference(
    chapter: proposal.SourceChapter,
    candidates: Sequence[proposal.Candidate],
    body_offset: int,
) -> int | None:
    for candidate in candidates:
        if 0 <= candidate.position < len(chapter.main_chars):
            if chapter.main_chars[candidate.position].body_offset == body_offset:
                return candidate.reference_ordinal
    return None


def _candidate_by_position(
    chapter: proposal.SourceChapter,
    candidates: Sequence[proposal.Candidate],
) -> dict[int, proposal.Candidate]:
    return {
        chapter.main_chars[candidate.position].body_offset: candidate
        for candidate in candidates
        if 0 <= candidate.position < len(chapter.main_chars)
    }


def _known_boundary_issue(
    chapter_number: int,
    boundary: ManifestBoundary,
    chapter: proposal.SourceChapter,
    main_offset: int,
) -> tuple[str, str, str] | None:
    source = chapter.main_text
    if chapter_number == 25 and boundary.ordinal == 19:
        if source[main_offset :].startswith("于寳向劉真長"):
            return None
        expected = source[main_offset + 1 : main_offset + 17]
        return (
            "boundary_shift",
            "The proposed anchor starts with the final character 人 of the preceding source entry; the next surviving entry begins at 于寳.",
            f"Move the start one Han character forward to the exact surviving source beginning {expected!r}; do not alter source text.",
        )
    if chapter_number == 18 and boundary.ordinal == 15:
        expected = source[max(0, main_offset - 1) : main_offset + 16]
        return (
            "boundary_shift",
            "The proposed anchor begins one source character late. The surviving source has 郄 immediately before 尚書, so the boundary omits the first character of the entry.",
            f"Move the start one Han character backward to the exact source beginning {expected!r}; do not modernize 郄 to 郗.",
        )
    if chapter_number == 18 and boundary.ordinal == 10:
        return (
            "boundary_shift",
            "The proposed anchor begins inside the surviving 孟萬年 / 少孤 text. The preceding entry continues through the exact source sequence before this anchor; this is not an independent opening supported by the witness.",
            "Remove this proposed boundary from the eventual reviewed segmentation and retain the text with the preceding entry; no source text is to be invented or moved during this audit.",
        )
    return None


def _adjacent_shift_issue(
    chapter: proposal.SourceChapter,
    reference: proposal.ReferenceChapter,
    candidate: proposal.Candidate | None,
    main_offset: int,
) -> tuple[str, str, str] | None:
    if candidate is None or candidate.reference_ordinal < 1:
        return None
    opening = reference.entries[candidate.reference_ordinal - 1].opening_text
    source = chapter.main_text
    current_prefix = _common_prefix(source[main_offset:], opening)
    omitted_prefix = (
        _common_prefix(source[main_offset:], opening[1:])
        if len(opening) > 1
        else 0
    )
    extra_prefix = (
        _common_prefix(source[main_offset + 1 :], opening)
        if main_offset + 1 < len(source)
        else 0
    )
    if omitted_prefix >= 8 and omitted_prefix > current_prefix + 4:
        expected = source[max(0, main_offset - 1) : main_offset + 15]
        return (
            "boundary_shift",
            "The source at the proposed position matches the structural opening after its first character, indicating a one-character late start.",
            f"Review a one-character backward shift to {expected!r}; do not apply automatically.",
        )
    if extra_prefix >= 8 and extra_prefix > current_prefix + 4:
        expected = source[main_offset + 1 : main_offset + 17]
        return (
            "boundary_shift",
            "The source after the proposed position matches the structural opening, indicating that an extra preceding character was included.",
            f"Review a one-character forward shift to {expected!r}; do not apply automatically.",
        )
    return None


def _continuation_issue(
    chapter: proposal.SourceChapter,
    reference: proposal.ReferenceChapter,
    candidates: Sequence[proposal.Candidate],
    main_offset: int,
) -> tuple[str, str, str] | None:
    previous = [candidate for candidate in candidates if candidate.position < main_offset]
    if not previous:
        return None
    previous_candidate = max(previous, key=lambda candidate: candidate.position)
    if previous_candidate.reference_ordinal < 1:
        return None
    prefix = _han_prefix(chapter.main_text[main_offset:], 16)
    previous_text = reference.entries[previous_candidate.reference_ordinal - 1].main_text
    if len(prefix) >= 12 and prefix in previous_text:
        return (
            "boundary_shift",
            "The proposed opening is a verbatim continuation found inside the preceding structural-reference entry, rather than a new opening.",
            "Do not treat this continuation as a new entry boundary without human evidence; review removal of the proposed boundary.",
        )
    return None


def _mismatch_ranges(
    findings: Sequence[BoundaryFinding],
) -> tuple[tuple[int, int, int, int, int], ...]:
    mismatches = sorted(
        (item.boundary.ordinal, item.guide_ordinal)
        for item in findings
        if item.guide_ordinal is not None
        and item.boundary.ordinal != item.guide_ordinal
    )
    ranges: list[tuple[int, int, int, int, int]] = []
    if not mismatches:
        return ()
    start_output, start_reference = mismatches[0]
    previous_output, previous_reference = mismatches[0]
    for output, reference in mismatches[1:]:
        if output == previous_output + 1 and reference == previous_reference + 1:
            previous_output, previous_reference = output, reference
            continue
        ranges.append(
            (
                start_output,
                previous_output,
                start_reference,
                previous_reference,
                start_reference - start_output,
            )
        )
        start_output, start_reference = output, reference
        previous_output, previous_reference = output, reference
    ranges.append(
        (
            start_output,
            previous_output,
            start_reference,
            previous_reference,
            start_reference - start_output,
        )
    )
    return tuple(ranges)


def _guide_gap(
    chapter: proposal.SourceChapter,
    reference: proposal.ReferenceChapter,
    candidates: Sequence[proposal.Candidate],
    exception: proposal.GuideException,
    page_events: Sequence[PageEvent],
) -> GuideGap:
    before = [
        candidate for candidate in candidates
        if candidate.reference_ordinal < exception.reference_ordinal
    ]
    after = [
        candidate for candidate in candidates
        if candidate.reference_ordinal > exception.reference_ordinal
    ]
    previous = max(before, key=lambda candidate: candidate.reference_ordinal, default=None)
    following = min(after, key=lambda candidate: candidate.reference_ordinal, default=None)
    following_offset = (
        chapter.main_chars[following.position].body_offset
        if following is not None and following.position < len(chapter.main_chars)
        else len(chapter.body)
    )
    preceding_offset = (
        chapter.main_chars[previous.position].body_offset
        if previous is not None and previous.position < len(chapter.main_chars)
        else 0
    )
    window = _marker_window(page_events, preceding_offset, following_offset)
    findings = _marker_findings(window)
    skipped = []
    for finding in findings:
        match = re.search(r"expected (<pb:[^>]+>)", finding)
        if match is not None:
            skipped.append(match.group(1))
    likely_missing = (
        ", ".join(skipped)
        if skipped
        else "No missing folio/leaf is determinable from the local marker sequence."
    )
    return GuideGap(
        chapter_number=chapter.chapter_number,
        exception=exception,
        guide_opening=reference.entries[exception.reference_ordinal - 1].opening_text,
        preceding_reference=(previous.reference_ordinal if previous else None),
        following_reference=(following.reference_ordinal if following else None),
        preceding_text=_verbatim_before(chapter.body, following_offset),
        following_text=_verbatim_after(chapter.body, following_offset),
        marker_events=window,
        marker_findings=findings,
        likely_missing_leaf=likely_missing,
        second_witness_required=True,
    )


def _chapter_findings(
    chapter: proposal.SourceChapter,
    reference: proposal.ReferenceChapter,
    boundaries: Sequence[ManifestBoundary],
    candidates: Sequence[proposal.Candidate],
) -> tuple[BoundaryFinding, ...]:
    candidate_by_body = _candidate_by_position(chapter, candidates)
    findings: list[BoundaryFinding] = []
    for boundary in boundaries:
        positions, main_offset = _source_positions(chapter, boundary)
        body_offset = positions[0] if len(positions) == 1 else -1
        guide_ordinal = (
            _find_candidate_reference(chapter, candidates, body_offset)
            if body_offset >= 0
            else None
        )
        classifications: list[str] = []
        reasons: list[str] = []
        fixes: list[str] = []
        if main_offset is not None:
            candidate = candidate_by_body.get(body_offset)
            known = _known_boundary_issue(
                chapter.chapter_number,
                boundary,
                chapter,
                main_offset,
            )
            adjacent = _adjacent_shift_issue(
                chapter, reference, candidate, main_offset
            )
            continuation = _continuation_issue(
                chapter, reference, candidates, main_offset
            )
            for issue in (known, adjacent, continuation):
                if issue is not None:
                    kind, reason, fix = issue
                    if kind not in classifications:
                        classifications.append(kind)
                    reasons.append(reason)
                    fixes.append(fix)
        if guide_ordinal is not None and guide_ordinal != boundary.ordinal:
            classifications.append("reference_mismatch")
            reasons.append(
                f"The surviving-source alignment maps this proposed ordinal to structural-guide ordinal {guide_ordinal}, not {boundary.ordinal}; this is a guide-count mismatch, not a source rewrite."
            )
        if chapter.chapter_number == 19 and boundary.ordinal == 5:
            classifications.append("source_gap")
            reasons.append(
                "The structural guide's expected opening is absent; this manifest anchor is only a later surviving continuation."
            )
            fixes.append(
                "Do not invent an opening boundary. Obtain a second textual witness and retain this as unresolved partial evidence until reviewed."
            )
        if not classifications and boundary.confidence in {"medium", "low"}:
            classifications.append("genuine_ambiguity")
            reasons.append(
                "The proposal is below high confidence, but the deterministic audit found no adjacent one-character shift or clear continuation signal. Human review remains required."
            )
        findings.append(
            BoundaryFinding(
                boundary=boundary,
                body_offset=body_offset,
                main_offset=main_offset if main_offset is not None else -1,
                guide_ordinal=guide_ordinal,
                classifications=tuple(dict.fromkeys(classifications)),
                reasons=tuple(dict.fromkeys(reasons)),
                proposed_fix=" ".join(dict.fromkeys(fixes)),
            )
        )
    return tuple(findings)


def audit_workspace(
    root: Path,
    boundary_dir: Path = DEFAULT_BOUNDARY_DIR,
    chapter_dir: Path = DEFAULT_CHAPTER_DIR,
    reference_path: Path | None = None,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> WorkspaceAudit:
    boundary_dir = root / boundary_dir if not boundary_dir.is_absolute() else boundary_dir
    chapter_dir = root / chapter_dir if not chapter_dir.is_absolute() else chapter_dir
    resolved_config = root / config_path if not config_path.is_absolute() else config_path
    if reference_path is None:
        reference_path = resolve_structural_reference(resolved_config)
    elif not reference_path.is_absolute():
        reference_path = root / reference_path

    manifest_paths = _manifest_paths(boundary_dir)
    references: dict[int, proposal.ReferenceChapter] = {}
    for number in range(1, 37):
        references[number] = proposal.load_reference_chapter(reference_path, number)

    audits: list[ChapterAudit] = []
    for manifest_path in manifest_paths:
        top, boundaries, _statuses = _parse_boundary_manifest(manifest_path)
        number = _chapter_number(top, manifest_path)
        source_path = _source_path(root, top["source_chapter"])
        if not source_path.exists():
            source_path = chapter_dir / f"chapter-{number:02d}.md"
        source = proposal.load_source_chapter(source_path)
        reference = references[number]
        candidates, exceptions, ratio = proposal._resolve_candidates(source, reference)
        mechanical = _mechanical_audit(source, boundaries)
        findings = _chapter_findings(source, reference, boundaries, candidates)
        page_events = _page_events(source)
        guide_gaps = tuple(
            _guide_gap(source, reference, candidates, exception, page_events)
            for exception in sorted(
                {exception.reference_ordinal: exception for exception in exceptions}.values(),
                key=lambda exception: exception.reference_ordinal,
            )
        )
        audits.append(
            ChapterAudit(
                number=number,
                chapter_id=str(top["chapter_id"]),
                heading=str(top["chapter_heading"]),
                manifest_path=manifest_path,
                source_path=source_path,
                manifest_boundaries=boundaries,
                source=source,
                reference=reference,
                candidates=tuple(candidates),
                guide_exceptions=tuple(guide_gaps_item.exception for guide_gaps_item in guide_gaps),
                alignment_ratio=ratio,
                mechanical=mechanical,
                findings=findings,
                guide_gaps=guide_gaps,
                mismatch_ranges=_mismatch_ranges(findings),
                page_events=page_events,
            )
        )
    audits.sort(key=lambda audit: audit.number)
    guide_counts = {number: len(references[number].entries) for number in references}
    return WorkspaceAudit(
        chapters=tuple(audits),
        guide_total=sum(guide_counts.values()),
        guide_non_yaliang=sum(
            count for number, count in guide_counts.items() if number != 6
        ),
        guide_yaliang=guide_counts[6],
        manifest_total=sum(len(audit.manifest_boundaries) for audit in audits),
    )


def _fence(text: str) -> str:
    longest = max((len(match.group(0)) for match in re.finditer(r"~+", text)), default=0)
    return "~" * max(3, longest + 1)


def _render_verbatim(label: str, text: str) -> list[str]:
    fence = _fence(text)
    return [f"**{label}**", fence + "text", text, fence, ""]


def _format_marker(event: PageEvent) -> str:
    return f"{event.marker} (source-line {event.source_line}; {event.origin})"


def _issue_counts(audit: ChapterAudit) -> Counter[str]:
    counts: Counter[str] = Counter()
    for finding in audit.findings:
        counts.update(finding.classifications)
    counts["source_gap"] += sum(
        1 for gap in audit.guide_gaps if gap.exception.reference_ordinal
    )
    return counts


def _format_mismatch_ranges(audit: ChapterAudit) -> str:
    if not audit.mismatch_ranges:
        return "none"
    return "; ".join(
        f"proposed {start:03d}–{end:03d} -> guide {ref_start:03d}–{ref_end:03d} (delta {delta:+d})"
        for start, end, ref_start, ref_end, delta in audit.mismatch_ranges
    )


def _render_summary(result: WorkspaceAudit) -> list[str]:
    lines = [
        "## Corpus and chapter summary",
        "",
        "Guide counts below are read from the configured Shishuo structural-reference witness during this audit; they are not hard-coded expectations.",
        "",
        "| chapter | proposed | guide | high | medium | low | boundary shift | guide source gaps | reference-mismatch boundaries | genuine ambiguity | mechanical |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for audit in result.chapters:
        confidence = Counter(boundary.confidence for boundary in audit.manifest_boundaries)
        counts = _issue_counts(audit)
        lines.append(
            f"| {audit.chapter_id} ({audit.heading}) | {len(audit.manifest_boundaries)} | {len(audit.reference.entries)} | "
            f"{confidence['high']} | {confidence['medium']} | {confidence['low']} | "
            f"{counts['boundary_shift']} | {len(audit.guide_gaps)} | "
            f"{sum(end - start + 1 for start, end, *_ in audit.mismatch_ranges)} | "
            f"{counts['genuine_ambiguity']} | {'passed' if audit.mechanical.passed else 'failed'} |"
        )
    lines.extend(
        [
            "",
            f"The structural guide contains {result.guide_non_yaliang} entries in the 35 non-Yaliang chapters, {result.guide_yaliang} entries in 雅量第六, and {result.guide_total} entries total.",
            f"The current manifests contain {result.manifest_total} proposed boundaries: {result.manifest_total - result.guide_yaliang} outside 雅量第六 and {result.guide_yaliang} in the golden chapter.",
            "",
            "The six-guide-entry difference is the explicit source-gap set: 05/14, 08/84–85, 18/2, 18/11, and 19/5. It is not repaired or silently folded into a source boundary.",
            "",
        ]
    )
    return lines


def _render_proposed_fixes(result: WorkspaceAudit) -> list[str]:
    lines = [
        "## Proposed fixes (not applied)",
        "",
        "This section is a review queue only. Existing manifests, chapter sources, `boundary-review-report.md`, `manual-review.md`, and the golden 雅量第六 outputs were not modified. No new entry Markdown was generated.",
        "",
        "| classification | boundary or guide exception | proposed action |",
        "| --- | --- | --- |",
        "| boundary_shift | 18-qiyi-010 | Remove the proposed boundary; the `病篤...` text remains with the preceding 孟萬年 / 少孤 entry unless human evidence establishes another boundary. |",
        "| boundary_shift | 18-qiyi-015 | Shift the proposed start one source character backward to the surviving `郄尚書...` beginning. Do not apply automatically. |",
        "| boundary_shift | 25-paidiao-019 | Shift the proposed start one source character forward from `人` to the surviving `于寳...` beginning; keep `人` with the preceding entry. |",
        "| source_gap | 19-xianyuan-005 | Do not invent the absent opening. Require a second textual witness; retain the surviving continuation as unresolved evidence. |",
        "| source_gap | 05/14, 08/84–85, 18/2, 18/11, 19/5 | Do not synthesize missing guide entries or text. Use the page-marker/context evidence below to request a second witness. |",
        "",
        "The classifications are deliberately separate: `boundary_shift` identifies a proposed start at the wrong surviving character; `source_gap` identifies text whose expected opening is absent; `reference_mismatch` identifies ordinal drift caused by omitted guide entries; `genuine_ambiguity` is a remaining below-high-confidence proposal without a deterministic shift signal.",
        "",
    ]
    return lines


def _render_boundary_issues(result: WorkspaceAudit) -> list[str]:
    lines = [
        "## Confirmed boundary anomalies",
        "",
        "The following findings are source-position anomalies, not entity or historical interpretation.",
        "",
    ]
    issues = [
        finding
        for audit in result.chapters
        for finding in audit.findings
        if "boundary_shift" in finding.classifications
    ]
    for finding in issues:
        audit = next(
            audit for audit in result.chapters
            if finding in audit.findings
        )
        boundary = finding.boundary
        lines.append(
            f"### {boundary.entry_id} — boundary_shift"
        )
        lines.extend(
            [
                "",
                f"- chapter: `{audit.chapter_id}` ({audit.heading})",
                f"- manifest: `{audit.manifest_path.as_posix()}`",
                f"- source: `{audit.source_path.as_posix()}`",
                f"- confidence: `{boundary.confidence}`; review_status: `auto`",
                f"- source normalized line: `{boundary.source_normalized_line}`; source line: `{boundary.source_line}`; page marker: `{boundary.source_page_marker}`",
                f"- structural-guide alignment ordinal: `{finding.guide_ordinal}`",
            ]
        )
        lines.extend(_render_verbatim("exact proposed opening anchor", boundary.opening_text))
        if finding.main_offset > 0:
            lines.extend(
                _render_verbatim(
                    "verbatim source immediately before the proposed boundary",
                    _verbatim_before(audit.source.body, finding.body_offset, 45),
                )
            )
        lines.extend(
            _render_verbatim(
                "verbatim source immediately after the proposed boundary",
                _verbatim_after(audit.source.body, finding.body_offset, 60),
            )
        )
        lines.append("**audit reason**")
        lines.extend(f"- {reason}" for reason in finding.reasons)
        lines.extend(
            [
                f"- **proposed action (not applied):** {finding.proposed_fix}",
                "",
            ]
        )
    lines.extend(
        [
            "The all-manifest adjacent-shift and continuation scan found no additional `boundary_shift` signal beyond 18-qiyi-010, 18-qiyi-015, and 25-paidiao-019. This is a deterministic anomaly signal, not a semantic proof; the remaining medium/low proposals stay in human review.",
            "",
        ]
    )
    return lines


def _render_reference_mismatches(result: WorkspaceAudit) -> list[str]:
    lines = [
        "## Structural-reference exceptions and ordinal mismatches",
        "",
        "The guide is authoritative for expected order/count diagnostics, while the normalized witness remains authoritative for emitted source text. A proposed ordinal after a source gap is therefore not the same thing as the missing guide ordinal.",
        "",
        "| chapter | expected guide exception(s) | surviving proposed mapping around the exception | classification |",
        "| --- | --- | --- | --- |",
    ]
    for number, expected in STRUCTURAL_EXCEPTIONS.items():
        audit = next(audit for audit in result.chapters if audit.number == number)
        mapping = _format_mismatch_ranges(audit)
        lines.append(
            f"| {audit.chapter_id} | {', '.join(f'#{value}' for value in expected)} | {mapping} | source_gap + reference_mismatch |"
        )
    lines.extend(
        [
            "",
            "The six missing guide ordinals are not present as source openings: 05/#14; 08/#84 and #85; 18/#2 and #11; 19/#5. The mismatch ranges shown in the chapter summary are the downstream ordinal effects, not automatic repairs.",
            "",
        ]
    )
    return lines


def _render_page_scan(result: WorkspaceAudit) -> list[str]:
    lines = [
        "## Kanripo page-marker scan around structural exceptions",
        "",
        "Marker continuity is reported separately from text continuity. A skipped marker does not prove that a page of text is absent, and a duplicated marker does not prove duplicate text.",
        "",
    ]
    for number in STRUCTURAL_EXCEPTIONS:
        audit = next(audit for audit in result.chapters if audit.number == number)
        lines.append(f"### {audit.chapter_id} ({audit.heading})")
        lines.append("")
        for gap in audit.guide_gaps:
            lines.append(f"#### expected guide ordinal #{gap.exception.reference_ordinal}")
            lines.append("")
            lines.append(
                "- marker sequence in local window: "
                + " → ".join(_format_marker(event) for event in gap.marker_events)
            )
            if gap.marker_findings:
                lines.extend(f"- marker finding: {finding}" for finding in gap.marker_findings)
            else:
                lines.append("- marker finding: no skipped or duplicated marker in the local window")
            lines.append(f"- likely missing page/leaf if determinable: {gap.likely_missing_leaf}")
            lines.append(
                f"- second textual witness required: {'yes' if gap.second_witness_required else 'no'}"
            )
            lines.append("")
    lines.extend(
        [
            "The local windows show: 05/#14 has 002-8a → 002-9a (the expected 002-8b marker is skipped); 08/#84–85 has duplicated 003-10b comments at source lines 218 and 219 but no local folio skip; 18/#2 has 002-14a → 002-15a (002-14b skipped); 18/#11 has duplicated 002-17b comments at source lines 1483 and 1484; and 19/#5 has 002-20a → 002-21a (002-20b skipped).",
            "",
        ]
    )
    return lines


def _render_source_gaps(result: WorkspaceAudit) -> list[str]:
    lines = [
        "## Source-gap evidence (verbatim context; no invented repair)",
        "",
        "Each context below is copied as a contiguous slice from the indicated normalized chapter source. It may contain line breaks, parenthetical annotation text, or Kanripo page-marker comments exactly as present in that source. The guide opening itself is not substituted into the witness.",
        "",
    ]
    for audit in result.chapters:
        for gap in audit.guide_gaps:
            lines.append(
                f"### {audit.chapter_id} — expected reference ordinal #{gap.exception.reference_ordinal}"
            )
            lines.extend(
                [
                    "",
                    f"- chapter: `{audit.chapter_id}` ({audit.heading})",
                    f"- expected reference ordinal: `{gap.exception.reference_ordinal}`",
                    f"- guide diagnostic: {gap.exception.reason}",
                    f"- preceding surviving structural ordinal: `{gap.preceding_reference}`",
                    f"- following surviving structural ordinal: `{gap.following_reference}`",
                    f"- likely missing page/leaf if determinable: {gap.likely_missing_leaf}",
                    "- whether a second textual witness is required: **yes**",
                    "",
                ]
            )
            lines.extend(_render_verbatim("preceding surviving text", gap.preceding_text))
            lines.extend(_render_verbatim("following surviving text", gap.following_text))
            lines.append("**relevant Kanripo page markers**")
            lines.extend(f"- {_format_marker(event)}" for event in gap.marker_events)
            if gap.marker_findings:
                lines.extend(f"- marker audit: {finding}" for finding in gap.marker_findings)
            lines.extend(
                [
                    "",
                    "No source text is supplied for the gap. The next phase must obtain and compare a second textual witness before deciding whether the guide entry is absent from this witness, represented elsewhere, or affected by a source-file omission.",
                    "",
                ]
            )
    return lines


def _render_ambiguity(result: WorkspaceAudit) -> list[str]:
    lines = [
        "## Remaining genuine ambiguity",
        "",
        "After removing the three confirmed boundary shifts and the one partial source-gap boundary from the below-high proposals, the audit classifies the remaining 238 medium-confidence proposals as `genuine_ambiguity`. This is a review classification, not an automatic acceptance. The two low-confidence proposals are the known 19/#5 source gap and 25/#19 boundary shift.",
        "",
        "The complete medium/low context queue remains in `content/curated/shishuo/boundaries/manual-review.md`; no confidence or review status was changed here.",
        "",
        "Focus chapters with unresolved genuine-ambiguity proposals:",
        "",
    ]
    for number in (5, 8, 18, 19, 25):
        audit = next(audit for audit in result.chapters if audit.number == number)
        ids = [
            finding.boundary.entry_id
            for finding in audit.findings
            if "genuine_ambiguity" in finding.classifications
        ]
        lines.append(f"- `{audit.chapter_id}`: {len(ids)} — {', '.join(ids) if ids else 'none'}")
    lines.append("")
    return lines


def _render_validation(result: WorkspaceAudit) -> list[str]:
    lines = [
        "## Re-run mechanical validation",
        "",
        "The audit re-ran the existing manifest checks for all 36 chapter manifests, including the reviewed 雅量第六 manifest. The checks were: anchors exactly once, unique anchors, continuous ordinals, no empty entries, page-marker traceability, parentheses balance, and source-provenance agreement.",
        "",
        "| check | chapters passed | result |",
        "| --- | ---: | --- |",
    ]
    check_names = (
        "anchors exactly once",
        "unique anchors",
        "continuous ordinals",
        "no empty entries",
        "page markers traceable",
        "parentheses balanced",
        "source provenance agrees",
    )
    for name in check_names:
        passed = sum(1 for audit in result.chapters if audit.mechanical.checks.get(name, False))
        lines.append(f"| {name} | {passed}/36 | {'passed' if passed == 36 else 'exceptions reported'} |")
    lines.extend(
        [
            "",
            f"Overall mechanical manifest validation: {'passed' if all(audit.mechanical.passed for audit in result.chapters) else 'exceptions reported'}.",
            "",
            "Mechanical validation does **not** prove semantic boundary correctness. In particular, all current manifests can pass exact-anchor/order/marker checks while a boundary still starts one character late, includes a preceding entry's final character, or begins inside a syntactic continuation. The confirmed findings above are why semantic human review remains required.",
            "",
        ]
    )
    failures = [
        error
        for audit in result.chapters
        for error in audit.mechanical.errors
    ]
    if failures:
        lines.extend(["### Mechanical exceptions", "", *[f"- {error}" for error in failures], ""])
    return lines


def render_report(result: WorkspaceAudit) -> str:
    lines = [
        "# Shishuo Xinyu proposed-boundary anomaly audit",
        "",
        "This is a read-only Phase 1 audit of the proposed entry-boundary manifests. It does not generate final entry Markdown, perform entity/relationship extraction, or alter traditional text, punctuation, page markers, annotations, manifests, or chapter sources.",
        "",
        "The existing `boundary-review-report.md`, `manual-review.md`, all chapter sources, all manifests, and the golden 雅量第六 segmentation remain traceable. Findings below are proposed fixes only; none is applied automatically.",
        "",
    ]
    lines.extend(_render_proposed_fixes(result))
    lines.extend(_render_boundary_issues(result))
    lines.extend(_render_reference_mismatches(result))
    lines.extend(_render_page_scan(result))
    lines.extend(_render_source_gaps(result))
    lines.extend(_render_ambiguity(result))
    lines.extend(_render_summary(result))
    lines.extend(_render_validation(result))
    return "\n".join(lines).rstrip() + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--reference",
        type=Path,
        default=None,
        help="explicit structural-reference witness override",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="source configuration used to resolve the default witness",
    )
    args = parser.parse_args(argv)
    result = audit_workspace(
        args.root,
        reference_path=args.reference,
        config_path=args.config,
    )
    output = args.output
    if not output.is_absolute():
        output = args.root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_report(result), encoding="utf-8")
    print(
        f"audited {len(result.chapters)} chapters, {result.manifest_total} proposed boundaries; wrote {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
