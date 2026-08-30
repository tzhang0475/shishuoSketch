#!/usr/bin/env python3
"""Build or replay the SFH2/HIR1 candidate-only projection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from sfh2.pipeline import run  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="sfh2-hir1-v1")
    parser.add_argument("--live", action="store_true", help="use the configured provider; without this flag only cached/offline data is used")
    parser.add_argument("--offline", action="store_true", help="explicitly select cached/offline replay (the default)")
    parser.add_argument("--max-link-calls", type=int, default=None)
    parser.add_argument("--max-pair-calls", type=int, default=None)
    parser.add_argument("--output-root", type=Path, default=None, help="optional isolated derived-output directory")
    args = parser.parse_args()
    if args.live and args.offline:
        parser.error("--live and --offline are mutually exclusive")
    result = run(run_id=args.run_id, live=args.live, max_link_calls=args.max_link_calls, max_pair_calls=args.max_pair_calls, output_root=args.output_root)
    print(json.dumps({"status": "ok", "run_dir": result["run_dir"], "metrics": result["metrics"]}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
