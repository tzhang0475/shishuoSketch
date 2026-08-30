#!/usr/bin/env python3
"""Build the X1.2R Jianshu-backed review and extension projection.

The builder is intentionally a single deterministic pipeline.  The selected
Story IDs come from the frozen X1.1 manifest; no new selection is performed.
Only reviewed extension records are emitted, and the prior X1.2A extension is
referenced rather than copied or rewritten.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from typing import Any, Mapping

try:
    from scripts.x1_2r_common import (
        CANONICAL_EXTENSION_PATH,
        CHANNEL_AUDIT_PATH,
        CITATION_PATH,
        CONFLICT_PATH,
        EPOCH,
        EVIDENCE_BUNDLES_PATH,
        FACT_REOPEN_PATH,
        FACT_REVIEW_PATH,
        IDENTITY_REVIEW_PATH,
        MATERIALIZATION_PATH,
        OUTPUT_PATHS,
        PARTICIPANT_REVIEW_PATH,
        REALIZED_YIELD_PATH,
        S1_ALIGNMENT_PATH,
        S1_ASSERTIONS_PATH,
        S1_CITATIONS_PATH,
        S1_GLYPH_AUDIT_PATH,
        SELECTION_EPOCH,
        SUMMARY_PATH,
        X1_2A_CANONICAL_FACTS_PATH,
        X1_2A_FACT_REVIEW_PATH,
        X1_2A_MATERIALIZATION_PATH,
        X1_2A_PERSON_REVIEW_PATH,
        X1_2A_REVIEW_MANIFEST_PATH,
        X1_2A_STORY_REVIEW_PATH,
        X1_2P_DEPENDENCY_PATH,
        X1_2P_STORY_REVIEW_PATH,
        canonical_hash,
        direct_story_record,
        frozen_projection_input_hash,
        layer_for_block,
        load_alignment,
        load_assertions_by_story,
        load_citations_by_story,
        load_jianshu_by_story,
        load_mentions_by_story,
        load_people_by_id,
        previous_fact_rows,
        previous_identity_rows,
        previous_production_story_review,
        previous_x1_2a_hashes,
        previous_x1_2p_hashes,
        protected_hashes,
        read,
        relevant_assertions,
        selected_ids,
        selection_provenance,
        sha256_file,
        source_hashes,
        source_locator_key,
        stable_id,
        unique,
        write,
        x1_hashes,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from x1_2r_common import (
        CANONICAL_EXTENSION_PATH,
        CHANNEL_AUDIT_PATH,
        CITATION_PATH,
        CONFLICT_PATH,
        EPOCH,
        EVIDENCE_BUNDLES_PATH,
        FACT_REOPEN_PATH,
        FACT_REVIEW_PATH,
        IDENTITY_REVIEW_PATH,
        MATERIALIZATION_PATH,
        OUTPUT_PATHS,
        PARTICIPANT_REVIEW_PATH,
        REALIZED_YIELD_PATH,
        S1_ALIGNMENT_PATH,
        S1_ASSERTIONS_PATH,
        S1_CITATIONS_PATH,
        S1_GLYPH_AUDIT_PATH,
        SELECTION_EPOCH,
        SUMMARY_PATH,
        X1_2A_CANONICAL_FACTS_PATH,
        X1_2A_FACT_REVIEW_PATH,
        X1_2A_MATERIALIZATION_PATH,
        X1_2A_PERSON_REVIEW_PATH,
        X1_2A_REVIEW_MANIFEST_PATH,
        X1_2A_STORY_REVIEW_PATH,
        X1_2P_DEPENDENCY_PATH,
        X1_2P_STORY_REVIEW_PATH,
        canonical_hash,
        direct_story_record,
        frozen_projection_input_hash,
        layer_for_block,
        load_alignment,
        load_assertions_by_story,
        load_citations_by_story,
        load_jianshu_by_story,
        load_mentions_by_story,
        load_people_by_id,
        previous_fact_rows,
        previous_identity_rows,
        previous_production_story_review,
        previous_x1_2a_hashes,
        previous_x1_2p_hashes,
        protected_hashes,
        read,
        relevant_assertions,
        selected_ids,
        selection_provenance,
        sha256_file,
        source_hashes,
        source_locator_key,
        stable_id,
        unique,
        write,
        x1_hashes,
    )


GENERIC_TITLE_SURFACES = {
    "王公",
    "王丞相",
    "丞相",
    "郗公",
    "郗太傅",
    "庾太尉",
    "謝鎮西",
    "殷揚州",
    "王東亭",
    "宣武",
}


def _alignment_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    evidence = row.get("evidence", [])
    first_evidence = dict(evidence[0]) if evidence else {}
    return {
        "alignment_id": row.get("alignment_id"),
        "alignment_class": row.get("alignment_class"),
        "alignment_basis": row.get("alignment_basis", []),
        "alignment_note": row.get("alignment_note"),
        "scope": row.get("scope"),
        "canonical_entry_exists": row.get("canonical_entry_exists"),
        "editorial_segmentation_available": row.get("editorial_segmentation_available"),
        "meaningful_variant": row.get("meaningful_variant"),
        "opening_prefix_match_length": row.get("opening_prefix_match_length"),
        "source_story_key": row.get("source_story_key"),
        "source_locator": row.get("source_locator") or first_evidence.get("source_locator"),
        "source_id": first_evidence.get("source_id"),
        "base_text_sha256": first_evidence.get("base_text_sha256"),
    }


def _block_projection(block: Mapping[str, Any]) -> dict[str, Any]:
    block_type = str(block.get("block_type", "unknown"))
    return {
        "block_id": block.get("block_id"),
        "layer": layer_for_block(block_type),
        "block_type": block_type,
        "attribution": block.get("attribution"),
        "attribution_explicit": bool(block.get("attribution_explicit", False)),
        "embedded": bool(block.get("embedded", False)),
        "marker_index": block.get("marker_index"),
        "segmentation": block.get("segmentation"),
        "text": block.get("text", ""),
        "text_sha256": block.get("text_sha256"),
        "source_locator": block.get("source_locator", {}),
    }


def build_evidence_bundles() -> dict[str, Any]:
    ids = selected_ids()
    if len(ids) != 20 or len(set(ids)) != 20:
        raise ValueError(f"X1.2R requires exactly 20 unique frozen Stories, got {len(ids)}")
    alignment = load_alignment()
    jianshu = load_jianshu_by_story()
    mentions = load_mentions_by_story()
    citations = load_citations_by_story()
    glyph_rows = read(S1_GLYPH_AUDIT_PATH).get("records", [])
    glyph_by_story: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in glyph_rows:
        if isinstance(row, Mapping) and row.get("story_id") in ids:
            glyph_by_story[str(row["story_id"])].append(dict(row))

    records: list[dict[str, Any]] = []
    for story_id in ids:
        source = jianshu.get(story_id)
        if source is None:
            raise ValueError(f"S1 Jianshu cache has no aligned record for {story_id}")
        if story_id not in alignment:
            raise ValueError(f"S1 alignment has no record for {story_id}")
        blocks = [_block_projection(block) for block in source.get("blocks", [])]
        if not any(block["layer"] == "base_text" for block in blocks):
            base_text = str(source.get("base_text", ""))
            blocks.insert(0, {
                "block_id": stable_id("x1-2r-base-text", story_id),
                "layer": "base_text",
                "block_type": "base_text",
                "attribution": None,
                "attribution_explicit": False,
                "embedded": False,
                "marker_index": None,
                "segmentation": "cache_base_text",
                "text": base_text,
                "text_sha256": source.get("base_text_sha256"),
                "source_locator": source.get("source_locator", {}),
            })
        by_layer = defaultdict(list)
        for block in blocks:
            by_layer[block["layer"]].append(block)
        for layer in by_layer:
            by_layer[layer].sort(key=lambda row: (json.dumps(row.get("source_locator", {}), sort_keys=True), str(row.get("block_id", ""))))

        compact_mentions = []
        for mention in mentions.get(story_id, []):
            compact_mentions.append({
                "mention_id": mention.get("mention_id"),
                "section": mention.get("section"),
                "surface": mention.get("surface"),
                "person_id": mention.get("person_id"),
                "candidate_person_ids": sorted(mention.get("candidate_person_ids", []) or []),
                "alias_type": mention.get("alias_type"),
                "confidence": mention.get("confidence"),
                "resolution_method": mention.get("resolution_method"),
                "context": mention.get("context"),
                "evidence_ids": sorted(mention.get("evidence_ids", []) or []),
            })
        compact_citations = []
        for citation in citations.get(story_id, []):
            compact_citations.append({
                "citation_id": citation.get("citation_id"),
                "assertion_id": citation.get("assertion_id"),
                "note_author": citation.get("attribution"),
                "layer": citation.get("layer"),
                "citation_surface": citation.get("citation_surface"),
                "normalized_source": citation.get("normalized_source"),
                "quoted_passage": citation.get("quoted_passage"),
                "review_status": citation.get("review_status"),
                "source_locator": citation.get("source_locator", {}),
            })
        source_locators = [block.get("source_locator", {}) for block in blocks]
        source_locators += [row.get("source_locator", {}) for row in compact_citations]
        locator_values = [json.loads(value) for value in sorted({source_locator_key(locator) for locator in source_locators})]
        records.append({
            "story_id": story_id,
            "selection_provenance": selection_provenance(story_id),
            "canonical_source": direct_story_record(story_id),
            "alignment": _alignment_projection(alignment[story_id]),
            "jianshu_source": {
                "source_family": "shishuo-jianshu-yujiaxi-local",
                "source_id": "shishuo-jianshu-yujiaxi-local-epub",
                "story_key": source.get("story_key"),
                "chapter_id": source.get("chapter_id"),
                "chapter_heading": source.get("chapter_heading"),
                "chapter_number": source.get("chapter_number"),
                "ordinal": source.get("ordinal"),
                "source_locator": source.get("source_locator", {}),
            },
            "blocks": {
                "base_text": by_layer.get("base_text", []),
                "liu_annotation": by_layer.get("liu_annotation", []),
                "jianshu_note": by_layer.get("jianshu_note", []),
                "collation_note": by_layer.get("collation_note", []),
                "other_scholar_note": by_layer.get("other_scholar_note", []),
            },
            "block_count": len(blocks),
            "person_surfaces": compact_mentions,
            "source_citations": compact_citations,
            "source_locators": locator_values,
            "glyph_anomalies": sorted(glyph_by_story.get(story_id, []), key=lambda row: json.dumps(row, ensure_ascii=False, sort_keys=True)),
            "historical_assertion_ids": sorted(row.get("assertion_id") for row in read(S1_ASSERTIONS_PATH).get("records", []) if row.get("story_id") == story_id and row.get("assertion_id")),
            "evidence_bundle_status": "aligned",
        })

    document = {
        "schema": 1,
        "stage": "x1-2r-jianshu-evidence-bundles",
        "review_epoch": EPOCH,
        "scope": {
            "selection_epoch": SELECTION_EPOCH,
            "story_count": len(records),
            "selected_story_ids": ids,
            "selection_manifest_sha256": sha256_file("data/derived/x1-1-selection-manifest.json"),
            "new_story_selection_performed": False,
        },
        "source_hashes": {
            "jianshu_payloads": source_hashes(),
            "s1_registration": frozen_projection_input_hash("data/derived/s1-jianshu-source-registration.json"),
            "s1_alignment": sha256_file(S1_ALIGNMENT_PATH),
            "s1_assertions": sha256_file(S1_ASSERTIONS_PATH),
            "s1_citations": sha256_file(S1_CITATIONS_PATH),
            "s1_glyph_audit": sha256_file(S1_GLYPH_AUDIT_PATH),
        },
        "policy": {
            "base_text_primary_for_participation": True,
            "liu_annotation_is_not_hard_participation": True,
            "jianshu_commentary_is_not_automatic_fact": True,
            "citation_is_not_source_verification": True,
            "full_jianshu_dump_not_tracked": True,
        },
        "records": sorted(records, key=lambda row: row["story_id"]),
    }
    write(EVIDENCE_BUNDLES_PATH, document)
    return document


def _canonical_names_in_story(blocks: Mapping[str, list[dict[str, Any]]], person_ids: list[str], people: Mapping[str, Mapping[str, Any]]) -> list[str]:
    searchable = "".join(block.get("text", "") for layer in ("base_text", "liu_annotation", "jianshu_note") for block in blocks.get(layer, []))
    return [person_id for person_id in person_ids if people.get(person_id, {}).get("canonical_name") and people[person_id]["canonical_name"] in searchable]


def _story_local_mapping(mention: Mapping[str, Any], bundle: Mapping[str, Any], people: Mapping[str, Mapping[str, Any]]) -> tuple[str | None, str]:
    candidates = [str(value) for value in mention.get("candidate_person_ids", []) if str(value) in people]
    if not candidates:
        return None, "no_candidate_person"
    matching = _canonical_names_in_story(bundle.get("blocks", {}), candidates, people)
    if len(matching) == 1:
        return matching[0], "story_local_explicit_name_in_aligned_source"
    return None, "title_or_surface_collision_remains"


def _participant_record(story_id: str, mention: Mapping[str, Any], bundle: Mapping[str, Any], people: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    section = str(mention.get("section") or "unknown")
    person_id = str(mention["person_id"]) if mention.get("person_id") else None
    basis = "existing_resolved_mention"
    if not person_id and section == "main_text":
        person_id, basis = _story_local_mapping(mention, bundle, people)
    endpoint_status = "production_resolved" if person_id in people else (
        "production_resolved_story_local" if person_id else (
            "unresolved_identity_surface" if mention.get("candidate_person_ids") else "non_production_or_unresolved_endpoint"
        )
    )
    title_surface = mention.get("alias_type") in {"contextual_title", "office_title"} or mention.get("surface") in GENERIC_TITLE_SURFACES
    if section == "main_text":
        if person_id and not title_surface:
            role = "actor"
        elif person_id:
            role = "referenced"
        else:
            role = "uncertain"
    else:
        role = "annotation_only"
    hard = section == "main_text" and role in {"present", "speaker", "actor"} and person_id in people
    return {
        "participant_id": stable_id("x1-2r-participant", story_id, mention.get("mention_id"), mention.get("surface")),
        "story_id": story_id,
        "person_id": person_id,
        "surface": mention.get("surface"),
        "role": role,
        "hard_participation": hard,
        "hard_temporal_eligible": hard,
        "source_section": section,
        "mention_id": mention.get("mention_id"),
        "alias_type": mention.get("alias_type"),
        "endpoint_status": endpoint_status,
        "resolution_basis": basis,
        "evidence_ids": sorted(mention.get("evidence_ids", []) or []),
        "mention_context": mention.get("context"),
        "review_status": "reviewed",
        "assertion_status": "attested" if role != "uncertain" else "uncertain",
    }


def build_participant_review(bundles: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    people = load_people_by_id()
    mentions = load_mentions_by_story()
    old_story_review = previous_production_story_review()
    records: list[dict[str, Any]] = []
    for bundle in sorted(bundles["records"], key=lambda row: row["story_id"]):
        story_id = bundle["story_id"]
        participant_rows = [_participant_record(story_id, mention, bundle, people) for mention in mentions.get(story_id, [])]
        participant_rows.sort(key=lambda row: (str(row.get("source_section")), str(row.get("mention_id")), str(row.get("surface"))))
        hard = [row for row in participant_rows if row["hard_participation"]]
        annotation_only = [row for row in participant_rows if row["role"] == "annotation_only"]
        contextual = [row for row in participant_rows if row["role"] in {"referenced", "off_frame", "uncertain"}]
        unresolved_main = [row for row in participant_rows if row["source_section"] == "main_text" and row["role"] == "uncertain"]
        editorial = bundle["alignment"]
        editorial_pass = bool(editorial.get("editorial_segmentation_available") and editorial.get("alignment_class") not in {"meaningful_variant", "structural_ambiguity", "unmatched"})
        participant_gate = "unresolved" if unresolved_main else "pass"
        gate = "pass" if editorial_pass and participant_gate == "pass" else "unresolved"
        unresolved_surfaces = [
            {
                "surface": row.get("surface"),
                "mention_id": row.get("mention_id"),
                "reason": row.get("endpoint_status"),
                "source_section": row.get("source_section"),
            }
            for row in participant_rows
            if row.get("endpoint_status") in {"unresolved_identity_surface", "non_production_or_unresolved_endpoint"}
        ]
        records.append({
            "review_item_id": stable_id("x1-2r-participant-review", story_id),
            "story_id": story_id,
            "selection_provenance": bundle["selection_provenance"],
            "source_evidence_bundle_story_id": story_id,
            "chapter_id": bundle["canonical_source"].get("chapter_id"),
            "chapter_heading": bundle["canonical_source"].get("chapter_heading"),
            "source_x1_2p_story_review_status": old_story_review.get(story_id, {}).get("review_status"),
            "editorial_gate": {
                "s1_alignment_class": editorial.get("alignment_class"),
                "editorial_segmentation_available": editorial.get("editorial_segmentation_available"),
                "meaningful_variant": editorial.get("meaningful_variant"),
                "status": "pass" if editorial_pass else "unresolved",
            },
            "participant_gate": participant_gate,
            "overall_gate": gate,
            "review_status": "reviewed",
            "hard_participants": hard,
            "contextual_participants": contextual,
            "annotation_only_persons": annotation_only,
            "all_reviewed_surfaces": participant_rows,
            "unresolved_surfaces": unresolved_surfaces,
            "hard_participant_coverage_gap": {
                "status": "none" if hard else "unresolved",
                "reason": None if hard else (
                    "No reviewed production-resolved main-text surface was available for a hard participant; "
                    "no hard participant was inferred from annotation, PersonStory, or biography."
                ),
            },
            "hard_participant_person_ids": sorted({row["person_id"] for row in hard if row.get("person_id")}),
            "contextual_person_ids": sorted({row["person_id"] for row in contextual if row.get("person_id")}),
            "annotation_only_person_ids": sorted({row["person_id"] for row in annotation_only if row.get("person_id")}),
            "evidence_ids": sorted({evidence_id for row in participant_rows for evidence_id in row.get("evidence_ids", [])}),
            "review_reason": (
                "All observed Person surfaces have reviewed Story-local semantics; annotation-only records remain non-hard."
                if gate == "pass"
                else "A main-text surface remains an occurrence-level identity/role ambiguity; Jianshu is retained as evidence but does not justify a global title mapping."
            ),
            "participant_policy": {
                "mention_is_not_automatically_participation": True,
                "person_story_is_not_automatically_participation": True,
                "annotation_only_never_hard": True,
                "unresolved_endpoint_is_gap_not_negative": True,
            },
        })

    document = {
        "schema": 1,
        "stage": "x1-2r-participant-review",
        "review_epoch": EPOCH,
        "scope": {"story_count": len(records), "selected_story_ids": [row["story_id"] for row in records], "new_story_selection_performed": False},
        "source_hashes": {
            "evidence_bundles": sha256_file(EVIDENCE_BUNDLES_PATH),
            "x1_1_selection": sha256_file("data/derived/x1-1-selection-manifest.json"),
            "x1_2p_story_review": sha256_file(X1_2P_STORY_REVIEW_PATH),
            "people": sha256_file("data/people.json"),
            "mentions": sha256_file("data/mentions/shishuo.json"),
        },
        "counts": {
            "stories_reviewed": len(records),
            "participant_gate_pass": sum(row["participant_gate"] == "pass" for row in records),
            "participant_gate_unresolved": sum(row["participant_gate"] == "unresolved" for row in records),
            "hard_participant_records": sum(len(row["hard_participants"]) for row in records),
            "stories_without_hard_participant_records": sum(not row["hard_participants"] for row in records),
            "annotation_only_records": sum(len(row["annotation_only_persons"]) for row in records),
            "unresolved_main_surfaces": sum(len([item for item in row["unresolved_surfaces"] if item["source_section"] == "main_text"]) for row in records),
        },
        "records": records,
    }
    write(PARTICIPANT_REVIEW_PATH, document)

    previous = previous_identity_rows()
    identity_rows: list[dict[str, Any]] = []
    participant_by_story = {row["story_id"]: row for row in records}
    for old in sorted(previous, key=lambda row: str(row.get("review_item_id"))):
        story_id = str(old["story_id"])
        surface = str(old.get("surface", ""))
        observed = [
            row for row in participant_by_story.get(story_id, {}).get("all_reviewed_surfaces", [])
            if row.get("surface") == surface and row.get("source_section") == "main_text"
        ]
        mapped = [row for row in observed if row.get("person_id")]
        status = "accepted" if mapped and all(row.get("endpoint_status") == "production_resolved_story_local" for row in mapped) else "unresolved"
        identity_rows.append({
            "review_item_id": stable_id("x1-2r-identity-review", old.get("review_item_id")),
            "source_x1_2a_review_item_id": old.get("review_item_id"),
            "source_candidate_id": old.get("source_candidate_id"),
            "story_id": story_id,
            "surface": surface,
            "selection_provenance": old.get("selection_provenance"),
            "previous_review_history": {
                "stage": "X1.2A",
                "review_status": old.get("review_status"),
                "review_reason": old.get("review_reason"),
                "evidence_ids": old.get("evidence_ids", []),
            },
            "reopen_status": "reopened_due_to_new_source" if story_id in participant_by_story else "no_new_evidence",
            "evidence_route": "story_local_jianshu_and_existing_mentions" if story_id in participant_by_story else "none",
            "observed_participant_records": observed,
            "resolved_person_id": mapped[0].get("person_id") if status == "accepted" else None,
            "canonical_name": people.get(mapped[0].get("person_id"), {}).get("canonical_name") if status == "accepted" else None,
            "review_status": status,
            "review_reason": (
                "Aligned local evidence supplies one existing Person endpoint for the surface; the mapping remains Story-local."
                if status == "accepted"
                else "Jianshu evidence was reviewed, but the occurrence remains a generic/title collision or lacks a safe antecedent; no Person is created."
            ),
            "materialization_status": "deferred_until_story_release" if status == "accepted" else "not_materialized",
            "new_person_created": False,
        })
    identity_document = {
        "schema": 1,
        "stage": "x1-2r-identity-review",
        "review_epoch": EPOCH,
        "scope": {"candidate_count": len(identity_rows), "selected_story_ids": sorted({row["story_id"] for row in identity_rows})},
        "source_hashes": {
            "x1_2a_person_review": sha256_file(X1_2A_PERSON_REVIEW_PATH),
            "participant_review": sha256_file(PARTICIPANT_REVIEW_PATH),
            "evidence_bundles": sha256_file(EVIDENCE_BUNDLES_PATH),
        },
        "counts": {
            "total": len(identity_rows),
            "mapped_existing": sum(row["review_status"] == "accepted" for row in identity_rows),
            "new_persons": 0,
            "unresolved": sum(row["review_status"] == "unresolved" for row in identity_rows),
            "rejected": sum(row["review_status"] == "rejected" for row in identity_rows),
        },
        "records": identity_rows,
    }
    write(IDENTITY_REVIEW_PATH, identity_document)
    return document, identity_document


def _assertion_reference(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "assertion_id": row.get("assertion_id"),
        "layer": row.get("layer"),
        "attribution": row.get("attribution"),
        "attribution_explicit": row.get("attribution_explicit"),
        "modality": row.get("modality"),
        "candidate_fact_types": row.get("candidate_fact_types", []),
        "text": row.get("text"),
        "text_sha256": row.get("text_sha256"),
        "source_locator": row.get("source_locator", {}),
        "candidate_status": row.get("candidate_status"),
        "canonicalization_status": row.get("canonicalization_status"),
    }


def build_fact_reviews(bundles: Mapping[str, Any], participant: Mapping[str, Any], identity: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    old_rows = previous_fact_rows()
    assertions = load_assertions_by_story()
    participant_by_story = {row["story_id"]: row for row in participant["records"]}
    identity_story_ids = {row["story_id"] for row in identity["records"] if row["review_status"] == "unresolved"}
    fact_rows: list[dict[str, Any]] = []
    reopened: list[dict[str, Any]] = []
    for old in sorted(old_rows, key=lambda row: str(row.get("review_item_id"))):
        story_id = str(old["story_id"])
        layer = str(old.get("fact_layer"))
        hits = relevant_assertions(story_id, layer, assertions)
        participant_gate = participant_by_story.get(story_id, {}).get("participant_gate")
        if hits:
            classification = "new_Jianshu_evidence_hit"
            reopen_status = "reopened_due_to_new_source"
        elif participant_gate == "unresolved":
            classification = "participant_blocked"
            reopen_status = "not_reopened"
        elif story_id in identity_story_ids:
            classification = "identity_blocked"
            reopen_status = "not_reopened"
        elif any(row.get("story_id") == story_id for row in bundles["records"]):
            classification = "semantic_uncertainty"
            reopen_status = "not_reopened"
        else:
            classification = "other"
            reopen_status = "not_reopened"
        if hits and all(str(row.get("modality")) == "disputed" for row in hits):
            review_reason = "Jianshu supplies a route, but all matching assertions are explicitly disputed; the candidate remains unresolved rather than being promoted."
        elif hits:
            review_reason = "Jianshu supplies semantically related assertions, but the candidate does not provide sufficiently explicit, production-endpoint-safe fact semantics for canonical release."
        else:
            review_reason = old.get("review_reason") or "No independent evidence route cleared this candidate."
        row = {
            "review_item_id": stable_id("x1-2r-fact-review", old.get("review_item_id")),
            "source_x1_2a_review_item_id": old.get("review_item_id"),
            "source_candidate_id": old.get("source_candidate_id"),
            "story_id": story_id,
            "fact_layer": layer,
            "candidate_fact_types": old.get("candidate_fact_types", []),
            "selection_provenance": old.get("selection_provenance"),
            "previous_review_history": {
                "stage": "X1.2A",
                "review_status": old.get("review_status"),
                "review_reason": old.get("review_reason"),
                "evidence_ids": old.get("evidence_ids", []),
            },
            "previous_x1_2p_blocker": "blocked_by_story_punctuation",
            "reopen_classification": classification,
            "reopen_status": reopen_status,
            "new_evidence_assertion_ids": [row.get("assertion_id") for row in hits],
            "new_evidence_refs": [_assertion_reference(row) for row in hits],
            "review_status": "unresolved",
            "review_reason": review_reason,
            "review_notes": "Jianshu commentary, citation and contextual background do not by themselves establish a canonical fact. No new Person, Relation, EventParticipation or exact chronology is inferred.",
            "materialization_status": "not_materialized",
            "materialization_kinds": [],
            "no_ml_write_back": True,
        }
        fact_rows.append(row)
        if reopen_status == "reopened_due_to_new_source":
            reopened.append({
                "review_item_id": row["review_item_id"],
                "source_x1_2a_review_item_id": old.get("review_item_id"),
                "story_id": story_id,
                "fact_layer": layer,
                "assertion_ids": row["new_evidence_assertion_ids"],
                "reopen_status": reopen_status,
                "result": row["review_status"],
            })

    fact_document = {
        "schema": 1,
        "stage": "x1-2r-fact-review",
        "review_epoch": EPOCH,
        "scope": {"unresolved_x1_2a_fact_count": 58, "new_story_selection_performed": False},
        "source_hashes": {
            "x1_2a_fact_review": sha256_file(X1_2A_FACT_REVIEW_PATH),
            "x1_2p_dependency_audit": sha256_file(X1_2P_DEPENDENCY_PATH),
            "evidence_bundles": sha256_file(EVIDENCE_BUNDLES_PATH),
            "s1_assertions": sha256_file(S1_ASSERTIONS_PATH),
            "participant_review": sha256_file(PARTICIPANT_REVIEW_PATH),
            "identity_review": sha256_file(IDENTITY_REVIEW_PATH),
        },
        "counts": {
            "total": len(fact_rows),
            "reopened_due_to_new_source": sum(row["reopen_status"] == "reopened_due_to_new_source" for row in fact_rows),
            "accepted": 0,
            "unresolved": len(fact_rows),
            "rejected": 0,
            "materialized": 0,
        },
        "records": fact_rows,
    }
    write(FACT_REVIEW_PATH, fact_document)
    reopen_document = {
        "schema": 1,
        "stage": "x1-2r-fact-reopen-manifest",
        "review_epoch": EPOCH,
        "scope": {"source_x1_2a_unresolved_fact_count": len(old_rows), "new_story_selection_performed": False},
        "source_hashes": {
            "x1_2a_fact_review": sha256_file(X1_2A_FACT_REVIEW_PATH),
            "x1_2p_dependency_audit": sha256_file(X1_2P_DEPENDENCY_PATH),
            "s1_assertions": sha256_file(S1_ASSERTIONS_PATH),
        },
        "counts": {
            "total": len(fact_rows),
            "new_Jianshu_evidence_hit": sum(row["reopen_classification"] == "new_Jianshu_evidence_hit" for row in fact_rows),
            "participant_blocked": sum(row["reopen_classification"] == "participant_blocked" for row in fact_rows),
            "identity_blocked": sum(row["reopen_classification"] == "identity_blocked" for row in fact_rows),
            "semantic_uncertainty": sum(row["reopen_classification"] == "semantic_uncertainty" for row in fact_rows),
            "other": sum(row["reopen_classification"] == "other" for row in fact_rows),
            "reopened": len(reopened),
        },
        "records": fact_rows,
    }
    write(FACT_REOPEN_PATH, reopen_document)
    return fact_document, reopen_document, {"assertions": assertions}


def build_citations() -> dict[str, Any]:
    ids = set(selected_ids())
    rows: list[dict[str, Any]] = []
    for story_id, story_rows in sorted(load_citations_by_story().items()):
        if story_id not in ids:
            continue
        for citation in story_rows:
            rows.append({
                "citation_id": citation.get("citation_id"),
                "assertion_id": citation.get("assertion_id"),
                "story_id": story_id,
                "note_author": citation.get("attribution"),
                "note_layer": citation.get("layer"),
                "citation_surface": citation.get("citation_surface"),
                "normalized_source": citation.get("normalized_source"),
                "quoted_passage": citation.get("quoted_passage"),
                "source_locator": citation.get("source_locator", {}),
                "candidate_use": [],
                "verification_status": "citation_only",
                "review_status": "research_candidate",
                "research_only": True,
                "canonical_fact_created": False,
            })
    document = {
        "schema": 1,
        "stage": "x1-2r-citation-candidates",
        "review_epoch": EPOCH,
        "scope": {"story_count": len(ids), "selected_story_ids": sorted(ids), "new_story_selection_performed": False},
        "source_hashes": {"s1_citations": sha256_file(S1_CITATIONS_PATH), "evidence_bundles": sha256_file(EVIDENCE_BUNDLES_PATH)},
        "policy": {"citation_is_not_source_verification": True, "citation_edges_not_projected_to_hg0": True},
        "counts": {"citation_candidates": len(rows), "unique_sources": len({row["normalized_source"] for row in rows if row.get("normalized_source")})},
        "records": sorted(rows, key=lambda row: (row["story_id"], str(row.get("citation_id")), str(row.get("assertion_id")))),
    }
    write(CITATION_PATH, document)
    return document


def build_conflicts(participant: Mapping[str, Any], identity: Mapping[str, Any], facts: Mapping[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for story in participant["records"]:
        for surface in story.get("unresolved_surfaces", []):
            if surface.get("source_section") == "main_text":
                rows.append({
                    "conflict_id": stable_id("x1-2r-conflict", story["story_id"], surface.get("mention_id"), surface.get("surface")),
                    "category": "identity_compatibility_gap",
                    "story_id": story["story_id"],
                    "surface": surface.get("surface"),
                    "evidence_ids": story.get("evidence_ids", []),
                    "status": "unresolved",
                    "reason": "Main-text title/person surface has no safe occurrence-level endpoint; graph topology and generic title fallback are prohibited.",
                })
    for row in identity["records"]:
        if row["review_status"] == "unresolved":
            rows.append({
                "conflict_id": stable_id("x1-2r-identity-conflict", row.get("review_item_id")),
                "category": "identity_compatibility_gap",
                "story_id": row["story_id"],
                "surface": row["surface"],
                "review_item_id": row["review_item_id"],
                "evidence_ids": [],
                "status": "unresolved",
                "reason": row["review_reason"],
            })
    for row in facts["records"]:
        if row["new_evidence_refs"] and any(ref.get("modality") == "disputed" for ref in row["new_evidence_refs"]):
            rows.append({
                "conflict_id": stable_id("x1-2r-source-conflict", row["review_item_id"]),
                "category": "source_conflict",
                "story_id": row["story_id"],
                "fact_review_item_id": row["review_item_id"],
                "evidence_ids": row["new_evidence_assertion_ids"],
                "status": "preserved",
                "reason": "The aligned Jianshu material preserves competing or explicitly disputed historical readings; no convenient selection was made.",
            })
    document = {
        "schema": 1,
        "stage": "x1-2r-conflict-audit",
        "review_epoch": EPOCH,
        "source_hashes": {"participant_review": sha256_file(PARTICIPANT_REVIEW_PATH), "identity_review": sha256_file(IDENTITY_REVIEW_PATH), "fact_review": sha256_file(FACT_REVIEW_PATH)},
        "counts": dict(sorted(Counter(row["category"] for row in rows).items())),
        "records": sorted(rows, key=lambda row: str(row["conflict_id"])),
        "policy": {"preserve_competing_evidence": True, "no_silent_reconciliation": True},
    }
    write(CONFLICT_PATH, document)
    return document


def _accepted_story_rows(participant: Mapping[str, Any], bundles: Mapping[str, Any]) -> list[dict[str, Any]]:
    bundle_by_story = {row["story_id"]: row for row in bundles["records"]}
    rows = []
    for row in participant["records"]:
        if row["overall_gate"] != "pass":
            continue
        bundle = bundle_by_story[row["story_id"]]
        rows.append({
            "story_id": row["story_id"],
            "canonical_scope": "x1-2r-canonical-extension",
            "materialization_status": "accepted_for_canonical_extension",
            "publication_state": "extension_reviewed_not_published",
            "canonical_source": bundle["canonical_source"],
            "selection_provenance": row["selection_provenance"],
            "alignment": bundle["alignment"],
            "participant_review_id": row["review_item_id"],
            "hard_participant_person_ids": row["hard_participant_person_ids"],
            "contextual_person_ids": row["contextual_person_ids"],
            "annotation_only_person_ids": row["annotation_only_person_ids"],
            "source_ids": ["shishuo-jianshu-yujiaxi-local-epub"],
            "source_text_unchanged": True,
            "note": "Extension-only release; the protected 143-Story production projection is not rewritten in X1.2R.",
        })
    return sorted(rows, key=lambda row: row["story_id"])


def build_materialization(bundles: Mapping[str, Any], participant: Mapping[str, Any], identity: Mapping[str, Any], facts: Mapping[str, Any], citations: Mapping[str, Any], conflicts: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    stories = _accepted_story_rows(participant, bundles)
    accepted_story_ids = {row["story_id"] for row in stories}
    participant_records = [
        dict(surface)
        for story in participant["records"]
        if story["story_id"] in accepted_story_ids
        for surface in story.get("all_reviewed_surfaces", [])
    ]
    participant_records.sort(key=lambda row: str(row.get("participant_id", "")))
    extension_links = []
    extension_mentions = []
    for row in participant_records:
        if not row.get("person_id"):
            continue
        link_id = stable_id("x1-2r-person-story", row["person_id"], row["story_id"], row.get("mention_id"), row.get("surface"))
        extension_links.append({
            "link_id": link_id,
            "person_id": row["person_id"],
            "story_id": row["story_id"],
            "surface": row.get("surface"),
            "role": row.get("role"),
            "source_section": row.get("source_section"),
            "hard_participation": row.get("hard_participation", False),
            "participant_id": row.get("participant_id"),
            "review_status": row.get("review_status"),
            "canonical_scope": "x1-2r-canonical-extension",
        })
        if row.get("mention_id"):
            extension_mentions.append({
                "mention_id": row.get("mention_id"),
                "story_id": row["story_id"],
                "person_id": row["person_id"],
                "surface": row.get("surface"),
                "section": row.get("source_section"),
                "role": row.get("role"),
                "hard_participation": row.get("hard_participation", False),
                "participant_id": row.get("participant_id"),
                "canonical_scope": "x1-2r-canonical-extension",
            })
    extension_links.sort(key=lambda row: row["link_id"])
    extension_mentions.sort(key=lambda row: (row["story_id"], row["mention_id"]))
    new_facts = [row for row in facts["records"] if row["review_status"] == "accepted"]
    new_persons = [row for row in identity["records"] if row["review_status"] == "accepted" and row.get("new_person_created")]
    old_extension = read(X1_2A_CANONICAL_FACTS_PATH)
    extension = {
        "schema": 1,
        "stage": "x1-2r-canonical-extension",
        "materialization_epoch": EPOCH,
        "canonical_scope": "x1-2r-canonical-extension",
        "source_hashes": {
            "selection_manifest": sha256_file("data/derived/x1-1-selection-manifest.json"),
            "participant_review": sha256_file(PARTICIPANT_REVIEW_PATH),
            "identity_review": sha256_file(IDENTITY_REVIEW_PATH),
            "fact_review": sha256_file(FACT_REVIEW_PATH),
            "evidence_bundles": sha256_file(EVIDENCE_BUNDLES_PATH),
        },
        "prior_extension": {
            "path": str(X1_2A_CANONICAL_FACTS_PATH),
            "sha256": sha256_file(X1_2A_CANONICAL_FACTS_PATH),
            "fact_count": len(old_extension.get("fact_index", [])),
            "entity_count": len(old_extension.get("entities", [])),
            "preserved_without_copy": True,
        },
        "stories": [
            {
                **story,
                "participant_record_ids": sorted(
                    row["participant_id"]
                    for row in participant_records
                    if row["story_id"] == story["story_id"]
                ),
                "person_story_link_ids": sorted(
                    row["link_id"]
                    for row in extension_links
                    if row["story_id"] == story["story_id"]
                ),
            }
            for story in stories
        ],
        "participant_records": participant_records,
        "person_story_links": extension_links,
        "mention_projections": extension_mentions,
        "entities": new_persons,
        "fact_index": new_facts,
        "counts": {
            "stories": len(stories),
            "persons": len(new_persons),
            "facts": len(new_facts),
            "conflicts_preserved": len(conflicts.get("records", [])),
            "participant_records": len(participant_records),
            "person_story_links": len(extension_links),
            "mention_projections": len(extension_mentions),
        },
        "policy": {
            "extension_only": True,
            "no_existing_fact_duplication": True,
            "no_production_story_projection_mutation": True,
            "no_global_alias_mutation": True,
            "no_ml_write_back": True,
        },
    }
    write(CANONICAL_EXTENSION_PATH, extension)
    materialization = {
        "schema": 1,
        "stage": "x1-2r-materialization-manifest",
        "materialization_epoch": EPOCH,
        "canonical_scope": "x1-2r-canonical-extension",
        "source_hashes": {
            "x1_1_selection": sha256_file("data/derived/x1-1-selection-manifest.json"),
            "s1_alignment": sha256_file(S1_ALIGNMENT_PATH),
            "x1_2a_review_manifest": sha256_file(X1_2A_REVIEW_MANIFEST_PATH),
            "x1_2a_story_review": sha256_file(X1_2A_STORY_REVIEW_PATH),
            "x1_2a_person_review": sha256_file(X1_2A_PERSON_REVIEW_PATH),
            "x1_2a_fact_review": sha256_file(X1_2A_FACT_REVIEW_PATH),
            "x1_2a_canonical_facts": sha256_file(X1_2A_CANONICAL_FACTS_PATH),
            "x1_2a_materialization": sha256_file(X1_2A_MATERIALIZATION_PATH),
            "x1_2p_story_review": sha256_file(X1_2P_STORY_REVIEW_PATH),
            "x1_2p_dependency_audit": sha256_file(X1_2P_DEPENDENCY_PATH),
            "participant_review": sha256_file(PARTICIPANT_REVIEW_PATH),
            "identity_review": sha256_file(IDENTITY_REVIEW_PATH),
            "fact_review": sha256_file(FACT_REVIEW_PATH),
        },
        "prior_extension": extension["prior_extension"],
        "counts": {
            "stories_reviewed": len(participant["records"]),
            "stories_accepted_for_canonical_extension": len(stories),
            "persons_added": len(new_persons),
            "facts_added": len(new_facts),
            "stories_added_to_production_scope": 0,
            "participant_records_added": len(participant_records),
            "person_story_links_added": len(extension_links),
            "mention_projections_added": len(extension_mentions),
        },
        "canonical_story_ids": [row["story_id"] for row in stories],
        "canonical_person_ids": [row.get("person_id") for row in new_persons if row.get("person_id")],
        "canonical_fact_ids": [row.get("fact_id") for row in new_facts if row.get("fact_id")],
        "extension_sha256": sha256_file(CANONICAL_EXTENSION_PATH),
        "protected_inputs": protected_hashes(),
        "preservation": {
            "x1_2a_extension_unchanged": sha256_file(X1_2A_CANONICAL_FACTS_PATH) == extension["prior_extension"]["sha256"],
            "x1_2p_unchanged": previous_x1_2p_hashes(),
            "no_new_story_selection": True,
            "no_ml_write_back": True,
            "production_projection_unchanged": True,
        },
    }
    write(MATERIALIZATION_PATH, materialization)
    return extension, materialization


def build_yield(participant: Mapping[str, Any], identity: Mapping[str, Any], facts: Mapping[str, Any], materialization: Mapping[str, Any], citations: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    by_mode: dict[str, list[str]] = defaultdict(list)
    for row in participant["records"]:
        by_mode[str(row["selection_provenance"].get("selection_mode"))].append(row["story_id"])
    story_by_id = {row["story_id"]: row for row in participant["records"]}
    story_source_by_id = {story_id: direct_story_record(story_id) for story_id in story_by_id}
    identity_by_story = defaultdict(list)
    for row in identity["records"]:
        identity_by_story[row["story_id"]].append(row)
    fact_by_story = defaultdict(list)
    for row in facts["records"]:
        fact_by_story[row["story_id"]].append(row)
    channels = []
    for mode in ("graph_guided", "coverage_guided", "stratified_random", "counter_model"):
        ids = sorted(by_mode.get(mode, []))
        channels.append({
            "selection_mode": mode,
            "selected_story_ids": ids,
            "selected_story_count": len(ids),
            "participant_gate_pass": sum(story_by_id[sid]["participant_gate"] == "pass" for sid in ids),
            "canonical_extension_story_count": sum(sid in materialization["canonical_story_ids"] for sid in ids),
            "canonical_production_story_count": 0,
            "existing_person_identity_resolutions": sum(row["review_status"] == "accepted" and not row.get("new_person_created") for sid in ids for row in identity_by_story.get(sid, [])),
            "new_person_count": sum(row.get("new_person_created") for sid in ids for row in identity_by_story.get(sid, [])),
            "facts_reopened": sum(row["reopen_status"] == "reopened_due_to_new_source" for sid in ids for row in fact_by_story.get(sid, [])),
            "facts_accepted": sum(row["review_status"] == "accepted" for sid in ids for row in fact_by_story.get(sid, [])),
            "facts_materialized": 0,
            "facts_unresolved": sum(row["review_status"] == "unresolved" for sid in ids for row in fact_by_story.get(sid, [])),
            "fact_layers_materialized": {},
            "interpretation": "Observed pilot yield; not a historical-importance score and not a causal comparison.",
        })
    document = {
        "schema": 1,
        "stage": "x1-2r-realized-yield",
        "review_epoch": EPOCH,
        "source_hashes": {"participant_review": sha256_file(PARTICIPANT_REVIEW_PATH), "identity_review": sha256_file(IDENTITY_REVIEW_PATH), "fact_review": sha256_file(FACT_REVIEW_PATH), "materialization": sha256_file(MATERIALIZATION_PATH)},
        "overall": {
            "stories_reviewed": len(participant["records"]),
            "stories_participant_pass": participant["counts"]["participant_gate_pass"],
            "stories_canonical_extension": len(materialization["canonical_story_ids"]),
            "stories_canonical_production": 0,
            "identities_reviewed": identity["counts"]["total"],
            "identities_mapped_existing": identity["counts"]["mapped_existing"],
            "identities_new_persons": identity["counts"]["new_persons"],
            "identities_unresolved": identity["counts"]["unresolved"],
            "facts_reopened": facts["counts"]["reopened_due_to_new_source"],
            "facts_accepted": facts["counts"]["accepted"],
            "facts_unresolved": facts["counts"]["unresolved"],
            "facts_rejected": facts["counts"]["rejected"],
            "facts_materialized": facts["counts"]["materialized"],
            "citation_candidates": citations["counts"]["citation_candidates"],
            "unique_cited_works": citations["counts"]["unique_sources"],
        },
        "channels": channels,
    }
    write(REALIZED_YIELD_PATH, document)

    proxy_records = read("data/derived/x1-1-review-results.json").get("records", [])
    proxy_by_story = {row["story_id"]: row for row in proxy_records}
    channel_audit = []
    for channel in channels:
        proxy_units = 0
        for sid in channel["selected_story_ids"]:
            proxy_units += sum(
                len(action.get("targets", []))
                for action in proxy_by_story.get(sid, {}).get("actions", [])
                if action.get("action") == "ADD_FACT"
            )
        realized_units = channel["canonical_extension_story_count"] + channel["facts_accepted"] + channel["existing_person_identity_resolutions"]
        channel_audit.append({
            "selection_mode": channel["selection_mode"],
            "x1_1_proxy_information_units": proxy_units,
            "x1_2r_realized_canonical_information_units": realized_units,
            "proxy_vs_realized": "insufficient_sample" if realized_units == 0 else ("proxy_aligned" if realized_units >= proxy_units else "proxy_optimistic"),
            "observed_gain_per_selected_story": realized_units / channel["selected_story_count"] if channel["selected_story_count"] else 0.0,
            "note": "The proxy count is a candidate-action count; the realized count is reviewed extension information only.",
        })
    hard_person_counts = Counter(row["person_id"] for row in participant["records"] for row in row.get("hard_participants", []) if row.get("person_id"))
    bias = {
        "story_count_by_channel": {row["selection_mode"]: row["selected_story_count"] for row in channels},
        "chapter_count_by_channel": {
            mode: dict(sorted(Counter(story_source_by_id[sid].get("chapter_id") for sid in ids).items()))
            for mode, ids in sorted(by_mode.items())
        },
        "hard_participant_person_frequency": dict(sorted(hard_person_counts.items())),
        "dense_core_surface": {
            "top_person_id_by_hard_participant_count": hard_person_counts.most_common(1)[0][0] if hard_person_counts else None,
            "top_person_count": hard_person_counts.most_common(1)[0][1] if hard_person_counts else 0,
            "interpretation": "Frequency reports selection concentration only; it is not historical importance.",
        },
        "channel_audit": channel_audit,
        "policy": {"model_score_not_historical_evidence": True, "counter_model_retained": True, "random_control_retained": True},
    }
    write(CHANNEL_AUDIT_PATH, {
        "schema": 1,
        "stage": "x1-2r-channel-audit",
        "review_epoch": EPOCH,
        "source_hashes": {"x1_1_review_results": sha256_file("data/derived/x1-1-review-results.json"), "realized_yield": sha256_file(REALIZED_YIELD_PATH)},
        "channels": channel_audit,
        "bias_audit": bias,
        "counter_model_audit": {
            "selection_mode": "counter_model",
            "selected_story_count": next(row["selected_story_count"] for row in channels if row["selection_mode"] == "counter_model"),
            "realized_extension_story_count": next(row["canonical_extension_story_count"] for row in channels if row["selection_mode"] == "counter_model"),
            "classification": "meaningful_blind_spot_signal" if next(row["canonical_extension_story_count"] for row in channels if row["selection_mode"] == "counter_model") else "possible_blind_spot_signal",
            "reason": "Counter-model Stories are evaluated after the shared editorial bottleneck; absence of new facts is not evidence that the Stories were historically low-value.",
        },
        "random_control_audit": {
            "selection_mode": "stratified_random",
            "classification": "independent_control",
            "reason": "The random channel remains independent of ML ranking and is reported without retrospective rescoring.",
        },
    })
    return document, bias


def build_summary(evidence: Mapping[str, Any], participant: Mapping[str, Any], identity: Mapping[str, Any], facts: Mapping[str, Any], citations: Mapping[str, Any], conflicts: Mapping[str, Any], materialization: Mapping[str, Any], yield_doc: Mapping[str, Any], channel_audit: Mapping[str, Any]) -> dict[str, Any]:
    layer_counts = Counter(row["fact_layer"] for row in facts["records"] if row["review_status"] == "accepted")
    fact_layer_review: dict[str, dict[str, int]] = {}
    for layer in sorted({row["fact_layer"] for row in facts["records"]}):
        layer_rows = [row for row in facts["records"] if row["fact_layer"] == layer]
        fact_layer_review[layer] = {
            "total": len(layer_rows),
            "reopened_due_to_new_source": sum(row["reopen_status"] == "reopened_due_to_new_source" for row in layer_rows),
            "accepted": sum(row["review_status"] == "accepted" for row in layer_rows),
            "unresolved": sum(row["review_status"] == "unresolved" for row in layer_rows),
            "rejected": sum(row["review_status"] == "rejected" for row in layer_rows),
        }
    assertion_layer_counts = Counter(
        ref.get("layer")
        for row in facts["records"]
        for ref in row.get("new_evidence_refs", [])
        if ref.get("layer")
    )
    jianshu_participant_context = sum(
        1
        for story in participant["records"]
        for row in story.get("all_reviewed_surfaces", [])
        if row.get("resolution_basis") == "story_local_explicit_name_in_aligned_source"
    )
    story_ids = materialization["canonical_story_ids"]
    hg_ready = bool(story_ids or materialization["canonical_fact_ids"] or materialization["canonical_person_ids"])
    document = {
        "schema": 1,
        "stage": "x1-2r-summary",
        "review_epoch": EPOCH,
        "scope": {"selected_story_count": len(selected_ids()), "selected_story_ids": selected_ids(), "new_story_selection_performed": False},
        "source_hashes": {
            "x1_1_selection": sha256_file("data/derived/x1-1-selection-manifest.json"),
            "s1_alignment": sha256_file(S1_ALIGNMENT_PATH),
            "evidence_bundles": sha256_file(EVIDENCE_BUNDLES_PATH),
            "participant_review": sha256_file(PARTICIPANT_REVIEW_PATH),
            "identity_review": sha256_file(IDENTITY_REVIEW_PATH),
            "fact_review": sha256_file(FACT_REVIEW_PATH),
            "materialization": sha256_file(MATERIALIZATION_PATH),
        },
        "jianshu_evidence_pilot": {
            "stories_bundled": evidence["scope"]["story_count"],
            "liu_annotation_blocks": sum(len(row["blocks"]["liu_annotation"]) for row in evidence["records"]),
            "jianshu_note_blocks": sum(len(row["blocks"]["jianshu_note"]) for row in evidence["records"]),
            "collation_note_blocks": sum(len(row["blocks"]["collation_note"]) for row in evidence["records"]),
            "liu_annotations_used_for_participant_review": participant["counts"]["annotation_only_records"],
            "jianshu_notes_used_for_fact_reopening": assertion_layer_counts.get("jianshu_note", 0),
            "collation_notes_used_for_historical_fact_release": 0,
            "stories_cleared_using_story_local_jianshu_identity_context": jianshu_participant_context,
            "citation_candidates": citations["counts"]["citation_candidates"],
            "unique_cited_works": citations["counts"]["unique_sources"],
            "pdf_fallback_checks": 0,
            "source_role": "scholarly_working_reference_not_primary_witness",
        },
        "participant_review": participant["counts"],
        "identity_review": identity["counts"],
        "fact_review": {**facts["counts"], "accepted_by_layer": dict(sorted(layer_counts.items())), "by_layer": fact_layer_review, "new_evidence_assertions_by_layer": dict(sorted(assertion_layer_counts.items()))},
        "canonical_delta": {
            "stories_in_extension": len(materialization["canonical_story_ids"]),
            "stories_added_to_production_scope": 0,
            "persons": len(materialization["canonical_person_ids"]),
            "facts": len(materialization["canonical_fact_ids"]),
            "entities": len(materialization["canonical_person_ids"]),
        },
        "selection_channel_audit": channel_audit["channels"],
        "conflicts": conflicts["counts"],
        "remaining_blockers": [
            "generic/title identity surfaces remain unresolved in 04-wenxue-021 and 05-fangzheng-039",
            "Jianshu historical assertions frequently provide commentary or citation context rather than a production-endpoint-safe fact",
            "cited historical works remain unverified source candidates",
            "accepted Story extension records are not merged into the protected 143-Story production projection until a downstream graph rebuild",
        ],
        "hg1_1_ready": hg_ready,
        "hg1_1_readiness_reason": (
            "The participant-reviewed Story extension is non-empty and provides a deterministic post-S1 graph input; external historical fact gain remains sparse and must be represented as gaps."
            if hg_ready
            else "No non-trivial canonical extension was released; the participant or identity gate remains the next blocker."
        ),
        "protection": {
            "x1_2a_extension_protected": True,
            "x1_2p_artifacts_protected": True,
            "h0c_hg0_ml0_protected": True,
            "no_ml_write_back": True,
            "no_new_story_selection": True,
            "no_ontology_change": True,
        },
        "stop_boundary": ["X1.2B", "HG1.1", "ML1.1", "ER2"],
    }
    write(SUMMARY_PATH, document)
    return document


def build() -> dict[str, Any]:
    bundles = build_evidence_bundles()
    participant, identity = build_participant_review(bundles)
    facts, reopen, _ = build_fact_reviews(bundles, participant, identity)
    citations = build_citations()
    conflicts = build_conflicts(participant, identity, facts)
    _extension, materialization = build_materialization(bundles, participant, identity, facts, citations, conflicts)
    yield_doc, _bias = build_yield(participant, identity, facts, materialization, citations)
    channel_audit = read(CHANNEL_AUDIT_PATH)
    return build_summary(bundles, participant, identity, facts, citations, conflicts, materialization, yield_doc, channel_audit)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    summary = build()
    print(json.dumps({"stage": summary["stage"], "counts": {"stories": summary["participant_review"]["stories_reviewed"], "participant_pass": summary["participant_review"]["participant_gate_pass"], "facts_reopened": summary["fact_review"]["reopened_due_to_new_source"], "stories_in_extension": summary["canonical_delta"]["stories_in_extension"]}, "hg1_1_ready": summary["hg1_1_ready"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
