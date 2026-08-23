#!/usr/bin/env python3
"""Reset generated SRM0.4A/0.4B run results without touching source data."""

from __future__ import annotations

import sys

SCRIPT_DIR = __import__("pathlib").Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from srm0_4b_common import reset_srm0_4_results  # noqa: E402


def main() -> int:
    removed = reset_srm0_4_results()
    print("SRM0.4 generated results reset")
    for path in removed:
        print(f"- removed: {path}")
    print("- status: data/generated/srm0/srm0-4-status.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
