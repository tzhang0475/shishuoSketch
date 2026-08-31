"""Bounded, cache-first transport for the isolated A0R live regression."""

from __future__ import annotations

import datetime as dt
import os
import re
import statistics
import threading
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


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", text(value)).strip("-") or "unit"


def _usage(response: Mapping[str, Any]) -> dict[str, int]:
    usage = response.get("usage") if isinstance(response.get("usage"), Mapping) else {}
    return {
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }


def _finish(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        return text(choices[0].get("finish_reason"))
    return ""


def summarize_transport_records(records: list[Mapping[str, Any]], *, live: bool) -> dict[str, Any]:
    by_stage: dict[str, dict[str, Any]] = {}
    for stage in PROMPT_VERSIONS:
        rows = [row for row in records if text(row.get("stage")) == stage]
        usages = [row.get("usage") or {} for row in rows]
        latencies = [float(row.get("elapsed_seconds") or 0) for row in rows if float(row.get("elapsed_seconds") or 0) > 0]
        by_stage[stage] = {
            "calls": len(rows),
            "parsed": sum(row.get("classification") == "parsed" for row in rows),
            "cache_hits": sum(row.get("classification") == "cache_hit" for row in rows),
            "offline_cache_misses": sum(row.get("classification") == "offline_cache_miss" for row in rows),
            "compatibility_replays": sum(row.get("classification") == "legacy_a0_compatibility_replay" for row in rows),
            "retries": sum(int(row.get("attempt") or 1) > 1 for row in rows),
            "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in rows),
            "invalid_payloads": sum(row.get("classification") == "response_parse_failure" for row in rows),
            "truncations": sum(row.get("classification") == "response_truncated" for row in rows),
            "prompt_tokens": sum(int(item.get("prompt_tokens") or 0) for item in usages),
            "completion_tokens": sum(int(item.get("completion_tokens") or 0) for item in usages),
            "total_tokens": sum(int(item.get("total_tokens") or 0) for item in usages),
            "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0,
            "max_latency_seconds": round(max(latencies), 3) if latencies else 0,
        }
    usages = [row.get("usage") or {} for row in records]
    latencies = [float(row.get("elapsed_seconds") or 0) for row in records if float(row.get("elapsed_seconds") or 0) > 0]
    non_live = {"cache_hit", "offline_cache_miss", "legacy_a0_compatibility_replay", "provider_attempt_budget_exhausted"}
    return {
        "schema": "sfh2-a0r-transport-v1",
        "model": MODEL,
        "pilot_version": PILOT_VERSION,
        "prompt_versions": dict(PROMPT_VERSIONS),
        "calls": len(records),
        "parsed_calls": sum(row.get("classification") == "parsed" for row in records),
        "cache_hits": sum(row.get("classification") == "cache_hit" for row in records),
        "offline_cache_misses": sum(row.get("classification") == "offline_cache_miss" for row in records),
        "compatibility_replays": sum(row.get("classification") == "legacy_a0_compatibility_replay" for row in records),
        "new_live_attempts": sum(row.get("classification") not in non_live for row in records) if live else 0,
        "retries": sum(int(row.get("attempt") or 1) > 1 for row in records),
        "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in records),
        "invalid_payloads": sum(row.get("classification") == "response_parse_failure" for row in records),
        "truncations": sum(row.get("classification") == "response_truncated" for row in records),
        "prompt_tokens": sum(int(item.get("prompt_tokens") or 0) for item in usages),
        "completion_tokens": sum(int(item.get("completion_tokens") or 0) for item in usages),
        "total_tokens": sum(int(item.get("total_tokens") or 0) for item in usages),
        "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0,
        "max_latency_seconds": round(max(latencies), 3) if latencies else 0,
        "by_stage": by_stage,
    }


class PilotClient:
    """Use exact cached responses first and enforce the A0R attempt budget."""

    def __init__(self, run_dir: Path, *, live: bool) -> None:
        self.run_dir = run_dir
        self.raw_dir = run_dir / "raw-api"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.live = live
        self.lock = threading.RLock()
        self.cache_path = OUT / "cache-index.json"
        self.cache = read_json(self.cache_path, {}) or {}
        stored = read_json(run_dir / "transport.json", []) or []
        self.records: list[dict[str, Any]] = stored if isinstance(stored, list) else []
        self.sequence = max((int(path.name.split("-", 1)[0]) for path in self.raw_dir.glob("*.json") if path.name.split("-", 1)[0].isdigit()), default=0)
        self.live_attempts = sum(row.get("classification") not in {"cache_hit", "offline_cache_miss", "legacy_a0_compatibility_replay", "provider_attempt_budget_exhausted"} for row in self.records)

    def _extract(self, response: Mapping[str, Any], function_name: str) -> tuple[Mapping[str, Any] | None, str | None]:
        import hng2_schema_controller as controller
        payload, _, error = controller.extract_strict_tool_payload(response, expected_function_name=function_name)
        return payload, error

    def _record(self, row: Mapping[str, Any]) -> None:
        with self.lock:
            self.records.append(dict(row))

    def call(self, *, stage: str, unit_id: str, system: str, payload: Mapping[str, Any], tool: Mapping[str, Any], max_tokens: int) -> Mapping[str, Any] | None:
        from smoke_deepseek import call_deepseek

        function_name = FUNCTION_NAMES[stage]
        packet_hash = stable_hash({
            "pilot_version": PILOT_VERSION,
            "stage": stage,
            "prompt_version": PROMPT_VERSIONS[stage],
            "model": MODEL,
            "system": system,
            "payload": payload,
            "tool": tool,
        })
        cached = self.cache.get(packet_hash)
        if isinstance(cached, Mapping):
            path = ROOT / text(cached.get("raw_path"))
            if path.is_file():
                response = read_json(path, {}) or {}
                extracted, error = self._extract(response, function_name)
                if extracted is not None and error is None:
                    self._record({
                        "stage": stage,
                        "unit_id": unit_id,
                        "packet_hash": packet_hash,
                        "prompt_version": PROMPT_VERSIONS[stage],
                        "classification": "cache_hit",
                        "raw_path": str(path.relative_to(ROOT)),
                        "usage": {},
                        "elapsed_seconds": 0,
                    })
                    return extracted
        if not self.live:
            self._record({
                "stage": stage,
                "unit_id": unit_id,
                "packet_hash": packet_hash,
                "prompt_version": PROMPT_VERSIONS[stage],
                "classification": "offline_cache_miss",
                "usage": {},
                "elapsed_seconds": 0,
            })
            return None
        for attempt in (1, 2):
            with self.lock:
                if self.live_attempts >= MAX_PROVIDER_ATTEMPTS:
                    self._record({
                        "stage": stage,
                        "unit_id": unit_id,
                        "classification": "provider_attempt_budget_exhausted",
                        "usage": {},
                        "elapsed_seconds": 0,
                        "budget": MAX_PROVIDER_ATTEMPTS,
                    })
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
                "model": MODEL,
                "temperature": 0,
                "thinking": {"type": "disabled"},
                "start_time": _now(),
            }
            try:
                response = call_deepseek(
                    [{"role": "system", "content": system}, {"role": "user", "content": canonical_json(payload)}],
                    model=MODEL,
                    temperature=0,
                    thinking={"type": "disabled"},
                    max_tokens=max_tokens,
                    timeout=180,
                    endpoint=STRICT_ENDPOINT,
                    tools=[dict(tool)],
                    tool_choice={"type": "function", "function": {"name": function_name}},
                )
                raw_path = self.raw_dir / f"{sequence:05d}-{_slug(stage)}-{_slug(unit_id)}-attempt{attempt}.json"
                if raw_path.exists():
                    raise RuntimeError("a0r_raw_response_path_collision")
                write_json(raw_path, response)
                finish = _finish(response)
                row.update({"raw_path": str(raw_path.relative_to(ROOT)), "usage": _usage(response), "finish_reason": finish})
                if finish == "length":
                    row.update({"classification": "response_truncated", "elapsed_seconds": round(time.monotonic() - started, 3), "end_time": _now()})
                    self._record(row)
                    continue
                extracted, error = self._extract(response, function_name)
                if extracted is None or error:
                    row.update({"classification": "response_parse_failure", "parse_error": error, "elapsed_seconds": round(time.monotonic() - started, 3), "end_time": _now()})
                    self._record(row)
                    continue
                row.update({"classification": "parsed", "elapsed_seconds": round(time.monotonic() - started, 3), "end_time": _now()})
                self._record(row)
                self.cache[packet_hash] = {
                    "raw_path": str(raw_path.relative_to(ROOT)),
                    "stage": stage,
                    "unit_id": unit_id,
                    "prompt_version": PROMPT_VERSIONS[stage],
                    "model": MODEL,
                }
                write_json(self.cache_path, self.cache)
                return extracted
            except Exception as exc:
                message = str(exc)
                secret = os.environ.get("DEEPSEEK_API_KEY")
                if secret:
                    message = message.replace(secret, "[REDACTED]")
                row.update({
                    "classification": "provider_request_failure",
                    "exception_class": type(exc).__name__,
                    "exception_message": message[:1200],
                    "http_status": getattr(exc, "http_status", None),
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "end_time": _now(),
                })
                self._record(row)
        return None

    def save(self) -> None:
        write_json(self.run_dir / "transport.json", self.records)

    def metrics(self) -> dict[str, Any]:
        return summarize_transport_records(self.records, live=self.live)
