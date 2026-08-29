"""L6 deterministic candidate and semantic constraint validation."""

from __future__ import annotations

from typing import Any, Mapping

from .common import text


def constrain_candidates(
    ledger: Mapping[str, Any],
    semantics: Mapping[str, Any],
    candidate_sets: Mapping[str, Any],
    judgments: Mapping[str, Any],
) -> dict[str, Any]:
    mentions = {text(row.get("mention_id")): dict(row) for row in ledger.get("valid_mentions", []) or []}
    semantic_index = {text(row.get("mention_id")): dict(row) for row in semantics.get("records", []) or []}
    candidates = {text(row.get("mention_id")): dict(row) for row in candidate_sets.get("records", []) or []}
    judgment_index = {text(row.get("mention_id")): dict(row) for row in judgments.get("judgments", []) or []}
    records: list[dict[str, Any]] = []
    distinct_pairs: set[tuple[str, str]] = set()
    coreference_pairs: set[tuple[str, str]] = set()
    for mention_id, semantic in semantic_index.items():
        for other in semantic.get("distinct_from", []) or []:
            pair = tuple(sorted((mention_id, text(other))))
            if pair[0] and pair[1] and pair[0] != pair[1]:
                distinct_pairs.add(pair)
        for other in semantic.get("coreference_with", []) or []:
            pair = tuple(sorted((mention_id, text(other))))
            if pair[0] and pair[1] and pair[0] != pair[1]:
                coreference_pairs.add(pair)
    for mention_id, mention in sorted(mentions.items()):
        semantic = semantic_index.get(mention_id, {"semantic_type": "uncertain", "confidence": "low"})
        candidate_record = candidates.get(mention_id, {"candidates": []})
        candidate_rows = [dict(row) for row in candidate_record.get("candidates", []) or []]
        candidate_keys = {text(row.get("candidate_key")) for row in candidate_rows}
        judgment = judgment_index.get(mention_id)
        vetoes: dict[str, list[str]] = {}
        errors: list[str] = []
        if text(mention.get("entity_kind")) != "person":
            candidate_rows = []
            candidate_keys = set()
        if text(semantic.get("semantic_type")) == "patron_plus_office":
            # The compound office reference is structural.  Its patron or
            # anchor is not the referent of the whole mention.
            for candidate in candidate_rows:
                vetoes[text(candidate.get("candidate_key"))] = ["structural_holder_patron_mismatch"]
        if text(semantic.get("semantic_type")) == "compositional_kinship":
            for candidate in candidate_rows:
                vetoes[text(candidate.get("candidate_key"))] = ["compositional_anchor_is_not_referent"]
        preferred = judgment.get("preferred_candidate_key") if judgment else None
        if preferred is not None and text(preferred) not in candidate_keys:
            errors.append("invalid_preferred_candidate_key")
            preferred = None
        for assessment in (judgment or {}).get("candidate_assessments", []) or []:
            key = text(assessment.get("candidate_key"))
            if key not in candidate_keys:
                errors.append("assessment_candidate_not_in_set")
            if text(assessment.get("verdict")) == "contradict" and assessment.get("contradicting_evidence_ids"):
                vetoes.setdefault(key, []).append("explicit_identity_contradiction")
        records.append({
            "mention_id": mention_id,
            "story_id": mention.get("story_id"),
            "surface": mention.get("surface"),
            "entity_kind": mention.get("entity_kind"),
            "reference_form": mention.get("reference_form"),
            "semantic_type": semantic.get("semantic_type"),
            "semantic_confidence": semantic.get("confidence"),
            "candidates": candidate_rows,
            "judgment": judgment,
            "preferred_candidate_key": preferred,
            "hard_vetoes": {key: sorted(set(value)) for key, value in sorted(vetoes.items())},
            "constraint_errors": sorted(set(errors)),
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return {
        "story_id": ledger.get("story_id"),
        "records": records,
        "distinct_pairs": [{"left_mention_id": left, "right_mention_id": right} for left, right in sorted(distinct_pairs)],
        "coreference_pairs": [{"left_mention_id": left, "right_mention_id": right} for left, right in sorted(coreference_pairs)],
        "candidate_only": True,
        "canonical_write_back": False,
    }
