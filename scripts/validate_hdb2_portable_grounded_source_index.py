#!/usr/bin/env python3
"""Validate the committed portable HDB2 grounded-source projection."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from hdb2_portable_grounded_source import INDEX_PATH, validate_index  # noqa: E402


def main() -> int:
    path = INDEX_PATH
    document = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    errors = validate_index(document)
    result = {
        "path": str(path.relative_to(ROOT)),
        "record_count": document.get("record_count") if isinstance(document, dict) else None,
        "errors": errors,
        "status": "ok" if not errors else "error",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
