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
    from .reading_layers import display_span_for_anchor, strip_display_punctuation
    from .validate_person_sketch import validate_bundle as validate_person_sketch_bundle
    from .validate_wp1 import validate_source_provenance
except ImportError:  # direct execution
    from build_six_person_pilot import parse_shishuo_sections
    from reading_layers import display_span_for_anchor, strip_display_punctuation
    from validate_person_sketch import validate_bundle as validate_person_sketch_bundle
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


def collect_sc1_source_provenance(bundle: dict[str, Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Collect each distinct upstream source identity used by SC1 Evidence.

    SC1 publishes a small bundle, but its source references are shared across
    many Evidence records.  Validating this set explicitly makes portable
    lock coverage a corpus-expansion invariant rather than an accidental
    consequence of the current number of records.
    """
    references: dict[tuple[str, str, str], dict[str, Any]] = {}
    for evidence in bundle.get("evidence", []):
        if not isinstance(evidence, dict):
            continue
        provenance = evidence.get("locator", {}).get("source_provenance")
        if not isinstance(provenance, dict):
            continue
        witness_id = provenance.get("witness_id")
        source_path = provenance.get("source_path")
        source_sha256 = provenance.get("source_sha256")
        if not all(isinstance(value, str) and value for value in (witness_id, source_path, source_sha256)):
            continue
        key = (witness_id, source_path, source_sha256)
        reference = references.setdefault(
            key,
            {"provenance": dict(provenance), "evidence_ids": [], "source_ids": []},
        )
        reference["evidence_ids"].append(evidence.get("id"))
        reference["source_ids"].append(evidence.get("source_id"))
    return references


def validate_inline_mention_projection(
    story: dict[str, Any],
    mentions: dict[str, dict[str, Any]],
    people: set[str],
) -> list[str]:
    """Validate deterministic inline Mention placement for one Story."""

    errors: list[str] = []
    story_id = str(story.get("id"))
    reading = story.get("reading", {})
    if not isinstance(reading, dict):
        return [f"SC1 {story_id}: reading is not an object"]
    canonical_by_layer: dict[tuple[str, str | None], str] = {
        ("main_text", None): str(story.get("text", "")),
    }
    for annotation in story.get("annotations", []):
        if isinstance(annotation, dict) and isinstance(annotation.get("id"), str):
            canonical_by_layer[("liu_annotation", annotation["id"])] = str(annotation.get("text", ""))

    placed: dict[str, tuple[str, str | None]] = {}
    placed_markers: set[str] = set()
    suppressed: dict[str, dict[str, Any]] = {}
    projection = reading.get("mention_projection", {})
    if isinstance(projection, dict) and isinstance(projection.get("suppressed"), list):
        for item in projection["suppressed"]:
            if not isinstance(item, dict):
                errors.append(f"SC1 {story_id}: malformed suppressed Mention record")
                continue
            if item.get("kind") == "annotation_marker":
                annotation_id = item.get("annotation_id")
                if not isinstance(annotation_id, str) or item.get("section") != "main_text":
                    errors.append(f"SC1 {story_id}: malformed suppressed annotation marker")
                continue
            if not isinstance(item.get("mention_id"), str):
                errors.append(f"SC1 {story_id}: malformed suppressed Mention record")
                continue
            mention_id = item["mention_id"]
            if mention_id in suppressed:
                errors.append(f"SC1 {story_id}: duplicate suppressed Mention {mention_id}")
            suppressed[mention_id] = item
            mention = mentions.get(mention_id)
            if mention is None or mention.get("story_id") != story_id:
                errors.append(f"SC1 {story_id}: suppressed Mention does not resolve: {mention_id}")
            elif mention.get("section") != item.get("section"):
                errors.append(f"SC1 {story_id}: suppressed Mention layer mismatch: {mention_id}")
    else:
        errors.append(f"SC1 {story_id}: missing mention_projection.suppressed")

    def inspect_segments(
        segments: Any,
        expected_original: str,
        expected_simplified: str,
        layer: str,
        annotation_id: str | None = None,
    ) -> None:
        if not isinstance(segments, list):
            errors.append(f"SC1 {story_id}: {layer} segments are not an array")
            return
        original = ""
        simplified = ""
        offset = 0
        for segment in segments:
            if not isinstance(segment, dict):
                errors.append(f"SC1 {story_id}: malformed {layer} segment")
                continue
            display = segment.get("display", {})
            if not isinstance(display, dict) or not isinstance(display.get("original"), str) or not isinstance(display.get("simplified"), str):
                errors.append(f"SC1 {story_id}: incomplete {layer} segment display")
                continue
            display_original = display["original"]
            display_simplified = display["simplified"]
            original += display_original
            simplified += display_simplified
            if segment.get("type") == "annotation_marker":
                annotation_marker_id = segment.get("annotation_id")
                if layer != "main_text" or not isinstance(annotation_marker_id, str):
                    errors.append(f"SC1 {story_id}: annotation marker is not in main text")
                    continue
                if display_original or display_simplified:
                    errors.append(f"SC1 {story_id}: annotation marker changes reconstructed text")
                label = segment.get("label")
                if not isinstance(label, dict) or not isinstance(label.get("original"), str) or not isinstance(label.get("simplified"), str):
                    errors.append(f"SC1 {story_id}: annotation marker label is incomplete")
                if annotation_marker_id in placed_markers:
                    errors.append(f"SC1 {story_id}: duplicate annotation marker: {annotation_marker_id}")
                placed_markers.add(annotation_marker_id)
                offset += len(display_original)
                continue
            if segment.get("type") != "person_mention":
                offset += len(display_original)
                continue
            mention_id = segment.get("mention_id")
            person_id = segment.get("person_id")
            if not isinstance(mention_id, str) or not isinstance(person_id, str):
                errors.append(f"SC1 {story_id}: person segment lacks IDs")
                offset += len(display_original)
                continue
            mention = mentions.get(mention_id)
            if mention is None:
                errors.append(f"SC1 {story_id}: inline Mention does not resolve: {mention_id}")
            else:
                if mention.get("story_id") != story_id or mention.get("section") != layer:
                    errors.append(f"SC1 {story_id}: inline Mention layer mismatch: {mention_id}")
                if mention.get("person_id") != person_id or person_id not in people:
                    errors.append(f"SC1 {story_id}: inline Mention Person mismatch: {mention_id}")
                if layer == "main_text" and "annotation_id" in segment:
                    errors.append(f"SC1 {story_id}: main-text Mention has annotation_id: {mention_id}")
                if layer == "liu_annotation" and segment.get("annotation_id") != annotation_id:
                    errors.append(f"SC1 {story_id}: annotation block mismatch: {mention_id}")
                canonical = canonical_by_layer.get((layer, annotation_id))
                anchor = mention.get("anchor", {})
                if canonical is None or not isinstance(anchor, dict) or not isinstance(anchor.get("offset"), int) or not isinstance(anchor.get("text"), str):
                    errors.append(f"SC1 {story_id}: missing canonical anchor for {mention_id}")
                else:
                    try:
                        expected_start, expected_end = display_span_for_anchor(
                            canonical,
                            expected_original,
                            anchor["offset"],
                            anchor["text"],
                        )
                        if offset != expected_start or offset + len(display_original) != expected_end:
                            errors.append(f"SC1 {story_id}: inline Mention display span differs from anchor: {mention_id}")
                    except ValueError as exc:
                        errors.append(f"SC1 {story_id}: unsafe inline Mention anchor {mention_id}: {exc}")
            if mention_id in placed:
                errors.append(f"SC1 {story_id}: duplicate inline Mention: {mention_id}")
            placed[mention_id] = (layer, annotation_id)
            offset += len(display_original)
        if original != expected_original or simplified != expected_simplified:
            errors.append(f"SC1 {story_id}: {layer} segments do not reconstruct reading text")

    main = reading.get("main_text", {})
    if isinstance(main, dict):
        inspect_segments(main.get("segments"), str(main.get("original", "")), str(main.get("simplified", "")), "main_text")
    for annotation in reading.get("annotations", []):
        if not isinstance(annotation, dict):
            continue
        annotation_id = annotation.get("id")
        if not isinstance(annotation_id, str):
            continue
        inspect_segments(
            annotation.get("segments"),
            str(annotation.get("original", "")),
            str(annotation.get("simplified", "")),
            "liu_annotation",
            annotation_id,
        )

    reading_annotations = reading.get("annotations", [])
    source_annotations = story.get("annotations", [])
    annotation_id_set = {
        item.get("id") for item in reading_annotations
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if not isinstance(reading_annotations, list) or not isinstance(source_annotations, list) or len(reading_annotations) != len(source_annotations):
        errors.append(f"SC1 {story_id}: canonical/reading annotation count differs")
    elif [item.get("id") for item in reading_annotations if isinstance(item, dict)] != [item.get("id") for item in source_annotations if isinstance(item, dict)]:
        errors.append(f"SC1 {story_id}: annotation order or IDs differ")
    story_evidence_ids = set(story.get("evidence_ids", []))
    for annotation in reading_annotations if isinstance(reading_annotations, list) else []:
        if not isinstance(annotation, dict):
            continue
        insertion = annotation.get("insertion")
        if not isinstance(insertion, dict) or insertion.get("status") not in {"safe", "unavailable"}:
            errors.append(f"SC1 {story_id}: annotation insertion metadata is invalid")
        if isinstance(insertion, dict) and insertion.get("status") == "safe" and annotation.get("id") not in placed_markers:
            errors.append(f"SC1 {story_id}: safe annotation insertion has no marker: {annotation.get('id')}")
        if isinstance(insertion, dict) and insertion.get("status") == "unavailable" and annotation.get("id") in placed_markers:
            errors.append(f"SC1 {story_id}: unavailable annotation insertion has a marker: {annotation.get('id')}")
        for evidence_id in annotation.get("evidence_ids", []):
            if not isinstance(evidence_id, str):
                errors.append(f"SC1 {story_id}: annotation Evidence ID is malformed: {evidence_id}")
            if evidence_id not in story_evidence_ids:
                errors.append(f"SC1 {story_id}: annotation Evidence is not exposed at Story level: {evidence_id}")
    for marker_id in placed_markers:
        if marker_id not in annotation_id_set:
            errors.append(f"SC1 {story_id}: annotation marker references unknown annotation: {marker_id}")

    for mention_id in story.get("mention_ids", []):
        mention = mentions.get(str(mention_id))
        if not mention or not isinstance(mention.get("person_id"), str) or mention.get("confidence") == "unresolved":
            continue
        if mention_id not in placed and mention_id not in suppressed:
            errors.append(f"SC1 {story_id}: resolved Mention has no inline/suppressed projection: {mention_id}")
    if placed.keys() & suppressed.keys():
        errors.append(f"SC1 {story_id}: Mention appears both inline and suppressed")
    return errors


def validate_sc1_source_provenance_coverage(
    root: Path,
    bundle: dict[str, Any],
    *,
    mode: str,
) -> list[str]:
    """Require every unique SC1 upstream source reference to pass provenance validation."""
    errors: list[str] = []
    source_by_id = {
        item.get("id"): item
        for item in bundle.get("sources", [])
        if isinstance(item, dict)
    }
    for (witness_id, source_path, source_sha256), reference in sorted(
        collect_sc1_source_provenance(bundle).items()
    ):
        provenance = reference["provenance"]
        evidence_ids = ", ".join(str(item) for item in reference["evidence_ids"])
        source_ids: list[Any] = []
        for source_id in reference["source_ids"]:
            if source_id not in source_ids:
                source_ids.append(source_id)
        for source_id in sorted(source_ids, key=lambda item: str(item)):
            source = source_by_id.get(source_id)
            if isinstance(source, dict) and provenance.get("witness_id") != source.get("witness_id"):
                errors.append(
                    "SC1 source provenance witness does not match source record: "
                    f"{witness_id!r} != {source.get('witness_id')!r} "
                    f"(source: {source_id!r}; Evidence: {evidence_ids})"
                )
        errors.extend(
            validate_source_provenance(
                root,
                provenance,
                label=(
                    "SC1 source_provenance coverage "
                    f"{witness_id}:{source_path}:{source_sha256[:12]} "
                    f"(Evidence: {evidence_ids})"
                ),
                mode=mode,
            )
        )
    return errors


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
        production_people = read_json(root / "data/people.json").get("people", [])
        raw_shishuo_mentions = read_json(root / "data/mentions/shishuo.json").get("mentions", [])
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
    people_id_set = {str(item.get("id")) for item in bundle.get("people", []) if isinstance(item, dict) and isinstance(item.get("id"), str)}

    errors.extend(validate_sc1_source_provenance_coverage(root, bundle, mode=mode))
    errors.extend(validate_person_sketch_bundle(root))
    chain_story_by_id = {item.get("entry_id"): item for item in chain.get("stories", [])}

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
        resolved_person_ids = list(dict.fromkeys(
            str(mention.get("person_id"))
            for mention in raw_shishuo_mentions
            if mention.get("entry_id") == entry_id
            and isinstance(mention.get("person_id"), str)
        ))
        expected_person_ids = list(dict.fromkeys([
            *(chain_story_by_id.get(entry_id, {}).get("linked_person_ids", selection.get("linked_person_ids", []))),
            *resolved_person_ids,
        ]))
        if story.get("person_ids") != expected_person_ids:
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
        for annotation in story.get("reading", {}).get("annotations", []):
            if not isinstance(annotation, dict):
                continue
            for evidence_id in annotation.get("evidence_ids", []):
                if evidence_id not in evidence_by_id:
                    errors.append(f"SC1 annotation has an invalid Evidence reference: {entry_id}/{evidence_id}")
        for relation_id in story.get("relation_ids", []):
            if relation_id not in relation_ids:
                errors.append(f"SC1 Story has an invalid Relation reference: {entry_id}/{relation_id}")
        errors.extend(validate_inline_mention_projection(story, mention_by_id, people_id_set))

    # The seven WP1 Person records remain byte-identical, while the unified
    # production registry may add the frozen P3B.1 wave.  Other shared WP1
    # factual layers are copied without expansion.
    base_people_by_id = {item.get("id"): item for item in base.get("people", [])}
    bundle_people_by_id = {item.get("id"): item for item in bundle.get("people", [])}
    production_people_by_id = {item.get("person_id"): item for item in production_people}
    if set(bundle_people_by_id) != set(production_people_by_id):
        errors.append("SC1 Person projection does not match the unified production registry")
    for person_id, base_person in base_people_by_id.items():
        if bundle_people_by_id.get(person_id) != base_person:
            errors.append(f"SC1 changed existing WP1 Person record: {person_id}")
    for key in ("relations", "sources", "eras"):
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
    frontend_story_refs = {
        item.get("entry_id"): item
        for item in frontend_chain.get("story_person_refs", [])
    }
    frontend_person_ids = {
        item.get("person_id")
        for item in frontend_chain.get("person_story_refs", [])
    }
    expected_person_ids = {
        item.get("person_id")
        for item in chain.get("person_story_refs", [])
    }
    expected_person_ids.update(
        str(mention.get("person_id"))
        for mention in raw_shishuo_mentions
        if mention.get("entry_id") in selected_ids and isinstance(mention.get("person_id"), str)
    )
    expected_person_ids.discard(None)
    for entry_id in selected_ids:
        expected = chain_story_by_id.get(entry_id)
        actual = frontend_story_refs.get(entry_id)
        if expected is None or actual is None:
            errors.append(f"SC1 missing Story ↔ Person projection: {entry_id}")
            continue
        story_mentions = [
            mention for mention in raw_shishuo_mentions
            if mention.get("entry_id") == entry_id
            and isinstance(mention.get("person_id"), str)
        ]
        resolved_main = sorted({
            str(mention["person_id"])
            for mention in story_mentions
            if mention.get("section") == "main_text"
        })
        resolved_annotation = sorted({
            str(mention["person_id"])
            for mention in story_mentions
            if mention.get("section") == "liu_annotation"
        } - set(resolved_main))
        expected_projection = {
            "linked_person_ids": list(dict.fromkeys([
                *expected.get("linked_person_ids", []),
                *resolved_main,
                *resolved_annotation,
            ])),
            "main_text_person_ids": list(dict.fromkeys([
                *expected.get("main_text_person_ids", []),
                *resolved_main,
            ])),
            "liu_annotation_only_person_ids": list(dict.fromkeys([
                *expected.get("liu_annotation_only_person_ids", []),
                *resolved_annotation,
            ])),
        }
        for field in ("linked_person_ids", "main_text_person_ids", "liu_annotation_only_person_ids"):
            if actual.get(field) != expected_projection[field]:
                errors.append(f"SC1 {field} projection differs: {entry_id}")
    for reference in frontend_chain.get("person_story_refs", []):
        if reference.get("person_id") not in people_by_id:
            errors.append(f"SC1 PersonStory reference has unknown Person: {reference.get('person_id')}")
        for story_id in reference.get("story_ids", []):
            if story_id not in story_by_id:
                errors.append(f"SC1 PersonStory reference has unknown Story: {story_id}")
    if frontend_person_ids != expected_person_ids:
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
