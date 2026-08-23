#!/usr/bin/env python3
"""Validate the additive HNG0.2R decorated-name projection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_hng0_2 as base  # noqa: E402
import validate_hng0_2 as validate_baseline  # noqa: E402
from hng0_1_common import quote_matches, sha256_file  # noqa: E402


OUTPUT_ROOT = ROOT / "data/generated/hng0-2r"
REVIEW = ROOT / "data/annotation/hng0-2r-review.json"
PEOPLE = ROOT / "data/people.json"

REQUIRED = (
    "identity-resolution.json",
    "normalized-relations.json",
    "normalized-temporal-items.json",
    "unresolved-identities.json",
    "interaction-edges.json",
    "retrieval-comparison.json",
    "metrics.json",
    "audit-sample.json",
    "manifest.json",
)

RESOLUTION_STATUSES = {"resolved_existing_person", "resolved_provisional_person", "unresolved_identity", "ambiguous_identity"}
RESOLUTION_METHODS = {
    "exact_name", "alias", "courtesy_name", "title", "seed_coreference", "kinship_context",
    "biography_local_context", "decorated_name_suffix", "unresolved", "ambiguous",
}
RELATION_LEVELS = {"hard_relation", "documented_interaction", "interpreted_relation"}
RELATION_TYPES = base.HARD_RELATIONS | base.DOCUMENTED_INTERACTIONS | base.INTERPRETED_RELATIONS


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(*, mode: str = "portable") -> dict[str, Any]:
    errors: list[str] = []
    docs: dict[str, Any] = {}
    for name in REQUIRED:
        path = OUTPUT_ROOT / name
        if not path.is_file():
            errors.append(f"missing HNG0.2R artifact: {name}")
        else:
            docs[name] = read(path)
    if errors:
        raise AssertionError("\n".join(errors))

    # The baseline validator is intentionally part of this gate: HNG0.2R
    # must not make an existing HNG0.2 regression invisible.
    try:
        validate_baseline.validate(mode=mode)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"HNG0.2 baseline validation failed: {exc}")

    manifest = docs["manifest.json"]
    if manifest.get("canonical_write_back") is not False or manifest.get("execution_kind") != "offline_deterministic":
        errors.append("HNG0.2R manifest is not offline candidate-only")
    if manifest.get("model_calls") != 0 or manifest.get("one_hop_only") is not True:
        errors.append("HNG0.2R permits model calls or misses one-hop marker")
    if manifest.get("resolver_version") != base.DECORATED_RESOLVER_VERSION:
        errors.append("unexpected decorated resolver version")

    baseline_hashes = manifest.get("hng02_baseline_artifact_hashes", {})
    for relative, expected in baseline_hashes.items():
        path = ROOT / relative
        if not path.is_file() or sha256_file(path) != expected:
            errors.append(f"HNG0.2 baseline artifact changed: {relative}")

    people = read(PEOPLE)
    person_ids = {str(row.get("person_id")) for row in people.get("people", []) if isinstance(row, Mapping) and row.get("person_id")}
    relation_input = read(base.RELATION_INPUT).get("relations", [])
    temporal_input = read(base.TEMPORAL_INPUT).get("temporal_items", [])
    unresolved_input = read(base.UNRESOLVED_INPUT).get("items", [])
    if len(relation_input) != 160 or len(temporal_input) != 83 or len(unresolved_input) != 157:
        errors.append("HNG0.1 frozen input counts changed")

    relation_doc = docs["normalized-relations.json"]
    temporal_doc = docs["normalized-temporal-items.json"]
    evidence: dict[str, Any] = dict(relation_doc.get("evidence", {}))
    evidence.update(temporal_doc.get("evidence", {}))
    for ref, row in evidence.items():
        path_value = str(row.get("source_path") or "")
        if "data/generated" in path_value.lower() or "model" in path_value.lower() or "deepseek" in path_value.lower():
            errors.append(f"generated/model evidence path: {ref}")
        if not row.get("source_work") or not row.get("source_layer") or not row.get("original_text"):
            errors.append(f"incomplete evidence: {ref}")
        path = ROOT / path_value
        if not path.is_file():
            errors.append(f"missing evidence source: {ref} -> {path_value}")
        elif mode == "full" and not validate_baseline.source_contains(path, str(row.get("original_text") or "")):
            errors.append(f"evidence text is not in source: {ref}")

    resolutions = docs["identity-resolution.json"].get("resolutions", [])
    resolution_ids = {str(row.get("candidate_id")) for row in resolutions if isinstance(row, Mapping)}
    if len(resolutions) != len(resolution_ids):
        errors.append("identity resolution IDs are not unique")
    for row in resolutions:
        status = row.get("resolution_status")
        method = row.get("resolution_method")
        if status not in RESOLUTION_STATUSES:
            errors.append(f"invalid identity status: {row.get('candidate_id')}")
        if method not in RESOLUTION_METHODS:
            errors.append(f"invalid identity method: {row.get('candidate_id')} -> {method}")
        if row.get("resolved_person_id") is not None and row.get("resolved_person_id") not in person_ids:
            errors.append(f"dangling resolved Person: {row.get('candidate_id')}")
        if not row.get("supporting_evidence_refs") or any(str(ref) not in evidence for ref in row.get("supporting_evidence_refs", [])):
            errors.append(f"identity evidence does not resolve: {row.get('candidate_id')}")
        if method == "decorated_name_suffix":
            for field in ("original_surface", "normalized_person_surface", "decorator_surface", "decorator_type"):
                if not row.get(field):
                    errors.append(f"decorated identity lacks {field}: {row.get('candidate_id')}")
            if row.get("decorator_type") not in base.DECORATED_DECORATOR_TYPES:
                errors.append(f"invalid decorator type: {row.get('candidate_id')}")
            if row.get("confidence") != "medium":
                errors.append(f"decorated identity confidence is not medium: {row.get('candidate_id')}")

    relation_ids: set[str] = set()
    for row in relation_doc.get("relations", []):
        rid = str(row.get("relation_id") or "")
        if not rid or rid in relation_ids:
            errors.append(f"duplicate/missing relation ID: {rid}")
        relation_ids.add(rid)
        if row.get("person_a") not in set(manifest.get("seed_person_ids", [])):
            errors.append(f"relation outside frozen seed scope: {rid}")
        if row.get("person_b") is not None and row.get("person_b") not in person_ids:
            errors.append(f"dangling relation endpoint: {rid}")
        if row.get("semantic_level") not in RELATION_LEVELS or row.get("relation_type") not in RELATION_TYPES:
            errors.append(f"invalid normalized relation: {rid}")
        if row.get("one_hop_only") is not True or row.get("review_status") != "candidate":
            errors.append(f"relation candidate markers invalid: {rid}")
        refs = row.get("evidence_refs", [])
        quotes = {str(item.get("ref")): str(item.get("quote") or "") for item in row.get("evidence_quotes", []) if isinstance(item, Mapping)}
        if not refs or any(str(ref) not in evidence for ref in refs):
            errors.append(f"relation evidence refs invalid: {rid}")
        for ref in refs:
            if not quote_matches(str(evidence[str(ref)].get("original_text") or ""), quotes.get(str(ref), "")):
                errors.append(f"relation quote invalid: {rid}/{ref}")
        if row.get("relation_type") == "grandparent_grandchild" and row.get("semantic_level") != "hard_relation":
            errors.append(f"grandparent relation not hard: {rid}")

    temporal_ids: set[str] = set()
    for row in temporal_doc.get("temporal_items", []):
        tid = str(row.get("temporal_id") or "")
        if not tid or tid in temporal_ids:
            errors.append(f"duplicate/missing temporal ID: {tid}")
        temporal_ids.add(tid)
        refs = row.get("evidence_refs", [])
        quotes = {str(item.get("ref")): str(item.get("quote") or "") for item in row.get("evidence_quotes", []) if isinstance(item, Mapping)}
        if not refs or any(str(ref) not in evidence for ref in refs):
            errors.append(f"temporal evidence refs invalid: {tid}")
        for ref in refs:
            if not quote_matches(str(evidence[str(ref)].get("original_text") or ""), quotes.get(str(ref), "")):
                errors.append(f"temporal quote invalid: {tid}/{ref}")

    review = read(REVIEW) if REVIEW.is_file() else {}
    if review.get("canonical_write_back") is not False:
        errors.append("HNG0.2R review overlay permits canonical write-back")
    if set(review.get("relation_decisions", {})) != relation_ids or set(review.get("temporal_decisions", {})) != temporal_ids or set(review.get("identity_decisions", {})) != resolution_ids:
        errors.append("HNG0.2R review overlay does not cover projection IDs")

    if errors:
        raise AssertionError("\n".join(errors))
    metrics = docs["metrics.json"]
    return {
        "status": "pass",
        "mode": mode,
        "decorated_name_suffix_count": metrics.get("decorated_name_suffix_count", 0),
        "remaining_unresolved_identity_count": metrics.get("remaining_unresolved_identity_count"),
        "remaining_ambiguous_identity_count": metrics.get("remaining_ambiguous_identity_count"),
        "normalized_relation_count": len(relation_doc.get("relations", [])),
        "normalized_temporal_count": len(temporal_doc.get("temporal_items", [])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("portable", "full"), default="portable")
    args = parser.parse_args()
    print(json.dumps(validate(mode=args.mode), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
