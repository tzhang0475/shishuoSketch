#!/usr/bin/env python3
"""Freeze the controlled SFH2.2-A0 selection and evaluation-only gold."""

from sfh2_a0.common import OUT, architecture_freeze, load_inputs, stable_hash, write_json
from sfh2_a0.selection import freeze_gold, freeze_selection


def main() -> int:
    inputs = load_inputs()
    selection = freeze_selection(inputs=inputs)
    # v2 is an explicit A0 contract transition: v1 provider output exposed a
    # formatting gap, so the complete pilot is rerun under the new freeze.
    gold = freeze_gold(allow_version_transition=True)
    write_json(OUT / "selection.json", selection)
    write_json(OUT / "selection-hash.json", {"schema": "sfh2-a0-selection-hash-v1", "selection_hash": selection.get("selection_hash")})
    write_json(OUT / "evaluation-gold.json", gold)
    write_json(OUT / "architecture-freeze.json", architecture_freeze(selection.get("selection_hash", "")))
    print({"case_count": selection.get("case_count"), "selection_hash": selection.get("selection_hash"), "gold_hash": stable_hash(gold)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
