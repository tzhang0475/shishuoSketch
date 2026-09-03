#!/usr/bin/env python3
"""Run the offline SFH2.2-A2OT taxonomy audit without provider access."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_a2ot.common import OUT  # noqa: E402
from sfh2_a2ot.pipeline import run  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args(argv)
    summary = run(args.output_dir)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
