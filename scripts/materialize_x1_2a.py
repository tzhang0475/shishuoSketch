#!/usr/bin/env python3
"""Materialize only accepted X1.2A facts into a protected extension layer.

This builder intentionally does not edit H0C/HG0 inputs, the global identity
index, SC1, PersonStory, or canonical source files.  The extension is the
controlled canonical result of the X1.2A review and is ready for a later
explicit corpus/graph migration, but is not silently projected into those
protected layers.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Mapping

try:
    from scripts.x1_2a_common import (
        CANONICAL_FACTS_PATH,
        EPOCH,
        MATERIALIZATION_PATH,
        REVIEW_MANIFEST_PATH,
        evidence_by_id,
        evidence_ref,
        load_x1_1,
        protected_hashes,
        read,
        sha256_file,
        stable_id,
        unique,
        write,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from x1_2a_common import (
        CANONICAL_FACTS_PATH,
        EPOCH,
        MATERIALIZATION_PATH,
        REVIEW_MANIFEST_PATH,
        evidence_by_id,
        evidence_ref,
        load_x1_1,
        protected_hashes,
        read,
        sha256_file,
        stable_id,
        unique,
        write,
    )


EXISTING_EIGHT_PRINCES = "event-eight-princes-disturbance"
OFFICE_ID = "office-x1-2a-jingzhou-zhizhong"
LOCATION_ID = "location-x1-2a-jingzhou"
NEW_EVENT_ID = "event-x1-2a-qi-wannian-rebellion"
OFFICE_TENURE_ID = "x1-2a-office-tenure-061-jingzhou-zhizhong"
LOCATION_FACT_ID = "x1-2a-location-fact-061-jingzhou-zhizhong"


def accepted_rows(manifest: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(row["story_id"]), str(row["fact_layer"])): dict(row)
        for row in manifest.get("fact_reviews", [])
        if row.get("review_status") == "accepted"
    }


def fact_record(
    *,
    fact_id: str,
    fact_type: str,
    subject_ids: list[str],
    story_ids: list[str],
    evidence_ids: list[str],
    review_row: Mapping[str, Any],
    temporal_precision: str | None = None,
    location_ids: list[str] | None = None,
    derived_from: list[str] | None = None,
    **fields: Any,
) -> dict[str, Any]:
    return {
        "fact_key": f"{fact_type}:{fact_id}",
        "fact_type": fact_type,
        "fact_id": fact_id,
        "subject_ids": sorted(subject_ids),
        "story_ids": sorted(story_ids),
        "evidence_ids": sorted(unique(evidence_ids)),
        "evidence_refs": [
            evidence_ref(evidence_id, evidence_by_id())
            for evidence_id in sorted(unique(evidence_ids))
        ],
        "provenance_refs": [
            {
                "review_item_id": review_row["review_item_id"],
                "source_candidate_id": review_row["source_candidate_id"],
                "selection_mode": review_row.get("selection_mode"),
                "selection_epoch": "X1.1",
                "source_graph_version": "HG0",
                "source_ml_version": "ML0",
            }
        ],
        "review_status": "reviewed",
        "assertion_status": "attested",
        "source_path": str(CANONICAL_FACTS_PATH),
        "temporal_precision": temporal_precision,
        "location_ids": sorted(location_ids or []),
        "derived_from": sorted(derived_from or []),
        "materialization_epoch": EPOCH,
        "canonical_scope": "x1-2a-canonical-extension",
        **fields,
    }


def build() -> dict[str, Any]:
    load_x1_1()
    review_manifest = read(REVIEW_MANIFEST_PATH)
    review_hash = sha256_file(REVIEW_MANIFEST_PATH)
    accepted = accepted_rows(review_manifest)
    evidence = evidence_by_id()
    facts: list[dict[str, Any]] = []
    entities: list[dict[str, Any]] = []

    office_review = accepted.get(("04-wenxue-080", "office"))
    geographic_review = accepted.get(("04-wenxue-080", "geographic"))
    if office_review is None or geographic_review is None:
        raise ValueError("the reviewed 習鑿齒 office/location pair is incomplete")
    office_evidence = [
        "evidence-p3b-wave-2-48b6e2e48b0072a0876d9311",
        "evidence-w4-person-bebfe77e427a80bf99c74122",
    ]
    if any(item not in evidence for item in office_evidence):
        raise ValueError("office extension evidence is missing")
    entities.append({
        "entity_type": "Office",
        "entity_id": OFFICE_ID,
        "semantic_key": "office|荊州治中",
        "canonical_name": "荊州治中",
        "aliases": ["荊州治中", "荆州治中"],
        "institutional_context": {"polity": None, "jurisdiction": "荊州"},
        "evidence_ids": office_evidence,
        "review_status": "reviewed",
        "assertion_status": "attested",
        "materialization_epoch": EPOCH,
        "canonical_scope": "x1-2a-canonical-extension",
    })
    entities.append({
        "entity_type": "Location",
        "entity_id": LOCATION_ID,
        "semantic_key": "location|荊州",
        "canonical_name": "荊州",
        "aliases": ["荊州", "荆州"],
        "location_type": "historical_jurisdiction",
        "historical_parent": None,
        "modern_mapping": {"status": "unknown", "latitude": None, "longitude": None, "precision": "unknown"},
        "evidence_ids": office_evidence,
        "review_status": "reviewed",
        "assertion_status": "attested",
        "materialization_epoch": EPOCH,
        "canonical_scope": "x1-2a-canonical-extension",
    })
    facts.append(fact_record(
        fact_id=OFFICE_TENURE_ID,
        fact_type="office_tenure",
        subject_ids=[OFFICE_ID, "person-061"],
        story_ids=["04-wenxue-080"],
        evidence_ids=office_evidence,
        review_row=office_review,
        temporal_precision="unknown",
        location_ids=[LOCATION_ID],
        office_id=OFFICE_ID,
        person_id="person-061",
        office_title="荊州治中",
        normalized_office_label="荊州治中",
        polity=None,
        jurisdiction="荊州",
        start_year_ce=None,
        end_year_ce=None,
        lower_bound_year_ce=None,
        upper_bound_year_ce=None,
        temporal_basis="source states office, not tenure dates",
    ))
    facts.append(fact_record(
        fact_id=LOCATION_FACT_ID,
        fact_type="location_fact",
        subject_ids=[LOCATION_ID, "person-061"],
        story_ids=["04-wenxue-080"],
        evidence_ids=office_evidence,
        review_row=geographic_review,
        temporal_precision="unknown",
        location_ids=[LOCATION_ID],
        location_id=LOCATION_ID,
        subject_type="person",
        subject_id="person-061",
        location_role="held_office_at",
        office_id=OFFICE_ID,
        office_tenure_id=OFFICE_TENURE_ID,
        precision="historical_jurisdiction_only",
    ))

    service_review = accepted.get(("23-rendan-032", "service_political"))
    if service_review is None:
        raise ValueError("the reviewed 王公 service fact is missing")
    service_evidence = [
        "evidence-p3b-wave-2-a82e4222963c8621e77a1e76",
        "evidence-p3b-wave-2-8905044d2d0aeb0f37ec0606",
    ]
    for person_id, surface in (("person-014", "王長史"), ("person-018", "謝仁祖")):
        fact_id = f"x1-2a-service-under-{person_id}-person-003"
        facts.append(fact_record(
            fact_id=fact_id,
            fact_type="service_political",
            subject_ids=[person_id, "person-003"],
            story_ids=["23-rendan-032"],
            evidence_ids=service_evidence,
            review_row=service_review,
            temporal_precision="unknown",
            service_type="served_under",
            relation_type="institutional",
            subject_person_id=person_id,
            superior_person_id="person-003",
            subject_surface=surface,
            superior_surface="王公",
            applicability_conditions=["direct same-Story 掾 wording", "local Liu identification of 王公 as 王導"],
            relation_materialized=False,
        ))

    def event_context(
        story_id: str,
        review_row: Mapping[str, Any],
        event_id: str,
        evidence_ids: list[str],
        relation_to_story: str,
        temporal_precision: str | None,
    ) -> None:
        facts.append(fact_record(
            fact_id=f"x1-2a-event-context-{story_id}-{event_id}",
            fact_type="event_story_context",
            subject_ids=[story_id, event_id],
            story_ids=[story_id],
            evidence_ids=evidence_ids,
            review_row=review_row,
            temporal_precision=temporal_precision,
            event_id=event_id,
            story_id=story_id,
            relation_to_story=relation_to_story,
            hard_temporal_eligible=False,
            constraint_role="context_only",
            person_participation_created=False,
        ))

    event_specs = {
        "15-zixin-001": (NEW_EVENT_ID, [
            "evidence-p3b-wave-2-6d483c973c364d7b23254979",
            "evidence-p3b-wave-2-ff4c641ecffcd1c1a0641ea3",
        ], "explicit annotation event context", "unknown"),
        "15-zixin-002": (EXISTING_EIGHT_PRINCES, [
            "evidence-p3b-wave-2-586ad232701eb91a0f11d711",
            "evidence-p3b-wave-2-ad716d81071da46d1b8040fb",
        ], "Liu/虞預 annotation historical background", "year_range"),
        "19-xianyuan-017": (EXISTING_EIGHT_PRINCES, [
            "evidence-p3b-wave-2-8b52c94b636d735cb8a02bf5",
            "evidence-p3b-wave-2-9ea90a5335c5e3f9ce9ae7f0",
        ], "main/annotation historical background", "year_range"),
        "36-chouxi-001": (EXISTING_EIGHT_PRINCES, [
            "evidence-p3b-wave-2-a371b8443e94ff970187ae43",
            "evidence-p3b-wave-2-f0d06a8d76fa4450798a8f5d",
        ], "Liu/王隱 annotation historical background", "year_range"),
    }
    for story_id, (event_id, event_evidence, relation_to_story, precision) in event_specs.items():
        row = accepted.get((story_id, "event"))
        if row is None:
            raise ValueError(f"event review is missing for {story_id}")
        if any(item not in evidence for item in event_evidence):
            raise ValueError(f"event extension evidence is missing for {story_id}")
        event_context(story_id, row, event_id, event_evidence, relation_to_story, precision)

    new_event_row = accepted.get(("15-zixin-001", "event"))
    new_event_evidence = [
        "evidence-p3b-wave-2-6d483c973c364d7b23254979",
        "evidence-p3b-wave-2-ff4c641ecffcd1c1a0641ea3",
    ]
    entities.append({
        "entity_type": "Event",
        "entity_id": NEW_EVENT_ID,
        "semantic_key": "event|齊萬年反",
        "canonical_name": "齊萬年反",
        "aliases": ["齊萬年反", "齊萬年之亂"],
        "event_type": "military_rebellion",
        "start_year_ce": None,
        "end_year_ce": None,
        "temporal_precision": "unknown",
        "location_ids": [],
        "linked_story_ids": ["15-zixin-001"],
        "evidence_ids": new_event_evidence,
        "review_status": "reviewed",
        "assertion_status": "attested",
        "materialization_epoch": EPOCH,
        "canonical_scope": "x1-2a-canonical-extension",
        "source_entity_status": "new_local_entity",
    })
    facts.append(fact_record(
        fact_id=NEW_EVENT_ID,
        fact_type="event",
        subject_ids=[NEW_EVENT_ID, "15-zixin-001"],
        story_ids=["15-zixin-001"],
        evidence_ids=new_event_evidence,
        review_row=new_event_row,
        temporal_precision="unknown",
        event_id=NEW_EVENT_ID,
        canonical_name="齊萬年反",
        event_type="military_rebellion",
        relation_to_story="explicit_local_event_surface",
    ))

    facts.sort(key=lambda row: row["fact_key"])
    entities.sort(key=lambda row: (row["entity_type"], row["entity_id"]))
    manifest = {
        "schema": 1,
        "stage": "x1-2a-materialization-manifest",
        "materialization_epoch": EPOCH,
        "source_review_manifest_sha256": review_hash,
        "source_x1_1_hashes": review_manifest.get("source_hashes", {}).get("x1_1", {}),
        "protected_input_hashes": protected_hashes(),
        "materialization_scope": "canonical_extension_only",
        "canonical_story_additions": [],
        "canonical_person_additions": [],
        "canonical_fact_additions": [row["fact_id"] for row in facts],
        "canonical_entity_additions": [row["entity_id"] for row in entities],
        "deferred_identity_decisions": [
            row["review_item_id"]
            for row in read("data/derived/x1-2a-person-review.json").get("records", [])
            if row.get("review_status") == "accepted"
        ],
        "protected_layers_unchanged": True,
        "no_ml_write_back": True,
        "counts": {
            "stories_added": 0,
            "persons_added": 0,
            "facts_added": len(facts),
            "entities_added": len(entities),
        },
        "policy": "Accepted facts are materialized in a deterministic X1.2A extension. A later explicit corpus migration is required before they become H0C/HG0 production projections.",
    }
    extension = {
        "schema": 1,
        "stage": "x1-2a-canonical-facts",
        "materialization_epoch": EPOCH,
        "source_review_manifest_sha256": review_hash,
        "source_x1_1_hashes": review_manifest.get("source_hashes", {}).get("x1_1", {}),
        "protected_input_hashes": protected_hashes(),
        "canonical_scope": "x1-2a-canonical-extension",
        "entities": entities,
        "fact_index": facts,
        "counts": {
            "entity_count": len(entities),
            "fact_count": len(facts),
            "fact_counts_by_type": {
                fact_type: sum(row["fact_type"] == fact_type for row in facts)
                for fact_type in sorted({row["fact_type"] for row in facts})
            },
        },
        "notes": [
            "This extension does not replace the frozen H0C historical fact index.",
            "Event context facts are context-only and cannot date a Story or create EventParticipation.",
            "No accepted fact creates a Person, reviewed Relation, StoryParticipant, or production Story.",
        ],
    }
    write(MATERIALIZATION_PATH, manifest)
    write(CANONICAL_FACTS_PATH, extension)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    manifest = build()
    print(json.dumps({"stage": manifest["stage"], "counts": manifest["counts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
