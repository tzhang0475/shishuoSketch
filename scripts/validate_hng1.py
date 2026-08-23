#!/usr/bin/env python3
"""Validate the HNG1 fresh-person, candidate-only projection."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_hng0_2 as hng02  # noqa: E402
import validate_hng0_2 as baseline  # noqa: E402
from hng0_1_common import quote_matches, sha256_file  # noqa: E402

OUTPUT = ROOT / "data/generated/hng1"
REVIEW = ROOT / "data/annotation/hng1-review.json"
PEOPLE = ROOT / "data/people.json"
HNG0_SELECTION = ROOT / "data/generated/hng0/hng0-selection.json"

REQUIRED = (
    "hng1-selection.json", "search-profiles.json", "retrieval-trace.json", "source-evidence-registry.json",
    "identity-resolution.json", "relations.json", "temporal-items.json", "neighborhoods.json",
    "unresolved-identities.json", "audit-sample.json", "metrics.json", "manifest.json",
)
RELATION_LEVELS = {"hard_relation", "documented_interaction", "interpreted_relation"}
RELATION_TYPES = hng02.HARD_RELATIONS | hng02.DOCUMENTED_INTERACTIONS | hng02.INTERPRETED_RELATIONS
RESOLUTION_STATUSES = {"resolved_existing_person", "resolved_provisional_person", "unresolved_identity", "ambiguous_identity"}
RESOLUTION_METHODS = {
    "exact_name", "alias", "courtesy_name", "title", "seed_coreference", "kinship_context",
    "biography_local_context", "decorated_name_suffix", "unresolved", "ambiguous",
}


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(*, mode: str = "portable") -> dict[str, Any]:
    errors: list[str] = []
    docs: dict[str, Any] = {}
    for name in REQUIRED:
        path = OUTPUT / name
        if not path.is_file():
            errors.append(f"missing HNG1 artifact: {name}")
        else:
            docs[name] = read(path)
    if errors:
        raise AssertionError("\n".join(errors))

    selection = docs["hng1-selection.json"]
    manifest = docs["manifest.json"]
    metrics = docs["metrics.json"]
    people = read(PEOPLE)
    person_ids = {str(row.get("person_id")) for row in people.get("people", []) if isinstance(row, Mapping) and row.get("person_id")}
    hng0_ids = {str(row.get("person_id")) for row in read(HNG0_SELECTION).get("people", []) if row.get("person_id")}
    selected = [str(row.get("person_id")) for row in selection.get("people", []) if row.get("person_id")]
    selected_set = set(selected)
    if not selection.get("frozen") or selection.get("canonical_write_back") is not False:
        errors.append("HNG1 selection is not frozen candidate-only")
    if not 30 <= len(selected) <= 50 or len(selected) != len(selected_set):
        errors.append(f"invalid fresh seed count: {len(selected)}")
    if not selected_set <= person_ids or selected_set & hng0_ids:
        errors.append("fresh HNG1 selection contains dangling or HNG0 seed Person")
    strata_counts = {name: sum(1 for row in selection.get("people", []) if row.get("stratum") == name) for name in ("high_connectivity", "medium_connectivity", "low_connectivity")}
    if strata_counts != selection.get("strata"):
        errors.append("HNG1 strata counts do not match frozen selection")
    if not selection.get("one_hop_only"):
        errors.append("selection misses one-hop marker")
    if manifest.get("selection_hash") != hashlib.sha256(json.dumps(selection, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest():
        errors.append("manifest selection hash mismatch")
    if manifest.get("resolver_version") != hng02.DECORATED_RESOLVER_VERSION:
        errors.append("HNG1 resolver version is not frozen HNG0.2R")
    if manifest.get("resolver_source_hash") != sha256_file(SCRIPT_DIR / "build_hng0_2.py"):
        errors.append("HNG1 resolver source hash mismatch")
    if manifest.get("hng02r_manifest_hash") != sha256_file(ROOT / "data/generated/hng0-2r/manifest.json"):
        errors.append("HNG0.2R manifest hash mismatch")
    if manifest.get("canonical_write_back") is not False or manifest.get("one_hop_only") is not True:
        errors.append("HNG1 manifest is not candidate-only/one-hop")

    profiles = docs["search-profiles.json"].get("profiles", {})
    if set(profiles) != selected_set:
        errors.append("search profile scope differs from frozen fresh selection")
    for pid, profile in profiles.items():
        if profile.get("seed") is not True or profile.get("one_hop_only") is not True:
            errors.append(f"invalid profile scope: {pid}")

    evidence = docs["source-evidence-registry.json"].get("evidence", {})
    for ref, row in evidence.items():
        path_value = str(row.get("source_path") or "")
        lowered = path_value.lower()
        if "data/generated" in lowered or "model" in lowered or "deepseek" in lowered:
            errors.append(f"generated/model evidence path: {ref}")
        if not row.get("source_work") or not row.get("source_layer") or not row.get("original_text"):
            errors.append(f"incomplete evidence provenance: {ref}")
        path = ROOT / path_value
        if not path.is_file():
            errors.append(f"missing evidence source: {ref} -> {path_value}")
        elif mode == "full" and not baseline.source_contains(path, str(row.get("original_text") or "")):
            errors.append(f"evidence source mismatch: {ref}")
        if row.get("source_form") not in {"punctuated", "legacy_local", "both"}:
            errors.append(f"invalid source form: {ref}")

    relation_doc = docs["relations.json"]
    temporal_doc = docs["temporal-items.json"]
    relation_ids: set[str] = set()
    for row in relation_doc.get("relations", []):
        rid = str(row.get("relation_id") or "")
        if not rid or rid in relation_ids:
            errors.append(f"duplicate/missing relation ID: {rid}")
        relation_ids.add(rid)
        if row.get("person_a") not in selected_set:
            errors.append(f"relation is not rooted at a fresh seed: {rid}")
        if row.get("person_b") is not None and row.get("person_b") not in person_ids:
            errors.append(f"dangling canonical relation endpoint: {rid}")
        if row.get("semantic_level") not in RELATION_LEVELS or row.get("normalized_relation_type") not in RELATION_TYPES:
            errors.append(f"invalid normalized relation: {rid}")
        if row.get("cooccurrence_only") is True or row.get("one_hop_only") is not True or row.get("review_status") != "candidate":
            errors.append(f"relation violates candidate/one-hop policy: {rid}")
        refs = row.get("evidence_refs", [])
        quotes = {str(item.get("ref")): str(item.get("quote") or "") for item in row.get("evidence_quotes", []) if isinstance(item, Mapping)}
        if not refs or any(str(ref) not in evidence for ref in refs):
            errors.append(f"relation lacks valid evidence refs: {rid}")
        for ref in refs:
            if not quote_matches(str(evidence[str(ref)].get("original_text") or ""), quotes.get(str(ref), "")):
                errors.append(f"relation quote invalid: {rid}/{ref}")
        if row.get("normalized_relation_type") == "grandparent_grandchild" and row.get("semantic_level") != "hard_relation":
            errors.append(f"grandparent relation lost hard level: {rid}")
        if row.get("normalized_relation_type") == "same_clan" and any(marker in str(row.get("claim") or "") for marker in ("祖", "孫", "祖父", "孫也")):
            errors.append(f"grandparent claim collapsed into same_clan: {rid}")

    temporal_ids: set[str] = set()
    for row in temporal_doc.get("temporal_items", []):
        tid = str(row.get("temporal_id") or "")
        if not tid or tid in temporal_ids:
            errors.append(f"duplicate/missing temporal ID: {tid}")
        temporal_ids.add(tid)
        if row.get("person_id") not in selected_set and not str(row.get("provisional_subject_id") or "").startswith("hng02-provisional-"):
            errors.append(f"temporal item outside fresh seed/one-hop scope: {tid}")
        refs = row.get("evidence_refs", [])
        quotes = {str(item.get("ref")): str(item.get("quote") or "") for item in row.get("evidence_quotes", []) if isinstance(item, Mapping)}
        if not refs or any(str(ref) not in evidence for ref in refs):
            errors.append(f"temporal item lacks valid evidence refs: {tid}")
        for ref in refs:
            if not quote_matches(str(evidence[str(ref)].get("original_text") or ""), quotes.get(str(ref), "")):
                errors.append(f"temporal quote invalid: {tid}/{ref}")

    resolutions = docs["identity-resolution.json"].get("resolutions", [])
    resolution_ids = {str(row.get("candidate_id")) for row in resolutions if row.get("candidate_id")}
    for row in resolutions:
        if row.get("resolution_status") not in RESOLUTION_STATUSES or row.get("resolution_method") not in RESOLUTION_METHODS:
            errors.append(f"invalid identity resolution: {row.get('candidate_id')}")
        if row.get("resolved_person_id") is not None and row.get("resolved_person_id") not in person_ids:
            errors.append(f"identity resolves to dangling Person: {row.get('candidate_id')}")
        if not row.get("supporting_evidence_refs") or any(str(ref) not in evidence for ref in row.get("supporting_evidence_refs", [])):
            errors.append(f"identity lacks evidence: {row.get('candidate_id')}")

    unresolved = docs["unresolved-identities.json"].get("items", [])
    if any(row.get("resolution_status") not in {"unresolved_identity", "ambiguous_identity"} for row in unresolved):
        errors.append("resolved identity entered unresolved projection")

    # Raw output hashes make accidental replacement visible.  If no raw files
    # exist after an environment preflight failure, the empty set is correct.
    expected_raw = manifest.get("raw_extraction_hashes", {})
    actual_raw = {str(path.relative_to(OUTPUT)): sha256_file(path) for path in sorted((OUTPUT / "raw-extractions").glob("*.json")) if path.is_file()}
    if actual_raw != expected_raw:
        errors.append("raw extraction hashes do not match manifest")

    review = read(REVIEW) if REVIEW.is_file() else {}
    if review.get("canonical_write_back") is not False:
        errors.append("HNG1 review overlay permits canonical write-back")
    if set(review.get("relation_decisions", {})) != relation_ids or set(review.get("temporal_decisions", {})) != temporal_ids or set(review.get("identity_decisions", {})) != resolution_ids:
        errors.append("HNG1 review overlay does not cover output IDs")

    if errors:
        raise AssertionError("\n".join(errors))
    return {
        "status": "pass",
        "mode": mode,
        "execution_kind": manifest.get("execution_kind"),
        "seed_count": len(selected),
        "relation_count": len(relation_doc.get("relations", [])),
        "temporal_count": len(temporal_doc.get("temporal_items", [])),
        "identity_occurrence_count": len(resolutions),
        "protocol_failure_count": metrics.get("protocol_failure_count", 0),
        "semantic_failure_count": metrics.get("semantic_failure_count", 0),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("portable", "full"), default="portable")
    args = parser.parse_args()
    print(json.dumps(validate(mode=args.mode), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
