#!/usr/bin/env python3
"""Build HDB1-W2 local candidates and aggregate HDB1 W1+W2 offline.

The aggregate is an evidence-preserving candidate projection.  It never
allocates Person IDs, writes canonical facts, or uses same-surface similarity
as an identity assertion.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_hdb1_candidate_database as builder  # noqa: E402
import historical_entity_resolver as resolver  # noqa: E402
import run_hdb1_wave2 as wave2  # noqa: E402
from hdb1_common import (  # noqa: E402
    ROOT as COMMON_ROOT,
    hdb_stable_id,
    load_frozen_selection as load_w1_selection,
    read_json,
    stable_hash,
    write_json,
)


W1_ROOT = ROOT / "data/generated/hdb1-wave1"
W2_ROOT = ROOT / "data/generated/hdb1-wave2"
ANNOTATION = ROOT / "data/annotation"
DERIVED = ROOT / "data/derived"
W2_STAGE = "hdb1-wave2-remaining-scope-production"
CROSS_STAGE = "hdb1-cross-wave-candidate-aggregation"


def _latest_complete_run(root: Path) -> str:
    runs = []
    for path in sorted((root / "live").glob("*")):
        if (path / "manifest.json").is_file() and (read_json(path / "manifest.json", {}) or {}).get("status") == "complete":
            runs.append(path.name)
    if len(runs) != 1:
        raise RuntimeError(f"expected_one_complete_run:{root}:{runs}")
    return runs[0]


def _tag_projection(projection: dict[str, Any], wave_id: str, stage: str, run_id: str) -> dict[str, Any]:
    projection["wave_id"] = wave_id
    projection["run_id"] = run_id
    projection["metrics"]["wave_id"] = wave_id
    projection["metrics"]["stage"] = stage
    projection["candidate_db"]["wave_id"] = wave_id
    projection["candidate_db"]["run_id"] = run_id
    projection["candidate_db"]["stage"] = stage
    return projection


def load_wave_projection(wave_id: str, run_id: str) -> dict[str, Any]:
    if wave_id == "HDB1-W1":
        projection = builder.build_run(run_id, write=False)
        return _tag_projection(projection, wave_id, "hdb1-wave1-controlled-candidate-production", run_id)
    if wave_id != "HDB1-W2":
        raise ValueError(wave_id)
    selection = wave2.load_frozen_selection()
    base = W2_ROOT / "live" / run_id
    manifest = read_json(base / "manifest.json", {}) or {}
    if manifest.get("status") != "complete":
        raise RuntimeError(f"hdb1_w2_manifest_not_complete:{run_id}")
    person_results = read_json(base / "person-results.json", []) or []
    temporal_results = read_json(base / "temporal-results.json", []) or []
    expected = int(selection.get("person_target_count") or 0)
    if len(person_results) != expected or len(temporal_results) != int(selection.get("story_count") or 0):
        raise RuntimeError(f"hdb1_w2_result_shape_invalid:{len(person_results)}:{len(temporal_results)}")
    projection = builder.project(selection, manifest, person_results, temporal_results, run_id)
    return _tag_projection(projection, wave_id, W2_STAGE, run_id)


def _write_wave2_projection(projection: Mapping[str, Any]) -> dict[str, str]:
    run_id = str(projection["run_id"])
    payloads = {
        "hdb1-wave2-person-candidates.json": projection["person_candidates"],
        "hdb1-wave2-identity-candidates.json": [*projection["identity_candidates"], *projection["identity_assertions"]],
        "hdb1-wave2-relation-candidates.json": projection["relation_candidates"],
        "hdb1-wave2-kinship-candidates.json": projection["kinship_candidates"],
        "hdb1-wave2-marriage-candidates.json": projection["marriage_candidates"],
        "hdb1-wave2-office-candidates.json": projection["office_candidates"],
        "hdb1-wave2-temporal-candidates.json": projection["temporal_candidates"],
        "hdb1-wave2-review-queue.json": projection["review_queue"],
        "hdb1-wave2-rejected-items.json": projection["rejected_items"],
    }
    paths: dict[str, str] = {}
    for name, records in payloads.items():
        path = ANNOTATION / name
        write_json(
            path,
            {
                "schema": name.removesuffix(".json") + "-v1",
                "stage": W2_STAGE,
                "wave_id": "HDB1-W2",
                "run_id": run_id,
                "candidate_only": True,
                "canonical_write_back": False,
                "records": records,
            },
        )
        paths[name] = str(path)

    write_json(DERIVED / "hdb1-wave2-production-metrics.json", projection["metrics"])
    paths["hdb1-wave2-production-metrics.json"] = str(DERIVED / "hdb1-wave2-production-metrics.json")

    live_dir = W2_ROOT / "live" / run_id
    live_rejected = live_dir / "rejected-items.json"
    write_json(
        live_rejected,
        {
            "schema": "hdb1-wave2-rejected-items-v1",
            "stage": W2_STAGE,
            "wave_id": "HDB1-W2",
            "run_id": run_id,
            "candidate_only": True,
            "canonical_write_back": False,
            "records": projection["rejected_items"],
        },
    )
    paths["rejected-items.json"] = str(live_rejected)
    summary = live_dir / "production-summary.json"
    write_json(
        summary,
        {
            "stage": W2_STAGE,
            "wave_id": "HDB1-W2",
            "run_id": run_id,
            "candidate_only": True,
            "canonical_write_back": False,
            "selection_hash": projection["selection"].get("selection_hash"),
            "metrics": projection["metrics"],
            "candidate_artifacts": paths,
        },
    )
    paths["production-summary.json"] = str(summary)
    return paths


def _record_with_wave(record: Mapping[str, Any], wave_id: str, run_id: str) -> dict[str, Any]:
    result = dict(record)
    result["wave_id"] = wave_id
    result["run_id"] = run_id
    return result


def _wave_records(waves: Sequence[Mapping[str, Any]], key: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for wave in waves:
        for row in wave.get(key, []) or []:
            result.append(_record_with_wave(row, str(wave["wave_id"]), str(wave["run_id"])))
    return result


class _UnionFind:
    def __init__(self, values: Iterable[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent.get(value, value)
        if parent != value:
            parent = self.find(parent)
            self.parent[value] = parent
        return parent

    def union(self, left: str, right: str) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[max(a, b)] = min(a, b)


def _identity_inputs(waves: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[tuple[str, str, str], dict[str, Any]], list[dict[str, Any]]]:
    observations = _wave_records(waves, "person_candidates")
    by_entity: dict[tuple[str, str, str], dict[str, Any]] = {}
    by_observation: dict[str, dict[str, Any]] = {}
    for row in observations:
        key = (str(row.get("wave_id")), str(row.get("unit_id")), str(row.get("entity_key")))
        by_entity[key] = row
        by_observation[str(row.get("identity_observation_id"))] = row
    assertions = _wave_records(waves, "identity_assertions")
    propagation: list[dict[str, Any]] = []
    # The wave-local normalizer is authoritative for direct catalogue
    # matches.  This additional pass only records explicit identity evidence
    # and never uses a same-surface match as a merge reason.
    for assertion in assertions:
        wave_id = str(assertion.get("wave_id"))
        unit_id = str(assertion.get("unit_id"))
        subject = by_entity.get((wave_id, unit_id, str(assertion.get("subject_entity_key"))))
        obj = by_entity.get((wave_id, unit_id, str(assertion.get("object_entity_key"))))
        if not subject or not obj:
            continue
        subject_pid = str(subject.get("resolved_person_id") or "")
        object_pid = str(obj.get("resolved_person_id") or "")
        if subject_pid and object_pid and subject_pid != object_pid:
            propagation.append(
                {
                    "propagation_id": hdb_stable_id("identity-propagation", {"wave_id": wave_id, "unit_id": unit_id, "assertion_id": assertion.get("identity_assertion_id")}),
                    "status": "conflicting_identity_assertion",
                    "wave_id": wave_id,
                    "unit_id": unit_id,
                    "assertion_id": assertion.get("identity_assertion_id"),
                    "source_observation_ids": [subject.get("identity_observation_id"), obj.get("identity_observation_id")],
                    "resolved_person_ids": [subject_pid, object_pid],
                    "evidence_ref": assertion.get("evidence_ref"),
                    "exact_span": assertion.get("exact_span"),
                }
            )
        elif subject_pid or object_pid:
            resolved_pid = subject_pid or object_pid
            unresolved = obj if subject_pid else subject
            if not str(unresolved.get("resolved_person_id") or ""):
                propagation.append(
                    {
                        "propagation_id": hdb_stable_id("identity-propagation", {"wave_id": wave_id, "unit_id": unit_id, "assertion_id": assertion.get("identity_assertion_id")}),
                        "status": "supported_existing_identity",
                        "wave_id": wave_id,
                        "unit_id": unit_id,
                        "assertion_id": assertion.get("identity_assertion_id"),
                        "source_observation_ids": [subject.get("identity_observation_id"), obj.get("identity_observation_id")],
                        "resolved_person_id": resolved_pid,
                        "propagated_observation_id": unresolved.get("identity_observation_id"),
                        "evidence_ref": assertion.get("evidence_ref"),
                        "exact_span": assertion.get("exact_span"),
                        "basis": "evidence_identity_assertion",
                    }
                )
    return observations, by_entity, propagation


def _build_identity_registry(waves: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    observations, by_entity, propagation = _identity_inputs(waves)
    observation_by_id = {str(row.get("identity_observation_id")): row for row in observations}
    propagated_pid: dict[str, str] = {}
    for row in propagation:
        if row.get("status") == "supported_existing_identity" and row.get("propagated_observation_id"):
            propagated_pid[str(row["propagated_observation_id"])] = str(row["resolved_person_id"])

    surface_buckets: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in observations:
        surface_buckets[resolver.matching_normalize(row.get("surface"))].append(row)

    # Explicit identity assertions may connect new candidate observations;
    # same-surface observations alone never union.
    union = _UnionFind(str(row.get("identity_observation_id")) for row in observations)
    for assertion in _wave_records(waves, "identity_assertions"):
        wave_id = str(assertion.get("wave_id"))
        unit_id = str(assertion.get("unit_id"))
        subject = by_entity.get((wave_id, unit_id, str(assertion.get("subject_entity_key"))))
        obj = by_entity.get((wave_id, unit_id, str(assertion.get("object_entity_key"))))
        if not subject or not obj:
            continue
        if subject.get("resolved_person_id") or obj.get("resolved_person_id"):
            continue
        if subject.get("identity_observation_id") and obj.get("identity_observation_id"):
            union.union(str(subject["identity_observation_id"]), str(obj["identity_observation_id"]))

    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in observations:
        obs_id = str(row.get("identity_observation_id"))
        pid = str(row.get("resolved_person_id") or propagated_pid.get(obs_id) or "")
        if pid:
            key = f"existing:{pid}"
        elif row.get("identity_status") == "resolved_new_candidate":
            key = f"new:{union.find(obs_id)}"
        else:
            # Retrieval/index bucket only: same normalized surface is never
            # treated as an identity assertion.
            key = f"surface:{resolver.matching_normalize(row.get('surface'))}"
        groups[key].append(row)

    registry: list[dict[str, Any]] = []
    obs_to_cluster: dict[str, str] = {}
    for key, rows in sorted(groups.items()):
        pid_values = sorted({str(row.get("resolved_person_id") or propagated_pid.get(str(row.get("identity_observation_id"))) or "") for row in rows if str(row.get("resolved_person_id") or propagated_pid.get(str(row.get("identity_observation_id"))) or "")})
        status = "resolved_existing" if pid_values else ("compatible_candidate_cluster" if any(row.get("identity_status") == "resolved_new_candidate" for row in rows) else "unresolved_surface_cluster")
        if len(pid_values) > 1:
            status = "conflicted"
        obs_ids = sorted(str(row.get("identity_observation_id")) for row in rows)
        cluster_id = hdb_stable_id("identity-cluster", {"status": status, "key": key, "observation_ids": obs_ids})
        identity_basis = collections.Counter(str(row.get("identity_resolution_basis") or "unresolved") for row in rows)
        if any(str(row.get("identity_observation_id")) in propagated_pid for row in rows):
            identity_basis["evidence_identity_assertion"] += 1
        record = {
            "candidate_identity_id": cluster_id,
            "status": status,
            "canonical_candidate_label": sorted({str(row.get("surface") or "") for row in rows if row.get("surface")})[0] if rows else "",
            "observed_surfaces": sorted({str(row.get("surface") or "") for row in rows if row.get("surface")}),
            "observation_ids": obs_ids,
            "candidate_ids": sorted(str(row.get("candidate_id")) for row in rows if row.get("candidate_id")),
            "story_ids": sorted({str(row.get("story_id")) for row in rows}),
            "evidence_refs": sorted({str(row.get("evidence_ref")) for row in rows if row.get("evidence_ref")}),
            "resolved_person_id": pid_values[0] if len(pid_values) == 1 else None,
            "identity_basis_summary": dict(identity_basis),
            "surface_bucket_only": status == "unresolved_surface_cluster",
            "occurrence_count": len(rows),
            "cross_wave_evidence_count": len({str(row.get("wave_id")) for row in rows}),
            "blocked_relation_count": 0,
            "blocked_kinship_count": 0,
            "blocked_marriage_count": 0,
            "candidate_only": True,
            "canonical_write_back": False,
        }
        registry.append(record)
        for obs_id in obs_ids:
            obs_to_cluster[obs_id] = cluster_id

    # Propagated observations belong to the existing cluster for their target,
    # without mutating the original wave-local observation.
    for row in propagation:
        if row.get("status") == "supported_existing_identity" and row.get("propagated_observation_id"):
            obs_to_cluster[str(row["propagated_observation_id"])] = next(
                (item["candidate_identity_id"] for item in registry if item.get("resolved_person_id") == row.get("resolved_person_id")),
                obs_to_cluster.get(str(row["propagated_observation_id"]), ""),
            )

    surface_output: list[dict[str, Any]] = []
    for folded, rows in sorted(surface_buckets.items()):
        existing_ids = sorted({str(row.get("resolved_person_id")) for row in rows if row.get("resolved_person_id")})
        surface_output.append(
            {
                "surface_bucket_id": hdb_stable_id("surface-bucket", {"surface": folded}),
                "normalized_surface": folded,
                "observed_surfaces": sorted({str(row.get("surface") or "") for row in rows}),
                "observation_ids": sorted(str(row.get("identity_observation_id")) for row in rows),
                "story_ids": sorted({str(row.get("story_id")) for row in rows}),
                "candidate_identity_ids": sorted({obs_to_cluster.get(str(row.get("identity_observation_id")), "") for row in rows if obs_to_cluster.get(str(row.get("identity_observation_id")), "")}),
                "status": "conflicted" if len(existing_ids) > 1 else "surface_bucket",
                "same_surface_is_not_identity": True,
                "candidate_only": True,
            }
        )
    return registry, obs_to_cluster, observation_by_id, propagation, {"surface_buckets": surface_output}


def _endpoint_observation(row: Mapping[str, Any], entity_lookup: Mapping[tuple[str, str, str], Mapping[str, Any]], endpoint_kind: str) -> Mapping[str, Any] | None:
    unit_id = str(row.get("unit_id"))
    wave_id = str(row.get("wave_id"))
    key = "subject_entity_key" if endpoint_kind == "subject" else "object_entity_key"
    return entity_lookup.get((wave_id, unit_id, str(row.get(key))))


def _endpoint_cluster(row: Mapping[str, Any], endpoint_kind: str, obs_to_cluster: Mapping[str, str], entity_lookup: Mapping[tuple[str, str, str], Mapping[str, Any]]) -> str | None:
    person_key = "subject_person_id" if endpoint_kind == "subject" else "object_person_id"
    provisional_key = "subject_provisional_person_id" if endpoint_kind == "subject" else "object_provisional_person_id"
    pid = str(row.get(person_key) or "")
    if pid:
        return next((cluster_id for obs_id, cluster_id in obs_to_cluster.items() if False), None)  # resolved below by the registry map
    provisional = str(row.get(provisional_key) or "")
    endpoint = _endpoint_observation(row, entity_lookup, endpoint_kind)
    if endpoint:
        return obs_to_cluster.get(str(endpoint.get("identity_observation_id")))
    if provisional:
        return None
    raw_ref = str(row.get(f"{endpoint_kind}_ref") or "")
    if raw_ref.startswith("unresolved:"):
        return obs_to_cluster.get(raw_ref.split(":", 1)[1])
    return None


def _cluster_for_endpoint(row: Mapping[str, Any], endpoint_kind: str, obs_to_cluster: Mapping[str, str], entity_lookup: Mapping[tuple[str, str, str], Mapping[str, Any]], registry_by_id: Mapping[str, Mapping[str, Any]], existing_by_pid: Mapping[str, str]) -> str | None:
    pid_key = "subject_person_id" if endpoint_kind == "subject" else "object_person_id"
    provisional_key = "subject_provisional_person_id" if endpoint_kind == "subject" else "object_provisional_person_id"
    pid = str(row.get(pid_key) or "")
    if pid and pid in existing_by_pid:
        return existing_by_pid[pid]
    endpoint = _endpoint_observation(row, entity_lookup, endpoint_kind)
    if endpoint:
        return obs_to_cluster.get(str(endpoint.get("identity_observation_id")))
    provisional = str(row.get(provisional_key) or "")
    if provisional:
        for obs_id, cluster_id in obs_to_cluster.items():
            # Provisional IDs are deterministic observation IDs in the wave
            # projection; use the endpoint's identity observation when it is
            # available rather than surface matching.
            if obs_id == provisional or cluster_id == provisional:
                return cluster_id
    raw_ref = str(row.get(f"{endpoint_kind}_ref") or "")
    if raw_ref.startswith("unresolved:"):
        return obs_to_cluster.get(raw_ref.split(":", 1)[1])
    return None


def _aggregate_facts(waves: Sequence[Mapping[str, Any]], registry: Sequence[Mapping[str, Any]], obs_to_cluster: Mapping[str, str], entity_lookup: Mapping[tuple[str, str, str], Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    registry_by_id = {str(row["candidate_identity_id"]): row for row in registry}
    existing_by_pid = {str(row["resolved_person_id"]): str(row["candidate_identity_id"]) for row in registry if row.get("resolved_person_id")}
    records = _wave_records(waves, "relation_candidates")
    kinship_ids = {str(row.get("candidate_id")) for row in _wave_records(waves, "kinship_candidates")}
    marriage_ids = {str(row.get("candidate_id")) for row in _wave_records(waves, "marriage_candidates")}
    office_ids = {str(row.get("candidate_id")) for row in _wave_records(waves, "office_candidates")}
    facts_by_key: dict[str, dict[str, Any]] = {}
    observations: list[dict[str, Any]] = []
    stats = {
        "w1_blocked_relations_before": 0,
        "w2_blocked_relations_before": 0,
        "w1_blocked_relations_unblocked_by_w2": 0,
        "w2_blocked_relations_unblocked": 0,
        "wave_local_candidate_endpoint_completions": 0,
        "cross_wave_endpoint_completions": 0,
        "duplicate_candidate_facts_collapsed": 0,
        "additional_evidence_links_added": 0,
        "facts_with_multiple_independent_evidence_sources": 0,
    }
    completions: list[dict[str, Any]] = []
    for row in records:
        family = "kinship" if str(row.get("candidate_id")) in kinship_ids else ("marriage" if str(row.get("candidate_id")) in marriage_ids else ("office" if str(row.get("candidate_id")) in office_ids else "relation"))
        subject_cluster = _cluster_for_endpoint(row, "subject", obs_to_cluster, entity_lookup, registry_by_id, existing_by_pid)
        object_cluster = _cluster_for_endpoint(row, "object", obs_to_cluster, entity_lookup, registry_by_id, existing_by_pid)
        before_blocked = str(row.get("novelty")) == "unresolved_endpoint"
        if before_blocked:
            if row.get("wave_id") == "HDB1-W1":
                stats["w1_blocked_relations_before"] += 1
            else:
                stats["w2_blocked_relations_before"] += 1
        subject_status = str((registry_by_id.get(subject_cluster) or {}).get("status") or "")
        object_status = str((registry_by_id.get(object_cluster) or {}).get("status") or "")
        endpoint_complete = bool(subject_cluster and object_cluster and subject_status in {"resolved_existing", "compatible_candidate_cluster"} and object_status in {"resolved_existing", "compatible_candidate_cluster"})
        if before_blocked and endpoint_complete:
            endpoint_observations_by_side: dict[str, list[str]] = {}
            endpoint_support_waves: dict[str, list[str]] = {}
            for side, cluster_id in (("subject", subject_cluster), ("object", object_cluster)):
                observations_for_cluster = list((registry_by_id.get(cluster_id) or {}).get("observation_ids", []))
                endpoint_observations_by_side[side] = observations_for_cluster
                obs_ids = set(observations_for_cluster)
                endpoint_support_waves[side] = sorted({
                    str(obs.get("wave_id"))
                    for obs in _wave_records(waves, "person_candidates")
                    if str(obs.get("identity_observation_id")) in obs_ids
                })

            # A cross-wave completion must be supported on the endpoint that
            # was unresolved in the original wave.  Recurrence of the other
            # endpoint (especially an existing Person) is not identity help
            # for this relation and must not inflate the W2 contribution.
            unresolved_endpoint_sides = [
                side for side in ("subject", "object")
                if not row.get(f"{side}_person_id")
            ]
            cross_wave_sides = [
                side for side in unresolved_endpoint_sides
                if "HDB1-W2" in endpoint_support_waves.get(side, [])
            ]
            endpoint_observations = sorted({
                obs_id
                for side in ("subject", "object")
                for obs_id in endpoint_observations_by_side.get(side, [])
            })
            support_waves = sorted({
                wave_id
                for side in ("subject", "object")
                for wave_id in endpoint_support_waves.get(side, [])
            })
            if row.get("wave_id") == "HDB1-W1" and cross_wave_sides:
                stats["w1_blocked_relations_unblocked_by_w2"] += 1
                stats["cross_wave_endpoint_completions"] += 1
                completions.append(
                    {
                        "completion_id": hdb_stable_id("endpoint-completion", {"candidate_id": row.get("candidate_id"), "support_waves": support_waves}),
                        "original_wave": row.get("wave_id"),
                        "original_observation": row.get("candidate_id"),
                        "new_identity_support": sorted(set(endpoint_observations)),
                        "blocked_endpoint_sides": cross_wave_sides,
                        "support_waves_by_endpoint": endpoint_support_waves,
                        "support_waves": support_waves,
                        "resolution_basis": "independent_identity_evidence",
                        "evidence_refs": [row.get("evidence_ref")],
                        "exact_spans": [row.get("exact_span")],
                    }
                )
            elif row.get("wave_id") == "HDB1-W2":
                stats["w2_blocked_relations_unblocked"] += 1
            elif row.get("wave_id") == "HDB1-W1" and any(
                (registry_by_id.get(cluster_id) or {}).get("status") == "compatible_candidate_cluster"
                for cluster_id in (subject_cluster, object_cluster)
            ):
                stats["wave_local_candidate_endpoint_completions"] += 1

        if not endpoint_complete:
            classification = "unresolved_endpoint"
            fact_key = None
        else:
            semantic = (family, str(row.get("relation_class") or ""), str(row.get("relation_surface") or ""), subject_cluster, object_cluster)
            fact_key = stable_hash(semantic)
            classification = "additional_evidence_for_existing_candidate" if fact_key in facts_by_key else ("reviewed_existing_match" if row.get("novelty") == "existing_reviewed_match" else ("candidate_existing_match" if row.get("novelty") == "existing_candidate_match" else "genuinely_new_candidate"))
        observation = {
            "candidate_observation_id": row.get("candidate_id"),
            "wave_id": row.get("wave_id"),
            "run_id": row.get("run_id"),
            "story_id": row.get("story_id"),
            "family": family,
            "relation_class": row.get("relation_class"),
            "relation_surface": row.get("relation_surface"),
            "subject_cluster_id": subject_cluster,
            "object_cluster_id": object_cluster,
            "evidence_ref": row.get("evidence_ref"),
            "exact_span": row.get("exact_span"),
            "classification": classification,
            "candidate_only": True,
        }
        observations.append(observation)
        if fact_key is not None:
            if fact_key in facts_by_key:
                existing = facts_by_key[fact_key]
                existing["observation_ids"].append(row.get("candidate_id"))
                existing["evidence_refs"].append(row.get("evidence_ref"))
                existing["story_ids"].append(row.get("story_id"))
                stats["duplicate_candidate_facts_collapsed"] += 1
                stats["additional_evidence_links_added"] += 1
            else:
                facts_by_key[fact_key] = {
                    "candidate_fact_id": hdb_stable_id("cross-wave-fact", {"fact_key": fact_key}),
                    "fact_key": fact_key,
                    "family": family,
                    "relation_class": row.get("relation_class"),
                    "relation_surface": row.get("relation_surface"),
                    "subject_cluster_id": subject_cluster,
                    "object_cluster_id": object_cluster,
                    "observation_ids": [row.get("candidate_id")],
                    "evidence_refs": [row.get("evidence_ref")],
                    "story_ids": [row.get("story_id")],
                    "candidate_only": True,
                    "canonical_write_back": False,
                }
    facts = []
    for fact in facts_by_key.values():
        fact["observation_ids"] = sorted(set(fact["observation_ids"]))
        fact["evidence_refs"] = sorted(set(value for value in fact["evidence_refs"] if value))
        fact["story_ids"] = sorted(set(fact["story_ids"]))
        fact["evidence_source_count"] = len(fact["evidence_refs"])
        fact["independent_story_count"] = len(fact["story_ids"])
        if fact["independent_story_count"] >= 2:
            stats["facts_with_multiple_independent_evidence_sources"] += 1
        facts.append(fact)
    return sorted(facts, key=lambda row: row["candidate_fact_id"]), sorted(completions, key=lambda row: row["completion_id"]), stats, observations


def _update_registry_blocks(registry: list[dict[str, Any]], facts: Sequence[Mapping[str, Any]], observations: Sequence[Mapping[str, Any]]) -> None:
    by_id = {str(row["candidate_identity_id"]): row for row in registry}
    for row in observations:
        if row.get("classification") != "unresolved_endpoint":
            continue
        relation = str(row.get("family"))
        for endpoint in (row.get("subject_cluster_id"), row.get("object_cluster_id")):
            record = by_id.get(str(endpoint))
            if not record:
                continue
            record["blocked_relation_count"] += 1
            if relation == "kinship":
                record["blocked_kinship_count"] += 1
            elif relation == "marriage":
                record["blocked_marriage_count"] += 1


def _review_priority(waves: Sequence[Mapping[str, Any]], registry: list[dict[str, Any]], observations: Sequence[Mapping[str, Any]], facts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_cluster = {str(row["candidate_identity_id"]): row for row in registry}
    active: list[dict[str, Any]] = []
    p3_backlog: list[dict[str, Any]] = []
    promotion_reasons: dict[str, list[str]] = collections.defaultdict(list)
    all_items: list[dict[str, Any]] = []
    for wave in waves:
        for item in wave.get("review_queue", []) or []:
            row = dict(item)
            row["wave_id"] = wave.get("wave_id")
            row["run_id"] = wave.get("run_id")
            all_items.append(row)
    obs_by_candidate = {str(row.get("candidate_observation_id")): row for row in observations}
    identity_candidate_to_cluster = {
        str(candidate_id): str(cluster.get("candidate_identity_id"))
        for cluster in registry
        for candidate_id in cluster.get("candidate_ids", [])
    }
    for item in sorted(all_items, key=lambda row: (str(row.get("priority")), str(row.get("review_item_id")))):
        priority = str(item.get("priority") or "P3")
        row = dict(item)
        if priority != "P3":
            row["active"] = True
            row["effective_priority"] = priority
            active.append(row)
            continue
        reasons: list[str] = []
        candidate_id = str(item.get("candidate_id") or "")
        observation = obs_by_candidate.get(candidate_id)
        cluster_ids = []
        if identity_candidate_to_cluster.get(candidate_id):
            cluster_ids.append(identity_candidate_to_cluster[candidate_id])
        if observation:
            cluster_ids = [str(value) for value in (observation.get("subject_cluster_id"), observation.get("object_cluster_id")) if value]
        for cluster_id in cluster_ids:
            cluster = by_cluster.get(cluster_id) or {}
            if len(cluster.get("story_ids", [])) >= 2:
                reasons.append("same_unresolved_identity_in_multiple_stories")
            if int(cluster.get("blocked_relation_count", 0)) >= 2:
                reasons.append("blocks_multiple_relation_candidates")
            if int(cluster.get("blocked_kinship_count", 0)) or int(cluster.get("blocked_marriage_count", 0)):
                reasons.append("blocks_kinship_or_marriage_endpoint")
        if observation and observation.get("wave_id") == "HDB1-W2" and observation.get("classification") != "unresolved_endpoint":
            reasons.append("new_wave_evidence_narrows_identity")
        if reasons:
            row["active"] = True
            row["effective_priority"] = "P2"
            row["promotion_reason"] = sorted(set(reasons))
            active.append(row)
            for reason in reasons:
                promotion_reasons[reason].append(str(item.get("review_item_id")))
        else:
            row["active"] = False
            row["effective_priority"] = "P3"
            p3_backlog.append(row)
    counts = collections.Counter(str(row.get("effective_priority")) for row in active)
    processed_story_ids = {
        str(story.get("story_id"))
        for wave in waves
        for story in (wave.get("selection", {}).get("stories", []) or [])
        if story.get("story_id")
    }
    review_story_ids = {
        str(row.get("story_id"))
        for row in all_items
        if row.get("story_id")
    }
    return {
        "schema": "hdb1-cross-wave-review-priority-v1",
        "stage": CROSS_STAGE,
        "active_review_items": sorted(active, key=lambda row: (str(row.get("effective_priority")), str(row.get("story_id")), str(row.get("review_item_id")))),
        "backlog_items": sorted(p3_backlog, key=lambda row: (str(row.get("story_id")), str(row.get("review_item_id")))),
        "active_priority_counts": {key: counts.get(key, 0) for key in ("P0", "P1", "P2")},
        "active_review_item_count": len(active),
        "backlog_item_count": len(p3_backlog),
        "processed_story_count": len(processed_story_ids),
        "review_story_count": len(review_story_ids),
        "promotion_reasons": {key: sorted(value) for key, value in sorted(promotion_reasons.items())},
        "active_review_items_per_story": len(active) / max(1, len(processed_story_ids)),
        "active_review_items_per_reviewed_story": len(active) / max(1, len(review_story_ids)),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def aggregate(waves: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    registry, obs_to_cluster, observation_by_id, propagation, surface_data = _build_identity_registry(waves)
    entity_lookup: dict[tuple[str, str, str], dict[str, Any]] = {}
    for wave in waves:
        for row in wave.get("person_candidates", []) or []:
            entity_lookup[(str(wave["wave_id"]), str(row.get("unit_id")), str(row.get("entity_key")))] = row
    facts, completions, fact_stats, fact_observations = _aggregate_facts(waves, registry, obs_to_cluster, entity_lookup)
    _update_registry_blocks(registry, facts, fact_observations)
    priority = _review_priority(waves, registry, fact_observations, facts)

    temporal = _wave_records(waves, "temporal_candidates")
    temporal_by_story: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in temporal:
        temporal_by_story[str(row.get("story_id"))].append(row)
    temporal_aggregate = [
        {
            "story_id": story_id,
            "wave_ids": sorted({str(row.get("wave_id")) for row in rows}),
            "candidate_count": len(rows),
            "scene_time_candidate_count": sum(bool(row.get("scene_time_candidate")) for row in rows),
            "contextual_temporal_count": sum(not bool(row.get("scene_time_candidate")) for row in rows),
            "h0a_compatible_count": sum(row.get("h0a_status") == "compatible" for row in rows),
            "h0a_upgrade_candidate_count": sum(bool(row.get("h0a_upgrade_candidate")) for row in rows),
            "later_outcome_count": sum(row.get("temporal_role") == "later_outcome" for row in rows),
            "quoted_background_count": sum(row.get("temporal_role") in {"quoted_precedent", "background_context"} for row in rows),
            "candidate_only": True,
        }
        for story_id, rows in sorted(temporal_by_story.items())
    ]

    person_observations = _wave_records(waves, "person_candidates")
    relation_observations = _wave_records(waves, "relation_candidates")
    all_candidate_observation_count = sum(
        len(_wave_records(waves, key))
        for key in ("person_candidates", "relation_candidates", "kinship_candidates", "marriage_candidates", "office_candidates", "temporal_candidates")
    )
    active = priority["active_review_item_count"]
    metrics = {
        "stage": CROSS_STAGE,
        "wave_ids": [str(wave["wave_id"]) for wave in waves],
        "total_unique_stories_processed_by_hdb1": len({str(row.get("story_id")) for wave in waves for row in wave.get("selection", {}).get("stories", [])}),
        "total_person_observations": len(person_observations),
        "unique_candidate_identity_clusters": len(registry),
        "unresolved_surface_clusters": sum(row.get("status") == "unresolved_surface_cluster" for row in registry),
        "cross_story_candidate_clusters": sum(row.get("status") == "compatible_candidate_cluster" and len(row.get("story_ids", [])) > 1 for row in registry),
        "W1_candidate_observations_reused": sum(len(wave.get(key, [])) for wave in waves if wave.get("wave_id") == "HDB1-W1" for key in ("person_candidates", "relation_candidates", "kinship_candidates", "marriage_candidates", "office_candidates", "temporal_candidates")),
        "W2_candidate_observations_reused": sum(len(wave.get(key, [])) for wave in waves if wave.get("wave_id") == "HDB1-W2" for key in ("person_candidates", "relation_candidates", "kinship_candidates", "marriage_candidates", "office_candidates", "temporal_candidates")),
        "W1_blocked_relations_before": fact_stats["w1_blocked_relations_before"],
        "W1_blocked_relations_unblocked_by_W2": fact_stats["w1_blocked_relations_unblocked_by_w2"],
        "W2_blocked_relations_before": fact_stats["w2_blocked_relations_before"],
        "wave_local_candidate_endpoint_completions": fact_stats["wave_local_candidate_endpoint_completions"],
        "cross_wave_endpoint_completions": fact_stats["cross_wave_endpoint_completions"],
        "facts_with_multiple_independent_evidence_sources": fact_stats["facts_with_multiple_independent_evidence_sources"],
        "duplicate_candidate_facts_collapsed": fact_stats["duplicate_candidate_facts_collapsed"],
        "additional_evidence_links_added": fact_stats["additional_evidence_links_added"],
        "active_review_items": active,
        "backlog_items": priority["backlog_item_count"],
        "P3_promoted": sum(bool(row.get("promotion_reason")) for row in priority["active_review_items"]),
        "active_review_items_per_story": priority["active_review_items_per_story"],
        "all_candidate_observation_count": all_candidate_observation_count,
        "api_calls": 0,
    }
    return {
        "schema": "hdb1-cross-wave-candidate-historical-db-v1",
        "stage": CROSS_STAGE,
        "wave_ids": [str(wave["wave_id"]) for wave in waves],
        "run_ids": [str(wave["run_id"]) for wave in waves],
        "selection_hashes": {str(wave["wave_id"]): wave.get("selection", {}).get("selection_hash") for wave in waves},
        "candidate_only": True,
        "canonical_write_back": False,
        "identity_observations": person_observations,
        "candidate_identity_registry": registry,
        "surface_buckets": surface_data["surface_buckets"],
        "identity_propagations": propagation,
        "relation_observations": relation_observations,
        "candidate_facts": facts,
        "newly_unblocked_relation_candidates": completions,
        "temporal_story_candidates": temporal_aggregate,
        "review_priority": priority,
        "metrics": metrics,
    }


def build_all(w1_run_id: str, w2_run_id: str, *, write: bool = True) -> dict[str, Any]:
    w1 = load_wave_projection("HDB1-W1", w1_run_id)
    w2 = load_wave_projection("HDB1-W2", w2_run_id)
    if write:
        w2["written_paths"] = _write_wave2_projection(w2)
    aggregate_output = aggregate([w1, w2])
    aggregate_output["source_runs"] = {"HDB1-W1": w1_run_id, "HDB1-W2": w2_run_id}
    aggregate_output["selection_hashes"] = {"HDB1-W1": w1["selection"].get("selection_hash"), "HDB1-W2": w2["selection"].get("selection_hash")}
    if write:
        write_json(DERIVED / "hdb1-candidate-identity-registry.json", {"schema": "hdb1-candidate-identity-registry-v1", "stage": CROSS_STAGE, "candidate_only": True, "canonical_write_back": False, "records": aggregate_output["candidate_identity_registry"], "surface_buckets": aggregate_output["surface_buckets"], "identity_propagations": aggregate_output["identity_propagations"]})
        write_json(DERIVED / "hdb1-cross-wave-candidate-historical-db.json", aggregate_output)
        write_json(DERIVED / "hdb1-cross-wave-review-priority.json", aggregate_output["review_priority"])
        write_json(DERIVED / "hdb1-cross-wave-gap-audit.json", {"schema": "hdb1-cross-wave-gap-audit-v1", "stage": CROSS_STAGE, "candidate_only": True, "canonical_write_back": False, "unresolved_surface_clusters": [row for row in aggregate_output["candidate_identity_registry"] if row.get("status") in {"unresolved_surface_cluster", "conflicted"}], "newly_unblocked_relation_candidates": aggregate_output["newly_unblocked_relation_candidates"], "temporal_story_candidates": aggregate_output["temporal_story_candidates"]})
    return {"wave1": w1, "wave2": w2, "aggregate": aggregate_output}


def deterministic_check(w1_run_id: str, w2_run_id: str) -> dict[str, Any]:
    first = build_all(w1_run_id, w2_run_id, write=False)
    second = build_all(w1_run_id, w2_run_id, write=False)
    first_hash = stable_hash(first["aggregate"])
    second_hash = stable_hash(second["aggregate"])
    return {"equal": first_hash == second_hash, "first_hash": first_hash, "second_hash": second_hash, "api_calls": 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--w1-run-id", default=None)
    parser.add_argument("--w2-run-id", default=None)
    parser.add_argument("--check-determinism", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    w1_run_id = args.w1_run_id or _latest_complete_run(W1_ROOT)
    w2_run_id = args.w2_run_id or _latest_complete_run(W2_ROOT)
    if args.check_determinism:
        result = deterministic_check(w1_run_id, w2_run_id)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        if args.no_write:
            return 0 if result["equal"] else 1
    result = build_all(w1_run_id, w2_run_id, write=not args.no_write)
    print(json.dumps({"w1_run_id": w1_run_id, "w2_run_id": w2_run_id, "metrics": result["aggregate"]["metrics"], "written_paths": result["wave2"].get("written_paths", {})}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
