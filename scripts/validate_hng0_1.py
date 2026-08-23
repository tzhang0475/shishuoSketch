#!/usr/bin/env python3
"""Validate the generated, candidate-only HNG0.1 source-growth layer."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hng0_1_common import (  # noqa: E402
    ALLOWED_RELATION_TYPES,
    ALLOWED_TEMPORAL_TYPES,
    HNG0_CANDIDATE_PATH,
    OUTPUT_ROOT,
    ROOT,
    REVIEW_STATUSES,
    build_people_catalog,
    quote_matches,
    read_json,
    resolve_counterpart,
    sha256_file,
    stable_hash,
)


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def _source_contains(path: Path, snippet: str) -> bool:
    if not path.is_file() or not snippet:
        return False
    if path.suffix == ".json":
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            texts: list[str] = []
            def collect(item: Any) -> None:
                if isinstance(item, str):
                    texts.append(item)
                elif isinstance(item, list):
                    for child in item:
                        collect(child)
                elif isinstance(item, Mapping):
                    for child in item.values():
                        collect(child)
            collect(value)
            return any(quote_matches(text, snippet) for text in texts)
        except json.JSONDecodeError:
            raw = path.read_text(encoding="utf-8")
    else:
        raw = path.read_text(encoding="utf-8")
    return quote_matches(raw, snippet)


def validate(root: Path = ROOT) -> dict[str, Any]:
    errors: list[str] = []
    required = [
        "seed-search-profiles.json", "retrieval-trace.json", "source-evidence-registry.json",
        "candidate-relations.json", "candidate-temporal-items.json", "unresolved-identities.json",
        "neighborhoods.json", "audit-sample.json", "metrics.json", "manifest.json",
    ]
    docs: dict[str, Any] = {}
    for name in required:
        path = root / OUTPUT_ROOT.relative_to(root) / name
        if not path.is_file():
            fail(errors, f"missing HNG0.1 artifact: {name}")
            continue
        docs[name] = read_json(path)
    if errors:
        raise AssertionError("; ".join(errors))
    selection = read_json(root / "data/generated/hng0/hng0-selection.json")
    seed_ids = {str(row.get("person_id")) for row in selection.get("people", []) if row.get("person_id")}
    if len(seed_ids) != 24:
        fail(errors, f"frozen HNG0 seed count is {len(seed_ids)}, expected 24")
    manifest = docs["manifest.json"]
    if manifest.get("canonical_write_back") is not False:
        fail(errors, "manifest permits canonical write-back")
    if set(manifest.get("seed_person_ids", [])) != seed_ids:
        fail(errors, "manifest seed scope differs from HNG0 selection")
    if manifest.get("protected_hng0_hash") != sha256_file(root / HNG0_CANDIDATE_PATH.relative_to(root)):
        fail(errors, "HNG0 candidate artifact changed after HNG0.1 run")
    if manifest.get("one_hop_only") is not True:
        fail(errors, "one-hop scope marker missing")

    profiles = docs["seed-search-profiles.json"].get("profiles", {})
    if set(profiles) != seed_ids:
        fail(errors, "search profile scope differs from seed scope")
    trace_people = docs["retrieval-trace.json"].get("people", {})
    if set(trace_people) != seed_ids:
        fail(errors, "retrieval trace does not cover every seed")
    all_retrieved: set[str] = set()
    all_opened: set[str] = set()
    for pid, trace in trace_people.items():
        retrieved = set(str(ref) for ref in trace.get("retrieved", []))
        opened = set(str(ref) for ref in trace.get("opened", []))
        used = set(str(ref) for ref in trace.get("used", []))
        all_retrieved |= retrieved
        all_opened |= opened
        if not opened <= retrieved:
            fail(errors, f"opened refs not retrieved for {pid}")
        if not used <= opened:
            fail(errors, f"used refs not opened for {pid}")
        if any("data/generated" in str(item.get("source_path", "")) for item in trace.get("find", {}).get("hits", [])):
            fail(errors, f"generated path entered FIND results for {pid}")
        for route in trace.get("route", []):
            if not route.get("work") or not route.get("reason"):
                fail(errors, f"source route lacks reason for {pid}")

    evidence = docs["source-evidence-registry.json"].get("evidence", {})
    if set(evidence) != all_opened:
        fail(errors, "opened refs and source evidence registry differ")
    for ref, item in evidence.items():
        path_value = str(item.get("source_path") or "")
        if "data/generated" in path_value or "model" in path_value.lower():
            fail(errors, f"generated/model path used as evidence: {ref}")
        source_path = root / path_value
        if not source_path.is_file():
            fail(errors, f"evidence source path missing: {ref} -> {path_value}")
        elif not _source_contains(source_path, str(item.get("original_text") or "")):
            fail(errors, f"opened source window is not contained in registered source: {ref}")
        if not item.get("source_work") or not item.get("source_layer"):
            fail(errors, f"evidence provenance incomplete: {ref}")

    people = build_people_catalog(root)
    relations = docs["candidate-relations.json"].get("relations", [])
    relation_ids: set[str] = set()
    relation_keys: set[tuple[Any, ...]] = set()
    for index, row in enumerate(relations):
        if not isinstance(row, Mapping):
            fail(errors, f"relation {index} is not an object")
            continue
        relation_id = str(row.get("relation_id") or "")
        if not relation_id or relation_id in relation_ids:
            fail(errors, f"relation {index} has duplicate/missing id")
        relation_ids.add(relation_id)
        a, b = row.get("person_a"), row.get("person_b")
        if a not in seed_ids and b not in seed_ids:
            fail(errors, f"relation {relation_id} does not have a seed endpoint")
        if b is not None and b not in people:
            fail(errors, f"relation {relation_id} has dangling person endpoint")
        if a in seed_ids and b in seed_ids:
            fail(errors, f"relation {relation_id} expands to another frozen seed")
        if row.get("relation_type") not in ALLOWED_RELATION_TYPES:
            fail(errors, f"relation {relation_id} has invalid relation type")
        if row.get("one_hop_only") is not True or row.get("origin") != "newly_extracted":
            fail(errors, f"relation {relation_id} lacks source-growth markers")
        if row.get("cooccurrence_only") is True:
            fail(errors, f"co-occurrence-only relation survived: {relation_id}")
        if row.get("review_status") not in REVIEW_STATUSES:
            fail(errors, f"relation {relation_id} has invalid review status")
        refs = row.get("evidence_refs", [])
        if not isinstance(refs, list) or not refs or not set(refs) <= set(evidence):
            fail(errors, f"relation {relation_id} lacks opened evidence")
        quotes = {str(item.get("ref")): str(item.get("quote")) for item in row.get("evidence_quotes", []) if isinstance(item, Mapping)}
        for ref in refs if isinstance(refs, list) else []:
            if ref not in quotes or not quote_matches(str(evidence[ref].get("original_text") or ""), quotes[ref]):
                fail(errors, f"relation {relation_id} has invalid exact quote for {ref}")
        endpoint = b or row.get("provisional_neighbor_id")
        key = (a, endpoint, row.get("relation_type"), (row.get("direction") or {}).get("kind") if isinstance(row.get("direction"), Mapping) else "")
        if key in relation_keys:
            fail(errors, f"duplicate relation identity key: {relation_id}")
        relation_keys.add(key)
        if row.get("resolution_status") == "resolved_existing_person" and not b:
            fail(errors, f"resolved relation has no person_b: {relation_id}")

    times = docs["candidate-temporal-items.json"].get("temporal_items", [])
    time_ids: set[str] = set()
    for index, row in enumerate(times):
        if not isinstance(row, Mapping):
            fail(errors, f"temporal item {index} is not an object")
            continue
        tid = str(row.get("temporal_id") or "")
        if not tid or tid in time_ids:
            fail(errors, f"temporal item {index} has duplicate/missing id")
        time_ids.add(tid)
        if row.get("person_id") not in seed_ids and row.get("subject_resolution_status") not in {"unresolved_identity", "ambiguous_identity"}:
            fail(errors, f"temporal item {tid} is outside one-hop scope")
        if row.get("temporal_type") not in ALLOWED_TEMPORAL_TYPES:
            fail(errors, f"temporal item {tid} has invalid temporal type")
        if row.get("origin") != "newly_extracted" or row.get("review_status") not in REVIEW_STATUSES:
            fail(errors, f"temporal item {tid} lacks candidate markers")
        refs = row.get("evidence_refs", [])
        if not isinstance(refs, list) or not refs or not set(refs) <= set(evidence):
            fail(errors, f"temporal item {tid} lacks opened evidence")
        quotes = {str(item.get("ref")): str(item.get("quote")) for item in row.get("evidence_quotes", []) if isinstance(item, Mapping)}
        for ref in refs if isinstance(refs, list) else []:
            if ref not in quotes or not quote_matches(str(evidence[ref].get("original_text") or ""), quotes[ref]):
                fail(errors, f"temporal item {tid} has invalid exact quote for {ref}")

    review = read_json(root / "data/annotation/hng0-1-review.json")
    if review.get("canonical_write_back") is not False:
        fail(errors, "review overlay permits canonical write-back")
    if set(review.get("relation_decisions", {})) != relation_ids or set(review.get("temporal_decisions", {})) != time_ids:
        fail(errors, "review overlay does not cover exactly HNG0.1 candidates")
    for decisions in (review.get("relation_decisions", {}), review.get("temporal_decisions", {})):
        for item_id, decision in decisions.items():
            if not isinstance(decision, Mapping) or decision.get("review_status") not in REVIEW_STATUSES:
                fail(errors, f"invalid review decision {item_id}")

    unresolved = docs["unresolved-identities.json"].get("items", [])
    for item in unresolved:
        candidate = item.get("candidate", {}) if isinstance(item, Mapping) else {}
        if candidate.get("resolution_status") == "resolved_existing_person" or candidate.get("subject_resolution_status") == "resolved_existing_person":
            fail(errors, "resolved candidate entered unresolved identity report")
        if item.get("seed_person_id") not in seed_ids:
            fail(errors, "unresolved identity has dangling seed")

    audit = docs["audit-sample.json"]
    if audit.get("canonical_write_back") is not False or audit.get("stage") != "hng0-1-manual-audit-sample":
        fail(errors, "audit sample is not candidate-only")
    for item in audit.get("items", []):
        candidate = item.get("candidate", {}) if isinstance(item, Mapping) else {}
        if not isinstance(candidate, Mapping):
            fail(errors, "audit sample candidate is not an object")
            continue
        for ref in candidate.get("evidence_refs", []) if isinstance(candidate.get("evidence_refs"), list) else []:
            if ref not in evidence:
                fail(errors, f"audit sample has dangling evidence: {ref}")

    if errors:
        raise AssertionError("\n".join(errors))
    return {
        "status": "pass",
        "execution_kind": manifest.get("execution_kind"),
        "seed_person_count": len(seed_ids),
        "retrieved_refs": len(all_retrieved),
        "opened_refs": len(all_opened),
        "relation_count": len(relations),
        "temporal_count": len(times),
        "unresolved_identity_count": len(unresolved),
        "evidence_validation_failures": docs["metrics.json"].get("evidence_validation_failures"),
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
