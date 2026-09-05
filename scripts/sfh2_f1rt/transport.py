"""Bounded live transport for SFH2.2-F1RT.

The transport is deliberately separate from the historical F1 client.  It
archives raw provider witnesses outside the repository and emits only compact
transport accounting.  A semantic recovery replay is one logical replay; a
transient network retry is accounted for separately and is never allowed to
become an additional semantic replay.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import statistics
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from .common import (
    ENDPOINT,
    MODEL,
    RECOVERY_MAX_NETWORK_RETRIES,
    TEMPERATURE,
    THINKING,
    canonical_json,
    read_json,
    stable_hash,
    text,
    write_json,
)


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


def _witness(response: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(response).encode("utf-8")).hexdigest()


def _scrub(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if any(token in str(key).lower() for token in ("secret", "token", "api_key", "authorization")) else _scrub(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_scrub(child) for child in value]
    return value


def _error_details(exc: BaseException) -> dict[str, Any]:
    body = text(getattr(exc, "provider_error_body", ""))
    secret = os.environ.get("DEEPSEEK_API_KEY")
    if secret:
        body = body.replace(secret, "[REDACTED]")
    try:
        decoded = json.loads(body) if body else None
    except (TypeError, ValueError):
        decoded = None
    safe = json.dumps(_scrub(decoded), ensure_ascii=False, sort_keys=True, separators=(",", ":")) if decoded is not None else body
    result: dict[str, Any] = {
        "http_status": getattr(exc, "http_status", None),
        "provider_error_body": safe[:4000],
    }
    error = decoded.get("error") if isinstance(decoded, Mapping) else decoded
    if isinstance(error, Mapping):
        for key in ("code", "message", "type", "param"):
            if error.get(key) is not None:
                result["provider_error_" + key] = text(error.get(key))[:1000]
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


def extract(response: Mapping[str, Any], function_name: str) -> tuple[Mapping[str, Any] | None, str | None]:
    import hng2_schema_controller as controller

    payload, _, error = controller.extract_strict_tool_payload(response, expected_function_name=function_name)
    return payload, error


class F1RTClient:
    """Provider client with no path into a protected historical namespace."""

    def __init__(self, *, live: bool, run_id: str) -> None:
        self.live = live
        self.run_id = run_id
        self.records: list[dict[str, Any]] = []
        self.provider_attempts = 0
        self.raw_root = Path("/tmp") / ("sfh2-f1rt-raw-" + _slug(run_id))
        self.raw_root.mkdir(parents=True, exist_ok=True)
        self.sequence = 0

    def _archive(self, stage: str, unit_id: str, attempt: int, response: Mapping[str, Any]) -> tuple[str, str]:
        self.sequence += 1
        path = self.raw_root / f"{self.sequence:04d}-{_slug(stage)}-{_slug(unit_id)}-attempt{attempt}.json"
        write_json(path, response)
        return str(path), hashlib.sha256(path.read_bytes()).hexdigest()

    def _offline_row(self, stage: str, unit_id: str, request_hash: str, attempt_class: str) -> dict[str, Any]:
        return {
            "stage": stage,
            "unit_id": unit_id,
            "request_hash": request_hash,
            "attempt_class": attempt_class,
            "model": MODEL,
            "temperature": TEMPERATURE,
            "thinking": dict(THINKING),
            "classification": "offline_no_provider_call",
            "valid": False,
            "provider_call": False,
            "network_retry": False,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "elapsed_seconds": 0,
        }

    def call(
        self,
        *,
        stage: str,
        unit_id: str,
        system: str,
        payload: Mapping[str, Any],
        tool: Mapping[str, Any],
        function_name: str,
        prompt_version: str,
        request_hash: str,
        max_tokens: int,
        attempt_class: str,
        network_retry_allowed: bool = True,
    ) -> tuple[Mapping[str, Any] | None, dict[str, Any]]:
        if not self.live:
            row = self._offline_row(stage, unit_id, request_hash, attempt_class)
            self.records.append(row)
            return None, row

        from smoke_deepseek import call_deepseek

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": canonical_json(payload)},
        ]
        max_network_retries = RECOVERY_MAX_NETWORK_RETRIES if network_retry_allowed else 0
        history: list[dict[str, Any]] = []
        final_payload: Mapping[str, Any] | None = None
        final_row: dict[str, Any] | None = None
        for attempt in range(1, max_network_retries + 2):
            self.provider_attempts += 1
            started = time.monotonic()
            try:
                response = call_deepseek(
                    messages,
                    model=MODEL,
                    temperature=TEMPERATURE,
                    thinking=THINKING,
                    max_tokens=max_tokens,
                    timeout=180,
                    endpoint=ENDPOINT,
                    tools=[dict(tool)],
                    tool_choice={"type": "function", "function": {"name": function_name}},
                )
                raw_path, raw_sha = self._archive(stage, unit_id, attempt, response)
                extracted, parse_error = extract(response, function_name)
                finish = _finish(response)
                classification = "response_truncated" if finish == "length" else "parsed" if extracted is not None and parse_error is None else "response_parse_failure"
                final_row = {
                    "stage": stage,
                    "unit_id": unit_id,
                    "request_hash": request_hash,
                    "attempt_class": attempt_class,
                    "model": MODEL,
                    "temperature": TEMPERATURE,
                    "thinking": dict(THINKING),
                    "endpoint": ENDPOINT,
                    "prompt_version": prompt_version,
                    "function_name": function_name,
                    "attempt": attempt,
                    "classification": classification,
                    "valid": classification == "parsed",
                    "provider_call": True,
                    "network_retry": attempt > 1,
                    "raw_archive_path": raw_path,
                    "raw_archive_sha256": raw_sha,
                    "provider_witness_hash": _witness(response),
                    "parse_error": parse_error,
                    "usage": _usage(response),
                    "finish_reason": finish,
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                }
                final_payload = extracted if classification == "parsed" else None
                break
            except Exception as exc:
                retryable = is_retryable(exc)
                details = _error_details(exc)
                history.append({"attempt": attempt, "classification": "provider_request_failure", "retryable": retryable, **details})
                final_row = {
                    "stage": stage,
                    "unit_id": unit_id,
                    "request_hash": request_hash,
                    "attempt_class": attempt_class,
                    "model": MODEL,
                    "temperature": TEMPERATURE,
                    "thinking": dict(THINKING),
                    "endpoint": ENDPOINT,
                    "prompt_version": prompt_version,
                    "function_name": function_name,
                    "attempt": attempt,
                    "classification": "provider_request_failure",
                    "valid": False,
                    "provider_call": True,
                    "network_retry": attempt > 1,
                    "retryable": retryable,
                    "exception_class": type(exc).__name__,
                    "exception_message": str(exc)[:1200],
                    **details,
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                }
                if not retryable or attempt > max_network_retries:
                    break
        if final_row is None:
            raise RuntimeError("f1rt_transport_internal_no_result")
        if history:
            final_row["network_attempt_history"] = history
        self.records.append(final_row)
        return final_payload, final_row

    def probe(
        self,
        *,
        stage: str,
        messages: Sequence[Mapping[str, Any]],
        tool: Mapping[str, Any],
        function_name: str,
        request_hash: str,
        max_tokens: int,
    ) -> tuple[Mapping[str, Any] | None, dict[str, Any]]:
        payload = {"probe": True, "stage": stage}
        if not self.live:
            row = self._offline_row(stage, "schema-probe", request_hash, "contract_probe")
            self.records.append(row)
            return None, row
        from smoke_deepseek import call_deepseek

        started = time.monotonic()
        self.provider_attempts += 1
        try:
            response = call_deepseek(
                list(messages),
                model=MODEL,
                temperature=TEMPERATURE,
                thinking=THINKING,
                max_tokens=max_tokens,
                timeout=180,
                endpoint=ENDPOINT,
                tools=[dict(tool)],
                tool_choice={"type": "function", "function": {"name": function_name}},
            )
            raw_path, raw_sha = self._archive(stage, "schema-probe", 1, response)
            extracted, parse_error = extract(response, function_name)
            finish = _finish(response)
            row = {
                "stage": stage,
                "unit_id": "schema-probe",
                "request_hash": request_hash,
                "attempt_class": "contract_probe",
                "model": MODEL,
                "temperature": TEMPERATURE,
                "thinking": dict(THINKING),
                "endpoint": ENDPOINT,
                "function_name": function_name,
                "attempt": 1,
                "classification": "parsed" if extracted is not None and parse_error is None else "response_parse_failure",
                "valid": extracted is not None and parse_error is None,
                "provider_call": True,
                "network_retry": False,
                "raw_archive_path": raw_path,
                "raw_archive_sha256": raw_sha,
                "provider_witness_hash": _witness(response),
                "parse_error": parse_error,
                "usage": _usage(response),
                "finish_reason": finish,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
        except Exception as exc:
            row = {
                "stage": stage,
                "unit_id": "schema-probe",
                "request_hash": request_hash,
                "attempt_class": "contract_probe",
                "model": MODEL,
                "temperature": TEMPERATURE,
                "thinking": dict(THINKING),
                "endpoint": ENDPOINT,
                "function_name": function_name,
                "attempt": 1,
                "classification": "provider_request_failure",
                "valid": False,
                "provider_call": True,
                "network_retry": False,
                "exception_class": type(exc).__name__,
                "exception_message": str(exc)[:1200],
                **_error_details(exc),
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
            extracted = None
        self.records.append(row)
        return extracted, row

    def accounting(self) -> dict[str, Any]:
        by_stage: dict[str, Any] = {}
        for stage in sorted({text(row.get("stage")) for row in self.records if text(row.get("stage"))}):
            stage_rows = [row for row in self.records if text(row.get("stage")) == stage]
            latencies = [float(row.get("elapsed_seconds") or 0) for row in stage_rows if float(row.get("elapsed_seconds") or 0) > 0]
            usages = [row.get("usage") or {} for row in stage_rows]
            by_stage[stage] = {
                "records": len(stage_rows),
                "provider_calls": sum(row.get("provider_call") is True for row in stage_rows),
                "parsed": sum(row.get("classification") == "parsed" for row in stage_rows),
                "parse_or_truncation_failures": sum(row.get("classification") in {"response_parse_failure", "response_truncated"} for row in stage_rows),
                "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in stage_rows),
                "network_retries": sum(row.get("network_retry") is True for row in stage_rows),
                "prompt_tokens": sum(int(item.get("prompt_tokens") or 0) for item in usages),
                "completion_tokens": sum(int(item.get("completion_tokens") or 0) for item in usages),
                "total_tokens": sum(int(item.get("total_tokens") or 0) for item in usages),
                "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0,
                "max_latency_seconds": round(max(latencies), 3) if latencies else 0,
            }
        usages = [row.get("usage") or {} for row in self.records]
        latencies = [float(row.get("elapsed_seconds") or 0) for row in self.records if float(row.get("elapsed_seconds") or 0) > 0]
        return {
            "schema": "sfh2-f1rt-provider-accounting-v1",
            "run_id": self.run_id,
            "model": MODEL,
            "temperature": TEMPERATURE,
            "thinking": dict(THINKING),
            "endpoint": ENDPOINT,
            "provider_calls": sum(row.get("provider_call") is True for row in self.records),
            "provider_attempts": self.provider_attempts,
            "network_retries": sum(row.get("network_retry") is True for row in self.records),
            "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in self.records),
            "parse_or_truncation_failures": sum(row.get("classification") in {"response_parse_failure", "response_truncated"} for row in self.records),
            "prompt_tokens": sum(int(item.get("prompt_tokens") or 0) for item in usages),
            "completion_tokens": sum(int(item.get("completion_tokens") or 0) for item in usages),
            "total_tokens": sum(int(item.get("total_tokens") or 0) for item in usages),
            "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0,
            "max_latency_seconds": round(max(latencies), 3) if latencies else 0,
            "by_stage": by_stage,
            "raw_provider_storage": "external_archive_default",
            "candidate_only": True,
            "canonical_write_back": False,
        }
