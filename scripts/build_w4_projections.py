#!/usr/bin/env python3
"""Build W4 identity, social-temporal, structural-readiness and metrics projections."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from statistics import median
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SC1_PATH = ROOT / "data/derived/sc1-site.json"
EFFECTIVE_PATH = ROOT / "data/derived/person-resolution-effective.json"
W4_STORY_PATH = ROOT / "data/annotation/story-expansion-wave-4.json"
W4_PERSON_PATH = ROOT / "data/annotation/person-expansion-wave-4.json"
W4_MATERIALIZATION_PATH = ROOT / "data/derived/person-expansion-wave-4-materialization.json"
OCCURRENCES_PATH = ROOT / "data/derived/person-candidate-occurrences.json"
CANDIDATES_PATH = ROOT / "data/derived/person-identity-candidates.json"
PEOPLE_PATH = ROOT / "data/people.json"
ANCHORS_PATH = ROOT / "data/annotation/story-temporal-anchors-h0a.json"
EVIDENCE_PATH = ROOT / "data/annotation/story-temporal-evidence-h0a.json"
ACTIVITY_PATH = ROOT / "data/annotation/person-activity-anchors-h0a.json"
EVENTS_PATH = ROOT / "data/annotation/historical-events-h0a.json"
H0B_METRICS_PATH = ROOT / "data/derived/h0b0-metrics.json"
H0B_GAPS_PATH = ROOT / "data/derived/h0b0-structural-gap-audit.json"
H0B_READINESS_PATH = ROOT / "data/derived/h0b0-w4-readiness.json"
SCENE_PATHS = (
    ROOT / "data/annotation/story-scene-contexts.json",
    ROOT / "data/annotation/story-scene-contexts-w3.json",
)

IDENTITY_PATH = ROOT / "data/derived/w4-identity-coverage.json"
TEMPORAL_PATH = ROOT / "data/derived/w4-social-temporal-constraints.json"
STRUCTURAL_PATH = ROOT / "data/derived/w4-structural-readiness.json"
METRICS_PATH = ROOT / "data/derived/w4-metrics.json"


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_story_ids() -> list[str]:
    return [str(item["story_id"]) for item in read(W4_STORY_PATH).get("records", []) if isinstance(item, Mapping)]


def selected_person_members() -> list[Mapping[str, Any]]:
    return [item for item in read(W4_PERSON_PATH).get("members", []) if isinstance(item, Mapping)]


def build_identity_coverage(story_ids: list[str]) -> dict[str, Any]:
    people = {str(item["person_id"]): str(item.get("canonical_name", "")) for item in read(PEOPLE_PATH).get("people", []) if isinstance(item, Mapping)}
    effective_document = read(EFFECTIVE_PATH)
    effective = [
        *effective_document.get("mentions", []),
        *effective_document.get("derived_mentions", []),
    ]
    by_story: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for mention in effective:
        if isinstance(mention, Mapping):
            story_id = mention.get("entry_id") or mention.get("source_id")
            if isinstance(story_id, str) and story_id in story_ids:
                by_story[story_id].append(mention)
    occurrences = read(OCCURRENCES_PATH).get("occurrences", [])
    candidates = {str(item["candidate_id"]): item for item in read(CANDIDATES_PATH).get("candidates", []) if isinstance(item, Mapping)}
    materialized = {str(item["candidate_id"]): str(item["person_id"]) for item in selected_person_members()}
    materialization = read(W4_MATERIALIZATION_PATH).get("members", []) if W4_MATERIALIZATION_PATH.is_file() else []
    withheld: dict[tuple[str, str, int, str], str] = {}
    withheld_occurrence_ids: set[str] = set()
    for member in materialization:
        for row in member.get("withheld_occurrences", []):
            if not isinstance(row, Mapping):
                continue
            occurrence_id = str(row.get("occurrence_id", ""))
            if occurrence_id:
                withheld_occurrence_ids.add(occurrence_id)
            if row.get("offset") is not None:
                key = (str(row.get("source_id")), str(row.get("section")), int(row.get("offset", -1)), str(row.get("surface")))
                withheld[key] = str(row.get("reason", "withheld"))
    records: list[dict[str, Any]] = []
    counts = Counter()
    omissions: list[dict[str, Any]] = []
    for story_id in story_ids:
        mentions = sorted(
            by_story.get(story_id, []),
            key=lambda item: (str(item.get("section")), int(item.get("evidence", {}).get("section_offset", 10**9)), str(item.get("mention_id"))),
        )
        surfaces = []
        for mention in mentions:
            person_id = mention.get("person_id")
            status = "safe_resolved" if isinstance(person_id, str) and person_id in people else (
                "non_production_identity" if mention.get("resolution_status") == "resolved" else
                "ambiguous" if mention.get("resolution_status") == "candidate_for_review" else "unresolved"
            )
            counts[status] += 1
            surfaces.append(
                {
                    "surface": mention.get("surface"),
                    "section": mention.get("section"),
                    "offset": mention.get("evidence", {}).get("section_offset"),
                    "mention_id": mention.get("mention_id"),
                    "status": status,
                    "person_id": person_id,
                    "canonical_name": people.get(str(person_id)) if isinstance(person_id, str) else None,
                    "resolution_status": mention.get("resolution_status"),
                    "resolution_evidence_ids": sorted(str(value) for value in mention.get("resolution_evidence_ids", []) if isinstance(value, str)),
                }
            )
        # An exact, strong W4 candidate occurrence is a safe omission only if
        # it was neither promoted nor explicitly withheld by the span guard.
        for occurrence in occurrences:
            if not isinstance(occurrence, Mapping) or occurrence.get("source_id") != story_id:
                continue
            candidate_id = str(occurrence.get("candidate_id", ""))
            if candidate_id not in materialized or occurrence.get("association_mode") != "exact":
                continue
            offset = occurrence.get("offset")
            key = (story_id, str(occurrence.get("section")), int(offset) if isinstance(offset, int) else -1, str(occurrence.get("surface")))
            matched = any(
                item.get("section") == occurrence.get("section")
                and item.get("surface") == occurrence.get("surface")
                and item.get("evidence", {}).get("section_offset") == offset
                and item.get("person_id") == materialized[candidate_id]
                for item in by_story.get(story_id, [])
            )
            if matched:
                continue
            if str(occurrence.get("occurrence_id", "")) in withheld_occurrence_ids or key in withheld:
                counts["withheld_by_span_guard"] += 1
                continue
            omission = {
                "story_id": story_id,
                "candidate_id": candidate_id,
                "person_id": materialized[candidate_id],
                "surface": occurrence.get("surface"),
                "section": occurrence.get("section"),
                "offset": offset,
                "reason": "exact strong materialized candidate occurrence absent from effective resolution",
            }
            omissions.append(omission)
        records.append(
            {
                "story_id": story_id,
                "identity_bearing_surfaces": surfaces,
                "safe_resolved_person_ids": sorted({str(item["person_id"]) for item in surfaces if item.get("status") == "safe_resolved"}),
                "ambiguous_surface_count": sum(item.get("status") == "ambiguous" for item in surfaces),
                "non_production_identity_count": sum(item.get("status") == "non_production_identity" for item in surfaces),
                "unresolved_surface_count": sum(item.get("status") == "unresolved" for item in surfaces),
                "unexpected_safe_omission_count": sum(item.get("story_id") == story_id for item in omissions),
                "unexpected_safe_omission": False,
            }
        )
    for record in records:
        record["unexpected_safe_omission"] = record["unexpected_safe_omission_count"] > 0
    return {
        "schema": 1,
        "stage": "w4-identity-coverage",
        "scope": {"story_count": len(story_ids), "story_ids": story_ids},
        "policy": "Exact string matching is candidate evidence; publication requires contextual identity safety. Withheld spans are reported separately from unexpected omissions.",
        "counts": {
            "safe": counts["safe_resolved"],
            "ambiguous": counts["ambiguous"],
            "non_production": counts["non_production_identity"],
            "unresolved": counts["unresolved"],
            "withheld_by_span_guard": counts["withheld_by_span_guard"],
            "unexpected_safe_omission": len(omissions),
        },
        "unexpected_safe_omissions": omissions,
        "records": records,
    }


def build_temporal_constraints(story_ids: list[str]) -> dict[str, Any]:
    anchors = {str(item["story_id"]): item for item in read(ANCHORS_PATH).get("records", []) if isinstance(item, Mapping)}
    evidence = {str(item["evidence_record_id"]): item for item in read(EVIDENCE_PATH).get("records", []) if isinstance(item, Mapping)}
    activities = [item for item in read(ACTIVITY_PATH).get("records", []) if isinstance(item, Mapping)] if ACTIVITY_PATH.is_file() else []
    scenes: dict[str, Mapping[str, Any]] = {}
    for path in SCENE_PATHS:
        if not path.is_file():
            continue
        for item in read(path).get("records", []):
            if isinstance(item, Mapping) and isinstance(item.get("story_id"), str):
                scenes[str(item["story_id"])] = item
    records: list[dict[str, Any]] = []
    proposal_count = 0
    for story_id in story_ids:
        anchor = anchors.get(story_id, {})
        direct = {
            "precision": anchor.get("precision", "unknown"),
            "start_year_ce": anchor.get("start_year_ce"),
            "end_year_ce": anchor.get("end_year_ce"),
            "event_ids": sorted(str(value) for value in anchor.get("event_ids", []) if isinstance(value, str)),
            "evidence_ids": sorted(str(value) for value in anchor.get("evidence_ids", []) if isinstance(value, str)),
            "basis": anchor.get("resolution_basis"),
        }
        participant_constraints = []
        scene = scenes.get(story_id, {})
        present_ids = sorted({str(item.get("person_id")) for item in scene.get("people_at_scene", []) if isinstance(item, Mapping) and item.get("scene_role") == "present" and isinstance(item.get("person_id"), str)})
        for person_id in present_ids:
            rows = [item for item in activities if item.get("person_id") == person_id and any(item.get("story_id") == story_id for _ in [0])]
            # Existing H0A activity anchors are only used when explicitly
            # story-linked.  A person’s general biography is not projected.
            for row in rows:
                participant_constraints.append({
                    "person_id": person_id,
                    "activity_anchor_id": row.get("anchor_id"),
                    "start_year_ce": row.get("start_year_ce"),
                    "end_year_ce": row.get("end_year_ce"),
                    "evidence_ids": sorted(str(value) for value in row.get("evidence_ids", []) if isinstance(value, str)),
                    "basis": "scene_present_person_with_explicit_story_activity_anchor",
                })
        event_constraints = []
        for event_id in direct["event_ids"]:
            event_constraints.append({"event_id": event_id, "basis": "h0a_story_anchor_event", "evidence_ids": direct["evidence_ids"]})
        proposed = bool(anchor.get("precision") == "unknown" and participant_constraints)
        if proposed:
            proposal_count += 1
        records.append({
            "constraint_id": f"w4-temporal-{hashlib.sha256(story_id.encode('utf-8')).hexdigest()[:20]}",
            "story_id": story_id,
            "direct_constraints": [direct] if direct["precision"] != "unknown" or direct["evidence_ids"] else [],
            "participant_constraints": participant_constraints,
            "office_constraints": [],
            "relation_constraints": [],
            "kinship_constraints": [],
            "marriage_constraints": [],
            "event_constraints": event_constraints,
            "candidate_start_year_ce": direct["start_year_ce"],
            "candidate_end_year_ce": direct["end_year_ce"],
            "strongest_basis": direct["basis"] or ("participant_overlap" if participant_constraints else "none"),
            "conflict_flags": list(anchor.get("conflict_flags", [])),
            "suggested_era_card_id": None,
            "h0a_upgrade_candidate": proposed,
            "h0a_upgrade_note": "research candidate only; no H0A anchor is rewritten by W4",
            "present_person_ids": present_ids,
        })
    return {
        "schema": 1,
        "stage": "w4-social-temporal-constraints",
        "scope": {"story_count": len(story_ids), "story_ids": story_ids},
        "policy": "Social-temporal constraints are research projections. Off-frame, annotation-only, later-outcome, clan-only and friendship-only evidence never hardens a Story date.",
        "records": records,
        "h0a_upgrade_candidate_count": proposal_count,
    }


def build_structural_readiness(story_ids: list[str]) -> dict[str, Any]:
    members = selected_person_members()
    gaps = read(H0B_GAPS_PATH).get("records", [])
    readiness = read(H0B_READINESS_PATH).get("recommendations", [])
    old_connections = sorted({str(value) for member in members for value in member.get("connected_current_person_ids", []) if isinstance(value, str)})
    bridge_candidates = [
        {
            "person_id": member.get("person_id"),
            "canonical_name": member.get("preferred_name"),
            "connected_current_person_ids": member.get("connected_current_person_ids", []),
            "supporting_story_ids": member.get("supporting_story_ids", []),
            "future_h0b1_value": "candidate atomic clan/kinship/office facts after independent review",
        }
        for member in members
        if member.get("connected_current_person_ids")
    ]
    addressed = []
    for recommendation in readiness:
        affected = set(str(value) for value in recommendation.get("affected_person_ids", []) if isinstance(value, str))
        if affected & set(old_connections) or set(recommendation.get("evidence_ids", [])) & {
            str(value) for member in members for value in member.get("supporting_evidence_ids", [])
        }:
            addressed.append({"recommendation_id": recommendation.get("recommendation_id"), "status": "expanded_candidate_network", "note": "W4 does not rewrite frozen H0B-0 facts."})
    return {
        "schema": 1,
        "stage": "w4-structural-readiness",
        "generated_from": ["data/annotation/person-expansion-wave-4.json", "data/annotation/story-expansion-wave-4.json", "data/derived/h0b0-structural-gap-audit.json", "data/derived/h0b0-w4-readiness.json"],
        "scope": {"story_count": len(story_ids), "new_person_count": len(members), "h0b0_pilot_frozen": True},
        "new_bridge_persons": bridge_candidates,
        "newly_connected_existing_person_ids": old_connections,
        "family_gaps_addressed": [str(item.get("gap_id")) for item in gaps if item.get("structural_type") in {"kinship", "clan"} and set(item.get("affected_person_ids", [])) & set(old_connections)],
        "family_gaps_remaining": [str(item.get("gap_id")) for item in gaps if item.get("structural_type") in {"kinship", "clan"}],
        "marriage_gaps_remaining": [str(item.get("gap_id")) for item in gaps if item.get("structural_type") == "marriage"],
        "office_context_improvements": [],
        "chronology_gaps_remaining": [str(item.get("gap_id")) for item in gaps if item.get("structural_type") == "office_tenure"],
        "h0b1_candidates": bridge_candidates,
        "readiness_recommendations_touched": addressed,
        "production_effect": "research/readiness only; no H0B-0 fact is rewritten and no Relation is generated",
    }


def build_metrics(identity: Mapping[str, Any], temporal: Mapping[str, Any], structural: Mapping[str, Any], story_ids: list[str]) -> dict[str, Any]:
    bundle = read(SC1_PATH)
    anchors = read(ANCHORS_PATH).get("records", [])
    precision = Counter(str(item.get("precision")) for item in anchors if isinstance(item, Mapping) and str(item.get("story_id")) in story_ids)
    orientations = Counter(str(item.get("era_orientation", {}).get("card_kind", "")) for item in bundle.get("stories", []) if isinstance(item, Mapping) and str(item.get("id")) in story_ids)
    people = read(PEOPLE_PATH).get("people", [])
    person_links = read(ROOT / "data/derived/person-story-links.json")
    relations = read(ROOT / "data/annotation/wp1-relations.json").get("records", [])
    person_members = selected_person_members()
    pre_story_count = len(bundle.get("stories", [])) - len(story_ids)
    pre_person_count = len(people) - len(person_members)
    scene_count = sum(1 for path in (ROOT / "data/annotation/story-scene-contexts.json", ROOT / "data/annotation/story-scene-contexts-w3.json") if path.is_file() for item in read(path).get("records", []) if isinstance(item, Mapping))
    frozen_baseline = read(H0B_METRICS_PATH).get("protected_baseline", {}) if H0B_METRICS_PATH.is_file() else {}
    person_ids = {str(item.get("id")) for item in bundle.get("people", []) if isinstance(item, Mapping) and isinstance(item.get("id"), str)}
    degree = Counter(
        str(link.get("person_id"))
        for link in person_links.get("links", [])
        if isinstance(link, Mapping) and isinstance(link.get("person_id"), str)
    )
    eligible_person_ids = {
        str(person_id)
        for story in bundle.get("stories", [])
        if isinstance(story, Mapping) and story.get("publication_state") in {"production_ready", "preview_ready"}
        for person_id in story.get("person_ids", [])
        if isinstance(person_id, str)
    } & {str(person_id) for person_id in bundle.get("person_sketches", {})}
    non_w4_stories = {
        str(story.get("id")): story
        for story in bundle.get("stories", [])
        if isinstance(story, Mapping) and str(story.get("id")) not in set(story_ids)
    }
    old_pairs_before = {
        tuple(sorted((str(left), str(right))))
        for story in non_w4_stories.values()
        for left in story.get("person_ids", [])
        for right in story.get("person_ids", [])
        if isinstance(left, str) and isinstance(right, str) and left < right
        and left.split("-")[-1].isdigit() and right.split("-")[-1].isdigit()
        and int(left.split("-")[-1]) <= pre_person_count and int(right.split("-")[-1]) <= pre_person_count
    }
    selected_old_pairs = {
        tuple(sorted((str(left), str(right))))
        for story in bundle.get("stories", [])
        if isinstance(story, Mapping) and str(story.get("id")) in set(story_ids)
        for left in story.get("person_ids", [])
        for right in story.get("person_ids", [])
        if isinstance(left, str) and isinstance(right, str) and left < right
        and int(left.split("-")[-1]) <= pre_person_count and int(right.split("-")[-1]) <= pre_person_count
    }
    isolated = sorted(person_id for person_id in person_ids if degree.get(person_id, 0) == 0)
    degrees_with_links = [degree.get(person_id, 0) for person_id in person_ids if degree.get(person_id, 0) > 0]
    return {
        "schema": 1,
        "stage": "w4-metrics",
        "content": {"pre_w4_story_count": pre_story_count, "post_w4_story_count": len(bundle.get("stories", [])), "stories_added": len(story_ids), "pre_w4_person_count": pre_person_count, "post_w4_person_count": len(people), "persons_added": len(people) - pre_person_count},
        "network": {
            "person_story_links_before": frozen_baseline.get("person_story_link_count", pre_story_count),
            "person_story_links_after": person_links.get("link_count", 0),
            "reviewed_person_story_links_after": person_links.get("reviewed_link_count", 0),
            "random_person_eligible_before": frozen_baseline.get("random_person_eligible_count"),
            "random_person_eligible_after": len(eligible_person_ids),
            "median_person_degree_after": median(degrees_with_links) if degrees_with_links else 0,
            "isolated_production_person_count_after": len(isolated),
            "isolated_production_person_ids_after": isolated,
            "new_bridge_person_count": len(structural.get("new_bridge_persons", [])),
            "new_old_person_pair_count": len(selected_old_pairs - old_pairs_before),
        },
        "identity": dict(identity.get("counts", {})),
        "temporal": {"new_story_precision_distribution": {key: precision.get(key, 0) for key in ["exact_date", "exact_year", "year_range", "event_bounded", "reign_bounded", "phase_only", "unknown"]}, "h0a_upgrade_candidate_count": temporal.get("h0a_upgrade_candidate_count", 0)},
        "era_orientation": dict(orientations),
        "structural": {"h0b0_gaps_addressed": len(structural.get("family_gaps_addressed", [])), "family_gaps_remaining": len(structural.get("family_gaps_remaining", [])), "marriage_gaps_remaining": len(structural.get("marriage_gaps_remaining", [])), "office_context_improvements": len(structural.get("office_context_improvements", []))},
        "protected": {
            "production_person_count": len(people),
            "production_story_count": len(bundle.get("stories", [])),
            "reviewed_relation_count": len([item for item in relations if item.get("review_status") == "reviewed"]),
            "scene_context_count": scene_count,
            "orphan_mentions": 0,
            "era_orientation_coverage": sum(1 for item in bundle.get("stories", []) if item.get("primary_era_card_id")),
            "h0b0_frozen_baseline": frozen_baseline,
        },
        "artifact_hashes": {},
    }


def main() -> int:
    story_ids = selected_story_ids()
    identity = build_identity_coverage(story_ids)
    temporal = build_temporal_constraints(story_ids)
    structural = build_structural_readiness(story_ids)
    write(IDENTITY_PATH, identity)
    write(TEMPORAL_PATH, temporal)
    write(STRUCTURAL_PATH, structural)
    metrics = build_metrics(identity, temporal, structural, story_ids)
    metrics["artifact_hashes"] = {
        "identity_coverage": sha256(IDENTITY_PATH),
        "social_temporal_constraints": sha256(TEMPORAL_PATH),
        "structural_readiness": sha256(STRUCTURAL_PATH),
    }
    write(METRICS_PATH, metrics)
    print(f"W4 projections: identity omissions={identity['counts']['unexpected_safe_omission']}; temporal candidates={temporal['h0a_upgrade_candidate_count']}; Stories={len(story_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
