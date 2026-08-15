#!/usr/bin/env python3
"""Validate the deterministic pre-W4 Person-resolution gap audit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

try:
    from . import person_resolution as pr
except ImportError:  # direct execution
    import person_resolution as pr


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = Path("data/derived/w4-preflight-person-resolution-gap-audit.json")
SCHEMA_PATH = Path("schema/w4-preflight-person-resolution-gap-audit.schema.json")


def _schema_errors(root: Path, value: Any) -> list[str]:
    schema = json.loads((root / SCHEMA_PATH).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return [f"schema: {error.message}" for error in Draft202012Validator(schema).iter_errors(value)]


def _target_errors(target: Any, people: Mapping[str, Mapping[str, Any]], candidates: Mapping[str, Mapping[str, Any]], label: str) -> list[str]:
    if not isinstance(target, Mapping):
        return [f"{label} is not an object"]
    kind = target.get("target_kind")
    if kind == "production_person":
        person_id = str(target.get("person_id", ""))
        person = people.get(person_id)
        if person is None:
            return [f"{label} references unknown Person {person_id}"]
        if target.get("canonical_name") != person.get("canonical_name"):
            return [f"{label} canonical_name does not match {person_id}"]
        return []
    if kind == "identity_candidate":
        candidate_id = str(target.get("candidate_id", ""))
        candidate = candidates.get(candidate_id)
        if candidate is None:
            return [f"{label} references unknown identity candidate {candidate_id}"]
        if target.get("canonical_name") != candidate.get("preferred_name"):
            return [f"{label} canonical_name does not match {candidate_id}"]
        return []
    return [f"{label} has invalid target_kind {kind!r}"]


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        document = pr.read_json(root, AUDIT_PATH)
    except (OSError, ValueError) as exc:
        return [f"cannot read W4 preflight audit: {exc}"]
    errors.extend(_schema_errors(root, document))

    published_ids = pr._published_story_ids(root)
    scope = document.get("scope", {})
    if set(scope.get("published_story_ids", [])) != published_ids:
        errors.append("audit scope Story IDs do not exactly match published Stories")
    if scope.get("published_story_count") != len(published_ids):
        errors.append("audit published_story_count is stale")
    if scope.get("audited_story_count") != len(published_ids):
        errors.append("audit audited_story_count does not cover all published Stories")

    people_document = pr.read_json(root, pr.PEOPLE_PATH)
    people = {
        str(item.get("person_id")): item
        for item in people_document.get("people", [])
        if isinstance(item, Mapping) and isinstance(item.get("person_id"), str)
    }
    candidate_document = pr.read_json(root, pr.IDENTITY_CANDIDATES_PATH)
    candidate_rows = [
        item
        for item in [
            *candidate_document.get("candidates", []),
            *pr.read_json(root, pr.IDENTITY_TARGETS_PATH).get("candidates", []),
        ]
        if isinstance(item, Mapping)
    ]
    candidates = {
        str(item.get("candidate_id")): item
        for item in candidate_rows
        if isinstance(item.get("candidate_id"), str)
    }
    evidence_document = pr.read_json(root, Path("data/evidence/wp1-evidence.json"))
    known_evidence = {
        str(item.get("id"))
        for item in evidence_document.get("records", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    effective = pr.read_json(root, pr.EFFECTIVE_PATH)
    for item in [*candidate_document.get("evidence", []), *effective.get("mentions", []), *effective.get("derived_mentions", [])]:
        if isinstance(item, Mapping):
            known_evidence.update(
                str(evidence_id)
                for evidence_id in item.get("resolution_evidence_ids", [])
                if isinstance(evidence_id, str)
            )

    sections = pr._load_sections(root)
    records = [item for item in document.get("records", []) if isinstance(item, Mapping)]
    if document.get("summary", {}).get("record_count") != len(records):
        errors.append("audit summary record_count does not match records")
    status_counts: dict[str, int] = {}
    record_keys: set[tuple[str, str, int, str]] = set()
    record_ids: set[str] = set()
    for number, record in enumerate(records):
        label = f"record {number}"
        story_id = str(record.get("story_id", ""))
        section = str(record.get("section", ""))
        annotation_id = record.get("annotation_id")
        source_section = (
            f"liu_annotation:{annotation_id}"
            if section == "liu_annotation" and isinstance(annotation_id, str)
            else section
        )
        span = record.get("span", {})
        offset = span.get("offset") if isinstance(span, Mapping) else None
        end = span.get("end_offset_exclusive") if isinstance(span, Mapping) else None
        surface = str(record.get("surface", ""))
        key = (story_id, section, int(offset) if isinstance(offset, int) else -1, surface)
        if key in record_keys:
            errors.append(f"{label} duplicates a source occurrence")
        record_keys.add(key)
        record_id = record.get("audit_record_id")
        if not isinstance(record_id, str) or record_id in record_ids:
            errors.append(f"{label} has a duplicate/invalid audit_record_id")
        elif isinstance(offset, int):
            record_ids.add(record_id)
            expected_id = "w4-preflight-gap-" + __import__("hashlib").sha256(
                f"{story_id}|{section}|{offset}|{surface}".encode("utf-8")
            ).hexdigest()[:24]
            if record_id != expected_id:
                errors.append(f"{label} audit_record_id is not deterministic")
        if story_id not in published_ids:
            errors.append(f"{label} references unpublished Story {story_id}")
        if source_section not in {key[1] for key in sections if key[0] == story_id}:
            errors.append(f"{label} references missing source section {story_id}/{source_section}")
        text = sections.get((story_id, source_section), "")
        if not isinstance(offset, int) or not isinstance(end, int) or end <= offset or text[offset:end] != surface:
            errors.append(f"{label} span does not round-trip to source text")
        if len(surface) % 2 == 0 and surface[: len(surface) // 2] == surface[len(surface) // 2 :]:
            errors.append(f"{label} contains a synthetic repeated alias {surface}")
        status = record.get("status")
        status_counts[str(status)] = status_counts.get(str(status), 0) + 1
        for target_number, target in enumerate(record.get("candidate_targets", [])):
            errors.extend(_target_errors(target, people, candidates, f"{label} candidate_targets[{target_number}]"))
        for evidence_id in record.get("evidence_ids", []):
            if evidence_id not in known_evidence:
                errors.append(f"{label} evidence does not resolve: {evidence_id}")
        existing = record.get("existing_effective_resolution")
        if status == "safe_story_local":
            if not isinstance(existing, Mapping) or existing.get("resolution_status") != "resolved":
                errors.append(f"{label} safe_story_local lacks a resolved effective row")
            if not isinstance(existing, Mapping) or not isinstance(existing.get("resolution_target"), Mapping):
                errors.append(f"{label} safe_story_local lacks a target")
        if status == "non_production_identity" and record.get("candidate_targets"):
            if not any(target.get("target_kind") == "identity_candidate" for target in record["candidate_targets"] if isinstance(target, Mapping)):
                errors.append(f"{label} non_production_identity lacks an identity candidate")

    expected_status_counts = document.get("summary", {}).get("status_counts", {})
    if expected_status_counts != dict(sorted(status_counts.items())):
        errors.append("audit summary status_counts does not match records")
    if document.get("summary", {}).get("record_count") != sum(status_counts.values()):
        errors.append("audit summary record total is inconsistent")

    by_story_surface = {(str(item.get("story_id")), str(item.get("surface"))): item for item in records}
    yu_taiwei = [item for item in records if item.get("story_id") == "14-rongzhi-024" and item.get("surface") == "庾太尉"]
    if len(yu_taiwei) != 1:
        errors.append("14-rongzhi-024 must have exactly one 庾太尉 audit record")
    else:
        target = yu_taiwei[0].get("existing_effective_resolution", {}).get("resolution_target")
        if yu_taiwei[0].get("status") != "safe_story_local" or not isinstance(target, Mapping) or target.get("person_id") != "person-010":
            errors.append("14-rongzhi-024 庾太尉 is not safely resolved to person-010")
    yu_gong = [item for item in records if item.get("story_id") == "14-rongzhi-024" and item.get("surface") == "庾公"]
    if len(yu_gong) != 1:
        errors.append("14-rongzhi-024 must have exactly one 庾公 audit record")
    else:
        target = yu_gong[0].get("existing_effective_resolution", {}).get("resolution_target")
        if yu_gong[0].get("status") != "safe_story_local" or not isinstance(target, Mapping) or target.get("person_id") != "person-010":
            errors.append("14-rongzhi-024 庾公 is not safely coreferential to person-010")
    for bare_surface in ("太尉", "公"):
        for record in records:
            if record.get("surface") != bare_surface:
                continue
            target = record.get("existing_effective_resolution", {}).get("resolution_target") if isinstance(record.get("existing_effective_resolution"), Mapping) else None
            if isinstance(target, Mapping) and target.get("person_id") == "person-010":
                errors.append(f"bare {bare_surface} was auto-resolved to 庾亮")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(error)
        return 1
    document = pr.read_json(ROOT, AUDIT_PATH)
    print(
        "W4 preflight Person-resolution audit validation passed: "
        f"{document['scope']['audited_story_count']} Stories; "
        f"{document['summary']['record_count']} records"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
