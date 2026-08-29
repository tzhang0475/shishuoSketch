"""L7 adapter to the frozen PSL1 collective-consistency implementation."""

from __future__ import annotations

from typing import Any, Mapping

from .common import text


def infer_collectively(constrained: Mapping[str, Any]) -> dict[str, Any]:
    import hdb2_psl1_common as psl

    cases: list[dict[str, Any]] = []
    predicates: list[dict[str, Any]] = []
    for record in constrained.get("records", []) or []:
        mention_id = text(record.get("mention_id"))
        candidates: list[dict[str, Any]] = []
        deterministic: list[dict[str, Any]] = []
        for candidate in record.get("candidates", []) or []:
            key = text(candidate.get("candidate_key"))
            node_id = text(candidate.get("person_id")) or text(candidate.get("candidate_person_id"))
            evidence_ids = [text(item.get("evidence_id")) for item in candidate.get("evidence", []) or [] if text(item.get("evidence_id"))]
            candidates.append({
                "candidate_key": key,
                "candidate_node_id": node_id,
                "name": candidate.get("display_name"),
                "entity_type": candidate.get("entity_type"),
            })
            if text(candidate.get("matched_surface")) == text(record.get("surface")) and evidence_ids:
                deterministic.append({
                    "predicate": "AliasMatch", "candidate_key": key,
                    "value": 1.0, "evidence_ids": evidence_ids,
                    "reason": candidate.get("retrieval_basis"),
                })
        judgment = record.get("judgment") if isinstance(record.get("judgment"), Mapping) else {}
        for assessment in judgment.get("candidate_assessments", []) or []:
            key = text(assessment.get("candidate_key"))
            verdict = text(assessment.get("verdict"))
            if verdict == "support":
                predicates.append({
                    "predicate": "IdentityContextSupport", "mention_id": mention_id,
                    "candidate_key": key, "value": 1.0,
                    "evidence_ids": assessment.get("supporting_evidence_ids", []),
                    "reason": "SFH1 grounded identity assessment",
                })
            elif verdict == "contradict":
                predicates.append({
                    "predicate": "IdentityContradiction", "mention_id": mention_id,
                    "candidate_key": key, "value": 1.0,
                    "evidence_ids": assessment.get("contradicting_evidence_ids", []),
                    "reason": "SFH1 grounded identity contradiction",
                })
        cases.append({
            "mention_id": mention_id,
            "surface": record.get("surface"),
            "candidates": candidates,
            "deterministic_predicates": deterministic,
            "psl1_hard_vetoes": record.get("hard_vetoes", {}),
        })
    for pair in constrained.get("coreference_pairs", []) or []:
        predicates.append({
            "predicate": "Coreference",
            "mention_id": pair.get("left_mention_id"),
            "other_mention_id": pair.get("right_mention_id"),
            "candidate_key": "",
            "value": 1.0,
            "evidence_ids": [],
            "reason": "validated L3 local coreference",
        })
    graph = {
        "cases": cases,
        "distinct_pairs": [
            {**dict(pair), "evidence_ids": [], "reason": "validated L3 explicit distinctness"}
            for pair in constrained.get("distinct_pairs", []) or []
        ],
        "same_story_pairs": [],
        "known_relation_paths": [],
    }
    try:
        result = psl.infer_graph(graph, predicates)
        decisions = result.get("decisions", []) if isinstance(result, Mapping) else []
        conflicts = result.get("coreference_conflicts", []) if isinstance(result, Mapping) else []
    except Exception as exc:
        decisions = []
        conflicts = [{"reason": "psl_adapter_failure", "exception_class": type(exc).__name__}]
    return {
        "story_id": constrained.get("story_id"),
        "graph": graph,
        "predicates": predicates,
        "decisions": decisions,
        "coreference_conflicts": conflicts,
        "weights_source": "scripts/hdb2_psl1_common.py:frozen",
        "weights_tuned": False,
        "candidate_only": True,
        "canonical_write_back": False,
    }
