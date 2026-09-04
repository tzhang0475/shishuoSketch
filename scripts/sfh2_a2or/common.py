"""Frozen A2O inputs and A2OR run constants.

This module deliberately reads the committed A2O packet and result artifacts.
It does not rebuild or mutate them.  A2OR changes only the prompt used for the
single narrative-function decision and writes a new output namespace.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from sfh2_a2o import common as a2o_common


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/generated/sfh2-a2or"
A2O_ROOT = ROOT / "data/generated/sfh2-a2o"
A2OT_ROOT = ROOT / "data/generated/sfh2-a2ot"
GOLD_PATH = ROOT / "data/annotation/sfh2-a2o-evaluation-gold.json"
BASELINE_COMMIT = "3d9d45e91c1746e74704d9e48537cdb2625a0a8e"
A2O_BASELINE_COMMIT = "1ac588e8ae54bd4745f3d091360d02e65e3f55ac"
MODEL = "deepseek-v4-flash"
TEMPERATURE = 0
THINKING = {"type": "disabled"}
STRICT_ENDPOINT = "https://api.deepseek.com/beta/chat/completions"
PROMPT_VERSION = "sfh2-a2or-occurrence-function-historian-v2"
SCHEMA_VERSION = "sfh2-a2or-occurrence-function-v2"
FUNCTION_NAME = "submit_sfh2_a2or_occurrence_function_v2"
MAX_PROVIDER_ATTEMPTS = 40


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


def rows(document: Any, key: str = "records") -> list[dict[str, Any]]:
    if isinstance(document, Mapping) and isinstance(document.get(key), list):
        return [dict(row) for row in document[key] if isinstance(row, Mapping)]
    if isinstance(document, list):
        return [dict(row) for row in document if isinstance(row, Mapping)]
    return []


def by_case(document: Any, key: str = "records") -> dict[str, dict[str, Any]]:
    return {
        text(row.get("case_id")): row
        for row in rows(document, key)
        if text(row.get("case_id"))
    }


def load_frozen_a2o() -> dict[str, Any]:
    """Load the exact A2O selection, packets, and results as immutable inputs."""

    selection_document = read_json(A2O_ROOT / "selection.json", {}) or {}
    selections = rows(selection_document, "cases")
    packet_rows = rows(read_json(A2O_ROOT / "case-packets.json", {}), "packets")
    packets = {
        text(row.get("case_id")): copy.deepcopy(row.get("packet"))
        for row in packet_rows
        if text(row.get("case_id")) and isinstance(row.get("packet"), Mapping)
    }
    a2o_results = by_case(read_json(A2O_ROOT / "occurrence-results.json", {}))
    if len(selections) != 26 or len({text(row.get("case_id")) for row in selections}) != 26:
        raise RuntimeError("sfh2_a2or_requires_exact_26_a2o_selections")
    case_ids = [text(row.get("case_id")) for row in selections]
    expected = set(case_ids)
    if set(packets) != expected or set(a2o_results) != expected:
        raise RuntimeError("sfh2_a2or_a2o_input_case_set_changed")
    if selection_document.get("selection_hash") != stable_hash(selections):
        raise RuntimeError("sfh2_a2or_a2o_selection_hash_invalid")
    if any(not isinstance(packets[case_id], Mapping) for case_id in case_ids):
        raise RuntimeError("sfh2_a2or_a2o_packet_missing")
    return {
        "selection_document": selection_document,
        "selections": selections,
        "packets": packets,
        "a2o_results": a2o_results,
        "a2o_architecture": read_json(A2O_ROOT / "architecture-freeze.json", {}) or {},
        "a2ot_taxonomy": read_json(A2OT_ROOT / "taxonomy-definition.json", {}) or {},
        "a2ot_gold_audit": read_json(A2OT_ROOT / "gold-taxonomy-audit.json", {}) or {},
    }


def frozen_input_hashes(bundle: Mapping[str, Any]) -> dict[str, str]:
    paths = [
        A2O_ROOT / "architecture-freeze.json",
        A2O_ROOT / "selection.json",
        A2O_ROOT / "case-packets.json",
        A2O_ROOT / "occurrence-results.json",
        A2O_ROOT / "projected-legacy-roles.json",
        A2OT_ROOT / "taxonomy-definition.json",
        ROOT / "data/frozen/sfh2/identity-v1/manifest.json",
    ]
    return {
        str(path.relative_to(ROOT)): file_hash(path)
        for path in paths
        if path.is_file()
    }


def a2o_result_semantics(row: Mapping[str, Any]) -> dict[str, Any]:
    result = row.get("occurrence_result")
    if not isinstance(result, Mapping):
        return {}
    return {
        key: copy.deepcopy(result.get(key))
        for key in ("case_id", "narrative_function", "confidence", "supporting_evidence_ids", "reason_summary")
        if key in result
    }


def old_gold_map(bundle: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the immutable pre-promotion Gold captured by A2OT."""

    return {
        text(row.get("case_id")): copy.deepcopy(row.get("current_gold"))
        for row in rows(bundle.get("a2ot_gold_audit"), "records")
        if text(row.get("case_id")) and isinstance(row.get("current_gold"), Mapping)
    }


def protected_hashes() -> dict[str, str]:
    paths = [
        "data/derived/sc1-site.json",
        "data/derived/sc1-current-site.json",
        "data/frozen/sfh2/identity-v1/manifest.json",
    ]
    return {path: file_hash(ROOT / path) for path in paths}
