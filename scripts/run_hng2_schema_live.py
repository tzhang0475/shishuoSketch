#!/usr/bin/env python3
"""HNG2-SL targeted semantic-assist validation.

This runner is deliberately narrower than HNG2-L.  It consumes only the
open ResearchGap cases in the frozen HNG2-S projection, runs at most two
semantic rounds and one local retrieval round per case, and never expands a
frontier or writes a canonical record.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_hng0_2 as hng02  # noqa: E402
import build_hng2_schema_replay as schema_replay  # noqa: E402
import historical_entity_schema as schema  # noqa: E402
import historical_entity_resolver as resolver  # noqa: E402
from hng1_common import find_punctuated_first, load_retrieval_sources, open_short_hits  # noqa: E402
from hng0_1_common import quote_matches, stable_hash  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402


BASE = ROOT / "data/generated/hng2-schema"
OUT = ROOT / "data/generated/hng2-schema-live"
RAW = OUT / "raw-api"
MODEL = "deepseek-v4-flash"
PROVIDER = "deepseek"
RUN_SCHEMA = 1
SELECTION_VERSION = "hng2-sl-selection-v2"
PROMPT_VERSION = "hng2-sl-semantic-assist-v1"
SEARCH_PROMPT_VERSION = "hng2-sl-search-plan-v1"

APPROVED_SOURCES = {
    "世說新語", "劉孝標注", "余嘉錫笺疏", "晉書", "三國志", "資治通鑑",
    "資治通鑑考異", "local historical corpus", "local source corpus",
}
MODEL_TOP_FIELDS = {"semantic_assessment", "identity_recommendation", "research_gap"}
SEMANTIC_FIELDS = {"assessment_status", "semantic_fit", "observed_role", "evidence_spans", "summary"}
RECOMMENDATION_FIELDS = {
    "decision", "chosen_candidate_key", "confidence", "reason_codes", "evidence_spans",
    "new_entity_candidate", "new_entity_key", "unresolved_reason", "summary",
}
GAP_FIELDS = {
    "status", "missing_constraints", "blocking_question", "next_best_action",
    "candidate_keys", "stop_condition",
}
FORBIDDEN_MODEL_FIELDS = {
    "person_id", "provisional_person_id", "identity_status", "graph_action",
    "constraint_checks", "state", "next_action", "frontier_status", "wave",
}

SEMANTIC_SYSTEM = """你是受约束的历史实体 schema 语义辅助器。
只使用输入中的正文、注释、候选人物和 Python 提供的硬约束，不使用外部知识。
不得创造 person_id、provisional_person_id 或候选键；chosen_candidate_key 只能使用给定候选键，无法判断则为 null。
不得修改、复述或替换 hard_constraints。只能返回下列 JSON 字段，不能返回 IdentityDecision 或 GraphAction：
{"semantic_assessment":{"assessment_status":"assessed|insufficient_context|not_applicable|invalid","semantic_fit":"strong_support|support|compatible|weak|unknown|conflict","observed_role":"event_participant|speaker|referenced_person|kinship_node|cited_author|text_author|commentator|office_holder|unknown","evidence_spans":[{"ref":"给定 ref","span":"原文连续短引文"}],"summary":"简短外部可审计摘要"},"identity_recommendation":{"decision":"choose_candidate|new_person_candidate|ambiguous|unresolved|not_a_single_person|not_a_person","chosen_candidate_key":"给定 c 键或 null","confidence":"high|medium|low|unknown","reason_codes":["简短代码"],"evidence_spans":[{"ref":"给定 ref","span":"原文连续短引文"}],"new_entity_candidate":null,"new_entity_key":"n0 或 null","unresolved_reason":"简短原因","summary":"简短摘要"},"research_gap":{"status":"closed|open","missing_constraints":[],"blocking_question":"","next_best_action":"search_kinship_context|search_title_identity|search_temporal_evidence|search_biography_context|human_review|none","candidate_keys":[],"stop_condition":""}}
证据 span 必须逐字来自对应 ref 的 supplied_text。metatextual 引书作者不能自动成为叙事事件参与者或说话者，也不能继承所述事件的个人活动时间。"""

SEARCH_SYSTEM = """你是历史实体检索计划器。只根据给定的 open ResearchGap、原文和候选生成一个本轮 SearchPlan，不回答历史问题，不扩展人物 frontier，不使用外部知识。
必须考虑以下五个规划问题：当前缺少哪一种证据最可能改变身份判断；这种证据最可能出现在哪类史料；应围绕哪些人物、亲属词、官职、事件或年代检索；哪些候选需分别验证或排除；什么证据即可结束本轮检索。
严格返回：{"search_plan":{"target_constraint":"","goal":"","candidate_keys":[],"preferred_sources":[],"search_entities":[],"search_patterns":[],"temporal_scope":{},"graph_neighborhood_scope":"case_only|none","stop_condition":""}}。preferred_sources 只能使用给定的本地来源。"""


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def json_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def compact(value: Any) -> str:
    return " ".join(str(value or "").split())


def _redact(value: Any) -> str:
    text = str(value or "")
    secret = os.environ.get("DEEPSEEK_API_KEY")
    return text.replace(secret, "[REDACTED]") if secret else text


def _stable_key(case_id: str) -> str:
    return stable_hash({"selection": SELECTION_VERSION, "case_id": case_id})


def load_base() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    cases_doc = read_json(BASE / "cases.json", {}) or {}
    gaps_doc = read_json(BASE / "research-gaps.json", {}) or {}
    cases = {str(row.get("case_id")): dict(row) for row in cases_doc.get("cases", []) if isinstance(row, Mapping) and row.get("case_id")}
    gaps = {str(row.get("case_id")): dict(row) for row in gaps_doc.get("gaps", []) if isinstance(row, Mapping) and row.get("case_id")}
    evidence: dict[str, dict[str, Any]] = {}
    for path in (ROOT / "data/generated/hng1r2/relations.json", ROOT / "data/generated/hng1r2/temporal-items.json"):
        document = read_json(path, {}) or {}
        for ref, row in (document.get("evidence") or {}).items():
            if isinstance(row, Mapping):
                evidence[str(ref)] = dict(row)
    return cases, gaps, evidence


def _category(case: Mapping[str, Any], gap: Mapping[str, Any]) -> str:
    interpretation = case.get("interpretation") if isinstance(case.get("interpretation"), Mapping) else {}
    surface = str((case.get("observation") or {}).get("surface") or "")
    kind = str(interpretation.get("entity_kind") or "")
    if interpretation.get("mention_scope") == "metatextual":
        return "metatextual"
    if kind in {"person_title", "person_office_title"}:
        return "title_office"
    if kind in {"structural_kinship_expression", "kinship_reference"}:
        return "kinship_structural"
    if kind in {"abbreviated_name", "courtesy_name"} or len(resolver.matching_normalize(surface)) <= 2:
        return "abbreviated_short"
    status = str((case.get("decision") or {}).get("identity_status") or "")
    if status in {"unresolved", "resolved_new_candidate"} or not case.get("candidates"):
        return "unresolved_new"
    if any(str(item.get("constraint_type")) == "temporal" and str(item.get("constraint_scope")) == "candidate" and str(item.get("status")) in {"unknown", "conflict"} for item in case.get("constraint_checks", [])):
        return "temporal_constraint"
    return "other"


def _context_for_case(case: Mapping[str, Any], evidence: Mapping[str, Mapping[str, Any]]) -> str:
    observation = case.get("observation") if isinstance(case.get("observation"), Mapping) else {}
    surface = str(observation.get("surface") or "")
    refs = [str(observation.get("source_ref") or "")]
    chunks: list[str] = []
    for ref in refs:
        row = evidence.get(ref, {})
        if not isinstance(row, Mapping):
            continue
        for key in ("model_snippet", "original_text"):
            text = str(row.get(key) or "")
            if text:
                chunks.append(text)
                break
    if not chunks:
        chunks.append(str(observation.get("exact_span") or ""))
    context = "\n".join(chunks)
    if len(context) > 1800:
        center = context.find(surface) if surface else 0
        center = max(center, 0)
        start = max(0, center - 700)
        context = context[start:start + 1800]
    return context


def _case_refs(case: Mapping[str, Any]) -> list[str]:
    observation = case.get("observation") if isinstance(case.get("observation"), Mapping) else {}
    return [str(observation.get("source_ref"))] if observation.get("source_ref") else []


def _fixture_cases(cases: Mapping[str, Mapping[str, Any]], validation: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_label = {str(row.get("label")): row for row in validation.get("regression_cases", []) if isinstance(row, Mapping)}
    regression_records = {str(row.get("case_id")): row for row in validation.get("regression_case_records", []) if isinstance(row, Mapping)}

    def add(case_id: str, label: str, expected: Mapping[str, Any]) -> None:
        row = cases.get(case_id) or regression_records.get(case_id)
        if not row:
            return
        if case_id in cases:
            interpretation = row.get("interpretation", {})
            decision = row.get("decision", {})
        else:
            interpretation = row.get("interpretation", {})
            decision = row.get("decision", {})
        actual = {"entity_kind": interpretation.get("entity_kind"), "mention_scope": interpretation.get("mention_scope"), "discourse_role": interpretation.get("discourse_role"), "identity_status": decision.get("identity_status"), "person_id": decision.get("person_id")}
        passed = all(actual.get(k) == v for k, v in expected.items())
        rows.append({"fixture_id": label, "case_id": case_id, "expected": dict(expected), "actual": actual, "passed": passed, "source": "offline_hng2_schema_regression"})

    add("regression-mount-tao", "山涛→山濤", {"identity_status": "resolved_existing", "person_id": "person-043"})
    add("regression-yu-taiwei", "庾太尉→庾亮", {"identity_status": "resolved_existing", "person_id": "person-010"})
    add("regression-bian-dun", "卞壼從父兄敦不→王敦", {"identity_status": "resolved_new_candidate"})
    add("regression-structural-kinship", "喜弟預女→not_single_person", {"entity_kind": "structural_kinship_expression", "identity_status": "not_single_person"})
    add("regression-title-wendi", "文帝保持歧义", {"entity_kind": "person_title", "identity_status": "ambiguous"})
    add("regression-metatext-yuanhong", "袁宏紀→metatextual", {"mention_scope": "metatextual", "discourse_role": "cited_author"})
    meta_cases = [row for row in cases.values() if (row.get("interpretation") or {}).get("mention_scope") == "metatextual"]
    for row in sorted(meta_cases, key=lambda x: str(x.get("case_id"))):
        add(str(row["case_id"]), "metatextual-existing-" + str(row["case_id"])[-8:], {"mention_scope": "metatextual", "discourse_role": "cited_author"})
    short_open = next((row for row in cases.values() if len(resolver.matching_normalize((row.get("observation") or {}).get("surface"))) <= 1 and (row.get("research_gap") or {}).get("status") == "open"), None)
    if short_open:
        add(str(short_open["case_id"]), "real-short-name-open", {"entity_kind": "abbreviated_name"})
    new_case = next((row for row in cases.values() if (row.get("decision") or {}).get("identity_status") == "resolved_new_candidate"), None)
    if new_case:
        add(str(new_case["case_id"]), "real-new-person-candidate", {"identity_status": "resolved_new_candidate"})
    return rows


def build_selection() -> dict[str, Any]:
    cases, gaps, evidence = load_base()
    eligible = [
        (case_id, cases[case_id], gaps[case_id])
        for case_id in sorted(gaps)
        if gaps[case_id].get("status") == "open"
        and case_id in cases
        and _case_refs(cases[case_id])
        and _context_for_case(cases[case_id], evidence)
        and _case_refs(cases[case_id])[0].startswith(("hng01-", "hng02-"))
    ]
    by_category: dict[str, list[tuple[str, dict[str, Any], dict[str, Any]]]] = collections.defaultdict(list)
    for item in eligible:
        by_category[_category(item[1], item[2])].append(item)
    targets = [
        ("title_office", 4), ("kinship_structural", 4), ("abbreviated_short", 3),
        ("metatextual", 2), ("unresolved_new", 3), ("temporal_constraint", 2),
    ]
    selected: dict[str, str] = {}
    rejected: list[dict[str, Any]] = []
    selected_basis: dict[str, str] = {}
    for category, count in targets:
        pool = sorted(by_category.get(category, []), key=lambda item: (_stable_key(item[0]), item[0]))
        for case_id, case, gap in pool[:count]:
            if case_id not in selected:
                selected[case_id] = category
                selected_basis[case_id] = "native_open_gap_category"
        if len(pool) < count:
            rejected.append({"category": category, "requested": count, "available": len(pool), "reason": "insufficient_open_cases_in_frozen_projection"})
    # The frozen projection has no open metatextual rows.  For the other
    # requested strata, use deterministic difficult open rows as coverage
    # proxies and state that basis explicitly; never relabel them as model
    # findings.  Required metatextual cases stay in fixture coverage only.
    for category, count in (("unresolved_new", 3), ("temporal_constraint", 2)):
        missing = count - sum(value == category for value in selected.values())
        if missing <= 0:
            continue
        pool = [item for item in eligible if item[0] not in selected]
        if category == "unresolved_new":
            pool.sort(key=lambda item: (0 if str((item[1].get("decision") or {}).get("identity_status")) in {"unresolved", "ambiguous"} else 1, _stable_key(item[0]), item[0]))
        else:
            pool.sort(key=lambda item: (0 if str(item[1].get("observation", {}).get("source_work")) in {"晉書", "資治通鑑", "三國志"} else 1, _stable_key(item[0]), item[0]))
        for case_id, case, gap in pool[:missing]:
            selected[case_id] = category
            selected_basis[case_id] = "deterministic_open_gap_proxy"
    for case_id, case, gap in sorted(eligible, key=lambda item: (_stable_key(item[0]), item[0])):
        if len(selected) >= 18:
            break
        if case_id not in selected:
            selected[case_id] = "deterministic_fill"
    if len(selected) != 18:
        raise RuntimeError(f"only {len(selected)} eligible open ResearchGap cases with local context")
    validation = read_json(BASE / "validation-cases.json", {}) or {}
    fixtures = _fixture_cases(cases, validation)
    live_cases = []
    for case_id, category in sorted(selected.items(), key=lambda item: (_stable_key(item[0]), item[0])):
        case = cases[case_id]
        gap = gaps[case_id]
        live_cases.append({
            "case_id": case_id, "selection_category": category, "selection_basis": selected_basis.get(case_id, "native_open_gap_category"), "selection_key": _stable_key(case_id),
            "source_ref": case["observation"].get("source_ref"), "source_work": case["observation"].get("source_work"),
            "surface": case["observation"].get("surface"), "entity_kind": case["interpretation"].get("entity_kind"),
            "mention_scope": case["interpretation"].get("mention_scope"), "gap": gap,
        })
    return {
        "schema": RUN_SCHEMA, "stage": "hng2-schema-live-selection", "selection_version": SELECTION_VERSION,
        "frozen": True, "selected_case_count": len(live_cases), "live_cases": live_cases,
        "target_composition": {key: count for key, count in targets},
        "actual_live_composition": dict(sorted(collections.Counter(row["selection_category"] for row in live_cases).items())),
        "selection_rejections": rejected,
        "fixture_coverage_cases": fixtures,
        "open_research_gap_only": True, "no_frontier_expansion": True, "canonical_write_back": False,
        "base_projection_hash": json_hash({"cases": cases, "gaps": gaps}),
    }


def freeze_selection() -> dict[str, Any]:
    path = OUT / "selection.json"
    if path.is_file():
        selection = read_json(path, {}) or {}
        if selection.get("selection_version") != SELECTION_VERSION or selection.get("selected_case_count") != 18:
            raise RuntimeError("existing selection is not the frozen HNG2-SL selection")
        return selection
    selection = build_selection()
    write_json(path, selection)
    return selection


def _source_context(case: Mapping[str, Any], evidence: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    ref = str((case.get("observation") or {}).get("source_ref") or "")
    row = evidence.get(ref, {}) if isinstance(evidence.get(ref), Mapping) else {}
    text = str(row.get("model_snippet") or row.get("original_text") or "")
    quote = str((case.get("observation") or {}).get("exact_span") or "")
    if text and quote and quote not in text and quote in str(row.get("original_text") or ""):
        original = str(row.get("original_text") or "")
        center = original.find(quote)
        text = original[max(0, center - 700):center + len(quote) + 700]
    if not text:
        text = quote
    if ref:
        result[ref] = {"ref": ref, "work": row.get("source_work") or (case.get("observation") or {}).get("source_work"), "layer": row.get("source_layer"), "text": text, "original_text": str(row.get("original_text") or text), "source_form": "punctuated" if "wikisource" in ref else "legacy_local"}
    return result


def _model_packet(case: Mapping[str, Any], gap: Mapping[str, Any], passages: Mapping[str, Mapping[str, Any]], *, round_no: int) -> dict[str, Any]:
    observation = case.get("observation") or {}
    interpretation = case.get("interpretation") or {}
    candidates = []
    for item in case.get("candidates", []) if isinstance(case.get("candidates"), list) else []:
        if isinstance(item, Mapping):
            candidates.append({key: item.get(key) for key in ("candidate_key", "canonical_name", "known_forms", "chronology_summary", "graph_summary")})
    checks = []
    for item in case.get("constraint_checks", []) if isinstance(case.get("constraint_checks"), list) else []:
        if isinstance(item, Mapping):
            checks.append({key: item.get(key) for key in ("constraint_type", "constraint_scope", "candidate_key", "status", "computed_by", "independent", "reason_code")})
    supplied = []
    for ref, item in sorted(passages.items()):
        supplied.append({"ref": ref, "work": item.get("work"), "layer": item.get("layer"), "source_form": item.get("source_form"), "supplied_text": item.get("text", "")})
    return {
        "case": {"case_id": case.get("case_id"), "mention_id": observation.get("mention_id"), "surface": observation.get("surface"), "exact_span": observation.get("exact_span"), "source_work": observation.get("source_work"), "interpretation": {key: interpretation.get(key) for key in ("entity_kind", "reference_form", "mention_scope", "discourse_role", "structural_kinship", "summary")}},
        "frozen_gap": {key: gap.get(key) for key in ("status", "missing_constraints", "blocking_question", "next_best_action", "candidate_keys", "stop_condition")},
        "candidates": candidates, "hard_constraints": checks, "source_passages": supplied,
        "semantic_questions": list(schema.CHINESE_SEMANTIC_ASSIST_QUESTIONS), "round": round_no,
    }


def _extract_content(response: Mapping[str, Any]) -> str:
    choices = response.get("choices") if isinstance(response, Mapping) else None
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message") if isinstance(choices[0], Mapping) else {}
    return str((message or {}).get("content") or "")


def _usage(response: Mapping[str, Any]) -> dict[str, int]:
    usage = response.get("usage") if isinstance(response, Mapping) else {}
    usage = usage if isinstance(usage, Mapping) else {}
    return {key: int(usage.get(key) or 0) for key in ("prompt_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens", "total_tokens")}


def _call(kind: str, case_id: str, prompt: Mapping[str, Any], system: str, raw_dir: Path, sequence: int) -> dict[str, Any]:
    started = utc_now()
    begin = time.monotonic()
    record: dict[str, Any] = {"kind": kind, "case_id": case_id, "sequence": sequence, "start_time": started, "model": MODEL, "prompt_version": PROMPT_VERSION if kind == "semantic" else SEARCH_PROMPT_VERSION, "input_hash": json_hash(prompt), "canonical_write_back": False, "immutable": True}
    try:
        response = call_deepseek([
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False, sort_keys=True)},
        ], model=MODEL, temperature=0, response_format={"type": "json_object"}, tools=[], timeout=180)
        content = _extract_content(response)
        record.update({"status": "response", "response": response, "content": content, "usage": _usage(response)})
    except Exception as exc:  # noqa: BLE001 - preserve transport failure as an observable record
        record.update({"status": "transport_failure", "response": None, "content": "", "usage": {}, "exception_class": type(exc).__name__, "exception_message": _redact(exc)})
    record["elapsed_seconds"] = round(time.monotonic() - begin, 6)
    target = raw_dir / f"{sequence:03d}-{kind}-{case_id}.json"
    write_json(target, record)
    return record


def _evidence_item(item: Any) -> tuple[str, str] | None:
    if not isinstance(item, Mapping):
        return None
    ref = str(item.get("ref") or "")
    span = str(item.get("span") or item.get("text") or "")
    return (ref, span) if ref and span else None


def _validate_spans(items: Any, passages: Mapping[str, Mapping[str, Any]], label: str) -> tuple[list[dict[str, Any]], list[str], int]:
    valid: list[dict[str, Any]] = []
    errors: list[str] = []
    boundary_count = 0
    if not isinstance(items, list):
        return valid, [f"{label}_not_array"], boundary_count
    for index, raw in enumerate(items):
        pair = _evidence_item(raw)
        if not pair:
            errors.append(f"{label}[{index}]:malformed")
            continue
        ref, span = pair
        source = str(passages.get(ref, {}).get("text") or "")
        if not source:
            errors.append(f"{label}[{index}]:unknown_ref:{ref}")
            continue
        if span in source:
            valid.append({"ref": ref, "span": span, "boundary_punctuation_normalized": False})
        elif quote_matches(source, span):
            boundary_count += 1
            valid.append({"ref": ref, "span": span, "boundary_punctuation_normalized": True})
        else:
            errors.append(f"{label}[{index}]:span_not_found:{ref}")
    return valid, errors, boundary_count


def validate_model_payload(payload: Any, case: Mapping[str, Any], passages: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    invalid_enums: list[str] = []
    invented_candidates: list[str] = []
    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": ["payload_not_object"], "invalid_enum_outputs": [], "invented_candidate_attempts": [], "boundary_punctuation_normalizations": 0}
    forbidden = sorted(set(payload).intersection(FORBIDDEN_MODEL_FIELDS))
    if forbidden:
        invented_candidates.extend([key for key in forbidden if key in {"person_id", "provisional_person_id"}])
        errors.extend(f"forbidden_model_field:{key}" for key in forbidden)
    unknown = sorted(set(payload) - MODEL_TOP_FIELDS)
    errors.extend(f"unknown_top_field:{key}" for key in unknown)
    assessment = payload.get("semantic_assessment") if isinstance(payload.get("semantic_assessment"), Mapping) else None
    recommendation = payload.get("identity_recommendation") if isinstance(payload.get("identity_recommendation"), Mapping) else None
    gap = payload.get("research_gap") if isinstance(payload.get("research_gap"), Mapping) else None
    if assessment is None:
        errors.append("missing_semantic_assessment")
    if recommendation is None:
        errors.append("missing_identity_recommendation")
    if gap is None:
        errors.append("missing_research_gap")
    if assessment:
        for key in set(assessment) - SEMANTIC_FIELDS:
            errors.append(f"unknown_semantic_field:{key}")
        for key, allowed in (("assessment_status", schema.ASSESSMENT_STATUSES), ("semantic_fit", schema.SEMANTIC_FITS), ("observed_role", schema.DISCOURSE_ROLES)):
            if assessment.get(key) not in allowed:
                invalid_enums.append(f"semantic_assessment.{key}:{assessment.get(key)}")
        if not str(assessment.get("summary") or "") and assessment.get("assessment_status") == "assessed":
            errors.append("empty_semantic_summary")
    if recommendation:
        for key in set(recommendation) - RECOMMENDATION_FIELDS:
            errors.append(f"unknown_recommendation_field:{key}")
        decision = recommendation.get("decision")
        if decision not in schema.RECOMMENDATION_DECISIONS:
            invalid_enums.append(f"identity_recommendation.decision:{decision}")
        if recommendation.get("confidence") not in schema.CONFIDENCE_LEVELS:
            invalid_enums.append(f"identity_recommendation.confidence:{recommendation.get('confidence')}")
        candidate_keys = {str(item.get("candidate_key")) for item in case.get("candidates", []) if isinstance(item, Mapping) and item.get("candidate_key")}
        chosen = recommendation.get("chosen_candidate_key")
        if chosen is not None and str(chosen) not in candidate_keys:
            invented_candidates.append(str(chosen))
            errors.append(f"invented_candidate_key:{chosen}")
        new_key = recommendation.get("new_entity_key")
        if new_key not in {None, "n0"}:
            invented_candidates.append(str(new_key))
            errors.append(f"invented_new_entity_key:{new_key}")
        if decision == "new_person_candidate" and new_key != "n0":
            errors.append("new_person_candidate_without_n0")
        if decision == "choose_candidate" and chosen is None:
            errors.append("choose_candidate_without_key")
        if decision != "choose_candidate" and chosen is not None:
            errors.append("non_choose_candidate_has_key")
    if gap:
        for key in set(gap) - GAP_FIELDS:
            errors.append(f"unknown_gap_field:{key}")
        if gap.get("status") not in schema.RESEARCH_GAP_STATUSES:
            invalid_enums.append(f"research_gap.status:{gap.get('status')}")
        if gap.get("next_best_action") not in schema.RESEARCH_ACTIONS:
            invalid_enums.append(f"research_gap.next_best_action:{gap.get('next_best_action')}")
        candidate_keys = {str(item.get("candidate_key")) for item in case.get("candidates", []) if isinstance(item, Mapping) and item.get("candidate_key")}
        if not isinstance(gap.get("candidate_keys", []), list) or any(str(key) not in candidate_keys for key in gap.get("candidate_keys", [])):
            errors.append("gap_contains_unknown_candidate_key")
    spans_a, span_errors_a, boundary_a = _validate_spans((assessment or {}).get("evidence_spans", []), passages, "semantic_evidence")
    spans_r, span_errors_r, boundary_r = _validate_spans((recommendation or {}).get("evidence_spans", []), passages, "recommendation_evidence")
    errors.extend(span_errors_a + span_errors_r)
    errors.extend(invalid_enums)
    if assessment and assessment.get("mention_scope") in {"event_participant", "speaker"}:
        errors.append("assessment_unknown_mention_scope_field")
    if (case.get("interpretation") or {}).get("mention_scope") == "metatextual" and (assessment or {}).get("observed_role") in {"event_participant", "speaker"}:
        errors.append("metatextual_role_invariant")
    return {"valid": not errors, "errors": sorted(set(errors)), "invalid_enum_outputs": sorted(set(invalid_enums)), "invented_candidate_attempts": sorted(set(invented_candidates)), "validated_assessment_evidence": spans_a, "validated_recommendation_evidence": spans_r, "boundary_punctuation_normalizations": boundary_a + boundary_r}


def _project_decision(case: Mapping[str, Any], recommendation: Mapping[str, Any], valid: Mapping[str, Any], refs: Sequence[str]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    candidates = {str(row.get("candidate_key")): row for row in case.get("candidates", []) if isinstance(row, Mapping) and row.get("candidate_key")}
    chosen_key = str(recommendation.get("chosen_candidate_key")) if recommendation.get("chosen_candidate_key") is not None else None
    selected = candidates.get(chosen_key or "")
    rec_decision = str(recommendation.get("decision") or "unresolved")
    confidence = str(recommendation.get("confidence") or "unknown")
    reasons = [str(x) for x in recommendation.get("reason_codes", []) if str(x)] if isinstance(recommendation.get("reason_codes"), list) else []
    if rec_decision == "choose_candidate" and selected and selected.get("person_id"):
        status, person_id, new_key = "resolved_existing", selected.get("person_id"), None
        action = {"action": "link_existing", "node_type": "existing_person", "person_id": person_id, "provisional_person_id": None, "frontier_status": "eligible", "reason_codes": ["validated_candidate", *reasons]}
    elif rec_decision == "new_person_candidate" and selected:
        status, person_id, new_key = "resolved_new_candidate", None, "n0"
        provisional = f"hng2-schema-live-provisional-{stable_hash({'case_id': case.get('case_id'), 'candidate_key': chosen_key})[:20]}"
        action = {"action": "create_provisional_candidate", "node_type": "provisional_person", "person_id": None, "provisional_person_id": provisional, "frontier_status": "candidate", "reason_codes": ["validated_new_candidate", *reasons]}
    elif rec_decision == "not_a_single_person":
        status, person_id, new_key = "not_single_person", None, None
        action = {"action": "no_person_node", "node_type": "none", "person_id": None, "provisional_person_id": None, "frontier_status": "blocked", "reason_codes": ["structural_expression_not_single_person", *reasons]}
    elif rec_decision == "not_a_person":
        status, person_id, new_key = "not_person", None, None
        action = {"action": "no_person_node", "node_type": "none", "person_id": None, "provisional_person_id": None, "frontier_status": "blocked", "reason_codes": ["generic_role", *reasons]}
    elif rec_decision == "ambiguous":
        status, person_id, new_key = "ambiguous", None, None
        action = {"action": "hold_for_review", "node_type": "none", "person_id": None, "provisional_person_id": None, "frontier_status": "needs_identity_review", "reason_codes": ["identity_ambiguity", *reasons]}
    else:
        status, person_id, new_key = "unresolved", None, None
        action = {"action": "hold_for_review", "node_type": "none", "person_id": None, "provisional_person_id": None, "frontier_status": "needs_semantic_parse", "reason_codes": ["identity_unresolved", *reasons]}
    decision = {"case_id": case.get("case_id"), "identity_status": status, "chosen_candidate_key": chosen_key if status in {"resolved_existing", "resolved_new_candidate"} else None, "person_id": person_id, "new_entity_key": new_key, "confidence": confidence, "reason_codes": reasons, "supporting_evidence_refs": sorted({str(x.get("ref")) for x in [*valid.get("validated_assessment_evidence", []), *valid.get("validated_recommendation_evidence", [])] if x.get("ref")}), "decision_summary": str(recommendation.get("summary") or recommendation.get("unresolved_reason") or ""), "canonical_write_back": False}
    if status in {"resolved_existing", "resolved_new_candidate", "not_person", "not_single_person"}:
        gap = {"status": "closed", "missing_constraints": [], "blocking_question": "", "next_best_action": "none", "candidate_keys": [], "stop_condition": "identity interpretation is sufficient for this targeted case"}
    else:
        old = case.get("research_gap") or {}
        gap = {"status": "open", "missing_constraints": [str(x) for x in (old.get("missing_constraints") or [])], "blocking_question": str(recommendation.get("unresolved_reason") or old.get("blocking_question") or "Further context is required for identity assessment"), "next_best_action": str(old.get("next_best_action") or "human_review"), "candidate_keys": [str(x) for x in (old.get("candidate_keys") or []) if str(x) in candidates], "stop_condition": str(old.get("stop_condition") or "stop when an independent source-local identity is supported")}
    return decision, action, gap


def _validate_search_plan(payload: Any, case: Mapping[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if not isinstance(payload, Mapping) or not isinstance(payload.get("search_plan"), Mapping):
        return None, ["missing_search_plan"]
    plan = dict(payload["search_plan"])
    allowed = {"target_constraint", "goal", "candidate_keys", "preferred_sources", "search_entities", "search_patterns", "temporal_scope", "graph_neighborhood_scope", "stop_condition"}
    errors.extend(f"unknown_search_plan_field:{key}" for key in set(plan) - allowed)
    candidate_keys = {str(item.get("candidate_key")) for item in case.get("candidates", []) if isinstance(item, Mapping) and item.get("candidate_key")}
    if any(str(key) not in candidate_keys for key in plan.get("candidate_keys", []) if isinstance(plan.get("candidate_keys"), list)):
        errors.append("search_plan_unknown_candidate")
    if not isinstance(plan.get("preferred_sources"), list) or any(str(x) not in APPROVED_SOURCES for x in plan.get("preferred_sources", [])):
        errors.append("search_plan_source_not_approved")
    if plan.get("graph_neighborhood_scope") not in {"case_only", "none"}:
        errors.append("search_plan_recursive_graph_scope")
    for key in ("target_constraint", "goal", "stop_condition"):
        if not str(plan.get(key) or "").strip():
            errors.append(f"empty_search_plan:{key}")
    for key in ("search_entities", "search_patterns"):
        if not isinstance(plan.get(key), list) or any(not str(x).strip() for x in plan.get(key, [])):
            errors.append(f"invalid_search_plan:{key}")
    return (plan if not errors else None), sorted(set(errors))


def _fallback_plan(case: Mapping[str, Any], gap: Mapping[str, Any]) -> dict[str, Any]:
    surface = str((case.get("observation") or {}).get("surface") or "")
    names = [str(x.get("canonical_name")) for x in case.get("candidates", []) if isinstance(x, Mapping) and x.get("canonical_name")]
    source = str((case.get("observation") or {}).get("source_work") or "local source corpus")
    return {"target_constraint": str((gap or {}).get("missing_constraints", ["identity_evidence"])[0]), "goal": str((gap or {}).get("blocking_question") or "obtain source-local identity evidence"), "candidate_keys": [str(x.get("candidate_key")) for x in case.get("candidates", []) if isinstance(x, Mapping) and x.get("candidate_key")], "preferred_sources": [source if source in APPROVED_SOURCES else "local source corpus"], "search_entities": [surface, *names], "search_patterns": [surface, "父", "子", "兄", "弟", "官"], "temporal_scope": {}, "graph_neighborhood_scope": "case_only", "stop_condition": str((gap or {}).get("stop_condition") or "stop when exact source-local evidence is found"), "fallback": True}


def _retrieve(case: Mapping[str, Any], plan: Mapping[str, Any], punctuated: Sequence[Mapping[str, Any]], legacy: Sequence[Mapping[str, Any]], *, original_ref: str) -> dict[str, Any]:
    observation = case.get("observation") or {}
    terms = [str(x) for x in [*(plan.get("search_entities") or []), *(plan.get("search_patterns") or [])] if str(x).strip()]
    profile = {"person_id": f"case:{case.get('case_id')}", "canonical_name": str(observation.get("surface") or ""), "search_terms_original": sorted(set(terms), key=lambda x: (-len(resolver.matching_normalize(x)), x))}
    found = find_punctuated_first(profile, punctuated, legacy, top_k=6)
    opened = open_short_hits(found, punctuated, legacy, max_passages=4)
    opened = [row for row in opened if str(row.get("source_ref")) != original_ref]
    passages = []
    for item in opened:
        ref = str(item.get("source_ref") or "")
        if not ref:
            continue
        passages.append({"ref": ref, "work": item.get("work"), "layer": item.get("source_layer"), "source_form": item.get("source_form"), "text": str(item.get("snippet") or ""), "original_text": str(item.get("original_text") or ""), "locator": item.get("locator", {}), "opened_chars": len(str(item.get("snippet") or ""))})
    return {"round": 1, "case_id": case.get("case_id"), "searched_corpora": sorted(set(str(x.get("work")) for x in [*punctuated, *legacy] if x.get("work"))), "retrieved_refs": [str(x.get("source_ref")) for x in found.get("hits", []) if x.get("source_ref")], "opened_refs": [str(x.get("ref")) for x in passages], "used_refs": [], "new_used_refs": [], "source_forms": sorted(set(str(x.get("source_form")) for x in passages)), "routing_reason": found.get("routes", []), "opened_chars": sum(int(x.get("opened_chars") or 0) for x in passages), "passages": passages, "canonical_write_back": False}


def _preflight() -> dict[str, Any]:
    start = utc_now()
    begin = time.monotonic()
    try:
        response = call_deepseek([{"role": "user", "content": "Reply only with OK"}], model=MODEL, temperature=0, timeout=60)
        return {"status": "reachable", "start_time": start, "elapsed_seconds": round(time.monotonic() - begin, 6), "response_model": response.get("model") if isinstance(response, Mapping) else None, "usage": _usage(response) if isinstance(response, Mapping) else {}, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"status": "unavailable", "start_time": start, "elapsed_seconds": round(time.monotonic() - begin, 6), "response_model": None, "usage": {}, "exception_class": type(exc).__name__, "exception_message": _redact(exc), "error": "transport_or_auth_failure"}


def _record_fixture_validation(selection: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in selection.get("fixture_coverage_cases", []) if isinstance(row, Mapping)]


def replay_projection() -> dict[str, Any]:
    """Split GraphAction from IdentityDecision without touching raw responses."""

    decision_doc = read_json(OUT / "identity-decisions.json", {}) or {}
    rows = decision_doc.get("decisions", []) if isinstance(decision_doc.get("decisions"), list) else []
    existing_actions_doc = read_json(OUT / "graph-actions.json", {}) or {}
    existing_actions = [dict(row) for row in existing_actions_doc.get("actions", []) if isinstance(row, Mapping)]
    actions: list[dict[str, Any]] = []
    clean: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        item = dict(row)
        action = item.pop("graph_action", None)
        if isinstance(action, Mapping):
            actions.append({"case_id": item.get("case_id"), **dict(action), "canonical_write_back": False})
        clean.append(item)
    if not actions:
        actions = existing_actions
    write_json(OUT / "identity-decisions.json", {**decision_doc, "decisions": clean, "canonical_write_back": False})
    write_json(OUT / "graph-actions.json", {"schema": RUN_SCHEMA, "actions": sorted(actions, key=lambda x: str(x.get("case_id"))), "canonical_write_back": False})
    manifest = read_json(OUT / "manifest.json", {}) or {}
    projection_names = [
        "semantic-assessments.json", "identity-recommendations.json", "identity-decisions.json",
        "graph-actions.json", "search-plans.json", "retrieval-trace.json", "updated-constraints.json",
        "research-gap-transitions.json", "validation-results.json", "metrics.json",
    ]
    projection = {name: read_json(OUT / name, {}) or {} for name in projection_names}
    manifest["projection_hash"] = json_hash(projection)
    manifest["graph_action_projection"] = "separate"
    write_json(OUT / "manifest.json", manifest)
    metrics = read_json(OUT / "metrics.json", {}) or {}
    plan_doc = read_json(OUT / "search-plans.json", {}) or {}
    raw_root = ROOT / str(manifest.get("raw_api_root") or "")
    raw_files = [read_json(path, {}) or {} for path in raw_root.glob("*.json")] if raw_root.is_dir() else []
    metrics["search_plan_validation_failures"] = sum(bool(row.get("model_validation_errors")) for row in plan_doc.get("plans", []) if isinstance(row, Mapping))
    metrics["search_plan_fallback_count"] = sum(str(row.get("source")) != "model" for row in plan_doc.get("plans", []) if isinstance(row, Mapping))
    metrics["raw_transport_failure_count"] = sum(row.get("status") == "transport_failure" for row in raw_files if isinstance(row, Mapping))
    metrics["semantic_json_parse_failure_count"] = sum(any(str(error).startswith("json_parse:") for error in row.get("errors", [])) for row in (read_json(OUT / "validation-results.json", {}) or {}).get("results", []) if isinstance(row, Mapping))
    write_json(OUT / "metrics.json", metrics)
    projection = {name: read_json(OUT / name, {}) or {} for name in projection_names}
    manifest["projection_hash"] = json_hash(projection)
    write_json(OUT / "manifest.json", manifest)
    return {"decision_count": len(clean), "graph_action_count": len(actions), "projection_hash": manifest["projection_hash"], "api_calls": 0}


def refresh_baseline_hashes() -> dict[str, Any]:
    """Update only deterministic input hashes after schema-only replay."""

    cases, gaps, _ = load_base()
    selection = read_json(OUT / "selection.json", {}) or {}
    selection["base_projection_hash"] = json_hash({"cases": cases, "gaps": gaps})
    write_json(OUT / "selection.json", selection)
    manifest = read_json(OUT / "manifest.json", {}) or {}
    manifest["base_schema_hash"] = json_hash({"cases": cases, "gaps": gaps})
    write_json(OUT / "manifest.json", manifest)
    return {"base_projection_hash": selection["base_projection_hash"], "api_calls": 0}


def run(*, run_id: str | None = None, selection_only: bool = False, quiet: bool = False) -> dict[str, Any]:
    selection = freeze_selection()
    if selection_only:
        return selection
    run_id = run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_dir = RAW / run_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    preflight = _preflight()
    write_json(Path("/tmp/hng2-schema-live-preflight.json"), preflight)
    if preflight.get("status") != "reachable":
        status = {"schema": RUN_SCHEMA, "stage": "hng2-schema-live", "run_id": run_id, "execution_status": "live_network_unavailable", "preflight": preflight, "story_results_created": False, "canonical_write_back": False}
        write_json(OUT / "run-status.json", status)
        if not quiet:
            print(json.dumps({"status": "live_network_unavailable", "preflight": "/tmp/hng2-schema-live-preflight.json"}, ensure_ascii=False))
        return status
    cases, gaps, evidence = load_base()
    punctuated, legacy = load_retrieval_sources()
    assessments: list[dict[str, Any]] = []
    recommendations: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    plans: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    updated_constraints: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    validations: list[dict[str, Any]] = []
    raw_records: list[dict[str, Any]] = []
    usage_rows: list[dict[str, Any]] = []
    sequence = 0
    for selected in selection["live_cases"]:
        case_id = str(selected["case_id"])
        case = cases[case_id]
        current_gap = dict(gaps[case_id])
        passages = _source_context(case, evidence)
        packet = _model_packet(case, current_gap, passages, round_no=1)
        sequence += 1
        raw = _call("semantic", case_id, packet, SEMANTIC_SYSTEM, raw_dir, sequence)
        raw_records.append({"kind": raw["kind"], "case_id": case_id, "sequence": sequence, "path": str((raw_dir / f"{sequence:03d}-semantic-{case_id}.json").relative_to(ROOT)), "status": raw.get("status"), "elapsed_seconds": raw.get("elapsed_seconds")})
        usage_rows.append({"kind": "semantic", "case_id": case_id, **raw.get("usage", {})})
        parsed = None
        parse_error = None
        if raw.get("status") == "response":
            try:
                parsed = json.loads(str(raw.get("content") or ""))
            except Exception as exc:  # noqa: BLE001
                parse_error = f"json_parse:{type(exc).__name__}"
        validation = validate_model_payload(parsed, case, passages) if parsed is not None else {"valid": False, "errors": [parse_error or "no_response"], "invalid_enum_outputs": [], "invented_candidate_attempts": [], "boundary_punctuation_normalizations": 0}
        validations.append({"case_id": case_id, "round": 1, "valid": validation.get("valid", False), "errors": validation.get("errors", []), "invalid_enum_outputs": validation.get("invalid_enum_outputs", []), "invented_candidate_attempts": validation.get("invented_candidate_attempts", []), "boundary_punctuation_normalizations": validation.get("boundary_punctuation_normalizations", 0)})
        if not validation.get("valid"):
            transitions.append({"case_id": case_id, "round": 1, "from": current_gap.get("status"), "to": "open", "reason": "semantic_validation_failed", "semantic_rounds": 1, "canonical_write_back": False})
            continue
        assessment = dict(parsed["semantic_assessment"])
        recommendation = dict(parsed["identity_recommendation"])
        decision, action, next_gap = _project_decision(case, recommendation, validation, _case_refs(case))
        assessments.append({"case_id": case_id, "round": 1, **assessment, "validated_evidence": validation.get("validated_assessment_evidence", []), "canonical_write_back": False})
        recommendations.append({"case_id": case_id, "round": 1, **recommendation, "validated_evidence": validation.get("validated_recommendation_evidence", []), "canonical_write_back": False})
        if next_gap["status"] == "open":
            sequence += 1
            search_packet = {"case_id": case_id, "research_gap": next_gap, "mention": {"surface": (case.get("observation") or {}).get("surface"), "source_work": (case.get("observation") or {}).get("source_work")}, "candidates": case.get("candidates", []), "source_passages": [{key: item.get(key) for key in ("ref", "work", "layer", "source_form", "text")} for item in passages.values()], "planning_questions": list(schema.CHINESE_SEARCH_PLAN_QUESTIONS)}
            search_raw = _call("search-plan", case_id, search_packet, SEARCH_SYSTEM, raw_dir, sequence)
            raw_records.append({"kind": search_raw["kind"], "case_id": case_id, "sequence": sequence, "path": str((raw_dir / f"{sequence:03d}-search-plan-{case_id}.json").relative_to(ROOT)), "status": search_raw.get("status"), "elapsed_seconds": search_raw.get("elapsed_seconds")})
            usage_rows.append({"kind": "search-plan", "case_id": case_id, **search_raw.get("usage", {})})
            search_payload = None
            if search_raw.get("status") == "response":
                try:
                    search_payload = json.loads(str(search_raw.get("content") or ""))
                except Exception:
                    search_payload = None
            plan, plan_errors = _validate_search_plan(search_payload, case)
            if plan is None:
                plan = _fallback_plan(case, next_gap)
            plans.append({"case_id": case_id, "round": 1, "plan": plan, "model_validation_errors": plan_errors, "source": "model" if not plan.get("fallback") else "frozen_gap_fallback", "canonical_write_back": False})
            trace = _retrieve(case, plan, punctuated, legacy, original_ref=str((case.get("observation") or {}).get("source_ref") or ""))
            traces.append(trace)
            retrieved_passages = dict(passages)
            for row in trace.get("passages", []):
                retrieved_passages[str(row["ref"])] = row
            packet2 = _model_packet(case, next_gap, retrieved_passages, round_no=2)
            sequence += 1
            raw2 = _call("semantic", case_id, packet2, SEMANTIC_SYSTEM, raw_dir, sequence)
            raw_records.append({"kind": raw2["kind"], "case_id": case_id, "sequence": sequence, "path": str((raw_dir / f"{sequence:03d}-semantic-{case_id}.json").relative_to(ROOT)), "status": raw2.get("status"), "elapsed_seconds": raw2.get("elapsed_seconds")})
            usage_rows.append({"kind": "semantic", "case_id": case_id, **raw2.get("usage", {})})
            parsed2 = None
            parse_error2 = None
            if raw2.get("status") == "response":
                try:
                    parsed2 = json.loads(str(raw2.get("content") or ""))
                except Exception as exc:  # noqa: BLE001
                    parse_error2 = f"json_parse:{type(exc).__name__}"
            validation2 = validate_model_payload(parsed2, case, retrieved_passages) if parsed2 is not None else {"valid": False, "errors": [parse_error2 or "no_response"], "invalid_enum_outputs": [], "invented_candidate_attempts": [], "boundary_punctuation_normalizations": 0}
            validations.append({"case_id": case_id, "round": 2, "valid": validation2.get("valid", False), "errors": validation2.get("errors", []), "invalid_enum_outputs": validation2.get("invalid_enum_outputs", []), "invented_candidate_attempts": validation2.get("invented_candidate_attempts", []), "boundary_punctuation_normalizations": validation2.get("boundary_punctuation_normalizations", 0)})
            if validation2.get("valid"):
                assessment = dict(parsed2["semantic_assessment"])
                recommendation = dict(parsed2["identity_recommendation"])
                decision, action, next_gap = _project_decision(case, recommendation, validation2, list(retrieved_passages))
                assessments.append({"case_id": case_id, "round": 2, **assessment, "validated_evidence": validation2.get("validated_assessment_evidence", []), "canonical_write_back": False})
                recommendations.append({"case_id": case_id, "round": 2, **recommendation, "validated_evidence": validation2.get("validated_recommendation_evidence", []), "canonical_write_back": False})
                used = sorted({str(x.get("ref")) for x in [*validation2.get("validated_assessment_evidence", []), *validation2.get("validated_recommendation_evidence", [])] if x.get("ref")})
                trace["used_refs"] = used
                trace["new_used_refs"] = sorted(set(used) - set(_case_refs(case)))
            else:
                next_gap = {"status": "open", "missing_constraints": ["semantic_validation"], "blocking_question": "semantic assessment could not be validated", "next_best_action": "human_review", "candidate_keys": [], "stop_condition": "human review required"}
            transitions.append({"case_id": case_id, "round": 2, "from": "open", "to": next_gap.get("status"), "reason": "targeted_retrieval_and_second_semantic_assessment", "semantic_rounds": 2, "canonical_write_back": False})
        else:
            transitions.append({"case_id": case_id, "round": 1, "from": current_gap.get("status"), "to": next_gap.get("status"), "reason": "closed_before_retrieval", "semantic_rounds": 1, "canonical_write_back": False})
        decisions.append({**decision, "graph_action": action, "research_gap": next_gap, "canonical_write_back": False})
        updated_constraints.append({"case_id": case_id, "base_constraints_unchanged": True, "new_evidence_refs": sorted({ref for trace in traces if trace.get("case_id") == case_id for ref in trace.get("used_refs", [])}), "constraint_scope_preserved": True, "canonical_write_back": False})
    # Any case with a round-1 validation failure has no safe decision.
    for selected in selection["live_cases"]:
        if not any(row.get("case_id") == selected["case_id"] for row in decisions):
            decisions.append({"case_id": selected["case_id"], "identity_status": "rejected", "chosen_candidate_key": None, "person_id": None, "new_entity_key": None, "confidence": "unknown", "reason_codes": ["semantic_validation_failure"], "supporting_evidence_refs": [], "decision_summary": "no valid semantic recommendation", "graph_action": {"action": "hold_for_review", "node_type": "none", "person_id": None, "provisional_person_id": None, "frontier_status": "needs_semantic_parse", "reason_codes": ["semantic_validation_failure"]}, "research_gap": {"status": "open", "missing_constraints": ["semantic_validation"], "blocking_question": "semantic assessment could not be validated", "next_best_action": "human_review", "candidate_keys": [], "stop_condition": "human review required"}, "canonical_write_back": False})
    all_usage = [row for row in usage_rows if isinstance(row, Mapping)]
    def total(key: str) -> int:
        return sum(int(row.get(key) or 0) for row in all_usage)
    latencies = [float(row.get("elapsed_seconds")) for row in raw_records if row.get("status") == "response" and row.get("elapsed_seconds") is not None]
    valid_cases = {str(row.get("case_id")) for row in decisions if row.get("identity_status") != "rejected"}
    final_status = {str(row.get("case_id")): str(row.get("identity_status")) for row in decisions}
    metrics = {
        "schema": RUN_SCHEMA, "stage": "hng2-schema-live", "selected_cases": len(selection["live_cases"]), "semantic_calls": sum(row.get("kind") == "semantic" for row in raw_records), "search_plan_calls": sum(row.get("kind") == "search-plan" for row in raw_records), "retrieval_rounds": len(traces), "gaps_closed_before_retrieval": sum(row.get("round") == 1 and row.get("to") == "closed" for row in transitions), "gaps_closed_after_retrieval": sum(row.get("round") == 2 and row.get("to") == "closed" for row in transitions), "gaps_remaining_open": sum(row.get("to") == "open" for row in transitions if row.get("round") in {1, 2}), "identity_status_counts": dict(sorted(collections.Counter(final_status.values()).items())), "validator_rejections": sum(not bool(row.get("valid")) for row in validations), "invalid_enum_outputs": sum(len(row.get("invalid_enum_outputs", [])) for row in validations), "invented_candidate_attempts": sum(len(row.get("invented_candidate_attempts", [])) for row in validations), "evidence_span_failures": sum(sum("span_not_found" in str(error) or "unknown_ref" in str(error) for error in row.get("errors", [])) for row in validations), "prompt_tokens": total("prompt_tokens"), "completion_tokens": total("completion_tokens"), "total_tokens": total("total_tokens"), "median_latency_seconds": statistics.median(latencies) if latencies else None, "max_latency_seconds": max(latencies) if latencies else None, "fixture_coverage_count": len(selection.get("fixture_coverage_cases", [])), "fixture_coverage_passed": sum(bool(row.get("passed")) for row in selection.get("fixture_coverage_cases", [])), "canonical_write_back": False, "no_frontier_expansion": True, "preflight": preflight,
    }
    for trace in traces:
        trace["new_used_refs"] = sorted(set(trace.get("used_refs", [])) - set(trace.get("new_used_refs", []))) if trace.get("new_used_refs") else []
    decision_rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    for row in decisions:
        item = dict(row)
        action = item.pop("graph_action", None)
        if isinstance(action, Mapping):
            action_rows.append({"case_id": item.get("case_id"), **dict(action), "canonical_write_back": False})
        decision_rows.append(item)
    documents = {
        "semantic-assessments.json": {"schema": RUN_SCHEMA, "assessments": sorted(assessments, key=lambda x: (str(x.get("case_id")), int(x.get("round", 0)))), "canonical_write_back": False},
        "identity-recommendations.json": {"schema": RUN_SCHEMA, "recommendations": sorted(recommendations, key=lambda x: (str(x.get("case_id")), int(x.get("round", 0)))), "canonical_write_back": False},
        "identity-decisions.json": {"schema": RUN_SCHEMA, "decisions": sorted(decision_rows, key=lambda x: str(x.get("case_id"))), "canonical_write_back": False},
        "graph-actions.json": {"schema": RUN_SCHEMA, "actions": sorted(action_rows, key=lambda x: str(x.get("case_id"))), "canonical_write_back": False},
        "search-plans.json": {"schema": RUN_SCHEMA, "plans": sorted(plans, key=lambda x: str(x.get("case_id"))), "canonical_write_back": False},
        "retrieval-trace.json": {"schema": RUN_SCHEMA, "traces": sorted(traces, key=lambda x: str(x.get("case_id"))), "canonical_write_back": False},
        "updated-constraints.json": {"schema": RUN_SCHEMA, "constraints": sorted(updated_constraints, key=lambda x: str(x.get("case_id"))), "canonical_write_back": False},
        "research-gap-transitions.json": {"schema": RUN_SCHEMA, "transitions": transitions, "canonical_write_back": False},
        "validation-results.json": {"schema": RUN_SCHEMA, "results": validations, "fixture_coverage": selection.get("fixture_coverage_cases", []), "canonical_write_back": False},
        "metrics.json": metrics,
    }
    for name, value in documents.items():
        write_json(OUT / name, value)
    write_json(OUT / "usage.json", {"schema": RUN_SCHEMA, "rows": usage_rows, "preflight": preflight, "canonical_write_back": False})
    write_json(OUT / "manifest.json", {"schema": RUN_SCHEMA, "stage": "hng2-schema-live", "run_id": run_id, "provider": PROVIDER, "model": MODEL, "prompt_version": PROMPT_VERSION, "search_prompt_version": SEARCH_PROMPT_VERSION, "selection_hash": json_hash(selection), "raw_api_root": str(raw_dir.relative_to(ROOT)), "raw_records": raw_records, "projection_hash": json_hash(documents), "semantic_round_cap": 2, "retrieval_round_cap": 1, "frontier_expansion": False, "canonical_write_back": False, "base_schema_hash": json_hash({"cases": cases, "gaps": gaps})})
    if not quiet:
        print(json.dumps(metrics, ensure_ascii=False, sort_keys=True))
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id")
    parser.add_argument("--selection-only", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--replay", action="store_true", help="split GraphAction from an existing projection; no API call")
    parser.add_argument("--refresh-baseline-hash", action="store_true", help="refresh schema input hash after offline schema replay; no API call")
    args = parser.parse_args()
    try:
        if args.replay:
            result = replay_projection()
        elif args.refresh_baseline_hash:
            result = refresh_baseline_hashes()
        else:
            result = run(run_id=args.run_id, selection_only=args.selection_only, quiet=args.quiet)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if args.selection_only:
        print(json.dumps({"selected_case_count": result.get("selected_case_count"), "actual_live_composition": result.get("actual_live_composition"), "fixture_coverage_count": len(result.get("fixture_coverage_cases", []))}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
