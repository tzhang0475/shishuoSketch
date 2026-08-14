#!/usr/bin/env python3
"""Materialize the explicitly reviewed R3B Relation decisions.

The R3A candidate file remains the discovery/history layer.  This module is
the only build-time bridge from the curated R3B decision file to production
Relation records.  It never treats Story co-occurrence or Scene Context as a
Relation signal.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = Path("data/annotation/person-relation-candidates-r3.json")
DECISION_PATH = Path("data/annotation/person-relation-review-r3b.json")
SCHEMA_PATH = Path("schema/person-relation-review-r3b.schema.json")
PEOPLE_PATH = Path("data/people.json")
EVIDENCE_PATH = Path("data/derived/sc1-site.json")
DERIVED_PATH = Path("data/derived/person-relations-r3b.json")
REPORT_PATH = Path("docs/person-relation-review-r3b.md")


def read_json(root: Path, relative: Path) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def write_json(root: Path, relative: Path, value: Any) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _unknown_time() -> dict[str, Any]:
    return {"status": "unknown", "label": None, "start_year": None, "end_year": None}


def _candidate_map(root: Path) -> dict[str, dict[str, Any]]:
    source = read_json(root, SOURCE_PATH)
    return {
        str(record["candidate_id"]): dict(record)
        for record in source.get("records", [])
        if isinstance(record, Mapping) and isinstance(record.get("candidate_id"), str)
    }


def validate_source(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        decisions = read_json(root, DECISION_PATH)
        schema = read_json(root, SCHEMA_PATH)
        Draft202012Validator.check_schema(schema)
        errors.extend(error.message for error in Draft202012Validator(schema).iter_errors(decisions))
        candidates = _candidate_map(root)
        people = {
            str(person["person_id"])
            for person in read_json(root, PEOPLE_PATH).get("people", [])
            if isinstance(person, Mapping) and isinstance(person.get("person_id"), str)
        }
        evidence_document = read_json(root, EVIDENCE_PATH)
        evidence = {
            str(item["id"]): item
            for item in evidence_document.get("evidence", [])
            if isinstance(item, Mapping) and isinstance(item.get("id"), str)
        }
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"R3B review input cannot be read: {exc}"]

    seen_candidates: set[str] = set()
    seen_relation_ids: set[str] = set()
    for record in decisions.get("records", []):
        if not isinstance(record, Mapping):
            continue
        candidate_id = record.get("candidate_id")
        if candidate_id in seen_candidates:
            errors.append(f"duplicate R3B decision: {candidate_id}")
        seen_candidates.add(str(candidate_id))
        candidate = candidates.get(str(candidate_id))
        if candidate is None:
            errors.append(f"R3B decision references unknown R3A candidate: {candidate_id}")
            continue
        if record.get("review_status") != "reviewed":
            errors.append(f"R3B decision is not reviewed: {candidate_id}")
        if record.get("person_a_id") != candidate.get("person_a_id") or record.get("person_b_id") != candidate.get("person_b_id"):
            errors.append(f"R3B decision endpoint differs from candidate: {candidate_id}")
        for key in ("person_a_id", "person_b_id"):
            if record.get(key) not in people:
                errors.append(f"R3B decision endpoint does not resolve: {candidate_id}/{record.get(key)}")
        for evidence_id in record.get("evidence_ids", []):
            if evidence_id not in evidence:
                errors.append(f"R3B decision Evidence does not resolve: {candidate_id}/{evidence_id}")
        for key in ("source_entry_ids", "source_unit_ids", "evidence_ids"):
            if list(record.get(key, [])) != list(candidate.get(key, [])):
                errors.append(f"R3B decision changed candidate provenance field {key}: {candidate_id}")
        relation_id = record.get("production_relation_id")
        if record.get("decision") == "approved":
            if not isinstance(relation_id, str) or relation_id in seen_relation_ids:
                errors.append(f"R3B approved decision lacks a unique production relation ID: {candidate_id}")
            else:
                seen_relation_ids.add(relation_id)
        elif relation_id is not None:
            errors.append(f"deferred/rejected R3B decision must not materialize a Relation: {candidate_id}")
    if seen_candidates != set(candidates):
        errors.append("R3B decisions must cover the complete frozen R3A candidate set exactly once")
    return errors


def _materialized_relation(record: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    relation: dict[str, Any] = {
        "id": record["production_relation_id"],
        "subject_id": record["person_a_id"],
        "object_id": record["person_b_id"],
        "relation_type": record["canonical_relation_type"],
        "relation_subtype": record["canonical_relation_subtype"],
        "relation_scope": record["relation_scope"],
        "scope_event": record.get("scope_event"),
        "role_a": record["role_a"],
        "role_b": record["role_b"],
        "label": record["label"],
        "story_ids": list(record["source_entry_ids"]),
        "source_entry_ids": list(record["source_entry_ids"]),
        "source_unit_ids": list(record["source_unit_ids"]),
        "evidence_ids": list(record["evidence_ids"]),
        "relation_basis": "direct",
        "source_candidate_id": record["candidate_id"],
        "time": _unknown_time(),
        "assertion_status": candidate.get("assertion_status", "unknown"),
        "review_status": "reviewed",
        "notes": record["decision_note"],
    }
    return relation


def project(root: Path = ROOT) -> dict[str, Any]:
    errors = validate_source(root)
    if errors:
        raise ValueError("R3B review validation failed: " + "; ".join(errors))
    decisions = read_json(root, DECISION_PATH)
    records = sorted(decisions["records"], key=lambda item: (str(item["candidate_id"])))
    approved = [record for record in records if record["decision"] == "approved"]
    deferred = [record for record in records if record["decision"] == "deferred"]
    candidates = _candidate_map(root)
    materialized = sorted(
        (_materialized_relation(record, candidates[record["candidate_id"]]) for record in approved),
        key=lambda item: item["id"],
    )
    return {
        "schema": 1,
        "stage": "r3b-reviewed-relation-materialization",
        "generated_from": [str(SOURCE_PATH), str(DECISION_PATH), str(PEOPLE_PATH), str(EVIDENCE_PATH)],
        "candidate_count": len(records),
        "approved_count": len(approved),
        "deferred_count": len(deferred),
        "rejected_count": sum(record["decision"] == "rejected" for record in records),
        "decisions": records,
        "materialized_relations": materialized,
    }


def report(root: Path, projection: Mapping[str, Any]) -> str:
    names = {
        str(item["person_id"]): str(item["canonical_name"])
        for item in read_json(root, PEOPLE_PATH).get("people", [])
        if isinstance(item, Mapping) and isinstance(item.get("person_id"), str)
    }
    lines = [
        "# R3B：人物关系复核与物化",
        "",
        "本报告只物化 R3B 决策文件中明确批准的 Relation。舞台、入画、共现和 PersonStory 都不是关系生成器。R3A 候选原件仍保留在独立候选层。",
        "",
        f"- R3A 候选复核：{projection['candidate_count']} 条",
        f"- 批准物化：{projection['approved_count']} 条",
        f"- 暂缓：{projection['deferred_count']} 条",
        f"- 拒绝：{projection['rejected_count']} 条",
        "",
        "## 已批准",
        "",
    ]
    for relation in projection["materialized_relations"]:
        event = f"；范围：{relation['scope_event']}" if relation.get("scope_event") else ""
        lines.extend([
            f"### {names.get(relation['subject_id'], relation['subject_id'])} × {names.get(relation['object_id'], relation['object_id'])}",
            "",
            f"- Relation：`{relation['id']}`；{relation['relation_type']}/{relation['relation_subtype']}；{relation['label']}{event}",
            f"- 来源候选：`{relation['source_candidate_id']}`；Evidence：{', '.join(relation['evidence_ids'])}",
            f"- 角色：{relation['role_a']} — {relation['role_b']}",
            f"- 决策说明：{relation['notes']}",
            "",
        ])
    lines.extend(["## 暂缓", ""])
    for record in sorted((item for item in projection["decisions"] if item["decision"] == "deferred"), key=lambda item: item["candidate_id"]):
        lines.extend([
            f"- `{record['candidate_id']}`：{names.get(record['person_a_id'], record['person_a_id'])} × {names.get(record['person_b_id'], record['person_b_id'])}；{record['decision_note']}",
        ])
    lines.extend([
        "",
        "R3B 的 reviewed Relation 才进入生产 Relation card；候选和暂缓记录不会出现在读者端。事件范围关系使用 `scope_event` 明示，不被显示为永久敌对。",
        "",
    ])
    return "\n".join(lines)


def write_outputs(root: Path = ROOT) -> dict[str, Any]:
    projection = project(root)
    write_json(root, DERIVED_PATH, projection)
    report_path = root / REPORT_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report(root, projection), encoding="utf-8")
    return projection


def approved_relation_records(root: Path = ROOT) -> list[dict[str, Any]]:
    return list(write_outputs(root)["materialized_relations"])


def main() -> int:
    projection = write_outputs()
    print(
        f"materialized R3B review: {projection['approved_count']} approved; "
        f"{projection['deferred_count']} deferred"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
