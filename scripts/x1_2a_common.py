#!/usr/bin/env python3
"""Shared inputs and deterministic helpers for X1.2A.

X1.2A is deliberately an evidence-review layer between the frozen X1.1
selection overlay and any future corpus/graph rebuild.  The module keeps the
input hashes explicit and never writes to H0C, HG0, ML0, or the production
Story/Person projections.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]

X1_1_INPUTS = {
    "candidate_pool": Path("data/derived/x1-1-candidate-pool.json"),
    "selection_manifest": Path("data/derived/x1-1-selection-manifest.json"),
    "review_results": Path("data/derived/x1-1-review-results.json"),
    "counter_model": Path("data/derived/x1-1-counter-model.json"),
    "ontology_gap_candidates": Path("data/derived/x1-1-ontology-gap-candidates.json"),
    "summary": Path("data/derived/x1-1-summary.json"),
    "information_gain": Path("data/derived/x1-1-information-gain.json"),
    "bias_audit": Path("data/derived/x1-1-bias-audit.json"),
    "next_epoch_recommendation": Path("data/derived/x1-1-next-epoch-recommendation.json"),
}

PROTECTED_INPUTS = {
    "people": Path("data/people.json"),
    "person_story_links": Path("data/derived/person-story-links.json"),
    "effective_mentions": Path("data/derived/person-resolution-effective.json"),
    "sc1_site": Path("data/derived/sc1-site.json"),
    "h0c_facts": Path("data/derived/h0c-historical-facts.json"),
    "h0c_participant_freeze": Path("data/derived/h0c-participant-freeze.json"),
    "h0c_graph": Path("data/derived/h0c-graph-projection.json"),
    "h0c_protection": Path("data/derived/h0c-protection-manifest.json"),
    "hg0_graph": Path("data/derived/hg0-graph-projection.json"),
    "hg0_ontology": Path("data/derived/hg0-ontology.json"),
    "hg0_protection": Path("data/derived/hg0-protection-manifest.json"),
    "ml0_dataset": Path("data/derived/ml0-dataset-manifest.json"),
    "ml0_metrics": Path("data/derived/ml0-metrics.json"),
    "ml0_protection": Path("data/derived/ml0-protection-manifest.json"),
}

CORPUS_PATH = Path("data/shishuo-corpus-index.json")
PUNCTUATION_PATH = Path("data/annotation/wp1-punctuation.json")
MENTIONS_PATH = Path("data/mentions/shishuo.json")
EVIDENCE_PATH = Path("data/evidence/wp1-evidence.json")

OUTPUT_DIR = Path("data/derived")
REVIEW_MANIFEST_PATH = OUTPUT_DIR / "x1-2a-review-manifest.json"
STORY_REVIEW_PATH = OUTPUT_DIR / "x1-2a-story-review.json"
PERSON_REVIEW_PATH = OUTPUT_DIR / "x1-2a-person-review.json"
FACT_REVIEW_PATH = OUTPUT_DIR / "x1-2a-fact-review.json"
ONTOLOGY_REVIEW_PATH = OUTPUT_DIR / "x1-2a-ontology-gap-review.json"
MATERIALIZATION_PATH = OUTPUT_DIR / "x1-2a-materialization-manifest.json"
CANONICAL_FACTS_PATH = OUTPUT_DIR / "x1-2a-canonical-facts.json"
CONFLICT_PATH = OUTPUT_DIR / "x1-2a-conflict-audit.json"
GAP_PATH = OUTPUT_DIR / "x1-2a-gap-audit.json"
REALIZED_YIELD_PATH = OUTPUT_DIR / "x1-2a-realized-yield.json"
BIAS_PATH = OUTPUT_DIR / "x1-2a-bias-audit.json"
COUNTER_MODEL_PATH = OUTPUT_DIR / "x1-2a-counter-model-audit.json"
NEXT_EPOCH_PATH = OUTPUT_DIR / "x1-2a-next-epoch-recommendation.json"
SUMMARY_PATH = OUTPUT_DIR / "x1-2a-summary.json"

EPOCH = "X1.2A"
SELECTION_EPOCH = "X1.1"


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
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def stable_id(prefix: str, *parts: object) -> str:
    material = "|".join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(material.encode('utf-8')).hexdigest()[:20]}"


def unique(values: Iterable[object]) -> list[str]:
    return sorted({str(value) for value in values if value is not None and str(value)})


def x1_1_hashes() -> dict[str, str]:
    return {name: sha256_file(path) for name, path in X1_1_INPUTS.items()}


def protected_hashes() -> dict[str, str]:
    return {
        name: sha256_file(path)
        for name, path in PROTECTED_INPUTS.items()
        if (ROOT / path).is_file()
    }


def protected_hashes_match(expected: Mapping[str, str], actual: Mapping[str, str]) -> bool:
    """Allow the D1.1 SC1 representation migration without weakening protection.

    D1.1 changes only the physical runtime display projection.  The dedicated
    semantic-equivalence validator proves that this one protected input is
    reader-equivalent to the frozen D1.0 bundle; every other protected hash
    must remain byte-identical.
    """

    if dict(expected) == dict(actual):
        return True
    if set(expected) != set(actual):
        return False
    mismatches = {key for key in expected if expected[key] != actual[key]}
    if mismatches != {"sc1_site"}:
        return False
    try:
        try:
            from scripts.validate_d1_1 import validate as validate_d1_1
        except ImportError:  # direct execution from scripts/
            from validate_d1_1 import validate as validate_d1_1
        return not validate_d1_1(ROOT)
    except (ImportError, OSError, ValueError, TypeError):
        return False


def load_x1_1() -> dict[str, Any]:
    values = {name: read(path) for name, path in X1_1_INPUTS.items()}
    selection = values["selection_manifest"]
    review = values["review_results"]
    ontology = values["ontology_gap_candidates"]
    if selection.get("selection_status") != "frozen":
        raise ValueError("X1.1 selection is not frozen")
    if selection.get("frozen_before_enrichment") is not True:
        raise ValueError("X1.1 selection freeze flag is missing")
    if review.get("source_selection_manifest_sha256") != sha256_file(X1_1_INPUTS["selection_manifest"]):
        raise ValueError("X1.1 review does not match the frozen selection manifest")
    if review.get("source_candidate_pool_sha256") != sha256_file(X1_1_INPUTS["candidate_pool"]):
        raise ValueError("X1.1 review does not match the frozen candidate pool")
    if ontology.get("source_hashes", {}).get("selection_manifest") != sha256_file(X1_1_INPUTS["selection_manifest"]):
        raise ValueError("X1.1 ontology candidates do not match the frozen selection")
    if ontology.get("source_hashes", {}).get("candidate_pool") != sha256_file(X1_1_INPUTS["candidate_pool"]):
        raise ValueError("X1.1 ontology candidates do not match the candidate pool")
    return values


def selection_by_story(selection: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["story_id"]): dict(row)
        for row in selection.get("records", [])
        if isinstance(row, Mapping) and row.get("story_id")
    }


def review_by_story(review: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["story_id"]): dict(row)
        for row in review.get("records", [])
        if isinstance(row, Mapping) and row.get("story_id")
    }


def candidate_by_story(pool: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["story_id"]): dict(row)
        for row in pool.get("records", [])
        if isinstance(row, Mapping) and row.get("story_id")
    }


def evidence_by_id() -> dict[str, dict[str, Any]]:
    return {
        str(row["id"]): dict(row)
        for row in read(EVIDENCE_PATH).get("records", [])
        if isinstance(row, Mapping) and row.get("id")
    }


def evidence_ref(evidence_id: str, evidence: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    row = evidence.get(evidence_id)
    if row is None:
        return {"evidence_id": evidence_id, "valid": False}
    locator = row.get("locator", {}) if isinstance(row.get("locator"), Mapping) else {}
    provenance = locator.get("source_provenance", {}) if isinstance(locator.get("source_provenance"), Mapping) else {}
    return {
        "evidence_id": evidence_id,
        "valid": True,
        "source_id": row.get("source_id"),
        "evidence_type": row.get("evidence_type"),
        "artifact_type": locator.get("artifact_type"),
        "artifact_path": locator.get("artifact_path"),
        "entry_id": locator.get("entry_id"),
        "unit_id": locator.get("unit_id"),
        "source_witness_id": provenance.get("witness_id"),
        "source_path": provenance.get("source_path"),
        "source_sha256": provenance.get("source_sha256"),
        "quote": row.get("quote"),
    }


def source_entry(story_id: str) -> dict[str, Any]:
    corpus = read(CORPUS_PATH)
    row = next((item for item in corpus.get("entries", []) if item.get("id") == story_id), None)
    if row is None:
        raise KeyError(f"unknown Story {story_id}")
    path = ROOT / str(row["path"])
    return {
        "story_id": story_id,
        "path": str(row["path"]),
        "sha256": str(row.get("entry_sha256") or sha256_file(row["path"])),
        "exists": path.is_file(),
        "global_ordinal": row.get("global_ordinal"),
        "chapter_id": row.get("chapter_id"),
        "chapter_heading": next(
            (chapter.get("heading", chapter.get("id")) for chapter in corpus.get("chapters", []) if chapter.get("id") == row.get("chapter_id")),
            row.get("chapter_id"),
        ),
    }


def punctuation_by_story() -> dict[str, dict[str, Any]]:
    return {
        str(row["entry_id"]): dict(row)
        for row in read(PUNCTUATION_PATH).get("records", [])
        if isinstance(row, Mapping) and row.get("entry_id")
    }


def mentions_by_story() -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in read(MENTIONS_PATH).get("mentions", []):
        if not isinstance(row, Mapping):
            continue
        story_id = row.get("entry_id") or row.get("source_id")
        if story_id:
            output[str(story_id)].append(dict(row))
    return dict(output)


def action_rows(review_record: Mapping[str, Any], action_name: str) -> list[dict[str, Any]]:
    return [
        dict(action)
        for action in review_record.get("actions", [])
        if isinstance(action, Mapping) and action.get("action") == action_name
    ]


def fact_candidates(review: Mapping[str, Any], selections: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for story_id in sorted(selections):
        record = review_by_story(review).get(story_id, {})
        for action in action_rows(record, "ADD_FACT"):
            action_evidence = unique(action.get("evidence_ids", []))
            for index, target in enumerate(action.get("targets", [])):
                if not isinstance(target, Mapping):
                    continue
                layer = str(target.get("layer"))
                rows.append({
                    "review_item_id": stable_id("x1-2a-fact-review", story_id, index, layer),
                    "source_candidate_id": f"{story_id}:ADD_FACT:{index:02d}:{layer}",
                    "story_id": story_id,
                    "candidate_index": index,
                    "review_type": "fact",
                    "fact_layer": layer,
                    "candidate_fact_types": list(target.get("candidate_fact_types", [])),
                    "candidate_reason": target.get("reason"),
                    "evidence_ids": action_evidence,
                    "selection_mode": selections[story_id].get("selection_mode"),
                    "selection_provenance": {
                        "selection_epoch": SELECTION_EPOCH,
                        "source_graph_version": "HG0",
                        "source_ml_version": "ML0",
                        "selection_rank": selections[story_id].get("selection_rank"),
                        "selection_score": selections[story_id].get("selection_score"),
                    },
                })
    return rows


def person_candidates(review: Mapping[str, Any], selections: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_story = review_by_story(review)
    mentions = mentions_by_story()
    for story_id in sorted(selections):
        record = by_story.get(story_id, {})
        for action in action_rows(record, "ADD_PERSON"):
            surfaces = [str(surface) for surface in action.get("surfaces", [])]
            for index, surface in enumerate(surfaces):
                occurrences = [
                    i for i, mention in enumerate(mentions.get(story_id, []))
                    if mention.get("surface") == surface
                ]
                rows.append({
                    "review_item_id": stable_id("x1-2a-person-review", story_id, surface, index),
                    "source_candidate_id": f"{story_id}:ADD_PERSON:{index:02d}:{surface}",
                    "story_id": story_id,
                    "surface": surface,
                    "occurrence_indexes": occurrences,
                    "related_production_person_ids": list(action.get("related_production_person_ids", [])),
                    "review_type": "person_identity",
                    "evidence_ids": unique(record.get("evidence_ids", [])),
                    "selection_mode": selections[story_id].get("selection_mode"),
                    "selection_provenance": {
                        "selection_epoch": SELECTION_EPOCH,
                        "source_graph_version": "HG0",
                        "source_ml_version": "ML0",
                        "selection_rank": selections[story_id].get("selection_rank"),
                        "selection_score": selections[story_id].get("selection_score"),
                    },
                })
    return rows


def story_selection_provenance(story_id: str, selections: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    row = selections[story_id]
    return {
        "selection_epoch": SELECTION_EPOCH,
        "selection_mode": row.get("selection_mode"),
        "source_graph_version": "HG0",
        "source_ml_version": "ML0",
        "candidate_pool_hash": row.get("candidate_pool_hash"),
        "selection_seed": row.get("selection_seed"),
        "selection_rank": row.get("selection_rank"),
        "selection_score": row.get("selection_score"),
        "selection_reason": row.get("selection_reason") or row.get("selection_inputs") or row.get("counter_model_reason"),
    }


def all_production_ids() -> tuple[set[str], set[str]]:
    people = {
        str(row.get("person_id"))
        for row in read("data/people.json").get("people", [])
        if isinstance(row, Mapping) and row.get("person_id")
    }
    stories = {
        str(row.get("id"))
        for row in read("data/derived/sc1-site.json").get("stories", [])
        if isinstance(row, Mapping) and row.get("id")
    }
    return people, stories
