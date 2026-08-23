#!/usr/bin/env python3
"""Validate the HNG1R offline identity-audit projection."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_hng0_2 as hng02  # noqa: E402
from hng0_1_common import quote_matches, sha256_file  # noqa: E402
from hng1r_common import (  # noqa: E402
    CONTEXTUAL_SHORT_RESOLVER_VERSION,
    GENERIC_ROLE_SURFACES,
    HNG1_ROOT,
    hng1_hashes,
    read_json,
)


OUTPUT = ROOT / "data/generated/hng1r"
REVIEW = ROOT / "data/annotation/hng1r-review.json"
PEOPLE = ROOT / "data/people.json"

REQUIRED = (
    "identity-resolution.json",
    "relations.json",
    "temporal-items.json",
    "unresolved-identities.json",
    "neighborhoods.json",
    "audit-sample.json",
    "hng2-readiness.json",
    "metrics.json",
    "manifest.json",
)
ALLOWED_REVIEW = {"correct", "false_merge", "uncertain", "not_reviewed"}
ALLOWED_STATUSES = {"resolved_existing_person", "resolved_provisional_person", "unresolved_identity", "ambiguous_identity"}


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(*, mode: str = "portable") -> dict[str, Any]:
    errors: list[str] = []
    docs: dict[str, Any] = {}
    for name in REQUIRED:
        path = OUTPUT / name
        if not path.is_file():
            errors.append(f"missing HNG1R artifact: {name}")
        else:
            docs[name] = _read(path)
    if errors:
        raise AssertionError("\n".join(errors))

    manifest = docs["manifest.json"]
    metrics = docs["metrics.json"]
    if manifest.get("execution_kind") != "offline_deterministic" or manifest.get("model_calls") != 0:
        errors.append("HNG1R is not offline/model-free")
    if manifest.get("canonical_write_back") is not False or manifest.get("one_hop_only") is not True:
        errors.append("HNG1R is not candidate-only one-hop data")
    if manifest.get("resolver_version") != CONTEXTUAL_SHORT_RESOLVER_VERSION:
        errors.append("unexpected contextual resolver version")
    if manifest.get("base_resolver_version") != hng02.DECORATED_RESOLVER_VERSION:
        errors.append("HNG0.2R base resolver version mismatch")
    if manifest.get("hng1_manifest_hash") != sha256_file(HNG1_ROOT / "manifest.json"):
        errors.append("HNG1 manifest changed or hash is stale")
    if manifest.get("hng1_artifact_hashes") != hng1_hashes():
        errors.append("HNG1 artifacts changed after HNG1R replay")
    if manifest.get("hng1_review_hash") is not None:
        review_path = ROOT / "data/annotation/hng1-review.json"
        if not review_path.is_file() or manifest.get("hng1_review_hash") != sha256_file(review_path):
            errors.append("HNG1 review overlay changed after HNG1R replay")

    people = _read(PEOPLE)
    person_ids = {
        str(row.get("person_id"))
        for row in people.get("people", [])
        if isinstance(row, Mapping) and row.get("person_id")
    }
    evidence = _read(HNG1_ROOT / "source-evidence-registry.json").get("evidence", {})
    resolutions = docs["identity-resolution.json"].get("resolutions", [])
    resolution_ids: set[str] = set()
    for row in resolutions:
        candidate_id = str(row.get("candidate_id") or "")
        if not candidate_id or candidate_id in resolution_ids:
            errors.append(f"duplicate/missing identity candidate_id: {candidate_id}")
        resolution_ids.add(candidate_id)
        if row.get("resolution_status") not in ALLOWED_STATUSES:
            errors.append(f"invalid identity status: {candidate_id}")
        if row.get("resolved_person_id") is not None and row.get("resolved_person_id") not in person_ids:
            errors.append(f"dangling resolved Person: {candidate_id}")
        if row.get("resolution_method") == "contextual_short_name":
            surface = str(row.get("original_surface") or row.get("surface") or "")
            if not 1 <= len(hng02.lookup(surface)) <= 2:
                errors.append(f"contextual resolver used on non-short surface: {candidate_id}")
            if hng02.lookup(surface) in {hng02.lookup(value) for value in GENERIC_ROLE_SURFACES}:
                errors.append(f"generic role surface resolved contextually: {candidate_id}")
            candidates = row.get("candidate_set", [])
            if row.get("resolution_status") != "resolved_existing_person" or len(row.get("matches", [])) != 1:
                errors.append(f"contextual resolution is not unique: {candidate_id}")
            if not candidates or row.get("resolved_person_id") not in candidates:
                errors.append(f"contextual candidate set mismatch: {candidate_id}")
            if not row.get("context_signals"):
                errors.append(f"contextual resolution lacks signals: {candidate_id}")
        if not row.get("supporting_evidence_refs"):
            errors.append(f"identity lacks evidence refs: {candidate_id}")
        for ref in row.get("supporting_evidence_refs", []):
            if str(ref) not in evidence:
                errors.append(f"identity evidence ref missing: {candidate_id}/{ref}")

    relation_doc = docs["relations.json"]
    relation_ids: set[str] = set()
    for row in relation_doc.get("relations", []):
        rid = str(row.get("relation_id") or "")
        if not rid or rid in relation_ids:
            errors.append(f"duplicate/missing relation ID: {rid}")
        relation_ids.add(rid)
        if row.get("person_b") is not None and row.get("person_b") not in person_ids:
            errors.append(f"dangling relation endpoint: {rid}")
        if row.get("one_hop_only") is not True or row.get("review_status") != "candidate":
            errors.append(f"relation scope/status violation: {rid}")
        refs = [str(ref) for ref in row.get("evidence_refs", []) if ref]
        if not refs or any(ref not in evidence for ref in refs):
            errors.append(f"relation evidence missing: {rid}")
        quotes = {
            str(item.get("ref")): str(item.get("quote") or "")
            for item in row.get("evidence_quotes", [])
            if isinstance(item, Mapping)
        }
        for ref in refs:
            if not quote_matches(str(evidence[ref].get("original_text") or ""), quotes.get(ref, "")):
                errors.append(f"relation quote invalid: {rid}/{ref}")

    temporal_ids: set[str] = set()
    for row in docs["temporal-items.json"].get("temporal_items", []):
        tid = str(row.get("temporal_id") or "")
        if not tid or tid in temporal_ids:
            errors.append(f"duplicate/missing temporal ID: {tid}")
        temporal_ids.add(tid)
        refs = [str(ref) for ref in row.get("evidence_refs", []) if ref]
        if not refs or any(ref not in evidence for ref in refs):
            errors.append(f"temporal evidence missing: {tid}")
        quotes = {
            str(item.get("ref")): str(item.get("quote") or "")
            for item in row.get("evidence_quotes", [])
            if isinstance(item, Mapping)
        }
        for ref in refs:
            if not quote_matches(str(evidence[ref].get("original_text") or ""), quotes.get(ref, "")):
                errors.append(f"temporal quote invalid: {tid}/{ref}")

    unresolved = docs["unresolved-identities.json"].get("items", [])
    if any(row.get("resolution_status") not in {"unresolved_identity", "ambiguous_identity"} for row in unresolved):
        errors.append("resolved identity entered unresolved projection")

    audit = docs["audit-sample.json"].get("items", [])
    audit_ids = {str(row.get("audit_id")) for row in audit}
    if len(audit_ids) != len(audit):
        errors.append("duplicate audit IDs")
    for row in audit:
        if row.get("review") not in ALLOWED_REVIEW:
            errors.append(f"invalid audit review field: {row.get('audit_id')}")
        if row.get("canonical_write_back") is not False:
            errors.append(f"audit permits canonical write-back: {row.get('audit_id')}")
        if not row.get("source_passages") or not row.get("extracted_surface"):
            errors.append(f"incomplete audit record: {row.get('audit_id')}")
        for passage in row.get("source_passages", []):
            ref = str(passage.get("ref") or "")
            if ref not in evidence:
                errors.append(f"audit evidence ref missing: {row.get('audit_id')}/{ref}")
            elif passage.get("quote") and not quote_matches(str(evidence[ref].get("original_text") or ""), str(passage.get("quote"))):
                errors.append(f"audit quote invalid: {row.get('audit_id')}/{ref}")

    review = _read(REVIEW) if REVIEW.is_file() else {}
    decisions = review.get("identity_decisions", {})
    if set(decisions) != audit_ids:
        errors.append("review overlay does not cover audit IDs")
    if any(value not in ALLOWED_REVIEW for value in decisions.values()):
        errors.append("review overlay contains an invalid decision")
    if review.get("canonical_write_back") is not False:
        errors.append("review overlay permits canonical write-back")

    readiness = docs["hng2-readiness.json"]
    if readiness.get("canonical_write_back") is not False or readiness.get("ready_for_hng2") is not False:
        errors.append("readiness report auto-approves HNG2")
    if readiness.get("reviewed_identity_count") != sum(value != "not_reviewed" for value in decisions.values()):
        errors.append("readiness reviewed count mismatch")
    if metrics.get("model_calls") != 0 or metrics.get("execution_kind") != "offline_deterministic":
        errors.append("metrics report model execution")
    if metrics.get("input_identity_occurrence_count") != len(resolutions):
        errors.append("metrics identity count mismatch")
    if metrics.get("unresolved_occurrences_after") != sum(row.get("resolution_status") == "unresolved_identity" for row in resolutions):
        errors.append("metrics unresolved count mismatch")

    if errors:
        raise AssertionError("\n".join(errors))
    return {
        "status": "pass",
        "mode": mode,
        "execution_kind": manifest.get("execution_kind"),
        "model_calls": manifest.get("model_calls"),
        "identity_occurrences": len(resolutions),
        "contextual_short_name_count": metrics.get("contextual_short_name_count", 0),
        "unresolved_before": metrics.get("unresolved_occurrences_before"),
        "unresolved_after": metrics.get("unresolved_occurrences_after"),
        "ambiguous_after": metrics.get("ambiguous_cases_after"),
        "relation_changes": metrics.get("relation_change_count", 0),
        "audit_items": len(audit),
        "hng1_unchanged": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("portable", "full"), default="portable")
    args = parser.parse_args()
    print(json.dumps(validate(mode=args.mode), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
