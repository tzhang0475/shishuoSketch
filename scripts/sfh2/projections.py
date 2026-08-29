"""Deterministic SFH2 entity, relation, graph, and growth projections."""

from __future__ import annotations

import collections
from pathlib import Path
from typing import Any, Mapping, Sequence

from .common import ROOT, flags, normalize_form, read_json, stable_hash, text
from .inputs import _packet_index


def _entity_index(consolidation: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {text(row.get("mention_id")): dict(row) for row in consolidation.get("observation_entities", []) or [] if text(row.get("mention_id"))}


def _obs_index(observations: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {text(row.get("mention_id")): dict(row) for row in observations.get("records", []) or [] if text(row.get("mention_id"))}


def _endpoint_kind(entity: Mapping[str, Any] | None) -> str:
    if not entity:
        return "unresolved"
    return {
        "production_person": "existing",
        "candidate_person_entity": "candidate",
        "structural_reference": "structural",
        "collective_reference": "collective",
        "non_person": "non_person",
        "unresolved_reference": "unresolved",
    }.get(text(entity.get("entity_type")), "unresolved")


def _state(subject: Mapping[str, Any] | None, object_row: Mapping[str, Any] | None) -> str:
    sk, ok = _endpoint_kind(subject), _endpoint_kind(object_row)
    if sk == "non_person" or ok == "non_person":
        return "semantic_reference_blocked"
    if sk == "structural" or ok == "structural" or sk == "collective" or ok == "collective":
        if sk in {"existing", "candidate"} or ok in {"existing", "candidate"}:
            return "semantic_reference_blocked"
        return "semantic_reference_blocked"
    if sk == "existing" and ok == "existing":
        return "both_existing_resolved"
    if {sk, ok} == {"existing", "candidate"}:
        return "existing_plus_candidate"
    if sk == "candidate" and ok == "candidate":
        return "both_candidate_resolved"
    if sk in {"existing", "candidate"} or ok in {"existing", "candidate"}:
        return "single_endpoint_resolved"
    return "both_unresolved"


def relation_endpoint_reprojection(observations: Mapping[str, Any], consolidation: Mapping[str, Any], documents: Mapping[str, Any]) -> dict[str, Any]:
    entity_by_mention = _entity_index(consolidation)
    observation_by_mention = _obs_index(observations)
    source = documents.get("relations") or {}
    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for relation in source.get("records", []) or []:
        if not isinstance(relation, Mapping):
            continue
        subject_mention = text(relation.get("subject_mention_id"))
        object_mention = text(relation.get("object_mention_id"))
        subject = entity_by_mention.get(subject_mention)
        object_row = entity_by_mention.get(object_mention)
        subject_endpoint = subject.get("entity_id") if subject and _endpoint_kind(subject) in {"existing", "candidate", "structural", "collective"} else None
        object_endpoint = object_row.get("entity_id") if object_row and _endpoint_kind(object_row) in {"existing", "candidate", "structural", "collective"} else None
        state = _state(subject, object_row)
        if subject_endpoint and object_endpoint and subject_endpoint == object_endpoint and text(relation.get("relation_type")) != "other":
            rejected.append(flags({"relation_id": relation.get("relation_id"), "story_id": relation.get("story_id"), "reason": "rejected_self_relation", "relation": dict(relation), "subject_endpoint": subject_endpoint, "object_endpoint": object_endpoint}))
            continue
        records.append(flags({
            "relation_id": relation.get("relation_id") or f"sfh2-relation-{stable_hash(relation)[:24]}",
            "story_id": relation.get("story_id"),
            "relation_type": relation.get("relation_type"),
            "predicate_surface": relation.get("predicate_surface"),
            "evidence_id": relation.get("evidence_id"),
            "subject_mention_id": subject_mention,
            "object_mention_id": object_mention,
            "original_subject_endpoint": relation.get("subject_endpoint"),
            "original_object_endpoint": relation.get("object_endpoint"),
            "original_endpoint_state": relation.get("endpoint_state"),
            "subject_endpoint": subject_endpoint,
            "object_endpoint": object_endpoint,
            "subject_endpoint_type": _endpoint_kind(subject),
            "object_endpoint_type": _endpoint_kind(object_row),
            "endpoint_state": state,
            "identity_chain": {
                "subject": {"mention_id": subject_mention, "observation_id": observation_by_mention.get(subject_mention, {}).get("observation_id"), "entity": subject},
                "object": {"mention_id": object_mention, "observation_id": observation_by_mention.get(object_mention, {}).get("observation_id"), "entity": object_row},
            },
            "candidate_only": True,
            "canonical_write_back": False,
        }))
    records.sort(key=lambda row: text(row.get("relation_id")))
    return flags({
        "schema": "sfh2-relation-endpoint-reprojection-v1",
        "records": records,
        "rejected": rejected,
        "total_input_relations": len(source.get("records", []) or []),
        "endpoint_state_counts": dict(sorted(collections.Counter(text(row.get("endpoint_state")) for row in records).items())),
        "candidate_only": True,
        "canonical_write_back": False,
    })


def family_projection(relations: Mapping[str, Any], family: str) -> dict[str, Any]:
    rows = [dict(row) for row in relations.get("records", []) or [] if text(row.get("relation_type")) == family]
    return flags({"schema": f"sfh2-{family}-projection-v1", "family": family, "records": rows, "endpoint_state_counts": dict(sorted(collections.Counter(text(row.get("endpoint_state")) for row in rows).items())), "candidate_only": True, "canonical_write_back": False})


def _graph_components(nodes: Sequence[Mapping[str, Any]], edges: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    keys = {f"{text(row.get('node_type'))}:{text(row.get('node_id'))}" for row in nodes if text(row.get("node_type")) and text(row.get("node_id"))}
    adjacency = {key: set() for key in keys}
    for edge in edges:
        source, target = edge.get("source") or {}, edge.get("target") or {}
        left = f"{text(source.get('node_type'))}:{text(source.get('node_id'))}"
        right = f"{text(target.get('node_type'))}:{text(target.get('node_id'))}"
        if left in adjacency and right in adjacency and left != right:
            adjacency[left].add(right); adjacency[right].add(left)
    seen: set[str] = set(); sizes: list[int] = []
    for start in sorted(adjacency):
        if start in seen:
            continue
        stack = [start]; seen.add(start); size = 0
        while stack:
            current = stack.pop(); size += 1
            for other in adjacency[current]:
                if other not in seen:
                    seen.add(other); stack.append(other)
        sizes.append(size)
    sizes.sort(reverse=True)
    return {"node_count": len(keys), "edge_count": len(edges), "connected_component_count": len(sizes), "largest_component_size": sizes[0] if sizes else 0, "isolated_node_count": sum(not value for value in adjacency.values()), "component_size_distribution": sizes[:30]}


def _node_type(entity: Mapping[str, Any]) -> str:
    return "Person" if text(entity.get("entity_type")) == "production_person" else "CandidatePerson" if text(entity.get("entity_type")) == "candidate_person_entity" else "StructuralReference" if text(entity.get("entity_type")) == "structural_reference" else "CollectiveReference" if text(entity.get("entity_type")) == "collective_reference" else "UnresolvedReference"


def _add_node(nodes: dict[tuple[str, str], dict[str, Any]], node_type: str, node_id: Any, label: Any = None, **extra: Any) -> None:
    value = text(node_id)
    if not value:
        return
    key = (node_type, value)
    nodes.setdefault(key, {"node_type": node_type, "node_id": value, "label": label or value, **extra})


def build_consolidated_graph(observations: Mapping[str, Any], consolidation: Mapping[str, Any], relations: Mapping[str, Any], documents: Mapping[str, Any], story_ids: set[str] | None = None) -> dict[str, Any]:
    story_ids = set(story_ids) if story_ids is not None else None
    base = read_json(ROOT / "data/derived/hg0-graph-projection.json", {}) or {}
    nodes: dict[tuple[str, str], dict[str, Any]] = {}
    for row in base.get("nodes", []) or []:
        if isinstance(row, Mapping):
            _add_node(nodes, text(row.get("node_type")), row.get("node_id"), row.get("label"), **{key: value for key, value in row.items() if key not in {"node_type", "node_id", "label"}})
    entities = {text(row.get("observation_id")): dict(row) for row in consolidation.get("observation_entities", []) or [] if text(row.get("observation_id"))}
    entity_by_id: dict[str, dict[str, Any]] = {}
    for entity in entities.values():
        entity_id = text(entity.get("entity_id"))
        if entity_id and entity.get("entity_type") in {"production_person", "candidate_person_entity", "structural_reference", "collective_reference"}:
            # An existing/candidate endpoint can be shared by many mentions.
            # Keep a deterministic representative for relation-node typing.
            entity_by_id.setdefault(entity_id, entity)
    obs_by_id = {text(row.get("observation_id")): dict(row) for row in observations.get("records", []) or [] if text(row.get("observation_id"))}
    included_entity_ids: set[str] = set()
    for oid, entity in entities.items():
        obs = obs_by_id.get(oid, {})
        sid = text(obs.get("story_id"))
        if story_ids is not None and sid not in story_ids:
            continue
        etype = text(entity.get("entity_type"))
        if etype in {"production_person", "candidate_person_entity", "structural_reference", "collective_reference"} and text(entity.get("entity_id")):
            nid = text(entity.get("entity_id")); ntype = _node_type(entity)
            _add_node(nodes, ntype, nid, entity.get("entity_id"), scope_role="candidate_projection" if ntype != "Person" else "production_person")
            included_entity_ids.add(oid)
        if sid:
            _add_node(nodes, "Story", sid, sid, scope_role="sfh2_story")
    edges: list[dict[str, Any]] = [dict(edge) for edge in base.get("edges", []) or [] if isinstance(edge, Mapping)]
    edge_keys = {(text(edge.get("edge_type")), text((edge.get("source") or {}).get("node_type")), text((edge.get("source") or {}).get("node_id")), text((edge.get("target") or {}).get("node_type")), text((edge.get("target") or {}).get("node_id")), text(edge.get("story_id"))) for edge in edges}
    for oid in sorted(included_entity_ids):
        entity = entities[oid]; obs = obs_by_id.get(oid, {}); sid = text(obs.get("story_id")); ntype = _node_type(entity); nid = text(entity.get("entity_id"))
        key = ("sfh2_person_story", ntype, nid, "Story", sid, sid)
        if key in edge_keys:
            continue
        edge_keys.add(key)
        edges.append(flags({"edge_id": f"sfh2-person-story-{stable_hash({'entity': nid, 'story': sid})[:24]}", "edge_type": "sfh2_person_story", "source": {"node_type": ntype, "node_id": nid}, "target": {"node_type": "Story", "node_id": sid}, "story_id": sid, "candidate_only": True, "canonical_write_back": False}))
    for relation in relations.get("records", []) or []:
        sid = text(relation.get("story_id"))
        if story_ids is not None and sid not in story_ids:
            continue
        left, right = text(relation.get("subject_endpoint")), text(relation.get("object_endpoint"))
        if not left or not right:
            continue
        subject_entity = entity_by_id.get(left, {})
        object_entity = entity_by_id.get(right, {})
        if not subject_entity:
            subject_entity = {"entity_type": "production_person"} if left.startswith("person-") else {"entity_type": "candidate_person_entity"} if left.startswith("sfh2-candidate-entity-") else {}
        if not object_entity:
            object_entity = {"entity_type": "production_person"} if right.startswith("person-") else {"entity_type": "candidate_person_entity"} if right.startswith("sfh2-candidate-entity-") else {}
        ltype, rtype = _node_type(subject_entity), _node_type(object_entity)
        _add_node(nodes, ltype, left, left, scope_role="candidate_projection")
        _add_node(nodes, rtype, right, right, scope_role="candidate_projection")
        key = ("sfh2_relation", ltype, left, rtype, right, sid)
        if key in edge_keys:
            continue
        edge_keys.add(key)
        edges.append(flags({"edge_id": f"sfh2-relation-edge-{stable_hash({'relation': relation.get('relation_id'), 'left': left, 'right': right})[:24]}", "edge_type": "sfh2_relation", "relation_id": relation.get("relation_id"), "relation_type": relation.get("relation_type"), "source": {"node_type": ltype, "node_id": left}, "target": {"node_type": rtype, "node_id": right}, "story_id": sid, "candidate_only": True, "canonical_write_back": False}))
    node_rows = sorted(nodes.values(), key=lambda row: (text(row.get("node_type")), text(row.get("node_id"))))
    edges.sort(key=lambda row: text(row.get("edge_id")))
    summary = _graph_components(node_rows, edges)
    return flags({"schema": "sfh2-consolidated-graph-v1", "nodes": node_rows, "edges": edges, "summary": summary, "story_scope": sorted(story_ids) if story_ids is not None else "all_sfh1", "candidate_only": True, "canonical_write_back": False})


def _entity_status(entity: Mapping[str, Any]) -> str:
    etype = text(entity.get("entity_type"))
    return "resolved_existing" if etype == "production_person" else "resolved_candidate_entity" if etype == "candidate_person_entity" else "anonymous_or_structural" if etype in {"structural_reference", "collective_reference"} else "unresolved"


def build_person_knowledge(observations: Mapping[str, Any], consolidation: Mapping[str, Any], relations: Mapping[str, Any], documents: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    obs_by_id = {text(row.get("observation_id")): dict(row) for row in observations.get("records", []) or [] if text(row.get("observation_id"))}
    entity_rows = [dict(row) for row in consolidation.get("observation_entities", []) or []]
    entity_by_obs = {text(row.get("observation_id")): row for row in entity_rows}
    entities: dict[str, dict[str, Any]] = {}
    for row in entity_rows:
        if text(row.get("entity_type")) not in {"production_person", "candidate_person_entity"} or not text(row.get("entity_id")):
            continue
        eid = text(row.get("entity_id")); obs = obs_by_id.get(text(row.get("observation_id")), {})
        profile = entities.setdefault(eid, {"person_id": eid, "canonical_name": eid, "identity": {"observed_surfaces": set(), "aliases": set(), "courtesy_names": set(), "titles": set(), "occurrence_ids": set(), "identity_evidence": []}, "story_presence": {"story_ids": set(), "roles": set(), "main_text_occurrences": set(), "annotation_occurrences": set()}, "family": {"kinship_candidates": [], "marriage_candidates": []}, "offices": {"office_candidates": []}, "temporal": {"activity_evidence": [], "story_temporal_links": [], "bounded_intervals": []}, "social": {"relation_candidates": [], "resolved_neighbors": set()}, "evidence": {"source_works": set(), "evidence_refs": set()}})
        profile["identity"]["observed_surfaces"].add(text(obs.get("surface")))
        profile["identity"]["occurrence_ids"].add(text(row.get("mention_id")))
        source = obs.get("source_evidence") or {}
        ref = text(source.get("evidence_id"))
        if ref:
            profile["identity"]["identity_evidence"].append({"surface": obs.get("surface"), "occurrence_id": row.get("observation_id"), "mention_id": row.get("mention_id"), "evidence_ref": ref, "identity_status": _entity_status(row), "identity_basis": text(row.get("decision")), "candidate_only": True, "canonical_write_back": False})
            profile["evidence"]["evidence_refs"].add(ref)
        profile["story_presence"]["story_ids"].add(text(obs.get("story_id")))
        layer = text(source.get("source_layer"))
        profile["story_presence"]["annotation_occurrences" if layer == "liu_annotation" else "main_text_occurrences"].add(text(row.get("observation_id")))
        profile["evidence"]["source_works"].add("劉注" if layer == "liu_annotation" else "世說正文")
        if eid.startswith("person-"):
            profile["canonical_name"] = next((text(person.get("canonical_name")) for person in (documents.get("people") or {}).get("people", []) or [] if text(person.get("person_id")) == eid), eid)
    for relation in relations.get("records", []) or []:
        for side, endpoint_key in (("subject", "subject_endpoint"), ("object", "object_endpoint")):
            eid = text(relation.get(endpoint_key))
            if not eid or eid not in entities:
                continue
            target = entities[eid]
            family = text(relation.get("relation_type"))
            item = {key: relation.get(key) for key in ("relation_id", "story_id", "predicate_surface", "evidence_id", "subject_endpoint", "object_endpoint", "endpoint_state")}
            item.update({"status": "candidate", "candidate_only": True, "canonical_write_back": False})
            if family == "kinship": target["family"]["kinship_candidates"].append(item)
            elif family == "marriage": target["family"]["marriage_candidates"].append(item)
            elif family == "office": target["offices"]["office_candidates"].append(item)
            else: target["social"]["relation_candidates"].append(item)
            other = text(relation.get("object_endpoint" if side == "subject" else "subject_endpoint"))
            if other and other != eid:
                target["social"]["resolved_neighbors"].add(other)
            target["evidence"]["evidence_refs"].add(text(relation.get("evidence_id")))
            target["evidence"]["source_works"].add("世說正文" if text(relation.get("evidence_id")).endswith("-main") else "劉注")
    def freeze(value: Any) -> Any:
        if isinstance(value, set): return sorted(value)
        if isinstance(value, list): return [freeze(item) for item in value]
        if isinstance(value, Mapping): return {key: freeze(item) for key, item in value.items()}
        return value
    existing = []; candidates = []
    for eid, profile in sorted(entities.items()):
        row = freeze(profile)
        row["candidate_only"] = True; row["canonical_write_back"] = False
        (existing if eid.startswith("person-") else candidates).append(row)
    return flags({"schema": "sfh2-person-knowledge-v1", "records": existing, "count": len(existing), "candidate_only": True, "canonical_write_back": False}), flags({"schema": "sfh2-candidate-person-knowledge-v1", "records": candidates, "count": len(candidates), "candidate_only": True, "canonical_write_back": False})


def _story_ids(documents: Mapping[str, Any], filename: str) -> set[str]:
    doc = read_json(ROOT / filename, {}) or {}
    return {text(value) for value in doc.get("story_ids", []) or [] if text(value)}


def growth_series(observations: Mapping[str, Any], consolidation: Mapping[str, Any], relations: Mapping[str, Any], graph_all: Mapping[str, Any], documents: Mapping[str, Any]) -> dict[str, Any]:
    production = {text(row.get("story_id")) for row in (read_json(ROOT / "data/derived/ux2-story-index.json", {}) or {}).get("records", []) or [] if text(row.get("story_id"))}
    wave_a = _story_ids(documents, "data/annotation/hge1-wave-a-selection.json")
    wave_b = _story_ids(documents, "data/annotation/hge1-wave-b-selection.json")
    stages = [("baseline", production), ("HGE1-WA-SFH2", production | wave_a), ("HGE1-WB-SFH2", production | wave_a | wave_b)]
    # Relation projection is keyed by mention, while growth counts are keyed
    # by SFH2 observation.  Keep the two indexes explicit so a mention ID can
    # never be confused with an occurrence observation ID.
    entity_by_obs = {text(row.get("observation_id")): dict(row) for row in consolidation.get("observation_entities", []) or [] if text(row.get("observation_id"))}
    obs_rows = [dict(row) for row in observations.get("records", []) or []]
    cluster_rows = list(consolidation.get("candidate_clusters", []) or [])
    relation_rows = list(relations.get("records", []) or [])
    points: list[dict[str, Any]] = []
    for wave, story_ids in stages:
        selected_obs = [row for row in obs_rows if text(row.get("story_id")) in story_ids]
        selected_relations = [row for row in relation_rows if text(row.get("story_id")) in story_ids]
        selected_clusters = [row for row in cluster_rows if any(text(obs_rows_by_id.get(oid, {}).get("story_id")) in story_ids for oid in row.get("member_observation_ids", []))] if (obs_rows_by_id := {text(row.get("observation_id")): row for row in obs_rows}) else []
        existing = {text(entity_by_obs.get(text(row.get("observation_id")), {}).get("entity_id")) for row in selected_obs if text(entity_by_obs.get(text(row.get("observation_id")), {}).get("entity_type")) == "production_person"}
        person_story = {(text(entity_by_obs.get(text(row.get("observation_id")), {}).get("entity_id")), text(row.get("story_id"))) for row in selected_obs if text(entity_by_obs.get(text(row.get("observation_id")), {}).get("entity_type")) in {"production_person", "candidate_person_entity"}}
        resolved_entities = {text(entity_by_obs.get(text(row.get("observation_id")), {}).get("entity_id")) for row in selected_obs if text(entity_by_obs.get(text(row.get("observation_id")), {}).get("entity_type")) in {"production_person", "candidate_person_entity"}}
        point = {
            "wave": wave,
            "story_count": len(story_ids),
            "person_mentions": sum(text(row.get("entity_kind")) == "person" for row in selected_obs),
            "existing_person_count": len((documents.get("people") or {}).get("people", []) or []),
            "existing_persons_reached": len(existing),
            "candidate_observation_count": sum(text(row.get("classification")) == "candidate_observation" for row in selected_obs),
            "unique_candidate_entity_count": len({text(row.get("cluster_id")) for row in selected_clusters}),
            "anonymous_structural_reference_count": sum(text(entity_by_obs.get(text(row.get("observation_id")), {}).get("entity_type")) in {"structural_reference", "collective_reference"} for row in selected_obs),
            "unresolved_entity_count": sum(text(entity_by_obs.get(text(row.get("observation_id")), {}).get("entity_type")) == "unresolved_reference" for row in selected_obs),
            "person_story_count": len(person_story),
            "historical_relation_edge_count": sum(bool(row.get("subject_endpoint") and row.get("object_endpoint")) for row in selected_relations),
            "kinship_count": sum(text(row.get("relation_type")) == "kinship" for row in selected_relations),
            "marriage_count": sum(text(row.get("relation_type")) == "marriage" for row in selected_relations),
            "office_count": sum(text(row.get("relation_type")) == "office" for row in selected_relations),
            "social_relation_count": sum(text(row.get("relation_type")) not in {"kinship", "marriage", "office"} for row in selected_relations),
            "resolved_entity_count": len(resolved_entities),
            "review_load": sum(text(entity_by_obs.get(text(row.get("observation_id")), {}).get("entity_type")) in {"unresolved_reference", "structural_reference", "candidate_person_entity"} for row in selected_obs),
        }
        graph = build_consolidated_graph(observations, consolidation, relations, documents, story_ids)
        point.update({"graph_nodes": graph.get("summary", {}).get("node_count", 0), "graph_edges": graph.get("summary", {}).get("edge_count", 0), "connected_components": graph.get("summary", {}).get("connected_component_count", 0), "largest_component": graph.get("summary", {}).get("largest_component_size", 0), "isolated_nodes": graph.get("summary", {}).get("isolated_node_count", 0)})
        points.append(flags(point))
    for index, point in enumerate(points):
        previous = points[index - 1] if index else None
        delta_stories = int(point.get("story_count") or 0) - int(previous.get("story_count") or 0) if previous else 0
        if previous:
            point["delta"] = {key: (point.get(key, 0) - previous.get(key, 0)) for key in ("existing_persons_reached", "candidate_observation_count", "unique_candidate_entity_count", "person_story_count", "historical_relation_edge_count", "graph_nodes", "graph_edges", "unresolved_entity_count")}
            point["delta_stories"] = delta_stories
            point["entity_novelty_rate"] = round((point.get("unique_candidate_entity_count", 0) - previous.get("unique_candidate_entity_count", 0)) / delta_stories, 6) if delta_stories else 0
            point["observation_novelty_rate"] = round(point.get("candidate_observation_count", 0) - previous.get("candidate_observation_count", 0), 6) / delta_stories if delta_stories else 0
            point["edge_novelty_rate"] = round((point.get("historical_relation_edge_count", 0) - previous.get("historical_relation_edge_count", 0)) / delta_stories, 6) if delta_stories else 0
            existing_edge_delta = sum(text(row.get("endpoint_state")) == "both_existing_resolved" and text(row.get("story_id")) in (wave_a if point.get("wave") == "HGE1-WA-SFH2" else wave_b) for row in relation_rows)
            point["new_existing_node_edges"] = existing_edge_delta
            point["densification_rate"] = round(existing_edge_delta / delta_stories, 6) if delta_stories else 0
            point["existing_node_edge_share"] = round(existing_edge_delta / max(1, point.get("historical_relation_edge_count", 0) - previous.get("historical_relation_edge_count", 0)), 6)
        else:
            point["delta"] = {}; point["delta_stories"] = 0; point["entity_novelty_rate"] = 0; point["observation_novelty_rate"] = 0; point["edge_novelty_rate"] = 0; point["new_existing_node_edges"] = 0; point["densification_rate"] = 0; point["existing_node_edge_share"] = 0
    old = read_json(ROOT / "data/generated/sfh1/hge1-recalibrated-growth-series.json", {}) or {}
    return flags({"schema": "sfh2-growth-series-v1", "series": points, "sfh1_reference_series": old.get("series", []), "candidate_observation_is_not_person_metric": True, "candidate_only": True, "canonical_write_back": False})
