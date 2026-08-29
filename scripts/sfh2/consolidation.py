"""Candidate retrieval and collective identity consolidation for SFH2.

The functions in this module are deliberately split into retrieval, model
judgment validation, and deterministic storage decisions.  A surface is only
a blocking key; it is never an identity merge rule.
"""

from __future__ import annotations

import collections
import itertools
from typing import Any, Mapping, Sequence

from .common import flags, normalize_form, read_json, stable_hash, text
from .llm import SFH2Client, evidence_ids_in_payload, link_tool, pair_tool, validate_link_result, validate_pair_result

STRUCTURAL_TYPES = {"compositional_kinship", "patron_plus_office", "descriptive_person_reference"}
PERSON_REFERENCE_FORMS = {"full_name", "personal_name", "courtesy_name", "style_name", "nickname", "surname_reference", "abbreviated_reference", "office_title", "honorific", "ruler_title", "uncertain"}
VALID_LINK_STATES = {"linked_existing", "reused_sfh1_existing", "no_existing_match", "ambiguous_existing", "provider_failure", "offline_cache_miss", "invalid_payload", "not_eligible"}


def _people(documents: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {text(row.get("person_id")): dict(row) for row in (documents.get("people") or {}).get("people", []) or [] if isinstance(row, Mapping) and text(row.get("person_id"))}


def _suppressed(documents: Mapping[str, Any]) -> set[tuple[str, str]]:
    source = documents.get("hda2_overlay") or []
    rows = source if isinstance(source, list) else source.get("records", []) or []
    return {(normalize_form(row.get("target_surface")), text(row.get("person_id"))) for row in rows if isinstance(row, Mapping) and text(row.get("action")) == "suppress_claim"}


def _add_form(index: dict[str, list[dict[str, Any]]], by_person: dict[str, dict[str, set[str]]], *, surface: Any, person_id: str, form_type: str, basis: str, evidence_ref: Any = None, evidence_text: Any = None, suppressed: set[tuple[str, str]]) -> None:
    surface_text = text(surface)
    key = normalize_form(surface_text)
    if not key or (key, person_id) in suppressed:
        return
    item = {
        "surface": surface_text,
        "form_type": form_type,
        "person_id": person_id,
        "basis": basis,
        "evidence_ref": text(evidence_ref),
        "evidence_text": text(evidence_text) or surface_text,
    }
    bucket = index.setdefault(key, [])
    if not any((row.get("person_id"), row.get("surface"), row.get("basis"), row.get("evidence_ref")) == (item["person_id"], item["surface"], item["basis"], item["evidence_ref"]) for row in bucket):
        bucket.append(item)
    by_person.setdefault(person_id, {}).setdefault(form_type, set()).add(surface_text)


def build_existing_form_index(documents: Mapping[str, Any]) -> dict[str, Any]:
    people = _people(documents)
    suppressed = _suppressed(documents)
    index: dict[str, list[dict[str, Any]]] = {}
    by_person: dict[str, dict[str, set[str]]] = {}
    for pid, person in people.items():
        _add_form(index, by_person, surface=person.get("canonical_name"), person_id=pid, form_type="canonical_name", basis="canonical_registry", suppressed=suppressed)
    for alias in (documents.get("aliases") or {}).get("aliases", []) or []:
        if not isinstance(alias, Mapping):
            continue
        ids = {text(value) for value in (alias.get("resolved_person_ids") or alias.get("person_ids") or []) if text(value) in people}
        status = text(alias.get("status"))
        if not ids or status not in {"resolved", "context_dependent", "contextual", "shared_or_contextual"}:
            continue
        for pid in sorted(ids):
            for source in alias.get("source_evidence", []) or [{}]:
                source = source if isinstance(source, Mapping) else {}
                _add_form(index, by_person, surface=alias.get("surface"), person_id=pid, form_type=text(alias.get("alias_type")) or "alias", basis="valid_alias_registry", evidence_ref=source.get("source_id") or source.get("mention_id"), evidence_text=source.get("evidence_snippet"), suppressed=suppressed)
    # HDB2-F profile forms are usable only when their own occurrence-level
    # provenance is present and strong.  Never read the convenience aliases
    # array without its form_provenance companion.
    for profile in (documents.get("profiles") or {}).get("records", []) or []:
        if not isinstance(profile, Mapping):
            continue
        pid = text(profile.get("person_id"))
        if pid not in people:
            continue
        for form in profile.get("identity", {}).get("form_provenance", []) or []:
            if not isinstance(form, Mapping) or text(form.get("identity_status")) not in {"direct_existing", "explicit_resolved", "contextually_resolved"}:
                continue
            _add_form(index, by_person, surface=form.get("surface"), person_id=pid, form_type=text(form.get("form_type")) or "observed_surface", basis="validated_profile_provenance", evidence_ref=form.get("evidence_ref"), evidence_text=form.get("surface"), suppressed=suppressed)
    for key in index:
        index[key].sort(key=lambda row: (row["person_id"], -len(row["surface"]), row["surface"], row["basis"], row["evidence_ref"]))
    serial_by_person = {pid: {kind: sorted(values) for kind, values in kinds.items()} for pid, kinds in by_person.items()}
    return flags({
        "schema": "sfh2-existing-form-index-v1",
        "forms": {key: value for key, value in sorted(index.items())},
        "forms_by_person": serial_by_person,
        "suppressed_forms": [{"surface": surface, "person_id": pid} for surface, pid in sorted(suppressed)],
        "candidate_only": True,
        "canonical_write_back": False,
    })


def _profile_dossier(documents: Mapping[str, Any], person_id: str, form_index: Mapping[str, Any]) -> dict[str, Any]:
    people = _people(documents)
    person = people.get(person_id, {})
    profile = next((row for row in (documents.get("profiles") or {}).get("records", []) or [] if isinstance(row, Mapping) and text(row.get("person_id")) == person_id), {})
    forms = (form_index.get("forms_by_person") or {}).get(person_id, {})
    identity = profile.get("identity", {}) if isinstance(profile, Mapping) else {}
    offices = profile.get("offices", {}) if isinstance(profile, Mapping) else {}
    family = profile.get("family", {}) if isinstance(profile, Mapping) else {}
    social = profile.get("social", {}) if isinstance(profile, Mapping) else {}
    temporal = profile.get("temporal", {}) if isinstance(profile, Mapping) else {}
    evidence: list[dict[str, Any]] = []
    for form in profile.get("identity", {}).get("form_provenance", []) if isinstance(profile, Mapping) else []:
        if not isinstance(form, Mapping):
            continue
        if text(form.get("identity_status")) not in {"direct_existing", "explicit_resolved", "contextually_resolved"}:
            continue
        eid = f"sfh2-profile-evidence-{stable_hash({'person_id': person_id, 'form': form})[:20]}"
        evidence.append({"evidence_id": eid, "text": text(form.get("surface")), "basis": form.get("identity_basis"), "source_ref": form.get("evidence_ref")})
    def redact_ids(value: Any) -> Any:
        """Remove internal identity keys before a dossier reaches the LLM.

        Candidate keys are assigned by the caller.  Production IDs may be
        retained in Python-side retrieval results, but putting them in a
        semantic prompt would make the supposed candidate comparison an
        answer-labeling task.  Preserve readable names only when the source
        profile already supplies a canonical catalogue mapping.
        """
        if isinstance(value, Mapping):
            result: dict[str, Any] = {}
            for key, item in value.items():
                key_text = text(key)
                lowered = key_text.lower()
                if lowered in {"person_id", "candidate_person_id", "entity_id", "subject_endpoint", "object_endpoint"}:
                    readable = people.get(text(item), {}).get("canonical_name")
                    if readable:
                        result["related_person_name"] = readable
                    continue
                if lowered.endswith("_person_id") or lowered.endswith("_entity_id"):
                    continue
                result[key_text] = redact_ids(item)
            return result
        if isinstance(value, list):
            return [redact_ids(item) for item in value]
        return value

    def readable_neighbors() -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for item in social.get("resolved_neighbors", []) if isinstance(social, Mapping) else []:
            if not isinstance(item, Mapping):
                continue
            pid = text(item.get("person_id"))
            row = {key: value for key, value in item.items() if key != "person_id"}
            if pid in people:
                row["person_name"] = people[pid].get("canonical_name") or pid
            result.append(redact_ids(row))
        return result[:10]

    return {
        "name": person.get("canonical_name") or person_id,
        "aliases": sorted(set(forms.get("alias", []) + forms.get("observed_surface", []))),
        "courtesy_names": sorted(set(forms.get("courtesy_name", []))),
        "titles": sorted(set(forms.get("title", []) + forms.get("office_title", []))),
        "known_activity_context": [redact_ids(dict(item)) for item in temporal.get("activity_evidence", [])[:8] if isinstance(item, Mapping)],
        "known_offices": [redact_ids(dict(item)) for item in offices.get("office_candidates", [])[:8] if isinstance(item, Mapping)],
        "known_kinship": [redact_ids(dict(item)) for item in (family.get("kinship_candidates", []) + family.get("marriage_candidates", []))[:8] if isinstance(item, Mapping)],
        "known_neighbors": readable_neighbors(),
        "supporting_evidence": redact_ids(evidence[:12]),
    }


def _context_evidence(obs: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in (obs.get("local_context") or {}).get("evidence", []) or []:
        if isinstance(item, Mapping) and text(item.get("evidence_id")):
            rows.append({"evidence_id": item.get("evidence_id"), "text": item.get("text"), "source_layer": item.get("source_layer")})
    for item in obs.get("liu_evidence", []) or []:
        if isinstance(item, Mapping) and text(item.get("evidence_id")) and not any(text(row.get("evidence_id")) == text(item.get("evidence_id")) for row in rows):
            rows.append({"evidence_id": item.get("evidence_id"), "text": item.get("text"), "source_layer": "liu_annotation"})
    for item in obs.get("temporal_context", []) or []:
        if isinstance(item, Mapping) and text(item.get("evidence_id")) and not any(text(row.get("evidence_id")) == text(item.get("evidence_id")) for row in rows):
            rows.append({"evidence_id": item.get("evidence_id"), "text": item.get("exact_span") or item.get("surface"), "source_layer": "temporal_semantics"})
    return rows[:20]


def _candidate_matches(obs: Mapping[str, Any], form_index: Mapping[str, Any], documents: Mapping[str, Any]) -> list[dict[str, Any]]:
    people = _people(documents)
    suppressed = _suppressed(documents)
    surface = normalize_form(obs.get("surface"))
    matches: dict[str, dict[str, Any]] = {}
    for row in (form_index.get("forms") or {}).get(surface, []) or []:
        pid = text(row.get("person_id"))
        if pid in people and (surface, pid) not in suppressed:
            matches.setdefault(pid, {"person_id": pid, "matched_forms": [], "retrieval_bases": set(), "evidence": []})
            matches[pid]["matched_forms"].append(row.get("surface"))
            matches[pid]["retrieval_bases"].add(row.get("basis"))
            eid = text(row.get("evidence_ref")) or f"sfh2-form-evidence-{stable_hash(row)[:20]}"
            matches[pid]["evidence"].append({"evidence_id": eid, "text": row.get("evidence_text") or row.get("surface"), "source_ref": row.get("evidence_ref"), "basis": row.get("basis")})
    # A full canonical/alias form appearing in the same supplied source
    # packet is a retrieval hint, not a resolution.  It is especially useful
    # for abbreviated mentions whose source names the bearer nearby.
    context = "\n".join(text(item.get("text")) for item in _context_evidence(obs))
    for form, rows in (form_index.get("forms") or {}).items():
        if len(form) < 2 or form not in normalize_form(context):
            continue
        for row in rows:
            pid = text(row.get("person_id"))
            if pid not in people or (surface, pid) in suppressed:
                continue
            matches.setdefault(pid, {"person_id": pid, "matched_forms": [], "retrieval_bases": set(), "evidence": []})
            matches[pid]["matched_forms"].append(row.get("surface"))
            matches[pid]["retrieval_bases"].add("local_context_full_form_hint")
            matches[pid]["evidence"].append({"evidence_id": f"sfh2-local-form-evidence-{stable_hash({'obs': obs.get('observation_id'), 'form': form, 'pid': pid})[:20]}", "text": form, "source_ref": obs.get("source_evidence", {}).get("evidence_id"), "basis": "local_context_full_form_hint"})
    result: list[dict[str, Any]] = []
    for pid, row in sorted(matches.items()):
        result.append({
            "candidate_key": f"c{len(result)}",
            "person_id": pid,
            "display_name": people[pid].get("canonical_name") or pid,
            "matched_forms": sorted(set(row["matched_forms"])),
            "retrieval_basis": sorted(row["retrieval_bases"]),
            "evidence": sorted({text(item.get("evidence_id")): item for item in row["evidence"] if text(item.get("evidence_id"))}.values(), key=lambda item: item["evidence_id"])[:12],
            "dossier": _profile_dossier(documents, pid, form_index),
        })
    return result


def build_existing_link_candidates(observations_doc: Mapping[str, Any], documents: Mapping[str, Any]) -> dict[str, Any]:
    form_index = build_existing_form_index(documents)
    records: list[dict[str, Any]] = []
    for obs in observations_doc.get("records", []) or []:
        if not isinstance(obs, Mapping):
            continue
        # Existing-person observations are already represented by the frozen
        # SFH1 stable decision and do not need to be re-queried as candidate
        # links.  Keeping them out also prevents a prior stable observation
        # from being mistaken for a new candidate observation.
        if text(obs.get("classification")) not in {"candidate_observation", "unresolved_person_observation"}:
            continue
        candidates = _candidate_matches(obs, form_index, documents)
        records.append(flags({
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
    return flags({
        "schema": "sfh2-existing-person-link-candidates-v1",
        "records": sorted(records, key=lambda row: text(row.get("observation_id"))),
        "form_index_hash": stable_hash(form_index),
        "candidate_only": True,
        "canonical_write_back": False,
    })


def _link_payload(obs: Mapping[str, Any], link_record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task": "historical existing-Person link assessment",
        "unit_id": obs.get("observation_id"),
        "occurrence": {
            "surface": obs.get("surface"),
            "semantic_reference_type": obs.get("semantic_reference_type"),
            "reference_form": obs.get("reference_form"),
            "story_id": obs.get("story_id"),
            "exact_span": (obs.get("source_evidence") or {}).get("exact_span"),
        },
        "source_evidence": _context_evidence(obs),
        "reference_semantics": obs.get("reference_semantics"),
        "candidate_dossiers": [
            {
                "candidate_key": row.get("candidate_key"),
                "name": row.get("display_name"),
                "matched_forms": row.get("matched_forms"),
                "retrieval_basis": row.get("retrieval_basis"),
                "dossier": row.get("dossier"),
                "evidence": row.get("evidence"),
            }
            for row in link_record.get("candidates", []) or []
        ],
        "instruction": "Judge only supplied candidate keys; do not assign a production ID and do not use surface equality alone.",
    }


def run_existing_person_links(client: SFH2Client, observations_doc: Mapping[str, Any], candidates_doc: Mapping[str, Any], documents: Mapping[str, Any], *, max_calls: int | None = None) -> dict[str, Any]:
    people = _people(documents)
    suppressed = _suppressed(documents)
    obs_by_id = {text(row.get("observation_id")): row for row in observations_doc.get("records", []) or [] if isinstance(row, Mapping)}
    rows_by_id = {text(row.get("observation_id")): row for row in candidates_doc.get("records", []) or [] if isinstance(row, Mapping)}
    results: list[dict[str, Any]] = []
    calls_started = 0
    for observation_id in sorted(rows_by_id):
        obs = obs_by_id.get(observation_id, {})
        row = rows_by_id[observation_id]
        final = obs.get("previous_identity_decision") or {}
        previous_pid = text(final.get("person_id"))
        if text(final.get("final_state")) == "stable_entity_resolved" and previous_pid in people and (normalize_form(obs.get("surface")), previous_pid) not in suppressed:
            results.append(flags({"observation_id": observation_id, "status": "reused_sfh1_existing", "selected_person_id": previous_pid, "candidate_person_ids": [previous_pid], "basis": "frozen_sfh1_stable_occurrence", "supporting_evidence_ids": obs.get("source_evidence_ids", []), "candidate_only": True, "canonical_write_back": False}))
            continue
        candidates = list(row.get("candidates", []) or [])
        if not candidates:
            results.append(flags({"observation_id": observation_id, "status": "no_existing_match", "selected_person_id": None, "candidate_person_ids": [], "basis": "deterministic_retrieval_no_match", "candidate_only": True, "canonical_write_back": False}))
            continue
        candidate_keys = {text(item.get("candidate_key")) for item in candidates}
        payload = _link_payload(obs, row)
        allowed_ids = evidence_ids_in_payload(payload) | set(text(value) for value in obs.get("source_evidence_ids", []) if text(value))
        # Offline/replay mode must still consult the immutable cache.  The
        # live budget limits provider work only; applying it to replay would
        # discard already-grounded SFH2 responses and make a replay less
        # informative than the original run.
        if client.live and max_calls is not None and calls_started >= max_calls:
            results.append(flags({"observation_id": observation_id, "status": "not_eligible", "selected_person_id": None, "candidate_person_ids": sorted(text(item.get("person_id")) for item in candidates), "basis": "bounded_cost_control_unassessed", "candidate_only": True, "canonical_write_back": False}))
            continue
        calls_started += 1
        parsed = client.call(stage="existing_person_link", unit_id=observation_id, payload=payload, tool=link_tool(), max_tokens=1800)
        validated, errors = validate_link_result(parsed, observation_id, candidate_keys, allowed_ids)
        if errors or validated is None:
            results.append(flags({"observation_id": observation_id, "status": "offline_cache_miss" if parsed is None and not client.live else "provider_failure" if parsed is None else "invalid_payload", "selected_person_id": None, "candidate_person_ids": sorted(text(item.get("person_id")) for item in candidates), "basis": "fail_closed", "validation_errors": errors, "candidate_only": True, "canonical_write_back": False}))
            continue
        preferred = validated.get("preferred_candidate_key")
        assessments = {text(item.get("candidate_key")): item for item in validated.get("candidate_assessments", []) or []}
        selected = next((item for item in candidates if text(item.get("candidate_key")) == text(preferred)), None)
        selected_assessment = assessments.get(text(preferred), {})
        contradiction = bool(selected_assessment.get("contradicting_evidence_ids")) or text(selected_assessment.get("verdict")) == "contradict"
        supported = text(validated.get("resolution")) == "existing_person_supported" and text(selected_assessment.get("verdict")) == "support" and not contradiction and selected is not None
        results.append(flags({
            "observation_id": observation_id,
            "status": "linked_existing" if supported else "ambiguous_existing" if text(validated.get("resolution")) == "ambiguous_existing_person" else "no_existing_match",
            "selected_person_id": selected.get("person_id") if supported else None,
            "selected_candidate_key": preferred if supported else None,
            "candidate_person_ids": sorted(text(item.get("person_id")) for item in candidates),
            "basis": "llm_grounded_existing_person_assessment" if supported else "llm_did_not_support_unique_existing_person",
            "assessment": validated,
            "supporting_evidence_ids": sorted(set(text(value) for value in selected_assessment.get("supporting_evidence_ids", []) if text(value))),
            "candidate_only": True,
            "canonical_write_back": False,
        }))
    return flags({
        "schema": "sfh2-existing-person-link-results-v1",
        "records": results,
        "attempted_units": calls_started,
        "linked_existing_count": sum(row.get("status") in {"linked_existing", "reused_sfh1_existing"} for row in results),
        "candidate_only": True,
        "canonical_write_back": False,
    })


def _explicit_pairs(observations_doc: Mapping[str, Any]) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    coref: set[tuple[str, str]] = set()
    distinct: set[tuple[str, str]] = set()
    for obs in observations_doc.get("records", []) or []:
        left = text(obs.get("observation_id"))
        semantics = obs.get("reference_semantics") or {}
        for field, target in (("coreference_with", coref), ("distinct_from", distinct)):
            for mention in semantics.get(field, []) or []:
                # Reference semantics stores mention IDs; the map below is
                # applied by build_blocking.
                target.add((left, text(mention)))
    return {tuple(sorted(pair)) for pair in coref if pair[0] and pair[1] and pair[0] != pair[1]}, {tuple(sorted(pair)) for pair in distinct if pair[0] and pair[1] and pair[0] != pair[1]}


def _mention_to_observation(observations_doc: Mapping[str, Any]) -> dict[str, str]:
    return {text(row.get("mention_id")): text(row.get("observation_id")) for row in observations_doc.get("records", []) or [] if text(row.get("mention_id")) and text(row.get("observation_id"))}


def _pair_block_keys(left: Mapping[str, Any], right: Mapping[str, Any]) -> set[str]:
    keys: set[str] = set()
    ls, rs = normalize_form(left.get("surface")), normalize_form(right.get("surface"))
    if ls and ls == rs:
        keys.add("surface:" + ls)
    if text(left.get("previous_candidate_person_id")) and text(left.get("previous_candidate_person_id")) == text(right.get("previous_candidate_person_id")):
        keys.add("prior_candidate:" + text(left.get("previous_candidate_person_id")))
    if text(left.get("story_id")) == text(right.get("story_id")):
        keys.add("story:" + text(left.get("story_id")))
    # Semantic type by itself is deliberately not a blocking key: nearly all
    # direct references would otherwise form one dense graph.  It is retained
    # in the dossiers for model judgment, while blocking requires a textual,
    # local, temporal, or graph connection.
    left_neighbors = {text(row.get("subject_endpoint_before")) or text(row.get("object_endpoint_before")) for row in left.get("relation_context", []) or []}
    right_neighbors = {text(row.get("subject_endpoint_before")) or text(row.get("object_endpoint_before")) for row in right.get("relation_context", []) or []}
    for neighbor in sorted((left_neighbors & right_neighbors) - {""}):
        keys.add("neighbor:" + neighbor)
    left_temporal = {normalize_form(row.get("surface")) for row in left.get("temporal_context", []) or [] if normalize_form(row.get("surface"))}
    right_temporal = {normalize_form(row.get("surface")) for row in right.get("temporal_context", []) or [] if normalize_form(row.get("surface"))}
    for value in sorted(left_temporal & right_temporal):
        if len(value) >= 2:
            keys.add("temporal:" + value)
    return keys


def build_blocking(observations_doc: Mapping[str, Any], link_results: Mapping[str, Any]) -> dict[str, Any]:
    obs_by_id = {text(row.get("observation_id")): row for row in observations_doc.get("records", []) or [] if isinstance(row, Mapping)}
    linked = {text(row.get("observation_id")) for row in link_results.get("records", []) or [] if text(row.get("status")) in {"linked_existing", "reused_sfh1_existing"}}
    target = [row for oid, row in sorted(obs_by_id.items()) if text(row.get("classification")) == "candidate_observation" and oid not in linked]
    mention_map = _mention_to_observation(observations_doc)
    raw_coref, raw_distinct = _explicit_pairs(observations_doc)
    coref = {tuple(sorted((mention_map.get(a, a), mention_map.get(b, b)))) for a, b in raw_coref if mention_map.get(a, a) in obs_by_id and mention_map.get(b, b) in obs_by_id}
    distinct = {tuple(sorted((mention_map.get(a, a), mention_map.get(b, b)))) for a, b in raw_distinct if mention_map.get(a, a) in obs_by_id and mention_map.get(b, b) in obs_by_id}
    pair_keys: dict[tuple[str, str], set[str]] = {}
    key_counts: collections.Counter[str] = collections.Counter()
    for left, right in itertools.combinations(target, 2):
        keys = _pair_block_keys(left, right)
        if not keys:
            continue
        pair = tuple(sorted((text(left.get("observation_id")), text(right.get("observation_id")))))
        pair_keys[pair] = keys
        key_counts.update(keys)
    # Explicit semantic relationships remain available even if their surface
    # blocking keys are weak.
    for pair in sorted(coref | distinct):
        if pair[0] in {text(row.get("observation_id")) for row in target} and pair[1] in {text(row.get("observation_id")) for row in target}:
            pair_keys.setdefault(pair, set()).add("validated_semantic_pair")
    pairs = [{"comparison_id": f"sfh2-comparison-{stable_hash({'left': pair[0], 'right': pair[1]})[:24]}", "left_observation_id": pair[0], "right_observation_id": pair[1], "block_keys": sorted(keys), "priority": _pair_priority(pair, pair_keys[pair], obs_by_id), "candidate_only": True, "canonical_write_back": False} for pair, keys in sorted(pair_keys.items())]
    pairs.sort(key=lambda row: (-int(row.get("priority") or 0), row["comparison_id"]))
    target_count = len(target)
    total_possible = target_count * max(0, target_count - 1) // 2
    return flags({
        "schema": "sfh2-candidate-blocking-v1",
        "candidate_observation_count": target_count,
        "total_possible_pairs": total_possible,
        "blocked_pair_count": len(pairs),
        "discarded_deterministic_non_candidate_pairs": total_possible - len(pairs),
        "block_key_counts": dict(sorted(key_counts.items())),
        "explicit_coreference_pairs": [{"left": a, "right": b} for a, b in sorted(coref)],
        "explicit_distinct_pairs": [{"left": a, "right": b} for a, b in sorted(distinct)],
        "pairs": pairs,
        "candidate_only": True,
        "canonical_write_back": False,
    })


def _pair_priority(pair: tuple[str, str], keys: set[str], obs_by_id: Mapping[str, Mapping[str, Any]]) -> int:
    score = 0
    score += 20 if "validated_semantic_pair" in keys else 0
    score += 12 if any(key.startswith("prior_candidate:") for key in keys) else 0
    score += 10 if any(key.startswith("surface:") and len(key.split(":", 1)[1]) >= 2 for key in keys) else 0
    score += 8 if any(key.startswith("neighbor:") for key in keys) else 0
    score += 5 if any(key.startswith("story:") for key in keys) else 0
    score += min(4, max(len(text(obs_by_id.get(pair[0], {}).get("surface"))), len(text(obs_by_id.get(pair[1], {}).get("surface")))))
    return score


def _pair_payload(left: Mapping[str, Any], right: Mapping[str, Any], comparison: Mapping[str, Any]) -> dict[str, Any]:
    def packet(obs: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "observation_id": obs.get("observation_id"),
            "surface": obs.get("surface"),
            "story_id": obs.get("story_id"),
            "semantic_reference_type": obs.get("semantic_reference_type"),
            "reference_form": obs.get("reference_form"),
            "exact_span": (obs.get("source_evidence") or {}).get("exact_span"),
            "source_evidence": _context_evidence(obs),
            "reference_semantics": obs.get("reference_semantics"),
            "temporal_context": obs.get("temporal_context", [])[:6],
            "relation_context": obs.get("relation_context", [])[:8],
        }
    return {"task": "candidate observation identity comparison", "comparison_id": comparison.get("comparison_id"), "left": packet(left), "right": packet(right), "instruction": "Determine whether these observations refer to one historical person. Surface similarity and co-occurrence are not sufficient; explicit distinctness must prevail."}


def run_pair_judgments(client: SFH2Client, observations_doc: Mapping[str, Any], blocking_doc: Mapping[str, Any], *, max_calls: int | None = None) -> dict[str, Any]:
    obs_by_id = {text(row.get("observation_id")): row for row in observations_doc.get("records", []) or [] if isinstance(row, Mapping)}
    explicit_coref = {tuple(sorted((text(row.get("left")), text(row.get("right"))))) for row in blocking_doc.get("explicit_coreference_pairs", []) or []}
    explicit_distinct = {tuple(sorted((text(row.get("left")), text(row.get("right"))))) for row in blocking_doc.get("explicit_distinct_pairs", []) or []}
    results: list[dict[str, Any]] = []
    calls = 0
    for comparison in blocking_doc.get("pairs", []) or []:
        left_id, right_id = text(comparison.get("left_observation_id")), text(comparison.get("right_observation_id"))
        pair = tuple(sorted((left_id, right_id)))
        if pair in explicit_distinct:
            results.append(flags({"comparison_id": comparison.get("comparison_id"), "left_observation_id": left_id, "right_observation_id": right_id, "verdict": "distinct_persons", "evaluation_status": "reused_validated_distinctness", "supporting_evidence_ids": [], "contradicting_evidence_ids": [], "reason_types": ["explicit_distinctness"], "candidate_only": True, "canonical_write_back": False}))
            continue
        if pair in explicit_coref:
            evidence = sorted(set(text(value) for value in obs_by_id.get(left_id, {}).get("source_evidence_ids", []) + obs_by_id.get(right_id, {}).get("source_evidence_ids", []) if text(value)))
            results.append(flags({"comparison_id": comparison.get("comparison_id"), "left_observation_id": left_id, "right_observation_id": right_id, "verdict": "same_person", "evaluation_status": "reused_validated_coreference", "supporting_evidence_ids": evidence, "contradicting_evidence_ids": [], "reason_types": ["story_coreference"], "candidate_only": True, "canonical_write_back": False}))
            continue
        if client.live and max_calls is not None and calls >= max_calls:
            results.append(flags({"comparison_id": comparison.get("comparison_id"), "left_observation_id": left_id, "right_observation_id": right_id, "verdict": None, "evaluation_status": "not_evaluated_cost_control", "supporting_evidence_ids": [], "contradicting_evidence_ids": [], "reason_types": [], "candidate_only": True, "canonical_write_back": False}))
            continue
        calls += 1
        payload = _pair_payload(obs_by_id.get(left_id, {}), obs_by_id.get(right_id, {}), comparison)
        parsed = client.call(stage="candidate_pair", unit_id=text(comparison.get("comparison_id")), payload=payload, tool=pair_tool(), max_tokens=1400)
        allowed = evidence_ids_in_payload(payload)
        validated, errors = validate_pair_result(parsed, text(comparison.get("comparison_id")), allowed)
        if errors or validated is None:
            results.append(flags({"comparison_id": comparison.get("comparison_id"), "left_observation_id": left_id, "right_observation_id": right_id, "verdict": None, "evaluation_status": "offline_cache_miss" if parsed is None and not client.live else "provider_failure" if parsed is None else "invalid_payload", "validation_errors": errors, "supporting_evidence_ids": [], "contradicting_evidence_ids": [], "reason_types": [], "candidate_only": True, "canonical_write_back": False}))
            continue
        results.append(flags({"comparison_id": comparison.get("comparison_id"), "left_observation_id": left_id, "right_observation_id": right_id, "verdict": validated.get("verdict"), "evaluation_status": "llm_validated", "supporting_evidence_ids": validated.get("supporting_evidence_ids", []), "contradicting_evidence_ids": validated.get("contradicting_evidence_ids", []), "reason_types": validated.get("reason_types", []), "explanation": validated.get("explanation"), "candidate_only": True, "canonical_write_back": False}))
    return flags({"schema": "sfh2-candidate-pair-judgments-v1", "records": results, "llm_calls": calls, "same_person_count": sum(row.get("verdict") == "same_person" for row in results), "distinct_person_count": sum(row.get("verdict") == "distinct_persons" for row in results), "candidate_only": True, "canonical_write_back": False})


class _DisjointSet:
    def __init__(self, items: Sequence[str]) -> None:
        self.parent = {item: item for item in items}

    def find(self, item: str) -> str:
        parent = self.parent.get(item, item)
        if parent != item:
            self.parent[item] = self.find(parent)
        return self.parent.get(item, item)

    def union(self, left: str, right: str) -> None:
        a, b = self.find(left), self.find(right)
        if a == b:
            return
        self.parent[max(a, b)] = min(a, b)


def _cluster_id(members: Sequence[str]) -> str:
    return "sfh2-candidate-entity-" + stable_hash({"members": sorted(members)})[:24]


def consolidate_entities(observations_doc: Mapping[str, Any], link_results: Mapping[str, Any], blocking_doc: Mapping[str, Any], pair_doc: Mapping[str, Any], documents: Mapping[str, Any]) -> dict[str, Any]:
    observations = {text(row.get("observation_id")): dict(row) for row in observations_doc.get("records", []) or [] if text(row.get("observation_id"))}
    links = {text(row.get("observation_id")): dict(row) for row in link_results.get("records", []) or [] if text(row.get("observation_id"))}
    dsu = _DisjointSet([oid for oid, row in observations.items() if row.get("classification") == "candidate_observation"])
    distinct_pairs = {tuple(sorted((text(row.get("left")), text(row.get("right"))))) for row in blocking_doc.get("explicit_distinct_pairs", []) or []}
    pair_rows = list(pair_doc.get("records", []) or [])
    distinct_pairs |= {tuple(sorted((text(row.get("left_observation_id")), text(row.get("right_observation_id"))))) for row in pair_rows if row.get("verdict") == "distinct_persons"}
    merge_edges: list[dict[str, Any]] = []
    rejected_merges: list[dict[str, Any]] = []
    for row in sorted(pair_rows, key=lambda item: text(item.get("comparison_id"))):
        if row.get("verdict") != "same_person":
            continue
        left, right = text(row.get("left_observation_id")), text(row.get("right_observation_id"))
        if left not in dsu.parent or right not in dsu.parent:
            continue
        left_root, right_root = dsu.find(left), dsu.find(right)
        candidate_members = {member for member in dsu.parent if dsu.find(member) in {left_root, right_root}}
        conflict = next((pair for pair in sorted(distinct_pairs) if pair[0] in candidate_members and pair[1] in candidate_members), None)
        if conflict:
            rejected_merges.append({"comparison_id": row.get("comparison_id"), "left_observation_id": left, "right_observation_id": right, "reason": "explicit_distinctness_veto", "distinct_pair": list(conflict)})
            continue
        dsu.union(left, right)
        merge_edges.append({"comparison_id": row.get("comparison_id"), "left_observation_id": left, "right_observation_id": right, "basis": row.get("evaluation_status"), "supporting_evidence_ids": row.get("supporting_evidence_ids", [])})
    groups: dict[str, list[str]] = collections.defaultdict(list)
    for oid in dsu.parent:
        groups[dsu.find(oid)].append(oid)
    cluster_rows: list[dict[str, Any]] = []
    observation_entities: list[dict[str, Any]] = []
    for root, members in sorted(groups.items(), key=lambda item: _cluster_id(item[1])):
        members.sort()
        cid = _cluster_id(members)
        member_rows = [observations[oid] for oid in members]
        labels = sorted({text(row.get("surface")) for row in member_rows if text(row.get("surface"))}, key=lambda value: (-len(value), value))
        evidence_ids = sorted({text(value) for row in member_rows for value in row.get("source_evidence_ids", []) if text(value)})
        offices = sorted({text((row.get("reference_semantics") or {}).get("semantic_type")) for row in member_rows if text((row.get("reference_semantics") or {}).get("semantic_type")) in {"office_holder_reference", "patron_plus_office"}})
        neighbor_ids = sorted({text(value) for row in member_rows for relation in row.get("relation_context", []) for value in [relation.get("subject_endpoint_before"), relation.get("object_endpoint_before")] if text(value)})
        cluster_rows.append(flags({
            "cluster_id": cid,
            "member_observation_ids": members,
            "member_mention_ids": sorted(text(row.get("mention_id")) for row in member_rows if text(row.get("mention_id"))),
            "observed_surfaces": labels,
            "candidate_display_label": labels[0] if labels else cid,
            "temporal_context": sorted({text(item.get("surface")) for row in member_rows for item in row.get("temporal_context", []) if text(item.get("surface"))}),
            "associated_offices": offices,
            "relation_neighbors": neighbor_ids,
            "evidence_ids": evidence_ids,
            "identity_confidence_state": "collectively_supported" if len(members) > 1 and any(edge.get("left_observation_id") in members and edge.get("right_observation_id") in members for edge in merge_edges) else "unresolved_candidate_entity",
            "merge_evidence": [edge for edge in merge_edges if edge.get("left_observation_id") in members and edge.get("right_observation_id") in members],
            "unresolved_conflicts": [row for row in rejected_merges if row.get("left_observation_id") in members or row.get("right_observation_id") in members],
            "candidate_only": True,
            "canonical_write_back": False,
        }))
        for row in member_rows:
            observation_entities.append(flags({"observation_id": row.get("observation_id"), "mention_id": row.get("mention_id"), "entity_type": "candidate_person_entity", "entity_id": cid, "previous_candidate_person_id": row.get("previous_candidate_person_id"), "decision": "candidate_cluster", "provenance": row.get("provenance"), "candidate_only": True, "canonical_write_back": False}))
    for oid, row in sorted(observations.items()):
        classification = text(row.get("classification"))
        if classification == "candidate_observation":
            link = links.get(oid, {})
            if text(link.get("status")) in {"linked_existing", "reused_sfh1_existing"} and text(link.get("selected_person_id")):
                observation_entities = [item for item in observation_entities if text(item.get("observation_id")) != oid]
                observation_entities.append(flags({"observation_id": oid, "mention_id": row.get("mention_id"), "entity_type": "production_person", "entity_id": link.get("selected_person_id"), "previous_candidate_person_id": row.get("previous_candidate_person_id"), "decision": link.get("status"), "provenance": {"observation": row.get("provenance"), "link": link.get("supporting_evidence_ids", [])}, "candidate_only": True, "canonical_write_back": False}))
        elif classification == "existing_person_observation" and text((row.get("previous_identity_decision") or {}).get("person_id")):
            observation_entities.append(flags({"observation_id": oid, "mention_id": row.get("mention_id"), "entity_type": "production_person", "entity_id": (row.get("previous_identity_decision") or {}).get("person_id"), "decision": "reused_sfh1_existing", "provenance": row.get("provenance"), "candidate_only": True, "canonical_write_back": False}))
        elif classification == "non_person":
            observation_entities.append(flags({"observation_id": oid, "mention_id": row.get("mention_id"), "entity_type": "non_person", "entity_id": None, "decision": "non_person", "provenance": row.get("provenance"), "candidate_only": True, "canonical_write_back": False}))
        elif classification == "collective_reference":
            observation_entities.append(flags({"observation_id": oid, "mention_id": row.get("mention_id"), "entity_type": "collective_reference", "entity_id": f"sfh2-collective-{stable_hash(oid)[:20]}", "decision": "collective_reference", "provenance": row.get("provenance"), "candidate_only": True, "canonical_write_back": False}))
        elif classification == "structural_reference":
            observation_entities.append(flags({"observation_id": oid, "mention_id": row.get("mention_id"), "entity_type": "structural_reference", "entity_id": f"sfh2-structural-{stable_hash(oid)[:20]}", "decision": "structural_reference", "provenance": row.get("provenance"), "candidate_only": True, "canonical_write_back": False}))
        elif classification == "unresolved_person_observation":
            observation_entities.append(flags({"observation_id": oid, "mention_id": row.get("mention_id"), "entity_type": "unresolved_reference", "entity_id": None, "decision": "unresolved", "provenance": row.get("provenance"), "candidate_only": True, "canonical_write_back": False}))
    # A candidate observation linked to an existing Person must not retain its
    # singleton candidate cluster as a parallel entity.
    entity_map = {text(row.get("observation_id")): row for row in observation_entities}
    cluster_rows = [row for row in cluster_rows if not any(text(entity_map.get(oid, {}).get("entity_type")) == "production_person" for oid in row.get("member_observation_ids", []))]
    return flags({
        "schema": "sfh2-entity-consolidation-v1",
        "candidate_clusters": sorted(cluster_rows, key=lambda row: text(row.get("cluster_id"))),
        "observation_entities": sorted(entity_map.values(), key=lambda row: text(row.get("observation_id"))),
        "merge_edges": merge_edges,
        "rejected_merges": rejected_merges,
        "distinct_pair_count": len(distinct_pairs),
        "candidate_observation_count": sum(row.get("classification") == "candidate_observation" for row in observations.values()),
        "candidate_cluster_count": len(cluster_rows),
        "candidate_nodes_merged": sum(max(0, len(row.get("member_observation_ids", [])) - 1) for row in cluster_rows),
        "candidate_only": True,
        "canonical_write_back": False,
    })
