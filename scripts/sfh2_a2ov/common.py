"""Frozen A2OR inputs and A2OV reviewer packet helpers.

A2OV deliberately treats the A2OR semantic result as an immutable cached
primary hypothesis.  This module only assembles an allow-listed review input;
it never loads Gold or residual-error classifications into that input.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/generated/sfh2-a2ov"
A2O_ROOT = ROOT / "data/generated/sfh2-a2o"
A2OT_ROOT = ROOT / "data/generated/sfh2-a2ot"
A2OR_ROOT = ROOT / "data/generated/sfh2-a2or"
A2OS_ROOT = ROOT / "data/generated/sfh2-a2os"
A2OSP_ROOT = ROOT / "data/generated/sfh2-a2osp"
GOLD_PATH = ROOT / "data/annotation/sfh2-a2o-evaluation-gold.json"
IDENTITY_MANIFEST_PATH = ROOT / "data/frozen/sfh2/identity-v1/manifest.json"

BASELINE_COMMIT = "2fe9c74b5cff32e478c79f17d08d3c51e645bf60"
MODEL = "deepseek-v4-flash"
TEMPERATURE = 0
THINKING = {"type": "disabled"}
STRICT_ENDPOINT = "https://api.deepseek.com/beta/chat/completions"
PROMPT_VERSION = "sfh2-a2ov-conservative-occurrence-reviewer-v1"
SCHEMA_VERSION = "sfh2-a2ov-review-v1"
FUNCTION_NAME = "submit_sfh2_a2ov_occurrence_review_v1"
CASE_COUNT = 26
REVIEWED_ROLE_COUNT = 6
CHALLENGE_COUNT = 20
MAX_PROVIDER_ATTEMPTS = 54

NARRATIVE_FUNCTIONS = (
    "participant",
    "reference",
    "speaker",
    "addressee",
    "collective_reference",
    "person_attribute",
    "citation_source",
    "historical_exemplum",
    "genealogy_reference",
    "structural",
    "other",
    "uncertain",
)

FROZEN_SC1_SHA256 = "cc82c6738fcbf4fc14c12005a459048e71ce329492867d0910562fc6fdfda0d8"
CURRENT_SC1_SHA256 = "b916530264285dd7fa1d2e27a7a1dff8cd2ed794dfb3b84985881f8f209d8f6a"
IDENTITY_MANIFEST_SHA256 = "f60e4eb84c5af10d644ac09dbcbdfba93cc435660868c3e38486563604dcc95e"
ACTIVE_GOLD_SHA256 = "177ab3018e6741c3deaf3b5f957bc177df8c4f416ee9a9035bdf6027f7d7e3a7"


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
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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


def exact_occurrence_key(packet: Mapping[str, Any]) -> dict[str, Any]:
    target = packet.get("target") if isinstance(packet.get("target"), Mapping) else {}
    return {
        "case_id": text(packet.get("case_id")),
        "story_id": text(packet.get("story_id")),
        "mention_id": text(packet.get("mention_id")),
        "source_evidence_id": text(target.get("source_evidence_id")),
        "source_start": target.get("source_start"),
        "source_end": target.get("source_end"),
        "surface": text(target.get("surface")),
    }


def _load_packet_rows() -> dict[str, dict[str, Any]]:
    document = read_json(A2OR_ROOT / "case-packets.json", {}) or {}
    result: dict[str, dict[str, Any]] = {}
    for row in document.get("packets", []) if isinstance(document, Mapping) else []:
        if isinstance(row, Mapping) and isinstance(row.get("packet"), Mapping):
            case_id = text(row.get("case_id"))
            if case_id:
                result[case_id] = copy.deepcopy(row["packet"])
    return result


def _validate_exact_witnesses(
    case_ids: list[str],
    packets: Mapping[str, Mapping[str, Any]],
) -> None:
    a2osp = by_case(read_json(A2OSP_ROOT / "a2or-post-promotion-evaluation.json", {}))
    integrity = read_json(A2OSP_ROOT / "selection-integrity-invariant.json", {}) or {}
    if integrity.get("all_current_cases_have_exact_keys") is not True:
        raise RuntimeError("sfh2_a2ov_selection_integrity_witness_failed")
    if len(a2osp) != CASE_COUNT:
        raise RuntimeError("sfh2_a2ov_exact_occurrence_witness_case_count_changed")
    for case_id in case_ids:
        expected = a2osp[case_id].get("exact_occurrence_key")
        actual = exact_occurrence_key(packets[case_id])
        if not isinstance(expected, Mapping) or dict(expected) != actual:
            raise RuntimeError(f"sfh2_a2ov_exact_occurrence_key_changed:{case_id}")


def load_frozen_bundle() -> dict[str, Any]:
    """Load exactly the A2OR 26-case cache and its exact-key witness."""

    selection = read_json(A2OR_ROOT / "selection-verification.json", {}) or {}
    case_ids = [text(value) for value in selection.get("case_ids", [])]
    if len(case_ids) != CASE_COUNT or len(set(case_ids)) != CASE_COUNT:
        raise RuntimeError("sfh2_a2ov_requires_exact_26_cases")
    packets = _load_packet_rows()
    primary_rows = by_case(read_json(A2OR_ROOT / "occurrence-results.json", {}))
    if set(packets) != set(case_ids) or set(primary_rows) != set(case_ids):
        raise RuntimeError("sfh2_a2ov_frozen_a2or_case_set_changed")
    _validate_exact_witnesses(case_ids, packets)
    if selection.get("selection_hash") != "269ad737e687c1526b89a4bc17ceea2c89fc11c05eb854e1aeb493b6ce2a9841":
        raise RuntimeError("sfh2_a2ov_frozen_selection_hash_changed")
    for case_id in case_ids:
        if primary_rows[case_id].get("valid") is not True:
            raise RuntimeError(f"sfh2_a2ov_primary_cache_invalid:{case_id}")
        if not isinstance(primary_rows[case_id].get("occurrence_result"), Mapping):
            raise RuntimeError(f"sfh2_a2ov_primary_semantics_missing:{case_id}")
    return {
        "selection": selection,
        "case_ids": case_ids,
        "packets": packets,
        "primary_rows": primary_rows,
        "taxonomy": read_json(A2OT_ROOT / "taxonomy-definition.json", {}) or {},
        "selection_integrity": read_json(A2OSP_ROOT / "selection-integrity-invariant.json", {}) or {},
    }


def primary_semantic(row: Mapping[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(row.get("occurrence_result") or {})


def primary_confidence(row: Mapping[str, Any]) -> str:
    return text(primary_semantic(row).get("confidence"))


def target_source_evidence(packet: Mapping[str, Any]) -> dict[str, Any]:
    target = packet.get("target") if isinstance(packet.get("target"), Mapping) else {}
    target_id = text(target.get("source_evidence_id"))
    for evidence in packet.get("source_evidence", []) or []:
        if isinstance(evidence, Mapping) and text(evidence.get("evidence_id")) == target_id:
            return copy.deepcopy(dict(evidence))
    return {}


def reviewer_payload(packet: Mapping[str, Any], primary: Mapping[str, Any]) -> dict[str, Any]:
    """Build the reviewer allow-list without Gold or residual annotations."""

    return {
        "task": "critically check only the primary narrative_function for the exact target occurrence",
        "case_id": packet.get("case_id"),
        "story_id": packet.get("story_id"),
        "target": copy.deepcopy(packet.get("target", {})),
        "target_source_evidence": target_source_evidence(packet),
        "nearby_source_evidence": copy.deepcopy(packet.get("source_evidence", [])),
        "validated_local_mentions": copy.deepcopy(packet.get("validated_local_mentions", [])),
        "provenance_layer": packet.get("provenance_layer"),
        "frozen_identity": copy.deepcopy(packet.get("frozen_identity_context", {})),
        "relevant_discourse_context": copy.deepcopy(packet.get("frozen_discourse_context", {})),
        "primary": {
            "narrative_function": primary.get("narrative_function"),
            "confidence": primary.get("confidence"),
            "supporting_evidence_ids": copy.deepcopy(primary.get("supporting_evidence_ids", [])),
            "reason_summary": primary.get("reason_summary"),
        },
        "narrative_function_ontology": list(NARRATIVE_FUNCTIONS),
        "identity_not_under_review": True,
        "provenance_structural_and_not_under_review": True,
        "reviewer_is_primary_aware": True,
        "do_not_output_identity_or_provenance_fields": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }


def input_hashes() -> dict[str, str]:
    paths = [
        A2OR_ROOT / "selection-verification.json",
        A2OR_ROOT / "case-packets.json",
        A2OR_ROOT / "occurrence-results.json",
        A2OR_ROOT / "projected-legacy-roles.json",
        A2OSP_ROOT / "selection-integrity-invariant.json",
        A2OSP_ROOT / "a2or-post-promotion-evaluation.json",
        A2OT_ROOT / "taxonomy-definition.json",
        IDENTITY_MANIFEST_PATH,
    ]
    return {
        str(path.relative_to(ROOT)): file_hash(path)
        for path in paths
        if path.is_file()
    }


def protected_hashes() -> dict[str, Any]:
    paths = [
        "data/generated/sfh2-a2o",
        "data/generated/sfh2-a2ot",
        "data/generated/sfh2-a2or",
        "data/generated/sfh2-a2os",
        "data/generated/sfh2-a2osp",
        "data/annotation/sfh2-a2o-evaluation-gold.json",
        "data/frozen/sfh2/identity-v1/manifest.json",
        "data/derived/sc1-site.json",
        "data/derived/sc1-current-site.json",
        "data/people.json",
        "data/aliases.json",
    ]
    result: dict[str, Any] = {}
    for relative in paths:
        path = ROOT / relative
        if path.is_file():
            result[relative] = {"sha256": file_hash(path), "size_bytes": path.stat().st_size}
        elif path.is_dir():
            result[relative] = {
                "file_count": sum(1 for child in path.rglob("*") if child.is_file()),
                "sha256_by_file": {
                    str(child.relative_to(ROOT)): file_hash(child)
                    for child in sorted(path.rglob("*"))
                    if child.is_file()
                },
            }
    return result


def exact_key_map(bundle: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        case_id: exact_occurrence_key(bundle["packets"][case_id])
        for case_id in bundle["case_ids"]
    }
