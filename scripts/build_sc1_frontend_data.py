#!/usr/bin/env python3
"""Build the static SC1 Story Chain frontend bundle.

SC1 is a publication projection, not a new textual or semantic source.  It
reads the existing WP1 bundle for shared Person/Relation/Evidence records,
then adds the frozen SC0 selection and any separate M2 experience expansion
Stories from the canonical entry index,
punctuation records, and reviewed PersonStoryLinks.  The two output files are
byte-identical views of one in-memory bundle for the Vite build-time import.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from opencc import OpenCC

try:
    from .build_six_person_pilot import (
        parse_frontmatter,
        parse_shishuo_sections,
    )
    from .build_wp1_sample import (
        assertion_for_mention,
        read_json as read_wp1_json,
        resolution_mode_for_mention,
    )
    from .reading_layers import build_display_reading, strip_display_punctuation
    from .person_sketch import build_person_sketches
    from .person_resolution import load_effective_mentions
    from .story_scene_contexts import DERIVED_PATH as SCENE_DERIVED_PATH, SOURCE_PATH as SCENE_SOURCE_PATH, project as project_scene_contexts, validate_source as validate_scene_source
except ImportError:  # direct execution
    from build_six_person_pilot import (
        parse_frontmatter,
        parse_shishuo_sections,
    )
    from build_wp1_sample import (
        assertion_for_mention,
        read_json as read_wp1_json,
        resolution_mode_for_mention,
    )
    from reading_layers import build_display_reading, strip_display_punctuation
    from person_sketch import build_person_sketches
    from person_resolution import load_effective_mentions
    from story_scene_contexts import DERIVED_PATH as SCENE_DERIVED_PATH, SOURCE_PATH as SCENE_SOURCE_PATH, project as project_scene_contexts, validate_source as validate_scene_source


ROOT = Path(__file__).resolve().parents[1]
WP1_BUNDLE_PATH = ROOT / "data/derived/wp1-site.json"
GOLD_PATH = ROOT / "data/story-chain-gold-set.json"
STORY_EXPANSION_PATH = ROOT / "data/annotation/story-expansion-wave-1.json"
CHAIN_INDEX_PATH = ROOT / "data/derived/story-chain-gold-index.json"
CORPUS_INDEX_PATH = ROOT / "data/shishuo-corpus-index.json"
MENTIONS_PATH = ROOT / "data/mentions/shishuo.json"
PEOPLE_REGISTRY_PATH = ROOT / "data/people.json"
ALIASES_PATH = ROOT / "data/aliases.json"
PERSON_STORY_INDEX_PATH = ROOT / "data/derived/person-story-index.json"
PUNCTUATION_PATH = ROOT / "data/annotation/wp1-punctuation.json"
PRODUCTION_EVIDENCE_PATH = ROOT / "data/evidence/wp1-evidence.json"
PRODUCTION_RELATIONS_PATH = ROOT / "data/annotation/wp1-relations.json"
DERIVED_PATH = ROOT / "data/derived/sc1-site.json"
VITE_PATH = ROOT / "site/src/generated/sc1-site.json"

DEFAULT_TIME = {
    "status": "unknown",
    "label": None,
    "start_year": None,
    "end_year": None,
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pair(text: str, converter: OpenCC) -> dict[str, str]:
    return {"original": text, "simplified": converter.convert(text)}


def entry_path(entry_id: str, entry_by_id: Mapping[str, Mapping[str, Any]]) -> Path:
    entry = entry_by_id[entry_id]
    return ROOT / str(entry["path"])


def parsed_entry(entry_id: str, entry_by_id: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], str, str, list[dict[str, Any]]]:
    path = entry_path(entry_id, entry_by_id)
    text = path.read_text(encoding="utf-8")
    metadata = parse_frontmatter(text)
    source_match = re.search(
        r"## Original source \(exact\)\n\n(.*?)\n\n## Main text",
        text,
        flags=re.DOTALL,
    )
    source_text = source_match.group(1) if source_match else ""
    main_text = ""
    annotations: list[dict[str, Any]] = []
    for section, body, section_metadata in parse_shishuo_sections(text):
        if section == "main_text":
            main_text = body.rstrip("\n")
        elif section == "liu_annotation":
            annotation_id = str(section_metadata.get("annotation_id", f"annotation-{len(annotations) + 1:03d}"))
            annotations.append(
                {
                    "id": annotation_id,
                    "text": body.rstrip("\n"),
                    "metadata": dict(section_metadata),
                }
            )
    if not main_text:
        raise ValueError(f"SC1 entry has no main text: {path}")
    return metadata, main_text, source_text, annotations


def source_locator(
    entry_id: str,
    metadata: Mapping[str, Any],
    entry_path_value: Path,
    *,
    annotation_id: str | None = None,
) -> dict[str, Any]:
    start_location = metadata.get("start_location", {})
    end_location = metadata.get("end_location", {})
    return {
        "artifact_type": "shishuo_entry",
        "entry_id": entry_id,
        "chapter_id": metadata.get("chapter_id"),
        "artifact_path": entry_path_value.relative_to(ROOT).as_posix(),
        "artifact_sha256": sha256_file(entry_path_value),
        "source_normalized_filename": metadata.get("source_normalized_filename"),
        "normalized_line_start": start_location.get("normalized_line"),
        "normalized_line_end": end_location.get("normalized_line"),
        "page_marker_start": start_location.get("page_marker"),
        "page_marker_end": end_location.get("page_marker"),
        "annotation_id": annotation_id,
        "source_provenance": {
            "witness_id": "shishuo-kanripo-wyg",
            "source_path": metadata.get("source_path"),
            "source_sha256": metadata.get("source_sha256"),
        },
    }


def build_evidence(
    entry_id: str,
    metadata: Mapping[str, Any],
    main_text: str,
    annotations: list[Mapping[str, Any]],
    entry_path_value: Path,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    evidence: list[dict[str, Any]] = []
    section_evidence: dict[str, str] = {}
    main_id = f"evidence-sc1-{entry_id}-main"
    evidence.append(
        {
            "id": main_id,
            "source_id": "source-001",
            "evidence_type": "primary_text",
            "quote": main_text,
            "locator": source_locator(entry_id, metadata, entry_path_value),
            "assertion_status": "attested",
            "review_status": "candidate",
            "notes": "SC1 static publication evidence copied from the canonical entry; it does not change the source text.",
        }
    )
    section_evidence["main_text"] = main_id
    if annotations:
        for annotation in annotations:
            annotation_number = str(annotation["id"])
            annotation_evidence_id = f"evidence-sc1-{entry_id}-{annotation_number}"
            evidence.append(
                {
                    "id": annotation_evidence_id,
                    "source_id": "source-001",
                    "evidence_type": "annotation",
                    "quote": str(annotation["text"]),
                    "locator": source_locator(
                        entry_id,
                        metadata,
                        entry_path_value,
                        annotation_id=annotation_number,
                    ),
                    "assertion_status": "attested",
                    "review_status": "candidate",
                    "notes": "SC1 annotation evidence remains canonical source material; no unreviewed annotation punctuation is published as reading text.",
                }
            )
            section_evidence[f"liu_annotation:{annotation_number}"] = annotation_evidence_id
        section_evidence["liu_annotation"] = section_evidence[f"liu_annotation:{annotations[0]['id']}"]
    return evidence, section_evidence


def frontend_mention(
    mention: Mapping[str, Any],
    section_evidence: Mapping[str, str],
) -> dict[str, Any]:
    section = str(mention.get("section", "main_text"))
    evidence = mention.get("evidence", {})
    annotation_metadata = mention.get("source_section_metadata", {})
    annotation_key = annotation_metadata.get("annotation_id") if isinstance(annotation_metadata, Mapping) else None
    evidence_id = (
        section_evidence.get(f"liu_annotation:{annotation_key}")
        if section == "liu_annotation" and annotation_key
        else None
    ) or section_evidence.get(section, section_evidence["main_text"])
    anchor: dict[str, Any] = {
        "text": mention.get("surface", ""),
        "section": section,
        "offset": evidence.get("section_offset", 0),
    }
    projected = {
        "id": mention["mention_id"],
        "story_id": mention["entry_id"],
        "surface": mention.get("surface", ""),
        "section": section,
        "person_id": mention.get("person_id"),
        "candidate_person_ids": mention.get("candidate_person_ids", []),
        "alias_type": mention.get("alias_type", ""),
        "resolution_mode": resolution_mode_for_mention(dict(mention)),
        "confidence": mention.get("confidence", "unresolved"),
        "anchor": anchor,
        "evidence_ids": [evidence_id],
        "assertion_status": assertion_for_mention(dict(mention)),
        "review_status": "candidate",
        "notes": "Projected from the existing conservative Person/Mention pilot; no participant status is inferred.",
    }
    if isinstance(mention.get("display_span"), Mapping):
        span = mention["display_span"]
        projected["display_span"] = {
            "offset": span.get("offset"),
            "end_offset_exclusive": span.get("end_offset_exclusive"),
            "text": span.get("text"),
            "basis": span.get("basis", "maximal_semantic_person_span"),
            "status": span.get("status", "safe"),
            "evidence_ids": list(span.get("evidence_ids", [])),
        }
    for key in (
        "resolution_status",
        "resolution_target",
        "resolution_candidates",
        "resolution_review_status",
        "resolution_decision_source",
        "resolution_evidence_ids",
        "resolution_note",
        "resolution_method",
        "derived_only",
        "span_decision_id",
        "coreference_antecedent_mention_id",
    ):
        if key in mention:
            projected[key] = mention[key]
    return projected


def publication_state(punctuation: Mapping[str, Any], canonical_main_text: str) -> str:
    if (
        punctuation.get("status") == "reviewed"
        and punctuation.get("review_status") == "reviewed"
    ):
        return "production_ready"
    main = punctuation.get("sections", {}).get("main_text", {})
    if (
        punctuation.get("status") in {"candidate", "aligned"}
        and isinstance(main.get("punctuated_text"), str)
        and main.get("punctuated_text")
        and strip_display_punctuation(main["punctuated_text"])
        == strip_display_punctuation(canonical_main_text)
    ):
        return "preview_ready"
    return "blocked"


def build_ui_labels(converter: OpenCC) -> dict[str, Any]:
    labels = {
        "person_stories_heading": "《世說》中的故事",
        "person_sketch_identity": "人物概覽",
        "person_sketch_aliases": "《世說》怎樣稱呼他／她",
        "person_sketch_stories": "《世說》中的他／她",
        "person_sketch_relations": "人物關係",
        "person_sketch_courtesy_name": "字",
        "person_sketch_clan": "族屬",
        "person_sketch_roles": "身份",
        "person_sketch_intro": "簡介",
        "person_sketch_evidence": "人物依據",
        "person_sketch_candidate": "資料整理預覽",
        "person_sketch_reviewed": "已復核資料",
        "person_sketch_main_story_count": "正文故事",
        "person_sketch_annotation_story_count": "劉注提及",
        "person_sketch_life_glimpse": "一瞥",
        "story_people_heading": "本則人物",
        "primary_story_label": "正文出現",
        "annotation_story_label": "劉注提及",
        "read_story": "閱讀",
        "reviewed_punctuation": "句讀：已復核",
        "preview_punctuation": "句讀：參考底本整理 · 待復核",
        "random_story": "隨便讀一則",
        "random_person": "隨便認識一個人",
        "scene_heading": "舞臺",
        "scene_people_heading": "入畫",
        "scene_position_heading": "舞臺",
        "scene_background_heading": "底色",
        "scene_focus_heading": "舞臺",
        "scene_off_frame_heading": "畫外",
        "scene_ground_heading": "底色",
        "scene_resonance_heading": "餘韻",
        "scene_evidence_heading": "查看依據",
        "scene_unknown": "未詳",
        "scene_not_materialized": "人物卡尚未建立",
    }
    return {key: pair(value, converter) for key, value in labels.items()}


def build(root: Path = ROOT) -> dict[str, Any]:
    if root.resolve() != ROOT.resolve():
        raise ValueError("SC1 builder currently requires the repository root")
    base = read_json(WP1_BUNDLE_PATH)
    production_relations = read_json(PRODUCTION_RELATIONS_PATH).get("records", [])
    gold = read_json(GOLD_PATH)
    chain_index = read_json(CHAIN_INDEX_PATH)
    corpus_entries = read_json(CORPUS_INDEX_PATH)["entries"]
    entry_by_id = {entry["id"]: entry for entry in corpus_entries}
    punctuation_by_id = {
        record["entry_id"]: record
        for record in read_json(PUNCTUATION_PATH)["records"]
    }
    # Project the ER1 effective resolution, while retaining the canonical
    # Mention IDs/anchors.  Candidate identity targets remain non-navigable;
    # only effective production_person targets contribute Person IDs.
    raw_mentions = load_effective_mentions(root)
    registry_people = read_json(PEOPLE_REGISTRY_PATH).get("people", [])
    registry_aliases = read_json(ALIASES_PATH).get("aliases", [])
    person_story_index = read_json(PERSON_STORY_INDEX_PATH)
    selected_records = list(gold["records"])
    if STORY_EXPANSION_PATH.is_file():
        expansion = read_json(STORY_EXPANSION_PATH)
        gold_ids = [str(item["entry_id"]) for item in gold["records"]]
        if expansion.get("gold_story_ids") != gold_ids:
            raise ValueError("M2 Story expansion manifest does not preserve the frozen SC0 Gold Set")
        expansion_records = [
            {"entry_id": str(item["story_id"]), "linked_person_ids": []}
            for item in expansion.get("records", [])
            if isinstance(item, Mapping) and isinstance(item.get("story_id"), str)
        ]
        selected_records.extend(expansion_records)
    selected_records.sort(key=lambda record: int(entry_by_id[record["entry_id"]].get("global_ordinal", 10**9)))
    selected_ids = [record["entry_id"] for record in selected_records]
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("SC1 publication union contains duplicate Story IDs")
    selected_set = set(selected_ids)
    base_stories = {story["id"]: story for story in base["stories"]}
    base_mentions = {mention["id"]: mention for mention in base["mentions"]}
    base_evidence = {item["id"]: item for item in base["evidence"]}
    converter = OpenCC("t2s")

    new_stories: list[dict[str, Any]] = []
    new_mentions: dict[str, dict[str, Any]] = dict(base_mentions)
    new_evidence: dict[str, dict[str, Any]] = dict(base_evidence)
    publication_by_id: dict[str, str] = {}

    # WP1 intentionally remains a small seven-Person sample.  SC1 projects
    # the full materialized registry without changing the WP1 publication
    # contract, so Wave 1 Persons become available to the existing Story /
    # Person navigation as soon as their approved Mentions occur in a selected
    # Story.
    base_people_by_id = {
        str(person.get("id")): person
        for person in base.get("people", [])
        if isinstance(person, Mapping) and isinstance(person.get("id"), str)
    }
    aliases_by_person: dict[str, list[Mapping[str, Any]]] = {}
    for alias in registry_aliases:
        if not isinstance(alias, Mapping):
            continue
        for person_id in alias.get("person_ids", []):
            if isinstance(person_id, str):
                aliases_by_person.setdefault(person_id, []).append(alias)
    mentions_by_person: dict[str, list[Mapping[str, Any]]] = {}
    for mention in raw_mentions:
        person_id = mention.get("person_id")
        if isinstance(person_id, str):
            mentions_by_person.setdefault(person_id, []).append(mention)

    def frontend_people_projection() -> list[dict[str, Any]]:
        projected: list[dict[str, Any]] = []
        for registry_person in registry_people:
            person_id = str(registry_person["person_id"])
            if person_id in base_people_by_id:
                projected.append(dict(base_people_by_id[person_id]))
                continue
            person_mentions = mentions_by_person.get(person_id, [])
            selected_story_ids_for_person = sorted(
                {
                    str(mention.get("entry_id") or mention.get("source_id"))
                    for mention in person_mentions
                    if str(mention.get("entry_id") or mention.get("source_id")) in selected_set
                }
            )
            evidence_ids = list(registry_person.get("materialization", {}).get("identity_evidence_ids", []))
            for mention in person_mentions:
                mention_story_id = str(mention.get("entry_id") or mention.get("source_id"))
                if mention_story_id not in selected_set:
                    continue
                for evidence_id in mention.get("evidence", {}).get("evidence_ids", []):
                    if evidence_id not in evidence_ids:
                        evidence_ids.append(evidence_id)
            aliases = []
            selected_alias_evidence: dict[str, list[str]] = {}
            for mention in person_mentions:
                mention_story_id = str(mention.get("entry_id") or mention.get("source_id"))
                if mention_story_id not in selected_set:
                    continue
                alias_id = mention.get("alias_id")
                if not isinstance(alias_id, str):
                    continue
                selected_alias_evidence.setdefault(alias_id, []).extend(
                    str(item)
                    for item in mention.get("evidence", {}).get("evidence_ids", [])
                    if isinstance(item, str)
                )
            for alias in sorted(
                aliases_by_person.get(person_id, []),
                key=lambda item: (
                    str(item.get("alias_type", "")),
                    str(item.get("surface", "")),
                    str(item.get("alias_id", "")),
                ),
            ):
                aliases.append(
                    {
                        "surface": alias.get("surface", ""),
                        "alias_type": alias.get("alias_type", ""),
                        "resolution_mode": alias.get("resolution_mode", "ambiguous"),
                        "evidence_ids": [
                            evidence_id
                            for evidence_id in sorted(set(selected_alias_evidence.get(str(alias.get("alias_id")), [])))
                        ],
                        "review_status": alias.get("review_status", "candidate"),
                    }
                )
            projected.append(
                {
                    "id": person_id,
                    "scope_role": registry_person.get("scope_role", "primary"),
                    "scope": registry_person.get("scope_role", "primary"),
                    "canonical_name": registry_person.get("canonical_name", ""),
                    "aliases": aliases,
                    "story_ids": selected_story_ids_for_person,
                    "evidence_ids": sorted(evidence_ids),
                    "assertion_status": "attested",
                    "review_status": "candidate",
                    "notes": "P3B.1 materialized Person projected into the SC1 static bundle; editorial review remains candidate.",
                }
            )
        return projected

    frontend_people = frontend_people_projection()
    production_evidence_by_id = {
        str(item.get("id")): item
        for item in read_json(PRODUCTION_EVIDENCE_PATH).get("records", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    frontend_people_evidence_ids: set[str] = set()
    for person in frontend_people:
        frontend_people_evidence_ids.update(
            str(item) for item in person.get("evidence_ids", []) if isinstance(item, str)
        )
        for alias in person.get("aliases", []):
            if isinstance(alias, Mapping):
                frontend_people_evidence_ids.update(
                    str(item) for item in alias.get("evidence_ids", []) if isinstance(item, str)
                )
    for evidence_id in sorted(frontend_people_evidence_ids):
        if evidence_id in production_evidence_by_id:
            new_evidence[evidence_id] = production_evidence_by_id[evidence_id]

    for selection in selected_records:
        entry_id = selection["entry_id"]
        punctuation = punctuation_by_id[entry_id]
        metadata, main_text, source_text, annotations = parsed_entry(entry_id, entry_by_id)
        state = publication_state(punctuation, main_text)
        publication_by_id[entry_id] = state
        if state == "blocked":
            raise ValueError(f"SC1 selected Story is blocked: {entry_id}")

        entry_mentions = [
            mention for mention in raw_mentions
            if mention.get("entry_id") == entry_id
        ]

        canonical_path = entry_path(entry_id, entry_by_id)
        if entry_id == "06-yaliang-019":
            # Keep the existing WP1 identity/evidence/mention records intact;
            # only derive the SC1 reading projection from the same canonical
            # entry and its reviewed punctuation record.
            story = dict(base_stories[entry_id])
            resolved_person_ids = sorted(
                {
                    str(mention.get("person_id"))
                    for mention in entry_mentions
                    if isinstance(mention.get("person_id"), str)
                }
            )
            story["person_ids"] = list(dict.fromkeys([*selection["linked_person_ids"], *resolved_person_ids]))
            story["publication_state"] = state
            story["publication_note"] = "已复核句读"
            story["chapter_heading"] = "雅量第六"
            story["chapter_display"] = pair("雅量第六", converter)
            story["ordinal"] = 19
            story["global_ordinal"] = 370
            base_annotation_evidence = {
                str(item.get("locator", {}).get("annotation_id")): item["id"]
                for item in base_evidence.values()
                if isinstance(item.get("locator"), Mapping)
                and item.get("locator", {}).get("entry_id") == entry_id
                and isinstance(item.get("locator", {}).get("annotation_id"), str)
                and item["id"] in story.get("evidence_ids", [])
            }
            projected_mentions = []
            for mention in entry_mentions:
                if mention.get("mention_id") in base_mentions:
                    # WP1 owns the original evidence projection for this
                    # Story, while ER1 owns the effective identity state.
                    # Merge only the latter so the special WP1 branch cannot
                    # resurrect a collision-resolved Person target.
                    projected = dict(base_mentions[mention["mention_id"]])
                    effective_projection = frontend_mention(mention, {
                        "main_text": "evidence-sc1-06-yaliang-019-main",
                        "liu_annotation:annotation-001": "evidence-sc1-06-yaliang-019-annotation-001",
                        "liu_annotation": "evidence-sc1-06-yaliang-019-annotation-001",
                    })
                    for key in (
                        "person_id",
                        "candidate_person_ids",
                        "resolution_mode",
                        "confidence",
                        "resolution_status",
                        "resolution_target",
                        "resolution_candidates",
                        "resolution_review_status",
                        "resolution_decision_source",
                        "resolution_evidence_ids",
                        "resolution_note",
                        "display_span",
                        "resolution_method",
                        "derived_only",
                        "span_decision_id",
                        "coreference_antecedent_mention_id",
                    ):
                        if key in effective_projection:
                            projected[key] = effective_projection[key]
                else:
                    projected = frontend_mention(mention, {
                        "main_text": "evidence-sc1-06-yaliang-019-main",
                        "liu_annotation:annotation-001": "evidence-sc1-06-yaliang-019-annotation-001",
                        "liu_annotation": "evidence-sc1-06-yaliang-019-annotation-001",
                    })
                new_mentions[projected["id"]] = projected
                projected_mentions.append(projected)
            story["reading"] = build_display_reading(
                punctuation,
                converter,
                people=frontend_people,
                mentions=projected_mentions,
                placement_mentions=entry_mentions,
                canonical_annotations=annotations,
                sources=base["sources"],
                relations=production_relations,
                evidence=list(base_evidence.values()),
                source_text=source_text,
                annotation_evidence_ids=base_annotation_evidence,
            )
            new_stories.append(story)
            continue

        generated_evidence, section_evidence = build_evidence(
            entry_id,
            metadata,
            main_text,
            annotations,
            canonical_path,
        )
        for item in generated_evidence:
            new_evidence[item["id"]] = item

        projected_mentions: list[dict[str, Any]] = []
        for mention in entry_mentions:
            projected = frontend_mention(mention, section_evidence)
            new_mentions[projected["id"]] = projected
            projected_mentions.append(projected)

        reading = build_display_reading(
            punctuation,
            converter,
            people=frontend_people,
            mentions=projected_mentions,
            placement_mentions=entry_mentions,
            canonical_annotations=annotations,
            sources=base["sources"],
            relations=production_relations,
            evidence=list(new_evidence.values()),
            source_text=source_text,
            annotation_evidence_ids={
                annotation_id: evidence_id
                for key, evidence_id in section_evidence.items()
                if key.startswith("liu_annotation:")
                for annotation_id in [key.split(":", 1)[1]]
            },
        )
        story = {
            "id": entry_id,
            "title": metadata.get("chapter_heading", entry_id),
            "title_source": "source_heading",
            "text": main_text,
            "source_entry_id": entry_id,
            "source_ids": ["source-001"],
            "evidence_ids": [
                section_evidence["main_text"],
                *[
                    section_evidence[f"liu_annotation:{annotation['id']}"]
                    for annotation in annotations
                    if f"liu_annotation:{annotation['id']}" in section_evidence
                ],
            ],
            "person_ids": list(dict.fromkeys([
                *selection["linked_person_ids"],
                *[
                    str(mention.get("person_id"))
                    for mention in entry_mentions
                    if isinstance(mention.get("person_id"), str)
                ],
            ])),
            "mention_ids": [mention["mention_id"] for mention in entry_mentions],
            "relation_ids": [],
            "era_ids": [],
            "annotations": [
                {
                    "id": annotation["id"],
                    "text": annotation["text"],
                    "source_location": canonical_path.relative_to(ROOT).as_posix(),
                }
                for annotation in annotations
            ],
            "summary": None,
            "time": dict(DEFAULT_TIME),
            "places": [],
            "assertion_status": "attested",
            "review_status": "candidate",
            "reading": reading,
            "chapter_heading": metadata.get("chapter_heading", ""),
            "chapter_display": pair(str(metadata.get("chapter_heading", "")), converter),
            "ordinal": int(metadata.get("ordinal", entry_by_id[entry_id].get("ordinal", 0))),
            "global_ordinal": int(entry_by_id[entry_id]["global_ordinal"]),
            "publication_state": state,
            "publication_note": "參考底本整理，待人工復核",
            "notes": "SC1 preview publication preserves the unreviewed CRL1/CRL1.1 punctuation status.",
        }
        new_stories.append(story)

    new_stories.sort(key=lambda story: int(story.get("global_ordinal", 10**9)))
    chain_stories = []
    chain_index_by_story = {
        str(item["entry_id"]): item
        for item in chain_index.get("stories", [])
        if isinstance(item, Mapping) and isinstance(item.get("entry_id"), str)
    }
    for selection in selected_records:
        entry_id = selection["entry_id"]
        base_chain = chain_index_by_story.get(entry_id, {})
        entry_mentions = [
            mention for mention in raw_mentions
            if mention.get("entry_id") == entry_id
            and isinstance(mention.get("person_id"), str)
        ]
        resolved_main_person_ids = sorted({
            str(mention["person_id"])
            for mention in entry_mentions
            if mention.get("section") == "main_text"
        })
        resolved_annotation_person_ids = sorted({
            str(mention["person_id"])
            for mention in entry_mentions
            if mention.get("section") == "liu_annotation"
        } - set(resolved_main_person_ids))
        main_person_ids = list(dict.fromkeys([
            *base_chain.get("main_text_person_ids", []),
            *resolved_main_person_ids,
        ]))
        annotation_person_ids = list(dict.fromkeys([
            *base_chain.get("liu_annotation_only_person_ids", []),
            *resolved_annotation_person_ids,
        ]))
        linked_person_ids = list(dict.fromkeys([
            *base_chain.get("linked_person_ids", selection["linked_person_ids"]),
            *resolved_main_person_ids,
            *resolved_annotation_person_ids,
        ]))
        chain_stories.append(
            {
                "entry_id": entry_id,
                "linked_person_ids": linked_person_ids,
                "main_text_person_ids": main_person_ids,
                "liu_annotation_only_person_ids": annotation_person_ids,
                "publication_state": publication_by_id[entry_id],
            }
        )
    person_story_refs = []
    all_chain_person_ids = sorted({
        person_id
        for story in chain_stories
        for person_id in story["linked_person_ids"]
    })
    for person_id in all_chain_person_ids:
        story_ids = [
            story["entry_id"] for story in chain_stories
            if person_id in story["linked_person_ids"]
        ]
        main_ids = [
            story["entry_id"] for story in chain_stories
            if person_id in story["main_text_person_ids"]
        ]
        annotation_only_ids = [
            story["entry_id"] for story in chain_stories
            if person_id in story["liu_annotation_only_person_ids"]
        ]
        person_story_refs.append(
            {
                "person_id": person_id,
                "story_ids": story_ids,
                "main_text_story_ids": main_ids,
                "liu_annotation_only_story_ids": annotation_only_ids,
            }
        )

    person_sketches = build_person_sketches(
        ROOT,
        people=frontend_people,
        frontend_mentions=new_mentions,
        converter=converter,
    )

    scene_source = read_json(ROOT / SCENE_SOURCE_PATH)
    scene_schema_errors = validate_scene_source(ROOT)
    if scene_schema_errors:
        raise ValueError("Story Scene Context schema validation failed: " + "; ".join(scene_schema_errors))
    scene_contexts = project_scene_contexts(
        scene_source,
        story_ids={story["id"] for story in new_stories if story["publication_state"] != "blocked"},
        people=frontend_people,
        evidence_ids=set(new_evidence),
        converter=converter,
    )
    write_json(
        ROOT / SCENE_DERIVED_PATH,
        {
            "schema": 1,
            "stage": "story-scene-context-pilot-derived",
            "generated_from": [str(SCENE_SOURCE_PATH), "data/derived/sc1-site.json"],
            "contexts": scene_contexts,
        },
    )

    bundle = {
        "schema": 1,
        "generated_from": "scripts/build_sc1_frontend_data.py",
        "stories": new_stories,
        "people": frontend_people,
        "mentions": sorted(new_mentions.values(), key=lambda item: item["id"]),
        "relations": production_relations,
        "eras": base["eras"],
        "evidence": sorted(new_evidence.values(), key=lambda item: item["id"]),
        "sources": base["sources"],
        "person_sketches": person_sketches,
        "scene_contexts": scene_contexts,
        "story_chain": {
            "schema": 1,
            "stage": "sc1-story-chain-frontend",
            "generated_from": [
                "data/story-chain-gold-set.json",
                "data/annotation/story-expansion-wave-1.json",
                "data/derived/person-story-links.json",
                "data/derived/story-chain-gold-index.json",
                "data/annotation/wp1-punctuation.json",
            ],
            "story_ids": selected_ids,
            "person_story_refs": person_story_refs,
            "story_person_refs": chain_stories,
        },
        "ui": build_ui_labels(converter),
    }
    write_json(DERIVED_PATH, bundle)
    write_json(VITE_PATH, bundle)
    return bundle


def main() -> int:
    bundle = build()
    states = {state: 0 for state in ("production_ready", "preview_ready", "blocked")}
    for story in bundle["stories"]:
        states[story["publication_state"]] += 1
    print(
        "built SC1 frontend bundle: "
        f"{len(bundle['stories'])} stories; "
        f"production={states['production_ready']}; "
        f"preview={states['preview_ready']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
