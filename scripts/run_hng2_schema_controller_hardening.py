#!/usr/bin/env python3
"""HNG2-SC.1 controller hardening, offline replay, and tiny live validation.

The replay path is deliberately the default.  It consumes immutable HNG2-SC
and HNG2-SL response envelopes, applies only the Python controller, and writes
to a new namespace.  The live path is opt-in and is limited to five frozen
open-gap cases; it never expands a frontier or writes canonical data.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_hng0_2 as hng02  # noqa: E402
import hng1_common  # noqa: E402
import hng2_schema_controller as controller  # noqa: E402
import hng2_schema_strict_tools as strict_tools  # noqa: E402
import historical_entity_schema as schema  # noqa: E402
import run_hng2_schema_controller as base  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402


OUT = ROOT / "data/generated/hng2-schema-controller-hardening"
SC_LIVE = ROOT / "data/generated/hng2-schema-controller-live"
SC_RUN = "20260824T-HNG2-SC-07"
SC_RAW = SC_LIVE / "raw-api" / SC_RUN
SL_RAW = ROOT / "data/generated/hng2-schema-live/raw-api/20260824T-HNG2-SL"
MODEL = "deepseek-v4-flash"
PROVIDER = "deepseek"
PROMPT_VERSION = "hng2-sc1-card-hardening-v1"
SEARCH_PROMPT_VERSION = "hng2-sc1-search-plan-v1"
ALLOWED_SOURCES = tuple(base.ALLOWED_SOURCES)
STRICT_ENDPOINT = strict_tools.STRICT_COMPLETIONS_ENDPOINT

SEMANTIC_SYSTEM = """先理解给定的历史史料原文，再提交当前 ResearchGap 所需的结构化 EvidenceCard。
只抽取解决当前问题必需的实体和断言，不做全文人物抽取；合并同一局部实体的重复指称，优先使用能证明判断的最短连续原文，不枚举无关事件。
目标实体必须与 target_entity_key 对应。所有实体、断言、语义评估和身份建议只能依据输入的 source passages 与 Python 提供的候选、硬约束；不得修改硬约束。
不得创建任何 Person ID、candidate key、provisional_person_id、relation_id 或 graph_id。候选 key 只能复制输入，新的局部人物只能使用工具结构允许的 n0。
每个证据 ref 和 evidence span 都必须逐字来自输入原文；不确定时明确选择 unresolved、ambiguous、not_a_person 或 not_a_single_person，不要为了填满字段而猜测。
请只通过被强制调用的 submit_historical_entity_card 工具提交卡片，不输出助手 prose；工具参数中的 summary 只供人工审核，Python 不依赖它控制状态。"""

SEARCH_SYSTEM = """你是历史实体 SearchPlan 规划器。只为当前 ResearchGap 生成一次本地检索计划，不回答历史问题，不扩展 frontier。
只返回 JSON 对象：{"search_plan":{"target_constraint":"title_identity|kinship|temporal|biography_identity|short_name_identity","goal":"","candidate_keys":[],"preferred_sources":[],"search_entities":[],"search_patterns":[],"temporal_scope":{},"graph_neighborhood_scope":"case_only","stop_condition":""}}。
preferred_sources 只能逐字复制 allowed_sources 列表中的来源名；不得写入列表外来源。"""


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def json_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def hash_tree(path: Path) -> str:
    digest = hashlib.sha256()
    if not path.exists():
        return digest.hexdigest()
    for item in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(str(item.relative_to(path)).encode("utf-8"))
        digest.update(item.read_bytes())
    return digest.hexdigest()


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def text(value: Any) -> str:
    return str(value or "").strip()


def load_inputs() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    cases, gaps = base.load_cases()
    sources = base.load_source_map()
    return cases, gaps, sources


def target_interpretation(case: Mapping[str, Any], *, kind: str | None = None, reference: str | None = None, scope: str | None = None, role: str | None = None) -> dict[str, Any]:
    """Make a local packet interpretation without changing frozen inputs."""

    result = dict(case.get("interpretation") or {})
    if kind:
        result["entity_kind"] = kind
    if reference:
        result["reference_form"] = reference
    if scope:
        result["mention_scope"] = scope
    if role:
        result["discourse_role"] = role
    return result


def build_selection(cases: Mapping[str, Mapping[str, Any]], gaps: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Freeze five existing open ResearchGap cases deterministically."""

    requested = [
        ("title_existing", "hng1r2-hng1-raw-relation-2ff2066d8872cbae15f7"),
        ("abbreviated_existing", "hng1r2-hng1-raw-relation-921d528c3cf9154fa43c"),
        ("kinship_target_separation", "hng1r2-hng1-raw-relation-b97bdeb3fbec092978bc"),
        ("new_person", "hng2-live-hng2-live-w1-identity-33afe84247b036e9d9cb"),
        ("genuine_unresolved", "hng1r2-hng1-raw-relation-1153a723032c48422396"),
    ]
    selected: list[dict[str, Any]] = []
    for category, case_id in requested:
        case = cases.get(case_id)
        gap = gaps.get(case_id)
        if not case or not gap or gap.get("status") != "open":
            raise RuntimeError(f"required_open_gap_missing:{case_id}")
        surface = text((case.get("observation") or {}).get("surface"))
        override = {}
        if category == "kinship_target_separation":
            override = {"kind": "named_person", "reference": "full_name", "scope": "narrative", "role": "referenced_person"}
        elif category == "abbreviated_existing":
            override = {"kind": "abbreviated_name", "reference": "abbreviated", "scope": "narrative", "role": "referenced_person"}
        elif category == "new_person":
            override = {"kind": "named_person", "reference": "full_name", "scope": "narrative", "role": "referenced_person"}
        elif category == "genuine_unresolved":
            override = {"kind": "abbreviated_name", "reference": "abbreviated", "scope": "narrative", "role": "referenced_person"}
        selected.append({
            "case_id": case_id,
            "category": category,
            "surface": surface,
            "source_ref": (case.get("observation") or {}).get("source_ref"),
            "selection_key": base.stable_hash({"stage": "hng2-sc1-live-selection-v1", "case_id": case_id}),
            "research_gap": dict(gap),
            "packet_interpretation_override": override,
        })
    selected.sort(key=lambda row: (row["selection_key"], row["case_id"]))
    return {
        "schema": schema.SCHEMA_VERSION,
        "stage": "hng2-schema-controller-hardening-live",
        "selection_version": "hng2-sc1-live-selection-v1",
        "frozen": True,
        "selected_case_count": len(selected),
        "cases": selected,
        "source_case_namespace": "data/generated/hng2-schema/research-gaps.json",
        "max_semantic_calls_per_case": 2,
        "max_retrieval_rounds_per_case": 1,
        "no_frontier_expansion": True,
        "canonical_write_back": False,
    }


def passages_for(case_id: str, case: Mapping[str, Any], sources: Mapping[str, Mapping[str, Any]], extra: Sequence[Mapping[str, Any]] = ()) -> dict[str, dict[str, Any]]:
    result = base.passages_for_case(case_id, case, sources)
    for row in extra:
        if isinstance(row, Mapping) and row.get("ref"):
            result[str(row["ref"])] = dict(row)
    return result


def finish_reason(response: Mapping[str, Any] | None) -> str | None:
    choices = response.get("choices") if isinstance(response, Mapping) else None
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        return text(choices[0].get("finish_reason")) or None
    return None


def classify_response(record: Mapping[str, Any], case: Mapping[str, Any], passages: Mapping[str, Mapping[str, Any]], *, require_target: bool, candidate_rows: Sequence[Mapping[str, Any]] | None = None, strict_function: bool = False) -> dict[str, Any]:
    """Classify envelope/parse/card failures without semantic repair."""

    response = record.get("response") if isinstance(record, Mapping) else None
    finish = finish_reason(response if isinstance(response, Mapping) else None)
    if record.get("status") == "provider_rate_limited":
        return {"classification": "provider_rate_limit", "response_channel": "none", "finish_reason": finish, "validation": None}
    if record.get("status") not in {None, "response"}:
        return {"classification": "provider_request_failure", "response_channel": "none", "finish_reason": finish, "validation": None}
    if strict_function:
        payload, channel, parse_error = controller.extract_strict_tool_payload(response or {})
    else:
        payload, channel, parse_error = controller.extract_response_payload(response or {})
    if finish == "length":
        return {"classification": "response_truncated", "response_channel": channel, "finish_reason": finish, "parse_error": parse_error, "payload_present": payload is not None, "validation": None}
    if payload is None:
        return {"classification": "response_parse_failure", "response_channel": channel, "finish_reason": finish, "parse_error": parse_error, "payload_present": False, "validation": None}
    wire_payload = strict_tools.wire_to_controller_payload(payload) if strict_function else payload
    validation = controller.validate_card_payload(wire_payload, case, passages, candidate_rows=candidate_rows, require_target=require_target)
    classification = "valid_card" if validation.get("valid") else "card_validation_failure"
    return {"classification": classification, "response_channel": channel, "finish_reason": finish, "parse_error": parse_error, "payload_present": True, "validation": validation, "payload": wire_payload, "strict_function": strict_function}


def _entity(entity_key: str, surface: str, kind: str, reference: str, ref: str, span: str) -> dict[str, Any]:
    return {"entity_key": entity_key, "surface": surface, "entity_kind": kind, "reference_form": reference, "evidence_ref": ref, "evidence_span": span}


def _assertion(assertion_id: str, atype: str, subject: str, ref: str, span: str, *, object_key: str | None = None, confidence: str = "high") -> dict[str, Any]:
    row = {"assertion_id": assertion_id, "assertion_type": atype, "subject_entity_key": subject, "evidence_ref": ref, "evidence_span": span, "confidence": confidence, "value": None, "direction": None}
    if object_key is not None:
        row["object_entity_key"] = object_key
    return row


def fixture_payload(kind: str, ref: str, text_value: str, *, target: str = "e0", candidate_key: str | None = None) -> dict[str, Any]:
    if kind == "wu":
        entities = [_entity("e0", "武皇帝", "person_title", "title_only", ref, "武皇帝"), _entity("e1", "炎", "named_person", "full_name", ref, "諱炎")]
        assertions = [_assertion("a0", "identity_equivalence", "e0", ref, "武皇帝諱炎", object_key="e1")]
        decision, confidence = "choose_candidate", "high"
        chosen = candidate_key
    elif kind == "yu":
        entities = [_entity("e0", "庾太尉", "person_office_title", "office_title_only", ref, "庾太尉"), _entity("e1", "庾亮", "named_person", "full_name", ref, "庾亮")]
        assertions = [_assertion("a0", "title_of", "e0", ref, "庾太尉庾亮", object_key="e1")]
        decision, confidence, chosen = "choose_candidate", "high", candidate_key
    elif kind == "廙":
        entities = [_entity("e0", "廙", "abbreviated_name", "abbreviated", ref, "廙"), _entity("e1", "王廙", "named_person", "full_name", ref, "王廙")]
        assertions = [_assertion("a0", "identity_equivalence", "e0", ref, "廙王廙", object_key="e1")]
        decision, confidence, chosen = "choose_candidate", "high", candidate_key
    elif kind == "虞喜":
        entities = [_entity("e0", "虞喜", "named_person", "full_name", ref, "虞喜"), _entity("e1", "喜弟預女", "structural_kinship_expression", "kinship_plus_name", ref, "喜弟預女")]
        assertions = [_assertion("a0", "kinship_relation", "e0", ref, "娉喜弟預女為妻", object_key="e1")]
        decision, confidence, chosen = "new_person_candidate", "high", None
    elif kind == "structural":
        entities = [_entity("e0", "喜弟預女", "structural_kinship_expression", "kinship_plus_name", ref, "喜弟預女")]
        assertions = [_assertion("a0", "kinship_relation", "e0", ref, "喜弟預女")]
        decision, confidence, chosen = "not_a_single_person", "high", None
    elif kind == "new":
        entities = [_entity("e0", "新史人物", "named_person", "full_name", ref, "新史人物")]
        assertions = [_assertion("a0", "person_mention", "e0", ref, "新史人物")]
        decision, confidence, chosen = "new_person_candidate", "high", None
    elif kind == "unresolved":
        entities = [_entity("e0", "宣", "abbreviated_name", "abbreviated", ref, "宣")]
        assertions = [_assertion("a0", "person_mention", "e0", ref, "宣", confidence="medium")]
        decision, confidence, chosen = "unresolved", "low", None
    else:
        raise ValueError(f"unknown_fixture:{kind}")
    rec = {
        "decision": decision, "chosen_candidate_key": chosen, "confidence": confidence,
        "reason_codes": ["hng2_sc1_fixture"], "evidence_spans": [{"ref": ref, "span": entities[0]["evidence_span"]}],
        "new_entity_candidate": {"surface": entities[0]["surface"]} if decision == "new_person_candidate" else None,
        "new_entity_key": "n0" if decision == "new_person_candidate" else None,
        "unresolved_reason": "fixture leaves target open" if decision == "unresolved" else "",
        "summary": "fixture only",
    }
    return {
        "evidence_interpretation": {"entities": entities, "assertions": assertions, "summary": "fixture only", "target_entity_key": target},
        "semantic_assessment": {"assessment_status": "assessed", "semantic_fit": "support" if decision not in {"unresolved", "ambiguous"} else "unknown", "observed_role": "kinship_node" if kind in {"虞喜", "structural"} else "referenced_person", "evidence_spans": [{"ref": ref, "span": entities[0]["evidence_span"]}], "summary": "fixture only"},
        "identity_recommendation": rec,
        "research_gap": {"status": "open" if decision == "unresolved" else "closed", "missing_constraints": ["identity_evidence"] if decision == "unresolved" else [], "blocking_question": "fixture open" if decision == "unresolved" else "", "next_best_action": "search_biography_context" if decision == "unresolved" else "none", "candidate_keys": [chosen] if chosen else [], "stop_condition": "fixture"},
    }


def fixture_suite(cases: Mapping[str, Mapping[str, Any]], sources: Mapping[str, Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    local_catalog = copy.deepcopy(catalog)
    # A test-only existing Person makes binary propagation observable without
    # changing the project catalogue or canonical data.
    local_catalog["person-fixture-sima-yan"] = {"person_id": "person-fixture-sima-yan", "canonical_name": "司馬炎", "forms": ["司馬炎", "炎"], "canonical_forms": ["司馬炎"], "courtesy_forms": [], "alias_forms": ["司馬炎", "炎"], "office_titles": [], "surname": "司馬", "review_status": "fixture"}
    local_index = hng02.forms_index(local_catalog)
    specs = [
        ("wu-emperor-propagation", "wu", "fixture-wu-emperor", "武皇帝諱炎"),
        ("yu-taiwei-propagation", "yu", "fixture-yu-taiwei", "庾太尉庾亮"),
        ("yuxi-target-separation", "虞喜", "fixture-yuxi-target", "虞喜娉喜弟預女為妻"),
        ("structural-target", "structural", "fixture-structural-target", "喜弟預女"),
        ("wangyi-propagation", "廙", "fixture-wangyi-propagation", "廙王廙"),
        ("prior-temporal-preservation", "王廙", "fixture-prior-temporal", "王廙"),
        ("known-person-candidate-upgrade", "王廙", "fixture-known-person-upgrade", "王廙"),
        ("new-person-transition", "new", "fixture-new-person", "新史人物"),
    ]
    result: list[dict[str, Any]] = []
    for fixture_id, kind, ref, span in specs:
        if kind == "虞喜":
            payload_kind = "虞喜"
        elif kind == "王廙":
            payload_kind = "new"
        else:
            payload_kind = kind
        passage_text = span
        if fixture_id == "wu-emperor-propagation":
            passage_text = "武皇帝諱炎，字安世，文帝長子也"
        elif fixture_id == "yu-taiwei-propagation":
            passage_text = "庾太尉庾亮"
        elif fixture_id == "yuxi-target-separation":
            passage_text = "虞喜娉喜弟預女為妻"
        elif fixture_id == "prior-temporal-preservation":
            passage_text = "王廙"
        case = {"case_id": ref, "observation": {"surface": span, "exact_span": span, "source_ref": ref, "source_work": "fixture"}, "interpretation": {"entity_kind": "named_person", "reference_form": "full_name", "mention_scope": "narrative", "discourse_role": "referenced_person"}, "candidates": [], "constraint_checks": [], "research_gap": {"status": "open", "missing_constraints": ["identity_evidence"], "next_best_action": "search_biography_context", "blocking_question": "fixture", "candidate_keys": [], "stop_condition": "fixture"}}
        candidate_key = None
        prior_candidates: list[dict[str, Any]] = []
        prior_constraints: list[dict[str, Any]] = []
        if fixture_id in {"yu-taiwei-propagation", "wangyi-propagation"}:
            pid = "person-010" if fixture_id == "yu-taiwei-propagation" else "person-053"
            name = "庾亮" if pid == "person-010" else "王廙"
            candidate_key = "c0"
            prior_candidates = [{"candidate_key": "c0", "person_id": pid, "canonical_name": name, "known_forms": [name]}]
        if fixture_id == "wu-emperor-propagation":
            candidate_key = "c0"
            prior_candidates = [{"candidate_key": "c0", "person_id": "person-fixture-sima-yan", "canonical_name": "司馬炎", "known_forms": ["司馬炎", "炎"]}]
        if fixture_id in {"prior-temporal-preservation", "known-person-candidate-upgrade"}:
            prior_candidates = [{"candidate_key": "c0", "person_id": "person-053", "canonical_name": "王廙", "known_forms": ["王廙"]}]
            if fixture_id == "known-person-candidate-upgrade":
                prior_candidates[0]["person_id"] = None
            candidate_key = "c0"
            if fixture_id == "prior-temporal-preservation":
                prior_constraints = [{"constraint_type": "temporal", "candidate_key": "c0", "constraint_scope": "candidate", "status": "strong_support", "computed_by": "python_seed_temporal", "evidence_refs": ["seed-temporal-1"], "reason_code": "frozen_prior_temporal", "independent": True}]
        if fixture_id == "new-person-transition":
            span = "新史人物"
            case["observation"]["surface"] = span
        if fixture_id == "yuxi-target-separation":
            case["interpretation"] = target_interpretation(case, kind="named_person", reference="full_name", scope="narrative", role="referenced_person")
        elif fixture_id == "wangyi-propagation":
            case["interpretation"] = target_interpretation(case, kind="abbreviated_name", reference="abbreviated", scope="narrative", role="referenced_person")
        payload = fixture_payload(payload_kind, ref, passage_text, target="e0", candidate_key=candidate_key)
        if fixture_id in {"prior-temporal-preservation", "known-person-candidate-upgrade"}:
            payload = fixture_payload("new", ref, passage_text, target="e0", candidate_key=None)
            payload["evidence_interpretation"]["entities"][0].update({"surface": "王廙", "entity_kind": "named_person", "reference_form": "full_name", "evidence_span": "王廙"})
            payload["evidence_interpretation"]["assertions"][0].update({"evidence_span": "王廙"})
            payload["semantic_assessment"]["evidence_spans"] = [{"ref": ref, "span": "王廙"}]
            payload["identity_recommendation"]["evidence_spans"] = [{"ref": ref, "span": "王廙"}]
            payload["identity_recommendation"].update({"decision": "choose_candidate", "chosen_candidate_key": "c0", "confidence": "high", "new_entity_key": None, "new_entity_candidate": None})
            payload["evidence_interpretation"]["assertions"][0] = _assertion("a0", "person_mention", "e0", ref, "王廙")
        passages = {ref: {"ref": ref, "work": "fixture", "text": passage_text, "original_text": passage_text, "source_form": "fixture"}}
        if fixture_id == "prior-temporal-preservation":
            passages["seed-temporal-1"] = {"ref": "seed-temporal-1", "work": "fixture", "text": "王廙", "original_text": "王廙", "source_form": "fixture"}
        result.append({"fixture_id": fixture_id, "case": case, "payload": payload, "passages": passages, "prior_candidates": prior_candidates, "prior_constraints": prior_constraints, "catalog": local_catalog, "index": local_index})
    return result


def process_fixture(row: Mapping[str, Any]) -> dict[str, Any]:
    case = dict(row["case"])
    passages = row["passages"]
    candidates = row.get("prior_candidates", [])
    constraints = row.get("prior_constraints", [])
    validation = controller.validate_card_payload(row["payload"], case, passages, candidate_rows=candidates, require_target=True)
    if not validation.get("valid"):
        return {"fixture_id": row["fixture_id"], "validation": validation, "projection": None, "prior_constraints_preserved": False, "expected": {"valid": False}}
    projection = controller.project_valid_card(case, row["payload"], passages, candidates, constraints, [], row["catalog"], row["index"])
    preserved = all(dict(old) in projection.get("constraints", []) for old in constraints if isinstance(old, Mapping))
    return {"fixture_id": row["fixture_id"], "validation": validation, "projection": projection, "prior_constraints_preserved": preserved, "expected": {"valid": True}}


def _raw_record(path: Path, source_run: str) -> dict[str, Any]:
    record = read_json(path, {}) or {}
    record["_source_run"] = source_run
    record["_source_path"] = str(path.relative_to(ROOT))
    return record


def replay() -> dict[str, Any]:
    cases, gaps, sources = load_inputs()
    catalog = hng02.person_catalog()
    index = hng02.forms_index(catalog)
    rows: list[dict[str, Any]] = []
    for path in sorted(SC_RAW.glob("*-semantic-*.json")):
        record = _raw_record(path, "HNG2-SC-07")
        case = dict(cases.get(text(record.get("case_id"))) or {"case_id": record.get("case_id"), "observation": {}, "candidates": [], "research_gap": {"status": "open"}})
        case["research_gap"] = dict(gaps.get(text(record.get("case_id"))) or case.get("research_gap") or {"status": "open"})
        passages = passages_for(text(record.get("case_id")), case, sources)
        classification = classify_response(record, case, passages, require_target=False, candidate_rows=case.get("candidates", []))
        row = {key: value for key, value in classification.items() if key not in {"payload"}}
        row.update({"source_run": "HNG2-SC-07", "path": record["_source_path"], "case_id": record.get("case_id"), "sequence": record.get("sequence")})
        if classification.get("classification") == "valid_card":
            projection = controller.project_valid_card(case, classification["payload"], passages, case.get("candidates", []), case.get("constraint_checks", []), [], catalog, index)
            row["projection"] = projection
            row["prior_constraints_preserved"] = all(dict(old) in projection.get("constraints", []) for old in case.get("constraint_checks", []) if isinstance(old, Mapping))
        rows.append(row)
    # HNG2-SL is used only as a frozen response-envelope regression source;
    # no new semantic result is treated as a live finding here.
    for path in sorted(SL_RAW.glob("*-semantic-*.json")):
        record = _raw_record(path, "HNG2-SL-envelope-regression")
        response = record.get("response") or {}
        choices = response.get("choices") if isinstance(response, Mapping) else None
        message = choices[0].get("message") if isinstance(choices, list) and choices and isinstance(choices[0], Mapping) else {}
        if not text((message or {}).get("reasoning_content")) or text((message or {}).get("content")):
            continue
        case = dict(cases.get(text(record.get("case_id"))) or {"case_id": record.get("case_id"), "observation": {}, "candidates": [], "research_gap": {"status": "open"}})
        case["research_gap"] = dict(gaps.get(text(record.get("case_id"))) or case.get("research_gap") or {"status": "open"})
        passages = passages_for(text(record.get("case_id")), case, sources)
        classification = classify_response(record, case, passages, require_target=False, candidate_rows=case.get("candidates", []))
        rows.append({key: value for key, value in classification.items() if key not in {"payload"}} | {"source_run": "HNG2-SL-envelope-regression", "path": record["_source_path"], "case_id": record.get("case_id"), "sequence": record.get("sequence")})

    fixture_rows = [process_fixture(row) for row in fixture_suite(cases, sources, catalog)]
    metrics = summarize_replay(rows, fixture_rows)
    manifest = {"schema": schema.SCHEMA_VERSION, "stage": "hng2-schema-controller-hardening-replay", "api_calls": 0, "canonical_write_back": False, "no_frontier_expansion": True, "input_hashes": {"hng2_sc_07_raw": hash_tree(SC_RAW), "hng2_sl_raw": hash_tree(SL_RAW), "hng2_schema": hash_tree(ROOT / "data/generated/hng2-schema")}, "controller": "scripts/hng2_schema_controller.py", "prompt_version": PROMPT_VERSION}
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "response-classifications.json", {"schema": schema.SCHEMA_VERSION, "rows": rows, "canonical_write_back": False})
    write_json(OUT / "replay-results.json", {"schema": schema.SCHEMA_VERSION, "source": "frozen HNG2-SC-07 plus HNG2-SL envelope samples", "rows": rows, "fixtures": fixture_rows, "metrics": metrics, "canonical_write_back": False})
    write_projection(OUT, rows, fixture_rows, metrics)
    manifest["selection_hash"] = None
    write_json(OUT / "manifest.json", manifest)
    return {"rows": rows, "fixtures": fixture_rows, "metrics": metrics, "manifest": manifest}


def summarize_replay(rows: Sequence[Mapping[str, Any]], fixtures: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in rows:
        key = text(row.get("classification")) or "unknown"
        counts[key] = counts.get(key, 0) + 1
    f_valid = sum(row.get("validation", {}).get("valid", False) for row in fixtures)
    f_invalid = len(fixtures) - f_valid
    projections = [row.get("projection") for row in fixtures if isinstance(row.get("projection"), Mapping)]
    propagation = sum(len(p.get("candidate_info", {}).get("identity_propagations", [])) for p in projections)
    upgrades = sum(len(p.get("state_delta", {}).get("upgraded_candidates", [])) for p in projections)
    new_person = sum(p.get("identity_decision", {}).get("identity_status") == "resolved_new_candidate" for p in projections)
    resolved_existing = sum(p.get("identity_decision", {}).get("identity_status") == "resolved_existing" for p in projections)
    unresolved = sum(p.get("identity_decision", {}).get("identity_status") == "unresolved" for p in projections)
    # This flag is attached during fixture projection, where the immutable
    # prior rows are still available for exact value comparison.
    prior_temporal = next((bool(row.get("prior_constraints_preserved")) for row in fixtures if row.get("fixture_id") == "prior-temporal-preservation"), False)
    return {
        "stage": "hng2-schema-controller-hardening-replay",
        "api_calls": 0,
        "response_classifications": dict(sorted(counts.items())),
        "hng2_sc07_raw_response_count": sum(row.get("source_run") == "HNG2-SC-07" for row in rows),
        "reasoning_content_responses_recovered": sum(row.get("source_run") == "HNG2-SL-envelope-regression" and row.get("response_channel") == "reasoning_content" and row.get("classification") in {"valid_card", "card_validation_failure"} for row in rows),
        "fixture_count": len(fixtures), "fixture_valid_count": f_valid, "fixture_invalid_count": f_invalid,
        "identity_propagation_count": propagation, "candidate_upgrade_count": upgrades,
        "resolved_existing_count": resolved_existing, "resolved_new_candidate_count": new_person, "unresolved_count": unresolved,
        "target_validation_fixture_count": f_valid,
        "prior_temporal_constraint_preserved": prior_temporal,
        "valid_cards": counts.get("valid_card", 0) + f_valid,
        "invalid_cards": counts.get("card_validation_failure", 0) + f_invalid,
        "truncated_responses": counts.get("response_truncated", 0),
        "parse_failures": counts.get("response_parse_failure", 0),
        "canonical_write_back": False, "no_frontier_expansion": True,
    }


def write_projection(out: Path, rows: Sequence[Mapping[str, Any]], fixtures: Sequence[Mapping[str, Any]], metrics: Mapping[str, Any]) -> None:
    projections = [{"fixture_id": row.get("fixture_id"), **dict(row.get("projection") or {}), "canonical_write_back": False} for row in fixtures if row.get("projection")]
    write_json(out / "candidate-deltas.json", {"schema": schema.SCHEMA_VERSION, "deltas": [{"fixture_id": row.get("fixture_id"), **dict((row.get("projection") or {}).get("state_delta") or {}), "canonical_write_back": False} for row in fixtures], "canonical_write_back": False})
    write_json(out / "constraint-updates.json", {"schema": schema.SCHEMA_VERSION, "updates": [{"fixture_id": row.get("fixture_id"), "constraints": (row.get("projection") or {}).get("constraints", []), "canonical_write_back": False} for row in fixtures], "canonical_write_back": False})
    write_json(out / "research-gaps.json", {"schema": schema.SCHEMA_VERSION, "gaps": [{"fixture_id": row.get("fixture_id"), "research_gap": (row.get("projection") or {}).get("research_gap"), "canonical_write_back": False} for row in fixtures], "canonical_write_back": False})
    write_json(out / "identity-decisions.json", {"schema": schema.SCHEMA_VERSION, "decisions": [{"fixture_id": row.get("fixture_id"), **dict((row.get("projection") or {}).get("identity_decision") or {}), "canonical_write_back": False} for row in fixtures], "canonical_write_back": False})
    write_json(out / "graph-actions.json", {"schema": schema.SCHEMA_VERSION, "actions": [{"fixture_id": row.get("fixture_id"), **dict((row.get("projection") or {}).get("graph_action") or {}), "canonical_write_back": False} for row in fixtures], "canonical_write_back": False})
    write_json(out / "state-deltas.json", {"schema": schema.SCHEMA_VERSION, "deltas": [{"fixture_id": row.get("fixture_id"), **dict((row.get("projection") or {}).get("state_delta") or {}), "canonical_write_back": False} for row in fixtures], "canonical_write_back": False})
    write_json(out / "metrics.json", dict(metrics))


def usage_from(response: Mapping[str, Any]) -> dict[str, int]:
    usage = response.get("usage") if isinstance(response, Mapping) else {}
    usage = usage if isinstance(usage, Mapping) else {}
    return {key: int(usage.get(key) or 0) for key in ("prompt_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens", "total_tokens")}


def call_live_record(kind: str, case_id: str, payload: Mapping[str, Any], raw_dir: Path, sequence: int) -> dict[str, Any]:
    started = time.monotonic()
    strict_function = kind == "semantic"
    endpoint = STRICT_ENDPOINT if strict_function else None
    record: dict[str, Any] = {"kind": kind, "case_id": case_id, "sequence": sequence, "start_time": now(), "model": MODEL, "provider": PROVIDER, "endpoint": endpoint or "https://api.deepseek.com/chat/completions", "strict_function": strict_function, "prompt_version": PROMPT_VERSION if kind == "semantic" else SEARCH_PROMPT_VERSION, "input_hash": json_hash(payload), "canonical_write_back": False, "immutable": True}
    try:
        messages = [{"role": "system", "content": SEMANTIC_SYSTEM if strict_function else SEARCH_SYSTEM}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)}]
        if strict_function:
            # The prompt asks for at most six entities/eight assertions.  A
            # modest 2400-token ceiling keeps a long but bounded strict card
            # from being cut off; it does not change the semantic contract.
            response = call_deepseek(messages, model=MODEL, temperature=0, tools=[strict_tools.legacy_strict_function_definition()], tool_choice=strict_tools.strict_tool_choice(), thinking={"type": "disabled"}, max_tokens=2400, timeout=180, endpoint=STRICT_ENDPOINT)
        else:
            response = call_deepseek(messages, model=MODEL, temperature=0, response_format={"type": "json_object"}, tools=[], thinking={"type": "disabled"}, max_tokens=700, timeout=180)
        record.update({"status": "response", "response": response, "usage": usage_from(response), "finish_reason": finish_reason(response)})
        if strict_function:
            _, channel, parse_error = controller.extract_strict_tool_payload(response)
            choices = response.get("choices") if isinstance(response, Mapping) else []
            message = choices[0].get("message") if isinstance(choices, list) and choices and isinstance(choices[0], Mapping) else {}
            tool_calls = message.get("tool_calls") if isinstance(message, Mapping) else []
            record.update({"response_channel": channel, "parse_error": parse_error, "tool_call_count": len(tool_calls) if isinstance(tool_calls, list) else 0, "tool_name": ((tool_calls[0].get("function") or {}).get("name") if isinstance(tool_calls, list) and tool_calls and isinstance(tool_calls[0], Mapping) and isinstance(tool_calls[0].get("function"), Mapping) else None)})
        else:
            _, channel, parse_error = controller.extract_response_payload(response)
            record.update({"response_channel": channel, "parse_error": parse_error, "tool_call_count": 0})
    except Exception as exc:
        http_status = getattr(exc, "http_status", None)
        body = str(getattr(exc, "provider_error_body", "") or "")
        try:
            parsed_body = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed_body = {}
        error_body = parsed_body.get("error") if isinstance(parsed_body, Mapping) else {}
        record.update({"status": "provider_rate_limited" if http_status == 429 else "provider_request_failure", "response": None, "usage": {}, "response_channel": "none", "finish_reason": None, "exception_class": type(exc).__name__, "exception_message": str(exc)[:500], "http_status": http_status, "provider_error_code": error_body.get("code") if isinstance(error_body, Mapping) else None, "provider_error_message": error_body.get("message") if isinstance(error_body, Mapping) else body[:500]})
    record["elapsed_seconds"] = round(time.monotonic() - started, 6)
    write_json(raw_dir / f"{sequence:03d}-{kind}-{case_id}.json", record)
    return record


def search_plan_packet(case: Mapping[str, Any], gap: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]], passages: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    packet = base.search_packet(case, gap, candidates, passages)
    packet["allowed_sources"] = list(ALLOWED_SOURCES)
    return packet


def validate_search_plan(payload: Any, candidates: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any] | None, list[str]]:
    return base._search_plan_from_response(payload, {}, candidates, ALLOWED_SOURCES)


def live(run_id: str) -> dict[str, Any]:
    cases, gaps, sources = load_inputs()
    selection = build_selection(cases, gaps)
    live_out = OUT / "live" / run_id
    write_json(live_out / "selection.json", selection)
    raw_dir = live_out / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=True)
    catalog = hng02.person_catalog()
    index = hng02.forms_index(catalog)
    usage: list[dict[str, Any]] = []
    # SearchPlan preflight is a real authenticated request, but contains no
    # project source text or historical finding.
    preflight_candidates = [{"candidate_key": "c0", "canonical_name": "庾亮", "known_forms": ["庾亮", "庾公"]}]
    preflight_payload = {"allowed_sources": list(ALLOWED_SOURCES), "research_gap": {"status": "open", "missing_constraints": ["title_identity"], "blocking_question": "validate typed local planning", "next_best_action": "search_title_identity", "candidate_keys": ["c0"], "stop_condition": "return one typed plan"}, "mention": {"surface": "庾太尉", "source_work": "晉書"}, "candidates": preflight_candidates, "source_passages": [], "planning_questions": list(schema.CHINESE_SEARCH_PLAN_QUESTIONS)}
    preflight = call_live_record("search-plan-preflight", "preflight", preflight_payload, raw_dir, 1)
    usage.append(preflight)
    preflight_payload_out, _, _ = controller.extract_response_payload(preflight.get("response") or {}) if preflight.get("response") else (None, "none", None)
    preflight_plan, preflight_errors = validate_search_plan(preflight_payload_out, preflight_candidates)
    write_json(raw_dir / "001-search-plan-preflight-validation.json", {"validated": preflight_plan is not None and not preflight_errors, "errors": preflight_errors, "canonical_write_back": False})
    if preflight.get("status") != "response" or preflight_plan is None:
        raise RuntimeError("search_plan_preflight_failed")

    punctuated, legacy = hng1_common.load_retrieval_sources()
    runs: list[dict[str, Any]] = []
    validations: list[dict[str, Any]] = []
    search_plans: list[dict[str, Any]] = []
    retrieval_rows: list[dict[str, Any]] = []
    sequence = 2
    for selected in selection["cases"]:
        case_id = selected["case_id"]
        case = copy.deepcopy(cases[case_id])
        override = selected.get("packet_interpretation_override") or {}
        case["interpretation"] = target_interpretation(case, **override)
        case["research_gap"] = dict(gaps[case_id])
        passages = passages_for(case_id, case, sources)
        candidates = [dict(row) for row in case.get("candidates", []) if isinstance(row, Mapping)]
        constraints = [dict(row) for row in case.get("constraint_checks", []) if isinstance(row, Mapping)]
        refs = sorted(passages)
        rounds: list[dict[str, Any]] = []
        final = {"status": "open", "reason": "no_valid_card"}
        for round_no in (1, 2):
            packet = base.semantic_packet(case, case["research_gap"], candidates, constraints, passages, round_no)
            packet["target_entity_surface"] = selected["surface"]
            packet["target_entity_required"] = True
            rec = call_live_record("semantic", case_id, packet, raw_dir, sequence)
            sequence += 1
            usage.append(rec)
            classification = classify_response(rec, case, passages, require_target=True, candidate_rows=candidates, strict_function=True)
            validation = classification.get("validation") or {"valid": False, "errors": [classification.get("parse_error") or classification.get("classification")], "invalid_enum_outputs": [], "invented_id_attempts": [], "evidence_span_failures": 0}
            validations.append({"case_id": case_id, "round": round_no, **{key: classification.get(key) for key in ("classification", "response_channel", "finish_reason", "parse_error", "payload_present")}, "validation": validation})
            round_row: dict[str, Any] = {"round": round_no, "classification": classification.get("classification"), "response_channel": classification.get("response_channel"), "validation": validation}
            if classification.get("classification") != "valid_card":
                rounds.append(round_row)
                final = {"status": "open", "reason": classification.get("classification")}
                break
            projection = controller.project_valid_card(case, classification["payload"], passages, candidates, constraints, refs, catalog, index)
            round_row.update({"projection": projection})
            rounds.append(round_row)
            candidates, constraints = projection["candidates"], projection["constraints"]
            case["research_gap"] = projection["research_gap"]
            refs = projection["supporting_refs"]
            final = projection["research_gap"]
            if round_no == 2 or final.get("status") != "open" or not projection.get("state_delta", {}).get("material"):
                break
            search_packet_value = search_plan_packet(case, final, candidates, passages)
            plan_rec = call_live_record("search-plan", case_id, search_packet_value, raw_dir, sequence)
            sequence += 1
            usage.append(plan_rec)
            plan_payload, plan_channel, plan_error = controller.extract_response_payload(plan_rec.get("response") or {}) if plan_rec.get("response") else (None, "none", plan_rec.get("exception_class"))
            plan, plan_errors = validate_search_plan(plan_payload, candidates)
            if plan is None:
                plan = controller.typed_fallback_search_plan(case, final, candidates)
                plan_errors = [*plan_errors, "typed_fallback_used"]
            search_plans.append({"case_id": case_id, "round": round_no, "plan": plan, "validation_errors": plan_errors, "response_channel": plan_channel, "canonical_write_back": False})
            retrieved, trace = base.retrieve(case, plan, passages, punctuated, legacy)
            trace["used_refs"] = sorted(set(refs) & set(retrieved))
            trace["new_used_refs"] = sorted(set(trace["used_refs"]) - set(refs))
            retrieval_rows.append({"case_id": case_id, "round": round_no, **trace, "canonical_write_back": False})
            passages = retrieved
        runs.append({"case_id": case_id, "category": selected["category"], "rounds": rounds, "final": final})

    response_rows = [row for row in usage if row.get("status") == "response"]
    latencies = [float(row["elapsed_seconds"]) for row in response_rows if row.get("elapsed_seconds") is not None]
    total_usage = {key: sum(int(row.get("usage", {}).get(key) or 0) for row in usage) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    metrics = {
        "stage": "hng2-schema-controller-hardening-live", "selected_cases": len(selection["cases"]), "api_calls": len(usage), "semantic_calls": sum(row.get("kind") == "semantic" for row in usage), "search_plan_calls": sum(row.get("kind") in {"search-plan", "search-plan-preflight"} for row in usage), "retrieval_rounds": len(retrieval_rows),
        "response_classifications": {key: sum(row.get("classification") == key for row in validations) for key in sorted({text(row.get("classification")) for row in validations})}, "search_plan_model_success": sum("typed_fallback_used" not in row.get("validation_errors", []) for row in search_plans), "search_plan_fallbacks": sum("typed_fallback_used" in row.get("validation_errors", []) for row in search_plans), "gaps_remaining_open": sum(row.get("final", {}).get("status") == "open" for row in runs), "gaps_closed": sum(row.get("final", {}).get("status") == "closed" for row in runs), "response_channels": {key: sum(row.get("response_channel") == key for row in validations) for key in sorted({text(row.get("response_channel")) for row in validations})}, "usage": total_usage, "median_latency_seconds": statistics.median(latencies) if latencies else 0, "max_latency_seconds": max(latencies) if latencies else 0, "second_semantic_calls_avoided": sum(len(run.get("rounds", [])) == 1 for run in runs), "semantic_state_mutations": sum(bool((run.get("rounds") or [{}])[0].get("projection")) for run in runs), "canonical_write_back": False, "no_frontier_expansion": True, "preflight_succeeded": True,
    }
    write_json(live_out / "semantic-assessments.json", {"schema": schema.SCHEMA_VERSION, "validations": validations, "canonical_write_back": False})
    write_json(live_out / "search-plans.json", {"schema": schema.SCHEMA_VERSION, "plans": search_plans, "canonical_write_back": False})
    write_json(live_out / "retrieval-trace.json", {"schema": schema.SCHEMA_VERSION, "traces": retrieval_rows, "canonical_write_back": False})
    write_json(live_out / "case-runs.json", {"schema": schema.SCHEMA_VERSION, "runs": runs, "canonical_write_back": False})
    write_json(live_out / "metrics.json", metrics)
    write_json(live_out / "manifest.json", {"schema": schema.SCHEMA_VERSION, "stage": "hng2-schema-controller-hardening-live", "run_id": run_id, "raw_api_root": str(raw_dir.relative_to(ROOT)), "input_hashes": {"hng2_schema": hash_tree(ROOT / "data/generated/hng2-schema"), "hng2_sc_07_raw": hash_tree(SC_RAW)}, "canonical_write_back": False, "no_frontier_expansion": True, "selection_hash": json_hash(selection), "resolver_code": "scripts/hng2_schema_controller.py", "prompt_version": PROMPT_VERSION})
    return {"selection": selection, "runs": runs, "metrics": metrics, "validations": validations, "output_root": str(live_out.relative_to(ROOT))}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("replay", "live"), default="replay")
    parser.add_argument("--run-id", default=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    result = replay() if args.mode == "replay" else live(args.run_id)
    if not args.quiet:
        print(json.dumps(result.get("metrics", {}), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
