#!/usr/bin/env python3
"""Small, deterministic helpers for the SRM0.1 research-memory pilot.

SRM0.1 is deliberately an isolated generated experiment.  The module reads
registered/reviewed projections and local source indexes, but never writes or
modifies canonical, Gold, frontend, or PersonStory data.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from .ds1_common import ROOT, read_json, sha256_file, stable_json, write_json
except ImportError:  # pragma: no cover - direct script execution
    from ds1_common import ROOT, read_json, sha256_file, stable_json, write_json


STORY_ID = "27-jiajue-008"
MODEL = "deepseek-v4-flash"
PROVIDER = "deepseek"
PROMPT_VERSION = "srm0.1-v1"
SCHEMA_VERSION = 1

SC1_PATH = Path("data/derived/sc1-site.json")
SHISHUO_SEARCH_PATH = Path("data/derived/ds2-1a-shishuo-search-corpus.json")
JIANSU_ASSERTIONS_PATH = Path("data/derived/s1-jianshu-historical-assertions.json")
JINSHU_INDEX_PATH = Path("data/jinshu-unit-index.json")
E0_ORIENTATION_PATH = Path("data/derived/e0-story-era-orientations.json")
H0C_PARTICIPANT_PATH = Path("data/derived/h0c-participant-freeze.json")
PERSON_SURFACE_PATH = Path("data/derived/ds2-1a-person-research-surface.json")

OUTPUT_ROOT = Path("data/generated/srm0") / STORY_ID
REVIEW_PATH = Path("data/annotation/srm0-1-review.json")

MAX_PUZZLES = 3
MIN_PROBES = 3
MAX_PROBES = 5
MAX_CANDIDATES = 8
MAX_MODEL_EVIDENCE_CHARS = 2000
MAX_MODEL_SNIPPET_CHARS = 280
MAX_KEEP_REFS = 3
MAX_CLAIM_UPDATES = 3
MAX_NEW_QUESTIONS = 2
MAX_READING_LINKS = 2

PUZZLE_CATEGORIES = {
    "identity",
    "temporal",
    "participant_state",
    "relationship_state",
    "causal_precondition",
    "stakes",
    "reading_link",
}
IMPORTANCE = {"high", "medium", "low"}
EVIDENCE_DECISIONS = {"keep", "discard", "later_only", "contradictory", "insufficient"}
CLAIM_OPERATIONS = {"add", "revise", "reject"}
CLAIM_UPDATE_TYPES = {"new_evidence", "refinement", "contradiction", "irrelevant_association"}
QUESTION_STATUSES = {"resolved", "superseded", "deprioritized", "unresolved"}
EVENT_TYPES = {
    "question_created",
    "evidence_retrieved",
    "evidence_kept",
    "evidence_discarded",
    "claim_added",
    "claim_revised",
    "claim_rejected",
    "question_superseded",
    "question_deprioritized",
    "question_created_from_evidence",
    "reading_link_added",
}

TRADITIONAL_FOLD = str.maketrans(
    {
        "蘇": "苏",
        "溫": "温",
        "嶠": "峤",
        "尋": "寻",
        "陽": "阳",
        "亂": "乱",
        "難": "难",
        "責": "责",
        "會": "会",
        "見": "见",
        "從": "从",
        "爲": "为",
        "為": "为",
        "與": "与",
        "後": "后",
        "國": "国",
        "將": "将",
        "軍": "军",
        "門": "门",
        "書": "书",
        "應": "应",
        "說": "说",
        "時": "时",
        "開": "开",
        "發": "发",
        "於": "于",
        "無": "无",
        "並": "并",
        "縁": "缘",
        "遜": "逊",
        "謝": "谢",
    }
)


def fold(value: str) -> str:
    """Fold for matching while retaining one character per source character."""

    return unicodedata.normalize("NFKC", value).translate(TRADITIONAL_FOLD).lower()


def compact(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def input_hash(value: Any) -> str:
    return sha256_text(stable_json(value))


def _source_path_is_forbidden(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.startswith("data/generated/") or normalized.startswith("data/annotation/")


def _story_from_sc1(doc: Mapping[str, Any], story_id: str) -> Mapping[str, Any]:
    for row in doc.get("stories", []):
        if isinstance(row, Mapping) and row.get("id") == story_id:
            return row
    raise ValueError(f"story not found in SC1: {story_id}")


def _person_name(row: Mapping[str, Any], person_id: str) -> str:
    value = row.get("canonical_name") or row.get("name") or row.get("display_name")
    if isinstance(value, Mapping):
        return str(value.get("original") or value.get("simplified") or person_id)
    return str(value or person_id)


def _sc1_person(sc1: Mapping[str, Any], person_id: str) -> Mapping[str, Any]:
    people = sc1.get("people", [])
    if isinstance(people, Mapping):
        value = people.get(person_id, {})
        return value if isinstance(value, Mapping) else {}
    for row in people if isinstance(people, list) else []:
        if isinstance(row, Mapping) and row.get("id") == person_id:
            return row
    return {}


def _main_text(story: Mapping[str, Any]) -> str:
    reading = story.get("reading")
    if isinstance(reading, Mapping):
        main = reading.get("main_text")
        if isinstance(main, Mapping):
            return str(main.get("original") or story.get("text") or "")
    return str(story.get("text") or "")


def _orientation_row(root: Path, story_id: str) -> dict[str, Any] | None:
    if not (root / E0_ORIENTATION_PATH).is_file():
        return None
    doc = read_json(root, E0_ORIENTATION_PATH)
    rows = doc.get("records", []) if isinstance(doc, Mapping) else []
    for row in rows:
        if isinstance(row, Mapping) and row.get("story_id") == story_id:
            label = row.get("label") if isinstance(row.get("label"), Mapping) else {}
            return {
                "era": label.get("original") or label.get("simplified"),
                "broad_temporal_anchor": row.get("h0a_precision") or row.get("orientation_precision"),
                "precision_status": row.get("orientation_precision"),
            }
    return None


def build_initial_packet(root: Path = ROOT, story_id: str = STORY_ID) -> tuple[dict[str, Any], dict[str, int]]:
    """Build the deliberately narrow Completion-1 model packet."""

    sc1 = read_json(root, SC1_PATH)
    story = _story_from_sc1(sc1, story_id)
    story_text = str(story.get("reading", {}).get("main_text", {}).get("original") or story.get("text") or "")
    mentions = [
        row for row in sc1.get("mentions", [])
        if isinstance(row, Mapping) and row.get("story_id") == story_id and row.get("person_id")
    ]
    h0c = read_json(root, H0C_PARTICIPANT_PATH)
    roles = {
        str(row.get("person_id")): str(row.get("role"))
        for row in h0c.get("records", [])
        if isinstance(row, Mapping) and row.get("story_id") == story_id and row.get("person_id")
    }
    surface = read_json(root, PERSON_SURFACE_PATH)
    surface_people = surface.get("people", {}) if isinstance(surface, Mapping) else {}

    person_ids = sorted({str(row.get("person_id")) for row in mentions if row.get("person_id")})
    cards: list[dict[str, Any]] = []
    for person_id in person_ids:
        person = _sc1_person(sc1, person_id)
        aliases: list[str] = []
        person_surface = surface_people.get(person_id, {}) if isinstance(surface_people, Mapping) else {}
        context = person_surface.get("reviewed_context", {}) if isinstance(person_surface, Mapping) else {}
        for alias in context.get("aliases", []) if isinstance(context, Mapping) else []:
            if isinstance(alias, Mapping) and alias.get("surface") and alias.get("status") in {"resolved", "reviewed"}:
                aliases.append(str(alias["surface"]))
        aliases = sorted(set(aliases))
        person_mentions = [row for row in mentions if str(row.get("person_id")) == person_id]
        role = roles.get(person_id)
        if not role:
            role = "main_text_mention" if any(row.get("section") == "main_text" for row in person_mentions) else "liu_annotation_mention"
        cards.append(
            {
                "person_id": person_id,
                "canonical_name": _person_name(person, person_id),
                "aliases": aliases,
                "current_story_role": role,
            }
        )

    annotations = []
    for annotation in story.get("annotations", []):
        if isinstance(annotation, Mapping):
            annotations.append(
                {
                    "annotation_id": str(annotation.get("id")),
                    "source_layer": "liu_annotation",
                    "text": str(annotation.get("text") or ""),
                }
            )

    conflicts: list[dict[str, Any]] = []
    for mention in mentions:
        if mention.get("surface") == "士衡" and mention.get("person_id") == "person-026" and "陶士衡" in story_text:
            conflicts.append(
                {
                    "conflict_type": "identity_resolution",
                    "surface": "士衡",
                    "textual_context": "陶士衡",
                    "existing_resolution": {"person_id": "person-026", "canonical_name": "陸機"},
                    "notice": "现有独立表面解析与正文复合称谓并存；本实验不改写身份，只保留冲突供研究记忆处理。",
                    "action": "human_review_required",
                }
            )
            break

    packet = {
        "schema": "srm0-1-initial-model-packet",
        "schema_version": SCHEMA_VERSION,
        "story_id": story_id,
        "chapter": story.get("chapter_heading") or story.get("title"),
        "story_text": story_text,
        "liu_annotations": sorted(annotations, key=lambda row: row["annotation_id"]),
        "era_orientation": _orientation_row(root, story_id),
        "person_orientation_cards": cards,
        "known_conflict_notices": conflicts,
        "canonical_write_back": False,
    }
    return packet, {"raw_input_chars": len(stable_json(packet)), "model_input_chars": len(stable_json(packet))}


@dataclass(frozen=True)
class SourceUnit:
    evidence_ref: str
    work: str
    source_layer: str
    text: str
    source_path: str
    source_sha256: str
    locator: dict[str, Any]
    story_id: str | None = None
    assertion_status: str | None = None
    review_status: str | None = None
    attribution: str | None = None
    quoted_source: str | None = None

    def model_row(self, snippet: str) -> dict[str, Any]:
        return {"ref": self.evidence_ref, "work": self.work, "source_layer": self.source_layer, "snippet": snippet}


def _jinshu_text(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    marker = "## Original source (exact)\n"
    if marker not in content:
        raise ValueError(f"Jinshu unit lacks exact-source marker: {path}")
    text = content.split(marker, 1)[1]
    return text.rstrip("\n")


def build_source_registry(root: Path = ROOT) -> tuple[dict[str, SourceUnit], dict[str, str]]:
    """Build the local, source-only registry used by SRM retrieval."""

    registry: dict[str, SourceUnit] = {}
    source_hashes: dict[str, str] = {}

    corpus = read_json(root, SHISHUO_SEARCH_PATH)
    source_hashes[SHISHUO_SEARCH_PATH.as_posix()] = sha256_file(root, SHISHUO_SEARCH_PATH)
    for row in corpus.get("records", []):
        if not isinstance(row, Mapping) or not row.get("story_id"):
            continue
        story_id = str(row["story_id"])
        source_path = str(row.get("source_path") or "")
        if _source_path_is_forbidden(source_path):
            raise ValueError(f"forbidden source path in Shishuo corpus: {source_path}")
        main_ref = f"shishuo:{story_id}:main"
        registry[main_ref] = SourceUnit(
            main_ref,
            "世说新语",
            "base_text",
            str(row.get("main_text") or ""),
            source_path or SHISHUO_SEARCH_PATH.as_posix(),
            str(row.get("source_sha256") or source_hashes[SHISHUO_SEARCH_PATH.as_posix()]),
            {"story_id": story_id, "chapter_id": row.get("chapter_id"), "entry_number": row.get("entry_number"), "source_path": source_path},
            story_id=story_id,
            assertion_status="attested",
            review_status="reviewed",
        )
        for annotation in row.get("liu_annotations", []):
            if not isinstance(annotation, Mapping) or not annotation.get("annotation_id"):
                continue
            annotation_id = str(annotation["annotation_id"])
            ref = f"shishuo:{story_id}:{annotation_id}"
            registry[ref] = SourceUnit(
                ref,
                "世说新语",
                "liu_annotation",
                str(annotation.get("text") or ""),
                str(annotation.get("source_locator", {}).get("source_path") or source_path or SHISHUO_SEARCH_PATH.as_posix()),
                str(row.get("source_sha256") or source_hashes[SHISHUO_SEARCH_PATH.as_posix()]),
                dict(annotation.get("source_locator") or {}),
                story_id=story_id,
                assertion_status="attested",
                review_status="reviewed",
            )

    jianshu = read_json(root, JIANSU_ASSERTIONS_PATH)
    source_hashes[JIANSU_ASSERTIONS_PATH.as_posix()] = sha256_file(root, JIANSU_ASSERTIONS_PATH)
    for row in jianshu.get("records", []):
        if not isinstance(row, Mapping) or not row.get("assertion_id") or not str(row.get("text") or "").strip():
            continue
        ref = str(row["assertion_id"])
        locator = dict(row.get("source_locator") or {})
        registry[ref] = SourceUnit(
            ref,
            "世说新语笺疏",
            str(row.get("layer") or "jianshu_note"),
            str(row.get("text") or ""),
            JIANSU_ASSERTIONS_PATH.as_posix(),
            source_hashes[JIANSU_ASSERTIONS_PATH.as_posix()],
            locator,
            story_id=str(row.get("story_id")) if row.get("story_id") else None,
            assertion_status=str(row.get("modality")) if row.get("modality") else None,
            review_status=str(row.get("canonicalization_status")) if row.get("canonicalization_status") else None,
            attribution=str(row.get("attribution")) if row.get("attribution") else None,
            quoted_source=str(row.get("quoted_source")) if row.get("quoted_source") else None,
        )

    jinshu = read_json(root, JINSHU_INDEX_PATH)
    source_hashes[JINSHU_INDEX_PATH.as_posix()] = sha256_file(root, JINSHU_INDEX_PATH)
    for row in jinshu.get("units", []):
        if not isinstance(row, Mapping) or row.get("category") != "liezhuan" or not row.get("unit_id"):
            continue
        path = str(row.get("file_path") or "")
        if not path or _source_path_is_forbidden(path) or not (root / path).is_file():
            continue
        text = _jinshu_text(root / path)
        ref = f"jinshu:{row['unit_id']}"
        registry[ref] = SourceUnit(
            ref,
            "晉書",
            "jinshu_unit",
            text,
            path,
            str(row.get("unit_text_sha256") or sha256_text(text)),
            {"unit_id": row.get("unit_id"), "volume": row.get("volume_number"), "title": row.get("title"), "source_path": path},
            assertion_status="attested",
            review_status="reviewed",
        )
    return registry, dict(sorted(source_hashes.items()))


def _probe_terms(probe: str) -> list[str]:
    value = fold(probe).strip()
    if not value:
        return []
    terms = {value}
    cjk = "".join(char for char in value if "\u3400" <= char <= "\u9fff")
    for size in (3, 2):
        if len(cjk) >= size:
            terms.update(cjk[index : index + size] for index in range(len(cjk) - size + 1))
    return sorted(terms, key=lambda item: (-len(item), item))


def _occurrences(text: str, term: str) -> list[int]:
    result: list[int] = []
    start = 0
    while term:
        index = text.find(term, start)
        if index < 0:
            break
        result.append(index)
        start = index + 1
    return result


def _clusters(offsets: Sequence[int], gap: int = 72) -> list[list[int]]:
    if not offsets:
        return []
    result: list[list[int]] = [[offsets[0]]]
    for offset in offsets[1:]:
        if offset - result[-1][-1] <= gap:
            result[-1].append(offset)
        else:
            result.append([offset])
    return result


def retrieve_windows(
    registry: Mapping[str, SourceUnit],
    probes: Sequence[str],
    *,
    entity_hints: Sequence[str] = (),
    exclude_story_id: str | None = STORY_ID,
    max_candidates: int = MAX_CANDIDATES,
) -> dict[str, Any]:
    """Retrieve source-character windows without using sentence boundaries."""

    probe_rows: list[dict[str, Any]] = []
    all_terms: list[tuple[str, str]] = []
    for probe in probes:
        terms = _probe_terms(str(probe))
        probe_rows.append({"probe": str(probe), "terms": terms, "match_count": 0, "cluster_count": 0})
        all_terms.extend((str(probe), term) for term in terms)
    hint_terms = sorted({term for hint in entity_hints for term in _probe_terms(str(hint)) if len(term) >= 2})
    raw_match_count = 0
    raw_cluster_count = 0
    candidates: list[dict[str, Any]] = []

    for ref in sorted(registry):
        unit = registry[ref]
        if exclude_story_id and unit.story_id == exclude_story_id:
            continue
        source_folded = fold(unit.text)
        hits: list[tuple[int, str, str]] = []
        for probe, term in all_terms:
            positions = _occurrences(source_folded, fold(term))
            if positions:
                raw_match_count += len(positions)
                row = next(item for item in probe_rows if item["probe"] == probe)
                row["match_count"] += len(positions)
                hits.extend((position, term, probe) for position in positions)
        if not hits:
            continue
        hits.sort(key=lambda item: (item[0], -len(item[1]), item[1], item[2]))
        clusters = _clusters([item[0] for item in hits])
        raw_cluster_count += len(clusters)
        for row in probe_rows:
            row["cluster_count"] += sum(1 for cluster in clusters if any(hit[2] == row["probe"] for hit in hits if hit[0] in cluster))
        for offsets in clusters:
            selected = [hit for hit in hits if hit[0] in offsets]
            matched_terms = sorted({item[1] for item in selected}, key=lambda item: (-len(item), item))
            matched_probes = sorted({item[2] for item in selected})
            start_offset = min(offsets)
            end_offset = max(offset + len(term) for offset, term, _ in selected)
            exact_count = sum(1 for _, term, _ in selected if len(term) >= 3)
            entity_count = sum(1 for hint in hint_terms if hint in source_folded[max(0, start_offset - 90) : min(len(source_folded), end_offset + 90)])
            distance = max(0, end_offset - start_offset)
            proximity = max(0, 40 - distance // 4)
            score = len(matched_terms) * 10 + exact_count * 12 + entity_count * 14 + proximity
            if any(len(term) >= 4 for _, term, _ in selected):
                score += 12
            padding = min(150, 80 + len(matched_terms) * 12)
            window_start = max(0, start_offset - padding)
            window_end = min(len(unit.text), end_offset + padding)
            candidates.append(
                {
                    "ref": ref,
                    "base_ref": ref,
                    "work": unit.work,
                    "source_layer": unit.source_layer,
                    "source_path": unit.source_path,
                    "source_sha256": unit.source_sha256,
                    "locator": unit.locator,
                    "story_id": unit.story_id,
                    "offset_start": window_start,
                    "offset_end": window_end,
                    "window_text": unit.text[window_start:window_end],
                    "matched_terms": matched_terms,
                    "matched_probes": matched_probes,
                    "exact_match_count": exact_count,
                    "entity_match_count": entity_count,
                    "score": score,
                }
            )

    # Merge overlapping windows for one source unit.  This is structural
    # deduplication, not semantic inference.
    candidates.sort(key=lambda row: (-int(row["score"]), row["work"], row["ref"], row["offset_start"]))
    merged: list[dict[str, Any]] = []
    for candidate in candidates:
        existing = next(
            (row for row in merged if row["base_ref"] == candidate["base_ref"] and not (candidate["offset_end"] < row["offset_start"] - 12 or candidate["offset_start"] > row["offset_end"] + 12)),
            None,
        )
        if existing is None:
            merged.append(dict(candidate))
        else:
            existing["offset_start"] = min(existing["offset_start"], candidate["offset_start"])
            existing["offset_end"] = max(existing["offset_end"], candidate["offset_end"])
            unit = registry[candidate["base_ref"]]
            existing["window_text"] = unit.text[existing["offset_start"] : existing["offset_end"]]
            existing["matched_terms"] = sorted(set(existing["matched_terms"]) | set(candidate["matched_terms"]), key=lambda item: (-len(item), item))
            existing["matched_probes"] = sorted(set(existing["matched_probes"]) | set(candidate["matched_probes"]))
            existing["score"] = max(int(existing["score"]), int(candidate["score"]))
    deduplicated = sorted(merged, key=lambda row: (-int(row["score"]), row["work"], row["ref"], row["offset_start"]))

    selected: list[dict[str, Any]] = []
    seen_works: set[str] = set()
    for candidate in deduplicated:
        if candidate["work"] not in seen_works:
            selected.append(candidate)
            seen_works.add(candidate["work"])
        if len(selected) >= max_candidates:
            break
    if len(selected) < max_candidates:
        for candidate in deduplicated:
            if candidate in selected:
                continue
            selected.append(candidate)
            if len(selected) >= max_candidates:
                break

    model_candidates: list[dict[str, Any]] = []
    model_chars = 0
    for candidate in selected:
        snippet = candidate["window_text"][:MAX_MODEL_SNIPPET_CHARS]
        row = {"ref": candidate["ref"], "work": candidate["work"], "source_layer": candidate["source_layer"], "snippet": snippet}
        if model_chars + len(snippet) > MAX_MODEL_EVIDENCE_CHARS:
            remaining = MAX_MODEL_EVIDENCE_CHARS - model_chars
            if remaining <= 0:
                break
            row["snippet"] = snippet[:remaining]
        model_candidates.append(row)
        model_chars += len(row["snippet"])
        if model_chars >= MAX_MODEL_EVIDENCE_CHARS:
            break

    trace_candidates = []
    for row in selected:
        trace_row = dict(row)
        trace_row["model_snippet"] = next((item["snippet"] for item in model_candidates if item["ref"] == row["ref"]), None)
        trace_candidates.append(trace_row)
    return {
        "segmentation_method": "source_unit_character_window_no_sentence_segmentation",
        "excluded_story_id": exclude_story_id,
        "probes": probe_rows,
        "raw_match_count": raw_match_count,
        "raw_cluster_count": raw_cluster_count,
        "deduplicated_candidate_count": len(deduplicated),
        "selected_candidate_count": len(trace_candidates),
        "raw_retrieval_chars": sum(len(row["window_text"]) for row in trace_candidates),
        "model_evidence_chars": model_chars,
        "candidates": trace_candidates,
        "model_candidates": model_candidates,
    }


QUESTION_SYSTEM_PROMPT = """你是《世说新语》单篇研究的第一阶段问题生成器。只能使用用户提供的原文、刘注和导航卡，不得调用检索，不得用预训练常识补足史实，也不要回答问题。请找出最多三个由准确原文跨度触发的 textual puzzle，说明未解释之处和回答后可能重读的原文跨度。span 和 reading_target 必须逐字取自用户给出的 Story 原文；不要改成简体，不要加入原文没有的标点。分类只能使用 identity、temporal、participant_state、relationship_state、causal_precondition、stakes、reading_link。必须选择且只选择一个 active_question，并给出三至五个紧凑的字符检索 probe。严格返回如下 JSON 字段：{\"textual_puzzles\":[{\"span\":\"原文跨度\",\"category\":\"...\",\"unexplained\":\"...\",\"reading_target\":\"...\",\"importance\":\"high|medium|low\"}],\"active_question\":{\"question\":\"...\",\"derived_from\":[\"P1\"],\"why_needed\":\"...\",\"reading_target\":\"原文跨度\",\"importance\":\"high|medium|low\"},\"search_probes\":[\"...\"]}。返回 JSON，不要输出 JSON 以外的文字。"""

MEMORY_SYSTEM_PROMPT = """你是受控的《世说新语》研究记忆更新器。请从头重读原文，只使用本轮提供的 active question 和本地检索候选，不得使用预训练常识。区分 new evidence、refinement、contradiction、irrelevant association；证据不足就保留不确定。请为每个候选 ref 做一项 evidence_decision；没有帮助时使用 insufficient 或 discard，不要强行保留。每项实质性 claim 和 reading link 必须引用本轮候选中的 ref。最多保留三条 evidence ref、三条 claim update、两条 new question、两条 reading-link update。必须返回恰好一条 next_active_question=true 的 new_questions；即使证据不足，也要提出一个用于下一轮核查的窄问题，而不是把列表留空。该问题必须有 derived_from、why_needed、reading_target、importance。不要执行这个新问题，不要写隐藏推理或长篇散文。严格返回 JSON，顶层字段只能是 evidence_decisions、claim_updates、question_updates、new_questions、reading_link_updates、stop_recommendation。new_questions 示例是一个含 question_id、question、derived_from、why_needed、reading_target、importance、next_active_question=true 的对象数组。"""


def question_messages(packet: Mapping[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": QUESTION_SYSTEM_PROMPT},
        {"role": "user", "content": stable_json(packet)},
    ]


def memory_messages(
    story_id: str,
    story_text: str,
    active_question: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    packet = {
        "story_id": story_id,
        "story_text": story_text,
        "active_question": dict(active_question),
        "current_research_state": {"claims": [], "reading_links": [], "seen_evidence_refs": []},
        "candidate_evidence": [dict(row) for row in candidates],
    }
    return [
        {"role": "system", "content": MEMORY_SYSTEM_PROMPT},
        {"role": "user", "content": stable_json(packet)},
    ]


def parse_json_content(content: Any) -> tuple[dict[str, Any], str]:
    text = str(content or "").strip()
    repair = "none"
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        repair = "markdown_fence_removed"
    value = json.loads(text)
    if not isinstance(value, Mapping):
        raise ValueError("model JSON must be an object")
    return dict(value), repair


def normalize_question_output(raw: Mapping[str, Any], story_text: str) -> dict[str, Any]:
    def exact_story_surface(value: Any) -> str:
        proposed = compact(value)
        if not proposed:
            return ""
        if proposed in story_text:
            return proposed
        folded_proposed = fold(proposed)
        folded_story = fold(story_text)
        start = folded_story.find(folded_proposed)
        if start >= 0:
            return story_text[start : start + len(proposed)]
        trimmed = proposed.strip("，。；：！？、,.!?;:")
        if trimmed:
            start = folded_story.find(fold(trimmed))
            if start >= 0:
                return story_text[start : start + len(trimmed)]
        return ""

    puzzles: list[dict[str, Any]] = []
    raw_puzzles = raw.get("textual_puzzles", raw.get("puzzles", []))
    if isinstance(raw_puzzles, Mapping):
        raw_puzzles = raw_puzzles.get("items", raw_puzzles.get("puzzles", []))
    for index, row in enumerate(raw_puzzles if isinstance(raw_puzzles, list) else [], start=1):
        if not isinstance(row, Mapping) or len(puzzles) >= MAX_PUZZLES:
            continue
        span = exact_story_surface(row.get("span") or row.get("text_span"))
        if not span:
            continue
        category = row.get("category") if row.get("category") in PUZZLE_CATEGORIES else "reading_link"
        importance = row.get("importance") if row.get("importance") in IMPORTANCE else "medium"
        puzzles.append(
            {
                "puzzle_id": f"P{len(puzzles) + 1}",
                "span": span,
                "category": category,
                "unexplained": compact(row.get("unexplained")),
                "reading_target": exact_story_surface(row.get("reading_target")) or span,
                "importance": importance,
            }
        )
    if not puzzles:
        raise ValueError("Completion 1 produced no exact textual puzzle")
    raw_active_value = raw.get("active_question", raw.get("active_research_question", {}))
    raw_active = raw_active_value if isinstance(raw_active_value, Mapping) else {}
    derived = [str(value) for value in raw_active.get("derived_from", []) if isinstance(value, str)]
    derived = [value for value in derived if value in {row["puzzle_id"] for row in puzzles}]
    if not derived:
        derived = [puzzles[0]["puzzle_id"]]
    active = {
        "question_id": "Q1",
        "question": compact(raw_active.get("question")),
        "derived_from": derived,
        "why_needed": compact(raw_active.get("why_needed")),
        "reading_target": exact_story_surface(raw_active.get("reading_target")) or puzzles[0]["reading_target"],
        "importance": raw_active.get("importance") if raw_active.get("importance") in IMPORTANCE else "high",
        "status": "active",
    }
    if not active["question"]:
        raise ValueError("Completion 1 produced an empty active question")
    probes: list[str] = []
    raw_probes = raw.get("search_probes", raw.get("lexical_probes", []))
    for value in raw_probes if isinstance(raw_probes, list) else []:
        value = compact(value)
        if value and value not in probes:
            probes.append(value)
    if len(probes) < MIN_PROBES:
        raise ValueError("Completion 1 must produce at least three search probes")
    return {"textual_puzzles": puzzles, "active_question": active, "search_probes": probes[:MAX_PROBES]}


def normalize_memory_patch(raw: Mapping[str, Any], candidate_refs: Iterable[str], story_text: str) -> dict[str, Any]:
    allowed_refs = set(candidate_refs)
    decisions: list[dict[str, Any]] = []
    for row in raw.get("evidence_decisions", []):
        if not isinstance(row, Mapping) or str(row.get("evidence_ref")) not in allowed_refs:
            continue
        decision = row.get("decision") if row.get("decision") in EVIDENCE_DECISIONS else "insufficient"
        decisions.append({"evidence_ref": str(row["evidence_ref"]), "decision": decision, "reason": compact(row.get("reason"))})
    decisions.sort(key=lambda row: row["evidence_ref"])
    kept = {row["evidence_ref"] for row in decisions if row["decision"] == "keep"}
    if len(kept) > MAX_KEEP_REFS:
        keep_rows = [row for row in decisions if row["decision"] == "keep"][:MAX_KEEP_REFS]
        kept = {row["evidence_ref"] for row in keep_rows}
        for row in decisions:
            if row["decision"] == "keep" and row["evidence_ref"] not in kept:
                row["decision"] = "later_only"

    claims: list[dict[str, Any]] = []
    for row in raw.get("claim_updates", []):
        if not isinstance(row, Mapping) or len(claims) >= MAX_CLAIM_UPDATES:
            continue
        refs = sorted({str(ref) for ref in row.get("evidence_refs", []) if str(ref) in allowed_refs}) if isinstance(row.get("evidence_refs"), list) else []
        if not refs:
            continue
        operation = row.get("operation") if row.get("operation") in CLAIM_OPERATIONS else "add"
        update_type = row.get("update_type") if row.get("update_type") in CLAIM_UPDATE_TYPES else "refinement"
        claims.append(
            {
                "claim_id": str(row.get("claim_id") or f"C{len(claims) + 1}"),
                "operation": operation,
                "update_type": update_type,
                "text": compact(row.get("text")),
                "evidence_refs": refs,
                "epistemic_status": row.get("epistemic_status") if row.get("epistemic_status") in {"attested", "supported_inference", "uncertain", "conflicted"} else "uncertain",
            }
        )

    question_updates: list[dict[str, Any]] = []
    for row in raw.get("question_updates", []):
        if not isinstance(row, Mapping):
            continue
        status = row.get("status") if row.get("status") in QUESTION_STATUSES else "unresolved"
        question_updates.append({"question_id": str(row.get("question_id") or "Q1"), "status": status, "reason": compact(row.get("reason"))})

    new_questions: list[dict[str, Any]] = []
    raw_new_questions = raw.get("new_questions", [])
    if not raw_new_questions:
        alternate = raw.get("next_active_question", raw.get("next_question"))
        if isinstance(alternate, Mapping):
            raw_new_questions = [alternate]
    for row in raw_new_questions if isinstance(raw_new_questions, list) else []:
        if not isinstance(row, Mapping) or len(new_questions) >= MAX_NEW_QUESTIONS:
            continue
        target = str(row.get("reading_target") or "")
        if target and target not in story_text:
            target = ""
        derived_from = [str(value) for value in row.get("derived_from", []) if isinstance(value, str)] if isinstance(row.get("derived_from"), list) else []
        if not derived_from or not row.get("question") or not target:
            continue
        new_questions.append(
            {
                "question_id": str(row.get("question_id") or f"Q{len(new_questions) + 2}"),
                "question": compact(row.get("question")),
                "derived_from": derived_from,
                "why_needed": compact(row.get("why_needed")),
                "reading_target": target,
                "importance": row.get("importance") if row.get("importance") in IMPORTANCE else "medium",
                "next_active_question": bool(row.get("next_active_question")),
            }
        )
    active_seen = False
    for row in new_questions:
        if row["next_active_question"] and not active_seen:
            active_seen = True
        else:
            row["next_active_question"] = False
    if not active_seen:
        raise ValueError("Completion 2 must produce exactly one refined next_active_question")

    links: list[dict[str, Any]] = []
    for row in raw.get("reading_link_updates", []):
        if not isinstance(row, Mapping) or len(links) >= MAX_READING_LINKS:
            continue
        span = str(row.get("text_span") or row.get("span") or "")
        refs = sorted({str(ref) for ref in row.get("evidence_refs", []) if str(ref) in allowed_refs}) if isinstance(row.get("evidence_refs"), list) else []
        if not span or span not in story_text or not refs:
            continue
        links.append({"text_span": span, "reading_effect": compact(row.get("reading_effect")), "evidence_refs": refs})

    stop = raw.get("stop_recommendation") if isinstance(raw.get("stop_recommendation"), Mapping) else {}
    return {
        "evidence_decisions": decisions,
        "claim_updates": claims,
        "question_updates": question_updates,
        "new_questions": new_questions,
        "reading_link_updates": links,
        "stop_recommendation": {"stop": bool(stop.get("stop")), "reason": compact(stop.get("reason"))},
    }


def usage_record(response: Mapping[str, Any] | None) -> dict[str, Any]:
    usage = response.get("usage", {}) if isinstance(response, Mapping) else {}
    usage = usage if isinstance(usage, Mapping) else {}
    return {
        "prompt_tokens": usage.get("prompt_tokens"),
        "prompt_cache_hit_tokens": usage.get("prompt_cache_hit_tokens"),
        "prompt_cache_miss_tokens": usage.get("prompt_cache_miss_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "raw_usage": dict(usage),
    }


def compression_metrics(raw_input_chars: int, model_input_chars: int, raw_retrieval_chars: int = 0, model_evidence_chars: int = 0) -> dict[str, Any]:
    return {
        "raw_input_chars": int(raw_input_chars),
        "model_input_chars": int(model_input_chars),
        "compression_ratio": round(model_input_chars / raw_input_chars, 6) if raw_input_chars else 0,
        "raw_retrieval_chars": int(raw_retrieval_chars),
        "model_evidence_chars": int(model_evidence_chars),
    }


def build_memory_state(
    story_id: str,
    question: Mapping[str, Any],
    retrieval: Mapping[str, Any],
    patch: Mapping[str, Any],
    *,
    execution_kind: str,
    run_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Materialize auditable state/events, never hidden chain-of-thought."""

    refs = sorted({str(row.get("ref")) for row in retrieval.get("model_candidates", []) if isinstance(row, Mapping) and row.get("ref")})
    claims = [dict(row) for row in patch.get("claim_updates", [])]
    active_questions = [row for row in patch.get("new_questions", []) if row.get("next_active_question")]
    state = {
        "schema": "srm0-1-research-memory",
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "generated_research_memory",
        "candidate_status": "candidate",
        "story_id": story_id,
        "iteration": 1,
        "run_id": run_id,
        "execution_kind": execution_kind,
        "claims": claims,
        "active_questions": active_questions,
        "resolved_questions": [row for row in patch.get("question_updates", []) if row.get("status") == "resolved"],
        "superseded_questions": [row for row in patch.get("question_updates", []) if row.get("status") == "superseded"],
        "deprioritized_questions": [row for row in patch.get("question_updates", []) if row.get("status") == "deprioritized"],
        "unresolved_no_evidence_questions": [row for row in patch.get("question_updates", []) if row.get("status") == "unresolved"],
        "reading_links": [dict(row) for row in patch.get("reading_link_updates", [])],
        "seen_evidence_refs": refs,
        "research_status": "next_question_pending_not_executed" if active_questions else "stopped_after_completion_2",
        "canonical_write_back": False,
    }

    raw_events: list[dict[str, Any]] = [
        {"event_type": "question_created", "question_id": question.get("question_id", "Q1"), "reason": "Completion 1 active question"},
        {"event_type": "evidence_retrieved", "evidence_refs": refs, "candidate_count": len(refs)},
    ]
    for row in patch.get("evidence_decisions", []):
        raw_events.append({"event_type": "evidence_kept" if row.get("decision") == "keep" else "evidence_discarded", "evidence_ref": row.get("evidence_ref"), "decision": row.get("decision"), "reason": row.get("reason", "")})
    for row in claims:
        raw_events.append({"event_type": {"add": "claim_added", "revise": "claim_revised", "reject": "claim_rejected"}.get(row.get("operation"), "claim_added"), "claim_id": row.get("claim_id"), "evidence_refs": row.get("evidence_refs", []), "reason": row.get("text", "")})
    for row in patch.get("question_updates", []):
        if row.get("status") in {"superseded", "deprioritized"}:
            raw_events.append({"event_type": "question_superseded" if row["status"] == "superseded" else "question_deprioritized", "question_id": row.get("question_id"), "reason": row.get("reason", "")})
    for row in active_questions:
        raw_events.append({"event_type": "question_created_from_evidence", "question_id": row.get("question_id"), "derived_from": row.get("derived_from", []), "reason": row.get("why_needed", "")})
    for row in patch.get("reading_link_updates", []):
        raw_events.append({"event_type": "reading_link_added", "text_span": row.get("text_span"), "evidence_refs": row.get("evidence_refs", []), "reason": row.get("reading_effect", "")})

    events: list[dict[str, Any]] = []
    for index, event in enumerate(raw_events, start=1):
        payload = {"story_id": story_id, "iteration": 1, "sequence": index, **event}
        payload["event_id"] = "srm0-event-" + sha256_text(stable_json(payload))[:16]
        events.append(payload)
    return state, events


def validate_question_output(value: Mapping[str, Any], story_text: str) -> list[str]:
    errors: list[str] = []
    puzzles = value.get("textual_puzzles", [])
    if not isinstance(puzzles, list) or not 1 <= len(puzzles) <= MAX_PUZZLES:
        errors.append("textual_puzzles must contain 1-3 items")
    for row in puzzles if isinstance(puzzles, list) else []:
        if not isinstance(row, Mapping) or not row.get("span") or row["span"] not in story_text:
            errors.append("every puzzle span must be an exact Story substring")
        if isinstance(row, Mapping) and row.get("category") not in PUZZLE_CATEGORIES:
            errors.append("invalid puzzle category")
    active = value.get("active_question")
    if not isinstance(active, Mapping) or active.get("status") != "active" or not active.get("question"):
        errors.append("exactly one active question is required")
    probes = value.get("search_probes", [])
    if not isinstance(probes, list) or not MIN_PROBES <= len(probes) <= MAX_PROBES:
        errors.append("search_probes must contain 3-5 items")
    return errors


def validate_memory_patch(value: Mapping[str, Any], candidate_refs: Iterable[str], story_text: str) -> list[str]:
    errors: list[str] = []
    allowed = set(candidate_refs)
    decisions = value.get("evidence_decisions", [])
    kept = [row for row in decisions if isinstance(row, Mapping) and row.get("decision") == "keep"]
    if len(kept) > MAX_KEEP_REFS:
        errors.append("more than three evidence refs kept")
    for row in decisions:
        if not isinstance(row, Mapping) or row.get("evidence_ref") not in allowed:
            errors.append("evidence decision references a non-retrieved ref")
    for row in value.get("claim_updates", []):
        if not row.get("evidence_refs") or not set(row["evidence_refs"]).issubset(allowed):
            errors.append("claim update lacks valid evidence refs")
    active_count = sum(1 for row in value.get("new_questions", []) if row.get("next_active_question"))
    if active_count != 1:
        errors.append("Completion 2 must contain exactly one next active question")
    for row in value.get("new_questions", []):
        if not row.get("derived_from") or not row.get("why_needed") or row.get("reading_target") not in story_text:
            errors.append("new question lacks derived_from, why_needed, or exact reading_target")
    for row in value.get("reading_link_updates", []):
        if row.get("text_span") not in story_text or not set(row.get("evidence_refs", [])).issubset(allowed):
            errors.append("reading link lacks exact span or valid evidence refs")
    return errors
