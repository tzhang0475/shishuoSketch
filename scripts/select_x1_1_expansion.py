#!/usr/bin/env python3
"""Freeze the four-channel X1.1 Story selection before enrichment."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from scripts.x1_1_common import (
        BATCH_SIZE,
        CHANNEL_ORDER,
        EPOCH,
        ML0_BIAS_PATH,
        ML0_DATASET_PATH,
        ML0_EXPERIMENT_PATH,
        ML0_METRICS_PATH,
        ML0_RECOMMENDATION_PATH,
        POOL_PATH,
        RATIOS,
        SEED,
        SELECTION_PATH,
        SOURCE_GRAPH_VERSION,
        SOURCE_ML_VERSION,
        canonical_hash,
        hashable_selection_records,
        read,
        sha256_file,
        source_hashes,
        write,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from x1_1_common import (
        BATCH_SIZE,
        CHANNEL_ORDER,
        EPOCH,
        ML0_BIAS_PATH,
        ML0_DATASET_PATH,
        ML0_EXPERIMENT_PATH,
        ML0_METRICS_PATH,
        ML0_RECOMMENDATION_PATH,
        POOL_PATH,
        RATIOS,
        SEED,
        SELECTION_PATH,
        SOURCE_GRAPH_VERSION,
        SOURCE_ML_VERSION,
        canonical_hash,
        hashable_selection_records,
        read,
        sha256_file,
        source_hashes,
        write,
    )


def allocate(batch_size: int, ratios: Mapping[str, float] = RATIOS) -> dict[str, int]:
    """Largest-remainder allocation with stable channel-order ties."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    raw = {channel: batch_size * float(ratios[channel]) for channel in CHANNEL_ORDER}
    counts = {channel: math.floor(raw[channel]) for channel in CHANNEL_ORDER}
    remaining = batch_size - sum(counts.values())
    order = sorted(
        CHANNEL_ORDER,
        key=lambda channel: (-(raw[channel] - counts[channel]), CHANNEL_ORDER.index(channel)),
    )
    for channel in order[:remaining]:
        counts[channel] += 1
    return counts


def rank_graph(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            -float(row["scores"]["graph_guided_score"]),
            -float(row["structural"]["missing_external_pair_count"]),
            -int(row["person_connections"]["reviewed_link_count"]),
            int(row["global_ordinal"]),
            str(row["story_id"]),
        ),
    )


def rank_coverage(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            -float(row["scores"]["coverage_guided_score"]),
            -len(row["coverage"]["missing_layers_for_connected_persons"]),
            -float(row["evidence"]["evidence_quality"]),
            int(row["global_ordinal"]),
            str(row["story_id"]),
        ),
    )


def seeded_stratum(row: Mapping[str, Any]) -> str:
    person_count = int(row["structural"]["person_count"])
    band = "one" if person_count == 1 else "two" if person_count == 2 else "three_plus"
    return f"chapter-{row['chapter']}|participants-{band}"


def hash_order(seed: int, channel: str, row: Mapping[str, Any]) -> str:
    return hashlib.sha256(f"{seed}|{channel}|{row['story_id']}".encode("utf-8")).hexdigest()


def select_stratified_random(rows: list[Mapping[str, Any]], count: int, seed: int) -> list[Mapping[str, Any]]:
    if count <= 0:
        return []
    strata: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        strata[seeded_stratum(row)].append(row)
    for stratum in strata:
        strata[stratum].sort(key=lambda row: (hash_order(seed, "stratified_random", row), str(row["story_id"])))
    # Round-robin across stable strata keeps the random channel from becoming
    # a disguised top-score or single-chapter sample.
    strata_order = sorted(strata, key=lambda value: hashlib.sha256(f"{seed}|stratum|{value}".encode("utf-8")).hexdigest())
    selected: list[Mapping[str, Any]] = []
    cursor = 0
    while len(selected) < count and strata_order:
        stratum = strata_order[cursor % len(strata_order)]
        if strata[stratum]:
            selected.append(strata[stratum].pop(0))
        if all(not values for values in strata.values()):
            break
        cursor += 1
    return selected


def counter_candidates(rows: list[Mapping[str, Any]], model_ranks: Mapping[str, int]) -> list[Mapping[str, Any]]:
    if not rows:
        return []
    median_rank = max(1, math.ceil(max(model_ranks.values()) * 0.50))
    qualified = [
        row for row in rows
        if model_ranks.get(str(row["story_id"]), 0) >= median_rank
        and len(row.get("independent_value_signals", [])) >= 2
        and float(row["scores"]["counter_model_independent_score"]) >= 0.36
    ]
    # Prefer an independent signal-rich item from the lower half, while
    # retaining model rank as a documented diagnostic rather than an opaque
    # selection score.  This is intentionally not the global bottom-score set.
    return sorted(
        qualified,
        key=lambda row: (
            -len(row.get("independent_value_signals", [])),
            -float(row["scores"]["counter_model_independent_score"]),
            float(row["scores"]["model_proxy_score"]),
            int(row["global_ordinal"]),
            str(row["story_id"]),
        ),
    )


def build(batch_size: int = BATCH_SIZE, seed: int = SEED) -> dict[str, Any]:
    pool = read(POOL_PATH)
    pool_hash = sha256_file(POOL_PATH)
    qualified = [row for row in pool["records"] if row.get("eligible") is True]
    if batch_size > len(qualified):
        raise ValueError(f"batch_size {batch_size} exceeds qualified pool {len(qualified)}")
    allocation = allocate(batch_size)
    selected_by_channel: dict[str, list[Mapping[str, Any]]] = {}
    remaining = list(qualified)

    graph_rows = rank_graph(remaining)
    selected_by_channel["graph_guided"] = graph_rows[:allocation["graph_guided"]]
    selected_ids = {str(row["story_id"]) for row in selected_by_channel["graph_guided"]}
    remaining = [row for row in remaining if str(row["story_id"]) not in selected_ids]

    coverage_rows = rank_coverage(remaining)
    selected_by_channel["coverage_guided"] = coverage_rows[:allocation["coverage_guided"]]
    selected_ids |= {str(row["story_id"]) for row in selected_by_channel["coverage_guided"]}
    remaining = [row for row in remaining if str(row["story_id"]) not in selected_ids]

    random_rows = select_stratified_random(remaining, allocation["stratified_random"], seed)
    selected_by_channel["stratified_random"] = random_rows
    selected_ids |= {str(row["story_id"]) for row in random_rows}
    remaining = [row for row in remaining if str(row["story_id"]) not in selected_ids]

    global_model_order = sorted(
        qualified,
        key=lambda row: (-float(row["scores"]["model_proxy_score"]), int(row["global_ordinal"]), str(row["story_id"])),
    )
    model_ranks = {str(row["story_id"]): index for index, row in enumerate(global_model_order, start=1)}
    counter_pool = counter_candidates(remaining, model_ranks)
    if len(counter_pool) < allocation["counter_model"]:
        # A documented deterministic fallback still requires independent
        # signals and chooses the strongest qualifying remainder.  It never
        # selects by "lowest model score" alone.
        counter_pool = sorted(
            [row for row in remaining if len(row.get("independent_value_signals", [])) >= 2],
            key=lambda row: (
                -float(row["scores"]["counter_model_independent_score"]),
                float(row["scores"]["model_proxy_score"]),
                int(row["global_ordinal"]),
                str(row["story_id"]),
            ),
        )
    selected_by_channel["counter_model"] = counter_pool[:allocation["counter_model"]]
    selected_ids |= {str(row["story_id"]) for row in selected_by_channel["counter_model"]}
    if len(selected_ids) != batch_size:
        raise RuntimeError(f"selection allocation produced {len(selected_ids)} unique Stories, expected {batch_size}")

    protected_hashes = source_hashes()
    protected_hashes["candidate_pool"] = pool_hash
    all_records: list[dict[str, Any]] = []
    overall_rank = 0
    for channel in CHANNEL_ORDER:
        rows = selected_by_channel[channel]
        channel_ordered = sorted(rows, key=lambda row: (int(row["global_ordinal"]), str(row["story_id"])))
        for rank, row in enumerate(channel_ordered, start=1):
            overall_rank += 1
            story_id = str(row["story_id"])
            if channel == "graph_guided":
                selection_score = row["scores"]["graph_guided_score"]
                selection_reason = [
                    "high interpretable bridge/external structure value",
                    "current graph has a documented PersonStory boundary for this Story",
                ]
                selection_inputs = ["structural_bridge_value", "external_layer_value", "temporal_value", "coverage_value"]
            elif channel == "coverage_guided":
                selection_score = row["scores"]["coverage_guided_score"]
                selection_reason = [
                    "addresses a documented coverage deficit rather than model similarity",
                    *[f"missing_or_underrepresented_{layer}" for layer in row["coverage"]["missing_layers_for_connected_persons"]],
                ]
                selection_inputs = ["coverage_deficit", "source_evidence_quality", "chapter_underrepresentation"]
            elif channel == "stratified_random":
                selection_score = None
                selection_reason = ["seeded independent exploration/control sample"]
                selection_inputs = ["stratum", "seeded_hash_order"]
            else:
                selection_score = row["scores"]["counter_model_independent_score"]
                selection_reason = [
                    "lower-half model-proxy preference with independent evidence/value signals",
                    *row.get("independent_value_signals", []),
                ]
                selection_inputs = ["model_proxy_rank_diagnostic", "independent_value_signals", "source_evidence_quality"]
            all_records.append({
                "story_id": story_id,
                "selection_epoch": EPOCH,
                "selection_mode": channel,
                "selection_rank": rank,
                "global_selection_rank": overall_rank,
                "global_rank": model_ranks.get(story_id),
                "selection_score": selection_score,
                "model_proxy_score": row["scores"]["model_proxy_score"],
                "model_proxy_policy": row.get("model_proxy_policy"),
                "model_proxy_rank": model_ranks.get(story_id),
                "counter_model_reason": row.get("independent_value_signals", []) if channel == "counter_model" else [],
                "stratum": seeded_stratum(row) if channel == "stratified_random" else None,
                "selection_seed": seed if channel in {"stratified_random", "counter_model"} else None,
                "candidate_pool_hash": pool_hash,
                "source_graph_version": SOURCE_GRAPH_VERSION,
                "source_ml_version": SOURCE_ML_VERSION,
                "selection_reason": selection_reason,
                "selection_inputs": selection_inputs,
                "source_story_global_ordinal": row["global_ordinal"],
            })
    all_records.sort(key=lambda row: int(row["global_selection_rank"]))
    selection_snapshot = hashable_selection_records(all_records)
    snapshot_hash = canonical_hash(selection_snapshot)
    document = {
        "schema": 1,
        "stage": "x1-1-selection-manifest",
        "selection_epoch": EPOCH,
        "selection_status": "frozen",
        "research_only": True,
        "frozen_before_enrichment": True,
        "batch_policy": {
            "requested_batch_size": batch_size,
            "ratios": RATIOS,
            "allocation": allocation,
            "allocation_method": "largest_remainder_then_channel_order_tie_break",
            "default_seed": SEED,
        },
        "source_versions": {
            "graph": SOURCE_GRAPH_VERSION,
            "ml": SOURCE_ML_VERSION,
            "input_artifact_hashes": protected_hashes,
        },
        "candidate_pool": {
            "path": str(POOL_PATH),
            "sha256": pool_hash,
            "qualified_story_count": len(qualified),
        },
        "selection_snapshot_sha256": snapshot_hash,
        "records": all_records,
        "policy": "Selection is frozen before X1.1 enrichment. Selection scores recommend review only; they do not assert historical importance or create facts.",
    }
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--output", default=str(SELECTION_PATH))
    args = parser.parse_args()
    document = build(args.batch_size, args.seed)
    write(Path(args.output), document)
    channel_paths = {
        channel: Path(f"data/derived/x1-1-{channel.replace('_', '-')}.json")
        for channel in CHANNEL_ORDER
    }
    for channel, path in channel_paths.items():
        records = [row for row in document["records"] if row["selection_mode"] == channel]
        write(path, {
            "schema": 1,
            "stage": f"x1-1-{channel}",
            "selection_epoch": EPOCH,
            "selection_status": "frozen",
            "source_selection_manifest": str(SELECTION_PATH),
            "source_selection_manifest_sha256": sha256_file(SELECTION_PATH) if Path(SELECTION_PATH).is_file() else None,
            "records": records,
        })
    print(json.dumps({
        "stage": document["stage"],
        "selection_status": document["selection_status"],
        "allocation": document["batch_policy"]["allocation"],
        "selection_snapshot_sha256": document["selection_snapshot_sha256"],
        "output": args.output,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
