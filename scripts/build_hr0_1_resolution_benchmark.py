#!/usr/bin/env python3
"""Build the HR0.1 ambiguity and evidence-resolution benchmark.

HR0.1 is a downstream benchmark projection.  It keeps the reviewed HR0 Gold
Set immutable and presents the same situations through two controlled views:
the Shishuo-text-only view and an evidence-augmented view.  No historical
fact, Story, Person, relation, model output, or retrieval result is written
back by this script.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
HR0_PATH = Path("data/derived/hr0-historical-situations.json")
EXTRA_SPEC_PATH = Path("data/annotation/hr0-1-resolution-spec.json")
SC1_PATH = Path("data/derived/sc1-site.json")
HR0_SCHEMA_PATH = Path("schema/historical-situation.schema.json")
SCHEMA_PATH = Path("schema/historical-situation-resolution-benchmark.schema.json")
PARTICIPANT_PATH = Path("data/derived/h0c-participant-freeze.json")
H0C_FACTS_PATH = Path("data/derived/h0c-historical-facts.json")
HG0_GRAPH_PATH = Path("data/derived/hg0-graph-projection.json")
ML0_METRICS_PATH = Path("data/derived/ml0-metrics.json")

BENCHMARK_PATH = Path("data/derived/hr0-1-ambiguity-benchmark.json")
METRICS_PATH = Path("data/derived/hr0-1-metrics.json")
PROTECTION_PATH = Path("data/derived/hr0-1-protection-manifest.json")

ITEM_ID_FIELDS = {
    "episodes": "episode_id",
    "participant_states": "state_id",
    "temporal_relations": "temporal_relation_id",
    "person_states": "state_id",
    "title_mentions": "title_mention_id",
    "uncertainties": "uncertainty_id",
}

VIEW_FIELDS = tuple(ITEM_ID_FIELDS)
ALLOWED_REQUIRES = {"liu_annotation", "jianshu", "external_source", "canonical_fact"}
BASE_LAYER = "base_text"


def read_json(root: Path, relative: Path) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def sha256_file(root: Path, relative: Path) -> str:
    return hashlib.sha256((root / relative).read_bytes()).hexdigest()


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_json(root: Path, relative: Path, value: Any) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(value), encoding="utf-8")


def item_id(field: str, item: Mapping[str, Any]) -> str:
    return str(item.get(ITEM_ID_FIELDS[field], ""))


def sorted_items(field: str, rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [copy.deepcopy(row) for row in sorted(rows, key=lambda row: item_id(field, row))]


def evidence_ids_for_item(item: Mapping[str, Any]) -> set[str]:
    return {str(value) for value in item.get("evidence_ids", [])}


def evidence_map(record: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(row["evidence_id"]): row for row in record.get("evidence_refs", [])}


def base_evidence_ids(record: Mapping[str, Any]) -> set[str]:
    return {
        evidence_id
        for evidence_id, ref in evidence_map(record).items()
        if ref.get("source_layer") == BASE_LAYER
    }


def source_requirements(record: Mapping[str, Any], evidence_ids: set[str]) -> list[str]:
    refs = evidence_map(record)
    requirements: set[str] = set()
    for evidence_id in evidence_ids:
        layer = refs.get(evidence_id, {}).get("source_layer")
        if layer == "liu_annotation":
            requirements.add("liu_annotation")
        elif layer == "secondary_reference":
            requirements.add("external_source")
    return sorted(requirements)


def dimension_for_uncertainty(uncertainty_type: str) -> str:
    return {
        "identity": "identity",
        "temporal": "temporal_relation",
        "participant_scope": "participant_presence_reference",
        "title": "title_identity",
        "semantic": "person_state_resolution",
        "episode_boundary": "episode_boundary",
        "source_layer": "evidence_layer",
        "location": "location",
        "comparative": "comparative_evaluation",
        "other": "person_state_resolution",
    }.get(uncertainty_type, "person_state_resolution")


def shishuo_status(record: Mapping[str, Any], evidence_ids: set[str], status: str) -> str:
    if not evidence_ids & base_evidence_ids(record):
        return "unavailable"
    if status == "bounded":
        return "limited"
    return "ambiguous"


def refined_value(record: Mapping[str, Any], uncertainty: Mapping[str, Any]) -> Any:
    """Describe a bounded HR0 conclusion without turning it into a date answer."""

    uncertainty_type = str(uncertainty.get("uncertainty_type"))
    evidence_ids = set(str(value) for value in uncertainty.get("evidence_ids", []))
    if uncertainty_type == "temporal":
        relations = [
            row
            for row in record.get("temporal_relations", [])
            if evidence_ids & evidence_ids_for_item(row)
        ]
        if relations:
            relation = sorted(relations, key=lambda row: str(row.get("temporal_relation_id", "")))[0]
            return {
                "kind": "temporal_constraint",
                "relation_type": relation.get("relation_type"),
                "precision": relation.get("precision"),
                "expression": relation.get("expression"),
            }
    if uncertainty_type == "title":
        titles = [
            row
            for row in record.get("title_mentions", [])
            if evidence_ids & evidence_ids_for_item(row)
            and row.get("surface") == uncertainty.get("scope")
            and row.get("resolution_status") == "resolved"
        ]
        if titles:
            title = sorted(titles, key=lambda row: str(row.get("title_mention_id", "")))[0]
            return {
                "surface": title.get("surface"),
                "entity_type": title.get("entity_type"),
                "entity_id": title.get("entity_id"),
            }
    if uncertainty_type == "participant_scope":
        return {
            "kind": "participant_scope",
            "scope": uncertainty.get("scope"),
            "description": uncertainty.get("description"),
        }
    return {
        "kind": "bounded_uncertainty",
        "uncertainty_type": uncertainty_type,
        "description": uncertainty.get("description"),
    }


def derived_case_affected_items(record: Mapping[str, Any], uncertainty: Mapping[str, Any], dimension: str) -> list[dict[str, Any]]:
    """Expose which HR0 items the ambiguity describes.

    Only identity/title endpoint ambiguities are masked in the Shishuo-only
    view.  Participant-scope and temporal cases retain their observable
    Story semantics while their uncertainty remains explicit.
    """

    scope = str(uncertainty.get("scope", ""))
    evidence_ids = {str(value) for value in uncertainty.get("evidence_ids", [])}
    rows: list[dict[str, Any]] = []
    for field in VIEW_FIELDS:
        for item in record.get(field, []):
            if evidence_ids and not evidence_ids & evidence_ids_for_item(item):
                continue
            surface = str(item.get("surface", ""))
            action = "preserve_context"
            if dimension in {"identity", "title_identity"} and (
                surface == scope or (scope and scope in surface)
            ):
                action = "mask_endpoint"
            rows.append({
                "field": field,
                "item_id": item_id(field, item),
                "shishuo_only_action": action,
            })
    return sorted(rows, key=lambda row: (str(row["field"]), str(row["item_id"])))


def make_derived_case(record: Mapping[str, Any], uncertainty: Mapping[str, Any]) -> dict[str, Any]:
    story_id = str(record["story_id"])
    uncertainty_id = str(uncertainty["uncertainty_id"])
    case_id = f"erc-hr0-1-{story_id}-{uncertainty_id}"
    evidence_ids = {str(value) for value in uncertainty.get("evidence_ids", [])}
    base_ids = base_evidence_ids(record)
    shishuo_refs = sorted(evidence_ids & base_ids) or sorted(base_ids)
    resolution_refs = sorted(evidence_ids) or sorted(base_ids)
    status = str(uncertainty.get("status"))
    if status == "bounded":
        resolved_status = "refined"
        resolved_value = refined_value(record, uncertainty)
    else:
        resolved_status = (
            "unresolved_even_with_available_evidence"
            if source_requirements(record, resolution_refs)
            else "unresolved"
        )
        resolved_value = None
    dimension = dimension_for_uncertainty(str(uncertainty.get("uncertainty_type")))
    requirements = source_requirements(record, set(resolution_refs))
    value = resolved_value if isinstance(resolved_value, Mapping) else None
    if value and value.get("entity_id"):
        requirements = sorted(set(requirements) | {"canonical_fact"})
    return {
        "case_id": case_id,
        "story_id": story_id,
        "situation_id": str(record["situation_id"]),
        "review_status": "reviewed",
        "review_note": str(uncertainty.get("description", "")),
        "shishuo_evidence_refs": shishuo_refs,
        "resolution_evidence_refs": resolution_refs,
        "affected_items": derived_case_affected_items(record, uncertainty, dimension),
        "resolution_dependency": {
            "uncertainty_id": uncertainty_id,
            "dimension": dimension,
            "shishuo_status": shishuo_status(record, evidence_ids, status),
            "resolved_status": resolved_status,
            "resolved_value": resolved_value,
            "requires": requirements,
            "evidence_refs": sorted(set(shishuo_refs) | set(resolution_refs)),
        },
    }


def make_extra_case(record: Mapping[str, Any], spec_row: Mapping[str, Any]) -> dict[str, Any]:
    story_id = str(record["story_id"])
    evidence_by_id = evidence_map(record)
    case_evidence = set(str(value) for value in spec_row.get("resolution_evidence_refs", []))
    base_refs = set(str(value) for value in spec_row.get("shishuo_evidence_refs", []))
    if not base_refs:
        base_refs = case_evidence & base_evidence_ids(record)
    if not case_evidence:
        case_evidence = base_refs
    unknown = sorted((base_refs | case_evidence) - set(evidence_by_id))
    if unknown:
        raise ValueError(f"HR0.1 extra case references unknown evidence in {story_id}: {unknown}")
    requires = sorted(set(str(value) for value in spec_row.get("requires", [])))
    if not set(requires).issubset(ALLOWED_REQUIRES):
        raise ValueError(f"HR0.1 extra case has unsupported dependency: {spec_row.get('case_id')}")
    affected = [
        {
            "field": str(path["field"]),
            "item_id": str(path["item_id"]),
            "shishuo_only_action": "mask_endpoint",
        }
        for path in spec_row.get("mask_paths", [])
    ]
    return {
        "case_id": str(spec_row["case_id"]),
        "story_id": story_id,
        "situation_id": str(record["situation_id"]),
        "review_status": "reviewed",
        "review_note": str(spec_row.get("review_note", "")),
        "shishuo_evidence_refs": sorted(base_refs),
        "resolution_evidence_refs": sorted(case_evidence),
        "affected_items": sorted(affected, key=lambda row: (row["field"], row["item_id"])),
        "resolution_dependency": {
            "uncertainty_id": str(spec_row["uncertainty_id"]),
            "dimension": str(spec_row["dimension"]),
            "shishuo_status": str(spec_row["shishuo_status"]),
            "resolved_status": str(spec_row["resolved_status"]),
            "resolved_value": copy.deepcopy(spec_row.get("resolved_value")),
            "requires": requires,
            "evidence_refs": sorted(base_refs | case_evidence),
        },
    }


def apply_endpoint_value(item: dict[str, Any], value: Mapping[str, Any]) -> None:
    entity_type = value.get("entity_type")
    entity_id = value.get("entity_id")
    if "person_id" in item and entity_type == "person":
        item["person_id"] = entity_id
        item["candidate_person_ids"] = []
        item["resolution_status"] = "resolved"
    if "entity_id" in item and entity_type in {"person", "ruler"}:
        item["entity_type"] = entity_type
        item["entity_id"] = entity_id
        item["candidate_entity_ids"] = []
        item["resolution_status"] = "resolved"


def mask_endpoint(item: dict[str, Any]) -> None:
    if "person_id" in item:
        item["person_id"] = None
        item["candidate_person_ids"] = []
        item["resolution_status"] = "unresolved"
    if "entity_id" in item:
        item["entity_id"] = None
        item["candidate_entity_ids"] = []
        item["resolution_status"] = "unresolved"


def neutralize_unavailable(field: str, item: dict[str, Any]) -> None:
    if field == "participant_states":
        mask_endpoint(item)
    elif field == "title_mentions":
        mask_endpoint(item)
    elif field == "person_states":
        item["person_id"] = None
        item["value"] = None
        item["assertion_status"] = "uncertain"
        item["modality"] = "uncertain"
    elif field == "episodes":
        item["summary"] = None
        item["assertion_status"] = "uncertain"
    elif field == "temporal_relations":
        item["expression"] = None
        item["precision"] = "unknown"


def build_view(record: Mapping[str, Any], cases: list[Mapping[str, Any]], view_name: str) -> dict[str, Any]:
    resolved = view_name == "evidence_resolved"
    all_ids = set(str(ref["evidence_id"]) for ref in record.get("evidence_refs", []))
    base_ids = base_evidence_ids(record)
    view: dict[str, Any] = {
        "view_name": view_name,
        "evidence_ids": sorted(all_ids if resolved else base_ids),
        "case_ids": sorted(str(case["case_id"]) for case in cases),
    }
    for field in VIEW_FIELDS:
        rows: list[dict[str, Any]] = []
        for source_item in sorted_items(field, list(record.get(field, []))):
            item = copy.deepcopy(source_item)
            item_evidence = evidence_ids_for_item(item)
            available_evidence = item_evidence if resolved else item_evidence & base_ids
            if resolved:
                item["availability"] = "evidence_resolved"
            elif not available_evidence:
                item["availability"] = "requires_external_evidence"
            elif available_evidence == item_evidence:
                item["availability"] = "available_from_shishuo"
            else:
                item["availability"] = "partially_available"
            item["evidence_ids"] = sorted(available_evidence)
            if not resolved and not available_evidence:
                neutralize_unavailable(field, item)
                if field == "uncertainties":
                    item["description"] = "该不确定性仅在非Shishuo证据层记录。"
            rows.append(item)
        view[field] = rows

    # The explicit cases are the review-controlled bridge between the two
    # views.  Apply only endpoint resolutions; no prose or historical claim is
    # synthesized here.
    for case in cases:
        dependency = case["resolution_dependency"]
        value = dependency.get("resolved_value")
        affected = case.get("affected_items", [])
        if not isinstance(value, Mapping) or dependency.get("resolved_status") not in {"resolved", "refined"}:
            continue
        for path in affected:
            field = str(path["field"])
            item_key = str(path["item_id"])
            for item in view.get(field, []):
                if item_id(field, item) != item_key:
                    continue
                if resolved and path.get("shishuo_only_action") == "mask_endpoint":
                    apply_endpoint_value(item, value)
                elif not resolved and path.get("shishuo_only_action") == "mask_endpoint":
                    mask_endpoint(item)

    if not resolved:
        for case in cases:
            for path in case.get("affected_items", []):
                if path.get("shishuo_only_action") != "mask_endpoint":
                    continue
                field = str(path["field"])
                item_key = str(path["item_id"])
                for item in view.get(field, []):
                    if item_id(field, item) == item_key:
                        mask_endpoint(item)
    return view


def build_documents(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    hr0 = read_json(root, HR0_PATH)
    extra_spec = read_json(root, EXTRA_SPEC_PATH)
    sc1 = read_json(root, SC1_PATH)
    hr0_records = sorted(hr0.get("records", []), key=lambda row: str(row.get("story_id", "")))
    sc1_stories = {str(row.get("id")) for row in sc1.get("stories", [])}
    sc1_evidence = {str(row.get("id")) for row in sc1.get("evidence", [])}
    if not hr0_records:
        raise ValueError("HR0.1 requires the completed HR0 Gold Set")
    if not set(str(row["story_id"]) for row in hr0_records).issubset(sc1_stories):
        raise ValueError("HR0.1 HR0 universe contains an unknown Story")

    extras_by_story: dict[str, list[Mapping[str, Any]]] = {}
    for row in extra_spec.get("additional_cases", []):
        extras_by_story.setdefault(str(row["story_id"]), []).append(row)

    output_records: list[dict[str, Any]] = []
    all_cases: list[dict[str, Any]] = []
    original_case_count = 0
    additional_case_count = 0
    for record in hr0_records:
        story_id = str(record["story_id"])
        cases = [make_derived_case(record, uncertainty) for uncertainty in record.get("uncertainties", [])]
        original_case_count += len(cases)
        for extra in sorted(extras_by_story.get(story_id, []), key=lambda row: str(row.get("case_id", ""))):
            cases.append(make_extra_case(record, extra))
            additional_case_count += 1
        cases = sorted(cases, key=lambda row: str(row["case_id"]))
        for case in cases:
            case_evidence = set(case["resolution_dependency"]["evidence_refs"])
            if not case_evidence.issubset(sc1_evidence):
                raise ValueError(f"HR0.1 case has unknown SC1 evidence: {case['case_id']}")
        all_cases.extend(cases)
        output_records.append(
            {
                "situation_id": str(record["situation_id"]),
                "story_id": story_id,
                "evidence_refs": copy.deepcopy(record["evidence_refs"]),
                "case_ids": sorted(str(case["case_id"]) for case in cases),
                "shishuo_only_gold": build_view(record, cases, "shishuo_only"),
                "evidence_resolved_gold": build_view(record, cases, "evidence_resolved"),
                "resolution_cases": cases,
            }
        )

    source_paths = [
        HR0_PATH,
        EXTRA_SPEC_PATH,
        SC1_PATH,
        HR0_SCHEMA_PATH,
        SCHEMA_PATH,
    ]
    source_hashes = {str(path): sha256_file(root, path) for path in source_paths}
    dimensions = Counter(str(case["resolution_dependency"]["dimension"]) for case in all_cases)
    statuses = Counter(str(case["resolution_dependency"]["resolved_status"]) for case in all_cases)
    dependencies = Counter(
        requirement
        for case in all_cases
        for requirement in case["resolution_dependency"].get("requires", [])
    )
    source_layers = Counter(
        ref.get("source_layer")
        for record in output_records
        for ref in record.get("evidence_refs", [])
    )
    counts = {
        "stories": len(output_records),
        "resolution_cases": len(all_cases),
        "original_hr0_uncertainty_cases": original_case_count,
        "additional_explicit_cases": additional_case_count,
        "cases_by_dimension": {key: dimensions[key] for key in sorted(dimensions)},
        "cases_by_resolution_status": {key: statuses[key] for key in sorted(statuses)},
        "resolved_or_refined_cases": sum(statuses[key] for key in ("resolved", "refined")),
        "unresolved_cases": sum(statuses[key] for key in ("unresolved", "unresolved_even_with_available_evidence")),
        "dependency_counts": {key: dependencies[key] for key in sorted(dependencies)},
        "evidence_ref_source_layer_counts": {key: source_layers[key] for key in sorted(source_layers)},
    }
    benchmark = {
        "schema": "historical-situation-resolution-benchmark",
        "stage": "HR0.1",
        "schema_version": "v0",
        "scope": {
            "story_count": len(output_records),
            "selected_story_ids": [str(record["story_id"]) for record in output_records],
            "pass_a": "shishuo_only",
            "pass_b": "evidence_augmented",
        },
        "records": output_records,
        "counts": counts,
        "source_hashes": source_hashes,
        "policy": {
            "canonical_data_write_back": False,
            "hr0_input_immutable": True,
            "resolution_requires_explicit_evidence": True,
            "unresolved_preserved": True,
            "llm": False,
            "rag": False,
            "temporal_solver": False,
        },
    }
    metrics = {
        "schema": "hr0-1-metrics",
        "stage": "HR0.1",
        "source_hashes": source_hashes,
        "counts": counts,
        "pass_views": {
            "shishuo_only": {
                "stories": len(output_records),
                "items_with_external_dependency": sum(
                    1
                    for record in output_records
                    for item in record["shishuo_only_gold"]["participant_states"]
                    + record["shishuo_only_gold"]["title_mentions"]
                    + record["shishuo_only_gold"]["person_states"]
                    if item.get("availability") == "requires_external_evidence"
                ),
            },
            "evidence_resolved": {"stories": len(output_records)},
        },
        "policy_checks": {
            "canonical_data_write_back": False,
            "llm_calls": False,
            "rag": False,
            "temporal_solver": False,
            "new_story_selection": False,
        },
    }

    protected_candidates = [
        HR0_PATH,
        SC1_PATH,
        PARTICIPANT_PATH,
        H0C_FACTS_PATH,
        HG0_GRAPH_PATH,
        ML0_METRICS_PATH,
        HR0_SCHEMA_PATH,
    ]
    protected_hashes = {
        str(path): sha256_file(root, path)
        for path in protected_candidates
        if (root / path).is_file()
    }
    protection = {
        "schema": "hr0-1-protection-manifest",
        "stage": "HR0.1",
        "protected_input_hashes": protected_hashes,
        "write_back": {
            "canonical_story_text": False,
            "canonical_people": False,
            "canonical_mentions": False,
            "canonical_facts": False,
            "canonical_relations": False,
            "participant_freeze": False,
            "hr0_gold": False,
            "hg0_graph": False,
            "ml0_artifacts": False,
        },
    }
    return benchmark, metrics, protection, {"source_hashes": source_hashes, "cases": all_cases}


def build(root: Path = ROOT) -> None:
    benchmark, metrics, protection, _ = build_documents(root)
    write_json(root, BENCHMARK_PATH, benchmark)
    write_json(root, METRICS_PATH, metrics)
    write_json(root, PROTECTION_PATH, protection)


if __name__ == "__main__":
    build()
    print(f"wrote {BENCHMARK_PATH}")
