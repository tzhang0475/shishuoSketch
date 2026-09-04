#!/usr/bin/env python3
"""Run or replay the SFH2.2-A2OVB blind boundary-validator pilot."""

from __future__ import annotations

import argparse
from pathlib import Path

from sfh2_a2ovb.common import OUT
from sfh2_a2ovb.pipeline import run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true", help="make one schema probe and only the boundary-cohort calls")
    mode.add_argument("--offline", action="store_true", help="derive results from cached A2OVB boundary responses")
    parser.add_argument("--run-id", default="sfh2-a2ovb-live-v1")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    output = (args.output or OUT) if args.live else (args.output or OUT / "replays" / args.run_id)
    result = run(live=args.live, output=output, run_id=args.run_id)
    print(result["recommendation"].get("recommendation"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
