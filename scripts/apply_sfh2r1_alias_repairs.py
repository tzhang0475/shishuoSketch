#!/usr/bin/env python3
"""Materialize the second, reviewed SFH2R.1 alias authority.

The authority document is the semantic decision.  This command only applies
the named evidence filters/status changes to the active alias registry and
records a reversible before/after audit.  It deliberately does not infer a
new alias, re-score a claim, or create a production Person.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import manual_semantic_authority as authority  # noqa: E402


ALIASES_PATH = ROOT / "data/aliases.json"
OUT = ROOT / "data/generated/sfh2r1"
AUDIT_PATH = OUT / "alias-before-after.json"


def read(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_hash(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _rows(document: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("alias_id")): dict(row)
        for row in document.get("aliases", []) or []
        if isinstance(row, Mapping) and str(row.get("alias_id") or "")
    }


def _already_materialized(document: Mapping[str, Any]) -> bool:
    expected = {str(row.get("alias_id")) for row in authority.second_alias_repairs() if row.get("alias_id")}
    actual = {
        str((row.get("sfh2r1_manual_repair") or {}).get("alias_id"))
        for row in document.get("aliases", []) or []
        if isinstance(row, Mapping) and (row.get("sfh2r1_manual_repair") or {}).get("alias_id")
    }
    return bool(expected) and expected <= actual


def materialize() -> dict[str, Any]:
    current = read(ALIASES_PATH, {}) or {}
    if not isinstance(current, Mapping) or not isinstance(current.get("aliases"), list):
        raise RuntimeError("aliases_document_invalid")
    previous = read(AUDIT_PATH, {}) or {}
    if _already_materialized(current) and isinstance(previous, Mapping) and previous:
        return dict(previous)

    before = json.loads(json.dumps(current, ensure_ascii=False))
    before_hash = file_hash(ALIASES_PATH)
    repaired, records = authority.apply_sfh2r1_alias_repairs(current)

    # Add a second-stage trace without overwriting the first authority trace.
    for record in records:
        alias_id = str(record.get("alias_id") or "")
        after = record.get("after") if isinstance(record.get("after"), Mapping) else {}
        trace = dict(after.get("sfh2r_manual_repair") or {})
        trace["authority"] = authority.authority_reference(authority.AUTHORITY_V2_PATH)
        trace["precedence"] = "sfh2r1_after_sfh2r"
        if isinstance(after, dict):
            after["sfh2r1_manual_repair"] = trace
        for row in repaired.get("aliases", []) or []:
            if isinstance(row, dict) and str(row.get("alias_id") or "") == alias_id:
                row["sfh2r1_manual_repair"] = trace
                break
        record["after"] = json.loads(json.dumps(after, ensure_ascii=False))
        record["authority"] = authority.authority_reference(authority.AUTHORITY_V2_PATH)

    write(ALIASES_PATH, repaired)
    audit = {
        "schema": "sfh2r1-alias-before-after-v1",
        "authority": authority.authority_reference(authority.AUTHORITY_V2_PATH),
        "authority_sha256": file_hash(authority.AUTHORITY_V2_PATH),
        "preceding_authority": authority.authority_reference(authority.AUTHORITY_PATH),
        "before_file_sha256": before_hash,
        "after_file_sha256": file_hash(ALIASES_PATH),
        "before_document": before,
        "records": records,
        "repair_count": len(records),
        "evidence_rows_removed": sum(len(row.get("removed_evidence_ids", []) or []) for row in records),
        "evidence_rows_retained": sum(len(row.get("retained_evidence_ids", []) or []) for row in records),
        "candidate_only": True,
        "canonical_write_back": False,
    }
    write(AUDIT_PATH, audit)
    return audit


if __name__ == "__main__":
    print(json.dumps(materialize(), ensure_ascii=False, indent=2, sort_keys=True))
