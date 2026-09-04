"""Frozen A2OR inputs and blind A2OVB packet construction.

The boundary cohort is routed from an already-frozen A2OR output, but the
allow-listed provider packet deliberately contains no A2OR hypothesis.  Gold
and all prior review artifacts are post-inference/evaluation inputs only.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from sfh2_a2o.provenance import derive_provenance_layer


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/generated/sfh2-a2ovb"
A2OR_ROOT = ROOT / "data/generated/sfh2-a2or"
A2O_ROOT = ROOT / "data/generated/sfh2-a2o"
A2OT_ROOT = ROOT / "data/generated/sfh2-a2ot"
A2OS_ROOT = ROOT / "data/generated/sfh2-a2os"
A2OSP_ROOT = ROOT / "data/generated/sfh2-a2osp"
A2OV_ROOT = ROOT / "data/generated/sfh2-a2ov"
GOLD_PATH = ROOT / "data/annotation/sfh2-a2o-evaluation-gold.json"
IDENTITY_MANIFEST_PATH = ROOT / "data/frozen/sfh2/identity-v1/manifest.json"

BASELINE_COMMIT = "ca3ac0d39f7f85282f555a4b4494f6116c9afbe1"
MODEL = "deepseek-v4-flash"
TEMPERATURE = 0
THINKING = {"type": "disabled"}
STRICT_ENDPOINT = "https://api.deepseek.com/beta/chat/completions"
PROMPT_VERSION = "sfh2-a2ovb-blind-boundary-validator-v1"
SCHEMA_VERSION = "sfh2-a2ovb-boundary-validation-v1"
FUNCTION_NAME = "submit_sfh2_a2ovb_boundary_validation_v1"
CASE_COUNT = 26
REVIEWED_ROLE_COUNT = 6
CHALLENGE_COUNT = 20
BOUNDARY_FUNCTIONS = ("participant", "reference")
BOUNDARY_JUDGMENTS = ("event_participant", "referential_only", "uncertain")
CONFIDENCES = ("low", "medium", "high")
MAX_PROVIDER_ATTEMPTS = 54
SELECTION_HASH = "269ad737e687c1526b89a4bc17ceea2c89fc11c05eb854e1aeb493b6ce2a9841"

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
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rows(document: Any, key: str = "records") -> list[dict[str, Any]]:
    if isinstance(document, list):
        return [dict(row) for row in document if isinstance(row, Mapping)]
    if isinstance(document, Mapping) and isinstance(document.get(key), list):
        return [dict(row) for row in document[key] if isinstance(row, Mapping)]
    return []


def by_case(document: Any, key: str = "records") -> dict[str, dict[str, Any]]:
    return {text(row.get("case_id")): row for row in rows(document, key) if text(row.get("case_id"))}


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


def _packet_map() -> dict[str, dict[str, Any]]:
    document = read_json(A2OR_ROOT / "case-packets.json", {}) or {}
    result: dict[str, dict[str, Any]] = {}
    for row in document.get("packets", []) if isinstance(document, Mapping) else []:
        if isinstance(row, Mapping) and isinstance(row.get("packet"), Mapping):
            case_id = text(row.get("case_id"))
            if case_id:
                result[case_id] = copy.deepcopy(dict(row["packet"]))
    return result


def _verify_exact_witnesses(case_ids: list[str], packets: Mapping[str, Mapping[str, Any]]) -> None:
    witness = by_case(read_json(A2OSP_ROOT / "a2or-post-promotion-evaluation.json", {}))
    integrity = read_json(A2OSP_ROOT / "selection-integrity-invariant.json", {}) or {}
    if integrity.get("all_current_cases_have_exact_keys") is not True:
        raise RuntimeError("sfh2_a2ovb_selection_integrity_witness_failed")
    if len(witness) != CASE_COUNT:
        raise RuntimeError("sfh2_a2ovb_exact_witness_case_count_changed")
    for case_id in case_ids:
        expected = witness[case_id].get("exact_occurrence_key")
        actual = exact_occurrence_key(packets[case_id])
        if not isinstance(expected, Mapping) or dict(expected) != actual:
            raise RuntimeError("sfh2_a2ovb_exact_occurrence_key_changed:" + case_id)


def load_frozen_bundle() -> dict[str, Any]:
    selection = read_json(A2OR_ROOT / "selection-verification.json", {}) or {}
    case_ids = [text(value) for value in selection.get("case_ids", [])]
    if len(case_ids) != CASE_COUNT or len(set(case_ids)) != CASE_COUNT:
        raise RuntimeError("sfh2_a2ovb_requires_exact_26_cases")
    if selection.get("selection_hash") != SELECTION_HASH:
        raise RuntimeError("sfh2_a2ovb_selection_hash_changed")
    packets = _packet_map()
    primary_rows = by_case(read_json(A2OR_ROOT / "occurrence-results.json", {}))
    if set(packets) != set(case_ids) or set(primary_rows) != set(case_ids):
        raise RuntimeError("sfh2_a2ovb_frozen_a2or_case_set_changed")
    _verify_exact_witnesses(case_ids, packets)
    for case_id in case_ids:
        row = primary_rows[case_id]
        if row.get("valid") is not True or not isinstance(row.get("occurrence_result"), Mapping):
            raise RuntimeError("sfh2_a2ovb_primary_cache_invalid:" + case_id)
        packet = packets[case_id]
        derived, errors = derive_provenance_layer(packet)
        if errors or derived != text(packet.get("provenance_layer")):
            raise RuntimeError("sfh2_a2ovb_provenance_witness_failed:" + case_id)
    return {
        "selection": selection,
        "case_ids": case_ids,
        "packets": packets,
        "primary_rows": primary_rows,
        "selection_integrity": read_json(A2OSP_ROOT / "selection-integrity-invariant.json", {}) or {},
    }


def primary_semantic(row: Mapping[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(dict(row.get("occurrence_result") or {}))


def primary_function(row: Mapping[str, Any]) -> str:
    return text(primary_semantic(row).get("narrative_function"))


def boundary_case_ids(bundle: Mapping[str, Any]) -> list[str]:
    return [case_id for case_id in bundle["case_ids"] if primary_function(bundle["primary_rows"][case_id]) in BOUNDARY_FUNCTIONS]


def target_source_evidence(packet: Mapping[str, Any]) -> dict[str, Any]:
    target = packet.get("target") if isinstance(packet.get("target"), Mapping) else {}
    target_id = text(target.get("source_evidence_id"))
    for evidence in packet.get("source_evidence", []) or []:
        if isinstance(evidence, Mapping) and text(evidence.get("evidence_id")) == target_id:
            return copy.deepcopy(dict(evidence))
    return {}


def provider_payload(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Return only the blind boundary-validation input allow-list."""

    identity = copy.deepcopy(packet.get("frozen_identity_context", {}))
    return {
        "task": "classify only whether the exact target occurrence is event participation or referential-only mention",
        "case_id": text(packet.get("case_id")),
        "story_id": text(packet.get("story_id")),
        "target": copy.deepcopy(packet.get("target", {})),
        "target_source_evidence": target_source_evidence(packet),
        "nearby_source_evidence": copy.deepcopy(packet.get("source_evidence", [])),
        "validated_local_mentions": copy.deepcopy(packet.get("validated_local_mentions", [])),
        "provenance_layer": text(packet.get("provenance_layer")),
        "frozen_identity": identity,
        "frozen_semantic_kind": identity.get("semantic_kind"),
        "relevant_discourse_context": copy.deepcopy(packet.get("frozen_discourse_context", {})),
        "boundary_ontology": {
            "event_participant": "The referent is genuinely involved in a narrated event represented at this exact occurrence.",
            "referential_only": "The occurrence mentions, compares, evaluates, describes, or points to an entity without making it a participant in a narrated event at this occurrence.",
            "uncertain": "The supplied evidence does not reliably establish the distinction.",
        },
        "identity_not_under_review": True,
        "provenance_structural_and_not_under_review": True,
        "no_prior_semantic_hypothesis_supplied": True,
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
    return {str(path.relative_to(ROOT)): file_hash(path) for path in paths if path.is_file()}


def protected_hashes() -> dict[str, Any]:
    paths = [
        "data/generated/sfh2-a2o",
        "data/generated/sfh2-a2ot",
        "data/generated/sfh2-a2or",
        "data/generated/sfh2-a2os",
        "data/generated/sfh2-a2osp",
        "data/generated/sfh2-a2ov",
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
    return {case_id: exact_occurrence_key(bundle["packets"][case_id]) for case_id in bundle["case_ids"]}
