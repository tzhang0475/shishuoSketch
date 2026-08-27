#!/usr/bin/env python3
"""HDB2-PSL1.3C boundary repairs.

This module is intentionally an adapter over the frozen PSL1.3B/PSL1.1
implementation.  It does not alter the predicate weights, candidate scorer,
review prompt, rescue interface, or any canonical input.  Its two jobs are
to (a) make occurrence/profile provenance fail closed and (b) prevent a
single-character occurrence from becoming a catalogue-wide lexical person
through an alias lookup.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import hdb2_psl1_3b_common as base
import hdb2_psl1_1_common as psl1_1
import hdb2_full_frontier_common as common


# Preserve the B implementation's public helpers and wire contract.  The
# explicit definitions below replace only the C boundary behavior.
for _name in dir(base):
    if not _name.startswith("__"):
        globals().setdefault(_name, getattr(base, _name))


GENERATED = ROOT / "data/generated/hdb2-psl1-3c"
RUN_VERSION = "hdb2-psl1-3c-v1"
PROMPT_VERSION = base.PROMPT_VERSION
SELECTION_PATH = base.SELECTION_PATH
B_RUN = ROOT / "data/generated/hdb2-psl1-3b/live/20260827T-HDB2-PSL1-3B-LIVE"
PROFILE_AUDIT = ROOT / "data/derived/hdb2-f-profile-integrity-audit.json"

# These are semantic descriptions used in audit metadata.  The provider
# schema remains the frozen 1.3A/1.3B schema; no new live calls are made by
# the C replay.
ABBREVIATED_REFERENCE_TYPES = {
    "abbreviated_person_reference",
    "local_anaphoric_person_reference",
    "surname_reference",
}

# Only these evidence families contain historical source text.  Chronology,
# participant and candidate-profile rows are structured context, not text in
# which a local antecedent can be discovered.  Keeping this boundary explicit
# prevents a neighbour's serialized catalogue profile from becoming a false
# local name occurrence.
SOURCE_EVIDENCE_FAMILIES = {"relevant_source_evidence", "story_local_context"}


def freeze_selection(path: Path = SELECTION_PATH) -> dict[str, Any]:
    """Return exactly the frozen B selection; C has no new sample.

    Recomputing B's historical exclusion scan from inside the new C
    namespace would make the new namespace self-referential.  The committed B
    selection is the frozen input contract, so runtime C validation loads it
    and checks its own embedded invariants instead of rebuilding a different
    selection.
    """
    selection = read_json(path, {}) or {}
    if not selection or selection.get("selection_hash") is None:
        raise RuntimeError("hdb2_psl1_3c_frozen_selection_missing")
    if selection.get("overlap_with_prior_story_ids") != []:
        raise RuntimeError("hdb2_psl1_3c_selection_has_prior_story_overlap")
    if selection.get("independent_count") != 10 or selection.get("distinct_story_count") != 10:
        raise RuntimeError("hdb2_psl1_3c_selection_contract_invalid")
    if selection.get("candidate_only") is not True or selection.get("canonical_write_back") is not False:
        raise RuntimeError("hdb2_psl1_3c_selection_safety_invalid")
    return selection


def _source_text(case: Mapping[str, Any]) -> str:
    pieces = [str(case.get("story_context") or "")]
    pieces.extend(str(value or "") for value in case.get("annotation_context", []) or [])
    pieces.extend(
        str(row.get("text") or "")
        for row in case.get("evidence_items", []) or []
        if isinstance(row, Mapping)
        and str(row.get("family") or "") in SOURCE_EVIDENCE_FAMILIES
    )
    return "\n".join(piece for piece in pieces if piece)


def _source_rows(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return only source-bearing rows usable for local text grounding."""
    result: list[dict[str, Any]] = []
    for row in case.get("evidence_items", []) or []:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("family") or "") not in SOURCE_EVIDENCE_FAMILIES:
            continue
        if row.get("evidence_id") and row.get("text"):
            result.append(dict(row))
    return sorted(result, key=lambda row: str(row.get("evidence_id") or ""))


def _local_text_occurrence_surfaces(case: Mapping[str, Any], target: str, text: str) -> list[dict[str, Any]]:
    """Find conservative full forms visibly introducing a one-character target.

    This is an antecedent *hypothesis* only.  It never creates a candidate or
    an identity edge.  The narrow look-ahead requires a lexical delimiter
    after the possible full form (桓子野善, 桓玄時, 桓謙比), avoiding arbitrary
    CJK substrings and the structured neighbour/profile payloads excluded by
    ``_source_text``.
    """
    if len(target) != 1 or not text:
        return []
    rows = _source_rows(case)
    # The combined text is useful for the caller, but matching each source
    # segment separately preserves the evidence ref for a name that occurs in
    # an annotation rather than in the main text.
    segments: list[tuple[str, Mapping[str, Any]]] = []
    story_context = str(case.get("story_context") or "")
    if story_context:
        first = rows[0] if rows else {}
        segments.append((story_context, first))
    segments.extend((str(row.get("text") or ""), row) for row in rows)
    delimiters = "善時比入於曰、，。；\n素遇過在出與和為爲問語謂見令作是其家共酣方將以年位拜中"
    grammatical_initials = set(delimiters)
    pattern = re.compile(rf"{re.escape(target)}[\u3400-\u9fff]{{1,2}}(?=[{re.escape(delimiters)}])")
    result: dict[str, dict[str, Any]] = {}
    for segment, source in segments:
        for match in pattern.finditer(segment):
            surface = match.group(0)
            # Do not treat a grammatical character as the first character of
            # a possible name (桓於庭 is syntax, while 桓玄時 and 桓子野善
            # contain plausible full forms).
            if surface == target or surface[1:2] in grammatical_initials:
                continue
            result.setdefault(surface, {
                "surface": surface,
                "identity_observation_id": None,
                "resolved_person_id": None,
                "provisional_person_id": None,
                "evidence_id": source.get("evidence_id"),
                "evidence_ref": source.get("source_ref"),
                "exact_span": surface,
                "derivation": "visible_local_full_form_hypothesis",
            })
    return sorted(result.values(), key=lambda row: (-len(str(row.get("surface") or "")), str(row.get("surface") or "")))


def _local_occurrence_surfaces(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Collect full forms from independent HDB1 occurrence rows in this Story.

    This is deliberately not a catalogue/profile scan.  It lets the audit
    show possible local antecedents (for example 桓伊 for a later 桓) without
    turning a same-surface profile entry into identity evidence.
    """
    story_id = str(case.get("story_id") or "")
    target = str(case.get("target_surface") or "")
    text = _source_text(case)
    try:
        _, identities, _, _ = common.load_hdb1()
    except Exception:
        identities = []
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in identities:
        if str(row.get("story_id") or "") != story_id:
            continue
        surface = str(row.get("surface") or "")
        if not surface or surface == target or len(surface) <= len(target) or surface not in text:
            continue
        if str(row.get("entity_kind") or "person") in {"location", "event", "office", "work_title", "not_person", "collective_persons"}:
            continue
        key = (surface, str(row.get("identity_observation_id") or ""))
        result[key] = {
            "surface": surface,
            "identity_observation_id": row.get("identity_observation_id"),
            "resolved_person_id": row.get("resolved_person_id"),
            "provisional_person_id": row.get("provisional_person_id"),
            "evidence_ref": row.get("evidence_ref"),
            "exact_span": row.get("exact_span") or surface,
        }
    # Keep local names already admitted by the occurrence builder too.  This
    # supports fixture cases without making arbitrary text a person.
    for row in [*(case.get("local_neighbors", []) or []), *(case.get("candidates", []) or [])]:
        if not isinstance(row, Mapping):
            continue
        surface = str(row.get("display_name") or row.get("name") or "")
        if not surface or surface == target or len(surface) <= len(target) or surface not in text:
            continue
        key = (surface, str(row.get("person_id") or row.get("candidate_key") or "local"))
        result.setdefault(key, {
            "surface": surface,
            "identity_observation_id": None,
            "resolved_person_id": row.get("person_id"),
            "provisional_person_id": None,
            "evidence_ref": None,
            "exact_span": surface,
        })
    if len(target) == 1:
        for row in _local_text_occurrence_surfaces(case, target, text):
            key = (str(row.get("surface") or ""), str(row.get("evidence_id") or "text"))
            result.setdefault(key, row)
    return sorted(result.values(), key=lambda row: (-len(str(row.get("surface") or "")), str(row.get("surface") or ""), str(row.get("identity_observation_id") or "")))


def _comparison_distinct(case: Mapping[str, Any]) -> list[str]:
    """Find explicitly compared/separately introduced local surfaces."""
    target = str(case.get("target_surface") or "")
    text = _source_text(case)
    if not target:
        return []
    names = {target}
    for row in [*(case.get("local_neighbors", []) or []), *(case.get("candidates", []) or []), *_local_occurrence_surfaces(case)]:
        if isinstance(row, Mapping):
            for key in ("display_name", "name", "surface"):
                value = str(row.get(key) or "")
                if value and value in text:
                    names.add(value)
            profile = row.get("profile") if isinstance(row.get("profile"), Mapping) else {}
            for key in ("canonical_name", "aliases", "courtesy_names", "titles"):
                values = profile.get(key, []) if key != "canonical_name" else [profile.get(key)]
                names.update(str(value) for value in values or [] if value and str(value) in text)
    result: set[str] = set()
    # Comparison is not identity.  Use known local forms to avoid treating
    # arbitrary prose as a second person.
    for other in sorted(names, key=lambda value: (-len(value), value)):
        if other == target:
            continue
        if re.search(re.escape(target) + r"[^。；\n]{0,12}(?:比|如|與|和)" + re.escape(other), text) or re.search(re.escape(other) + r"[^。；\n]{0,12}(?:比|如|與|和)" + re.escape(target), text):
            result.add(other)
        if re.search(re.escape(target) + r"[^。；\n]{0,8}比" + re.escape(other), text) or re.search(re.escape(other) + r"[^。；\n]{0,8}比" + re.escape(target), text):
            result.add(other)
    # The common ``A年...，B...`` introduction is a separate-person cue.
    for match in re.finditer(r"([\u3400-\u9fff]{2,8})年[^，。；\n]{0,16}[，,]([\u3400-\u9fff]{2,8})", text):
        left, right = match.groups()
        if target == left or target.startswith(left) or left.startswith(target):
            result.add(right)
        elif target == right or target.startswith(right) or right.startswith(target):
            result.add(left)
    return sorted(result, key=lambda value: (-len(value), value))


def _single_character_hypothesis(case: Mapping[str, Any], target: str, text: str) -> dict[str, Any]:
    local = [row for row in _local_occurrence_surfaces(case) if str(row.get("surface") or "") != target]
    # The old wire schema has no abbreviated-person enum.  Retain ``uncertain``
    # as the provider-facing structure while exposing the richer Python
    # hypothesis in metadata.  This forces arbitration/resolution to remain
    # candidate- and evidence-bound rather than lexical-profile-bound.
    evidence = base._evidence_ids(case, (target,))
    semantic_kind = "local_anaphoric_person_reference" if local else "abbreviated_person_reference"
    components = [{"text": target, "role": "personal_form"}] if target and target in text else []
    return base._hypothesis(
        "abbreviated",
        "uncertain",
        "person" if local else "uncertain",
        components,
        basis=semantic_kind,
        evidence_ids=evidence,
        deterministic=False,
    )


def build_reference_hypotheses(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Build B hypotheses but never lexicalize a single-character surface."""
    target = str(case.get("target_surface") or "")
    if len(target) != 1:
        return base.build_reference_hypotheses(case)

    text = _source_text(case)
    hypotheses: list[dict[str, Any]] = []
    # Preserve explicit object/ruler/office syntax before the abbreviated
    # fallback.  These are not ordinary surname aliases.
    hypotheses.extend(base._office_hypotheses(case, target, text))
    if target in {"帝", "明帝", "武帝", "文帝", "元帝", "康帝"}:
        hypotheses.append(base._hypothesis("ruler", "ruler_reference", "ruler", [base._component(target, "title")], basis="known_ruler_title_surface", evidence_ids=base._evidence_ids(case, (target,)), deterministic=True))
    if target == "主":
        match = re.search(r"(?P<actor>[\u3400-\u9fff]{1,8})(?:初)?尚主", text)
        if match:
            actor = str(match.group("actor") or "").removesuffix("初")
            hypotheses.append(base._hypothesis("marriage", "non_person", "non_person", [base._component(actor, "anchor_person"), base._component(target, "title")], basis="explicit_marriage_object_syntax", evidence_ids=base._evidence_ids(case, (actor, "尚主")), deterministic=True))
    if target == "陛下":
        hypotheses.append(base._hypothesis("honorific", "honorific_person_reference", "ruler", [base._component(target, "title")], basis="honorific_ruler_reference", evidence_ids=base._evidence_ids(case, (target,)), deterministic=True))
    if not hypotheses:
        hypotheses.append(_single_character_hypothesis(case, target, text))
    # At most one abbreviated hypothesis; the local antecedent information is
    # attached later to the graph/audit packet rather than used as an implicit
    # identity decision.
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in hypotheses:
        key = (row.get("surface_structure"), row.get("referent_type"), tuple((c.get("text"), c.get("role")) for c in row.get("components", [])))
        unique.setdefault(key, row)
    return list(unique.values())


def reference_hypotheses(case: Mapping[str, Any]) -> dict[str, Any]:
    hypotheses = build_reference_hypotheses(case)
    deterministic = [row for row in hypotheses if row.get("deterministic")]
    # A single-character fallback is never deterministic even if a stale
    # caller supplies a catalogue alias.
    if len(str(case.get("target_surface") or "")) == 1 and not any(row.get("surface_structure") in {"ruler_reference", "honorific_person_reference", "non_person", *OFFICE_ROLE_STRUCTURES} for row in hypotheses):
        deterministic = []
    ambiguous = len(hypotheses) != 1 or len(deterministic) != 1
    return {
        "hypotheses": hypotheses,
        "ambiguous": ambiguous,
        "deterministic": len(deterministic) == 1 and not ambiguous,
        "deterministic_hypothesis": deterministic[0] if len(deterministic) == 1 and not ambiguous else None,
        "local_antecedent_hypotheses": _local_occurrence_surfaces(case) if len(str(case.get("target_surface") or "")) == 1 else [],
        "comparison_distinct_mentions": _comparison_distinct(case),
    }


def _clear_single_char_alias(case: dict[str, Any]) -> None:
    target = str(case.get("target_surface") or "")
    if len(target) != 1:
        return
    for row in case.get("deterministic_predicates", []) or []:
        if str(row.get("predicate") or "") == "AliasMatch":
            row.update({"value": 0.5, "evidence_ids": [], "reason": "single_character_alias_requires_local_antecedent"})


def _candidate_has_local_name_evidence(case: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
    """Whether a single-character candidate is named in this source packet.

    A relation neighbour is not a local antecedent merely because the graph
    builder placed it beside the occurrence.  For the abbreviated-reference
    boundary, require the candidate's displayed/canonical name itself to be
    visible in source-facing text (or an explicitly source-backed candidate
    evidence id).  Profile aliases are intentionally not enough: ``仲文`` in
    ``09-pinzao-088`` is not evidence that its unrelated catalogue bearer
    朱伺 is the person meant by 桓.
    """
    text = _source_text(case)
    display = str(candidate.get("display_name") or candidate.get("name") or "")
    if display and display in text:
        return True
    source_ids = {str(row.get("evidence_id") or "") for row in _source_rows(case)}
    supports = {str(value) for value in candidate.get("support_evidence_ids", []) or []}
    return bool(source_ids & supports)


def _prune_unrelated_single_character_candidates(case: dict[str, Any]) -> None:
    """Remove co-occurring graph neighbours from an abbreviated target.

    This is a candidate-generation boundary, not a new identity rule: local
    full-name occurrences remain available through the antecedent hypotheses,
    and a candidate explicitly named in the source remains in the set.  The
    operation is restricted to ordinary person references; ruler, office and
    structural references retain their separate semantics.
    """
    target = str(case.get("target_surface") or "")
    structure = case.get("reference_structure") or {}
    if len(target) != 1 or str(structure.get("reference_type") or "") not in {"person_reference", "unknown"}:
        return
    candidates = list(case.get("candidates", []) or [])
    kept = [row for row in candidates if _candidate_has_local_name_evidence(case, row)]
    removed = [row for row in candidates if row not in kept]
    if not removed:
        return
    removed_keys = {str(row.get("candidate_key")) for row in removed}
    case["candidates"] = kept
    case["candidate_keys"] = [str(row.get("candidate_key")) for row in kept]
    case["candidate_dossiers"] = [
        row for row in case.get("candidate_dossiers", []) or []
        if str(row.get("candidate_key")) not in removed_keys
    ]
    for field in ("deterministic_predicates", "known_relation_predicates", "psl1_hard_vetoes", "psl1_1_role_vetoes"):
        value = case.get(field)
        if isinstance(value, list):
            case[field] = [row for row in value if str(row.get("candidate_key")) not in removed_keys]
        elif isinstance(value, Mapping):
            case[field] = {key: item for key, item in value.items() if str(key) not in removed_keys}
    case["single_character_unrelated_candidates_removed"] = sorted(removed_keys)


def _comparison_vetoes(case: dict[str, Any], structure: Mapping[str, Any]) -> dict[str, list[str]]:
    vetoes = {str(key): sorted(set(str(value) for value in values)) for key, values in (case.get("psl1_hard_vetoes") or {}).items()}
    target = str(case.get("target_surface") or "")
    distinct = [str(value) for value in structure.get("explicit_distinct_mentions", []) if value]
    for candidate in case.get("candidates", []) or []:
        forms = psl1_1._profile_forms(candidate)
        if target not in distinct:
            continue
        if any(psl1_1.matching(form) == psl1_1.matching(other) for other in distinct if other != target for form in forms):
            key = str(candidate.get("candidate_key"))
            vetoes[key] = sorted(set(vetoes.get(key, []) + ["ExplicitDistinct"]))
    return vetoes


def _structure_fields(case: Mapping[str, Any], hypothesis: Mapping[str, Any], *, arbitration: Mapping[str, Any] | None = None) -> dict[str, Any]:
    fields = base._structure_fields(case, hypothesis, arbitration=arbitration)
    fields["derivation"] = "hdb2-psl1-3c-semantic-arbitration" if arbitration else "hdb2-psl1-3c-deterministic"
    fields["local_antecedent_hypotheses"] = _local_occurrence_surfaces(case) if len(str(case.get("target_surface") or "")) == 1 else []
    comparison = _comparison_distinct(case)
    existing = [str(value) for value in fields.get("explicit_distinct_mentions", []) if value]
    fields["explicit_distinct_mentions"] = sorted(set(existing + ([str(case.get("target_surface"))] if comparison else []) + comparison))
    fields["comparison_distinctness"] = comparison
    fields["semantic_hypothesis_kind"] = str(hypothesis.get("basis") or "")
    return fields


def finalize_reference_structure(case: Mapping[str, Any], arbitration: Mapping[str, Any] | None = None, validation: Mapping[str, Any] | None = None) -> dict[str, Any]:
    info = reference_hypotheses(case)
    hypotheses = info["hypotheses"]
    chosen: dict[str, Any] | None = None
    if info["deterministic"]:
        chosen = dict(info["deterministic_hypothesis"])
    elif arbitration and (validation or {}).get("valid") is True:
        chosen = base._find_hypothesis(hypotheses, str(arbitration.get("surface_structure") or "uncertain"), str(arbitration.get("referent_type") or "uncertain"))
        if chosen and arbitration.get("confidence") in {"low", None}:
            chosen = None
        if chosen:
            chosen["components"] = [dict(row) for row in arbitration.get("components", []) or []]
            chosen["evidence_ids"] = list(arbitration.get("supporting_evidence_ids", []) or [])
            chosen["referent_type"] = arbitration.get("referent_type")
    if chosen is None:
        chosen = base._hypothesis("uncertain", "uncertain", "uncertain", [], basis="ambiguous_without_accepted_semantic_arbitration")
    return _structure_fields(case, chosen, arbitration=arbitration)


def apply_reference_structures(graph: Mapping[str, Any], structures: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    result = base.apply_reference_structures(graph, structures)
    for case in result.get("cases", []) or []:
        _clear_single_char_alias(case)
        structure = case.get("reference_structure") or {}
        _prune_unrelated_single_character_candidates(case)
        distinct = _comparison_vetoes(case, structure)
        case["psl1_1_role_vetoes"] = distinct
        case["psl1_hard_vetoes"] = distinct
        case["local_antecedent_hypotheses"] = structure.get("local_antecedent_hypotheses", [])
        case["comparison_distinctness"] = structure.get("comparison_distinctness", [])
        case["candidate_only"] = True
        case["canonical_write_back"] = False
    result["schema"] = "hdb2-psl1-3c-graph-cases-v1"
    result["reference_structure_version"] = RUN_VERSION
    result["candidate_only"] = True
    result["canonical_write_back"] = False
    return result


def clean_structural_decisions(decisions: Mapping[str, Any], graph: Mapping[str, Any]) -> dict[str, Any]:
    result = base.clean_structural_decisions(decisions, graph)
    result["schema"] = "hdb2-psl1-3c-decisions-v1"
    result["reference_structure_version"] = RUN_VERSION
    result["candidate_only"] = True
    result["canonical_write_back"] = False
    return result


_BASE_APPLY_REVIEWER = psl1_1.apply_reviewer


def apply_reviewer(decisions: Mapping[str, Any], reviewer_rows: Sequence[Mapping[str, Any]], graph: Mapping[str, Any]) -> dict[str, Any]:
    """Apply frozen reviewer semantics, demoting invalid required reviews."""
    result = _BASE_APPLY_REVIEWER(decisions, reviewer_rows, graph)
    reviewers = {str(row.get("mention_id")): row for row in reviewer_rows}
    initial = {str(row.get("mention_id")): row for row in decisions.get("records", []) or []}
    for row in result.get("records", []) or []:
        mention_id = str(row.get("mention_id"))
        before = initial.get(mention_id, {})
        required = bool(row.get("reviewer_required")) or str(before.get("result_state") or "") in {"stable_entity_resolved", "review_required"}
        review = reviewers.get(mention_id)
        valid = bool(review and (review.get("validation") or {}).get("valid") is True)
        if required and not valid:
            # A required reviewer is a safety gate.  If its payload is
            # malformed/missing, preserving a pre-review resolution would be
            # fail-open; the human must see the item again even when the
            # current ranking has no viable candidate.
            row["result_state"] = "review_required"
            row["reviewer_invalid_demoted"] = True
            row["reviewer_invalid_errors"] = list((review or {}).get("validation", {}).get("errors", []) or []) if review else ["reviewer_missing"]
            row["reviewer_required"] = True
        row["candidate_only"] = True
        row["canonical_write_back"] = False
    result["schema"] = "hdb2-psl1-3c-final-decisions-v1"
    result["reviewer_invalid_demotions"] = sum(bool(row.get("reviewer_invalid_demoted")) for row in result.get("records", []))
    result["candidate_only"] = True
    result["canonical_write_back"] = False
    return result


def reference_regression_records() -> dict[str, Any]:
    """C structural regressions, using the same frozen cases as B."""
    expected = base.reference_regression_records()
    # Add the C-specific invariant without modifying the B report.
    graphs = [build_graph(freeze_selection())]
    by_key = {(str(c.get("story_id")), str(c.get("target_surface"))): c for g in graphs for c in g.get("cases", []) or []}
    checks = []
    for key in (("23-rendan-049", "桓"), ("09-pinzao-088", "桓"), ("09-pinzao-018", "潁")):
        case = by_key.get(key)
        info = reference_hypotheses(case) if case else {}
        checks.append({"story_id": key[0], "surface": key[1], "passed": bool(case and not any(row.get("surface_structure") == "lexicalized_personal_form" and row.get("deterministic") for row in info.get("hypotheses", []))), "hypotheses": info.get("hypotheses", [])})
    return {"schema": "hdb2-psl1-3c-reference-regressions-v1", "prior_b_regressions": expected, "records": checks, "all_pass": bool(expected.get("all_pass") and all(row.get("passed") for row in checks)), "candidate_only": True, "canonical_write_back": False}


__all__ = [name for name in globals() if not name.startswith("_")]
