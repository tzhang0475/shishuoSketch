#!/usr/bin/env python3
"""Build the HNG0.2R decorated-name resolution projection.

HNG0.2R is an additive, offline projection of the frozen HNG0.1 candidate
layer.  It reuses HNG0.2 normalization and retrieval code, enabling only the
generic decorated canonical-name suffix resolver.  It never rewrites HNG0.2,
canonical history, or source text.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_hng0_2 as base  # noqa: E402
from hng0_1_common import sha256_file, stable_hash, write_json  # noqa: E402


OUTPUT_ROOT = ROOT / "data/generated/hng0-2r"
REVIEW_PATH = ROOT / "data/annotation/hng0-2r-review.json"
BASELINE_ROOT = ROOT / "data/generated/hng0-2"
BASELINE_FRONTEND = ROOT / "site/src/generated/hng0-2-site.json"
BASELINE_REVIEW = ROOT / "data/annotation/hng0-2-review.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def json_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def baseline_hashes() -> dict[str, str]:
    paths = sorted(BASELINE_ROOT.glob("*.json")) + [BASELINE_FRONTEND, BASELINE_REVIEW]
    return {
        str(path.relative_to(ROOT)): sha256_file(path)
        for path in paths
        if path.is_file()
    }


def build() -> dict[str, Any]:
    frozen_manifest = read_json(OUTPUT_ROOT / "manifest.json") if (OUTPUT_ROOT / "manifest.json").is_file() else {}
    relations, temporal, evidence, unresolved_doc = base.load_hng_inputs()
    catalog = base.person_catalog()
    exact_index = base.forms_index(catalog)
    frozen_aliases = None
    try:
        import sfh2r_contract
        frozen_aliases = sfh2r_contract.pre_repair_alias_document()
    except (ImportError, OSError, ValueError, TypeError):
        frozen_aliases = None
    profiles = base.build_search_profiles(ROOT, frozen_aliases)
    for pid, profile in profiles.items():
        if pid in catalog:
            profile["canonical_name"] = catalog[pid].get("canonical_name") or profile.get("canonical_name")

    resolution_rows: list[dict[str, Any]] = []
    resolution_map: dict[str, dict[str, Any]] = {}
    for row in relations:
        rid = str(row.get("relation_id") or "")
        resolved = base.resolution_for_candidate(
            row,
            seed_profiles=profiles,
            evidence=evidence,
            catalog=catalog,
            exact_index=exact_index,
            surface_key="counterpart_surface",
            allow_decorated=True,
        )
        resolution_rows.append(resolved)
        resolution_map[rid] = resolved
    for row in temporal:
        tid = str(row.get("temporal_id") or "")
        resolved = base.resolution_for_candidate(
            row,
            seed_profiles=profiles,
            evidence=evidence,
            catalog=catalog,
            exact_index=exact_index,
            surface_key="subject_surface",
            allow_decorated=True,
        )
        resolution_rows.append(resolved)
        resolution_map[tid] = resolved

    normalized_relations, rejected_relations = base.normalize_relations(
        relations,
        resolutions=resolution_map,
        evidence=evidence,
        catalog=catalog,
    )
    normalized_temporal = base.normalize_temporal(
        temporal,
        resolutions=resolution_map,
        catalog=catalog,
    )

    unresolved_items: list[dict[str, Any]] = []
    seen_unresolved: set[tuple[str, str, str]] = set()
    for row in resolution_rows:
        if row.get("resolution_status") not in {"unresolved_identity", "ambiguous_identity"}:
            continue
        key = (str(row.get("seed_person_id")), str(row.get("surface")), str(row.get("resolution_status")))
        if key in seen_unresolved:
            continue
        seen_unresolved.add(key)
        unresolved_items.append(row)

    punctuated_units = base.load_punctuated_units()
    legacy_units = base.load_legacy_units(evidence)
    retrieval_comparison = base.run_retrieval_comparison(profiles, evidence, punctuated_units, legacy_units)

    relation_counts = collections.Counter(
        (str(row.get("semantic_level")), str(row.get("normalized_relation_type")))
        for row in normalized_relations
    )
    level_counts = collections.Counter(str(row.get("semantic_level")) for row in normalized_relations)
    type_counts = collections.Counter(str(row.get("normalized_relation_type")) for row in normalized_relations)
    old_political = sum(1 for row in relations if row.get("relation_type") == "explicit_political_cooperation_opposition")
    political_reclassified = sum(
        1
        for row in normalized_relations
        if row.get("original_relation_type") == "explicit_political_cooperation_opposition"
        and row.get("normalized_relation_type") == "documented_political_interaction"
    )
    kinship_corrections = sum(1 for row in normalized_relations if row.get("normalization_reason") == "kinship_ontology_repair")
    before_provisional = len({str(row.get("provisional_neighbor_id")) for row in relations if row.get("provisional_neighbor_id")})
    resolved_existing = [row for row in resolution_rows if row.get("resolution_status") == "resolved_existing_person"]
    resolved_provisional = [row for row in resolution_rows if row.get("resolution_status") == "resolved_provisional_person"]
    unresolved_occurrences_before = sum(
        1
        for row in relations
        if row.get("resolution_status") == "unresolved_identity"
    ) + sum(
        1
        for row in temporal
        if row.get("subject_resolution_status") == "unresolved_identity"
    )
    unresolved_occurrences_after = sum(1 for row in resolution_rows if row.get("resolution_status") == "unresolved_identity")
    ambiguous_after = sum(1 for row in resolution_rows if row.get("resolution_status") == "ambiguous_identity")
    provisional_after = len({str(row.get("provisional_neighbor_id")) for row in normalized_relations if row.get("provisional_neighbor_id")})
    unresolved_provisional_after = len({
        str(row.get("provisional_neighbor_id"))
        for row in normalized_relations
        if row.get("resolution_status") == "unresolved_identity" and row.get("provisional_neighbor_id")
    })
    source_forms = collections.Counter()
    for mode in retrieval_comparison.get("modes", {}).values():
        source_forms.update(mode.get("source_form_counts", {}))
    decorated_rows = [row for row in resolution_rows if row.get("resolution_method") == "decorated_name_suffix"]

    metrics = {
        "schema": 1,
        "stage": "hng0-2r-metrics",
        "canonical_write_back": False,
        "execution_kind": "offline_deterministic",
        "model_calls": 0,
        "resolver_version": base.DECORATED_RESOLVER_VERSION,
        "seed_count": len(profiles),
        "seed_person_ids": sorted(profiles),
        "input_relation_candidates": len(relations),
        "input_temporal_candidates": len(temporal),
        "input_unresolved_occurrences": len(unresolved_doc.get("items", [])),
        "unresolved_provisional_neighbor_count_before": before_provisional,
        "provisional_neighbor_count_after": provisional_after,
        "unresolved_provisional_neighbor_count_after": unresolved_provisional_after,
        "unresolved_occurrences_before": unresolved_occurrences_before,
        "unresolved_occurrences_after": unresolved_occurrences_after,
        "ambiguous_identity_count_after": ambiguous_after,
        "resolved_existing_count": len(resolved_existing),
        "resolved_provisional_count": len(resolved_provisional),
        "resolved_by_method": dict(sorted(collections.Counter(
            str(row.get("resolution_method")) for row in resolved_existing + resolved_provisional
        ).items())),
        "decorated_name_suffix_count": len(decorated_rows),
        "normalized_relation_count": len(normalized_relations),
        "normalized_temporal_count": len(normalized_temporal),
        "relation_level_counts": dict(sorted(level_counts.items())),
        "relation_type_counts": dict(sorted(type_counts.items())),
        "relation_level_type_counts": {
            f"{level}:{kind}": count
            for (level, kind), count in sorted(relation_counts.items())
        },
        "political_candidates_before": old_political,
        "political_candidates_reclassified_to_documented_interaction": political_reclassified,
        "kinship_ontology_corrections": kinship_corrections,
        "rejected_after_normalization": len(rejected_relations),
        "remaining_unresolved_identity_count": len([row for row in resolution_rows if row.get("resolution_status") == "unresolved_identity"]),
        "remaining_ambiguous_identity_count": ambiguous_after,
        "source_form_usage": dict(sorted(source_forms.items())),
        "punctuated_unit_count": len(punctuated_units),
        "legacy_comparison_unit_count": len(legacy_units),
        "api_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "latency": {"model_calls": 0},
    }

    evidence_projection = base.build_evidence_projection(evidence)
    identity_doc = {
        "schema": 1,
        "stage": "hng0-2r-identity-resolution",
        "canonical_write_back": False,
        "resolver_version": base.DECORATED_RESOLVER_VERSION,
        "input_relation_count": len(relations),
        "input_temporal_count": len(temporal),
        "resolutions": sorted(
            resolution_rows,
            key=lambda row: (str(row.get("candidate_kind")), str(row.get("candidate_id")), str(row.get("surface"))),
        ),
    }
    relation_doc = {
        "schema": 1,
        "stage": "hng0-2r-normalized-relations",
        "canonical_write_back": False,
        "relations": normalized_relations,
        "evidence": evidence_projection,
        "rejected": rejected_relations,
    }
    temporal_doc = {
        "schema": 1,
        "stage": "hng0-2r-normalized-temporal",
        "canonical_write_back": False,
        "temporal_items": normalized_temporal,
        "evidence": evidence_projection,
    }
    interaction_doc = {
        "schema": 1,
        "stage": "hng0-2r-interaction-edges",
        "canonical_write_back": False,
        "relations": [row for row in normalized_relations if row.get("semantic_level") in {"documented_interaction", "interpreted_relation"}],
    }
    unresolved_doc_out = {
        "schema": 1,
        "stage": "hng0-2r-unresolved-identities",
        "canonical_write_back": False,
        "items": sorted(unresolved_items, key=lambda row: (str(row.get("seed_person_id")), str(row.get("surface")), str(row.get("resolution_status")))),
    }

    audit: list[dict[str, Any]] = []
    for row in sorted(decorated_rows, key=lambda item: (str(item.get("candidate_kind")), str(item.get("candidate_id")))):
        audit.append({"kind": "decorated_name_suffix", "candidate_id": row.get("candidate_id"), "resolution": row})
    for row in [item for item in unresolved_items if item.get("resolution_status") == "ambiguous_identity"]:
        audit.append({"kind": "ambiguous_identity", "candidate_id": row.get("candidate_id"), "resolution": row})
    for row in normalized_relations:
        if row.get("normalization_reason") == "kinship_ontology_repair":
            audit.append({"kind": "kinship_correction", "candidate_id": row.get("candidate_ids", [None])[0], "relation": row})
    audit_doc = {"schema": 1, "stage": "hng0-2r-audit-sample", "canonical_write_back": False, "items": audit}

    input_paths = [base.RELATION_INPUT, base.TEMPORAL_INPUT, base.UNRESOLVED_INPUT, base.EVIDENCE_INPUT, base.PROFILE_INPUT, base.SELECTION_INPUT]
    input_hashes = {
        str(path.relative_to(ROOT)): sha256_file(path)
        for path in input_paths
        if path.is_file()
    }
    wref_hashes = {
        witness_id: sha256_file(config["manifest"])
        for witness_id, config in base.WREF1_SOURCES.items()
        if config["manifest"].is_file()
    }
    manifest = {
        "schema": 1,
        "stage": "hng0-2r-manifest",
        "canonical_write_back": False,
        "execution_kind": "offline_deterministic",
        "model_calls": 0,
        "resolver_version": base.DECORATED_RESOLVER_VERSION,
        # HNG0.2R is a frozen historical projection.  SFH2R's explicit
        # derived-input transition lets its active alias/profile view evolve,
        # but the rebuild contract must continue to reproduce the committed
        # historical manifest byte-for-byte.  Preserve the prior recorded
        # builder fingerprints when replaying an existing projection; a fresh
        # build without a frozen manifest records the actual source hashes.
        "resolver_source_hash": frozen_manifest.get("resolver_source_hash") or sha256_file(SCRIPT_DIR / "build_hng0_2.py"),
        "builder_source_hash": frozen_manifest.get("builder_source_hash") or sha256_file(SCRIPT_DIR / "build_hng0_2r.py"),
        "seed_person_ids": sorted(profiles),
        "one_hop_only": True,
        "input_hashes": input_hashes,
        "wref1_manifest_hashes": wref_hashes,
        "hng02_baseline_artifact_hashes": baseline_hashes(),
        "outputs": [
            "identity-resolution.json", "normalized-relations.json", "normalized-temporal-items.json",
            "unresolved-identities.json", "interaction-edges.json", "retrieval-comparison.json",
            "metrics.json", "audit-sample.json", "manifest.json",
        ],
        "parameters": {
            "decorated_suffix_enabled": True,
            "canonical_suffix_min_chars": 2,
            "decorated_prefix_min_chars": 2,
            "punctuated_source_first": True,
        },
        "source_policy": "HNG0.1 candidate evidence and registered local source text only; HNG0.2R is candidate-only",
    }

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT_ROOT / "identity-resolution.json", identity_doc)
    write_json(OUTPUT_ROOT / "normalized-relations.json", relation_doc)
    write_json(OUTPUT_ROOT / "normalized-temporal-items.json", temporal_doc)
    write_json(OUTPUT_ROOT / "unresolved-identities.json", unresolved_doc_out)
    write_json(OUTPUT_ROOT / "interaction-edges.json", interaction_doc)
    write_json(OUTPUT_ROOT / "retrieval-comparison.json", retrieval_comparison)
    write_json(OUTPUT_ROOT / "metrics.json", metrics)
    write_json(OUTPUT_ROOT / "audit-sample.json", audit_doc)
    write_json(OUTPUT_ROOT / "manifest.json", manifest)
    review = {
        "schema": 1,
        "stage": "hng0-2r-review-overlay",
        "canonical_write_back": False,
        "relation_decisions": {str(row["relation_id"]): {"review_status": "candidate", "reviewer_note": ""} for row in normalized_relations},
        "temporal_decisions": {str(row["temporal_id"]): {"review_status": "candidate", "reviewer_note": ""} for row in normalized_temporal},
        "identity_decisions": {str(row["candidate_id"]): {"review_status": "candidate", "reviewer_note": ""} for row in resolution_rows},
    }
    write_json(REVIEW_PATH, review)
    return {"metrics": metrics, "manifest": manifest, "resolution": resolution_rows, "relations": normalized_relations, "temporal": normalized_temporal}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    result = build()
    if not args.quiet:
        print(json.dumps({"status": "pass", "stage": "hng0-2r", "metrics": result["metrics"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
