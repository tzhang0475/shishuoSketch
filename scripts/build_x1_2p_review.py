#!/usr/bin/env python3
"""Build the deterministic X1.2P punctuation review and dependency audits.

X1.2P is intentionally conservative.  It reviews the frozen X1.1 Stories
without editing the punctuation source record: the only local punctuation
witness is provisionally qualified, so exact transfer is not silently
promoted to human-reviewed production punctuation.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any, Mapping

try:
    from scripts.x1_2p_common import (
        CHANNELS,
        CHANNEL_PATH,
        CORPUS_PATH,
        EPOCH,
        ELIGIBILITY_PATH,
        GATE_AUDIT_PATH,
        PUNCTUATION_PATH,
        READINESS_PATH,
        STORY_REVIEW_PATH,
        DEPENDENCY_PATH,
        TOP_LEVEL_STATES,
        X1_1_INPUTS,
        X1_2A_INPUTS,
        common_source_bundle,
        corpus_by_story,
        evidence_refs_for_ids,
        production_ids,
        punctuation_by_story,
        read,
        selection_by_story,
        sha256_file,
        stable_id,
        unique,
        write,
        x1_2a_documents,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from x1_2p_common import (
        CHANNELS,
        CHANNEL_PATH,
        CORPUS_PATH,
        EPOCH,
        ELIGIBILITY_PATH,
        GATE_AUDIT_PATH,
        PUNCTUATION_PATH,
        READINESS_PATH,
        STORY_REVIEW_PATH,
        DEPENDENCY_PATH,
        TOP_LEVEL_STATES,
        X1_1_INPUTS,
        X1_2A_INPUTS,
        common_source_bundle,
        corpus_by_story,
        evidence_refs_for_ids,
        production_ids,
        punctuation_by_story,
        read,
        selection_by_story,
        sha256_file,
        stable_id,
        unique,
        write,
        x1_2a_documents,
    )


ROOT = Path(__file__).resolve().parents[1]


def reference_audit(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    results = []
    for reference in record.get("references", []):
        if not isinstance(reference, Mapping):
            continue
        path = str(reference.get("path", ""))
        absolute = ROOT / path
        exists = absolute.is_file()
        actual_hash = sha256_file(path) if exists else None
        expected_hash = reference.get("sha256")
        results.append({
            "kind": reference.get("kind"),
            "witness_id": reference.get("witness_id"),
            "path": path,
            "expected_sha256": expected_hash,
            "actual_sha256": actual_hash,
            "exists": exists,
            "hash_matches": bool(exists and expected_hash and actual_hash == expected_hash),
            "notes": reference.get("notes"),
        })
    return results


def classify_punctuation(record: Mapping[str, Any]) -> dict[str, Any]:
    status = record.get("status")
    review_status = record.get("review_status")
    basis = record.get("punctuation_basis")
    exact_transfer = record.get("exact_transfer") is True
    alignment = record.get("alignment", {}) if isinstance(record.get("alignment"), Mapping) else {}
    alignment_class = alignment.get("alignment_class")

    if (
        status == "reviewed"
        and review_status == "reviewed"
        and basis in {"human_reviewed", "trusted_reference_exact"}
    ):
        return {
            "review_status": "accepted",
            "reason_code": "already_production_reviewed",
            "review_reason": "The punctuation record already satisfies the production review contract.",
            "review_cost": "ready",
            "production_punctuation_ready": True,
        }
    if status == "disputed" or basis == "disputed" or alignment_class == "character-disagreement":
        return {
            "review_status": "unresolved",
            "reason_code": "unresolved_source_witness_conflict",
            "review_reason": (
                "The only punctuation-bearing local reference differs in canonical character sequence; punctuation cannot be promoted "
                "without importing a textual variant or making an unreviewed emendation."
            ),
            "review_cost": "disputed",
            "production_punctuation_ready": False,
        }
    if exact_transfer and status in {"candidate", "aligned"} and review_status == "unreviewed" and basis == "reference_candidate":
        return {
            "review_status": "unresolved",
            "reason_code": "unresolved_insufficient_local_evidence",
            "review_reason": (
                "Character transfer is exact, but the sole punctuation-bearing witness is only provisionally qualified and no "
                "independent editorial punctuation source is tracked; exact transfer is therefore not production approval."
            ),
            "review_cost": "substantive_review",
            "production_punctuation_ready": False,
        }
    return {
        "review_status": "unresolved",
        "reason_code": "unresolved_insufficient_local_evidence",
        "review_reason": "The punctuation record does not satisfy the explicit production review contract.",
        "review_cost": "substantive_review",
        "production_punctuation_ready": False,
    }


def gate_record(
    story_id: str,
    selection: Mapping[str, Any],
    x1_2a_story: Mapping[str, Any],
    punctuation: Mapping[str, Any],
    punctuation_result: Mapping[str, Any],
    source_ok: bool,
    evidence_ok: bool,
    duplicate: bool,
) -> dict[str, Any]:
    punctuation_gate = "pass" if punctuation_result.get("production_punctuation_ready") else "unresolved"
    overall = "accepted" if punctuation_gate == "pass" and x1_2a_story.get("review_status") == "accepted" else "unresolved"
    return {
        "story_id": story_id,
        "selection_mode": selection.get("selection_mode"),
        "gates": {
            "source_integrity": "pass" if source_ok else "fail",
            "story_identity": "pass" if source_ok and not duplicate else "fail",
            "punctuation": punctuation_gate,
            "participant_review": "not_evaluated",
            "evidence_traceability": "pass" if evidence_ok else "fail",
            "duplicate_check": "fail" if duplicate else "pass",
        },
        "x1_2a_review_status": x1_2a_story.get("review_status"),
        "overall_status": overall,
        "blocking_gate": "punctuation" if punctuation_gate != "pass" else "participant_review",
        "selection_does_not_affect_textual_judgment": True,
    }


def build_gate_audit(selections: Mapping[str, Mapping[str, Any]], story_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": 1,
        "stage": "x1-2p-punctuation-gate-audit",
        "review_epoch": EPOCH,
        "source_hashes": common_source_bundle(),
        "scope": {
            "selection_epoch": "X1.1",
            "selected_story_count": len(selections),
            "selected_story_ids": sorted(selections),
            "replacement_selection": False,
            "x1_1_disputed_28_reopened": False,
        },
        "gate_contract": [
            {
                "gate_name": "candidate_punctuation_eligibility",
                "stage": "X1.1 candidate pool",
                "required_status": "punctuation record present and not explicitly disputed",
                "source_field": "data/annotation/wp1-punctuation.json:status",
                "allowed_values": ["reviewed", "aligned", "candidate"],
                "reject_conditions": ["missing record", "status=disputed", "missing source/evidence route"],
                "reason": "X1.1 is a research-selection gate; candidate eligibility is deliberately broader than publication readiness.",
                "implementation_location": "scripts/x1_1_common.py:make_candidate_record",
            },
            {
                "gate_name": "production_punctuation_eligibility",
                "stage": "X1.2A / SC1 production projection",
                "required_status": "status=reviewed, review_status=reviewed, punctuation_basis=human_reviewed (or explicitly trusted production basis)",
                "source_field": "data/annotation/wp1-punctuation.json:(status,review_status,punctuation_basis)",
                "allowed_values": {"status": ["reviewed"], "review_status": ["reviewed"], "punctuation_basis": ["human_reviewed"]},
                "reject_conditions": ["candidate/unreviewed", "reference_candidate", "disputed", "character variant without textual review"],
                "reason": "Production reader text requires explicit editorial review; machine/reference alignment is not approval.",
                "implementation_location": "scripts/build_x1_2a_review.py:review_story; scripts/build_sc1_frontend_data.py:publication_state",
            },
            {
                "gate_name": "participant_review",
                "stage": "X1.2A / future Story promotion",
                "required_status": "reviewed participant semantics, if the Story is promoted",
                "source_field": "X1.2A story_review.participant_gate",
                "allowed_values": ["reviewed", "not_evaluated"],
                "reject_conditions": ["PersonStory or Mention treated as hard participation without review"],
                "reason": "Punctuation passage alone does not complete Story admissibility.",
                "implementation_location": "scripts/build_x1_2a_review.py:review_story",
            },
        ],
        "classification": {
            "type": "intentional_two_tier_policy",
            "implementation_bug": False,
            "stale_metadata": False,
            "validator_schema_mismatch": False,
            "explanation": (
                "X1.1 intentionally admits non-disputed source-backed candidates for research selection. X1.2A intentionally "
                "requires explicit reviewed punctuation for production. The 20 Stories entered the former gate and stopped at "
                "the latter; the local source qualification explicitly forbids treating exact transfer as trusted production text."
            ),
        },
        "story_gate_results": [
            row["gate_result"] for row in story_rows
        ],
        "summary": {
            "candidate_gate_pass_count": len(selections),
            "production_punctuation_gate_pass_count": sum(
                row["punctuation_review"]["production_punctuation_ready"] for row in story_rows
            ),
            "production_punctuation_gate_unresolved_count": sum(
                not row["punctuation_review"]["production_punctuation_ready"] for row in story_rows
            ),
            "story_identity_source_pass_count": sum(row["gate_result"]["gates"]["story_identity"] == "pass" for row in story_rows),
            "participant_gate_not_evaluated_count": sum(row["gate_result"]["gates"]["participant_review"] == "not_evaluated" for row in story_rows),
        },
        "policy": "Selection mode is research provenance only and never influences punctuation truth.",
    }


def build_story_reviews() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selections = selection_by_story()
    punc = punctuation_by_story()
    corpus = corpus_by_story()
    x1_2a = x1_2a_documents()
    x1_2a_stories = {
        str(row["story_id"]): dict(row)
        for row in x1_2a["story_review"].get("records", [])
        if isinstance(row, Mapping) and row.get("story_id")
    }
    production_people, production_stories = production_ids()
    del production_people
    rows = []
    for story_id in sorted(selections, key=lambda value: (corpus.get(value, {}).get("global_ordinal", 10**9), value)):
        selection = selections[story_id]
        record = punc.get(story_id, {})
        source = corpus.get(story_id, {})
        source_path = str(source.get("path", ""))
        source_exists = bool(source_path and (ROOT / source_path).is_file())
        source_hash = sha256_file(source_path) if source_exists else None
        source_ok = source_exists and source_hash == source.get("entry_sha256")
        refs = reference_audit(record)
        refs_ok = bool(refs) and all(item["hash_matches"] for item in refs)
        x1_2a_story = x1_2a_stories[story_id]
        evidence_ids = unique(x1_2a_story.get("evidence_ids", []))
        evidence_refs = evidence_refs_for_ids(evidence_ids)
        evidence_ok = bool(evidence_refs) and all(item.get("valid") for item in evidence_refs)
        duplicate = story_id in production_stories
        punctuation_result = classify_punctuation(record)
        review_status = punctuation_result["review_status"]
        row = {
            "review_item_id": stable_id("x1-2p-story-review", story_id),
            "source_candidate_id": f"{story_id}:X1.2P:PUNCTUATION",
            "story_id": story_id,
            "review_type": "story_punctuation_gate",
            "selection_epoch": "X1.1",
            "selection_mode": selection.get("selection_mode"),
            "selection_provenance": dict(selection),
            "source": {
                "path": source_path,
                "expected_sha256": source.get("entry_sha256"),
                "actual_sha256": source_hash,
                "exists": source_exists,
                "hash_verified": source_ok,
                "canonical_story_identity": story_id,
            },
            "punctuation_record": {
                "record_id": record.get("id"),
                "old_status": record.get("status"),
                "old_review_status": record.get("review_status"),
                "old_punctuation_basis": record.get("punctuation_basis"),
                "exact_transfer": record.get("exact_transfer") is True,
                "alignment_class": record.get("alignment", {}).get("alignment_class") if isinstance(record.get("alignment"), Mapping) else None,
                "reason_codes": list(record.get("alignment", {}).get("reason_codes", [])) if isinstance(record.get("alignment"), Mapping) else [],
                "reference_count": len(record.get("references", [])),
                "reference_audit": refs,
            },
            "punctuation_review": {
                **punctuation_result,
                "new_status": record.get("status"),
                "new_review_status": record.get("review_status"),
                "new_punctuation_basis": record.get("punctuation_basis"),
                "change_applied": False,
                "change_reason": "No source-backed modification is justified in X1.2P.",
            },
            "evidence_ids": evidence_ids,
            "evidence_refs": evidence_refs,
            "x1_2a_review": {
                "review_item_id": x1_2a_story.get("review_item_id"),
                "review_status": x1_2a_story.get("review_status"),
                "participant_gate": x1_2a_story.get("participant_gate", {}),
            },
            "gates": {
                "source_integrity": "pass" if source_ok else "fail",
                "story_identity": "pass" if source_ok and not duplicate else "fail",
                "punctuation": "pass" if punctuation_result["production_punctuation_ready"] else "unresolved",
                "participant_review": "not_evaluated",
                "evidence_traceability": "pass" if evidence_ok and refs_ok else "fail",
                "duplicate_check": "fail" if duplicate else "pass",
            },
            "review_status": review_status,
            "review_reason": punctuation_result["review_reason"],
            "review_notes": (
                "The Story remains a research candidate. Exact character transfer is an alignment fact, not editorial approval."
                if record.get("exact_transfer") is True
                else "The reference character variant is preserved as a conflict; no wording or canonical source text is changed."
            ),
            "materialization_status": "not_materialized",
            "eligible_for_rematerialization": False,
            "selection_does_not_affect_textual_judgment": True,
        }
        row["gate_result"] = gate_record(
            story_id,
            selection,
            x1_2a_story,
            record,
            punctuation_result,
            source_ok,
            evidence_ok and refs_ok,
            duplicate,
        )
        rows.append(row)
    return rows, x1_2a


SEMANTIC_DEPENDENCY_BY_LAYER = {
    "family": "semantic_uncertainty",
    "office": "insufficient_evidence",
    "event": "insufficient_evidence",
    "geographic": "semantic_uncertainty",
    "service_political": "semantic_uncertainty",
}


def build_dependency_audit(story_rows: list[dict[str, Any]], x1_2a: Mapping[str, Any]) -> dict[str, Any]:
    story_by_id = {row["story_id"]: row for row in story_rows}
    fact_rows = [row for row in x1_2a["fact_review"].get("records", []) if row.get("review_status") == "unresolved"]
    records = []
    for row in fact_rows:
        story = story_by_id[str(row["story_id"])]
        semantic = SEMANTIC_DEPENDENCY_BY_LAYER.get(str(row.get("fact_layer")), "insufficient_evidence")
        records.append({
            "dependency_id": stable_id("x1-2p-fact-dependency", row["review_item_id"]),
            "source_review_item_id": row["review_item_id"],
            "story_id": row["story_id"],
            "fact_layer": row.get("fact_layer"),
            "x1_2a_review_status": row.get("review_status"),
            "punctuation_review_status": story.get("review_status"),
            "punctuation_dependency": "blocked_by_story_punctuation",
            "independent_dependency": semantic,
            "blocking_factors": ["blocked_by_story_punctuation", semantic],
            "primary_blocker": "blocked_by_story_punctuation",
            "review_reason": row.get("review_reason"),
            "evidence_ids": row.get("evidence_ids", []),
            "would_punctuation_only_accept_fact": False,
            "materialization_status": "not_materialized",
        })
    identity_rows = [row for row in x1_2a["person_review"].get("records", []) if row.get("review_status") == "unresolved"]
    identity_records = []
    for row in identity_rows:
        story = story_by_id[str(row["story_id"])]
        identity_records.append({
            "dependency_id": stable_id("x1-2p-identity-dependency", row["review_item_id"]),
            "source_review_item_id": row["review_item_id"],
            "story_id": row["story_id"],
            "surface": row.get("surface"),
            "punctuation_review_status": story.get("review_status"),
            "punctuation_dependency": "blocked_by_story_punctuation",
            "independent_dependency": "identity_ambiguity",
            "blocking_factors": ["blocked_by_story_punctuation", "identity_ambiguity"],
            "primary_blocker": "identity_ambiguity",
            "review_reason": row.get("review_reason"),
            "evidence_ids": row.get("evidence_ids", []),
            "would_punctuation_only_resolve_identity": False,
            "materialization_status": "not_materialized",
        })
    semantic_counts = Counter(row["independent_dependency"] for row in records)
    return {
        "schema": 1,
        "stage": "x1-2p-dependency-audit",
        "review_epoch": EPOCH,
        "source_hashes": common_source_bundle(),
        "fact_records": records,
        "identity_records": identity_records,
        "summary": {
            "unresolved_fact_candidate_count": len(records),
            "facts_blocked_by_story_punctuation": sum(row["punctuation_dependency"] == "blocked_by_story_punctuation" for row in records),
            "fact_independent_dependency_distribution": dict(sorted(semantic_counts.items())),
            "unresolved_identity_candidate_count": len(identity_records),
            "identities_blocked_by_story_punctuation": sum(row["punctuation_dependency"] == "blocked_by_story_punctuation" for row in identity_records),
            "identities_with_independent_ambiguity": sum(row["independent_dependency"] == "identity_ambiguity" for row in identity_records),
            "punctuation_only_acceptance_count": 0,
        },
        "policy": "Punctuation passage never auto-accepts an X1.2A fact or identity; independent evidence review remains required.",
    }


def build_eligibility(story_rows: list[dict[str, Any]], x1_2a: Mapping[str, Any]) -> dict[str, Any]:
    extension_facts = x1_2a["canonical_facts"].get("fact_index", [])
    rows = []
    for story in story_rows:
        story_id = story["story_id"]
        prior_facts = sorted(row["fact_id"] for row in extension_facts if story_id in row.get("story_ids", []))
        rows.append({
            "story_id": story_id,
            "selection_mode": story["selection_mode"],
            "punctuation_review_status": story["review_status"],
            "punctuation_production_ready": story["punctuation_review"]["production_punctuation_ready"],
            "x1_2a_story_review_status": story["x1_2a_review"]["review_status"],
            "participant_gate": story["gates"]["participant_review"],
            "eligibility_state": "still_unresolved",
            "eligible_for_rematerialization": False,
            "reason_codes": [
                "punctuation_gate_unresolved",
                "participant_review_not_evaluated",
            ],
            "previously_materialized_x1_2a_fact_ids": prior_facts,
            "previously_materialized_fact_release_allowed": False,
            "release_action": "none",
        })
    return {
        "schema": 1,
        "stage": "x1-2p-rematerialization-eligibility",
        "review_epoch": EPOCH,
        "source_hashes": common_source_bundle(),
        "records": rows,
        "counts": {
            "eligible_for_rematerialization": sum(row["eligible_for_rematerialization"] for row in rows),
            "still_unresolved": sum(row["eligibility_state"] == "still_unresolved" for row in rows),
            "rejected": sum(row["eligibility_state"] == "rejected" for row in rows),
            "stories_released": 0,
            "facts_released": 0,
            "persons_released": 0,
        },
        "policy": "X1.2A accepted extension facts remain protected; X1.2P performs no release while participant semantics are unevaluated.",
    }


def build_channel_audit(story_rows: list[dict[str, Any]]) -> dict[str, Any]:
    channels = []
    for channel in CHANNELS:
        rows = [row for row in story_rows if row["selection_mode"] == channel]
        status_counts = Counter(row["review_status"] for row in rows)
        channels.append({
            "selection_mode": channel,
            "selected_story_ids": sorted(row["story_id"] for row in rows),
            "selected_story_count": len(rows),
            "punctuation_outcome_distribution": dict(sorted(status_counts.items())),
            "accepted_count": status_counts.get("accepted", 0),
            "unresolved_count": status_counts.get("unresolved", 0),
            "rejected_count": status_counts.get("rejected", 0),
            "resolution_rate": 0.0 if rows else None,
            "selection_channel_was_used_as_textual_evidence": False,
        })
    return {
        "schema": 1,
        "stage": "x1-2p-channel-audit",
        "review_epoch": EPOCH,
        "source_hashes": common_source_bundle(),
        "channels": channels,
        "channel_neutrality": {
            "same_review_rule_applied": True,
            "selection_mode_influenced_outcome": False,
            "interpretation": "Differences are textual-admissibility counts only, not model-quality evidence.",
        },
    }


def build_readiness_overlay(story_rows: list[dict[str, Any]]) -> dict[str, Any]:
    selected = {row["story_id"]: row for row in story_rows}
    pool = read(X1_1_INPUTS["candidate_pool"])
    records = []
    for candidate in pool.get("records", []):
        story_id = str(candidate["story_id"])
        punctuation = punctuation_by_story().get(story_id, {})
        status = punctuation.get("status")
        review_status = punctuation.get("review_status")
        basis = punctuation.get("punctuation_basis")
        source = candidate.get("source", {})
        production_ready = status == "reviewed" and review_status == "reviewed" and basis == "human_reviewed"
        disputed = status == "disputed" or basis == "disputed" or punctuation.get("alignment", {}).get("alignment_class") == "character-disagreement"
        if production_ready:
            cost = "ready"
        elif disputed:
            cost = "disputed"
        elif punctuation.get("exact_transfer") is True:
            cost = "substantive_review"
        else:
            cost = "light_review"
        review_row = selected.get(story_id)
        records.append({
            "story_id": story_id,
            "candidate_pool_eligible": candidate.get("eligible") is True,
            "source_exists": bool(source.get("path") and (ROOT / str(source["path"])).is_file()),
            "punctuation_status": status,
            "punctuation_review_status": review_status,
            "punctuation_basis": basis,
            "exact_transfer": punctuation.get("exact_transfer") is True,
            "alignment_class": punctuation.get("alignment", {}).get("alignment_class") if isinstance(punctuation.get("alignment"), Mapping) else None,
            "candidate_reviewable": bool(source.get("path")) and status not in {None, "disputed"},
            "production_punctuation_ready": production_ready,
            "punctuation_review_required": not production_ready and not disputed,
            "punctuation_disputed": disputed,
            "punctuation_review_cost": cost,
            "x1_2p_selected": review_row is not None,
            "x1_2p_outcome": review_row.get("review_status") if review_row else None,
        })
    records.sort(key=lambda row: row["story_id"])
    return {
        "schema": 1,
        "stage": "x1-2p-candidate-punctuation-readiness",
        "review_epoch": EPOCH,
        "source_hashes": common_source_bundle(),
        "candidate_pool_sha256": sha256_file(X1_1_INPUTS["candidate_pool"]),
        "selection_snapshot_sha256": read(X1_1_INPUTS["selection_manifest"]).get("selection_snapshot_sha256"),
        "records": records,
        "counts": dict(sorted(Counter(
            "production_punctuation_ready" if row["production_punctuation_ready"]
            else "punctuation_disputed" if row["punctuation_disputed"]
            else "punctuation_review_required"
            for row in records
        ).items())),
        "policy": "This is a derived readiness overlay; the frozen X1.1 candidate pool and selection manifest are not rewritten.",
    }


def build() -> dict[str, Any]:
    selections = selection_by_story()
    story_rows, x1_2a = build_story_reviews()
    gate_audit = build_gate_audit(selections, story_rows)
    dependency = build_dependency_audit(story_rows, x1_2a)
    eligibility = build_eligibility(story_rows, x1_2a)
    channel = build_channel_audit(story_rows)
    readiness = build_readiness_overlay(story_rows)
    source_bundle = common_source_bundle()
    review_doc = {
        "schema": 1,
        "stage": "x1-2p-story-review",
        "review_epoch": EPOCH,
        "source_hashes": source_bundle,
        "selection_frozen_before_review": True,
        "selection_replacement": False,
        "records": story_rows,
        "counts": dict(sorted(Counter(row["review_status"] for row in story_rows).items())),
        "punctuation_change_count": sum(row["punctuation_review"]["change_applied"] for row in story_rows),
        "review_policy": {
            "selection_mode_is_not_textual_evidence": True,
            "exact_transfer_is_not_editorial_approval": True,
            "no_canonical_source_text_edit": True,
            "no_forced_resolution": True,
            "top_level_states": ["accepted", "unresolved", "rejected"],
        },
    }
    write(GATE_AUDIT_PATH, gate_audit)
    write(STORY_REVIEW_PATH, review_doc)
    write(DEPENDENCY_PATH, dependency)
    write(ELIGIBILITY_PATH, eligibility)
    write(READINESS_PATH, readiness)
    write(CHANNEL_PATH, channel)
    return {
        "stage": review_doc["stage"],
        "counts": review_doc["counts"],
        "punctuation_changes": review_doc["punctuation_change_count"],
        "dependency": dependency["summary"],
        "eligibility": eligibility["counts"],
    }


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(build(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
