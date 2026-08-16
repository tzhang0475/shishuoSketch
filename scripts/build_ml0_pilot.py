#!/usr/bin/env python3
"""Build the ML0 research projection and bias-controlled learning pilot.

ML0 is deliberately downstream of HG0.  This module reads the frozen HG0
graph, creates deterministic disposable dataset views, runs transparent
structural baselines and a small NumPy R-GCN-style message-passing pilot, and
emits research diagnostics.  It never writes to canonical historical data or
HG0 inputs.

The NumPy model is used because the repository execution environment does not
ship PyTorch/PyG.  It is a relation-aware two-layer message-passing model,
implemented only for this small pilot.  A future environment may replace it
with PyTorch without changing the dataset contract.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
import platform
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping

try:  # ML0 is optional for the normal historical-data pipeline.
    import numpy as np
except ImportError:  # pragma: no cover - exercised only in minimal installs.
    np = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[1]

HG0_INPUTS = {
    "ontology": Path("data/derived/hg0-ontology.json"),
    "universe": Path("data/derived/hg0-graph-universe.json"),
    "graph": Path("data/derived/hg0-graph-projection.json"),
    "temporal": Path("data/derived/hg0-temporal-projection.json"),
    "graph_audit": Path("data/derived/hg0-graph-audit.json"),
    "sufficiency": Path("data/derived/hg0-sufficiency-audit.json"),
    "bias": Path("data/derived/hg0-bias-audit.json"),
    "gaps": Path("data/derived/hg0-gap-audit.json"),
    "ml_contract": Path("data/derived/hg0-ml0-readiness.json"),
    "protection": Path("data/derived/hg0-protection-manifest.json"),
    "metrics": Path("data/derived/hg0-metrics.json"),
}

OUTPUTS = {
    "dataset": Path("data/derived/ml0-dataset-manifest.json"),
    "experiments": Path("data/derived/ml0-experiment-manifest.json"),
    "baselines": Path("data/derived/ml0-baseline-results.json"),
    "gnn": Path("data/derived/ml0-gnn-results.json"),
    "ablations": Path("data/derived/ml0-ablation-results.json"),
    "bias": Path("data/derived/ml0-bias-diagnostic.json"),
    "temporal": Path("data/derived/ml0-temporal-feasibility.json"),
    "link": Path("data/derived/ml0-link-feasibility.json"),
    "expansion": Path("data/derived/ml0-expansion-recommendation.json"),
    "metrics": Path("data/derived/ml0-metrics.json"),
    "protection": Path("data/derived/ml0-protection-manifest.json"),
}

ML0_SCHEMA = 1
SPLIT_SEED = 20260816
PRIMARY_SEEDS = (17, 29, 43, 61, 73)
SECONDARY_SEEDS = (17, 29, 43)
HIDDEN_DIM = 16
EPOCHS = 60
LEARNING_RATE = 0.01
TRAIN_NEGATIVES = 2
TEST_NEGATIVES = 10

PRIMARY_VIEWS = (
    "G_story",
    "G_external",
    "G_all",
    "G_reviewed",
    "G_reviewed_plus_candidate",
    "G_temporal_bounded",
)
ABLATION_LAYERS = (
    "family",
    "clan",
    "office",
    "event",
    "geographic",
    "service_political",
)
EXTERNAL_LAYERS = {
    "family",
    "clan",
    "office",
    "event",
    "geographic",
    "service_political",
    "social_context",
}
TEMPORAL_BOUNDED_STATES = {"bounded", "one_sided"}
REVIEWED_STATES = {"reviewed"}
REVIEWED_PLUS_CANDIDATE_STATES = {"reviewed", "candidate"}


def read_json(relative: Path) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def write_json(relative: Path, value: Any) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def sha256_file(relative: Path) -> str:
    digest = hashlib.sha256()
    with (ROOT / relative).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_value(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stable_sort_key(value: object) -> str:
    return str(value)


def finite_float(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def finite_mean(values: Iterable[float | None]) -> float | None:
    usable = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return finite_float(sum(usable) / len(usable)) if usable else None


def finite_std(values: Iterable[float | None]) -> float | None:
    usable = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not usable:
        return None
    mean = sum(usable) / len(usable)
    return finite_float(math.sqrt(sum((value - mean) ** 2 for value in usable) / len(usable)))


def node_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return str(row["node_type"]), str(row["node_id"])


def endpoint_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return str(row["node_type"]), str(row["node_id"])


def edge_pair(edge: Mapping[str, Any]) -> tuple[int, int]:
    return int(edge["source_index"]), int(edge["target_index"])


def load_hg0() -> dict[str, Any]:
    documents = {name: read_json(path) for name, path in HG0_INPUTS.items()}
    graph = documents["graph"]
    nodes = sorted((dict(row) for row in graph.get("nodes", [])), key=node_key)
    edges = sorted(
        (dict(row) for row in graph.get("edges", [])),
        key=lambda row: (str(row.get("edge_id", "")), str(row.get("semantic_key", ""))),
    )
    node_index = {f"{row['node_type']}:{row['node_id']}": index for index, row in enumerate(nodes)}
    for edge in edges:
        source = f"{edge['source']['node_type']}:{edge['source']['node_id']}"
        target = f"{edge['target']['node_type']}:{edge['target']['node_id']}"
        if source not in node_index or target not in node_index:
            raise ValueError(f"HG0 edge endpoint missing from node index: {edge['edge_id']}")
        edge["source_index"] = node_index[source]
        edge["target_index"] = node_index[target]
    documents["nodes"] = nodes
    documents["edges"] = edges
    documents["node_index"] = node_index
    return documents


def edge_review_status(edge: Mapping[str, Any]) -> str:
    return str(edge.get("review_status") or "unknown")


def edge_temporal_state(edge: Mapping[str, Any]) -> str:
    temporal = edge.get("temporal") or {}
    return str(temporal.get("temporal_state") or "unknown")


def edge_layers(edge: Mapping[str, Any]) -> set[str]:
    return {str(value) for value in edge.get("layer_memberships", [])}


def keep_for_view(edge: Mapping[str, Any], view_id: str) -> bool:
    layers = edge_layers(edge)
    if view_id == "G_all":
        return True
    if view_id == "G_story":
        return "story" in layers
    if view_id == "G_external":
        # External means a non-textual historical layer.  Story-labelled
        # context edges are excluded even if they also carry event/temporal
        # metadata; this prevents textual structure being smuggled into the
        # external comparison.  Story endpoints are excluded as well: an
        # Event→Story or ServiceContext→Story edge is still a textual-context
        # bridge for a PersonStory task, not an independent Person-side
        # historical layer.
        source_type = str(edge.get("source", {}).get("node_type") or "")
        target_type = str(edge.get("target", {}).get("node_type") or "")
        return bool(layers & EXTERNAL_LAYERS) and "story" not in layers and source_type != "Story" and target_type != "Story"
    if view_id == "G_reviewed":
        return edge_review_status(edge) in REVIEWED_STATES
    if view_id == "G_reviewed_plus_candidate":
        return edge_review_status(edge) in REVIEWED_PLUS_CANDIDATE_STATES
    if view_id == "G_temporal_bounded":
        return edge_temporal_state(edge) in TEMPORAL_BOUNDED_STATES
    if view_id.startswith("G_all_minus_"):
        return view_id.removeprefix("G_all_minus_") not in layers
    raise ValueError(f"Unknown ML0 graph view: {view_id}")


def view_definition(view_id: str) -> str:
    definitions = {
        "G_all": "All HG0 edges in the protected published-story graph scope.",
        "G_story": "Edges carrying the HG0 story layer; this is textual/participation structure, not a generic social tie.",
        "G_external": "Edges carrying a non-textual historical layer, no story-layer membership, and no Story endpoint; no synthetic co-occurrence compensation.",
        "G_reviewed": "All HG0 edges whose review_status is reviewed; omission is not a negative fact.",
        "G_reviewed_plus_candidate": "Edges with review_status reviewed or candidate; epistemic state remains attached.",
        "G_temporal_bounded": "Edges with bounded or one-sided HG0 temporal state; unknown and relative facts stay in a separate bucket.",
    }
    if view_id in definitions:
        return definitions[view_id]
    if view_id.startswith("G_all_minus_"):
        layer = view_id.removeprefix("G_all_minus_")
        return f"G_all with HG0 layer {layer} removed; independent other layers remain multiplex edges."
    raise ValueError(view_id)


def encode_edges(edges: list[dict[str, Any]], edge_type_index: Mapping[str, int]) -> list[dict[str, Any]]:
    return [
        {
            "edge_id": str(edge["edge_id"]),
            "source_index": int(edge["source_index"]),
            "target_index": int(edge["target_index"]),
            "edge_type_index": int(edge_type_index[str(edge["edge_type"])]),
        }
        for edge in edges
    ]


def make_feature_schema(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    node_types = sorted({str(node["node_type"]) for node in nodes})
    layers = sorted({layer for edge in edges for layer in edge_layers(edge)})
    edge_types = sorted({str(edge["edge_type"]) for edge in edges})
    review_states = sorted({edge_review_status(edge) for edge in edges} | {"unknown"})
    temporal_states = sorted({edge_temporal_state(edge) for edge in edges} | {"unknown"})
    participant_roles = ["present", "speaker", "actor", "referenced", "off_frame", "annotation_only"]
    fields: list[dict[str, Any]] = []
    for value in node_types:
        fields.append({"name": f"node_type:{value}", "kind": "one_hot", "source": "HG0 node type"})
    for direction in ("in", "out"):
        for layer in layers:
            fields.append({"name": f"degree:{direction}:layer:{layer}", "kind": "log1p_count", "source": "HG0 layer membership"})
        for edge_type in edge_types:
            fields.append({"name": f"degree:{direction}:edge_type:{edge_type}", "kind": "log1p_count", "source": "HG0 edge type"})
        for state in review_states:
            fields.append({"name": f"availability:{direction}:review:{state}", "kind": "log1p_count", "source": "HG0 review metadata"})
        for state in temporal_states:
            fields.append({"name": f"availability:{direction}:temporal:{state}", "kind": "log1p_count", "source": "HG0 temporal metadata"})
    for role in participant_roles:
        fields.append({"name": f"story_role:{role}", "kind": "log1p_count", "source": "HG0 story_participant edge type"})
    fields.append({"name": "availability:incident_evidence", "kind": "log1p_count", "source": "HG0 evidence IDs"})
    fields.append({"name": "availability:incident_fact", "kind": "log1p_count", "source": "HG0 fact IDs"})
    return fields


def build_feature_matrix(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], schema: list[dict[str, Any]]):
    if np is None:
        raise RuntimeError("NumPy is required for ML0 dataset features")
    node_index = {f"{node['node_type']}:{node['node_id']}": index for index, node in enumerate(nodes)}
    field_index = {str(field["name"]): index for index, field in enumerate(schema)}
    matrix = np.zeros((len(nodes), len(schema)), dtype=np.float64)
    for index, node in enumerate(nodes):
        matrix[index, field_index[f"node_type:{node['node_type']}"]] = 1.0
    for edge in edges:
        source = int(edge["source_index"])
        target = int(edge["target_index"])
        edge_type = str(edge["edge_type"])
        review = edge_review_status(edge)
        temporal = edge_temporal_state(edge)
        layers = edge_layers(edge)
        for layer in layers:
            matrix[source, field_index[f"degree:out:layer:{layer}"]] += 1.0
            matrix[target, field_index[f"degree:in:layer:{layer}"]] += 1.0
        matrix[source, field_index[f"degree:out:edge_type:{edge_type}"]] += 1.0
        matrix[target, field_index[f"degree:in:edge_type:{edge_type}"]] += 1.0
        matrix[source, field_index[f"availability:out:review:{review}"]] += 1.0
        matrix[target, field_index[f"availability:in:review:{review}"]] += 1.0
        matrix[source, field_index[f"availability:out:temporal:{temporal}"]] += 1.0
        matrix[target, field_index[f"availability:in:temporal:{temporal}"]] += 1.0
        if edge_type.startswith("story_participant_"):
            role = edge_type.removeprefix("story_participant_")
            if f"story_role:{role}" in field_index:
                matrix[source, field_index[f"story_role:{role}"]] += 1.0
                matrix[target, field_index[f"story_role:{role}"]] += 1.0
        evidence_count = len(edge.get("evidence_ids", []))
        fact_count = len(edge.get("fact_ids", []))
        matrix[source, field_index["availability:incident_evidence"]] += evidence_count
        matrix[target, field_index["availability:incident_evidence"]] += evidence_count
        matrix[source, field_index["availability:incident_fact"]] += fact_count
        matrix[target, field_index["availability:incident_fact"]] += fact_count
    for index, field in enumerate(schema):
        if field["kind"] == "log1p_count":
            matrix[:, index] = np.log1p(matrix[:, index])
    # Keep node order explicit in the code path; this assertion catches a
    # future accidental reordering without making IDs predictive features.
    if len(node_index) != len(nodes):
        raise AssertionError("duplicate ML0 node index")
    return matrix


def directed_relation_catalog(edge_types: list[str]) -> list[str]:
    return [value for edge_type in sorted(edge_types) for value in (f"{edge_type}::forward", f"{edge_type}::reverse")]


def directed_edges(edges: list[dict[str, Any]], edge_type_index: Mapping[str, int], relation_index: Mapping[str, int]) -> list[tuple[int, int, int, float]]:
    result: list[tuple[int, int, int, float]] = []
    for edge in edges:
        edge_type = str(edge["edge_type"])
        forward = relation_index[f"{edge_type}::forward"]
        reverse = relation_index[f"{edge_type}::reverse"]
        result.append((int(edge["source_index"]), int(edge["target_index"]), forward, 1.0))
        result.append((int(edge["target_index"]), int(edge["source_index"]), reverse, 1.0))
    return result


def build_directed_with_norm(edges: list[dict[str, Any]], relation_index: Mapping[str, int]) -> list[tuple[int, int, int, float]]:
    raw: list[tuple[int, int, int]] = []
    for edge in edges:
        edge_type = str(edge["edge_type"])
        raw.append((int(edge["source_index"]), int(edge["target_index"]), relation_index[f"{edge_type}::forward"]))
        raw.append((int(edge["target_index"]), int(edge["source_index"]), relation_index[f"{edge_type}::reverse"]))
    incoming = Counter(target for _, target, _ in raw)
    outgoing = Counter(source for source, _, _ in raw)
    return [
        (source, target, relation, 1.0 / math.sqrt(max(1, outgoing[source]) * max(1, incoming[target])))
        for source, target, relation in raw
    ]


def graph_view_edges(all_edges: list[dict[str, Any]], view_id: str) -> list[dict[str, Any]]:
    return [edge for edge in all_edges if keep_for_view(edge, view_id)]


def feature_hash(matrix) -> str:
    if np is None:
        return ""
    return hash_bytes(np.asarray(matrix, dtype="<f8").tobytes())


def build_dataset_manifest(hg0: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    if np is None:
        raise RuntimeError("NumPy is required for ML0")
    nodes = list(hg0["nodes"])
    edges = list(hg0["edges"])
    node_types = sorted({str(node["node_type"]) for node in nodes})
    edge_types = sorted({str(edge["edge_type"]) for edge in edges})
    node_type_index = {value: index for index, value in enumerate(node_types)}
    edge_type_index = {value: index for index, value in enumerate(edge_types)}
    relation_types = directed_relation_catalog(edge_types)
    relation_index = {value: index for index, value in enumerate(relation_types)}
    schema = make_feature_schema(nodes, edges)
    encoded_views: dict[str, list[dict[str, Any]]] = {}
    feature_matrices: dict[str, Any] = {}
    view_rows: list[dict[str, Any]] = []
    primary_and_ablation = list(PRIMARY_VIEWS) + [f"G_all_minus_{layer}" for layer in ABLATION_LAYERS]
    for view_id in primary_and_ablation:
        view_edges = graph_view_edges(edges, view_id)
        encoded = encode_edges(view_edges, edge_type_index)
        encoded_views[view_id] = encoded
        matrix = build_feature_matrix(nodes, view_edges, schema)
        feature_matrices[view_id] = matrix
        view_rows.append({
            "view_id": view_id,
            "definition": view_definition(view_id),
            "node_count": len(nodes),
            "edge_count": len(view_edges),
            "edge_ids": [row["edge_id"] for row in encoded],
            "encoded_edges": encoded,
            "edge_type_counts": dict(sorted(Counter(str(edge["edge_type"]) for edge in view_edges).items())),
            "layer_counts": dict(sorted(Counter(layer for edge in view_edges for layer in edge_layers(edge)).items())),
            "review_status_counts": dict(sorted(Counter(edge_review_status(edge) for edge in view_edges).items())),
            "temporal_state_counts": dict(sorted(Counter(edge_temporal_state(edge) for edge in view_edges).items())),
            "feature_shape": [int(value) for value in matrix.shape],
            "feature_sha256": feature_hash(matrix),
            "unknown_temporal_edge_count": sum(edge_temporal_state(edge) in {"unknown", "relative_only"} for edge in view_edges),
        })
    node_rows = [
        {"ml_index": index, "node_type": str(node["node_type"]), "node_id": str(node["node_id"])}
        for index, node in enumerate(nodes)
    ]
    mapping_payload = {
        "nodes": node_rows,
        "node_type_index": node_type_index,
        "edge_type_index": edge_type_index,
        "directed_relation_type_index": relation_index,
    }
    manifest = {
        "schema": ML0_SCHEMA,
        "stage": "ml0-dataset-manifest",
        "research_only": True,
        "source_graph": {
            "graph_id": hg0["graph"].get("graph_id"),
            "scope_id": hg0["graph"].get("scope_id"),
            "hg0_graph_sha256": sha256_file(HG0_INPUTS["graph"]),
            "hg0_ontology_sha256": sha256_file(HG0_INPUTS["ontology"]),
        },
        "mapping": mapping_payload,
        "mapping_sha256": hash_value(mapping_payload),
        "feature_policy": {
            "schema": schema,
            "transformation": "node-type one-hot plus log1p typed incidence/count features; canonical IDs and labels are never feature values.",
            "unknown_is_not_zero_truth": "A zero feature count means no observed edge in this view, not an explicit historical negative.",
        },
        "views": view_rows,
        "published_scope_boundary": hg0["universe"].get("scopes", []),
        "missingness": {
            "missing_edge_is_negative": False,
            "generated_negative_facts": False,
            "ml_corruptions_are_separate": True,
        },
    }
    return manifest, encoded_views, {
        "nodes": nodes,
        "edges": edges,
        "node_type_index": node_type_index,
        "edge_type_index": edge_type_index,
        "relation_index": relation_index,
        "schema": schema,
        "feature_matrices": feature_matrices,
    }


def pair_is_person_story(edge: Mapping[str, Any]) -> bool:
    return (
        str(edge["source"]["node_type"]) == "Person"
        and str(edge["target"]["node_type"]) == "Story"
    )


def deterministic_edge_split(edges: list[dict[str, Any]], seed: int = SPLIT_SEED) -> dict[str, Any]:
    positives = [edge for edge in edges if str(edge["edge_type"]) == "person_story_link" and pair_is_person_story(edge)]
    positives.sort(key=lambda edge: hashlib.sha256(f"{seed}|{edge['edge_id']}".encode()).hexdigest())
    test_count = max(1, int(round(len(positives) * 0.20)))
    test = sorted(positives[:test_count], key=lambda edge: str(edge["edge_id"]))
    train = sorted(positives[test_count:], key=lambda edge: str(edge["edge_id"]))
    payload = {
        "split_seed": seed,
        "target_edge_type": "person_story_link",
        "protocol": "deterministic hash partition; test endpoint pairs are blocked from every context edge to prevent direct duplicate semantic support leakage.",
        "train_edge_ids": [str(edge["edge_id"]) for edge in train],
        "test_edge_ids": [str(edge["edge_id"]) for edge in test],
    }
    payload["split_sha256"] = hash_value(payload)
    return {"train": train, "test": test, "manifest": payload}


def generate_corruptions(
    positives: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
    all_positive_pairs: set[tuple[int, int]],
    count: int,
    seed: int,
) -> dict[tuple[int, int], list[int]]:
    stories = [index for index, node in enumerate(nodes) if str(node["node_type"]) == "Story"]
    result: dict[tuple[int, int], list[int]] = {}
    for edge in positives:
        person = int(edge["source_index"])
        story = int(edge["target_index"])
        candidates = sorted(
            stories,
            key=lambda candidate: hashlib.sha256(f"{seed}|{person}|{story}|{candidate}".encode()).hexdigest(),
        )
        selected: list[int] = []
        for candidate in candidates:
            if candidate == story or (person, candidate) in all_positive_pairs:
                continue
            selected.append(candidate)
            if len(selected) >= count:
                break
        result[(person, story)] = selected
    return result


def edge_context_without_test_pairs(edges: list[dict[str, Any]], test: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocked = {(int(edge["source_index"]), int(edge["target_index"])) for edge in test}
    return [edge for edge in edges if (int(edge["source_index"]), int(edge["target_index"])) not in blocked]


def neighbor_profiles(edges: list[dict[str, Any]], node_count: int) -> tuple[list[set[int]], list[dict[tuple[int, str], int]]]:
    neighbors = [set() for _ in range(node_count)]
    typed = [defaultdict(int) for _ in range(node_count)]
    for edge in edges:
        source = int(edge["source_index"])
        target = int(edge["target_index"])
        typ = str(edge["edge_type"])
        neighbors[source].add(target)
        neighbors[target].add(source)
        typed[source][(target, typ)] += 1
        typed[target][(source, typ)] += 1
    return neighbors, typed


def cosine_row(left, right) -> float:
    left_norm = float(np.linalg.norm(left))
    right_norm = float(np.linalg.norm(right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return float(np.dot(left, right) / (left_norm * right_norm))


def baseline_scores(
    model_name: str,
    features,
    context_edges: list[dict[str, Any]],
    pairs: list[tuple[int, int]],
    nodes: list[dict[str, Any]],
) -> dict[tuple[int, int], float]:
    node_count = len(nodes)
    neighbors, typed = neighbor_profiles(context_edges, node_count)
    if model_name == "spectral_svd":
        person_indices = [index for index, node in enumerate(nodes) if str(node["node_type"]) == "Person"]
        story_indices = [index for index, node in enumerate(nodes) if str(node["node_type"]) == "Story"]
        ppos = {value: index for index, value in enumerate(person_indices)}
        spos = {value: index for index, value in enumerate(story_indices)}
        matrix = np.zeros((len(person_indices), len(story_indices)), dtype=np.float64)
        for edge in context_edges:
            source = int(edge["source_index"])
            target = int(edge["target_index"])
            if source in ppos and target in spos:
                matrix[ppos[source], spos[target]] += 1.0
            elif target in ppos and source in spos:
                matrix[ppos[target], spos[source]] += 1.0
        if matrix.size and np.any(matrix):
            u, singular, vt = np.linalg.svd(matrix, full_matrices=False)
            k = min(8, len(singular))
            left = u[:, :k] * singular[:k]
            right = vt[:k, :].T * singular[:k]
        else:
            left = np.zeros((len(person_indices), 1), dtype=np.float64)
            right = np.zeros((len(story_indices), 1), dtype=np.float64)
        return {
            pair: float(np.dot(left[ppos[pair[0]]], right[spos[pair[1]]])) if pair[0] in ppos and pair[1] in spos else 0.0
            for pair in pairs
        }
    result: dict[tuple[int, int], float] = {}
    for person, story in pairs:
        common = neighbors[person] & neighbors[story]
        degree_product = math.log1p(len(neighbors[person])) * math.log1p(len(neighbors[story]))
        overlap = len(common) / max(1, len(neighbors[person] | neighbors[story]))
        typed_overlap = sum(
            1.0
            for neighbor in common
            if any((neighbor, edge_type) in typed[person] for _, edge_type in typed[story])
        )
        if model_name == "typed_structural_features":
            result[(person, story)] = float(len(common)) + 0.25 * degree_product + 0.5 * overlap + 0.1 * cosine_row(features[person], features[story])
        elif model_name == "relation_count_neighborhood":
            result[(person, story)] = float(typed_overlap) + 0.25 * float(len(common)) + 0.5 * overlap
        else:
            raise ValueError(model_name)
    return result


def ranking_metrics(
    scores: Mapping[tuple[int, int], float],
    positives: list[dict[str, Any]],
    corruptions: Mapping[tuple[int, int], list[int]],
) -> dict[str, Any]:
    reciprocal: list[float] = []
    ranks: list[float] = []
    hits = {1: 0, 3: 0, 10: 0}
    evaluated = 0
    for edge in positives:
        pair = (int(edge["source_index"]), int(edge["target_index"]))
        positive_score = scores.get(pair, 0.0)
        negatives = corruptions.get(pair, [])
        if not negatives:
            continue
        better = sum(scores.get((pair[0], candidate), 0.0) > positive_score for candidate in negatives)
        tied = sum(scores.get((pair[0], candidate), 0.0) == positive_score for candidate in negatives)
        # Average-rank ties prevent an uninformative constant scorer from
        # receiving rank 1 merely because ``>`` is false for every negative.
        rank = 1.0 + float(better) + 0.5 * float(tied)
        ranks.append(rank)
        reciprocal.append(1.0 / rank)
        for k in hits:
            hits[k] += int(rank <= k)
        evaluated += 1
    return {
        "evaluated_positive_count": evaluated,
        "mrr": finite_mean(reciprocal),
        "mean_rank": finite_mean(ranks),
        "hits_at_1": finite_float(hits[1] / evaluated) if evaluated else None,
        "hits_at_3": finite_float(hits[3] / evaluated) if evaluated else None,
        "hits_at_10": finite_float(hits[10] / evaluated) if evaluated else None,
        "negative_semantics": "ML-only deterministic corruptions; they are not historical negative facts.",
    }


def run_baselines(
    nodes: list[dict[str, Any]],
    all_edges: list[dict[str, Any]],
    feature_matrices: Mapping[str, Any],
    split: Mapping[str, Any],
    encoded_views: Mapping[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    test = list(split["test"])
    all_pairs = {(int(edge["source_index"]), int(edge["target_index"])) for edge in all_edges if str(edge["edge_type"]) == "person_story_link"}
    test_corruptions = generate_corruptions(test, nodes, all_pairs, TEST_NEGATIVES, SPLIT_SEED + 100)
    rows: list[dict[str, Any]] = []
    for view_id in PRIMARY_VIEWS:
        view_edges = [edge for edge in all_edges if keep_for_view(edge, view_id)]
        context = edge_context_without_test_pairs(view_edges, test)
        features = build_feature_matrix(nodes, context, make_feature_schema(nodes, all_edges))
        for model_name in ("typed_structural_features", "spectral_svd", "relation_count_neighborhood"):
            pairs = [(int(edge["source_index"]), int(edge["target_index"])) for edge in test]
            score_pairs = pairs + [(pair[0], negative) for pair, negatives in test_corruptions.items() for negative in negatives]
            scores = baseline_scores(model_name, features, context, score_pairs, nodes)
            metrics = ranking_metrics(scores, test, test_corruptions)
            rows.append({
                "view_id": view_id,
                "model": model_name,
                "context_edge_count": len(context),
                "feature_shape": [int(value) for value in features.shape],
                "metrics": metrics,
                "status": "completed",
                "structural_only": True,
                "input_view_edge_count": len(view_edges),
            })
    return {
        "schema": ML0_SCHEMA,
        "stage": "ml0-baseline-results",
        "task": "held-out observed PersonStory reconstruction",
        "protocol": "No canonical negatives; deterministic corruption candidates are used only for ranking evaluation.",
        "split_sha256": split["manifest"]["split_sha256"],
        "results": rows,
    }


def tanh_forward(h, w_rel, w_self, bias, edges, node_count):
    aggregate = h @ w_self
    for source, target, relation, norm in edges:
        aggregate[target] += (h[source] @ w_rel[relation]) * norm
    pre = aggregate + bias
    return np.tanh(pre), {"input": h, "pre": pre, "edges": edges}


def tanh_backward(cache, grad_out, w_rel, w_self, relation_count):
    h = cache["input"]
    pre = cache["pre"]
    edges = cache["edges"]
    grad_pre = grad_out * (1.0 - np.tanh(pre) ** 2)
    grad_w_rel = np.zeros_like(w_rel)
    grad_w_self = h.T @ grad_pre
    grad_bias = grad_pre.sum(axis=0)
    grad_h = grad_pre @ w_self.T
    for source, target, relation, norm in edges:
        message_gradient = grad_pre[target] * norm
        grad_w_rel[relation] += np.outer(h[source], message_gradient)
        grad_h[source] += message_gradient @ w_rel[relation].T
    return grad_h, grad_w_rel, grad_w_self, grad_bias


def rgcn_forward(features, params, graph_edges, node_count):
    hidden1, cache1 = tanh_forward(features, params["w1_rel"], params["w1_self"], params["b1"], graph_edges, node_count)
    hidden2, cache2 = tanh_forward(hidden1, params["w2_rel"], params["w2_self"], params["b2"], graph_edges, node_count)
    return hidden2, (cache1, cache2)


def link_loss_and_gradient(embeddings, positives, corruptions):
    grad = np.zeros_like(embeddings)
    losses: list[float] = []
    sample_count = 0
    examples: list[tuple[int, int, float]] = []
    for edge in positives:
        person = int(edge["source_index"])
        story = int(edge["target_index"])
        examples.append((person, story, 1.0))
        examples.extend((person, candidate, 0.0) for candidate in corruptions.get((person, story), []))
    for person, story, label in examples:
        logit = float(np.dot(embeddings[person], embeddings[story]))
        clipped = max(-40.0, min(40.0, logit))
        sigmoid = 1.0 / (1.0 + math.exp(-clipped))
        if label:
            losses.append(math.log1p(math.exp(-clipped)))
        else:
            losses.append(math.log1p(math.exp(clipped)))
        coefficient = (sigmoid - label) / max(1, len(examples))
        grad[person] += coefficient * embeddings[story]
        grad[story] += coefficient * embeddings[person]
        sample_count += 1
    return finite_float(sum(losses) / max(1, len(losses))), grad, sample_count


def adam_step(params, gradients, state, step, learning_rate):
    beta1 = 0.9
    beta2 = 0.999
    epsilon = 1e-8
    for name, value in params.items():
        gradient = np.clip(gradients[name], -5.0, 5.0)
        state[name]["m"] = beta1 * state[name]["m"] + (1 - beta1) * gradient
        state[name]["v"] = beta2 * state[name]["v"] + (1 - beta2) * (gradient * gradient)
        corrected_m = state[name]["m"] / (1 - beta1 ** step)
        corrected_v = state[name]["v"] / (1 - beta2 ** step)
        params[name] = value - learning_rate * corrected_m / (np.sqrt(corrected_v) + epsilon)


def initialize_rgcn(feature_dim, relation_count, hidden_dim, seed):
    rng = np.random.default_rng(seed)
    scale1 = math.sqrt(2.0 / max(1, feature_dim))
    scale2 = math.sqrt(2.0 / max(1, hidden_dim))
    return {
        "w1_rel": rng.normal(0.0, scale1, (relation_count, feature_dim, hidden_dim)),
        "w1_self": rng.normal(0.0, scale1, (feature_dim, hidden_dim)),
        "b1": np.zeros(hidden_dim, dtype=np.float64),
        "w2_rel": rng.normal(0.0, scale2, (relation_count, hidden_dim, hidden_dim)),
        "w2_self": rng.normal(0.0, scale2, (hidden_dim, hidden_dim)),
        "b2": np.zeros(hidden_dim, dtype=np.float64),
    }


def zero_like_params(params):
    return {name: np.zeros_like(value) for name, value in params.items()}


def train_rgcn(
    features,
    context_edges: list[dict[str, Any]],
    train_positives: list[dict[str, Any]],
    test_positives: list[dict[str, Any]],
    train_corruptions: Mapping[tuple[int, int], list[int]],
    test_corruptions: Mapping[tuple[int, int], list[int]],
    relation_index: Mapping[str, int],
    nodes: list[dict[str, Any]],
    seed: int,
):
    node_count = len(nodes)
    relation_count = len(relation_index)
    model_edges = build_directed_with_norm(context_edges, relation_index)
    params = initialize_rgcn(features.shape[1], relation_count, HIDDEN_DIM, seed)
    optimizer = {
        name: {"m": np.zeros_like(value), "v": np.zeros_like(value)}
        for name, value in params.items()
    }
    losses: list[float] = []
    for step in range(1, EPOCHS + 1):
        embeddings, caches = rgcn_forward(features, params, model_edges, node_count)
        loss, grad_embeddings, _ = link_loss_and_gradient(embeddings, train_positives, train_corruptions)
        if loss is None or not np.all(np.isfinite(grad_embeddings)):
            return {"status": "unstable_non_finite", "seed": seed, "losses": losses, "embedding": None}
        grad_h1, grad_w2_rel, grad_w2_self, grad_b2 = tanh_backward(caches[1], grad_embeddings, params["w2_rel"], params["w2_self"], relation_count)
        _, grad_w1_rel, grad_w1_self, grad_b1 = tanh_backward(caches[0], grad_h1, params["w1_rel"], params["w1_self"], relation_count)
        gradients = {
            "w1_rel": grad_w1_rel,
            "w1_self": grad_w1_self,
            "b1": grad_b1,
            "w2_rel": grad_w2_rel,
            "w2_self": grad_w2_self,
            "b2": grad_b2,
        }
        adam_step(params, gradients, optimizer, step, LEARNING_RATE)
        losses.append(float(loss))
    embeddings, _ = rgcn_forward(features, params, model_edges, node_count)
    pairs = [(int(edge["source_index"]), int(edge["target_index"])) for edge in test_positives]
    score_pairs = pairs + [(pair[0], candidate) for pair, negatives in test_corruptions.items() for candidate in negatives]
    scores = {pair: float(np.dot(embeddings[pair[0]], embeddings[pair[1]])) for pair in score_pairs}
    metrics = ranking_metrics(scores, test_positives, test_corruptions)
    person_indices = [index for index, node in enumerate(nodes) if str(node["node_type"]) == "Person"]
    person_embeddings = embeddings[person_indices]
    return {
        "status": "completed",
        "seed": seed,
        "losses": {
            "first": finite_float(losses[0]) if losses else None,
            "last": finite_float(losses[-1]) if losses else None,
            "minimum": finite_float(min(losses)) if losses else None,
            "epoch_count": len(losses),
        },
        "metrics": metrics,
        "embedding_dimension": int(embeddings.shape[1]),
        "person_embedding_sha256": hash_bytes(np.asarray(person_embeddings, dtype="<f8").tobytes()),
        "embedding": person_embeddings,
    }


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [run for run in runs if run.get("status") == "completed"]
    metrics = [run.get("metrics", {}) for run in completed]
    keys = ("mrr", "hits_at_1", "hits_at_3", "hits_at_10", "mean_rank")
    summary = {
        "run_count": len(runs),
        "completed_count": len(completed),
        "status": "completed" if completed else "unavailable_or_unstable",
        "metrics": {
            key: {
                "mean": finite_mean(metric.get(key) for metric in metrics),
                "std": finite_std(metric.get(key) for metric in metrics),
            }
            for key in keys
        },
        "loss_last": {
            "mean": finite_mean(run.get("losses", {}).get("last") for run in completed),
            "std": finite_std(run.get("losses", {}).get("last") for run in completed),
        },
    }
    return summary


def run_gnn_experiments(
    nodes: list[dict[str, Any]],
    all_edges: list[dict[str, Any]],
    schema: list[dict[str, Any]],
    relation_index: Mapping[str, int],
    split: Mapping[str, Any],
    seed_map: Mapping[str, tuple[int, ...]],
) -> tuple[dict[str, Any], dict[str, dict[int, Any]]]:
    train = list(split["train"])
    test = list(split["test"])
    all_pairs = {(int(edge["source_index"]), int(edge["target_index"])) for edge in all_edges if str(edge["edge_type"]) == "person_story_link"}
    embeddings: dict[str, dict[int, Any]] = {}
    view_summaries: list[dict[str, Any]] = []
    raw_runs: dict[str, list[dict[str, Any]]] = {}
    for view_id, seeds in seed_map.items():
        view_edges = [edge for edge in all_edges if keep_for_view(edge, view_id)]
        context_edges = edge_context_without_test_pairs(view_edges, test)
        features = build_feature_matrix(nodes, context_edges, schema)
        runs: list[dict[str, Any]] = []
        embeddings[view_id] = {}
        for seed in seeds:
            train_corruptions = generate_corruptions(train, nodes, all_pairs, TRAIN_NEGATIVES, seed + 1000)
            test_corruptions = generate_corruptions(test, nodes, all_pairs, TEST_NEGATIVES, seed + 2000)
            run = train_rgcn(
                features,
                context_edges,
                train,
                test,
                train_corruptions,
                test_corruptions,
                relation_index,
                nodes,
                seed,
            )
            if run.get("embedding") is not None:
                embeddings[view_id][seed] = run.pop("embedding")
            run["context_edge_count"] = len(context_edges)
            run["view_edge_count"] = len(view_edges)
            run["feature_shape"] = [int(value) for value in features.shape]
            run["train_positive_count"] = len(train)
            run["test_positive_count"] = len(test)
            run["corruption_policy"] = "Deterministic endpoint-type constrained computational corruptions only; no negative historical facts are emitted."
            runs.append(run)
        raw_runs[view_id] = runs
        summary = summarize_runs(runs)
        summary.update({
            "view_id": view_id,
            "context_edge_count": len(context_edges),
            "view_edge_count": len(view_edges),
            "seed_policy": list(seeds),
            "model": "numpy_rgcn_style_two_layer_relation_aware_message_passing",
            "hyperparameters": {
                "hidden_dimension": HIDDEN_DIM,
                "layers": 2,
                "epochs": EPOCHS,
                "learning_rate": LEARNING_RATE,
                "train_corruptions_per_positive": TRAIN_NEGATIVES,
                "test_corruptions_per_positive": TEST_NEGATIVES,
                "activation": "tanh",
                "normalization": "symmetric degree normalization on directed forward/reverse relation messages",
            },
        })
        view_summaries.append(summary)
    clean_runs = {}
    for view_id, runs in raw_runs.items():
        clean_runs[view_id] = []
        for run in runs:
            clean = {key: value for key, value in run.items() if key != "embedding"}
            clean_runs[view_id].append(clean)
    return {
        "schema": ML0_SCHEMA,
        "stage": "ml0-gnn-results",
        "implementation": {
            "framework": "NumPy 1.x custom implementation",
            "framework_status": "PyTorch/PyG unavailable in execution environment; this is a lightweight relation-aware R-GCN-style pilot, not a production ML dependency.",
            "model": "two-layer relation-aware message-passing autoencoder with typed-edge reconstruction objective",
            "write_back": False,
        },
        "task": "held-out observed PersonStory reconstruction",
        "views": view_summaries,
        "runs": clean_runs,
    }, embeddings


def pairwise_distance_correlation(left, right) -> float | None:
    left = np.asarray(left, dtype=np.float64)
    right = np.asarray(right, dtype=np.float64)
    if left.shape != right.shape or left.shape[0] < 3:
        return None
    left_distance = np.linalg.norm(left[:, None, :] - left[None, :, :], axis=2)
    right_distance = np.linalg.norm(right[:, None, :] - right[None, :, :], axis=2)
    mask = np.triu(np.ones(left_distance.shape, dtype=bool), 1)
    a = left_distance[mask]
    b = right_distance[mask]
    if np.std(a) == 0 or np.std(b) == 0:
        return None
    return finite_float(np.corrcoef(a, b)[0, 1])


def nearest_neighbor_overlap(left, right, k: int = 5) -> float | None:
    left = np.asarray(left, dtype=np.float64)
    right = np.asarray(right, dtype=np.float64)
    if left.shape != right.shape or left.shape[0] < 2:
        return None
    k = min(k, left.shape[0] - 1)
    def neighbors(value):
        norm = value / np.maximum(np.linalg.norm(value, axis=1, keepdims=True), 1e-12)
        similarity = norm @ norm.T
        np.fill_diagonal(similarity, -np.inf)
        return [set(np.argsort(-similarity[index])[:k]) for index in range(value.shape[0])]
    one = neighbors(left)
    two = neighbors(right)
    return finite_mean(len(one[index] & two[index]) / max(1, k) for index in range(left.shape[0]))


def procrustes_similarity(left, right) -> float | None:
    left = np.asarray(left, dtype=np.float64)
    right = np.asarray(right, dtype=np.float64)
    if left.shape != right.shape or left.size == 0:
        return None
    left = left - left.mean(axis=0, keepdims=True)
    right = right - right.mean(axis=0, keepdims=True)
    left_norm = float(np.linalg.norm(left))
    right_norm = float(np.linalg.norm(right))
    if left_norm == 0 or right_norm == 0:
        return None
    u, _, vt = np.linalg.svd(left.T @ right, full_matrices=False)
    rotation = u @ vt
    aligned = left @ rotation
    return finite_float(1.0 - float(np.linalg.norm(aligned - right)) / max(left_norm, right_norm))


def representation_comparison(
    embeddings: Mapping[str, Mapping[int, Any]],
    left_view: str,
    right_view: str,
) -> dict[str, Any]:
    common_seeds = sorted(set(embeddings.get(left_view, {})) & set(embeddings.get(right_view, {})))
    rows = []
    for seed in common_seeds:
        left = embeddings[left_view][seed]
        right = embeddings[right_view][seed]
        rows.append({
            "seed": seed,
            "pairwise_distance_correlation": pairwise_distance_correlation(left, right),
            "nearest_neighbor_overlap_at_5": nearest_neighbor_overlap(left, right, 5),
            "procrustes_similarity": procrustes_similarity(left, right),
        })
    return {
        "left_view": left_view,
        "right_view": right_view,
        "common_seed_count": len(common_seeds),
        "seed_comparisons": rows,
        "summary": {
            metric: {
                "mean": finite_mean(row.get(metric) for row in rows),
                "std": finite_std(row.get(metric) for row in rows),
            }
            for metric in ("pairwise_distance_correlation", "nearest_neighbor_overlap_at_5", "procrustes_similarity")
        },
        "interpretation": "Model-space similarity only; it is not historical or social similarity.",
    }


def representation_comparisons(embeddings: Mapping[str, Mapping[int, Any]], layers: Iterable[str]) -> list[dict[str, Any]]:
    pairs = [
        ("G_all", "G_story"),
        ("G_all", "G_external"),
        ("G_all", "G_reviewed"),
        ("G_reviewed", "G_reviewed_plus_candidate"),
    ]
    pairs.extend(("G_all", f"G_all_minus_{layer}") for layer in layers)
    return [representation_comparison(embeddings, left, right) for left, right in pairs]


def extract_summary(gnn: Mapping[str, Any], view_id: str, metric: str) -> float | None:
    for row in gnn.get("views", []):
        if row.get("view_id") == view_id:
            return row.get("metrics", {}).get(metric, {}).get("mean")
    return None


def build_ablation_results(gnn: Mapping[str, Any], comparisons: list[dict[str, Any]], all_edges: list[dict[str, Any]]) -> dict[str, Any]:
    comparison_by_right = {row["right_view"]: row for row in comparisons if row.get("left_view") == "G_all"}
    rows = []
    for layer in ABLATION_LAYERS:
        view_id = f"G_all_minus_{layer}"
        removed = sum(layer in edge_layers(edge) for edge in all_edges)
        comparison = comparison_by_right.get(view_id, {})
        rows.append({
            "layer": layer,
            "view_id": view_id,
            "edge_count_removed": removed,
            "persons_affected": sorted({
                endpoint["node_id"]
                for edge in all_edges
                if layer in edge_layers(edge)
                for endpoint in (edge["source"], edge["target"])
                if endpoint["node_type"] == "Person"
            }),
            "gnn_mrr": next((row.get("metrics", {}).get("mrr") for row in gnn.get("views", []) if row.get("view_id") == view_id), None),
            "representation_change": comparison.get("summary", {}),
            "status": "meaningful" if removed else "not_meaningful_no_edges",
        })
    return {
        "schema": ML0_SCHEMA,
        "stage": "ml0-ablation-results",
        "policy": "Ablations remove one explicit HG0 layer from G_all; independent multiplex edge types are not collapsed or replaced by co-occurrence edges.",
        "results": rows,
    }


def build_temporal_feasibility(edges: list[dict[str, Any]]) -> dict[str, Any]:
    bounded = [edge for edge in edges if edge_temporal_state(edge) in TEMPORAL_BOUNDED_STATES]
    unknown = [edge for edge in edges if edge_temporal_state(edge) in {"unknown", "relative_only"}]
    years = sorted({
        int(value)
        for edge in bounded
        for value in ((edge.get("temporal") or {}).get("start_year_ce"), (edge.get("temporal") or {}).get("end_year_ce"))
        if value is not None
    })
    cutoffs = sorted({years[index] for index in (0, len(years) // 2, len(years) - 1) if years})
    slices = []
    for cutoff in cutoffs:
        pre = [edge for edge in bounded if (edge.get("temporal") or {}).get("end_year_ce") is not None and int(edge["temporal"]["end_year_ce"]) <= cutoff]
        post = [edge for edge in bounded if (edge.get("temporal") or {}).get("start_year_ce") is not None and int(edge["temporal"]["start_year_ce"]) > cutoff]
        active = [edge for edge in bounded if (edge.get("temporal") or {}).get("start_year_ce") is not None and (edge.get("temporal") or {}).get("end_year_ce") is not None and int(edge["temporal"]["start_year_ce"]) <= cutoff <= int(edge["temporal"]["end_year_ce"])]
        slices.append({
            "cutoff_year_ce": cutoff,
            "pre_edge_count": len(pre),
            "post_edge_count": len(post),
            "potentially_active_edge_count": len(active),
            "pre_unknown_edge_count": sum(edge in unknown for edge in pre),
            "pre_max_end_year_ce": max((int(edge["temporal"]["end_year_ce"]) for edge in pre), default=None),
            "post_min_start_year_ce": min((int(edge["temporal"]["start_year_ce"]) for edge in post), default=None),
        })
    return {
        "schema": ML0_SCHEMA,
        "stage": "ml0-temporal-feasibility",
        "status": "pilot_only" if bounded else "insufficient",
        "policy": "Strict temporal views use only bounded/one-sided HG0 intervals. Unknown and relative-only edges are never silently treated as pre-cutoff observations.",
        "bounded_edge_count": len(bounded),
        "unknown_or_relative_bucket": {
            "edge_count": len(unknown),
            "edge_ids": [str(edge["edge_id"]) for edge in unknown],
        },
        "cutoff_slices": slices,
        "leakage_checks": {
            "unknown_excluded_from_pre": all(row["pre_unknown_edge_count"] == 0 for row in slices),
            "pre_max_end_respects_cutoff": all(row["pre_max_end_year_ce"] is None or row["pre_max_end_year_ce"] <= row["cutoff_year_ce"] for row in slices),
            "future_start_excluded_from_pre": all(row["post_min_start_year_ce"] is None or row["post_min_start_year_ce"] > row["cutoff_year_ce"] for row in slices),
        },
        "future_ml_use": "This is a feasibility contract, not a predictive temporal accuracy claim and not a train/test split artifact.",
    }


def build_link_feasibility(split: Mapping[str, Any], baselines: Mapping[str, Any], gnn: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": ML0_SCHEMA,
        "stage": "ml0-link-feasibility",
        "status": "pilot_only",
        "target": "person_story_link",
        "observed_positive_count": len(split["train"]) + len(split["test"]),
        "train_positive_count": len(split["train"]),
        "test_positive_count": len(split["test"]),
        "split": split["manifest"],
        "baseline_views": sorted({row["view_id"] for row in baselines.get("results", [])}),
        "gnn_views": sorted(row["view_id"] for row in gnn.get("views", [])),
        "protocol": {
            "held_out_observed_positive": True,
            "direct_duplicate_support_blocked": True,
            "endpoint_type_constraints": "Person source to Story target",
            "generated_corruptions_are_not_historical_negatives": True,
            "sparse_external_relations_excluded": "Non-Story Person-Person relation types lack enough reviewed positives for a responsible standalone pilot.",
        },
        "interpretation": "Feasibility of reconstructing observed published-scope links only; no missing historical relation is inferred.",
    }


def build_bias_diagnostic(
    hg0: Mapping[str, Any],
    gnn: Mapping[str, Any],
    comparisons: list[dict[str, Any]],
    baselines: Mapping[str, Any],
) -> dict[str, Any]:
    story_ratio = float(hg0["bias"]["story_layer_dominance"].get("story_related_edge_ratio", 0.0))
    comparison = {(row["left_view"], row["right_view"]): row for row in comparisons}
    all_story = comparison.get(("G_all", "G_story"), {})
    all_external = comparison.get(("G_all", "G_external"), {})
    story_corr = all_story.get("summary", {}).get("pairwise_distance_correlation", {}).get("mean")
    external_corr = all_external.get("summary", {}).get("pairwise_distance_correlation", {}).get("mean")
    all_mrr = extract_summary(gnn, "G_all", "mrr")
    story_mrr = extract_summary(gnn, "G_story", "mrr")
    external_mrr = extract_summary(gnn, "G_external", "mrr")
    random_mrr = sum(1.0 / rank for rank in range(1, TEST_NEGATIVES + 2)) / (TEST_NEGATIVES + 1)
    external_delta = (external_mrr - random_mrr) if external_mrr is not None else None
    if story_corr is not None and story_corr >= 0.80 and story_ratio >= 0.70 and (external_delta is None or external_delta < 0.05):
        story_class = "story-dominated"
    elif story_corr is not None and story_corr >= 0.55:
        story_class = "mixed signal"
    else:
        story_class = "insufficient evidence"
    if external_delta is not None and external_delta >= 0.05 and (external_corr is None or external_corr < 0.90):
        external_class = "meaningful"
    elif external_mrr is not None:
        external_class = "weak"
    else:
        external_class = "insufficient"
    return {
        "schema": ML0_SCHEMA,
        "stage": "ml0-bias-diagnostic",
        "story_edge_ratio_from_hg0": story_ratio,
        "gnn_mrr": {"G_all": all_mrr, "G_story": story_mrr, "G_external": external_mrr},
        "random_mrr_reference": random_mrr,
        "representation_comparisons": {
            "G_all_vs_G_story": all_story.get("summary", {}),
            "G_all_vs_G_external": all_external.get("summary", {}),
        },
        "classification": {
            "story_dominance": story_class,
            "external_historical_signal": external_class,
            "graph_trainability": "stable" if any(row.get("status") == "completed" and row.get("completed_count", 0) >= 3 for row in gnn.get("views", [])) else "unstable",
        },
        "thresholds": {
            "story_ratio_for_dominance": 0.70,
            "all_story_distance_correlation_for_dominance": 0.80,
            "external_mrr_margin_over_random_for_meaningful": 0.05,
            "note": "These are transparent pilot diagnostic thresholds, not historical truth scores.",
        },
        "limitations": [
            "The task reconstructs observed PersonStory links and is selected by published corpus scope.",
            "Model-space similarity is not historical similarity.",
            "Candidate/reviewed status changes measure epistemic sensitivity, not source correctness.",
        ],
    }


def build_expansion_recommendation(
    hg0: Mapping[str, Any],
    gnn: Mapping[str, Any],
    ablations: Mapping[str, Any],
    bias: Mapping[str, Any],
) -> dict[str, Any]:
    sufficiency = hg0["sufficiency"].get("layers", {})
    ablation_by_layer = {row["layer"]: row for row in ablations.get("results", [])}
    story_class = bias["classification"].get("story_dominance")
    external_class = bias["classification"].get("external_historical_signal")
    rows = []
    for layer in ("family", "clan", "office", "event", "geographic", "service_political", "temporal", "social_context"):
        status = sufficiency.get(layer, {}).get("classification", "unknown")
        ablation = ablation_by_layer.get(layer, {})
        change = ablation.get("representation_change", {}).get("pairwise_distance_correlation", {}).get("mean")
        if status in {"insufficient", "pilot_only"}:
            action = "enrich_targeted" if layer not in {"social_context"} else "retain_as_audit_only"
            priority = "high" if layer in {"office", "family", "event", "temporal"} else "medium"
        else:
            action = "monitor"
            priority = "low"
        if change is not None and change < 0.85:
            signal = "meaningful_sensitivity"
        elif change is not None:
            signal = "weak_sensitivity"
        else:
            signal = "unknown"
        rows.append({
            "layer": layer,
            "current_status": status,
            "ml0_signal": signal,
            "representation_similarity_to_g_all": change,
            "reason": "Layer readiness and controlled ablation sensitivity are reported together; neither is historical importance.",
            "recommended_action": action,
            "priority": priority,
            "target_types": {
                "family": ["Person", "KinshipFact", "MarriageUnion", "Clan"],
                "clan": ["Person", "Clan", "ClanMembership"],
                "office": ["Person", "Office", "OfficeTenure", "Location"],
                "event": ["Person", "Event", "EventParticipation"],
                "geographic": ["Person", "Location", "PersonActivity"],
                "service_political": ["Person", "ServicePoliticalFact", "Event"],
                "temporal": ["PersonActivity", "OfficeTenure", "Event", "Story"],
                "social_context": ["Relation", "Evidence"],
            }.get(layer, []),
            "selection_policy": "Use local-source availability, bridge/coverage value, and provenance completeness; do not select by model score, centrality, fame, or inferred historical importance.",
        })
    if story_class == "story-dominated":
        story_action = "conditional_targeted_expansion"
        story_reason = "The combined representation is close to the Story view and the external view is weak; expand only Stories that add source-backed external historical context, not broad textual volume."
        person_action = "selective_external_bridge_expansion"
    elif external_class == "meaningful":
        story_action = "targeted_expansion"
        story_reason = "External layers show measurable independent model signal; prioritize Stories that activate those layers while preserving identity and provenance gates."
        person_action = "selective_layer_bridge_expansion"
    else:
        story_action = "defer_broad_expansion_pending_targeted_enrichment"
        story_reason = "The pilot does not establish enough independent external signal to justify broad corpus growth."
        person_action = "selective_review_only"
    return {
        "schema": ML0_SCHEMA,
        "stage": "ml0-expansion-recommendation",
        "research_only": True,
        "layers": rows,
        "story_expansion": {
            "recommendation": story_action,
            "reason": story_reason,
            "do_not_execute": True,
            "selection_policy": "If expanded later, choose Stories that close documented office/family/event/location/temporal gaps and have qualified local source evidence; do not expand to optimize graph size.",
        },
        "person_expansion": {
            "recommendation": person_action,
            "reason": "Promote only secure identities that are necessary bridges for selected source-backed Stories or historical layers; no centrality/fame/model-score ranking.",
            "do_not_execute": True,
            "selection_policy": "Review bridge endpoint gaps and local evidence first; missing historical edges remain unknown.",
        },
        "decision": "ML0 recommends targeted X1 planning, not immediate broad Story or Person expansion.",
    }


def build_experiment_manifest(split: Mapping[str, Any], input_hashes: Mapping[str, str]) -> dict[str, Any]:
    return {
        "schema": ML0_SCHEMA,
        "stage": "ml0-experiment-manifest",
        "research_only": True,
        "input_hg0_hashes": dict(sorted(input_hashes.items())),
        "runtime_environment": {
            "python": platform.python_version(),
            "numpy": getattr(np, "__version__", "unavailable"),
            "pytorch": "unavailable_in_execution_environment",
            "platform": platform.platform(),
            "python_executable": sys.executable,
        },
        "random_seed_policy": {
            "split_seed": SPLIT_SEED,
            "primary_seeds": list(PRIMARY_SEEDS),
            "secondary_seeds": list(SECONDARY_SEEDS),
            "same_seeds_across_views": True,
        },
        "task": {
            "target": "observed person_story_link",
            "objective": "typed edge reconstruction of held-out observed positives",
            "negative_policy": "deterministic computational corruptions only; no canonical negative facts",
            "direct_duplicate_support_leakage": "all context edges sharing held-out Person→Story endpoint pair are removed",
        },
        "dataset_views": [
            {"view_id": view_id, "definition": view_definition(view_id)}
            for view_id in list(PRIMARY_VIEWS) + [f"G_all_minus_{layer}" for layer in ABLATION_LAYERS]
        ],
        "models": [
            {"model": "typed_structural_features", "kind": "non_gnn", "feature_policy": "typed log1p incidence counts"},
            {"model": "spectral_svd", "kind": "non_gnn", "feature_policy": "training-context Person×Story incidence SVD"},
            {"model": "relation_count_neighborhood", "kind": "non_gnn", "feature_policy": "typed two-hop neighborhood overlap"},
            {"model": "numpy_rgcn_style_two_layer_relation_aware_message_passing", "kind": "gnn_pilot", "hidden_dimension": HIDDEN_DIM, "epochs": EPOCHS, "learning_rate": LEARNING_RATE},
        ],
        "split": split["manifest"],
        "no_model_selection_sweep": True,
    }


def build_metrics(
    hg0: Mapping[str, Any],
    manifest: Mapping[str, Any],
    baselines: Mapping[str, Any],
    gnn: Mapping[str, Any],
    bias: Mapping[str, Any],
    temporal: Mapping[str, Any],
    link: Mapping[str, Any],
    expansion: Mapping[str, Any],
) -> dict[str, Any]:
    view_counts = {
        row["view_id"]: {key: row[key] for key in ("node_count", "edge_count", "unknown_temporal_edge_count")}
        for row in manifest.get("views", [])
    }
    return {
        "schema": ML0_SCHEMA,
        "stage": "ml0-metrics",
        "scope": {
            "hg0_graph_id": hg0["graph"].get("graph_id"),
            "persons": sum(node["node_type"] == "Person" for node in hg0["nodes"]),
            "stories": sum(node["node_type"] == "Story" for node in hg0["nodes"]),
            "hg0_nodes": len(hg0["nodes"]),
            "hg0_edges": len(hg0["edges"]),
        },
        "dataset_views": view_counts,
        "baseline_completed_count": sum(row.get("status") == "completed" for row in baselines.get("results", [])),
        "gnn_completed_runs": sum(row.get("completed_count", 0) for row in gnn.get("views", [])),
        "gnn_total_runs": sum(row.get("run_count", 0) for row in gnn.get("views", [])),
        "seed_variance_reported": True,
        "story_dominance": bias["classification"].get("story_dominance"),
        "external_signal": bias["classification"].get("external_historical_signal"),
        "graph_trainability": bias["classification"].get("graph_trainability"),
        "temporal_feasibility": temporal.get("status"),
        "link_feasibility": link.get("status"),
        "x1_recommendation": expansion.get("decision"),
        "negative_facts_generated": False,
        "embeddings_persisted": False,
        "checkpoints_persisted": False,
        "write_back_to_historical_facts": False,
    }


def build_all() -> dict[str, Any]:
    if np is None:
        raise RuntimeError("ML0 requires NumPy. Install the optional ML dependencies from requirements-ml.txt.")
    hg0 = load_hg0()
    input_hashes = {name: sha256_file(path) for name, path in HG0_INPUTS.items()}
    manifest, encoded_views, context = build_dataset_manifest(hg0)
    split = deterministic_edge_split(hg0["edges"])
    baselines = run_baselines(
        context["nodes"],
        context["edges"],
        context["feature_matrices"],
        split,
        encoded_views,
    )
    seed_map = {
        "G_story": PRIMARY_SEEDS,
        "G_external": PRIMARY_SEEDS,
        "G_all": PRIMARY_SEEDS,
        "G_reviewed": PRIMARY_SEEDS,
        "G_reviewed_plus_candidate": SECONDARY_SEEDS,
        "G_temporal_bounded": SECONDARY_SEEDS,
    }
    seed_map.update({f"G_all_minus_{layer}": SECONDARY_SEEDS for layer in ABLATION_LAYERS})
    gnn, embeddings = run_gnn_experiments(
        context["nodes"],
        context["edges"],
        context["schema"],
        context["relation_index"],
        split,
        seed_map,
    )
    comparisons = representation_comparisons(embeddings, ABLATION_LAYERS)
    gnn["representation_comparisons"] = comparisons
    ablations = build_ablation_results(gnn, comparisons, context["edges"])
    temporal = build_temporal_feasibility(context["edges"])
    link = build_link_feasibility(split, baselines, gnn)
    bias = build_bias_diagnostic(hg0, gnn, comparisons, baselines)
    expansion = build_expansion_recommendation(hg0, gnn, ablations, bias)
    experiments = build_experiment_manifest(split, input_hashes)
    metrics = build_metrics(hg0, manifest, baselines, gnn, bias, temporal, link, expansion)
    protection = {
        "schema": ML0_SCHEMA,
        "stage": "ml0-protection-manifest",
        "hg0_input_hashes": dict(sorted(input_hashes.items())),
        "hg0_graph_id": hg0["graph"].get("graph_id"),
        "protected_counts": {
            "persons": sum(node["node_type"] == "Person" for node in hg0["nodes"]),
            "stories": sum(node["node_type"] == "Story" for node in hg0["nodes"]),
            "hg0_nodes": len(hg0["nodes"]),
            "hg0_edges": len(hg0["edges"]),
        },
        "write_back_policy": "ML0 outputs are disposable research artifacts. No model output, corruption, embedding, or recommendation writes to H0C facts, HG0 ontology, HG0 graph truth, Persons, Stories, Relations, or participant freeze.",
        "canonical_negative_facts_generated": False,
        "model_checkpoints_generated": False,
        "embeddings_persisted": False,
    }
    outputs = {
        "dataset": manifest,
        "experiments": experiments,
        "baselines": baselines,
        "gnn": gnn,
        "ablations": ablations,
        "bias": bias,
        "temporal": temporal,
        "link": link,
        "expansion": expansion,
        "metrics": metrics,
        "protection": protection,
    }
    return outputs


def main() -> None:
    outputs = build_all()
    for key, value in outputs.items():
        write_json(OUTPUTS[key], value)
    print(json.dumps({
        "stage": "ml0",
        "outputs": [str(path) for path in OUTPUTS.values()],
        "metrics": outputs["metrics"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
