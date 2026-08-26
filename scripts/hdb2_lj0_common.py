#!/usr/bin/env python3
"""Shared, candidate-only helpers for HDB2-LJ0.

LJ0 is an isolated identity-inference experiment.  It deliberately consumes
the frozen HDB2 review projection and existing candidate dossiers, but it
never changes HDB2 decisions or projects canonical data.  The model sees
only local candidate keys and supplied evidence IDs; all scoring and state
transitions below are Python-owned.
"""

from __future__ import annotations

import collections
import hashlib
import json
import re
import statistics
from pathlib import Path
from typing import Any, Mapping, Sequence

import build_hng0_2 as hng02
import historical_entity_resolver as resolver
import hdb2_occurrence_common as occurrence


ROOT = Path(__file__).resolve().parents[1]
ANNOTATION = ROOT / "data/annotation"
DERIVED = ROOT / "data/derived"
REVIEW_ROOT = ROOT / "site/public/generated/review/hdb2"
MODEL = "deepseek-v4-flash"
STRICT_ENDPOINT = "https://api.deepseek.com/beta/chat/completions"
RUN_VERSION = "hdb2-lj0-v1"
PROMPT_VERSION = "hdb2-lj0-grounded-identity-inference-v1"
EVALUATION_FUNCTION = "submit_hdb2_grounded_identity_evaluation"
FALSIFICATION_FUNCTION = "submit_hdb2_identity_falsification"

SUPPORT_FAMILIES = {
    "story_local_context",
    "era_chronology",
    "known_participants",
    "office_title_compatibility",
    "person_relations_network",
    "confirmed_story_profile",
    "relevant_source_evidence",
}
EVIDENCE_STATES = {"strong_support", "support", "neutral", "contradiction", "strong_contradiction"}
CROSS_STORY_STATES = {"supports_profile", "compatible", "contradiction"}
FALSIFICATION_OUTCOMES = {"survives", "falsified", "inconclusive"}
HARD_FORBIDDEN_KEYS = {
    "person_id",
    "provisional_person_id",
    "canonical_person_id",
    "relation_id",
    "graph_id",
    "candidate_id",
}
KINSHIP_SUFFIXES = ("兒", "子", "女", "兄", "弟", "父", "母", "妻", "婿")
RULER_SURFACES = {"帝", "明帝", "武帝", "晉武帝", "文帝", "元帝"}
PERSON_RESULT_STATES = {"high_confidence_contextual", "review_required", "genuinely_unresolved"}
STATE_SCORE = {
    "strong_support": 2,
    "support": 1,
    "neutral": 0,
    "contradiction": -1,
    "strong_contradiction": -2,
}
FAMILY_WEIGHT = {
    "story_local_context": 2,
    "era_chronology": 2,
    "known_participants": 2,
    "office_title_compatibility": 2,
    "person_relations_network": 1,
    "confirmed_story_profile": 1,
    "relevant_source_evidence": 3,
}
# These are deliberately conservative, transparent experiment thresholds.
MIN_HIGH_SCORE = 6
MIN_HIGH_MARGIN = 3
MIN_HIGH_SUPPORT_FAMILIES = 2


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "missing"


def matching(value: Any) -> str:
    return resolver.matching_normalize(str(value or ""))


def load_review_items() -> list[dict[str, Any]]:
    index = read_json(REVIEW_ROOT / "index.json", {}) or {}
    rows: list[dict[str, Any]] = []
    for entry in index.get("items", []):
        path = REVIEW_ROOT / str(entry.get("item_path") or "")
        if path.is_file():
            rows.append(dict(read_json(path, {}) or {}))
    return sorted(rows, key=lambda row: str(row.get("occurrence_id") or ""))


def load_queue() -> dict[str, Any]:
    return read_json(ANNOTATION / "hdb2-f-review-queue.json", {}) or {}


def load_occurrence_cases() -> dict[str, dict[str, Any]]:
    document = read_json(DERIVED / "hdb2-f-occurrence-cases.json", {}) or {}
    return {str(row.get("occurrence_id")): dict(row) for row in document.get("cases", []) if row.get("occurrence_id")}


def load_person_knowledge() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name in ("hdb2-f-person-knowledge.json", "hdb2-f-candidate-person-knowledge.json"):
        document = read_json(DERIVED / name, {}) or {}
        for row in document.get("records", []):
            key = str(row.get("person_id") or row.get("canonical_name") or "")
            if key:
                result[key] = dict(row)
    return result


def load_h0a_context(story_id: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    anchors = read_json(ANNOTATION / "story-temporal-anchors-h0a.json", {}) or {}
    evidence = read_json(ANNOTATION / "story-temporal-evidence-h0a.json", {}) or {}
    for row in anchors.get("records", []):
        if str(row.get("story_id")) == story_id:
            result.append({
                "kind": "story_anchor",
                "precision": row.get("precision"),
                "start_year_ce": row.get("start_year_ce"),
                "end_year_ce": row.get("end_year_ce"),
                "reign_id": row.get("reign_id"),
                "ruler_context_id": row.get("ruler_context_id"),
                "phase_id": row.get("phase_id"),
                "review_status": row.get("review_status"),
            })
    for row in evidence.get("records", []):
        if str(row.get("story_id")) == story_id:
            result.append({
                "kind": "story_evidence",
                "evidence_type": row.get("evidence_type"),
                "raw_surface": row.get("raw_surface"),
                "relation_to_story": row.get("relation_to_story"),
                "normalized_candidate": row.get("normalized_candidate"),
                "review_status": row.get("review_status"),
            })
    return result


def _fact_count(item: Mapping[str, Any], kind: str) -> int:
    return len((item.get("affected_facts") or {}).get(kind, []) or [])


def _selection_value(item: Mapping[str, Any]) -> int:
    facts = item.get("affected_facts") or {}
    status = str((item.get("current_state") or {}).get("status") or item.get("status") or "")
    occurrence_type = str(item.get("occurrence_type") or "")
    return (
        8 * _fact_count(item, "marriage")
        + 7 * _fact_count(item, "kinship")
        + 4 * len(facts.get("relations", []) or [])
        + 2 * len(item.get("candidate_people", []) or [])
        + 2 * int(status in {"unresolved", "contextually_preferred", "office_reference", "ruler_reference"})
        + 2 * int(occurrence_type in {"ruler_reference", "title_reference", "office_reference"})
        + int(item.get("priority") == "P1")
    )


def _selection_category(item: Mapping[str, Any]) -> str:
    review_type = str(item.get("review_type") or "")
    occurrence_type = str(item.get("occurrence_type") or "")
    surface = str(item.get("target_surface") or "")
    if review_type == "candidate_person":
        return "candidate_person"
    if review_type == "compositional_kinship":
        return "compositional_reference"
    if surface in RULER_SURFACES or occurrence_type == "ruler_reference":
        return "ruler_title_reference"
    if review_type == "office_or_title_holder" or occurrence_type in {"title_reference", "office_reference"}:
        return "office_title_holder"
    if review_type == "identity":
        return "ambiguous_identity"
    return "other"


def _selection_row(item: Mapping[str, Any]) -> dict[str, Any]:
    source_refs = sorted({
        str(row.get("evidence_ref"))
        for row in (item.get("selected_evidence") or [])
        if row.get("evidence_ref")
    })
    key_material = {
        "occurrence_id": item.get("occurrence_id"),
        "identity_observation_id": item.get("identity_observation_id"),
        "story_id": item.get("story_id"),
        "surface": item.get("target_surface"),
        "source_refs": source_refs,
    }
    return {
        "review_id": item.get("review_id"),
        "occurrence_id": item.get("occurrence_id"),
        "identity_observation_id": item.get("identity_observation_id"),
        "story_id": item.get("story_id"),
        "surface": item.get("target_surface"),
        "review_type": item.get("review_type"),
        "occurrence_type": item.get("occurrence_type"),
        "current_status": (item.get("current_state") or {}).get("status") or item.get("status"),
        "priority": item.get("priority"),
        "selection_category": _selection_category(item),
        "selection_value": _selection_value(item),
        "blocked_fact_counts": {kind: _fact_count(item, kind) for kind in ("relations", "kinship", "marriage", "office")},
        "source_refs": source_refs,
        "selection_key": stable_hash(key_material),
    }


def build_selection(items: Sequence[Mapping[str, Any]], *, limit: int = 24) -> dict[str, Any]:
    if not 20 <= limit <= 30:
        raise ValueError("lj0_selection_limit_out_of_range")
    ordered = sorted(
        (_selection_row(item) for item in items),
        key=lambda row: (-int(row.get("selection_value") or 0), str(row.get("selection_key"))),
    )
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    # These deterministic category representatives guarantee that the pilot
    # tests the requested phenomena without looking at model output.
    required = [
        lambda row: str(row.get("story_id")) == "05-fangzheng-011" and str(row.get("surface")) == "武帝",
        lambda row: row.get("selection_category") == "candidate_person",
        lambda row: row.get("selection_category") == "compositional_reference",
        lambda row: row.get("selection_category") == "ambiguous_identity",
        lambda row: row.get("selection_category") == "office_title_holder",
    ]
    for predicate in required:
        match = next((row for row in ordered if predicate(row) and str(row.get("occurrence_id")) not in selected_ids), None)
        if match:
            selected.append(match)
            selected_ids.add(str(match.get("occurrence_id")))
    for row in ordered:
        if len(selected) >= limit:
            break
        occurrence_id = str(row.get("occurrence_id") or "")
        if occurrence_id not in selected_ids:
            selected.append(row)
            selected_ids.add(occurrence_id)
    if len(selected) != limit:
        raise RuntimeError(f"lj0_selection_count:{len(selected)}")
    selected.sort(key=lambda row: str(row.get("selection_key")))
    queue = load_queue()
    index = read_json(REVIEW_ROOT / "index.json", {}) or {}
    result: dict[str, Any] = {
        "schema": "hdb2-lj0-selection-v1",
        "run_version": RUN_VERSION,
        "prompt_version": PROMPT_VERSION,
        "model": MODEL,
        "temperature": 0,
        "thinking": "disabled",
        "frozen_before_live": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "current_review_count": len(items),
        "selected_count": len(selected),
        "source_inputs": {
            "review_queue_hash": stable_hash(queue),
            "review_index_hash": stable_hash(index),
            "review_queue_file_hash": file_hash(ANNOTATION / "hdb2-f-review-queue.json"),
            "review_index_file_hash": file_hash(REVIEW_ROOT / "index.json"),
        },
        "cases": selected,
        "selection_hash": None,
    }
    result["selection_hash"] = stable_hash({key: value for key, value in result.items() if key != "selection_hash"})
    return result


def freeze_selection(path: Path, items: Sequence[Mapping[str, Any]], *, limit: int = 24) -> dict[str, Any]:
    proposed = build_selection(items, limit=limit)
    if path.is_file():
        existing = read_json(path, {}) or {}
        if existing != proposed:
            raise RuntimeError("hdb2_lj0_frozen_selection_changed")
        return existing
    write_json(path, proposed)
    return proposed


def _catalog_candidates(surface: str, catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for pid in sorted(set(str(x) for x in occurrence._surface_candidates(surface, catalog, index))):
        if pid in catalog:
            result.append({
                "display_name": catalog[pid].get("canonical_name") or pid,
                "person_id": pid,
                "source": "catalogue_surface_match",
                "semantic_type": "person",
            })
    return result


def _ruler_candidates(surface: str, temporal: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return H0A ruler labels without turning them into production Persons."""
    coordinates = read_json(DERIVED / "h0a-temporal-coordinates.json", {}) or {}
    ranges = _story_intervals(temporal)
    rows: list[dict[str, Any]] = []
    for context in coordinates.get("ruler_contexts", []) or []:
        name = str(context.get("ruler_name") or "")
        matches = surface in name or (surface == "武帝" and "武" in name and "帝" in name)
        if not matches:
            continue
        start, end = context.get("start_year_ce"), context.get("end_year_ce")
        if ranges and isinstance(start, int) and isinstance(end, int) and all(end < lo or start > hi for lo, hi in ranges):
            continue
        rows.append({
            "display_name": name,
            "person_id": None,
            "source": "h0a_ruler_registry",
            "semantic_type": "ruler_title",
            "known_activity_context": [{"start_year_ce": start, "end_year_ce": end, "ruler_context_id": context.get("ruler_context_id")}],
        })
    return sorted(rows, key=lambda row: str(row.get("display_name")))[:6]


def _candidate_profile(pid: str | None, display_name: str, knowledge: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    row = knowledge.get(str(pid or ""), {}) if pid else {}
    identity = row.get("identity") or {}
    presence = row.get("story_presence") or {}
    family = row.get("family") or {}
    offices = row.get("offices") or {}
    social = row.get("social") or {}
    temporal = row.get("temporal") or {}
    titles: list[str] = []
    for value in identity.get("titles", []) or []:
        if isinstance(value, Mapping):
            text = str(value.get("title") or value.get("surface") or "")
        else:
            text = str(value or "")
        if text:
            titles.append(text)
    def safe_fact(value: Any, fields: Sequence[str] = ("relation_surface", "relation_class", "story_id", "title", "office", "exact_span", "evidence_ref")) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            return {"value": str(value)}
        return {field: value.get(field) for field in fields if value.get(field) not in (None, "")}

    safe_offices = [safe_fact(value, ("relation_surface", "relation_class", "story_id", "exact_span", "evidence_ref")) for value in offices.get("office_candidates", []) or []]
    safe_kinship = [safe_fact(value) for value in family.get("kinship_candidates", []) or []]
    safe_marriages = [safe_fact(value, ("relation_surface", "relation_class", "story_id", "exact_span", "evidence_ref")) for value in family.get("marriage_candidates", []) or []]
    safe_neighbors = [safe_fact(value, ("relation_surface", "relation_class", "story_id")) for value in social.get("resolved_neighbors", []) or []]
    safe_temporal = [safe_fact(value, ("start_year_ce", "end_year_ce", "event_id", "reign_id", "phase_id")) for value in temporal.get("bounded_intervals", []) or []]
    return {
        "canonical_name": row.get("canonical_name") or display_name,
        "aliases": sorted(set(str(x) for x in identity.get("aliases", []) if x)),
        "courtesy_names": sorted(set(str(x) for x in identity.get("courtesy_names", []) if x)),
        "titles": sorted(set(titles)),
        "confirmed_story_ids": sorted(set(str(x) for x in presence.get("story_ids", []) if x)),
        "known_offices": safe_offices[:8],
        "known_kinship": safe_kinship[:8],
        "known_marriages": safe_marriages[:8],
        "known_neighbors": safe_neighbors[:12],
        "temporal_evidence": safe_temporal[:8],
        "source_works": sorted(set(str(x) for x in (row.get("evidence") or {}).get("source_works", []) if x)),
    }


def _base_surface(surface: str) -> str:
    for suffix in KINSHIP_SUFFIXES:
        if surface.endswith(suffix) and len(surface) > len(suffix):
            return surface[: -len(suffix)]
    return surface


def _story_intervals(story_context: Sequence[Mapping[str, Any]]) -> list[tuple[int, int]]:
    result = []
    for row in story_context:
        start, end = row.get("start_year_ce"), row.get("end_year_ce")
        if isinstance(start, int) and isinstance(end, int):
            result.append((start, end))
    return result


def _activity_conflict(profile: Mapping[str, Any], temporal: Sequence[Mapping[str, Any]]) -> bool:
    intervals = _story_intervals(temporal)
    if not intervals:
        return False
    activities = profile.get("temporal_evidence", [])
    bounded = []
    for row in activities:
        if not isinstance(row, Mapping):
            continue
        start, end = row.get("start_year_ce"), row.get("end_year_ce")
        if isinstance(start, int) and isinstance(end, int):
            bounded.append((start, end))
    return bool(bounded) and all(end < lo or start > hi for start, end in bounded for lo, hi in intervals)


def _build_evidence_items(item: Mapping[str, Any], case: Mapping[str, Any] | None, profiles: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    def add(family: str, source_ref: str, text: Any, kind: str) -> str:
        evidence_id = f"ev{len(items)}"
        items.append({
            "evidence_id": evidence_id,
            "family": family,
            "kind": kind,
            "source_ref": source_ref,
            "text": str(text or ""),
        })
        return evidence_id

    for selected in item.get("selected_evidence", []) or []:
        ref = str(selected.get("evidence_ref") or "")
        if ref:
            add(
                "relevant_source_evidence" if selected.get("source_layer") != "liu_annotation" else "story_local_context",
                ref,
                selected.get("excerpt") or selected.get("text") or "",
                str(selected.get("source_layer") or "source_passage"),
            )
    if case:
        for selected in case.get("evidence_items", []) or []:
            ref = str(selected.get("source_ref") or "")
            if ref and not any(str(row.get("source_ref")) == ref for row in items):
                add(str(selected.get("source_layer") == "liu_annotation" and "story_local_context" or "relevant_source_evidence"), ref, selected.get("text"), str(selected.get("source_layer") or "source_passage"))
    temporal = (case or {}).get("story_temporal_context") or load_h0a_context(str(item.get("story_id") or ""))
    if temporal:
        add("era_chronology", f"h0a:story:{item.get('story_id')}", json.dumps(temporal, ensure_ascii=False, sort_keys=True), "h0a_context")
    neighbors = [
        {
            "display_name": row.get("display_name"),
            "relation_surface": row.get("relation_surface"),
            "relation_class": row.get("relation_class"),
            "story_id": row.get("story_id"),
        }
        for row in ((case or {}).get("local_neighbors") or [])
    ]
    if neighbors:
        add("known_participants", f"hdb2:neighbors:{item.get('occurrence_id')}", json.dumps(neighbors, ensure_ascii=False, sort_keys=True), "known_participants")
    for candidate_key, profile in profiles.items():
        add("confirmed_story_profile", f"hdb2:profile:{candidate_key}", json.dumps(profile, ensure_ascii=False, sort_keys=True), "candidate_profile")
    return items


def build_case(selection_row: Mapping[str, Any], item: Mapping[str, Any], case: Mapping[str, Any] | None, catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]], knowledge: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    case = dict(case or {})
    surface = str(item.get("target_surface") or "")
    occurrence_type = str(item.get("occurrence_type") or case.get("occurrence_type") or "unclear")
    raw_candidates: list[dict[str, Any]] = []
    raw_candidates.extend(dict(row) for row in case.get("candidates", []) or [])
    raw_candidates.extend({
        "display_name": row.get("display_name"),
        "person_id": row.get("person_id"),
        "source": row.get("source") or "review_projection",
        "semantic_type": row.get("semantic_type") or ("ruler_title" if occurrence_type == "ruler_reference" else "person"),
    } for row in item.get("candidate_people", []) or [])
    raw_candidates.extend(_catalog_candidates(surface, catalog, index))
    for pid in (item.get("current_state") or {}).get("candidate_set", []) or []:
        if str(pid) in catalog:
            raw_candidates.append({"display_name": catalog[str(pid)].get("canonical_name"), "person_id": str(pid), "source": "current_candidate_set", "semantic_type": "person"})
    # The current HDB2 queue's new-candidate label is an existing candidate
    # observation, not a model answer.  It is retained as a candidate-only
    # option with no production ID.
    proposed = item.get("proposed_identity") or {}
    if proposed.get("label") and not proposed.get("person_id"):
        proposed_label = str(proposed.get("label"))
        proposed_type = "ruler_title" if occurrence_type == "ruler_reference" and "帝" in proposed_label else "person"
        raw_candidates.append({"display_name": proposed_label, "person_id": None, "source": "existing_candidate_observation", "semantic_type": proposed_type})

    dedup: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in raw_candidates:
        display = str(row.get("display_name") or row.get("name") or "").strip()
        if not display:
            continue
        pid = str(row.get("person_id") or "")
        if not pid:
            matches = sorted(occurrence._surface_candidates(display, catalog, index))
            if len(matches) == 1:
                pid = str(matches[0])
        key = (pid, matching(display), str(row.get("semantic_type") or "person"))
        dedup.setdefault(key, {**row, "display_name": display, "person_id": pid or None})
    ordered = sorted(dedup.values(), key=lambda row: (matching(row.get("display_name")), str(row.get("person_id") or ""), str(row.get("source") or "")))

    temporal = list(case.get("story_temporal_context") or load_h0a_context(str(item.get("story_id") or "")))
    profiles: dict[str, dict[str, Any]] = {}
    candidates: list[dict[str, Any]] = []
    hard_exclusions: list[dict[str, Any]] = []
    base = matching(_base_surface(surface))
    for row in ordered:
        pid = str(row.get("person_id") or "") or None
        display = str(row.get("display_name") or "")
        profile = _candidate_profile(pid, display, knowledge)
        candidate = {**row, "display_name": display, "person_id": pid, "profile": profile}
        reasons: list[str] = []
        if occurrence_type == "kinship_compositional_reference":
            forms = [display, *profile.get("aliases", []), *profile.get("courtesy_names", [])]
            if any(matching(value) == base or matching(value).endswith(base) for value in forms if value):
                reasons.append("compositional_base_person")
        if occurrence_type == "generic_or_non_person_reference":
            reasons.append("non_person_reference")
        if occurrence_type == "ruler_reference" and str(row.get("semantic_type") or "person") != "ruler_title":
            reasons.append("ruler_semantic_type_mismatch")
        if _activity_conflict(profile, temporal):
            reasons.append("hard_temporal_incompatibility")
        if reasons:
            hard_exclusions.append({"display_name": display, "person_id": pid, "reasons": sorted(set(reasons))})
            continue
        candidates.append(candidate)

    # A ruler/title occurrence may have no catalogue candidate but can still
    # be compared against the existing H0A ruler registry labels.
    if occurrence_type == "ruler_reference" and not candidates:
        for row in _ruler_candidates(surface, temporal):
            candidates.append({**row, "profile": _candidate_profile(None, str(row.get("display_name") or ""), knowledge)})
        candidates = sorted(candidates, key=lambda row: matching(row.get("display_name")))[:6]
    for number, candidate in enumerate(candidates):
        candidate["candidate_key"] = f"c{number}"
        profiles[candidate["candidate_key"]] = candidate.get("profile") or {}
    evidence_items = _build_evidence_items(item, case, profiles)
    candidate_evidence_ids = {row.get("evidence_id") for row in evidence_items}
    for candidate in candidates:
        profile_id = next((row.get("evidence_id") for row in evidence_items if row.get("kind") == "candidate_profile" and row.get("source_ref") == f"hdb2:profile:{candidate['candidate_key']}"), None)
        candidate["profile_evidence_id"] = profile_id if profile_id in candidate_evidence_ids else None

    local_neighbors = list(case.get("local_neighbors", []) or [])
    story_context = str(item.get("story_context") or case.get("local_story_context") or "")
    annotation_context = list(item.get("relevant_annotation_context") or case.get("annotation_context") or [])
    return {
        "occurrence_id": item.get("occurrence_id"),
        "identity_observation_id": item.get("identity_observation_id"),
        "review_id": item.get("review_id"),
        "story_id": item.get("story_id"),
        "target_surface": surface,
        "occurrence_type": occurrence_type,
        "current_review_type": item.get("review_type"),
        "current_status": (item.get("current_state") or {}).get("status") or item.get("status"),
        "story_context": story_context,
        "annotation_context": annotation_context,
        "temporal_context": temporal,
        "local_neighbors": local_neighbors,
        "local_relations": list(case.get("local_relations", []) or []),
        "evidence_items": evidence_items,
        "candidates": candidates,
        "candidate_keys": [row.get("candidate_key") for row in candidates],
        "hard_exclusions": hard_exclusions,
        "affected_facts": item.get("affected_facts") or {},
        "candidate_only": True,
        "canonical_write_back": False,
    }


def build_cases(selection: Mapping[str, Any]) -> dict[str, Any]:
    items = {str(row.get("occurrence_id")): row for row in load_review_items()}
    case_map = load_occurrence_cases()
    catalog = hng02.person_catalog()
    index = resolver.forms_index(catalog)
    knowledge = load_person_knowledge()
    cases: list[dict[str, Any]] = []
    for row in selection.get("cases", []):
        occurrence_id = str(row.get("occurrence_id"))
        if occurrence_id not in items:
            raise RuntimeError(f"lj0_selection_item_missing:{occurrence_id}")
        cases.append(build_case(row, items[occurrence_id], case_map.get(occurrence_id), catalog, index, knowledge))
    return {
        "schema": "hdb2-lj0-cases-v1",
        "run_version": RUN_VERSION,
        "selection_hash": selection.get("selection_hash"),
        "cases": cases,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _candidate_wire(candidate: Mapping[str, Any]) -> dict[str, Any]:
    profile = candidate.get("profile") or {}
    return {
        "candidate_key": candidate.get("candidate_key"),
        "name": candidate.get("display_name"),
        "aliases": list(profile.get("aliases", []))[:12],
        "courtesy_names": list(profile.get("courtesy_names", []))[:8],
        "titles": list(profile.get("titles", []))[:8],
        "confirmed_story_ids": list(profile.get("confirmed_story_ids", []))[:12],
        "office_context": list(profile.get("known_offices", []))[:8],
        "kinship_context": list(profile.get("known_kinship", []))[:8],
        "social_context": list(profile.get("known_neighbors", []))[:12],
        "temporal_context": list(profile.get("temporal_evidence", []))[:8],
        "source_works": list(profile.get("source_works", []))[:8],
        "evidence_ids": [candidate.get("profile_evidence_id")] if candidate.get("profile_evidence_id") else [],
    }


def wire_packet(case: Mapping[str, Any]) -> dict[str, Any]:
    public_neighbors = [
        {
            "key": f"p{i}",
            "name": row.get("display_name"),
            "relation": row.get("relation_surface"),
            "relation_class": row.get("relation_class"),
        }
        for i, row in enumerate(case.get("local_neighbors", []))
    ][:12]
    return {
        "task": "grounded identity inference for one historical occurrence",
        "occurrence": {
            "surface": case.get("target_surface"),
            "semantic_type": case.get("occurrence_type"),
            "story_id": case.get("story_id"),
            "story_context": case.get("story_context"),
            "annotation_context": list(case.get("annotation_context", []))[:4],
            "temporal_context": list(case.get("temporal_context", []))[:8],
            "known_participants": public_neighbors,
        },
        "evidence_items": [
            {
                "evidence_id": row.get("evidence_id"),
                "family": row.get("family"),
                "kind": row.get("kind"),
                "source_ref": row.get("source_ref"),
                "text": row.get("text"),
            }
            for row in case.get("evidence_items", [])
        ],
        "candidates": [_candidate_wire(row) for row in case.get("candidates", [])],
    }


def falsification_packet(case: Mapping[str, Any], leading_candidate_key: str | None) -> dict[str, Any]:
    packet = wire_packet(case)
    packet["task"] = "falsification pass for one grounded identity inference"
    packet["falsification_target"] = {"leading_candidate_key": leading_candidate_key}
    return packet


def _object(properties: Mapping[str, Mapping[str, Any]], description: str) -> dict[str, Any]:
    return {
        "type": "object",
        "description": description,
        "properties": {key: dict(value) for key, value in properties.items()},
        "required": list(properties),
        "additionalProperties": False,
    }


def evaluation_tool() -> dict[str, Any]:
    assessment = _object({
        "family": {"type": "string", "enum": sorted(SUPPORT_FAMILIES), "description": "独立证据家族；只能评价 supplied evidence。"},
        "state": {"type": "string", "enum": sorted(EVIDENCE_STATES), "description": "该证据家族对候选的支持状态，不是概率。"},
        "evidence_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 8, "description": "直接支持该状态的 supplied evidence_id；neutral 可以为空。"},
    }, "逐个记录一个证据家族的判断，不写人物 ID。")
    candidate = _object({
        "candidate_key": {"type": "string", "description": "只能复制输入中 supplied 的 c0/c1 等局部候选键。"},
        "family_assessments": {"type": "array", "maxItems": 7, "items": assessment, "description": "对该候选的各独立证据家族逐项评价。"},
        "cross_story_consistency": {"type": "string", "enum": sorted(CROSS_STORY_STATES), "description": "本次指派对候选已有 Story profile 的关系：支持、兼容或矛盾。"},
        "hard_conflict": {"type": "boolean", "description": "只有 supplied evidence 明确形成硬冲突时才为 true。"},
    }, "必须覆盖每个 supplied 候选；不允许创建候选。")
    params = _object({
        "candidate_evaluations": {"type": "array", "maxItems": 8, "items": candidate, "description": "逐个评价所有仍然 plausible 的候选。"},
        "leading_candidate_key": {"type": ["string", "null"], "description": "可复制的最优候选局部键；证据不足时为 JSON null。"},
        "note": {"type": "string", "description": "供审核阅读的简短说明；Python 不把它当作决策依据。"},
    }, "结构化身份证据比较结果；不得输出 Person ID、Relation ID 或 canonical action。")
    return {"type": "function", "function": {"name": EVALUATION_FUNCTION, "description": "基于 supplied historical evidence 比较候选人物；不得创建或输出人物 ID。", "strict": True, "parameters": params}}


def evaluation_tool_choice() -> dict[str, Any]:
    return {"type": "function", "function": {"name": EVALUATION_FUNCTION}}


def falsification_tool() -> dict[str, Any]:
    params = _object({
        "leading_candidate_key": {"type": ["string", "null"], "description": "必须复制 supplied 的 leading candidate key；若无 lead 使用 JSON null。"},
        "contradiction_evidence_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 8, "description": "若 leading candidate 被 supplied evidence 反驳，列出证据 ID。"},
        "comparably_plausible_candidate_keys": {"type": "array", "items": {"type": "string"}, "maxItems": 8, "description": "仍有相近解释力的 supplied candidate keys。"},
        "outcome": {"type": "string", "enum": sorted(FALSIFICATION_OUTCOMES), "description": "leading candidate 经过反证检查后的状态。"},
        "note": {"type": "string", "description": "供审核阅读；Python 不从 note 读取历史事实。"},
    }, "假定 leading candidate 错误，检查 supplied evidence 中的反证或同等候选；不得使用外部知识。")
    return {"type": "function", "function": {"name": FALSIFICATION_FUNCTION, "description": "独立反证检查 supplied identity candidate；不得创建人物 ID。", "strict": True, "parameters": params}}


def falsification_tool_choice() -> dict[str, Any]:
    return {"type": "function", "function": {"name": FALSIFICATION_FUNCTION}}


EVALUATION_SYSTEM = """只根据 supplied occurrence、candidate dossiers 和 evidence_items 评价本次具体历史 occurrence。分别检查 Story-local、时代/年代、参与者、官职称号、人物关系网络、候选已有 Stories 和 source evidence。每个非 neutral 判断必须引用 supplied evidence_id。不要把 LLM 信心当概率，不要使用外部知识，不要输出或猜测 Person ID。"""
FALSIFICATION_SYSTEM = """进行独立 falsification pass：假定 supplied leading candidate 是错误的，只在 supplied evidence_items 中寻找直接矛盾或同样有力的 supplied alternative。不要把假设写成事实，不要使用外部知识；没有充分证据就返回 inconclusive。所有反证必须引用 supplied evidence_id。"""


def _walk_for_forbidden_ids(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) in HARD_FORBIDDEN_KEYS:
                found.append(f"{path}.{key}" if path else str(key))
            found.extend(_walk_for_forbidden_ids(child, f"{path}.{key}" if path else str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_walk_for_forbidden_ids(child, f"{path}[{index}]"))
    return found


def validate_evaluation(payload: Any, case: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    forbidden = _walk_for_forbidden_ids(payload)
    if forbidden:
        errors.extend(f"forbidden_id_field:{x}" for x in forbidden)
    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": ["payload_not_object", *errors]}
    expected = {"candidate_evaluations", "leading_candidate_key", "note"}
    errors.extend(f"unknown_field:{key}" for key in sorted(set(payload) - expected))
    rows = payload.get("candidate_evaluations")
    if not isinstance(rows, list):
        errors.append("candidate_evaluations_not_array")
        rows = []
    allowed = {str(x) for x in case.get("candidate_keys", [])}
    evidence = {str(x.get("evidence_id")) for x in case.get("evidence_items", [])}
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            errors.append(f"candidate_evaluation_not_object:{index}")
            continue
        key = str(row.get("candidate_key") or "")
        if key not in allowed:
            errors.append(f"candidate_key_invalid:{key}")
        if key in seen:
            errors.append(f"candidate_key_duplicate:{key}")
        seen.add(key)
        families = row.get("family_assessments")
        if not isinstance(families, list):
            errors.append(f"family_assessments_not_array:{key}")
            families = []
        for family_row in families:
            if not isinstance(family_row, Mapping):
                errors.append(f"family_assessment_not_object:{key}")
                continue
            family = str(family_row.get("family") or "")
            state = str(family_row.get("state") or "")
            ids = family_row.get("evidence_ids")
            if family not in SUPPORT_FAMILIES:
                errors.append(f"support_family_invalid:{family}")
            if state not in EVIDENCE_STATES:
                errors.append(f"evidence_state_invalid:{state}")
            if not isinstance(ids, list):
                errors.append(f"evidence_ids_not_array:{key}")
                ids = []
            for evidence_id in ids:
                if str(evidence_id) not in evidence:
                    errors.append(f"evidence_reference_invalid:{evidence_id}")
            if state != "neutral" and not ids:
                errors.append(f"non_neutral_without_evidence:{key}:{family}")
        if bool(row.get("hard_conflict")) and not any(
            isinstance(family_row, Mapping)
            and str(family_row.get("state")) in {"contradiction", "strong_contradiction"}
            and family_row.get("evidence_ids")
            for family_row in families
        ):
            errors.append(f"hard_conflict_without_grounded_contradiction:{key}")
        if not isinstance(row.get("hard_conflict"), bool):
            errors.append(f"hard_conflict_not_boolean:{key}")
        if str(row.get("cross_story_consistency") or "") not in CROSS_STORY_STATES:
            errors.append(f"cross_story_consistency_invalid:{key}")
    if seen != allowed:
        errors.append("candidate_evaluations_must_cover_all_candidates")
    leading = payload.get("leading_candidate_key")
    if leading is not None and str(leading) not in allowed:
        errors.append("leading_candidate_key_invalid")
    return {"valid": not errors, "errors": sorted(set(errors)), "payload": dict(payload)}


def validate_falsification(payload: Any, case: Mapping[str, Any], leading_candidate_key: str | None) -> dict[str, Any]:
    errors: list[str] = []
    errors.extend(f"forbidden_id_field:{x}" for x in _walk_for_forbidden_ids(payload))
    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": ["payload_not_object", *errors]}
    expected = {"leading_candidate_key", "contradiction_evidence_ids", "comparably_plausible_candidate_keys", "outcome", "note"}
    errors.extend(f"unknown_field:{key}" for key in sorted(set(payload) - expected))
    allowed = {str(x) for x in case.get("candidate_keys", [])}
    evidence = {str(x.get("evidence_id")) for x in case.get("evidence_items", [])}
    returned_lead = payload.get("leading_candidate_key")
    if returned_lead != leading_candidate_key:
        errors.append("falsification_leading_candidate_mismatch")
    for key in payload.get("comparably_plausible_candidate_keys", []) if isinstance(payload.get("comparably_plausible_candidate_keys"), list) else []:
        if str(key) not in allowed:
            errors.append(f"alternative_candidate_key_invalid:{key}")
    contradiction_ids = payload.get("contradiction_evidence_ids")
    if not isinstance(contradiction_ids, list):
        errors.append("contradiction_evidence_ids_not_array")
        contradiction_ids = []
    for evidence_id in contradiction_ids:
        if str(evidence_id) not in evidence:
            errors.append(f"falsification_evidence_reference_invalid:{evidence_id}")
    outcome = str(payload.get("outcome") or "")
    if outcome not in FALSIFICATION_OUTCOMES:
        errors.append("falsification_outcome_invalid")
    if outcome == "falsified" and not contradiction_ids:
        errors.append("falsified_without_evidence")
    return {"valid": not errors, "errors": sorted(set(errors)), "payload": dict(payload)}


def _family_rows(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(x) for x in row.get("family_assessments", []) if isinstance(x, Mapping)]


def score_evaluations(case: Mapping[str, Any], evaluation: Mapping[str, Any], falsification: Mapping[str, Any] | None) -> dict[str, Any]:
    by_key = {str(row.get("candidate_key")): row for row in evaluation.get("candidate_evaluations", []) if isinstance(row, Mapping)}
    falsification = falsification or {}
    falsified = str(falsification.get("outcome") or "") == "falsified"
    contradiction_ids = list(falsification.get("contradiction_evidence_ids", []) or [])
    ranked: list[dict[str, Any]] = []
    for candidate in case.get("candidates", []):
        key = str(candidate.get("candidate_key"))
        row = by_key.get(key, {})
        supporting: list[dict[str, Any]] = []
        contradicting: list[dict[str, Any]] = []
        score = 0
        support_families: set[str] = set()
        for family_row in _family_rows(row):
            family = str(family_row.get("family") or "")
            state = str(family_row.get("state") or "neutral")
            ids = [str(x) for x in family_row.get("evidence_ids", [])]
            weighted = STATE_SCORE.get(state, 0) * FAMILY_WEIGHT.get(family, 1)
            score += weighted
            entry = {"family": family, "state": state, "evidence_ids": ids, "weighted_score": weighted}
            if state in {"strong_support", "support"}:
                supporting.append(entry)
                support_families.add(family)
            elif state in {"contradiction", "strong_contradiction"}:
                contradicting.append(entry)
        cross_story = str(row.get("cross_story_consistency") or "compatible")
        if cross_story == "supports_profile":
            score += 2
        elif cross_story == "contradiction":
            score -= 2
        grounded_strong_contradiction = any(
            str(entry.get("state") or "") == "strong_contradiction"
            and bool(entry.get("evidence_ids"))
            for entry in _family_rows(row)
        )
        hard_conflict = bool(row.get("hard_conflict")) or grounded_strong_contradiction or (
            falsified
            and key == str(falsification.get("leading_candidate_key"))
            and bool(contradiction_ids)
        )
        if hard_conflict:
            score = -10_000
        ranked.append({
            "candidate_key": key,
            "candidate": candidate.get("display_name"),
            "candidate_person_id": candidate.get("person_id"),
            "identity_score": score,
            "supporting_evidence": supporting,
            "contradicting_evidence": contradicting,
            "cross_story_consistency": cross_story,
            "hard_conflict": hard_conflict,
            "support_family_count": len(support_families),
        })
    ranked.sort(key=lambda row: (-int(row.get("identity_score") or 0), str(row.get("candidate_key"))))
    viable = [row for row in ranked if not row.get("hard_conflict")]
    lead = viable[0] if viable else None
    second_score = int(viable[1].get("identity_score")) if len(viable) > 1 else None
    margin = int(lead.get("identity_score")) - second_score if lead is not None and second_score is not None else (int(lead.get("identity_score")) if lead is not None else None)
    support_count = int(lead.get("support_family_count") or 0) if lead else 0
    has_strong_support = bool(lead and any(row.get("state") == "strong_support" for row in lead.get("supporting_evidence", [])))
    alternatives = {str(x) for x in falsification.get("comparably_plausible_candidate_keys", []) or []}
    high = bool(
        lead
        and int(lead.get("identity_score") or 0) >= MIN_HIGH_SCORE
        and (margin is None or margin >= MIN_HIGH_MARGIN)
        and support_count >= MIN_HIGH_SUPPORT_FAMILIES
        and has_strong_support
        and not alternatives.intersection({str(lead.get("candidate_key"))})
        and str(falsification.get("outcome") or "inconclusive") != "falsified"
        and lead.get("cross_story_consistency") != "contradiction"
    )
    if high:
        result_state = "high_confidence_contextual"
    elif not viable or not lead or int(lead.get("identity_score") or 0) <= 0:
        result_state = "genuinely_unresolved"
    else:
        result_state = "review_required"
    true_ambiguity = bool(result_state == "review_required" and (second_score is None or margin is None or margin < MIN_HIGH_MARGIN or alternatives))
    return {
        "occurrence_id": case.get("occurrence_id"),
        "story_id": case.get("story_id"),
        "surface": case.get("target_surface"),
        "ranked_candidates": ranked,
        "leading_candidate_key": lead.get("candidate_key") if lead else None,
        "identity_score_policy": {
            "state_scores": STATE_SCORE,
            "family_weights": FAMILY_WEIGHT,
            "note": "identity_score is an experimental deterministic support index, not a probability",
        },
        "result_state": result_state,
        "score_margin": margin,
        "true_ambiguity": true_ambiguity,
        "hard_conflicts_found": sum(bool(row.get("hard_conflict")) for row in ranked),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def aggregate_metrics(cases: Sequence[Mapping[str, Any]], scored: Sequence[Mapping[str, Any]], *, total_review_count: int, call_records: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    states = collections.Counter(str(row.get("result_state")) for row in scored)
    high = states.get("high_confidence_contextual", 0)
    new_review = len(scored) - high
    types = collections.Counter(str(case.get("current_review_type")) for case in cases)
    latencies = [float(row.get("elapsed_seconds") or 0) for row in call_records if row.get("elapsed_seconds") is not None]
    return {
        "schema": "hdb2-lj0-metrics-v1",
        "current_review_count": total_review_count,
        "experiment_item_count": len(cases),
        "experiment_baseline_review_count": len(cases),
        "new_review_count": new_review,
        "pilot_net_review_reduction": high,
        "high_confidence_resolutions": high,
        "true_ambiguities": sum(bool(row.get("true_ambiguity")) for row in scored),
        "hard_conflicts_found": sum(int(row.get("hard_conflicts_found") or 0) for row in scored),
        "result_states": dict(sorted(states.items())),
        "review_types": dict(sorted(types.items())),
        "calls": len(call_records),
        "contextual_calls": sum(str(x.get("call_type")) == "evaluation" for x in call_records),
        "falsification_calls": sum(str(x.get("call_type")) == "falsification" for x in call_records),
        "prompt_tokens": sum(int((x.get("usage") or {}).get("prompt_tokens") or 0) for x in call_records),
        "completion_tokens": sum(int((x.get("usage") or {}).get("completion_tokens") or 0) for x in call_records),
        "total_tokens": sum(int((x.get("usage") or {}).get("total_tokens") or 0) for x in call_records),
        "median_latency_seconds": statistics.median(latencies) if latencies else None,
        "max_latency_seconds": max(latencies) if latencies else None,
        "candidate_only": True,
        "canonical_write_back": False,
    }
