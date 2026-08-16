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


def normalize_reader_whitespace(text: str) -> str:
    """Collapse physical source line boundaries in reader-facing text.

    Processed Shishuo entries preserve witness line boundaries for source and
    provenance work.  The current punctuation/reading schema has no separate
    semantic-paragraph field, so a newline in a display string is a physical
    source boundary, not a reader paragraph.  Keep the boundary as ordinary
    inline whitespace while leaving the canonical/source strings untouched.

    If semantic paragraph breaks are introduced later, they must be carried
    by an explicit reading-layer field and projected separately; this helper
    deliberately does not infer them from raw newlines.
    """

    return re.sub(r"[\r\n]+", " ", text).strip()


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


def _person_name(people: Any, person_id: Any) -> str:
    if not isinstance(people, (list, tuple)) or not isinstance(person_id, str):
        return ""
    for person in people:
        if isinstance(person, Mapping) and person.get("id") == person_id:
            value = person.get("canonical_name")
            if isinstance(value, str):
                return value
    return ""


def _mention_explanation(mention: Mapping[str, Any], people: Any) -> str:
    """Build a restrained route explanation from structured mention facts."""

    surface = str(mention.get("surface", ""))
    target = mention.get("resolution_target")
    person_name = (
        str(target.get("canonical_name"))
        if isinstance(target, Mapping) and isinstance(target.get("canonical_name"), str)
        else _person_name(people, mention.get("person_id"))
    ) or "此人"
    resolution_status = mention.get("resolution_status")
    if resolution_status == "candidate_for_review":
        names = [
            str(item.get("canonical_name"))
            for item in mention.get("resolution_candidates", [])
            if isinstance(item, Mapping) and isinstance(item.get("canonical_name"), str)
        ]
        alias_type = str(mention.get("alias_type", ""))
        if alias_type in {"office_title", "official_title"}:
            return (
                f"「{surface}」是官职称谓，需结合上下文判断；"
                f"当前可能指{'、'.join(dict.fromkeys(names)) or '不同人物'}，证据不足以唯一判断。"
            )
        return (
            f"「{surface}」可能指{'、'.join(dict.fromkeys(names)) or '不同人物'}，"
            "当前证据不足以唯一判断。"
        )
    if resolution_status == "resolved" and isinstance(target, Mapping) and target.get("target_kind") == "identity_candidate":
        return f"本项目已将「{surface}」解析为{person_name}；该人物尚未建立人物卡。"
    alias_type = str(mention.get("alias_type", ""))
    resolution_mode = str(mention.get("resolution_mode", ""))
    exact = resolution_mode == "exact"
    if alias_type == "courtesy_name" and mention.get("confidence", "unresolved") != "unresolved":
        return f"「{surface}」是{person_name}的字。"
    if exact and alias_type == "personal_name":
        return f"「{surface}」是{person_name}的名。"
    if alias_type in {"office_title", "official_title"}:
        if exact:
            return f"「{surface}」是官职称谓。"
        return (
            f"「{surface}」是官职称谓，并非{person_name}的专名。"
            f"本则依据上下文及现有解析证据指向{person_name}。解析方式：上下文判定。"
        )
    if alias_type in {"contextual_title", "general_title", "textual_shorthand"} or not exact:
        return (
            f"「{surface}」是上下文称谓，并非{person_name}的专名。"
            f"本则依据现有解析证据指向{person_name}。解析方式：{resolution_mode or '上下文判定'}。"
        )
    if alias_type == "kinship_reference":
        return (
            f"「{surface}」是亲属称谓，本则依据现有解析证据指向{person_name}。"
            f"解析方式：{resolution_mode or '上下文判定'}。"
        )
    if exact:
        return f"本项目已将「{surface}」解析为{person_name}。"
    return (
        f"本项目已将「{surface}」解析为{person_name}。"
        f"解析方式：{resolution_mode or '未注明'}。"
    )


def _build_mention_display(
    mentions: Any,
    converter: Any,
    people: Any,
    *,
    include_explanations: bool = True,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if not isinstance(mentions, (list, tuple)):
        return result
    for mention in mentions:
        if not isinstance(mention, Mapping) or not isinstance(mention.get("id"), str):
            continue
        surface = mention.get("surface")
        if isinstance(surface, str):
            display: dict[str, Any] = {"surface": _display_pair(surface, converter)}
            if include_explanations:
                display.update(
                    {
                        "explanation": _display_pair(_mention_explanation(mention, people), converter),
                        "alias_type": str(mention.get("alias_type", "")),
                        "resolution_mode": str(mention.get("resolution_mode", "")),
                    }
                )
                resolution_target = mention.get("resolution_target")
                if isinstance(resolution_target, Mapping):
                    display["resolution_status"] = str(mention.get("resolution_status", "resolved"))
                    display["target_kind"] = str(resolution_target.get("target_kind", ""))
                    if isinstance(resolution_target.get("canonical_name"), str):
                        display["canonical_name"] = _display_pair(str(resolution_target["canonical_name"]), converter)
                candidates = mention.get("resolution_candidates")
                if isinstance(candidates, list):
                    names = [
                        _display_pair(str(item["canonical_name"]), converter)
                        for item in candidates
                        if isinstance(item, Mapping) and isinstance(item.get("canonical_name"), str)
                    ]
                    if names:
                        display["candidate_names"] = names
                        display.setdefault("resolution_status", str(mention.get("resolution_status", "resolved")))
            result[mention["id"]] = display
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

        display = {
            "label": _display_pair(str(relation.get("label", "")), converter),
            "role_a": role_pair("role_a"),
            "role_b": role_pair("role_b"),
        }
        # Only expose the bounded event label to readers.  Internal ontology
        # values such as long_term_social are schema metadata, not
        # reader-facing prose.  Keep the field absent for legacy Relations so
        # the existing Relation card projection remains byte/semantically
        # stable.
        scope = role_pair("scope_event")
        if scope is not None:
            display["scope"] = scope
        result[relation["id"]] = display
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
    """Return the displayed span for one canonical Mention anchor.

    A semantic span may preserve a physical source line ending (for example
    ``温\n太真``) while the reader projection removes that witness boundary
    (``温太真``).  Permit that presentation-only whitespace change, but keep
    the canonical anchor and the significant character sequence strict.
    """

    if offset < 0 or canonical[offset : offset + len(surface)] != surface:
        raise ValueError("Mention anchor does not match canonical section text")
    starts, ends, _characters = _display_boundaries(canonical, displayed)
    end_offset = offset + len(surface)
    if end_offset > len(canonical):
        raise ValueError("Mention anchor exceeds canonical section text")
    start = starts[offset]
    end = ends[end_offset]
    if start >= end:
        raise ValueError("Mention anchor cannot be mapped to displayed text")
    visible = displayed[start:end]
    visible_without_physical_breaks = visible.replace("\r\n", "").replace("\n", "").replace("\r", "")
    surface_without_physical_breaks = surface.replace("\r\n", "").replace("\n", "").replace("\r", "")
    if visible != surface and visible_without_physical_breaks != surface_without_physical_breaks:
        raise ValueError("Mention anchor cannot be mapped to displayed text")
    return start, end


def _display_offset_for_logical_offset(canonical: str, displayed: str, logical_offset: int) -> int:
    """Map a significant-character offset to a displayed-string boundary."""

    _starts, _ends, characters = _display_boundaries(canonical, displayed)
    if logical_offset < 0 or logical_offset > len(characters):
        raise ValueError("logical display offset exceeds canonical section")
    displayed_positions = _significant_positions(displayed)
    if logical_offset == len(displayed_positions):
        return len(displayed)
    return displayed_positions[logical_offset][1]


def _annotation_id(mention: Mapping[str, Any]) -> str | None:
    explicit = mention.get("annotation_id")
    if isinstance(explicit, str):
        return explicit
    metadata = mention.get("source_section_metadata")
    if isinstance(metadata, Mapping) and isinstance(metadata.get("annotation_id"), str):
        return metadata["annotation_id"]
    anchor = mention.get("anchor")
    if isinstance(anchor, Mapping) and isinstance(anchor.get("annotation_id"), str):
        return anchor["annotation_id"]
    return None


def _annotation_ownership(
    mention: Mapping[str, Any],
    canonical_annotations: Any,
) -> tuple[str | None, str]:
    """Resolve Liu Mention ownership from explicit metadata or safe text evidence.

    A Mention ordinal embedded in an ID is never an annotation locator.  The
    normal path is the explicit processed-entry metadata; the fallback is
    deliberately narrow and only accepts one canonical block whose text
    contains the anchored surface at the anchored offset (or, when no offset
    exists, one unique block-level occurrence).
    """

    metadata = mention.get("source_section_metadata")
    if isinstance(metadata, Mapping) and isinstance(metadata.get("annotation_id"), str):
        return str(metadata["annotation_id"]), "source_section_metadata.annotation_id"
    anchor = mention.get("anchor")
    if isinstance(anchor, Mapping) and isinstance(anchor.get("annotation_id"), str):
        return str(anchor["annotation_id"]), "anchor.annotation_id"
    if mention.get("section") != "liu_annotation":
        return None, "not_liu_annotation"

    surface = mention.get("surface")
    offset = _mention_offset(mention)
    if not isinstance(surface, str) or not surface:
        return None, "unresolved_annotation_block"
    candidates: list[str] = []
    if isinstance(canonical_annotations, (list, tuple)):
        for annotation in canonical_annotations:
            if not isinstance(annotation, Mapping) or not isinstance(annotation.get("id"), str):
                continue
            annotation_id = str(annotation["id"])
            text = str(annotation.get("text", ""))
            if isinstance(offset, int) and offset >= 0 and text[offset : offset + len(surface)] == surface:
                candidates.append(annotation_id)
        if len(candidates) == 1:
            return candidates[0], "unique_canonical_anchor_match"
        if offset is None:
            unique_occurrences = [
                str(annotation["id"])
                for annotation in canonical_annotations
                if isinstance(annotation, Mapping)
                and isinstance(annotation.get("id"), str)
                and str(annotation.get("text", "")).count(surface) == 1
            ]
            if len(unique_occurrences) == 1:
                return unique_occurrences[0], "unique_canonical_surface_match"
    return None, "unresolved_annotation_block"


def effective_annotation_id(
    mention: Mapping[str, Any],
    canonical_annotations: Any = (),
) -> str | None:
    """Return the canonical Liu annotation ID without parsing Mention IDs."""

    return _annotation_ownership(mention, canonical_annotations)[0]


def _visible_resolution_mention(mention: Any) -> bool:
    if not isinstance(mention, Mapping):
        return False
    return (
        _resolved_mention(mention)
        or mention.get("resolution_status") in {"resolved", "candidate_for_review"}
    )


def _prepare_placement_mentions(
    mentions: Any,
    canonical_annotations: Any,
) -> tuple[list[Mapping[str, Any]], list[dict[str, Any]]]:
    """Normalize Liu ownership before scanning individual annotation blocks."""

    if not isinstance(mentions, (list, tuple)):
        return [], []
    annotation_ids = {
        str(annotation.get("id"))
        for annotation in canonical_annotations
        if isinstance(annotation, Mapping) and isinstance(annotation.get("id"), str)
    } if isinstance(canonical_annotations, (list, tuple)) else set()
    prepared: list[Mapping[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    for mention in mentions:
        if not isinstance(mention, Mapping) or not _visible_resolution_mention(mention):
            prepared.append(mention)
            continue
        if mention.get("section") != "liu_annotation":
            prepared.append(mention)
            continue
        annotation_id, basis = _annotation_ownership(mention, canonical_annotations)
        if annotation_id is None or annotation_id not in annotation_ids:
            mention_id = _mention_id(mention)
            if mention_id:
                suppressed.append(
                    {
                        "mention_id": mention_id,
                        "reason": "unresolved_annotation_block",
                        "section": "liu_annotation",
                        "annotation_id": annotation_id,
                        "annotation_ownership_basis": basis,
                    }
                )
            continue
        normalized = dict(mention)
        metadata = dict(mention.get("source_section_metadata", {})) if isinstance(mention.get("source_section_metadata"), Mapping) else {}
        metadata["annotation_id"] = annotation_id
        normalized["source_section_metadata"] = metadata
        if basis not in {"source_section_metadata.annotation_id", "anchor.annotation_id"}:
            normalized["annotation_ownership_basis"] = basis
        prepared.append(normalized)
    return prepared, suppressed


def _annotation_label(index: int) -> str:
    labels = "①②③④⑤⑥⑦⑧⑨⑩"
    if 1 <= index <= len(labels):
        return labels[index - 1]
    return str(index)


def build_annotation_insertions(
    source_text: str | None,
    main_canonical: str,
    annotations: Any,
) -> dict[str, dict[str, Any]]:
    """Map processed-entry annotation ranges into the transmitted main text.

    The processed entry records where an annotation block occurs in the source
    stream.  This is an insertion point for reading apparatus, not a claim
    about the lemma span that the annotation explains.
    """

    result: dict[str, dict[str, Any]] = {}
    annotation_list = [
        annotation
        for annotation in annotations
        if isinstance(annotation, Mapping) and isinstance(annotation.get("id"), str)
    ] if isinstance(annotations, (list, tuple)) else []
    if not source_text:
        for index, annotation in enumerate(annotation_list, start=1):
            result[annotation["id"]] = {
                "status": "unavailable",
                "main_text_offset": None,
                "source": None,
                "reason": "missing_processed_entry_source",
                "label": _annotation_label(index),
            }
        return result

    ranges: list[tuple[int, int, str, str]] = []
    invalid_ids: set[str] = set()
    for annotation in annotation_list:
        annotation_id = annotation["id"]
        metadata = annotation.get("metadata", {})
        start = metadata.get("entry_relative_start") if isinstance(metadata, Mapping) else None
        end = metadata.get("entry_relative_end_exclusive") if isinstance(metadata, Mapping) else None
        text = str(annotation.get("text", ""))
        if (
            not isinstance(start, int)
            or not isinstance(end, int)
            or start < 0
            or end <= start
            or end > len(source_text)
            or source_text[start:end] != text
        ):
            invalid_ids.add(annotation_id)
            continue
        ranges.append((start, end, annotation_id, text))

    ranges.sort(key=lambda item: (item[0], item[1], item[2]))
    overlaps = any(current[0] < previous[1] for previous, current in zip(ranges, ranges[1:]))
    visible_source = source_text
    for start, end, _annotation_id_value, _text in sorted(ranges, key=lambda item: item[0], reverse=True):
        visible_source = visible_source[:start] + visible_source[end:]
    visible_source = re.sub(r"<!--.*?-->", "", visible_source, flags=re.DOTALL)
    aligned_stream = strip_display_punctuation(visible_source) == strip_display_punctuation(main_canonical)

    for index, annotation in enumerate(annotation_list, start=1):
        annotation_id = annotation["id"]
        matching = next((item for item in ranges if item[2] == annotation_id), None)
        reason = None
        if annotation_id in invalid_ids:
            reason = "invalid_entry_relative_range"
        elif overlaps:
            reason = "overlapping_entry_relative_ranges"
        elif not aligned_stream:
            reason = "processed_entry_stream_mismatch"
        if reason or matching is None:
            result[annotation_id] = {
                "status": "unavailable",
                "main_text_offset": None,
                "source": "processed_entry_structure" if matching else None,
                "reason": reason or "missing_entry_relative_range",
                "label": _annotation_label(index),
            }
            continue
        start = matching[0]
        prefix = source_text[:start]
        prior_ranges = [item for item in ranges if item[1] <= start]
        for prior_start, prior_end, _prior_id, _prior_text in sorted(
            prior_ranges,
            key=lambda item: item[0],
            reverse=True,
        ):
            prefix = prefix[:prior_start] + prefix[prior_end:]
        prefix = re.sub(r"<!--.*?-->", "", prefix, flags=re.DOTALL)
        main_offset = len(strip_display_punctuation(prefix))
        result[annotation_id] = {
            "status": "safe",
            "main_text_offset": main_offset,
            "source": "processed_entry_structure",
            "reason": "entry_relative_range_exact",
            "label": _annotation_label(index),
        }
    return result


def _resolved_mention(mention: Mapping[str, Any]) -> bool:
    return (
        isinstance(mention.get("person_id"), str)
        and bool(mention.get("person_id"))
        and mention.get("confidence", "unresolved") != "unresolved"
    )


def _identity_resolution_mention(mention: Mapping[str, Any]) -> bool:
    """Whether a Mention has a non-production ER1 identity projection."""

    status = mention.get("resolution_status")
    if status not in {"resolved", "candidate_for_review"}:
        return False
    target = mention.get("resolution_target")
    if isinstance(target, Mapping) and target.get("target_kind") == "identity_candidate":
        return True
    candidates = mention.get("resolution_candidates")
    return status == "candidate_for_review" and isinstance(candidates, list) and bool(candidates)


def _placement_candidates(
    canonical: str,
    displayed: str,
    mentions: Any,
    *,
    section: str,
    annotation_id: str | None,
    ruler_mentions: Any = (),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    start_boundaries, end_boundaries, _characters = _display_boundaries(canonical, displayed)
    placements: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    if not isinstance(mentions, (list, tuple)):
        return placements, suppressed

    source_mentions: list[Mapping[str, Any]] = []
    if isinstance(mentions, (list, tuple)):
        source_mentions.extend(item for item in mentions if isinstance(item, Mapping))
    if isinstance(ruler_mentions, (list, tuple)):
        source_mentions.extend(
            {**item, "_e0_ruler_mention": True}
            for item in ruler_mentions
            if isinstance(item, Mapping)
        )

    for mention in source_mentions:
        is_ruler = bool(mention.get("_e0_ruler_mention"))
        if not isinstance(mention, Mapping) or not (
            _resolved_mention(mention) or _identity_resolution_mention(mention) or is_ruler
        ):
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
        target = mention.get("resolution_target")
        is_production = _resolved_mention(mention)
        if not isinstance(surface, str) or not mention_id or (is_production and not isinstance(person_id, str)) or offset is None:
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
        display_span = mention.get("display_span")
        span_offset = offset
        span_surface = surface
        if isinstance(display_span, Mapping):
            candidate_offset = display_span.get("offset")
            candidate_end = display_span.get("end_offset_exclusive")
            candidate_text = display_span.get("text")
            if (
                not isinstance(candidate_offset, int)
                or not isinstance(candidate_end, int)
                or not isinstance(candidate_text, str)
                or candidate_end <= candidate_offset
                or candidate_text == ""
            ):
                suppressed.append(
                    {
                        "mention_id": mention_id,
                        "reason": "unsafe_display_span",
                        "section": section,
                        "annotation_id": annotation_id,
                    }
                )
                continue
            span_offset = candidate_offset
            span_surface = candidate_text
        end_offset = span_offset + len(span_surface)
        if span_offset < 0 or end_offset > len(canonical) or canonical[span_offset:end_offset] != span_surface:
            suppressed.append(
                {
                    "mention_id": mention_id,
                    "reason": "unsafe_anchor",
                    "section": section,
                    "annotation_id": annotation_id,
                }
            )
            continue
        start = start_boundaries[span_offset]
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
        placement = {
            "mention_id": mention_id,
            "person_id": person_id if isinstance(person_id, str) else None,
            "target_kind": "ruler" if is_ruler else ("production_person" if is_production else "identity_candidate"),
            "resolution_status": str(mention.get("resolution_status", "resolved")),
            "resolution_target": dict(target) if isinstance(target, Mapping) else None,
            "resolution_candidates": [
                dict(item)
                for item in mention.get("resolution_candidates", [])
                if isinstance(item, Mapping)
            ],
            "start": start,
            "end": end,
            "canonical_offset": span_offset,
            "canonical_end_offset_exclusive": end_offset,
            "surface": span_surface,
            "raw_surface": surface,
            "span_basis": str(display_span.get("basis")) if isinstance(display_span, Mapping) else "canonical_mention_surface",
            "section": section,
            "annotation_id": annotation_id,
        }
        if is_ruler:
            placement["ruler_id"] = str(mention["ruler_id"])
            placement["era_card_id"] = str(mention["era_card_id"])
            placement["resolution_status"] = "resolved"
        if isinstance(mention.get("annotation_ownership_basis"), str):
            placement["annotation_ownership_basis"] = mention["annotation_ownership_basis"]
        placements.append(placement)

    # Prefer the maximal semantic surface when one resolved Mention is nested
    # inside another.  The canonical Mention anchor remains untouched; the
    # build-time display_span is the separate span decision.  This prevents
    # 温太真 from being rendered as only 太真 while retaining deterministic
    # suppression of the nested shorter record.
    selected: list[dict[str, Any]] = []
    for placement in sorted(
        placements,
        key=lambda item: (
            -(item["end"] - item["start"]),
            item["start"],
            -len(str(item.get("raw_surface", ""))),
            item["mention_id"],
        ),
    ):
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
        if same_range:
            placement_target = placement.get("resolution_target") or {"person_id": placement.get("person_id")}
            conflict_target = conflict.get("resolution_target") or {"person_id": conflict.get("person_id")}
            if placement_target == conflict_target:
                suppressed.append(
                    {
                        "mention_id": placement["mention_id"],
                        "reason": "duplicate_display_span",
                        "section": section,
                        "annotation_id": annotation_id,
                    }
                )
                continue
            raise ValueError(
                "incompatible overlapping resolved Mention ranges: "
                f"{placement['mention_id']} and {conflict['mention_id']}"
            )
        if not contains:
            raise ValueError(
                "incompatible overlapping resolved Mention ranges: "
                f"{placement['mention_id']} and {conflict['mention_id']}"
            )
        placement_target = placement.get("resolution_target") or {"person_id": placement.get("person_id")}
        conflict_target = conflict.get("resolution_target") or {"person_id": conflict.get("person_id")}
        if placement_target != conflict_target:
            # Existing nested mentions can intentionally describe different
            # people (for example 王凝之妻謝氏 contains 王凝之).  Preserve
            # the established shorter anchor in that case; maximal-span
            # preference applies only when both spans resolve to one person.
            placement_length = placement["end"] - placement["start"]
            conflict_length = conflict["end"] - conflict["start"]
            if placement_length < conflict_length:
                selected.remove(conflict)
                suppressed.append(
                    {
                        "mention_id": conflict["mention_id"],
                        "reason": "overlapping_anchor",
                        "section": section,
                        "annotation_id": annotation_id,
                    }
                )
                selected.append(placement)
            else:
                suppressed.append(
                    {
                        "mention_id": placement["mention_id"],
                        "reason": "overlapping_anchor",
                        "section": section,
                        "annotation_id": annotation_id,
                    }
                )
            continue
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
    annotation_markers: Any = (),
    ruler_mentions: Any = (),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Project resolved canonical Mention anchors into display segments."""

    placements, suppressed = _placement_candidates(
        canonical,
        displayed,
        mentions,
        section=section,
        annotation_id=annotation_id,
        ruler_mentions=ruler_mentions,
    )
    valid_markers: list[dict[str, Any]] = []
    if section == "main_text" and isinstance(annotation_markers, (list, tuple)):
        for marker in annotation_markers:
            if not isinstance(marker, Mapping):
                continue
            annotation_id_value = marker.get("annotation_id")
            display_offset = marker.get("display_offset")
            if not isinstance(annotation_id_value, str) or not isinstance(display_offset, int):
                continue
            if display_offset < 0 or display_offset > len(displayed):
                suppressed.append(
                    {
                        "kind": "annotation_marker",
                        "annotation_id": annotation_id_value,
                        "reason": "unsafe_insertion_point",
                        "section": section,
                    }
                )
                continue
            if any(item["start"] < display_offset < item["end"] for item in placements):
                suppressed.append(
                    {
                        "kind": "annotation_marker",
                        "annotation_id": annotation_id_value,
                        "reason": "insertion_inside_person_mention",
                        "section": section,
                    }
                )
                continue
            valid_markers.append(
                {
                    "annotation_id": annotation_id_value,
                    "display_offset": display_offset,
                    "label": marker.get("label", _display_pair("〔注〕", converter)),
                }
            )

    def make_pieces(selected_placements: list[dict[str, Any]], selected_markers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        pieces: list[dict[str, Any]] = []
        cursor = 0
        marker_index = 0
        for placement in selected_placements:
            while marker_index < len(selected_markers) and selected_markers[marker_index]["display_offset"] <= placement["start"]:
                marker = selected_markers[marker_index]
                marker_offset = marker["display_offset"]
                if marker_offset < cursor:
                    marker_index += 1
                    continue
                if marker_offset > cursor:
                    text = displayed[cursor:marker_offset]
                    pieces.append({"type": "text", "display": _display_pair(text, converter)})
                pieces.append(
                    {
                        "type": "annotation_marker",
                        "annotation_id": marker["annotation_id"],
                        "label": marker["label"],
                        "display": _display_pair("", converter),
                    }
                )
                cursor = marker_offset
                marker_index += 1
            if placement["start"] > cursor:
                text = displayed[cursor : placement["start"]]
                pieces.append({"type": "text", "display": _display_pair(text, converter)})
            text = displayed[placement["start"] : placement["end"]]
            if placement.get("target_kind") == "production_person":
                piece: dict[str, Any] = {
                    "type": "person_mention",
                    "mention_id": placement["mention_id"],
                    "person_id": placement["person_id"],
                    "display": _display_pair(text, converter),
                }
            elif placement.get("target_kind") == "ruler":
                piece = {
                    "type": "ruler_mention",
                    "mention_id": placement["mention_id"],
                    "ruler_id": placement["ruler_id"],
                    "era_card_id": placement["era_card_id"],
                    "display": _display_pair(text, converter),
                }
                if section == "liu_annotation" and annotation_id is not None:
                    piece["annotation_id"] = annotation_id
            else:
                target = placement.get("resolution_target")
                names: list[str] = []
                primary_name: str | None = None
                if isinstance(target, Mapping) and isinstance(target.get("canonical_name"), str):
                    primary_name = str(target["canonical_name"])
                    names.append(primary_name)
                for candidate in placement.get("resolution_candidates", []):
                    if isinstance(candidate, Mapping) and isinstance(candidate.get("canonical_name"), str):
                        if candidate["canonical_name"] not in names:
                            names.append(str(candidate["canonical_name"]))
                piece = {
                    "type": "identity_mention",
                    "mention_id": placement["mention_id"],
                    "resolution_status": placement.get("resolution_status", "resolved"),
                    "target_kind": "identity_candidate",
                    # A resolved target remains the recommended identity even
                    # when the same surface has competing candidates.  The
                    # competing names stay available in candidate_names for
                    # the review/display layer; they must not erase the
                    # selected target's identity label.
                    "canonical_name": _display_pair(primary_name, converter) if primary_name else None,
                    "candidate_names": [_display_pair(name, converter) for name in names],
                    "display": _display_pair(text, converter),
                }
            if section == "liu_annotation" and annotation_id is not None:
                piece["annotation_id"] = annotation_id
            if isinstance(placement.get("annotation_ownership_basis"), str):
                piece["annotation_ownership_basis"] = placement["annotation_ownership_basis"]
            pieces.append(piece)
            cursor = placement["end"]
        while marker_index < len(selected_markers):
            marker = selected_markers[marker_index]
            marker_offset = marker["display_offset"]
            if marker_offset < cursor:
                marker_index += 1
                continue
            if marker_offset > cursor:
                text = displayed[cursor:marker_offset]
                pieces.append({"type": "text", "display": _display_pair(text, converter)})
            pieces.append(
                {
                    "type": "annotation_marker",
                    "annotation_id": marker["annotation_id"],
                    "label": marker["label"],
                    "display": _display_pair("", converter),
                }
            )
            cursor = marker_offset
            marker_index += 1
        if cursor < len(displayed):
            pieces.append({"type": "text", "display": _display_pair(displayed[cursor:], converter)})
        if not pieces:
            pieces = [{"type": "text", "display": _display_pair(displayed, converter)}]
        return pieces

    valid_markers.sort(key=lambda item: (item["display_offset"], item["annotation_id"]))
    pieces = make_pieces(placements, valid_markers)

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
        marker_ids = {marker["annotation_id"] for marker in valid_markers}
        suppressed.extend(
            {
                "kind": "annotation_marker",
                "annotation_id": annotation_id_value,
                "reason": "display_conversion_context_mismatch",
                "section": section,
            }
            for annotation_id_value in sorted(marker_ids)
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
    source_text: str | None = None,
    annotation_evidence_ids: Mapping[str, str] | None = None,
    ruler_mentions: Any = (),
) -> dict[str, Any]:
    sections = record["sections"]
    annotations: list[dict[str, Any]] = []
    suppressed_mentions: list[dict[str, Any]] = []
    main_canonical = str(sections["main_text"].get("canonical_text", ""))
    # Punctuation records are derived display input, but may still retain
    # physical witness line boundaries.  Normalize only this reader-facing
    # projection; canonical/source text and evidence quotations remain exact.
    main_display = normalize_reader_whitespace(
        str(sections["main_text"].get("punctuated_text", ""))
    )
    canonical_annotation_by_id = {
        str(annotation.get("id")): annotation
        for annotation in canonical_annotations
        if isinstance(annotation, Mapping) and isinstance(annotation.get("id"), str)
    }
    prepared_placement_mentions, ownership_suppressed = _prepare_placement_mentions(
        placement_mentions,
        canonical_annotations,
    )
    suppressed_mentions.extend(ownership_suppressed)
    annotation_section = sections.get("liu_annotation")
    annotation_insertions = build_annotation_insertions(
        source_text,
        main_canonical,
        canonical_annotations,
    )
    annotation_markers: list[dict[str, Any]] = []
    try:
        main_starts, _main_ends, _main_chars = _display_boundaries(main_canonical, main_display)
    except ValueError:
        main_starts = []
    for annotation_id, annotation in canonical_annotation_by_id.items():
        canonical_annotation = str(annotation.get("text", ""))
        punctuated_annotation = None
        if isinstance(annotation_section, Mapping):
            candidate_by_id = annotation_section.get("punctuated_text_by_id")
            candidate = (
                candidate_by_id.get(annotation_id)
                if isinstance(candidate_by_id, Mapping)
                else None
            )
            if annotation_id == "annotation-001" and candidate is None:
                candidate = annotation_section.get("punctuated_text")
            if isinstance(candidate, str) and candidate and strip_display_punctuation(candidate) == strip_display_punctuation(canonical_annotation):
                punctuated_annotation = candidate
        displayed_annotation = normalize_reader_whitespace(
            punctuated_annotation or canonical_annotation
        )
        segments, segment_suppressed = build_reading_segments(
            canonical_annotation,
            displayed_annotation,
            converter,
            prepared_placement_mentions,
            section="liu_annotation",
            annotation_id=annotation_id,
            ruler_mentions=ruler_mentions,
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
                "evidence_ids": (
                    [annotation_evidence_ids[annotation_id]]
                    if isinstance(annotation_evidence_ids, Mapping)
                    and isinstance(annotation_evidence_ids.get(annotation_id), str)
                    else []
                ),
            }
        )
        if not annotations[-1]["evidence_ids"]:
            annotations[-1].pop("evidence_ids", None)
        if source_text is not None:
            annotations[-1]["insertion"] = dict(
                annotation_insertions.get(
                    annotation_id,
                    {
                        "status": "unavailable",
                        "main_text_offset": None,
                        "source": None,
                        "reason": "no_processed_entry_range",
                        "label": _annotation_label(len(annotations)),
                    },
                )
            )
    for annotation in annotations:
        if source_text is None:
            continue
        insertion = annotation.get("insertion", {})
        if (
            isinstance(insertion, Mapping)
            and insertion.get("status") == "safe"
            and isinstance(insertion.get("main_text_offset"), int)
            and main_starts
        ):
            canonical_offset = insertion["main_text_offset"]
            if 0 <= canonical_offset <= len(_significant_positions(main_canonical)):
                annotation_markers.append(
                    {
                        "annotation_id": annotation["id"],
                        "display_offset": _display_offset_for_logical_offset(
                            main_canonical,
                            main_display,
                            canonical_offset,
                        ),
                        "label": _display_pair(
                            f"〔注{insertion.get('label', '注')}〕",
                            converter,
                        ),
                    }
                )
    main_segments, main_suppressed = build_reading_segments(
        main_canonical,
        main_display,
        converter,
        prepared_placement_mentions,
        section="main_text",
        annotation_markers=annotation_markers,
        ruler_mentions=ruler_mentions,
    )
    suppressed_mentions.extend(main_suppressed)
    suppressed_marker_ids = {
        item.get("annotation_id")
        for item in main_suppressed
        if item.get("kind") == "annotation_marker"
    }
    for annotation in annotations:
        insertion = annotation.get("insertion")
        if isinstance(insertion, dict) and annotation["id"] in suppressed_marker_ids:
            insertion["status"] = "unavailable"
            insertion["reason"] = next(
                (
                    item.get("reason")
                    for item in main_suppressed
                    if item.get("kind") == "annotation_marker"
                    and item.get("annotation_id") == annotation["id"]
                ),
                "marker_projection_failed",
            )

    # A visible resolution must never disappear merely because a section
    # scanner skipped it.  Reconcile the complete build-time projection before
    # returning the bundle so the browser cannot be the first place to find an
    # orphan Mention.
    visible_ids = {
        mention_id
        for mention in placement_mentions
        if isinstance(mention, Mapping)
        and _visible_resolution_mention(mention)
        and (mention_id := _mention_id(mention))
    } if isinstance(placement_mentions, (list, tuple)) else set()
    placed_ids: list[str] = []

    def collect_placed(segments: Any) -> None:
        if not isinstance(segments, (list, tuple)):
            return
        for segment in segments:
            if not isinstance(segment, Mapping) or segment.get("type") not in {"person_mention", "identity_mention"}:
                continue
            mention_id = segment.get("mention_id")
            if isinstance(mention_id, str):
                placed_ids.append(mention_id)

    collect_placed(main_segments)
    for annotation in annotations:
        collect_placed(annotation.get("segments"))
    suppressed_ids = [
        str(item["mention_id"])
        for item in suppressed_mentions
        if isinstance(item, Mapping) and isinstance(item.get("mention_id"), str)
    ]
    placed_set = set(placed_ids)
    suppressed_set = set(suppressed_ids)
    if len(placed_ids) != len(placed_set):
        duplicates = sorted({mention_id for mention_id in placed_ids if placed_ids.count(mention_id) > 1})
        raise ValueError(f"duplicate inline Mention projection: {', '.join(duplicates)}")
    if len(suppressed_ids) != len(suppressed_set):
        duplicates = sorted({mention_id for mention_id in suppressed_ids if suppressed_ids.count(mention_id) > 1})
        raise ValueError(f"duplicate suppressed Mention projection: {', '.join(duplicates)}")
    both = sorted(placed_set & suppressed_set)
    if both:
        raise ValueError(f"Mention appears both inline and suppressed: {', '.join(both)}")
    orphan_ids = sorted(visible_ids - placed_set - suppressed_set)
    if orphan_ids:
        raise ValueError(f"visible Mention has no inline/suppressed projection: {', '.join(orphan_ids)}")
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
        "mention_display": _build_mention_display(
            mentions,
            converter,
            people,
            include_explanations=source_text is not None,
        ),
        "source_display": _build_source_display(sources, converter),
        "relation_display": _build_relation_display(relations, converter),
        "evidence_display": _build_evidence_display(evidence, converter),
        "display_overrides": list(record.get("display_overrides", [])),
    }
