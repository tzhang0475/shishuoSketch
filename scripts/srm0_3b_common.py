#!/usr/bin/env python3
"""Contracts for SRM0.3B minimal-question semantic-delta pilot."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from .ds1_common import ROOT, stable_json
    from .srm0_2m_common import resolve_jianshu_material
    from .srm0_3a_common import ENTRY_PATH, resolve_commentary_material, source_text
except ImportError:  # pragma: no cover - direct script execution
    from ds1_common import ROOT, stable_json
    from srm0_2m_common import resolve_jianshu_material
    from srm0_3a_common import ENTRY_PATH, resolve_commentary_material, source_text


STORY_ID = "03-zhengshi-005"
OUTPUT_ROOT = Path("data/generated/srm0") / STORY_ID / "commentary-resolution-v2"
REVIEW_PATH = Path("data/annotation/srm0-3b-commentary-resolution-review.json")
MODEL = "deepseek-v4-flash"
PROVIDER = "deepseek"
PROMPT_VERSION = "srm0.3b-minimal-question-semantic-delta-v1"
SCHEMA_VERSION = 1
MAX_GAPS = 3
MAX_ANSWERED_ASPECTS = 3
MAX_RELATIONS = 4
MAX_APPRAISALS = 4
VALID_CONFLICT_ROLES = {"supports", "limits", "conflicts"}
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
    "state",
    "next_action",
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
REPEATED_IMMUTABLE_KEYS = {"story_span", "gap", "question", "why_unclear_from_main_text", "why_unclear"}
EXPLANATION_LEAK_PATTERNS = (
    "可能是",
    "可能为",
    "可能指",
    "应为",
    "應為",
    "应该是",
    "應該是",
    "即是",
    "即为",
    "即為",
    "也就是",
    "换言之",
    "換言之",
    "意为",
    "意為",
    "解释为",
    "解釋為",
    "可理解为",
    "可理解為",
    "实为",
    "實為",
    "当指",
    "當指",
)
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

现在只给正文。找出至多三个如果不进一步理解，就可能影响正文阅读的关键缺口。

每个 gap 必须：
- 绑定正文中的准确文字；
- 只描述“缺什么”；
- 简短、单一、可继续核查。

不要尝试回答，不要提出可能答案，不要解释词义，不要猜异文，不要使用外部历史知识，不要生成搜索词。

只返回以下 JSON，不要添加其他字段：
{"gaps":[{"question_id":"Q1","story_span":"正文原文","gap":"具体缺少什么"}]}

最多三个 gap。gap 不要包含“可能是”“应为”“即”“换言之”等答案或解释。"""

COMMENTARY_SYSTEM_PROMPT = """现在阅读正文，并检查所附刘孝标注与余嘉锡《笺疏》是否回答了每个 frozen gap。

你的任务只返回语义增量：
1. supplied commentary 实际回答了什么；
2. 什么仍未回答且仍影响正文阅读；
3. 材料之间是否存在影响阅读的冲突；
4. 如果仍有缺口，提出一个严格由该缺口形成的更窄问题。

不要管理 state 或 next_action，不要重复 question_id 之外的 frozen question 字段，不要使用外部知识，不要因有趣而继续研究。

每个 answered_aspects claim 必须有至少一个实际存在的 ref 和逐字 quote。conflict 也必须有实际 ref 和逐字 quote。Python 会据此推导 state、Working Answer 和 next_action。

只返回以下 JSON，不能省略字段：
{"updates":[{"question_id":"Q1","answered_aspects":[{"claim":"...","evidence":[{"ref":"J14","quote":"..."}]}],"unanswered_aspects":[],"conflicts":[],"reading_sufficient":true,"historical_verification_open":true,"remaining_reading_gap":null,"refined_question":null}],"relation_candidates":[],"appraisal_candidates":[]}

reading_sufficient=true 时 remaining_reading_gap 和 refined_question 必须为 null；false 时 remaining_reading_gap 必须具体非空。不要输出 state、next_action、搜索词、搜索结果、事实数据库字段或 canonical 写回字段。"""


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


def _contains_person_id(value: Any) -> bool:
    if isinstance(value, str):
        return bool(re.search(r"(?:^|\b)person-[A-Za-z0-9_-]+(?:\b|$)", value))
    if isinstance(value, Mapping):
        return any(_contains_person_id(key) or _contains_person_id(child) for key, child in value.items())
    if isinstance(value, list):
        return any(_contains_person_id(child) for child in value)
    return False


def _align_whitespace(value: str, source: str) -> str:
    value = _text(value)
    if not value or value in source:
        return value
    compact_value = re.sub(r"\s+", "", value)
    source_chars: list[str] = []
    offsets: list[int] = []
    for index, char in enumerate(source):
        if not char.isspace():
            source_chars.append(char)
            offsets.append(index)
    start = "".join(source_chars).find(compact_value)
    if start < 0 or not compact_value:
        return value
    end = start + len(compact_value) - 1
    return source[offsets[start] : offsets[end] + 1]


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


def build_commentary_payload(material: Mapping[str, Any], gaps: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "story_id": STORY_ID,
        "primary_text": {
            "label": "世說新語正文",
            "text": str(material["entry"]["story_text"]),
        },
        "frozen_questions": [
            {
                "question_id": str(row.get("question_id") or ""),
                "gap": str(row.get("gap") or ""),
            }
            for row in gaps
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


def build_commentary_messages(material: Mapping[str, Any], gaps: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": COMMENTARY_SYSTEM_PROMPT},
        {"role": "user", "content": stable_json(build_commentary_payload(material, gaps))},
    ]


def allowed_commentary_refs(material: Mapping[str, Any]) -> set[str]:
    return {note["ref"] for note in material["early_notes"]} | {note["ref"] for note in material["later_notes"]}


def normalize_initial(raw: Mapping[str, Any], material: Mapping[str, Any]) -> dict[str, Any]:
    rows = raw.get("gaps", []) if isinstance(raw.get("gaps"), list) else []
    gaps: list[dict[str, Any]] = []
    for index, row in enumerate(rows[:MAX_GAPS], start=1):
        if not isinstance(row, Mapping):
            continue
        span = _align_whitespace(_text(row.get("story_span") or row.get("span")), str(material["entry"]["story_text"]))
        gaps.append(
            {
                "question_id": _text(row.get("question_id") or row.get("id") or f"Q{index}"),
                "story_span": span,
                "gap": _text(row.get("gap")),
            }
        )
    return {"gaps": gaps}


def normalize_semantic_delta(raw: Mapping[str, Any], material: Mapping[str, Any], initial: Mapping[str, Any]) -> dict[str, Any]:
    updates: list[dict[str, Any]] = []
    rows = raw.get("updates", []) if isinstance(raw.get("updates"), list) else []
    allowed = allowed_commentary_refs(material)
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        answered: list[dict[str, Any]] = []
        for aspect in row.get("answered_aspects", []) if isinstance(row.get("answered_aspects"), list) else []:
            if not isinstance(aspect, Mapping):
                continue
            evidence: list[dict[str, Any]] = []
            for item in aspect.get("evidence", []) if isinstance(aspect.get("evidence"), list) else []:
                if not isinstance(item, Mapping):
                    continue
                ref = _text(item.get("ref"))
                quote = _text(item.get("quote"))
                if ref in allowed:
                    quote = _align_whitespace(quote, source_text(ref, material))
                evidence.append({"ref": ref, "quote": quote})
            answered.append({"claim": _text(aspect.get("claim")), "evidence": evidence})
        conflicts: list[dict[str, Any]] = []
        for conflict in row.get("conflicts", []) if isinstance(row.get("conflicts"), list) else []:
            if not isinstance(conflict, Mapping):
                continue
            evidence = []
            for item in conflict.get("evidence", []) if isinstance(conflict.get("evidence"), list) else []:
                if not isinstance(item, Mapping):
                    continue
                ref = _text(item.get("ref"))
                quote = _text(item.get("quote"))
                if ref in allowed:
                    quote = _align_whitespace(quote, source_text(ref, material))
                evidence.append({"ref": ref, "quote": quote})
            conflicts.append({"description": _text(conflict.get("description")), "evidence": evidence})
        remaining = row.get("remaining_reading_gap")
        if remaining is not None:
            remaining = _text(remaining) or None
        refined = row.get("refined_question")
        if refined is not None:
            refined = _text(refined) or None
        updates.append(
            {
                "question_id": _text(row.get("question_id") or row.get("id")),
                "answered_aspects": answered,
                "unanswered_aspects": [_text(item) for item in row.get("unanswered_aspects", []) if _text(item)] if isinstance(row.get("unanswered_aspects"), list) else [],
                "conflicts": conflicts,
                "reading_sufficient": row.get("reading_sufficient"),
                "historical_verification_open": row.get("historical_verification_open"),
                "remaining_reading_gap": remaining,
                "refined_question": refined,
            }
        )

    relations: list[dict[str, Any]] = []
    for row in raw.get("relation_candidates", [])[:MAX_RELATIONS] if isinstance(raw.get("relation_candidates"), list) else []:
        if not isinstance(row, Mapping):
            continue
        evidence = []
        for item in row.get("evidence", []) if isinstance(row.get("evidence"), list) else []:
            if not isinstance(item, Mapping):
                continue
            ref = _text(item.get("ref"))
            quote = _align_whitespace(_text(item.get("quote")), source_text(ref, material)) if ref in allowed else _text(item.get("quote"))
            evidence.append({"ref": ref, "quote": quote})
        relations.append(
            {
                "persons": [_text(item) for item in row.get("persons", []) if _text(item)] if isinstance(row.get("persons"), list) else [],
                "observation": _text(row.get("observation")),
                "evidence": evidence,
            }
        )

    appraisals: list[dict[str, Any]] = []
    for row in raw.get("appraisal_candidates", [])[:MAX_APPRAISALS] if isinstance(raw.get("appraisal_candidates"), list) else []:
        if not isinstance(row, Mapping):
            continue
        ref = _text(row.get("evidence_ref") or row.get("ref"))
        quote = _text(row.get("evidence_quote") or row.get("quote"))
        if ref in allowed:
            quote = _align_whitespace(quote, source_text(ref, material))
        appraisals.append(
            {
                "evaluator": _text(row.get("evaluator")),
                "target": _text(row.get("target")),
                "appraisal_text": _text(row.get("appraisal_text") or row.get("observation")),
                "evidence_ref": ref,
                "evidence_quote": quote,
            }
        )
    return {"updates": updates, "relation_candidates": relations, "appraisal_candidates": appraisals}


def _validate_evidence(items: Any, material: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    allowed = allowed_commentary_refs(material)
    if not isinstance(items, list) or not items:
        return ["evidence is required"]
    for item in items:
        if not isinstance(item, Mapping):
            errors.append("evidence item is not an object")
            continue
        ref = _text(item.get("ref"))
        quote = _text(item.get("quote"))
        if ref not in allowed:
            errors.append("evidence ref is invalid")
        elif not quote or quote not in source_text(ref, material):
            errors.append("evidence quote is not an exact substring")
    return errors


def validate_initial(raw: Mapping[str, Any], normalized: Mapping[str, Any], material: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(raw) != {"gaps"}:
        errors.append("Completion 1 must contain only gaps")
    for key in _walk_keys(raw):
        if key in FORBIDDEN_KEYS:
            errors.append(f"forbidden Completion 1 field: {key}")
    if _contains_person_id(raw):
        errors.append("Completion 1 contains a Person ID")
    rows = raw.get("gaps")
    if not isinstance(rows, list):
        errors.append("gaps must be an array")
    elif len(rows) > MAX_GAPS:
        errors.append("more than three gaps")
    main_text = str(material["entry"]["story_text"])
    seen: set[str] = set()
    raw_rows = rows if isinstance(rows, list) else []
    for row in raw_rows:
        if isinstance(row, Mapping) and set(row) != {"question_id", "story_span", "gap"}:
            errors.append("Completion 1 gap has unexpected fields")
    for row in normalized.get("gaps", []) if isinstance(normalized.get("gaps"), list) else []:
        if not isinstance(row, Mapping) or any(not _text(row.get(key)) for key in ("question_id", "story_span", "gap")):
            errors.append("gap has an empty required field")
            continue
        if row["question_id"] in seen:
            errors.append("duplicate gap question_id")
        seen.add(row["question_id"])
        if row["story_span"] not in main_text:
            errors.append("gap story_span is not exact primary text")
        if len(row["gap"]) > 120 or row["gap"].count("。") + row["gap"].count("；") > 2:
            errors.append("gap is not concise")
        if any(pattern in row["gap"] for pattern in EXPLANATION_LEAK_PATTERNS):
            errors.append("gap contains explanation or attempted answer")
    return sorted(set(errors))


def validate_semantic_delta(raw: Mapping[str, Any], normalized: Mapping[str, Any], material: Mapping[str, Any], initial: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(raw) != {"updates", "relation_candidates", "appraisal_candidates"}:
        errors.append("Completion 2 has unexpected top-level fields")
    for key in _walk_keys(raw):
        if key in FORBIDDEN_KEYS:
            errors.append(f"forbidden Completion 2 field: {key}")
        if key in REPEATED_IMMUTABLE_KEYS:
            errors.append(f"Completion 2 repeats immutable field: {key}")
    if _contains_person_id(raw):
        errors.append("Completion 2 contains a Person ID")
    initial_rows = initial.get("gaps", []) if isinstance(initial.get("gaps"), list) else []
    initial_by_id = {str(row.get("question_id")): row for row in initial_rows if isinstance(row, Mapping)}
    updates = normalized.get("updates", [])
    if not isinstance(updates, list) or len(updates) != len(initial_by_id):
        errors.append("there must be one semantic delta for every frozen gap")
    seen: set[str] = set()
    for row in updates if isinstance(updates, list) else []:
        if not isinstance(row, Mapping):
            errors.append("semantic delta is not an object")
            continue
        qid = _text(row.get("question_id"))
        if qid in seen:
            errors.append("duplicate semantic delta question_id")
        seen.add(qid)
        if qid not in initial_by_id:
            errors.append("semantic delta question_id is unknown")
        if not isinstance(row.get("reading_sufficient"), bool):
            errors.append("reading_sufficient must be boolean")
        if not isinstance(row.get("historical_verification_open"), bool):
            errors.append("historical_verification_open must be boolean")
        answered = row.get("answered_aspects")
        if not isinstance(answered, list):
            errors.append("answered_aspects must be an array")
        else:
            if len(answered) > MAX_ANSWERED_ASPECTS:
                errors.append("too many answered aspects")
            for aspect in answered:
                if not isinstance(aspect, Mapping) or not _text(aspect.get("claim")):
                    errors.append("answered aspect has an empty claim")
                    continue
                errors.extend(_validate_evidence(aspect.get("evidence"), material))
        unanswered = row.get("unanswered_aspects")
        if not isinstance(unanswered, list):
            errors.append("unanswered_aspects must be an array")
        else:
            if any(not _text(item) for item in unanswered):
                errors.append("unanswered aspect is empty")
        conflicts = row.get("conflicts")
        if not isinstance(conflicts, list):
            errors.append("conflicts must be an array")
        else:
            for conflict in conflicts:
                if not isinstance(conflict, Mapping) or not _text(conflict.get("description")):
                    errors.append("conflict has an empty description")
                    continue
                errors.extend(_validate_evidence(conflict.get("evidence"), material))
        sufficient = row.get("reading_sufficient")
        remaining = row.get("remaining_reading_gap")
        refined = row.get("refined_question")
        if sufficient is True:
            if remaining is not None:
                errors.append("sufficient reading has a non-null remaining gap")
            if refined is not None:
                errors.append("sufficient reading has a refined question")
        else:
            if not _text(remaining):
                errors.append("insufficient reading has an empty remaining gap")
            if refined is not None and (not _text(refined) or (qid in initial_by_id and initial_by_id[qid]["story_span"] not in refined)):
                errors.append("refined question is not bound to the frozen Story span")

    relations = normalized.get("relation_candidates", [])
    if not isinstance(relations, list) or len(relations) > MAX_RELATIONS:
        errors.append("too many relation candidates")
    for row in relations if isinstance(relations, list) else []:
        if not isinstance(row, Mapping) or not isinstance(row.get("persons"), list) or len(row.get("persons", [])) != 2 or any(not _text(person) for person in row.get("persons", [])) or not _text(row.get("observation")):
            errors.append("invalid relation candidate")
            continue
        if any(term in row["observation"] for term in DYNAMIC_RELATION_TERMS):
            errors.append("relation candidate uses unsupported association inference")
        errors.extend(_validate_evidence(row.get("evidence"), material))
    appraisals = normalized.get("appraisal_candidates", [])
    if not isinstance(appraisals, list) or len(appraisals) > MAX_APPRAISALS:
        errors.append("too many appraisal candidates")
    for row in appraisals if isinstance(appraisals, list) else []:
        if not isinstance(row, Mapping) or any(not _text(row.get(key)) for key in ("evaluator", "target", "appraisal_text", "evidence_ref", "evidence_quote")):
            errors.append("invalid appraisal candidate")
            continue
        errors.extend(_validate_evidence([{"ref": row["evidence_ref"], "quote": row["evidence_quote"]}], material))
    return sorted(set(errors))


def working_answer(answered_aspects: Sequence[Mapping[str, Any]]) -> str:
    claims = [_text(row.get("claim")) for row in answered_aspects if isinstance(row, Mapping) and _text(row.get("claim"))]
    claims = claims[:2]
    return "".join(claim if claim.endswith(("。", "！", "？", ".", "!", "?")) else claim + "。" for claim in claims)


def derive_state(initial: Mapping[str, Any], delta: Mapping[str, Any]) -> dict[str, Any]:
    by_id = {str(row.get("question_id")): row for row in initial.get("gaps", []) if isinstance(row, Mapping)}
    questions: list[dict[str, Any]] = []
    for update in delta.get("updates", []) if isinstance(delta.get("updates"), list) else []:
        qid = str(update.get("question_id"))
        frozen = by_id[qid]
        conflicts = update.get("conflicts", [])
        answered = update.get("answered_aspects", [])
        if conflicts:
            state = "conflicted"
        elif update.get("reading_sufficient") is True:
            state = "substantially_explained"
        elif answered:
            state = "partially_explained"
        else:
            state = "unexplained"
        remaining = update.get("remaining_reading_gap")
        refined = update.get("refined_question")
        next_action = "stop" if update.get("reading_sufficient") is True else "refine_question" if refined is not None else "external_search"
        refs: set[str] = set()
        for aspect in answered:
            if not isinstance(aspect, Mapping):
                continue
            evidence = aspect.get("evidence")
            if not isinstance(evidence, list):
                continue
            for item in evidence:
                if isinstance(item, Mapping) and _text(item.get("ref")):
                    refs.add(str(item["ref"]))
        for conflict in conflicts:
            if not isinstance(conflict, Mapping):
                continue
            evidence = conflict.get("evidence")
            if not isinstance(evidence, list):
                continue
            for item in evidence:
                if isinstance(item, Mapping) and _text(item.get("ref")):
                    refs.add(str(item["ref"]))
        questions.append(
            {
                "question_id": qid,
                "story_span": frozen["story_span"],
                "gap": frozen["gap"],
                "question": frozen["gap"],
                "state": state,
                "working_answer": working_answer(answered),
                "supporting_refs": sorted(set(refs)),
                "reading_sufficient": update.get("reading_sufficient"),
                "historical_verification_open": update.get("historical_verification_open"),
                "remaining_gap": remaining,
                "next_action": next_action,
                "refined_question": refined,
            }
        )
    return {
        "schema": "srm0-3b-research-state",
        "schema_version": SCHEMA_VERSION,
        "story_id": STORY_ID,
        "stage": "commentary_resolution_complete",
        "questions": questions,
        "relation_candidates": [
            {
                "persons": row.get("persons"),
                "observation": row.get("observation"),
                "supporting_refs": sorted(
                    str(item["ref"])
                    for item in row.get("evidence", [])
                    if isinstance(item, Mapping) and _text(item.get("ref"))
                ),
            }
            for row in delta.get("relation_candidates", []) if isinstance(row, Mapping)
        ],
        "appraisal_candidates": [
            {"evaluator": row.get("evaluator"), "target": row.get("target"), "appraisal_text": row.get("appraisal_text"), "evidence_ref": row.get("evidence_ref")}
            for row in delta.get("appraisal_candidates", []) if isinstance(row, Mapping)
        ],
        "canonical_write_back": False,
        "external_search_performed": False,
    }


def derive_events(initial: Mapping[str, Any], delta: Mapping[str, Any], state: Mapping[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [
        {"event": "question_created", "question_id": row.get("question_id"), "story_span": row.get("story_span"), "gap": row.get("gap")}
        for row in initial.get("gaps", []) if isinstance(row, Mapping)
    ]
    for row in state.get("questions", []) if isinstance(state.get("questions"), list) else []:
        refs = row.get("supporting_refs", [])
        events.append({"event": "commentary_read", "question_id": row.get("question_id"), "evidence_refs": refs})
        if refs:
            events.append({"event": "answer_supported", "question_id": row.get("question_id"), "evidence_refs": refs})
        if row.get("state") == "conflicted":
            events.append({"event": "conflict_detected", "question_id": row.get("question_id")})
        if row.get("reading_sufficient") is True:
            events.append({"event": "reading_sufficient", "question_id": row.get("question_id")})
        else:
            events.append({"event": "reading_gap_remaining", "question_id": row.get("question_id")})
        if row.get("refined_question"):
            events.append({"event": "refined_question_proposed", "question_id": row.get("question_id"), "refined_question": row.get("refined_question")})
        if row.get("next_action") == "stop":
            events.append({"event": "research_stop_recommended", "question_id": row.get("question_id")})
    for index, row in enumerate(state.get("relation_candidates", []) if isinstance(state.get("relation_candidates"), list) else []):
        events.append({"event": "relation_candidate_added", "index": index, "persons": row.get("persons")})
    for index, row in enumerate(state.get("appraisal_candidates", []) if isinstance(state.get("appraisal_candidates"), list) else []):
        events.append({"event": "appraisal_candidate_added", "index": index, "target": row.get("target")})
    return events


def review_template() -> dict[str, Any]:
    return {
        "schema": "srm0-3b-commentary-resolution-review",
        "schema_version": SCHEMA_VERSION,
        "story_id": STORY_ID,
        "initial_question_quality": None,
        "commentary_consumption": None,
        "semantic_delta_precision": None,
        "sufficiency_judgment": None,
        "working_answer_projection": None,
        "stop_restraint": None,
        "relation_precision": None,
        "appraisal_precision": None,
        "token_efficiency": None,
        "notes": "",
    }


__all__ = [
    "COMMENTARY_SYSTEM_PROMPT",
    "INITIAL_SYSTEM_PROMPT",
    "MODEL",
    "OUTPUT_ROOT",
    "PROMPT_VERSION",
    "PROVIDER",
    "REVIEW_PATH",
    "ROOT",
    "STORY_ID",
    "build_commentary_messages",
    "build_commentary_payload",
    "build_initial_messages",
    "build_initial_payload",
    "derive_events",
    "derive_state",
    "normalize_initial",
    "normalize_semantic_delta",
    "review_template",
    "resolve_commentary_material",
    "stable_json",
    "validate_initial",
    "validate_semantic_delta",
    "working_answer",
]
