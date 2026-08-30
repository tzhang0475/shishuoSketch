"""Apply semantic occurrence roles to SFH2 relation and graph projections."""

from __future__ import annotations

import collections
import copy
from typing import Any, Mapping


# These are explicit semantic roles emitted by SFH1/manual authority.  The
# set is policy, not a classifier: this module never derives a role from text.
# A historical person can retain source/context identity while this particular
# occurrence is excluded from the core Story social graph.
CORE_GRAPH_INELIGIBLE_ROLES = frozenset({
    "citation_author",
    "historical_exemplum",
    "person_attribute",
    "collective_reference",
    "structural_reference",
    "genealogy_ancestor",
})


def install(module: Any) -> None:
    original_relations = module.relation_endpoint_reprojection
    original_graph = module.build_consolidated_graph

    def _ineligible_mentions(observations: Mapping[str, Any]) -> set[str]:
        return {
            module.text(row.get("mention_id"))
            for row in observations.get("records", []) or []
            if isinstance(row, Mapping)
            and _is_ineligible(row)
            and module.text(row.get("mention_id"))
        }

    def _is_ineligible(row: Mapping[str, Any]) -> bool:
        role = module.text(row.get("network_role"))
        return row.get("core_story_graph_eligible") is False or role in CORE_GRAPH_INELIGIBLE_ROLES

    def relation_endpoint_reprojection(observations: Mapping[str, Any], consolidation: Mapping[str, Any], documents: Mapping[str, Any]) -> dict[str, Any]:
        result = original_relations(observations, consolidation, documents)
        blocked = _ineligible_mentions(observations)
        if not blocked:
            result["semantic_role_blocked_mentions"] = []
            return result
        for row in result.get("records", []) or []:
            if not isinstance(row, dict):
                continue
            subject_blocked = module.text(row.get("subject_mention_id")) in blocked
            object_blocked = module.text(row.get("object_mention_id")) in blocked
            if subject_blocked:
                row["subject_endpoint"] = None
                row["subject_endpoint_type"] = "semantic_role_excluded"
            if object_blocked:
                row["object_endpoint"] = None
                row["object_endpoint_type"] = "semantic_role_excluded"
            if subject_blocked or object_blocked:
                row["endpoint_state"] = "semantic_reference_blocked"
                row["semantic_role_exclusion"] = {
                    "subject": subject_blocked,
                    "object": object_blocked,
                }
        result["endpoint_state_counts"] = dict(sorted(collections.Counter(
            module.text(row.get("endpoint_state")) for row in result.get("records", []) or []
        ).items()))
        result["semantic_role_blocked_mentions"] = sorted(blocked)
        return result

    def build_consolidated_graph(observations: Mapping[str, Any], consolidation: Mapping[str, Any], relations: Mapping[str, Any], documents: Mapping[str, Any], story_ids: set[str] | None = None) -> dict[str, Any]:
        blocked_obs = {
            module.text(row.get("observation_id"))
            for row in observations.get("records", []) or []
            if isinstance(row, Mapping)
            and _is_ineligible(row)
            and module.text(row.get("observation_id"))
        }
        if not blocked_obs:
            return original_graph(observations, consolidation, relations, documents, story_ids)
        filtered = copy.deepcopy(dict(consolidation))
        filtered["observation_entities"] = [
            row for row in filtered.get("observation_entities", []) or []
            if module.text(row.get("observation_id")) not in blocked_obs
        ]
        # The original graph builder can add relation edges from endpoint IDs
        # even after an entity row is filtered.  Filter the occurrence-level
        # relation witnesses too, so a source-only mention cannot re-enter via
        # the independent relation projection path.
        filtered_relations = copy.deepcopy(dict(relations))
        filtered_relations["records"] = [
            row for row in filtered_relations.get("records", []) or []
            if module.text(row.get("subject_mention_id")) not in {
                module.text(item.get("mention_id"))
                for item in observations.get("records", []) or []
                if isinstance(item, Mapping) and _is_ineligible(item)
            }
            and module.text(row.get("object_mention_id")) not in {
                module.text(item.get("mention_id"))
                for item in observations.get("records", []) or []
                if isinstance(item, Mapping) and _is_ineligible(item)
            }
            and not isinstance(row.get("semantic_role_exclusion"), Mapping)
        ]
        result = original_graph(observations, filtered, filtered_relations, documents, story_ids)
        result["semantic_role_excluded_observation_ids"] = sorted(blocked_obs)
        result["semantic_role_policy"] = "/".join(sorted(CORE_GRAPH_INELIGIBLE_ROLES)) + " occurrences do not create core Story graph nodes or edges"
        return result

    module.relation_endpoint_reprojection = relation_endpoint_reprojection
    module.build_consolidated_graph = build_consolidated_graph
