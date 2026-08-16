#!/usr/bin/env python3
"""Build X1.2R fact reopening, fact review and citation projections."""

from __future__ import annotations

import json

try:
    from scripts.build_x1_2r import (
        build_citations,
        build_conflicts,
        build_evidence_bundles,
        build_fact_reviews,
        build_participant_review,
    )
except ModuleNotFoundError:
    from build_x1_2r import (
        build_citations,
        build_conflicts,
        build_evidence_bundles,
        build_fact_reviews,
        build_participant_review,
    )


if __name__ == "__main__":
    bundles = build_evidence_bundles()
    participant, identity = build_participant_review(bundles)
    facts, reopen, _ = build_fact_reviews(bundles, participant, identity)
    citations = build_citations()
    conflicts = build_conflicts(participant, identity, facts)
    print(json.dumps({"facts": facts["counts"], "reopened": reopen["counts"], "citations": citations["counts"], "conflicts": conflicts["counts"]}, ensure_ascii=False, indent=2))
