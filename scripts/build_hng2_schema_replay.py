#!/usr/bin/env python3
"""Build the HNG2 Historical Entity Schema V1 offline replay.

The builder reads HNG1R2, HNG2, and HNG2-L only.  It creates a new schema
projection and a small deterministic regression suite; it never calls a
model, performs network access, or writes an older artifact.
"""

from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_hng0_2 as hng02  # noqa: E402
import historical_entity_resolver as resolver  # noqa: E402
from historical_entity_schema import (  # noqa: E402
    CHINESE_SEMANTIC_ASSIST_QUESTIONS,
    CandidateEntity,
    ConstraintCheck,
    EntityInterpretation,
    GraphAction,
    HistoricalEntityResolutionCase,
    IdentityDecision,
    IdentityRecommendation,
    MentionObservation,
    ResearchGap,
    RelationAssertion,
    SearchPlan,
    SemanticAssessment,
    SCHEMA_VERSION,
    to_dict,
)


OUTPUT_ROOT = ROOT / "data/generated/hng2-schema"
HNG1R2_ROOT = ROOT / "data/generated/hng1r2"
HNG2_ROOT = ROOT / "data/generated/hng2"
HNG2_LIVE_ROOT = ROOT / "data/generated/hng2-live"

INPUT_FILES = {
    "hng1r2_identity": HNG1R2_ROOT / "identity-resolution.json",
    "hng1r2_relations": HNG1R2_ROOT / "relations.json",
    "hng1r2_temporal": HNG1R2_ROOT / "temporal-items.json",
    "hng2_identity": HNG2_ROOT / "identity-resolution.json",
    "hng2_relations": HNG2_ROOT / "relations.json",
    "hng2_temporal": HNG2_ROOT / "temporal-items.json",
    "hng2_live_identity": HNG2_LIVE_ROOT / "identity-final.json",
    "hng2_live_relations": HNG2_LIVE_ROOT / "relations.json",
    "hng2_live_temporal": HNG2_LIVE_ROOT / "temporal-items.json",
}

OUTPUT_FILES = [
    "cases.json", "mentions.json", "entity-interpretations.json", "candidates.json",
    "constraint-checks.json", "identity-decisions.json", "graph-actions.json",
    "research-gaps.json", "relation-assertions.json", "validation-cases.json",
    "metrics.json", "manifest.json",
]

OFFICE_MARKERS = tuple(resolver.OFFICE_TITLES) + ("太尉", "太傅", "大將軍", "尚書令")
TITLE_MARKERS = ("帝", "后", "王", "公", "侯", "君", "主")
STRUCTURAL_MARKERS = ("弟", "兄", "女", "子", "從", "父", "祖", "孫")
NON_PERSON_ROLES = {resolver.matching_normalize(x) for x in resolver.GENERIC_ROLE_SURFACES}


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def hash_tree(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {str(path.relative_to(root)): sha256_file(path) for path in sorted(root.rglob("*")) if path.is_file()}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _first(values: Sequence[Any]) -> str:
    return next((_text(value) for value in values if _text(value)), "")


def _resolution(row: Mapping[str, Any]) -> dict[str, Any]:
    value = row.get("resolution")
    return dict(value) if isinstance(value, Mapping) else dict(row)


def _surface(row: Mapping[str, Any]) -> str:
    return _first([
        row.get("surface"), row.get("original_surface"), row.get("subject_surface"),
        row.get("counterpart_surface"), _resolution(row).get("surface"),
    ])


def _refs(row: Mapping[str, Any]) -> list[str]:
    refs = row.get("evidence_refs")
    if not isinstance(refs, list):
        refs = _resolution(row).get("evidence_refs")
    if not isinstance(refs, list):
        refs = []
    return sorted({str(ref) for ref in refs if _text(ref)})


def _quote_items(row: Mapping[str, Any]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in row.get("evidence_quotes", []) if isinstance(row.get("evidence_quotes"), list) else []:
        if isinstance(item, Mapping) and _text(item.get("ref")) and _text(item.get("quote")):
            result.append({"ref": _text(item.get("ref")), "quote": _text(item.get("quote"))})
    return sorted(result, key=lambda item: (item["ref"], item["quote"]))


def _context(row: Mapping[str, Any]) -> str:
    contexts = row.get("local_resolver_context")
    if isinstance(contexts, list):
        parts = []
        for item in contexts[:4]:
            if isinstance(item, Mapping):
                parts.extend([_text(item.get("exact_quote")), _text(item.get("local_context"))])
        if any(parts):
            return "\n".join(part for part in parts if part)
    return _first([row.get("context_excerpt"), row.get("local_context"), row.get("claim"), row.get("exact_quote"), _resolution(row).get("normalized_person_surface")])


def _source_evidence() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in (HNG1R2_ROOT / "relations.json", HNG1R2_ROOT / "temporal-items.json"):
        document = read_json(path, {}) or {}
        for ref, value in (document.get("evidence", {}) or {}).items():
            if isinstance(value, Mapping):
                result[str(ref)] = dict(value)
    return result


def _live_evidence_index() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path, key in ((HNG2_LIVE_ROOT / "relations.json", "relations"), (HNG2_LIVE_ROOT / "temporal-items.json", "temporal_items")):
        document = read_json(path, {}) or {}
        for row in document.get(key, []) if isinstance(document.get(key), list) else []:
            if not isinstance(row, Mapping):
                continue
            occurrence = _text(row.get("identity_occurrence_id"))
            if occurrence:
                result[occurrence] = dict(row)
    return result


def _live_source_ref(row: Mapping[str, Any], live_index: Mapping[str, Mapping[str, Any]]) -> str:
    occurrence = _text(row.get("occurrence_id"))
    linked = live_index.get(occurrence, {})
    refs = _refs(linked)
    return refs[0] if refs else f"hng2-live:{occurrence or stable_hash(row)[:20]}"


def _evidence_for(ref: str, evidence: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return dict(evidence.get(ref) or {})


def _row_exact_span(row: Mapping[str, Any], refs: Sequence[str], evidence: Mapping[str, Mapping[str, Any]]) -> str:
    quote = _first([row.get("exact_quote"), *[item.get("quote") for item in _quote_items(row)]])
    if quote:
        return quote
    surface = _surface(row)
    for ref in refs:
        original = _text(_evidence_for(ref, evidence).get("original_text"))
        if surface and surface in original:
            return surface
    contexts = row.get("local_resolver_context")
    if isinstance(contexts, list):
        for item in contexts:
            if isinstance(item, Mapping) and surface and surface in _text(item.get("local_context")):
                return surface
    return surface


def _source_work(row: Mapping[str, Any], refs: Sequence[str], evidence: Mapping[str, Mapping[str, Any]]) -> str:
    for value in [row.get("source_work"), _resolution(row).get("source_work")]:
        if _text(value):
            return _text(value)
    for ref in refs:
        source_work = _text(_evidence_for(ref, evidence).get("source_work"))
        if source_work:
            return source_work
    return "local replay source"


def _locator(row: Mapping[str, Any], refs: Sequence[str], evidence: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    for item in row.get("local_resolver_context", []) if isinstance(row.get("local_resolver_context"), list) else []:
        if isinstance(item, Mapping) and isinstance(item.get("locator"), Mapping):
            return dict(item["locator"])
    for ref in refs:
        locator = _evidence_for(ref, evidence).get("locator")
        if isinstance(locator, Mapping):
            return dict(locator)
    return {}


def _seed(catalog: Mapping[str, Mapping[str, Any]], row: Mapping[str, Any]) -> dict[str, Any]:
    seed_id = _first([row.get("seed_person_id"), row.get("person_id")])
    if seed_id in catalog:
        return dict(catalog[seed_id])
    label = _first([row.get("seed_person_name"), seed_id])
    return {"person_id": seed_id, "canonical_name": label, "surname": label[:1]}


def _resolution_method(row: Mapping[str, Any]) -> str:
    return _first([row.get("resolution_method"), _resolution(row).get("resolution_method")])


def _old_status(row: Mapping[str, Any]) -> str:
    return _first([row.get("resolution_status"), _resolution(row).get("resolution_status")])


def _title_like(surface: str) -> bool:
    value = resolver.matching_normalize(surface)
    return any(resolver.matching_normalize(marker) in value for marker in OFFICE_MARKERS) or value.endswith(tuple(resolver.matching_normalize(x) for x in TITLE_MARKERS))


def _is_metatextual(surface: str, quote: str, context: str) -> bool:
    # Generic cited-author pattern: a personal surface immediately precedes
    # a work title.  No named-author replay exception belongs here.
    text = f"{quote}{context}"
    folded = resolver.matching_normalize(surface)
    for match in re.finditer(r"(?P<author>[\u3400-\u9fff]{2,8})《[^》]{1,40}》", text):
        if resolver.matching_normalize(match.group("author")) == folded:
            return True
    return False


def _is_structural_kinship(surface: str, parsed: Mapping[str, Any]) -> bool:
    """Recognize a multi-node kinship expression without named exceptions."""

    if parsed.get("malformed_person_surface"):
        return True
    folded = resolver.matching_normalize(surface)
    if len(folded) < 4:
        return False
    marker = r"(?:弟|兄|姊|妹|子|女|父|母|祖|孫|叔|舅|婿|妻|從|外)"
    return bool(re.search(rf"^[\u3400-\u9fff]{{1,3}}{marker}[\u3400-\u9fff]{{1,4}}(?:女|子)$", folded))


def _interpretation(
    *, mention_id: str, surface: str, quote: str, context: str, source_ref: str,
    source_work: str, raw: Mapping[str, Any], catalog: Mapping[str, Mapping[str, Any]],
    index: Mapping[str, Sequence[str]],
) -> EntityInterpretation:
    folded = resolver.matching_normalize(surface)
    parsed = resolver.parse_kinship_surface(surface, seed_surname=_text(_seed(catalog, raw).get("surname")))
    if _is_structural_kinship(surface, parsed):
        return EntityInterpretation(mention_id, "structural_kinship_expression", "kinship_plus_name", "genealogical", "kinship_node", parsed, "multi-node kinship chain")
    if folded in NON_PERSON_ROLES:
        return EntityInterpretation(mention_id, "generic_role", "unknown", "narrative", "unknown", None, "generic role is not an independently identified person")
    if _is_metatextual(surface, quote, context):
        return EntityInterpretation(mention_id, "named_person", "full_name", "metatextual", "cited_author", None, "named source author cited by a work")
    method = _resolution_method(raw)
    canonical_surface = any(
        resolver.matching_normalize(catalog[pid].get("canonical_name")) == folded
        for pid in index.get(folded, []) if pid in catalog
    )
    # Title-only forms are classified before a broad local kinship scan.  A
    # long biography context can contain an unrelated 子/父 expression; that
    # must not turn 文帝 or another title into a kinship person.
    if _title_like(surface) and not canonical_surface:
        kind = "person_office_title" if any(resolver.matching_normalize(marker) in folded for marker in OFFICE_MARKERS) else "person_title"
        return EntityInterpretation(mention_id, kind, "office_title_only" if kind == "person_office_title" else "title_only", "narrative", "office_holder", None, "title-only expression")
    contextual_kin = resolver.parse_structural_kinship_context(
        context, seed_surname=_text(_seed(catalog, raw).get("surname"))
    )
    if contextual_kin and not contextual_kin.get("malformed_person_surface"):
        return EntityInterpretation(mention_id, "kinship_reference", "kinship_plus_name", "genealogical", "kinship_node", contextual_kin, "kinship-bearing abbreviated reference")
    if contextual_kin and contextual_kin.get("malformed_person_surface"):
        return EntityInterpretation(mention_id, "structural_kinship_expression", "kinship_plus_name", "genealogical", "kinship_node", contextual_kin, "multi-node kinship chain")
    if method in {"title", "reviewed_contextual_alias"} and _title_like(surface):
        kind = "person_office_title" if any(resolver.matching_normalize(marker) in folded for marker in OFFICE_MARKERS) else "person_title"
        return EntityInterpretation(mention_id, kind, "office_title_only" if kind == "person_office_title" else "title_only", "narrative", "office_holder", None, "title or office appellation")
    if _title_like(surface) and not any(resolver.matching_normalize(surface) == resolver.matching_normalize(catalog[pid].get("canonical_name")) for pid in index.get(folded, [])):
        kind = "person_office_title" if any(resolver.matching_normalize(marker) in folded for marker in OFFICE_MARKERS) else "person_title"
        return EntityInterpretation(mention_id, kind, "office_title_only" if kind == "person_office_title" else "title_only", "narrative", "office_holder", None, "title-only expression")
    if parsed.get("is_kinship"):
        scope = "genealogical" if any(marker in context or marker in quote for marker in STRUCTURAL_MARKERS) else "narrative"
        return EntityInterpretation(mention_id, "kinship_reference", "kinship_plus_name", scope, "kinship_node", parsed, "kinship-bearing abbreviated reference")
    exact = index.get(folded, [])
    if len(exact) == 1 and resolver.matching_normalize(catalog[exact[0]].get("canonical_name")) == folded:
        return EntityInterpretation(mention_id, "named_person", "full_name", "narrative", "referenced_person", None, "canonical full name")
    if method in {"courtesy_name"} or any(folded == resolver.matching_normalize(form) for pid in exact for form in catalog[pid].get("courtesy_forms", [])):
        return EntityInterpretation(mention_id, "courtesy_name", "courtesy", "narrative", "referenced_person", None, "courtesy-name form")
    if len(folded) <= 1 or method in {"contextual_short_name", "decorated_name_suffix", "source_local_context"}:
        return EntityInterpretation(mention_id, "abbreviated_name", "abbreviated", "narrative", "referenced_person", None, "abbreviated or local form")
    return EntityInterpretation(mention_id, "named_person", "full_name", "narrative", "referenced_person", None, "named-person surface")


def _candidate_rows(
    *, surface: str, context: str, raw: Mapping[str, Any], interpretation: EntityInterpretation,
    catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]],
) -> tuple[list[CandidateEntity], dict[str, Any]]:
    old = _resolution(raw)
    seed = _seed(catalog, raw)
    candidates: dict[str, CandidateEntity] = {}
    pid_values: set[str] = set(str(x) for x in old.get("candidate_set", []) if str(x) in catalog)
    pid_values.update(str(x) for x in old.get("matches", []) if str(x) in catalog)
    pid_values.update(str(x) for x in index.get(resolver.matching_normalize(surface), []) if str(x) in catalog)
    try:
        resolved = resolver.resolve_identity(
            surface=surface, seed=seed, context=context, evidence={}, catalog=catalog, index=index,
            evidence_refs=_refs(raw), temporal={"status": _first([old.get("temporal_status"), "unknown"])},
        )
    except Exception:
        resolved = {}
    pid_values.update(str(x) for x in resolved.get("candidate_set", []) if str(x) in catalog)
    if _text(resolved.get("resolved_person_id")) in catalog:
        pid_values.add(str(resolved["resolved_person_id"]))
    for pid in sorted(pid_values):
        person = catalog[pid]
        candidates[pid] = CandidateEntity(
            candidate_key=f"c{len(candidates)}", person_id=pid,
            canonical_name=_text(person.get("canonical_name")),
            known_forms=resolver.catalog_forms(person), candidate_source="person_catalog",
            graph_summary="independent HNG support available" if old.get("graph_support") else "",
        )
    new_label = _first([
        old.get("normalized_person_surface"), old.get("resolved_label"), old.get("provisional_person_id") and old.get("surface"),
    ])
    kin = old.get("kinship_parse") if isinstance(old.get("kinship_parse"), Mapping) else {}
    if not new_label and kin.get("surname_inheriting") and kin.get("candidate_surface") and not kin.get("malformed_person_surface"):
        new_label = f"{_text(seed.get('surname'))}{_text(kin.get('candidate_surface'))}"
    if interpretation.entity_kind in {"structural_kinship_expression", "generic_role", "person_title", "person_office_title"}:
        new_label = ""
    # A candidate with an old provisional label is retained as a local new
    # entity candidate, never as an existing Person.
    if new_label and not any(resolver.matching_normalize(new_label) == resolver.matching_normalize(item.canonical_name) for item in candidates.values()):
        if len(resolver.matching_normalize(new_label)) >= 2:
            key = f"c{len(candidates)}"
            candidates[new_label] = CandidateEntity(
                candidate_key=key, person_id=None, canonical_name=new_label,
                known_forms=[new_label], candidate_source="replayed_local_identity_candidate",
                graph_summary="",
            )
    by_key = {item.candidate_key: item for item in candidates.values()}
    return list(by_key.values()), resolved


def _constraints(
    *, candidates: Sequence[CandidateEntity], surface: str, context: str, interpretation: EntityInterpretation,
    raw: Mapping[str, Any], source_ref: str, resolved: Mapping[str, Any],
) -> list[ConstraintCheck]:
    result: list[ConstraintCheck] = []
    old = _resolution(raw)
    refs = (source_ref,) if source_ref else tuple(_refs(raw))
    kin = old.get("kinship_parse") if isinstance(old.get("kinship_parse"), Mapping) else {}
    for candidate in candidates:
        folded_surface = resolver.matching_normalize(surface)
        forms = {resolver.matching_normalize(form) for form in candidate.known_forms}
        if folded_surface in forms:
            name_status, name_reason = "strong_support", "catalogue_form"
        elif interpretation.entity_kind in {"abbreviated_name", "kinship_reference"} and folded_surface and any(resolver.matching_normalize(form).endswith(folded_surface) for form in candidate.known_forms if len(resolver.matching_normalize(form)) > 1):
            name_status, name_reason = "weak", "suffix_only"
        else:
            name_status, name_reason = "unknown", "no_direct_form_match"
        result.append(ConstraintCheck("name", candidate.candidate_key, name_status, "python", refs, True, name_reason, "candidate"))
        alias = "support" if folded_surface in {resolver.matching_normalize(x) for x in candidate.known_forms} else "not_applicable"
        result.append(ConstraintCheck("alias", candidate.candidate_key, alias, "python", refs, True, "reviewed_catalogue_form" if alias == "support" else "not_a_catalogue_alias", "candidate"))
        if interpretation.entity_kind in {"person_title", "person_office_title"}:
            title_status = "support" if candidate.person_id and (_text(old.get("resolved_person_id")) == candidate.person_id or candidate.person_id in old.get("candidate_set", [])) else "unknown"
            result.append(ConstraintCheck("title", candidate.candidate_key, title_status, "python", refs, True, "reviewed_title_context" if title_status == "support" else "title_not_unique", "candidate"))
        else:
            result.append(ConstraintCheck("title", candidate.candidate_key, "not_applicable", "python", refs, True, "not_title_case", "candidate"))
        if kin.get("surname_inheriting") and kin.get("family_surname"):
            surname = resolver.matching_normalize(kin.get("family_surname"))
            cand_name = resolver.matching_normalize(candidate.canonical_name)
            kin_status = "support" if cand_name.startswith(surname) else "conflict"
            result.append(ConstraintCheck("kinship", candidate.candidate_key, kin_status, "python", refs, True, "family_surname_match" if kin_status == "support" else "family_surname_conflict", "candidate"))
        elif interpretation.entity_kind == "kinship_reference":
            result.append(ConstraintCheck("kinship", candidate.candidate_key, "weak", "python", refs, True, "kinship_without_safe_surname_inheritance", "candidate"))
        else:
            result.append(ConstraintCheck("kinship", candidate.candidate_key, "not_applicable", "python", refs, True, "not_kinship_case", "candidate"))
        temporal = _first([old.get("temporal_status"), resolved.get("temporal_status"), "unknown"])
        if temporal == "conflict":
            temporal_status, temporal_reason = "conflict", "replayed_temporal_conflict"
        elif temporal == "compatible":
            temporal_status, temporal_reason = "compatible", "replayed_temporal_compatibility"
        else:
            temporal_status, temporal_reason = "unknown", "chronology_not_deterministic"
        result.append(ConstraintCheck("temporal", candidate.candidate_key, temporal_status, "python", refs, True, temporal_reason, "candidate"))
        graph = old.get("graph_support") if isinstance(old.get("graph_support"), Mapping) else {}
        independent_graph = int(graph.get("independent_graph_support_count") or 0)
        result.append(ConstraintCheck("graph_relation", candidate.candidate_key, "support" if independent_graph else "unknown", "python", refs, bool(independent_graph), "independent_graph_support" if independent_graph else "no_independent_graph_support", "candidate"))
        local = "support" if candidate.person_id and resolver.matching_normalize(candidate.canonical_name) in resolver.matching_normalize(context) else "unknown"
        result.append(ConstraintCheck("source_local_context", candidate.candidate_key, local, "python", refs, True, "canonical_name_in_context" if local == "support" else "no_full_name_local_context", "candidate"))
    # Non-candidate constraints are explicitly scoped.  They are immutable
    # controller facts and cannot be supplied or changed by an LLM.
    temporal = _first([old.get("temporal_status"), resolved.get("temporal_status"), "unknown"])
    result.append(ConstraintCheck("temporal", None, temporal if temporal in {"compatible", "unknown", "conflict"} else "unknown", "python", refs, True, "seed_temporal_gate", "seed"))
    result.append(ConstraintCheck("source_local_context", None, "support" if context else "unknown", "python", refs, True, "passage_context_available" if context else "passage_context_missing", "passage"))
    result.append(ConstraintCheck("case_identity", None, "support" if surface else "unknown", "python", refs, True, "observed_surface_present" if surface else "surface_missing", "case"))
    return result


def _recommendation(
    *, interpretation: EntityInterpretation, candidates: Sequence[CandidateEntity], checks: Sequence[ConstraintCheck],
    raw: Mapping[str, Any], resolved: Mapping[str, Any], quote: str,
) -> IdentityRecommendation:
    old = _resolution(raw)
    if interpretation.entity_kind == "structural_kinship_expression":
        return IdentityRecommendation("not_a_single_person", confidence="high", reason_codes=["structural_kinship_chain"], evidence_spans=[quote], unresolved_reason="expression contains multiple kinship nodes")
    if interpretation.entity_kind == "generic_role":
        return IdentityRecommendation("not_a_person", confidence="high", reason_codes=["generic_role"], evidence_spans=[quote], unresolved_reason="generic role is not a single named person")
    if interpretation.entity_kind in {"person_title", "person_office_title"} and interpretation.mention_id:
        pid = _text(old.get("resolved_person_id")) or _text(resolved.get("resolved_person_id"))
        candidate = next((item for item in candidates if item.person_id == pid), None)
        # A reviewed title context may resolve (庾太尉), while a bare title
        # such as 文帝 may not create a new person from its text alone.
        if candidate and _resolution_method(raw) in {"title", "reviewed_contextual_alias"} and pid:
            return IdentityRecommendation("choose_candidate", candidate.candidate_key, "medium", ["reviewed_title_context"], [quote])
        return IdentityRecommendation("ambiguous", confidence="low", reason_codes=["title_only_not_unique"], evidence_spans=[quote], unresolved_reason="title or office appellation lacks unique contextual identity")
    pid = _text(old.get("resolved_person_id")) or _text(resolved.get("resolved_person_id"))
    candidate = next((item for item in candidates if item.person_id == pid), None)
    if candidate:
        return IdentityRecommendation("choose_candidate", candidate.candidate_key, _first([old.get("confidence"), resolved.get("confidence"), "medium"]), ["canonical_or_reviewed_form"], [quote])
    new = next((item for item in candidates if item.person_id is None), None)
    if new and interpretation.entity_kind not in {"generic_role", "structural_kinship_expression"}:
        return IdentityRecommendation("new_person_candidate", new.candidate_key, _first([old.get("confidence"), "medium"]), ["explicit_local_person_candidate"], [quote], {"canonical_name": new.canonical_name}, new_entity_key="n0")
    if len(candidates) > 1:
        return IdentityRecommendation("ambiguous", confidence="low", reason_codes=["multiple_viable_candidates"], evidence_spans=[quote], unresolved_reason="multiple candidates remain")
    return IdentityRecommendation("unresolved", confidence="low", reason_codes=["insufficient_identity_evidence"], evidence_spans=[quote], unresolved_reason="no validated candidate")


def _decision(recommendation: IdentityRecommendation, candidates: Sequence[CandidateEntity], refs: Sequence[str], case_id: str) -> IdentityDecision:
    selected = next((item for item in candidates if item.candidate_key == recommendation.chosen_candidate_key), None)
    if recommendation.decision == "choose_candidate" and selected and selected.person_id:
        return IdentityDecision(identity_status="resolved_existing", chosen_candidate_key=selected.candidate_key, person_id=selected.person_id, confidence=recommendation.confidence, reason_codes=recommendation.reason_codes, supporting_evidence_refs=list(refs), decision_summary=recommendation.summary)
    if recommendation.decision == "new_person_candidate" and selected:
        return IdentityDecision(identity_status="resolved_new_candidate", chosen_candidate_key=selected.candidate_key, confidence=recommendation.confidence, reason_codes=recommendation.reason_codes, supporting_evidence_refs=list(refs), decision_summary=recommendation.summary, new_entity_key=recommendation.new_entity_key or "n0")
    if recommendation.decision == "not_a_single_person":
        return IdentityDecision(identity_status="not_single_person", confidence=recommendation.confidence, reason_codes=recommendation.reason_codes, supporting_evidence_refs=list(refs), decision_summary=recommendation.unresolved_reason)
    if recommendation.decision == "not_a_person":
        return IdentityDecision(identity_status="not_person", confidence=recommendation.confidence, reason_codes=recommendation.reason_codes, supporting_evidence_refs=list(refs), decision_summary=recommendation.unresolved_reason)
    if recommendation.decision == "ambiguous":
        return IdentityDecision(identity_status="ambiguous", confidence=recommendation.confidence, reason_codes=recommendation.reason_codes, supporting_evidence_refs=list(refs), decision_summary=recommendation.unresolved_reason)
    return IdentityDecision(identity_status="unresolved", confidence=recommendation.confidence, reason_codes=recommendation.reason_codes, supporting_evidence_refs=list(refs), decision_summary=recommendation.unresolved_reason)


def _graph_action(decision: IdentityDecision, interpretation: EntityInterpretation, refs: Sequence[str], provisional_person_id: str | None = None) -> GraphAction:
    if decision.identity_status == "resolved_existing":
        return GraphAction("link_existing", "existing_person", person_id=decision.person_id, frontier_status="eligible", reason_codes=["resolved_existing", "traceable_evidence"])
    if decision.identity_status == "resolved_new_candidate":
        return GraphAction("create_provisional_candidate", "provisional_person", provisional_person_id=provisional_person_id, frontier_status="eligible", reason_codes=["resolved_new_candidate", "traceable_evidence"])
    if decision.identity_status == "not_single_person":
        return GraphAction("no_person_node", "none", frontier_status="blocked", reason_codes=["structural_expression_not_single_person"])
    if decision.identity_status == "not_person":
        return GraphAction("no_person_node", "none", frontier_status="blocked", reason_codes=["generic_role"])
    if decision.identity_status == "ambiguous":
        return GraphAction("hold_for_review", "none", frontier_status="needs_identity_review", reason_codes=["identity_ambiguity"])
    return GraphAction("hold_for_review", "none", frontier_status="needs_semantic_parse", reason_codes=["identity_unresolved"])


def _gap(decision: IdentityDecision, interpretation: EntityInterpretation, candidates: Sequence[CandidateEntity]) -> ResearchGap:
    if decision.identity_status in {"resolved_existing", "resolved_new_candidate", "not_person"}:
        return ResearchGap("closed", [], "", "none", [], "identity decision is sufficient for current replay")
    if decision.identity_status == "not_single_person":
        return ResearchGap("open", ["structural_kinship_parse"], "Which individuals are represented by the kinship chain?", "search_kinship_context", [c.candidate_key for c in candidates], "do not create a node until the chain is parsed")
    if interpretation.entity_kind in {"person_title", "person_office_title"}:
        return ResearchGap("open", ["title_identity"], "Which historical person does this title denote in this passage?", "search_title_identity", [c.candidate_key for c in candidates], "stop when one context-compatible person is independently supported")
    if decision.identity_status == "ambiguous":
        return ResearchGap("open", ["candidate_disambiguation"], "Which candidate is supported by independent source-local evidence?", "human_review", [c.candidate_key for c in candidates], "stop when one candidate has non-circular support")
    return ResearchGap("open", ["identity_evidence"], "What source-local evidence identifies this surface?", "search_biography_context", [c.candidate_key for c in candidates], "stop when an exact or structurally explicit identity is found")


def _build_case(row: Mapping[str, Any], stage: str, ordinal: int, evidence: Mapping[str, Mapping[str, Any]], live_index: Mapping[str, Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]]) -> HistoricalEntityResolutionCase:
    raw = dict(row)
    surface = _surface(raw)
    refs = _refs(raw)
    if stage == "hng2-live":
        linked = live_index.get(_text(raw.get("occurrence_id")), {})
        refs = _refs(linked) or refs
        if not refs:
            refs = [_live_source_ref(raw, live_index)]
    source_ref = refs[0] if refs else f"{stage}:{_text(raw.get('candidate_id') or raw.get('occurrence_id'))}"
    quote = _row_exact_span(raw, refs, evidence)
    context = _context(raw)
    source_work = _source_work(raw, refs, evidence)
    mention_id = f"{stage}-{_text(raw.get('candidate_id') or raw.get('occurrence_id')) or stable_hash(raw)[:20]}"
    observation = MentionObservation(mention_id, surface, quote, source_ref, source_work, _locator(raw, refs, evidence))
    interpretation = _interpretation(mention_id=mention_id, surface=surface, quote=quote, context=context, source_ref=source_ref, source_work=source_work, raw=raw, catalog=catalog, index=index)
    candidates, resolved = _candidate_rows(surface=surface, context=context, raw=raw, interpretation=interpretation, catalog=catalog, index=index)
    checks = _constraints(candidates=candidates, surface=surface, context=context, interpretation=interpretation, raw=raw, source_ref=source_ref, resolved=resolved)
    recommendation = _recommendation(interpretation=interpretation, candidates=candidates, checks=checks, raw=raw, resolved=resolved, quote=quote)
    decision = _decision(recommendation, candidates, refs, mention_id)
    provisional_id = None
    if decision.identity_status == "resolved_new_candidate":
        selected = next((item for item in candidates if item.candidate_key == decision.chosen_candidate_key), None)
        provisional_id = f"hng2-schema-provisional-{stable_hash({'case_id': mention_id, 'name': selected.canonical_name if selected else ''})[:20]}"
    action = _graph_action(decision, interpretation, refs, provisional_id)
    gap = _gap(decision, interpretation, candidates)
    semantic = SemanticAssessment(mention_id, "assessed", "support" if decision.identity_status in {"resolved_existing", "resolved_new_candidate"} else "unknown", interpretation.discourse_role, [quote], interpretation.summary, True)
    plans = []
    if gap.status == "open":
        plans.append(SearchPlan(gap.missing_constraints[0], gap.blocking_question, gap.candidate_keys, [source_work], [surface], [surface, *STRUCTURAL_MARKERS[:2]], {}, "one_hop", gap.stop_condition))
    return HistoricalEntityResolutionCase(
        case_id=mention_id, observation=observation, interpretation=interpretation,
        candidates=candidates, constraint_checks=checks, semantic_assessment=semantic,
        recommendation=recommendation, decision=decision, graph_action=action,
        research_gap=gap, search_plans=plans, source_stage=stage,
    )


def _collect_identity_rows(document: Mapping[str, Any], key: str, stage: str) -> list[dict[str, Any]]:
    result = []
    for row in document.get(key, []) if isinstance(document.get(key), list) else []:
        if isinstance(row, Mapping) and _surface(row):
            result.append({**dict(row), "_stage": stage})
    return result


def _regression_row(name: str, surface: str, quote: str, source_ref: str, source_work: str, seed_id: str, context: str, resolution: Mapping[str, Any] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "candidate_id": name, "surface": surface, "exact_quote": quote,
        "evidence_refs": [source_ref], "source_work": source_work, "seed_person_id": seed_id,
        "context_excerpt": context, "_stage": "regression",
    }
    if resolution:
        row["resolution"] = dict(resolution)
    return row


def _find_actual(rows: Sequence[Mapping[str, Any]], predicate) -> Mapping[str, Any] | None:
    return next((row for row in rows if predicate(row)), None)


def _build_regression_cases(actual_rows: Sequence[Mapping[str, Any]], evidence: Mapping[str, Mapping[str, Any]], live_index: Mapping[str, Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_surface = lambda s: _find_actual(actual_rows, lambda r: _surface(r) == s)
    rows: list[dict[str, Any]] = []
    source = by_surface("山濤") or by_surface("山涛")
    rows.append(_regression_row("mount-tao", "山涛", "山涛", "regression:catalogue:山濤", "project regression catalogue", "person-043", "山涛 == 山濤"))
    rows.append(_regression_row("yu-taiwei", "庾太尉", "庾太尉", "regression:reviewed-title:庾亮", "世說新語", "person-065", "武昌孟嘉作庾太尉州從事", {"resolution_status": "resolved_existing_person", "resolved_person_id": "person-010", "resolution_method": "title", "confidence": "high", "candidate_set": ["person-010"]}))
    rows.append(_regression_row("bian-dun", "敦", "從父兄敦", "hng02-jinshu-wikisource-punctuated-070", "晉書", "person-029", "卞壼（從父兄敦）", {"resolution_status": "provisional", "resolved_label": "卞敦", "resolution_method": "kinship_context", "confidence": "medium", "kinship_parse": {"is_kinship": True, "kinship_marker": "從父兄", "surname_inheriting": True, "family_surname": "卞", "candidate_surface": "敦"}}))
    rows.append(_regression_row("structural-kinship", "喜弟預女", "娉喜弟預女為妻", "hng01-jinshu-088-liezhuan-007", "晉書", "person-015", "孫晷娉喜弟預女為妻"))
    rows.append(_regression_row("title-wendi", "文帝", "文帝", "regression:title-only:文帝", "晉書", "person-039", "文帝"))
    rows.append(_regression_row("metatext-yuanhong", "袁宏", "袁宏《紀》", "hng02-zizhi-tongjian-wikisource-hu-062", "資治通鑑", "person-012", "袁宏《紀》"))
    for name in ("王敦", "王導", "桓溫", "郗鑒", "王戎", "劉伶", "蘇峻"):
        pid = next((pid for pid, person in catalog.items() if _text(person.get("canonical_name")) == name), "")
        rows.append(_regression_row(f"exact-{name}", name, name, f"regression:catalogue:{name}", "project regression catalogue", pid, name))
    cases = [_build_case(row, "regression", index_no, evidence, live_index, catalog, index) for index_no, row in enumerate(rows)]
    case_dicts = [to_dict(case) for case in cases]
    by_id = {case.case_id: case for case in cases}
    checks: list[dict[str, Any]] = []
    def assertion(case_id: str, label: str, passed: bool, details: Mapping[str, Any]) -> dict[str, Any]:
        return {"case_id": case_id, "label": label, "passed": bool(passed), "details": dict(details)}
    for case in cases:
        d = case.decision
        a = case.graph_action
        checks.append(assertion(case.case_id, case.case_id, d is not None and a is not None, {"identity_status": d.identity_status if d else None, "graph_action": a.action if a else None}))
    mount = by_id["regression-mount-tao"]
    checks.append(assertion(mount.case_id, "山涛 normalizes to 山濤", mount.decision.identity_status == "resolved_existing" and mount.decision.person_id == "person-043" and mount.graph_action.action == "link_existing", {"person_id": mount.decision.person_id, "identity_status": mount.decision.identity_status}))
    yu = by_id["regression-yu-taiwei"]
    checks.append(assertion(yu.case_id, "庾太尉 reviewed context", yu.decision.person_id == "person-010", {"person_id": yu.decision.person_id, "entity_kind": yu.interpretation.entity_kind}))
    bian = by_id["regression-bian-dun"]
    wang_dun = next((pid for pid, person in catalog.items() if _text(person.get("canonical_name")) == "王敦"), "")
    checks.append(assertion(bian.case_id, "卞壼 kinship does not bind 王敦", bian.decision.person_id != wang_dun and bian.decision.identity_status == "resolved_new_candidate", {"person_id": bian.decision.person_id, "new_entity_key": bian.decision.new_entity_key, "graph_provisional_person_id": bian.graph_action.provisional_person_id, "candidate_names": [c.canonical_name for c in bian.candidates]}))
    structural = by_id["regression-structural-kinship"]
    checks.append(assertion(structural.case_id, "喜弟預女 is not one person", structural.decision.identity_status == "not_single_person" and structural.graph_action.action == "no_person_node" and structural.graph_action.frontier_status == "blocked", {"identity_status": structural.decision.identity_status, "frontier_status": structural.graph_action.frontier_status}))
    wendi = by_id["regression-title-wendi"]
    checks.append(assertion(wendi.case_id, "文帝 is title-review, not a new person", wendi.interpretation.entity_kind == "person_title" and wendi.decision.identity_status == "ambiguous" and wendi.graph_action.frontier_status == "needs_identity_review", {"identity_status": wendi.decision.identity_status, "graph_action": wendi.graph_action.action}))
    yuan = by_id["regression-metatext-yuanhong"]
    checks.append(assertion(yuan.case_id, "袁宏《紀》 is metatextual cited author", yuan.interpretation.entity_kind == "named_person" and yuan.interpretation.mention_scope == "metatextual" and yuan.interpretation.discourse_role == "cited_author" and yuan.interpretation.discourse_role != "event_participant", {"mention_scope": yuan.interpretation.mention_scope, "discourse_role": yuan.interpretation.discourse_role}))
    for name in ("王敦", "王導", "桓溫", "郗鑒", "王戎", "劉伶", "蘇峻"):
        case = by_id[f"regression-exact-{name}"]
        expected = next(pid for pid, person in catalog.items() if _text(person.get("canonical_name")) == name)
        checks.append(assertion(case.case_id, f"exact canonical {name}", case.decision.identity_status == "resolved_existing" and case.decision.person_id == expected, {"person_id": case.decision.person_id, "expected": expected}))
    # Relation schema regression: free text is kept in its description while
    # the level remains the controlled enum.
    relation = RelationAssertion("regression-relation-zhongya", "person-058", "person-017", "shared_explicit_event", "documented_interaction", "co-participants in military command", ["regression:relation:鍾雅"], [{"ref": "regression:relation:鍾雅", "quote": "鍾雅與人共掌軍事"}])
    checks.append({"case_id": "regression-relation-zhongya", "label": "鍾雅 semantic description does not populate level", "passed": relation.semantic_level == "documented_interaction" and relation.relation_semantics_description == "co-participants in military command", "details": to_dict(relation)})
    return case_dicts, checks


def _relation_assertions() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    sources = [
        (HNG1R2_ROOT / "relations.json", "hng1r2", "relations"),
        (HNG2_ROOT / "relations.json", "hng2", "relations"),
        (HNG2_LIVE_ROOT / "relations.json", "hng2-live", "relations"),
    ]
    for path, stage, key in sources:
        document = read_json(path, {}) or {}
        for ordinal, row in enumerate(document.get(key, []) if isinstance(document.get(key), list) else []):
            if not isinstance(row, Mapping):
                continue
            level = _text(row.get("semantic_level"))
            if level not in {"hard_relation", "documented_interaction", "interpreted_relation"}:
                level = "documented_interaction" if _text(row.get("normalized_relation_type") or row.get("relation_type")) else "interpreted_relation"
            relation_type = _first([row.get("normalized_relation_type"), row.get("relation_type"), "documented_interaction"])
            quotes = _quote_items(row)
            result.append(to_dict(RelationAssertion(
                f"{stage}-{_text(row.get('relation_id')) or stable_hash({'stage': stage, 'ordinal': ordinal})[:20]}",
                _first([row.get("person_a"), (row.get("direction") or {}).get("from") if isinstance(row.get("direction"), Mapping) else ""]),
                _first([row.get("person_b"), (row.get("direction") or {}).get("to") if isinstance(row.get("direction"), Mapping) else ""]),
                relation_type, level,
                _first([row.get("relation_semantics_description"), row.get("normalization_reason"), row.get("claim"), "source-supported historical interaction"]),
                _refs(row), quotes, "candidate", False,
            )))
    return sorted(result, key=lambda row: row["relation_id"])


def _migration(cases: Sequence[Mapping[str, Any]], source_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    old_statuses = collections.Counter()
    for row in source_rows:
        old = _old_status(row)
        if old:
            old_statuses[old] += 1
    mapping = collections.Counter()
    for case in cases:
        status = case["decision"]["identity_status"]
        interpretation = case["interpretation"]["entity_kind"]
        if status == "resolved_new_candidate": mapping["resolved_new_candidate"] += 1
        elif status == "ambiguous": mapping["ambiguous"] += 1
        elif status == "not_single_person": mapping["structural_expression"] += 1
        elif interpretation in {"person_title", "person_office_title", "generic_role"} and status not in {"resolved_existing", "resolved_new_candidate"}:
            mapping["title_role_needing_review"] += 1
        elif status == "resolved_existing": mapping["resolved_existing_after_normalization"] += 1
    stale = []
    for label in ("山涛", "文帝"):
        matches = [case for case in cases if case["observation"]["surface"] == label]
        if matches:
            case = sorted(matches, key=lambda item: item["case_id"])[0]
            stale.append({"surface": label, "old_status": "provisional", "new_identity_status": case["decision"]["identity_status"], "graph_action": case["graph_action"]["action"], "frontier_status": case["graph_action"]["frontier_status"], "reason": "schema separates existing identity/title ambiguity from provisional graph nodes"})
    return {"old_status_counts": dict(sorted(old_statuses.items())), "old_provisional_count": int(sum(value for key, value in old_statuses.items() if "provisional" in key)), "new_mapping_counts": dict(sorted(mapping.items())), "stale_provisional_frontiers": stale}


def build(*, output_root: Path = OUTPUT_ROOT, force: bool = False) -> dict[str, Any]:
    # HNG2-SL treats the checked-in HNG2-S replay as an immutable baseline.
    # The hardened projection can be built explicitly into a new generated
    # directory with --output-root; the default command remains a harmless
    # deterministic check for the existing baseline.
    if output_root == OUTPUT_ROOT and output_root.is_dir() and not force:
        metrics = read_json(output_root / "metrics.json", {}) or {}
        validation = read_json(output_root / "validation-cases.json", {}) or {}
        return {
            "case_count": metrics.get("case_count", 0),
            "regression_case_count": metrics.get("regression_case_count", len(validation.get("regression_case_records", []))),
            "validation_all_passed": validation.get("all_passed", True),
            "identity_status_counts": metrics.get("identity_status_counts", {}),
            "preserved_existing_projection": True,
        }
    catalog = resolver.person_catalog()
    index = resolver.forms_index(catalog)
    evidence = _source_evidence()
    live_index = _live_evidence_index()
    hng1r2_identity = read_json(INPUT_FILES["hng1r2_identity"], {}) or {}
    hng2_identity = read_json(INPUT_FILES["hng2_identity"], {}) or {}
    live_identity = read_json(INPUT_FILES["hng2_live_identity"], {}) or {}
    rows: list[tuple[str, Mapping[str, Any]]] = []
    for row in _collect_identity_rows(hng1r2_identity, "resolutions", "hng1r2"):
        rows.append(("hng1r2", row))
    for row in _collect_identity_rows(hng2_identity, "resolutions", "hng2"):
        rows.append(("hng2", row))
    for row in _collect_identity_rows(live_identity, "records", "hng2-live"):
        rows.append(("hng2-live", row))
    cases = [_build_case(row, stage, ordinal, evidence, live_index, catalog, index) for ordinal, (stage, row) in enumerate(rows)]
    case_dicts = [to_dict(case) for case in cases]
    regression_case_dicts, validation_cases = _build_regression_cases(rows and [row for _, row in rows] or [], evidence, live_index, catalog, index)
    case_dicts = sorted(case_dicts, key=lambda row: row["case_id"])
    relation_assertions = _relation_assertions()
    mentions = [row["observation"] for row in case_dicts]
    interpretations = [row["interpretation"] for row in case_dicts]
    candidates = [{"case_id": row["case_id"], "candidates": row["candidates"]} for row in case_dicts]
    constraint_checks = [{"case_id": row["case_id"], "checks": row["constraint_checks"]} for row in case_dicts]
    decisions = [{"case_id": row["case_id"], **row["decision"]} for row in case_dicts]
    graph_actions = [{"case_id": row["case_id"], **row["graph_action"]} for row in case_dicts]
    research_gaps = [{"case_id": row["case_id"], **row["research_gap"]} for row in case_dicts]
    entity_counts = collections.Counter(row["interpretation"]["entity_kind"] for row in case_dicts)
    status_counts = collections.Counter(row["decision"]["identity_status"] for row in case_dicts)
    scope_counts = collections.Counter(row["interpretation"]["mention_scope"] for row in case_dicts)
    role_counts = collections.Counter(row["interpretation"]["discourse_role"] for row in case_dicts)
    gap_counts = collections.Counter(row["research_gap"]["status"] for row in case_dicts)
    source_rows = [row for _, row in rows]
    migration = _migration(case_dicts, source_rows)
    metrics = {
        "schema": SCHEMA_VERSION,
        "execution_kind": "offline_deterministic_replay",
        "model_calls": 0,
        "api_calls": 0,
        "replay_input_counts": {"hng1r2": len(_collect_identity_rows(hng1r2_identity, "resolutions", "hng1r2")), "hng2": len(_collect_identity_rows(hng2_identity, "resolutions", "hng2")), "hng2_live": len(_collect_identity_rows(live_identity, "records", "hng2-live"))},
        "case_count": len(case_dicts),
        "regression_case_count": len(regression_case_dicts),
        "entity_kind_counts": dict(sorted(entity_counts.items())),
        "identity_status_counts": dict(sorted(status_counts.items())),
        "mention_scope_counts": dict(sorted(scope_counts.items())),
        "discourse_role_counts": dict(sorted(role_counts.items())),
        "research_gap_counts": dict(sorted(gap_counts.items())),
        "resolved_new_candidate_count": status_counts.get("resolved_new_candidate", 0),
        "title_role_blocked_from_frontier": sum(1 for row in case_dicts if row["interpretation"]["entity_kind"] in {"person_title", "person_office_title"} and row["graph_action"]["frontier_status"] != "eligible"),
        "structural_kinship_case_count": entity_counts.get("structural_kinship_expression", 0),
        "metatextual_cited_author_count": sum(1 for row in case_dicts if row["interpretation"]["mention_scope"] == "metatextual" and row["interpretation"]["discourse_role"] == "cited_author"),
        "migration": migration,
        "schema_suitable_for_targeted_live_validation": True,
        "semantic_assist_contract_question_count": len(CHINESE_SEMANTIC_ASSIST_QUESTIONS),
    }
    protected_roots = {
        label: ROOT / "data/generated" / label
        for label in ("hng0", "hng0-1", "hng0-2", "hng0-2r", "hng1", "hng1r", "hng1r2", "hng2", "hng2-live")
    }
    protected_roots["srm0"] = ROOT / "data/generated/srm0"
    protected_hashes = {label: hash_tree(path) for label, path in sorted(protected_roots.items())}
    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in INPUT_FILES.values() if path.is_file()}
    project_files = [
        ROOT / "data/people.json", ROOT / "data/aliases.json",
        ROOT / "data/derived/person-story-links.json", ROOT / "data/story-chain-gold-set.json",
    ]
    project_input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in project_files if path.is_file()}
    manifest = {
        "schema": SCHEMA_VERSION,
        "stage": "hng2-schema-offline-replay",
        "execution_kind": "offline_deterministic_replay",
        "model": {"provider": "deepseek", "model": "deepseek-v4-flash", "model_calls": 0, "api_calls": 0},
        "canonical_write_back": False,
        "source_inputs": sorted(str(path.relative_to(ROOT)) for path in INPUT_FILES.values()),
        "input_hashes": dict(sorted(input_hashes.items())),
        "project_input_hashes": dict(sorted(project_input_hashes.items())),
        "protected_artifact_hashes": protected_hashes,
        "resolver_version": resolver.RESOLVER_VERSION,
        "output_files": OUTPUT_FILES,
        "replay_contract": "MentionObservation -> EntityInterpretation -> CandidateGeneration -> HardConstraints -> SemanticAssessment -> IdentityRecommendation -> Python IdentityDecision -> GraphAction/ResearchGap",
        "llm_semantic_assist_contract": list(CHINESE_SEMANTIC_ASSIST_QUESTIONS),
    }
    documents = {
        "cases.json": {"schema": SCHEMA_VERSION, "stage": "offline_replay", "cases": case_dicts, "canonical_write_back": False},
        "mentions.json": {"schema": SCHEMA_VERSION, "mentions": mentions, "canonical_write_back": False},
        "entity-interpretations.json": {"schema": SCHEMA_VERSION, "interpretations": interpretations, "canonical_write_back": False},
        "candidates.json": {"schema": SCHEMA_VERSION, "case_candidates": candidates, "canonical_write_back": False},
        "constraint-checks.json": {"schema": SCHEMA_VERSION, "case_constraints": constraint_checks, "hard_constraints_computed_by": "python", "canonical_write_back": False},
        "identity-decisions.json": {"schema": SCHEMA_VERSION, "decisions": decisions, "canonical_write_back": False},
        "graph-actions.json": {"schema": SCHEMA_VERSION, "actions": graph_actions, "canonical_write_back": False},
        "research-gaps.json": {"schema": SCHEMA_VERSION, "gaps": research_gaps, "search_plans": [plan for row in case_dicts for plan in row.get("search_plans", [])], "canonical_write_back": False},
        "relation-assertions.json": {"schema": SCHEMA_VERSION, "relations": relation_assertions, "canonical_write_back": False},
        "validation-cases.json": {"schema": SCHEMA_VERSION, "regression_case_records": regression_case_dicts, "regression_cases": validation_cases, "all_passed": all(bool(row.get("passed")) for row in validation_cases), "canonical_write_back": False},
        "metrics.json": metrics,
        "manifest.json": manifest,
    }
    if output_root.exists():
        for path in sorted(output_root.iterdir()):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
    output_root.mkdir(parents=True, exist_ok=True)
    for name in OUTPUT_FILES:
        write_json(output_root / name, documents[name])
    return {"case_count": len(case_dicts), "regression_case_count": len(regression_case_dicts), "validation_all_passed": documents["validation-cases.json"]["all_passed"], "identity_status_counts": metrics["identity_status_counts"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--rebuild", action="store_true", help="rebuild the specified generated projection")
    args = parser.parse_args()
    result = build(output_root=args.output_root, force=args.rebuild)
    if not args.quiet:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
