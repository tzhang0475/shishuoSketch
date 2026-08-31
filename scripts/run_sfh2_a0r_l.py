#!/usr/bin/env python3
"""Prepare, probe, or run the isolated SFH2.2-A0R-L pilot."""

from __future__ import annotations

import argparse
import json

from sfh2_a0r_l.common import canonical_json
from sfh2_a0r_l.pipeline import prepare, prepare_and_probe, run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--offline", action="store_true")
    parser.add_argument("--run-id", default="sfh2-a0r-l-offline")
    args = parser.parse_args(argv)
    if args.prepare:
        result = prepare()
        print(canonical_json({"regression_cases": len(result["regression"]["cases"]), "challenge_cases": len(result["challenge"]["cases"]), "challenge_stories": sorted({row.get("story_id") for row in result["challenge"]["cases"]}), "architecture_hash": result["architecture"].get("architecture_hash")}))
        return 0
    if args.probe:
        result = prepare_and_probe()
        print(canonical_json(result))
        return 0 if result.get("live_provider_available") else 2
    result = run(live=args.live, run_id=args.run_id)
    print(json.dumps({"recommendation": result["recommendation"], "metrics": result["metrics"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
