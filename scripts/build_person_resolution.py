#!/usr/bin/env python3
"""Build the ER1 effective Person-resolution and review artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from . import person_resolution
except ImportError:  # direct execution
    import person_resolution


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    result = person_resolution.build(args.root)
    print(
        "built ER1 person resolution: "
        f"{result['mention_count']} Mentions; "
        f"{result['counts']['candidate_for_review_count']} candidate_for_review; "
        f"{result['counts']['unresolved_count']} unresolved"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
