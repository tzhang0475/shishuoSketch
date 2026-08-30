#!/usr/bin/env python3
"""Run the bounded SFH2.2-P semantic identity-resolution pilot."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sfh2_2p.pipeline import main


if __name__ == "__main__":
    raise SystemExit(main())
