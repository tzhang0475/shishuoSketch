#!/usr/bin/env python3
"""Run or deterministically replay SFH1."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from semantic_first.pipeline import replay, run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="sfh1-v1")
    parser.add_argument("--offline-replay", action="store_true")
    parser.add_argument("--story-limit", type=int)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--rebuild-all", action="store_true")
    parser.add_argument("--skip-temporal", action="store_true")
    args = parser.parse_args()
    result = replay(run_id=args.run_id, include_temporal=not args.skip_temporal) if args.offline_replay else run(run_id=args.run_id, live=True, include_temporal=not args.skip_temporal, story_limit=args.story_limit, workers=args.workers, retry_failed=args.retry_failed, rebuild_all=args.rebuild_all)
    print(json.dumps({"run_id": args.run_id, "stories": result["manifest"]["story_count"], "metrics": result["metrics"], "regression": result["regression"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
