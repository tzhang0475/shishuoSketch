"""Frozen inputs and language-neutral helpers for the A2OS audit.

This package audits occurrence identity and evaluation provenance.  It is not a
runtime semantic resolver: it does not infer a historical identity or a
narrative function from a surface string.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
BASELINE_COMMIT = "5ccaae72e9842054984fff4f741bf6c5a2ac5b32"
OUT = ROOT / "data/generated/sfh2-a2os"
A2O_ROOT = ROOT / "data/generated/sfh2-a2o"
A2OT_ROOT = ROOT / "data/generated/sfh2-a2ot"
A2OR_ROOT = ROOT / "data/generated/sfh2-a2or"
SELECTION_PATH = A2O_ROOT / "selection.json"
PACKETS_PATH = A2O_ROOT / "case-packets.json"
A2O_RESULTS_PATH = A2O_ROOT / "occurrence-results.json"
A2O_EVALUATION_PATH = A2O_ROOT / "evaluation.json"
A2OT_AUDIT_PATH = A2OT_ROOT / "gold-taxonomy-audit.json"
A2OR_RESULTS_PATH = A2OR_ROOT / "occurrence-results.json"
A2OR_EVALUATION_PATH = A2OR_ROOT / "evaluation.json"
GOLD_PATH = ROOT / "data/annotation/sfh2-a2o-evaluation-gold.json"
MENTIONS_PATH = ROOT / "data/generated/sfh1/validated-mentions.json"
IDENTITY_MANIFEST_PATH = ROOT / "data/frozen/sfh2/identity-v1/manifest.json"

CASE_COUNT = 26
PROTECTED_SC1_SHA256 = "cc82c6738fcbf4fc14c12005a459048e71ce329492867d0910562fc6fdfda0d8"
PROTECTED_SC1_CURRENT_SHA256 = "b916530264285dd7fa1d2e27a7a1dff8cd2ed794dfb3b84985881f8f209d8f6a"
PROTECTED_IDENTITY_SHA256 = "f60e4eb84c5af10d644ac09dbcbdfba93cc435660868c3e38486563604dcc95e"

CASE_GU = "sfh2-a0r-l-challenge-f245371d8f0cdf9c8773"
CASE_QI = "sfh2-a0-57d1fc3c0492b21ee1f4"
CASE_KANG = "sfh2-a0r-l-challenge-f56a3b1584f60d143182"
CASE_WENDU = "sfh2-a0r-l-challenge-a1f887b7602c151cfbbd"


def text(value: Any) -> str:
    return str(value or "").strip()


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


def source_evidence(packet: Mapping[str, Any], evidence_id: str) -> dict[str, Any]:
    for row in packet.get("source_evidence", []) or []:
        if isinstance(row, Mapping) and text(row.get("evidence_id")) == text(evidence_id):
            return dict(row)
    return {}


def text_offsets(source_text: str, surface: str) -> list[dict[str, int]]:
    """Return textual occurrences for collision visibility only.

    This is structural reporting.  It does not classify the meaning of any
    occurrence and is never used to select or replace a semantic answer.
    """

    found: list[dict[str, int]] = []
    start = 0
    while surface:
        position = source_text.find(surface, start)
        if position < 0:
            break
        found.append({"source_start": position, "source_end": position + len(surface)})
        start = position + 1
    return found


def interval_overlaps(left_start: Any, left_end: Any, right_start: Any, right_end: Any) -> bool:
    values = (left_start, left_end, right_start, right_end)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        return False
    return max(left_start, right_start) < min(left_end, right_end)


def load_bundle() -> dict[str, Any]:
    selection_document = read_json(SELECTION_PATH, {}) or {}
    selections = rows(selection_document, "cases")
    packet_rows = rows(read_json(PACKETS_PATH, {}) or {}, "packets")
    packets = {
        text(row.get("case_id")): row.get("packet")
        for row in packet_rows
        if text(row.get("case_id")) and isinstance(row.get("packet"), Mapping)
    }
    a2o_results = by_case(read_json(A2O_RESULTS_PATH, {}) or {})
    a2o_evaluation = by_case(read_json(A2O_EVALUATION_PATH, {}) or {})
    a2or_results = by_case(read_json(A2OR_RESULTS_PATH, {}) or {})
    a2or_evaluation = by_case(read_json(A2OR_EVALUATION_PATH, {}) or {})
    # A2OS is a frozen audit. A later Gold promotion must not silently alter
    # its historical counterfactuals, so prefer the Gold witness captured in
    # the immutable A2OS alignment artifact.
    audit_document = read_json(OUT / "gold-alignment-audit.json", {}) or {}
    frozen_gold = {
        text(row.get("case_id")): copy.deepcopy(row.get("current_gold"))
        for row in rows(audit_document)
        if text(row.get("case_id")) and isinstance(row.get("current_gold"), Mapping)
    }
    gold = frozen_gold if len(frozen_gold) == 26 else by_case(read_json(GOLD_PATH, {}) or {})
    mentions_document = read_json(MENTIONS_PATH, {}) or {}
    mention_rows = rows(mentions_document)
    mentions = {
        text(row.get("mention_id")): row
        for row in mention_rows
        if text(row.get("mention_id"))
    }
    if len(selections) != CASE_COUNT or len({text(row.get("case_id")) for row in selections}) != CASE_COUNT:
        raise RuntimeError("sfh2_a2os_requires_exact_26_frozen_cases")
    expected = {text(row.get("case_id")) for row in selections}
    maps = (packets, a2o_results, a2o_evaluation, a2or_results, a2or_evaluation, gold)
    if any(set(mapping) != expected for mapping in maps):
        raise RuntimeError("sfh2_a2os_frozen_input_case_sets_mismatch")
    return {
        "selection_document": selection_document,
        "selections": selections,
        "packets": packets,
        "a2o_results": a2o_results,
        "a2o_evaluation": a2o_evaluation,
        "a2or_results": a2or_results,
        "a2or_evaluation": a2or_evaluation,
        "gold": gold,
        "mentions": mentions,
        "mention_rows": mention_rows,
    }


def occurrence_key(selection: Mapping[str, Any], target: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_id": selection.get("case_id"),
        "story_id": selection.get("story_id"),
        "mention_id": selection.get("mention_id"),
        "source_evidence_id": selection.get("source_evidence_id"),
        "source_start": target.get("source_start"),
        "source_end": target.get("source_end"),
        "surface": target.get("surface"),
    }


def target_context(packet: Mapping[str, Any], selection: Mapping[str, Any]) -> dict[str, Any]:
    target = packet.get("target") if isinstance(packet.get("target"), Mapping) else {}
    evidence_id = text(target.get("source_evidence_id"))
    evidence = source_evidence(packet, evidence_id)
    source_text = text(evidence.get("text"))
    start = target.get("source_start")
    end = target.get("source_end")
    offsets_valid = (
        isinstance(start, int)
        and not isinstance(start, bool)
        and isinstance(end, int)
        and not isinstance(end, bool)
        and 0 <= start <= end <= len(source_text)
    )
    matched = source_text[start:end] if offsets_valid else ""
    radius = 48
    window_start = max(0, start - radius) if offsets_valid else 0
    window_end = min(len(source_text), end + radius) if offsets_valid else len(source_text)
    return {
        "target": copy.deepcopy(dict(target)),
        "target_evidence": copy.deepcopy(evidence),
        "source_text": source_text,
        "matched_source_text": matched,
        "offsets_valid": offsets_valid,
        "offset_convention": "zero_based_end_exclusive",
        "context_window": {
            "source_start": window_start,
            "source_end": window_end,
            "text": source_text[window_start:window_end],
        },
        "source_evidence_ids": [
            text(row.get("evidence_id"))
            for row in packet.get("source_evidence", []) or []
            if isinstance(row, Mapping) and text(row.get("evidence_id"))
        ],
        "selection_surface_matches_target": text(selection.get("surface")) == text(target.get("surface")),
        "selection_evidence_matches_target": text(selection.get("source_evidence_id")) == evidence_id,
    }
