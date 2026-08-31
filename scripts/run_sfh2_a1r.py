#!/usr/bin/env python3
"""Run the isolated SFH2.2-A1R strict-review repair pilot."""

from __future__ import annotations

import argparse
import json
import sys

from sfh2_a1r.common import canonical_json
from sfh2_a1r.pipeline import run, run_schema_probes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--offline", action="store_true")
    parser.add_argument("--run-id", default="sfh2-a1r-live-v1")
    args = parser.parse_args(argv)
    if args.probe:
        result = run_schema_probes(run_id=args.run_id)
        print(canonical_json(result))
        return 0 if result.get("all_pass") else 1
    result = run(live=args.live, run_id=args.run_id)
    print(json.dumps({"recommendation": result.get("metrics", {}).get("recommendation"), "transport": result.get("transport"), "metrics": result.get("metrics")}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
