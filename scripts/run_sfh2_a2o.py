#!/usr/bin/env python3
"""Run or replay the isolated SFH2.2-A2O occurrence-function pilot."""

from __future__ import annotations

import argparse

from sfh2_a2o.pipeline import run


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--offline", action="store_true")
    parser.add_argument("--run-id", default="sfh2-a2o-offline")
    args = parser.parse_args()
    result = run(live=args.live, run_id=args.run_id)
    print({
        "pilot": "SFH2.2-A2O",
        "live": args.live,
        "cases": len(result["cases"]),
        "valid_occurrence_records": result["evaluation"].get("metrics", {}).get("valid_occurrence_records"),
        "narrative_function_accuracy": result["evaluation"].get("metrics", {}).get("narrative_function_accuracy"),
        "recommendation": result["recommendation"],
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
