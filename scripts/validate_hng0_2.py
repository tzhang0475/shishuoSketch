#!/usr/bin/env python3
"""Validate the HNG0.2 offline identity/relation projection.

This validator deliberately treats HNG0.1 and the WREF1 locks as immutable
inputs.  HNG0.2 is a candidate/research projection only; it is never a
canonical-history write path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hng0_1_common import quote_matches, sha256_file  # noqa: E402

ROOT = SCRIPT_DIR.parent
OUTPUT_ROOT = ROOT / "data/generated/hng0-2"
FRONTEND = ROOT / "site/src/generated/hng0-2-site.json"
REVIEW = ROOT / "data/annotation/hng0-2-review.json"
SELECTION = ROOT / "data/generated/hng0/hng0-selection.json"
PEOPLE = ROOT / "data/people.json"

RELATION_INPUT = ROOT / "data/generated/hng0-1/candidate-relations.json"
TEMPORAL_INPUT = ROOT / "data/generated/hng0-1/candidate-temporal-items.json"
UNRESOLVED_INPUT = ROOT / "data/generated/hng0-1/unresolved-identities.json"
PROFILE_INPUT = ROOT / "data/generated/hng0-1/seed-search-profiles.json"
EVIDENCE_INPUT = ROOT / "data/generated/hng0-1/source-evidence-registry.json"

WREF1 = {
    "jinshu-wikisource-punctuated": ROOT / "sources/downloads/jinshu/wikisource-punctuated/manifest.lock.json",
    "zizhi-tongjian-wikisource-hu": ROOT / "sources/downloads/zizhi-tongjian/wikisource-hu/manifest.lock.json",
}

REVIEW_STATUSES = {"candidate", "accepted", "rejected", "uncertain", "needs_more_evidence"}
RESOLUTION_STATUSES = {"resolved_existing_person", "resolved_provisional_person", "unresolved_identity", "ambiguous_identity"}
RESOLUTION_METHODS = {
    "exact_name", "alias", "courtesy_name", "title", "seed_coreference",
    "kinship_context", "biography_local_context", "unresolved", "ambiguous",
}
RELATION_LEVELS = {"hard_relation", "documented_interaction", "interpreted_relation"}
HARD_TYPES = {
    "parent_child", "grandparent_grandchild", "sibling", "uncle_nephew",
    "cousin_clan_kin", "marriage", "affinal_relation", "same_clan",
    "superior_subordinate", "recruitment_served_under", "teacher_student",
}
DOCUMENTED_TYPES = {"documented_social_interaction", "documented_political_interaction", "shared_explicit_event"}
INTERPRETED_TYPES = {"friendship", "political_cooperation", "political_opposition", "rivalry", "factional_alignment"}


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def source_contains(path: Path, text: str) -> bool:
    if not path.is_file() or not text:
        return False
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() != ".json":
        return quote_matches(raw, text)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return quote_matches(raw, text)
    strings: list[str] = []

    def collect(item: Any) -> None:
        if isinstance(item, str):
            strings.append(item)
        elif isinstance(item, list):
            for child in item:
                collect(child)
        elif isinstance(item, Mapping):
            for child in item.values():
                collect(child)

    collect(value)
    return any(quote_matches(candidate, text) for candidate in strings)


def validate_wref1(errors: list[str], *, mode: str) -> None:
    for witness_id, path in WREF1.items():
        if not path.is_file():
            fail(errors, f"missing WREF1 lock: {path.relative_to(ROOT)}")
            continue
        doc = read(path)
        expected = int(doc.get("expected_juan_count") or 0)
        records = doc.get("records", [])
        juans = [int(row.get("global_juan")) for row in records if isinstance(row, Mapping) and row.get("global_juan") is not None]
        if doc.get("status") != "complete":
            fail(errors, f"WREF1 {witness_id} is not complete")
        if doc.get("missing_juans") != [] or doc.get("duplicate_juans") != []:
            fail(errors, f"WREF1 {witness_id} has missing/duplicate metadata")
        if expected != len(juans) or sorted(juans) != list(range(1, expected + 1)):
            fail(errors, f"WREF1 {witness_id} does not cover 1-{expected} exactly")
        for row in records:
            if not isinstance(row, Mapping):
                fail(errors, f"WREF1 {witness_id} has non-object record")
                continue
            for field in ("work", "witness_id", "global_juan", "page_title", "source_url", "api_url", "page_id", "revision_id", "revision_timestamp", "source_path", "source_sha256"):
                if row.get(field) in (None, ""):
                    fail(errors, f"WREF1 {witness_id} record lacks {field}")
            if str(row.get("witness_id")) != witness_id:
                fail(errors, f"WREF1 record witness mismatch: {witness_id}")
            if mode == "full":
                source_path = ROOT / str(row.get("source_path"))
                if not source_path.is_file():
                    fail(errors, f"locked WREF1 payload missing: {source_path}")
                else:
                    if sha256_file(source_path) != str(row.get("source_sha256")):
                        fail(errors, f"locked WREF1 payload hash mismatch: {source_path}")


def validate(root: Path = ROOT, *, mode: str = "portable") -> dict[str, Any]:
    errors: list[str] = []
    required = [
        "identity-resolution.json", "normalized-relations.json", "normalized-temporal-items.json",
        "unresolved-identities.json", "interaction-edges.json", "retrieval-comparison.json",
        "metrics.json", "audit-sample.json", "manifest.json",
    ]
    docs: dict[str, Any] = {}
    for name in required:
        path = OUTPUT_ROOT / name
        if not path.is_file():
            fail(errors, f"missing HNG0.2 artifact: {name}")
        else:
            docs[name] = read(path)
    if not (REVIEW.is_file() and FRONTEND.is_file() and SELECTION.is_file() and PEOPLE.is_file()):
        fail(errors, "HNG0.2 review/frontend/selection/person input is missing")
    if errors:
        raise AssertionError("\n".join(errors))

    validate_wref1(errors, mode=mode)
    manifest = docs["manifest.json"]
    if manifest.get("canonical_write_back") is not False or manifest.get("execution_kind") != "offline_deterministic":
        fail(errors, "HNG0.2 manifest is not offline candidate-only")
    if manifest.get("model_calls") != 0 or manifest.get("one_hop_only") is not True:
        fail(errors, "HNG0.2 manifest permits model calls or misses one-hop marker")

    people_doc = read(PEOPLE)
    person_ids = {str(row.get("person_id")) for row in people_doc.get("people", []) if isinstance(row, Mapping) and row.get("person_id")}
    selection = read(SELECTION)
    seed_ids = {str(row.get("person_id")) for row in selection.get("people", []) if isinstance(row, Mapping) and row.get("person_id")}
    if len(seed_ids) != 24 or not seed_ids <= person_ids:
        fail(errors, f"HNG0.2 seed scope is invalid: {len(seed_ids)}")
    if set(manifest.get("seed_person_ids", [])) != seed_ids:
        fail(errors, "HNG0.2 seed scope differs from frozen HNG0 selection")

    inputs = {
        "data/generated/hng0-1/candidate-relations.json": RELATION_INPUT,
        "data/generated/hng0-1/candidate-temporal-items.json": TEMPORAL_INPUT,
        "data/generated/hng0-1/unresolved-identities.json": UNRESOLVED_INPUT,
        "data/generated/hng0-1/source-evidence-registry.json": EVIDENCE_INPUT,
        "data/generated/hng0-1/seed-search-profiles.json": PROFILE_INPUT,
        "data/generated/hng0/hng0-selection.json": SELECTION,
    }
    for relative, path in inputs.items():
        if not path.is_file() or manifest.get("input_hashes", {}).get(relative) != sha256_file(path):
            fail(errors, f"frozen input hash mismatch: {relative}")

    relation_input = read(RELATION_INPUT).get("relations", [])
    temporal_input = read(TEMPORAL_INPUT).get("temporal_items", [])
    unresolved_input = read(UNRESOLVED_INPUT).get("items", [])
    if len(relation_input) != 160:
        fail(errors, f"HNG0.1 relation input count changed: {len(relation_input)}")
    if len(temporal_input) != 83:
        fail(errors, f"HNG0.1 temporal input count changed: {len(temporal_input)}")
    provisional_before = {str(row.get("provisional_neighbor_id")) for row in relation_input if row.get("provisional_neighbor_id")}
    if len(provisional_before) != 117:
        fail(errors, f"HNG0.1 provisional neighbor count changed: {len(provisional_before)}")
    if len(unresolved_input) != 157:
        fail(errors, f"HNG0.1 unresolved occurrence count changed: {len(unresolved_input)}")

    evidence = docs["normalized-relations.json"].get("evidence", {})
    evidence.update(docs["normalized-temporal-items.json"].get("evidence", {}))
    for ref, row in evidence.items():
        path_value = str(row.get("source_path") or "")
        lowered = path_value.lower()
        if "data/generated" in lowered or "model" in lowered or "deepseek" in lowered:
            fail(errors, f"generated/model source path entered evidence: {ref}")
        if not row.get("source_work") or not row.get("source_layer"):
            fail(errors, f"incomplete evidence provenance: {ref}")
        if not (ROOT / path_value).is_file():
            fail(errors, f"evidence source path missing: {ref} -> {path_value}")
        elif not source_contains(ROOT / path_value, str(row.get("original_text") or "")):
            fail(errors, f"evidence original text is not in registered source: {ref}")

    resolution_doc = docs["identity-resolution.json"]
    resolutions = resolution_doc.get("resolutions", [])
    resolution_ids = {str(row.get("candidate_id")) for row in resolutions if isinstance(row, Mapping)}
    if len(resolutions) != len(set(resolution_ids)) or not all(row.get("candidate_id") for row in resolutions):
        fail(errors, "identity-resolution has missing/duplicate candidate IDs")
    for row in resolutions:
        status = row.get("resolution_status")
        method = row.get("resolution_method")
        if status not in RESOLUTION_STATUSES:
            fail(errors, f"invalid identity resolution status: {status}")
        if method not in RESOLUTION_METHODS:
            fail(errors, f"invalid identity resolution method: {method}")
        if status == "resolved_existing_person" and row.get("resolved_person_id") not in person_ids:
            fail(errors, f"identity resolves to dangling Person: {row.get('candidate_id')}")
        if status == "resolved_provisional_person" and not str(row.get("provisional_person_id") or "").startswith("hng02-provisional-"):
            fail(errors, f"provisional identity lacks HNG-only ID: {row.get('candidate_id')}")
        if not row.get("supporting_evidence_refs"):
            fail(errors, f"identity lacks supporting evidence: {row.get('candidate_id')}")
        if not str(row.get("surface") or ""):
            fail(errors, f"identity lacks source surface: {row.get('candidate_id')}")
        if any(str(ref) not in evidence for ref in row.get("supporting_evidence_refs", [])):
            fail(errors, f"identity has dangling evidence: {row.get('candidate_id')}")

    relation_doc = docs["normalized-relations.json"]
    relations = relation_doc.get("relations", [])
    relation_ids: set[str] = set()
    relation_keys: set[tuple[Any, ...]] = set()
    for row in relations:
        rid = str(row.get("relation_id") or "")
        if not rid or rid in relation_ids:
            fail(errors, f"duplicate/missing normalized relation ID: {rid}")
        relation_ids.add(rid)
        if row.get("person_a") not in seed_ids:
            fail(errors, f"relation is outside seed scope: {rid}")
        person_b = row.get("person_b")
        provisional = str(row.get("provisional_neighbor_id") or "")
        if person_b is not None and person_b not in person_ids:
            fail(errors, f"relation has dangling canonical endpoint: {rid}")
        if person_b is None and not provisional.startswith("hng02-provisional-"):
            fail(errors, f"unresolved relation lacks HNG provisional endpoint: {rid}")
        if row.get("semantic_level") not in RELATION_LEVELS:
            fail(errors, f"invalid semantic relation level: {rid}")
        relation_type = row.get("relation_type")
        if relation_type not in HARD_TYPES | DOCUMENTED_TYPES | INTERPRETED_TYPES:
            fail(errors, f"invalid normalized relation type: {rid}")
        if row.get("relation_type") == "grandparent_grandchild" and row.get("semantic_level") != "hard_relation":
            fail(errors, f"grandparent relation is not hard_relation: {rid}")
        if row.get("relation_type") == "same_clan" and any(marker in str(row.get("claim") or "") for marker in ("祖", "孫", "祖父", "孫也")):
            fail(errors, f"explicit grandparent claim remained same_clan: {rid}")
        if row.get("original_relation_type") == "explicit_political_cooperation_opposition" and row.get("semantic_level") == "interpreted_relation":
            fail(errors, f"weak political candidate remained interpreted: {rid}")
        if row.get("review_status") not in REVIEW_STATUSES or row.get("one_hop_only") is not True or row.get("canonical_write_back") is True:
            fail(errors, f"relation candidate markers invalid: {rid}")
        refs = row.get("evidence_refs", [])
        quotes = {str(item.get("ref")): str(item.get("quote") or "") for item in row.get("evidence_quotes", []) if isinstance(item, Mapping)}
        if not isinstance(refs, list) or not refs or any(str(ref) not in evidence for ref in refs):
            fail(errors, f"relation lacks resolvable evidence: {rid}")
        for ref in refs:
            if str(ref) not in quotes or not quote_matches(str(evidence[str(ref)].get("original_text") or ""), quotes[str(ref)]):
                fail(errors, f"relation has invalid exact quote: {rid}/{ref}")
        key = (row.get("person_a"), person_b or provisional, row.get("relation_type"), (row.get("direction") or {}).get("kind") if isinstance(row.get("direction"), Mapping) else "")
        if key in relation_keys:
            fail(errors, f"duplicate normalized relation identity key: {rid}")
        relation_keys.add(key)

    temporal = docs["normalized-temporal-items.json"].get("temporal_items", [])
    temporal_ids: set[str] = set()
    for row in temporal:
        tid = str(row.get("temporal_id") or "")
        if not tid or tid in temporal_ids:
            fail(errors, f"duplicate/missing normalized temporal ID: {tid}")
        temporal_ids.add(tid)
        if row.get("person_id") not in seed_ids and not str(row.get("provisional_subject_id") or "").startswith("hng02-provisional-"):
            fail(errors, f"temporal item is outside one-hop seed scope: {tid}")
        if row.get("review_status") not in REVIEW_STATUSES:
            fail(errors, f"temporal review status invalid: {tid}")
        refs = row.get("evidence_refs", [])
        quotes = {str(item.get("ref")): str(item.get("quote") or "") for item in row.get("evidence_quotes", []) if isinstance(item, Mapping)}
        if not isinstance(refs, list) or not refs or any(str(ref) not in evidence for ref in refs):
            fail(errors, f"temporal item lacks resolvable evidence: {tid}")
        for ref in refs:
            if str(ref) not in quotes or not quote_matches(str(evidence[str(ref)].get("original_text") or ""), quotes[str(ref)]):
                fail(errors, f"temporal item has invalid exact quote: {tid}/{ref}")

    unresolved = docs["unresolved-identities.json"].get("items", [])
    for row in unresolved:
        if row.get("resolution_status") not in {"unresolved_identity", "ambiguous_identity"}:
            fail(errors, f"resolved item entered unresolved projection: {row.get('candidate_id')}")
        if row.get("seed_person_id") not in seed_ids:
            fail(errors, f"unresolved identity has dangling seed: {row.get('candidate_id')}")

    interaction = docs["interaction-edges.json"]
    if {str(row.get("relation_id")) for row in interaction.get("relations", [])} - relation_ids:
        fail(errors, "interaction edge is not a normalized relation")
    review = read(REVIEW)
    if review.get("canonical_write_back") is not False:
        fail(errors, "HNG0.2 review overlay permits canonical write-back")
    if set(review.get("relation_decisions", {})) != relation_ids or set(review.get("temporal_decisions", {})) != temporal_ids or set(review.get("identity_decisions", {})) != resolution_ids:
        fail(errors, "HNG0.2 review overlay does not cover generated IDs exactly")
    for group in (review.get("relation_decisions", {}), review.get("temporal_decisions", {}), review.get("identity_decisions", {})):
        for item_id, decision in group.items():
            if not isinstance(decision, Mapping) or decision.get("review_status") not in REVIEW_STATUSES:
                fail(errors, f"invalid HNG0.2 review decision: {item_id}")

    comparison = docs["retrieval-comparison.json"]
    if comparison.get("canonical_write_back") is not False or comparison.get("model_calls") != 0:
        fail(errors, "retrieval comparison is not offline candidate-only")
    for mode_name, mode_doc in comparison.get("modes", {}).items():
        if mode_doc.get("elapsed_seconds") != 0.0:
            fail(errors, f"offline comparison contains nondeterministic timing: {mode_name}")
        if mode_name == "punctuated_first" and float(mode_doc.get("average_open_chars") or 0) > 520:
            fail(errors, "punctuated-first OPEN windows exceed the configured cap")

    frontend = read(FRONTEND)
    if frontend.get("canonical_write_back") is not False or frontend.get("stage") != "hng0-2-frontend-review":
        fail(errors, "HNG0.2 frontend bundle is not candidate-only")
    if set(frontend.get("people", {})) != seed_ids:
        fail(errors, "HNG0.2 frontend people scope differs from seeds")

    if errors:
        raise AssertionError("\n".join(errors))
    metrics = docs["metrics.json"]
    return {
        "status": "pass",
        "mode": mode,
        "seed_person_count": len(seed_ids),
        "input_relation_count": len(relation_input),
        "input_temporal_count": len(temporal_input),
        "input_unresolved_occurrences": len(unresolved_input),
        "normalized_relation_count": len(relations),
        "normalized_temporal_count": len(temporal),
        "remaining_unresolved_identity_count": len(unresolved),
        "relation_level_counts": metrics.get("relation_level_counts", {}),
        "source_form_usage": metrics.get("source_form_usage", {}),
        "model_calls": manifest.get("model_calls"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("portable", "full"), default="portable")
    args = parser.parse_args()
    print(json.dumps(validate(mode=args.mode), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
