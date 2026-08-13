#!/usr/bin/env python3
"""Validate the SC0 Story Chain Gold Set and its derived index."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from opencc import OpenCC

try:
    from .build_six_person_pilot import parse_shishuo_sections
    from .reading_layers import strip_display_punctuation
except ImportError:  # direct execution
    from build_six_person_pilot import parse_shishuo_sections
    from reading_layers import strip_display_punctuation


ROOT = Path(__file__).resolve().parents[1]
GOLD_PATH = Path("data/story-chain-gold-set.json")
CHAIN_INDEX_PATH = Path("data/derived/story-chain-gold-index.json")
CONNECTIVITY_PATH = Path("data/derived/story-chain-connectivity.json")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_main_text(path: Path) -> str:
    for section, body, _metadata in parse_shishuo_sections(path.read_text(encoding="utf-8")):
        if section == "main_text":
            return body.strip("\n")
    raise ValueError(f"canonical entry has no main_text: {path}")


def schema_errors(root: Path, schema_name: str, value: Any, label: str) -> list[str]:
    schema = read_json(root / "schema" / schema_name)
    Draft202012Validator.check_schema(schema)
    return [f"{label}: {error.message}" for error in Draft202012Validator(schema).iter_errors(value)]


def validate(root: Path = ROOT) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    try:
        gold = read_json(root / GOLD_PATH)
        chain = read_json(root / CHAIN_INDEX_PATH)
        connectivity = read_json(root / CONNECTIVITY_PATH)
        links_document = read_json(root / "data/derived/person-story-links.json")
        people_document = read_json(root / "data/people.json")
        corpus = read_json(root / "data/shishuo-corpus-index.json")
        punctuation_document = read_json(root / "data/annotation/wp1-punctuation.json")
        reading_document = read_json(root / "data/derived/shishuo-reading-layer.json")
    except (OSError, ValueError) as exc:
        return [f"SC0 cannot read required artifact: {exc}"]

    errors.extend(schema_errors(root, "story-chain-gold-set.schema.json", gold, "SC0 Gold Set"))
    errors.extend(schema_errors(root, "story-chain-gold-index.schema.json", chain, "SC0 Gold Index"))
    errors.extend(schema_errors(root, "story-chain-connectivity.schema.json", connectivity, "SC0 connectivity"))

    people = {person.get("person_id"): person for person in people_document.get("people", [])}
    entries = {entry.get("id"): entry for entry in corpus.get("entries", [])}
    links = [link for link in links_document.get("links", []) if link.get("review_status") == "reviewed"]
    links_by_entry: dict[str, list[dict[str, Any]]] = {}
    for link in links:
        links_by_entry.setdefault(link.get("entry_id"), []).append(link)
    punctuation = {record.get("entry_id"): record for record in punctuation_document.get("records", [])}
    reading = {record.get("entry_id"): record for record in reading_document.get("records", [])}

    records = gold.get("records", [])
    entry_ids = [record.get("entry_id") for record in records]
    if len(entry_ids) != len(set(entry_ids)):
        errors.append("SC0 Gold Set contains duplicate Story IDs")
    if not 15 <= len(records) <= 20:
        errors.append(f"SC0 Gold Set must contain 15-20 Stories, found {len(records)}")
    if entry_ids != sorted(entry_ids, key=lambda item: entries.get(item, {}).get("global_ordinal", 10**9)):
        errors.append("SC0 Gold Set is not in canonical corpus order")
    if sum(record.get("selection_status") == "gold_anchor" for record in records) != 1:
        errors.append("SC0 Gold Set must contain exactly one gold_anchor")

    selected_by_id = {record.get("entry_id"): record for record in records}
    expected_person_story: dict[str, list[str]] = {}
    for record in records:
        entry_id = record.get("entry_id")
        entry = entries.get(entry_id)
        if entry is None:
            errors.append(f"SC0 selected Story does not resolve: {entry_id!r}")
            continue
        actual_links = links_by_entry.get(entry_id, [])
        actual_person_ids = {link.get("person_id") for link in actual_links}
        linked_person_ids = set(record.get("linked_person_ids", []))
        if not linked_person_ids.issubset(people):
            errors.append(f"SC0 {entry_id} references a nonexistent Person")
        if linked_person_ids != actual_person_ids:
            errors.append(
                f"SC0 {entry_id} linked_person_ids do not exactly project reviewed PersonStoryLinks: "
                f"{sorted(linked_person_ids)} != {sorted(actual_person_ids)}"
            )
        for person_id in linked_person_ids:
            expected_person_story.setdefault(person_id, []).append(entry_id)

        punct = punctuation.get(entry_id)
        read = reading.get(entry_id)
        if punct is None or read is None:
            errors.append(f"SC0 {entry_id} has no reading-layer record")
            continue
        reading_status = record.get("reading_layer_status", {})
        for key in ("status", "punctuation_basis", "exact_transfer"):
            source_key = "punctuation_status" if key == "status" else key
            if reading_status.get(source_key) != (
                punct.get(key) if key != "status" else punct.get("status")
            ):
                errors.append(f"SC0 {entry_id} reading status disagrees with punctuation record: {source_key}")
        if reading_status.get("story_reader_ready") != read.get("story_reader_ready"):
            errors.append(f"SC0 {entry_id} reader-ready state disagrees with CRL1 layer")
        main = punct.get("sections", {}).get("main_text", {})
        canonical_path = root / entry["path"]
        if not canonical_path.is_file() or sha256_file(canonical_path) != entry.get("entry_sha256"):
            errors.append(f"SC0 {entry_id} canonical artifact/hash is invalid")
        elif isinstance(main.get("punctuated_text"), str):
            canonical = canonical_main_text(canonical_path)
            if strip_display_punctuation(main["punctuated_text"]) != strip_display_punctuation(canonical):
                errors.append(f"SC0 {entry_id} punctuation candidate does not round-trip")
            simplified = read.get("main_text", {}).get("simplified")
            if simplified != OpenCC("t2s").convert(main["punctuated_text"]):
                errors.append(f"SC0 {entry_id} simplified reading is not deterministic")

        # Main-text and annotation-only classifications are projected from
        # existing link presence metadata; no annotation-only person is
        # silently relabeled as a main-text person.
        expected_main: set[str] = set()
        expected_annotation_only: set[str] = set()
        for link in actual_links:
            layers = {presence.get("source_layer") for presence in link.get("presences", [])}
            if "main_text" in layers:
                expected_main.add(link["person_id"])
            elif "liu_annotation" in layers:
                expected_annotation_only.add(link["person_id"])
        chain_story = next((item for item in chain.get("stories", []) if item.get("entry_id") == entry_id), None)
        if chain_story is not None:
            if set(chain_story.get("main_text_person_ids", [])) != expected_main:
                errors.append(f"SC0 {entry_id} main-text Person classification is not projected")
            if set(chain_story.get("liu_annotation_only_person_ids", [])) != expected_annotation_only:
                errors.append(f"SC0 {entry_id} annotation-only Person classification is not projected")

    chain_stories = chain.get("stories", [])
    chain_ids = [item.get("entry_id") for item in chain_stories]
    if chain.get("story_count") != len(records) or chain_ids != entry_ids:
        errors.append("SC0 Gold Index stories do not exactly project the Gold Set")
    chain_by_person = {item.get("person_id"): item.get("entry_ids", []) for item in chain.get("person_story_refs", [])}
    if set(chain_by_person) != set(expected_person_story):
        errors.append("SC0 Gold Index person_story_refs do not project selected Persons")
    for person_id, expected_ids in expected_person_story.items():
        ordered = sorted(expected_ids, key=lambda item: entries[item]["global_ordinal"])
        if chain_by_person.get(person_id) != ordered:
            errors.append(f"SC0 Gold Index Story projection is wrong for {person_id}")

    if connectivity.get("candidate_count") != len(connectivity.get("candidate_records", [])):
        errors.append("SC0 connectivity candidate_count is incorrect")
    if connectivity.get("gold_set_entry_ids") != entry_ids:
        errors.append("SC0 connectivity Gold Set projection is incorrect")
    if connectivity.get("gold_set_count") != len(records):
        errors.append("SC0 connectivity gold_set_count is incorrect")
    if connectivity.get("main_component_count") < 1:
        errors.append("SC0 connectivity has no bipartite component")
    relations = read_json(root / "data/annotation/wp1-relations.json").get("records", [])
    represented_person_ids = {
        person_id
        for record in records
        for person_id in record.get("linked_person_ids", [])
    }
    expected_direct_relation_ids = [
        relation["id"]
        for relation in relations
        if relation.get("review_status") == "reviewed"
        and relation.get("relation_basis") == "direct"
        and relation.get("subject_id") in represented_person_ids
        and relation.get("object_id") in represented_person_ids
    ]
    expected_derived_relation_ids = [
        relation["id"]
        for relation in relations
        if relation.get("review_status") == "reviewed"
        and relation.get("relation_basis") == "derived"
        and relation.get("subject_id") in represented_person_ids
        and relation.get("object_id") in represented_person_ids
    ]
    if connectivity.get("covered_direct_relation_ids") != expected_direct_relation_ids:
        errors.append("SC0 direct relation coverage does not project existing reviewed Relations")
    if connectivity.get("covered_direct_relation_count") != len(expected_direct_relation_ids):
        errors.append("SC0 direct relation coverage count is incorrect")
    if connectivity.get("covered_derived_relation_ids") != expected_derived_relation_ids:
        errors.append("SC0 derived relation coverage does not project existing reviewed Relations")
    selected_candidates = [
        next((item for item in connectivity.get("candidate_records", []) if item.get("entry_id") == entry_id), None)
        for entry_id in entry_ids
    ]
    selected_candidates = [item for item in selected_candidates if item is not None]
    if connectivity.get("main_text_story_count") != sum(bool(item.get("main_text_person_ids")) for item in selected_candidates):
        errors.append("SC0 connectivity main_text_story_count is incorrect")
    if connectivity.get("annotation_only_story_count") != sum(
        bool(item.get("liu_annotation_only_person_ids")) and not bool(item.get("main_text_person_ids"))
        for item in selected_candidates
    ):
        errors.append("SC0 connectivity annotation_only_story_count is incorrect")

    # Explicitly ensure this task did not create a relation-local story link.
    for record in records:
        if any(key.startswith("relation") for key in record):
            errors.append(f"SC0 {record.get('entry_id')} contains relation-derived fields")
    anchor = punctuation.get("06-yaliang-019")
    if not anchor or anchor.get("status") != "reviewed" or anchor.get("punctuation_basis") != "human_reviewed":
        errors.append("SC0 changed the reviewed 06-yaliang-019 punctuation baseline")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("SC0 validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("SC0 validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
