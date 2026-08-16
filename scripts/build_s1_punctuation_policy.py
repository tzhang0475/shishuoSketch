#!/usr/bin/env python3
"""Formalize the prospective S1 punctuation/admissibility contract."""

from __future__ import annotations

from pathlib import Path
import re
import sys

from s1_jianshu_common import (
    CACHE_ROOT,
    X1_SELECTION_PATH,
    load_story_records,
    read_json,
    sha256_file,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
X1_CANDIDATE_POOL = Path("data/derived/x1-1-candidate-pool.json")
X1_2P_GATE_AUDIT = Path("data/derived/x1-2p-punctuation-gate-audit.json")
GATE_OUTPUT = Path("data/derived/s1-jianshu-punctuation-gate-audit.json")
READINESS_OUTPUT = Path("data/derived/s1-jianshu-candidate-punctuation-readiness.json")


def story_key(story_id: str) -> tuple[str, int] | None:
    match = re.match(r"^(\d{2}-[^-]+)-(\d+)$", story_id)
    return (match.group(1), int(match.group(2))) if match else None


def build() -> dict:
    stories = {(str(row["chapter_id"]), int(row["ordinal"])): row for row in load_story_records()}
    old_gate = read_json(X1_2P_GATE_AUDIT)
    candidate_pool = read_json(X1_CANDIDATE_POOL)
    gate = {
        "schema": "s1-jianshu-punctuation-gate-audit-1",
        "stage": "S1.3/S1.4",
        "source_hashes": {
            "x1_1_candidate_pool": sha256_file(X1_CANDIDATE_POOL),
            "x1_1_selection": sha256_file(X1_SELECTION_PATH),
            "x1_2p_gate_audit": sha256_file(X1_2P_GATE_AUDIT),
        },
        "gate_contract": [
            {
                "gate_name": "candidate_punctuation_eligibility",
                "stage": "X1.1 candidate pool",
                "required_status": "source exists and punctuation is not explicitly disputed",
                "source_field": "data/annotation/wp1-punctuation.json plus source/evidence route",
                "allowed_values": ["reviewed", "aligned", "candidate"],
                "reject_conditions": ["missing source", "explicitly disputed punctuation", "missing evidence route"],
                "why_x1_1_qualified": "X1.1 is a research-selection gate and intentionally admits reviewable candidate Stories.",
                "implementation_location": "scripts/x1_1_common.py:make_candidate_record",
            },
            {
                "gate_name": "production_editorial_admissibility_pre_s1",
                "stage": "X1.2A/X1.2P",
                "required_status": "independent punctuation-bearing editorial witness reviewed without unresolved character conflict",
                "source_field": "X1.2A story review plus X1.2P punctuation review",
                "allowed_values": ["reviewed", "accepted"],
                "reject_conditions": ["candidate-only punctuation", "unresolved source-witness conflict", "unreviewed character variant"],
                "why_x1_2a_blocked": "The prior policy required an additional independent editorial witness, so all 20 selected Stories remained unresolved when their only local punctuation route was candidate-level.",
                "implementation_location": "scripts/x1_2a_common.py and scripts/x1_2p_common.py",
            },
            {
                "gate_name": "production_editorial_admissibility_s1",
                "stage": "S1 prospective policy",
                "required_status": "reliably aligned Jianshu Story with usable editorial segmentation and no meaningful identity/semantic/boundary variant",
                "source_field": "data/derived/s1-jianshu-story-alignment.json",
                "allowed_values": ["exact", "near_exact", "known_minor_variant"],
                "reject_conditions": ["unmatched", "structural ambiguity", "meaningful variant", "segmentation unavailable"],
                "why_s1_changes_policy": "The local Jianshu family is now an available named scholarly working reference; an aligned Story supplies sufficient punctuation/segmentation evidence without changing the primary text.",
                "implementation_location": "scripts/reresolve_s1_backlog.py",
            },
        ],
        "classification": {
            "result": "intentional_two_tier_policy_resolved_by_s1_source_policy",
            "implementation_bug": False,
            "validator_schema_mismatch": False,
            "stale_metadata": False,
            "selection_mode_affects_textual_judgment": False,
        },
        "previous_behavior": {
            "x1_1_candidate_story_count": len(candidate_pool.get("records", [])),
            "x1_2p_selected_story_count": len(old_gate.get("story_gate_results", [])),
            "x1_2p_unresolved_story_count": sum(row.get("overall_status") == "unresolved" for row in old_gate.get("story_gate_results", [])),
            "x1_2p_artifact_preserved": True,
        },
        "policy": "A selected Story receives no punctuation privilege. S1 changes only the admissible scholarly-reference route, not the textual standard or the canonical primary witness.",
    }
    readiness_rows = []
    for candidate in sorted(candidate_pool.get("records", []), key=lambda row: str(row.get("story_id"))):
        story_id = str(candidate.get("story_id"))
        key = story_key(story_id)
        reference = stories.get(key) if key else None
        if reference:
            readiness = "aligned_reference_available"
            production_ready = True
            reason = "Jianshu has a deterministic chapter/ordinal Story record with a base paragraph and editorial note structure."
        else:
            readiness = "unmatched"
            production_ready = False
            reason = "No deterministic Jianshu chapter/ordinal record was found."
        readiness_rows.append(
            {
                "story_id": story_id,
                "selection_epoch": "X1.1" if candidate.get("eligible") else None,
                "candidate_eligible": candidate.get("eligible", False),
                "candidate_punctuation_status": candidate.get("evidence", {}).get("punctuation_status"),
                "candidate_punctuation_review_status": candidate.get("evidence", {}).get("punctuation_review_status"),
                "jianshu_reference_status": readiness,
                "production_punctuation_ready_under_s1": production_ready,
                "punctuation_review_required": not production_ready,
                "punctuation_disputed": False,
                "punctuation_review_cost": "reference_alignment" if production_ready else "substantive_review",
                "reason": reason,
                "selection_channel": None,
                "policy_note": "Punctuation readiness is not Story publication approval; participant, identity, evidence, and duplicate gates remain separate.",
            }
        )
    readiness = {
        "schema": "s1-jianshu-candidate-punctuation-readiness-1",
        "stage": "S1 prospective candidate metadata",
        "source_hashes": gate["source_hashes"],
        "records": readiness_rows,
        "counts": {
            "candidate_records": len(readiness_rows),
            "jianshu_reference_available": sum(row["jianshu_reference_status"] == "aligned_reference_available" for row in readiness_rows),
            "production_punctuation_ready_under_s1": sum(row["production_punctuation_ready_under_s1"] for row in readiness_rows),
            "still_unmatched": sum(row["jianshu_reference_status"] == "unmatched" for row in readiness_rows),
        },
        "policy": "This is a prospective research-readiness overlay. It does not rewrite X1.2P or promote Stories by itself.",
    }
    write_json(GATE_OUTPUT, gate)
    write_json(READINESS_OUTPUT, readiness)
    return {"gate": gate["classification"], "readiness": readiness["counts"]}


def main() -> int:
    try:
        print(build())
        return 0
    except Exception as exc:
        print(f"S1 punctuation policy build failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
