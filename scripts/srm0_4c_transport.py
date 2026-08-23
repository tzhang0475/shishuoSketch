#!/usr/bin/env python3
"""Bounded DeepSeek transport for SRM0.4C.

This module owns transport concerns only.  It does not normalize or interpret
model output, so SRM0.4B's research logic remains unchanged.
"""

from __future__ import annotations

import json
import os
import socket
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

try:  # requests is present in the development/runtime image, but keep a stdlib fallback.
    import requests
except ImportError:  # pragma: no cover - exercised only in minimal environments
    requests = None  # type: ignore[assignment]


API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-v4-flash"
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 180


class DeepSeekProtocolError(RuntimeError):
    """The HTTP request succeeded but the provider body was not JSON."""

    protocol_failure = True


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _usage(response: Mapping[str, Any] | None) -> dict[str, Any]:
    value = response.get("usage", {}) if isinstance(response, Mapping) else {}
    return dict(value) if isinstance(value, Mapping) else {}


def _message_content(response: Mapping[str, Any] | None) -> str:
    choices = response.get("choices") if isinstance(response, Mapping) else None
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
        return ""
    message = choices[0].get("message")
    content = message.get("content") if isinstance(message, Mapping) else None
    return content if isinstance(content, str) else ""


def classify_transport_error(exc: BaseException, status: int | None = None) -> str:
    """Classify only the transport/API boundary; semantic errors are separate."""
    if getattr(exc, "protocol_failure", False):
        return "protocol_failure"
    if "deepseek_api_key is not set" in str(exc).lower():
        return "auth_failure"
    if status is not None:
        if status in {401, 403}:
            return "auth_failure"
        if status == 429:
            return "rate_limited"
        if 500 <= status <= 599:
            return "server_error"
        return "other_transport_failure"
    if requests is not None:
        if isinstance(exc, requests.exceptions.ConnectTimeout):
            return "connect_timeout"
        if isinstance(exc, requests.exceptions.ReadTimeout):
            return "read_timeout"
        if isinstance(exc, requests.exceptions.SSLError):
            return "tls_failure"
        if isinstance(exc, requests.exceptions.ProxyError):
            return "proxy_failure"
        if isinstance(exc, requests.exceptions.ConnectionError):
            text = str(exc).lower()
            if "operation not permitted" in text:
                return "sandbox_denied"
            return "other_transport_failure"
    if isinstance(exc, ssl.SSLError):
        return "tls_failure"
    if isinstance(exc, socket.gaierror):
        return "dns_failure"
    if isinstance(exc, TimeoutError):
        return "read_timeout"
    if isinstance(exc, urllib.error.HTTPError):
        return classify_transport_error(exc, int(exc.code))
    if isinstance(exc, urllib.error.URLError):
        reason = str(getattr(exc, "reason", exc)).lower()
        if "operation not permitted" in reason:
            return "sandbox_denied"
        if "name or service not known" in reason or "temporary failure in name resolution" in reason:
            return "dns_failure"
        if "ssl" in reason or "tls" in reason or "certificate" in reason:
            return "tls_failure"
        if "timed out" in reason:
            return "connect_timeout"
        if "proxy" in reason or "refused" in reason:
            return "proxy_failure"
    text = str(exc).lower()
    if "operation not permitted" in text:
        return "sandbox_denied"
    if "timed out" in text or "timeout" in text:
        return "read_timeout"
    return "other_transport_failure"


def retryable_failure(failure_class: str | None) -> bool:
    return failure_class in {"tls_failure", "other_transport_failure", "connect_timeout", "read_timeout", "server_error"}


def _record(
    *, story_id: str, round_number: int, completion_kind: str, attempt: int,
    start: str, elapsed: float, status: int | None, exc: BaseException | None,
    failure_class: str | None, response: Mapping[str, Any] | None,
    actual_request: bool,
) -> dict[str, Any]:
    message = str(exc) if exc is not None else None
    secret = os.environ.get("DEEPSEEK_API_KEY")
    if secret and message:
        message = message.replace(secret, "[REDACTED]")
    return {
        "story_id": story_id,
        "round": round_number,
        "completion_kind": completion_kind,
        "attempt": attempt,
        "actual_request": actual_request,
        "start_time": start,
        "elapsed_seconds": round(elapsed, 6),
        "http_status": status,
        "exception_class": type(exc).__name__ if exc is not None else None,
        "exception_message": message,
        "failure_class": failure_class,
        "response_model": response.get("model") if isinstance(response, Mapping) else None,
        "api_usage": _usage(response),
    }


class DeepSeekTransport:
    """A session-backed client with at most one retry per call."""

    def __init__(self, *, connect_timeout: int = CONNECT_TIMEOUT, read_timeout: int = READ_TIMEOUT, backoff_seconds: float = 2.0) -> None:
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.backoff_seconds = backoff_seconds
        self.session = requests.Session() if requests is not None else None

    def _payload(self, messages: Sequence[Mapping[str, Any]], *, model: str = MODEL) -> dict[str, Any]:
        return {
            "model": model,
            "messages": [dict(message) for message in messages],
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "tools": [],
            "stream": False,
        }

    def _one_request(self, payload: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str, int | None, BaseException | None]:
        key = os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            return None, "", None, RuntimeError("DEEPSEEK_API_KEY is not set")
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        if self.session is not None:
            try:
                response = self.session.post(API_URL, data=body, headers=headers, timeout=(self.connect_timeout, self.read_timeout))
                status = int(response.status_code)
                if status < 200 or status >= 300:
                    error = RuntimeError(f"DeepSeek API request failed with HTTP {status}")
                    setattr(error, "http_status", status)
                    return None, "", status, error
                try:
                    value = response.json()
                except ValueError as exc:
                    return None, response.text, status, DeepSeekProtocolError("DeepSeek API returned invalid JSON")
                response_value = dict(value) if isinstance(value, Mapping) else None
                return response_value, _message_content(response_value), status, None
            except Exception as exc:  # requests exception classification happens in caller
                return None, "", getattr(getattr(exc, "response", None), "status_code", None), exc
        request = urllib.request.Request(API_URL, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.read_timeout) as response:
                raw = response.read().decode("utf-8")
                try:
                    value = json.loads(raw)
                except ValueError:
                    return None, raw, int(response.status), DeepSeekProtocolError("DeepSeek API returned invalid JSON")
                response_value = dict(value) if isinstance(value, Mapping) else None
                return response_value, _message_content(response_value), int(response.status), None
        except urllib.error.HTTPError as exc:
            error = RuntimeError(f"DeepSeek API request failed with HTTP {exc.code}")
            setattr(error, "http_status", int(exc.code))
            return None, "", int(exc.code), error
        except Exception as exc:  # pragma: no cover - fallback only
            return None, "", None, exc

    def call(
        self, *, story_id: str, round_number: int, completion_kind: str,
        messages: Sequence[Mapping[str, Any]], attempt_start: int = 1,
        max_retries: int = 1,
    ) -> dict[str, Any]:
        payload = self._payload(messages)
        attempts: list[dict[str, Any]] = []
        response: dict[str, Any] | None = None
        content = ""
        last_error: BaseException | None = None
        for offset in range(max_retries + 1):
            attempt = attempt_start + offset
            started = time.monotonic()
            started_at = _now()
            response, content, status, error = self._one_request(payload)
            elapsed = time.monotonic() - started
            failure = None if error is None else classify_transport_error(error, getattr(error, "http_status", None) or status)
            attempts.append(_record(
                story_id=story_id, round_number=round_number, completion_kind=completion_kind,
                attempt=attempt, start=started_at, elapsed=elapsed, status=status,
                exc=error, failure_class=failure, response=response, actual_request=True,
            ))
            if error is None:
                return {"success": True, "response": response, "content": content, "error": None, "failure_class": None, "attempts": attempts}
            last_error = error
            if offset >= max_retries or not retryable_failure(failure):
                break
            if self.backoff_seconds:
                time.sleep(self.backoff_seconds)
        failure = classify_transport_error(last_error or RuntimeError("unknown transport failure"), getattr(last_error, "http_status", None))
        return {"success": False, "response": response, "content": content, "error": str(last_error) if last_error else "unknown transport failure", "failure_class": failure, "attempts": attempts}


def preserved_attempt(*, story_id: str, round_number: int, completion_kind: str, attempt: int, artifact: Mapping[str, Any]) -> dict[str, Any]:
    """Make an immutable audit projection of an old attempt without a call."""
    failure = artifact.get("failure_class")
    return _record(
        story_id=story_id, round_number=round_number, completion_kind=completion_kind,
        attempt=attempt, start=str(artifact.get("start_time") or ""),
        elapsed=float(artifact.get("elapsed_seconds") or 0), status=artifact.get("http_status"),
        exc=RuntimeError(str(artifact.get("transport_error") or artifact.get("protocol_error") or "preserved prior result")) if failure else None,
        failure_class=str(failure) if failure else None,
        response=artifact.get("raw_response") if isinstance(artifact.get("raw_response"), Mapping) else None,
        actual_request=False,
    )


__all__ = ["API_URL", "MODEL", "CONNECT_TIMEOUT", "READ_TIMEOUT", "DeepSeekTransport", "classify_transport_error", "preserved_attempt", "retryable_failure"]
