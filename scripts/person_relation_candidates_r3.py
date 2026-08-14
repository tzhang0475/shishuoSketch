#!/usr/bin/env python3
"""Build the R3A explicit Person Relation discovery artifacts.

R3A is deliberately a review layer.  It reads the current production Person
registry and existing source Evidence, but never mutates reviewed Relations
or projects candidate edges into the frontend.
"""

from __future__ import annotations

from hashlib import sha256
import itertools
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = Path("data/annotation/person-relation-candidates-r3.json")
SCHEMA_PATH = Path("schema/person-relation-candidate.schema.json")
SC1_PATH = Path("data/derived/sc1-site.json")
RELATIONS_PATH = Path("data/annotation/wp1-relations.json")
R3B_REVIEW_PATH = Path("data/annotation/person-relation-review-r3b.json")
WAVE_PATH = Path("data/annotation/person-expansion-wave-1.json")
WAVE2_PATH = Path("data/annotation/person-expansion-wave-2.json")
DERIVED_PATH = Path("data/derived/person-relation-candidates-r3.json")
REPORT_PATH = Path("docs/person-relation-candidates-r3.md")

TIER_ORDER = {"A": 0, "B": 1, "C": 2}


def read_json(root: Path, relative: Path) -> Any:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def write_json(root: Path, relative: Path, value: Any) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _unique_sorted(values: Iterable[str]) -> list[str]:
    return sorted({value for value in values if isinstance(value, str) and value})


def _pair(person_a_id: str, person_b_id: str) -> tuple[str, str]:
    return tuple(sorted((person_a_id, person_b_id)))


def candidate_id(record: Mapping[str, Any]) -> str:
    """Return an opaque ID from stable semantic fields, never from names."""

    # R3A candidate IDs are analysis identities, not Person IDs.  Once a
    # candidate is emitted into the curated review layer, keep that opaque ID
    # frozen across a Person foreign-key migration.
    explicit = record.get("candidate_id")
    if isinstance(explicit, str) and explicit:
        return explicit

    payload = {
        key: record.get(key)
        for key in (
            "person_a_id",
            "person_b_id",
            "proposed_relation_class",
            "proposed_role_a",
            "proposed_role_b",
            "relation_scope",
            "source_entry_ids",
            "source_unit_ids",
            "evidence_ids",
        )
    }
    digest = sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"r3-candidate-{digest[:20]}"


def _compact(text: str, limit: int = 180) -> str:
    value = " ".join(str(text).split())
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _evidence_layer(evidence: Mapping[str, Any]) -> str:
    locator = evidence.get("locator", {})
    artifact_type = locator.get("artifact_type")
    if artifact_type == "jinshu_unit":
        return "jinshu"
    if artifact_type == "shishuo_entry":
        if evidence.get("evidence_type") == "annotation" or locator.get("annotation_id"):
            return "shishuo_liu_annotation"
        return "shishuo_main_text"
    return str(evidence.get("source_id") or "unknown")


def _evidence_summary(evidence: Mapping[str, Any]) -> dict[str, Any]:
    locator = evidence.get("locator", {})
    return {
        "id": evidence["id"],
        "layer": _evidence_layer(evidence),
        "evidence_type": evidence.get("evidence_type"),
        "source_entry_id": locator.get("entry_id"),
        "source_unit_id": locator.get("unit_id"),
        "assertion_status": evidence.get("assertion_status"),
        "quote": _compact(str(evidence.get("quote", ""))),
    }


def _tier(record: Mapping[str, Any]) -> str:
    risks = set(record.get("risk_flags", []))
    if "event_bounded" in risks or "political_scope_requires_review" in risks:
        return "C"
    if "scene_and_institutional_scope_overlap" in risks or "reported_annotation" in risks:
        return "B"
    if record.get("discovery_basis", "").startswith("explicit_"):
        return "A"
    return "B"


def _sort_candidate(item: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        TIER_ORDER[str(item["review_tier"])],
        -len(item.get("evidence_ids", [])),
        -int(item.get("metrics", {}).get("current_story_count", 0)),
        str(item["candidate_id"]),
    )


def _reviewed_relations(root: Path) -> list[dict[str, Any]]:
    document = read_json(root, RELATIONS_PATH)
    return [
        record
        for record in document.get("records", [])
        if isinstance(record, Mapping) and record.get("review_status") == "reviewed"
    ]


def _r3b_decisions(root: Path) -> dict[str, dict[str, Any]]:
    path = root / R3B_REVIEW_PATH
    if not path.is_file():
        return {}
    document = read_json(root, R3B_REVIEW_PATH)
    return {
        str(record["candidate_id"]): dict(record)
        for record in document.get("records", [])
        if isinstance(record, Mapping) and isinstance(record.get("candidate_id"), str)
    }


def _project_candidate(
    record: Mapping[str, Any],
    *,
    names: Mapping[str, str],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    stories: Mapping[str, Mapping[str, Any]],
    reviewed_pairs: Mapping[tuple[str, str], list[str]],
    r3b_decisions: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    a, b = str(record["person_a_id"]), str(record["person_b_id"])
    evidence = [evidence_by_id[evidence_id] for evidence_id in record["evidence_ids"]]
    source_entry_ids = _unique_sorted(
        [*record.get("source_entry_ids", []), *[str(e.get("locator", {}).get("entry_id")) for e in evidence if e.get("locator", {}).get("entry_id")]]
    )
    source_unit_ids = _unique_sorted(
        [*record.get("source_unit_ids", []), *[str(e.get("locator", {}).get("unit_id")) for e in evidence if e.get("locator", {}).get("unit_id")]]
    )
    current_story_ids = sorted(
        story_id
        for story_id, story in stories.items()
        if a in story.get("person_ids", []) and b in story.get("person_ids", [])
    )
    layers = _unique_sorted(_evidence_layer(item) for item in evidence)
    relation_pair = _pair(a, b)
    r3b = r3b_decisions.get(candidate_id(record), {})
    disposition = "unreviewed"
    materialized_relation_id = None
    if r3b:
        disposition = {
            "approved": "approved_materialized",
            "deferred": "deferred",
            "rejected": "rejected",
        }.get(str(r3b.get("decision")), "unreviewed")
        materialized_relation_id = r3b.get("production_relation_id")
    result = {
        "candidate_id": candidate_id(record),
        "person_a_id": a,
        "person_b_id": b,
        "person_a_name": names[a],
        "person_b_name": names[b],
        "proposed_relation_class": record["proposed_relation_class"],
        "proposed_role_a": record["proposed_role_a"],
        "proposed_role_b": record["proposed_role_b"],
        "relation_scope": record["relation_scope"],
        "source_entry_ids": source_entry_ids,
        "source_unit_ids": source_unit_ids,
        "evidence_ids": list(record["evidence_ids"]),
        "assertion_status": record["assertion_status"],
        "review_status": record["review_status"],
        "review_tier": _tier(record),
        "discovery_basis": record["discovery_basis"],
        "discovery_note": record["discovery_note"],
        "risk_flags": list(record.get("risk_flags", [])),
        "metrics": {
            "evidence_count": len(evidence),
            "source_layer_count": len(layers),
            "current_story_count": len(current_story_ids),
            "shared_story_count": len(current_story_ids),
        },
        "current_story_ids": current_story_ids,
        "evidence_summary": [_evidence_summary(item) for item in evidence],
        "existing_reviewed_relation_ids": list(reviewed_pairs.get(relation_pair, [])),
        "review_disposition": disposition,
    }
    if isinstance(materialized_relation_id, str):
        result["materialized_relation_id"] = materialized_relation_id
    return result


def _pair_audit(
    people: list[str],
    stories: Mapping[str, Mapping[str, Any]],
    reviewed_pairs: Mapping[tuple[str, str], list[str]],
    candidate_pairs: set[tuple[str, str]],
    names: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    counts: dict[tuple[str, str], list[str]] = {}
    for story_id, story in stories.items():
        story_people = sorted(set(story.get("person_ids", [])) & set(people))
        for a, b in itertools.combinations(story_people, 2):
            counts.setdefault((a, b), []).append(story_id)
    cooccurrence_only: list[dict[str, Any]] = []
    all_pairs: list[dict[str, Any]] = []
    for a, b in itertools.combinations(sorted(people), 2):
        story_ids = sorted(counts.get((a, b), []))
        relation_ids = reviewed_pairs.get((a, b), [])
        row = {
            "person_a_id": a,
            "person_b_id": b,
            "person_a_name": names[a],
            "person_b_name": names[b],
            "shared_story_count": len(story_ids),
            "shared_story_ids": story_ids,
            "reviewed_relation_ids": list(relation_ids),
            "has_r3a_candidate": (a, b) in candidate_pairs,
        }
        all_pairs.append(row)
        if story_ids and not relation_ids and (a, b) not in candidate_pairs:
            cooccurrence_only.append(row)
    cooccurrence_only.sort(key=lambda row: (-row["shared_story_count"], row["person_a_id"], row["person_b_id"]))
    return all_pairs, cooccurrence_only[:30]


def _scene_encounters(
    root: Path,
    *,
    names: Mapping[str, str],
    reviewed_pairs: Mapping[tuple[str, str], list[str]],
    candidate_by_pair: Mapping[tuple[str, str], str],
) -> list[dict[str, Any]]:
    scene_source = read_json(root, Path("data/annotation/story-scene-contexts.json"))
    rows: list[dict[str, Any]] = []
    for record in scene_source.get("records", []):
        scene_people = sorted({item["person_id"] for item in record.get("people_at_scene", [])})
        for a, b in itertools.combinations(scene_people, 2):
            pair = _pair(a, b)
            rows.append(
                {
                    "story_id": record["story_id"],
                    "person_a_id": a,
                    "person_b_id": b,
                    "person_a_name": names.get(a, a),
                    "person_b_name": names.get(b, b),
                    "reviewed_relation_ids": list(reviewed_pairs.get(pair, [])),
                    "r3a_candidate_id": candidate_by_pair.get(pair),
                    "disposition": "candidate_or_reviewed_relation_exists" if pair in reviewed_pairs or pair in candidate_by_pair else "scene_encounter_only",
                }
            )
    return sorted(rows, key=lambda row: (row["story_id"], row["person_a_id"], row["person_b_id"]))


def project(root: Path = ROOT) -> dict[str, Any]:
    source = read_json(root, SOURCE_PATH)
    bundle = read_json(root, SC1_PATH)
    reviewed_relations = _reviewed_relations(root)
    r3b_decisions = _r3b_decisions(root)
    names = {
        str(person["id"]): str(person["canonical_name"])
        for person in bundle.get("people", [])
        if isinstance(person, Mapping) and isinstance(person.get("id"), str)
    }
    people = sorted(names)
    evidence_by_id = {
        str(item["id"]): item
        for item in bundle.get("evidence", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    stories = {
        str(story["id"]): story
        for story in bundle.get("stories", [])
        if isinstance(story, Mapping)
        and isinstance(story.get("id"), str)
        and story.get("publication_state") != "blocked"
    }
    reviewed_pairs: dict[tuple[str, str], list[str]] = {}
    already_reviewed: list[dict[str, Any]] = []
    for relation in reviewed_relations:
        a, b = _pair(str(relation["subject_id"]), str(relation["object_id"]))
        reviewed_pairs.setdefault((a, b), []).append(str(relation["id"]))
        already_reviewed.append(
            {
                "relation_id": relation["id"],
                "person_a_id": a,
                "person_b_id": b,
                "person_a_name": names.get(a, a),
                "person_b_name": names.get(b, b),
                "relation_type": relation.get("relation_type"),
                "relation_subtype": relation.get("relation_subtype"),
                "label": relation.get("label"),
            }
        )
    for relation_ids in reviewed_pairs.values():
        relation_ids.sort()
    already_reviewed.sort(key=lambda row: row["relation_id"])

    candidates: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for record in source.get("records", []):
        pair = _pair(str(record["person_a_id"]), str(record["person_b_id"]))
        if pair in seen_pairs:
            raise ValueError(f"duplicate R3A candidate pair: {pair}")
        seen_pairs.add(pair)
        candidates.append(
            _project_candidate(
                record,
                names=names,
                evidence_by_id=evidence_by_id,
                stories=stories,
                reviewed_pairs=reviewed_pairs,
                r3b_decisions=r3b_decisions,
            )
        )
    candidates.sort(key=_sort_candidate)
    for rank, item in enumerate(candidates, start=1):
        item["rank"] = rank

    all_pairs, cooccurrence_only = _pair_audit(people, stories, reviewed_pairs, seen_pairs, names)
    candidate_by_pair = {_pair(item["person_a_id"], item["person_b_id"]): item["candidate_id"] for item in candidates}
    scene_encounters = _scene_encounters(
        root,
        names=names,
        reviewed_pairs=reviewed_pairs,
        candidate_by_pair=candidate_by_pair,
    )
    wave = read_json(root, WAVE_PATH)
    wave_person_ids = sorted(
        str(member["person_id"])
        for member in wave.get("members", [])
        if isinstance(member, Mapping) and isinstance(member.get("person_id"), str)
    )
    wave2 = read_json(root, WAVE2_PATH)
    wave2_person_ids = sorted(
        str(member["person_id"])
        for member in wave2.get("members", [])
        if isinstance(member, Mapping) and isinstance(member.get("person_id"), str)
    )
    candidate_endpoint_ids = {endpoint for item in candidates for endpoint in (item["person_a_id"], item["person_b_id"])}
    isolated = sorted(
        person_id
        for person_id in people
        if not any(person_id in pair for pair in reviewed_pairs)
    )
    tier_counts = {tier: sum(item["review_tier"] == tier for item in candidates) for tier in ("A", "B", "C")}
    return {
        "schema": 1,
        "stage": "r3a-explicit-person-relation-discovery",
        "generated_from": [str(SOURCE_PATH), str(SC1_PATH), str(RELATIONS_PATH), str(R3B_REVIEW_PATH), str(WAVE_PATH), str(WAVE2_PATH)],
        "production_person_count": len(people),
        "production_person_ids": people,
        "reviewed_relation_count": len(reviewed_relations),
        "reviewed_direct_relation_count": sum(relation.get("relation_basis") == "direct" for relation in reviewed_relations),
        "pair_count_audited": len(all_pairs),
        "candidate_count": len(candidates),
        "tier_counts": tier_counts,
        "already_reviewed_rediscoveries": already_reviewed,
        "already_reviewed_rediscovery_count": len(already_reviewed),
        "candidates": candidates,
        "cooccurrence_only_pair_count": len(cooccurrence_only),
        "cooccurrence_only_pairs": cooccurrence_only,
        "scene_encounters": scene_encounters,
        "wave1_person_ids": wave_person_ids,
        "wave2_person_ids": wave2_person_ids,
        "wave1_persons_with_candidate_relation": sorted(set(wave_person_ids) & candidate_endpoint_ids),
        "wave2_persons_with_candidate_relation": sorted(set(wave2_person_ids) & candidate_endpoint_ids),
        "isolated_person_ids_by_reviewed_relation": isolated,
        "notes": [
        "R3A is a candidate review layer; approved R3B decisions are retained as provenance but only the R3B materialization builder updates production Relation output.",
            "Shared Story and Scene co-occurrence are reported separately and never become Relation candidates by themselves.",
        "Candidate IDs are opaque hashes of stable endpoint/class/source fields, not names or rank positions.",
        ],
    }


def render_report(document: Mapping[str, Any]) -> str:
    lines = [
        "# R3A：显式人物关系发现候选",
        "",
        "本报告是当前生产人物的关系发现审计，不是 Relation 生产写入。所有候选的 `review_status` 均为 `candidate`；同则共现、Scene 场景位置和 PersonStory 连接不会单独生成关系候选。",
        "",
        "## 审计摘要",
        "",
        f"- 当前生产人物：**{document['production_person_count']}**",
        f"- 已审阅 Relation：**{document['reviewed_relation_count']}**（其中 direct **{document['reviewed_direct_relation_count']}**）",
        f"- 人物无序对审计：**{document['pair_count_audited']}**",
        f"- 显式候选：**{document['candidate_count']}**（Tier A {document['tier_counts']['A']} / B {document['tier_counts']['B']} / C {document['tier_counts']['C']}）",
        f"- 已审阅关系再发现控制项：**{document['already_reviewed_rediscovery_count']}**",
        f"- 仅共现、未形成候选的组合（报告上限 30）：**{document['cooccurrence_only_pair_count']}**",
        f"- Wave-1 中已有候选端点的人物：**{len(document['wave1_persons_with_candidate_relation'])}**；Wave-2：**{len(document['wave2_persons_with_candidate_relation'])}**",
        f"- 仅按已审阅 Relation 仍孤立的人物：**{len(document['isolated_person_ids_by_reviewed_relation'])}**",
        "",
        "## 候选关系",
        "",
    ]
    for candidate in document["candidates"]:
        lines.extend(
            [
                f"### {candidate['person_a_name']} × {candidate['person_b_name']}",
                "",
                f"- Rank：{candidate['rank']} · Tier {candidate['review_tier']} · Candidate ID：`{candidate['candidate_id']}` · R3B：{candidate.get('review_disposition', 'unreviewed')}",
                f"- 建议类别：`{candidate['proposed_relation_class']}`；范围：`{candidate['relation_scope']}`",
                f"- 角色：{candidate['person_a_name']}（{candidate['proposed_role_a']}）— {candidate['person_b_name']}（{candidate['proposed_role_b']}）",
                f"- 来源：{', '.join(candidate['source_entry_ids'] + candidate['source_unit_ids']) or '未提供'}",
                f"- 发现依据：{candidate['discovery_note']}",
                f"- 风险：{', '.join(candidate['risk_flags']) or '无额外标记'}",
            ]
        )
        for evidence in candidate["evidence_summary"]:
            lines.append(f"- 证据（{evidence['layer']} · {evidence['id']}）：“{evidence['quote']}”")
        lines.append("")

    lines.extend(["## 已审阅关系再发现控制", ""])
    for relation in document["already_reviewed_rediscoveries"]:
        lines.append(f"- `{relation['relation_id']}`：{relation['person_a_name']} × {relation['person_b_name']} · {relation['label']}")
    lines.extend(
        [
            "",
            "## Scene / Relation 交叉审计",
            "",
            "Scene 只解释本则人物为何在此相遇；只有来源独立明确写出长期、社会或制度关系，才进入上面的候选。",
            "",
        ]
    )
    for row in document["scene_encounters"]:
        if row["disposition"] == "scene_encounter_only":
            lines.append(f"- `{row['story_id']}`：{row['person_a_name']} × {row['person_b_name']} — 仅场景相遇，未生成 Relation 候选。")
    lines.extend(["", "## 仅共现审计（不是关系）", ""])
    for row in document["cooccurrence_only_pairs"][:12]:
        lines.append(f"- {row['person_a_name']} × {row['person_b_name']}：共享 {row['shared_story_count']} 则 Story（{', '.join(row['shared_story_ids'])}）。")
    lines.extend(
        [
            "",
            "## 下一步",
            "",
            "本产物保留 R3A 候选与 R3B 决策的审计链。只有 R3B 明确批准的记录才会出现在读者端 Relation card；暂缓和未审候选不会写入生产 Relation。",
            "",
        ]
    )
    return "\n".join(lines)


def build(root: Path = ROOT) -> tuple[Path, Path]:
    document = project(root)
    write_json(root, DERIVED_PATH, document)
    report_path = root / REPORT_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(document), encoding="utf-8")
    return root / DERIVED_PATH, report_path


def validate_source(root: Path = ROOT) -> list[str]:
    source = read_json(root, SOURCE_PATH)
    schema = read_json(root, SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    return [error.message for error in Draft202012Validator(schema).iter_errors(source)]


if __name__ == "__main__":
    for path in build():
        print(path)
