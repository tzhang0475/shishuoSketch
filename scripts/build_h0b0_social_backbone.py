#!/usr/bin/env python3
"""Build the H0B-0 atomic social-backbone pilot.

H0B-0 deliberately keeps ClanMembership, KinshipFact, MarriageUnion, and
OfficeTenure separate from the existing reader-facing Relation graph.  The
input seed file is the frozen editorial boundary for this pilot; this module
only validates, decorates with provenance, and derives deterministic audits.
It never allocates Persons, Stories, or Relations.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
PEOPLE_PATH = Path("data/people.json")
EVIDENCE_PATH = Path("data/evidence/wp1-evidence.json")
RELATIONS_PATH = Path("data/annotation/wp1-relations.json")
PERSON_STORY_PATH = Path("data/derived/person-story-links.json")
SC1_PATH = Path("data/derived/sc1-site.json")
M2_METRICS_PATH = Path("data/derived/m2-experience-metrics.json")
SELECTION_PATH = Path("data/annotation/h0b0-pilot-selection.json")
SEEDS_PATH = Path("data/annotation/h0b0-fact-seeds.json")
SELECTION_SCHEMA_PATH = Path("schema/h0b0-pilot-selection.schema.json")
SEEDS_SCHEMA_PATH = Path("schema/h0b0-fact-seeds.schema.json")
BACKBONE_SCHEMA_PATH = Path("schema/h0b0-social-backbone.schema.json")

OUTPUTS = {
    "clans": Path("data/annotation/clans-h0b0.json"),
    "clan_memberships": Path("data/annotation/clan-memberships-h0b0.json"),
    "kinship": Path("data/annotation/kinship-h0b0.json"),
    "marriages": Path("data/annotation/marriages-h0b0.json"),
    "office_tenures": Path("data/annotation/office-tenures-h0b0.json"),
    "selection_audit": Path("data/derived/h0b0-selection-audit.json"),
    "social_backbone": Path("data/derived/h0b0-social-backbone.json"),
    "gap_audit": Path("data/derived/h0b0-structural-gap-audit.json"),
    "w4_readiness": Path("data/derived/h0b0-w4-readiness.json"),
    "metrics": Path("data/derived/h0b0-metrics.json"),
}


def read_json(relative: Path) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def write_json(relative: Path, value: Any) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def sha256_file(relative: Path) -> str:
    digest = hashlib.sha256()
    with (ROOT / relative).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unique(values: Iterable[str]) -> list[str]:
    return sorted(set(values))


def records(document: Mapping[str, Any], *keys: str) -> list[dict[str, Any]]:
    for key in keys:
        value = document.get(key)
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def validate_schema(document: Any, schema_relative: Path, label: str) -> None:
    schema = read_json(schema_relative)
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(document), key=lambda item: list(item.path))
    if errors:
        details = "; ".join(error.message for error in errors[:8])
        raise ValueError(f"{label} schema validation failed: {details}")


def load_inputs() -> dict[str, Any]:
    people_document = read_json(PEOPLE_PATH)
    evidence_document = read_json(EVIDENCE_PATH)
    relations_document = read_json(RELATIONS_PATH)
    person_story_document = read_json(PERSON_STORY_PATH)
    sc1_document = read_json(SC1_PATH)
    selection = read_json(SELECTION_PATH)
    seeds = read_json(SEEDS_PATH)

    validate_schema(selection, SELECTION_SCHEMA_PATH, "H0B-0 selection")
    validate_schema(seeds, SEEDS_SCHEMA_PATH, "H0B-0 fact seeds")

    people = records(people_document, "people")
    evidence = records(evidence_document, "records", "evidence")
    if not people:
        raise ValueError("production Person registry is empty")
    if not evidence:
        raise ValueError("WP1 Evidence registry is empty")
    return {
        "people": people,
        "people_by_id": {str(item["person_id"]): item for item in people},
        "evidence": evidence,
        "evidence_by_id": {str(item["id"]): item for item in evidence},
        "relations": records(relations_document, "materialized_relations", "relations", "records"),
        "person_story_links": records(person_story_document, "links", "records"),
        "sc1": sc1_document,
        "m2_metrics": read_json(M2_METRICS_PATH),
        "selection": selection,
        "seeds": seeds,
    }


def validate_seed_references(inputs: Mapping[str, Any]) -> None:
    people = set(inputs["people_by_id"])
    evidence = set(inputs["evidence_by_id"])
    selection = inputs["selection"]
    selected = list(selection["selected_person_ids"])
    if len(selected) < 15 or len(selected) > 20 or len(set(selected)) != len(selected):
        raise ValueError("H0B-0 frozen selection must contain 15–20 unique Persons")
    missing_selection = sorted(set(selected) - people)
    if missing_selection:
        raise ValueError(f"selection contains non-production Persons: {missing_selection}")

    seeds = inputs["seeds"]
    clan_ids = {item["clan_id"] for item in seeds["clans"]}
    for item in seeds["clans"]:
        if not item.get("evidence_ids"):
            raise ValueError(f"Clan has no Evidence: {item['clan_id']}")
        missing = sorted(set(item["evidence_ids"]) - evidence)
        if missing:
            raise ValueError(f"Clan {item['clan_id']} has missing Evidence: {missing}")
    for item in seeds["clan_memberships"]:
        if item["person_id"] not in people:
            raise ValueError(f"ClanMembership endpoint is not a production Person: {item['membership_id']}")
        if item["person_id"] not in selected:
            raise ValueError(f"ClanMembership endpoint is outside frozen Pilot: {item['membership_id']}")
        if item["clan_id"] not in clan_ids:
            raise ValueError(f"ClanMembership references unknown Clan: {item['membership_id']}")
        if item.get("membership_basis") == "shared_surname":
            raise ValueError(f"shared surname cannot create ClanMembership: {item['membership_id']}")
        missing = sorted(set(item.get("evidence_ids", [])) - evidence)
        if not missing:
            continue
        raise ValueError(f"ClanMembership {item['membership_id']} has missing Evidence: {missing}")

    kinship_ids = {item["kinship_id"] for item in seeds["kinship"]}
    if len(kinship_ids) != len(seeds["kinship"]):
        raise ValueError("duplicate H0B-0 KinshipFact ID")
    for item in seeds["kinship"]:
        for key in ("person_a_id", "person_b_id"):
            if item[key] not in people or item[key] not in selected:
                raise ValueError(f"Kinship endpoint outside frozen Pilot: {item['kinship_id']}")
        if item["person_a_id"] == item["person_b_id"]:
            raise ValueError(f"self-kinship is not allowed: {item['kinship_id']}")
        if not item.get("evidence_ids"):
            raise ValueError(f"direct/derived KinshipFact lacks Evidence: {item['kinship_id']}")
        missing = sorted(set(item["evidence_ids"]) - evidence)
        if missing:
            raise ValueError(f"KinshipFact {item['kinship_id']} has missing Evidence: {missing}")
        if item.get("relation_basis") not in {"direct", "derived"}:
            raise ValueError(f"unknown KinshipFact basis: {item['kinship_id']}")
        if item.get("relation_basis") == "derived":
            missing_sources = sorted(set(item.get("derived_from_kinship_ids", [])) - kinship_ids)
            if missing_sources:
                raise ValueError(f"derived KinshipFact has missing source facts: {item['kinship_id']}")

    marriage_pairs: set[tuple[str, str]] = set()
    marriage_ids: set[str] = set()
    for item in seeds["marriages"]:
        marriage_ids.add(item["marriage_id"])
        a, b = item["spouse_a_id"], item["spouse_b_id"]
        if a not in people or b not in people or a not in selected or b not in selected:
            raise ValueError(f"Marriage endpoint outside frozen Pilot: {item['marriage_id']}")
        if a == b or (a, b) != tuple(sorted((a, b))):
            raise ValueError(f"MarriageUnion endpoints must be canonical and distinct: {item['marriage_id']}")
        pair = (a, b)
        if pair in marriage_pairs:
            raise ValueError(f"duplicate MarriageUnion endpoints: {item['marriage_id']}")
        marriage_pairs.add(pair)
        if not item.get("evidence_ids"):
            raise ValueError(f"MarriageUnion lacks Evidence: {item['marriage_id']}")
        missing = sorted(set(item["evidence_ids"]) - evidence)
        if missing:
            raise ValueError(f"MarriageUnion {item['marriage_id']} has missing Evidence: {missing}")
        if item.get("start_year_ce") is not None and item.get("end_year_ce") is not None:
            if item["start_year_ce"] > item["end_year_ce"]:
                raise ValueError(f"invalid MarriageUnion interval: {item['marriage_id']}")

    tenure_ids: set[str] = set()
    for item in seeds["office_tenures"]:
        tenure_id = item["tenure_id"]
        if tenure_id in tenure_ids:
            raise ValueError(f"duplicate OfficeTenure ID: {tenure_id}")
        tenure_ids.add(tenure_id)
        person_id = item["person_id"]
        if person_id not in people or person_id not in selected:
            raise ValueError(f"OfficeTenure endpoint outside frozen Pilot: {tenure_id}")
        if not item.get("office_title") or not item.get("evidence_ids"):
            raise ValueError(f"OfficeTenure lacks title/Evidence: {tenure_id}")
        missing = sorted(set(item["evidence_ids"]) - evidence)
        if missing:
            raise ValueError(f"OfficeTenure {tenure_id} has missing Evidence: {missing}")
        start, end = item.get("start_year_ce"), item.get("end_year_ce")
        if start is not None and end is not None and start > end:
            raise ValueError(f"invalid OfficeTenure interval: {tenure_id}")
        if item.get("temporal_precision") == "unknown" and (start is not None or end is not None):
            raise ValueError(f"unknown OfficeTenure cannot carry unqualified bounds: {tenure_id}")

    for collection_name in ("gaps", "w4_recommendations"):
        ids: set[str] = set()
        id_key = "gap_id" if collection_name == "gaps" else "recommendation_id"
        for item in seeds[collection_name]:
            item_id = item[id_key]
            if item_id in ids:
                raise ValueError(f"duplicate H0B-0 {collection_name} ID: {item_id}")
            ids.add(item_id)
            missing = sorted(set(item.get("evidence_ids", [])) - evidence)
            if missing:
                raise ValueError(f"{collection_name} {item_id} has missing Evidence: {missing}")
            unknown_people = sorted(set(item.get("affected_person_ids", [])) - people)
            if unknown_people:
                raise ValueError(f"{collection_name} {item_id} references unknown Persons: {unknown_people}")


def source_ref(evidence_id: str, evidence_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    item = evidence_by_id[evidence_id]
    locator = item.get("locator", {})
    result: dict[str, Any] = {
        "evidence_id": evidence_id,
        "source_id": item.get("source_id"),
        "evidence_type": item.get("evidence_type"),
        "artifact_type": locator.get("artifact_type"),
        "artifact_path": locator.get("artifact_path"),
        "artifact_sha256": locator.get("artifact_sha256"),
        "entry_id": locator.get("entry_id"),
        "unit_id": locator.get("unit_id"),
        "source_witness_id": locator.get("source_provenance", {}).get("witness_id"),
        "source_path": locator.get("source_provenance", {}).get("source_path"),
        "source_sha256": locator.get("source_provenance", {}).get("source_sha256"),
    }
    return result


def decorate(
    items: Iterable[Mapping[str, Any]],
    id_key: str,
    evidence_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for original in items:
        item = copy.deepcopy(dict(original))
        item["id"] = item[id_key]
        evidence_ids = unique(item.get("evidence_ids", []))
        item["evidence_ids"] = evidence_ids
        item["source_refs"] = [
            source_ref(evidence_id, evidence_by_id)
            for evidence_id in evidence_ids
        ]
        item["production_scope"] = "h0b0-pilot"
        output.append(item)
    return output


def build_selection_audit(inputs: Mapping[str, Any]) -> dict[str, Any]:
    people = inputs["people_by_id"]
    selected = list(inputs["selection"]["selected_person_ids"])
    selected_set = set(selected)
    links_by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for link in inputs["person_story_links"]:
        person_id = link.get("person_id")
        if isinstance(person_id, str):
            links_by_person[person_id].append(link)
    story_to_era = {
        str(story.get("id")): story.get("primary_era_card_id")
        for story in inputs["sc1"].get("stories", [])
        if isinstance(story, Mapping) and isinstance(story.get("id"), str)
    }
    eras_by_person: dict[str, set[str]] = defaultdict(set)
    for person_id, links in links_by_person.items():
        for link in links:
            era_id = story_to_era.get(str(link.get("entry_id")))
            if isinstance(era_id, str) and era_id:
                eras_by_person[person_id].add(era_id)

    relation_neighbors: dict[str, set[str]] = defaultdict(set)
    relation_degree: Counter[str] = Counter()
    for relation in inputs["relations"]:
        a, b = relation.get("subject_id"), relation.get("object_id")
        if isinstance(a, str) and isinstance(b, str):
            relation_neighbors[a].add(b)
            relation_neighbors[b].add(a)
            relation_degree[a] += 1
            relation_degree[b] += 1

    seeds = inputs["seeds"]
    clan_count: Counter[str] = Counter(item["person_id"] for item in seeds["clan_memberships"])
    kin_count: Counter[str] = Counter()
    structural_neighbors: dict[str, set[str]] = defaultdict(set)
    for item in seeds["kinship"]:
        a, b = item["person_a_id"], item["person_b_id"]
        kin_count[a] += 1
        kin_count[b] += 1
        structural_neighbors[a].add(b)
        structural_neighbors[b].add(a)
    marriage_count: Counter[str] = Counter()
    for item in seeds["marriages"]:
        marriage_count[item["spouse_a_id"]] += 1
        marriage_count[item["spouse_b_id"]] += 1
        structural_neighbors[item["spouse_a_id"]].add(item["spouse_b_id"])
        structural_neighbors[item["spouse_b_id"]].add(item["spouse_a_id"])
    office_count: Counter[str] = Counter(item["person_id"] for item in seeds["office_tenures"])
    clans_by_person: dict[str, set[str]] = defaultdict(set)
    for membership in seeds["clan_memberships"]:
        clans_by_person[membership["person_id"]].add(membership["clan_id"])
    gap_count: Counter[str] = Counter(
        person_id
        for gap in seeds["gaps"]
        for person_id in gap.get("affected_person_ids", [])
    )
    selected_rank = {person_id: index + 1 for index, person_id in enumerate(selected)}
    audit_records: list[dict[str, Any]] = []
    for person_id in sorted(people):
        related = structural_neighbors[person_id] | relation_neighbors[person_id]
        signals = {
            "published_story_count": len(links_by_person.get(person_id, [])),
            "relation_degree": relation_degree[person_id],
            "direct_clan_evidence_count": clan_count[person_id],
            "direct_kinship_evidence_count": kin_count[person_id],
            "direct_marriage_evidence_count": marriage_count[person_id],
            "office_evidence_count": office_count[person_id],
            "structurally_connected_production_person_count": len(related & set(people)),
            "missing_bridge_identity_count": gap_count[person_id],
            "cross_era_relevance": len(eras_by_person[person_id]),
            "cross_clan_bridge_value": len(
                {
                    clan_id
                    for related_person in related
                    for clan_id in clans_by_person[related_person]
                    if clan_id not in clans_by_person[person_id]
                }
            ),
        }
        score = (
            signals["published_story_count"]
            + signals["relation_degree"] * 3
            + signals["direct_clan_evidence_count"] * 4
            + signals["direct_kinship_evidence_count"] * 5
            + signals["direct_marriage_evidence_count"] * 7
            + signals["office_evidence_count"] * 2
            + signals["structurally_connected_production_person_count"] * 3
            + signals["cross_era_relevance"] * 2
            + signals["cross_clan_bridge_value"] * 4
        )
        audit_records.append(
            {
                "person_id": person_id,
                "canonical_name": people[person_id].get("canonical_name"),
                "selected": person_id in selected_set,
                "selection_rank": selected_rank.get(person_id),
                "structural_signals": signals,
                "selection_score_for_audit_only": score,
                "notes": "分数只用于解释试点结构信号，不是历史重要性或自动选人依据。",
            }
        )
    return {
        "schema": 1,
        "stage": "h0b0-selection-audit",
        "selection_manifest": str(SELECTION_PATH),
        "selection_status": inputs["selection"]["selection_status"],
        "selected_person_ids": selected,
        "production_person_count": len(people),
        "records": audit_records,
        "method": {
            "story_count": "current PersonStory links",
            "relation_degree": "existing production Relation endpoints",
            "structural_counts": "H0B-0 frozen fact seeds",
            "warning": "audit signals never promote an identity or materialize a fact",
        },
    }


def build_relation_compatibility(
    inputs: Mapping[str, Any],
    facts: Mapping[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    relation_to_facts: dict[str, list[str]] = defaultdict(list)
    for family in ("kinship", "marriages"):
        for item in facts[family]:
            for relation_id in item.get("compatibility_relation_ids", []):
                relation_to_facts[relation_id].append(item["id"])
    relation_to_facts["relation-r3b-003"].append("h0b0-office-008")

    output: list[dict[str, Any]] = []
    for relation in sorted(inputs["relations"], key=lambda item: str(item.get("id", ""))):
        relation_id = str(relation["id"])
        linked = sorted(set(relation_to_facts.get(relation_id, [])))
        relation_type = relation.get("relation_type")
        if linked:
            compatibility = "compatible_existing_relation"
            note = "H0B 原子事实与既有 reviewed Relation 语义兼容；本阶段不改写生产 Relation。"
        elif relation_type == "institutional":
            compatibility = "relation_not_an_h0b_atomic_fact"
            note = "Relation 仍是人物间语义边；OfficeTenure 只记录任职事实，不替代该边。"
        elif relation_type in {"friendship", "political"}:
            compatibility = "relation_not_an_h0b_atomic_fact"
            note = "友谊/事件政治关系不是本 Pilot 的四类原子结构事实，继续由 Relation 层管理。"
        else:
            compatibility = "relation_not_an_h0b_atomic_fact"
            note = "当前 Relation 没有可安全投影为 H0B-0 原子事实的等价记录。"
        output.append(
            {
                "relation_id": relation_id,
                "relation_type": relation_type,
                "person_a_id": relation.get("subject_id"),
                "person_b_id": relation.get("object_id"),
                "compatibility": compatibility,
                "h0b0_fact_ids": linked,
                "existing_relation_review_status": relation.get("review_status"),
                "note": note,
            }
        )
    return output


def write_annotation_family(
    relative: Path,
    stage: str,
    records_value: list[dict[str, Any]],
    generated_from: list[str],
) -> None:
    write_json(
        relative,
        {
            "schema": 1,
            "stage": stage,
            "generated_from": generated_from,
            "record_count": len(records_value),
            "records": records_value,
        },
    )


def build_outputs(inputs: Mapping[str, Any]) -> dict[str, Any]:
    validate_seed_references(inputs)
    evidence_by_id = inputs["evidence_by_id"]
    seeds = inputs["seeds"]
    selected = list(inputs["selection"]["selected_person_ids"])

    facts = {
        "clans": decorate(seeds["clans"], "clan_id", evidence_by_id),
        "clan_memberships": decorate(seeds["clan_memberships"], "membership_id", evidence_by_id),
        "kinship": decorate(seeds["kinship"], "kinship_id", evidence_by_id),
        "marriages": decorate(seeds["marriages"], "marriage_id", evidence_by_id),
        "office_tenures": decorate(seeds["office_tenures"], "tenure_id", evidence_by_id),
    }
    generated_from = [
        str(PEOPLE_PATH),
        str(EVIDENCE_PATH),
        str(RELATIONS_PATH),
        str(PERSON_STORY_PATH),
        str(SELECTION_PATH),
        str(SEEDS_PATH),
    ]
    write_annotation_family(OUTPUTS["clans"], "h0b0-clans", facts["clans"], generated_from)
    write_annotation_family(
        OUTPUTS["clan_memberships"],
        "h0b0-clan-memberships",
        facts["clan_memberships"],
        generated_from,
    )
    write_annotation_family(OUTPUTS["kinship"], "h0b0-kinship", facts["kinship"], generated_from)
    write_annotation_family(OUTPUTS["marriages"], "h0b0-marriages", facts["marriages"], generated_from)
    write_annotation_family(
        OUTPUTS["office_tenures"],
        "h0b0-office-tenures",
        facts["office_tenures"],
        generated_from,
    )

    selection_audit = build_selection_audit(inputs)
    write_json(OUTPUTS["selection_audit"], selection_audit)

    compatibility = build_relation_compatibility(inputs, facts)
    production_person_ids = sorted(inputs["people_by_id"])
    backbone = {
        "schema": 1,
        "stage": "h0b0-social-backbone",
        "generated_from": generated_from,
        "production_person_ids": production_person_ids,
        "pilot_person_ids": selected,
        "clans": facts["clans"],
        "clan_memberships": facts["clan_memberships"],
        "kinship": facts["kinship"],
        "marriages": facts["marriages"],
        "office_tenures": facts["office_tenures"],
        "existing_relation_compatibility": compatibility,
        "policy": seeds["policy"],
        "counts": {
            "production_person_count": len(production_person_ids),
            "pilot_person_count": len(selected),
            "clan_count": len(facts["clans"]),
            "clan_membership_count": len(facts["clan_memberships"]),
            "kinship_direct_count": sum(item.get("relation_basis") == "direct" for item in facts["kinship"]),
            "kinship_derived_count": sum(item.get("relation_basis") == "derived" for item in facts["kinship"]),
            "marriage_union_count": len(facts["marriages"]),
            "office_tenure_count": len(facts["office_tenures"]),
            "existing_reviewed_relation_count": len(inputs["relations"]),
        },
    }
    validate_schema(backbone, BACKBONE_SCHEMA_PATH, "H0B-0 social backbone")
    write_json(OUTPUTS["social_backbone"], backbone)

    gap_records = decorate(seeds["gaps"], "gap_id", evidence_by_id)
    for gap in gap_records:
        gap["review_status"] = "todo"
        gap["assertion_status"] = "unknown"
    gap_counts = Counter(str(item["category"]) for item in gap_records)
    gap_audit = {
        "schema": 1,
        "stage": "h0b0-structural-gap-audit",
        "generated_from": generated_from,
        "scope": {
            "production_person_count": len(production_person_ids),
            "pilot_person_count": len(selected),
            "production_persons_are_not_expanded": True,
        },
        "summary": {
            "gap_count": len(gap_records),
            "by_category": dict(sorted(gap_counts.items())),
        },
        "records": gap_records,
        "notes": "这些是当前生产 scope 的结构性缺口，不是 H0B-0 的待办物化事实。",
    }
    write_json(OUTPUTS["gap_audit"], gap_audit)

    recommendations = []
    for item in sorted(seeds["w4_recommendations"], key=lambda value: (value["priority"], value["recommendation_id"])):
        record = decorate([item], "recommendation_id", evidence_by_id)[0]
        record["production_effect"] = "none"
        record["person_id_allocation"] = "forbidden_in_h0b0"
        record["story_publication"] = "forbidden_in_h0b0"
        recommendations.append(record)
    w4 = {
        "schema": 1,
        "stage": "h0b0-w4-readiness",
        "generated_from": [str(OUTPUTS["gap_audit"]), str(SEEDS_PATH)],
        "recommendation_count": len(recommendations),
        "recommendations": recommendations,
        "notes": "规划性输出；不分配 Person ID、不发布 Story、不创建新的生产事实。",
    }
    write_json(OUTPUTS["w4_readiness"], w4)

    person_story_count = len(inputs["person_story_links"])
    sc1 = inputs["sc1"]
    m2_after = inputs["m2_metrics"].get("after", {})
    production_person_ids_set = set(production_person_ids)
    orphan_mention_count = sum(
        1
        for mention in sc1.get("mentions", [])
        if isinstance(mention, Mapping)
        and mention.get("person_id") is not None
        and mention.get("person_id") not in production_person_ids_set
    )
    orphan_mention_count += sum(
        1
        for story in sc1.get("stories", [])
        if isinstance(story, Mapping)
        for segment in story.get("reading", {}).get("main_text", {}).get("segments", [])
        if isinstance(segment, Mapping)
        and segment.get("type") == "person_mention"
        and segment.get("person_id") not in production_person_ids_set
    )
    office_precision = Counter(str(item.get("temporal_precision", "unknown")) for item in facts["office_tenures"])
    compatibility_counts = Counter(str(item["compatibility"]) for item in compatibility)
    metrics = {
        "schema": 1,
        "stage": "h0b0-metrics",
        "pilot": {
            "selected_person_count": len(selected),
            "selected_person_ids": selected,
        },
        "clan": {
            "count": len(facts["clans"]),
            "membership_count": len(facts["clan_memberships"]),
            "unresolved_branch_count": gap_counts.get("clan_branch_unresolved", 0),
        },
        "kinship": {
            "direct_count": sum(item.get("relation_basis") == "direct" for item in facts["kinship"]),
            "derived_count": sum(item.get("relation_basis") == "derived" for item in facts["kinship"]),
            "gap_count": sum(item.get("structural_type") == "kinship" for item in gap_records),
        },
        "marriage": {
            "union_count": len(facts["marriages"]),
            "non_production_spouse_gap_count": sum(
                item.get("category") == "marriage_spouse_not_production" for item in gap_records
            ),
        },
        "office": {
            "tenure_count": len(facts["office_tenures"]),
            "temporal_precision_distribution": dict(sorted(office_precision.items())),
        },
        "structural_gaps": dict(sorted(gap_counts.items())),
        "w4_readiness": {
            "recommendation_count": len(recommendations),
            "top_recommendation_ids": [item["recommendation_id"] for item in recommendations[:5]],
        },
        "relation_compatibility": dict(sorted(compatibility_counts.items())),
        "protected_baseline": {
            "production_person_count": len(sc1.get("people", [])),
            "production_story_count": len(sc1.get("stories", [])),
            "person_story_link_count": person_story_count,
            "random_person_eligible_count": m2_after.get("random_person_eligible_count"),
            "scene_context_count": len(sc1.get("scene_contexts", {})),
            "reviewed_relation_count": len(sc1.get("relations", [])),
            "primary_era_orientation_count": len(sc1.get("story_era_orientations", [])),
            "orphan_mention_count": orphan_mention_count,
        },
        "invariants": {
            "new_production_person_count": 0,
            "new_production_story_count": 0,
            "new_reviewed_relation_count": 0,
            "frontend_changed": False,
            "canonical_sources_changed": False,
        },
        "artifact_hashes": {},
    }
    write_json(OUTPUTS["metrics"], metrics)
    artifact_hashes = {
        key: sha256_file(relative)
        for key, relative in OUTPUTS.items()
        if key != "metrics"
    }
    metrics["artifact_hashes"] = artifact_hashes
    write_json(OUTPUTS["metrics"], metrics)
    return {
        "facts": facts,
        "backbone": backbone,
        "gap_audit": gap_audit,
        "w4": w4,
        "metrics": metrics,
        "selection_audit": selection_audit,
    }


def main() -> int:
    inputs = load_inputs()
    output = build_outputs(inputs)
    counts = output["backbone"]["counts"]
    print(
        "H0B-0 social backbone: "
        f"{counts['clan_count']} clans, "
        f"{counts['clan_membership_count']} memberships, "
        f"{counts['kinship_direct_count']} direct kinship facts, "
        f"{counts['marriage_union_count']} marriages, "
        f"{counts['office_tenure_count']} office fragments; "
        f"{len(output['gap_audit']['records'])} structural gaps"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
