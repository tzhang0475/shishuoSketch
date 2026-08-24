#!/usr/bin/env python3
"""HNG2-SC offline replay and targeted live controller validation."""

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
import hng1_common  # noqa: E402
import historical_entity_resolver as resolver  # noqa: E402
import historical_entity_schema as schema  # noqa: E402
import hng2_schema_controller as controller  # noqa: E402
from hng0_1_common import stable_hash  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402


BASE = ROOT / "data/generated/hng2-schema"
SL = ROOT / "data/generated/hng2-schema-live"
REPLAY_OUT = ROOT / "data/generated/hng2-schema-controller-replay"
LIVE_OUT = ROOT / "data/generated/hng2-schema-controller-live"
MODEL = "deepseek-v4-flash"
PROVIDER = "deepseek"
RUN_SCHEMA = 1
PROMPT_VERSION = "hng2-sc-card-controller-v1"
SEARCH_PROMPT_VERSION = "hng2-sc-search-plan-v1"

SEMANTIC_SYSTEM = """你是历史实体 Schema v1 的结构化证据卡辅助器。
只根据输入正文、注释、候选人物和 Python 提供的 hard_constraints 理解当前文字。
先识别本段出现的实体，再把原文直接支持的身份、称谓、亲属、事件或时间断言填入 evidence_interpretation。
所有 entity_key 只能是本次回答内部的 e0/e1/...；不得创造 person_id、candidate_key、provisional_person_id、relation_id 或 graph_id。
chosen_candidate_key 只能使用输入中给定的候选键；新的可识别人物只能使用 new_entity_key=n0，不得写人物 ID。
不得修改 hard_constraints。summary 仅供人工审阅，Python 不会用它控制状态。
metatextual 引书作者不是叙事参与者或说话者，也不继承所述事件的个人时间。
严格返回一个 JSON 对象，顶层只能有：evidence_interpretation、semantic_assessment、identity_recommendation、research_gap。
semantic_assessment 和 identity_recommendation 必须是 JSON 对象，绝不能是字符串。请严格套用这个骨架，不要改字段类型：
{"evidence_interpretation":{"entities":[],"assertions":[]},"semantic_assessment":{"assessment_status":"assessed","semantic_fit":"unknown","observed_role":"unknown","evidence_spans":[],"summary":""},"identity_recommendation":{"decision":"unresolved","chosen_candidate_key":null,"confidence":"unknown","reason_codes":[],"evidence_spans":[],"new_entity_candidate":null,"new_entity_key":null,"unresolved_reason":"","summary":""},"research_gap":{"status":"open","missing_constraints":[],"blocking_question":"","next_best_action":"human_review","candidate_keys":[],"stop_condition":""}}
evidence_interpretation.entities 每项含 entity_key、surface、entity_kind、reference_form、evidence_ref、evidence_span；
assertions 每项含 assertion_id(a0/a1...)、assertion_type、subject_entity_key、可选 object_entity_key/value/direction、evidence_ref、evidence_span、confidence。
assertion_type 只能是 identity_equivalence、alias_of、courtesy_name_of、title_of、office_held_by、parent_child、sibling、kinship_relation、participates_in_event、temporal_statement、person_mention。
entity_kind 和 reference_form 必须逐字使用输入 contract 中的枚举值；例如 named_person/full_name，不得使用 person、surname_only、title_plus_surname 等自造值。
semantic_fit 只能使用 strong_support、support、compatible、weak、unknown、conflict；exact、full_match、title_only、match 等都无效。
semantic_assessment.evidence_spans 与 identity_recommendation.evidence_spans 必须是 {"ref":"给定 ref","span":"连续原文"} 对象数组，不能是字符串数组；若不需要可返回空数组。
identity_recommendation.decision 只能使用 choose_candidate、new_person_candidate、ambiguous、unresolved、not_a_single_person、not_a_person；resolved、new_entity、insufficient_evidence 等都无效。
semantic_assessment 使用固定枚举；identity_recommendation 使用固定枚举；research_gap 只报告模型观察，最终状态由 Python 重算。
所有 evidence_span 必须是给定 source_passages 中的连续原文。"""

SEARCH_SYSTEM = """你是历史实体 SearchPlan 规划器。只根据给定的 ResearchGap、候选和短正文材料制定一次本地检索计划，不回答历史问题，不扩展 frontier。
思考：缺少哪类证据、最可能出现在哪类本地史料、围绕哪些人物/亲属词/官职/事件/年代检索、需分别验证哪些候选、什么证据可停止。
严格只返回 json 对象：{"search_plan":{"target_constraint":"title_identity|kinship|temporal|biography_identity|short_name_identity","goal":"","candidate_keys":[],"preferred_sources":[],"search_entities":[],"search_patterns":[],"temporal_scope":{},"graph_neighborhood_scope":"case_only","stop_condition":""}}。
preferred_sources 只能从给定的本地来源中选择。"""


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def json_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _redact(value: Any) -> str:
    text = str(value or "")
    secret = os.environ.get("DEEPSEEK_API_KEY")
    return text.replace(secret, "[REDACTED]") if secret else text


def load_cases() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    cases_doc = read_json(BASE / "cases.json", {}) or {}
    gaps_doc = read_json(BASE / "research-gaps.json", {}) or {}
    cases = {str(row.get("case_id")): dict(row) for row in cases_doc.get("cases", []) if isinstance(row, Mapping) and row.get("case_id")}
    gaps = {str(row.get("case_id")): dict(row) for row in gaps_doc.get("gaps", []) if isinstance(row, Mapping) and row.get("case_id")}
    return cases, gaps


def load_evidence() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name in ("relations.json", "temporal-items.json"):
        document = read_json(ROOT / "data/generated/hng1r2" / name, {}) or {}
        for ref, row in (document.get("evidence") or {}).items():
            if isinstance(row, Mapping):
                result[str(ref)] = dict(row)
    return result


def load_source_map() -> dict[str, dict[str, Any]]:
    sources = load_evidence()
    for trace in (read_json(SL / "retrieval-trace.json", {}) or {}).get("traces", []):
        for row in trace.get("passages", []) if isinstance(trace, Mapping) else []:
            if isinstance(row, Mapping) and row.get("ref"):
                current = sources.get(str(row["ref"]), {})
                sources[str(row["ref"])] = {
                    **current, "ref": str(row["ref"]), "work": row.get("work") or current.get("source_work"),
                    "layer": row.get("layer") or current.get("source_layer"), "source_form": row.get("source_form") or "legacy_local",
                    "text": row.get("text") or current.get("model_snippet") or current.get("original_text") or "",
                    "original_text": row.get("original_text") or current.get("original_text") or row.get("text") or "",
                    "locator": row.get("locator") or current.get("locator") or {},
                }
    return sources


def passages_for_case(case_id: str, case: Mapping[str, Any], source_map: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    observation = case.get("observation") if isinstance(case.get("observation"), Mapping) else {}
    ref = _text(observation.get("source_ref"))
    if ref:
        row = source_map.get(ref, {})
        result[ref] = {"ref": ref, "work": row.get("source_work") or row.get("work") or observation.get("source_work"), "layer": row.get("source_layer") or row.get("layer"), "source_form": row.get("source_form") or "legacy_local", "text": row.get("original_text") or row.get("model_snippet") or row.get("text") or observation.get("exact_span") or "", "original_text": row.get("original_text") or row.get("model_snippet") or row.get("text") or ""}
    for trace in (read_json(SL / "retrieval-trace.json", {}) or {}).get("traces", []):
        if str(trace.get("case_id")) != str(case_id):
            continue
        for row in trace.get("passages", []):
            if isinstance(row, Mapping) and row.get("ref"):
                result[str(row["ref"])] = {key: row.get(key) for key in ("ref", "work", "layer", "source_form", "text", "original_text", "locator")}
    return result


def normalize_target_interpretation(case: Mapping[str, Any], source_text: str, catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]]) -> dict[str, Any]:
    """Correct context-only kinship leakage without a person-specific rule."""

    raw = dict(case.get("interpretation") or {})
    surface = _text((case.get("observation") or {}).get("surface"))
    folded = resolver.matching_normalize(surface)
    kinship_markers = ("父", "母", "兄", "弟", "子", "女", "祖", "孫", "叔", "舅", "婿", "妻", "從")
    if raw.get("entity_kind") == "structural_kinship_expression" and len(folded) >= 2 and not any(marker in surface for marker in kinship_markers):
        raw.update({"entity_kind": "named_person", "reference_form": "full_name", "mention_scope": "narrative", "discourse_role": "referenced_person", "structural_kinship": None, "summary": "target full-name mention; nearby kinship context is not the target"})
    return raw


def build_selection() -> dict[str, Any]:
    cases, gaps = load_cases()
    source_map = load_source_map()
    open_rows = []
    for case_id, gap in gaps.items():
        case = cases.get(case_id)
        if not case or gap.get("status") != "open":
            continue
        observation = case.get("observation") or {}
        interpretation = normalize_target_interpretation(case, _text((source_map.get(_text(observation.get("source_ref"))) or {}).get("original_text")), hng02.person_catalog(), hng02.forms_index(hng02.person_catalog()))
        kind = _text(interpretation.get("entity_kind"))
        surface = _text(observation.get("surface"))
        temporal_signal = any(str(row.get("constraint_type")) == "temporal" and str(row.get("status")) in {"unknown", "conflict"} for row in case.get("constraint_checks", []) if isinstance(row, Mapping))
        if kind in {"person_title", "person_office_title"} and case.get("candidates"):
            category = "title_known"
        elif temporal_signal:
            category = "temporal"
        elif kind in {"person_title", "person_office_title"}:
            category = "title_office"
        elif kind == "structural_kinship_expression":
            category = "kinship_structural"
        elif kind in {"abbreviated_name", "courtesy_name"} or len(resolver.matching_normalize(surface)) <= 1:
            category = "short_name"
        elif kind == "named_person" and len(resolver.matching_normalize(surface)) >= 2:
            category = "new_named_person"
        elif "temporal" in [str(x) for x in gap.get("missing_constraints", [])]:
            category = "temporal"
        else:
            category = "unresolved"
        open_rows.append({"case_id": case_id, "category": category, "selection_key": stable_hash({"stage": "hng2-sc", "case_id": case_id}), "surface": surface, "source_ref": observation.get("source_ref"), "gap": gap, "interpretation": interpretation})
    groups = collections.defaultdict(list)
    for row in open_rows:
        groups[row["category"]].append(row)
    for rows in groups.values():
        rows.sort(key=lambda row: row["selection_key"])
    # The categories are selected from the frozen open-gap inventory, not from
    # newly discovered nodes.  This is a deterministic targeted validation set.
    targets = [("title_known", 1), ("title_office", 1), ("short_name", 1), ("kinship_structural", 1), ("new_named_person", 1), ("temporal", 1), ("unresolved", 1)]
    selected: list[dict[str, Any]] = []
    for category, count in targets:
        selected.extend(groups.get(category, [])[:count])
    if len(selected) < 6:
        for row in sorted(open_rows, key=lambda item: item["selection_key"]):
            if row not in selected:
                selected.append(row)
            if len(selected) >= 6:
                break
    selected = sorted(selected[:8], key=lambda row: row["selection_key"])
    return {
        "stage": "hng2-schema-controller-live", "schema": schema.SCHEMA_VERSION, "selection_version": "hng2-sc-selection-v1",
        "frozen": True, "selected_case_count": len(selected), "no_frontier_expansion": True, "canonical_write_back": False,
        "base_projection_hash": hash_tree(BASE), "cases": selected, "target_categories": dict(targets),
        "available_categories": {key: len(value) for key, value in sorted(groups.items())},
    }


def _compact_passages(passages: Mapping[str, Mapping[str, Any]], limit: int = 4, anchor: str = "") -> list[dict[str, Any]]:
    rows = []
    for ref, row in sorted(passages.items()):
        text = _text(row.get("text"))
        if len(text) > 900:
            center = text.find(anchor) if anchor else -1
            if center >= 0:
                start = max(0, center - 420)
                text = text[start:start + 900]
            else:
                text = text[:900]
        rows.append({"ref": ref, "work": row.get("work"), "layer": row.get("layer"), "source_form": row.get("source_form"), "supplied_text": text})
    return rows[:limit]


def semantic_packet(case: Mapping[str, Any], gap: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]], constraints: Sequence[Mapping[str, Any]], passages: Mapping[str, Mapping[str, Any]], round_no: int) -> dict[str, Any]:
    interpretation = normalize_target_interpretation(case, "\n".join(_text(row.get("text")) for row in passages.values()), hng02.person_catalog(), hng02.forms_index(hng02.person_catalog()))
    return {
        "case": {"case_id": case.get("case_id"), "surface": (case.get("observation") or {}).get("surface"), "exact_span": (case.get("observation") or {}).get("exact_span"), "source_work": (case.get("observation") or {}).get("source_work"), "interpretation": {key: interpretation.get(key) for key in ("entity_kind", "reference_form", "mention_scope", "discourse_role", "summary")}},
        "research_gap": {key: gap.get(key) for key in ("status", "missing_constraints", "blocking_question", "next_best_action", "candidate_keys", "stop_condition")},
        "candidates": [{key: row.get(key) for key in ("candidate_key", "canonical_name", "known_forms", "chronology_summary", "graph_summary")} for row in candidates],
        "hard_constraints": [dict(row) for row in constraints],
        "source_passages": _compact_passages(passages, anchor=_text((case.get("observation") or {}).get("surface")) or _text((case.get("observation") or {}).get("exact_span"))),
        "semantic_questions": list(schema.CHINESE_SEMANTIC_ASSIST_QUESTIONS),
        "round": round_no,
    }


def search_packet(case: Mapping[str, Any], gap: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]], passages: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return {"research_gap": {key: gap.get(key) for key in ("status", "missing_constraints", "blocking_question", "next_best_action", "candidate_keys", "stop_condition")}, "mention": {"surface": (case.get("observation") or {}).get("surface"), "source_work": (case.get("observation") or {}).get("source_work")}, "candidates": [{key: row.get(key) for key in ("candidate_key", "canonical_name", "known_forms")} for row in candidates], "source_passages": _compact_passages(passages, 2), "planning_questions": list(schema.CHINESE_SEARCH_PLAN_QUESTIONS)}


def _usage(response: Mapping[str, Any]) -> dict[str, int]:
    usage = response.get("usage") if isinstance(response, Mapping) else {}
    usage = usage if isinstance(usage, Mapping) else {}
    return {key: int(usage.get(key) or 0) for key in ("prompt_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens", "total_tokens")}


def call_record(kind: str, case_id: str, payload: Mapping[str, Any], system: str, raw_dir: Path, sequence: int) -> dict[str, Any]:
    begin = time.monotonic()
    record: dict[str, Any] = {"kind": kind, "case_id": case_id, "sequence": sequence, "start_time": utc_now(), "model": MODEL, "provider": PROVIDER, "prompt_version": PROMPT_VERSION if kind == "semantic" else SEARCH_PROMPT_VERSION, "input_hash": json_hash(payload), "canonical_write_back": False, "immutable": True}
    try:
        response = call_deepseek([{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)}], model=MODEL, temperature=0, response_format={"type": "json_object"}, tools=[], thinking={"type": "disabled"}, max_tokens=1600 if kind == "semantic" else 700, timeout=180)
        record.update({"status": "response", "response": response, "usage": _usage(response)})
        parsed, channel, error = controller.extract_response_payload(response)
        record.update({"response_channel": channel, "parse_error": error, "parsed": parsed})
    except Exception as exc:  # preserve transport failures without secrets
        provider_body = _redact(getattr(exc, "provider_error_body", ""))
        provider_error = {}
        try:
            provider_error = json.loads(provider_body) if provider_body else {}
        except json.JSONDecodeError:
            provider_error = {}
        error_obj = provider_error.get("error") if isinstance(provider_error, Mapping) else {}
        http_status = getattr(exc, "http_status", None)
        if http_status == 429:
            status = "provider_rate_limited"
        elif isinstance(http_status, int) and 400 <= http_status < 500:
            status = "provider_request_rejected"
        else:
            status = "transport_failure"
        record.update({"status": status, "response": None, "usage": {}, "response_channel": "none", "parse_error": type(exc).__name__, "exception_class": type(exc).__name__, "exception_message": _redact(exc), "http_status": http_status, "provider_error_code": error_obj.get("code") if isinstance(error_obj, Mapping) else None, "provider_error_message": error_obj.get("message") if isinstance(error_obj, Mapping) else (provider_body[:500] if provider_body else "")})
    record["elapsed_seconds"] = round(time.monotonic() - begin, 6)
    write_json(raw_dir / f"{sequence:03d}-{kind}-{case_id}.json", record)
    return record


def _source_profile(case: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    observation = case.get("observation") or {}
    return {"person_id": f"case:{case.get('case_id')}", "canonical_name": _text(observation.get("surface")), "search_terms_original": sorted(set([_text(x) for x in [*(plan.get("search_entities") or []), *(plan.get("search_patterns") or [])] if _text(x)]), key=lambda item: (-len(resolver.matching_normalize(item)), item))}


def retrieve(case: Mapping[str, Any], plan: Mapping[str, Any], passages: Mapping[str, Mapping[str, Any]], punctuated: Sequence[Mapping[str, Any]], legacy: Sequence[Mapping[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    found = hng1_common.find_punctuated_first(_source_profile(case, plan), punctuated, legacy, top_k=6)
    opened = hng1_common.open_short_hits(found, punctuated, legacy, max_passages=4)
    original_ref = _text((case.get("observation") or {}).get("source_ref"))
    rows: dict[str, dict[str, Any]] = {}
    for row in opened:
        ref = _text(row.get("source_ref"))
        if not ref or ref == original_ref:
            continue
        rows[ref] = {"ref": ref, "work": row.get("work"), "layer": row.get("layer"), "source_form": row.get("source_form") or "legacy_local", "text": row.get("text") or "", "original_text": row.get("original_text") or row.get("text") or "", "locator": row.get("locator") or {}}
    combined = {**passages, **rows}
    return combined, {"retrieved_refs": [str(x) for x in found.get("refs", [])], "opened_refs": sorted(rows), "used_refs": [], "new_used_refs": [], "opened_chars": sum(len(_text(row.get("text"))) for row in rows.values()), "source_forms": sorted(set(_text(row.get("source_form")) for row in rows.values())), "searched_corpora": sorted(set(_text(row.get("work")) for row in rows.values())), "passages": list(rows.values())}


def _fixture_payload(kind: str, ref: str, span: str, source_text: str, candidate: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if kind == "structural":
        entity_kind, reference, role, decision, fit = "structural_kinship_expression", "kinship_plus_name", "kinship_node", "not_a_single_person", "strong_support"
        assertion_type = "kinship_relation"
    elif kind == "metatext":
        entity_kind, reference, role, decision, fit = "named_person", "full_name", "cited_author", "choose_candidate", "strong_support"
        assertion_type = "person_mention"
    elif kind == "title":
        entity_kind, reference, role, decision, fit = "person_office_title", "office_title_only", "office_holder", "choose_candidate" if candidate else "ambiguous", "support"
        assertion_type = "title_of"
    elif kind == "new":
        entity_kind, reference, role, decision, fit = "named_person", "full_name", "referenced_person", "new_person_candidate", "support"
        assertion_type = "person_mention"
    elif kind == "unresolved":
        entity_kind, reference, role, decision, fit = "abbreviated_name", "abbreviated", "referenced_person", "unresolved", "unknown"
        assertion_type = "person_mention"
    else:
        entity_kind, reference, role, decision, fit = "person_title", "title_only", "office_holder", "ambiguous", "unknown"
        assertion_type = "title_of"
    entity = {"entity_key": "e0", "surface": span, "entity_kind": entity_kind, "reference_form": reference, "evidence_ref": ref, "evidence_span": span}
    assertion = {"assertion_id": "a0", "assertion_type": assertion_type, "subject_entity_key": "e0", "value": None, "direction": None, "evidence_ref": ref, "evidence_span": span, "confidence": "high" if decision in {"not_a_single_person", "choose_candidate"} else "medium"}
    rec: dict[str, Any] = {"decision": decision, "chosen_candidate_key": candidate.get("candidate_key") if candidate and decision == "choose_candidate" else None, "confidence": "high" if decision == "not_a_single_person" else "medium", "reason_codes": ["offline_fixture"], "evidence_spans": [{"ref": ref, "span": span}], "new_entity_candidate": {"surface": span} if decision == "new_person_candidate" else None, "new_entity_key": "n0" if decision == "new_person_candidate" else None, "unresolved_reason": "fixture leaves identity open" if decision in {"ambiguous", "unresolved"} else "", "summary": "fixture"}
    return {"evidence_interpretation": {"entities": [entity], "assertions": [assertion], "summary": "fixture"}, "semantic_assessment": {"assessment_status": "assessed", "semantic_fit": fit, "observed_role": role, "evidence_spans": [{"ref": ref, "span": span}], "summary": "fixture"}, "identity_recommendation": rec, "research_gap": {"status": "open" if decision in {"ambiguous", "unresolved"} else "closed", "missing_constraints": ["identity_evidence"] if decision in {"ambiguous", "unresolved"} else [], "blocking_question": "fixture open" if decision in {"ambiguous", "unresolved"} else "", "next_best_action": "human_review" if decision == "ambiguous" else "search_biography_context" if decision == "unresolved" else "none", "candidate_keys": [candidate.get("candidate_key")] if candidate else [], "stop_condition": "fixture"}}


def fixture_cases(cases: Mapping[str, Mapping[str, Any]], source_map: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_label = {str(row.get("case_id")): row for row in (read_json(BASE / "validation-cases.json", {}) or {}).get("regression_case_records", []) if isinstance(row, Mapping)}
    result: list[dict[str, Any]] = []
    specs = [
        ("regression-mount-tao", "title", "山濤"),
        ("regression-yu-taiwei", "title", "庾太尉"),
        ("regression-title-wendi", "title", "文帝"),
        ("regression-structural-kinship", "structural", "喜弟預女"),
        ("regression-metatext-yuanhong", "metatext", "袁宏《紀》"),
        ("hng1r2-hng1-raw-relation-b97bdeb3fbec092978bc", "new", "虞喜"),
        ("hng1r2-hng1-raw-relation-1153a723032c48422396", "unresolved", "宣"),
    ]
    # A fresh named surface is the deterministic new-person transition case.
    for case_id, kind, span in specs:
        row = by_label.get(case_id) or cases.get(case_id)
        if not row:
            continue
        ref = _text((row.get("observation") or {}).get("source_ref"))
        text = _text((source_map.get(ref) or {}).get("original_text")) or span
        if span not in text:
            text = span
        passages = {ref: {"ref": ref, "text": text, "work": (row.get("observation") or {}).get("source_work")}}
        candidate = (row.get("candidates") or [None])[0] if kind in {"title", "metatext"} else None
        payload = _fixture_payload(kind, ref, span, text, candidate)
        if case_id == "regression-mount-tao":
            payload["evidence_interpretation"]["entities"][0].update({"surface": "山濤", "entity_kind": "named_person", "reference_form": "full_name"})
            payload["identity_recommendation"].update({"decision": "choose_candidate", "chosen_candidate_key": "c0", "confidence": "high"})
        result.append({"fixture_id": case_id, "case": row, "payload": payload, "passages": passages})
    # The historical ``譽`` case exercises fail-closed validation: a model
    # may not attach a new-entity key to an ambiguous recommendation.
    yuyi = next((row for row in (read_json(BASE / "cases.json", {}) or {}).get("cases", []) if row.get("case_id") == "hng2-hng02-relation-53df6f655bff9d79d0c5"), None)
    if yuyi:
        ref = _text((yuyi.get("observation") or {}).get("source_ref"))
        text = _text((source_map.get(ref) or {}).get("original_text")) or "譽"
        bad = _fixture_payload("unresolved", ref, "譽", text)
        bad["identity_recommendation"].update({"decision": "ambiguous", "new_entity_key": "n9"})
        result.append({"fixture_id": "fixture-invalid-new-key-ambiguous", "case": yuyi, "payload": bad, "passages": {ref: {"ref": ref, "text": text, "work": (yuyi.get("observation") or {}).get("source_work")}}})
    # The full local passage used in Jinshu 帝紀 supplies the title/name
    # equivalence required for the 武皇帝諱炎 regression.
    wu_path = ROOT / "content/processed/jinshu/units/benji/003-benji-001.md"
    wu_text = wu_path.read_text(encoding="utf-8") if wu_path.is_file() else "武皇帝諱炎，字安世，文帝長子也"
    wu_span = "武皇帝諱炎"
    wu_ref = "fixture-jinshu-benji-003"
    wu_case = {"case_id": "fixture-wu-emperor", "observation": {"surface": wu_span, "exact_span": wu_span, "source_ref": wu_ref, "source_work": "晉書"}, "interpretation": {"mention_scope": "narrative"}, "candidates": [], "research_gap": {"status": "open", "missing_constraints": ["title_identity"], "next_best_action": "search_title_identity", "blocking_question": "which name does this title identify"}}
    wu_payload = _fixture_payload("new", wu_ref, wu_span, wu_text)
    wu_payload["evidence_interpretation"]["entities"].append({"entity_key": "e1", "surface": "炎", "entity_kind": "named_person", "reference_form": "full_name", "evidence_ref": wu_ref, "evidence_span": "諱炎"})
    wu_payload["evidence_interpretation"]["assertions"].append({"assertion_id": "a1", "assertion_type": "identity_equivalence", "subject_entity_key": "e0", "object_entity_key": "e1", "value": None, "direction": None, "evidence_ref": wu_ref, "evidence_span": "武皇帝諱炎", "confidence": "high"})
    result.append({"fixture_id": "fixture-wu-emperor", "case": wu_case, "payload": wu_payload, "passages": {wu_ref: {"ref": wu_ref, "text": wu_text, "work": "晉書"}}})
    return result


def process_card(case: Mapping[str, Any], payload: Mapping[str, Any], passages: Mapping[str, Mapping[str, Any]], candidates: Sequence[Mapping[str, Any]], constraints: Sequence[Mapping[str, Any]], refs: Sequence[str], catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]]) -> tuple[dict[str, Any], dict[str, Any]]:
    validation = controller.validate_card_payload(payload, case, passages, candidate_rows=candidates)
    if not validation["valid"]:
        return validation, {"card": None, "candidates": [dict(row) for row in candidates], "constraints": [dict(row) for row in constraints], "research_gap": dict(case.get("research_gap") or {"status": "open", "missing_constraints": ["semantic_validation"], "next_best_action": "human_review"}), "state_delta": {"new_evidence": [], "new_candidates": [], "changed_constraints": [], "removed_conflicts": [], "new_conflicts": [], "material": False}}
    projection = controller.project_valid_card(case, payload, passages, candidates, constraints, refs, catalog, index)
    return validation, projection


def replay_raw() -> dict[str, Any]:
    cases, gaps = load_cases()
    sources = load_source_map()
    catalog = hng02.person_catalog()
    index = hng02.forms_index(catalog)
    run_id = _text((read_json(SL / "manifest.json", {}) or {}).get("run_id"))
    raw_dir = SL / "raw-api" / run_id
    raw_records = []
    for path in sorted(raw_dir.glob("*-semantic-*.json")):
        record = read_json(path, {}) or {}
        payload, channel, error = controller.extract_response_payload(record.get("response") or {})
        case = cases.get(str(record.get("case_id")), {"case_id": record.get("case_id"), "candidates": [], "research_gap": {"status": "open"}, "observation": {}})
        passages = passages_for_case(str(record.get("case_id")), case, sources)
        validation = controller.validate_card_payload(payload, case, passages) if payload is not None else {"valid": False, "errors": [error or "no_payload"], "invalid_enum_outputs": [], "invented_id_attempts": [], "evidence_span_failures": 0}
        raw_records.append({"path": str(path.relative_to(ROOT)), "case_id": record.get("case_id"), "sequence": record.get("sequence"), "response_channel": channel, "parse_error": error, "card_valid": validation.get("valid", False), "validation": validation, "payload_present": payload is not None})
    fixtures: list[dict[str, Any]] = []
    for fixture in fixture_cases(cases, sources):
        case = fixture["case"]
        case = {**case, "interpretation": normalize_target_interpretation(case, "\n".join(_text(x.get("text")) for x in fixture["passages"].values()), catalog, index)}
        validation, projection = process_card(case, fixture["payload"], fixture["passages"], case.get("candidates", []), case.get("constraint_checks", []), [], catalog, index)
        fixtures.append({"fixture_id": fixture["fixture_id"], "valid": validation.get("valid", False), "validation": validation, "projection": projection, "payload": fixture["payload"], "case": case})
    metrics = summarize(raw_records, fixtures, [], [])
    metrics.update({"stage": "hng2-schema-controller-replay", "api_calls": 0, "canonical_write_back": False, "no_frontier_expansion": True})
    output = {"schema": schema.SCHEMA_VERSION, "stage": "hng2-schema-controller-replay", "raw_records": raw_records, "fixtures": fixtures, "metrics": metrics, "canonical_write_back": False}
    REPLAY_OUT.mkdir(parents=True, exist_ok=True)
    write_json(REPLAY_OUT / "replay-results.json", output)
    write_projection(REPLAY_OUT, raw_records, fixtures, metrics, "offline-replay", 0)
    return output


def summarize(raw_records: Sequence[Mapping[str, Any]], fixtures: Sequence[Mapping[str, Any]], case_runs: Sequence[Mapping[str, Any]], usage: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    valid_cards = sum(bool(row.get("card_valid")) for row in raw_records) + sum(bool(row.get("valid")) for row in fixtures)
    channels = collections.Counter(str(row.get("response_channel") or "none") for row in raw_records)
    errors = collections.Counter(error for row in raw_records for error in row.get("validation", {}).get("errors", []))
    semantic_calls = sum(1 for row in usage if row.get("kind") == "semantic")
    search_calls = sum(1 for row in usage if row.get("kind") == "search-plan")
    total = {key: sum(int(row.get("usage", {}).get(key) or 0) for row in usage) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    latency = [float(row.get("elapsed_seconds")) for row in usage if row.get("status") == "response" and row.get("elapsed_seconds") is not None]
    transitions = [row for run in case_runs for row in run.get("rounds", []) if isinstance(row, Mapping)]
    return {
        "raw_response_count": len(raw_records), "cards_returned": sum(bool(row.get("payload_present")) for row in raw_records) + sum(bool(row.get("valid")) for row in fixtures), "cards_valid": valid_cards,
        "cards_rejected": len(raw_records) - sum(bool(row.get("card_valid")) for row in raw_records) + sum(not bool(row.get("valid")) for row in fixtures),
        "response_channels": dict(sorted(channels.items())), "validation_error_counts": dict(errors),
        "semantic_calls": semantic_calls, "search_plan_calls": search_calls,
        "candidate_additions": sum(len(row.get("projection", {}).get("state_delta", {}).get("new_candidates", [])) for row in fixtures) + sum(len(row.get("state_delta", {}).get("new_candidates", [])) for row in transitions),
        "constraint_additions": sum(len(row.get("projection", {}).get("constraints", [])) for row in fixtures) + sum(len(row.get("constraints", [])) for row in transitions),
        "gaps_closed": sum(row.get("projection", {}).get("research_gap", {}).get("status") == "closed" for row in fixtures) + sum(row.get("research_gap", {}).get("status") == "closed" for row in transitions),
        "total_usage": total, "median_latency_seconds": statistics.median(latency) if latency else 0, "max_latency_seconds": max(latency) if latency else 0,
    }


def write_projection(out: Path, raw_records: Sequence[Mapping[str, Any]], fixtures: Sequence[Mapping[str, Any]], metrics: Mapping[str, Any], stage: str, api_calls: int) -> None:
    valid_rows = [row for row in fixtures if row.get("valid")]
    assessments = []
    recommendations = []
    decisions = []
    actions = []
    gaps = []
    cards = []
    candidates = []
    constraints = []
    deltas = []
    for row in valid_rows:
        projection = row.get("projection") or {}
        payload = (row.get("payload") or {}) if isinstance(row.get("payload"), Mapping) else {}
        case_id = row.get("fixture_id")
        cards.append({"case_id": case_id, "card": projection.get("card"), "canonical_write_back": False})
        assessments.append({"case_id": case_id, **dict(payload.get("semantic_assessment") or {}), "canonical_write_back": False})
        recommendations.append({"case_id": case_id, **dict(payload.get("identity_recommendation") or {}), "canonical_write_back": False})
        decisions.append({"case_id": case_id, **dict(projection.get("identity_decision") or {}), "canonical_write_back": False})
        actions.append({"case_id": case_id, **dict(projection.get("graph_action") or {}), "canonical_write_back": False})
        gaps.append({"case_id": case_id, **dict(projection.get("research_gap") or {}), "canonical_write_back": False})
        candidates.append({"case_id": case_id, "candidates": projection.get("candidates", []), "delta": projection.get("state_delta", {}), "canonical_write_back": False})
        constraints.append({"case_id": case_id, "constraints": projection.get("constraints", []), "canonical_write_back": False})
        deltas.append({"case_id": case_id, **dict(projection.get("state_delta") or {}), "canonical_write_back": False})
    write_json(out / "evidence-cards.json", {"schema": schema.SCHEMA_VERSION, "cards": cards, "canonical_write_back": False})
    write_json(out / "semantic-assessments.json", {"schema": schema.SCHEMA_VERSION, "assessments": assessments, "canonical_write_back": False})
    write_json(out / "identity-recommendations.json", {"schema": schema.SCHEMA_VERSION, "recommendations": recommendations, "canonical_write_back": False})
    write_json(out / "identity-decisions.json", {"schema": schema.SCHEMA_VERSION, "decisions": decisions, "canonical_write_back": False})
    write_json(out / "graph-actions.json", {"schema": schema.SCHEMA_VERSION, "actions": actions, "canonical_write_back": False})
    write_json(out / "research-gaps.json", {"schema": schema.SCHEMA_VERSION, "gaps": gaps, "canonical_write_back": False})
    write_json(out / "candidate-deltas.json", {"schema": schema.SCHEMA_VERSION, "candidates": candidates, "canonical_write_back": False})
    write_json(out / "constraint-updates.json", {"schema": schema.SCHEMA_VERSION, "constraints": constraints, "canonical_write_back": False})
    write_json(out / "state-deltas.json", {"schema": schema.SCHEMA_VERSION, "deltas": deltas, "canonical_write_back": False})
    manifest = {"schema": schema.SCHEMA_VERSION, "stage": stage, "api_calls": api_calls, "model": {"provider": PROVIDER, "model": MODEL, "api_calls": api_calls}, "canonical_write_back": False, "no_frontier_expansion": True, "base_projection_hash": hash_tree(BASE), "controller_module": "scripts/hng2_schema_controller.py"}
    write_json(out / "manifest.json", manifest)
    write_json(out / "metrics.json", {**dict(metrics), "stage": stage, "canonical_write_back": False, "no_frontier_expansion": True})


def _search_plan_from_response(payload: Any, case: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(payload, Mapping) or not isinstance(payload.get("search_plan"), Mapping):
        return None, ["missing_search_plan"]
    plan = dict(payload["search_plan"])
    allowed = {"target_constraint", "goal", "candidate_keys", "preferred_sources", "search_entities", "search_patterns", "temporal_scope", "graph_neighborhood_scope", "stop_condition"}
    errors = [f"unknown_field:{key}" for key in set(plan) - allowed]
    if plan.get("target_constraint") not in {"title_identity", "kinship", "temporal", "biography_identity", "short_name_identity"}:
        errors.append("invalid_target_constraint")
    keys = {str(row.get("candidate_key")) for row in candidates if row.get("candidate_key")}
    if not isinstance(plan.get("candidate_keys"), list) or any(str(key) not in keys for key in plan.get("candidate_keys", [])):
        errors.append("unknown_candidate_key")
    if plan.get("graph_neighborhood_scope") != "case_only":
        errors.append("frontier_expansion")
    approved = {"世說新語", "劉孝標注", "余嘉錫笺疏", "晉書", "三國志", "資治通鑑", "資治通鑑考異", "local source corpus"}
    if not isinstance(plan.get("preferred_sources"), list) or any(str(source) not in approved for source in plan.get("preferred_sources", [])):
        errors.append("unapproved_source")
    for key in ("goal", "stop_condition"):
        if not _text(plan.get(key)):
            errors.append(f"empty_{key}")
    if not isinstance(plan.get("preferred_sources"), list) or not plan.get("preferred_sources"):
        errors.append("missing_preferred_sources")
    for key in ("search_entities", "search_patterns"):
        if not isinstance(plan.get(key), list) or not all(_text(x) for x in plan.get(key, [])):
            errors.append(f"invalid_{key}")
    return (plan if not errors else None), sorted(set(errors))


def run_live(selection: Mapping[str, Any], run_id: str) -> dict[str, Any]:
    preflight_payload = {"research_gap": {"status": "open", "missing_constraints": ["title_identity"], "blocking_question": "choose a local identity source", "next_best_action": "search_title_identity", "candidate_keys": ["c0"], "stop_condition": "return a valid local plan"}, "candidates": [{"candidate_key": "c0", "canonical_name": "庾亮", "known_forms": ["庾公"]}], "source_passages": [{"ref": "preflight-ref", "work": "晉書", "layer": "main", "source_form": "punctuated", "supplied_text": "庾太尉"}], "planning_questions": list(schema.CHINESE_SEARCH_PLAN_QUESTIONS)}
    preflight = call_record("search-plan-preflight", "preflight", preflight_payload, SEARCH_SYSTEM, LIVE_OUT / "raw-api" / run_id, 1)
    preflight_plan, preflight_errors = _search_plan_from_response(preflight.get("parsed"), {"candidates": preflight_payload["candidates"]}, preflight_payload["candidates"]) if preflight.get("status") == "response" else (None, [preflight.get("parse_error") or "no_response"])
    preflight["validation_errors"] = preflight_errors
    preflight["validated"] = preflight_plan is not None
    write_json(LIVE_OUT / "raw-api" / run_id / "001-search-plan-preflight-validation.json", {"case_id": "preflight", "validated": preflight_plan is not None, "validation_errors": preflight_errors, "canonical_write_back": False})
    preflight_ok = preflight.get("status") == "response" and preflight_plan is not None
    write_json(Path("/tmp/hng2-schema-controller-preflight.json"), {key: value for key, value in preflight.items() if key not in {"response", "parsed"}})
    if not preflight_ok:
        raise RuntimeError("live_network_or_search_plan_preflight_failed")
    punctuated, legacy = hng1_common.load_retrieval_sources()
    sources = load_source_map()
    catalog = hng02.person_catalog()
    index = hng02.forms_index(catalog)
    cases, gaps = load_cases()
    usage = [preflight]
    case_runs = []
    validation_rows = []
    search_plans = []
    retrieval_rows = []
    all_cards = []
    for selected in selection.get("cases", []):
        case_id = str(selected["case_id"])
        case = dict(cases[case_id])
        source_passages = passages_for_case(case_id, case, sources)
        interpretation = normalize_target_interpretation(case, "\n".join(_text(row.get("text")) for row in source_passages.values()), catalog, index)
        case["interpretation"] = interpretation
        candidates = [dict(row) for row in case.get("candidates", []) if isinstance(row, Mapping)]
        constraints = [dict(row) for row in case.get("constraint_checks", []) if isinstance(row, Mapping)]
        gap = dict(gaps[case_id])
        refs = list(source_passages)
        rounds: list[dict[str, Any]] = []
        packet = semantic_packet(case, gap, candidates, constraints, source_passages, 1)
        rec = call_record("semantic", case_id, packet, SEMANTIC_SYSTEM, LIVE_OUT / "raw-api" / run_id, len(usage) + 1)
        usage.append(rec)
        payload, channel, parse_error = controller.extract_response_payload(rec.get("response") or {}) if rec.get("response") else (None, "none", rec.get("parse_error"))
        validation, projection = process_card(case, payload, source_passages, candidates, constraints, refs, catalog, index) if payload is not None else ({"valid": False, "errors": [parse_error or "no_payload"], "invalid_enum_outputs": [], "invented_id_attempts": [], "evidence_span_failures": 0}, {"card": None, "candidates": candidates, "constraints": constraints, "research_gap": gap, "state_delta": {"material": False}})
        validation_rows.append({"case_id": case_id, "round": 1, "response_channel": channel, "valid": validation.get("valid", False), "errors": validation.get("errors", []), "invalid_enum_outputs": validation.get("invalid_enum_outputs", []), "invented_id_attempts": validation.get("invented_id_attempts", []), "evidence_span_failures": validation.get("evidence_span_failures", 0)})
        rounds.append({"round": 1, "response_channel": channel, "validation": validation, **projection})
        all_cards.append({"case_id": case_id, "round": 1, "payload": payload, "validation": validation})
        if not validation.get("valid"):
            case_runs.append({"case_id": case_id, "rounds": rounds, "final": {"status": "open", "reason": "invalid_card"}})
            continue
        candidates = projection["candidates"]
        constraints = projection["constraints"]
        gap = projection["research_gap"]
        refs = projection["supporting_refs"]
        if gap.get("status") != "open" or not projection["state_delta"].get("material"):
            case_runs.append({"case_id": case_id, "rounds": rounds, "final": {"status": gap.get("status"), "reason": "card_closed_or_no_state_delta"}})
            continue
        search_payload = search_packet(case, gap, candidates, source_passages)
        search_rec = call_record("search-plan", case_id, search_payload, SEARCH_SYSTEM, LIVE_OUT / "raw-api" / run_id, len(usage) + 1)
        usage.append(search_rec)
        search_payload_out, search_channel, search_error = controller.extract_response_payload(search_rec.get("response") or {}) if search_rec.get("response") else (None, "none", search_rec.get("parse_error"))
        plan, plan_errors = _search_plan_from_response(search_payload_out, case, candidates)
        if plan is None:
            plan = controller.typed_fallback_search_plan(case, gap, candidates)
            plan_errors = [*plan_errors, "typed_fallback_used"]
        search_plans.append({"case_id": case_id, "round": 1, "plan": plan, "validation_errors": plan_errors, "response_channel": search_channel, "canonical_write_back": False})
        retrieved, trace = retrieve(case, plan, source_passages, punctuated, legacy)
        # The first card's evidence is already used; only newly retrieved refs
        # enter the second card packet as possible new evidence.
        trace["used_refs"] = sorted(set(refs) & set(retrieved))
        trace["new_used_refs"] = sorted(set(trace["used_refs"]) - set(refs))
        retrieval_rows.append({"case_id": case_id, "round": 1, **trace, "canonical_write_back": False})
        packet2 = semantic_packet(case, gap, candidates, constraints, retrieved, 2)
        rec2 = call_record("semantic", case_id, packet2, SEMANTIC_SYSTEM, LIVE_OUT / "raw-api" / run_id, len(usage) + 1)
        usage.append(rec2)
        payload2, channel2, parse_error2 = controller.extract_response_payload(rec2.get("response") or {}) if rec2.get("response") else (None, "none", rec2.get("parse_error"))
        validation2, projection2 = process_card(case, payload2, retrieved, candidates, constraints, refs, catalog, index) if payload2 is not None else ({"valid": False, "errors": [parse_error2 or "no_payload"], "invalid_enum_outputs": [], "invented_id_attempts": [], "evidence_span_failures": 0}, {"card": None, "candidates": candidates, "constraints": constraints, "research_gap": gap, "state_delta": {"material": False}})
        validation_rows.append({"case_id": case_id, "round": 2, "response_channel": channel2, "valid": validation2.get("valid", False), "errors": validation2.get("errors", []), "invalid_enum_outputs": validation2.get("invalid_enum_outputs", []), "invented_id_attempts": validation2.get("invented_id_attempts", []), "evidence_span_failures": validation2.get("evidence_span_failures", 0)})
        rounds.append({"round": 2, "response_channel": channel2, "validation": validation2, **projection2})
        all_cards.append({"case_id": case_id, "round": 2, "payload": payload2, "validation": validation2})
        final = projection2.get("research_gap", gap) if validation2.get("valid") else {**gap, "status": "open"}
        case_runs.append({"case_id": case_id, "rounds": rounds, "final": final})
    metrics = summarize([], [], case_runs, usage)
    response_rows = [row for row in usage if row.get("status") == "response"]
    response_channels = collections.Counter(str(row.get("response_channel") or "none") for row in response_rows)
    validation_errors = collections.Counter(error for row in validation_rows for error in row.get("errors", []))
    metrics.update({"stage": "hng2-schema-controller-live", "selected_cases": len(selection.get("cases", [])), "cards_returned": sum(row.get("payload") is not None for row in all_cards), "cards_valid": sum(row.get("validation", {}).get("valid", False) for row in all_cards), "cards_rejected": sum(not row.get("validation", {}).get("valid", False) for row in all_cards), "raw_response_count": len(response_rows), "response_channels": dict(sorted(response_channels.items())), "reasoning_content_recovered": sum(row.get("response_channel") == "reasoning_content" for row in response_rows), "validation_error_counts": dict(sorted(validation_errors.items())), "invalid_enum_output_count": sum(len(row.get("invalid_enum_outputs", [])) for row in validation_rows), "invented_id_attempt_count": sum(len(row.get("invented_id_attempts", [])) for row in validation_rows), "evidence_span_failure_count": sum(int(row.get("evidence_span_failures", 0) or 0) for row in validation_rows), "search_plan_success": sum(not any(error == "typed_fallback_used" for error in row.get("validation_errors", [])) for row in search_plans), "search_plan_fallbacks": sum(any(error == "typed_fallback_used" for error in row.get("validation_errors", [])) for row in search_plans), "retrieval_rounds": len(retrieval_rows), "gaps_closed_before_retrieval": sum(run.get("final", {}).get("status") == "closed" and len(run.get("rounds", [])) == 1 for run in case_runs), "gaps_closed_after_evidence_card": sum(run.get("final", {}).get("status") == "closed" and len(run.get("rounds", [])) > 1 for run in case_runs), "gaps_remaining_open": sum(run.get("final", {}).get("status") == "open" for run in case_runs), "canonical_write_back": False, "no_frontier_expansion": True})
    preflight_doc = read_json(LIVE_OUT / "raw-api" / run_id / "001-search-plan-preflight-validation.json", {}) or {}
    metrics.update({"api_calls": len(usage), "postprocessing_api_calls": 0, "search_plan_preflight_success": preflight_doc.get("validated") is True, "gaps_closed_semantic_only": sum(run.get("final", {}).get("status") == "closed" and len(run.get("rounds", [])) == 1 for run in case_runs), "gaps_closed_after_candidate_constraint_update": sum(run.get("final", {}).get("status") == "closed" and len(run.get("rounds", [])) == 1 for run in case_runs), "gaps_closed_after_round2": sum(run.get("final", {}).get("status") == "closed" and len(run.get("rounds", [])) >= 2 for run in case_runs), "second_round_calls_avoided": sum(run.get("final", {}).get("status") == "closed" and len(run.get("rounds", [])) == 1 and (run.get("rounds") or [{}])[0].get("validation", {}).get("valid") for run in case_runs), "genuine_unresolved_cases": sum(run.get("final", {}).get("status") == "open" and all(row.get("validation", {}).get("valid") for row in run.get("rounds", [])) for run in case_runs), "invalid_card_cases": sum(run.get("final", {}).get("reason") == "invalid_card" for run in case_runs), "new_person_candidates": sum((run.get("rounds") or [{}])[-1].get("identity_decision", {}).get("identity_status") == "resolved_new_candidate" for run in case_runs)})
    write_json(LIVE_OUT / "selection.json", dict(selection))
    write_json(LIVE_OUT / "semantic-assessments.json", {"schema": schema.SCHEMA_VERSION, "assessments": [row for row in all_cards], "canonical_write_back": False})
    write_json(LIVE_OUT / "evidence-cards.json", {"schema": schema.SCHEMA_VERSION, "cards": all_cards, "canonical_write_back": False})
    write_json(LIVE_OUT / "search-plans.json", {"schema": schema.SCHEMA_VERSION, "plans": search_plans, "canonical_write_back": False})
    write_json(LIVE_OUT / "retrieval-trace.json", {"schema": schema.SCHEMA_VERSION, "traces": retrieval_rows, "canonical_write_back": False})
    write_json(LIVE_OUT / "validation-results.json", {"schema": schema.SCHEMA_VERSION, "results": validation_rows, "canonical_write_back": False})
    write_json(LIVE_OUT / "research-gap-transitions.json", {"schema": schema.SCHEMA_VERSION, "transitions": [{"case_id": run["case_id"], "rounds": len(run.get("rounds", [])), "final": run.get("final"), "canonical_write_back": False} for run in case_runs], "canonical_write_back": False})
    write_json(LIVE_OUT / "usage.json", {"schema": schema.SCHEMA_VERSION, "records": [{key: value for key, value in row.items() if key not in {"response", "parsed"}} for row in usage], "canonical_write_back": False})
    write_json(LIVE_OUT / "research-gaps.json", {"schema": schema.SCHEMA_VERSION, "gaps": [{"case_id": run["case_id"], **dict(run.get("final") or {}), "canonical_write_back": False} for run in case_runs], "canonical_write_back": False})
    write_json(LIVE_OUT / "candidate-deltas.json", {"schema": schema.SCHEMA_VERSION, "deltas": [{"case_id": run["case_id"], "rounds": [dict(item.get("state_delta") or {}) for item in run.get("rounds", [])], "canonical_write_back": False} for run in case_runs], "canonical_write_back": False})
    write_json(LIVE_OUT / "state-deltas.json", {"schema": schema.SCHEMA_VERSION, "deltas": [{"case_id": run["case_id"], "rounds": [dict(item.get("state_delta") or {}) for item in run.get("rounds", [])], "canonical_write_back": False} for run in case_runs], "canonical_write_back": False})
    # Keep the live projections explicit; no helper is allowed to replace
    # them with an empty replay projection.
    write_json(LIVE_OUT / "case-runs.json", {"schema": schema.SCHEMA_VERSION, "runs": case_runs, "canonical_write_back": False})
    write_json(LIVE_OUT / "identity-decisions.json", {"schema": schema.SCHEMA_VERSION, "decisions": [{"case_id": run["case_id"], **dict((run.get("rounds") or [{}])[-1].get("identity_decision") or {}), "canonical_write_back": False} for run in case_runs], "canonical_write_back": False})
    write_json(LIVE_OUT / "graph-actions.json", {"schema": schema.SCHEMA_VERSION, "actions": [{"case_id": run["case_id"], **dict((run.get("rounds") or [{}])[-1].get("graph_action") or {}), "canonical_write_back": False} for run in case_runs], "canonical_write_back": False})
    write_json(LIVE_OUT / "identity-recommendations.json", {"schema": schema.SCHEMA_VERSION, "recommendations": [{"case_id": run["case_id"], **dict((run.get("rounds") or [{}])[-1].get("recommendation") or {}), "canonical_write_back": False} for run in case_runs], "canonical_write_back": False})
    write_json(LIVE_OUT / "updated-constraints.json", {"schema": schema.SCHEMA_VERSION, "constraints": [{"case_id": run["case_id"], "constraints": (run.get("rounds") or [{}])[-1].get("constraints", []), "canonical_write_back": False} for run in case_runs], "canonical_write_back": False})
    write_json(LIVE_OUT / "metrics.json", metrics)
    write_json(LIVE_OUT / "manifest.json", {"schema": schema.SCHEMA_VERSION, "stage": "hng2-schema-controller-live", "run_id": run_id, "model": {"provider": PROVIDER, "model": MODEL, "api_calls": len(usage)}, "raw_api_root": str((LIVE_OUT / "raw-api" / run_id).relative_to(ROOT)), "base_projection_hash": hash_tree(BASE), "canonical_write_back": False, "no_frontier_expansion": True, "selection_hash": json_hash(selection)})
    return {"metrics": metrics, "runs": case_runs, "usage": usage, "validation": validation_rows}


def replay_live(run_id: str | None = None) -> dict[str, Any]:
    """Reproject one completed live run without making any API call.

    Raw provider envelopes remain untouched.  The replay rebuilds only the
    Python-owned projections from the stored semantic responses and the
    stored retrieval passages, so a controller fix can be validated against
    the same live evidence without resampling the model.
    """

    manifest = read_json(LIVE_OUT / "manifest.json", {}) or {}
    run_id = run_id or _text(manifest.get("run_id"))
    raw_dir = LIVE_OUT / "raw-api" / run_id
    selection = read_json(LIVE_OUT / "selection.json", {}) or {}
    cases, gaps = load_cases()
    sources = load_source_map()
    catalog = hng02.person_catalog()
    index = hng02.forms_index(catalog)
    raw_semantic: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for path in sorted(raw_dir.glob("*-semantic-*.json")):
        record = read_json(path, {}) or {}
        payload, channel, error = controller.extract_response_payload(record.get("response") or {})
        raw_semantic[str(record.get("case_id"))].append({"record": record, "payload": payload, "channel": channel, "error": error})
    trace_rows = (read_json(LIVE_OUT / "retrieval-trace.json", {}) or {}).get("traces", [])
    traces = {str(row.get("case_id")): dict(row) for row in trace_rows if isinstance(row, Mapping) and row.get("case_id")}
    usage = (read_json(LIVE_OUT / "usage.json", {}) or {}).get("records", [])
    search_plans = (read_json(LIVE_OUT / "search-plans.json", {}) or {}).get("plans", [])
    retrieval_rows = trace_rows
    case_runs: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    all_cards: list[dict[str, Any]] = []

    for selected in selection.get("cases", []):
        case_id = str(selected.get("case_id"))
        case = dict(cases.get(case_id) or selected)
        case["interpretation"] = normalize_target_interpretation(case, "", catalog, index)
        observation = case.get("observation") or {}
        ref = _text(observation.get("source_ref"))
        source_row = sources.get(ref, {})
        initial = {}
        if ref:
            initial[ref] = {"ref": ref, "work": source_row.get("source_work") or source_row.get("work") or observation.get("source_work"), "layer": source_row.get("source_layer") or source_row.get("layer"), "source_form": source_row.get("source_form") or "legacy_local", "text": source_row.get("original_text") or source_row.get("model_snippet") or source_row.get("text") or observation.get("exact_span") or "", "original_text": source_row.get("original_text") or source_row.get("model_snippet") or source_row.get("text") or ""}
        candidates = [dict(row) for row in case.get("candidates", []) if isinstance(row, Mapping)]
        constraints = [dict(row) for row in case.get("constraint_checks", []) if isinstance(row, Mapping)]
        gap = dict(gaps.get(case_id) or selected.get("gap") or {"status": "open"})
        refs: list[str] = []
        rounds: list[dict[str, Any]] = []
        group = sorted(raw_semantic.get(case_id, []), key=lambda row: int(row["record"].get("sequence") or 0))[:2]
        final: dict[str, Any] = {"status": "open", "reason": "no_semantic_response"}
        for round_no, item in enumerate(group, start=1):
            passages = initial
            if round_no == 2:
                passages = dict(initial)
                passages.update({str(row.get("ref")): dict(row) for row in traces.get(case_id, {}).get("passages", []) if isinstance(row, Mapping) and row.get("ref")})
            payload = item.get("payload")
            if payload is not None:
                validation, projection = process_card(case, payload, passages, candidates, constraints, refs, catalog, index)
            else:
                validation = {"valid": False, "errors": [item.get("error") or "no_payload"], "invalid_enum_outputs": [], "invented_id_attempts": [], "evidence_span_failures": 0}
                projection = {"card": None, "candidates": candidates, "constraints": constraints, "research_gap": gap, "state_delta": {"material": False}}
            validation_rows.append({"case_id": case_id, "round": round_no, "response_channel": item.get("channel"), "valid": validation.get("valid", False), "errors": validation.get("errors", []), "invalid_enum_outputs": validation.get("invalid_enum_outputs", []), "invented_id_attempts": validation.get("invented_id_attempts", []), "evidence_span_failures": validation.get("evidence_span_failures", 0)})
            rounds.append({"round": round_no, "response_channel": item.get("channel"), "validation": validation, **projection})
            all_cards.append({"case_id": case_id, "round": round_no, "payload": payload, "validation": validation})
            if not validation.get("valid"):
                final = {"status": "open", "reason": "invalid_card"}
                break
            candidates = projection["candidates"]
            constraints = projection["constraints"]
            gap = projection["research_gap"]
            refs = projection["supporting_refs"]
            final = gap
            if round_no == 1 and (gap.get("status") != "open" or not projection["state_delta"].get("material")):
                break
        case_runs.append({"case_id": case_id, "rounds": rounds, "final": final})

    response_rows = [row for row in usage if row.get("status") == "response"]
    response_channels = collections.Counter(str(row.get("response_channel") or "none") for row in response_rows)
    validation_errors = collections.Counter(error for row in validation_rows for error in row.get("errors", []))
    metrics = summarize([], [], case_runs, usage)
    metrics.update({"stage": "hng2-schema-controller-live", "selected_cases": len(selection.get("cases", [])), "cards_returned": sum(row.get("payload") is not None for row in all_cards), "cards_valid": sum(row.get("validation", {}).get("valid", False) for row in all_cards), "cards_rejected": sum(not row.get("validation", {}).get("valid", False) for row in all_cards), "raw_response_count": len(response_rows), "response_channels": dict(sorted(response_channels.items())), "reasoning_content_recovered": sum(row.get("response_channel") == "reasoning_content" for row in response_rows), "validation_error_counts": dict(sorted(validation_errors.items())), "invalid_enum_output_count": sum(len(row.get("invalid_enum_outputs", [])) for row in validation_rows), "invented_id_attempt_count": sum(len(row.get("invented_id_attempts", [])) for row in validation_rows), "evidence_span_failure_count": sum(int(row.get("evidence_span_failures", 0) or 0) for row in validation_rows), "search_plan_success": sum(not any(error == "typed_fallback_used" for error in row.get("validation_errors", [])) for row in search_plans), "search_plan_fallbacks": sum(any(error == "typed_fallback_used" for error in row.get("validation_errors", [])) for row in search_plans), "retrieval_rounds": len(retrieval_rows), "gaps_closed_before_retrieval": sum(run.get("final", {}).get("status") == "closed" and len(run.get("rounds", [])) == 1 for run in case_runs), "gaps_closed_after_evidence_card": sum(run.get("final", {}).get("status") == "closed" and len(run.get("rounds", [])) > 1 for run in case_runs), "gaps_remaining_open": sum(run.get("final", {}).get("status") == "open" for run in case_runs), "canonical_write_back": False, "no_frontier_expansion": True, "postprocessed_without_api_calls": True})
    preflight_doc = read_json(LIVE_OUT / "raw-api" / run_id / "001-search-plan-preflight-validation.json", {}) or {}
    metrics.update({"api_calls": len(usage), "postprocessing_api_calls": 0, "search_plan_preflight_success": preflight_doc.get("validated") is True, "gaps_closed_semantic_only": sum(run.get("final", {}).get("status") == "closed" and len(run.get("rounds", [])) == 1 for run in case_runs), "gaps_closed_after_candidate_constraint_update": sum(run.get("final", {}).get("status") == "closed" and len(run.get("rounds", [])) == 1 for run in case_runs), "gaps_closed_after_round2": sum(run.get("final", {}).get("status") == "closed" and len(run.get("rounds", [])) >= 2 for run in case_runs), "second_round_calls_avoided": sum(run.get("final", {}).get("status") == "closed" and len(run.get("rounds", [])) == 1 and (run.get("rounds") or [{}])[0].get("validation", {}).get("valid") for run in case_runs), "genuine_unresolved_cases": sum(run.get("final", {}).get("status") == "open" and all(row.get("validation", {}).get("valid") for row in run.get("rounds", [])) for run in case_runs), "invalid_card_cases": sum(run.get("final", {}).get("reason") == "invalid_card" for run in case_runs), "new_person_candidates": sum((run.get("rounds") or [{}])[-1].get("identity_decision", {}).get("identity_status") == "resolved_new_candidate" for run in case_runs)})
    write_json(LIVE_OUT / "selection.json", selection)
    write_json(LIVE_OUT / "semantic-assessments.json", {"schema": schema.SCHEMA_VERSION, "assessments": all_cards, "canonical_write_back": False})
    write_json(LIVE_OUT / "evidence-cards.json", {"schema": schema.SCHEMA_VERSION, "cards": all_cards, "canonical_write_back": False})
    write_json(LIVE_OUT / "validation-results.json", {"schema": schema.SCHEMA_VERSION, "results": validation_rows, "canonical_write_back": False})
    write_json(LIVE_OUT / "research-gap-transitions.json", {"schema": schema.SCHEMA_VERSION, "transitions": [{"case_id": run["case_id"], "rounds": len(run.get("rounds", [])), "final": run.get("final"), "canonical_write_back": False} for run in case_runs], "canonical_write_back": False})
    write_json(LIVE_OUT / "case-runs.json", {"schema": schema.SCHEMA_VERSION, "runs": case_runs, "canonical_write_back": False})
    write_json(LIVE_OUT / "identity-decisions.json", {"schema": schema.SCHEMA_VERSION, "decisions": [{"case_id": run["case_id"], **dict((run.get("rounds") or [{}])[-1].get("identity_decision") or {}), "canonical_write_back": False} for run in case_runs], "canonical_write_back": False})
    write_json(LIVE_OUT / "graph-actions.json", {"schema": schema.SCHEMA_VERSION, "actions": [{"case_id": run["case_id"], **dict((run.get("rounds") or [{}])[-1].get("graph_action") or {}), "canonical_write_back": False} for run in case_runs], "canonical_write_back": False})
    write_json(LIVE_OUT / "identity-recommendations.json", {"schema": schema.SCHEMA_VERSION, "recommendations": [{"case_id": run["case_id"], **dict((run.get("rounds") or [{}])[-1].get("recommendation") or {}), "canonical_write_back": False} for run in case_runs], "canonical_write_back": False})
    write_json(LIVE_OUT / "updated-constraints.json", {"schema": schema.SCHEMA_VERSION, "constraints": [{"case_id": run["case_id"], "constraints": (run.get("rounds") or [{}])[-1].get("constraints", []), "canonical_write_back": False} for run in case_runs], "canonical_write_back": False})
    write_json(LIVE_OUT / "research-gaps.json", {"schema": schema.SCHEMA_VERSION, "gaps": [{"case_id": run["case_id"], **dict(run.get("final") or {}), "canonical_write_back": False} for run in case_runs], "canonical_write_back": False})
    write_json(LIVE_OUT / "candidate-deltas.json", {"schema": schema.SCHEMA_VERSION, "deltas": [{"case_id": run["case_id"], "rounds": [dict(item.get("state_delta") or {}) for item in run.get("rounds", [])], "canonical_write_back": False} for run in case_runs], "canonical_write_back": False})
    write_json(LIVE_OUT / "state-deltas.json", {"schema": schema.SCHEMA_VERSION, "deltas": [{"case_id": run["case_id"], "rounds": [dict(item.get("state_delta") or {}) for item in run.get("rounds", [])], "canonical_write_back": False} for run in case_runs], "canonical_write_back": False})
    write_json(LIVE_OUT / "metrics.json", metrics)
    manifest["postprocessed_without_api_calls"] = True
    manifest["replay_source_run_id"] = run_id
    write_json(LIVE_OUT / "manifest.json", manifest)
    return {"metrics": metrics, "runs": case_runs, "validation": validation_rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("replay", "live", "replay-live"), default="replay")
    parser.add_argument("--run-id", default=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    if args.mode == "replay":
        result = replay_raw()
        if not args.quiet:
            print(json.dumps(result.get("metrics", {}), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.mode == "replay-live":
        result = replay_live(args.run_id)
        if not args.quiet:
            print(json.dumps(result.get("metrics", {}), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    selection = build_selection()
    LIVE_OUT.mkdir(parents=True, exist_ok=True)
    write_json(LIVE_OUT / "selection.json", selection)
    result = run_live(selection, args.run_id)
    if not args.quiet:
        print(json.dumps(result.get("metrics", {}), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
