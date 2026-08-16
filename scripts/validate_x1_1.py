#!/usr/bin/env python3
"""Validate the X1.1 candidate, selection, review, and audit contracts."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

try:
    from scripts.x1_1_common import (
        BATCH_SIZE,
        CHANNEL_ORDER,
        POOL_PATH,
        RATIOS,
        SELECTION_PATH,
        canonical_hash,
        hashable_selection_records,
        read,
        sha256_file,
        source_hashes,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from x1_1_common import (
        BATCH_SIZE,
        CHANNEL_ORDER,
        POOL_PATH,
        RATIOS,
        SELECTION_PATH,
        canonical_hash,
        hashable_selection_records,
        read,
        sha256_file,
        source_hashes,
    )


ROOT = Path(__file__).resolve().parents[1]
REVIEW_PATH = Path("data/derived/x1-1-review-results.json")
INFO_PATH = Path("data/derived/x1-1-information-gain.json")
BIAS_PATH = Path("data/derived/x1-1-bias-audit.json")
ONTOLOGY_PATH = Path("data/derived/x1-1-ontology-gap-candidates.json")
RECOMMENDATION_PATH = Path("data/derived/x1-1-next-epoch-recommendation.json")
SUMMARY_PATH = Path("data/derived/x1-1-summary.json")


def validate() -> dict[str, Any]:
    pool = read(POOL_PATH)
    selection = read(SELECTION_PATH)
    review = read(REVIEW_PATH)
    info = read(INFO_PATH)
    bias = read(BIAS_PATH)
    ontology = read(ONTOLOGY_PATH)
    recommendation = read(RECOMMENDATION_PATH)
    summary = read(SUMMARY_PATH)
    errors: list[str] = []

    if pool.get("stage") != "x1-1-candidate-pool":
        errors.append("candidate pool stage is invalid")
    if selection.get("stage") != "x1-1-selection-manifest" or selection.get("selection_status") != "frozen":
        errors.append("selection is not frozen")
    if selection.get("frozen_before_enrichment") is not True:
        errors.append("selection freeze flag is missing")
    if review.get("stage") != "x1-1-review-results":
        errors.append("review result stage is invalid")

    records = pool.get("records", [])
    record_by_id = {str(row.get("story_id")): row for row in records if isinstance(row, dict)}
    qualified_ids = {story_id for story_id, row in record_by_id.items() if row.get("eligible") is True}
    production_ids = {
        str(row.get("id"))
        for row in read("data/derived/sc1-site.json").get("stories", [])
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    links = read("data/derived/person-story-links.json").get("links", [])
    global_story_ids = {str(row.get("entry_id")) for row in links if isinstance(row, dict) and isinstance(row.get("entry_id"), str)}
    if len(records) != 417:
        errors.append(f"candidate audit count is {len(records)}, expected 417")
    if len(qualified_ids) != pool.get("counts", {}).get("qualified_story_count"):
        errors.append("candidate eligibility count does not match pool summary")
    if len(global_story_ids - production_ids) != 417:
        errors.append("global out-of-scope Story universe is not 417")
    if sum(1 for row in links if row.get("entry_id") in production_ids) != 330:
        errors.append("published PersonStory boundary is not 330")
    if sum(1 for row in links if row.get("entry_id") not in production_ids) != 545:
        errors.append("out-of-scope PersonStory boundary is not 545")
    if len({str(row.get("story_id")) for row in records}) != len(records):
        errors.append("candidate Story IDs are not unique")
    for row in records:
        story_id = str(row.get("story_id"))
        if story_id in production_ids:
            errors.append(f"published Story appears in candidate pool: {story_id}")
        if not (ROOT / row.get("source", {}).get("path", "missing")).is_file():
            errors.append(f"candidate source is missing: {story_id}")
        if not row.get("source", {}).get("sha256"):
            errors.append(f"candidate source hash is missing: {story_id}")
        if row.get("eligible") is True and row.get("rejection_reasons"):
            errors.append(f"eligible Story has rejection reasons: {story_id}")
        if row.get("eligible") is not True and not row.get("rejection_reasons"):
            errors.append(f"rejected Story has no rejection reason: {story_id}")

    selected = selection.get("records", [])
    selected_ids = [str(row.get("story_id")) for row in selected]
    allocation = selection.get("batch_policy", {}).get("allocation", {})
    expected_allocation = {channel: int(BATCH_SIZE * RATIOS[channel]) for channel in CHANNEL_ORDER}
    # The default 20-Story allocation is exact; validate the manifest itself
    # as the authority for configurable runs.
    if allocation != {"graph_guided": 8, "coverage_guided": 6, "stratified_random": 3, "counter_model": 3}:
        errors.append(f"default allocation changed: {allocation}")
    if len(selected) != BATCH_SIZE or len(set(selected_ids)) != BATCH_SIZE:
        errors.append("selection batch is not 20 unique Stories")
    if not set(selected_ids) <= qualified_ids:
        errors.append("selected Story is outside the qualified candidate pool")
    if set(selected_ids) & production_ids:
        errors.append("selection overlaps published production scope")
    channel_ids: dict[str, set[str]] = {channel: set() for channel in CHANNEL_ORDER}
    for row in selected:
        channel = row.get("selection_mode")
        if channel not in channel_ids:
            errors.append(f"unknown selection channel: {channel}")
            continue
        channel_ids[channel].add(str(row.get("story_id")))
        if row.get("candidate_pool_hash") != sha256_file(POOL_PATH):
            errors.append(f"selection candidate-pool hash mismatch: {row.get('story_id')}")
        if channel == "stratified_random":
            if row.get("selection_score") is not None or not row.get("stratum") or row.get("selection_seed") is None:
                errors.append(f"random channel carries model-dependent selection data: {row.get('story_id')}")
            if "model" in " ".join(row.get("selection_inputs", [])).lower():
                errors.append(f"random channel names a model input: {row.get('story_id')}")
        if channel == "counter_model":
            if len(row.get("counter_model_reason", [])) < 2:
                errors.append(f"counter-model candidate lacks independent signals: {row.get('story_id')}")
            if int(row.get("model_proxy_rank", 0)) <= len(qualified_ids) // 2:
                errors.append(f"counter-model candidate is not lower-half model preference: {row.get('story_id')}")
        if not row.get("model_proxy_policy"):
            errors.append(f"model-proxy policy is missing: {row.get('story_id')}")
        if channel == "graph_guided" and row.get("selection_score") is None:
            errors.append(f"graph-guided selection score missing: {row.get('story_id')}")
        if channel == "coverage_guided" and row.get("selection_score") is None:
            errors.append(f"coverage-guided selection score missing: {row.get('story_id')}")
    for channel in CHANNEL_ORDER:
        if len(channel_ids[channel]) != allocation.get(channel):
            errors.append(f"{channel} allocation mismatch")
    if any(channel_ids[left] & channel_ids[right] for index, left in enumerate(CHANNEL_ORDER) for right in CHANNEL_ORDER[index + 1:]):
        errors.append("selection channels are not disjoint")
    snapshot = canonical_hash(hashable_selection_records(selected))
    if snapshot != selection.get("selection_snapshot_sha256"):
        errors.append("selection snapshot hash mismatch")

    review_by_id = {str(row.get("story_id")): row for row in review.get("records", []) if isinstance(row, dict)}
    if set(review_by_id) != set(selected_ids):
        errors.append("review results do not exactly match frozen selection")
    for story_id, row in review_by_id.items():
        if row.get("selection_status") != "selected" or row.get("review_status") != "candidate":
            errors.append(f"selection/review states are not separated: {story_id}")
        if row.get("canonical_status") != "not_materialized":
            errors.append(f"X1.1 canonical materialization is not deferred: {story_id}")
        if row.get("acceptance_status") != "accepted_for_x1_1_review_overlay":
            errors.append(f"Story overlay acceptance state invalid: {story_id}")
        for evidence_id in row.get("evidence_ids", []):
            if evidence_id not in {
                str(item.get("id")) for item in read("data/evidence/wp1-evidence.json").get("records", [])
                if isinstance(item, dict) and item.get("id")
            }:
                errors.append(f"review evidence does not resolve: {story_id}/{evidence_id}")
        for action in row.get("actions", []):
            if action.get("action") == "ADD_STORY" and action.get("accepted") is not True:
                errors.append(f"ADD_STORY overlay action is not accepted: {story_id}")
            if action.get("action") == "ADD_FACT" and action.get("accepted") is not False:
                errors.append(f"ADD_FACT was canonicalized in X1.1: {story_id}")
            if action.get("action") == "ADD_PERSON" and action.get("accepted") is not False:
                errors.append(f"ADD_PERSON was canonicalized in X1.1: {story_id}")
        action_order = {"ADD_FACT": 0, "ADD_STORY": 1, "ADD_PERSON": 2}
        observed_order = [action_order.get(str(action.get("action")), 99) for action in row.get("actions", [])]
        if observed_order != sorted(observed_order):
            errors.append(f"X1.1 action order violates ADD_FACT -> ADD_STORY -> ADD_PERSON preference: {story_id}")
    if review.get("counts", {}).get("canonical_fact_addition_count") != 0:
        errors.append("canonical fact additions are nonzero")
    if review.get("counts", {}).get("canonical_person_addition_count") != 0:
        errors.append("canonical Person additions are nonzero")
    if review.get("counts", {}).get("canonical_story_addition_count") != 0:
        errors.append("canonical Story additions are nonzero")
    if review.get("review_policy", {}).get("model_output_does_not_create_facts") is not True:
        errors.append("review policy does not protect against ML write-back")
    if review.get("review_policy", {}).get("missing_edges_are_not_negative_facts") is not True:
        errors.append("missing-edge policy is absent")

    for artifact_path, stage in ((INFO_PATH, "x1-1-information-gain"), (BIAS_PATH, "x1-1-bias-audit"), (ONTOLOGY_PATH, "x1-1-ontology-gap-candidates"), (RECOMMENDATION_PATH, "x1-1-next-epoch-recommendation"), (SUMMARY_PATH, "x1-1-summary")):
        document = read(artifact_path)
        if document.get("stage") != stage:
            errors.append(f"invalid stage in {artifact_path}")
        if document.get("research_only") is not True:
            errors.append(f"{artifact_path} is not research-only")
    if set(row.get("selection_mode") for row in info.get("channels", [])) != set(CHANNEL_ORDER):
        errors.append("information-gain channel matrix is incomplete")
    if len(bias.get("channels", [])) != len(CHANNEL_ORDER):
        errors.append("bias audit channel matrix is incomplete")
    ratios = recommendation.get("recommended_x1_2_ratios", {})
    if float(ratios.get("stratified_random", 0)) < 0.10 or float(ratios.get("counter_model", 0)) < 0.10:
        errors.append("X1.2 recommendation drops an independent-channel floor")
    if recommendation.get("do_not_execute") is None or "HG1.1" not in recommendation.get("do_not_execute", []):
        errors.append("X1.2 stop boundary is missing")

    pool_hashes = pool.get("source_artifact_hashes", {})
    current_hashes = source_hashes()
    for name, expected in pool_hashes.items():
        if current_hashes.get(name) != expected:
            errors.append(f"protected input changed: {name}")
    if summary.get("protected_input_hashes") != pool_hashes:
        errors.append("summary protected hashes do not match candidate pool")
    if errors:
        raise AssertionError("\n".join(sorted(set(errors))))
    return {
        "status": "ok",
        "audited_candidates": len(records),
        "qualified_candidates": len(qualified_ids),
        "selected_stories": len(selected),
        "allocation": allocation,
        "canonical_additions": review.get("counts", {}).get("canonical_story_addition_count", 0) + review.get("counts", {}).get("canonical_fact_addition_count", 0) + review.get("counts", {}).get("canonical_person_addition_count", 0),
        "ontology_gap_candidates": len(ontology.get("candidates", [])),
        "protected_hashes_verified": len(pool_hashes),
    }


def main() -> None:
    argparse.ArgumentParser().parse_args()
    print(json.dumps(validate(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
