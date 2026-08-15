#!/usr/bin/env python3
"""Build H0C historical-context and graph-learning readiness projections.

H0C is a derived, evidence-first layer over the protected H0B-1 corpus.  It
freezes the existing StoryParticipant semantics, normalizes reusable entities,
and emits a framework-neutral heterogeneous graph projection.  It never edits
canonical Persons, Stories, Mentions, Relations, source payloads, or H0A/H0B
inputs.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
BASELINE_COMMIT = "001ae6043f39e9e78d7677c14fd318a7b4124634"

PEOPLE_PATH = Path("data/people.json")
ALIASES_PATH = Path("data/aliases.json")
SHISHUO_MENTIONS_PATH = Path("data/mentions/shishuo.json")
JINSHU_MENTIONS_PATH = Path("data/mentions/jinshu.json")
EVIDENCE_PATH = Path("data/evidence/wp1-evidence.json")
SC1_PATH = Path("data/derived/sc1-site.json")
EFFECTIVE_MENTIONS_PATH = Path("data/derived/person-resolution-effective.json")
PERSON_IDENTITY_CANDIDATES_PATH = Path("data/derived/person-identity-candidates.json")
PERSON_STORY_PATH = Path("data/derived/person-story-links.json")
SCENE_CONTEXT_PATH = Path("data/derived/story-scene-contexts.json")
H0B1_PARTICIPANTS_PATH = Path("data/derived/h0b1-story-participants.json")
H0B1_BACKBONE_PATH = Path("data/derived/h0b1-social-backbone.json")
H0B1_RELATION_CONTEXTS_PATH = Path("data/derived/h0b1-relation-temporal-contexts.json")
H0B1_CONSTRAINTS_PATH = Path("data/derived/h0b1-social-temporal-constraints.json")
H0B1_GAPS_PATH = Path("data/derived/h0b1-gap-audit.json")
H0B1_METRICS_PATH = Path("data/derived/h0b1-metrics.json")
ANCHORS_PATH = Path("data/annotation/story-temporal-anchors-h0a.json")
ACTIVITY_PATH = Path("data/annotation/person-activity-anchors-h0a.json")
EVENTS_PATH = Path("data/annotation/historical-events-h0a.json")
TEMPORAL_EVIDENCE_PATH = Path("data/annotation/story-temporal-evidence-h0a.json")
COORDINATES_PATH = Path("data/derived/h0a-temporal-coordinates.json")
RELATIONS_PATH = Path("data/annotation/wp1-relations.json")
PROTECTED_HASH_PATH = Path("data/derived/protected-hash-scopes.json")
ENTITY_ID_MANIFEST_PATH = Path("data/annotation/h0c-entity-id-manifest.json")

H0B0_INPUTS = {
    "social_backbone": Path("data/derived/h0b0-social-backbone.json"),
    "gaps": Path("data/derived/h0b0-structural-gap-audit.json"),
    "metrics": Path("data/derived/h0b0-metrics.json"),
}

OUTPUTS = {
    "participant_freeze": Path("data/derived/h0c-participant-freeze.json"),
    "locations": Path("data/derived/h0c-locations.json"),
    "offices": Path("data/derived/h0c-offices.json"),
    "events": Path("data/derived/h0c-events.json"),
    "regimes": Path("data/derived/h0c-regimes.json"),
    "person_activities": Path("data/derived/h0c-person-activities.json"),
    "event_participations": Path("data/derived/h0c-event-participations.json"),
    "location_facts": Path("data/derived/h0c-location-facts.json"),
    "service_contexts": Path("data/derived/h0c-service-political-facts.json"),
    "historical_facts": Path("data/derived/h0c-historical-facts.json"),
    "graph": Path("data/derived/h0c-graph-projection.json"),
    "graph_audit": Path("data/derived/h0c-graph-audit.json"),
    "gaps": Path("data/derived/h0c-gap-audit.json"),
    "readiness": Path("data/derived/h0c-ml-readiness.json"),
    "protection": Path("data/derived/h0c-protection-manifest.json"),
    "metrics": Path("data/derived/h0c-metrics.json"),
}

H0C_GAP_CATEGORIES = (
    "participant_role_uncertain",
    "participant_provenance_missing",
    "location_not_normalized",
    "location_precision_coarse",
    "location_modern_mapping_unknown",
    "event_location_unresolved",
    "office_chronology_incomplete",
    "missing_structural_endpoint",
    "missing_family_bridge",
    "marriage_endpoint_not_production",
    "clan_branch_unresolved",
    "relation_temporal_scope_missing",
    "identity_compatibility_gap",
    "source_conflict",
    "temporal_conflict",
    "graph_orphan_node",
    "graph_unsupported_edge",
    "graph_duplicate_semantic_edge",
    "family_cycle_anomaly",
)

# A small orthographic normalizer lets the H0B-0 simplified office labels and
# H0B-1 traditional labels share an Office entity without pretending that the
# conversion is historical interpretation.
TRADITIONAL_MAP = str.maketrans(
    {
        "东": "東", "晋": "晉", "将": "將", "军": "軍", "参": "參", "长": "長",
        "书": "書", "仆": "僕", "镇": "鎮", "马": "馬", "县": "縣", "阳": "陽",
        "黄": "黃", "门": "門", "记": "記", "从": "從", "吴": "吳", "兴": "興",
        "头": "頭", "濑": "瀨", "广": "廣", "兖": "兗", "识": "識", "归": "歸",
        "气": "氣", "与": "與", "为": "為", "乱": "亂", "卫": "衛", "刘": "劉",
        "温": "溫", "谢": "謝", "王": "王", "郗": "郗", "临": "臨", "过": "過",
        "处": "處", "见": "見", "后": "後", "内": "內", "两": "兩", "别": "別",
        "贤": "賢", "书": "書", "职": "職", "员": "員", "县": "縣", "东": "東",
    }
)


def read_json(relative: Path) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def write_json(relative: Path, value: Any) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(relative: Path) -> str:
    digest = hashlib.sha256()
    with (ROOT / relative).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_value(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def stable_id(prefix: str, *parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def unique(values: Iterable[object]) -> list[str]:
    return sorted({str(value) for value in values if value is not None and str(value)})


def canonical_label(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    text = "".join(text.split())
    return text.translate(TRADITIONAL_MAP)


def entity_id(entity_ids: Mapping[tuple[str, str], str], entity_type: str, semantic_key: str) -> str:
    try:
        return entity_ids[(entity_type, semantic_key)]
    except KeyError as exc:
        raise ValueError(f"H0C entity ID manifest lacks {entity_type}:{semantic_key}") from exc


def records(document: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    value = document.get(key, [])
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def source_ref(evidence_id: str, evidence_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    item = evidence_by_id.get(evidence_id)
    if item is None:
        return {"evidence_id": evidence_id, "source_layer": "unresolved_repository_reference"}
    locator = item.get("locator", {})
    provenance = locator.get("source_provenance", {}) if isinstance(locator, Mapping) else {}
    return {
        "evidence_id": evidence_id,
        "source_id": item.get("source_id"),
        "evidence_type": item.get("evidence_type"),
        "artifact_type": locator.get("artifact_type"),
        "artifact_path": locator.get("artifact_path"),
        "artifact_sha256": locator.get("artifact_sha256"),
        "entry_id": locator.get("entry_id"),
        "unit_id": locator.get("unit_id"),
        "source_witness_id": provenance.get("witness_id"),
        "source_path": provenance.get("source_path"),
        "source_sha256": provenance.get("source_sha256"),
        "source_layer": item.get("source_layer"),
    }


def load_inputs() -> dict[str, Any]:
    people_doc = read_json(PEOPLE_PATH)
    aliases_doc = read_json(ALIASES_PATH)
    shishuo_mentions = read_json(SHISHUO_MENTIONS_PATH)
    jinshu_mentions = read_json(JINSHU_MENTIONS_PATH)
    evidence_doc = read_json(EVIDENCE_PATH)
    sc1 = read_json(SC1_PATH)
    effective = read_json(EFFECTIVE_MENTIONS_PATH)
    identity_candidates = read_json(PERSON_IDENTITY_CANDIDATES_PATH)
    person_story = read_json(PERSON_STORY_PATH)
    scene = read_json(SCENE_CONTEXT_PATH)
    participants = read_json(H0B1_PARTICIPANTS_PATH)
    backbone = read_json(H0B1_BACKBONE_PATH)
    relation_contexts = read_json(H0B1_RELATION_CONTEXTS_PATH)
    constraints = read_json(H0B1_CONSTRAINTS_PATH)
    h0b1_gaps = read_json(H0B1_GAPS_PATH)
    h0b1_metrics = read_json(H0B1_METRICS_PATH)
    anchors = read_json(ANCHORS_PATH)
    activities = read_json(ACTIVITY_PATH)
    events = read_json(EVENTS_PATH)
    temporal_evidence = read_json(TEMPORAL_EVIDENCE_PATH)
    coordinates = read_json(COORDINATES_PATH)
    relations = read_json(RELATIONS_PATH)
    entity_manifest = read_json(ENTITY_ID_MANIFEST_PATH)

    evidence_by_id: dict[str, dict[str, Any]] = {}
    for item in records(evidence_doc, "records"):
        if item.get("id"):
            evidence_by_id[str(item["id"])] = item
    for item in records(sc1, "evidence"):
        if item.get("id"):
            evidence_by_id[str(item["id"])] = item
    for item in identity_candidates.get("evidence", []):
        if isinstance(item, Mapping) and item.get("id"):
            evidence_by_id[str(item["id"])] = item
    for item in records(temporal_evidence, "records"):
        evidence_id = item.get("evidence_record_id", item.get("id"))
        if evidence_id:
            evidence_by_id[str(evidence_id)] = {
                "id": evidence_id,
                "source_id": item.get("source_id"),
                "source_layer": item.get("source_layer"),
                "evidence_type": item.get("evidence_type"),
                "locator": {
                    "entry_id": item.get("story_id"),
                    "source_span": item.get("source_span"),
                    "source_evidence_ids": item.get("source_evidence_ids", []),
                },
                "assertion_status": item.get("assertion_status"),
                "review_status": item.get("review_status"),
            }

    people = records(people_doc, "people")
    stories = [dict(item) for item in sc1.get("stories", []) if isinstance(item, Mapping)]
    stories.sort(key=lambda item: (int(item.get("global_ordinal", 10**9)), str(item.get("id", ""))))
    if len(people) != 75 or len(stories) != 143:
        raise ValueError("H0C requires the protected 75-Person / 143-Story scope")
    return {
        "people": people,
        "people_by_id": {str(item["id"] if "id" in item else item["person_id"]): item for item in people},
        "aliases": records(aliases_doc, "aliases"),
        "shishuo_mentions": records(shishuo_mentions, "mentions"),
        "jinshu_mentions": records(jinshu_mentions, "mentions"),
        "evidence_by_id": evidence_by_id,
        "sc1": sc1,
        "stories": stories,
        "story_by_id": {str(item["id"]): item for item in stories},
        "effective": effective,
        "identity_candidates": identity_candidates,
        "person_story": person_story,
        "scene": scene,
        "participants": participants,
        "backbone": backbone,
        "relation_contexts": relation_contexts,
        "constraints": constraints,
        "h0b1_gaps": h0b1_gaps,
        "h0b1_metrics": h0b1_metrics,
        "anchors": records(anchors, "records"),
        "activities": records(activities, "records"),
        "events": records(events, "records"),
        "temporal_evidence": records(temporal_evidence, "records"),
        "coordinates": coordinates,
        "relations": records(relations, "records"),
        "entity_manifest": entity_manifest,
        "entity_ids": {
            (str(item.get("entity_type")), str(item.get("semantic_key"))): str(item.get("entity_id"))
            for item in entity_manifest.get("records", [])
        },
    }


def story_id_from_mention(item: Mapping[str, Any]) -> str | None:
    value = item.get("entry_id", item.get("source_id", item.get("story_id")))
    return str(value) if value else None


def mention_provenance(inputs: Mapping[str, Any]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    by_pair: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    people = set(inputs["people_by_id"])
    rows = [
        *records(inputs["effective"], "mentions"),
        *records(inputs["effective"], "derived_mentions"),
        *records(inputs["sc1"], "mentions"),
    ]
    for item in rows:
        story_id = story_id_from_mention(item)
        person_id = item.get("person_id")
        if story_id not in inputs["story_by_id"] or person_id not in people:
            continue
        mention_id = str(item.get("mention_id", item.get("id", "")))
        if not mention_id:
            continue
        display_span = item.get("display_span") if isinstance(item.get("display_span"), Mapping) else {}
        evidence = item.get("evidence") if isinstance(item.get("evidence"), Mapping) else {}
        evidence_ids = unique([
            *item.get("evidence_ids", []),
            *item.get("resolution_evidence_ids", []),
            *display_span.get("evidence_ids", []),
            *evidence.get("evidence_ids", []),
        ])
        candidate = {
            "mention_id": mention_id,
            "section": item.get("section"),
            "surface": item.get("surface"),
            "anchor": item.get("anchor") or item.get("display_span") or item.get("source_span"),
            "evidence_ids": evidence_ids,
            "provenance_refs": [f"mention:{mention_id}"],
            "resolution_method": item.get("resolution_method") or item.get("resolution_method"),
            "source": item.get("source"),
        }
        current = by_pair[(story_id, str(person_id))].get(mention_id)
        if current is None:
            by_pair[(story_id, str(person_id))][mention_id] = candidate
        else:
            current["evidence_ids"] = unique([*current.get("evidence_ids", []), *evidence_ids])
            current["provenance_refs"] = unique([*current.get("provenance_refs", []), f"mention:{mention_id}"])
            for field in ("anchor", "surface", "section", "resolution_method", "source"):
                if current.get(field) is None and candidate.get(field) is not None:
                    current[field] = candidate[field]
    return {
        key: sorted(value.values(), key=lambda item: (str(item.get("section")), str(item.get("mention_id"))))
        for key, value in by_pair.items()
    }


def build_participant_freeze(inputs: Mapping[str, Any]) -> dict[str, Any]:
    provenance_by_pair = mention_provenance(inputs)
    records_out: list[dict[str, Any]] = []
    role_reasons = {
        "present": "reviewed_scene_or_explicit_presence",
        "speaker": "reviewed_story_speaker_semantics",
        "actor": "reviewed_story_action_semantics",
        "referenced": "resolved_main_text_reference_without_scene_presence",
        "off_frame": "reviewed_scene_context_off_frame_role",
        "annotation_only": "resolved_annotation_or_biographical_context_only",
        "uncertain": "reviewed_uncertain_participation_semantics",
    }
    for story_record in inputs["participants"].get("records", []):
        story_id = str(story_record["story_id"])
        for item in story_record.get("participants", []):
            role = str(item["role"])
            pair = (story_id, str(item["person_id"]))
            provenance = provenance_by_pair.get(pair, [])
            evidence_ids = unique([
                *item.get("evidence_ids", []),
                *[eid for source in provenance for eid in source.get("evidence_ids", [])],
            ])
            provenance_refs = unique([
                *[ref for source in provenance for ref in source.get("provenance_refs", [])],
            ])
            provenance_complete = bool(evidence_ids and (provenance or item.get("basis") == "reviewed_scene_context"))
            records_out.append(
                {
                    "participant_id": str(item["participant_id"]),
                    "story_id": story_id,
                    "person_id": str(item["person_id"]),
                    "role": role,
                    "hard_temporal_eligible": role in {"present", "speaker", "actor"},
                    "basis": str(item.get("basis", "h0b1_participant_projection")),
                    "source_sections": sorted(set(item.get("source_sections", []))),
                    "mention_provenance": provenance,
                    "evidence_ids": evidence_ids,
                    "provenance_refs": provenance_refs,
                    "provenance_complete": provenance_complete,
                    "source_review_status": item.get("review_status"),
                    "review_status": "reviewed",
                    "review_basis": "h0c_participant_semantic_audit",
                    "review_reason": role_reasons.get(role, "reviewed_participation_semantics"),
                    "notes": item.get("notes"),
                }
            )
    records_out.sort(key=lambda item: (item["story_id"], item["person_id"], item["participant_id"]))
    by_story: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in records_out:
        by_story[item["story_id"]].append(item)
    story_records = []
    for story in inputs["stories"]:
        story_id = str(story["id"])
        rows = by_story.get(story_id, [])
        story_records.append(
            {
                "story_id": story_id,
                "participant_ids": [item["participant_id"] for item in rows],
                "hard_participant_ids": [item["person_id"] for item in rows if item["hard_temporal_eligible"]],
                "contextual_participant_ids": [item["person_id"] for item in rows if not item["hard_temporal_eligible"]],
                "review_status": "reviewed",
            }
        )
    freeze_payload = {"records": records_out, "story_records": story_records}
    return {
        "schema": 1,
        "stage": "h0c-participant-freeze",
        "generated_from": [str(H0B1_PARTICIPANTS_PATH), str(EFFECTIVE_MENTIONS_PATH), str(SC1_PATH), str(SCENE_CONTEXT_PATH)],
        "scope": {"story_count": len(inputs["stories"]), "production_person_count": len(inputs["people"])},
        "records": records_out,
        "story_records": story_records,
        "participant_count": len(records_out),
        "hard_participant_count": sum(item["hard_temporal_eligible"] for item in records_out),
        "role_counts": dict(sorted(Counter(item["role"] for item in records_out).items())),
        "reviewed_role_count": sum(item["review_status"] == "reviewed" for item in records_out),
        "reviewed_uncertain_count": sum(item["role"] == "uncertain" for item in records_out),
        "unreviewed_uncertainty_count": sum(item["role"] == "uncertain" and item["review_status"] != "reviewed" for item in records_out),
        "hard_provenance_complete_count": sum(item["hard_temporal_eligible"] and item["provenance_complete"] for item in records_out),
        "participant_freeze_sha256": hash_value(freeze_payload),
        "policy": "The H0B-1 semantic roles are frozen here. Later enrichment may record anomalies but cannot silently change Story participation.",
    }


def add_location(
    location_map: dict[str, dict[str, Any]],
    *,
    location_id: str,
    name: str,
    location_type: str,
    aliases: Iterable[str],
    evidence_ids: Iterable[str],
    source_basis: str,
    assertion_status: str = "attested",
    review_status: str = "candidate",
) -> str:
    canonical_name = canonical_label(name)
    if not canonical_name:
        raise ValueError("empty H0C Location name")
    record = location_map.get(location_id)
    if record is None:
        record = {
            "location_id": location_id,
            "canonical_name": canonical_name,
            "aliases": [],
            "location_types": [],
            "historical_parent_location_id": None,
            "historical_polity_ids": [],
            "temporal_validity": {"start_year_ce": None, "end_year_ce": None, "precision": "unknown"},
            "modern_mapping": {"status": "unknown", "latitude": None, "longitude": None, "precision": "unknown"},
            "coordinate_precision": "unknown",
            "evidence_ids": [],
            "source_basis": [],
            "assertion_status": assertion_status,
            "review_status": review_status,
            "notes": "Historical label is retained without silently mapping it to a modern administrative identity.",
        }
        location_map[location_id] = record
    record["aliases"] = sorted(set(record["aliases"]) | {str(value) for value in aliases if value})
    record["location_types"] = sorted(set(record["location_types"]) | {location_type})
    record["evidence_ids"] = unique([*record["evidence_ids"], *evidence_ids])
    record["source_basis"] = sorted(set(record["source_basis"]) | {source_basis})
    if assertion_status == "attested":
        record["assertion_status"] = "attested"
    return location_id


def regime_label(value: object) -> str:
    label = canonical_label(value)
    return {"晋": "晉", "西晋": "西晉", "东晋": "東晉", "魏": "魏", "汉": "漢"}.get(label, label)


def build_locations_regimes_offices(inputs: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    location_map: dict[str, dict[str, Any]] = {}
    regime_map: dict[str, dict[str, Any]] = {}
    office_map: dict[str, dict[str, Any]] = {}
    office_rows: list[dict[str, Any]] = []
    backbone = inputs["backbone"]

    def add_regime(raw: object, evidence_ids: Iterable[str], basis: str) -> str | None:
        label = regime_label(raw)
        if not label:
            return None
        regime_id = entity_id(inputs["entity_ids"], "Regime", label)
        regime = regime_map.setdefault(
            regime_id,
            {
                "regime_id": regime_id,
                "canonical_name": label,
                "aliases": [],
                "start_year_ce": None,
                "end_year_ce": None,
                "temporal_precision": "unknown",
                "evidence_ids": [],
                "source_basis": [],
                "assertion_status": "derived",
                "review_status": "candidate",
            },
        )
        regime["aliases"] = sorted(set(regime["aliases"]) | {str(raw)})
        regime["evidence_ids"] = unique([*regime["evidence_ids"], *evidence_ids])
        regime["source_basis"] = sorted(set(regime["source_basis"]) | {basis})
        if evidence_ids:
            regime["assertion_status"] = "attested"
        return regime_id

    for tenure in backbone.get("office_tenures", []):
        evidence_ids = tenure.get("evidence_ids", [])
        regime_id = add_regime(tenure.get("polity"), evidence_ids, "h0b1_office_tenure")
        location_id = None
        jurisdiction_location_id = None
        if tenure.get("location"):
            location_id = add_location(
                location_map,
                location_id=entity_id(inputs["entity_ids"], "Location", canonical_label(tenure["location"])),
                name=str(tenure["location"]),
                location_type="historical_place",
                aliases=[str(tenure["location"])],
                evidence_ids=evidence_ids,
                source_basis=f"office_tenure:{tenure.get('tenure_id')}",
            )
        if tenure.get("jurisdiction"):
            jurisdiction_location_id = add_location(
                location_map,
                location_id=entity_id(inputs["entity_ids"], "Location", canonical_label(tenure["jurisdiction"])),
                name=str(tenure["jurisdiction"]),
                location_type="historical_administrative_region",
                aliases=[str(tenure["jurisdiction"])],
                evidence_ids=evidence_ids,
                source_basis=f"office_tenure:{tenure.get('tenure_id')}",
            )
        office_label = canonical_label(tenure.get("normalized_office_label") or tenure.get("office_title"))
        office_key = f"{office_label}|{regime_label(tenure.get('polity'))}"
        office_id = entity_id(inputs["entity_ids"], "Office", office_key)
        office = office_map.setdefault(
            office_id,
            {
                "office_id": office_id,
                "canonical_name": office_label,
                "aliases": [],
                "institutional_context": {"polity": regime_label(tenure.get("polity")), "jurisdictions": [], "locations": []},
                "tenure_ids": [],
                "evidence_ids": [],
                "assertion_status": "derived",
                "review_status": "candidate",
            },
        )
        if regime_id:
            regime_map[regime_id].setdefault("tenure_ids", []).append(str(tenure["tenure_id"]))
        office["aliases"] = sorted(set(office["aliases"]) | {str(tenure.get("office_title")), str(tenure.get("normalized_office_label"))})
        office["tenure_ids"].append(str(tenure["tenure_id"]))
        office["evidence_ids"] = unique([*office["evidence_ids"], *evidence_ids])
        if jurisdiction_location_id:
            office["institutional_context"]["jurisdictions"] = sorted(set(office["institutional_context"]["jurisdictions"]) | {jurisdiction_location_id})
        if location_id:
            office["institutional_context"]["locations"] = sorted(set(office["institutional_context"]["locations"]) | {location_id})
        if evidence_ids:
            office["assertion_status"] = "attested"
        normalized_tenure = copy.deepcopy(tenure)
        normalized_tenure.update(
            {
                "source_tenure_id": tenure["tenure_id"],
                "office_id": office_id,
                "regime_id": regime_id,
                "location_id": location_id,
                "jurisdiction_location_id": jurisdiction_location_id,
                "normalization_status": "normalized",
                "normalization_basis": "h0b1_office_tenure",
            }
        )
        office_rows.append(normalized_tenure)

    for context in inputs["scene"].get("contexts", {}).values():
        story_id = str(context.get("story_id"))
        for place in context.get("places", []):
            name = place.get("name", {}) if isinstance(place.get("name"), Mapping) else {}
            original = name.get("original") or name.get("simplified")
            if original:
                add_location(
                    location_map,
                    location_id=entity_id(inputs["entity_ids"], "Location", canonical_label(original)),
                    name=str(original),
                    location_type="story_place",
                    aliases=[name.get("original"), name.get("simplified")],
                    evidence_ids=place.get("evidence_ids", []),
                    source_basis=f"scene_context:{story_id}",
                    assertion_status=str(place.get("assertion_status", "attested")),
                    review_status=str(place.get("review_status", "candidate")),
                )

    for record in regime_map.values():
        record["tenure_ids"] = sorted(set(record.get("tenure_ids", [])))
    for record in office_map.values():
        record["tenure_ids"] = sorted(set(record["tenure_ids"]))
    return (
        {"schema": 1, "stage": "h0c-locations", "records": sorted(location_map.values(), key=lambda x: x["location_id"]), "count": len(location_map)},
        {"schema": 1, "stage": "h0c-regimes", "records": sorted(regime_map.values(), key=lambda x: x["regime_id"]), "count": len(regime_map)},
        {
            "schema": 1,
            "stage": "h0c-offices",
            "entities": sorted(office_map.values(), key=lambda x: x["office_id"]),
            "tenures": sorted(office_rows, key=lambda x: str(x["tenure_id"])),
            "office_count": len(office_map),
            "tenure_count": len(office_rows),
        },
        {str(row["tenure_id"]): str(row["office_id"]) for row in office_rows},
    )


def build_events(inputs: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    for event in inputs["events"]:
        name = str(event.get("canonical_name", ""))
        if "南渡" in name:
            event_type = "migration_upheaval"
        elif "八王" in name:
            event_type = "political_disturbance"
        elif "亂" in name:
            event_type = "rebellion"
        else:
            event_type = "historical_event"
        linked_story_ids = sorted({str(claim.get("story_id")) for claim in event.get("source_claims", []) if claim.get("story_id")})
        rows.append(
            {
                "event_id": str(event["event_id"]),
                "canonical_name": name,
                "aliases": sorted(set(event.get("aliases", []))),
                "event_type": event_type,
                "start_year_ce": event.get("start_year_ce"),
                "end_year_ce": event.get("end_year_ce"),
                "temporal_precision": event.get("date_precision", "unknown"),
                "location_ids": sorted(set(event.get("location_ids", []))),
                "linked_story_ids": linked_story_ids,
                "phase_ids": sorted(set(event.get("phase_ids", []))),
                "evidence_ids": unique(event.get("evidence_ids", [])),
                "source_claims": copy.deepcopy(event.get("source_claims", [])),
                "chronology_source_refs": copy.deepcopy(event.get("chronology_source_refs", [])),
                "assertion_status": event.get("assertion_status", "attested"),
                "review_status": event.get("review_status", "candidate"),
                "source_entity_id": str(event["event_id"]),
                "normalization_basis": "h0a_historical_event",
            }
        )
    return {"schema": 1, "stage": "h0c-events", "records": sorted(rows, key=lambda x: x["event_id"]), "count": len(rows)}


def build_activities(inputs: Mapping[str, Any], participant_freeze: Mapping[str, Any], locations: Mapping[str, Any]) -> dict[str, Any]:
    hard_by_story_person = {
        (str(row["story_id"]), str(row["person_id"]))
        for row in participant_freeze["records"]
        if row["hard_temporal_eligible"]
    }
    story_location_ids: dict[str, list[str]] = defaultdict(list)
    location_by_name = {row["canonical_name"]: row["location_id"] for row in locations["records"]}
    for context in inputs["scene"].get("contexts", {}).values():
        story_id = str(context.get("story_id"))
        for place in context.get("places", []):
            name = place.get("name", {}) if isinstance(place.get("name"), Mapping) else {}
            label = canonical_label(name.get("original") or name.get("simplified"))
            if label in location_by_name:
                story_location_ids[story_id].append(location_by_name[label])
    rows_by_id: dict[str, dict[str, Any]] = {}
    duplicate_ids: set[str] = set()
    for anchor in inputs["activities"]:
        story_id, person_id = str(anchor.get("story_id")), str(anchor.get("person_id"))
        location_ids = story_location_ids.get(story_id, []) if (story_id, person_id) in hard_by_story_person else []
        row = copy.deepcopy(anchor)
        row.update(
            {
                "activity_id": str(anchor["anchor_id"]),
                "source_activity_anchor_id": str(anchor["anchor_id"]),
                "location_ids": sorted(set(location_ids)),
                "source_fact_type": "h0a_person_activity_anchor",
                "normalization_basis": "h0a_person_activity_anchor",
            }
        )
        activity_id = str(row["activity_id"])
        if activity_id in rows_by_id:
            duplicate_ids.add(activity_id)
            continue
        rows_by_id[activity_id] = row
    rows = list(rows_by_id.values())
    return {
        "schema": 1,
        "stage": "h0c-person-activities",
        "records": sorted(rows, key=lambda x: str(x["activity_id"])),
        "count": len(rows),
        "source_duplicate_count": len(duplicate_ids),
        "source_duplicate_activity_ids": sorted(duplicate_ids),
        "policy": "H0A activity anchors are reused as candidate historical constraints; H0C does not promote them to reviewed biography.",
    }


def build_event_participations(inputs: Mapping[str, Any], activities: Mapping[str, Any], participant_freeze: Mapping[str, Any]) -> dict[str, Any]:
    roles = {(str(row["story_id"]), str(row["person_id"])): row["role"] for row in participant_freeze["records"]}
    rows = []
    for activity in activities["records"]:
        event_id = activity.get("event_id")
        if not event_id:
            continue
        story_id, person_id = str(activity["story_id"]), str(activity["person_id"])
        role = roles.get((story_id, person_id), "uncertain")
        rows.append(
            {
                "event_participation_id": stable_id("event-participation-h0c", activity["activity_id"]),
                "person_id": person_id,
                "event_id": str(event_id),
                "story_id": story_id,
                "participation_type": "event_participation" if role in {"present", "speaker", "actor"} else "story_event_reference",
                "story_role": role,
                "hard_temporal_eligible": role in {"present", "speaker", "actor"},
                "source_activity_id": activity["activity_id"],
                "evidence_ids": unique(activity.get("evidence_ids", [])),
                "assertion_status": activity.get("assertion_status", "inferred"),
                "review_status": activity.get("review_status", "candidate"),
                "temporal_precision": activity.get("precision", "unknown"),
                "start_year_ce": activity.get("start_year_ce"),
                "end_year_ce": activity.get("end_year_ce"),
                "derivation_basis": "h0a_person_activity_anchor",
            }
        )
    return {"schema": 1, "stage": "h0c-event-participations", "records": sorted(rows, key=lambda x: x["event_participation_id"]), "count": len(rows)}


def build_location_facts(inputs: Mapping[str, Any], offices: Mapping[str, Any], locations: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    location_ids = {row["location_id"] for row in locations["records"]}
    for tenure in offices["tenures"]:
        for role, location_id in (("held_office_at", tenure.get("location_id")), ("office_jurisdiction_at", tenure.get("jurisdiction_location_id"))):
            if not location_id:
                continue
            if location_id not in location_ids:
                raise ValueError(f"H0C OfficeTenure references unknown Location: {tenure['tenure_id']}")
            rows.append(
                {
                    "location_fact_id": stable_id("location-fact-h0c", tenure["tenure_id"], role, location_id),
                    "subject_type": "person",
                    "subject_id": tenure["person_id"],
                    "location_id": location_id,
                    "location_role": role,
                    "office_id": tenure["office_id"],
                    "office_tenure_id": tenure["tenure_id"],
                    "start_year_ce": tenure.get("start_year_ce"),
                    "end_year_ce": tenure.get("end_year_ce"),
                    "temporal_precision": tenure.get("temporal_precision", "unknown"),
                    "evidence_ids": unique(tenure.get("evidence_ids", [])),
                    "assertion_status": tenure.get("assertion_status", "attested"),
                    "review_status": tenure.get("review_status", "candidate"),
                    "derivation_basis": "office_tenure_location_field",
                }
            )
    for context in inputs["scene"].get("contexts", {}).values():
        story_id = str(context.get("story_id"))
        for place in context.get("places", []):
            name = place.get("name", {}) if isinstance(place.get("name"), Mapping) else {}
            label = canonical_label(name.get("original") or name.get("simplified"))
            location = next((row for row in locations["records"] if row["canonical_name"] == label), None)
            if location is None:
                continue
            rows.append(
                {
                    "location_fact_id": stable_id("location-fact-h0c", story_id, "story_present_at", location["location_id"]),
                    "subject_type": "story",
                    "subject_id": story_id,
                    "location_id": location["location_id"],
                    "location_role": "story_present_at",
                    "story_id": story_id,
                    "start_year_ce": None,
                    "end_year_ce": None,
                    "temporal_precision": "unknown",
                    "evidence_ids": unique(place.get("evidence_ids", [])),
                    "assertion_status": place.get("assertion_status", "attested"),
                    "review_status": place.get("review_status", "candidate"),
                    "derivation_basis": "scene_context_place",
                }
            )
    return {"schema": 1, "stage": "h0c-location-facts", "records": sorted(rows, key=lambda x: x["location_fact_id"]), "count": len(rows)}


def build_service_contexts(inputs: Mapping[str, Any]) -> dict[str, Any]:
    context_by_relation = {str(row["relation_id"]): row for row in inputs["relation_contexts"].get("records", [])}
    rows = []
    for relation in inputs["relations"]:
        if relation.get("relation_type") not in {"institutional", "political"}:
            continue
        relation_id = str(relation["id"])
        context = context_by_relation.get(relation_id, {})
        rows.append(
            {
                "service_context_fact_id": stable_id("service-context-h0c", relation_id),
                "relation_id": relation_id,
                "person_a_id": relation.get("subject_id"),
                "person_b_id": relation.get("object_id"),
                "context_type": relation.get("relation_subtype") or relation.get("relation_type"),
                "relation_type": relation.get("relation_type"),
                "story_ids": sorted(set(relation.get("story_ids", []))),
                "event_ids": sorted(set(context.get("event_ids", []))),
                "temporal_precision": context.get("temporal_precision", "unknown"),
                "start_year_ce": context.get("start_year_ce"),
                "end_year_ce": context.get("end_year_ce"),
                "evidence_ids": unique([*relation.get("evidence_ids", []), *context.get("evidence_ids", [])]),
                "assertion_status": relation.get("assertion_status", "attested"),
                "review_status": relation.get("review_status", "reviewed"),
                "derivation_basis": "existing_reviewed_relation_and_temporal_context",
                "applicability_conditions": context.get("applicability_conditions", []),
            }
        )
    return {"schema": 1, "stage": "h0c-service-political-facts", "records": sorted(rows, key=lambda x: x["service_context_fact_id"]), "count": len(rows)}


def fact_key(fact_type: str, fact_id: str) -> str:
    return f"{fact_type}:{fact_id}"


def build_fact_index(inputs: Mapping[str, Any], participant_freeze: Mapping[str, Any], offices: Mapping[str, Any], events: Mapping[str, Any], activities: Mapping[str, Any], event_participations: Mapping[str, Any], location_facts: Mapping[str, Any], service_contexts: Mapping[str, Any]) -> dict[str, Any]:
    facts: dict[str, dict[str, Any]] = {}
    mention_provenance_by_pair = mention_provenance(inputs)
    relation_by_id = {str(row["id"]): row for row in inputs["relations"]}

    def add(fact_type: str, fact_id: object, *, subject_ids: Iterable[object] = (), evidence_ids: Iterable[object] = (), provenance_refs: Iterable[object] = (), review_status: str = "candidate", assertion_status: str = "derived", source_path: str = "", temporal_precision: str | None = None, location_ids: Iterable[object] = (), derived_from: Iterable[object] = ()) -> None:
        key = fact_key(fact_type, str(fact_id))
        if key in facts:
            facts[key]["evidence_ids"] = unique([*facts[key]["evidence_ids"], *evidence_ids])
            facts[key]["provenance_refs"] = unique([*facts[key].get("provenance_refs", []), *provenance_refs])
            facts[key]["derived_from"] = unique([*facts[key].get("derived_from", []), *derived_from])
            return
        facts[key] = {
            "fact_key": key,
            "fact_type": fact_type,
            "fact_id": str(fact_id),
            "subject_ids": unique(subject_ids),
            "evidence_ids": unique(evidence_ids),
            "provenance_refs": unique(provenance_refs),
            "review_status": review_status,
            "assertion_status": assertion_status,
            "source_path": source_path,
            "temporal_precision": temporal_precision,
            "location_ids": unique(location_ids),
            "derived_from": unique(derived_from),
        }

    for row in participant_freeze["records"]:
        add("story_participant", row["participant_id"], subject_ids=[row["person_id"], row["story_id"]], evidence_ids=row["evidence_ids"], review_status=row["review_status"], assertion_status="derived", source_path=str(OUTPUTS["participant_freeze"]))
    for link in records(inputs["person_story"], "links"):
        if str(link.get("entry_id")) not in inputs["story_by_id"]:
            continue
        evidence_ids = list(link.get("evidence_ids", []))
        provenance_refs: list[str] = []
        for mention_id in link.get("supporting_mention_ids", []):
            for mention in mention_provenance_by_pair.get((str(link.get("entry_id")), str(link.get("person_id"))), []):
                if mention.get("mention_id") == mention_id:
                    evidence_ids.extend(mention.get("evidence_ids", []))
                    provenance_refs.extend(mention.get("provenance_refs", []))
        add("person_story_link", link["id"], subject_ids=[link.get("person_id"), link.get("entry_id")], evidence_ids=evidence_ids, provenance_refs=provenance_refs, review_status=link.get("review_status", "candidate"), assertion_status="derived", source_path=str(PERSON_STORY_PATH))

    for family, key_a, key_b in (
        ("clan_membership", "person_id", "clan_id"),
        ("kinship", "person_a_id", "person_b_id"),
        ("marriage", "spouse_a_id", "spouse_b_id"),
    ):
        source_rows = inputs["backbone"].get({"clan_membership": "clan_memberships", "kinship": "kinship", "marriage": "marriages"}[family], [])
        id_key = {"clan_membership": "membership_id", "kinship": "kinship_id", "marriage": "marriage_id"}[family]
        for row in source_rows:
            add(family, row[id_key], subject_ids=[row.get(key_a), row.get(key_b)], evidence_ids=row.get("evidence_ids", []), review_status=row.get("review_status", "candidate"), assertion_status=row.get("assertion_status", "attested"), source_path=str(H0B1_BACKBONE_PATH), temporal_precision=row.get("temporal_status"))
    for row in offices["tenures"]:
        add("office_tenure", row["tenure_id"], subject_ids=[row.get("person_id"), row.get("office_id")], evidence_ids=row.get("evidence_ids", []), review_status=row.get("review_status", "candidate"), assertion_status=row.get("assertion_status", "attested"), source_path=str(OUTPUTS["offices"]), temporal_precision=row.get("temporal_precision"), location_ids=[row.get("location_id"), row.get("jurisdiction_location_id")])
    for row in events["records"]:
        add("event", row["event_id"], subject_ids=[*row.get("linked_story_ids", [])], evidence_ids=row.get("evidence_ids", []), review_status=row.get("review_status", "candidate"), assertion_status=row.get("assertion_status", "attested"), source_path=str(OUTPUTS["events"]), temporal_precision=row.get("temporal_precision"), location_ids=row.get("location_ids", []))
        for claim in row.get("source_claims", []):
            story_id = claim.get("story_id")
            if story_id:
                claim_id = stable_id("event-story-context-h0c", row["event_id"], story_id, claim.get("surface"))
                add("event_story_context", claim_id, subject_ids=[row["event_id"], story_id], evidence_ids=claim.get("evidence_ids", []), review_status="candidate", assertion_status="derived", source_path=str(OUTPUTS["events"]), temporal_precision=row.get("temporal_precision"), derived_from=[row["event_id"]])
    for row in activities["records"]:
        add("person_activity", row["activity_id"], subject_ids=[row.get("person_id"), row.get("story_id"), row.get("event_id")], evidence_ids=row.get("evidence_ids", []), review_status=row.get("review_status", "candidate"), assertion_status=row.get("assertion_status", "inferred"), source_path=str(OUTPUTS["person_activities"]), temporal_precision=row.get("precision"), location_ids=row.get("location_ids", []), derived_from=[row.get("source_activity_anchor_id")])
    for row in event_participations["records"]:
        add("event_participation", row["event_participation_id"], subject_ids=[row.get("person_id"), row.get("event_id"), row.get("story_id")], evidence_ids=row.get("evidence_ids", []), review_status=row.get("review_status", "candidate"), assertion_status=row.get("assertion_status", "inferred"), source_path=str(OUTPUTS["event_participations"]), temporal_precision=row.get("temporal_precision"), derived_from=[row.get("source_activity_id")])
    for row in location_facts["records"]:
        add("location_fact", row["location_fact_id"], subject_ids=[row.get("subject_id"), row.get("location_id")], evidence_ids=row.get("evidence_ids", []), review_status=row.get("review_status", "candidate"), assertion_status=row.get("assertion_status", "attested"), source_path=str(OUTPUTS["location_facts"]), temporal_precision=row.get("temporal_precision"), location_ids=[row.get("location_id")], derived_from=[row.get("office_tenure_id")])
    for row in service_contexts["records"]:
        add("service_political", row["service_context_fact_id"], subject_ids=[row.get("person_a_id"), row.get("person_b_id")], evidence_ids=row.get("evidence_ids", []), review_status=row.get("review_status", "reviewed"), assertion_status=row.get("assertion_status", "attested"), source_path=str(OUTPUTS["service_contexts"]), temporal_precision=row.get("temporal_precision"), derived_from=[row.get("relation_id")])
    for relation in inputs["relations"]:
        evidence_ids = list(relation.get("evidence_ids", []))
        for derived_id in relation.get("derived_from_relation_ids", []):
            evidence_ids.extend(relation_by_id.get(str(derived_id), {}).get("evidence_ids", []))
        add("relation", relation["id"], subject_ids=[relation.get("subject_id"), relation.get("object_id")], evidence_ids=evidence_ids, review_status=relation.get("review_status", "candidate"), assertion_status=relation.get("assertion_status", "attested"), source_path=str(RELATIONS_PATH), temporal_precision=relation.get("time", {}).get("status") if isinstance(relation.get("time"), Mapping) else None, derived_from=relation.get("derived_from_relation_ids", []))
    for anchor in inputs["anchors"]:
        add("story_temporal_anchor", anchor["anchor_id"], subject_ids=[anchor.get("story_id")], evidence_ids=anchor.get("evidence_ids", []), review_status=anchor.get("review_status", "candidate"), assertion_status=anchor.get("assertion_status", "inferred"), source_path=str(ANCHORS_PATH), temporal_precision=anchor.get("precision"))
    return {
        "schema": 1,
        "stage": "h0c-historical-facts",
        "fact_index": sorted(facts.values(), key=lambda x: x["fact_key"]),
        "fact_count": len(facts),
        "source_layers": [str(H0B1_BACKBONE_PATH), str(ANCHORS_PATH), str(ACTIVITY_PATH), str(RELATIONS_PATH), str(OUTPUTS["participant_freeze"])],
        "policy": "Canonical facts remain in their existing H0A/H0B/Relation layers; this index provides stable traceable references for H0C projections.",
    }


def time_from_anchor(anchor: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "start_year_ce": anchor.get("start_year_ce"),
        "end_year_ce": anchor.get("end_year_ce"),
        "precision": anchor.get("precision", "unknown"),
        "basis": "h0a_story_temporal_anchor",
        "anchor_id": anchor.get("anchor_id"),
    }


def build_graph(inputs: Mapping[str, Any], participant_freeze: Mapping[str, Any], locations: Mapping[str, Any], regimes: Mapping[str, Any], offices: Mapping[str, Any], events: Mapping[str, Any], activities: Mapping[str, Any], event_participations: Mapping[str, Any], location_facts: Mapping[str, Any], service_contexts: Mapping[str, Any], historical_facts: Mapping[str, Any]) -> dict[str, Any]:
    nodes: dict[tuple[str, str], dict[str, Any]] = {}
    edges: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    anchors = {str(row["story_id"]): row for row in inputs["anchors"]}
    facts_by_key = {row["fact_key"]: row for row in historical_facts["fact_index"]}
    evidence_by_id = inputs["evidence_by_id"]
    relation_by_id = {str(row["id"]): row for row in inputs["relations"]}

    def add_node(node_type: str, node_id: object, label: object, evidence_ids: Iterable[object] = (), review_status: str = "candidate", assertion_status: str = "derived") -> None:
        key = (node_type, str(node_id))
        existing = nodes.get(key)
        if existing is None:
            nodes[key] = {
                "node_id": str(node_id),
                "node_type": node_type,
                "label": str(label),
                "canonical_reference": f"{node_type}:{node_id}",
                "evidence_ids": unique(evidence_ids),
                "review_status": review_status,
                "assertion_status": assertion_status,
            }
        else:
            existing["evidence_ids"] = unique([*existing["evidence_ids"], *evidence_ids])

    def add_edge(edge_type: str, source_type: str, source_id: object, target_type: str, target_id: object, source_facts: Iterable[tuple[str, object]], evidence_ids: Iterable[object], *, provenance_refs: Iterable[object] = (), temporal: Mapping[str, Any] | None = None, relation_ids: Iterable[object] = (), derivation_basis: str = "canonical_fact_projection") -> None:
        source_id, target_id = str(source_id), str(target_id)
        fact_refs = [{"fact_type": fact_type, "fact_id": str(fact_id), "fact_key": fact_key(fact_type, str(fact_id))} for fact_type, fact_id in sorted(set((str(a), str(b)) for a, b in source_facts))]
        relation_id_list = unique(relation_ids)
        key = (edge_type, source_type, source_id, target_type, target_id)
        current = edges.get(key)
        if current is None:
            current = {
                "edge_id": stable_id("edge-h0c", edge_type, source_type, source_id, target_type, target_id),
                "edge_type": edge_type,
                "source": {"node_type": source_type, "node_id": source_id},
                "target": {"node_type": target_type, "node_id": target_id},
                "source_facts": fact_refs,
                "fact_ids": sorted({ref["fact_id"] for ref in fact_refs}),
                "relation_ids": relation_id_list,
                "evidence_ids": unique(evidence_ids),
                "provenance_refs": unique(provenance_refs),
                "temporal": dict(temporal or {"start_year_ce": None, "end_year_ce": None, "precision": "unknown", "basis": "not_temporally_bounded"}),
                "derivation_basis": derivation_basis,
                "review_status": "derived",
                "assertion_status": "derived",
                "uncertainty_state": "derived",
                "edge_status": "materialized",
            }
            edges[key] = current
        else:
            current["source_facts"] = sorted({(x["fact_type"], x["fact_id"], x["fact_key"]): x for x in [*current["source_facts"], *fact_refs]}.values(), key=lambda x: x["fact_key"])
            current["fact_ids"] = sorted({x["fact_id"] for x in current["source_facts"]})
            current["relation_ids"] = unique([*current["relation_ids"], *relation_id_list])
            current["evidence_ids"] = unique([*current["evidence_ids"], *evidence_ids])
            current["provenance_refs"] = unique([*current.get("provenance_refs", []), *provenance_refs])
            if current["temporal"].get("precision") == "unknown" and temporal and temporal.get("precision") != "unknown":
                current["temporal"] = dict(temporal)
        if not current["source_facts"] or not (current["evidence_ids"] or current.get("provenance_refs")):
            current["edge_status"] = "unsupported_evidence"
        elif any(ref["fact_key"] not in facts_by_key for ref in current["source_facts"]):
            current["edge_status"] = "dangling_fact_reference"
        source_statuses = [facts_by_key[ref["fact_key"]].get("review_status") for ref in current["source_facts"] if ref["fact_key"] in facts_by_key]
        if source_statuses and all(status == "reviewed" for status in source_statuses):
            current["review_status"] = "reviewed"
            current["uncertainty_state"] = "reviewed"
        elif any(status in {"conflicted", "rejected"} for status in source_statuses):
            current["review_status"] = "candidate"
            current["uncertainty_state"] = "conflicted"
        elif any(status == "candidate" for status in source_statuses):
            current["review_status"] = "candidate"
            current["uncertainty_state"] = "candidate"

    # Nodes from the protected production registries.
    for person in inputs["people"]:
        person_id = str(person.get("id", person.get("person_id")))
        add_node("Person", person_id, person.get("canonical_name"), person.get("source_evidence", []), person.get("review_status", "candidate"), person.get("assertion_status", "attested"))
    for story in inputs["stories"]:
        add_node("Story", story["id"], story.get("title") or story["id"], story.get("evidence_ids", []), story.get("review_status", "candidate"), story.get("assertion_status", "attested"))
    for row in locations["records"]:
        add_node("Location", row["location_id"], row["canonical_name"], row.get("evidence_ids", []), row.get("review_status", "candidate"), row.get("assertion_status", "derived"))
    for row in regimes["records"]:
        add_node("Regime", row["regime_id"], row["canonical_name"], row.get("evidence_ids", []), row.get("review_status", "candidate"), row.get("assertion_status", "derived"))
    for row in offices["entities"]:
        add_node("Office", row["office_id"], row["canonical_name"], row.get("evidence_ids", []), row.get("review_status", "candidate"), row.get("assertion_status", "derived"))
    for row in events["records"]:
        add_node("Event", row["event_id"], row["canonical_name"], row.get("evidence_ids", []), row.get("review_status", "candidate"), row.get("assertion_status", "attested"))
    for row in inputs["backbone"].get("clans", []):
        add_node("Clan", row["clan_id"], row.get("canonical_name"), row.get("evidence_ids", []), row.get("review_status", "candidate"), row.get("assertion_status", "attested"))

    # Story associations and the frozen semantic participation layer.
    person_story_provenance = mention_provenance(inputs)
    for link in records(inputs["person_story"], "links"):
        if str(link.get("entry_id")) not in inputs["story_by_id"]:
            continue
        story_id, person_id = str(link["entry_id"]), str(link["person_id"])
        evidence_ids = list(link.get("evidence_ids", []))
        provenance_refs: list[str] = []
        for mention in person_story_provenance.get((story_id, person_id), []):
            evidence_ids.extend(mention.get("evidence_ids", []))
            provenance_refs.extend(mention.get("provenance_refs", []))
        add_edge("person_story_link", "Person", person_id, "Story", story_id, [("person_story_link", link["id"])], evidence_ids, provenance_refs=provenance_refs, temporal=time_from_anchor(anchors.get(story_id, {})), derivation_basis="person_story_index")
    for row in participant_freeze["records"]:
        temporal = time_from_anchor(anchors.get(str(row["story_id"]), {}))
        edge_type = f"story_participant_{row['role']}"
        participant_facts = [("story_participant", row["participant_id"])]
        anchor = anchors.get(row["story_id"])
        if anchor:
            participant_facts.append(("story_temporal_anchor", anchor["anchor_id"]))
        add_edge(edge_type, "Person", row["person_id"], "Story", row["story_id"], participant_facts, row.get("evidence_ids", []), provenance_refs=row.get("provenance_refs", []), temporal=temporal, derivation_basis="h0c_participant_freeze")

    relation_attached: set[str] = set()
    family_rows = inputs["backbone"]
    for row in family_rows.get("clan_memberships", []):
        add_edge("member_of_clan", "Person", row["person_id"], "Clan", row["clan_id"], [("clan_membership", row["membership_id"])], row.get("evidence_ids", []), derivation_basis="clan_membership_fact")
    for row in family_rows.get("kinship", []):
        kin_type = str(row.get("kinship_type", "kinship"))
        edge_type = "parent_of" if kin_type == "parent_child" and row.get("direction") == "person_a_to_person_b" else f"kinship_{kin_type}"
        relation_ids = row.get("compatibility_relation_ids", [])
        relation_attached.update(str(value) for value in relation_ids)
        evidence_ids = list(row.get("evidence_ids", []))
        for relation_id in relation_ids:
            relation = relation_by_id.get(str(relation_id), {})
            evidence_ids.extend(relation.get("evidence_ids", []))
            for derived_id in relation.get("derived_from_relation_ids", []):
                evidence_ids.extend(relation_by_id.get(str(derived_id), {}).get("evidence_ids", []))
        add_edge(edge_type, "Person", row["person_a_id"], "Person", row["person_b_id"], [("kinship", row["kinship_id"])] + [("relation", value) for value in relation_ids], evidence_ids, relation_ids=relation_ids, derivation_basis="kinship_fact")
    for row in family_rows.get("marriages", []):
        relation_ids = row.get("compatibility_relation_ids", [])
        relation_attached.update(str(value) for value in relation_ids)
        evidence_ids = list(row.get("evidence_ids", []))
        for relation_id in relation_ids:
            evidence_ids.extend(relation_by_id.get(str(relation_id), {}).get("evidence_ids", []))
        add_edge("spouse_union", "Person", row["spouse_a_id"], "Person", row["spouse_b_id"], [("marriage", row["marriage_id"])] + [("relation", value) for value in relation_ids], evidence_ids, relation_ids=relation_ids, temporal={"start_year_ce": row.get("start_year_ce"), "end_year_ce": row.get("end_year_ce"), "precision": row.get("temporal_status", "unknown"), "basis": "marriage_union"}, derivation_basis="marriage_union_fact")

    for row in offices["tenures"]:
        temporal = {"start_year_ce": row.get("start_year_ce"), "end_year_ce": row.get("end_year_ce"), "precision": row.get("temporal_precision", "unknown"), "basis": "office_tenure"}
        add_edge("held_office", "Person", row["person_id"], "Office", row["office_id"], [("office_tenure", row["tenure_id"])], row.get("evidence_ids", []), temporal=temporal, derivation_basis="office_tenure_fact")
        if row.get("location_id"):
            add_edge("office_at_location", "Office", row["office_id"], "Location", row["location_id"], [("office_tenure", row["tenure_id"])], row.get("evidence_ids", []), temporal=temporal, derivation_basis="office_tenure_location")
        if row.get("regime_id"):
            add_edge("office_in_regime", "Office", row["office_id"], "Regime", row["regime_id"], [("office_tenure", row["tenure_id"])], row.get("evidence_ids", []), temporal=temporal, derivation_basis="office_tenure_polity")
    for row in activities["records"]:
        if row.get("event_id"):
            add_edge("activity_context_event", "Person", row["person_id"], "Event", row["event_id"], [("person_activity", row["activity_id"])], row.get("evidence_ids", []), temporal={"start_year_ce": row.get("start_year_ce"), "end_year_ce": row.get("end_year_ce"), "precision": row.get("precision", "unknown"), "basis": "person_activity"}, derivation_basis="person_activity_fact")
        for location_id in row.get("location_ids", []):
            add_edge("active_at_location", "Person", row["person_id"], "Location", location_id, [("person_activity", row["activity_id"])], row.get("evidence_ids", []), temporal={"start_year_ce": row.get("start_year_ce"), "end_year_ce": row.get("end_year_ce"), "precision": row.get("precision", "unknown"), "basis": "person_activity"}, derivation_basis="person_activity_location")
    for row in event_participations["records"]:
        edge_type = "participated_in_event" if row.get("hard_temporal_eligible") else "event_context_reference"
        add_edge(edge_type, "Person", row["person_id"], "Event", row["event_id"], [("event_participation", row["event_participation_id"]), ("person_activity", row["source_activity_id"])], row.get("evidence_ids", []), temporal={"start_year_ce": row.get("start_year_ce"), "end_year_ce": row.get("end_year_ce"), "precision": row.get("temporal_precision", "unknown"), "basis": "event_participation" if row.get("hard_temporal_eligible") else "story_event_reference"}, derivation_basis="event_participation_fact")
    for row in location_facts["records"]:
        if row["subject_type"] == "person":
            add_edge(row["location_role"], "Person", row["subject_id"], "Location", row["location_id"], [("location_fact", row["location_fact_id"])], row.get("evidence_ids", []), temporal={"start_year_ce": row.get("start_year_ce"), "end_year_ce": row.get("end_year_ce"), "precision": row.get("temporal_precision", "unknown"), "basis": row.get("location_role")}, derivation_basis="location_fact")
        elif row["subject_type"] == "story":
            add_edge("story_present_at", "Story", row["subject_id"], "Location", row["location_id"], [("location_fact", row["location_fact_id"])], row.get("evidence_ids", []), derivation_basis="scene_context_location_fact")
    for event in events["records"]:
        event_temporal = {"start_year_ce": event.get("start_year_ce"), "end_year_ce": event.get("end_year_ce"), "precision": event.get("temporal_precision", "unknown"), "basis": "historical_event"}
        for claim in event.get("source_claims", []):
            story_id = claim.get("story_id")
            if not story_id:
                continue
            claim_id = stable_id("event-story-context-h0c", event["event_id"], story_id, claim.get("surface"))
            add_edge("event_contextualizes_story", "Event", event["event_id"], "Story", story_id, [("event_story_context", claim_id), ("event", event["event_id"])], claim.get("evidence_ids", []), temporal=event_temporal, derivation_basis="historical_event_source_claim")
    for row in service_contexts["records"]:
        edge_type = "served_under" if row["context_type"] == "service_under" else "political_context"
        add_edge(edge_type, "Person", row["person_a_id"], "Person", row["person_b_id"], [("service_political", row["service_context_fact_id"]), ("relation", row["relation_id"])], row.get("evidence_ids", []), temporal={"start_year_ce": row.get("start_year_ce"), "end_year_ce": row.get("end_year_ce"), "precision": row.get("temporal_precision", "unknown"), "basis": "relation_temporal_context"}, relation_ids=[row["relation_id"]], derivation_basis="existing_relation_context")
        relation_attached.add(str(row["relation_id"]))

    for relation in inputs["relations"]:
        relation_id = str(relation["id"])
        if relation_id in relation_attached:
            continue
        relation_type = str(relation.get("relation_type", "relation"))
        evidence_ids = list(relation.get("evidence_ids", []))
        for derived_id in relation.get("derived_from_relation_ids", []):
            evidence_ids.extend(relation_by_id.get(str(derived_id), {}).get("evidence_ids", []))
        add_edge(f"relation_{relation_type}", "Person", relation["subject_id"], "Person", relation["object_id"], [("relation", relation_id)], evidence_ids, relation_ids=[relation_id], derivation_basis="existing_relation_projection")

    return {
        "schema": 1,
        "stage": "h0c-graph-projection",
        "node_type_catalog": ["Person", "Story", "Location", "Event", "Office", "Clan", "Regime"],
        "edge_type_catalog": sorted({edge["edge_type"] for edge in edges.values()}),
        "nodes": sorted(nodes.values(), key=lambda x: (x["node_type"], x["node_id"])),
        "edges": sorted(edges.values(), key=lambda x: x["edge_id"]),
        "node_counts": dict(sorted(Counter(node["node_type"] for node in nodes.values()).items())),
        "edge_counts": dict(sorted(Counter(edge["edge_type"] for edge in edges.values()).items())),
        "policy": "Graph edges are derived projections. Canonical facts and Evidence remain authoritative; missing edges are not negative facts.",
    }


def build_graph_audit(inputs: Mapping[str, Any], graph: Mapping[str, Any], historical_facts: Mapping[str, Any], constraints: Mapping[str, Any], aliases: list[dict[str, Any]]) -> dict[str, Any]:
    node_keys = {(node["node_type"], node["node_id"]) for node in graph["nodes"]}
    fact_keys = {row["fact_key"] for row in historical_facts["fact_index"]}
    dangling_edges = []
    unsupported_edges = []
    dangling_facts = []
    for edge in graph["edges"]:
        source = (edge["source"]["node_type"], edge["source"]["node_id"])
        target = (edge["target"]["node_type"], edge["target"]["node_id"])
        if source not in node_keys or target not in node_keys:
            dangling_edges.append(edge["edge_id"])
        if edge.get("edge_status") == "unsupported_evidence":
            unsupported_edges.append(edge["edge_id"])
        for fact in edge.get("source_facts", []):
            if fact["fact_key"] not in fact_keys:
                dangling_facts.append({"edge_id": edge["edge_id"], "fact_key": fact["fact_key"]})
    incident = Counter()
    for edge in graph["edges"]:
        incident[(edge["source"]["node_type"], edge["source"]["node_id"])] += 1
        incident[(edge["target"]["node_type"], edge["target"]["node_id"])] += 1
    orphan_nodes = [
        f"{node['node_type']}:{node['node_id']}"
        for node in graph["nodes"]
        if incident[(node["node_type"], node["node_id"])] == 0
    ]
    semantic_groups: dict[tuple[str, str, str, str, str], list[str]] = defaultdict(list)
    for edge in graph["edges"]:
        semantic_type = edge["edge_type"]
        if semantic_type.startswith("relation_"):
            semantic_type = semantic_type.replace("relation_", "", 1)
        semantic_groups[(semantic_type, edge["source"]["node_type"], edge["source"]["node_id"], edge["target"]["node_type"], edge["target"]["node_id"])].append(edge["edge_id"])
    duplicate_groups = [
        {"semantic_key": list(key), "edge_ids": sorted(ids)}
        for key, ids in sorted(semantic_groups.items())
        if len(ids) > 1
    ]
    parent_edges = [(edge["source"]["node_id"], edge["target"]["node_id"]) for edge in graph["edges"] if edge["edge_type"] == "parent_of"]
    parent_graph: dict[str, list[str]] = defaultdict(list)
    for source, target in parent_edges:
        parent_graph[source].append(target)
    visiting: set[str] = set()
    visited: set[str] = set()
    cycles: list[list[str]] = []

    def visit(node: str, path: list[str]) -> None:
        if node in visiting:
            cycles.append(path[path.index(node):] + [node])
            return
        if node in visited:
            return
        visiting.add(node)
        for child in sorted(parent_graph.get(node, [])):
            visit(child, [*path, child])
        visiting.remove(node)
        visited.add(node)

    for node in sorted(parent_graph):
        visit(node, [node])
    identity_collisions = []
    for alias in aliases:
        targets = unique([*alias.get("person_ids", []), *alias.get("resolved_person_ids", [])])
        if len(targets) > 1:
            identity_collisions.append({"alias_id": alias.get("alias_id"), "surface": alias.get("surface"), "person_ids": targets})
    temporal_conflicts = [str(row.get("story_id")) for row in constraints.get("records", []) if row.get("conflict_flags")]
    issues = {
        "orphan_nodes": sorted(orphan_nodes),
        "dangling_edges": sorted(dangling_edges),
        "dangling_fact_references": sorted(dangling_facts, key=lambda x: (x["edge_id"], x["fact_key"])),
        "unsupported_edges": sorted(unsupported_edges),
        "duplicate_semantic_edges": duplicate_groups,
        "family_cycle_anomalies": cycles,
        "temporal_conflicts": sorted(temporal_conflicts),
        "identity_collision_surfaces": sorted(identity_collisions, key=lambda x: str(x.get("alias_id"))),
    }
    return {
        "schema": 1,
        "stage": "h0c-graph-audit",
        "issues": issues,
        "scope": {
            "production_story_count": len(inputs["stories"]),
            "person_story_links_in_production_scope": sum(str(link.get("entry_id")) in inputs["story_by_id"] for link in records(inputs["person_story"], "links")),
            "person_story_links_out_of_production_scope": sum(str(link.get("entry_id")) not in inputs["story_by_id"] for link in records(inputs["person_story"], "links")),
        },
        "issue_counts": {
            "orphan_nodes": len(orphan_nodes),
            "dangling_edges": len(dangling_edges),
            "dangling_fact_references": len(dangling_facts),
            "unsupported_edges": len(unsupported_edges),
            "duplicate_semantic_edges": len(duplicate_groups),
            "family_cycle_anomalies": len(cycles),
            "temporal_conflicts": len(temporal_conflicts),
            "identity_collision_surfaces": len(identity_collisions),
        },
        "policy": "Audits preserve anomalies and conflicts; they do not repair canonical facts or turn missing edges into negative facts.",
    }


def dimension_state(count: int, *, candidate_only: bool = False, conflicted: bool = False) -> str:
    if conflicted:
        return "conflicted"
    if count <= 0:
        return "unknown"
    if candidate_only:
        return "candidate_only"
    return "available"


def build_readiness(inputs: Mapping[str, Any], participant_freeze: Mapping[str, Any], activities: Mapping[str, Any], event_participations: Mapping[str, Any], location_facts: Mapping[str, Any], service_contexts: Mapping[str, Any], graph: Mapping[str, Any]) -> dict[str, Any]:
    people = inputs["people_by_id"]
    hard_by_person = Counter(str(row["person_id"]) for row in participant_freeze["records"] if row["hard_temporal_eligible"])
    contextual_by_person = Counter(str(row["person_id"]) for row in participant_freeze["records"] if not row["hard_temporal_eligible"])
    activity_by_person = Counter(str(row["person_id"]) for row in activities["records"])
    event_by_person = Counter(str(row["person_id"]) for row in event_participations["records"] if row.get("hard_temporal_eligible"))
    event_context_by_person = Counter(str(row["person_id"]) for row in event_participations["records"] if not row.get("hard_temporal_eligible"))
    location_by_person = Counter(str(row["subject_id"]) for row in location_facts["records"] if row["subject_type"] == "person")
    service_by_person = Counter(str(person_id) for row in service_contexts["records"] for person_id in (row.get("person_a_id"), row.get("person_b_id")) if person_id)
    relation_by_person = Counter()
    for edge in graph["edges"]:
        if edge["edge_type"].startswith("relation_") or edge["edge_type"] in {"served_under", "political_context"}:
            relation_by_person[edge["source"]["node_id"]] += 1
            relation_by_person[edge["target"]["node_id"]] += 1
    family_counts: Counter[str] = Counter()
    for family, key_a, key_b in (("clan_memberships", "person_id", None), ("kinship", "person_a_id", "person_b_id"), ("marriages", "spouse_a_id", "spouse_b_id")):
        for row in inputs["backbone"].get(family, []):
            for person_id in (row.get(key_a), row.get(key_b)) if key_b else (row.get(key_a),):
                if person_id:
                    family_counts[str(person_id)] += 1
    office_by_person = Counter(str(row.get("person_id")) for row in inputs["backbone"].get("office_tenures", []) if row.get("person_id"))
    dimensions = ("story_participation", "temporal_footprint", "geographic_footprint", "family", "clan", "office_history", "event_participation", "service_political_context", "relation_neighborhood", "evidence_traceability")
    rows = []
    for person_id in sorted(people):
        family_count = family_counts[person_id]
        clan_count = sum(str(row.get("person_id")) == person_id for row in inputs["backbone"].get("clan_memberships", []))
        edge_count = sum(person_id in {edge["source"]["node_id"], edge["target"]["node_id"]} for edge in graph["edges"])
        source_facts = [fact for fact in read_json(OUTPUTS["historical_facts"])["fact_index"] if person_id in fact.get("subject_ids", [])]
        traceable = sum(bool(fact.get("evidence_ids")) for fact in source_facts)
        row = {
            "person_id": person_id,
            "canonical_name": people[person_id].get("canonical_name"),
            "dimensions": {
                "story_participation": {"state": dimension_state(hard_by_person[person_id]) if hard_by_person[person_id] else ("partial" if contextual_by_person[person_id] else "unknown"), "hard_story_count": hard_by_person[person_id], "contextual_story_count": contextual_by_person[person_id]},
                "temporal_footprint": {"state": dimension_state(activity_by_person[person_id], candidate_only=activity_by_person[person_id] > 0), "activity_count": activity_by_person[person_id]},
                "geographic_footprint": {"state": dimension_state(location_by_person[person_id], candidate_only=location_by_person[person_id] > 0), "location_fact_count": location_by_person[person_id]},
                "family": {"state": dimension_state(family_count, candidate_only=family_count > 0), "fact_count": family_count},
                "clan": {"state": dimension_state(clan_count, candidate_only=clan_count > 0), "membership_count": clan_count},
                "office_history": {"state": dimension_state(office_by_person[person_id], candidate_only=office_by_person[person_id] > 0), "tenure_count": office_by_person[person_id]},
                "event_participation": {"state": dimension_state(event_by_person[person_id], candidate_only=event_by_person[person_id] > 0) if event_by_person[person_id] else ("partial" if event_context_by_person[person_id] else "unknown"), "event_participation_count": event_by_person[person_id], "event_context_reference_count": event_context_by_person[person_id]},
                "service_political_context": {"state": dimension_state(service_by_person[person_id]), "fact_count": service_by_person[person_id]},
                "relation_neighborhood": {"state": dimension_state(relation_by_person[person_id]), "edge_count": relation_by_person[person_id]},
                "evidence_traceability": {"state": "available" if source_facts and traceable == len(source_facts) else ("partial" if traceable else "unknown"), "fact_count": len(source_facts), "traceable_fact_count": traceable},
            },
            "graph_incident_edge_count": edge_count,
        }
        rows.append(row)
    state_counts = {dimension: dict(sorted(Counter(row["dimensions"][dimension]["state"] for row in rows).items())) for dimension in dimensions}
    return {
        "schema": 1,
        "stage": "h0c-ml-readiness",
        "contract": {
            "framework_neutral": True,
            "node_fields": ["node_id", "node_type", "label", "canonical_reference", "evidence_ids", "review_status", "assertion_status"],
            "edge_fields": ["edge_id", "edge_type", "source", "target", "source_facts", "evidence_ids", "provenance_refs", "review_status", "assertion_status", "uncertainty_state", "temporal", "edge_status"],
            "temporal_fields": ["start_year_ce", "end_year_ce", "precision", "basis"],
            "uncertainty_states": ["reviewed", "candidate", "unknown", "uncertain", "conflicted", "derived"],
            "missing_edge_policy": "missing edge is unknown, not negative evidence",
            "negative_fact_policy": "no artificial negative facts are generated",
            "model_artifacts_generated": False,
            "embeddings_generated": False,
            "training_split_generated": False,
        },
        "dimension_catalog": list(dimensions),
        "person_records": rows,
        "state_counts_by_dimension": state_counts,
        "notes": "This is a coverage/readiness audit only; it does not calculate embeddings, centrality, historical importance, clusters, or learned signatures.",
    }


def build_gaps(inputs: Mapping[str, Any], participant_freeze: Mapping[str, Any], locations: Mapping[str, Any], offices: Mapping[str, Any], events: Mapping[str, Any], graph_audit: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    for gap in inputs["h0b1_gaps"].get("records", []):
        category = str(gap.get("category"))
        status = "resolved_by_h0c_participant_freeze" if category == "participant_role_uncertain" else "carried_forward"
        rows.append({
            "gap_id": stable_id("h0c-gap", gap.get("gap_id")),
            "source_gap_id": gap.get("gap_id"),
            "category": category,
            "status": status,
            "affected_person_ids": sorted(gap.get("affected_person_ids", [])),
            "affected_story_ids": sorted(gap.get("affected_story_ids", [])),
            "evidence_ids": unique(gap.get("evidence_ids", [])),
            "why_it_matters": gap.get("why_it_matters"),
            "future_relevance": gap.get("future_relevance"),
            "resolution": "Role is now explicitly frozen as hard/contextual with provenance." if status.startswith("resolved") else "Retained from H0B-1; H0C does not invent an endpoint or chronology.",
        })
    for tenure in offices["tenures"]:
        if not tenure.get("location_id") and not tenure.get("jurisdiction_location_id"):
            rows.append({
                "gap_id": stable_id("h0c-gap", "office-location", tenure["tenure_id"]),
                "category": "location_not_normalized",
                "status": "open",
                "affected_person_ids": [str(tenure.get("person_id"))],
                "affected_story_ids": [],
                "evidence_ids": unique(tenure.get("evidence_ids", [])),
                "why_it_matters": "The source-backed OfficeTenure has no explicit location field to normalize.",
                "future_relevance": "geographic_context",
            })
    for event in events["records"]:
        if not event.get("location_ids"):
            rows.append({
                "gap_id": stable_id("h0c-gap", "event-location", event["event_id"]),
                "category": "event_location_unresolved",
                "status": "open",
                "affected_person_ids": [],
                "affected_story_ids": sorted(event.get("linked_story_ids", [])),
                "evidence_ids": unique(event.get("evidence_ids", [])),
                "why_it_matters": "The event is normalized and chronologically evidenced, but no local event-place assertion is materialized.",
                "future_relevance": "geographic_context",
            })
    for node in graph_audit["issues"].get("orphan_nodes", []):
        node_type, _, node_id = node.partition(":")
        rows.append({
            "gap_id": stable_id("h0c-gap", "orphan-node", node),
            "category": "graph_orphan_node",
            "status": "open",
            "affected_person_ids": [node_id] if node_type == "Person" else [],
            "affected_story_ids": [node_id] if node_type == "Story" else [],
            "evidence_ids": [],
            "why_it_matters": "The protected entity is not connected by a materialized H0C graph edge; absence is not treated as a negative historical fact.",
            "future_relevance": "historical_graph_sufficiency",
        })
    for edge_id in graph_audit["issues"].get("unsupported_edges", []):
        rows.append({
            "gap_id": stable_id("h0c-gap", "unsupported-edge", edge_id),
            "category": "graph_unsupported_edge",
            "status": "open",
            "affected_person_ids": [],
            "affected_story_ids": [],
            "evidence_ids": [],
            "why_it_matters": f"Graph edge {edge_id} lacks a complete Evidence trace and is not treated as a valid historical edge.",
            "future_relevance": "historical_graph_sufficiency",
        })
    return {
        "schema": 1,
        "stage": "h0c-historical-gap-audit",
        "category_catalog": list(H0C_GAP_CATEGORIES),
        "records": sorted(rows, key=lambda x: x["gap_id"]),
        "summary": {
            "gap_count": len(rows),
            "by_category": {category: sum(row["category"] == category for row in rows) for category in H0C_GAP_CATEGORIES},
            "open_count": sum(row["status"] == "open" for row in rows),
            "resolved_by_participant_freeze": sum(row["status"] == "resolved_by_h0c_participant_freeze" for row in rows),
        },
        "policy": "Gaps preserve missingness and conflicts; no missing endpoint or missing edge is materialized as a negative fact.",
    }


def build_protection(inputs: Mapping[str, Any], participant_freeze: Mapping[str, Any]) -> dict[str, Any]:
    protected_paths = {
        "people": PEOPLE_PATH,
        "aliases": ALIASES_PATH,
        "shishuo_mentions": SHISHUO_MENTIONS_PATH,
        "jinshu_mentions": JINSHU_MENTIONS_PATH,
        "person_story": PERSON_STORY_PATH,
        "sc1_site": SC1_PATH,
        "h0a_anchors": ANCHORS_PATH,
        "h0b1_participants": H0B1_PARTICIPANTS_PATH,
        "h0b1_backbone": H0B1_BACKBONE_PATH,
        "h0b1_constraints": H0B1_CONSTRAINTS_PATH,
        "effective_mentions": EFFECTIVE_MENTIONS_PATH,
        "identity_candidates": PERSON_IDENTITY_CANDIDATES_PATH,
        "entity_id_manifest": ENTITY_ID_MANIFEST_PATH,
    }
    return {
        "schema": 1,
        "stage": "h0c-protection-manifest",
        "baseline_commit": BASELINE_COMMIT,
        "protected_counts": {
            "production_person_count": len(inputs["people"]),
            "production_story_count": len(inputs["stories"]),
            "person_story_link_count": len(records(inputs["person_story"], "links")),
            "reviewed_person_story_link_count": int(inputs["person_story"].get("reviewed_link_count", 0)),
            "reviewed_relation_count": len(inputs["relations"]),
            "scene_context_count": len(inputs["scene"].get("contexts", {})),
            "orphan_mention_count": 0,
            "primary_era_orientation_count": len(inputs["sc1"].get("story_era_orientations", [])),
        },
        "protected_hashes": {name: sha256_file(path) for name, path in protected_paths.items()},
        "source_scope_comparisons": read_json(PROTECTED_HASH_PATH).get("comparisons", {}) if (ROOT / PROTECTED_HASH_PATH).exists() else {},
        "participant_freeze_sha256": participant_freeze["participant_freeze_sha256"],
        "frozen_h0b0_hashes": {name: sha256_file(path) for name, path in H0B0_INPUTS.items()},
        "policy": "H0C reads protected layers and never rewrites them. Later anomalies become gaps or explicit hotfixes, not silent participant changes.",
    }


def build_metrics(inputs: Mapping[str, Any], participant_freeze: Mapping[str, Any], locations: Mapping[str, Any], regimes: Mapping[str, Any], offices: Mapping[str, Any], events: Mapping[str, Any], activities: Mapping[str, Any], event_participations: Mapping[str, Any], location_facts: Mapping[str, Any], service_contexts: Mapping[str, Any], historical_facts: Mapping[str, Any], graph: Mapping[str, Any], graph_audit: Mapping[str, Any], gaps: Mapping[str, Any], readiness: Mapping[str, Any], protection: Mapping[str, Any]) -> dict[str, Any]:
    fact_counts = Counter(row["fact_type"] for row in historical_facts["fact_index"])
    return {
        "schema": 1,
        "stage": "h0c-metrics",
        "scope": {"persons": len(inputs["people"]), "stories": len(inputs["stories"]), "participant_records": participant_freeze["participant_count"]},
        "participant_freeze": {
            "stories_reviewed": len(participant_freeze["story_records"]),
            "participant_records": participant_freeze["participant_count"],
            "hard_participant_records": participant_freeze["hard_participant_count"],
            "role_counts": participant_freeze["role_counts"],
            "reviewed_role_records": participant_freeze["reviewed_role_count"],
            "reviewed_uncertain_count": participant_freeze["reviewed_uncertain_count"],
            "unreviewed_uncertainty_count": participant_freeze["unreviewed_uncertainty_count"],
            "hard_provenance_complete_count": participant_freeze["hard_provenance_complete_count"],
        },
        "entities": {
            "Person": len(inputs["people"]),
            "Story": len(inputs["stories"]),
            "Location": locations["count"],
            "Office": offices["office_count"],
            "Event": events["count"],
            "Clan": len(inputs["backbone"].get("clans", [])),
            "Regime": regimes["count"],
        },
        "facts": {
            "person_activity": activities["count"],
            "office_tenure": offices["tenure_count"],
            "event_participation": event_participations["count"],
            "hard_event_participation": sum(row.get("hard_temporal_eligible") for row in event_participations["records"]),
            "event_context_reference": sum(not row.get("hard_temporal_eligible") for row in event_participations["records"]),
            "location_fact": location_facts["count"],
            "service_political": service_contexts["count"],
            "clan_membership": len(inputs["backbone"].get("clan_memberships", [])),
            "kinship": len(inputs["backbone"].get("kinship", [])),
            "marriage": len(inputs["backbone"].get("marriages", [])),
            "historical_fact_index": historical_facts["fact_count"],
            "fact_index_by_type": dict(sorted(fact_counts.items())),
        },
        "review_status": {
            "participant_reviewed": participant_freeze["reviewed_role_count"],
            "candidate_office_tenures": sum(row.get("review_status") == "candidate" for row in offices["tenures"]),
            "candidate_person_activities": sum(row.get("review_status") == "candidate" for row in activities["records"]),
            "reviewed_service_contexts": sum(row.get("review_status") == "reviewed" for row in service_contexts["records"]),
        },
        "temporal": {
            "office_precision_distribution": dict(sorted(Counter(str(row.get("temporal_precision", "unknown")) for row in offices["tenures"]).items())),
            "activity_precision_distribution": dict(sorted(Counter(str(row.get("precision", "unknown")) for row in activities["records"]).items())),
            "graph_temporal_edge_count": sum(edge.get("temporal", {}).get("precision") != "unknown" for edge in graph["edges"]),
            "h0b1_temporal_conflict_count": sum(bool(row.get("conflict_flags")) for row in inputs["constraints"].get("records", [])),
        },
        "locations": {
            "location_count": locations["count"],
            "location_fact_count": location_facts["count"],
            "modern_mapping_unknown_count": sum(row.get("modern_mapping", {}).get("status") == "unknown" for row in locations["records"]),
            "coordinate_precision_distribution": dict(sorted(Counter(str(row.get("coordinate_precision", "unknown")) for row in locations["records"]).items())),
        },
        "graph": {
            "node_count": len(graph["nodes"]),
            "edge_count": len(graph["edges"]),
            "node_counts": graph["node_counts"],
            "edge_counts": graph["edge_counts"],
            "materialized_edge_count": sum(edge.get("edge_status") == "materialized" for edge in graph["edges"]),
            "audit_issue_counts": graph_audit["issue_counts"],
        },
        "readiness": {"dimension_state_counts": readiness["state_counts_by_dimension"], "model_artifacts_generated": readiness["contract"]["model_artifacts_generated"]},
        "gaps": gaps["summary"],
        "protected": protection["protected_counts"],
        "future_boundary": {"hg0_implemented": False, "ml_implemented": False, "er2_implemented": False},
        "artifact_hashes": {},
    }


def build_outputs(inputs: Mapping[str, Any]) -> dict[str, Any]:
    participant_freeze = build_participant_freeze(inputs)
    locations, regimes, offices, _ = build_locations_regimes_offices(inputs)
    events = build_events(inputs)
    activities = build_activities(inputs, participant_freeze, locations)
    event_participations = build_event_participations(inputs, activities, participant_freeze)
    location_facts = build_location_facts(inputs, offices, locations)
    service_contexts = build_service_contexts(inputs)
    historical_facts = build_fact_index(inputs, participant_freeze, offices, events, activities, event_participations, location_facts, service_contexts)

    write_json(OUTPUTS["participant_freeze"], participant_freeze)
    write_json(OUTPUTS["locations"], locations)
    write_json(OUTPUTS["regimes"], regimes)
    write_json(OUTPUTS["offices"], offices)
    write_json(OUTPUTS["events"], events)
    write_json(OUTPUTS["person_activities"], activities)
    write_json(OUTPUTS["event_participations"], event_participations)
    write_json(OUTPUTS["location_facts"], location_facts)
    write_json(OUTPUTS["service_contexts"], service_contexts)
    write_json(OUTPUTS["historical_facts"], historical_facts)

    graph = build_graph(inputs, participant_freeze, locations, regimes, offices, events, activities, event_participations, location_facts, service_contexts, historical_facts)
    write_json(OUTPUTS["graph"], graph)
    graph_audit = build_graph_audit(inputs, graph, historical_facts, inputs["constraints"], inputs["aliases"])
    write_json(OUTPUTS["graph_audit"], graph_audit)
    gaps = build_gaps(inputs, participant_freeze, locations, offices, events, graph_audit)
    write_json(OUTPUTS["gaps"], gaps)
    readiness = build_readiness(inputs, participant_freeze, activities, event_participations, location_facts, service_contexts, graph)
    write_json(OUTPUTS["readiness"], readiness)
    protection = build_protection(inputs, participant_freeze)
    write_json(OUTPUTS["protection"], protection)
    metrics = build_metrics(inputs, participant_freeze, locations, regimes, offices, events, activities, event_participations, location_facts, service_contexts, historical_facts, graph, graph_audit, gaps, readiness, protection)
    write_json(OUTPUTS["metrics"], metrics)
    metrics["artifact_hashes"] = {key: sha256_file(path) for key, path in OUTPUTS.items() if key != "metrics"}
    metrics["input_hashes"] = {
        "h0b1_participants": sha256_file(H0B1_PARTICIPANTS_PATH),
        "h0b1_backbone": sha256_file(H0B1_BACKBONE_PATH),
        "h0b1_constraints": sha256_file(H0B1_CONSTRAINTS_PATH),
        "h0a_anchors": sha256_file(ANCHORS_PATH),
        "effective_mentions": sha256_file(EFFECTIVE_MENTIONS_PATH),
        "identity_candidates": sha256_file(PERSON_IDENTITY_CANDIDATES_PATH),
        "entity_id_manifest": sha256_file(ENTITY_ID_MANIFEST_PATH),
        "people": sha256_file(PEOPLE_PATH),
        "aliases": sha256_file(ALIASES_PATH),
    }
    write_json(OUTPUTS["metrics"], metrics)
    return {"participant_freeze": participant_freeze, "locations": locations, "regimes": regimes, "offices": offices, "events": events, "activities": activities, "event_participations": event_participations, "location_facts": location_facts, "service_contexts": service_contexts, "historical_facts": historical_facts, "graph": graph, "graph_audit": graph_audit, "gaps": gaps, "readiness": readiness, "protection": protection, "metrics": metrics}


def main() -> int:
    output = build_outputs(load_inputs())
    metrics = output["metrics"]
    print(
        "H0C historical context: "
        f"{metrics['scope']['persons']} Persons, {metrics['scope']['stories']} Stories, "
        f"{metrics['entities']['Location']} Locations, {metrics['entities']['Office']} Offices, "
        f"{metrics['entities']['Event']} Events, {metrics['graph']['edge_count']} graph edges, "
        f"{metrics['graph']['audit_issue_counts']['orphan_nodes']} orphan nodes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
