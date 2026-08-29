"""Auditable SFH2 consolidation diagnostics and human-review preparation."""

from __future__ import annotations

import collections
from typing import Any, Mapping, Sequence

from .common import ROOT, flags, normalize_form, read_json, stable_hash, text


def prior_candidate_dedup_audit(observations: Mapping[str, Any], consolidation: Mapping[str, Any], documents: Mapping[str, Any]) -> dict[str, Any]:
    entity_by_obs = {text(row.get("observation_id")): dict(row) for row in consolidation.get("observation_entities", []) or []}
    grouped: dict[str, list[Mapping[str, Any]]] = collections.defaultdict(list)
    for row in observations.get("records", []) or []:
        candidate_id = text(row.get("previous_candidate_person_id"))
        if candidate_id:
            grouped[candidate_id].append(row)
    rows: list[dict[str, Any]] = []
    for candidate_id, members in sorted(grouped.items()):
        entities = {text(entity_by_obs.get(text(row.get("observation_id")), {}).get("entity_id")) for row in members if text(entity_by_obs.get(text(row.get("observation_id")), {}).get("entity_id"))}
        entity_types = {text(entity_by_obs.get(text(row.get("observation_id")), {}).get("entity_type")) for row in members}
        rows.append(flags({
            "prior_candidate_person_id": candidate_id,
            "observation_count": len(members),
            "observation_ids": sorted(text(row.get("observation_id")) for row in members),
            "surfaces": sorted({text(row.get("surface")) for row in members}),
            "stories": sorted({text(row.get("story_id")) for row in members}),
            "consolidated_entity_ids": sorted(entities),
            "consolidated_entity_types": sorted(entity_types),
            "classification": "absorbed_into_existing" if "production_person" in entity_types else "merged_candidate_observations" if len(entities) == 1 and len(members) > 1 else "repeated_observation" if len(members) > 1 else "singleton_candidate_observation",
            "candidate_only": True,
            "canonical_write_back": False,
        }))
    prior_profile_ids: set[str] = set()
    for doc_key in ("candidate_profiles",):
        for row in (documents.get(doc_key) or {}).get("records", []) or []:
            pid = text(row.get("person_id"))
            if pid:
                prior_profile_ids.add(pid)
    wave_ids: set[str] = set()
    for path in (ROOT / "data/derived/hge1-wave-a-candidate-db.json", ROOT / "data/derived/hge1-wave-b-candidate-db.json"):
        doc = read_json(path, {}) or {}
        for row in doc.get("candidate_persons", []) or []:
            pid = text(row.get("candidate_person_id"))
            if pid:
                wave_ids.add(pid)
    return flags({
        "schema": "sfh2-prior-candidate-dedup-audit-v1",
        "source_candidate_id_count": len(grouped),
        "source_candidate_ids": sorted(grouped),
        "prior_profile_candidate_id_count": len(prior_profile_ids),
        "prior_wave_candidate_id_count": len(wave_ids),
        "repeated_candidate_ids": sum(len(row.get("observation_ids", [])) > 1 for row in rows),
        "absorbed_into_existing_count": sum(row.get("classification") == "absorbed_into_existing" for row in rows),
        "merged_candidate_observation_groups": sum(row.get("classification") == "merged_candidate_observations" for row in rows),
        "records": rows,
        "candidate_only": True,
        "canonical_write_back": False,
    })


def failure_attribution(observations: Mapping[str, Any], link_results: Mapping[str, Any], consolidation: Mapping[str, Any], blocking: Mapping[str, Any], pair_judgments: Mapping[str, Any]) -> dict[str, Any]:
    obs_by_id = {text(row.get("observation_id")): dict(row) for row in observations.get("records", []) or [] if text(row.get("observation_id"))}
    links = {text(row.get("observation_id")): dict(row) for row in link_results.get("records", []) or []}
    failures: list[dict[str, Any]] = []
    for row in consolidation.get("observation_entities", []) or []:
        etype = text(row.get("entity_type")); oid = text(row.get("observation_id")); obs = obs_by_id.get(oid, {}); link = links.get(oid, {})
        if etype in {"production_person", "candidate_person_entity"}:
            if etype == "candidate_person_entity" and text(row.get("decision")) == "candidate_cluster":
                reason = "candidate_cluster_ambiguous" if any(text(item.get("identity_confidence_state")) == "unresolved_candidate_entity" for item in consolidation.get("candidate_clusters", []) or [] if oid in (item.get("member_observation_ids") or [])) else "insufficient_historical_evidence"
            else:
                continue
        elif etype == "structural_reference":
            reason = "semantic_reference_ambiguous"
        elif etype == "collective_reference":
            reason = "anonymous_reference"
        elif etype == "unresolved_reference":
            if text(link.get("status")) in {"provider_failure", "offline_cache_miss", "invalid_payload"}:
                reason = "provider_failure"
            elif text(link.get("status")) == "ambiguous_existing":
                reason = "candidate_cluster_ambiguous"
            elif text(link.get("status")) == "no_existing_match":
                reason = "existing_person_candidate_missing"
            elif text((obs.get("previous_identity_decision") or {}).get("failure_stage")) == "hard_constraint_veto":
                reason = "hard_constraint_veto"
            else:
                reason = "insufficient_historical_evidence"
        else:
            continue
        failures.append(flags({"observation_id": oid, "mention_id": row.get("mention_id"), "story_id": obs.get("story_id"), "surface": obs.get("surface"), "entity_id": row.get("entity_id"), "failure_stage": reason, "source_evidence_ids": obs.get("source_evidence_ids", []), "candidate_only": True, "canonical_write_back": False}))
    counts = collections.Counter(text(row.get("failure_stage")) for row in failures)
    return flags({"schema": "sfh2-failure-attribution-v1", "records": sorted(failures, key=lambda row: text(row.get("observation_id"))), "counts": dict(sorted(counts.items())), "candidate_only": True, "canonical_write_back": False})


def human_audit_sample(observations: Mapping[str, Any], link_results: Mapping[str, Any], pair_judgments: Mapping[str, Any], consolidation: Mapping[str, Any], *, seed: str = "sfh2-hir1-human-audit-v1") -> dict[str, Any]:
    obs_by_id = {text(row.get("observation_id")): dict(row) for row in observations.get("records", []) or []}
    entity_by_obs = {text(row.get("observation_id")): dict(row) for row in consolidation.get("observation_entities", []) or []}
    # The existing-Person group is a blind audit sample, not a list of
    # accepted links.  Include unresolved/provider-failed proposals whenever
    # Python retrieval supplied at least one existing-Person candidate so the
    # human can audit both positive and negative link decisions.
    links = [dict(row) for row in link_results.get("records", []) or [] if row.get("candidate_person_ids")]
    pairs = [dict(row) for row in pair_judgments.get("records", []) or [] if row.get("verdict")]
    merges = [row for row in pairs if row.get("verdict") in {"same_person", "plausibly_same"}]
    distinct = [row for row in pairs if row.get("verdict") == "distinct_persons"]
    unresolved = [row for row in consolidation.get("observation_entities", []) or [] if text(row.get("entity_type")) in {"candidate_person_entity", "unresolved_reference", "structural_reference", "collective_reference"}]
    def stable_pick(rows: Sequence[Mapping[str, Any]], count: int, key: str) -> list[dict[str, Any]]:
        ordered = sorted(rows, key=lambda row: (stable_hash({"seed": seed, "kind": key, "row": row}), text(row.get("observation_id") or row.get("comparison_id"))))
        return [dict(row) for row in ordered[:count]]
    def context(row: Mapping[str, Any], kind: str) -> dict[str, Any]:
        if kind == "candidate_existing":
            obs = obs_by_id.get(text(row.get("observation_id")), {})
            return {"observation_id": row.get("observation_id"), "surface": obs.get("surface"), "story_id": obs.get("story_id"), "source_evidence": obs.get("source_evidence"), "local_context": obs.get("local_context"), "proposal": row}
        left = obs_by_id.get(text(row.get("left_observation_id")), {}); right = obs_by_id.get(text(row.get("right_observation_id")), {})
        return {"comparison_id": row.get("comparison_id"), "left": {"observation_id": left.get("observation_id"), "surface": left.get("surface"), "story_id": left.get("story_id"), "source_evidence": left.get("source_evidence"), "local_context": left.get("local_context")}, "right": {"observation_id": right.get("observation_id"), "surface": right.get("surface"), "story_id": right.get("story_id"), "source_evidence": right.get("source_evidence"), "local_context": right.get("local_context")}, "judgment": row}
    groups = {
        "candidate_to_existing_links": stable_pick(links, 30, "candidate_existing"),
        "candidate_candidate_merges": stable_pick(merges, 30, "candidate_merge"),
        "distinct_person_decisions": stable_pick(distinct, 20, "distinct"),
        "unresolved_cases": stable_pick(unresolved, 20, "unresolved"),
    }
    rendered = {}
    for kind, rows in groups.items():
        rendered[kind] = [context(row, "candidate_existing" if kind == "candidate_to_existing_links" else "pair") if kind != "unresolved_cases" else {"observation": row, "source": obs_by_id.get(text(row.get("observation_id")), {}), "entity": entity_by_obs.get(text(row.get("observation_id")), {})} for row in rows]
    return flags({"schema": "sfh2-human-audit-sample-v1", "selection_seed": seed, "requested_counts": {"candidate_to_existing_links": 30, "candidate_candidate_merges": 30, "distinct_person_decisions": 20, "unresolved_cases": 20}, "actual_counts": {key: len(value) for key, value in rendered.items()}, "groups": rendered, "candidate_only": True, "canonical_write_back": False})


def fragmentation_analysis(graph_before: Mapping[str, Any], graph_after: Mapping[str, Any], consolidation: Mapping[str, Any], link_results: Mapping[str, Any]) -> dict[str, Any]:
    before = graph_before.get("summary", graph_before) if isinstance(graph_before, Mapping) else {}
    after = graph_after.get("summary", graph_after) if isinstance(graph_after, Mapping) else {}
    return flags({
        "schema": "sfh2-fragmentation-analysis-v1",
        "before": {"graph_nodes": before.get("node_count", 0), "graph_edges": before.get("edge_count", 0), "components": before.get("connected_component_count", 0), "largest_component": before.get("largest_component_size", 0), "isolated_nodes": before.get("isolated_node_count", 0)},
        "after": {"graph_nodes": after.get("node_count", 0), "graph_edges": after.get("edge_count", 0), "components": after.get("connected_component_count", 0), "largest_component": after.get("largest_component_size", 0), "isolated_nodes": after.get("isolated_node_count", 0)},
        "delta": {"graph_nodes": int(after.get("node_count", 0)) - int(before.get("node_count", 0)), "graph_edges": int(after.get("edge_count", 0)) - int(before.get("edge_count", 0)), "components": int(after.get("connected_component_count", 0)) - int(before.get("connected_component_count", 0)), "largest_component": int(after.get("largest_component_size", 0)) - int(before.get("largest_component_size", 0))},
        "candidate_nodes_merged": consolidation.get("candidate_nodes_merged", 0),
        "candidate_nodes_linked_to_existing": sum(bool(text(row.get("selected_person_id"))) for row in link_results.get("records", []) or []),
        "candidate_observations_absorbed_into_existing": sum(text(row.get("status")) in {"linked_existing", "reused_sfh1_existing"} for row in link_results.get("records", []) or []),
        "interpretation": "candidate fragmentation is measured separately from genuinely new peripheral or anonymous structures; two waves are not sufficient to infer saturation",
        "candidate_only": True,
        "canonical_write_back": False,
    })
