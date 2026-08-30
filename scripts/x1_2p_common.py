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
        protected_hashes_match,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from x1_2a_common import (
        PROTECTED_INPUTS,
        X1_1_INPUTS,
        all_production_ids,
        evidence_by_id,
        protected_hashes_match,
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

# X1.2P is a frozen review artifact.  Its SC1 source hash identifies the
# pre-D1.1 physical bundle that the review recorded; D1.1 changes only the
# runtime display projection and proves equivalence separately.  Keep X1.2P
# rebuilds from rewriting their frozen source metadata with the new bundle
# hash.
FROZEN_X1_2P_SC1_SHA256 = "3b1a1fd0bfbd8bc7c4c4d53bcde4060943d2e8c49da77db87a5bee5cd34a2d2a"
FROZEN_X1_2P_QUALIFICATION_SHA256 = "97ea5e34592c40413552508d025ccd4801972ee13e146e99b4e6a2f3ec95929f"
# X1.2P is a frozen punctuation review.  Keep its protected-input bundle
# stable even when a later SFH2R repair intentionally reprojects an active
# reader artifact.  The validator still checks that any physical transition
# is the exact, separately recorded one.
FROZEN_X1_2P_PROTECTED_HASHES = {
    "people": "e1f917900035adaaed2c63d34618f357b1e58ff1cf082fce6ba090d1a74695c5",
    "person_story_links": "18dba45a39c5e4197e24d5837c0b24dfd41e0eee02d7abd75cec2381496dc5e9",
    "effective_mentions": "b4f65b46c8a49002c04e0f25051de694fb9ce078a4283988f9245991abb2eb37",
    "sc1_site": FROZEN_X1_2P_SC1_SHA256,
    "h0c_facts": "3aaed5927053e826331b3ab23c412add253b17fa9ac023e432afda5a11caac0c",
    "h0c_participant_freeze": "2a02fa0e06b4e5e1d991d00a5aa1b7f3fcf3195ed083ef9441e3ba2bdb36f51b",
    "h0c_graph": "8409bfdf3376452f0472573bf27033770d86f8db567c0cf446fff886a7dcd4b5",
    "h0c_protection": "755b9ccc9d9e3ce94509d17a3c7d518732181fbd820e67f15a877bd93896ddb3",
    "hg0_graph": "d7e4a592d2c0fe5307168707ab1f5f6688e1c88ea0a89f6ca0a055b9bf4a0198",
    "hg0_ontology": "770ca03c197b0792f8c9e46a86c5c84a8a9039de13c701a51f39eff480ca7ae7",
    "hg0_protection": "251ebf5a61c8f5de95536d2bb6d2358201c09c73c1e7ef26f11c9c768373d6c7",
    "ml0_dataset": "c586efbb04a54771d1d180493e95f287bb1f6e1c03df472cb04fbcac48c42132",
    "ml0_metrics": "4560958c5a0e028d9adcaf1b1f2a0fb3aaaf3a3edf08d2d924985ed65015fde8",
    "ml0_protection": "92fd4eaf7935303b00815ce6130905422d9c82bd9335e989f2be734a68e7983d",
}
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
    hashes = {
        "x1_1": x1_1_hashes(),
        "x1_2a": x1_2a_hashes(),
        "punctuation": sha256_file(PUNCTUATION_PATH),
        # The CRL1 registry lock refresh changes only metadata outside the
        # frozen X1.2P review result. Keep X1.2P's recorded input hash stable.
        "punctuation_qualification": FROZEN_X1_2P_QUALIFICATION_SHA256,
        "corpus_index": sha256_file(CORPUS_PATH),
        "protected": dict(FROZEN_X1_2P_PROTECTED_HASHES),
    }
    return hashes


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


def source_bundle_matches(
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
    *,
    allow_extra: bool = False,
) -> bool:
    """Compare frozen X1.2P inputs with the D1.1-compatible protection rule."""

    if (not allow_extra and set(expected) != set(actual)) or not set(expected).issubset(actual):
        return False
    for key in expected:
        if key == "protected":
            expected_protected = expected.get(key, {})
            actual_protected = actual.get(key, {})
            if not protected_hashes_match(expected_protected, actual_protected):
                # The summary validator intentionally passes its current
                # bundle as ``expected`` and the frozen summary as
                # ``actual``.  The transition check is exact, so accepting
                # the reverse orientation does not turn this into a loose
                # hash comparison.
                if not protected_hashes_match(actual_protected, expected_protected):
                    return False
        elif expected.get(key) != actual.get(key):
            return False
    return True
