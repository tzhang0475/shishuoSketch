#!/usr/bin/env python3
"""Occurrence-level identity disambiguation for HDB2-P1.1.

This module deliberately sits above the frozen HDB1/HDB2-P1 evidence layer.
It splits unresolved identity observations into independent contextual cases,
builds Python-owned candidate dossiers, and exposes only local candidate keys
to the semantic model.  It never retrieves new evidence and never writes
canonical data.
"""

from __future__ import annotations

import collections
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
import hdb2_p1_common as p1  # noqa: E402


ANNOTATION = ROOT / "data/annotation"
DERIVED = ROOT / "data/derived"
GENERATED = ROOT / "data/generated/hdb2-p1-1"
MODEL = "deepseek-v4-flash"
RUN_VERSION = "hdb2-p1-1-v1"
PROMPT_VERSION = "hdb2-p1-1-occurrence-disambiguation-v1"

OCCURRENCE_TYPES = {
    "abbreviated_person_name",
    "courtesy_name_reference",
    "title_reference",
    "ruler_reference",
    "office_reference",
    "kinship_compositional_reference",
    "generic_or_non_person_reference",
    "unclear",
}
DECISIONS = {"candidate", "unresolved", "not_person", "compositional_reference"}
CONFIDENCE = {"high", "medium", "low"}
SUPPORT_TYPES = {
    "explicit_name",
    "temporal_context",
    "social_context",
    "office_context",
    "kinship_context",
    "title_context",
    "ruler_context",
    "annotation_context",
}
AGAINST_TYPES = {"temporal_conflict", "identity_conflict", "kinship_conflict", "office_conflict", "context_mismatch"}
REASON_CODES = {
    "explicit_identity",
    "multi_context_support",
    "single_context_support",
    "insufficient_context",
    "candidate_conflict",
    "compositional_kinship",
    "not_person",
}
PAYLOAD_KEYS = {"decision", "candidate_key", "confidence", "support", "against", "reason_code"}
FORBIDDEN_PROMPT_KEYS = {"person_id", "provisional_person_id", "priority_score", "surface_cluster_decision", "canonical_graph_action"}
KINSHIP_SUFFIXES = ("兒", "子", "女", "兄", "弟", "父", "妻", "婿")
RULER_SURFACES = {"帝", "明帝", "武帝"}
OFFICE_SURFACES = {"司空", "僕射", "車騎", "丹陽尹", "吏部尚書"}
REQUIRED_SURFACES = ("充", "嶠", "王", "帝", "明帝", "武帝", "庾亮兒", "文度兒", "温", "敦", "籍", "戎")
QUOTAS = {"充": 1, "嶠": 4, "王": 3, "帝": 2, "明帝": 2, "武帝": 2, "温": 2, "敦": 3, "庾亮兒": 1, "文度兒": 1, "籍": 2, "戎": 2}


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def matching(value: Any) -> str:
    return resolver.matching_normalize(str(value or ""))


def normalize_surface(value: Any) -> str:
    return matching(value)


def _hdb1() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    aggregate = read_json(DERIVED / "hdb1-cross-wave-candidate-historical-db.json", {}) or {}
    return aggregate, list(aggregate.get("identity_observations", [])), list(aggregate.get("relation_observations", [])), list(aggregate.get("candidate_identity_registry", []))


def _p1_rows() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    run = read_json(GENERATED / "live/20260825T-HDB2-P1-03/case-results.json", {}) or {}
    cases = list(run.get("cases", []))
    solved = read_json(DERIVED / "hdb2-constraint-results.json", {}) or {}
    solved_by = {str(row.get("case_id")): row for row in solved.get("cases", [])}
    by_story_surface: dict[tuple[str, str], dict[str, Any]] = {}
    for row in solved.get("cases", []):
        surfaces = row.get("case", {}).get("target_surfaces", [])
        stories = row.get("case", {}).get("story_ids", [])
        for story_id in stories:
            for surface in surfaces:
                by_story_surface[(str(story_id), matching(surface))] = row
    return cases, solved_by, by_story_surface


def _temporal_context(story_id: str) -> list[dict[str, Any]]:
    anchors = read_json(ANNOTATION / "story-temporal-anchors-h0a.json", {}) or {}
    evidence = read_json(ANNOTATION / "story-temporal-evidence-h0a.json", {}) or {}
    result: list[dict[str, Any]] = []
    for row in anchors.get("records", []):
        if str(row.get("story_id")) != story_id:
            continue
        result.append({
            "precision": row.get("precision"),
            "start_year_ce": row.get("start_year_ce"),
            "end_year_ce": row.get("end_year_ce"),
            "reign_id": row.get("reign_id"),
            "ruler_context_id": row.get("ruler_context_id"),
            "phase_id": row.get("phase_id"),
            "event_ids": list(row.get("event_ids", [])),
            "evidence_ids": list(row.get("evidence_ids", [])),
        })
    for row in evidence.get("records", []):
        if str(row.get("story_id")) != story_id:
            continue
        result.append({
            "evidence_record_id": row.get("evidence_record_id"),
            "evidence_type": row.get("evidence_type"),
            "raw_surface": row.get("raw_surface"),
            "relation_to_story": row.get("relation_to_story"),
            "normalized_candidate": row.get("normalized_candidate"),
        })
    return result


def classify_occurrence(surface: str, row: Mapping[str, Any]) -> str:
    text = str(surface or "")
    if any(text.endswith(suffix) for suffix in KINSHIP_SUFFIXES):
        return "kinship_compositional_reference"
    if text in RULER_SURFACES:
        return "ruler_reference"
    if text in OFFICE_SURFACES:
        return "office_reference"
    reference = str(row.get("reference_form") or "")
    if reference == "courtesy":
        return "courtesy_name_reference"
    if reference in {"title_only", "office_title_only"}:
        return "title_reference" if text not in RULER_SURFACES else "ruler_reference"
    if reference == "abbreviated" or str(row.get("entity_kind")) in {"abbreviated_name", "named_person"}:
        return "abbreviated_person_name"
    if str(row.get("entity_kind")) in {"generic_role", "not_person", "collective_persons"}:
        return "generic_or_non_person_reference"
    return "unclear"


def _source_units() -> list[dict[str, Any]]:
    return p1.build_source_index()


def _story_units(units: Sequence[Mapping[str, Any]], story_id: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    main = next((dict(x) for x in units if x.get("source_work") == "世說新語" and x.get("source_layer") == "main_text" and str(x.get("story_id")) == story_id), None)
    annotations = [dict(x) for x in units if x.get("source_work") == "劉注" and str(x.get("story_id")) == story_id]
    return main, sorted(annotations, key=lambda x: str(x.get("ref")))


def _related_rows(observation_id: str, relations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    token = f"unresolved:{observation_id}"
    return sorted([dict(x) for x in relations if str(x.get("subject_ref")) == token or str(x.get("object_ref")) == token], key=lambda x: str(x.get("candidate_id")))


def _same_story_identity(story_id: str, identity: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(x) for x in identity if str(x.get("story_id")) == story_id]


def _passage_evidence(case_surface: str, story_id: str, main: Mapping[str, Any] | None, annotations: Sequence[Mapping[str, Any]], p1_case: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    def add(ref: str, text: str, work: str, layer: str, kind: str, locator: Mapping[str, Any] | None = None) -> str | None:
        if not ref or not text or any(str(x.get("source_ref")) == ref for x in items):
            return next((str(x.get("evidence_id")) for x in items if str(x.get("source_ref")) == ref), None)
        evidence_id = f"ev-{stable_hash({'ref': ref, 'text': text})[:20]}"
        items.append({"evidence_id": evidence_id, "source_ref": ref, "source_work": work, "source_layer": layer, "text": text, "locator": dict(locator or {})})
        return evidence_id

    if main:
        add(str(main.get("ref")), str(main.get("evidence_text") or ""), "世說正文", "main_text", "story_main", main.get("locator"))
    target = matching(case_surface)
    for ann in annotations:
        text = str(ann.get("evidence_text") or "")
        if target and target not in matching(text):
            continue
        add(str(ann.get("ref")), text, "劉注", "liu_annotation", "liu_annotation", ann.get("locator"))
        if len(items) >= 3:
            break
    if p1_case:
        atoms = list(p1_case.get("validated_atoms", []))
        passages = {str(x.get("ref")): dict(x) for x in p1_case.get("all_passages", [])}
        relevant_refs = {str(a.get("evidence_ref")) for a in atoms if target and target in matching(str(a.get("subject_surface") or "") + str(a.get("object_surface") or ""))}
        for ref in sorted(relevant_refs):
            passage = passages.get(ref)
            if not passage:
                continue
            add(ref, str(passage.get("evidence_text") or ""), str(passage.get("source_work") or ""), str(passage.get("source_layer") or ""), "hdb2_p1_grounded_evidence", passage.get("locator"))
            if len(items) >= 6:
                break
    return items


def _surface_candidates(surface: str, catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]]) -> set[str]:
    norm = matching(surface)
    ids = set(str(x) for x in index.get(norm, []))
    if norm:
        for pid, person in catalog.items():
            forms = [person.get("canonical_name"), *(person.get("forms") or [])]
            if any(matching(form).endswith(norm) for form in forms if form):
                ids.add(str(pid))
    return {pid for pid in ids if pid in catalog}


def _base_surface(surface: str) -> str:
    text = str(surface or "")
    for suffix in KINSHIP_SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix):
            return text[: -len(suffix)]
    return text


def _h0a_ruler_candidates(surface: str, temporal: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if surface not in RULER_SURFACES:
        return []
    coords = read_json(DERIVED / "h0a-temporal-coordinates.json", {}) or {}
    contexts = list(coords.get("ruler_contexts", []))
    anchor_ranges = [(x.get("start_year_ce"), x.get("end_year_ce")) for x in temporal if isinstance(x.get("start_year_ce"), int) and isinstance(x.get("end_year_ce"), int)]
    result: list[dict[str, Any]] = []
    for row in contexts:
        name = str(row.get("ruler_name") or "")
        if "帝" not in name or surface not in name:
            continue
        if anchor_ranges and isinstance(row.get("start_year_ce"), int) and isinstance(row.get("end_year_ce"), int):
            if all(row["end_year_ce"] < start or row["start_year_ce"] > end for start, end in anchor_ranges):
                continue
        result.append({"display_name": name, "person_id": None, "source": "h0a_ruler_registry", "semantic_type": "ruler_title", "known_activity_context": [{"start_year_ce": row.get("start_year_ce"), "end_year_ce": row.get("end_year_ce"), "ruler_context_id": row.get("ruler_context_id")}], "aliases": []})
    return sorted(result, key=lambda x: (str(x.get("display_name")), stable_hash(x)))[:6]


def _p1_support_candidates(surface: str, p1_case: Mapping[str, Any] | None, p1_solved: Mapping[str, Any] | None, evidence_items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if not p1_solved:
        return result
    # HDB2-P1 was a surface-cluster experiment.  Its identity atoms are
    # reusable only when their exact source wording is present in this
    # occurrence's local evidence bundle; otherwise using them would leak a
    # different occurrence into the candidate set.
    local_text = "\n".join(str(x.get("text") or "") for x in evidence_items)

    def local_support(ref: Any, span: Any, person_surface: Any = "") -> bool:
        span_text = str(span or "")
        person_text = str(person_surface or "")
        return bool((span_text and span_text in local_text) or (person_text and person_text in local_text))

    for support in p1_solved.get("decision", {}).get("identity_support", []):
        if not local_support(support.get("evidence_ref"), support.get("exact_span"), support.get("person_surface")):
            continue
        result.append({"person_id": support.get("person_id"), "display_name": support.get("person_surface") or support.get("person_id"), "source": "hdb2_p1_identity_evidence", "support_evidence_ref": support.get("evidence_ref"), "support_exact_span": support.get("exact_span"), "semantic_type": "person"})
    for row in p1_solved.get("decision", {}).get("new_candidate_support", []):
        if not local_support(row.get("evidence_ref"), row.get("exact_span"), row.get("person_surface") or row.get("canonical_candidate_label")):
            continue
        result.append({"person_id": None, "display_name": row.get("person_surface") or row.get("canonical_candidate_label"), "source": "hdb2_p1_new_candidate_evidence", "support_evidence_ref": row.get("evidence_ref"), "support_exact_span": row.get("exact_span"), "semantic_type": "person"})
    for atom in (p1_solved.get("atoms") or []):
        if str(atom.get("atom_kind")) != "identity_name":
            continue
        subject = str(atom.get("subject_surface") or "")
        obj = str(atom.get("object_surface") or "")
        if matching(surface) not in {matching(subject), matching(obj)}:
            continue
        other = obj if matching(surface) == matching(subject) else subject
        if other and other != surface and local_support(atom.get("evidence_ref"), atom.get("exact_span"), other):
            result.append({"person_id": None, "display_name": other, "source": "hdb2_p1_local_identity_evidence", "support_evidence_ref": atom.get("evidence_ref"), "support_exact_span": atom.get("exact_span"), "semantic_type": "person"})
    return result


def _candidate_dossier(row: Mapping[str, Any], catalog: Mapping[str, Mapping[str, Any]], hdb1_identity: Sequence[Mapping[str, Any]], relations: Sequence[Mapping[str, Any]], support_evidence: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    pid = str(row.get("person_id") or "")
    person = catalog.get(pid, {}) if pid else {}
    forms = [str(x) for x in [person.get("canonical_name"), *(person.get("forms") or [])] if x]
    known_neighbors = []
    for rel in relations:
        if pid and (str(rel.get("subject_person_id")) == pid or str(rel.get("object_person_id")) == pid):
            known_neighbors.append({"story_id": rel.get("story_id"), "relation_surface": rel.get("relation_surface"), "relation_class": rel.get("relation_class")})
    activity = []
    anchors = read_json(ANNOTATION / "person-activity-anchors-h0a.json", {}) or {}
    for anchor in anchors.get("records", []):
        if pid and str(anchor.get("person_id")) == pid:
            activity.append({"start_year_ce": anchor.get("start_year_ce"), "end_year_ce": anchor.get("end_year_ce"), "event_id": anchor.get("event_id"), "review_status": anchor.get("review_status")})
    return {
        "candidate_key": row.get("candidate_key"),
        "display_name": row.get("display_name"),
        "aliases": forms,
        "courtesy_names": [x for x in forms if x != person.get("canonical_name")],
        "titles": [x for x in forms if any(t in x for t in ("帝", "公", "太尉", "尚書", "將軍", "司空", "僕射"))],
        "known_activity_context": row.get("known_activity_context") or activity,
        "known_offices": [],
        "known_kinship": [],
        "known_neighbors": known_neighbors[:12],
        "supporting_evidence": [x.get("evidence_id") for x in support_evidence if x.get("evidence_id") in set(row.get("support_evidence_ids", []))],
        "source": row.get("source"),
        "semantic_type": row.get("semantic_type", "person"),
    }


def _context_case(row: Mapping[str, Any], units: Sequence[Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]], identity: Sequence[Mapping[str, Any]], relations: Sequence[Mapping[str, Any]], p1_case_by_surface: Mapping[str, Mapping[str, Any]], p1_solved_by_surface: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    surface = str(row.get("surface") or "")
    story_id = str(row.get("story_id") or "")
    occurrence_id = f"hdb2-occ-{stable_hash({'identity_observation_id': row.get('identity_observation_id'), 'story_id': story_id, 'evidence_ref': row.get('evidence_ref'), 'exact_span': row.get('exact_span')})[:20]}"
    occurrence_type = classify_occurrence(surface, row)
    main, annotations = _story_units(units, story_id)
    p1_case = p1_case_by_surface.get((story_id, matching(surface)))
    p1_solved = p1_solved_by_surface.get((story_id, matching(surface)))
    evidence_items = _passage_evidence(surface, story_id, main, annotations, p1_case)
    related = _related_rows(str(row.get("identity_observation_id")), relations)
    same_story = _same_story_identity(story_id, identity)
    local_neighbors: list[dict[str, Any]] = []
    neighbor_ids: set[str] = set()
    for rel in related:
        for side in ("subject_person_id", "object_person_id"):
            pid = str(rel.get(side) or "")
            if pid and pid in catalog and pid not in neighbor_ids:
                neighbor_ids.add(pid)
                local_neighbors.append({"person_id": pid, "display_name": catalog[pid].get("canonical_name"), "relation_surface": rel.get("relation_surface"), "relation_class": rel.get("relation_class"), "story_id": story_id})
    for obs in same_story:
        pid = str(obs.get("resolved_person_id") or "")
        if pid and pid in catalog and pid not in neighbor_ids:
            neighbor_ids.add(pid)
            local_neighbors.append({"person_id": pid, "display_name": catalog[pid].get("canonical_name"), "relation_surface": "same_story_identity_observation", "relation_class": "context", "story_id": story_id})
    temporal = _temporal_context(story_id)
    candidate_rows: list[dict[str, Any]] = []
    by_identity: dict[tuple[str, str], dict[str, Any]] = {}

    def add_candidate(display_name: str, person_id: str | None, source: str, semantic_type: str = "person", support_ref: str | None = None, support_span: str | None = None, activity: Sequence[Mapping[str, Any]] | None = None) -> None:
        display_name = str(display_name or "").strip()
        if not display_name:
            return
        # Existing-catalogue matching happens before a local candidate is
        # created.  This is especially important for HDB2-P1 evidence that
        # names an existing Person using an occurrence surface or alias.
        if not person_id:
            matched_ids = sorted(_surface_candidates(display_name, catalog, index))
            if len(matched_ids) == 1:
                person_id = matched_ids[0]
        if person_id and person_id in catalog:
            display_name = str(catalog[person_id].get("canonical_name") or display_name)
        key = (str(person_id or ""), "" if person_id else matching(display_name))
        existing = by_identity.get(key)
        if existing:
            if support_ref:
                existing.setdefault("support_evidence_ids", []).extend([x.get("evidence_id") for x in evidence_items if x.get("source_ref") == support_ref])
            return
        forms = []
        if person_id and person_id in catalog:
            person = catalog[person_id]
            forms = [str(x) for x in [person.get("canonical_name"), *(person.get("forms") or [])] if x]
        candidate = {"display_name": display_name, "person_id": person_id, "aliases": forms, "source": source, "semantic_type": semantic_type, "support_evidence_ids": [], "known_activity_context": list(activity or [])}
        if support_ref:
            candidate["support_evidence_ids"] = [x.get("evidence_id") for x in evidence_items if x.get("source_ref") == support_ref]
        by_identity[key] = candidate
        candidate_rows.append(candidate)

    for pid in sorted(_surface_candidates(surface, catalog, index)):
        add_candidate(str(catalog[pid].get("canonical_name") or pid), pid, "catalogue_suffix")
    if occurrence_type == "kinship_compositional_reference":
        base = _base_surface(surface)
        for pid in sorted(_surface_candidates(base, catalog, index)):
            add_candidate(str(catalog[pid].get("canonical_name") or pid), pid, "kinship_base_candidate", "kinship_base")
    for neighbor in local_neighbors:
        pid = str(neighbor.get("person_id"))
        add_candidate(str(neighbor.get("display_name") or pid), pid, "local_story_neighbor")
    for item in _p1_support_candidates(surface, p1_case, p1_solved, evidence_items):
        add_candidate(str(item.get("display_name") or ""), str(item.get("person_id")) if item.get("person_id") else None, str(item.get("source")), str(item.get("semantic_type") or "person"), item.get("support_evidence_ref"), item.get("support_exact_span"))
    for item in _h0a_ruler_candidates(surface, temporal):
        add_candidate(str(item.get("display_name")), None, "h0a_ruler_registry", "ruler_title", activity=item.get("known_activity_context"))
    candidate_rows.sort(key=lambda x: (str(x.get("source")), matching(x.get("display_name")), str(x.get("person_id") or "")))
    for i, candidate in enumerate(candidate_rows):
        candidate["candidate_key"] = f"c{i}"
    evidence_set = {x.get("evidence_id") for x in evidence_items}
    dossiers = [_candidate_dossier(row, catalog, identity, relations, evidence_items) for row in candidate_rows]
    for dossier, row2 in zip(dossiers, candidate_rows):
        dossier["candidate_key"] = row2["candidate_key"]
        dossier["supporting_evidence"] = [x for x in dossier.get("supporting_evidence", []) if x in evidence_set]
    local_relations = [{k: v for k, v in rel.items() if k in {"candidate_id", "relation_class", "relation_surface", "exact_span", "evidence_ref", "semantic_level", "story_id"}} for rel in related]
    office_context = [x for x in local_relations if x.get("relation_class") == "institutional" or any(t in str(x.get("relation_surface") or "") for t in ("拜", "辟", "除", "為", "爲", "召", "任"))]
    kinship_context = [x for x in local_relations if x.get("relation_class") in {"kinship", "marriage"}]
    baseline = dict((p1_solved or {}).get("decision", {}))
    return {
        "occurrence_id": occurrence_id,
        "identity_observation_id": row.get("identity_observation_id"),
        "target_surface": surface,
        "occurrence_type": occurrence_type,
        "story_id": story_id,
        "source_ref": row.get("evidence_ref"),
        "exact_span": row.get("exact_span"),
        "source_section": "main_text" if "main" in str(row.get("evidence_ref")) else "liu_annotation",
        "local_story_context": str(main.get("evidence_text") if main else ""),
        "annotation_context": [x.get("text") for x in annotations if matching(surface) in matching(str(x.get("evidence_text") or ""))][:2],
        "local_neighbors": local_neighbors,
        "local_relations": local_relations,
        "story_temporal_context": temporal,
        "office_context": office_context,
        "kinship_context": kinship_context,
        "candidate_keys": [x.get("candidate_key") for x in candidate_rows],
        "candidates": candidate_rows,
        "candidate_dossiers": dossiers,
        "evidence_items": evidence_items,
        "baseline_surface_decision": baseline,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _select_observations(identity: Sequence[Mapping[str, Any]], selection_cases: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ids = {str(x) for case in selection_cases for x in case.get("observation_ids", [])}
    rows = [dict(x) for x in identity if str(x.get("identity_observation_id")) in ids]
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        grouped[str(row.get("surface") or "")].append(row)
    selected: list[dict[str, Any]] = []
    for surface, quota in QUOTAS.items():
        candidates = grouped.get(surface, [])
        if not candidates and surface == "溫":
            candidates = grouped.get("温", [])
        # Selection uses only frozen HDB1 observation coordinates and stable
        # ordering, never model output or a global surface decision.
        ranked = sorted(candidates, key=lambda x: stable_hash({"surface": surface, "observation_id": x.get("identity_observation_id"), "story": x.get("story_id")}))
        selected.extend(ranked[:quota])
    if len(selected) < 20 or len(selected) > 30:
        raise RuntimeError(f"hdb2_p1_1_selection_out_of_range:{len(selected)}")
    return sorted(selected, key=lambda x: (str(x.get("surface")), str(x.get("story_id")), str(x.get("identity_observation_id"))))


def build_cases() -> dict[str, Any]:
    selection = read_json(ANNOTATION / "hdb2-p1-selection.json", {}) or {}
    aggregate, identity, relations, _registry = _hdb1()
    p1_cases, p1_solved_by, p1_by_surface = _p1_rows()
    catalog = hng02.person_catalog()
    index = resolver.forms_index(catalog)
    units = _source_units()
    selected = _select_observations(identity, selection.get("cases", []))
    cases = []
    for row in selected:
        case = _context_case(row, units, catalog, index, identity, relations, p1_by_surface, {k: p1_solved_by.get(str(v.get("case_id")), {}) for k, v in p1_by_surface.items()})
        cases.append(case)
    source_hashes = {
        "hdb1_aggregate": stable_hash(aggregate),
        "hdb2_p1_selection": stable_hash(selection),
        "hdb2_p1_case_results": stable_hash(p1_cases),
        "hdb2_p1_constraint_results": stable_hash(read_json(DERIVED / "hdb2-constraint-results.json", {}) or {}),
    }
    return {
        "schema": "hdb2-p1-1-occurrence-cases-v1",
        "run_version": RUN_VERSION,
        "algorithm_version": "HNG2-C.3/HDB2-P1-occurrence-context-v1",
        "model": MODEL,
        "temperature": 0,
        "source_inputs": source_hashes,
        "occurrence_count": len(cases),
        "cases": cases,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def build_selection(cases_doc: Mapping[str, Any]) -> dict[str, Any]:
    cases = []
    for case in cases_doc.get("cases", []):
        cases.append({
            "occurrence_id": case.get("occurrence_id"),
            "identity_observation_id": case.get("identity_observation_id"),
            "target_surface": case.get("target_surface"),
            "occurrence_type": case.get("occurrence_type"),
            "story_id": case.get("story_id"),
            "source_ref": case.get("source_ref"),
            "exact_span": case.get("exact_span"),
            "source_section": case.get("source_section"),
            "candidate_keys": case.get("candidate_keys", []),
            "candidate_count": len(case.get("candidate_keys", [])),
            "selection_key": stable_hash({"occurrence_id": case.get("occurrence_id"), "story_id": case.get("story_id"), "surface": case.get("target_surface")}),
        })
    result = {
        "schema": "hdb2-p1-1-occurrence-selection-v1",
        "run_version": RUN_VERSION,
        "algorithm_version": "HNG2-C.3/HDB2-P1-occurrence-context-v1",
        "frozen_before_live": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "source_case_hash": stable_hash(cases_doc),
        "occurrence_count": len(cases),
        "cases": sorted(cases, key=lambda x: str(x.get("selection_key"))),
        "selection_hash": None,
    }
    result["selection_hash"] = stable_hash({k: v for k, v in result.items() if k != "selection_hash"})
    return result


def freeze_selection(path: Path, cases_doc: Mapping[str, Any]) -> dict[str, Any]:
    proposed = build_selection(cases_doc)
    if path.is_file():
        existing = read_json(path, {}) or {}
        if existing != proposed:
            raise RuntimeError("hdb2_p1_1_frozen_selection_changed")
        return existing
    write_json(path, proposed)
    return proposed


def wire_case(case: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task": "occurrence identity disambiguation",
        "occurrence": {
            "surface": case.get("target_surface"),
            "type": case.get("occurrence_type"),
            "story_id": case.get("story_id"),
            "story_text": case.get("local_story_context"),
            "annotation_context": case.get("annotation_context", []),
            "temporal_context": case.get("story_temporal_context", []),
            "known_people_in_context": [{"key": f"p{i}", "name": row.get("display_name"), "relation": row.get("relation_surface")} for i, row in enumerate(case.get("local_neighbors", []))],
        },
        "evidence_items": [{"evidence_id": row.get("evidence_id"), "source_ref": row.get("source_ref"), "source_work": row.get("source_work"), "source_layer": row.get("source_layer"), "text": row.get("text")} for row in case.get("evidence_items", [])],
        "candidates": [
            {
                "candidate_key": dossier.get("candidate_key"),
                "name": dossier.get("display_name"),
                "aliases": dossier.get("aliases", []),
                "courtesy_names": dossier.get("courtesy_names", []),
                "titles": dossier.get("titles", []),
                "activity_context": dossier.get("known_activity_context", []),
                "office_context": dossier.get("known_offices", []),
                "social_context": dossier.get("known_neighbors", []),
                "evidence": dossier.get("supporting_evidence", []),
            }
            for dossier in case.get("candidate_dossiers", [])
        ],
    }


def strict_tool() -> dict[str, Any]:
    support = {
        "type": "object",
        "properties": {
            "support_type": {"type": "string", "enum": sorted(SUPPORT_TYPES), "description": "支持当前 occurrence 候选判断的证据家族。只能引用 supplied evidence。"},
            "evidence_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 6, "description": "直接支持判断的 supplied evidence_id。不得创建新证据编号。"},
        },
        "required": ["support_type", "evidence_ids"],
        "additionalProperties": False,
    }
    against = {
        "type": "object",
        "properties": {
            "candidate_key": {"type": "string", "description": "被反驳的 supplied candidate_key。"},
            "reason_type": {"type": "string", "enum": sorted(AGAINST_TYPES), "description": "原文语境与该候选不合的受控理由。"},
        },
        "required": ["candidate_key", "reason_type"],
        "additionalProperties": False,
    }
    params = {
        "type": "object",
        "properties": {
            "decision": {"type": "string", "enum": sorted(DECISIONS), "description": "对这一个 occurrence 的候选判断；允许 unresolved。"},
            "candidate_key": {"type": ["string", "null"], "description": "只能复制 supplied candidate_key；非 candidate decision 使用 null。"},
            "confidence": {"type": "string", "enum": sorted(CONFIDENCE), "description": "对 supplied text 是否支持该判断的信心，不是 canonical truth。"},
            "support": {"type": "array", "maxItems": 6, "items": support, "description": "只列直接支持当前 occurrence 判断的 evidence family。"},
            "against": {"type": "array", "maxItems": 6, "items": against, "description": "只列 supplied candidate 中被当前上下文反对的候选。"},
            "reason_code": {"type": "string", "enum": sorted(REASON_CODES), "description": "简短受控判断理由。"},
        },
        "required": ["decision", "candidate_key", "confidence", "support", "against", "reason_code"],
        "additionalProperties": False,
    }
    return {"type": "function", "function": {"name": "submit_hdb2_occurrence_identity_decision", "description": "比较系统提供的候选人物并判断当前单一历史 occurrence；不得创建人物 ID。", "strict": True, "parameters": params}}


def tool_choice() -> dict[str, Any]:
    return {"type": "function", "function": {"name": "submit_hdb2_occurrence_identity_decision"}}


SYSTEM_PROMPT = """只根据 supplied occurrence context、evidence_items 和 candidates 判断这一个历史文字 occurrence 的指代。不得使用外部知识补写，不得创建或猜测人物 ID，不得把同表面其他 occurrence 的结论当作本次证据。候选之外只能 unresolved。X兒、X子、X女等结构性亲属表达不是其 base Person；帝/明帝/武帝必须结合本段语境。每个 support 只能引用 supplied evidence_id。"""


def user_prompt(case: Mapping[str, Any]) -> dict[str, Any]:
    return wire_case(case)


def validate_model_payload(payload: Any, case: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": ["payload_not_object"], "payload": payload}
    errors: list[str] = []
    errors.extend(f"unknown_payload_field:{key}" for key in sorted(set(payload) - PAYLOAD_KEYS))
    decision = str(payload.get("decision") or "")
    candidate_key = payload.get("candidate_key")
    if decision not in DECISIONS:
        errors.append("invalid_decision")
    if decision == "candidate" and not isinstance(candidate_key, str):
        errors.append("candidate_key_required")
    if decision != "candidate" and candidate_key not in (None, ""):
        errors.append("candidate_key_must_be_null_outside_candidate")
    if str(payload.get("confidence") or "") not in CONFIDENCE:
        errors.append("invalid_confidence")
    if str(payload.get("reason_code") or "") not in REASON_CODES:
        errors.append("invalid_reason_code")
    allowed = set(case.get("candidate_keys", []))
    if decision == "candidate" and candidate_key not in allowed:
        errors.append("candidate_key_invalid")
    evidence_ids = {str(x.get("evidence_id")) for x in case.get("evidence_items", [])}
    if not isinstance(payload.get("support"), list):
        errors.append("support_not_array")
    if not isinstance(payload.get("against"), list):
        errors.append("against_not_array")
    for support in payload.get("support", []) if isinstance(payload.get("support"), list) else []:
        if not isinstance(support, Mapping):
            errors.append("support_not_object")
            continue
        if str(support.get("support_type") or "") not in SUPPORT_TYPES:
            errors.append("support_type_invalid")
        for evidence_id in support.get("evidence_ids", []) if isinstance(support.get("evidence_ids"), list) else []:
            if str(evidence_id) not in evidence_ids:
                errors.append("evidence_reference_invalid")
    for against in payload.get("against", []) if isinstance(payload.get("against"), list) else []:
        if not isinstance(against, Mapping):
            errors.append("against_not_object")
            continue
        if str(against.get("candidate_key") or "") not in allowed:
            errors.append("against_candidate_key_invalid")
        if str(against.get("reason_type") or "") not in AGAINST_TYPES:
            errors.append("against_reason_invalid")
    return {"valid": not errors, "errors": sorted(set(errors)), "payload": dict(payload)}


def _support_families(payload: Mapping[str, Any]) -> list[str]:
    return sorted({str(x.get("support_type")) for x in payload.get("support", []) if isinstance(x, Mapping) and str(x.get("support_type") or "")})


def _is_base_candidate(case: Mapping[str, Any], candidate: Mapping[str, Any] | None) -> bool:
    if not candidate or case.get("occurrence_type") != "kinship_compositional_reference":
        return False
    base = matching(_base_surface(str(case.get("target_surface") or "")))
    forms = [candidate.get("display_name"), *(candidate.get("aliases") or [])]
    return any(matching(form) == base or matching(form).endswith(base) for form in forms if form)


def _temporal_conflict(case: Mapping[str, Any], candidate: Mapping[str, Any] | None) -> bool:
    if not candidate:
        return False
    ranges = [(x.get("start_year_ce"), x.get("end_year_ce")) for x in case.get("story_temporal_context", []) if isinstance(x.get("start_year_ce"), int) and isinstance(x.get("end_year_ce"), int)]
    activities = candidate.get("known_activity_context", [])
    if not ranges or not activities:
        return False
    for activity in activities:
        start, end = activity.get("start_year_ce"), activity.get("end_year_ce")
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        if any(not (end < lo or start > hi) for lo, hi in ranges):
            return False
    return any(isinstance(x.get("start_year_ce"), int) and isinstance(x.get("end_year_ce"), int) for x in activities)


def python_decision(case: Mapping[str, Any], payload: Mapping[str, Any], validation: Mapping[str, Any]) -> dict[str, Any]:
    candidates = {str(x.get("candidate_key")): x for x in case.get("candidates", [])}
    model_decision = str(payload.get("decision") or "")
    chosen_key = payload.get("candidate_key") if isinstance(payload.get("candidate_key"), str) else None
    chosen = candidates.get(str(chosen_key)) if chosen_key else None
    support_families = _support_families(payload)
    hard_rejections: list[str] = list(validation.get("errors", []))
    if chosen and _is_base_candidate(case, chosen):
        hard_rejections.append("compositional_base_person_rejected")
    if chosen and case.get("occurrence_type") == "ruler_reference" and str(chosen.get("semantic_type") or "person") != "ruler_title":
        hard_rejections.append("ruler_reference_candidate_type_conflict")
    if chosen and case.get("occurrence_type") == "generic_or_non_person_reference":
        hard_rejections.append("non_person_occurrence_candidate")
    if chosen and _temporal_conflict(case, chosen):
        hard_rejections.append("explicit_temporal_conflict")
    if case.get("occurrence_type") == "kinship_compositional_reference":
        base = _base_surface(str(case.get("target_surface") or ""))
        base_key = next((str(x.get("candidate_key")) for x in case.get("candidates", []) if _is_base_candidate(case, x)), None)
        final_status = "compositional_reference"
        final_key = None
        compositional = {"base_candidate_key": base_key, "base_surface": base, "relation": "child_or_kinship_referent", "referent_candidate_key": None}
    elif hard_rejections or model_decision == "unresolved":
        final_status = "unresolved"
        final_key = None
        compositional = None
    elif model_decision == "not_person":
        final_status = "not_person"
        final_key = None
        compositional = None
    elif model_decision == "compositional_reference":
        final_status = "compositional_reference"
        final_key = None
        compositional = {"base_candidate_key": None, "base_surface": _base_surface(str(case.get("target_surface") or "")), "relation": "child_or_kinship_referent", "referent_candidate_key": None}
    elif model_decision == "candidate" and chosen:
        if "explicit_name" in support_families:
            final_status = "explicit_resolved"
        elif str(payload.get("confidence")) == "high" and len(support_families) >= 2:
            final_status = "contextually_resolved"
        elif support_families:
            final_status = "contextually_preferred"
        else:
            final_status = "unresolved"
        final_key = chosen_key
        compositional = None
    else:
        final_status = "unresolved"
        final_key = None
        compositional = None
    return {
        "occurrence_id": case.get("occurrence_id"),
        "target_surface": case.get("target_surface"),
        "story_id": case.get("story_id"),
        "status": final_status,
        "candidate_key": final_key,
        "resolved_person_id": chosen.get("person_id") if chosen and final_key and final_status in {"explicit_resolved", "contextually_resolved"} else None,
        "support_families": support_families,
        "hard_constraint_rejections": sorted(set(hard_rejections)),
        "compositional_referent": compositional,
        "model_decision": dict(payload),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def compare_to_p1(case: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    baseline = case.get("baseline_surface_decision", {}) or {}
    old_status = str(baseline.get("status") or "unresolved")
    old_pid = str(baseline.get("resolved_person_id") or "")
    new_status = str(result.get("status") or "unresolved")
    new_pid = str(result.get("resolved_person_id") or "")
    if new_status == "compositional_reference" and case.get("occurrence_type") == "kinship_compositional_reference":
        change = "corrected_compositional_reference"
    elif new_pid and old_pid and new_pid != old_pid:
        expected = _explicit_local_person_ids(case)
        change = "corrected_false_merge" if len(expected) == 1 and new_pid in expected else "new_conflict"
    elif new_status in {"explicit_resolved", "contextually_resolved"} and old_status in {"unresolved", "narrowed", "conflict"}:
        change = "newly_contextually_resolved"
    elif new_status == "contextually_preferred" and old_status in {"unresolved", "narrowed"}:
        change = "newly_preferred"
    elif new_status == "unresolved" and old_status in {"unresolved", "narrowed"}:
        change = "remains_unresolved"
    elif new_pid and new_pid == old_pid:
        change = "unchanged_correct"
    else:
        change = "unchanged_correct" if new_status == old_status else "new_conflict"
    return {"occurrence_id": case.get("occurrence_id"), "surface": case.get("target_surface"), "story_id": case.get("story_id"), "p1_surface_decision": {"status": old_status, "resolved_person_id": old_pid or None}, "p1_1_occurrence_decision": {"status": new_status, "resolved_person_id": new_pid or None, "candidate_key": result.get("candidate_key")}, "change": change}


def build_comparison(cases: Sequence[Mapping[str, Any]], results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [compare_to_p1(case, result) for case, result in zip(cases, results)]
    by_surface: dict[str, set[str]] = collections.defaultdict(set)
    for case, result in zip(cases, results):
        pid = str(result.get("resolved_person_id") or "")
        if pid:
            by_surface[matching(case.get("target_surface") or "")].add(pid)
    split = {surface: sorted(pids) for surface, pids in by_surface.items() if len(pids) > 1}
    return {"schema": "hdb2-p1-1-comparison-v1", "occurrence_decisions": rows, "surface_buckets_split": split, "same_surface_multi_person_cases": sum(len(v) > 1 for v in by_surface.values()), "candidate_only": True, "canonical_write_back": False}


def _explicit_local_person_ids(case: Mapping[str, Any]) -> set[str]:
    """Find unique, text-visible full catalogue forms for post-run audit only.

    This is not sent to DeepSeek and is not a resolution rule.  It supplies a
    conservative diagnostic for cases where the supplied local passage itself
    contains one unambiguous full Person form.
    """
    catalog = hng02.person_catalog()
    text = matching("\n".join([str(case.get("local_story_context") or ""), *[str(x or "") for x in case.get("annotation_context", [])]]))
    result: set[str] = set()
    for pid, person in catalog.items():
        forms = [person.get("canonical_name"), *(person.get("forms") or [])]
        for form in forms:
            normalized = matching(form)
            if len(normalized) >= 2 and normalized in text:
                result.add(str(pid))
                break
    return result


def build_metrics(cases: Sequence[Mapping[str, Any]], results: Sequence[Mapping[str, Any]], comparisons: Mapping[str, Any], validation_stats: Mapping[str, Any] | None = None) -> dict[str, Any]:
    statuses = collections.Counter(str(x.get("status")) for x in results)
    changes = collections.Counter(str(x.get("change")) for x in comparisons.get("occurrence_decisions", []))
    support = sum(len(x.get("support_families", [])) >= 2 and x.get("status") == "contextually_resolved" for x in results)
    false_base = 0
    for case in cases:
        if case.get("occurrence_type") != "kinship_compositional_reference":
            continue
        baseline = case.get("baseline_surface_decision", {}) or {}
        old_pid = str(baseline.get("resolved_person_id") or "")
        if old_pid and any(str(candidate.get("person_id") or "") == old_pid and _is_base_candidate(case, candidate) for candidate in case.get("candidates", [])):
            false_base += 1
    known_correct = 0
    known_wrong = 0
    known_unresolved = 0
    for case, result in zip(cases, results):
        expected = _explicit_local_person_ids(case)
        if len(expected) != 1:
            continue
        resolved = str(result.get("resolved_person_id") or "")
        if resolved == next(iter(expected)):
            known_correct += 1
        elif resolved:
            known_wrong += 1
        else:
            known_unresolved += 1
    return {
        "schema": "hdb2-p1-1-metrics-v1",
        "occurrence_count": len(cases),
        "explicit_resolved": statuses.get("explicit_resolved", 0),
        "contextually_resolved": statuses.get("contextually_resolved", 0),
        "contextually_preferred": statuses.get("contextually_preferred", 0),
        "unresolved": statuses.get("unresolved", 0),
        "compositional_reference": statuses.get("compositional_reference", 0),
        "not_person": statuses.get("not_person", 0),
        "surface_buckets_split": len(comparisons.get("surface_buckets_split", {})),
        "same_surface_multi_person_cases": comparisons.get("same_surface_multi_person_cases", 0),
        "false_base_person_collapses": false_base,
        "false_base_person_collapses_after_fix": sum(1 for x in results if x.get("status") == "compositional_reference" and x.get("resolved_person_id")),
        "candidate_key_invalid": int((validation_stats or {}).get("candidate_key_invalid", 0)),
        "evidence_reference_invalid": int((validation_stats or {}).get("evidence_reference_invalid", 0)),
        "hard_constraint_rejections": sum(bool(x.get("hard_constraint_rejections")) for x in results),
        "contextually_resolved_with_2plus_support_families": int(support),
        "p1_changes": dict(changes),
        "known_wrong_identity_promotions": known_wrong,
        "known_reference_correct": known_correct,
        "known_reference_wrong": known_wrong,
        "known_reference_unresolved": known_unresolved,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def build_audit(cases: Sequence[Mapping[str, Any]], results: Sequence[Mapping[str, Any]], required: Sequence[str] = ("充", "嶠", "庾亮兒", "帝", "籍", "戎")) -> list[dict[str, Any]]:
    rows = []
    for case, result in zip(cases, results):
        if str(case.get("target_surface")) not in required:
            continue
        rows.append({
            "audit_id": f"hdb2-p1-1-audit-{stable_hash(case.get('occurrence_id'))[:20]}",
            "story_id": case.get("story_id"),
            "exact_occurrence": {"surface": case.get("target_surface"), "exact_span": case.get("exact_span"), "source_ref": case.get("source_ref")},
            "candidate_list": [{"candidate_key": d.get("candidate_key"), "display_name": d.get("display_name")} for d in case.get("candidate_dossiers", [])],
            "supplied_context": {"story_text": case.get("local_story_context"), "annotation_context": case.get("annotation_context"), "evidence_items": case.get("evidence_items", [])},
            "model_decision": result.get("model_decision"),
            "support_families": result.get("support_families", []),
            "python_final_decision": result,
            "review_status": "not_reviewed",
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return sorted(rows, key=lambda x: str(x.get("audit_id")))
