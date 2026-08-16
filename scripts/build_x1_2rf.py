#!/usr/bin/env python3
"""Build the X1.2R-F assertion-level Jianshu fact review.

The builder is deliberately conservative and extension-only.  It reviews the
already frozen 20-Story Jianshu universe, keeps the original X1.2R candidate
decisions separate, and materializes only a small set of explicit,
endpoint-safe propositions whose existing H0C ontology can represent them.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from typing import Any, Mapping

try:
    from scripts.x1_2rf_common import (
        ALLOWED_REVIEW_STATES,
        ASSERTION_REVIEW_PATH,
        CORROBORATION_PATH,
        EPOCH,
        H0C_FACTS_PATH,
        MATERIALIZED_FACTS_PATH,
        NEXT_STEP_PATH,
        ORIGINAL_REVIEW_PATH,
        OUTPUT_PATHS,
        POLICY_PATH,
        SCHOLARLY_ASSERTIONS_PATH,
        S1_ASSERTIONS_PATH,
        SUMMARY_PATH,
        X1_2R_BUNDLES_PATH,
        X1_2R_FACT_REVIEW_PATH,
        X1_2R_IDENTITY_PATH,
        X1_2R_PARTICIPANT_PATH,
        X1_2R_CITATION_PATH,
        X1_2R_EXTENSION_PATH,
        X1_2R_MATERIALIZATION_PATH,
        X1_2R_SUMMARY_PATH,
        X1_2A_FACTS_PATH,
        canonical_hash,
        evidence_hash,
        existing_semantic_keys,
        excerpt,
        input_hashes,
        load_assertions,
        load_citations,
        load_x1_2r_facts,
        locations_by_name,
        offices_by_name,
        protected_hashes,
        quoted_source_for,
        read,
        reopened_x1_2r_facts,
        selected_ids,
        source_hashes,
        source_transmission,
        stable_id,
        write,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from x1_2rf_common import (
        ALLOWED_REVIEW_STATES,
        ASSERTION_REVIEW_PATH,
        CORROBORATION_PATH,
        EPOCH,
        H0C_FACTS_PATH,
        MATERIALIZED_FACTS_PATH,
        NEXT_STEP_PATH,
        ORIGINAL_REVIEW_PATH,
        OUTPUT_PATHS,
        POLICY_PATH,
        SCHOLARLY_ASSERTIONS_PATH,
        S1_ASSERTIONS_PATH,
        SUMMARY_PATH,
        X1_2R_BUNDLES_PATH,
        X1_2R_FACT_REVIEW_PATH,
        X1_2R_IDENTITY_PATH,
        X1_2R_PARTICIPANT_PATH,
        X1_2R_CITATION_PATH,
        X1_2R_EXTENSION_PATH,
        X1_2R_MATERIALIZATION_PATH,
        X1_2R_SUMMARY_PATH,
        X1_2A_FACTS_PATH,
        canonical_hash,
        evidence_hash,
        existing_semantic_keys,
        excerpt,
        input_hashes,
        load_assertions,
        load_citations,
        load_x1_2r_facts,
        locations_by_name,
        offices_by_name,
        protected_hashes,
        quoted_source_for,
        read,
        reopened_x1_2r_facts,
        selected_ids,
        source_hashes,
        source_transmission,
        stable_id,
        write,
    )


SOURCE_ASSERTION_IDS = {
    "office_habits_letter": "s1-assertion-37db448f1a3cd3d4b8d8",
    "office_history_named_source": "s1-assertion-7ddb1fd033eea16e0959",
    "office_history_meng_jia": "s1-assertion-999b2025717ca979fd32",
    "danyang_quoted_record": "s1-assertion-40d736dd768f591858b2",
}


def _assertion_index(rows: list[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["assertion_id"]): dict(row) for row in rows}


def _related_candidates(assertion_id: str, fact_rows: list[Mapping[str, Any]]) -> list[str]:
    return sorted(
        str(row["review_item_id"])
        for row in fact_rows
        if assertion_id in (row.get("new_evidence_assertion_ids") or [])
    )


def _source_assertion_class(row: Mapping[str, Any], quoted_source: str | None, is_citation_only: bool) -> str:
    if is_citation_only:
        return "E_citation_only"
    if str(row.get("modality")) in {"probable", "possible", "disputed", "unknown"}:
        return "D_modal_or_disputed"
    if str(row.get("layer")) == "collation_note":
        return "C_scholarly_or_collation"
    if str(row.get("layer")) == "jianshu_note" and (row.get("attribution") or quoted_source):
        return "B_or_C_transmitted_or_scholarly"
    if quoted_source:
        return "B_named_quotation"
    return "F_endpoint_or_semantic_review_required"


def _base_review(row: Mapping[str, Any], citations: Mapping[str, list[dict[str, Any]]], fact_rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    assertion_id = str(row["assertion_id"])
    quoted_source = quoted_source_for(row, citations)
    modality = str(row.get("modality", "unknown"))
    is_citation = _citation_only(row, quoted_source)
    if is_citation:
        status = "citation_only"
        reason = "The passage identifies a cited work or source lead but does not provide a reviewed, endpoint-safe proposition."
    elif str(row.get("layer")) == "collation_note":
        status = "scholarly_assertion_only"
        reason = "Collation material is preserved as editorial evidence and is not flattened into a historical fact."
    elif modality in {"probable", "possible", "disputed", "unknown"}:
        status = "scholarly_assertion_only"
        reason = {
            "probable": "The passage carries probable or inferential modality; it remains a scholarly assertion rather than a certain fact.",
            "possible": "The passage carries possible modality; it remains a scholarly assertion rather than a certain fact.",
            "disputed": "The passage records a disputed source or scholarly position; it is not promoted to a certain fact.",
            "unknown": "The assertion modality is unknown and cannot support certain fact materialization.",
        }[modality]
    elif row.get("attribution") or quoted_source:
        status = "scholarly_assertion_only"
        reason = "The block contains explicit source or scholarly material, but no independently reviewed endpoint-safe proposition was selected from this block."
    else:
        status = "unresolved"
        reason = "The assertion is explicit-looking but its endpoint or ontology semantics are not safe to materialize at block level."
    return {
        "review_item_id": stable_id("x1-2rf-review", assertion_id, "block"),
        "assertion_unit_id": "block",
        "source_assertion_id": assertion_id,
        "story_id": row.get("story_id"),
        "source_family": "shishuo-jianshu-yujiaxi-local",
        "source_layer": row.get("layer"),
        "attribution": row.get("attribution"),
        "quoted_source": quoted_source,
        "transmission_status": source_transmission(row, quoted_source),
        "source_locator": row.get("source_locator", {}),
        "evidence_hash": evidence_hash(row),
        "evidence_excerpt": excerpt(row),
        "assertion_class": _source_assertion_class(row, quoted_source, is_citation),
        "explicit_assertion": modality == "explicit",
        "extracted_proposition": None,
        "subject_endpoint": None,
        "predicate": None,
        "fact_type": None,
        "object_endpoint": None,
        "modality": modality,
        "identity_resolution_state": "not_resolved_for_structured_fact",
        "ontology_resolution_state": "not_resolved_for_structured_fact",
        "review_status": status,
        "review_reason": reason,
        "materialization_status": "not_materialized",
        "produced_fact_ids": [],
        "corroboration_fact_ids": [],
        "related_x1_2r_review_item_ids": _related_candidates(assertion_id, fact_rows),
        "source_assertion_record": True,
        "derived_from_source_assertion": False,
        "no_ml_write_back": True,
    }


def _citation_only(row: Mapping[str, Any], quoted_source: str | None) -> bool:
    text = " ".join(str(row.get("text", "")).split())
    if not quoted_source or len(text) > 85:
        return False
    return not any(token in text for token in ("人物", "字", "父", "母", "子", "為", "是", "遷", "卒", "曰：", "云："))


def _accept_unit(
    base: dict[str, Any],
    *,
    unit_id: str,
    proposition: str,
    subject: Mapping[str, Any],
    predicate: str,
    fact_type: str,
    object_endpoint: Mapping[str, Any],
    review_reason: str,
    materialization_status: str = "materialized",
    parent_assertion_id: str | None = None,
) -> dict[str, Any]:
    row = dict(base)
    row.update(
        {
            "review_item_id": stable_id("x1-2rf-review", base["source_assertion_id"], unit_id),
            "assertion_unit_id": unit_id,
            "derived_from_source_assertion": unit_id != "block",
            "parent_assertion_id": parent_assertion_id,
            "extracted_proposition": proposition,
            "subject_endpoint": dict(subject),
            "predicate": predicate,
            "fact_type": fact_type,
            "object_endpoint": dict(object_endpoint),
            "identity_resolution_state": "resolved_existing_canonical_endpoint",
            "ontology_resolution_state": "resolved_existing_h0c_ontology",
            "review_status": "accepted",
            "review_reason": review_reason,
            "materialization_status": materialization_status,
            "no_ml_write_back": True,
        }
    )
    if parent_assertion_id is not None:
        row["source_assertion_record"] = False
    row["assertion_class"] = "B_named_quotation" if row.get("quoted_source") else "A_explicit_historical_assertion"
    row["modality"] = "explicit"
    row["explicit_assertion"] = True
    return row


def _make_review_records(assertions: list[dict[str, Any]], fact_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    citations = load_citations()
    base_rows = [_base_review(row, citations, fact_rows) for row in assertions]
    by_assertion = {row["source_assertion_id"]: row for row in base_rows}
    people = read("data/people.json").get("people", [])
    people_by_id = {str(row["person_id"]): row for row in people}
    offices = offices_by_name()
    locations = locations_by_name()

    # The proposition is explicitly stated in a letter quoted by Liu.  The
    # existing person and H0C office endpoints are stable; no date is guessed.
    office_061 = offices["州從事"]
    row = by_assertion[SOURCE_ASSERTION_IDS["office_habits_letter"]]
    by_assertion[SOURCE_ASSERTION_IDS["office_habits_letter"]] = _accept_unit(
        row,
        unit_id="習鑿齒-荊州從事",
        proposition="習鑿齒明言自己為荊州從事。",
        subject={"entity_type": "Person", "entity_id": "person-061", "surface": "鑿齒", "resolution_basis": "explicit_named_person_in_liu_annotation"},
        predicate="held_office",
        fact_type="office_tenure",
        object_endpoint={"entity_type": "Office", "entity_id": office_061["office_id"], "surface": "荊州從事", "resolution_basis": "existing_H0C_Office_alias"},
        review_reason="The Liu annotation explicitly quotes the named person's own letter and the office maps to the existing H0C 州從事 entity; chronology remains unknown.",
    )

    # The longer 續晉陽秋 block supplies independent corroborating support
    # for the same semantic office fact, but must not create a duplicate.
    row = by_assertion[SOURCE_ASSERTION_IDS["office_history_named_source"]]
    by_assertion[SOURCE_ASSERTION_IDS["office_history_named_source"]] = _accept_unit(
        row,
        unit_id="習鑿齒-州從事-corroboration",
        proposition="續晉陽秋記習鑿齒自州從事遷治中。",
        subject={"entity_type": "Person", "entity_id": "person-061", "surface": "鑿齒", "resolution_basis": "explicit_named_person_in_quoted_source"},
        predicate="held_office",
        fact_type="office_tenure",
        object_endpoint={"entity_type": "Office", "entity_id": office_061["office_id"], "surface": "州從事", "resolution_basis": "existing_H0C_Office_alias"},
        review_reason="The named quoted source explicitly repeats the same office proposition; it is recorded as corroboration rather than a duplicate fact.",
        materialization_status="corroboration_only",
    )

    office_065 = offices["長史"]
    row = by_assertion[SOURCE_ASSERTION_IDS["office_history_meng_jia"]]
    by_assertion[SOURCE_ASSERTION_IDS["office_history_meng_jia"]] = _accept_unit(
        row,
        unit_id="孟嘉-遷長史",
        proposition="孟嘉後遷長史。",
        subject={"entity_type": "Person", "entity_id": "person-065", "surface": "嘉", "resolution_basis": "story_local_reviewed_person_surface"},
        predicate="held_office",
        fact_type="office_tenure",
        object_endpoint={"entity_type": "Office", "entity_id": office_065["office_id"], "surface": "長史", "resolution_basis": "existing_H0C_Office_canonical_name"},
        review_reason="The Liu annotation explicitly states 遷長史 for the already-resolved Story person 孟嘉; no chronology is inferred.",
    )

    # This parent block mixes explicit quotations with disputed commentary.
    # Keep the block non-canonical and review only the endpoint-safe quoted
    # clause as a derived assertion unit.
    parent_id = SOURCE_ASSERTION_IDS["danyang_quoted_record"]
    parent = by_assertion[parent_id]
    parent["review_reason"] = "The parent block contains both explicit quotations and disputed/conjectural commentary; only a separately reviewed quoted clause may be materialized."
    parent["review_status"] = "scholarly_assertion_only"
    parent["materialization_status"] = "unit_extracted"
    loc = locations["丹陽"]
    child = _accept_unit(
        parent,
        unit_id="王導-丹陽太守",
        proposition="王導被明確稱為丹陽太守。",
        subject={"entity_type": "Person", "entity_id": "person-003", "surface": "王導", "resolution_basis": "explicit_named_person_in_quoted_source"},
        predicate="held_office_at",
        fact_type="location_fact",
        object_endpoint={"entity_type": "Location", "entity_id": loc["location_id"], "surface": "丹陽", "resolution_basis": "existing_H0C_Location_canonical_name"},
        review_reason="The quoted 王隱晉書 clause explicitly names 王導 and 丹陽; the later 疑是 conjecture remains outside fact materialization.",
        parent_assertion_id=parent_id,
    )
    child["object_endpoint"]["office_title_surface"] = "丹陽太守"
    child["parent_modality"] = parent.get("modality")
    child["assertion_class"] = "B_named_quotation"
    child["modality"] = "explicit"
    child["explicit_assertion"] = True

    records = list(by_assertion.values())
    records.append(child)
    return sorted(records, key=lambda row: (str(row.get("story_id")), str(row.get("source_assertion_id")), str(row.get("assertion_unit_id")))), by_assertion


def _fact_evidence(assertion_ids: list[str], assertion_index: Mapping[str, Mapping[str, Any]], review_by_key: Mapping[tuple[str, str], Mapping[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    evidence_ids: list[str] = []
    refs: list[dict[str, Any]] = []
    for assertion_id in assertion_ids:
        source = assertion_index[assertion_id]
        accepted_rows = [row for (aid, _), row in review_by_key.items() if aid == assertion_id and row.get("review_status") == "accepted"]
        evidence_ids.append(assertion_id)
        refs.append(
            {
                "assertion_id": assertion_id,
                "evidence_hash": evidence_hash(source),
                "source_layer": source.get("layer"),
                "attribution": source.get("attribution"),
                "quoted_source": accepted_rows[0].get("quoted_source") if accepted_rows else None,
                "transmission_status": accepted_rows[0].get("transmission_status") if accepted_rows else source_transmission(source, None),
                "source_locator": source.get("source_locator", {}),
                "valid": True,
            }
        )
    return sorted(set(evidence_ids)), sorted(refs, key=lambda row: row["assertion_id"])


def _build_facts(review_records: list[dict[str, Any]], assertions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    assertion_index = _assertion_index(assertions)
    review_by_key = {(str(row["source_assertion_id"]), str(row["assertion_unit_id"])): row for row in review_records}
    existing = existing_semantic_keys()
    facts: list[dict[str, Any]] = []
    corroboration: list[dict[str, Any]] = []
    fact_specs = [
        {
            "source_assertion_ids": [SOURCE_ASSERTION_IDS["office_habits_letter"], SOURCE_ASSERTION_IDS["office_history_named_source"]],
            "fact_type": "office_tenure",
            "semantic_key": "office_tenure|person-061|office-h0c-004",
            "subject_ids": ["person-061"],
            "story_id": "04-wenxue-080",
            "office_id": "office-h0c-004",
            "office_title": "州從事",
            "predicate": "held_office",
        },
        {
            "source_assertion_ids": [SOURCE_ASSERTION_IDS["office_history_meng_jia"]],
            "fact_type": "office_tenure",
            "semantic_key": "office_tenure|person-065|office-h0c-017",
            "subject_ids": ["person-065"],
            "story_id": "07-shijian-016",
            "office_id": "office-h0c-017",
            "office_title": "長史",
            "predicate": "held_office",
        },
        {
            "source_assertion_ids": [SOURCE_ASSERTION_IDS["danyang_quoted_record"]],
            "fact_type": "location_fact",
            "semantic_key": "location_fact|person|person-003|location-h0c-002|held_office_at",
            "subject_ids": ["person-003"],
            "story_id": "26-qingdi-004",
            "location_id": "location-h0c-002",
            "location_role": "held_office_at",
            "office_title_surface": "丹陽太守",
            "predicate": "held_office_at",
        },
    ]
    for spec in fact_specs:
        key = str(spec["semantic_key"])
        fact_id = stable_id("x1-2rf-fact", key)
        if key in existing:
            corroboration.append(
                {
                    "corroboration_id": stable_id("x1-2rf-corroboration", key, *spec["source_assertion_ids"]),
                    "semantic_key": key,
                    "target_scope": "pre_existing_canonical_fact",
                    "target_fact_id": None,
                    "source_assertion_ids": spec["source_assertion_ids"],
                    "status": "equivalent_fact_already_exists",
                    "review_status": "reviewed",
                    "notes": "The Jianshu evidence is retained without duplicating an existing fact.",
                }
            )
            continue
        evidence_ids, evidence_refs = _fact_evidence(spec["source_assertion_ids"], assertion_index, review_by_key)
        primary = next(
            row for row in review_records
            if row.get("source_assertion_id") == spec["source_assertion_ids"][0] and row.get("review_status") == "accepted"
        )
        fact = {
            "fact_id": fact_id,
            "fact_key": key,
            "fact_type": spec["fact_type"],
            "predicate": spec["predicate"],
            "subject_ids": spec["subject_ids"],
            "story_ids": [spec["story_id"]],
            "evidence_ids": evidence_ids,
            "evidence_refs": evidence_refs,
            "provenance_refs": [
                {
                    "review_item_id": primary["review_item_id"],
                    "source_assertion_ids": spec["source_assertion_ids"],
                    "source_layer": primary.get("source_layer"),
                    "source_family": "shishuo-jianshu-yujiaxi-local",
                    "attribution": primary.get("attribution"),
                    "quoted_source": primary.get("quoted_source"),
                    "transmission_status": primary.get("transmission_status"),
                    "source_locator": primary.get("source_locator"),
                }
            ],
            "review_status": "reviewed",
            "review_decision": "accepted",
            "assertion_status": "attested",
            "modality": "explicit",
            "source_assertion_modality": primary.get("modality"),
            "parent_assertion_modality": primary.get("parent_modality"),
            "temporal_precision": "unknown",
            "start_year_ce": None,
            "end_year_ce": None,
            "source_path": str(S1_ASSERTIONS_PATH),
            "source_family": "shishuo-jianshu-yujiaxi-local",
            "source_layer": primary.get("source_layer"),
            "attribution": primary.get("attribution"),
            "quoted_source": primary.get("quoted_source"),
            "transmission_status": primary.get("transmission_status"),
            "derivation_basis": "x1_2rf_explicit_endpoint_safe_assertion",
            "materialization_epoch": EPOCH,
            "canonical_scope": "x1-2rf-historical-fact-extension",
            "research_selection_provenance": {
                "selection_epoch": "X1.1",
                "selection_mode": _selection_mode(spec["story_id"]),
                "selection_rank": _selection_rank(spec["story_id"]),
            },
            "no_ml_write_back": True,
            "protected_h0c_hg0_ml0": True,
        }
        if spec["fact_type"] == "office_tenure":
            fact.update(
                {
                    "person_id": spec["subject_ids"][0],
                    "office_id": spec["office_id"],
                    "office_title": spec["office_title"],
                    "tenure_id": stable_id("x1-2rf-tenure", key),
                    "location_id": None,
                    "regime_id": None,
                }
            )
        else:
            fact.update(
                {
                    "subject_type": "person",
                    "subject_id": spec["subject_ids"][0],
                    "location_id": spec["location_id"],
                    "location_role": spec["location_role"],
                    "office_id": None,
                    "office_title_surface": spec["office_title_surface"],
                    "office_tenure_id": None,
                }
            )
        facts.append(fact)

    # The second assertion in the first fact is accepted as corroborating
    # support, not as a second semantic edge/fact.
    first_fact = next((row for row in facts if row["fact_key"] == "office_tenure|person-061|office-h0c-004"), None)
    if first_fact:
        corroboration.append(
            {
                "corroboration_id": stable_id("x1-2rf-corroboration", SOURCE_ASSERTION_IDS["office_history_named_source"], first_fact["fact_id"]),
                "semantic_key": first_fact["fact_key"],
                "target_scope": "same_epoch_extension_fact",
                "target_fact_id": first_fact["fact_id"],
                "source_assertion_ids": [SOURCE_ASSERTION_IDS["office_history_named_source"]],
                "status": "accepted_support_without_duplicate_fact",
                "review_status": "reviewed",
                "notes": "The named quoted source supports the materialized office proposition; it does not create a parallel fact.",
            }
        )
    return sorted(facts, key=lambda row: str(row["fact_id"])), sorted(corroboration, key=lambda row: str(row["corroboration_id"]))


_SELECTION_CACHE: dict[str, dict[str, Any]] | None = None


def _selection_mode(story_id: str) -> str | None:
    global _SELECTION_CACHE
    if _SELECTION_CACHE is None:
        _SELECTION_CACHE = {str(row["story_id"]): dict(row) for row in read("data/derived/x1-1-selection-manifest.json").get("records", [])}
    return _SELECTION_CACHE.get(story_id, {}).get("selection_mode")


def _selection_rank(story_id: str) -> int | None:
    global _SELECTION_CACHE
    if _SELECTION_CACHE is None:
        _SELECTION_CACHE = {str(row["story_id"]): dict(row) for row in read("data/derived/x1-1-selection-manifest.json").get("records", [])}
    value = _SELECTION_CACHE.get(story_id, {}).get("global_selection_rank", _SELECTION_CACHE.get(story_id, {}).get("selection_rank"))
    return int(value) if value is not None else None


def _original_candidate_review(
    reopened: list[dict[str, Any]],
    review_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in review_records:
        by_source[str(row.get("source_assertion_id"))].append(row)
    output: list[dict[str, Any]] = []
    for row in reopened:
        assertion_ids = sorted(row.get("new_evidence_assertion_ids") or [])
        related = [candidate for assertion_id in assertion_ids for candidate in by_source.get(assertion_id, [])]
        accepted_new = [candidate for candidate in related if candidate.get("review_status") == "accepted" and candidate.get("materialization_status") == "materialized"]
        corroborated = [candidate for candidate in related if candidate.get("review_status") == "accepted" and candidate.get("materialization_status") == "corroboration_only"]
        scholarly = [candidate for candidate in related if candidate.get("review_status") == "scholarly_assertion_only"]
        citation = [candidate for candidate in related if candidate.get("review_status") == "citation_only"]
        output.append(
            {
                "review_item_id": stable_id("x1-2rf-original", row["review_item_id"]),
                "source_x1_2r_review_item_id": row["review_item_id"],
                "source_candidate_id": row.get("source_candidate_id"),
                "story_id": row.get("story_id"),
                "fact_layer": row.get("fact_layer"),
                "selection_provenance": row.get("selection_provenance", {}),
                "reopen_status": row.get("reopen_status"),
                "original_candidate_outcome": {
                    "review_status": row.get("review_status"),
                    "materialization_status": row.get("materialization_status"),
                    "review_reason": row.get("review_reason"),
                    "preserved_without_mutation": True,
                },
                "new_source_assertion_ids": assertion_ids,
                "independent_assertion_review_ids": sorted(candidate["review_item_id"] for candidate in related),
                "independent_assertion_yield": {
                    "new_fact_accepted": len(accepted_new),
                    "corroboration_only": len(corroborated),
                    "scholarly_assertion_only": len(scholarly),
                    "citation_only": len(citation),
                    "unresolved_or_other": len(related) - len(accepted_new) - len(corroborated) - len(scholarly) - len(citation),
                    "produced_fact_ids": sorted(fact_id for candidate in accepted_new for fact_id in candidate.get("produced_fact_ids", [])),
                },
                "policy_effect": "original_candidate_evaluated_separately_from_independent_assertion_units",
                "review_status": "reviewed",
                "no_candidate_mutation": True,
            }
        )
    return sorted(output, key=lambda row: str(row["source_x1_2r_review_item_id"]))


def _attach_fact_ids(review_records: list[dict[str, Any]], facts: list[dict[str, Any]], corroboration: list[dict[str, Any]]) -> None:
    fact_by_key = {row["fact_key"]: row for row in facts}
    for row in review_records:
        if row.get("materialization_status") not in {"materialized", "corroboration_only"}:
            continue
        if row.get("source_assertion_id") == SOURCE_ASSERTION_IDS["office_habits_letter"]:
            fact = fact_by_key.get("office_tenure|person-061|office-h0c-004")
        elif row.get("source_assertion_id") == SOURCE_ASSERTION_IDS["office_history_named_source"]:
            fact = fact_by_key.get("office_tenure|person-061|office-h0c-004")
        elif row.get("source_assertion_id") == SOURCE_ASSERTION_IDS["office_history_meng_jia"]:
            fact = fact_by_key.get("office_tenure|person-065|office-h0c-017")
        elif row.get("source_assertion_id") == SOURCE_ASSERTION_IDS["danyang_quoted_record"] and row.get("assertion_unit_id") != "block":
            fact = fact_by_key.get("location_fact|person|person-003|location-h0c-002|held_office_at")
        else:
            fact = None
        if fact:
            if row.get("materialization_status") == "materialized":
                row["produced_fact_ids"] = [fact["fact_id"]]
            else:
                row["corroboration_fact_ids"] = [fact["fact_id"]]
    for row in facts:
        row["evidence_ids"] = sorted(set(row.get("evidence_ids", [])))


def _scholarly_rows(review_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in review_records:
        if row.get("review_status") not in {"scholarly_assertion_only", "citation_only"}:
            continue
        rows.append(
            {
                "review_item_id": row["review_item_id"],
                "source_assertion_id": row["source_assertion_id"],
                "assertion_unit_id": row["assertion_unit_id"],
                "story_id": row["story_id"],
                "source_family": row.get("source_family"),
                "source_layer": row["source_layer"],
                "attribution": row["attribution"],
                "quoted_source": row["quoted_source"],
                "transmission_status": row["transmission_status"],
                "modality": row["modality"],
                "review_status": row["review_status"],
                "materialization_status": row.get("materialization_status", "not_materialized"),
                "source_locator": row["source_locator"],
                "evidence_hash": row["evidence_hash"],
                "evidence_excerpt": row["evidence_excerpt"],
                "preserved_as_noncanonical": True,
                "review_reason": row["review_reason"],
            }
        )
    return sorted(rows, key=lambda row: (str(row["story_id"]), str(row["source_assertion_id"]), str(row["assertion_unit_id"])))


def build() -> None:
    selected = selected_ids()
    if len(selected) != 20 or len(set(selected)) != 20:
        raise ValueError(f"X1.2R-F requires exactly 20 unique frozen Stories, got {len(selected)}")
    assertions = load_assertions()
    assertion_index = _assertion_index(assertions)
    if {row["story_id"] for row in assertions} - set(selected):
        raise ValueError("assertion scope escaped the frozen 20 Stories")
    if len(assertions) != 132:
        raise ValueError(f"expected the current 20-Story assertion scope to contain 132 records, got {len(assertions)}")
    fact_rows = load_x1_2r_facts()
    reopened = reopened_x1_2r_facts()
    if len(reopened) != 34:
        raise ValueError(f"expected 34 X1.2R reopened facts, got {len(reopened)}")
    review_records, _ = _make_review_records(assertions, fact_rows)
    facts, corroboration = _build_facts(review_records, assertions)
    _attach_fact_ids(review_records, facts, corroboration)
    original_review = _original_candidate_review(reopened, review_records)
    scholarly = _scholarly_rows(review_records)

    hashes = input_hashes()
    protected = protected_hashes()
    policy = {
        "schema": 1,
        "stage": "x1-2rf-policy",
        "policy_version": "explicit-transmitted-assertion-v1",
        "automatic_acceptance": False,
        "materialization_rule": "An explicit, endpoint-resolved, semantically clear, non-modal assertion may be reviewed and materialized as an extension fact; Jianshu material never establishes a fact automatically.",
        "required_conditions": [
            "assertion_explicit",
            "semantic_proposition_clear",
            "endpoint_identity_safe",
            "existing_h0c_ontology_relation",
            "non_modal_or_uncertainty_preserved",
            "no_meaningful_textual_or_glyph_ambiguity",
            "evidence_locator_and_hash_preserved",
            "transmission_path_preserved",
            "explicit_review_acceptance",
            "no_duplicate_canonical_fact",
        ],
        "transmission_statuses": [
            "direct_jianshu_assertion",
            "liu_annotation_assertion",
            "quoted_via_liu_annotation",
            "quoted_via_jianshu_note",
            "scholarly_assertion",
            "citation_only",
        ],
        "modal_values_not_certain_fact": ["疑", "或", "恐", "未詳", "未審", "當作", "當是", "蓋", "似", "probable", "possible", "disputed", "unknown"],
        "review_states": sorted(ALLOWED_REVIEW_STATES),
        "scope": {
            "selected_story_count": len(selected),
            "selected_story_ids": selected,
            "x1_2r_reopened_fact_count": len(reopened),
            "new_story_selection_performed": False,
            "new_story_materialization": False,
            "new_person_materialization": False,
            "citation_corpus_ingestion": False,
        },
        "ontology_change_count": 0,
        "source_hashes": hashes,
        "protected_hashes": protected,
        "no_ml_write_back": True,
    }

    # Update source review rows with produced fact IDs after the fact pass.
    assertion_review = {
        "schema": 1,
        "stage": "x1-2rf-assertion-review",
        "review_epoch": EPOCH,
        "scope": {
            "selected_story_ids": selected,
            "source_assertion_count": len(assertions),
            "review_record_count": len(review_records),
            "new_story_selection_performed": False,
        },
        "source_hashes": hashes,
        "records": review_records,
        "counts": {
            "source_assertions_reviewed": len(assertions),
            "review_records": len(review_records),
            "explicit_source_assertions": sum(1 for row in assertions if row.get("modality") == "explicit"),
            "accepted_review_records": sum(1 for row in review_records if row.get("review_status") == "accepted"),
            "accepted_materialized_assertion_units": sum(1 for row in review_records if row.get("materialization_status") == "materialized"),
            "corroboration_only_assertion_units": sum(1 for row in review_records if row.get("materialization_status") == "corroboration_only"),
            "unresolved": sum(1 for row in review_records if row.get("review_status") == "unresolved"),
            "scholarly_assertion_only": sum(1 for row in review_records if row.get("review_status") == "scholarly_assertion_only"),
            "citation_only": sum(1 for row in review_records if row.get("review_status") == "citation_only"),
            "rejected": sum(1 for row in review_records if row.get("review_status") == "rejected"),
        },
    }

    original_artifact = {
        "schema": 1,
        "stage": "x1-2rf-original-candidate-review",
        "review_epoch": EPOCH,
        "scope": {"selected_story_ids": selected, "reopened_candidate_count": len(reopened), "new_story_selection_performed": False},
        "source_hashes": hashes,
        "records": original_review,
        "counts": {
            "original_candidates_reviewed": len(original_review),
            "accepted": sum(1 for row in original_review if row["original_candidate_outcome"]["review_status"] == "accepted"),
            "unresolved": sum(1 for row in original_review if row["original_candidate_outcome"]["review_status"] == "unresolved"),
            "rejected": sum(1 for row in original_review if row["original_candidate_outcome"]["review_status"] == "rejected"),
            "independent_new_fact_units": sum(row["independent_assertion_yield"]["new_fact_accepted"] for row in original_review),
            "independent_corroboration_units": sum(row["independent_assertion_yield"]["corroboration_only"] for row in original_review),
        },
    }

    facts_artifact = {
        "schema": 1,
        "stage": "x1-2rf-materialized-facts",
        "materialization_epoch": EPOCH,
        "canonical_scope": "x1-2rf-historical-fact-extension",
        "source_hashes": hashes,
        "protected_input_hashes": protected,
        "facts": facts,
        "counts": {
            "facts_added": len(facts),
            "entities_added": 0,
            "persons_added": 0,
            "stories_added_to_production_scope": 0,
            "by_fact_type": dict(sorted(Counter(row["fact_type"] for row in facts).items())),
            "by_layer": dict(sorted(Counter("office" if row["fact_type"] == "office_tenure" else "geographic" for row in facts).items())),
        },
        "preservation": {
            "h0c_facts_unchanged": True,
            "hg0_unchanged": True,
            "ml0_unchanged": True,
            "x1_2a_extension_unchanged": True,
            "x1_2r_extension_unchanged": True,
            "no_ml_write_back": True,
        },
    }

    corroboration_artifact = {
        "schema": 1,
        "stage": "x1-2rf-corroboration",
        "review_epoch": EPOCH,
        "source_hashes": hashes,
        "records": corroboration,
        "counts": {
            "records": len(corroboration),
            "pre_existing_canonical_facts_corrobated": sum(1 for row in corroboration if row["target_scope"] == "pre_existing_canonical_fact"),
            "same_epoch_support_records": sum(1 for row in corroboration if row["target_scope"] == "same_epoch_extension_fact"),
        },
        "policy": "Equivalent semantic facts are never duplicated; supplementary Jianshu support is kept as a provenance record.",
    }

    scholarly_artifact = {
        "schema": 1,
        "stage": "x1-2rf-scholarly-assertions",
        "review_epoch": EPOCH,
        "source_hashes": hashes,
        "records": scholarly,
        "counts": dict(sorted(Counter(row["review_status"] for row in scholarly).items())),
        "policy": "Scholarly interpretation, dispute, collation and citation leads remain useful non-canonical evidence.",
    }

    accepted_fact_layers = Counter("office" if row["fact_type"] == "office_tenure" else "geographic" for row in facts)
    transmission_all = Counter(row.get("transmission_status") for row in review_records)
    transmission_accepted = Counter(row.get("transmission_status") for row in review_records if row.get("materialization_status") == "materialized")
    source_review_by_id = {
        str(row["source_assertion_id"]): row
        for row in review_records
        if row.get("source_assertion_record") is True
    }
    independent_fact_ids = {
        str(fact["fact_id"])
        for fact in facts
        if any(
            not source_review_by_id.get(str(assertion_id), {}).get("related_x1_2r_review_item_ids")
            for assertion_id in fact.get("evidence_ids", [])
        )
    }
    summary = {
        "schema": 1,
        "stage": "x1-2rf-summary",
        "review_epoch": EPOCH,
        "scope": {
            "frozen_stories_reviewed": len(selected),
            "source_assertions_reviewed": len(assertions),
            "original_reopened_candidates_reviewed": len(reopened),
            "new_story_selection_performed": False,
            "stories_added_to_production": 0,
            "persons_added": 0,
        },
        "assertions": {
            "explicit": sum(1 for row in assertions if row.get("modality") == "explicit"),
            "accepted_materialized_units": len(facts),
            "existing_facts_corroborated": corroboration_artifact["counts"]["pre_existing_canonical_facts_corrobated"],
            "same_epoch_corroboration": corroboration_artifact["counts"]["same_epoch_support_records"],
            "unresolved": assertion_review["counts"]["unresolved"],
            "scholarly_assertion_only": assertion_review["counts"]["scholarly_assertion_only"],
            "citation_only": assertion_review["counts"]["citation_only"],
            "rejected": assertion_review["counts"]["rejected"],
        },
        "original_34_candidates": original_artifact["counts"],
        "independent_facts_outside_original_candidate_semantics": len(independent_fact_ids),
        "fact_yield_by_layer": {
            "family": 0,
            "office": accepted_fact_layers.get("office", 0),
            "event": 0,
            "geographic": accepted_fact_layers.get("geographic", 0),
            "temporal": 0,
            "service_political": 0,
            "identity_alias": 0,
        },
        "transmission_breakdown": {
            "all_review_records": dict(sorted((str(key), value) for key, value in transmission_all.items())),
            "accepted_new_facts": dict(sorted((str(key), value) for key, value in transmission_accepted.items())),
        },
        "canonical_delta": {
            "stories": 0,
            "persons": 0,
            "facts": len(facts),
            "entities": 0,
            "destination": "x1-2rf-historical-fact-extension",
        },
        "protection": {
            "h0c_hg0_ml0_protected": True,
            "x1_2a_extension_protected": True,
            "x1_2r_extension_protected": True,
            "x1_2r_selection_protected": True,
            "no_ml_write_back": True,
            "no_ontology_change": True,
        },
        "decision_classification": "policy_correction_materially_increases_fact_yield",
        "remaining_blockers": [
            "Most Jianshu blocks remain multi-proposition, modal, contextual, or endpoint-unsafe.",
            "The three X1.2R identity candidates remain unresolved.",
            "Cited historical works remain citation leads and were not ingested or independently verified.",
            "The accepted extension has not yet been projected into a rebuilt HG1.1 graph.",
        ],
        "stop_boundary": ["X1.2B", "S2", "HG1.1", "ML1.1", "ER2"],
        "source_hashes": hashes,
        "protected_hashes": protected,
    }

    next_step = {
        "schema": 1,
        "stage": "x1-2rf-next-step-recommendation",
        "review_epoch": EPOCH,
        "policy_outcome": summary["decision_classification"],
        "recommendation": "defer_x1_2b_until_hg1_1_consumes_the_extension",
        "x1_2b_may_proceed_now": False,
        "reason": "The policy correction produced a non-zero, provenance-preserving extension, but Story selection should wait until a future HG1.1 graph rebuild measures its structural effect. No additional broad evidence sweep is required to justify the three accepted facts.",
        "hg1_1_ready_recommendation": True,
        "hg1_1_reason": "Three reviewed extension facts plus one same-semantic corroboration are a material canonical delta while Stories, Persons, and HG0 remain protected.",
        "recommended_follow_up": [
            "Run HG1.1 using x1-2rf-materialized-facts as an extension input.",
            "Keep the 34 original candidate outcomes separate from independent assertion yield.",
            "Revisit endpoint-unsafe and modal cases only when a qualified identity/source route becomes available.",
        ],
        "source_hashes": hashes,
        "no_new_story_selection": True,
        "no_new_person_expansion": True,
    }

    write(POLICY_PATH, policy)
    write(ASSERTION_REVIEW_PATH, assertion_review)
    write(ORIGINAL_REVIEW_PATH, original_artifact)
    write(MATERIALIZED_FACTS_PATH, facts_artifact)
    write(CORROBORATION_PATH, corroboration_artifact)
    write(SCHOLARLY_ASSERTIONS_PATH, scholarly_artifact)
    write(SUMMARY_PATH, summary)
    write(NEXT_STEP_PATH, next_step)
    print(json.dumps({"stage": EPOCH, "facts": len(facts), "assertions": len(assertions), "original_reopened": len(reopened)}, ensure_ascii=False, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Build deterministically; validation is a separate command.")
    parser.parse_args()
    build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
