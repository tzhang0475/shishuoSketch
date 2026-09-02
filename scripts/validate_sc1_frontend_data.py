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
    from .reading_layers import display_span_for_anchor, normalize_reader_whitespace, strip_display_punctuation
    from .validate_person_sketch import validate_bundle as validate_person_sketch_bundle
    from .validate_wp1 import validate_source_provenance
    from .sc1_paths import CURRENT_SC1_DERIVED_PATH, CURRENT_SC1_VITE_PATH
    from .story_scene_contexts import DERIVED_PATH as SCENE_DERIVED_PATH, SOURCE_PATH as SCENE_SOURCE_PATH, project as project_scene_contexts, validate_source as validate_scene_source, validate_source_path as validate_scene_source_path
    from .person_resolution import load_effective_mentions
except ImportError:  # direct execution
    from build_six_person_pilot import parse_shishuo_sections
    from reading_layers import display_span_for_anchor, normalize_reader_whitespace, strip_display_punctuation
    from validate_person_sketch import validate_bundle as validate_person_sketch_bundle
    from validate_wp1 import validate_source_provenance
    from sc1_paths import CURRENT_SC1_DERIVED_PATH, CURRENT_SC1_VITE_PATH
    from story_scene_contexts import DERIVED_PATH as SCENE_DERIVED_PATH, SOURCE_PATH as SCENE_SOURCE_PATH, project as project_scene_contexts, validate_source as validate_scene_source, validate_source_path as validate_scene_source_path
    from person_resolution import load_effective_mentions


ROOT = Path(__file__).resolve().parents[1]
# This validator checks the current rebuildable production projection.  The
# historical v1 snapshot has a separate integrity-only validator.
SC1_PATH = ROOT / CURRENT_SC1_DERIVED_PATH
VITE_PATH = ROOT / CURRENT_SC1_VITE_PATH


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
    ruler_mentions: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """Validate deterministic inline Mention placement for one Story."""

    errors: list[str] = []
    story_id = str(story.get("id"))
    validate_ruler_registry = ruler_mentions is not None
    ruler_mentions = ruler_mentions or {}
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

    def mention_anchor(mention: dict[str, Any]) -> tuple[int, str] | None:
        """Return the effective display span without changing the raw anchor."""

        span = mention.get("display_span")
        if isinstance(span, dict):
            offset = span.get("offset")
            text = span.get("text")
            end = span.get("end_offset_exclusive")
            if isinstance(offset, int) and isinstance(end, int) and isinstance(text, str) and end == offset + len(text):
                return offset, text
            return None
        anchor = mention.get("anchor", {})
        if isinstance(anchor, dict) and isinstance(anchor.get("offset"), int) and isinstance(anchor.get("text"), str):
            return anchor["offset"], anchor["text"]
        return None

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
            if segment.get("type") == "ruler_mention":
                mention_id = segment.get("mention_id")
                ruler_id = segment.get("ruler_id")
                era_card_id = segment.get("era_card_id")
                if not isinstance(mention_id, str) or not isinstance(ruler_id, str) or not isinstance(era_card_id, str):
                    errors.append(f"SC1 {story_id}: ruler segment lacks IDs")
                    offset += len(display_original)
                    continue
                ruler_mention = ruler_mentions.get(mention_id)
                if validate_ruler_registry and ruler_mention is None:
                    errors.append(f"SC1 {story_id}: ruler Mention does not resolve: {mention_id}")
                elif validate_ruler_registry and ruler_mention is not None:
                    if ruler_mention.get("story_id") != story_id or ruler_mention.get("section") != layer:
                        errors.append(f"SC1 {story_id}: ruler Mention layer mismatch: {mention_id}")
                    if ruler_mention.get("ruler_id") != ruler_id or ruler_mention.get("era_card_id") != era_card_id:
                        errors.append(f"SC1 {story_id}: ruler Mention target mismatch: {mention_id}")
                    if ruler_mention.get("resolution_status") != "resolved":
                        errors.append(f"SC1 {story_id}: non-resolved ruler Mention is projected as clickable: {mention_id}")
                    if layer == "main_text" and "annotation_id" in segment:
                        errors.append(f"SC1 {story_id}: main-text ruler Mention has annotation_id: {mention_id}")
                    if layer == "liu_annotation" and segment.get("annotation_id") != annotation_id:
                        errors.append(f"SC1 {story_id}: annotation ruler block mismatch: {mention_id}")
                    canonical = canonical_by_layer.get((layer, annotation_id))
                    anchor = mention_anchor(ruler_mention)
                    if canonical is None or anchor is None:
                        errors.append(f"SC1 {story_id}: missing canonical anchor for ruler Mention {mention_id}")
                    else:
                        try:
                            expected_start, expected_end = display_span_for_anchor(
                                canonical,
                                expected_original,
                                anchor[0],
                                anchor[1],
                            )
                            if offset != expected_start or offset + len(display_original) != expected_end:
                                errors.append(f"SC1 {story_id}: ruler Mention display span differs from anchor: {mention_id}")
                        except ValueError as exc:
                            errors.append(f"SC1 {story_id}: unsafe ruler Mention anchor {mention_id}: {exc}")
                if mention_id in placed:
                    errors.append(f"SC1 {story_id}: duplicate inline Mention: {mention_id}")
                placed[mention_id] = (layer, annotation_id)
                offset += len(display_original)
                continue
            if segment.get("type") == "identity_mention":
                mention_id = segment.get("mention_id")
                if not isinstance(mention_id, str):
                    errors.append(f"SC1 {story_id}: identity segment lacks Mention ID")
                    offset += len(display_original)
                    continue
                mention = mentions.get(mention_id)
                if mention is None:
                    errors.append(f"SC1 {story_id}: identity Mention does not resolve: {mention_id}")
                else:
                    if mention.get("story_id") != story_id or mention.get("section") != layer:
                        errors.append(f"SC1 {story_id}: identity Mention layer mismatch: {mention_id}")
                    if mention.get("resolution_status") != segment.get("resolution_status"):
                        errors.append(f"SC1 {story_id}: identity Mention status mismatch: {mention_id}")
                    target = mention.get("resolution_target")
                    if segment.get("target_kind") != "identity_candidate":
                        errors.append(f"SC1 {story_id}: identity segment target kind is invalid: {mention_id}")
                    if isinstance(target, dict) and target.get("target_kind") == "production_person":
                        errors.append(f"SC1 {story_id}: identity Mention points to production Person: {mention_id}")
                    if layer == "main_text" and "annotation_id" in segment:
                        errors.append(f"SC1 {story_id}: main-text identity Mention has annotation_id: {mention_id}")
                    if layer == "liu_annotation" and segment.get("annotation_id") != annotation_id:
                        errors.append(f"SC1 {story_id}: annotation identity block mismatch: {mention_id}")
                    if isinstance(target, dict) and target.get("canonical_name") != (segment.get("canonical_name") or {}).get("original"):
                        errors.append(f"SC1 {story_id}: identity Mention target name mismatch: {mention_id}")
                    canonical = canonical_by_layer.get((layer, annotation_id))
                    anchor = mention_anchor(mention)
                    if canonical is None or anchor is None:
                        errors.append(f"SC1 {story_id}: missing canonical anchor for identity Mention {mention_id}")
                    else:
                        try:
                            expected_start, expected_end = display_span_for_anchor(
                                canonical,
                                expected_original,
                                anchor[0],
                                anchor[1],
                            )
                            if offset != expected_start or offset + len(display_original) != expected_end:
                                errors.append(f"SC1 {story_id}: identity Mention display span differs from anchor: {mention_id}")
                        except ValueError as exc:
                            errors.append(f"SC1 {story_id}: unsafe identity Mention anchor {mention_id}: {exc}")
                if mention_id in placed:
                    errors.append(f"SC1 {story_id}: duplicate inline Mention: {mention_id}")
                placed[mention_id] = (layer, annotation_id)
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
                anchor = mention_anchor(mention)
                if canonical is None or anchor is None:
                    errors.append(f"SC1 {story_id}: missing canonical anchor for {mention_id}")
                else:
                    try:
                        expected_start, expected_end = display_span_for_anchor(
                            canonical,
                            expected_original,
                            anchor[0],
                            anchor[1],
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
        visible_resolution = bool(
            mention
            and (
                (
                    isinstance(mention.get("person_id"), str)
                    and mention.get("confidence") != "unresolved"
                )
                or mention.get("resolution_status") in {"resolved", "candidate_for_review"}
            )
        )
        if not visible_resolution:
            continue
        if mention_id not in placed and mention_id not in suppressed:
            errors.append(f"SC1 {story_id}: resolved Mention has no inline/suppressed projection: {mention_id}")
    if validate_ruler_registry:
        expected_ruler_ids = {
            mention_id
            for mention_id, ruler_mention in ruler_mentions.items()
            if isinstance(ruler_mention, dict) and ruler_mention.get("story_id") == story_id
        }
        if expected_ruler_ids - set(placed):
            errors.append(
                f"SC1 {story_id}: resolved ruler Mention has no inline projection: "
                f"{', '.join(sorted(expected_ruler_ids - set(placed)))}"
            )
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
        expansion = read_json(root / "data/annotation/story-expansion-wave-1.json") if (root / "data/annotation/story-expansion-wave-1.json").is_file() else None
        w3_expansion = read_json(root / "data/annotation/story-expansion-wave-3.json") if (root / "data/annotation/story-expansion-wave-3.json").is_file() else None
        w4_expansion = read_json(root / "data/annotation/story-expansion-wave-4.json") if (root / "data/annotation/story-expansion-wave-4.json").is_file() else None
        chain = read_json(root / "data/derived/story-chain-gold-index.json")
        corpus = read_json(root / "data/shishuo-corpus-index.json")
        punctuation = {
            item["entry_id"]: item
            for item in read_json(root / "data/annotation/wp1-punctuation.json")["records"]
        }
        base = read_json(root / "data/derived/wp1-site.json")
        production_people = read_json(root / "data/people.json").get("people", [])
        raw_shishuo_mentions = load_effective_mentions(root)
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

    gold_records = list(gold.get("records", []))
    gold_ids = [item.get("entry_id") for item in gold_records]
    if len(gold_ids) != 16 or len(set(gold_ids)) != 16:
        errors.append("SC0 Gold Set must remain exactly 16 unique Stories")
    selected = list(gold_records)
    expansion_ids: list[str] = []
    if expansion is not None:
        expansion_ids = [str(item.get("story_id")) for item in expansion.get("records", [])]
        if expansion.get("gold_story_ids") != gold_ids:
            errors.append("M2 Story expansion manifest does not preserve the exact SC0 Gold Set")
        if len(expansion_ids) != len(set(expansion_ids)):
            errors.append("M2 Story expansion manifest contains duplicate Story IDs")
        if set(expansion_ids) & set(gold_ids):
            errors.append("M2 Story expansion manifest duplicates an SC0 Story")
        selected.extend({"entry_id": story_id, "linked_person_ids": []} for story_id in expansion_ids)
    w3_expansion_ids: list[str] = []
    if w3_expansion is not None:
        w3_expansion_ids = [str(item.get("story_id")) for item in w3_expansion.get("records", [])]
        if w3_expansion.get("gold_story_ids") != gold_ids:
            errors.append("W3 Story expansion manifest does not preserve the exact SC0 Gold Set")
        if len(w3_expansion_ids) != len(set(w3_expansion_ids)):
            errors.append("W3 Story expansion manifest contains duplicate Story IDs")
        if set(w3_expansion_ids) & (set(gold_ids) | set(expansion_ids)):
            errors.append("W3 Story expansion manifest overlaps an existing publication set")
        selected.extend({"entry_id": story_id, "linked_person_ids": []} for story_id in w3_expansion_ids)
    w4_expansion_ids: list[str] = []
    if w4_expansion is not None:
        w4_expansion_ids = [str(item.get("story_id")) for item in w4_expansion.get("records", [])]
        if w4_expansion.get("gold_story_ids") != gold_ids:
            errors.append("W4 Story expansion manifest does not preserve the exact SC0 Gold Set")
        if w4_expansion.get("selection_status") != "frozen":
            errors.append("W4 Story expansion manifest is not frozen")
        if len(w4_expansion_ids) != len(set(w4_expansion_ids)):
            errors.append("W4 Story expansion manifest contains duplicate Story IDs")
        if set(w4_expansion_ids) & (set(gold_ids) | set(expansion_ids) | set(w3_expansion_ids)):
            errors.append("W4 Story expansion manifest overlaps an existing publication set")
        selected.extend({"entry_id": story_id, "linked_person_ids": []} for story_id in w4_expansion_ids)
    selected_ids = [item.get("entry_id") for item in selected]
    corpus_by_id = {item.get("id"): item for item in corpus.get("entries", [])}
    selected.sort(key=lambda item: int(corpus_by_id.get(item.get("entry_id"), {}).get("global_ordinal", 10**9)))
    selected_ids = [item.get("entry_id") for item in selected]
    stories = bundle.get("stories", [])
    story_by_id = {item.get("id"): item for item in stories if isinstance(item, dict)}
    if selected_ids != [item.get("id") for item in stories]:
        errors.append("SC1 stories are not exactly the ordered SC0 + M2 + W3 + W4 expansion union")
    expected_story_count = len(gold_ids) + len(expansion_ids) + len(w3_expansion_ids) + len(w4_expansion_ids)
    if len(stories) != expected_story_count or len(story_by_id) != len(stories):
        errors.append(f"SC1 must contain exactly {expected_story_count} unique Stories from the frozen publication manifests")

    people_by_id = {item.get("id"): item for item in bundle.get("people", [])}
    mention_by_id = {item.get("id"): item for item in bundle.get("mentions", [])}
    ruler_mention_by_id = {
        item.get("mention_id"): item
        for item in bundle.get("ruler_mentions", [])
        if isinstance(item, dict) and isinstance(item.get("mention_id"), str)
    }
    relation_ids = {item.get("id") for item in bundle.get("relations", [])}
    evidence_by_id = {item.get("id"): item for item in bundle.get("evidence", [])}
    shared_display = bundle.get("display")
    if not isinstance(shared_display, dict):
        errors.append("SC1 shared display registry is missing")
    else:
        required_display_tables = {
            "labels": None,
            "people": set(people_by_id),
            "relations": set(relation_ids),
            "sources": {
                item.get("id")
                for item in bundle.get("sources", [])
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            },
            "evidence": set(evidence_by_id),
        }
        for table_name, expected_ids in required_display_tables.items():
            table = shared_display.get(table_name)
            if not isinstance(table, dict):
                errors.append(f"SC1 shared display table is missing: {table_name}")
                continue
            if expected_ids is not None and set(table) != expected_ids:
                errors.append(f"SC1 shared display table keys differ: {table_name}")
            for key, value in table.items():
                if table_name in {"labels", "evidence"}:
                    if not isinstance(value, dict) or not isinstance(value.get("original"), str) or not isinstance(value.get("simplified"), str):
                        errors.append(f"SC1 shared display pair is incomplete: {table_name}/{key}")
                elif not isinstance(value, dict):
                    errors.append(f"SC1 shared display record is invalid: {table_name}/{key}")
        labels = shared_display.get("labels")
        for key in (
            "people_section",
            "resolved_mentions_heading",
            "alias_hint",
            "resolved_alias_label",
            "annotation_label",
            "evidence_heading",
            "evidence_intro",
            "empty_alias",
            "relation_section",
            "direct_relation_label",
            "derived_relation_label",
            "derived_relation_note",
            "relation_evidence_toggle",
            "relation_evidence_heading",
            "no_direct_relations",
            "focused_person_label",
            "back_label",
        ):
            if not isinstance(labels, dict) or key not in labels:
                errors.append(f"SC1 shared display labels missing: {key}")
    converter = OpenCC("t2s")
    people_id_set = {str(item.get("id")) for item in bundle.get("people", []) if isinstance(item, dict) and isinstance(item.get("id"), str)}

    errors.extend(validate_sc1_source_provenance_coverage(root, bundle, mode=mode))
    errors.extend(validate_person_sketch_bundle(root))
    errors.extend(f"Scene Context schema: {error}" for error in validate_scene_source(root))
    try:
        scene_source = read_json(root / SCENE_SOURCE_PATH)
        expected_scene_contexts = project_scene_contexts(
            scene_source,
            story_ids={
                str(story.get("id"))
                for story in stories
                if isinstance(story, dict) and story.get("publication_state") != "blocked"
            },
            people=bundle.get("people", []),
            evidence_ids=set(evidence_by_id),
            converter=converter,
        )
        w3_scene_path = root / "data/annotation/story-scene-contexts-w3.json"
        if w3_scene_path.is_file():
            errors.extend(f"W3 Scene Context schema: {error}" for error in validate_scene_source_path(root, Path("data/annotation/story-scene-contexts-w3.json")))
            w3_scene_source = read_json(w3_scene_path)
            w3_contexts = project_scene_contexts(
                w3_scene_source,
                story_ids={
                    str(story.get("id"))
                    for story in stories
                    if isinstance(story, dict) and story.get("publication_state") != "blocked"
                },
                people=bundle.get("people", []),
                evidence_ids=set(evidence_by_id),
                converter=converter,
            )
            if set(expected_scene_contexts) & set(w3_contexts):
                errors.append("W3 Scene Context overlaps the existing curated projection")
            expected_scene_contexts = {**expected_scene_contexts, **w3_contexts}
        if bundle.get("scene_contexts") != expected_scene_contexts:
            errors.append("SC1 scene_contexts is not the deterministic projection of curated data")
        derived_scene = read_json(root / SCENE_DERIVED_PATH)
        if derived_scene.get("contexts") != expected_scene_contexts:
            errors.append("derived Story Scene Context projection differs from SC1")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"SC1 Scene Context projection cannot be validated: {exc}")
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
        if isinstance(reading, dict):
            for key in ("labels", "person_display", "source_display", "relation_display", "evidence_display"):
                if key in reading:
                    errors.append(f"SC1 Story retains duplicated shared display table: {entry_id}/{key}")
        main = punct.get("sections", {}).get("main_text", {})
        if reading.get("status") != punct.get("status"):
            errors.append(f"SC1 reading status differs from punctuation record: {entry_id}")
        expected_reader_main = normalize_reader_whitespace(str(main.get("punctuated_text", "")))
        if reading.get("main_text", {}).get("original") != expected_reader_main:
            errors.append(f"SC1 punctuated reading differs from punctuation record: {entry_id}")
        if strip_display_punctuation(str(main.get("punctuated_text", ""))) != strip_display_punctuation(canonical):
            errors.append(f"SC1 punctuation does not round-trip: {entry_id}")
        if reading.get("main_text", {}).get("simplified") != converter.convert(expected_reader_main):
            errors.append(f"SC1 simplified reading is not deterministic: {entry_id}")
        if "\n" in expected_reader_main or "\r" in expected_reader_main:
            errors.append(f"SC1 reader projection retains a physical source line break: {entry_id}")
        for annotation in reading.get("annotations", []):
            if not isinstance(annotation, dict):
                continue
            if "\n" in str(annotation.get("original", "")) or "\r" in str(annotation.get("original", "")):
                errors.append(
                    f"SC1 Liu annotation reader projection retains a physical source line break: {entry_id}/{annotation.get('id')}"
                )
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
        errors.extend(
            validate_inline_mention_projection(
                story,
                mention_by_id,
                people_id_set,
                ruler_mention_by_id,
            )
        )

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
    # Relations are the one intentional exception to the byte-identical WP1
    # shared-layer rule: the SC1 projection carries the current production
    # Relation registry, which includes the reviewed R3B wave.  Preserve the
    # historical WP1 records exactly while allowing additional reviewed
    # production records to be projected.
    base_relations_by_id = {item.get("id"): item for item in base.get("relations", [])}
    bundle_relations_by_id = {item.get("id"): item for item in bundle.get("relations", [])}
    for relation_id, base_relation in base_relations_by_id.items():
        if bundle_relations_by_id.get(relation_id) != base_relation:
            errors.append(f"SC1 changed existing WP1 Relation record: {relation_id}")
    for key in ("sources", "eras"):
        if bundle.get(key) != base.get(key):
            errors.append(f"SC1 changed shared WP1 {key} records")
    base_evidence = {item["id"]: item for item in base.get("evidence", [])}
    for evidence_id, item in base_evidence.items():
        if evidence_by_id.get(evidence_id) != item:
            errors.append(f"SC1 changed existing Evidence record: {evidence_id}")
    base_mentions = {item["id"]: item for item in base.get("mentions", [])}
    # ER1 is an effective-resolution projection.  It may change only the
    # identity-resolution fields of a copied WP1 Mention; canonical text,
    # anchors, layer, and evidence remain immutable.
    resolution_projection_keys = {
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
        "resolution_method",
        "display_span",
        "derived_only",
        "span_decision_id",
        "coreference_antecedent_mention_id",
    }
    for mention_id, item in base_mentions.items():
        projected = mention_by_id.get(mention_id)
        if not isinstance(projected, dict):
            errors.append(f"SC1 dropped existing Mention record: {mention_id}")
            continue
        immutable_base = {
            key: value for key, value in item.items()
            if key not in resolution_projection_keys
        }
        immutable_projected = {
            key: value for key, value in projected.items()
            if key not in resolution_projection_keys
        }
        if immutable_projected != immutable_base:
            errors.append(f"SC1 changed immutable existing Mention fields: {mention_id}")

    frontend_chain = bundle.get("story_chain", {})
    if frontend_chain.get("story_ids") != selected_ids:
        errors.append("SC1 story_chain.story_ids does not project the SC0 + M2 + W3 + W4 expansion union")
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
        if expected is None:
            story_mentions_for_entry = [
                mention for mention in raw_shishuo_mentions
                if mention.get("entry_id") == entry_id
                and isinstance(mention.get("person_id"), str)
            ]
            resolved_main_for_entry = sorted({
                str(mention["person_id"])
                for mention in story_mentions_for_entry
                if mention.get("section") == "main_text"
            })
            resolved_annotation_for_entry = sorted({
                str(mention["person_id"])
                for mention in story_mentions_for_entry
                if mention.get("section") == "liu_annotation"
            } - set(resolved_main_for_entry))
            expected = {
                "entry_id": entry_id,
                "linked_person_ids": list(dict.fromkeys([
                    *resolved_main_for_entry,
                    *resolved_annotation_for_entry,
                ])),
                "main_text_person_ids": resolved_main_for_entry,
                "liu_annotation_only_person_ids": resolved_annotation_for_entry,
            }
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
