#!/usr/bin/env python3
"""Materialize the frozen W3 early Wei--Jin Person wave."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from . import materialize_person_expansion as materializer
except ImportError:  # direct execution
    import materialize_person_expansion as materializer


ROOT = Path(__file__).resolve().parents[1]
WAVE_PATH = Path("data/annotation/person-expansion-wave-3.json")
RANKING_PATH = Path("data/derived/w3-person-expansion-ranking.json")
MATERIALIZATION_PATH = Path("data/derived/person-expansion-wave-3-materialization.json")
REPORT_PATH = Path("docs/w3-early-weijin-expansion.md")
ALLOCATION_PATH = Path("data/derived/person-id-allocation-state.json")
W3_PERSON_IDS = {f"person-{index:03d}" for index in range(36, 51)}


def read(path: Path) -> Any:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def configure() -> None:
    materializer.WAVE_PATH = WAVE_PATH
    materializer.RANKING_PATH = RANKING_PATH
    materializer.RANKING_SNAPSHOT_PATH = RANKING_PATH
    materializer.MATERIALIZATION_PATH = MATERIALIZATION_PATH
    materializer.REPORT_PATH = REPORT_PATH
    materializer.WAVE_ID = "w3-early-weijin-person-wave-1"
    materializer.WAVE_LABEL = "W3 Early Wei–Jin"
    materializer.MATERIALIZATION_STAGE = "w3-early-weijin-person-materialization"
    materializer.EXPECTED_WAVE_SIZE = 15
    materializer.EVIDENCE_PREFIX = "evidence-w3-person-"
    materializer.MENTION_PREFIX = "shishuo-w3-"
    materializer.ALIAS_PREFIX = "alias-w3-"


def update_allocation_state(root: Path = ROOT) -> dict[str, Any]:
    state = read(ALLOCATION_PATH)
    wave = read(WAVE_PATH)
    by_id = {str(item["person_id"]): dict(item) for item in state.get("allocations", [])}
    for member in sorted(wave.get("members", []), key=lambda item: int(item["rank_at_selection"])):
        record = {
            "person_id": str(member["person_id"]),
            "canonical_name": str(member["preferred_name"]),
            "allocation_basis": "w3_early_weijin_rank_order",
            "source_wave_id": str(wave["wave_id"]),
        }
        existing = by_id.get(record["person_id"])
        if existing is not None and existing != record:
            raise ValueError(f"Person ID allocation drift for {record['person_id']}")
        by_id[record["person_id"]] = record
    allocations = sorted(by_id.values(), key=lambda item: item["person_id"])
    expected = [f"person-{index:03d}" for index in range(1, len(allocations) + 1)]
    if [item["person_id"] for item in allocations] != expected:
        raise ValueError("Person ID allocation has a gap or duplicate")
    state["allocations"] = allocations
    state["next_person_sequence"] = len(allocations) + 1
    state["notes"] = [
        "Opaque Person IDs are assigned once and never generated from names or display text.",
        "W3 allocates person-036 onward in frozen chronological selection order.",
    ]
    write(ALLOCATION_PATH, state)
    return state


def reset_w3_projection(root: Path = ROOT) -> None:
    """Rebuild W3-owned generated rows from the frozen manifest.

    This keeps the wrapper recoverable after a provenance-policy correction:
    W3 records are derived artifacts, so removing only this wave's rows before
    a clean materialization is safer than preserving a stale partial output.
    """

    people_path = root / materializer.PEOPLE_PATH
    people_document = read(materializer.PEOPLE_PATH)
    people_document["people"] = [
        item for item in people_document.get("people", [])
        if str(item.get("person_id")) not in W3_PERSON_IDS
    ]
    write(materializer.PEOPLE_PATH, people_document)

    aliases_path = root / materializer.ALIASES_PATH
    aliases_document = read(materializer.ALIASES_PATH)
    aliases_document["aliases"] = [
        item for item in aliases_document.get("aliases", [])
        if not str(item.get("alias_id", "")).startswith("alias-w3-")
        and not any(str(person_id) in W3_PERSON_IDS for person_id in item.get("person_ids", []))
    ]
    write(materializer.ALIASES_PATH, aliases_document)

    mentions_document = read(materializer.MENTIONS_PATH)
    mentions_document["mentions"] = [
        item for item in mentions_document.get("mentions", [])
        if not str(item.get("mention_id", "")).startswith("shishuo-w3-")
        and item.get("materialization", {}).get("wave_id") != materializer.WAVE_ID
    ]
    mentions_document["mention_count"] = len(mentions_document["mentions"])
    write(materializer.MENTIONS_PATH, mentions_document)

    evidence_document = read(materializer.EVIDENCE_PATH)
    evidence_document["records"] = [
        item for item in evidence_document.get("records", [])
        if not str(item.get("id", "")).startswith("evidence-w3-person-")
    ]
    write(materializer.EVIDENCE_PATH, evidence_document)

    sketch_document = read(materializer.SKETCH_PATH)
    sketch_document["person_scope"] = [
        str(item.get("person_id"))
        for item in sketch_document.get("records", [])
        if str(item.get("person_id")) not in W3_PERSON_IDS
    ]
    sketch_document["records"] = [
        item for item in sketch_document.get("records", [])
        if str(item.get("person_id")) not in W3_PERSON_IDS
    ]
    write(materializer.SKETCH_PATH, sketch_document)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    configure()
    update_allocation_state(args.root)
    reset_w3_projection(args.root)
    # Keep the committed W3 selection manifest immutable.  The generic
    # materializer enriches its in-memory wave with production alias and
    # occurrence details for the materialization report; those runtime
    # metrics belong in the derived materialization artifact, not in the
    # frozen selection decision.
    frozen_wave = read(WAVE_PATH)
    result = materializer.build(args.root)
    write(WAVE_PATH, frozen_wave)
    print(
        f"materialized W3 Persons: {result['people_before']} -> {result['people_after']}; "
        f"promoted Mentions={result['promoted_mention_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
