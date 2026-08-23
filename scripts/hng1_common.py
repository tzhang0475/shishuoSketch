#!/usr/bin/env python3
"""Deterministic HNG1 selection, profiles, and local retrieval primitives."""

from __future__ import annotations

import collections
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
HNG0_SELECTION = ROOT / "data/generated/hng0/hng0-selection.json"
PEOPLE = ROOT / "data/people.json"
ALIASES = ROOT / "data/aliases.json"
PERSON_STORY = ROOT / "data/derived/person-story-links.json"
JINSHU_INDEX = ROOT / "data/jinshu-unit-index.json"
HNG0_CANDIDATES = ROOT / "data/generated/hng0/hng0-candidates.json"

import build_hng0_2 as hng02  # noqa: E402
from hng0_1_common import (  # noqa: E402
    _load_shishuo_units,
    build_people_catalog,
    build_source_units,
    read_json,
    search_normalize,
    sha256_file,
    stable_hash,
    route_sources,
)


def _person_story_degrees() -> collections.Counter[str]:
    doc = read_json(PERSON_STORY)
    degree: collections.Counter[str] = collections.Counter()
    for row in doc.get("links", []):
        if isinstance(row, Mapping) and row.get("person_id") and row.get("entry_id"):
            degree[str(row["person_id"])] += 1
    return degree


def _relation_degrees() -> collections.Counter[str]:
    counts: collections.Counter[str] = collections.Counter()
    if not HNG0_CANDIDATES.is_file():
        return counts
    doc = read_json(HNG0_CANDIDATES)
    for row in doc.get("relations", []):
        if not isinstance(row, Mapping):
            continue
        for key in ("person_a", "person_b"):
            if row.get(key):
                counts[str(row[key])] += 1
    return counts


def _jinshu_degrees(catalog: Mapping[str, Mapping[str, Any]]) -> collections.Counter[str]:
    """Count deterministic name/alias hits in processed Jinshu units."""

    counts: collections.Counter[str] = collections.Counter()
    doc = read_json(JINSHU_INDEX)
    terms = {
        pid: sorted({search_normalize(person.get("canonical_name")), *(
            search_normalize(value) for value in person.get("forms", [])
        )} - {""}, key=lambda value: (-len(value), value))
        for pid, person in catalog.items()
    }
    for item in doc.get("units", []):
        if not isinstance(item, Mapping) or item.get("category") == "editorial":
            continue
        path = ROOT / str(item.get("file_path") or "")
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        folded = search_normalize(text)
        for pid, values in terms.items():
            if any(value in folded for value in values):
                counts[pid] += 1
    return counts


def build_hng1_selection(*, count_per_stratum: int = 12) -> dict[str, Any]:
    catalog = build_people_catalog(ROOT)
    hng0 = read_json(HNG0_SELECTION)
    excluded = {str(row.get("person_id")) for row in hng0.get("people", []) if row.get("person_id")}
    people_doc = read_json(PEOPLE)
    raw_people = {str(row.get("person_id")): row for row in people_doc.get("people", []) if isinstance(row, Mapping) and row.get("person_id")}
    story_degree = _person_story_degrees()
    relation_degree = _relation_degrees()
    jinshu_degree = _jinshu_degrees(catalog)

    fresh: list[dict[str, Any]] = []
    for pid, person in sorted(catalog.items()):
        if pid in excluded:
            continue
        raw = raw_people.get(pid, {})
        evidence_density = len(raw.get("source_evidence", [])) if isinstance(raw.get("source_evidence"), list) else 0
        signals = {
            "story_degree": int(story_degree.get(pid, 0)),
            "relation_degree": int(relation_degree.get(pid, 0)),
            "evidence_density": evidence_density,
            "jinshu_entry_count": int(jinshu_degree.get(pid, 0)),
        }
        # The score is only a reproducible connectivity signal.  It does not
        # encode historical importance and does not alter the live algorithm.
        score = (
            signals["story_degree"] * 10
            + signals["relation_degree"] * 15
            + signals["evidence_density"] * 3
            + signals["jinshu_entry_count"]
        )
        selection_key = stable_hash({"stage": "hng1-selection-v1", "person_id": pid})
        fresh.append({
            "person_id": pid,
            "canonical_name": person.get("canonical_name"),
            "score": score,
            "signals": signals,
            "selection_key": selection_key,
            "available_scope_role": raw.get("scope_role"),
            "available_identity_scope": raw.get("identity_scope"),
        })

    ranked = sorted(fresh, key=lambda row: (-int(row["score"]), str(row["selection_key"]), str(row["person_id"])))
    total = len(ranked)
    for index, row in enumerate(ranked, 1):
        if index <= (total + 2) // 3:
            row["stratum"] = "high_connectivity"
        elif index <= 2 * (total + 2) // 3:
            row["stratum"] = "medium_connectivity"
        else:
            row["stratum"] = "low_connectivity"
        row["connectivity_rank"] = index

    selected: list[dict[str, Any]] = []
    for stratum in ("high_connectivity", "medium_connectivity", "low_connectivity"):
        selected.extend([row for row in ranked if row["stratum"] == stratum][:count_per_stratum])
    selected.sort(key=lambda row: (str(row["stratum"]), int(row["connectivity_rank"]), str(row["person_id"])))
    return {
        "schema": 1,
        "stage": "hng1-selection",
        "selection_method": "fresh_non_hng0_score_stratified_deterministic_v1",
        "frozen": True,
        "requested_seed_count": count_per_stratum * 3,
        "selected_seed_count": len(selected),
        "source_person_count": len(catalog),
        "excluded_hng0_seed_ids": sorted(excluded),
        "strata": {name: count_per_stratum for name in ("high_connectivity", "medium_connectivity", "low_connectivity")},
        "selection_signals": ["story_degree", "relation_degree", "evidence_density", "jinshu_entry_count"],
        "people": selected,
        "source_hashes": {
            "data/people.json": sha256_file(PEOPLE),
            "data/aliases.json": sha256_file(ALIASES),
            "data/derived/person-story-links.json": sha256_file(PERSON_STORY),
            "data/jinshu-unit-index.json": sha256_file(JINSHU_INDEX),
            "data/generated/hng0/hng0-selection.json": sha256_file(HNG0_SELECTION),
        },
        "one_hop_only": True,
        "canonical_write_back": False,
    }


def build_fresh_profiles(selection: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    catalog = build_people_catalog(ROOT)
    profiles: dict[str, dict[str, Any]] = {}
    selected_ids = {str(row.get("person_id")) for row in selection.get("people", []) if row.get("person_id")}
    for pid in sorted(selected_ids):
        person = catalog.get(pid, {})
        terms = sorted({
            search_normalize(value)
            for value in [person.get("canonical_name"), *person.get("forms", [])]
            if len(search_normalize(value)) >= 2
        })
        profiles[pid] = {
            "person_id": pid,
            "canonical_name": person.get("canonical_name"),
            "courtesy_name": person.get("courtesy_forms", []),
            "aliases": person.get("alias_forms", []),
            "office_titles": person.get("office_titles", []),
            "clan": None,
            "native_place": None,
            "known_relatives": [],
            "search_terms_original": sorted({
                value for value in [person.get("canonical_name"), *person.get("forms", [])] if value and len(search_normalize(value)) >= 2
            }),
            "search_terms_normalized": terms,
            "seed": True,
            "one_hop_only": True,
            "stratum": next((row.get("stratum") for row in selection.get("people", []) if str(row.get("person_id")) == pid), None),
        }
    return profiles


def load_retrieval_sources() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return punctuated-first units and legacy fallback units separately."""

    punctuated = list(hng02.load_punctuated_units())
    for row in _load_shishuo_units(ROOT):
        punctuated.append({**row, "source_form": "punctuated", "source_witness": "shishuo-canonical-punctuated"})
    legacy: list[dict[str, Any]] = []
    for row in build_source_units(ROOT):
        legacy.append({**row, "source_form": "legacy_local"})
    punctuated.sort(key=lambda row: str(row.get("source_ref")))
    legacy.sort(key=lambda row: str(row.get("source_ref")))
    return punctuated, legacy


def _logical_hit_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    locator = row.get("locator") if isinstance(row.get("locator"), Mapping) else {}
    identity = locator.get("story_id") or locator.get("unit_id") or locator.get("page_title") or locator.get("block_id") or locator.get("global_juan") or locator.get("volume") or ""
    return str(row.get("work") or ""), str(identity), ",".join(sorted(str(x) for x in row.get("matched_terms", [])))


def find_punctuated_first(profile: Mapping[str, Any], punctuated: Sequence[Mapping[str, Any]], legacy: Sequence[Mapping[str, Any]], *, top_k: int = 8) -> dict[str, Any]:
    routes = route_sources(profile, [*punctuated, *legacy])
    p_hits = hng02.find_units(profile, punctuated, punctuated_first=True, top_k=max(top_k, 8))
    l_hits = hng02.find_units(profile, legacy, punctuated_first=False, top_k=max(top_k, 8))
    selected: list[dict[str, Any]] = []
    selected_refs: set[str] = set()
    for hit in p_hits:
        if str(hit.get("source_ref")) in selected_refs:
            continue
        selected.append({**hit, "source_form": "punctuated"})
        selected_refs.add(str(hit.get("source_ref")))
        if len(selected) >= top_k:
            break
    fallback_used = False
    if len(selected) < top_k:
        fallback_used = bool(l_hits)
        for hit in l_hits:
            if str(hit.get("source_ref")) in selected_refs:
                continue
            selected.append({**hit, "source_form": "legacy_local"})
            selected_refs.add(str(hit.get("source_ref")))
            if len(selected) >= top_k:
                break
    return {
        "profile_person_id": profile.get("person_id"),
        "routes": routes,
        "query_terms": profile.get("search_terms_original", []),
        "punctuated_match_count": len(p_hits),
        "legacy_match_count": len(l_hits),
        "raw_match_count": len(p_hits) + len(l_hits),
        "fallback_used": fallback_used,
        "hits": selected,
    }


def open_short_hits(find_result: Mapping[str, Any], punctuated: Sequence[Mapping[str, Any]], legacy: Sequence[Mapping[str, Any]], *, max_passages: int = 6) -> list[dict[str, Any]]:
    units_by_ref = {str(row.get("source_ref")): row for row in [*punctuated, *legacy]}
    opened: list[dict[str, Any]] = []
    for hit in list(find_result.get("hits", []))[: max(1, min(max_passages, 8))]:
        ref = str(hit.get("source_ref") or "")
        unit = units_by_ref.get(ref)
        if not unit:
            continue
        item = hng02.open_hit(hit, units_by_ref, short=True)
        if not item:
            continue
        item.update({
            "original_text": str(unit.get("text") or ""),
            "source_path": unit.get("source_path"),
            "source_sha256": unit.get("source_sha256"),
            "source_witness": unit.get("source_witness"),
            "source_url": unit.get("source_url"),
            "revision_id": unit.get("revision_id"),
            "source_form": hit.get("source_form") or unit.get("source_form"),
        })
        opened.append(item)
    return opened


__all__ = [
    "build_hng1_selection", "build_fresh_profiles", "load_retrieval_sources",
    "find_punctuated_first", "open_short_hits",
]
