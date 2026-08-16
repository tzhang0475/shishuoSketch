#!/usr/bin/env python3
"""Build the HR0 HistoricalSituation v0 Gold Set.

HR0 is a reviewed, downstream specification artifact.  The script only reads
existing SC1/H0C inputs and a tracked, manually reviewed annotation spec; it
does not materialize canonical historical data.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = Path("data/annotation/hr0-gold-spec.json")
SC1_PATH = Path("data/derived/sc1-site.json")
PARTICIPANT_PATH = Path("data/derived/h0c-participant-freeze.json")
SCENE_SOURCE_PATH = Path("data/annotation/story-scene-contexts.json")
H0C_FACTS_PATH = Path("data/derived/h0c-historical-facts.json")
HG0_GRAPH_PATH = Path("data/derived/h0c-graph-projection.json")
ML0_METRICS_PATH = Path("data/derived/ml0-metrics.json")
SCHEMA_PATH = Path("schema/historical-situation.schema.json")

GOLD_PATH = Path("data/derived/hr0-historical-situations.json")
SELECTION_PATH = Path("data/derived/hr0-selection-manifest.json")
METRICS_PATH = Path("data/derived/hr0-metrics.json")
PROTECTION_PATH = Path("data/derived/hr0-protection-manifest.json")

SOURCE_LAYER = {
    "primary_text": "base_text",
    "annotation": "liu_annotation",
    "editorial": "editorial",
    "secondary_reference": "secondary_reference",
}

USAGE_FIELDS = {
    "episodes": "episode",
    "participant_states": "participant_state",
    "person_states": "person_state",
    "title_mentions": "title_mention",
    "temporal_relations": "temporal_relation",
    "uncertainties": "uncertainty",
}


def read_json(relative: Path) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def sha256_file(relative: Path) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def quote_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_json(relative: Path, value: Any) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(value), encoding="utf-8")


def all_evidence_ids(record: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    for field in USAGE_FIELDS:
        for item in record.get(field, []):
            ids.update(str(value) for value in item.get("evidence_ids", []))
    return ids


def evidence_usage(record: Mapping[str, Any]) -> dict[str, set[str]]:
    usage: dict[str, set[str]] = {}
    for field, label in USAGE_FIELDS.items():
        for item in record.get(field, []):
            for evidence_id in item.get("evidence_ids", []):
                usage.setdefault(str(evidence_id), set()).add(label)
    return usage


def reject_forbidden_temporal_fields(value: Any, path: str = "spec") -> None:
    """Keep date answers out of HR0 semantic annotations."""

    forbidden = {"start_year", "end_year", "start_year_ce", "end_year_ce", "date", "date_or_age", "year"}
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) in forbidden:
                raise ValueError(f"HR0 may not copy derived/date answer field: {path}.{key}")
            reject_forbidden_temporal_fields(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_forbidden_temporal_fields(child, f"{path}[{index}]")


def build_documents(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    spec = json.loads((root / SPEC_PATH).read_text(encoding="utf-8"))
    sc1 = json.loads((root / SC1_PATH).read_text(encoding="utf-8"))
    participant_freeze = json.loads((root / PARTICIPANT_PATH).read_text(encoding="utf-8"))
    scene_source = json.loads((root / SCENE_SOURCE_PATH).read_text(encoding="utf-8"))

    reject_forbidden_temporal_fields(spec)

    stories = {str(row["id"]): row for row in sc1.get("stories", [])}
    people = {str(row["id"]): row for row in sc1.get("people", [])}
    rulers = {str(row.get("ruler_id", row.get("id"))): row for row in sc1.get("ruler_identities", [])}
    evidence = {str(row["id"]): row for row in sc1.get("evidence", [])}
    scene_story_ids = {str(row["story_id"]) for row in scene_source.get("records", [])}
    selected_ids = sorted(str(row["story_id"]) for row in spec.get("records", []))
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("HR0 selection contains duplicate Story IDs")
    if not selected_ids:
        raise ValueError("HR0 selection is empty")
    if not set(selected_ids).issubset(stories):
        missing = sorted(set(selected_ids) - set(stories))
        raise ValueError(f"HR0 selection contains unknown Stories: {missing}")
    # The curated scene pilot is one selection signal, not the only universe;
    # the two extra evidence-rich records are intentionally allowed here.
    if not {"06-yaliang-029", "05-fangzheng-032"}.issubset(scene_story_ids):
        raise ValueError("HR0 mandatory evidence-rich Stories are absent from the curated scene source")

    record_by_story = {str(row["story_id"]): row for row in spec["records"]}
    output_records: list[dict[str, Any]] = []
    all_categories: set[str] = set()
    category_counts: dict[str, int] = {}
    evidence_ref_count = 0
    unique_evidence_ids: set[str] = set()

    for story_id in selected_ids:
        source_record = record_by_story[story_id]
        usage = evidence_usage(source_record)
        referenced_ids = all_evidence_ids(source_record)
        missing_evidence = sorted(referenced_ids - set(evidence))
        if missing_evidence:
            raise ValueError(f"{story_id} references unknown evidence: {missing_evidence}")
        categories = sorted(set(str(value) for value in source_record["selection_categories"]))
        all_categories.update(categories)
        for category in categories:
            category_counts[category] = category_counts.get(category, 0) + 1

        enriched_refs: list[dict[str, Any]] = []
        for evidence_id in sorted(referenced_ids):
            source = evidence[evidence_id]
            locator = copy.deepcopy(source.get("locator"))
            if not isinstance(locator, Mapping) or not locator.get("source_provenance"):
                raise ValueError(f"evidence lacks source provenance: {evidence_id}")
            enriched_refs.append(
                {
                    "evidence_id": evidence_id,
                    "usage": sorted(usage[evidence_id]),
                    "source_layer": SOURCE_LAYER.get(str(source.get("evidence_type")), "unknown"),
                    "source_id": source.get("source_id"),
                    "evidence_type": source.get("evidence_type"),
                    "review_status": source.get("review_status"),
                    "assertion_status": source.get("assertion_status"),
                    "quote_sha256": quote_sha256(str(source.get("quote", ""))),
                    "locator": locator,
                }
            )
        evidence_ref_count += len(enriched_refs)
        unique_evidence_ids.update(referenced_ids)

        def reviewed_collection(field: str) -> list[dict[str, Any]]:
            rows = copy.deepcopy(source_record.get(field, []))
            for row in rows:
                row.setdefault("review_status", "reviewed")
            return sorted(rows, key=lambda row: str(row.get("episode_id", row.get("state_id", row.get("temporal_relation_id", row.get("title_mention_id", row.get("uncertainty_id", "")))))))

        output_records.append(
            {
                "situation_id": f"hs-hr0-{story_id}",
                "story_id": story_id,
                "review_status": "reviewed_gold",
                "selection_categories": categories,
                "selection_reason": str(source_record["selection_reason"]),
                "episodes": reviewed_collection("episodes"),
                "participant_states": reviewed_collection("participant_states"),
                "temporal_relations": reviewed_collection("temporal_relations"),
                "person_states": reviewed_collection("person_states"),
                "title_mentions": reviewed_collection("title_mentions"),
                "evidence_refs": enriched_refs,
                "uncertainties": reviewed_collection("uncertainties"),
                "review_notes": list(source_record.get("review_notes", [])),
            }
        )

    source_relatives = [SPEC_PATH, SC1_PATH, PARTICIPANT_PATH, SCENE_SOURCE_PATH, SCHEMA_PATH]
    source_hashes = {str(path): hashlib.sha256((root / path).read_bytes()).hexdigest() for path in source_relatives}
    protected_relatives = [SC1_PATH, PARTICIPANT_PATH, H0C_FACTS_PATH, HG0_GRAPH_PATH, ML0_METRICS_PATH]
    protected_hashes = {str(path): hashlib.sha256((root / path).read_bytes()).hexdigest() for path in protected_relatives if (root / path).is_file()}

    counts = {
        "stories": len(output_records),
        "episodes": sum(len(row["episodes"]) for row in output_records),
        "participant_states": sum(len(row["participant_states"]) for row in output_records),
        "temporal_relations": sum(len(row["temporal_relations"]) for row in output_records),
        "person_states": sum(len(row["person_states"]) for row in output_records),
        "title_mentions": sum(len(row["title_mentions"]) for row in output_records),
        "evidence_refs": evidence_ref_count,
        "unique_evidence_ids": len(unique_evidence_ids),
        "uncertainties": sum(len(row["uncertainties"]) for row in output_records),
    }
    gold = {
        "schema": "historical-situation-gold-set",
        "stage": "HR0",
        "schema_version": "v0",
        "scope": {
            "story_count": len(output_records),
            "selected_story_ids": selected_ids,
            "selection_categories": sorted(all_categories),
        },
        "records": output_records,
        "counts": counts,
        "source_hashes": source_hashes,
        "policy": {
            "canonical_data_write_back": False,
            "canonical_fact_materialization": False,
            "inference": False,
            "derived_story_dates_as_answers": False,
            "evidence_required": True,
            "review_model": "reviewed_deterministic_gold",
        },
    }
    selection = {
        "schema": "hr0-selection-manifest",
        "stage": "HR0",
        "selection_method": "deterministic_evidence_rich_pilot",
        "story_count": len(output_records),
        "source_hashes": source_hashes,
        "records": [
            {
                "story_id": row["story_id"],
                "situation_id": row["situation_id"],
                "selection_categories": row["selection_categories"],
                "selection_reason": row["selection_reason"],
                "evidence_count": len(row["evidence_refs"]),
            }
            for row in output_records
        ],
        "policy": "selection is a representative specification pilot, not a historical importance ranking",
    }
    metrics = {
        "schema": "hr0-metrics",
        "stage": "HR0",
        "source_hashes": source_hashes,
        "counts": counts,
        "selection_category_counts": {key: category_counts[key] for key in sorted(category_counts)},
        "episode_kind_counts": {
            key: sum(1 for record in output_records for episode in record["episodes"] if episode["episode_kind"] == key)
            for key in sorted({episode["episode_kind"] for record in output_records for episode in record["episodes"]})
        },
        "resolution_counts": {
            "resolved_participant_states": sum(1 for record in output_records for item in record["participant_states"] if item["resolution_status"] == "resolved"),
            "unresolved_or_ambiguous_participant_states": sum(1 for record in output_records for item in record["participant_states"] if item["resolution_status"] != "resolved"),
            "resolved_title_mentions": sum(1 for record in output_records for item in record["title_mentions"] if item["resolution_status"] == "resolved"),
            "unresolved_or_ambiguous_title_mentions": sum(1 for record in output_records for item in record["title_mentions"] if item["resolution_status"] != "resolved"),
        },
        "policy_checks": {
            "llm_calls": False,
            "rag": False,
            "temporal_solver": False,
            "canonical_fact_materialization": False,
        },
    }
    protection = {
        "schema": "hr0-protection-manifest",
        "stage": "HR0",
        "protected_input_hashes": protected_hashes,
        "write_back": {
            "canonical_story_text": False,
            "canonical_people": False,
            "canonical_mentions": False,
            "canonical_facts": False,
            "canonical_relations": False,
            "participant_freeze": False,
            "hg0_graph": False,
            "ml0_artifacts": False,
        },
    }
    return gold, selection, metrics, protection


def build(root: Path = ROOT) -> None:
    gold, selection, metrics, protection = build_documents(root)
    for relative, value in (
        (GOLD_PATH, gold),
        (SELECTION_PATH, selection),
        (METRICS_PATH, metrics),
        (PROTECTION_PATH, protection),
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(stable_json(value), encoding="utf-8")


if __name__ == "__main__":
    build()
    print(f"wrote {GOLD_PATH}")
