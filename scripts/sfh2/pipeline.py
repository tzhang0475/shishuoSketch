"""SFH2/HIR1 orchestration.

The pipeline is an additive projection over the 188-story SFH1 universe.  A
run can be replayed offline from its input snapshot and raw SFH2 responses;
no function in this module writes a canonical artifact.
"""

from __future__ import annotations

import collections
from pathlib import Path
from typing import Any, Mapping

from .audit import failure_attribution, fragmentation_analysis, human_audit_sample, prior_candidate_dedup_audit
from .common import MODEL, OUTPUT_ROOT, ROOT, RUN_VERSION, flags, file_hash, normalize_form, read_json, stable_hash, text, write_json
from .consolidation import build_blocking, build_existing_link_candidates, consolidate_entities, run_existing_person_links, run_pair_judgments
from .inputs import build_candidate_observations, freeze_input_manifest, load_documents
from .llm import SFH2Client
from .projections import build_consolidated_graph, build_person_knowledge, family_projection, growth_series, relation_endpoint_reprojection


def _sfh1_metrics() -> dict[str, Any]:
    return read_json(ROOT / "data/generated/sfh1/metrics.json", {}) or {}


def _before_graph() -> dict[str, Any]:
    series = read_json(ROOT / "data/generated/sfh1/hge1-recalibrated-growth-series.json", {}) or {}
    row = next((item for item in series.get("series", []) or [] if text(item.get("wave")) == "HGE1-WB-SFH1"), None)
    if row:
        return {"summary": {"node_count": row.get("graph_nodes", 0), "edge_count": row.get("graph_edges", 0), "connected_component_count": row.get("connected_components", 0), "largest_component_size": row.get("largest_component_size", row.get("largest_component", 0)), "isolated_node_count": row.get("isolated_nodes", 0)}}
    return read_json(ROOT / "data/derived/hg0-graph-projection.json", {}) or {}


def _profile_suppression_audit(observations: Mapping[str, Any], link_candidates: Mapping[str, Any], documents: Mapping[str, Any]) -> dict[str, Any]:
    overlay = documents.get("hda2_overlay") or []
    rows = overlay if isinstance(overlay, list) else overlay.get("records", []) or []
    suppressed = {(normalize_form(row.get("target_surface")), text(row.get("person_id"))) for row in rows if isinstance(row, Mapping) and text(row.get("action")) == "suppress_claim"}
    hits: list[dict[str, Any]] = []
    for record in link_candidates.get("records", []) or []:
        surface = text(record.get("surface"))
        for candidate in record.get("candidates", []) or []:
            pair = (normalize_form(surface), text(candidate.get("person_id")))
            if pair in suppressed:
                hits.append({"observation_id": record.get("observation_id"), "surface": surface, "person_id": pair[1], "reason": "suppressed_HDA2_claim_reintroduced"})
    return flags({"suppressed_claim_count": len(suppressed), "suppressed_claims": [{"surface": surface, "person_id": pid} for surface, pid in sorted(suppressed)], "reintroduced": hits, "reintroduced_count": len(hits), "candidate_only": True, "canonical_write_back": False})


def _known_forbidden(observations: Mapping[str, Any], consolidation: Mapping[str, Any], documents: Mapping[str, Any]) -> list[dict[str, Any]]:
    forbidden = {
        ("09-pinzao-088", "仲文", "朱伺"),
        ("09-pinzao-018", "潁", "鄧攸"),
        ("06-yaliang-041", "殷荆州", "王恭"),
        ("02-yanyu-086", "王子敬", "王恭"),
        ("34-pilou-001", "主", "王敦"),
        ("02-yanyu-046", "謝豫章", "謝尚"),
        ("05-fangzheng-028", "敦主簿", "王敦"),
    }
    names = {text(row.get("person_id")): text(row.get("canonical_name")) for row in (documents.get("people") or {}).get("people", []) or [] if isinstance(row, Mapping)}
    entity_by_mention = {text(row.get("mention_id")): dict(row) for row in consolidation.get("observation_entities", []) or []}
    obs_by_mention = {text(row.get("mention_id")): dict(row) for row in observations.get("records", []) or []}
    failures: list[dict[str, Any]] = []
    for story, surface, wrong in sorted(forbidden):
        for mention_id, obs in obs_by_mention.items():
            if text(obs.get("story_id")) != story or text(obs.get("surface")) != surface:
                continue
            entity = entity_by_mention.get(mention_id, {})
            if names.get(text(entity.get("entity_id"))) == wrong:
                failures.append({"story_id": story, "surface": surface, "wrong_person": wrong, "mention_id": mention_id, "entity": entity.get("entity_id")})
    return failures


def _cluster_validation(consolidation: Mapping[str, Any], blocking: Mapping[str, Any]) -> dict[str, Any]:
    explicit = {tuple(sorted((text(row.get("left")), text(row.get("right"))))) for row in blocking.get("explicit_distinct_pairs", []) or []}
    violations: list[dict[str, Any]] = []
    for cluster in consolidation.get("candidate_clusters", []) or []:
        members = sorted(text(value) for value in cluster.get("member_observation_ids", []) if text(value))
        for index, left in enumerate(members):
            for right in members[index + 1:]:
                if (left, right) in explicit:
                    violations.append({"cluster_id": cluster.get("cluster_id"), "left": left, "right": right, "reason": "explicit_distinct_members"})
    return flags({"schema": "sfh2-cluster-validation-v1", "cluster_count": len(consolidation.get("candidate_clusters", []) or []), "explicit_distinct_cluster_violations": violations, "violation_count": len(violations), "candidate_only": True, "canonical_write_back": False})


def _metrics(observations: Mapping[str, Any], links: Mapping[str, Any], blocking: Mapping[str, Any], pairs: Mapping[str, Any], consolidation: Mapping[str, Any], relations: Mapping[str, Any], graph: Mapping[str, Any], growth: Mapping[str, Any], client_metrics: Mapping[str, Any], suppression: Mapping[str, Any], cluster_validation: Mapping[str, Any], documents: Mapping[str, Any]) -> dict[str, Any]:
    sfh1_metrics = _sfh1_metrics()
    final_states = collections.Counter(text(row.get("final_state")) for row in (documents.get("final") or {}).get("records", []) or [])
    before_relations = collections.Counter(text(row.get("endpoint_state")) for row in (documents.get("relations") or {}).get("records", []) or [])
    after_relations = collections.Counter(text(row.get("endpoint_state")) for row in relations.get("records", []) or [])
    entity_rows = consolidation.get("observation_entities", []) or []
    existing_before = {text(row.get("person_id")) for row in (documents.get("final") or {}).get("records", []) or [] if text(row.get("person_id"))}
    existing_after = {text(row.get("entity_id")) for row in entity_rows if text(row.get("entity_type")) == "production_person" and text(row.get("entity_id"))}
    forbidden = _known_forbidden(observations, consolidation, documents)
    relation_complete = sum(after_relations[key] for key in ("both_existing_resolved", "existing_plus_candidate", "both_candidate_resolved"))
    unique_edges = len({(text(row.get("subject_endpoint")), text(row.get("object_endpoint")), text(row.get("relation_type")), text(row.get("story_id"))) for row in relations.get("records", []) or [] if text(row.get("subject_endpoint")) and text(row.get("object_endpoint"))})
    source_candidate_ids = {text(row.get("previous_candidate_person_id")) for row in observations.get("records", []) or [] if text(row.get("previous_candidate_person_id"))}
    candidate_clusters = consolidation.get("candidate_clusters", []) or []
    anonymous = sum(text(row.get("entity_type")) in {"structural_reference", "collective_reference"} for row in entity_rows)
    unresolved_entities = sum(text(row.get("entity_type")) == "unresolved_reference" for row in entity_rows) + sum(text(row.get("identity_confidence_state")) == "unresolved_candidate_entity" for row in candidate_clusters)
    suppressed = suppression.get("reintroduced_count", 0)
    return flags({
        "schema": "sfh2-metrics-v1",
        "stories_retained": len((documents.get("packets") or {}).get("packets", []) or []),
        "person_mentions": sum(text(row.get("entity_kind")) == "person" for row in observations.get("records", []) or []),
        "candidate_observations": int(sum(bool(text(row.get("previous_candidate_person_id"))) for row in observations.get("records", []) or [])),
        "candidate_entity_eligible_observations": int(observations.get("entity_resolution_candidate_observation_count") or 0),
        "original_sfh1_candidate_person_ids": len(source_candidate_ids),
        "original_sfh1_candidate_person_id_list": sorted(source_candidate_ids),
        "linked_to_existing_persons": sum(text(row.get("status")) in {"linked_existing", "reused_sfh1_existing"} for row in links.get("records", []) or []),
        "candidate_observations_absorbed_into_existing": sum(text(row.get("status")) in {"linked_existing", "reused_sfh1_existing"} for row in links.get("records", []) or []),
        "candidate_ids_merged_with_candidate_ids": int(consolidation.get("candidate_nodes_merged") or 0),
        "unique_new_candidate_entities": len(candidate_clusters),
        "anonymous_structural_references": anonymous,
        "unresolved_entities": unresolved_entities,
        "existing_persons_reached_before": len(existing_before),
        "existing_persons_reached_after": len(existing_after),
        "existing_person_ids_reached_after": sorted(existing_after),
        "stable_existing_occurrence_decisions_before": final_states["stable_entity_resolved"],
        "total_semantic_relations": len((documents.get("relations") or {}).get("records", []) or []),
        "endpoint_complete_relations_before": before_relations["complete"],
        "endpoint_complete_relations_after": relation_complete,
        "endpoint_state_before": dict(sorted(before_relations.items())),
        "endpoint_state_after": dict(sorted(after_relations.items())),
        "unique_consolidated_relation_edges": unique_edges,
        "graph_nodes_before": _before_graph().get("summary", {}).get("node_count", 0),
        "graph_nodes_after": graph.get("summary", {}).get("node_count", 0),
        "graph_components_before": _before_graph().get("summary", {}).get("connected_component_count", 0),
        "graph_components_after": graph.get("summary", {}).get("connected_component_count", 0),
        "largest_component_before": _before_graph().get("summary", {}).get("largest_component_size", 0),
        "largest_component_after": graph.get("summary", {}).get("largest_component_size", 0),
        "edge_count_before": _before_graph().get("summary", {}).get("edge_count", 0),
        "edge_count_after": graph.get("summary", {}).get("edge_count", 0),
        "candidate_nodes_merged": consolidation.get("candidate_nodes_merged", 0),
        "candidate_nodes_linked_to_existing": sum(text(row.get("status")) in {"linked_existing", "reused_sfh1_existing"} for row in links.get("records", []) or []),
        "forbidden_identity_merges": forbidden,
        "forbidden_identity_merge_count": len(forbidden),
        "suppressed_hda2_claim_reentry_count": suppressed,
        "explicit_distinct_cluster_violations": cluster_validation.get("violation_count", 0),
        "candidate_only": True,
        "canonical_write_back": False,
        "relation_family_counts_after": {family: len([row for row in relations.get("records", []) or [] if text(row.get("relation_type")) == family]) for family in ("kinship", "marriage", "office")},
        "cost": client_metrics,
        "sfh1_provider_tokens_reference": int(sfh1_metrics.get("provider", {}).get("total_tokens") or 0),
        "sfh1_dense_packet_failures_reused": int(sum(text(row.get("failure_stage")) == "provider_failure" for row in (documents.get("final") or {}).get("records", []) or [])),
        "dense_packet_recovered": 0,
        "dense_packet_still_failed": int(sum(text(row.get("failure_stage")) == "provider_failure" for row in (documents.get("final") or {}).get("records", []) or [])),
        "growth_series": growth.get("series", []),
    })


def run(*, run_id: str = "sfh2-hir1-v1", live: bool = False, max_link_calls: int | None = None, max_pair_calls: int | None = None) -> dict[str, Any]:
    manifest = freeze_input_manifest()
    documents = load_documents()
    observations = build_candidate_observations(documents)
    link_candidates = build_existing_link_candidates(observations, documents)
    run_dir = OUTPUT_ROOT / "live" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    client = SFH2Client(run_dir, live=live)
    if max_link_calls is None:
        max_link_calls = 256 if live else 0
    if max_pair_calls is None:
        max_pair_calls = 256 if live else 0
    links = run_existing_person_links(client, observations, link_candidates, documents, max_calls=max_link_calls)
    blocking = build_blocking(observations, links)
    pairs = run_pair_judgments(client, observations, blocking, max_calls=max_pair_calls)
    consolidation = consolidate_entities(observations, links, blocking, pairs, documents)
    relation_projection = relation_endpoint_reprojection(observations, consolidation, documents)
    graph = build_consolidated_graph(observations, consolidation, relation_projection, documents)
    person_knowledge, candidate_knowledge = build_person_knowledge(observations, consolidation, relation_projection, documents)
    growth = growth_series(observations, consolidation, relation_projection, graph, documents)
    prior_audit = prior_candidate_dedup_audit(observations, consolidation, documents)
    suppression = _profile_suppression_audit(observations, link_candidates, documents)
    cluster_validation = _cluster_validation(consolidation, blocking)
    failures = failure_attribution(observations, links, consolidation, blocking, pairs)
    human = human_audit_sample(observations, links, pairs, consolidation)
    client.write_transport()
    client_metrics = client.metrics()
    metrics = _metrics(observations, links, blocking, pairs, consolidation, relation_projection, graph, growth, client_metrics, suppression, cluster_validation, documents)
    # Deliberately omit wall-clock completion time.  The manifest is part of
    # the replay contract; operational timing belongs in raw transport rows,
    # not in deterministic derived output.
    live_manifest = flags({
        "schema": "sfh2-live-manifest-v1",
        "run_id": run_id,
        "run_version": RUN_VERSION,
        "model": MODEL,
        "input_snapshot_hash": manifest.get("input_snapshot_hash"),
        "live": live,
        "raw_response_count": len(list(client.raw_dir.glob("*.json"))),
        "replayed_cache_hits": client_metrics.get("cache_hits", 0),
        "new_live_calls": client_metrics.get("new_live_calls", 0),
        "candidate_only": True,
        "canonical_write_back": False,
    })
    write_json(run_dir / "manifest.json", live_manifest)
    outputs: dict[str, Any] = {
        "input-manifest.json": manifest,
        "candidate-observations.json": observations,
        "existing-person-link-candidates.json": link_candidates,
        "existing-person-link-results.json": links,
        "candidate-blocking.json": blocking,
        "candidate-pair-judgments.json": pairs,
        "candidate-clusters.json": {"schema": "sfh2-candidate-clusters-v1", "records": consolidation.get("candidate_clusters", []), "candidate_only": True, "canonical_write_back": False},
        "cluster-validation.json": cluster_validation,
        "entity-consolidation.json": consolidation,
        "relation-endpoint-reprojection.json": relation_projection,
        "consolidated-graph.json": graph,
        "person-knowledge.json": person_knowledge,
        "candidate-person-knowledge.json": candidate_knowledge,
        "growth-series.json": growth,
        "fragmentation-analysis.json": fragmentation_analysis(_before_graph(), graph, consolidation, links),
        "human-audit-sample.json": human,
        "cost-metrics.json": client_metrics,
        "failure-attribution.json": failures,
        "prior-candidate-dedup-audit.json": prior_audit,
        "metrics.json": metrics,
        "hda2-suppression-audit.json": suppression,
        "kinship-projection.json": family_projection(relation_projection, "kinship"),
        "marriage-projection.json": family_projection(relation_projection, "marriage"),
        "office-projection.json": family_projection(relation_projection, "office"),
    }
    for name, value in outputs.items():
        write_json(OUTPUT_ROOT / name, value)
    return {"manifest": manifest, "metrics": metrics, "outputs": sorted(outputs), "run_dir": str(run_dir.relative_to(ROOT))}
