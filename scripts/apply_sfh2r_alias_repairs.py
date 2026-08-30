#!/usr/bin/env python3
"""Materialize the reviewed SFH2R alias overlay into the active alias index.

The semantic decisions live in
``data/annotation/sfh2r-manual-semantic-authority.json``.  This command only
filters the explicitly named evidence rows and records a before/after audit;
it does not infer, score, or expand an identity claim.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import manual_semantic_authority as authority  # noqa: E402


ALIASES_PATH = ROOT / "data/aliases.json"
OUT = ROOT / "data/generated/sfh2r"
AUDIT_PATH = OUT / "alias-before-after.json"


def read(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep the active registry's established object order stable.  The
    # semantic audit artifacts may be sorted independently, but a reviewed
    # repair should not create a repository-wide formatting diff.
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _already_materialized(document: dict[str, Any]) -> bool:
    expected = {
        str(row.get("alias_id"))
        for row in authority.alias_repairs()
        if row.get("alias_id")
    }
    actual = {
        str((row.get("sfh2r_manual_repair") or {}).get("alias_id"))
        for row in document.get("aliases", []) or []
        if isinstance(row, dict) and (row.get("sfh2r_manual_repair") or {}).get("alias_id")
    }
    return bool(expected) and expected <= actual


def materialize(*, force: bool = False) -> dict[str, Any]:
    current = read(ALIASES_PATH, {}) or {}
    if not isinstance(current, dict) or not isinstance(current.get("aliases"), list):
        raise RuntimeError("aliases_document_invalid")
    if _already_materialized(current) and not force:
        audit = read(AUDIT_PATH, {}) or {}
        if audit:
            return audit
        return {
            "schema": "sfh2r-alias-before-after-v1",
            "authority": authority.authority_reference(),
            "idempotent_replay": True,
            "records": [],
            "candidate_only": True,
            "canonical_write_back": False,
        }
    repaired, records = authority.apply_alias_repairs(current)
    write(ALIASES_PATH, repaired)
    audit = {
        "schema": "sfh2r-alias-before-after-v1",
        "authority": authority.authority_reference(),
        "repair_count": len(records),
        "records": records,
        "idempotent_replay": False,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    write(AUDIT_PATH, audit)
    return audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="reapply against an un-repaired input only")
    args = parser.parse_args()
    result = materialize(force=args.force)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
