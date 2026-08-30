"""Safe SFH2 candidate retrieval installed over the legacy consolidation module.

The legacy SFH2 implementation remains available for provenance/replay, but
its local-context substring scan is not safe for identity candidate creation.
This module replaces only the retrieval functions; later LLM/constraint/
clustering stages keep their existing contracts.
"""

from __future__ import annotations

from typing import Any, Mapping

from identity_resolution_policy import (
    alias_retrieval_scope,
    explicitly_blocked_form_person_pairs,
    filtered_alias_evidence,
    normalize_form,
    profile_form_retrieval_scope,
)


def install(module: Any) -> None:
    """Install the reviewed retrieval policy into sfh2.consolidation."""

    def build_existing_form_index(documents: Mapping[str, Any]) -> dict[str, Any]:
        people = module._people(documents)
        suppressed = module._suppressed(documents) | explicitly_blocked_form_person_pairs()
        exact: dict[str, list[dict[str, Any]]] = {}
        contextual: dict[str, list[dict[str, Any]]] = {}
        by_person: dict[str, dict[str, set[str]]] = {}

        def add(target: dict[str, list[dict[str, Any]]], *, surface: Any, person_id: str, form_type: str, basis: str, evidence_ref: Any = None, evidence_text: Any = None) -> None:
            surface_text = module.text(surface)
            key = normalize_form(surface_text)
            if not key or person_id not in people or (key, person_id) in suppressed:
                return
            item = {
                "surface": surface_text,
                "form_type": form_type,
                "person_id": person_id,
                "basis": basis,
                "evidence_ref": module.text(evidence_ref),
                "evidence_text": module.text(evidence_text) or surface_text,
            }
            bucket = target.setdefault(key, [])
            signature = (person_id, surface_text, basis, module.text(evidence_ref))
            if not any((row.get("person_id"), row.get("surface"), row.get("basis"), row.get("evidence_ref")) == signature for row in bucket):
                bucket.append(item)
            by_person.setdefault(person_id, {}).setdefault(form_type, set()).add(surface_text)

        for pid, person in people.items():
            add(exact, surface=person.get("canonical_name"), person_id=pid, form_type="canonical_name", basis="canonical_registry")

        for alias in (documents.get("aliases") or {}).get("aliases", []) or []:
            if not isinstance(alias, Mapping):
                continue
            ids = {
                module.text(value)
                for value in (alias.get("resolved_person_ids") or alias.get("person_ids") or [])
                if module.text(value) in people
            }
            if not ids:
                continue
            scope = alias_retrieval_scope(alias)
            if scope == "blocked":
                continue
            target = exact if scope == "exact" else contextual
            sources = filtered_alias_evidence(alias) or [{}]
            for pid in sorted(ids):
                for source in sources:
                    source = source if isinstance(source, Mapping) else {}
                    add(
                        target,
                        surface=alias.get("surface"),
                        person_id=pid,
                        form_type=module.text(alias.get("alias_type")) or "alias",
                        basis=f"alias_registry_{scope}",
                        evidence_ref=source.get("source_id") or source.get("mention_id"),
                        evidence_text=source.get("evidence_snippet"),
                    )

        # Profile provenance remains available for dossiers, but short
        # occurrence-derived forms are contextual rather than global keys.
        for profile in (documents.get("profiles") or {}).get("records", []) or []:
            if not isinstance(profile, Mapping):
                continue
            pid = module.text(profile.get("person_id"))
            if pid not in people:
                continue
            for form in profile.get("identity", {}).get("form_provenance", []) or []:
                if not isinstance(form, Mapping):
                    continue
                if module.text(form.get("identity_status")) not in {"direct_existing", "explicit_resolved", "contextually_resolved"}:
                    continue
                scope = profile_form_retrieval_scope(form)
                target = exact if scope == "exact" else contextual
                add(
                    target,
                    surface=form.get("surface"),
                    person_id=pid,
                    form_type=module.text(form.get("form_type")) or "observed_surface",
                    basis=f"profile_provenance_{scope}",
                    evidence_ref=form.get("evidence_ref"),
                    evidence_text=form.get("surface"),
                )

        for index in (exact, contextual):
            for key in index:
                index[key].sort(key=lambda row: (row["person_id"], -len(row["surface"]), row["surface"], row["basis"], row["evidence_ref"]))
        serial_by_person = {pid: {kind: sorted(values) for kind, values in kinds.items()} for pid, kinds in by_person.items()}
        return module.flags({
            "schema": "sfh2-existing-form-index-v2",
            "forms": {key: value for key, value in sorted(exact.items())},
            "exact_forms": {key: value for key, value in sorted(exact.items())},
            "contextual_forms": {key: value for key, value in sorted(contextual.items())},
            "forms_by_person": serial_by_person,
            "suppressed_forms": [{"surface": surface, "person_id": pid} for surface, pid in sorted(suppressed)],
            "policy": {
                "surface_exact_can_resolve": "canonical/full-name classes only",
                "contextual_forms_require_semantic_judgment": True,
                "substring_context_scan": False,
                "occurrence_resolution_implies_global_alias": False,
                "manual_evidence_filtering": True,
            },
            "candidate_only": True,
            "canonical_write_back": False,
        })

    def candidate_matches(obs: Mapping[str, Any], form_index: Mapping[str, Any], documents: Mapping[str, Any]) -> list[dict[str, Any]]:
        people = module._people(documents)
        suppressed = module._suppressed(documents) | explicitly_blocked_form_person_pairs()
        surface = normalize_form(obs.get("surface"))
        matches: dict[str, dict[str, Any]] = {}

        def consume(rows: list[dict[str, Any]], scope: str) -> None:
            for row in rows:
                pid = module.text(row.get("person_id"))
                if pid not in people or (surface, pid) in suppressed:
                    continue
                target = matches.setdefault(pid, {
                    "person_id": pid,
                    "matched_forms": [],
                    "retrieval_bases": set(),
                    "evidence": [],
                    "retrieval_scopes": set(),
                })
                target["matched_forms"].append(row.get("surface"))
                target["retrieval_bases"].add(row.get("basis"))
                target["retrieval_scopes"].add(scope)
                eid = module.text(row.get("evidence_ref")) or f"sfh2-form-evidence-{module.stable_hash(row)[:20]}"
                target["evidence"].append({
                    "evidence_id": eid,
                    "text": row.get("evidence_text") or row.get("surface"),
                    "source_ref": row.get("evidence_ref"),
                    "basis": row.get("basis"),
                })

        # IMPORTANT: only the occurrence's own validated surface is used.
        # There is deliberately no arbitrary local-context substring scan.
        consume(list((form_index.get("exact_forms") or {}).get(surface, []) or []), "exact")
        consume(list((form_index.get("contextual_forms") or {}).get(surface, []) or []), "contextual")

        result: list[dict[str, Any]] = []
        for pid, row in sorted(matches.items()):
            scopes = sorted(row["retrieval_scopes"])
            result.append({
                "candidate_key": f"c{len(result)}",
                "person_id": pid,
                "display_name": people[pid].get("canonical_name") or pid,
                "matched_forms": sorted(set(row["matched_forms"])),
                "retrieval_basis": sorted(row["retrieval_bases"]),
                "retrieval_scope": "exact" if "exact" in scopes else "contextual",
                "requires_semantic_judgment": "exact" not in scopes,
                "evidence": sorted(
                    {module.text(item.get("evidence_id")): item for item in row["evidence"] if module.text(item.get("evidence_id"))}.values(),
                    key=lambda item: item["evidence_id"],
                )[:12],
                "dossier": module._profile_dossier(documents, pid, form_index),
            })
        return result

    def build_existing_link_candidates(observations_doc: Mapping[str, Any], documents: Mapping[str, Any]) -> dict[str, Any]:
        form_index = build_existing_form_index(documents)
        records: list[dict[str, Any]] = []
        for obs in observations_doc.get("records", []) or []:
            if not isinstance(obs, Mapping):
                continue
            if module.text(obs.get("classification")) not in {"candidate_observation", "unresolved_person_observation"}:
                continue
            candidates = candidate_matches(obs, form_index, documents)
            records.append(module.flags({
                "observation_id": obs.get("observation_id"),
                "mention_id": obs.get("mention_id"),
                "story_id": obs.get("story_id"),
                "surface": obs.get("surface"),
                "semantic_reference_type": obs.get("semantic_reference_type"),
                "candidates": candidates,
                "candidate_count": len(candidates),
                "retrieval_status": "candidates_found" if candidates else "candidate_missing",
                "candidate_only": True,
                "canonical_write_back": False,
            }))
        return module.flags({
            "schema": "sfh2-existing-person-link-candidates-v2",
            "records": sorted(records, key=lambda row: module.text(row.get("observation_id"))),
            "form_index_hash": module.stable_hash(form_index),
            "retrieval_policy": form_index.get("policy"),
            "candidate_only": True,
            "canonical_write_back": False,
        })

    module.build_existing_form_index = build_existing_form_index
    module._candidate_matches = candidate_matches
    module.build_existing_link_candidates = build_existing_link_candidates
