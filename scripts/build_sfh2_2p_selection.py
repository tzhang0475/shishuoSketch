#!/usr/bin/env python3
"""Freeze the SFH2.2-P occurrence selection before any provider call."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_2p.common import OUT, SELECTION_PATH, write_json
from sfh2_2p.selection import freeze_selection


def main() -> int:
    selection = freeze_selection(SELECTION_PATH)
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "selection.json", selection)
    write_json(OUT / "selection-hash.json", {
        "schema": "sfh2-2p-selection-hash-v1",
        "selection_hash": selection.get("selection_hash"),
        "case_count": selection.get("case_count"),
        "gold_case_count": selection.get("gold_case_count"),
        "blind_case_count": selection.get("blind_case_count"),
        "candidate_only": True,
        "canonical_write_back": False,
    })
    print(json.dumps({key: selection.get(key) for key in ("case_count", "gold_case_count", "blind_case_count", "selection_hash", "selection_missing_specs")}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
