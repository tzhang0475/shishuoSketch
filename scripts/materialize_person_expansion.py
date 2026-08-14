#!/usr/bin/env python3
"""Materialize the frozen P3B.1 Person Expansion Wave 1.

P3A.1 candidate identities remain reviewable analysis until a frozen wave
manifest is supplied.  This module is the scalable bridge from that manifest
to the existing production Person, Alias, Mention, Evidence and Person Sketch
layers.  It deliberately does not touch Relations, canonical text, or Story
publication selection.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, Mapping

try:
    from .build_six_person_pilot import parse_frontmatter, parse_shishuo_sections
except ImportError:  # direct execution
    from build_six_person_pilot import parse_frontmatter, parse_shishuo_sections


ROOT = Path(__file__).resolve().parents[1]
WAVE_PATH = Path("data/annotation/person-expansion-wave-1.json")
RANKING_PATH = Path("data/derived/person-expansion-candidates.json")
RANKING_SNAPSHOT_PATH = Path("data/derived/person-expansion-wave-1-ranking.json")
P3A1_PATH = Path("data/derived/person-identity-candidates.json")
OCCURRENCES_PATH = Path("data/derived/person-candidate-occurrences.json")
PEOPLE_PATH = Path("data/people.json")
ALIASES_PATH = Path("data/aliases.json")
MENTIONS_PATH = Path("data/mentions/shishuo.json")
EVIDENCE_PATH = Path("data/evidence/wp1-evidence.json")
SKETCH_PATH = Path("data/annotation/person-sketches.json")
CORPUS_INDEX_PATH = Path("data/shishuo-corpus-index.json")
RELATIONS_PATH = Path("data/annotation/wp1-relations.json")
GOLD_PATH = Path("data/story-chain-gold-set.json")
PUNCTUATION_PATH = Path("data/annotation/wp1-punctuation.json")
MATERIALIZATION_PATH = Path("data/derived/person-expansion-wave-1-materialization.json")
REPORT_PATH = Path("docs/person-expansion-wave-1.md")

WAVE_ID = "p3b-wave-1"
WAVE_LABEL = "P3B.1 Wave 1"
SELECTION_SCORE_FIELD = "p3a_score"
SELECTION_TIER_FIELD = "p3a_tier"
MATERIALIZATION_STAGE = "p3b1-person-expansion-materialization"
EXPECTED_WAVE_SIZE = 10
EVIDENCE_PREFIX = "evidence-p3b-wave-1-"
MENTION_PREFIX = "shishuo-p3b-wave-1-"
ALIAS_PREFIX = "alias-p3b-wave-1-"
BLOCKING_FLAGS = {
    "conflicting_identity_evidence",
    "multiple_possible_people",
    "no_full_name",
    "unresolved_identity",
}
EXACT_SURFACE_TYPES = {
    "personal_name",
    "courtesy_name",
    "surname_plus_courtesy_name",
    "orthographic_variant",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def stable_hash(*values: object) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(str(value).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def production_evidence_id(source_evidence_id: str) -> str:
    return EVIDENCE_PREFIX + stable_hash(source_evidence_id)[:24]


def production_alias_id(candidate_id: str, surface: str, surface_type: str) -> str:
    """Allocate a stable analysis Alias ID without embedding a Person ID.

    Existing materialized Alias IDs are preserved by the idempotent path.  A
    future wave starts from its frozen candidate ID, so changing a Person's
    opaque primary key cannot silently rename its aliases.
    """

    return ALIAS_PREFIX + stable_hash(candidate_id, surface, surface_type)[:24]


def production_mention_id(occurrence_id: str) -> str:
    return MENTION_PREFIX + stable_hash(occurrence_id)[:24]


def _protected_hashes(root: Path) -> dict[str, str]:
    paths = (
        RELATIONS_PATH,
        GOLD_PATH,
        PUNCTUATION_PATH,
        Path("data/mentions/jinshu.json"),
        Path("data/shishuo-corpus-index.json"),
        Path("data/jinshu-unit-index.json"),
    )
    return {str(path): sha256_file(root / path) for path in paths}


def _source_id(source: str) -> str:
    if source == "shishuo":
        return "source-001"
    if source == "jinshu":
        return "source-002"
    raise ValueError(f"unsupported P3B.1 evidence source: {source!r}")


def _evidence_type(source: str, section: str) -> str:
    if section == "liu_annotation":
        return "annotation"
    return "primary_text"


def _clean_locator(
    candidate_evidence: Mapping[str, Any],
    *,
    annotation_id: str | None = None,
) -> dict[str, Any]:
    raw = candidate_evidence.get("locator", {})
    if not isinstance(raw, Mapping):
        raise ValueError(f"P3A.1 Evidence has no locator: {candidate_evidence.get('id')}")
    locator: dict[str, Any] = {
        "artifact_type": raw.get("artifact_type"),
        "artifact_path": raw.get("artifact_path"),
        "artifact_sha256": raw.get("artifact_sha256"),
        "source_provenance": {
            "witness_id": raw.get("source_provenance", {}).get("witness_id"),
            "source_path": raw.get("source_provenance", {}).get("source_path"),
            "source_sha256": raw.get("source_provenance", {}).get("source_sha256"),
        },
    }
    for key in (
        "entry_id",
        "unit_id",
        "chapter_id",
        "source_normalized_filename",
        "normalized_line_start",
        "normalized_line_end",
        "page_marker_start",
        "page_marker_end",
    ):
        if key in raw:
            locator[key] = raw[key]
    if annotation_id is not None:
        locator["annotation_id"] = annotation_id
    elif "annotation_id" in raw:
        locator["annotation_id"] = raw["annotation_id"]
    required = (
        locator["artifact_type"],
        locator["artifact_path"],
        locator["artifact_sha256"],
        locator["source_provenance"].get("witness_id"),
        locator["source_provenance"].get("source_path"),
        locator["source_provenance"].get("source_sha256"),
    )
    if not all(isinstance(item, str) and item for item in required):
        raise ValueError(f"P3A.1 Evidence locator is incomplete: {candidate_evidence.get('id')}")
    if locator["artifact_type"] == "shishuo_entry" and "entry_id" not in locator:
        raise ValueError(f"Shishuo Evidence locator has no entry_id: {candidate_evidence.get('id')}")
    if locator["artifact_type"] == "jinshu_unit" and "unit_id" not in locator:
        raise ValueError(f"Jinshu Evidence locator has no unit_id: {candidate_evidence.get('id')}")
    return locator


def _candidate_evidence_record(
    candidate_evidence: Mapping[str, Any],
    *,
    root: Path = ROOT,
    annotation_id: str | None = None,
) -> dict[str, Any]:
    source = str(candidate_evidence.get("source"))
    section = str(candidate_evidence.get("section", ""))
    source_id = _source_id(source)
    source_evidence_id = str(candidate_evidence["id"])
    quote = str(candidate_evidence.get("quote", ""))
    artifact_path = candidate_evidence.get("locator", {}).get("artifact_path")
    if isinstance(artifact_path, str):
        artifact = root / artifact_path
        if artifact.is_file() and quote not in artifact.read_text(encoding="utf-8"):
            surface = str(candidate_evidence.get("surface", ""))
            artifact_text = artifact.read_text(encoding="utf-8")
            surface_offset = artifact_text.find(surface) if surface else -1
            if surface_offset >= 0:
                # P3A.1 identity-seed quotations may be normalized unit text
                # rather than literal Markdown excerpts.  Preserve the
                # identity evidence while making the production quotation an
                # exact excerpt of the registered processed artifact.
                quote = artifact_text[surface_offset : surface_offset + max(len(surface), 160)]
            else:
                raise ValueError(
                    f"P3A.1 Evidence quote and surface are absent from artifact: {source_evidence_id}"
                )
    return {
        "id": production_evidence_id(source_evidence_id),
        "source_id": source_id,
        "evidence_type": _evidence_type(source, section),
        "quote": quote,
        "locator": _clean_locator(candidate_evidence, annotation_id=annotation_id),
        "assertion_status": "attested",
        "review_status": "candidate",
        "notes": (
            "P3B.1 materialization projection from P3A.1 candidate evidence; "
            "identity and surface semantics remain candidate pending editorial review."
        ),
    }


def _candidate_map(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    document = read_json(root / P3A1_PATH)
    candidates = {
        str(item["candidate_id"]): item
        for item in document.get("candidates", [])
        if isinstance(item, Mapping) and isinstance(item.get("candidate_id"), str)
    }
    evidence = {
        str(item["id"]): item
        for item in document.get("evidence", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    return candidates, evidence


def freeze_selection(root: Path = ROOT) -> dict[str, Any]:
    """Validate the pre-mutation ranking bytes and frozen wave guard."""

    wave_path = root / WAVE_PATH
    wave = read_json(wave_path)
    if wave.get("wave_id") != WAVE_ID:
        raise ValueError(f"unexpected wave_id: {wave.get('wave_id')!r}")
    source_path = root / str(wave.get("source_ranking_artifact"))
    if not source_path.is_file():
        raise ValueError(f"missing source ranking artifact: {source_path}")
    expected_hash = wave.get("source_ranking_sha256")
    actual_hash = sha256_file(source_path)
    if expected_hash != actual_hash:
        raise ValueError(
            f"source ranking hash mismatch before materialization: {expected_hash!r} != {actual_hash!r}"
        )

    snapshot_path = root / RANKING_SNAPSHOT_PATH
    if snapshot_path.exists():
        if sha256_file(snapshot_path) != expected_hash:
            raise ValueError("existing Wave 1 ranking snapshot does not match the frozen hash")
    else:
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, snapshot_path)

    if str(wave.get("source_ranking_artifact")) != str(RANKING_SNAPSHOT_PATH):
        wave["source_ranking_artifact"] = str(RANKING_SNAPSHOT_PATH)
        write_json(wave_path, wave)

    ranking = read_json(snapshot_path)
    ranking_by_candidate = {
        str(item.get("candidate_id")): item
        for item in ranking.get("candidates", [])
        if isinstance(item, Mapping) and isinstance(item.get("candidate_id"), str)
    }
    candidates, _evidence = _candidate_map(root)
    members = wave.get("members", [])
    if len(members) != EXPECTED_WAVE_SIZE:
        raise ValueError(f"{WAVE_LABEL} requires exactly {EXPECTED_WAVE_SIZE} frozen members, found {len(members)}")
    ranks = sorted(int(item.get("rank_at_selection", -1)) for item in members)
    if ranks != list(range(1, EXPECTED_WAVE_SIZE + 1)):
        raise ValueError(f"{WAVE_LABEL} member ranks are not exactly 1-{EXPECTED_WAVE_SIZE}: {ranks}")
    people = read_json(root / PEOPLE_PATH).get("people", [])
    current_ids = {str(item.get("person_id")) for item in people}
    for member in sorted(members, key=lambda item: int(item["rank_at_selection"])):
        candidate_id = member.get("candidate_id")
        rank = int(member["rank_at_selection"])
        ranking_row = ranking_by_candidate.get(candidate_id)
        candidate = candidates.get(str(candidate_id))
        if ranking_row is None:
            raise ValueError(f"{WAVE_LABEL} member is absent from frozen ranking: {candidate_id}")
        if int(ranking_row.get("rank", -1)) != rank:
            raise ValueError(f"{WAVE_LABEL} rank changed for {candidate_id}: {ranking_row.get('rank')} != {rank}")
        if candidate is None:
            raise ValueError(f"{WAVE_LABEL} member is absent from P3A.1 candidates: {candidate_id}")
        person_id = member.get("person_id")
        registered_wave_person = next(
            (
                person for person in people
                if isinstance(person, Mapping)
                and isinstance(person.get("materialization"), Mapping)
                and person["materialization"].get("wave_id") == WAVE_ID
                and person["materialization"].get("candidate_id") == candidate_id
            ),
            None,
        )
        if candidate.get("status") != "strong_candidate" and registered_wave_person is None:
            raise ValueError(f"{WAVE_LABEL} member is not strong_candidate: {candidate_id}")
        if candidate.get("materialization_state") != "new_candidate" and registered_wave_person is None:
            raise ValueError(f"{WAVE_LABEL} member is already materialized elsewhere: {candidate_id}")
        if not isinstance(candidate.get("preferred_name"), str) or not candidate["preferred_name"]:
            raise ValueError(f"{WAVE_LABEL} member has no preferred name: {candidate_id}")
        if not candidate.get("identity_evidence_ids"):
            raise ValueError(f"{WAVE_LABEL} member has no identity Evidence: {candidate_id}")
        flags = set(candidate.get("risk_flags", []))
        blocking = sorted(flags & BLOCKING_FLAGS)
        if blocking:
            raise ValueError(f"{WAVE_LABEL} member has blocking identity flags {blocking}: {candidate_id}")
        if not isinstance(person_id, str) or not person_id:
            raise ValueError(f"{WAVE_LABEL} intended Person ID is missing or already used: {person_id!r}")
        if person_id in current_ids and registered_wave_person is None:
            raise ValueError(f"{WAVE_LABEL} intended Person ID is already used: {person_id!r}")
        if member.get("preferred_name") != candidate.get("preferred_name"):
            raise ValueError(f"{WAVE_LABEL} preferred name drift: {candidate_id}")
    return wave


def _entry_sections(root: Path, entry: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = root / str(entry["path"])
    text = path.read_text(encoding="utf-8")
    metadata = parse_frontmatter(text)
    rows: list[dict[str, Any]] = []
    for section, body, section_metadata in parse_shishuo_sections(text):
        rows.append(
            {
                "section": section,
                "text": body,
                "metadata": dict(section_metadata),
            }
        )
    return metadata, rows


def _validate_occurrence(
    root: Path,
    occurrence: Mapping[str, Any],
    entries: Mapping[str, Mapping[str, Any]],
) -> tuple[bool, str, dict[str, Any] | None]:
    story_id = occurrence.get("source_id")
    entry = entries.get(str(story_id))
    if entry is None:
        return False, "unknown_story", None
    section = str(occurrence.get("section"))
    surface = str(occurrence.get("surface"))
    offset = occurrence.get("offset")
    if not isinstance(offset, int) or offset < 0:
        return False, "unsafe_anchor", None
    metadata, rows = _entry_sections(root, entry)
    matches: list[dict[str, Any]] = []
    for row in rows:
        if row["section"] != section:
            continue
        text = str(row["text"])
        if offset + len(surface) <= len(text) and text[offset : offset + len(surface)] == surface:
            matches.append({"metadata": metadata, "section_metadata": row["metadata"], "text": text})
    if len(matches) != 1:
        if not matches:
            return False, "unsafe_anchor", None
        return False, "ambiguous_anchor", None
    return True, "", matches[0]


def _occurrence_key(mention: Mapping[str, Any]) -> tuple[str, str, int, str]:
    evidence = mention.get("evidence", {})
    offset = evidence.get("section_offset") if isinstance(evidence, Mapping) else None
    if not isinstance(offset, int):
        anchor = mention.get("anchor", {})
        offset = anchor.get("offset", -1) if isinstance(anchor, Mapping) else -1
    return (
        str(mention.get("entry_id") or mention.get("source_id")),
        str(mention.get("section")),
        int(offset),
        str(mention.get("surface")),
    )


def _mention_span(mention: Mapping[str, Any]) -> tuple[str, str, int, int] | None:
    evidence = mention.get("evidence", {})
    offset = evidence.get("section_offset") if isinstance(evidence, Mapping) else None
    if not isinstance(offset, int):
        anchor = mention.get("anchor", {})
        offset = anchor.get("offset") if isinstance(anchor, Mapping) else None
    surface = mention.get("surface")
    if not isinstance(offset, int) or not isinstance(surface, str):
        return None
    entry_id = str(mention.get("entry_id") or mention.get("source_id"))
    section = str(mention.get("section"))
    return entry_id, section, offset, offset + len(surface)


def _spans_overlap(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_span = _mention_span(left)
    right_span = _mention_span(right)
    if left_span is None or right_span is None or left_span[:2] != right_span[:2]:
        return False
    return left_span[2] < right_span[3] and right_span[2] < left_span[3]


def _build_mention(
    occurrence: Mapping[str, Any],
    *,
    person_id: str,
    candidate: Mapping[str, Any],
    candidate_evidence: Mapping[str, Mapping[str, Any]],
    production_evidence_ids: list[str],
    location: Mapping[str, Any],
    alias_id: str,
) -> dict[str, Any]:
    metadata = location["metadata"]
    section_metadata = location["section_metadata"]
    first_evidence = candidate_evidence[str(occurrence["evidence_ids"][0])]
    quote = str(first_evidence.get("quote", ""))
    provenance = dict(first_evidence.get("locator", {}).get("source_provenance", {}))
    section = str(occurrence["section"])
    source_id = str(occurrence["source_id"])
    offset = int(occurrence["offset"])
    occurrence_id = str(occurrence["occurrence_id"])
    return {
        "source": "shishuo",
        "source_id": source_id,
        "section": section,
        "surface": str(occurrence["surface"]),
        "alias_id": alias_id,
        "alias_type": str(occurrence.get("surface_type", "")),
        "person_id": person_id,
        "candidate_person_ids": [person_id],
        "confidence": "high",
        "resolution_method": f"exact_{WAVE_ID}_candidate_occurrence",
        "context_identity_hits": [str(candidate.get("preferred_name"))],
        "context": quote,
        "evidence": {
            "snippet": quote,
            "section_offset": offset,
            "evidence_ids": production_evidence_ids,
            "provenance": provenance,
        },
        "mention_id": production_mention_id(occurrence_id),
        "entry_id": source_id,
        "chapter_id": metadata.get("chapter_id"),
        "chapter_heading": metadata.get("chapter_heading"),
        "source_section_metadata": dict(section_metadata),
        "assertion_status": "attested",
        "review_status": "candidate",
        "materialization": {
            "wave_id": WAVE_ID,
            "candidate_id": candidate["candidate_id"],
            "candidate_occurrence_id": occurrence_id,
        },
    }


def _candidate_identity_source_evidence(
    candidate: Mapping[str, Any],
    evidence_map: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    return [
        production_evidence_id(str(evidence_id))
        for evidence_id in candidate.get("identity_evidence_ids", [])
        if str(evidence_id) in evidence_map
    ]


def _build_aliases(
    candidate: Mapping[str, Any],
    *,
    person_id: str,
    evidence_map: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], str]]:
    aliases: list[dict[str, Any]] = []
    alias_ids: dict[tuple[str, str], str] = {}
    surfaces = sorted(
        [item for item in candidate.get("surfaces", []) if isinstance(item, Mapping)],
        key=lambda item: (
            str(item.get("surface_type", "")),
            str(item.get("surface", "")),
            str(item.get("association_mode", "")),
        ),
    )
    for surface in surfaces:
        value = str(surface.get("surface", ""))
        surface_type = str(surface.get("surface_type", ""))
        if not value or not surface_type:
            continue
        key = (value, surface_type)
        alias_id = production_alias_id(str(candidate["candidate_id"]), value, surface_type)
        alias_ids[key] = alias_id
        mode = str(surface.get("association_mode", "ambiguous"))
        if mode not in {"exact", "contextual", "ambiguous"}:
            mode = "ambiguous"
        evidence_ids = [
            production_evidence_id(str(evidence_id))
            for evidence_id in surface.get("evidence_ids", [])
            if str(evidence_id) in evidence_map
        ]
        aliases.append(
            {
                "alias_id": alias_id,
                "surface": value,
                "person_ids": [person_id],
                "alias_type": surface_type,
                "resolution_mode": mode,
                "status": "resolved" if mode == "exact" else "context_dependent" if mode == "contextual" else "ambiguous",
                "observed_count": int(surface.get("occurrence_count", 0)),
                "resolved_person_ids": [person_id] if mode in {"exact", "contextual"} else [],
                "source_evidence": [
                    {
                        "evidence_id": production_evidence_id(str(evidence_id)),
                        "source": evidence_map[str(evidence_id)].get("source"),
                        "source_id": evidence_map[str(evidence_id)].get("source_id"),
                        "surface": value,
                        "evidence_snippet": evidence_map[str(evidence_id)].get("quote", ""),
                    }
                    for evidence_id in surface.get("evidence_ids", [])
                    if str(evidence_id) in evidence_map
                ],
                "review_status": "candidate",
                "materialization": {
                    "wave_id": WAVE_ID,
                    "candidate_id": candidate["candidate_id"],
                    "association_mode": mode,
                },
            }
        )
    return aliases, alias_ids


def _build_person(
    candidate: Mapping[str, Any],
    *,
    person_id: str,
    aliases: list[Mapping[str, Any]],
    evidence_map: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    identity_evidence_ids = _candidate_identity_source_evidence(candidate, evidence_map)
    source_evidence = []
    for source_evidence_id in candidate.get("identity_evidence_ids", []):
        item = evidence_map.get(str(source_evidence_id))
        if item is None:
            continue
        source_evidence.append(
            {
                "evidence_id": production_evidence_id(str(source_evidence_id)),
                "source": item.get("source"),
                "source_id": item.get("source_id"),
                "surface": item.get("surface"),
                "confidence": "strong_candidate",
                "snippet": item.get("quote"),
                "provenance": item.get("locator", {}).get("source_provenance", {}),
            }
        )
    return {
        "person_id": person_id,
        "canonical_name": str(candidate["preferred_name"]),
        "scope_role": "primary",
        "identity_scope": f"{WAVE_LABEL} materialization; identity review remains candidate",
        "alias_ids": [str(alias["alias_id"]) for alias in aliases],
        "source_evidence": source_evidence,
        "materialization": {
            "wave_id": WAVE_ID,
            "candidate_id": candidate["candidate_id"],
            "review_status": "candidate",
            "identity_evidence_ids": identity_evidence_ids,
        },
        "review_status": "candidate",
    }


def _update_sketch_source(
    root: Path,
    *,
    people: list[Mapping[str, Any]],
    candidates: Mapping[str, Mapping[str, Any]],
    wave_by_candidate: Mapping[str, Mapping[str, Any]],
    evidence_map: Mapping[str, Mapping[str, Any]],
) -> None:
    source = read_json(root / SKETCH_PATH)
    records_by_id = {
        str(item["person_id"]): item
        for item in source.get("records", [])
        if isinstance(item, Mapping) and isinstance(item.get("person_id"), str)
    }
    for candidate_id, member in wave_by_candidate.items():
        person_id = str(member["person_id"])
        candidate = candidates[candidate_id]
        courtesy = next(
            (
                str(item.get("surface"))
                for item in candidate.get("surfaces", [])
                if item.get("surface_type") == "courtesy_name"
                and item.get("association_mode") == "exact"
            ),
            None,
        )
        identity_evidence_ids = _candidate_identity_source_evidence(candidate, evidence_map)
        records_by_id[person_id] = {
            "person_id": person_id,
            "review_status": "candidate",
            "identity": {
                "canonical_name": str(candidate["preferred_name"]),
                "courtesy_name": courtesy,
                "clan": None,
                "identity_roles": [],
                "brief_intro": None,
                "evidence_ids": identity_evidence_ids,
            },
            "profile_evidence_ids": identity_evidence_ids,
        }
    ordered_ids = [str(item["person_id"]) for item in people]
    source["person_scope"] = ordered_ids
    source["records"] = [records_by_id[person_id] for person_id in ordered_ids]
    write_json(root / SKETCH_PATH, source)


def _enrich_materialization_member(
    member: dict[str, Any],
    *,
    candidate: Mapping[str, Any],
    ranking_row: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach deterministic audit metrics without changing factual layers."""

    metrics = candidate.get("metrics", {})
    surfaces = [
        item for item in candidate.get("surfaces", [])
        if isinstance(item, Mapping) and isinstance(item.get("surface"), str)
    ]
    member.update(
        {
            SELECTION_SCORE_FIELD: float(
                ranking_row.get("score", ranking_row.get("m2_score", 0.0))
            ),
            SELECTION_TIER_FIELD: str(
                ranking_row.get("tier", "m2-eligible" if ranking_row.get("eligible") else "deferred")
            ),
            "exact_aliases": sorted(
                str(item["surface"])
                for item in surfaces
                if item.get("association_mode") == "exact"
            ),
            "contextual_aliases": sorted(
                str(item["surface"])
                for item in surfaces
                if item.get("association_mode") == "contextual"
            ),
            "shishuo_main_story_count": int(metrics.get("shishuo_main_story_count", 0)),
            "shishuo_annotation_story_count": int(metrics.get("shishuo_annotation_story_count", 0)),
            "jinshu_unit_count": int(metrics.get("jinshu_unit_count", 0)),
            "current_sc1_occurrence_count": int(candidate.get("current_sc1_occurrence_count", 0)),
            "direct_relation_count": 0,
        }
    )
    return member


def _render_report(
    wave: Mapping[str, Any],
    materialization: Mapping[str, Any],
    people_before: int,
    people_after: int,
) -> str:
    lines = [
        f"# {WAVE_LABEL} Person Expansion",
        "",
        f"> This report records the frozen {WAVE_LABEL} materialization. New identity, alias, Mention, and Person Sketch records remain candidate data; no Relation or Story publication fact is created here.",
        "",
        "## Selection freeze",
        "",
        f"- Wave: `{wave['wave_id']}`",
        f"- Ranking artifact: `{wave['source_ranking_artifact']}`",
        f"- Ranking SHA-256: `{wave['source_ranking_sha256']}`",
        f"- Person registry: {people_before} → {people_after}",
        f"- Selection authority: pre-mutation ranking ranks 1–{EXPECTED_WAVE_SIZE}; no rank substitution.",
        "",
        "## Materialized Persons",
        "",
        "| Rank | Person | Candidate ID | Score | Exact aliases | Contextual aliases | Shishuo main/Liu Stories | Jinshu units | Promoted | Withheld | SC1 stories | Relations |",
        "|---:|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for member in materialization["members"]:
        lines.append(
            f"| {member['rank_at_selection']} | {member['preferred_name']} (`{member['person_id']}`) | `{member['candidate_id']}` | "
            f"{member.get('p3a_score', 0.0):.6f} | {', '.join(member.get('exact_aliases', [])) or '—'} | "
            f"{', '.join(member.get('contextual_aliases', [])) or '—'} | "
            f"{member.get('shishuo_main_story_count', 0)}/{member.get('shishuo_annotation_story_count', 0)} | "
            f"{member.get('jinshu_unit_count', 0)} | {member['promoted_occurrence_count']} | "
            f"{member['withheld_occurrence_count']} | {len(member['current_sc1_story_ids'])} | "
            f"{member.get('direct_relation_count', 0)} |"
        )
    lines.extend(
        [
            "",
            "## Occurrence policy",
            "",
            "Only strong-candidate exact associations with a validated section-local anchor were promoted to production Mention records. Contextual, ambiguous, generic-title, and unsafe-anchor occurrences remain in the machine-readable withheld report. Promotion preserves main-text versus Liu-annotation sections and does not infer participant status.",
            "",
            "## Relations and publication",
            "",
            "No Relation records were created. PersonStory links may cover the full Shishuo corpus, but the SC0/SC1 Story publication set is unchanged.",
            "",
        ]
    )
    for member in materialization["members"]:
        withheld = member.get("withheld_occurrences", [])
        if not withheld:
            continue
        lines.extend([f"### Withheld surfaces — {member['preferred_name']}", ""])
        for item in withheld:
            lines.append(
                f"- `{item.get('source_id')}` · {item.get('section')} · `{item.get('surface')}` · `{item.get('reason')}`"
            )
        lines.append("")
    return "\n".join(lines)


def build(root: Path = ROOT) -> dict[str, Any]:
    wave = freeze_selection(root)
    candidates, candidate_evidence = _candidate_map(root)
    occurrences_document = read_json(root / OCCURRENCES_PATH)
    occurrences = occurrences_document.get("occurrences", [])
    entries = {
        str(item["id"]): item
        for item in read_json(root / CORPUS_INDEX_PATH).get("entries", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    people_document = read_json(root / PEOPLE_PATH)
    aliases_document = read_json(root / ALIASES_PATH)
    mentions_document = read_json(root / MENTIONS_PATH)
    evidence_document = read_json(root / EVIDENCE_PATH)
    existing_people = list(people_document.get("people", []))
    existing_aliases = list(aliases_document.get("aliases", []))
    existing_mentions = list(mentions_document.get("mentions", []))
    existing_evidence = list(evidence_document.get("records", []))
    existing_person_ids = {str(item.get("person_id")) for item in existing_people}
    wave_members = sorted(wave["members"], key=lambda item: int(item["rank_at_selection"]))
    wave_by_candidate = {str(item["candidate_id"]): item for item in wave_members}
    people_before = len(existing_people)
    ranking_snapshot = read_json(root / RANKING_SNAPSHOT_PATH)
    ranking_by_candidate = {
        str(item["candidate_id"]): item
        for item in ranking_snapshot.get("candidates", [])
        if isinstance(item, Mapping) and isinstance(item.get("candidate_id"), str)
    }

    # If the wave has already been materialized, the P3A.1 occurrence builder
    # may have correctly filtered these candidates as already_materialized.
    # Reuse the committed materialization output and verify the production
    # registry instead of silently rebuilding from an empty proposal set.
    already_materialized = all(
        any(
            isinstance(person.get("materialization"), Mapping)
            and person["materialization"].get("wave_id") == WAVE_ID
            and person["materialization"].get("candidate_id") == candidate_id
            for person in existing_people
        )
        for candidate_id in wave_by_candidate
    )
    if already_materialized and (root / MATERIALIZATION_PATH).is_file():
        # Keep the idempotent path capable of repairing a deterministic
        # projection change (for example, a quotation normalization fix)
        # without re-running candidate occurrence discovery after P3A.1 has
        # classified the wave as already materialized.
        evidence_by_id = {str(item.get("id")): item for item in existing_evidence}
        for source_evidence_id in sorted(candidate_evidence):
            production_id = production_evidence_id(source_evidence_id)
            # Recreate a missing derived production record deterministically.
            # A later wave-specific provenance gate may withhold it, but an
            # idempotent rebuild must not leave stale foreign-key references
            # merely because an earlier projection was sanitized.
            record = _candidate_evidence_record(
                candidate_evidence[source_evidence_id], root=root
            )
            existing_record = evidence_by_id.get(production_id)
            if existing_record is not None and existing_record != record:
                raise ValueError(f"production Evidence ID collision: {production_id}")
            evidence_by_id[production_id] = record
        evidence_document["records"] = sorted(
            evidence_by_id.values(), key=lambda item: str(item.get("id"))
        )
        write_json(root / EVIDENCE_PATH, evidence_document)
        materialization = read_json(root / MATERIALIZATION_PATH)
        enriched_members = [
            _enrich_materialization_member(
                dict(member),
                candidate=candidates[str(member["candidate_id"])],
                ranking_row=ranking_by_candidate[str(member["candidate_id"])],
            )
            for member in materialization.get("members", [])
        ]
        materialization["members"] = enriched_members
        wave["members"] = enriched_members
        write_json(root / WAVE_PATH, wave)
        materialization["source_ranking_artifact"] = wave["source_ranking_artifact"]
        materialization["source_ranking_sha256"] = wave["source_ranking_sha256"]
        materialization["protected_hashes"] = _protected_hashes(root)
        write_json(root / MATERIALIZATION_PATH, materialization)
        _update_sketch_source(
            root,
            people=existing_people,
            candidates=candidates,
            wave_by_candidate=wave_by_candidate,
            evidence_map=candidate_evidence,
        )
        (root / REPORT_PATH).parent.mkdir(parents=True, exist_ok=True)
        (root / REPORT_PATH).write_text(
            _render_report(
                wave,
                materialization,
                materialization["people_before"],
                materialization["people_after"],
            ),
            encoding="utf-8",
        )
        return materialization

    new_people: list[dict[str, Any]] = []
    new_aliases: list[dict[str, Any]] = []
    alias_lookup: dict[tuple[str, str, str], str] = {}
    for member in wave_members:
        candidate_id = str(member["candidate_id"])
        candidate = candidates[candidate_id]
        person_id = str(member["person_id"])
        aliases, alias_ids = _build_aliases(
            candidate,
            person_id=person_id,
            evidence_map=candidate_evidence,
        )
        new_aliases.extend(aliases)
        for key, alias_id in alias_ids.items():
            alias_lookup[(person_id, key[0], key[1])] = alias_id
        new_people.append(
            _build_person(
                candidate,
                person_id=person_id,
                aliases=aliases,
                evidence_map=candidate_evidence,
            )
        )

    used_source_evidence_ids: set[str] = set()
    for candidate_id in wave_by_candidate:
        candidate = candidates[candidate_id]
        used_source_evidence_ids.update(str(item) for item in candidate.get("identity_evidence_ids", []))
        for surface in candidate.get("surfaces", []):
            used_source_evidence_ids.update(str(item) for item in surface.get("evidence_ids", []))
    production_evidence_records = {
        production_evidence_id(source_id): _candidate_evidence_record(
            candidate_evidence[source_id], root=root
        )
        for source_id in sorted(used_source_evidence_ids)
        if source_id in candidate_evidence
    }
    evidence_by_id = {str(item.get("id")): item for item in existing_evidence}
    for evidence_id, record in production_evidence_records.items():
        existing = evidence_by_id.get(evidence_id)
        if existing is not None and existing != record:
            raise ValueError(f"production Evidence ID collision: {evidence_id}")
        evidence_by_id[evidence_id] = record

    occurrence_by_candidate: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for occurrence in occurrences:
        candidate_id = str(occurrence.get("candidate_id"))
        if candidate_id in wave_by_candidate:
            occurrence_by_candidate[candidate_id].append(occurrence)
    existing_occurrence_keys = {_occurrence_key(item): item for item in existing_mentions}
    wave_occurrences = [
        occurrence
        for occurrence in occurrences
        if str(occurrence.get("candidate_id")) in wave_by_candidate
    ]
    cross_candidate_suppressed: dict[str, str] = {}
    for index, left in enumerate(wave_occurrences):
        left_probe = {
            "entry_id": left.get("source_id"),
            "section": left.get("section"),
            "surface": left.get("surface"),
            "evidence": {"section_offset": left.get("offset")},
        }
        for right in wave_occurrences[index + 1 :]:
            if str(left.get("candidate_id")) == str(right.get("candidate_id")):
                continue
            right_probe = {
                "entry_id": right.get("source_id"),
                "section": right.get("section"),
                "surface": right.get("surface"),
                "evidence": {"section_offset": right.get("offset")},
            }
            if _spans_overlap(left_probe, right_probe):
                cross_candidate_suppressed[str(left.get("occurrence_id"))] = "incompatible_overlapping_candidate_ranges"
                cross_candidate_suppressed[str(right.get("occurrence_id"))] = "incompatible_overlapping_candidate_ranges"
    promoted_mentions: list[dict[str, Any]] = []
    materialized_members: list[dict[str, Any]] = []
    for member in wave_members:
        candidate_id = str(member["candidate_id"])
        candidate = candidates[candidate_id]
        person_id = str(member["person_id"])
        candidate_rows = sorted(
            occurrence_by_candidate.get(candidate_id, []),
            key=lambda item: (
                str(item.get("source_id")),
                0 if item.get("section") == "main_text" else 1,
                int(item.get("offset", 10**9)) if isinstance(item.get("offset"), int) else 10**9,
                -len(str(item.get("surface", ""))),
                str(item.get("occurrence_id")),
            ),
        )
        suppressed_overlaps: dict[str, str] = {
            occurrence_id: reason
            for occurrence_id, reason in cross_candidate_suppressed.items()
            if any(str(row.get("occurrence_id")) == occurrence_id for row in candidate_rows)
        }
        for index, left in enumerate(candidate_rows):
            for right in candidate_rows[index + 1 :]:
                left_span = (
                    str(left.get("source_id")),
                    str(left.get("section")),
                    int(left.get("offset", -1)) if isinstance(left.get("offset"), int) else -1,
                    int(left.get("offset", -1)) + len(str(left.get("surface", "")))
                    if isinstance(left.get("offset"), int)
                    else -1,
                )
                right_span = (
                    str(right.get("source_id")),
                    str(right.get("section")),
                    int(right.get("offset", -1)) if isinstance(right.get("offset"), int) else -1,
                    int(right.get("offset", -1)) + len(str(right.get("surface", "")))
                    if isinstance(right.get("offset"), int)
                    else -1,
                )
                if left_span[:2] != right_span[:2] or left_span[2] < 0 or right_span[2] < 0:
                    continue
                if not (left_span[2] < right_span[3] and right_span[2] < left_span[3]):
                    continue
                if str(left.get("candidate_id")) != str(right.get("candidate_id")):
                    # Different candidate identities at an incompatible range
                    # are all withheld.  The materializer must not choose a
                    # Person merely because a wave rank happened to be first.
                    suppressed_overlaps[str(left.get("occurrence_id"))] = "incompatible_overlapping_candidate_ranges"
                    suppressed_overlaps[str(right.get("occurrence_id"))] = "incompatible_overlapping_candidate_ranges"
                elif len(str(left.get("surface", ""))) >= len(str(right.get("surface", ""))):
                    suppressed_overlaps[str(right.get("occurrence_id"))] = "nested_same_person_alias_range"
                else:
                    suppressed_overlaps[str(left.get("occurrence_id"))] = "nested_same_person_alias_range"
        promoted_occurrence_ids: list[str] = []
        promoted_mention_ids: list[str] = []
        withheld: list[dict[str, Any]] = []
        for occurrence in candidate_rows:
            exact = occurrence.get("association_mode") == "exact"
            strong = occurrence.get("confidence") == "strong_candidate"
            surface_type = str(occurrence.get("surface_type", ""))
            reason: str | None = None
            reused_existing = False
            if str(occurrence.get("occurrence_id")) in suppressed_overlaps:
                reason = suppressed_overlaps[str(occurrence.get("occurrence_id"))]
            if not exact:
                reason = reason or "contextual_association"
            elif not strong:
                reason = reason or "non_strong_candidate_confidence"
            elif surface_type not in EXACT_SURFACE_TYPES:
                reason = reason or "title_or_non_exact_surface_type"
            valid, validation_reason, location = _validate_occurrence(root, occurrence, entries)
            if reason is None and not valid:
                reason = validation_reason
            key = (
                str(occurrence.get("source_id")),
                str(occurrence.get("section")),
                int(occurrence.get("offset", -1)),
                str(occurrence.get("surface")),
            )
            if reason is None and key in existing_occurrence_keys:
                existing = existing_occurrence_keys[key]
                if existing.get("person_id") == person_id:
                    promoted_occurrence_ids.append(str(occurrence["occurrence_id"]))
                    promoted_mention_ids.append(str(existing["mention_id"]))
                    reused_existing = True
                else:
                    reason = "existing_mention_collision"
            if reused_existing:
                continue
            if reason is None:
                probe = {
                    "entry_id": occurrence.get("source_id"),
                    "section": occurrence.get("section"),
                    "surface": occurrence.get("surface"),
                    "evidence": {"section_offset": occurrence.get("offset")},
                }
                if any(_spans_overlap(probe, existing) for existing in existing_mentions):
                    reason = "overlapping_existing_mention_range"
            if reason is not None:
                withheld.append(
                    {
                        "occurrence_id": occurrence.get("occurrence_id"),
                        "source_id": occurrence.get("source_id"),
                        "section": occurrence.get("section"),
                        "surface": occurrence.get("surface"),
                        "association_mode": occurrence.get("association_mode"),
                        "confidence": occurrence.get("confidence"),
                        "reason": reason,
                        "evidence_ids": [
                            production_evidence_id(str(item))
                            for item in occurrence.get("evidence_ids", [])
                            if str(item) in candidate_evidence
                        ],
                    }
                )
                continue
            if not valid or location is None:
                raise AssertionError("validated occurrence has no location")
            production_ids = [
                production_evidence_id(str(item))
                for item in occurrence.get("evidence_ids", [])
                if str(item) in candidate_evidence
            ]
            alias_id = alias_lookup.get((person_id, str(occurrence["surface"]), surface_type))
            if alias_id is None:
                raise ValueError(f"promoted occurrence has no production Alias: {occurrence}")
            mention = _build_mention(
                occurrence,
                person_id=person_id,
                candidate=candidate,
                candidate_evidence=candidate_evidence,
                production_evidence_ids=production_ids,
                location=location,
                alias_id=alias_id,
            )
            if mention["mention_id"] in {str(item.get("mention_id")) for item in existing_mentions}:
                existing_mention = next(item for item in existing_mentions if item.get("mention_id") == mention["mention_id"])
                if existing_mention != mention:
                    raise ValueError(f"production Mention ID collision: {mention['mention_id']}")
            else:
                existing_mentions.append(mention)
                existing_occurrence_keys[key] = mention
                promoted_mentions.append(mention)
            promoted_occurrence_ids.append(str(occurrence["occurrence_id"]))
            promoted_mention_ids.append(str(mention["mention_id"]))
        exact_alias_count = sum(item.get("association_mode") == "exact" for item in candidate.get("surfaces", []))
        contextual_alias_count = sum(item.get("association_mode") == "contextual" for item in candidate.get("surfaces", []))
        materialized_members.append(
            _enrich_materialization_member(
                {
                    "candidate_id": candidate_id,
                    "rank_at_selection": int(member["rank_at_selection"]),
                    "preferred_name": candidate["preferred_name"],
                    "person_id": person_id,
                    "candidate_status": candidate["status"],
                    "materialization_status": "materialized",
                    "review_status": "candidate",
                    "exact_alias_count": exact_alias_count,
                    "contextual_alias_count": contextual_alias_count,
                    "promoted_occurrence_ids": sorted(promoted_occurrence_ids),
                    "promoted_mention_ids": sorted(set(promoted_mention_ids)),
                    "promoted_occurrence_count": len(promoted_occurrence_ids),
                    "withheld_occurrence_count": len(withheld),
                    "withheld_occurrences": withheld,
                    "current_sc1_story_ids": sorted(candidate.get("current_sc1_story_ids", [])),
                    "production_alias_ids": [
                        str(item["alias_id"])
                        for item in new_aliases
                        if person_id in item.get("person_ids", [])
                    ],
                    "production_identity_evidence_ids": _candidate_identity_source_evidence(
                        candidate, candidate_evidence
                    ),
                },
                candidate=candidate,
                ranking_row=ranking_by_candidate[candidate_id],
            )
        )

    # Append in stable Wave rank order.  Existing legacy records are copied
    # byte/semantically unchanged.
    people_document["stage"] = "materialized-person-registry"
    people_document["people"] = [*existing_people, *new_people]
    aliases_document["stage"] = "materialized-person-registry"
    aliases_document["aliases"] = [*existing_aliases, *new_aliases]
    mentions_document["stage"] = "materialized-mention-detection"
    mentions_document["person_scope"] = sorted(
        {str(item["person_id"]) for item in people_document["people"]}
    )
    mentions_document["mention_count"] = len(existing_mentions)
    mentions_document["mentions"] = sorted(
        existing_mentions,
        key=lambda item: (
            str(item.get("entry_id") or item.get("source_id")),
            0 if item.get("section") == "main_text" else 1,
            int(item.get("evidence", {}).get("section_offset", 10**9))
            if isinstance(item.get("evidence"), Mapping) and isinstance(item.get("evidence", {}).get("section_offset"), int)
            else 10**9,
            str(item.get("mention_id")),
        ),
    )
    evidence_document["records"] = sorted(evidence_by_id.values(), key=lambda item: str(item.get("id")))
    write_json(root / PEOPLE_PATH, people_document)
    write_json(root / ALIASES_PATH, aliases_document)
    write_json(root / MENTIONS_PATH, mentions_document)
    write_json(root / EVIDENCE_PATH, evidence_document)

    wave["members"] = materialized_members
    write_json(root / WAVE_PATH, wave)
    materialization = {
        "schema": 1,
        "stage": MATERIALIZATION_STAGE,
        "wave_id": WAVE_ID,
        "source_ranking_artifact": wave["source_ranking_artifact"],
        "source_ranking_sha256": wave["source_ranking_sha256"],
        "people_before": people_before,
        "people_after": len(people_document["people"]),
        "promoted_mention_count": len(promoted_mentions),
        "withheld_occurrence_count": sum(item["withheld_occurrence_count"] for item in materialized_members),
        "production_evidence_ids": sorted(production_evidence_records),
        "protected_hashes": _protected_hashes(root),
        "members": materialized_members,
        "notes": [
            "Wave membership is frozen by the pre-mutation ranking hash.",
            "Candidate review status is preserved; no new Relation or Story publication record is created.",
            "Contextual and unsafe occurrences remain withheld with reasons.",
        ],
    }
    write_json(root / MATERIALIZATION_PATH, materialization)
    _update_sketch_source(
        root,
        people=people_document["people"],
        candidates=candidates,
        wave_by_candidate=wave_by_candidate,
        evidence_map=candidate_evidence,
    )
    (root / REPORT_PATH).parent.mkdir(parents=True, exist_ok=True)
    (root / REPORT_PATH).write_text(
        _render_report(wave, materialization, people_before, len(people_document["people"])),
        encoding="utf-8",
    )
    return materialization


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--freeze-only", action="store_true")
    args = parser.parse_args()
    if args.freeze_only:
        wave = freeze_selection(args.root)
        print(f"frozen {wave['wave_id']} from {wave['source_ranking_artifact']}")
        return 0
    materialization = build(args.root)
    print(
        f"materialized {materialization['wave_id']}: "
        f"{len(materialization['members'])} Persons, "
        f"{materialization['promoted_mention_count']} promoted Mentions, "
        f"{materialization['withheld_occurrence_count']} withheld occurrences"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
