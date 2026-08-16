#!/usr/bin/env python3
"""Shared deterministic inputs and helpers for X1.2R.

X1.2R is an extension-only review layer.  It consumes the frozen X1.1
selection, the S1 Jianshu cache and the immutable X1.2A/X1.2P review
artifacts.  Nothing in this module writes to the protected production
corpus, H0C, HG0 or ML0 projections.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from scripts.s1_jianshu_common import (
        CACHE_ROOT,
        load_story_records,
        sha256_path,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from s1_jianshu_common import CACHE_ROOT, load_story_records, sha256_path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path("data/derived")

X1_SELECTION_PATH = Path("data/derived/x1-1-selection-manifest.json")
X1_REVIEW_RESULTS_PATH = Path("data/derived/x1-1-review-results.json")
X1_2A_REVIEW_MANIFEST_PATH = Path("data/derived/x1-2a-review-manifest.json")
X1_2A_STORY_REVIEW_PATH = Path("data/derived/x1-2a-story-review.json")
X1_2A_PERSON_REVIEW_PATH = Path("data/derived/x1-2a-person-review.json")
X1_2A_FACT_REVIEW_PATH = Path("data/derived/x1-2a-fact-review.json")
X1_2A_CANONICAL_FACTS_PATH = Path("data/derived/x1-2a-canonical-facts.json")
X1_2A_MATERIALIZATION_PATH = Path("data/derived/x1-2a-materialization-manifest.json")
X1_2A_CONFLICT_PATH = Path("data/derived/x1-2a-conflict-audit.json")
X1_2P_STORY_REVIEW_PATH = Path("data/derived/x1-2p-story-review.json")
X1_2P_DEPENDENCY_PATH = Path("data/derived/x1-2p-dependency-audit.json")
S1_REGISTRATION_PATH = Path("data/derived/s1-jianshu-source-registration.json")
S1_ALIGNMENT_PATH = Path("data/derived/s1-jianshu-story-alignment.json")
S1_ASSERTIONS_PATH = Path("data/derived/s1-jianshu-historical-assertions.json")
S1_CITATIONS_PATH = Path("data/derived/s1-jianshu-source-citations.json")
S1_GLYPH_AUDIT_PATH = Path("data/derived/s1-jianshu-glyph-audit.json")
CORPUS_INDEX_PATH = Path("data/shishuo-corpus-index.json")
PEOPLE_PATH = Path("data/people.json")
MENTIONS_PATH = Path("data/mentions/shishuo.json")

EVIDENCE_BUNDLES_PATH = OUTPUT_DIR / "x1-2r-jianshu-evidence-bundles.json"
PARTICIPANT_REVIEW_PATH = OUTPUT_DIR / "x1-2r-participant-review.json"
IDENTITY_REVIEW_PATH = OUTPUT_DIR / "x1-2r-identity-review.json"
FACT_REOPEN_PATH = OUTPUT_DIR / "x1-2r-fact-reopen-manifest.json"
FACT_REVIEW_PATH = OUTPUT_DIR / "x1-2r-fact-review.json"
CITATION_PATH = OUTPUT_DIR / "x1-2r-citation-candidates.json"
CONFLICT_PATH = OUTPUT_DIR / "x1-2r-conflict-audit.json"
MATERIALIZATION_PATH = OUTPUT_DIR / "x1-2r-materialization-manifest.json"
CANONICAL_EXTENSION_PATH = OUTPUT_DIR / "x1-2r-canonical-extension.json"
REALIZED_YIELD_PATH = OUTPUT_DIR / "x1-2r-realized-yield.json"
CHANNEL_AUDIT_PATH = OUTPUT_DIR / "x1-2r-channel-audit.json"
SUMMARY_PATH = OUTPUT_DIR / "x1-2r-summary.json"

EPOCH = "X1.2R"
SELECTION_EPOCH = "X1.1"

OUTPUT_PATHS = (
    EVIDENCE_BUNDLES_PATH,
    PARTICIPANT_REVIEW_PATH,
    IDENTITY_REVIEW_PATH,
    FACT_REOPEN_PATH,
    FACT_REVIEW_PATH,
    CITATION_PATH,
    CONFLICT_PATH,
    CANONICAL_EXTENSION_PATH,
    MATERIALIZATION_PATH,
    REALIZED_YIELD_PATH,
    CHANNEL_AUDIT_PATH,
    SUMMARY_PATH,
)


def read(path: Path | str) -> Any:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def write(path: Path | str, value: Any) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path | str) -> str:
    return sha256_path(ROOT / path)


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def stable_id(prefix: str, *parts: object, length: int = 20) -> str:
    raw = "|".join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:length]}"


def unique(values: Iterable[object]) -> list[str]:
    return sorted({str(value) for value in values if value is not None and str(value)})


def selection_rows() -> list[dict[str, Any]]:
    rows = read(X1_SELECTION_PATH).get("records", [])
    return sorted((dict(row) for row in rows), key=lambda row: (int(row.get("global_selection_rank", 0)), str(row.get("story_id"))))


def selected_ids() -> list[str]:
    return [str(row["story_id"]) for row in selection_rows()]


def selection_by_story() -> dict[str, dict[str, Any]]:
    return {str(row["story_id"]): row for row in selection_rows()}


def selection_provenance(story_id: str) -> dict[str, Any]:
    row = selection_by_story()[story_id]
    return {
        "selection_epoch": SELECTION_EPOCH,
        "selection_mode": row.get("selection_mode"),
        "selection_rank": row.get("global_selection_rank", row.get("selection_rank")),
        "selection_score": row.get("selection_score"),
        "selection_seed": row.get("selection_seed"),
        "selection_reason": row.get("selection_reason") or row.get("selection_inputs") or row.get("counter_model_reason"),
        "candidate_pool_hash": row.get("candidate_pool_hash"),
        "source_graph_version": "HG0",
        "source_ml_version": "ML0",
    }


def load_alignment() -> dict[str, dict[str, Any]]:
    return {
        str(row["story_id"]): dict(row)
        for row in read(S1_ALIGNMENT_PATH).get("records", [])
        if isinstance(row, Mapping) and row.get("story_id")
    }


def load_jianshu_by_story() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in load_story_records():
        story_id = row.get("canonical_story_id") or row.get("story_id")
        if story_id:
            result[str(story_id)] = dict(row)
    return result


def load_mentions_by_story() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in read(MENTIONS_PATH).get("mentions", []):
        if not isinstance(row, Mapping):
            continue
        story_id = row.get("entry_id") or row.get("source_id")
        if story_id:
            result[str(story_id)].append(dict(row))
    return {story_id: sorted(rows, key=lambda row: str(row.get("mention_id", ""))) for story_id, rows in result.items()}


def load_people_by_id() -> dict[str, dict[str, Any]]:
    return {
        str(row["person_id"]): dict(row)
        for row in read(PEOPLE_PATH).get("people", [])
        if isinstance(row, Mapping) and row.get("person_id")
    }


def load_assertions_by_story() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in read(S1_ASSERTIONS_PATH).get("records", []):
        if isinstance(row, Mapping) and row.get("story_id"):
            result[str(row["story_id"])].append(dict(row))
    for story_id in result:
        result[story_id].sort(key=lambda row: str(row.get("assertion_id", "")))
    return dict(result)


def load_citations_by_story() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in read(S1_CITATIONS_PATH).get("records", []):
        if isinstance(row, Mapping) and row.get("story_id"):
            result[str(row["story_id"])].append(dict(row))
    for story_id in result:
        result[story_id].sort(key=lambda row: (str(row.get("citation_id", "")), str(row.get("assertion_id", ""))))
    return dict(result)


def source_hashes() -> dict[str, str]:
    registration = read(S1_REGISTRATION_PATH)
    output: dict[str, str] = {}
    payloads = registration.get("payloads", [])
    if isinstance(payloads, Mapping):
        payloads = list(payloads.values())
    for row in payloads:
        if isinstance(row, Mapping) and row.get("format") and row.get("sha256"):
            output[str(row["format"]).lower()] = str(row["sha256"])
    return dict(sorted(output.items()))


def layer_for_block(block_type: str) -> str:
    if block_type in {"base_text", "liu_annotation", "jianshu_note", "collation_note"}:
        return block_type
    return "other_scholar_note"


def all_production_person_ids() -> set[str]:
    return set(load_people_by_id())


def direct_story_record(story_id: str) -> dict[str, Any]:
    row = read(CORPUS_INDEX_PATH)
    for entry in row.get("entries", []):
        if entry.get("id") == story_id:
            path = ROOT / str(entry["path"])
            # The corpus index predates the explicit chapter_id field on
            # entries.  Recover the stable chapter identity from the
            # repository path when the field is absent; this is metadata
            # normalization, not a change to canonical Story text.
            chapter_id = entry.get("chapter_id") or Path(str(entry["path"])).parent.name
            return {
                "story_id": story_id,
                "path": str(entry["path"]),
                "sha256": str(entry.get("entry_sha256") or sha256_file(entry["path"])),
                "exists": path.is_file(),
                "global_ordinal": entry.get("global_ordinal"),
                "chapter_id": chapter_id,
                "chapter_heading": next(
                    (chapter.get("heading", chapter.get("id")) for chapter in row.get("chapters", []) if chapter.get("id") == chapter_id),
                    chapter_id,
                ),
            }
    raise KeyError(f"unknown Story {story_id}")


def source_locator_key(locator: Mapping[str, Any]) -> str:
    return json.dumps(dict(locator), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def previous_identity_rows() -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in read(X1_2A_PERSON_REVIEW_PATH).get("records", [])
        if row.get("review_status") == "unresolved"
    ]


def previous_fact_rows() -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in read(X1_2A_FACT_REVIEW_PATH).get("records", [])
        if row.get("review_status") == "unresolved"
    ]


def previous_production_story_review() -> dict[str, dict[str, Any]]:
    return {
        str(row["story_id"]): dict(row)
        for row in read(X1_2P_STORY_REVIEW_PATH).get("records", [])
        if row.get("story_id")
    }


def previous_x1_2a_hashes() -> dict[str, str]:
    paths = {
        "review_manifest": X1_2A_REVIEW_MANIFEST_PATH,
        "story_review": X1_2A_STORY_REVIEW_PATH,
        "person_review": X1_2A_PERSON_REVIEW_PATH,
        "fact_review": X1_2A_FACT_REVIEW_PATH,
        "canonical_facts": X1_2A_CANONICAL_FACTS_PATH,
        "materialization": X1_2A_MATERIALIZATION_PATH,
    }
    return {name: sha256_file(path) for name, path in paths.items()}


def previous_x1_2p_hashes() -> dict[str, str]:
    paths = {
        "story_review": X1_2P_STORY_REVIEW_PATH,
        "dependency_audit": X1_2P_DEPENDENCY_PATH,
    }
    return {name: sha256_file(path) for name, path in paths.items()}


def x1_hashes() -> dict[str, str]:
    paths = {
        "selection_manifest": X1_SELECTION_PATH,
        "review_results": X1_REVIEW_RESULTS_PATH,
    }
    return {name: sha256_file(path) for name, path in paths.items()}


def protected_hashes() -> dict[str, str]:
    paths = {
        "people": PEOPLE_PATH,
        "mentions": MENTIONS_PATH,
        "h0c_participant_freeze": Path("data/derived/h0c-participant-freeze.json"),
        "h0c_historical_facts": Path("data/derived/h0c-historical-facts.json"),
        "h0c_graph": Path("data/derived/h0c-graph-projection.json"),
        "hg0_graph": Path("data/derived/hg0-graph-projection.json"),
        "ml0_metrics": Path("data/derived/ml0-metrics.json"),
    }
    return {name: sha256_file(path) for name, path in paths.items() if (ROOT / path).is_file()}


def relevant_assertions(story_id: str, layer: str, assertions: Mapping[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Return source assertions that open a genuine route for this fact layer.

    ``historical_context`` alone is deliberately not enough.  The assertion
    must name the candidate semantic domain.  Collation notes are retained in
    the bundle but are not treated as historical-fact evidence here.
    """

    wanted = {
        "family": {"family", "kinship", "marriage", "identity"},
        "office": {"office", "temporal"},
        "event": {"event", "historical_event"},
        "geographic": {"geographic", "location"},
        "service_political": {"service", "political", "institutional"},
        "temporal": {"temporal", "chronology"},
        "clan": {"clan"},
    }.get(layer, {layer})
    rows: list[dict[str, Any]] = []
    for row in assertions.get(story_id, []):
        if row.get("layer") == "collation_note":
            continue
        types = {str(value).lower() for value in row.get("candidate_fact_types", [])}
        if types & wanted:
            rows.append(row)
    return sorted(rows, key=lambda row: str(row.get("assertion_id", "")))
