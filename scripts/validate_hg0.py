#!/usr/bin/env python3
"""Validate HG0 graph ontology, projection, audits, and H0C protection."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from build_hg0_historical_graph import INPUTS, OUTPUTS, interval_overlaps, node_key, read_json, sha256_file


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = Path("schema/hg0-historical-graph.schema.json")


def validate_schema(value: Any, label: str) -> list[str]:
    schema = read_json(SCHEMA_PATH)
    return [f"{label}: {error.message} at {'/'.join(str(part) for part in error.absolute_path)}" for error in Draft202012Validator(schema).iter_errors(value)]


def load() -> dict[str, Any]:
    return {name: read_json(path) for name, path in OUTPUTS.items()}


def validate() -> list[str]:
    out = load()
    errors: list[str] = []
    for name, document in out.items():
        errors.extend(validate_schema(document, name))

    ontology = out["ontology"]
    universe = out["universe"]
    graph = out["graph"]
    temporal = out["temporal"]
    audit = out["graph_audit"]
    sufficiency = out["sufficiency"]
    ml_contract = out["ml_contract"]
    protection = out["protection"]
    inputs = {name: read_json(path) for name, path in INPUTS.items()}
    fact_index = records(inputs["h0c_facts"], "fact_index")
    fact_keys = {str(row["fact_key"]) for row in fact_index}

    if protection.get("baseline_h0c_commit") != "4854d3d1997300c9039d8093c0c7114cb00c47d1":
        errors.append("HG0 protection baseline is not the frozen H0C commit")
    for name, path in INPUTS.items():
        if name.startswith("h0c_") and protection.get("h0c_input_hashes", {}).get(name) != sha256_file(path):
            errors.append(f"H0C protected input hash changed: {name}")
    if protection.get("h0c_protection_manifest_sha256") != sha256_file(INPUTS["h0c_protection"]):
        errors.append("H0C protection manifest hash does not match current input")
    if protection.get("participant_freeze_sha256") != inputs["h0c_participants"].get("participant_freeze_sha256"):
        errors.append("H0C participant freeze semantic hash changed")
    if protection.get("entity_id_manifest_sha256") != sha256_file(INPUTS["h0c_entity_manifest"]):
        errors.append("H0C entity ID manifest changed")

    h0c_nodes = inputs["h0c_graph"].get("nodes", [])
    h0c_base = {(str(node["node_type"]), str(node["node_id"])) for node in h0c_nodes}
    graph_base = {(str(node["node_type"]), str(node["node_id"])) for node in graph["nodes"] if not node.get("reified_fact_node")}
    if h0c_base != graph_base:
        errors.append("HG0 canonical entity node universe differs from H0C")
    if len([node for node in graph["nodes"] if node.get("node_type") == "Person" and not node.get("reified_fact_node")]) != 75:
        errors.append("HG0 does not contain exactly 75 canonical Person nodes")
    if len([node for node in graph["nodes"] if node.get("node_type") == "Story" and not node.get("reified_fact_node")]) != 143:
        errors.append("HG0 does not contain exactly 143 canonical Story nodes")

    universe_counts = universe.get("protected_counts", {})
    expected_counts = {"production_persons": 75, "published_stories": 143, "global_person_story_links": 875, "published_person_story_links": 330, "excluded_person_story_links": 545}
    for key, expected in expected_counts.items():
        if universe_counts.get(key) != expected:
            errors.append(f"HG0 universe protected count {key}={universe_counts.get(key)!r}, expected {expected}")
    boundary = next((scope for scope in universe.get("scopes", []) if scope.get("scope_id") == "global_person_story_index_boundary"), {})
    if boundary.get("outside_story_id_count") != 417:
        errors.append("HG0 global PersonStory boundary story count changed")
    if boundary.get("story_node_count") != 0 or boundary.get("status") != "boundary_only_not_materialized":
        errors.append("HG0 incorrectly materializes the wider PersonStory boundary as Story nodes")

    ontology_node_types = {str(row["node_type"]) for row in ontology.get("node_types", [])}
    ontology_edges = {str(row["edge_type"]): row for row in ontology.get("edge_types", [])}
    ontology_layers = {str(row["layer"]) for row in ontology.get("layers", [])}
    graph_node_types = {str(row["node_type"]) for row in graph.get("nodes", [])}
    graph_edge_types = {str(row["edge_type"]) for row in graph.get("edges", [])}
    if not graph_node_types <= ontology_node_types:
        errors.append("HG0 graph contains node type missing from ontology")
    if not graph_edge_types <= set(ontology_edges):
        errors.append("HG0 graph contains edge type missing from ontology")

    node_keys = {(str(node["node_type"]), str(node["node_id"])) for node in graph.get("nodes", [])}
    if len(node_keys) != len(graph.get("nodes", [])):
        errors.append("HG0 node IDs are not unique within node type")
    seen_edge_ids: set[str] = set()
    seen_semantic_keys: set[str] = set()
    temporal_by_edge = {str(row["edge_id"]): row for row in temporal.get("edge_temporal_index", [])}
    if len(temporal_by_edge) != len(graph.get("edges", [])):
        errors.append("HG0 temporal index does not contain exactly one row per graph edge")
    for edge in graph.get("edges", []):
        edge_id = str(edge["edge_id"])
        if edge_id in seen_edge_ids:
            errors.append(f"duplicate edge ID {edge_id}")
        seen_edge_ids.add(edge_id)
        semantic_key = str(edge.get("semantic_key"))
        if semantic_key in seen_semantic_keys:
            errors.append(f"duplicate semantic edge {semantic_key}")
        seen_semantic_keys.add(semantic_key)
        source = (str(edge["source"]["node_type"]), str(edge["source"]["node_id"]))
        target = (str(edge["target"]["node_type"]), str(edge["target"]["node_id"]))
        if source not in node_keys or target not in node_keys:
            errors.append(f"dangling HG0 edge {edge_id}")
        if edge["graph_layer"] not in ontology_layers:
            errors.append(f"edge {edge_id} has unknown graph layer {edge['graph_layer']}")
        if edge["graph_layer"] not in edge.get("layer_memberships", []):
            errors.append(f"edge {edge_id} does not include its primary layer")
        for ref in edge.get("source_facts", []):
            if str(ref.get("fact_key")) not in fact_keys:
                errors.append(f"edge {edge_id} has dangling fact reference {ref.get('fact_key')}")
        if not edge.get("source_facts") or (not edge.get("evidence_ids") and not edge.get("provenance_refs")):
            errors.append(f"edge {edge_id} lacks fact/evidence traceability")
        temporal_row = temporal_by_edge.get(edge_id)
        if temporal_row and temporal_row.get("temporal_state") != edge.get("temporal", {}).get("temporal_state"):
            errors.append(f"edge {edge_id} temporal projection disagrees with graph")
        start = edge.get("temporal", {}).get("start_year_ce")
        end = edge.get("temporal", {}).get("end_year_ce")
        if start is not None and end is not None and int(start) > int(end):
            errors.append(f"edge {edge_id} has inverted temporal interval")
        if edge.get("projection_role") == "reified_support":
            if not any(node_type in {"OfficeTenure", "PersonActivity", "EventParticipation", "ServicePoliticalFact"} for node_type in (source[0], target[0])):
                errors.append(f"edge {edge_id} is marked reified_support without a reified endpoint")
    for node in graph.get("nodes", []):
        if node.get("reified_fact_node"):
            if str(node.get("source_fact", {}).get("fact_key")) not in fact_keys:
                errors.append(f"reified node {node['node_id']} has dangling source fact")
            if not node.get("evidence_ids"):
                errors.append(f"reified node {node['node_id']} lacks evidence")

    for name in ["dangling_edges", "dangling_fact_references", "unsupported_edges", "duplicate_edge_ids", "duplicate_semantic_edges", "symmetric_reverse_duplicates", "invalid_edge_types", "invalid_node_types", "invalid_temporal_intervals", "ontology_endpoint_conflicts", "unsupported_nodes"]:
        if audit.get("issue_counts", {}).get(name, 0):
            errors.append(f"HG0 graph audit has {audit['issue_counts'][name]} {name}")
    if audit.get("issue_counts", {}).get("family_cycle_anomalies", 0):
        errors.append("HG0 graph contains a family cycle")

    if not ml_contract.get("framework_neutral"):
        errors.append("HG0 ML0 contract is not framework-neutral")
    for field in ["model_artifacts_generated", "embeddings_generated", "training_split_generated"]:
        if ml_contract.get(field):
            errors.append(f"HG0 unexpectedly generated {field}")
    missingness = ml_contract.get("missingness_contract", {})
    if missingness.get("missing_edge_is_negative") or missingness.get("negative_facts_generated"):
        errors.append("HG0 violates missing-edge/negative-fact semantics")
    if sufficiency.get("layers", {}).get("combined", {}).get("classification") not in {"strong", "usable", "pilot_only", "insufficient"}:
        errors.append("HG0 combined sufficiency classification is invalid")

    return errors


def records(document: Mapping[str, Any], key: str = "records") -> list[dict[str, Any]]:
    value = document.get(key, [])
    return [dict(item) for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    graph = read_json(OUTPUTS["graph"])
    sufficiency = read_json(OUTPUTS["sufficiency"])
    print(
        "HG0 validation passed: "
        f"{len(graph['nodes'])} nodes, {len(graph['edges'])} edges, "
        f"combined={sufficiency['layers']['combined']['classification']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
