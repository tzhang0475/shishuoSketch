#!/usr/bin/env python3
"""Validate the isolated HNG2-SC small-card replay/live projection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import hng2_schema_strict_tools as strict_tools  # noqa: E402


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    replay = root / "offline-replay"
    metrics = read_json(replay / "metrics.json")
    if metrics.get("api_calls") != 0:
        errors.append("offline_replay_has_api_calls")
    if metrics.get("valid_cards") != 5 or metrics.get("invalid_cards") != 0:
        errors.append("offline_replay_card_count")
    if metrics.get("structural_target_status") != "not_single_person":
        errors.append("structural_target_regression")
    if metrics.get("identity_propagation_count", 0) < 1:
        errors.append("identity_propagation_missing")
    for path in (replay / "cards.json", replay / "manifest.json"):
        if not path.is_file():
            errors.append(f"missing:{path.relative_to(root)}")
    return {"valid": not errors, "errors": errors, "small_card_schema_hash": strict_tools.small_card_schema_hash(), "canonical_write_back": False}


def validate_live(root: Path) -> dict[str, Any]:
    live_roots = [path for path in (root / "live").glob("*") if (path / "manifest.json").is_file()]
    if not live_roots:
        return {"valid": False, "errors": ["live_run_missing"], "canonical_write_back": False}
    live = sorted(live_roots)[-1]
    errors: list[str] = []
    metrics = read_json(live / "metrics.json")
    selection = read_json(live / "selection.json")
    cards = read_json(live / "semantic-cards.json")
    runs = read_json(live / "case-runs.json")
    preflight = read_json(live / "raw-api" / "001-preflight-preflight.json")
    validations = cards.get("validations", []) if isinstance(cards, dict) else []
    run_rows = runs.get("runs", []) if isinstance(runs, dict) else []
    if len(selection.get("cases", [])) != 5:
        errors.append("live_selection_not_five")
    if preflight.get("status") != "response":
        errors.append("preflight_failed")
    if len(validations) != 5 or metrics.get("semantic_calls") != 5:
        errors.append("semantic_call_count")
    if metrics.get("valid_strict_tool_calls") != 5:
        errors.append("tool_call_count")
    if metrics.get("response_truncated") or metrics.get("response_parse_failures"):
        errors.append("unexpected_envelope_failure")
    for validation, run in zip(validations, run_rows):
        if validation.get("classification") == "card_validation_failure" and "projection" in run:
            errors.append("rejected_card_mutated_projection")
    return {"valid": not errors, "errors": errors, "root": str(live.relative_to(ROOT)), "small_card_schema_hash": strict_tools.small_card_schema_hash(), "canonical_write_back": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT / "data/generated/hng2-schema-controller-small-card"))
    parser.add_argument("--mode", choices=("offline", "live"), default="offline")
    args = parser.parse_args()
    result = validate(Path(args.root)) if args.mode == "offline" else validate_live(Path(args.root))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
