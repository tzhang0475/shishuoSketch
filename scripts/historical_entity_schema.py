#!/usr/bin/env python3
"""Historical Entity Schema V1.

This module is deliberately a data-contract layer.  It separates what a
source passage contains from interpretations, candidate generation, hard
constraints, semantic assessment, and the final Python-owned graph action.
It has no network or model client and never writes canonical data.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Mapping


SCHEMA_VERSION = "historical-entity-schema-v1"

ENTITY_KINDS = {
    "named_person", "person_title", "person_office_title", "courtesy_name",
    "abbreviated_name", "kinship_reference", "pronoun_reference",
    "structural_kinship_expression", "generic_role", "collective_persons",
    "not_person", "unknown",
}
REFERENCE_FORMS = {
    "full_name", "courtesy", "title_only", "office_title_only", "abbreviated",
    "kinship_plus_name", "implicit", "anonymous", "unknown",
}
MENTION_SCOPES = {
    "narrative", "metatextual", "quotation", "commentary", "genealogical", "unknown",
}
DISCOURSE_ROLES = {
    "event_participant", "speaker", "referenced_person", "kinship_node",
    "cited_author", "text_author", "commentator", "office_holder", "unknown",
}

CONSTRAINT_STATUSES = {
    "strong_support", "support", "compatible", "weak", "unknown", "conflict", "not_applicable",
}
RECOMMENDATION_DECISIONS = {
    "choose_candidate", "new_person_candidate", "ambiguous", "unresolved",
    "not_a_single_person", "not_a_person",
}
IDENTITY_STATUSES = {
    "resolved_existing", "resolved_new_candidate", "ambiguous", "unresolved",
    "rejected", "not_person", "not_single_person",
}
GRAPH_ACTIONS = {
    "link_existing", "create_provisional_candidate", "no_person_node",
    "hold_for_review", "no_action",
}
GRAPH_NODE_TYPES = {"existing_person", "provisional_person", "none"}
FRONTIER_STATUSES = {
    "eligible", "candidate", "blocked", "needs_identity_review",
    "needs_semantic_parse", "researched",
}
RESEARCH_GAP_STATUSES = {"closed", "open"}
RESEARCH_ACTIONS = {
    "search_kinship_context", "search_title_identity", "search_temporal_evidence",
    "search_biography_context", "human_review", "none",
}
SEMANTIC_LEVELS = {"hard_relation", "documented_interaction", "interpreted_relation"}


def _plain(value: Any) -> Any:
    """Convert dataclasses and tuples to stable JSON-compatible values."""

    if is_dataclass(value):
        return _plain(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(v) for v in value]
    return value


def to_dict(value: Any) -> dict[str, Any]:
    result = _plain(value)
    if not isinstance(result, dict):
        raise TypeError("schema object must serialize to a JSON object")
    return result


def _check(value: str, allowed: set[str], field_name: str) -> None:
    if value not in allowed:
        raise ValueError(f"invalid {field_name}: {value!r}")


@dataclass
class MentionObservation:
    """Only the directly observed source mention; no inferred semantics."""

    mention_id: str
    surface: str
    exact_span: str
    source_ref: str
    source_work: str
    locator: dict[str, Any] = field(default_factory=dict)
    start: int | None = None
    end: int | None = None

    def __post_init__(self) -> None:
        for name in ("mention_id", "surface", "exact_span", "source_ref", "source_work"):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"empty MentionObservation.{name}")


@dataclass
class EntityInterpretation:
    mention_id: str
    entity_kind: str
    reference_form: str = "unknown"
    mention_scope: str = "unknown"
    discourse_role: str = "unknown"
    structural_kinship: dict[str, Any] | None = None
    summary: str = ""

    def __post_init__(self) -> None:
        _check(self.entity_kind, ENTITY_KINDS, "entity_kind")
        _check(self.reference_form, REFERENCE_FORMS, "reference_form")
        _check(self.mention_scope, MENTION_SCOPES, "mention_scope")
        _check(self.discourse_role, DISCOURSE_ROLES, "discourse_role")


@dataclass
class CandidateEntity:
    candidate_key: str
    person_id: str | None
    canonical_name: str
    known_forms: list[str] = field(default_factory=list)
    candidate_source: str = "python"
    chronology_summary: str = ""
    graph_summary: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_key.startswith("c") or not self.candidate_key[1:].isdigit():
            raise ValueError("candidate_key must be a local c0/c1/... key")
        if not self.canonical_name:
            raise ValueError("CandidateEntity requires canonical_name")


@dataclass(frozen=True)
class ConstraintCheck:
    constraint_type: str
    candidate_key: str
    status: str
    computed_by: str
    evidence_refs: tuple[str, ...] = ()
    independent: bool = True
    reason_code: str = ""

    def __post_init__(self) -> None:
        _check(self.status, CONSTRAINT_STATUSES, "constraint status")


@dataclass
class SemanticAssessment:
    mention_id: str
    assessment_status: str = "unassessed"
    semantic_fit: str = "unknown"
    observed_role: str = "unknown"
    evidence_spans: list[str] = field(default_factory=list)
    summary: str = ""
    hard_constraints_immutable: bool = True


@dataclass
class IdentityRecommendation:
    decision: str
    chosen_candidate_key: str | None = None
    confidence: str = "low"
    reason_codes: list[str] = field(default_factory=list)
    evidence_spans: list[str] = field(default_factory=list)
    new_entity_candidate: dict[str, Any] | None = None
    unresolved_reason: str = ""
    summary: str = ""

    def __post_init__(self) -> None:
        _check(self.decision, RECOMMENDATION_DECISIONS, "recommendation decision")


@dataclass
class IdentityDecision:
    identity_status: str
    chosen_candidate_key: str | None = None
    person_id: str | None = None
    provisional_person_id: str | None = None
    confidence: str = "low"
    reason_codes: list[str] = field(default_factory=list)
    supporting_evidence_refs: list[str] = field(default_factory=list)
    decision_summary: str = ""

    def __post_init__(self) -> None:
        _check(self.identity_status, IDENTITY_STATUSES, "identity status")
        if self.identity_status == "resolved_existing" and not self.person_id:
            raise ValueError("resolved_existing requires person_id")
        if self.identity_status == "resolved_new_candidate" and not self.provisional_person_id:
            raise ValueError("resolved_new_candidate requires provisional_person_id")


@dataclass
class GraphAction:
    action: str
    node_type: str
    person_id: str | None = None
    provisional_person_id: str | None = None
    frontier_status: str = "blocked"
    reason_codes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _check(self.action, GRAPH_ACTIONS, "graph action")
        _check(self.node_type, GRAPH_NODE_TYPES, "graph node type")
        _check(self.frontier_status, FRONTIER_STATUSES, "frontier status")
        if self.node_type == "existing_person" and not self.person_id:
            raise ValueError("existing_person graph action requires person_id")
        if self.node_type == "provisional_person" and not self.provisional_person_id:
            raise ValueError("provisional_person graph action requires provisional_person_id")


@dataclass
class ResearchGap:
    status: str
    missing_constraints: list[str] = field(default_factory=list)
    blocking_question: str = ""
    next_best_action: str = "none"
    candidate_keys: list[str] = field(default_factory=list)
    stop_condition: str = ""

    def __post_init__(self) -> None:
        _check(self.status, RESEARCH_GAP_STATUSES, "research gap status")
        _check(self.next_best_action, RESEARCH_ACTIONS, "research gap action")


@dataclass
class SearchPlan:
    target_constraint: str
    goal: str
    candidate_keys: list[str] = field(default_factory=list)
    preferred_sources: list[str] = field(default_factory=list)
    search_entities: list[str] = field(default_factory=list)
    search_patterns: list[str] = field(default_factory=list)
    temporal_scope: dict[str, Any] = field(default_factory=dict)
    graph_neighborhood_scope: str = "none"
    stop_condition: str = ""


@dataclass
class RelationAssertion:
    relation_id: str
    person_a: str | None
    person_b: str | None
    relation_type: str
    semantic_level: str
    relation_semantics_description: str
    evidence_refs: list[str] = field(default_factory=list)
    evidence_quotes: list[dict[str, str]] = field(default_factory=list)
    status: str = "candidate"
    canonical_write_back: bool = False

    def __post_init__(self) -> None:
        _check(self.semantic_level, SEMANTIC_LEVELS, "semantic level")


@dataclass
class HistoricalEntityResolutionCase:
    case_id: str
    observation: MentionObservation
    interpretation: EntityInterpretation
    candidates: list[CandidateEntity] = field(default_factory=list)
    constraint_checks: list[ConstraintCheck] = field(default_factory=list)
    semantic_assessment: SemanticAssessment | None = None
    recommendation: IdentityRecommendation | None = None
    decision: IdentityDecision | None = None
    graph_action: GraphAction | None = None
    research_gap: ResearchGap | None = None
    search_plans: list[SearchPlan] = field(default_factory=list)
    source_stage: str = "offline_replay"


# This is a contract for a future constrained semantic-assist call.  It is
# intentionally data-only: HNG2-S never invokes a model.
CHINESE_SEMANTIC_ASSIST_QUESTIONS = (
    "目标表达在这段文字中是什么性质？它是明确姓名、字、简称、帝王/爵号、官职称谓、亲属指代、代词指代、结构性亲属表达、泛称，还是并非人物表达？",
    "这个表达在当前文字中指的是一个可单独识别的人物吗？它在本段承担什么功能？是事件参与者、说话者、被谈论者、亲属链中的人物、引书作者、史家/注家，还是其他角色？",
    "对系统提供的每一个候选人物，原文有哪些直接支持或反对该候选的语言证据？不得修改系统给出的年代、关系、官职等硬约束。",
    "综合原文语义与系统提供的硬约束，现有证据是否足以唯一认定某个候选人物？",
    "如果不能唯一认定，应归入哪种情况？新的独立人物候选 / 多个候选仍有歧义 / 证据不足 / 不是人物 / 不是单一人物表达。",
    "哪些连续原文直接支持上述判断？不补写，不改写。",
)


def validate_semantic_level(value: str) -> bool:
    return value in SEMANTIC_LEVELS


def validate_identity_status(value: str) -> bool:
    # Explicitly excludes the old HNG provisional status.
    return value in IDENTITY_STATUSES


__all__ = [
    "SCHEMA_VERSION", "ENTITY_KINDS", "REFERENCE_FORMS", "MENTION_SCOPES", "DISCOURSE_ROLES",
    "CONSTRAINT_STATUSES", "RECOMMENDATION_DECISIONS", "IDENTITY_STATUSES", "GRAPH_ACTIONS",
    "GRAPH_NODE_TYPES", "FRONTIER_STATUSES", "RESEARCH_GAP_STATUSES", "RESEARCH_ACTIONS",
    "SEMANTIC_LEVELS", "MentionObservation", "EntityInterpretation", "CandidateEntity",
    "ConstraintCheck", "SemanticAssessment", "IdentityRecommendation", "IdentityDecision",
    "GraphAction", "ResearchGap", "SearchPlan", "RelationAssertion",
    "HistoricalEntityResolutionCase", "CHINESE_SEMANTIC_ASSIST_QUESTIONS", "to_dict",
    "validate_semantic_level", "validate_identity_status",
]
