"""L4 deterministic, provenance-bearing identity candidate retrieval."""

from __future__ import annotations

import collections
import re
from typing import Any, Mapping, Sequence

from manual_semantic_authority import blocked_global_forms, replacement_exact_forms
from .common import ROOT, read_json, stable_hash, text

VARIANTS = str.maketrans({"爲": "為", "髙": "高", "鳯": "鳳", "臺": "台", "台": "台"})
STRONG_PROFILE_STATES = {"direct_existing", "explicit_resolved", "contextually_resolved"}
STRUCTURAL_SEMANTICS = {"compositional_kinship", "patron_plus_office", "descriptive_person_reference"}


def normalize_form(value: str) -> str:
    return re.sub(r"\s+", "", text(value)).translate(VARIANTS)


def _overlay_suppressed() -> set[tuple[str, str]]:
    document = read_json(ROOT / "data/generated/hda2/repair-overlay.json", []) or []
    rows = document if isinstance(document, list) else document.get("records", []) or []
    return {
        (normalize_form(text(row.get("target_surface"))), text(row.get("person_id")))
        for row in rows
        if isinstance(row, Mapping) and text(row.get("action")) == "suppress_claim"
    }


def _person_registry() -> dict[str, dict[str, Any]]:
    document = read_json(ROOT / "data/people.json", {}) or {}
    return {
        text(row.get("person_id")): dict(row)
        for row in document.get("people", []) or []
        if isinstance(row, Mapping) and text(row.get("person_id"))
    }


def _profile_index() -> dict[str, dict[str, Any]]:
    document = read_json(ROOT / "data/derived/hdb2-f-person-knowledge.json", {}) or {}
    return {
        text(row.get("person_id")): dict(row)
        for row in document.get("records", []) or []
        if isinstance(row, Mapping) and text(row.get("person_id"))
    }


def _form_rows() -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    people = _person_registry()
    # HDA2 suppressions and the manually reviewed SFH2R alias decisions have
    # identical precedence here: neither may be restored by alias/profile
    # convenience data.  This is deterministic application, not inference.
    suppressed = _overlay_suppressed() | {
        (normalize_form(surface), person_id)
        for surface, person_id in blocked_global_forms()
    }
    by_form: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for person_id, person in people.items():
        canonical = text(person.get("canonical_name"))
        if canonical:
            by_form[normalize_form(canonical)].append({
                "person_id": person_id, "surface": canonical,
                "basis": "canonical_name", "evidence": canonical,
                "evidence_ref": "data/people.json",
            })
    aliases = read_json(ROOT / "data/aliases.json", {}) or {}
    for alias in aliases.get("aliases", []) or []:
        if not isinstance(alias, Mapping):
            continue
        surface = text(alias.get("surface"))
        resolved = [text(value) for value in alias.get("resolved_person_ids", []) or [] if text(value) in people]
        if not surface or len(set(resolved)) != 1:
            continue
        person_id = resolved[0]
        if (normalize_form(surface), person_id) in suppressed:
            continue
        snippets = [text(row.get("evidence_snippet")) for row in alias.get("source_evidence", []) or [] if isinstance(row, Mapping) and text(row.get("evidence_snippet"))]
        by_form[normalize_form(surface)].append({
            "person_id": person_id, "surface": surface,
            "basis": f"alias_registry:{text(alias.get('alias_type')) or 'alias'}",
            "evidence": snippets[0] if snippets else surface,
            "evidence_ref": "data/aliases.json",
        })
    # Add only replacement forms explicitly stated by the manual authority.
    # At present this restores 郭象字子玄 while suppressing the corrupt 子少.
    for replacement in replacement_exact_forms():
        person_id = text(replacement.get("person_id"))
        surface = text(replacement.get("surface"))
        if person_id not in people or not surface:
            continue
        by_form[normalize_form(surface)].append({
            "person_id": person_id,
            "surface": surface,
            "basis": text(replacement.get("basis")) or "manual_semantic_authority",
            "evidence": surface,
            "evidence_ref": text(replacement.get("evidence_ref")),
        })
    profiles = _profile_index()
    for person_id, profile in profiles.items():
        identity = profile.get("identity") if isinstance(profile.get("identity"), Mapping) else {}
        for form in identity.get("form_provenance", []) or []:
            if not isinstance(form, Mapping):
                continue
            surface = text(form.get("surface"))
            if not surface or text(form.get("person_id")) != person_id:
                continue
            if text(form.get("identity_status")) not in STRONG_PROFILE_STATES:
                continue
            if (normalize_form(surface), person_id) in suppressed:
                continue
            by_form[normalize_form(surface)].append({
                "person_id": person_id, "surface": surface,
                "basis": f"profile:{text(form.get('identity_basis'))}",
                "evidence": surface,
                "evidence_ref": text(form.get("evidence_ref")) or "data/derived/hdb2-f-person-knowledge.json",
            })
    return people, by_form


def _prior_candidate_rows() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for path in (
        ROOT / "data/derived/hge1-wave-a-candidate-db.json",
        ROOT / "data/derived/hge1-wave-b-candidate-db.json",
        ROOT / "data/derived/hdb2-f-candidate-person-knowledge.json",
    ):
        document = read_json(path, {}) or {}
        rows = document.get("candidate_persons") or document.get("records") or []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            candidate_id = text(row.get("candidate_person_id")) or text(row.get("person_id"))
            surfaces = [text(row.get("canonical_name")), *[text(value) for value in row.get("observed_surfaces", []) or []]]
            for surface in surfaces:
                if surface and candidate_id:
                    result[normalize_form(surface)].append({
                        "candidate_person_id": candidate_id,
                        "surface": surface,
                        "basis": f"prior_candidate:{path.name}",
                        "evidence_ref": str(path.relative_to(ROOT)),
                    })
    return result


def build_candidate_sets(
    packet: Mapping[str, Any],
    ledger: Mapping[str, Any],
    semantics: Mapping[str, Any],
) -> dict[str, Any]:
    people, by_form = _form_rows()
    prior = _prior_candidate_rows()
    semantic_index = {text(row.get("mention_id")): dict(row) for row in semantics.get("records", []) or []}
    mention_index = {text(row.get("mention_id")): dict(row) for row in ledger.get("valid_mentions", []) or []}
    records: list[dict[str, Any]] = []
    for mention_id, mention in sorted(mention_index.items()):
        if text(mention.get("entity_kind")) != "person":
            records.append({"mention_id": mention_id, "candidates": [], "retrieval_status": "non_person_or_collective"})
            continue
        semantic = semantic_index.get(mention_id, {})
        form = normalize_form(text(mention.get("surface")))
        candidate_rows: list[dict[str, Any]] = []
        seen_entities: set[str] = set()
        matching_forms = [form]
        for linked_id in semantic.get("coreference_with", []) or []:
            linked = mention_index.get(text(linked_id), {})
            linked_form = normalize_form(text(linked.get("surface")))
            if linked_form:
                matching_forms.append(linked_form)
        for matching_form in dict.fromkeys(matching_forms):
            for found in by_form.get(matching_form, []):
                person_id = text(found.get("person_id"))
                if not person_id or person_id in seen_entities:
                    continue
                seen_entities.add(person_id)
                evidence_id = f"sfh1-candidate-evidence-{stable_hash({'mention_id': mention_id, 'person_id': person_id, 'found': found})[:20]}"
                candidate_rows.append({
                    "candidate_key": f"c{len(candidate_rows)}",
                    "entity_type": "existing_person",
                    "person_id": person_id,
                    "display_name": people[person_id].get("canonical_name"),
                    "matched_surface": found.get("surface"),
                    "retrieval_basis": found.get("basis"),
                    "evidence": [{
                        "evidence_id": evidence_id,
                        "text": found.get("evidence"),
                        "source_ref": found.get("evidence_ref"),
                    }],
                })
            for found in prior.get(matching_form, []):
                candidate_id = text(found.get("candidate_person_id"))
                if not candidate_id or candidate_id in seen_entities:
                    continue
                seen_entities.add(candidate_id)
                evidence_id = f"sfh1-candidate-evidence-{stable_hash({'mention_id': mention_id, 'candidate_id': candidate_id, 'found': found})[:20]}"
                candidate_rows.append({
                    "candidate_key": f"c{len(candidate_rows)}",
                    "entity_type": "prior_candidate_person",
                    "candidate_person_id": candidate_id,
                    "display_name": found.get("surface"),
                    "matched_surface": found.get("surface"),
                    "retrieval_basis": found.get("basis"),
                    "evidence": [{"evidence_id": evidence_id, "text": found.get("surface"), "source_ref": found.get("evidence_ref")}],
                })
        # Full-name-like source forms may form a local candidate observation,
        # but structural, honorific, ruler, office and uncertain references do
        # not become candidate people merely because they were mentioned.
        if not candidate_rows and text(semantic.get("semantic_type")) not in STRUCTURAL_SEMANTICS and text(semantic.get("semantic_type")) in {"direct_person_form", "abbreviated_person_reference", "local_anaphoric_reference"} and text(mention.get("reference_form")) in {"full_name", "personal_name", "courtesy_name", "style_name", "nickname"} and text(mention.get("confidence")) in {"high", "medium"}:
            candidate_id = f"sfh1-local-person-{stable_hash({'mention_id': mention_id, 'surface': mention.get('surface'), 'evidence': mention.get('source_evidence_id')})[:22]}"
            candidate_rows.append({
                "candidate_key": "c0",
                "entity_type": "local_candidate_person",
                "candidate_person_id": candidate_id,
                "display_name": mention.get("surface"),
                "matched_surface": mention.get("surface"),
                "retrieval_basis": "source-grounded_local_person_form",
                "evidence": [{
                    "evidence_id": mention.get("source_evidence_id"),
                    "text": mention.get("surface"),
                    "source_ref": mention.get("source_evidence_id"),
                }],
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
        "candidate_only": True,
        "canonical_write_back": False,
    }


def candidate_evidence(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for candidate in record.get("candidates", []) or [] for item in candidate.get("evidence", []) or [] if isinstance(item, Mapping)]
