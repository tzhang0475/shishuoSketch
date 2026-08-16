#!/usr/bin/env python3
"""Build compact, lazy UX1 historical display projections.

UX1 deliberately reads reviewed/attested projections and the retained
scholarly layer only.  It does not expose H0C candidate facts, graph data,
review queues, or the full Jianshu corpus to the browser.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from opencc import OpenCC
except ImportError:  # Keep the optional projection builder usable in shallow CI.
    class OpenCC:  # type: ignore[no-redef]
        _fallback = str.maketrans({
            "長": "长", "從": "从", "陽": "阳", "晉": "晋", "與": "与",
            "為": "为", "縣": "县", "書": "书", "國": "国", "門": "门",
            "會": "会", "東": "东", "學": "学", "時": "时", "後": "后",
            "傳": "传", "親": "亲", "屬": "属", "據": "据", "應": "应",
            "開": "开", "見": "见", "於": "于", "無": "无", "舊": "旧",
            "為": "为", "華": "华", "賢": "贤", "劉": "刘", "謝": "谢",
            "嶠": "峤", "書": "书", "陽": "阳", "陽": "阳", "郡": "郡",
        })

        def __init__(self, _config: str) -> None:
            pass

        def convert(self, value: str) -> str:
            return value.translate(self._fallback)


ROOT = Path(__file__).resolve().parents[1]
SC1_PATH = ROOT / "data/derived/sc1-site.json"
H0C_FACTS_PATH = ROOT / "data/derived/h0c-historical-facts.json"
H0C_OFFICES_PATH = ROOT / "data/derived/h0c-offices.json"
H0C_LOCATIONS_PATH = ROOT / "data/derived/h0c-locations.json"
PARTICIPANT_PATH = ROOT / "data/derived/h0c-participant-freeze.json"
SELECTION_PATH = ROOT / "data/derived/x1-1-selection-manifest.json"
X1_2R_PARTICIPANT_PATH = ROOT / "data/derived/x1-2r-participant-review.json"
X1_2RF_FACT_PATH = ROOT / "data/derived/x1-2rf-materialized-facts.json"
X1_2RF_ASSERTION_PATH = ROOT / "data/derived/x1-2rf-assertion-review.json"
X1_2RF_SCHOLARLY_PATH = ROOT / "data/derived/x1-2rf-scholarly-assertions.json"
X1_2R_CITATION_PATH = ROOT / "data/derived/x1-2r-citation-candidates.json"
OUTPUT_ROOT = ROOT / "site/public/generated/history"
MANIFEST_PATH = OUTPUT_ROOT / "manifest.json"

CONVERTER = OpenCC("t2s")
MAX_EXCERPT = 280
MAX_REFS = 3


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pair(value: Any) -> dict[str, str] | None:
    if value is None:
        return None
    text = str(value)
    return {"original": text, "simplified": CONVERTER.convert(text)}


def nonempty(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def short_text(value: Any) -> str:
    text = "" if value is None else " ".join(str(value).split())
    if len(text) <= MAX_EXCERPT:
        return text
    return text[:MAX_EXCERPT].rstrip() + "…"


def review_ok(record: Mapping[str, Any]) -> bool:
    return record.get("review_status") == "reviewed"


def sorted_unique(values: Iterable[str]) -> list[str]:
    return sorted({value for value in values if nonempty(value)})


def source_locator(record: Mapping[str, Any]) -> str:
    locator = record.get("source_locator") or record.get("locator") or {}
    if not isinstance(locator, Mapping):
        return str(locator)
    bits: list[str] = []
    for key, label in (("epub_file", "EPUB"), ("pdf_page", "PDF p."), ("block_index", "block"), ("spine_index", "spine"), ("tag", "tag")):
        value = locator.get(key)
        if value is not None:
            bits.append(f"{label} {value}")
    return " · ".join(bits)


def x1_evidence_id(assertion_id: str) -> str:
    return f"ux1-{assertion_id}"


def relation_source_label(relation: Mapping[str, Any]) -> str:
    basis = relation.get("relation_basis")
    if basis == "direct":
        return "直接关系"
    if basis == "derived":
        return "关系链推得"
    return "已审阅关系"


def location_role_label(role: Any) -> str:
    return {
        "origin_from": "出自",
        "resident_at": "居于",
        "active_at": "活动于",
        "served_at": "任职于",
        "held_office_at": "任官于",
        "event_at": "事件地点",
        "story_present_at": "故事所在",
    }.get(str(role), str(role) if role else "历史地点")


def person_name(
    people: Mapping[str, Mapping[str, Any]],
    person_display: Mapping[str, Mapping[str, Any]],
    person_id: str,
) -> dict[str, str]:
    display = person_display.get(person_id) or {}
    if isinstance(display.get("name"), Mapping):
        return dict(display["name"])
    person = people.get(person_id) or {}
    return pair(person.get("canonical_name") or person_id) or {"original": person_id, "simplified": person_id}


def make_evidence_from_sc1(
    evidence: Mapping[str, Mapping[str, Any]],
    source_display: Mapping[str, Mapping[str, Any]],
    evidence_id: str,
) -> dict[str, Any] | None:
    item = evidence.get(evidence_id)
    if not item or item.get("review_status") != "reviewed":
        return None
    source = source_display.get(str(item.get("source_id"))) or {}
    source_label = {
        "work": source.get("work") or pair(item.get("source_id")) or {"original": str(item.get("source_id")), "simplified": str(item.get("source_id"))},
        "edition": source.get("edition") or pair("") or {"original": "", "simplified": ""},
    }
    locator = item.get("locator") or {}
    return {
        "schema": 1,
        "projection": "ux1_evidence_detail",
        "evidence_id": evidence_id,
        "source_label": source_label,
        "source_layer": item.get("evidence_type") or "historical_evidence",
        "attribution": None,
        "quoted_source": None,
        "transmission_status": "qualified_source_evidence",
        "locator": " · ".join(filter(None, [locator.get("artifact_path"), locator.get("source_provenance", {}).get("witness_id")])),
        "short_excerpt": pair(short_text(item.get("quote"))) or {"original": "", "simplified": ""},
        "assertion_status": item.get("assertion_status") or "unknown",
        "review_status": "reviewed",
        "kind": "canonical_evidence",
    }


def make_evidence_from_x1(
    assertion: Mapping[str, Any],
    materialized_fact: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_id = x1_evidence_id(str(assertion.get("source_assertion_id") or assertion.get("assertion_id")))
    source_layer = assertion.get("source_layer") or (materialized_fact or {}).get("source_layer") or "jianshu"
    attribution = assertion.get("attribution") or (materialized_fact or {}).get("attribution")
    quoted_source = assertion.get("quoted_source") or (materialized_fact or {}).get("quoted_source")
    excerpt = assertion.get("evidence_excerpt") or assertion.get("quoted_passage") or ""
    return {
        "schema": 1,
        "projection": "ux1_evidence_detail",
        "evidence_id": evidence_id,
        "source_label": pair("《世说新语笺疏》") or {"original": "《世说新语笺疏》", "simplified": "《世说新语笺疏》"},
        "source_layer": source_layer,
        "attribution": attribution,
        "quoted_source": quoted_source,
        "transmission_status": assertion.get("transmission_status") or (materialized_fact or {}).get("transmission_status"),
        "locator": source_locator(assertion) or source_locator(materialized_fact or {}),
        "short_excerpt": pair(short_text(excerpt)) or {"original": "", "simplified": ""},
        "assertion_status": (materialized_fact or {}).get("assertion_status") or assertion.get("modality") or "scholarly_assertion",
        "modality": assertion.get("modality") or (materialized_fact or {}).get("modality"),
        "parent_assertion_modality": (materialized_fact or {}).get("parent_assertion_modality"),
        "review_status": "reviewed",
        "kind": "scholarly_reference" if not materialized_fact else "reviewed_extension_fact_evidence",
    }


def ref_from_evidence(
    record: Mapping[str, Any],
    evidence_id: str,
    kind: str,
) -> dict[str, Any]:
    layer = record.get("source_layer") or record.get("note_layer") or kind
    label = {
        "liu_annotation": "刘注",
        "jianshu_note": "笺疏",
        "collation_note": "校文",
        "citation": "引书",
    }.get(layer, "进一步读")
    if kind == "citation":
        label = "笺疏引书"
    return {
        "evidence_id": evidence_id,
        "label": pair(label),
        "kind": kind,
        "source_layer": layer,
        "attribution": record.get("attribution") or record.get("note_author"),
        "quoted_source": record.get("quoted_source") or record.get("normalized_source"),
        "modality": record.get("modality"),
        "review_status": "reviewed" if kind != "citation" else "research_only",
    }


def trim_refs(refs: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for ref in refs:
        evidence_id = str(ref.get("evidence_id"))
        if not evidence_id or evidence_id in seen:
            continue
        seen.add(evidence_id)
        output.append(dict(ref))
        if len(output) >= MAX_REFS:
            break
    return output


def build() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    sc1 = read_json(SC1_PATH)
    h0c_facts = read_json(H0C_FACTS_PATH).get("fact_index", [])
    h0c_offices = read_json(H0C_OFFICES_PATH).get("entities", [])
    h0c_locations = read_json(H0C_LOCATIONS_PATH).get("records", [])
    participant_freeze = read_json(PARTICIPANT_PATH).get("records", [])
    selection = read_json(SELECTION_PATH)
    x1_participants = read_json(X1_2R_PARTICIPANT_PATH).get("records", [])
    x1_fact_document = read_json(X1_2RF_FACT_PATH)
    x1_facts = x1_fact_document.get("facts", x1_fact_document.get("records", []))
    x1_assertions = read_json(X1_2RF_ASSERTION_PATH).get("records", [])
    x1_scholarly = read_json(X1_2RF_SCHOLARLY_PATH).get("records", [])
    citations = read_json(X1_2R_CITATION_PATH).get("records", [])

    people = {str(row["id"]): row for row in sc1.get("people", [])}
    stories = {str(row["id"]): row for row in sc1.get("stories", [])}
    evidence = {str(row["id"]): row for row in sc1.get("evidence", [])}
    source_display = sc1.get("display", {}).get("sources", {})
    person_display = sc1.get("display", {}).get("people", {})
    relations = [row for row in sc1.get("relations", []) if review_ok(row)]
    relation_by_id = {str(row["id"]): row for row in relations}
    office_by_id = {str(row["office_id"]): row for row in h0c_offices}
    location_by_id = {str(row["location_id"]): row for row in h0c_locations}
    selected_story_ids = sorted(str(row["story_id"]) for row in selection.get("records", []))
    selected_story_set = set(selected_story_ids)
    published_story_ids = sorted(stories)

    assertion_by_id: dict[str, Mapping[str, Any]] = {}
    assertion_by_source_id: dict[str, Mapping[str, Any]] = {}
    for row in x1_assertions:
        if row.get("source_assertion_id"):
            assertion_by_source_id[str(row["source_assertion_id"])] = row
        if row.get("review_item_id"):
            assertion_by_id[str(row["review_item_id"])] = row
    scholarly_by_story: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in x1_scholarly:
        story_id = row.get("story_id")
        if story_id in selected_story_set:
            scholarly_by_story[str(story_id)].append(row)
    citation_by_story: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in citations:
        story_id = row.get("story_id")
        if story_id in selected_story_set:
            citation_by_story[str(story_id)].append(row)

    # Source evidence and all accepted extension-fact evidence are written once.
    evidence_shards: dict[str, dict[str, Any]] = {}
    for evidence_id in sorted(evidence):
        projected = make_evidence_from_sc1(evidence, source_display, evidence_id)
        if projected:
            evidence_shards[evidence_id] = projected
    for fact in x1_facts:
        if not review_ok(fact) or fact.get("review_decision") != "accepted":
            continue
        for assertion_id in fact.get("evidence_ids", []):
            assertion = assertion_by_source_id.get(str(assertion_id), {})
            evidence_shards[x1_evidence_id(str(assertion_id))] = make_evidence_from_x1(assertion, fact)
    for row in x1_scholarly:
        if row.get("review_status") not in {"scholarly_assertion_only", "citation_only"}:
            continue
        evidence_id = x1_evidence_id(str(row.get("source_assertion_id")))
        evidence_shards.setdefault(evidence_id, make_evidence_from_x1(row))

    # Reviewed atomic relations are the only source of family/marriage profile rows.
    family_by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    relation_shards: dict[str, dict[str, Any]] = {}
    for relation in sorted(relations, key=lambda row: str(row["id"])):
        relation_id = str(relation["id"])
        subject_id = str(relation.get("subject_id"))
        object_id = str(relation.get("object_id"))
        subject_name = person_name(people, person_display, subject_id)
        object_name = person_name(people, person_display, object_id)
        relation_label = pair(relation.get("label") or relation.get("relation_type") or "关系")
        relation_shards[relation_id] = {
            "schema": 1,
            "relation_id": relation_id,
            "source": "reviewed_hg0_relation_projection",
            "subject": {"person_id": subject_id, "name": subject_name},
            "object": {"person_id": object_id, "name": object_name},
            "relation_type": relation.get("relation_type"),
            "relation_subtype": relation.get("relation_subtype"),
            "label": relation_label,
            "relation_basis": relation.get("relation_basis"),
            "assertion_status": relation.get("assertion_status"),
            "review_status": "reviewed",
            "time": relation.get("time") or {"status": "unknown", "label": None},
            "story_ids": sorted(str(x) for x in relation.get("story_ids", [])),
            "evidence_ids": sorted(str(x) for x in relation.get("evidence_ids", []) if str(x) in evidence_shards),
            "context_label": pair(relation_source_label(relation)),
            "notes": relation.get("notes"),
        }
        if relation.get("relation_type") not in {"kinship", "marriage"}:
            continue
        for person_id, neighbor_id, role in (
            (subject_id, object_id, relation.get("role_a")),
            (object_id, subject_id, relation.get("role_b")),
        ):
            family_by_person[person_id].append({
                "person_id": neighbor_id,
                "name": person_name(people, person_display, neighbor_id),
                "relation_id": relation_id,
                "relation_label": pair(role or relation.get("label") or relation.get("relation_type")),
                "relation_basis": relation.get("relation_basis") or "direct",
                "assertion_status": relation.get("assertion_status"),
                "review_status": "reviewed",
                "evidence_ids": sorted(str(x) for x in relation.get("evidence_ids", []) if str(x) in evidence_shards),
            })

    # Map the accepted X1.2R-F facts back to their Story-local assertion records.
    x1_fact_story: dict[str, str] = {}
    for fact in x1_facts:
        for assertion_id in fact.get("evidence_ids", []):
            assertion = assertion_by_source_id.get(str(assertion_id))
            if assertion and assertion.get("story_id"):
                x1_fact_story[str(fact.get("fact_id"))] = str(assertion["story_id"])

    offices_by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    locations_by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fact in x1_facts:
        if not review_ok(fact) or fact.get("review_decision") != "accepted":
            continue
        person_id = fact.get("person_id") or fact.get("subject_id")
        if not person_id:
            continue
        evidence_ids = [x1_evidence_id(str(x)) for x in fact.get("evidence_ids", [])]
        provenance = {
            "source_family": fact.get("source_family"),
            "source_layer": fact.get("source_layer"),
            "attribution": fact.get("attribution"),
            "quoted_source": fact.get("quoted_source"),
            "transmission_status": fact.get("transmission_status"),
            "temporal_precision": fact.get("temporal_precision") or "unknown",
            "parent_assertion_modality": fact.get("parent_assertion_modality"),
        }
        if fact.get("fact_type") == "office_tenure":
            office = office_by_id.get(str(fact.get("office_id")))
            title = fact.get("office_title") or (office or {}).get("canonical_name") or "官职"
            offices_by_person[str(person_id)].append({
                "fact_id": fact.get("fact_id"),
                "office_id": fact.get("office_id"),
                "name": pair(title),
                "temporal_label": pair(fact.get("time_label")) if fact.get("time_label") else None,
                "temporal_precision": fact.get("temporal_precision") or "unknown",
                "review_status": "reviewed",
                "assertion_status": fact.get("assertion_status"),
                "evidence_ids": evidence_ids,
                "provenance": provenance,
            })
        if fact.get("fact_type") == "location_fact" and fact.get("location_id"):
            location = location_by_id.get(str(fact.get("location_id")))
            location_name = (location or {}).get("canonical_name") or fact.get("location_id")
            locations_by_person[str(person_id)].append({
                "fact_id": fact.get("fact_id"),
                "location_id": fact.get("location_id"),
                "name": pair(location_name),
                "role": pair(location_role_label(fact.get("location_role"))),
                "temporal_precision": fact.get("temporal_precision") or "unknown",
                "review_status": "reviewed",
                "assertion_status": fact.get("assertion_status"),
                "evidence_ids": evidence_ids,
                "provenance": provenance,
            })

    # Story orientations are shown only where their own review gate passed.
    orientations = {
        str(row.get("story_id")): row
        for row in sc1.get("story_era_orientations", [])
        if row.get("review_status") == "reviewed"
    }
    periods_by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for story_id, orientation in orientations.items():
        story = stories.get(story_id)
        if not story:
            continue
        for person_id in story.get("person_ids", []):
            periods_by_person[str(person_id)].append({
                "label": orientation.get("label"),
                "precision": orientation.get("orientation_precision"),
                "story_ids": [story_id],
                "evidence_ids": sorted(str(x) for x in orientation.get("evidence_ids", []) if str(x) in evidence_shards),
                "review_status": "reviewed",
            })

    # Retain participant semantics for the Story shard without turning references into facts.
    hard_participants_by_story: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in participant_freeze:
        if row.get("review_status") != "reviewed" or row.get("role") not in {"present", "speaker", "actor"}:
            continue
        story_id = str(row.get("story_id"))
        person_id = str(row.get("person_id"))
        hard_participants_by_story[story_id].append({
            "person_id": person_id,
            "name": person_name(people, person_display, person_id),
            "role": row.get("role"),
            "review_status": "reviewed",
            "evidence_ids": sorted(str(x) for x in row.get("evidence_ids", []) if str(x) in evidence_shards),
        })
    # Extension participant review is reviewed, but the associated Stories are not
    # in the current SiteBundle.  Keep it available only as person further reading.
    person_story_refs: dict[str, set[str]] = defaultdict(set)
    for row in x1_participants:
        if row.get("review_status") != "reviewed":
            continue
        story_id = row.get("story_id")
        if story_id not in selected_story_set:
            continue
        for surface in row.get("all_reviewed_surfaces", []):
            if surface.get("person_id"):
                person_story_refs[str(surface["person_id"])].add(str(story_id))

    # Per-person and per-story scholarly references are summary-only; full excerpts
    # are behind evidence shards.
    scholarly_refs_by_story: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for story_id, rows in scholarly_by_story.items():
        for row in sorted(rows, key=lambda x: str(x.get("review_item_id"))):
            evidence_id = x1_evidence_id(str(row.get("source_assertion_id")))
            kind = "citation" if row.get("review_status") == "citation_only" else "scholarly"
            scholarly_refs_by_story[story_id].append(ref_from_evidence(row, evidence_id, kind))
    citation_refs_by_story: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for story_id, rows in citation_by_story.items():
        for row in sorted(rows, key=lambda x: str(x.get("citation_id"))):
            citation_refs_by_story[story_id].append(ref_from_evidence(row, x1_evidence_id(str(row.get("assertion_id"))), "citation"))

    person_shards: dict[str, dict[str, Any]] = {}
    for person_id in sorted(people):
        refs: list[dict[str, Any]] = []
        for story_id in sorted(person_story_refs.get(person_id, set())):
            refs.extend(scholarly_refs_by_story.get(story_id, []))
            refs.extend(citation_refs_by_story.get(story_id, []))
        family = sorted(family_by_person.get(person_id, []), key=lambda x: (x["person_id"], x["relation_id"]))
        offices = sorted(offices_by_person.get(person_id, []), key=lambda x: (str(x.get("office_id")), str(x.get("fact_id"))))
        locations = sorted(locations_by_person.get(person_id, []), key=lambda x: (str(x.get("location_id")), str(x.get("fact_id"))))
        periods = sorted(periods_by_person.get(person_id, []), key=lambda x: str(x.get("label", {}).get("original", "")))
        refs = trim_refs(refs)
        all_evidence = sorted_unique(
            [evidence_id for row in family + offices + locations + periods for evidence_id in row.get("evidence_ids", [])]
            + [str(row["evidence_id"]) for row in refs]
        )
        person_shards[person_id] = {
            "schema": 1,
            "projection": "ux1_person_history",
            "person_id": person_id,
            "review_policy": "reviewed_facts_only; scholarly_assertions_are_separate",
            "family": family,
            "offices": offices,
            "locations": locations,
            "events": [],
            "periods": periods,
            "scholarly_refs": refs,
            "evidence_ids": all_evidence,
        }

    story_shards: dict[str, dict[str, Any]] = {}
    for story_id in published_story_ids:
        story = stories[story_id]
        orientation = orientations.get(story_id)
        context: list[dict[str, Any]] = []
        if orientation:
            context.append({
                "kind": "period",
                "label": orientation.get("label"),
                "precision": orientation.get("orientation_precision"),
                "review_status": "reviewed",
                "evidence_ids": sorted(str(x) for x in orientation.get("evidence_ids", []) if str(x) in evidence_shards),
            })
        story_refs = trim_refs(scholarly_refs_by_story.get(story_id, []) + citation_refs_by_story.get(story_id, []))
        story_scholar_refs = [ref for ref in story_refs if ref.get("kind") != "citation"]
        story_citation_refs = [ref for ref in story_refs if ref.get("kind") == "citation"]
        hard = sorted(hard_participants_by_story.get(story_id, []), key=lambda x: (x["person_id"], x["role"]))
        story_shards[story_id] = {
            "schema": 1,
            "projection": "ux1_story_history",
            "story_id": story_id,
            "review_policy": "reviewed_context_only; references_are_not_participation",
            "historical_context": context,
            "participant_context": hard,
            "scholarly_refs": story_scholar_refs,
            "citation_refs": story_citation_refs,
            "evidence_ids": sorted_unique(
                [x for row in context + hard for x in row.get("evidence_ids", [])]
                + [str(row["evidence_id"]) for row in story_refs]
            ),
        }

    # Era shards are intentionally small: only reviewed ruler identities and
    # reviewed story orientations are included; candidate event/location lists
    # remain in the existing initial Era projection and are not restated here.
    ruler_identities = {
        str(row.get("ruler_id")): row
        for row in sc1.get("ruler_identities", [])
        if row.get("review_status") == "reviewed"
    }
    era_shards: dict[str, dict[str, Any]] = {}
    for card in sorted(sc1.get("era_cards", []), key=lambda x: str(x.get("era_card_id"))):
        card_id = str(card.get("era_card_id"))
        ruler = ruler_identities.get(str(card.get("ruler_id")))
        reviewed_story_ids = [
            str(story_id) for story_id in card.get("story_ids", [])
            if str(story_id) in orientations
        ]
        payload: dict[str, Any] = {
            "schema": 1,
            "projection": "ux1_era_history",
            "era_id": card_id,
            "review_policy": "reviewed_ruler_and_temporal_context_only",
            "ruler": None,
            "events": [],
            "people": [],
            "offices": [],
            "locations": [],
            "story_ids": sorted(reviewed_story_ids),
            "has_more": {"events": False, "people": False, "offices": False, "locations": False, "stories": len(reviewed_story_ids) > 5},
            "evidence_ids": [],
        }
        if ruler:
            payload["ruler"] = {
                "ruler_id": ruler.get("ruler_id"),
                "title": ruler.get("canonical_title"),
                "personal_name": ruler.get("personal_name"),
                "polity": pair(ruler.get("polity")),
                "reign_start_year": ruler.get("actual_reign_start_year"),
                "reign_end_year": ruler.get("actual_reign_end_year"),
                "review_status": "reviewed",
                "evidence_ids": sorted(str(x) for x in ruler.get("evidence_ids", []) if str(x) in evidence_shards),
            }
            payload["evidence_ids"] = payload["ruler"]["evidence_ids"]
        era_shards[card_id] = payload

    # Make the source list explicit and stable; the browser only receives shard
    # paths, never this input inventory.
    inputs = [
        SC1_PATH, H0C_FACTS_PATH, H0C_OFFICES_PATH, H0C_LOCATIONS_PATH,
        PARTICIPANT_PATH, SELECTION_PATH, X1_2R_PARTICIPANT_PATH,
        X1_2RF_FACT_PATH, X1_2RF_ASSERTION_PATH, X1_2RF_SCHOLARLY_PATH,
        X1_2R_CITATION_PATH,
    ]
    shards: dict[str, dict[str, Any]] = {}
    for kind, rows in (
        ("person", person_shards),
        ("story", story_shards),
        ("era", era_shards),
        ("relation", relation_shards),
        ("evidence", evidence_shards),
    ):
        for entity_id in sorted(rows):
            shards[f"{kind}/{entity_id}.json"] = {"kind": kind, "id": entity_id}
    manifest = {
        "schema": 1,
        "projection": "UX1 historical depth",
        "generated_from": "reviewed downstream projections; no initial-bundle expansion",
        "source_hashes": {path.relative_to(ROOT).as_posix(): sha256_file(path) for path in inputs},
        "scope": {
            "published_story_count": len(published_story_ids),
            "person_count": len(person_shards),
            "era_count": len(era_shards),
            "reviewed_relation_count": len(relation_shards),
            "selected_x1_1_story_count": len(selected_story_ids),
            "selected_x1_1_story_ids": selected_story_ids,
        },
        "shards": shards,
        "policies": {
            "unresolved_facts_projected": False,
            "candidate_facts_projected": False,
            "scholarly_assertions_as_facts": False,
            "citation_only_as_facts": False,
            "ml_fields_projected": False,
            "full_jianshu_text_projected": False,
        },
    }
    all_shards: dict[str, dict[str, Any]] = {}
    for kind, rows in (
        ("person", person_shards), ("story", story_shards), ("era", era_shards),
        ("relation", relation_shards), ("evidence", evidence_shards),
    ):
        for entity_id, payload in rows.items():
            all_shards[f"{kind}/{entity_id}.json"] = payload
    return manifest, all_shards


def main() -> int:
    manifest, shards = build()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for relative_path, payload in sorted(shards.items()):
        write_json(OUTPUT_ROOT / relative_path, payload)
    # Add byte/hash metadata only after all shard contents are stable.
    manifest["shards"] = {
        relative_path: {
            **manifest["shards"][relative_path],
            "bytes": (OUTPUT_ROOT / relative_path).stat().st_size,
            "sha256": sha256_file(OUTPUT_ROOT / relative_path),
        }
        for relative_path in sorted(shards)
    }
    write_json(MANIFEST_PATH, manifest)
    print(json.dumps({
        "person": sum(path.startswith("person/") for path in shards),
        "story": sum(path.startswith("story/") for path in shards),
        "era": sum(path.startswith("era/") for path in shards),
        "relation": sum(path.startswith("relation/") for path in shards),
        "evidence": sum(path.startswith("evidence/") for path in shards),
        "output": str(OUTPUT_ROOT.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
