"""Frozen inputs and language-neutral A2R helpers.

The A2R stage is deliberately isolated from the immutable A2 artifacts.  It
reuses A2's source packets and semantic cache, while writing its own transport
cache and derived records.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from sfh2_a2.common import CHALLENGE_STORIES, build_case_packet, cases_by_cohort, load_inputs, provider_source_packet

ROOT = Path(__file__).resolve().parents[2]
A2_ROOT = ROOT / "data/generated/sfh2-a2"
OUT = ROOT / "data/generated/sfh2-a2r"
MODEL = "deepseek-v4-flash"
PILOT_VERSION = "sfh2-a2r-v1"
SCHEMA_VERSION = "sfh2-a2r-v2"
STRICT_ENDPOINT = "https://api.deepseek.com/beta/chat/completions"
MAX_PROVIDER_ATTEMPTS = 45
PROMPT_VERSIONS = {
    # This value is intentionally the A2 value: the four B replacement calls
    # use exactly the frozen A2 semantic setup.
    "historian_b_recovery": "sfh2-a2-independent-historian-v1",
    "adjudicator": "sfh2-a2r-adjudicator-v2",
    "schema_probe": "sfh2-a2r-adjudicator-schema-probe-v1",
}
FUNCTION_NAMES = {
    "historian_b_recovery": "submit_sfh2_a2_independent_historian_v1",
    "adjudicator": "submit_sfh2_a2r_adjudication_v2",
    "schema_probe": "submit_sfh2_a2r_adjudication_v2",
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


def a2_artifact_hashes() -> dict[str, str]:
    return {
        str(path.relative_to(ROOT)): file_hash(path)
        for path in sorted(A2_ROOT.rglob("*"))
        if path.is_file() and "/raw-api/" not in path.as_posix()
    }


def a2_raw_hashes() -> dict[str, str]:
    raw = A2_ROOT / "live/sfh2-a2-live-v1/raw-api"
    return {
        str(path.relative_to(ROOT)): file_hash(path)
        for path in sorted(raw.glob("*.json"))
        if path.is_file()
    }


def input_hashes() -> dict[str, str]:
    paths = [
        ROOT / "data/generated/sfh2/story-packets.json",
        ROOT / "data/generated/sfh1/validated-mentions.json",
        ROOT / "data/generated/sfh1/reference-semantics.json",
        ROOT / "data/generated/sfh1/candidate-sets.json",
        ROOT / "data/generated/sfh1/identity-judgments.json",
        ROOT / "data/generated/sfh1/final-decisions.json",
        ROOT / "data/people.json",
        ROOT / "data/aliases.json",
        ROOT / "data/derived/hdb2-f-person-knowledge.json",
        ROOT / "data/generated/hda2/repair-overlay.json",
    ]
    return {
        str(path.relative_to(ROOT)): file_hash(path)
        for path in paths
        if path.is_file()
    }


def selection_hashes(cases: Mapping[str, list[Mapping[str, Any]]]) -> dict[str, str]:
    return {cohort: stable_hash([dict(row) for row in rows]) for cohort, rows in cases.items()}


def architecture_freeze(cases: Mapping[str, list[Mapping[str, Any]]]) -> dict[str, Any]:
    from . import contracts, pipeline
    from sfh2_a0r import contracts as a0r_contracts

    code_paths = [
        ROOT / "scripts/sfh2_a2r/common.py",
        ROOT / "scripts/sfh2_a2r/contracts.py",
        ROOT / "scripts/sfh2_a2r/transport.py",
        ROOT / "scripts/sfh2_a2r/pipeline.py",
        ROOT / "scripts/sfh2_a2r/evaluation.py",
    ]
    code_files = {
        str(path.relative_to(ROOT)): file_hash(path)
        for path in code_paths
        if path.is_file()
    }
    result: dict[str, Any] = {
        "schema": "sfh2-a2r-architecture-freeze-v1",
        "pilot": "SFH2.2-A2R",
        "baseline_commit": "32e5081d57766f43456becfcb340206acae1f950",
        "historian_a_source": "A2 immutable cached Historian A / A1 Primary",
        "historian_b_source": "A2 immutable valid B cache; four malformed B witnesses eligible for one replacement call",
        "selection_hashes": selection_hashes(cases),
        "challenge_story_list_hash": stable_hash(list(CHALLENGE_STORIES)),
        "model_config": {
            "historian_b_recovery_model": MODEL,
            "adjudicator_model": os.environ.get("SFH2_ADJUDICATOR_MODEL") or MODEL,
            "temperature": 0,
            "thinking": {"type": "disabled"},
            "endpoint": STRICT_ENDPOINT,
            "prompt_versions": dict(PROMPT_VERSIONS),
            "function_names": dict(FUNCTION_NAMES),
            "max_provider_attempts": MAX_PROVIDER_ATTEMPTS,
            "max_historian_b_recovery_calls": 4,
            "retry_policy": "transient_only_at_most_one_retry; HTTP400_not_retryable",
        },
        "prompt_hashes": {
            "historian_b_recovery": stable_hash(pipeline.HISTORIAN_B_SYSTEM),
            "adjudicator": stable_hash(pipeline.ADJUDICATOR_SYSTEM),
        },
        "schema_hashes": {
            "historian_b": stable_hash(contracts.historian_b_tool()),
            "adjudicator": stable_hash(contracts.adjudicator_tool()),
            "semantic_record": stable_hash(a0r_contracts.semantic_record_tool()),
        },
        "code_files": code_files,
        "a2_artifact_hashes": a2_artifact_hashes(),
        "a2_raw_hashes": a2_raw_hashes(),
        "input_hashes": input_hashes(),
        "authority_policy": "reviewed human semantics > LLM semantics > soft consistency > deterministic retrieval hints",
        "candidate_only": True,
        "canonical_write_back": False,
        "no_full_188_story_live_run": True,
    }
    result["architecture_hash"] = stable_hash({key: value for key, value in result.items() if key != "architecture_hash"})
    return result
