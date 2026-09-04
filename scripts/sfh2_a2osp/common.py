"""Frozen inputs and structural helpers for SFH2.2-A2OSP.

This stage deliberately consumes the immutable A2OS/A2OR artifacts.  It may
read the active reviewed Gold after the two authorized A2OSP mutations, but it
never regenerates provider results or modifies historical experiment output.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/generated/sfh2-a2osp"
A2O_ROOT = ROOT / "data/generated/sfh2-a2o"
A2OT_ROOT = ROOT / "data/generated/sfh2-a2ot"
A2OR_ROOT = ROOT / "data/generated/sfh2-a2or"
A2OS_ROOT = ROOT / "data/generated/sfh2-a2os"
GOLD_PATH = ROOT / "data/annotation/sfh2-a2o-evaluation-gold.json"
AUTHORITY_PATH = ROOT / "data/annotation/sfh2-a2osp-human-semantic-authority.json"
IDENTITY_MANIFEST_PATH = ROOT / "data/frozen/sfh2/identity-v1/manifest.json"
MENTIONS_PATH = ROOT / "data/generated/sfh1/validated-mentions.json"

BASELINE_COMMIT = "5f16de1729950536e6c460def301042d2f4df8ea"
PREVIOUS_GOLD_SHA256 = "498dd1df68c5f99b80651ec1fad58676d0c24e7a6b624c484d89dd6218844f28"
FROZEN_SC1_SHA256 = "cc82c6738fcbf4fc14c12005a459048e71ce329492867d0910562fc6fdfda0d8"
CURRENT_SC1_SHA256 = "b916530264285dd7fa1d2e27a7a1dff8cd2ed794dfb3b84985881f8f209d8f6a"
IDENTITY_MANIFEST_SHA256 = "f60e4eb84c5af10d644ac09dbcbdfba93cc435660868c3e38486563604dcc95e"
CASE_COUNT = 26
CASE_QI = "sfh2-a0-57d1fc3c0492b21ee1f4"
CASE_GU = "sfh2-a0r-l-challenge-f245371d8f0cdf9c8773"
EXPECTED_CHANGED_CASES = (CASE_QI, CASE_GU)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text(value: Any) -> str:
    return str(value or "").strip()


def rows(document: Any, key: str = "records") -> list[dict[str, Any]]:
    if isinstance(document, list):
        return [dict(row) for row in document if isinstance(row, Mapping)]
    if isinstance(document, Mapping) and isinstance(document.get(key), list):
        return [dict(row) for row in document[key] if isinstance(row, Mapping)]
    return []


def by_case(document: Any, key: str = "records") -> dict[str, dict[str, Any]]:
    return {
        text(row.get("case_id")): row
        for row in rows(document, key)
        if text(row.get("case_id"))
    }


def _gold_witness() -> dict[str, dict[str, Any]]:
    """Read the pre-promotion Gold captured in the immutable A2OS audit."""

    document = read_json(A2OS_ROOT / "gold-alignment-audit.json", {}) or {}
    result = {
        text(row.get("case_id")): copy.deepcopy(row.get("current_gold"))
        for row in rows(document)
        if text(row.get("case_id")) and isinstance(row.get("current_gold"), Mapping)
    }
    if len(result) != CASE_COUNT:
        raise RuntimeError("sfh2_a2osp_pre_promotion_gold_witness_missing")
    return result


def load_inputs() -> dict[str, Any]:
    selection = rows(read_json(A2O_ROOT / "selection.json", {}), "cases")
    exact_rows = rows(read_json(A2OS_ROOT / "exact-occurrence-audit.json", {}))
    a2or_rows = rows(read_json(A2OR_ROOT / "evaluation.json", {}))
    result_rows = rows(read_json(A2OR_ROOT / "occurrence-results.json", {}))
    projection_rows = rows(read_json(A2OR_ROOT / "projected-legacy-roles.json", {}))
    active_gold = by_case(read_json(GOLD_PATH, {}))
    frozen_gold = _gold_witness()
    case_ids = [text(row.get("case_id")) for row in selection]
    expected = set(case_ids)
    maps = (
        {text(row.get("case_id")): row for row in exact_rows},
        {text(row.get("case_id")): row for row in a2or_rows},
        {text(row.get("case_id")): row for row in result_rows},
        {text(row.get("case_id")): row for row in projection_rows},
        frozen_gold,
        active_gold,
    )
    if len(case_ids) != CASE_COUNT or len(expected) != CASE_COUNT:
        raise RuntimeError("sfh2_a2osp_case_count_changed")
    if any(set(mapping) != expected for mapping in maps):
        raise RuntimeError("sfh2_a2osp_input_case_set_changed")
    authority = read_json(AUTHORITY_PATH, {}) or {}
    authority_rows = rows(authority)
    if len(authority_rows) != 2:
        raise RuntimeError("sfh2_a2osp_human_authority_requires_two_records")
    return {
        "selection": selection,
        "exact": {text(row.get("case_id")): row for row in exact_rows},
        "a2or_evaluation": {text(row.get("case_id")): row for row in a2or_rows},
        "a2or_results": {text(row.get("case_id")): row for row in result_rows},
        "a2or_projection": {text(row.get("case_id")): row for row in projection_rows},
        "frozen_gold": frozen_gold,
        "active_gold": active_gold,
        "authority": authority,
        "identity_manifest": read_json(IDENTITY_MANIFEST_PATH, {}) or {},
    }


def protected_hashes() -> dict[str, str]:
    paths = {
        "data/derived/sc1-site.json": FROZEN_SC1_SHA256,
        "data/derived/sc1-current-site.json": CURRENT_SC1_SHA256,
        "data/frozen/sfh2/identity-v1/manifest.json": IDENTITY_MANIFEST_SHA256,
    }
    return {path: file_hash(ROOT / path) for path in paths}


def occurrence_key(row: Mapping[str, Any]) -> dict[str, Any]:
    key = row.get("exact_occurrence_key")
    if not isinstance(key, Mapping):
        raise RuntimeError(f"sfh2_a2osp_exact_occurrence_key_missing:{row.get('case_id')}")
    return {field: copy.deepcopy(key.get(field)) for field in (
        "case_id", "story_id", "mention_id", "source_evidence_id", "source_start", "source_end", "surface"
    )}


def score(rows_in: list[Mapping[str, Any]], field: str) -> dict[str, Any]:
    evaluable = [row for row in rows_in if row.get(field) is not None]
    correct = sum(row.get(field) is True for row in evaluable)
    return {
        "correct": correct,
        "evaluable": len(evaluable),
        "accuracy": round(correct / len(evaluable), 4) if evaluable else None,
    }


def changed_fields(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    keys = sorted(set(before) | set(after))
    return [key for key in keys if before.get(key) != after.get(key)]
