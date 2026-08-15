#!/usr/bin/env python3
"""Validate the H0B-0 atomic social-backbone pilot."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from build_h0b0_social_backbone import (
    BACKBONE_SCHEMA_PATH,
    EVIDENCE_PATH,
    OUTPUTS,
    PEOPLE_PATH,
    PERSON_STORY_PATH,
    RELATIONS_PATH,
    SC1_PATH,
    SEEDS_PATH,
    load_inputs,
    read_json,
    sha256_file,
    validate_schema,
)


ROOT = Path(__file__).resolve().parents[1]


def document_records(relative: Path) -> list[dict[str, Any]]:
    value = read_json(relative)
    return [
        dict(item)
        for item in value.get("records", [])
        if isinstance(item, Mapping)
    ]


def validate() -> list[str]:
    errors: list[str] = []
    inputs = load_inputs()
    people = set(inputs["people_by_id"])
    selected = set(inputs["selection"]["selected_person_ids"])
    evidence = inputs["evidence_by_id"]
    seeds = inputs["seeds"]

    try:
        backbone = read_json(OUTPUTS["social_backbone"])
        validate_schema(backbone, BACKBONE_SCHEMA_PATH, "H0B-0 social backbone")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"social backbone cannot be read: {exc}"]

    expected_families = {
        "clans": ("clan_id", OUTPUTS["clans"]),
        "clan_memberships": ("membership_id", OUTPUTS["clan_memberships"]),
        "kinship": ("kinship_id", OUTPUTS["kinship"]),
        "marriages": ("marriage_id", OUTPUTS["marriages"]),
        "office_tenures": ("tenure_id", OUTPUTS["office_tenures"]),
    }
    generated_families: dict[str, list[dict[str, Any]]] = {}
    for family, (id_key, path) in expected_families.items():
        try:
            generated = document_records(path)
        except (OSError, ValueError) as exc:
            errors.append(f"{family} cannot be read: {exc}")
            continue
        generated_families[family] = generated
        seed_ids = {str(item[id_key]) for item in seeds[family]}
        generated_ids = {str(item.get(id_key)) for item in generated}
        if seed_ids != generated_ids:
            errors.append(f"{family} generated IDs differ from frozen seed IDs")
        if len(generated_ids) != len(generated):
            errors.append(f"{family} contains duplicate IDs")
        for item in generated:
            if item.get("id") != item.get(id_key):
                errors.append(f"{family} record id field is not its stable semantic ID: {item.get(id_key)}")
            if item.get("review_status") != "candidate":
                errors.append(f"new H0B-0 fact is not candidate: {item.get(id_key)}")
            for evidence_id in item.get("evidence_ids", []):
                if evidence_id not in evidence:
                    errors.append(f"{item.get(id_key)} references missing Evidence {evidence_id}")
            source_ref_ids = {ref.get("evidence_id") for ref in item.get("source_refs", [])}
            if source_ref_ids != set(item.get("evidence_ids", [])):
                errors.append(f"{item.get(id_key)} has incomplete source_refs")
            for ref in item.get("source_refs", []):
                source = evidence.get(ref.get("evidence_id"))
                if source is None:
                    continue
                locator = source.get("locator", {})
                if ref.get("artifact_sha256") != locator.get("artifact_sha256"):
                    errors.append(f"{item.get(id_key)} source hash mismatch for {ref.get('evidence_id')}")

    clan_ids = {item["clan_id"] for item in generated_families.get("clans", [])}
    kinship_ids = {item["kinship_id"] for item in generated_families.get("kinship", [])}
    for item in generated_families.get("clan_memberships", []):
        if item.get("person_id") not in people or item.get("person_id") not in selected:
            errors.append(f"ClanMembership endpoint is outside production Pilot: {item.get('id')}")
        if item.get("clan_id") not in clan_ids:
            errors.append(f"ClanMembership has unknown Clan: {item.get('id')}")
        if item.get("membership_basis") == "shared_surname":
            errors.append(f"shared surname is being used as ClanMembership evidence: {item.get('id')}")
        if item.get("branch_label") and not any(
            item.get("branch_label") == clan.get("branch_label")
            for clan in generated_families.get("clans", [])
        ):
            errors.append(f"ClanMembership branch precision is not represented by its Clan: {item.get('id')}")
        if item.get("relation_basis") == "derived":
            missing = set(item.get("derived_from_kinship_ids", [])) - kinship_ids
            if missing:
                errors.append(f"derived ClanMembership has missing Kinship source: {item.get('id')}")

    direct_kinship_ids = {
        item["kinship_id"]
        for item in generated_families.get("kinship", [])
        if item.get("relation_basis") == "direct"
    }
    for item in generated_families.get("kinship", []):
        a, b = item.get("person_a_id"), item.get("person_b_id")
        if a not in people or b not in people or a not in selected or b not in selected:
            errors.append(f"Kinship endpoint is outside production Pilot: {item.get('id')}")
        if a == b:
            errors.append(f"self-kinship: {item.get('id')}")
        if not item.get("evidence_ids"):
            errors.append(f"Kinship lacks Evidence: {item.get('id')}")
        if item.get("kinship_type") == "parent_child" and item.get("direction") != "person_a_to_person_b":
            errors.append(f"parent_child direction is not canonical: {item.get('id')}")
        if item.get("relation_basis") == "derived":
            source_ids = set(item.get("derived_from_kinship_ids", []))
            if not source_ids or not source_ids <= direct_kinship_ids:
                errors.append(f"derived KinshipFact does not use direct atomic sources: {item.get('id')}")

    marriage_pairs: set[tuple[str, str]] = set()
    for item in generated_families.get("marriages", []):
        a, b = item.get("spouse_a_id"), item.get("spouse_b_id")
        if a not in people or b not in people or a not in selected or b not in selected:
            errors.append(f"Marriage endpoint is outside production Pilot: {item.get('id')}")
        if a == b or (a, b) != tuple(sorted((a, b))):
            errors.append(f"Marriage endpoints are not canonical: {item.get('id')}")
        if (a, b) in marriage_pairs:
            errors.append(f"duplicate MarriageUnion pair: {item.get('id')}")
        marriage_pairs.add((a, b))
        if not item.get("evidence_ids"):
            errors.append(f"Marriage lacks direct Evidence: {item.get('id')}")

    for item in generated_families.get("office_tenures", []):
        person_id = item.get("person_id")
        if person_id not in people or person_id not in selected:
            errors.append(f"OfficeTenure endpoint is outside production Pilot: {item.get('id')}")
        if not item.get("office_title") or not item.get("evidence_ids"):
            errors.append(f"OfficeTenure lacks title/Evidence: {item.get('id')}")
        start, end = item.get("start_year_ce"), item.get("end_year_ce")
        if start is not None and end is not None and start > end:
            errors.append(f"OfficeTenure interval is inverted: {item.get('id')}")
        if item.get("temporal_precision") == "unknown" and (start is not None or end is not None):
            errors.append(f"unknown OfficeTenure has invented bounds: {item.get('id')}")
        forbidden_relation_keys = {"relation_id", "subject_id", "object_id", "relation_type"}
        if forbidden_relation_keys & set(item):
            errors.append(f"OfficeTenure contains interpersonal Relation fields: {item.get('id')}")

    existing_relations = {
        str(item["id"]): item
        for item in inputs["relations"]
    }
    compatibility = backbone.get("existing_relation_compatibility", [])
    compatibility_ids = {str(item.get("relation_id")) for item in compatibility}
    if compatibility_ids != set(existing_relations):
        errors.append("H0B compatibility audit does not cover exactly the current reviewed Relations")
    for item in compatibility:
        relation = existing_relations.get(str(item.get("relation_id")))
        if relation is None:
            continue
        if relation.get("review_status") != "reviewed":
            errors.append(f"compatibility target is not reviewed: {item.get('relation_id')}")
        if item.get("compatibility") not in {
            "compatible_existing_relation",
            "structurally_richer_than_relation",
            "relation_not_an_h0b_atomic_fact",
            "semantic_conflict",
        }:
            errors.append(f"unknown Relation compatibility state: {item.get('relation_id')}")

    for family, field in (
        ("clans", "clans"),
        ("clan_memberships", "clan_memberships"),
        ("kinship", "kinship"),
        ("marriages", "marriages"),
        ("office_tenures", "office_tenures"),
    ):
        generated_ids = {item.get("id") for item in generated_families.get(family, [])}
        backbone_ids = {item.get("id") for item in backbone.get(field, [])}
        if generated_ids != backbone_ids:
            errors.append(f"social backbone does not mirror {family} annotation IDs")

    for item in document_records(OUTPUTS["gap_audit"]):
        if item.get("review_status") not in {"todo", "candidate"}:
            errors.append(f"structural gap has invalid workflow status: {item.get('id')}")
        if not item.get("category"):
            errors.append(f"structural gap has no category: {item.get('id')}")
    w4 = read_json(OUTPUTS["w4_readiness"])
    for item in w4.get("recommendations", []):
        if item.get("production_effect") != "none":
            errors.append(f"W4 readiness recommendation has production effect: {item.get('id')}")
        if item.get("person_id_allocation") != "forbidden_in_h0b0":
            errors.append(f"W4 readiness recommendation allocates a Person: {item.get('id')}")

    sc1 = read_json(SC1_PATH)
    person_story = read_json(PERSON_STORY_PATH)
    if len(sc1.get("people", [])) != len(people):
        errors.append("H0B-0 changed or misread the production Person count")
    if len(sc1.get("stories", [])) != 83:
        errors.append("production Story scope is not the expected current 83-story set")
    if len(person_story.get("links", [])) != 704:
        errors.append("PersonStory link count changed from the protected baseline")
    if len(inputs["relations"]) != 12:
        errors.append("reviewed production Relation count changed from 12")
    if len(sc1.get("scene_contexts", {})) != 44:
        errors.append("Scene Context count changed from the protected baseline")
    if len(sc1.get("story_era_orientations", [])) != 83:
        errors.append("E0.1 primary Era orientation coverage changed")
    m2_after = inputs["m2_metrics"].get("after", {})
    if m2_after.get("random_person_eligible_count") != 45:
        errors.append("Random Person eligibility changed from the protected baseline")
    if backbone.get("pilot_person_ids") != inputs["selection"]["selected_person_ids"]:
        errors.append("frozen Pilot order changed in social backbone")
    if set(backbone.get("production_person_ids", [])) != people:
        errors.append("H0B backbone production Person universe differs from data/people.json")
    if backbone.get("counts", {}).get("existing_reviewed_relation_count") != len(existing_relations):
        errors.append("H0B count reports a different existing Relation count")

    metrics = read_json(OUTPUTS["metrics"])
    for key, relative in OUTPUTS.items():
        if key == "metrics":
            continue
        expected = metrics.get("artifact_hashes", {}).get(key)
        if expected and expected != sha256_file(relative):
            errors.append(f"metrics hash mismatch for {key}")

    # Canonical source and identity layers are read-only inputs to H0B-0.
    for protected in (PEOPLE_PATH, EVIDENCE_PATH, RELATIONS_PATH, PERSON_STORY_PATH, SC1_PATH, SEEDS_PATH):
        if not (ROOT / protected).is_file():
            errors.append(f"required protected input is missing: {protected}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    metrics = read_json(OUTPUTS["metrics"])
    print(
        "H0B-0 validation passed: "
        f"{metrics['clan']['count']} clans; "
        f"{metrics['kinship']['direct_count']} direct kinship facts; "
        f"{metrics['marriage']['union_count']} MarriageUnions; "
        f"{metrics['office']['tenure_count']} OfficeTenures; "
        f"{sum(metrics['structural_gaps'].values())} structural gaps"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
