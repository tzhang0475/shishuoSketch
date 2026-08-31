#!/usr/bin/env python3
"""Run the isolated SFH2.2-A2 independent semantic audit."""

from __future__ import annotations

import argparse

from sfh2_a2.pipeline import run


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--offline", action="store_true")
    parser.add_argument("--run-id", default="sfh2-a2-offline")
    args = parser.parse_args()
    result = run(live=args.live, run_id=args.run_id)
    print({"pilot": "SFH2.2-A2", "live": args.live, "historian_a_cached": result["metrics"].get("historian_a_cached_records"), "historian_b_valid": result["metrics"].get("historian_b_valid_records"), "adjudicator_calls": result["metrics"].get("adjudicator_calls"), "recommendation": result["recommendation"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
