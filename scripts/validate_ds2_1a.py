#!/usr/bin/env python3
"""Validate the DS2.1A local Person research projection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

try:
    from .build_ds2_1a_person_research import (
        ALIASES_PATH,
        H0C_FACTS_PATH,
        H0C_PARTICIPANT_FREEZE_PATH,
        H0C_EVENT_PARTICIPATIONS_PATH,
        H0C_PERSON_ACTIVITIES_PATH,
        HG1_FACT_EXTENSION_PATH,
        JINSHU_INDEX_PATH,
        JINSHU_MENTIONS_PATH,
        OUTPUT_PATH,
        ASSOCIATION_AUDIT_PATH,
        PEOPLE_PATH,
        PERSON_STORY_LINKS_PATH,
        ROOT,
        SC1_PATH,
        SHISHUO_CORPUS_INDEX_PATH,
        SHISHUO_SEARCH_OUTPUT_PATH,
        build_shishuo_search_corpus,
        build_association_union,
        compact_text,
        confirmed_biography_units,
        exposed_stories,
        load_jinshu_source,
        parse_canonical_entry,
        registered_persons,
        sha256_file,
        sha256_text,
    )
except ImportError:  # direct execution: python scripts/validate_ds2_1a.py
    from build_ds2_1a_person_research import (  # type: ignore
        ALIASES_PATH,
        H0C_FACTS_PATH,
        H0C_PARTICIPANT_FREEZE_PATH,
        H0C_EVENT_PARTICIPATIONS_PATH,
        H0C_PERSON_ACTIVITIES_PATH,
        HG1_FACT_EXTENSION_PATH,
        JINSHU_INDEX_PATH,
        JINSHU_MENTIONS_PATH,
        OUTPUT_PATH,
        ASSOCIATION_AUDIT_PATH,
        PEOPLE_PATH,
        PERSON_STORY_LINKS_PATH,
        ROOT,
        SC1_PATH,
        SHISHUO_CORPUS_INDEX_PATH,
        SHISHUO_SEARCH_OUTPUT_PATH,
        build_shishuo_search_corpus,
        build_association_union,
        compact_text,
        confirmed_biography_units,
        exposed_stories,
        load_jinshu_source,
        parse_canonical_entry,
        registered_persons,
        sha256_file,
        sha256_text,
    )


def read_json(root: Path, relative: Path) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def path_is_safe(relative: str) -> bool:
    path = Path(relative)
    return not path.is_absolute() and ".." not in path.parts


def contains_forbidden_path(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(contains_forbidden_path(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_forbidden_path(item) for item in value)
    if isinstance(value, str):
        normalized = value.replace("\\", "/")
        return "data/generated/" in normalized or "/model-output/" in normalized or normalized.startswith("model-output/")
    return False


def validate(root: Path = ROOT, document: Mapping[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    try:
        sc1 = read_json(root, SC1_PATH)
        links_document = read_json(root, PERSON_STORY_LINKS_PATH)
        index = read_json(root, JINSHU_INDEX_PATH)
        surface = document if document is not None else read_json(root, OUTPUT_PATH)
        search_document = read_json(root, SHISHUO_SEARCH_OUTPUT_PATH)
        corpus_index = read_json(root, SHISHUO_CORPUS_INDEX_PATH)
        association_audit = read_json(root, ASSOCIATION_AUDIT_PATH)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        return [f"cannot load DS2.1A inputs: {error}"]

    if surface.get("schema") != 1:
        errors.append("surface schema must be 1")
    if surface.get("projection") != "ds2_1a_person_research_surface":
        errors.append("unexpected projection name")
    if contains_forbidden_path(surface):
        errors.append("surface contains a generated/model-output path")
    if association_audit.get("schema") != 1:
        errors.append("association audit schema must be 1")
    if association_audit.get("projection") != "ds2_1a_research_association_union_audit":
        errors.append("unexpected association audit projection name")
    if contains_forbidden_path(association_audit):
        errors.append("association audit contains a generated/model-output path")

    source_documents = surface.get("source_documents")
    if not isinstance(source_documents, list):
        errors.append("source_documents must be a list")
    else:
        for item in source_documents:
            if not isinstance(item, Mapping):
                errors.append("source_documents contains a non-object")
                continue
            relative = str(item.get("path", ""))
            if not path_is_safe(relative) or not relative or not (root / relative).is_file():
                errors.append(f"source document is missing or unsafe: {relative}")
                continue
            if item.get("sha256") != sha256_file(root, Path(relative)):
                errors.append(f"source document SHA mismatch: {relative}")

    exposed_people_rows = registered_persons(root)
    published_story_ids = {str(row["id"]) for row in exposed_stories(sc1)}
    expected_people = {str(row["id"]): row for row in exposed_people_rows}
    corpus_entries = [row for row in corpus_index.get("entries", []) if isinstance(row, Mapping)]
    corpus_entries.sort(
        key=lambda row: (
            int(row.get("global_ordinal")) if isinstance(row.get("global_ordinal"), int) else 10**9,
            str(row.get("id", "")),
        )
    )
    corpus_by_id = {str(row.get("id")): row for row in corpus_entries}
    chapter_by_id = {
        str(row.get("id")): row
        for row in corpus_index.get("chapters", [])
        if isinstance(row, Mapping) and row.get("id")
    }
    people = surface.get("people")
    if not isinstance(people, Mapping):
        return errors + ["people must be an object"]
    if set(people) != set(expected_people):
        errors.append("surface Person IDs do not match the exposed SC1 Person IDs")

    all_links = [row for row in links_document.get("links", []) if isinstance(row, Mapping)]
    if len(all_links) != int(links_document.get("link_count", len(all_links))):
        errors.append("PersonStory source link_count does not match links length")
    if int(links_document.get("reviewed_link_count", -1)) != sum(row.get("review_status") == "reviewed" for row in all_links):
        errors.append("PersonStory reviewed_link_count changed or is inconsistent")
    if int(links_document.get("candidate_link_count", -1)) != sum(row.get("review_status") == "candidate" for row in all_links):
        errors.append("PersonStory candidate_link_count changed or is inconsistent")
    link_by_id = {
        str(row.get("id")): row
        for row in all_links
    }
    if len(link_by_id) != len(all_links):
        errors.append("PersonStory links contain duplicate IDs")
    if any(str(row.get("person_id")) not in expected_people for row in all_links):
        errors.append("PersonStory links reference a Person outside the registered Person projection")
    unresolved_link_stories = sorted(
        {str(row.get("entry_id")) for row in all_links if str(row.get("entry_id")) not in corpus_by_id}
    )
    if unresolved_link_stories:
        errors.append(f"PersonStory links reference missing canonical Stories: {unresolved_link_stories}")
    unit_by_id = {
        str(row.get("unit_id")): row
        for row in index.get("units", [])
        if isinstance(row, Mapping)
    }
    confirmed = confirmed_biography_units(root)

    search_records = search_document.get("records") if isinstance(search_document, Mapping) else None
    if search_document.get("schema") != 1:
        errors.append("Shishuo search corpus schema must be 1")
    if search_document.get("projection") != "ds2_1a_shishuo_search_corpus":
        errors.append("unexpected Shishuo search corpus projection name")
    if contains_forbidden_path(search_document):
        errors.append("Shishuo search corpus contains a generated/model-output path")
    if not isinstance(search_records, list):
        errors.append("Shishuo search corpus records must be a list")
        search_records = []
    if len(search_records) != len(corpus_entries):
        errors.append(f"Shishuo search corpus count is {len(search_records)}, expected {len(corpus_entries)}")
    search_by_id = {
        str(row.get("story_id")): row
        for row in search_records
        if isinstance(row, Mapping)
    }
    if len(search_by_id) != len(search_records):
        errors.append("Shishuo search corpus contains duplicate Story IDs")
    if set(search_by_id) != set(corpus_by_id):
        errors.append("Shishuo search corpus Story IDs do not match the canonical corpus index")
    search_source_documents = search_document.get("source_documents")
    if not isinstance(search_source_documents, list):
        errors.append("Shishuo search corpus source_documents must be a list")
    else:
        for item in search_source_documents:
            if not isinstance(item, Mapping):
                errors.append("Shishuo search corpus source_documents contains a non-object")
                continue
            relative = str(item.get("path", ""))
            if not path_is_safe(relative) or not relative or not (root / relative).is_file():
                errors.append(f"Shishuo search source document is missing or unsafe: {relative}")
            elif item.get("sha256") != sha256_file(root, Path(relative)):
                errors.append(f"Shishuo search source document SHA mismatch: {relative}")

    expected_search = build_shishuo_search_corpus(root, sc1)
    expected_search_by_id = {str(row["story_id"]): row for row in expected_search}
    for story_id, expected_record in expected_search_by_id.items():
        actual = search_by_id.get(story_id)
        if not isinstance(actual, Mapping):
            continue
        for key in (
            "story_id",
            "chapter_id",
            "chapter_heading",
            "entry_number",
            "main_text",
            "liu_annotations",
            "search_text",
            "search_text_normalized",
            "source_path",
            "source_sha256",
            "source_provenance",
            "publication_scope",
        ):
            if actual.get(key) != expected_record.get(key):
                errors.append(f"Shishuo search record differs from canonical source projection: {story_id}.{key}")
        if actual.get("source_path", "").startswith("data/generated/"):
            errors.append(f"Shishuo search record uses generated source: {story_id}")
        if actual.get("publication_scope") not in {"published", "research_only"}:
            errors.append(f"Shishuo search record has invalid publication_scope: {story_id}")

    expected_union, expected_audit = build_association_union(
        root,
        sc1,
        links_document,
        expected_search,
        list(expected_people.values()),
    )
    if association_audit != expected_audit:
        errors.append("association audit does not match the deterministic union")
    expected_union_summary = {
        "audit_path": ASSOCIATION_AUDIT_PATH.as_posix(),
        "union_pairs": expected_audit["counts"]["union_pairs"],
        "person_story_pairs": expected_audit["counts"]["person_story_pairs"],
        "participant_pairs": expected_audit["counts"]["participant_pairs"],
        "both_pairs": expected_audit["counts"]["both_pairs"],
        "person_story_only_pairs": expected_audit["counts"]["person_story_only_pairs"],
        "participant_only_pairs": expected_audit["counts"]["participant_only_pairs"],
        "source_layer_disagreement_count": expected_audit["counts"]["source_layer_disagreement_count"],
        "role_disagreement_count": expected_audit["counts"]["role_disagreement_count"],
    }
    if surface.get("association_union") != expected_union_summary:
        errors.append("surface association_union summary is inconsistent")
    audit_counts = association_audit.get("counts")
    if audit_counts != expected_audit["counts"]:
        errors.append("association audit counts are inconsistent")
    for key in (
        "both_pairs",
        "person_story_only_pairs",
        "participant_only_pairs",
        "source_layer_disagreements",
        "role_disagreements",
        "unresolved_provenance_anomalies",
    ):
        if not isinstance(association_audit.get(key), list):
            errors.append(f"association audit {key} must be a list")
    audit_source_documents = association_audit.get("source_documents")
    if not isinstance(audit_source_documents, list):
        errors.append("association audit source_documents must be a list")
    else:
        for item in audit_source_documents:
            if not isinstance(item, Mapping):
                errors.append("association audit source_documents contains a non-object")
                continue
            relative = str(item.get("path", ""))
            if not path_is_safe(relative) or not relative or not (root / relative).is_file():
                errors.append(f"association audit source document is missing or unsafe: {relative}")
            elif item.get("sha256") != sha256_file(root, Path(relative)):
                errors.append(f"association audit source document SHA mismatch: {relative}")

    participant_ids = {
        str(row.get("participant_id"))
        for row in read_json(root, H0C_PARTICIPANT_FREEZE_PATH).get("records", [])
        if isinstance(row, Mapping) and row.get("participant_id")
    }
    person_story_ids_from_union: set[str] = set()

    for person_id, person in people.items():
        if not isinstance(person, Mapping):
            errors.append(f"{person_id} is not an object")
            continue
        expected = expected_people.get(str(person_id))
        if expected is None:
            continue
        if person.get("person_id") != person_id:
            errors.append(f"{person_id}.person_id mismatch")
        if person.get("canonical_name") != expected.get("canonical_name"):
            errors.append(f"{person_id}.canonical_name mismatch")

        story_rows = person.get("shishuo_stories")
        if not isinstance(story_rows, list):
            errors.append(f"{person_id}.shishuo_stories must be a list")
            story_rows = []
        expected_rows = expected_union.get(str(person_id), [])
        if story_rows != expected_rows:
            errors.append(f"{person_id}.shishuo_stories differs from deterministic association union")
        for story in story_rows:
            if not isinstance(story, Mapping):
                errors.append(f"{person_id} has a non-object Story preview")
                continue
            story_id = str(story.get("story_id"))
            search_record = search_by_id.get(story_id)
            if search_record is None:
                errors.append(f"{person_id} references non-canonical Story {story_id}")
                continue
            if story.get("source_presence") not in {"main_text", "liu_annotation_only", "both"}:
                errors.append(f"{person_id}/{story_id} has invalid source_presence")
            research_presence = story.get("research_presence")
            if not isinstance(research_presence, Mapping) or not isinstance(research_presence.get("main_text"), bool) or not isinstance(research_presence.get("liu_annotation"), bool):
                errors.append(f"{person_id}/{story_id} has invalid research_presence")
            if story.get("relation_to_person") != story.get("source_presence"):
                errors.append(f"{person_id}/{story_id} relation_to_person compatibility field differs")
            if story.get("chapter_id") != search_record.get("chapter_id"):
                errors.append(f"{person_id}/{story_id} chapter_id mismatch")
            if story.get("chapter_heading") != search_record.get("chapter_heading"):
                errors.append(f"{person_id}/{story_id} chapter_heading mismatch")
            if story.get("story_ordinal") != search_record.get("entry_number"):
                errors.append(f"{person_id}/{story_id} story_ordinal mismatch")
            if story.get("current_story") is not False:
                errors.append(f"{person_id}/{story_id} static surface current_story must be false")
            expected_scope = "published" if story_id in published_story_ids else "research_only"
            if story.get("research_scope") != expected_scope:
                errors.append(f"{person_id}/{story_id} research_scope mismatch")
            excerpt = story.get("short_excerpt")
            if not isinstance(excerpt, str) or not excerpt:
                errors.append(f"{person_id}/{story_id} has no Story excerpt")
            elif excerpt not in compact_text(str(search_record.get("main_text", ""))):
                errors.append(f"{person_id}/{story_id} excerpt is not from Story source text")
            association_sources = story.get("association_sources")
            if not isinstance(association_sources, list) or not association_sources:
                errors.append(f"{person_id}/{story_id} has no association provenance")
                continue
            for source in association_sources:
                if not isinstance(source, Mapping):
                    errors.append(f"{person_id}/{story_id} has a non-object association source")
                    continue
                source_type = source.get("type")
                if source_type == "person_story":
                    record_id = str(source.get("record_id", ""))
                    person_story_ids_from_union.add(record_id)
                    if not set(source.get("source_layers", [])) <= {"main_text", "liu_annotation"}:
                        errors.append(f"{person_id}/{story_id} has invalid PersonStory source layers")
                    link = link_by_id.get(record_id)
                    if link is None or link.get("person_id") != person_id or link.get("entry_id") != story_id:
                        errors.append(f"{person_id}/{story_id} has invalid PersonStory provenance")
                    elif link.get("review_status") == "candidate" and source.get("review_status") != "candidate":
                        errors.append(f"{person_id}/{story_id} candidate PersonStory status was promoted")
                elif source_type == "reviewed_participant":
                    if source.get("review_status") != "reviewed" or str(source.get("record_id")) not in participant_ids:
                        errors.append(f"{person_id}/{story_id} has invalid H0C participant provenance")
                    if not set(source.get("source_sections", [])) <= {"main_text", "liu_annotation"}:
                        errors.append(f"{person_id}/{story_id} has invalid participant source sections")
                else:
                    errors.append(f"{person_id}/{story_id} has unknown association source type")
            if story.get("association_strength") not in {"reviewed_scene", "reviewed_textual", "candidate_textual"}:
                errors.append(f"{person_id}/{story_id} has invalid association_strength")
            if story.get("research_priority_class") not in {
                "reviewed_hard_scene",
                "reviewed_main_text",
                "reviewed_contextual",
                "reviewed_liu_only",
                "candidate_textual",
            }:
                errors.append(f"{person_id}/{story_id} has invalid research_priority_class")
            if not isinstance(story.get("scene_roles"), list):
                errors.append(f"{person_id}/{story_id} scene_roles must be a list")
            elif any(role not in {"present", "speaker", "actor", "referenced", "off_frame", "annotation_only", "uncertain"} for role in story["scene_roles"]):
                errors.append(f"{person_id}/{story_id} has an invalid scene role")

        expected_person_story_ids = {
            str(link.get("id"))
            for link in all_links
            if str(link.get("person_id")) == str(person_id)
        }
        actual_person_story_ids = {
            str(source.get("record_id"))
            for story in story_rows
            if isinstance(story, Mapping)
            for source in story.get("association_sources", [])
            if isinstance(source, Mapping) and source.get("type") == "person_story"
        }
        if actual_person_story_ids != expected_person_story_ids:
            errors.append(f"{person_id} does not expose every existing PersonStory association")
        expected_counts = {
            "story_count_total": len({str(row.get("story_id")) for row in expected_rows}),
            "story_count_published": len({str(row.get("story_id")) for row in expected_rows if row.get("research_scope") == "published"}),
            "story_count_research_only": len({str(row.get("story_id")) for row in expected_rows if row.get("research_scope") == "research_only"}),
            "main_text_story_count": len({str(row.get("story_id")) for row in expected_rows if row.get("research_presence", {}).get("main_text")}),
            "liu_annotation_only_story_count": len({str(row.get("story_id")) for row in expected_rows if row.get("research_presence", {}).get("liu_annotation") and not row.get("research_presence", {}).get("main_text")}),
            "both_layer_story_count": len({str(row.get("story_id")) for row in expected_rows if row.get("research_presence", {}).get("main_text") and row.get("research_presence", {}).get("liu_annotation")}),
            "reviewed_link_count": sum(source.get("review_status") == "reviewed" for row in expected_rows for source in row.get("association_sources", []) if source.get("type") == "person_story"),
            "candidate_link_count": sum(source.get("review_status") == "candidate" for row in expected_rows for source in row.get("association_sources", []) if source.get("type") == "person_story"),
        }
        for key, value in expected_counts.items():
            if person.get(key) != value:
                errors.append(f"{person_id}.{key} is {person.get(key)!r}, expected {value}")

        biographies = person.get("historical_biography_entries")
        if not isinstance(biographies, list):
            errors.append(f"{person_id}.historical_biography_entries must be a list")
            biographies = []
        seen_units: set[str] = set()
        for entry in biographies:
            if not isinstance(entry, Mapping):
                errors.append(f"{person_id} has a non-object biography entry")
                continue
            unit_id = str(entry.get("unit_id"))
            unit = unit_by_id.get(unit_id)
            if unit is None or unit.get("category") != "liezhuan":
                errors.append(f"{person_id} biography entry has invalid Jinshu unit {unit_id}")
                continue
            if unit_id in seen_units:
                errors.append(f"{person_id} repeats Jinshu unit {unit_id}")
            seen_units.add(unit_id)
            source_path = str(entry.get("source_path", ""))
            if not path_is_safe(source_path) or not source_path.startswith("content/processed/jinshu/units/"):
                errors.append(f"{person_id}/{unit_id} has unsafe biography source_path")
            elif not (root / source_path).is_file():
                errors.append(f"{person_id}/{unit_id} biography source_path is missing")
            else:
                try:
                    source = load_jinshu_source(root, unit)
                except (OSError, ValueError) as error:
                    errors.append(f"{person_id}/{unit_id} source cannot be read: {error}")
                else:
                    excerpt = entry.get("short_excerpt")
                    if not isinstance(excerpt, str) or not excerpt or excerpt not in compact_text(source):
                        errors.append(f"{person_id}/{unit_id} excerpt is not from Jinshu source text")
                    if entry.get("source_sha256") != unit.get("unit_text_sha256"):
                        errors.append(f"{person_id}/{unit_id} source SHA mismatch")
                    if sha256_text(source) != unit.get("unit_text_sha256"):
                        errors.append(f"{person_id}/{unit_id} registered unit text hash mismatch")
            if entry.get("work") != "晉書":
                errors.append(f"{person_id}/{unit_id} is not labeled 晉書")
            if entry.get("match_status") not in {"confirmed", "candidate"}:
                errors.append(f"{person_id}/{unit_id} has invalid match_status")
            if entry.get("match_status") == "confirmed" and unit_id not in confirmed.get(str(person_id), set()):
                errors.append(f"{person_id}/{unit_id} is confirmed without deterministic biography support")
            if not set(entry.get("match_basis", [])) <= {"canonical_name", "alias"} or not entry.get("match_basis"):
                errors.append(f"{person_id}/{unit_id} has invalid match_basis")

        context = person.get("reviewed_context")
        if not isinstance(context, Mapping):
            errors.append(f"{person_id}.reviewed_context must be an object")
            continue
        for key in ("aliases", "relations", "kinship", "offices", "events"):
            rows = context.get(key)
            if not isinstance(rows, list):
                errors.append(f"{person_id}.reviewed_context.{key} must be a list")
                continue
            for row in rows:
                if not isinstance(row, Mapping):
                    errors.append(f"{person_id}.reviewed_context.{key} contains a non-object")
                    continue
                if key == "aliases":
                    if row.get("status") != "resolved" or row.get("resolution_mode") != "exact":
                        errors.append(f"{person_id} exposes a non-resolved alias")
                elif row.get("review_status") != "reviewed":
                    errors.append(f"{person_id}.reviewed_context.{key} contains an unreviewed row")

    if person_story_ids_from_union != set(link_by_id):
        errors.append("association union does not expose exactly every PersonStory link once")

    return errors


def main() -> int:
    errors = validate(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("DS2.1A validation passed")
    return 0


def story_main_text(story: Mapping[str, Any]) -> str:
    reading = story.get("reading")
    if isinstance(reading, Mapping) and isinstance(reading.get("main_text"), Mapping):
        value = reading["main_text"].get("original")
        if isinstance(value, str) and value:
            return value
    return str(story.get("text", ""))


if __name__ == "__main__":
    raise SystemExit(main())
