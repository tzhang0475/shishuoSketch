"""Bounded A2OV transport with no committed raw provider envelopes."""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import time
from typing import Any, Mapping

from .common import (
    FUNCTION_NAME,
    MAX_PROVIDER_ATTEMPTS,
    MODEL,
    PROMPT_VERSION,
    STRICT_ENDPOINT,
    TEMPERATURE,
    THINKING,
    canonical_json,
    stable_hash,
    text,
)
from .contracts import reviewer_tool, validate_reviewer_payload


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


def _extract(response: Mapping[str, Any]) -> tuple[Mapping[str, Any] | None, str | None]:
    import hng2_schema_controller as controller

    payload, _, error = controller.extract_strict_tool_payload(response, expected_function_name=FUNCTION_NAME)
    return payload, error


def _scrub(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if any(token in str(key).lower() for token in ("secret", "token", "api_key", "authorization")) else _scrub(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_scrub(child) for child in value]
    return value


def error_details(exc: BaseException) -> dict[str, Any]:
    body = text(getattr(exc, "provider_error_body", ""))
    secret = os.environ.get("DEEPSEEK_API_KEY")
    if secret:
        body = body.replace(secret, "[REDACTED]")
    try:
        decoded = json.loads(body) if body else None
    except (TypeError, ValueError):
        decoded = None
    safe_body = json.dumps(_scrub(decoded), ensure_ascii=False, sort_keys=True, separators=(",", ":")) if decoded is not None else body
    result: dict[str, Any] = {
        "http_status": getattr(exc, "http_status", None),
        "provider_error_body": safe_body[:4000],
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


def _witness(response: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(response, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _base(stage: str, case_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "stage": stage,
        "case_id": case_id,
        "request_hash": stable_hash({"stage": stage, "case_id": case_id, "payload": payload}),
        "model": MODEL,
        "temperature": TEMPERATURE,
        "thinking": dict(THINKING),
        "prompt_version": PROMPT_VERSION,
    }


class ReviewerClient:
    def __init__(self, *, live: bool) -> None:
        self.live = live
        self.attempts = 0

    def probe(self, messages: list[Mapping[str, Any]], tool: Mapping[str, Any]) -> tuple[Mapping[str, Any] | None, dict[str, Any]]:
        from smoke_deepseek import call_deepseek

        payload = {"probe": True}
        row = _base("schema_probe", "schema-probe", payload)
        row["attempt"] = 1
        started = time.monotonic()
        if not self.live:
            row.update({"classification": "offline_no_provider_call", "valid": True, "usage": {}, "elapsed_seconds": 0})
            return {"case_id": "schema-probe", "decision": "confirm_primary", "revised_narrative_function": None, "confidence": "high", "supporting_evidence_ids": [], "reason_summary": "offline"}, row
        self.attempts += 1
        try:
            response = call_deepseek(
                messages,
                model=MODEL,
                temperature=TEMPERATURE,
                thinking=THINKING,
                max_tokens=300,
                timeout=180,
                endpoint=STRICT_ENDPOINT,
                tools=[dict(tool)],
                tool_choice={"type": "function", "function": {"name": FUNCTION_NAME}},
            )
            extracted, parse_error = _extract(response)
            row.update({
                "classification": "parsed" if extracted is not None and parse_error is None else "response_parse_failure",
                "valid": extracted is not None and parse_error is None,
                "parse_error": parse_error,
                "usage": _usage(response),
                "finish_reason": _finish(response),
                "response_witness_sha256": _witness(response),
            })
            return extracted, row
        except Exception as exc:
            row.update({
                "classification": "provider_request_failure",
                "valid": False,
                "retryable": False,
                **error_details(exc),
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            })
            return None, row
        finally:
            row["elapsed_seconds"] = round(time.monotonic() - started, 3)

    def call(
        self,
        *,
        case_id: str,
        system: str,
        payload: Mapping[str, Any],
        tool: Mapping[str, Any],
    ) -> tuple[Mapping[str, Any] | None, dict[str, Any]]:
        from smoke_deepseek import call_deepseek

        row = _base("reviewer", case_id, payload)
        if not self.live:
            row.update({"attempt": 0, "classification": "offline_no_provider_call", "valid": False, "usage": {}, "elapsed_seconds": 0})
            return None, row
        attempt_history: list[dict[str, Any]] = []
        for attempt in (1, 2):
            if self.attempts >= MAX_PROVIDER_ATTEMPTS:
                row.update({"attempt": attempt, "classification": "provider_attempt_budget_exhausted", "valid": False, "usage": {}, "elapsed_seconds": 0})
                return None, row
            self.attempts += 1
            started = time.monotonic()
            try:
                response = call_deepseek(
                    [{"role": "system", "content": system}, {"role": "user", "content": canonical_json(payload)}],
                    model=MODEL,
                    temperature=TEMPERATURE,
                    thinking=THINKING,
                    max_tokens=500,
                    timeout=180,
                    endpoint=STRICT_ENDPOINT,
                    tools=[dict(tool)],
                    tool_choice={"type": "function", "function": {"name": FUNCTION_NAME}},
                )
                extracted, parse_error = _extract(response)
                finish = _finish(response)
                classification = "response_truncated" if finish == "length" else ("parsed" if extracted is not None and parse_error is None else "response_parse_failure")
                row.update({
                    "attempt": attempt,
                    "classification": classification,
                    "valid": classification == "parsed",
                    "parse_error": parse_error,
                    "usage": _usage(response),
                    "finish_reason": finish,
                    "response_witness_sha256": _witness(response),
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                })
                if attempt_history:
                    row["attempt_history"] = attempt_history
                return extracted if classification == "parsed" else None, row
            except Exception as exc:
                retryable = is_retryable(exc)
                details = error_details(exc)
                attempt_history.append({"attempt": attempt, "classification": "provider_request_failure", "retryable": retryable, **details})
                row.update({
                    "attempt": attempt,
                    "classification": "provider_request_failure",
                    "valid": False,
                    "retryable": retryable,
                    **details,
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                })
                if not retryable:
                    if attempt_history[:-1]:
                        row["attempt_history"] = attempt_history[:-1]
                    return None, row
        row["attempt_history"] = attempt_history
        return None, row


def summarize(rows: list[Mapping[str, Any]], *, live: bool, provider_attempts: int) -> dict[str, Any]:
    latencies = [float(row.get("elapsed_seconds") or 0) for row in rows if float(row.get("elapsed_seconds") or 0) > 0]
    usages = [row.get("usage") or {} for row in rows]
    return {
        "schema": "sfh2-a2ov-provider-accounting-v1",
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "endpoint": STRICT_ENDPOINT,
        "live": live,
        "provider_calls": len(rows) if live else 0,
        "schema_probe_calls": sum(row.get("stage") == "schema_probe" for row in rows),
        "reviewer_calls": sum(row.get("stage") == "reviewer" for row in rows),
        "parsed_calls": sum(row.get("classification") == "parsed" for row in rows),
        "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in rows),
        "invalid_payloads": sum(row.get("classification") == "response_parse_failure" for row in rows),
        "truncations": sum(row.get("classification") == "response_truncated" for row in rows),
        "http_400_failures": sum(row.get("http_status") == 400 for row in rows),
        "retries": sum(int(row.get("attempt") or 0) > 1 for row in rows),
        "provider_attempts": provider_attempts if live else 0,
        "prompt_tokens": sum(int(usage.get("prompt_tokens") or 0) for usage in usages),
        "completion_tokens": sum(int(usage.get("completion_tokens") or 0) for usage in usages),
        "total_tokens": sum(int(usage.get("total_tokens") or 0) for usage in usages),
        "median_latency_seconds": round(statistics.median(latencies), 3) if latencies else 0,
        "max_latency_seconds": round(max(latencies), 3) if latencies else 0,
        "raw_provider_storage": "external_only_not_committed",
        "candidate_only": True,
        "canonical_write_back": False,
    }
