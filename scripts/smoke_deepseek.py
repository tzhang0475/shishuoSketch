#!/usr/bin/env python3
"""Make one minimal DeepSeek API connectivity check."""

import json
import os
import urllib.error
import urllib.request
from typing import Any, Mapping, Sequence


API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_BETA_URL = "https://api.deepseek.com/beta/chat/completions"
MODEL = "deepseek-v4-flash"
PROMPT = 'Return JSON: {"status":"connected"}'


def call_deepseek(
    messages: Sequence[Mapping[str, Any]],
    *,
    model: str = MODEL,
    temperature: float = 0,
    response_format: Mapping[str, str] | None = None,
    tools: Sequence[Mapping[str, Any]] | None = None,
    tool_choice: str | Mapping[str, Any] | None = None,
    thinking: Mapping[str, Any] | None = None,
    max_tokens: int | None = None,
    timeout: int = 60,
    endpoint: str | None = None,
) -> dict[str, Any]:
    """Call the existing OpenAI-compatible DeepSeek endpoint.

    This deliberately remains a small stdlib client so DS1 can reuse the
    smoke-test integration without adding an SDK or exposing credentials to
    generated artifacts.
    """

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")

    payload: dict[str, Any] = {
        "model": model,
        "messages": list(messages),
        "temperature": temperature,
        "stream": False,
    }
    if response_format is not None:
        payload["response_format"] = dict(response_format)
    if tools is not None:
        payload["tools"] = [dict(tool) for tool in tools]
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice
    if thinking is not None:
        payload["thinking"] = dict(thinking)
    if max_tokens is not None:
        payload["max_tokens"] = int(max_tokens)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint or API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        body = ""
        try:
            body = error.read().decode("utf-8", "replace")[:4000]
        except Exception:
            body = ""
        failure = RuntimeError(f"DeepSeek API request failed with HTTP {error.code}")
        failure.http_status = error.code  # type: ignore[attr-defined]
        failure.provider_error_body = body  # type: ignore[attr-defined]
        raise failure from error
    except urllib.error.URLError as error:
        failure = RuntimeError(f"DeepSeek API request failed: {error.reason}")
        failure.http_status = None  # type: ignore[attr-defined]
        failure.provider_error_body = ""  # type: ignore[attr-defined]
        raise failure from error


def main() -> int:
    try:
        result = call_deepseek([{"role": "user", "content": PROMPT}])
    except RuntimeError as error:
        raise SystemExit(str(error)) from error

    content = result["choices"][0]["message"]["content"]
    usage = result.get("usage", {})
    print("content:")
    print(content)
    print("token_usage:")
    print(json.dumps(usage, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
