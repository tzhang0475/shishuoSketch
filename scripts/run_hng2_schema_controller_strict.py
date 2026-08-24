#!/usr/bin/env python3
"""HNG2-SC strict Function Calling replay and five-case validation.

This wrapper keeps the prior SC.1 hardening runner's research logic but sends
semantic cards through DeepSeek's forced strict tool on the Beta endpoint.  A
new output namespace is used so the older JSON-mode raw responses remain
immutable evidence.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hng2_schema_strict_tools as strict_tools  # noqa: E402
import run_hng2_schema_controller_hardening as base  # noqa: E402


OUT = ROOT / "data/generated/hng2-schema-controller-strict"
base.OUT = OUT
base.PROMPT_VERSION = "hng2-sc1-strict-function-card-v1"


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def strict_fixture_replay(fixtures: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Replay fixture payloads through the actual strict tool envelope parser."""

    rows: list[dict[str, Any]] = []
    for fixture in fixtures:
        payload = strict_tools.controller_payload_to_wire(fixture.get("payload") or {})
        envelope = {
            "choices": [{
                "finish_reason": "stop",
                "message": {
                    "content": "",
                    "tool_calls": [{
                        "id": "fixture-call",
                        "type": "function",
                        "function": {"name": strict_tools.FUNCTION_NAME, "arguments": json.dumps(payload, ensure_ascii=False, sort_keys=True)},
                    }],
                },
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        case = fixture.get("case") or {}
        passages = fixture.get("passages") or {}
        parsed = base.classify_response(
            {"status": "response", "response": envelope},
            case,
            passages,
            require_target=True,
            candidate_rows=fixture.get("prior_candidates") or [],
            strict_function=True,
        )
        rows.append({
            "fixture_id": fixture.get("fixture_id"),
            "classification": parsed.get("classification"),
            "response_channel": parsed.get("response_channel"),
            "parse_error": parsed.get("parse_error"),
            "validation": parsed.get("validation"),
            "payload": parsed.get("payload"),
            "canonical_write_back": False,
        })
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("classification") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return rows, counts


def replay() -> dict[str, Any]:
    result = base.replay()
    cases, gaps, sources = base.load_inputs()
    fixture_inputs = base.fixture_suite(cases, sources, base.hng02.person_catalog())
    strict_rows, strict_counts = strict_fixture_replay(fixture_inputs)
    metrics = dict(result.get("metrics") or {})
    semantic_card_rejections = sum(row.get("classification") in {"card_validation_failure", "response_truncated", "response_parse_failure"} for row in validation_rows if isinstance(row, Mapping))
    metrics.update({
        "stage": "hng2-schema-controller-strict-replay",
        "api_calls": 0,
        "strict_function_fixture_count": len(strict_rows),
        "strict_function_fixture_valid_count": strict_counts.get("valid_card", 0),
        "strict_function_fixture_rejected_count": sum(value for key, value in strict_counts.items() if key != "valid_card"),
        "strict_schema_hash": strict_tools.schema_hash(),
        "strict_function_name": strict_tools.FUNCTION_NAME,
        "strict_endpoint": strict_tools.STRICT_ENDPOINT,
        "canonical_write_back": False,
    })
    replay_path = OUT / "replay-results.json"
    replay_payload = read_json(replay_path, {}) or {}
    replay_payload["strict_function_fixtures"] = strict_rows
    replay_payload["metrics"] = metrics
    replay_payload["canonical_write_back"] = False
    write_json(replay_path, replay_payload)
    write_json(OUT / "strict-function-fixtures.json", {
        "schema": "historical-entity-schema-v1",
        "function_name": strict_tools.FUNCTION_NAME,
        "schema_hash": strict_tools.schema_hash(),
        "rows": strict_rows,
        "canonical_write_back": False,
    })
    write_json(OUT / "metrics.json", metrics)
    manifest = dict(read_json(OUT / "manifest.json", {}) or {})
    manifest.update({
        "stage": "hng2-schema-controller-strict-replay",
        "strict_function_calling": True,
        "strict_endpoint": strict_tools.STRICT_ENDPOINT,
        "strict_function_name": strict_tools.FUNCTION_NAME,
        "strict_schema_hash": strict_tools.schema_hash(),
        "prompt_version": base.PROMPT_VERSION,
        "api_calls": 0,
        "canonical_write_back": False,
    })
    write_json(OUT / "manifest.json", manifest)
    result["strict_function_fixtures"] = strict_rows
    result["metrics"] = metrics
    result["manifest"] = manifest
    return result


def postprocess_live(result: Mapping[str, Any], run_id: str) -> dict[str, Any]:
    live_root = OUT / "live" / run_id
    metrics = dict(read_json(live_root / "metrics.json", result.get("metrics") or {}) or {})
    raw_rows = []
    raw_dir = live_root / "raw-api"
    for path in sorted(raw_dir.glob("*-semantic-*.json")):
        row = read_json(path, {}) or {}
        raw_rows.append(row)
    strict_rows = [row for row in raw_rows if row.get("strict_function") is True]
    valid_tool_calls = sum(row.get("status") == "response" and row.get("response_channel") == "tool_call" and row.get("tool_name") == strict_tools.FUNCTION_NAME for row in strict_rows)
    rejected_tool_calls = sum(row.get("status") == "response" and not (row.get("response_channel") == "tool_call" and row.get("tool_name") == strict_tools.FUNCTION_NAME) for row in strict_rows)
    semantic_doc = read_json(live_root / "semantic-assessments.json", {}) or {}
    validation_rows = semantic_doc.get("validations", []) if isinstance(semantic_doc, Mapping) else []
    undefined_field_errors = sum(
        1
        for row in validation_rows if isinstance(row, Mapping)
        for error in ((row.get("validation") or {}).get("errors", []) if isinstance(row.get("validation"), Mapping) else [])
        if str(error).startswith("unknown_")
    )
    first_round_rows = [row for row in validation_rows if isinstance(row, Mapping) and row.get("round") == 1]
    semantic_card_rejections = sum(
        row.get("classification") in {"card_validation_failure", "response_truncated", "response_parse_failure"}
        for row in first_round_rows
    )
    metrics.update({
        "stage": "hng2-schema-controller-strict-live",
        "strict_function_calling": True,
        "strict_function_name": strict_tools.FUNCTION_NAME,
        "strict_endpoint": strict_tools.STRICT_ENDPOINT,
        "strict_schema_hash": strict_tools.schema_hash(),
        "valid_strict_tool_calls": valid_tool_calls,
        "rejected_strict_tool_calls": rejected_tool_calls,
        "valid_strict_tool_calls_first_round": sum(row.get("response_channel") == "tool_call" for row in first_round_rows),
        "rejected_strict_tool_calls_first_round": sum(row.get("response_channel") != "tool_call" for row in first_round_rows),
        "valid_strict_cards_first_round": sum(row.get("classification") == "valid_card" for row in first_round_rows),
        "semantic_card_rejections_first_round": semantic_card_rejections,
        "undefined_field_invention_count": undefined_field_errors,
        "canonical_write_back": False,
    })
    write_json(live_root / "metrics.json", metrics)
    selection = read_json(live_root / "selection.json", {}) or {}
    selection["stage"] = "hng2-schema-controller-strict-live"
    selection["strict_function_calling"] = True
    selection["strict_schema_hash"] = strict_tools.schema_hash()
    write_json(live_root / "selection.json", selection)
    manifest = dict(read_json(live_root / "manifest.json", {}) or {})
    manifest.update({
        "stage": "hng2-schema-controller-strict-live",
        "strict_function_calling": True,
        "strict_endpoint": strict_tools.STRICT_ENDPOINT,
        "strict_function_name": strict_tools.FUNCTION_NAME,
        "strict_schema_hash": strict_tools.schema_hash(),
        "prompt_version": base.PROMPT_VERSION,
        "canonical_write_back": False,
    })
    write_json(live_root / "manifest.json", manifest)
    return {**dict(result), "metrics": metrics, "output_root": str(live_root.relative_to(ROOT))}


def live(run_id: str) -> dict[str, Any]:
    return postprocess_live(base.live(run_id), run_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("replay", "live"), default="replay")
    parser.add_argument("--run-id", default=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    result = replay() if args.mode == "replay" else live(args.run_id)
    if not args.quiet:
        print(json.dumps(result.get("metrics", {}), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
