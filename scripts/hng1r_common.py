#!/usr/bin/env python3
"""Offline HNG1R contextual short-name resolution helpers.

This module deliberately sits after the frozen HNG1 projection.  It does not
call the model and it does not alter the HNG1 resolver or any source artifact.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import build_hng0_2 as hng02


ROOT = Path(__file__).resolve().parents[1]
HNG1_ROOT = ROOT / "data/generated/hng1"
HNG02R_ROOT = ROOT / "data/generated/hng0-2r"

GENERIC_ROLE_SURFACES = set(hng02.GENERIC_SURFACES) | {
    "客",
    "帝",
    "太子",
    "皇帝",
}

CONTEXTUAL_SHORT_RESOLVER_VERSION = "hng1r-contextual-short-name-v1"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def json_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_tree(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {
        str(path.relative_to(root)): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def hng1_hashes() -> dict[str, str]:
    return hash_tree(HNG1_ROOT)


def _surface_forms(person: Mapping[str, Any]) -> list[str]:
    values: set[str] = set()
    for key in ("canonical_forms", "forms", "courtesy_forms", "alias_forms", "office_titles"):
        raw = person.get(key, [])
        if isinstance(raw, str):
            raw = [raw]
        if isinstance(raw, Sequence):
            values.update(str(value).strip() for value in raw if str(value).strip())
    canonical = str(person.get("canonical_name") or "").strip()
    if canonical:
        values.add(canonical)
    return sorted(values, key=lambda value: (-len(hng02.lookup(value)), hng02.lookup(value), value))


def _candidate_catalog(catalog: Mapping[str, Mapping[str, Any]], surface: str) -> list[dict[str, Any]]:
    folded_surface = hng02.lookup(surface)
    candidates: dict[str, dict[str, Any]] = {}
    for pid, person in sorted(catalog.items()):
        matching_forms = [
            form for form in _surface_forms(person)
            if len(hng02.lookup(form)) > len(folded_surface)
            and hng02.lookup(form).endswith(folded_surface)
        ]
        if matching_forms:
            candidates[str(pid)] = {
                "person_id": str(pid),
                "canonical_name": person.get("canonical_name"),
                "matching_forms": matching_forms,
            }
    return [candidates[pid] for pid in sorted(candidates)]


def _strip_markup(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"\[\[([^]|]+)(?:\|[^]]+)?\]\]", r"\1", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    return text.strip()


def _headings(text: str) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    for match in re.finditer(r"(?m)^\s*(={2,6})\s*([^=\n]+?)\s*\1\s*$", text):
        value = _strip_markup(match.group(2))
        if value:
            result.append((match.start(), value))
    return result


def _local_context(original: str, quote: str, *, radius: int = 900) -> tuple[str, list[str]]:
    """Return a bounded context and nearest structural headings.

    The full source remains available in the evidence registry.  Matching is
    bounded around the quoted passage so a whole Wikisource volume cannot
    make unrelated biographies look like context.
    """

    if not original:
        return quote, []
    positions = [match.start() for match in re.finditer(re.escape(quote), original)] if quote else []
    center = positions[0] if positions else 0
    start = max(0, center - radius)
    end = min(len(original), center + max(len(quote), 1) + radius)
    headings = _headings(original)
    nearby = []
    for position, heading in headings:
        if position <= center:
            nearby.append((center - position, heading))
    nearby.sort(key=lambda item: item[0])
    return original[start:end], [heading for _, heading in nearby[:3]]


def evidence_context(
    candidate: Mapping[str, Any],
    evidence: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    refs = [str(ref) for ref in candidate.get("evidence_refs", []) if ref]
    if not refs:
        refs = [str(item.get("ref")) for item in candidate.get("evidence_quotes", []) if isinstance(item, Mapping) and item.get("ref")]
    quote_by_ref = {
        str(item.get("ref")): str(item.get("quote") or "")
        for item in candidate.get("evidence_quotes", [])
        if isinstance(item, Mapping) and item.get("ref")
    }
    local_texts: list[str] = []
    headings: list[str] = []
    title_values: list[str] = []
    records: list[dict[str, Any]] = []
    for ref in sorted(set(refs)):
        row = evidence.get(ref, {})
        if not isinstance(row, Mapping):
            continue
        locator = row.get("locator") if isinstance(row.get("locator"), Mapping) else {}
        for key in ("title", "section", "unit_title", "page_title"):
            value = _strip_markup(locator.get(key))
            if value:
                title_values.append(value)
        original = str(row.get("original_text") or "")
        local, local_headings = _local_context(original, quote_by_ref.get(ref, ""))
        local_texts.append(local)
        headings.extend(local_headings)
        snippet = str(row.get("model_snippet") or "")
        if snippet:
            local_texts.append(snippet)
        records.append({
            "evidence_ref": ref,
            "source_work": row.get("source_work"),
            "source_layer": row.get("source_layer"),
            "source_path": row.get("source_path"),
            "locator": dict(locator),
            "original_text": original,
            "model_snippet": snippet,
            "quote": quote_by_ref.get(ref, ""),
        })
    return {
        "refs": sorted(set(refs)),
        "records": records,
        "local_text": "\n".join(local_texts),
        "headings": sorted(set(headings)),
        "title_values": sorted(set(title_values)),
    }


def load_hng_neighborhoods() -> dict[str, set[str]]:
    """Load only already-known one-hop canonical neighbors.

    This is a context signal, not recursive expansion.  HNG1R never searches
    or researches a neighbor because it appears here.
    """

    neighborhoods: dict[str, set[str]] = {}
    paths = [
        HNG02R_ROOT / "normalized-relations.json",
        HNG1_ROOT / "relations.json",
    ]
    for path in paths:
        if not path.is_file():
            continue
        doc = read_json(path)
        rows = doc.get("relations", []) if isinstance(doc, Mapping) else []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            a = str(row.get("person_a") or "")
            b = str(row.get("person_b") or "")
            if a and b:
                neighborhoods.setdefault(a, set()).add(b)
                neighborhoods.setdefault(b, set()).add(a)
    return neighborhoods


def _candidate_signal(
    candidate: Mapping[str, Any],
    *,
    context: Mapping[str, Any],
    seed_id: str,
    neighborhoods: Mapping[str, set[str]],
    temporal_compatible: bool,
) -> dict[str, Any]:
    pid = str(candidate["person_id"])
    forms = [str(value) for value in candidate.get("matching_forms", [])]
    canonical = str(candidate.get("canonical_name") or "")
    local_text = hng02.lookup(context.get("local_text", ""))
    headings = [hng02.lookup(value) for value in context.get("headings", [])]
    titles = [hng02.lookup(value) for value in context.get("title_values", [])]
    all_forms = [hng02.lookup(value) for value in [canonical, *forms] if value]
    title_hits = sorted({value for value in all_forms if any(value and value in heading for heading in headings)})
    source_title_hits = sorted({value for value in all_forms if any(value and value in title for title in titles)})
    explicit_hits = sorted({value for value in all_forms if value and value in local_text})
    current_seed = pid == seed_id
    neighborhood = pid in neighborhoods.get(seed_id, set())
    signals: list[str] = []
    if title_hits:
        signals.append("biography_title")
    if source_title_hits:
        signals.append("source_unit_title")
    if explicit_hits:
        signals.append("explicit_full_name")
    if current_seed:
        signals.append("current_seed")
    if neighborhood:
        signals.append("hng_one_hop_neighborhood")
    if temporal_compatible:
        signals.append("temporal_compatible")
    # Structural title/heading evidence outranks a mere mention.  The tuple
    # remains deterministic and is retained in the audit output.
    rank = (
        1 if title_hits else 0,
        1 if source_title_hits else 0,
        1 if explicit_hits else 0,
        1 if current_seed else 0,
        1 if neighborhood else 0,
        1 if temporal_compatible else 0,
    )
    return {
        "person_id": pid,
        "canonical_name": canonical,
        "matching_forms": forms,
        "signals": signals,
        "signal_details": {
            "biography_title": title_hits,
            "source_unit_title": source_title_hits,
            "explicit_full_name": explicit_hits,
            "current_seed": current_seed,
            "hng_one_hop_neighborhood": neighborhood,
            "temporal_compatible": temporal_compatible,
        },
        "rank": list(rank),
    }


def resolve_contextual_short_name(
    *,
    old_resolution: Mapping[str, Any],
    candidate: Mapping[str, Any],
    evidence: Mapping[str, Mapping[str, Any]],
    catalog: Mapping[str, Mapping[str, Any]],
    neighborhoods: Mapping[str, set[str]],
) -> dict[str, Any]:
    """Apply the single HNG1R contextual short-name stage.

    Existing HNG1 decisions are frozen.  Only unresolved/provisional short
    surfaces enter this function; all other records are copied unchanged.
    """

    row = copy.deepcopy(dict(old_resolution))
    surface = str(old_resolution.get("surface") or candidate.get("counterpart_surface") or candidate.get("subject_surface") or "").strip()
    row.setdefault("original_surface", surface)
    row.setdefault("candidate_set", [])
    row.setdefault("context_signals", [])
    if old_resolution.get("resolution_status") not in {"unresolved_identity", "resolved_provisional_person", "ambiguous_identity"}:
        return row
    if len(hng02.lookup(surface)) > 2 or hng02.lookup(surface) in {hng02.lookup(value) for value in GENERIC_ROLE_SURFACES}:
        return row

    candidates = _candidate_catalog(catalog, surface)
    row["candidate_set"] = [str(item["person_id"]) for item in candidates]
    if not candidates:
        return row

    context = evidence_context(candidate, evidence)
    seed_id = str(old_resolution.get("seed_person_id") or candidate.get("person_a") or candidate.get("person_id") or "")
    temporal_warnings = [str(value) for value in candidate.get("temporal_warnings", []) if value]
    temporal_compatible = not any("conflict" in value.lower() or "impossible" in value.lower() for value in temporal_warnings)
    scored = [
        _candidate_signal(
            item,
            context=context,
            seed_id=seed_id,
            neighborhoods=neighborhoods,
            temporal_compatible=temporal_compatible,
        )
        for item in candidates
    ]
    row["context_signals"] = scored
    compatible = [item for item in scored if any(item["rank"][:5])]
    if not compatible:
        return row
    best_rank = max(tuple(item["rank"]) for item in compatible)
    best = [item for item in compatible if tuple(item["rank"]) == best_rank]
    if len(best) != 1:
        row.update({
            "resolution_status": "ambiguous_identity",
            "resolution_method": "ambiguous",
            "resolved_person_id": None,
            "resolved_label": None,
            "provisional_person_id": None,
            "matches": [str(item["person_id"]) for item in best],
            "confidence": "low",
            "note": "context-compatible short-name candidates remain tied",
        })
        return row

    chosen = best[0]
    if not chosen["signals"] or chosen["rank"][:5] == [0, 0, 0, 0, 0]:
        return row
    strong = set(chosen["signals"]) & {
        "biography_title", "source_unit_title", "explicit_full_name",
        "current_seed", "hng_one_hop_neighborhood",
    }
    if not strong:
        return row
    confidence = "high" if {"biography_title", "explicit_full_name"} & strong else "medium"
    row.update({
        "resolution_status": "resolved_existing_person",
        "resolution_method": "contextual_short_name",
        "resolved_person_id": chosen["person_id"],
        "resolved_label": chosen["canonical_name"],
        "provisional_person_id": None,
        "matches": [chosen["person_id"]],
        "confidence": confidence,
        "normalized_person_surface": chosen["canonical_name"],
        "note": "unique context-compatible suffix candidate",
    })
    return row


def candidate_from_projection(row: Mapping[str, Any], *, kind: str) -> dict[str, Any]:
    candidate = dict(row)
    if kind == "relation":
        candidate["person_a"] = row.get("person_a")
        candidate["counterpart_surface"] = row.get("counterpart_surface")
    else:
        candidate["person_id"] = row.get("person_id") or row.get("identity_resolution", {}).get("seed_person_id")
        candidate["subject_surface"] = row.get("subject_surface")
    return candidate


def apply_identity_to_relation(row: Mapping[str, Any], identity: Mapping[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(dict(row))
    old_identity = out.get("identity_resolution") if isinstance(out.get("identity_resolution"), Mapping) else {}
    out["identity_resolution"] = copy.deepcopy(dict(identity))
    out["resolution_status"] = identity.get("resolution_status")
    out["resolution_matches"] = list(identity.get("matches", []))
    out["person_b"] = identity.get("resolved_person_id") or (old_identity.get("resolved_person_id") if old_identity else out.get("person_b"))
    out["person_b_name"] = identity.get("resolved_label") or (old_identity.get("resolved_label") if old_identity else out.get("person_b_name"))
    if identity.get("resolution_status") == "resolved_existing_person":
        out["provisional_neighbor_id"] = None
        out["provisional_neighbor_label"] = None
    elif identity.get("resolution_status") == "ambiguous_identity":
        out["person_b"] = None
        out["person_b_name"] = None
        out["provisional_neighbor_id"] = out.get("provisional_neighbor_id") or old_identity.get("provisional_person_id")
        out["provisional_neighbor_label"] = identity.get("surface")
    return out


def apply_identity_to_temporal(row: Mapping[str, Any], identity: Mapping[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(dict(row))
    out["identity_resolution"] = copy.deepcopy(dict(identity))
    out["subject_resolution_status"] = identity.get("resolution_status")
    out["subject_matches"] = list(identity.get("matches", []))
    if identity.get("resolution_status") == "resolved_existing_person":
        out["person_id"] = identity.get("resolved_person_id")
        out["subject_label"] = identity.get("resolved_label")
        out["provisional_subject_id"] = None
    elif identity.get("resolution_status") == "ambiguous_identity":
        out["person_id"] = None
        out["subject_label"] = None
    return out


def relation_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    direction = row.get("direction") if isinstance(row.get("direction"), Mapping) else {}
    return (
        str(row.get("person_a") or ""),
        str(row.get("person_b") or row.get("provisional_neighbor_id") or ""),
        str(row.get("normalized_relation_type") or row.get("relation_type") or ""),
        str(direction.get("kind") or "undirected"),
    )


def merge_relation_rows(target: dict[str, Any], row: Mapping[str, Any]) -> None:
    for key in ("evidence_refs", "source_works", "source_forms", "source_witnesses", "candidate_ids"):
        target[key] = sorted(set(target.get(key, [])) | set(row.get(key, [])))
    quotes = {(str(item.get("ref")), str(item.get("quote"))) for item in target.get("evidence_quotes", []) if isinstance(item, Mapping)}
    quotes.update((str(item.get("ref")), str(item.get("quote"))) for item in row.get("evidence_quotes", []) if isinstance(item, Mapping))
    target["evidence_quotes"] = [{"ref": ref, "quote": quote} for ref, quote in sorted(quotes)]
    merged_from = set(target.get("merged_from_relation_ids", [target.get("relation_id")]))
    merged_from.update(row.get("merged_from_relation_ids", [row.get("relation_id")]))
    target["merged_from_relation_ids"] = sorted(str(value) for value in merged_from if value)


def unique_relation_projection(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in sorted(rows, key=lambda value: str(value.get("relation_id"))):
        key = relation_key(row)
        if key not in merged:
            merged[key] = copy.deepcopy(dict(row))
            merged[key].setdefault("merged_from_relation_ids", [row.get("relation_id")])
        else:
            merge_relation_rows(merged[key], row)
    return sorted(merged.values(), key=lambda row: str(row.get("relation_id")))


def readiness(review_rows: Sequence[Mapping[str, Any]], resolutions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    judgments = [str(row.get("review") or "not_reviewed") for row in review_rows]
    reviewed = [value for value in judgments if value != "not_reviewed"]
    false_merges = judgments.count("false_merge")
    uncertain = judgments.count("uncertain")
    total = len(resolutions)
    status_counts: dict[str, int] = {}
    for row in resolutions:
        status = str(row.get("resolution_status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "schema": 1,
        "stage": "hng1r-hng2-readiness",
        "canonical_write_back": False,
        "reviewed_identity_count": len(reviewed),
        "audit_identity_count": len(review_rows),
        "false_merge_count": false_merges,
        "false_merge_rate": (false_merges / len(reviewed)) if reviewed else None,
        "uncertain_count": uncertain,
        "unresolved_rate": status_counts.get("unresolved_identity", 0) / total if total else 0,
        "provisional_rate": status_counts.get("resolved_provisional_person", 0) / total if total else 0,
        "ambiguous_rate": status_counts.get("ambiguous_identity", 0) / total if total else 0,
        "status_counts": dict(sorted(status_counts.items())),
        "ready_for_hng2": False,
        "readiness_status": "awaiting_meaningful_human_audit",
        "reason": "HNG1R supplies review records but does not auto-populate human judgments",
    }
