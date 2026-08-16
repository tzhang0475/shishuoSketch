#!/usr/bin/env python3
"""Compare X1.1 selection channels and produce the next-epoch recommendation."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from scripts.x1_1_common import (
        BIAS_PATH,
        EPOCH,
        RATIOS,
        INFO_GAIN_PATH,
        ONTOLOGY_PATH,
        RECOMMENDATION_PATH,
        REVIEW_PATH,
        SELECTION_PATH,
        SUMMARY_PATH,
        build_context,
        canonical_hash,
        read,
        sha256_file,
        write,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from x1_1_common import (
        BIAS_PATH,
        EPOCH,
        RATIOS,
        INFO_GAIN_PATH,
        ONTOLOGY_PATH,
        RECOMMENDATION_PATH,
        REVIEW_PATH,
        SELECTION_PATH,
        SUMMARY_PATH,
        build_context,
        canonical_hash,
        read,
        sha256_file,
        write,
    )


CHANNELS = tuple(RATIOS)


def rows_by_channel(selection: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    result = {channel: [] for channel in CHANNELS}
    for row in selection.get("records", []):
        if row.get("selection_mode") in result:
            result[str(row["selection_mode"])].append(row)
    return result


def review_by_story(review: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(row["story_id"]): row for row in review.get("records", []) if isinstance(row, Mapping)}


def candidate_by_story(pool: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(row["story_id"]): row for row in pool.get("records", []) if isinstance(row, Mapping)}


def layer_targets(review_row: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    for action in review_row.get("actions", []):
        if action.get("action") == "ADD_FACT":
            result.extend(str(target.get("layer")) for target in action.get("targets", []) if isinstance(target, Mapping))
    return sorted(set(result))


def information_gain(pool: Mapping[str, Any], selection: Mapping[str, Any], review: Mapping[str, Any]) -> dict[str, Any]:
    candidates = candidate_by_story(pool)
    reviews = review_by_story(review)
    channels = rows_by_channel(selection)
    result: list[dict[str, Any]] = []
    for channel in CHANNELS:
        selected = channels[channel]
        rows = [candidates[str(row["story_id"])] for row in selected]
        review_rows = [reviews[str(row["story_id"])] for row in selected]
        target_layers = Counter(layer for row in review_rows for layer in layer_targets(row))
        ontology_count = sum(len(candidates[str(row["story_id"])].get("ontology_clues", {})) for row in selected)
        external_potential = sum(
            1 for row in rows
            if row["structural"]["missing_external_pair_count"] > 0 or row["structural"]["external_layer_value"] > 0
        )
        bridge_count = sum(1 for row in rows if row["structural"]["missing_external_pair_count"] > 0)
        persons = sorted({person_id for row in rows for person_id in row["person_connections"]["production_person_ids"]})
        evidence = sorted({evidence_id for row in rows for evidence_id in row["evidence"]["local_evidence_ids"]})
        candidate_person_surfaces = sum(
            len(action.get("surfaces", []))
            for review_row in review_rows
            for action in review_row.get("actions", [])
            if action.get("action") == "ADD_PERSON"
        )
        info_units = (
            sum(target_layers.values())
            + external_potential
            + bridge_count
            + ontology_count
            + candidate_person_surfaces
        )
        result.append({
            "selection_mode": channel,
            "requested_allocation": selection["batch_policy"]["allocation"][channel],
            "selected_story_count": len(selected),
            "accepted_story_overlay_count": sum(
                reviews[str(row["story_id"])].get("acceptance_status") == "accepted_for_x1_1_review_overlay"
                for row in selected
            ),
            "rejected_story_count": 0,
            "canonical_additions": {
                "ADD_FACT": 0,
                "ADD_STORY": 0,
                "ADD_PERSON": 0,
            },
            "review_queue": {
                "candidate_fact_action_count": sum(target_layers.values()),
                "fact_layers": dict(sorted(target_layers.items())),
                "identity_review_candidate_count": candidate_person_surfaces,
            },
            "observed_structure": {
                "connected_production_person_count": len(persons),
                "source_evidence_count": len(evidence),
                "external_layer_potential_story_count": external_potential,
                "bridge_story_count": bridge_count,
                "ontology_gap_surface_count": ontology_count,
                "information_units": info_units,
                "information_units_per_selected_story": round(info_units / len(selected), 8) if selected else 0.0,
            },
            "normalized_metrics": {
                "candidate_fact_actions_per_story": round(sum(target_layers.values()) / len(selected), 8) if selected else 0.0,
                "external_potential_per_story": round(external_potential / len(selected), 8) if selected else 0.0,
                "bridge_stories_per_story": round(bridge_count / len(selected), 8) if selected else 0.0,
            },
            "interpretation": "Observed pilot information gain is a selection diagnostic, not historical importance or causal proof.",
        })
    return {
        "schema": 1,
        "stage": "x1-1-information-gain",
        "selection_epoch": EPOCH,
        "research_only": True,
        "source_hashes": {
            "candidate_pool": sha256_file("data/derived/x1-1-candidate-pool.json"),
            "selection_manifest": sha256_file(SELECTION_PATH),
            "review_results": sha256_file(REVIEW_PATH),
        },
        "channels": result,
        "policy": "No X1.1 action is canonicalized by this audit; information gain is reported per selection channel and per accepted review-overlay Story.",
    }


def distribution(rows: Iterable[Mapping[str, Any]], field_getter) -> dict[str, int]:
    return dict(sorted(Counter(str(field_getter(row)) for row in rows).items()))


def bias_audit(pool: Mapping[str, Any], selection: Mapping[str, Any]) -> dict[str, Any]:
    candidates = candidate_by_story(pool)
    channels = rows_by_channel(selection)
    all_qualified = [row for row in pool.get("records", []) if row.get("eligible") is True]
    per_channel: list[dict[str, Any]] = []
    for channel in CHANNELS:
        selected = [candidates[str(row["story_id"])] for row in channels[channel]]
        person_ids = [person_id for row in selected for person_id in row["person_connections"]["production_person_ids"]]
        person_degree_values = [
            1.0 - float(row["coverage"]["person_degree_signal"])
            for row in selected
        ]
        per_channel.append({
            "selection_mode": channel,
            "story_count": len(selected),
            "chapter_distribution": distribution(selected, lambda row: row["chapter"]),
            "person_count_band": distribution(selected, lambda row: row["structural"]["person_count"] if row["structural"]["person_count"] < 3 else "3_plus"),
            "coverage_layer_distribution": dict(sorted(Counter(
                layer for row in selected for layer in row["coverage"]["missing_layers_for_connected_persons"]
            ).items())),
            "mean_model_proxy_score": round(sum(float(row["scores"]["model_proxy_score"]) for row in selected) / len(selected), 8) if selected else 0.0,
            "mean_current_person_degree_proxy": round(sum(person_degree_values) / len(person_degree_values), 8) if person_degree_values else 0.0,
            "unique_production_person_count": len(set(person_ids)),
            "top_person_share": round(
                max(Counter(person_ids).values(), default=0) / max(1, len(person_ids)),
                8,
            ),
        })
    qualified_chapters = Counter(row["chapter"] for row in all_qualified)
    selected_chapters = Counter(
        chapter
        for channel in per_channel
        for chapter, count in channel["chapter_distribution"].items()
        for _ in range(count)
    )
    graph_row = next(row for row in per_channel if row["selection_mode"] == "graph_guided")
    graph_dense_person_warning = (
        graph_row["mean_current_person_degree_proxy"] > sum(
            1.0 - float(row["coverage"]["person_degree_signal"]) for row in all_qualified
        ) / max(1, len(all_qualified))
        and graph_row["top_person_share"] > 0.28
    )
    return {
        "schema": 1,
        "stage": "x1-1-bias-audit",
        "selection_epoch": EPOCH,
        "research_only": True,
        "source_hashes": {
            "candidate_pool": sha256_file("data/derived/x1-1-candidate-pool.json"),
            "selection_manifest": sha256_file(SELECTION_PATH),
        },
        "qualified_pool_baselines": {
            "story_count": len(all_qualified),
            "chapter_distribution": dict(sorted(qualified_chapters.items())),
            "selection_share_by_chapter": {
                chapter: round(count / max(1, sum(selected_chapters.values())), 8)
                for chapter, count in sorted(selected_chapters.items())
            },
        },
        "channels": per_channel,
        "selection_bias_surfaces": {
            "graph_guided_dense_person_concentration": graph_dense_person_warning,
            "graph_guided_dense_person_concentration_reason": "Graph-guided selection has a higher current Person-degree proxy and a concentrated top-person share than the qualified-pool baseline." if graph_dense_person_warning else "No thresholded dense-person concentration warning in this small pilot.",
            "coverage_vs_graph_overlap_policy": "Channels are disjoint by frozen sequential allocation; coverage ranking is computed from deficits rather than graph score.",
            "random_independence_policy": "Stratified random uses chapter/participant strata and seeded hash order; no model or graph score is an input to its choice.",
        },
        "limitations": [
            "Small batch size makes concentration estimates diagnostic rather than inferential.",
            "Person degree is a representation/coverage statistic, not historical importance.",
            "Chapter and source survival distributions reflect the surviving corpus.",
        ],
    }


def ontology_gaps(pool: Mapping[str, Any], selection: Mapping[str, Any]) -> dict[str, Any]:
    candidates = candidate_by_story(pool)
    grouped: dict[str, dict[str, Any]] = {}
    for row in selection.get("records", []):
        candidate = candidates[str(row["story_id"])]
        for semantic, terms in candidate.get("ontology_clues", {}).items():
            item = grouped.setdefault(semantic, {
                "candidate_relation_semantics": semantic,
                "supporting_story_ids": [],
                "supporting_evidence_ids": set(),
                "surface_terms": set(),
                "frequency": 0,
                "existing_hg0_edge_type_match": False,
                "review_required": True,
            })
            item["supporting_story_ids"].append(str(row["story_id"]))
            item["supporting_evidence_ids"].update(candidate["evidence"]["local_evidence_ids"])
            item["surface_terms"].update(terms)
            item["frequency"] += 1
    rows = []
    for semantic, item in sorted(grouped.items()):
        item["supporting_story_ids"] = sorted(set(item["supporting_story_ids"]))
        item["supporting_evidence_ids"] = sorted(item["supporting_evidence_ids"])
        item["surface_terms"] = sorted(item["surface_terms"])
        item["detection_basis"] = "surface_signal_only; semantic review required"
        # A semantic clue such as marriage mediation is not equivalent to an
        # existing spouse edge.  X1.1 deliberately reports these as ontology
        # candidates rather than claiming an HG0 match.
        item["existing_hg0_edge_type_match"] = False
        item["existing_ontology_mismatch"] = not item["existing_hg0_edge_type_match"]
        rows.append(item)
    return {
        "schema": 1,
        "stage": "x1-1-ontology-gap-candidates",
        "selection_epoch": EPOCH,
        "research_only": True,
        "source_hashes": {
            "candidate_pool": sha256_file("data/derived/x1-1-candidate-pool.json"),
            "selection_manifest": sha256_file(SELECTION_PATH),
        },
        "candidates": rows,
        "policy": "These are reviewable semantic surfaces, not new ontology edge types or historical facts. X1.1 does not alter HG0 ontology.",
    }


def recommendation(info: Mapping[str, Any], bias: Mapping[str, Any], ontology: Mapping[str, Any]) -> dict[str, Any]:
    channels = {row["selection_mode"]: row for row in info["channels"]}
    graph_units = float(channels["graph_guided"]["observed_structure"]["information_units_per_selected_story"])
    coverage_units = float(channels["coverage_guided"]["observed_structure"]["information_units_per_selected_story"])
    if coverage_units > graph_units * 1.10:
        ratios = {"graph_guided": 0.30, "coverage_guided": 0.40, "stratified_random": 0.15, "counter_model": 0.15}
        ratio_reason = "Coverage-guided review produced materially more observed review-queue/structural units per selected Story in this epoch."
    else:
        ratios = dict(RATIOS)
        ratio_reason = "The small pilot does not justify changing the default 40/30/15/15 balance; retain it while preserving independent random and counter-model floors."
    layer_counts = Counter()
    for row in info["channels"]:
        layer_counts.update(row["review_queue"]["fact_layers"])
    prioritized_layers = [layer for layer, _count in sorted(layer_counts.items(), key=lambda item: (-item[1], item[0]))]
    if not prioritized_layers:
        prioritized_layers = ["office", "event", "temporal", "family"]
    dense_warning = bool(bias["selection_bias_surfaces"]["graph_guided_dense_person_concentration"])
    return {
        "schema": 1,
        "stage": "x1-1-next-epoch-recommendation",
        "selection_epoch": EPOCH,
        "research_only": True,
        "recommended_x1_2_ratios": ratios,
        "ratio_reason": ratio_reason,
        "long_term_floors": {
            "stratified_random_minimum": 0.10,
            "counter_model_minimum": 0.10,
            "floor_policy": "Retain both independent discovery channels unless a documented source/qualification constraint prevents it.",
        },
        "priorities": {
            "historical_layers": prioritized_layers,
            "primary_action": "review_candidate_ADD_FACT_targets_before_broad_story_materialization",
            "story_expansion": "selective_and_source_gated",
            "person_expansion": "defer_unless_identity_review_finds_a_secure_non_production_bridge",
            "ontology": "review_recurrent_counter_model_surfaces_before_any_HG1_1_ontology_change",
        },
        "selection_channel_findings": {
            "graph_guided": "Use for bridge and heterogeneous-connectivity opportunities, with concentration monitoring." if not dense_warning else "Useful bridge channel, but its dense-person concentration warning argues for stronger coverage/random counterweight.",
            "coverage_guided": "Use for office/event/temporal/family deficits identified from source-backed gaps.",
            "stratified_random": "Maintain as an independent exploration/control channel.",
            "counter_model": "Maintain as an explicit model-blind-spot channel; do not replace it with global low-score sampling.",
        },
        "basis": {
            "information_gain_sha256": sha256_file(INFO_GAIN_PATH),
            "bias_audit_sha256": sha256_file(BIAS_PATH),
            "ontology_gap_sha256": sha256_file(ONTOLOGY_PATH),
        },
        "limitations": [
            "One 20-Story epoch cannot establish causal superiority of a selection strategy.",
            "Accepted X1.1 Stories are a research overlay until downstream participant/punctuation/fact projection is reviewed.",
            "Model disagreement is treated as a review signal, never as evidence against qualified history.",
        ],
        "do_not_execute": ["X1.2", "HG1.1", "ML1.1", "ER2"],
    }


def build() -> dict[str, Any]:
    pool = read("data/derived/x1-1-candidate-pool.json")
    selection = read(SELECTION_PATH)
    review = read(REVIEW_PATH)
    info = information_gain(pool, selection, review)
    bias = bias_audit(pool, selection)
    ontology = ontology_gaps(pool, selection)
    write(INFO_GAIN_PATH, info)
    write(BIAS_PATH, bias)
    write(ONTOLOGY_PATH, ontology)
    rec = recommendation(info, bias, ontology)
    write(RECOMMENDATION_PATH, rec)
    output_hashes = {
        "candidate_pool": sha256_file("data/derived/x1-1-candidate-pool.json"),
        "selection_manifest": sha256_file(SELECTION_PATH),
        "review_results": sha256_file(REVIEW_PATH),
        "information_gain": sha256_file(INFO_GAIN_PATH),
        "bias_audit": sha256_file(BIAS_PATH),
        "ontology_gap_candidates": sha256_file(ONTOLOGY_PATH),
        "next_epoch_recommendation": sha256_file(RECOMMENDATION_PATH),
    }
    summary = {
        "schema": 1,
        "stage": "x1-1-summary",
        "selection_epoch": EPOCH,
        "research_only": True,
        "candidate_pool": pool["counts"],
        "selection": {
            "requested_batch_size": selection["batch_policy"]["requested_batch_size"],
            "requested_ratios": selection["batch_policy"]["ratios"],
            "actual_allocation": selection["batch_policy"]["allocation"],
            "selection_status": selection["selection_status"],
            "snapshot_sha256": selection["selection_snapshot_sha256"],
        },
        "review": review["counts"],
        "information_gain": {
            row["selection_mode"]: row["observed_structure"]
            for row in info["channels"]
        },
        "bias": bias["selection_bias_surfaces"],
        "counter_model_findings": {
            "selected_count": selection["batch_policy"]["allocation"]["counter_model"],
            "independent_signal_story_count": sum(
                1 for row in selection["records"]
                if row["selection_mode"] == "counter_model" and row.get("counter_model_reason")
            ),
            "ontology_gap_candidate_count": len(ontology["candidates"]),
            "interpretation": "Counter-model items are qualified review candidates, not anomalous or historically low-value Stories.",
        },
        "next_epoch": {
            "recommended_ratios": rec["recommended_x1_2_ratios"],
            "historical_layer_priorities": rec["priorities"]["historical_layers"],
            "story_expansion": rec["priorities"]["story_expansion"],
            "person_expansion": rec["priorities"]["person_expansion"],
        },
        "protected_input_hashes": pool["source_artifact_hashes"],
        "x1_1_output_hashes": output_hashes,
        "policy": "X1.1 stops after selection, review screening, comparative audit, and next-epoch recommendation. No HG1.1 or ML1.1 projection is performed.",
    }
    write(SUMMARY_PATH, summary)
    return summary


def main() -> None:
    argparse.ArgumentParser().parse_args()
    summary = build()
    print(json.dumps({
        "stage": summary["stage"],
        "information_gain_channels": list(summary["information_gain"]),
        "ontology_gap_candidates": summary["counter_model_findings"]["ontology_gap_candidate_count"],
        "recommended_x1_2_ratios": summary["next_epoch"]["recommended_ratios"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
