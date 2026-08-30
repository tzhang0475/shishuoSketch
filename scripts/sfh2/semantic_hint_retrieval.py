"""Augment safe SFH2 retrieval with validated LLM referent hints.

A referent hint may add an existing Person to the candidate set.  It never
selects that Person: the normal LLM identity assessment and hard constraints
still decide whether the candidate is supported.
"""

from __future__ import annotations

from typing import Any, Mapping


def install(module: Any) -> None:
    base_builder = module.build_existing_link_candidates

    def build_existing_link_candidates(observations_doc: Mapping[str, Any], documents: Mapping[str, Any]) -> dict[str, Any]:
        result = base_builder(observations_doc, documents)
        form_index = module.build_existing_form_index(documents)
        people = module._people(documents)
        obs_by_id = {
            module.text(row.get("observation_id")): row
            for row in observations_doc.get("records", []) or []
            if isinstance(row, Mapping)
        }

        for record in result.get("records", []) or []:
            if not isinstance(record, dict):
                continue
            obs = obs_by_id.get(module.text(record.get("observation_id")), {})
            hint = module.normalize_form((obs.get("reference_semantics") or {}).get("referent_hint"))
            if not hint:
                continue
            existing = {module.text(row.get("person_id")) for row in record.get("candidates", []) or []}
            hinted_rows: list[tuple[str, Mapping[str, Any]]] = []
            for scope, index in (("exact", form_index.get("exact_forms") or {}), ("contextual", form_index.get("contextual_forms") or {})):
                for found in index.get(hint, []) or []:
                    hinted_rows.append((scope, found))
            for scope, found in hinted_rows:
                pid = module.text(found.get("person_id"))
                if not pid or pid in existing or pid not in people:
                    continue
                existing.add(pid)
                record.setdefault("candidates", []).append({
                    "candidate_key": f"c{len(record.get('candidates', []))}",
                    "person_id": pid,
                    "display_name": people[pid].get("canonical_name") or pid,
                    "matched_forms": [found.get("surface")],
                    "retrieval_basis": [f"llm_referent_hint_{scope}"],
                    "retrieval_scope": "semantic_hint",
                    "requires_semantic_judgment": True,
                    "evidence": [{
                        "evidence_id": module.text(found.get("evidence_ref")) or f"sfh2-hint-{module.stable_hash({'obs': record.get('observation_id'), 'pid': pid, 'hint': hint})[:20]}",
                        "text": found.get("evidence_text") or found.get("surface"),
                        "source_ref": found.get("evidence_ref"),
                        "basis": "llm_referent_hint",
                    }],
                    "dossier": module._profile_dossier(documents, pid, form_index),
                    "semantic_referent_hint": (obs.get("reference_semantics") or {}).get("referent_hint"),
                })
            record["candidate_count"] = len(record.get("candidates", []) or [])
            record["retrieval_status"] = "candidates_found" if record["candidate_count"] else "candidate_missing"
        result["retrieval_policy"] = {
            **(result.get("retrieval_policy") or {}),
            "llm_referent_hint_consumed": True,
        }
        return result

    module.build_existing_link_candidates = build_existing_link_candidates
