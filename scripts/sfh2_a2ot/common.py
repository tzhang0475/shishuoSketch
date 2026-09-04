"""Frozen A2O inputs used by the offline taxonomy audit."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
BASELINE_COMMIT = "1ac588e8ae54bd4745f3d091360d02e65e3f55ac"
A2O_ROOT = ROOT / "data/generated/sfh2-a2o"
A2O_GOLD_PATH = ROOT / "data/annotation/sfh2-a2o-evaluation-gold.json"
A2O_ROLE_AUDIT_PATH = ROOT / "data/generated/sfh2-a2g/occurrence-role-audit.json"
A2R_EVALUATION_PATH = ROOT / "data/generated/sfh2-a2r/regression-evaluation.json"
A2R_FINAL_RESULTS_PATH = ROOT / "data/generated/sfh2-a2r/final-results.json"
A2R_CHALLENGE_REVIEW_PATH = ROOT / "data/generated/sfh2-a2r/challenge-review-bundle.json"
OUT = ROOT / "data/generated/sfh2-a2ot"

A2O_PROTECTED_FILES = (
    "data/annotation/sfh2-a2o-evaluation-gold.json",
    "data/generated/sfh2-a2o/architecture-freeze.json",
    "data/generated/sfh2-a2o/case-packets.json",
    "data/generated/sfh2-a2o/confusion-matrix.json",
    "data/generated/sfh2-a2o/error-analysis.json",
    "data/generated/sfh2-a2o/evaluation.json",
    "data/generated/sfh2-a2o/metrics.json",
    "data/generated/sfh2-a2o/occurrence-results.json",
    "data/generated/sfh2-a2o/occurrence-semantics.md",
    "data/generated/sfh2-a2o/projected-legacy-roles.json",
    "data/generated/sfh2-a2o/recommendation.json",
    "data/generated/sfh2-a2o/selection.json",
    "data/generated/sfh2-a2o/storage-safety-audit.json",
    "data/generated/sfh2-a2o/transport.json",
    "data/generated/sfh2-a2o/validation-summary.json",
)

PROTECTED_HASHES = {
    "data/derived/sc1-site.json": "cc82c6738fcbf4fc14c12005a459048e71ce329492867d0910562fc6fdfda0d8",
    "data/derived/sc1-current-site.json": "b916530264285dd7fa1d2e27a7a1dff8cd2ed794dfb3b84985881f8f209d8f6a",
    "data/frozen/sfh2/identity-v1/manifest.json": "f60e4eb84c5af10d644ac09dbcbdfba93cc435660868c3e38486563604dcc95e",
}


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


def _by_case(document: Any, key: str = "records") -> dict[str, dict[str, Any]]:
    return {
        text(row.get("case_id")): row
        for row in rows(document, key)
        if text(row.get("case_id"))
    }


def load_frozen_bundle() -> dict[str, Any]:
    packet_rows = rows(read_json(A2O_ROOT / "case-packets.json", {}), "packets")
    packets = {
        text(row.get("case_id")): row.get("packet")
        for row in packet_rows
        if text(row.get("case_id")) and isinstance(row.get("packet"), Mapping)
    }
    results = _by_case(read_json(A2O_ROOT / "occurrence-results.json", {}))
    evaluation = _by_case(read_json(A2O_ROOT / "evaluation.json", {}))
    selection = rows(read_json(A2O_ROOT / "selection.json", {}), "cases")
    case_ids = [text(row.get("case_id")) for row in selection]
    # A2OR may later promote a reviewed revision of the active Gold file.  The
    # A2OT audit itself remains historical and must therefore read the Gold
    # witness captured inside its immutable audit artifact when available.
    # This is provenance selection, not a semantic replacement or a runtime
    # historical rule.
    audit_document = read_json(OUT / "gold-taxonomy-audit.json", {}) or {}
    frozen_gold = {
        text(row.get("case_id")): row.get("current_gold")
        for row in rows(audit_document)
        if text(row.get("case_id")) and isinstance(row.get("current_gold"), Mapping)
    }
    gold = frozen_gold if len(frozen_gold) == len(case_ids) else _by_case(read_json(A2O_GOLD_PATH, {}))
    if len(case_ids) != 26 or len(set(case_ids)) != 26:
        raise RuntimeError("sfh2_a2ot_expected_26_frozen_a2o_cases")
    expected = set(case_ids)
    if set(packets) != expected or set(results) != expected or set(evaluation) != expected or set(gold) != expected:
        raise RuntimeError("sfh2_a2ot_frozen_case_sets_do_not_match")
    return {
        "selection": selection,
        "packets": packets,
        "results": results,
        "evaluation": evaluation,
        "gold": gold,
        "a2r_evaluation": read_json(A2R_EVALUATION_PATH, {}),
        "a2r_final_results": _by_case(read_json(A2R_FINAL_RESULTS_PATH, {})),
        "a2r_challenge_review": _by_case(read_json(A2R_CHALLENGE_REVIEW_PATH, {})),
        "role_audit": read_json(A2O_ROLE_AUDIT_PATH, {}),
    }


def _target_evidence(packet: Mapping[str, Any]) -> dict[str, Any]:
    target = packet.get("target") if isinstance(packet.get("target"), Mapping) else {}
    target_id = text(target.get("source_evidence_id"))
    evidence = packet.get("source_evidence") if isinstance(packet.get("source_evidence"), list) else []
    for row in evidence:
        if isinstance(row, Mapping) and text(row.get("evidence_id")) == target_id:
            return dict(row)
    return {}


def target_context(packet: Mapping[str, Any]) -> dict[str, Any]:
    target = packet.get("target") if isinstance(packet.get("target"), Mapping) else {}
    evidence = _target_evidence(packet)
    source_text = text(evidence.get("text"))
    start = target.get("source_start")
    end = target.get("source_end")
    valid_offsets = isinstance(start, int) and not isinstance(start, bool) and isinstance(end, int) and not isinstance(end, bool) and 0 <= start <= end <= len(source_text)
    matched = source_text[start:end] if valid_offsets else ""
    radius = 32
    window_start = max(0, start - radius) if valid_offsets else 0
    window_end = min(len(source_text), end + radius) if valid_offsets else len(source_text)
    nearby = []
    for row in packet.get("source_evidence", []) if isinstance(packet.get("source_evidence"), list) else []:
        if isinstance(row, Mapping):
            nearby.append({
                "evidence_id": row.get("evidence_id"),
                "source_layer": row.get("source_layer"),
                "text": row.get("text"),
            })
    return {
        "exact_span": target.get("exact_span"),
        "source_evidence_id": target.get("source_evidence_id"),
        "source_start": start,
        "source_end": end,
        "offset_convention": "zero_based_end_exclusive",
        "offsets_valid": valid_offsets,
        "matched_source_text": matched,
        "target_evidence": copy.deepcopy(evidence),
        "context_window": {
            "start": window_start,
            "end": window_end,
            "text": source_text[window_start:window_end],
        },
        "nearby_source_evidence": nearby,
    }
