#!/usr/bin/env python3
"""Build the bounded portable source projection used by HDB2 rescue.

Run this builder in a full-source checkout.  Selection is based only on
generic identity-bearing historical syntax, never on the expected answers of
PSL regression tests.  Each output row retains the original registered
source ref/path/hash plus an exact bounded text window.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hdb2_p1_common as p1  # noqa: E402
from hdb2_portable_grounded_source import (  # noqa: E402
    INDEX_PATH,
    PORTABLE_SOURCE_FORM,
    SCHEMA,
    index_fingerprint,
    stable_hash,
)


# These are retrieval/serialization patterns only.  They identify compact
# regions likely to contain source-grounded identity evidence.  No pattern
# names a person, and no extracted candidate is stored in this projection.
IDENTITY_PATTERN = re.compile(
    r"[\u3400-\u9fff]{1,8}\s*(?:字|名|諱|號|号|即)\s*[\u3400-\u9fff]{1,8}(?:\s*(?:一人|也))?"
)
KINSHIP_PATTERN = re.compile(
    r"[\u3400-\u9fff]{1,8}(?:父|母|兄|弟|子|女|妻|婿)[\u3400-\u9fff]{1,8}"
)
OFFICE_APPOINTMENT_PATTERN = re.compile(
    r"[\u3400-\u9fff]{1,8}\s*(?:爲|為|拜|除|任|授|遷|迁|轉|转|領|领|兼)\s*"
    r"[\u3400-\u9fff]{1,8}(?:尹|太守|長史|尚書|將軍|司空|僕射|廷尉|侍中|太傅|中丞|主簿|刺史|掾|光祿|光禄)"
)
TITLE_NAME_PATTERN = re.compile(
    r"[\u3400-\u9fff]{1,8}(?:尹|太守|長史|尚書|將軍|司空|僕射|廷尉|侍中|太傅|中丞|主簿|刺史|掾|光祿|光禄)"
    r"[\s，,:：；;、()（）〔〕「」『』]*[\u3400-\u9fff]{2,4}"
    r"[\s，,:：；;、()（）〔〕「」『』]*(?:已見|已见|一人|也|字|即|別傳|别传|傳曰|传曰)"
)
RULER_CONTEXT_PATTERN = re.compile(
    r"[\u3400-\u9fff]{1,4}帝|朕|寡人|陛下"
)

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("identity_marker", IDENTITY_PATTERN),
    ("kinship_marker", KINSHIP_PATTERN),
    ("office_appointment", OFFICE_APPOINTMENT_PATTERN),
    ("title_name_statement", TITLE_NAME_PATTERN),
    ("ruler_context", RULER_CONTEXT_PATTERN),
)
WINDOW_BEFORE = 280
WINDOW_AFTER = 280
MAX_WINDOWS_PER_UNIT = 4
BASIS_PRIORITY = {
    "title_name_statement": 0,
    "identity_marker": 1,
    "office_appointment": 2,
    "ruler_context": 3,
    "kinship_marker": 4,
}
MAX_OVERLAP_RATIO = 0.65


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _window(text: str, start: int, end: int) -> tuple[str, int, int]:
    left = max(0, int(start) - WINDOW_BEFORE)
    right = min(len(text), int(end) + WINDOW_AFTER)
    window = text[left:right]
    leading = len(window) - len(window.lstrip())
    window = window.strip()
    left += leading
    right = left + len(window)
    return window, left, right


def _record(unit: Mapping[str, Any], text: str, start: int, end: int, basis: str) -> dict[str, Any] | None:
    window, window_start, window_end = _window(text, start, end)
    ref = str(unit.get("ref") or "")
    if not ref or not window:
        return None
    source_locator = unit.get("locator") if isinstance(unit.get("locator"), Mapping) else {}
    material = {
        "source_ref": ref,
        "window_start": window_start,
        "window_end": window_end,
        "window_sha256": _sha256_text(window),
        "window_basis": basis,
    }
    return {
        "record_id": f"portable-grounded-window-{stable_hash(material)[:24]}",
        "source_ref": ref,
        "source_work": unit.get("source_work"),
        "source_layer": unit.get("source_layer"),
        "evidence_text": window,
        "source_locator": dict(source_locator),
        "source_path": unit.get("source_path"),
        "source_sha256": unit.get("source_sha256"),
        "source_form": PORTABLE_SOURCE_FORM,
        "story_id": unit.get("story_id"),
        "window_start": window_start,
        "window_end": window_end,
        "window_sha256": material["window_sha256"],
        "window_basis": basis,
        "registered_source_form": unit.get("source_form"),
    }


def _candidate_records(unit: Mapping[str, Any]) -> list[dict[str, Any]]:
    text = str(unit.get("evidence_text") or "")
    records: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for basis, pattern in PATTERNS:
        for match in pattern.finditer(text):
            window, start, end = _window(text, match.start(), match.end())
            # The same short passage often satisfies more than one generic
            # retrieval pattern.  Store it once; the first pattern in the
            # fixed PATTERNS order supplies the deterministic audit label.
            key = (start, end)
            if not window or key in seen:
                continue
            seen.add(key)
            row = _record(unit, text, match.start(), match.end(), basis)
            if row:
                records.append(row)
    # Keep deterministic and bounded coverage even for large biographies.
    # Different generic patterns frequently select almost the same passage;
    # retain one representative rather than serializing that text repeatedly.
    ranked = sorted(records, key=lambda row: (
        BASIS_PRIORITY.get(str(row.get("window_basis") or ""), 99),
        int(row.get("window_start") or 0),
        str(row.get("record_id") or ""),
    ))
    selected: list[dict[str, Any]] = []
    for row in ranked:
        start = int(row.get("window_start") or 0)
        end = int(row.get("window_end") or start)
        length = max(1, end - start)
        overlaps = False
        for other in selected:
            other_start = int(other.get("window_start") or 0)
            other_end = int(other.get("window_end") or other_start)
            overlap = max(0, min(end, other_end) - max(start, other_start))
            if overlap / max(1, min(length, other_end - other_start)) >= MAX_OVERLAP_RATIO:
                overlaps = True
                break
        if overlaps:
            continue
        selected.append(row)
        if len(selected) >= MAX_WINDOWS_PER_UNIT:
            break
    return sorted(selected, key=lambda row: (
        int(row.get("window_start") or 0),
        str(row.get("window_basis") or ""),
        str(row.get("record_id") or ""),
    ))


def _requires_portable_projection(unit: Mapping[str, Any]) -> bool:
    """Keep the fallback focused on payload-backed registered witnesses.

    The committed processed Shishuo/劉注/三國志/通鑑 units are already
    available to Pages CI through ``p1.build_source_index``.  Jianshu and
    Jinshu units point at ignored/downloaded payloads, so only those source
    families need a derived window fallback.  This is a provenance/path
    decision, not a person- or regression-specific selection.
    """
    source_path = str(unit.get("source_path") or "")
    source_work = str(unit.get("source_work") or "")
    return source_path.startswith("sources/downloads/") or source_work in {"箋疏", "箋疏正文", "晉書"}


def build_projection(units: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    source_units = list(units if units is not None else p1.build_source_index())
    records: list[dict[str, Any]] = []
    for unit in source_units:
        if not _requires_portable_projection(unit):
            continue
        records.extend(_candidate_records(unit))
    unique: dict[str, dict[str, Any]] = {}
    for row in records:
        unique.setdefault(str(row["record_id"]), row)
    ordered = sorted(unique.values(), key=lambda row: (
        str(row.get("source_work") or ""),
        str(row.get("source_ref") or ""),
        int(row.get("window_start") or 0),
        str(row.get("window_basis") or ""),
        str(row.get("record_id") or ""),
    ))
    document: dict[str, Any] = {
        "schema": SCHEMA,
        "purpose": "portable derived source windows for HDB2 PSL1.2/PSL1.3 grounded rescue",
        "source_selection": "payload-backed registered witnesses plus generic identity/kinship/office/ruler syntax; no expected identity mappings",
        "candidate_only": True,
        "canonical_write_back": False,
        "record_count": len(ordered),
        "records": ordered,
        "index_hash": None,
    }
    document["index_hash"] = index_fingerprint(document)
    return document


def write_projection(path: Path = INDEX_PATH, units: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    document = build_projection(units)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=INDEX_PATH)
    parser.add_argument("--check", action="store_true", help="build and compare without writing")
    args = parser.parse_args()
    document = build_projection()
    if args.check:
        if not args.output.is_file():
            print(f"missing:{args.output}")
            return 1
        current = json.loads(args.output.read_text(encoding="utf-8"))
        if current != document:
            print("portable_grounded_source_index_changed")
            return 1
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"path": str(args.output), "record_count": document["record_count"], "index_hash": document["index_hash"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
