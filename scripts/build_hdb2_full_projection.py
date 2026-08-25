#!/usr/bin/env python3
"""Deterministic candidate/database projection for HDB2-F."""

from __future__ import annotations

import collections
import json
import sys
import statistics
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import build_hng0_2 as hng02  # noqa: E402
import hdb2_full_frontier_common as common  # noqa: E402
import hdb2_occurrence_common as occ  # noqa: E402


ENDPOINT_COMPLETE = {"both_existing_resolved", "existing_plus_candidate", "both_candidate_resolved"}
RELATION_CLASSES = {"kinship", "marriage", "institutional"}


def _prior_case_maps() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    cases_by_occ: dict[str, dict[str, Any]] = {}
    decisions_by_id: dict[str, dict[str, Any]] = {}
    types_by_id: dict[str, dict[str, Any]] = {}
    for selection_path, cases_path, result_path in [
        (common.ANNOTATION / "hdb2-p1-1-occurrence-selection.json", ROOT / "data/derived/hdb2-p1-1-occurrence-cases.json", ROOT / "data/generated/hdb2-p1-1/live/20260825T-HDB2-P1-1-01/python-decisions.json"),
        (common.ANNOTATION / "hdb2-p2t-occurrence-selection.json", ROOT / "data/derived/hdb2-p2t-occurrence-cases.json", ROOT / "data/generated/hdb2-p2t/live/20260825T-HDB2-P2T-01/python-decisions.json"),
    ]:
        selection = common.read_json(selection_path, {}) or {}
        doc = common.read_json(cases_path, {}) or {}
        by_occ = {str(x.get("occurrence_id")): dict(x) for x in doc.get("cases", [])}
        for row in selection.get("cases", []):
            oid = str(row.get("occurrence_id"))
            if oid in by_occ:
                cases_by_occ[oid] = by_occ[oid]
                types_by_id[str(row.get("identity_observation_id"))] = {
                    "occurrence_type": row.get("occurrence_type") or row.get("selection_category"),
                    "occurrence_id": oid,
                }
        result = common.read_json(result_path, {}) or {}
        records = list(result.get("records", []))
        rows = list(selection.get("cases", []))
        for index, record in enumerate(records):
            selected = rows[index] if index < len(rows) else {}
            identity_id = str(record.get("identity_observation_id") or selected.get("identity_observation_id") or "")
            if not identity_id:
                continue
            item = dict(record)
            item["identity_observation_id"] = identity_id
            item["occurrence_id"] = str(record.get("occurrence_id") or selected.get("occurrence_id") or "")
            item["occurrence_type"] = selected.get("occurrence_type") or selected.get("selection_category")
            decisions_by_id[identity_id] = item
    return cases_by_occ, decisions_by_id, types_by_id


def _load_inputs(run_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    aggregate, identity, relations, registry = common.load_hdb1()
    ledger = common.read_json(common.DERIVED / "hdb2-f-occurrence-ledger.json", {}) or {}
    live_contexts = common.read_json(run_dir / "occurrence-contexts.json", {}) or {}
    live_decisions = common.read_json(run_dir / "python-decisions.json", {}) or {}
    live_cases = {str(x.get("occurrence_id")): dict(x) for x in live_contexts.get("cases", [])}
    live_results = {str(x.get("occurrence_id")): dict(x) for x in live_decisions.get("records", [])}
    prior_cases, prior_decisions, prior_types = _prior_case_maps()
    # Previous cases are also useful for selected candidate keys and local
    # semantic typing, but their decisions remain separate overlays.
    _ = prior_cases
    return aggregate, identity, relations, registry, {str(x.get("occurrence_id")): dict(x) for x in ledger.get("occurrences", [])}, {**live_results, **{}}


def _case_for_occurrence(occurrence: Mapping[str, Any], live_cases: Mapping[str, Mapping[str, Any]], prior_cases: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any]:
    oid = str(occurrence.get("occurrence_id"))
    return live_cases.get(oid) or prior_cases.get(oid) or {}


def _candidate_id_for_result(result: Mapping[str, Any], case: Mapping[str, Any]) -> tuple[str | None, str | None]:
    if result.get("status") == "direct_existing" and result.get("resolved_person_id"):
        return str(result.get("resolved_person_id")), None
    key = result.get("candidate_key")
    if key in (None, ""):
        if result.get("status") == "resolved_new_candidate":
            return str(result.get("new_candidate_id") or "") or None, str(result.get("new_candidate_label") or "") or None
        return None, None
    candidate = next((x for x in case.get("candidates", []) if str(x.get("candidate_key")) == str(key)), None)
    if not candidate:
        return None, None
    if candidate.get("person_id"):
        return str(candidate.get("person_id")), str(candidate.get("display_name") or "")
    label = str(result.get("new_candidate_label") or candidate.get("display_name") or "")
    cid = str(result.get("new_candidate_id") or f"hdb2-candidate-person-{common.stable_hash({'occurrence_id': case.get('occurrence_id'), 'candidate_key': key, 'label': label})[:16]}")
    return cid, label


def _decision_record(row: Mapping[str, Any], result: Mapping[str, Any] | None, case: Mapping[str, Any], *, source: str) -> dict[str, Any]:
    result = dict(result or {})
    status = str(result.get("status") or "unresolved")
    pid, label = _candidate_id_for_result(result, case)
    if status in {"explicit_resolved", "contextually_resolved", "direct_existing"} and not pid:
        # A ruler/title candidate without an existing Person is not an
        # existing identity resolution; preserve it as structural/unresolved.
        if status == "direct_existing":
            status = "unresolved"
    resolved_person_id = pid if pid and pid.startswith("person-") else None
    candidate_person_id = pid if pid and not pid.startswith("person-") else None
    if status in {"compositional_reference", "ruler_reference", "office_reference", "not_person"}:
        # Structural interpretation is deliberately not a Person identity
        # decision, even when its local dossier happened to contain a
        # catalogue candidate.
        resolved_person_id = None
        candidate_person_id = None
    return {
        "occurrence_id": row.get("occurrence_id"),
        "identity_observation_id": row.get("identity_observation_id"),
        "story_id": row.get("story_id"),
        "surface": row.get("target_surface"),
        "exact_span": row.get("exact_span"),
        "evidence_ref": row.get("evidence_ref"),
        "occurrence_type": case.get("occurrence_type") or occ.classify_occurrence(str(row.get("target_surface") or ""), row),
        "status": status,
        "resolved_person_id": resolved_person_id,
        "candidate_person_id": candidate_person_id,
        "candidate_label": label,
        "candidate_key": result.get("candidate_key"),
        "original_hdb1_candidate_id": row.get("hdb1_candidate_id"),
        "original_hdb1_provisional_person_id": row.get("original_hdb1_provisional_person_id"),
        "identity_resolution_basis": result.get("identity_resolution_basis") or ("new_candidate" if pid and not pid.startswith("person-") else "unresolved"),
        "support_families": sorted(set(result.get("support_families") or [])),
        "hard_constraint_rejections": sorted(set(result.get("hard_constraint_rejections") or [])),
        "cascade_stage": result.get("cascade_stage"),
        "rescue_attempted": bool(result.get("rescue_attempted")),
        "rescue_useful": bool(result.get("rescue_useful")),
        "rescue_reasons": list(result.get("rescue_reasons") or []),
        "contextual_call_count": int(result.get("contextual_call_count") or 0),
        "source": source,
        "evidence_chain": [{"evidence_ref": row.get("evidence_ref"), "exact_span": row.get("exact_span")}],
        "candidate_only": True,
        "canonical_write_back": False,
    }


def build_occurrence_decisions(run_dir: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    aggregate, identity, relations, registry = common.load_hdb1()
    ledger = common.read_json(common.DERIVED / "hdb2-f-occurrence-ledger.json", {}) or {}
    live_cases_doc = common.read_json(run_dir / "occurrence-contexts.json", {}) or {}
    live_results_doc = common.read_json(run_dir / "python-decisions.json", {}) or {}
    live_cases = {str(x.get("occurrence_id")): dict(x) for x in live_cases_doc.get("cases", [])}
    live_results = {str(x.get("occurrence_id")): dict(x) for x in live_results_doc.get("records", [])}
    prior_cases, prior_decisions, prior_types = _prior_case_maps()
    decisions: list[dict[str, Any]] = []
    for row in ledger.get("occurrences", []):
        oid = str(row.get("occurrence_id"))
        identity_id = str(row.get("identity_observation_id"))
        case = live_cases.get(oid) or prior_cases.get(oid) or {}
        hdb1_status = str(row.get("original_hdb1_status") or "unresolved")
        if hdb1_status == "resolved_existing" and row.get("original_hdb1_resolved_person_id"):
            result = {
                "status": "direct_existing",
                "resolved_person_id": row.get("original_hdb1_resolved_person_id"),
                "identity_resolution_basis": row.get("original_hdb1_basis") or "catalogue_exact_match",
                "cascade_stage": "hdb1_direct",
            }
            decisions.append(_decision_record(row, result, case, source="hdb1_direct_existing"))
            continue
        prior = prior_decisions.get(identity_id, {})
        if prior:
            prior_result = dict(prior)
            prior_result["status"] = prior_result.get("status") or "unresolved"
            # P1.1/P2T records are frozen overlays.  Their local key is
            # resolved against the matching frozen case, never by surface.
            decisions.append(_decision_record(row, prior_result, case, source=str(prior.get("source") or "prior_hdb2")))
            continue
        result = live_results.get(oid)
        if not result:
            raise RuntimeError(f"missing_hdb2_f_decision:{oid}")
        decisions.append(_decision_record(row, result, case, source="hdb2_f"))
    return decisions, live_cases, {**prior_cases}


def _decision_by_identity(decisions: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(x.get("identity_observation_id")): dict(x) for x in decisions}


def _candidate_registry(decisions: Sequence[Mapping[str, Any]], identity: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    by_candidate: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        cid = str(decision.get("candidate_person_id") or "")
        if not cid:
            continue
        item = by_candidate.setdefault(cid, {
            "candidate_identity_id": cid,
            "status": "compatible_candidate_cluster",
            "canonical_candidate_label": decision.get("candidate_label") or decision.get("surface"),
            "observed_surfaces": [],
            "observation_ids": [],
            "story_ids": [],
            "evidence_refs": [],
            "resolved_person_id": None,
            "identity_basis_summary": collections.Counter(),
            "blocked_relation_count": 0,
            "blocked_kinship_count": 0,
            "blocked_marriage_count": 0,
            "occurrence_count": 0,
            "candidate_only": True,
            "canonical_write_back": False,
        })
        item["observed_surfaces"].append(decision.get("surface"))
        item["observation_ids"].append(decision.get("identity_observation_id"))
        item["story_ids"].append(decision.get("story_id"))
        item["evidence_refs"].append(decision.get("evidence_ref"))
        item["identity_basis_summary"][str(decision.get("identity_resolution_basis") or "unresolved")] += 1
        item["occurrence_count"] += 1
    for item in by_candidate.values():
        item["observed_surfaces"] = sorted(set(x for x in item["observed_surfaces"] if x))
        item["observation_ids"] = sorted(set(x for x in item["observation_ids"] if x))
        item["story_ids"] = sorted(set(x for x in item["story_ids"] if x))
        item["evidence_refs"] = sorted(set(x for x in item["evidence_refs"] if x))
        item["identity_basis_summary"] = dict(sorted(item["identity_basis_summary"].items()))
    return sorted(by_candidate.values(), key=lambda x: str(x.get("candidate_identity_id"))), by_candidate


def _endpoint_from_ref(ref: Any, person_id: Any, identity_by_id: Mapping[str, Mapping[str, Any]], candidate_by_hdb1_id: Mapping[str, str], decisions_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    ref_text = str(ref or "")
    if ref_text.startswith("person:") or (person_id and str(person_id).startswith("person-")):
        pid = str(person_id or ref_text.split(":", 1)[1])
        return {"type": "existing", "person_id": pid}
    if ":" in ref_text:
        kind, key = ref_text.split(":", 1)
        if kind == "unresolved":
            decision = decisions_by_id.get(key, {})
            status = str(decision.get("status") or "unresolved")
            if decision.get("resolved_person_id"):
                return {"type": "existing", "person_id": decision.get("resolved_person_id"), "identity_observation_id": key, "decision_status": status}
            if decision.get("candidate_person_id"):
                return {"type": "candidate", "candidate_person_id": decision.get("candidate_person_id"), "identity_observation_id": key, "decision_status": status}
            if status in {"compositional_reference", "ruler_reference", "office_reference", "not_person"}:
                return {"type": "structural", "identity_observation_id": key, "decision_status": status}
            if status == "conflict":
                return {"type": "conflict", "identity_observation_id": key, "decision_status": status}
            return {"type": "unresolved", "identity_observation_id": key, "decision_status": status}
        if kind == "provisional":
            candidate_id = candidate_by_hdb1_id.get(key)
            if candidate_id:
                return {"type": "candidate", "candidate_person_id": candidate_id, "hdb1_provisional_id": key}
            for identity_id, decision in decisions_by_id.items():
                if str(identity_by_id.get(identity_id, {}).get("provisional_person_id")) == key:
                    if decision.get("resolved_person_id"):
                        return {"type": "existing", "person_id": decision.get("resolved_person_id"), "identity_observation_id": identity_id, "decision_status": decision.get("status")}
                    if decision.get("candidate_person_id"):
                        return {"type": "candidate", "candidate_person_id": decision.get("candidate_person_id"), "identity_observation_id": identity_id, "decision_status": decision.get("status")}
            return {"type": "unresolved", "hdb1_provisional_id": key}
    return {"type": "unresolved"}


def _before_endpoint(ref: Any, person_id: Any) -> dict[str, Any]:
    ref_text = str(ref or "")
    if ref_text.startswith("person:") or (person_id and str(person_id).startswith("person-")):
        return {"type": "existing", "person_id": str(person_id or ref_text.split(":", 1)[1])}
    if ref_text.startswith("provisional:"):
        return {"type": "candidate", "candidate_person_id": ref_text.split(":", 1)[1]}
    return {"type": "unresolved"}


def _endpoint_state(subject: Mapping[str, Any], object_: Mapping[str, Any]) -> str:
    if subject.get("type") == "existing" and object_.get("type") == "existing" and subject.get("person_id") == object_.get("person_id"):
        return "rejected_self_relation"
    if "conflict" in {subject.get("type"), object_.get("type")}:
        return "conflict"
    if "structural" in {subject.get("type"), object_.get("type")}:
        return "semantic_reference_blocked"
    st, ot = subject.get("type"), object_.get("type")
    if st == "existing" and ot == "existing":
        return "both_existing_resolved"
    if {st, ot} == {"existing", "candidate"}:
        return "existing_plus_candidate"
    if st == "candidate" and ot == "candidate":
        return "both_candidate_resolved"
    if st in {"existing", "candidate"} or ot in {"existing", "candidate"}:
        return "single_endpoint_resolved"
    return "both_unresolved"


def _relation_blocker(row: Mapping[str, Any], state: str, subject: Mapping[str, Any], object_: Mapping[str, Any]) -> str | None:
    if state in ENDPOINT_COMPLETE or state == "rejected_self_relation":
        return None
    if state == "conflict":
        return "identity_conflict"
    statuses = {str(subject.get("decision_status") or ""), str(object_.get("decision_status") or "")}
    if "contextually_preferred" in statuses:
        return "contextually_preferred_only"
    if "compositional_reference" in statuses:
        return "compositional_referent_unresolved"
    if "ruler_reference" in statuses:
        return "ruler_holder_unresolved"
    if "office_reference" in statuses:
        return "office_holder_unresolved"
    if "candidate" in {subject.get("type"), object_.get("type")} and state == "single_endpoint_resolved":
        return "candidate_person_not_materialized"
    if state == "single_endpoint_resolved":
        return "opposite_endpoint_unresolved"
    return "identity_unresolved"


def project_relations(relations: Sequence[Mapping[str, Any]], identity: Sequence[Mapping[str, Any]], decisions: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    identity_by_id = {str(x.get("identity_observation_id")): dict(x) for x in identity}
    decisions_by_id = _decision_by_identity(decisions)
    candidate_by_hdb1: dict[str, str] = {}
    for item in decisions:
        candidate = str(item.get("candidate_person_id") or "")
        if not candidate:
            continue
        for key in (item.get("original_hdb1_candidate_id"), item.get("original_hdb1_provisional_person_id")):
            if key:
                candidate_by_hdb1[str(key)] = candidate
    before_counts: collections.Counter[str] = collections.Counter()
    after_counts: collections.Counter[str] = collections.Counter()
    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for source in relations:
        before_subject = _before_endpoint(source.get("subject_ref"), source.get("subject_person_id"))
        before_object = _before_endpoint(source.get("object_ref"), source.get("object_person_id"))
        before_state = _endpoint_state(before_subject, before_object)
        subject = _endpoint_from_ref(source.get("subject_ref"), source.get("subject_person_id"), identity_by_id, candidate_by_hdb1, decisions_by_id)
        object_ = _endpoint_from_ref(source.get("object_ref"), source.get("object_person_id"), identity_by_id, candidate_by_hdb1, decisions_by_id)
        after_state = _endpoint_state(subject, object_)
        before_counts[before_state] += 1
        after_counts[after_state] += 1
        blocker = _relation_blocker(source, after_state, subject, object_)
        row = {
            "candidate_id": source.get("candidate_id"),
            "story_id": source.get("story_id"),
            "relation_class": source.get("relation_class"),
            "relation_surface": source.get("relation_surface"),
            "semantic_level": source.get("semantic_level"),
            "evidence_ref": source.get("evidence_ref"),
            "exact_span": source.get("exact_span"),
            "before": {"state": before_state, "subject": before_subject, "object": before_object},
            "after": {"state": after_state, "subject": subject, "object": object_},
            "primary_blocker": blocker,
            "newly_unblocked_candidate_fact": before_state not in ENDPOINT_COMPLETE and after_state in ENDPOINT_COMPLETE,
            "candidate_only": True,
            "canonical_write_back": False,
        }
        rows.append(row)
        if blocker:
            blockers.append({"candidate_id": source.get("candidate_id"), "relation_class": source.get("relation_class"), "primary_blocker": blocker, "story_id": source.get("story_id"), "evidence_ref": source.get("evidence_ref")})
    return rows, {"before": dict(sorted(before_counts.items())), "after": dict(sorted(after_counts.items()))}, blockers


def build_unblocked(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "status": "newly_unblocked_candidate_fact",
            "candidate_id": row.get("candidate_id"),
            "story_id": row.get("story_id"),
            "relation_class": row.get("relation_class"),
            "relation_surface": row.get("relation_surface"),
            "evidence_ref": row.get("evidence_ref"),
            "exact_span": row.get("exact_span"),
            "endpoint_before": row.get("before"),
            "endpoint_after": row.get("after"),
            "identity_support": [x for x in [row.get("after", {}).get("subject", {}).get("identity_observation_id"), row.get("after", {}).get("object", {}).get("identity_observation_id")] if x],
            "candidate_only": True,
            "canonical_write_back": False,
        }
        for row in rows
        if row.get("newly_unblocked_candidate_fact")
    ]


def _work(ref: Any) -> str:
    text = str(ref or "")
    if "liu" in text:
        return "劉注"
    if "jinshu" in text:
        return "晉書"
    if "sgz" in text:
        return "三國志"
    if "ztj" in text:
        return "資治通鑑"
    if "jianshu" in text:
        return "箋疏"
    if "shishuo" in text or "hng2c1" in text:
        return "世說正文"
    return "unknown"


def _occurrence_types(decisions: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    return {str(x.get("identity_observation_id")): str(x.get("occurrence_type") or "unclear") for x in decisions}


def build_knowledge(decisions: Sequence[Mapping[str, Any]], relation_rows: Sequence[Mapping[str, Any]], identity: Sequence[Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]], temporal_rows: Sequence[Mapping[str, Any]] = ()) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_pid: dict[str, dict[str, Any]] = {}
    candidate_by_id: dict[str, dict[str, Any]] = {}
    types = _occurrence_types(decisions)
    def empty(pid: str, name: str) -> dict[str, Any]:
        return {
            "person_id": pid,
            "canonical_name": name,
            "identity": {"observed_surfaces": [], "aliases": [], "courtesy_names": [], "titles": [], "occurrence_ids": [], "identity_evidence": []},
            "story_presence": {"story_ids": [], "roles": [], "main_text_occurrences": [], "annotation_occurrences": []},
            "family": {"kinship_candidates": [], "marriage_candidates": []},
            "offices": {"office_candidates": []},
            "temporal": {"activity_evidence": [], "story_temporal_links": [], "bounded_intervals": []},
            "social": {"relation_candidates": [], "resolved_neighbors": []},
            "evidence": {"source_works": [], "evidence_refs": []},
            "candidate_only": True,
            "canonical_write_back": False,
        }
    for pid, person in catalog.items():
        by_pid[str(pid)] = empty(str(pid), str(person.get("canonical_name") or pid))
    identity_rows = {str(x.get("identity_observation_id")): x for x in identity}
    for decision in decisions:
        target = str(decision.get("resolved_person_id") or decision.get("candidate_person_id") or "")
        if not target:
            continue
        if target.startswith("person-"):
            item = by_pid.setdefault(target, empty(target, str(catalog.get(target, {}).get("canonical_name") or target)))
        else:
            item = candidate_by_id.setdefault(target, empty(target, str(decision.get("candidate_label") or decision.get("surface") or target)))
        surface = str(decision.get("surface") or "")
        item["identity"]["observed_surfaces"].append(surface)
        item["identity"]["occurrence_ids"].append(decision.get("occurrence_id"))
        item["identity"]["identity_evidence"].append({"observation_id": decision.get("identity_observation_id"), "evidence_ref": decision.get("evidence_ref"), "exact_span": decision.get("exact_span"), "basis": decision.get("identity_resolution_basis"), "status": decision.get("status")})
        typ = types.get(str(decision.get("identity_observation_id")), "unclear")
        if typ in {"courtesy_name_reference", "courtesy"}:
            item["identity"]["courtesy_names"].append(surface)
        elif typ in {"title_reference", "office_reference", "ruler_reference"}:
            item["identity"]["titles"].append(surface)
        elif surface and surface != item.get("canonical_name"):
            item["identity"]["aliases"].append(surface)
        item["story_presence"]["story_ids"].append(decision.get("story_id"))
        if "liu" in str(decision.get("evidence_ref")):
            item["story_presence"]["annotation_occurrences"].append(decision.get("occurrence_id"))
        else:
            item["story_presence"]["main_text_occurrences"].append(decision.get("occurrence_id"))
        ref = decision.get("evidence_ref")
        item["evidence"]["evidence_refs"].append(ref)
        item["evidence"]["source_works"].append(_work(ref))
    for row in relation_rows:
        state = row.get("after", {}).get("state")
        if state not in ENDPOINT_COMPLETE:
            continue
        endpoints = [row.get("after", {}).get("subject", {}), row.get("after", {}).get("object", {})]
        for endpoint in endpoints:
            pid = str(endpoint.get("person_id") or endpoint.get("candidate_person_id") or "")
            if not pid:
                continue
            item = by_pid.get(pid) or candidate_by_id.get(pid)
            if not item:
                continue
            item["social"]["relation_candidates"].append({"candidate_id": row.get("candidate_id"), "relation_class": row.get("relation_class"), "relation_surface": row.get("relation_surface"), "story_id": row.get("story_id"), "evidence_ref": row.get("evidence_ref"), "status": "candidate"})
            other = endpoints[1] if endpoint is endpoints[0] else endpoints[0]
            other_id = other.get("person_id") or other.get("candidate_person_id")
            if other_id:
                item["social"]["resolved_neighbors"].append({"person_id": other_id, "relation_surface": row.get("relation_surface"), "relation_class": row.get("relation_class"), "story_id": row.get("story_id")})
            if row.get("relation_class") == "kinship":
                item["family"]["kinship_candidates"].append(dict(row))
            elif row.get("relation_class") == "marriage":
                item["family"]["marriage_candidates"].append(dict(row))
            elif row.get("relation_class") == "institutional":
                item["offices"]["office_candidates"].append(dict(row))
    # Temporal evidence remains Story-owned.  It is attached to a Person
    # knowledge projection only when that Person already has an independent
    # occurrence in the same Story; no temporal fact is transferred across
    # Stories or used here to prove identity.
    person_stories: dict[str, set[str]] = {}
    for item in [*by_pid.values(), *candidate_by_id.values()]:
        person_stories[str(item.get("person_id"))] = set(str(x) for x in item.get("story_presence", {}).get("story_ids", []))
    for temporal in temporal_rows:
        story = str(temporal.get("story_id") or "")
        if not story:
            continue
        for item in [*by_pid.values(), *candidate_by_id.values()]:
            pid = str(item.get("person_id"))
            if story not in person_stories.get(pid, set()):
                continue
            item["temporal"]["story_temporal_links"].append({"story_id": story, "temporal_candidate_id": temporal.get("temporal_candidate_id"), "temporal_role": temporal.get("temporal_role"), "temporal_surface": temporal.get("temporal_surface"), "projection_class": temporal.get("projection_class"), "h0a_status": temporal.get("h0a_status"), "evidence_ref": temporal.get("evidence_ref"), "exact_span": temporal.get("exact_span")})
            item["evidence"]["evidence_refs"].append(temporal.get("evidence_ref"))
            item["evidence"]["source_works"].append("世說正文" if "shishuo" in str(temporal.get("evidence_ref")) else "unknown")
    def clean(item: dict[str, Any]) -> dict[str, Any]:
        def unique(values: list[Any]) -> list[Any]:
            seen: set[str] = set(); out: list[Any] = []
            for value in values:
                key = json.dumps(value, ensure_ascii=False, sort_keys=True)
                if key not in seen:
                    seen.add(key); out.append(value)
            return sorted(out, key=lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True))
        for section in (item["identity"], item["story_presence"], item["evidence"]):
            for key, value in list(section.items()):
                if isinstance(value, list): section[key] = unique([x for x in value if x not in (None, "")])
        for section_name in ("family", "offices", "temporal", "social"):
            for key, value in item[section_name].items():
                item[section_name][key] = unique(value)
        return item
    existing = [clean(by_pid[pid]) for pid in sorted(by_pid)]
    candidates = [clean(candidate_by_id[pid]) for pid in sorted(candidate_by_id)]
    return existing, candidates


def build_bottleneck_audit(relation_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    result: dict[str, collections.Counter[str]] = {"generic_relations": collections.Counter(), "kinship": collections.Counter(), "marriage": collections.Counter(), "office": collections.Counter()}
    for row in relation_rows:
        blocker = row.get("primary_blocker")
        if not blocker:
            continue
        cls = str(row.get("relation_class"))
        bucket = "kinship" if cls == "kinship" else "marriage" if cls == "marriage" else "office" if cls == "institutional" else "generic_relations"
        result[bucket][str(blocker)] += 1
    return {key: dict(sorted(value.items())) for key, value in result.items()}


def build_review_queue(decisions: Sequence[Mapping[str, Any]], relation_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    relation_by_identity: collections.Counter[str] = collections.Counter()
    for row in relation_rows:
        for endpoint in (row.get("after", {}).get("subject", {}), row.get("after", {}).get("object", {})):
            if endpoint.get("identity_observation_id") and row.get("after", {}).get("state") not in ENDPOINT_COMPLETE:
                relation_by_identity[str(endpoint.get("identity_observation_id"))] += 1
    queue: list[dict[str, Any]] = []
    for decision in decisions:
        status = str(decision.get("status"))
        count = relation_by_identity.get(str(decision.get("identity_observation_id")), 0)
        if status == "conflict": priority = "P0"
        elif status == "resolved_new_candidate" or (status in ENDPOINT_COMPLETE and count >= 2): priority = "P1"
        elif status in {"contextually_resolved", "ruler_reference", "office_reference"}: priority = "P2"
        elif status in {"contextually_preferred", "unresolved"} and count >= 1: priority = "P3"
        else: continue
        queue.append({"priority": priority, "identity_observation_id": decision.get("identity_observation_id"), "occurrence_id": decision.get("occurrence_id"), "story_id": decision.get("story_id"), "surface": decision.get("surface"), "status": status, "blocked_relation_count": count, "reason": "candidate_or_endpoint_review" if priority in {"P0", "P1"} else "residual_identity_ambiguity", "candidate_only": True, "canonical_write_back": False})
    return sorted(queue, key=lambda x: (str(x.get("priority")), str(x.get("story_id")), str(x.get("identity_observation_id"))))


def project(run_dir: Path) -> dict[str, Any]:
    aggregate, identity, relations, registry = common.load_hdb1()
    decisions, live_cases, prior_cases = build_occurrence_decisions(run_dir)
    catalog = hng02.person_catalog()
    candidate_registry, candidate_by_id = _candidate_registry(decisions, identity)
    relation_rows, endpoint_metrics, blockers = project_relations(relations, identity, decisions)
    unblocked = build_unblocked(relation_rows)
    temporal_rows: list[dict[str, Any]] = []
    for path in (common.ANNOTATION / "hdb1-temporal-candidates.json", common.ANNOTATION / "hdb1-wave2-temporal-candidates.json"):
        temporal_rows.extend((common.read_json(path, {}) or {}).get("records", []))
    existing_knowledge, candidate_knowledge = build_knowledge(decisions, relation_rows, identity, catalog, temporal_rows)
    bottlenecks = build_bottleneck_audit(relation_rows)
    review_queue = build_review_queue(decisions, relation_rows)
    all_relation = {"schema": "hdb2-f-relation-projection-v1", "records": relation_rows, "endpoint_metrics": endpoint_metrics, "candidate_only": True, "canonical_write_back": False}
    for filename, cls in [("hdb2-f-kinship-projection.json", "kinship"), ("hdb2-f-marriage-projection.json", "marriage"), ("hdb2-f-office-projection.json", "institutional")]:
        rows = [x for x in relation_rows if x.get("relation_class") == cls]
        common.write_json(common.DERIVED / filename, {"schema": f"hdb2-f-{cls}-projection-v1", "records": rows, "endpoint_metrics": {"before": dict(collections.Counter(x["before"]["state"] for x in rows)), "after": dict(collections.Counter(x["after"]["state"] for x in rows))}, "candidate_only": True, "canonical_write_back": False})
    common.write_json(common.DERIVED / "hdb2-f-relation-projection.json", all_relation)
    common.write_json(common.DERIVED / "hdb2-f-candidate-person-registry.json", {"schema": "hdb2-f-candidate-person-registry-v1", "records": candidate_registry, "candidate_only": True, "canonical_write_back": False})
    common.write_json(common.DERIVED / "hdb2-f-person-knowledge.json", {"schema": "hdb2-f-person-knowledge-v1", "records": existing_knowledge, "candidate_only": True, "canonical_write_back": False})
    common.write_json(common.DERIVED / "hdb2-f-candidate-person-knowledge.json", {"schema": "hdb2-f-candidate-person-knowledge-v1", "records": candidate_knowledge, "candidate_only": True, "canonical_write_back": False})
    common.write_json(common.DERIVED / "hdb2-f-endpoint-bottleneck-audit.json", {"schema": "hdb2-f-endpoint-bottleneck-v1", "records": blockers, "counts": bottlenecks, "candidate_only": True, "canonical_write_back": False})
    common.write_json(common.DERIVED / "hdb2-f-network-completion-metrics.json", {"schema": "hdb2-f-network-completion-v1", "endpoint_metrics": endpoint_metrics, "candidate_only": True, "canonical_write_back": False})
    common.write_json(common.ANNOTATION / "hdb2-f-occurrence-decisions.json", {"schema": "hdb2-f-occurrence-decisions-v1", "records": decisions, "candidate_only": True, "canonical_write_back": False})
    common.write_json(common.ANNOTATION / "hdb2-f-candidate-person-review.json", {"schema": "hdb2-f-candidate-person-review-v1", "records": candidate_registry, "candidate_only": True, "canonical_write_back": False})
    common.write_json(common.ANNOTATION / "hdb2-f-review-queue.json", {"schema": "hdb2-f-review-queue-v1", "records": review_queue, "candidate_only": True, "canonical_write_back": False})
    summary = build_summary(decisions, relation_rows, unblocked, existing_knowledge, candidate_knowledge, candidate_registry, run_dir)
    common.write_json(common.DERIVED / "hdb2-f-identity-summary.json", summary["identity_summary"])
    common.write_json(common.DERIVED / "hdb2-f-metrics.json", summary)
    common.write_json(common.DERIVED / "hdb2-f-unblocked-candidate-facts.json", {"schema": "hdb2-f-unblocked-facts-v1", "records": unblocked, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "relation-projection.json", all_relation)
    common.write_json(run_dir / "unblocked-candidate-facts.json", {"records": unblocked, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "knowledge-deltas.json", {"existing_persons": existing_knowledge, "candidate_persons": candidate_knowledge, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "review-queue.json", {"records": review_queue, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "production-summary.json", summary)
    return summary


def build_summary(decisions: Sequence[Mapping[str, Any]], relation_rows: Sequence[Mapping[str, Any]], unblocked: Sequence[Mapping[str, Any]], existing_knowledge: Sequence[Mapping[str, Any]], candidate_knowledge: Sequence[Mapping[str, Any]], candidate_registry: Sequence[Mapping[str, Any]], run_dir: Path) -> dict[str, Any]:
    statuses = collections.Counter(str(x.get("status")) for x in decisions)
    source_counts = collections.Counter(str(x.get("source")) for x in decisions)
    live_records = common.read_json(run_dir / "model-decisions.json", {}) or {}
    calls = list(live_records.get("records", []))
    calls_by_type = {}
    for kind in ("contextual_disambiguation", "evidence_rescue"):
        rows = [x for x in calls if x.get("call_type") == kind]
        usage = {key: sum(int((x.get("usage") or {}).get(key) or 0) for x in rows) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
        latency = [float(x.get("elapsed_seconds")) for x in rows if x.get("elapsed_seconds") is not None]
        calls_by_type[kind] = {"calls": len(rows), **usage, "median_latency": statistics.median(latency) if latency else None, "max_latency": max(latency) if latency else None, "retries": sum(int(x.get("retry_count") or 0) for x in rows), "failures": sum(x.get("classification") in {"provider_request_failure", "response_parse_failure", "response_truncated"} for x in rows), "invalid_schema_payloads": sum(x.get("validation", {}).get("valid") is False for x in rows if kind == "contextual_disambiguation")}
    by_class: dict[str, dict[str, Any]] = {}
    for relation_class in sorted({str(x.get("relation_class")) for x in relation_rows}):
        rows = [x for x in relation_rows if str(x.get("relation_class")) == relation_class]
        by_class[relation_class] = {
            "count": len(rows),
            "before": dict(sorted(collections.Counter(x.get("before", {}).get("state") for x in rows).items())),
            "after": dict(sorted(collections.Counter(x.get("after", {}).get("state") for x in rows).items())),
            "newly_unblocked": sum(bool(x.get("newly_unblocked_candidate_fact")) for x in rows),
        }
    return {
        "schema": "hdb2-f-metrics-v1",
        "candidate_only": True,
        "canonical_write_back": False,
        "identity_summary": {"schema": "hdb2-f-identity-summary-v1", "total_observations": len(decisions), "final_states": dict(sorted(statuses.items())), "source_states": dict(sorted(source_counts.items())), "unique_existing_persons_reached": len({x.get("resolved_person_id") for x in decisions if x.get("resolved_person_id")}), "unique_candidate_persons": len(candidate_registry), "contextual_llm_decisions": sum(x.get("cascade_stage") == "llm_contextual" for x in decisions), "rescue_eligible": sum(bool(x.get("rescue_attempted")) for x in decisions), "rescue_useful": sum(bool(x.get("rescue_useful")) for x in decisions)},
        "identity_metrics": {"total_observations": len(decisions), "hdb1_direct_existing": sum(x.get("source") == "hdb1_direct_existing" for x in decisions), "prior_p1_1_p2t_reused": sum(x.get("source") == "prior_hdb2" for x in decisions), "hdb2_f_python_explicit": sum(x.get("source") == "hdb2_f" and x.get("cascade_stage") == "python_explicit" for x in decisions), "hdb2_f_python_structural": sum(x.get("source") == "hdb2_f" and x.get("cascade_stage") == "python_structural" for x in decisions), "hdb2_f_contextual_llm": sum(x.get("source") == "hdb2_f" and x.get("cascade_stage") == "llm_contextual" for x in decisions), "final_states": dict(sorted(statuses.items()))},
        "endpoint_metrics": {"relation_observations": len(relation_rows), "before": dict(sorted(collections.Counter(x.get("before", {}).get("state") for x in relation_rows).items())), "after": dict(sorted(collections.Counter(x.get("after", {}).get("state") for x in relation_rows).items())), "newly_unblocked_candidate_facts": len(unblocked), "existing_person_edge_completion_rate": sum(x.get("after", {}).get("state") == "both_existing_resolved" for x in relation_rows) / len(relation_rows) if relation_rows else 0, "candidate_aware_edge_completion_rate": sum(x.get("after", {}).get("state") in ENDPOINT_COMPLETE for x in relation_rows) / len(relation_rows) if relation_rows else 0, "by_relation_class": by_class},
        "person_knowledge_coverage": {"existing_persons": len(existing_knowledge), "persons_with_story_occurrence": sum(bool(x.get("story_presence", {}).get("story_ids")) for x in existing_knowledge), "persons_with_kinship": sum(bool(x.get("family", {}).get("kinship_candidates")) for x in existing_knowledge), "persons_with_marriage": sum(bool(x.get("family", {}).get("marriage_candidates")) for x in existing_knowledge), "persons_with_office": sum(bool(x.get("offices", {}).get("office_candidates")) for x in existing_knowledge), "persons_with_temporal": sum(bool(x.get("temporal", {}).get("activity_evidence") or x.get("temporal", {}).get("story_temporal_links")) for x in existing_knowledge), "persons_with_social": sum(bool(x.get("social", {}).get("relation_candidates")) for x in existing_knowledge), "persons_with_multi_source_identity": sum(len(set(x.get("evidence", {}).get("source_works", []))) >= 2 for x in existing_knowledge)},
        "llm": calls_by_type,
        "candidate_person_count": len(candidate_registry),
        "existing_persons_enriched": sum(bool(x.get("identity", {}).get("occurrence_ids") or x.get("social", {}).get("relation_candidates")) for x in existing_knowledge),
    }
