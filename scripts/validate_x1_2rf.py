#!/usr/bin/env python3
"""Validate the X1.2R-F extension-only fact materialization boundary."""

from __future__ import annotations

import argparse
import json
from typing import Any, Mapping

try:
    from scripts.x1_2rf_common import (
        ALLOWED_REVIEW_STATES,
        ASSERTION_REVIEW_PATH,
        CORROBORATION_PATH,
        MATERIALIZED_FACTS_PATH,
        NEXT_STEP_PATH,
        ORIGINAL_REVIEW_PATH,
        POLICY_PATH,
        SCHOLARLY_ASSERTIONS_PATH,
        SUMMARY_PATH,
        X1_2R_EXTENSION_PATH,
        X1_2R_IDENTITY_PATH,
        X1_2R_PARTICIPANT_PATH,
        X1_2R_CITATION_PATH,
        X1_2R_BUNDLES_PATH,
        X1_2R_FACT_REVIEW_PATH,
        X1_2R_MATERIALIZATION_PATH,
        X1_2R_SUMMARY_PATH,
        existing_semantic_keys,
        input_hashes,
        load_assertions,
        load_x1_2r_facts,
        protected_hashes,
        read,
        reopened_x1_2r_facts,
        selected_ids,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from x1_2rf_common import (
        ALLOWED_REVIEW_STATES,
        ASSERTION_REVIEW_PATH,
        CORROBORATION_PATH,
        MATERIALIZED_FACTS_PATH,
        NEXT_STEP_PATH,
        ORIGINAL_REVIEW_PATH,
        POLICY_PATH,
        SCHOLARLY_ASSERTIONS_PATH,
        SUMMARY_PATH,
        X1_2R_EXTENSION_PATH,
        X1_2R_IDENTITY_PATH,
        X1_2R_PARTICIPANT_PATH,
        X1_2R_CITATION_PATH,
        X1_2R_BUNDLES_PATH,
        X1_2R_FACT_REVIEW_PATH,
        X1_2R_MATERIALIZATION_PATH,
        X1_2R_SUMMARY_PATH,
        existing_semantic_keys,
        input_hashes,
        load_assertions,
        load_x1_2r_facts,
        protected_hashes,
        read,
        reopened_x1_2r_facts,
        selected_ids,
    )


ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


def _document(path: Any) -> dict[str, Any]:
    value = read(path)
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} is not a JSON object")
    return dict(value)


def _contains_forbidden_model_field(value: Any) -> bool:
    if isinstance(value, Mapping):
        if any(key in value for key in ("model_score", "embedding", "centrality_score")):
            return True
        return any(_contains_forbidden_model_field(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_model_field(item) for item in value)
    return False


def validate() -> list[str]:
    errors: list[str] = []
    try:
        policy = _document(POLICY_PATH)
        assertion_review = _document(ASSERTION_REVIEW_PATH)
        original = _document(ORIGINAL_REVIEW_PATH)
        facts_doc = _document(MATERIALIZED_FACTS_PATH)
        corroboration = _document(CORROBORATION_PATH)
        scholarly = _document(SCHOLARLY_ASSERTIONS_PATH)
        summary = _document(SUMMARY_PATH)
        next_step = _document(NEXT_STEP_PATH)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"X1.2R-F artifacts cannot be read: {exc}"]

    selected = selected_ids()
    selected_set = set(selected)
    assertions = load_assertions()
    assertion_ids = {str(row["assertion_id"]) for row in assertions}
    reopened = reopened_x1_2r_facts()
    reopened_ids = {str(row["review_item_id"]) for row in reopened}

    if len(selected) != 20 or len(selected_set) != 20:
        errors.append("frozen X1.1 Story universe is not exactly 20 unique Stories")
    if policy.get("automatic_acceptance") is not False:
        errors.append("policy accidentally enables automatic acceptance")
    if policy.get("scope", {}).get("selected_story_ids") != selected:
        errors.append("policy Story scope differs from the frozen X1.1 ordering")
    if policy.get("scope", {}).get("x1_2r_reopened_fact_count") != 34:
        errors.append("policy does not record exactly 34 reopened X1.2R cases")
    if policy.get("ontology_change_count") != 0:
        errors.append("X1.2R-F changed ontology")

    expected_inputs = input_hashes()
    if policy.get("source_hashes") != expected_inputs:
        errors.append("X1.2R-F source hashes do not match current protected inputs")
    expected_protected = protected_hashes()
    if policy.get("protected_hashes") != expected_protected:
        errors.append("X1.2R-F protected H0C/HG0/ML0 hashes do not match current files")

    review_records = assertion_review.get("records", [])
    source_rows = [row for row in review_records if row.get("source_assertion_record") is True]
    source_row_ids = {str(row.get("source_assertion_id")) for row in source_rows}
    if source_row_ids != assertion_ids:
        errors.append("assertion review does not cover exactly the frozen 20-Story S1 assertions")
    if {row.get("story_id") for row in source_rows} - selected_set:
        errors.append("assertion review escaped the frozen Story universe")
    for row in review_records:
        if row.get("review_status") not in ALLOWED_REVIEW_STATES:
            errors.append(f"invalid assertion review status: {row.get('review_item_id')}")
        if not row.get("source_locator") or not row.get("evidence_hash"):
            errors.append(f"assertion lacks source locator/hash: {row.get('review_item_id')}")
        if row.get("source_family") != "shishuo-jianshu-yujiaxi-local":
            errors.append(f"assertion lacks the registered Jianshu source family: {row.get('review_item_id')}")
        if row.get("no_ml_write_back") is not True:
            errors.append(f"assertion lacks ML write-back protection: {row.get('review_item_id')}")
        if row.get("materialization_status") == "materialized" and row.get("modality") != "explicit":
            errors.append(f"modal assertion materialized: {row.get('review_item_id')}")
        if row.get("review_status") == "citation_only" and row.get("materialization_status") != "not_materialized":
            errors.append(f"citation-only assertion leaked into materialization: {row.get('review_item_id')}")
    if assertion_review.get("scope", {}).get("new_story_selection_performed") is not False:
        errors.append("assertion review records a new Story selection")

    original_rows = original.get("records", [])
    if len(original_rows) != 34:
        errors.append(f"original candidate review contains {len(original_rows)} rows, expected 34")
    if {row.get("source_x1_2r_review_item_id") for row in original_rows} != reopened_ids:
        errors.append("original candidate review does not cover exactly reopened X1.2R cases")
    if any(row.get("no_candidate_mutation") is not True for row in original_rows):
        errors.append("original X1.2R candidate decision was not protected")

    facts = facts_doc.get("facts", [])
    fact_ids = [str(row.get("fact_id")) for row in facts]
    if len(fact_ids) != len(set(fact_ids)):
        errors.append("duplicate materialized fact IDs")
    semantic_keys = [str(row.get("fact_key")) for row in facts]
    if len(semantic_keys) != len(set(semantic_keys)):
        errors.append("duplicate semantic facts in X1.2R-F extension")
    old_keys = existing_semantic_keys()
    if set(semantic_keys) & old_keys:
        errors.append("X1.2R-F duplicated an existing canonical semantic fact")

    people = {str(row["person_id"]) for row in read("data/people.json").get("people", [])}
    offices = {str(row["office_id"]) for row in read("data/derived/h0c-offices.json").get("entities", [])}
    locations = {str(row["location_id"]) for row in read("data/derived/h0c-locations.json").get("records", [])}
    review_by_fact: dict[str, list[Mapping[str, Any]]] = {}
    for row in review_records:
        for fact_id in row.get("produced_fact_ids", []):
            review_by_fact.setdefault(str(fact_id), []).append(row)
    for fact in facts:
        if fact.get("review_status") != "reviewed" or fact.get("review_decision") != "accepted" or fact.get("assertion_status") != "attested":
            errors.append(f"materialized fact is not reviewed/attested: {fact.get('fact_id')}")
        if fact.get("modality") != "explicit" or fact.get("temporal_precision") != "unknown":
            errors.append(f"materialized fact has unsafe modality/precision: {fact.get('fact_id')}")
        if not fact.get("evidence_ids") or not fact.get("evidence_refs"):
            errors.append(f"materialized fact lacks evidence: {fact.get('fact_id')}")
        if fact.get("source_family") != "shishuo-jianshu-yujiaxi-local":
            errors.append(f"materialized fact lacks the registered Jianshu source family: {fact.get('fact_id')}")
        if not review_by_fact.get(str(fact.get("fact_id"))):
            errors.append(f"materialized fact lacks accepted assertion review: {fact.get('fact_id')}")
        for row in review_by_fact.get(str(fact.get("fact_id")), []):
            if row.get("review_status") != "accepted" or row.get("modality") != "explicit":
                errors.append(f"fact points to non-explicit assertion review: {fact.get('fact_id')}")
        if fact.get("fact_type") == "office_tenure":
            if fact.get("person_id") not in people or fact.get("office_id") not in offices:
                errors.append(f"office fact endpoint is invalid: {fact.get('fact_id')}")
        elif fact.get("fact_type") == "location_fact":
            if fact.get("subject_id") not in people or fact.get("location_id") not in locations:
                errors.append(f"location fact endpoint is invalid: {fact.get('fact_id')}")
        else:
            errors.append(f"unsupported materialized fact type: {fact.get('fact_type')}")
        if _contains_forbidden_model_field(fact):
            errors.append(f"ML/model field leaked into historical fact: {fact.get('fact_id')}")
    if facts_doc.get("counts", {}).get("stories_added_to_production_scope") != 0 or facts_doc.get("counts", {}).get("persons_added") != 0:
        errors.append("X1.2R-F expanded production Stories or Persons")
    if facts_doc.get("preservation", {}).get("no_ml_write_back") is not True:
        errors.append("materialized fact extension lacks no-ML-write-back protection")

    for row in corroboration.get("records", []):
        if row.get("review_status") != "reviewed" or not row.get("source_assertion_ids"):
            errors.append(f"invalid corroboration record: {row.get('corroboration_id')}")
        if row.get("target_scope") == "pre_existing_canonical_fact" and row.get("target_fact_id"):
            errors.append("pre-existing corroboration unexpectedly rewrote a canonical fact")
    if scholarly.get("records") and any(row.get("preserved_as_noncanonical") is not True for row in scholarly["records"]):
        errors.append("scholarly assertion record is not explicitly non-canonical")

    if summary.get("scope", {}).get("stories_added_to_production") != 0 or summary.get("scope", {}).get("persons_added") != 0:
        errors.append("summary records unauthorized Story/Person expansion")
    if summary.get("decision_classification") not in {
        "policy_correction_materially_increases_fact_yield",
        "modest_fact_yield_but_policy_is_sound",
        "most_assertions_remain_endpoint_or_modality_blocked",
    }:
        errors.append("invalid decision classification")
    if next_step.get("x1_2b_may_proceed_now") is not False:
        errors.append("X1.2R-F attempts to proceed directly into X1.2B")

    # Explicitly ensure protected X1.2R artifacts are still the inputs that
    # this extension claims to consume.  No old artifact is regenerated here.
    for path in (X1_2R_BUNDLES_PATH, X1_2R_FACT_REVIEW_PATH, X1_2R_IDENTITY_PATH, X1_2R_PARTICIPANT_PATH, X1_2R_CITATION_PATH, X1_2R_EXTENSION_PATH, X1_2R_MATERIALIZATION_PATH, X1_2R_SUMMARY_PATH):
        if not (ROOT / path).is_file():
            errors.append(f"protected X1.2R input is missing: {path}")
    if read(X1_2R_CITATION_PATH).get("records") and any(row.get("canonical_fact_created") for row in read(X1_2R_CITATION_PATH).get("records", [])):
        errors.append("X1.2R citation candidate artifact was changed into canonical facts")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print errors as JSON")
    args = parser.parse_args()
    errors = validate()
    if args.json:
        print(json.dumps({"errors": errors}, ensure_ascii=False, sort_keys=True))
    else:
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
        else:
            print("X1.2R-F validation passed")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
