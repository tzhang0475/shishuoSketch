"""Frozen inputs and deterministic helpers for the A0R closeout pilot."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from sfh2_a0.common import build_case_packet as _build_case_packet
from sfh2_a0.common import input_hashes as _a0_input_hashes
from sfh2_a0.common import load_inputs as _load_inputs

ROOT = Path(__file__).resolve().parents[2]
A0_OUT = ROOT / "data/generated/sfh2-a0"
OUT = ROOT / "data/generated/sfh2-a0r"
SELECTION_PATH = ROOT / "data/annotation/sfh2-a0-selection.json"
GOLD_PATH = ROOT / "data/annotation/sfh2-a0-evaluation-gold.json"

MODEL = "deepseek-v4-flash"
# The live provider was unavailable during the first attempt.  A subsequent
# purely mechanical replay-contract fix (substantive-vs-metadata routing and
# compatibility-row provenance) is an explicit protocol restart, so it gets a
# new cache namespace while retaining the frozen prompts and schemas.
PILOT_VERSION = "sfh2-a0r-v2"
PROTOCOL_REVISION = "sfh2-a0r-contract-repair-v2"
SCHEMA_VERSION = "sfh2-a0r-v1"
STRICT_ENDPOINT = "https://api.deepseek.com/beta/chat/completions"
PROMPT_VERSIONS = {
    "primary_historian": "sfh2-a0r-primary-historian-v1",
    "critical_reviewer": "sfh2-a0r-critical-reviewer-patch-v1",
    "adjudicator": "sfh2-a0r-adjudicator-selector-patch-v1",
}
FUNCTION_NAMES = {
    "primary_historian": "submit_sfh2_a0r_primary_semantics_v1",
    "critical_reviewer": "submit_sfh2_a0r_critical_review_patch_v1",
    "adjudicator": "submit_sfh2_a0r_adjudication_selector_v1",
}
MAX_PROVIDER_ATTEMPTS = 45


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


def normalize(value: Any) -> str:
    # Normalization is only used for deterministic representation comparison.
    # It is not an identity rule and never selects a historical answer.
    translation = str.maketrans({"爲": "為", "髙": "高", "鳯": "鳳", "臺": "台", "裏": "裡", "禄": "祿", "隱": "隐", "獻": "献", "綽": "绰"})
    return re.sub(r"\s+", "", text(value)).translate(translation)


def load_inputs() -> dict[str, Any]:
    return _load_inputs()


def build_case_packet(case: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Reuse the frozen A0 L0 packet builder without adding evaluation data."""

    packet = dict(_build_case_packet(case, inputs))
    packet["a0r_authority"] = "llm_semantics_python_consistency_and_storage"
    packet["gold_visible_to_model"] = False
    packet["candidate_only"] = True
    packet["canonical_write_back"] = False
    return packet


def selection() -> dict[str, Any]:
    return read_json(SELECTION_PATH, {}) or {}


def gold() -> dict[str, Any]:
    return read_json(GOLD_PATH, {}) or {}


def input_hashes() -> dict[str, str]:
    """Hash the frozen A0 inputs and protected source data used by A0R."""

    result = dict(_a0_input_hashes())
    paths = [
        A0_OUT / "selection.json",
        A0_OUT / "case-packets.json",
        A0_OUT / "pass1-semantic-results.json",
        A0_OUT / "pass2-review-results.json",
        A0_OUT / "pass3-adjudication-results.json",
        A0_OUT / "final-decisions.json",
        A0_OUT / "evaluation.json",
        GOLD_PATH,
    ]
    for path in paths:
        if path.is_file():
            result[str(path.relative_to(ROOT))] = file_hash(path)
    return dict(sorted(result.items()))


def architecture_freeze(selection_hash: str) -> dict[str, Any]:
    """Return the immutable A0R protocol fingerprint."""

    from . import contracts, consistency, pipeline

    code_paths = [
        ROOT / "scripts/sfh2_a0r/common.py",
        ROOT / "scripts/sfh2_a0r/contracts.py",
        ROOT / "scripts/sfh2_a0r/consistency.py",
        ROOT / "scripts/sfh2_a0r/pipeline.py",
        ROOT / "scripts/sfh2_a0r/transport.py",
    ]
    code_files = {
        str(path.relative_to(ROOT)): file_hash(path)
        for path in code_paths
        if path.is_file()
    }
    result: dict[str, Any] = {
        "schema": "sfh2-a0r-architecture-freeze-v1",
        "pilot": "SFH2.2-A0R",
        "protocol_revision": PROTOCOL_REVISION,
        "baseline_a0": "6155ff28a717dcacbd88525dc1e3dc94216b31ef",
        "selection_hash": selection_hash,
        "model_config": {
            "model": MODEL,
            "temperature": 0,
            "thinking": {"type": "disabled"},
            "endpoint": STRICT_ENDPOINT,
            "prompt_versions": dict(PROMPT_VERSIONS),
            "function_names": dict(FUNCTION_NAMES),
            "max_provider_attempts": MAX_PROVIDER_ATTEMPTS,
        },
        "prompt_hashes": {
            "primary_historian": stable_hash(pipeline.PRIMARY_HISTORIAN_SYSTEM),
            "critical_reviewer": stable_hash(pipeline.CRITICAL_REVIEWER_SYSTEM),
            "adjudicator": stable_hash(pipeline.ADJUDICATOR_SYSTEM),
        },
        "schema_hashes": {
            "semantic_record": stable_hash(contracts.semantic_record_tool()),
            "critical_review": stable_hash(contracts.critical_review_tool()),
            "adjudication": stable_hash(contracts.adjudication_tool()),
        },
        "code_files": code_files,
        "consistency_engine_contract": consistency.CONSISTENCY_CONTRACT,
        "authority_policy": "reviewed human semantic decision > validated LLM semantic judgment > soft collective consistency > deterministic retrieval hint",
        "selection_is_frozen": True,
        "candidate_only": True,
        "canonical_write_back": False,
    }
    result["input_hashes"] = input_hashes()
    result["architecture_hash"] = stable_hash({key: value for key, value in result.items() if key != "architecture_hash"})
    return result
