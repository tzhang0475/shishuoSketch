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


def build_display_reading(
    record: Mapping[str, Any],
    converter: Any,
    *,
    people: Any = (),
    mentions: Any = (),
    sources: Any = (),
    relations: Any = (),
    evidence: Any = (),
) -> dict[str, Any]:
    sections = record["sections"]
    annotations: list[dict[str, str]] = []
    annotation_section = sections.get("liu_annotation")
    if isinstance(annotation_section, Mapping):
        punctuated_annotation = annotation_section.get("punctuated_text")
        if isinstance(punctuated_annotation, str) and punctuated_annotation:
            annotations.append(
                {
                    "id": "annotation-001",
                    "original": punctuated_annotation,
                    "simplified": converter.convert(punctuated_annotation),
                }
            )
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
            "original": sections["main_text"]["punctuated_text"],
            "simplified": converter.convert(sections["main_text"]["punctuated_text"]),
        },
        "annotations": annotations,
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
