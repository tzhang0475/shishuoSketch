#!/usr/bin/env python3
"""Build the H0A historical temporal backbone.

H0A is intentionally evidence-first.  It creates a reusable coordinate layer,
audits every currently published Story, records only source-local temporal
surfaces, and produces exactly one conservative StoryTemporalAnchor per Story.
It does not edit canonical source text, identity decisions, Relations, or
publication manifests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / "data/derived/sc1-site.json"
W3_PATH = ROOT / "data/annotation/story-expansion-wave-3.json"
ZTJ_INDEX_PATH = ROOT / "data/derived/ztj0-chronology-index.json"
ZTJ_MANIFEST_PATH = ROOT / "data/derived/ztj0-processed-corpus.json"
SGZ_MANIFEST_PATH = ROOT / "data/derived/sgz0-processed-corpus.json"
ZTJ_VOLUME_DIR = ROOT / "content/processed/zizhi-tongjian/volumes"
KAOYI_DIR = ROOT / "content/processed/zizhi-tongjian/kaoyi"
COORDINATES_PATH = ROOT / "data/derived/h0a-temporal-coordinates.json"
EVIDENCE_PATH = ROOT / "data/annotation/story-temporal-evidence-h0a.json"
EVENTS_PATH = ROOT / "data/annotation/historical-events-h0a.json"
ACTIVITY_PATH = ROOT / "data/annotation/person-activity-anchors-h0a.json"
ANCHORS_PATH = ROOT / "data/annotation/story-temporal-anchors-h0a.json"
GAP_PATH = ROOT / "data/derived/h0a-temporal-gap-audit.json"
METRICS_PATH = ROOT / "data/derived/h0a-metrics.json"
DOC_PATH = ROOT / "docs/h0a-historical-temporal-backbone.md"
POLICY_DOC_PATH = ROOT / "docs/h0a-temporal-resolution-policy.md"
GAP_DOC_PATH = ROOT / "docs/h0a-temporal-gap-audit.md"

SCHEMA = 1

PHASES: list[dict[str, Any]] = [
    {
        "phase_id": "phase-1",
        "label_zh": "漢末餘緒／魏初",
        "approximate_start_year": 184,
        "approximate_end_year": 239,
        "definition_note": "產品導向的漢末至魏初定位帶；不是精確年代斷限。",
        "evidence_basis": ["data/derived/c0-chronological-coverage.json", "W3 frozen phase metadata"],
        "assertion_status": "inferred",
        "review_status": "candidate",
    },
    {
        "phase_id": "phase-2",
        "label_zh": "正始與曹魏後期",
        "approximate_start_year": 240,
        "approximate_end_year": 265,
        "definition_note": "正始至曹魏後期的產品定位帶；不把產品分期当作唯一史學分期。",
        "evidence_basis": ["data/derived/c0-chronological-coverage.json", "W3 frozen phase metadata"],
        "assertion_status": "inferred",
        "review_status": "candidate",
    },
    {
        "phase_id": "phase-3",
        "label_zh": "竹林—西晉初",
        "approximate_start_year": 266,
        "approximate_end_year": 290,
        "definition_note": "竹林人物及西晉初年的產品定位帶。",
        "evidence_basis": ["data/derived/c0-chronological-coverage.json", "W3 frozen phase metadata"],
        "assertion_status": "inferred",
        "review_status": "candidate",
    },
    {
        "phase_id": "phase-4",
        "label_zh": "西晉後期—永嘉南渡",
        "approximate_start_year": 291,
        "approximate_end_year": 317,
        "definition_note": "西晉後期、永嘉動亂及南渡前後的產品定位帶。",
        "evidence_basis": ["data/derived/c0-chronological-coverage.json", "W3 frozen phase metadata"],
        "assertion_status": "inferred",
        "review_status": "candidate",
    },
    {
        "phase_id": "phase-5",
        "label_zh": "東晉",
        "approximate_start_year": 318,
        "approximate_end_year": 420,
        "definition_note": "東晉產品閱讀範圍；不宣稱覆蓋東晉全部政治史。",
        "evidence_basis": ["data/derived/c0-chronological-coverage.json", "W3 frozen phase metadata"],
        "assertion_status": "inferred",
        "review_status": "candidate",
    },
]

# These are only the eras actually needed to normalize the Wei–Jin surfaces
# exposed by ZTJ0.  The table is deliberately narrower than a full Chinese
# chronology and is never used to force Story dates without local evidence.
ERA_PERIODS: dict[tuple[str, str], tuple[int, int]] = {
    ("漢", "建安"): (196, 220),
    ("魏", "黃初"): (220, 226),
    ("魏", "太和"): (227, 233),
    ("魏", "青龍"): (233, 237),
    ("魏", "景初"): (237, 239),
    ("魏", "正始"): (240, 249),
    ("魏", "嘉平"): (249, 254),
    ("魏", "甘露"): (256, 260),
    ("魏", "景元"): (260, 264),
    ("魏", "咸熙"): (264, 265),
    ("晉", "泰始"): (265, 274),
    ("晉", "咸寧"): (275, 280),
    ("晉", "太康"): (280, 289),
    ("晉", "太熙"): (290, 290),
    ("晉", "元康"): (291, 299),
    ("晉", "永康"): (300, 300),
    ("晉", "永寧"): (301, 301),
    ("晉", "太安"): (302, 303),
    ("晉", "永興"): (304, 305),
    ("晉", "光熙"): (306, 306),
    ("晉", "永嘉"): (307, 313),
    ("晉", "建興"): (313, 317),
    ("晉", "建武"): (317, 317),
    ("晉", "大興"): (318, 321),
    ("晉", "永昌"): (322, 322),
    ("晉", "太寧"): (323, 326),
    ("晉", "咸和"): (326, 334),
    ("晉", "咸康"): (335, 342),
    ("晉", "建元"): (343, 344),
    ("晉", "永和"): (345, 356),
    ("晉", "升平"): (357, 361),
    ("晉", "隆和"): (362, 363),
    ("晉", "興寧"): (363, 365),
    ("晉", "太和"): (366, 371),
    ("晉", "咸安"): (371, 372),
    ("晉", "寧康"): (373, 375),
    ("晉", "太元"): (376, 396),
    ("晉", "隆安"): (397, 401),
    ("晉", "元興"): (402, 404),
    ("晉", "義熙"): (405, 418),
    ("晉", "元熙"): (419, 420),
}

ERA_NAME_ALIASES = {
    "黄初": "黃初",
    "太寜": "太寧",
    "義熈": "義熙",
    "义熙": "義熙",
}
KNOWN_ERA_NAMES = sorted(
    {
        "建安", "黃初", "黄初", "太和", "青龍", "景初", "正始", "嘉平", "甘露", "景元", "咸熙",
        "泰始", "咸寧", "太康", "太熙", "元康", "永康", "永寧", "太安", "永興", "光熙", "永嘉",
        "建興", "建武", "大興", "永昌", "太寧", "咸和", "咸康", "建元", "永和", "升平", "隆和",
        "興寧", "咸安", "寧康", "太元", "隆安", "元興", "義熙", "義熈", "元熙",
        # Han surfaces are retained as chronology coordinates when observed.
        "中平", "光和", "初平", "興平", "建安", "延康", "黃初", "建武", "永平", "永元",
    },
    key=len,
    reverse=True,
)

CHINESE_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}

EVENT_CATALOG: list[dict[str, Any]] = [
    {
        "event_id": "event-wang-dun-rebellion",
        "canonical_name": "王敦之亂",
        "aliases": ["王敦討劉隗", "王敦既下", "王敦引軍", "大將軍作亂"],
        "start_year_ce": 322,
        "end_year_ce": 324,
        "date_precision": "year_range",
        "phase_ids": ["phase-5"],
        "scope_note": "只在本地證據明確指向王敦舉兵或相關後果時使用。",
    },
    {
        "event_id": "event-su-jun-rebellion",
        "canonical_name": "蘇峻之亂",
        "aliases": ["蘇峻之難", "蘇峻之亂", "蘇峻時", "遭蘇峻", "為蘇峻"],
        "start_year_ce": 328,
        "end_year_ce": 329,
        "date_precision": "year_range",
        "phase_ids": ["phase-5"],
        "scope_note": "事件邊界僅表示本則與蘇峻之亂相連，不把同場人物自動變成 Relation。",
    },
    {
        "event_id": "event-yongjia-upheaval",
        "canonical_name": "永嘉之亂與南渡",
        "aliases": ["永嘉之中", "永嘉流", "遭亂渡江", "後遭亂渡江"],
        "start_year_ce": 307,
        "end_year_ce": 317,
        "date_precision": "year_range",
        "phase_ids": ["phase-4"],
        "scope_note": "用作動亂／南渡背景，不把背景提及當作本則精確年份。",
    },
    {
        "event_id": "event-eight-princes-disturbance",
        "canonical_name": "八王之亂",
        "aliases": ["八王故事", "八王之亂"],
        "start_year_ce": 291,
        "end_year_ce": 306,
        "date_precision": "year_range",
        "phase_ids": ["phase-4"],
        "scope_note": "僅保留為歷史參照事件；引用本身不約束故事時間。",
    },
    {
        "event_id": "event-sun-en-rebellion",
        "canonical_name": "孫恩之亂",
        "aliases": ["孫恩作亂"],
        "start_year_ce": 399,
        "end_year_ce": 402,
        "date_precision": "year_range",
        "phase_ids": ["phase-5"],
        "scope_note": "目前只作为刘注中的后续事件证据。",
    },
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def stable_id(prefix: str, *parts: object) -> str:
    raw = "\x1f".join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def parse_chinese_number(value: str) -> int | None:
    value = value.replace("廿", "二十").replace("卅", "三十")
    if value in {"元", "一"}:
        return 1
    if value.isdigit():
        return int(value)
    if not value:
        return None
    total = 0
    section = 0
    number = 0
    for char in value:
        if char in CHINESE_DIGITS:
            number = CHINESE_DIGITS[char]
        elif char == "十":
            section += (number or 1) * 10
            number = 0
        elif char == "百":
            section += (number or 1) * 100
            number = 0
        else:
            return None
    return total + section + number if total + section + number > 0 else None


def normalize_era_name(value: str) -> str:
    return ERA_NAME_ALIASES.get(value, value)


def parse_era_surface(surface: str) -> tuple[str, int, str] | None:
    for name in KNOWN_ERA_NAMES:
        match = re.search(re.escape(name) + r"(?P<number>元|[一二兩三四五六七八九十百廿卅〇0-9]+)年", surface)
        if not match:
            continue
        number = parse_chinese_number(match.group("number"))
        if number is None:
            continue
        return normalize_era_name(name), number, match.group(0)
    return None


def polity_from_chronicle(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("魏"):
        return "魏"
    if value.startswith("晉") or value.startswith("晋"):
        return "晉"
    if value.startswith("漢") or value.startswith("汉"):
        return "漢"
    return None


def phase_for_year(year: int | None) -> str | None:
    if year is None:
        return None
    for phase in PHASES:
        if phase["approximate_start_year"] <= year <= phase["approximate_end_year"]:
            return str(phase["phase_id"])
    return None


def phase_map() -> dict[str, dict[str, Any]]:
    return {str(item["phase_id"]): item for item in PHASES}


def source_evidence_ids(bundle: Mapping[str, Any], story_id: str, section: str, annotation_id: str | None) -> list[str]:
    wanted = (
        f"evidence-sc1-{story_id}-{annotation_id}"
        if section == "liu_annotation" and annotation_id
        else f"evidence-sc1-{story_id}-main"
    )
    evidence_ids = {str(item.get("id")) for item in bundle.get("evidence", []) if isinstance(item, Mapping)}
    return [wanted] if wanted in evidence_ids else []


def add_temporal_evidence(
    records: list[dict[str, Any]],
    bundle: Mapping[str, Any],
    *,
    story_id: str,
    section: str,
    annotation_id: str | None,
    text: str,
    start: int,
    end: int,
    evidence_type: str,
    normalized_candidate: Any,
    relation_to_story: str,
    assertion_status: str,
    review_status: str,
    confidence: str,
    notes: str,
) -> dict[str, Any]:
    raw_surface = text[start:end]
    record_id = stable_id(
        "h0a-evidence",
        story_id,
        section,
        annotation_id or "",
        start,
        end,
        evidence_type,
        raw_surface,
        normalized_candidate,
        relation_to_story,
    )
    record = {
        "evidence_record_id": record_id,
        "story_id": story_id,
        "source_layer": section,
        "source_id": "shishuo-kanripo-wyg",
        "source_span": {
            "kind": "published_story_layer",
            "section": section,
            "annotation_id": annotation_id,
            "char_start": start,
            "char_end_exclusive": end,
        },
        "source_evidence_ids": source_evidence_ids(bundle, story_id, section, annotation_id),
        "evidence_type": evidence_type,
        "raw_surface": raw_surface,
        "normalized_candidate": normalized_candidate,
        "relation_to_story": relation_to_story,
        "assertion_status": assertion_status,
        "review_status": review_status,
        "confidence": confidence,
        "notes": notes,
    }
    records.append(record)
    return record


def text_layers(story: Mapping[str, Any]) -> Iterable[tuple[str, str, str | None]]:
    yield "main_text", str(story.get("text", "")), None
    for annotation in story.get("annotations", []):
        if isinstance(annotation, Mapping):
            yield "liu_annotation", str(annotation.get("text", "")), str(annotation.get("id"))


def event_match_relation(event_id: str, section: str, text: str, start: int) -> str:
    before = text[max(0, start - 10):start]
    after = text[start:start + 18]
    window = before + after
    if event_id == "event-yongjia-upheaval" and ("永嘉之中" in window or "永嘉流" in window or "後遭亂渡江" in window):
        return "earlier_background" if "後遭亂渡江" in window else "event_context"
    if event_id == "event-eight-princes-disturbance":
        return "earlier_background"
    if event_id == "event-sun-en-rebellion":
        return "later_outcome" if section == "liu_annotation" else "event_context"
    if event_id == "event-su-jun-rebellion":
        if "遇害" in window or "兒" in before or "改適" in window:
            return "later_outcome" if "遇害" in window or section == "liu_annotation" else "event_context"
        return "direct_story_time" if section == "main_text" else "event_context"
    if event_id == "event-wang-dun-rebellion":
        if "墓" in window or "所歎" in window:
            return "earlier_background"
        if "作亂" in window and ("俄而" in before or "如其所言" in window):
            return "later_outcome"
        return "direct_story_time" if section == "main_text" else "event_context"
    return "event_context"


def build_coordinates(ztj_index: Mapping[str, Any]) -> dict[str, Any]:
    observations: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    era_year_observations: dict[tuple[str, str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for record in ztj_index.get("records", []):
        if not isinstance(record, Mapping):
            continue
        polity = polity_from_chronicle(record.get("chronicle_name"))
        if not polity:
            continue
        for surface in record.get("era_year_surface_candidates", []):
            parsed = parse_era_surface(str(surface))
            if not parsed:
                continue
            era_name, year_number, raw_surface = parsed
            key = (polity, str(record.get("ruler_surface") or ""), era_name)
            observation = {
                "block_id": record.get("block_id"),
                "volume": record.get("volume"),
                "source_file": record.get("source_file"),
                "surface": raw_surface,
                "source_span": record.get("source_span"),
            }
            observations[key].append(observation)
            era_year_observations[(polity, str(record.get("ruler_surface") or ""), era_name, year_number)].append(observation)

    reigns: list[dict[str, Any]] = []
    reign_by_key: dict[tuple[str, str, str], str] = {}
    for key in sorted(observations):
        polity, ruler, era_name = key
        start, end = ERA_PERIODS.get((polity, era_name), (None, None))
        reign_id = stable_id("h0a-reign", polity, ruler, era_name)
        reign_by_key[key] = reign_id
        reigns.append(
            {
                "reign_id": reign_id,
                "polity": polity,
                "ruler_name": ruler or None,
                "era_name": era_name,
                "start_year_ce": start,
                "end_year_ce": end,
                "evidence_refs": [
                    {"source": "ztj0-chronology-index", **item}
                    for item in sorted(observations[key], key=lambda item: (int(item.get("volume") or 0), str(item.get("block_id"))))
                ],
                "assertion_status": "attested",
                "review_status": "candidate" if start is None else "reviewed",
                "notes": "由 ZTJ0 實際紀年標題觀察；年份正規化只用於座標層，不直接給 Story 定年。",
            }
        )

    era_years: list[dict[str, Any]] = []
    for key in sorted(era_year_observations):
        polity, ruler, era_name, year_number = key
        reign_id = reign_by_key[(polity, ruler, era_name)]
        period = ERA_PERIODS.get((polity, era_name))
        year_ce = period[0] + year_number - 1 if period else None
        era_years.append(
            {
                "era_year_id": stable_id("h0a-era-year", reign_id, year_number),
                "reign_id": reign_id,
                "era_year_number": year_number,
                "year_ce": year_ce,
                "source_surfaces": sorted({str(item["surface"]) for item in era_year_observations[key]}),
                "evidence_refs": [
                    {"source": "ztj0-chronology-index", **item}
                    for item in sorted(era_year_observations[key], key=lambda item: (int(item.get("volume") or 0), str(item.get("block_id"))))
                ],
                "assertion_status": "attested",
                "review_status": "reviewed" if year_ce is not None else "candidate",
                "notes": "保留 ZTJ 表面；不涉及傳統曆法日級換算。",
            }
        )

    return {
        "schema": SCHEMA,
        "stage": "h0a-temporal-coordinate-layer",
        "coordinate_policy": "Reuse W3/C0 product phase IDs; derive reign/era surfaces from observed ZTJ0 chronology headings; normalize only deterministic year coordinates.",
        "phases": PHASES,
        "reign_periods": reigns,
        "era_years": era_years,
        "source_basis": {
            "ztj0_chronology_index": "data/derived/ztj0-chronology-index.json",
            "c0_phase_basis": "data/derived/c0-chronological-coverage.json",
            "no_gregorian_day_conversion": True,
        },
    }


def build_evidence_and_anchors(
    bundle: Mapping[str, Any],
    coordinates: Mapping[str, Any],
    w3: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    phase_by_id = phase_map()
    w3_by_story = {
        str(item.get("story_id")): item
        for item in w3.get("records", [])
        if isinstance(item, Mapping) and isinstance(item.get("story_id"), str)
    }
    event_by_id = {str(item["event_id"]): item for item in EVENT_CATALOG}
    all_evidence: list[dict[str, Any]] = []
    per_story_evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    per_story_events: dict[str, set[str]] = defaultdict(set)
    per_story_era_years: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)

    for story in sorted(bundle.get("stories", []), key=lambda item: str(item.get("id"))):
        story_id = str(story["id"])
        for section, text, annotation_id in text_layers(story):
            # Only known era names are considered.  Generic “某年” and
            # numeric prose never become temporal coordinates.
            era_spans: list[tuple[int, int]] = []
            for match in re.finditer(r"[\u4e00-龥]{1,8}(?:元|[一二兩三四五六七八九十百廿卅〇0-9]+)年", text):
                parsed = parse_era_surface(match.group(0))
                if not parsed:
                    continue
                era_spans.append((match.start(), match.end()))
                era_name, year_number, raw_surface = parsed
                relation = "direct_story_time" if section == "main_text" else "earlier_background"
                if story_id == "06-yaliang-017" and era_name == "咸和":
                    relation = "later_outcome"
                evidence = add_temporal_evidence(
                    all_evidence,
                    bundle,
                    story_id=story_id,
                    section=section,
                    annotation_id=annotation_id,
                    text=text,
                    start=match.start(),
                    end=match.end(),
                    evidence_type="era_year",
                    normalized_candidate={"era_name": era_name, "era_year_number": year_number, "surface": raw_surface},
                    relation_to_story=relation,
                    assertion_status="attested",
                    review_status="candidate",
                    confidence="high" if relation == "direct_story_time" else "medium",
                    notes="保留故事层原始纪年表面；注中后世年岁不自动回填为本则发生年。",
                )
                per_story_evidence[story_id].append(evidence)
                for era_year in coordinates.get("era_years", []):
                    if raw_surface in era_year.get("source_surfaces", []) and era_year.get("era_year_number") == year_number:
                        per_story_era_years[story_id].append((evidence, era_year))
                        break

            # Some Liu witnesses split a year surface across annotation
            # blocks, as in 06-yaliang-017's “咸和/…/六年”.  Preserve the
            # explicit era-name evidence without fabricating an exact year.
            for era_name_surface in KNOWN_ERA_NAMES:
                start = 0
                while True:
                    found = text.find(era_name_surface, start)
                    if found < 0:
                        break
                    if any(span_start <= found < span_end for span_start, span_end in era_spans):
                        start = found + len(era_name_surface)
                        continue
                    relation = "direct_story_time" if section == "main_text" else "earlier_background"
                    if story_id == "06-yaliang-017" and era_name_surface == "咸和":
                        relation = "later_outcome"
                    evidence = add_temporal_evidence(
                        all_evidence,
                        bundle,
                        story_id=story_id,
                        section=section,
                        annotation_id=annotation_id,
                        text=text,
                        start=found,
                        end=found + len(era_name_surface),
                        evidence_type="reign_reference",
                        normalized_candidate={"era_name": normalize_era_name(era_name_surface)},
                        relation_to_story=relation,
                        assertion_status="attested",
                        review_status="candidate",
                        confidence="medium" if relation != "direct_story_time" else "high",
                        notes="保留被正文或刘注明确写出的年号表面；未将分散的年号与年数拼成未经证实的精确年。",
                    )
                    per_story_evidence[story_id].append(evidence)
                    start = found + len(era_name_surface)

            for event in EVENT_CATALOG:
                event_id = str(event["event_id"])
                aliases = sorted((str(alias) for alias in event.get("aliases", [])), key=len, reverse=True)
                for alias in aliases:
                    start = 0
                    while True:
                        found = text.find(alias, start)
                        if found < 0:
                            break
                        relation = event_match_relation(event_id, section, text, found)
                        evidence = add_temporal_evidence(
                            all_evidence,
                            bundle,
                            story_id=story_id,
                            section=section,
                            annotation_id=annotation_id,
                            text=text,
                            start=found,
                            end=found + len(alias),
                            evidence_type="historical_event_reference",
                            normalized_candidate={"event_id": event_id, "event_name": event["canonical_name"]},
                            relation_to_story=relation,
                            assertion_status="attested",
                            review_status="candidate",
                            confidence="high" if relation == "direct_story_time" else "medium",
                            notes="事件表面只作为时间证据候选；背景、后果和正文当下严格区分。",
                        )
                        per_story_evidence[story_id].append(evidence)
                        if relation in {"direct_story_time", "event_context"}:
                            per_story_events[story_id].add(event_id)
                        start = found + len(alias)

            for match in re.finditer(r"(?:渡江|過江|入洛|出洛|既過江|既過江)", text):
                relation = "direct_story_time" if section == "main_text" else "earlier_background"
                if "後" in text[max(0, match.start() - 4):match.start()] or "遭亂" in text[max(0, match.start() - 6):match.start()]:
                    relation = "later_outcome"
                evidence = add_temporal_evidence(
                    all_evidence,
                    bundle,
                    story_id=story_id,
                    section=section,
                    annotation_id=annotation_id,
                    text=text,
                    start=match.start(),
                    end=match.end(),
                    evidence_type="migration_or_crossing_anchor",
                    normalized_candidate={"surface": match.group(0)},
                    relation_to_story=relation,
                    assertion_status="attested",
                    review_status="candidate",
                    confidence="medium",
                    notes="渡江/過江只记录叙事中的迁移表面，不自动换算为年份。",
                )
                per_story_evidence[story_id].append(evidence)

            for match in re.finditer(r"(?:遇害|遭[^。！？\n]{0,4}害|薨|崩|作亂)", text):
                if any(match.start() >= int(item["source_span"]["char_start"]) and match.start() < int(item["source_span"]["char_end_exclusive"]) for item in per_story_evidence[story_id]):
                    continue
                relation = "later_outcome" if section == "liu_annotation" else "person_activity_context"
                evidence = add_temporal_evidence(
                    all_evidence,
                    bundle,
                    story_id=story_id,
                    section=section,
                    annotation_id=annotation_id,
                    text=text,
                    start=match.start(),
                    end=match.end(),
                    evidence_type="death_or_accession_anchor",
                    normalized_candidate={"surface": match.group(0)},
                    relation_to_story=relation,
                    assertion_status="attested",
                    review_status="candidate",
                    confidence="medium",
                    notes="人物后果或事件后果作为方向性证据保留，不回推故事发生年。",
                )
                per_story_evidence[story_id].append(evidence)

        w3_record = w3_by_story.get(story_id)
        if w3_record and isinstance(w3_record.get("phase_id"), str):
            phase_id = str(w3_record["phase_id"])
            phase_label = str(w3_record.get("phase_label") or phase_by_id.get(phase_id, {}).get("label_zh", ""))
            evidence = add_temporal_evidence(
                all_evidence,
                bundle,
                story_id=story_id,
                section="main_text",
                annotation_id=None,
                text=str(story.get("text", "")),
                start=0,
                end=0,
                evidence_type="phase_only_context",
                normalized_candidate={"phase_id": phase_id, "label_zh": phase_label},
                relation_to_story="direct_story_time",
                assertion_status="inferred",
                review_status="candidate",
                confidence="medium",
                notes="复用 W3 冻结的产品阶段定位；不是 H0A 对精确年份的判断。",
            )
            per_story_evidence[story_id].append(evidence)

    anchors: list[dict[str, Any]] = []
    for story in sorted(bundle.get("stories", []), key=lambda item: str(item.get("id"))):
        story_id = str(story["id"])
        records = per_story_evidence.get(story_id, [])
        direct_era = [
            (record, era_year)
            for record, era_year in per_story_era_years.get(story_id, [])
            if record.get("relation_to_story") == "direct_story_time" and era_year.get("year_ce") is not None
        ]
        event_ids = sorted(per_story_events.get(story_id, set()))
        w3_record = w3_by_story.get(story_id)
        phase_id: str | None = None
        precision = "unknown"
        start_year = None
        end_year = None
        reign_id = None
        era_year_ids: list[str] = []
        assertion_status = "unknown"
        review_status = "candidate"
        basis = "no_safe_temporal_evidence"
        rationale = "当前已处理证据不足以安全定位本则时间；保留 unknown，等待后续有针对性的史料审查。"
        conflict_flags: list[str] = []
        if len(direct_era) == 1:
            record, era_year = direct_era[0]
            precision = "exact_year"
            start_year = int(era_year["year_ce"])
            end_year = start_year
            reign_id = era_year.get("reign_id")
            era_year_ids = [str(era_year["era_year_id"])]
            phase_id = phase_for_year(start_year)
            assertion_status = "attested"
            review_status = "reviewed"
            basis = "explicit_story_local_era_year"
            rationale = "正文直接出现可与 ZTJ0 纪年坐标对应的年号年；未进行日级历法换算。"
        elif len(direct_era) > 1:
            conflict_flags.append("multiple_story_local_era_years")
            basis = "conflicting_story_local_era_evidence"
            rationale = "本则存在多个故事层纪年表面，未在没有审查的情况下选择其一。"
        elif event_ids:
            selected_event = event_by_id[event_ids[0]]
            if len(event_ids) > 1:
                conflict_flags.append("multiple_event_contexts")
            precision = "event_bounded"
            start_year = selected_event.get("start_year_ce")
            end_year = selected_event.get("end_year_ce")
            phase_id = (selected_event.get("phase_ids") or [None])[0]
            assertion_status = "inferred"
            review_status = "candidate"
            basis = "explicit_story_event_context"
            rationale = f"本则证据直接连接到{selected_event['canonical_name']}；显示事件范围，不把事件关联扩大为人物关系。"
        elif w3_record and isinstance(w3_record.get("phase_id"), str):
            phase_id = str(w3_record["phase_id"])
            precision = "phase_only"
            assertion_status = "inferred"
            review_status = "candidate"
            basis = "w3_frozen_phase_orientation"
            rationale = "沿用 W3/C0 的阶段定位；没有把阶段标签扩写成故事年份。"

        evidence_ids = [str(record["evidence_record_id"]) for record in records]
        if precision == "unknown" and any(record.get("relation_to_story") == "later_outcome" for record in records):
            basis = "later_outcome_does_not_date_story"
            rationale = "仅有后续命运／事件证据；按时间方向规则不回推为本则发生年。"
        if precision == "unknown" and any(record.get("relation_to_story") == "earlier_background" for record in records):
            basis = "background_reference_does_not_date_story"
            rationale = "仅有早先背景或引述，不能当作本则故事时间。"
        if conflict_flags:
            precision = "unknown"
            assertion_status = "unknown"
            review_status = "candidate"

        label = None
        if precision == "exact_year" and direct_era:
            era_year = direct_era[0][1]
            reign = next((item for item in coordinates.get("reign_periods", []) if item.get("reign_id") == era_year.get("reign_id")), None)
            if reign:
                polity_label = {"魏": "曹魏", "晉": "東晉" if (reign.get("start_year_ce") or 0) >= 318 else "西晉", "漢": "漢"}.get(reign.get("polity"), str(reign.get("polity") or ""))
                label = f"{polity_label} · {era_year.get('source_surfaces', [''])[0]}"
        elif precision == "event_bounded" and phase_id:
            phase = phase_by_id.get(phase_id, {})
            label = f"{phase.get('label_zh', '')} · {event_by_id[event_ids[0]]['canonical_name']}"
        elif precision == "phase_only" and phase_id:
            label = str(w3_record.get("phase_label") or phase_by_id.get(phase_id, {}).get("label_zh", ""))

        anchor = {
            "anchor_id": stable_id("h0a-anchor", story_id),
            "story_id": story_id,
            "precision": precision,
            "start_year_ce": start_year,
            "end_year_ce": end_year,
            "reign_id": reign_id,
            "era_year_ids": era_year_ids,
            "phase_id": phase_id,
            "event_ids": event_ids,
            "evidence_ids": evidence_ids,
            "supporting_activity_anchor_ids": [],
            "assertion_status": assertion_status,
            "review_status": review_status,
            "resolution_basis": basis,
            "rationale": rationale,
            "conflict_flags": sorted(conflict_flags),
            "reader_projection": {
                "label_zh": label,
                "show": bool(label),
                "precision": precision,
            },
        }
        anchors.append(anchor)

    return all_evidence, anchors, per_story_evidence


def build_source_chronology_refs(aliases: Iterable[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Find bounded source references without treating them as Story dates."""

    aliases = sorted(set(str(alias) for alias in aliases), key=len, reverse=True)
    chronology_refs: list[dict[str, Any]] = []
    kaoyi_refs: list[dict[str, Any]] = []
    for path in sorted(ZTJ_VOLUME_DIR.glob("volume-*.json")):
        record = read_json(path)
        for block in record.get("chronicle_blocks", []):
            if not isinstance(block, Mapping):
                continue
            main_text = str(block.get("main_text", ""))
            for alias in aliases:
                offset = main_text.find(alias)
                if offset >= 0:
                    chronology_refs.append(
                        {
                            "source_layer": "tongjian_main",
                            "volume": record.get("juan_number"),
                            "source_file": record.get("source_file"),
                            "source_sha256": record.get("source_sha256"),
                            "block_id": block.get("block_id"),
                            "surface": alias,
                            "surface_offset_in_block": offset,
                            "source_span": block.get("source_span"),
                        }
                    )
                    break
            for annotation in block.get("annotations", []):
                if not isinstance(annotation, Mapping):
                    continue
                annotation_text = str(annotation.get("text", ""))
                for alias in aliases:
                    if alias in annotation_text:
                        chronology_refs.append(
                            {
                                "source_layer": "hu_annotation",
                                "volume": record.get("juan_number"),
                                "source_file": record.get("source_file"),
                                "source_sha256": record.get("source_sha256"),
                                "block_id": block.get("block_id"),
                                "annotation_id": annotation.get("annotation_id"),
                                "surface": alias,
                                "source_span": annotation.get("source_span"),
                            }
                        )
                        break
    for path in sorted(KAOYI_DIR.glob("kaoyi-*.json")):
        record = read_json(path)
        for block in record.get("blocks", []):
            if not isinstance(block, Mapping):
                continue
            text = str(block.get("text", ""))
            for alias in aliases:
                offset = text.find(alias)
                if offset >= 0:
                    kaoyi_refs.append(
                        {
                            "source_layer": "kaoyi",
                            "kaoyi_volume": record.get("blocks", [{}])[0].get("kaoyi_volume") if record.get("blocks") else None,
                            "source_file": record.get("source_file"),
                            "source_sha256": record.get("source_sha256"),
                            "kaoyi_id": block.get("kaoyi_id"),
                            "surface": alias,
                            "surface_offset_in_block": offset,
                            "source_span": block.get("source_span"),
                        }
                    )
                    break
    chronology_refs.sort(key=lambda item: (str(item.get("source_layer")), int(item.get("volume") or 0), str(item.get("source_file")), str(item.get("annotation_id") or ""), int(item.get("surface_offset_in_block", 0))))
    kaoyi_refs.sort(key=lambda item: (int(item.get("kaoyi_volume") or 0), str(item.get("source_file")), int(item.get("surface_offset_in_block", 0))))
    return chronology_refs[:64], kaoyi_refs[:32]


def build_events(evidence: list[dict[str, Any]], ztj_index: Mapping[str, Any]) -> list[dict[str, Any]]:
    by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in evidence:
        candidate = record.get("normalized_candidate")
        if isinstance(candidate, Mapping) and isinstance(candidate.get("event_id"), str):
            by_event[str(candidate["event_id"])].append(record)
    output: list[dict[str, Any]] = []
    for definition in EVENT_CATALOG:
        event_id = str(definition["event_id"])
        records = sorted(by_event.get(event_id, []), key=lambda item: str(item["evidence_record_id"]))
        if not records:
            continue
        story_ids = sorted({str(item["story_id"]) for item in records})
        source_claims = [
            {
                "source_layer": record["source_layer"],
                "story_id": record["story_id"],
                "surface": record["raw_surface"],
                "relation_to_story": record["relation_to_story"],
                "evidence_ids": [record["evidence_record_id"]],
                "source_evidence_ids": record.get("source_evidence_ids", []),
            }
            for record in records
        ]
        # The source index is a chronology reference, not an automatic Story
        # dating authority.  Keep its role explicit in the event record.
        aliases = [str(item) for item in definition.get("aliases", [])]
        chronology_refs, kaoyi_refs = build_source_chronology_refs(aliases)
        output.append(
            {
                "event_id": event_id,
                "canonical_name": definition["canonical_name"],
                "aliases": aliases,
                "start_year_ce": definition["start_year_ce"],
                "end_year_ce": definition["end_year_ce"],
                "date_precision": definition["date_precision"],
                "phase_ids": definition["phase_ids"],
                "evidence_ids": sorted({str(item["evidence_record_id"]) for item in records}),
                "source_claims": source_claims,
                "chronology_source_refs": chronology_refs,
                "kaoyi_source_refs": kaoyi_refs,
                "chronology_status": "source_evidence_plus_bounded_coordinate" if chronology_refs else "story_evidence_bounded",
                "review_status": "candidate",
                "conflict_flags": [],
                "linked_story_ids": story_ids,
                "notes": definition["scope_note"],
            }
        )
    return output


def build_activity_anchors(bundle: Mapping[str, Any], evidence: list[dict[str, Any]], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    event_evidence_by_story: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in evidence:
        candidate = record.get("normalized_candidate")
        if isinstance(candidate, Mapping) and isinstance(candidate.get("event_id"), str) and record.get("relation_to_story") in {"direct_story_time", "event_context"}:
            event_evidence_by_story[str(record["story_id"])].append(record)
    people_by_story: dict[str, list[str]] = defaultdict(list)
    for mention in bundle.get("mentions", []):
        if not isinstance(mention, Mapping) or mention.get("section") != "main_text":
            continue
        person_id = mention.get("person_id")
        story_id = mention.get("story_id")
        if isinstance(person_id, str) and isinstance(story_id, str):
            people_by_story[story_id].append(person_id)
    output: list[dict[str, Any]] = []
    for story_id in sorted(event_evidence_by_story):
        for event_record in sorted(event_evidence_by_story[story_id], key=lambda item: str(item["evidence_record_id"])):
            event_id = str(event_record["normalized_candidate"]["event_id"])
            for person_id in sorted(set(people_by_story.get(story_id, []))):
                output.append(
                    {
                        "anchor_id": stable_id("h0a-activity", person_id, event_id, story_id),
                        "story_id": story_id,
                        "person_id": person_id,
                        "activity_type": "story_event_context",
                        "event_id": event_id,
                        "phase_id": "phase-5" if event_id in {"event-wang-dun-rebellion", "event-su-jun-rebellion"} else None,
                        "start_year_ce": next((item.get("start_year_ce") for item in events if item.get("event_id") == event_id), None),
                        "end_year_ce": next((item.get("end_year_ce") for item in events if item.get("event_id") == event_id), None),
                        "evidence_ids": [str(event_record["evidence_record_id"])],
                        "precision": "event_bounded",
                        "assertion_status": "inferred",
                        "review_status": "candidate",
                        "notes": "仅作为约束故事时间的最小事件上下文，不是完整任职史或人物传记。",
                    }
                )
    return output


def build_gap_audit(bundle: Mapping[str, Any], anchors: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    evidence_by_story: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in evidence:
        evidence_by_story[str(record["story_id"])].append(record)
    rows: list[dict[str, Any]] = []
    for anchor in anchors:
        story_id = str(anchor["story_id"])
        records = evidence_by_story.get(story_id, [])
        precision = str(anchor["precision"])
        if precision == "unknown":
            if anchor.get("conflict_flags"):
                gap_class = "conflicting_sources"
            elif any(item.get("relation_to_story") == "later_outcome" for item in records):
                gap_class = "event_known_date_uncertain"
            elif any(item.get("relation_to_story") == "earlier_background" for item in records):
                gap_class = "ambiguous_reference"
            else:
                gap_class = "genuine_unknown"
        elif precision == "phase_only":
            gap_class = "phase_only"
        elif precision == "event_bounded":
            gap_class = "event_known_date_uncertain"
        else:
            gap_class = "resolved_at_supported_precision"
        rows.append(
            {
                "story_id": story_id,
                "precision": precision,
                "gap_class": gap_class,
                "evidence_record_ids": [str(item["evidence_record_id"]) for item in records],
                "notes": anchor["rationale"],
            }
        )
    return {
        "schema": SCHEMA,
        "stage": "h0a-temporal-gap-audit",
        "policy": "Unknown and phase-only are valid outcomes; no new source acquisition is triggered by this audit.",
        "records": rows,
        "unknown_story_ids": [row["story_id"] for row in rows if row["precision"] == "unknown"],
    }


def build_metrics(bundle: Mapping[str, Any], evidence: list[dict[str, Any]], events: list[dict[str, Any]], anchors: list[dict[str, Any]], gap: Mapping[str, Any]) -> dict[str, Any]:
    precision = Counter(str(item["precision"]) for item in anchors)
    review = Counter(str(item["review_status"]) for item in anchors)
    source_layers = Counter(str(item.get("source_layer")) for item in evidence)
    chronology_refs = [
        ref
        for event in events
        for ref in event.get("chronology_source_refs", [])
        if isinstance(ref, Mapping)
    ]
    kaoyi_refs = [
        ref
        for event in events
        for ref in event.get("kaoyi_source_refs", [])
        if isinstance(ref, Mapping)
    ]
    source_counts = {
        "shishuo_main": source_layers.get("main_text", 0),
        "liu_annotation": source_layers.get("liu_annotation", 0),
        "jinshu": 0,
        "sanguozhi_main": 0,
        "pei_annotation": 0,
        "tongjian_main": sum(1 for ref in chronology_refs if ref.get("source_layer") == "tongjian_main"),
        "hu_annotation": sum(1 for ref in chronology_refs if ref.get("source_layer") == "hu_annotation"),
        "kaoyi": len(kaoyi_refs),
    }
    ztj_manifest = read_json(ZTJ_MANIFEST_PATH) if ZTJ_MANIFEST_PATH.exists() else {}
    sgz_manifest = read_json(SGZ_MANIFEST_PATH) if SGZ_MANIFEST_PATH.exists() else {}
    primary = ztj_manifest.get("primary", {}) if isinstance(ztj_manifest, Mapping) else {}
    kaoyi = ztj_manifest.get("kaoyi", {}) if isinstance(ztj_manifest, Mapping) else {}
    event_story_ids = sorted({story_id for event in events for story_id in event.get("linked_story_ids", [])})
    conflicts = sorted({flag for anchor in anchors for flag in anchor.get("conflict_flags", [])})
    return {
        "schema": SCHEMA,
        "stage": "h0a-metrics",
        "production_story_count": len(bundle.get("stories", [])),
        "precision_distribution": {key: precision.get(key, 0) for key in ["exact_date", "exact_year", "year_range", "event_bounded", "reign_bounded", "phase_only", "unknown"]},
        "review_distribution": {key: review.get(key, 0) for key in ["reviewed", "candidate", "unresolved"]},
        "historical_event_count": len(events),
        "stories_linked_to_events": len(event_story_ids),
        "event_story_ids": event_story_ids,
        "evidence_counts_by_source_layer": source_counts,
        "source_usage_counts": {
            "story_temporal_evidence_records": {
                "shishuo_main": source_layers.get("main_text", 0),
                "liu_annotation": source_layers.get("liu_annotation", 0),
                "jinshu": 0,
                "sanguozhi_main": 0,
                "pei_annotation": 0,
            },
            "supporting_coordinate_references": {
                "tongjian_main": source_counts["tongjian_main"],
                "hu_annotation": source_counts["hu_annotation"],
                "kaoyi": source_counts["kaoyi"],
            },
            "processed_corpus_inventory": {
                "tongjian_main_text_units": primary.get("main_text_unit_count", 0),
                "tongjian_hu_annotation_units": primary.get("hu_annotation_unit_count", 0),
                "kaoyi_blocks": kaoyi.get("block_count", 0),
                "sanguozhi_main_text_units": sgz_manifest.get("main_text_unit_count", 0),
                "sanguozhi_pei_annotation_units": sgz_manifest.get("pei_annotation_unit_count", 0),
            },
        },
        "evidence_record_count": len(evidence),
        "genuine_unknown_count": sum(1 for item in anchors if item["precision"] == "unknown" and not item.get("conflict_flags")),
        "source_conflict_count": sum(1 for item in anchors if item.get("conflict_flags")),
        "conflict_flags": conflicts,
        "frontend_visible_temporal_orientation_count": sum(1 for item in anchors if item.get("reader_projection", {}).get("show")),
        "frontend_intentionally_unlabeled_count": sum(1 for item in anchors if not item.get("reader_projection", {}).get("show")),
        "gap_class_counts": dict(Counter(str(item["gap_class"]) for item in gap.get("records", []))),
        "unknown_story_ids": list(gap.get("unknown_story_ids", [])),
    }


def write_docs(bundle: Mapping[str, Any], coordinates: Mapping[str, Any], events: list[dict[str, Any]], anchors: list[dict[str, Any]], gap: Mapping[str, Any], metrics: Mapping[str, Any]) -> None:
    event_names = ", ".join(str(item["canonical_name"]) for item in events) or "目前没有足够证据建立事件记录"
    unknown_ids = "、".join(str(item) for item in gap.get("unknown_story_ids", [])) or "无"
    DOC_PATH.write_text(
        f"""# H0A 历史时间骨架

H0A 将当前生产 Story 放入有证据支撑的时间分辨率中。它是时间证据与阅读定位层，不是完整年表，也不把《资治通鉴》设为自动最高权威。

## 坐标层

- 产品阶段沿用 W3/C0 的五个稳定 ID；本次保留 {len(coordinates.get('phases', []))} 个阶段定义。
- 从 ZTJ0 实际纪年标题构建 {len(coordinates.get('reign_periods', []))} 个 ReignPeriod、{len(coordinates.get('era_years', []))} 个 EraYear。
- 年号年可在证据确定时归一化为公元年；不做日级传统历法换算。

## 证据与事件

当前 {len(bundle.get('stories', []))} 则 Story 均有一个 StoryTemporalAnchor；生成 {len(events)} 个当前范围确实需要的 HistoricalEvent：{event_names}。事件记录保留 Story/Liu 的表面和来源层，不把事件共现转为人物 Relation。

## 重点回归

- `05-fangzheng-031`：王敦举兵相关证据是事件范围证据；伯仁的政治批评仍是本则舞台语境，不生成周顗—王敦 Relation。
- `06-yaliang-017`：刘注的“咸和六年遇害”记录为 `later_outcome`，不把庾会后来的命运误定为童年场景年份。
- `05-fangzheng-055`：桓子野／桓伊的身份修复不被时间抽取改写。
- `01-dexing-026`：“少孤”仍是普通叙事词，不恢复孟陋的错误 Mention。
- W3 的曹魏、竹林—西晋初、西晋后期样本沿用冻结阶段定位，没有虚构精确年份。

## 前端

Story 头部只显示有意义的自然中文时间定位；unknown 不显示“未详”、unknown 或内部 precision。若已有 W3 阶段，H0A 的 temporal orientation 取代旧的独立时间系统，避免重复标签。

## 边界

H0A 不创建 Clan、OfficeTenure、HistoricalCircle、Timeline UI 或完整 HistoricalEvent 图。后续 H0B/P4/ES0 必须先审阅本层的 unknown 与冲突。

## 当前分布

精度分布：`{json.dumps(metrics.get('precision_distribution', {}), ensure_ascii=False)}`。前端有定位标签的 Story：{metrics.get('frontend_visible_temporal_orientation_count', 0)}。
""",
        encoding="utf-8",
    )
    POLICY_DOC_PATH.write_text(
        """# H0A 时间解析政策

## 来源职责

《世说新语》正文与刘注负责本则的直接表面；《晋书》与《三国志》负责人物、制度和事件背景；《资治通鉴》负责编年与事件序列；胡三省注负责通鉴注释；《资治通鉴考异》负责保留编年争议。任何来源都不自动覆盖其他来源。

## 分辨率

优先级是故事本地明确年号年、可独立确认的事件范围、兼容的上下界、年号/在位范围、阶段、unknown。只有正文直接出现且能接到坐标层的年号年才允许 `exact_year`。

`later_outcome`、`earlier_background` 和古代引述不会自动约束故事时间。多个互相冲突的约束会降级并保留 `conflict_flags`，不会静默选择一个日期。

## 前端规则

只投影自然中文标签，例如“东晋 · 苏峻之乱”或“竹林—西晋初”。unknown、phase ID、event-bounded、candidate 和 review_status 永不显示。

## 非目标

H0A 不建立完整年表、不做日级历法、不创建 Clan/OfficeTenure/Timeline，也不把事件参与或共现变成 Relation。
""",
        encoding="utf-8",
    )
    rows_text = "\n".join(
        f"| `{row['story_id']}` | `{row['precision']}` | `{row['gap_class']}` | {row['notes']} |"
        for row in gap.get("records", [])
    )
    GAP_DOC_PATH.write_text(
        f"""# H0A 时间缺口审计

本审计覆盖当前全部生产 Story。unknown 与 phase_only 都是合法结果，不是必须消灭的缺陷。

- Story 总数：{len(anchors)}
- genuine_unknown：{metrics.get('genuine_unknown_count', 0)}
- source conflict：{metrics.get('source_conflict_count', 0)}
- event-linked：{metrics.get('stories_linked_to_events', 0)}

## 仍为 unknown 的 Story

{unknown_ids}

## 分类

| Story | precision | gap class | 说明 |
|---|---|---|---|
{rows_text}

下一步是审阅这些缺口，而不是在 H0A 中下载新来源或强行补年。
""",
        encoding="utf-8",
    )


def build() -> dict[str, Any]:
    bundle = read_json(BUNDLE_PATH)
    w3 = read_json(W3_PATH)
    ztj_index = read_json(ZTJ_INDEX_PATH)
    coordinates = build_coordinates(ztj_index)
    evidence, anchors, _ = build_evidence_and_anchors(bundle, coordinates, w3)
    events = build_events(evidence, ztj_index)
    activities = build_activity_anchors(bundle, evidence, events)
    # Activity anchors are deliberately not required for every event anchor;
    # only direct production-Person event context can support one.
    for anchor in anchors:
        story_id = str(anchor["story_id"])
        linked = [
            item["anchor_id"]
            for item in activities
            if item.get("story_id") == story_id
            and any(item.get("event_id") == event_id for event_id in anchor.get("event_ids", []))
        ]
        anchor["supporting_activity_anchor_ids"] = sorted(set(linked))
    gap = build_gap_audit(bundle, anchors, evidence)
    metrics = build_metrics(bundle, evidence, events, anchors, gap)

    coordinates_hash = write_json(COORDINATES_PATH, coordinates)
    evidence_hash = write_json(
        EVIDENCE_PATH,
        {
            "schema": SCHEMA,
            "stage": "h0a-story-temporal-evidence",
            "scope": {"published_story_ids": [str(item["id"]) for item in bundle.get("stories", [])]},
            "records": sorted(evidence, key=lambda item: (str(item["story_id"]), str(item["source_layer"]), str(item["source_span"].get("annotation_id") or ""), int(item["source_span"].get("char_start", 0)), str(item["evidence_record_id"]))),
            "policy": "Keyword surfaces remain candidate evidence; relation_to_story controls whether they constrain a Story anchor.",
        },
    )
    events_hash = write_json(
        EVENTS_PATH,
        {
            "schema": SCHEMA,
            "stage": "h0a-historical-events",
            "scope": {"event_count": len(events), "story_scope": [str(item["id"]) for item in bundle.get("stories", [])]},
            "records": events,
            "policy": "Only events required by current source evidence are represented; Event != Relation.",
        },
    )
    activity_hash = write_json(
        ACTIVITY_PATH,
        {
            "schema": SCHEMA,
            "stage": "h0a-person-activity-anchors",
            "policy": "Minimal event-context anchors only; not a generalized OfficeTenure or biography layer.",
            "records": activities,
        },
    )
    anchors_hash = write_json(
        ANCHORS_PATH,
        {
            "schema": SCHEMA,
            "stage": "h0a-story-temporal-anchors",
            "scope": {"published_story_ids": [str(item["id"]) for item in bundle.get("stories", [])]},
            "records": anchors,
            "policy": "Exactly one conservative anchor per current production Story; unknown is valid.",
        },
    )
    gap_hash = write_json(GAP_PATH, gap)
    metrics["artifact_hashes"] = {
        "temporal_coordinates": coordinates_hash,
        "temporal_evidence": evidence_hash,
        "historical_events": events_hash,
        "person_activity_anchors": activity_hash,
        "story_temporal_anchors": anchors_hash,
        "gap_audit": gap_hash,
    }
    write_json(METRICS_PATH, metrics)
    write_docs(bundle, coordinates, events, anchors, gap, metrics)
    return {
        "coordinates": coordinates,
        "evidence": evidence,
        "events": events,
        "activities": activities,
        "anchors": anchors,
        "gap": gap,
        "metrics": metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    result = build()
    if not args.quiet:
        metrics = result["metrics"]
        print(
            "built H0A: "
            f"stories={len(result['anchors'])}; "
            f"evidence={len(result['evidence'])}; "
            f"events={len(result['events'])}; "
            f"precision={json.dumps(metrics['precision_distribution'], ensure_ascii=False, sort_keys=True)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
