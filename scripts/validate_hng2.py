#!/usr/bin/env python3
"""Validate the generated HNG2 research layer without external services."""

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

from hng0_1_common import sha256_file  # noqa: E402
from historical_entity_resolver import RESOLVER_VERSION, is_generic_role, matching_normalize, person_catalog  # noqa: E402

OUT = ROOT / "data/generated/hng2"
REVIEW = ROOT / "data/annotation/hng2-review.json"
REQUIRED = [
    "frontier-selection.json", "frontier-wave-1.json", "frontier-wave-2.json", "retrieval-trace.json",
    "temporal-gate-decisions.json", "identity-resolution.json", "contextual-identity-registry.json", "identity-llm-assist.json", "identity-graph-support.json",
    "provisional-persons.json", "consolidation-candidates.json", "relations.json", "temporal-items.json", "neighborhoods.json",
    "rejected-passages.json", "unresolved-identities.json", "ambiguous-identities.json", "audit-sample.json", "metrics.json", "manifest.json",
]


class ValidationError(Exception):
    pass


def read(name: str) -> dict[str, Any]:
    path = OUT / name
    if not path.is_file():
        raise ValidationError(f"missing HNG2 artifact: {name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"artifact is not an object: {name}")
    return value


def hash_tree(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {str(p.relative_to(root)): sha256_file(p) for p in sorted(root.rglob("*")) if p.is_file()}


def _source_evidence() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name in ("relations.json", "temporal-items.json"):
        doc = json.loads((ROOT / "data/generated/hng1r2" / name).read_text(encoding="utf-8"))
        for ref, row in (doc.get("evidence", {}) or {}).items():
            if isinstance(row, Mapping):
                result[str(ref)] = dict(row)
    return result


def validate(*, mode: str = "portable") -> list[str]:
    errors: list[str] = []
    for name in REQUIRED:
        if not (OUT / name).is_file():
            errors.append(f"missing:{name}")
    if errors:
        return errors
    try:
        manifest = read("manifest.json")
        identities = read("identity-resolution.json").get("resolutions", [])
        relations = read("relations.json").get("relations", [])
        temporal = read("temporal-items.json").get("temporal_items", [])
        frontiers = read("frontier-selection.json").get("frontiers", [])
        wave1 = read("frontier-wave-1.json")
        wave2 = read("frontier-wave-2.json")
        traces = read("retrieval-trace.json").get("records", [])
        gates = read("temporal-gate-decisions.json").get("decisions", [])
        llm = read("identity-llm-assist.json")
        graph = read("identity-graph-support.json")
        review = json.loads(REVIEW.read_text(encoding="utf-8")) if REVIEW.is_file() else {}
    except Exception as exc:
        return [f"read_error:{type(exc).__name__}:{exc}"]

    if manifest.get("resolver_version") != RESOLVER_VERSION:
        errors.append("resolver_version_mismatch")
    if manifest.get("canonical_write_back") is not False:
        errors.append("manifest_canonical_write_back")
    if llm.get("model_calls") != 0 or llm.get("api_calls") != 0:
        errors.append("unexpected_llm_calls_in_offline_projection")
    if manifest.get("model", {}).get("model_calls") != 0:
        errors.append("manifest_model_calls_nonzero")
    if wave2.get("wave_3_created") is not False:
        errors.append("wave3_created")
    if wave2.get("wave") != 2 or wave1.get("wave") != 1:
        errors.append("wave_number_invalid")
    if any(int(row.get("wave") or 0) > 2 for row in [*frontiers, *wave1.get("frontiers", []), *wave2.get("frontiers", []), *relations, *temporal]):
        errors.append("third_wave_record_present")

    catalog = person_catalog()
    person_ids = set(catalog)
    occurrence_ids = [str(row.get("occurrence_id") or "") for row in identities]
    if len(occurrence_ids) != len(set(occurrence_ids)):
        errors.append("duplicate_identity_occurrence")
    expected = len(json.loads((ROOT / "data/generated/hng1r2/identity-resolution.json").read_text(encoding="utf-8")).get("resolutions", []))
    if len(identities) != expected:
        errors.append(f"identity_coverage:{len(identities)}!={expected}")

    source_evidence = _source_evidence()
    valid_refs: set[str] = set()
    for row in [*relations, *temporal]:
        if row.get("canonical_write_back") is not False:
            errors.append(f"canonical_write_back:{row.get('relation_id') or row.get('temporal_id')}")
        if row.get("one_hop_only") is not True:
            errors.append(f"not_one_hop:{row.get('relation_id') or row.get('temporal_id')}")
        if not row.get("evidence_refs"):
            errors.append(f"no_evidence:{row.get('relation_id') or row.get('temporal_id')}")
        for item in row.get("evidence_quotes", []):
            if not isinstance(item, Mapping):
                errors.append("malformed_evidence_quote")
                continue
            ref, quote = str(item.get("ref") or ""), str(item.get("quote") or "")
            if not ref or not quote:
                errors.append("empty_evidence_quote")
                continue
            valid_refs.add(ref)
            source = source_evidence.get(ref, {})
            original = str(source.get("original_text") or "")
            if original and quote not in original:
                errors.append(f"quote_not_exact:{ref}")
        if row.get("evidence_basis") == "cooccurrence_only":
            errors.append(f"cooccurrence_relation:{row.get('relation_id')}")

    for row in relations:
        a, b = str(row.get("person_a") or ""), str(row.get("person_b") or "")
        if a not in person_ids:
            errors.append(f"dangling_person_a:{a}")
        if b and b not in person_ids:
            errors.append(f"dangling_person_b:{b}")
        if not b and not row.get("provisional_neighbor_id"):
            identity = row.get("identity_resolution") if isinstance(row.get("identity_resolution"), Mapping) else {}
            resolution = identity.get("resolution") if isinstance(identity.get("resolution"), Mapping) else identity
            if resolution.get("resolution_status") not in {"unresolved", "ambiguous"} or not row.get("unresolved_neighbor_surface"):
                errors.append(f"missing_relation_endpoint:{row.get('relation_id')}")
        if row.get("semantic_level") not in {"hard_relation", "documented_interaction", "interpreted_relation"}:
            errors.append(f"invalid_semantic_level:{row.get('relation_id')}")
        identity = row.get("identity_resolution") if isinstance(row.get("identity_resolution"), Mapping) else {}
        resolution = identity.get("resolution") if isinstance(identity.get("resolution"), Mapping) else identity
        if resolution.get("resolution_status") == "resolved_existing_person" and not resolution.get("resolved_person_id"):
            errors.append(f"empty_resolved_relation:{row.get('relation_id')}")
        support = row.get("graph_support") if isinstance(row.get("graph_support"), Mapping) else {}
        if support.get("independent_graph_support_count", 0) and not resolution.get("context_signals"):
            errors.append(f"graph_only_resolution:{row.get('relation_id')}")

    for row in temporal:
        if row.get("person_id") and str(row["person_id"]) not in person_ids:
            errors.append(f"dangling_temporal_person:{row.get('temporal_id')}")
        if not row.get("person_id") and not row.get("provisional_subject_id"):
            errors.append(f"missing_temporal_subject:{row.get('temporal_id')}")

    for row in identities:
        resolution = row.get("resolution") if isinstance(row.get("resolution"), Mapping) else {}
        if resolution.get("resolution_status") == "resolved_existing_person" and str(resolution.get("resolved_person_id")) not in person_ids:
            errors.append(f"dangling_identity_person:{row.get('occurrence_id')}")
        if resolution.get("resolution_method") == "kinship_context":
            kin = resolution.get("kinship_parse") if isinstance(resolution.get("kinship_parse"), Mapping) else {}
            if kin.get("kinship_marker") in {"外祖", "舅", "妻", "妻父", "婿", "外甥"} and kin.get("surname_inheriting"):
                errors.append(f"maternal_surname_inheritance:{row.get('occurrence_id')}")
        if resolution.get("kinship_parse", {}).get("malformed_person_surface") and resolution.get("resolution_status") not in {"unresolved", "provisional"}:
            errors.append(f"malformed_kinship_resolved:{row.get('occurrence_id')}")

    for row in gates:
        if row.get("status") == "conflict":
            occurrence = str(row.get("occurrence_id") or "")
            if any(str(x.get("occurrence_id") or "") == occurrence for x in relations + temporal):
                errors.append(f"temporal_conflict_not_rejected:{occurrence}")

    for row in traces:
        if row.get("wave") not in {1, 2}:
            errors.append("invalid_retrieval_wave")
        for key in ("retrieved_refs", "opened_refs", "used_refs", "new_used_refs", "searched_corpora", "rejected_by_temporal_gate", "rejected_by_seed_identity_gate"):
            if key not in row:
                errors.append(f"missing_retrieval_trace_field:{key}")
        if set(row.get("new_used_refs", [])) - set(row.get("used_refs", [])):
            errors.append("new_used_not_used")

    if review.get("canonical_write_back") is not False:
        errors.append("review_canonical_write_back")
    if set(review.get("review_values", [])) != {"correct", "false_merge", "false_split", "bad_seed_match", "bad_temporal_rejection", "uncertain", "not_reviewed"}:
        errors.append("review_values_incomplete")

    # The manifest is a protection ledger for frozen historical layers.
    protected = manifest.get("protected_artifact_hashes", {})
    for label, expected_hashes in protected.items():
        root = ROOT / "data/generated" / label
        if label == "hng0-1": root = ROOT / "data/generated/hng0-1"
        elif label == "hng0-2": root = ROOT / "data/generated/hng0-2"
        elif label == "hng1r": root = ROOT / "data/generated/hng1r"
        elif label == "hng1r2": root = ROOT / "data/generated/hng1r2"
        current = hash_tree(root)
        if current != expected_hashes:
            errors.append(f"protected_artifact_changed:{label}")

    if mode == "full":
        for path in [ROOT / "data/people.json", ROOT / "data/aliases.json", ROOT / "data/derived/person-story-links.json"]:
            expected_hash = manifest.get("input_hashes", {}).get(str(path.relative_to(ROOT)))
            if expected_hash and sha256_file(path) != expected_hash:
                errors.append(f"protected_input_changed:{path.relative_to(ROOT)}")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("portable", "full"), default="portable")
    args = parser.parse_args()
    errors = validate(mode=args.mode)
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 1
    print(f"HNG2 {args.mode} validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
