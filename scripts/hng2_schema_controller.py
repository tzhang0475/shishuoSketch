#!/usr/bin/env python3
"""Structured Evidence Card controller for HNG2-SC.

This module is intentionally independent of the historical expansion runners.
It accepts a model envelope, validates the evidence card, and projects only
validated structured fields into candidates, constraints, state deltas, and a
Python-owned ResearchGap.  It never writes canonical data and never interprets
free-text summaries for control flow.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, Mapping, Sequence

import build_hng0_2 as hng02
import historical_entity_resolver as resolver
import historical_entity_schema as schema
from hng0_1_common import quote_matches, stable_hash


CARD_TOP_FIELDS = {
    "evidence_interpretation", "semantic_assessment", "identity_recommendation", "research_gap",
}
SEMANTIC_FIELDS = {
    "assessment_status", "semantic_fit", "observed_role", "evidence_spans", "summary",
}
RECOMMENDATION_FIELDS = {
    "decision", "chosen_candidate_key", "confidence", "reason_codes", "evidence_spans",
    "new_entity_candidate", "new_entity_key", "unresolved_reason", "summary",
}
GAP_FIELDS = {
    "status", "missing_constraints", "blocking_question", "next_best_action",
    "candidate_keys", "stop_condition",
}
FORBIDDEN_ID_KEYS = {
    "person_id", "provisional_person_id", "relation_id", "graph_id", "candidate_id", "candidate_key",
}
LOCAL_ENTITY_RE = re.compile(r"^e[0-9]+$")
LOCAL_ASSERTION_RE = re.compile(r"^a[0-9]+$")
LOCAL_NEW_ENTITY_RE = re.compile(r"^n[0-9]+$")

ASSERTION_TO_CONSTRAINT = {
    "identity_equivalence": ("name", "support"),
    "alias_of": ("alias", "support"),
    "courtesy_name_of": ("alias", "support"),
    "title_of": ("title", "support"),
    "office_held_by": ("office", "support"),
    "parent_child": ("kinship", "support"),
    "sibling": ("kinship", "support"),
    "kinship_relation": ("kinship", "support"),
    "participates_in_event": ("event", "support"),
    "temporal_statement": ("temporal", "support"),
    "person_mention": ("source_local_context", "support"),
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _json_object(text: str) -> Any:
    """Extract one JSON object without semantic repair."""

    raw = str(text or "").strip()
    if not raw:
        raise ValueError("empty_response_text")
    decoder = json.JSONDecoder()
    starts = [index for index, char in enumerate(raw) if char == "{"]
    for start in starts:
        try:
            value, end = decoder.raw_decode(raw[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, Mapping):
            trailing = raw[start + end:].strip()
            if not trailing or trailing in {"```", "```json"}:
                return value
    raise ValueError("json_object_not_found")


def extract_response_payload(response: Mapping[str, Any]) -> tuple[Any | None, str, str | None]:
    """Prefer content; fall back to reasoning_content only when needed."""

    choices = response.get("choices") if isinstance(response, Mapping) else None
    message = choices[0].get("message") if isinstance(choices, list) and choices and isinstance(choices[0], Mapping) else {}
    content = _text((message or {}).get("content"))
    reasoning = _text((message or {}).get("reasoning_content"))
    if content:
        try:
            return _json_object(content), "content", None
        except ValueError as exc:
            return None, "content", type(exc).__name__
    if reasoning:
        try:
            return _json_object(reasoning), "reasoning_content", None
        except ValueError as exc:
            return None, "reasoning_content", type(exc).__name__
    return None, "none", "empty_response"


def _valid_local_key(value: Any, pattern: re.Pattern[str]) -> bool:
    return bool(pattern.fullmatch(_text(value)))


def _provided_ids(value: Any, *, path: str = "") -> list[str]:
    """Find forbidden provider-owned IDs in model JSON.

    Candidate keys are allowed only in the Python-provided candidate list and
    in the model's selected-candidate field, so this scan is limited to
    canonical/graph/relation identifier field names.
    """

    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) in FORBIDDEN_ID_KEYS:
                found.append(f"{path}.{key}" if path else str(key))
            found.extend(_provided_ids(child, path=f"{path}.{key}" if path else str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_provided_ids(child, path=f"{path}[{index}]"))
    return found


def _evidence_pair(value: Any) -> tuple[str, str] | None:
    if not isinstance(value, Mapping):
        return None
    ref = _text(value.get("ref") or value.get("evidence_ref"))
    span = _text(value.get("span") or value.get("evidence_span") or value.get("quote"))
    return (ref, span) if ref and span else None


def validate_evidence_span(ref: str, span: str, passages: Mapping[str, Mapping[str, Any]]) -> tuple[bool, bool]:
    source = _text((passages.get(ref) or {}).get("text"))
    if source and span in source:
        return True, False
    if source and quote_matches(source, span):
        return True, True
    return False, False


def _validate_evidence_list(items: Any, passages: Mapping[str, Mapping[str, Any]], label: str) -> tuple[list[dict[str, Any]], list[str], int]:
    valid: list[dict[str, Any]] = []
    errors: list[str] = []
    boundary = 0
    if not isinstance(items, list):
        return [], [f"{label}_not_array"], 0
    for index, item in enumerate(items):
        pair = _evidence_pair(item)
        if not pair:
            errors.append(f"{label}[{index}]:malformed")
            continue
        ref, span = pair
        ok, normalized = validate_evidence_span(ref, span, passages)
        if not ok:
            errors.append(f"{label}[{index}]:span_not_found:{ref}")
            continue
        boundary += int(normalized)
        valid.append({"ref": ref, "span": span, "boundary_punctuation_normalized": normalized})
    return valid, errors, boundary


def validate_card_payload(payload: Any, case: Mapping[str, Any], passages: Mapping[str, Mapping[str, Any]], candidate_rows: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Strictly validate the complete card/envelope before any projection."""

    errors: list[str] = []
    invalid_enums: list[str] = []
    invented_ids = _provided_ids(payload)
    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": ["payload_not_object"], "invalid_enum_outputs": [], "invented_id_attempts": invented_ids, "evidence_span_failures": 0}
    unknown = sorted(set(payload) - CARD_TOP_FIELDS)
    errors.extend(f"unknown_top_field:{key}" for key in unknown)
    card = payload.get("evidence_interpretation")
    assessment = payload.get("semantic_assessment")
    recommendation = payload.get("identity_recommendation")
    gap = payload.get("research_gap")
    if not isinstance(card, Mapping):
        errors.append("missing_evidence_interpretation")
    if not isinstance(assessment, Mapping):
        errors.append("missing_semantic_assessment")
    if not isinstance(recommendation, Mapping):
        errors.append("missing_identity_recommendation")
    if not isinstance(gap, Mapping):
        errors.append("missing_research_gap")

    entity_keys: set[str] = set()
    entity_rows = card.get("entities") if isinstance(card, Mapping) else None
    if not isinstance(entity_rows, list):
        errors.append("evidence_entities_not_array")
        entity_rows = []
    for index, row in enumerate(entity_rows):
        if not isinstance(row, Mapping):
            errors.append(f"entity[{index}]:not_object")
            continue
        key = _text(row.get("entity_key"))
        if not _valid_local_key(key, LOCAL_ENTITY_RE):
            errors.append(f"entity[{index}]:invalid_local_key")
        elif key in entity_keys:
            errors.append(f"entity[{index}]:duplicate_local_key:{key}")
        entity_keys.add(key)
        for field_name in ("surface", "entity_kind", "reference_form", "evidence_ref", "evidence_span"):
            if not _text(row.get(field_name)):
                errors.append(f"entity[{index}]:empty_{field_name}")
        if row.get("entity_kind") not in schema.ENTITY_KINDS:
            invalid_enums.append(f"entity_kind:{row.get('entity_kind')}")
        if row.get("reference_form") not in schema.REFERENCE_FORMS:
            invalid_enums.append(f"reference_form:{row.get('reference_form')}")
        ok, normalized = validate_evidence_span(_text(row.get("evidence_ref")), _text(row.get("evidence_span")), passages)
        if not ok:
            errors.append(f"entity[{index}]:evidence_span_not_found")

    assertion_rows = card.get("assertions") if isinstance(card, Mapping) else None
    if not isinstance(assertion_rows, list):
        errors.append("evidence_assertions_not_array")
        assertion_rows = []
    assertion_ids: set[str] = set()
    for index, row in enumerate(assertion_rows):
        if not isinstance(row, Mapping):
            errors.append(f"assertion[{index}]:not_object")
            continue
        assertion_id = _text(row.get("assertion_id"))
        if assertion_id and (not _valid_local_key(assertion_id, LOCAL_ASSERTION_RE) or assertion_id in assertion_ids):
            errors.append(f"assertion[{index}]:invalid_or_duplicate_id")
        if assertion_id:
            assertion_ids.add(assertion_id)
        atype = row.get("assertion_type")
        if atype not in schema.EVIDENCE_ASSERTION_TYPES:
            invalid_enums.append(f"assertion_type:{atype}")
        subject = _text(row.get("subject_entity_key"))
        object_key = row.get("object_entity_key")
        if subject not in entity_keys:
            errors.append(f"assertion[{index}]:unknown_subject")
        if object_key is not None and _text(object_key) not in entity_keys:
            errors.append(f"assertion[{index}]:unknown_object")
        if not _text(row.get("evidence_ref")) or not _text(row.get("evidence_span")):
            errors.append(f"assertion[{index}]:missing_provenance")
        ok, normalized = validate_evidence_span(_text(row.get("evidence_ref")), _text(row.get("evidence_span")), passages)
        if not ok:
            errors.append(f"assertion[{index}]:evidence_span_not_found")
        if row.get("confidence") not in schema.CONFIDENCE_LEVELS:
            invalid_enums.append(f"assertion_confidence:{row.get('confidence')}")

    if isinstance(assessment, Mapping):
        errors.extend(f"unknown_semantic_field:{key}" for key in set(assessment) - {"assessment_status", "semantic_fit", "observed_role", "evidence_spans", "summary"})
        for key, allowed in (("assessment_status", schema.ASSESSMENT_STATUSES), ("semantic_fit", schema.SEMANTIC_FITS), ("observed_role", schema.DISCOURSE_ROLES)):
            if assessment.get(key) not in allowed:
                invalid_enums.append(f"semantic_assessment.{key}:{assessment.get(key)}")
        _, span_errors, _ = _validate_evidence_list(assessment.get("evidence_spans", []), passages, "semantic_evidence")
        errors.extend(span_errors)
    if isinstance(recommendation, Mapping):
        errors.extend(f"unknown_recommendation_field:{key}" for key in set(recommendation) - {"decision", "chosen_candidate_key", "confidence", "reason_codes", "evidence_spans", "new_entity_candidate", "new_entity_key", "unresolved_reason", "summary"})
        if recommendation.get("decision") not in schema.RECOMMENDATION_DECISIONS:
            invalid_enums.append(f"recommendation.decision:{recommendation.get('decision')}")
        if recommendation.get("confidence") not in schema.CONFIDENCE_LEVELS:
            invalid_enums.append(f"recommendation.confidence:{recommendation.get('confidence')}")
        chosen = recommendation.get("chosen_candidate_key")
        supplied = candidate_rows if candidate_rows is not None else case.get("candidates", [])
        supplied_keys = {str(row.get("candidate_key")) for row in supplied if isinstance(row, Mapping) and row.get("candidate_key")}
        if chosen is not None and str(chosen) not in supplied_keys:
            errors.append(f"invented_candidate_key:{chosen}")
        new_key = recommendation.get("new_entity_key")
        if new_key is not None and not _valid_local_key(new_key, LOCAL_NEW_ENTITY_RE):
            errors.append("invalid_new_entity_key")
        if new_key is not None and recommendation.get("decision") != "new_person_candidate":
            errors.append("new_entity_key_without_new_person_decision")
        if recommendation.get("decision") == "new_person_candidate" and new_key is None:
            errors.append("new_person_candidate_without_new_entity_key")
        if recommendation.get("decision") == "choose_candidate" and chosen is None:
            errors.append("choose_candidate_without_key")
        if recommendation.get("decision") != "choose_candidate" and chosen is not None:
            errors.append("non_choose_candidate_has_key")
        _, span_errors, _ = _validate_evidence_list(recommendation.get("evidence_spans", []), passages, "recommendation_evidence")
        errors.extend(span_errors)
    if isinstance(gap, Mapping):
        errors.extend(f"unknown_gap_field:{key}" for key in set(gap) - {"status", "missing_constraints", "blocking_question", "next_best_action", "candidate_keys", "stop_condition"})
        if gap.get("status") not in schema.RESEARCH_GAP_STATUSES:
            invalid_enums.append(f"research_gap.status:{gap.get('status')}")
        if gap.get("next_best_action") not in schema.RESEARCH_ACTIONS:
            invalid_enums.append(f"research_gap.next_best_action:{gap.get('next_best_action')}")
    if (case.get("interpretation") or {}).get("mention_scope") == "metatextual" and isinstance(assessment, Mapping) and assessment.get("observed_role") in {"event_participant", "speaker"}:
        errors.append("metatextual_role_invariant")
    errors.extend(f"forbidden_or_invented_id:{item}" for item in invented_ids)
    errors.extend(invalid_enums)
    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "invalid_enum_outputs": sorted(set(invalid_enums)),
        "invented_id_attempts": sorted(set(invented_ids)),
        "evidence_span_failures": sum("evidence_span" in error or "span_not_found" in error for error in errors),
    }


def _source_forms(person: Mapping[str, Any]) -> list[str]:
    return resolver.catalog_forms(person)


def _candidate_from_person(key: str, person_id: str, person: Mapping[str, Any], source: str) -> dict[str, Any]:
    return {
        "candidate_key": key,
        "person_id": person_id,
        "canonical_name": _text(person.get("canonical_name")),
        "known_forms": _source_forms(person),
        "candidate_source": source,
        "chronology_summary": "",
        "graph_summary": "",
    }


def _entity_candidate_match(entity: Mapping[str, Any], catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]], context: str) -> list[str]:
    surface = _text(entity.get("surface"))
    folded = resolver.matching_normalize(surface)
    pids = set(str(pid) for pid in index.get(folded, []) if str(pid) in catalog)
    for pid, person in catalog.items():
        forms = _source_forms(person)
        if folded and any(resolver.matching_normalize(form) == folded for form in forms):
            pids.add(str(pid))
    try:
        resolved = resolver.resolve_identity(surface=surface, seed={}, context=context, evidence={}, catalog=catalog, index=index, evidence_refs=[])
    except Exception:
        resolved = {}
    pids.update(str(pid) for pid in resolved.get("candidate_set", []) if str(pid) in catalog)
    if resolved.get("resolved_person_id") in catalog:
        pids.add(str(resolved["resolved_person_id"]))
    return sorted(pids)


def generate_candidates(case: Mapping[str, Any], card: Mapping[str, Any], passages: Mapping[str, Mapping[str, Any]], prior: Sequence[Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Generate/extend candidates strictly from card entities and catalogue."""

    result = [dict(row) for row in prior if isinstance(row, Mapping) and row.get("candidate_key")]
    by_name = {resolver.matching_normalize(_text(row.get("canonical_name"))): row for row in result}
    context = "\n".join(_text(row.get("text")) for row in passages.values())
    entity_to_candidate: dict[str, str] = {}
    for entity in card.get("entities", []) if isinstance(card.get("entities"), list) else []:
        if not isinstance(entity, Mapping):
            continue
        kind = _text(entity.get("entity_kind"))
        if kind in {"generic_role", "not_person", "collective_persons", "structural_kinship_expression", "unknown"}:
            continue
        surface = _text(entity.get("surface"))
        pids = _entity_candidate_match(entity, catalog, index, context)
        chosen_key = None
        for row in result:
            forms = {_text(row.get("canonical_name")), *[_text(x) for x in row.get("known_forms", [])]}
            if resolver.matching_normalize(surface) in {resolver.matching_normalize(x) for x in forms if x}:
                chosen_key = _text(row.get("candidate_key"))
                break
        if chosen_key is None and len(pids) == 1:
            pid = pids[0]
            for row in result:
                if _text(row.get("person_id")) == pid:
                    chosen_key = _text(row.get("candidate_key"))
                    break
            if chosen_key is None:
                key = f"c{len(result)}"
                result.append(_candidate_from_person(key, pid, catalog[pid], "evidence_card_catalogue_match"))
                chosen_key = key
        if chosen_key is None and kind in {"named_person", "courtesy_name", "abbreviated_name", "kinship_reference", "person_title", "person_office_title"} and len(resolver.matching_normalize(surface)) >= 2:
            folded_surface = resolver.matching_normalize(surface)
            if folded_surface not in by_name:
                key = f"c{len(result)}"
                row = {"candidate_key": key, "person_id": None, "canonical_name": surface, "known_forms": [surface], "candidate_source": "evidence_card_named_person", "chronology_summary": "", "graph_summary": ""}
                result.append(row)
                by_name[folded_surface] = row
                chosen_key = key
        if chosen_key:
            entity_to_candidate[_text(entity.get("entity_key"))] = chosen_key
    return result, {"entity_to_candidate": entity_to_candidate}


def _candidate_for_entity(entity_key: str, entity_map: Mapping[str, str]) -> str | None:
    return _text(entity_map.get(entity_key)) or None


def translate_constraints(card: Mapping[str, Any], candidate_info: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]], passages: Mapping[str, Mapping[str, Any]], *, assertion_source: str = "python_card_projection") -> list[dict[str, Any]]:
    """Translate validated assertions into Python-owned ConstraintChecks."""

    entity_map = candidate_info.get("entity_to_candidate") if isinstance(candidate_info.get("entity_to_candidate"), Mapping) else {}
    rows: list[dict[str, Any]] = []
    for index, assertion in enumerate(card.get("assertions", []) if isinstance(card.get("assertions"), list) else []):
        if not isinstance(assertion, Mapping):
            continue
        assertion_id = _text(assertion.get("assertion_id")) or f"a{index}"
        ckey = _candidate_for_entity(_text(assertion.get("subject_entity_key")), entity_map)
        constraint_type, status = ASSERTION_TO_CONSTRAINT.get(_text(assertion.get("assertion_type")), ("source_local_context", "support"))
        if ckey:
            rows.append({
                "constraint_type": constraint_type,
                "candidate_key": ckey,
                "constraint_scope": "candidate",
                "status": status,
                "computed_by": "python",
                "evidence_refs": [_text(assertion.get("evidence_ref"))],
                "evidence_span": _text(assertion.get("evidence_span")),
                "assertion_id": assertion_id,
                "independent": True,
                "reason_code": f"validated_assertion:{_text(assertion.get('assertion_type'))}",
            })
        else:
            rows.append({
                "constraint_type": constraint_type,
                "candidate_key": None,
                "constraint_scope": "passage",
                "status": status,
                "computed_by": "python",
                "evidence_refs": [_text(assertion.get("evidence_ref"))],
                "evidence_span": _text(assertion.get("evidence_span")),
                "assertion_id": assertion_id,
                "independent": True,
                "reason_code": f"unbound_assertion:{_text(assertion.get('assertion_type'))}",
            })
    # Preserve the immutable seed/case constraints in a compact form.
    rows.append({"constraint_type": "source_local_context", "candidate_key": None, "constraint_scope": "case", "status": "support" if passages else "unknown", "computed_by": "python", "evidence_refs": sorted(passages), "evidence_span": "", "assertion_id": None, "independent": True, "reason_code": "supplied_passage"})
    return rows


def _has_identifiable_entity(card: Mapping[str, Any]) -> bool:
    return any(isinstance(row, Mapping) and _text(row.get("entity_kind")) in {"named_person", "courtesy_name", "abbreviated_name", "kinship_reference", "person_title", "person_office_title"} for row in card.get("entities", []) if isinstance(card.get("entities"), list))


def _has_structural_entity(card: Mapping[str, Any]) -> bool:
    return any(isinstance(row, Mapping) and _text(row.get("entity_kind")) == "structural_kinship_expression" for row in card.get("entities", []) if isinstance(card.get("entities"), list))


def recalculate_research_gap(case: Mapping[str, Any], card: Mapping[str, Any], recommendation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]], constraints: Sequence[Mapping[str, Any]], valid_evidence_refs: Sequence[str]) -> dict[str, Any]:
    """Derive the next action from structured evidence, never summary prose."""

    decision = _text(recommendation.get("decision"))
    chosen = _text(recommendation.get("chosen_candidate_key"))
    new_key = _text(recommendation.get("new_entity_key"))
    structural = _has_structural_entity(card)
    identifiable = _has_identifiable_entity(card)
    conflict = any(_text(row.get("status")) == "conflict" for row in constraints if isinstance(row, Mapping))
    supported = any(_text(row.get("status")) in {"strong_support", "support"} for row in constraints if isinstance(row, Mapping))
    if structural or decision in {"not_a_single_person", "not_a_person"}:
        return {"status": "closed", "missing_constraints": [], "blocking_question": "", "next_best_action": "none", "candidate_keys": [], "stop_condition": "structured card establishes that no single Person node is required"}
    selected = next((row for row in candidates if _text(row.get("candidate_key")) == chosen), None)
    # A candidate generated from a card's named surface may be a local
    # evidence candidate without a catalogue person_id. It is not an
    # existing-person resolution, so choosing it cannot close the gap until
    # Python has an existing person to link.
    if decision == "choose_candidate" and chosen and selected and selected.get("person_id") and supported:
        return {"status": "closed", "missing_constraints": [], "blocking_question": "", "next_best_action": "none", "candidate_keys": [], "stop_condition": "validated candidate has structured source support"}
    if decision == "new_person_candidate" and new_key and identifiable and supported:
        return {"status": "closed", "missing_constraints": [], "blocking_question": "", "next_best_action": "none", "candidate_keys": [], "stop_condition": "named new-person candidate is source-supported"}
    old = case.get("research_gap") if isinstance(case.get("research_gap"), Mapping) else {}
    missing = [str(x) for x in old.get("missing_constraints", []) if str(x)] or ["identity_evidence"]
    action = str(old.get("next_best_action") or "human_review")
    if missing[0] == "title_identity":
        action = "search_title_identity"
    elif missing[0] in {"structural_kinship_parse", "kinship"}:
        action = "search_kinship_context"
    elif missing[0] == "temporal":
        action = "search_temporal_evidence"
    elif missing[0] in {"identity_evidence", "short_name_identity"}:
        action = "search_biography_context"
    if action not in schema.RESEARCH_ACTIONS:
        action = "human_review"
    return {"status": "open", "missing_constraints": missing, "blocking_question": str(old.get("blocking_question") or "Structured evidence does not uniquely identify this mention"), "next_best_action": action, "candidate_keys": [str(row.get("candidate_key")) for row in candidates if row.get("candidate_key")], "stop_condition": str(old.get("stop_condition") or "stop when independent source-local evidence resolves the remaining constraint")}


def state_delta(before_candidates: Sequence[Mapping[str, Any]], after_candidates: Sequence[Mapping[str, Any]], before_constraints: Sequence[Mapping[str, Any]], after_constraints: Sequence[Mapping[str, Any]], before_refs: Sequence[str], after_refs: Sequence[str], previous_conflicts: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    before_by = {str(row.get("candidate_key")): row for row in before_candidates if isinstance(row, Mapping) and row.get("candidate_key")}
    after_by = {str(row.get("candidate_key")): row for row in after_candidates if isinstance(row, Mapping) and row.get("candidate_key")}
    before_canonical = {key: json.dumps(row, ensure_ascii=False, sort_keys=True) for key, row in before_by.items()}
    after_canonical = {key: json.dumps(row, ensure_ascii=False, sort_keys=True) for key, row in after_by.items()}
    before_checks = {json.dumps(row, ensure_ascii=False, sort_keys=True) for row in before_constraints if isinstance(row, Mapping)}
    after_checks = {json.dumps(row, ensure_ascii=False, sort_keys=True) for row in after_constraints if isinstance(row, Mapping)}
    added = sorted(set(after_by) - set(before_by))
    removed = sorted(set(before_by) - set(after_by))
    changed = sorted(key for key in set(before_canonical) & set(after_canonical) if before_canonical[key] != after_canonical[key])
    return {
        "new_evidence": sorted(set(after_refs) - set(before_refs)),
        "new_candidates": added,
        "removed_candidates": removed,
        "unchanged_candidates": sorted(set(before_by) & set(after_by) - set(changed)),
        "changed_constraints": sorted(after_checks - before_checks),
        "removed_conflicts": [],
        "new_conflicts": sorted(row for row in after_constraints if isinstance(row, Mapping) and row.get("status") == "conflict" and json.dumps(row, ensure_ascii=False, sort_keys=True) not in before_checks),
        "material": bool(set(after_refs) - set(before_refs) or added or removed or changed or after_checks != before_checks),
    }


def project_identity_decision(case: Mapping[str, Any], recommendation: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]], card: Mapping[str, Any], gap: Mapping[str, Any], supporting_refs: Sequence[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    chosen = _text(recommendation.get("chosen_candidate_key")) or None
    selected = next((row for row in candidates if _text(row.get("candidate_key")) == chosen), None)
    decision = _text(recommendation.get("decision"))
    confidence = _text(recommendation.get("confidence")) or "unknown"
    reasons = [str(x) for x in recommendation.get("reason_codes", []) if str(x)] if isinstance(recommendation.get("reason_codes"), list) else []
    if decision == "choose_candidate" and selected and selected.get("person_id"):
        identity_status = "resolved_existing"
        person_id = _text(selected.get("person_id"))
        new_entity_key = None
        action = {"action": "link_existing", "node_type": "existing_person", "person_id": person_id, "provisional_person_id": None, "frontier_status": "eligible", "reason_codes": ["evidence_card_validated", *reasons]}
    elif decision == "new_person_candidate" and _valid_local_key(recommendation.get("new_entity_key"), LOCAL_NEW_ENTITY_RE) and _has_identifiable_entity(card) and gap.get("status") == "closed":
        identity_status = "resolved_new_candidate"
        person_id = None
        new_entity_key = _text(recommendation.get("new_entity_key"))
        provisional = f"hng2-sc-provisional-{stable_hash({'case_id': case.get('case_id'), 'new_entity_key': new_entity_key})[:20]}"
        action = {"action": "create_provisional_candidate", "node_type": "provisional_person", "person_id": None, "provisional_person_id": provisional, "frontier_status": "candidate", "reason_codes": ["evidence_card_new_person", *reasons]}
    elif decision == "not_a_single_person" or _has_structural_entity(card):
        identity_status = "not_single_person"
        person_id = None
        new_entity_key = None
        action = {"action": "no_person_node", "node_type": "none", "person_id": None, "provisional_person_id": None, "frontier_status": "blocked", "reason_codes": ["structural_kinship_expression", *reasons]}
    elif decision == "not_a_person":
        identity_status = "not_person"
        person_id = None
        new_entity_key = None
        action = {"action": "no_person_node", "node_type": "none", "person_id": None, "provisional_person_id": None, "frontier_status": "blocked", "reason_codes": ["not_person", *reasons]}
    elif decision == "ambiguous":
        identity_status = "ambiguous"
        person_id = None
        new_entity_key = None
        action = {"action": "hold_for_review", "node_type": "none", "person_id": None, "provisional_person_id": None, "frontier_status": "needs_identity_review", "reason_codes": ["ambiguous_recommendation", *reasons]}
    else:
        identity_status = "unresolved"
        person_id = None
        new_entity_key = None
        action = {"action": "hold_for_review", "node_type": "none", "person_id": None, "provisional_person_id": None, "frontier_status": "needs_semantic_parse", "reason_codes": ["unresolved_recommendation", *reasons]}
    decision_doc = {
        "case_id": case.get("case_id"), "identity_status": identity_status, "chosen_candidate_key": chosen if identity_status == "resolved_existing" else None,
        "person_id": person_id, "new_entity_key": new_entity_key, "confidence": confidence, "reason_codes": reasons,
        "supporting_evidence_refs": sorted(set(str(x) for x in supporting_refs if x)), "decision_summary": _text(recommendation.get("summary") or recommendation.get("unresolved_reason")), "canonical_write_back": False,
    }
    return decision_doc, action


def card_to_dict(payload: Mapping[str, Any]) -> dict[str, Any]:
    card = payload.get("evidence_interpretation") if isinstance(payload.get("evidence_interpretation"), Mapping) else {}
    return {"entities": [dict(row) for row in card.get("entities", []) if isinstance(row, Mapping)], "assertions": [dict(row) for row in card.get("assertions", []) if isinstance(row, Mapping)], "summary": _text(card.get("summary"))}


def project_valid_card(case: Mapping[str, Any], payload: Mapping[str, Any], passages: Mapping[str, Mapping[str, Any]], prior_candidates: Sequence[Mapping[str, Any]], prior_constraints: Sequence[Mapping[str, Any]], prior_refs: Sequence[str], catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]]) -> dict[str, Any]:
    card = card_to_dict(payload)
    candidates, candidate_info = generate_candidates(case, card, passages, prior_candidates, catalog, index)
    constraints = translate_constraints(card, candidate_info, candidates, passages)
    recommendation = payload.get("identity_recommendation") if isinstance(payload.get("identity_recommendation"), Mapping) else {}
    refs = sorted(set([_text(row.get("evidence_ref")) for row in card.get("entities", []) if isinstance(row, Mapping)] + [_text(row.get("evidence_ref")) for row in card.get("assertions", []) if isinstance(row, Mapping)] + list(prior_refs)))
    gap = recalculate_research_gap(case, card, recommendation, candidates, constraints, refs)
    decision, action = project_identity_decision(case, recommendation, candidates, card, gap, refs)
    delta = state_delta(prior_candidates, candidates, prior_constraints, constraints, prior_refs, refs)
    return {"card": card, "candidates": candidates, "candidate_info": candidate_info, "constraints": constraints, "recommendation": dict(recommendation), "research_gap": gap, "identity_decision": decision, "graph_action": action, "state_delta": delta, "supporting_refs": refs}


def typed_fallback_search_plan(case: Mapping[str, Any], gap: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    missing = _text((gap.get("missing_constraints") or ["identity_evidence"])[0])
    type_map = {
        "title_identity": ("title_identity", ["晉書", "世說新語", "余嘉錫笺疏"], ["官職", "爵號", "本名"]),
        "structural_kinship_parse": ("kinship", ["晉書", "世說新語", "余嘉錫笺疏"], ["父", "兄", "弟", "子", "女"]),
        "temporal": ("temporal", ["晉書", "資治通鑑", "三國志"], ["年", "即位", "卒"]),
        "short_name_identity": ("short_name_identity", ["晉書", "世說新語", "余嘉錫笺疏"], ["本名", "字", "傳"]),
        "identity_evidence": ("biography_identity", ["晉書", "世說新語", "三國志"], ["字", "本名", "父", "兄"]),
    }
    target, sources, markers = type_map.get(missing, type_map["identity_evidence"])
    surface = _text((case.get("observation") or {}).get("surface"))
    return {
        "target_constraint": target,
        "goal": _text(gap.get("blocking_question")) or "obtain source-local identity evidence",
        "candidate_keys": [str(row.get("candidate_key")) for row in candidates if row.get("candidate_key")],
        "preferred_sources": sources,
        "search_entities": [surface, *[_text(row.get("canonical_name")) for row in candidates if row.get("canonical_name")]],
        "search_patterns": [surface, *markers],
        "temporal_scope": {}, "graph_neighborhood_scope": "case_only",
        "stop_condition": _text(gap.get("stop_condition")) or "stop when exact source-local evidence is found",
        "fallback": True, "gap_type": target,
    }


__all__ = [
    "CARD_TOP_FIELDS", "EVIDENCE_ASSERTION_TYPES", "extract_response_payload", "validate_evidence_span",
    "validate_card_payload", "generate_candidates", "translate_constraints", "recalculate_research_gap",
    "state_delta", "project_identity_decision", "project_valid_card", "typed_fallback_search_plan",
]
