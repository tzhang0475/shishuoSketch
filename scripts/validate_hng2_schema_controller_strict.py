#!/usr/bin/env python3
"""Fail-closed validator for HNG2-SC strict Function Calling outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hng2_schema_strict_tools as strict_tools  # noqa: E402
import run_hng2_schema_controller_strict as runner  # noqa: E402


def read(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def fail(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def validate_replay(root: Path = runner.OUT) -> dict[str, Any]:
    errors: list[str] = []
    manifest = read(root / "manifest.json", {}) or {}
    metrics = read(root / "metrics.json", {}) or {}
    fixtures = read(root / "strict-function-fixtures.json", {}) or {}
    rows = fixtures.get("rows", []) if isinstance(fixtures, Mapping) else []
    fail(errors, manifest.get("stage") == "hng2-schema-controller-strict-replay", "wrong_replay_stage")
    fail(errors, metrics.get("api_calls") == 0, "offline_replay_called_api")
    fail(errors, metrics.get("canonical_write_back") is False, "canonical_write_back")
    fail(errors, manifest.get("strict_function_calling") is True, "strict_function_calling_not_marked")
    fail(errors, manifest.get("strict_function_name") == strict_tools.FUNCTION_NAME, "wrong_function_name")
    fail(errors, manifest.get("strict_schema_hash") == strict_tools.schema_hash(), "strict_schema_hash_mismatch")
    fail(errors, len(rows) == 8, "strict_fixture_count")
    fail(errors, all(row.get("response_channel") == "tool_call" for row in rows), "fixture_not_parsed_as_tool_call")
    fail(errors, all(row.get("classification") == "valid_card" for row in rows), "strict_fixture_invalid")
    return {"valid": not errors, "errors": sorted(set(errors)), "mode": "replay", "api_calls": 0}


def _latest_live_root(root: Path) -> Path:
    candidates = [path for path in (root / "live").glob("*") if (path / "manifest.json").is_file()]
    if candidates:
        return sorted(candidates)[-1]
    return root


def validate_live(root: Path = runner.OUT) -> dict[str, Any]:
    root = _latest_live_root(root)
    errors: list[str] = []
    manifest = read(root / "manifest.json", {}) or {}
    selection = read(root / "selection.json", {}) or {}
    metrics = read(root / "metrics.json", {}) or {}
    semantic_doc = read(root / "semantic-assessments.json", {}) or {}
    validations = semantic_doc.get("validations", []) if isinstance(semantic_doc, Mapping) else []
    raw_root = ROOT / str(manifest.get("raw_api_root") or "")
    fail(errors, manifest.get("stage") == "hng2-schema-controller-strict-live", "wrong_live_stage")
    fail(errors, len(selection.get("cases", [])) == 5, "live_selection_not_five")
    fail(errors, metrics.get("preflight_succeeded") is True, "preflight_failed")
    fail(errors, metrics.get("no_frontier_expansion") is True, "frontier_expansion")
    fail(errors, metrics.get("strict_function_calling") is True, "strict_function_calling_not_marked")
    fail(errors, manifest.get("strict_endpoint") == strict_tools.STRICT_ENDPOINT, "wrong_strict_base_endpoint")
    fail(errors, manifest.get("strict_schema_hash") == strict_tools.schema_hash(), "strict_schema_hash_mismatch")
    fail(errors, raw_root.is_dir(), "raw_api_root_missing")
    semantic_validations = [row for row in validations if isinstance(row, Mapping)]
    fail(errors, all(row.get("response_channel") == "tool_call" or row.get("classification") != "valid_card" for row in semantic_validations), "valid_card_without_tool_call")
    fail(errors, all(row.get("response_channel") != "content" for row in semantic_validations), "content_channel_used_for_strict_card")
    fail(errors, all(row.get("response_channel") != "reasoning_content" for row in semantic_validations), "reasoning_channel_used_for_strict_card")
    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "mode": "live",
        "root": str(root.relative_to(ROOT)) if root.is_relative_to(ROOT) else str(root),
        "api_calls": metrics.get("api_calls", 0),
        "valid_strict_tool_calls_first_round": metrics.get("valid_strict_tool_calls_first_round", 0),
        "valid_strict_cards_first_round": metrics.get("valid_strict_cards_first_round", 0),
        "rejected_strict_tool_calls_first_round": metrics.get("rejected_strict_tool_calls_first_round", 0),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("replay", "live"), default="replay")
    parser.add_argument("--run-root", default="")
    args = parser.parse_args()
    root = Path(args.run_root) if args.run_root else runner.OUT
    result = validate_replay(root) if args.mode == "replay" else validate_live(root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
