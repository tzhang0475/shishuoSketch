"""Bounded cache-first transport for the independent A2 semantic pass."""

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
    body = body[:4000]
    result: dict[str, Any] = {"http_status": getattr(exc, "http_status", None), "provider_error_body": body}
    try:
        decoded = json.loads(body) if body else None
    except (TypeError, ValueError):
        decoded = None
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


def summarize(records: list[Mapping[str, Any]], *, live: bool) -> dict[str, Any]:
    stages = ("historian_b", "adjudicator")
    def parse_failure(row: Mapping[str, Any]) -> bool:
        return row.get("classification") == "response_parse_failure" or (
            row.get("classification") == "raw_cache_replay" and bool(row.get("parse_error"))
        )

    by_stage: dict[str, dict[str, Any]] = {}
    for stage in stages:
        rows = [row for row in records if text(row.get("stage")) == stage]
        latencies = [float(row.get("elapsed_seconds") or 0) for row in rows if float(row.get("elapsed_seconds") or 0) > 0]
        usages = [row.get("usage") or {} for row in rows]
        by_stage[stage] = {
            "calls": len(rows),
            "parsed": sum(row.get("classification") == "parsed" for row in rows),
            "cache_hits": sum(row.get("classification") == "cache_hit" for row in rows),
            "raw_cache_replays": sum(row.get("classification") == "raw_cache_replay" for row in rows),
            "offline_cache_misses": sum(row.get("classification") == "offline_cache_miss" for row in rows),
            "provider_attempt_budget_exhausted": sum(row.get("classification") == "provider_attempt_budget_exhausted" for row in rows),
            "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in rows),
            "invalid_payloads": sum(parse_failure(row) for row in rows),
            "retries": sum(int(row.get("attempt") or 1) > 1 for row in rows),
            "http_400_failures": sum(row.get("http_status") == 400 for row in rows),
            "prompt_tokens": sum(int(item.get("prompt_tokens") or 0) for item in usages),
            "completion_tokens": sum(int(item.get("completion_tokens") or 0) for item in usages),
            "total_tokens": sum(int(item.get("total_tokens") or 0) for item in usages),
            "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0,
            "max_latency_seconds": round(max(latencies), 3) if latencies else 0,
        }
    non_live = {"cache_hit", "raw_cache_replay", "offline_cache_miss", "provider_attempt_budget_exhausted"}
    latencies = [float(row.get("elapsed_seconds") or 0) for row in records if float(row.get("elapsed_seconds") or 0) > 0]
    usages = [row.get("usage") or {} for row in records]
    return {
        "schema": "sfh2-a2-transport-v1",
        "model": MODEL,
        "pilot_version": PILOT_VERSION,
        "prompt_versions": dict(PROMPT_VERSIONS),
        "calls": len(records),
        "parsed_calls": sum(row.get("classification") == "parsed" for row in records),
        "cache_hits": sum(row.get("classification") == "cache_hit" for row in records),
        "raw_cache_replays": sum(row.get("classification") == "raw_cache_replay" for row in records),
        "offline_cache_misses": sum(row.get("classification") == "offline_cache_miss" for row in records),
        "provider_attempt_budget_exhausted": sum(row.get("classification") == "provider_attempt_budget_exhausted" for row in records),
        "new_live_attempts": sum(row.get("classification") not in non_live for row in records) if live else 0,
        "retries": sum(int(row.get("attempt") or 1) > 1 for row in records),
        "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in records),
        "http_400_failures": sum(row.get("http_status") == 400 for row in records),
        "invalid_payloads": sum(parse_failure(row) for row in records),
        "prompt_tokens": sum(int(item.get("prompt_tokens") or 0) for item in usages),
        "completion_tokens": sum(int(item.get("completion_tokens") or 0) for item in usages),
        "total_tokens": sum(int(item.get("total_tokens") or 0) for item in usages),
        "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0,
        "max_latency_seconds": round(max(latencies), 3) if latencies else 0,
        "by_stage": by_stage,
    }


class A2Client:
    """Cache-first B/adjudicator transport with a hard attempt budget."""

    @staticmethod
    def _coalesce_replay_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove duplicate non-live resume rows for one logical request.

        A resumed process may first replay an orphaned raw witness and later
        discover the same witness through the cache index.  Both are the same
        deterministic result, not two transport calls.  Provider attempts
        and their retry records are retained; only non-live bookkeeping rows
        are coalesced by stage/unit.
        """

        non_live = {"cache_hit", "raw_cache_replay", "offline_cache_miss", "provider_attempt_budget_exhausted"}
        latest: dict[tuple[str, str], int] = {}
        for index, row in enumerate(rows):
            if row.get("classification") in non_live:
                latest[(text(row.get("stage")), text(row.get("unit_id")))] = index
        return [
            row for index, row in enumerate(rows)
            if row.get("classification") not in non_live
            or latest.get((text(row.get("stage")), text(row.get("unit_id")))) == index
        ]

    def __init__(self, run_dir: Path, *, live: bool) -> None:
        self.run_dir = run_dir
        self.raw_dir = run_dir / "raw-api"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.live = live
        self.cache_path = OUT / "cache-index.json"
        self.cache = read_json(self.cache_path, {}) or {}
        # Keep the machine-readable summary at ``transport.json``.  The
        # per-request log uses a separate name so writing it cannot replace
        # the deterministic replay summary that validators compare.
        stored = read_json(run_dir / "transport-log.json", None)
        if stored is None:
            # Compatibility with the interrupted first run, whose log was
            # written under the old name before the split was introduced.
            stored = read_json(run_dir / "transport.json", []) or []
        self.records: list[dict[str, Any]] = self._coalesce_replay_rows(stored if isinstance(stored, list) else [])
        self.sequence = max((int(path.name.split("-", 1)[0]) for path in self.raw_dir.glob("*.json") if path.name.split("-", 1)[0].isdigit()), default=0)
        # Raw response files are durable attempt witnesses.  Counting them is
        # important when a process is interrupted after the provider response
        # is written but before transport.json is flushed: a resumed run must
        # not exceed the original hard budget or repeat an invalid response.
        self.raw_attempts_before_resume = len(list(self.raw_dir.glob("*.json")))
        recorded_attempts = sum(row.get("classification") not in {"cache_hit", "raw_cache_replay", "offline_cache_miss", "provider_attempt_budget_exhausted"} for row in self.records)
        self.live_attempts = max(recorded_attempts, self.raw_attempts_before_resume)

    def _record_for(self, packet_hash: str, stage: str, unit_id: str) -> dict[str, Any] | None:
        rows = [row for row in self.records if row.get("packet_hash") == packet_hash and row.get("stage") == stage and row.get("unit_id") == unit_id]
        return dict(rows[-1]) if rows else None

    def call(self, *, stage: str, unit_id: str, system: str, payload: Mapping[str, Any], tool: Mapping[str, Any], max_tokens: int) -> Mapping[str, Any] | None:
        from smoke_deepseek import call_deepseek

        schema_errors = validate_deepseek_strict_schema(tool["function"]["parameters"])
        if schema_errors:
            raise ValueError("invalid_deepseek_strict_schema:" + ";".join(schema_errors))
        function_name = FUNCTION_NAMES[stage]
        packet_hash = stable_hash({
            "pilot_version": PILOT_VERSION,
            "stage": stage,
            "prompt_version": PROMPT_VERSIONS[stage],
            "model": MODEL,
            "adjudicator_model": os.environ.get("SFH2_ADJUDICATOR_MODEL") or MODEL,
            "system": system,
            "payload": payload,
            "tool": tool,
        })
        cached = self.cache.get(packet_hash)
        if isinstance(cached, Mapping):
            path = ROOT / text(cached.get("raw_path"))
            if path.is_file():
                response = read_json(path, {}) or {}
                extracted, error = extract(response, function_name)
                if extracted is not None and error is None:
                    if not any(row.get("packet_hash") == packet_hash for row in self.records):
                        self.records.append({"stage": stage, "unit_id": unit_id, "packet_hash": packet_hash, "prompt_version": PROMPT_VERSIONS[stage], "classification": "cache_hit", "raw_path": str(path.relative_to(ROOT)), "usage": {}, "elapsed_seconds": 0})
                    return extracted
                # Invalid provider tool arguments are still durable evidence.
                # Replaying them must not fall through to a live request (or
                # an offline miss), otherwise a replay could change the
                # semantic/contract outcome and silently consume another
                # attempt.  The cache entry is deliberately marked so this
                # branch remains structural transport handling only.
                if not any(
                    row.get("packet_hash") == packet_hash
                    and row.get("stage") == stage
                    and row.get("unit_id") == unit_id
                    for row in self.records
                ):
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
                return None
        # A prior process may have durably written a provider response but
        # been interrupted before it could update the cache index or
        # transport log.  Reuse that response, including a structurally
        # invalid one, rather than issuing a duplicate semantic call.
        raw_candidates = sorted(self.raw_dir.glob(f"*-{_slug(stage)}-{_slug(unit_id)}-attempt*.json"))
        if raw_candidates:
            path = raw_candidates[-1]
            response = read_json(path, {}) or {}
            extracted, error = extract(response, function_name)
            if not any(
                row.get("packet_hash") == packet_hash
                and row.get("stage") == stage
                and row.get("unit_id") == unit_id
                for row in self.records
            ):
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
            # Cache both successful and invalid raw witnesses.  A malformed
            # tool payload is a deterministic provider-contract result and
            # must be reproducible offline without another request.
            self.cache[packet_hash] = {
                "raw_path": str(path.relative_to(ROOT)),
                "stage": stage,
                "unit_id": unit_id,
                "prompt_version": PROMPT_VERSIONS[stage],
                "model": MODEL if stage == "historian_b" else (os.environ.get("SFH2_ADJUDICATOR_MODEL") or MODEL),
                "response_status": "valid" if extracted is not None and error is None else "invalid",
                "parse_error": error,
            }
            if self.live:
                write_json(self.cache_path, self.cache)
            return extracted
        if not self.live:
            self.records.append({"stage": stage, "unit_id": unit_id, "packet_hash": packet_hash, "prompt_version": PROMPT_VERSIONS[stage], "classification": "offline_cache_miss", "usage": {}, "elapsed_seconds": 0})
            return None
        for attempt in (1, 2):
            if self.live_attempts >= MAX_PROVIDER_ATTEMPTS:
                if not any(
                    row.get("packet_hash") == packet_hash
                    and row.get("stage") == stage
                    and row.get("unit_id") == unit_id
                    and row.get("classification") == "provider_attempt_budget_exhausted"
                    for row in self.records
                ):
                    self.records.append({"stage": stage, "unit_id": unit_id, "packet_hash": packet_hash, "classification": "provider_attempt_budget_exhausted", "usage": {}, "elapsed_seconds": 0, "budget": MAX_PROVIDER_ATTEMPTS})
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
                "model": os.environ.get("SFH2_ADJUDICATOR_MODEL") if stage == "adjudicator" else MODEL,
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
                    return None
                row.update({"classification": "parsed", "elapsed_seconds": round(time.monotonic() - started, 3), "end_time": _now()})
                self.records.append(row)
                self.cache[packet_hash] = {"raw_path": str(raw_path.relative_to(ROOT)), "stage": stage, "unit_id": unit_id, "prompt_version": PROMPT_VERSIONS[stage], "model": row["model"]}
                write_json(self.cache_path, self.cache)
                return extracted
            except Exception as exc:
                message = str(exc)
                secret = os.environ.get("DEEPSEEK_API_KEY")
                if secret:
                    message = message.replace(secret, "[REDACTED]")
                row.update({"classification": "provider_request_failure", "exception_class": type(exc).__name__, "exception_message": message[:1200], **_error_details(exc), "retryable": is_retryable(exc), "elapsed_seconds": round(time.monotonic() - started, 3), "end_time": _now()})
                self.records.append(row)
                if not is_retryable(exc):
                    return None
        return None

    def save(self) -> None:
        write_json(self.run_dir / "transport-log.json", self.records)

    def latest_transport(self, *, stage: str, unit_id: str) -> dict[str, Any] | None:
        rows = [row for row in self.records if row.get("stage") == stage and row.get("unit_id") == unit_id]
        return dict(rows[-1]) if rows else None

    def metrics(self) -> dict[str, Any]:
        result = summarize(self.records, live=self.live)
        result["raw_provider_attempts_in_run"] = len(list(self.raw_dir.glob("*.json")))
        result["raw_attempts_before_resume"] = self.raw_attempts_before_resume
        if self.live:
            # The raw directory is the complete durable count, including
            # attempts made before an interrupted/resumed process.
            result["new_live_attempts"] = result["raw_provider_attempts_in_run"]
        return result
