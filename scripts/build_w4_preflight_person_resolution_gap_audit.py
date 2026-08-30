#!/usr/bin/env python3
"""Audit title/appellation surfaces before the W4 structural expansion.

This is an evidence audit, not a resolver.  It deliberately reports
context-dependent surfaces without promoting them to global aliases.  The
effective ER1 projection is the only source of a ``safe_story_local`` result.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

try:
    from . import person_resolution as pr
except ImportError:  # direct execution
    import person_resolution as pr


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = Path("data/derived/w4-preflight-person-resolution-gap-audit.json")

# These are audit categories, not a title resolver.  In particular, a bare
# title is intentionally retained as an ambiguity/lexical record rather than
# assigned to whichever production Person currently has the most aliases.
FOCUS_ALIAS_TYPES = {
    "courtesy_name",
    "established_appellation",
    "honorific",
    "office_title",
    "contextual_title",
    "textual_shorthand",
    "surname_plus_courtesy_name",
    "surname_plus_title",
}
TITLE_SUFFIXES = (
    "從事中郎",
    "大將軍",
    "尚書令",
    "太尉",
    "丞相",
    "右軍",
    "太傅",
    "尚書",
    "中軍",
    "司州",
    "將軍",
    "侯",
    "公",
)
GENERIC_CONTEXTUAL_SURFACES = set(TITLE_SUFFIXES) | {"公"}

# This is a deliberately small audit seed for the confirmed Story-local
# omission.  It does not alter resolution and is kept here so the preflight
# report records the non-production/candidate identity surface explicitly.
EXPLICIT_STORY_SURFACES = {
    "14-rongzhi-024": {
        "王胡之": "story_local_person_like_surface_requires_identity_evidence",
    },
}


def _write_json(root: Path, relative: Path, value: Any) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _target_key(target: Mapping[str, Any]) -> str:
    return pr._target_key(target)


def _target_copy(target: Mapping[str, Any]) -> dict[str, Any]:
    return pr._target_copy(target)


def _offset(mention: Mapping[str, Any]) -> int | None:
    for key in ("entry_relative_start", "entry_relative_offset"):
        value = mention.get(key)
        if isinstance(value, int):
            return value
    evidence = mention.get("evidence")
    if isinstance(evidence, Mapping) and isinstance(evidence.get("section_offset"), int):
        return int(evidence["section_offset"])
    anchor = mention.get("anchor")
    if isinstance(anchor, Mapping) and isinstance(anchor.get("offset"), int):
        return int(anchor["offset"])
    return None


def _target_rows(root: Path) -> tuple[list[Mapping[str, Any]], dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    people_document = pr.read_json(root, pr.PEOPLE_PATH)
    people = [item for item in people_document.get("people", []) if isinstance(item, Mapping)]
    candidate_document = pr.read_json(root, pr.IDENTITY_CANDIDATES_PATH)
    candidates = [item for item in candidate_document.get("candidates", []) if isinstance(item, Mapping)]
    identity_document = pr.read_json(root, pr.IDENTITY_TARGETS_PATH)
    identity_candidates = [item for item in identity_document.get("candidates", []) if isinstance(item, Mapping)]
    candidates_by_id = {
        str(item.get("candidate_id")): item
        for item in [*candidates, *identity_candidates]
        if isinstance(item.get("candidate_id"), str)
    }
    people_by_id = {
        str(item.get("person_id")): item
        for item in people
        if isinstance(item.get("person_id"), str)
    }
    return people, people_by_id, candidates_by_id


def _build_alias_data(root: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]], list[Mapping[str, Any]]]:
    people, _people_by_id, _candidates_by_id = _target_rows(root)
    try:
        from scripts import sfh2r_contract
        preserved = sfh2r_contract.pre_repair_alias_document()
    except (ImportError, OSError, ValueError, TypeError):
        preserved = None
    aliases = (preserved or pr.read_json(root, pr.ALIASES_PATH)).get("aliases", [])
    candidate_document = pr.read_json(root, pr.IDENTITY_CANDIDATES_PATH)
    candidates = candidate_document.get("candidates", [])
    candidate_evidence = {
        str(item.get("id")): item
        for item in candidate_document.get("evidence", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    identity_overrides = pr._identity_target_overrides(root)
    materialized = pr._materialized_candidate_persons(root)
    return pr._build_alias_index(
        root,
        people,
        aliases,
        candidates,
        candidate_evidence,
        identity_overrides,
        materialized,
    )


def _stable_record_id(story_id: str, section: str, offset: int, surface: str) -> str:
    raw = f"{story_id}|{section}|{offset}|{surface}".encode("utf-8")
    return "w4-preflight-gap-" + hashlib.sha256(raw).hexdigest()[:24]


def _occurrences(text: str, surface: str) -> list[tuple[int, int]]:
    if not surface:
        return []
    result: list[tuple[int, int]] = []
    cursor = 0
    while cursor <= len(text) - len(surface):
        offset = text.find(surface, cursor)
        if offset < 0:
            break
        end = offset + len(surface)
        result.append((offset, end))
        cursor = end
    return result


def _effective_index(root: Path) -> dict[tuple[str, str, int, str], list[Mapping[str, Any]]]:
    document = pr.read_json(root, pr.EFFECTIVE_PATH)
    result: dict[tuple[str, str, int, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in [*document.get("mentions", []), *document.get("derived_mentions", [])]:
        if not isinstance(row, Mapping):
            continue
        story_id = str(row.get("entry_id") or row.get("source_id") or "")
        section = str(row.get("section", "main_text"))
        if section.startswith("liu_annotation"):
            section = "liu_annotation"
        offset = _offset(row)
        surface = str(row.get("surface", ""))
        if story_id and surface and offset is not None:
            result[(story_id, section, offset, surface)].append(row)
    return result


def _compact_effective(rows: list[Mapping[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    rows = sorted(rows, key=lambda row: str(row.get("mention_id", "")))
    row = rows[0]
    target = row.get("resolution_target")
    compact: dict[str, Any] = {
        "mention_id": str(row.get("mention_id", "")),
        "resolution_status": str(row.get("resolution_status", "")),
        "resolution_method": str(row.get("resolution_method", "")),
        "resolution_review_status": str(row.get("resolution_review_status", "")),
    }
    compact["resolution_target"] = _target_copy(target) if isinstance(target, Mapping) else None
    compact["resolution_candidates"] = [
        _target_copy(item)
        for item in row.get("resolution_candidates", [])
        if isinstance(item, Mapping)
    ]
    compact["resolution_evidence_ids"] = sorted(
        str(item)
        for item in row.get("resolution_evidence_ids", [])
        if isinstance(item, str)
    )
    compact["derived_only"] = bool(row.get("derived_only", False))
    return compact


def _candidate_targets(
    associations: list[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    targets: dict[str, dict[str, Any]] = {}
    evidence_ids: set[str] = set()
    modes: set[str] = set()
    for item in associations:
        target = item.get("target")
        if isinstance(target, Mapping):
            targets[_target_key(target)] = _target_copy(target)
        for evidence_id in item.get("evidence_ids", []):
            if isinstance(evidence_id, str):
                evidence_ids.add(evidence_id)
        mode = item.get("association_mode")
        if isinstance(mode, str):
            modes.add(mode)
    return (
        sorted(targets.values(), key=lambda target: (_target_key(target), target.get("canonical_name", ""))),
        sorted(evidence_ids),
        sorted(modes),
    )


def _status_for_occurrence(
    *,
    surface: str,
    effective: Mapping[str, Any] | None,
    candidates: list[dict[str, Any]],
    association_modes: list[str],
    lexical_rule: Mapping[str, Any] | None,
    explicit_basis: str | None,
) -> tuple[str, str]:
    if effective is not None:
        target = effective.get("resolution_target")
        if isinstance(target, Mapping) and target.get("target_kind") == "identity_candidate":
            return "non_production_identity", "existing_effective_identity_candidate"
        if effective.get("resolution_status") == "resolved" and isinstance(target, Mapping):
            if effective.get("derived_only") or effective.get("resolution_method") in {
                "er1_1_contextual_span_seed",
                "er1_1_story_local_coreference",
            }:
                return "safe_story_local", "existing_story_local_span_decision"
            return "safe_story_local", "existing_effective_resolution"
        if effective.get("resolution_status") == "candidate_for_review":
            return "ambiguous", "existing_candidate_for_review"
        if lexical_rule is not None:
            return "lexical_non_identity", "existing_unresolved_homographic_alias"
        return "unresolved", "existing_unresolved_resolution"

    if lexical_rule is not None:
        return "lexical_non_identity", "homographic_alias_rule_requires_context"
    if surface in GENERIC_CONTEXTUAL_SURFACES:
        return "ambiguous", "generic_title_requires_story_context"
    if explicit_basis is not None:
        return "unresolved", explicit_basis
    if any(target.get("target_kind") == "identity_candidate" for target in candidates):
        if all(target.get("target_kind") == "identity_candidate" for target in candidates):
            return "non_production_identity", "identity_candidate_surface_without_production_navigation"
        return "ambiguous", "production_and_non_production_identity_candidates"
    if len(candidates) > 1 or any(mode != "exact" for mode in association_modes):
        return "ambiguous", "shared_or_contextual_alias_requires_local_evidence"
    if candidates:
        return "unresolved", "known_alias_without_effective_story_resolution"
    return "unresolved", "person_like_surface_requires_identity_evidence"


def build(root: Path = ROOT) -> dict[str, Any]:
    published_ids = pr._published_story_ids(root)
    sections = pr._load_sections(root)
    alias_index, _targets_by_key, _metadata = _build_alias_data(root)
    effective_index = _effective_index(root)
    _people, people_by_id, candidates_by_id = _target_rows(root)
    lexical_rules = pr._lexical_alias_rules(root)

    surname_chars = {
        str(person.get("canonical_name", ""))[0]
        for person in people_by_id.values()
        if str(person.get("canonical_name", ""))
    }
    surname_chars.update(
        str(candidate.get("preferred_name", ""))[0]
        for candidate in candidates_by_id.values()
        if str(candidate.get("preferred_name", ""))
        and str(candidate.get("preferred_name", ""))[0] not in GENERIC_CONTEXTUAL_SURFACES
    )

    # Surface -> audit discovery bases.  The list is populated from current
    # identity data and observed title morphology; it is not a resolver map.
    surface_bases: dict[str, set[str]] = defaultdict(set)
    for surface, associations in alias_index.items():
        if any(str(item.get("alias_type", "")) in FOCUS_ALIAS_TYPES for item in associations):
            surface_bases[surface].add("current_alias_registry")
        if any(
            isinstance(item.get("target"), Mapping)
            and item["target"].get("target_kind") == "identity_candidate"
            for item in associations
        ):
            surface_bases[surface].add("identity_candidate_registry")
    for surface in GENERIC_CONTEXTUAL_SURFACES:
        surface_bases[surface].add("generic_title_audit")
    for story_id, seeded in EXPLICIT_STORY_SURFACES.items():
        for surface, basis in seeded.items():
            surface_bases[surface].add(basis)

    source_surface_occurrences: list[tuple[str, str, str, int, int]] = []
    for story_id in sorted(published_ids):
        for section in ("main_text", "liu_annotation"):
            text = sections.get((story_id, section), "")
            if not text:
                continue
            observed: dict[str, set[str]] = defaultdict(set)
            for surface in surface_bases:
                if surface in text:
                    observed[surface].update(surface_bases[surface])
            for surname in sorted(surname_chars):
                for suffix in TITLE_SUFFIXES:
                    surface = surname + suffix
                    if surface in text:
                        observed[surface].add("surname_plus_title_pattern")
            for surface, bases in observed.items():
                surface_bases[surface].update(bases)
                for offset, end in _occurrences(text, surface):
                    source_surface_occurrences.append((story_id, section, surface, offset, end))

    # De-duplicate and keep source order.  A shorter surface wholly contained
    # in a longer observed identity span is not separately reported unless it
    # has its own effective resolution; this prevents a semantic span audit
    # from manufacturing shorter aliases.
    unique_occurrences = sorted(set(source_surface_occurrences), key=lambda item: (item[0], item[1], item[3], -len(item[2]), item[2]))
    retained: list[tuple[str, str, str, int, int]] = []
    for occurrence in unique_occurrences:
        story_id, section, surface, offset, end = occurrence
        key = (story_id, section, offset, surface)
        if effective_index.get(key):
            retained.append(occurrence)
            continue
        contained = any(
            other[0] == story_id
            and other[1] == section
            and other[3] <= offset
            and end <= other[4]
            and len(other[2]) > len(surface)
            for other in unique_occurrences
        )
        if not contained:
            retained.append(occurrence)

    evidence_document = pr.read_json(root, Path("data/evidence/wp1-evidence.json"))
    known_evidence_ids = {
        str(item.get("id"))
        for item in evidence_document.get("records", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    source_evidence_by_story: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for item in evidence_document.get("records", []):
        if not isinstance(item, Mapping):
            continue
        locator = item.get("locator")
        if isinstance(locator, Mapping) and isinstance(locator.get("entry_id"), str):
            source_evidence_by_story[str(locator["entry_id"])].append(item)
    records: list[dict[str, Any]] = []
    for story_id, section, surface, offset, end in retained:
        text = sections[(story_id, section)]
        normalized_section = "liu_annotation" if section.startswith("liu_annotation:") else section
        effective = _compact_effective(effective_index.get((story_id, normalized_section, offset, surface), []))
        associations = [item for item in alias_index.get(surface, []) if isinstance(item, Mapping)]
        candidates, alias_evidence_ids, association_modes = _candidate_targets(associations)
        if effective is not None:
            for target in effective.get("resolution_candidates", []):
                if isinstance(target, Mapping):
                    key = _target_key(target)
                    if key not in {_target_key(item) for item in candidates}:
                        candidates.append(_target_copy(target))
        explicit_basis = None
        if story_id in EXPLICIT_STORY_SURFACES and surface in EXPLICIT_STORY_SURFACES[story_id]:
            explicit_basis = EXPLICIT_STORY_SURFACES[story_id][surface]
        status, basis = _status_for_occurrence(
            surface=surface,
            effective=effective,
            candidates=candidates,
            association_modes=association_modes,
            lexical_rule=lexical_rules.get(surface),
            explicit_basis=explicit_basis,
        )
        evidence_ids = set(alias_evidence_ids)
        for item in source_evidence_by_story.get(story_id, []):
            if surface in str(item.get("quote", "")) and isinstance(item.get("id"), str):
                evidence_ids.add(str(item["id"]))
        if effective is not None:
            for evidence_id in effective.get("resolution_evidence_ids", []):
                if isinstance(evidence_id, str):
                    evidence_ids.add(evidence_id)
        evidence_ids = sorted(evidence_ids & known_evidence_ids)
        nearby_start = max(0, offset - 18)
        nearby_end = min(len(text), end + 18)
        records.append(
            {
                "audit_record_id": _stable_record_id(story_id, section, offset, surface),
                "story_id": story_id,
                "section": normalized_section,
                "surface": surface,
                "span": {
                    "offset": offset,
                    "end_offset_exclusive": end,
                    "text": text[offset:end],
                },
                "nearby_context": text[nearby_start:nearby_end],
                **(
                    {"annotation_id": section.split(":", 1)[1]}
                    if section.startswith("liu_annotation:")
                    else {}
                ),
                "existing_effective_resolution": effective,
                "candidate_targets": sorted(candidates, key=lambda target: (_target_key(target), target.get("canonical_name", ""))),
                "resolution_basis": basis,
                "discovery_bases": sorted(surface_bases.get(surface, set())),
                "evidence_ids": evidence_ids,
                "status": status,
            }
        )

    records.sort(key=lambda item: (item["story_id"], item["section"], item["span"]["offset"], -len(item["surface"]), item["surface"], item["audit_record_id"]))
    status_counts = Counter(str(item["status"]) for item in records)
    story_record_counts = Counter(str(item["story_id"]) for item in records)
    document = {
        "schema": 1,
        "stage": "w4-preflight-person-resolution-gap-audit",
        "scope": {
            "published_story_count": len(published_ids),
            "audited_story_count": len(published_ids),
            "published_story_ids": sorted(published_ids),
            "audit_sections": ["main_text", "liu_annotation"],
        },
        "summary": {
            "record_count": len(records),
            "story_count_with_records": len(story_record_counts),
            "status_counts": dict(sorted(status_counts.items())),
            "safe_story_local_count": status_counts.get("safe_story_local", 0),
            "ambiguous_count": status_counts.get("ambiguous", 0),
            "non_production_identity_count": status_counts.get("non_production_identity", 0),
            "lexical_non_identity_count": status_counts.get("lexical_non_identity", 0),
            "unresolved_count": status_counts.get("unresolved", 0),
            "stories_without_attention_records": len(published_ids - set(story_record_counts)),
        },
        "generated_from": [
            "data/people.json",
            "data/aliases.json",
            "data/derived/person-identity-candidates.json",
            "data/annotation/person-resolution-identity-candidates.json",
            "data/derived/person-resolution-effective.json",
            "content/processed/shishuo/entries/",
        ],
        "records": records,
    }
    _write_json(root, OUTPUT_PATH, document)
    return document


def main() -> int:
    document = build()
    print(
        "built W4 preflight Person-resolution audit: "
        f"{document['scope']['published_story_count']} Stories; "
        f"{document['summary']['record_count']} records; "
        f"statuses={document['summary']['status_counts']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
