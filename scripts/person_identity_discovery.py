#!/usr/bin/env python3
"""Deterministic P3A.1 open-world Person identity discovery.

This module intentionally runs before the reviewed Person/Alias/Mention
pipeline.  It proposes identity candidates from structured Jinshu biography
units and conservative Shishuo/Liu surface evidence.  Nothing produced here
is a production Person, Mention, Relation, PersonStoryLink, or publication
record.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from opencc import OpenCC

try:
    from .build_six_person_pilot import (
        entry_provenance,
        markdown_body,
        mask_markup_comments,
        parse_frontmatter,
        parse_shishuo_sections,
        source_context,
        unit_provenance,
    )
except ImportError:  # direct execution: python scripts/build_person_identity_candidates.py
    from build_six_person_pilot import (
        entry_provenance,
        markdown_body,
        mask_markup_comments,
        parse_frontmatter,
        parse_shishuo_sections,
        source_context,
        unit_provenance,
    )


ROOT = Path(__file__).resolve().parents[1]

PEOPLE_PATH = Path("data/people.json")
ALIASES_PATH = Path("data/aliases.json")
CORPUS_INDEX_PATH = Path("data/shishuo-corpus-index.json")
JINSHU_INDEX_PATH = Path("data/jinshu-unit-index.json")
SHISHUO_ENTRIES_PATH = Path("content/processed/shishuo/entries")
JINSHU_UNITS_PATH = Path("content/processed/jinshu/units")
SC1_BUNDLE_PATH = Path("data/derived/sc1-site.json")
OUTPUT_PATH = Path("data/derived/person-identity-candidates.json")
OCCURRENCES_PATH = Path("data/derived/person-candidate-occurrences.json")
REPORT_PATH = Path("docs/person-identity-candidates.md")

HAN = r"\u3400-\u9fff"
HAN_RE = re.compile(rf"[{HAN}]")

# These are only surface-classification rules.  They are not identity rules.
# A title is attached to an identity only after a separate local exact-name
# check succeeds.
TITLE_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("大司馬", "office_title"),
    ("太傅", "office_title"),
    ("丞相", "office_title"),
    ("右軍", "office_title"),
    ("宣武", "posthumous_title"),
    ("將軍", "office_title"),
    ("刺史", "office_title"),
    ("中郎", "office_title"),
    ("太守", "office_title"),
    ("尚書", "office_title"),
    ("公", "contextual_title"),
    ("侯", "contextual_title"),
    ("君", "contextual_title"),
)
TITLE_SUFFIXES_SORTED = tuple(sorted(TITLE_SUFFIXES, key=lambda item: -len(item[0])))
GENERIC_TITLES = {"太傅", "丞相", "右軍", "大司馬", "將軍", "刺史", "中郎", "太守", "尚書"}
ROLE_MARKERS = ("皇后", "太后", "皇太后", "太子妃", "夫人", "妻", "母", "女", "妃")


def read_json(root: Path, relative: Path) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def write_json(root: Path, relative: Path, value: Any) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@lru_cache(maxsize=None)
def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_hash(*parts: object) -> str:
    value = "\x1f".join(str(part) for part in parts)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _han_only(value: str) -> bool:
    return bool(value) and all(HAN_RE.fullmatch(char) for char in value)


def _clean_unit_text(value: str) -> str:
    # Comments are structural markup, not historical text for identity
    # matching.  Masking preserves offsets for evidence locators.
    return re.sub(r"\s+", "", mask_markup_comments(value))


def _clean_title(value: object) -> str:
    raw = str(value or "")
    return re.sub(r"[\s　]+", "", raw)


def _source_provenance_for_jinshu(metadata: Mapping[str, Any]) -> dict[str, Any]:
    provenance = unit_provenance(metadata)
    return {
        "witness_id": provenance.get("source_witness"),
        "source_path": provenance.get("source_path"),
        "source_sha256": provenance.get("source_sha256"),
        "source_file": provenance.get("source_file"),
        "normalized_file_sha256": provenance.get("normalized_file_sha256"),
        "source_span": provenance.get("source_span", {}),
    }


def _source_provenance_for_shishuo(root: Path, metadata: Mapping[str, Any]) -> dict[str, Any]:
    provenance = entry_provenance(metadata)
    source_path = provenance.get("source_path")
    source_sha256 = provenance.get("source_sha256")
    witness_id = "shishuo-kanripo-wyg"
    if not source_path or not source_sha256:
        # Repaired entries intentionally have no Kanripo payload locator. Their
        # front matter records an SBCK page path, whose committed lock record
        # supplies the trusted hash without adding raw source text.
        locations = metadata.get("source_locations")
        if isinstance(locations, str):
            try:
                locations = json.loads(locations)
            except json.JSONDecodeError:
                locations = None
        if isinstance(locations, list) and locations:
            first = locations[0]
            if isinstance(first, Mapping):
                source_path = first.get("path")
                lock_path = root / "sources/downloads/shishuo/wikisource-sbck/manifest.lock.json"
                if lock_path.is_file():
                    lock = json.loads(lock_path.read_text(encoding="utf-8"))
                    for record in lock.get("records", []):
                        if isinstance(record, Mapping) and record.get("path") == source_path:
                            source_sha256 = record.get("sha256")
                            witness_id = record.get("witness_id", "shishuo-wikisource-sbck")
                            break
    return {
        "witness_id": witness_id,
        "source_path": source_path,
        "source_sha256": source_sha256,
        "source_normalized_filename": provenance.get("source_normalized_filename"),
        "source_chapter": provenance.get("source_chapter"),
        "FILE": provenance.get("FILE"),
        "source_span": provenance.get("source_span", {}),
    }


def _current_identity_maps(root: Path) -> tuple[set[str], dict[str, set[str]], dict[str, str]]:
    people = read_json(root, PEOPLE_PATH).get("people", [])
    current_ids = {
        str(item.get("person_id"))
        for item in people
        if isinstance(item, Mapping) and isinstance(item.get("person_id"), str)
    }
    surface_to_ids: dict[str, set[str]] = defaultdict(set)
    for person in people:
        if not isinstance(person, Mapping):
            continue
        person_id = person.get("person_id")
        name = person.get("canonical_name")
        if isinstance(person_id, str) and isinstance(name, str):
            surface_to_ids[name].add(person_id)
    for alias in read_json(root, ALIASES_PATH).get("aliases", []):
        if not isinstance(alias, Mapping):
            continue
        surface = alias.get("surface")
        if not isinstance(surface, str) or not surface:
            continue
        mode = alias.get("resolution_mode")
        alias_type = alias.get("alias_type")
        # Only stable exact identity aliases can identify a biography seed.
        if mode not in {"exact", None} and alias_type not in {"personal_name", "courtesy_name", "orthographic_variant"}:
            continue
        ids = alias.get("person_ids", alias.get("resolved_person_ids", []))
        if isinstance(ids, list):
            surface_to_ids[surface].update(value for value in ids if value in current_ids)
    canonical = {
        str(item.get("person_id")): str(item.get("canonical_name"))
        for item in people
        if isinstance(item, Mapping)
        and isinstance(item.get("person_id"), str)
        and isinstance(item.get("canonical_name"), str)
    }
    return current_ids, surface_to_ids, canonical


def _extract_identity_cue(title: str, clean_text: str) -> tuple[str | None, str | None, str | None]:
    """Extract a local `X字Y`/`X名Y` style cue from a biography unit.

    The first two Han characters after 字/名/諱/小字 are used because the
    processed Jinshu text places the next prose immediately after the usual
    two-character courtesy name.  This is a deterministic locator, not an
    interpretation of the biography.
    """

    if not title or title not in clean_text:
        return None, None, None
    escaped = re.escape(title)
    pattern = re.compile(rf"{escaped}(字|名|諱|小字)([{HAN}]{{1,4}})")
    match = pattern.search(clean_text[:1800])
    if not match:
        return None, None, None
    cue = match.group(1)
    tail = match.group(2)
    # Two-character courtesy names are the overwhelmingly stable form in the
    # processed units.  Preserve one-character forms when that is all that is
    # available, without inventing a longer alias.
    alias = tail[:2]
    return alias, cue, match.group(0)


def _title_has_role_marker(title: str) -> bool:
    return any(marker in title for marker in ROLE_MARKERS)


def _is_stable_name_title(title: str, cue: str | None) -> bool:
    return cue in {"字", "名", "諱", "小字"} and _han_only(title) and 2 <= len(title) <= 4 and not _title_has_role_marker(title)


def _candidate_id(name: str, courtesy: str | None, unit_ids: Iterable[str]) -> str:
    ordered = sorted(unit_ids)
    first = ordered[0] if ordered else "materialized"
    suffix = _stable_hash(name, courtesy or "", *ordered)[:12]
    return f"candidate-identity-{first}-{suffix}"


def _surface_type_for_title(surface: str) -> str:
    for suffix, kind in TITLE_SUFFIXES_SORTED:
        if surface.endswith(suffix):
            return kind
    return "unknown_person_like_surface"


def _find_title_like_surfaces(text: str) -> list[tuple[int, int, str, str]]:
    results: list[tuple[int, int, str, str]] = []
    masked = mask_markup_comments(text)
    for suffix, kind in TITLE_SUFFIXES_SORTED:
        # Keep a short surname/title prefix.  This deliberately does not scan
        # arbitrary 2–4 character strings as names.
        for match in re.finditer(rf"([{HAN}]{{1,3}}{re.escape(suffix)})", masked):
            surface = match.group(1)
            if surface in GENERIC_TITLES or len(surface) <= len(suffix):
                continue
            results.append((match.start(1), match.end(1), surface, kind))
    for title in sorted(GENERIC_TITLES, key=lambda item: (-len(item), item)):
        for match in re.finditer(re.escape(title), masked):
            results.append((match.start(), match.end(), title, _surface_type_for_title(title)))
    # Same textual range can be found by a broad suffix and a specific suffix;
    # retain one deterministic row.
    unique: dict[tuple[int, int, str], tuple[int, int, str, str]] = {}
    for row in results:
        unique[(row[0], row[1], row[2])] = row
    return sorted(unique.values(), key=lambda row: (row[0], row[1], row[2]))


def _evidence_id(kind: str, candidate_id: str, source: str, source_id: str, section: str, surface: str, offset: int) -> str:
    return f"evidence-p3a1-{_stable_hash(kind, candidate_id, source, source_id, section, surface, offset)[:20]}"


def _evidence_record(
    *,
    evidence_id: str,
    candidate_id: str | None,
    kind: str,
    source: str,
    source_id: str,
    section: str,
    surface: str,
    quote: str,
    locator: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "id": evidence_id,
        "candidate_id": candidate_id,
        "evidence_kind": kind,
        "source": source,
        "source_id": source_id,
        "section": section,
        "surface": surface,
        "quote": quote[:240],
        "locator": dict(locator),
        "review_status": "candidate",
    }


def _ordered_story_ids(values: Iterable[str], corpus_order: Mapping[str, int]) -> list[str]:
    return sorted(set(values), key=lambda item: (corpus_order.get(item, 10**9), item))


def build_discovery(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any], str]:
    converter = OpenCC("t2s")
    current_ids, current_surface_ids, current_names = _current_identity_maps(root)
    corpus_entries = read_json(root, CORPUS_INDEX_PATH).get("entries", [])
    corpus_order = {
        str(entry.get("id")): int(entry.get("global_ordinal", 10**9))
        for entry in corpus_entries
        if isinstance(entry, Mapping) and isinstance(entry.get("id"), str)
    }
    gold = read_json(root, Path("data/story-chain-gold-set.json"))
    current_sc1_story_ids = [str(item["entry_id"]) for item in gold.get("records", [])]
    current_sc1_story_set = set(current_sc1_story_ids)

    # --- Jinshu structured identity seeds ---------------------------------
    unit_index = read_json(root, JINSHU_INDEX_PATH).get("units", [])
    seeds_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    unit_seed_rows: list[dict[str, Any]] = []
    evidence: dict[str, dict[str, Any]] = {}
    jinshu_search_units: list[dict[str, Any]] = []

    for unit in sorted(
        (item for item in unit_index if isinstance(item, Mapping) and item.get("unit_kind") == "biography"),
        key=lambda item: (int(item.get("volume_number") or 10**9), str(item.get("unit_id"))),
    ):
        unit_id = str(unit.get("unit_id"))
        relative_path = Path(str(unit.get("file_path")))
        path = root / relative_path
        if not path.is_file():
            continue
        raw = path.read_text(encoding="utf-8")
        metadata = parse_frontmatter(raw)
        if "## Original source (exact)\n\n" not in raw:
            continue
        body = raw.split("## Original source (exact)\n\n", 1)[1]
        clean_body = _clean_unit_text(body)
        title = _clean_title(metadata.get("title") or unit.get("title"))
        jinshu_search_units.append(
            {
                "unit_id": unit_id,
                "body": clean_body,
                "path": relative_path,
                "metadata": metadata,
            }
        )
        courtesy, cue, matched = _extract_identity_cue(title, clean_body)
        if cue is None:
            continue

        matched_current = set(current_surface_ids.get(title, set()))
        # A structured Jinshu heading is retained as an identity seed only
        # when it is a full name-shaped subject. Relationship headings and
        # one-character headings are reviewed as surfaces, not Persons.
        if not matched_current and not (
            2 <= len(title) <= 4
            and _han_only(title)
            and not _title_has_role_marker(title)
        ):
            continue
        key = (title, courtesy or "")
        if matched_current:
            seed = seeds_by_key.setdefault(
                key,
                {
                    "name": title,
                    "courtesy": courtesy,
                    "unit_ids": set(),
                    "unit_rows": [],
                    "identity_evidence_ids": set(),
                    "matched_person_ids": set(),
                    "full_name_attestation_count": 0,
                    "explicit_identity_link_count": 0,
                    "source_layers": {"jinshu"},
                    "cue": cue,
                    "preferred_name": None,
                },
            )
            seed["matched_person_ids"].update(matched_current)
        else:
            seed = seeds_by_key.setdefault(
                key,
                {
                    "name": title,
                    "courtesy": courtesy,
                    "unit_ids": set(),
                    "unit_rows": [],
                    "identity_evidence_ids": set(),
                    "matched_person_ids": set(),
                    "full_name_attestation_count": 0,
                    "explicit_identity_link_count": 0,
                    "source_layers": {"jinshu"},
                    "cue": cue,
                    "preferred_name": None,
                },
            )
        seed["unit_ids"].add(unit_id)
        seed["unit_rows"].append({"unit_id": unit_id, "title": title, "path": str(relative_path), "cue": cue})
        seed["full_name_attestation_count"] += 1
        seed["explicit_identity_link_count"] += 1
        seed["matched_person_ids"].update(matched_current)
        if matched_current:
            seed["preferred_name"] = current_names[sorted(matched_current)[0]]

        cue_offset = clean_body.find(matched or title)
        evidence_id = _evidence_id("identity_seed", _candidate_id(title, courtesy, [unit_id]), "jinshu", unit_id, "unit_text", title, max(cue_offset, 0))
        provenance = _source_provenance_for_jinshu(metadata)
        evidence[evidence_id] = _evidence_record(
            evidence_id=evidence_id,
            candidate_id=None,
            kind="jinshu_identity_seed",
            source="jinshu",
            source_id=unit_id,
            section="unit_text",
            surface=title,
            quote=source_context(clean_body, max(cue_offset, 0), max(cue_offset, 0) + len(matched or title), 110),
            locator={
                "artifact_type": "jinshu_unit",
                "unit_id": unit_id,
                "artifact_path": str(relative_path),
                "artifact_sha256": _sha256(path),
                "source_provenance": provenance,
                "identity_cue": cue,
                "courtesy_name": courtesy,
            },
        )
        seed["identity_evidence_ids"].add(evidence_id)
        unit_seed_rows.append({"unit_id": unit_id, "title": title, "courtesy": courtesy, "cue": cue})

    # Candidate IDs are assigned after grouping, making repeated builds and
    # source ordering independent of Python dict/set implementation details.
    seeds: list[dict[str, Any]] = []
    for key, seed in sorted(seeds_by_key.items(), key=lambda item: item[0]):
        seed["candidate_id"] = _candidate_id(seed["name"], seed["courtesy"], seed["unit_ids"])
        seed["matched_person_ids"] = set(seed["matched_person_ids"])
        seeds.append(seed)

    # Include registry-only current Persons as explicit rediscovery controls.
    # Wang Ningzhi and 郗璿 do not have a dedicated Jinshu biography seed in
    # the existing unit material, but they must still be excluded from any
    # open-world expansion result.
    seeded_current = {
        person_id
        for seed in seeds
        for person_id in seed["matched_person_ids"]
    }
    for person_id in sorted(current_ids - seeded_current):
        name = current_names[person_id]
        seeds.append(
            {
                "name": name,
                "preferred_name": name,
                "courtesy": None,
                "cue": None,
                "unit_ids": set(),
                "unit_rows": [],
                "identity_evidence_ids": set(),
                "matched_person_ids": {person_id},
                "full_name_attestation_count": 0,
                "explicit_identity_link_count": 0,
                "source_layers": {"registry"},
                "candidate_id": _candidate_id(name, None, []),
            }
        )
    name_to_seed_ids: dict[str, list[str]] = defaultdict(list)
    for seed in seeds:
        name_to_seed_ids[seed["name"]].append(seed["candidate_id"])

    # Re-key the identity evidence candidate ID now that the final candidate
    # ID is known.  Evidence IDs remain stable because they were based on the
    # same deterministic seed key; only the owning candidate is attached.
    for seed in seeds:
        for evidence_id in seed["identity_evidence_ids"]:
            evidence[evidence_id]["candidate_id"] = seed["candidate_id"]

    # Add a small, conservative bridge for full names visible in the current
    # SC1 stories when the same exact form is present in processed Jinshu.
    # Requiring two current Stories prevents ordinary three-character prose
    # fragments from entering the identity registry; the resulting status is
    # still `candidate`, not `strong_candidate`, because no explicit local
    # courtesy-name cue has been established for that subject.
    current_name_counts: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"story_ids": set(), "contexts": []}
    )
    for entry_path in sorted((root / SHISHUO_ENTRIES_PATH).rglob("entry-*.md")):
        raw = entry_path.read_text(encoding="utf-8")
        metadata = parse_frontmatter(raw)
        story_id = str(metadata.get("entry_id"))
        if story_id not in current_sc1_story_set:
            continue
        for section, text, _section_metadata in parse_shishuo_sections(raw):
            masked = mask_markup_comments(text)
            for match in re.finditer(rf"([{HAN}]{{3}})", masked):
                surface = match.group(1)
                if surface in GENERIC_TITLES or _title_has_role_marker(surface):
                    continue
                if surface.startswith("小") or surface.endswith("也") or any(char in surface for char in ("字", "曰", "謂")):
                    continue
                if _surface_type_for_title(surface) != "unknown_person_like_surface":
                    continue
                if current_surface_ids.get(surface):
                    continue
                row = current_name_counts[surface]
                row["story_ids"].add(story_id)
                if len(row["contexts"]) < 4:
                    row["contexts"].append(
                        {
                            "entry_id": story_id,
                            "section": section,
                            "offset": match.start(),
                            "quote": source_context(text, match.start(), match.end()),
                            "path": str(entry_path.relative_to(root)),
                            "metadata": metadata,
                        }
                    )
    for surface, row in sorted(current_name_counts.items()):
        if len(row["story_ids"]) < 2 or any(surface in seed["name"] for seed in seeds):
            continue
        supporting_units = [unit for unit in jinshu_search_units if surface in unit["body"]]
        if not supporting_units:
            continue
        seeds_by_key[(surface, "")] = {
            "name": surface,
            "preferred_name": surface,
            "courtesy": None,
            "cue": "repeated_full_name_cross_source",
            "unit_ids": {unit["unit_id"] for unit in supporting_units[:5]},
            "unit_rows": [],
            "identity_evidence_ids": set(),
            "matched_person_ids": set(),
            "full_name_attestation_count": len(row["story_ids"]),
            "explicit_identity_link_count": 0,
            "source_layers": {"shishuo", "jinshu"},
            "repeated_full_name_contexts": row["contexts"],
            "cross_source_name_candidate": True,
        }
        seed = seeds_by_key[(surface, "")]
        # A deterministic identity evidence record is attached to the first
        # Story context; Jinshu support remains recorded in the seed metrics.
        context = row["contexts"][0]
        evidence_id = _evidence_id("cross_source_name", surface, "shishuo", context["entry_id"], context["section"], surface, context["offset"])
        evidence[evidence_id] = _evidence_record(
            evidence_id=evidence_id,
            candidate_id=None,
            kind="cross_source_full_name_attestation",
            source="shishuo",
            source_id=context["entry_id"],
            section=context["section"],
            surface=surface,
            quote=context["quote"],
            locator={
                "artifact_type": "shishuo_entry",
                "entry_id": context["entry_id"],
                "artifact_path": context["path"],
                "artifact_sha256": _sha256(root / context["path"]),
                "section_offset": context["offset"],
                "source_provenance": _source_provenance_for_shishuo(root, context["metadata"]),
                "jinshu_support_unit_ids": sorted(seed["unit_ids"]),
            },
        )
        seed["identity_evidence_ids"].add(evidence_id)

    # Rebuild deterministic seed list after cross-source candidates were
    # appended.
    seeds = []
    for key, seed in sorted(seeds_by_key.items(), key=lambda item: item[0]):
        seed["candidate_id"] = _candidate_id(seed["name"], seed["courtesy"], seed["unit_ids"])
        seed["matched_person_ids"] = set(seed["matched_person_ids"])
        seeds.append(seed)
    for seed in seeds:
        for evidence_id in seed["identity_evidence_ids"]:
            evidence[evidence_id]["candidate_id"] = seed["candidate_id"]
    name_to_seed_ids = defaultdict(list)
    seeded_current = {person_id for seed in seeds for person_id in seed["matched_person_ids"]}
    for person_id in sorted(current_ids - seeded_current):
        name = current_names[person_id]
        seed = {
            "name": name,
            "preferred_name": name,
            "courtesy": None,
            "cue": None,
            "unit_ids": set(),
            "unit_rows": [],
            "identity_evidence_ids": set(),
            "matched_person_ids": {person_id},
            "full_name_attestation_count": 0,
            "explicit_identity_link_count": 0,
            "source_layers": {"registry"},
            "candidate_id": _candidate_id(name, None, []),
        }
        seeds.append(seed)
    for seed in seeds:
        name_to_seed_ids[seed["name"]].append(seed["candidate_id"])

    # --- Shishuo/Liu occurrence and surface discovery --------------------
    candidate_by_surface: dict[str, list[tuple[dict[str, Any], str]]] = defaultdict(list)
    for seed in seeds:
        if not current_surface_ids.get(seed["name"]) or seed.get("matched_person_ids"):
            candidate_by_surface[seed["name"]].append((seed, "personal_name"))
        simplified_name = converter.convert(seed["name"])
        if simplified_name != seed["name"] and (not current_surface_ids.get(simplified_name) or seed.get("matched_person_ids")):
            candidate_by_surface[simplified_name].append((seed, "orthographic_variant"))
        if seed.get("courtesy"):
            if not current_surface_ids.get(seed["courtesy"]) or seed.get("matched_person_ids"):
                candidate_by_surface[seed["courtesy"]].append((seed, "courtesy_name"))
            simplified_courtesy = converter.convert(seed["courtesy"])
            if simplified_courtesy != seed["courtesy"] and (not current_surface_ids.get(simplified_courtesy) or seed.get("matched_person_ids")):
                candidate_by_surface[simplified_courtesy].append((seed, "orthographic_variant"))
            if len(seed["name"]) >= 1:
                surname_plus_courtesy = seed["name"][0] + seed["courtesy"]
                if not current_surface_ids.get(surname_plus_courtesy) or seed.get("matched_person_ids"):
                    candidate_by_surface[surname_plus_courtesy].append((seed, "surname_plus_courtesy_name"))

    candidate_rows: dict[str, dict[str, Any]] = {}
    occurrences: list[dict[str, Any]] = []
    surface_rows: dict[str, dict[str, Any]] = {}
    occurrence_evidence_ids: dict[str, set[str]] = defaultdict(set)

    def ensure_candidate_row(seed: Mapping[str, Any]) -> dict[str, Any]:
        candidate_id = str(seed["candidate_id"])
        return candidate_rows.setdefault(
            candidate_id,
            {
                "candidate_id": candidate_id,
                "preferred_name": seed.get("preferred_name") or seed["name"],
                "status": "strong_candidate" if _is_stable_name_title(seed["name"], seed.get("cue")) else "candidate",
                "matched_person_id": sorted(seed["matched_person_ids"])[0] if seed["matched_person_ids"] else None,
                "materialization_state": "already_materialized" if seed["matched_person_ids"] else "new_candidate",
                "surfaces": {},
                "identity_evidence_ids": sorted(seed["identity_evidence_ids"]),
                "metrics": {
                    "shishuo_main_story_count": 0,
                    "shishuo_annotation_story_count": 0,
                    "shishuo_main_occurrence_count": 0,
                    "shishuo_annotation_occurrence_count": 0,
                    "jinshu_unit_count": len(seed["unit_ids"]),
                    "full_name_attestation_count": seed["full_name_attestation_count"],
                    "explicit_identity_link_count": seed["explicit_identity_link_count"],
                },
                "shishuo_story_ids": set(),
                "current_sc1_story_ids": set(),
                "current_sc1_occurrence_count": 0,
                "risk_flags": set(),
                "identity_basis": ["structured_jinshu_biography_subject", "explicit_name_identity_cue"],
            },
        )

    def add_surface(seed: Mapping[str, Any], surface: str, surface_type: str, mode: str, strength: str, source: str, evidence_ids: Iterable[str], occurrence_count: int = 1) -> None:
        row = ensure_candidate_row(seed)
        existing = row["surfaces"].get(surface)
        if existing is None:
            row["surfaces"][surface] = {
                "surface": surface,
                "surface_type": surface_type,
                "association_mode": mode,
                "association_strength": strength,
                "source_layers": [source],
                "evidence_ids": sorted(set(evidence_ids)),
                "occurrence_count": occurrence_count,
            }
        else:
            existing["source_layers"] = sorted(set(existing["source_layers"]) | {source})
            existing["evidence_ids"] = sorted(set(existing["evidence_ids"]) | set(evidence_ids))
            existing["occurrence_count"] += occurrence_count
            if strength == "strong":
                existing["association_strength"] = "strong"
            if mode == "contextual":
                existing["association_mode"] = "contextual"

    for seed in seeds:
        row = ensure_candidate_row(seed)
        add_surface(seed, seed["name"], "personal_name", "exact", "strong", "jinshu", seed["identity_evidence_ids"])
        if seed.get("courtesy"):
            add_surface(seed, seed["courtesy"], "courtesy_name", "exact", "strong", "jinshu", seed["identity_evidence_ids"])

    # Scan each processed section once for all known exact surfaces.  The
    # look-ahead preserves overlapping occurrences while avoiding a full
    # section rescan for every Jinshu seed.
    exact_surface_pattern = None
    exact_surfaces_by_initial: dict[str, list[str]] = defaultdict(list)
    if candidate_by_surface:
        for surface in candidate_by_surface:
            exact_surfaces_by_initial[surface[0]].append(surface)
        for values in exact_surfaces_by_initial.values():
            values.sort(key=lambda value: (-len(value), value))
        alternatives = "|".join(
            re.escape(surface)
            for surface in sorted(candidate_by_surface, key=lambda value: (-len(value), value))
        )
        exact_surface_pattern = re.compile(rf"(?=(?P<surface>{alternatives}))")

    entry_files = sorted((root / SHISHUO_ENTRIES_PATH).rglob("entry-*.md"))
    section_cache: dict[str, list[dict[str, Any]]] = {}
    for path in entry_files:
        raw = path.read_text(encoding="utf-8")
        metadata = parse_frontmatter(raw)
        story_id = str(metadata.get("entry_id"))
        sections = parse_shishuo_sections(raw)
        section_rows: list[dict[str, Any]] = []
        for section, text, section_metadata in sections:
            section_rows.append({"section": section, "text": text, "masked": mask_markup_comments(text), "metadata": section_metadata})
        section_cache[story_id] = section_rows
        provenance = _source_provenance_for_shishuo(root, metadata)

        # Exact candidate name/courtesy surfaces.
        for section_row in section_rows:
            section = section_row["section"]
            text = section_row["text"]
            masked = section_row["masked"]
            if exact_surface_pattern is not None:
                for match in exact_surface_pattern.finditer(masked):
                    start = match.start()
                    for surface in exact_surfaces_by_initial.get(masked[start], []):
                        if not masked.startswith(surface, start):
                            continue
                        matching_entries = candidate_by_surface[surface]
                        # A surface shared by distinct discovered identities is
                        # not assigned to either identity without a stronger local
                        # distinction.
                        matching_seed_ids = {entry[0]["candidate_id"] for entry in matching_entries}
                        if len(matching_seed_ids) != 1:
                            continue
                        seed = matching_entries[0][0]
                        row = ensure_candidate_row(seed)
                        kind = matching_entries[0][1]
                        end = start + len(surface)
                        eid = _evidence_id("shishuo_occurrence", seed["candidate_id"], "shishuo", story_id, section, surface, start)
                        evidence[eid] = _evidence_record(
                            evidence_id=eid,
                            candidate_id=seed["candidate_id"],
                            kind="shishuo_candidate_occurrence",
                            source="shishuo",
                            source_id=story_id,
                            section=section,
                            surface=surface,
                            quote=source_context(text, start, end),
                            locator={
                                "artifact_type": "shishuo_entry",
                                "entry_id": story_id,
                                "chapter_id": metadata.get("chapter_id"),
                                "artifact_path": str(path.relative_to(root)),
                                "artifact_sha256": _sha256(path),
                                "section_offset": start,
                                "source_provenance": provenance,
                            },
                        )
                        occurrence_evidence_ids[seed["candidate_id"]].add(eid)
                        occurrence_id = f"occurrence-p3a1-{_stable_hash(seed['candidate_id'], story_id, section, surface, start)[:20]}"
                        occurrences.append({
                            "occurrence_id": occurrence_id,
                            "candidate_id": seed["candidate_id"],
                            "source": "shishuo",
                            "source_id": story_id,
                            "section": section,
                            "surface": surface,
                            "surface_type": kind,
                            "association_mode": "exact",
                            "confidence": "strong_candidate",
                            "evidence_ids": [eid],
                            "offset": start,
                        })
                        add_surface(seed, surface, kind, "exact", "strong", "shishuo", [eid])
                        row["shishuo_story_ids"].add(story_id)
                        if section == "main_text":
                            row["metrics"]["shishuo_main_occurrence_count"] += 1
                        elif section == "liu_annotation":
                            row["metrics"]["shishuo_annotation_occurrence_count"] += 1
                        if story_id in current_sc1_story_set:
                            row["current_sc1_story_ids"].add(story_id)
                            row["current_sc1_occurrence_count"] += 1

        # Person-like title surfaces.  These remain unresolved unless a
        # distinct seed identity appears in the same local source context.
        # Keep section-local offsets rather than searching in React or
        # collapsing main text and Liu annotation into one layer.
        for section_row in section_rows:
            section = section_row["section"]
            text = section_row["text"]
            masked = section_row["masked"]
            for start, end, surface, surface_type in _find_title_like_surfaces(text):
                generic = surface in GENERIC_TITLES
                possible = [
                    seed for seed in seeds
                    if seed["name"]
                    and not generic
                    and surface.startswith(seed["name"][0])
                    and seed["name"] != surface
                ]
                # A title can attach only if a unique exact full name appears
                # in the same section, or if a unique exact name appears in a
                # different layer of the same Story.  The latter is retained
                # as medium/contextual evidence, never as an exact alias.
                name_variants = {
                    seed["name"]: {seed["name"], converter.convert(seed["name"])}
                    for seed in possible
                }
                same_section = [
                    seed for seed in possible
                    if any(re.search(re.escape(variant), masked) for variant in name_variants[seed["name"]])
                ]
                same_story = [
                    seed for seed in possible
                    if any(
                        any(re.search(re.escape(variant), other["masked"]) for variant in name_variants[seed["name"]])
                        for other in section_rows
                    )
                ]
                attached = same_section if len(same_section) == 1 else (same_story if len(same_story) == 1 else [])
                if attached:
                    seed = attached[0]
                    strength = "strong" if seed in same_section else "medium"
                    eid = _evidence_id("contextual_occurrence", seed["candidate_id"], "shishuo", story_id, section, surface, start)
                    evidence[eid] = _evidence_record(
                        evidence_id=eid,
                        candidate_id=seed["candidate_id"],
                        kind="shishuo_contextual_surface",
                        source="shishuo",
                        source_id=story_id,
                        section=section,
                        surface=surface,
                        quote=source_context(text, start, end),
                        locator={
                            "artifact_type": "shishuo_entry",
                            "entry_id": story_id,
                            "chapter_id": metadata.get("chapter_id"),
                            "artifact_path": str(path.relative_to(root)),
                            "artifact_sha256": _sha256(path),
                            "section_offset": start,
                            "source_provenance": provenance,
                        },
                    )
                    occurrence_id = f"occurrence-p3a1-{_stable_hash(seed['candidate_id'], story_id, section, surface, start)[:20]}"
                    occurrences.append({
                        "occurrence_id": occurrence_id,
                        "candidate_id": seed["candidate_id"],
                        "source": "shishuo",
                        "source_id": story_id,
                        "section": section,
                        "surface": surface,
                        "surface_type": surface_type,
                        "association_mode": "contextual",
                        "confidence": "strong_candidate" if strength == "strong" else "candidate",
                        "evidence_ids": [eid],
                        "offset": start,
                    })
                    row = ensure_candidate_row(seed)
                    add_surface(seed, surface, surface_type, "contextual", strength, "shishuo", [eid])
                    row["shishuo_story_ids"].add(story_id)
                    row["risk_flags"].add("contextual_surface_association")
                    if section == "main_text":
                        row["metrics"]["shishuo_main_occurrence_count"] += 1
                    else:
                        row["metrics"]["shishuo_annotation_occurrence_count"] += 1
                    if story_id in current_sc1_story_set:
                        row["current_sc1_story_ids"].add(story_id)
                        row["current_sc1_occurrence_count"] += 1
                    occurrence_evidence_ids[seed["candidate_id"]].add(eid)
                    continue

                # A generic or unattached title remains a surface cluster and
                # is never emitted as a candidate identity.
                cluster = surface_rows.setdefault(
                    surface,
                    {
                        "surface": surface,
                        "surface_type": surface_type,
                        "occurrence_count": 0,
                        "story_ids": set(),
                        "source_layers": set(),
                        "candidate_identity_options": set(),
                        "classification": "generic_title" if generic else "potential_new_candidate_surface",
                        "reason_code": "generic_title_no_stable_identity" if generic else "no_local_identity_bridge",
                    },
                )
                cluster["occurrence_count"] += 1
                cluster["story_ids"].add(story_id)
                cluster["source_layers"].add(section)
                cluster["candidate_identity_options"].update(seed["candidate_id"] for seed in possible)

    # Add source-layer metrics and final status/risk data.
    for seed in seeds:
        row = ensure_candidate_row(seed)
        row["metrics"]["shishuo_main_story_count"] = len({
            occurrence["source_id"] for occurrence in occurrences
            if occurrence["candidate_id"] == seed["candidate_id"] and occurrence["section"] == "main_text"
        })
        row["metrics"]["shishuo_annotation_story_count"] = len({
            occurrence["source_id"] for occurrence in occurrences
            if occurrence["candidate_id"] == seed["candidate_id"] and occurrence["section"] == "liu_annotation"
        })
        if len(name_to_seed_ids[seed["name"]]) > 1:
            row["status"] = "ambiguous"
            row["risk_flags"].add("possible_same_name_people")
        if len(seed["name"]) == 1:
            row["status"] = "candidate" if row["status"] != "already_materialized" else row["status"]
            row["risk_flags"].add("no_full_name")
        if not row["metrics"]["shishuo_main_story_count"] and not row["metrics"]["shishuo_annotation_story_count"]:
            row["risk_flags"].add("jinshu_only")
        if row["status"] == "strong_candidate" and len(seed["unit_ids"]) == 1:
            row["risk_flags"].add("single_source_unit")
        if row["matched_person_id"]:
            row["status"] = "already_materialized"
        row["surfaces"] = [
            row["surfaces"][surface]
            for surface in sorted(row["surfaces"], key=lambda value: (
                {"personal_name": 0, "courtesy_name": 1, "surname_plus_courtesy_name": 2}.get(row["surfaces"][value]["surface_type"], 9), value
            ))
        ]
        row["identity_evidence_ids"] = sorted(set(row["identity_evidence_ids"]))
        row["evidence_ids"] = sorted(occurrence_evidence_ids.get(seed["candidate_id"], set()))
        row["shishuo_story_ids"] = _ordered_story_ids(row["shishuo_story_ids"], corpus_order)
        row["current_sc1_story_ids"] = _ordered_story_ids(row["current_sc1_story_ids"], corpus_order)
        row["risk_flags"] = sorted(row["risk_flags"])
        if row["status"] == "strong_candidate" and "contextual_surface_association" in row["risk_flags"]:
            row["identity_basis"].append("local_contextual_surface_bridge_recorded_separately")
        row["identity_basis"] = sorted(set(row["identity_basis"]))

    # A candidate occurrence must never expose a production person_id field.
    occurrences = [
        occurrence
        for occurrence in occurrences
        if candidate_rows.get(occurrence["candidate_id"], {}).get("materialization_state") == "new_candidate"
    ]
    occurrences.sort(key=lambda item: (
        corpus_order.get(str(item["source_id"]), 10**9),
        str(item["source_id"]),
        0 if item["section"] == "main_text" else 1,
        int(item.get("offset", 10**9)),
        str(item["candidate_id"]),
    ))
    occurrence_document = {
        "schema": 1,
        "stage": "p3a1-person-candidate-occurrences",
        "generated_from": [str(OUTPUT_PATH), str(SHISHUO_ENTRIES_PATH), str(CORPUS_INDEX_PATH)],
        "occurrence_count": len(occurrences),
        "occurrences": occurrences,
        "notes": [
            "Candidate occurrences are exploratory navigation evidence, not reviewed Mention records.",
            "No occurrence contains a production person_id; source layer and association mode remain explicit.",
        ],
    }

    unresolved = []
    for surface, row in sorted(surface_rows.items(), key=lambda item: (-item[1]["occurrence_count"], item[0])):
        unresolved.append({
            "surface": surface,
            "surface_type": row["surface_type"],
            "classification": row["classification"],
            "reason_code": row["reason_code"],
            "occurrence_count": row["occurrence_count"],
            "story_ids": _ordered_story_ids(row["story_ids"], corpus_order),
            "source_layers": sorted(row["source_layers"], key=lambda value: (0 if value == "main_text" else 1, value)),
            "candidate_identity_options": sorted(row["candidate_identity_options"]),
            "not_ranked_as_person": True,
        })

    candidates = []
    for candidate_id in sorted(candidate_rows):
        row = candidate_rows[candidate_id]
        row["metrics"]["current_sc1_story_count"] = len(row["current_sc1_story_ids"])
        row["metrics"]["current_sc1_occurrence_count"] = row["current_sc1_occurrence_count"]
        row["current_sc1_story_ids"] = list(row["current_sc1_story_ids"])
        candidates.append(row)
    candidates.sort(key=lambda row: (row["preferred_name"], row["candidate_id"]))

    current_gaps: list[dict[str, Any]] = []
    by_story: dict[str, list[dict[str, Any]]] = defaultdict(list)
    candidate_map = {row["candidate_id"]: row for row in candidates}
    for occurrence in occurrences:
        if occurrence["source_id"] in current_sc1_story_set:
            by_story[occurrence["source_id"]].append(occurrence)
    for story_id in current_sc1_story_ids:
        rows = by_story.get(story_id, [])
        if not rows:
            continue
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for occurrence in rows:
            candidate = candidate_map.get(occurrence["candidate_id"])
            if candidate and candidate["materialization_state"] == "new_candidate":
                grouped[occurrence["candidate_id"]].append(occurrence)
        if grouped:
            current_gaps.append({
                "story_id": story_id,
                "candidates": [
                    {
                        "candidate_id": candidate_id,
                        "preferred_name": candidate_map[candidate_id]["preferred_name"],
                        "surfaces": sorted({item["surface"] for item in rows}),
                        "sections": sorted({item["section"] for item in rows}),
                        "evidence_strengths": sorted({item["confidence"] for item in rows}),
                    }
                    for candidate_id, rows in sorted(grouped.items())
                ],
            })

    status_counts = Counter(row["status"] for row in candidates)
    discovery_document = {
        "schema": 1,
        "stage": "p3a1-open-world-person-discovery",
        "generated_from": [
            str(PEOPLE_PATH),
            str(ALIASES_PATH),
            str(CORPUS_INDEX_PATH),
            str(JINSHU_INDEX_PATH),
            str(SHISHUO_ENTRIES_PATH),
            str(JINSHU_UNITS_PATH),
            str(SC1_BUNDLE_PATH),
        ],
        "discovery_policy": {
            "identity_seeds": [
                "processed Jinshu biography/unit subjects",
                "explicit local name/courtesy-name identity cues",
            ],
            "shishuo_surface_policy": "full names and courtesy names are exact only; title-like surfaces require a unique local exact-name bridge and remain contextual",
            "generic_titles": sorted(GENERIC_TITLES),
            "unresolved_surface_policy": "unattached or generic surfaces are retained as clusters and never emitted as Person identities",
            "p3a_eligible_statuses": ["strong_candidate"],
            "production_materialization": "forbidden in P3A.1",
        },
        "input_counts": {
            "scoped_person_count": len(current_ids),
            "canonical_story_count": len(corpus_order),
            "jinshu_biography_unit_count": sum(1 for item in unit_index if isinstance(item, Mapping) and item.get("unit_kind") == "biography"),
            "identity_seed_unit_count": len(unit_seed_rows),
            "current_sc1_story_count": len(current_sc1_story_ids),
        },
        "discovery_counts": {
            "person_like_surface_count": len({*surface_rows, *(surface for row in candidates for surface in [item["surface"] for item in row["surfaces"]])}),
            "candidate_identity_count": len(candidates),
            "already_materialized_count": status_counts.get("already_materialized", 0),
            "strong_candidate_count": status_counts.get("strong_candidate", 0),
            "candidate_count": status_counts.get("candidate", 0),
            "ambiguous_identity_count": status_counts.get("ambiguous", 0),
            "unresolved_surface_count": len(unresolved),
        },
        "current_sc1_open_world_gaps": current_gaps,
        "unresolved_surface_clusters": unresolved,
        "evidence": [evidence[key] for key in sorted(evidence)],
        "candidates": candidates,
        "notes": [
            "Candidate identities are derived review proposals; they are not production Persons.",
            "Surface associations retain exact versus contextual semantics and source-layer distinctions.",
            "No canonical Mention, Person, Relation, PersonStory, Person Sketch, Story, punctuation, or source payload is written by this stage.",
        ],
    }
    report = render_report(discovery_document, occurrence_document)
    return discovery_document, occurrence_document, report


def render_report(document: Mapping[str, Any], occurrence_document: Mapping[str, Any]) -> str:
    counts = document["discovery_counts"]
    candidates = list(document["candidates"])
    strong = [row for row in candidates if row["status"] == "strong_candidate"]
    strong.sort(key=lambda row: (
        -len(row["identity_evidence_ids"]),
        -row["metrics"]["explicit_identity_link_count"],
        -row["metrics"]["full_name_attestation_count"],
        -row["metrics"]["jinshu_unit_count"],
        -row["metrics"]["current_sc1_story_count"],
        -row["metrics"]["shishuo_main_story_count"],
        -row["metrics"]["shishuo_annotation_story_count"],
        row["preferred_name"],
        row["candidate_id"],
    ))
    lines = [
        "# P3A.1 Open-World Person Identity Candidates",
        "",
        "> Review artifact only. This stage does not materialize Persons, Mentions, Relations, PersonStory links, Person Sketches, or Stories.",
        "",
        "## Summary",
        "",
        f"- Person-like surfaces discovered: **{counts['person_like_surface_count']}**",
        f"- Candidate identity records: **{counts['candidate_identity_count']}**",
        f"- Already-materialized rediscoveries: **{counts['already_materialized_count']}**",
        f"- Strong candidates: **{counts['strong_candidate_count']}**",
        f"- Weaker candidates: **{counts['candidate_count']}**",
        f"- Ambiguous identity records: **{counts['ambiguous_identity_count']}**",
        f"- Unresolved surface clusters: **{counts['unresolved_surface_count']}**",
        f"- Candidate occurrence records: **{occurrence_document['occurrence_count']}**",
        "",
        "Identity seeds come from processed Jinshu biography units with explicit local name/courtesy-name cues. Shishuo and Liu text supplies separate exact or contextual occurrence evidence. A title such as `太傅` is never a Person identity by frequency alone.",
        "",
        "## Strong candidates",
        "",
    ]
    if not strong:
        lines.append("No strong open-world identity candidate was formed from the current structured evidence.")
        lines.append("")
    for row in strong[:50]:
        surfaces = row["surfaces"]
        surface_text = ", ".join(
            f"{item['surface']}（{item['surface_type']} · {item['association_mode']}）"
            for item in surfaces
        )
        lines.extend(
            [
                f"### {row['preferred_name']}",
                "",
                f"Candidate ID: `{row['candidate_id']}`",
                f"Status: **{row['status']}**",
                f"Shishuo main text: **{row['metrics']['shishuo_main_story_count']} Stories**; Liu annotation: **{row['metrics']['shishuo_annotation_story_count']} Stories**",
                f"Jinshu support: **{row['metrics']['jinshu_unit_count']} unit(s)**; current SC1 Stories: **{row['metrics']['current_sc1_story_count']}** ({', '.join(row['current_sc1_story_ids']) or 'none'})",
                "",
                f"Observed surfaces: {surface_text or '—'}",
                "",
                "Identity basis:",
                *[f"- {item}" for item in row["identity_basis"]],
                "",
                f"Risks: {', '.join(row['risk_flags']) if row['risk_flags'] else 'none recorded'}",
                "",
            ]
        )
    lines.extend(["## Current SC1 open-world gaps", ""])
    gaps = document.get("current_sc1_open_world_gaps", [])
    if not gaps:
        lines.append("No supported new identity occurrence was found in the current SC1 Story set; unresolved surfaces remain listed separately.")
    else:
        for gap in gaps:
            parts = []
            for candidate in gap["candidates"]:
                parts.append(
                    f"{candidate['preferred_name']} [{', '.join(candidate['surfaces'])}; {', '.join(candidate['sections'])}; {', '.join(candidate['evidence_strengths'])}]"
                )
            lines.append(f"- `{gap['story_id']}` → " + "; ".join(parts))
    lines.extend(["", "## Unresolved surface clusters", "", "These are not Person identities and are not fed to P3A as candidates.", ""])
    for row in document.get("unresolved_surface_clusters", []):
        options = ", ".join(row["candidate_identity_options"]) or "none"
        lines.append(
            f"- `{row['surface']}` — {row['classification']}; {row['occurrence_count']} occurrence(s), {len(row['story_ids'])} Story/ies; options: {options}"
        )
    lines.extend(
        [
            "",
            "## Review boundary",
            "",
            "Only `strong_candidate` records are eligible for the existing P3A ranking by default. P3A.1 does not choose final Person IDs, write canonical Mentions, or promote contextual surfaces to exact aliases. Human review and a later P3B materialization step remain required.",
            "",
        ]
    )
    return "\n".join(lines)


def build(root: Path = ROOT) -> tuple[Path, Path, Path]:
    document, occurrence_document, report = build_discovery(root)
    write_json(root, OUTPUT_PATH, document)
    write_json(root, OCCURRENCES_PATH, occurrence_document)
    (root / REPORT_PATH).write_text(report, encoding="utf-8")
    return root / OUTPUT_PATH, root / OCCURRENCES_PATH, root / REPORT_PATH


if __name__ == "__main__":
    for path in build():
        print(path)
