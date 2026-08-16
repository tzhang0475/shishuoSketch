#!/usr/bin/env python3
"""Build HG0, the deterministic Historical Graph foundation.

HG0 is deliberately a projection layer over the frozen H0C entities and
facts.  It defines graph scope, typed/multiplex edges, reification policy,
interval-aware temporal reconstruction, sufficiency/bias audits, and a
framework-neutral ML0 contract.  It never edits canonical historical facts.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path
from statistics import fmean, median
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
BASELINE_H0C_COMMIT = "4854d3d1997300c9039d8093c0c7114cb00c47d1"

INPUTS = {
    "h0c_graph": Path("data/derived/h0c-graph-projection.json"),
    "h0c_audit": Path("data/derived/h0c-graph-audit.json"),
    "h0c_facts": Path("data/derived/h0c-historical-facts.json"),
    "h0c_participants": Path("data/derived/h0c-participant-freeze.json"),
    "h0c_locations": Path("data/derived/h0c-locations.json"),
    "h0c_location_facts": Path("data/derived/h0c-location-facts.json"),
    "h0c_offices": Path("data/derived/h0c-offices.json"),
    "h0c_activities": Path("data/derived/h0c-person-activities.json"),
    "h0c_event_participations": Path("data/derived/h0c-event-participations.json"),
    "h0c_events": Path("data/derived/h0c-events.json"),
    "h0c_service": Path("data/derived/h0c-service-political-facts.json"),
    "h0c_readiness": Path("data/derived/h0c-ml-readiness.json"),
    "h0c_protection": Path("data/derived/h0c-protection-manifest.json"),
    "h0c_entity_manifest": Path("data/annotation/h0c-entity-id-manifest.json"),
    "person_story_links": Path("data/derived/person-story-links.json"),
    "sc1_site": Path("data/derived/sc1-site.json"),
    "people": Path("data/people.json"),
}

OUTPUTS = {
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


def read_json(relative: Path) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def write_json(relative: Path, value: Any) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(relative: Path) -> str:
    digest = hashlib.sha256()
    with (ROOT / relative).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_value(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def stable_id(prefix: str, *parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def unique(values: Iterable[object]) -> list[str]:
    return sorted({str(value) for value in values if value is not None and str(value)})


def node_key(node_type: object, node_id: object) -> str:
    return f"{node_type}:{node_id}"


def edge_endpoint_key(endpoint: Mapping[str, Any]) -> tuple[str, str]:
    return str(endpoint["node_type"]), str(endpoint["node_id"])


def records(document: Mapping[str, Any], key: str = "records") -> list[dict[str, Any]]:
    value = document.get(key, [])
    return [dict(item) for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def integer_or_none(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalized_temporal(row: Mapping[str, Any] | None, *, basis: str = "unknown") -> dict[str, Any]:
    row = row or {}
    precision = row.get("precision", row.get("temporal_precision", "unknown"))
    start = integer_or_none(row.get("start_year_ce", row.get("lower_bound_year_ce")))
    end = integer_or_none(row.get("end_year_ce", row.get("upper_bound_year_ce")))
    precision = str(precision or "unknown")
    if start is not None and end is not None:
        state = "bounded"
    elif start is not None or end is not None:
        state = "one_sided"
    elif precision in {"sequence_bounded", "relative", "relative_only"}:
        state = "relative_only"
    else:
        state = "unknown"
    return {
        "start_year_ce": start,
        "end_year_ce": end,
        "precision": precision,
        "basis": str(row.get("basis", basis)),
        "temporal_state": state,
    }


def interval_overlaps(temporal: Mapping[str, Any], start_year_ce: int, end_year_ce: int) -> bool:
    """Return whether a bounded fact may be active in an inclusive interval."""
    start = integer_or_none(temporal.get("start_year_ce"))
    end = integer_or_none(temporal.get("end_year_ce"))
    if start is None and end is None:
        return False
    if start is None:
        return end >= start_year_ce
    if end is None:
        return start <= end_year_ce
    return start <= end_year_ce and end >= start_year_ce


H0C_DIRECT_KEEP = {
    "event_contextualizes_story",
    "kinship_collateral_kinship",
    "kinship_uncle_niece",
    "member_of_clan",
    "office_at_location",
    "office_in_regime",
    "parent_of",
    "person_story_link",
    "relation_kinship",
    "relation_social",
    "spouse_union",
    "story_participant_actor",
    "story_participant_annotation_only",
    "story_participant_off_frame",
    "story_participant_present",
    "story_participant_referenced",
    "story_present_at",
}

REIFIED_SOURCE_TYPES = {
    "office_tenure": "OfficeTenure",
    "person_activity": "PersonActivity",
    "event_participation": "EventParticipation",
    "service_political": "ServicePoliticalFact",
}

EDGE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "person_story_link": {"source": "Person", "target": "Story", "layer": "story", "symmetric": False, "meaning": "PersonStory index link; not participation by itself."},
    "story_participant_present": {"source": "Person", "target": "Story", "layer": "story", "symmetric": False, "meaning": "Reviewed hard scene presence."},
    "story_participant_speaker": {"source": "Person", "target": "Story", "layer": "story", "symmetric": False, "meaning": "Reviewed hard speaker role."},
    "story_participant_actor": {"source": "Person", "target": "Story", "layer": "story", "symmetric": False, "meaning": "Reviewed hard actor role."},
    "story_participant_referenced": {"source": "Person", "target": "Story", "layer": "story", "symmetric": False, "meaning": "Contextual reference; not hard presence."},
    "story_participant_off_frame": {"source": "Person", "target": "Story", "layer": "story", "symmetric": False, "meaning": "Named outside the scene frame."},
    "story_participant_annotation_only": {"source": "Person", "target": "Story", "layer": "story", "symmetric": False, "meaning": "Liu/biographical context only."},
    "story_present_at": {"source": "Story", "target": "Location", "layer": "geographic", "symmetric": False, "meaning": "Story scene location."},
    "parent_of": {"source": "Person", "target": "Person", "layer": "family", "symmetric": False, "meaning": "Canonical directional parent-child fact."},
    "kinship_collateral_kinship": {"source": "Person", "target": "Person", "layer": "family", "symmetric": False, "meaning": "Explicit collateral kinship projection."},
    "kinship_uncle_niece": {"source": "Person", "target": "Person", "layer": "family", "symmetric": False, "meaning": "Explicit uncle/niece projection."},
    "spouse_union": {"source": "Person", "target": "Person", "layer": "family", "symmetric": True, "meaning": "One canonical symmetric MarriageUnion."},
    "member_of_clan": {"source": "Person", "target": "Clan", "layer": "clan", "symmetric": False, "meaning": "Source-backed ClanMembership."},
    "relation_kinship": {"source": "Person", "target": "Person", "layer": "family", "symmetric": False, "meaning": "Existing reader Relation; not a replacement for atomic kinship."},
    "relation_social": {"source": "Person", "target": "Person", "layer": "social_context", "symmetric": False, "meaning": "Existing reviewed social Relation."},
    "office_in_regime": {"source": "Office", "target": "Regime", "layer": "office", "symmetric": False, "meaning": "Normalized institutional context."},
    "office_at_location": {"source": "Office", "target": "Location", "layer": "office", "symmetric": False, "meaning": "Normalized office/location context."},
    "event_contextualizes_story": {"source": "Event", "target": "Story", "layer": "event", "symmetric": False, "meaning": "Historical event context attached to a Story."},
    "has_office_tenure": {"source": "Person", "target": "OfficeTenure", "layer": "office", "symmetric": False, "meaning": "Reified OfficeTenure incidence."},
    "tenure_for_office": {"source": "OfficeTenure", "target": "Office", "layer": "office", "symmetric": False, "meaning": "OfficeTenure institutional endpoint."},
    "tenure_under_regime": {"source": "OfficeTenure", "target": "Regime", "layer": "office", "symmetric": False, "meaning": "OfficeTenure regime context."},
    "tenure_at_location": {"source": "OfficeTenure", "target": "Location", "layer": "geographic", "symmetric": False, "meaning": "OfficeTenure location/jurisdiction endpoint."},
    "has_activity": {"source": "Person", "target": "PersonActivity", "layer": "temporal", "symmetric": False, "meaning": "Reified PersonActivity incidence."},
    "activity_in_story": {"source": "PersonActivity", "target": "Story", "layer": "story", "symmetric": False, "meaning": "PersonActivity Story context."},
    "activity_context_event": {"source": "PersonActivity", "target": "Event", "layer": "event", "symmetric": False, "meaning": "PersonActivity event context."},
    "activity_at_location": {"source": "PersonActivity", "target": "Location", "layer": "geographic", "symmetric": False, "meaning": "PersonActivity location context."},
    "has_event_participation": {"source": "Person", "target": "EventParticipation", "layer": "event", "symmetric": False, "meaning": "Reified EventParticipation incidence."},
    "participation_in_event": {"source": "EventParticipation", "target": "Event", "layer": "event", "symmetric": False, "meaning": "EventParticipation event endpoint."},
    "participation_in_story": {"source": "EventParticipation", "target": "Story", "layer": "event", "symmetric": False, "meaning": "EventParticipation Story context."},
    "source_person_in_service_context": {"source": "Person", "target": "ServicePoliticalFact", "layer": "service_political", "symmetric": False, "meaning": "Reified service/political context source endpoint."},
    "target_person_in_service_context": {"source": "ServicePoliticalFact", "target": "Person", "layer": "service_political", "symmetric": False, "meaning": "Reified service/political context target endpoint."},
    "service_context_in_story": {"source": "ServicePoliticalFact", "target": "Story", "layer": "service_political", "symmetric": False, "meaning": "Story that activates a service/political context."},
    "service_context_in_event": {"source": "ServicePoliticalFact", "target": "Event", "layer": "service_political", "symmetric": False, "meaning": "Event that scopes a service/political context."},
}

LAYER_DEFINITIONS = {
    "story": {"purpose": "Textual and participation structure; PersonStory is not equivalent to hard presence.", "relevant_node_types": ["Person", "Story"], "sufficiency_rule": "Strong textual orientation requires near-complete published Story coverage and traceable PersonStory links; hard participation is reported separately."},
    "family": {"purpose": "Typed kinship and marriage structure only.", "relevant_node_types": ["Person", "Clan"], "sufficiency_rule": "Usable requires broad production-Person endpoint coverage and reviewed/direct evidence; sparse source-backed edges remain pilot-only."},
    "clan": {"purpose": "Source-backed ClanMembership, never surname topology.", "relevant_node_types": ["Person", "Clan"], "sufficiency_rule": "Pilot-only when a small subset of Persons/Clans is covered."},
    "office": {"purpose": "Institutional Office and reified OfficeTenure history.", "relevant_node_types": ["Person", "Office", "OfficeTenure", "Regime", "Location"], "sufficiency_rule": "Usable requires meaningful Person and tenure coverage plus temporal/location detail; otherwise pilot-only."},
    "event": {"purpose": "Reusable Events, EventParticipation, and Story event context.", "relevant_node_types": ["Person", "Story", "Event", "EventParticipation", "PersonActivity"], "sufficiency_rule": "Usable requires event and participant coverage across the corpus; sparse event anchors are pilot-only."},
    "geographic": {"purpose": "Typed historical Location usage with explicit precision.", "relevant_node_types": ["Person", "Story", "Location", "OfficeTenure", "PersonActivity"], "sufficiency_rule": "Usable requires typed location facts for a substantial Person/Story share; missing coordinates do not fail validity but limit research."},
    "service_political": {"purpose": "Explicit service/political context, not inferred factions.", "relevant_node_types": ["Person", "Story", "Event", "ServicePoliticalFact"], "sufficiency_rule": "Pilot-only until multiple reviewed contexts cover a substantial network."},
    "social_context": {"purpose": "Existing reviewed social Relations that are not automatically temporal or familial.", "relevant_node_types": ["Person"], "sufficiency_rule": "Pilot-only for the current twelve-Relation review surface."},
    "temporal": {"purpose": "Interval and relative-time attributes across historical graph facts.", "relevant_node_types": ["Person", "Story", "Event", "OfficeTenure", "PersonActivity", "EventParticipation", "ServicePoliticalFact"], "sufficiency_rule": "Usable requires broad bounded edge coverage and explicit unknown/relative states; current corpus is expected to remain pilot-only."},
}


def load_inputs() -> dict[str, Any]:
    loaded = {name: read_json(path) for name, path in INPUTS.items()}
    loaded["h0c_fact_index"] = records(loaded["h0c_facts"], "fact_index")
    loaded["fact_by_key"] = {str(row["fact_key"]): row for row in loaded["h0c_fact_index"]}
    loaded["published_story_ids"] = {str(node["node_id"]) for node in loaded["h0c_graph"].get("nodes", []) if node.get("node_type") == "Story"}
    loaded["person_ids"] = {str(node["node_id"]) for node in loaded["h0c_graph"].get("nodes", []) if node.get("node_type") == "Person"}
    loaded["person_story_rows"] = records(loaded["person_story_links"], "links")
    return loaded


def fact_key(fact_type: str, fact_id: object) -> str:
    return f"{fact_type}:{fact_id}"


def fact_ref(fact: Mapping[str, Any]) -> dict[str, Any]:
    return {"fact_type": str(fact["fact_type"]), "fact_id": str(fact["fact_id"]), "fact_key": str(fact["fact_key"])}


def fact_for(inputs: Mapping[str, Any], fact_type: str, fact_id: object) -> dict[str, Any]:
    key = fact_key(fact_type, fact_id)
    try:
        return dict(inputs["fact_by_key"][key])
    except KeyError as exc:
        raise ValueError(f"HG0 missing H0C fact {key}") from exc


def evidence_for_facts(inputs: Mapping[str, Any], facts: Iterable[Mapping[str, Any]]) -> list[str]:
    return unique(evidence_id for fact in facts for evidence_id in fact.get("evidence_ids", []))


def provenance_for_facts(facts: Iterable[Mapping[str, Any]]) -> list[str]:
    return unique(ref for fact in facts for ref in fact.get("provenance_refs", []))


def build_ontology(h0c_graph: Mapping[str, Any]) -> dict[str, Any]:
    base_types = ["Person", "Story", "Location", "Event", "Office", "Clan", "Regime"]
    reified_types = ["OfficeTenure", "PersonActivity", "EventParticipation", "ServicePoliticalFact"]
    node_types = []
    for node_type in base_types:
        node_types.append({
            "node_type": node_type,
            "category": "historical_entity",
            "canonical_rule": "Reuse the canonical H0C entity ID; display labels are not identifiers.",
            "graph_role": "entity_node",
            "ml_role": "typed_entity",
        })
    node_types.extend([
        {"node_type": "OfficeTenure", "category": "reified_fact", "canonical_rule": "Node ID is a deterministic projection of the H0C OfficeTenure fact ID.", "graph_role": "reified_fact_node", "ml_role": "optional_fact_node"},
        {"node_type": "PersonActivity", "category": "reified_fact", "canonical_rule": "Node ID is a deterministic projection of the H0C PersonActivity fact ID.", "graph_role": "reified_fact_node", "ml_role": "optional_fact_node"},
        {"node_type": "EventParticipation", "category": "reified_fact", "canonical_rule": "Node ID is a deterministic projection of the H0C EventParticipation fact ID.", "graph_role": "reified_fact_node", "ml_role": "optional_fact_node"},
        {"node_type": "ServicePoliticalFact", "category": "reified_fact", "canonical_rule": "Node ID is a deterministic projection of the H0C service/political fact ID.", "graph_role": "reified_fact_node", "ml_role": "optional_fact_node"},
    ])
    all_edge_types = dict(EDGE_DEFINITIONS)
    for edge_type in h0c_graph.get("edge_type_catalog", []):
        all_edge_types.setdefault(edge_type, {
            "source": "unknown",
            "target": "unknown",
            "layer": "unclassified",
            "symmetric": False,
            "meaning": "Inherited H0C edge; inspect source ontology before use.",
        })
    edge_types = [{"edge_type": name, **all_edge_types[name]} for name in sorted(all_edge_types)]
    return {
        "schema": 1,
        "stage": "hg0-ontology",
        "node_types": node_types,
        "edge_types": edge_types,
        "layers": [{"layer": name, **LAYER_DEFINITIONS[name]} for name in sorted(LAYER_DEFINITIONS)],
        "multiplex_policy": {
            "graph_name": "G_all",
            "layer_views": [f"G_{name}" for name in sorted(LAYER_DEFINITIONS)],
            "same_endpoint_different_type": "Preserve as distinct typed edges; kinship, Story co-occurrence, office and service are not interchangeable.",
            "duplicate_policy": "One semantic edge per edge type/endpoints/support fact set; independent edge types remain parallel multiplex edges.",
        },
        "reification_audit": [
            {"fact_type": "office_tenure", "decision": "reified_node", "reason": "Person × Office × Time × Location × Regime can lose tenure identity when collapsed to Person→Office."},
            {"fact_type": "person_activity", "decision": "reified_node", "reason": "Person × Activity × Time × Location/Event/Story preserves the activity context and interval."},
            {"fact_type": "event_participation", "decision": "reified_node", "reason": "Person × Event × Story × role distinguishes hard participation from contextual reference."},
            {"fact_type": "service_political", "decision": "reified_node", "reason": "Person pair × Story/Event × temporal context must not become an unscoped Person→Person tie."},
            {"fact_type": "marriage", "decision": "direct_typed_edge_with_fact_reference", "reason": "Current MarriageUnion is a binary canonical union; its fact ID and temporal attributes remain on one symmetric edge."},
            {"fact_type": "kinship", "decision": "direct_typed_edge_with_fact_reference", "reason": "Directional/explicit atomic kinship is preserved as typed Person→Person edges."},
            {"fact_type": "clan_membership", "decision": "direct_typed_edge_with_fact_reference", "reason": "Person→Clan is binary and retains source precision; it never implies kinship or chronology."},
        ],
        "source_h0c_edge_catalog": sorted(str(value) for value in h0c_graph.get("edge_type_catalog", [])),
        "policy": "Facts remain canonical; HG0 nodes and edges are deterministic projections and never historical truth.",
    }


def build_universe(inputs: Mapping[str, Any]) -> dict[str, Any]:
    h0c_graph = inputs["h0c_graph"]
    base_nodes = [dict(node) for node in h0c_graph.get("nodes", [])]
    person_story_rows = inputs["person_story_rows"]
    published_story_ids = inputs["published_story_ids"]
    inside = [row for row in person_story_rows if str(row.get("entry_id")) in published_story_ids]
    outside = [row for row in person_story_rows if str(row.get("entry_id")) not in published_story_ids]
    outside_story_ids = sorted({str(row.get("entry_id")) for row in outside})
    node_counts = dict(sorted(Counter(str(node["node_type"]) for node in base_nodes).items()))
    return {
        "schema": 1,
        "stage": "hg0-graph-universe",
        "default_scope_id": "published_story_scope",
        "scopes": [
            {
                "scope_id": "published_story_scope",
                "status": "materialized",
                "person_ids": sorted(inputs["person_ids"]),
                "story_ids": sorted(published_story_ids),
                "historical_context_entity_policy": "Include H0C-normalized Location/Event/Office/Clan/Regime nodes referenced by protected facts even when no current published Story edge exists.",
                "node_counts_before_reification": node_counts,
                "person_story_links_in_scope": len(inside),
                "graph_story_node_count": len(published_story_ids),
            },
            {
                "scope_id": "global_person_story_index_boundary",
                "status": "boundary_only_not_materialized",
                "person_count": len(inputs["person_ids"]),
                "story_node_count": 0,
                "global_person_story_link_count": len(person_story_rows),
                "links_outside_published_story_scope": len(outside),
                "outside_story_id_count": len(outside_story_ids),
                "outside_story_ids_sample": outside_story_ids[:20],
                "policy": "Do not create dangling Story nodes. These links are an auditable research boundary until their canonical Story layer is in scope.",
            },
        ],
        "questions_answered": {
            "persons": "All 75 protected production Persons are included.",
            "stories": "The default HG0 graph includes the 143 published Story nodes in H0C.",
            "unpublished_stories": "Not materialized without canonical Story records; their global PersonStory links remain boundary metadata.",
            "context_entities_without_published_story": "Allowed when the H0C fact/entity layer references them; this is historical context, not a hidden Story expansion.",
            "research_scope": "Use published_story_scope by default; a wider research projection requires an explicit future scope manifest.",
        },
        "protected_counts": {
            "production_persons": len(inputs["person_ids"]),
            "published_stories": len(published_story_ids),
            "global_person_story_links": len(person_story_rows),
            "published_person_story_links": len(inside),
            "excluded_person_story_links": len(outside),
        },
        "policy": "Scope is explicit. Excluded global PersonStory links are not negative evidence and are not converted into dangling graph nodes.",
    }


def layer_memberships(edge_type: str, temporal_state: str, projection_role: str) -> tuple[str, list[str]]:
    definition = EDGE_DEFINITIONS.get(edge_type, {})
    primary = str(definition.get("layer", "unclassified"))
    layers = [primary]
    if temporal_state != "unknown":
        layers.append("temporal")
    if projection_role == "reified_support":
        layers.append("reification_support")
    return primary, sorted(set(layers))


def uncertainty_from_status(review_status: str, assertion_status: str, *, derived: bool = False) -> str:
    if review_status == "reviewed":
        return "reviewed"
    if review_status in {"uncertain", "conflicted"} or assertion_status in {"conflicted", "rejected"}:
        return "conflicted" if assertion_status == "conflicted" else "uncertain"
    if derived:
        return "derived"
    if review_status == "candidate":
        return "candidate"
    return "unknown"


def build_graph(inputs: Mapping[str, Any]) -> dict[str, Any]:
    h0c_graph = inputs["h0c_graph"]
    nodes: dict[tuple[str, str], dict[str, Any]] = {}
    edges: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    fact_by_key = inputs["fact_by_key"]

    def add_node(node: Mapping[str, Any], *, reified: bool = False, fact: Mapping[str, Any] | None = None, temporal: Mapping[str, Any] | None = None) -> str:
        node_type = str(node["node_type"])
        node_id = str(node["node_id"])
        key = (node_type, node_id)
        if key in nodes:
            return node_id
        output = dict(node)
        output["node_id"] = node_id
        output["node_type"] = node_type
        output["canonical_reference"] = str(output.get("canonical_reference", f"{node_type}:{node_id}"))
        output["scope_role"] = "historical_fact" if reified else ("production_entity" if node_type in {"Person", "Story"} else "historical_context_entity")
        output["reified_fact_node"] = bool(reified)
        if fact is not None:
            output["source_fact"] = fact_ref(fact)
            output["fact_ids"] = [str(fact["fact_id"])]
            output["evidence_ids"] = unique(fact.get("evidence_ids", []))
            output["review_status"] = str(fact.get("review_status", "candidate"))
            output["assertion_status"] = str(fact.get("assertion_status", "derived"))
            output["uncertainty_state"] = uncertainty_from_status(output["review_status"], output["assertion_status"])
            output["temporal"] = dict(temporal or normalized_temporal(fact, basis=str(fact["fact_type"])))
        nodes[key] = output
        return node_id

    def add_fact_node(node_type: str, fact: Mapping[str, Any], label: str, temporal: Mapping[str, Any]) -> str:
        fact_id = str(fact["fact_id"])
        projected_id = stable_id("node-hg0", node_type, fact_id)
        add_node({
            "node_id": projected_id,
            "node_type": node_type,
            "label": label,
            "canonical_reference": f"{node_type}:{fact_id}",
        }, reified=True, fact=fact, temporal=temporal)
        return projected_id

    def add_edge(
        edge_type: str,
        source_type: str,
        source_id: object,
        target_type: str,
        target_id: object,
        source_facts: Iterable[Mapping[str, Any]],
        evidence_ids: Iterable[object],
        temporal: Mapping[str, Any],
        *,
        review_status: str = "candidate",
        assertion_status: str = "derived",
        provenance_refs: Iterable[object] = (),
        relation_ids: Iterable[object] = (),
        projection_role: str = "semantic_direct",
        source_h0c_edge_id: str | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        source_facts_sorted = sorted({str(f["fact_key"]): fact_ref(f) for f in source_facts}.values(), key=lambda item: item["fact_key"])
        fact_ids = [str(item["fact_id"]) for item in source_facts_sorted]
        source_key = node_key(source_type, source_id)
        target_key = node_key(target_type, target_id)
        semantic_key = (edge_type, source_key, target_key, "|".join(item["fact_key"] for item in source_facts_sorted))
        edge_id = stable_id("edge-hg0", *semantic_key)
        state = str(temporal.get("temporal_state", "unknown"))
        primary_layer, memberships = layer_memberships(edge_type, state, projection_role)
        output = {
            "edge_id": edge_id,
            "edge_type": edge_type,
            "source": {"node_type": source_type, "node_id": str(source_id)},
            "target": {"node_type": target_type, "node_id": str(target_id)},
            "source_facts": source_facts_sorted,
            "fact_ids": sorted(set(fact_ids)),
            "relation_ids": unique(relation_ids),
            "evidence_ids": unique(evidence_ids),
            "provenance_refs": unique(provenance_refs),
            "temporal": dict(temporal),
            "graph_layer": primary_layer,
            "layer_memberships": memberships,
            "projection_role": projection_role,
            "review_status": review_status,
            "assertion_status": assertion_status,
            "uncertainty_state": uncertainty_from_status(review_status, assertion_status, derived=projection_role != "semantic_direct"),
            "edge_status": "materialized",
            "semantic_key": f"{edge_type}|{source_key}|{target_key}|{'|'.join(fact_ids)}",
        }
        if source_h0c_edge_id:
            output["source_h0c_edge_id"] = source_h0c_edge_id
        if attributes:
            output["attributes"] = dict(attributes)
        if edge_id in {item["edge_id"] for item in edges.values()}:
            raise ValueError(f"duplicate HG0 edge ID {edge_id}")
        edges[semantic_key] = output

    for source_node in h0c_graph.get("nodes", []):
        add_node(source_node)

    for source_edge in h0c_graph.get("edges", []):
        edge_type = str(source_edge["edge_type"])
        if edge_type not in H0C_DIRECT_KEEP:
            continue
        temporal = normalized_temporal(source_edge.get("temporal", {}), basis="h0c_edge")
        facts = [fact_by_key[str(ref["fact_key"])] for ref in source_edge.get("source_facts", []) if str(ref.get("fact_key")) in fact_by_key]
        if not facts:
            raise ValueError(f"H0C edge {source_edge.get('edge_id')} has no indexed source fact")
        add_edge(
            edge_type,
            str(source_edge["source"]["node_type"]),
            str(source_edge["source"]["node_id"]),
            str(source_edge["target"]["node_type"]),
            str(source_edge["target"]["node_id"]),
            facts,
            source_edge.get("evidence_ids", []),
            temporal,
            review_status=str(source_edge.get("review_status", "candidate")),
            assertion_status=str(source_edge.get("assertion_status", "derived")),
            provenance_refs=source_edge.get("provenance_refs", []),
            relation_ids=source_edge.get("relation_ids", []),
            source_h0c_edge_id=str(source_edge.get("edge_id")),
            attributes={"h0c_derivation_basis": source_edge.get("derivation_basis")},
        )

    office_by_tenure = {str(row["tenure_id"]): row for row in records(inputs["h0c_offices"], "tenures")}
    for row in sorted(office_by_tenure.values(), key=lambda item: str(item["tenure_id"])):
        fact = fact_for(inputs, "office_tenure", row["tenure_id"])
        temporal = normalized_temporal(row, basis="office_tenure")
        tenure_node = add_fact_node("OfficeTenure", fact, str(row.get("office_title", row["tenure_id"])), temporal)
        person_id = str(row["person_id"])
        office_id = row.get("office_id")
        if office_id:
            add_edge("has_office_tenure", "Person", person_id, "OfficeTenure", tenure_node, [fact], fact.get("evidence_ids", []), temporal, projection_role="reified_support")
            add_edge("tenure_for_office", "OfficeTenure", tenure_node, "Office", str(office_id), [fact], fact.get("evidence_ids", []), temporal, projection_role="reified_support")
        if row.get("regime_id"):
            add_edge("tenure_under_regime", "OfficeTenure", tenure_node, "Regime", str(row["regime_id"]), [fact], fact.get("evidence_ids", []), temporal, projection_role="reified_support")
        for location_id in unique([row.get("location_id"), row.get("jurisdiction_location_id")]):
            add_edge("tenure_at_location", "OfficeTenure", tenure_node, "Location", location_id, [fact], fact.get("evidence_ids", []), temporal, projection_role="reified_support", attributes={"location_role": "location_or_jurisdiction"})

    for row in sorted(records(inputs["h0c_activities"]), key=lambda item: str(item["activity_id"])):
        fact = fact_for(inputs, "person_activity", row["activity_id"])
        temporal = normalized_temporal(row, basis="person_activity")
        activity_node = add_fact_node("PersonActivity", fact, str(row.get("activity_type", row["activity_id"])), temporal)
        evidence_ids = fact.get("evidence_ids", [])
        add_edge("has_activity", "Person", str(row["person_id"]), "PersonActivity", activity_node, [fact], evidence_ids, temporal, projection_role="reified_support")
        if row.get("story_id") in inputs["published_story_ids"]:
            add_edge("activity_in_story", "PersonActivity", activity_node, "Story", str(row["story_id"]), [fact], evidence_ids, temporal, projection_role="reified_support")
        if row.get("event_id"):
            add_edge("activity_context_event", "PersonActivity", activity_node, "Event", str(row["event_id"]), [fact], evidence_ids, temporal, projection_role="reified_support")
        for location_id in unique(row.get("location_ids", [])):
            add_edge("activity_at_location", "PersonActivity", activity_node, "Location", location_id, [fact], evidence_ids, temporal, projection_role="reified_support")

    for row in sorted(records(inputs["h0c_event_participations"]), key=lambda item: str(item["event_participation_id"])):
        fact = fact_for(inputs, "event_participation", row["event_participation_id"])
        temporal = normalized_temporal(row, basis="event_participation")
        participation_node = add_fact_node("EventParticipation", fact, str(row.get("participation_type", row["event_participation_id"])), temporal)
        evidence_ids = fact.get("evidence_ids", [])
        attributes = {
            "participation_type": row.get("participation_type"),
            "story_role": row.get("story_role"),
            "hard_temporal_eligible": bool(row.get("hard_temporal_eligible")),
        }
        add_edge("has_event_participation", "Person", str(row["person_id"]), "EventParticipation", participation_node, [fact], evidence_ids, temporal, projection_role="reified_support", attributes=attributes)
        add_edge("participation_in_event", "EventParticipation", participation_node, "Event", str(row["event_id"]), [fact], evidence_ids, temporal, projection_role="reified_support", attributes=attributes)
        if row.get("story_id") in inputs["published_story_ids"]:
            add_edge("participation_in_story", "EventParticipation", participation_node, "Story", str(row["story_id"]), [fact], evidence_ids, temporal, projection_role="reified_support", attributes=attributes)

    for row in sorted(records(inputs["h0c_service"]), key=lambda item: str(item["service_context_fact_id"])):
        fact = fact_for(inputs, "service_political", row["service_context_fact_id"])
        temporal = normalized_temporal(row, basis="relation_temporal_context")
        service_node = add_fact_node("ServicePoliticalFact", fact, str(row.get("context_type", row["service_context_fact_id"])), temporal)
        evidence_ids = fact.get("evidence_ids", [])
        attrs = {"context_type": row.get("context_type"), "relation_type": row.get("relation_type"), "relation_id": row.get("relation_id"), "applicability_conditions": row.get("applicability_conditions", [])}
        add_edge("source_person_in_service_context", "Person", str(row["person_a_id"]), "ServicePoliticalFact", service_node, [fact], evidence_ids, temporal, relation_ids=[row.get("relation_id")], projection_role="reified_support", attributes=attrs)
        add_edge("target_person_in_service_context", "ServicePoliticalFact", service_node, "Person", str(row["person_b_id"]), [fact], evidence_ids, temporal, relation_ids=[row.get("relation_id")], projection_role="reified_support", attributes=attrs)
        for story_id in sorted(set(str(value) for value in row.get("story_ids", []) if str(value) in inputs["published_story_ids"])):
            add_edge("service_context_in_story", "ServicePoliticalFact", service_node, "Story", story_id, [fact], evidence_ids, temporal, relation_ids=[row.get("relation_id")], projection_role="reified_support", attributes=attrs)
        for event_id in unique(row.get("event_ids", [])):
            add_edge("service_context_in_event", "ServicePoliticalFact", service_node, "Event", event_id, [fact], evidence_ids, temporal, relation_ids=[row.get("relation_id")], projection_role="reified_support", attributes=attrs)

    nodes_out = sorted(nodes.values(), key=lambda item: (item["node_type"], item["node_id"]))
    edges_out = sorted(edges.values(), key=lambda item: (item["edge_type"], item["source"]["node_type"], item["source"]["node_id"], item["target"]["node_type"], item["target"]["node_id"], item["edge_id"]))
    return {
        "schema": 1,
        "stage": "hg0-graph-projection",
        "graph_id": "hg0-published-story-scope",
        "scope_id": "published_story_scope",
        "node_type_catalog": sorted({str(node["node_type"]) for node in nodes_out}),
        "edge_type_catalog": sorted({str(edge["edge_type"]) for edge in edges_out}),
        "nodes": nodes_out,
        "edges": edges_out,
        "node_counts": dict(sorted(Counter(str(node["node_type"]) for node in nodes_out).items())),
        "edge_counts": dict(sorted(Counter(str(edge["edge_type"]) for edge in edges_out).items())),
        "projection_roles": dict(sorted(Counter(str(edge["projection_role"]) for edge in edges_out).items())),
        "layer_counts": dict(sorted(Counter(layer for edge in edges_out for layer in edge.get("layer_memberships", [])).items())),
        "reification": {
            "materialized_fact_node_types": ["OfficeTenure", "PersonActivity", "EventParticipation", "ServicePoliticalFact"],
            "h0c_direct_edge_types_replaced_by_reified_paths": sorted(set(str(edge["edge_type"]) for edge in h0c_graph.get("edges", [])) - H0C_DIRECT_KEEP),
            "policy": "Reified paths preserve higher-order fact identity; direct shortcuts are not silently treated as canonical facts.",
        },
        "policy": "HG0 graph nodes and edges are derived from H0C facts. Missing edges are unknown, not negative evidence; topology never resolves alias collisions.",
    }


def component_summary(nodes: list[Mapping[str, Any]], edges: list[Mapping[str, Any]], predicate: Any = None) -> dict[str, Any]:
    node_keys = {node_key(node["node_type"], node["node_id"]): node for node in nodes}
    adjacency: dict[str, set[str]] = {key: set() for key in node_keys}
    for edge in edges:
        if predicate is not None and not predicate(edge):
            continue
        source = node_key(edge["source"]["node_type"], edge["source"]["node_id"])
        target = node_key(edge["target"]["node_type"], edge["target"]["node_id"])
        if source in adjacency and target in adjacency:
            adjacency[source].add(target)
            adjacency[target].add(source)
    seen: set[str] = set()
    components: list[list[str]] = []
    for start in sorted(adjacency):
        if start in seen:
            continue
        queue = [start]
        seen.add(start)
        component: list[str] = []
        while queue:
            current = queue.pop()
            component.append(current)
            for neighbor in sorted(adjacency[current]):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        components.append(sorted(component))
    components.sort(key=lambda value: (-len(value), value[0] if value else ""))
    degree_values = [len(adjacency[key]) for key in sorted(adjacency)]
    isolated = sorted(key for key, neighbors in adjacency.items() if not neighbors)
    return {
        "node_count": len(adjacency),
        "edge_count": sum(1 for edge in edges if predicate is None or predicate(edge)),
        "connected_component_count": len(components),
        "largest_component_size": len(components[0]) if components else 0,
        "isolated_node_count": len(isolated),
        "isolated_nodes": isolated,
        "degree": {
            "min": min(degree_values) if degree_values else 0,
            "max": max(degree_values) if degree_values else 0,
            "mean": round(fmean(degree_values), 6) if degree_values else 0,
            "median": median(degree_values) if degree_values else 0,
        },
        "component_size_distribution": [len(component) for component in components[:20]],
    }


def temporal_distribution(edges: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(edge.get("temporal", {}).get("temporal_state", "unknown")) for edge in edges).items()))


def review_distribution(edges: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(edge.get("review_status", "unknown")) for edge in edges).items()))


def classify_layer(layer: str, metric: Mapping[str, Any]) -> tuple[str, str]:
    coverage = float(metric.get("canonical_node_coverage_ratio", 0.0))
    semantic_edges = int(metric.get("semantic_edge_count", 0))
    bounded = int(metric.get("bounded_edge_count", 0))
    review = metric.get("review_distribution", {})
    reviewed = int(review.get("reviewed", 0))
    reviewed_ratio = reviewed / semantic_edges if semantic_edges else 0.0
    if layer == "story" and coverage >= 0.90 and semantic_edges >= 300:
        return "usable", "Published Story/Person coverage is near-complete and the layer has hundreds of traceable links, but hard participation remains narrower than PersonStory."
    if layer == "combined" and coverage >= 0.90 and semantic_edges >= 500:
        return "usable", "The combined graph is connected enough for deterministic heterogeneous pilot projections, while layer sparsity and source selection bias remain material."
    if semantic_edges == 0:
        return "insufficient", "No materialized semantic edges exist for this layer in the protected H0C scope."
    if layer == "temporal" and bounded < 25:
        return "pilot_only", "Some bounded intervals exist, but the temporal edge population is too sparse for general temporal claims."
    if coverage < 0.05 or semantic_edges < 5:
        return "insufficient", "The layer has too little endpoint coverage or too few semantic edges for a meaningful corpus-level experiment."
    if reviewed_ratio < 0.25 and semantic_edges < 50:
        return "pilot_only", "The layer is source-backed but small and primarily candidate/derived; it is suitable for focused pilots only."
    return "pilot_only", "The layer is usable for targeted, evidence-filtered pilots but lacks broad coverage for corpus-level historical inference."


def build_sufficiency(inputs: Mapping[str, Any], graph: Mapping[str, Any], universe: Mapping[str, Any], temporal: Mapping[str, Any]) -> dict[str, Any]:
    nodes = graph["nodes"]
    edges = graph["edges"]
    canonical_nodes = [node for node in nodes if not node.get("reified_fact_node")]
    layer_metrics: dict[str, dict[str, Any]] = {}
    relevant_types = {layer: set(info["relevant_node_types"]) for layer, info in LAYER_DEFINITIONS.items()}
    for layer in sorted(LAYER_DEFINITIONS):
        layer_edges = [edge for edge in edges if layer in edge.get("layer_memberships", [])]
        direct_edges = [edge for edge in layer_edges if edge.get("projection_role") != "reified_support"]
        relevant_nodes = [node for node in canonical_nodes if node["node_type"] in relevant_types[layer]]
        incident = set()
        for edge in layer_edges:
            incident.add(node_key(edge["source"]["node_type"], edge["source"]["node_id"]))
            incident.add(node_key(edge["target"]["node_type"], edge["target"]["node_id"]))
        relevant_keys = {node_key(node["node_type"], node["node_id"]) for node in relevant_nodes}
        coverage = len(incident & relevant_keys) / len(relevant_keys) if relevant_keys else 0.0
        bounded = sum(edge.get("temporal", {}).get("temporal_state") == "bounded" for edge in layer_edges)
        component_node_keys = relevant_keys | incident
        component_nodes = [node for node in nodes if node_key(node["node_type"], node["node_id"]) in component_node_keys]
        metric = {
            "layer": layer,
            "canonical_node_count": len(relevant_nodes),
            "canonical_nodes_with_layer_edges": len(incident & relevant_keys),
            "canonical_node_coverage_ratio": round(coverage, 6),
            "semantic_edge_count": len(layer_edges),
            "direct_semantic_edge_count": len(direct_edges),
            "reified_support_edge_count": sum(edge.get("projection_role") == "reified_support" for edge in layer_edges),
            "edge_type_counts": dict(sorted(Counter(edge["edge_type"] for edge in layer_edges).items())),
            "temporal_distribution": temporal_distribution(layer_edges),
            "bounded_edge_count": bounded,
            "review_distribution": review_distribution(layer_edges),
            "component_summary": component_summary(component_nodes, layer_edges),
        }
        classification, reason = classify_layer(layer, metric)
        metric["classification"] = classification
        metric["classification_reason"] = reason
        layer_metrics[layer] = metric

    combined_semantic = [edge for edge in edges if edge.get("projection_role") != "reified_support"]
    all_summary = component_summary(nodes, edges)
    canonical_incident = set()
    for edge in edges:
        canonical_incident.add(node_key(edge["source"]["node_type"], edge["source"]["node_id"]))
        canonical_incident.add(node_key(edge["target"]["node_type"], edge["target"]["node_id"]))
    canonical_keys = {node_key(node["node_type"], node["node_id"]) for node in canonical_nodes}
    combined_metric = {
        "layer": "combined",
        "canonical_node_count": len(canonical_nodes),
        "canonical_nodes_with_layer_edges": len(canonical_incident & canonical_keys),
        "canonical_node_coverage_ratio": round(len(canonical_incident & canonical_keys) / len(canonical_keys), 6) if canonical_keys else 0.0,
        "semantic_edge_count": len(combined_semantic),
        "support_edge_count": len(edges) - len(combined_semantic),
        "edge_type_counts": dict(sorted(Counter(edge["edge_type"] for edge in combined_semantic).items())),
        "temporal_distribution": temporal_distribution(combined_semantic),
        "bounded_edge_count": sum(edge.get("temporal", {}).get("temporal_state") == "bounded" for edge in combined_semantic),
        "review_distribution": review_distribution(combined_semantic),
        "component_summary": all_summary,
    }
    classification, reason = classify_layer("combined", combined_metric)
    combined_metric["classification"] = classification
    combined_metric["classification_reason"] = reason
    layer_metrics["combined"] = combined_metric

    location_records = records(inputs["h0c_locations"])
    location_facts = records(inputs["h0c_location_facts"])
    location_edges = [edge for edge in edges if "geographic" in edge.get("layer_memberships", [])]
    location_subjects = {str(row.get("subject_id")) for row in location_facts if row.get("subject_type") == "person"}
    story_location_count = sum(row.get("subject_type") == "story" for row in location_facts)
    event_location_count = sum(bool(row.get("location_ids")) for row in records(inputs["h0c_events"]))
    spatial = {
        "location_entity_count": len(location_records),
        "persons_with_typed_location_fact": len(location_subjects),
        "story_location_fact_count": story_location_count,
        "events_with_location": event_location_count,
        "geographic_edge_count": len(location_edges),
        "coordinate_precision_distribution": dict(sorted(Counter(str(row.get("coordinate_precision", "unknown")) for row in location_records).items())),
        "modern_mapping_status_distribution": dict(sorted(Counter(str(row.get("modern_mapping", {}).get("status", "unknown")) for row in location_records).items())),
        "policy": "Missing coordinates and modern mappings remain unknown; ancient Location identity is not replaced by modern geography.",
    }
    return {
        "schema": 1,
        "stage": "hg0-sufficiency-audit",
        "scope_id": universe["default_scope_id"],
        "graph_summary": all_summary,
        "layers": layer_metrics,
        "spatial": spatial,
        "temporal": temporal["coverage"],
        "readiness_scale": {
            "strong": "Broad coverage with traceable, sufficiently reviewed evidence for corpus-level structural use.",
            "usable": "Deterministic projection supports constrained research/pilot use, but known bias or sparsity remains.",
            "pilot_only": "Evidence-backed but sparse, candidate-heavy, or semantically narrow; do not generalize across the corpus.",
            "insufficient": "Current graph does not support a meaningful experiment for this layer.",
        },
        "policy": "Sufficiency is a structural/data-coverage audit, not a measure of historical importance or truth.",
    }


def build_temporal(inputs: Mapping[str, Any], graph: Mapping[str, Any], universe: Mapping[str, Any]) -> dict[str, Any]:
    index = []
    for edge in graph["edges"]:
        temporal = dict(edge.get("temporal", {}))
        index.append({
            "edge_id": edge["edge_id"],
            "edge_type": edge["edge_type"],
            "source": edge["source"],
            "target": edge["target"],
            "start_year_ce": temporal.get("start_year_ce"),
            "end_year_ce": temporal.get("end_year_ce"),
            "precision": temporal.get("precision", "unknown"),
            "basis": temporal.get("basis", "unknown"),
            "temporal_state": temporal.get("temporal_state", "unknown"),
            "source_fact_ids": edge.get("fact_ids", []),
        })
    index.sort(key=lambda row: (row["start_year_ce"] is None, row["start_year_ce"] if row["start_year_ce"] is not None else 10**9, row["end_year_ce"] is None, row["end_year_ce"] if row["end_year_ce"] is not None else 10**9, row["edge_id"]))
    ranges = [(307, 317), (322, 329), (399, 402)]
    examples = []
    by_id = {edge["edge_id"]: edge for edge in graph["edges"]}
    for start, end in ranges:
        active = [row["edge_id"] for row in index if interval_overlaps(row, start, end)]
        unknown = [row["edge_id"] for row in index if row["temporal_state"] in {"unknown", "relative_only"}]
        examples.append({"start_year_ce": start, "end_year_ce": end, "potentially_active_edge_count": len(active), "potentially_active_edge_ids": active[:100], "strict_unknown_edge_count": len(unknown)})
    return {
        "schema": 1,
        "stage": "hg0-temporal-projection",
        "scope_id": universe["default_scope_id"],
        "edge_temporal_index": index,
        "coverage": {
            "edge_count": len(index),
            "state_distribution": dict(sorted(Counter(row["temporal_state"] for row in index).items())),
            "precision_distribution": dict(sorted(Counter(row["precision"] for row in index).items())),
            "bounded_edge_count": sum(row["temporal_state"] == "bounded" for row in index),
            "one_sided_edge_count": sum(row["temporal_state"] == "one_sided" for row in index),
            "relative_only_edge_count": sum(row["temporal_state"] == "relative_only" for row in index),
            "unknown_edge_count": sum(row["temporal_state"] == "unknown" for row in index),
        },
        "slice_query_contract": {
            "query": "edges_for_interval(start_year_ce, end_year_ce, include_unknown=False)",
            "interval_semantics": "Inclusive potential-overlap: a bounded edge is returned when its interval intersects the requested interval.",
            "one_sided_semantics": "A lower/upper bound is returned as potentially active when it does not exclude the requested interval.",
            "unknown_semantics": "Unknown and relative-only facts are excluded from strict slices and reported separately; include_unknown may expose them as uncertain context.",
            "temporal_leakage_rule": "A pre-cutoff projection may include only facts whose known end is at or before the cutoff, plus an explicit uncertain bucket; future or unknown facts must not be used as observed features.",
            "no_exactness_upgrade": "Overlap never upgrades approximate, event-bounded, phase-only, relative, or unknown evidence to an exact date.",
        },
        "example_queries": examples,
        "policy": "G(t) is a derived potential-activity view. Canonical temporal assertions remain in H0A/H0B/H0C facts.",
    }


def build_graph_audit(inputs: Mapping[str, Any], graph: Mapping[str, Any], ontology: Mapping[str, Any]) -> dict[str, Any]:
    node_keys = {node_key(node["node_type"], node["node_id"]) for node in graph["nodes"]}
    node_types = set(graph["node_type_catalog"])
    edge_types = set(graph["edge_type_catalog"])
    fact_keys = set(inputs["fact_by_key"])
    issues: dict[str, list[Any]] = defaultdict(list)
    seen_edge_ids: set[str] = set()
    seen_semantic: set[str] = set()
    spouse_pairs: set[tuple[str, str]] = set()
    for edge in graph["edges"]:
        edge_id = str(edge["edge_id"])
        source = node_key(edge["source"]["node_type"], edge["source"]["node_id"])
        target = node_key(edge["target"]["node_type"], edge["target"]["node_id"])
        if source not in node_keys or target not in node_keys:
            issues["dangling_edges"].append(edge_id)
        if edge_id in seen_edge_ids:
            issues["duplicate_edge_ids"].append(edge_id)
        seen_edge_ids.add(edge_id)
        if edge["edge_type"] not in edge_types:
            issues["invalid_edge_types"].append(edge_id)
        if edge["source"]["node_type"] not in node_types or edge["target"]["node_type"] not in node_types:
            issues["invalid_node_types"].append(edge_id)
        semantic_key = str(edge.get("semantic_key"))
        if semantic_key in seen_semantic:
            issues["duplicate_semantic_edges"].append(edge_id)
        seen_semantic.add(semantic_key)
        if edge["edge_type"] == "spouse_union":
            pair = tuple(sorted([source, target]))
            if pair in spouse_pairs:
                issues["symmetric_reverse_duplicates"].append(edge_id)
            spouse_pairs.add(pair)
        if not edge.get("source_facts") or (not edge.get("evidence_ids") and not edge.get("provenance_refs")):
            issues["unsupported_edges"].append(edge_id)
        for ref in edge.get("source_facts", []):
            if str(ref.get("fact_key")) not in fact_keys:
                issues["dangling_fact_references"].append({"edge_id": edge_id, "fact_key": ref.get("fact_key")})
        temporal = edge.get("temporal", {})
        start = integer_or_none(temporal.get("start_year_ce"))
        end = integer_or_none(temporal.get("end_year_ce"))
        if start is not None and end is not None and start > end:
            issues["invalid_temporal_intervals"].append(edge_id)
        expected = EDGE_DEFINITIONS.get(edge["edge_type"])
        if expected and expected["source"] != "unknown":
            if expected["source"] != edge["source"]["node_type"] or expected["target"] != edge["target"]["node_type"]:
                issues["ontology_endpoint_conflicts"].append(edge_id)

    for node in graph["nodes"]:
        if node.get("reified_fact_node"):
            ref = node.get("source_fact", {})
            if str(ref.get("fact_key")) not in fact_keys:
                issues["dangling_fact_references"].append({"node_id": node["node_id"], "fact_key": ref.get("fact_key")})
            if not node.get("evidence_ids"):
                issues["unsupported_nodes"].append(node_key(node["node_type"], node["node_id"]))

    parent_graph: dict[str, list[str]] = defaultdict(list)
    for edge in graph["edges"]:
        if edge["edge_type"] == "parent_of":
            parent_graph[str(edge["source"]["node_id"])].append(str(edge["target"]["node_id"]))
    cycles: list[list[str]] = []
    def visit(start: str, current: str, path: list[str]) -> None:
        for child in sorted(parent_graph.get(current, [])):
            if child == start:
                cycles.append(path + [child])
            elif child not in path and len(path) < len(parent_graph) + 1:
                visit(start, child, path + [child])
    for start in sorted(parent_graph):
        visit(start, start, [start])
    issues["family_cycle_anomalies"].extend(cycles)
    issue_catalog = [
        "dangling_edges",
        "dangling_fact_references",
        "unsupported_edges",
        "unsupported_nodes",
        "duplicate_edge_ids",
        "duplicate_semantic_edges",
        "symmetric_reverse_duplicates",
        "invalid_edge_types",
        "invalid_node_types",
        "invalid_temporal_intervals",
        "ontology_endpoint_conflicts",
        "family_cycle_anomalies",
    ]
    for issue_name in issue_catalog:
        issues.setdefault(issue_name, [])
    issue_counts = {name: len(values) for name, values in sorted(issues.items())}
    return {
        "schema": 1,
        "stage": "hg0-graph-audit",
        "issues": {name: sorted(values, key=lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True)) for name, values in sorted(issues.items())},
        "issue_counts": issue_counts,
        "inherited_h0c_issues": inputs["h0c_audit"].get("issues", {}),
        "multi_edge_policy_check": {
            "independent_edge_types_allowed": True,
            "duplicate_same_semantic_edge_rejected": not issues.get("duplicate_semantic_edges"),
            "symmetric_spouse_edge_policy": "One canonical endpoint order; reverse duplicate is invalid.",
        },
        "policy": "Graph integrity failures are validation errors; isolated nodes, unknown chronology, and unresolved aliases are auditable historical states rather than repairs.",
    }


def build_bias(inputs: Mapping[str, Any], graph: Mapping[str, Any], universe: Mapping[str, Any]) -> dict[str, Any]:
    h0c_edges = inputs["h0c_graph"].get("edges", [])
    story_related_types = {
        "person_story_link",
        "story_participant_present",
        "story_participant_actor",
        "story_participant_referenced",
        "story_participant_off_frame",
        "story_participant_annotation_only",
        "event_contextualizes_story",
        "event_context_reference",
        "story_present_at",
    }
    story_edges = [edge for edge in h0c_edges if edge.get("edge_type") in story_related_types]
    external_edges = [edge for edge in h0c_edges if edge.get("edge_type") not in story_related_types]
    published_person_story = [edge for edge in h0c_edges if edge.get("edge_type") == "person_story_link"]
    degree = Counter(str(edge["source"]["node_id"]) for edge in published_person_story)
    top10 = sorted(degree.values(), reverse=True)[:10]
    source_layer_counts: Counter[str] = Counter()
    for row in inputs["person_story_rows"]:
        for presence in row.get("presences", []):
            source_layer_counts[str(presence.get("source_layer", "unknown"))] += 1
    participant_section_counts: Counter[str] = Counter()
    for row in records(inputs["h0c_participants"]):
        for section in row.get("source_sections", []):
            participant_section_counts[str(section)] += 1
    candidate_by_layer: dict[str, dict[str, int]] = {}
    for layer in sorted(LAYER_DEFINITIONS):
        layer_edges = [edge for edge in graph["edges"] if layer in edge.get("layer_memberships", [])]
        candidate_by_layer[layer] = dict(sorted(Counter(str(edge.get("review_status", "unknown")) for edge in layer_edges).items()))
    outside = int(universe["protected_counts"]["excluded_person_story_links"])
    total_global = int(universe["protected_counts"]["global_person_story_links"])
    story_ratio = len(story_edges) / len(h0c_edges) if h0c_edges else 0.0
    return {
        "schema": 1,
        "stage": "hg0-bias-audit",
        "scope_id": universe["default_scope_id"],
        "story_layer_dominance": {
            "h0c_edge_count": len(h0c_edges),
            "story_related_edge_count": len(story_edges),
            "external_historical_edge_count": len(external_edges),
            "story_related_edge_ratio": round(story_ratio, 6),
            "classification": "story_textual_structure_dominant" if story_ratio >= 0.70 else "mixed_layer_representation",
            "definition": "Story-related includes PersonStory, participant roles, Story event context, and Story location context; it does not create Person-Person co-occurrence edges.",
            "interpretation": "A future model trained on G_all can learn editorial/textual structure more easily than external social history; layer-restricted views are required.",
        },
        "published_scope_selection": {
            "global_person_story_links": total_global,
            "materialized_published_person_story_links": int(universe["protected_counts"]["published_person_story_links"]),
            "excluded_links": outside,
            "excluded_link_ratio": round(outside / total_global, 6) if total_global else 0.0,
            "excluded_story_id_count": next(scope["outside_story_id_count"] for scope in universe["scopes"] if scope["scope_id"] == "global_person_story_index_boundary"),
            "bias": "Published scope is an editorial selection and must not be treated as the complete historical Story universe.",
        },
        "person_story_degree_concentration": {
            "person_count_with_published_person_story": len(degree),
            "top_10_published_person_story_degree_sum": sum(top10),
            "published_person_story_edge_count": len(published_person_story),
            "top_10_share": round(sum(top10) / len(published_person_story), 6) if published_person_story else 0.0,
            "policy": "Degree is representation/coverage metadata, not historical importance.",
        },
        "source_layer_representation": {
            "person_story_presence_source_layers": dict(sorted(source_layer_counts.items())),
            "participant_source_sections": dict(sorted(participant_section_counts.items())),
            "annotation_only_participant_count": sum(row.get("role") == "annotation_only" for row in records(inputs["h0c_participants"])),
            "caveat": "Liu annotation can expand contextual connectivity without proving hard Story presence.",
        },
        "review_status_by_layer": candidate_by_layer,
        "known_biases": [
            "The published 143-Story scope is an editorial sample of the wider canonical PersonStory index.",
            "The Story/textual layer dominates edge volume; external family, office, event, location, and service layers are sparse.",
            "Liu annotation contributes contextual Person links and must not be read as scene participation.",
            "Surviving local source evidence and production Person selection shape graph visibility; missing edges are unknown, not negative evidence.",
            "Candidate/derived graph edges are not equivalent to reviewed historical certainty.",
        ],
        "policy": "Bias audit describes graph construction and coverage, not sociological conclusions about Wei-Jin society.",
    }


def classify_orphan(inputs: Mapping[str, Any], node_key_value: str) -> str:
    node_type, _, node_id = node_key_value.partition(":")
    if node_type == "Person":
        external = any(str(row.get("person_id")) == node_id and str(row.get("entry_id")) not in inputs["published_story_ids"] for row in inputs["person_story_rows"])
        return "published_scope_artifact" if external else "missing_data_or_sparse_evidence"
    if node_type == "Story":
        return "published_scope_entity_without_current_edge"
    return "entity_type_structural_isolation"


def build_gaps(inputs: Mapping[str, Any], universe: Mapping[str, Any], graph: Mapping[str, Any], audit: Mapping[str, Any], sufficiency: Mapping[str, Any], bias: Mapping[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    def add(category: str, status: str, why: str, *, node_ids: Iterable[str] = (), edge_ids: Iterable[str] = (), story_ids: Iterable[str] = (), person_ids: Iterable[str] = (), evidence_ids: Iterable[str] = (), future_relevance: str = "HG0 sufficiency") -> None:
        key = [category, why, future_relevance, sorted(node_ids), sorted(edge_ids), sorted(story_ids), sorted(person_ids), sorted(evidence_ids)]
        rows.append({
            "gap_id": stable_id("hg0-gap", json.dumps(key, ensure_ascii=False, sort_keys=True)),
            "category": category,
            "status": status,
            "node_ids": sorted(set(node_ids)),
            "edge_ids": sorted(set(edge_ids)),
            "affected_story_ids": sorted(set(story_ids)),
            "affected_person_ids": sorted(set(person_ids)),
            "evidence_ids": sorted(set(evidence_ids)),
            "why_it_matters": why,
            "future_relevance": future_relevance,
        })

    if universe["protected_counts"]["excluded_person_story_links"]:
        boundary = next(scope for scope in universe["scopes"] if scope["scope_id"] == "global_person_story_index_boundary")
        add("graph_scope_gap", "open", "The global PersonStory index is wider than the published Story graph and cannot be materialized without canonical Story nodes.", edge_ids=[], future_relevance="future wider research universe")
        rows[-1]["boundary"] = {"excluded_link_count": boundary["links_outside_published_story_scope"], "outside_story_id_count": boundary["outside_story_id_count"]}

    for orphan in audit.get("inherited_h0c_issues", {}).get("orphan_nodes", []):
        node_type, _, node_id = str(orphan).partition(":")
        add("isolated_node", "open", f"Protected H0C node {orphan} remains isolated; HG0 does not invent a connecting fact.", node_ids=[str(orphan)], person_ids=[node_id] if node_type == "Person" else [], story_ids=[node_id] if node_type == "Story" else [], future_relevance=classify_orphan(inputs, str(orphan)))
        rows[-1]["isolation_classification"] = classify_orphan(inputs, str(orphan))

    for layer, metric in sorted(sufficiency["layers"].items()):
        if layer == "combined":
            continue
        if metric["classification"] in {"pilot_only", "insufficient"}:
            add("weak_layer_coverage", "open", f"Layer {layer} is classified as {metric['classification']}: {metric['classification_reason']}", future_relevance=f"future {layer} enrichment")
        unknown = int(metric["temporal_distribution"].get("unknown", 0))
        total = int(metric["semantic_edge_count"])
        if total and unknown / total >= 0.50:
            add("missing_temporal_semantics", "open", f"Layer {layer} has {unknown}/{total} semantic edges without bounded temporal values; unknown is retained rather than dated by topology.", future_relevance="temporal graph experiments")

    spatial = sufficiency["spatial"]
    if spatial["location_entity_count"] and spatial["coordinate_precision_distribution"].get("unknown", 0):
        add("spatial_precision_gap", "open", "Historical Locations remain valid without exact modern coordinates; spatial experiments must use typed historical identity and precision masks.", future_relevance="spatial graph experiments")
    for collision in inputs["h0c_audit"].get("issues", {}).get("identity_collision_surfaces", []):
        add("alias_collision", "open", f"Generic alias surface {collision.get('surface')} remains unresolved; graph topology cannot resolve it.", person_ids=collision.get("person_ids", []), future_relevance="identity audit upstream")
    ratio = float(bias["story_layer_dominance"]["story_related_edge_ratio"])
    if ratio >= 0.70:
        add("story_layer_dominance", "open", f"Story-related edges account for {ratio:.1%} of the H0C semantic graph edge set; use layer-restricted views before ML.", future_relevance="ML0 experiment design")
    for layer, distribution in sorted(bias["review_status_by_layer"].items()):
        candidate = int(distribution.get("candidate", 0))
        reviewed = int(distribution.get("reviewed", 0))
        if candidate > reviewed and candidate >= 5:
            add("review_status_imbalance", "open", f"Layer {layer} has more candidate than reviewed semantic edges; candidate edges must not be treated as gold labels.", future_relevance="uncertainty-aware graph projection")
    for issue_name in ["dangling_edges", "dangling_fact_references", "unsupported_edges", "duplicate_semantic_edges", "invalid_temporal_intervals", "ontology_endpoint_conflicts"]:
        if audit["issue_counts"].get(issue_name, 0):
            add("graph_integrity_failure", "blocking", f"HG0 graph audit reports {audit['issue_counts'][issue_name]} {issue_name}.", edge_ids=audit["issues"].get(issue_name, []), future_relevance="HG0 validation")

    return {
        "schema": 1,
        "stage": "hg0-graph-gap-audit",
        "scope_id": universe["default_scope_id"],
        "category_catalog": ["graph_scope_gap", "isolated_node", "weak_layer_coverage", "missing_temporal_semantics", "missing_location_semantics", "missing_event_context", "missing_office_context", "missing_family_endpoint", "alias_collision", "evidence_imbalance", "story_layer_dominance", "review_status_imbalance", "temporal_scope_conflict", "spatial_precision_gap", "graph_integrity_failure"],
        "records": sorted(rows, key=lambda row: row["gap_id"]),
        "summary": {
            "gap_count": len(rows),
            "open_count": sum(row["status"] == "open" for row in rows),
            "blocking_count": sum(row["status"] == "blocking" for row in rows),
            "by_category": dict(sorted(Counter(row["category"] for row in rows).items())),
        },
        "policy": "HG0 diagnoses graph insufficiency and does not reflexively enrich H0C facts or create artificial negative edges.",
    }


def build_ml_contract(ontology: Mapping[str, Any], universe: Mapping[str, Any], graph: Mapping[str, Any], temporal: Mapping[str, Any], sufficiency: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": 1,
        "stage": "hg0-ml0-readiness",
        "framework_neutral": True,
        "graph_id": graph["graph_id"],
        "scope_id": universe["default_scope_id"],
        "node_contract": {
            "required_fields": ["node_id", "node_type", "canonical_reference", "scope_role", "evidence_ids", "review_status", "assertion_status", "reified_fact_node"],
            "optional_fields": ["label", "source_fact", "fact_ids", "temporal", "uncertainty_state"],
            "stable_id_rule": "Canonical H0C entity IDs are reused; reified IDs are deterministic projections of canonical fact IDs.",
        },
        "edge_contract": {
            "required_fields": ["edge_id", "edge_type", "source", "target", "graph_layer", "layer_memberships", "source_facts", "fact_ids", "evidence_ids", "review_status", "assertion_status", "uncertainty_state", "temporal", "projection_role"],
            "optional_fields": ["relation_ids", "provenance_refs", "attributes", "source_h0c_edge_id"],
            "traceability_rule": "Every edge must resolve to H0C fact IDs and Evidence IDs or explicit source provenance.",
            "multi_edge_rule": "Independent edge types may share endpoints; duplicate same-type semantic edges with the same fact set are invalid.",
        },
        "projection_views": [
            {"view_id": "all", "filter": "All materialized HG0 edges; preserve candidate/unknown metadata."},
            {"view_id": "reviewed_only", "filter": "review_status == reviewed; this is not a claim that omitted edges are negative."},
            {"view_id": "reviewed_plus_candidate", "filter": "review_status in {reviewed,candidate}; uncertainty remains attached."},
            {"view_id": "strict_temporal_interval", "filter": "Bounded/one-sided interval overlap only; unknown and relative-only facts are separate."},
        ],
        "temporal_contract": temporal["slice_query_contract"],
        "missingness_contract": {
            "missing_edge_is_negative": False,
            "unknown_is_false": False,
            "candidate_is_reviewed": False,
            "approximate_is_exact": False,
            "negative_facts_generated": False,
            "required_behavior": "Future experiments must carry observed-positive, candidate, unknown, conflicted, and explicit-negative states separately; HG0 generates no negative samples.",
        },
        "raw_feature_availability": [
            "node type and canonical reference",
            "typed degree/counts by layer",
            "Story participation role counts",
            "temporal precision/state masks",
            "Office/Clan/Event/Location incidence",
            "review/assertion/evidence availability masks",
        ],
        "research_question_readiness": [
            {"question": "heterogeneous structure representation", "classification": sufficiency["layers"]["combined"]["classification"], "reason": sufficiency["layers"]["combined"]["classification_reason"]},
            {"question": "constrained link-prediction pilot", "classification": "pilot_only", "reason": "Family/service layers are sparse and missing edges are unknown rather than negative; use reviewed-only, layer-specific evaluation."},
            {"question": "temporal representation pilot", "classification": sufficiency["layers"]["temporal"]["classification"], "reason": sufficiency["layers"]["temporal"]["classification_reason"]},
            {"question": "political-faction discovery", "classification": "premature", "reason": "No sourced faction ontology exists and service/political coverage is sparse; topology must not invent factions."},
            {"question": "event prediction", "classification": "premature", "reason": "Event and temporal coverage are too sparse and the published Story scope is selected."},
            {"question": "historical-importance ranking", "classification": "not_supported", "reason": "Degree and corpus visibility are selection-biased and are not historical importance labels."},
        ],
        "forbidden_artifacts": ["embeddings", "model_checkpoints", "train_test_split", "negative_samples", "learned_clusters", "centrality_as_historical_truth"],
        "model_artifacts_generated": False,
        "embeddings_generated": False,
        "training_split_generated": False,
        "policy": "HG0 defines a framework-neutral export contract; ML0 chooses models only after the sufficiency audit and without rewriting canonical facts.",
    }


def build_protection(inputs: Mapping[str, Any], universe: Mapping[str, Any], graph: Mapping[str, Any]) -> dict[str, Any]:
    h0c_paths = [
        INPUTS["h0c_graph"], INPUTS["h0c_audit"], INPUTS["h0c_facts"], INPUTS["h0c_participants"],
        INPUTS["h0c_readiness"], INPUTS["h0c_protection"], INPUTS["h0c_entity_manifest"],
    ]
    return {
        "schema": 1,
        "stage": "hg0-protection-manifest",
        "baseline_h0c_commit": BASELINE_H0C_COMMIT,
        "h0c_input_hashes": {name: sha256_file(path) for name, path in INPUTS.items() if name.startswith("h0c_")},
        "h0c_protection_manifest_sha256": sha256_file(INPUTS["h0c_protection"]),
        "protected_counts": {
            "persons": universe["protected_counts"]["production_persons"],
            "published_stories": universe["protected_counts"]["published_stories"],
            "global_person_story_links": universe["protected_counts"]["global_person_story_links"],
            "published_person_story_links": universe["protected_counts"]["published_person_story_links"],
        },
        "participant_freeze_sha256": inputs["h0c_participants"].get("participant_freeze_sha256"),
        "entity_id_manifest_sha256": sha256_file(INPUTS["h0c_entity_manifest"]),
        "graph_projection": {"node_count": len(graph["nodes"]), "edge_count": len(graph["edges"])},
        "policy": "HG0 is reproducible from H0C protected inputs. It never rewrites H0C facts, identity, participation, source text, or frontend data.",
    }


def build_metrics(inputs: Mapping[str, Any], universe: Mapping[str, Any], graph: Mapping[str, Any], temporal: Mapping[str, Any], audit: Mapping[str, Any], sufficiency: Mapping[str, Any], bias: Mapping[str, Any], gaps: Mapping[str, Any], ml_contract: Mapping[str, Any], protection: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": 1,
        "stage": "hg0-metrics",
        "scope": universe["protected_counts"],
        "graph": {
            "node_count": len(graph["nodes"]),
            "edge_count": len(graph["edges"]),
            "node_counts": graph["node_counts"],
            "edge_counts": graph["edge_counts"],
            "layer_counts": graph["layer_counts"],
            "projection_roles": graph["projection_roles"],
            "component_summary": sufficiency["graph_summary"],
            "audit_issue_counts": audit["issue_counts"],
        },
        "temporal": temporal["coverage"],
        "spatial": sufficiency["spatial"],
        "sufficiency": {layer: {"classification": metric["classification"], "canonical_node_coverage_ratio": metric["canonical_node_coverage_ratio"], "semantic_edge_count": metric["semantic_edge_count"]} for layer, metric in sorted(sufficiency["layers"].items())},
        "bias": {
            "story_related_edge_ratio": bias["story_layer_dominance"]["story_related_edge_ratio"],
            "published_scope_excluded_link_ratio": bias["published_scope_selection"]["excluded_link_ratio"],
            "top_10_person_story_share": bias["person_story_degree_concentration"]["top_10_share"],
        },
        "gaps": gaps["summary"],
        "ml0": {
            "framework_neutral": ml_contract["framework_neutral"],
            "model_artifacts_generated": ml_contract["model_artifacts_generated"],
            "embeddings_generated": ml_contract["embeddings_generated"],
            "training_split_generated": ml_contract["training_split_generated"],
        },
        "protected": protection["protected_counts"],
        "future_boundary": {"hg0_implemented": True, "ml0_implemented": False, "gnn_implemented": False, "er2_implemented": False},
        "artifact_hashes": {},
        "input_hashes": {},
    }


def build_outputs() -> dict[str, Any]:
    inputs = load_inputs()
    ontology = build_ontology(inputs["h0c_graph"])
    universe = build_universe(inputs)
    graph = build_graph(inputs)
    temporal = build_temporal(inputs, graph, universe)
    graph_audit = build_graph_audit(inputs, graph, ontology)
    sufficiency = build_sufficiency(inputs, graph, universe, temporal)
    bias = build_bias(inputs, graph, universe)
    gaps = build_gaps(inputs, universe, graph, graph_audit, sufficiency, bias)
    ml_contract = build_ml_contract(ontology, universe, graph, temporal, sufficiency)
    protection = build_protection(inputs, universe, graph)

    documents = {
        "ontology": ontology,
        "universe": universe,
        "graph": graph,
        "temporal": temporal,
        "graph_audit": graph_audit,
        "sufficiency": sufficiency,
        "bias": bias,
        "gaps": gaps,
        "ml_contract": ml_contract,
        "protection": protection,
    }
    for name, document in documents.items():
        write_json(OUTPUTS[name], document)
    metrics = build_metrics(inputs, universe, graph, temporal, graph_audit, sufficiency, bias, gaps, ml_contract, protection)
    metrics["artifact_hashes"] = {name: sha256_file(path) for name, path in OUTPUTS.items() if name != "metrics"}
    metrics["input_hashes"] = {name: sha256_file(path) for name, path in INPUTS.items() if name.startswith("h0c_") or name in {"person_story_links", "sc1_site"}}
    write_json(OUTPUTS["metrics"], metrics)
    return {**documents, "metrics": metrics}


def main() -> int:
    output = build_outputs()
    graph = output["graph"]
    sufficiency = output["sufficiency"]
    print(
        "HG0 Historical Graph: "
        f"{len(graph['nodes'])} nodes, {len(graph['edges'])} edges, "
        f"{sufficiency['graph_summary']['connected_component_count']} components, "
        f"{sufficiency['graph_summary']['isolated_node_count']} isolated nodes; "
        f"combined={sufficiency['layers']['combined']['classification']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
