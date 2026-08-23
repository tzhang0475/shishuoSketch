#!/usr/bin/env python3
"""Validate the HNG1R2 full offline identity replay."""

from __future__ import annotations

import argparse
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
from hng1r_common import hash_tree  # noqa: E402
from hng1r2_common import (  # noqa: E402
    GENERIC_ROLE_SURFACES,
    HNG1_ROOT,
    HNG1R_ROOT,
    RESOLVER_VERSION,
)


OUTPUT_ROOT = ROOT / "data/generated/hng1r2"
REVIEW_PATH = ROOT / "data/annotation/hng1r2-review.json"
HNG1_REVIEW_PATH = ROOT / "data/annotation/hng1-review.json"
HNG1R_REVIEW_PATH = ROOT / "data/annotation/hng1r-review.json"
REQUIRED = (
    "identity-resolution.json",
    "relations.json",
    "temporal-items.json",
    "resolution-changes.json",
    "false-split-repairs.json",
    "false-merge-repairs.json",
    "unresolved-identities.json",
    "audit-sample.json",
    "hng2-readiness.json",
    "metrics.json",
    "manifest.json",
)
ALLOWED_STATUSES = {
    "resolved_existing_person", "resolved_provisional_person",
    "unresolved_identity", "ambiguous_identity",
}
ALLOWED_REVIEW = {"correct", "false_merge", "false_split", "uncertain", "not_reviewed"}


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(*, mode: str = "portable") -> dict[str, Any]:
    errors: list[str] = []
    docs: dict[str, Any] = {}
    for name in REQUIRED:
        path = OUTPUT_ROOT / name
        if not path.is_file():
            errors.append(f"missing HNG1R2 artifact: {name}")
        else:
            docs[name] = _read(path)
    if errors:
        raise AssertionError("\n".join(errors))

    manifest = docs["manifest.json"]
    metrics = docs["metrics.json"]
    if manifest.get("execution_kind") != "offline_deterministic" or manifest.get("model_calls") != 0 or manifest.get("api_calls") != 0:
        errors.append("HNG1R2 is not an offline zero-call replay")
    if manifest.get("canonical_write_back") is not False or manifest.get("one_hop_only") is not True:
        errors.append("HNG1R2 scope/write boundary is invalid")
    if manifest.get("resolver_version") != RESOLVER_VERSION:
        errors.append("HNG1R2 resolver version mismatch")
    if manifest.get("resolver_catalog") != "build_hng0_2.person_catalog" or manifest.get("forms_index") != "build_hng0_2.forms_index":
        errors.append("HNG1R2 does not declare the schema-consistent resolver catalogue")
    if manifest.get("base_resolver") != "build_hng0_2.resolution_for_candidate":
        errors.append("HNG1R2 base resolver declaration is invalid")
    if manifest.get("person_specific_rules") is not False:
        errors.append("HNG1R2 declares person-specific rules")
    if manifest.get("resolver_source_hash") != sha256_file(SCRIPT_DIR / "hng1r2_common.py"):
        errors.append("HNG1R2 resolver source hash is stale")
    if manifest.get("hng1_artifact_hashes") != hash_tree(HNG1_ROOT):
        errors.append("HNG1 is not byte-identical to the frozen replay input")
    if manifest.get("hng1r_artifact_hashes") != hash_tree(HNG1R_ROOT):
        errors.append("HNG1R is not byte-identical to the frozen replay input")
    if manifest.get("hng1_review_hash") is not None and (
        not HNG1_REVIEW_PATH.is_file() or manifest.get("hng1_review_hash") != sha256_file(HNG1_REVIEW_PATH)
    ):
        errors.append("HNG1 review overlay changed")
    if manifest.get("hng1r_review_hash") is not None and (
        not HNG1R_REVIEW_PATH.is_file() or manifest.get("hng1r_review_hash") != sha256_file(HNG1R_REVIEW_PATH)
    ):
        errors.append("HNG1R review overlay changed")

    people = _read(ROOT / "data/people.json")
    person_ids = {
        str(row.get("person_id"))
        for row in people.get("people", [])
        if isinstance(row, Mapping) and row.get("person_id")
    }
    catalog = hng02.person_catalog()
    exact_index = hng02.forms_index(catalog)
    generic = {hng02.lookup(value) for value in GENERIC_ROLE_SURFACES}
    evidence = _read(HNG1_ROOT / "source-evidence-registry.json").get("evidence", {})
    frozen_ids = {
        str(row.get("candidate_id"))
        for row in _read(HNG1_ROOT / "identity-resolution.json").get("resolutions", [])
    }
    resolutions = docs["identity-resolution.json"].get("resolutions", [])
    resolution_map: dict[str, Mapping[str, Any]] = {}
    for row in resolutions:
        cid = str(row.get("candidate_id") or "")
        if not cid or cid in resolution_map:
            errors.append(f"duplicate/missing identity candidate_id: {cid}")
        resolution_map[cid] = row
        if row.get("resolution_status") not in ALLOWED_STATUSES:
            errors.append(f"invalid resolution status: {cid}")
        if row.get("resolved_person_id") is not None and row.get("resolved_person_id") not in person_ids:
            errors.append(f"dangling resolved Person: {cid}")
        refs = [str(ref) for ref in row.get("supporting_evidence_refs", []) if ref]
        if not refs or any(ref not in evidence for ref in refs):
            errors.append(f"identity evidence does not resolve: {cid}")
        surface = str(row.get("surface") or "")
        folded = hng02.lookup(surface)
        if folded in generic and row.get("resolution_status") != "unresolved_identity":
            errors.append(f"generic role surface did not fail closed: {cid}/{surface}")
        exact = list(exact_index.get(folded, []))
        if folded not in generic and len(exact) == 1:
            if row.get("resolution_status") != "resolved_existing_person" or row.get("resolved_person_id") != exact[0]:
                errors.append(f"unique exact catalogue form did not resolve: {cid}/{surface}")
        if row.get("resolution_method") == "contextual_short_name":
            if not 1 <= len(folded) <= 2 or row.get("resolution_status") != "resolved_existing_person":
                errors.append(f"invalid contextual short-name resolution: {cid}")
            if not row.get("candidate_set") or row.get("resolved_person_id") not in row.get("candidate_set", []):
                errors.append(f"contextual candidate set mismatch: {cid}")
            if not row.get("context_signals"):
                errors.append(f"contextual short-name lacks deterministic signals: {cid}")
        if not row.get("local_resolver_context"):
            errors.append(f"identity lacks local resolver context: {cid}")
        for context in row.get("local_resolver_context", []):
            ref = str(context.get("ref") or "")
            quote = str(context.get("exact_quote") or "")
            local = str(context.get("local_context") or "")
            if ref not in evidence:
                errors.append(f"local context ref is unknown: {cid}/{ref}")
            elif quote and not quote_matches(str(evidence[ref].get("original_text") or ""), quote):
                errors.append(f"identity exact quote is invalid: {cid}/{ref}")
            if quote and not quote_matches(local, quote):
                errors.append(f"local context omits exact quote: {cid}/{ref}")
    if set(resolution_map) != frozen_ids or len(resolutions) != 103:
        errors.append("HNG1R2 did not replay exactly all frozen HNG1 identity occurrences")

    kinship_regressions = [
        row for row in resolutions
        if row.get("surface") == "敦"
        and any("從父兄敦" in str(context.get("exact_quote") or "") for context in row.get("local_resolver_context", []))
    ]
    if len(kinship_regressions) != 1:
        errors.append("missing unique 卞壼/從父兄敦 regression occurrence")
    else:
        row = kinship_regressions[0]
        if row.get("resolved_person_id") == "person-011" or row.get("resolution_method") != "kinship_context":
            errors.append("卞壼從父兄敦 incorrectly resolves to 王敦")

    for row in docs["relations.json"].get("relations", []):
        rid = str(row.get("relation_id") or "")
        if row.get("person_b") is not None and row.get("person_b") not in person_ids:
            errors.append(f"dangling relation person_b: {rid}")
        if row.get("review_status") != "candidate" or row.get("one_hop_only") is not True:
            errors.append(f"relation escaped candidate/one-hop scope: {rid}")
        identity = row.get("identity_resolution") if isinstance(row.get("identity_resolution"), Mapping) else {}
        if identity.get("resolution_status") == "resolved_existing_person" and row.get("person_b") != identity.get("resolved_person_id"):
            errors.append(f"relation endpoint does not reflect identity replay: {rid}")
        for item in row.get("evidence_quotes", []):
            ref = str(item.get("ref") or "")
            if ref not in evidence or not quote_matches(str(evidence.get(ref, {}).get("original_text") or ""), str(item.get("quote") or "")):
                errors.append(f"relation evidence quote invalid: {rid}/{ref}")

    for row in docs["temporal-items.json"].get("temporal_items", []):
        tid = str(row.get("temporal_id") or "")
        if row.get("person_id") is not None and row.get("person_id") not in person_ids:
            errors.append(f"dangling temporal Person: {tid}")
        identity = row.get("identity_resolution") if isinstance(row.get("identity_resolution"), Mapping) else {}
        if identity.get("resolution_status") == "resolved_existing_person" and row.get("person_id") != identity.get("resolved_person_id"):
            errors.append(f"temporal subject does not reflect identity replay: {tid}")
        for item in row.get("evidence_quotes", []):
            ref = str(item.get("ref") or "")
            if ref not in evidence or not quote_matches(str(evidence.get(ref, {}).get("original_text") or ""), str(item.get("quote") or "")):
                errors.append(f"temporal evidence quote invalid: {tid}/{ref}")

    false_splits = docs["false-split-repairs.json"].get("repairs", [])
    false_merges = docs["false-merge-repairs.json"].get("repairs", [])
    if metrics.get("false_split_repair_count") != len(false_splits):
        errors.append("false-split metric mismatch")
    if metrics.get("false_merge_repair_count") != len(false_merges):
        errors.append("false-merge metric mismatch")
    if not any(row.get("surface") == "敦" and row.get("incorrect_person_id") == "person-011" for row in false_merges):
        errors.append("known HNG1R false merge is not recorded as repaired")

    audit = docs["audit-sample.json"].get("items", [])
    audit_ids = {str(row.get("audit_id")) for row in audit}
    if len(audit_ids) != len(audit):
        errors.append("duplicate HNG1R2 audit IDs")
    for row in audit:
        if row.get("review") not in ALLOWED_REVIEW or row.get("canonical_write_back") is not False:
            errors.append(f"invalid audit review boundary: {row.get('audit_id')}")
        if not row.get("exact_quote") or not row.get("local_resolver_context"):
            errors.append(f"audit lacks exact quote/local resolver context: {row.get('audit_id')}")
        if "model_snippet" in row:
            errors.append(f"audit exposes model_snippet as primary passage: {row.get('audit_id')}")
    review = _read(REVIEW_PATH) if REVIEW_PATH.is_file() else {}
    decisions = review.get("identity_decisions", {})
    if set(decisions) != audit_ids or any(value not in ALLOWED_REVIEW for value in decisions.values()):
        errors.append("HNG1R2 review overlay does not exactly cover the audit")
    if review.get("canonical_write_back") is not False:
        errors.append("HNG1R2 review permits canonical write-back")

    readiness = docs["hng2-readiness.json"]
    if readiness.get("ready_for_hng2") is not False or readiness.get("readiness_status") != "awaiting_meaningful_human_audit":
        errors.append("HNG2 readiness was auto-approved")
    if readiness.get("reviewed_identity_count") != sum(value != "not_reviewed" for value in decisions.values()):
        errors.append("readiness reviewed count mismatch")
    if metrics.get("identity_occurrence_count") != len(resolutions) or metrics.get("model_calls") != 0 or metrics.get("api_calls") != 0:
        errors.append("HNG1R2 metrics are inconsistent")

    if errors:
        raise AssertionError("\n".join(errors))
    counts = metrics.get("status_counts_hng1r2", {})
    return {
        "status": "pass",
        "mode": mode,
        "identity_occurrences": len(resolutions),
        "resolved_existing_person": counts.get("resolved_existing_person", 0),
        "resolved_provisional_person": counts.get("resolved_provisional_person", 0),
        "unresolved_identity": counts.get("unresolved_identity", 0),
        "ambiguous_identity": counts.get("ambiguous_identity", 0),
        "false_split_repairs": len(false_splits),
        "false_merge_repairs": len(false_merges),
        "relation_changes": metrics.get("relation_projection_change_count", 0),
        "audit_items": len(audit),
        "model_calls": 0,
        "hng1_unchanged": True,
        "hng1r_unchanged": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("portable", "full"), default="portable")
    args = parser.parse_args()
    print(json.dumps(validate(mode=args.mode), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
