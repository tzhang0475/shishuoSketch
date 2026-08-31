"""Frozen A2 inputs and deterministic, language-neutral helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from sfh2_a0r_l.common import (
    CHALLENGE_STORIES,
    a0_selection,
    build_case_packet as _build_case_packet,
    load_inputs as _load_inputs,
    selection as challenge_selection,
)

ROOT = Path(__file__).resolve().parents[2]
A1R_L_ROOT = ROOT / "data/generated/sfh2-a0r-l"
A1R_LIVE_ROOT = A1R_L_ROOT / "live/sfh2-a0r-l-host-live-v1"
OUT = ROOT / "data/generated/sfh2-a2"
MODEL = "deepseek-v4-flash"
PILOT_VERSION = "sfh2-a2-v1"
SCHEMA_VERSION = "sfh2-a2-v1"
STRICT_ENDPOINT = "https://api.deepseek.com/beta/chat/completions"
MAX_PROVIDER_ATTEMPTS = 70
PROMPT_VERSIONS = {
    "historian_b": "sfh2-a2-independent-historian-v1",
    "adjudicator": "sfh2-a2-disagreement-adjudicator-v1",
}
FUNCTION_NAMES = {
    "historian_b": "submit_sfh2_a2_independent_historian_v1",
    "adjudicator": "submit_sfh2_a2_disagreement_adjudication_v1",
}


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


def load_inputs() -> dict[str, Any]:
    return _load_inputs()


def cases_by_cohort() -> dict[str, list[dict[str, Any]]]:
    return {
        "regression": [dict(row) for row in (a0_selection().get("cases", []) or []) if isinstance(row, Mapping)],
        "challenge": [dict(row) for row in (challenge_selection().get("cases", []) or []) if isinstance(row, Mapping)],
    }


def build_case_packet(case: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    """Build the frozen source packet without A output, flags, or gold."""

    packet = dict(_build_case_packet(case, inputs))
    packet["a2_authority"] = "independent_llm_semantics_python_structural_comparison_only"
    packet["gold_visible_to_model"] = False
    packet["candidate_only"] = True
    packet["canonical_write_back"] = False
    return packet


def provider_source_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Return the only source material permitted in Historian B's prompt."""

    return {
        "source_evidence": json.loads(json.dumps(packet.get("source_evidence", []), ensure_ascii=False)),
        "validated_local_mentions": json.loads(json.dumps(packet.get("validated_local_mentions", []), ensure_ascii=False)),
        "target": json.loads(json.dumps(packet.get("target", {}), ensure_ascii=False)),
        "story_id": packet.get("story_id"),
    }


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
        A1R_L_ROOT / "regression-selection.json",
        A1R_L_ROOT / "challenge-selection.json",
        A1R_L_ROOT / "challenge-selection-hash.json",
        A1R_L_ROOT / "architecture-freeze.json",
        A1R_L_ROOT / "cache-index.json",
        A1R_LIVE_ROOT / "transport.json",
    ]
    return {
        str(path.relative_to(ROOT)): file_hash(path)
        for path in paths
        if path.is_file()
    }


def selection_hashes(cases: Mapping[str, list[Mapping[str, Any]]]) -> dict[str, str]:
    return {
        cohort: stable_hash([dict(row) for row in rows])
        for cohort, rows in cases.items()
    }


def architecture_freeze(cases: Mapping[str, list[Mapping[str, Any]]]) -> dict[str, Any]:
    from . import contracts, pipeline
    from sfh2_a0r import contracts as a0r_contracts
    from sfh2_a0r import pipeline as a0r_pipeline

    code_paths = [
        ROOT / "scripts/sfh2_a2/common.py",
        ROOT / "scripts/sfh2_a2/contracts.py",
        ROOT / "scripts/sfh2_a2/comparison.py",
        ROOT / "scripts/sfh2_a2/evaluation.py",
        ROOT / "scripts/sfh2_a2/pipeline.py",
        ROOT / "scripts/sfh2_a2/transport.py",
    ]
    code_files = {
        str(path.relative_to(ROOT)): file_hash(path)
        for path in code_paths
        if path.is_file()
    }
    a0r_freeze = read_json(A1R_L_ROOT / "architecture-freeze.json", {}) or {}
    result: dict[str, Any] = {
        "schema": "sfh2-a2-architecture-freeze-v1",
        "pilot": "SFH2.2-A2",
        "baseline_commit": "51a07a9d5fb108c13748b7983d64a81181f86be6",
        "historian_a_source": "A1 cached live Primary Historian",
        "a1r_l_architecture_hash": a0r_freeze.get("architecture_hash"),
        "selection_hashes": selection_hashes(cases),
        "challenge_story_list_hash": stable_hash(list(CHALLENGE_STORIES)),
        "model_config": {
            "historian_b_model": MODEL,
            "adjudicator_model": __import__("os").environ.get("SFH2_ADJUDICATOR_MODEL") or MODEL,
            "temperature": 0,
            "thinking": {"type": "disabled"},
            "endpoint": STRICT_ENDPOINT,
            "prompt_versions": dict(PROMPT_VERSIONS),
            "function_names": dict(FUNCTION_NAMES),
            "max_provider_attempts": MAX_PROVIDER_ATTEMPTS,
            "retry_policy": "transient_only_at_most_one_retry; HTTP400_not_retryable",
        },
        "prompt_hashes": {
            "historian_b": stable_hash(pipeline.HISTORIAN_B_SYSTEM),
            "adjudicator": stable_hash(pipeline.ADJUDICATOR_SYSTEM),
        },
        "schema_hashes": {
            "historian_b": stable_hash(contracts.historian_b_tool()),
            "adjudicator": stable_hash(contracts.adjudicator_tool()),
            "semantic_record": stable_hash(a0r_contracts.semantic_record_tool()),
        },
        "a0r_prompt_hashes": {
            "primary_historian": stable_hash(a0r_pipeline.PRIMARY_HISTORIAN_SYSTEM),
        },
        "code_files": code_files,
        "authority_policy": "reviewed human semantics > LLM semantics > soft consistency > deterministic retrieval hints",
        "historian_b_is_independent": True,
        "historian_b_receives_no_historian_a": True,
        "historian_b_receives_no_python_flags": True,
        "gold_not_in_provider_packets": True,
        "candidate_only": True,
        "canonical_write_back": False,
        "no_full_188_story_live_run": True,
        "input_hashes": input_hashes(),
    }
    result["architecture_hash"] = stable_hash({key: value for key, value in result.items() if key != "architecture_hash"})
    return result
