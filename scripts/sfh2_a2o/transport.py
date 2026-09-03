"""Bounded A2O transport with raw witnesses kept outside the repository."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import statistics
import time
from pathlib import Path
from typing import Any, Mapping

from .common import (
    MAX_PROVIDER_ATTEMPTS,
    MODEL,
    PROMPT_VERSION,
    ROOT,
    STRICT_ENDPOINT,
    THINKING,
    TEMPERATURE,
    canonical_json,
    stable_hash,
    text,
    write_json,
)
from .contracts import FUNCTION_NAME, occurrence_function_tool


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", text(value)).strip("-") or "unit"


def _usage(response: Mapping[str, Any]) -> dict[str, int]:
    usage = response.get("usage") if isinstance(response.get("usage"), Mapping) else {}
    return {key: int(usage.get(key) or 0) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}


def _finish(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        return text(choices[0].get("finish_reason"))
    return ""


def _extract(response: Mapping[str, Any]) -> tuple[Mapping[str, Any] | None, str | None]:
    import hng2_schema_controller as controller

    payload, _, error = controller.extract_strict_tool_payload(response, expected_function_name=FUNCTION_NAME)
    return payload, error


def _error_details(exc: BaseException) -> dict[str, Any]:
    body = text(getattr(exc, "provider_error_body", ""))
    secret = os.environ.get("DEEPSEEK_API_KEY")
    if secret:
        body = body.replace(secret, "[REDACTED]")
    try:
        decoded = json.loads(body) if body else None
    except (TypeError, ValueError):
        decoded = None

    def scrub(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                str(key): "[REDACTED]" if any(token in str(key).lower() for token in ("secret", "token", "api_key", "authorization")) else scrub(child)
                for key, child in value.items()
            }
        if isinstance(value, list):
            return [scrub(child) for child in value]
        return value

    if decoded is not None:
        body = json.dumps(scrub(decoded), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    result: dict[str, Any] = {
        "http_status": getattr(exc, "http_status", None),
        "provider_error_body": body[:4000],
    }
    error = decoded.get("error") if isinstance(decoded, Mapping) else decoded
    if isinstance(error, Mapping):
        for key in ("code", "message", "type", "param"):
            if error.get(key) is not None:
                result[f"provider_error_{key}"] = text(error.get(key))[:1000]
    elif isinstance(error, str) and error:
        result["provider_error_message"] = error[:1000]
    request_id = getattr(exc, "provider_request_id", None)
    if request_id:
        result["provider_request_id"] = text(request_id)[:300]
    return result


def is_retryable(exc: BaseException) -> bool:
    status = getattr(exc, "http_status", None)
    try:
        status = int(status) if status is not None else None
    except (TypeError, ValueError):
        status = None
    if status == 400 or (status is not None and 400 <= status < 500 and status != 429):
        return False
    if status == 429 or (status is not None and status >= 500):
        return True
    message = str(exc).lower()
    return any(token in message for token in ("timed out", "timeout", "connection reset", "temporarily unavailable", "network is unreachable"))


class A2OClient:
    """One-shot-per-request client; raw envelopes are external witnesses."""

    def __init__(self, run_id: str, *, live: bool) -> None:
        self.run_id = run_id
        self.live = live
        raw_root = Path(os.environ.get("SFH2_A2O_RAW_DIR", "/tmp/sfh2-a2o-live"))
        self.raw_dir = raw_root / _slug(run_id) / "raw-api"
        if live:
            self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.records: list[dict[str, Any]] = []
        self.attempts = 0

    @staticmethod
    def _row_base(stage: str, case_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "stage": stage,
            "case_id": case_id,
            "request_hash": stable_hash({"stage": stage, "case_id": case_id, "payload": payload}),
            "model": MODEL,
            "temperature": TEMPERATURE,
            "thinking": dict(THINKING),
            "prompt_version": PROMPT_VERSION,
        }

    def _save_external_raw(self, sequence: int, stage: str, case_id: str, attempt: int, response: Mapping[str, Any]) -> Path:
        path = self.raw_dir / f"{sequence:05d}-{_slug(stage)}-{_slug(case_id)}-attempt{attempt}.json"
        write_json(path, response)
        return path

    def probe(self, tool: Mapping[str, Any]) -> dict[str, Any]:
        """Make one strict-tool smoke request before case inference."""

        from smoke_deepseek import call_deepseek

        row = self._row_base("schema_probe", "schema-probe", {"probe": True})
        row["attempt"] = 1
        started = time.monotonic()
        if not self.live:
            row.update({"classification": "offline_no_provider_call", "elapsed_seconds": 0, "valid": True})
            return row
        self.attempts += 1
        try:
            response = call_deepseek(
                [{"role": "system", "content": "Return a valid A2O occurrence-function tool response for this schema smoke test. Do not emit identity fields."}, {"role": "user", "content": '{"probe":true}'}],
                model=MODEL,
                temperature=TEMPERATURE,
                thinking=THINKING,
                max_tokens=180,
                timeout=180,
                endpoint=STRICT_ENDPOINT,
                tools=[dict(tool)],
                tool_choice={"type": "function", "function": {"name": FUNCTION_NAME}},
            )
            raw = self._save_external_raw(self.attempts, "schema-probe", "schema-probe", 1, response)
            payload, error = _extract(response)
            row.update({
                "classification": "parsed" if payload is not None and error is None else "response_parse_failure",
                "parse_error": error,
                "valid": payload is not None and error is None,
                "usage": _usage(response),
                "finish_reason": _finish(response),
                "raw_witness_sha256": __import__("hashlib").sha256(raw.read_bytes()).hexdigest(),
            })
        except Exception as exc:
            row.update({"classification": "provider_request_failure", **_error_details(exc), "retryable": False, "valid": False, "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}})
        row["elapsed_seconds"] = round(time.monotonic() - started, 3)
        return row

    def call(self, *, case_id: str, system: str, payload: Mapping[str, Any], tool: Mapping[str, Any]) -> tuple[Mapping[str, Any] | None, dict[str, Any]]:
        from smoke_deepseek import call_deepseek

        row = self._row_base("occurrence_function", case_id, payload)
        if not self.live:
            row.update({"classification": "offline_no_provider_call", "attempt": 0, "elapsed_seconds": 0, "valid": False, "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}})
            return None, row
        for attempt in (1, 2):
            if self.attempts >= MAX_PROVIDER_ATTEMPTS:
                row.update({"classification": "provider_attempt_budget_exhausted", "attempt": attempt, "elapsed_seconds": 0, "valid": False, "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}})
                return None, row
            self.attempts += 1
            started = time.monotonic()
            try:
                response = call_deepseek(
                    [{"role": "system", "content": system}, {"role": "user", "content": canonical_json(payload)}],
                    model=MODEL,
                    temperature=TEMPERATURE,
                    thinking=THINKING,
                    max_tokens=400,
                    timeout=180,
                    endpoint=STRICT_ENDPOINT,
                    tools=[dict(tool)],
                    tool_choice={"type": "function", "function": {"name": FUNCTION_NAME}},
                )
                raw = self._save_external_raw(self.attempts, "occurrence-function", case_id, attempt, response)
                extracted, error = _extract(response)
                row.update({
                    "attempt": attempt,
                    "classification": "parsed" if extracted is not None and error is None else "response_parse_failure",
                    "parse_error": error,
                    "valid": extracted is not None and error is None,
                    "usage": _usage(response),
                    "finish_reason": _finish(response),
                    "raw_witness_sha256": __import__("hashlib").sha256(raw.read_bytes()).hexdigest(),
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                })
                if extracted is not None and error is None:
                    return extracted, row
                return None, row
            except Exception as exc:
                retryable = is_retryable(exc)
                row.update({"attempt": attempt, "classification": "provider_request_failure", **_error_details(exc), "retryable": retryable, "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}, "elapsed_seconds": round(time.monotonic() - started, 3)})
                if not retryable:
                    return None, row
        return None, row


def summarize(rows: list[Mapping[str, Any]], *, live: bool, client_attempts: int = 0) -> dict[str, Any]:
    latencies = [float(row.get("elapsed_seconds") or 0) for row in rows if float(row.get("elapsed_seconds") or 0) > 0]
    usages = [row.get("usage") or {} for row in rows]
    return {
        "schema": "sfh2-a2o-transport-v1",
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "endpoint": STRICT_ENDPOINT,
        "live": live,
        "provider_calls": sum(row.get("stage") in {"schema_probe", "occurrence_function"} and row.get("classification") in {"parsed", "response_parse_failure", "provider_request_failure"} for row in rows),
        "case_calls": sum(row.get("stage") == "occurrence_function" for row in rows),
        "schema_probe_calls": sum(row.get("stage") == "schema_probe" for row in rows),
        "parsed_calls": sum(row.get("classification") == "parsed" for row in rows),
        "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in rows),
        "invalid_payloads": sum(row.get("classification") == "response_parse_failure" for row in rows),
        "retries": sum(int(row.get("attempt") or 0) > 1 for row in rows),
        "provider_attempts": client_attempts,
        "prompt_tokens": sum(int(item.get("prompt_tokens") or 0) for item in usages),
        "completion_tokens": sum(int(item.get("completion_tokens") or 0) for item in usages),
        "total_tokens": sum(int(item.get("total_tokens") or 0) for item in usages),
        "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0,
        "max_latency_seconds": round(max(latencies), 3) if latencies else 0,
        "raw_storage": "external_only_not_committed",
        "candidate_only": True,
        "canonical_write_back": False,
    }
