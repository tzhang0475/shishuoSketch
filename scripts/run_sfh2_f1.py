#!/usr/bin/env python3
"""Run or resume the bounded SFH2.2-F1 candidate wave."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_f1.pipeline import run  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true", help="allow the frozen provider calls")
    mode.add_argument("--offline", action="store_true", help="run only the local orchestration path")
    parser.add_argument("--phase-a-limit", type=int, choices=(5,), help="execute the required five-occurrence resume-smoke phase")
    parser.add_argument("--resume", action="store_true", help="restart over the original selection and reuse valid checkpoints")
    parser.add_argument("--run-id", default="sfh2-f1-live-v1", help="external raw-witness namespace")
    args = parser.parse_args(argv)
    metrics = run(
        live=args.live,
        phase_a_limit=args.phase_a_limit,
        resume=args.resume,
        run_id=args.run_id,
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
