#!/usr/bin/env python3
"""Shared deterministic inputs and paths for X1.2P punctuation review."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from scripts.x1_2a_common import (
        PROTECTED_INPUTS,
        X1_1_INPUTS,
        all_production_ids,
        evidence_by_id,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from x1_2a_common import (
        PROTECTED_INPUTS,
        X1_1_INPUTS,
        all_production_ids,
        evidence_by_id,
    )


ROOT = Path(__file__).resolve().parents[1]

PUNCTUATION_PATH = Path("data/annotation/wp1-punctuation.json")
QUALIFICATION_PATH = Path("data/reading-source-qualification.json")
CORPUS_PATH = Path("data/shishuo-corpus-index.json")

X1_2A_INPUTS = {
    "review_manifest": Path("data/derived/x1-2a-review-manifest.json"),
    "story_review": Path("data/derived/x1-2a-story-review.json"),
    "person_review": Path("data/derived/x1-2a-person-review.json"),
    "fact_review": Path("data/derived/x1-2a-fact-review.json"),
    "ontology_review": Path("data/derived/x1-2a-ontology-gap-review.json"),
    "materialization": Path("data/derived/x1-2a-materialization-manifest.json"),
    "canonical_facts": Path("data/derived/x1-2a-canonical-facts.json"),
}

OUTPUT_DIR = Path("data/derived")
GATE_AUDIT_PATH = OUTPUT_DIR / "x1-2p-punctuation-gate-audit.json"
STORY_REVIEW_PATH = OUTPUT_DIR / "x1-2p-story-review.json"
DEPENDENCY_PATH = OUTPUT_DIR / "x1-2p-dependency-audit.json"
ELIGIBILITY_PATH = OUTPUT_DIR / "x1-2p-rematerialization-eligibility.json"
CHANNEL_PATH = OUTPUT_DIR / "x1-2p-channel-audit.json"
READINESS_PATH = OUTPUT_DIR / "x1-2p-candidate-punctuation-readiness.json"
NEXT_STEP_PATH = OUTPUT_DIR / "x1-2p-next-step-recommendation.json"
SUMMARY_PATH = OUTPUT_DIR / "x1-2p-summary.json"

EPOCH = "X1.2P"
SELECTED_STORY_COUNT = 20
TOP_LEVEL_STATES = {"accepted", "unresolved", "rejected"}
CHANNELS = ("graph_guided", "coverage_guided", "stratified_random", "counter_model")


def read(path: Path | str) -> Any:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def write(path: Path | str, value: Any) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with (ROOT / path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def stable_id(prefix: str, *parts: object) -> str:
    material = "|".join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(material.encode('utf-8')).hexdigest()[:20]}"


def unique(values: Iterable[object]) -> list[str]:
    return sorted({str(value) for value in values if value is not None and str(value)})


def x1_1_hashes() -> dict[str, str]:
    return {name: sha256_file(path) for name, path in X1_1_INPUTS.items()}


def x1_2a_hashes() -> dict[str, str]:
    return {name: sha256_file(path) for name, path in X1_2A_INPUTS.items()}


def protected_hashes() -> dict[str, str]:
    return {
        name: sha256_file(path)
        for name, path in PROTECTED_INPUTS.items()
        if (ROOT / path).is_file()
    }


def source_hashes() -> dict[str, Any]:
    return {
        "x1_1": x1_1_hashes(),
        "x1_2a": x1_2a_hashes(),
        "punctuation": sha256_file(PUNCTUATION_PATH),
        "punctuation_qualification": sha256_file(QUALIFICATION_PATH),
        "corpus_index": sha256_file(CORPUS_PATH),
        "protected": protected_hashes(),
    }


def selection_manifest() -> dict[str, Any]:
    document = read(X1_1_INPUTS["selection_manifest"])
    if document.get("selection_status") != "frozen":
        raise ValueError("X1.1 selection is not frozen")
    if document.get("frozen_before_enrichment") is not True:
        raise ValueError("X1.1 selection freeze flag is missing")
    if len(document.get("records", [])) != SELECTED_STORY_COUNT:
        raise ValueError("X1.1 selection does not contain exactly 20 Stories")
    return document


def selection_by_story() -> dict[str, dict[str, Any]]:
    return {
        str(row["story_id"]): dict(row)
        for row in selection_manifest().get("records", [])
        if isinstance(row, Mapping) and row.get("story_id")
    }


def punctuation_by_story() -> dict[str, dict[str, Any]]:
    return {
        str(row["entry_id"]): dict(row)
        for row in read(PUNCTUATION_PATH).get("records", [])
        if isinstance(row, Mapping) and row.get("entry_id")
    }


def corpus_by_story() -> dict[str, dict[str, Any]]:
    return {
        str(row["id"]): dict(row)
        for row in read(CORPUS_PATH).get("entries", [])
        if isinstance(row, Mapping) and row.get("id")
    }


def x1_2a_documents() -> dict[str, Any]:
    return {name: read(path) for name, path in X1_2A_INPUTS.items()}


def x1_2a_review_by_story() -> dict[str, dict[str, Any]]:
    return {
        str(row["story_id"]): dict(row)
        for row in read(X1_2A_INPUTS["story_review"]).get("records", [])
        if isinstance(row, Mapping) and row.get("story_id")
    }


def evidence_refs_for_ids(evidence_ids: Iterable[object]) -> list[dict[str, Any]]:
    evidence = evidence_by_id()
    refs = []
    for evidence_id in unique(evidence_ids):
        row = evidence.get(evidence_id)
        if row is None:
            refs.append({"evidence_id": evidence_id, "valid": False})
            continue
        locator = row.get("locator", {}) if isinstance(row.get("locator"), Mapping) else {}
        provenance = locator.get("source_provenance", {}) if isinstance(locator.get("source_provenance"), Mapping) else {}
        refs.append({
            "evidence_id": evidence_id,
            "valid": True,
            "source_id": row.get("source_id"),
            "evidence_type": row.get("evidence_type"),
            "artifact_path": locator.get("artifact_path"),
            "entry_id": locator.get("entry_id"),
            "source_witness_id": provenance.get("witness_id"),
            "source_path": provenance.get("source_path"),
            "source_sha256": provenance.get("source_sha256"),
            "quote": row.get("quote"),
        })
    return refs


def production_ids() -> tuple[set[str], set[str]]:
    return all_production_ids()


def current_x1_2a_fact_hash() -> str:
    return sha256_file(X1_2A_INPUTS["canonical_facts"])


def current_ontology_hash() -> str:
    return sha256_file("data/derived/hg0-ontology.json")


def common_source_bundle() -> dict[str, Any]:
    return {
        **source_hashes(),
        "x1_2a_canonical_fact_hash": current_x1_2a_fact_hash(),
        "hg0_ontology_hash": current_ontology_hash(),
    }
