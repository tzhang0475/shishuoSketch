#!/usr/bin/env python3
"""Deterministic contracts and local retrieval for the SRM0.4A pilot."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from .ds1_common import ROOT, sha256_file, stable_json, write_json
except ImportError:  # pragma: no cover - direct execution
    from ds1_common import ROOT, sha256_file, stable_json, write_json


SCHEMA_VERSION = 1
MODEL = "deepseek-v4-flash"
PROVIDER = "deepseek"
PROMPT_VERSION = "srm0.4a-convergence-v1"
STORY_COUNT = 6
MAX_INITIAL_GAPS = 3
MAX_EVIDENCE_ROUNDS = 4
MAX_RETRIEVED = 12
MAX_OPENED = 5
MAX_MODEL_CANDIDATE_CHARS = 360
MAX_ANSWERED_ASPECTS = 3
MAX_UNANSWERED_ASPECTS = 3
MAX_CONFLICTS = 3

SELECTION_PATH = Path("data/generated/srm0/srm0-4a-selection.json")
BATCH_SUMMARY_PATH = Path("data/generated/srm0/srm0-4a-batch-summary.json")
CORPUS_INDEX_PATH = Path("data/shishuo-corpus-index.json")
SHISHUO_SEARCH_PATH = Path("data/derived/ds2-1a-shishuo-search-corpus.json")
JIANSU_ASSERTIONS_PATH = Path("data/derived/s1-jianshu-historical-assertions.json")
JIANSU_CITATIONS_PATH = Path("data/derived/s1-jianshu-source-citations.json")
JINSHU_INDEX_PATH = Path("data/jinshu-unit-index.json")
SGZ_PATH = Path("data/derived/sgz1-sanguozhi-complete-corpus.json")
ZTJ_CHRONOLOGY_PATH = Path("data/derived/ztj0-chronology-index.json")
ZTJ_KAOYI_PATH = Path("data/derived/ztj0-kaoyi-index.json")

# All Stories used by the preceding SRM, DS and IRR prompt experiments.
EXCLUDED_STORIES = {
    "27-jiajue-008",
    "03-zhengshi-005",
    "05-fangzheng-032",
    "02-yanyu-036",
    "19-xianyuan-026",
    "09-pinzao-017",
    "02-yanyu-035",
    "06-yaliang-017",
}

RICH_RULE = {"main_text_chars_min": 50, "liu_blocks_min": 4, "jianshu_chars_min": 500}
MEDIUM_RULE = {"liu_blocks_min": 1, "jianshu_chars_min": 100}
LOW_RULE = {"liu_blocks_max": 1, "jianshu_chars_max": 99}

FORBIDDEN_MODEL_KEYS = {
    "state", "next_action", "question_type", "category", "relation_type",
    "search_probe", "search_probes", "retrieval", "search_results",
    "canonical_fact", "canonical_write_back", "person_id", "fact_id",
}
GAP_LEAK_PATTERNS = (
    "可能是", "可能为", "可能指", "应为", "應為", "应该是", "應該是",
    "即是", "即为", "即為", "也就是", "换言之", "換言之", "意为", "意為",
    "解释为", "解釋為", "可理解为", "可理解為",
)
BOUNDARY_PUNCTUATION = " \t\r\n\u3000，。；：！？、,.!?;:「」『』“”‘’\"'（）()[]【】《》〈〉﹁﹂"


def read_json(root: Path, relative: Path) -> Any:
    return _cached_json(str(root.resolve()), relative.as_posix())


@lru_cache(maxsize=32)
def _cached_json(root_name: str, relative_name: str) -> Any:
    return json.loads((Path(root_name) / relative_name).read_text(encoding="utf-8"))


@lru_cache(maxsize=8)
def _source_artifact_hashes(root_name: str) -> dict[str, str | None]:
    root = Path(root_name)
    result: dict[str, str | None] = {}
    for path in (SHISHUO_SEARCH_PATH, JIANSU_ASSERTIONS_PATH, JIANSU_CITATIONS_PATH):
        result[path.as_posix()] = sha256_file(root, path) if (root / path).is_file() else None
    return result


def _text(value: Any) -> str:
    return str(value or "").strip()


def _hash(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def _compact(value: str) -> str:
    return re.sub(r"[\s\W_]+", "", unicodedata.normalize("NFKC", value or ""), flags=re.UNICODE)


def fold(value: str) -> str:
    return unicodedata.normalize("NFKC", value or "").translate(str.maketrans({
        "魏": "魏", "濤": "涛", "嶠": "峤", "嶺": "岭", "為": "为", "爲": "为",
        "後": "后", "與": "与", "並": "并", "貴": "贵", "勝": "胜", "說": "说",
        "時": "时", "任": "任", "關": "关", "係": "系", "諸": "诸", "傳": "传",
    })).lower()


def _walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key)
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def story_ids_from_corpus(root: Path = ROOT) -> list[str]:
    document = read_json(root, SHISHUO_SEARCH_PATH)
    return sorted(str(row["story_id"]) for row in document.get("records", []) if isinstance(row, Mapping) and row.get("story_id"))


def _citation_sources(root: Path) -> dict[str, list[str]]:
    if not (root / JIANSU_CITATIONS_PATH).is_file():
        return {}
    document = read_json(root, JIANSU_CITATIONS_PATH)
    result: dict[str, set[str]] = {}
    for row in document.get("records", []) if isinstance(document, Mapping) else []:
        if isinstance(row, Mapping) and row.get("assertion_id") and row.get("normalized_source"):
            result.setdefault(str(row["assertion_id"]), set()).add(str(row["normalized_source"]))
    return {key: sorted(values) for key, values in sorted(result.items())}


def _story_record(root: Path, story_id: str) -> dict[str, Any]:
    document = read_json(root, SHISHUO_SEARCH_PATH)
    for row in document.get("records", []):
        if isinstance(row, Mapping) and row.get("story_id") == story_id:
            return dict(row)
    raise ValueError(f"unknown Shishuo Story: {story_id}")


def story_material(root: Path, story_id: str) -> dict[str, Any]:
    record = _story_record(root, story_id)
    assertions = read_json(root, JIANSU_ASSERTIONS_PATH)
    citations = _citation_sources(root)
    rows = [
        row for row in assertions.get("records", [])
        if isinstance(row, Mapping)
        and row.get("story_id") == story_id
        and row.get("text")
        and row.get("layer") != "liu_annotation"
    ]
    rows.sort(key=lambda row: (int((row.get("source_locator") or {}).get("block_index", 10**9)), str(row.get("assertion_id"))))
    attached: dict[str, dict[str, Any]] = {
        "MAIN": {"ref": "MAIN", "work": "世說新語", "source_layer": "main_text", "text": str(record.get("main_text", "")), "source_path": record.get("source_path")},
    }
    liu_notes: list[dict[str, Any]] = []
    for index, row in enumerate(record.get("liu_annotations", []), start=1):
        ref = f"L{index:02d}"
        note = {
            "ref": ref,
            "work": "世說新語",
            "source_layer": "liu_annotation",
            "text": str(row.get("text", "")),
            "evidence_ids": list(row.get("evidence_ids") or []),
            "source_locator": dict(row.get("source_locator") or {}),
        }
        liu_notes.append(note)
        attached[ref] = note
    jianshu_notes: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        ref = f"J{index:02d}"
        note = {
            "ref": ref,
            "work": "余嘉錫箋疏",
            "source_layer": str(row.get("layer") or "jianshu_note"),
            "text": str(row["text"]),
            "speaker": row.get("attribution"),
            "source_labels": citations.get(str(row.get("assertion_id")), []),
            "local_ref": row.get("assertion_id"),
            "source_locator": dict(row.get("source_locator") or {}),
            "canonicalization_status": row.get("canonicalization_status"),
        }
        jianshu_notes.append(note)
        attached[ref] = note
    return {
        "story_id": story_id,
        "chapter_id": record.get("chapter_id"),
        "chapter_heading": record.get("chapter_heading"),
        "entry_number": record.get("entry_number"),
        "main_text": str(record.get("main_text", "")),
        "liu_notes": liu_notes,
        "jianshu_notes": jianshu_notes,
        "attached": attached,
        "main_text_chars": len(str(record.get("main_text", ""))),
        "liu_block_count": len(liu_notes),
        "liu_chars": sum(len(note["text"]) for note in liu_notes),
        "jianshu_note_count": len(jianshu_notes),
        "jianshu_chars": sum(len(note["text"]) for note in jianshu_notes),
        "source_path": record.get("source_path"),
        "source_sha256": record.get("source_sha256"),
        "source_artifacts": {
            **_source_artifact_hashes(str(root.resolve())),
        },
    }


def classify_metrics(row: Mapping[str, Any]) -> str:
    main_chars = int(row.get("main_text_chars", 0))
    liu_blocks = int(row.get("liu_block_count", 0))
    jianshu_chars = int(row.get("jianshu_chars", 0))
    if main_chars >= RICH_RULE["main_text_chars_min"] and liu_blocks >= RICH_RULE["liu_blocks_min"] and jianshu_chars >= RICH_RULE["jianshu_chars_min"]:
        return "rich_commentary"
    if liu_blocks <= LOW_RULE["liu_blocks_max"] and jianshu_chars <= LOW_RULE["jianshu_chars_max"]:
        return "low_context_control"
    if liu_blocks >= MEDIUM_RULE["liu_blocks_min"] or jianshu_chars >= MEDIUM_RULE["jianshu_chars_min"]:
        return "medium_commentary"
    return "other"


def selection(root: Path = ROOT, excluded: set[str] | None = None) -> dict[str, Any]:
    excluded = set(excluded or EXCLUDED_STORIES)
    records: list[dict[str, Any]] = []
    for story_id in story_ids_from_corpus(root):
        if story_id in excluded:
            continue
        material = story_material(root, story_id)
        classification = classify_metrics(material)
        records.append({
            "story_id": story_id,
            "class": classification,
            "main_text_chars": material["main_text_chars"],
            "liu_block_count": material["liu_block_count"],
            "jianshu_note_count": material["jianshu_note_count"],
            "jianshu_chars": material["jianshu_chars"],
            "selection_hash": hashlib.sha256(story_id.encode("utf-8")).hexdigest(),
        })
    chosen: list[dict[str, Any]] = []
    targets = {"rich_commentary": 3, "medium_commentary": 2, "low_context_control": 1}
    for class_name, count in targets.items():
        candidates = sorted((row for row in records if row["class"] == class_name), key=lambda row: row["selection_hash"])
        chosen.extend(candidates[:count])
    chosen.sort(key=lambda row: (row["class"], row["selection_hash"], row["story_id"]))
    counts = {class_name: sum(row["class"] == class_name for row in records) for class_name in targets}
    return {
        "schema": "srm0-4a-selection",
        "schema_version": SCHEMA_VERSION,
        "stage": "deterministic_fresh_story_selection",
        "excluded_stories": sorted(excluded),
        "rules": {"rich": RICH_RULE, "medium": MEDIUM_RULE, "low": LOW_RULE},
        "candidate_counts": counts,
        "selected": chosen,
        "selection_rationale": "All prior SRM/DS/IRR pilot Stories are excluded. Within each observed commentary class, SHA-256(Story ID) ordering selects the first eligible records; no success-based hand selection is used.",
        "canonical_write_back": False,
    }


def build_initial_payload(material: Mapping[str, Any]) -> dict[str, Any]:
    return {"story_id": material["story_id"], "primary_text": {"label": "世說新語正文", "text": material["main_text"]}}


INITIAL_SYSTEM_PROMPT = """你第一次阅读一则《世说新语》，现在只给你正文。
找出至多三个如果不进一步理解，就可能影响正文阅读的关键缺口。

每个缺口必须绑定正文准确文字，只描述缺什么，不尝试回答，不解释词义，不猜异文，不使用外部知识，不生成搜索词。
优先选择答案可能改变人物处境、行动意义、场景关系、隐喻或叙事力量的缺口；不要只扩展姓名或孤立字词，除非它确实改变正文理解。
如果正文其他部分已经直接回答某个问题，不要列为缺口。

只返回 JSON：{"gaps":[{"question_id":"Q1","story_span":"正文原文","gap":"简短缺口"}]}，最多三个。"""


COMMENTARY_SYSTEM_PROMPT = """请检查冻结的正文阅读缺口，以及所附刘孝标注、余嘉锡《笺疏》。只返回语义增量，不输出 state 或 next_action。

判断注释实际回答了什么、仍有什么影响正文理解的缺口、是否有材料冲突。reading_sufficient 只表示当前阅读已经足够，不表示历史事实已被最终验证。不要为了有趣继续研究，不使用外部知识。

每个 answered_aspect 和 conflict 都必须引用输入中的 ref 与逐字 quote。unanswered_aspects 只保留仍影响正文理解的事项，使用 aspect_id、gap、reading_impact(high|medium|low)。

只返回 JSON：{"updates":[{"question_id":"Q1","answered_aspects":[{"aspect_id":"Q1-A1","claim":"...","evidence":[{"ref":"...","quote":"..."}]}],"unanswered_aspects":[{"aspect_id":"Q1-U1","gap":"...","reading_impact":"high"}],"conflicts":[{"conflict_id":"Q1-C1","description":"...","evidence":[{"ref":"...","quote":"..."}]}],"reading_sufficient":true,"historical_verification_open":false}]}。"""


RETRIEVAL_SYSTEM_PROMPT = """请根据当前正文阅读缺口和本轮本地史料候选，更新语义理解。只使用输入候选，不使用预训练知识。

只写实际被候选证据支持的 answered_aspects；unanswered_aspects 只保留仍影响正文理解的窄缺口；conflicts 只写材料明确冲突。reading_sufficient 表示当前阅读是否足够，不等于历史学上的最终验证。不要输出 state、next_action、搜索词或 canonical 事实，不要为了有趣继续研究。

每个使用的证据必须引用候选 ref 和逐字 quote。只返回 JSON 对象，且只能有顶层字段 updates；每个 update 只能有 question_id、answered_aspects、unanswered_aspects、conflicts、reading_sufficient、historical_verification_open。不要返回数组本身或其他状态字段。"""


def build_initial_messages(material: Mapping[str, Any]) -> list[dict[str, str]]:
    return [{"role": "system", "content": INITIAL_SYSTEM_PROMPT}, {"role": "user", "content": stable_json(build_initial_payload(material))}]


def build_commentary_payload(material: Mapping[str, Any], questions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "story_id": material["story_id"],
        "primary_text": {"label": "世說新語正文", "text": material["main_text"]},
        "frozen_questions": [{"question_id": row["question_id"], "story_span": row["story_span"], "gap": row["gap"]} for row in questions],
        "early_commentary": {"label": "劉孝標注", "notes":[{"ref": n["ref"], "text": n["text"]} for n in material["liu_notes"]]},
        "later_commentary": {"label": "余嘉錫箋疏", "notes":[{"ref": n["ref"], "layer": n["source_layer"], "speaker": n.get("speaker"), "source_labels": n.get("source_labels", []), "text": n["text"]} for n in material["jianshu_notes"]]},
    }


def build_commentary_messages(material: Mapping[str, Any], questions: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    return [{"role": "system", "content": COMMENTARY_SYSTEM_PROMPT}, {"role": "user", "content": stable_json(build_commentary_payload(material, questions))}]


def build_retrieval_payload(material: Mapping[str, Any], questions: Sequence[Mapping[str, Any]], candidates: Sequence[Mapping[str, Any]], previous: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "story_id": material["story_id"],
        "primary_text": {"label": "世說新語正文", "text": material["main_text"]},
        "active_questions": [
            {
                "question_id": row["question_id"],
                "parent_question_id": row.get("parent_question_id"),
                "parent_aspect_id": row.get("parent_aspect_id"),
                "story_span": row["story_span"],
                "gap": row["gap"],
                "current_reading": row.get("current_reading") or {
                    "state": row.get("state"),
                    "working_answer": row.get("working_answer", ""),
                    "supporting_refs": row.get("supporting_refs", []),
                    "remaining_gap": row.get("remaining_gap"),
                },
            }
            for row in questions
        ],
        "local_evidence_candidates": [
            {"ref": row["ref"], "work": row["work"], "source_layer": row["source_layer"], "snippet": row["snippet"]}
            for row in candidates
        ],
    }


def build_retrieval_messages(material: Mapping[str, Any], questions: Sequence[Mapping[str, Any]], candidates: Sequence[Mapping[str, Any]], previous: Mapping[str, Any]) -> list[dict[str, str]]:
    return [{"role": "system", "content": RETRIEVAL_SYSTEM_PROMPT}, {"role": "user", "content": stable_json(build_retrieval_payload(material, questions, candidates, previous))}]


def _align_span(value: Any, source: str) -> str:
    candidate = _text(value)
    if candidate in source:
        return candidate
    compact_candidate = "".join(char for char in candidate if not char.isspace())
    compact_source = "".join(char for char in source if not char.isspace())
    start = compact_source.find(compact_candidate) if compact_candidate else -1
    if start < 0:
        return candidate
    offsets = [index for index, char in enumerate(source) if not char.isspace()]
    return source[offsets[start] : offsets[start + len(compact_candidate) - 1] + 1]


def normalize_initial(raw: Mapping[str, Any], material: Mapping[str, Any]) -> dict[str, Any]:
    rows = raw.get("gaps", []) if isinstance(raw.get("gaps"), list) else []
    return {"gaps": [
        {"question_id": _text(row.get("question_id") or f"Q{index}"), "story_span": _align_span(row.get("story_span"), material["main_text"]), "gap": _text(row.get("gap"))}
        for index, row in enumerate(rows[:MAX_INITIAL_GAPS], start=1) if isinstance(row, Mapping)
    ]}


def _normalize_quote(quote: str, source: str) -> tuple[str, str | None]:
    candidate = _text(quote)
    if candidate in source:
        return candidate, None
    compact_candidate = "".join(char for char in candidate if not char.isspace())
    compact_source = "".join(char for char in source if not char.isspace())
    start = compact_source.find(compact_candidate) if compact_candidate else -1
    if start >= 0:
        offsets = [index for index, char in enumerate(source) if not char.isspace()]
        return source[offsets[start] : offsets[start + len(compact_candidate) - 1] + 1], "whitespace_normalized"
    # Prefer removing only an outer boundary character that prevents an
    # otherwise exact source substring.  This preserves source-final
    # punctuation instead of stripping it together with an extra quote mark.
    for left in range(len(candidate) + 1):
        if any(char not in BOUNDARY_PUNCTUATION for char in candidate[:left]):
            break
        for right in range(len(candidate) - left + 1):
            if right and any(char not in BOUNDARY_PUNCTUATION for char in candidate[len(candidate) - right:]):
                break
            trimmed_boundary = candidate[left : len(candidate) - right if right else len(candidate)]
            if (left or right) and trimmed_boundary and trimmed_boundary in source:
                return trimmed_boundary, "boundary_punctuation_trimmed"
    trimmed = candidate.strip(BOUNDARY_PUNCTUATION)
    if trimmed and trimmed != candidate:
        if trimmed in source:
            return trimmed, "boundary_punctuation_trimmed"
        compact_trimmed = "".join(char for char in trimmed if not char.isspace())
        start = compact_source.find(compact_trimmed) if compact_trimmed else -1
        if start >= 0:
            offsets = [index for index, char in enumerate(source) if not char.isspace()]
            return source[offsets[start] : offsets[start + len(compact_trimmed) - 1] + 1], "whitespace_and_boundary_normalized"
    return candidate, None


def normalize_delta(raw: Mapping[str, Any], sources: Mapping[str, str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    updates: list[dict[str, Any]] = []
    normalizations: list[dict[str, Any]] = []
    rows = raw.get("updates", []) if isinstance(raw.get("updates"), list) else []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        answered: list[dict[str, Any]] = []
        for aspect in row.get("answered_aspects", []) if isinstance(row.get("answered_aspects"), list) else []:
            if not isinstance(aspect, Mapping):
                continue
            evidence = []
            for item in aspect.get("evidence", []) if isinstance(aspect.get("evidence"), list) else []:
                if not isinstance(item, Mapping):
                    continue
                ref, quote = _text(item.get("ref")), _text(item.get("quote"))
                normalized_quote, method = _normalize_quote(quote, sources.get(ref, "")) if ref in sources else (quote, None)
                if method:
                    normalizations.append({"ref": ref, "method": method, "original_quote": quote, "normalized_quote": normalized_quote})
                evidence.append({"ref": ref, "quote": normalized_quote})
            answered.append({"aspect_id": _text(aspect.get("aspect_id")), "claim": _text(aspect.get("claim")), "evidence": evidence})
        unanswered = []
        for aspect in row.get("unanswered_aspects", []) if isinstance(row.get("unanswered_aspects"), list) else []:
            if not isinstance(aspect, Mapping):
                continue
            impact = aspect.get("reading_impact") if aspect.get("reading_impact") in {"high", "medium", "low"} else "medium"
            unanswered.append({"aspect_id": _text(aspect.get("aspect_id")), "gap": _text(aspect.get("gap")), "reading_impact": impact})
        conflicts = []
        for conflict in row.get("conflicts", []) if isinstance(row.get("conflicts"), list) else []:
            if not isinstance(conflict, Mapping):
                continue
            evidence = []
            for item in conflict.get("evidence", []) if isinstance(conflict.get("evidence"), list) else []:
                if not isinstance(item, Mapping):
                    continue
                ref, quote = _text(item.get("ref")), _text(item.get("quote"))
                normalized_quote, method = _normalize_quote(quote, sources.get(ref, "")) if ref in sources else (quote, None)
                if method:
                    normalizations.append({"ref": ref, "method": method, "original_quote": quote, "normalized_quote": normalized_quote})
                evidence.append({"ref": ref, "quote": normalized_quote})
            conflicts.append({"conflict_id": _text(conflict.get("conflict_id")), "description": _text(conflict.get("description")), "evidence": evidence})
        updates.append({
            "question_id": _text(row.get("question_id")),
            "answered_aspects": answered,
            "unanswered_aspects": unanswered,
            "conflicts": conflicts,
            "reading_sufficient": row.get("reading_sufficient"),
            "historical_verification_open": row.get("historical_verification_open"),
        })
    return {"updates": updates}, normalizations


def validate_initial(raw: Mapping[str, Any], normalized: Mapping[str, Any], material: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(raw) != {"gaps"}:
        errors.append("initial output must contain only gaps")
    if not isinstance(raw.get("gaps"), list) or len(raw.get("gaps", [])) > MAX_INITIAL_GAPS:
        errors.append("initial gaps must be an array of at most three")
    for key in _walk_keys(raw):
        if key in FORBIDDEN_MODEL_KEYS:
            errors.append(f"forbidden initial field: {key}")
    for row in raw.get("gaps", []) if isinstance(raw.get("gaps"), list) else []:
        if not isinstance(row, Mapping) or set(row) != {"question_id", "story_span", "gap"}:
            errors.append("initial gap has unexpected fields")
    seen: set[str] = set()
    for row in normalized.get("gaps", []) if isinstance(normalized.get("gaps"), list) else []:
        if any(not _text(row.get(field)) for field in ("question_id", "story_span", "gap")):
            errors.append("initial gap has an empty field")
            continue
        if row["question_id"] in seen:
            errors.append("duplicate initial question_id")
        seen.add(row["question_id"])
        if row["story_span"] not in material["main_text"]:
            errors.append("initial story_span is not exact")
        if len(row["gap"]) > 120 or any(pattern in row["gap"] for pattern in GAP_LEAK_PATTERNS):
            errors.append("initial gap is verbose or contains an attempted answer")
    raw_gaps = raw.get("gaps") if isinstance(raw.get("gaps"), list) else None
    if raw_gaps is None or len(normalized.get("gaps", [])) != len(raw_gaps):
        errors.append("initial normalization dropped a gap")
    return sorted(set(errors))


def validate_delta(raw: Mapping[str, Any], normalized: Mapping[str, Any], sources: Mapping[str, str], question_ids: set[str]) -> list[str]:
    errors: list[str] = []
    if set(raw) != {"updates"}:
        errors.append("semantic delta must contain only updates")
    for key in _walk_keys(raw):
        if key in FORBIDDEN_MODEL_KEYS:
            errors.append(f"forbidden semantic field: {key}")
    raw_updates = raw.get("updates") if isinstance(raw.get("updates"), list) else []
    updates = normalized.get("updates", [])
    if not isinstance(raw.get("updates"), list):
        errors.append("semantic updates must be an array")
    if isinstance(updates, list) and len(updates) != len(raw_updates):
        errors.append("semantic normalization dropped an update")
    if not isinstance(updates, list) or {str(row.get("question_id")) for row in updates if isinstance(row, Mapping)} != question_ids or len(updates) != len(question_ids):
        errors.append("semantic delta must contain exactly one update per active question")
    seen: set[str] = set()
    for raw_row, row in zip(raw_updates, updates):
        if not isinstance(row, Mapping):
            errors.append("semantic update is not an object")
            continue
        if not isinstance(raw_row, Mapping) or set(raw_row) != {"question_id", "answered_aspects", "unanswered_aspects", "conflicts", "reading_sufficient", "historical_verification_open"}:
            errors.append("semantic update has unexpected fields")
        qid = _text(row.get("question_id"))
        if qid in seen:
            errors.append("duplicate semantic update")
        seen.add(qid)
        if not isinstance(row.get("reading_sufficient"), bool) or not isinstance(row.get("historical_verification_open"), bool):
            errors.append("semantic booleans are required")
        raw_answered = raw_row.get("answered_aspects", []) if isinstance(raw_row, Mapping) and isinstance(raw_row.get("answered_aspects"), list) else []
        raw_unanswered = raw_row.get("unanswered_aspects", []) if isinstance(raw_row, Mapping) and isinstance(raw_row.get("unanswered_aspects"), list) else []
        raw_conflicts = raw_row.get("conflicts", []) if isinstance(raw_row, Mapping) and isinstance(raw_row.get("conflicts"), list) else []
        if not isinstance(raw_row, Mapping) or not isinstance(raw_row.get("answered_aspects"), list) or not isinstance(raw_row.get("unanswered_aspects"), list) or not isinstance(raw_row.get("conflicts"), list):
            errors.append("semantic aspect arrays are required")
        if len(row.get("answered_aspects", [])) != len(raw_answered) or len(row.get("unanswered_aspects", [])) != len(raw_unanswered) or len(row.get("conflicts", [])) != len(raw_conflicts):
            errors.append("semantic normalization dropped an aspect")
        for raw_aspect, aspect in zip(raw_answered, row.get("answered_aspects", [])):
            if not isinstance(aspect, Mapping) or not _text(aspect.get("aspect_id")) or not _text(aspect.get("claim")):
                errors.append("answered aspect is incomplete")
                continue
            if not isinstance(raw_aspect, Mapping) or set(raw_aspect) != {"aspect_id", "claim", "evidence"} or not isinstance(raw_aspect.get("evidence"), list):
                errors.append("answered aspect has unexpected fields")
            raw_evidence = raw_aspect.get("evidence", []) if isinstance(raw_aspect, Mapping) and isinstance(raw_aspect.get("evidence"), list) else []
            norm_evidence = aspect.get("evidence", []) if isinstance(aspect.get("evidence"), list) else []
            if len(raw_evidence) != len(norm_evidence):
                errors.append("answered aspect evidence was dropped")
            for raw_item, evidence in zip(raw_evidence, norm_evidence):
                if not isinstance(raw_item, Mapping) or set(raw_item) != {"ref", "quote"}:
                    errors.append("answered evidence has unexpected fields")
                if not isinstance(evidence, Mapping) or evidence.get("ref") not in sources or not _text(evidence.get("quote")) or evidence["quote"] not in sources.get(str(evidence.get("ref")), ""):
                    errors.append("semantic evidence ref/quote is invalid")
        if len(row.get("answered_aspects", [])) > MAX_ANSWERED_ASPECTS:
            errors.append("too many answered aspects")
        for raw_aspect, aspect in zip(raw_unanswered, row.get("unanswered_aspects", [])):
            if not isinstance(aspect, Mapping) or not _text(aspect.get("aspect_id")) or not _text(aspect.get("gap")) or aspect.get("reading_impact") not in {"high", "medium", "low"}:
                errors.append("unanswered aspect is incomplete")
            if not isinstance(raw_aspect, Mapping) or set(raw_aspect) != {"aspect_id", "gap", "reading_impact"}:
                errors.append("unanswered aspect has unexpected fields")
        if len(row.get("unanswered_aspects", [])) > MAX_UNANSWERED_ASPECTS:
            errors.append("too many unanswered aspects")
        for raw_conflict, conflict in zip(raw_conflicts, row.get("conflicts", [])):
            if not isinstance(conflict, Mapping) or not _text(conflict.get("conflict_id")) or not _text(conflict.get("description")):
                errors.append("conflict is incomplete")
                continue
            if not isinstance(raw_conflict, Mapping) or set(raw_conflict) != {"conflict_id", "description", "evidence"}:
                errors.append("conflict has unexpected fields")
            evidence_rows = conflict.get("evidence", [])
            raw_evidence_rows = raw_conflict.get("evidence", []) if isinstance(raw_conflict, Mapping) and isinstance(raw_conflict.get("evidence"), list) else []
            if not isinstance(evidence_rows, list) or not evidence_rows:
                errors.append("conflict requires evidence")
            if len(raw_evidence_rows) != len(evidence_rows):
                errors.append("conflict evidence was dropped")
            for raw_item, evidence in zip(raw_evidence_rows, evidence_rows):
                if not isinstance(raw_item, Mapping) or set(raw_item) != {"ref", "quote"}:
                    errors.append("conflict evidence has unexpected fields")
                if not isinstance(evidence, Mapping) or evidence.get("ref") not in sources or not _text(evidence.get("quote")) or evidence["quote"] not in sources.get(str(evidence.get("ref")), ""):
                    errors.append("conflict evidence ref/quote is invalid")
        if len(row.get("conflicts", [])) > MAX_CONFLICTS:
            errors.append("too many conflicts")
    return sorted(set(errors))


def self_resolution_reason(gap: Mapping[str, Any], material: Mapping[str, Any]) -> str | None:
    span = str(gap.get("story_span", ""))
    text = material["main_text"]
    span_start = text.find(span)
    quoted = re.findall(r"[『「“\"]([^』」”\"]{2,20})[』」”\"]", str(gap.get("gap", "")))
    for token in quoted:
        cursor = 0
        while True:
            position = text.find(token, cursor)
            if position < 0:
                break
            inside_selected_span = span_start >= 0 and span_start <= position and position + len(token) <= span_start + len(span)
            if not inside_selected_span:
                window = text[max(0, position - 8) : min(len(text), position + len(token) + 12)]
                if any(marker in window for marker in ("即", "乃", "是", "為", "为", "指", "謂", "谓")):
                    return f"same-story direct marker around {token}"
            cursor = position + max(1, len(token))
    return None


def low_leverage_reason(gap: Mapping[str, Any]) -> str | None:
    value = str(gap.get("gap", ""))
    low_markers = ("姓名", "名字", "籍贯", "籍貫", "家世", "生平")
    high_markers = ("为何", "為何", "何以", "如何", "关系", "關係", "职责", "職任", "处境", "處境", "局势", "局勢", "行动", "行動", "隐喻", "隱喻", "意味", "牵制", "牽制", "冲突", "衝突", "叙事", "敘事")
    if any(marker in value for marker in low_markers) and not any(marker in value for marker in high_markers):
        return "biographical/name expansion without an explicit reading-leverage marker"
    return None


def apply_gap_gates(gaps: Sequence[Mapping[str, Any]], material: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    for gap in gaps:
        reason = self_resolution_reason(gap, material) or low_leverage_reason(gap)
        row = dict(gap)
        row["gate"] = "removed" if reason else "accepted"
        row["gate_reason"] = reason
        audit.append(row)
        if not reason:
            accepted.append(dict(gap))
    return accepted, audit


def _terms(query: str) -> list[str]:
    compact = _compact(query)
    terms = [compact] if len(compact) >= 2 else []
    for width in (3, 2):
        terms.extend(compact[index:index + width] for index in range(max(0, len(compact) - width + 1)))
    return sorted(set(term for term in terms if term), key=lambda value: (-len(value), value))


def _snippet(text: str, query: str, limit: int = MAX_MODEL_CANDIDATE_CHARS) -> str:
    terms = _terms(query)
    folded = fold(text)
    start = 0
    for term in terms:
        position = folded.find(fold(term))
        if position >= 0:
            start = max(0, position - limit // 3)
            break
    return text[start : start + limit]


def _add_registry(registry: dict[str, dict[str, Any]], row: Mapping[str, Any]) -> None:
    ref = str(row.get("ref", ""))
    text = str(row.get("text", ""))
    if ref and text and ref not in registry:
        registry[ref] = dict(row)


def build_retrieval_registry(root: Path = ROOT) -> dict[str, dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}
    shishuo = read_json(root, SHISHUO_SEARCH_PATH)
    for record in shishuo.get("records", []):
        if not isinstance(record, Mapping):
            continue
        sid = str(record.get("story_id"))
        _add_registry(registry, {"ref": f"shishuo:{sid}:main", "work": "世說新語", "source_layer": "main_text", "text": record.get("main_text", ""), "story_id": sid, "source_path": record.get("source_path"), "source_sha256": record.get("source_sha256")})
        for annotation in record.get("liu_annotations", []):
            if isinstance(annotation, Mapping):
                aid = str(annotation.get("annotation_id"))
                _add_registry(registry, {"ref": f"shishuo:{sid}:liu:{aid}", "work": "世說新語", "source_layer": "liu_annotation", "text": annotation.get("text", ""), "story_id": sid, "source_path": (annotation.get("source_locator") or {}).get("source_path")})
    assertions = read_json(root, JIANSU_ASSERTIONS_PATH)
    for row in assertions.get("records", []):
        if isinstance(row, Mapping) and row.get("assertion_id") and row.get("text"):
            _add_registry(registry, {"ref": f"s1:{row['assertion_id']}", "work": "余嘉錫箋疏", "source_layer": row.get("layer", "unknown"), "text": row["text"], "story_id": row.get("story_id"), "source_locator": row.get("source_locator"), "source_sha256": row.get("text_sha256")})
    if (root / JINSHU_INDEX_PATH).is_file():
        index = read_json(root, JINSHU_INDEX_PATH)
        marker = "## Original source (exact)\n\n"
        for row in index.get("units", []):
            if not isinstance(row, Mapping) or not row.get("unit_id"):
                continue
            path = root / str(row.get("file_path", ""))
            if not path.is_file():
                continue
            content = path.read_text(encoding="utf-8")
            text = content.split(marker, 1)[1] if marker in content else ""
            _add_registry(registry, {"ref": f"jinshu:{row['unit_id']}", "work": "晉書", "source_layer": "main_text", "text": text, "source_path": row.get("file_path"), "source_locator": {"volume": row.get("volume"), "title": row.get("title")}})
    if (root / SGZ_PATH).is_file():
        sgz = read_json(root, SGZ_PATH)
        for record in sgz.get("records", []):
            if not isinstance(record, Mapping):
                continue
            for unit in record.get("units", []):
                if isinstance(unit, Mapping) and unit.get("unit_id") and unit.get("text"):
                    _add_registry(registry, {"ref": f"sanguozhi:{unit['unit_id']}", "work": "三國志", "source_layer": unit.get("layer", "unknown"), "text": unit["text"], "source_path": unit.get("source_path"), "source_sha256": record.get("source_sha256")})
    for path, prefix, work, layer, text_key in (
        (ZTJ_CHRONOLOGY_PATH, "ztj:chronology:", "資治通鑑", "chronology", "chronology_surface"),
        (ZTJ_KAOYI_PATH, "ztj:kaoyi:", "資治通鑑考異", "kaoyi", "chronology_surface"),
    ):
        if not (root / path).is_file():
            continue
        doc = read_json(root, path)
        for row in doc.get("records", []):
            if isinstance(row, Mapping) and row.get(text_key):
                key = row.get("block_id") or row.get("kaoyi_id")
                _add_registry(registry, {"ref": prefix + str(key), "work": work, "source_layer": layer, "text": row[text_key], "source_path": path.as_posix(), "source_locator": {key: key}})
    return registry


def search_registry(registry: Mapping[str, Mapping[str, Any]], query: str, *, exclude_story: str | None = None, top_k: int = MAX_RETRIEVED) -> dict[str, Any]:
    terms = _terms(query)
    compact_query = _compact(query)
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for ref, row in registry.items():
        if exclude_story and row.get("story_id") == exclude_story and str(row.get("work")) in {"世說新語", "余嘉錫箋疏"}:
            continue
        text = str(row.get("text", ""))
        folded_text = fold(_compact(text))
        score = 0
        if compact_query and fold(compact_query) in folded_text:
            score += 120 + len(compact_query) * 2
        hits = sum(1 for term in terms if len(term) >= 2 and fold(term) in folded_text)
        score += hits * 5
        if score <= 0:
            continue
        candidate = dict(row)
        candidate.update({"score": score, "snippet": _snippet(text, query)})
        scored.append((score, ref, candidate))
    scored.sort(key=lambda item: (-item[0], str(item[2].get("work", "")), item[1]))
    selected: list[dict[str, Any]] = []
    work_counts: dict[str, int] = {}
    for _, _, candidate in scored:
        work = str(candidate.get("work", ""))
        if work_counts.get(work, 0) >= 3 and len(selected) < top_k:
            continue
        selected.append(candidate)
        work_counts[work] = work_counts.get(work, 0) + 1
        if len(selected) >= top_k:
            break
    return {"raw_match_count": len(scored), "hits": selected}


def open_candidates(search_result: Mapping[str, Any], limit: int = MAX_OPENED) -> list[dict[str, Any]]:
    return [dict(row) for row in search_result.get("hits", [])[:limit] if isinstance(row, Mapping)]


def working_answer(claims: Sequence[Mapping[str, Any]]) -> str:
    values = [_text(row.get("claim")) for row in claims if isinstance(row, Mapping) and _text(row.get("claim"))][:2]
    return "".join(value if value.endswith(("。", "！", "？", ".", "!", "?")) else value + "。" for value in values)


def derive_question_state(question: Mapping[str, Any], update: Mapping[str, Any], prior: Mapping[str, Any] | None = None) -> dict[str, Any]:
    conflicts = update.get("conflicts", []) if isinstance(update.get("conflicts"), list) else []
    answered = update.get("answered_aspects", []) if isinstance(update.get("answered_aspects"), list) else []
    state = "conflicted" if conflicts else "substantially_explained" if update.get("reading_sufficient") is True else "partially_explained" if answered else "unexplained"
    unanswered = update.get("unanswered_aspects", []) if isinstance(update.get("unanswered_aspects"), list) else []
    high = [row for row in unanswered if isinstance(row, Mapping) and row.get("reading_impact") == "high" and _text(row.get("gap"))]
    remaining = high[0]["gap"] if high else next((row["gap"] for row in unanswered if isinstance(row, Mapping) and _text(row.get("gap"))), None)
    refs = sorted({str(item.get("ref")) for aspect in answered if isinstance(aspect, Mapping) for item in aspect.get("evidence", []) if isinstance(item, Mapping) and _text(item.get("ref"))} | {str(item.get("ref")) for conflict in conflicts if isinstance(conflict, Mapping) for item in conflict.get("evidence", []) if isinstance(item, Mapping) and _text(item.get("ref"))})
    return {
        "question_id": question["question_id"],
        "parent_question_id": question.get("parent_question_id"),
        "parent_aspect_id": question.get("parent_aspect_id"),
        "story_span": question["story_span"],
        "gap": question["gap"],
        "state": state,
        "working_answer": working_answer(answered),
        "supporting_refs": refs,
        "remaining_gap": remaining,
        "reading_sufficient": bool(update.get("reading_sufficient")),
        "historical_verification_open": bool(update.get("historical_verification_open")),
        "next_action": "stop" if update.get("reading_sufficient") is True else "retrieve_local" if high else "stop",
        "terminal_reason": "reading_sufficient" if update.get("reading_sufficient") is True else "not_worth_pursuing" if not high else None,
        "active": update.get("reading_sufficient") is not True and bool(high),
        "conflict_ids": sorted(str(row.get("conflict_id")) for row in conflicts if isinstance(row, Mapping) and row.get("conflict_id")),
    }


def make_refined_questions(question: Mapping[str, Any], update: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, aspect in enumerate(update.get("unanswered_aspects", []) if isinstance(update.get("unanswered_aspects"), list) else [], start=1):
        if not isinstance(aspect, Mapping) or aspect.get("reading_impact") != "high" or not _text(aspect.get("gap")) or not _text(aspect.get("aspect_id")):
            continue
        result.append({
            "question_id": f"{question['question_id']}.{index}",
            "parent_question_id": question["question_id"],
            "parent_aspect_id": aspect["aspect_id"],
            "story_span": question["story_span"],
            "gap": aspect["gap"],
        })
    return result


def semantic_delta_changed(previous: Mapping[str, Any] | None, current: Mapping[str, Any]) -> int:
    if previous is None:
        return int(bool(current.get("answered_aspects") or current.get("conflicts") or current.get("reading_sufficient")))
    for field in ("state", "working_answer", "remaining_gap", "reading_sufficient", "conflict_ids"):
        if previous.get(field) != current.get(field):
            return 1
    return 0


def evidence_novelty(used_refs: Sequence[str], seen_refs: set[str]) -> tuple[float, list[str]]:
    unique = sorted(set(str(ref) for ref in used_refs))
    new = [ref for ref in unique if ref not in seen_refs]
    return (len(new) / len(unique) if unique else 0.0), new


def saturation(metrics: Sequence[Mapping[str, Any]]) -> bool:
    if len(metrics) < 2:
        return False
    left, right = metrics[-2], metrics[-1]
    return left.get("D_t") == 0 and right.get("D_t") == 0 and float(left.get("N_t", 0)) < 0.2 and float(right.get("N_t", 0)) < 0.2


def boundary_normalization_count(rows: Sequence[Mapping[str, Any]]) -> int:
    return sum(1 for row in rows if row.get("method") in {"boundary_punctuation_trimmed", "whitespace_and_boundary_normalized"})


def review_template(story_ids: Sequence[str]) -> dict[str, Any]:
    return {"schema": "srm0-4a-review", "schema_version": SCHEMA_VERSION, "stories": {story_id: {"notes": ""} for story_id in sorted(story_ids)}}


__all__ = [
    "BATCH_SUMMARY_PATH", "BOUNDARY_PUNCTUATION", "COMMENTARY_SYSTEM_PROMPT", "CORPUS_INDEX_PATH", "EXCLUDED_STORIES",
    "INITIAL_SYSTEM_PROMPT", "JIANSU_ASSERTIONS_PATH", "LOW_RULE", "MAX_EVIDENCE_ROUNDS", "MODEL", "PROMPT_VERSION",
    "PROVIDER", "RETRIEVAL_SYSTEM_PROMPT", "ROOT", "SCHEMA_VERSION", "SELECTION_PATH", "SGZ_PATH", "STORY_COUNT",
    "ZTJ_CHRONOLOGY_PATH", "ZTJ_KAOYI_PATH", "apply_gap_gates", "boundary_normalization_count", "build_commentary_messages",
    "build_commentary_payload", "build_initial_messages", "build_initial_payload", "build_retrieval_messages", "build_retrieval_payload",
    "build_retrieval_registry", "classify_metrics", "derive_question_state", "evidence_novelty", "fold", "make_refined_questions",
    "normalize_delta", "normalize_initial", "open_candidates", "read_json", "review_template", "saturation", "search_registry",
    "selection", "semantic_delta_changed", "story_material", "story_ids_from_corpus", "stable_json", "validate_delta", "validate_initial",
    "working_answer",
]
