#!/usr/bin/env python3
"""Run the complete X1.2R pipeline and emit its extension-only release."""

from __future__ import annotations

import json

try:
    from scripts.build_x1_2r import build
except ModuleNotFoundError:
    from build_x1_2r import build


if __name__ == "__main__":
    summary = build()
    print(json.dumps({"stage": summary["stage"], "canonical_delta": summary["canonical_delta"], "hg1_1_ready": summary["hg1_1_ready"]}, ensure_ascii=False, indent=2))
