#!/usr/bin/env python3
"""Freeze the deterministic HDB2-P1 unresolved identity case set."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from hdb2_p1_common import ANNOTATION, freeze_selection, write_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ANNOTATION / "hdb2-p1-selection.json")
    args = parser.parse_args()
    selection = freeze_selection(args.output)
    print(f"frozen {selection['selected_case_count']} HDB2-P1 identity cases")
    print(f"selection_hash={selection['selection_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
