#!/usr/bin/env python3
"""Validate ER1's effective contextual Person-resolution layer.

This validator treats the canonical Mention file as immutable segmentation and
checks that the ER1 projection only changes resolution semantics.  It also
checks that a reviewed decision cannot be lost when the automatic resolver is
rebuilt.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

try:
    from .person_resolution import (
        COLLISIONS_PATH,
        DECISIONS_PATH,
        EFFECTIVE_PATH,
        QUEUE_PATH,
        _target_key,
        read_json,
    )
except ImportError:  # direct execution
    from person_resolution import (
        COLLISIONS_PATH,
        DECISIONS_PATH,
        EFFECTIVE_PATH,
        QUEUE_PATH,
        _target_key,
        read_json,
    )


ROOT = Path(__file__).resolve().parents[1]
PEOPLE_PATH = Path("data/people.json")
MENTIONS_PATH = Path("data/mentions/shishuo.json")
CANDIDATES_PATH = Path("data/derived/person-identity-candidates.json")
EVIDENCE_PATH = Path("data/evidence/wp1-evidence.json")
CORPUS_PATH = Path("data/shishuo-corpus-index.json")
DECISION_SCHEMA_PATH = Path("schema/person-resolution-decision.schema.json")
EFFECTIVE_SCHEMA_PATH = Path("schema/person-resolution-effective.schema.json")
QUEUE_SCHEMA_PATH = Path("schema/person-resolution-review-queue.schema.json")
COLLISION_SCHEMA_PATH = Path("schema/person-alias-collisions.schema.json")

RESOLUTION_FIELDS = {
    "person_id",
    "candidate_person_ids",
    "confidence",
    "resolution_mode",
    "resolution_method",
    "resolution_status",
    "resolution_target",
    "resolution_candidates",
    "resolution_review_status",
    "resolution_decision_source",
    "resolution_evidence_ids",
    "resolution_note",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _schema_errors(root: Path, schema_path: Path, value: Any, label: str) -> list[str]:
    try:
        schema = read_json(root, schema_path)
        Draft202012Validator.check_schema(schema)
        return [f"{label}: {error.message}" for error in Draft202012Validator(schema).iter_errors(value)]
    except Exception as exc:  # schema errors must be reported, not hidden
        return [f"{label} schema validation failed: {exc}"]


def _target_valid(
    target: Any,
    *,
    people_by_id: Mapping[str, Mapping[str, Any]],
    candidates_by_id: Mapping[str, Mapping[str, Any]],
    label: str,
) -> list[str]:
    errors: list[str] = []
    if target is None:
        return errors
    if not isinstance(target, Mapping):
        return [f"{label} is not an object"]
    kind = target.get("target_kind")
    name = target.get("canonical_name")
    if kind == "production_person":
        person_id = target.get("person_id")
        person = people_by_id.get(str(person_id))
        if person is None:
            errors.append(f"{label} references unknown production Person: {person_id!r}")
        elif name != person.get("canonical_name"):
            errors.append(f"{label} canonical_name disagrees with production Person: {person_id}")
        if "candidate_id" in target:
            errors.append(f"{label} production target carries candidate_id")
    elif kind == "identity_candidate":
        candidate_id = target.get("candidate_id")
        candidate = candidates_by_id.get(str(candidate_id))
        if candidate is None:
            errors.append(f"{label} references unknown identity candidate: {candidate_id!r}")
        elif name != candidate.get("preferred_name"):
            errors.append(f"{label} canonical_name disagrees with identity candidate: {candidate_id}")
        elif candidate.get("status") == "already_materialized":
            errors.append(f"{label} uses an already-materialized candidate as a non-production target: {candidate_id}")
        if "person_id" in target:
            errors.append(f"{label} identity-candidate target carries person_id")
    else:
        errors.append(f"{label} has invalid target_kind: {kind!r}")
    return errors


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        people_document = read_json(root, PEOPLE_PATH)
        raw_document = read_json(root, MENTIONS_PATH)
        candidates_document = read_json(root, CANDIDATES_PATH)
        evidence_document = read_json(root, EVIDENCE_PATH)
        corpus_document = read_json(root, CORPUS_PATH)
        decisions_document = read_json(root, DECISIONS_PATH)
        effective = read_json(root, EFFECTIVE_PATH)
        queue = read_json(root, QUEUE_PATH)
        collisions = read_json(root, COLLISIONS_PATH)
    except (OSError, ValueError, KeyError) as exc:
        return [f"ER1 cannot read required artifact: {exc}"]

    for number, decision in enumerate(decisions_document.get("decisions", [])):
        errors.extend(_schema_errors(root, DECISION_SCHEMA_PATH, decision, f"ER1 decision {number}"))
    errors.extend(_schema_errors(root, EFFECTIVE_SCHEMA_PATH, effective, "ER1 effective resolution"))
    errors.extend(_schema_errors(root, QUEUE_SCHEMA_PATH, queue, "ER1 review queue"))
    errors.extend(_schema_errors(root, COLLISION_SCHEMA_PATH, collisions, "ER1 alias collisions"))

    people = [item for item in people_document.get("people", []) if isinstance(item, Mapping)]
    people_by_id = {str(item.get("person_id")): item for item in people if isinstance(item.get("person_id"), str)}
    candidate_rows = [item for item in candidates_document.get("candidates", []) if isinstance(item, Mapping)]
    candidates_by_id = {str(item.get("candidate_id")): item for item in candidate_rows if isinstance(item.get("candidate_id"), str)}
    evidence_ids = {
        str(item.get("id"))
        for item in [*candidates_document.get("evidence", []), *evidence_document.get("records", [])]
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    raw_mentions = [item for item in raw_document.get("mentions", []) if isinstance(item, Mapping)]
    raw_by_id = {str(item.get("mention_id")): item for item in raw_mentions if isinstance(item.get("mention_id"), str)}
    story_ids = {
        str(item.get("id"))
        for item in corpus_document.get("entries", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }

    if effective.get("mention_count") != len(effective.get("mentions", [])):
        errors.append("ER1 effective mention_count does not match mentions length")
    if effective.get("source_mentions_sha256") != sha256_file(root / MENTIONS_PATH):
        errors.append("ER1 effective projection is stale relative to canonical Mention data")
    if effective.get("decision_sha256") != sha256_file(root / DECISIONS_PATH):
        errors.append("ER1 effective projection is stale relative to human decisions")
    effective_rows = [item for item in effective.get("mentions", []) if isinstance(item, Mapping)]
    effective_by_id: dict[str, Mapping[str, Any]] = {}
    for row in effective_rows:
        mention_id = row.get("mention_id")
        if not isinstance(mention_id, str) or mention_id in effective_by_id:
            errors.append(f"ER1 duplicate/invalid effective Mention ID: {mention_id!r}")
            continue
        effective_by_id[mention_id] = row
        raw = raw_by_id.get(mention_id)
        if raw is None:
            errors.append(f"ER1 effective Mention is not canonical: {mention_id}")
            continue
        for field in ("entry_id", "section", "surface", "alias_id", "alias_type"):
            if row.get(field) != raw.get(field):
                errors.append(f"ER1 changed immutable Mention field {field}: {mention_id}")
        raw_anchor = raw.get("evidence", {}) if isinstance(raw.get("evidence"), Mapping) else {}
        row_anchor = row.get("evidence", {}) if isinstance(row.get("evidence"), Mapping) else {}
        if row_anchor.get("section_offset") != raw_anchor.get("section_offset"):
            errors.append(f"ER1 changed immutable Mention anchor: {mention_id}")
        status = row.get("resolution_status")
        target = row.get("resolution_target")
        candidates = row.get("resolution_candidates", [])
        if status not in {"resolved", "candidate_for_review", "unresolved"}:
            errors.append(f"ER1 invalid resolution status: {mention_id}")
        if status == "unresolved" and target is not None:
            errors.append(f"ER1 unresolved Mention has a target: {mention_id}")
        if status == "candidate_for_review" and not isinstance(candidates, list):
            errors.append(f"ER1 review Mention candidates are not a list: {mention_id}")
        if status == "candidate_for_review" and len(candidates) < 1:
            errors.append(f"ER1 candidate_for_review lacks a concrete identity candidate: {mention_id}")
        errors.extend(_target_valid(target, people_by_id=people_by_id, candidates_by_id=candidates_by_id, label=f"ER1 target {mention_id}"))
        for number, candidate in enumerate(candidates):
            errors.extend(_target_valid(candidate, people_by_id=people_by_id, candidates_by_id=candidates_by_id, label=f"ER1 candidate {mention_id}[{number}]"))
        for evidence_id in row.get("resolution_evidence_ids", []):
            if evidence_id not in evidence_ids:
                errors.append(f"ER1 resolution Evidence does not resolve: {mention_id}/{evidence_id}")
        if row.get("resolution_decision_source") == "human_review" and row.get("resolution_review_status") != "reviewed":
            errors.append(f"ER1 human resolution is not reviewed: {mention_id}")

    if set(effective_by_id) != set(raw_by_id):
        errors.append("ER1 effective Mention IDs do not exactly cover canonical Mentions")

    decisions = [item for item in decisions_document.get("decisions", []) if isinstance(item, Mapping)]
    if decisions_document.get("schema") != 1 or decisions_document.get("stage") != "er1-person-resolution-decisions":
        errors.append("ER1 human decision document has invalid schema/stage")
    decision_by_id: dict[str, Mapping[str, Any]] = {}
    for decision in decisions:
        mention_id = decision.get("mention_id")
        if not isinstance(mention_id, str) or mention_id in decision_by_id:
            errors.append(f"ER1 duplicate/invalid human decision: {mention_id!r}")
            continue
        decision_by_id[mention_id] = decision
        if mention_id not in raw_by_id:
            errors.append(f"ER1 decision references unknown Mention: {mention_id}")
        errors.extend(_target_valid(decision.get("target"), people_by_id=people_by_id, candidates_by_id=candidates_by_id, label=f"ER1 decision {mention_id}"))
        for evidence_id in decision.get("evidence_ids", []):
            if evidence_id not in evidence_ids:
                errors.append(f"ER1 decision Evidence does not resolve: {mention_id}/{evidence_id}")
        effective_row = effective_by_id.get(mention_id)
        if effective_row is None:
            continue
        if effective_row.get("resolution_decision_source") != "human_review":
            errors.append(f"ER1 reviewed decision was not applied: {mention_id}")
        if effective_row.get("resolution_status") != decision.get("resolution_status") or effective_row.get("resolution_target") != decision.get("target"):
            errors.append(f"ER1 effective result disagrees with reviewed decision: {mention_id}")

    queue_records = [item for item in queue.get("records", []) if isinstance(item, Mapping)]
    queue_ids: set[str] = set()
    for record in queue_records:
        review_id = record.get("review_id")
        mention_id = record.get("mention_id")
        if not isinstance(review_id, str) or review_id in queue_ids:
            errors.append(f"ER1 duplicate/invalid review ID: {review_id!r}")
        else:
            queue_ids.add(review_id)
        effective_row = effective_by_id.get(str(mention_id))
        if effective_row is None:
            errors.append(f"ER1 review queue references unknown Mention: {mention_id!r}")
            continue
        if record.get("story_id") not in story_ids:
            errors.append(f"ER1 review queue references unknown Story: {record.get('story_id')!r}")
        if record.get("resolution_status") != effective_row.get("resolution_status"):
            errors.append(f"ER1 review queue status disagrees with effective Mention: {mention_id}")
        if record.get("resolution_status") == "candidate_for_review" and len(record.get("candidates", [])) < 1:
            errors.append(f"ER1 review queue candidate lacks a concrete identity: {mention_id}")

    collision_records = [item for item in collisions.get("records", []) if isinstance(item, Mapping)]
    if collisions.get("collision_count") != len(collision_records):
        errors.append("ER1 collision_count does not match records length")
    collision_by_surface = {str(item.get("surface")): item for item in collision_records}
    wen_du = collision_by_surface.get("文度")
    if wen_du is None:
        errors.append("ER1 collision registry lacks 文度")
    else:
        keys = {
            _target_key(identity)
            for identity in wen_du.get("candidate_identities", [])
            if isinstance(identity, Mapping)
        }
        if "production_person:person-015" not in keys:
            errors.append("ER1 文度 collision registry lacks 孫晷/person-015")
        if not any(key.startswith("identity_candidate:candidate-identity-067-") for key in keys):
            errors.append("ER1 文度 collision registry lacks 王坦之 candidate")
    for row in collision_records:
        if row.get("resolution_policy") != "never globally unique; require Story-local evidence or human review":
            errors.append(f"ER1 collision has unsafe global policy: {row.get('surface')}")

    regression_ids = {
        str(item.get("mention_id"))
        for item in raw_mentions
        if item.get("entry_id") == "05-fangzheng-058" and item.get("surface") == "文度"
    }
    if not regression_ids:
        errors.append("ER1 regression Story has no 文度 Mentions")
    for mention_id in sorted(regression_ids):
        row = effective_by_id.get(mention_id, {})
        target = row.get("resolution_target")
        if row.get("resolution_status") != "resolved" or not isinstance(target, Mapping) or target.get("target_kind") != "identity_candidate" or target.get("candidate_id") != "candidate-identity-067-liezhuan-002-e72bf92e965f":
            errors.append(f"ER1 王文度 regression is not resolved to 王坦之: {mention_id}")
        if row.get("person_id") == "person-015":
            errors.append(f"ER1 王文度 regression still navigates to 孫晷: {mention_id}")

    return errors


if __name__ == "__main__":
    problems = validate()
    if problems:
        print("ER1 person-resolution validation failed:")
        for problem in problems:
            print(f"- {problem}")
        raise SystemExit(1)
    print("ER1 person-resolution validation passed")
