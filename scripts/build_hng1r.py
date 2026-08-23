#!/usr/bin/env python3
"""Build the HNG1R offline identity-repair projection.

HNG1R reads the immutable HNG1 projection and applies only the generic
contextual_short_name stage.  It never calls DeepSeek and never writes HNG1
or canonical historical data.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_hng0_2 as hng02  # noqa: E402
from hng0_1_common import write_json  # noqa: E402
from hng1r_common import (  # noqa: E402
    CONTEXTUAL_SHORT_RESOLVER_VERSION,
    HNG1_ROOT,
    apply_identity_to_relation,
    apply_identity_to_temporal,
    candidate_from_projection,
    hng1_hashes,
    load_hng_neighborhoods,
    readiness,
    read_json,
    resolve_contextual_short_name,
    sha256_file,
    unique_relation_projection,
)


OUTPUT_ROOT = ROOT / "data/generated/hng1r"
REVIEW_PATH = ROOT / "data/annotation/hng1r-review.json"
HNG1_REVIEW = ROOT / "data/annotation/hng1-review.json"


def _load_inputs() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    identity_doc = read_json(HNG1_ROOT / "identity-resolution.json")
    evidence_doc = read_json(HNG1_ROOT / "source-evidence-registry.json")
    relation_rows = read_json(HNG1_ROOT / "relations.json").get("relations", [])
    temporal_rows = read_json(HNG1_ROOT / "temporal-items.json").get("temporal_items", [])
    candidates: dict[str, dict[str, Any]] = {}
    for row in [*relation_rows, *temporal_rows]:
        if not isinstance(row, Mapping):
            continue
        for candidate_id in row.get("candidate_ids", []):
            if candidate_id:
                candidates[str(candidate_id)] = dict(row)
    return identity_doc, evidence_doc, relation_rows, temporal_rows, candidates


def _updated_resolutions(
    identity_doc: Mapping[str, Any],
    candidates: Mapping[str, Mapping[str, Any]],
    evidence: Mapping[str, Mapping[str, Any]],
    catalog: Mapping[str, Mapping[str, Any]],
    neighborhoods: Mapping[str, set[str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    output: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for old in sorted(identity_doc.get("resolutions", []), key=lambda row: str(row.get("candidate_id"))):
        old_row = dict(old)
        candidate_id = str(old_row.get("candidate_id") or "")
        candidate = candidates.get(candidate_id)
        if candidate is None:
            new_row = copy.deepcopy(old_row)
            new_row.setdefault("replay_note", "candidate projection unavailable; frozen identity retained")
        else:
            kind = "relation" if "counterpart_surface" in candidate else "temporal"
            candidate = candidate_from_projection(candidate, kind=kind)
            new_row = resolve_contextual_short_name(
                old_resolution=old_row,
                candidate=candidate,
                evidence=evidence,
                catalog=catalog,
                neighborhoods=neighborhoods,
            )
        comparable = ("resolution_status", "resolved_person_id", "provisional_person_id", "resolution_method")
        if any(old_row.get(key) != new_row.get(key) for key in comparable):
            changes.append({
                "candidate_id": candidate_id,
                "surface": old_row.get("surface"),
                "before": {key: old_row.get(key) for key in comparable},
                "after": {key: new_row.get(key) for key in comparable},
                "repair": "contextual_short_name" if new_row.get("resolution_method") == "contextual_short_name" else "contextual_replay",
            })
        output.append(new_row)
        if candidate_id:
            by_id[candidate_id] = new_row
    return output, changes, by_id


def _audit_record(identity: Mapping[str, Any], candidate: Mapping[str, Any], evidence: Mapping[str, Mapping[str, Any]], selection_reason: str) -> dict[str, Any]:
    refs = [str(ref) for ref in identity.get("supporting_evidence_refs", []) if ref]
    if not refs:
        refs = [str(ref) for ref in candidate.get("evidence_refs", []) if ref]
    quotes = {
        str(item.get("ref")): str(item.get("quote") or "")
        for item in candidate.get("evidence_quotes", [])
        if isinstance(item, Mapping) and item.get("ref")
    }
    passages = []
    for ref in sorted(set(refs)):
        source = evidence.get(ref, {})
        passages.append({
            "ref": ref,
            "source_work": source.get("source_work"),
            "source_path": source.get("source_path"),
            "quote": quotes.get(ref, ""),
            "passage": source.get("model_snippet") or identity.get("supporting_passage") or "",
        })
    resolved_id = identity.get("resolved_person_id")
    return {
        "audit_id": f"hng1r-audit-{identity.get('candidate_id')}",
        "candidate_id": identity.get("candidate_id"),
        "seed_person_id": identity.get("seed_person_id") or candidate.get("person_a") or candidate.get("person_id"),
        "source_work": sorted({str(item.get("source_work")) for item in passages if item.get("source_work")}),
        "source_passages": passages,
        "extracted_surface": identity.get("surface") or candidate.get("counterpart_surface") or candidate.get("subject_surface"),
        "resolved_identity": {
            "person_id": resolved_id,
            "canonical_name": identity.get("resolved_label"),
        },
        "resolution_method": identity.get("resolution_method"),
        "alternative_candidate_set": list(identity.get("candidate_set", [])),
        "context_signals": list(identity.get("context_signals", [])),
        "confidence": identity.get("confidence"),
        "review": "not_reviewed",
        "selection_reason": selection_reason,
        "canonical_write_back": False,
    }


def _build_audit(resolutions: list[dict[str, Any]], candidates: Mapping[str, Mapping[str, Any]], evidence: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[str, tuple[dict[str, Any], str]] = {}

    def add(row: dict[str, Any], reason: str) -> None:
        cid = str(row.get("candidate_id") or "")
        if cid and cid not in selected:
            selected[cid] = (row, reason)

    for row in resolutions:
        if row.get("resolution_status") == "resolved_existing_person":
            add(row, "all_resolved_existing_person")
    for row in resolutions:
        if row.get("resolution_method") == "contextual_short_name":
            add(row, "all_contextual_short_name")
    for row in [x for x in resolutions if x.get("resolution_status") == "resolved_provisional_person"][:20]:
        add(row, "provisional_identity_sample_20")
    title_rows = [
        row for row in resolutions
        if row.get("resolution_method") in {"title", "decorated_name_suffix"}
    ]
    for row in title_rows[:10]:
        add(row, "title_or_decorated_sample_10")
    for row in resolutions:
        if row.get("resolution_status") == "ambiguous_identity":
            add(row, "all_ambiguous_identity")

    return [
        _audit_record(row, candidates.get(str(row.get("candidate_id")), {}), evidence, reason)
        for row, reason in sorted(selected.values(), key=lambda item: str(item[0].get("candidate_id")))
    ]


def _project_neighborhoods(selection: Mapping[str, Any], relations: list[Mapping[str, Any]], temporal: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    profiles = {str(row.get("person_id")): row for row in selection.get("people", []) if row.get("person_id")}
    output = []
    for pid in sorted(profiles):
        rels = [row for row in relations if str(row.get("person_a")) == pid]
        times = [row for row in temporal if str(row.get("person_id")) == pid]
        nearby = sorted({str(row.get("person_b")) for row in rels if row.get("person_b")} | {str(row.get("provisional_neighbor_id")) for row in rels if row.get("provisional_neighbor_id")})
        output.append({
            "person_id": pid,
            "canonical_name": profiles[pid].get("canonical_name"),
            "seed": True,
            "one_hop_only": True,
            "nearby_person_ids": nearby,
            "relations": [row.get("relation_id") for row in rels],
            "temporal_items": [row.get("temporal_id") for row in times],
            "evidence_refs": sorted({str(ref) for row in [*rels, *times] for ref in row.get("evidence_refs", [])}),
            "approximate_temporal_window": {},
        })
    return output


def build(*, quiet: bool = False) -> dict[str, Any]:
    identity_doc, evidence_doc, relation_rows, temporal_rows, candidates = _load_inputs()
    evidence = evidence_doc.get("evidence", {})
    selection = read_json(HNG1_ROOT / "hng1-selection.json")
    catalog = hng02.person_catalog()
    neighborhoods = load_hng_neighborhoods()
    hng1_before = hng1_hashes()
    old_review_hash = sha256_file(HNG1_REVIEW) if HNG1_REVIEW.is_file() else None

    resolutions, resolution_changes, by_id = _updated_resolutions(
        identity_doc,
        candidates,
        evidence,
        catalog,
        neighborhoods,
    )
    repaired_relations: list[dict[str, Any]] = []
    for row in relation_rows:
        candidate_ids = [str(value) for value in row.get("candidate_ids", []) if value]
        identity = by_id.get(candidate_ids[0]) if candidate_ids else row.get("identity_resolution", {})
        repaired_relations.append(apply_identity_to_relation(row, identity or {}))
    repaired_relations = unique_relation_projection(repaired_relations)

    repaired_temporal: list[dict[str, Any]] = []
    for row in temporal_rows:
        candidate_ids = [str(value) for value in row.get("candidate_ids", []) if value]
        identity = by_id.get(candidate_ids[0]) if candidate_ids else row.get("identity_resolution", {})
        repaired_temporal.append(apply_identity_to_temporal(row, identity or {}))

    audit_items = _build_audit(resolutions, candidates, evidence)
    audit_requested = {
        "resolved_existing_person": "all",
        "contextual_short_name": "all",
        "provisional_identity": 20,
        "title_or_decorated": 10,
        "ambiguous_identity": "all",
    }
    audit_available = {
        "resolved_existing_person": sum(row.get("resolution_status") == "resolved_existing_person" for row in resolutions),
        "contextual_short_name": sum(row.get("resolution_method") == "contextual_short_name" for row in resolutions),
        "provisional_identity": min(20, sum(row.get("resolution_status") == "resolved_provisional_person" for row in resolutions)),
        "title_or_decorated": min(10, sum(row.get("resolution_method") in {"title", "decorated_name_suffix"} for row in resolutions)),
        "ambiguous_identity": sum(row.get("resolution_status") == "ambiguous_identity" for row in resolutions),
    }
    readiness_doc = readiness(audit_items, resolutions)
    old_status = {}
    for row in identity_doc.get("resolutions", []):
        old_status[str(row.get("candidate_id"))] = str(row.get("resolution_status"))
    new_status = {str(row.get("candidate_id")): str(row.get("resolution_status")) for row in resolutions}
    status_counts_before: dict[str, int] = {}
    status_counts_after: dict[str, int] = {}
    for value in old_status.values():
        status_counts_before[value] = status_counts_before.get(value, 0) + 1
    for value in new_status.values():
        status_counts_after[value] = status_counts_after.get(value, 0) + 1
    relation_changes = []
    old_rel_by_id = {str(row.get("relation_id")): row for row in relation_rows}
    for row in repaired_relations:
        old = old_rel_by_id.get(str(row.get("relation_id")), {})
        keys = ("person_b", "provisional_neighbor_id", "resolution_status")
        if any(old.get(key) != row.get(key) for key in keys):
            relation_changes.append({
                "relation_id": row.get("relation_id"),
                "before": {key: old.get(key) for key in keys},
                "after": {key: row.get(key) for key in keys},
                "cause": "identity_repair_only",
            })

    unresolved = [row for row in resolutions if row.get("resolution_status") in {"unresolved_identity", "ambiguous_identity"}]
    metrics = {
        "schema": 1,
        "stage": "hng1r-metrics",
        "execution_kind": "offline_deterministic",
        "model_calls": 0,
        "canonical_write_back": False,
        "hng1_immutable": True,
        "resolver_version": CONTEXTUAL_SHORT_RESOLVER_VERSION,
        "input_identity_occurrence_count": len(identity_doc.get("resolutions", [])),
        "output_identity_occurrence_count": len(resolutions),
        "status_counts_before": dict(sorted(status_counts_before.items())),
        "status_counts_after": dict(sorted(status_counts_after.items())),
        "unresolved_occurrences_before": status_counts_before.get("unresolved_identity", 0),
        "unresolved_occurrences_after": status_counts_after.get("unresolved_identity", 0),
        "newly_resolved_count": sum(1 for row in resolution_changes if row.get("after", {}).get("resolution_status") == "resolved_existing_person"),
        "contextual_short_name_count": sum(1 for row in resolutions if row.get("resolution_method") == "contextual_short_name"),
        "ambiguous_cases_before": status_counts_before.get("ambiguous_identity", 0),
        "ambiguous_cases_after": status_counts_after.get("ambiguous_identity", 0),
        "provisional_count_before": status_counts_before.get("resolved_provisional_person", 0),
        "provisional_count_after": status_counts_after.get("resolved_provisional_person", 0),
        "resolution_changes": resolution_changes,
        "relation_count_before": len(relation_rows),
        "relation_count_after": len(repaired_relations),
        "relation_changes_identity_only": relation_changes,
        "relation_change_count": len(relation_changes),
        "unresolved_items_after": len(unresolved),
        "audit_item_count": len(audit_items),
        "hng2_readiness": readiness_doc,
    }

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT_ROOT / "identity-resolution.json", {
        "schema": 1,
        "stage": "hng1r-identity-resolution",
        "canonical_write_back": False,
        "resolver_version": CONTEXTUAL_SHORT_RESOLVER_VERSION,
        "base_resolver_version": hng02.DECORATED_RESOLVER_VERSION,
        "resolutions": resolutions,
    })
    write_json(OUTPUT_ROOT / "relations.json", {
        "schema": 1,
        "stage": "hng1r-relations",
        "canonical_write_back": False,
        "relations": repaired_relations,
        "evidence": evidence,
    })
    write_json(OUTPUT_ROOT / "temporal-items.json", {
        "schema": 1,
        "stage": "hng1r-temporal-items",
        "canonical_write_back": False,
        "temporal_items": repaired_temporal,
        "evidence": evidence,
    })
    write_json(OUTPUT_ROOT / "unresolved-identities.json", {
        "schema": 1,
        "stage": "hng1r-unresolved-identities",
        "canonical_write_back": False,
        "items": unresolved,
    })
    write_json(OUTPUT_ROOT / "neighborhoods.json", {
        "schema": 1,
        "stage": "hng1r-neighborhoods",
        "canonical_write_back": False,
        "one_hop_only": True,
        "people": _project_neighborhoods(selection, repaired_relations, repaired_temporal),
    })
    write_json(OUTPUT_ROOT / "audit-sample.json", {
        "schema": 1,
        "stage": "hng1r-identity-audit",
        "canonical_write_back": False,
        "items": audit_items,
        "requested_sample": audit_requested,
        "available_sample": audit_available,
        "review_field": "review",
        "allowed_review_values": ["correct", "false_merge", "uncertain", "not_reviewed"],
    })
    write_json(OUTPUT_ROOT / "hng2-readiness.json", readiness_doc)
    write_json(OUTPUT_ROOT / "metrics.json", metrics)

    review = {
        "schema": 1,
        "stage": "hng1r-review-overlay",
        "canonical_write_back": False,
        "allowed_decisions": ["correct", "false_merge", "uncertain", "not_reviewed"],
        "identity_decisions": {str(row.get("audit_id")): "not_reviewed" for row in audit_items},
    }
    write_json(REVIEW_PATH, review)

    hng1_after = hng1_hashes()
    if hng1_before != hng1_after:
        raise RuntimeError("HNG1 changed during HNG1R build")
    manifest = {
        "schema": 1,
        "stage": "hng1r-manifest",
        "execution_kind": "offline_deterministic",
        "canonical_write_back": False,
        "model_calls": 0,
        "resolver_version": CONTEXTUAL_SHORT_RESOLVER_VERSION,
        "base_resolver_version": hng02.DECORATED_RESOLVER_VERSION,
        "hng1_manifest_hash": sha256_file(HNG1_ROOT / "manifest.json"),
        "hng1_review_hash": old_review_hash,
        "hng1_artifact_hashes": hng1_before,
        "one_hop_only": True,
        "outputs": [
            "identity-resolution.json", "relations.json", "temporal-items.json",
            "unresolved-identities.json", "neighborhoods.json", "audit-sample.json",
            "hng2-readiness.json", "metrics.json", "manifest.json",
        ],
    }
    write_json(OUTPUT_ROOT / "manifest.json", manifest)
    result = {
        "status": "pass",
        "execution_kind": "offline_deterministic",
        "model_calls": 0,
        "hng1_unchanged": True,
        "identity_occurrences_before": len(identity_doc.get("resolutions", [])),
        "identity_occurrences_after": len(resolutions),
        "contextual_short_name_count": metrics["contextual_short_name_count"],
        "unresolved_before": metrics["unresolved_occurrences_before"],
        "unresolved_after": metrics["unresolved_occurrences_after"],
        "ambiguous_before": metrics["ambiguous_cases_before"],
        "ambiguous_after": metrics["ambiguous_cases_after"],
        "provisional_before": metrics["provisional_count_before"],
        "provisional_after": metrics["provisional_count_after"],
        "relation_changes": len(relation_changes),
        "audit_items": len(audit_items),
        "hng2_readiness": readiness_doc["readiness_status"],
    }
    if not quiet:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    build(quiet=args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
