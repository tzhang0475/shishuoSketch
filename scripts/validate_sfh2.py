#!/usr/bin/env python3
"""Validate SFH2/HIR1 invariants and frozen SFH1 input hashes."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from sfh2.common import INPUT_FILES, OUTPUT_ROOT, file_hash, normalize_form, read_json, text, stable_hash  # noqa: E402
from sfh2.inputs import freeze_input_manifest, load_documents  # noqa: E402


def _errors() -> list[str]:
    errors: list[str] = []
    required = [
        "input-manifest.json", "candidate-observations.json", "existing-person-link-candidates.json",
        "existing-person-link-results.json", "candidate-blocking.json", "candidate-pair-judgments.json",
        "candidate-clusters.json", "cluster-validation.json", "entity-consolidation.json",
        "relation-endpoint-reprojection.json", "consolidated-graph.json", "growth-series.json",
        "fragmentation-analysis.json", "human-audit-sample.json", "cost-metrics.json",
        "failure-attribution.json", "prior-candidate-dedup-audit.json", "metrics.json",
        "hda2-suppression-audit.json", "kinship-projection.json",
        "marriage-projection.json", "office-projection.json",
    ]
    for name in required:
        if not (OUTPUT_ROOT / name).is_file():
            errors.append(f"missing_artifact:{name}")
    if errors:
        return errors
    manifest = read_json(OUTPUT_ROOT / "input-manifest.json", {}) or {}
    try:
        expected_manifest = freeze_input_manifest()
    except Exception as exc:
        return [f"input_manifest_error:{type(exc).__name__}:{exc}"]
    if manifest != expected_manifest:
        errors.append("input_manifest_drift")
    for path, expected in (manifest.get("source_hashes") or {}).items():
        actual_path = ROOT / path
        if not actual_path.is_file() or file_hash(actual_path) != expected:
            errors.append(f"sfh1_input_hash_drift:{path}")
    documents = load_documents()
    obs = read_json(OUTPUT_ROOT / "candidate-observations.json", {}) or {}
    links = read_json(OUTPUT_ROOT / "existing-person-link-results.json", {}) or {}
    blocking = read_json(OUTPUT_ROOT / "candidate-blocking.json", {}) or {}
    pairs = read_json(OUTPUT_ROOT / "candidate-pair-judgments.json", {}) or {}
    consolidation = read_json(OUTPUT_ROOT / "entity-consolidation.json", {}) or {}
    relation = read_json(OUTPUT_ROOT / "relation-endpoint-reprojection.json", {}) or {}
    graph = read_json(OUTPUT_ROOT / "consolidated-graph.json", {}) or {}
    metrics = read_json(OUTPUT_ROOT / "metrics.json", {}) or {}
    for name, document in (("observations", obs), ("links", links), ("blocking", blocking), ("pairs", pairs), ("consolidation", consolidation), ("relation", relation), ("graph", graph), ("metrics", metrics)):
        if document.get("candidate_only") is not True or document.get("canonical_write_back") is not False:
            errors.append(f"storage_flags_invalid:{name}")
    people = {text(row.get("person_id")) for row in (documents.get("people") or {}).get("people", []) or [] if isinstance(row, Mapping)}
    for row in consolidation.get("observation_entities", []) or []:
        if text(row.get("entity_type")) == "production_person" and text(row.get("entity_id")) not in people:
            errors.append(f"invalid_production_person:{row.get('entity_id')}")
        if text(row.get("entity_type")) == "production_person" and text(row.get("entity_id")).startswith("hdb2-candidate-person-"):
            errors.append("candidate_person_as_production_person")
    obs_ids = {text(row.get("observation_id")) for row in obs.get("records", []) or []}
    mention_ids = {text(row.get("mention_id")) for row in obs.get("records", []) or []}
    entity_by_obs = {text(row.get("observation_id")): row for row in consolidation.get("observation_entities", []) or []}
    if obs_ids != set(entity_by_obs):
        errors.append("observation_entity_coverage_drift")
    explicit_distinct = {tuple(sorted((text(row.get("left")), text(row.get("right"))))) for row in blocking.get("explicit_distinct_pairs", []) or []}
    for cluster in consolidation.get("candidate_clusters", []) or []:
        members = sorted(text(value) for value in cluster.get("member_observation_ids", []) if text(value))
        for index, left in enumerate(members):
            for right in members[index + 1:]:
                if (left, right) in explicit_distinct:
                    errors.append(f"cluster_contains_distinct:{cluster.get('cluster_id')}")
    valid_endpoint_ids = {text(row.get("entity_id")) for row in entity_by_obs.values() if text(row.get("entity_id"))}
    for row in relation.get("records", []) or []:
        for key in ("subject_endpoint", "object_endpoint"):
            value = text(row.get(key))
            if value and value not in valid_endpoint_ids:
                errors.append(f"relation_endpoint_not_consolidated:{row.get('relation_id')}:{key}")
        if text(row.get("subject_endpoint")) and text(row.get("subject_endpoint")) == text(row.get("object_endpoint")) and text(row.get("relation_type")) != "other":
            errors.append(f"surviving_self_relation:{row.get('relation_id')}")
    suppressed_rows = documents.get("hda2_overlay") or []
    suppressed = {(normalize_form(row.get("target_surface")), text(row.get("person_id"))) for row in (suppressed_rows if isinstance(suppressed_rows, list) else suppressed_rows.get("records", []) or []) if isinstance(row, Mapping) and text(row.get("action")) == "suppress_claim"}
    for row in (read_json(OUTPUT_ROOT / "existing-person-link-candidates.json", {}) or {}).get("records", []) or []:
        surface = normalize_form(row.get("surface"))
        for candidate in row.get("candidates", []) or []:
            if (surface, text(candidate.get("person_id"))) in suppressed:
                errors.append(f"suppressed_hda2_reintroduced:{row.get('observation_id')}:{candidate.get('person_id')}")
    if int(metrics.get("forbidden_identity_merge_count") or 0):
        errors.append("forbidden_identity_merge")
    if int(metrics.get("suppressed_hda2_claim_reentry_count") or 0):
        errors.append("suppressed_claim_reentry")
    if int((read_json(OUTPUT_ROOT / "cluster-validation.json", {}) or {}).get("violation_count") or 0):
        errors.append("cluster_validation_failure")
    if int(metrics.get("original_sfh1_candidate_person_ids") or 0) != 542:
        errors.append(f"source_candidate_count_not_542:{metrics.get('original_sfh1_candidate_person_ids')}")
    if len(obs.get("records", []) or []) != 3303:
        errors.append(f"sfh1_observation_count_drift:{len(obs.get('records', []) or [])}")
    if int(obs.get("candidate_observation_count") or 0) != 597:
        errors.append(f"candidate_observation_count_drift:{obs.get('candidate_observation_count')}")
    if int(obs.get("entity_resolution_candidate_observation_count") or 0) != 594:
        errors.append(f"eligible_candidate_observation_count_drift:{obs.get('entity_resolution_candidate_observation_count')}")
    if len(relation.get("records", []) or []) + len(relation.get("rejected", []) or []) != 2219:
        errors.append("relation_coverage_drift")
    if graph.get("summary", {}).get("node_count") != len(graph.get("nodes", []) or []):
        errors.append("graph_node_summary_drift")
    for row in graph.get("nodes", []) or []:
        if text(row.get("node_type")) == "CandidatePerson" and text(row.get("node_id")).startswith("person-"):
            errors.append("candidate_node_uses_production_prefix")
    growth = read_json(OUTPUT_ROOT / "growth-series.json", {}) or {}
    if [text(row.get("wave")) for row in growth.get("series", []) or []] != ["baseline", "HGE1-WA-SFH2", "HGE1-WB-SFH2"]:
        errors.append("growth_series_wave_contract_drift")
    if [text(row.get("wave")) for row in growth.get("sfh1_reference_series", []) or []] != ["baseline", "HGE1-WA-SFH1", "HGE1-WB-SFH1"]:
        errors.append("sfh1_reference_series_drift")
    if growth.get("candidate_observation_is_not_person_metric") is not True:
        errors.append("candidate_observation_person_metric_boundary_missing")
    return sorted(set(errors))


def validate() -> list[str]:
    return _errors()


def main() -> int:
    errors = validate()
    print(json.dumps({"status": "ok" if not errors else "failed", "errors": errors}, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
