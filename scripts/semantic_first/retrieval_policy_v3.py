"""SFH1 retrieval v3: consume LLM referent hints before local fallback."""

from __future__ import annotations

from typing import Any, Mapping

from .retrieval_policy_v2 import install as install_v2


def install(module: Any) -> None:
    install_v2(module)
    safe_form_rows = module._form_rows

    def build_candidate_sets(packet: Mapping[str, Any], ledger: Mapping[str, Any], semantics: Mapping[str, Any]) -> dict[str, Any]:
        people, exact_forms, contextual_forms = safe_form_rows()
        prior = module._prior_candidate_rows()
        semantic_index = {module.text(row.get("mention_id")): dict(row) for row in semantics.get("records", []) or []}
        mention_index = {module.text(row.get("mention_id")): dict(row) for row in ledger.get("valid_mentions", []) or []}
        records: list[dict[str, Any]] = []

        for mention_id, mention in sorted(mention_index.items()):
            if module.text(mention.get("entity_kind")) != "person":
                records.append({"mention_id": mention_id, "candidates": [], "retrieval_status": "non_person_or_collective"})
                continue

            semantic = semantic_index.get(mention_id, {})
            referent_hint = module.text(semantic.get("referent_hint"))
            candidate_rows: list[dict[str, Any]] = []
            seen: set[str] = set()
            matching_forms = [module.normalize_form(module.text(mention.get("surface")))]
            if referent_hint:
                matching_forms.append(module.normalize_form(referent_hint))
            for linked_id in semantic.get("coreference_with", []) or []:
                linked = mention_index.get(module.text(linked_id), {})
                linked_form = module.normalize_form(module.text(linked.get("surface")))
                if linked_form:
                    matching_forms.append(linked_form)

            for form in dict.fromkeys(value for value in matching_forms if value):
                for scope, index in (("exact", exact_forms), ("contextual", contextual_forms)):
                    for found in index.get(form, []):
                        person_id = module.text(found.get("person_id"))
                        if not person_id or person_id in seen:
                            continue
                        seen.add(person_id)
                        evidence_id = f"sfh1-candidate-evidence-{module.stable_hash({'mention_id': mention_id, 'person_id': person_id, 'found': found, 'hint': referent_hint})[:20]}"
                        candidate_rows.append({
                            "candidate_key": f"c{len(candidate_rows)}",
                            "entity_type": "existing_person",
                            "person_id": person_id,
                            "display_name": people[person_id].get("canonical_name"),
                            "matched_surface": found.get("surface"),
                            "retrieval_basis": found.get("basis"),
                            "retrieval_scope": scope,
                            "semantic_referent_hint": referent_hint or None,
                            "requires_semantic_judgment": scope != "exact" or bool(referent_hint),
                            "evidence": [{"evidence_id": evidence_id, "text": found.get("evidence"), "source_ref": found.get("evidence_ref")}],
                        })
                for found in prior.get(form, []):
                    candidate_id = module.text(found.get("candidate_person_id"))
                    if not candidate_id or candidate_id in seen:
                        continue
                    seen.add(candidate_id)
                    candidate_rows.append({
                        "candidate_key": f"c{len(candidate_rows)}",
                        "entity_type": "prior_candidate_person",
                        "candidate_person_id": candidate_id,
                        "display_name": found.get("surface"),
                        "matched_surface": found.get("surface"),
                        "retrieval_basis": found.get("basis"),
                        "retrieval_scope": "contextual",
                        "semantic_referent_hint": referent_hint or None,
                        "requires_semantic_judgment": True,
                        "evidence": [{"evidence_id": module.text(found.get("evidence_ref")) or candidate_id, "text": found.get("surface"), "source_ref": found.get("evidence_ref")}],
                    })

            if (
                not candidate_rows
                and module.text(semantic.get("semantic_type")) not in module.STRUCTURAL_SEMANTICS
                and module.text(semantic.get("semantic_type")) in {"direct_person_form", "abbreviated_person_reference", "local_anaphoric_reference"}
                and module.text(mention.get("confidence")) in {"high", "medium"}
            ):
                # Semantic hint wins over the abbreviated surface for candidate
                # naming.  Python owns only the generated local ID.
                display_name = referent_hint or module.text(mention.get("surface"))
                candidate_id = f"sfh1-local-person-{module.stable_hash({'mention_id': mention_id, 'display_name': display_name, 'evidence': mention.get('source_evidence_id')})[:22]}"
                candidate_rows.append({
                    "candidate_key": "c0",
                    "entity_type": "local_candidate_person",
                    "candidate_person_id": candidate_id,
                    "display_name": display_name,
                    "matched_surface": mention.get("surface"),
                    "retrieval_basis": "llm_referent_hint_local_candidate" if referent_hint else "source-grounded_local_person_form",
                    "retrieval_scope": "local_candidate",
                    "semantic_referent_hint": referent_hint or None,
                    "requires_semantic_judgment": True,
                    "evidence": [{"evidence_id": mention.get("source_evidence_id"), "text": mention.get("surface"), "source_ref": mention.get("source_evidence_id")}],
                })

            records.append({
                "mention_id": mention_id,
                "story_id": packet.get("story_id"),
                "surface": mention.get("surface"),
                "semantic_type": semantic.get("semantic_type", "uncertain"),
                "referent_hint": referent_hint,
                "network_role": semantic.get("network_role", "uncertain"),
                "candidates": candidate_rows,
                "retrieval_status": "candidates_found" if candidate_rows else "candidate_missing",
                "candidate_only": True,
                "canonical_write_back": False,
            })

        return {
            "story_id": packet.get("story_id"),
            "records": records,
            "retrieval_policy": "semantic_precedence_v3_referent_hint",
            "candidate_only": True,
            "canonical_write_back": False,
        }

    module.build_candidate_sets = build_candidate_sets
