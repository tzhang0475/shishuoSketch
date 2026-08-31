"""Frozen inputs and deterministic helpers for the A1R review repair."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from sfh2_a0.common import build_case_packet as _build_case_packet
from sfh2_a0.common import load_inputs as _load_inputs
from sfh2_a0.common import records as _records
from sfh2_a0r.common import file_hash as _file_hash

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/generated/sfh2-a1r"
A1R_L_ROOT = ROOT / "data/generated/sfh2-a0r-l"
A1R_LIVE_ROOT = A1R_L_ROOT / "live/sfh2-a0r-l-host-live-v1"
MODEL = "deepseek-v4-flash"
PILOT_VERSION = "sfh2-a1r-v1"
SCHEMA_VERSION = "sfh2-a1r-v1"
STRICT_ENDPOINT = "https://api.deepseek.com/beta/chat/completions"
MAX_PROVIDER_ATTEMPTS = 30
PROMPT_VERSIONS = {
    "critical_reviewer": "sfh2-a1r-critical-reviewer-patch-ops-v1",
    "adjudicator": "sfh2-a1r-adjudicator-selector-patch-ops-v1",
}
FUNCTION_NAMES = {
    "critical_reviewer": "submit_sfh2_a0r_critical_review_patch_v1",
    "adjudicator": "submit_sfh2_a0r_adjudication_selector_v1",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def text(value: Any) -> str:
    return str(value or "").strip()


def records(document: Any, *keys: str) -> list[dict[str, Any]]:
    return _records(document, *(keys or ("records",)))


def load_inputs() -> dict[str, Any]:
    return _load_inputs()


def build_case_packet(case: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    packet = dict(_build_case_packet(case, inputs))
    packet["sfh2_a1r_authority"] = "cached_primary_strict_review_python_integrity_and_storage"
    packet["gold_visible_to_model"] = False
    packet["candidate_only"] = True
    packet["canonical_write_back"] = False
    return packet


def cohort_cases() -> dict[str, list[dict[str, Any]]]:
    return {
        "regression": [dict(row) for row in (read_json(A1R_L_ROOT / "regression-selection.json", {}) or {}).get("cases", []) or []],
        "challenge": [dict(row) for row in (read_json(A1R_L_ROOT / "challenge-selection.json", {}) or {}).get("cases", []) or []],
    }


def source_manifest() -> dict[str, str]:
    paths = [
        A1R_L_ROOT / "architecture-freeze.json",
        A1R_L_ROOT / "regression-selection.json",
        A1R_L_ROOT / "challenge-selection.json",
        A1R_L_ROOT / "cache-index.json",
        A1R_LIVE_ROOT / "transport.json",
        A1R_L_ROOT / "challenge-human-review.json",
        A1R_L_ROOT / "regression-evaluation.json",
        A1R_L_ROOT / "metrics.json",
    ]
    return {str(path.relative_to(ROOT)): file_hash(path) for path in paths if path.is_file()}


def patch_contract_fingerprint() -> dict[str, str]:
    from sfh2_a0r.contracts import adjudication_tool, critical_review_tool, semantic_record_tool

    return {
        "semantic_record": stable_hash(semantic_record_tool()),
        "critical_review": stable_hash(critical_review_tool()),
        "adjudication": stable_hash(adjudication_tool()),
    }
