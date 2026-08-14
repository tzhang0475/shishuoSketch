#!/usr/bin/env python3
"""Deterministic Person Sketch v1 projection helpers.

The curated file in ``data/annotation/person-sketches.json`` owns only the
small identity capsule.  Alias rows and story counts are projected here from
the canonical Person, Alias, Mention and PersonStory layers so the frontend
does not receive a second identity or relationship database.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from opencc import OpenCC

try:
    from .person_resolution import load_effective_mentions
except ImportError:  # direct execution
    from person_resolution import load_effective_mentions


PERSON_SKETCH_PATH = Path("data/annotation/person-sketches.json")
ALIASES_PATH = Path("data/aliases.json")
PEOPLE_PATH = Path("data/people.json")
MENTIONS_PATH = Path("data/mentions/shishuo.json")
PERSON_STORY_INDEX_PATH = Path("data/derived/person-story-index.json")
LIFE_GLIMPSE_OVERLAY_PATH = Path("data/annotation/s2-person-life-glimpses.json")

ALIAS_TYPE_LABELS = {
    "personal_name": "名",
    "courtesy_name": "字",
    "surname_plus_courtesy_name": "姓 + 字",
    "office_title": "官称",
    "contextual_title": "上下文称谓",
    "textual_shorthand": "简称",
    "kinship_reference": "亲属称谓",
    "orthographic_variant": "异文形式",
}

ALIAS_TYPE_ORDER = {
    "personal_name": 0,
    "courtesy_name": 1,
    "surname_plus_courtesy_name": 2,
    "office_title": 3,
    "contextual_title": 4,
    "textual_shorthand": 5,
    "kinship_reference": 6,
    "orthographic_variant": 7,
}

LAYER_ORDER = {"main_text": 0, "liu_annotation": 1}


def read_json(root: Path, relative_path: Path) -> Any:
    return json.loads((root / relative_path).read_text(encoding="utf-8"))


def load_source(root: Path) -> dict[str, Any]:
    return read_json(root, PERSON_SKETCH_PATH)


def _pair(value: str | None, converter: OpenCC) -> dict[str, str] | None:
    if value is None:
        return None
    return {"original": value, "simplified": converter.convert(value)}


def _semantic_status(alias: Mapping[str, Any]) -> str:
    mode = str(alias.get("resolution_mode", "ambiguous"))
    if mode == "exact":
        return "exact"
    if mode == "contextual":
        return "contextual"
    return "ambiguous"


def _semantic_label(status: str) -> str:
    return {
        "exact": "明确称谓",
        "contextual": "上下文称谓",
        "ambiguous": "需结合上下文",
    }[status]


def _mention_sort_key(
    mention: Mapping[str, Any],
    corpus_order: Mapping[str, int],
) -> tuple[int, int, int, str]:
    evidence = mention.get("evidence", {})
    offset = evidence.get("section_offset", 0) if isinstance(evidence, Mapping) else 0
    if not isinstance(offset, int):
        offset = 0
    section = str(mention.get("section", "main_text"))
    return (
        corpus_order.get(str(mention.get("entry_id", "")), 10**9),
        LAYER_ORDER.get(section, 9),
        offset,
        str(mention.get("mention_id", "")),
    )


def _story_counts(
    person_id: str,
    person_story_index: Mapping[str, Any],
) -> dict[str, int]:
    record = next(
        (
            item
            for item in person_story_index.get("persons", [])
            if isinstance(item, Mapping) and item.get("person_id") == person_id
        ),
        {},
    )
    refs = [item for item in record.get("story_refs", []) if isinstance(item, Mapping)]
    main_count = sum("main_text" in item.get("source_layers", []) for item in refs)
    annotation_only_count = sum(
        "main_text" not in item.get("source_layers", [])
        and "liu_annotation" in item.get("source_layers", [])
        for item in refs
    )
    reader_ready_count = sum(bool(item.get("reader_ready")) for item in refs)
    return {
        "total": len(refs),
        "main_text": main_count,
        "liu_annotation_only": annotation_only_count,
        "reader_ready": reader_ready_count,
    }


def _life_glimpse_rows(
    curated: Mapping[str, Any],
    converter: OpenCC,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for point in curated.get("life_glimpse", []):
        if not isinstance(point, Mapping):
            continue
        rows.append(
            {
                "text": _pair(str(point.get("text", "")), converter),
                "assertion_status": str(point.get("assertion_status", "unknown")),
                "review_status": str(point.get("review_status", "candidate")),
                "evidence_ids": sorted({str(item) for item in point.get("evidence_ids", []) if isinstance(item, str)}),
                "story_ids": sorted({str(item) for item in point.get("story_ids", []) if isinstance(item, str)}),
            }
        )
    return rows


def _alias_rows(
    person: Mapping[str, Any],
    aliases_by_id: Mapping[str, Mapping[str, Any]],
    raw_mentions: Sequence[Mapping[str, Any]],
    frontend_mentions: Mapping[str, Mapping[str, Any]],
    corpus_order: Mapping[str, int],
    converter: OpenCC,
) -> list[dict[str, Any]]:
    person_id = str(person.get("person_id", person.get("id", "")))
    rows: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for fallback_order, alias_id in enumerate(person.get("alias_ids", [])):
        alias = aliases_by_id.get(str(alias_id))
        if alias is None:
            raise ValueError(f"Person {person_id} references unknown Alias: {alias_id}")
        matches = [
            mention
            for mention in raw_mentions
            if mention.get("alias_id") == alias_id
            and (
                mention.get("person_id") == person_id
                or person_id in mention.get("candidate_person_ids", [])
            )
        ]
        matches.sort(key=lambda item: _mention_sort_key(item, corpus_order))
        # The frontend bundle intentionally contains only the current SC1
        # publication projection.  Retain occurrence counts from the full
        # reviewed Mention corpus, but expose only Mention IDs that are
        # actually available in this static bundle.
        mention_ids = [
            str(item["mention_id"])
            for item in matches
            if str(item.get("mention_id")) in frontend_mentions
        ]
        source_layers = sorted(
            {str(item.get("section")) for item in matches},
            key=lambda section: LAYER_ORDER.get(section, 9),
        )
        evidence_ids: list[str] = []
        for mention_id in mention_ids:
            projected = frontend_mentions.get(mention_id)
            if not projected:
                continue
            for evidence_id in projected.get("evidence_ids", []):
                if evidence_id not in evidence_ids:
                    evidence_ids.append(evidence_id)
        semantic_status = _semantic_status(alias)
        alias_type = str(alias.get("alias_type", ""))
        first_order = (
            _mention_sort_key(matches[0], corpus_order)
            if matches
            else (10**9, 10**9, fallback_order, str(alias_id))
        )
        row = {
            "alias_id": str(alias_id),
            "surface": _pair(str(alias.get("surface", "")), converter),
            "alias_type": alias_type,
            "label": _pair(ALIAS_TYPE_LABELS.get(alias_type, "称谓"), converter),
            "resolution_mode": str(alias.get("resolution_mode", "ambiguous")),
            "semantic_status": semantic_status,
            "semantic_label": _pair(_semantic_label(semantic_status), converter),
            "status": str(alias.get("status", "unknown")),
            "observed_in_shishuo": {
                "main_text": "main_text" in source_layers,
                "liu_annotation": "liu_annotation" in source_layers,
            },
            "source_layers": source_layers,
            "occurrence_count": len(matches),
            "mention_ids": mention_ids,
            "evidence_ids": evidence_ids,
        }
        rows.append(
            (
                (
                    ALIAS_TYPE_ORDER.get(alias_type, 99),
                    first_order,
                    str(alias_id),
                ),
                row,
            )
        )
    rows.sort(key=lambda item: item[0])
    result: list[dict[str, Any]] = []
    for display_order, (_sort_key, row) in enumerate(rows):
        row["display_order"] = display_order
        result.append(row)
    return result


def build_person_sketches(
    root: Path,
    *,
    people: Sequence[Mapping[str, Any]],
    frontend_mentions: Mapping[str, Mapping[str, Any]],
    converter: OpenCC | None = None,
) -> dict[str, dict[str, Any]]:
    """Build the frontend Person Sketch projection deterministically."""

    converter = converter or OpenCC("t2s")
    source = load_source(root)
    life_overlay = read_json(root, LIFE_GLIMPSE_OVERLAY_PATH) if (root / LIFE_GLIMPSE_OVERLAY_PATH).is_file() else {"records": []}
    life_overlay_by_person = {
        str(item["person_id"]): list(item.get("points", []))
        for item in life_overlay.get("records", [])
        if isinstance(item, Mapping) and isinstance(item.get("person_id"), str)
    }
    source_by_person = {
        str(item["person_id"]): item
        for item in source.get("records", [])
        if isinstance(item, Mapping) and isinstance(item.get("person_id"), str)
    }
    aliases = read_json(root, ALIASES_PATH).get("aliases", [])
    aliases_by_id = {
        str(item["alias_id"]): item
        for item in aliases
        if isinstance(item, Mapping) and isinstance(item.get("alias_id"), str)
    }
    # Alias rows are a reader-facing projection of effective resolution.  The
    # canonical Mention file remains the source of segmentation, but a
    # collision-aware ER1 decision must not leave a false occurrence under a
    # production Person's Sketch.
    raw_mentions = load_effective_mentions(root)
    corpus = read_json(root, Path("data/shishuo-corpus-index.json")).get("entries", [])
    corpus_order = {
        str(item["id"]): int(item.get("global_ordinal", 10**9))
        for item in corpus
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    person_story_index = read_json(root, PERSON_STORY_INDEX_PATH)
    canonical_people = read_json(root, PEOPLE_PATH).get("people", [])
    canonical_people_by_id = {
        str(item["person_id"]): item
        for item in canonical_people
        if isinstance(item, Mapping) and isinstance(item.get("person_id"), str)
    }

    result: dict[str, dict[str, Any]] = {}
    for person in people:
        person_id = str(person["id"] if "id" in person else person["person_id"])
        curated = source_by_person.get(person_id)
        if curated is None:
            raise ValueError(f"Person Sketch source is missing: {person_id}")
        canonical_person = canonical_people_by_id.get(person_id)
        if canonical_person is None:
            raise ValueError(f"Person registry source is missing: {person_id}")
        identity = curated.get("identity", {})
        if not isinstance(identity, Mapping):
            raise ValueError(f"Person Sketch identity is invalid: {person_id}")
        identity_projection = {
            "canonical_name": _pair(str(identity.get("canonical_name", person.get("canonical_name", ""))), converter),
            "courtesy_name": _pair(identity.get("courtesy_name"), converter),
            "clan": _pair(identity.get("clan"), converter),
            "identity_roles": [
                _pair(str(role), converter)
                for role in identity.get("identity_roles", [])
                if isinstance(role, str)
            ],
            "brief_intro": _pair(identity.get("brief_intro"), converter),
            "evidence_ids": list(identity.get("evidence_ids", [])),
        }
        curated_life_glimpse = list(curated.get("life_glimpse", []))
        curated_life_glimpse.extend(life_overlay_by_person.get(person_id, []))
        curated_with_overlay = dict(curated)
        curated_with_overlay["life_glimpse"] = curated_life_glimpse
        result[person_id] = {
            "person_id": person_id,
            "scope_role": person.get("scope_role", person.get("scope", "primary")),
            "review_status": curated.get("review_status", "candidate"),
            "identity": identity_projection,
            "profile_evidence_ids": list(curated.get("profile_evidence_ids", [])),
            "aliases": _alias_rows(
                canonical_person,
                aliases_by_id,
                raw_mentions,
                frontend_mentions,
                corpus_order,
                converter,
            ),
            "story_counts": _story_counts(person_id, person_story_index),
            "life_glimpse": _life_glimpse_rows(curated_with_overlay, converter),
        }
    return result
