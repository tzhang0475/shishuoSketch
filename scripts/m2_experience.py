#!/usr/bin/env python3
"""Deterministic M2A experience-selection analysis.

P3A.1 answers whether a stable identity can be proposed.  M2A answers a
different product question: which of those identities will make the current
Story/Person experience more traversable?  This module intentionally keeps
the two analyses separate and never writes production Persons, Mentions,
Relations, or Story publication state.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

try:
    from .build_six_person_pilot import parse_shishuo_sections
except ImportError:  # direct execution
    from build_six_person_pilot import parse_shishuo_sections


ROOT = Path(__file__).resolve().parents[1]
P3A1_PATH = Path("data/derived/person-identity-candidates.json")
OCCURRENCES_PATH = Path("data/derived/person-candidate-occurrences.json")
PEOPLE_PATH = Path("data/people.json")
MENTIONS_PATH = Path("data/mentions/shishuo.json")
CORPUS_INDEX_PATH = Path("data/shishuo-corpus-index.json")
GOLD_PATH = Path("data/story-chain-gold-set.json")
SCENE_PATH = Path("data/annotation/story-scene-contexts.json")
PUNCTUATION_PATH = Path("data/annotation/wp1-punctuation.json")
RANKING_PATH = Path("data/derived/m2-person-expansion-ranking.json")
REPORT_PATH = Path("docs/m2-person-expansion-ranking.md")
WAVE2_PATH = Path("data/annotation/person-expansion-wave-2.json")
ALLOCATION_PATH = Path("data/derived/person-id-allocation-state.json")
WAVE2_ID = "p3b-wave-2"
WAVE2_SIZE = 18

SCHEMA_VERSION = 1
RANKING_STAGE = "m2a-person-experience-ranking"

# The weights are deliberately public and sum to 1.10 before the citation
# penalty.  The extra headroom makes the anti-citation signal material without
# allowing it to erase an otherwise useful narrative candidate silently.
WEIGHTS = {
    "main_text_narrative_coverage": 0.24,
    "story_unlock_value": 0.14,
    "current_network_bridge_value": 0.13,
    "dead_end_closure_value": 0.18,
    "person_sketch_value": 0.08,
    "relation_opportunity": 0.05,
    "scene_value": 0.06,
    "identity_evidence_quality": 0.16,
    "naming_richness": 0.06,
    "annotation_citation_author_penalty": 0.20,
}

_CITATION_PATTERNS = (
    re.compile(r"晉書曰"),
    re.compile(r"晉紀曰"),
    re.compile(r"晉陽秋曰"),
    re.compile(r"別傳曰"),
    re.compile(r"譜曰"),
    re.compile(r"傳曰"),
    re.compile(r"史曰"),
    re.compile(r"某書曰"),
    re.compile(r"《[^》]{1,24}》"),
)


def read_json(root: Path, path: Path) -> Any:
    return json.loads((root / path).read_text(encoding="utf-8"))


def write_json(root: Path, path: Path, value: Any) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _log_norm(value: int | float, maximum: int | float) -> float:
    if value <= 0 or maximum <= 0:
        return 0.0
    return round(math.log1p(float(value)) / math.log1p(float(maximum)), 8)


def _sorted_unique(values: Iterable[str]) -> list[str]:
    return sorted({str(value) for value in values if isinstance(value, str) and value})


def _entry_sections(root: Path, entry: Mapping[str, Any]) -> dict[str, str]:
    text = (root / str(entry["path"])).read_text(encoding="utf-8")
    return {section: body for section, body, _metadata in parse_shishuo_sections(text)}


def _occurrence_context(
    root: Path,
    entries: Mapping[str, Mapping[str, Any]],
    occurrence: Mapping[str, Any],
) -> str:
    entry = entries.get(str(occurrence.get("source_id")))
    if entry is None:
        return ""
    section = str(occurrence.get("section"))
    surface = str(occurrence.get("surface"))
    offset = occurrence.get("offset")
    if not isinstance(offset, int):
        return ""
    text = _entry_sections(root, entry).get(section, "")
    return text[max(0, offset - 48) : min(len(text), offset + len(surface) + 96)]


def _is_citation_occurrence(context: str) -> bool:
    if not context:
        return False
    return any(pattern.search(context) for pattern in _CITATION_PATTERNS)


def _candidate_evidence_quality(candidate: Mapping[str, Any]) -> float:
    metrics = candidate.get("metrics", {})
    score = 0.0
    if int(metrics.get("jinshu_unit_count", 0)) > 0:
        score += 0.42
    if int(metrics.get("explicit_identity_link_count", 0)) > 0:
        score += 0.32
    if int(metrics.get("full_name_attestation_count", 0)) > 0:
        score += 0.18
    if candidate.get("identity_basis"):
        score += 0.08
    if "single_source_unit" in set(candidate.get("risk_flags", [])):
        score -= 0.08
    if "conflicting_identity_evidence" in set(candidate.get("risk_flags", [])):
        score -= 0.35
    return round(max(0.0, min(1.0, score)), 8)


def _surface_richness(candidate: Mapping[str, Any]) -> float:
    useful_types = {
        "personal_name",
        "courtesy_name",
        "surname_plus_courtesy_name",
        "orthographic_variant",
    }
    types = {
        str(item.get("surface_type"))
        for item in candidate.get("surfaces", [])
        if isinstance(item, Mapping)
        and item.get("association_mode") in {"exact", "contextual"}
        and str(item.get("surface_type")) in useful_types
    }
    return round(min(1.0, len(types) / 3.0), 8)


def _story_people(mentions: Iterable[Mapping[str, Any]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for mention in mentions:
        if mention.get("section") != "main_text":
            continue
        story_id = str(mention.get("entry_id") or mention.get("source_id"))
        person_id = mention.get("person_id")
        if story_id and isinstance(person_id, str):
            result[story_id].add(person_id)
    return result


def _story_annotation_counts(mentions: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    result: dict[str, int] = defaultdict(int)
    for mention in mentions:
        if mention.get("section") == "liu_annotation":
            result[str(mention.get("entry_id") or mention.get("source_id"))] += 1
    return result


def _current_story_ids(root: Path) -> list[str]:
    return [str(item["entry_id"]) for item in read_json(root, GOLD_PATH).get("records", [])]


def _candidate_occurrences(
    root: Path,
    *,
    entries: Mapping[str, Mapping[str, Any]],
    current_story_ids: set[str],
    production_person_ids: set[str],
    current_main_people: Mapping[str, set[str]],
    annotation_counts: Mapping[str, int],
) -> tuple[dict[str, dict[str, Any]], int]:
    p3a1 = read_json(root, P3A1_PATH)
    candidates = {
        str(item["candidate_id"]): item
        for item in p3a1.get("candidates", [])
        if isinstance(item, Mapping)
        and item.get("status") == "strong_candidate"
        and item.get("materialization_state") == "new_candidate"
    }
    occurrences = [
        item for item in read_json(root, OCCURRENCES_PATH).get("occurrences", [])
        if isinstance(item, Mapping) and str(item.get("candidate_id")) in candidates
    ]
    by_candidate: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for occurrence in occurrences:
        by_candidate[str(occurrence["candidate_id"])].append(occurrence)

    scene_story_ids = {
        str(item.get("story_id"))
        for item in read_json(root, SCENE_PATH).get("records", [])
        if isinstance(item, Mapping) and isinstance(item.get("story_id"), str)
    }
    max_main = max(
        (
            len({str(item.get("source_id")) for item in rows if item.get("section") == "main_text"})
            for rows in by_candidate.values()
        ),
        default=0,
    )
    max_unlock = 0
    max_network = 0
    max_dead_end = max(
        (
            len({str(item.get("source_id")) for item in rows if str(item.get("source_id")) in current_story_ids})
            for rows in by_candidate.values()
        ),
        default=0,
    )

    working: dict[str, dict[str, Any]] = {}
    for candidate_id, candidate in candidates.items():
        rows = sorted(
            by_candidate.get(candidate_id, []),
            key=lambda item: (
                str(item.get("source_id")),
                0 if item.get("section") == "main_text" else 1,
                int(item.get("offset", 10**9)) if isinstance(item.get("offset"), int) else 10**9,
                str(item.get("occurrence_id")),
            ),
        )
        main_story_ids = _sorted_unique(
            str(item.get("source_id"))
            for item in rows
            if item.get("section") == "main_text"
            and item.get("association_mode") in {"exact", "contextual"}
        )
        exact_main_story_ids = _sorted_unique(
            str(item.get("source_id"))
            for item in rows
            if item.get("section") == "main_text" and item.get("association_mode") == "exact"
        )
        liu_story_ids = _sorted_unique(
            str(item.get("source_id"))
            for item in rows
            if item.get("section") == "liu_annotation"
        )
        current_story_ids_for_candidate = _sorted_unique(
            str(item.get("source_id")) for item in rows if str(item.get("source_id")) in current_story_ids
        )
        dead_end_story_ids = _sorted_unique(
            str(item.get("source_id"))
            for item in rows
            if str(item.get("source_id")) in current_story_ids
            and str(item.get("source_id")) in scene_story_ids | current_story_ids
        )
        unlock_story_ids = _sorted_unique(
            story_id
            for story_id in exact_main_story_ids
            if story_id not in current_story_ids and current_main_people.get(story_id, set())
        )
        shared_current_person_ids = _sorted_unique(
            person_id
            for story_id in exact_main_story_ids
            for person_id in current_main_people.get(story_id, set())
            if person_id in production_person_ids
        )
        scene_value_story_ids = _sorted_unique(
            story_id
            for story_id in set(main_story_ids) | set(liu_story_ids)
            if annotation_counts.get(story_id, 0) > 0
            and (len(current_main_people.get(story_id, set())) >= 1 or story_id in scene_story_ids)
        )
        citation_rows = [
            item
            for item in rows
            if item.get("section") == "liu_annotation"
            and _is_citation_occurrence(_occurrence_context(root, entries, item))
        ]
        citation_ratio = len(citation_rows) / max(1, len(liu_story_ids) and sum(item.get("section") == "liu_annotation" for item in rows))
        annotation_count = sum(item.get("section") == "liu_annotation" for item in rows)
        # A non-citation annotation occurrence is still useful context, but a
        # candidate with no narrative main-text occurrence and only citation
        # attribution should not be selected for Story traversal.
        if not main_story_ids and annotation_count:
            citation_ratio = max(citation_ratio, 0.85)
        max_unlock = max(max_unlock, len(unlock_story_ids))
        max_network = max(max_network, len(shared_current_person_ids))
        working[candidate_id] = {
            "candidate": candidate,
            "rows": rows,
            "main_story_ids": main_story_ids,
            "exact_main_story_ids": exact_main_story_ids,
            "liu_story_ids": liu_story_ids,
            "current_story_ids": current_story_ids_for_candidate,
            "dead_end_story_ids": dead_end_story_ids,
            "unlock_story_ids": unlock_story_ids,
            "shared_current_person_ids": shared_current_person_ids,
            "scene_value_story_ids": scene_value_story_ids,
            "main_story_count": len(main_story_ids),
            "liu_story_count": len(liu_story_ids),
            "mention_count": len(rows),
            "citation_occurrence_count": len(citation_rows),
            "annotation_occurrence_count": annotation_count,
            "annotation_citation_author_ratio": round(min(1.0, citation_ratio), 8),
            "identity_evidence_quality": _candidate_evidence_quality(candidate),
            "naming_richness": _surface_richness(candidate),
            "scene_story_count": len(scene_value_story_ids),
        }
    return working, max_main


def build_person_ranking(root: Path = ROOT) -> dict[str, Any]:
    people = read_json(root, PEOPLE_PATH).get("people", [])
    production_ids = {str(item.get("person_id")) for item in people if isinstance(item, Mapping)}
    current_story_ids = set(_current_story_ids(root))
    entries = {
        str(item["id"]): item
        for item in read_json(root, CORPUS_INDEX_PATH).get("entries", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    mentions = read_json(root, MENTIONS_PATH).get("mentions", [])
    current_main_people = _story_people(mentions)
    annotation_counts = _story_annotation_counts(mentions)
    working, _max_main_from_occurrences = _candidate_occurrences(
        root,
        entries=entries,
        current_story_ids=current_story_ids,
        production_person_ids=production_ids,
        current_main_people=current_main_people,
        annotation_counts=annotation_counts,
    )
    max_main = max((row["main_story_count"] for row in working.values()), default=0)
    max_unlock = max((len(row["unlock_story_ids"]) for row in working.values()), default=0)
    max_network = max((len(row["shared_current_person_ids"]) for row in working.values()), default=0)
    max_dead = max((len(row["dead_end_story_ids"]) for row in working.values()), default=0)
    max_scene = max((row["scene_story_count"] for row in working.values()), default=0)

    rows: list[dict[str, Any]] = []
    for candidate_id, row in working.items():
        candidate = row["candidate"]
        components = {
            "main_text_narrative_coverage": _log_norm(row["main_story_count"], max_main),
            "story_unlock_value": _log_norm(len(row["unlock_story_ids"]), max_unlock),
            "current_network_bridge_value": _log_norm(len(row["shared_current_person_ids"]), max_network),
            "dead_end_closure_value": _log_norm(len(row["dead_end_story_ids"]), max_dead),
            "person_sketch_value": _log_norm(row["main_story_count"], max_main),
            # R3A does not yet expose candidate endpoints, so this remains a
            # transparent zero rather than treating co-occurrence as a Relation.
            "relation_opportunity": 0.0,
            "scene_value": _log_norm(row["scene_story_count"], max_scene),
            "identity_evidence_quality": row["identity_evidence_quality"],
            "naming_richness": row["naming_richness"],
            "annotation_citation_author_penalty": row["annotation_citation_author_ratio"],
        }
        positive = sum(
            WEIGHTS[name] * components[name]
            for name in WEIGHTS
            if name != "annotation_citation_author_penalty"
        )
        score = round(max(0.0, min(100.0, 100.0 * (positive - WEIGHTS["annotation_citation_author_penalty"] * components["annotation_citation_author_penalty"]))), 4)
        risk_flags = sorted({str(flag) for flag in candidate.get("risk_flags", [])})
        if components["annotation_citation_author_penalty"] >= 0.75:
            risk_flags.append("annotation_citation_dominated")
        if not row["main_story_ids"]:
            risk_flags.append("no_main_text_narrative")
        risk_flags = sorted(set(risk_flags))
        eligible = (
            candidate.get("status") == "strong_candidate"
            and candidate.get("materialization_state") == "new_candidate"
            and bool(candidate.get("identity_evidence_ids"))
            and not set(risk_flags) & {"conflicting_identity_evidence", "multiple_possible_people", "no_full_name", "unresolved_identity"}
            and bool(row["main_story_ids"])
            and components["annotation_citation_author_penalty"] < 0.9
        )
        reasons: list[str] = []
        if row["main_story_count"]:
            reasons.append(f"{row['main_story_count']}則正文故事可形成连续阅读路径")
        if row["unlock_story_ids"]:
            reasons.append(f"可连接{len(row['unlock_story_ids'])}则已有生产人物参与的未发布故事")
        if row["dead_end_story_ids"]:
            reasons.append(f"当前SC1中有{len(row['dead_end_story_ids'])}则故事出现未物化人物")
        if row["scene_story_count"]:
            reasons.append(f"{row['scene_story_count']}则故事具备注释/场景上下文潜力")
        if components["annotation_citation_author_penalty"] >= 0.75:
            reasons.append("刘注出现主要呈史料引文署名，降低体验优先级")
        rows.append(
            {
                "candidate_id": candidate_id,
                "preferred_name": str(candidate.get("preferred_name")),
                "status": candidate.get("status"),
                "score": score,
                "eligible": eligible,
                "components": components,
                "metrics": {
                    "main_text_story_count": row["main_story_count"],
                    "exact_main_text_story_count": len(row["exact_main_story_ids"]),
                    "liu_annotation_story_count": row["liu_story_count"],
                    "mention_count": row["mention_count"],
                    "citation_occurrence_count": row["citation_occurrence_count"],
                    "annotation_occurrence_count": row["annotation_occurrence_count"],
                    "annotation_citation_author_ratio": row["annotation_citation_author_ratio"],
                    "story_unlock_count": len(row["unlock_story_ids"]),
                    "current_network_person_count": len(row["shared_current_person_ids"]),
                    "dead_end_closure_story_count": len(row["dead_end_story_ids"]),
                    "scene_value_story_count": row["scene_story_count"],
                    "identity_evidence_quality": row["identity_evidence_quality"],
                    "naming_richness": row["naming_richness"],
                },
                "main_text_story_ids": row["main_story_ids"],
                "liu_annotation_story_ids": row["liu_story_ids"],
                "unlock_story_ids": row["unlock_story_ids"],
                "dead_end_story_ids": row["dead_end_story_ids"],
                "scene_value_story_ids": row["scene_value_story_ids"],
                "connected_current_person_ids": row["shared_current_person_ids"],
                "identity_evidence_ids": _sorted_unique(str(item) for item in candidate.get("identity_evidence_ids", [])),
                "risk_flags": risk_flags,
                "selection_reasons": reasons,
            }
        )

    rows.sort(
        key=lambda item: (
            -float(item["score"]),
            -int(item["metrics"]["dead_end_closure_story_count"]),
            -int(item["metrics"]["main_text_story_count"]),
            -int(item["metrics"]["story_unlock_count"]),
            str(item["preferred_name"]),
            str(item["candidate_id"]),
        )
    )
    for rank, item in enumerate(rows, start=1):
        item["rank"] = rank

    current_live_gaps = []
    by_story: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in rows:
        for story_id in item["dead_end_story_ids"]:
            by_story[story_id].append(item)
    for story_id in sorted(by_story):
        current_live_gaps.append(
            {
                "story_id": story_id,
                "candidate_ids": [item["candidate_id"] for item in sorted(by_story[story_id], key=lambda x: x["rank"])],
                "preferred_names": [item["preferred_name"] for item in sorted(by_story[story_id], key=lambda x: x["rank"])],
            }
        )

    document = {
        "schema": SCHEMA_VERSION,
        "stage": RANKING_STAGE,
        "generated_from": [str(P3A1_PATH), str(OCCURRENCES_PATH), str(PEOPLE_PATH), str(MENTIONS_PATH), str(GOLD_PATH), str(SCENE_PATH)],
        "weights": WEIGHTS,
        "normalization": "Each count component uses log1p(value)/log1p(maximum) over the current strong-candidate universe; identity and naming are bounded rule scores. Citation-author ratio is a direct penalty.",
        "candidate_universe_count": len(rows),
        "eligible_candidate_count": sum(bool(item["eligible"]) for item in rows),
        "production_person_count": len(production_ids),
        "current_sc1_story_count": len(current_story_ids),
        "current_live_story_gap_count": len(current_live_gaps),
        "current_live_story_gaps": current_live_gaps,
        "candidates": rows,
        "notes": [
            "M2 ranking is decision support and does not materialize Persons or modify P3A.1.",
            "Main-text narrative coverage is separated from Liu annotation coverage.",
            "Citation-author detection is deterministic and conservative; Liu-only identities remain in P3A.1 but are normally ineligible for M2 traversal selection.",
            "Shared Story and Scene data are navigation signals only and never create Relation facts.",
        ],
    }
    return document


def render_person_report(document: Mapping[str, Any], top_n: int = 60) -> str:
    candidates = list(document["candidates"])
    lines = [
        "# M2A 人物体验扩展排序",
        "",
        "本排序是 P3A.1 身份候选之上的体验决策层：优先选择能让读者从正文故事继续走向人物、再走向更多故事的人物。它不改变 P3A.1 身份语义，也不直接物化人物。",
        "",
        "## 摘要",
        "",
        f"- 当前生产人物：**{document['production_person_count']}**",
        f"- 候选身份：**{document['candidate_universe_count']}**；符合 M2 严格门槛：**{document['eligible_candidate_count']}**",
        f"- 当前 SC1 故事：**{document['current_sc1_story_count']}**；可由开放世界候选解释的当前缺口：**{document['current_live_story_gap_count']}**",
        "- 计分重点：正文叙事覆盖、故事解锁、当前网络桥接、当前死路闭合、Scene 潜力、身份证据质量。",
        "- 反向信号：刘注史料引文署名占比；这不会删除身份，只降低 M2 阅读优先级。",
        "",
        "## 权重",
        "",
        "| 维度 | 权重 |",
        "|---|---:|",
    ]
    for name, weight in document["weights"].items():
        lines.append(f"| `{name}` | {weight:.2f} |")
    lines.extend(["", "## 排名", "", "| Rank | 人物 | 分数 | 正文故事 | 解锁故事 | 当前死路 | 刘注署名比 | 身份证据 | 资格 |", "|---:|---|---:|---:|---:|---:|---:|---:|---|"])
    for item in candidates[:top_n]:
        metrics = item["metrics"]
        lines.append(
            f"| {item['rank']} | {item['preferred_name']} (`{item['candidate_id']}`) | {item['score']:.4f} | "
            f"{metrics['main_text_story_count']} | {metrics['story_unlock_count']} | {metrics['dead_end_closure_story_count']} | "
            f"{metrics['annotation_citation_author_ratio']:.2f} | {metrics['identity_evidence_quality']:.2f} | "
            f"{'可进入 Wave 2' if item['eligible'] else '暂缓'} |"
        )
    lines.extend(["", "## 当前 live Story 缺口", ""])
    if document["current_live_story_gaps"]:
        for gap in document["current_live_story_gaps"]:
            lines.append(f"- `{gap['story_id']}`：{', '.join(gap['preferred_names'])}")
    else:
        lines.append("- 当前开放世界候选没有安全身份投影到 SC1 缺口。")
    lines.extend(["", "## 选择纪律", "", "- M2 Wave 2 选择应从 `eligible=true` 的稳定身份中冻结；不得以名气、现代评价或单纯共现补足名额。", "- 只有正文/安全身份路径能形成故事漫游价值的候选才进入默认资格；纯刘注史料署名保留在 P3A.1，不进入本轮体验物化。", "- `relation_opportunity` 目前显式为 0，避免把共现误作 Relation；未来 R3B 仍需独立审阅。", ""])
    return "\n".join(lines)


def _initial_allocation_state(root: Path) -> dict[str, Any]:
    people = read_json(root, PEOPLE_PATH).get("people", [])
    allocations = []
    for person in people:
        person_id = str(person.get("person_id"))
        materialization = person.get("materialization", {})
        wave_id = materialization.get("wave_id") if isinstance(materialization, Mapping) else None
        if person_id <= "person-006":
            basis = "bootstrap_order"
        elif person_id == "person-007":
            basis = "supporting_person_preserved_from_pid1"
        elif wave_id == "p3b-wave-1":
            basis = "p3b_wave_1_rank_order"
        else:
            basis = "existing_production_registry"
        allocations.append(
            {
                "person_id": person_id,
                "canonical_name": str(person.get("canonical_name")),
                "allocation_basis": basis,
                "source_wave_id": wave_id,
            }
        )
    allocations.sort(key=lambda item: item["person_id"])
    return {
        "schema": 1,
        "stage": "production-person-id-allocation-state",
        "next_person_sequence": len(allocations) + 1,
        "allocations": allocations,
        "notes": [
            "Opaque Person IDs are assigned once and never generated from names or display text.",
            "This state artifact is updated only by an explicit materialization wave.",
        ],
    }


def freeze_wave2(root: Path = ROOT, *, size: int = WAVE2_SIZE) -> dict[str, Any]:
    """Freeze the M2 ranking selection before any production mutation."""

    ranking_path = root / RANKING_PATH
    if not ranking_path.is_file():
        raise ValueError(f"missing M2 ranking artifact: {ranking_path}")
    ranking = read_json(root, RANKING_PATH)
    ranking_hash = sha256_file(ranking_path)
    people = read_json(root, PEOPLE_PATH).get("people", [])
    current_ids = {str(item.get("person_id")) for item in people if isinstance(item, Mapping)}
    eligible = [item for item in ranking.get("candidates", []) if item.get("eligible") is True]
    selected = eligible[:size]
    if len(selected) < size:
        raise ValueError(f"M2 Wave 2 requires {size} eligible candidates, found {len(selected)}")
    members = []
    for rank, item in enumerate(selected, start=1):
        person_id = f"person-{17 + rank:03d}"
        if person_id in current_ids:
            raise ValueError(f"M2 Wave 2 target Person ID already exists: {person_id}")
        members.append(
            {
                "candidate_id": str(item["candidate_id"]),
                "rank_at_selection": int(item["rank"]),
                "preferred_name": str(item["preferred_name"]),
                "person_id": person_id,
                "candidate_status": "strong_candidate",
                "materialization_status": "pending",
                "review_status": "candidate",
                "m2_score": float(item["score"]),
                "m2_components": dict(item["components"]),
                "selection_reasons": list(item.get("selection_reasons", [])),
                "identity_evidence_ids": list(item.get("identity_evidence_ids", [])),
                "risk_flags": list(item.get("risk_flags", [])),
            }
        )
    document = {
        "schema": 1,
        "stage": "m2a-person-expansion-wave",
        "wave_id": WAVE2_ID,
        "source_ranking_artifact": str(RANKING_PATH),
        "source_ranking_sha256": ranking_hash,
        "ranking_version": RANKING_STAGE,
        "selection_policy": f"Freeze the first {size} eligible candidates from the deterministic M2 experience ranking; never substitute a later rank during materialization.",
        "members": members,
        "notes": [
            "Wave membership is selected before production mutation.",
            "Production Person IDs are explicit opaque allocations beginning at person-018.",
            "Candidate review status remains candidate after materialization.",
        ],
    }
    wave_path = root / WAVE2_PATH
    if wave_path.is_file():
        existing = read_json(root, WAVE2_PATH)
        if existing != document:
            raise ValueError("existing M2 Wave 2 manifest differs from the deterministic pre-mutation selection")
    else:
        write_json(root, WAVE2_PATH, document)
    allocation_path = root / ALLOCATION_PATH
    allocation = _initial_allocation_state(root)
    if allocation_path.is_file():
        existing_allocation = read_json(root, ALLOCATION_PATH)
        if existing_allocation != allocation:
            raise ValueError("existing Person ID allocation state differs from the P-ID1 registry")
    else:
        write_json(root, ALLOCATION_PATH, allocation)
    return document


def build(root: Path = ROOT) -> tuple[Path, Path]:
    document = build_person_ranking(root)
    write_json(root, RANKING_PATH, document)
    report = render_person_report(document)
    target = root / REPORT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report, encoding="utf-8")
    return root / RANKING_PATH, target


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-wave-2", action="store_true")
    args = parser.parse_args()
    for path in build():
        print(path)
    if args.freeze_wave_2:
        wave = freeze_wave2()
        print(ROOT / WAVE2_PATH)
        print(f"froze {wave['wave_id']} with {len(wave['members'])} members")
