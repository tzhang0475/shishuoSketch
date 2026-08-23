#!/usr/bin/env python3
"""Deterministic full identity replay helpers for HNG1R2.

HNG1R2 consumes the frozen HNG1 candidate projection and source evidence.  It
uses one catalogue schema throughout (``build_hng0_2.person_catalog``), never
calls a model, and never mutates canonical identity data.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import build_hng0_2 as hng02
from hng1r_common import resolve_contextual_short_name


ROOT = Path(__file__).resolve().parents[1]
HNG1_ROOT = ROOT / "data/generated/hng1"
HNG1R_ROOT = ROOT / "data/generated/hng1r"

RESOLVER_VERSION = "hng1r2-full-offline-identity-replay-v1"
GENERIC_ROLE_SURFACES = set(hng02.GENERIC_SURFACES) | {"客", "帝", "太子", "皇帝"}
KINSHIP_RELATION_TYPES = {
    "parent_child",
    "grandparent_grandchild",
    "sibling",
    "uncle_nephew",
    "cousin_clan_kin",
    "marriage",
    "affinal_relation",
    "same_clan",
}
KINSHIP_EXPRESSION_MARKERS = (
    "從父兄", "從父弟", "兄子", "弟子", "從兄", "從弟",
    "祖父", "外祖", "父", "母", "兄", "弟", "叔", "舅", "妻", "婿", "孫",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _compact(value: Any) -> str:
    return " ".join(str(value or "").split())


def _strip_heading_markup(value: str) -> str:
    text = re.sub(r"\[\[([^]|]+)(?:\|[^]]+)?\]\]", r"\1", value)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    return _compact(text)


def _headings(text: str) -> list[tuple[int, str]]:
    rows: list[tuple[int, str]] = []
    pattern = re.compile(r"(?m)^\s*(={2,6})\s*([^=\n]+?)\s*\1\s*$")
    for match in pattern.finditer(text):
        heading = _strip_heading_markup(match.group(2))
        if heading:
            rows.append((match.start(), heading))
    return rows


def _nearest_heading(text: str, position: int) -> str | None:
    previous = [(offset, heading) for offset, heading in _headings(text) if offset <= position]
    if not previous:
        return None
    return sorted(previous, key=lambda item: item[0])[-1][1]


def _candidate_quotes(candidate: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(item.get("ref")): str(item.get("quote") or "")
        for item in candidate.get("evidence_quotes", [])
        if isinstance(item, Mapping) and item.get("ref")
    }


def localize_evidence(
    candidate: Mapping[str, Any],
    evidence: Mapping[str, Mapping[str, Any]],
    *,
    radius: int = 500,
    expose_heading_to_resolver: bool = False,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Build source-derived local contexts around each exact candidate quote.

    The localized records are ephemeral resolver inputs.  The frozen source
    registry remains untouched, and the audit retains the exact source window
    instead of an unrelated model-facing retrieval snippet.
    """

    quotes = _candidate_quotes(candidate)
    refs = sorted({str(ref) for ref in candidate.get("evidence_refs", []) if ref} | set(quotes))
    localized: dict[str, dict[str, Any]] = {}
    audit_contexts: list[dict[str, Any]] = []
    for ref in refs:
        source = evidence.get(ref, {})
        original = str(source.get("original_text") or "")
        quote = quotes.get(ref, "")
        position = original.find(quote) if quote else -1
        if position < 0:
            position = 0
            start, end = 0, min(len(original), max(1000, len(quote)))
        else:
            start = max(0, position - radius)
            end = min(len(original), position + len(quote) + radius)
        window = original[start:end]
        heading = _nearest_heading(original, position)
        locator = dict(source.get("locator") or {})
        if expose_heading_to_resolver and heading:
            locator["unit_title"] = heading
            locator["title"] = heading
        localized[ref] = {
            **dict(source),
            "original_text": window,
            "model_snippet": "",
            "locator": locator,
        }
        audit_contexts.append({
            "ref": ref,
            "source_work": source.get("source_work"),
            "source_layer": source.get("source_layer"),
            "source_path": source.get("source_path"),
            "exact_quote": quote,
            "local_context": window,
            "local_context_start": start,
            "local_context_end": end,
            "source_unit_title": heading,
        })
    return localized, audit_contexts


def candidate_from_projection(
    row: Mapping[str, Any],
    old_resolution: Mapping[str, Any],
) -> tuple[dict[str, Any], str, str]:
    """Recover one frozen candidate occurrence from its HNG1 projection."""

    candidate = copy.deepcopy(dict(row))
    candidate_id = str(old_resolution.get("candidate_id") or "")
    kind = str(old_resolution.get("candidate_kind") or ("relation" if "counterpart_surface" in row else "temporal"))
    if kind == "relation":
        candidate["relation_id"] = candidate_id
        surface_key = "counterpart_surface"
    else:
        candidate["temporal_id"] = candidate_id
        candidate["person_id"] = old_resolution.get("seed_person_id")
        surface_key = "subject_surface"
    # Generated model claims are not identity evidence.  Identity replay uses
    # exact quotations and local source structure only.
    candidate["claim"] = ""
    return candidate, kind, surface_key


def _base_identity_row(
    *,
    old_resolution: Mapping[str, Any],
    candidate: Mapping[str, Any],
    status: str,
    method: str,
    resolved_person_id: str | None = None,
    resolved_label: str | None = None,
    provisional_person_id: str | None = None,
    matches: Sequence[str] = (),
    confidence: str = "low",
    note: str = "",
    local_contexts: Sequence[Mapping[str, Any]] = (),
    candidate_set: Sequence[str] = (),
    context_signals: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    surface = str(old_resolution.get("surface") or candidate.get("counterpart_surface") or candidate.get("subject_surface") or "")
    refs = sorted({str(ref) for ref in candidate.get("evidence_refs", []) if ref})
    quotes = _candidate_quotes(candidate)
    supporting = next((quotes[ref] for ref in refs if quotes.get(ref)), "")
    return {
        "candidate_id": str(old_resolution.get("candidate_id") or ""),
        "candidate_kind": old_resolution.get("candidate_kind"),
        "seed_person_id": old_resolution.get("seed_person_id"),
        "surface": surface,
        "original_surface": surface,
        "resolved_person_id": resolved_person_id,
        "provisional_person_id": provisional_person_id,
        "resolved_label": resolved_label,
        "resolution_status": status,
        "resolution_method": method,
        "supporting_evidence_refs": refs,
        "evidence_refs": refs,
        "supporting_passage": supporting,
        "confidence": confidence,
        "matches": sorted(set(str(value) for value in matches if value)),
        "candidate_set": sorted(set(str(value) for value in candidate_set if value)),
        "context_signals": [dict(value) for value in context_signals],
        "local_resolver_context": [dict(value) for value in local_contexts],
        "note": note,
    }


def _is_generic_role(surface: str) -> bool:
    folded = hng02.lookup(surface)
    return folded in {hng02.lookup(value) for value in GENERIC_ROLE_SURFACES}


def _kinship_abbreviation(
    candidate: Mapping[str, Any],
    *,
    kind: str,
    surface: str,
) -> bool:
    if kind != "relation" or len(hng02.lookup(surface)) != 1 or _is_generic_role(surface):
        return False
    relation_type = str(candidate.get("original_relation_type") or candidate.get("normalized_relation_type") or candidate.get("relation_type") or "")
    quote_text = "".join(_candidate_quotes(candidate).values())
    return relation_type in KINSHIP_RELATION_TYPES and any(marker in quote_text for marker in KINSHIP_EXPRESSION_MARKERS)


def _resolve_kinship_abbreviation(
    *,
    old_resolution: Mapping[str, Any],
    candidate: Mapping[str, Any],
    catalog: Mapping[str, Mapping[str, Any]],
    exact_index: Mapping[str, Sequence[str]],
    local_contexts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    surface = str(old_resolution.get("surface") or candidate.get("counterpart_surface") or "")
    seed_id = str(old_resolution.get("seed_person_id") or candidate.get("person_a") or "")
    surname = str(catalog.get(seed_id, {}).get("surname") or "")
    normalized = surname + surface if surname else surface
    matches = list(exact_index.get(hng02.lookup(normalized), [])) if surname else []
    signal = {
        "signal": "kinship_family_surname_context",
        "seed_person_id": seed_id,
        "family_surname": surname or None,
        "abbreviated_surface": surface,
        "normalized_person_surface": normalized,
        "candidate_ids": matches,
    }
    if len(matches) == 1:
        pid = matches[0]
        return _base_identity_row(
            old_resolution=old_resolution,
            candidate=candidate,
            status="resolved_existing_person",
            method="kinship_context",
            resolved_person_id=pid,
            resolved_label=str(catalog[pid].get("canonical_name") or normalized),
            matches=matches,
            confidence="medium",
            note="abbreviated kin name resolved inside the seed family surname context",
            local_contexts=local_contexts,
            candidate_set=matches,
            context_signals=[signal],
        )
    if len(matches) > 1:
        return _base_identity_row(
            old_resolution=old_resolution,
            candidate=candidate,
            status="ambiguous_identity",
            method="ambiguous",
            matches=matches,
            confidence="low",
            note="kinship surname context has multiple canonical candidates",
            local_contexts=local_contexts,
            candidate_set=matches,
            context_signals=[signal],
        )
    if surname:
        return _base_identity_row(
            old_resolution=old_resolution,
            candidate=candidate,
            status="resolved_provisional_person",
            method="kinship_context",
            provisional_person_id=hng02.provisional_id(normalized),
            resolved_label=normalized,
            confidence="medium",
            note="family-local abbreviated name preserved provisionally; no canonical Person created",
            local_contexts=local_contexts,
            context_signals=[signal],
        )
    return _base_identity_row(
        old_resolution=old_resolution,
        candidate=candidate,
        status="unresolved_identity",
        method="unresolved",
        confidence="low",
        note="kinship abbreviation lacks a deterministic family surname context",
        local_contexts=local_contexts,
        context_signals=[signal],
    )


def _catalog_forms(person: Mapping[str, Any]) -> set[str]:
    forms: set[str] = set()
    for key in ("forms", "canonical_forms", "courtesy_forms", "alias_forms", "office_titles"):
        values = person.get(key, [])
        if isinstance(values, str):
            values = [values]
        if isinstance(values, Sequence):
            forms.update(hng02.lookup(value) for value in values if value)
    return forms


def _reject_spurious_compound(
    result: Mapping[str, Any],
    *,
    surface: str,
    catalog: Mapping[str, Mapping[str, Any]],
) -> bool:
    """Reject surname concatenations unsupported by the chosen Person forms.

    This prevents a kinship word such as 外祖 immediately before a full name
    from being read as the surname of an unrelated canonical person.
    """

    if result.get("note") != "contextual compound surface":
        return False
    pid = str(result.get("resolved_person_id") or "")
    if not pid or pid not in catalog:
        return True
    return hng02.lookup(surface) not in _catalog_forms(catalog[pid])


def _provisional_fallback(
    *,
    old_resolution: Mapping[str, Any],
    candidate: Mapping[str, Any],
    local_contexts: Sequence[Mapping[str, Any]],
    note: str,
) -> dict[str, Any]:
    surface = str(old_resolution.get("surface") or candidate.get("counterpart_surface") or candidate.get("subject_surface") or "")
    if len(hng02.lookup(surface)) >= 2:
        return _base_identity_row(
            old_resolution=old_resolution,
            candidate=candidate,
            status="resolved_provisional_person",
            method="biography_local_context",
            provisional_person_id=hng02.provisional_id(surface),
            resolved_label=surface,
            confidence="medium",
            note=note,
            local_contexts=local_contexts,
        )
    return _base_identity_row(
        old_resolution=old_resolution,
        candidate=candidate,
        status="unresolved_identity",
        method="unresolved",
        confidence="low",
        note=note,
        local_contexts=local_contexts,
    )


def replay_identity(
    *,
    old_resolution: Mapping[str, Any],
    projected_candidate: Mapping[str, Any],
    evidence: Mapping[str, Mapping[str, Any]],
    catalog: Mapping[str, Mapping[str, Any]],
    exact_index: Mapping[str, Sequence[str]],
    neighborhoods: Mapping[str, set[str]],
) -> dict[str, Any]:
    """Replay every resolver stage for one frozen HNG1 identity occurrence."""

    candidate, kind, surface_key = candidate_from_projection(projected_candidate, old_resolution)
    surface = str(old_resolution.get("surface") or candidate.get(surface_key) or "").strip()
    base_evidence, local_contexts = localize_evidence(candidate, evidence, expose_heading_to_resolver=False)
    contextual_evidence, _ = localize_evidence(candidate, evidence, expose_heading_to_resolver=True)

    if not surface or _is_generic_role(surface):
        return _base_identity_row(
            old_resolution=old_resolution,
            candidate=candidate,
            status="unresolved_identity",
            method="unresolved",
            confidence="low",
            note="generic role surface is not an independently identified person",
            local_contexts=local_contexts,
        )

    # A local family surname outranks generic suffix matching for abbreviated
    # names in explicit kinship expressions.
    if _kinship_abbreviation(candidate, kind=kind, surface=surface):
        return _resolve_kinship_abbreviation(
            old_resolution=old_resolution,
            candidate=candidate,
            catalog=catalog,
            exact_index=exact_index,
            local_contexts=local_contexts,
        )

    result = hng02.resolution_for_candidate(
        candidate,
        seed_profiles=catalog,
        evidence=base_evidence,
        catalog=catalog,
        exact_index=exact_index,
        surface_key=surface_key,
        allow_decorated=True,
    )
    if _reject_spurious_compound(result, surface=surface, catalog=catalog):
        result = _provisional_fallback(
            old_resolution=old_resolution,
            candidate=candidate,
            local_contexts=local_contexts,
            note="contextual compound rejected because the surface is not a form of the proposed Person",
        )

    # Short and abbreviated surfaces use the frozen HNG1R context scorer only
    # after exact/alias/courtesy/title/decorated/kinship/base-context stages.
    if result.get("resolution_status") in {"unresolved_identity", "resolved_provisional_person", "ambiguous_identity"} and len(hng02.lookup(surface)) <= 2:
        result = resolve_contextual_short_name(
            old_resolution=result,
            candidate=candidate,
            evidence=contextual_evidence,
            catalog=catalog,
            neighborhoods=neighborhoods,
        )

    result = copy.deepcopy(dict(result))
    result["candidate_id"] = str(old_resolution.get("candidate_id") or "")
    result["candidate_kind"] = old_resolution.get("candidate_kind")
    result["seed_person_id"] = old_resolution.get("seed_person_id")
    result["surface"] = surface
    result.setdefault("original_surface", surface)
    result.setdefault("candidate_set", list(result.get("matches", [])))
    result.setdefault("context_signals", [])
    result["local_resolver_context"] = local_contexts
    result["resolver_catalog"] = "build_hng0_2.person_catalog"
    result["resolver_version"] = RESOLVER_VERSION
    return result


def identity_signature(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in (
            "resolution_status", "resolution_method", "resolved_person_id",
            "provisional_person_id", "resolved_label", "confidence",
        )
    }


def project_relation(row: Mapping[str, Any], identity: Mapping[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(dict(row))
    status = str(identity.get("resolution_status") or "unresolved_identity")
    out["identity_resolution"] = copy.deepcopy(dict(identity))
    out["resolution_status"] = status
    out["resolution_matches"] = list(identity.get("matches", []))
    out["identity_replay_stage"] = "hng1r2"
    if status == "resolved_existing_person":
        endpoint = str(identity.get("resolved_person_id"))
        out["person_b"] = endpoint
        out["person_b_name"] = identity.get("resolved_label")
        out["provisional_neighbor_id"] = None
        out["provisional_neighbor_label"] = None
    else:
        label = str(identity.get("resolved_label") or identity.get("surface") or row.get("counterpart_surface") or "unresolved")
        provisional = identity.get("provisional_person_id") or hng02.provisional_id(label)
        endpoint = str(provisional)
        out["person_b"] = None
        out["person_b_name"] = None
        out["provisional_neighbor_id"] = provisional
        out["provisional_neighbor_label"] = label
    direction = out.get("direction") if isinstance(out.get("direction"), Mapping) else {}
    kind = str(direction.get("kind") or "undirected")
    seed = out.get("person_a")
    out["direction"] = {
        "kind": kind,
        "from": seed if kind == "seed_to_counterpart" else endpoint if kind == "counterpart_to_seed" else None,
        "to": endpoint if kind == "seed_to_counterpart" else seed if kind == "counterpart_to_seed" else None,
    }
    return out


def _merge_projection(target: dict[str, Any], row: Mapping[str, Any], *, id_key: str) -> None:
    for key in ("evidence_refs", "source_works", "source_forms", "source_witnesses", "candidate_ids"):
        target[key] = sorted(set(target.get(key, [])) | set(row.get(key, [])))
    quotes = {
        (str(item.get("ref")), str(item.get("quote")))
        for item in [*target.get("evidence_quotes", []), *row.get("evidence_quotes", [])]
        if isinstance(item, Mapping)
    }
    target["evidence_quotes"] = [{"ref": ref, "quote": quote} for ref, quote in sorted(quotes)]
    merged = set(target.get(f"merged_from_{id_key}s", [target.get(id_key)]))
    merged.update(row.get(f"merged_from_{id_key}s", [row.get(id_key)]))
    target[f"merged_from_{id_key}s"] = sorted(str(value) for value in merged if value)


def deduplicate_relations(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in sorted(rows, key=lambda item: str(item.get("relation_id"))):
        direction = row.get("direction") if isinstance(row.get("direction"), Mapping) else {}
        key = (
            str(row.get("person_a") or ""),
            str(row.get("person_b") or row.get("provisional_neighbor_id") or ""),
            str(row.get("normalized_relation_type") or row.get("relation_type") or ""),
            str(direction.get("kind") or "undirected"),
        )
        if key not in merged:
            merged[key] = copy.deepcopy(dict(row))
            merged[key]["merged_from_relation_ids"] = [row.get("relation_id")]
        else:
            _merge_projection(merged[key], row, id_key="relation_id")
    return sorted(merged.values(), key=lambda item: str(item.get("relation_id")))


def project_temporal(row: Mapping[str, Any], identity: Mapping[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(dict(row))
    status = str(identity.get("resolution_status") or "unresolved_identity")
    out["identity_resolution"] = copy.deepcopy(dict(identity))
    out["subject_resolution_status"] = status
    out["subject_matches"] = list(identity.get("matches", []))
    out["identity_replay_stage"] = "hng1r2"
    if status == "resolved_existing_person":
        out["person_id"] = identity.get("resolved_person_id")
        out["subject_label"] = identity.get("resolved_label")
        out["provisional_subject_id"] = None
    else:
        label = str(identity.get("resolved_label") or identity.get("surface") or row.get("subject_surface") or "unresolved")
        out["person_id"] = None
        out["subject_label"] = label
        out["provisional_subject_id"] = identity.get("provisional_person_id") or hng02.provisional_id(label)
    return out


def deduplicate_temporal(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in sorted(rows, key=lambda item: str(item.get("temporal_id"))):
        key = json.dumps({
            "person_id": row.get("person_id"),
            "provisional_subject_id": row.get("provisional_subject_id"),
            "temporal_type": row.get("temporal_type"),
            "claim": row.get("claim"),
            "temporal_scope": row.get("temporal_scope"),
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if key not in merged:
            merged[key] = copy.deepcopy(dict(row))
            merged[key]["merged_from_temporal_ids"] = [row.get("temporal_id")]
        else:
            _merge_projection(merged[key], row, id_key="temporal_id")
    return sorted(merged.values(), key=lambda item: str(item.get("temporal_id")))
