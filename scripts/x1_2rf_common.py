#!/usr/bin/env python3
"""Shared deterministic inputs for X1.2R-F.

X1.2R-F is an extension-only review layer.  It reads the frozen X1.2R/S1
artifacts and writes a separate assertion review and historical-fact
extension.  It never rewrites H0C, HG0, ML0, or the protected X1.2R data.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

try:
    from scripts.x1_2r_common import (
        ROOT,
        canonical_hash,
        frozen_projection_input_hash,
        load_people_by_id,
        read,
        selected_ids,
        sha256_file,
        stable_id,
        write,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from x1_2r_common import (
        ROOT,
        canonical_hash,
        frozen_projection_input_hash,
        load_people_by_id,
        read,
        selected_ids,
        sha256_file,
        stable_id,
        write,
    )


OUTPUT_DIR = Path("data/derived")
EPOCH = "X1.2R-F"

SELECTION_PATH = Path("data/derived/x1-1-selection-manifest.json")
S1_ASSERTIONS_PATH = Path("data/derived/s1-jianshu-historical-assertions.json")
S1_CITATIONS_PATH = Path("data/derived/s1-jianshu-source-citations.json")
S1_REGISTRATION_PATH = Path("data/derived/s1-jianshu-source-registration.json")
X1_2R_BUNDLES_PATH = Path("data/derived/x1-2r-jianshu-evidence-bundles.json")
X1_2R_PARTICIPANT_PATH = Path("data/derived/x1-2r-participant-review.json")
X1_2R_IDENTITY_PATH = Path("data/derived/x1-2r-identity-review.json")
X1_2R_FACT_REVIEW_PATH = Path("data/derived/x1-2r-fact-review.json")
X1_2R_CITATION_PATH = Path("data/derived/x1-2r-citation-candidates.json")
X1_2R_MATERIALIZATION_PATH = Path("data/derived/x1-2r-materialization-manifest.json")
X1_2R_EXTENSION_PATH = Path("data/derived/x1-2r-canonical-extension.json")
X1_2R_SUMMARY_PATH = Path("data/derived/x1-2r-summary.json")

PEOPLE_PATH = Path("data/people.json")
OFFICES_PATH = Path("data/derived/h0c-offices.json")
LOCATIONS_PATH = Path("data/derived/h0c-locations.json")
H0C_FACTS_PATH = Path("data/derived/h0c-historical-facts.json")
H0C_OFFICE_PATH = Path("data/derived/h0c-offices.json")
H0C_LOCATION_FACTS_PATH = Path("data/derived/h0c-location-facts.json")
X1_2A_FACTS_PATH = Path("data/derived/x1-2a-canonical-facts.json")

POLICY_PATH = OUTPUT_DIR / "x1-2rf-policy.json"
ASSERTION_REVIEW_PATH = OUTPUT_DIR / "x1-2rf-assertion-review.json"
ORIGINAL_REVIEW_PATH = OUTPUT_DIR / "x1-2rf-original-candidate-review.json"
MATERIALIZED_FACTS_PATH = OUTPUT_DIR / "x1-2rf-materialized-facts.json"
CORROBORATION_PATH = OUTPUT_DIR / "x1-2rf-corroboration.json"
SCHOLARLY_ASSERTIONS_PATH = OUTPUT_DIR / "x1-2rf-scholarly-assertions.json"
SUMMARY_PATH = OUTPUT_DIR / "x1-2rf-summary.json"
NEXT_STEP_PATH = OUTPUT_DIR / "x1-2rf-next-step-recommendation.json"

OUTPUT_PATHS = (
    POLICY_PATH,
    ASSERTION_REVIEW_PATH,
    ORIGINAL_REVIEW_PATH,
    MATERIALIZED_FACTS_PATH,
    CORROBORATION_PATH,
    SCHOLARLY_ASSERTIONS_PATH,
    SUMMARY_PATH,
    NEXT_STEP_PATH,
)

MODAL_VALUES = {"probable", "possible", "disputed", "unknown"}
ALLOWED_REVIEW_STATES = {
    "accepted",
    "unresolved",
    "rejected",
    "citation_only",
    "scholarly_assertion_only",
}


def load_assertions() -> list[dict[str, Any]]:
    selected = set(selected_ids())
    rows = [
        dict(row)
        for row in read(S1_ASSERTIONS_PATH).get("records", [])
        if isinstance(row, Mapping) and row.get("story_id") in selected
    ]
    return sorted(rows, key=lambda row: (str(row.get("story_id")), str(row.get("assertion_id"))))


def load_citations() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in read(S1_CITATIONS_PATH).get("records", []):
        if isinstance(row, Mapping) and row.get("story_id") in set(selected_ids()):
            result[str(row.get("assertion_id"))].append(dict(row))
    for assertion_id in result:
        result[assertion_id].sort(key=lambda row: str(row.get("citation_id", "")))
    return dict(result)


def load_x1_2r_facts() -> list[dict[str, Any]]:
    return sorted(
        [dict(row) for row in read(X1_2R_FACT_REVIEW_PATH).get("records", [])],
        key=lambda row: str(row.get("review_item_id", "")),
    )


def reopened_x1_2r_facts() -> list[dict[str, Any]]:
    return [row for row in load_x1_2r_facts() if row.get("reopen_status") == "reopened_due_to_new_source"]


def source_transmission(row: Mapping[str, Any], quoted_source: str | None) -> str:
    layer = str(row.get("layer", ""))
    attribution = row.get("attribution")
    if layer == "liu_annotation":
        return "quoted_via_liu_annotation" if quoted_source else "liu_annotation_assertion"
    if layer == "jianshu_note":
        return "quoted_via_jianshu_note" if quoted_source else ("scholarly_assertion" if attribution else "direct_jianshu_assertion")
    if layer == "collation_note":
        return "scholarly_assertion"
    return "direct_jianshu_assertion"


def quoted_source_for(assertion: Mapping[str, Any], citations: Mapping[str, list[dict[str, Any]]]) -> str | None:
    assertion_id = str(assertion.get("assertion_id", ""))
    text = str(assertion.get("text", ""))
    # Preserve the source identity stated in the passage when it is more
    # specific than a normalized citation label (for example 王隱晉書 rather
    # than the broader 晉書).
    known = (
        "王隱晉書",
        "續晉陽秋",
        "渚宮舊事",
        "鄧粲晉紀",
        "漢晉春秋",
        "顧和別傳",
        "晉陽秋",
        "中興書",
        "晉書",
        "嘉錫案",
    )
    for token in known:
        if token in text and ("曰" in text or "云" in text or "案" in text):
            return token
    citation_rows = citations.get(assertion_id, [])
    if citation_rows:
        normalized = [str(row.get("normalized_source")) for row in citation_rows if row.get("normalized_source")]
        if normalized:
            return sorted(set(normalized))[0]
    return None


def input_hashes() -> dict[str, str]:
    paths = {
        "x1_1_selection": SELECTION_PATH,
        "s1_assertions": S1_ASSERTIONS_PATH,
        "s1_citations": S1_CITATIONS_PATH,
        "s1_registration": S1_REGISTRATION_PATH,
        "x1_2r_bundles": X1_2R_BUNDLES_PATH,
        "x1_2r_participant": X1_2R_PARTICIPANT_PATH,
        "x1_2r_identity": X1_2R_IDENTITY_PATH,
        "x1_2r_fact_review": X1_2R_FACT_REVIEW_PATH,
        "x1_2r_citations": X1_2R_CITATION_PATH,
        "x1_2r_materialization": X1_2R_MATERIALIZATION_PATH,
        "x1_2r_extension": X1_2R_EXTENSION_PATH,
        "x1_2r_summary": X1_2R_SUMMARY_PATH,
        "h0c_offices": H0C_OFFICE_PATH,
        "h0c_location_facts": H0C_LOCATION_FACTS_PATH,
        "h0c_facts": H0C_FACTS_PATH,
        "x1_2a_facts": X1_2A_FACTS_PATH,
        "people": PEOPLE_PATH,
    }
    return {
        name: (frozen_projection_input_hash(path) if name == "s1_registration" else sha256_file(path))
        for name, path in sorted(paths.items())
    }


def protected_hashes() -> dict[str, str]:
    paths = {
        "people": PEOPLE_PATH,
        "mentions": Path("data/mentions/shishuo.json"),
        "h0c_participant_freeze": Path("data/derived/h0c-participant-freeze.json"),
        "h0c_historical_facts": H0C_FACTS_PATH,
        "h0c_graph": Path("data/derived/h0c-graph-projection.json"),
        "hg0_graph": Path("data/derived/hg0-graph-projection.json"),
        "ml0_metrics": Path("data/derived/ml0-metrics.json"),
        "h0c_protection_manifest": Path("data/derived/h0c-protection-manifest.json"),
        "hg0_protection_manifest": Path("data/derived/hg0-protection-manifest.json"),
        "ml0_protection_manifest": Path("data/derived/ml0-protection-manifest.json"),
        "x1_2a_canonical_facts": X1_2A_FACTS_PATH,
        "x1_2r_extension": X1_2R_EXTENSION_PATH,
        "x1_2r_participant": X1_2R_PARTICIPANT_PATH,
        "x1_2r_identity": X1_2R_IDENTITY_PATH,
        "x1_2r_citations": X1_2R_CITATION_PATH,
    }
    return {name: sha256_file(path) for name, path in sorted(paths.items()) if (ROOT / path).is_file()}


def source_hashes() -> dict[str, str]:
    registration = read(S1_REGISTRATION_PATH)
    result: dict[str, str] = {}
    for row in registration.get("payloads", []):
        if isinstance(row, Mapping) and row.get("format") and row.get("sha256"):
            result[f"jianshu_{str(row['format']).lower()}"] = str(row["sha256"])
    return dict(sorted(result.items()))


def existing_semantic_keys() -> set[str]:
    keys: set[str] = set()
    for row in read(H0C_FACTS_PATH).get("fact_index", []):
        if isinstance(row, Mapping):
            keys.add(fact_semantic_key(row))
    for row in read(X1_2A_FACTS_PATH).get("fact_index", []):
        if isinstance(row, Mapping):
            keys.add(fact_semantic_key(row))
    for row in read(H0C_OFFICE_PATH).get("tenures", []):
        if isinstance(row, Mapping):
            keys.add(f"office_tenure|{row.get('person_id')}|{row.get('office_id') or row.get('normalized_office_label')}")
    for row in read(H0C_LOCATION_FACTS_PATH).get("records", []):
        if isinstance(row, Mapping):
            keys.add(f"location_fact|{row.get('subject_type')}|{row.get('subject_id')}|{row.get('location_id')}|{row.get('location_role')}")
    return {key for key in keys if key and "None" not in key}


def fact_semantic_key(row: Mapping[str, Any]) -> str:
    fact_type = str(row.get("fact_type", ""))
    if fact_type in {"office_tenure", "OfficeTenure"}:
        return f"office_tenure|{row.get('person_id') or (row.get('subject_ids') or [None])[0]}|{row.get('office_id') or row.get('normalized_office_label') or row.get('office_title')}"
    if fact_type in {"location_fact", "LocationFact"}:
        return f"location_fact|{row.get('subject_type', 'person')}|{row.get('subject_id') or (row.get('subject_ids') or [None])[0]}|{row.get('location_id') or (row.get('location_ids') or [None])[0]}|{row.get('location_role')}"
    if fact_type in {"service_political", "ServicePoliticalFact"}:
        subjects = row.get("subject_ids") or []
        return f"service_political|{'|'.join(map(str, subjects))}|{row.get('relation_type')}|{row.get('object_id')}"
    return "|".join(str(row.get(key, "")) for key in ("fact_type", "fact_key", "fact_id"))


def offices_by_name() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in read(OFFICES_PATH).get("entities", []):
        if isinstance(row, Mapping):
            for name in [row.get("canonical_name"), *(row.get("aliases") or [])]:
                if name:
                    result[str(name)] = dict(row)
    return result


def locations_by_name() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    payload = read(LOCATIONS_PATH)
    rows = payload.get("entities", payload.get("records", []))
    for row in rows:
        if isinstance(row, Mapping):
            for name in [row.get("canonical_name"), *(row.get("aliases") or [])]:
                if name:
                    result[str(name)] = dict(row)
    return result


def evidence_hash(assertion: Mapping[str, Any]) -> str:
    text_hash = assertion.get("text_sha256")
    if text_hash:
        return str(text_hash)
    return hashlib.sha256(str(assertion.get("text", "")).encode("utf-8")).hexdigest()


def excerpt(assertion: Mapping[str, Any], limit: int = 240) -> str:
    text = " ".join(str(assertion.get("text", "")).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def citation_only(assertion: Mapping[str, Any], quoted_source: str | None) -> bool:
    text = " ".join(str(assertion.get("text", "")).split())
    if not quoted_source or len(text) > 85:
        return False
    return not any(token in text for token in ("人物", "字", "父", "母", "子", "為", "是", "遷", "卒", "曰：", "云："))


def modal_reason(modality: str) -> str:
    return {
        "probable": "probable or inferential modality is retained outside certain fact materialization",
        "possible": "possible modality is retained outside certain fact materialization",
        "disputed": "disputed scholarly/source transmission is not promoted to a certain fact",
        "unknown": "assertion modality is unknown",
    }.get(modality, "assertion requires endpoint and semantic review")


def sorted_records(rows: Iterable[Mapping[str, Any]], *keys: str) -> list[dict[str, Any]]:
    keys = keys or ("review_item_id",)
    return sorted((dict(row) for row in rows), key=lambda row: tuple(str(row.get(key, "")) for key in keys))
