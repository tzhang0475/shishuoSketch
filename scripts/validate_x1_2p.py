#!/usr/bin/env python3
"""Validate the X1.2P punctuation gate and frozen-scope contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

try:
    from scripts.x1_2p_common import (
        CHANNEL_PATH,
        DEPENDENCY_PATH,
        ELIGIBILITY_PATH,
        GATE_AUDIT_PATH,
        NEXT_STEP_PATH,
        PUNCTUATION_PATH,
        READINESS_PATH,
        STORY_REVIEW_PATH,
        SUMMARY_PATH,
        X1_1_INPUTS,
        X1_2A_INPUTS,
        common_source_bundle,
        read,
        selection_by_story,
        sha256_file,
        source_bundle_matches,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from x1_2p_common import (
        CHANNEL_PATH,
        DEPENDENCY_PATH,
        ELIGIBILITY_PATH,
        GATE_AUDIT_PATH,
        NEXT_STEP_PATH,
        PUNCTUATION_PATH,
        READINESS_PATH,
        STORY_REVIEW_PATH,
        SUMMARY_PATH,
        X1_1_INPUTS,
        X1_2A_INPUTS,
        common_source_bundle,
        read,
        selection_by_story,
        sha256_file,
        source_bundle_matches,
    )


ROOT = Path(__file__).resolve().parents[1]
STATES = {"accepted", "unresolved", "rejected"}


def validate() -> list[str]:
    errors: list[str] = []
    try:
        selection = read(X1_1_INPUTS["selection_manifest"])
        pool = read(X1_1_INPUTS["candidate_pool"])
        x1_2a_review = read(X1_2A_INPUTS["review_manifest"])
        x1_2a_extension = read(X1_2A_INPUTS["canonical_facts"])
        gate = read(GATE_AUDIT_PATH)
        story = read(STORY_REVIEW_PATH)
        dependency = read(DEPENDENCY_PATH)
        eligibility = read(ELIGIBILITY_PATH)
        channel = read(CHANNEL_PATH)
        readiness = read(READINESS_PATH)
        recommendation = read(NEXT_STEP_PATH)
        summary = read(SUMMARY_PATH)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return [f"X1.2P artifacts cannot be read: {exc}"]

    selected_ids = set(selection_by_story())
    if len(selected_ids) != 20:
        errors.append("X1.1 selection does not contain exactly 20 Stories")
    if selection.get("selection_status") != "frozen" or selection.get("frozen_before_enrichment") is not True:
        errors.append("X1.1 selection is not frozen")
    if gate.get("scope", {}).get("selected_story_ids") != sorted(selected_ids):
        errors.append("X1.2P Story scope differs from frozen X1.1 selection")
    if gate.get("scope", {}).get("replacement_selection") is not False:
        errors.append("X1.2P replacement selection is not prohibited")
    if gate.get("scope", {}).get("x1_1_disputed_28_reopened") is not False:
        errors.append("X1.1 disputed 28 Stories were reopened")
    expected_pool_punctuation = pool.get("source_artifact_hashes", {}).get("punctuation")
    if not expected_pool_punctuation or sha256_file(PUNCTUATION_PATH) != expected_pool_punctuation:
        errors.append("punctuation source changed relative to the frozen X1.1 candidate pool")

    expected_source_hashes = common_source_bundle()
    for document, label in (
        (gate, "gate audit"),
        (story, "Story review"),
        (dependency, "dependency audit"),
        (eligibility, "eligibility"),
        (channel, "channel audit"),
        (readiness, "candidate readiness"),
        (recommendation, "next-step recommendation"),
    ):
        if not source_bundle_matches(document.get("source_hashes", {}), expected_source_hashes):
            errors.append(f"{label} source hashes are stale")
    summary_hashes = summary.get("source_hashes", {})
    if not source_bundle_matches(expected_source_hashes, summary_hashes, allow_extra=True):
        errors.append("summary source hashes are stale")

    story_rows = story.get("records", [])
    if len(story_rows) != 20:
        errors.append(f"Story review count is {len(story_rows)}, expected 20")
    if {row.get("story_id") for row in story_rows} != selected_ids:
        errors.append("Story review IDs differ from X1.1 selection")
    if len({row.get("review_item_id") for row in story_rows}) != len(story_rows):
        errors.append("Story review IDs are not unique")
    for row in story_rows:
        if row.get("review_status") not in STATES:
            errors.append(f"invalid Story review state: {row.get('story_id')}")
        if not row.get("review_reason"):
            errors.append(f"Story review lacks reason: {row.get('story_id')}")
        if row.get("selection_does_not_affect_textual_judgment") is not True:
            errors.append(f"Story review lacks channel-neutrality flag: {row.get('story_id')}")
        if row.get("punctuation_review", {}).get("change_applied") is not False:
            errors.append(f"X1.2P unexpectedly modified punctuation: {row.get('story_id')}")
        refs = row.get("punctuation_record", {}).get("reference_audit", [])
        if not refs or not all(ref.get("exists") and ref.get("hash_matches") for ref in refs):
            errors.append(f"punctuation reference provenance failed: {row.get('story_id')}")
        if row.get("review_status") == "accepted":
            if not row.get("evidence_ids") or not all(ref.get("valid") for ref in row.get("evidence_refs", [])):
                errors.append(f"accepted punctuation lacks valid evidence: {row.get('story_id')}")
            if row.get("gates", {}).get("punctuation") != "pass":
                errors.append(f"accepted punctuation did not pass its gate: {row.get('story_id')}")
    if story.get("counts") != {"unresolved": 20}:
        errors.append(f"X1.2P Story outcomes changed unexpectedly: {story.get('counts')}")
    if story.get("punctuation_change_count") != 0:
        errors.append("X1.2P punctuation changes are nonzero")

    classification = gate.get("classification", {})
    if classification.get("type") != "intentional_two_tier_policy":
        errors.append("gate classification is not intentional_two_tier_policy")
    for key in ("implementation_bug", "stale_metadata", "validator_schema_mismatch"):
        if classification.get(key) is not False:
            errors.append(f"gate classification incorrectly flags {key}")
    if gate.get("summary", {}).get("candidate_gate_pass_count") != 20:
        errors.append("candidate-level gate count is not 20")
    if gate.get("summary", {}).get("production_punctuation_gate_pass_count") != 0:
        errors.append("production punctuation gate unexpectedly passed a Story")

    if dependency.get("summary", {}).get("unresolved_fact_candidate_count") != 58:
        errors.append("dependency audit does not cover all 58 unresolved facts")
    if len(dependency.get("fact_records", [])) != 58:
        errors.append("fact dependency record count is not 58")
    if len(dependency.get("identity_records", [])) != 3:
        errors.append("identity dependency record count is not 3")
    for row in dependency.get("fact_records", []) + dependency.get("identity_records", []):
        if "blocked_by_story_punctuation" not in row.get("blocking_factors", []):
            errors.append(f"dependency lacks punctuation blocker: {row.get('dependency_id')}")
        if row.get("materialization_status") != "not_materialized":
            errors.append(f"dependency was materialized: {row.get('dependency_id')}")
        if row.get("would_punctuation_only_accept_fact", False) or row.get("would_punctuation_only_resolve_identity", False):
            errors.append(f"punctuation-only acceptance leaked into dependency audit: {row.get('dependency_id')}")

    if len(eligibility.get("records", [])) != 20:
        errors.append("rematerialization eligibility does not cover 20 Stories")
    if eligibility.get("counts") != {
        "eligible_for_rematerialization": 0,
        "still_unresolved": 20,
        "rejected": 0,
        "stories_released": 0,
        "facts_released": 0,
        "persons_released": 0,
    }:
        errors.append(f"unexpected rematerialization counts: {eligibility.get('counts')}")
    if len(channel.get("channels", [])) != 4:
        errors.append("channel audit does not cover four channels")
    for row in channel.get("channels", []):
        if row.get("accepted_count") != 0 or row.get("rejected_count") != 0:
            errors.append(f"channel has unexpected resolved Story: {row.get('selection_mode')}")
        if row.get("selected_story_count") != {"graph_guided": 8, "coverage_guided": 6, "stratified_random": 3, "counter_model": 3}.get(row.get("selection_mode")):
            errors.append(f"channel allocation changed: {row.get('selection_mode')}")
    if channel.get("channel_neutrality", {}).get("selection_mode_influenced_outcome") is not False:
        errors.append("selection mode influenced punctuation outcome")

    if len(readiness.get("records", [])) != len(pool.get("records", [])):
        errors.append("candidate punctuation readiness does not cover the full X1.1 pool")
    if readiness.get("candidate_pool_sha256") != sha256_file(X1_1_INPUTS["candidate_pool"]):
        errors.append("candidate readiness is not bound to the frozen pool")
    if readiness.get("selection_snapshot_sha256") != selection.get("selection_snapshot_sha256"):
        errors.append("candidate readiness is not bound to the frozen selection snapshot")
    readiness_by_id = {row.get("story_id"): row for row in readiness.get("records", [])}
    for story_id in selected_ids:
        row = readiness_by_id.get(story_id, {})
        if row.get("x1_2p_selected") is not True or row.get("production_punctuation_ready") is not False:
            errors.append(f"selected Story readiness is inconsistent: {story_id}")

    if x1_2a_review.get("source_hashes", {}).get("x1_1") != {
        name: sha256_file(path) for name, path in X1_1_INPUTS.items()
    }:
        errors.append("X1.2A review input hashes no longer resolve")
    if len(x1_2a_extension.get("fact_index", [])) != 9 or len(x1_2a_extension.get("entities", [])) != 3:
        errors.append("protected X1.2A extension counts changed")
    if summary.get("protected_x1_2a", {}).get("canonical_extension_unchanged") is not True:
        errors.append("X1.2A extension protection is missing")
    if recommendation.get("do_not_execute") != ["X1.2B", "HG1.1", "ML1.1", "ER2"]:
        errors.append("X1.2P stop boundary is incomplete")
    if summary.get("stage") != "x1-2p-summary":
        errors.append("summary stage is invalid")
    return errors


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    errors = validate()
    if errors:
        print("X1.2P validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("X1.2P validation passed")


if __name__ == "__main__":
    main()
