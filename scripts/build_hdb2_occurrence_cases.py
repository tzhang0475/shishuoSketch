#!/usr/bin/env python3
"""Build and freeze the HDB2-P1.1 occurrence-level input projection.

This is an offline projection of immutable HDB1/HDB2-P1 observations.  It
does not retrieve, call a model, allocate Person IDs, or write canonical data.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hdb2_occurrence_common as common  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=common.DERIVED / "hdb2-p1-1-occurrence-cases.json")
    parser.add_argument("--selection", type=Path, default=common.ANNOTATION / "hdb2-p1-1-occurrence-selection.json")
    args = parser.parse_args()

    cases = common.build_cases()
    if args.cases.is_file() and common.read_json(args.cases, {}) != cases:
        raise SystemExit("occurrence_cases_projection_changed")
    if not args.cases.is_file():
        common.write_json(args.cases, cases)
    selection = common.freeze_selection(args.selection, cases)
    print(f"occurrences={selection['occurrence_count']}")
    print(f"selection_hash={selection['selection_hash']}")
    print(f"frozen_before_live={selection['frozen_before_live']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
