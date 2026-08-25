#!/usr/bin/env python3
"""Shared, candidate-only helpers for HDB2-F.

HDB2-F is an integration layer over the frozen HDB1 and HDB2 occurrence
artifacts.  This module deliberately does not alter those artifacts and does
not contain a second identity algorithm: occurrence construction, the
P1.1/P2T wire card, and the P2T cascade remain the authorities.
"""

from __future__ import annotations

import collections
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import build_hng0_2 as hng02
import hdb2_occurrence_common as occ
import hdb2_p1_common as p1
import hdb2_p2t_common as p2t
import historical_entity_resolver as resolver

ROOT = Path(__file__).resolve().parents[1]
ANNOTATION = ROOT / "data/annotation"
DERIVED = ROOT / "data/derived"
GENERATED = ROOT / "data/generated/hdb2-f"

MODEL = occ.MODEL
RUN_VERSION = "hdb2-f-v1"
ALGORITHM_VERSION = "HNG2-C.3/HDB2-P2T-frozen-frontier-v1"
SCHEMA = "hdb2-f-frontier-v1"

FINAL_STATES = {
    "direct_existing",
    "explicit_resolved",
    "contextually_resolved",
    "contextually_preferred",
    "resolved_new_candidate",
    "compositional_reference",
    "ruler_reference",
    "office_reference",
    "not_person",
    "unresolved",
    "conflict",
}

STRUCTURAL_STATES = {"compositional_reference", "ruler_reference", "office_reference", "not_person"}
PERSON_LIKE_TYPES = {
    "named_person",
    "abbreviated_person_name",
    "courtesy_name_reference",
    "person_title",
    "person_office_title",
    "kinship_reference",
}


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def matching(value: Any) -> str:
    return resolver.matching_normalize(str(value or ""))


def occurrence_id(row: Mapping[str, Any]) -> str:
    return f"hdb2-occ-{stable_hash({'identity_observation_id': row.get('identity_observation_id'), 'story_id': row.get('story_id'), 'evidence_ref': row.get('evidence_ref'), 'exact_span': row.get('exact_span')})[:20]}"


def protected_hashes() -> dict[str, str]:
    """Hash the frozen/canonical inputs, omitting optional files absent here."""
    names = [
        "data/people.json",
        "data/relations.json",
        "data/personStory.json",
        "data/annotation/story-temporal-anchors-h0a.json",
        "data/annotation/story-temporal-evidence-h0a.json",
        "data/annotation/kinship-h0b1.json",
        "data/annotation/marriages-h0b1.json",
        "data/annotation/office-tenures-h0b1.json",
        "data/derived/hdb1-cross-wave-candidate-historical-db.json",
        "data/annotation/hdb1-wave1-selection.json",
        "data/annotation/hdb1-wave2-selection.json",
        "data/generated/hdb2-p1/live/20260825T-HDB2-P1-03/case-results.json",
        "data/derived/hdb2-constraint-results.json",
        "data/annotation/hdb2-p1-1-occurrence-selection.json",
        "data/derived/hdb2-p1-1-occurrence-cases.json",
        "data/generated/hdb2-p1-1/live/20260825T-HDB2-P1-1-01/model-decisions.json",
        "data/annotation/hdb2-p2t-occurrence-selection.json",
        "data/derived/hdb2-p2t-occurrence-cases.json",
        "data/generated/hdb2-p2t/live/20260825T-HDB2-P2T-01/model-decisions.json",
    ]
    return {name: file_hash(ROOT / name) for name in names if (ROOT / name).is_file()}


def load_hdb1() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    aggregate = read_json(DERIVED / "hdb1-cross-wave-candidate-historical-db.json", {}) or {}
    return (
        aggregate,
        [dict(x) for x in aggregate.get("identity_observations", [])],
        [dict(x) for x in aggregate.get("relation_observations", [])],
        [dict(x) for x in aggregate.get("candidate_identity_registry", [])],
    )


def _prior_run_records(selection_path: Path, records_path: Path, *, selection_key: str = "cases") -> list[dict[str, Any]]:
    selection = read_json(selection_path, {}) or {}
    records_doc = read_json(records_path, {}) or {}
    selection_rows = list(selection.get(selection_key, []))
    records = list(records_doc.get("records", []))
    result: list[dict[str, Any]] = []
    # P1.1 records predate occurrence IDs in the decision envelope.  Its
    # runner order is the frozen selection order, so the coordinate mapping is
    # deterministic and does not infer identity from a surface.
    for index, record in enumerate(records):
        selected = selection_rows[index] if index < len(selection_rows) else {}
        identity_id = str(record.get("identity_observation_id") or selected.get("identity_observation_id") or "")
        if not identity_id:
            continue
        result.append({
            "source": selection_path.as_posix().split("/annotation/")[-1],
            "identity_observation_id": identity_id,
            "occurrence_id": str(record.get("occurrence_id") or selected.get("occurrence_id") or ""),
            "story_id": record.get("story_id") or selected.get("story_id"),
            "surface": record.get("target_surface") or selected.get("target_surface") or selected.get("surface"),
            "status": record.get("status") or "unresolved",
            "resolved_person_id": record.get("resolved_person_id"),
            "candidate_key": record.get("candidate_key"),
            "support_families": list(record.get("support_families") or []),
            "hard_constraint_rejections": list(record.get("hard_constraint_rejections") or []),
            "selection": dict(selected),
        })
    return result


def load_prior_decisions() -> dict[str, list[dict[str, Any]]]:
    p11 = _prior_run_records(
        ANNOTATION / "hdb2-p1-1-occurrence-selection.json",
        ROOT / "data/generated/hdb2-p1-1/live/20260825T-HDB2-P1-1-01/python-decisions.json",
    )
    p2t = _prior_run_records(
        ANNOTATION / "hdb2-p2t-occurrence-selection.json",
        ROOT / "data/generated/hdb2-p2t/live/20260825T-HDB2-P2T-01/python-decisions.json",
    )
    by_id: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in [*p11, *p2t]:
        by_id[str(row["identity_observation_id"])].append(row)
    return dict(by_id)


def _registry_by_observation(registry: Sequence[Mapping[str, Any]], identity: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    candidate_to_registry: dict[str, dict[str, Any]] = {}
    for row in registry:
        for candidate_id in row.get("candidate_ids", []):
            candidate_to_registry[str(candidate_id)] = dict(row)
    result: dict[str, dict[str, Any]] = {}
    for row in identity:
        item = candidate_to_registry.get(str(row.get("candidate_id")))
        if item:
            result[str(row.get("identity_observation_id"))] = item
    return result


def build_ledger() -> dict[str, Any]:
    aggregate, identity, relations, registry = load_hdb1()
    prior = load_prior_decisions()
    registry_by_obs = _registry_by_observation(registry, identity)
    rows: list[dict[str, Any]] = []
    direct = 0
    pending = 0
    reused = 0
    for source in sorted(identity, key=lambda x: str(x.get("identity_observation_id"))):
        identity_id = str(source.get("identity_observation_id"))
        hdb1_status = str(source.get("identity_status") or source.get("person_resolution") or "unresolved")
        prior_rows = sorted(prior.get(identity_id, []), key=lambda x: (str(x.get("source")), str(x.get("occurrence_id"))))
        if hdb1_status == "resolved_existing" and source.get("resolved_person_id"):
            effective = {
                "status": "direct_existing",
                "resolved_person_id": source.get("resolved_person_id"),
                "basis": source.get("identity_resolution_basis") or "catalogue_exact_match",
                "source": "hdb1_direct_existing",
            }
            direct += 1
        elif prior_rows:
            chosen = prior_rows[-1]
            effective = {
                "status": chosen.get("status") or "unresolved",
                "resolved_person_id": chosen.get("resolved_person_id"),
                "candidate_key": chosen.get("candidate_key"),
                "basis": "prior_" + ("p2t" if "p2t" in str(chosen.get("source")) else "p1_1"),
                "source": chosen.get("source"),
            }
            reused += 1
        else:
            effective = {"status": "hdb2_f_frontier_pending", "source": "hdb2_f"}
            pending += 1
        registry_row = registry_by_obs.get(identity_id, {})
        rows.append({
            "occurrence_id": occurrence_id(source),
            "identity_observation_id": identity_id,
            "story_id": source.get("story_id"),
            "unit_id": source.get("unit_id"),
            "target_surface": source.get("surface"),
            # Frozen occurrence helpers use the HDB1 field name ``surface``;
            # retain the explicit target_surface name in the ledger as well.
            "surface": source.get("surface"),
            "entity_kind": source.get("entity_kind"),
            "reference_form": source.get("reference_form"),
            "exact_span": source.get("exact_span"),
            "evidence_ref": source.get("evidence_ref"),
            "source_layer": "main_text" if "main" in str(source.get("evidence_ref")) else "liu_annotation",
            "source_hash": source.get("source_hash"),
            "original_hdb1_status": hdb1_status,
            "original_hdb1_basis": source.get("identity_resolution_basis"),
            "original_hdb1_resolved_person_id": source.get("resolved_person_id"),
            "original_hdb1_provisional_person_id": source.get("provisional_person_id"),
            "original_hdb1_candidate_set": list(source.get("candidate_set") or []),
            "hdb1_candidate_id": source.get("candidate_id"),
            "hdb1_candidate_label": registry_row.get("canonical_candidate_label"),
            "hdb1_registry_status": registry_row.get("status"),
            "prior_candidate_decisions": prior_rows,
            "current_effective_state": effective,
        })
    return {
        "schema": "hdb2-f-occurrence-ledger-v1",
        "algorithm_version": ALGORITHM_VERSION,
        "candidate_only": True,
        "canonical_write_back": False,
        "source_inputs": {
            "hdb1_aggregate_hash": stable_hash(aggregate),
            "identity_observation_count": len(identity),
            "relation_observation_count": len(relations),
            "prior_decision_hash": stable_hash(prior),
        },
        "counts": {"total": len(rows), "hdb1_direct_existing": direct, "prior_decisions_reused": reused, "hdb2_f_live_frontier": pending},
        "occurrences": rows,
    }


def build_frontier_selection(ledger: Mapping[str, Any]) -> dict[str, Any]:
    rows = [x for x in ledger.get("occurrences", []) if x.get("current_effective_state", {}).get("status") == "hdb2_f_frontier_pending"]
    aggregate, identity, relations, registry = load_hdb1()
    by_id = {str(x.get("identity_observation_id")): x for x in identity}
    counts_by_surface = collections.Counter(str(x.get("target_surface") or "") for x in rows)
    selection_rows: list[dict[str, Any]] = []
    for row in rows:
        identity_row = by_id.get(str(row.get("identity_observation_id")), {})
        related = [x for x in relations if str(x.get("subject_ref")) == f"unresolved:{row.get('identity_observation_id')}" or str(x.get("object_ref")) == f"unresolved:{row.get('identity_observation_id')}" or str(x.get("subject_ref")) == f"provisional:{row.get('hdb1_candidate_id')}" or str(x.get("object_ref")) == f"provisional:{row.get('hdb1_candidate_id')}"]
        blocked_rel = len(related)
        blocked_kin = sum(str(x.get("relation_class")) == "kinship" for x in related)
        blocked_mar = sum(str(x.get("relation_class")) == "marriage" for x in related)
        neighbor_ids = {str(x.get("subject_person_id")) for x in related if x.get("subject_person_id")} | {str(x.get("object_person_id")) for x in related if x.get("object_person_id")}
        occurrence_type = occ.classify_occurrence(str(row.get("target_surface") or ""), identity_row)
        score = 5 * blocked_mar + 4 * blocked_kin + 2 * blocked_rel + 2 * len(neighbor_ids) + int(counts_by_surface[str(row.get("target_surface") or "")] > 1) + int(occurrence_type in {"title_reference", "office_reference", "ruler_reference"})
        selection_rows.append({
            "occurrence_id": row.get("occurrence_id"),
            "identity_observation_id": row.get("identity_observation_id"),
            "story_id": row.get("story_id"),
            "unit_id": row.get("unit_id"),
            "target_surface": row.get("target_surface"),
            "exact_span": row.get("exact_span"),
            "source_ref": row.get("evidence_ref"),
            "source_section": row.get("source_layer"),
            "original_hdb1_status": row.get("original_hdb1_status"),
            "candidate_set": row.get("original_hdb1_candidate_set", []),
            "blocked_relation_count": blocked_rel,
            "blocked_kinship_count": blocked_kin,
            "blocked_marriage_count": blocked_mar,
            "resolved_neighbor_count": len(neighbor_ids),
            "occurrence_type": occurrence_type,
            "priority_score": score,
            "selection_key": stable_hash({"identity_observation_id": row.get("identity_observation_id"), "occurrence_id": row.get("occurrence_id"), "source_ref": row.get("evidence_ref"), "exact_span": row.get("exact_span")}),
        })
    selection_rows.sort(key=lambda x: str(x.get("selection_key")))
    result = {
        "schema": "hdb2-f-frontier-selection-v1",
        "run_version": RUN_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "model": MODEL,
        "temperature": 0,
        "thinking": "disabled",
        "frozen_before_live": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "total_hdb1_observations": len(ledger.get("occurrences", [])),
        "already_hdb1_resolved": ledger.get("counts", {}).get("hdb1_direct_existing", 0),
        "prior_p1_1_p2t_processed": ledger.get("counts", {}).get("prior_decisions_reused", 0),
        "remaining_hdb2_f_live_frontier": len(selection_rows),
        "source_inputs": {
            "hdb1_aggregate_hash": stable_hash(aggregate),
            "ledger_hash": stable_hash(ledger),
            "hdb1_registry_hash": stable_hash(registry),
            "relation_hash": stable_hash(relations),
        },
        "cases": selection_rows,
        "selection_hash": None,
    }
    result["selection_hash"] = stable_hash({k: v for k, v in result.items() if k != "selection_hash"})
    return result


def _candidate_key(candidate: Mapping[str, Any]) -> tuple[str, str]:
    return str(candidate.get("person_id") or ""), matching(candidate.get("display_name"))


def _reindex_case(case: dict[str, Any], catalog: Mapping[str, Mapping[str, Any]], identity: Sequence[Mapping[str, Any]], relations: Sequence[Mapping[str, Any]]) -> None:
    ordered: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in sorted(case.get("candidates", []), key=lambda x: (str(x.get("source")), matching(x.get("display_name")), str(x.get("person_id") or ""))):
        item = dict(candidate)
        key = _candidate_key(item)
        if not key[1] or key in seen:
            continue
        seen.add(key)
        item.setdefault("support_evidence_ids", [])
        ordered.append(item)
    for index, candidate in enumerate(ordered):
        candidate["candidate_key"] = f"c{index}"
    case["candidates"] = ordered
    case["candidate_keys"] = [x["candidate_key"] for x in ordered]
    case["candidate_dossiers"] = [occ._candidate_dossier(x, catalog, identity, relations, case.get("evidence_items", [])) for x in ordered]
    for dossier, candidate in zip(case["candidate_dossiers"], ordered):
        dossier["candidate_key"] = candidate["candidate_key"]
        dossier["supporting_evidence"] = sorted(set(dossier.get("supporting_evidence", [])))


def _append_person_candidate(case: dict[str, Any], catalog: Mapping[str, Mapping[str, Any]], person_id: str | None, display_name: str, source: str, semantic_type: str = "person", support_ids: Sequence[str] = ()) -> None:
    if person_id and person_id in catalog:
        display_name = str(catalog[person_id].get("canonical_name") or display_name)
    case.setdefault("candidates", []).append({
        "display_name": display_name,
        "person_id": person_id,
        "aliases": [catalog[person_id].get("canonical_name"), *(catalog[person_id].get("forms") or [])] if person_id and person_id in catalog else [],
        "source": source,
        "semantic_type": semantic_type,
        "support_evidence_ids": sorted(set(str(x) for x in support_ids)),
        "known_activity_context": [],
    })


def _prior_same_story(case: Mapping[str, Any], prior: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[dict[str, Any]]:
    story = str(case.get("story_id"))
    rows: list[dict[str, Any]] = []
    for values in prior.values():
        for value in values:
            if str(value.get("story_id")) == story and value.get("resolved_person_id") and value.get("status") in {"explicit_resolved", "contextually_resolved", "direct_existing"}:
                rows.append(dict(value))
    return rows


def build_case(row: Mapping[str, Any], ledger: Mapping[str, Any], units: Sequence[Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]], identity: Sequence[Mapping[str, Any]], relations: Sequence[Mapping[str, Any]], registry: Sequence[Mapping[str, Any]], prior: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    p1_cases, p1_solved_by, p1_by_story_surface = occ._p1_rows()
    p1_solved = {key: p1_solved_by.get(str(value.get("case_id")), {}) for key, value in p1_by_story_surface.items()}
    case = occ._context_case(dict(row), units, catalog, index, identity, relations, p1_by_story_surface, p1_solved)
    case["hdb1_original_status"] = row.get("original_hdb1_status")
    case["hdb1_candidate_id"] = row.get("hdb1_candidate_id")
    case["hdb1_candidate_label"] = row.get("hdb1_candidate_label")
    case["hdb1_candidate_set"] = list(row.get("original_hdb1_candidate_set") or [])
    case["frontier_priority"] = {key: row.get(key) for key in ("priority_score", "blocked_relation_count", "blocked_kinship_count", "blocked_marriage_count", "resolved_neighbor_count")}
    case["prior_candidate_decisions"] = list(row.get("prior_candidate_decisions") or [])
    # HDB1 candidate sets are input evidence for Python generation, not model
    # answers.  Existing IDs never cross the wire in occ.user_prompt().
    for pid in row.get("original_hdb1_candidate_set") or []:
        if str(pid) in catalog:
            _append_person_candidate(case, catalog, str(pid), str(catalog[str(pid)].get("canonical_name") or pid), "hdb1_candidate_set")
    # HDB1 new candidates remain candidate-only, but are not discarded.  A
    # registry label is used only as a local candidate description.
    if row.get("original_hdb1_status") == "resolved_new_candidate":
        label = str(row.get("hdb1_candidate_label") or row.get("target_surface") or "")
        if label:
            _append_person_candidate(case, catalog, None, label, "hdb1_new_candidate", "person")
    for value in _prior_same_story(case, prior):
        pid = str(value.get("resolved_person_id"))
        if pid in catalog:
            _append_person_candidate(case, catalog, pid, str(catalog[pid].get("canonical_name") or pid), "prior_contextual_occurrence")
    _reindex_case(case, catalog, identity, relations)
    # Preserve the frozen P2T provenance boundary for historical witnesses
    # whose registered display/search text contains the HDB1 span while the
    # primary packet has line-break markup.  This adds an explicitly
    # registered local witness; it does not fuzzy-repair a quotation.
    p2t._ensure_occurrence_grounding(case)
    case["candidate_set_before"] = [x.get("person_id") or x.get("display_name") for x in case.get("candidates", [])]
    case["candidate_only"] = True
    case["canonical_write_back"] = False
    return case


def build_cases(ledger: Mapping[str, Any], selection: Mapping[str, Any]) -> dict[str, Any]:
    aggregate, identity, relations, registry = load_hdb1()
    catalog = hng02.person_catalog()
    index = resolver.forms_index(catalog)
    units = occ._source_units()
    prior = load_prior_decisions()
    by_id = {str(x.get("identity_observation_id")): x for x in ledger.get("occurrences", [])}
    rows = [by_id[str(x.get("identity_observation_id"))] for x in selection.get("cases", [])]
    cases = [build_case(row, ledger, units, catalog, index, identity, relations, registry, prior) for row in rows]
    return {
        "schema": "hdb2-f-occurrence-cases-v1",
        "run_version": RUN_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "model": MODEL,
        "temperature": 0,
        "source_inputs": {
            "ledger_hash": stable_hash(ledger),
            "selection_hash": selection.get("selection_hash"),
            "hdb1_aggregate_hash": stable_hash(aggregate),
        },
        "occurrence_count": len(cases),
        "cases": cases,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _visible_text(case: Mapping[str, Any]) -> str:
    return matching("\n".join([str(case.get("local_story_context") or ""), *[str(x or "") for x in case.get("annotation_context", [])], *[str(x.get("text") or "") for x in case.get("evidence_items", [])]]))


def deterministic_result(case: Mapping[str, Any], base: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(base)
    result.setdefault("candidate_key", None)
    result.setdefault("resolved_person_id", None)
    result.setdefault("support_families", [])
    result.setdefault("hard_constraint_rejections", [])
    result["candidate_set_before"] = list(case.get("candidate_set_before", []))
    result["candidate_count_before"] = len(case.get("candidates", []))
    if result.get("status") in STRUCTURAL_STATES:
        # A structural interpretation may have been selected from a dossier
        # containing a catalogue candidate, but it is not an identity
        # decision.  Keep the local key/reason for audit while making the
        # Person endpoint explicitly null.
        result["resolved_person_id"] = None
        result["candidate_person_id"] = None
    candidate = next((x for x in case.get("candidates", []) if str(x.get("candidate_key")) == str(result.get("candidate_key"))), None)
    if result.get("status") == "explicit_resolved" and candidate and not result.get("resolved_person_id"):
        if candidate.get("source") in {"hdb1_new_candidate", "rescue_evidence_identity"} and len(matching(candidate.get("display_name"))) >= 2 and matching(candidate.get("display_name")) in _visible_text(case):
            result["status"] = "resolved_new_candidate"
            result["new_candidate_label"] = candidate.get("display_name")
            result["new_candidate_id"] = f"hdb2-candidate-person-{stable_hash({'occurrence_id': case.get('occurrence_id'), 'label': candidate.get('display_name'), 'evidence': case.get('evidence_items', [])})[:16]}"
    if result.get("status") in {"explicit_resolved", "contextually_resolved", "direct_existing"}:
        if result.get("resolved_person_id"):
            result["identity_resolution_basis"] = result.get("identity_resolution_basis") or ("catalogue_exact_match" if result.get("cascade_stage") == "python_explicit" else ("evidence_identity_assertion" if "explicit_name" in result.get("support_families", []) else "contextual_name_projection"))
        else:
            result.setdefault("identity_resolution_basis", "new_candidate")
    elif result.get("status") == "resolved_new_candidate":
        result["identity_resolution_basis"] = "new_candidate"
    else:
        result.setdefault("identity_resolution_basis", "unresolved")
    result["candidate_only"] = True
    result["canonical_write_back"] = False
    return result


def deterministic_cascade(case: Mapping[str, Any]) -> dict[str, Any]:
    return deterministic_result(case, p2t.deterministic_cascade(case))


def apply_contextual(case: Mapping[str, Any], payload: Mapping[str, Any], validation: Mapping[str, Any]) -> dict[str, Any]:
    if validation.get("valid") is not True:
        return deterministic_result(case, {
            "status": "unresolved",
            "candidate_key": None,
            "resolved_person_id": None,
            "cascade_stage": "llm_contextual",
            "cascade_reason": "invalid_model_payload",
            "llm_called": True,
            "hard_constraint_rejections": list(validation.get("errors", [])),
        })
    result = occ.python_decision(case, payload, validation)
    if any(code in result.get("hard_constraint_rejections", []) for code in ("explicit_temporal_conflict", "ruler_reference_candidate_type_conflict", "non_person_occurrence_candidate", "compositional_base_person_rejected")):
        result["status"] = "conflict"
    result.update({"cascade_stage": "llm_contextual", "cascade_reason": "multiple_plausible_candidates", "llm_called": True})
    return deterministic_result(case, result)


def rescue_eligible(case: Mapping[str, Any], all_identity: Sequence[Mapping[str, Any]]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    frontier = case.get("frontier_priority", {})
    if int(frontier.get("blocked_marriage_count") or 0) > 0:
        reasons.append("blocked_marriage")
    if int(frontier.get("blocked_kinship_count") or 0) > 0:
        reasons.append("blocked_kinship")
    if int(frontier.get("blocked_relation_count") or 0) >= 2:
        reasons.append("two_blocked_relations")
    stories = {str(x.get("story_id")) for x in all_identity if matching(x.get("surface")) == matching(case.get("target_surface"))}
    if len(stories) >= 2:
        reasons.append("surface_occurs_in_multiple_stories")
    if case.get("occurrence_type") in {"title_reference", "office_reference", "ruler_reference"}:
        reasons.append("title_ruler_office_ambiguity")
    return bool(reasons), reasons


def candidate_from_atom(case: dict[str, Any], atom: Mapping[str, Any], catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]]) -> list[dict[str, Any]]:
    if str(atom.get("atom_kind")) != "identity_name":
        return []
    target = matching(case.get("target_surface"))
    surfaces = [str(atom.get("subject_surface") or ""), str(atom.get("object_surface") or "")]
    other = [x for x in surfaces if x and matching(x) != target]
    added: list[dict[str, Any]] = []
    for value in other:
        pids = sorted({str(x) for x in index.get(matching(value), []) if str(x) in catalog})
        if len(pids) == 1:
            _append_person_candidate(case, catalog, pids[0], str(catalog[pids[0]].get("canonical_name") or value), "rescue_evidence_identity", "person")
            added.append({"surface": value, "person_id": pids[0], "basis": "catalogue_exact_match"})
        elif len(pids) == 0 and len(matching(value)) >= 2:
            _append_person_candidate(case, catalog, None, value, "rescue_evidence_identity", "person")
            added.append({"surface": value, "person_id": None, "basis": "new_candidate"})
    return added


def source_work_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(collections.Counter(str(x.get("source_work") or "unknown") for x in rows))


def compact_rescue_search_result(row: Mapping[str, Any]) -> dict[str, Any]:
    """Remove passage bodies from the persisted rescue search trace.

    Retrieval and ranking are unchanged.  The selected passage bodies remain
    in ``rescue-selected-passages.json``; the search trace keeps only enough
    hit metadata to audit counts, ranking, and source coverage.
    """
    hits = list(row.get("hits") or [])
    selected = list(row.get("selected_passages") or [])
    selected_refs = [str(item.get("ref")) for item in selected if item.get("ref")]
    selected_set = set(selected_refs)
    unselected: list[dict[str, Any]] = []
    for rank, hit in enumerate(hits, start=1):
        ref = str(hit.get("ref") or "")
        if ref in selected_set:
            continue
        query = hit.get("query") if isinstance(hit.get("query"), Mapping) else {}
        unselected.append({
            "ref": ref,
            "source_work": hit.get("source_work"),
            "source_layer": hit.get("source_layer"),
            "rank": rank,
            "score": hit.get("score"),
            "matched_terms": [str(query.get("term"))] if query.get("term") else [],
        })
    return {
        "occurrence_id": row.get("occurrence_id"),
        "queries": list(row.get("queries") or []),
        "total_hit_count": len(hits),
        "hits_by_source": source_work_counts(hits),
        "selected_refs": selected_refs,
        "selected_count": len(selected_refs),
        "unselected_hits": unselected,
        "reasons": list(row.get("reasons") or []),
    }
