#!/usr/bin/env python3
"""Rebuild and print the deterministic X1.2R audit summary."""

from __future__ import annotations

import json

try:
    from scripts.build_x1_2r import build
except ModuleNotFoundError:
    from build_x1_2r import build


if __name__ == "__main__":
    summary = build()
    print(json.dumps({"stage": summary["stage"], "participant_review": summary["participant_review"], "fact_review": summary["fact_review"], "canonical_delta": summary["canonical_delta"], "hg1_1_ready": summary["hg1_1_ready"]}, ensure_ascii=False, indent=2))
