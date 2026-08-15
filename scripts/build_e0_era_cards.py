#!/usr/bin/env python3
"""Build the static E0 ruler audit and Era Card projection.

E0 deliberately keeps chronological rulers outside the production Person
registry.  The input is the already-built SC1 bundle plus H0A's reviewed
ruler-context evidence; this script does not discover historical rulers from
string matches alone.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from opencc import OpenCC


ROOT = Path(__file__).resolve().parents[1]
SC1_PATH = ROOT / "data/derived/sc1-site.json"
COORDINATES_PATH = ROOT / "data/derived/h0a-temporal-coordinates.json"
ANCHORS_PATH = ROOT / "data/annotation/story-temporal-anchors-h0a.json"
TEMPORAL_EVIDENCE_PATH = ROOT / "data/annotation/story-temporal-evidence-h0a.json"
EVENTS_PATH = ROOT / "data/annotation/historical-events-h0a.json"

IDENTITIES_PATH = ROOT / "data/annotation/ruler-identities-e0.json"
CARDS_PATH = ROOT / "data/annotation/era-cards-e0.json"
AUDIT_PATH = ROOT / "data/derived/e0-ruler-mention-audit.json"
PROJECTION_PATH = ROOT / "data/derived/e0-era-card-projection.json"
METRICS_PATH = ROOT / "data/derived/e0-metrics.json"


# These are not aliases to be applied globally.  Each entry is tied to a
# reviewed H0A ruler context, and the audit below only resolves occurrences
# whose local source evidence proves that context.
SAFE_RULERS: dict[str, dict[str, Any]] = {
    "h0a-ruler-context-cf3db82aef544b1c7cc1": {
        "ruler_id": "ruler-jin-wudi",
        "title": "晉武帝",
        "personal_name": None,
        "polity": "晉",
        "aliases": ["武帝", "晉武帝", "世祖武皇帝"],
        "context_note": "武帝在位于西晋初年的泰始、太康年间。这里的故事由他直接发问，使人物品评落在西晋初年的宫廷语境中。",
        "context_note_original": "武帝在位於西晉初年的泰始、太康年間。這裡的故事由他直接發問，使人物品評落在西晉初年的宮廷語境中。",
    },
    "h0a-ruler-context-eda2e8b7fb1eca551eda": {
        "ruler_id": "ruler-jin-yuandi",
        "title": "晉元帝",
        "personal_name": None,
        "polity": "晉",
        "aliases": ["元帝", "元皇帝", "晉元帝", "中宗元皇帝"],
        "context_note": "元帝在位于东晋初年的建武、大兴、永昌年间。故事写到元皇帝登阼后的皇储安排，呈现东晋早期的政治语境。",
        "context_note_original": "元帝在位於東晉初年的建武、大興、永昌年間。故事寫到元皇帝登阼後的皇儲安排，呈現東晉早期的政治語境。",
    },
    "h0a-ruler-context-99f376b4d6f693729b7d": {
        "ruler_id": "ruler-jin-mingdi",
        "title": "晉明帝",
        "personal_name": None,
        "polity": "晉",
        "aliases": ["明帝", "晉明帝", "肅宗明皇帝"],
        "context_note": "明帝在位于东晋早期的太宁年间。多则故事写他直接发问或会见人物，人物品评与交往由此落在东晋早期的宫廷语境中。",
        "context_note_original": "明帝在位於東晉早期的太寧年間。多則故事寫他直接發問或會見人物，人物品評與交往由此落在東晉早期的宮廷語境中。",
    },
}


# Surfaces are collected for audit even when no card can safely be selected.
# The list is intentionally finite and reviewable; it is not a Chinese NER
# rule.  Long forms precede short forms so the audit never creates an
# artificial substring occurrence.
RULER_SURFACES = sorted(
    {
        "晉安帝",
        "宋明帝",
        "孝愍皇帝",
        "孝懷皇帝",
        "簡文皇帝",
        "文皇帝",
        "明皇帝",
        "武皇帝",
        "高貴鄉公",
        "簡文帝",
        "孝武帝",
        "孝惠帝",
        "孝懷帝",
        "孝愍帝",
        "安帝",
        "惠帝",
        "成帝",
        "明帝",
        "元皇帝",
        "元帝",
        "武帝",
        "文帝",
        "宣帝",
        "晉明帝",
        "晉元帝",
        "晉武帝",
        "簡文",
        "文王",
        "宣王",
    },
    key=lambda value: (-len(value), value),
)
RULER_SURFACE_RE = re.compile("|".join(re.escape(value) for value in RULER_SURFACES))

SHARED_TITLE_SURFACES = {"明帝", "武帝", "文帝", "惠帝", "成帝", "元帝"}

# The two references in 05-fangzheng-023 are secure because the sentence
# introduces the Jin crown prince as 明帝 under 元皇帝.  They are references,
# not appearances, and are kept separate from the H0A direct ruler evidence.
SAFE_REFERENCES: dict[tuple[str, str, int, str], dict[str, str]] = {
    ("02-yanyu-078", "main_text", 0, "晉武帝"): {"ruler_id": "ruler-jin-wudi", "role": "referenced", "basis": "explicit_full_ruler_title"},
    ("05-fangzheng-023", "main_text", 13, "明帝"): {"ruler_id": "ruler-jin-mingdi", "role": "referenced", "basis": "story_local_dynastic_reference"},
    ("05-fangzheng-023", "main_text", 35, "明帝"): {"ruler_id": "ruler-jin-mingdi", "role": "referenced", "basis": "story_local_dynastic_reference"},
    ("05-fangzheng-023", "main_text", 73, "元帝"): {"ruler_id": "ruler-jin-yuandi", "role": "appears", "basis": "story_local_short_form_coreference"},
    ("08-shangyu-034", "liu_annotation", 10, "晉明帝"): {"ruler_id": "ruler-jin-mingdi", "role": "referenced", "basis": "explicit_full_ruler_title"},
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stable_id(prefix: str, *parts: object) -> str:
    material = "|".join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(material.encode('utf-8')).hexdigest()[:20]}"


def pair(original: str, converter: OpenCC) -> dict[str, str]:
    return {"original": original, "simplified": converter.convert(original)}


def source_evidence_id(story_id: str, section: str, annotation_id: str | None) -> str:
    if section == "main_text":
        return f"evidence-sc1-{story_id}-main"
    return f"evidence-sc1-{story_id}-{annotation_id}"


def source_span_evidence(
    story_id: str,
    section: str,
    start: int,
    end: int,
    annotation_id: str | None,
) -> dict[str, Any]:
    return {
        "kind": "published_story_layer",
        "section": section,
        "annotation_id": annotation_id,
        "char_start": start,
        "char_end_exclusive": end,
        "source_evidence_ids": [source_evidence_id(story_id, section, annotation_id)],
    }


def context_id_for_temporal_evidence(item: Mapping[str, Any]) -> str | None:
    candidate = item.get("normalized_candidate")
    if not isinstance(candidate, Mapping):
        return None
    value = candidate.get("ruler_context_id")
    return str(value) if isinstance(value, str) else None


def build_audit(
    bundle: Mapping[str, Any],
    coordinates: Mapping[str, Any],
    temporal_evidence: list[Mapping[str, Any]],
    anchors: list[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    evidence_by_location: dict[tuple[str, str, int, int], Mapping[str, Any]] = {}
    for item in temporal_evidence:
        if not isinstance(item, Mapping):
            continue
        if item.get("review_status") != "reviewed":
            continue
        if item.get("relation_to_story") != "direct_story_time":
            continue
        context_id = context_id_for_temporal_evidence(item)
        if context_id not in SAFE_RULERS:
            continue
        story_id = item.get("story_id")
        span = item.get("source_span")
        if not isinstance(story_id, str) or not isinstance(span, Mapping):
            continue
        section = str(span.get("section", ""))
        start = span.get("char_start")
        end = span.get("char_end_exclusive")
        if isinstance(start, int) and isinstance(end, int):
            evidence_by_location[(story_id, section, start, end)] = item

    anchor_by_story = {
        str(item["story_id"]): item
        for item in anchors
        if isinstance(item, Mapping) and isinstance(item.get("story_id"), str)
    }
    records: list[dict[str, Any]] = []
    for story in sorted(
        (item for item in bundle.get("stories", []) if isinstance(item, Mapping)),
        key=lambda item: (int(item.get("global_ordinal", 10**9)), str(item.get("id"))),
    ):
        story_id = str(story.get("id"))
        sections: list[tuple[str, str, str | None]] = [("main_text", str(story.get("text", "")), None)]
        for annotation in story.get("annotations", []):
            if not isinstance(annotation, Mapping):
                continue
            annotation_id = annotation.get("id")
            if isinstance(annotation_id, str):
                sections.append(("liu_annotation", str(annotation.get("text", "")), annotation_id))
        for section, text, annotation_id in sections:
            for match in RULER_SURFACE_RE.finditer(text):
                surface = match.group(0)
                start, end = match.span()
                temporal = evidence_by_location.get((story_id, section, start, end))
                safe_ruler_id: str | None = None
                role: str | None = None
                basis = "shared_title_requires_story_context"
                status = "unresolved"
                candidates: list[str] = []
                if temporal is not None:
                    context_id = context_id_for_temporal_evidence(temporal)
                    if context_id in SAFE_RULERS:
                        safe_ruler_id = SAFE_RULERS[context_id]["ruler_id"]
                        role = "appears"
                        basis = "h0a_reviewed_direct_ruler_evidence"
                        status = "resolved"
                        candidates = [safe_ruler_id]
                reference = SAFE_REFERENCES.get((story_id, section, start, surface))
                if reference:
                    safe_ruler_id = reference["ruler_id"]
                    role = reference["role"]
                    basis = reference["basis"]
                    status = "resolved"
                    candidates = [safe_ruler_id]
                if safe_ruler_id is None:
                    # A known card candidate is still not enough to resolve a
                    # shared imperial title.  Preserve the audit trail.
                    if surface in {"明帝", "元帝", "元皇帝", "武帝", "晉明帝", "晉元帝", "晉武帝"}:
                        candidates = [
                            SAFE_RULERS[context]["ruler_id"]
                            for context in sorted(SAFE_RULERS)
                            if surface in SAFE_RULERS[context]["aliases"]
                        ]
                    if surface in SHARED_TITLE_SURFACES:
                        status = "ambiguous"
                    elif len(candidates) > 1:
                        status = "ambiguous"
                    elif candidates:
                        status = "candidate_for_review"
                evidence_ids = [source_evidence_id(story_id, section, annotation_id)]
                temporal_evidence_ids: list[str] = []
                if temporal is not None and isinstance(temporal.get("evidence_record_id"), str):
                    temporal_evidence_ids.append(str(temporal["evidence_record_id"]))
                mention_id = stable_id("e0-ruler-mention", story_id, section, annotation_id or "", start, end, surface)
                records.append(
                    {
                        "mention_id": mention_id,
                        "story_id": story_id,
                        "section": section,
                        "annotation_id": annotation_id,
                        "surface": surface,
                        "anchor": {"text": surface, "section": section, "offset": start},
                        "source_span": source_span_evidence(story_id, section, start, end, annotation_id),
                        "candidate_ruler_ids": sorted(set(candidates)),
                        "ruler_id": safe_ruler_id,
                        "era_card_id": f"era-card-{safe_ruler_id}" if safe_ruler_id else None,
                        "resolution_basis": basis,
                        "resolution_status": status,
                        "story_role_candidate": role,
                        "evidence_ids": evidence_ids,
                        "temporal_evidence_ids": temporal_evidence_ids,
                        "era_card_exists": bool(safe_ruler_id),
                        "audit_note": (
                            "已由故事局部证据确认君主身份。"
                            if status == "resolved"
                            else "帝号存在跨朝代或同朝异主风险，未因字符串命中而建立导航。"
                        ),
                    }
                )
    return records, anchor_by_story


def period_rows(coordinates: Mapping[str, Any], context_id: str) -> list[Mapping[str, Any]]:
    contexts = {str(item.get("ruler_context_id")): item for item in coordinates.get("ruler_contexts", []) if isinstance(item, Mapping)}
    context = contexts.get(context_id, {})
    reign_ids = set(str(value) for value in context.get("reign_ids", []) if isinstance(value, str))
    return sorted(
        [item for item in coordinates.get("reign_periods", []) if isinstance(item, Mapping) and item.get("reign_id") in reign_ids],
        key=lambda item: (item.get("start_year_ce") is None, item.get("start_year_ce") or 10**9, str(item.get("reign_id"))),
    )


def source_temporal_ids(records: list[Mapping[str, Any]]) -> list[str]:
    return sorted({str(value) for record in records for value in record.get("temporal_evidence_ids", []) if isinstance(value, str)})


def build_projection(
    bundle: Mapping[str, Any],
    coordinates: Mapping[str, Any],
    anchors: list[Mapping[str, Any]],
    temporal_evidence: list[Mapping[str, Any]],
    events: list[Mapping[str, Any]],
    audit: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    converter = OpenCC("t2s")
    by_ruler: dict[str, list[dict[str, Any]]] = {}
    for item in audit:
        if item.get("resolution_status") == "resolved" and isinstance(item.get("ruler_id"), str):
            by_ruler.setdefault(str(item["ruler_id"]), []).append(item)
    anchors_by_context: dict[str, list[Mapping[str, Any]]] = {}
    for anchor in anchors:
        context_id = anchor.get("ruler_context_id")
        if isinstance(context_id, str) and context_id in SAFE_RULERS:
            anchors_by_context.setdefault(context_id, []).append(anchor)

    projected_events: list[dict[str, Any]] = []
    for event in sorted(events, key=lambda item: str(item.get("event_id"))):
        if not isinstance(event, Mapping) or not isinstance(event.get("event_id"), str):
            continue
        projected_events.append(
            {
                "id": str(event["event_id"]),
                "canonical_name": pair(str(event.get("canonical_name", event["event_id"])), converter),
                "aliases": [pair(str(alias), converter) for alias in event.get("aliases", []) if isinstance(alias, str)],
                "start_year_ce": event.get("start_year_ce"),
                "end_year_ce": event.get("end_year_ce"),
                "date_precision": event.get("date_precision"),
                "phase_ids": list(event.get("phase_ids", [])),
                "evidence_ids": list(event.get("evidence_ids", [])),
                "source_evidence_ids": sorted({
                    source_id
                    for claim in event.get("source_claims", [])
                    if isinstance(claim, Mapping)
                    for source_id in claim.get("source_evidence_ids", [])
                    if isinstance(source_id, str)
                }),
                "review_status": event.get("review_status", "candidate"),
            }
        )

    cards: list[dict[str, Any]] = []
    identities: list[dict[str, Any]] = []
    ruler_mentions = [item for item in audit if item.get("resolution_status") == "resolved" and item.get("era_card_exists")]
    story_by_id = {str(item.get("id")): item for item in bundle.get("stories", []) if isinstance(item, Mapping)}
    for context_id, definition in sorted(SAFE_RULERS.items(), key=lambda item: item[1]["ruler_id"]):
        ruler_id = str(definition["ruler_id"])
        periods = period_rows(coordinates, context_id)
        known_years = [value for period in periods for value in (period.get("start_year_ce"), period.get("end_year_ce")) if isinstance(value, int)]
        start_year = min(known_years) if known_years else None
        end_year = max(known_years) if known_years else None
        records = sorted(by_ruler.get(ruler_id, []), key=lambda item: (str(item.get("story_id")), str(item.get("mention_id"))))
        story_link_map: dict[tuple[str, str], dict[str, Any]] = {}
        for item in records:
            key = (str(item["story_id"]), str(item["story_role_candidate"]))
            entry = story_link_map.setdefault(
                key,
                {
                    "story_id": str(item["story_id"]),
                    "link_type": str(item["story_role_candidate"]),
                    "mention_ids": [],
                    "evidence_ids": [],
                    "source_evidence_ids": [],
                    "derivation_basis": str(item["resolution_basis"]),
                },
            )
            entry["mention_ids"].append(str(item["mention_id"]))
            entry["evidence_ids"].extend(str(value) for value in item.get("temporal_evidence_ids", []) if isinstance(value, str))
            entry["source_evidence_ids"].extend(str(value) for value in item.get("evidence_ids", []) if isinstance(value, str))
        for anchor in anchors_by_context.get(context_id, []):
            story_id = str(anchor["story_id"])
            key = (story_id, "reign_context")
            entry = story_link_map.setdefault(
                key,
                {
                    "story_id": story_id,
                    "link_type": "reign_context",
                    "mention_ids": [],
                    "evidence_ids": [],
                    "source_evidence_ids": [],
                    "derivation_basis": "h0a_story_temporal_anchor_intersects_reviewed_ruler_context",
                },
            )
            entry["evidence_ids"].extend(str(value) for value in anchor.get("evidence_ids", []) if isinstance(value, str))
            for evidence_id in anchor.get("evidence_ids", []):
                temporal = next((item for item in temporal_evidence if item.get("evidence_record_id") == evidence_id), None)
                if isinstance(temporal, Mapping):
                    entry["source_evidence_ids"].extend(str(value) for value in temporal.get("source_evidence_ids", []) if isinstance(value, str))
        story_links = []
        for entry in sorted(story_link_map.values(), key=lambda item: (int(story_by_id.get(item["story_id"], {}).get("global_ordinal", 10**9)), item["link_type"])):
            entry["mention_ids"] = sorted(set(entry["mention_ids"]))
            entry["evidence_ids"] = sorted(set(entry["evidence_ids"]))
            entry["source_evidence_ids"] = sorted(set(entry["source_evidence_ids"]))
            story_links.append(entry)
        linked_story_ids = sorted({str(item["story_id"]) for item in story_links})
        # Use authoritative H0A event records for relevance.  A card shows
        # only events whose dated interval intersects the reign and which
        # already link to at least one current production Story.
        current_story_ids = set(story_by_id)
        event_ids: list[str] = []
        for event in events:
            if not isinstance(event, Mapping) or not isinstance(event.get("event_id"), str):
                continue
            event_start, event_end = event.get("start_year_ce"), event.get("end_year_ce")
            if not all(isinstance(value, int) for value in (start_year, end_year, event_start, event_end)):
                continue
            if int(event_end) < int(start_year) or int(event_start) > int(end_year):
                continue
            linked_event_story_ids = {
                str(value)
                for value in event.get("linked_story_ids", [])
                if isinstance(value, str)
            }
            if linked_event_story_ids & current_story_ids:
                event_ids.append(str(event["event_id"]))
        event_ids = sorted(set(event_ids))

        person_story_ids: dict[str, set[str]] = {}
        for link in story_links:
            if link["link_type"] != "appears":
                continue
            story = story_by_id.get(link["story_id"], {})
            for person_id in story.get("person_ids", []):
                if isinstance(person_id, str):
                    person_story_ids.setdefault(person_id, set()).add(link["story_id"])
        intersections = [
            {
                "person_id": person_id,
                "story_ids": sorted(story_ids, key=lambda value: int(story_by_id.get(value, {}).get("global_ordinal", 10**9))),
                "story_count": len(story_ids),
                "derivation_basis": "production_person_and_ruler_appears_share_story",
                "evidence_ids": sorted({
                    evidence_id
                    for story_id in story_ids
                    for evidence_id in story_by_id.get(story_id, {}).get("evidence_ids", [])
                    if isinstance(evidence_id, str)
                }),
            }
            for person_id, story_ids in sorted(person_story_ids.items())
        ]
        temporal_ids = source_temporal_ids(records)
        identity = {
            "ruler_id": ruler_id,
            "canonical_title": pair(str(definition["title"]), converter),
            "personal_name": pair(str(definition["personal_name"]), converter) if definition.get("personal_name") else None,
            "polity": definition["polity"],
            "reign_start_year": start_year,
            "reign_end_year": end_year,
            "reign_period_ids": [str(period["reign_id"]) for period in periods if isinstance(period.get("reign_id"), str)],
            "era_year_ids": [
                str(item["era_year_id"])
                for item in coordinates.get("era_years", [])
                if isinstance(item, Mapping) and item.get("reign_id") in {period.get("reign_id") for period in periods}
            ],
            "aliases": [pair(alias, converter) for alias in definition["aliases"]],
            "evidence_ids": temporal_ids,
            "source_evidence_ids": sorted({value for item in records for value in item.get("evidence_ids", []) if isinstance(value, str)}),
            "assertion_status": "attested",
            "review_status": "reviewed",
            "resolution_basis": "h0a_reviewed_story_local_ruler_context",
        }
        identities.append(identity)
        era_names = [
            {
                "name": pair(str(period.get("era_name", "")), converter),
                "reign_period_id": period.get("reign_id"),
                "start_year_ce": period.get("start_year_ce"),
                "end_year_ce": period.get("end_year_ce"),
            }
            for period in periods
            if isinstance(period.get("era_name"), str) and period.get("era_name")
        ]
        context_evidence_ids = sorted(set(temporal_ids + [str(value) for item in records for value in item.get("evidence_ids", []) if isinstance(value, str)]))
        cards.append(
            {
                "era_card_id": f"era-card-{ruler_id}",
                "ruler_id": ruler_id,
                "title": pair(str(definition["title"]), converter),
                "personal_name": identity["personal_name"],
                "polity": definition["polity"],
                "reign_label": pair(f"在位 {start_year}–{end_year}" if start_year is not None and end_year is not None else "", converter),
                "reign_start_year": start_year,
                "reign_end_year": end_year,
                "era_names": era_names,
                "era_context": {
                    "text": pair(str(definition["context_note_original"]), converter),
                    "evidence_ids": context_evidence_ids,
                    "assertion_status": "inferred",
                    "review_status": "candidate",
                },
                "ruler_story_links": story_links,
                "person_intersections": intersections,
                "historical_event_ids": event_ids,
                "evidence_ids": context_evidence_ids,
                "source_evidence_ids": sorted({value for link in story_links for value in link.get("source_evidence_ids", []) if isinstance(value, str)}),
                "review_status": "candidate",
                "selection_note": "纳入当前 83 则生产故事中有明确、经 H0A 审核的故事局部君主证据的最小 pilot 集合。",
            }
        )

    metrics = {
        "schema": 1,
        "stage": "e0-era-card-pilot-metrics",
        "ruler_audit": {
            "ruler_like_surfaces_found": len(audit),
            "resolved_ruler_mentions": sum(item.get("resolution_status") == "resolved" for item in audit),
            "ambiguous_ruler_mentions": sum(item.get("resolution_status") == "ambiguous" for item in audit),
            "unresolved_ruler_mentions": sum(item.get("resolution_status") in {"unresolved", "candidate_for_review"} for item in audit),
            "unique_stories_audited": len({item["story_id"] for item in audit}),
        },
        "era_cards": {
            "count": len(cards),
            "rulers_covered": len(identities),
            "reign_years_covered": sorted({
                year
                for card in cards
                for year in (card.get("reign_start_year"), card.get("reign_end_year"))
                if isinstance(year, int)
            }),
            "era_names_represented": sorted({
                era["name"]["original"]
                for card in cards
                for era in card.get("era_names", [])
                if isinstance(era, Mapping) and isinstance(era.get("name"), Mapping)
            }),
        },
        "stories": {
            "appears": len({item["story_id"] for card in cards for item in card["ruler_story_links"] if item["link_type"] == "appears"}),
            "referenced": len({item["story_id"] for card in cards for item in card["ruler_story_links"] if item["link_type"] == "referenced"}),
            "reign_context": len({item["story_id"] for card in cards for item in card["ruler_story_links"] if item["link_type"] == "reign_context"}),
            "unique_reachable": len({item["story_id"] for card in cards for item in card["ruler_story_links"]}),
        },
        "person_intersections": {
            "direct_links": sum(len(card["person_intersections"]) for card in cards),
            "unique_people": len({item["person_id"] for card in cards for item in card["person_intersections"]}),
        },
        "events": {
            "projected_into_cards": len({event_id for card in cards for event_id in card["historical_event_ids"]}),
            "names": sorted({event["canonical_name"]["original"] for event in projected_events if any(event["id"] in card["historical_event_ids"] for card in cards)}),
        },
        "navigation": {
            "clickable_ruler_mentions": len(ruler_mentions),
            "era_to_story_links": sum(len(card["ruler_story_links"]) for card in cards),
            "era_to_person_links": sum(len(card["person_intersections"]) for card in cards),
        },
        "deferred_ruler_surfaces": sorted({item["surface"] for item in audit if item.get("resolution_status") != "resolved"}),
    }
    return identities, cards, projected_events, metrics


def build() -> dict[str, Any]:
    bundle = read_json(SC1_PATH)
    coordinates = read_json(COORDINATES_PATH)
    anchors_doc = read_json(ANCHORS_PATH)
    temporal_doc = read_json(TEMPORAL_EVIDENCE_PATH)
    events_doc = read_json(EVENTS_PATH)
    anchors = [item for item in anchors_doc.get("records", []) if isinstance(item, Mapping)]
    temporal_evidence = [item for item in temporal_doc.get("records", []) if isinstance(item, Mapping)]
    events = [item for item in events_doc.get("records", []) if isinstance(item, Mapping)]
    audit, _anchor_by_story = build_audit(bundle, coordinates, temporal_evidence, anchors)
    identities, cards, projected_events, metrics = build_projection(
        bundle, coordinates, anchors, temporal_evidence, events, audit
    )
    write_json(IDENTITIES_PATH, {"schema": 1, "stage": "e0-ruler-identity-registry", "records": identities})
    write_json(CARDS_PATH, {"schema": 1, "stage": "e0-era-card-pilot", "records": cards})
    write_json(
        AUDIT_PATH,
        {
            "schema": 1,
            "stage": "e0-ruler-mention-audit",
            "scope": {"story_count": len(bundle.get("stories", [])), "story_ids": [item.get("id") for item in bundle.get("stories", []) if isinstance(item, Mapping)]},
            "records": audit,
            "policy": "帝号只在故事局部证据与已审核 H0A ruler context 同时支持时解析；字符串命中本身永不建立导航。",
        },
    )
    projection = {
        "schema": 1,
        "stage": "e0-era-card-static-projection",
        "generated_from": [str(path.relative_to(ROOT)) for path in (SC1_PATH, COORDINATES_PATH, TEMPORAL_EVIDENCE_PATH, ANCHORS_PATH, EVENTS_PATH)],
        "ruler_identities": identities,
        "era_cards": cards,
        "ruler_mentions": [item for item in audit if item.get("resolution_status") == "resolved" and item.get("era_card_exists")],
        "historical_events": projected_events,
    }
    write_json(PROJECTION_PATH, projection)
    write_json(METRICS_PATH, metrics)
    return projection


if __name__ == "__main__":
    result = build()
    print(
        "built E0 Era Card pilot: "
        f"{len(result['era_cards'])} cards; "
        f"{len(result['ruler_mentions'])} clickable ruler mentions"
    )
