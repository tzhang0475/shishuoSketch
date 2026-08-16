#!/usr/bin/env python3
"""Validate ML0's disposable datasets and experiment contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_ml0_pilot import (
    EXTERNAL_LAYERS,
    HG0_INPUTS,
    OUTPUTS,
    PRIMARY_VIEWS,
    ABLATION_LAYERS,
    REVIEWED_PLUS_CANDIDATE_STATES,
    REVIEWED_STATES,
    TEMPORAL_BOUNDED_STATES,
    sha256_file,
)


def load_output(key: str) -> dict[str, Any]:
    return json.loads((ROOT / OUTPUTS[key]).read_text(encoding="utf-8"))


def fail(message: str) -> None:
    raise AssertionError(message)


def validate() -> dict[str, Any]:
    dataset = load_output("dataset")
    experiments = load_output("experiments")
    baselines = load_output("baselines")
    gnn = load_output("gnn")
    ablations = load_output("ablations")
    temporal = load_output("temporal")
    link = load_output("link")
    metrics = load_output("metrics")
    protection = load_output("protection")
    hg0 = json.loads((ROOT / HG0_INPUTS["graph"]).read_text(encoding="utf-8"))
    ontology = json.loads((ROOT / HG0_INPUTS["ontology"]).read_text(encoding="utf-8"))
    nodes = {(str(row["node_type"]), str(row["node_id"])) for row in hg0["nodes"]}
    edges = {str(row["edge_id"]): row for row in hg0["edges"]}
    node_type_names = {str(row["node_type"]) for row in ontology["node_types"]}
    edge_type_names = {str(row["edge_type"]) for row in ontology["edge_types"]}

    if dataset.get("stage") != "ml0-dataset-manifest":
        fail("invalid ML0 dataset stage")
    if dataset.get("research_only") is not True:
        fail("ML0 dataset is not marked research-only")
    for name, relative in HG0_INPUTS.items():
        expected = protection.get("hg0_input_hashes", {}).get(name)
        if expected is None or sha256_file(relative) != expected:
            fail(f"HG0 protected input changed: {name}")
    if dataset.get("source_graph", {}).get("hg0_graph_sha256") != sha256_file(HG0_INPUTS["graph"]):
        fail("dataset source graph hash does not match HG0")

    mapping = dataset.get("mapping", {})
    node_rows = mapping.get("nodes", [])
    if [row.get("ml_index") for row in node_rows] != list(range(len(node_rows))):
        fail("node indices are not contiguous and deterministic")
    if len(node_rows) != len(nodes):
        fail("ML node universe does not match HG0")
    if len({(row.get("node_type"), row.get("node_id")) for row in node_rows}) != len(node_rows):
        fail("duplicate ML node mapping")
    if any((str(row.get("node_type")), str(row.get("node_id"))) not in nodes for row in node_rows):
        fail("ML node does not resolve to HG0")
    if set(mapping.get("node_type_index", {})) != node_type_names:
        fail("node type mapping does not cover HG0 ontology")
    if not set(mapping.get("edge_type_index", {})) <= edge_type_names:
        fail("unknown edge type in ML mapping")

    feature_names = [str(row.get("name")) for row in dataset.get("feature_policy", {}).get("schema", [])]
    forbidden_feature_tokens = ("node_id", "canonical_reference", "label", "name")
    if any(any(token in name.lower() for token in forbidden_feature_tokens) for name in feature_names):
        fail("canonical labels or IDs were exposed as ML feature columns")

    expected_views = set(PRIMARY_VIEWS) | {f"G_all_minus_{layer}" for layer in ABLATION_LAYERS}
    view_rows = {str(row["view_id"]): row for row in dataset.get("views", [])}
    if set(view_rows) != expected_views:
        fail("ML dataset view set is incomplete")
    for view_id, view in view_rows.items():
        encoded = view.get("encoded_edges", [])
        if view.get("node_count") != len(node_rows) or view.get("edge_count") != len(encoded):
            fail(f"view count mismatch: {view_id}")
        if len({row.get("edge_id") for row in encoded}) != len(encoded):
            fail(f"duplicate edge in view: {view_id}")
        for row in encoded:
            edge_id = str(row.get("edge_id"))
            if edge_id not in edges:
                fail(f"view edge does not resolve to HG0: {edge_id}")
            original = edges[edge_id]
            source = int(row.get("source_index"))
            target = int(row.get("target_index"))
            if source < 0 or target < 0 or source >= len(node_rows) or target >= len(node_rows):
                fail(f"dangling ML edge index in {view_id}")
            expected_source = (str(original["source"]["node_type"]), str(original["source"]["node_id"]))
            expected_target = (str(original["target"]["node_type"]), str(original["target"]["node_id"]))
            if (node_rows[source]["node_type"], node_rows[source]["node_id"]) != expected_source:
                fail(f"source mapping mismatch in {view_id}: {edge_id}")
            if (node_rows[target]["node_type"], node_rows[target]["node_id"]) != expected_target:
                fail(f"target mapping mismatch in {view_id}: {edge_id}")
            if int(row.get("edge_type_index")) != int(mapping["edge_type_index"][str(original["edge_type"])]):
                fail(f"edge type mapping mismatch in {view_id}: {edge_id}")
        resolved = [edges[str(row["edge_id"])] for row in encoded]
        if view_id == "G_story":
            if any("story" not in set(row.get("layer_memberships", [])) for row in resolved):
                fail("G_story contains an edge without the story layer")
        if view_id == "G_external":
            if any(
                not (set(row.get("layer_memberships", [])) & EXTERNAL_LAYERS)
                or "story" in row.get("layer_memberships", [])
                or row["source"]["node_type"] == "Story"
                or row["target"]["node_type"] == "Story"
                for row in resolved
            ):
                fail("G_external contains Story/textual structure")
        if view_id == "G_reviewed" and any(row.get("review_status") not in REVIEWED_STATES for row in resolved):
            fail("G_reviewed contains a non-reviewed assertion")
        if view_id == "G_reviewed_plus_candidate" and any(row.get("review_status") not in REVIEWED_PLUS_CANDIDATE_STATES for row in resolved):
            fail("G_reviewed_plus_candidate contains an unsupported review state")
        if view_id == "G_temporal_bounded" and any((row.get("temporal") or {}).get("temporal_state") not in TEMPORAL_BOUNDED_STATES for row in resolved):
            fail("G_temporal_bounded contains an unbounded edge")
        if view_id.startswith("G_all_minus_"):
            removed_layer = view_id.removeprefix("G_all_minus_")
            if any(removed_layer in set(row.get("layer_memberships", [])) for row in resolved):
                fail(f"ablation failed to remove {removed_layer}")

    split = link.get("split", {})
    train_ids = set(split.get("train_edge_ids", []))
    test_ids = set(split.get("test_edge_ids", []))
    if not train_ids or not test_ids or train_ids & test_ids:
        fail("invalid ML-only link split")
    if any(edge_id not in edges or edges[edge_id].get("edge_type") != "person_story_link" for edge_id in train_ids | test_ids):
        fail("link split contains a non-target or dangling edge")

    if metrics.get("negative_facts_generated") is not False or protection.get("canonical_negative_facts_generated") is not False:
        fail("ML0 claims canonical negative facts were generated")
    if metrics.get("write_back_to_historical_facts") is not False or protection.get("embeddings_persisted") is not False:
        fail("ML0 write-back or persisted model artifact policy is invalid")
    if temporal.get("leakage_checks", {}).get("unknown_excluded_from_pre") is not True:
        fail("temporal unknown bucket leaked into pre-cutoff view")
    if temporal.get("leakage_checks", {}).get("pre_max_end_respects_cutoff") is not True:
        fail("temporal pre-cutoff interval check failed")

    if gnn.get("stage") != "ml0-gnn-results" or not gnn.get("views"):
        fail("GNN pilot results are missing")
    if any(row.get("completed_count", 0) == 0 for row in gnn.get("views", [])):
        fail("a configured GNN view has no completed seed")
    if len(ablations.get("results", [])) != len(ABLATION_LAYERS):
        fail("layer ablation result set incomplete")
    if experiments.get("task", {}).get("negative_policy", "").find("no canonical negative") < 0:
        fail("experiment manifest lacks negative-sampling policy")
    if len(baselines.get("results", [])) != len(PRIMARY_VIEWS) * 3:
        fail("structural baseline matrix incomplete")

    return {
        "status": "ok",
        "hg0_hashes_verified": len(HG0_INPUTS),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "view_count": len(view_rows),
        "gnn_views": len(gnn.get("views", [])),
        "ablation_count": len(ablations.get("results", [])),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(validate(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
