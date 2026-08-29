"""L9 candidate-only storage gate and final failure attribution."""

from __future__ import annotations

from typing import Any, Mapping

from .common import stable_hash, text
from .schemas import FINAL_STATES

STRUCTURAL = {"compositional_kinship", "patron_plus_office", "descriptive_person_reference"}


def finalize_story(
    ledger: Mapping[str, Any],
    semantics: Mapping[str, Any],
    constrained: Mapping[str, Any],
    collective: Mapping[str, Any],
    reviews: Mapping[str, Any],
) -> dict[str, Any]:
    mentions = {text(row.get("mention_id")): dict(row) for row in ledger.get("valid_mentions", []) or []}
    semantic_index = {text(row.get("mention_id")): dict(row) for row in semantics.get("records", []) or []}
    constrained_index = {text(row.get("mention_id")): dict(row) for row in constrained.get("records", []) or []}
    psl_index = {text(row.get("mention_id")): dict(row) for row in collective.get("decisions", []) or []}
    review_index = {text(row.get("mention_id")): dict(row) for row in reviews.get("reviews", []) or []}
    required_reviews = set(text(value) for value in reviews.get("required_mentions", []) or [])
    records: list[dict[str, Any]] = []
    for mention_id, mention in sorted(mentions.items()):
        semantic = semantic_index.get(mention_id, {})
        constrained_row = constrained_index.get(mention_id, {})
        candidates = constrained_row.get("candidates", []) or []
        judgment = constrained_row.get("judgment") if isinstance(constrained_row.get("judgment"), Mapping) else {}
        preferred = judgment.get("preferred_candidate_key")
        candidate = next((row for row in candidates if row.get("candidate_key") == preferred), None)
        vetoes = constrained_row.get("hard_vetoes", {}) or {}
        review = review_index.get(mention_id)
        state = "genuinely_unresolved"
        failure_stage = None
        resolved_person_id = None
        candidate_person_id = None
        if text(mention.get("entity_kind")) == "non_person":
            state = "non_person"
        elif text(mention.get("entity_kind")) == "collective_person_reference":
            state = "structural_reference"
        elif text(semantic.get("semantic_type")) in STRUCTURAL:
            state = "structural_reference"
        elif text(semantic.get("semantic_type")) == "uncertain" or text(semantic.get("confidence")) == "low":
            state = "review_required"
            failure_stage = "reference_semantics_uncertain"
        elif not candidates:
            state = "genuinely_unresolved"
            failure_stage = "candidate_recall_failure"
        elif not judgment:
            state = "review_required"
            failure_stage = "provider_failure"
        elif preferred is None:
            state = "review_required" if judgment.get("resolution") == "candidate_ambiguous" else "genuinely_unresolved"
            failure_stage = "identity_evidence_insufficient"
        elif preferred in vetoes:
            state = "review_required"
            failure_stage = "hard_constraint_veto"
        elif not candidate:
            state = "review_required"
            failure_stage = "hard_constraint_veto"
        elif candidate.get("entity_type") == "local_candidate_person" and judgment.get("resolution") == "candidate_supported":
            state = "local_candidate_resolved"
            candidate_person_id = candidate.get("candidate_person_id")
        elif candidate.get("entity_type") == "prior_candidate_person" and judgment.get("resolution") == "candidate_supported":
            state = "local_candidate_resolved"
            candidate_person_id = candidate.get("candidate_person_id")
        elif candidate.get("entity_type") == "existing_person" and judgment.get("resolution") == "candidate_supported":
            if mention_id not in required_reviews:
                state = "review_required"
                failure_stage = "provider_failure"
            elif not review:
                state = "review_required"
                failure_stage = "provider_failure"
            elif review.get("verdict") == "accept":
                state = "stable_entity_resolved"
                resolved_person_id = candidate.get("person_id")
            elif review.get("verdict") == "reject":
                state = "review_required"
                failure_stage = "reviewer_rejection"
            else:
                state = "review_required"
                failure_stage = "identity_evidence_insufficient"
        else:
            state = "review_required"
            failure_stage = "identity_evidence_insufficient"
        assert state in FINAL_STATES
        records.append({
            "decision_id": f"sfh1-decision-{stable_hash({'mention_id': mention_id, 'state': state, 'person': resolved_person_id, 'candidate': candidate_person_id})[:24]}",
            "mention_id": mention_id,
            "story_id": mention.get("story_id"),
            "surface": mention.get("surface"),
            "entity_kind": mention.get("entity_kind"),
            "reference_form": mention.get("reference_form"),
            "semantic_type": semantic.get("semantic_type", "uncertain"),
            "final_state": state,
            "person_id": resolved_person_id,
            "candidate_person_id": candidate_person_id,
            "preferred_candidate_key": preferred,
            "candidate_display_name": candidate.get("display_name") if candidate else None,
            "failure_stage": failure_stage,
            "evidence_ids": sorted(set([
                text(mention.get("source_evidence_id")),
                *[text(value) for value in (review or {}).get("supporting_evidence_ids", []) or []],
            ]) - {""}),
            "psl": psl_index.get(mention_id),
            "review": review,
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return {
        "story_id": ledger.get("story_id"),
        "records": records,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def project_relations(semantics_by_story: list[Mapping[str, Any]], final_records: list[Mapping[str, Any]]) -> dict[str, Any]:
    decisions = {text(row.get("mention_id")): row for row in final_records}
    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for story in semantics_by_story:
        for relation in story.get("relations", []) or []:
            subject = decisions.get(text(relation.get("subject_mention_id")))
            object_row = decisions.get(text(relation.get("object_mention_id")))
            if not subject or not object_row:
                rejected.append({"relation": dict(relation), "reason": "endpoint_missing"})
                continue
            subject_endpoint = subject.get("person_id") or subject.get("candidate_person_id")
            object_endpoint = object_row.get("person_id") or object_row.get("candidate_person_id")
            if subject_endpoint and object_endpoint and subject_endpoint == object_endpoint and relation.get("relation_type") not in {"other"}:
                rejected.append({"relation": dict(relation), "reason": "nonidentity_self_relation"})
                continue
            records.append({
                "relation_id": f"sfh1-relation-{stable_hash(relation)[:24]}",
                **dict(relation),
                "story_id": story.get("story_id"),
                "subject_endpoint": subject_endpoint,
                "object_endpoint": object_endpoint,
                "endpoint_state": "complete" if subject_endpoint and object_endpoint else "incomplete",
                "candidate_only": True,
                "canonical_write_back": False,
            })
    return {"records": records, "rejected": rejected, "candidate_only": True, "canonical_write_back": False}
