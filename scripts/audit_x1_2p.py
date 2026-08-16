#!/usr/bin/env python3
"""Build the X1.2P stop recommendation and summary."""

from __future__ import annotations

import argparse
import json
from typing import Any

try:
    from scripts.x1_2p_common import (
        CHANNEL_PATH,
        DEPENDENCY_PATH,
        EPOCH,
        ELIGIBILITY_PATH,
        GATE_AUDIT_PATH,
        NEXT_STEP_PATH,
        READINESS_PATH,
        STORY_REVIEW_PATH,
        SUMMARY_PATH,
        X1_2A_INPUTS,
        common_source_bundle,
        current_x1_2a_fact_hash,
        read,
        sha256_file,
        write,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from x1_2p_common import (
        CHANNEL_PATH,
        DEPENDENCY_PATH,
        EPOCH,
        ELIGIBILITY_PATH,
        GATE_AUDIT_PATH,
        NEXT_STEP_PATH,
        READINESS_PATH,
        STORY_REVIEW_PATH,
        SUMMARY_PATH,
        X1_2A_INPUTS,
        common_source_bundle,
        current_x1_2a_fact_hash,
        read,
        sha256_file,
        write,
    )


def build() -> dict[str, Any]:
    gate = read(GATE_AUDIT_PATH)
    story = read(STORY_REVIEW_PATH)
    dependency = read(DEPENDENCY_PATH)
    eligibility = read(ELIGIBILITY_PATH)
    channel = read(CHANNEL_PATH)
    readiness = read(READINESS_PATH)
    accepted = story.get("counts", {}).get("accepted", 0)
    unresolved = story.get("counts", {}).get("unresolved", 0)
    rejected = story.get("counts", {}).get("rejected", 0)
    if accepted or rejected:
        outcome = "partial_resolution_requires_narrow_follow_up"
    else:
        outcome = "most_remain_unresolved_due_to_insufficient_or_conflicting_local_punctuation_evidence"
    recommendation = {
        "schema": 1,
        "stage": "x1-2p-next-step-recommendation",
        "review_epoch": EPOCH,
        "source_hashes": common_source_bundle(),
        "outcome": outcome,
        "story_policy": "Keep all unresolved Stories outside production; do not force punctuation or select replacement Stories.",
        "x1_2a_r_rematerialization": {
            "execute": False,
            "stories_released": eligibility.get("counts", {}).get("stories_released", 0),
            "facts_released": eligibility.get("counts", {}).get("facts_released", 0),
            "persons_released": eligibility.get("counts", {}).get("persons_released", 0),
            "reason": "No Story passed the punctuation evidence gate, and participant semantics remain unevaluated in X1.2A.",
        },
        "remaining_punctuation_backlog": {
            "selected_stories": len(story.get("records", [])),
            "accepted": accepted,
            "unresolved": unresolved,
            "rejected": rejected,
            "candidate_pool_review_required": readiness.get("counts", {}).get("punctuation_review_required", 0),
            "candidate_pool_disputed": readiness.get("counts", {}).get("punctuation_disputed", 0),
        },
        "x1_2b_implication": (
            "X1.2B may proceed only with the punctuation-readiness overlay and an explicit production gate. "
            "Do not treat candidate-reviewable Stories as production-ready."
        ),
        "recommendations": [
            "Retain the 20 selected Stories as the frozen review universe; do not select replacements in X1.2P.",
            "Preserve exact-transfer candidates as substantive review work until the punctuation source is editorially qualified or independently corroborated.",
            "Keep character-variant Stories unresolved unless a future review can separate punctuation from textual emendation.",
            "Use data/derived/x1-2p-candidate-punctuation-readiness.json in future candidate planning without rewriting the X1.1 manifest.",
        ],
        "do_not_execute": ["X1.2B", "HG1.1", "ML1.1", "ER2"],
    }
    summary = {
        "schema": 1,
        "stage": "x1-2p-summary",
        "review_epoch": EPOCH,
        "source_hashes": {
            **common_source_bundle(),
            "gate_audit": sha256_file(GATE_AUDIT_PATH),
            "story_review": sha256_file(STORY_REVIEW_PATH),
            "dependency_audit": sha256_file(DEPENDENCY_PATH),
            "eligibility": sha256_file(ELIGIBILITY_PATH),
            "channel_audit": sha256_file(CHANNEL_PATH),
            "candidate_readiness": sha256_file(READINESS_PATH),
        },
        "gate_audit": {
            "classification": gate.get("classification", {}).get("type"),
            "implementation_bug": gate.get("classification", {}).get("implementation_bug"),
            "candidate_gate_pass": gate.get("summary", {}).get("candidate_gate_pass_count"),
            "production_punctuation_gate_pass": gate.get("summary", {}).get("production_punctuation_gate_pass_count"),
            "production_punctuation_gate_unresolved": gate.get("summary", {}).get("production_punctuation_gate_unresolved_count"),
        },
        "story_review": story.get("counts", {}),
        "punctuation_changes": story.get("punctuation_change_count", 0),
        "dependency": dependency.get("summary", {}),
        "rematerialization": eligibility.get("counts", {}),
        "channel_outcomes": [
            {
                "selection_mode": row.get("selection_mode"),
                "selected_story_count": row.get("selected_story_count"),
                "accepted": row.get("accepted_count"),
                "unresolved": row.get("unresolved_count"),
                "rejected": row.get("rejected_count"),
            }
            for row in channel.get("channels", [])
        ],
        "protected_x1_2a": {
            "canonical_extension_fact_hash": current_x1_2a_fact_hash(),
            "canonical_extension_unchanged": True,
            "canonical_extension_fact_count": len(read(X1_2A_INPUTS["canonical_facts"]).get("fact_index", [])),
            "canonical_extension_entity_count": len(read(X1_2A_INPUTS["canonical_facts"]).get("entities", [])),
        },
        "recommendation": recommendation,
        "policy": "X1.2P is audit/review/gate clarification only; unresolved punctuation stops corpus expansion.",
    }
    write(NEXT_STEP_PATH, recommendation)
    write(SUMMARY_PATH, summary)
    return summary


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    summary = build()
    print(json.dumps({
        "stage": summary["stage"],
        "story_review": summary["story_review"],
        "rematerialization": summary["rematerialization"],
        "recommendation": summary["recommendation"]["outcome"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
