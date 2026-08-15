#!/usr/bin/env python3
"""Validate the H0C historical-context and graph-readiness projections.

H0C is deliberately a derived layer.  This validator checks that it is
referentially safe, provenance-aware, temporally explicit, and unable to
silently widen the protected H0B-1 corpus.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

try:
    from .build_h0c_historical_context import (
        ALIASES_PATH,
        ANCHORS_PATH,
        H0B0_INPUTS,
        H0B1_BACKBONE_PATH,
        H0B1_CONSTRAINTS_PATH,
        H0B1_PARTICIPANTS_PATH,
        OUTPUTS,
        PEOPLE_PATH,
        PERSON_STORY_PATH,
        SC1_PATH,
        SCENE_CONTEXT_PATH,
        EFFECTIVE_MENTIONS_PATH,
        PERSON_IDENTITY_CANDIDATES_PATH,
        ENTITY_ID_MANIFEST_PATH,
        load_inputs,
        read_json,
        sha256_file,
    )
except ImportError:
    from build_h0c_historical_context import (
        ALIASES_PATH,
        ANCHORS_PATH,
        H0B0_INPUTS,
        H0B1_BACKBONE_PATH,
        H0B1_CONSTRAINTS_PATH,
        H0B1_PARTICIPANTS_PATH,
        OUTPUTS,
        PEOPLE_PATH,
        PERSON_STORY_PATH,
        SC1_PATH,
        SCENE_CONTEXT_PATH,
        EFFECTIVE_MENTIONS_PATH,
        PERSON_IDENTITY_CANDIDATES_PATH,
        ENTITY_ID_MANIFEST_PATH,
        load_inputs,
        read_json,
        sha256_file,
    )


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = Path("schema/h0c-historical-context.schema.json")
ROLE_SET = {"present", "speaker", "actor", "referenced", "off_frame", "annotation_only", "uncertain"}
HARD_ROLES = {"present", "speaker", "actor"}


def validate_schema(value: Any, label: str) -> list[str]:
    schema = read_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    return [f"{label}: {error.message}" for error in Draft202012Validator(schema).iter_errors(value)]


def unique_ids(rows: list[Mapping[str, Any]], key: str) -> bool:
    values = [str(row.get(key)) for row in rows]
    return len(values) == len(set(values))


def evidence_ids(rows: list[Mapping[str, Any]]) -> set[str]:
    return {str(value) for row in rows for value in row.get("evidence_ids", [])}


def validate() -> list[str]:
    errors: list[str] = []
    try:
        inputs = load_inputs()
        artifacts = {name: read_json(path) for name, path in OUTPUTS.items()}
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return [f"H0C artifacts cannot be read: {exc}"]

    for name, artifact in artifacts.items():
        errors.extend(validate_schema(artifact, f"H0C {name}"))
    errors.extend(validate_schema(inputs["entity_manifest"], "H0C entity ID manifest"))

    people = set(inputs["people_by_id"])
    stories = set(inputs["story_by_id"])
    evidence = set(inputs["evidence_by_id"])
    freeze = artifacts["participant_freeze"]
    locations = artifacts["locations"]
    offices = artifacts["offices"]
    events = artifacts["events"]
    regimes = artifacts["regimes"]
    activities = artifacts["person_activities"]
    event_participations = artifacts["event_participations"]
    location_facts = artifacts["location_facts"]
    service_contexts = artifacts["service_contexts"]
    historical_facts = artifacts["historical_facts"]
    graph = artifacts["graph"]
    graph_audit = artifacts["graph_audit"]
    gaps = artifacts["gaps"]
    readiness = artifacts["readiness"]
    protection = artifacts["protection"]
    metrics = artifacts["metrics"]

    # Protected corpus and source layers.
    protected = protection.get("protected_counts", {})
    expected = {
        "production_person_count": 75,
        "production_story_count": 143,
        "person_story_link_count": 875,
        "reviewed_person_story_link_count": 870,
        "reviewed_relation_count": 12,
        "scene_context_count": 44,
        "orphan_mention_count": 0,
        "primary_era_orientation_count": 143,
    }
    for key, value in expected.items():
        if protected.get(key) != value:
            errors.append(f"protected metric {key}={protected.get(key)!r}, expected {value!r}")
    if len(people) != 75 or len(stories) != 143:
        errors.append("H0C input scope is not exactly 75 Persons / 143 Stories")
    if len(inputs["relations"]) != 12:
        errors.append("reviewed Relation count changed from 12")
    for name, path in {
        "people": PEOPLE_PATH,
        "aliases": ALIASES_PATH,
        "person_story": PERSON_STORY_PATH,
        "sc1_site": SC1_PATH,
        "h0a_anchors": ANCHORS_PATH,
        "effective_mentions": EFFECTIVE_MENTIONS_PATH,
        "identity_candidates": PERSON_IDENTITY_CANDIDATES_PATH,
        "entity_id_manifest": ENTITY_ID_MANIFEST_PATH,
        "h0b1_participants": H0B1_PARTICIPANTS_PATH,
        "h0b1_backbone": H0B1_BACKBONE_PATH,
        "h0b1_constraints": H0B1_CONSTRAINTS_PATH,
    }.items():
        expected_hash = protection.get("protected_hashes", {}).get(name)
        if expected_hash and sha256_file(path) != expected_hash:
            errors.append(f"protected input hash changed: {name}")
    for name, path in H0B0_INPUTS.items():
        expected_hash = protection.get("frozen_h0b0_hashes", {}).get(name)
        if expected_hash and sha256_file(path) != expected_hash:
            errors.append(f"frozen H0B-0 hash changed: {name}")
    if protection.get("baseline_commit") != "001ae6043f39e9e78d7677c14fd318a7b4124634":
        errors.append("H0C protection manifest baseline commit is incorrect")

    # Participant freeze: all Story records, fixed semantic roles, and hard
    # participant provenance.  The input H0B-1 projection is not rewritten.
    participant_rows = freeze.get("records", [])
    if len(freeze.get("story_records", [])) != 143 or {str(row.get("story_id")) for row in freeze.get("story_records", [])} != stories:
        errors.append("participant freeze does not cover exactly all production Stories")
    if not unique_ids(participant_rows, "participant_id"):
        errors.append("duplicate H0C participant IDs")
    for row in participant_rows:
        story_id, person_id, role = str(row.get("story_id")), str(row.get("person_id")), row.get("role")
        if story_id not in stories or person_id not in people:
            errors.append(f"participant endpoint outside production scope: {row.get('participant_id')}")
        if role not in ROLE_SET:
            errors.append(f"unknown participant role: {row.get('participant_id')}")
        if bool(row.get("hard_temporal_eligible")) != (role in HARD_ROLES):
            errors.append(f"participant hard-role mismatch: {row.get('participant_id')}")
        if row.get("review_status") != "reviewed":
            errors.append(f"participant role is not reviewed/frozen: {row.get('participant_id')}")
        if role == "uncertain" and row.get("review_status") != "reviewed":
            errors.append(f"unreviewed participant uncertainty: {row.get('participant_id')}")
        if role in HARD_ROLES and not row.get("provenance_complete"):
            errors.append(f"hard participant lacks complete provenance: {row.get('participant_id')}")
        missing = sorted(set(row.get("evidence_ids", [])) - evidence)
        if missing:
            errors.append(f"participant {row.get('participant_id')} references missing Evidence: {missing}")
    effective = inputs["effective"]
    for group in ("mentions", "derived_mentions"):
        for mention in effective.get(group, []):
            if mention.get("source_id") == "08-shangyu-079" and mention.get("surface") == "望之" and mention.get("person_id") == "person-029":
                errors.append("lexical 望之 re-entered effective Person identity")
    if any(row.get("story_id") == "08-shangyu-079" and row.get("person_id") == "person-029" for row in participant_rows):
        errors.append("lexical 望之 re-entered H0C participant freeze")

    # Reusable entities.
    location_rows = locations.get("records", [])
    office_rows = offices.get("entities", [])
    tenure_rows = offices.get("tenures", [])
    event_rows = events.get("records", [])
    regime_rows = regimes.get("records", [])
    if not unique_ids(location_rows, "location_id"):
        errors.append("duplicate Location IDs")
    if not unique_ids(office_rows, "office_id") or not unique_ids(tenure_rows, "tenure_id"):
        errors.append("duplicate Office or OfficeTenure IDs")
    if not unique_ids(event_rows, "event_id") or not unique_ids(regime_rows, "regime_id"):
        errors.append("duplicate Event or Regime IDs")
    location_ids = {str(row.get("location_id")) for row in location_rows}
    office_ids = {str(row.get("office_id")) for row in office_rows}
    event_ids = {str(row.get("event_id")) for row in event_rows}
    regime_ids = {str(row.get("regime_id")) for row in regime_rows}
    manifest_rows = inputs.get("entity_manifest", {}).get("records", [])
    manifest_keys = {(str(row.get("entity_type")), str(row.get("semantic_key"))): str(row.get("entity_id")) for row in manifest_rows}
    manifest_ids = [str(row.get("entity_id")) for row in manifest_rows]
    if len(manifest_ids) != len(set(manifest_ids)) or len(manifest_keys) != len(manifest_rows):
        errors.append("H0C entity ID manifest has duplicate keys or IDs")
    expected_location_ids = {entity_id for (kind, _), entity_id in manifest_keys.items() if kind == "Location"}
    expected_office_ids = {entity_id for (kind, _), entity_id in manifest_keys.items() if kind == "Office"}
    expected_regime_ids = {entity_id for (kind, _), entity_id in manifest_keys.items() if kind == "Regime"}
    if location_ids != expected_location_ids or office_ids != expected_office_ids or regime_ids != expected_regime_ids:
        errors.append("H0C normalized entity IDs do not match the frozen ID manifest")
    for row in location_rows:
        if row.get("modern_mapping", {}).get("status") == "unknown" and any(row.get("modern_mapping", {}).get(key) is not None for key in ("latitude", "longitude")):
            errors.append(f"unknown Location has coordinates: {row.get('location_id')}")
        missing = sorted(set(row.get("evidence_ids", [])) - evidence)
        if missing:
            errors.append(f"Location {row.get('location_id')} references missing Evidence: {missing}")
    for row in tenure_rows:
        if row.get("person_id") not in people or row.get("office_id") not in office_ids:
            errors.append(f"OfficeTenure endpoint invalid: {row.get('tenure_id')}")
        for key in ("location_id", "jurisdiction_location_id"):
            if row.get(key) and row.get(key) not in location_ids:
                errors.append(f"OfficeTenure {row.get('tenure_id')} references unknown Location")
        start, end = row.get("start_year_ce"), row.get("end_year_ce")
        if start is not None and end is not None and start > end:
            errors.append(f"reversed OfficeTenure interval: {row.get('tenure_id')}")
        if row.get("temporal_precision") == "unknown" and any(row.get(key) is not None for key in ("start_year_ce", "end_year_ce", "lower_bound_year_ce", "upper_bound_year_ce")):
            errors.append(f"unknown OfficeTenure has invented bounds: {row.get('tenure_id')}")
        if not row.get("office_title") or not row.get("evidence_ids"):
            errors.append(f"OfficeTenure lacks title/Evidence: {row.get('tenure_id')}")
    for row in event_rows:
        if row.get("start_year_ce") is not None and row.get("end_year_ce") is not None and row["start_year_ce"] > row["end_year_ce"]:
            errors.append(f"reversed Event interval: {row.get('event_id')}")
        if set(row.get("location_ids", [])) - location_ids or set(row.get("evidence_ids", [])) - evidence:
            errors.append(f"Event references unknown Location/Evidence: {row.get('event_id')}")
    for row in office_rows:
        if set(row.get("tenure_ids", [])) - {str(item.get("tenure_id")) for item in tenure_rows}:
            errors.append(f"Office has dangling tenure reference: {row.get('office_id')}")

    # Reused facts and the canonical fact index.
    for artifact_name, rows, id_key in (
        ("person activity", activities.get("records", []), "activity_id"),
        ("event participation", event_participations.get("records", []), "event_participation_id"),
        ("location fact", location_facts.get("records", []), "location_fact_id"),
        ("service context", service_contexts.get("records", []), "service_context_fact_id"),
    ):
        if not unique_ids(rows, id_key):
            errors.append(f"duplicate H0C {artifact_name} IDs")
        for row in rows:
            missing = sorted(set(row.get("evidence_ids", [])) - evidence)
            if missing:
                errors.append(f"{artifact_name} {row.get(id_key)} references missing Evidence: {missing}")
    for row in event_participations.get("records", []):
        if row.get("person_id") not in people or row.get("event_id") not in event_ids or row.get("story_id") not in stories:
            errors.append(f"event participation endpoint invalid: {row.get('event_participation_id')}")
        if bool(row.get("hard_temporal_eligible")) != (row.get("story_role") in HARD_ROLES):
            errors.append(f"event participation hard-role mismatch: {row.get('event_participation_id')}")
    fact_rows = historical_facts.get("fact_index", [])
    if historical_facts.get("fact_count") != len(fact_rows) or not unique_ids(fact_rows, "fact_key"):
        errors.append("historical fact index count or IDs are not unique")
    for row in fact_rows:
        unknown_anchor = row.get("fact_type") == "story_temporal_anchor" and row.get("temporal_precision") == "unknown"
        if not row.get("evidence_ids") and not row.get("provenance_refs") and not unknown_anchor:
            errors.append(f"historical fact has no evidence/provenance: {row.get('fact_key')}")
        if set(row.get("evidence_ids", [])) - evidence:
            errors.append(f"historical fact references missing Evidence: {row.get('fact_key')}")

    # Graph: endpoints, fact/evidence traceability, and no synthetic negative
    # edges.  Orphan nodes and identity collisions are reported gaps, not
    # validation failures.
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_keys = {(str(row.get("node_type")), str(row.get("node_id"))) for row in nodes}
    fact_keys = {str(row.get("fact_key")) for row in fact_rows}
    if len(node_keys) != len(nodes) or not unique_ids(edges, "edge_id"):
        errors.append("graph node or edge IDs are not unique")
    for edge in edges:
        source = (str(edge.get("source", {}).get("node_type")), str(edge.get("source", {}).get("node_id")))
        target = (str(edge.get("target", {}).get("node_type")), str(edge.get("target", {}).get("node_id")))
        if source not in node_keys or target not in node_keys:
            errors.append(f"graph edge has dangling endpoint: {edge.get('edge_id')}")
        if edge.get("edge_status") != "materialized":
            errors.append(f"graph edge is not materialized: {edge.get('edge_id')} / {edge.get('edge_status')}")
        if edge.get("assertion_status") != "derived" or not edge.get("review_status") or not edge.get("uncertainty_state"):
            errors.append(f"graph edge lacks explicit uncertainty metadata: {edge.get('edge_id')}")
        if not edge.get("source_facts") or not (edge.get("evidence_ids") or edge.get("provenance_refs")):
            errors.append(f"graph edge lacks traceability: {edge.get('edge_id')}")
        for ref in edge.get("source_facts", []):
            if ref.get("fact_key") not in fact_keys:
                errors.append(f"graph edge references missing fact: {edge.get('edge_id')} -> {ref.get('fact_key')}")
        temporal = edge.get("temporal", {})
        start, end = temporal.get("start_year_ce"), temporal.get("end_year_ce")
        if start is not None and end is not None and start > end:
            errors.append(f"graph edge interval is reversed: {edge.get('edge_id')}")
    audit_counts = graph_audit.get("issue_counts", {})
    for key in ("dangling_edges", "dangling_fact_references", "unsupported_edges", "duplicate_semantic_edges", "family_cycle_anomalies", "temporal_conflicts"):
        if audit_counts.get(key, 0) != 0:
            errors.append(f"graph audit reports invalid {key}: {audit_counts.get(key)}")
    if graph_audit.get("scope", {}).get("person_story_links_out_of_production_scope") != 545:
        errors.append("out-of-scope PersonStory link audit is not the expected 545")

    # Gap catalog and readiness contract.
    if gaps.get("summary", {}).get("resolved_by_participant_freeze") != 130:
        errors.append("H0B-1 participant-role gap reconciliation is incomplete")
    if {str(row.get("person_id")) for row in readiness.get("person_records", [])} != people:
        errors.append("ML readiness audit does not cover all 75 Persons")
    contract = readiness.get("contract", {})
    if not contract.get("framework_neutral") or contract.get("model_artifacts_generated") or contract.get("embeddings_generated") or contract.get("training_split_generated"):
        errors.append("H0C ML contract indicates framework/model artifacts were generated")
    if contract.get("missing_edge_policy") != "missing edge is unknown, not negative evidence":
        errors.append("H0C missing-edge policy is not explicit")
    if metrics.get("future_boundary") != {"hg0_implemented": False, "ml_implemented": False, "er2_implemented": False}:
        errors.append("H0C future boundary was not preserved")
    if metrics.get("protected") != protected:
        errors.append("H0C metrics and protection manifest disagree")

    # H0C must not rewrite H0B-1/H0A inputs.
    for label, path in {
        "h0b1_participants": H0B1_PARTICIPANTS_PATH,
        "h0b1_backbone": H0B1_BACKBONE_PATH,
        "h0b1_constraints": H0B1_CONSTRAINTS_PATH,
        "h0a_anchors": ANCHORS_PATH,
    }.items():
        if metrics.get("input_hashes", {}).get(label) != sha256_file(path):
            errors.append(f"H0C input hash mismatch: {label}")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    metrics = read_json(OUTPUTS["metrics"])
    print(
        "H0C validation passed: "
        f"{metrics['scope']['persons']} Persons, {metrics['scope']['stories']} Stories, "
        f"{metrics['entities']['Location']} Locations, {metrics['graph']['edge_count']} graph edges; "
        "protected H0B-1/H0A inputs unchanged"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
