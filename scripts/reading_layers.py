#!/usr/bin/env python3
"""Shared helpers for the reviewed WP1 reading layer."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unicodedata
from typing import Any, Mapping

try:
    from .build_six_person_pilot import parse_shishuo_sections
except ImportError:  # pragma: no cover - direct script imports
    from build_six_person_pilot import parse_shishuo_sections


PUNCTUATION_RELATIVE_PATH = "data/annotation/wp1-punctuation.json"

READER_LABELS = {
    "people_section": "人物",
    "resolved_mentions_heading": "文中已解析的稱謂",
    "alias_hint": "查看稱謂",
    "resolved_alias_label": "本則中已解析的稱謂",
    "annotation_label": "劉孝標注",
    "evidence_heading": "證據與出處",
    "evidence_intro": "以下資訊來自已驗證的 WP1 靜態資料；artifact 是頁面所引用的派生檔案，source provenance 保留其上游見證資訊。",
    "empty_alias": "—",
    "relation_section": "人物關係",
    "direct_relation_label": "已審核的直接關係",
    "derived_relation_label": "推得關係",
    "derived_relation_note": "由關係鏈推得",
    "relation_evidence_toggle": "查看關係依據",
    "relation_evidence_heading": "關係依據",
    "no_direct_relations": "目前尚無已審核的人物關係。",
    "focused_person_label": "當前人物",
    "back_label": "返回",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_sections(entry_path: Path) -> dict[str, str]:
    sections = parse_shishuo_sections(entry_path.read_text(encoding="utf-8"))
    result: dict[str, str] = {}
    for section, text, metadata in sections:
        if section == "main_text":
            result[section] = text.rstrip("\n")
        elif section == "liu_annotation":
            annotation_id = str(metadata.get("annotation_id", "annotation-001"))
            result[section] = text.rstrip("\n")
            result.setdefault("liu_annotation_id", annotation_id)
    if "main_text" not in result or "liu_annotation" not in result:
        raise ValueError(f"canonical entry lacks main text or Liu annotation: {entry_path}")
    return result


def canonical_reading_sections(entry_path: Path) -> dict[str, str]:
    """Return the canonical main section and any available annotation.

    CRL1 only requires main-text reading coverage.  The older WP1 helper
    above intentionally remains strict because its reviewed sample includes a
    Liu Xiaobiao annotation record.
    """

    result: dict[str, str] = {}
    for section, text, metadata in parse_shishuo_sections(entry_path.read_text(encoding="utf-8")):
        if section == "main_text":
            result[section] = text.rstrip("\n")
        elif section == "liu_annotation":
            result[section] = text.rstrip("\n")
            result.setdefault("liu_annotation_id", str(metadata.get("annotation_id", "annotation-001")))
    if "main_text" not in result:
        raise ValueError(f"canonical entry lacks main text: {entry_path}")
    return result


def strip_display_punctuation(text: str) -> str:
    """Remove Unicode punctuation and display whitespace, preserving characters."""
    return "".join(
        character
        for character in text
        if not character.isspace() and not unicodedata.category(character).startswith("P")
    )


def validate_punctuation_round_trip(
    record: Mapping[str, Any],
    canonical: Mapping[str, str],
    *,
    section_names: tuple[str, ...] = ("main_text", "liu_annotation"),
    allow_missing_punctuated: bool = False,
) -> list[str]:
    errors: list[str] = []
    sections = record.get("sections")
    if not isinstance(sections, Mapping):
        return [f"{record.get('id')}: sections is not an object"]
    for section_name in section_names:
        section = sections.get(section_name)
        if not isinstance(section, Mapping):
            errors.append(f"{record.get('id')}.{section_name}: section is not an object")
            continue
        actual_canonical = canonical.get(section_name)
        recorded_canonical = section.get("canonical_text")
        punctuated = section.get("punctuated_text")
        if recorded_canonical != actual_canonical:
            errors.append(
                f"{record.get('id')}.{section_name}: canonical_text does not match the entry"
            )
        if punctuated is None and allow_missing_punctuated:
            continue
        if not isinstance(punctuated, str) or not punctuated:
            errors.append(f"{record.get('id')}.{section_name}: punctuated_text is empty")
            continue
        if isinstance(actual_canonical, str) and strip_display_punctuation(punctuated) != strip_display_punctuation(actual_canonical):
            errors.append(
                f"{record.get('id')}.{section_name}: punctuation round-trip changes the canonical character sequence"
            )
    return errors


def _display_pair(text: str, converter: Any) -> dict[str, str]:
    return {"original": text, "simplified": converter.convert(text)}


def _build_person_display(people: Any, converter: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if not isinstance(people, (list, tuple)):
        return result
    for person in people:
        if not isinstance(person, Mapping) or not isinstance(person.get("id"), str):
            continue
        aliases = []
        for alias in person.get("aliases", []):
            if not isinstance(alias, Mapping) or not isinstance(alias.get("surface"), str):
                continue
            aliases.append(
                {
                    "surface": _display_pair(alias["surface"], converter),
                    "alias_type": alias.get("alias_type", ""),
                }
            )
        result[person["id"]] = {
            "name": _display_pair(str(person.get("canonical_name", "")), converter),
            "aliases": aliases,
        }
    return result


def _build_mention_display(mentions: Any, converter: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if not isinstance(mentions, (list, tuple)):
        return result
    for mention in mentions:
        if not isinstance(mention, Mapping) or not isinstance(mention.get("id"), str):
            continue
        surface = mention.get("surface")
        if isinstance(surface, str):
            result[mention["id"]] = {"surface": _display_pair(surface, converter)}
    return result


def _build_source_display(sources: Any, converter: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if not isinstance(sources, (list, tuple)):
        return result
    for source in sources:
        if not isinstance(source, Mapping) or not isinstance(source.get("id"), str):
            continue
        result[source["id"]] = {
            "work": _display_pair(str(source.get("work", "")), converter),
            "edition": _display_pair(str(source.get("edition", "")), converter),
        }
    return result


def _build_relation_display(relations: Any, converter: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if not isinstance(relations, (list, tuple)):
        return result
    for relation in relations:
        if not isinstance(relation, Mapping) or not isinstance(relation.get("id"), str):
            continue

        def role_pair(key: str) -> dict[str, str] | None:
            value = relation.get(key)
            return _display_pair(value, converter) if isinstance(value, str) else None

        result[relation["id"]] = {
            "label": _display_pair(str(relation.get("label", "")), converter),
            "role_a": role_pair("role_a"),
            "role_b": role_pair("role_b"),
        }
    return result


def _reader_quote(quote: str) -> str:
    """Remove presentation-only MediaWiki comments from a reader quotation."""
    return re.sub(r"<!--.*?-->", "", quote, flags=re.DOTALL).strip()


def _build_evidence_display(evidence: Any, converter: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if not isinstance(evidence, (list, tuple)):
        return result
    for item in evidence:
        if not isinstance(item, Mapping) or not isinstance(item.get("id"), str):
            continue
        quote = item.get("quote")
        if isinstance(quote, str):
            result[item["id"]] = _display_pair(_reader_quote(quote), converter)
    return result


def _is_display_ignored(character: str) -> bool:
    """Return whether a character is presentation-only for alignment.

    The canonical entry may retain source line breaks and top-level annotation
    delimiters.  Reading punctuation uses the same round-trip rule as the
    punctuation validator: Unicode punctuation and whitespace are ignored
    while historical characters remain exact.
    """

    return character.isspace() or unicodedata.category(character).startswith("P")


def _significant_positions(text: str) -> list[tuple[str, int]]:
    return [
        (character, index)
        for index, character in enumerate(text)
        if not _is_display_ignored(character)
    ]


def _display_boundaries(canonical: str, displayed: str) -> tuple[list[int], list[int], list[str]]:
    """Map raw canonical character offsets to displayed-text boundaries.

    Offsets in the Mention records are offsets into the normalized canonical
    section, which can contain source line breaks and annotation delimiters.
    The displayed reading can contain a different set of punctuation and
    whitespace.  Matching the significant character sequences gives an exact,
    variant-preserving mapping without assuming equal string lengths.
    """

    canonical_positions = _significant_positions(canonical)
    displayed_positions = _significant_positions(displayed)
    canonical_text = "".join(character for character, _ in canonical_positions)
    displayed_text = "".join(character for character, _ in displayed_positions)
    if canonical_text != displayed_text:
        raise ValueError("canonical/display text character sequences do not align")

    raw_to_logical: list[int] = [0] * (len(canonical) + 1)
    logical = 0
    for raw_index in range(len(canonical) + 1):
        raw_to_logical[raw_index] = logical
        if raw_index < len(canonical) and not _is_display_ignored(canonical[raw_index]):
            logical += 1

    logical_to_display_start: list[int] = [0] * (len(displayed_positions) + 1)
    for logical_index, (_character, display_index) in enumerate(displayed_positions):
        logical_to_display_start[logical_index] = display_index
    logical_to_display_start[len(displayed_positions)] = len(displayed)

    logical_to_display_end: list[int] = [0] * (len(displayed_positions) + 1)
    logical_to_display_end[0] = 0
    for logical_index, (_character, display_index) in enumerate(displayed_positions, start=1):
        logical_to_display_end[logical_index] = display_index + 1

    start_boundaries = [0] * (len(canonical) + 1)
    end_boundaries = [0] * (len(canonical) + 1)
    for raw_index, logical_index in enumerate(raw_to_logical):
        start_boundaries[raw_index] = logical_to_display_start[logical_index]
        end_boundaries[raw_index] = logical_to_display_end[logical_index]
    return start_boundaries, end_boundaries, [character for character, _ in canonical_positions]


def _mention_id(mention: Mapping[str, Any]) -> str | None:
    value = mention.get("mention_id", mention.get("id"))
    return value if isinstance(value, str) and value else None


def _mention_offset(mention: Mapping[str, Any]) -> int | None:
    evidence = mention.get("evidence")
    if isinstance(evidence, Mapping) and isinstance(evidence.get("section_offset"), int):
        return evidence["section_offset"]
    anchor = mention.get("anchor")
    if isinstance(anchor, Mapping) and isinstance(anchor.get("offset"), int):
        return anchor["offset"]
    return None


def display_span_for_anchor(
    canonical: str,
    displayed: str,
    offset: int,
    surface: str,
) -> tuple[int, int]:
    """Return the exact displayed span for one canonical Mention anchor."""

    if offset < 0 or canonical[offset : offset + len(surface)] != surface:
        raise ValueError("Mention anchor does not match canonical section text")
    starts, ends, _characters = _display_boundaries(canonical, displayed)
    end_offset = offset + len(surface)
    if end_offset > len(canonical):
        raise ValueError("Mention anchor exceeds canonical section text")
    start = starts[offset]
    end = ends[end_offset]
    if start >= end or displayed[start:end] != surface:
        raise ValueError("Mention anchor cannot be mapped to displayed text")
    return start, end


def _annotation_id(mention: Mapping[str, Any]) -> str | None:
    metadata = mention.get("source_section_metadata")
    if isinstance(metadata, Mapping) and isinstance(metadata.get("annotation_id"), str):
        return metadata["annotation_id"]
    anchor = mention.get("anchor")
    if isinstance(anchor, Mapping) and isinstance(anchor.get("annotation_id"), str):
        return anchor["annotation_id"]
    return None


def _resolved_mention(mention: Mapping[str, Any]) -> bool:
    return (
        isinstance(mention.get("person_id"), str)
        and bool(mention.get("person_id"))
        and mention.get("confidence", "unresolved") != "unresolved"
    )


def _placement_candidates(
    canonical: str,
    displayed: str,
    mentions: Any,
    *,
    section: str,
    annotation_id: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    start_boundaries, end_boundaries, _characters = _display_boundaries(canonical, displayed)
    placements: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    if not isinstance(mentions, (list, tuple)):
        return placements, suppressed

    for mention in mentions:
        if not isinstance(mention, Mapping) or not _resolved_mention(mention):
            continue
        mention_section = mention.get("section")
        if mention_section != section:
            continue
        mention_annotation_id = _annotation_id(mention)
        if section == "liu_annotation" and annotation_id is not None and mention_annotation_id != annotation_id:
            continue
        surface = mention.get("surface")
        mention_id = _mention_id(mention)
        offset = _mention_offset(mention)
        person_id = mention.get("person_id")
        if not isinstance(surface, str) or not mention_id or not isinstance(person_id, str) or offset is None:
            if mention_id:
                suppressed.append(
                    {
                        "mention_id": mention_id,
                        "reason": "unsafe_anchor",
                        "section": section,
                        "annotation_id": annotation_id,
                    }
                )
            continue
        end_offset = offset + len(surface)
        if offset < 0 or end_offset > len(canonical) or canonical[offset:end_offset] != surface:
            suppressed.append(
                {
                    "mention_id": mention_id,
                    "reason": "unsafe_anchor",
                    "section": section,
                    "annotation_id": annotation_id,
                }
            )
            continue
        start = start_boundaries[offset]
        end = end_boundaries[end_offset]
        if start >= end or displayed[start:end] == "":
            suppressed.append(
                {
                    "mention_id": mention_id,
                    "reason": "unsafe_anchor",
                    "section": section,
                    "annotation_id": annotation_id,
                }
            )
            continue
        placements.append(
            {
                "mention_id": mention_id,
                "person_id": person_id,
                "start": start,
                "end": end,
                "section": section,
                "annotation_id": annotation_id,
            }
        )

    # Prefer the shortest exact anchored surface when one resolved mention is
    # nested inside another.  This is deterministic and keeps explicit names
    # such as 王凝之 interactive without emitting nested buttons.  The larger
    # mention remains visible in the secondary mention summary.
    selected: list[dict[str, Any]] = []
    for placement in sorted(placements, key=lambda item: (item["end"] - item["start"], item["start"], item["mention_id"])):
        conflict = next(
            (
                existing
                for existing in selected
                if placement["start"] < existing["end"] and existing["start"] < placement["end"]
            ),
            None,
        )
        if conflict is None:
            selected.append(placement)
            continue
        same_range = placement["start"] == conflict["start"] and placement["end"] == conflict["end"]
        contains = (
            placement["start"] <= conflict["start"] and placement["end"] >= conflict["end"]
        ) or (
            conflict["start"] <= placement["start"] and conflict["end"] >= placement["end"]
        )
        if same_range or not contains:
            raise ValueError(
                "incompatible overlapping resolved Mention ranges: "
                f"{placement['mention_id']} and {conflict['mention_id']}"
            )
        suppressed.append(
            {
                "mention_id": placement["mention_id"],
                "reason": "overlapping_anchor",
                "section": section,
                "annotation_id": annotation_id,
            }
        )
    selected.sort(key=lambda item: (item["start"], item["end"], item["mention_id"]))
    return selected, suppressed


def build_reading_segments(
    canonical: str,
    displayed: str,
    converter: Any,
    mentions: Any,
    *,
    section: str,
    annotation_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Project resolved canonical Mention anchors into display segments."""

    placements, suppressed = _placement_candidates(
        canonical,
        displayed,
        mentions,
        section=section,
        annotation_id=annotation_id,
    )
    pieces: list[dict[str, Any]] = []
    cursor = 0
    for placement in placements:
        if placement["start"] > cursor:
            text = displayed[cursor : placement["start"]]
            pieces.append({"type": "text", "display": _display_pair(text, converter)})
        text = displayed[placement["start"] : placement["end"]]
        piece: dict[str, Any] = {
            "type": "person_mention",
            "mention_id": placement["mention_id"],
            "person_id": placement["person_id"],
            "display": _display_pair(text, converter),
        }
        if section == "liu_annotation" and annotation_id is not None:
            piece["annotation_id"] = annotation_id
        pieces.append(piece)
        cursor = placement["end"]
    if cursor < len(displayed):
        pieces.append({"type": "text", "display": _display_pair(displayed[cursor:], converter)})
    if not pieces:
        pieces = [{"type": "text", "display": _display_pair(displayed, converter)}]

    expected_simplified = converter.convert(displayed)
    actual_simplified = "".join(piece["display"]["simplified"] for piece in pieces)
    if actual_simplified != expected_simplified:
        # OpenCC can use phrase context.  If independent segment conversion
        # would change the existing simplified reading, keep the source as one
        # ordinary segment and make the inability to project explicit.
        mention_ids = {
            placement["mention_id"] for placement in placements
        }
        suppressed.extend(
            {
                "mention_id": mention_id,
                "reason": "display_conversion_context_mismatch",
                "section": section,
                "annotation_id": annotation_id,
            }
            for mention_id in sorted(mention_ids)
        )
        return [{"type": "text", "display": _display_pair(displayed, converter)}], suppressed
    return pieces, suppressed


def build_display_reading(
    record: Mapping[str, Any],
    converter: Any,
    *,
    people: Any = (),
    mentions: Any = (),
    placement_mentions: Any = (),
    canonical_annotations: Any = (),
    sources: Any = (),
    relations: Any = (),
    evidence: Any = (),
) -> dict[str, Any]:
    sections = record["sections"]
    annotations: list[dict[str, Any]] = []
    suppressed_mentions: list[dict[str, Any]] = []
    canonical_annotation_by_id = {
        str(annotation.get("id")): annotation
        for annotation in canonical_annotations
        if isinstance(annotation, Mapping) and isinstance(annotation.get("id"), str)
    }
    annotation_section = sections.get("liu_annotation")
    for annotation_id, annotation in canonical_annotation_by_id.items():
        canonical_annotation = str(annotation.get("text", ""))
        punctuated_annotation = None
        if annotation_id == "annotation-001" and isinstance(annotation_section, Mapping):
            candidate = annotation_section.get("punctuated_text")
            if isinstance(candidate, str) and candidate:
                punctuated_annotation = candidate
        displayed_annotation = punctuated_annotation or canonical_annotation
        segments, segment_suppressed = build_reading_segments(
            canonical_annotation,
            displayed_annotation,
            converter,
            placement_mentions,
            section="liu_annotation",
            annotation_id=annotation_id,
        )
        suppressed_mentions.extend(segment_suppressed)
        annotations.append(
            {
                "id": annotation_id,
                "original": displayed_annotation,
                "simplified": converter.convert(displayed_annotation),
                "segments": segments,
                "display_source": "punctuation_record" if punctuated_annotation else "canonical_source",
                "punctuation_status": "available" if punctuated_annotation else "unavailable",
            }
        )
    main_canonical = str(sections["main_text"].get("canonical_text", ""))
    main_display = str(sections["main_text"].get("punctuated_text", ""))
    main_segments, main_suppressed = build_reading_segments(
        main_canonical,
        main_display,
        converter,
        placement_mentions,
        section="main_text",
    )
    suppressed_mentions.extend(main_suppressed)
    return {
        "entry_id": record["entry_id"],
        "status": record["status"],
        "punctuation_record_id": record["id"],
        "base_canonical_entry_sha256": record["base_canonical_entry_sha256"],
        "conversion": {
            "library": "opencc-python-reimplemented",
            "config": "t2s",
        },
        "main_text": {
            "original": main_display,
            "simplified": converter.convert(main_display),
            "segments": main_segments,
        },
        "annotations": annotations,
        "mention_projection": {"suppressed": suppressed_mentions},
        "labels": {
            key: _display_pair(value, converter) for key, value in READER_LABELS.items()
        },
        "person_display": _build_person_display(people, converter),
        "mention_display": _build_mention_display(mentions, converter),
        "source_display": _build_source_display(sources, converter),
        "relation_display": _build_relation_display(relations, converter),
        "evidence_display": _build_evidence_display(evidence, converter),
        "display_overrides": list(record.get("display_overrides", [])),
    }
