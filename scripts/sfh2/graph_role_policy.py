"""Apply semantic occurrence roles to SFH2 relation and graph projections."""

from __future__ import annotations

import collections
import copy
from typing import Any, Mapping


def install(module: Any) -> None:
    original_relations = module.relation_endpoint_reprojection
    original_graph = module.build_consolidated_graph

    def _ineligible_mentions(observations: Mapping[str, Any]) -> set[str]:
        return {
            module.text(row.get("mention_id"))
            for row in observations.get("records", []) or []
            if isinstance(row, Mapping)
            and row.get("core_story_graph_eligible") is False
            and module.text(row.get("mention_id"))
        }

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
            and row.get("core_story_graph_eligible") is False
            and module.text(row.get("observation_id"))
        }
        if not blocked_obs:
            return original_graph(observations, consolidation, relations, documents, story_ids)
        filtered = copy.deepcopy(dict(consolidation))
        filtered["observation_entities"] = [
            row for row in filtered.get("observation_entities", []) or []
            if module.text(row.get("observation_id")) not in blocked_obs
        ]
        result = original_graph(observations, filtered, relations, documents, story_ids)
        result["semantic_role_excluded_observation_ids"] = sorted(blocked_obs)
        result["semantic_role_policy"] = "citation_author/historical_exemplum/person_attribute occurrences do not create core Story graph nodes or edges"
        return result

    module.relation_endpoint_reprojection = relation_endpoint_reprojection
    module.build_consolidated_graph = build_consolidated_graph
