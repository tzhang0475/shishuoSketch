#!/usr/bin/env python3
"""Validate the deterministic Shishuo Person ↔ Story pilot artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver


ROOT = Path(__file__).resolve().parents[1]
LINKS_PATH = Path("data/derived/person-story-links.json")
INDEX_PATH = Path("data/derived/person-story-index.json")
LINKS_SCHEMA_PATH = Path("schema/person-story-links.schema.json")
LINK_SCHEMA_PATH = Path("schema/person-story-link.schema.json")
INDEX_SCHEMA_PATH = Path("schema/person-story-index.schema.json")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def schema_errors(schema_path: Path, value: Any, label: str) -> list[str]:
    schema = read_json(schema_path)
    Draft202012Validator.check_schema(schema)
    resolver = None
    if schema_path.name == "person-story-links.schema.json":
        child_path = schema_path.with_name("person-story-link.schema.json")
        child_schema = read_json(child_path)
        resolver = RefResolver.from_schema(
            schema,
            store={child_schema["$id"]: child_schema},
        )
    validator = Draft202012Validator(schema, resolver=resolver)
    return [f"{label}: {error.message}" for error in validator.iter_errors(value)]


def _entry_metadata(root: Path, entry: dict[str, Any]) -> dict[str, Any]:
    path = root / entry["path"]
    text = path.read_text(encoding="utf-8")
    first = text.find("---\n")
    end = text.find("\n---\n", first + 4)
    fields: dict[str, str] = {}
    if first == 0 and end >= 0:
        for line in text[4:end].splitlines():
            if ":" in line and not line.startswith(" "):
                key, value = line.split(":", 1)
                fields[key.strip()] = value.strip().strip('"')
    return fields


def _readiness_prerequisites(
    root: Path,
    entry: dict[str, Any],
    punctuation_by_entry: dict[str, dict[str, Any]],
    frontend_stories: dict[str, dict[str, Any]],
    reviewed_link_count: int,
) -> tuple[bool, bool, bool, bool]:
    path = root / entry["path"]
    canonical = path.is_file() and sha256_file(path) == entry.get("entry_sha256")
    punctuation = punctuation_by_entry.get(entry["id"])
    reviewed_punctuation = bool(
        punctuation
        and punctuation.get("status") == "reviewed"
        and punctuation.get("base_canonical_entry_path") == entry.get("path")
        and punctuation.get("base_canonical_entry_sha256") == entry.get("entry_sha256")
    )
    story = frontend_stories.get(entry["id"], {})
    reading = story.get("reading") if isinstance(story, dict) else None
    simplified_reading = bool(
        isinstance(reading, dict)
        and reading.get("status") == "reviewed"
        and isinstance(reading.get("main_text"), dict)
        and isinstance(reading["main_text"].get("original"), str)
        and isinstance(reading["main_text"].get("simplified"), str)
        and isinstance(reading.get("annotations"), list)
    )
    return canonical, reviewed_punctuation, simplified_reading, reviewed_link_count > 0


def validate(
    root: Path = ROOT,
    *,
    links_document: dict[str, Any] | None = None,
    index: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    try:
        if links_document is None:
            links_document = read_json(root / LINKS_PATH)
        if index is None:
            index = read_json(root / INDEX_PATH)
    except (OSError, ValueError) as exc:
        return [str(exc)]

    try:
        errors.extend(schema_errors(root / LINKS_SCHEMA_PATH, links_document, "PersonStoryLinks"))
        errors.extend(schema_errors(root / INDEX_SCHEMA_PATH, index, "PersonStoryIndex"))
        link_schema = root / LINK_SCHEMA_PATH
        for number, link in enumerate(links_document.get("links", [])):
            errors.extend(schema_errors(link_schema, link, f"PersonStoryLink {number}"))
    except Exception as exc:
        # jsonschema may raise a schema/ref error; report it as a validation
        # error instead of masking the artifact problem.
        errors.append(f"PersonStory schema validation failed: {exc}")

    people_document = read_json(root / "data/people.json")
    people = people_document.get("people", [])
    people_by_id = {person.get("person_id"): person for person in people}
    entries = read_json(root / "data/shishuo-corpus-index.json").get("entries", [])
    entries_by_id = {entry.get("id"): entry for entry in entries}
    mentions = read_json(root / "data/mentions/shishuo.json").get("mentions", [])
    mentions_by_id = {mention.get("mention_id"): mention for mention in mentions}
    evidence = read_json(root / "data/evidence/wp1-evidence.json").get("records", [])
    evidence_by_id = {record.get("id"): record for record in evidence}
    punctuation = read_json(root / "data/annotation/wp1-punctuation.json").get("records", [])
    punctuation_by_entry = {record.get("entry_id"): record for record in punctuation}
    frontend_stories = {
        story.get("id"): story
        for story in read_json(root / "data/derived/wp1-site.json").get("stories", [])
    }

    links = links_document.get("links", [])
    if not isinstance(links, list):
        errors.append("PersonStoryLinks.links must be an array")
        links = []
    link_by_id: dict[str, dict[str, Any]] = {}
    semantic_keys: set[tuple[str, str]] = set()
    for link in links:
        if not isinstance(link, dict):
            continue
        link_id = link.get("id")
        person_id = link.get("person_id")
        entry_id = link.get("entry_id")
        if isinstance(link_id, str):
            if link_id in link_by_id:
                errors.append(f"duplicate PersonStoryLink ID: {link_id}")
            link_by_id[link_id] = link
        if person_id not in people_by_id:
            errors.append(f"PersonStoryLink {link_id} references nonexistent Person: {person_id!r}")
        if entry_id not in entries_by_id:
            errors.append(f"PersonStoryLink {link_id} references nonexistent entry: {entry_id!r}")
        key = (str(person_id), str(entry_id))
        if key in semantic_keys:
            errors.append(f"duplicate PersonStoryLink semantic link: {key}")
        semantic_keys.add(key)
        if link.get("link_basis") == "mention":
            if not link.get("supporting_mention_ids") and not link.get("candidate_mention_ids"):
                errors.append(f"PersonStoryLink {link_id} mention basis has no supporting or candidate mentions")
            if link.get("review_status") == "reviewed" and not link.get("supporting_mention_ids"):
                errors.append(f"PersonStoryLink {link_id} reviewed mention basis has no supporting mentions")
        if link.get("link_basis") == "explicit_evidence" and not link.get("evidence_ids"):
            errors.append(f"PersonStoryLink {link_id} explicit evidence basis has no evidence")
        for evidence_id in link.get("evidence_ids", []):
            if evidence_id not in evidence_by_id:
                errors.append(f"PersonStoryLink {link_id} references nonexistent Evidence: {evidence_id!r}")
            else:
                locator = evidence_by_id[evidence_id].get("locator", {})
                if locator.get("artifact_type") != "shishuo_entry" or locator.get("entry_id") != entry_id:
                    errors.append(f"PersonStoryLink {link_id} evidence {evidence_id} does not locate its entry")
        supporting_mention_ids = list(link.get("supporting_mention_ids", []))
        candidate_mention_ids = list(link.get("candidate_mention_ids", []))
        all_mention_ids = supporting_mention_ids + candidate_mention_ids
        for mention_id in all_mention_ids:
            mention = mentions_by_id.get(mention_id)
            if mention is None:
                errors.append(f"PersonStoryLink {link_id} references nonexistent Mention: {mention_id!r}")
                continue
            if mention.get("person_id") != person_id:
                errors.append(f"PersonStoryLink {link_id} Mention {mention_id} resolves to a different Person")
            if mention.get("entry_id") != entry_id and mention.get("source_id") != entry_id:
                errors.append(f"PersonStoryLink {link_id} Mention {mention_id} belongs to a different entry")
            if mention_id in supporting_mention_ids and mention.get("confidence") != "high":
                errors.append(f"PersonStoryLink {link_id} supporting Mention {mention_id} is not high confidence")
            if mention_id in candidate_mention_ids and mention.get("confidence") == "high":
                errors.append(f"PersonStoryLink {link_id} candidate Mention {mention_id} is high confidence")
            if mention.get("source") != "shishuo":
                errors.append(f"PersonStoryLink {link_id} Mention {mention_id} is not a Shishuo Mention")
            if not isinstance(mention.get("evidence"), dict) or not mention.get("evidence", {}).get("provenance"):
                errors.append(f"PersonStoryLink {link_id} Mention {mention_id} has no provenance")
        presence_keys: set[str] = set()
        presence_mention_ids: set[str] = set()
        for presence in link.get("presences", []):
            layer = presence.get("source_layer")
            kind = presence.get("presence_kind")
            if layer in presence_keys:
                errors.append(f"PersonStoryLink {link_id} duplicates source layer: {layer}")
            presence_keys.add(str(layer))
            if kind == "participant":
                if layer != "main_text":
                    errors.append(f"PersonStoryLink {link_id} annotation-only presence cannot be participant")
                if not presence.get("supporting_mention_ids"):
                    errors.append(f"PersonStoryLink {link_id} participant presence has no supporting Mention")
            presence_supporting_ids = presence.get("supporting_mention_ids", [])
            presence_candidate_ids = presence.get("candidate_mention_ids", [])
            if set(presence_supporting_ids) & set(presence_candidate_ids):
                errors.append(f"PersonStoryLink {link_id} presence has overlapping supporting and candidate Mentions")
            presence_mention_ids.update(presence_supporting_ids)
            presence_mention_ids.update(presence_candidate_ids)
            for mention_id in presence_supporting_ids + presence_candidate_ids:
                if mention_id not in link.get("supporting_mention_ids", []):
                    if mention_id not in link.get("candidate_mention_ids", []):
                        errors.append(f"PersonStoryLink {link_id} presence Mention is not in link mentions")
                mention = mentions_by_id.get(mention_id)
                if mention and mention.get("section") != layer:
                    errors.append(f"PersonStoryLink {link_id} presence layer disagrees with Mention {mention_id}")
        if presence_mention_ids != set(all_mention_ids):
            errors.append(f"PersonStoryLink {link_id} presence Mentions do not exactly project link Mentions")
        if set(supporting_mention_ids) & set(candidate_mention_ids):
            errors.append(f"PersonStoryLink {link_id} has overlapping supporting and candidate Mentions")

    if links_document.get("link_count") != len(links):
        errors.append("PersonStoryLinks.link_count does not match links")
    if links_document.get("reviewed_link_count") != sum(link.get("review_status") == "reviewed" for link in links):
        errors.append("PersonStoryLinks.reviewed_link_count does not match links")
    if links_document.get("candidate_link_count") != sum(link.get("review_status") == "candidate" for link in links):
        errors.append("PersonStoryLinks.candidate_link_count does not match links")
    if links_document.get("candidate_mention_count") != sum(len(link.get("candidate_mention_ids", [])) for link in links):
        errors.append("PersonStoryLinks.candidate_mention_count does not match links")

    reviewed_link_count = sum(link.get("review_status") == "reviewed" for link in links)
    candidate_link_count = sum(link.get("review_status") == "candidate" for link in links)
    candidate_mention_count = sum(len(link.get("candidate_mention_ids", [])) for link in links)
    if index.get("reviewed_link_count") != reviewed_link_count:
        errors.append("PersonStoryIndex.reviewed_link_count does not match links")
    if index.get("candidate_link_count") != candidate_link_count:
        errors.append("PersonStoryIndex.candidate_link_count does not match links")
    if index.get("candidate_mention_count") != candidate_mention_count:
        errors.append("PersonStoryIndex.candidate_mention_count does not match links")

    registry_person_ids = set(people_by_id)
    if set(links_document.get("person_scope", [])) != registry_person_ids:
        errors.append("PersonStoryLinks person_scope does not match the unified Person registry")
    if set(index.get("person_scope", [])) != registry_person_ids:
        errors.append("PersonStoryIndex person_scope does not match the unified Person registry")

    reviewed_links = [link for link in links if link.get("review_status") == "reviewed"]
    expected_by_person: dict[str, list[dict[str, Any]]] = {person_id: [] for person_id in people_by_id}
    for link in reviewed_links:
        person_id = link.get("person_id")
        if person_id in people_by_id:
            expected_by_person.setdefault(person_id, []).append(link)
    expected_by_person_ids = set(people_by_id)
    actual_person_ids = {person.get("person_id") for person in index.get("persons", [])}
    if actual_person_ids != expected_by_person_ids:
        errors.append("PersonStoryIndex persons do not match the unified Person registry")
    for person_record in index.get("persons", []):
        person_id = person_record.get("person_id")
        expected_links = expected_by_person.get(person_id, [])
        expected_link_ids = {link["id"] for link in expected_links}
        actual_refs = person_record.get("story_refs", [])
        actual_link_ids = {
            link_id
            for ref in actual_refs
            for link_id in ref.get("link_ids", [])
        }
        if actual_link_ids != expected_link_ids:
            errors.append(f"PersonStoryIndex {person_id} does not exactly project reviewed links")
        candidate_ids = {
            link["entry_id"]
            for link in links
            if link.get("person_id") == person_id and link.get("review_status") == "candidate"
        }
        if set(person_record.get("candidate_story_ids", [])) != candidate_ids:
            errors.append(f"PersonStoryIndex {person_id} candidate_story_ids do not match candidate links")
        for ref in actual_refs:
            ref_entry_id = ref.get("entry_id")
            if ref_entry_id not in entries_by_id:
                errors.append(f"PersonStoryIndex {person_id} references nonexistent entry: {ref.get('entry_id')!r}")
            for link_id in ref.get("link_ids", []):
                if link_id not in link_by_id:
                    errors.append(f"PersonStoryIndex {person_id} references nonexistent link: {link_id!r}")
            referenced_links = [link_by_id[link_id] for link_id in ref.get("link_ids", []) if link_id in link_by_id]
            if ref_entry_id in entries_by_id and referenced_links:
                for link in referenced_links:
                    if link.get("person_id") != person_id:
                        errors.append(
                            f"PersonStoryIndex {person_id} {ref_entry_id} includes a link for another Person"
                        )
                    if link.get("entry_id") != ref_entry_id:
                        errors.append(
                            f"PersonStoryIndex {person_id} {ref_entry_id} includes a link for another entry"
                        )
                expected_layers = sorted({
                    presence["source_layer"]
                    for link in referenced_links
                    for presence in link.get("presences", [])
                })
                expected_kinds = sorted({
                    presence["presence_kind"]
                    for link in referenced_links
                    for presence in link.get("presences", [])
                })
                if ref.get("source_layers") != expected_layers:
                    errors.append(f"PersonStoryIndex {person_id} {ref_entry_id} source_layers do not project links")
                if ref.get("presence_kinds") != expected_kinds:
                    errors.append(f"PersonStoryIndex {person_id} {ref_entry_id} presence_kinds do not project links")

    readiness = index.get("story_readiness", [])
    readiness_by_entry = {item.get("entry_id"): item for item in readiness}
    linked_entry_ids = {link.get("entry_id") for link in links}
    if set(readiness_by_entry) != linked_entry_ids:
        errors.append("PersonStoryIndex story_readiness does not cover exactly linked entries")
    for entry_id, item in readiness_by_entry.items():
        entry = entries_by_id.get(entry_id)
        if entry is None:
            continue
        reviewed_count = sum(
            link.get("review_status") == "reviewed" and link.get("entry_id") == entry_id
            for link in links
        )
        canonical, reviewed_punctuation, simplified_reading, resolved = _readiness_prerequisites(
            root,
            entry,
            punctuation_by_entry,
            frontend_stories,
            reviewed_count,
        )
        expected_ready = all((canonical, reviewed_punctuation, simplified_reading, resolved))
        for field, expected in (
            ("canonical_entry", canonical),
            ("reviewed_punctuation", reviewed_punctuation),
            ("simplified_reading", simplified_reading),
            ("resolved_person_mentions", resolved),
            ("reader_ready", expected_ready),
        ):
            if item.get(field) != expected:
                errors.append(f"PersonStoryIndex readiness {entry_id}.{field} is inconsistent")
        if item.get("reviewed_link_count") != reviewed_count:
            errors.append(f"PersonStoryIndex readiness {entry_id}.reviewed_link_count is inconsistent")

    for person_record in index.get("persons", []):
        person_id = person_record.get("person_id")
        for ref in person_record.get("story_refs", []):
            entry_id = ref.get("entry_id")
            if entry_id in readiness_by_entry and ref.get("reader_ready") != readiness_by_entry[entry_id].get("reader_ready"):
                errors.append(f"PersonStoryIndex {person_id} {entry_id} reader_ready does not project readiness")

    selected = index.get("candidate_selection", {})
    if selected.get("count") != len(selected.get("entry_ids", [])):
        errors.append("PersonStoryIndex candidate_selection.count is inconsistent")
    if not set(selected.get("entry_ids", [])).issubset(linked_entry_ids):
        errors.append("PersonStoryIndex candidate selection references an unlinked entry")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("PersonStory validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PersonStory validation passed: links, index, mentions, entries, and reader readiness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
