#!/usr/bin/env python3
"""Build and freeze the complete HDB2-F occurrence frontier offline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import hdb2_full_frontier_common as common  # noqa: E402


SELECTION = common.ANNOTATION / "hdb2-f-frontier-selection.json"
LEDGER = common.DERIVED / "hdb2-f-occurrence-ledger.json"
CASES = common.DERIVED / "hdb2-f-occurrence-cases.json"


def build(*, write: bool = True) -> tuple[dict, dict, dict]:
    ledger = common.build_ledger()
    selection = common.build_frontier_selection(ledger)
    cases = common.build_cases(ledger, selection)
    if write:
        if SELECTION.is_file():
            existing = common.read_json(SELECTION, {}) or {}
            if existing != selection:
                raise RuntimeError("hdb2_f_frontier_selection_changed")
        else:
            common.write_json(SELECTION, selection)
        common.write_json(LEDGER, ledger)
        common.write_json(CASES, cases)
    return ledger, selection, cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    ledger, selection, cases = build(write=not args.check_only)
    print(common.json.dumps({
        "ledger": ledger.get("counts"),
        "frontier": selection.get("remaining_hdb2_f_live_frontier"),
        "cases": cases.get("occurrence_count"),
        "selection_hash": selection.get("selection_hash"),
        "candidate_only": True,
        "canonical_write_back": False,
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

