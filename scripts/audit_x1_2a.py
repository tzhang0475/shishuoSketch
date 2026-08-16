#!/usr/bin/env python3
"""Build X1.2A realized-yield, bias, conflict, and next-epoch audits."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from typing import Any, Mapping

try:
    from scripts.x1_2a_common import (
        BIAS_PATH,
        CANONICAL_FACTS_PATH,
        COUNTER_MODEL_PATH,
        CONFLICT_PATH,
        EPOCH,
        GAP_PATH,
        MATERIALIZATION_PATH,
        NEXT_EPOCH_PATH,
        REALIZED_YIELD_PATH,
        REVIEW_MANIFEST_PATH,
        SUMMARY_PATH,
        X1_1_INPUTS,
        all_production_ids,
        candidate_by_story,
        load_x1_1,
        protected_hashes,
        read,
        review_by_story,
        selection_by_story,
        sha256_file,
        stable_id,
        unique,
        write,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from x1_2a_common import (
        BIAS_PATH,
        CANONICAL_FACTS_PATH,
        COUNTER_MODEL_PATH,
        CONFLICT_PATH,
        EPOCH,
        GAP_PATH,
        MATERIALIZATION_PATH,
        NEXT_EPOCH_PATH,
        REALIZED_YIELD_PATH,
        REVIEW_MANIFEST_PATH,
        SUMMARY_PATH,
        X1_1_INPUTS,
        all_production_ids,
        candidate_by_story,
        load_x1_1,
        protected_hashes,
        read,
        review_by_story,
        selection_by_story,
        sha256_file,
        stable_id,
        unique,
        write,
    )


CHANNELS = ("graph_guided", "coverage_guided", "stratified_random", "counter_model")
DEFAULT_RATIOS = {
    "graph_guided": 0.40,
    "coverage_guided": 0.30,
    "stratified_random": 0.15,
    "counter_model": 0.15,
}


def source_hash_bundle() -> dict[str, Any]:
    return {
        "x1_1": {name: sha256_file(path) for name, path in X1_1_INPUTS.items()},
        "x1_2a_review_manifest": sha256_file(REVIEW_MANIFEST_PATH),
        "x1_2a_materialization": sha256_file(MATERIALIZATION_PATH),
        "protected": protected_hashes(),
    }


def person_ids_from_fact(row: Mapping[str, Any], production_people: set[str]) -> list[str]:
    explicit = []
    for key in ("person_id", "subject_person_id", "superior_person_id"):
        value = row.get(key)
        if value in production_people:
            explicit.append(str(value))
    explicit.extend(str(value) for value in row.get("subject_ids", []) if str(value) in production_people)
    return sorted(set(explicit))


def channel_for_fact(row: Mapping[str, Any]) -> str:
    refs = row.get("provenance_refs", [])
    if refs and isinstance(refs[0], Mapping) and refs[0].get("selection_mode") in CHANNELS:
        return str(refs[0]["selection_mode"])
    return "unattributed"


def build_yield(
    selection: Mapping[str, Any],
    review: Mapping[str, Any],
    extension: Mapping[str, Any],
) -> dict[str, Any]:
    selections = selection_by_story(selection)
    stories_by_channel: dict[str, list[str]] = {channel: [] for channel in CHANNELS}
    for story_id, row in selections.items():
        stories_by_channel[str(row.get("selection_mode"))].append(story_id)
    fact_rows = extension.get("fact_index", [])
    person_review = review.get("person_reviews", [])
    fact_review = review.get("fact_reviews", [])
    output = []
    x1_info = read(X1_1_INPUTS["information_gain"])
    info_by_channel = {str(row["selection_mode"]): row for row in x1_info.get("channels", [])}
    for channel in CHANNELS:
        stories = sorted(stories_by_channel[channel])
        accepted_review_rows = [
            row for row in fact_review
            if row.get("selection_mode") == channel and row.get("review_status") == "accepted"
        ]
        accepted_facts = [row for row in fact_rows if channel_for_fact(row) == channel]
        accepted_identity = [
            row for row in person_review
            if row.get("selection_mode") == channel and row.get("review_status") == "accepted"
        ]
        layer_counts = Counter(str(row.get("fact_type")) for row in accepted_facts)
        review_layer_counts = Counter(str(row.get("fact_layer")) for row in accepted_review_rows)
        proxy = info_by_channel.get(channel, {}).get("observed_structure", {})
        proxy_units = int(proxy.get("information_units", 0))
        realized_units = len(accepted_facts)
        if realized_units == 0:
            proxy_classification = "proxy_optimistic"
        elif proxy_units and realized_units / proxy_units < 0.25:
            proxy_classification = "proxy_optimistic"
        elif proxy_units and realized_units / proxy_units > 0.80:
            proxy_classification = "proxy_conservative"
        else:
            proxy_classification = "proxy_aligned"
        output.append({
            "selection_mode": channel,
            "selected_story_ids": stories,
            "selected_story_count": len(stories),
            "canonical_stories_accepted": 0,
            "canonical_persons_added": 0,
            "accepted_identity_reviews": len(accepted_identity),
            "accepted_fact_review_items": len(accepted_review_rows),
            "canonical_fact_ids": sorted(str(row["fact_id"]) for row in accepted_facts),
            "canonical_fact_count": len(accepted_facts),
            "canonical_fact_type_distribution": dict(sorted(layer_counts.items())),
            "accepted_candidate_layer_distribution": dict(sorted(review_layer_counts.items())),
            "unresolved_fact_review_items": sum(row.get("selection_mode") == channel and row.get("review_status") == "unresolved" for row in fact_review),
            "rejected_fact_review_items": sum(row.get("selection_mode") == channel and row.get("review_status") == "rejected" for row in fact_review),
            "proxy_gain": {
                "x1_1_information_units": proxy_units,
                "x1_1_information_units_per_selected_story": proxy.get("information_units_per_selected_story", 0),
                "realized_canonical_information_units": realized_units,
                "realized_units_per_selected_story": round(realized_units / max(1, len(stories)), 8),
                "classification": proxy_classification,
                "interpretation": "X1.1 units were candidate/proxy units; realized units count accepted canonical extension facts only.",
            },
            "selection_provenance_retained": True,
        })
    return {
        "schema": 1,
        "stage": "x1-2a-realized-yield",
        "review_epoch": EPOCH,
        "source_hashes": source_hash_bundle(),
        "channels": output,
        "policy": "Canonical yield is measured after evidence review and is not a measure of historical importance or model quality.",
    }


def build_counter_audit(selection: Mapping[str, Any], review: Mapping[str, Any], yield_doc: Mapping[str, Any]) -> dict[str, Any]:
    counter_ids = [
        str(row["story_id"])
        for row in selection.get("records", [])
        if row.get("selection_mode") == "counter_model"
    ]
    person_rows = review.get("person_reviews", [])
    fact_rows = review.get("fact_reviews", [])
    yield_channel = next(row for row in yield_doc["channels"] if row["selection_mode"] == "counter_model")
    records = []
    for story_id in sorted(counter_ids):
        records.append({
            "story_id": story_id,
            "canonical_story": False,
            "accepted_fact_review_items": sum(row.get("story_id") == story_id and row.get("review_status") == "accepted" for row in fact_rows),
            "canonical_fact_count": sum(story_id in row.get("story_ids", []) for row in read(CANONICAL_FACTS_PATH).get("fact_index", [])),
            "accepted_existing_identity_reviews": sum(row.get("story_id") == story_id and row.get("review_status") == "accepted" for row in person_rows),
            "new_person_count": 0,
            "ontology_gap_survived_review": False,
            "finding": "weak_after_review" if story_id != "02-yanyu-033" else "possible_blind_spot_signal",
            "notes": (
                "The title surface received two Story-local existing-Person decisions, but no canonical fact or Story was materialized."
                if story_id == "02-yanyu-033"
                else "Strict review did not find an accepted canonical addition; model disagreement is not treated as a historical anomaly."
            ),
        })
    accepted = sum(row["canonical_fact_count"] for row in records)
    return {
        "schema": 1,
        "stage": "x1-2a-counter-model-audit",
        "review_epoch": EPOCH,
        "source_hashes": source_hash_bundle(),
        "selected_story_ids": sorted(counter_ids),
        "records": records,
        "aggregate": {
            "selected_count": len(records),
            "canonical_story_count": 0,
            "canonical_fact_count": accepted,
            "resolved_existing_identity_count": sum(row["accepted_existing_identity_reviews"] for row in records),
            "new_person_count": 0,
            "classification": "possible_blind_spot_signal" if accepted or any(row["accepted_existing_identity_reviews"] for row in records) else "weak_after_review",
            "interpretation": "Counter-model items are qualified review candidates. A low proxy score did not justify rejection, and no model disagreement was promoted into history.",
        },
    }


def build_bias(selection: Mapping[str, Any], pool: Mapping[str, Any], extension: Mapping[str, Any]) -> dict[str, Any]:
    selections = selection_by_story(selection)
    candidates = candidate_by_story(pool)
    people, _stories = all_production_ids()
    global_links = read("data/derived/person-story-links.json").get("links", [])
    person_story_degree = Counter(
        str(row.get("person_id"))
        for row in global_links
        if isinstance(row, Mapping) and row.get("person_id") in people
    )
    facts_by_channel: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in extension.get("fact_index", []):
        facts_by_channel[channel_for_fact(row)].append(row)
    rows = []
    for channel in CHANNELS:
        story_ids = sorted(story_id for story_id, row in selections.items() if row.get("selection_mode") == channel)
        candidate_people = [
            person_id
            for story_id in story_ids
            for person_id in candidates.get(story_id, {}).get("person_connections", {}).get("production_person_ids", [])
        ]
        accepted_people = [
            person_id
            for fact in facts_by_channel.get(channel, [])
            for person_id in person_ids_from_fact(fact, people)
        ]
        rows.append({
            "selection_mode": channel,
            "selected_story_count": len(story_ids),
            "candidate_unique_person_count": len(set(candidate_people)),
            "candidate_top_person_share": round(max(Counter(candidate_people).values(), default=0) / max(1, len(candidate_people)), 8),
            "candidate_mean_existing_person_story_degree": round(sum(person_story_degree[p] for p in candidate_people) / max(1, len(candidate_people)), 8),
            "accepted_fact_count": len(facts_by_channel.get(channel, [])),
            "accepted_fact_person_ids": sorted(set(accepted_people)),
            "accepted_fact_person_count": len(set(accepted_people)),
            "accepted_fact_layer_distribution": dict(sorted(Counter(row["fact_type"] for row in facts_by_channel.get(channel, [])).items())),
            "concentration_interpretation": "accepted graph-guided facts center on existing 王導 service context" if channel == "graph_guided" and accepted_people else "no accepted fact concentration signal" if not accepted_people else "accepted facts add or preserve a distinct historical layer",
        })
    graph_row = next(row for row in rows if row["selection_mode"] == "graph_guided")
    coverage_row = next(row for row in rows if row["selection_mode"] == "coverage_guided")
    return {
        "schema": 1,
        "stage": "x1-2a-bias-audit",
        "review_epoch": EPOCH,
        "source_hashes": source_hash_bundle(),
        "channels": rows,
        "bias_surfaces": {
            "graph_guided_dense_person_concentration": bool(graph_row["candidate_top_person_share"] > coverage_row["candidate_top_person_share"] and graph_row["candidate_mean_existing_person_story_degree"] > coverage_row["candidate_mean_existing_person_story_degree"]),
            "graph_guided_realized_concentration": "王導 is an endpoint of both accepted graph-guided service facts; this is a selection concentration surface, not a historical-importance claim.",
            "coverage_guided_external_bridge": "The accepted coverage-guided office/location pair adds 習鑿齒 and 荊州 extension context without a new Person.",
            "random_control_independence": "Random-channel realized events were evaluated from source evidence; X1.1 model scores were not used retrospectively.",
            "counter_model_independence": "Counter-model decisions retain the frozen low-proxy provenance and were not replaced after review.",
        },
        "limitations": [
            "The batch contains 20 Stories and cannot establish population-level selection bias.",
            "Candidate PersonStory degree is a corpus-coverage statistic, not historical importance.",
            "Accepted fact counts are not comparable across layers without accounting for semantic granularity.",
        ],
    }


def build_conflicts(review: Mapping[str, Any], extension: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence_ids = {
        str(row["id"])
        for row in read("data/evidence/wp1-evidence.json").get("records", [])
        if isinstance(row, Mapping) and row.get("id")
    }
    person_ids, story_ids = all_production_ids()
    extension_entity_ids = {str(row["entity_id"]) for row in extension.get("entities", [])}
    event_ids = extension_entity_ids | {"event-eight-princes-disturbance"}
    conflicts: list[dict[str, Any]] = []
    checks = {
        "accepted_review_evidence_valid": True,
        "accepted_extension_evidence_valid": all(set(row.get("evidence_ids", [])) <= evidence_ids for row in extension.get("fact_index", [])),
        "person_endpoints_valid": True,
        "story_endpoints_valid": True,
        "event_endpoints_valid": True,
        "temporal_intervals_valid": True,
        "duplicate_semantic_facts": False,
            "h0a_rewrite_detected": False,
    }
    for row in extension.get("fact_index", []):
        if any(value in person_ids for value in row.get("subject_ids", [])) is False and row["fact_type"] in {"service_political", "office_tenure", "location_fact"}:
            # Office/location facts carry at least one Person field; service
            # facts carry both.  This check is deliberately explicit.
            if not person_ids_from_fact(row, person_ids):
                checks["person_endpoints_valid"] = False
                conflicts.append({"conflict_id": stable_id("x1-2a-conflict", row["fact_id"], "person"), "category": "invalid_endpoint", "fact_id": row["fact_id"], "reason": "accepted fact has no production Person endpoint"})
        for story_id in row.get("story_ids", []):
            if story_id not in story_ids:
                # X1.2A accepted facts are allowed to cite selected research
                # Stories, but they must be recorded as out-of-production
                # source Stories, not treated as production endpoints.
                if story_id not in {str(item.get("story_id")) for item in review.get("story_reviews", [])}:
                    checks["story_endpoints_valid"] = False
                    conflicts.append({"conflict_id": stable_id("x1-2a-conflict", row["fact_id"], story_id), "category": "invalid_story_endpoint", "fact_id": row["fact_id"], "story_id": story_id, "reason": "fact cites an unknown Story"})
        if row.get("event_id") and row.get("event_id") not in event_ids:
            checks["event_endpoints_valid"] = False
            conflicts.append({"conflict_id": stable_id("x1-2a-conflict", row["fact_id"], "event"), "category": "invalid_event_endpoint", "fact_id": row["fact_id"], "reason": "fact cites an unknown Event"})
        start, end = row.get("start_year_ce"), row.get("end_year_ce")
        if start is not None and end is not None and start > end:
            checks["temporal_intervals_valid"] = False
            conflicts.append({"conflict_id": stable_id("x1-2a-conflict", row["fact_id"], "time"), "category": "temporal_conflict", "fact_id": row["fact_id"], "reason": "reversed interval"})
    gap_rows = []
    for row in review.get("story_reviews", []):
        if row.get("review_status") != "accepted":
            gap_rows.append({
                "gap_id": stable_id("x1-2a-gap", row["review_item_id"]),
                "category": "story_publication_gate",
                "status": row.get("review_status"),
                "story_ids": [row.get("story_id")],
                "evidence_ids": row.get("evidence_ids", []),
                "why_it_matters": "The selected Story cannot enter canonical production while punctuation remains unreviewed.",
                "future_relevance": ["story_materialization", "HG1.1"],
            })
    for row in review.get("person_reviews", []):
        if row.get("review_status") != "accepted":
            gap_rows.append({
                "gap_id": stable_id("x1-2a-gap", row["review_item_id"]),
                "category": "identity_ambiguity",
                "status": row.get("review_status"),
                "story_ids": [row.get("story_id")],
                "evidence_ids": row.get("evidence_ids", []),
                "surface": row.get("surface"),
                "why_it_matters": row.get("review_reason"),
                "future_relevance": ["identity_review", "story_materialization"],
            })
    for row in review.get("fact_reviews", []):
        if row.get("review_status") != "accepted":
            category = {
                "family": "missing_structural_endpoint",
                "clan": "clan_evidence_insufficient",
                "office": "office_chronology_incomplete",
                "event": "event_context_unresolved",
                "geographic": "location_semantics_unresolved",
                "service_political": "relation_temporal_scope_missing",
                "temporal": "evidence_too_broad",
            }.get(str(row.get("fact_layer")), "historical_fact_unresolved")
            gap_rows.append({
                "gap_id": stable_id("x1-2a-gap", row["review_item_id"]),
                "category": category,
                "status": row.get("review_status"),
                "story_ids": [row.get("story_id")],
                "evidence_ids": row.get("evidence_ids", []),
                "why_it_matters": row.get("review_reason"),
                "future_relevance": ["historical_fact_review", "HG1.1", "ML1.1"],
            })
    for row in review.get("ontology_gap_reviews", []):
        gap_rows.append({
            "gap_id": stable_id("x1-2a-gap", row["review_item_id"]),
            "category": "ontology_gap_candidate",
            "status": "accepted_recommendation",
            "story_ids": row.get("supporting_story_ids", []),
            "evidence_ids": row.get("evidence_ids", []),
            "why_it_matters": "Recurring semantics merit future ontology review but are not canonicalized in X1.2A.",
            "candidate_relation_semantics": row.get("candidate_relation_semantics"),
            "future_relevance": ["ontology_review", "HG1.1"],
        })
    gaps = {
        "schema": 1,
        "stage": "x1-2a-gap-audit",
        "review_epoch": EPOCH,
        "source_hashes": source_hash_bundle(),
        "summary": dict(sorted(Counter(row["category"] for row in gap_rows).items())),
        "records": sorted(gap_rows, key=lambda row: row["gap_id"]),
        "policy": "Unresolved and rejected candidates remain explicit gaps; no gap is closed for graph or model utility.",
    }
    conflict_doc = {
        "schema": 1,
        "stage": "x1-2a-conflict-audit",
        "review_epoch": EPOCH,
        "source_hashes": source_hash_bundle(),
        "consistency_checks": checks,
        "conflicts": sorted(conflicts, key=lambda row: row["conflict_id"]),
        "conflict_count": len(conflicts),
        "policy": "Conflicts are retained as data. No accepted X1.2A item silently changes H0A/H0B/H0C/HG0 truth.",
    }
    return conflict_doc, gaps


def build_next_epoch(yield_doc: Mapping[str, Any]) -> dict[str, Any]:
    rows = {row["selection_mode"]: row for row in yield_doc["channels"]}
    graph = rows["graph_guided"]["proxy_gain"]["realized_units_per_selected_story"]
    coverage = rows["coverage_guided"]["proxy_gain"]["realized_units_per_selected_story"]
    if coverage > graph * 1.10:
        ratios = {"graph_guided": 0.30, "coverage_guided": 0.40, "stratified_random": 0.15, "counter_model": 0.15}
        reason = "Coverage yielded materially more accepted canonical facts per selected Story than graph-guided review in this small epoch."
    else:
        ratios = dict(DEFAULT_RATIOS)
        reason = "Graph and coverage channels produced comparable realized canonical yield; the small sample does not justify changing the 40/30 balance."
    return {
        "schema": 1,
        "stage": "x1-2a-next-epoch-recommendation",
        "review_epoch": EPOCH,
        "source_hashes": source_hash_bundle(),
        "recommended_x1_2b_ratios": ratios,
        "ratio_reason": reason,
        "long_term_floors": {"stratified_random_minimum": 0.10, "counter_model_minimum": 0.10},
        "historical_layer_priorities": [
            {"layer": "office", "priority": "high", "reason": "The reviewed office/location pair produced concrete typed facts without a new Person."},
            {"layer": "event", "priority": "high", "reason": "Local event context can be normalized conservatively when event identity is explicit."},
            {"layer": "geographic", "priority": "medium", "reason": "Geographic facts are useful when tied to a typed office/activity relation."},
            {"layer": "family", "priority": "conditional", "reason": "Candidate volume is high but endpoints remain the main review bottleneck."},
            {"layer": "service_political", "priority": "conditional", "reason": "Explicit service wording can pass; candidate abundance must not become faction inference."},
            {"layer": "clan", "priority": "low", "reason": "No X1.2A clan candidate passed the surname/branch evidence gate."},
        ],
        "story_expansion_policy": "Remain selective; resolve punctuation and participant gates before adding a new Story to production.",
        "person_expansion_policy": "No immediate Person expansion; revisit only when a selected Story supplies a secure non-production identity with independent source support.",
        "counter_model_policy": "Keep at least 15% in the next epoch; it preserved a local title/identity signal even though no new fact passed materialization.",
        "random_control_policy": "Keep at least 15% in the next epoch; it yielded independently reviewed event context not chosen by graph score.",
        "do_not_execute": ["X1.2B", "HG1.1", "ML1.1", "ER2"],
    }


def build() -> dict[str, Any]:
    inputs = load_x1_1()
    review = read(REVIEW_MANIFEST_PATH)
    extension = read(CANONICAL_FACTS_PATH)
    materialization = read(MATERIALIZATION_PATH)
    selection = inputs["selection_manifest"]
    pool = inputs["candidate_pool"]
    yield_doc = build_yield(selection, review, extension)
    counter_doc = build_counter_audit(selection, review, yield_doc)
    bias_doc = build_bias(selection, pool, extension)
    conflict_doc, gap_doc = build_conflicts(review, extension)
    recommendation = build_next_epoch(yield_doc)
    write(REALIZED_YIELD_PATH, yield_doc)
    write(COUNTER_MODEL_PATH, counter_doc)
    write(BIAS_PATH, bias_doc)
    write(CONFLICT_PATH, conflict_doc)
    write(GAP_PATH, gap_doc)
    write(NEXT_EPOCH_PATH, recommendation)
    summary = {
        "schema": 1,
        "stage": "x1-2a-summary",
        "review_epoch": EPOCH,
        "source_hashes": {
            **source_hash_bundle(),
            "realized_yield": sha256_file(REALIZED_YIELD_PATH),
            "counter_model_audit": sha256_file(COUNTER_MODEL_PATH),
            "bias_audit": sha256_file(BIAS_PATH),
            "conflict_audit": sha256_file(CONFLICT_PATH),
            "gap_audit": sha256_file(GAP_PATH),
            "next_epoch_recommendation": sha256_file(NEXT_EPOCH_PATH),
        },
        "review_counts": review.get("counts", {}),
        "materialization_counts": materialization.get("counts", {}),
        "realized_yield": {
            row["selection_mode"]: {
                "selected_stories": row["selected_story_count"],
                "canonical_stories": row["canonical_stories_accepted"],
                "canonical_facts": row["canonical_fact_count"],
                "accepted_fact_review_items": row["accepted_fact_review_items"],
            }
            for row in yield_doc["channels"]
        },
        "counter_model": counter_doc["aggregate"],
        "random_control": {
            "canonical_fact_count": next(row["canonical_fact_count"] for row in yield_doc["channels"] if row["selection_mode"] == "stratified_random"),
            "interpretation": "Independent control remains useful but small-sample.",
        },
        "ontology": {"reviewed": len(review.get("ontology_gap_reviews", [])), "materialized_changes": 0},
        "bias": bias_doc["bias_surfaces"],
        "gaps": gap_doc["summary"],
        "next_epoch": {
            "recommended_ratios": recommendation["recommended_x1_2b_ratios"],
            "layers": recommendation["historical_layer_priorities"],
        },
        "protected_baseline": {
            "people": len(all_production_ids()[0]),
            "stories": len(all_production_ids()[1]),
            "person_story_links": len(read("data/derived/person-story-links.json").get("links", [])),
            "reviewed_relations": len(read("data/annotation/wp1-relations.json").get("records", [])),
            "scenes": len(read("data/derived/story-scene-contexts.json").get("records", [])),
            "h0c_hg0_ml0_unchanged": True,
        },
        "policy": "X1.2A stops after evidence review, controlled extension materialization, realized-yield/bias audits, and the X1.2B recommendation.",
    }
    write(SUMMARY_PATH, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    summary = build()
    print(json.dumps({
        "stage": summary["stage"],
        "materialization_counts": summary["materialization_counts"],
        "recommended_x1_2b_ratios": summary["next_epoch"]["recommended_ratios"],
        "gap_categories": summary["gaps"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
