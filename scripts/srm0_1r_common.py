#!/usr/bin/env python3
"""Contracts for the SRM0.1R evidence-consumption retest.

This module freezes the successful SRM0.1 inputs and translates one compact
semantic model result into an isolated generated memory state.  It never
changes canonical, Gold, PersonStory, or the original SRM0.1 artifacts.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from .ds1_common import ROOT, read_json, sha256_file, stable_json, write_json
    from .srm0_1_common import (
        STORY_ID,
        build_initial_packet,
        input_hash,
        parse_json_content,
    )
except ImportError:  # pragma: no cover - direct script execution
    from ds1_common import ROOT, read_json, sha256_file, stable_json, write_json
    from srm0_1_common import STORY_ID, build_initial_packet, input_hash, parse_json_content


PROMPT_VERSION = "srm0.1r-v1"
MODEL = "deepseek-v4-flash"
PROVIDER = "deepseek"
SCHEMA_VERSION = 1

ORIGINAL_ROOT = Path("data/generated/srm0") / STORY_ID
RETEST_ROOT = ORIGINAL_ROOT / "retest"
REVIEW_PATH = Path("data/annotation/srm0-1r-review.json")

FROZEN_QUESTION = "陶公為何在庾亮引咎責躬後不覺釋然，其轉變的關鍵是什麼？"
FROZEN_READING_TARGET = "陶不覺釋然"

USEFUL_ROLES = {"direct_support", "context", "contradiction", "later_only"}
ROLE_ALIASES = {
    "supports": "direct_support",
    "support": "direct_support",
    "background": "context",
    "contextual": "context",
    "analogy": "context",
    "contradicts": "contradiction",
    "later": "later_only",
}
QUESTION_STATUSES = {"resolved", "partially_resolved", "unresolved", "not_worth_pursuing"}
SUBQUESTION_SOURCES = {"necessary_gap", "evidence_conflict", "next_textual_puzzle"}
IMPORTANCE = {"high", "medium", "low"}
APPRAISAL_TYPES = {"contemporary_appraisal", "historian_appraisal", "later_scholar_appraisal"}
STATIC_RELATION_TYPES = {
    "kinship",
    "marriage",
    "office_relation",
    "recommendation_appointment",
    "political_collaboration",
    "common_event_participation",
    "explicit_conflict_accusation",
}
DYNAMIC_RELATION_WORDS = {
    "trust",
    "dominance",
    "fear",
    "deference",
    "intimacy",
    "hostility",
    "信任",
    "支配",
    "恐惧",
    "畏惧",
    "亲密",
    "敌意",
}

SYSTEM_PROMPT = """你是受控的《世说新语》证据消费器。只回答当前 Q1，不执行检索，不使用预训练历史知识，只使用用户提供的原文和冻结的八个候选证据。先判断证据能否回答 Q1，再决定是否有直接的原文重读联系。证据可以支持、补充、矛盾或无法回答；不能把有趣的关联写成因果证据。特别注意时间方向：后文或后来的材料不能自动解释此前的释然。不要把动态心理状态抽取为静态关系。不要强行生成下一问题；只有必要缺口、证据冲突或 Q1 已解决后仍有高影响原文谜题才可提出 candidate_subquestion。短输出，JSON בלבד。

严格只返回以下顶层字段：useful_evidence、question_resolution、reading_links、static_relation_candidates、appraisal_candidates、candidate_subquestion、deprioritized_associations、stop_recommendation。
useful_evidence 最多四项，每项有 ref、finding、role；ref 必须来自八个候选，finding 不得为空。
question_resolution 必须有 question_id=Q1、status、current_answer、remaining_gap、evidence_refs。status 只能是 resolved、partially_resolved、unresolved、not_worth_pursuing；除 unresolved 外 current_answer 不得为空。只在必要时给 candidate_subquestion，且 source 只能是 necessary_gap、evidence_conflict、next_textual_puzzle。
reading_links 最多两项；text_span 必须逐字取自原文，每项必须引用候选 ref。static_relation_candidates 和 appraisal_candidates 是可选候选，不是事实，不得写入 canonical。stop_recommendation 必须有 stop 和非空 reason。不要输出数据库操作、claim add、question supersede 或隐藏推理。"""


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def load_frozen_inputs(root: Path = ROOT) -> dict[str, Any]:
    """Load and verify the exact successful SRM0.1 Q1 and eight candidates."""

    original_output = read_json(root, ORIGINAL_ROOT / "round-00-output.json")
    original_trace = read_json(root, ORIGINAL_ROOT / "round-01-search-trace.json")
    packet, _ = build_initial_packet(root, STORY_ID)
    question = original_output.get("output", {})
    if question.get("active_question", {}).get("question") != FROZEN_QUESTION:
        raise ValueError("SRM0.1 frozen Q1 does not match the required question")
    if question.get("active_question", {}).get("reading_target") != FROZEN_READING_TARGET:
        raise ValueError("SRM0.1 frozen reading target does not match")
    candidates = original_trace.get("search_trace", {}).get("model_candidates", [])
    if not isinstance(candidates, list) or len(candidates) != 8:
        raise ValueError("SRM0.1 successful run must provide exactly eight model-facing candidates")
    required_keys = {"ref", "work", "source_layer", "snippet"}
    frozen_candidates: list[dict[str, str]] = []
    for row in candidates:
        if not isinstance(row, Mapping) or set(row) != required_keys:
            raise ValueError("frozen candidate shape changed")
        frozen_candidates.append({key: str(row[key]) for key in ("ref", "work", "source_layer", "snippet")})
    candidate_hash = _stable_hash(frozen_candidates)
    return {
        "story_id": STORY_ID,
        "story_text": str(packet["story_text"]),
        "question_id": "Q1",
        "question": FROZEN_QUESTION,
        "reading_target": FROZEN_READING_TARGET,
        "candidates": frozen_candidates,
        "candidate_hash": candidate_hash,
        "source_artifacts": {
            (ORIGINAL_ROOT / "round-00-output.json").as_posix(): sha256_file(root, ORIGINAL_ROOT / "round-00-output.json"),
            (ORIGINAL_ROOT / "round-01-search-trace.json").as_posix(): sha256_file(root, ORIGINAL_ROOT / "round-01-search-trace.json"),
        },
    }


def build_model_payload(frozen: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "story_id": frozen["story_id"],
        "story_text": frozen["story_text"],
        "question": {
            "question_id": frozen["question_id"],
            "question": frozen["question"],
            "reading_target": frozen["reading_target"],
        },
        "evidence": [dict(row) for row in frozen["candidates"]],
    }


def build_messages(frozen: Mapping[str, Any]) -> list[dict[str, str]]:
    payload = build_model_payload(frozen)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": stable_json(payload)},
    ]


def character_metrics(frozen: Mapping[str, Any], messages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    source_material_chars = len(str(frozen["story_text"])) + len(str(frozen["question"])) + len(str(frozen["reading_target"])) + sum(len(str(row["snippet"])) for row in frozen["candidates"])
    payload = build_model_payload(frozen)
    projected_payload_chars = len(stable_json(payload))
    instruction_chars = len(SYSTEM_PROMPT)
    serialized_prompt_chars = sum(len(str(message.get("content", ""))) for message in messages)
    return {
        "source_material_chars": source_material_chars,
        "projected_payload_chars": projected_payload_chars,
        "instruction_chars": instruction_chars,
        "serialized_prompt_chars": serialized_prompt_chars,
        "compression_ratio": round(projected_payload_chars / source_material_chars, 6) if source_material_chars else 0,
    }


def _refs(value: Any, allowed: set[str]) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({str(ref) for ref in value if str(ref) in allowed})


def normalize_semantic_result(
    raw: Mapping[str, Any],
    story_text: str,
    candidate_refs: Iterable[str],
    candidate_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Normalize only the semantic result; Python handles bookkeeping later."""

    allowed = set(candidate_refs)
    candidate_text_by_ref = {
        str(row.get("ref")): str(row.get("snippet") or "")
        for row in (candidate_rows or [])
        if isinstance(row, Mapping) and row.get("ref") in allowed
    }
    useful: list[dict[str, Any]] = []
    for row in raw.get("useful_evidence", []) if isinstance(raw.get("useful_evidence", []), list) else []:
        if not isinstance(row, Mapping) or len(useful) >= 4:
            continue
        ref = str(row.get("ref") or "")
        finding = str(row.get("finding") or "").strip()
        role = row.get("role")
        role = ROLE_ALIASES.get(role, role)
        if ref not in allowed or not finding or role not in USEFUL_ROLES:
            continue
        useful.append({"ref": ref, "finding": finding, "role": role})

    resolution = raw.get("question_resolution") if isinstance(raw.get("question_resolution"), Mapping) else {}
    status = resolution.get("status") if resolution.get("status") in QUESTION_STATUSES else "unresolved"
    current_answer = str(resolution.get("current_answer") or "").strip()
    remaining_gap = str(resolution.get("remaining_gap") or "").strip()
    normalized_resolution = {
        "question_id": "Q1",
        "status": status,
        "current_answer": current_answer,
        "remaining_gap": remaining_gap,
        "evidence_refs": _refs(resolution.get("evidence_refs"), allowed),
    }

    reading_links: list[dict[str, Any]] = []
    raw_links = raw.get("reading_links", []) if isinstance(raw.get("reading_links", []), list) else []
    for row in raw_links:
        if not isinstance(row, Mapping) or len(reading_links) >= 2:
            continue
        span = str(row.get("text_span") or "")
        refs = _refs(row.get("refs") or ([row.get("ref")] if row.get("ref") else []), allowed)
        context = str(row.get("context") or row.get("link_type") or "").strip()
        effect = str(row.get("reading_effect") or row.get("link_type") or "").strip()
        if not span or span not in story_text or not context or not effect or not refs:
            continue
        reading_links.append({
            "context": context,
            "text_span": span,
            "reading_effect": effect,
            "refs": refs,
        })

    relations: list[dict[str, Any]] = []
    raw_relations = raw.get("static_relation_candidates", []) if isinstance(raw.get("static_relation_candidates", []), list) else []
    for row in raw_relations:
        if not isinstance(row, Mapping) or len(relations) >= 3:
            continue
        persons = [str(person) for person in row.get("persons", []) if isinstance(person, str)] if isinstance(row.get("persons"), list) else []
        relation_type = row.get("relation_type")
        refs = _refs(row.get("evidence_refs"), allowed)
        description = str(row.get("description") or "").strip()
        if len(persons) != 2 or relation_type not in STATIC_RELATION_TYPES or any(word in str(relation_type).lower() or word in description.lower() for word in DYNAMIC_RELATION_WORDS) or not description or not refs:
            continue
        relations.append({"persons": persons, "relation_type": relation_type, "description": description, "evidence_refs": refs, "status": "candidate"})

    appraisals: list[dict[str, Any]] = []
    raw_appraisals = raw.get("appraisal_candidates", []) if isinstance(raw.get("appraisal_candidates", []), list) else []
    for row in raw_appraisals:
        if not isinstance(row, Mapping) or len(appraisals) >= 3:
            continue
        refs = _refs(row.get("evidence_refs"), allowed)
        appraisal_type = row.get("appraisal_type")
        evaluator = str(row.get("evaluator") or "").strip()
        target = str(row.get("target") or "").strip()
        text = str(row.get("appraisal_text") or "").strip()
        if not evaluator or not target or not text or appraisal_type not in APPRAISAL_TYPES or not refs:
            continue
        appraisals.append({"evaluator": evaluator, "target": target, "appraisal_text": text, "appraisal_type": appraisal_type, "evidence_refs": refs, "status": "candidate"})

    subquestion_value = raw.get("candidate_subquestion")
    subquestion: dict[str, Any] | None = None
    if isinstance(subquestion_value, Mapping):
        source = subquestion_value.get("source")
        question = str(subquestion_value.get("question") or "").strip()
        derived_from = [str(value) for value in subquestion_value.get("derived_from", []) if isinstance(value, str)] if isinstance(subquestion_value.get("derived_from"), list) else []
        why_needed = str(subquestion_value.get("why_needed") or "").strip()
        reading_target = str(subquestion_value.get("reading_target") or "").strip()
        importance = subquestion_value.get("importance")
        if source in SUBQUESTION_SOURCES and question and derived_from and why_needed and reading_target and reading_target in story_text and importance in IMPORTANCE:
            subquestion = {"question": question, "source": source, "derived_from": derived_from, "why_needed": why_needed, "reading_target": reading_target, "importance": importance}

    deprioritized: list[dict[str, Any]] = []
    raw_deprioritized = raw.get("deprioritized_associations", []) if isinstance(raw.get("deprioritized_associations", []), list) else []
    for row in raw_deprioritized:
        if not isinstance(row, Mapping) or len(deprioritized) >= 3:
            if isinstance(row, str) and len(deprioritized) < 3:
                idea = row.strip()
                keywords = ("噉薤", "留白", "為政之實", "竹頭木屑")
                refs = sorted(
                    ref for ref in allowed
                    if any(keyword in candidate_text_by_ref.get(ref, "") for keyword in keywords)
                )
                if refs:
                    deprioritized.append({"idea": idea, "reason": "该关联存在时间方向风险，不能自动作为当前释然的直接原因。", "trigger_refs": refs[:3]})
            continue
        idea = str(row.get("idea") or "").strip()
        reason = str(row.get("reason") or "").strip()
        refs = _refs(row.get("trigger_refs") or row.get("refs"), allowed)
        if idea and reason and refs:
            deprioritized.append({"idea": idea, "reason": reason, "trigger_refs": refs})

    stop = raw.get("stop_recommendation") if isinstance(raw.get("stop_recommendation"), Mapping) else {}
    stop_recommendation = {"stop": bool(stop.get("stop")), "reason": str(stop.get("reason") or "").strip()}

    return {
        "useful_evidence": useful,
        "question_resolution": normalized_resolution,
        "reading_links": reading_links,
        "static_relation_candidates": relations,
        "appraisal_candidates": appraisals,
        "candidate_subquestion": subquestion,
        "deprioritized_associations": deprioritized,
        "stop_recommendation": stop_recommendation,
    }


def validate_semantic_result(value: Mapping[str, Any], story_text: str, candidate_refs: Iterable[str]) -> list[str]:
    errors: list[str] = []
    allowed = set(candidate_refs)
    required = {"useful_evidence", "question_resolution", "reading_links", "static_relation_candidates", "appraisal_candidates", "candidate_subquestion", "deprioritized_associations", "stop_recommendation"}
    if set(value) != required:
        errors.append("semantic result top-level fields do not match SRM0.1R contract")
    useful = value.get("useful_evidence", [])
    if not isinstance(useful, list) or len(useful) > 4:
        errors.append("useful_evidence must contain at most four items")
    for row in useful if isinstance(useful, list) else []:
        if not isinstance(row, Mapping) or not row.get("ref") or not row.get("finding") or row.get("ref") not in allowed or row.get("role") not in USEFUL_ROLES:
            errors.append("invalid useful_evidence item")

    resolution = value.get("question_resolution")
    if not isinstance(resolution, Mapping):
        errors.append("question_resolution is required")
    else:
        if resolution.get("question_id") != "Q1" or resolution.get("status") not in QUESTION_STATUSES:
            errors.append("invalid Q1 question_resolution")
        status = resolution.get("status")
        if status != "unresolved" and not str(resolution.get("current_answer") or "").strip():
            errors.append("current_answer is required unless Q1 is unresolved")
        if status not in {"resolved", "not_worth_pursuing"} and not str(resolution.get("remaining_gap") or "").strip():
            errors.append("remaining_gap is required for unresolved or partial Q1")
        if not set(resolution.get("evidence_refs", [])).issubset(allowed):
            errors.append("question_resolution has an unknown evidence ref")
        if status in {"resolved", "partially_resolved"} and not resolution.get("evidence_refs"):
            errors.append("resolved or partially resolved Q1 needs evidence refs")

    links = value.get("reading_links", [])
    if not isinstance(links, list) or len(links) > 2:
        errors.append("reading_links must contain at most two items")
    for row in links if isinstance(links, list) else []:
        if not isinstance(row, Mapping) or not row.get("context") or not row.get("reading_effect") or row.get("text_span") not in story_text or not row.get("refs") or not set(row.get("refs", [])).issubset(allowed):
            errors.append("reading link lacks exact text or evidence refs")

    relations = value.get("static_relation_candidates", [])
    if not isinstance(relations, list) or len(relations) > 3:
        errors.append("static_relation_candidates must contain at most three items")
    for row in relations if isinstance(relations, list) else []:
        if not isinstance(row, Mapping) or row.get("status") != "candidate" or len(row.get("persons", [])) != 2 or row.get("relation_type") not in STATIC_RELATION_TYPES or not row.get("description") or not row.get("evidence_refs") or not set(row.get("evidence_refs", [])).issubset(allowed):
            errors.append("invalid static relation candidate")
        if isinstance(row, Mapping) and any(word in str(row.get("relation_type", "")).lower() or word in str(row.get("description", "")).lower() for word in DYNAMIC_RELATION_WORDS):
            errors.append("dynamic relation candidate is forbidden")

    appraisals = value.get("appraisal_candidates", [])
    if not isinstance(appraisals, list) or len(appraisals) > 3:
        errors.append("appraisal_candidates must contain at most three items")
    for row in appraisals if isinstance(appraisals, list) else []:
        if not isinstance(row, Mapping) or not row.get("evaluator") or not row.get("target") or not row.get("appraisal_text") or row.get("appraisal_type") not in APPRAISAL_TYPES or not row.get("evidence_refs") or not set(row.get("evidence_refs", [])).issubset(allowed):
            errors.append("invalid appraisal candidate")

    subquestion = value.get("candidate_subquestion")
    if subquestion is not None:
        if not isinstance(subquestion, Mapping) or subquestion.get("source") not in SUBQUESTION_SOURCES or not subquestion.get("question") or not subquestion.get("derived_from") or not subquestion.get("why_needed") or not subquestion.get("reading_target") or subquestion.get("reading_target") not in story_text or subquestion.get("importance") not in IMPORTANCE:
            errors.append("invalid candidate_subquestion")

    deprioritized = value.get("deprioritized_associations", [])
    if not isinstance(deprioritized, list) or len(deprioritized) > 3:
        errors.append("deprioritized_associations must contain at most three items")
    for row in deprioritized if isinstance(deprioritized, list) else []:
        if not isinstance(row, Mapping) or not row.get("idea") or not row.get("reason") or not row.get("trigger_refs") or not set(row.get("trigger_refs", [])).issubset(allowed):
            errors.append("invalid deprioritized association")

    stop = value.get("stop_recommendation")
    if not isinstance(stop, Mapping) or not isinstance(stop.get("stop"), bool) or not stop.get("reason"):
        errors.append("stop_recommendation requires stop and a reason")
    return errors


def build_state_events(frozen: Mapping[str, Any], result: Mapping[str, Any], *, run_id: str, execution_kind: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    candidate_refs = [str(row["ref"]) for row in frozen["candidates"]]
    selected_refs = {str(row["ref"]) for row in result["useful_evidence"]}
    unselected_refs = [ref for ref in candidate_refs if ref not in selected_refs]
    resolution = dict(result["question_resolution"])
    events_raw: list[dict[str, Any]] = [{"event_type": "question_resolution", "question_id": "Q1", "status": resolution["status"], "reason": resolution.get("remaining_gap", "") or resolution.get("current_answer", "") }]
    for row in result["useful_evidence"]:
        events_raw.append({"event_type": "evidence_kept", "evidence_ref": row["ref"], "role": row["role"], "reason": row["finding"]})
    for ref in unselected_refs:
        events_raw.append({"event_type": "seen_not_selected", "evidence_ref": ref, "reason": "冻结候选未被本轮语义结果选为 useful_evidence"})
    for row in result["reading_links"]:
        events_raw.append({"event_type": "reading_link_added", "text_span": row["text_span"], "evidence_refs": row["refs"], "reason": row["reading_effect"]})
    for row in result["static_relation_candidates"]:
        events_raw.append({"event_type": "static_relation_candidate_added", "persons": row["persons"], "relation_type": row["relation_type"], "evidence_refs": row["evidence_refs"], "reason": row["description"]})
    for row in result["appraisal_candidates"]:
        events_raw.append({"event_type": "appraisal_candidate_added", "target": row["target"], "appraisal_type": row["appraisal_type"], "evidence_refs": row["evidence_refs"], "reason": row["appraisal_text"]})
    if result["candidate_subquestion"] is not None:
        row = result["candidate_subquestion"]
        events_raw.append({"event_type": "question_candidate_added", "source": row["source"], "derived_from": row["derived_from"], "reason": row["why_needed"], "reading_target": row["reading_target"]})
    for row in result["deprioritized_associations"]:
        events_raw.append({"event_type": "association_deprioritized", "idea": row["idea"], "trigger_refs": row["trigger_refs"], "reason": row["reason"]})

    events: list[dict[str, Any]] = []
    for sequence, event in enumerate(events_raw, start=1):
        payload = {"story_id": STORY_ID, "iteration": 1, "sequence": sequence, **event}
        payload["event_id"] = "srm0-1r-event-" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()[:16]
        events.append(payload)

    state = {
        "schema": "srm0-1r-research-memory",
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "generated_research_memory_retest",
        "candidate_status": "candidate",
        "story_id": STORY_ID,
        "iteration": 1,
        "run_id": run_id,
        "execution_kind": execution_kind,
        "retest_of": ORIGINAL_ROOT.as_posix(),
        "question_id": "Q1",
        "question": FROZEN_QUESTION,
        "reading_target": FROZEN_READING_TARGET,
        "useful_evidence": [dict(row) for row in result["useful_evidence"]],
        "question_resolution": resolution,
        "reading_links": [dict(row) for row in result["reading_links"]],
        "static_relation_candidates": [dict(row) for row in result["static_relation_candidates"]],
        "appraisal_candidates": [dict(row) for row in result["appraisal_candidates"]],
        "candidate_subquestion": result["candidate_subquestion"],
        "deprioritized_associations": [dict(row) for row in result["deprioritized_associations"]],
        "stop_recommendation": dict(result["stop_recommendation"]),
        "seen_evidence_refs": candidate_refs,
        "seen_not_selected_refs": unselected_refs,
        "research_status": "retest_complete_next_question_not_executed",
        "canonical_write_back": False,
    }
    return state, events


def review_template() -> dict[str, Any]:
    return {
        "schema": "srm0-1r-review",
        "schema_version": 1,
        "stage": "SRM0.1R",
        "records": [
            {
                "story_id": STORY_ID,
                "evidence_consumption": None,
                "question_resolution": None,
                "reading_link_quality": None,
                "next_question_restraint": None,
                "temporal_reasoning": None,
                "static_relation_extraction": None,
                "appraisal_extraction": None,
                "token_efficiency": None,
                "notes": "",
            }
        ],
        "canonical_write_back": False,
    }
