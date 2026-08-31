"""Bounded transport and one-shot connectivity preflight for A0R-L."""

from __future__ import annotations

import datetime as dt
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


def classify_preflight_failure(exc: BaseException) -> str:
    """Classify the probe without interpreting a historical result."""

    message = str(exc).lower()
    environmental = (
        "operation not permitted",
        "network is unreachable",
        "network unreachable",
        "socket",
        "dns",
        "name or service not known",
        "temporary failure in name resolution",
        "connection refused",
        "connection reset",
        "timed out",
        "timeout",
        "sandbox",
    )
    if any(token in message for token in environmental):
        return "environmental_network_failure"
    if "api key" in message or "authentication" in message or "401" in message or "403" in message:
        return "provider_authentication_failure"
    return "provider_preflight_failure"


def run_connectivity_probe(run_id: str = "a0r-l-connectivity-probe") -> dict[str, Any]:
    """Make exactly one minimal provider request; never retry it."""

    from smoke_deepseek import call_deepseek

    preflight_path = OUT / "provider-preflight.json"
    if preflight_path.is_file():
        raise RuntimeError("sfh2_a0r_l_provider_probe_already_recorded")
    run_dir = OUT / "live" / run_id
    raw_dir = run_dir / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    result: dict[str, Any] = {
        "schema": "sfh2-a0r-l-provider-preflight-v1",
        "pilot": "SFH2.2-A0R-L",
        "run_id": run_id,
        "attempts": 1,
        "model": MODEL,
        "temperature": 0,
        "thinking": {"type": "disabled"},
        "endpoint": STRICT_ENDPOINT,
        "request": "minimal_reply_only_probe",
        "live_provider_available": False,
        "stop_live_phase_on_failure": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    try:
        response = call_deepseek(
            [{"role": "user", "content": "Reply only with OK"}],
            model=MODEL,
            temperature=0,
            thinking={"type": "disabled"},
            max_tokens=8,
            timeout=20,
            endpoint=STRICT_ENDPOINT,
            tools=[],
        )
        raw_path = raw_dir / "00001-connectivity-probe.json"
        write_json(raw_path, response)
        result.update({
            "live_provider_available": True,
            "response_received": True,
            "raw_path": str(raw_path.relative_to(ROOT)),
            "finish_reason": _finish(response),
            "usage": _usage(response),
        })
    except Exception as exc:
        message = str(exc)
        secret = os.environ.get("DEEPSEEK_API_KEY")
        if secret:
            message = message.replace(secret, "[REDACTED]")
        result.update({
            "response_received": False,
            "failure_class": classify_preflight_failure(exc),
            "exception_class": type(exc).__name__,
            "exception_message": message[:1200],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        })
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    write_json(preflight_path, result)
    return result


def summarize_transport_records(rows: list[Mapping[str, Any]], *, live: bool) -> dict[str, Any]:
    by_stage: dict[str, dict[str, Any]] = {}
    for stage in PROMPT_VERSIONS:
        stage_rows = [row for row in rows if text(row.get("stage")) == stage]
        usages = [row.get("usage") or {} for row in stage_rows]
        latencies = [float(row.get("elapsed_seconds") or 0) for row in stage_rows if float(row.get("elapsed_seconds") or 0) > 0]
        by_stage[stage] = {
            "records": len(stage_rows),
            "parsed": sum(row.get("classification") == "parsed" for row in stage_rows),
            "cache_hits": sum(row.get("classification") == "cache_hit" for row in stage_rows),
            "offline_cache_misses": sum(row.get("classification") == "offline_cache_miss" for row in stage_rows),
            "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in stage_rows),
            "invalid_payloads": sum(row.get("classification") == "response_parse_failure" for row in stage_rows),
            "truncations": sum(row.get("classification") == "response_truncated" for row in stage_rows),
            "budget_exhausted": sum(row.get("classification") == "provider_attempt_budget_exhausted" for row in stage_rows),
            "retries": sum(int(row.get("attempt") or 1) > 1 for row in stage_rows),
            "prompt_tokens": sum(int(item.get("prompt_tokens") or 0) for item in usages),
            "completion_tokens": sum(int(item.get("completion_tokens") or 0) for item in usages),
            "total_tokens": sum(int(item.get("total_tokens") or 0) for item in usages),
            "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0,
            "max_latency_seconds": round(max(latencies), 3) if latencies else 0,
        }
    usages = [row.get("usage") or {} for row in rows]
    latencies = [float(row.get("elapsed_seconds") or 0) for row in rows if float(row.get("elapsed_seconds") or 0) > 0]
    non_live = {"cache_hit", "offline_cache_miss", "provider_attempt_budget_exhausted"}
    return {
        "schema": "sfh2-a0r-l-transport-v1",
        "model": MODEL,
        "pilot_version": PILOT_VERSION,
        "prompt_versions": dict(PROMPT_VERSIONS),
        "calls": len(rows),
        "parsed_calls": sum(row.get("classification") == "parsed" for row in rows),
        "cache_hits": sum(row.get("classification") == "cache_hit" for row in rows),
        "offline_cache_misses": sum(row.get("classification") == "offline_cache_miss" for row in rows),
        "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in rows),
        "invalid_payloads": sum(row.get("classification") == "response_parse_failure" for row in rows),
        "truncations": sum(row.get("classification") == "response_truncated" for row in rows),
        "budget_exhausted": sum(row.get("classification") == "provider_attempt_budget_exhausted" for row in rows),
        "new_live_attempts": sum(row.get("classification") not in non_live for row in rows) if live else 0,
        "retries": sum(int(row.get("attempt") or 1) > 1 for row in rows),
        "prompt_tokens": sum(int(item.get("prompt_tokens") or 0) for item in usages),
        "completion_tokens": sum(int(item.get("completion_tokens") or 0) for item in usages),
        "total_tokens": sum(int(item.get("total_tokens") or 0) for item in usages),
        "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0,
        "max_latency_seconds": round(max(latencies), 3) if latencies else 0,
        "by_stage": by_stage,
    }


class PilotClient:
    """Cache-first semantic transport with at most one retry per call."""

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

    def _extract(self, response: Mapping[str, Any], function_name: str) -> tuple[Mapping[str, Any] | None, str | None]:
        import hng2_schema_controller as controller
        payload, _, error = controller.extract_strict_tool_payload(response, expected_function_name=function_name)
        return payload, error

    def _record(self, row: Mapping[str, Any]) -> None:
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
                        "stage": stage, "unit_id": unit_id, "packet_hash": packet_hash,
                        "prompt_version": PROMPT_VERSIONS[stage], "classification": "cache_hit",
                        "raw_path": str(path.relative_to(ROOT)), "usage": {}, "elapsed_seconds": 0,
                    })
                    return extracted
        if not self.live:
            self._record({
                "stage": stage, "unit_id": unit_id, "packet_hash": packet_hash,
                "prompt_version": PROMPT_VERSIONS[stage], "classification": "offline_cache_miss",
                "usage": {}, "elapsed_seconds": 0,
            })
            return None
        for attempt in (1, 2):
            if self.live_attempts >= MAX_PROVIDER_ATTEMPTS:
                self._record({
                    "stage": stage, "unit_id": unit_id, "packet_hash": packet_hash,
                    "classification": "provider_attempt_budget_exhausted", "usage": {},
                    "elapsed_seconds": 0, "budget": MAX_PROVIDER_ATTEMPTS,
                })
                return None
            self.live_attempts += 1
            self.sequence += 1
            sequence = self.sequence
            started = time.monotonic()
            row: dict[str, Any] = {
                "sequence": sequence, "attempt": attempt, "stage": stage, "unit_id": unit_id,
                "packet_hash": packet_hash, "prompt_version": PROMPT_VERSIONS[stage], "model": MODEL,
                "temperature": 0, "thinking": {"type": "disabled"}, "start_time": _now(),
            }
            try:
                response = call_deepseek(
                    [{"role": "system", "content": system}, {"role": "user", "content": canonical_json(payload)}],
                    model=MODEL, temperature=0, thinking={"type": "disabled"}, max_tokens=max_tokens,
                    timeout=180, endpoint=STRICT_ENDPOINT, tools=[dict(tool)],
                    tool_choice={"type": "function", "function": {"name": function_name}},
                )
                raw_path = self.raw_dir / f"{sequence:05d}-{_slug(stage)}-{_slug(unit_id)}-attempt{attempt}.json"
                if raw_path.exists():
                    raise RuntimeError("a0r_l_raw_response_path_collision")
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
                    "raw_path": str(raw_path.relative_to(ROOT)), "stage": stage, "unit_id": unit_id,
                    "prompt_version": PROMPT_VERSIONS[stage], "model": MODEL,
                }
                write_json(self.cache_path, self.cache)
                return extracted
            except Exception as exc:
                message = str(exc)
                secret = os.environ.get("DEEPSEEK_API_KEY")
                if secret:
                    message = message.replace(secret, "[REDACTED]")
                row.update({
                    "classification": "provider_request_failure", "exception_class": type(exc).__name__,
                    "exception_message": message[:1200], "http_status": getattr(exc, "http_status", None),
                    "usage": row.get("usage", {}), "elapsed_seconds": round(time.monotonic() - started, 3), "end_time": _now(),
                })
                self._record(row)
        return None

    def save(self) -> None:
        write_json(self.run_dir / "transport.json", self.records)

    def metrics(self) -> dict[str, Any]:
        return summarize_transport_records(self.records, live=self.live)
