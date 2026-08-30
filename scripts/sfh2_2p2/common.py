"""Frozen-input and architecture-freeze helpers for SFH2.2-P2.

P2 intentionally imports the P1 packet preparation and semantic contracts.
It owns a separate selection, cache, raw-run directory, and output projection;
the P1 source files are never edited by this pilot.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from sfh2_2p.common import build_case_packet as _build_case_packet
from sfh2_2p.common import load_inputs as _load_inputs
from sfh2_2p.common import records, text
from sfh2_2p1.common import file_hash, packet_index, read_json

ROOT = Path(__file__).resolve().parents[2]
SFH1_ROOT = ROOT / "data/generated/sfh1"
P_ROOT = ROOT / "data/generated/sfh2-2p"
P1_ROOT = ROOT / "data/generated/sfh2-2p1"
OUT = ROOT / "data/generated/sfh2-2p2"
SELECTION_PATH = ROOT / "data/annotation/sfh2-2p2-selection.json"

P1_BASELINE = "6237d9eafe44a29daab7dfcfb7256a1b39094871"
MODEL = "deepseek-v4-flash"
PILOT_VERSION = "sfh2-2p2-v1"
SCHEMA_VERSION = "sfh2-2p2-v1"

# These are deliberately the P1 contracts.  A different value would make the
# P2 run a prompt/schema experiment rather than a blind generalization test.
PROMPT_VERSIONS = {
    "entity_proposal": "sfh2-2p1-entity-proposal-v3",
    "identity_equivalence": "sfh2-2p1-identity-equivalence-v1",
}
STRICT_ENDPOINT = "https://api.deepseek.com/beta/chat/completions"

VARIANT_TRANSLATION = str.maketrans({
    "爲": "為", "髙": "高", "鳯": "鳳", "臺": "台", "裏": "裡",
    "禄": "祿", "綽": "绰", "隱": "隐", "獻": "献",
})


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def normalize(value: Any) -> str:
    return re.sub(r"\s+", "", text(value)).translate(VARIANT_TRANSLATION)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_inputs() -> dict[str, Any]:
    # Keep the same SFH1 frozen universe and source packet loader as P1.
    inputs = _load_inputs()
    inputs.update({
        "p_selection": read_json(P_ROOT / "selection.json", {}) or {},
        "p_candidate_sets": read_json(P_ROOT / "candidate-sets.json", {}) or {},
        "p_final": read_json(P_ROOT / "final-decisions.json", {}) or {},
        "p1_selection": read_json(P1_ROOT / "selection.json", {}) or {},
        "p1_final": read_json(P1_ROOT / "final-decisions.json", {}) or {},
    })
    return inputs


def build_case_packet(case: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    # The shared builder is deterministic L0 preparation.  P2 selection rows
    # contain no evaluation answer, so no gold can enter this packet.
    return _build_case_packet(case, inputs)


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
        P_ROOT / "selection.json",
        P_ROOT / "candidate-sets.json",
        P_ROOT / "final-decisions.json",
        P1_ROOT / "selection.json",
        P1_ROOT / "candidate-sets.json",
        P1_ROOT / "final-decisions.json",
    ]
    return {
        str(path.relative_to(ROOT)): file_hash(path)
        for path in paths
        if path.is_file()
    }


def architecture_freeze(selection_hash: str) -> dict[str, Any]:
    """Describe the exact P1 contracts imported by this pilot."""
    from sfh2_2p1 import pipeline as p1_pipeline
    from sfh2_2p1 import schemas as p1_schemas

    p1_files = [
        ROOT / "scripts/sfh2_2p1/common.py",
        ROOT / "scripts/sfh2_2p1/pipeline.py",
        ROOT / "scripts/sfh2_2p1/retrieval.py",
        ROOT / "scripts/sfh2_2p1/schemas.py",
        ROOT / "scripts/sfh2_2p1/transport.py",
    ]
    files = {
        str(path.relative_to(ROOT)): file_hash(path)
        for path in p1_files
        if path.is_file()
    }
    prompts = {
        "entity_proposal": stable_hash(p1_pipeline.PROPOSAL_SYSTEM),
        "identity_equivalence": stable_hash(p1_pipeline.EQUIVALENCE_SYSTEM),
    }
    schemas = {
        "entity_proposal": stable_hash(p1_schemas.entity_proposal_tool()),
        "identity_equivalence": stable_hash(p1_schemas.identity_equivalence_tool()),
    }
    model_config = {
        "model": MODEL,
        "temperature": 0,
        "thinking": {"type": "disabled"},
        "endpoint": STRICT_ENDPOINT,
        "prompt_versions": dict(PROMPT_VERSIONS),
        "function_names": {
            "entity_proposal": "submit_sfh2_2p1_entity_proposals",
            "identity_equivalence": "submit_sfh2_2p1_identity_equivalence",
        },
    }
    result = {
        "schema": "sfh2-2p2-architecture-freeze-v1",
        "pilot": "SFH2.2-P2",
        "p1_baseline": P1_BASELINE,
        "selection_hash": selection_hash,
        "model_config": model_config,
        "model_config_hash": stable_hash(model_config),
        "p1_files": files,
        "p1_prompt_hashes": prompts,
        "p1_schema_hashes": schemas,
        "authority_policy": "reviewed human semantics > LLM proposal/equivalence > soft consistency > Python retrieval hints",
        "candidate_only": True,
        "canonical_write_back": False,
    }
    result["architecture_hash"] = stable_hash({key: value for key, value in result.items() if key != "architecture_hash"})
    return result


def write_architecture_freeze(selection_hash: str) -> dict[str, Any]:
    result = architecture_freeze(selection_hash)
    write_json(OUT / "architecture-freeze.json", result)
    return result


def packet_source_evidence(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
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


def story_excerpt(packet: Mapping[str, Any]) -> str:
    rows = packet_source_evidence(packet)
    main = [text(row.get("text")) for row in rows if text(row.get("source_layer")) == "main_text"]
    return main[0] if main else (text(rows[0].get("text")) if rows else "")
