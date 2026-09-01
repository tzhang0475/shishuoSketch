"""Isolated A2R transport for four B recoveries and new adjudication calls."""

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
from .contracts import validate_deepseek_strict_schema


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
                key: "[REDACTED]" if any(token in str(key).lower() for token in ("secret", "token", "api_key", "authorization")) else scrub(child)
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


def extract(response: Mapping[str, Any], function_name: str) -> tuple[Mapping[str, Any] | None, str | None]:
    import hng2_schema_controller as controller
    payload, _, error = controller.extract_strict_tool_payload(response, expected_function_name=function_name)
    return payload, error


class A2RClient:
    """A new cache namespace; it never reads or writes the A2 cache."""

    def __init__(self, run_dir: Path, *, live: bool) -> None:
        self.run_dir = run_dir
        self.raw_dir = run_dir / "raw-api"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.live = live
        self.cache_path = OUT / "cache-index.json"
        self.cache = read_json(self.cache_path, {}) or {}
        stored = read_json(run_dir / "transport-log.json", []) or []
        self.records: list[dict[str, Any]] = list(stored) if isinstance(stored, list) else []
        self.sequence = max((int(path.name.split("-", 1)[0]) for path in self.raw_dir.glob("*.json") if path.name.split("-", 1)[0].isdigit()), default=0)
        self.live_attempts = len(list(self.raw_dir.glob("*.json")))

    def _cache_key(self, *, stage: str, system: str, payload: Mapping[str, Any], tool: Mapping[str, Any]) -> str:
        return stable_hash({
            "pilot_version": PILOT_VERSION,
            "stage": stage,
            "prompt_version": PROMPT_VERSIONS[stage],
            "model": os.environ.get("SFH2_ADJUDICATOR_MODEL") or MODEL if stage == "adjudicator" else MODEL,
            "system": system,
            "payload": payload,
            "tool": tool,
        })

    def _cached_response(self, packet_hash: str, function_name: str, stage: str, unit_id: str) -> Mapping[str, Any] | None:
        entry = self.cache.get(packet_hash)
        path = ROOT / text(entry.get("raw_path")) if isinstance(entry, Mapping) else None
        if path is None or not path.is_file():
            return None
        response = read_json(path, {}) or {}
        extracted, error = extract(response, function_name)
        self.records.append({
            "stage": stage,
            "unit_id": unit_id,
            "packet_hash": packet_hash,
            "prompt_version": PROMPT_VERSIONS[stage],
            "classification": "cache_hit" if extracted is not None and error is None else "raw_cache_replay",
            "raw_path": str(path.relative_to(ROOT)),
            "parse_error": error,
            "usage": {},
            "elapsed_seconds": 0,
        })
        return extracted

    def _raw_replay(self, packet_hash: str, function_name: str, stage: str, unit_id: str) -> tuple[bool, Mapping[str, Any] | None]:
        """Reuse a durable response that was written before cache indexing."""

        paths = sorted(self.raw_dir.glob(f"*-{_slug(stage)}-{_slug(unit_id)}-attempt*.json"))
        if not paths:
            return False, None
        path = paths[-1]
        response = read_json(path, {}) or {}
        extracted, error = extract(response, function_name)
        self.records.append({
            "stage": stage,
            "unit_id": unit_id,
            "packet_hash": packet_hash,
            "prompt_version": PROMPT_VERSIONS[stage],
            "classification": "raw_cache_replay",
            "raw_path": str(path.relative_to(ROOT)),
            "parse_error": error,
            "usage": {},
            "elapsed_seconds": 0,
        })
        self.cache[packet_hash] = {
            "raw_path": str(path.relative_to(ROOT)),
            "stage": stage,
            "unit_id": unit_id,
            "prompt_version": PROMPT_VERSIONS[stage],
            "model": os.environ.get("SFH2_ADJUDICATOR_MODEL") or MODEL if stage == "adjudicator" else MODEL,
            "response_status": "valid" if extracted is not None and error is None else "invalid",
            "parse_error": error,
        }
        if self.live:
            write_json(self.cache_path, self.cache)
        return True, extracted

    def call(self, *, stage: str, unit_id: str, system: str, payload: Mapping[str, Any], tool: Mapping[str, Any], max_tokens: int, cache_allowed: bool = True, retry_transient: bool = True) -> Mapping[str, Any] | None:
        from smoke_deepseek import call_deepseek

        schema_errors = validate_deepseek_strict_schema(tool["function"]["parameters"])
        if schema_errors:
            raise ValueError("invalid_deepseek_strict_schema:" + ";".join(schema_errors))
        function_name = FUNCTION_NAMES[stage]
        packet_hash = self._cache_key(stage=stage, system=system, payload=payload, tool=tool)
        if cache_allowed:
            entry = self.cache.get(packet_hash)
            if isinstance(entry, Mapping) and (ROOT / text(entry.get("raw_path"))).is_file():
                return self._cached_response(packet_hash, function_name, stage, unit_id)
            found, replay = self._raw_replay(packet_hash, function_name, stage, unit_id)
            if found:
                return replay
        if not self.live:
            self.records.append({"stage": stage, "unit_id": unit_id, "packet_hash": packet_hash, "prompt_version": PROMPT_VERSIONS[stage], "classification": "offline_cache_miss", "usage": {}, "elapsed_seconds": 0})
            return None

        attempts = (1, 2) if retry_transient else (1,)
        for attempt in attempts:
            if self.live_attempts >= MAX_PROVIDER_ATTEMPTS:
                self.records.append({"stage": stage, "unit_id": unit_id, "packet_hash": packet_hash, "classification": "provider_attempt_budget_exhausted", "usage": {}, "elapsed_seconds": 0})
                return None
            self.live_attempts += 1
            self.sequence += 1
            sequence = self.sequence
            started = time.monotonic()
            row: dict[str, Any] = {
                "sequence": sequence,
                "attempt": attempt,
                "stage": stage,
                "unit_id": unit_id,
                "packet_hash": packet_hash,
                "prompt_version": PROMPT_VERSIONS[stage],
                "model": os.environ.get("SFH2_ADJUDICATOR_MODEL") or MODEL if stage == "adjudicator" else MODEL,
                "temperature": 0,
                "thinking": {"type": "disabled"},
                "start_time": _now(),
            }
            try:
                response = call_deepseek(
                    [{"role": "system", "content": system}, {"role": "user", "content": canonical_json(payload)}],
                    model=(os.environ.get("SFH2_ADJUDICATOR_MODEL") or MODEL) if stage == "adjudicator" else MODEL,
                    temperature=0,
                    thinking={"type": "disabled"},
                    max_tokens=max_tokens,
                    timeout=180,
                    endpoint=STRICT_ENDPOINT,
                    tools=[dict(tool)],
                    tool_choice={"type": "function", "function": {"name": function_name}},
                )
                raw_path = self.raw_dir / f"{sequence:05d}-{_slug(stage)}-{_slug(unit_id)}-attempt{attempt}.json"
                write_json(raw_path, response)
                row.update({"raw_path": str(raw_path.relative_to(ROOT)), "usage": _usage(response), "finish_reason": _finish(response)})
                extracted, error = extract(response, function_name)
                if extracted is None or error:
                    row.update({"classification": "response_parse_failure", "parse_error": error, "elapsed_seconds": round(time.monotonic() - started, 3), "end_time": _now()})
                    self.records.append(row)
                    self.cache[packet_hash] = {
                        "raw_path": str(raw_path.relative_to(ROOT)),
                        "stage": stage,
                        "unit_id": unit_id,
                        "prompt_version": PROMPT_VERSIONS[stage],
                        "model": row["model"],
                        "response_status": "invalid",
                        "parse_error": error,
                    }
                    write_json(self.cache_path, self.cache)
                    return None
                row.update({"classification": "parsed", "elapsed_seconds": round(time.monotonic() - started, 3), "end_time": _now()})
                self.records.append(row)
                self.cache[packet_hash] = {"raw_path": str(raw_path.relative_to(ROOT)), "stage": stage, "unit_id": unit_id, "prompt_version": PROMPT_VERSIONS[stage], "model": row["model"], "response_status": "valid"}
                write_json(self.cache_path, self.cache)
                return extracted
            except Exception as exc:
                message = str(exc)
                secret = os.environ.get("DEEPSEEK_API_KEY")
                if secret:
                    message = message.replace(secret, "[REDACTED]")
                row.update({"classification": "provider_request_failure", "exception_class": type(exc).__name__, "exception_message": message[:1200], **_error_details(exc), "retryable": is_retryable(exc), "elapsed_seconds": round(time.monotonic() - started, 3), "end_time": _now()})
                self.records.append(row)
                if not retry_transient or not is_retryable(exc):
                    return None
        return None

    def save(self) -> None:
        # A rerun may append cache-hit bookkeeping to a log that already has
        # the durable provider attempt.  Keep provider attempt witnesses and
        # only the latest bookkeeping row for cache-only requests so the
        # accounting remains per logical request rather than per replay.
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in self.records:
            grouped.setdefault((text(row.get("stage")), text(row.get("unit_id"))), []).append(row)
        compact: list[dict[str, Any]] = []
        provider_classes = {"parsed", "response_parse_failure", "provider_request_failure"}
        for key in sorted(grouped):
            rows = grouped[key]
            provider_rows = [row for row in rows if row.get("classification") in provider_classes]
            compact.extend(provider_rows if provider_rows else [rows[-1]])
        self.records = compact
        write_json(self.run_dir / "transport-log.json", self.records)

    def latest(self, *, stage: str, unit_id: str) -> dict[str, Any] | None:
        rows = [row for row in self.records if row.get("stage") == stage and row.get("unit_id") == unit_id]
        return dict(rows[-1]) if rows else None

    def metrics(self) -> dict[str, Any]:
        stages = ("schema_probe", "historian_b_recovery", "adjudicator")
        by_stage: dict[str, Any] = {}
        for stage in stages:
            rows = [row for row in self.records if text(row.get("stage")) == stage]
            latencies = [float(row.get("elapsed_seconds") or 0) for row in rows if float(row.get("elapsed_seconds") or 0) > 0]
            usage = [row.get("usage") or {} for row in rows]
            by_stage[stage] = {
                "logical_calls": len(rows),
                "parsed": sum(row.get("classification") in {"parsed", "cache_hit"} for row in rows),
                "cache_hits": sum(row.get("classification") == "cache_hit" for row in rows),
                "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in rows),
                "invalid_payloads": sum(row.get("classification") == "response_parse_failure" for row in rows),
                "http_400_failures": sum(row.get("http_status") == 400 for row in rows),
                "retries": sum(int(row.get("attempt") or 1) > 1 for row in rows),
                "prompt_tokens": sum(int(item.get("prompt_tokens") or 0) for item in usage),
                "completion_tokens": sum(int(item.get("completion_tokens") or 0) for item in usage),
                "total_tokens": sum(int(item.get("total_tokens") or 0) for item in usage),
                "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0,
                "max_latency_seconds": round(max(latencies), 3) if latencies else 0,
            }
        all_usage = [row.get("usage") or {} for row in self.records]
        latencies = [float(row.get("elapsed_seconds") or 0) for row in self.records if float(row.get("elapsed_seconds") or 0) > 0]
        return {
            "schema": "sfh2-a2r-transport-v1",
            "pilot_version": PILOT_VERSION,
            "model": os.environ.get("SFH2_ADJUDICATOR_MODEL") or MODEL,
            "prompt_versions": dict(PROMPT_VERSIONS),
            "logical_calls": len(self.records),
            "new_live_attempts": self.live_attempts if self.live else 0,
            "parsed_calls": sum(row.get("classification") in {"parsed", "cache_hit"} for row in self.records),
            "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in self.records),
            "invalid_payloads": sum(row.get("classification") == "response_parse_failure" for row in self.records),
            "http_400_failures": sum(row.get("http_status") == 400 for row in self.records),
            "retries": sum(int(row.get("attempt") or 1) > 1 for row in self.records),
            "prompt_tokens": sum(int(item.get("prompt_tokens") or 0) for item in all_usage),
            "completion_tokens": sum(int(item.get("completion_tokens") or 0) for item in all_usage),
            "total_tokens": sum(int(item.get("total_tokens") or 0) for item in all_usage),
            "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0,
            "max_latency_seconds": round(max(latencies), 3) if latencies else 0,
            "by_stage": by_stage,
            "candidate_only": True,
            "canonical_write_back": False,
        }
