#!/usr/bin/env python3
"""Build/freeze the HDB2-P2T occurrence-level integration input."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hdb2_p2t_common as common  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=common.DERIVED / "hdb2-p2t-occurrence-cases.json")
    parser.add_argument("--selection", type=Path, default=common.ANNOTATION / "hdb2-p2t-occurrence-selection.json")
    parser.add_argument("--refresh-context", action="store_true", help="refresh only additive registered-evidence context after a boundary validation fix")
    args = parser.parse_args()
    cases = common.build_cases()
    if args.cases.is_file() and not args.refresh_context:
        if common.read_json(args.cases, {}) != cases:
            raise SystemExit("p2t_occurrence_cases_projection_changed")
    else:
        if args.refresh_context and args.selection.is_file():
            existing_selection = common.read_json(args.selection, {}) or {}
            if existing_selection != common.build_selection(cases):
                raise SystemExit("p2t_frozen_selection_would_change")
        common.write_json(args.cases, cases)
    selection = common.freeze_selection(args.selection, cases)
    print(f"occurrences={selection['occurrence_count']}")
    print(f"selection_hash={selection['selection_hash']}")
    print(f"p1_1_excluded={len(selection['p1_1_excluded_occurrence_ids'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
