#!/usr/bin/env python3
"""Validate the HNG0 candidate/review/frontend projections."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "data/generated/hng0"
SELECTION = OUTPUT_ROOT / "hng0-selection.json"
CANDIDATES = OUTPUT_ROOT / "hng0-candidates.json"
PROJECTION = OUTPUT_ROOT / "hng0-reviewed-projection.json"
METRICS = OUTPUT_ROOT / "hng0-metrics.json"
RETRIEVAL_TRACE = OUTPUT_ROOT / "hng0-retrieval-trace.json"
MANIFEST = OUTPUT_ROOT / "hng0-manifest.json"
REVIEW = ROOT / "data/annotation/hng0-review.json"
FRONTEND = ROOT / "site/src/generated/hng0-site.json"

ALLOWED_RELATION_TYPES = {
    "parent_child", "sibling", "uncle_nephew", "cousin_clan_kin", "marriage",
    "affinal_relation", "same_clan", "superior_subordinate", "recruitment_served_under",
    "teacher_student", "explicit_friendship_association", "explicit_political_cooperation_opposition",
    "shared_explicit_event",
}
ALLOWED_PRECISIONS = {"exact", "circa", "before", "after", "between", "reign_period", "unknown"}
ALLOWED_REVIEW = {"candidate", "accepted", "rejected", "uncertain", "needs_more_evidence"}


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> None:
    raise SystemExit(f"HNG0 validation failed: {message}")


def compact(value: Any) -> str:
    return " ".join(str(value or "").split())


def validate() -> dict[str, Any]:
    required = [SELECTION, CANDIDATES, PROJECTION, METRICS, RETRIEVAL_TRACE, MANIFEST, REVIEW, FRONTEND]
    for path in required:
        if not path.is_file():
            fail(f"missing {path.relative_to(ROOT)}")
    selection = read(SELECTION)
    candidates = read(CANDIDATES)
    projection = read(PROJECTION)
    metrics = read(METRICS)
    retrieval_trace = read(RETRIEVAL_TRACE)
    manifest = read(MANIFEST)
    review = read(REVIEW)
    frontend = read(FRONTEND)
    if selection.get("canonical_write_back") is not False or candidates.get("canonical_write_back") is not False or projection.get("canonical_write_back") is not False or review.get("canonical_write_back") is not False:
        fail("canonical_write_back must be false in every HNG0 layer")
    people_doc = read(ROOT / "data/people.json")
    person_ids = {str(row.get("person_id")) for row in people_doc.get("people", []) if isinstance(row, Mapping)}
    selected = selection.get("people", [])
    seed_ids = {str(row.get("person_id")) for row in selected if isinstance(row, Mapping)}
    if not 20 <= len(seed_ids) <= 30:
        fail(f"selection size is {len(seed_ids)}, expected 20–30")
    if len(seed_ids) != len(selected) or not seed_ids <= person_ids:
        fail("selection has duplicate or dangling Person IDs")
    strata = {row.get("stratum") for row in selected}
    if "high_connectivity" not in strata or "low_connectivity" not in strata:
        fail("selection does not include high and low connectivity strata")
    if selection.get("one_hop_only") is not True or candidates.get("scope", {}).get("one_hop_only") is not True:
        fail("one-hop scope marker missing")

    corpus = read(ROOT / "data/shishuo-corpus-index.json")
    story_ids = {str(row.get("id")) for row in corpus.get("entries", []) if isinstance(row, Mapping)}
    if len(story_ids) != 1130:
        fail(f"canonical corpus index has {len(story_ids)} Stories, expected 1130")
    registry = candidates.get("evidence", {})
    if not isinstance(registry, Mapping):
        fail("evidence registry is missing")
    generated_markers = ("data/generated", "model-output", "deepseek", "srm0")
    for ref, evidence in registry.items():
        if not isinstance(evidence, Mapping) or evidence.get("evidence_ref") != ref:
            fail(f"evidence registry row {ref} is malformed")
        source_path = str(evidence.get("source_path") or "").lower()
        if any(marker in source_path for marker in generated_markers):
            fail(f"generated/model path entered evidence registry: {ref}")
    if retrieval_trace.get("canonical_write_back") is not False or retrieval_trace.get("method") != "existing_local_projection":
        fail("retrieval trace is not marked as a local candidate-only projection")
    trace_people = retrieval_trace.get("people", {})
    if set(trace_people) != seed_ids:
        fail("retrieval trace does not cover exactly the seed Persons")
    for pid, trace in trace_people.items():
        if trace.get("llm_calls") != 0:
            fail(f"HNG0 retrieval trace records an LLM call for {pid}")
        searched = set(trace.get("searched_refs", []))
        retrieved = set(trace.get("retrieved_refs", []))
        opened = set(trace.get("opened_refs", []))
        used = set(trace.get("used_evidence_refs", []))
        if not retrieved <= searched or not used <= retrieved or not opened <= searched:
            fail(f"retrieval trace set nesting is invalid for {pid}")
        if any(ref not in registry for ref in searched | retrieved | opened | used):
            fail(f"retrieval trace has dangling evidence ref for {pid}")
    rows = candidates.get("relations", [])
    relation_ids = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            fail(f"relation {index} is not an object")
        relation_id = row.get("relation_id")
        if not isinstance(relation_id, str) or relation_id in relation_ids:
            fail(f"relation {index} has duplicate/missing relation_id")
        relation_ids.add(relation_id)
        a, b = str(row.get("person_a") or ""), str(row.get("person_b") or "")
        if a not in person_ids or b not in person_ids:
            fail(f"relation {relation_id} has dangling Person")
        if a not in seed_ids and b not in seed_ids:
            fail(f"relation {relation_id} expands beyond one hop")
        if row.get("relation_type") not in ALLOWED_RELATION_TYPES:
            fail(f"relation {relation_id} has invalid type")
        if row.get("review_status") not in ALLOWED_REVIEW:
            fail(f"relation {relation_id} has invalid review status")
        refs = row.get("evidence_refs")
        if not isinstance(refs, list) or not refs or any(str(ref) not in registry for ref in refs):
            fail(f"relation {relation_id} lacks resolvable evidence")
        if row.get("extraction_method") in {"cooccurrence", "story_cooccurrence"} or "cooccurrence" in str(row.get("notes") or "").lower() and row.get("relation_type") != "same_clan":
            fail(f"co-occurrence-only relation survived: {relation_id}")
    time_rows = candidates.get("temporal_items", [])
    temporal_ids = set()
    for index, row in enumerate(time_rows):
        if not isinstance(row, Mapping):
            fail(f"temporal item {index} is not an object")
        temporal_id = row.get("temporal_id")
        if not isinstance(temporal_id, str) or temporal_id in temporal_ids:
            fail(f"temporal item {index} has duplicate/missing temporal_id")
        temporal_ids.add(temporal_id)
        if row.get("person_id") not in seed_ids:
            fail(f"temporal item {temporal_id} is outside seed scope")
        if row.get("precision") not in ALLOWED_PRECISIONS:
            fail(f"temporal item {temporal_id} has invalid precision")
        refs = row.get("evidence_refs")
        if not isinstance(refs, list) or not refs or any(str(ref) not in registry for ref in refs):
            fail(f"temporal item {temporal_id} lacks resolvable evidence")
        if row.get("precision") == "exact" and row.get("start_year") != row.get("end_year"):
            fail(f"exact temporal item {temporal_id} has no single year")
    people = candidates.get("people", {})
    if set(people) != seed_ids:
        fail("candidate people do not exactly match selection")
    for pid, person in people.items():
        for story in person.get("stories", []):
            if story.get("story_id") not in story_ids:
                fail(f"PersonStory {pid}/{story.get('story_id')} does not resolve")
            if story.get("source_presence") not in {"main_text", "liu_annotation_only", "both"}:
                fail(f"invalid source presence for {pid}/{story.get('story_id')}")
            if story.get("research_scope") not in {"published", "research_only"}:
                fail(f"invalid research scope for {pid}/{story.get('story_id')}")
            refs = story.get("evidence_refs") or []
            if any(str(ref) not in registry for ref in refs):
                fail(f"unresolvable PersonStory evidence {pid}/{story.get('story_id')}")
        nearby = set(person.get("nearby_person_ids", []))
        if not nearby <= person_ids:
            fail(f"nearby Person ID dangling for {pid}")
        for story in person.get("stories", []):
            source = story.get("short_excerpt") or ""
            if source:
                # The builder removes only structural whitespace for previews;
                # compare against canonical parsed source in the validator.
                entry = next((row for row in corpus.get("entries", []) if row.get("id") == story.get("story_id")), None)
                if not entry:
                    fail(f"missing canonical source row for {story.get('story_id')}")
                source_path = ROOT / str(entry["path"])
                raw = source_path.read_text(encoding="utf-8")
                if compact(source) not in compact(raw):
                    fail(f"Story excerpt is not a canonical source projection: {pid}/{story.get('story_id')}")

    overlay_rel = review.get("relation_decisions", {})
    overlay_time = review.get("temporal_decisions", {})
    if set(overlay_rel) != relation_ids or set(overlay_time) != temporal_ids:
        fail("review overlay does not cover exactly the candidate IDs")
    for group in (overlay_rel, overlay_time):
        for item_id, decision in group.items():
            if not isinstance(decision, Mapping) or decision.get("review_status") not in ALLOWED_REVIEW:
                fail(f"invalid review decision {item_id}")
    if set(projection.get("people", {})) != seed_ids or len(projection.get("relations", [])) != len(rows) or len(projection.get("temporal_items", [])) != len(time_rows):
        fail("reviewed projection shape differs from candidates")
    if frontend.get("canonical_write_back") is not False or set(frontend.get("people", {})) != seed_ids:
        fail("frontend HNG bundle scope is invalid")
    if set(frontend.get("evidence", {})) != set(registry):
        fail("frontend evidence bundle is incomplete")
    source_hashes = manifest.get("source_hashes", {})
    for relative, expected in source_hashes.items():
        path = ROOT / relative
        if not path.is_file() or sha256(path) != expected:
            fail(f"source hash mismatch: {relative}")
    if metrics.get("evidence_validation_failures") != 0:
        fail("metrics report evidence validation failures")
    return {
        "status": "pass",
        "seed_person_count": len(seed_ids),
        "relation_count": len(rows),
        "temporal_item_count": len(time_rows),
        "evidence_count": len(registry),
        "research_story_links": sum(len(person.get("stories", [])) for person in people.values()),
        "source_text_evidence_count": sum(1 for item in registry.values() if item.get("provenance_kind") == "source_text"),
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
