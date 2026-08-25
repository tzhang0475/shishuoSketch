#!/usr/bin/env python3
"""Build HDB1-W1 candidate-only historical data from an immutable live run.

The projection is deterministic and intentionally writes only new HDB1 files.
It never allocates production Person IDs and never changes H0A/H0B or any
canonical/reviewed object.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import shutil
import statistics
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
import sys

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import historical_context_algorithm as algorithm  # noqa: E402
import run_hng2_algorithm_closeout as closeout  # noqa: E402
from hdb1_common import (  # noqa: E402
    NON_SCENE_ROLES,
    OFFICE_VERBS,
    PERSON_LIKE_KINDS,
    ROOT as COMMON_ROOT,
    STAGE,
    hdb_stable_id,
    is_office_or_title_entity,
    is_person_like,
    load_frozen_selection,
    load_h0a_maps,
    load_people_catalog,
    looks_like_office_relation,
    read_json,
    relation_has_explicit_evidence,
    source_hash_for_ref,
    stable_hash,
    write_json,
)


OUT = ROOT / "data/generated/hdb1-wave1"
ANNOTATION = ROOT / "data/annotation"
DERIVED = ROOT / "data/derived"
PRODUCTION_PERSON_RE = re.compile(r"^person-[0-9]+$")


def _run_base(run_id: str) -> Path:
    base = OUT / "live" / run_id
    if not base.is_dir():
        raise RuntimeError(f"hdb1_missing_live_run:{run_id}")
    return base


def _existing_index() -> dict[str, Any]:
    backbone = read_json(ROOT / "data/derived/h0b1-social-backbone.json", {}) or {}
    relation_doc = read_json(ROOT / "data/derived/person-relations-r3b.json", {}) or {}
    result: dict[str, Any] = {
        "kinship": {},
        "marriage": {},
        "office": {},
        "relations": {},
    }

    def add(bucket: str, key: Any, row: Mapping[str, Any], reviewed: bool) -> None:
        result[bucket].setdefault(tuple(key) if isinstance(key, (list, tuple)) else key, []).append({"row": dict(row), "reviewed": reviewed})

    for row in backbone.get("kinship", []):
        a, b = str(row.get("person_a_id") or ""), str(row.get("person_b_id") or "")
        if a and b:
            add("kinship", tuple(sorted((a, b))), row, str(row.get("review_status")) == "reviewed")
    for row in backbone.get("marriages", []):
        a, b = str(row.get("spouse_a_id") or ""), str(row.get("spouse_b_id") or "")
        if a and b:
            add("marriage", tuple(sorted((a, b))), row, str(row.get("review_status")) == "reviewed")
    for row in backbone.get("office_tenures", []):
        person = str(row.get("person_id") or "")
        office = str(row.get("normalized_office_label") or row.get("office_title") or "")
        if person and office:
            add("office", (person, office), row, str(row.get("review_status")) == "reviewed")
    for row in relation_doc.get("materialized_relations", []):
        a, b = str(row.get("subject_id") or ""), str(row.get("object_id") or "")
        if a and b:
            add("relations", tuple(sorted((a, b))), row, str(row.get("review_status")) == "reviewed")
    for row in relation_doc.get("decisions", []):
        if row.get("decision") not in {"approved", "deferred"}:
            continue
        a, b = str(row.get("person_a_id") or ""), str(row.get("person_b_id") or "")
        if a and b:
            add("relations", tuple(sorted((a, b))), row, str(row.get("review_status")) == "reviewed")
    return result


def _novelty(bucket: str, endpoint_ids: Sequence[str | None], existing: Mapping[str, Any], extra_key: Any = None) -> str:
    ids = [str(value) for value in endpoint_ids if value]
    if len(ids) != len(endpoint_ids) or not ids:
        return "unresolved_endpoint"
    key: Any = tuple(sorted(ids))
    if bucket == "office":
        key = (ids[0], str(extra_key or ""))
    rows = list(existing.get(bucket, {}).get(key, []))
    if rows:
        return "existing_reviewed_match" if any(row.get("reviewed") for row in rows) else "existing_candidate_match"
    return "new_candidate"


def _window_map(row: Mapping[str, Any], lane: str) -> dict[str, Mapping[str, Any]]:
    return {
        str(item.get("ref")): item
        for item in row.get("evidence_windows", [])
        if item.get("ref")
    }


def _candidate_person_token(entity: Mapping[str, Any], candidate_id: str, story_id: str, unit_id: str) -> tuple[str, dict[str, Any]]:
    status = str(entity.get("identity_status") or "unresolved")
    resolved = str(entity.get("resolved_person_id") or "")
    basis = str(entity.get("identity_resolution_basis") or "unresolved")
    material = {
        "object_type": "person_observation",
        "story_id": story_id,
        "unit_id": unit_id,
        "entity_key": entity.get("entity_key"),
        "evidence_ref": entity.get("evidence_ref"),
        "exact_span": entity.get("exact_span"),
        "surface": entity.get("surface"),
    }
    observation_id = hdb_stable_id("identity", material)
    if status == "resolved_existing" and resolved:
        return f"person:{resolved}", {"person_id": resolved, "provisional_person_id": None, "observation_id": observation_id}
    if status == "resolved_new_candidate":
        provisional = hdb_stable_id("person", material)
        return f"provisional:{provisional}", {"person_id": None, "provisional_person_id": provisional, "observation_id": observation_id}
    return f"unresolved:{observation_id}", {"person_id": None, "provisional_person_id": None, "observation_id": observation_id}


def _identity_and_entities(person_results: Sequence[Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[tuple[str, str], dict[str, str]], list[dict[str, Any]], dict[str, Any]]:
    person_candidates: list[dict[str, Any]] = []
    identity_candidates: list[dict[str, Any]] = []
    endpoint_map: dict[tuple[str, str], dict[str, str]] = {}
    rejected: list[dict[str, Any]] = []
    target_eval: dict[str, Any] = {"correct": 0, "wrong": 0, "unresolved": 0, "rows": []}
    for result in person_results:
        story_id = str(result.get("story_id"))
        unit_id = str(result.get("unit_id"))
        selection = result.get("selection") or {}
        windows = _window_map(result, "person")
        normalized = result.get("normalization") or {}
        entities = list(normalized.get("entities", []))
        by_key = {str(row.get("entity_key")): dict(row) for row in entities if row.get("entity_key")}
        for entity in entities:
            kind = str(entity.get("entity_kind") or "")
            resolved = str(entity.get("resolved_person_id") or "")
            if resolved and not is_person_like(kind):
                rejected.append({"type": "identity", "reason": "nonperson_person_id_anomaly", "story_id": story_id, "unit_id": unit_id, "entity": dict(entity)})
                continue
            if not is_person_like(kind):
                continue
            candidate_token, token_data = _candidate_person_token(entity, str(entity.get("candidate_key") or ""), story_id, unit_id)
            evidence_ref = str(entity.get("evidence_ref") or "")
            source_hash = source_hash_for_ref(result.get("evidence_windows", []), evidence_ref)
            record = {
                "candidate_id": hdb_stable_id("person-observation", {"story_id": story_id, "unit_id": unit_id, "entity_key": entity.get("entity_key"), "evidence_ref": evidence_ref, "exact_span": entity.get("exact_span"), "surface": entity.get("surface")} ),
                "identity_observation_id": token_data["observation_id"],
                "story_id": story_id,
                "unit_id": unit_id,
                "target_id": selection.get("target_id"),
                "is_target": str(entity.get("surface") or "") == str(selection.get("surface") or ""),
                "entity_key": entity.get("entity_key"),
                "surface": entity.get("surface"),
                "entity_kind": kind,
                "reference_form": entity.get("reference_form"),
                "identity_status": entity.get("identity_status") or "unresolved",
                "person_resolution": entity.get("person_resolution"),
                "resolved_person_id": token_data["person_id"],
                "provisional_person_id": token_data["provisional_person_id"],
                "identity_resolution_basis": entity.get("identity_resolution_basis") or "unresolved",
                "resolution_method": entity.get("resolution_method"),
                "candidate_key": entity.get("candidate_key"),
                "candidate_set": list(entity.get("candidate_set", [])),
                "confidence": entity.get("confidence"),
                "evidence_ref": evidence_ref,
                "exact_span": entity.get("exact_span"),
                "source_hash": source_hash,
                "candidate_only": True,
                "canonical_write_back": False,
                "novelty": "existing_reviewed_match" if token_data["person_id"] else ("new_candidate" if token_data["provisional_person_id"] else "unresolved_endpoint"),
            }
            person_candidates.append(record)
            identity_candidates.append({
                **record,
                "identity_resolution_basis": record["identity_resolution_basis"],
                "derivation_metadata": (entity.get("resolver_result") or {}).get("context_signals", []),
            })
            endpoint_map[(unit_id, str(entity.get("entity_key")))] = {"token": candidate_token, "person_id": token_data["person_id"] or "", "provisional_person_id": token_data["provisional_person_id"] or "", "observation_id": token_data["observation_id"], "entity_kind": kind}
        expected = str(selection.get("reference_person_id") or "")
        target = next((row for row in person_candidates if row.get("unit_id") == unit_id and row.get("is_target")), None)
        eval_row = {"story_id": story_id, "unit_id": unit_id, "target_id": selection.get("target_id"), "target_surface": selection.get("surface"), "expected_person_id": expected or None, "actual_person_id": (target or {}).get("resolved_person_id"), "status": "unresolved"}
        if expected and target and target.get("resolved_person_id") == expected:
            target_eval["correct"] += 1; eval_row["status"] = "correct"
        elif expected and target and target.get("resolved_person_id"):
            target_eval["wrong"] += 1; eval_row["status"] = "wrong"
        elif expected:
            target_eval["unresolved"] += 1
        else:
            eval_row["status"] = "no_hidden_reference"
        target_eval["rows"].append(eval_row)
    return person_candidates, identity_candidates, endpoint_map, rejected, target_eval


def _relation_endpoint(endpoint_map: Mapping[tuple[str, str], Mapping[str, str]], unit_id: str, entity_key: Any) -> Mapping[str, str] | None:
    return endpoint_map.get((unit_id, str(entity_key)))


def _base_relation_record(result: Mapping[str, Any], relation: Mapping[str, Any], endpoints: tuple[Mapping[str, str] | None, Mapping[str, str] | None], novelty: str) -> dict[str, Any]:
    subject, obj = endpoints
    story_id, unit_id = str(result.get("story_id")), str(result.get("unit_id"))
    return {
        "candidate_id": hdb_stable_id("relation", {"object_type": "relation", "story_id": story_id, "unit_id": unit_id, "relation_id": relation.get("relation_id"), "relation_class": relation.get("relation_class"), "subject": subject, "object": obj, "evidence_ref": relation.get("evidence_ref"), "exact_span": relation.get("exact_span")} ),
        "story_id": story_id,
        "unit_id": unit_id,
        "relation_id": relation.get("relation_id"),
        "subject_entity_key": relation.get("subject_entity_key"),
        "object_entity_key": relation.get("object_entity_key"),
        "subject_ref": subject.get("token") if subject else None,
        "object_ref": obj.get("token") if obj else None,
        "subject_person_id": subject.get("person_id") if subject and subject.get("person_id") else None,
        "object_person_id": obj.get("person_id") if obj and obj.get("person_id") else None,
        "subject_provisional_person_id": subject.get("provisional_person_id") if subject and subject.get("provisional_person_id") else None,
        "object_provisional_person_id": obj.get("provisional_person_id") if obj and obj.get("provisional_person_id") else None,
        "relation_surface": relation.get("relation_surface"),
        "relation_class": relation.get("relation_class"),
        "semantic_level": relation.get("semantic_level"),
        "confidence": relation.get("confidence"),
        "evidence_ref": relation.get("evidence_ref"),
        "exact_span": relation.get("exact_span"),
        "source_hash": source_hash_for_ref(result.get("evidence_windows", []), str(relation.get("evidence_ref") or "")),
        "novelty": novelty,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _relation_projection(person_results: Sequence[Mapping[str, Any]], endpoint_map: Mapping[tuple[str, str], Mapping[str, str]], existing: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    relation_candidates: list[dict[str, Any]] = []
    kinship: list[dict[str, Any]] = []
    marriage: list[dict[str, Any]] = []
    offices: list[dict[str, Any]] = []
    identity_assertions: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    relation_stats: dict[str, Any] = {"valid": 0, "existing": 0, "new": 0, "unresolved": 0, "self": 0, "classes": collections.Counter()}
    for result in person_results:
        normalized = result.get("normalization") or {}
        unit_id = str(result.get("unit_id"))
        entities = {str(row.get("entity_key")): dict(row) for row in normalized.get("entities", []) if row.get("entity_key")}
        for relation in normalized.get("relations", []):
            if not relation_has_explicit_evidence(relation):
                rejected.append({"type": "relation", "reason": "missing_exact_evidence", "story_id": result.get("story_id"), "unit_id": unit_id, "relation": dict(relation)})
                continue
            relation_stats["valid"] += 1
            relation_stats["classes"][str(relation.get("relation_class"))] += 1
            if str(relation.get("relation_class")) == "identity_name":
                identity_assertions.append({
                    "identity_assertion_id": hdb_stable_id("identity-assertion", {"story_id": result.get("story_id"), "unit_id": unit_id, "relation_id": relation.get("relation_id"), "evidence_ref": relation.get("evidence_ref"), "exact_span": relation.get("exact_span")} ),
                    "story_id": result.get("story_id"), "unit_id": unit_id, "relation_id": relation.get("relation_id"),
                    "subject_entity_key": relation.get("subject_entity_key"), "object_entity_key": relation.get("object_entity_key"),
                    "relation_surface": relation.get("relation_surface"), "evidence_ref": relation.get("evidence_ref"), "exact_span": relation.get("exact_span"), "confidence": relation.get("confidence"), "candidate_only": True,
                })
                continue
            subject = _relation_endpoint(endpoint_map, unit_id, relation.get("subject_entity_key"))
            obj = _relation_endpoint(endpoint_map, unit_id, relation.get("object_entity_key"))
            endpoint_ids = [subject.get("person_id") if subject else None, obj.get("person_id") if obj else None]
            if subject and obj and subject.get("token") == obj.get("token"):
                relation_stats["self"] += 1
                rejected.append({"type": "relation", "reason": "collapsed_self_relation", "story_id": result.get("story_id"), "unit_id": unit_id, "relation": dict(relation)})
                continue
            relation_class = str(relation.get("relation_class") or "other")
            bucket = "relations"
            if relation_class == "kinship":
                bucket = "kinship"
            elif relation_class == "marriage":
                bucket = "marriage"
            elif relation_class == "institutional" and looks_like_office_relation(relation, entities):
                bucket = "office"
            novelty = _novelty(bucket, endpoint_ids, existing, extra_key=(entities.get(str(relation.get("object_entity_key"))) or {}).get("surface") if bucket == "office" else None)
            base = _base_relation_record(result, relation, (subject, obj), novelty)
            base["graph_candidate"] = relation_class == "interaction" and bool(subject and obj and all(endpoint_ids))
            base["relation_observation_kind"] = "explicit_person_interaction" if relation_class == "interaction" else ("historical_observation" if relation_class == "other" else relation_class)
            relation_candidates.append(base)
            if novelty in {"existing_reviewed_match", "existing_candidate_match"}:
                relation_stats["existing"] += 1
            elif novelty == "new_candidate":
                relation_stats["new"] += 1
            else:
                relation_stats["unresolved"] += 1
            if bucket == "kinship":
                kinship.append({
                    **base,
                    "kinship_type": relation.get("relation_surface"),
                    "direction": "subject_to_object",
                    "fact_kind": "candidate_kinship_fact",
                    "safe_for_existing_fact": bool(subject and obj and all(endpoint_ids)),
                })
            elif bucket == "marriage":
                marriage.append({
                    **base,
                    "union_kind": "candidate_marriage_union",
                    "canonical_endpoint_order": sorted(endpoint_ids) if all(endpoint_ids) else None,
                    "safe_for_existing_union": bool(subject and obj and all(endpoint_ids)),
                })
            elif bucket == "office":
                object_entity = entities.get(str(relation.get("object_entity_key")), {})
                office_surface = str(object_entity.get("surface") or relation.get("relation_surface") or "")
                offices.append({
                    **base,
                    "office_title": office_surface,
                    "office_attribution_kind": "candidate_office_tenure",
                    "safe_for_existing_person": bool(subject and subject.get("person_id")),
                })
    relation_stats["classes"] = dict(relation_stats["classes"])
    return relation_candidates, kinship, marriage, offices, identity_assertions, rejected, relation_stats


def _temporal_projection(temporal_results: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    anchors, evidence = load_h0a_maps()
    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    stats: dict[str, Any] = {
        "valid_temporal_atoms": 0,
        "rejected_temporal_atoms": 0,
        "valid_temporal_assertions": 0,
        "h0a_compatible": 0,
        "h0a_upgrade_candidates": 0,
        "h0a_scene_affecting_conflicts": 0,
        "non_scene_role_disagreements": 0,
        "later_outcome_excluded": 0,
        "quoted_background_excluded": 0,
        "no_temporal_evidence": 0,
        "false_temporal_promotions": 0,
        "scanner_visible_surfaces": 0,
        "scanner_visible_surfaces_considered_by_t1": 0,
        "scanner_visible_recall_misses": 0,
        "h0a_evidence_outside_scanner_scope": 0,
        "t1_temporal_atoms_outside_scanner_scope": 0,
        "no_temporal_evidence_stories": [],
    }
    for result in temporal_results:
        story_id = str(result.get("story_id"))
        windows = result.get("evidence_windows", [])
        stats["scanner_visible_surfaces"] += len(result.get("visible_temporal_surfaces", []))
        valid_read = ((result.get("temporal_read") or {}).get("validation") or {})
        stats["scanner_visible_surfaces_considered_by_t1"] += sum(
            closeout._hint_considered(hint, valid_read.get("valid_atoms", []))
            for hint in result.get("visible_temporal_surfaces", [])
        )
        stats["valid_temporal_atoms"] += len(valid_read.get("valid_atoms", []))
        stats["rejected_temporal_atoms"] += len(valid_read.get("rejected_atoms", []))
        stats["rejected_temporal_atoms"] += len(((result.get("temporal_fill") or {}).get("validation") or {}).get("rejected_temporal_assertions", []))
        normalized = (result.get("normalization") or {}).get("temporal_assertions", [])
        if not normalized:
            stats["no_temporal_evidence"] += 1
            stats["no_temporal_evidence_stories"].append(story_id)
        for item in normalized:
            stats["valid_temporal_assertions"] += 1
            role = str(item.get("temporal_role") or "uncertain")
            h0a = item.get("h0a") or {}
            h0a_status = str(h0a.get("status") or "unknown")
            scene = bool(item.get("scene_constraint_candidate"))
            anchor = anchors.get(story_id, {})
            precision = str(anchor.get("precision") or "unknown")
            if h0a_status == "compatible":
                stats["h0a_compatible"] += 1
            if h0a_status == "conflict" and scene:
                stats["h0a_scene_affecting_conflicts"] += 1
            if h0a_status == "conflict" and not scene:
                stats["non_scene_role_disagreements"] += 1
            if role == "later_outcome" and not scene:
                stats["later_outcome_excluded"] += 1
            if role in {"quoted_precedent", "background_context"} and not scene:
                stats["quoted_background_excluded"] += 1
            upgrade = scene and precision in {"unknown", "phase_only", ""} and h0a_status != "conflict"
            if upgrade:
                stats["h0a_upgrade_candidates"] += 1
            if scene and h0a_status == "conflict":
                stats["false_temporal_promotions"] += 0
            records.append({
                "temporal_candidate_id": hdb_stable_id("temporal", {"story_id": story_id, "temporal_id": item.get("temporal_id"), "evidence_ref": item.get("evidence_ref"), "exact_span": item.get("exact_span"), "temporal_surface": item.get("temporal_surface")} ),
                "story_id": story_id,
                "unit_id": result.get("unit_id"),
                "temporal_id": item.get("temporal_id"),
                "temporal_surface": item.get("temporal_surface"),
                "temporal_type": item.get("temporal_type"),
                "temporal_role": role,
                "reference_surface": item.get("reference_surface"),
                "evidence_ref": item.get("evidence_ref"),
                "exact_span": item.get("exact_span"),
                "confidence": item.get("confidence"),
                "scene_time_candidate": scene,
                "projection_class": "scene_time_candidate" if scene else "contextual_temporal_evidence",
                "h0a_status": h0a_status,
                "h0a_comparison": h0a,
                "h0a_upgrade_candidate": upgrade,
                "h0a_current_anchor": dict(anchor),
                "source_hash": source_hash_for_ref(windows, str(item.get("evidence_ref") or "")),
                "candidate_only": True,
                "canonical_write_back": False,
            })
    return records, stats, rejected


def _operation_summary(manifest: Mapping[str, Any], person_results: Sequence[Mapping[str, Any]], temporal_results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    attempts: list[Mapping[str, Any]] = []
    for result in [*person_results, *temporal_results]:
        for lane in ("person_read", "person_fill", "temporal_read", "temporal_fill"):
            attempts.extend(((result.get(lane) or {}).get("transport") or {}).get("attempts", []))
    usage = {key: sum(int((attempt.get("usage") or {}).get(key) or 0) for attempt in attempts) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    latencies = [float(attempt.get("elapsed_seconds")) for attempt in attempts if attempt.get("status") == "response" and attempt.get("elapsed_seconds") is not None]
    return {
        "model": manifest.get("model"),
        "prompt_versions": manifest.get("prompt_versions", {}),
        "semantic_calls": len(attempts),
        "expected_semantic_calls": manifest.get("expected_semantic_calls"),
        "retries": sum(max(0, len(((result.get(lane) or {}).get("transport") or {}).get("attempts", [])) - 1) for result in [*person_results, *temporal_results] for lane in ("person_read", "person_fill", "temporal_read", "temporal_fill")),
        "provider_failures": sum(attempt.get("classification") == "provider_request_failure" for attempt in attempts),
        "parse_failures": sum(attempt.get("classification") == "response_parse_failure" for attempt in attempts),
        "truncations": sum(attempt.get("classification") == "response_truncated" for attempt in attempts),
        "prompt_tokens": usage["prompt_tokens"],
        "completion_tokens": usage["completion_tokens"],
        "total_tokens": usage["total_tokens"],
        "token_usage": usage,
        "median_latency_seconds": statistics.median(latencies) if latencies else None,
        "max_latency_seconds": max(latencies) if latencies else None,
        "preflight_calls": manifest.get("preflight_calls", 1),
        "api_calls": len(attempts) + int(manifest.get("preflight_calls", 1) or 0),
    }


def _review_queue(person_candidates: Sequence[Mapping[str, Any]], identity_candidates: Sequence[Mapping[str, Any]], relation_candidates: Sequence[Mapping[str, Any]], kinship: Sequence[Mapping[str, Any]], marriage: Sequence[Mapping[str, Any]], offices: Sequence[Mapping[str, Any]], temporal: Sequence[Mapping[str, Any]], rejected: Sequence[Mapping[str, Any]], target_eval: Mapping[str, Any]) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    def add(priority: str, review_type: str, candidate: Mapping[str, Any], reason: str) -> None:
        material = {"priority": priority, "review_type": review_type, "candidate_id": candidate.get("candidate_id") or candidate.get("temporal_candidate_id"), "story_id": candidate.get("story_id"), "exact_span": candidate.get("exact_span")}
        queue.append({
            "review_item_id": hdb_stable_id("review", material),
            "priority": priority,
            "review_type": review_type,
            "review_status": "not_reviewed",
            "candidate_id": candidate.get("candidate_id") or candidate.get("temporal_candidate_id"),
            "story_id": candidate.get("story_id"),
            "unit_id": candidate.get("unit_id"),
            "reason": reason,
            "evidence_ref": candidate.get("evidence_ref"),
            "exact_span": candidate.get("exact_span"),
            "candidate_only": True,
            "canonical_write_back": False,
        })
    for row in target_eval.get("rows", []):
        if row.get("status") == "wrong":
            add("P0", "identity_conflict_with_existing_person", row, "known_target_wrong_resolution")
    for candidate in identity_candidates:
        status = str(candidate.get("identity_status") or "")
        basis = str(candidate.get("identity_resolution_basis") or "")
        if status == "resolved_new_candidate":
            add("P1", "new_person_candidate", candidate, "resolved_new_candidate")
        elif basis == "contextual_name_projection":
            add("P1", "contextual_name_projection", candidate, "contextual identity derivation requires review")
        elif status in {"ambiguous", "unresolved"}:
            add("P3", "unresolved_identity_observation", candidate, status)
    for candidate in kinship:
        add("P1", "new_kinship_candidate", candidate, str(candidate.get("novelty")))
    for candidate in marriage:
        add("P1", "new_marriage_candidate", candidate, str(candidate.get("novelty")))
    for candidate in offices:
        add("P2", "new_office_candidate", candidate, str(candidate.get("novelty")))
    for candidate in relation_candidates:
        if candidate.get("relation_class") == "interaction" and candidate.get("novelty") == "new_candidate":
            add("P2", "new_explicit_interaction", candidate, "explicit interaction between candidate endpoints")
        elif candidate.get("relation_class") == "other":
            add("P3", "other_historical_observation", candidate, "broad relation class requires review")
        elif candidate.get("novelty") == "unresolved_endpoint":
            add("P3", "unresolved_relation_endpoint", candidate, "relation endpoint unresolved")
    for candidate in temporal:
        if candidate.get("h0a_status") == "conflict" and candidate.get("scene_time_candidate"):
            add("P0", "h0a_scene_affecting_conflict", candidate, "candidate scene evidence conflicts with reviewed H0A")
        elif candidate.get("h0a_upgrade_candidate"):
            add("P1", "h0a_upgrade_candidate", candidate, "candidate scene evidence may improve weak H0A")
    return sorted(queue, key=lambda row: (row["priority"], str(row.get("story_id")), str(row["review_item_id"])))


def project(selection: Mapping[str, Any], manifest: Mapping[str, Any], person_results: Sequence[Mapping[str, Any]], temporal_results: Sequence[Mapping[str, Any]], run_id: str) -> dict[str, Any]:
    catalog = load_people_catalog()
    person_candidates, identity_candidates, endpoint_map, rejected_identity, target_eval = _identity_and_entities(person_results, catalog)
    existing = _existing_index()
    relation_candidates, kinship, marriage, offices, identity_assertions, rejected_relations, relation_stats = _relation_projection(person_results, endpoint_map, existing)
    temporal, temporal_stats, rejected_temporal = _temporal_projection(temporal_results)
    operation_summary = _operation_summary(manifest, person_results, temporal_results)
    rejected_items = [*rejected_identity, *rejected_relations, *rejected_temporal]
    for result in person_results:
        for lane in ("person_read", "person_fill"):
            validation = (result.get(lane) or {}).get("validation") or {}
            for key in ("rejected_atoms", "rejected_entities", "rejected_relations"):
                for item in validation.get(key, []) or []:
                    rejected_items.append({"type": key, "lane": lane, "story_id": result.get("story_id"), "unit_id": result.get("unit_id"), **dict(item)})
    for result in temporal_results:
        for lane in ("temporal_read", "temporal_fill"):
            validation = (result.get(lane) or {}).get("validation") or {}
            for key in ("rejected_atoms", "rejected_temporal_assertions"):
                for item in validation.get(key, []) or []:
                    rejected_items.append({"type": key, "lane": lane, "story_id": result.get("story_id"), "unit_id": result.get("unit_id"), **dict(item)})
    review_queue = _review_queue(person_candidates, identity_candidates, relation_candidates, kinship, marriage, offices, temporal, rejected_items, target_eval)
    person_metrics = {
        "resolved_existing": sum(row.get("identity_status") == "resolved_existing" for row in person_candidates),
        "resolved_new_candidate": sum(row.get("identity_status") == "resolved_new_candidate" for row in person_candidates),
        "unresolved": sum(row.get("identity_status") == "unresolved" for row in person_candidates),
        "ambiguous": sum(row.get("identity_status") == "ambiguous" for row in person_candidates),
        "identity_resolution_basis": dict(collections.Counter(str(row.get("identity_resolution_basis") or "unresolved") for row in person_candidates)),
        "new_person_candidate_observations": sum(row.get("identity_status") == "resolved_new_candidate" for row in person_candidates),
        "nonperson_person_id_anomalies": sum(item.get("reason") == "nonperson_person_id_anomaly" for item in rejected_items),
        "target_evaluation": target_eval,
    }
    review_metrics = dict(collections.Counter(str(row.get("priority")) for row in review_queue))
    useful_story_ids = {
        str(row.get("story_id"))
        for row in [*person_candidates, *relation_candidates, *kinship, *marriage, *offices, *temporal]
        if row.get("story_id")
    }
    source_forms = collections.Counter(
        str(window.get("source_form") or "unknown")
        for result in [*person_results, *temporal_results]
        for window in result.get("evidence_windows", [])
    )
    metrics = {
        "stage": STAGE,
        "wave_id": "HDB1-W1",
        "stories_processed": len(selection.get("stories", [])),
        "person_targets": len(person_results),
        "main_text_targets": len(person_results),
        "secondary_targets": sum(len(row.get("targets", [])) > 1 for row in selection.get("stories", [])),
        "deepseek": operation_summary,
        "useful_story_count": len(useful_story_ids),
        "source_form_distribution": dict(source_forms),
        "person": person_metrics,
        "evidence": {
            "valid_person_atoms": sum(len(((row.get("person_read") or {}).get("validation") or {}).get("valid_atoms", [])) for row in person_results),
            "rejected_person_atoms": sum(len(((row.get("person_read") or {}).get("validation") or {}).get("rejected_atoms", [])) for row in person_results),
            "person_grounding_rejection_reasons": dict(collections.Counter(str(item.get("reason")) for row in person_results for item in (((row.get("person_read") or {}).get("validation") or {}).get("rejected_atoms", [])))),
        },
        "relations": {
            "valid_relation_observations": relation_stats["valid"],
            "new_relation_candidates": relation_stats["new"],
            "existing_relation_matches": relation_stats["existing"],
            "unresolved_endpoint_candidates": relation_stats["unresolved"],
            "collapsed_nonidentity_self_relations": relation_stats["self"],
            "relation_classes": relation_stats["classes"],
            "new_kinship_candidates": sum(row.get("novelty") not in {"existing_reviewed_match", "existing_candidate_match"} for row in kinship),
            "new_marriage_candidates": sum(row.get("novelty") not in {"existing_reviewed_match", "existing_candidate_match"} for row in marriage),
            "new_office_candidates": sum(row.get("novelty") not in {"existing_reviewed_match", "existing_candidate_match"} for row in offices),
            "existing_fact_matches": sum(row.get("novelty") in {"existing_reviewed_match", "existing_candidate_match", "additional_evidence_candidate"} for row in [*kinship, *marriage, *offices]),
        },
        "temporal": temporal_stats,
        "review_burden": {"P0": review_metrics.get("P0", 0), "P1": review_metrics.get("P1", 0), "P2": review_metrics.get("P2", 0), "P3": review_metrics.get("P3", 0), "total_review_items": len(review_queue), "review_items_per_story": len(review_queue) / max(1, len(selection.get("stories", [])))},
        "novelty": {
            "new_candidates_per_story": (sum(row.get("novelty") == "new_candidate" for row in [*person_candidates, *relation_candidates, *temporal]) / max(1, len(selection.get("stories", [])))),
            "existing_match_rate": sum(row.get("novelty") in {"existing_reviewed_match", "existing_candidate_match", "additional_evidence_candidate"} for row in [*person_candidates, *relation_candidates, *kinship, *marriage, *offices]) / max(1, len([*person_candidates, *relation_candidates, *kinship, *marriage, *offices])),
            "unresolved_rate": sum(row.get("novelty") == "unresolved_endpoint" for row in [*person_candidates, *relation_candidates, *kinship, *marriage, *offices]) / max(1, len([*person_candidates, *relation_candidates, *kinship, *marriage, *offices])),
        },
        "candidate_only": True,
        "canonical_write_back": False,
    }
    # Keep the production report convenient for validators and downstream
    # review tooling without changing the nested metric structure above.
    metrics.update(
        {
            "semantic_calls": operation_summary.get("semantic_calls", 0),
            "retries": operation_summary.get("retries", 0),
            "provider_failures": operation_summary.get("provider_failures", 0),
            "parse_failures": operation_summary.get("parse_failures", 0),
            "truncations": operation_summary.get("truncations", 0),
            "prompt_tokens": operation_summary.get("prompt_tokens", 0),
            "completion_tokens": operation_summary.get("completion_tokens", 0),
            "total_tokens": operation_summary.get("total_tokens", 0),
            "median_latency": operation_summary.get("median_latency_seconds", 0),
            "max_latency": operation_summary.get("max_latency_seconds", 0),
            "known_target_correct": target_eval.get("correct", 0),
            "known_target_wrong": target_eval.get("wrong", 0),
            "known_target_unresolved": target_eval.get("unresolved", 0),
        }
    )
    candidate_db = {
        "schema": "hdb1-candidate-historical-db-v1",
        "stage": STAGE,
        "run_id": run_id,
        "selection_hash": selection.get("selection_hash"),
        "candidate_only": True,
        "canonical_write_back": False,
        "person_candidates": person_candidates,
        "identity_candidates": identity_candidates,
        "identity_assertions": identity_assertions,
        "relation_candidates": relation_candidates,
        "kinship_candidates": kinship,
        "marriage_candidates": marriage,
        "office_candidates": offices,
        "temporal_candidates": temporal,
        "review_item_ids": [row["review_item_id"] for row in review_queue],
    }
    return {
        "run_id": run_id,
        "selection": dict(selection),
        "manifest": dict(manifest),
        "person_candidates": person_candidates,
        "identity_candidates": identity_candidates,
        "identity_assertions": identity_assertions,
        "relation_candidates": relation_candidates,
        "kinship_candidates": kinship,
        "marriage_candidates": marriage,
        "office_candidates": offices,
        "temporal_candidates": temporal,
        "review_queue": review_queue,
        "rejected_items": rejected_items,
        "candidate_db": candidate_db,
        "metrics": metrics,
        "target_evaluation": target_eval,
    }


def write_projection(projection: Mapping[str, Any]) -> dict[str, str]:
    run_id = str(projection["run_id"])
    annotation_payloads = {
        "hdb1-person-candidates.json": {"schema": "hdb1-person-candidates-v1", "stage": STAGE, "run_id": run_id, "candidate_only": True, "records": projection["person_candidates"]},
        "hdb1-identity-candidates.json": {"schema": "hdb1-identity-candidates-v1", "stage": STAGE, "run_id": run_id, "candidate_only": True, "records": projection["identity_candidates"] + projection["identity_assertions"]},
        "hdb1-relation-candidates.json": {"schema": "hdb1-relation-candidates-v1", "stage": STAGE, "run_id": run_id, "candidate_only": True, "records": projection["relation_candidates"]},
        "hdb1-kinship-candidates.json": {"schema": "hdb1-kinship-candidates-v1", "stage": STAGE, "run_id": run_id, "candidate_only": True, "records": projection["kinship_candidates"]},
        "hdb1-marriage-candidates.json": {"schema": "hdb1-marriage-candidates-v1", "stage": STAGE, "run_id": run_id, "candidate_only": True, "records": projection["marriage_candidates"]},
        "hdb1-office-candidates.json": {"schema": "hdb1-office-candidates-v1", "stage": STAGE, "run_id": run_id, "candidate_only": True, "records": projection["office_candidates"]},
        "hdb1-temporal-candidates.json": {"schema": "hdb1-temporal-candidates-v1", "stage": STAGE, "run_id": run_id, "candidate_only": True, "records": projection["temporal_candidates"]},
        "hdb1-review-queue.json": {"schema": "hdb1-review-queue-v1", "stage": STAGE, "run_id": run_id, "candidate_only": True, "records": projection["review_queue"]},
    }
    paths: dict[str, str] = {}
    for name, payload in annotation_payloads.items():
        path = ANNOTATION / name
        write_json(path, payload)
        paths[name] = str(path)
    write_json(ANNOTATION / "hdb1-rejected-items.json", {"schema": "hdb1-rejected-items-v1", "stage": STAGE, "run_id": run_id, "records": projection["rejected_items"]})
    paths["hdb1-rejected-items.json"] = str(ANNOTATION / "hdb1-rejected-items.json")
    write_json(DERIVED / "hdb1-candidate-historical-db.json", projection["candidate_db"])
    write_json(DERIVED / "hdb1-production-metrics.json", projection["metrics"])
    gap_audit = {
        "schema": "hdb1-gap-audit-v1",
        "stage": STAGE,
        "run_id": run_id,
        "unresolved_persons": [row for row in projection["person_candidates"] if row.get("identity_status") in {"unresolved", "ambiguous"}],
        "unresolved_relation_endpoints": [row for row in projection["relation_candidates"] if row.get("novelty") == "unresolved_endpoint"],
        "no_temporal_evidence_stories": projection["metrics"].get("temporal", {}).get("no_temporal_evidence", []),
        "candidate_only": True,
        "canonical_write_back": False,
    }
    write_json(DERIVED / "hdb1-gap-audit.json", gap_audit)
    paths["hdb1-candidate-historical-db.json"] = str(DERIVED / "hdb1-candidate-historical-db.json")
    paths["hdb1-production-metrics.json"] = str(DERIVED / "hdb1-production-metrics.json")
    paths["hdb1-gap-audit.json"] = str(DERIVED / "hdb1-gap-audit.json")
    live_summary = OUT / "live" / run_id / "production-summary.json"
    live_rejected = OUT / "live" / run_id / "rejected-items.json"
    write_json(
        live_rejected,
        {
            "schema": "hdb1-rejected-items-v1",
            "stage": STAGE,
            "run_id": run_id,
            "candidate_only": True,
            "records": projection["rejected_items"],
        },
    )
    paths["rejected-items.json"] = str(live_rejected)
    write_json(
        live_summary,
        {
            "stage": STAGE,
            "run_id": run_id,
            "candidate_only": True,
            "canonical_write_back": False,
            "selection_hash": projection["selection"].get("selection_hash"),
            "metrics": projection["metrics"],
            "candidate_artifacts": paths,
        },
    )
    paths["production-summary.json"] = str(live_summary)
    return paths


def load_projection_inputs(run_id: str) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    selection = load_frozen_selection()
    base = _run_base(run_id)
    manifest = read_json(base / "manifest.json", {}) or {}
    if manifest.get("status") != "complete":
        raise RuntimeError("hdb1_live_manifest_not_complete")
    return selection, manifest, read_json(base / "person-results.json", []) or [], read_json(base / "temporal-results.json", []) or []


def build_run(run_id: str, *, write: bool = True) -> dict[str, Any]:
    selection, manifest, person_results, temporal_results = load_projection_inputs(run_id)
    expected = int(selection.get("person_target_count") or 0)
    if len(person_results) != expected or len(temporal_results) != 48:
        raise RuntimeError(f"hdb1_live_result_shape_invalid:{len(person_results)}:{len(temporal_results)}")
    projection = project(selection, manifest, person_results, temporal_results, run_id)
    if write:
        projection["written_paths"] = write_projection(projection)
    return projection


def deterministic_rebuild_check(run_id: str) -> dict[str, Any]:
    first = build_run(run_id, write=False)
    second = build_run(run_id, write=False)
    first_json = json.dumps(first, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    second_json = json.dumps(second, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {"equal": first_json == second_json, "first_hash": stable_hash(first), "second_hash": stable_hash(second), "api_calls": 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--check-determinism", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    if args.check_determinism:
        print(json.dumps(deterministic_rebuild_check(args.run_id), ensure_ascii=False, indent=2, sort_keys=True))
        if args.no_write:
            return 0
    projection = build_run(args.run_id, write=not args.no_write)
    print(json.dumps({"run_id": args.run_id, "written_paths": projection.get("written_paths", {}), "metrics": projection.get("metrics", {})}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
