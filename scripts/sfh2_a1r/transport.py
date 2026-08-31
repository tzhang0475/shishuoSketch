"""Strict A1R review transport with cached-first replay and safe retries."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import statistics
import time
from pathlib import Path
from typing import Any, Mapping

from sfh2_a0r.contracts import validate_deepseek_strict_schema

from .common import (
    FUNCTION_NAMES,
    MAX_PROVIDER_ATTEMPTS,
    MODEL,
    OUT,
    PILOT_VERSION,
    PROMPT_VERSIONS,
    ROOT,
    STRICT_ENDPOINT,
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
    return {"prompt_tokens": int(usage.get("prompt_tokens") or 0), "completion_tokens": int(usage.get("completion_tokens") or 0), "total_tokens": int(usage.get("total_tokens") or 0)}


def _finish(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        return text(choices[0].get("finish_reason"))
    return ""


def _provider_error(exc: BaseException) -> dict[str, Any]:
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
            return {key: "[REDACTED]" if any(token in str(key).lower() for token in ("secret", "token", "api_key", "authorization")) else scrub(child) for key, child in value.items()}
        if isinstance(value, list):
            return [scrub(child) for child in value]
        return value
    if decoded is not None:
        body = json.dumps(scrub(decoded), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    body = body[:4000]
    result: dict[str, Any] = {"http_status": getattr(exc, "http_status", None), "provider_error_body": body}
    try:
        parsed = json.loads(body) if body else None
    except (TypeError, ValueError):
        parsed = None
    error = parsed.get("error") if isinstance(parsed, Mapping) else parsed
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


def summarize(records: list[Mapping[str, Any]], *, live: bool) -> dict[str, Any]:
    by_stage: dict[str, dict[str, Any]] = {}
    for stage in PROMPT_VERSIONS:
        rows = [row for row in records if text(row.get("stage")) == stage]
        latencies = [float(row.get("elapsed_seconds") or 0) for row in rows if float(row.get("elapsed_seconds") or 0) > 0]
        usages = [row.get("usage") or {} for row in rows]
        by_stage[stage] = {
            "records": len(rows),
            "parsed": sum(row.get("classification") == "parsed" for row in rows),
            "cache_hits": sum(row.get("classification") == "cache_hit" for row in rows),
            "offline_cache_misses": sum(row.get("classification") == "offline_cache_miss" for row in rows),
            "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in rows),
            "invalid_payloads": sum(row.get("classification") == "response_parse_failure" for row in rows),
            "truncations": sum(row.get("classification") == "response_truncated" for row in rows),
            "http_400_failures": sum(row.get("http_status") == 400 for row in rows),
            "retries": sum(int(row.get("attempt") or 1) > 1 for row in rows),
            "prompt_tokens": sum(int(item.get("prompt_tokens") or 0) for item in usages),
            "completion_tokens": sum(int(item.get("completion_tokens") or 0) for item in usages),
            "total_tokens": sum(int(item.get("total_tokens") or 0) for item in usages),
            "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0,
            "max_latency_seconds": round(max(latencies), 3) if latencies else 0,
        }
    latencies = [float(row.get("elapsed_seconds") or 0) for row in records if float(row.get("elapsed_seconds") or 0) > 0]
    usages = [row.get("usage") or {} for row in records]
    non_live = {"cache_hit", "offline_cache_miss", "provider_attempt_budget_exhausted"}
    return {
        "schema": "sfh2-a1r-transport-v1",
        "model": MODEL,
        "pilot_version": PILOT_VERSION,
        "prompt_versions": dict(PROMPT_VERSIONS),
        "calls": len(records),
        "parsed_calls": sum(row.get("classification") == "parsed" for row in records),
        "cache_hits": sum(row.get("classification") == "cache_hit" for row in records),
        "offline_cache_misses": sum(row.get("classification") == "offline_cache_miss" for row in records),
        "new_live_attempts": sum(row.get("classification") not in non_live for row in records) if live else 0,
        "retries": sum(int(row.get("attempt") or 1) > 1 for row in records),
        "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in records),
        "http_400_failures": sum(row.get("http_status") == 400 for row in records),
        "invalid_payloads": sum(row.get("classification") == "response_parse_failure" for row in records),
        "truncations": sum(row.get("classification") == "response_truncated" for row in records),
        "prompt_tokens": sum(int(item.get("prompt_tokens") or 0) for item in usages),
        "completion_tokens": sum(int(item.get("completion_tokens") or 0) for item in usages),
        "total_tokens": sum(int(item.get("total_tokens") or 0) for item in usages),
        "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0,
        "max_latency_seconds": round(max(latencies), 3) if latencies else 0,
        "by_stage": by_stage,
    }


class ReviewClient:
    """Use only exact cache hits or bounded live review calls."""

    def __init__(self, run_dir: Path, *, live: bool) -> None:
        self.run_dir = run_dir
        self.raw_dir = run_dir / "raw-api"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.live = live
        self.cache_path = OUT / "cache-index.json"
        self.cache = read_json(self.cache_path, {}) or {}
        stored = read_json(run_dir / "transport.json", []) or []
        self.records: list[dict[str, Any]] = stored if isinstance(stored, list) else []
        self.sequence = max((int(path.name.split("-", 1)[0]) for path in self.raw_dir.glob("*.json") if path.name.split("-", 1)[0].isdigit()), default=0)
        self.live_attempts = sum(row.get("classification") not in {"cache_hit", "offline_cache_miss", "provider_attempt_budget_exhausted"} for row in self.records)

    def call(self, *, stage: str, unit_id: str, system: str, payload: Mapping[str, Any], tool: Mapping[str, Any], max_tokens: int) -> Mapping[str, Any] | None:
        from smoke_deepseek import call_deepseek

        schema_errors = validate_deepseek_strict_schema(tool["function"]["parameters"])
        if schema_errors:
            raise ValueError("invalid_deepseek_strict_schema:" + ";".join(schema_errors))
        function_name = FUNCTION_NAMES[stage]
        packet_hash = stable_hash({"pilot_version": PILOT_VERSION, "stage": stage, "prompt_version": PROMPT_VERSIONS[stage], "model": MODEL, "system": system, "payload": payload, "tool": tool})
        cached = self.cache.get(packet_hash)
        if isinstance(cached, Mapping):
            path = ROOT / text(cached.get("raw_path"))
            if path.is_file():
                response = read_json(path, {}) or {}
                extracted, error = extract(response, function_name)
                if extracted is not None and error is None:
                    # A deterministic rebuild of an already completed live
                    # run must not append a second accounting row for the
                    # same packet.  New run directories still receive an
                    # explicit cache-hit row below.
                    if any(
                        text(row.get("packet_hash")) == packet_hash
                        for row in self.records
                        if isinstance(row, Mapping)
                    ):
                        return extracted
                    self.records.append({"stage": stage, "unit_id": unit_id, "packet_hash": packet_hash, "prompt_version": PROMPT_VERSIONS[stage], "classification": "cache_hit", "raw_path": str(path.relative_to(ROOT)), "usage": {}, "elapsed_seconds": 0})
                    return extracted
        if not self.live:
            self.records.append({"stage": stage, "unit_id": unit_id, "packet_hash": packet_hash, "prompt_version": PROMPT_VERSIONS[stage], "classification": "offline_cache_miss", "usage": {}, "elapsed_seconds": 0})
            return None
        for attempt in (1, 2):
            if self.live_attempts >= MAX_PROVIDER_ATTEMPTS:
                self.records.append({"stage": stage, "unit_id": unit_id, "packet_hash": packet_hash, "classification": "provider_attempt_budget_exhausted", "usage": {}, "elapsed_seconds": 0, "budget": MAX_PROVIDER_ATTEMPTS})
                return None
            self.live_attempts += 1
            self.sequence += 1
            sequence = self.sequence
            started = time.monotonic()
            row: dict[str, Any] = {"sequence": sequence, "attempt": attempt, "stage": stage, "unit_id": unit_id, "packet_hash": packet_hash, "prompt_version": PROMPT_VERSIONS[stage], "model": MODEL, "temperature": 0, "thinking": {"type": "disabled"}, "start_time": _now()}
            try:
                response = call_deepseek(
                    [{"role": "system", "content": system}, {"role": "user", "content": canonical_json(payload)}],
                    model=MODEL, temperature=0, thinking={"type": "disabled"}, max_tokens=max_tokens,
                    timeout=180, endpoint=STRICT_ENDPOINT, tools=[dict(tool)],
                    tool_choice={"type": "function", "function": {"name": function_name}},
                )
                raw_path = self.raw_dir / f"{sequence:05d}-{_slug(stage)}-{_slug(unit_id)}-attempt{attempt}.json"
                write_json(raw_path, response)
                finish = _finish(response)
                row.update({"raw_path": str(raw_path.relative_to(ROOT)), "usage": _usage(response), "finish_reason": finish})
                if finish == "length":
                    row.update({"classification": "response_truncated", "elapsed_seconds": round(time.monotonic() - started, 3), "end_time": _now()})
                    self.records.append(row)
                    if attempt == 1:
                        continue
                    return None
                extracted, error = extract(response, function_name)
                if extracted is None or error:
                    row.update({"classification": "response_parse_failure", "parse_error": error, "elapsed_seconds": round(time.monotonic() - started, 3), "end_time": _now()})
                    self.records.append(row)
                    return None
                row.update({"classification": "parsed", "elapsed_seconds": round(time.monotonic() - started, 3), "end_time": _now()})
                self.records.append(row)
                self.cache[packet_hash] = {"raw_path": str(raw_path.relative_to(ROOT)), "stage": stage, "unit_id": unit_id, "prompt_version": PROMPT_VERSIONS[stage], "model": MODEL}
                write_json(self.cache_path, self.cache)
                return extracted
            except Exception as exc:
                message = str(exc)
                secret = os.environ.get("DEEPSEEK_API_KEY")
                if secret:
                    message = message.replace(secret, "[REDACTED]")
                error = _provider_error(exc)
                row.update({"classification": "provider_request_failure", "exception_class": type(exc).__name__, "exception_message": message[:1200], **error, "retryable": is_retryable(exc), "elapsed_seconds": round(time.monotonic() - started, 3), "end_time": _now()})
                self.records.append(row)
                if not is_retryable(exc):
                    return None
        return None

    def save(self) -> None:
        write_json(self.run_dir / "transport.json", self.records)

    def metrics(self) -> dict[str, Any]:
        return summarize(self.records, live=self.live)
