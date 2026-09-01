#!/usr/bin/env python3
"""Run the isolated SFH2.2-A2R cached dual-semantic adjudication."""

from __future__ import annotations

import argparse
import json
import sys

from sfh2_a2r import pipeline


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--offline", action="store_true")
    parser.add_argument("--run-id", default="sfh2-a2r-offline")
    args = parser.parse_args()
    live = bool(args.live)
    try:
        result = pipeline.run(live=live, run_id=args.run_id)
    except Exception as exc:
        print(f"SFH2.2-A2R failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"output": result.get("output"), "recommendation": result.get("recommendation"), "transport": result.get("transport")}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
