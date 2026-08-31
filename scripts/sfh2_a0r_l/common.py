"""Frozen inputs and deterministic helpers for the A0R-L pilot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from sfh2_a0.common import build_case_packet as _build_case_packet
from sfh2_a0.common import load_inputs as _load_inputs
from sfh2_a0.common import records as _records
from sfh2_a0.common import text

ROOT = Path(__file__).resolve().parents[2]
BASELINE_COMMIT = "3f58058a833f6b7564a91c3d94ca69f14ec50774"
A0R_ROOT = ROOT / "data/generated/sfh2-a0r"
OUT = ROOT / "data/generated/sfh2-a0r-l"
A0_SELECTION_PATH = ROOT / "data/annotation/sfh2-a0-selection.json"
CHALLENGE_SELECTION_PATH = ROOT / "data/annotation/sfh2-a0r-l-challenge-selection.json"
MODEL = "deepseek-v4-flash"
PILOT_VERSION = "sfh2-a0r-l-v1"
SCHEMA_VERSION = "sfh2-a0r-l-v1"
STRICT_ENDPOINT = "https://api.deepseek.com/beta/chat/completions"
MAX_PROVIDER_ATTEMPTS = 80
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

CHALLENGE_STORIES = (
    "09-pinzao-063",
    "25-paidiao-015",
    "21-qiaoyi-011",
    "10-guizhen-011",
    "02-yanyu-060",
)


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


def records(document: Any, *keys: str) -> list[dict[str, Any]]:
    return _records(document, *(keys or ("records",)))


def load_inputs() -> dict[str, Any]:
    return _load_inputs()


def build_case_packet(case: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Build the frozen A0 L0 packet for either cohort."""

    packet = dict(_build_case_packet(case, inputs))
    packet["a0r_l_authority"] = "llm_semantics_python_formal_checks_and_storage"
    packet["gold_visible_to_model"] = False
    packet["candidate_only"] = True
    packet["canonical_write_back"] = False
    return packet


def selection(path: Path = CHALLENGE_SELECTION_PATH) -> dict[str, Any]:
    return read_json(path, {}) or {}


def a0_selection() -> dict[str, Any]:
    return read_json(A0_SELECTION_PATH, {}) or {}


def a0r_freeze() -> dict[str, Any]:
    return read_json(A0R_ROOT / "architecture-freeze.json", {}) or {}


def input_hashes() -> dict[str, str]:
    paths = [
        ROOT / "data/generated/sfh1/story-packets.json",
        ROOT / "data/generated/sfh1/validated-mentions.json",
        ROOT / "data/generated/sfh1/reference-semantics.json",
        ROOT / "data/generated/sfh1/candidate-sets.json",
        ROOT / "data/generated/sfh1/identity-judgments.json",
        ROOT / "data/generated/sfh1/final-decisions.json",
        ROOT / "data/generated/sfh1/relation-assertions.json",
        ROOT / "data/people.json",
        ROOT / "data/aliases.json",
        ROOT / "data/derived/hdb2-f-person-knowledge.json",
        ROOT / "data/derived/hdb2-f-candidate-person-knowledge.json",
        ROOT / "data/generated/hda2/repair-overlay.json",
        A0_SELECTION_PATH,
        ROOT / "data/annotation/sfh2-a0-evaluation-gold.json",
        A0R_ROOT / "architecture-freeze.json",
        A0R_ROOT / "pass1-semantic-results.json",
        A0R_ROOT / "pass2-review-decisions.json",
        A0R_ROOT / "pass3-adjudication-decisions.json",
        A0R_ROOT / "final-decisions.json",
    ]
    return {
        str(path.relative_to(ROOT)): file_hash(path)
        for path in paths
        if path.is_file()
    }


def architecture_freeze(regression_selection_hash: str, challenge_selection_hash: str) -> dict[str, Any]:
    """Fingerprint the frozen A0R protocol and the two A0R-L cohorts."""

    from sfh2_a0r import contracts, consistency, pipeline

    a0r_arch = a0r_freeze()
    code_paths = [
        ROOT / "scripts/sfh2_a0r_l/common.py",
        ROOT / "scripts/sfh2_a0r_l/selection.py",
        ROOT / "scripts/sfh2_a0r_l/consistency.py",
        ROOT / "scripts/sfh2_a0r_l/transport.py",
        ROOT / "scripts/sfh2_a0r_l/pipeline.py",
    ]
    code_files = {
        str(path.relative_to(ROOT)): file_hash(path)
        for path in code_paths
        if path.is_file()
    }
    result: dict[str, Any] = {
        "schema": "sfh2-a0r-l-architecture-freeze-v1",
        "pilot": "SFH2.2-A0R-L",
        "baseline_commit": BASELINE_COMMIT,
        "a0r_architecture_hash": a0r_arch.get("architecture_hash"),
        "a0r_protocol_revision": a0r_arch.get("protocol_revision"),
        "regression_selection_hash": regression_selection_hash,
        "challenge_selection_hash": challenge_selection_hash,
        "challenge_story_list_hash": stable_hash(list(CHALLENGE_STORIES)),
        "model_config": {
            "model": MODEL,
            "temperature": 0,
            "thinking": {"type": "disabled"},
            "endpoint": STRICT_ENDPOINT,
            "prompt_versions": dict(PROMPT_VERSIONS),
            "function_names": dict(FUNCTION_NAMES),
            "max_provider_attempts": MAX_PROVIDER_ATTEMPTS,
            "retry_policy": "at_most_one_retry_per_logical_call",
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
        "a0r_code_hashes": a0r_arch.get("code_files", {}),
        "code_files": code_files,
        "consistency_engine_contract": consistency.CONSISTENCY_CONTRACT,
        "authority_policy": "reviewed human semantics > validated LLM semantics > soft consistency > deterministic retrieval hints",
        "selection_is_frozen": True,
        "gold_not_in_provider_packets": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "no_full_188_story_live_run": True,
        "input_hashes": input_hashes(),
    }
    result["architecture_hash"] = stable_hash({key: value for key, value in result.items() if key != "architecture_hash"})
    return result
