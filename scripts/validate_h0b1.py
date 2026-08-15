#!/usr/bin/env python3
"""Validate H0B-1 without weakening the frozen H0B-0/H0A boundaries."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from build_h0b1_social_temporal_backbone import (
    ANCHORS_PATH,
    EFFECTIVE_MENTIONS_PATH,
    GAP_CATEGORIES,
    H0B0_BACKBONE_PATH,
    H0B0_FAMILY_PATHS,
    OUTPUTS,
    PEOPLE_PATH,
    RELATIONS_PATH,
    SC1_PATH,
    SCENE_CONTEXT_PATH,
    SEEDS_PATH,
    W4_METRICS_PATH,
    load_inputs,
    read_json,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = Path("schema/h0b1-social-temporal-backbone.schema.json")


def validate_schema(value: Any, label: str) -> list[str]:
    schema = read_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    return [f"{label}: {error.message}" for error in Draft202012Validator(schema).iter_errors(value)]


def ids(rows: list[Mapping[str, Any]], key: str) -> list[str]:
    return [str(row.get(key, row.get("id"))) for row in rows]


def validate() -> list[str]:
    errors: list[str] = []
    try:
        inputs = load_inputs()
        backbone = read_json(OUTPUTS["backbone"])
        metrics = read_json(OUTPUTS["metrics"])
        participants = read_json(OUTPUTS["participants"])
        constraints = read_json(OUTPUTS["constraints"])
        relation_contexts = read_json(OUTPUTS["relation_contexts"])
        activity_compatibility = read_json(OUTPUTS["activity_compatibility"])
        person_coverage = read_json(OUTPUTS["person_coverage"])
        gaps = read_json(OUTPUTS["gap_audit"])
        reconciliation = read_json(OUTPUTS["reconciliation"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"H0B-1 artifacts cannot be read: {exc}"]

    errors.extend(validate_schema(backbone, "H0B-1 backbone"))
    people = set(inputs["people_by_id"])
    stories = set(inputs["story_by_id"])
    evidence = set(inputs["evidence_by_id"])

    # Protected production scope.
    if set(backbone.get("production_person_ids", [])) != people or len(people) != 75:
        errors.append("H0B-1 production Person scope is not exactly the current 75-Person registry")
    if len(stories) != 143:
        errors.append("current Story scope is not exactly 143")
    person_story = inputs["person_story"]
    if len(person_story.get("links", [])) != 875:
        errors.append("PersonStory link count is not the corrected 875 baseline")
    if int(person_story.get("reviewed_link_count", 0)) != 870:
        errors.append("reviewed PersonStory count is not the corrected 870 baseline")
    current_metrics = read_json(W4_METRICS_PATH)
    if current_metrics.get("network", {}).get("random_person_eligible_after") != 69:
        errors.append("Random Person eligible count is not 69")
    if len(inputs["relations"]) != 12:
        errors.append("reviewed Relation count changed from 12")
    if len(inputs["sc1"].get("scene_contexts", {})) != 44:
        errors.append("Scene Context count changed from 44")
    if len(inputs["orientations"]) != 143:
        errors.append("primary Era orientation coverage is not 143")

    # H0B-0 imports must be exact old IDs, without a copied new namespace.
    for family, path in H0B0_FAMILY_PATHS.items():
        old_rows = read_json(path).get("records", [])
        key = {"clans": "clan_id", "clan_memberships": "membership_id", "kinship": "kinship_id", "marriages": "marriage_id", "office_tenures": "tenure_id"}[family]
        old_ids = ids(old_rows, key)
        if backbone.get("h0b0_imports", {}).get(family) != old_ids:
            errors.append(f"H0B-0 import IDs changed for {family}")
        if sha256_file(path) != metrics.get("frozen_h0b0_hashes", {}).get(family):
            errors.append(f"frozen H0B-0 artifact hash mismatch for {family}")
    for label, path in {
        "social_backbone": H0B0_BACKBONE_PATH,
        "structural_gap_audit": Path("data/derived/h0b0-structural-gap-audit.json"),
        "metrics": Path("data/derived/h0b0-metrics.json"),
    }.items():
        if sha256_file(path) != metrics.get("frozen_h0b0_hashes", {}).get(label):
            errors.append(f"frozen H0B-0 artifact hash mismatch for {label}")
    if sha256_file(SEEDS_PATH) != metrics.get("seed_sha256"):
        errors.append("H0B-1 seed hash changed after generation")

    if sha256_file(ANCHORS_PATH) != metrics.get("h0a_anchor_sha256"):
        errors.append("H0A StoryTemporalAnchor hash changed during H0B-1")
    if metrics.get("invariants", {}).get("h0a_rewritten") is not False:
        errors.append("H0B-1 reports that H0A was rewritten")

    # Consolidated facts.
    family_specs = {
        "clans": ("clan_id", "clan_count"),
        "clan_memberships": ("membership_id", "clan_membership_count"),
        "kinship": ("kinship_id", "kinship_direct_count"),
        "marriages": ("marriage_id", "marriage_union_count"),
        "office_tenures": ("tenure_id", "office_tenure_count"),
    }
    all_fact_ids: set[str] = set()
    for family, (key, count_key) in family_specs.items():
        rows = [row for row in backbone.get(family, []) if isinstance(row, Mapping)]
        row_ids = ids(rows, key)
        if len(row_ids) != len(set(row_ids)):
            errors.append(f"duplicate H0B-1 {family} IDs")
        all_fact_ids.update(row_ids)
        for row in rows:
            evidence_ids = set(row.get("evidence_ids", []))
            missing = sorted(evidence_ids - evidence)
            if missing:
                errors.append(f"{family} {row.get(key)} references missing Evidence: {missing}")
            if row.get("review_status") == "reviewed" and row.get("production_scope") == "h0b1-scale-up":
                errors.append(f"new H0B-1 fact is marked reviewed without an existing review path: {row.get(key)}")
        if len(rows) != metrics.get("social", {}).get(count_key, len(rows)):
            errors.append(f"H0B-1 count mismatch for {family}")

    memberships = backbone.get("clan_memberships", [])
    clan_ids = {str(row.get("clan_id")) for row in backbone.get("clans", [])}
    for row in memberships:
        if row.get("person_id") not in people or row.get("clan_id") not in clan_ids:
            errors.append(f"invalid ClanMembership endpoints: {row.get('membership_id')}")
        if row.get("membership_basis") in {"shared_surname", "story_cooccurrence"}:
            errors.append(f"unsafe surname/cooccurrence ClanMembership: {row.get('membership_id')}")

    kinship_ids = {str(row.get("kinship_id", row.get("id"))) for row in backbone.get("kinship", [])}
    for row in backbone.get("kinship", []):
        a, b = row.get("person_a_id"), row.get("person_b_id")
        if a not in people or b not in people or a == b:
            errors.append(f"invalid Kinship endpoints: {row.get('kinship_id')}")
        if not row.get("evidence_ids"):
            errors.append(f"Kinship lacks Evidence: {row.get('kinship_id')}")
        if row.get("relation_basis") == "derived" and not set(row.get("derived_from_kinship_ids", [])) <= kinship_ids:
            errors.append(f"derived Kinship has missing source facts: {row.get('kinship_id')}")

    marriage_pairs: set[tuple[str, str]] = set()
    for row in backbone.get("marriages", []):
        a, b = row.get("spouse_a_id"), row.get("spouse_b_id")
        if a not in people or b not in people or a == b or (a, b) != tuple(sorted((a, b))):
            errors.append(f"non-canonical MarriageUnion: {row.get('marriage_id')}")
        pair = (str(a), str(b))
        if pair in marriage_pairs:
            errors.append(f"duplicate MarriageUnion endpoints: {row.get('marriage_id')}")
        marriage_pairs.add(pair)

    for row in backbone.get("office_tenures", []):
        if row.get("person_id") not in people:
            errors.append(f"OfficeTenure endpoint is not production: {row.get('tenure_id')}")
        start, end = row.get("start_year_ce"), row.get("end_year_ce")
        if start is not None and end is not None and start > end:
            errors.append(f"OfficeTenure interval is reversed: {row.get('tenure_id')}")
        if row.get("temporal_precision") == "unknown" and any(row.get(key) is not None for key in ("start_year_ce", "end_year_ce", "lower_bound_year_ce", "upper_bound_year_ce")):
            errors.append(f"unknown OfficeTenure carries bounds: {row.get('tenure_id')}")
        if not row.get("office_title") or not row.get("evidence_ids"):
            errors.append(f"OfficeTenure lacks title/Evidence: {row.get('tenure_id')}")

    # Participant semantics.
    participant_story_ids = {str(row.get("story_id")) for row in participants.get("records", [])}
    if participant_story_ids != stories:
        errors.append("StoryParticipant projection does not cover exactly all 143 Stories")
    participant_rows = [row for story in participants.get("records", []) for row in story.get("participants", [])]
    for row in participant_rows:
        if row.get("person_id") not in people or row.get("story_id") not in stories:
            errors.append(f"StoryParticipant has invalid endpoint: {row.get('participant_id')}")
        expected_hard = row.get("role") in {"present", "speaker", "actor"}
        if row.get("hard_temporal_eligible") is not expected_hard:
            errors.append(f"StoryParticipant hard eligibility mismatch: {row.get('participant_id')}")
        if row.get("role") not in {"present", "speaker", "actor", "referenced", "off_frame", "annotation_only", "uncertain"}:
            errors.append(f"unknown StoryParticipant role: {row.get('participant_id')}")
    bad_望之 = [row for row in participant_rows if row.get("story_id") == "08-shangyu-079" and row.get("person_id") == "person-029" and row.get("hard_temporal_eligible")]
    if bad_望之:
        errors.append("lexical 望之 re-entered hard Story participation for person-029")

    # Constraint scope and conservative hierarchy.
    anchor_by_story = {str(row.get("story_id")): row for row in inputs["anchors"]}
    constraint_rows = constraints.get("records", [])
    if {str(row.get("story_id")) for row in constraint_rows} != stories:
        errors.append("H0B-1 social-temporal constraints do not cover exactly all Stories")
    if len(constraint_rows) != 143:
        errors.append("H0B-1 social-temporal constraint count is not 143")
    for row in constraint_rows:
        story_id = str(row.get("story_id"))
        if row.get("h0a_precision") != anchor_by_story.get(story_id, {}).get("precision"):
            errors.append(f"H0A precision changed in H0B-1 constraint projection: {story_id}")
        for group_name in ("participant_constraints", "office_constraints", "relation_constraints", "marriage_constraints", "kinship_constraints"):
            for item in row.get(group_name, []):
                if group_name == "participant_constraints" and item.get("basis") not in {"person_activity_anchor"}:
                    errors.append(f"unexpected participant constraint basis: {story_id}")
        for candidate_office in row.get("candidate_office_constraints", []):
            if candidate_office.get("hard_temporal_eligible") is not False:
                errors.append(f"candidate OfficeTenure was marked hard: {story_id}")
            if candidate_office.get("review_status") == "rejected":
                errors.append(f"rejected OfficeTenure entered candidate temporal projection: {story_id}")
        if any(item.get("review_status") != "reviewed" for item in row.get("office_constraints", [])):
            errors.append(f"unreviewed OfficeTenure entered hard temporal constraints: {story_id}")
        for group_name in ("participant_constraints", "office_constraints", "event_constraints", "relation_constraints"):
            for item in row.get(group_name, []):
                start, end = item.get("start_year_ce"), item.get("end_year_ce")
                if start is not None and end is not None and start > end:
                    errors.append(f"reversed H0B-1 interval in {story_id}")
        if row.get("constraint_precision") == "conflict" and not row.get("conflict_flags"):
            errors.append(f"conflict precision without conflict flag: {story_id}")
        if row.get("h0a_upgrade_candidate") and row.get("h0a_precision") != "unknown":
            errors.append(f"upgrade candidate is not based on H0A unknown: {story_id}")

    # Relation contexts are metadata over the exact existing 12 Relations.
    relation_ids = {str(row["id"]) for row in inputs["relations"]}
    context_rows = relation_contexts.get("records", [])
    if {str(row.get("relation_id")) for row in context_rows} != relation_ids:
        errors.append("RelationTemporalContext scope differs from the existing 12 Relations")
    if len(context_rows) != 12:
        errors.append("RelationTemporalContext count is not 12")
    if len(relation_contexts.get("records", [])) != len(relation_ids):
        errors.append("RelationTemporalContext duplicates exist")

    if {str(row.get("person_id")) for row in person_coverage.get("records", [])} != people:
        errors.append("Person structural coverage audit does not cover all 75 Persons")
    if reconciliation.get("h0b0_artifact_unchanged") is not True:
        errors.append("H0B-0 reconciliation does not assert frozen input")
    if gaps.get("category_catalog") != list(GAP_CATEGORIES):
        errors.append("H0B-1 gap category catalog is incomplete or unstable")
    if set(gaps.get("summary", {}).get("by_category", {})) != set(GAP_CATEGORIES):
        errors.append("H0B-1 gap summary does not expose all supported categories")

    protected = metrics.get("protected_baseline", {})
    expected_protected = {
        "production_person_count": 75,
        "production_story_count": 143,
        "person_story_link_count": 875,
        "reviewed_person_story_link_count": 870,
        "random_person_eligible_count": 69,
        "reviewed_relation_count": 12,
        "scene_context_count": 44,
        "orphan_mention_count": 0,
        "primary_era_orientation_count": 143,
    }
    for key, value in expected_protected.items():
        if protected.get(key) != value:
            errors.append(f"protected H0B-1 metric mismatch: {key}={protected.get(key)!r}, expected {value!r}")

    # The corrected lexical collision must stay absent from the effective
    # identity layer, not merely absent from the new participant projection.
    effective = read_json(EFFECTIVE_MENTIONS_PATH)
    for group in ("mentions", "derived_mentions"):
        for mention in effective.get(group, []):
            if mention.get("source_id") == "08-shangyu-079" and mention.get("surface") == "望之" and mention.get("person_id") == "person-029":
                errors.append("effective identity layer still resolves lexical 望之 to person-029")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    metrics = read_json(OUTPUTS["metrics"])
    print(
        "H0B-1 validation passed: "
        f"{metrics['scope']['persons_audited']} Persons, "
        f"{metrics['scope']['stories_audited']} Stories, "
        f"{metrics['social']['office_tenure_count']} OfficeTenures, "
        f"{metrics['story_temporal']['h0a_upgrade_candidate_count']} upgrade candidates, "
        "H0A unchanged"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
