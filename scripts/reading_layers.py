#!/usr/bin/env python3
"""Shared helpers for the reviewed WP1 reading layer."""

from __future__ import annotations

import json
from pathlib import Path
import unicodedata
from typing import Any, Mapping

try:
    from .build_six_person_pilot import parse_shishuo_sections
except ImportError:  # pragma: no cover - direct script imports
    from build_six_person_pilot import parse_shishuo_sections


PUNCTUATION_RELATIVE_PATH = "data/annotation/wp1-punctuation.json"


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
) -> list[str]:
    errors: list[str] = []
    sections = record.get("sections")
    if not isinstance(sections, Mapping):
        return [f"{record.get('id')}: sections is not an object"]
    for section_name in ("main_text", "liu_annotation"):
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
        if not isinstance(punctuated, str) or not punctuated:
            errors.append(f"{record.get('id')}.{section_name}: punctuated_text is empty")
            continue
        if isinstance(actual_canonical, str) and strip_display_punctuation(punctuated) != strip_display_punctuation(actual_canonical):
            errors.append(
                f"{record.get('id')}.{section_name}: punctuation round-trip changes the canonical character sequence"
            )
    return errors


def build_display_reading(record: Mapping[str, Any], converter: Any) -> dict[str, Any]:
    sections = record["sections"]
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
        "annotations": [
            {
                "id": "annotation-001",
                "original": sections["liu_annotation"]["punctuated_text"],
                "simplified": converter.convert(sections["liu_annotation"]["punctuated_text"]),
            }
        ],
        "display_overrides": list(record.get("display_overrides", [])),
    }
