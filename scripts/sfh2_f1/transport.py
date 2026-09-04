"""F1 live transport with external raw witnesses and one-retry policy."""

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
    OUT,
    TEMPERATURE,
    THINKING,
    canonical_json,
    external_raw_root,
    frozen_policy_documents,
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


def extract(response: Mapping[str, Any], function_name: str) -> tuple[Mapping[str, Any] | None, str | None]:
    import hng2_schema_controller as controller

    payload, _, error = controller.extract_strict_tool_payload(response, expected_function_name=function_name)
    return payload, error


class F1Client:
    """Transport that keeps raw responses external and compact accounting in F1."""

    def __init__(self, *, live: bool, run_id: str = "sfh2-f1-live-v1") -> None:
        self.live = live
        self.run_id = run_id
        self.failure_policy = frozen_policy_documents()["provider_failure"]
        self.raw_root = external_raw_root() / _slug(run_id)
        self.raw_root.mkdir(parents=True, exist_ok=True)
        self.transport_path = OUT / "transport-log.json"
        stored = read_json(self.transport_path, []) or []
        self.records: list[dict[str, Any]] = [dict(row) for row in stored if isinstance(row, Mapping)]
        self.sequence = max(
            (int(path.name.split("-", 1)[0]) for path in self.raw_root.glob("*.json") if path.name.split("-", 1)[0].isdigit()),
            default=0,
        )
        self.provider_attempts = sum(
            max(1, int(row.get("attempt") or 1))
            for row in self.records
            if row.get("provider_call") is True
        )

    def _persist(self) -> None:
        write_json(self.transport_path, self.records)

    def _archive_response(self, stage: str, unit_id: str, attempt: int, response: Mapping[str, Any]) -> tuple[str, str]:
        self.sequence += 1
        path = self.raw_root / f"{self.sequence:05d}-{_slug(stage)}-{_slug(unit_id)}-attempt{attempt}.json"
        write_json(path, response)
        return str(path), hashlib.sha256(path.read_bytes()).hexdigest()

    def record_cache_hit(
        self,
        *,
        stage: str,
        unit_id: str,
        request_hash_value: str,
        source: str,
        provider_witness_hash: str | None = None,
    ) -> dict[str, Any]:
        row = {
            "stage": stage,
            "unit_id": unit_id,
            "request_hash": request_hash_value,
            "model": MODEL,
            "temperature": TEMPERATURE,
            "thinking": dict(THINKING),
            "classification": "cache_hit",
            "cache_hit": True,
            "provider_call": False,
            "cache_source": source,
            "provider_witness_hash": provider_witness_hash,
            "response_witness_sha256": provider_witness_hash,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "elapsed_seconds": 0,
        }
        self.records.append(row)
        self._persist()
        return row

    def probe(
        self,
        *,
        stage: str,
        messages: Sequence[Mapping[str, Any]],
        tool: Mapping[str, Any],
        function_name: str,
        request_hash_value: str,
    ) -> tuple[Mapping[str, Any] | None, dict[str, Any]]:
        if not self.live:
            row = {
                "stage": stage,
                "unit_id": "schema-probe",
                "request_hash": request_hash_value,
                "classification": "offline_no_provider_call",
                "valid": False,
                "provider_call": False,
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "elapsed_seconds": 0,
            }
            self.records.append(row)
            self._persist()
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
                max_tokens=1800 if stage == "probe_identity" else 500,
                timeout=180,
                endpoint=ENDPOINT,
                tools=[dict(tool)],
                tool_choice={"type": "function", "function": {"name": function_name}},
            )
            raw_path, raw_sha = self._archive_response(stage, "schema-probe", 1, response)
            payload, parse_error = extract(response, function_name)
            row = {
                "stage": stage,
                "unit_id": "schema-probe",
                "request_hash": request_hash_value,
                "model": MODEL,
                "temperature": TEMPERATURE,
                "thinking": dict(THINKING),
                "prompt_version": stage,
                "attempt": 1,
                "classification": "parsed" if payload is not None and parse_error is None else "response_parse_failure",
                "valid": payload is not None and parse_error is None,
                "provider_call": True,
                "raw_archive_path": raw_path,
                "raw_archive_sha256": raw_sha,
                "provider_witness_hash": _witness(response),
                "parse_error": parse_error,
                "usage": _usage(response),
                "finish_reason": _finish(response),
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
        except Exception as exc:
            row = {
                "stage": stage,
                "unit_id": "schema-probe",
                "request_hash": request_hash_value,
                "model": MODEL,
                "temperature": TEMPERATURE,
                "thinking": dict(THINKING),
                "prompt_version": stage,
                "attempt": 1,
                "classification": "provider_request_failure",
                "valid": False,
                "provider_call": True,
                "retryable": False,
                "exception_class": type(exc).__name__,
                "exception_message": str(exc)[:1200],
                **_error_details(exc),
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
            payload = None
        self.records.append(row)
        self._persist()
        return payload, row

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
        request_hash_value: str,
        max_tokens: int,
    ) -> tuple[Mapping[str, Any] | None, dict[str, Any]]:
        if not self.live:
            row = {
                "stage": stage,
                "unit_id": unit_id,
                "request_hash": request_hash_value,
                "model": MODEL,
                "temperature": TEMPERATURE,
                "thinking": dict(THINKING),
                "prompt_version": prompt_version,
                "classification": "offline_no_provider_call",
                "valid": False,
                "provider_call": False,
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "elapsed_seconds": 0,
            }
            self.records.append(row)
            self._persist()
            return None, row
        from smoke_deepseek import call_deepseek

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": canonical_json(payload)},
        ]
        attempt_history: list[dict[str, Any]] = []
        final_payload: Mapping[str, Any] | None = None
        final_row: dict[str, Any] | None = None
        transient_policy = self.failure_policy.get("transient_429_5xx_timeout_connection_reset") or {}
        max_retries = int(transient_policy.get("max_retries", 0))
        for attempt in range(1, max_retries + 2):
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
                raw_path, raw_sha = self._archive_response(stage, unit_id, attempt, response)
                extracted, parse_error = extract(response, function_name)
                finish_reason = _finish(response)
                classification = "response_truncated" if finish_reason == "length" else "parsed" if extracted is not None and parse_error is None else "response_parse_failure"
                final_row = {
                    "stage": stage,
                    "unit_id": unit_id,
                    "request_hash": request_hash_value,
                    "model": MODEL,
                    "temperature": TEMPERATURE,
                    "thinking": dict(THINKING),
                    "prompt_version": prompt_version,
                    "attempt": attempt,
                    "classification": classification,
                    "valid": classification == "parsed",
                    "provider_call": True,
                    "raw_archive_path": raw_path,
                    "raw_archive_sha256": raw_sha,
                    "provider_witness_hash": _witness(response),
                    "parse_error": parse_error,
                    "usage": _usage(response),
                    "finish_reason": finish_reason,
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                }
                final_payload = extracted if classification == "parsed" else None
                break
            except Exception as exc:
                retryable = is_retryable(exc)
                attempt_history.append({
                    "attempt": attempt,
                    "classification": "provider_request_failure",
                    "retryable": retryable,
                    **_error_details(exc),
                })
                final_row = {
                    "stage": stage,
                    "unit_id": unit_id,
                    "request_hash": request_hash_value,
                    "model": MODEL,
                    "temperature": TEMPERATURE,
                    "thinking": dict(THINKING),
                    "prompt_version": prompt_version,
                    "attempt": attempt,
                    "classification": "provider_request_failure",
                    "valid": False,
                    "provider_call": True,
                    "retryable": retryable,
                    "exception_class": type(exc).__name__,
                    "exception_message": str(exc)[:1200],
                    **_error_details(exc),
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                }
                if not retryable:
                    break
        if final_row is None:
            raise RuntimeError("f1_transport_internal_no_result")
        if attempt_history:
            final_row["attempt_history"] = attempt_history
        self.records.append(final_row)
        self._persist()
        return final_payload, final_row

    def metrics(self) -> dict[str, Any]:
        stages = sorted({text(row.get("stage")) for row in self.records if text(row.get("stage"))})
        by_stage: dict[str, Any] = {}
        for stage in stages:
            stage_rows = [row for row in self.records if text(row.get("stage")) == stage]
            latencies = [float(row.get("elapsed_seconds") or 0) for row in stage_rows if float(row.get("elapsed_seconds") or 0) > 0]
            usages = [row.get("usage") or {} for row in stage_rows]
            by_stage[stage] = {
                "records": len(stage_rows),
                "provider_calls": sum(row.get("provider_call") is True for row in stage_rows),
                "cache_hits": sum(row.get("cache_hit") is True for row in stage_rows),
                "parsed": sum(row.get("classification") == "parsed" for row in stage_rows),
                "invalid_or_parse_failures": sum(row.get("classification") in {"response_parse_failure", "response_truncated"} for row in stage_rows),
                "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in stage_rows),
                "retries": sum(int(row.get("attempt") or 1) > 1 for row in stage_rows),
                "prompt_tokens": sum(int(item.get("prompt_tokens") or 0) for item in usages),
                "completion_tokens": sum(int(item.get("completion_tokens") or 0) for item in usages),
                "total_tokens": sum(int(item.get("total_tokens") or 0) for item in usages),
                "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0,
                "max_latency_seconds": round(max(latencies), 3) if latencies else 0,
            }
        usages = [row.get("usage") or {} for row in self.records]
        latencies = [float(row.get("elapsed_seconds") or 0) for row in self.records if float(row.get("elapsed_seconds") or 0) > 0]
        return {
            "schema": "sfh2-f1-provider-accounting-v1",
            "model": MODEL,
            "temperature": TEMPERATURE,
            "thinking": dict(THINKING),
            "endpoint": ENDPOINT,
            "run_id": self.run_id,
            "provider_calls": sum(row.get("provider_call") is True for row in self.records),
            "cache_hits": sum(row.get("cache_hit") is True for row in self.records),
            "provider_attempts": self.provider_attempts,
            "retries": sum(int(row.get("attempt") or 1) > 1 for row in self.records),
            "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in self.records),
            "invalid_payloads": sum(row.get("classification") in {"response_parse_failure", "response_truncated"} for row in self.records),
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
