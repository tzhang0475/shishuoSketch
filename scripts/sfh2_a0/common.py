"""Frozen inputs and deterministic helpers for the SFH2.2-A0 pilot."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from sfh2_2p.common import build_case_packet as _build_case_packet
from sfh2_2p.common import evidence_index as _evidence_index
from sfh2_2p.common import load_inputs as _load_inputs
from sfh2_2p.common import records as _records
from sfh2_2p.common import text

ROOT = Path(__file__).resolve().parents[2]
SFH1_ROOT = ROOT / "data/generated/sfh1"
OUT = ROOT / "data/generated/sfh2-a0"
SELECTION_PATH = ROOT / "data/annotation/sfh2-a0-selection.json"
GOLD_PATH = ROOT / "data/annotation/sfh2-a0-evaluation-gold.json"
MODEL = "deepseek-v4-flash"
PILOT_VERSION = "sfh2-a0-v2"
SCHEMA_VERSION = "sfh2-a0-v2"
STRICT_ENDPOINT = "https://api.deepseek.com/beta/chat/completions"
PROMPT_VERSIONS = {
    "primary_historian": "sfh2-a0-primary-historian-v2",
    "critical_reviewer": "sfh2-a0-critical-reviewer-v2",
    "adjudicator": "sfh2-a0-adjudicator-v2",
}
FUNCTION_NAMES = {
    "primary_historian": "submit_sfh2_a0_primary_semantics_v2",
    "critical_reviewer": "submit_sfh2_a0_critical_review_v2",
    "adjudicator": "submit_sfh2_a0_adjudication_v2",
}
MAX_PROVIDER_ATTEMPTS = 60

# This is normalization metadata only.  It does not interpret a historical
# surface or select an identity.
VARIANT_TRANSLATION = str.maketrans({
    "爲": "為", "髙": "高", "鳯": "鳳", "臺": "台", "裏": "裡",
    "禄": "祿", "隱": "隐", "獻": "献", "綽": "绰",
})


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(value: Any) -> str:
    return re.sub(r"\s+", "", text(value)).translate(VARIANT_TRANSLATION)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def records(document: Any, *keys: str) -> list[dict[str, Any]]:
    return _records(document, *(keys or ("records",)))


def evidence_index(packet: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return _evidence_index(packet)


def load_inputs() -> dict[str, Any]:
    return _load_inputs()


def build_case_packet(case: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Build the existing deterministic L0 packet without evaluation gold."""

    packet = _build_case_packet(case, inputs)
    # A0 adds no semantic labels to L0.  These fields are explicit transport
    # metadata and are safe for the provider to see.
    packet = dict(packet)
    packet["a0_semantic_authority"] = "llm"
    packet["python_authority"] = [
        "schema_and_evidence_integrity",
        "formal_consistency_checks",
        "candidate_id_allocation",
        "storage_safety",
    ]
    packet["gold_visible_to_model"] = False
    packet["candidate_only"] = True
    packet["canonical_write_back"] = False
    return packet


def input_hashes() -> dict[str, str]:
    paths = [
        SFH1_ROOT / "story-packets.json",
        SFH1_ROOT / "validated-mentions.json",
        SFH1_ROOT / "reference-semantics.json",
        SFH1_ROOT / "candidate-sets.json",
        SFH1_ROOT / "identity-judgments.json",
        SFH1_ROOT / "final-decisions.json",
        SFH1_ROOT / "relation-assertions.json",
        ROOT / "data/people.json",
        ROOT / "data/aliases.json",
        ROOT / "data/derived/hdb2-f-person-knowledge.json",
        ROOT / "data/derived/hdb2-f-candidate-person-knowledge.json",
        ROOT / "data/generated/hda2/repair-overlay.json",
        ROOT / "data/generated/sfh2-2p1/selection.json",
        ROOT / "data/generated/sfh2-2p2/selection.json",
    ]
    return {
        str(path.relative_to(ROOT)): file_hash(path)
        for path in paths
        if path.is_file()
    }


def case_by_id(selection: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {text(row.get("case_id")): dict(row) for row in selection.get("cases", []) or [] if isinstance(row, Mapping)}


def packet_evidence(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": row.get("evidence_id"),
            "source_layer": row.get("source_layer"),
            "source_ref": row.get("source_ref"),
            "text": row.get("text"),
        }
        for row in packet.get("source_evidence", []) or []
        if isinstance(row, Mapping)
    ]


def architecture_freeze(selection_hash: str) -> dict[str, Any]:
    """Hash A0's exact prompts, tools, consistency engine and inputs."""

    from . import consistency, pipeline, schemas

    code_paths = [
        ROOT / "scripts/sfh2_a0/common.py",
        ROOT / "scripts/sfh2_a0/consistency.py",
        ROOT / "scripts/sfh2_a0/pipeline.py",
        ROOT / "scripts/sfh2_a0/retrieval.py",
        ROOT / "scripts/sfh2_a0/schemas.py",
        ROOT / "scripts/sfh2_a0/transport.py",
    ]
    files = {
        str(path.relative_to(ROOT)): file_hash(path)
        for path in code_paths
        if path.is_file()
    }
    prompts = {
        "primary_historian": stable_hash(pipeline.PRIMARY_HISTORIAN_SYSTEM),
        "critical_reviewer": stable_hash(pipeline.CRITICAL_REVIEWER_SYSTEM),
        "adjudicator": stable_hash(pipeline.ADJUDICATOR_SYSTEM),
    }
    schemas = {
        "semantic_record": stable_hash(schemas.semantic_record_tool()),
        "critical_review": stable_hash(schemas.critical_review_tool()),
        "adjudication": stable_hash(schemas.adjudication_tool()),
    }
    model_config = {
        "model": MODEL,
        "temperature": 0,
        "thinking": {"type": "disabled"},
        "endpoint": STRICT_ENDPOINT,
        "prompt_versions": dict(PROMPT_VERSIONS),
        "function_names": dict(FUNCTION_NAMES),
        "max_provider_attempts": MAX_PROVIDER_ATTEMPTS,
    }
    result = {
        "schema": "sfh2-a0-architecture-freeze-v1",
        "pilot": "SFH2.2-A0",
        "baseline": "d832519b80be089f4c8cff887aa07f3693469fee",
        "selection_hash": selection_hash,
        "model_config": model_config,
        "model_config_hash": stable_hash(model_config),
        "prompt_hashes": prompts,
        "schema_hashes": schemas,
        "code_files": files,
        "consistency_engine_contract": consistency.CONSISTENCY_CONTRACT,
        "authority_policy": "reviewed human semantic decision > validated LLM semantic judgment > soft collective consistency > deterministic retrieval hint",
        "candidate_only": True,
        "canonical_write_back": False,
    }
    result["architecture_hash"] = stable_hash({key: value for key, value in result.items() if key != "architecture_hash"})
    return result
