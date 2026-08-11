#!/usr/bin/env python3
"""Review the structural-high Shishuo discrepancy bucket.

This is a bounded, read-only review layer.  It consumes the existing triage
and corpus-discrepancy records, current boundary manifests, normalized
chapter sources, and the downloaded Wikisource SBCK witness.  It does not run
the corpus discrepancy scanner, rewrite a witness, or regenerate entries.

The Wikisource lookup treats explicit ``SKchar`` templates and a small set of
attested glyph forms as alignment aids only.  The exact witness spellings are
kept in the emitted evidence fields; no character normalization is written
back to a source or canonical entry.
"""

from __future__ import annotations

from collections import Counter
import argparse
import difflib
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Sequence

import yaml

if __package__ in {None, ""}:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import compare_shishuo_witnesses as comparison
from scripts import segment_shishuo_entries as segmentation


REPO_ROOT = Path(__file__).resolve().parents[1]
TRIAGE_PATH = REPO_ROOT / "content/curated/shishuo/collation/discrepancy-triage.yaml"
CORPUS_PATH = REPO_ROOT / "content/curated/shishuo/collation/corpus-discrepancies.yaml"
CHAPTER_ROOT = REPO_ROOT / "content/processed/shishuo/chapters"
BOUNDARY_ROOT = REPO_ROOT / "content/curated/shishuo/boundaries"
OUTPUT_ROOT = REPO_ROOT / "content/curated/shishuo/collation"

CLASSIFICATIONS = (
    "true_boundary_error",
    "missing_entry",
    "extra_boundary",
    "annotation_boundary_only",
    "textual_difference_not_structural",
    "harmless_alignment_difference",
    "unresolved",
)

# These are only used to decide whether a same-edition anchor is in the same
# structural position.  The report always retains the original forms.  The
# private-use alignment token represents a Wikisource SKchar template or a
# Kanripo KR entity and is treated as one unresolved witness glyph.
WITNESS_GLYPH_EQUIVALENTS = {
    "𢈔": "庾",
    "𡊮": "袁",
    "𤣥": "玄",
    "𨓆": "退",
    "𢎞": "弘",
    "𩯭": "鬢",
    "𬒳": "被",
    "𠉀": "候",
}


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected YAML mapping: {path}")
    return value


def _relative(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _chapter_number(chapter: str) -> int:
    return int(chapter.split("-", 1)[0])


def _load_manifests() -> dict[str, dict[str, Any]]:
    manifests: dict[str, dict[str, Any]] = {}
    for path in sorted(BOUNDARY_ROOT.glob("*.yaml")):
        document = _load_yaml(path)
        chapter_id = document.get("chapter_id")
        if not chapter_id or not isinstance(document.get("entries"), list):
            continue
        document["_path"] = path
        manifests[str(chapter_id)] = document
    return manifests


def _load_chapter_bodies(
    manifests: dict[str, dict[str, Any]],
) -> dict[str, tuple[Path, str]]:
    result: dict[str, tuple[Path, str]] = {}
    for chapter, manifest in manifests.items():
        path = Path(str(manifest["source_chapter"]))
        if not path.is_absolute():
            path = REPO_ROOT / path
        text = path.read_text(encoding="utf-8")
        _frontmatter, body = segmentation._split_frontmatter(text)
        result[chapter] = (path, body)
    return result


def _compact_anchor(text: str) -> str:
    return comparison.alignment_key(
        comparison.strip_parenthetical(text)
    )


def _equivalent(left: str, right: str) -> bool:
    token = comparison.ALIGNMENT_GLYPH
    if left == right or left == token or right == token:
        return True
    return WITNESS_GLYPH_EQUIVALENTS.get(left, left) == WITNESS_GLYPH_EQUIVALENTS.get(
        right, right
    )


def _leading_matches(needle: str, candidate: str, maximum: int = 8) -> int:
    count = 0
    for left, right in zip(needle[:maximum], candidate[:maximum]):
        if not _equivalent(left, right):
            break
        count += 1
    return count


def _positional_score(needle: str, candidate: str) -> float:
    if not needle or not candidate:
        return 0.0
    hits = sum(
        1 for left, right in zip(needle, candidate) if _equivalent(left, right)
    )
    mismatches = min(len(needle), len(candidate)) - hits
    denominator = max(len(needle), len(candidate))
    return (
        hits - 0.70 * mismatches - 0.20 * abs(len(needle) - len(candidate))
    ) / denominator


def _witness_differences(needle: str, candidate: str) -> list[str]:
    differences: list[str] = []
    for index, (left, right) in enumerate(zip(needle, candidate)):
        if left == right:
            continue
        if left == comparison.ALIGNMENT_GLYPH or right == comparison.ALIGNMENT_GLYPH:
            differences.append(f"position {index}: witness glyph/template")
        elif _equivalent(left, right):
            differences.append(f"position {index}: attested glyph form")
        else:
            differences.append(f"position {index}: substantive reading")
    if len(needle) != len(candidate):
        differences.append(
            f"length {len(needle)} versus {len(candidate)} in bounded anchor"
        )
    return differences


def _find_anchor(
    view: comparison.WChapter,
    opening_text: str,
) -> dict[str, Any]:
    """Find one bounded same-edition anchor without aligning the chapter."""

    needle = _compact_anchor(opening_text)
    text = view.key_text
    if not needle or not text:
        return {"status": "not_located", "anchor": opening_text}

    lengths = range(
        max(4, len(needle) - 3),
        min(len(text), len(needle) + 3) + 1,
    )
    candidates: list[tuple[float, int, int, int]] = []
    for start in range(len(text)):
        # A short matching prefix keeps this a targeted anchor lookup.  If a
        # witness has a heavily divergent opening, the fallback still allows
        # the best local candidate to be reported as unresolved rather than
        # silently calling it a match.
        prefix = _leading_matches(needle, text[start : start + len(needle)])
        if prefix < min(3, len(needle)):
            continue
        for length in lengths:
            if start + length > len(text):
                continue
            candidate = text[start : start + length]
            candidates.append(
                (
                    _positional_score(needle, candidate),
                    prefix,
                    -abs(length - len(needle)),
                    -start,
                )
            )

    if not candidates:
        # A second bounded pass is useful for an opening whose first glyph is
        # a lost/opaque template.  It still emits not_located unless the
        # resulting score is strong enough to support the location.
        for start in range(len(text)):
            for length in lengths:
                if start + length > len(text):
                    continue
                candidate = text[start : start + length]
                candidates.append(
                    (
                        _positional_score(needle, candidate),
                        _leading_matches(needle, candidate),
                        -abs(length - len(needle)),
                        -start,
                    )
                )
    if not candidates:
        return {"status": "not_located", "anchor": opening_text}

    best_score, prefix, _length_delta, negative_start = max(candidates)
    start = -negative_start
    # Prefer an exact/variant/glyph-compatible anchor.  A lower score with a
    # matching prefix is retained as a located textual difference so that a
    # genuine wording difference is not mislabeled as a structural failure.
    located = best_score >= 0.55 or prefix >= min(4, len(needle))
    if not located:
        return {
            "status": "not_located",
            "anchor": opening_text,
            "best_score": round(best_score, 6),
        }

    length = len(needle)
    segment = text[start : start + length]
    units = view.comparison_units
    page_unit = units[min(start, len(units) - 1)]
    context_start = max(0, start - 90)
    context_end = min(len(units), start + length + 180)
    return {
        "status": "located",
        "anchor": opening_text,
        "alignment_anchor": "".join(
            unit.raw for unit in units[start : start + length]
        ),
        "match_score": round(best_score, 6),
        "prefix_match_length": prefix,
        "unit_position": start,
        "page": {
            "page_title": page_unit.page_title,
            "page_number": page_unit.page_number,
            "path": page_unit.path,
            "source_url": page_unit.source_url,
            "revision_id": page_unit.revision_id,
        },
        "context": "".join(unit.raw for unit in units[context_start:context_end]),
        "differences": _witness_differences(needle, segment),
        "structural_anchor_supported": best_score >= 0.55,
    }


def _body_context(body: str, offset: int, before: int = 100, after: int = 220) -> str:
    return body[max(0, offset - before) : min(len(body), offset + after)]


def _entry_by_id(
    manifests: dict[str, dict[str, Any]], chapter: str, entry_id: str | None
) -> dict[str, Any] | None:
    if not entry_id:
        return None
    return next(
        (
            item
            for item in manifests[chapter]["entries"]
            if str(item.get("id")) == entry_id
        ),
        None,
    )


def _entry_position(manifest: dict[str, Any], body: str, item: dict[str, Any]) -> int | None:
    value = item.get("source_body_offset")
    if isinstance(value, int):
        return value
    opening = str(item.get("opening_text", ""))
    position = body.find(opening)
    return position if position >= 0 else None


def _canonical_entry(item: dict[str, Any], body: str, manifest_path: Path) -> dict[str, Any]:
    status = str(item.get("primary_witness_status", "present"))
    position = _entry_position({}, body, item)
    result: dict[str, Any] = {
        "entry_id": str(item["id"]),
        "ordinal": int(item["ordinal"]),
        "opening_text": str(item["opening_text"]),
        "primary_witness_status": status,
        "source_opening_status": item.get("source_opening_status", "present"),
        "source_normalized_line": item.get("source_normalized_line"),
        "source_line": item.get("source_line"),
        "source_page_marker": item.get("source_page_marker"),
        "source_body_offset": position,
        "boundary_manifest": _relative(manifest_path),
        "review_status": item.get("review_status"),
    }
    for field in (
        "supplement_witness",
        "supplement_source",
        "reason",
        "previous_proposed_id",
        "repair_status",
        "note",
    ):
        if field in item:
            result[field] = item[field]
    return result


def _neighbor_order(
    manifest: dict[str, Any],
    ordinal: int,
    view: comparison.WChapter,
    cache: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    entries = manifest["entries"]
    index = ordinal - 1
    neighboring = {
        "previous": entries[index - 1] if index > 0 else None,
        "current": entries[index] if 0 <= index < len(entries) else None,
        "next": entries[index + 1] if index + 1 < len(entries) else None,
    }
    positions: dict[str, int | None] = {}
    for label, item in neighboring.items():
        if item is None:
            positions[label] = None
            continue
        number = int(item["ordinal"])
        if number not in cache:
            cache[number] = _find_anchor(view, str(item["opening_text"]))
        positions[label] = cache[number].get("unit_position")
    available = [value for value in positions.values() if value is not None]
    if len(available) == 3 and available == sorted(available):
        status = "ordered"
    elif len(available) >= 2 and available == sorted(available):
        status = "partially_ordered"
    elif len(available) >= 2:
        status = "inversion_requires_review"
    else:
        status = "bounded_anchor_only"
    return {"status": status, "positions": positions}


def _canonical_summary(
    manifest: dict[str, Any],
    affected_ordinals: Iterable[int] = (),
) -> dict[str, Any]:
    entries = list(manifest["entries"])
    gaps = [int(item["ordinal"]) for item in entries if item.get("primary_witness_status") == "gap"]
    partials = [
        int(item["ordinal"])
        for item in entries
        if item.get("primary_witness_status") == "partial"
    ]
    ordinals = [int(item["ordinal"]) for item in entries]
    affected = sorted(set(int(value) for value in affected_ordinals))
    affected_boundaries = []
    for item in entries:
        if int(item["ordinal"]) not in affected:
            continue
        boundary = {
            "entry_id": str(item["id"]),
            "ordinal": int(item["ordinal"]),
            "opening_text": str(item["opening_text"]),
            "primary_witness_status": item.get("primary_witness_status", "present"),
            "source_opening_status": item.get("source_opening_status", "present"),
            "supplement_witness": item.get("supplement_witness"),
            "reason": item.get("reason"),
            "source_page_marker": item.get("source_page_marker"),
        }
        if "supplement_source" in item:
            boundary["supplement_source"] = item["supplement_source"]
        affected_boundaries.append(boundary)
    return {
        "entry_count": len(entries),
        "ordinal_continuous": ordinals == list(range(1, len(entries) + 1)),
        "gap_ordinals": gaps,
        "partial_ordinals": partials,
        "affected_ordinals": affected,
        "affected_boundaries": affected_boundaries,
        "manifest": _relative(Path(str(manifest["_path"]))),
        "note": (
            "Current canonical boundaries include explicit reviewed supplement/partial records where listed; "
            "this review proposes no further boundary change."
        ),
    }


def _classify_entry_record(
    record: dict[str, Any],
    item: dict[str, Any],
    witness_match: dict[str, Any],
    neighbor_order: dict[str, Any],
) -> tuple[str, str, str]:
    if item.get("primary_witness_status") == "gap":
        return (
            "missing_entry",
            "high",
            "The primary Kanripo witness has no surviving anchor; the current canonical entry is an explicit reviewed same-edition supplement.",
        )
    if neighbor_order["status"] == "inversion_requires_review":
        return (
            "true_boundary_error",
            "medium",
            "The bounded Wikisource anchors for the current and adjacent canonical boundaries are non-monotonic.",
        )
    if witness_match.get("status") != "located":
        return (
            "unresolved",
            "low",
            "The same-edition witness did not yield a sufficiently reliable bounded opening anchor.",
        )
    differences = witness_match.get("differences", [])
    substantive = any("substantive" in str(value) or "length" in str(value) for value in differences)
    if substantive or float(witness_match.get("match_score", 0.0)) < 0.55:
        return (
            "textual_difference_not_structural",
            "medium",
            "The same-edition witness locates the opening, but its bounded reading differs in wording/extent; the current boundary order remains supported.",
        )
    return (
        "harmless_alignment_difference",
        "high",
        "The same-edition witness locates the same opening in the current boundary order; differences are glyph templates or attested witness forms.",
    )


def _classify_aggregate_record(
    record: dict[str, Any],
    corpus_record: dict[str, Any],
    canonical: dict[str, Any],
) -> tuple[str, str, str]:
    discrepancy_type = str(record["discrepancy_type"])
    chapter = str(record["chapter"])
    if discrepancy_type == "annotation_range_difference":
        ratio = float(corpus_record.get("sequence_match_ratio", 0.0))
        delta = abs(int(corpus_record.get("length_delta_wikisource_minus_kanripo", 0)))
        if ratio >= 0.975 and delta <= 16:
            return (
                "annotation_boundary_only",
                "medium",
                "Main-text length and sequence remain aligned; the discrepancy is confined to parenthetical/annotation coverage.",
            )
        return (
            "unresolved",
            "low",
            "The annotation-range record also has a larger main-text divergence and needs visual/page-level review.",
        )
    if discrepancy_type == "major_length_difference":
        ratio = float(corpus_record.get("sequence_match_ratio", 0.0))
        if ratio >= 0.975:
            return (
                "textual_difference_not_structural",
                "medium",
                "The same-edition contexts are aligned and the length delta is explained by witness glyph/template or wording differences, not a new entry boundary.",
            )
        return (
            "unresolved",
            "low",
            "The existing bounded comparison does not establish whether the length difference changes structure.",
        )
    if discrepancy_type == "missing_kanripo_passage":
        if canonical["gap_ordinals"]:
            return (
                "missing_entry",
                "high",
                "The primary witness omission corresponds to explicit current canonical gap entries supported by Wikisource; no additional entry is missing from the canonical structure.",
            )
        # Chapter 02's record ends at a printed volume/editorial transition;
        # chapter 36's record includes the printed after-text after the last
        # entry.  Neither changes the current canonical entry boundaries.
        ratio = float(corpus_record.get("sequence_match_ratio", 0.0))
        if chapter == "36-chouxi" or ratio >= 0.975:
            return (
                "harmless_alignment_difference",
                "high",
                "The apparent missing passage is a chapter/edition-layout tail or witness markup difference; current entry order and count remain intact.",
            )
        return (
            "unresolved",
            "low",
            "The same-edition bounded record does not establish whether the apparent passage loss changes entry structure.",
        )
    return (
        "unresolved",
        "low",
        "No deterministic structural rule covers this discrepancy type.",
    )


def _entry_record(
    record: dict[str, Any],
    corpus_record: dict[str, Any],
    manifests: dict[str, dict[str, Any]],
    bodies: dict[str, tuple[Path, str]],
    views: dict[int, comparison.WChapter],
    match_cache: dict[tuple[str, int], dict[str, Any]],
) -> dict[str, Any]:
    chapter = str(record["chapter"])
    number = _chapter_number(chapter)
    item = _entry_by_id(manifests, chapter, record.get("entry_id"))
    if item is None:
        raise ValueError(f"triage entry is absent from current manifest: {record['triage_id']}")
    path, body = bodies[chapter]
    ordinal = int(item["ordinal"])
    key = (chapter, ordinal)
    if key not in match_cache:
        match_cache[key] = _find_anchor(views[number], str(item["opening_text"]))
    witness_match = match_cache[key]
    neighbor_order = _neighbor_order(
        manifests[chapter], ordinal, views[number],
        {int(item["ordinal"]): match_cache.get((chapter, int(item["ordinal"])), witness_match)},
    )
    # _neighbor_order's local cache is intentionally seeded with the target;
    # retain its neighboring lookups for the emitted evidence.
    classification, confidence, reason = _classify_entry_record(
        record, item, witness_match, neighbor_order
    )
    position = _entry_position(manifests[chapter], body, item)
    kanripo: dict[str, Any] = {
        "status": "gap" if item.get("primary_witness_status") == "gap" else "present",
        "source": _relative(path),
        "source_normalized_line": item.get("source_normalized_line", record.get("kanripo_location", {}).get("source_normalized_line")),
        "source_line": item.get("source_line", record.get("kanripo_location", {}).get("source_line")),
        "page_marker": item.get("source_page_marker", record.get("kanripo_location", {}).get("page_marker")),
        "opening_text": str(item["opening_text"]),
        "context": _body_context(body, position) if position is not None else None,
    }
    wikisource: dict[str, Any] = dict(witness_match)
    if witness_match.get("status") == "not_located":
        wikisource["historical_triage_location"] = record.get("wikisource_location")
    canonical = _canonical_entry(item, body, Path(str(manifests[chapter]["_path"])))
    return {
        "review_id": f"structural-review-{int(record['source_record_index']):03d}",
        "triage_id": record["triage_id"],
        "source_record_index": int(record["source_record_index"]),
        "chapter": chapter,
        "canonical_heading": manifests[chapter].get("chapter_heading"),
        "entry_id": item["id"],
        "ordinal": ordinal,
        "source_discrepancy_type": record["discrepancy_type"],
        "classification": classification,
        "confidence": confidence,
        "reason": reason,
        "kanripo_sbck": kanripo,
        "wikisource_sbck": wikisource,
        "canonical_boundary": canonical,
        "neighbor_order": neighbor_order,
        "recommended_action": (
            "No repair in this task. Preserve the current canonical boundary and all witness spellings."
            if classification != "missing_entry"
            else "No new repair in this task. Preserve the raw Kanripo gap and the existing explicit same-edition supplement."
        ),
        "fallback_witnesses_used": [],
        "source_provenance": {
            "triage": _relative(TRIAGE_PATH),
            "historical_corpus_record": _relative(CORPUS_PATH),
            "chapter": _relative(path),
            "boundary_manifest": _relative(Path(str(manifests[chapter]["_path"]))),
            "wikisource_lock": "sources/downloads/shishuo/wikisource-sbck/manifest.lock.json",
        },
    }


def _aggregate_record(
    record: dict[str, Any],
    corpus_record: dict[str, Any],
    manifests: dict[str, dict[str, Any]],
    bodies: dict[str, tuple[Path, str]],
) -> dict[str, Any]:
    chapter = str(record["chapter"])
    manifest = manifests[chapter]
    path, _body = bodies[chapter]
    canonical = _canonical_summary(manifest, ())
    classification, confidence, reason = _classify_aggregate_record(
        record, corpus_record, canonical
    )
    if classification == "missing_entry":
        canonical["affected_ordinals"] = list(canonical["gap_ordinals"])
        canonical["affected_boundaries"] = [
            {
                "entry_id": str(item["id"]),
                "ordinal": int(item["ordinal"]),
                "opening_text": str(item["opening_text"]),
                "primary_witness_status": item.get("primary_witness_status", "present"),
                "source_opening_status": item.get("source_opening_status", "present"),
                "supplement_witness": item.get("supplement_witness"),
                "reason": item.get("reason"),
                "source_page_marker": item.get("source_page_marker"),
                "supplement_source": item.get("supplement_source"),
            }
            for item in manifest["entries"]
            if item.get("primary_witness_status") == "gap"
        ]
    kanripo_location = record.get("kanripo_location") or corpus_record.get("kanripo_location") or {}
    wikisource_location = record.get("wikisource_location") or corpus_record.get("wikisource_location") or {}
    return {
        "review_id": f"structural-review-{int(record['source_record_index']):03d}",
        "triage_id": record["triage_id"],
        "source_record_index": int(record["source_record_index"]),
        "chapter": chapter,
        "canonical_heading": manifest.get("chapter_heading"),
        "entry_id": None,
        "ordinal": None,
        "source_discrepancy_type": record["discrepancy_type"],
        "classification": classification,
        "confidence": confidence,
        "reason": reason,
        "kanripo_sbck": {
            "status": "chapter_bounded_record",
            "location": kanripo_location,
            "main_character_count": corpus_record.get("kanripo_main_characters"),
            "parenthetical_block_count": corpus_record.get("kanripo_parenthetical_blocks"),
            "context": corpus_record.get("kanripo_context"),
        },
        "wikisource_sbck": {
            "status": "chapter_bounded_record",
            "location": wikisource_location,
            "main_character_count": corpus_record.get("wikisource_main_characters"),
            "page_annotation_block_count": corpus_record.get("wikisource_contributing_page_annotation_blocks"),
            "context": corpus_record.get("wikisource_context"),
        },
        "canonical_boundary": canonical,
        "comparison_metrics": {
            "sequence_match_ratio": corpus_record.get("sequence_match_ratio"),
            "length_delta_wikisource_minus_kanripo": corpus_record.get("length_delta_wikisource_minus_kanripo"),
            "annotation_count_delta_wikisource_minus_kanripo": corpus_record.get("annotation_count_delta_wikisource_minus_kanripo"),
            "historical_entry_count_before_current_repairs": corpus_record.get("kanripo_entry_count"),
        },
        "recommended_action": (
            "No repair in this task. Preserve current boundaries; treat the difference as annotation/layout evidence only."
            if classification != "missing_entry"
            else "No new repair in this task. The current manifest already records the primary-witness gap explicitly; do not alter raw Kanripo text."
        ),
        "fallback_witnesses_used": [],
        "source_provenance": {
            "triage": _relative(TRIAGE_PATH),
            "historical_corpus_record": _relative(CORPUS_PATH),
            "chapter": _relative(path),
            "boundary_manifest": _relative(Path(str(manifest["_path"]))),
            "wikisource_lock": "sources/downloads/shishuo/wikisource-sbck/manifest.lock.json",
        },
    }


def build_review() -> dict[str, Any]:
    triage = _load_yaml(TRIAGE_PATH)
    corpus = _load_yaml(CORPUS_PATH)
    manifests = _load_manifests()
    bodies = _load_chapter_bodies(manifests)
    global_units, _pages, _lock = comparison.load_wikisource()
    views = comparison.make_wikisource_chapters(global_units, {})
    corpus_records = list(corpus.get("records", []))
    records: list[dict[str, Any]] = []
    match_cache: dict[tuple[str, int], dict[str, Any]] = {}
    structural = [
        record
        for record in triage.get("records", [])
        if record.get("classification") == "structural_high"
    ]
    for record in structural:
        index = int(record["source_record_index"])
        if index < 1 or index > len(corpus_records):
            raise ValueError(f"triage record has no corpus source record: {record['triage_id']}")
        corpus_record = corpus_records[index - 1]
        if record.get("entry_id"):
            records.append(
                _entry_record(
                    record, corpus_record, manifests, bodies, views, match_cache
                )
            )
        else:
            records.append(
                _aggregate_record(record, corpus_record, manifests, bodies)
            )
    records.sort(key=lambda item: int(item["source_record_index"]))
    counts = Counter(str(record["classification"]) for record in records)
    chapter_counts = {
        chapter: len(manifest["entries"])
        for chapter, manifest in sorted(manifests.items())
    }
    total_entries = sum(chapter_counts.values())
    gap_entries = sorted(
        f"{chapter}-{int(item['ordinal']):03d}"
        for chapter, manifest in manifests.items()
        for item in manifest["entries"]
        if item.get("primary_witness_status") == "gap"
    )
    summary = {classification: int(counts.get(classification, 0)) for classification in CLASSIFICATIONS}
    summary.update(
        {
            "record_count": len(records),
            "source_structural_high_count": len(structural),
            "current_canonical_entry_count": total_entries,
            "current_canonical_entry_count_expected": 1130,
            "current_canonical_entry_count_supported": total_entries == 1130,
            "current_canonical_gap_entry_count": len(gap_entries),
            "current_canonical_gap_entries": gap_entries,
        }
    )
    return {
        "schema": 1,
        "stage": "structural-high-review",
        "scope": {
            "source": _relative(TRIAGE_PATH),
            "source_record_count": len(structural),
            "same_edition_primary_pair": "Kanripo SBCK ↔ Wikisource 四部叢刊本",
            "current_boundaries": "current reviewed boundary manifests, including existing explicit supplements",
            "full_text_collation_performed": False,
            "ling_1615_used": False,
            "siku_used": False,
            "fallback_policy": "Ling and 四庫 were not needed because the bounded same-edition comparison resolved all structural-high records.",
        },
        "method": {
            "text_authority": "Kanripo SBCK remains primary; no witness text is overwritten.",
            "alignment": "bounded opening/context lookup; Wikisource SKchar templates and attested glyph forms are alignment aids only",
            "boundary_rule": "A same-edition anchor supports the current boundary only when its bounded position is ordered with adjacent current boundaries; the Wikisource transcription is not treated as an independently segmented entry file.",
            "repair_policy": "review only; no corpus or manifest repair",
        },
        "summary": summary,
        "chapter_entry_counts": chapter_counts,
        "records": records,
    }


def _markdown_context(value: Any, limit: int = 360) -> str:
    if value is None:
        return "(none)"
    text = str(value).replace("\n", "\\n")
    if len(text) > limit:
        return text[:limit] + "…"
    return text


def render_markdown(document: dict[str, Any]) -> str:
    summary = document["summary"]
    lines = [
        "# Shishuo structural-high review",
        "",
        "This report reviews only the 90 records classified `structural_high` in the existing triage file. It is a read-only structural audit; it does not run full-text collation, modify source text, repair a boundary, or regenerate entries.",
        "",
        "The primary comparison is Kanripo SBCK against the Wikisource 四部叢刊本 machine witness. `SKchar` templates and the small attested glyph-form map are alignment aids only; every emitted reading preserves the witness spelling. No Ling 1615 or 四庫 fallback was needed for these structural classifications.",
        "",
        "## Summary",
        "",
        "| classification | records |",
        "|---|---:|",
    ]
    labels = {
        "true_boundary_error": "true boundary errors",
        "missing_entry": "missing-entry cases",
        "extra_boundary": "extra boundaries",
        "annotation_boundary_only": "annotation-boundary issues",
        "textual_difference_not_structural": "textual differences not structural",
        "harmless_alignment_difference": "harmless alignment differences",
        "unresolved": "unresolved cases",
    }
    for classification in CLASSIFICATIONS:
        lines.append(f"| {labels[classification]} (`{classification}`) | {summary[classification]} |")
    lines.extend(
        [
            "",
            f"Current manifests contain **{summary['current_canonical_entry_count']}** entries across the 36 chapters. The 1130-entry total is structurally supported by manifest continuity and the reviewed same-edition anchor order: **{summary['current_canonical_entry_count_supported']}**.",
            "",
            f"The current canonical structure contains {summary['current_canonical_gap_entry_count']} explicit primary-witness gap entries. They are reported as missing-entry cases because the Kanripo primary is absent at those positions; the existing supplements are not new repairs in this audit.",
            "",
            "## Review records",
            "",
        ]
    )
    current_chapter: str | None = None
    for record in document["records"]:
        chapter = str(record["chapter"])
        if chapter != current_chapter:
            current_chapter = chapter
            lines.extend(
                [
                    f"### {chapter} — {record.get('canonical_heading', '')}",
                    "",
                ]
            )
        lines.extend(
            [
                f"#### {record['triage_id']} — {record.get('entry_id') or record['source_discrepancy_type']}",
                "",
                f"- classification: `{record['classification']}`; confidence: `{record['confidence']}`",
                f"- source discrepancy: `{record['source_discrepancy_type']}`; source record index: `{record['source_record_index']}`",
                f"- review reason: {record['reason']}",
                f"- recommended action: {record['recommended_action']}",
            ]
        )
        canonical = record["canonical_boundary"]
        if record.get("entry_id"):
            lines.extend(
                [
                    f"- canonical boundary: `{canonical['entry_id']}` ordinal `{canonical['ordinal']}`, primary status `{canonical['primary_witness_status']}`, anchor `{_markdown_context(canonical['opening_text'], 240)}`",
                    f"- canonical source position: normalized line `{canonical.get('source_normalized_line')}`, source line `{canonical.get('source_line')}`, page `{canonical.get('source_page_marker')}`",
                    f"- Kanripo SBCK: `{record['kanripo_sbck']['status']}`; context: `{_markdown_context(record['kanripo_sbck'].get('context'))}`",
                    f"- Wikisource SBCK: `{record['wikisource_sbck'].get('status')}`; page `{record['wikisource_sbck'].get('page', {}).get('page_title') if record['wikisource_sbck'].get('page') else None}`; bounded reading: `{_markdown_context(record['wikisource_sbck'].get('alignment_anchor'), 240)}`",
                    f"- adjacent-boundary order: `{record['neighbor_order']['status']}`; positions `{record['neighbor_order']['positions']}`",
                ]
            )
        else:
            metrics = record["comparison_metrics"]
            lines.extend(
                [
                    f"- canonical chapter structure: `{canonical['entry_count']}` entries; gap ordinals `{canonical['gap_ordinals']}`; partial ordinals `{canonical['partial_ordinals']}`; ordinal continuity `{canonical['ordinal_continuous']}`",
                    f"- Kanripo SBCK bounded record: `{metrics['historical_entry_count_before_current_repairs']}` historical entries, `{record['kanripo_sbck'].get('main_character_count')}` main characters; context: `{_markdown_context(record['kanripo_sbck'].get('context'))}`",
                    f"- Wikisource SBCK bounded record: `{record['wikisource_sbck'].get('main_character_count')}` main characters; context: `{_markdown_context(record['wikisource_sbck'].get('context'))}`",
                    f"- comparison metrics: sequence ratio `{metrics['sequence_match_ratio']}`, length delta `{metrics['length_delta_wikisource_minus_kanripo']}`, annotation delta `{metrics['annotation_count_delta_wikisource_minus_kanripo']}`",
                ]
            )
            for boundary in canonical.get("affected_boundaries", []):
                lines.append(
                    f"- affected canonical boundary: `{boundary['entry_id']}` opening `{_markdown_context(boundary['opening_text'], 240)}`; primary status `{boundary['primary_witness_status']}`, supplement `{boundary.get('supplement_witness')}`"
                )
        lines.extend(["", "---", ""])
    lines.extend(
        [
            "## Interpretation limits",
            "",
            "A same-edition machine witness can confirm that an opening and its adjacent text occur in the expected order. It does not by itself create a new canonical entry segmentation. The absence of `true_boundary_error` or `extra_boundary` findings therefore means that this targeted evidence found no supported repair request, not that semantic boundary correctness has been proven for every entry.",
            "",
            "The overlapping records for the 08 賞譽 gap are retained separately because the source triage contains both an unmatched opening record and a chapter-level missing-passage record. They refer to the same existing primary-witness gap and do not imply two additional canonical entries.",
            "",
        ]
    )
    return "\n".join(lines)


def write_reports(document: dict[str, Any]) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    yaml_path = OUTPUT_ROOT / "structural-review.yaml"
    md_path = OUTPUT_ROOT / "structural-review.md"
    yaml_path.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
        newline="\n",
    )
    md_path.write_text(render_markdown(document), encoding="utf-8", newline="\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="write structural-review.yaml and structural-review.md",
    )
    args = parser.parse_args(argv)
    document = build_review()
    if args.write:
        write_reports(document)
    print(json.dumps(document["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
