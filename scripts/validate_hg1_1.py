#!/usr/bin/env python3
"""Validate the HG1.1 reviewed relation/temporal projections.

HG1.1 is deliberately validated as a downstream projection.  The validator
checks that every new edge is traceable to a reviewed relation or inherited
reviewed extension fact, while the protected H0C/HG0/ML0 inputs remain
unchanged.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_hg1_1_historical_densification import (  # noqa: E402
    DIRECT_EDGE_TYPES,
    INPUTS,
    OUTPUTS,
    read_json,
    sha256_file,
)


def load_output(name: str) -> Any:
    path = ROOT / OUTPUTS[name]
    return read_json(OUTPUTS[name])


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def validate() -> list[str]:
    errors: list[str] = []
    for name, path in OUTPUTS.items():
        if not (ROOT / path).is_file():
            fail(errors, f"missing output: {path}")
    for name, path in INPUTS.items():
        if not (ROOT / path).is_file():
            fail(errors, f"missing input: {path}")
    if errors:
        return errors

    outputs = {name: load_output(name) for name in OUTPUTS}
    inputs = {name: read_json(path) for name, path in INPUTS.items()}
    sc1 = inputs["sc1"]
    person_ids = {str(row.get("id")) for row in sc1.get("people", [])}
    story_ids = {str(row.get("id")) for row in sc1.get("stories", [])}
    reviewed_relations = {
        str(row.get("id")): row
        for row in sc1.get("relations", [])
        if row.get("review_status") == "reviewed"
    }
    h0c_facts = {
        str(row.get("fact_id")): row
        for row in inputs["h0c_facts"].get("fact_index", [])
    }
    service_facts = {
        str(row.get("service_context_fact_id")): row
        for row in inputs["h0c_service"].get("records", [])
    }
    x1_facts = {
        str(row.get("fact_id")): row
        for row in outputs["fact_extension"].get("facts", [])
    }

    # Every recorded source hash is relative and current.  This catches an
    # accidental rebuild against a changed upstream artifact before it can be
    # mistaken for an HG1.1 result.
    for document_name in ("relation_candidates", "relation_review", "relation_materialization", "temporal_constraints"):
        for relative, expected in outputs[document_name].get("source_hashes", {}).items():
            path = ROOT / relative
            if Path(relative).is_absolute():
                fail(errors, f"{document_name} contains an absolute source path: {relative}")
            elif not path.is_file() or sha256_file(Path(relative)) != expected:
                fail(errors, f"{document_name} source hash mismatch: {relative}")

    candidates = outputs["relation_candidates"]
    candidate_rows = list(candidates.get("records", []))
    source_scan = list(candidates.get("source_scan", []))
    if len({str(row.get("candidate_id")) for row in candidate_rows + source_scan}) != len(candidate_rows) + len(source_scan):
        fail(errors, "relation candidate IDs are not unique")
    if candidates.get("candidate_count") != len(candidate_rows) + len(source_scan):
        fail(errors, "relation candidate count does not match records plus source scan")
    if candidates.get("scope", {}).get("production_person_count") != 75 or candidates.get("scope", {}).get("production_story_count") != 143:
        fail(errors, "relation candidate scope is not the protected 75-person/143-story universe")
    if candidates.get("scope", {}).get("selected_x1_1_story_count") != 20:
        fail(errors, "relation candidate scope does not retain the frozen 20-Story selection")
    if any(row.get("review_status") != "unresolved" for row in source_scan):
        fail(errors, "Jianshu relation scan contains a materialized source-scan candidate")
    if any(row.get("cooccurrence_only") for row in candidate_rows + source_scan):
        fail(errors, "co-occurrence-only material was treated as a relation candidate")

    review = outputs["relation_review"]
    review_rows = list(review.get("records", []))
    if len({str(row.get("review_item_id")) for row in review_rows}) != len(review_rows):
        fail(errors, "relation review item IDs are not unique")
    if any(row.get("review_status") not in {"accepted", "unresolved", "rejected"} for row in review_rows):
        fail(errors, "relation review contains an invalid review status")
    if review.get("counts", {}).get("accepted") != sum(row.get("review_status") == "accepted" for row in review_rows):
        fail(errors, "relation review accepted count is inconsistent")
    for row in review_rows:
        if row.get("review_status") == "accepted":
            relation_id = str(row.get("relation_id"))
            if relation_id not in reviewed_relations:
                fail(errors, f"accepted relation review is not backed by a reviewed SC1 relation: {relation_id}")
            if str(row.get("subject_id")) not in person_ids or str(row.get("object_id")) not in person_ids:
                fail(errors, f"accepted relation review has an invalid endpoint: {relation_id}")
            if not row.get("evidence_ids"):
                fail(errors, f"accepted relation review has no evidence: {relation_id}")
        if row.get("review_status") == "unresolved" and row.get("relation_id") is not None:
            fail(errors, "unresolved relation review unexpectedly has a materialized relation ID")

    materialization = outputs["relation_materialization"]
    materialized_rows = list(materialization.get("records", []))
    materialized_ids = {str(row.get("relation_id")) for row in materialized_rows}
    if len(materialized_ids) != len(materialized_rows):
        fail(errors, "materialized relation IDs are not unique")
    if materialization.get("counts", {}).get("new_canonical_relation_facts") != 0:
        fail(errors, "HG1.1 unexpectedly created new canonical relation facts")
    for row in materialized_rows:
        relation_id = str(row.get("relation_id"))
        if relation_id not in reviewed_relations:
            fail(errors, f"materialized relation is not an existing reviewed relation: {relation_id}")
        if row.get("review_status") != "reviewed" or row.get("materialization_status") != "inherited_h0c_canonical_fact":
            fail(errors, f"materialized relation is not marked as inherited reviewed data: {relation_id}")
        if str(row.get("subject_id")) not in person_ids or str(row.get("object_id")) not in person_ids:
            fail(errors, f"materialized relation endpoint is invalid: {relation_id}")
        if not row.get("provenance_refs") or not row.get("evidence_ids"):
            fail(errors, f"materialized relation lacks provenance/evidence: {relation_id}")
    direct_additions = [row for row in materialized_rows if row.get("direct_projection_status") == "add_hg1_1_direct_edge"]
    if {row.get("relation_id") for row in direct_additions} != {"relation-r3b-003", "relation-r3b-004", "relation-r3b-005"}:
        fail(errors, "HG1.1 direct relation projection set changed")

    fact_extension = outputs["fact_extension"]
    for fact_id, fact in x1_facts.items():
        if fact.get("review_status") != "reviewed" or fact.get("review_decision") != "accepted":
            fail(errors, f"inherited extension fact is not reviewed/accepted: {fact_id}")
        if not fact.get("evidence_ids") or not fact.get("provenance_refs"):
            fail(errors, f"inherited extension fact lacks evidence/provenance: {fact_id}")
    if fact_extension.get("counts", {}).get("new_canonical_facts_created_by_hg1_1") != 0:
        fail(errors, "HG1.1 fact extension claims newly created canonical facts")

    ontology = outputs["ontology"]
    hg0_ontology = inputs["hg0_ontology"]
    if ontology.get("hg0_ontology_sha256") != sha256_file(INPUTS["hg0_ontology"]):
        fail(errors, "HG1.1 ontology does not identify the current HG0 ontology")
    added_edge_types = {str(row.get("edge_type")) for row in ontology.get("edge_types", [])} - {
        str(row.get("edge_type")) for row in hg0_ontology.get("edge_types", [])
    }
    if added_edge_types != {"relation_institutional", "relation_political"}:
        fail(errors, f"unexpected HG1.1 ontology extension: {sorted(added_edge_types)}")

    graph = outputs["graph"]
    hg0 = inputs["hg0_graph"]
    if graph.get("hg0_input_sha256") != sha256_file(INPUTS["hg0_graph"]):
        fail(errors, "HG1.1 graph does not identify the current HG0 graph")
    if len(graph.get("nodes", [])) != len(hg0.get("nodes", [])) + 2:
        fail(errors, "HG1.1 graph node delta is not the reviewed X1 extension delta")
    if len(graph.get("edges", [])) != len(hg0.get("edges", [])) + 8:
        fail(errors, "HG1.1 graph edge delta is not the reviewed extension/direct-relation delta")
    node_keys = {(str(row.get("node_type")), str(row.get("node_id"))) for row in graph.get("nodes", [])}
    if len(node_keys) != len(graph.get("nodes", [])):
        fail(errors, "HG1.1 node keys are not unique")
    edge_ids = [str(row.get("edge_id")) for row in graph.get("edges", [])]
    semantic_keys = [str(row.get("semantic_key")) for row in graph.get("edges", [])]
    if len(set(edge_ids)) != len(edge_ids) or len(set(semantic_keys)) != len(semantic_keys):
        fail(errors, "HG1.1 edge IDs or semantic keys are duplicated")
    edge_types = {str(row.get("edge_type")) for row in ontology.get("edge_types", [])}
    hg0_edge_ids = {str(row.get("edge_id")) for row in hg0.get("edges", [])}
    for edge in graph.get("edges", []):
        source = (str(edge.get("source", {}).get("node_type")), str(edge.get("source", {}).get("node_id")))
        target = (str(edge.get("target", {}).get("node_type")), str(edge.get("target", {}).get("node_id")))
        if source not in node_keys or target not in node_keys:
            fail(errors, f"HG1.1 edge has a dangling endpoint: {edge.get('edge_id')}")
        if edge.get("edge_type") not in edge_types:
            fail(errors, f"HG1.1 edge type is absent from ontology: {edge.get('edge_type')}")
        # HG0 edges are inherited verbatim and retain their original
        # epistemic fields.  The HG1.1 review-status requirement applies to
        # newly added projection edges only.
        if str(edge.get("edge_id")) not in hg0_edge_ids:
            if edge.get("review_status") != "reviewed":
                fail(errors, f"new HG1.1 edge is not reviewed: {edge.get('edge_id')}")
            source_fact_ids = {str(value) for value in edge.get("fact_ids", [])}
            if not source_fact_ids.intersection(materialized_ids | set(x1_facts) | set(service_facts)):
                fail(errors, f"new HG1.1 edge lacks a reviewed source fact: {edge.get('edge_id')}")
            if not edge.get("evidence_ids"):
                fail(errors, f"new HG1.1 edge lacks evidence: {edge.get('edge_id')}")
    new_direct = [
        edge for edge in graph.get("edges", [])
        if str(edge.get("edge_id")) not in hg0_edge_ids
        and edge.get("source", {}).get("node_type") == "Person"
        and edge.get("target", {}).get("node_type") == "Person"
        and edge.get("projection_role") == "semantic_direct"
    ]
    if len(new_direct) != 3 or {edge.get("edge_type") for edge in new_direct} != {"relation_institutional", "relation_political"}:
        fail(errors, "HG1.1 direct Person relation edge delta is invalid")

    temporal = outputs["temporal_constraints"]
    temporal_rows = list(temporal.get("records", []))
    if len(temporal_rows) != 143 or {str(row.get("story_id")) for row in temporal_rows} != story_ids:
        fail(errors, "HG1.1 temporal projection is not exactly the production Story universe")
    if temporal.get("counts", {}).get("person_tenure_only_resolutions") != 0:
        fail(errors, "HG1.1 temporal projection used Person tenure alone to date a Story")
    for row in temporal_rows:
        if row.get("resolution_status") == "resolved":
            if row.get("review_status") != "reviewed" or not row.get("source_fact_ids"):
                fail(errors, f"resolved temporal Story row lacks reviewed source provenance: {row.get('story_id')}")
            if row.get("start_year_ce") is None or row.get("end_year_ce") is None:
                fail(errors, f"resolved temporal Story row lacks an interval: {row.get('story_id')}")
            if int(row["start_year_ce"]) > int(row["end_year_ce"]):
                fail(errors, f"resolved temporal Story row has an inverted interval: {row.get('story_id')}")
        elif row.get("resolution_status") == "unknown":
            if row.get("review_status") != "unresolved" or row.get("start_year_ce") is not None or row.get("end_year_ce") is not None:
                fail(errors, f"unknown temporal Story row contains an unsupported interval: {row.get('story_id')}")
        else:
            fail(errors, f"invalid temporal resolution state: {row.get('story_id')}")
    temporal_projection = outputs["temporal_projection"]
    if len(temporal_projection.get("edge_temporal_index", [])) != len(graph.get("edges", [])):
        fail(errors, "HG1.1 temporal edge projection does not cover the graph")

    delta = outputs["delta"]
    if delta.get("from", {}).get("sha256") != sha256_file(INPUTS["hg0_graph"]):
        fail(errors, "HG0→HG1.1 delta does not identify the current HG0 graph")
    if delta.get("counts", {}).get("added_edges") != 8 or delta.get("counts", {}).get("added_nodes") != 2:
        fail(errors, "HG0→HG1.1 delta counts are inconsistent")

    protection = outputs["protection"]
    for relative, expected in protection.get("protected_input_hashes", {}).items():
        path = ROOT / relative
        if not path.is_file() or sha256_file(Path(relative)) != expected:
            fail(errors, f"HG1.1 protected input hash mismatch: {relative}")
    if any(protection.get("write_back", {}).values()):
        fail(errors, "HG1.1 protection manifest permits write-back")
    protected_counts = protection.get("protected_counts", {})
    if protected_counts.get("h0c_fact_count") != len(h0c_facts):
        fail(errors, "HG1.1 H0C fact count does not match current protected input")
    if protected_counts.get("hg0_node_count") != len(hg0.get("nodes", [])) or protected_counts.get("hg0_edge_count") != len(hg0.get("edges", [])):
        fail(errors, "HG1.1 protected HG0 counts do not match current input")

    hg0_protection = inputs["hg0_protection"]
    for name, expected in hg0_protection.get("h0c_input_hashes", {}).items():
        path = INPUTS.get(name)
        if path and sha256_file(path) != expected:
            fail(errors, f"H0C protected input changed: {name}")
    ml0_protection = Path("data/derived/ml0-protection-manifest.json")
    if ml0_protection.exists():
        ml0 = read_json(ml0_protection)
        if ml0.get("hg0_input_hashes", {}).get("graph") != sha256_file(INPUTS["hg0_graph"]):
            fail(errors, "ML0 protected HG0 graph hash changed")
        if any(ml0.get(key) for key in ("canonical_negative_facts_generated", "model_checkpoints_generated", "embeddings_persisted")):
            fail(errors, "ML0 protection manifest reports forbidden artifacts")

    readiness = outputs["ml_readiness"]
    if readiness.get("ml1_1_recommendation") != "defer_training_until_hg1_1_snapshot_is_reviewed":
        fail(errors, "HG1.1 does not defer ML1.1")
    if any(value in json.dumps(readiness, ensure_ascii=False) for value in ["embedding", "negative_samples", "political_factions", "historical_importance_ranking"]):
        # These names are allowed only in the explicit forbidden-output list;
        # no generated model artifact may appear anywhere else.
        if readiness.get("forbidden_outputs") != ["embeddings", "negative_samples", "political_factions", "historical_importance_ranking"]:
            fail(errors, "HG1.1 readiness contains unexpected ML output")

    ux_delta = outputs["ux_delta"]
    manifest_path = Path("site/public/generated/history/manifest.json")
    if ux_delta.get("after_manifest_sha256") != sha256_file(manifest_path):
        fail(errors, "HG1.1 UX coverage delta does not identify the current UX1 manifest")
    if ux_delta.get("after", {}).get("story_temporal_context_rows", 0) < ux_delta.get("before", {}).get("story_temporal_context_rows", 0):
        fail(errors, "HG1.1 reduced UX1 temporal coverage")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    graph = load_output("graph")
    temporal = load_output("temporal_constraints")
    relation = load_output("relation_review")
    print(json.dumps({
        "status": "pass",
        "graph": {"nodes": len(graph.get("nodes", [])), "edges": len(graph.get("edges", []))},
        "relation_review": relation.get("counts", {}),
        "temporal": temporal.get("counts", {}),
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
