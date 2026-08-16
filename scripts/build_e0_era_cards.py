#!/usr/bin/env python3
"""Build the static E0 ruler audit and E0.1 universal Era projection.

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
ACTIVITY_PATH = ROOT / "data/annotation/person-activity-anchors-h0a.json"
W3_EXPANSION_PATH = ROOT / "data/annotation/story-expansion-wave-3.json"

IDENTITIES_PATH = ROOT / "data/annotation/ruler-identities-e0.json"
CARDS_PATH = ROOT / "data/annotation/era-cards-e0.json"
AUDIT_PATH = ROOT / "data/derived/e0-ruler-mention-audit.json"
PROJECTION_PATH = ROOT / "data/derived/e0-era-card-projection.json"
ORIENTATION_PATH = ROOT / "data/derived/e0-story-era-orientations.json"
METRICS_PATH = ROOT / "data/derived/e0-metrics.json"


# These are not aliases to be applied globally.  Each entry is tied to a
# reviewed H0A ruler context, and the audit below only resolves occurrences
# whose local source evidence proves that context.
SAFE_RULERS: dict[str, dict[str, Any]] = {
    "h0a-ruler-context-cf3db82aef544b1c7cc1": {
        "ruler_id": "ruler-jin-wudi",
        "title": "晉武帝",
        "personal_name": "司馬炎",
        "personal_name_source": "content/processed/jinshu/units/benji/003-benji-001.md",
        "polity": "晉",
        "aliases": ["武帝", "晉武帝", "世祖武皇帝"],
        "context_note": "武帝在位于西晋初年的泰始、太康年间。这里的故事由他直接发问，使人物品评落在西晋初年的宫廷语境中。",
        "context_note_original": "武帝在位於西晉初年的泰始、太康年間。這裡的故事由他直接發問，使人物品評落在西晉初年的宮廷語境中。",
    },
    "h0a-ruler-context-eda2e8b7fb1eca551eda": {
        "ruler_id": "ruler-jin-yuandi",
        "title": "晉元帝",
        "personal_name": "司馬睿",
        "personal_name_source": "content/processed/jinshu/units/benji/006-benji-001.md",
        "polity": "晉",
        "aliases": ["元帝", "元皇帝", "晉元帝", "中宗元皇帝"],
        "context_note": "元帝在位于东晋初年的建武、大兴、永昌年间。故事写到元皇帝登阼后的皇储安排，呈现东晋早期的政治语境。",
        "context_note_original": "元帝在位於東晉初年的建武、大興、永昌年間。故事寫到元皇帝登阼後的皇儲安排，呈現東晉早期的政治語境。",
    },
    "h0a-ruler-context-99f376b4d6f693729b7d": {
        "ruler_id": "ruler-jin-mingdi",
        "title": "晉明帝",
        "personal_name": "司馬紹",
        "personal_name_source": "content/processed/jinshu/units/benji/006-benji-001.md",
        "polity": "晉",
        "aliases": ["明帝", "晉明帝", "肅宗明皇帝"],
        "context_note": "明帝在位于东晋早期的太宁年间。多则故事写他直接发问或会见人物，人物品评与交往由此落在东晋早期的宫廷语境中。",
        "context_note_original": "明帝在位於東晉早期的太寧年間。多則故事寫他直接發問或會見人物，人物品評與交往由此落在東晉早期的宮廷語境中。",
    },
}


# These are source-backed personal-name readings, not a second ruler table.
# The actual tenure interval is still taken from the reviewed H0A ruler
# context, whose chronology is derived from ZTJ0 and cross-checked by the
# local Jinshu 帝紀 units named above.
RULER_BIOGRAPHY_SURFACES: dict[str, str] = {
    "ruler-jin-wudi": "武皇帝諱炎字安世",
    "ruler-jin-yuandi": "元皇帝諱睿字景文",
    "ruler-jin-mingdi": "明皇帝諱紹字道畿",
}


# Reader-oriented windows deliberately reuse H0A phase coordinates.  The two
# narrower Eastern-Jin windows are only used when a current Story is linked to
# a dated H0A event; they do not alter the phase ontology or Story anchors.
BROAD_WINDOW_SPECS = {
    "phase-1": {
        "era_card_id": "era-card-period-phase-1",
        "label": "漢末餘緒／魏初",
        "context": "漢末至魏初的故事，讓讀者先看見世說人物所承接的政治與士人背景。",
        "context_simplified": "汉末至魏初的故事，让读者先看见世说人物所承接的政治与士人背景。",
    },
    "phase-2": {
        "era_card_id": "era-card-period-phase-2",
        "label": "正始與曹魏後期",
        "context": "正始與曹魏後期，是魏晉人物品評、清談與政局轉折交會的一段閱讀時段。",
        "context_simplified": "正始与曹魏后期，是魏晋人物品评、清谈与政局转折交会的一段阅读时段。",
    },
    "phase-3": {
        "era_card_id": "era-card-period-phase-3",
        "label": "竹林—西晉初",
        "context": "竹林人物與西晉初年的故事，呈現魏末士人風氣如何進入新的政權秩序。",
        "context_simplified": "竹林人物与西晋初年的故事，呈现魏末士人风气如何进入新的政权秩序。",
    },
    "phase-4": {
        "era_card_id": "era-card-period-phase-4",
        "label": "西晉後期—永嘉南渡",
        "context": "西晉後期至永嘉南渡前後，動亂與遷徙改變了人物活動的地理與政治背景。",
        "context_simplified": "西晋后期至永嘉南渡前后，动乱与迁徙改变了人物活动的地理与政治背景。",
    },
    "phase-5": {
        "era_card_id": "era-card-period-phase-5",
        "label": "東晉",
        "context": "東晉是当前世說故事最集中的歷史背景；南渡政權與士族人物在此交織。",
        "context_simplified": "东晋是当前世说故事最集中的历史背景；南渡政权与士族人物在此交织。",
    },
    "east-jin-early": {
        "era_card_id": "era-card-period-east-jin-early",
        "label": "東晉早期",
        "context": "東晉早期的故事靠近新政權建立與王敦、蘇峻等局勢轉折，人物行動仍帶著南渡後的緊張。",
        "context_simplified": "东晋早期的故事靠近新政权建立与王敦、苏峻等局势转折，人物行动仍带着南渡后的紧张。",
    },
    "east-jin-late": {
        "era_card_id": "era-card-period-east-jin-late",
        "label": "東晉後期",
        "context": "東晉後期的故事落在政局與人物聲名已經延展多年的時段；這裡只作閱讀定位，不代替完整年代考證。",
        "context_simplified": "东晋后期的故事落在政局与人物声名已经延展多年的时段；这里只作阅读定位，不代替完整年代考证。",
    },
}

CORPUS_CARD_SPEC = {
    "era_card_id": "era-card-corpus-shishuo-era",
    "label": "世說時代",
    "label_simplified": "世说时代",
    "context": "這則故事目前缺少足以縮小年代的本地證據；先把它放回《世說》所涵蓋的魏晉歷史閱讀範圍。",
    "context_simplified": "这则故事目前缺少足以缩小年代的本地证据；先把它放回《世说》所涵盖的魏晋历史阅读范围。",
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
    # This 明帝 is the Jin ruler named by the story's local political
    # context (王敦's proposed deposition of the current emperor).  It is a
    # reviewed occurrence decision, not a global 明帝 alias.
    ("05-fangzheng-032", "main_text", 11, "明帝"): {"ruler_id": "ruler-jin-mingdi", "role": "referenced", "basis": "story_local_reviewed_ruler_reference"},
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


def phase_by_id(coordinates: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(item["phase_id"]): item
        for item in coordinates.get("phases", [])
        if isinstance(item, Mapping) and isinstance(item.get("phase_id"), str)
    }


def phase_interval(coordinates: Mapping[str, Any], phase_id: str) -> tuple[int | None, int | None]:
    phase = phase_by_id(coordinates).get(phase_id, {})
    start = phase.get("approximate_start_year")
    end = phase.get("approximate_end_year")
    return (start if isinstance(start, int) else None, end if isinstance(end, int) else None)


def story_order_key(story_by_id: Mapping[str, Mapping[str, Any]], anchors_by_story: Mapping[str, Mapping[str, Any]], story_id: str) -> tuple[Any, ...]:
    anchor = anchors_by_story.get(story_id, {})
    start = anchor.get("start_year_ce")
    end = anchor.get("end_year_ce")
    # A missing date must not be sorted before a dated Story.  The final
    # canonical ordinal is the only fallback; it is never used as historical
    # evidence.
    return (
        start is None,
        start if isinstance(start, int) else 10**9,
        end if isinstance(end, int) else 10**9,
        int(story_by_id.get(story_id, {}).get("global_ordinal", 10**9)),
        story_id,
    )


def ordered_story_ids(
    story_by_id: Mapping[str, Mapping[str, Any]],
    anchors_by_story: Mapping[str, Mapping[str, Any]],
    story_ids: set[str],
) -> list[str]:
    return sorted(story_ids, key=lambda story_id: story_order_key(story_by_id, anchors_by_story, story_id))


def present_person_ids(bundle: Mapping[str, Any], story_id: str) -> list[str]:
    """Return only scene participants, never off-frame or annotation-only people."""

    contexts = bundle.get("scene_contexts", {})
    context = contexts.get(story_id, {}) if isinstance(contexts, Mapping) else {}
    people = context.get("people_at_scene", []) if isinstance(context, Mapping) else []
    story = next(
        (
            item
            for item in bundle.get("stories", [])
            if isinstance(item, Mapping) and item.get("id") == story_id
        ),
        {},
    )
    story_person_ids = {
        str(person_id)
        for person_id in story.get("person_ids", [])
        if isinstance(person_id, str)
    }
    return sorted({
        str(item.get("person_id"))
        for item in people
        if isinstance(item, Mapping)
        and item.get("scene_role") == "present"
        and isinstance(item.get("person_id"), str)
        and str(item.get("person_id")) in story_person_ids
    })


def participant_intersections(
    bundle: Mapping[str, Any],
    story_by_id: Mapping[str, Mapping[str, Any]],
    story_ids: set[str],
    *,
    derivation_basis: str,
    anchors_by_story: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    by_person: dict[str, set[str]] = {}
    for story_id in story_ids:
        for person_id in present_person_ids(bundle, story_id):
            by_person.setdefault(person_id, set()).add(story_id)
    return [
        {
            "person_id": person_id,
            "story_ids": ordered_story_ids(story_by_id, anchors_by_story or {}, story_ids_for_person),
            "story_count": len(story_ids_for_person),
            "derivation_basis": derivation_basis,
            "evidence_ids": sorted({
                str(evidence_id)
                for story_id in story_ids_for_person
                for evidence_id in story_by_id.get(story_id, {}).get("evidence_ids", [])
                if isinstance(evidence_id, str)
            }),
        }
        for person_id, story_ids_for_person in sorted(by_person.items())
    ]


def event_phase_ids(event: Mapping[str, Any], phase_lookup: Mapping[str, Mapping[str, Any]]) -> list[str]:
    values = [str(value) for value in event.get("phase_ids", []) if isinstance(value, str) and value in phase_lookup]
    return sorted(set(values))


def broad_window_for_story(
    story_id: str,
    anchor: Mapping[str, Any],
    w3_by_story: Mapping[str, Mapping[str, Any]],
    events_by_id: Mapping[str, Mapping[str, Any]],
) -> str | None:
    """Choose a reader window without changing the H0A anchor."""

    event_ids = [str(value) for value in anchor.get("event_ids", []) if isinstance(value, str)]
    if "event-sun-en-rebellion" in event_ids:
        return "east-jin-late"
    if {"event-wang-dun-rebellion", "event-su-jun-rebellion"} & set(event_ids):
        return "east-jin-early"
    phase_id = anchor.get("phase_id")
    if isinstance(phase_id, str) and phase_id in BROAD_WINDOW_SPECS:
        return phase_id
    w3 = w3_by_story.get(story_id, {})
    w3_phase_id = w3.get("phase_id")
    if isinstance(w3_phase_id, str) and w3_phase_id in BROAD_WINDOW_SPECS:
        # W3's phase is a product orientation input, not a rewrite of the
        # StoryTemporalAnchor.  Its provenance remains on the audit record.
        return w3_phase_id
    # Event phase can be useful even when the H0A anchor intentionally kept a
    # broad or unknown direct date.  Use only events already linked to this
    # Story, never a keyword found elsewhere in the corpus.
    event_phases = {
        str(phase_id)
        for event_id in event_ids
        for phase_id in events_by_id.get(event_id, {}).get("phase_ids", [])
        if isinstance(phase_id, str)
    }
    return next(iter(sorted(event_phases)), None) if len(event_phases) == 1 else None


def build_broad_window(
    window_id: str,
    coordinates: Mapping[str, Any],
    stories: set[str],
    story_by_id: Mapping[str, Mapping[str, Any]],
    anchors_by_story: Mapping[str, Mapping[str, Any]],
    bundle: Mapping[str, Any],
    events: list[Mapping[str, Any]],
    *,
    story_basis: Mapping[str, str],
) -> dict[str, Any]:
    if window_id in BROAD_WINDOW_SPECS:
        spec = BROAD_WINDOW_SPECS[window_id]
        phase_id = window_id if window_id.startswith("phase-") else "phase-5"
        phase_start, phase_end = phase_interval(coordinates, phase_id)
        if window_id == "east-jin-early":
            start_year, end_year = 318, 342
            phase_ids = ["phase-5"]
        elif window_id == "east-jin-late":
            start_year, end_year = 376, 420
            phase_ids = ["phase-5"]
        else:
            start_year, end_year = phase_start, phase_end
            phase_ids = [phase_id]
        context = pair(str(spec["context"]), OpenCC("t2s"))
        context["original"] = str(spec["context"])
        context["simplified"] = str(spec["context_simplified"])
        label = pair(str(spec["label"]), OpenCC("t2s"))
    else:
        raise ValueError(f"unknown broad Era window: {window_id}")

    event_ids = []
    for event in events:
        if not isinstance(event, Mapping) or not isinstance(event.get("event_id"), str):
            continue
        event_start, event_end = event.get("start_year_ce"), event.get("end_year_ce")
        if not all(isinstance(value, int) for value in (start_year, end_year, event_start, event_end)):
            continue
        if int(event_end) < int(start_year) or int(event_start) > int(end_year):
            continue
        linked = {str(value) for value in event.get("linked_story_ids", []) if isinstance(value, str)}
        if linked & stories:
            event_ids.append(str(event["event_id"]))
    event_ids.sort(key=lambda event_id: (
        next((event.get("start_year_ce") for event in events if event.get("event_id") == event_id), 10**9),
        next((event.get("end_year_ce") for event in events if event.get("event_id") == event_id), 10**9),
        event_id,
    ))
    evidence_ids = sorted({
        evidence_id
        for story_id in stories
        for evidence_id in anchors_by_story.get(story_id, {}).get("evidence_ids", [])
        if isinstance(evidence_id, str)
    } | {
        evidence_id
        for event in events
        if event.get("event_id") in event_ids
        for evidence_id in event.get("evidence_ids", [])
        if isinstance(evidence_id, str)
    })
    source_evidence_ids = sorted({
        evidence_id
        for story_id in stories
        for evidence_id in story_by_id.get(story_id, {}).get("evidence_ids", [])
        if isinstance(evidence_id, str)
    })
    return {
        "era_card_id": str(BROAD_WINDOW_SPECS[window_id]["era_card_id"]),
        "card_kind": "broad_period",
        "ruler_id": None,
        "title": label,
        "label": label,
        "orientation_label": label,
        "personal_name": None,
        "polity": "晉" if phase_id == "phase-5" else None,
        "reign_label": pair(
            f"約 {start_year}–{end_year}" if isinstance(start_year, int) and isinstance(end_year, int) else "",
            OpenCC("t2s"),
        ),
        "reign_start_year": start_year,
        "reign_end_year": end_year,
        "start_year_ce": start_year,
        "end_year_ce": end_year,
        "era_names": [],
        "phase_ids": phase_ids,
        "era_context": {
            "text": context,
            "evidence_ids": evidence_ids,
            "assertion_status": "inferred",
            "review_status": "candidate",
        },
        "ruler_story_links": [],
        "story_ids": ordered_story_ids(story_by_id, anchors_by_story, stories),
        "person_intersections": participant_intersections(
            bundle,
            story_by_id,
            stories,
            derivation_basis="assigned_story_scene_participants",
            anchors_by_story=anchors_by_story,
        ),
        "historical_event_ids": event_ids,
        "evidence_ids": evidence_ids,
        "source_evidence_ids": source_evidence_ids,
        "orientation_precision": "broad_period",
        "review_status": "candidate",
        "selection_note": "以 H0A phase/event 坐标建立阅读定位窗口；不改写 StoryTemporalAnchor。",
        "story_basis": {story_id: story_basis.get(story_id, "historical_phase") for story_id in sorted(stories)},
    }


def build_projection(
    bundle: Mapping[str, Any],
    coordinates: Mapping[str, Any],
    anchors: list[Mapping[str, Any]],
    temporal_evidence: list[Mapping[str, Any]],
    events: list[Mapping[str, Any]],
    activities: list[Mapping[str, Any]],
    audit: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    converter = OpenCC("t2s")
    by_ruler: dict[str, list[dict[str, Any]]] = {}
    for item in audit:
        if item.get("resolution_status") == "resolved" and isinstance(item.get("ruler_id"), str):
            by_ruler.setdefault(str(item["ruler_id"]), []).append(item)
    anchors_by_context: dict[str, list[Mapping[str, Any]]] = {}
    anchors_by_story: dict[str, Mapping[str, Any]] = {}
    for anchor in anchors:
        if isinstance(anchor.get("story_id"), str):
            anchors_by_story[str(anchor["story_id"])] = anchor
        context_id = anchor.get("ruler_context_id")
        if isinstance(context_id, str) and context_id in SAFE_RULERS:
            anchors_by_context.setdefault(context_id, []).append(anchor)

    projected_events: list[dict[str, Any]] = []
    for event in sorted(
        events,
        key=lambda item: (
            item.get("start_year_ce") is None,
            item.get("start_year_ce") if isinstance(item.get("start_year_ce"), int) else 10**9,
            item.get("end_year_ce") if isinstance(item.get("end_year_ce"), int) else 10**9,
            str(item.get("event_id")),
        ),
    ):
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
        context_row = next(
            (
                item
                for item in coordinates.get("ruler_contexts", [])
                if isinstance(item, Mapping) and item.get("ruler_context_id") == context_id
            ),
            {},
        )
        # This interval is the ruler's actual tenure coordinate.  The
        # era-name rows below are observed chronology segments; Story
        # coverage must never define the ruler's reign.
        start_year = context_row.get("start_year_ce") if isinstance(context_row.get("start_year_ce"), int) else None
        end_year = context_row.get("end_year_ce") if isinstance(context_row.get("end_year_ce"), int) else None
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
        event_by_id = {
            str(event.get("event_id")): event
            for event in events
            if isinstance(event, Mapping) and isinstance(event.get("event_id"), str)
        }
        event_ids = sorted(
            set(event_ids),
            key=lambda event_id: (
                event_by_id.get(event_id, {}).get("start_year_ce") is None,
                event_by_id.get(event_id, {}).get("start_year_ce") if isinstance(event_by_id.get(event_id, {}).get("start_year_ce"), int) else 10**9,
                event_by_id.get(event_id, {}).get("end_year_ce") if isinstance(event_by_id.get(event_id, {}).get("end_year_ce"), int) else 10**9,
                event_id,
            ),
        )

        appears_story_ids = {str(link["story_id"]) for link in story_links if link["link_type"] == "appears"}
        intersections = participant_intersections(
            bundle,
            story_by_id,
            appears_story_ids,
            derivation_basis="production_person_and_ruler_appears_share_scene",
            anchors_by_story=anchors_by_story,
        )
        temporal_ids = source_temporal_ids(records)
        identity = {
            "ruler_id": ruler_id,
            "actual_reign_start_year": start_year,
            "actual_reign_end_year": end_year,
            "canonical_title": pair(str(definition["title"]), converter),
            "personal_name": pair(str(definition["personal_name"]), converter) if definition.get("personal_name") else None,
            "polity": definition["polity"],
            "reign_start_year": start_year,
            "reign_end_year": end_year,
            "reign_period_ids": [str(period["reign_id"]) for period in periods if isinstance(period.get("reign_id"), str)],
            "observed_reign_period_ids": [str(period["reign_id"]) for period in periods if isinstance(period.get("reign_id"), str)],
            "era_year_ids": [
                str(item["era_year_id"])
                for item in coordinates.get("era_years", [])
                if isinstance(item, Mapping) and item.get("reign_id") in {period.get("reign_id") for period in periods}
            ],
            "aliases": [pair(alias, converter) for alias in definition["aliases"]],
            "evidence_ids": temporal_ids,
            "source_evidence_ids": sorted({value for item in records for value in item.get("evidence_ids", []) if isinstance(value, str)}),
            "tenure_evidence": {
                "h0a_ruler_context_id": context_id,
                "jinshu_unit_path": definition.get("personal_name_source"),
                "identity_surface": RULER_BIOGRAPHY_SURFACES.get(ruler_id),
            },
            "personal_name_evidence": {
                "source_path": definition.get("personal_name_source"),
                "surface": RULER_BIOGRAPHY_SURFACES.get(ruler_id),
            },
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
        orientation_label = pair(str(definition["title"]), converter)
        if era_names:
            orientation_label = pair(
                f"{definition['title']} · {era_names[0]['name']['original']}",
                converter,
            )
        context_evidence_ids = sorted(set(temporal_ids + [str(value) for item in records for value in item.get("evidence_ids", []) if isinstance(value, str)]))
        cards.append(
            {
                "era_card_id": f"era-card-{ruler_id}",
                "card_kind": "ruler_reign",
                "ruler_id": ruler_id,
                "title": pair(str(definition["title"]), converter),
                "label": pair(str(definition["title"]), converter),
                "orientation_label": orientation_label,
                "personal_name": identity["personal_name"],
                "polity": definition["polity"],
                "reign_label": pair(f"在位 {start_year}–{end_year}" if start_year is not None and end_year is not None else "", converter),
                "reign_start_year": start_year,
                "reign_end_year": end_year,
                "actual_reign_start_year": start_year,
                "actual_reign_end_year": end_year,
                "start_year_ce": start_year,
                "end_year_ce": end_year,
                "era_names": era_names,
                "phase_ids": sorted({
                    phase_id
                    for period in periods
                    for phase_id, phase in phase_by_id(coordinates).items()
                    if isinstance(phase, Mapping)
                    and isinstance(phase.get("approximate_start_year"), int)
                    and isinstance(phase.get("approximate_end_year"), int)
                    and isinstance(period.get("start_year_ce"), int)
                    and int(phase["approximate_start_year"]) <= int(period["end_year_ce"])
                    and int(phase["approximate_end_year"]) >= int(period["start_year_ce"])
                }),
                "era_context": {
                    "text": pair(str(definition["context_note_original"]), converter),
                    "evidence_ids": context_evidence_ids,
                    "assertion_status": "inferred",
                    "review_status": "candidate",
                },
                "ruler_story_links": story_links,
                "story_ids": ordered_story_ids(story_by_id, anchors_by_story, set(linked_story_ids)),
                "person_intersections": intersections,
                "historical_event_ids": event_ids,
                "evidence_ids": context_evidence_ids,
                "source_evidence_ids": sorted({value for link in story_links for value in link.get("source_evidence_ids", []) if isinstance(value, str)}),
                "orientation_precision": "ruler_reign",
                "review_status": "candidate",
                "selection_note": "纳入当前 83 则生产故事中有明确、经 H0A 审核的故事局部君主证据的最小 pilot 集合。",
            }
        )

    # E0.1 adds a reader orientation for every Story without changing the
    # H0A historical assertion.  The selection is deliberately separate:
    # direct ruler evidence wins, then a reviewed H0A coordinate or product
    # phase, and finally a neutral corpus card.  In particular, this code
    # never turns a referenced/off-frame Person into Story-time evidence.
    w3_by_story: dict[str, Mapping[str, Any]] = {}
    if W3_EXPANSION_PATH.is_file():
        w3_doc = read_json(W3_EXPANSION_PATH)
        w3_by_story = {
            str(item["story_id"]): item
            for item in w3_doc.get("records", [])
            if isinstance(item, Mapping) and isinstance(item.get("story_id"), str)
        }
    activities_by_story: dict[str, list[Mapping[str, Any]]] = {}
    for activity in activities:
        story_id = activity.get("story_id")
        if isinstance(story_id, str):
            activities_by_story.setdefault(story_id, []).append(activity)
    events_by_id = {
        str(event.get("event_id")): event
        for event in events
        if isinstance(event, Mapping) and isinstance(event.get("event_id"), str)
    }
    cards_by_ruler = {
        str(card["ruler_id"]): card
        for card in cards
        if card.get("card_kind") == "ruler_reign" and isinstance(card.get("ruler_id"), str)
    }
    direct_ruler_story_ids: dict[str, set[str]] = {}
    for card in cards:
        if card.get("card_kind") != "ruler_reign":
            continue
        for link in card.get("ruler_story_links", []):
            if isinstance(link, Mapping) and link.get("link_type") == "appears" and isinstance(link.get("story_id"), str):
                direct_ruler_story_ids.setdefault(str(link["story_id"]), set()).add(str(card["ruler_id"]))

    orientation_selection: dict[str, dict[str, Any]] = {}
    broad_story_ids: dict[str, set[str]] = {}
    corpus_story_ids: set[str] = set()
    for story_id in sorted(story_by_id, key=lambda item: story_order_key(story_by_id, anchors_by_story, item)):
        anchor = anchors_by_story.get(story_id, {})
        present_ids = set(present_person_ids(bundle, story_id))
        activity_support = [
            activity
            for activity in activities_by_story.get(story_id, [])
            if isinstance(activity.get("person_id"), str) and str(activity["person_id"]) in present_ids
        ]
        direct_rulers = direct_ruler_story_ids.get(story_id, set())
        if len(direct_rulers) == 1:
            ruler_id = next(iter(direct_rulers))
            orientation_selection[story_id] = {
                "card_kind": "ruler_reign",
                "era_card_id": str(cards_by_ruler[ruler_id]["era_card_id"]),
                "orientation_basis": "direct_ruler",
                "ruler_context_id": next(
                    (
                        context_id
                        for context_id, definition in SAFE_RULERS.items()
                        if definition.get("ruler_id") == ruler_id
                    ),
                    None,
                ),
                "activity_support": activity_support,
            }
            continue
        anchor_context = anchor.get("ruler_context_id")
        if (
            isinstance(anchor_context, str)
            and anchor_context in SAFE_RULERS
            and anchor.get("review_status") == "reviewed"
            and SAFE_RULERS[anchor_context]["ruler_id"] in cards_by_ruler
        ):
            ruler_id = str(SAFE_RULERS[anchor_context]["ruler_id"])
            orientation_selection[story_id] = {
                "card_kind": "ruler_reign",
                "era_card_id": str(cards_by_ruler[ruler_id]["era_card_id"]),
                "orientation_basis": "reviewed_reign_anchor",
                "ruler_context_id": anchor_context,
                "activity_support": activity_support,
            }
            continue

        window_id = broad_window_for_story(story_id, anchor, w3_by_story, events_by_id)
        if window_id is not None:
            if activity_support and not anchor.get("phase_id") and not anchor.get("event_ids"):
                basis = "participant_activity_intersection"
            elif anchor.get("review_status") == "reviewed" and anchor.get("precision") not in {None, "unknown"}:
                basis = "reviewed_temporal_anchor"
            else:
                basis = "historical_phase"
            selection = {
                "card_kind": "broad_period",
                "era_card_id": str(BROAD_WINDOW_SPECS[window_id]["era_card_id"]),
                "orientation_basis": basis,
                "ruler_context_id": None,
                "activity_support": activity_support,
                "window_id": window_id,
            }
            orientation_selection[story_id] = selection
            broad_story_ids.setdefault(window_id, set()).add(story_id)
            continue

        orientation_selection[story_id] = {
            "card_kind": "corpus_context",
            "era_card_id": CORPUS_CARD_SPEC["era_card_id"],
            "orientation_basis": "corpus_context_fallback",
            "ruler_context_id": None,
            "activity_support": activity_support,
        }
        corpus_story_ids.add(story_id)

    def broad_sort_key(window_id: str) -> tuple[Any, ...]:
        if window_id.startswith("phase-"):
            start, _ = phase_interval(coordinates, window_id)
            return (start is None, start if isinstance(start, int) else 10**9, window_id)
        return (False, 318 if window_id == "east-jin-early" else 376 if window_id == "east-jin-late" else 10**9, window_id)

    for window_id in sorted(broad_story_ids, key=broad_sort_key):
        cards.append(
            build_broad_window(
                window_id,
                coordinates,
                broad_story_ids[window_id],
                story_by_id,
                anchors_by_story,
                bundle,
                events,
                story_basis={
                    story_id: str(orientation_selection[story_id]["orientation_basis"])
                    for story_id in broad_story_ids[window_id]
                },
            )
        )

    if corpus_story_ids:
        corpus_evidence_ids = sorted({
            str(evidence_id)
            for story_id in corpus_story_ids
            for evidence_id in story_by_id.get(story_id, {}).get("evidence_ids", [])
            if isinstance(evidence_id, str)
        })
        corpus_card = {
            "era_card_id": CORPUS_CARD_SPEC["era_card_id"],
            "card_kind": "corpus_context",
            "ruler_id": None,
            "title": pair(str(CORPUS_CARD_SPEC["label"]), converter),
            "label": pair(str(CORPUS_CARD_SPEC["label"]), converter),
            "orientation_label": pair(str(CORPUS_CARD_SPEC["label"]), converter),
            "personal_name": None,
            "polity": None,
            "reign_label": pair("", converter),
            "reign_start_year": None,
            "reign_end_year": None,
            "actual_reign_start_year": None,
            "actual_reign_end_year": None,
            "start_year_ce": None,
            "end_year_ce": None,
            "era_names": [],
            "phase_ids": [],
            "era_context": {
                "text": pair(str(CORPUS_CARD_SPEC["context"]), converter),
                "evidence_ids": corpus_evidence_ids,
                "assertion_status": "inferred",
                "review_status": "candidate",
            },
            "ruler_story_links": [],
            "story_ids": ordered_story_ids(story_by_id, anchors_by_story, corpus_story_ids),
            "person_intersections": participant_intersections(
                bundle,
                story_by_id,
                corpus_story_ids,
                derivation_basis="assigned_story_scene_participants",
                anchors_by_story=anchors_by_story,
            ),
            "historical_event_ids": [],
            "evidence_ids": corpus_evidence_ids,
            "source_evidence_ids": corpus_evidence_ids,
            "orientation_precision": "corpus_context",
            "review_status": "candidate",
            "selection_note": "没有足以缩小年代的本地证据时提供中性的《世说》阅读入口；不构成历史断代。",
            "story_basis": {story_id: "corpus_context_fallback" for story_id in sorted(corpus_story_ids)},
        }
        cards.append(corpus_card)

    card_by_id = {str(card["era_card_id"]): card for card in cards}
    orientation_records: list[dict[str, Any]] = []
    for story_id in sorted(orientation_selection, key=lambda item: story_order_key(story_by_id, anchors_by_story, item)):
        selection = orientation_selection[story_id]
        card = card_by_id[str(selection["era_card_id"])]
        anchor = anchors_by_story.get(story_id, {})
        activity_support = selection.get("activity_support", [])
        supporting_activity_ids = sorted({
            str(activity["anchor_id"])
            for activity in activity_support
            if isinstance(activity.get("anchor_id"), str)
        })
        supporting_people = present_person_ids(bundle, story_id)
        evidence_ids = sorted({
            str(evidence_id)
            for evidence_id in anchor.get("evidence_ids", [])
            if isinstance(evidence_id, str)
        } | {
            str(evidence_id)
            for activity in activity_support
            for evidence_id in activity.get("evidence_ids", [])
            if isinstance(evidence_id, str)
        })
        h0a_precision = str(anchor.get("precision", "unknown"))
        basis = str(selection["orientation_basis"])
        orientation_records.append(
            {
                "story_id": story_id,
                "primary_era_card_id": str(card["era_card_id"]),
                "card_kind": str(card["card_kind"]),
                "orientation_precision": str(card["orientation_precision"]),
                "orientation_basis": basis,
                "label": card["orientation_label"],
                "h0a_anchor_id": anchor.get("anchor_id"),
                "h0a_precision": h0a_precision,
                "supporting_person_ids": supporting_people,
                "supporting_activity_anchor_ids": supporting_activity_ids,
                "ruler_context_id": selection.get("ruler_context_id"),
                "event_ids": sorted({str(value) for value in anchor.get("event_ids", []) if isinstance(value, str)}),
                "evidence_ids": evidence_ids,
                "assertion_status": "attested" if basis in {"direct_ruler", "reviewed_reign_anchor", "reviewed_temporal_anchor"} else "inferred",
                "review_status": "reviewed" if basis in {"direct_ruler", "reviewed_reign_anchor"} else "candidate",
                "confidence": "high" if basis in {"direct_ruler", "reviewed_reign_anchor"} else "medium" if basis != "corpus_context_fallback" else "low",
                "rationale": (
                    "故事正文有已审核的故事时君主证据，故以该君主在位窗口作为主要阅读定位。"
                    if basis == "direct_ruler"
                    else "H0A 已审核的君主／在位证据支持这一纪元入口，但不改写 StoryTemporalAnchor。"
                    if basis == "reviewed_reign_anchor"
                    else "沿用已有 H0A／W3 阶段或事件坐标作为宽泛阅读定位，不主张精确年份。"
                    if basis in {"reviewed_temporal_anchor", "historical_phase"}
                    else "当前本地证据不足以缩小年代，保留中性的《世说》时代入口。"
                ),
            }
        )

    cards.sort(key=lambda card: (
        card.get("start_year_ce") is None,
        card.get("start_year_ce") if isinstance(card.get("start_year_ce"), int) else 10**9,
        card.get("end_year_ce") if isinstance(card.get("end_year_ce"), int) else 10**9,
        str(card.get("era_card_id")),
    ))

    metrics = {
        "schema": 1,
        "stage": "e0-1-universal-era-orientation-metrics",
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
    metrics["universal_orientation"] = {
        "story_count": len(orientation_records),
        "by_card_kind": {
            card_kind: sum(item["card_kind"] == card_kind for item in orientation_records)
            for card_kind in ("ruler_reign", "broad_period", "corpus_context")
        },
        "by_orientation_basis": {
            basis: sum(item["orientation_basis"] == basis for item in orientation_records)
            for basis in sorted({str(item["orientation_basis"]) for item in orientation_records})
        },
        "ruler_cards": sum(item["card_kind"] == "ruler_reign" for item in orientation_records),
        "broad_cards": sum(item["card_kind"] == "broad_period" for item in orientation_records),
        "corpus_fallback": sum(item["card_kind"] == "corpus_context" for item in orientation_records),
        "h0a_unknown_with_orientation": sum(
            item["h0a_precision"] == "unknown" for item in orientation_records
        ),
        "h0a_precision_unchanged": True,
    }
    return identities, cards, projected_events, metrics, orientation_records


def build() -> dict[str, Any]:
    bundle = read_json(SC1_PATH)
    coordinates = read_json(COORDINATES_PATH)
    anchors_doc = read_json(ANCHORS_PATH)
    temporal_doc = read_json(TEMPORAL_EVIDENCE_PATH)
    events_doc = read_json(EVENTS_PATH)
    activities_doc = read_json(ACTIVITY_PATH) if ACTIVITY_PATH.is_file() else {}
    anchors = [item for item in anchors_doc.get("records", []) if isinstance(item, Mapping)]
    temporal_evidence = [item for item in temporal_doc.get("records", []) if isinstance(item, Mapping)]
    events = [item for item in events_doc.get("records", []) if isinstance(item, Mapping)]
    activities = [item for item in activities_doc.get("records", []) if isinstance(item, Mapping)]
    audit, _anchor_by_story = build_audit(bundle, coordinates, temporal_evidence, anchors)
    identities, cards, projected_events, metrics, orientation_records = build_projection(
        bundle, coordinates, anchors, temporal_evidence, events, activities, audit
    )
    write_json(IDENTITIES_PATH, {"schema": 1, "stage": "e0-ruler-identity-registry", "records": identities})
    write_json(CARDS_PATH, {"schema": 1, "stage": "e0-1-era-card-orientation", "records": cards})
    write_json(
        ORIENTATION_PATH,
        {
            "schema": 1,
            "stage": "e0-story-era-orientation",
            "scope": {
                "story_count": len(bundle.get("stories", [])),
                "story_ids": [
                    item.get("id")
                    for item in bundle.get("stories", [])
                    if isinstance(item, Mapping)
                ],
            },
            "records": orientation_records,
            "policy": "StoryTemporalAnchor 是历史断代结果；StoryEraOrientation 是每则故事的阅读入口，允许宽泛阶段或中性 corpus_context。",
        },
    )
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
        "generated_from": [str(path.relative_to(ROOT)) for path in (SC1_PATH, COORDINATES_PATH, TEMPORAL_EVIDENCE_PATH, ANCHORS_PATH, EVENTS_PATH, ACTIVITY_PATH, W3_EXPANSION_PATH)],
        "ruler_identities": identities,
        "era_cards": cards,
        "ruler_mentions": [item for item in audit if item.get("resolution_status") == "resolved" and item.get("era_card_exists")],
        "historical_events": projected_events,
        "story_era_orientations": orientation_records,
    }
    write_json(PROJECTION_PATH, projection)
    write_json(METRICS_PATH, metrics)
    return projection


if __name__ == "__main__":
    result = build()
    print(
        "built E0.1 universal Era orientation: "
        f"{len(result['era_cards'])} cards; "
        f"{len(result['ruler_mentions'])} clickable ruler mentions"
    )
