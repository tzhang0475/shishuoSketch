#!/usr/bin/env python3
"""Materialize the frozen W4 story-first Person selection."""

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
WAVE_PATH = Path("data/annotation/person-expansion-wave-4.json")
RANKING_PATH = Path("data/derived/w4-person-expansion-ranking.json")
MATERIALIZATION_PATH = Path("data/derived/person-expansion-wave-4-materialization.json")
REPORT_PATH = Path("docs/w4-person-expansion.md")
ALLOCATION_PATH = Path("data/derived/person-id-allocation-state.json")
W4_PERSON_IDS = {f"person-{index:03d}" for index in range(51, 76)}


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
    materializer.WAVE_ID = "w4-structural-temporal-person-wave-1"
    materializer.WAVE_LABEL = "W4 Structural & Temporal"
    materializer.MATERIALIZATION_STAGE = "w4-structural-temporal-person-materialization"
    materializer.EXPECTED_WAVE_SIZE = 25
    materializer.EVIDENCE_PREFIX = "evidence-w4-person-"
    materializer.MENTION_PREFIX = "shishuo-w4-"
    materializer.ALIAS_PREFIX = "alias-w4-"


def update_allocation_state(root: Path = ROOT) -> dict[str, Any]:
    state_path = root / ALLOCATION_PATH
    state = read(ALLOCATION_PATH)
    wave = read(WAVE_PATH)
    # W4 selection is still recoverable before commit.  Remove only the
    # previous W4 allocation records so a reviewed selection refresh can
    # deterministically reassign the same contiguous W4 range; earlier waves
    # remain immutable and any committed W4 rerun reapplies identical rows.
    by_id = {
        str(item["person_id"]): dict(item)
        for item in state.get("allocations", [])
        if item.get("source_wave_id") != "w4-structural-temporal-person-wave-1"
    }
    for member in sorted(wave.get("members", []), key=lambda item: int(item["rank_at_selection"])):
        record = {
            "person_id": str(member["person_id"]),
            "canonical_name": str(member["preferred_name"]),
            "allocation_basis": "w4_structural_temporal_rank_order",
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
        "W4 allocates person-051 onward from the frozen story-first structural/temporal selection.",
    ]
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state


def reset_w4_projection(root: Path = ROOT) -> None:
    """Remove only W4-owned derived rows before a recoverable rebuild."""

    people_document = read(materializer.PEOPLE_PATH)
    people_document["people"] = [
        item for item in people_document.get("people", [])
        if str(item.get("person_id")) not in W4_PERSON_IDS
    ]
    write(materializer.PEOPLE_PATH, people_document)

    aliases_document = read(materializer.ALIASES_PATH)
    aliases_document["aliases"] = [
        item for item in aliases_document.get("aliases", [])
        if not str(item.get("alias_id", "")).startswith("alias-w4-")
        and not W4_PERSON_IDS.intersection(str(value) for value in item.get("person_ids", []))
    ]
    write(materializer.ALIASES_PATH, aliases_document)

    mentions_document = read(materializer.MENTIONS_PATH)
    mentions_document["mentions"] = [
        item for item in mentions_document.get("mentions", [])
        if not str(item.get("mention_id", "")).startswith("shishuo-w4-")
        and item.get("materialization", {}).get("wave_id") != materializer.WAVE_ID
    ]
    mentions_document["mention_count"] = len(mentions_document["mentions"])
    write(materializer.MENTIONS_PATH, mentions_document)

    evidence_document = read(materializer.EVIDENCE_PATH)
    evidence_document["records"] = [
        item for item in evidence_document.get("records", [])
        if not str(item.get("id", "")).startswith("evidence-w4-person-")
    ]
    write(materializer.EVIDENCE_PATH, evidence_document)

    sketch_document = read(materializer.SKETCH_PATH)
    sketch_document["person_scope"] = [
        str(item.get("person_id"))
        for item in sketch_document.get("records", [])
        if str(item.get("person_id")) not in W4_PERSON_IDS
    ]
    sketch_document["records"] = [
        item for item in sketch_document.get("records", [])
        if str(item.get("person_id")) not in W4_PERSON_IDS
    ]
    write(materializer.SKETCH_PATH, sketch_document)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    configure()
    update_allocation_state(args.root)
    reset_w4_projection(args.root)
    frozen_wave = read(WAVE_PATH)
    result = materializer.build(args.root)
    write(WAVE_PATH, frozen_wave)
    print(
        f"materialized W4 Persons: {result['people_before']} -> {result['people_after']}; "
        f"promoted Mentions={result['promoted_mention_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
