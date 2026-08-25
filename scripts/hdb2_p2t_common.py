#!/usr/bin/env python3
"""Shared offline/live helpers for HDB2-P2T.

P2T is an integration projection over the frozen HDB2-P1.1 occurrence
pipeline.  It deliberately keeps the P1.1 wire card and Python validator
unchanged; this module adds only deterministic selection, cascade bookkeeping,
and candidate-only post-processing.
"""

from __future__ import annotations

import collections
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_hng0_2 as hng02  # noqa: E402
import historical_entity_resolver as resolver  # noqa: E402
import hdb2_occurrence_common as occ  # noqa: E402


ANNOTATION = ROOT / "data/annotation"
DERIVED = ROOT / "data/derived"
GENERATED = ROOT / "data/generated/hdb2-p2t"
MODEL = occ.MODEL
RUN_VERSION = "hdb2-p2t-v1"
PROMPT_VERSION = occ.PROMPT_VERSION
SCHEMA = "hdb2-p2t-occurrence-cases-v1"

FINAL_STATUSES = {
    "explicit_resolved",
    "contextually_resolved",
    "contextually_preferred",
    "compositional_reference",
    "ruler_reference",
    "office_reference",
    "not_person",
    "unresolved",
    "conflict",
}
CATEGORY_QUOTAS = {
    "abbreviated_name": 8,
    "title_office": 7,
    "ruler_reference": 5,
    "compositional_kinship": 7,
    "ambiguous_single_character": 8,
    "ordinary_unresolved": 5,
}
OFFICE_MARKERS = ("辟", "拜", "除", "召", "任", "為", "爲", "尹", "刺史", "太守", "將軍", "尚書", "司空", "僕射")
KINSHIP_MARKERS = ("父", "母", "子", "女", "兄", "弟", "妻", "婿", "兒", "婚", "嫁")


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def matching(value: Any) -> str:
    return resolver.matching_normalize(str(value or ""))


def protected_input_hashes() -> dict[str, str]:
    relative = [
        "data/people.json",
        "data/relations.json",
        "data/personStory.json",
        "data/annotation/story-temporal-anchors-h0a.json",
        "data/annotation/story-temporal-evidence-h0a.json",
        "data/annotation/kinship-h0b1.json",
        "data/annotation/marriages-h0b1.json",
        "data/annotation/office-tenures-h0b1.json",
        "data/derived/hdb1-cross-wave-candidate-historical-db.json",
        "data/derived/hdb2-constraint-results.json",
        "data/annotation/hdb2-p1-1-occurrence-selection.json",
        "data/derived/hdb2-p1-1-occurrence-cases.json",
        "data/generated/hdb2-p1-1/live/20260825T-HDB2-P1-1-01/model-decisions.json",
        "data/generated/hdb2-p1/live/20260825T-HDB2-P1-03/case-results.json",
    ]
    result: dict[str, str] = {}
    for item in relative:
        path = ROOT / item
        if path.is_file():
            result[item] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _hdb1_inputs() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    aggregate = read_json(DERIVED / "hdb1-cross-wave-candidate-historical-db.json", {}) or {}
    return (
        aggregate,
        [dict(x) for x in aggregate.get("identity_observations", [])],
        [dict(x) for x in aggregate.get("relation_observations", [])],
        [dict(x) for x in aggregate.get("candidate_identity_registry", [])],
    )


def _p11_exclusion() -> tuple[set[str], set[tuple[str, str, str, str]]]:
    selection = read_json(ANNOTATION / "hdb2-p1-1-occurrence-selection.json", {}) or {}
    used_ids = {str(x.get("identity_observation_id")) for x in selection.get("cases", []) if x.get("identity_observation_id")}
    used_coordinates = {
        (str(x.get("story_id")), matching(x.get("target_surface")), str(x.get("source_ref")), str(x.get("exact_span")))
        for x in selection.get("cases", [])
    }
    return used_ids, used_coordinates


def _candidate_relations(observation_id: str, relations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    token = f"unresolved:{observation_id}"
    return sorted(
        [dict(x) for x in relations if str(x.get("subject_ref")) == token or str(x.get("object_ref")) == token],
        key=lambda x: str(x.get("candidate_id")),
    )


def occurrence_category(row: Mapping[str, Any]) -> str:
    surface = str(row.get("surface") or "")
    kind = occ.classify_occurrence(surface, row)
    if kind == "kinship_compositional_reference":
        return "compositional_kinship"
    if kind == "ruler_reference":
        return "ruler_reference"
    if kind in {"title_reference", "office_reference"}:
        return "title_office"
    if kind == "abbreviated_person_name" and len(matching(surface)) > 1:
        return "abbreviated_name"
    if len(matching(surface)) <= 1:
        return "ambiguous_single_character"
    return "ordinary_unresolved"


def _score_row(row: Mapping[str, Any], relations: Sequence[Mapping[str, Any]], temporal_by_story: Mapping[str, Sequence[Mapping[str, Any]]], story_text_by_id: Mapping[str, str]) -> dict[str, Any]:
    observation_id = str(row.get("identity_observation_id"))
    related = _candidate_relations(observation_id, relations)
    blocked_relation = len(related)
    blocked_kinship = sum(str(x.get("relation_class")) == "kinship" for x in related)
    blocked_marriage = sum(str(x.get("relation_class")) == "marriage" for x in related)
    neighbors = {
        str(x.get("subject_person_id"))
        for x in related
        if x.get("subject_person_id")
    } | {
        str(x.get("object_person_id"))
        for x in related
        if x.get("object_person_id")
    }
    text = story_text_by_id.get(str(row.get("story_id")), "")
    office_hint = bool(any(marker in (str(row.get("exact_span")) + text) for marker in OFFICE_MARKERS))
    temporal_available = bool(temporal_by_story.get(str(row.get("story_id"))))
    score = 5 * blocked_marriage + 4 * blocked_kinship + 2 * blocked_relation + 2 * len(neighbors) + int(temporal_available) + int(office_hint)
    return {
        "priority_score": score,
        "blocked_relation_count": blocked_relation,
        "blocked_kinship_count": blocked_kinship,
        "blocked_marriage_count": blocked_marriage,
        "resolved_neighbor_count": len(neighbors),
        "temporal_constraint_available": temporal_available,
        "office_hint_available": office_hint,
    }


def _story_texts(units: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in units:
        if row.get("source_work") == "世說新語" and row.get("source_layer") == "main_text":
            result[str(row.get("story_id"))] = str(row.get("evidence_text") or "")
    return result


def _legacy_normalized_story_text(story_id: str) -> tuple[str, str] | None:
    """Return an already-registered local normalized search witness.

    This is a provenance boundary repair, not fuzzy quote repair.  The
    original HDB1 exact span remains unchanged; the additional evidence item
    explicitly records that its model-visible text comes from the repository's
    normalized local search witness.
    """
    corpus = read_json(DERIVED / "ds2-1a-shishuo-search-corpus.json", {}) or {}
    for row in corpus.get("records", []):
        if str(row.get("story_id")) == story_id:
            text = str(row.get("search_text_normalized") or "")
            ref = f"hdb2-p2t-legacy-local-{story_id}-{stable_hash(text)[:16]}"
            return ref, text
    return None


def _ensure_occurrence_grounding(case: dict[str, Any]) -> None:
    span = str(case.get("exact_span") or "")
    if not span or any(span in str(item.get("text") or "") for item in case.get("evidence_items", [])):
        return
    witness = _legacy_normalized_story_text(str(case.get("story_id")))
    if not witness or span not in witness[1]:
        case["context_grounding_rejection"] = "exact_span_not_in_registered_evidence_text"
        return
    ref, text = witness
    case.setdefault("evidence_items", []).append({
        "evidence_id": f"ev-{stable_hash({'ref': ref, 'text': text})[:20]}",
        "source_ref": ref,
        "source_work": "世說正文",
        "source_layer": "legacy_local_normalized",
        "source_form": "legacy_local_normalized",
        "text": text,
        "locator": {"story_id": case.get("story_id"), "registered_corpus": "data/derived/ds2-1a-shishuo-search-corpus.json"},
    })


def _temporal_by_story() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    anchors = read_json(ANNOTATION / "story-temporal-anchors-h0a.json", {}) or {}
    evidence = read_json(ANNOTATION / "story-temporal-evidence-h0a.json", {}) or {}
    for row in anchors.get("records", []):
        if row.get("story_id"):
            result[str(row["story_id"])].append(dict(row))
    for row in evidence.get("records", []):
        if row.get("story_id"):
            result[str(row["story_id"])].append(dict(row))
    return dict(result)


def _pool_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    aggregate, identity, relations, _registry = _hdb1_inputs()
    used_ids, used_coordinates = _p11_exclusion()
    units = occ._source_units()
    story_text = _story_texts(units)
    temporal = _temporal_by_story()
    dedup: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in identity:
        status = str(row.get("identity_status") or row.get("person_resolution") or "")
        if status not in {"unresolved", "ambiguous"}:
            continue
        coordinate = (str(row.get("story_id")), matching(row.get("surface")), str(row.get("evidence_ref")), str(row.get("exact_span")))
        if str(row.get("identity_observation_id")) in used_ids or coordinate in used_coordinates:
            continue
        if not str(row.get("surface") or "").strip() or not str(row.get("exact_span") or "").strip():
            continue
        metrics = _score_row(row, relations, temporal, story_text)
        category = occurrence_category(row)
        candidate = {**dict(row), **metrics, "selection_category": category}
        dedup.setdefault(coordinate, candidate)
    rows = list(dedup.values())
    provenance = {
        "hdb1_aggregate_hash": stable_hash(aggregate),
        "p1_1_selection_hash": stable_hash(read_json(ANNOTATION / "hdb2-p1-1-occurrence-selection.json", {}) or {}),
        "p1_1_excluded_identity_ids": sorted(used_ids),
        "p1_1_excluded_coordinate_count": len(used_coordinates),
        "pool_count": len(rows),
    }
    return rows, provenance


def select_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, provenance = _pool_rows()
    by_category: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        by_category[str(row["selection_category"])].append(row)
    selected: list[dict[str, Any]] = []
    selected_coords: set[tuple[str, str, str, str]] = set()
    for category, quota in CATEGORY_QUOTAS.items():
        candidates = sorted(
            by_category.get(category, []),
            key=lambda row: (-int(row.get("priority_score", 0)), stable_hash({"category": category, "identity_observation_id": row.get("identity_observation_id")})),
        )
        for row in candidates[:quota]:
            coordinate = (str(row.get("story_id")), matching(row.get("surface")), str(row.get("evidence_ref")), str(row.get("exact_span")))
            if coordinate in selected_coords:
                continue
            selected.append(row)
            selected_coords.add(coordinate)
    remaining = sorted(
        [row for row in rows if (str(row.get("story_id")), matching(row.get("surface")), str(row.get("evidence_ref")), str(row.get("exact_span"))) not in selected_coords],
        key=lambda row: (-int(row.get("priority_score", 0)), stable_hash({"identity_observation_id": row.get("identity_observation_id")})),
    )
    for row in remaining:
        if len(selected) >= 40:
            break
        coordinate = (str(row.get("story_id")), matching(row.get("surface")), str(row.get("evidence_ref")), str(row.get("exact_span")))
        if coordinate not in selected_coords:
            selected.append(row)
            selected_coords.add(coordinate)
    if len(selected) != 40:
        raise RuntimeError(f"p2t_selection_count:{len(selected)}:pool={len(rows)}")
    selected.sort(key=lambda row: stable_hash({"identity_observation_id": row.get("identity_observation_id"), "story": row.get("story_id")}))
    return selected, provenance


def _p1_maps() -> tuple[dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    _p1_cases, solved_by_id, by_story_surface = occ._p1_rows()
    solved = {(story, surface): solved_by_id.get(str(row.get("case_id")), {}) for (story, surface), row in by_story_surface.items()}
    return by_story_surface, solved


def _p11_contextual_support() -> list[dict[str, Any]]:
    case_doc = read_json(DERIVED / "hdb2-p1-1-occurrence-cases.json", {}) or {}
    run_dir = GENERATED.parent / "hdb2-p1-1" / "live" / "20260825T-HDB2-P1-1-01"
    # The path above is intentionally resolved from data/generated; keep a
    # fallback for callers that use a custom local run directory.
    if not run_dir.is_dir():
        run_dirs = sorted((ROOT / "data/generated/hdb2-p1-1/live").glob("*"))
        run_dir = run_dirs[-1] if run_dirs else run_dir
    results = read_json(run_dir / "python-decisions.json", {}) or {}
    result_by_occurrence = {str(x.get("occurrence_id")): x for x in results.get("records", [])}
    output: list[dict[str, Any]] = []
    for case in case_doc.get("cases", []):
        result = result_by_occurrence.get(str(case.get("occurrence_id")), {})
        pid = str(result.get("resolved_person_id") or "")
        if not pid or result.get("status") not in {"explicit_resolved", "contextually_resolved"}:
            continue
        output.append({"story_id": case.get("story_id"), "source_ref": case.get("source_ref"), "person_id": pid, "evidence_items": case.get("evidence_items", []), "surface": case.get("target_surface")})
    return output


def _add_p11_support(case: dict[str, Any], support_rows: Sequence[Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]], identity: Sequence[Mapping[str, Any]], relations: Sequence[Mapping[str, Any]]) -> None:
    existing_by_pid = {str(row.get("person_id")): row for row in case.get("candidates", []) if row.get("person_id")}
    local_support = [row for row in support_rows if str(row.get("story_id")) == str(case.get("story_id"))]
    for support in local_support:
        pid = str(support.get("person_id") or "")
        if pid not in catalog:
            continue
        evidence_ids = {str(item.get("evidence_id")) for item in case.get("evidence_items", [])}
        support_refs = {str(item.get("source_ref")) for item in support.get("evidence_items", [])}
        support_ids = [str(item.get("evidence_id")) for item in case.get("evidence_items", []) if str(item.get("source_ref")) in support_refs and str(item.get("evidence_id")) in evidence_ids]
        if pid in existing_by_pid:
            existing_by_pid[pid].setdefault("support_evidence_ids", []).extend(support_ids)
            existing_by_pid[pid]["support_evidence_ids"] = sorted(set(existing_by_pid[pid]["support_evidence_ids"]))
            continue
        person = catalog[pid]
        case.setdefault("candidates", []).append({
            "display_name": person.get("canonical_name"),
            "person_id": pid,
            "aliases": [person.get("canonical_name"), *(person.get("forms") or [])],
            "source": "hdb2_p1_1_contextual_support",
            "semantic_type": "person",
            "support_evidence_ids": sorted(set(support_ids)),
            "known_activity_context": [],
        })
    rows = sorted(case.get("candidates", []), key=lambda row: (str(row.get("source")), matching(row.get("display_name")), str(row.get("person_id") or "")))
    dedup: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (str(row.get("person_id") or ""), matching(row.get("display_name")))
        if key in seen:
            continue
        seen.add(key)
        dedup.append(row)
    case["candidates"] = dedup
    for index, row in enumerate(case["candidates"]):
        row["candidate_key"] = f"c{index}"
    case["candidate_keys"] = [row["candidate_key"] for row in case["candidates"]]
    case["candidate_dossiers"] = [occ._candidate_dossier(row, catalog, identity, relations, case.get("evidence_items", [])) for row in case["candidates"]]
    for dossier, row in zip(case["candidate_dossiers"], case["candidates"]):
        dossier["candidate_key"] = row["candidate_key"]
        dossier["supporting_evidence"] = [x for x in dossier.get("supporting_evidence", []) if x in {item.get("evidence_id") for item in case.get("evidence_items", [])}]


def build_cases() -> dict[str, Any]:
    rows, provenance = select_rows()
    _aggregate, identity, relations, _registry = _hdb1_inputs()
    catalog = hng02.person_catalog()
    index = resolver.forms_index(catalog)
    units = occ._source_units()
    p1_by_story_surface, p1_solved = _p1_maps()
    support_rows = _p11_contextual_support()
    cases: list[dict[str, Any]] = []
    for row in rows:
        case = occ._context_case(row, units, catalog, index, identity, relations, p1_by_story_surface, p1_solved)
        _add_p11_support(case, support_rows, catalog, identity, relations)
        _ensure_occurrence_grounding(case)
        case.update({
            "selection_category": row.get("selection_category"),
            "priority_score": row.get("priority_score"),
            "blocked_relation_count": row.get("blocked_relation_count"),
            "blocked_kinship_count": row.get("blocked_kinship_count"),
            "blocked_marriage_count": row.get("blocked_marriage_count"),
            "cascade": None,
            "candidate_only": True,
            "canonical_write_back": False,
        })
        cases.append(case)
    return {
        "schema": SCHEMA,
        "run_version": RUN_VERSION,
        "algorithm_version": "HNG2-C.3/HDB2-P1.1-occurrence-cascade-v1",
        "model": MODEL,
        "temperature": 0,
        "source_inputs": provenance,
        "occurrence_count": len(cases),
        "cases": cases,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def build_selection(cases_doc: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    for case in cases_doc.get("cases", []):
        rows.append({
            "occurrence_id": case.get("occurrence_id"),
            "identity_observation_id": case.get("identity_observation_id"),
            "story_id": case.get("story_id"),
            "surface": case.get("target_surface"),
            "exact_span": case.get("exact_span"),
            "source_ref": case.get("source_ref"),
            "source_section": case.get("source_section"),
            "selection_category": case.get("selection_category"),
            "priority_score": case.get("priority_score"),
            "candidate_keys": case.get("candidate_keys", []),
            "selection_key": stable_hash({"occurrence_id": case.get("occurrence_id"), "story_id": case.get("story_id"), "source_ref": case.get("source_ref"), "exact_span": case.get("exact_span")}),
        })
    excluded_ids, excluded_coords = _p11_exclusion()
    result = {
        "schema": "hdb2-p2t-occurrence-selection-v1",
        "run_version": RUN_VERSION,
        "algorithm_version": "HNG2-C.3/HDB2-P1.1-occurrence-cascade-v1",
        "frozen_before_live": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "occurrence_count": len(rows),
        "p1_1_excluded_occurrence_ids": sorted(excluded_ids),
        "p1_1_excluded_coordinate_hash": stable_hash(sorted(excluded_coords)),
        "cases": sorted(rows, key=lambda row: str(row.get("selection_key"))),
        "selection_hash": None,
    }
    result["selection_hash"] = stable_hash({key: value for key, value in result.items() if key != "selection_hash"})
    return result


def freeze_selection(path: Path, cases_doc: Mapping[str, Any]) -> dict[str, Any]:
    proposed = build_selection(cases_doc)
    if path.is_file():
        existing = read_json(path, {}) or {}
        if existing != proposed:
            raise RuntimeError("hdb2_p2t_frozen_selection_changed")
        return existing
    write_json(path, proposed)
    return proposed


def _visible_text(case: Mapping[str, Any]) -> str:
    return matching("\n".join([str(case.get("local_story_context") or ""), *[str(x or "") for x in case.get("annotation_context", [])], *[str(x.get("text") or "") for x in case.get("evidence_items", [])]]))


def _explicit_candidate_keys(case: Mapping[str, Any]) -> list[str]:
    text = _visible_text(case)
    occurrence_type = str(case.get("occurrence_type") or "")
    target = matching(case.get("target_surface"))
    found: dict[str, str] = {}
    for candidate in case.get("candidates", []):
        pid = str(candidate.get("person_id") or "")
        if not pid:
            continue
        forms = [candidate.get("display_name"), *(candidate.get("aliases") or [])]
        full_forms = [matching(form) for form in forms if len(matching(form)) >= 2]
        # A full name elsewhere in a sentence is not evidence that a ruler,
        # office, or title surface refers to that person.  Such forms may
        # participate in explicit resolution only when the candidate's own
        # supplied form contains the target title surface.
        if occurrence_type in {"ruler_reference", "office_reference", "title_reference"} and not any(target and target in form for form in full_forms):
            continue
        if any(form in text for form in full_forms):
            found[pid] = str(candidate.get("candidate_key"))
    return sorted(found.values()) if len(found) == 1 else []


def _result(case: Mapping[str, Any], status: str, *, candidate_key: str | None = None, resolved_person_id: str | None = None, stage: str, reason: str, llm_called: bool = False, hard_rejections: Sequence[str] = ()) -> dict[str, Any]:
    return {
        "occurrence_id": case.get("occurrence_id"),
        "identity_observation_id": case.get("identity_observation_id"),
        "story_id": case.get("story_id"),
        "target_surface": case.get("target_surface"),
        "status": status,
        "candidate_key": candidate_key,
        "resolved_person_id": resolved_person_id,
        "cascade_stage": stage,
        "cascade_reason": reason,
        "llm_called": llm_called,
        "support_families": [],
        "hard_constraint_rejections": sorted(set(hard_rejections)),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def deterministic_cascade(case: Mapping[str, Any]) -> dict[str, Any]:
    occurrence_type = str(case.get("occurrence_type") or "unclear")
    candidates = list(case.get("candidates", []))
    if occurrence_type == "kinship_compositional_reference":
        return _result(case, "compositional_reference", stage="python_structural", reason="compositional_kinship")
    if occurrence_type == "generic_or_non_person_reference":
        return _result(case, "not_person", stage="python_structural", reason="generic_or_non_person")
    explicit = _explicit_candidate_keys(case)
    if explicit:
        candidate = next(row for row in candidates if row.get("candidate_key") == explicit[0])
        return _result(case, "explicit_resolved", candidate_key=explicit[0], resolved_person_id=str(candidate.get("person_id") or "") or None, stage="python_explicit", reason="unique_visible_full_name")
    if occurrence_type == "ruler_reference" and len(candidates) == 1:
        return _result(case, "ruler_reference", candidate_key=str(candidates[0].get("candidate_key")), stage="python_structural", reason="unique_ruler_candidate")
    if occurrence_type == "office_reference" and len(candidates) == 1:
        return _result(case, "office_reference", candidate_key=str(candidates[0].get("candidate_key")), resolved_person_id=str(candidates[0].get("person_id") or "") or None, stage="python_structural", reason="unique_office_candidate")
    if occurrence_type == "title_reference" and len(candidates) == 1 and candidates[0].get("person_id"):
        return _result(case, "office_reference", candidate_key=str(candidates[0].get("candidate_key")), resolved_person_id=str(candidates[0].get("person_id")), stage="python_structural", reason="unique_title_candidate")
    if len(candidates) < 2:
        return _result(case, "unresolved", stage="python_structural", reason="insufficient_candidates")
    return {"occurrence_id": case.get("occurrence_id"), "cascade_stage": "llm_contextual", "cascade_reason": "multiple_plausible_candidates", "llm_called": True, "candidate_only": True, "canonical_write_back": False}


def apply_llm_result(case: Mapping[str, Any], payload: Mapping[str, Any], validation: Mapping[str, Any]) -> dict[str, Any]:
    result = occ.python_decision(case, payload, validation)
    hard = list(result.get("hard_constraint_rejections", []))
    if any(code in hard for code in ("explicit_temporal_conflict", "ruler_reference_candidate_type_conflict", "non_person_occurrence_candidate")):
        result["status"] = "conflict"
    result.update({"cascade_stage": "llm_contextual", "cascade_reason": "multiple_plausible_candidates", "llm_called": True, "candidate_only": True, "canonical_write_back": False})
    return result


def initial_cascade_counts(results: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(collections.Counter(str(x.get("cascade_stage")) for x in results))
