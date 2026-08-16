#!/usr/bin/env python3
"""Build the deterministic X1.1 Story candidate universe.

The pool starts from the global PersonStory boundary rather than inventing a
second corpus.  Every out-of-scope Story is audited; only source-backed,
non-disputed, identity-linked entries become qualified candidates.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

try:
    from scripts.x1_1_common import (
        EPOCH,
        POOL_PATH,
        SEED,
        SOURCE_GRAPH_VERSION,
        SOURCE_ML_VERSION,
        build_context,
        make_candidate_record,
        source_hashes,
        write,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from x1_1_common import (
        EPOCH,
        POOL_PATH,
        SEED,
        SOURCE_GRAPH_VERSION,
        SOURCE_ML_VERSION,
        build_context,
        make_candidate_record,
        source_hashes,
        write,
    )


def build() -> dict[str, Any]:
    context = build_context()
    global_story_ids = sorted(context["links_by_story"], key=lambda story_id: (context["entries"].get(story_id, {}).get("global_ordinal", 10**9), story_id))
    out_of_scope_ids = [story_id for story_id in global_story_ids if story_id not in context["production_story_ids"]]
    records = [make_candidate_record(context, story_id) for story_id in out_of_scope_ids]
    records.sort(key=lambda row: (int(row["global_ordinal"]), str(row["story_id"])))
    qualified = [row for row in records if row["eligible"]]
    rejected = [row for row in records if not row["eligible"]]
    return {
        "schema": 1,
        "stage": "x1-1-candidate-pool",
        "selection_epoch": EPOCH,
        "source_graph_version": SOURCE_GRAPH_VERSION,
        "source_ml_version": SOURCE_ML_VERSION,
        "research_only": True,
        "candidate_universe": {
            "basis": "global_person_story_index_outside_published_story_scope",
            "global_person_story_link_count": len(context["links"]),
            "published_story_scope_count": len(context["production_story_ids"]),
            "published_person_story_link_count": sum(
                1 for link in context["links"] if link.get("entry_id") in context["production_story_ids"]
            ),
            "out_of_scope_person_story_link_count": sum(
                1 for link in context["links"] if link.get("entry_id") not in context["production_story_ids"]
            ),
            "out_of_scope_story_count": len(out_of_scope_ids),
            "out_of_scope_story_ids": out_of_scope_ids,
            "candidate_pool_seed": SEED,
        },
        "qualification_policy": {
            "required": [
                "canonical source entry exists and has a stable hash",
                "Story is outside the current published production scope",
                "punctuation record is present and not disputed",
                "at least one production PersonStory identity route exists",
                "at least one local Evidence reference exists",
            ],
            "reader_publication_is_separate_gate": True,
            "person_story_is_not_participation": True,
            "rejected_candidates_are_not_negative_historical_facts": True,
        },
        "source_artifact_hashes": source_hashes(),
        "counts": {
            "audited_story_count": len(records),
            "qualified_story_count": len(qualified),
            "rejected_story_count": len(rejected),
            "qualified_link_count": sum(
                len(context["links_by_story"].get(row["story_id"], [])) for row in qualified
            ),
            "rejection_reasons": dict(sorted(Counter(
                reason for row in rejected for reason in row["rejection_reasons"]
            ).items())),
        },
        "records": records,
        "policy": "This pool is an X1.1 research selection input. It does not add Story nodes to HG0 or modify the 143-Story publication scope.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(POOL_PATH))
    args = parser.parse_args()
    document = build()
    write(Path(args.output), document)
    print(json.dumps({
        "stage": document["stage"],
        "audited": document["counts"]["audited_story_count"],
        "qualified": document["counts"]["qualified_story_count"],
        "rejected": document["counts"]["rejected_story_count"],
        "output": args.output,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
