#!/usr/bin/env python3
"""Build HNG1R2 by replaying all frozen HNG1 identities offline."""

from __future__ import annotations

import argparse
import collections
import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_hng0_2 as hng02  # noqa: E402
from hng0_1_common import sha256_file, write_json  # noqa: E402
from hng1r_common import hash_tree, load_hng_neighborhoods  # noqa: E402
from hng1r2_common import (  # noqa: E402
    HNG1_ROOT,
    HNG1R_ROOT,
    RESOLVER_VERSION,
    deduplicate_relations,
    deduplicate_temporal,
    identity_signature,
    project_relation,
    project_temporal,
    read_json,
    replay_identity,
)


OUTPUT_ROOT = ROOT / "data/generated/hng1r2"
REVIEW_PATH = ROOT / "data/annotation/hng1r2-review.json"
HNG1_REVIEW_PATH = ROOT / "data/annotation/hng1-review.json"
HNG1R_REVIEW_PATH = ROOT / "data/annotation/hng1r-review.json"
ALLOWED_REVIEW_VALUES = ["correct", "false_merge", "false_split", "uncertain", "not_reviewed"]


def _candidate_index(
    relations: Sequence[Mapping[str, Any]],
    temporal: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in [*relations, *temporal]:
        for candidate_id in row.get("candidate_ids", []):
            cid = str(candidate_id)
            if cid in result:
                raise ValueError(f"duplicate frozen candidate projection: {cid}")
            result[cid] = dict(row)
    return result


def _status_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get("resolution_status") or "unknown") for row in rows).items()))


def _change_record(
    candidate_id: str,
    before_hng1: Mapping[str, Any],
    before_hng1r: Mapping[str, Any] | None,
    after: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "surface": after.get("surface") or before_hng1.get("surface"),
        "seed_person_id": after.get("seed_person_id") or before_hng1.get("seed_person_id"),
        "before_hng1": identity_signature(before_hng1),
        "before_hng1r": identity_signature(before_hng1r or {}),
        "after_hng1r2": identity_signature(after),
        "changed_from_hng1": identity_signature(before_hng1) != identity_signature(after),
        "changed_from_hng1r": bool(before_hng1r) and identity_signature(before_hng1r or {}) != identity_signature(after),
        "evidence_refs": list(after.get("supporting_evidence_refs", [])),
    }


def _false_split_record(change: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **dict(change),
        "repair_type": "false_split",
        "repair_reason": "frozen HNG1 occurrence now resolves through the schema-consistent canonical catalogue",
        "already_repaired_in_hng1r": change.get("before_hng1r", {}).get("resolution_status") == "resolved_existing_person",
        "resolution_method": after.get("resolution_method"),
        "resolved_person_id": after.get("resolved_person_id"),
        "resolved_label": after.get("resolved_label"),
    }


def _false_merge_record(change: Mapping[str, Any], hng1r_row: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **dict(change),
        "repair_type": "false_merge",
        "repair_reason": "HNG1R existing-person binding is incompatible with local kinship/family context",
        "incorrect_person_id": hng1r_row.get("resolved_person_id"),
        "repaired_status": after.get("resolution_status"),
        "repaired_person_id": after.get("resolved_person_id"),
        "repaired_label": after.get("resolved_label"),
        "resolution_method": after.get("resolution_method"),
    }


def _relation_change(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any] | None:
    keys = ("person_b", "person_b_name", "provisional_neighbor_id", "provisional_neighbor_label", "resolution_status")
    if not any(before.get(key) != after.get(key) for key in keys):
        return None
    candidate_id = next(iter(after.get("candidate_ids", [])), None)
    return {
        "candidate_id": candidate_id,
        "relation_id": before.get("relation_id"),
        "before": {key: before.get(key) for key in keys},
        "after": {key: after.get(key) for key in keys},
        "cause": "offline_identity_replay_only",
    }


def _merge_temporal_evidence(target: dict[str, Any], row: Mapping[str, Any]) -> None:
    for key in ("evidence_refs", "source_works", "source_forms", "source_witnesses", "candidate_ids"):
        target[key] = sorted(set(target.get(key, [])) | set(row.get(key, [])))


def _audit_record(
    resolution: Mapping[str, Any],
    reasons: Sequence[str],
    evidence: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    contexts = [dict(row) for row in resolution.get("local_resolver_context", []) if isinstance(row, Mapping)]
    source_works = sorted({str(row.get("source_work")) for row in contexts if row.get("source_work")})
    return {
        "audit_id": f"hng1r2-audit-{resolution.get('candidate_id')}",
        "candidate_id": resolution.get("candidate_id"),
        "seed_person_id": resolution.get("seed_person_id"),
        "source_work": source_works,
        "exact_quote": next((str(row.get("exact_quote")) for row in contexts if row.get("exact_quote")), ""),
        "local_resolver_context": contexts,
        "extracted_surface": resolution.get("surface"),
        "resolved_identity": {
            "person_id": resolution.get("resolved_person_id"),
            "provisional_person_id": resolution.get("provisional_person_id"),
            "canonical_name": resolution.get("resolved_label"),
            "status": resolution.get("resolution_status"),
        },
        "resolution_method": resolution.get("resolution_method"),
        "alternative_candidate_set": list(resolution.get("candidate_set", resolution.get("matches", []))),
        "context_signals": list(resolution.get("context_signals", [])),
        "confidence": resolution.get("confidence"),
        "selection_reasons": sorted(set(reasons)),
        "review": "not_reviewed",
        "canonical_write_back": False,
    }


def _build_audit(
    resolutions: Sequence[Mapping[str, Any]],
    false_splits: Sequence[Mapping[str, Any]],
    evidence: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    reasons: dict[str, set[str]] = collections.defaultdict(set)
    by_id = {str(row.get("candidate_id")): row for row in resolutions}
    for row in resolutions:
        cid = str(row.get("candidate_id"))
        if row.get("resolution_status") == "resolved_existing_person":
            reasons[cid].add("all_resolved_existing_person")
        if row.get("resolution_method") == "contextual_short_name":
            reasons[cid].add("all_contextual_short_name")
        if row.get("resolution_method") == "kinship_context":
            reasons[cid].add("all_kinship_context")
        if row.get("resolution_status") == "ambiguous_identity":
            reasons[cid].add("all_ambiguous_identity")
    for row in false_splits:
        reasons[str(row.get("candidate_id"))].add("all_repaired_false_splits")
    provisional = sorted(
        (row for row in resolutions if row.get("resolution_status") == "resolved_provisional_person"),
        key=lambda row: str(row.get("candidate_id")),
    )
    for row in provisional[:20]:
        reasons[str(row.get("candidate_id"))].add("provisional_sample_20")
    return [
        _audit_record(by_id[cid], sorted(selection_reasons), evidence)
        for cid, selection_reasons in sorted(reasons.items())
    ]


def _readiness(audit: Sequence[Mapping[str, Any]], resolutions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    decisions = [str(row.get("review") or "not_reviewed") for row in audit]
    reviewed = [value for value in decisions if value != "not_reviewed"]
    counts = _status_counts(resolutions)
    total = len(resolutions)
    return {
        "schema": 1,
        "stage": "hng1r2-hng2-readiness",
        "canonical_write_back": False,
        "reviewed_identity_count": len(reviewed),
        "audit_identity_count": len(audit),
        "correct_count": decisions.count("correct"),
        "false_merge_count": decisions.count("false_merge"),
        "false_split_count": decisions.count("false_split"),
        "false_merge_rate": decisions.count("false_merge") / len(reviewed) if reviewed else None,
        "uncertain_count": decisions.count("uncertain"),
        "unresolved_rate": counts.get("unresolved_identity", 0) / total if total else 0,
        "provisional_rate": counts.get("resolved_provisional_person", 0) / total if total else 0,
        "ambiguous_rate": counts.get("ambiguous_identity", 0) / total if total else 0,
        "status_counts": counts,
        "ready_for_hng2": False,
        "readiness_status": "awaiting_meaningful_human_audit",
        "reason": "HNG1R2 repairs the offline projection but does not auto-populate human audit judgments",
    }


def build(*, quiet: bool = False) -> dict[str, Any]:
    hng1_before = hash_tree(HNG1_ROOT)
    hng1r_before = hash_tree(HNG1R_ROOT)
    review_hashes_before = {
        "hng1": sha256_file(HNG1_REVIEW_PATH) if HNG1_REVIEW_PATH.is_file() else None,
        "hng1r": sha256_file(HNG1R_REVIEW_PATH) if HNG1R_REVIEW_PATH.is_file() else None,
    }

    identity_doc = read_json(HNG1_ROOT / "identity-resolution.json")
    relation_doc = read_json(HNG1_ROOT / "relations.json")
    temporal_doc = read_json(HNG1_ROOT / "temporal-items.json")
    evidence_doc = read_json(HNG1_ROOT / "source-evidence-registry.json")
    hng1r_identity_doc = read_json(HNG1R_ROOT / "identity-resolution.json")
    evidence = evidence_doc.get("evidence", {})
    relations = relation_doc.get("relations", [])
    temporal = temporal_doc.get("temporal_items", [])
    candidates = _candidate_index(relations, temporal)
    hng1r_by_id = {str(row.get("candidate_id")): row for row in hng1r_identity_doc.get("resolutions", [])}

    catalog = hng02.person_catalog()
    exact_index = hng02.forms_index(catalog)
    neighborhoods = load_hng_neighborhoods()

    resolutions: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    false_splits: list[dict[str, Any]] = []
    false_merges: list[dict[str, Any]] = []
    resolution_map: dict[str, dict[str, Any]] = {}
    old_rows = sorted(identity_doc.get("resolutions", []), key=lambda row: str(row.get("candidate_id")))
    for old in old_rows:
        cid = str(old.get("candidate_id") or "")
        if cid not in candidates:
            raise ValueError(f"frozen HNG1 identity has no candidate projection: {cid}")
        new = replay_identity(
            old_resolution=old,
            projected_candidate=candidates[cid],
            evidence=evidence,
            catalog=catalog,
            exact_index=exact_index,
            neighborhoods=neighborhoods,
        )
        resolutions.append(new)
        resolution_map[cid] = new
        hng1r_row = hng1r_by_id.get(cid)
        change = _change_record(cid, old, hng1r_row, new)
        if change["changed_from_hng1"] or change["changed_from_hng1r"]:
            changes.append(change)
        if old.get("resolution_status") != "resolved_existing_person" and new.get("resolution_status") == "resolved_existing_person":
            false_splits.append(_false_split_record(change, new))
        if hng1r_row and hng1r_row.get("resolution_status") == "resolved_existing_person" and (
            new.get("resolution_status") != "resolved_existing_person"
            or new.get("resolved_person_id") != hng1r_row.get("resolved_person_id")
        ):
            false_merges.append(_false_merge_record(change, hng1r_row, new))

    projected_relation_rows: list[dict[str, Any]] = []
    relation_changes: list[dict[str, Any]] = []
    for row in relations:
        cid = str(next(iter(row.get("candidate_ids", [])), ""))
        projected = project_relation(row, resolution_map[cid])
        projected_relation_rows.append(projected)
        change = _relation_change(row, projected)
        if change:
            relation_changes.append(change)
    repaired_relations = deduplicate_relations(projected_relation_rows)

    projected_temporal_rows: list[dict[str, Any]] = []
    for row in temporal:
        cid = str(next(iter(row.get("candidate_ids", [])), ""))
        projected_temporal_rows.append(project_temporal(row, resolution_map[cid]))
    repaired_temporal = deduplicate_temporal(projected_temporal_rows)

    audit = _build_audit(resolutions, false_splits, evidence)
    readiness = _readiness(audit, resolutions)
    hng1_counts = _status_counts(old_rows)
    hng1r_counts = _status_counts(hng1r_identity_doc.get("resolutions", []))
    after_counts = _status_counts(resolutions)
    unresolved = [row for row in resolutions if row.get("resolution_status") in {"unresolved_identity", "ambiguous_identity"}]

    metrics = {
        "schema": 1,
        "stage": "hng1r2-metrics",
        "execution_kind": "offline_deterministic",
        "model_calls": 0,
        "api_calls": 0,
        "canonical_write_back": False,
        "resolver_version": RESOLVER_VERSION,
        "resolver_catalog": "build_hng0_2.person_catalog",
        "person_specific_rules": False,
        "identity_occurrence_count": len(resolutions),
        "status_counts_hng1": hng1_counts,
        "status_counts_hng1r": hng1r_counts,
        "status_counts_hng1r2": after_counts,
        "identity_change_count": len(changes),
        "false_split_repair_count": len(false_splits),
        "false_merge_repair_count": len(false_merges),
        "contextual_short_name_count": sum(row.get("resolution_method") == "contextual_short_name" for row in resolutions),
        "kinship_context_count": sum(row.get("resolution_method") == "kinship_context" for row in resolutions),
        "relation_count_before": len(relations),
        "relation_count_after": len(repaired_relations),
        "relation_projection_change_count": len(relation_changes),
        "relation_deduplication_count": len(projected_relation_rows) - len(repaired_relations),
        "temporal_count_before": len(temporal),
        "temporal_count_after": len(repaired_temporal),
        "temporal_deduplication_count": len(projected_temporal_rows) - len(repaired_temporal),
        "audit_item_count": len(audit),
        "unresolved_item_count": len(unresolved),
        "hng2_readiness_status": readiness["readiness_status"],
    }

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT_ROOT / "identity-resolution.json", {
        "schema": 1,
        "stage": "hng1r2-full-identity-replay",
        "canonical_write_back": False,
        "execution_kind": "offline_deterministic",
        "resolver_version": RESOLVER_VERSION,
        "resolver_catalog": "build_hng0_2.person_catalog",
        "resolutions": resolutions,
    })
    write_json(OUTPUT_ROOT / "relations.json", {
        "schema": 1,
        "stage": "hng1r2-relations",
        "canonical_write_back": False,
        "relations": repaired_relations,
        "evidence": evidence,
    })
    write_json(OUTPUT_ROOT / "temporal-items.json", {
        "schema": 1,
        "stage": "hng1r2-temporal-items",
        "canonical_write_back": False,
        "temporal_items": repaired_temporal,
        "evidence": evidence,
    })
    write_json(OUTPUT_ROOT / "resolution-changes.json", {
        "schema": 1,
        "stage": "hng1r2-resolution-changes",
        "canonical_write_back": False,
        "identity_changes": changes,
        "relation_projection_changes": relation_changes,
    })
    write_json(OUTPUT_ROOT / "false-split-repairs.json", {
        "schema": 1,
        "stage": "hng1r2-false-split-repairs",
        "canonical_write_back": False,
        "repairs": false_splits,
    })
    write_json(OUTPUT_ROOT / "false-merge-repairs.json", {
        "schema": 1,
        "stage": "hng1r2-false-merge-repairs",
        "canonical_write_back": False,
        "repairs": false_merges,
    })
    write_json(OUTPUT_ROOT / "unresolved-identities.json", {
        "schema": 1,
        "stage": "hng1r2-unresolved-identities",
        "canonical_write_back": False,
        "items": unresolved,
    })
    write_json(OUTPUT_ROOT / "audit-sample.json", {
        "schema": 1,
        "stage": "hng1r2-identity-audit",
        "canonical_write_back": False,
        "allowed_review_values": ALLOWED_REVIEW_VALUES,
        "selection_policy": {
            "resolved_existing_person": "all",
            "contextual_short_name": "all",
            "kinship_context": "all",
            "repaired_false_splits": "all",
            "ambiguous_identity": "all",
            "provisional_identity": 20,
        },
        "items": audit,
    })
    write_json(OUTPUT_ROOT / "hng2-readiness.json", readiness)
    write_json(OUTPUT_ROOT / "metrics.json", metrics)
    write_json(REVIEW_PATH, {
        "schema": 1,
        "stage": "hng1r2-review-overlay",
        "canonical_write_back": False,
        "allowed_decisions": ALLOWED_REVIEW_VALUES,
        "identity_decisions": {str(row.get("audit_id")): "not_reviewed" for row in audit},
    })

    if hng1_before != hash_tree(HNG1_ROOT):
        raise RuntimeError("HNG1 changed during HNG1R2 build")
    if hng1r_before != hash_tree(HNG1R_ROOT):
        raise RuntimeError("HNG1R changed during HNG1R2 build")
    review_hashes_after = {
        "hng1": sha256_file(HNG1_REVIEW_PATH) if HNG1_REVIEW_PATH.is_file() else None,
        "hng1r": sha256_file(HNG1R_REVIEW_PATH) if HNG1R_REVIEW_PATH.is_file() else None,
    }
    if review_hashes_before != review_hashes_after:
        raise RuntimeError("HNG1/HNG1R review overlays changed during HNG1R2 build")

    manifest = {
        "schema": 1,
        "stage": "hng1r2-manifest",
        "execution_kind": "offline_deterministic",
        "model_calls": 0,
        "api_calls": 0,
        "canonical_write_back": False,
        "one_hop_only": True,
        "resolver_version": RESOLVER_VERSION,
        "resolver_catalog": "build_hng0_2.person_catalog",
        "forms_index": "build_hng0_2.forms_index",
        "base_resolver": "build_hng0_2.resolution_for_candidate",
        "person_specific_rules": False,
        "resolver_source_hash": sha256_file(SCRIPT_DIR / "hng1r2_common.py"),
        "hng1_artifact_hashes": hng1_before,
        "hng1r_artifact_hashes": hng1r_before,
        "hng1_review_hash": review_hashes_before["hng1"],
        "hng1r_review_hash": review_hashes_before["hng1r"],
        "outputs": [
            "identity-resolution.json", "relations.json", "temporal-items.json",
            "resolution-changes.json", "false-split-repairs.json",
            "false-merge-repairs.json", "unresolved-identities.json",
            "audit-sample.json", "hng2-readiness.json", "metrics.json",
            "manifest.json",
        ],
    }
    write_json(OUTPUT_ROOT / "manifest.json", manifest)

    result = {
        "status": "pass",
        "identity_occurrences": len(resolutions),
        "status_counts_hng1": hng1_counts,
        "status_counts_hng1r": hng1r_counts,
        "status_counts_hng1r2": after_counts,
        "false_split_repairs": len(false_splits),
        "false_merge_repairs": len(false_merges),
        "relation_changes": len(relation_changes),
        "audit_items": len(audit),
        "hng2_readiness": readiness["readiness_status"],
        "model_calls": 0,
        "hng1_unchanged": True,
        "hng1r_unchanged": True,
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
