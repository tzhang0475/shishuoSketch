#!/usr/bin/env python3
"""Run HNG2's bounded two-wave projection.

The command is intentionally offline by default.  A future approved-network
runner may use ``--allow-llm`` to expose residual cases to a constrained
identity-assist client; this script still refuses to create canonical data.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_hng2 import build  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded HNG2 frontier growth")
    parser.add_argument("--allow-llm", action="store_true", help="record residual identity-assist eligibility; no automatic canonical write-back")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    build(allow_llm=args.allow_llm, quiet=args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
