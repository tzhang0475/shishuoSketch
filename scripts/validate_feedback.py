#!/usr/bin/env python3
"""Validate the isolated F0 raw/reviewed feedback boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

try:
    from .export_user_feedback import build_document
    from .feedback_store import (
        CATEGORIES,
        RAW_RELATIVE_PATH,
        REVIEWED_RELATIVE_PATH,
        REVIEWED_SCHEMA,
        REVIEWED_STATUSES,
        ROOT,
        TARGET_TYPES,
        LocalFeedbackRepository,
        REASON_CODES,
        stable_json,
    )
except ImportError:  # direct ``python3 scripts/validate_feedback.py``
    from export_user_feedback import build_document  # type: ignore[no-redef]
    from feedback_store import (  # type: ignore[no-redef]
        CATEGORIES,
        RAW_RELATIVE_PATH,
        REVIEWED_RELATIVE_PATH,
        REVIEWED_SCHEMA,
        REVIEWED_STATUSES,
        ROOT,
        TARGET_TYPES,
        LocalFeedbackRepository,
        REASON_CODES,
        stable_json,
    )


SC1_PATH = Path("data/derived/sc1-site.json")
SCHEMA_PATH = Path("schema/f0-reviewed-feedback.schema.json")
FORBIDDEN_EXPORT_KEYS = {
    "person_name",
    "canonical_fact",
    "relation_fact",
    "gold_annotation",
    "password",
    "email",
    "user_name",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    output_path = root / REVIEWED_RELATIVE_PATH
    sc1_path = root / SC1_PATH
    if not output_path.is_file():
        errors.append(f"missing reviewed feedback export: {REVIEWED_RELATIVE_PATH.as_posix()}")
        return errors
    if not sc1_path.is_file():
        errors.append(f"missing SC1 reference: {SC1_PATH.as_posix()}")
        return errors
    schema_path = root / SCHEMA_PATH
    if not schema_path.is_file():
        errors.append(f"missing feedback schema: {SCHEMA_PATH.as_posix()}")
        return errors

    document = read_json(output_path)
    expected = build_document(root)
    if stable_json(document) != stable_json(expected):
        errors.append("reviewed feedback export is not deterministic from the local raw store")
    if document.get("schema") != REVIEWED_SCHEMA or document.get("schema_version") != 1:
        errors.append("reviewed feedback schema is invalid")
    if document.get("document_kind") != "user_feedback_reviewed":
        errors.append("reviewed feedback document kind is invalid")
    schema = read_json(schema_path)
    errors.extend(
        f"reviewed feedback schema: {error.message} at /{'/'.join(str(part) for part in error.absolute_path)}"
        for error in Draft202012Validator(schema).iter_errors(document)
    )
    if document.get("policy", {}).get("canonical_write_back") is not False:
        errors.append("feedback export permits canonical write-back")
    if document.get("policy", {}).get("gold_write_back") is not False:
        errors.append("feedback export permits Gold write-back")

    sc1 = read_json(sc1_path)
    stories = {
        str(story.get("id")): story
        for story in sc1.get("stories", [])
        if isinstance(story, Mapping)
        and story.get("publication_state") in {"production_ready", "preview_ready"}
    }
    evidence_by_story = {
        story_id: {str(value) for value in story.get("evidence_ids", [])}
        for story_id, story in stories.items()
    }
    people = {str(row.get("id")) for row in sc1.get("people", []) if isinstance(row, Mapping)}
    relations = {str(row.get("id")) for row in sc1.get("relations", []) if isinstance(row, Mapping)}
    records = document.get("records", [])
    if not isinstance(records, list):
        errors.append("reviewed feedback records is not a list")
        records = []
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, Mapping):
            errors.append("reviewed feedback record is not an object")
            continue
        feedback_id = str(record.get("feedback_id", ""))
        if not feedback_id or feedback_id in seen:
            errors.append(f"duplicate or missing feedback_id: {feedback_id}")
        seen.add(feedback_id)
        if record.get("status") not in REVIEWED_STATUSES:
            errors.append(f"unreviewed status leaked into export: {feedback_id}")
        story_id = str(record.get("story_id", ""))
        if story_id not in stories:
            errors.append(f"feedback references a non-reader-ready Story: {feedback_id}")
        target_type = record.get("target_type")
        if target_type not in TARGET_TYPES:
            errors.append(f"invalid feedback target type: {feedback_id}")
        target_id = record.get("target_id")
        if target_type == "story" and target_id not in (None, "", story_id):
            errors.append(f"Story feedback target does not resolve to its Story: {feedback_id}")
        if target_type == "evidence" and str(target_id) not in evidence_by_story.get(story_id, set()):
            errors.append(f"evidence feedback target is not attached to the Story: {feedback_id}")
        if target_type == "person" and str(target_id) not in people:
            errors.append(f"person feedback target is unknown: {feedback_id}")
        if target_type == "relation" and str(target_id) not in relations:
            errors.append(f"relation feedback target is unknown: {feedback_id}")
        if target_type == "narrative" and str(target_id) != f"story-sketch-nl0-{story_id}":
            errors.append(f"narrative feedback target is not a known Story Sketch ID: {feedback_id}")
        category = record.get("category")
        reason = record.get("reason_code")
        if category not in CATEGORIES or reason not in REASON_CODES.get(str(category), set()):
            errors.append(f"invalid feedback category/reason: {feedback_id}")
        if set(record).intersection(FORBIDDEN_EXPORT_KEYS):
            errors.append(f"identifying/canonical field leaked into feedback export: {feedback_id}")

    raw_path = root / RAW_RELATIVE_PATH
    if raw_path.is_file():
        try:
            raw_records = LocalFeedbackRepository(root=root)._load()  # noqa: SLF001
        except Exception as error:  # pragma: no cover - error text is enough for the validator
            errors.append(str(error))
            raw_records = []
        for record in raw_records:
            if record.get("schema") != "f0-raw-feedback":
                errors.append(f"raw record has invalid schema: {record.get('feedback_id')}")
            if record.get("status") not in {"new", "triaged", "duplicate", "accepted", "rejected", "needs_review", "resolved"}:
                errors.append(f"raw record has invalid status: {record.get('feedback_id')}")

    return errors


def main() -> int:
    errors = validate(ROOT)
    if errors:
        for error in errors:
            print(f"F0 feedback validation failed: {error}")
        return 1
    document = read_json(ROOT / REVIEWED_RELATIVE_PATH)
    print(json.dumps({"status": "pass", "reviewed_records": len(document.get("records", []))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
