#!/usr/bin/env python3
"""Build X1.2R participant and identity review projections."""

from __future__ import annotations

import json

try:
    from scripts.build_x1_2r import build_evidence_bundles, build_participant_review
except ModuleNotFoundError:
    from build_x1_2r import build_evidence_bundles, build_participant_review


if __name__ == "__main__":
    bundles = build_evidence_bundles()
    participant, identity = build_participant_review(bundles)
    print(json.dumps({"participant": participant["counts"], "identity": identity["counts"]}, ensure_ascii=False, indent=2))
