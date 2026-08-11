#!/usr/bin/env python3
"""Render a deterministic human-review queue for Shishuo boundaries.

The script reads boundary manifests and normalized chapter bodies.  It never
changes a manifest or chapter and never writes entry Markdown.  Every source
excerpt in the output is a contiguous, verbatim slice of its normalized
chapter body.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable

import yaml

DEFAULT_BOUNDARY_DIR = Path("content/curated/shishuo/boundaries")
DEFAULT_OUTPUT = DEFAULT_BOUNDARY_DIR / "manual-review.md"
STRUCTURALLY_UNUSUAL_CHAPTERS = frozenset({5, 8, 18, 19, 25})

@dataclass(frozen=True)
class ReviewItem:
    chapter_number: int
    chapter_id: str
    chapter_heading: str
    source_chapter: str
    entry_id: str
    ordinal: int
    confidence: str
    opening_text: str
    source_normalized_line: int
    source_line: int | None
    source_page_marker: str
    review_status: str
    reason: str
    context_before: str
    context_after: str
    before_han_count: int
    after_han_count: int
    structural_context: tuple[str, ...]
    selection_kind: str


@dataclass(frozen=True)
class ManifestBoundary:
    entry_id: str
    ordinal: int
    opening_text: str
    source_normalized_line: int
    source_line: int | None
    source_page_marker: str
    confidence: str
    note: str = ""
    primary_witness_status: str = "present"


def _scalar(value: str) -> Any:
    value = value.strip()
    if value.startswith('"'):
        return json.loads(value)
    if value == "null":
        return None
    try:
        return int(value)
    except ValueError:
        return value


def _parse_boundary_manifest(
    path: Path,
) -> tuple[dict[str, Any], tuple[ManifestBoundary, ...], dict[str, str]]:
    """Parse both the original compact manifests and repaired YAML."""

    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("entries"), list):
        raise ValueError(f"invalid boundary manifest: {path}")
    top = {key: value for key, value in document.items() if key != "entries"}
    raw_entries = list(document["entries"])

    required_top = {"schema", "chapter_id", "chapter_heading", "source_chapter"}
    missing = sorted(required_top - top.keys())
    if missing:
        raise ValueError(f"manifest missing fields {', '.join(missing)}: {path}")

    statuses: dict[str, str] = {}
    boundaries: list[ManifestBoundary] = []
    for expected, item in enumerate(raw_entries, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"manifest entry is not a mapping: {path}:{expected}")
        required = {
            "id",
            "ordinal",
            "opening_text",
            "source_normalized_line",
            "boundary_confidence",
        }
        missing_entry = sorted(required - item.keys())
        if missing_entry:
            raise ValueError(
                f"manifest entry {expected} missing {', '.join(missing_entry)}: {path}"
            )
        ordinal = int(item["ordinal"])
        if ordinal != expected:
            raise ValueError(
                f"manifest ordinal {ordinal} is not {expected}: {path}"
            )
        entry_id = str(item["id"])
        status = str(item.get("review_status", top.get("review_status", "unknown")))
        statuses[entry_id] = status
        boundaries.append(
            ManifestBoundary(
                entry_id=entry_id,
                ordinal=ordinal,
                opening_text=str(item["opening_text"]),
                source_normalized_line=(
                    int(item["source_normalized_line"])
                    if item.get("source_normalized_line") is not None
                    else 0
                ),
                source_line=(
                    int(item["source_line"])
                    if item.get("source_line") is not None
                    else None
                ),
                source_page_marker=str(item.get("source_page_marker", "")),
                confidence=str(item["boundary_confidence"]),
                note=str(item.get("note", "")),
                primary_witness_status=str(item.get("primary_witness_status", "present")),
            )
        )
    return top, tuple(boundaries), statuses


def _is_han(character: str) -> bool:
    if len(character) != 1:
        return False
    codepoint = ord(character)
    return 0x3400 <= codepoint <= 0x9FFF or 0x20000 <= codepoint <= 0x2FFFF


def _han_count(text: str) -> int:
    return sum(1 for character in text if _is_han(character))


def _source_body(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"chapter source has no YAML front matter: {path}")
    closing = next(
        (index for index in range(1, len(lines)) if lines[index].strip() == "---"),
        None,
    )
    if closing is None:
        raise ValueError(f"chapter source has unterminated front matter: {path}")
    return "".join(lines[closing + 1 :])


def _expand_structural_edges(body: str, start: int, end: int) -> tuple[int, int]:
    """Avoid cutting through a page comment or parenthetical block when nearby."""

    for _ in range(4):
        changed = False

        comment_start = body.rfind("<!--", 0, start)
        comment_end = body.rfind("-->", 0, start)
        if comment_start > comment_end:
            start = comment_start
            changed = True

        comment_start = body.rfind("<!--", start, end)
        comment_end = body.rfind("-->", start, end)
        if comment_start > comment_end:
            closing = body.find("-->", end)
            if closing >= 0:
                end = closing + len("-->")
                changed = True

        opening = body.rfind("(", 0, start)
        closing = body.rfind(")", 0, start)
        if opening > closing:
            start = opening
            changed = True

        depth = 0
        for character in body[start:end]:
            if character == "(":
                depth += 1
            elif character == ")" and depth:
                depth -= 1
        if depth:
            cursor = end
            while cursor < len(body) and depth:
                character = body[cursor]
                if character == "(":
                    depth += 1
                elif character == ")":
                    depth -= 1
                cursor += 1
            if depth == 0:
                end = cursor
                changed = True

        if not changed:
            break
    return start, end


def _context_before(body: str, offset: int, target_han: int = 125) -> str:
    start = offset
    count = 0
    while start > 0 and count < target_han:
        start -= 1
        if _is_han(body[start]):
            count += 1
    start, _ = _expand_structural_edges(body, start, offset)
    return body[start:offset]


def _context_after(body: str, offset: int, target_han: int = 175) -> str:
    end = offset
    count = 0
    while end < len(body) and count < target_han:
        if _is_han(body[end]):
            count += 1
        end += 1
    _, end = _expand_structural_edges(body, offset, end)
    return body[offset:end]


def _fence_for(text: str) -> str:
    longest = max((len(match.group(0)) for match in re.finditer(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def _chapter_number(top: dict[str, Any], manifest_path: Path) -> int:
    chapter_id = str(top.get("chapter_id", ""))
    match = re.match(r"^(\d+)-", chapter_id)
    if match is None:
        raise ValueError(f"manifest has no numeric chapter id: {manifest_path}")
    return int(match.group(1))


def _source_path(root: Path, source_chapter: str) -> Path:
    path = Path(source_chapter)
    return path if path.is_absolute() else root / path


def _manifest_paths(boundary_dir: Path) -> list[Path]:
    paths = sorted(boundary_dir.glob("*.yaml"))
    if not paths:
        raise FileNotFoundError(f"no YAML boundary manifests found in {boundary_dir}")
    return sorted(paths, key=lambda path: _manifest_sort_key(path))


def _manifest_sort_key(path: Path) -> tuple[int, str]:
    match = re.match(r"^(\d+)-", path.name)
    return (int(match.group(1)) if match else 10_000, path.name)


def _high_samples(
    boundaries: Iterable[ManifestBoundary], body: str | None = None
) -> tuple[ManifestBoundary, ...]:
    high = [boundary for boundary in boundaries if boundary.confidence == "high"]
    if body is not None:
        eligible: list[ManifestBoundary] = []
        for boundary in high:
            positions = [
                match.start()
                for match in re.finditer(re.escape(boundary.opening_text), body)
            ]
            if len(positions) == 1:
                offset = positions[0]
                if _han_count(body[:offset]) >= 100 and _han_count(body[offset:]) >= 150:
                    eligible.append(boundary)
        if eligible:
            high = eligible
    if not high:
        return ()
    indexes = sorted({0, len(high) // 2, len(high) - 1})
    return tuple(high[index] for index in indexes)


def _selection_for(
    chapter_number: int,
    boundaries: Iterable[ManifestBoundary],
    body: str | None = None,
) -> list[tuple[ManifestBoundary, str, str]]:
    selected: list[tuple[ManifestBoundary, str, str]] = []
    boundary_list = list(boundaries)
    for boundary in boundary_list:
        if boundary.confidence == "low":
            selected.append(
                (
                    boundary,
                    "low",
                    boundary.note or "The manifest marks this boundary low confidence.",
                )
            )
        elif boundary.confidence == "medium":
            selected.append(
                (
                    boundary,
                    "medium",
                    boundary.note
                    or "The manifest marks this boundary medium confidence.",
                )
            )

    if chapter_number in STRUCTURALLY_UNUSUAL_CHAPTERS:
        samples = _high_samples(boundary_list, body=body)
        sample_ids = {boundary.entry_id for boundary in samples}
        for boundary in boundary_list:
            if boundary.entry_id in sample_ids:
                selected.append(
                    (
                        boundary,
                        "high-sample",
                        "Confidence is high; included as a deterministic first/middle/last eligible high-confidence sample from a structurally unusual chapter.",
                    )
                )
    return selected


def _structural_context(
    opening_text: str, before: str, after: str
) -> tuple[str, ...]:
    text = opening_text + before + after
    context: list[str] = []
    if "(" in text or ")" in text:
        context.append("top-level parenthetical annotation delimiters")
    if "<!-- kanripo-page" in text or "<pb:" in text:
        context.append("Kanripo page-marker comments")
    return tuple(context)


def _build_item(
    root: Path,
    top: dict[str, Any],
    boundary: ManifestBoundary,
    selection_kind: str,
    reason: str,
    review_status: str,
) -> ReviewItem:
    source_chapter = str(top["source_chapter"])
    source_path = _source_path(root, source_chapter)
    body = _source_body(source_path)
    positions = [
        match.start()
        for match in re.finditer(re.escape(boundary.opening_text), body)
    ]
    if len(positions) != 1:
        raise ValueError(
            f"{boundary.entry_id}: expected one exact anchor in {source_path}, "
            f"found {len(positions)}"
        )
    offset = positions[0]
    before = _context_before(body, offset)
    after = _context_after(body, offset)
    return ReviewItem(
        chapter_number=_chapter_number(top, source_path),
        chapter_id=str(top["chapter_id"]),
        chapter_heading=str(top["chapter_heading"]),
        source_chapter=source_chapter,
        entry_id=boundary.entry_id,
        ordinal=boundary.ordinal,
        confidence=boundary.confidence,
        opening_text=boundary.opening_text,
        source_normalized_line=boundary.source_normalized_line,
        source_line=boundary.source_line,
        source_page_marker=boundary.source_page_marker,
        review_status=review_status,
        reason=reason,
        context_before=before,
        context_after=after,
        before_han_count=_han_count(before),
        after_han_count=_han_count(after),
        structural_context=_structural_context(
            boundary.opening_text, before, after
        ),
        selection_kind=selection_kind,
    )


def collect_review_items(
    boundary_dir: Path = DEFAULT_BOUNDARY_DIR,
    root: Path = Path("."),
) -> tuple[ReviewItem, ...]:
    root = root.resolve()
    boundary_dir = boundary_dir if boundary_dir.is_absolute() else root / boundary_dir
    items: list[ReviewItem] = []
    for manifest_path in _manifest_paths(boundary_dir):
        top, boundaries, statuses = _parse_boundary_manifest(manifest_path)
        chapter_number = _chapter_number(top, manifest_path)
        source_body = _source_body(
            _source_path(root, str(top["source_chapter"]))
        )
        for boundary, selection_kind, reason in _selection_for(
            chapter_number, boundaries, body=source_body
        ):
            items.append(
                _build_item(
                    root,
                    top,
                    boundary,
                    selection_kind,
                    reason,
                    statuses.get(
                        boundary.entry_id, str(top.get("review_status", "unknown"))
                    ),
                )
            )

    priority = {"low": 0, "medium": 1, "high-sample": 2}
    return tuple(
        sorted(
            items,
            key=lambda item: (
                priority[item.selection_kind],
                item.chapter_number,
                item.ordinal,
            ),
        )
    )


def _fenced(lines: list[str], label: str, text: str) -> None:
    fence = _fence_for(text)
    lines.extend([label, "", f"{fence}text", text, fence, ""])


def _render_item(lines: list[str], item: ReviewItem) -> None:
    lines.extend(
        [
            f"#### {item.entry_id}",
            "",
            f"- chapter: `{item.chapter_id}` — `{item.chapter_heading}`",
            f"- ordinal: {item.ordinal}",
            f"- confidence: `{item.confidence}`",
            f"- current review_status: `{item.review_status}`",
            f"- source: `{item.source_chapter}`, normalized line {item.source_normalized_line}, source line {item.source_line}, page marker `{item.source_page_marker}`",
            f"- review reason: {item.reason}",
        ]
    )
    if item.selection_kind == "high-sample":
        lines.append(
            "- sampling rule: first, middle, and last eligible high-confidence boundaries with sufficient surrounding source context in this structurally unusual chapter"
        )
    lines.append("")
    _fenced(lines, "- exact proposed opening anchor:", item.opening_text)
    _fenced(
        lines,
        f"- exact source context immediately before boundary ({item.before_han_count} Chinese characters):",
        item.context_before,
    )
    _fenced(
        lines,
        f"- exact source context from boundary forward ({item.after_han_count} Chinese characters):",
        item.context_after,
    )
    if item.structural_context:
        lines.append(
            "- annotation/page-marker context: the excerpts above contain "
            + " and ".join(item.structural_context)
            + "; they are copied verbatim."
        )
    else:
        lines.append(
            "- annotation/page-marker context: no parenthetical annotation or Kanripo page-marker comment occurs in these selected excerpts."
        )
    availability: list[str] = []
    if item.before_han_count < 100:
        availability.append(
            f"only {item.before_han_count} Chinese characters are available before the boundary"
        )
    if item.after_han_count < 150:
        availability.append(
            f"only {item.after_han_count} Chinese characters are available from the boundary forward"
        )
    if availability:
        lines.append(
            "- context availability: "
            + "; ".join(availability)
            + "; the normalized chapter does not contain the full requested window."
        )
    lines.append("")


def _summary_rows(
    boundary_dir: Path, items: Iterable[ReviewItem]
) -> list[tuple[str, int, int, int, int]]:
    item_counts: dict[str, int] = {}
    for item in items:
        item_counts[item.chapter_id] = item_counts.get(item.chapter_id, 0) + 1

    rows: list[tuple[str, int, int, int, int]] = []
    for manifest_path in _manifest_paths(boundary_dir):
        top, boundaries, _statuses = _parse_boundary_manifest(manifest_path)
        counts = {"high": 0, "medium": 0, "low": 0}
        for boundary in boundaries:
            if boundary.confidence not in counts:
                raise ValueError(
                    f"unsupported confidence {boundary.confidence!r} in {manifest_path}"
                )
            counts[boundary.confidence] += 1
        chapter_id = str(top["chapter_id"])
        rows.append(
            (
                chapter_id,
                counts["high"],
                counts["medium"],
                counts["low"],
                item_counts.get(chapter_id, 0),
            )
        )
    return rows


def render_manual_review(
    boundary_dir: Path = DEFAULT_BOUNDARY_DIR,
    root: Path = Path("."),
) -> str:
    root = root.resolve()
    resolved_boundary_dir = (
        boundary_dir if boundary_dir.is_absolute() else root / boundary_dir
    )
    items = collect_review_items(resolved_boundary_dir, root=root)
    rows = _summary_rows(resolved_boundary_dir, items)
    lines = [
        "# Shishuo Xinyu human boundary review",
        "",
        "This review queue is generated from the existing boundary manifests and normalized chapter sources.  It does not change any boundary, source chapter, or entry output.",
        "",
        "Every medium- and low-confidence boundary is included.  For chapters 05, 08, 18, 19, and 25, the first, middle, and last eligible high-confidence boundaries are also included as deterministic structural samples.  Eligibility requires at least 100 Chinese characters before and 150 after the boundary when available.  The 06-yaliang reviewed manifest is retained and is not sampled.",
        "",
        "The source excerpts below are contiguous slices copied verbatim from the normalized chapter body.  Chinese-character counts exclude Markdown comments, punctuation, whitespace, and other non-Han characters.",
        "",
        "## Summary",
        "",
        "| chapter | high | medium | low | review items |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for chapter_id, high, medium, low, review_items in rows:
        lines.append(
            f"| {chapter_id} | {high} | {medium} | {low} | {review_items} |"
        )
    lines.extend(
        [
            "",
            f"Total review items: {len(items)}.",
            "",
            "## LOW confidence",
            "",
        ]
    )
    low_items = [item for item in items if item.selection_kind == "low"]
    medium_items = [item for item in items if item.selection_kind == "medium"]
    high_items = [item for item in items if item.selection_kind == "high-sample"]

    def render_group(group: Iterable[ReviewItem]) -> None:
        group_list = list(group)
        current_chapter: str | None = None
        for item in group_list:
            if item.chapter_id != current_chapter:
                lines.extend(
                    [f"### {item.chapter_id} — {item.chapter_heading}", ""]
                )
                current_chapter = item.chapter_id
            _render_item(lines, item)
        if not group_list:
            lines.extend(["None.", ""])

    render_group(low_items)
    lines.extend(["## MEDIUM confidence", ""])
    render_group(medium_items)
    lines.extend(
        [
            "## HIGH-confidence structural samples",
            "",
            "Only the deterministic eligible samples from chapters 05, 08, 18, 19, and 25 appear in this section.",
            "",
        ]
    )
    render_group(high_items)
    return "\n".join(lines)


def write_manual_review(
    boundary_dir: Path = DEFAULT_BOUNDARY_DIR,
    output_path: Path = DEFAULT_OUTPUT,
    root: Path = Path("."),
) -> tuple[ReviewItem, ...]:
    root = root.resolve()
    output_path = output_path if output_path.is_absolute() else root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_manual_review(boundary_dir=boundary_dir, root=root),
        encoding="utf-8",
    )
    return collect_review_items(boundary_dir=boundary_dir, root=root)


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundary-dir", type=Path, default=DEFAULT_BOUNDARY_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    items = write_manual_review(
        boundary_dir=args.boundary_dir,
        output_path=args.output,
        root=args.root,
    )
    counts = {"low": 0, "medium": 0, "high-sample": 0}
    for item in items:
        counts[item.selection_kind] += 1
    print(
        f"rendered {len(items)} review items; "
        f"low={counts['low']}; medium={counts['medium']}; "
        f"high-samples={counts['high-sample']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
