#!/usr/bin/env python3
"""Run the SFH2.2-A2OR clarified occurrence-semantics experiment."""

from __future__ import annotations

import argparse

from sfh2_a2or.pipeline import run


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--offline", action="store_true")
    parser.add_argument("--run-id", default="sfh2-a2or-offline")
    args = parser.parse_args()
    result = run(live=args.live, run_id=args.run_id)
    print({
        "stage": "SFH2.2-A2OR",
        "live": args.live,
        "cases": len(result["cases"]),
        "valid_records": result["evaluation"]["metrics"].get("valid_records"),
        "narrative_function_accuracy": result["evaluation"]["metrics"].get("narrative_function_accuracy"),
        "recommendation": result["recommendation"],
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
