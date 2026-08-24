#!/usr/bin/env python3
"""Build the HNG2 hybrid resolver and two-wave research projection.

HNG2 is a generated research layer.  The default runner is deliberately
offline: it replays immutable HNG1R2 evidence, uses local punctuated-first
retrieval for frontier accounting, and calls no model when deterministic
resolution is sufficient.  ``--allow-llm`` only records residual cases for a
future constrained identity-assist call; it never promotes a model answer to
canonical history.
"""

from __future__ import annotations

import argparse
import collections
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_hng0_2 as hng02  # noqa: E402
from hng0_1_common import (  # noqa: E402
    _load_jinshu_units,
    _load_jianshu_units,
    _load_shishuo_units,
    _load_sgz_units,
    _load_ztj_units,
    sha256_file,
    stable_hash,
    write_json,
)
from hng1_common import open_short_hits  # noqa: E402
from historical_entity_resolver import (  # noqa: E402
    RESOLVER_VERSION,
    build_contextual_identity_registry,
    catalog_forms,
    forms_index,
    frontier_state,
    graph_support,
    is_generic_role,
    matching_normalize,
    person_catalog,
    resolve_identity,
    stable_hash as resolver_hash,
    temporal_gate,
)

OUTPUT_ROOT = ROOT / "data/generated/hng2"
REVIEW_PATH = ROOT / "data/annotation/hng2-review.json"
HNG1R2_ROOT = ROOT / "data/generated/hng1r2"
HNG1R2_IDENTITY = HNG1R2_ROOT / "identity-resolution.json"
HNG1R2_RELATIONS = HNG1R2_ROOT / "relations.json"
HNG1R2_TEMPORAL = HNG1R2_ROOT / "temporal-items.json"
HNG0_CANDIDATES = ROOT / "data/generated/hng0/hng0-candidates.json"
HNG0_REVIEW = ROOT / "data/annotation/hng0-review.json"

OUTPUT_FILES = [
    "frontier-selection.json", "frontier-wave-1.json", "frontier-wave-2.json",
    "retrieval-trace.json", "temporal-gate-decisions.json", "identity-resolution.json",
    "contextual-identity-registry.json",
    "identity-llm-assist.json", "identity-graph-support.json", "provisional-persons.json",
    "consolidation-candidates.json", "relations.json", "temporal-items.json", "neighborhoods.json",
    "rejected-passages.json", "unresolved-identities.json", "ambiguous-identities.json",
    "audit-sample.json", "metrics.json", "manifest.json",
]

HARD_RELATIONS = {
    "parent_child", "grandparent_grandchild", "sibling", "uncle_nephew", "cousin_clan_kin",
    "marriage", "affinal_relation", "same_clan", "superior_subordinate", "recruitment_served_under", "teacher_student",
}
DOCUMENTED_LEVELS = {"documented_interaction"}


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def hash_tree(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {str(p.relative_to(root)): sha256_file(p) for p in sorted(root.rglob("*")) if p.is_file()}


def _person_profiles(catalog: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for pid, person in sorted(catalog.items()):
        profiles[pid] = {
            "person_id": pid,
            "canonical_name": person.get("canonical_name"),
            "surname": person.get("surname"),
            "forms": catalog_forms(person),
            "courtesy_forms": list(person.get("courtesy_forms", [])),
            "aliases": list(person.get("alias_forms", [])),
            "office_titles": list(person.get("office_titles", [])),
            "dynasty": "",
            "temporal_context": "",
            "frontier_origin": "canonical_person",
        }
    return profiles


def _source_evidence() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in (HNG1R2_RELATIONS, HNG1R2_TEMPORAL):
        doc = read_json(path, {}) or {}
        for ref, row in (doc.get("evidence", {}) or {}).items():
            if isinstance(row, Mapping):
                result[str(ref)] = dict(row)
    return result


def _hng0_accepted_edges() -> list[dict[str, Any]]:
    candidates = read_json(HNG0_CANDIDATES, {}) or {}
    review = read_json(HNG0_REVIEW, {}) or {}
    decisions = review.get("relation_decisions", {}) if isinstance(review, Mapping) else {}
    result: list[dict[str, Any]] = []
    for row in candidates.get("relations", []):
        if not isinstance(row, Mapping):
            continue
        rid = str(row.get("relation_id") or "")
        status = str((decisions.get(rid) or {}).get("review_status") or row.get("review_status") or "candidate")
        if status != "accepted":
            continue
        result.append({**dict(row), "review_status": "accepted", "independent_source": "hng0-review"})
    return sorted(result, key=lambda x: str(x.get("relation_id")))


def _seed_profile(catalog: Mapping[str, Mapping[str, Any]], pid: str) -> dict[str, Any]:
    return dict(catalog.get(pid) or {"person_id": pid, "canonical_name": pid, "surname": ""})


def _row_refs(row: Mapping[str, Any]) -> list[str]:
    refs = [str(x) for x in row.get("evidence_refs", []) if x]
    if not refs:
        refs = [str(x.get("ref")) for x in row.get("evidence_quotes", []) if isinstance(x, Mapping) and x.get("ref")]
    return sorted(set(refs))


def _row_quotes(row: Mapping[str, Any]) -> list[dict[str, str]]:
    result = []
    for item in row.get("evidence_quotes", []):
        if isinstance(item, Mapping) and item.get("ref") and item.get("quote"):
            result.append({"ref": str(item["ref"]), "quote": str(item["quote"])})
    return sorted(set((item["ref"], item["quote"]) for item in result)) and [
        {"ref": ref, "quote": quote} for ref, quote in sorted(set((item["ref"], item["quote"]) for item in result))
    ] or []


def _valid_evidence(row: Mapping[str, Any], evidence: Mapping[str, Mapping[str, Any]]) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    valid: list[dict[str, str]] = []
    failures: list[dict[str, Any]] = []
    quotes = _row_quotes(row)
    for item in quotes:
        ref, quote = item["ref"], item["quote"]
        source = evidence.get(ref, {})
        original = str(source.get("original_text") or "") if isinstance(source, Mapping) else ""
        if not original:
            failures.append({"ref": ref, "quote": quote, "reason": "missing_original_source_text"})
        elif quote not in original:
            failures.append({"ref": ref, "quote": quote, "reason": "quote_not_exact_substring"})
        else:
            valid.append(item)
    for ref in _row_refs(row):
        if ref not in evidence:
            failures.append({"ref": ref, "reason": "unknown_evidence_ref"})
    return valid, failures


def _evidence_context(refs: Sequence[str], quotes: Sequence[Mapping[str, Any]], evidence: Mapping[str, Mapping[str, Any]]) -> str:
    bits: list[str] = []
    for ref in sorted(set(str(x) for x in refs)):
        source = evidence.get(ref, {})
        if isinstance(source, Mapping):
            bits.append(str(source.get("original_text") or ""))
    bits.extend(str(item.get("quote") or "") for item in quotes if isinstance(item, Mapping))
    return "\n".join(x for x in bits if x)


def _gate_for_row(row: Mapping[str, Any], seed: Mapping[str, Any], evidence: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    refs = _row_refs(row)
    decisions: list[dict[str, Any]] = []
    statuses: list[str] = []
    for ref in refs:
        source = dict(evidence.get(ref) or {})
        source["evidence_ref"] = ref
        gate = temporal_gate(seed, source)
        gate = {"evidence_ref": ref, **gate}
        decisions.append(gate)
        statuses.append(str(gate.get("status")))
    if "conflict" in statuses:
        return {"status": "conflict", "reason": "at least one evidence passage conflicts with seed chronology", "decisions": decisions}, decisions
    if statuses and all(x == "compatible" for x in statuses):
        return {"status": "compatible", "reason": "all checked evidence is compatible", "decisions": decisions}, decisions
    return {"status": "unknown", "reason": "no deterministic conflict", "decisions": decisions}, decisions


def _identity_input(row: Mapping[str, Any], kind: str) -> tuple[str, str]:
    if kind == "relation":
        return str(row.get("counterpart_surface") or ""), str(row.get("person_a") or "")
    return str(row.get("subject_surface") or ""), str(row.get("person_id") or row.get("seed_person_id") or "")


def _identity_record(row: Mapping[str, Any], kind: str, resolution: Mapping[str, Any], gate: Mapping[str, Any], wave: int, source_forms: Sequence[str]) -> dict[str, Any]:
    return {
        "occurrence_id": str(row.get("relation_id") or row.get("temporal_id") or row.get("candidate_ids", [""])[0]),
        "candidate_kind": kind,
        "seed_person_id": row.get("person_a") or row.get("person_id") or row.get("seed_person_id"),
        "surface": row.get("counterpart_surface") if kind == "relation" else row.get("subject_surface"),
        "resolution": copy.deepcopy(dict(resolution)),
        "temporal_gate": copy.deepcopy(dict(gate)),
        "wave": wave,
        "source_forms": sorted(set(str(x) for x in source_forms if x)),
        "evidence_refs": _row_refs(row),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _project_relation(row: Mapping[str, Any], identity: Mapping[str, Any], valid_quotes: Sequence[Mapping[str, Any]], gate: Mapping[str, Any], graph: Mapping[str, Any], wave: int) -> dict[str, Any] | None:
    seed = str(row.get("person_a") or "")
    if not seed:
        return None
    status = str(identity.get("resolution_status") or "unresolved")
    endpoint = str(identity.get("resolved_person_id") or "") if status == "resolved_existing_person" else ""
    provisional = str(identity.get("provisional_person_id") or "") if not endpoint else ""
    label = str(identity.get("resolved_label") or identity.get("surface") or row.get("counterpart_surface") or "")
    if endpoint == seed:
        return None
    relation_type = str(row.get("normalized_relation_type") or row.get("relation_type") or "documented_social_interaction")
    level = str(row.get("semantic_level") or ("hard_relation" if relation_type in HARD_RELATIONS else "documented_interaction"))
    direction = row.get("direction") if isinstance(row.get("direction"), Mapping) else {"kind": "undirected"}
    kind = str(direction.get("kind") or "undirected")
    key = (seed, endpoint or provisional, relation_type, kind)
    return {
        "relation_id": f"hng2-relation-{resolver_hash(key)[:20]}",
        "person_a": seed,
        "person_b": endpoint or None,
        "person_b_name": row.get("person_b_name") if endpoint else None,
        "provisional_neighbor_id": provisional or None,
        "provisional_neighbor_label": label if provisional else None,
        "unresolved_neighbor_surface": label if not endpoint and not provisional else None,
        "counterpart_surface": row.get("counterpart_surface"),
        "relation_type": relation_type,
        "normalized_relation_type": relation_type,
        "original_relation_type": row.get("original_relation_type") or row.get("relation_type"),
        "semantic_level": level,
        "direction": {"kind": kind, "from": seed if kind == "seed_to_counterpart" else endpoint or provisional if kind == "counterpart_to_seed" else None, "to": endpoint or provisional if kind == "seed_to_counterpart" else seed if kind == "counterpart_to_seed" else None},
        "temporal_scope": row.get("temporal_scope", {}),
        "certainty": row.get("certainty") or "low",
        "historical_verification_open": True,
        "claim": row.get("claim") or "",
        "evidence_refs": sorted(set(str(x.get("ref")) for x in valid_quotes if x.get("ref"))),
        "evidence_quotes": [dict(x) for x in valid_quotes],
        "source_works": sorted(set(str(x) for x in row.get("source_works", []) if x)),
        "source_forms": sorted(set(str(x) for x in row.get("source_forms", []) if x) or {"legacy_local"}),
        "source_witnesses": sorted(set(str(x) for x in row.get("source_witnesses", []) if x)),
        "extraction_method": row.get("extraction_method") or "hng1r2-frozen-candidate",
        "origin": "hng2-frozen-evidence-replay",
        "review_status": "candidate",
        "source_review_status": "candidate_model_output",
        "one_hop_only": True,
        "wave": wave,
        "identity_resolution": copy.deepcopy(dict(identity)),
        "temporal_gate": copy.deepcopy(dict(gate)),
        "graph_support": copy.deepcopy(dict(graph)),
        "evidence_basis": "exact_quote_validated_candidate",
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _merge_relations(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in sorted(rows, key=lambda x: str(x.get("relation_id"))):
        direction = row.get("direction") if isinstance(row.get("direction"), Mapping) else {}
        key = (str(row.get("person_a") or ""), str(row.get("person_b") or row.get("provisional_neighbor_id") or ""), str(row.get("normalized_relation_type") or ""), str(direction.get("kind") or "undirected"))
        if key not in merged:
            merged[key] = copy.deepcopy(dict(row))
            merged[key]["merged_from_relation_ids"] = [row.get("relation_id")]
            continue
        target = merged[key]
        target["evidence_refs"] = sorted(set(target.get("evidence_refs", [])) | set(row.get("evidence_refs", [])))
        target["evidence_quotes"] = sorted({(str(x.get("ref")), str(x.get("quote"))) for x in [*target.get("evidence_quotes", []), *row.get("evidence_quotes", [])] if isinstance(x, Mapping)})
        target["evidence_quotes"] = [{"ref": ref, "quote": quote} for ref, quote in target["evidence_quotes"]]
        for field in ("source_works", "source_forms", "source_witnesses", "merged_from_relation_ids"):
            target[field] = sorted(set(target.get(field, [])) | set(row.get(field, [])))
        if row.get("claim") and row.get("claim") != target.get("claim"):
            target.setdefault("claim_variants", []).append(row.get("claim"))
            target["claim_variants"] = sorted(set(target["claim_variants"]))
    return sorted(merged.values(), key=lambda x: str(x.get("relation_id")))


def _project_temporal(row: Mapping[str, Any], identity: Mapping[str, Any], valid_quotes: Sequence[Mapping[str, Any]], gate: Mapping[str, Any], wave: int) -> dict[str, Any]:
    status = str(identity.get("resolution_status") or "unresolved")
    pid = str(identity.get("resolved_person_id") or "") if status == "resolved_existing_person" else None
    provisional = None if pid else str(identity.get("provisional_person_id") or f"hng2-provisional-{resolver_hash(row.get('subject_surface'))[:20]}")
    return {
        "temporal_id": f"hng2-time-{resolver_hash((pid or provisional, row.get('temporal_type'), row.get('claim'), row.get('temporal_scope', {})))[:20]}",
        "person_id": pid,
        "provisional_subject_id": provisional,
        "subject_surface": row.get("subject_surface"),
        "subject_label": identity.get("resolved_label") or row.get("subject_label") or row.get("subject_surface"),
        "subject_resolution_status": status,
        "temporal_type": row.get("temporal_type"),
        "claim": row.get("claim") or "",
        "temporal_scope": row.get("temporal_scope", {}),
        "precision": row.get("precision") or "unknown",
        "certainty": row.get("certainty") or "low",
        "historical_verification_open": True,
        "evidence_refs": sorted(set(str(x.get("ref")) for x in valid_quotes if x.get("ref"))),
        "evidence_quotes": [dict(x) for x in valid_quotes],
        "source_works": sorted(set(str(x) for x in row.get("source_works", []) if x)),
        "source_forms": sorted(set(str(x) for x in row.get("source_forms", []) if x) or {"legacy_local"}),
        "source_witnesses": sorted(set(str(x) for x in row.get("source_witnesses", []) if x)),
        "extraction_method": row.get("extraction_method") or "hng1r2-frozen-candidate",
        "origin": "hng2-frozen-evidence-replay",
        "review_status": "candidate",
        "one_hop_only": True,
        "wave": wave,
        "identity_resolution": copy.deepcopy(dict(identity)),
        "temporal_gate": copy.deepcopy(dict(gate)),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _profiles_for_frontier(catalog: Mapping[str, Mapping[str, Any]], ids: Sequence[str], provisional: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    provisional = provisional or {}
    profiles: dict[str, dict[str, Any]] = {}
    for pid in sorted(set(str(x) for x in ids if x)):
        if pid in catalog:
            profiles[pid] = dict(catalog[pid])
        elif pid in provisional:
            item = provisional[pid]
            profiles[pid] = {
                "person_id": pid,
                "canonical_name": item.get("label"),
                "surname": str(item.get("label") or "")[:1],
                "forms": [item.get("label")],
                "courtesy_forms": [], "alias_forms": [], "office_titles": [],
                "frontier_origin": "hng1r2_provisional",
            }
    return profiles


def _prepare_search_units(units: Sequence[Mapping[str, Any]]) -> list[tuple[Mapping[str, Any], str]]:
    """Fold each local unit once instead of once per frontier Person."""

    return [(unit, hng02.lookup(str(unit.get("text") or ""))) for unit in units]


def _fast_find(profile: Mapping[str, Any], prepared: Sequence[tuple[Mapping[str, Any], str]], *, top_k: int, punctuated_first: bool) -> list[dict[str, Any]]:
    terms = []
    for value in [*profile.get("search_terms_original", []), profile.get("canonical_name")]:
        value = str(value or "").strip()
        folded = hng02.lookup(value)
        if folded and len(folded) >= 2:
            terms.append((value, folded))
    # Longest terms make exact-name hits deterministic and avoid noisy one-
    # character title matches.
    unique_terms = sorted({(raw, folded) for raw, folded in terms}, key=lambda x: (-len(x[1]), x[1], x[0]))
    scored: list[dict[str, Any]] = []
    canonical = hng02.lookup(str(profile.get("canonical_name") or ""))
    for unit, folded_text in prepared:
        hits = [raw for raw, folded in unique_terms if folded in folded_text]
        if not hits:
            continue
        exact_name = bool(canonical and canonical in folded_text)
        relation_hits = sum(1 for term in ("父", "子", "祖", "孫", "友善", "親善", "辟", "引", "討", "攻", "謀", "舉兵") if term in str(unit.get("text") or ""))
        score = len(hits) * 10 + (35 if exact_name else 0) + min(relation_hits, 8) * 2
        if unit.get("source_form") == "punctuated" and punctuated_first:
            score += 20
        if unit.get("work") == "晉書" and "biography" in str((unit.get("locator") or {}).get("category") or ""):
            score += 8
        scored.append({
            "source_ref": unit.get("source_ref"), "work": unit.get("work"), "source_layer": unit.get("source_layer"),
            "source_form": unit.get("source_form"), "locator": unit.get("locator", {}), "matched_terms": hits,
            "score": score, "text_chars": len(str(unit.get("text") or "")),
        })
    scored.sort(key=lambda x: (-int(x["score"]), 0 if x.get("source_form") == "punctuated" and punctuated_first else 1, str(x.get("work")), str(x.get("source_ref"))))
    return scored[: max(1, min(8, int(top_k)))]


def _run_retrieval(frontier_rows: Sequence[Mapping[str, Any]], profiles: Mapping[str, Mapping[str, Any]], punctuated: Sequence[Mapping[str, Any]], legacy: Sequence[Mapping[str, Any]], wave: int, prepared_punctuated: Sequence[tuple[Mapping[str, Any], str]], prepared_legacy: Sequence[tuple[Mapping[str, Any], str]]) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    for row in sorted(frontier_rows, key=lambda x: str(x.get("frontier_id") or x.get("person_id"))):
        pid = str(row.get("person_id") or row.get("frontier_id") or "")
        profile = dict(profiles.get(pid) or {})
        forms = [str(x) for x in profile.get("forms", []) if len(matching_normalize(x)) >= 2]
        profile.update({
            "person_id": pid,
            "search_terms_original": sorted(set(forms), key=lambda x: (-len(matching_normalize(x)), x))[:12],
            "search_terms_normalized": sorted(set(matching_normalize(x) for x in forms if matching_normalize(x)))[:12],
        })
        try:
            # Avoid rescanning the very large legacy 通鑑 projection when the
            # punctuated reference already supplies hits.  This is the same
            # punctuated-first policy as HNG1, with a lazy legacy fallback.
            p_hits = _fast_find(profile, prepared_punctuated, punctuated_first=True, top_k=3)
            l_hits = [] if p_hits else _fast_find(profile, prepared_legacy, punctuated_first=False, top_k=3)
            found = {
                "hits": [{**dict(x), "source_form": x.get("source_form") or "punctuated"} for x in (p_hits or l_hits)],
                "routes": [], "fallback_used": not bool(p_hits),
            }
            opened = open_short_hits(found, punctuated, legacy, max_passages=3)
        except Exception as exc:  # local source anomalies are recorded, not model failures
            traces.append({
                "wave": wave, "frontier_id": pid, "person_id": pid, "searched_corpora": [],
                "retrieved_refs": [], "opened_refs": [], "used_refs": [], "new_used_refs": [],
                "rejected_by_temporal_gate": [], "rejected_by_seed_identity_gate": [],
                "source_forms": [], "error": {"class": type(exc).__name__, "message": str(exc)},
            })
            continue
        retrieved = [str(x.get("source_ref")) for x in found.get("hits", []) if x.get("source_ref")]
        opened_records = []
        for item in opened:
            snippet = str(item.get("snippet") or item.get("text") or "")
            opened_records.append({
                "ref": item.get("source_ref"),
                "source_form": item.get("source_form"),
                "work": item.get("work"),
                "excerpt": snippet[:520],
                "char_count": len(snippet),
            })
        routes = found.get("routes", [])
        traces.append({
            "wave": wave, "frontier_id": pid, "person_id": pid,
            "searched_corpora": sorted(set(str(x.get("work") or x.get("source_work") or "") for x in [*punctuated, *legacy] if x.get("work") or x.get("source_work"))),
            "routes": routes,
            "retrieved_refs": retrieved,
            "opened_refs": [str(x.get("ref")) for x in opened_records if x.get("ref")],
            "opened": opened_records,
            # Retrieval itself does not assert a relation.  The only used
            # evidence below comes from validated frozen candidate quotes.
            "used_refs": [], "new_used_refs": [],
            "rejected_by_temporal_gate": [], "rejected_by_seed_identity_gate": [],
            "source_forms": sorted(set(str(x.get("source_form")) for x in opened_records if x.get("source_form"))),
            "fallback_used": bool(found.get("fallback_used")),
            "retrieved_count": len(retrieved), "opened_count": len(opened_records),
            "opened_chars": sum(int(x.get("char_count") or 0) for x in opened_records),
        })
    return traces


def _provisional_summary(relations: Sequence[Mapping[str, Any]], identities: Sequence[Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    by_id = {str(row.get("occurrence_id")): row for row in identities}
    records: dict[str, dict[str, Any]] = {}
    for row in relations:
        pid = str(row.get("provisional_neighbor_id") or "")
        if not pid:
            continue
        identity = row.get("identity_resolution") if isinstance(row.get("identity_resolution"), Mapping) else {}
        item = records.setdefault(pid, {
            "provisional_person_id": pid,
            "label": row.get("provisional_neighbor_label") or row.get("counterpart_surface"),
            "evidence_refs": [], "source_works": [], "relation_ids": [], "hard_relation_count": 0,
            "interaction_count": 0, "identity_occurrences": [], "canonical_write_back": False,
        })
        item["evidence_refs"] = sorted(set(item["evidence_refs"]) | set(row.get("evidence_refs", [])))
        item["source_works"] = sorted(set(item["source_works"]) | set(row.get("source_works", [])))
        item["relation_ids"].append(row.get("relation_id"))
        if row.get("semantic_level") == "hard_relation": item["hard_relation_count"] += 1
        if row.get("semantic_level") == "documented_interaction": item["interaction_count"] += 1
        item["identity_occurrences"].append(row.get("relation_id"))
        item["identity"] = identity
    for item in records.values():
        identity = item.get("identity") or {"resolution_status": "provisional", "resolved_label": item.get("label")}
        item["frontier_state"] = frontier_state(
            identity,
            evidence_traceable=bool(item["evidence_refs"]),
            no_temporal_conflict=True,
            hard_relation_count=int(item["hard_relation_count"]),
            interaction_count=int(item["interaction_count"]),
            direct_source_hit=bool(item["source_works"]),
        )
        item["relation_ids"] = sorted(set(item["relation_ids"]))
        item["identity_occurrences"] = sorted(set(item["identity_occurrences"]))
    return {key: records[key] for key in sorted(records)}


def _frontier_selection(catalog: Mapping[str, Mapping[str, Any]], provisional: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    for pid, person in sorted(catalog.items()):
        rows.append({
            "frontier_id": pid, "person_id": pid, "label": person.get("canonical_name"),
            "frontier_state": "eligible_frontier", "wave": 0, "origin": "canonical_person",
            "eligibility_basis": ["canonical_existing_person"], "one_hop_only": True,
        })
    for pid, item in sorted(provisional.items()):
        if item.get("frontier_state") != "eligible_frontier":
            continue
        rows.append({
            "frontier_id": pid, "person_id": None, "provisional_person_id": pid, "label": item.get("label"),
            "frontier_state": "eligible_frontier", "wave": 0, "origin": "hng1r2_high_confidence_provisional",
            "eligibility_basis": ["traceable_source_evidence", "explicit_named_source_candidate"], "one_hop_only": True,
        })
    rows.sort(key=lambda x: (str(x.get("origin")), str(x.get("frontier_id"))))
    return {
        "schema": 1, "stage": "hng2-frontier-selection", "resolver_version": RESOLVER_VERSION,
        "selection_method": "existing_canonical_plus_high_confidence_hng1r2_provisional",
        "wave_cap": 2, "one_hop_only": True, "frontier_count": len(rows), "frontiers": rows,
        "canonical_write_back": False,
    }, rows


def _build_audit(identity_rows: Sequence[Mapping[str, Any]], graph_rows: Sequence[Mapping[str, Any]], provisional: Mapping[str, Mapping[str, Any]], temporal_rejections: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[str, set[str]] = collections.defaultdict(set)
    for row in identity_rows:
        resolution = row.get("resolution") if isinstance(row.get("resolution"), Mapping) else {}
        if resolution.get("decision_level") == "LLM_RESOLVED": selected[str(row.get("occurrence_id"))].add("llm_resolved")
        if resolution.get("decision_level") == "AUTO_SUPPORTED" and (resolution.get("graph_support") or {}).get("independent_graph_support_count", 0): selected[str(row.get("occurrence_id"))].add("graph_assisted")
        if resolution.get("resolution_status") == "ambiguous": selected[str(row.get("occurrence_id"))].add("ambiguous")
        if resolution.get("decision_level") in {"AUTO_HIGH", "AUTO_SUPPORTED"} and not selected[str(row.get("occurrence_id"))]: selected[str(row.get("occurrence_id"))].add("deterministic_sample")
    for row in temporal_rejections:
        selected[f"temporal-{row.get('evidence_ref')}-{row.get('occurrence_id')}"] .add("temporal_gate_rejection")
    for pid in sorted(provisional)[:20]:
        selected[f"provisional-{pid}"].add("provisional_frontier_candidate")
    out: list[dict[str, Any]] = []
    by_id = {str(row.get("occurrence_id")): row for row in identity_rows}
    for aid, reasons in sorted(selected.items()):
        if aid.startswith("provisional-"):
            item = provisional.get(aid.removeprefix("provisional-"), {})
            out.append({"audit_id": f"hng2-audit-{aid}", "kind": "frontier", "label": item.get("label"), "provisional_person_id": item.get("provisional_person_id"), "selection_reasons": sorted(reasons), "review": "not_reviewed", "canonical_write_back": False})
            continue
        row = by_id.get(aid, {})
        resolution = row.get("resolution") if isinstance(row.get("resolution"), Mapping) else {}
        out.append({
            "audit_id": f"hng2-audit-{aid}", "kind": row.get("candidate_kind"), "occurrence_id": aid,
            "seed_person_id": row.get("seed_person_id"), "source_work": resolution.get("source_work"),
            "surface": row.get("surface"), "resolution_method": resolution.get("resolution_method"),
            "resolved_person_id": resolution.get("resolved_person_id"), "provisional_person_id": resolution.get("provisional_person_id"),
            "candidate_set": resolution.get("candidate_set", []), "context_signals": resolution.get("context_signals", []),
            "graph_support_edges": (resolution.get("graph_support") or {}).get("graph_support_edges", []),
            "excluded_circular_edges": (resolution.get("graph_support") or {}).get("excluded_circular_edges", []),
            "evidence_refs": row.get("evidence_refs", []), "selection_reasons": sorted(reasons),
            "review": "not_reviewed", "canonical_write_back": False,
        })
    return out


def build(*, allow_llm: bool = False, quiet: bool = False) -> dict[str, Any]:
    catalog = person_catalog()
    index = forms_index(catalog)
    contextual = build_contextual_identity_registry(catalog=catalog, accepted_only=True)
    profiles = _person_profiles(catalog)
    evidence = _source_evidence()
    rel_doc = read_json(HNG1R2_RELATIONS, {}) or {}
    time_doc = read_json(HNG1R2_TEMPORAL, {}) or {}
    raw_relations = [dict(x) for x in rel_doc.get("relations", []) if isinstance(x, Mapping)]
    raw_temporal = [dict(x) for x in time_doc.get("temporal_items", []) if isinstance(x, Mapping)]
    graph_edges = _hng0_accepted_edges()

    # First determine provisional endpoints from the frozen relation layer so
    # the starting frontier is deterministic before any source retrieval.
    provisional_seed: dict[str, dict[str, Any]] = {}
    for row in raw_relations:
        ir = row.get("identity_resolution") if isinstance(row.get("identity_resolution"), Mapping) else {}
        pid = str(row.get("provisional_neighbor_id") or ir.get("provisional_person_id") or "")
        if not pid:
            continue
        label = row.get("provisional_neighbor_label") or ir.get("resolved_label") or row.get("counterpart_surface")
        item = provisional_seed.setdefault(pid, {"provisional_person_id": pid, "label": label, "evidence_refs": [], "source_works": [], "hard_relation_count": 0, "interaction_count": 0})
        item["evidence_refs"] = sorted(set(item["evidence_refs"]) | set(row.get("evidence_refs", [])))
        item["source_works"] = sorted(set(item["source_works"]) | set(row.get("source_works", [])))
        item["hard_relation_count"] += int(row.get("semantic_level") == "hard_relation")
        item["interaction_count"] += int(row.get("semantic_level") == "documented_interaction")
        item["identity"] = ir
    for pid, item in provisional_seed.items():
        item["frontier_state"] = frontier_state(item.get("identity") or {"resolution_status": "provisional", "resolved_label": item.get("label")}, evidence_traceable=bool(item["evidence_refs"]), no_temporal_conflict=True, hard_relation_count=item["hard_relation_count"], interaction_count=item["interaction_count"], direct_source_hit=bool(item["source_works"]))
    selection, wave0 = _frontier_selection(catalog, provisional_seed)
    write_json(OUTPUT_ROOT / "frontier-selection.json", selection)

    # Load the small punctuated reference set first.  The complete legacy
    # corpus contains a very large ZTJ projection; HNG2 keeps it as a lazy
    # fallback set of the already indexed local Jinshu/Shishuo/Jianshu/SGZ
    # units, while the punctuated ZTJ witness remains the normal route.
    punctuated = list(hng02.load_punctuated_units())
    punctuated.extend({**dict(row), "source_form": row.get("source_form") or "punctuated"} for row in _load_shishuo_units(ROOT))
    legacy = []
    for loader in (_load_jinshu_units, _load_shishuo_units, _load_jianshu_units, _load_sgz_units, _load_ztj_units):
        legacy.extend({**dict(row), "source_form": row.get("source_form") or "legacy_local"} for row in loader(ROOT))
    punctuated.sort(key=lambda row: str(row.get("source_ref")))
    legacy.sort(key=lambda row: str(row.get("source_ref")))
    wave1_profiles = _profiles_for_frontier(catalog, [row["frontier_id"] for row in wave0], provisional_seed)
    prepared_punctuated = _prepare_search_units(punctuated)
    prepared_legacy = _prepare_search_units(legacy)
    retrieval_trace = _run_retrieval(wave0, wave1_profiles, punctuated, legacy, 1, prepared_punctuated, prepared_legacy)
    write_json(OUTPUT_ROOT / "frontier-wave-1.json", {"schema": 1, "wave": 1, "frontiers": wave0, "researched_count": len(wave0), "new_neighbors": [], "canonical_write_back": False})

    identity_rows: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    temporal_items: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    validation_failures: list[dict[str, Any]] = []
    graph_support_rows: list[dict[str, Any]] = []
    starting_ids = {str(row.get("person_id")) for row in wave0 if row.get("person_id")}

    # HNG1R2 rows are immutable source-driven candidates.  HNG2 re-resolves
    # their identities through the reusable resolver; it does not treat the
    # old identity choice as a fact.
    for kind, raw_rows in (("relation", raw_relations), ("temporal", raw_temporal)):
        for row in sorted(raw_rows, key=lambda x: str(x.get("relation_id") or x.get("temporal_id"))):
            seed_id = str(row.get("person_a") or row.get("person_id") or row.get("seed_person_id") or "")
            if seed_id and seed_id not in starting_ids:
                continue
            surface, context_seed_id = _identity_input(row, kind)
            seed_id = seed_id or context_seed_id
            seed = _seed_profile(catalog, seed_id)
            valid_quotes, failures = _valid_evidence(row, evidence)
            for failure in failures:
                validation_failures.append({"occurrence_id": row.get("relation_id") or row.get("temporal_id"), **failure})
            if not valid_quotes:
                unresolved_resolution = {
                    "surface": surface,
                    "resolution_status": "unresolved",
                    "decision_level": "UNRESOLVED",
                    "resolution_method": "unresolved",
                    "confidence": "low",
                    "candidate_set": [],
                    "context_signals": [],
                    "note": "all supplied evidence quotes failed exact source validation",
                    "evidence_validation_failures": failures,
                    "temporal_status": "unknown",
                }
                identity_rows.append(_identity_record(row, kind, unresolved_resolution, {"status": "unknown", "reason": "no valid source evidence", "decisions": []}, 1, row.get("source_forms", [])))
                rejected.append({"occurrence_id": row.get("relation_id") or row.get("temporal_id"), "reason": "no_valid_exact_evidence", "kind": kind})
                continue
            gate, decisions = _gate_for_row(row, seed, evidence)
            occurrence_id = str(row.get("relation_id") or row.get("temporal_id") or "")
            for decision in decisions:
                gates.append({"occurrence_id": occurrence_id, "kind": kind, "seed_person_id": seed_id, **decision})
            if gate.get("status") == "conflict":
                rejected.append({"occurrence_id": occurrence_id, "reason": "seed_temporal_conflict", "kind": kind, "gate": gate})
                continue
            context = _evidence_context(_row_refs(row), valid_quotes, evidence)
            resolution = resolve_identity(
                surface=surface, seed=seed, context=context, evidence=evidence, catalog=catalog, index=index,
                contextual_registry=contextual, neighborhoods={}, graph_edges=graph_edges,
                evidence_refs=[str(x.get("ref")) for x in valid_quotes], candidate_id=occurrence_id, temporal=gate,
            )
            # Keep the temporal result in the identity record even when the
            # identity itself remains provisional or ambiguous.
            identity_rows.append(_identity_record(row, kind, resolution, gate, 1, row.get("source_forms", [])))
            graph = resolution.get("graph_support") if isinstance(resolution.get("graph_support"), Mapping) else graph_support(seed_id=seed_id, candidate_id=str(resolution.get("resolved_person_id") or ""), edges=graph_edges, current_evidence_refs=_row_refs(row), current_candidate_id=occurrence_id, current_claim=row.get("claim") or "")
            if graph.get("graph_support_edges") or graph.get("excluded_circular_edges"):
                graph_support_rows.append({"occurrence_id": occurrence_id, **graph})
            if kind == "relation":
                projected = _project_relation(row, resolution, valid_quotes, gate, graph, 1)
                if projected:
                    relations.append(projected)
                else:
                    rejected.append({"occurrence_id": occurrence_id, "reason": "self_relation_after_hybrid_resolution", "kind": kind})
            else:
                temporal_items.append(_project_temporal(row, resolution, valid_quotes, gate, 1))

    relations = _merge_relations(relations)
    # Recompute provisional nodes from the repaired relation projection.
    provisional = _provisional_summary(relations, identity_rows, catalog)
    write_json(OUTPUT_ROOT / "frontier-wave-1.json", {
        "schema": 1, "wave": 1, "frontiers": wave0, "researched_count": len(wave0),
        "new_neighbors": sorted(provisional), "new_neighbor_count": len(provisional), "canonical_write_back": False,
    })
    wave2_candidates = [item for item in provisional.values() if item.get("frontier_state") == "eligible_frontier"]
    wave2_frontiers = [{
        "frontier_id": item["provisional_person_id"], "person_id": None,
        "provisional_person_id": item["provisional_person_id"], "label": item.get("label"),
        "frontier_state": "eligible_frontier", "wave": 2, "origin": "wave_1_new_neighbor",
        "eligibility_basis": ["traceable_source_evidence", "independent_candidate_relation"], "one_hop_only": True,
    } for item in sorted(wave2_candidates, key=lambda x: str(x.get("provisional_person_id")))]
    wave2_profiles = _profiles_for_frontier(catalog, [x["frontier_id"] for x in wave2_frontiers], provisional)
    retrieval_trace.extend(_run_retrieval(wave2_frontiers, wave2_profiles, punctuated, legacy, 2, prepared_punctuated, prepared_legacy))
    write_json(OUTPUT_ROOT / "frontier-wave-2.json", {
        "schema": 1, "wave": 2, "frontiers": wave2_frontiers, "researched_count": len(wave2_frontiers),
        "new_neighbors": [], "wave_3_created": False, "terminal_reason": "two_wave_cap", "canonical_write_back": False,
    })

    # No HNG2 extraction call is needed in this replay: Wave 2's local hits
    # are recorded for the next controlled run, not converted into unreviewed
    # relations by a hidden heuristic.
    llm_assist = {
        "schema": 1, "stage": "hng2-identity-llm-assist", "model": "deepseek-v4-flash",
        "eligible_cases": [row["occurrence_id"] for row in identity_rows if (row.get("resolution") or {}).get("resolution_status") in {"ambiguous", "unresolved"}],
        "model_calls": 0, "api_calls": 0, "outputs": [], "reason": "deterministic replay did not require semantic adjudication",
        "canonical_write_back": False,
    }
    audit = _build_audit(identity_rows, graph_support_rows, provisional, rejected)
    write_json(OUTPUT_ROOT / "identity-resolution.json", {"schema": 1, "stage": "hng2-hybrid-identity-resolution", "resolver_version": RESOLVER_VERSION, "catalog_source": "build_hng0_2.person_catalog", "forms_index": "systematic_matching_normalize", "resolutions": identity_rows, "canonical_write_back": False})
    write_json(OUTPUT_ROOT / "contextual-identity-registry.json", {"schema": 1, "stage": "hng2-read-only-contextual-identity-registry", "source": "historical_entity_resolver.build_contextual_identity_registry", "rows": contextual, "global_alias_write_back": False, "canonical_write_back": False})
    write_json(OUTPUT_ROOT / "identity-llm-assist.json", llm_assist)
    write_json(OUTPUT_ROOT / "identity-graph-support.json", {"schema": 1, "stage": "hng2-independent-graph-support", "edges": graph_support_rows, "source": "accepted_hng0_review_edges", "circular_edges_excluded": sum(len(row.get("excluded_circular_edges", [])) for row in graph_support_rows), "canonical_write_back": False})
    write_json(OUTPUT_ROOT / "relations.json", {"schema": 1, "stage": "hng2-candidate-relations", "relations": relations, "source_candidate_count": len(raw_relations), "canonical_write_back": False})
    write_json(OUTPUT_ROOT / "temporal-items.json", {"schema": 1, "stage": "hng2-candidate-temporal-items", "temporal_items": temporal_items, "canonical_write_back": False})
    write_json(OUTPUT_ROOT / "temporal-gate-decisions.json", {"schema": 1, "stage": "hng2-seed-temporal-gate", "decisions": gates, "canonical_write_back": False})
    # A frozen candidate quote is considered used only for the frontier that
    # supplied it.  This keeps retrieval hits separate from evidence actually
    # consumed by the projection.
    used_by_frontier: dict[str, set[str]] = collections.defaultdict(set)
    for row in [*relations, *temporal_items]:
        owner = str(row.get("person_a") or row.get("person_id") or "")
        used_by_frontier[owner].update(str(ref) for ref in row.get("evidence_refs", []) if ref)
    seen_used: set[str] = set()
    for trace in retrieval_trace:
        owner = str(trace.get("person_id") or trace.get("frontier_id") or "")
        used = sorted(used_by_frontier.get(owner, set()))
        trace["used_refs"] = used
        trace["new_used_refs"] = sorted(set(used) - seen_used)
        seen_used.update(used)
    write_json(OUTPUT_ROOT / "retrieval-trace.json", {"schema": 1, "stage": "hng2-punctuated-first-retrieval", "waves": [1, 2], "records": retrieval_trace, "canonical_write_back": False})
    write_json(OUTPUT_ROOT / "provisional-persons.json", {"schema": 1, "stage": "hng2-provisional-persons", "persons": list(provisional.values()), "canonical_write_back": False})
    write_json(OUTPUT_ROOT / "consolidation-candidates.json", {"schema": 1, "stage": "hng2-provisional-consolidation", "candidates": [], "reason": "provisional IDs are deterministic label keys; no ambiguous merge was auto-created", "canonical_write_back": False})
    write_json(OUTPUT_ROOT / "rejected-passages.json", {"schema": 1, "stage": "hng2-rejected-passages", "records": rejected, "canonical_write_back": False})
    unresolved = [row for row in identity_rows if (row.get("resolution") or {}).get("resolution_status") == "unresolved"]
    ambiguous = [row for row in identity_rows if (row.get("resolution") or {}).get("resolution_status") == "ambiguous"]
    write_json(OUTPUT_ROOT / "unresolved-identities.json", {"schema": 1, "stage": "hng2-unresolved-identities", "occurrences": unresolved, "canonical_write_back": False})
    write_json(OUTPUT_ROOT / "ambiguous-identities.json", {"schema": 1, "stage": "hng2-ambiguous-identities", "occurrences": ambiguous, "canonical_write_back": False})
    write_json(OUTPUT_ROOT / "audit-sample.json", {"schema": 1, "stage": "hng2-audit-sample", "records": audit, "review_values": ["correct", "false_merge", "false_split", "bad_seed_match", "bad_temporal_rejection", "uncertain", "not_reviewed"], "canonical_write_back": False})

    # A compact per-person neighbourhood is intentionally derived only from
    # candidate rows; it is not a canonical graph projection.
    neighborhoods: list[dict[str, Any]] = []
    all_frontiers = [*wave0, *wave2_frontiers]
    for frontier in sorted(all_frontiers, key=lambda x: str(x.get("frontier_id"))):
        fid = str(frontier.get("frontier_id"))
        rels = [r for r in relations if str(r.get("person_a")) == fid or str(r.get("person_b")) == fid]
        times = [t for t in temporal_items if str(t.get("person_id") or t.get("provisional_subject_id")) == fid]
        nearby = sorted({str(r.get("person_b") or r.get("provisional_neighbor_id")) for r in rels if str(r.get("person_a")) == fid} | {str(r.get("person_a")) for r in rels if str(r.get("person_b")) == fid})
        neighborhoods.append({"frontier_id": fid, "person": profiles.get(fid, {}).get("canonical_name") or frontier.get("label"), "frontier_state": frontier.get("frontier_state"), "one_hop_relations": [r.get("relation_id") for r in rels], "temporal_items": [t.get("temporal_id") for t in times], "nearby_persons": [x for x in nearby if x and x != fid], "evidence_refs": sorted(set(ref for r in rels for ref in r.get("evidence_refs", [])) | set(ref for t in times for ref in t.get("evidence_refs", []))), "approximate_temporal_window": "unknown", "canonical_write_back": False})
    write_json(OUTPUT_ROOT / "neighborhoods.json", {"schema": 1, "stage": "hng2-research-neighborhoods", "neighborhoods": neighborhoods, "canonical_write_back": False})

    resolution_statuses = collections.Counter(str((row.get("resolution") or {}).get("resolution_status") or "unknown") for row in identity_rows)
    levels = collections.Counter(str(row.get("semantic_level") or "unknown") for row in relations)
    gate_statuses = collections.Counter(str(row.get("status") or "unknown") for row in gates)
    source_forms = collections.Counter(form for row in retrieval_trace for form in row.get("source_forms", []))
    retrieved = sum(int(row.get("retrieved_count") or 0) for row in retrieval_trace)
    opened = sum(int(row.get("opened_count") or 0) for row in retrieval_trace)
    opened_chars = sum(int(row.get("opened_chars") or 0) for row in retrieval_trace)
    metrics = {
        "schema": 1, "stage": "hng2-metrics", "canonical_write_back": False,
        "seed_frontier_count": len(wave0), "canonical_seed_count": len(catalog), "wave_1_researched_count": len(wave0),
        "wave_1_new_person_count": len(provisional), "wave_2_eligible_count": len(wave2_frontiers), "wave_2_researched_count": len(wave2_frontiers),
        "wave_3_created": False, "total_new_unique_persons": len(provisional), "total_new_relations": len(relations), "total_temporal_items": len(temporal_items),
        "identity_occurrence_count": len(identity_rows), "identity_status_counts": dict(sorted(resolution_statuses.items())),
        "deterministic_resolved_count": sum(1 for r in identity_rows if (r.get("resolution") or {}).get("decision_level") in {"AUTO_HIGH", "AUTO_SUPPORTED"}),
        "graph_assisted_resolved_count": sum(1 for r in identity_rows if (r.get("resolution") or {}).get("graph_support", {}).get("independent_graph_support_count", 0)),
        "llm_assist_calls": 0, "llm_assist_success_rate": None, "validator_rejection_count": len(validation_failures),
        "temporal_gate_counts": dict(sorted(gate_statuses.items())), "temporal_checked_passage_count": len(gates),
        "graph_identity_support_count": len(graph_support_rows), "independent_graph_support_edges": sum(int(r.get("independent_graph_support_count") or 0) for r in graph_support_rows),
        "circular_graph_edges_excluded": sum(len(r.get("excluded_circular_edges", [])) for r in graph_support_rows),
        "relation_semantic_level_counts": dict(sorted(levels.items())), "relation_by_type": dict(sorted(collections.Counter(str(r.get("normalized_relation_type")) for r in relations).items())),
        "retrieval": {"trace_count": len(retrieval_trace), "retrieved_passages": retrieved, "opened_passages": opened, "used_evidence_refs": len(set(ref for r in relations for ref in r.get("evidence_refs", [])) | set(ref for t in temporal_items for ref in t.get("evidence_refs", []))), "opened_chars": opened_chars, "source_form_counts": dict(sorted(source_forms.items())), "punctuated_first": True},
        "unresolved_identity_count": len(unresolved), "ambiguous_identity_count": len(ambiguous), "provisional_person_count": len(provisional),
        "evidence_validation_failures": validation_failures, "rejected_passage_count": len(rejected), "api_calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "latency_seconds": [],
        "deterministic_identity_savings": {"identity_assist_calls_avoided": len(identity_rows), "reason": "all HNG2 output was built by offline deterministic replay"},
    }
    write_json(OUTPUT_ROOT / "metrics.json", metrics)

    # Review overlay is separate from generated candidate data and starts
    # entirely unreviewed.
    write_json(REVIEW_PATH, {"schema": 1, "stage": "hng2-review-overlay", "canonical_write_back": False, "review_values": ["correct", "false_merge", "false_split", "bad_seed_match", "bad_temporal_rejection", "uncertain", "not_reviewed"], "identity_decisions": {str(row.get("audit_id")): {"review_status": "not_reviewed", "reviewer_note": ""} for row in audit}, "relation_decisions": {str(row.get("relation_id")): {"review_status": "not_reviewed", "reviewer_note": ""} for row in relations}, "temporal_decisions": {str(row.get("temporal_id")): {"review_status": "not_reviewed", "reviewer_note": ""} for row in temporal_items}})

    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in [HNG1R2_IDENTITY, HNG1R2_RELATIONS, HNG1R2_TEMPORAL, ROOT / "data/people.json", ROOT / "data/aliases.json"] if path.is_file()}
    protected_hashes = {
        "hng1r2": hash_tree(HNG1R2_ROOT),
        "hng0": hash_tree(ROOT / "data/generated/hng0"),
        "hng0-1": hash_tree(ROOT / "data/generated/hng0-1"),
        "hng0-2": hash_tree(ROOT / "data/generated/hng0-2"),
        "hng1": hash_tree(ROOT / "data/generated/hng1"),
        "hng1r": hash_tree(ROOT / "data/generated/hng1r"),
    }
    manifest = {
        "schema": 1, "stage": "hng2", "execution_kind": "offline_deterministic_replay", "resolver_version": RESOLVER_VERSION,
        "catalog_source": "build_hng0_2.person_catalog", "forms_index": "historical_entity_resolver.forms_index", "contextual_registry_source": "read_only_alias_and_effective_identity_records",
        "input_hashes": input_hashes, "protected_artifact_hashes": protected_hashes, "outputs": OUTPUT_FILES,
        "model": {"provider": "deepseek", "model": "deepseek-v4-flash", "model_calls": 0, "identity_assist_calls": 0, "allow_llm_requested": bool(allow_llm)},
        "wave_cap": 2, "one_hop_only": True, "canonical_write_back": False, "person_specific_rules": False,
    }
    write_json(OUTPUT_ROOT / "manifest.json", manifest)
    if not quiet:
        print(json.dumps({"stage": "hng2", "identity_occurrences": len(identity_rows), "relations": len(relations), "provisional_persons": len(provisional), "wave_2": len(wave2_frontiers), "model_calls": 0}, ensure_ascii=False, sort_keys=True))
    return {"metrics": metrics, "manifest": manifest}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-llm", action="store_true", help="record residual identity-assist eligibility; no call is made by offline build")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    build(allow_llm=args.allow_llm, quiet=args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
