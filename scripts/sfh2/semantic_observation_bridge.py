"""Bridge SFH1 v2 semantic hints into SFH2 observations."""

from __future__ import annotations

from typing import Any, Mapping

from .graph_role_policy import CORE_GRAPH_INELIGIBLE_ROLES


def install(module: Any) -> None:
    original = module.build_candidate_observations

    def build_candidate_observations(documents: Mapping[str, Any] | None = None) -> dict[str, Any]:
        docs = documents or module.load_documents()
        result = original(docs)
        semantics = {
            module.text(row.get("mention_id")): dict(row)
            for row in module.as_records(docs.get("semantics"), "records")
            if module.text(row.get("mention_id"))
        }
        for row in result.get("records", []) or []:
            if not isinstance(row, dict):
                continue
            semantic = semantics.get(module.text(row.get("mention_id")), {})
            ref = row.setdefault("reference_semantics", {})
            hint = module.text(semantic.get("referent_hint"))
            explicit_role = module.text(semantic.get("network_role"))
            role = explicit_role or "uncertain"
            ref["referent_hint"] = hint
            ref["network_role"] = role
            row["semantic_referent_hint"] = hint
            row["network_role"] = role
            if explicit_role in CORE_GRAPH_INELIGIBLE_ROLES:
                row["core_story_graph_eligible"] = False
            else:
                # No semantic role is invented for legacy SFH1 observations.
                # Preserve an existing explicit eligibility value; otherwise
                # retain the historical default for backwards compatibility.
                row.setdefault("core_story_graph_eligible", True)
        result["semantic_bridge"] = "sfh1_reference_semantics_v2"
        return result

    module.build_candidate_observations = build_candidate_observations
