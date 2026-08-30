#!/usr/bin/env python3
"""Build the deterministic, local-only DS2.1A Person research surfaces.

The Person projection reuses the canonical Person registry and existing
PersonStory links, while the companion search projection covers every
canonical Shishuo corpus entry.  Neither creates a new identity or historical
fact layer.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import unicodedata
from typing import Any, Iterable, Mapping

try:
    from .build_six_person_pilot import parse_frontmatter, parse_shishuo_sections
except ImportError:  # direct execution: python scripts/build_ds2_1a_person_research.py
    from build_six_person_pilot import parse_frontmatter, parse_shishuo_sections


ROOT = Path(__file__).resolve().parents[1]

SC1_PATH = Path("data/derived/sc1-site.json")
PEOPLE_PATH = Path("data/people.json")
PERSON_STORY_LINKS_PATH = Path("data/derived/person-story-links.json")
SHISHUO_CORPUS_INDEX_PATH = Path("data/shishuo-corpus-index.json")
SHISHUO_SEARCH_OUTPUT_PATH = Path("data/derived/ds2-1a-shishuo-search-corpus.json")
ALIASES_PATH = Path("data/aliases.json")
JINSHU_INDEX_PATH = Path("data/jinshu-unit-index.json")
JINSHU_MENTIONS_PATH = Path("data/mentions/jinshu.json")
H0C_FACTS_PATH = Path("data/derived/h0c-historical-facts.json")
H0C_PARTICIPANT_FREEZE_PATH = Path("data/derived/h0c-participant-freeze.json")
H0C_EVENT_PARTICIPATIONS_PATH = Path("data/derived/h0c-event-participations.json")
H0C_PERSON_ACTIVITIES_PATH = Path("data/derived/h0c-person-activities.json")
HG1_FACT_EXTENSION_PATH = Path("data/derived/hg1-1-fact-extension.json")
OUTPUT_PATH = Path("data/derived/ds2-1a-person-research-surface.json")
ASSOCIATION_AUDIT_PATH = Path("data/derived/ds2-1a-research-association-audit.json")

PUBLISHED_STATES = {"production_ready", "preview_ready"}
SOURCE_MARKER = "## Original source (exact)\n\n"

# This is deliberately a small matching fold, not a new text-normalization
# pipeline.  It covers the character-form differences present in the local
# Person registry and Jinshu witness (notably 温/溫 and 嶠/峤).
MATCH_FOLD = str.maketrans(
    {
        "溫": "温",
        "嶠": "峤",
        "謝": "谢",
        "導": "导",
        "凝": "凝",
        "侃": "侃",
        "敦": "敦",
        "鯤": "鲲",
        "安": "安",
        "亮": "亮",
        "王": "王",
        "陶": "陶",
        "峤": "峤",
        "韞": "韫",
    }
)


def read_json(root: Path, relative: Path) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_json(root: Path, relative: Path, value: Any) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(value), encoding="utf-8", newline="\n")


def sha256_file(root: Path, relative: Path) -> str:
    digest = hashlib.sha256()
    with (root / relative).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fold(value: str) -> str:
    return unicodedata.normalize("NFKC", value).translate(MATCH_FOLD).lower()


def compact_text(value: str) -> str:
    return "".join(character for character in value if not character.isspace())


def source_excerpt(value: str, terms: Iterable[str] = (), limit: int = 110) -> str:
    """Return a deterministic source-derived preview without adding prose."""

    compact = compact_text(value)
    if len(compact) <= limit:
        return compact
    folded = fold(compact)
    positions = [folded.find(fold(term)) for term in terms if term]
    positions = [position for position in positions if position >= 0]
    start = max(0, min(positions) - 24) if positions else 0
    if start + limit > len(compact):
        start = max(0, len(compact) - limit)
    return compact[start : start + limit]


def exposed_persons(sc1: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Use the same Person exposure boundary as the existing UX2 index."""

    rows = [
        row
        for row in sc1.get("people", [])
        if isinstance(row, Mapping)
        and isinstance(row.get("id"), str)
        and row.get("scope_role") in {"primary", "supporting"}
        and row.get("scope") in {"primary", "supporting"}
    ]
    return sorted(rows, key=lambda row: (str(row["id"]), str(row.get("canonical_name", ""))))


def registered_persons(root: Path = ROOT) -> list[dict[str, Any]]:
    """Return the current canonical Person registry, independent of frontend scope."""

    document = read_json(root, PEOPLE_PATH)
    rows: list[dict[str, Any]] = []
    for row in document.get("people", []) if isinstance(document, Mapping) else []:
        if not isinstance(row, Mapping) or not row.get("person_id"):
            continue
        normalized = dict(row)
        normalized["id"] = str(row["person_id"])
        rows.append(normalized)
    return sorted(rows, key=lambda row: (str(row["id"]), str(row.get("canonical_name", ""))))


def exposed_stories(sc1: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = [
        row
        for row in sc1.get("stories", [])
        if isinstance(row, Mapping)
        and isinstance(row.get("id"), str)
        and row.get("publication_state") in PUBLISHED_STATES
        and row.get("title_source") != "candidate"
    ]
    return sorted(
        rows,
        key=lambda row: (
            int(row.get("global_ordinal")) if isinstance(row.get("global_ordinal"), int) else 10**9,
            str(row["id"]),
        ),
    )


def chapter_label(story: Mapping[str, Any]) -> str:
    display = story.get("chapter_display")
    if isinstance(display, Mapping):
        value = display.get("original") or display.get("simplified")
        if isinstance(value, str) and value:
            return value
    for key in ("chapter_heading", "title"):
        value = story.get(key)
        if isinstance(value, str) and value:
            return value
    return str(story["id"])


def story_main_text(story: Mapping[str, Any]) -> str:
    reading = story.get("reading")
    if isinstance(reading, Mapping):
        main_text = reading.get("main_text")
        if isinstance(main_text, Mapping):
            value = main_text.get("original")
            if isinstance(value, str) and value:
                return value
    value = story.get("text")
    return value if isinstance(value, str) else ""


def parse_canonical_entry(
    root: Path, entry: Mapping[str, Any]
) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    """Read one indexed canonical entry without rewriting source characters."""

    relative = Path(str(entry.get("path", "")))
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError(f"Shishuo entry has unsafe path: {relative}")
    path = root / relative
    if not path.is_file():
        raise FileNotFoundError(f"Shishuo entry is missing: {relative}")
    raw = path.read_text(encoding="utf-8")
    expected_sha256 = entry.get("entry_sha256")
    if not isinstance(expected_sha256, str) or sha256_file(root, relative) != expected_sha256:
        raise ValueError(f"Shishuo entry hash differs from corpus index: {relative}")
    metadata = parse_frontmatter(raw)
    if metadata.get("entry_id") != entry.get("id"):
        raise ValueError(f"Shishuo entry id mismatch: {relative}")
    main_text = ""
    annotations: list[dict[str, Any]] = []
    for section, body, section_metadata in parse_shishuo_sections(raw):
        if section == "main_text":
            main_text = body.rstrip("\n")
        elif section == "liu_annotation":
            annotation_id = str(
                section_metadata.get("annotation_id", f"annotation-{len(annotations) + 1:03d}")
            )
            annotations.append(
                {
                    "annotation_id": annotation_id,
                    "text": body.rstrip("\n"),
                    "metadata": dict(section_metadata),
                }
            )
    if not main_text:
        raise ValueError(f"Shishuo entry has no canonical main text: {relative}")
    return metadata, main_text, annotations


def shishuo_evidence_id(story_id: str, annotation_id: str) -> str:
    """Stable local evidence address for a canonical Liu annotation block."""

    return f"shishuo-evidence-{story_id}-{annotation_id}"


def build_shishuo_search_corpus(
    root: Path = ROOT,
    sc1: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build the complete, source-layered 1,130-entry research corpus."""

    corpus = read_json(root, SHISHUO_CORPUS_INDEX_PATH)
    if not isinstance(corpus, Mapping) or not isinstance(corpus.get("entries"), list):
        raise ValueError("Shishuo corpus index has no entries list")
    entries = [row for row in corpus["entries"] if isinstance(row, Mapping)]
    entries.sort(
        key=lambda row: (
            int(row.get("global_ordinal")) if isinstance(row.get("global_ordinal"), int) else 10**9,
            str(row.get("id", "")),
        )
    )
    if len(entries) != int(corpus.get("entry_count", len(entries))):
        raise ValueError("Shishuo corpus index entry count is inconsistent")
    chapter_rows = {
        str(row.get("id")): row
        for row in corpus.get("chapters", [])
        if isinstance(row, Mapping) and row.get("id")
    }
    if sc1 is None:
        sc1 = read_json(root, SC1_PATH)
    published_ids = {str(row["id"]) for row in exposed_stories(sc1)}

    output: list[dict[str, Any]] = []
    for entry in entries:
        story_id = str(entry.get("id", ""))
        chapter_id = story_id.rsplit("-", 1)[0]
        chapter = chapter_rows.get(chapter_id, {})
        metadata, main_text, annotations = parse_canonical_entry(root, entry)
        annotation_rows = [
            {
                "annotation_id": str(annotation["annotation_id"]),
                "text": str(annotation["text"]),
                "evidence_ids": [
                    shishuo_evidence_id(story_id, str(annotation["annotation_id"]))
                ],
                "source_locator": {
                    "source_path": str(entry["path"]),
                    "entry_id": story_id,
                    "annotation_id": str(annotation["annotation_id"]),
                },
            }
            for annotation in annotations
        ]
        annotation_text = "\n".join(row["text"] for row in annotation_rows)
        search_text = main_text if not annotation_text else f"{main_text}\n{annotation_text}"
        output.append(
            {
                "story_id": story_id,
                "chapter_id": chapter_id,
                "chapter_heading": str(
                    chapter.get("heading") or metadata.get("chapter_heading") or chapter_id
                ),
                "entry_number": entry.get("ordinal", metadata.get("ordinal")),
                "main_text": main_text,
                "liu_annotations": annotation_rows,
                "search_text": search_text,
                "search_text_normalized": fold(compact_text(search_text)),
                "source_path": str(entry["path"]),
                "source_sha256": str(entry["entry_sha256"]),
                "source_provenance": {
                    "witness_id": "shishuo-kanripo-wyg",
                    "source_path": metadata.get("source_path"),
                    "source_sha256": metadata.get("source_sha256"),
                },
                "publication_scope": "published" if story_id in published_ids else "research_only",
            }
        )
    return output


PARTICIPANT_ROLES = {
    "present",
    "speaker",
    "actor",
    "referenced",
    "off_frame",
    "annotation_only",
    "uncertain",
}
HARD_SCENE_ROLES = {"present", "speaker", "actor"}
CONTEXTUAL_SCENE_ROLES = {"referenced", "off_frame"}
ROLE_ORDER = {
    "present": 0,
    "speaker": 1,
    "actor": 2,
    "referenced": 3,
    "off_frame": 4,
    "annotation_only": 5,
    "uncertain": 6,
}
PRIORITY_ORDER = {
    "reviewed_hard_scene": 0,
    "reviewed_main_text": 1,
    "reviewed_contextual": 2,
    "reviewed_liu_only": 3,
    "candidate_textual": 4,
}


def layer_presence(layers: set[str]) -> str:
    if layers == {"main_text"}:
        return "main_text"
    if layers == {"liu_annotation"}:
        return "liu_annotation_only"
    if layers == {"main_text", "liu_annotation"}:
        return "both"
    raise ValueError(f"unsupported Shishuo source-layer set: {sorted(layers)}")


def load_reviewed_participants(
    root: Path,
    person_ids: set[str],
    story_ids: set[str],
) -> tuple[dict[tuple[str, str], list[Mapping[str, Any]]], list[dict[str, Any]]]:
    """Load only reviewed H0C participant records; do not infer overlays."""

    document = read_json(root, H0C_PARTICIPANT_FREEZE_PATH)
    by_pair: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    anomalies: list[dict[str, Any]] = []
    for row in document.get("records", []) if isinstance(document, Mapping) else []:
        if not isinstance(row, Mapping):
            anomalies.append({"reason": "non_object_participant_record"})
            continue
        person_id = str(row.get("person_id", ""))
        story_id = str(row.get("story_id", ""))
        participant_id = str(row.get("participant_id", ""))
        if not participant_id or person_id not in person_ids or story_id not in story_ids:
            anomalies.append(
                {
                    "participant_id": participant_id or None,
                    "person_id": person_id or None,
                    "story_id": story_id or None,
                    "reason": "participant_endpoint_unresolved",
                }
            )
            continue
        if row.get("review_status") != "reviewed":
            anomalies.append(
                {
                    "participant_id": participant_id,
                    "person_id": person_id,
                    "story_id": story_id,
                    "reason": "participant_not_reviewed",
                    "review_status": row.get("review_status"),
                }
            )
            continue
        if row.get("role") not in PARTICIPANT_ROLES:
            anomalies.append(
                {
                    "participant_id": participant_id,
                    "person_id": person_id,
                    "story_id": story_id,
                    "reason": "participant_role_invalid",
                    "role": row.get("role"),
                }
            )
            continue
        by_pair[(person_id, story_id)].append(row)
    for rows in by_pair.values():
        rows.sort(key=lambda row: str(row.get("participant_id", "")))
    anomalies.sort(
        key=lambda row: (
            str(row.get("person_id", "")),
            str(row.get("story_id", "")),
            str(row.get("participant_id", "")),
            str(row.get("reason", "")),
        )
    )
    return by_pair, anomalies


def build_association_union(
    root: Path,
    sc1: Mapping[str, Any],
    links_document: Mapping[str, Any],
    search_corpus: list[Mapping[str, Any]],
    people: list[Mapping[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Merge existing PersonStory and reviewed H0C participant channels."""

    person_ids = {str(row["id"]) for row in people}
    search_by_id = {str(row["story_id"]): row for row in search_corpus}
    story_order = {str(row["story_id"]): index for index, row in enumerate(search_corpus)}
    published_ids = {str(row["id"]) for row in exposed_stories(sc1)}
    participant_by_pair, participant_anomalies = load_reviewed_participants(
        root, person_ids, set(search_by_id)
    )
    pair_states: dict[tuple[str, str], dict[str, list[Mapping[str, Any]]]] = {}
    person_story_pairs: set[tuple[str, str]] = set()
    for link in links_document.get("links", []):
        if not isinstance(link, Mapping):
            continue
        person_id = str(link.get("person_id", ""))
        story_id = str(link.get("entry_id", ""))
        if person_id not in person_ids or story_id not in search_by_id:
            continue
        key = (person_id, story_id)
        pair_states.setdefault(key, {"person_story": [], "participant": []})["person_story"].append(link)
        person_story_pairs.add(key)
    for key, rows in participant_by_pair.items():
        pair_states.setdefault(key, {"person_story": [], "participant": []})["participant"].extend(rows)

    output_by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    both_pairs: list[dict[str, Any]] = []
    person_story_only: list[dict[str, Any]] = []
    participant_only: list[dict[str, Any]] = []
    source_layer_disagreements: list[dict[str, Any]] = []
    role_disagreements: list[dict[str, Any]] = []

    for person_id, story_id in sorted(
        pair_states,
        key=lambda key: (story_order.get(key[1], 10**9), key[0], key[1]),
    ):
        state = pair_states[(person_id, story_id)]
        ps_rows = state["person_story"]
        participant_rows = state["participant"]
        ps_layers = {
            str(presence.get("source_layer"))
            for link in ps_rows
            for presence in link.get("presences", [])
            if isinstance(presence, Mapping)
        }
        participant_sections = {
            str(section)
            for row in participant_rows
            for section in row.get("source_sections", [])
        }
        combined_layers = ps_layers | participant_sections
        source_presence = layer_presence(combined_layers)
        scene_roles = sorted(
            {str(row.get("role")) for row in participant_rows},
            key=lambda role: (ROLE_ORDER.get(role, 99), role),
        )
        association_sources: list[dict[str, Any]] = []
        for link in sorted(ps_rows, key=lambda row: str(row.get("id", ""))):
            association_sources.append(
                {
                    "type": "person_story",
                    "record_id": str(link.get("id")),
                    "source_layers": sorted(
                        str(presence.get("source_layer"))
                        for presence in link.get("presences", [])
                        if isinstance(presence, Mapping)
                    ),
                    "resolution_status": link.get("resolution_status"),
                    "review_status": link.get("review_status"),
                    "confidence": link.get("confidence"),
                    "evidence_ids": sorted(str(value) for value in link.get("evidence_ids", [])),
                }
            )
        for row in sorted(participant_rows, key=lambda item: str(item.get("participant_id", ""))):
            association_sources.append(
                {
                    "type": "reviewed_participant",
                    "record_id": str(row.get("participant_id")),
                    "role": row.get("role"),
                    "source_sections": sorted(str(value) for value in row.get("source_sections", [])),
                    "review_status": "reviewed",
                    "basis": row.get("basis"),
                    "evidence_ids": sorted(str(value) for value in row.get("evidence_ids", [])),
                    "provenance_refs": sorted(str(value) for value in row.get("provenance_refs", [])),
                }
            )

        ps_reviewed = any(row.get("review_status") == "reviewed" for row in ps_rows)
        ps_candidate = any(row.get("review_status") == "candidate" for row in ps_rows)
        hard_scene = bool(set(scene_roles) & HARD_SCENE_ROLES)
        contextual = bool(set(scene_roles) & CONTEXTUAL_SCENE_ROLES)
        participant_annotation_only = "annotation_only" in scene_roles
        ps_main_reviewed = ps_reviewed and "main_text" in ps_layers
        ps_liu_reviewed = ps_reviewed and "liu_annotation" in ps_layers
        if hard_scene:
            priority_class = "reviewed_hard_scene"
        elif ps_main_reviewed:
            priority_class = "reviewed_main_text"
        elif contextual:
            priority_class = "reviewed_contextual"
        elif ps_liu_reviewed or participant_annotation_only:
            priority_class = "reviewed_liu_only"
        elif ps_reviewed:
            priority_class = "reviewed_liu_only"
        else:
            priority_class = "candidate_textual"
        association_strength = "reviewed_scene" if hard_scene else "reviewed_textual" if (ps_reviewed or participant_rows) else "candidate_textual"
        story = search_by_id[story_id]
        person_story = ps_rows[0] if ps_rows else None
        row = {
            "story_id": story_id,
            "chapter_id": story["chapter_id"],
            "chapter_heading": story["chapter_heading"],
            "story_ordinal": story["entry_number"],
            "chapter": story["chapter_heading"],
            "relation_to_person": source_presence,
            "source_presence": source_presence,
            "short_excerpt": source_excerpt(str(story["main_text"])),
            "current_story": False,
            "person_story_link_id": str(person_story.get("id")) if person_story else None,
            "resolution_status": person_story.get("resolution_status") if person_story else None,
            "confidence": person_story.get("confidence") if person_story else None,
            "review_status": person_story.get("review_status") if person_story else "reviewed",
            "research_scope": "published" if story_id in published_ids else "research_only",
            "association_sources": association_sources,
            "research_presence": {
                "main_text": "main_text" in combined_layers,
                "liu_annotation": "liu_annotation" in combined_layers,
            },
            "scene_roles": scene_roles,
            "association_strength": association_strength,
            "research_priority_class": priority_class,
        }
        output_by_person[person_id].append(row)

        if ps_rows and participant_rows:
            both_pairs.append({"person_id": person_id, "story_id": story_id, "association_sources": association_sources})
        elif ps_rows:
            person_story_only.append({"person_id": person_id, "story_id": story_id, "source_presence": source_presence})
        else:
            participant_only.append({"person_id": person_id, "story_id": story_id, "scene_roles": scene_roles})

        ps_presence = {"main_text": "main_text" in ps_layers, "liu_annotation": "liu_annotation" in ps_layers}
        participant_presence = {
            "main_text": "main_text" in participant_sections,
            "liu_annotation": "liu_annotation" in participant_sections,
        }
        if ps_rows and participant_rows and ps_presence != participant_presence:
            source_layer_disagreements.append(
                {
                    "person_id": person_id,
                    "story_id": story_id,
                    "person_story_presence": ps_presence,
                    "participant_presence": participant_presence,
                    "person_story_link_ids": sorted(str(link.get("id")) for link in ps_rows),
                    "participant_ids": sorted(str(item.get("participant_id")) for item in participant_rows),
                }
            )
        if len(set(scene_roles)) > 1:
            role_disagreements.append(
                {
                    "person_id": person_id,
                    "story_id": story_id,
                    "roles": scene_roles,
                    "participant_ids": sorted(str(item.get("participant_id")) for item in participant_rows),
                }
            )

    for person_id in sorted(person_ids):
        output_by_person[person_id].sort(
            key=lambda row: (story_order.get(str(row["story_id"]), 10**9), str(row["story_id"]))
        )
    both_pairs.sort(key=lambda row: (row["person_id"], row["story_id"]))
    person_story_only.sort(key=lambda row: (row["person_id"], row["story_id"]))
    participant_only.sort(key=lambda row: (row["person_id"], row["story_id"]))
    source_layer_disagreements.sort(key=lambda row: (row["person_id"], row["story_id"]))
    role_disagreements.sort(key=lambda row: (row["person_id"], row["story_id"]))
    audit = {
        "schema": 1,
        "projection": "ds2_1a_research_association_union_audit",
        "source_documents": [
            {"path": PERSON_STORY_LINKS_PATH.as_posix(), "sha256": sha256_file(root, PERSON_STORY_LINKS_PATH)},
            {"path": H0C_PARTICIPANT_FREEZE_PATH.as_posix(), "sha256": sha256_file(root, H0C_PARTICIPANT_FREEZE_PATH)},
        ],
        "counts": {
            "union_pairs": len(pair_states),
            "person_story_pairs": len(person_story_pairs),
            "participant_pairs": len(participant_by_pair),
            "both_pairs": len(both_pairs),
            "person_story_only_pairs": len(person_story_only),
            "participant_only_pairs": len(participant_only),
            "source_layer_disagreement_count": len(source_layer_disagreements),
            "role_disagreement_count": len(role_disagreements),
            "unresolved_provenance_anomaly_count": len(participant_anomalies),
        },
        "both_pairs": both_pairs,
        "person_story_only_pairs": person_story_only,
        "participant_only_pairs": participant_only,
        "source_layer_disagreements": source_layer_disagreements,
        "role_disagreements": role_disagreements,
        "unresolved_provenance_anomalies": participant_anomalies,
    }
    return dict(output_by_person), audit


def load_jinshu_source(root: Path, record: Mapping[str, Any]) -> str:
    relative = Path(str(record.get("file_path", "")))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Jinshu unit has unsafe file path: {relative}")
    path = root / relative
    if not path.is_file():
        raise FileNotFoundError(f"Jinshu unit source is missing: {relative}")
    text = path.read_text(encoding="utf-8")
    if SOURCE_MARKER not in text:
        raise ValueError(f"Jinshu unit has no exact-source section: {relative}")
    return text.split(SOURCE_MARKER, 1)[1]


def resolved_aliases(root: Path, person_ids: set[str]) -> dict[str, list[dict[str, Any]]]:
    aliases_by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    # DS2.1A is an active research surface.  It must see the repaired alias
    # registry so invalid shared/lexical evidence cannot re-enter its search
    # and biography projections.  Older frozen readers keep their own
    # explicit witness where required; this active index does not.
    aliases = read_json(root, ALIASES_PATH).get("aliases", [])
    for alias in aliases:
        if not isinstance(alias, Mapping):
            continue
        if alias.get("status") != "resolved" or alias.get("resolution_mode") != "exact":
            continue
        surfaces = alias.get("resolved_person_ids", [])
        if not isinstance(surfaces, list):
            continue
        source_mention_ids = sorted(
            str(item.get("mention_id"))
            for item in alias.get("source_evidence", [])
            if isinstance(item, Mapping) and item.get("mention_id")
        )
        record = {
            "alias_id": str(alias.get("alias_id")),
            "surface": str(alias.get("surface")),
            "alias_type": str(alias.get("alias_type")),
            "resolution_mode": "exact",
            "status": "resolved",
            "source_mention_ids": source_mention_ids,
        }
        for person_id in sorted(set(str(item) for item in surfaces) & person_ids):
            aliases_by_person[person_id].append(record.copy())
    for person_id in aliases_by_person:
        aliases_by_person[person_id].sort(key=lambda row: (row["surface"], row["alias_id"]))
    return aliases_by_person


def reviewed_relation_context(
    sc1: Mapping[str, Any], person_ids: set[str]
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    context = {
        person_id: {"relations": [], "kinship": []}
        for person_id in sorted(person_ids)
    }
    seen: set[tuple[str, str]] = set()
    for relation in sc1.get("relations", []):
        if not isinstance(relation, Mapping):
            continue
        if relation.get("review_status") != "reviewed" or relation.get("relation_basis") != "direct":
            continue
        relation_id = str(relation.get("id", ""))
        subject_id = str(relation.get("subject_id", ""))
        object_id = str(relation.get("object_id", ""))
        if not relation_id or subject_id not in person_ids or object_id not in person_ids:
            continue
        for person_id, other_id, direction in (
            (subject_id, object_id, "subject"),
            (object_id, subject_id, "object"),
        ):
            key = (person_id, relation_id)
            if key in seen:
                continue
            seen.add(key)
            row = {
                "relation_id": relation_id,
                "other_person_id": other_id,
                "direction": direction,
                "relation_type": str(relation.get("relation_type", "")),
                "relation_subtype": relation.get("relation_subtype"),
                "relation_scope": relation.get("relation_scope"),
                "label": relation.get("label"),
                "story_ids": sorted(str(item) for item in relation.get("story_ids", [])),
                "evidence_ids": sorted(str(item) for item in relation.get("evidence_ids", [])),
                "assertion_status": relation.get("assertion_status"),
                "review_status": "reviewed",
            }
            if relation.get("relation_type") in {"kinship", "marriage"}:
                context[person_id]["kinship"].append(row)
            else:
                context[person_id]["relations"].append(row)
    for values in context.values():
        for key in values:
            values[key].sort(key=lambda row: (row["relation_id"], row["other_person_id"]))
    return context


def fact_endpoints(record: Mapping[str, Any]) -> set[str]:
    endpoints = {str(item) for item in record.get("subject_ids", []) if item}
    for key in ("person_id", "subject_id", "object_id", "person_a_id", "person_b_id"):
        value = record.get(key)
        if value:
            endpoints.add(str(value))
    return endpoints


def reviewed_fact_rows(root: Path, relative: Path) -> list[Mapping[str, Any]]:
    if not (root / relative).is_file():
        return []
    document = read_json(root, relative)
    rows: list[Mapping[str, Any]] = []
    for key in ("fact_index", "facts", "records"):
        value = document.get(key) if isinstance(document, Mapping) else None
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, Mapping))
    return rows


def reviewed_structured_context(
    root: Path, person_ids: set[str], relation_context: dict[str, dict[str, list[dict[str, Any]]]]
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    context = {
        person_id: {
            "aliases": [],
            "relations": list(relation_context[person_id]["relations"]),
            "kinship": list(relation_context[person_id]["kinship"]),
            "offices": [],
            "events": [],
        }
        for person_id in sorted(person_ids)
    }

    office_rows: list[tuple[Mapping[str, Any], str]] = []
    for relative in (H0C_FACTS_PATH, HG1_FACT_EXTENSION_PATH):
        for row in reviewed_fact_rows(root, relative):
            if row.get("review_status") != "reviewed":
                continue
            if row.get("fact_type") in {"office_tenure", "office"}:
                office_rows.append((row, relative.as_posix()))
    seen_offices: set[tuple[str, str]] = set()
    for row, source_path in office_rows:
        fact_id = str(row.get("fact_id") or row.get("tenure_id") or row.get("id") or "")
        for person_id in sorted(fact_endpoints(row) & person_ids):
            key = (person_id, fact_id)
            if not fact_id or key in seen_offices:
                continue
            seen_offices.add(key)
            context[person_id]["offices"].append(
                {
                    "fact_id": fact_id,
                    "fact_type": str(row.get("fact_type")),
                    "office_id": row.get("office_id"),
                    "office_title": row.get("office_title"),
                    "start_year_ce": row.get("start_year_ce"),
                    "end_year_ce": row.get("end_year_ce"),
                    "temporal_precision": row.get("temporal_precision"),
                    "evidence_ids": sorted(str(item) for item in row.get("evidence_ids", [])),
                    "source_path": source_path,
                    "assertion_status": row.get("assertion_status"),
                    "review_status": "reviewed",
                }
            )

    event_rows: list[tuple[Mapping[str, Any], str]] = []
    for relative in (H0C_FACTS_PATH, H0C_EVENT_PARTICIPATIONS_PATH, H0C_PERSON_ACTIVITIES_PATH, HG1_FACT_EXTENSION_PATH):
        for row in reviewed_fact_rows(root, relative):
            if row.get("review_status") != "reviewed":
                continue
            if row.get("fact_type") in {"event_participation", "person_activity", "event"} or row.get("event_id"):
                event_rows.append((row, relative.as_posix()))
    seen_events: set[tuple[str, str]] = set()
    for row, source_path in event_rows:
        fact_id = str(row.get("fact_id") or row.get("event_participation_id") or row.get("activity_id") or row.get("event_id") or "")
        for person_id in sorted(fact_endpoints(row) & person_ids):
            key = (person_id, fact_id)
            if not fact_id or key in seen_events:
                continue
            seen_events.add(key)
            context[person_id]["events"].append(
                {
                    "fact_id": fact_id,
                    "fact_type": str(row.get("fact_type") or row.get("participation_type") or row.get("activity_type") or "event"),
                    "event_id": row.get("event_id"),
                    "story_id": row.get("story_id"),
                    "participation_type": row.get("participation_type"),
                    "temporal_precision": row.get("temporal_precision") or row.get("precision"),
                    "start_year_ce": row.get("start_year_ce"),
                    "end_year_ce": row.get("end_year_ce"),
                    "evidence_ids": sorted(str(item) for item in row.get("evidence_ids", [])),
                    "source_path": source_path,
                    "assertion_status": row.get("assertion_status"),
                    "review_status": "reviewed",
                }
            )

    aliases = resolved_aliases(root, person_ids)
    for person_id in sorted(person_ids):
        context[person_id]["aliases"] = aliases.get(person_id, [])
        context[person_id]["offices"].sort(key=lambda row: (row["fact_id"], str(row.get("office_title") or "")))
        context[person_id]["events"].sort(key=lambda row: (row["fact_id"], str(row.get("event_id") or "")))
    return context


def confirmed_biography_units(root: Path) -> dict[str, set[str]]:
    """Use only the existing deterministic own-biography identity support."""

    result: dict[str, set[str]] = defaultdict(set)
    if not (root / JINSHU_MENTIONS_PATH).is_file():
        return result
    mentions = read_json(root, JINSHU_MENTIONS_PATH).get("mentions", [])
    for mention in mentions:
        if (
            isinstance(mention, Mapping)
            and mention.get("person_id")
            and mention.get("confidence") == "high"
            and mention.get("biography_scope") == "own_biography"
            and mention.get("unit_id")
        ):
            result[str(mention["person_id"])].add(str(mention["unit_id"]))
    return result


def biography_entries(
    root: Path, people: list[Mapping[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    aliases_by_person = resolved_aliases(root, {str(row["id"]) for row in people})
    confirmed = confirmed_biography_units(root)
    index = read_json(root, JINSHU_INDEX_PATH)
    records = [
        row
        for row in index.get("units", [])
        if isinstance(row, Mapping) and row.get("category") == "liezhuan"
    ]
    records.sort(key=lambda row: (int(row.get("volume_number") or 10**9), str(row.get("unit_id", ""))))
    output: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for person in people:
        person_id = str(person["id"])
        canonical = str(person.get("canonical_name", ""))
        alias_surfaces = [str(row["surface"]) for row in aliases_by_person.get(person_id, [])]
        terms = [canonical] + [surface for surface in alias_surfaces if surface != canonical]
        seen_units: set[str] = set()
        for record in records:
            unit_id = str(record.get("unit_id", ""))
            if not unit_id or unit_id in seen_units:
                continue
            source = load_jinshu_source(root, record)
            folded_source = fold(compact_text(source))
            canonical_match = bool(canonical) and fold(canonical) in folded_source
            alias_match = any(fold(term) in folded_source for term in alias_surfaces if term)
            if not (canonical_match or alias_match):
                continue
            seen_units.add(unit_id)
            basis: list[str] = []
            if canonical_match:
                basis.append("canonical_name")
            if alias_match:
                basis.append("alias")
            status = "confirmed" if unit_id in confirmed.get(person_id, set()) else "candidate"
            output[person_id].append(
                {
                    "work": "晉書",
                    "unit_id": unit_id,
                    "volume": record.get("volume_number"),
                    "unit_title": record.get("title"),
                    "match_basis": basis,
                    "short_excerpt": source_excerpt(source, terms),
                    "source_path": str(record.get("file_path")),
                    "source_sha256": record.get("unit_text_sha256"),
                    "match_status": status,
                }
            )
        output[person_id].sort(
            key=lambda row: (
                0 if row["match_status"] == "confirmed" else 1,
                int(row["volume"]) if isinstance(row["volume"], int) else 10**9,
                row["unit_id"],
            )
        )
    return output


def build_document(root: Path = ROOT) -> dict[str, Any]:
    sc1 = read_json(root, SC1_PATH)
    links_document = read_json(root, PERSON_STORY_LINKS_PATH)
    search_corpus = build_shishuo_search_corpus(root, sc1)
    people = registered_persons(root)
    people_by_id = {str(row["id"]): row for row in people}
    search_by_id = {str(row["story_id"]): row for row in search_corpus}
    person_ids = set(people_by_id)

    all_links = [link for link in links_document.get("links", []) if isinstance(link, Mapping)]
    if len(all_links) != int(links_document.get("link_count", len(all_links))):
        raise ValueError("PersonStory link count is inconsistent")
    invalid_people = sorted(
        {str(link.get("person_id")) for link in all_links if str(link.get("person_id")) not in person_ids}
    )
    if invalid_people:
        raise ValueError(f"PersonStory links reference unregistered Persons: {invalid_people}")
    invalid_stories = sorted(
        {str(link.get("entry_id")) for link in all_links if str(link.get("entry_id")) not in search_by_id}
    )
    if invalid_stories:
        raise ValueError(f"PersonStory links reference missing canonical Stories: {invalid_stories}")
    published_ids = {
        str(row["id"])
        for row in exposed_stories(sc1)
    }
    relation_context = reviewed_relation_context(sc1, person_ids)
    structured_context = reviewed_structured_context(root, person_ids, relation_context)
    biography_by_person = biography_entries(root, people)
    association_by_person, association_audit = build_association_union(
        root,
        sc1,
        links_document,
        search_corpus,
        people,
    )

    output_people: dict[str, dict[str, Any]] = {}
    for person_id in sorted(person_ids):
        story_rows = association_by_person.get(person_id, [])
        story_ids = {str(row["story_id"]) for row in story_rows}
        person_story_sources = [
            source
            for row in story_rows
            for source in row.get("association_sources", [])
            if source.get("type") == "person_story"
        ]
        story_counts = {
            "story_count_total": len(story_ids),
            "story_count_published": len({row["story_id"] for row in story_rows if row["research_scope"] == "published"}),
            "story_count_research_only": len({row["story_id"] for row in story_rows if row["research_scope"] == "research_only"}),
            "main_text_story_count": len({row["story_id"] for row in story_rows if row["research_presence"]["main_text"]}),
            "liu_annotation_only_story_count": len({row["story_id"] for row in story_rows if row["research_presence"]["liu_annotation"] and not row["research_presence"]["main_text"]}),
            "both_layer_story_count": len({row["story_id"] for row in story_rows if row["research_presence"]["main_text"] and row["research_presence"]["liu_annotation"]}),
            "reviewed_link_count": sum(source.get("review_status") == "reviewed" for source in person_story_sources),
            "candidate_link_count": sum(source.get("review_status") == "candidate" for source in person_story_sources),
        }
        output_people[person_id] = {
            "person_id": person_id,
            "canonical_name": str(people_by_id[person_id].get("canonical_name", person_id)),
            "shishuo_stories": story_rows,
            **story_counts,
            "historical_biography_entries": biography_by_person.get(person_id, []),
            "reviewed_context": structured_context[person_id],
        }

    source_documents = [
        {"path": relative.as_posix(), "sha256": sha256_file(root, relative)}
        for relative in (
            SC1_PATH,
            PEOPLE_PATH,
            PERSON_STORY_LINKS_PATH,
            SHISHUO_CORPUS_INDEX_PATH,
            H0C_PARTICIPANT_FREEZE_PATH,
            ALIASES_PATH,
            JINSHU_INDEX_PATH,
            JINSHU_MENTIONS_PATH,
            H0C_FACTS_PATH,
            H0C_EVENT_PARTICIPATIONS_PATH,
            H0C_PERSON_ACTIVITIES_PATH,
            HG1_FACT_EXTENSION_PATH,
        )
        if (root / relative).is_file()
    ]
    return {
        "schema": 1,
        "projection": "ds2_1a_person_research_surface",
        "scope": {
            "person_policy": "canonical registered Persons; existing PersonStory links are not re-inferred",
            "story_policy": "all existing PersonStory links, classified as published or research_only against the protected SC1 publication scope",
            "search_policy": "all canonical Shishuo corpus-index entries; main text and Liu annotation remain separate",
            "biography_policy": "local Jinshu liezhuan unit matches only; no identity inference",
        },
        "source_documents": source_documents,
        "association_union": {
            "audit_path": ASSOCIATION_AUDIT_PATH.as_posix(),
            "union_pairs": association_audit["counts"]["union_pairs"],
            "person_story_pairs": association_audit["counts"]["person_story_pairs"],
            "participant_pairs": association_audit["counts"]["participant_pairs"],
            "both_pairs": association_audit["counts"]["both_pairs"],
            "person_story_only_pairs": association_audit["counts"]["person_story_only_pairs"],
            "participant_only_pairs": association_audit["counts"]["participant_only_pairs"],
            "source_layer_disagreement_count": association_audit["counts"]["source_layer_disagreement_count"],
            "role_disagreement_count": association_audit["counts"]["role_disagreement_count"],
        },
        "search_corpus": {
            "path": SHISHUO_SEARCH_OUTPUT_PATH.as_posix(),
            "record_count": len(search_corpus),
        },
        "people": output_people,
    }


def build(root: Path = ROOT, output_path: Path = OUTPUT_PATH) -> dict[str, Any]:
    document = build_document(root)
    search_corpus = build_shishuo_search_corpus(root)
    sc1 = read_json(root, SC1_PATH)
    links_document = read_json(root, PERSON_STORY_LINKS_PATH)
    people = registered_persons(root)
    _, association_audit = build_association_union(root, sc1, links_document, search_corpus, people)
    write_json(root, SHISHUO_SEARCH_OUTPUT_PATH, {
        "schema": 1,
        "projection": "ds2_1a_shishuo_search_corpus",
        "work": "世說新語",
        "scope": "all canonical corpus-index entries; research-only projection",
        "source_documents": [
            {
                "path": SHISHUO_CORPUS_INDEX_PATH.as_posix(),
                "sha256": sha256_file(root, SHISHUO_CORPUS_INDEX_PATH),
            }
        ],
        "records": search_corpus,
    })
    write_json(root, ASSOCIATION_AUDIT_PATH, association_audit)
    write_json(root, output_path, document)
    return document


def main() -> int:
    document = build(ROOT)
    print(
        json.dumps(
            {
                "people": len(document["people"]),
                "shishuo_story_links": sum(len(row["shishuo_stories"]) for row in document["people"].values()),
                "association_union_pairs": document["association_union"]["union_pairs"],
                "search_stories": document["search_corpus"]["record_count"],
                "biography_entries": sum(len(row["historical_biography_entries"]) for row in document["people"].values()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
