#!/usr/bin/env python3
"""Validate the X1.2A review and controlled-materialization boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

try:
    from scripts.x1_2a_common import (
        BIAS_PATH,
        CANONICAL_FACTS_PATH,
        CONFLICT_PATH,
        COUNTER_MODEL_PATH,
        FACT_REVIEW_PATH,
        GAP_PATH,
        MATERIALIZATION_PATH,
        NEXT_EPOCH_PATH,
        ONTOLOGY_REVIEW_PATH,
        PERSON_REVIEW_PATH,
        REALIZED_YIELD_PATH,
        REVIEW_MANIFEST_PATH,
        STORY_REVIEW_PATH,
        SUMMARY_PATH,
        X1_1_INPUTS,
        all_production_ids,
        evidence_by_id,
        load_x1_1,
        protected_hashes,
        read,
        sha256_file,
        protected_hashes_match,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from x1_2a_common import (
        BIAS_PATH,
        CANONICAL_FACTS_PATH,
        CONFLICT_PATH,
        COUNTER_MODEL_PATH,
        FACT_REVIEW_PATH,
        GAP_PATH,
        MATERIALIZATION_PATH,
        NEXT_EPOCH_PATH,
        ONTOLOGY_REVIEW_PATH,
        PERSON_REVIEW_PATH,
        REALIZED_YIELD_PATH,
        REVIEW_MANIFEST_PATH,
        STORY_REVIEW_PATH,
        SUMMARY_PATH,
        X1_1_INPUTS,
        all_production_ids,
        evidence_by_id,
        load_x1_1,
        protected_hashes,
        read,
        sha256_file,
        protected_hashes_match,
    )


ROOT = Path(__file__).resolve().parents[1]
STATES = {"accepted", "unresolved", "rejected"}


def contains_forbidden_ml_key(value: Any) -> bool:
    forbidden = {"model_score", "model_rank", "selection_score", "embedding", "prediction"}
    if isinstance(value, Mapping):
        return any(str(key) in forbidden or contains_forbidden_ml_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(contains_forbidden_ml_key(item) for item in value)
    return False


def validate() -> list[str]:
    errors: list[str] = []
    try:
        load_x1_1()
        review = read(REVIEW_MANIFEST_PATH)
        materialization = read(MATERIALIZATION_PATH)
        extension = read(CANONICAL_FACTS_PATH)
        story_review = read(STORY_REVIEW_PATH)
        person_review = read(PERSON_REVIEW_PATH)
        fact_review = read(FACT_REVIEW_PATH)
        ontology_review = read(ONTOLOGY_REVIEW_PATH)
        conflict = read(CONFLICT_PATH)
        realized = read(REALIZED_YIELD_PATH)
        counter = read(COUNTER_MODEL_PATH)
        bias = read(BIAS_PATH)
        gaps = read(GAP_PATH)
        recommendation = read(NEXT_EPOCH_PATH)
        summary = read(SUMMARY_PATH)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return [f"X1.2A artifacts cannot be read: {exc}"]

    if review.get("stage") != "x1-2a-review-manifest":
        errors.append("review manifest stage is invalid")
    if review.get("selection_frozen_before_review") is not True:
        errors.append("selection freeze is not recorded")
    if review.get("review_policy", {}).get("top_level_states") != ["accepted", "unresolved", "rejected"]:
        errors.append("review state policy is incomplete")
    expected_hashes = {name: sha256_file(path) for name, path in X1_1_INPUTS.items()}
    if review.get("source_hashes", {}).get("x1_1") != expected_hashes:
        errors.append("X1.1 input hash bundle changed")
    if not protected_hashes_match(review.get("source_hashes", {}).get("protected", {}), protected_hashes()):
        errors.append("protected input hash bundle changed")

    stories = review.get("story_reviews", [])
    persons = review.get("person_reviews", [])
    facts = review.get("fact_reviews", [])
    ontology = review.get("ontology_gap_reviews", [])
    for label, rows, expected in (("Stories", stories, 20), ("Persons", persons, 8), ("facts", facts, 88), ("ontology", ontology, 7)):
        if len(rows) != expected:
            errors.append(f"{label} review count is {len(rows)}, expected {expected}")
        ids = [row.get("review_item_id") for row in rows]
        if len(ids) != len(set(ids)):
            errors.append(f"duplicate {label} review IDs")
        for row in rows:
            if row.get("review_status") not in STATES:
                errors.append(f"{label} item has invalid review state: {row.get('review_item_id')}")
            if not row.get("review_reason"):
                errors.append(f"{label} item lacks review reason: {row.get('review_item_id')}")
            if row.get("review_status") == "accepted" and not row.get("evidence_ids") and label != "ontology":
                errors.append(f"accepted {label} item lacks evidence: {row.get('review_item_id')}")
    if review.get("counts", {}).get("fact_candidate_count") != 88:
        errors.append("fact candidate count is not 88")
    if review.get("counts", {}).get("person_identity_candidate_count") != 8:
        errors.append("identity candidate count is not 8")

    evidence_ids = set(evidence_by_id())
    for row in stories + persons + facts + ontology:
        missing = sorted(set(row.get("evidence_ids", [])) - evidence_ids)
        if missing:
            errors.append(f"review item {row.get('review_item_id')} references missing Evidence: {missing}")
    for split_path, split_stage in ((STORY_REVIEW_PATH, "x1-2a-story-review"), (PERSON_REVIEW_PATH, "x1-2a-person-review"), (FACT_REVIEW_PATH, "x1-2a-fact-review"), (ONTOLOGY_REVIEW_PATH, "x1-2a-ontology-gap-review")):
        split = read(split_path)
        if split.get("stage") != split_stage:
            errors.append(f"split artifact stage is invalid: {split_path}")
        if split.get("source_review_manifest_sha256") != sha256_file(REVIEW_MANIFEST_PATH):
            errors.append(f"split artifact is not bound to review manifest: {split_path}")

    people, production_stories = all_production_ids()
    if materialization.get("source_review_manifest_sha256") != sha256_file(REVIEW_MANIFEST_PATH):
        errors.append("materialization is not bound to the review manifest")
    if materialization.get("source_x1_1_hashes") != expected_hashes:
        errors.append("materialization X1.1 hashes changed")
    if not protected_hashes_match(materialization.get("protected_input_hashes", {}), protected_hashes()):
        errors.append("materialization protected hashes changed")
    counts = materialization.get("counts", {})
    if counts.get("stories_added") != 0 or counts.get("persons_added") != 0:
        errors.append("X1.2A added a production Story or Person")
    extension_facts = extension.get("fact_index", [])
    if len(extension_facts) != counts.get("facts_added"):
        errors.append("extension fact count disagrees with materialization manifest")
    if len({row.get("fact_id") for row in extension_facts}) != len(extension_facts):
        errors.append("duplicate canonical extension fact IDs")
    if len({row.get("entity_id") for row in extension.get("entities", [])}) != len(extension.get("entities", [])):
        errors.append("duplicate canonical extension entity IDs")
    accepted_review_ids = {row.get("review_item_id") for row in facts if row.get("review_status") == "accepted"}
    for row in extension_facts:
        if row.get("review_status") != "reviewed" or row.get("assertion_status") != "attested":
            errors.append(f"extension fact is not reviewed/attested: {row.get('fact_id')}")
        if not row.get("evidence_ids") or not set(row.get("evidence_ids", [])) <= evidence_ids:
            errors.append(f"extension fact lacks valid Evidence: {row.get('fact_id')}")
        refs = row.get("provenance_refs", [])
        if not refs or refs[0].get("review_item_id") not in accepted_review_ids:
            errors.append(f"extension fact lacks accepted review provenance: {row.get('fact_id')}")
        if contains_forbidden_ml_key(row):
            errors.append(f"ML score/output leaked into canonical extension fact: {row.get('fact_id')}")
        for story_id in row.get("story_ids", []):
            if story_id not in production_stories and not any(item.get("story_id") == story_id for item in stories):
                errors.append(f"extension fact references unknown Story: {row.get('fact_id')} -> {story_id}")
        if row.get("fact_type") == "event_story_context" and row.get("hard_temporal_eligible") is not False:
            errors.append(f"event context is hard-temporal eligible: {row.get('fact_id')}")
        if row.get("temporal_precision") == "unknown" and any(row.get(key) is not None for key in ("start_year_ce", "end_year_ce", "lower_bound_year_ce", "upper_bound_year_ce")):
            errors.append(f"unknown temporal fact has invented bounds: {row.get('fact_id')}")
    entity_ids = {row.get("entity_id") for row in extension.get("entities", [])}
    if entity_ids & {row.get("entity_id") for row in read("data/annotation/h0c-entity-id-manifest.json").get("records", [])}:
        errors.append("X1.2A extension reused a frozen H0C entity ID")
    if extension.get("canonical_scope") != "x1-2a-canonical-extension":
        errors.append("canonical extension scope is missing")
    if ontology_review.get("ontology_change_count") != 0:
        errors.append("X1.2A changed ontology")

    checks = conflict.get("consistency_checks", {})
    for key, value in checks.items():
        if key in {"duplicate_semantic_facts", "h0a_rewrite_detected"}:
            if value is not False:
                errors.append(f"consistency check failed: {key}")
        elif value is not True:
            errors.append(f"consistency check failed: {key}")
    if conflict.get("conflict_count") != 0:
        errors.append("X1.2A accepted extension contains unresolved conflicts")
    if len(realized.get("channels", [])) != 4:
        errors.append("realized yield does not cover four selection channels")
    if len(counter.get("selected_story_ids", [])) != 3:
        errors.append("counter-model audit does not cover three Stories")
    if len(bias.get("channels", [])) != 4:
        errors.append("bias audit does not cover four selection channels")
    if not gaps.get("records"):
        errors.append("gap audit is empty despite unresolved/rejected candidates")
    ratios = recommendation.get("recommended_x1_2b_ratios", {})
    if set(ratios) != {"graph_guided", "coverage_guided", "stratified_random", "counter_model"} or round(sum(float(value) for value in ratios.values()), 8) != 1.0:
        errors.append("next-epoch ratios are invalid")
    if ratios.get("stratified_random", 0) < 0.10 or ratios.get("counter_model", 0) < 0.10:
        errors.append("next-epoch independent-channel floor was violated")
    if summary.get("stage") != "x1-2a-summary":
        errors.append("summary stage is invalid")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    errors = validate()
    if errors:
        print("X1.2A validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("X1.2A validation passed")


if __name__ == "__main__":
    main()
