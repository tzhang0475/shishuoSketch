#!/usr/bin/env python3
"""Offline FIND/OPEN helper for a frozen HDB2-P1 identity case."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import build_hng0_2 as hng02  # noqa: E402
from hdb2_p1_common import build_source_index, read_json, search_case  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id")
    parser.add_argument("--selection", type=Path, default=ROOT / "data/annotation/hdb2-p1-selection.json")
    parser.add_argument("--round", type=int, default=1)
    parser.add_argument("--used-ref", action="append", default=[])
    args = parser.parse_args()
    selection = read_json(args.selection, {}) or {}
    case = next((row for row in selection.get("cases", []) if row.get("case_id") == args.case_id), None)
    if case is None:
        raise SystemExit(f"unknown_case:{args.case_id}")
    result = search_case(case, build_source_index(), hng02.person_catalog(), used_refs=set(args.used_ref), max_passages=4, max_chars=2000)
    print(json.dumps({"case_id": args.case_id, "round": args.round, **result}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
