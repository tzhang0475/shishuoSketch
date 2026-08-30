"""Bridge SFH1 v2 semantic hints into SFH2 observations."""

from __future__ import annotations

from typing import Any, Mapping


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
            role = module.text(semantic.get("network_role")) or "uncertain"
            ref["referent_hint"] = hint
            ref["network_role"] = role
            row["semantic_referent_hint"] = hint
            row["network_role"] = role
            if role in {"citation_author", "historical_exemplum", "person_attribute"}:
                row["core_story_graph_eligible"] = False
            else:
                row.setdefault("core_story_graph_eligible", True)
        result["semantic_bridge"] = "sfh1_reference_semantics_v2"
        return result

    module.build_candidate_observations = build_candidate_observations
