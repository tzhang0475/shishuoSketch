#!/usr/bin/env python3
"""Materialize the offline SFH2.2-F1RP reviewed overlay and policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_f1rp.audit import OUT, run  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--no-repository-overlays", action="store_true", help="write only the supplied output directory")
    args = parser.parse_args(argv)
    documents = run(args.output, materialize_repository_overlays=not args.no_repository_overlays)
    print(json.dumps(documents["metrics.json"], ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
