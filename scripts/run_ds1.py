#!/usr/bin/env python3
"""Run the single-story DS1 DeepSeek context candidate experiment."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ds1_common import (  # noqa: E402
    CANDIDATE_PATH,
    CONTEXT_PATH,
    MODEL,
    PROMPT_VERSION,
    ROOT as PROJECT_ROOT,
    STORY_ID,
    build_context_bundle,
    build_prompt,
    ensure_review,
    input_hash,
    parse_model_json,
    sha256_file,
    stable_json,
    validate_scene_context,
    write_json,
)
from smoke_deepseek import call_deepseek  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", default=STORY_ID, help=f"DS1 Story (only {STORY_ID} is supported)")
    args = parser.parse_args()
    if args.story != STORY_ID:
        parser.error(f"DS1 is intentionally scoped to {STORY_ID}")

    context = build_context_bundle(PROJECT_ROOT, args.story)
    write_json(PROJECT_ROOT, CONTEXT_PATH, context)
    messages = build_prompt(context)
    request_hash = input_hash(messages)

    try:
        response = call_deepseek(
            messages,
            model=MODEL,
            temperature=0,
            response_format={"type": "json_object"},
        )
    except RuntimeError as error:
        raise SystemExit(str(error)) from error

    try:
        raw_content = str(response["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as error:
        raise SystemExit("DeepSeek response did not contain choices[0].message.content") from error

    validation_errors: list[str] = []
    result: Any = None
    try:
        result = parse_model_json(raw_content)
        validation_errors = validate_scene_context(result, context["evidence_bundle_ids"])
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        validation_errors = [f"model JSON is invalid: {error}"]

    candidate = {
        "schema": "ds1-scene-context-candidate",
        "schema_version": 1,
        "stage": "DS1",
        "story_id": STORY_ID,
        "candidate_status": "candidate",
        "model": MODEL,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prompt_config_version": PROMPT_VERSION,
        "parameters": {"temperature": 0, "response_format": "json_object"},
        "token_usage": response.get("usage", {}),
        "evidence_bundle_ids": context["evidence_bundle_ids"],
        "context_path": CONTEXT_PATH.as_posix(),
        "context_sha256": sha256_file(PROJECT_ROOT, CONTEXT_PATH),
        "input_hash": request_hash,
        "raw_model_content": raw_content,
        "result": result if not validation_errors else None,
        "validation_errors": validation_errors,
        "canonical_write_back": False,
    }
    write_json(PROJECT_ROOT, CANDIDATE_PATH, candidate)
    candidate_sha256 = sha256_file(PROJECT_ROOT, CANDIDATE_PATH)
    review = ensure_review(PROJECT_ROOT, candidate_sha256)

    print(f"context: {CONTEXT_PATH.as_posix()}")
    print(f"candidate: {CANDIDATE_PATH.as_posix()}")
    print("review: data/annotation/ds1-review.json")
    print(f"review_decision: {review.get('decision', 'pending')}")
    print(f"validation: {'pass' if not validation_errors else 'fail'}")
    if validation_errors:
        print(stable_json({"validation_errors": validation_errors}), end="")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
