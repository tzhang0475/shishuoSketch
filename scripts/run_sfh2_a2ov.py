#!/usr/bin/env python3
"""Run or replay the SFH2.2-A2OV conservative reviewer pilot."""

from __future__ import annotations

import argparse
from pathlib import Path

from sfh2_a2ov.common import OUT
from sfh2_a2ov.pipeline import run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true", help="make one probe and the 26 reviewer calls")
    mode.add_argument("--offline", action="store_true", help="derive outputs from the cached A2OV reviewer results")
    parser.add_argument("--run-id", default="sfh2-a2ov-live-v1")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    if args.live:
        output = args.output or OUT
    else:
        output = args.output or OUT / "replays" / args.run_id
    result = run(live=args.live, output=output, run_id=args.run_id)
    print(result["recommendation"].get("recommendation"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
