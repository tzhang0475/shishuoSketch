#!/usr/bin/env python3
"""Portable, source-derived HDB2 grounded-source projection.

This module is deliberately a provenance boundary, not an identity table.
The committed records contain bounded windows copied from registered source
units.  They are used only when the corresponding ignored/local witness is
not available.  The PSL1.2/PSL1.3 parsers still discover mappings from the
text using their normal generic rules.
"""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "data/derived/hdb2-portable-grounded-source-index.json"
SCHEMA = "hdb2-portable-grounded-source-index-v1"
PORTABLE_SOURCE_FORM = "portable_derived"


def stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _read(path: Path) -> Any:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _unit_from_record(record: Mapping[str, Any]) -> dict[str, Any] | None:
    """Adapt one projection record to the existing P1 source-unit shape."""
    ref = str(record.get("source_ref") or "")
    text = str(record.get("evidence_text") or "")
    if not ref or not text:
        return None
    locator = record.get("source_locator")
    if not isinstance(locator, Mapping):
        locator = {}
    return {
        "ref": ref,
        "source_work": str(record.get("source_work") or ""),
        "source_layer": str(record.get("source_layer") or ""),
        "evidence_text": text,
        "source_path": record.get("source_path"),
        "source_sha256": record.get("source_sha256"),
        "locator": dict(locator),
        "source_form": PORTABLE_SOURCE_FORM,
        "story_id": record.get("story_id"),
        "portable_record_id": record.get("record_id"),
        "portable_window_start": record.get("window_start"),
        "portable_window_end": record.get("window_end"),
        "portable_window_sha256": record.get("window_sha256"),
        "portable_source_form": record.get("source_form") or PORTABLE_SOURCE_FORM,
    }


def validate_index(document: Any) -> list[str]:
    """Validate the projection's deterministic/provenance contract.

    This intentionally does not require ``source_path`` to exist: the point
    of the projection is to make a bounded, source-hashed window available in
    a portable checkout where the ignored payload is absent.
    """
    errors: list[str] = []
    if not isinstance(document, Mapping):
        return ["document_not_object"]
    if document.get("schema") != SCHEMA:
        errors.append("schema_invalid")
    if document.get("candidate_only") is not True:
        errors.append("candidate_only_invalid")
    if document.get("canonical_write_back") is not False:
        errors.append("canonical_write_back_invalid")
    records = document.get("records")
    if not isinstance(records, list):
        return sorted(set([*errors, "records_not_array"]))
    if document.get("record_count") != len(records):
        errors.append("record_count_invalid")
    if document.get("index_hash") != index_fingerprint(document):
        errors.append("index_hash_invalid")
    seen: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            errors.append(f"record_not_object:{index}")
            continue
        record_id = str(record.get("record_id") or "")
        if not record_id or record_id in seen:
            errors.append(f"record_id_invalid:{index}")
        seen.add(record_id)
        for key in (
            "source_ref", "source_work", "source_layer", "evidence_text",
            "source_sha256", "source_form", "source_locator", "window_start",
            "window_end", "window_sha256", "window_basis",
        ):
            if key not in record or record.get(key) in (None, ""):
                errors.append(f"record_field_missing:{index}:{key}")
        source_hash = str(record.get("source_sha256") or "")
        if source_hash and not re.fullmatch(r"[0-9a-f]{64}", source_hash):
            errors.append(f"source_sha256_invalid:{index}")
        text = str(record.get("evidence_text") or "")
        window_hash = str(record.get("window_sha256") or "")
        if window_hash != hashlib.sha256(text.encode("utf-8")).hexdigest():
            errors.append(f"window_sha256_invalid:{index}")
        try:
            start = int(record.get("window_start"))
            end = int(record.get("window_end"))
        except (TypeError, ValueError):
            errors.append(f"window_offsets_invalid:{index}")
        else:
            if start < 0 or end < start or end - start != len(text):
                errors.append(f"window_offsets_invalid:{index}")
    return sorted(set(errors))


@lru_cache(maxsize=4)
def load_portable_source_units(path: Path = INDEX_PATH) -> list[dict[str, Any]]:
    """Load and validate the committed projection without requiring payloads."""
    document = _read(path)
    if validate_index(document):
        return []
    result: list[dict[str, Any]] = []
    for record in document.get("records", []) or []:
        if not isinstance(record, Mapping):
            continue
        unit = _unit_from_record(record)
        if unit:
            result.append(unit)
    return sorted(result, key=lambda row: (str(row.get("ref")), str(row.get("portable_record_id"))))


def _is_portable(unit: Mapping[str, Any]) -> bool:
    return str(unit.get("source_form") or "") == PORTABLE_SOURCE_FORM or bool(unit.get("portable_record_id"))


def _unit_preference(unit: Mapping[str, Any]) -> tuple[int, int, str]:
    """Prefer a physical registered witness over a derived window."""
    return (
        1 if not _is_portable(unit) else 0,
        len(str(unit.get("evidence_text") or "")),
        str(unit.get("source_form") or ""),
    )


def merge_source_units(
    physical_units: Sequence[Mapping[str, Any]],
    portable_units: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Merge physical and portable units, preferring physical by source ref.

    A source ref is the stable identity used by the existing rescue parsers.
    In a full checkout the physical unit wins.  In portable CI the same ref is
    supplied by the committed window, so parser code and provenance fields
    remain identical across environments.
    """
    by_ref: dict[str, dict[str, Any]] = {}
    for raw in [*(physical_units or []), *(portable_units or load_portable_source_units())]:
        unit = dict(raw)
        ref = str(unit.get("ref") or unit.get("source_ref") or "")
        if not ref or not str(unit.get("evidence_text") or ""):
            continue
        unit["ref"] = ref
        current = by_ref.get(ref)
        if current is None or _unit_preference(unit) > _unit_preference(current):
            by_ref[ref] = unit
    return sorted(by_ref.values(), key=lambda row: (str(row.get("source_work")), str(row.get("ref"))))


def index_fingerprint(document: Mapping[str, Any]) -> str:
    return stable_hash({key: value for key, value in document.items() if key != "index_hash"})


__all__ = [
    "INDEX_PATH",
    "PORTABLE_SOURCE_FORM",
    "ROOT",
    "SCHEMA",
    "index_fingerprint",
    "load_portable_source_units",
    "merge_source_units",
    "stable_hash",
    "validate_index",
]
