"""Formal, language-neutral review routing for SFH2.2-A0R."""

from __future__ import annotations

from typing import Any, Mapping

from sfh2_a0.consistency import EXCLUDED_CORE_ROLES
from sfh2_a0.consistency import check_record as _check_record

from .common import text

CONSISTENCY_CONTRACT = "formal_fields_graph_and_storage_routing_v2"
HARD_FLAG_TYPES = frozenset({
    "evidence_grounding_failure",
    "identity_distinctness_conflict",
    "entity_storage_type_conflict",
    "source_role_projection_conflict",
    "graph_relation_conflict",
})
REVIEW_FLAG_TYPES = frozenset({
    "internal_field_conflict",
    "low_confidence",
    "multi_candidate_ambiguity",
    "temporal_conflict",
})


def _challenged_fields(flag: Mapping[str, Any]) -> list[str]:
    flag_type = text(flag.get("flag_type"))
    involved = [text(value) for value in flag.get("involved", []) or [] if text(value)]
    explicit = [text(value) for value in flag.get("challenged_fields", []) or [] if text(value)]
    if explicit:
        return sorted(set(explicit))
    if flag_type == "internal_field_conflict":
        return sorted(set(involved))
    if flag_type == "low_confidence":
        return ["confidence", "referent.confidence"]
    if flag_type == "identity_distinctness_conflict":
        return ["relations"]
    if flag_type == "source_role_projection_conflict":
        return ["occurrence_role"]
    if flag_type == "entity_storage_type_conflict":
        return ["semantic_kind", "abstain"]
    if flag_type == "multi_candidate_ambiguity":
        return ["relations", "referent.canonical_hint"]
    return []


def analyze_record(
    record: Mapping[str, Any] | None,
    *,
    evidence_ids: set[str] | None = None,
    realization: Mapping[str, Any] | None = None,
    graph_facts: list[Mapping[str, Any]] | None = None,
    stage: str = "pass1",
) -> dict[str, Any]:
    """Return formal flags with severity and challenged field metadata.

    The delegated checks inspect structured values and storage state only.  No
    form, title, name, or language-specific answer is supplied here.
    """

    raw = _check_record(
        record,
        evidence_ids=evidence_ids,
        realization=realization,
        graph_facts=graph_facts,
        stage=stage,
    )
    flags: list[dict[str, Any]] = []
    for source in raw.get("flags", []) or []:
        flag = dict(source) if isinstance(source, Mapping) else {}
        flag_type = text(flag.get("flag_type"))
        if flag_type in HARD_FLAG_TYPES:
            severity = "hard"
        elif flag_type in REVIEW_FLAG_TYPES:
            severity = "review"
        else:
            severity = text(flag.get("severity")) if text(flag.get("severity")) in {"hard", "review", "diagnostic"} else "diagnostic"
        flag["severity"] = severity
        flag["challenged_fields"] = _challenged_fields(flag)
        flags.append(flag)
    score = sum(5 if text(flag.get("severity")) == "hard" else 2 if text(flag.get("severity")) == "review" else 0 for flag in flags)
    return {
        "schema": "sfh2-a0r-consistency-v2",
        "stage": stage,
        "flags": flags,
        "review_trigger_score": score,
        "has_hard_flags": any(text(flag.get("severity")) == "hard" for flag in flags),
        "has_review_flags": any(text(flag.get("severity")) == "review" for flag in flags),
        "has_diagnostic_flags": any(text(flag.get("severity")) == "diagnostic" for flag in flags),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def review_required(consistency: Mapping[str, Any] | None) -> bool:
    if not isinstance(consistency, Mapping):
        return True
    return bool(consistency.get("has_hard_flags") or consistency.get("has_review_flags"))


def hard_conflict(consistency: Mapping[str, Any] | None) -> bool:
    return bool(isinstance(consistency, Mapping) and consistency.get("has_hard_flags"))


def diagnostic_only(consistency: Mapping[str, Any] | None) -> bool:
    if not isinstance(consistency, Mapping):
        return False
    flags = consistency.get("flags", []) or []
    return bool(flags) and all(text(flag.get("severity")) == "diagnostic" for flag in flags if isinstance(flag, Mapping))
