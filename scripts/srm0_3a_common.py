#!/usr/bin/env python3
"""Contracts and deterministic projections for the SRM0.3A pilot."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from .ds1_common import ROOT, read_json, sha256_file, stable_json, write_json
    from .srm0_2b_common import ENTRY_PATH, load_entry
    from .srm0_2m_common import resolve_jianshu_material
except ImportError:  # pragma: no cover - direct script execution
    from ds1_common import ROOT, read_json, sha256_file, stable_json, write_json
    from srm0_2b_common import ENTRY_PATH, load_entry
    from srm0_2m_common import resolve_jianshu_material


STORY_ID = "03-zhengshi-005"
OUTPUT_ROOT = Path("data/generated/srm0") / STORY_ID / "commentary-resolution"
REVIEW_PATH = Path("data/annotation/srm0-3a-commentary-resolution-review.json")
MODEL = "deepseek-v4-flash"
PROVIDER = "deepseek"
PROMPT_VERSION = "srm0.3a-commentary-resolution-v1"
SCHEMA_VERSION = 1
MAX_INITIAL_QUESTIONS = 3
MAX_RELATIONS = 4
MAX_APPRAISALS = 4
VALID_STATES = {"unexplained", "partially_explained", "substantially_explained", "conflicted"}
VALID_NEXT_ACTIONS = {"stop", "refine_question", "external_search"}
VALID_EVIDENCE_ROLES = {"supports", "limits", "conflicts"}
FORBIDDEN_KEYS = {
    "question_type",
    "category",
    "relation_type",
    "relation_category",
    "search_probe",
    "search_probes",
    "probes",
    "active_question",
    "next_question",
    "final_answer",
    "historical_answer",
    "claim_updates",
    "claims",
    "canonical_fact",
    "canonical_status",
    "is_canonical",
    "canonical_write_back",
    "person_id",
    "relation_id",
    "fact_id",
    "retrieval",
    "search_results",
}
TOP_LEVEL_INITIAL = {"questions"}
TOP_LEVEL_COMMENTARY = {"question_updates", "relation_candidates", "appraisal_candidates"}
DYNAMIC_RELATION_TERMS = (
    "关系密切",
    "親密",
    "亲密",
    "信任",
    "支配",
    "畏惧",
    "恐惧",
    "敌意",
    "同现",
    "同出現",
    "同出现",
    "同朝為官",
    "同朝为官",
    "同姓",
    "同族",
    "同宗",
    "並列",
    "并列",
    "同时代",
    "同時代",
    "后来",
    "後來",
    "将来",
    "將來",
    "必与",
    "必與",
    "将与",
    "將與",
)

INITIAL_SYSTEM_PROMPT = """你第一次阅读这一则《世说新语》。

现在只给你正文，不给任何注释或外部史料。

请找出至多三个：如果不知道背景、人物位置、词义或事件关系，就可能低估或误读正文的地方。

每个问题必须绑定正文中的准确文字。

不要泛泛询问人物生平。不要试图回答问题。不要使用外部历史知识。不要生成搜索词。

只返回 JSON：
{"questions":[{"question_id":"Q1","story_span":"正文原文","question":"...","why_unclear_from_main_text":"..."}]}

最多三个问题；不要添加问题分类、关系类别、历史答案或其他字段。"""

COMMENTARY_SYSTEM_PROMPT = """现在请检查刘孝标注和余嘉锡《笺疏》，判断它们对每一个正文问题已经回答到什么程度。

你的任务不是继续寻找有趣的问题，而是判断：
1. 当前注释已经说明了什么；
2. 哪些内容仍未说明；
3. 对理解这段正文而言，剩余缺口是否值得继续研究。

每个问题必须形成一个非常简短的 Working Answer。Working Answer 只是当前证据允许的最小结论，不是最终历史事实，也不是长篇解释。最多两句短句。

必须引用实际提供的注释 ref 和对应原文短引文。ref 必须是输入中出现的 Lxx 或 Jxx；quote 必须逐字取自对应 ref 的文本。不得使用外部历史知识。

如果当前材料已经足以理解正文，应停止，不要为了继续研究而制造新的问题。如果仍有重要缺口，新问题必须严格来自 remaining_gap，并继续绑定同一正文跨度。

区分史料支持、限制和冲突。不要把同现、同姓、同时代或推测自动写成关系候选；不要把评价写成客观人格事实。

只返回以下 JSON 结构，不能省略字段：
{"question_updates":[{"question_id":"Q1","story_span":"与原问题完全相同的正文跨度","question":"与原问题完全相同","state":"unexplained|partially_explained|substantially_explained|conflicted","working_answer":"最多两句","evidence":[{"ref":"Lxx或Jxx","quote":"该ref中的逐字短引文","role":"supports|limits|conflicts"}],"remaining_gap":"...","next_action":"stop|refine_question|external_search","refined_question":null}],"relation_candidates":[],"appraisal_candidates":[]}

每个原始问题恰好一个 question_update，必须重复 question_id、story_span、question；不要添加搜索结果、搜索词、事实数据库字段或 canonical 写回字段。"""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key)
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def _hash(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def _compact_whitespace(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _align_whitespace_quote(quote: str, source: str) -> str:
    """Align only omitted/extra whitespace; never alter source characters."""

    quote = _text(quote)
    if not quote or quote in source:
        return quote
    compact_quote = _compact_whitespace(quote)
    compact_source_chars: list[str] = []
    source_offsets: list[int] = []
    for offset, char in enumerate(source):
        if not char.isspace():
            compact_source_chars.append(char)
            source_offsets.append(offset)
    compact_source = "".join(compact_source_chars)
    start = compact_source.find(compact_quote)
    if start < 0 or not compact_quote:
        return quote
    end = start + len(compact_quote) - 1
    return source[source_offsets[start] : source_offsets[end] + 1]


def resolve_commentary_material(root: Path = ROOT) -> dict[str, Any]:
    """Build the local two-layer commentary packet without semantic inference."""

    material = resolve_jianshu_material(root)
    entry = material["entry"]
    early_notes = [
        {"ref": f"L{index:02d}", "text": str(row["text"])}
        for index, row in enumerate(entry["liu_annotations"], start=1)
    ]
    later_notes = [
        {
            "ref": str(note["note_id"]),
            "layer": str(note["layer"]),
            "speaker": note.get("speaker"),
            "source_labels": list(note.get("source_labels") or []),
            "text": str(note["text"]),
        }
        for note in material["notes"]
        if note.get("layer") != "liu_annotation"
    ]
    duplicate_notes = [note for note in material["notes"] if note.get("layer") == "liu_annotation"]
    return {
        "schema": "srm0-3a-commentary-material",
        "schema_version": SCHEMA_VERSION,
        "story_id": STORY_ID,
        "entry": entry,
        "early_notes": early_notes,
        "later_notes": later_notes,
        "duplicate_notes": [
            {"ref": str(note["note_id"]), "layer": str(note["layer"]), "text": str(note["text"])}
            for note in duplicate_notes
        ],
        "all_note_count": len(material["notes"]),
        "main_text_chars": len(str(entry["story_text"])),
        "liu_chars": sum(len(note["text"]) for note in early_notes),
        "later_commentary_chars": sum(len(note["text"]) for note in later_notes),
        "duplicate_commentary_chars_removed": sum(len(note["text"]) for note in duplicate_notes),
        "source_artifacts": {
            ENTRY_PATH.as_posix(): entry["entry_sha256"],
            "data/derived/s1-jianshu-historical-assertions.json": sha256_file(root, Path("data/derived/s1-jianshu-historical-assertions.json")),
            "data/derived/s1-jianshu-source-citations.json": sha256_file(root, Path("data/derived/s1-jianshu-source-citations.json")),
        },
    }


def build_initial_payload(material: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "story_id": STORY_ID,
        "primary_text": {
            "label": "世說新語正文",
            "text": str(material["entry"]["story_text"]),
        },
    }


def build_initial_messages(material: Mapping[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": INITIAL_SYSTEM_PROMPT},
        {"role": "user", "content": stable_json(build_initial_payload(material))},
    ]


def build_commentary_payload(material: Mapping[str, Any], questions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "story_id": STORY_ID,
        "primary_text": {
            "label": "世說新語正文",
            "text": str(material["entry"]["story_text"]),
        },
        "questions": [
            {
                "question_id": str(row.get("question_id") or ""),
                "story_span": str(row.get("story_span") or ""),
                "question": str(row.get("question") or ""),
            }
            for row in questions
        ],
        "early_commentary": {
            "label": "劉孝標注",
            "notes": list(material["early_notes"]),
        },
        "later_commentary": {
            "label": "余嘉錫箋疏",
            "notes": list(material["later_notes"]),
        },
    }


def build_commentary_messages(material: Mapping[str, Any], questions: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": COMMENTARY_SYSTEM_PROMPT},
        {"role": "user", "content": stable_json(build_commentary_payload(material, questions))},
    ]


def allowed_commentary_refs(material: Mapping[str, Any]) -> set[str]:
    return {note["ref"] for note in material["early_notes"]} | {note["ref"] for note in material["later_notes"]}


def source_text(ref: str, material: Mapping[str, Any]) -> str:
    if ref == "MAIN":
        return str(material["entry"]["story_text"])
    for note in material["early_notes"] + material["later_notes"]:
        if note["ref"] == ref:
            return str(note["text"])
    return ""


def normalize_initial(raw: Mapping[str, Any], material: Mapping[str, Any] | None = None) -> dict[str, Any]:
    rows = raw.get("questions", []) if isinstance(raw.get("questions"), list) else []
    questions: list[dict[str, Any]] = []
    for index, row in enumerate(rows[:MAX_INITIAL_QUESTIONS], start=1):
        if not isinstance(row, Mapping):
            continue
        story_span = _text(row.get("story_span") or row.get("span"))
        if material is not None:
            story_span = _align_whitespace_quote(story_span, str(material["entry"]["story_text"]))
        questions.append(
            {
                "question_id": _text(row.get("question_id") or row.get("id") or f"Q{index}"),
                "story_span": story_span,
                "question": _text(row.get("question")),
                "why_unclear_from_main_text": _text(row.get("why_unclear_from_main_text") or row.get("why_unclear") or row.get("why")),
            }
        )
    return {"questions": questions}


def normalize_commentary(raw: Mapping[str, Any], material: Mapping[str, Any], initial: Mapping[str, Any]) -> dict[str, Any]:
    updates: list[dict[str, Any]] = []
    rows = raw.get("question_updates", []) if isinstance(raw.get("question_updates"), list) else []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        evidence_rows = row.get("evidence", []) if isinstance(row.get("evidence"), list) else []
        evidence: list[dict[str, Any]] = []
        for item in evidence_rows:
            if not isinstance(item, Mapping):
                continue
            ref = _text(item.get("ref"))
            quote = _text(item.get("quote"))
            if ref in allowed_commentary_refs(material):
                quote = _align_whitespace_quote(quote, source_text(ref, material))
            evidence.append({"ref": ref, "quote": quote, "role": _text(item.get("role"))})
        refined = row.get("refined_question")
        if refined is not None:
            refined = _text(refined) or None
        updates.append(
            {
                "question_id": _text(row.get("question_id") or row.get("id")),
                "story_span": _text(row.get("story_span") or row.get("span")),
                "question": _text(row.get("question")),
                "state": _text(row.get("state") or row.get("status")),
                "working_answer": _text(row.get("working_answer") or row.get("answer")),
                "evidence": evidence,
                "remaining_gap": _text(row.get("remaining_gap") or row.get("gap")),
                "next_action": _text(row.get("next_action") or row.get("action")),
                "refined_question": refined,
            }
        )

    relation_candidates: list[dict[str, Any]] = []
    relation_rows = raw.get("relation_candidates", []) if isinstance(raw.get("relation_candidates"), list) else []
    for row in relation_rows[:MAX_RELATIONS]:
        if not isinstance(row, Mapping):
            continue
        evidence_rows = row.get("evidence", []) if isinstance(row.get("evidence"), list) else []
        evidence = []
        for item in evidence_rows:
            if not isinstance(item, Mapping):
                continue
            ref = _text(item.get("ref"))
            quote = _align_whitespace_quote(_text(item.get("quote")), source_text(ref, material)) if ref in allowed_commentary_refs(material) else _text(item.get("quote"))
            evidence.append({"ref": ref, "quote": quote})
        persons = row.get("persons") if isinstance(row.get("persons"), list) else []
        relation_candidates.append(
            {
                "persons": [_text(person) for person in persons if _text(person)],
                "observation": _text(row.get("observation") or row.get("description")),
                "evidence": evidence,
                "status": _text(row.get("status")) or "candidate",
            }
        )

    appraisal_candidates: list[dict[str, Any]] = []
    appraisal_rows = raw.get("appraisal_candidates", []) if isinstance(raw.get("appraisal_candidates"), list) else []
    for row in appraisal_rows[:MAX_APPRAISALS]:
        if not isinstance(row, Mapping):
            continue
        ref = _text(row.get("evidence_ref") or row.get("ref"))
        quote = _text(row.get("evidence_quote") or row.get("quote"))
        if ref in allowed_commentary_refs(material):
            quote = _align_whitespace_quote(quote, source_text(ref, material))
        appraisal_candidates.append(
            {
                "evaluator": _text(row.get("evaluator")),
                "target": _text(row.get("target")),
                "appraisal_text": _text(row.get("appraisal_text") or row.get("observation")),
                "evidence_ref": ref,
                "evidence_quote": quote,
                "status": _text(row.get("status")) or "candidate",
            }
        )

    return {
        "question_updates": updates,
        "relation_candidates": relation_candidates,
        "appraisal_candidates": appraisal_candidates,
    }


def _contains_person_id(value: Any) -> bool:
    if isinstance(value, str):
        return bool(re.search(r"(?:^|\b)person-[A-Za-z0-9_-]+(?:\b|$)", value))
    if isinstance(value, Mapping):
        return any(_contains_person_id(key) or _contains_person_id(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_person_id(child) for child in value)
    return False


def _sentence_count(value: str) -> int:
    return len(re.findall(r"[。！？!?]", value))


def _validate_evidence_items(items: Any, material: Mapping[str, Any], *, require_role: bool = True) -> list[str]:
    errors: list[str] = []
    if not isinstance(items, list) or not items:
        return ["evidence is required"]
    allowed = allowed_commentary_refs(material)
    for item in items:
        if not isinstance(item, Mapping):
            errors.append("evidence item is not an object")
            continue
        ref = _text(item.get("ref"))
        quote = _text(item.get("quote"))
        if ref not in allowed:
            errors.append("evidence ref is not in the commentary packet")
            continue
        if not quote or quote not in source_text(ref, material):
            errors.append("evidence quote is not an exact substring of its ref")
        if require_role and item.get("role") not in VALID_EVIDENCE_ROLES:
            errors.append("evidence role is invalid")
    return errors


def validate_initial(raw: Mapping[str, Any], normalized: Mapping[str, Any], material: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(raw) != TOP_LEVEL_INITIAL:
        errors.append("initial output must contain only questions")
    for key in _walk_keys(raw):
        if key in FORBIDDEN_KEYS:
            errors.append(f"forbidden initial field: {key}")
    if _contains_person_id(raw):
        errors.append("initial output contains a Person ID")
    rows = raw.get("questions")
    if not isinstance(rows, list):
        errors.append("questions must be an array")
    elif len(rows) > MAX_INITIAL_QUESTIONS:
        errors.append("initial question count exceeds three")
    seen: set[str] = set()
    main_text = str(material["entry"]["story_text"])
    for row in normalized.get("questions", []) if isinstance(normalized.get("questions"), list) else []:
        if not isinstance(row, Mapping) or any(not _text(row.get(key)) for key in ("question_id", "story_span", "question", "why_unclear_from_main_text")):
            errors.append("initial question has an empty required field")
            continue
        if row["question_id"] in seen:
            errors.append("initial question IDs are not unique")
        seen.add(row["question_id"])
        if row["story_span"] not in main_text:
            errors.append("initial story span is not exact primary text")
    return sorted(set(errors))


def validate_commentary(raw: Mapping[str, Any], normalized: Mapping[str, Any], material: Mapping[str, Any], initial: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(raw) != TOP_LEVEL_COMMENTARY:
        errors.append("commentary output has unexpected top-level fields")
    for key in _walk_keys(raw):
        if key in FORBIDDEN_KEYS:
            errors.append(f"forbidden commentary field: {key}")
    if _contains_person_id(raw):
        errors.append("commentary output contains a Person ID")

    initial_rows = initial.get("questions", []) if isinstance(initial.get("questions"), list) else []
    initial_by_id = {str(row.get("question_id")): row for row in initial_rows if isinstance(row, Mapping)}
    updates = normalized.get("question_updates", [])
    if not isinstance(updates, list) or len(updates) != len(initial_by_id):
        errors.append("there must be exactly one update for every initial question")
    seen: set[str] = set()
    for row in updates if isinstance(updates, list) else []:
        if not isinstance(row, Mapping):
            errors.append("question update is not an object")
            continue
        qid = _text(row.get("question_id"))
        if qid in seen:
            errors.append("question update IDs are not unique")
        seen.add(qid)
        original = initial_by_id.get(qid)
        if original is None:
            errors.append("question update does not match an initial question")
        else:
            if row.get("story_span") != original.get("story_span"):
                errors.append("question update changed the original Story span")
            if row.get("question") != original.get("question"):
                errors.append("question update changed the original question")
        if any(not _text(row.get(key)) for key in ("question_id", "story_span", "question", "state", "working_answer", "next_action")):
            errors.append("question update has an empty required field")
        if row.get("state") not in VALID_STATES:
            errors.append("question update state is invalid")
        if len(str(row.get("working_answer") or "")) > 240 or _sentence_count(str(row.get("working_answer") or "")) > 2:
            errors.append("working answer is longer than two short sentences")
        errors.extend(_validate_evidence_items(row.get("evidence"), material))
        state = row.get("state")
        remaining = _text(row.get("remaining_gap"))
        action = row.get("next_action")
        refined = row.get("refined_question")
        if action not in VALID_NEXT_ACTIONS:
            errors.append("question update next_action is invalid")
        if state == "substantially_explained":
            if remaining:
                errors.append("substantially explained question has a remaining gap")
            if action != "stop":
                errors.append("substantially explained question must stop")
            if refined is not None:
                errors.append("substantially explained question cannot be refined")
        elif state in {"partially_explained", "conflicted", "unexplained"} and not remaining:
            errors.append("non-substantial question has an empty remaining gap")
        if state == "conflicted" and not row.get("evidence"):
            errors.append("conflicted question has no evidence")
        if refined is not None:
            if action not in {"refine_question", "external_search"}:
                errors.append("refined question has an incompatible next_action")
            if not _text(refined) or refined == row.get("question"):
                errors.append("refined question is empty or repeats the original")
            if row.get("story_span") not in str(refined):
                errors.append("refined question is not bound to the original Story span")

    relations = normalized.get("relation_candidates", [])
    if not isinstance(relations, list) or len(relations) > MAX_RELATIONS:
        errors.append("relation candidate count exceeds four")
    for row in relations if isinstance(relations, list) else []:
        if (
            not isinstance(row, Mapping)
            or not isinstance(row.get("persons"), list)
            or len(row.get("persons", [])) != 2
            or any(not _text(person) for person in row.get("persons", []))
            or not _text(row.get("observation"))
            or row.get("status") != "candidate"
        ):
            errors.append("invalid relation candidate")
            continue
        if any(term in row["observation"] for term in DYNAMIC_RELATION_TERMS):
            errors.append("relation candidate is based on unsupported association or dynamic inference")
        errors.extend(_validate_evidence_items(row.get("evidence"), material, require_role=False))

    appraisals = normalized.get("appraisal_candidates", [])
    if not isinstance(appraisals, list) or len(appraisals) > MAX_APPRAISALS:
        errors.append("appraisal candidate count exceeds four")
    for row in appraisals if isinstance(appraisals, list) else []:
        if (
            not isinstance(row, Mapping)
            or any(not _text(row.get(key)) for key in ("evaluator", "target", "appraisal_text", "evidence_ref", "evidence_quote"))
            or row.get("status") != "candidate"
        ):
            errors.append("invalid appraisal candidate")
            continue
        errors.extend(_validate_evidence_items([{"ref": row.get("evidence_ref"), "quote": row.get("evidence_quote")}], material, require_role=False))
    return sorted(set(errors))


def normalization_repairs(raw_initial: Mapping[str, Any], normalized_initial: Mapping[str, Any], raw_commentary: Mapping[str, Any], normalized_commentary: Mapping[str, Any]) -> list[dict[str, Any]]:
    repairs: list[dict[str, Any]] = []
    initial_rows = raw_initial.get("questions", []) if isinstance(raw_initial.get("questions"), list) else []
    for index, row in enumerate(initial_rows):
        if not isinstance(row, Mapping):
            continue
        if "id" in row and "question_id" not in row:
            repairs.append({"kind": "field_alias", "field": "id", "normalized_field": "question_id", "index": index})
        if "span" in row and "story_span" not in row:
            repairs.append({"kind": "field_alias", "field": "span", "normalized_field": "story_span", "index": index})
        if "why" in row and "why_unclear_from_main_text" not in row:
            repairs.append({"kind": "field_alias", "field": "why", "normalized_field": "why_unclear_from_main_text", "index": index})
    commentary_rows = raw_commentary.get("question_updates", []) if isinstance(raw_commentary.get("question_updates"), list) else []
    for index, row in enumerate(commentary_rows):
        if not isinstance(row, Mapping):
            continue
        for source, target in (("id", "question_id"), ("span", "story_span"), ("status", "state"), ("answer", "working_answer"), ("gap", "remaining_gap"), ("action", "next_action")):
            if source in row and target not in row:
                repairs.append({"kind": "field_alias", "field": source, "normalized_field": target, "index": index})
        for item in row.get("evidence", []) if isinstance(row.get("evidence"), list) else []:
            if isinstance(item, Mapping) and _text(item.get("quote")) != _align_whitespace_quote(_text(item.get("quote")), source_text(_text(item.get("ref")), {"early_notes": [], "later_notes": []})):
                # The actual source-aware alignment is recorded below by the validator; this branch only
                # documents the provider-field pass without guessing a source ref.
                pass
    return repairs


def project_state(initial: Mapping[str, Any], commentary: Mapping[str, Any]) -> dict[str, Any]:
    questions = []
    for row in commentary.get("question_updates", []) if isinstance(commentary.get("question_updates"), list) else []:
        refs = sorted({str(item.get("ref")) for item in row.get("evidence", []) if isinstance(item, Mapping) and _text(item.get("ref"))})
        questions.append(
            {
                "question_id": row.get("question_id"),
                "story_span": row.get("story_span"),
                "question": row.get("question"),
                "state": row.get("state"),
                "working_answer": row.get("working_answer"),
                "supporting_refs": refs,
                "remaining_gap": row.get("remaining_gap"),
                "next_action": row.get("next_action"),
                "refined_question": row.get("refined_question"),
            }
        )
    relations = []
    for row in commentary.get("relation_candidates", []) if isinstance(commentary.get("relation_candidates"), list) else []:
        relations.append(
            {
                "persons": list(row.get("persons") or []),
                "observation": row.get("observation"),
                "supporting_refs": sorted({str(item.get("ref")) for item in row.get("evidence", []) if isinstance(item, Mapping) and _text(item.get("ref"))}),
                "status": row.get("status"),
            }
        )
    appraisals = []
    for row in commentary.get("appraisal_candidates", []) if isinstance(commentary.get("appraisal_candidates"), list) else []:
        appraisals.append(
            {
                "evaluator": row.get("evaluator"),
                "target": row.get("target"),
                "appraisal_text": row.get("appraisal_text"),
                "evidence_ref": row.get("evidence_ref"),
                "status": row.get("status"),
            }
        )
    return {
        "schema": "srm0-3a-research-state",
        "schema_version": SCHEMA_VERSION,
        "story_id": STORY_ID,
        "stage": "commentary_resolution_complete",
        "questions": questions,
        "relation_candidates": relations,
        "appraisal_candidates": appraisals,
        "canonical_write_back": False,
    }


def project_events(initial: Mapping[str, Any], commentary: Mapping[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in initial.get("questions", []) if isinstance(initial.get("questions"), list) else []:
        events.append({"event": "question_created", "question_id": row.get("question_id"), "story_span": row.get("story_span")})
    for row in commentary.get("question_updates", []) if isinstance(commentary.get("question_updates"), list) else []:
        refs = sorted({str(item.get("ref")) for item in row.get("evidence", []) if isinstance(item, Mapping) and _text(item.get("ref"))})
        events.append({"event": "commentary_read", "question_id": row.get("question_id"), "evidence_refs": refs})
        events.append({"event": "working_answer_updated", "question_id": row.get("question_id"), "state": row.get("state")})
        state_event = {
            "unexplained": "question_unexplained",
            "partially_explained": "question_partially_explained",
            "substantially_explained": "question_substantially_explained",
            "conflicted": "question_conflicted",
        }.get(str(row.get("state")))
        if state_event:
            events.append({"event": state_event, "question_id": row.get("question_id")})
        if row.get("refined_question"):
            events.append({"event": "refined_question_proposed", "question_id": row.get("question_id"), "refined_question": row.get("refined_question")})
        if row.get("next_action") == "stop":
            events.append({"event": "research_stop_recommended", "question_id": row.get("question_id")})
    for index, row in enumerate(commentary.get("relation_candidates", []) if isinstance(commentary.get("relation_candidates"), list) else []):
        events.append({"event": "relation_candidate_added", "index": index, "persons": row.get("persons")})
    for index, row in enumerate(commentary.get("appraisal_candidates", []) if isinstance(commentary.get("appraisal_candidates"), list) else []):
        events.append({"event": "appraisal_candidate_added", "index": index, "target": row.get("target")})
    return events


def review_template() -> dict[str, Any]:
    return {
        "schema": "srm0-3a-commentary-resolution-review",
        "schema_version": SCHEMA_VERSION,
        "story_id": STORY_ID,
        "initial_question_quality": None,
        "commentary_consumption": None,
        "working_answer_precision": None,
        "sufficiency_judgment": None,
        "remaining_gap_quality": None,
        "refined_question_quality": None,
        "stop_restraint": None,
        "relation_precision": None,
        "appraisal_precision": None,
        "self_reinforcement_control": None,
        "token_efficiency": None,
        "notes": "",
    }


__all__ = [
    "COMMENTARY_SYSTEM_PROMPT",
    "ENTRY_PATH",
    "INITIAL_SYSTEM_PROMPT",
    "MODEL",
    "OUTPUT_ROOT",
    "PROMPT_VERSION",
    "PROVIDER",
    "REVIEW_PATH",
    "ROOT",
    "STORY_ID",
    "TOP_LEVEL_COMMENTARY",
    "TOP_LEVEL_INITIAL",
    "allowed_commentary_refs",
    "build_commentary_messages",
    "build_commentary_payload",
    "build_initial_messages",
    "build_initial_payload",
    "normalize_commentary",
    "normalize_initial",
    "normalization_repairs",
    "project_events",
    "project_state",
    "read_json",
    "resolve_commentary_material",
    "review_template",
    "sha256_file",
    "source_text",
    "stable_json",
    "validate_commentary",
    "validate_initial",
    "write_json",
]
