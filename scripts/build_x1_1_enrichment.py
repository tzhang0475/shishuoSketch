#!/usr/bin/env python3
"""Screen the frozen X1.1 selection into a non-canonical review overlay.

This builder intentionally stops before canonical production materialization.
It records what can be accepted for the next projection and what still needs
historical review.  In particular, PersonStory identity links are not
silently promoted to Story participation or new historical facts.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any, Mapping

try:
    from scripts.x1_1_common import (
        EPOCH,
        POOL_PATH,
        REVIEW_PATH,
        SELECTION_PATH,
        build_context,
        read,
        sha256_file,
        unique,
        write,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from x1_1_common import (
        EPOCH,
        POOL_PATH,
        REVIEW_PATH,
        SELECTION_PATH,
        build_context,
        read,
        sha256_file,
        unique,
        write,
    )


LAYER_FACT_TYPES = {
    "office": ["Office", "OfficeTenure"],
    "event": ["Event", "EventParticipation"],
    "temporal": ["StoryTemporalConstraint", "PersonActivityCandidate"],
    "family": ["KinshipFact", "MarriageUnion"],
    "clan": ["ClanMembership"],
    "geographic": ["LocationFact", "PersonActivity"],
    "service_political": ["ServicePoliticalFact", "RelationTemporalContext"],
}


def build() -> dict[str, Any]:
    pool = read(POOL_PATH)
    selection = read(SELECTION_PATH)
    context = build_context()
    pool_by_id = {str(row["story_id"]): row for row in pool.get("records", [])}
    records: list[dict[str, Any]] = []
    fact_candidate_count = 0
    person_candidate_count = 0
    action_counts: Counter[str] = Counter()
    action_status_counts: Counter[str] = Counter()
    for selected in sorted(selection.get("records", []), key=lambda row: int(row.get("global_selection_rank", 0))):
        story_id = str(selected["story_id"])
        candidate = pool_by_id[story_id]
        person_ids = list(candidate["person_connections"]["production_person_ids"])
        evidence_ids = list(candidate["evidence"]["local_evidence_ids"])
        missing_layers = list(candidate["coverage"]["missing_layers_for_connected_persons"])
        unresolved_mentions = context["mentions_by_story"].get(story_id, [])
        unresolved_surfaces = unique(
            mention.get("surface")
            for mention in unresolved_mentions
            if not isinstance(mention.get("person_id"), str) or mention.get("person_id") not in context["people"]
        )
        actions: list[dict[str, Any]] = []

        fact_targets = [
            {
                "layer": layer,
                "candidate_fact_types": LAYER_FACT_TYPES[layer],
                "status": "review_queue",
                "accepted": False,
                "review_status": "candidate",
                "reason": "The Story exposes a coverage opportunity, but X1.1 does not promote a semantic fact from a keyword or PersonStory link alone.",
            }
            for layer in missing_layers
        ]
        if fact_targets:
            fact_candidate_count += len(fact_targets)
            actions.append({
                "action": "ADD_FACT",
                "status": "candidate_review_queue",
                "accepted": False,
                "targets": fact_targets,
                "evidence_ids": evidence_ids,
                "reason": "Coverage-guided review target; requires source-level semantic review before canonicalization.",
            })
            action_counts["ADD_FACT"] += len(fact_targets)
            action_status_counts["ADD_FACT:candidate_review_queue"] += len(fact_targets)

        actions.append({
            "action": "ADD_STORY",
            "status": "accepted_for_x1_1_review_overlay",
            "accepted": True,
            "canonical_production_materialization": "deferred_to_HG1_1",
            "reason": "Canonical source and stable identity/evidence route passed X1.1 screening; reader publication and participant projection remain separate gates.",
        })
        action_counts["ADD_STORY"] += 1
        action_status_counts["ADD_STORY:accepted_for_x1_1_review_overlay"] += 1

        if unresolved_surfaces:
            person_candidate_count += len(unresolved_surfaces)
            actions.append({
                "action": "ADD_PERSON",
                "status": "identity_review_required",
                "accepted": False,
                "surfaces": unresolved_surfaces,
                "related_production_person_ids": person_ids,
                "reason": "Non-production or unresolved surfaces are recorded for identity review only; no new Person is allocated in X1.1.",
            })
            action_counts["ADD_PERSON"] += len(unresolved_surfaces)
            action_status_counts["ADD_PERSON:identity_review_required"] += len(unresolved_surfaces)

        records.append({
            "story_id": story_id,
            "selection_epoch": EPOCH,
            "selection_mode": selected["selection_mode"],
            "selection_rank": selected["selection_rank"],
            "selection_status": "selected",
            "review_status": "candidate",
            "selection_manifest_frozen": True,
            "source": candidate["source"],
            "production_person_ids": person_ids,
            "production_person_names": candidate["person_connections"]["production_person_names"],
            "evidence_ids": evidence_ids,
            "link_ids": candidate["person_connections"]["link_ids"],
            "identity_review": {
                "resolved_production_person_path": bool(person_ids),
                "non_production_or_unresolved_surfaces": unresolved_surfaces,
                "person_story_is_not_participation": True,
                "scene_participant_status": "deferred_to_hg1_1_participant_review",
            },
            "review_checks": {
                "canonical_source_exists": True,
                "canonical_source_hash_present": bool(candidate["source"].get("sha256")),
                "outside_current_production_scope": True,
                "punctuation_not_disputed": candidate["evidence"].get("punctuation_status") != "disputed",
                "local_evidence_traceable": bool(evidence_ids),
                "identity_route_reviewable": bool(person_ids),
                "reader_publication_ready": False,
                "participant_projection_materialized": False,
            },
            "enrichment_priorities": {
                "high": [layer for layer in missing_layers if layer in {"office", "event", "temporal", "family"}],
                "medium": [layer for layer in missing_layers if layer in {"clan", "geographic", "service_political"}],
            },
            "actions": actions,
            "screening_status": "completed",
            "acceptance_status": "accepted_for_x1_1_review_overlay",
            "canonical_status": "not_materialized",
        })

    return {
        "schema": 1,
        "stage": "x1-1-review-results",
        "selection_epoch": EPOCH,
        "research_only": True,
        "source_selection_manifest": str(SELECTION_PATH),
        "source_selection_manifest_sha256": sha256_file(SELECTION_PATH),
        "source_candidate_pool": str(POOL_PATH),
        "source_candidate_pool_sha256": sha256_file(POOL_PATH),
        "review_policy": {
            "accepted_scope": "frozen X1.1 research overlay only",
            "canonical_facts_added": False,
            "canonical_stories_added": False,
            "canonical_persons_added": False,
            "participant_projection_added": False,
            "person_story_does_not_imply_participation": True,
            "model_output_does_not_create_facts": True,
            "missing_edges_are_not_negative_facts": True,
        },
        "counts": {
            "selected_story_count": len(records),
            "accepted_story_overlay_count": sum(row["acceptance_status"] == "accepted_for_x1_1_review_overlay" for row in records),
            "rejected_story_count": 0,
            "canonical_story_addition_count": 0,
            "canonical_fact_addition_count": 0,
            "canonical_person_addition_count": 0,
            "candidate_fact_action_count": fact_candidate_count,
            "person_identity_review_candidate_count": person_candidate_count,
            "action_counts": dict(sorted(action_counts.items())),
            "action_status_counts": dict(sorted(action_status_counts.items())),
        },
        "records": records,
        "policy": "X1.1 completes selection and historical review screening; HG1.1 must perform the downstream canonical projection only after participant, punctuation, and fact-level review.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(REVIEW_PATH))
    args = parser.parse_args()
    document = build()
    write(Path(args.output), document)
    print(json.dumps({
        "stage": document["stage"],
        "selected": document["counts"]["selected_story_count"],
        "accepted_overlay": document["counts"]["accepted_story_overlay_count"],
        "candidate_fact_actions": document["counts"]["candidate_fact_action_count"],
        "person_identity_candidates": document["counts"]["person_identity_review_candidate_count"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
