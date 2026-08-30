"""Inputs and deterministic helpers for the isolated SFH2.2-P1 pilot.

The package deliberately reuses the frozen SFH1/SFH2.2-P packet preparation
code, but owns its selection, cache, outputs, prompts, and schemas.  The
existing SFH2.2-P artifacts are read-only inputs to this experiment.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from sfh2_2p.common import (
    build_case_packet as _build_case_packet,
    evidence_index,
    file_hash,
    load_inputs as _load_inputs,
    mention_index,
    packet_index,
    records,
    text,
)

ROOT = Path(__file__).resolve().parents[2]
SFH1_ROOT = ROOT / "data/generated/sfh1"
P_ROOT = ROOT / "data/generated/sfh2-2p"
OUT = ROOT / "data/generated/sfh2-2p1"
SELECTION_PATH = ROOT / "data/annotation/sfh2-2p1-selection.json"
MODEL = "deepseek-v4-flash"
PILOT_VERSION = "sfh2-2p1-v4"
SCHEMA_VERSION = "sfh2-2p1-v1"
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


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_inputs() -> dict[str, Any]:
    inputs = _load_inputs()
    inputs.update({
        "p_selection": read_json(P_ROOT / "selection.json", {}) or {},
        "p_candidate_sets": read_json(P_ROOT / "candidate-sets.json", {}) or {},
        "p_final": read_json(P_ROOT / "final-decisions.json", {}) or {},
        "p_l3": read_json(P_ROOT / "l3-semantic-results.json", {}) or {},
        "p_metrics": read_json(P_ROOT / "metrics.json", {}) or {},
    })
    return inputs


def build_case_packet(case: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    # SFH2.2-P's packet builder is deterministic L0 preparation.  It does not
    # include gold fields, and its source/evidence hashes remain frozen inputs.
    return _build_case_packet(case, inputs)


def input_hashes(inputs: Mapping[str, Any]) -> dict[str, str]:
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
    ]
    result = {}
    for path in paths:
        if path.is_file():
            result[str(path.relative_to(ROOT))] = file_hash(path)
    return dict(sorted(result.items()))


def exact_span(mention: Mapping[str, Any], packet: Mapping[str, Any]) -> str:
    source = evidence_index(packet).get(text(mention.get("source_evidence_id")), {})
    value = text(source.get("text"))
    start, end = mention.get("source_start"), mention.get("source_end")
    if isinstance(start, int) and isinstance(end, int) and 0 <= start <= end <= len(value):
        return value[start:end]
    return text(mention.get("surface"))
