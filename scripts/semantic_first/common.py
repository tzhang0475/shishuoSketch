"""Shared deterministic utilities and strict provider transport for SFH1."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import statistics
import threading
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
OUT = ROOT / "data/generated/sfh1"
MODEL = "deepseek-v4-flash"
RUN_VERSION = "sfh1-semantic-first-v1"
STRICT_ENDPOINT = "https://api.deepseek.com/beta/chat/completions"
PROMPT_VERSIONS = {
    "mention_reading": "sfh1-l1-mention-reading-v2-null-offsets",
    "reference_semantics": "sfh1-l3-reference-semantics-v3-small-chunks",
    "identity_judgment": "sfh1-l5-identity-judgment-v2-chunked",
    "adversarial_review": "sfh1-l8-adversarial-review-v2-chunked",
    "temporal_semantics": "sfh1-temporal-semantics-v2-bounded",
}


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def text(value: Any) -> str:
    return str(value or "").strip()


def safe_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-") or "unit"


def usage(response: Mapping[str, Any]) -> dict[str, int]:
    row = response.get("usage") if isinstance(response.get("usage"), Mapping) else {}
    return {
        "prompt_tokens": int(row.get("prompt_tokens") or 0),
        "completion_tokens": int(row.get("completion_tokens") or 0),
        "total_tokens": int(row.get("total_tokens") or 0),
    }


def finish_reason(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
        return ""
    return text(choices[0].get("finish_reason"))


def safe_error(exc: Exception) -> dict[str, Any]:
    message = str(exc)
    secret = os.environ.get("DEEPSEEK_API_KEY")
    if secret:
        message = message.replace(secret, "[REDACTED]")
    return {
        "exception_class": type(exc).__name__,
        "exception_message": message[:1200],
        "http_status": getattr(exc, "http_status", None),
    }


class StrictStageClient:
    """Replayable strict-function transport with one identical safe retry."""

    def __init__(self, run_dir: Path, *, live: bool) -> None:
        self.run_dir = run_dir
        self.raw_dir = run_dir / "raw-api"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.live = live
        self._lock = threading.RLock()
        # A resumable run may already contain immutable raw responses.  Start
        # after the highest persisted sequence so a changed prompt/version can
        # never collide with or overwrite an earlier response filename.
        existing_sequences = []
        for path in self.raw_dir.glob("*.json"):
            prefix = path.name.split("-", 1)[0]
            if prefix.isdigit():
                existing_sequences.append(int(prefix))
        self.sequence = max(existing_sequences, default=0)
        self.records: list[dict[str, Any]] = list(read_json(run_dir / "transport.json", []) or [])
        self.cache_path = OUT / "cache-index.json"
        self.cache = read_json(self.cache_path, {}) or {}

    def _record(self, row: Mapping[str, Any]) -> None:
        with self._lock:
            self.records.append(dict(row))

    def _extract(self, response: Mapping[str, Any], function_name: str) -> tuple[Mapping[str, Any] | None, str | None]:
        import hng2_schema_controller as controller

        payload, _, error = controller.extract_strict_tool_payload(
            response,
            expected_function_name=function_name,
        )
        return payload, error

    def call(
        self,
        *,
        stage: str,
        unit_id: str,
        system: str,
        payload: Mapping[str, Any],
        function: Mapping[str, Any],
        function_name: str,
        max_tokens: int,
    ) -> Mapping[str, Any] | None:
        from smoke_deepseek import call_deepseek

        prompt_version = PROMPT_VERSIONS[stage]
        packet_hash = stable_hash({
            "stage": stage,
            "prompt_version": prompt_version,
            "model": MODEL,
            "system": system,
            "payload": payload,
            "function": function,
        })
        cached = self.cache.get(packet_hash)
        if isinstance(cached, Mapping):
            raw_path = ROOT / text(cached.get("raw_path"))
            if raw_path.is_file():
                response = read_json(raw_path, {}) or {}
                parsed, error = self._extract(response, function_name)
                if parsed is not None and error is None:
                    self._record({
                        "stage": stage,
                        "unit_id": unit_id,
                        "packet_hash": packet_hash,
                        "classification": "cache_hit",
                        "raw_path": str(raw_path.relative_to(ROOT)),
                        "usage": {},
                        "elapsed_seconds": 0,
                    })
                    return parsed
        if not self.live:
            self._record({
                "stage": stage,
                "unit_id": unit_id,
                "packet_hash": packet_hash,
                "classification": "offline_cache_miss",
                "usage": {},
                "elapsed_seconds": 0,
            })
            return None

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": canonical_json(payload)},
        ]
        for attempt in (1, 2):
            with self._lock:
                self.sequence += 1
                sequence = self.sequence
            started = time.monotonic()
            row: dict[str, Any] = {
                "sequence": sequence,
                "attempt": attempt,
                "stage": stage,
                "unit_id": unit_id,
                "packet_hash": packet_hash,
                "prompt_version": prompt_version,
                "model": MODEL,
                "start_time": utc_now(),
            }
            try:
                response = call_deepseek(
                    messages,
                    model=MODEL,
                    temperature=0,
                    thinking={"type": "disabled"},
                    max_tokens=max_tokens,
                    timeout=180,
                    endpoint=STRICT_ENDPOINT,
                    tools=[dict(function)],
                    tool_choice={"type": "function", "function": {"name": function_name}},
                )
                name = f"{sequence:05d}-{safe_slug(stage)}-{safe_slug(unit_id)}-attempt{attempt}.json"
                raw_path = self.raw_dir / name
                if raw_path.exists():
                    raise RuntimeError("immutable_raw_response_exists")
                write_json(raw_path, response)
                row.update({
                    "raw_path": str(raw_path.relative_to(ROOT)),
                    "usage": usage(response),
                    "finish_reason": finish_reason(response),
                })
                if finish_reason(response) == "length":
                    row["classification"] = "response_truncated"
                    row["elapsed_seconds"] = round(time.monotonic() - started, 3)
                    row["end_time"] = utc_now()
                    self._record(row)
                    continue
                parsed, error = self._extract(response, function_name)
                if error or parsed is None:
                    row.update({"classification": "response_parse_failure", "parse_error": error})
                    row["elapsed_seconds"] = round(time.monotonic() - started, 3)
                    row["end_time"] = utc_now()
                    self._record(row)
                    continue
                row["classification"] = "parsed"
                row["elapsed_seconds"] = round(time.monotonic() - started, 3)
                row["end_time"] = utc_now()
                self._record(row)
                with self._lock:
                    self.cache[packet_hash] = {
                        "raw_path": str(raw_path.relative_to(ROOT)),
                        "stage": stage,
                        "unit_id": unit_id,
                        "prompt_version": prompt_version,
                        "model": MODEL,
                    }
                    write_json(self.cache_path, self.cache)
                return parsed
            except Exception as exc:
                row.update({"classification": "provider_request_failure", **safe_error(exc)})
                row["elapsed_seconds"] = round(time.monotonic() - started, 3)
                row["end_time"] = utc_now()
                self._record(row)
        return None

    def metrics(self) -> dict[str, Any]:
        calls = [row for row in self.records if row.get("classification") != "cache_hit"]
        usages = [row.get("usage") or {} for row in calls]
        latencies = [float(row.get("elapsed_seconds") or 0) for row in calls if float(row.get("elapsed_seconds") or 0) > 0]
        by_stage: dict[str, dict[str, Any]] = {}
        for stage in PROMPT_VERSIONS:
            rows = [row for row in self.records if row.get("stage") == stage]
            stage_usages = [row.get("usage") or {} for row in rows]
            stage_latencies = [float(row.get("elapsed_seconds") or 0) for row in rows if float(row.get("elapsed_seconds") or 0) > 0]
            by_stage[stage] = {
                "calls": sum(row.get("classification") != "cache_hit" for row in rows),
                "cache_hits": sum(row.get("classification") == "cache_hit" for row in rows),
                "retries": sum(int(row.get("attempt") or 1) > 1 for row in rows),
                "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in rows),
                "parse_failures": sum(row.get("classification") == "response_parse_failure" for row in rows),
                "truncations": sum(row.get("classification") == "response_truncated" for row in rows),
                "prompt_tokens": sum(int(row.get("prompt_tokens") or 0) for row in stage_usages),
                "completion_tokens": sum(int(row.get("completion_tokens") or 0) for row in stage_usages),
                "total_tokens": sum(int(row.get("total_tokens") or 0) for row in stage_usages),
                "median_latency_seconds": round(statistics.median(stage_latencies), 3) if stage_latencies else 0,
                "max_latency_seconds": round(max(stage_latencies), 3) if stage_latencies else 0,
            }
        return {
            "model": MODEL,
            "calls": len(calls),
            "cache_hits": sum(row.get("classification") == "cache_hit" for row in self.records),
            "retries": sum(int(row.get("attempt") or 1) > 1 for row in calls),
            "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in calls),
            "parse_failures": sum(row.get("classification") == "response_parse_failure" for row in calls),
            "truncations": sum(row.get("classification") == "response_truncated" for row in calls),
            "prompt_tokens": sum(int(row.get("prompt_tokens") or 0) for row in usages),
            "completion_tokens": sum(int(row.get("completion_tokens") or 0) for row in usages),
            "total_tokens": sum(int(row.get("total_tokens") or 0) for row in usages),
            "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0,
            "max_latency_seconds": round(max(latencies), 3) if latencies else 0,
            "by_stage": by_stage,
        }
