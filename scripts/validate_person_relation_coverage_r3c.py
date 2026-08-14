#!/usr/bin/env python3
"""Validate R3C coverage and candidate artifacts without mutating production."""

from __future__ import annotations

import argparse
from pathlib import Path
import json
from typing import Any

try:
    from .person_relation_coverage_r3c import (
        BUNDLE_PATH,
        CANDIDATE_PATH,
        COVERAGE_PATH,
        PEOPLE_PATH,
        RELATIONS_PATH,
        R3A_PATH,
        R3B_PATH,
        build_projection,
        candidate_document,
        project,
        read_json,
        stable_attention_id,
        stable_candidate_id,
        validate_source,
    )
except ImportError:
    from person_relation_coverage_r3c import (
        BUNDLE_PATH,
        CANDIDATE_PATH,
        COVERAGE_PATH,
        PEOPLE_PATH,
        RELATIONS_PATH,
        R3A_PATH,
        R3B_PATH,
        build_projection,
        candidate_document,
        project,
        read_json,
        stable_attention_id,
        stable_candidate_id,
        validate_source,
    )


ROOT = Path(__file__).resolve().parents[1]


def validate(root: Path = ROOT) -> list[str]:
    errors = list(validate_source(root))
    try:
        coverage = read_json(root, COVERAGE_PATH)
        candidates = read_json(root, CANDIDATE_PATH)
        expected_coverage, expected_candidates = build_projection(root)
        bundle = read_json(root, BUNDLE_PATH)
        people = read_json(root, PEOPLE_PATH).get("people", [])
        relations = read_json(root, RELATIONS_PATH).get("records", [])
        r3a = read_json(root, R3A_PATH).get("records", [])
        r3b = read_json(root, R3B_PATH).get("records", [])
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return errors + [f"R3C artifact could not be read: {exc}"]

    if coverage != expected_coverage:
        errors.append("R3C coverage artifact is not the deterministic projection")
    if candidates != expected_candidates:
        errors.append("R3C candidate artifact is not the deterministic projection")

    person_ids = {str(person.get("person_id")) for person in people if isinstance(person, dict)}
    bundle_person_ids = {str(person.get("id")) for person in bundle.get("people", []) if isinstance(person, dict)}
    story_ids = {
        str(story.get("id"))
        for story in bundle.get("stories", [])
        if isinstance(story, dict) and story.get("publication_state") in {"production_ready", "preview_ready"}
    }
    if coverage["scope"]["production_person_count"] != len(person_ids):
        errors.append("R3C production Person count mismatch")
    if coverage["scope"]["production_person_ids"] != sorted(person_ids):
        errors.append("R3C production Person ordering mismatch")
    if coverage["scope"]["production_person_ids"] != sorted(bundle_person_ids):
        errors.append("R3C scope differs from generated Person bundle")
    if coverage["scope"]["published_story_count"] != len(story_ids):
        errors.append("R3C published Story count mismatch")
    if coverage["scope"]["published_story_ids"] != sorted(story_ids):
        errors.append("R3C published Story IDs mismatch")
    expected_pairs = len(person_ids) * (len(person_ids) - 1) // 2
    if coverage["scope"]["person_pair_universe"] != expected_pairs:
        errors.append("R3C pair universe is not n*(n-1)/2")

    reviewed_ids = {str(item.get("id")) for item in relations if item.get("review_status") == "reviewed"}
    r3a_ids = {str(item.get("candidate_id")) for item in r3a}
    r3b_ids = {str(item.get("candidate_id")) for item in r3b}
    candidate_ids: set[str] = set()
    for candidate in candidates.get("records", []):
        cid = str(candidate.get("candidate_id"))
        if cid in candidate_ids:
            errors.append(f"duplicate R3C candidate ID: {cid}")
        candidate_ids.add(cid)
        if candidate.get("review_status") != "candidate":
            errors.append(f"R3C candidate is not review_status=candidate: {cid}")
        if candidate.get("person_a_id") not in person_ids or candidate.get("person_b_id") not in person_ids:
            errors.append(f"R3C candidate endpoint does not resolve: {cid}")
        if candidate.get("person_a_id") >= candidate.get("person_b_id"):
            errors.append(f"R3C candidate pair is not canonicalized: {cid}")
        if "production_relation_id" in candidate:
            errors.append(f"R3C candidate must not carry production_relation_id: {cid}")
        if stable_candidate_id(candidate) != cid:
            errors.append(f"R3C candidate ID is not a stable semantic hash: {cid}")
        if not candidate.get("evidence_ids"):
            errors.append(f"R3C candidate has no Evidence: {cid}")
        if not candidate.get("source_entry_ids") and not candidate.get("source_unit_ids"):
            errors.append(f"R3C candidate has no source anchor: {cid}")
        if any("cooccurrence" in flag for flag in candidate.get("risk_flags", [])):
            errors.append(f"co-occurrence-only signal became R3C candidate: {cid}")

    attention_ids: set[str] = set()
    for record in coverage.get("attention_records", []):
        aid = str(record.get("attention_id"))
        if aid in attention_ids:
            errors.append(f"duplicate R3C attention ID: {aid}")
        attention_ids.add(aid)
        if record.get("person_a_id") not in person_ids or record.get("person_b_id") not in person_ids:
            errors.append(f"R3C attention endpoint does not resolve: {aid}")
        if record.get("person_a_id") >= record.get("person_b_id"):
            errors.append(f"R3C attention pair is not canonicalized: {aid}")
        if stable_attention_id(record) != aid:
            errors.append(f"R3C attention ID is not deterministic: {aid}")
        if record.get("disposition") == "new_candidate" and record.get("candidate_id") not in candidate_ids:
            errors.append(f"R3C new-candidate attention has no candidate: {aid}")
        if record.get("disposition") == "existing_reviewed" and not set(record.get("existing_relation_ids", [])) <= reviewed_ids:
            errors.append(f"R3C reviewed attention references unknown Relation: {aid}")
        if not set(record.get("existing_r3a_candidate_ids", [])) <= r3a_ids:
            errors.append(f"R3C attention references unknown R3A candidate: {aid}")

    summary = coverage["summary"]
    dispositions = {}
    for record in coverage.get("attention_records", []):
        dispositions[record["disposition"]] = dispositions.get(record["disposition"], 0) + 1
    if summary["already_reviewed_rediscovery_count"] != len([item for item in coverage["attention_records"] if item["disposition"] == "existing_reviewed"]):
        errors.append("R3C reviewed rediscovery metric mismatch")
    if summary["existing_deferred_rediscovery_count"] != len([item for item in coverage["attention_records"] if item["disposition"] == "existing_deferred"]):
        errors.append("R3C deferred rediscovery metric mismatch")
    if summary["new_candidate_count"] != len(candidates.get("records", [])):
        errors.append("R3C candidate count mismatch")
    if summary["relation_isolated_person_count"] != len(summary["relation_isolated_person_ids"]):
        errors.append("R3C isolated Person metric mismatch")
    if not set(summary["relation_isolated_person_ids"]) <= person_ids:
        errors.append("R3C isolated Person summary contains unknown Person")

    # The audit must not change the current production Relation registry or
    # the authoritative R3B review decisions.  These checks intentionally
    # compare only the source documents, not generated candidate output.
    if len(relations) != len(read_json(root, RELATIONS_PATH).get("records", [])):
        errors.append("R3C unexpectedly changed production Relation count")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = validate(args.root)
    if errors:
        print("R3C validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("R3C Person Relation coverage artifacts valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
