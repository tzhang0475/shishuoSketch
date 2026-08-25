#!/usr/bin/env python3
"""Validate one HNG2-C.2 Evidence-Atom run without calling DeepSeek."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/generated/hng2-evidence-atom-validation"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    parent = BASE / ("offline-replay" if args.offline else "live")
    if args.run_id:
        run = parent / args.run_id
    else:
        candidates = sorted(path for path in parent.iterdir() if path.is_dir()) if parent.is_dir() else []
        if not candidates:
            raise SystemExit("no HNG2-C.2 run found")
        run = candidates[-1]

    required = (
        "person-results.json", "temporal-results.json", "heldout-results.json",
        "comparison-with-hng2-c1.json", "evaluation.json", "metrics.json", "manifest.json",
    )
    missing = [name for name in required if not (run / name).is_file()]
    if missing:
        raise SystemExit(f"missing artifacts: {missing}")
    manifest = load(run / "manifest.json")
    metrics = load(run / "metrics.json")
    failures: list[str] = []
    if manifest.get("semantic_calls") != 44 or metrics.get("semantic_calls") != 44:
        failures.append("semantic call count is not 44")
    if manifest.get("canonical_write_back") is not False or metrics.get("canonical_write_back") is not False:
        failures.append("canonical write-back guard missing")
    if metrics.get("response_truncated"):
        failures.append("response truncation detected")
    anomalies = metrics.get("normalization_anomalies") or {}
    if anomalies.get("nonperson_with_person_id"):
        failures.append("non-person resolved to Person ID")
    if anomalies.get("projected_nonidentity_self_relation"):
        failures.append("normalized non-identity self relation projected")
    raw_count = len(list((run / "raw-api").glob("*.json"))) if not args.offline else 0
    if not args.offline and raw_count != 44:
        failures.append(f"raw API response count {raw_count}, expected 44")
    for lane in ("person_read", "temporal_read"):
        row = metrics.get(lane) or {}
        if row.get("atoms_returned") != int(row.get("atoms_grounded") or 0) + int(row.get("atoms_rejected") or 0):
            failures.append(f"{lane} atom accounting mismatch")
    if failures:
        print(json.dumps({"status": "failed", "run": str(run), "failures": failures}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"status": "passed", "run": str(run), "semantic_calls": 44, "raw_api_responses": raw_count, "canonical_write_back": False}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
