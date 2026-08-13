#!/usr/bin/env python3
"""Validate the SC1 static Story Chain frontend projection."""

from __future__ import annotations

import hashlib
import json
import argparse
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from opencc import OpenCC

try:
    from .build_six_person_pilot import parse_shishuo_sections
    from .reading_layers import strip_display_punctuation
    from .validate_wp1 import validate_source_provenance
except ImportError:  # direct execution
    from build_six_person_pilot import parse_shishuo_sections
    from reading_layers import strip_display_punctuation
    from validate_wp1 import validate_source_provenance


ROOT = Path(__file__).resolve().parents[1]
SC1_PATH = ROOT / "data/derived/sc1-site.json"
VITE_PATH = ROOT / "site/src/generated/sc1-site.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_main(path: Path) -> str:
    for section, body, _metadata in parse_shishuo_sections(path.read_text(encoding="utf-8")):
        if section == "main_text":
            return body.rstrip("\n")
    raise ValueError(f"canonical entry has no main text: {path}")


def validate(root: Path = ROOT, mode: str = "full") -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    try:
        bundle = read_json(root / SC1_PATH.relative_to(ROOT))
        vite = read_json(root / VITE_PATH.relative_to(ROOT))
        gold = read_json(root / "data/story-chain-gold-set.json")
        chain = read_json(root / "data/derived/story-chain-gold-index.json")
        corpus = read_json(root / "data/shishuo-corpus-index.json")
        punctuation = {
            item["entry_id"]: item
            for item in read_json(root / "data/annotation/wp1-punctuation.json")["records"]
        }
        base = read_json(root / "data/derived/wp1-site.json")
    except (OSError, ValueError, KeyError) as exc:
        return [f"SC1 cannot read required artifact: {exc}"]

    try:
        schema = read_json(root / "schema/sc1-site.schema.json")
        Draft202012Validator.check_schema(schema)
        errors.extend(f"SC1 schema: {error.message}" for error in Draft202012Validator(schema).iter_errors(bundle))
    except (OSError, ValueError) as exc:
        errors.append(f"SC1 schema cannot be validated: {exc}")

    if (root / SC1_PATH.relative_to(ROOT)).read_bytes() != (root / VITE_PATH.relative_to(ROOT)).read_bytes():
        errors.append("SC1 derived bundle and Vite input bytes differ")
    if bundle != vite:
        errors.append("SC1 derived bundle and Vite input JSON differ")

    selected = gold.get("records", [])
    selected_ids = [item.get("entry_id") for item in selected]
    stories = bundle.get("stories", [])
    story_by_id = {item.get("id"): item for item in stories if isinstance(item, dict)}
    if selected_ids != [item.get("id") for item in stories]:
        errors.append("SC1 stories are not exactly the ordered SC0 Gold Set")
    if len(stories) != 16 or len(story_by_id) != len(stories):
        errors.append("SC1 must contain exactly 16 unique Stories")

    corpus_by_id = {item.get("id"): item for item in corpus.get("entries", [])}
    people_by_id = {item.get("id"): item for item in bundle.get("people", [])}
    mention_by_id = {item.get("id"): item for item in bundle.get("mentions", [])}
    relation_ids = {item.get("id") for item in bundle.get("relations", [])}
    evidence_by_id = {item.get("id"): item for item in bundle.get("evidence", [])}
    converter = OpenCC("t2s")

    for evidence_id, evidence in evidence_by_id.items():
        locator = evidence.get("locator", {})
        artifact_path = locator.get("artifact_path")
        if not isinstance(artifact_path, str):
            errors.append(f"SC1 Evidence {evidence_id} has no artifact path")
            continue
        artifact = root / artifact_path
        if not artifact.is_file():
            errors.append(f"SC1 Evidence {evidence_id} artifact is missing: {artifact_path}")
        elif locator.get("artifact_sha256") != sha256_file(artifact):
            errors.append(f"SC1 Evidence {evidence_id} artifact hash mismatch")
        provenance = locator.get("source_provenance")
        if isinstance(provenance, dict):
            errors.extend(
                validate_source_provenance(
                    root,
                    provenance,
                    label=f"SC1 Evidence {evidence_id} source_provenance",
                    mode=mode,
                )
            )

    for selection in selected:
        entry_id = selection.get("entry_id")
        story = story_by_id.get(entry_id)
        entry = corpus_by_id.get(entry_id)
        punct = punctuation.get(entry_id)
        if story is None or entry is None or punct is None:
            errors.append(f"SC1 missing selected Story inputs: {entry_id}")
            continue
        path = root / entry["path"]
        if not path.is_file():
            errors.append(f"SC1 canonical entry is missing: {entry_id}")
            continue
        if sha256_file(path) != entry.get("entry_sha256"):
            errors.append(f"SC1 canonical entry hash mismatch: {entry_id}")
        canonical = canonical_main(path)
        if story.get("text") != canonical:
            errors.append(f"SC1 Story text differs from canonical entry: {entry_id}")
        if story.get("person_ids") != selection.get("linked_person_ids"):
            errors.append(f"SC1 Person projection differs for {entry_id}")
        if any(person_id not in people_by_id for person_id in story.get("person_ids", [])):
            errors.append(f"SC1 Story has an unresolved Person: {entry_id}")

        reading = story.get("reading", {})
        main = punct.get("sections", {}).get("main_text", {})
        if reading.get("status") != punct.get("status"):
            errors.append(f"SC1 reading status differs from punctuation record: {entry_id}")
        if reading.get("main_text", {}).get("original") != main.get("punctuated_text"):
            errors.append(f"SC1 punctuated reading differs from punctuation record: {entry_id}")
        if strip_display_punctuation(str(main.get("punctuated_text", ""))) != strip_display_punctuation(canonical):
            errors.append(f"SC1 punctuation does not round-trip: {entry_id}")
        if reading.get("main_text", {}).get("simplified") != converter.convert(str(main.get("punctuated_text", ""))):
            errors.append(f"SC1 simplified reading is not deterministic: {entry_id}")
        expected_state = "production_ready" if entry_id == "06-yaliang-019" else "preview_ready"
        if story.get("publication_state") != expected_state:
            errors.append(f"SC1 publication state is wrong for {entry_id}")
        if entry_id == "06-yaliang-019":
            if punct.get("review_status") != "reviewed" or punct.get("punctuation_basis") != "human_reviewed":
                errors.append("SC1 changed the reviewed punctuation baseline")
        else:
            if punct.get("review_status") != "unreviewed" or punct.get("punctuation_basis") != "reference_candidate":
                errors.append(f"SC1 changed candidate punctuation semantics: {entry_id}")

        for mention_id in story.get("mention_ids", []):
            mention = mention_by_id.get(mention_id)
            if mention is None or mention.get("story_id") != entry_id:
                errors.append(f"SC1 Story has an invalid Mention reference: {entry_id}/{mention_id}")
        for evidence_id in story.get("evidence_ids", []):
            if evidence_id not in evidence_by_id:
                errors.append(f"SC1 Story has an invalid Evidence reference: {entry_id}/{evidence_id}")
        for relation_id in story.get("relation_ids", []):
            if relation_id not in relation_ids:
                errors.append(f"SC1 Story has an invalid Relation reference: {entry_id}/{relation_id}")

    # Shared WP1 identity/relation records are copied, not re-authored.
    for key in ("people", "relations", "sources", "eras"):
        if bundle.get(key) != base.get(key):
            errors.append(f"SC1 changed shared WP1 {key} records")
    base_evidence = {item["id"]: item for item in base.get("evidence", [])}
    for evidence_id, item in base_evidence.items():
        if evidence_by_id.get(evidence_id) != item:
            errors.append(f"SC1 changed existing Evidence record: {evidence_id}")
    base_mentions = {item["id"]: item for item in base.get("mentions", [])}
    for mention_id, item in base_mentions.items():
        if mention_by_id.get(mention_id) != item:
            errors.append(f"SC1 changed existing Mention record: {mention_id}")

    frontend_chain = bundle.get("story_chain", {})
    if frontend_chain.get("story_ids") != selected_ids:
        errors.append("SC1 story_chain.story_ids does not project the Gold Set")
    chain_story_by_id = {item.get("entry_id"): item for item in chain.get("stories", [])}
    frontend_story_refs = {
        item.get("entry_id"): item
        for item in frontend_chain.get("story_person_refs", [])
    }
    expected_person_ids = {
        item.get("person_id")
        for item in frontend_chain.get("person_story_refs", [])
    }
    expected_person_ids.discard(None)
    for entry_id in selected_ids:
        expected = chain_story_by_id.get(entry_id)
        actual = frontend_story_refs.get(entry_id)
        if expected is None or actual is None:
            errors.append(f"SC1 missing Story ↔ Person projection: {entry_id}")
            continue
        for field in ("linked_person_ids", "main_text_person_ids", "liu_annotation_only_person_ids"):
            if actual.get(field) != expected.get(field):
                errors.append(f"SC1 {field} projection differs: {entry_id}")
    for reference in frontend_chain.get("person_story_refs", []):
        if reference.get("person_id") not in people_by_id:
            errors.append(f"SC1 PersonStory reference has unknown Person: {reference.get('person_id')}")
        for story_id in reference.get("story_ids", []):
            if story_id not in story_by_id:
                errors.append(f"SC1 PersonStory reference has unknown Story: {story_id}")
    if expected_person_ids != {item.get("person_id") for item in chain.get("person_story_refs", [])}:
        errors.append("SC1 PersonStory reference set is incomplete")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("full", "portable"), default="full")
    args = parser.parse_args()
    errors = validate(mode=args.mode)
    if errors:
        print("SC1 frontend validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("SC1 frontend validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
