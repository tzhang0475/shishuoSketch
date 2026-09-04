#!/usr/bin/env python3
"""Run the offline SFH2.2-A2OS target-alignment audit."""

from __future__ import annotations

import argparse
from pathlib import Path

from sfh2_a2os.common import OUT
from sfh2_a2os.pipeline import run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="required; A2OS has no live mode")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    if not args.offline:
        parser.error("A2OS is offline-only; pass --offline")
    documents = run(args.output)
    metrics = documents["metrics.json"]
    print(f"A2OS offline audit: {metrics['case_count']} cases; provider_calls={metrics['provider_calls']}; candidates={metrics['gold_review_candidate_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
