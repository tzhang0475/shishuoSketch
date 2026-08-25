#!/usr/bin/env python3
"""Validate HNG2-C.3 closeout artifacts without model calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/generated/hng2-algorithm-closeout"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    failures: list[str] = []
    selection_path = BASE / "selection.json"
    replay_path = BASE / "person-offline-replay.json"
    if not selection_path.is_file() or not replay_path.is_file():
        raise SystemExit("missing selection or Person replay")
    selection = load(selection_path)
    replay = load(replay_path)
    if selection.get("story_count") != 10 or selection.get("semantic_call_count") != 20:
        failures.append("frozen temporal selection shape invalid")
    if replay.get("api_calls") != 0:
        failures.append("Person replay made API calls")
    if not replay.get("person_lane_frozen"):
        failures.append("Person lane freeze checks failed")
    checks = replay.get("regression_checks") or {}
    if not checks.get("yi_resolves_person_053"):
        failures.append("廙 did not resolve to person-053")
    if (replay.get("metrics") or {}).get("nonperson_person_id_anomalies"):
        failures.append("non-person Person-ID leakage")
    if (replay.get("metrics") or {}).get("collapsed_nonidentity_self_relations"):
        failures.append("collapsed self relation projected")

    live_summary: dict[str, Any] | None = None
    if args.run_id:
        run = BASE / "live" / args.run_id
        for name in ("preflight.json", "temporal-results.json", "metrics.json", "manifest.json"):
            if not (run / name).is_file():
                failures.append(f"missing live artifact {name}")
        if not failures:
            metrics = load(run / "metrics.json")
            manifest = load(run / "manifest.json")
            raw_count = len(list((run / "raw-api").glob("*.json")))
            if manifest.get("semantic_calls") != 20 or metrics.get("semantic_calls") != 20 or raw_count != 20:
                failures.append("live semantic/raw call accounting mismatch")
            if manifest.get("no_retries") is not True or manifest.get("no_search") is not True:
                failures.append("no-retry/no-search guard missing")
            if metrics.get("response_truncated") or metrics.get("provider_or_parse_failures"):
                failures.append("live response failure detected")
            if metrics.get("false_temporal_promotions"):
                failures.append("false temporal promotion detected")
            if not metrics.get("temporal_lane_frozen"):
                failures.append("Temporal lane freeze checks failed")
            if manifest.get("canonical_write_back") is not False or metrics.get("canonical_write_back") is not False:
                failures.append("canonical write-back guard missing")
            live_summary = {
                "run": str(run),
                "raw_api_responses": raw_count,
                "temporal_lane_frozen": metrics.get("temporal_lane_frozen"),
                "regression_checks": metrics.get("regression_checks"),
            }
    status = "failed" if failures else "passed"
    print(json.dumps({"status": status, "failures": failures, "person_lane_frozen": replay.get("person_lane_frozen"), "live": live_summary}, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
