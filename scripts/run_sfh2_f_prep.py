#!/usr/bin/env python3
"""Generate the offline SFH2.2-F-prep production preflight."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_f_prep.pipeline import build_all  # noqa: E402


if __name__ == "__main__":
    build_all()
    print("SFH2.2-F-prep: offline artifacts generated; provider calls=0")
