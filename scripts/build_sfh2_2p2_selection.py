"""Freeze the answer-blind SFH2.2-P2 occurrence selection."""

from __future__ import annotations

import argparse
import sys

from sfh2_2p2.common import OUT, load_inputs, write_architecture_freeze, write_json
from sfh2_2p2.selection import build_selection, freeze_selection


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="rebuild the not-yet-authoritative selection before freezing")
    args = parser.parse_args()
    if args.refresh:
        selection = build_selection(load_inputs())
        from sfh2_2p2.common import SELECTION_PATH
        write_json(SELECTION_PATH, selection)
    else:
        selection = freeze_selection()
    # The annotation file is the frozen human-facing source; this generated
    # copy keeps the isolated pilot directory self-contained for replay and
    # validators.
    write_json(OUT / "selection.json", selection)
    write_json(OUT / "selection-hash.json", {
        "schema": "sfh2-2p2-selection-hash-v1",
        "selection_hash": selection.get("selection_hash"),
        "selection_seed": selection.get("selection_seed"),
        "case_count": selection.get("case_count"),
        "gold_case_count": 0,
        "blind_case_count": selection.get("blind_case_count"),
        "gold_fields_present": False,
    })
    write_architecture_freeze(str(selection.get("selection_hash")))
    print(f"SFH2.2-P2 frozen selection: {selection.get('case_count')} cases")
    print(f"selection_hash={selection.get('selection_hash')}")
    print(f"eligible={selection.get('eligible_count')} excluded={selection.get('excluded_count')}")
    print(f"strata={selection.get('stratum_counts')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
