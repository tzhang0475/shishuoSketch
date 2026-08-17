#!/usr/bin/env python3
"""Isolated F0 feedback persistence and validation primitives.

This module deliberately knows nothing about canonical historical annotation
materialization.  The local repository stores raw feedback in the ignored
``.cache`` tree; a future HTTP/database adapter can implement the same small
repository contract without changing the frontend or the reviewed export.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol


ROOT = Path(__file__).resolve().parents[1]
RAW_RELATIVE_PATH = Path(".cache/shishuo-feedback/raw-feedback.jsonl")
REVIEWED_RELATIVE_PATH = Path("data/annotation/user-feedback-reviewed.json")

FEEDBACK_SCHEMA = "f0-raw-feedback"
REVIEWED_SCHEMA = "f0-reviewed-feedback"

CATEGORIES = {"text", "historical_fact", "narrative", "bug", "other"}
TARGET_TYPES = {"story", "evidence", "narrative", "person", "relation"}
STATUSES = {"new", "triaged", "duplicate", "accepted", "rejected", "needs_review", "resolved"}
REVIEWED_STATUSES = {"accepted", "rejected", "duplicate", "resolved"}
REASON_CODES: dict[str, set[str]] = {
    "text": {"incorrect_text", "punctuation", "missing_text", "other"},
    "historical_fact": {"inaccurate", "insufficient_evidence", "missing_context", "other"},
    "narrative": {"inaccurate", "unnecessary", "overinterpreted", "insufficient_evidence", "missing_context", "other"},
    "bug": {"layout", "interaction", "data_loading", "other"},
    "other": {"other"},
}

MAX_ID_LENGTH = 240
MAX_COMMENT_LENGTH = 2000
MAX_SNAPSHOT_LENGTH = 500
MAX_URL_LENGTH = 2048
MAX_VERSION_LENGTH = 160

_TAG_RE = re.compile(r"<[^>]*>")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class FeedbackValidationError(ValueError):
    """Raised when a feedback payload crosses the storage boundary invalidly."""


class RateLimitHook(Protocol):
    def __call__(self, payload: Mapping[str, Any]) -> bool: ...


class FeedbackRepository(Protocol):
    def submit(self, payload: Mapping[str, Any]) -> dict[str, Any]: ...

    def list_for_target(
        self,
        story_id: str,
        target_type: str | None = None,
        target_id: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def update_review(
        self,
        feedback_id: str,
        status: str,
        review_note: str = "",
        duplicate_of: str | None = None,
    ) -> dict[str, Any]: ...


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def sanitize_plain_text(value: Any, limit: int) -> str:
    """Strip markup/control characters while retaining readable user text."""

    text = "" if value is None else str(value)
    text = html.unescape(_TAG_RE.sub(" ", text))
    text = _CONTROL_RE.sub("", text).replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()[:limit]


def _required_text(payload: Mapping[str, Any], key: str, limit: int) -> str:
    value = sanitize_plain_text(payload.get(key), limit)
    if not value:
        raise FeedbackValidationError(f"feedback field is required: {key}")
    return value


def normalize_submission(payload: Mapping[str, Any]) -> dict[str, Any]:
    story_id = _required_text(payload, "story_id", MAX_ID_LENGTH)
    target_type = _required_text(payload, "target_type", 40)
    if target_type not in TARGET_TYPES:
        raise FeedbackValidationError(f"invalid target_type: {target_type}")
    target_id = sanitize_plain_text(payload.get("target_id"), MAX_ID_LENGTH)
    if target_type != "story" and not target_id:
        raise FeedbackValidationError("target_id is required for non-story feedback")

    category = _required_text(payload, "category", 40)
    if category not in CATEGORIES:
        raise FeedbackValidationError(f"invalid category: {category}")
    reason_code = _required_text(payload, "reason_code", 80)
    if reason_code not in REASON_CODES[category]:
        raise FeedbackValidationError(f"invalid reason_code for {category}: {reason_code}")

    result: dict[str, Any] = {
        "story_id": story_id,
        "target_type": target_type,
        "category": category,
        "reason_code": reason_code,
        "page_url": sanitize_plain_text(payload.get("page_url"), MAX_URL_LENGTH),
        "frontend_version": sanitize_plain_text(payload.get("frontend_version"), MAX_VERSION_LENGTH),
        "data_version": sanitize_plain_text(payload.get("data_version"), MAX_VERSION_LENGTH),
    }
    if target_id:
        result["target_id"] = target_id
    comment = sanitize_plain_text(payload.get("comment"), MAX_COMMENT_LENGTH)
    snapshot = sanitize_plain_text(payload.get("target_text_snapshot"), MAX_SNAPSHOT_LENGTH)
    if comment:
        result["comment"] = comment
    if snapshot:
        result["target_text_snapshot"] = snapshot
    return result


def feedback_fingerprint(payload: Mapping[str, Any]) -> str:
    duplicate_basis = {
        key: payload.get(key, "")
        for key in ("story_id", "target_type", "target_id", "category", "reason_code", "comment", "target_text_snapshot")
    }
    encoded = stable_json(duplicate_basis).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sorted_records(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(record)
        for record in sorted(
            records,
            key=lambda record: (str(record.get("created_at", "")), str(record.get("feedback_id", ""))),
        )
    ]


class LocalFeedbackRepository:
    """Ignored JSONL development store; never a canonical-data input."""

    def __init__(
        self,
        root: Path = ROOT,
        now: Callable[[], str] = _now_iso,
        rate_limit_hook: RateLimitHook | None = None,
    ) -> None:
        self.root = root
        self.path = root / RAW_RELATIVE_PATH
        self.now = now
        self.rate_limit_hook = rate_limit_hook or (lambda _payload: True)

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise FeedbackValidationError(f"invalid raw feedback JSONL at line {line_number}") from error
            if not isinstance(value, dict):
                raise FeedbackValidationError(f"raw feedback record at line {line_number} is not an object")
            records.append(value)
        return records

    def _save(self, records: Iterable[Mapping[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for record in _sorted_records(records)
        )
        self.path.write_text(text, encoding="utf-8")

    def submit(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        normalized = normalize_submission(payload)
        if not self.rate_limit_hook(normalized):
            raise FeedbackValidationError("feedback rate limit reached")
        records = self._load()
        fingerprint = feedback_fingerprint(normalized)
        duplicate_of = next(
            (
                str(record["feedback_id"])
                for record in records
                if record.get("fingerprint") == fingerprint and record.get("status") not in {"rejected", "duplicate"}
            ),
            None,
        )
        record: dict[str, Any] = {
            "schema": FEEDBACK_SCHEMA,
            "feedback_id": f"feedback-{uuid.uuid4().hex}",
            **normalized,
            "fingerprint": fingerprint,
            "status": "duplicate" if duplicate_of else "new",
            "created_at": self.now(),
        }
        if duplicate_of:
            record["duplicate_of"] = duplicate_of
        records.append(record)
        self._save(records)
        return record

    def list_for_target(
        self,
        story_id: str,
        target_type: str | None = None,
        target_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return _sorted_records(
            record
            for record in self._load()
            if record.get("story_id") == story_id
            and (target_type is None or record.get("target_type") == target_type)
            and (target_id is None or record.get("target_id") == target_id)
        )

    def update_review(
        self,
        feedback_id: str,
        status: str,
        review_note: str = "",
        duplicate_of: str | None = None,
    ) -> dict[str, Any]:
        if status not in STATUSES:
            raise FeedbackValidationError(f"invalid feedback status: {status}")
        records = self._load()
        target = next((record for record in records if record.get("feedback_id") == feedback_id), None)
        if target is None:
            raise FeedbackValidationError(f"unknown feedback_id: {feedback_id}")
        if duplicate_of == feedback_id:
            raise FeedbackValidationError("feedback cannot duplicate itself")
        target["status"] = status
        target["review_note"] = sanitize_plain_text(review_note, MAX_COMMENT_LENGTH)
        if duplicate_of:
            if not any(record.get("feedback_id") == duplicate_of for record in records):
                raise FeedbackValidationError(f"unknown duplicate target: {duplicate_of}")
            target["duplicate_of"] = duplicate_of
        else:
            target.pop("duplicate_of", None)
        target["reviewed_at"] = self.now()
        self._save(records)
        return dict(target)


def reviewed_export_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Remove transport/runtime fields before reviewed export."""

    fields = (
        "feedback_id",
        "story_id",
        "target_type",
        "target_id",
        "category",
        "reason_code",
        "comment",
        "target_text_snapshot",
        "data_version",
        "frontend_version",
        "status",
        "duplicate_of",
        "review_note",
        "created_at",
        "reviewed_at",
    )
    return {key: record[key] for key in fields if key in record and record[key] not in (None, "")}
