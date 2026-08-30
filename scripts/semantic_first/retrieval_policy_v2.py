"""Install safe contextual candidate retrieval for SFH1 semantic-first parsing.

This module replaces candidate generation only.  It never resolves identity;
LLM semantic judgment remains authoritative and Python only supplies IDs and
provenance-bearing hints.
"""

from __future__ import annotations

import collections
from typing import Any, Mapping

from identity_resolution_policy import (
    alias_retrieval_scope,
    explicitly_blocked_form_person_pairs,
    filtered_alias_evidence,
    profile_form_retrieval_scope,
)
from manual_semantic_authority import replacement_exact_forms


def install(module: Any) -> None:
    def safe_form_rows() -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
        people = module._person_registry()
        suppressed = module._overlay_suppressed() | {
            (module.normalize_form(surface), person_id)
            for surface, person_id in explicitly_blocked_form_person_pairs()
        }
        exact: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
        contextual: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)

        def add(target: dict[str, list[dict[str, Any]]], surface: Any, person_id: str, basis: str, evidence: Any, evidence_ref: Any, form_type: str) -> None:
            surface_text = module.text(surface)
            key = module.normalize_form(surface_text)
            if not key or person_id not in people or (key, person_id) in suppressed:
                return
            row = {
                "person_id": person_id,
                "surface": surface_text,
                "basis": basis,
                "evidence": module.text(evidence) or surface_text,
                "evidence_ref": module.text(evidence_ref),
                "form_type": form_type,
            }
            signature = (person_id, surface_text, basis, module.text(evidence_ref))
            if not any((item.get("person_id"), item.get("surface"), item.get("basis"), item.get("evidence_ref")) == signature for item in target[key]):
                target[key].append(row)

        for person_id, person in people.items():
            canonical = module.text(person.get("canonical_name"))
            if canonical:
                add(exact, canonical, person_id, "canonical_name", canonical, "data/people.json", "canonical_name")

        aliases = module.read_json(module.ROOT / "data/aliases.json", {}) or {}
        for alias in aliases.get("aliases", []) or []:
            if not isinstance(alias, Mapping):
                continue
            resolved = [module.text(value) for value in alias.get("resolved_person_ids", []) or [] if module.text(value) in people]
            if len(set(resolved)) != 1 or not module.text(alias.get("surface")):
                continue
            scope = alias_retrieval_scope(alias)
            if scope == "blocked":
                continue
            target = exact if scope == "exact" else contextual
            sources = filtered_alias_evidence(alias)
            if not sources:
                sources = [{}]
            for source in sources:
                add(
                    target,
                    alias.get("surface"),
                    resolved[0],
                    f"alias_registry_{scope}:{module.text(alias.get('alias_type')) or 'alias'}",
                    source.get("evidence_snippet") or alias.get("surface"),
                    source.get("source_id") or "data/aliases.json",
                    module.text(alias.get("alias_type")) or "alias",
                )

        for replacement in replacement_exact_forms():
            person_id = module.text(replacement.get("person_id"))
            surface = module.text(replacement.get("surface"))
            if person_id in people and surface:
                add(exact, surface, person_id, "manual_semantic_authority", surface, replacement.get("evidence_ref"), "manual_reviewed_form")

        # Occurrence/profile forms are dossier evidence by default.  Their
        # existence must not create a new global alias.
        for person_id, profile in module._profile_index().items():
            identity = profile.get("identity") if isinstance(profile.get("identity"), Mapping) else {}
            for form in identity.get("form_provenance", []) or []:
                if not isinstance(form, Mapping):
                    continue
                if module.text(form.get("person_id")) != person_id or module.text(form.get("identity_status")) not in module.STRONG_PROFILE_STATES:
                    continue
                surface = module.text(form.get("surface"))
                if not surface or (module.normalize_form(surface), person_id) in suppressed:
                    continue
                scope = profile_form_retrieval_scope(form)
                target = exact if scope == "exact" else contextual
                add(target, surface, person_id, f"profile_{scope}:{module.text(form.get('identity_basis'))}", surface, form.get("evidence_ref"), module.text(form.get("form_type")) or "observed_surface")

        return people, dict(exact), dict(contextual)

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
            candidate_rows: list[dict[str, Any]] = []
            seen: set[str] = set()
            matching_forms = [module.normalize_form(module.text(mention.get("surface")))]
            for linked_id in semantic.get("coreference_with", []) or []:
                linked = mention_index.get(module.text(linked_id), {})
                linked_form = module.normalize_form(module.text(linked.get("surface")))
                if linked_form:
                    matching_forms.append(linked_form)

            # Only validated mention/coreference surfaces are allowed as keys.
            # No arbitrary local-context substring scan occurs here.
            for form in dict.fromkeys(value for value in matching_forms if value):
                for scope, index in (("exact", exact_forms), ("contextual", contextual_forms)):
                    for found in index.get(form, []):
                        person_id = module.text(found.get("person_id"))
                        if not person_id or person_id in seen:
                            continue
                        seen.add(person_id)
                        evidence_id = f"sfh1-candidate-evidence-{module.stable_hash({'mention_id': mention_id, 'person_id': person_id, 'found': found})[:20]}"
                        candidate_rows.append({
                            "candidate_key": f"c{len(candidate_rows)}",
                            "entity_type": "existing_person",
                            "person_id": person_id,
                            "display_name": people[person_id].get("canonical_name"),
                            "matched_surface": found.get("surface"),
                            "retrieval_basis": found.get("basis"),
                            "retrieval_scope": scope,
                            "requires_semantic_judgment": scope != "exact",
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
                        "requires_semantic_judgment": True,
                        "evidence": [{"evidence_id": module.text(found.get("evidence_ref")) or candidate_id, "text": found.get("surface"), "source_ref": found.get("evidence_ref")}],
                    })

            if (
                not candidate_rows
                and module.text(semantic.get("semantic_type")) not in module.STRUCTURAL_SEMANTICS
                and module.text(semantic.get("semantic_type")) in {"direct_person_form", "abbreviated_person_reference", "local_anaphoric_reference"}
                and module.text(mention.get("reference_form")) in {"full_name", "personal_name", "courtesy_name", "style_name", "nickname"}
                and module.text(mention.get("confidence")) in {"high", "medium"}
            ):
                candidate_id = f"sfh1-local-person-{module.stable_hash({'mention_id': mention_id, 'surface': mention.get('surface'), 'evidence': mention.get('source_evidence_id')})[:22]}"
                candidate_rows.append({
                    "candidate_key": "c0",
                    "entity_type": "local_candidate_person",
                    "candidate_person_id": candidate_id,
                    "display_name": mention.get("surface"),
                    "matched_surface": mention.get("surface"),
                    "retrieval_basis": "source-grounded_local_person_form",
                    "retrieval_scope": "local_candidate",
                    "requires_semantic_judgment": True,
                    "evidence": [{"evidence_id": mention.get("source_evidence_id"), "text": mention.get("surface"), "source_ref": mention.get("source_evidence_id")}],
                })

            records.append({
                "mention_id": mention_id,
                "story_id": packet.get("story_id"),
                "surface": mention.get("surface"),
                "semantic_type": semantic.get("semantic_type", "uncertain"),
                "candidates": candidate_rows,
                "retrieval_status": "candidates_found" if candidate_rows else "candidate_missing",
                "candidate_only": True,
                "canonical_write_back": False,
            })

        return {
            "story_id": packet.get("story_id"),
            "records": records,
            "retrieval_policy": "semantic_precedence_v2",
            "candidate_only": True,
            "canonical_write_back": False,
        }

    module._form_rows = safe_form_rows
    module.build_candidate_sets = build_candidate_sets
