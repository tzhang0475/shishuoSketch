#!/usr/bin/env python3
"""Build only the deterministic X1.2R Story-local Jianshu evidence layer."""

from __future__ import annotations

import json

try:
    from scripts.build_x1_2r import build_evidence_bundles
except ModuleNotFoundError:
    from build_x1_2r import build_evidence_bundles


if __name__ == "__main__":
    document = build_evidence_bundles()
    print(json.dumps({"stage": document["stage"], "stories": document["scope"]["story_count"]}, ensure_ascii=False, indent=2))
