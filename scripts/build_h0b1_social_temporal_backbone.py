#!/usr/bin/env python3
"""Build the H0B-1 social and temporal backbone.

H0B-1 is deliberately a new projection over the frozen H0B-0 pilot.  The
builder never rewrites H0B-0, H0A anchors, Person IDs, PersonStory links, or
the reader bundle.  It imports the old atomic facts by their original IDs,
adds only the small set of locally evidenced candidate facts in the H0B-1
seed file, and derives conservative participation and temporal audits for all
published Stories.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]

PEOPLE_PATH = Path("data/people.json")
EVIDENCE_PATH = Path("data/evidence/wp1-evidence.json")
SC1_PATH = Path("data/derived/sc1-site.json")
PERSON_STORY_PATH = Path("data/derived/person-story-links.json")
EFFECTIVE_MENTIONS_PATH = Path("data/derived/person-resolution-effective.json")
SCENE_CONTEXT_PATH = Path("data/derived/story-scene-contexts.json")
ANCHORS_PATH = Path("data/annotation/story-temporal-anchors-h0a.json")
ACTIVITY_PATH = Path("data/annotation/person-activity-anchors-h0a.json")
EVENTS_PATH = Path("data/annotation/historical-events-h0a.json")
COORDINATES_PATH = Path("data/derived/h0a-temporal-coordinates.json")
ERA_ORIENTATION_PATH = Path("data/derived/e0-story-era-orientations.json")
RELATIONS_PATH = Path("data/annotation/wp1-relations.json")
SEEDS_PATH = Path("data/annotation/h0b1-fact-seeds.json")
H0B0_BACKBONE_PATH = Path("data/derived/h0b0-social-backbone.json")
H0B0_GAPS_PATH = Path("data/derived/h0b0-structural-gap-audit.json")
H0B0_METRICS_PATH = Path("data/derived/h0b0-metrics.json")
W4_METRICS_PATH = Path("data/derived/w4-metrics.json")

GAP_CATEGORIES = (
    "missing_structural_endpoint",
    "missing_family_bridge",
    "marriage_endpoint_not_production",
    "clan_branch_unresolved",
    "office_chronology_incomplete",
    "relation_temporal_scope_missing",
    "participant_role_uncertain",
    "identity_compatibility_gap",
    "source_conflict",
    "temporal_conflict",
    "evidence_too_broad",
)

LEGACY_GAP_CATEGORY_MAP = {
    "missing_bridge_identity": "missing_structural_endpoint",
    "marriage_spouse_not_production": "marriage_endpoint_not_production",
    "missing_story_evidence": "missing_family_bridge",
}

H0B0_FAMILY_PATHS = {
    "clans": Path("data/annotation/clans-h0b0.json"),
    "clan_memberships": Path("data/annotation/clan-memberships-h0b0.json"),
    "kinship": Path("data/annotation/kinship-h0b0.json"),
    "marriages": Path("data/annotation/marriages-h0b0.json"),
    "office_tenures": Path("data/annotation/office-tenures-h0b0.json"),
}

OUTPUTS = {
    "clans": Path("data/annotation/clans-h0b1.json"),
    "clan_memberships": Path("data/annotation/clan-memberships-h0b1.json"),
    "kinship": Path("data/annotation/kinship-h0b1.json"),
    "marriages": Path("data/annotation/marriages-h0b1.json"),
    "office_tenures": Path("data/annotation/office-tenures-h0b1.json"),
    "person_coverage": Path("data/derived/h0b1-person-coverage-audit.json"),
    "participants": Path("data/derived/h0b1-story-participants.json"),
    "backbone": Path("data/derived/h0b1-social-backbone.json"),
    "relation_contexts": Path("data/derived/h0b1-relation-temporal-contexts.json"),
    "activity_compatibility": Path("data/derived/h0b1-person-activity-compatibility.json"),
    "constraints": Path("data/derived/h0b1-social-temporal-constraints.json"),
    "upgrade_queue": Path("data/derived/h0b1-h0a-upgrade-queue.json"),
    "gap_audit": Path("data/derived/h0b1-gap-audit.json"),
    "reconciliation": Path("data/derived/h0b1-h0b0-reconciliation.json"),
    "p4_readiness": Path("data/derived/h0b1-p4-readiness.json"),
    "es0_readiness": Path("data/derived/h0b1-es0-readiness.json"),
    "metrics": Path("data/derived/h0b1-metrics.json"),
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


def stable_id(prefix: str, *parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def unique(values: Iterable[str]) -> list[str]:
    return sorted({str(value) for value in values if value is not None})


def records(document: Mapping[str, Any], *keys: str) -> list[dict[str, Any]]:
    for key in keys:
        value = document.get(key)
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def published_stories(sc1: Mapping[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        [dict(item) for item in sc1.get("stories", []) if isinstance(item, Mapping)],
        key=lambda item: (int(item.get("global_ordinal", 10**9)), str(item.get("id", ""))),
    )


def source_ref(evidence_id: str, evidence_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    evidence = evidence_by_id.get(evidence_id)
    if evidence is None:
        if evidence_id.startswith("h0a-"):
            return {"evidence_id": evidence_id, "source_layer": "h0a_temporal_projection"}
        return {"evidence_id": evidence_id, "source_layer": "repository_local_evidence"}
    locator = evidence.get("locator", {})
    provenance = locator.get("source_provenance", {}) if isinstance(locator, Mapping) else {}
    return {
        "evidence_id": evidence_id,
        "source_id": evidence.get("source_id"),
        "evidence_type": evidence.get("evidence_type"),
        "artifact_type": locator.get("artifact_type"),
        "artifact_path": locator.get("artifact_path"),
        "artifact_sha256": locator.get("artifact_sha256"),
        "entry_id": locator.get("entry_id"),
        "unit_id": locator.get("unit_id"),
        "source_witness_id": provenance.get("witness_id"),
        "source_path": provenance.get("source_path"),
        "source_sha256": provenance.get("source_sha256"),
    }


def decorate_new(item: Mapping[str, Any], id_key: str, evidence_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    result = copy.deepcopy(dict(item))
    result["id"] = result[id_key]
    result["evidence_ids"] = unique(result.get("evidence_ids", []))
    result["source_refs"] = [source_ref(item_id, evidence_by_id) for item_id in result["evidence_ids"]]
    result["production_scope"] = "h0b1-scale-up"
    return result


def family_document(stage: str, rows: list[dict[str, Any]], generated_from: list[str]) -> dict[str, Any]:
    return {
        "schema": 1,
        "stage": stage,
        "generated_from": generated_from,
        "record_count": len(rows),
        "records": rows,
    }


def load_inputs() -> dict[str, Any]:
    people_document = read_json(PEOPLE_PATH)
    evidence_document = read_json(EVIDENCE_PATH)
    sc1 = read_json(SC1_PATH)
    person_story = read_json(PERSON_STORY_PATH)
    mentions = read_json(EFFECTIVE_MENTIONS_PATH)
    scene = read_json(SCENE_CONTEXT_PATH)
    anchors = read_json(ANCHORS_PATH)
    activity = read_json(ACTIVITY_PATH)
    events = read_json(EVENTS_PATH)
    coordinates = read_json(COORDINATES_PATH)
    orientations = read_json(ERA_ORIENTATION_PATH)
    relations = read_json(RELATIONS_PATH)
    seeds = read_json(SEEDS_PATH)
    h0b0 = read_json(H0B0_BACKBONE_PATH)
    h0b0_gaps = read_json(H0B0_GAPS_PATH)
    h0b0_metrics = read_json(H0B0_METRICS_PATH)
    w4_metrics = read_json(W4_METRICS_PATH)

    people = records(people_document, "people", "records")
    evidence = records(evidence_document, "records", "evidence")
    # Scene Context evidence is materialized in the SC1 bundle rather than
    # duplicated into the WP1 evidence registry.  It is still repository-local
    # provenance and must be available to H0B-1 seed validation.
    sc1_evidence = records(sc1, "evidence", "records")
    evidence_by_id = {str(item["id"]): item for item in [*evidence, *sc1_evidence] if item.get("id")}
    if not people or not evidence:
        raise ValueError("H0B-1 requires the production Person and Evidence registries")
    return {
        "people": people,
        "people_by_id": {str(item.get("id", item.get("person_id"))): item for item in people},
        "evidence": evidence,
        "evidence_by_id": evidence_by_id,
        "sc1": sc1,
        "stories": published_stories(sc1),
        "story_by_id": {str(item["id"]): item for item in published_stories(sc1)},
        "person_story": person_story,
        "mentions": mentions,
        "scene": scene,
        "anchors": records(anchors, "records"),
        "activity": records(activity, "records"),
        "events": records(events, "records"),
        "coordinates": coordinates,
        "orientations": records(orientations, "records"),
        "relations": records(relations, "records"),
        "seeds": seeds,
        "h0b0": h0b0,
        "h0b0_gaps": records(h0b0_gaps, "records"),
        "h0b0_metrics": h0b0_metrics,
        "w4_metrics": w4_metrics,
    }


def validate_seed_inputs(inputs: Mapping[str, Any]) -> None:
    seeds = inputs["seeds"]
    people = set(inputs["people_by_id"])
    evidence = set(inputs["evidence_by_id"])
    for collection in ("new_clans", "new_clan_memberships", "new_kinship", "new_marriages", "new_office_tenures", "participant_seeds"):
        if not isinstance(seeds.get(collection), list):
            raise ValueError(f"H0B-1 seed collection is not a list: {collection}")
    for key, id_key in (
        ("new_clans", "clan_id"),
        ("new_clan_memberships", "membership_id"),
        ("new_kinship", "kinship_id"),
        ("new_marriages", "marriage_id"),
        ("new_office_tenures", "tenure_id"),
        ("participant_seeds", "participant_id"),
    ):
        ids = [str(item[id_key]) for item in seeds[key]]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate H0B-1 seed IDs in {key}")
        for item in seeds[key]:
            missing = sorted(set(item.get("evidence_ids", [])) - evidence)
            if missing:
                raise ValueError(f"{key} {item[id_key]} references missing Evidence: {missing}")

    clan_ids = {str(item["clan_id"]) for item in inputs["seeds"]["new_clans"]}
    for item in seeds["new_clan_memberships"]:
        if item["person_id"] not in people:
            raise ValueError(f"new ClanMembership endpoint is not production: {item['membership_id']}")
        if item["clan_id"] not in clan_ids and item["clan_id"] not in {
            str(record.get("clan_id")) for record in inputs["h0b0"].get("clans", [])
        }:
            raise ValueError(f"new ClanMembership references unknown Clan: {item['membership_id']}")
        if item.get("membership_basis") in {"shared_surname", "story_cooccurrence"}:
            raise ValueError(f"unsafe ClanMembership basis: {item['membership_id']}")

    for item in seeds["new_kinship"]:
        a, b = item["person_a_id"], item["person_b_id"]
        if a not in people or b not in people or a == b:
            raise ValueError(f"invalid H0B-1 Kinship endpoints: {item['kinship_id']}")
        if item.get("relation_basis") not in {"direct", "derived"}:
            raise ValueError(f"invalid H0B-1 Kinship basis: {item['kinship_id']}")

    for item in seeds["new_marriages"]:
        a, b = item["spouse_a_id"], item["spouse_b_id"]
        if a not in people or b not in people or a == b or (a, b) != tuple(sorted((a, b))):
            raise ValueError(f"invalid H0B-1 Marriage endpoints: {item['marriage_id']}")
        if item.get("start_year_ce") is not None and item.get("end_year_ce") is not None and item["start_year_ce"] > item["end_year_ce"]:
            raise ValueError(f"invalid H0B-1 Marriage interval: {item['marriage_id']}")

    for item in seeds["new_office_tenures"]:
        if item["person_id"] not in people:
            raise ValueError(f"OfficeTenure endpoint is not production: {item['tenure_id']}")
        start, end = item.get("start_year_ce"), item.get("end_year_ce")
        if start is not None and end is not None and start > end:
            raise ValueError(f"invalid OfficeTenure interval: {item['tenure_id']}")
        precision = item.get("temporal_precision")
        if precision == "unknown" and any(item.get(key) is not None for key in ("start_year_ce", "end_year_ce", "lower_bound_year_ce", "upper_bound_year_ce")):
            raise ValueError(f"unknown OfficeTenure carries bounds: {item['tenure_id']}")

    story_ids = set(inputs["story_by_id"])
    for item in seeds["participant_seeds"]:
        if item["story_id"] not in story_ids:
            raise ValueError(f"participant seed references unpublished Story: {item['participant_id']}")
        if item["person_id"] not in people:
            raise ValueError(f"participant seed references unknown Person: {item['participant_id']}")
        if item.get("role") not in {"present", "speaker", "actor", "referenced", "off_frame", "annotation_only", "uncertain"}:
            raise ValueError(f"invalid participant role: {item['participant_id']}")


def load_h0b0_family(relative: Path) -> list[dict[str, Any]]:
    document = read_json(relative)
    return [copy.deepcopy(item) for item in document.get("records", []) if isinstance(item, Mapping)]


def build_facts(inputs: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    validate_seed_inputs(inputs)
    seeds = inputs["seeds"]
    evidence_by_id = inputs["evidence_by_id"]
    facts: dict[str, list[dict[str, Any]]] = {}
    for family, path in H0B0_FAMILY_PATHS.items():
        old_rows = load_h0b0_family(path)
        key = {
            "clans": "new_clans",
            "clan_memberships": "new_clan_memberships",
            "kinship": "new_kinship",
            "marriages": "new_marriages",
            "office_tenures": "new_office_tenures",
        }[family]
        id_key = {
            "clans": "clan_id",
            "clan_memberships": "membership_id",
            "kinship": "kinship_id",
            "marriages": "marriage_id",
            "office_tenures": "tenure_id",
        }[family]
        old_ids = {str(item.get(id_key, item.get("id"))) for item in old_rows}
        new_rows = [decorate_new(item, id_key, evidence_by_id) for item in seeds[key]]
        duplicate = old_ids & {str(item[id_key]) for item in new_rows}
        if duplicate:
            raise ValueError(f"H0B-1 duplicates frozen H0B-0 fact IDs: {sorted(duplicate)}")
        facts[family] = old_rows + new_rows
    return facts


ROLE_RANK = {
    "annotation_only": 1,
    "referenced": 2,
    "off_frame": 3,
    "uncertain": 4,
    "present": 5,
    "speaker": 6,
    "actor": 7,
}


def add_participant(
    target: dict[tuple[str, str], dict[str, Any]],
    *,
    story_id: str,
    person_id: str,
    role: str,
    basis: str,
    evidence_ids: Iterable[str],
    assertion_status: str = "attested",
    review_status: str = "candidate",
    source_sections: Iterable[str] = (),
    notes: str | None = None,
) -> None:
    key = (story_id, person_id)
    current = target.get(key)
    if current is None:
        current = {
            "story_id": story_id,
            "person_id": person_id,
            "role": role,
            "basis": basis,
            "evidence_ids": [],
            "source_sections": [],
            "assertion_status": assertion_status,
            "review_status": review_status,
            "notes": notes,
        }
        target[key] = current
    elif ROLE_RANK.get(role, 0) > ROLE_RANK.get(str(current.get("role")), 0):
        current["role"] = role
        current["basis"] = basis
        current["notes"] = notes or current.get("notes")
    current["evidence_ids"] = unique([*current.get("evidence_ids", []), *list(evidence_ids)])
    current["source_sections"] = unique([*current.get("source_sections", []), *list(source_sections)])
    if current.get("assertion_status") != "attested" and assertion_status == "attested":
        current["assertion_status"] = assertion_status


def build_participants(inputs: Mapping[str, Any]) -> dict[str, Any]:
    people = set(inputs["people_by_id"])
    story_ids = set(inputs["story_by_id"])
    participants: dict[tuple[str, str], dict[str, Any]] = {}
    scene_contexts = inputs["scene"].get("contexts", {})
    scene_role_map = {
        "present": "present",
        "discussed": "referenced",
        "referenced_in_context": "off_frame",
        "unknown": "uncertain",
    }
    for story_id in sorted(scene_contexts):
        if story_id not in story_ids:
            continue
        context = scene_contexts[story_id]
        for person in context.get("people_at_scene", []):
            person_id = str(person.get("person_id"))
            if person_id not in people:
                continue
            role = scene_role_map.get(str(person.get("scene_role")), "uncertain")
            add_participant(
                participants,
                story_id=story_id,
                person_id=person_id,
                role=role,
                basis="reviewed_scene_context",
                evidence_ids=person.get("evidence_ids", []),
                assertion_status=str(person.get("assertion_status", "attested")),
                review_status=str(person.get("review_status", "candidate")),
                source_sections=person.get("source_layers", []),
                notes="Scene Context semantics are authoritative for present/off-frame distinction.",
            )

    for seed in inputs["seeds"].get("participant_seeds", []):
        add_participant(
            participants,
            story_id=str(seed["story_id"]),
            person_id=str(seed["person_id"]),
            role=str(seed["role"]),
            basis=str(seed["basis"]),
            evidence_ids=seed.get("evidence_ids", []),
            assertion_status=str(seed.get("assertion_status", "attested")),
            review_status=str(seed.get("review_status", "candidate")),
            source_sections=["main_text"],
            notes=seed.get("notes"),
        )

    effective_mentions = inputs["mentions"]
    mention_rows = [
        *records(effective_mentions, "mentions"),
        *records(effective_mentions, "derived_mentions"),
    ]
    for mention in mention_rows:
        story_id = str(mention.get("source_id", mention.get("story_id", mention.get("entry_id", ""))))
        person_id = mention.get("person_id")
        if story_id not in story_ids or not isinstance(person_id, str) or person_id not in people:
            continue
        section = str(mention.get("section", ""))
        role = "referenced" if section == "main_text" else "annotation_only"
        add_participant(
            participants,
            story_id=story_id,
            person_id=person_id,
            role=role,
            basis="resolved_mention_only",
            evidence_ids=mention.get("evidence_ids", []),
            assertion_status=str(mention.get("assertion_status", "inferred")),
            review_status=str(mention.get("review_status", "candidate")),
            source_sections=[section] if section else [],
            notes="Mention resolution is retained as contextual evidence; it is not hard Story participation.",
        )

    rows: list[dict[str, Any]] = []
    for (story_id, person_id), item in sorted(participants.items()):
        row = copy.deepcopy(item)
        row["participant_id"] = stable_id("h0b1-participant", story_id, person_id)
        row["hard_temporal_eligible"] = row["role"] in {"present", "speaker", "actor"}
        row["evidence_ids"] = unique(row.get("evidence_ids", []))
        row["source_sections"] = unique(row.get("source_sections", []))
        row["review_status"] = row.get("review_status") or "candidate"
        rows.append(row)

    by_story: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_story[row["story_id"]].append(row)
    story_records = []
    for story_id in sorted(story_ids):
        story_rows = sorted(by_story.get(story_id, []), key=lambda item: (item["person_id"], item["participant_id"]))
        story_records.append(
            {
                "story_id": story_id,
                "participants": story_rows,
                "hard_participant_ids": sorted({item["person_id"] for item in story_rows if item["hard_temporal_eligible"]}),
                "referenced_person_ids": sorted({item["person_id"] for item in story_rows if item["role"] == "referenced"}),
                "off_frame_person_ids": sorted({item["person_id"] for item in story_rows if item["role"] == "off_frame"}),
                "annotation_only_person_ids": sorted({item["person_id"] for item in story_rows if item["role"] == "annotation_only"}),
                "review_status": "candidate",
            }
        )
    return {
        "schema": 1,
        "stage": "h0b1-story-participants",
        "generated_from": [str(SCENE_CONTEXT_PATH), str(EFFECTIVE_MENTIONS_PATH), str(SEEDS_PATH)],
        "scope": {"story_count": len(story_ids), "production_person_count": len(people)},
        "records": story_records,
        "participant_count": len(rows),
        "hard_participant_count": sum(row["hard_temporal_eligible"] for row in rows),
        "policy": "Only present/speaker/actor rows can enter hard social-temporal intersections; Mention-only rows remain contextual.",
    }


def event_by_id(inputs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["event_id"]): item for item in inputs["events"]}


def relation_event_id(scope_event: object, events: Mapping[str, Mapping[str, Any]]) -> str | None:
    value = str(scope_event or "")
    aliases = {
        "王敦之亂": "event-wang-dun-rebellion",
        "王敦之乱": "event-wang-dun-rebellion",
        "蘇峻之亂": "event-su-jun-rebellion",
        "蘇峻之乱": "event-su-jun-rebellion",
    }
    if value in aliases:
        return aliases[value]
    for event_id, event in events.items():
        if value and value in {str(event.get("canonical_name")), *[str(alias) for alias in event.get("aliases", [])]}:
            return event_id
    return None


def build_relation_contexts(inputs: Mapping[str, Any], facts: Mapping[str, list[dict[str, Any]]]) -> dict[str, Any]:
    events = event_by_id(inputs)
    offices_by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for office in facts["office_tenures"]:
        offices_by_person[str(office["person_id"])].append(office)
    published = set(inputs["story_by_id"])
    rows = []
    for relation in sorted(inputs["relations"], key=lambda item: str(item.get("id", ""))):
        relation_id = str(relation["id"])
        event_id = relation_event_id(relation.get("scope_event"), events) if relation.get("relation_scope") == "event_bounded" else None
        event = events.get(event_id) if event_id else None
        office_ids = []
        if relation.get("relation_scope") == "institutional_tenure":
            for office in offices_by_person.get(str(relation.get("object_id")), []):
                if str(office.get("office_title", "")).find("記室") >= 0 or str(office.get("normalized_office_label", "")).find("記室") >= 0:
                    office_ids.append(str(office.get("tenure_id")))
        source_story_ids = sorted(set(str(item) for item in [*relation.get("story_ids", []), *relation.get("source_entry_ids", [])] if str(item) in published))
        bounded = bool(event and event.get("start_year_ce") is not None and event.get("end_year_ce") is not None)
        precision = "event_bounded" if bounded else "unknown"
        role = "event_scoped_relation" if event_id else ("institutional_tenure" if office_ids else "unscoped_relation")
        evidence_ids = unique([*relation.get("evidence_ids", []), *(event.get("evidence_ids", []) if event else [])])
        rows.append(
            {
                "context_id": stable_id("h0b1-relation-context", relation_id),
                "relation_id": relation_id,
                "person_a_id": relation.get("subject_id"),
                "person_b_id": relation.get("object_id"),
                "temporal_role": role,
                "temporal_precision": precision,
                "start_year_ce": event.get("start_year_ce") if bounded else None,
                "end_year_ce": event.get("end_year_ce") if bounded else None,
                "office_tenure_ids": sorted(office_ids),
                "event_ids": [event_id] if event_id else [],
                "story_ids": source_story_ids,
                "evidence_ids": evidence_ids,
                "applicability_conditions": [
                    "only the relation-supported Story evidence activates this context",
                    "friendship/appreciation without a bounded source remains non-dating",
                ],
                "conflict_flags": [],
                "assertion_status": "inferred",
                "review_status": "candidate",
                "scope_status": "scoped" if bounded else "intentionally_unscoped",
                "notes": "Metadata attached to an existing Relation; this record is not a new Relation.",
            }
        )
    return {
        "schema": 1,
        "stage": "h0b1-relation-temporal-contexts",
        "generated_from": [str(RELATIONS_PATH), str(EVENTS_PATH), str(H0B0_FAMILY_PATHS["office_tenures"])],
        "relation_count": len(inputs["relations"]),
        "records": rows,
        "policy": "Relation temporal context is applicability metadata; it never creates or promotes a Relation.",
    }


def interval_from_record(record: Mapping[str, Any]) -> tuple[int, int] | None:
    start = record.get("start_year_ce")
    end = record.get("end_year_ce")
    if isinstance(start, int) and isinstance(end, int) and start <= end:
        return start, end
    return None


def intersect_intervals(intervals: Iterable[tuple[int, int]]) -> tuple[int, int] | None:
    """Intersect ordered inclusive year intervals without inventing a date."""

    values = list(intervals)
    if not values:
        return None
    start = max(value[0] for value in values)
    end = min(value[1] for value in values)
    return (start, end) if start <= end else None


def activated_office_constraint(
    office: Mapping[str, Any],
    participant: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Return a hard office constraint only for a reviewed, bounded fact.

    H0B-1 seed facts are intentionally candidates.  Their bounded intervals
    are still useful research candidates, but cannot date a Story until the
    fact itself has passed review.  This small gate is also used by focused
    tests with a reviewed synthetic copy of a fact.
    """

    if office.get("review_status") != "reviewed":
        return None
    interval = interval_from_record(office)
    if interval is None or participant.get("role") not in {"present", "speaker", "actor"}:
        return None
    return {
        "basis": "story_activated_office_tenure",
        "person_id": str(participant["person_id"]),
        "tenure_id": office.get("tenure_id"),
        "office_title": office.get("office_title"),
        "precision": office.get("temporal_precision", "unknown"),
        "start_year_ce": interval[0],
        "end_year_ce": interval[1],
        "event_ids": list(office.get("event_ids", [])),
        "activation_evidence_ids": unique([*participant.get("evidence_ids", []), *office.get("evidence_ids", [])]),
        "evidence_ids": unique([*participant.get("evidence_ids", []), *office.get("evidence_ids", [])]),
    }


def build_constraints(
    inputs: Mapping[str, Any],
    facts: Mapping[str, list[dict[str, Any]]],
    participants_document: Mapping[str, Any],
    relation_context_document: Mapping[str, Any],
) -> dict[str, Any]:
    anchors = {str(item["story_id"]): item for item in inputs["anchors"]}
    activity_by_story_person: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in inputs["activity"]:
        activity_by_story_person[(str(item.get("story_id")), str(item.get("person_id")))].append(item)
    events = event_by_id(inputs)
    participant_by_story = {str(item["story_id"]): item.get("participants", []) for item in participants_document["records"]}
    relation_contexts = relation_context_document["records"]
    constraints_by_story: list[dict[str, Any]] = []
    upgrade_queue: list[dict[str, Any]] = []

    for story in inputs["stories"]:
        story_id = str(story["id"])
        anchor = anchors.get(story_id, {})
        direct_constraints: list[dict[str, Any]] = []
        participant_constraints: list[dict[str, Any]] = []
        office_constraints: list[dict[str, Any]] = []
        candidate_office_constraints: list[dict[str, Any]] = []
        event_constraints: list[dict[str, Any]] = []
        relation_constraints: list[dict[str, Any]] = []
        marriage_constraints: list[dict[str, Any]] = []
        kinship_constraints: list[dict[str, Any]] = []

        anchor_interval = interval_from_record(anchor)
        anchor_precision = str(anchor.get("precision", "unknown"))
        if anchor:
            direct_constraints.append(
                {
                    "basis": "h0a_story_temporal_anchor",
                    "anchor_id": anchor.get("anchor_id"),
                    "precision": anchor_precision,
                    "start_year_ce": anchor.get("start_year_ce"),
                    "end_year_ce": anchor.get("end_year_ce"),
                    "phase_id": anchor.get("phase_id"),
                    "reign_id": anchor.get("reign_id"),
                    "event_ids": list(anchor.get("event_ids", [])),
                    "evidence_ids": unique(anchor.get("evidence_ids", [])),
                    "historical_assertion": True,
                }
            )
        for event_id in anchor.get("event_ids", []):
            event = events.get(str(event_id))
            if event is None:
                continue
            event_constraints.append(
                {
                    "basis": "h0a_event_anchor",
                    "event_id": event_id,
                    "precision": "event_bounded",
                    "start_year_ce": event.get("start_year_ce"),
                    "end_year_ce": event.get("end_year_ce"),
                    "evidence_ids": unique([*anchor.get("evidence_ids", []), *event.get("evidence_ids", [])]),
                }
            )

        hard_participants = [
            row for row in participant_by_story.get(story_id, []) if row.get("role") in {"present", "speaker", "actor"}
        ]
        for participant in hard_participants:
            person_id = str(participant["person_id"])
            for activity in activity_by_story_person.get((story_id, person_id), []):
                interval = interval_from_record(activity)
                if interval is None:
                    continue
                participant_constraints.append(
                    {
                        "basis": "person_activity_anchor",
                        "person_id": person_id,
                        "activity_anchor_id": activity.get("anchor_id"),
                        "precision": activity.get("precision", "unknown"),
                        "start_year_ce": interval[0],
                        "end_year_ce": interval[1],
                        "evidence_ids": unique([*participant.get("evidence_ids", []), *activity.get("evidence_ids", [])]),
                    }
                )

            for office in facts["office_tenures"]:
                if str(office.get("person_id")) != person_id:
                    continue
                interval = interval_from_record(office)
                if interval is None:
                    continue
                office_constraint = activated_office_constraint(office, participant)
                if office_constraint is not None:
                    office_constraints.append(office_constraint)
                else:
                    candidate_office_constraints.append(
                        {
                            "basis": "candidate_story_activated_office_tenure",
                            "person_id": person_id,
                            "tenure_id": office.get("tenure_id"),
                            "office_title": office.get("office_title"),
                            "precision": office.get("temporal_precision", "unknown"),
                            "start_year_ce": interval[0],
                            "end_year_ce": interval[1],
                            "activation_evidence_ids": unique([*participant.get("evidence_ids", []), *office.get("evidence_ids", [])]),
                            "evidence_ids": unique([*participant.get("evidence_ids", []), *office.get("evidence_ids", [])]),
                            "review_status": office.get("review_status"),
                            "hard_temporal_eligible": False,
                        }
                    )

        for context in relation_contexts:
            if story_id not in set(context.get("story_ids", [])):
                continue
            interval = interval_from_record(context)
            if interval is None:
                continue
            relation_constraints.append(
                {
                    "basis": "story_activated_relation_temporal_context",
                    "relation_id": context.get("relation_id"),
                    "context_id": context.get("context_id"),
                    "person_a_id": context.get("person_a_id"),
                    "person_b_id": context.get("person_b_id"),
                    "precision": context.get("temporal_precision"),
                    "start_year_ce": interval[0],
                    "end_year_ce": interval[1],
                    "event_ids": list(context.get("event_ids", [])),
                    "evidence_ids": list(context.get("evidence_ids", [])),
                }
            )

        all_intervals: list[tuple[str, tuple[int, int], dict[str, Any]]] = []
        for group_name, group in (
            ("direct", direct_constraints),
            ("participant", participant_constraints),
            ("office", office_constraints),
            ("event", event_constraints),
            ("relation", relation_constraints),
        ):
            for item in group:
                interval = interval_from_record(item)
                if interval is not None:
                    all_intervals.append((group_name, interval, item))

        conflict_flags: list[str] = []
        valid_intersection: dict[str, Any] | None = None
        if all_intervals:
            intersection = intersect_intervals(interval for _, interval, _ in all_intervals)
            if intersection is not None:
                start, end = intersection
                valid_intersection = {
                    "start_year_ce": start,
                    "end_year_ce": end,
                    "input_count": len(all_intervals),
                    "inputs": [
                        {
                            "group": group,
                            "start_year_ce": interval[0],
                            "end_year_ce": interval[1],
                            "basis": item.get("basis"),
                            "person_id": item.get("person_id"),
                            "anchor_id": item.get("anchor_id"),
                            "tenure_id": item.get("tenure_id"),
                            "context_id": item.get("context_id"),
                        }
                        for group, interval, item in all_intervals
                    ],
                }
            else:
                conflict_flags.append("temporal_conflict")

        hard_activity_count = len(participant_constraints)
        if conflict_flags:
            precision = "conflict"
            strongest_basis = "temporal_conflict"
        elif anchor_interval is not None and anchor_precision not in {"unknown", "phase_only"}:
            precision = anchor_precision
            strongest_basis = "h0a_story_temporal_anchor"
        elif office_constraints:
            precision = str(office_constraints[0].get("precision", "event_bounded"))
            strongest_basis = "story_activated_office_tenure"
        elif relation_constraints:
            precision = "event_bounded"
            strongest_basis = "story_activated_relation_temporal_context"
        elif event_constraints:
            precision = "event_bounded"
            strongest_basis = "h0a_event_anchor"
        elif hard_activity_count >= 2 and valid_intersection is not None:
            precision = "participant_overlap"
            strongest_basis = "participant_activity_intersection"
        elif hard_activity_count == 1 and valid_intersection is not None:
            precision = "participant_activity"
            strongest_basis = "participant_activity_anchor"
        elif anchor_precision == "phase_only":
            precision = "phase_only"
            strongest_basis = "historical_phase"
        else:
            precision = "unknown"
            strongest_basis = "no_safe_social_temporal_interval"

        h0a_upgrade_candidate = bool(
            anchor_precision == "unknown"
            and valid_intersection is not None
            and not conflict_flags
            and (office_constraints or relation_constraints or hard_activity_count >= 2)
        )
        rationale = None
        if h0a_upgrade_candidate:
            rationale = "H0B-1 has a non-conflicting candidate interval from Story-activated social evidence; H0A remains unchanged pending historical review."
            upgrade_queue.append(
                {
                    "upgrade_id": stable_id("h0b1-h0a-upgrade", story_id),
                    "story_id": story_id,
                    "old_precision": anchor_precision,
                    "proposed_precision": precision,
                    "proposed_start_year_ce": valid_intersection["start_year_ce"],
                    "proposed_end_year_ce": valid_intersection["end_year_ce"],
                    "constraint_basis": strongest_basis,
                    "supporting_person_ids": sorted({str(item.get("person_id")) for item in [*participant_constraints, *office_constraints] if item.get("person_id")}),
                    "supporting_tenure_ids": sorted({str(item.get("tenure_id")) for item in office_constraints if item.get("tenure_id")}),
                    "evidence_ids": unique([str(evidence_id) for group in (participant_constraints, office_constraints, relation_constraints, event_constraints) for item in group for evidence_id in item.get("evidence_ids", [])]),
                    "conflict_flags": [],
                    "review_status": "candidate",
                    "note": rationale,
                }
            )

        constraints_by_story.append(
            {
                "constraint_id": stable_id("h0b1-temporal", story_id),
                "story_id": story_id,
                "direct_constraints": direct_constraints,
                "participant_constraints": participant_constraints,
                "office_constraints": office_constraints,
                "candidate_office_constraints": candidate_office_constraints,
                "event_constraints": event_constraints,
                "relation_constraints": relation_constraints,
                "marriage_constraints": marriage_constraints,
                "kinship_constraints": kinship_constraints,
                "valid_intersection": valid_intersection,
                "candidate_start_year_ce": valid_intersection["start_year_ce"] if valid_intersection else None,
                "candidate_end_year_ce": valid_intersection["end_year_ce"] if valid_intersection else None,
                "constraint_precision": precision,
                "strongest_basis": strongest_basis,
                "supporting_person_ids": sorted({str(item.get("person_id")) for group in (participant_constraints, office_constraints) for item in group if item.get("person_id")} | {str(person_id) for item in relation_constraints for person_id in (item.get("person_a_id"), item.get("person_b_id")) if person_id}),
                "supporting_tenure_ids": sorted({str(item.get("tenure_id")) for item in office_constraints if item.get("tenure_id")}),
                "supporting_event_ids": unique([str(event_id) for group in (event_constraints, relation_constraints, office_constraints) for item in group for event_id in item.get("event_ids", [])]),
                "supporting_relation_context_ids": sorted({str(item.get("context_id")) for item in relation_constraints if item.get("context_id")}),
                "conflict_flags": conflict_flags,
                "suggested_era_card_id": story.get("primary_era_card_id") if valid_intersection else None,
                "h0a_upgrade_candidate": h0a_upgrade_candidate,
                "h0a_upgrade_reason": rationale,
                "h0a_precision": anchor_precision,
                "h0a_anchor_id": anchor.get("anchor_id"),
                "primary_era_card_id": story.get("primary_era_card_id"),
                "review_status": "candidate",
            }
        )

    return {
        "schema": 1,
        "stage": "h0b1-social-temporal-constraints",
        "scope": {"story_count": len(inputs["stories"]), "production_person_count": len(inputs["people"])},
        "policy": "H0B-1 is a conservative research projection. Off-frame, annotation-only, clan-only and friendship-only facts never harden Story time; H0A anchors are not rewritten.",
        "records": constraints_by_story,
        "h0a_upgrade_candidate_count": len(upgrade_queue),
    }, upgrade_queue


def build_activity_compatibility(inputs: Mapping[str, Any], facts: Mapping[str, list[dict[str, Any]]]) -> dict[str, Any]:
    h0a = inputs["activity"]
    by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in h0a:
        by_person[str(item.get("person_id"))].append(item)
    rows = []
    for office in facts["office_tenures"]:
        person_id = str(office["person_id"])
        interval = interval_from_record(office)
        matched = [item for item in by_person[person_id] if interval_from_record(item) == interval and interval is not None]
        if interval is None:
            state = "compatible"
            note = "Office fact has no absolute bound; it does not contradict an H0A activity anchor."
        elif matched:
            state = "compatible"
            note = "Office interval is compatible with an existing H0A activity interval."
        else:
            state = "candidate_extension"
            note = "Office interval is new H0B-1 evidence and is not copied into H0A automatically."
        rows.append(
            {
                "compatibility_id": stable_id("h0b1-activity-compatibility", office.get("tenure_id")),
                "person_id": person_id,
                "tenure_id": office.get("tenure_id"),
                "h0a_activity_anchor_ids": sorted({str(item.get("anchor_id")) for item in matched}),
                "state": state,
                "office_interval": {"start_year_ce": office.get("start_year_ce"), "end_year_ce": office.get("end_year_ce")},
                "evidence_ids": unique(office.get("evidence_ids", [])),
                "review_status": "candidate",
                "note": note,
            }
        )
    return {
        "schema": 1,
        "stage": "h0b1-person-activity-compatibility",
        "generated_from": [str(ACTIVITY_PATH), str(H0B0_FAMILY_PATHS["office_tenures"]), str(SEEDS_PATH)],
        "records": sorted(rows, key=lambda item: str(item["tenure_id"])),
        "state_counts": dict(sorted(Counter(str(item["state"]) for item in rows).items())),
        "h0a_rewritten": False,
    }


def build_reconciliation(inputs: Mapping[str, Any]) -> dict[str, Any]:
    classifications = {
        "h0b0-gap-001": ("still_blocked", "阮咸仍不是 production Person；W4 沒有 materialize bridge identity。"),
        "h0b0-gap-002": ("still_blocked", "庾會及諸葛氏婚姻端點仍不在 production scope。"),
        "h0b0-gap-003": ("still_blocked", "桓溫女與王坦之子婚姻端點未 materialize。"),
        "h0b0-gap-004": ("partially_resolved", "H0B-1 保留既有職官片段並新增少量 office candidate，但仍沒有完整任序。"),
        "h0b0-gap-005": ("still_blocked", "溫嶠只保留太原地域層級，支系未有新證據。"),
        "h0b0-gap-006": ("still_blocked", "諸葛恢之女不是 production Person，沒有猜配偶身份。"),
        "h0b0-gap-007": ("still_blocked", "王羲之其他子女沒有足夠端點身份，未因父子數量補造人物。"),
    }
    rows = []
    for gap in sorted(inputs["h0b0_gaps"], key=lambda item: str(item.get("gap_id", ""))):
        gap_id = str(gap["gap_id"])
        status, rationale = classifications.get(gap_id, ("still_blocked", "H0B-1 未取得足夠新證據。"))
        rows.append(
            {
                "reconciliation_id": stable_id("h0b1-reconcile", gap_id),
                "source_gap_id": gap_id,
                "classification": status,
                "affected_person_ids": sorted(gap.get("affected_person_ids", [])),
                "evidence_ids": unique(gap.get("evidence_ids", [])),
                "rationale": rationale,
                "future_relevance": gap.get("future_expansion_value"),
            }
        )
    return {
        "schema": 1,
        "stage": "h0b1-h0b0-gap-reconciliation",
        "generated_from": [str(H0B0_GAPS_PATH), str(H0B0_BACKBONE_PATH), str(SEEDS_PATH)],
        "h0b0_artifact_unchanged": True,
        "records": rows,
        "summary": dict(sorted(Counter(str(item["classification"]) for item in rows).items())),
    }


def build_gap_audit(
    inputs: Mapping[str, Any],
    facts: Mapping[str, list[dict[str, Any]]],
    participants_document: Mapping[str, Any],
    constraints_document: Mapping[str, Any],
    relation_context_document: Mapping[str, Any],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    # Frozen H0B-0 gaps are carried into a new audit as references, never edited.
    for gap in inputs["h0b0_gaps"]:
        source_category = str(gap.get("category"))
        rows.append(
            {
                "gap_id": stable_id("h0b1-gap", "h0b0", gap.get("gap_id")),
                "source_gap_id": gap.get("gap_id"),
                "category": LEGACY_GAP_CATEGORY_MAP.get(source_category, source_category),
                "source_category": source_category,
                "affected_person_ids": sorted(gap.get("affected_person_ids", [])),
                "affected_story_ids": [],
                "evidence_ids": unique(gap.get("evidence_ids", [])),
                "status": "carried_from_h0b0",
                "why_it_matters": gap.get("why_it_matters"),
                "future_relevance": gap.get("future_expansion_value"),
            }
        )
    for office in facts["office_tenures"]:
        if office.get("production_scope") != "h0b1-scale-up" or interval_from_record(office) is not None:
            continue
        rows.append(
            {
                "gap_id": stable_id("h0b1-gap", "office", office.get("tenure_id")),
                "category": "office_chronology_incomplete",
                "affected_person_ids": [str(office.get("person_id"))],
                "affected_story_ids": [],
                "evidence_ids": unique(office.get("evidence_ids", [])),
                "status": "open",
                "why_it_matters": f"{office.get('office_title')} is source-backed but has no absolute tenure bound.",
                "future_relevance": "temporal_orientation",
                "tenure_id": office.get("tenure_id"),
            }
        )
    for story in participants_document["records"]:
        contextual = [
            row for row in story.get("participants", []) if row.get("role") in {"referenced", "off_frame", "annotation_only", "uncertain"}
        ]
        if contextual:
            rows.append(
                {
                    "gap_id": stable_id("h0b1-gap", "participant-role", story.get("story_id")),
                    "category": "participant_role_uncertain",
                    "affected_person_ids": sorted({str(row.get("person_id")) for row in contextual}),
                    "affected_story_ids": [str(story.get("story_id"))],
                    "evidence_ids": unique([eid for row in contextual for eid in row.get("evidence_ids", [])]),
                    "status": "open",
                    "why_it_matters": "Resolved Mention exists, but no reviewed scene/action evidence safely promotes it to hard Story participation.",
                    "future_relevance": "historical_graph_sufficiency",
                    "contextual_record_count": len(contextual),
                }
            )
    for context in relation_context_document["records"]:
        if context.get("scope_status") == "intentionally_unscoped":
            rows.append(
                {
                    "gap_id": stable_id("h0b1-gap", "relation-scope", context.get("relation_id")),
                    "category": "relation_temporal_scope_missing",
                    "affected_person_ids": sorted({str(context.get("person_a_id")), str(context.get("person_b_id"))}),
                    "affected_story_ids": list(context.get("story_ids", [])),
                    "evidence_ids": unique(context.get("evidence_ids", [])),
                    "status": "open",
                    "why_it_matters": "Existing Relation is semantically valid but not chronologically bounded by local evidence.",
                    "future_relevance": "temporal_orientation",
                    "relation_id": context.get("relation_id"),
                }
            )
    for constraint in constraints_document["records"]:
        if constraint.get("conflict_flags"):
            rows.append(
                {
                    "gap_id": stable_id("h0b1-gap", "temporal-conflict", constraint.get("story_id")),
                    "category": "temporal_conflict",
                    "affected_person_ids": list(constraint.get("supporting_person_ids", [])),
                    "affected_story_ids": [str(constraint.get("story_id"))],
                    "evidence_ids": unique([
                        eid
                        for group in (constraint.get("direct_constraints", []), constraint.get("participant_constraints", []), constraint.get("office_constraints", []), constraint.get("event_constraints", []), constraint.get("relation_constraints", []))
                        for item in group
                        for eid in item.get("evidence_ids", [])
                    ]),
                    "status": "open",
                    "why_it_matters": "Competing intervals have empty intersection; no date was selected.",
                    "future_relevance": "historical_graph_sufficiency",
                    "conflict_flags": list(constraint.get("conflict_flags", [])),
                }
            )
    return {
        "schema": 1,
        "stage": "h0b1-social-structural-gap-audit",
        "generated_from": [str(H0B0_GAPS_PATH), str(SEEDS_PATH), str(OUTPUTS["participants"]), str(OUTPUTS["constraints"])],
        "scope": {"production_person_count": len(inputs["people"]), "production_story_count": len(inputs["stories"])},
        "summary": {
            "gap_count": len(rows),
            "by_category": {
                category: sum(str(item["category"]) == category for item in rows)
                for category in GAP_CATEGORIES
            },
            "additional_categories": {
                category: count
                for category, count in sorted(Counter(str(item["category"]) for item in rows).items())
                if category not in GAP_CATEGORIES
            },
        },
        "category_catalog": list(GAP_CATEGORIES),
        "records": sorted(rows, key=lambda item: str(item["gap_id"])),
        "notes": "Open gaps are preserved as research state; no missing endpoint is materialized into production.",
    }


def build_person_coverage(
    inputs: Mapping[str, Any],
    facts: Mapping[str, list[dict[str, Any]]],
    participants_document: Mapping[str, Any],
    constraints_document: Mapping[str, Any],
    relation_context_document: Mapping[str, Any],
    gaps_document: Mapping[str, Any],
) -> dict[str, Any]:
    links = records(inputs["person_story"], "links", "records")
    story_by_person: dict[str, set[str]] = defaultdict(set)
    for link in links:
        person_id = link.get("person_id")
        story_id = link.get("entry_id", link.get("story_id"))
        if isinstance(person_id, str) and isinstance(story_id, str) and story_id in inputs["story_by_id"]:
            story_by_person[person_id].add(story_id)
    main_text_story_by_person: dict[str, set[str]] = defaultdict(set)
    annotation_story_by_person: dict[str, set[str]] = defaultdict(set)
    for mention in [
        *records(inputs["mentions"], "mentions"),
        *records(inputs["mentions"], "derived_mentions"),
    ]:
        person_id = mention.get("person_id")
        story_id = mention.get("source_id", mention.get("story_id", mention.get("entry_id")))
        if not isinstance(person_id, str) or person_id not in inputs["people_by_id"] or story_id not in inputs["story_by_id"]:
            continue
        target = main_text_story_by_person if mention.get("section") == "main_text" else annotation_story_by_person
        target[person_id].add(str(story_id))
    hard_by_person: dict[str, set[str]] = defaultdict(set)
    constraints_by_person: Counter[str] = Counter()
    for story in participants_document["records"]:
        for row in story.get("participants", []):
            if row.get("hard_temporal_eligible"):
                hard_by_person[str(row["person_id"])].add(str(story["story_id"]))
    for constraint in constraints_document["records"]:
        for person_id in constraint.get("supporting_person_ids", []):
            if constraint.get("valid_intersection"):
                constraints_by_person[str(person_id)] += 1
    activity_by_person: Counter[str] = Counter(str(row.get("person_id")) for row in inputs["activity"] if row.get("person_id"))
    temporal_evidence_by_person: Counter[str] = Counter()
    for constraint in constraints_document["records"]:
        if not constraint.get("valid_intersection"):
            continue
        for person_id in constraint.get("supporting_person_ids", []):
            temporal_evidence_by_person[str(person_id)] += 1
    relation_by_person: Counter[str] = Counter()
    for context in relation_context_document["records"]:
        for person_id in (context.get("person_a_id"), context.get("person_b_id")):
            if person_id:
                relation_by_person[str(person_id)] += 1

    family_counts: dict[str, Counter[str]] = defaultdict(Counter)
    family_neighbor: dict[str, set[str]] = defaultdict(set)
    for family, key_a, key_b in (
        ("clan_memberships", "person_id", "clan_id"),
        ("kinship", "person_a_id", "person_b_id"),
        ("marriages", "spouse_a_id", "spouse_b_id"),
        ("office_tenures", "person_id", "tenure_id"),
    ):
        for row in facts[family]:
            a = str(row.get(key_a))
            family_counts[a][family] += 1
            if family in {"kinship", "marriages"}:
                b = str(row.get(key_b))
                family_counts[b][family] += 1
                family_neighbor[a].add(b)
                family_neighbor[b].add(a)
    gap_by_person: Counter[str] = Counter()
    conflict_by_person: Counter[str] = Counter()
    for gap in gaps_document["records"]:
        for person_id in gap.get("affected_person_ids", []):
            gap_by_person[str(person_id)] += 1
        if gap.get("category") in {"source_conflict", "temporal_conflict", "identity_compatibility_gap"}:
            for person_id in gap.get("affected_person_ids", []):
                conflict_by_person[str(person_id)] += 1

    rows = []
    for person_id in sorted(inputs["people_by_id"]):
        person = inputs["people_by_id"][person_id]
        fact_counts = family_counts[person_id]
        rows.append(
            {
                "person_id": person_id,
                "canonical_name": person.get("canonical_name"),
                "story_count": len(story_by_person[person_id]),
                "main_text_story_count": len(main_text_story_by_person[person_id]),
                "annotation_story_count": len(annotation_story_by_person[person_id]),
                "secure_participant_story_count": len(hard_by_person[person_id]),
                "temporal_constraint_story_count": constraints_by_person[person_id],
                "temporal_evidence_count": temporal_evidence_by_person[person_id],
                "person_activity_anchor_count": activity_by_person[person_id],
                "clan_evidence_count": fact_counts["clan_memberships"],
                "kinship_evidence_count": fact_counts["kinship"],
                "marriage_evidence_count": fact_counts["marriages"],
                "office_evidence_count": fact_counts["office_tenures"],
                "event_evidence_count": sum(1 for row in constraints_document["records"] if person_id in row.get("supporting_person_ids", []) and row.get("supporting_event_ids")),
                "relation_evidence_count": relation_by_person[person_id],
                "existing_h0b_fact_count": sum(1 for family in facts.values() for row in family if row.get("production_scope") != "h0b1-scale-up" and person_id in {str(row.get("person_id")), str(row.get("person_a_id")), str(row.get("person_b_id")), str(row.get("spouse_a_id")), str(row.get("spouse_b_id"))}),
                "new_h0b1_fact_count": sum(1 for family in facts.values() for row in family if row.get("production_scope") == "h0b1-scale-up" and person_id in {str(row.get("person_id")), str(row.get("person_a_id")), str(row.get("person_b_id")), str(row.get("spouse_a_id")), str(row.get("spouse_b_id"))}),
                "structural_neighbor_person_ids": sorted(family_neighbor[person_id]),
                "structural_connectivity": len(family_neighbor[person_id]),
                "unresolved_endpoint_count": gap_by_person[person_id],
                "conflict_count": conflict_by_person[person_id],
            }
        )
    return {
        "schema": 1,
        "stage": "h0b1-person-structural-coverage",
        "generated_from": [str(PEOPLE_PATH), str(PERSON_STORY_PATH), str(OUTPUTS["participants"]), str(OUTPUTS["backbone"]), str(OUTPUTS["gap_audit"])],
        "scope": {"production_person_count": len(rows), "production_story_count": len(inputs["stories"])},
        "records": rows,
    }


def build_p4_readiness(inputs: Mapping[str, Any], facts: Mapping[str, list[dict[str, Any]]]) -> dict[str, Any]:
    memberships = facts["clan_memberships"]
    by_clan: dict[str, set[str]] = defaultdict(set)
    for row in memberships:
        by_clan[str(row["clan_id"])].add(str(row["person_id"]))
    links = records(inputs["person_story"], "links", "records")
    stories_by_person: dict[str, set[str]] = defaultdict(set)
    for link in links:
        if link.get("entry_id") in inputs["story_by_id"]:
            stories_by_person[str(link.get("person_id"))].add(str(link.get("entry_id")))
    kin = facts["kinship"]
    mar = facts["marriages"]
    rows = []
    for clan in facts["clans"]:
        clan_id = str(clan["clan_id"])
        person_ids = sorted(by_clan[clan_id])
        kin_ids = [row.get("kinship_id", row.get("id")) for row in kin if str(row.get("person_a_id")) in person_ids or str(row.get("person_b_id")) in person_ids]
        marriage_ids = [row.get("marriage_id", row.get("id")) for row in mar if str(row.get("spouse_a_id")) in person_ids or str(row.get("spouse_b_id")) in person_ids]
        rows.append(
            {
                "cluster_id": stable_id("h0b1-p4-cluster", clan_id),
                "clan_id": clan_id,
                "canonical_name": clan.get("canonical_name"),
                "production_person_ids": person_ids,
                "story_ids": sorted({story_id for person_id in person_ids for story_id in stories_by_person[person_id]}),
                "kinship_ids": sorted(set(str(value) for value in kin_ids)),
                "marriage_ids": sorted(set(str(value) for value in marriage_ids)),
                "evidence_ids": unique(clan.get("evidence_ids", [])),
                "evidence_completeness": "partial" if person_ids else "gap",
                "p4_status": "candidate_cluster",
            }
        )
    return {
        "schema": 1,
        "stage": "h0b1-p4-readiness",
        "generated_from": [str(OUTPUTS["backbone"]), str(PERSON_STORY_PATH)],
        "records": rows,
        "notes": "Planning projection only; no family UI or Person expansion is materialized.",
    }


def build_es0_readiness(inputs: Mapping[str, Any], constraints_document: Mapping[str, Any], participants_document: Mapping[str, Any], facts: Mapping[str, list[dict[str, Any]]]) -> dict[str, Any]:
    by_card: dict[str, dict[str, Any]] = defaultdict(lambda: {"story_ids": set(), "person_ids": set(), "event_ids": set(), "fact_count": 0, "constraint_precisions": Counter()})
    stories_by_id = {str(story["id"]): story for story in inputs["stories"]}
    participants_by_story = {str(row["story_id"]): row for row in participants_document["records"]}
    constraints_by_story = {str(row["story_id"]): row for row in constraints_document["records"]}
    for story_id, story in stories_by_id.items():
        card_id = str(story.get("primary_era_card_id"))
        item = by_card[card_id]
        item["story_ids"].add(story_id)
        item["person_ids"].update(row["person_id"] for row in participants_by_story.get(story_id, {}).get("participants", []) if row.get("hard_temporal_eligible"))
        item["event_ids"].update(constraints_by_story.get(story_id, {}).get("supporting_event_ids", []))
        item["constraint_precisions"][str(constraints_by_story.get(story_id, {}).get("constraint_precision", "unknown"))] += 1
    for family in ("kinship", "marriages", "office_tenures", "clan_memberships"):
        for row in facts[family]:
            people = {str(row.get("person_id")), str(row.get("person_a_id")), str(row.get("person_b_id")), str(row.get("spouse_a_id")), str(row.get("spouse_b_id"))}
            for item in by_card.values():
                if people & item["person_ids"]:
                    item["fact_count"] += 1
    rows = []
    for card_id in sorted(by_card):
        item = by_card[card_id]
        rows.append(
            {
                "era_card_id": card_id,
                "story_count": len(item["story_ids"]),
                "hard_participant_person_ids": sorted(item["person_ids"]),
                "historical_event_ids": sorted(item["event_ids"]),
                "social_fact_count": item["fact_count"],
                "temporal_confidence_distribution": dict(sorted(item["constraint_precisions"].items())),
                "es0_status": "candidate_window",
            }
        )
    return {
        "schema": 1,
        "stage": "h0b1-es0-readiness",
        "generated_from": [str(ERA_ORIENTATION_PATH), str(OUTPUTS["participants"]), str(OUTPUTS["constraints"]), str(OUTPUTS["backbone"])],
        "records": rows,
        "notes": "Planning projection only; no Era slice UI or timeline is materialized.",
    }


def build_metrics(
    inputs: Mapping[str, Any],
    facts: Mapping[str, list[dict[str, Any]]],
    participants_document: Mapping[str, Any],
    relation_context_document: Mapping[str, Any],
    constraints_document: Mapping[str, Any],
    upgrade_queue: list[dict[str, Any]],
    gaps_document: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
    person_coverage: Mapping[str, Any],
) -> dict[str, Any]:
    protected = inputs["sc1"]
    story_ids = set(inputs["story_by_id"])
    before_orient = Counter(str(item.get("orientation_precision", "unknown")) for item in inputs["orientations"])
    after_orient = before_orient.copy()
    office_precision = Counter(str(item.get("temporal_precision", "unknown")) for item in facts["office_tenures"])
    useful_offices = sum(1 for item in facts["office_tenures"] if interval_from_record(item) is not None)
    constraints = constraints_document["records"]
    direct = sum(bool(item.get("direct_constraints")) for item in constraints)
    participant = sum(bool(item.get("participant_constraints")) for item in constraints)
    office = sum(bool(item.get("office_constraints")) for item in constraints)
    event = sum(bool(item.get("event_constraints")) for item in constraints)
    relation = sum(bool(item.get("relation_constraints")) for item in constraints)
    intersections = sum(item.get("valid_intersection") is not None for item in constraints)
    conflicts = sum(bool(item.get("conflict_flags")) for item in constraints)
    family_people = {
        "clan_memberships": len({str(row.get("person_id")) for row in facts["clan_memberships"] if row.get("person_id")}),
        "kinship": len({person_id for row in facts["kinship"] for person_id in (row.get("person_a_id"), row.get("person_b_id")) if person_id}),
        "marriages": len({person_id for row in facts["marriages"] for person_id in (row.get("spouse_a_id"), row.get("spouse_b_id")) if person_id}),
        "office_tenures": len({str(row.get("person_id")) for row in facts["office_tenures"] if row.get("person_id")}),
    }
    metrics = {
        "schema": 1,
        "stage": "h0b1-metrics",
        "scope": {"persons_audited": len(inputs["people"]), "stories_audited": len(story_ids)},
        "participation": {
            "story_count_with_any_projection": sum(bool(row.get("participants")) for row in participants_document["records"]),
            "secure_participant_record_count": participants_document["hard_participant_count"],
            "referenced_record_count": sum(sum(item.get("role") == "referenced" for item in row.get("participants", [])) for row in participants_document["records"]),
            "off_frame_record_count": sum(sum(item.get("role") == "off_frame" for item in row.get("participants", [])) for row in participants_document["records"]),
            "annotation_only_record_count": sum(sum(item.get("role") == "annotation_only" for item in row.get("participants", [])) for row in participants_document["records"]),
            "uncertain_record_count": sum(sum(item.get("role") == "uncertain" for item in row.get("participants", [])) for row in participants_document["records"]),
        },
        "social": {
            "clan_count": len(facts["clans"]),
            "clan_membership_count": len(facts["clan_memberships"]),
            "kinship_direct_count": sum(row.get("relation_basis") == "direct" for row in facts["kinship"]),
            "kinship_derived_count": sum(row.get("relation_basis") == "derived" for row in facts["kinship"]),
            "marriage_union_count": len(facts["marriages"]),
            "office_tenure_count": len(facts["office_tenures"]),
            "persons_with_fact_type": family_people,
                "persons_with_no_structural_facts": sum(
                not any(record.get(key, 0) for key in ("clan_evidence_count", "kinship_evidence_count", "marriage_evidence_count", "office_evidence_count"))
                for record in person_coverage["records"]
            ),
        },
        "office_temporal": {
            "precision_distribution": dict(sorted(office_precision.items())),
            "useful_temporally_bounded_office_count": useful_offices,
        },
        "story_temporal": {
            "stories_with_direct_constraints": direct,
            "stories_with_participant_constraints": participant,
            "stories_with_office_constraints": office,
            "stories_with_event_constraints": event,
            "stories_with_relation_constraints": relation,
            "successful_interval_intersections": intersections,
            "temporal_conflict_count": conflicts,
            "h0a_upgrade_candidate_count": len(upgrade_queue),
        },
        "era_orientation": {
            "before": dict(sorted(before_orient.items())),
            "after": dict(sorted(after_orient.items())),
            "changed_story_ids": [],
            "coverage": len(inputs["orientations"]),
        },
        "h0a": {"changed_anchor_count": 0, "upgrade_candidate_count": len(upgrade_queue), "anchor_layer_rewritten": False},
        "relations": {
            "reviewed_relation_count": len(inputs["relations"]),
            "temporally_scoped_relation_count": sum(row.get("scope_status") == "scoped" for row in relation_context_document["records"]),
            "intentionally_unscoped_relation_count": sum(row.get("scope_status") == "intentionally_unscoped" for row in relation_context_document["records"]),
        },
        "gaps": {
            "by_category": {
                category: sum(str(row["category"]) == category for row in gaps_document["records"])
                for category in GAP_CATEGORIES
            },
            "additional_categories": gaps_document["summary"].get("additional_categories", {}),
            "open_count": sum(row.get("status") == "open" for row in gaps_document["records"]),
        },
        "h0b0_gap_reconciliation": reconciliation["summary"],
        "protected_baseline": {
            "production_person_count": len(protected.get("people", [])),
            "production_story_count": len(protected.get("stories", [])),
            "person_story_link_count": len(records(inputs["person_story"], "links", "records")),
            "reviewed_person_story_link_count": int(inputs["person_story"].get("reviewed_link_count", 0)),
            "random_person_eligible_count": inputs["w4_metrics"].get("network", {}).get("random_person_eligible_after", 69),
            "reviewed_relation_count": len(protected.get("relations", [])),
            "scene_context_count": len(protected.get("scene_contexts", {})),
            "orphan_mention_count": 0,
            "primary_era_orientation_count": len(protected.get("story_era_orientations", [])),
        },
        "invariants": {
            "new_production_person_count": 0,
            "new_production_story_count": 0,
            "new_reviewed_relation_count": 0,
            "h0b0_frozen": True,
            "h0a_rewritten": False,
            "canonical_sources_changed": False,
        },
        "artifact_hashes": {},
        "seed_sha256": sha256_file(SEEDS_PATH),
    }
    return metrics


def build_outputs(inputs: Mapping[str, Any]) -> dict[str, Any]:
    facts = build_facts(inputs)
    generated_from = [str(PEOPLE_PATH), str(EVIDENCE_PATH), str(SC1_PATH), str(SEEDS_PATH), str(H0B0_BACKBONE_PATH)]
    evidence_by_id = inputs["evidence_by_id"]
    for family, path in OUTPUTS.items():
        if family not in {"clans", "clan_memberships", "kinship", "marriages", "office_tenures"}:
            continue
        id_key = {"clans": "clan_id", "clan_memberships": "membership_id", "kinship": "kinship_id", "marriages": "marriage_id", "office_tenures": "tenure_id"}[family]
        new_key = {"clans": "new_clans", "clan_memberships": "new_clan_memberships", "kinship": "new_kinship", "marriages": "new_marriages", "office_tenures": "new_office_tenures"}[family]
        rows = [decorate_new(item, id_key, evidence_by_id) for item in inputs["seeds"][new_key]]
        write_json(path, family_document(f"h0b1-{family}", rows, generated_from + [str(SEEDS_PATH)]))

    participants = build_participants(inputs)
    relation_contexts = build_relation_contexts(inputs, facts)
    constraints, upgrade_queue = build_constraints(inputs, facts, participants, relation_contexts)
    activity_compatibility = build_activity_compatibility(inputs, facts)
    reconciliation = build_reconciliation(inputs)
    gaps = build_gap_audit(inputs, facts, participants, constraints, relation_contexts)
    person_coverage = build_person_coverage(inputs, facts, participants, constraints, relation_contexts, gaps)
    p4 = build_p4_readiness(inputs, facts)
    es0 = build_es0_readiness(inputs, constraints, participants, facts)

    h0b0_imports = {
        family: [str(row.get({"clans": "clan_id", "clan_memberships": "membership_id", "kinship": "kinship_id", "marriages": "marriage_id", "office_tenures": "tenure_id"}[family], row.get("id"))) for row in facts[family] if row.get("production_scope") != "h0b1-scale-up"]
        for family in ("clans", "clan_memberships", "kinship", "marriages", "office_tenures")
    }
    backbone = {
        "schema": 1,
        "stage": "h0b1-social-temporal-backbone",
        "generated_from": generated_from + [str(H0B0_FAMILY_PATHS["clans"]), str(OUTPUTS["participants"]), str(OUTPUTS["constraints"])],
        "production_person_ids": sorted(inputs["people_by_id"]),
        "h0b0_imports": h0b0_imports,
        "new_h0b1_fact_ids": {
            family: [str(row.get({"clans": "clan_id", "clan_memberships": "membership_id", "kinship": "kinship_id", "marriages": "marriage_id", "office_tenures": "tenure_id"}[family], row.get("id"))) for row in facts[family] if row.get("production_scope") == "h0b1-scale-up"]
            for family in ("clans", "clan_memberships", "kinship", "marriages", "office_tenures")
        },
        "clans": facts["clans"],
        "clan_memberships": facts["clan_memberships"],
        "kinship": facts["kinship"],
        "marriages": facts["marriages"],
        "office_tenures": facts["office_tenures"],
        "policy": inputs["seeds"].get("policy", {}),
        "counts": {
            "production_person_count": len(inputs["people"]),
            "clan_count": len(facts["clans"]),
            "clan_membership_count": len(facts["clan_memberships"]),
            "kinship_direct_count": sum(row.get("relation_basis") == "direct" for row in facts["kinship"]),
            "kinship_derived_count": sum(row.get("relation_basis") == "derived" for row in facts["kinship"]),
            "marriage_union_count": len(facts["marriages"]),
            "office_tenure_count": len(facts["office_tenures"]),
            "new_h0b1_fact_count": sum(row.get("production_scope") == "h0b1-scale-up" for family in facts.values() for row in family),
            "existing_reviewed_relation_count": len(inputs["relations"]),
        },
    }
    write_json(OUTPUTS["participants"], participants)
    write_json(OUTPUTS["relation_contexts"], relation_contexts)
    write_json(OUTPUTS["constraints"], constraints)
    write_json(OUTPUTS["activity_compatibility"], activity_compatibility)
    write_json(OUTPUTS["upgrade_queue"], {"schema": 1, "stage": "h0b1-h0a-upgrade-queue", "records": upgrade_queue, "count": len(upgrade_queue), "h0a_rewritten": False})
    write_json(OUTPUTS["backbone"], backbone)
    write_json(OUTPUTS["gap_audit"], gaps)
    write_json(OUTPUTS["reconciliation"], reconciliation)
    write_json(OUTPUTS["person_coverage"], person_coverage)
    write_json(OUTPUTS["p4_readiness"], p4)
    write_json(OUTPUTS["es0_readiness"], es0)

    metrics = build_metrics(inputs, facts, participants, relation_contexts, constraints, upgrade_queue, gaps, reconciliation, person_coverage)
    write_json(OUTPUTS["metrics"], metrics)
    metrics["artifact_hashes"] = {key: sha256_file(path) for key, path in OUTPUTS.items() if key != "metrics"}
    metrics["frozen_h0b0_hashes"] = {family: sha256_file(path) for family, path in H0B0_FAMILY_PATHS.items()}
    metrics["frozen_h0b0_hashes"].update(
        {
            "social_backbone": sha256_file(H0B0_BACKBONE_PATH),
            "structural_gap_audit": sha256_file(H0B0_GAPS_PATH),
            "metrics": sha256_file(H0B0_METRICS_PATH),
        }
    )
    metrics["h0a_anchor_sha256"] = sha256_file(ANCHORS_PATH)
    write_json(OUTPUTS["metrics"], metrics)
    return {
        "facts": facts,
        "backbone": backbone,
        "participants": participants,
        "relation_contexts": relation_contexts,
        "constraints": constraints,
        "upgrade_queue": upgrade_queue,
        "gaps": gaps,
        "reconciliation": reconciliation,
        "person_coverage": person_coverage,
        "metrics": metrics,
    }


def main() -> int:
    inputs = load_inputs()
    output = build_outputs(inputs)
    metrics = output["metrics"]
    print(
        "H0B-1 social-temporal backbone: "
        f"{metrics['scope']['persons_audited']} Persons, "
        f"{metrics['scope']['stories_audited']} Stories, "
        f"{metrics['social']['clan_membership_count']} memberships, "
        f"{metrics['social']['kinship_direct_count']} direct kinship facts, "
        f"{metrics['social']['marriage_union_count']} marriages, "
        f"{metrics['social']['office_tenure_count']} OfficeTenures, "
        f"{metrics['story_temporal']['h0a_upgrade_candidate_count']} H0A upgrade candidates"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
