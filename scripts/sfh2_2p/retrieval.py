"""Broad but safe candidate retrieval for selected SFH2.2-P mentions.

This module only proposes candidate keys.  It never resolves a mention and it
never writes an alias.  In particular, it has no local-context substring
search: local evidence is admitted only as a bounded whole validated mention
or as a supplied semantic referent hint.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Mapping

from .common import candidate_index, load_inputs, mention_index, normalize, packet_index, semantic_index, text, stable_hash


# These are retrieval categories emitted by the already validated SFH1
# mention reader.  They are deliberately narrower than "anything that looks
# like a Chinese phrase": descriptive, kinship, pronoun, and uncertain spans
# are not candidate-person evidence merely because they occur in a Story.
_LOCAL_PERSON_REFERENCE_FORMS = frozenset({
    "full_name", "personal_name", "courtesy_name", "style_name", "nickname",
})


def _people(inputs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        text(row.get("person_id")): dict(row)
        for row in (inputs.get("people") or {}).get("people", []) or []
        if isinstance(row, Mapping) and text(row.get("person_id"))
    }


def _alias_rows(inputs: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in (inputs.get("aliases") or {}).get("aliases", []) or [] if isinstance(row, Mapping)]


def _suppressed(inputs: Mapping[str, Any]) -> set[tuple[str, str]]:
    suppressed: set[tuple[str, str]] = set()
    overlays = inputs.get("hda2_overlay") or []
    overlays = overlays if isinstance(overlays, list) else overlays.get("records", []) or []
    for row in overlays:
        if isinstance(row, Mapping) and text(row.get("action")) == "suppress_claim":
            suppressed.add((normalize(row.get("target_surface")), text(row.get("person_id"))))
    # SFH2R's explicit wrong-bearer policy is safe to reuse as a retrieval
    # veto.  Importing this policy does not infer a new semantic answer.
    try:
        from identity_resolution_policy import explicitly_blocked_form_person_pairs
        suppressed.update((normalize(surface), text(pid)) for surface, pid in explicitly_blocked_form_person_pairs())
    except Exception:
        pass
    return suppressed


def _form_index(inputs: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    people = _people(inputs)
    suppressed = _suppressed(inputs)
    result: dict[str, list[dict[str, Any]]] = {}

    def add(surface: Any, pid: str, basis: str, scope: str, evidence: Any, snippet: Any) -> None:
        key = normalize(surface)
        if not key or pid not in people or (key, pid) in suppressed:
            return
        row = {
            "surface": text(surface), "person_id": pid, "basis": basis,
            "retrieval_scope": scope, "evidence_id": text(evidence), "evidence_text": text(snippet),
        }
        bucket = result.setdefault(key, [])
        signature = (row["person_id"], row["surface"], row["basis"], row["evidence_id"])
        if not any((x.get("person_id"), x.get("surface"), x.get("basis"), x.get("evidence_id")) == signature for x in bucket):
            bucket.append(row)

    for pid, person in people.items():
        add(person.get("canonical_name"), pid, "canonical_registry", "exact", f"registry:{pid}", person.get("canonical_name"))
    for alias in _alias_rows(inputs):
        ids = [text(value) for value in (alias.get("resolved_person_ids") or alias.get("person_ids") or []) if text(value) in people]
        mode = text(alias.get("resolution_mode")) or "contextual"
        scope = "exact" if mode == "exact" and text(alias.get("status")) in {"resolved", "candidate", ""} else "contextual"
        if not ids:
            continue
        sources = [source for source in alias.get("source_evidence", []) or [] if isinstance(source, Mapping)] or [{}]
        for pid in sorted(set(ids)):
            for source in sources:
                add(alias.get("surface"), pid, "reviewed_alias_registry", scope, source.get("evidence_id"), source.get("evidence_snippet"))
    # Active profile forms are used only when their own occurrence provenance
    # exists.  This keeps the pilot independent of convenience alias arrays.
    for profile in (inputs.get("profiles") or {}).get("records", []) or []:
        if not isinstance(profile, Mapping):
            continue
        pid = text(profile.get("person_id"))
        if pid not in people:
            continue
        for form in profile.get("identity", {}).get("form_provenance", []) or []:
            if not isinstance(form, Mapping) or text(form.get("identity_status")) not in {"direct_existing", "explicit_resolved", "contextually_resolved"}:
                continue
            add(form.get("surface"), pid, "validated_profile_form", "contextual", form.get("evidence_ref") or form.get("occurrence_id"), form.get("identity_basis"))
    for values in result.values():
        values.sort(key=lambda row: (row["retrieval_scope"], row["person_id"], row["surface"], row["evidence_id"]))
    return result


def _candidate_id(display_name: str) -> str:
    return f"sfh2-2p-candidate-person-{stable_hash({'display_name': normalize(display_name)})[:22]}"


def build_candidate_set(case: Mapping[str, Any], semantics: Mapping[str, Any], inputs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    inputs = inputs or load_inputs()
    mentions = mention_index(inputs)
    packets = packet_index(inputs)
    all_semantics = semantic_index(inputs)
    target_id = text(case.get("mention_id"))
    target = mentions.get(target_id, {})
    packet = packets.get(text(case.get("story_id")), {})
    forms = _form_index(inputs)
    people = _people(inputs)
    candidate_rows: "OrderedDict[tuple[str, str], dict[str, Any]]" = OrderedDict()
    distinct_veto_person_ids: set[str] = set()
    distinct_vetoes: list[dict[str, Any]] = []

    def add_existing(pid: str, *, basis: str, scope: str, matched_surface: Any, evidence_id: Any, evidence_text: Any, hint: Any = "") -> None:
        if pid not in people:
            return
        key = ("existing_person", pid)
        row = candidate_rows.get(key)
        if row is None:
            row = {
                "entity_type": "existing_person", "person_id": pid,
                "display_name": people[pid].get("canonical_name"), "matched_surface": text(matched_surface),
                "retrieval_basis": [], "retrieval_scopes": [], "semantic_referent_hint": text(hint),
                "requires_semantic_judgment": True, "evidence": [],
            }
            candidate_rows[key] = row
        row["retrieval_basis"].append(basis)
        row["retrieval_scopes"].append(scope)
        if text(evidence_id):
            row["evidence"].append({"evidence_id": text(evidence_id), "text": text(evidence_text) or text(matched_surface), "source_ref": text(evidence_id)})

    def add_candidate(display_name: Any, *, basis: str, evidence_id: Any, evidence_text: Any, hint: Any = "", candidate_type: str = "candidate_historical_person") -> None:
        display = text(display_name)
        if not display:
            return
        cid = _candidate_id(display)
        key = (candidate_type, cid)
        row = candidate_rows.get(key)
        if row is None:
            row = {
                "entity_type": candidate_type, "candidate_person_id": cid,
                "display_name": display, "matched_surface": text(target.get("surface")),
                "retrieval_basis": [], "retrieval_scopes": ["candidate_only"], "semantic_referent_hint": text(hint),
                "requires_semantic_judgment": True, "evidence": [],
            }
            candidate_rows[key] = row
        row["retrieval_basis"].append(basis)
        if text(evidence_id):
            row["evidence"].append({"evidence_id": text(evidence_id), "text": text(evidence_text) or display, "source_ref": text(evidence_id)})

    target_surface = text(target.get("surface"))
    hint = text(semantics.get("referent_hint"))
    lookup_forms = list(dict.fromkeys(value for value in (target_surface, hint) if normalize(value)))
    for surface in lookup_forms:
        for found in forms.get(normalize(surface), []):
            add_existing(found["person_id"], basis=found["basis"], scope=found["retrieval_scope"], matched_surface=found["surface"], evidence_id=found.get("evidence_id"), evidence_text=found.get("evidence_text"), hint=hint)

    # Whole validated local mentions are retrieval witnesses.  They are not
    # treated as identity assertions for the target until L5 judges them.
    local_mentions = [row for row in mentions.values() if text(row.get("story_id")) == text(case.get("story_id")) and text(row.get("mention_id")) != target_id]
    for local in sorted(local_mentions, key=lambda row: text(row.get("mention_id"))):
        local_surface = text(local.get("surface"))
        if not local_surface or text(local.get("entity_kind")) == "non_person":
            continue
        local_key = normalize(local_surface)
        local_found = forms.get(local_key, [])
        # A local mention is a retrieval witness only when the upstream
        # semantic reader called it a person-like whole form.  Length is not
        # a semantic authority: one-character surnames and arbitrary
        # substrings must not manufacture candidates.
        is_whole_person = text(local.get("reference_form")) in _LOCAL_PERSON_REFERENCE_FORMS
        if local_found and is_whole_person:
            for found in local_found:
                add_existing(found["person_id"], basis="validated_local_mention", scope=found["retrieval_scope"], matched_surface=local_surface, evidence_id=local.get("source_evidence_id"), evidence_text=local_surface, hint=hint)
        elif is_whole_person and text(local.get("entity_kind")) == "person":
            add_candidate(local_surface, basis="validated_local_person_mention", evidence_id=local.get("source_evidence_id"), evidence_text=local_surface, hint=hint)

    # Distinctness is an upstream semantic predicate, not a Python guess.
    # Where a distinct local mention has a grounded production form, carry it
    # as a hard veto so an identity judge cannot select the explicitly
    # different person.  The veto is provenance-bearing and is intentionally
    # independent of the evaluation metadata in the frozen selection.
    for distinct_id in sorted({text(value) for value in semantics.get("distinct_from", []) or [] if text(value)}):
        distinct = mentions.get(distinct_id, {})
        distinct_surface = text(distinct.get("surface"))
        if not distinct_surface:
            continue
        grounded = forms.get(normalize(distinct_surface), [])
        pids = sorted({text(found.get("person_id")) for found in grounded if text(found.get("person_id")) in people})
        for pid in pids:
            distinct_veto_person_ids.add(pid)
        if pids:
            distinct_vetoes.append({
                "distinct_mention_id": distinct_id,
                "distinct_surface": distinct_surface,
                "person_ids": pids,
                "basis": "validated_semantic_distinctness_plus_grounded_local_form",
                "evidence_id": text(distinct.get("source_evidence_id")),
            })

    # A validated semantic referent hint may name a historical person missing
    # from the registry.  The candidate is created here, but L5 must still
    # support it; the hint never performs a final state transition.
    # A hint that merely repeats the observed surface is not a new historical
    # entity label.  Keeping it out prevents the pilot from turning the
    # unresolved surface itself into a preferred candidate; a real expanded
    # hint such as 石勒 or 阮裕 is still preserved as a candidate-only entity.
    if hint and normalize(hint) != normalize(target_surface) and not any(normalize(row.get("display_name")) == normalize(hint) for row in candidate_rows.values()):
        add_candidate(hint, basis="semantic_referent_hint", evidence_id=semantics.get("supporting_evidence_ids", [target.get("source_evidence_id")])[0] if semantics.get("supporting_evidence_ids") else target.get("source_evidence_id"), evidence_text=hint, hint=hint)

    # Reuse prior local candidate observations only as candidate observations;
    # do not import old existing-Person profile matches into the pilot.
    prior = candidate_index(inputs).get(target_id, {})
    for old in prior.get("candidates", []) or []:
        if not isinstance(old, Mapping) or text(old.get("entity_type")) not in {"local_candidate_person", "prior_candidate_person"}:
            continue
        display = text(old.get("display_name"))
        if display and (not hint or normalize(display) != normalize(target_surface)):
            add_candidate(display, basis="prior_candidate_observation", evidence_id=target.get("source_evidence_id"), evidence_text=display, hint=hint, candidate_type="prior_candidate_person")

    candidates: list[dict[str, Any]] = []
    for row in candidate_rows.values():
        row["retrieval_basis"] = sorted(set(row.get("retrieval_basis", [])))
        row["retrieval_scopes"] = sorted(set(row.get("retrieval_scopes", [])))
        dedup: dict[str, dict[str, Any]] = {text(item.get("evidence_id")): item for item in row.get("evidence", []) if text(item.get("evidence_id"))}
        row["evidence"] = [dedup[key] for key in sorted(dedup)]
        candidates.append(row)
    # Keep packets bounded without deciding identity.  A semantic hint or a
    # validated whole local name is more useful retrieval context than an
    # unrelated prior candidate, but all retained rows remain subject to L5.
    def priority(row: Mapping[str, Any]) -> tuple[int, int, str, str]:
        bases = set(row.get("retrieval_basis", []) or [])
        if "semantic_referent_hint" in bases:
            rank = 0
        elif "canonical_registry" in bases or "reviewed_alias_registry" in bases:
            rank = 1
        elif "validated_local_mention" in bases or "validated_local_person_mention" in bases:
            rank = 2
        elif "prior_candidate_observation" in bases:
            rank = 3
        else:
            rank = 4
        return (rank, 0 if row.get("entity_type") == "existing_person" else 1, normalize(row.get("display_name")), text(row.get("person_id") or row.get("candidate_person_id")))

    candidates.sort(key=priority)
    candidates = candidates[:32]
    for index, row in enumerate(candidates):
        row["candidate_key"] = f"c{index}"
    return {
        "unit_id": target_id,
        "story_id": text(case.get("story_id")),
        "mention_id": target_id,
        "surface": target_surface,
        "semantic_type": text(semantics.get("semantic_type")) or "uncertain",
        "referent_hint": hint,
        "network_role": text(semantics.get("network_role")) or "uncertain",
        "hard_veto_person_ids": sorted(distinct_veto_person_ids),
        "hard_vetoes": distinct_vetoes,
        "candidates": candidates,
        "retrieval_status": "candidates_found" if candidates else "candidate_missing",
        "candidate_only": True,
        "canonical_write_back": False,
    }
