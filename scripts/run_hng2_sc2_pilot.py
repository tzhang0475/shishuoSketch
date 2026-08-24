#!/usr/bin/env python3
"""HNG2-SC2-P: one bounded evidence-discovery follow-up pilot.

The pilot is intentionally isolated from the HNG controller.  It runs the
current small-card path once as a baseline, then independently runs the same
candidate-blind card with two bounded additions: unresolved observations and
one local FIND/OPEN followed by one generic evidence-resolution card.

No result from the follow-up card is projected into Person, Relation, Fact,
GraphAction, IdentityDecision, or canonical data.  The only Python validation
performed on Round 2 is source-ref/span validation and a small comparison
projection for reporting.
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
import run_hng2_schema_controller_hardening as hardening  # noqa: E402
import run_hng2_schema_controller_small_card as small  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402


OUT = ROOT / "data/generated/hng2-sc2-pilot"
MODEL = "deepseek-v4-flash"
PROVIDER = "deepseek"
PROMPT_VERSION = "hng2-sc2-p-small-card-followup-v1"
SEMANTIC_ENDPOINT = strict_tools.STRICT_COMPLETIONS_ENDPOINT

R1_SYSTEM = """先阅读给定的历史史料，理解当前 target，并提交最小 Historical Evidence Card。
只使用输入的 source_passages；保持 target 与同段上下文人物分开。只有原文直接支持的实体关系才能形成断言，共现本身不是关系。合并重复指称，优先保留解决当前 target 所需的最少证据，不枚举无关事件。
如果原文中有与当前 target 直接相关、但当前小型 assertion vocabulary 不能安全表达的文字观察，可以记录在 unresolved_observations 中。观察必须逐字锚定输入原文，只是后续本地检索提示，不是历史事实、身份决定或关系；最多两条，每条最多三个简短 search_terms。不要猜测或泛化。
你只负责记录史料文字层证据，不作数据库身份、候选、约束、ResearchGap 或图谱决定；不确定时保留不确定性。所有出处只能引用输入 passage ref，不创建任何数据库 ID。请只通过被强制调用的工具提交结果，不输出助手 prose。"""

R2_SYSTEM = """请核查一个 Round 1 观察，但不要预设该观察为真。
只使用本次输入的 target、观察和新提供的 source_passages。只提交新原文直接支持的最小 findings；每条 finding 必须引用输入 ref 和其中连续、原样的 exact_span。无法由新证据直接支持时返回 unresolved，不要依赖 Round 1 文字本身推断，不要补充外部历史知识。
你只负责来源对齐的文字证据发现，不创建 Person ID、candidate key、Relation ID、Fact、GraphAction 或任何数据库决定。请只通过被强制调用的工具提交结果，不输出助手 prose。"""


FROZEN_CASES: tuple[dict[str, str], ...] = (
    {
        "category": "control_title_known",
        "case_id": "hng1r2-hng1-raw-relation-2ff2066d8872cbae15f7",
        "rationale": "existing title/office case with a reviewed candidate; control for a question already handled by the small card",
    },
    {
        "category": "control_required_new_person",
        "case_id": "hng2-live-hng2-live-w1-identity-33afe84247b036e9d9cb",
        "rationale": "required 陳騫 case and existing named-person control; tests that follow-up does not needlessly expand a clear name",
    },
    {
        "category": "rich_title",
        "case_id": "hng2-hng02-relation-35297c7dc00a768062fe",
        "rationale": "punctuated Jinshu passage contains richer imperial title/name context than the target surface alone",
    },
    {
        "category": "rich_title_temporal_context",
        "case_id": "hng1r2-hng1-raw-relation-72e698708d54086b78ac",
        "rationale": "title-only 文帝 case retained as a difficult title/era control from the frozen open-gap inventory",
    },
    {
        "category": "relation_kinship_target",
        "case_id": "hng1r2-hng1-raw-relation-b97bdeb3fbec092978bc",
        "rationale": "虞喜 target with contextual kinship material; target/context separation is directly testable",
    },
    {
        "category": "relation_kinship_structure",
        "case_id": "hng2-hng02-relation-2164c52caaa53337435e",
        "rationale": "喜弟預女 structural expression; relation vocabulary is intentionally too small for all useful context",
    },
    {
        "category": "temporal_era",
        "case_id": "hng2-live-hng2-live-w1-temporal-7787c8e7d9f2c14fc5b5",
        "rationale": "temporal/office context around 何曾; tests whether follow-up discovers period information without broad extraction",
    },
)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def json_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


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


def usage_from(response: Mapping[str, Any] | None) -> dict[str, int]:
    usage = response.get("usage") if isinstance(response, Mapping) else {}
    usage = usage if isinstance(usage, Mapping) else {}
    return {key: int(usage.get(key) or 0) for key in ("prompt_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens", "total_tokens")}


def finish_reason(response: Mapping[str, Any] | None) -> str | None:
    choices = response.get("choices") if isinstance(response, Mapping) else None
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        return text(choices[0].get("finish_reason")) or None
    return None


def safe_file_part(value: Any) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in str(value))[:160]


def build_selection(cases: Mapping[str, Mapping[str, Any]], gaps: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    selected: list[dict[str, Any]] = []
    for row in FROZEN_CASES:
        case_id = row["case_id"]
        case = cases.get(case_id)
        gap = gaps.get(case_id)
        if not isinstance(case, Mapping) or not isinstance(gap, Mapping):
            raise RuntimeError(f"frozen_case_missing:{case_id}")
        if gap.get("status") != "open":
            raise RuntimeError(f"frozen_case_not_open:{case_id}")
        obs = case.get("observation") if isinstance(case.get("observation"), Mapping) else {}
        selected.append({
            **row,
            "surface": text(obs.get("surface")),
            "source_ref": text(obs.get("source_ref")),
            "source_work": text(obs.get("source_work")),
            "reading_gap": dict(gap),
            "selection_key": base.stable_hash({"stage": "hng2-sc2-p-frozen-selection-v1", "case_id": case_id}),
        })
    selected.sort(key=lambda item: (item["selection_key"], item["case_id"]))
    return {
        "stage": "hng2-sc2-p",
        "selection_version": "hng2-sc2-p-frozen-selection-v1",
        "frozen": True,
        "selection_basis": "existing HNG2 schema open ResearchGap inventory; deterministic required-case composition",
        "selected_case_count": len(selected),
        "cases": selected,
        "max_observations_per_case": 2,
        "max_search_terms_per_observation": 3,
        "max_new_opened_passages_per_case": 4,
        "max_followup_rounds": 1,
        "canonical_write_back": False,
        "no_frontier_expansion": True,
    }


def ensure_selection(cases: Mapping[str, Mapping[str, Any]], gaps: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    selection = build_selection(cases, gaps)
    path = OUT / "selection.json"
    if path.is_file():
        old = read_json(path, {}) or {}
        if json_hash(old) != json_hash(selection):
            raise RuntimeError("frozen_selection_changed")
    else:
        write_json(path, selection)
    return selection


def passage_text(row: Mapping[str, Any]) -> str:
    return text(row.get("text") or row.get("original_text") or row.get("supplied_text"))


def compact_text(value: str, anchor: str = "", limit: int = 1000) -> str:
    value = text(value)
    if len(value) <= limit:
        return value
    pos = value.find(anchor) if anchor else -1
    start = max(0, pos - limit // 3) if pos >= 0 else 0
    return value[start:start + limit]


def packet_passage_rows(passages: Mapping[str, Mapping[str, Any]], *, refs: Sequence[str] | None = None, anchor: str = "", compact: bool = False) -> list[dict[str, Any]]:
    allowed = set(str(ref) for ref in refs) if refs is not None else set(passages)
    rows: list[dict[str, Any]] = []
    for ref in sorted(passages):
        if ref not in allowed:
            continue
        row = passages[ref]
        value = passage_text(row)
        rows.append({
            "ref": ref,
            "work": text(row.get("work") or row.get("source_work")),
            "layer": text(row.get("layer") or row.get("source_layer")),
            "source_form": text(row.get("source_form")),
            "text": compact_text(value, anchor=anchor, limit=1000) if compact else value,
        })
    return rows


def candidate_blind_packet(selected: Mapping[str, Any], case: Mapping[str, Any], passages: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    observation = case.get("observation") if isinstance(case.get("observation"), Mapping) else {}
    target = {
        "surface": text(selected.get("surface") or observation.get("surface")),
        "exact_span": text(observation.get("exact_span") or selected.get("surface")),
        "source_ref": text(observation.get("source_ref") or selected.get("source_ref")),
        "source_work": text(observation.get("source_work") or selected.get("source_work")),
    }
    return {"target": target, "source_passages": packet_passage_rows(passages)}


def validate_unresolved_observations(payload: Any, passages: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": ["payload_not_object"], "span_failures": 0}
    expected = set(strict_tools.small_card_with_observations_parameters_schema()["properties"])
    errors.extend(f"unknown_top_field:{key}" for key in set(payload) - expected)
    if "unresolved_observations" not in payload:
        errors.append("missing_top_field:unresolved_observations")
        return {"valid": False, "errors": sorted(set(errors)), "span_failures": 0}
    rows = payload.get("unresolved_observations")
    if not isinstance(rows, list):
        return {"valid": False, "errors": [*errors, "unresolved_observations_not_array"], "span_failures": 0}
    if len(rows) > 2:
        errors.append("unresolved_observations_too_many")
    span_failures = 0
    for index, row in enumerate(rows[:2]):
        if not isinstance(row, Mapping):
            errors.append(f"observation[{index}]:not_object")
            continue
        errors.extend(f"observation[{index}]:unknown_field:{key}" for key in set(row) - strict_tools.UNRESOLVED_OBSERVATION_FIELDS)
        for field in strict_tools.UNRESOLVED_OBSERVATION_FIELDS:
            if field not in row:
                errors.append(f"observation[{index}]:missing_{field}")
        ref = text(row.get("source_ref"))
        span = text(row.get("exact_span"))
        if not ref or ref not in passages:
            errors.append(f"observation[{index}]:unknown_source_ref:{ref}")
        elif not span or span not in passage_text(passages[ref]):
            errors.append(f"observation[{index}]:exact_span_not_found:{ref}")
            span_failures += 1
        if not text(row.get("observation")):
            errors.append(f"observation[{index}]:empty_observation")
        terms = row.get("search_terms")
        if not isinstance(terms, list):
            errors.append(f"observation[{index}]:search_terms_not_array")
        else:
            if len(terms) > 3:
                errors.append(f"observation[{index}]:too_many_search_terms")
            for term_index, term in enumerate(terms):
                if not isinstance(term, str) or not text(term):
                    errors.append(f"observation[{index}]:empty_search_term:{term_index}")
    return {"valid": not errors, "errors": sorted(set(errors)), "span_failures": span_failures}


def base_card_from_extended(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(payload[key]) for key in ("target_entity_key", "entities", "assertions", "note") if key in payload}


def classify_small_response(record: Mapping[str, Any], case: Mapping[str, Any], passages: Mapping[str, Mapping[str, Any]], *, extended: bool) -> dict[str, Any]:
    response = record.get("response") if isinstance(record, Mapping) else None
    finish = finish_reason(response if isinstance(response, Mapping) else None)
    if record.get("status") != "response":
        return {"classification": "provider_request_failure", "response_channel": "none", "finish_reason": finish, "validation": None}
    payload, channel, parse_error = controller.extract_strict_tool_payload(response or {})
    if finish == "length":
        return {"classification": "response_truncated", "response_channel": channel, "finish_reason": finish, "parse_error": parse_error, "payload_present": payload is not None, "validation": None}
    if payload is None:
        return {"classification": "response_parse_failure", "response_channel": channel, "finish_reason": finish, "parse_error": parse_error, "payload_present": False, "validation": None}
    observation_validation = {"valid": True, "errors": [], "span_failures": 0}
    base_payload: Any = payload
    if extended:
        observation_validation = validate_unresolved_observations(payload, passages)
        base_payload = base_card_from_extended(payload) if isinstance(payload, Mapping) else payload
    validation = controller.validate_small_card_payload(base_payload, case, passages, require_target=True)
    valid = bool(validation.get("valid")) and bool(observation_validation.get("valid"))
    return {
        "classification": "valid_card" if valid else "card_validation_failure",
        "response_channel": channel,
        "finish_reason": finish,
        "parse_error": parse_error,
        "payload_present": True,
        "validation": {**validation, "unresolved_observations": observation_validation},
        "payload": payload,
        "base_payload": base_payload,
    }


def validate_round2_payload(payload: Any, passages: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": ["payload_not_object"], "finding_rejections": []}
    expected = set(strict_tools.round2_resolution_parameters_schema()["properties"])
    errors.extend(f"unknown_top_field:{key}" for key in set(payload) - expected)
    for field in expected:
        if field not in payload:
            errors.append(f"missing_top_field:{field}")
    if payload.get("status") not in strict_tools.ROUND2_STATUS:
        errors.append(f"invalid_status:{payload.get('status')}")
    findings = payload.get("findings")
    if not isinstance(findings, list):
        errors.append("findings_not_array")
        findings = []
    if len(findings) > 8:
        errors.append("findings_too_many")
    rejected: list[dict[str, Any]] = []
    valid_findings: list[dict[str, Any]] = []
    allowed_finding = {"subject_surface", "predicate", "object_surface", "fact_kind", "source_ref", "exact_span", "confidence"}
    for index, row in enumerate(findings[:8]):
        row_errors: list[str] = []
        if not isinstance(row, Mapping):
            row_errors.append("not_object")
        else:
            row_errors.extend(f"unknown_field:{key}" for key in set(row) - allowed_finding)
            for field in allowed_finding:
                if field not in row:
                    row_errors.append(f"missing_{field}")
            for field in ("subject_surface", "predicate", "object_surface", "source_ref", "exact_span"):
                if not isinstance(row.get(field), str):
                    row_errors.append(f"{field}_not_string")
            if not text(row.get("subject_surface")):
                row_errors.append("empty_subject_surface")
            if not text(row.get("predicate")):
                row_errors.append("empty_predicate")
            if row.get("fact_kind") not in strict_tools.ROUND2_FACT_KINDS:
                row_errors.append(f"invalid_fact_kind:{row.get('fact_kind')}")
            if row.get("confidence") not in schema.CONFIDENCE_LEVELS:
                row_errors.append(f"invalid_confidence:{row.get('confidence')}")
            ref = text(row.get("source_ref"))
            span = text(row.get("exact_span"))
            if not ref or ref not in passages:
                row_errors.append(f"unknown_source_ref:{ref}")
            elif not span or span not in passage_text(passages[ref]):
                row_errors.append(f"exact_span_not_found:{ref}")
        if row_errors:
            rejected.append({"index": index, "finding": dict(row) if isinstance(row, Mapping) else row, "reasons": sorted(set(row_errors))})
        else:
            valid_findings.append(dict(row))
    if controller._provided_ids(payload):
        errors.append("forbidden_or_invented_id")
    return {"valid": not errors and not rejected, "errors": sorted(set(errors)), "valid_findings": valid_findings, "finding_rejections": rejected}


def resolution_packet(selected: Mapping[str, Any], case: Mapping[str, Any], observation: Mapping[str, Any], original_passages: Mapping[str, Mapping[str, Any]], new_passages: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    case_obs = case.get("observation") if isinstance(case.get("observation"), Mapping) else {}
    original_ref = text(case_obs.get("source_ref"))
    refs = [*sorted(new_passages)]
    if original_ref and original_ref in original_passages:
        refs.append(original_ref)
    return {
        "target": {
            "surface": text(selected.get("surface") or case_obs.get("surface")),
            "exact_span": text(case_obs.get("exact_span") or selected.get("surface")),
            "source_ref": original_ref,
            "source_work": text(case_obs.get("source_work") or selected.get("source_work")),
        },
        "observation": {
            "source_ref": text(observation.get("source_ref")),
            "exact_span": text(observation.get("exact_span")),
            "observation": text(observation.get("observation")),
        },
        "source_passages": packet_passage_rows({**original_passages, **new_passages}, refs=refs, anchor=text(observation.get("exact_span")), compact=True),
    }


def record_request(kind: str, case_id: str, payload: Mapping[str, Any], raw_dir: Path, sequence: int, *, function_definition: Mapping[str, Any] | None = None, tool_choice: Mapping[str, Any] | None = None, system: str | None = None, expected_function_name: str | None = None, preflight: bool = False) -> dict[str, Any]:
    started = time.monotonic()
    record: dict[str, Any] = {
        "kind": kind,
        "case_id": case_id,
        "sequence": sequence,
        "start_time": now(),
        "model": MODEL,
        "provider": PROVIDER,
        "endpoint": SEMANTIC_ENDPOINT if function_definition else "https://api.deepseek.com/chat/completions",
        "strict_function": bool(function_definition),
        "function_name": expected_function_name,
        "prompt_version": PROMPT_VERSION,
        "input_hash": json_hash(payload),
        "preflight": preflight,
        "immutable": True,
        "canonical_write_back": False,
    }
    try:
        if preflight:
            response = call_deepseek([{"role": "user", "content": "Reply only with OK"}], model=MODEL, temperature=0, tools=[], max_tokens=16, timeout=60)
        else:
            response = call_deepseek(
                [{"role": "system", "content": system or ""}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)}],
                model=MODEL,
                temperature=0,
                tools=[dict(function_definition)] if function_definition else [],
                tool_choice=tool_choice,
                thinking={"type": "disabled"},
                max_tokens=900 if kind in {"baseline", "round1"} else 650,
                timeout=180,
                endpoint=SEMANTIC_ENDPOINT if function_definition else None,
            )
        record.update({"status": "response", "response": response, "usage": usage_from(response), "finish_reason": finish_reason(response)})
    except Exception as exc:
        http_status = getattr(exc, "http_status", None)
        record.update({
            "status": "provider_rate_limit" if http_status == 429 else "provider_request_failure",
            "response": None,
            "usage": {},
            "finish_reason": None,
            "exception_class": type(exc).__name__,
            "exception_message": str(exc)[:500],
            "http_status": http_status,
        })
    record["elapsed_seconds"] = round(time.monotonic() - started, 6)
    filename = f"{sequence:03d}-{safe_file_part(kind)}-{safe_file_part(case_id)}.json"
    write_json(raw_dir / filename, record)
    return record


def project_baseline(case: Mapping[str, Any], payload: Mapping[str, Any], passages: Mapping[str, Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]]) -> dict[str, Any]:
    internal = strict_tools.small_card_to_controller_card(payload)
    return controller.project_small_card(case, internal, passages, case.get("candidates", []), case.get("constraint_checks", []), [], catalog, index)


def card_findings(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"entities": [], "assertions": []}
    return {
        "entities": [{key: row.get(key) for key in ("entity_key", "surface", "entity_kind", "reference_form", "evidence_refs")} for row in payload.get("entities", []) if isinstance(row, Mapping)],
        "assertions": [{key: row.get(key) for key in ("assertion_id", "assertion_type", "subject_entity_key", "object_entity_key", "evidence_refs", "confidence")} for row in payload.get("assertions", []) if isinstance(row, Mapping)],
    }


def observation_fixture(selected: Mapping[str, Any], passages: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    ref = text(selected.get("source_ref"))
    span = text((passages.get(ref) or {}).get("text"))
    case_surface = text(selected.get("surface"))
    exact = text((passages.get(ref) or {}).get("text"))
    if len(exact) > 80:
        exact = text((selected.get("surface"))) or span[:40]
    return {"source_ref": ref, "exact_span": exact, "observation": f"offline fixture observation for {case_surface}", "search_terms": [case_surface] if case_surface else []}


def offline() -> dict[str, Any]:
    cases, gaps, sources = hardening.load_inputs()
    selection = ensure_selection(cases, gaps)
    catalog = hng02.person_catalog()
    index = hng02.forms_index(catalog)
    rows: list[dict[str, Any]] = []
    for selected in selection["cases"]:
        case = copy.deepcopy(cases[selected["case_id"]])
        case["research_gap"] = dict(gaps[selected["case_id"]])
        passages = hardening.passages_for(selected["case_id"], case, sources)
        ref = text(selected["source_ref"])
        surface = text(selected["surface"])
        kind = "structural_kinship_expression" if surface == "喜弟預女" else ("person_office_title" if surface == "庾太尉" else ("person_title" if surface in {"簡文皇帝", "文帝"} else "named_person"))
        span = text((passages.get(ref) or {}).get("text"))
        span = surface if surface and surface in span else (span[:30] or surface)
        card = {
            "target_entity_key": "e0",
            "entities": [{"entity_key": "e0", "surface": surface, "entity_kind": kind, "reference_form": "abbreviated" if len(surface) <= 1 else ("office_title_only" if surface == "庾太尉" else ("title_only" if kind == "person_title" else "full_name")), "evidence_refs": [ref]}],
            "assertions": [{"assertion_id": "a0", "assertion_type": "person_mention", "subject_entity_key": "e0", "object_entity_key": "", "evidence_refs": [ref], "confidence": "medium"}],
            "note": "fixture only",
            "unresolved_observations": [{"source_ref": ref, "exact_span": span, "observation": f"fixture observation for {surface}", "search_terms": [surface] if surface else []}],
        }
        obs_validation = validate_unresolved_observations(card, passages)
        base_validation = controller.validate_small_card_payload(base_card_from_extended(card), case, passages, require_target=True)
        projection = project_baseline(case, base_card_from_extended(card), passages, catalog, index) if obs_validation["valid"] and base_validation["valid"] else None
        round2 = {"status": "resolved", "findings": [{"subject_surface": surface, "predicate": "person_mention", "object_surface": "", "fact_kind": "other", "source_ref": ref, "exact_span": span, "confidence": "low"}]}
        round2_validation = validate_round2_payload(round2, {ref: passages[ref]}) if ref in passages else {"valid": False, "errors": ["fixture_ref_missing"]}
        rows.append({"case_id": selected["case_id"], "category": selected["category"], "fixture_only": True, "round1_validation": {"base": base_validation, "observations": obs_validation}, "round1_projection": projection, "round2_validation": round2_validation, "api_calls": 0, "canonical_write_back": False})
    result = {"stage": "hng2-sc2-p-offline-replay", "fixture_only": True, "api_calls": 0, "cases": rows, "canonical_write_back": False, "no_frontier_expansion": True}
    write_json(OUT / "offline-replay" / "results.json", result)
    write_json(OUT / "offline-replay" / "manifest.json", {"stage": "hng2-sc2-p-offline-replay", "fixture_only": True, "api_calls": 0, "selection_hash": json_hash(selection), "input_hashes": {"hng2_schema": hash_tree(ROOT / "data/generated/hng2-schema"), "hng2_sc1": hash_tree(ROOT / "data/generated/hng2-schema-controller-small-card")}, "canonical_write_back": False})
    return result


def classify_round2(record: Mapping[str, Any], passages: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    response = record.get("response") if isinstance(record, Mapping) else None
    finish = finish_reason(response if isinstance(response, Mapping) else None)
    if record.get("status") != "response":
        return {"classification": "provider_request_failure", "response_channel": "none", "finish_reason": finish, "validation": None}
    payload, channel, parse_error = controller.extract_strict_tool_payload(response or {}, expected_function_name=strict_tools.ROUND2_FUNCTION_NAME)
    if finish == "length":
        return {"classification": "response_truncated", "response_channel": channel, "finish_reason": finish, "parse_error": parse_error, "validation": None}
    if payload is None:
        return {"classification": "response_parse_failure", "response_channel": channel, "finish_reason": finish, "parse_error": parse_error, "validation": None}
    validation = validate_round2_payload(payload, passages)
    return {"classification": "valid_resolution" if validation.get("valid") else "resolution_validation_failure", "response_channel": channel, "finish_reason": finish, "parse_error": parse_error, "validation": validation, "payload": payload}


def retrieve_observation(case: Mapping[str, Any], observation: Mapping[str, Any], current_passages: Mapping[str, Mapping[str, Any]], punctuated: Sequence[Mapping[str, Any]], legacy: Sequence[Mapping[str, Any]], remaining: int) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    terms = [text(term) for term in observation.get("search_terms", []) if text(term)]
    plan = {"search_entities": terms, "search_patterns": terms}
    seen = set(current_passages)
    profile = base._source_profile(case, plan)
    found = hng1_common.find_punctuated_first(profile, punctuated, legacy, top_k=6)
    opened = hng1_common.open_short_hits(found, punctuated, legacy, max_passages=max(1, min(4, remaining)))
    opened_rows: dict[str, dict[str, Any]] = {}
    for row in opened:
        ref = text(row.get("source_ref"))
        if not ref or ref in seen or ref in opened_rows:
            continue
        snippet = text(row.get("snippet") or row.get("text"))
        opened_rows[ref] = {
            "ref": ref,
            "work": row.get("work"),
            "layer": row.get("source_layer") or row.get("layer"),
            "source_form": row.get("source_form") or "legacy_local",
            "text": snippet,
            "original_text": text(row.get("original_text") or snippet),
            "locator": row.get("locator") or {},
        }
    new_refs = sorted(opened_rows)[:max(0, remaining)]
    new_rows = {ref: opened_rows[ref] for ref in new_refs}
    trace = {
        "profile_person_id": profile.get("person_id"),
        "routes": found.get("routes", []),
        "retrieved_refs": sorted(text(hit.get("source_ref")) for hit in found.get("hits", []) if text(hit.get("source_ref"))),
        "observation_source_ref": text(observation.get("source_ref")),
        "search_terms": terms,
        "opened_refs": sorted(opened_rows),
        "new_opened_refs": new_refs,
        "deduplicated_refs": sorted(set(text(row.get("source_ref")) for row in opened if text(row.get("source_ref")) in seen)),
        "opened_chars": sum(len(passage_text(row)) for row in new_rows.values()),
        "new_passages": list(new_rows.values()),
        "used_refs": [],
        "new_used_refs": [],
    }
    return {**current_passages, **new_rows}, trace


def run_case_live(selected: Mapping[str, Any], case: Mapping[str, Any], passages: Mapping[str, Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]], punctuated: Sequence[Mapping[str, Any]], legacy: Sequence[Mapping[str, Any]], raw_dir: Path, sequence: int) -> tuple[dict[str, Any], int, list[dict[str, Any]]]:
    case_id = text(selected.get("case_id"))
    packet = candidate_blind_packet(selected, case, passages)
    baseline_record = record_request("baseline", case_id, packet, raw_dir, sequence, function_definition=strict_tools.small_card_function_definition(), tool_choice=strict_tools.strict_tool_choice(), system=small.SEMANTIC_SYSTEM, expected_function_name=strict_tools.FUNCTION_NAME)
    sequence += 1
    baseline_class = classify_small_response(baseline_record, case, passages, extended=False)
    baseline_projection = project_baseline(case, baseline_class["payload"], passages, catalog, index) if baseline_class.get("classification") == "valid_card" else None
    baseline_row = {
        "case_id": case_id,
        "category": selected.get("category"),
        "classification": baseline_class.get("classification"),
        "validation": baseline_class.get("validation"),
        "findings": card_findings(baseline_class.get("payload")),
        "projection": baseline_projection,
        "canonical_write_back": False,
    }

    round1_record = record_request("round1", case_id, packet, raw_dir, sequence, function_definition=strict_tools.small_card_with_observations_function_definition(), tool_choice=strict_tools.strict_tool_choice(), system=R1_SYSTEM, expected_function_name=strict_tools.FUNCTION_NAME)
    sequence += 1
    round1_class = classify_small_response(round1_record, case, passages, extended=True)
    round1_projection = project_baseline(case, round1_class["base_payload"], passages, catalog, index) if round1_class.get("classification") == "valid_card" else None
    observations = []
    if round1_class.get("classification") == "valid_card":
        observations = [dict(row) for row in (round1_class.get("payload") or {}).get("unresolved_observations", []) if isinstance(row, Mapping)]
    round1_row = {
        "case_id": case_id,
        "category": selected.get("category"),
        "classification": round1_class.get("classification"),
        "validation": round1_class.get("validation"),
        "findings": card_findings(round1_class.get("base_payload")),
        "unresolved_observations": observations,
        "projection": round1_projection,
        "canonical_write_back": False,
    }

    retrieval_rows: list[dict[str, Any]] = []
    round2_rows: list[dict[str, Any]] = []
    all_passages = dict(passages)
    remaining = 4
    for obs_index, observation in enumerate(observations[:2]):
        if remaining <= 0:
            break
        retrieved, trace = retrieve_observation(case, observation, all_passages, punctuated, legacy, remaining)
        new_refs = list(trace.get("new_opened_refs", []))
        retrieval_rows.append({"case_id": case_id, "observation_index": obs_index, **trace, "canonical_write_back": False})
        new_rows = {ref: retrieved[ref] for ref in new_refs if ref in retrieved}
        remaining -= len(new_rows)
        all_passages.update(new_rows)
        if not new_rows:
            round2_rows.append({"observation_index": obs_index, "status": "not_run_no_new_passage", "observation": observation, "canonical_write_back": False})
            continue
        r2_packet = resolution_packet(selected, case, observation, passages, new_rows)
        r2_record = record_request("round2", f"{case_id}-obs-{obs_index}", r2_packet, raw_dir, sequence, function_definition=strict_tools.round2_resolution_function_definition(), tool_choice=strict_tools.round2_tool_choice(), system=R2_SYSTEM, expected_function_name=strict_tools.ROUND2_FUNCTION_NAME)
        sequence += 1
        r2_class = classify_round2(r2_record, {**new_rows, **({text((case.get("observation") or {}).get("source_ref")): passages[text((case.get("observation") or {}).get("source_ref"))]} if text((case.get("observation") or {}).get("source_ref")) in passages else {})})
        validation = r2_class.get("validation") or {}
        valid_findings = list(validation.get("valid_findings", [])) if r2_class.get("classification") == "valid_resolution" else []
        for row in retrieval_rows:
            if row.get("observation_index") == obs_index:
                used = sorted(set(text(item.get("source_ref")) for item in valid_findings if text(item.get("source_ref"))))
                row["used_refs"] = used
                row["new_used_refs"] = sorted(set(used) & set(new_refs))
        round2_rows.append({
            "observation_index": obs_index,
            "observation": observation,
            "packet_hash": json_hash(r2_packet),
            "classification": r2_class.get("classification"),
            "validation": validation,
            "supported_findings": valid_findings,
            "new_supported_findings": [row for row in valid_findings if text(row.get("source_ref")) in set(new_refs)],
            "rejected_findings": validation.get("finding_rejections", []),
            "canonical_write_back": False,
        })
    case_row = {
        "case_id": case_id,
        "category": selected.get("category"),
        "baseline": baseline_row,
        "round1": round1_row,
        "retrieval": retrieval_rows,
        "round2": round2_rows,
        "canonical_write_back": False,
        "no_frontier_expansion": True,
    }
    return case_row, sequence, retrieval_rows


def live(run_id: str) -> dict[str, Any]:
    cases, gaps, sources = hardening.load_inputs()
    selection = ensure_selection(cases, gaps)
    run_dir = OUT / "live" / run_id
    raw_dir = run_dir / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "selection.json", selection)
    preflight = record_request("preflight", "preflight", {"purpose": "authenticated_transport_preflight", "model": MODEL}, raw_dir, 1, preflight=True)
    if preflight.get("status") != "response":
        write_json(run_dir / "metrics.json", {"stage": "hng2-sc2-p-live", "preflight_succeeded": False, "execution_environment_failure": True, "canonical_write_back": False})
        raise RuntimeError("live_network_unavailable")
    catalog = hng02.person_catalog()
    index = hng02.forms_index(catalog)
    punctuated, legacy = hng1_common.load_retrieval_sources()
    rows: list[dict[str, Any]] = []
    retrieval_rows: list[dict[str, Any]] = []
    sequence = 2
    for selected in selection["cases"]:
        case = copy.deepcopy(cases[selected["case_id"]])
        case["research_gap"] = dict(gaps[selected["case_id"]])
        passages = hardening.passages_for(selected["case_id"], case, sources)
        row, sequence, traces = run_case_live(selected, case, passages, catalog, index, punctuated, legacy, raw_dir, sequence)
        rows.append(row)
        retrieval_rows.extend(traces)

    baseline_valid = sum(row.get("baseline", {}).get("classification") == "valid_card" for row in rows)
    r1_valid = sum(row.get("round1", {}).get("classification") == "valid_card" for row in rows)
    new_findings = [finding for row in rows for r2 in row.get("round2", []) for finding in r2.get("new_supported_findings", [])]
    all_supported = [finding for row in rows for r2 in row.get("round2", []) for finding in r2.get("supported_findings", [])]
    rejected = [finding for row in rows for r2 in row.get("round2", []) for finding in r2.get("rejected_findings", [])]
    useful_searches = sum(bool(trace.get("new_used_refs")) for trace in retrieval_rows)
    controls = {"control_title_known", "control_required_new_person"}
    control_noise = sum(len(row.get("round2", [])[i].get("supported_findings", [])) for row in rows if row.get("category") in controls for i in range(len(row.get("round2", []))))
    cases_with_new_supported = sum(1 for row in rows if any(r2.get("new_supported_findings") for r2 in row.get("round2", [])))
    api_records = [read_json(path, {}) or {} for path in sorted(raw_dir.glob("*.json"))]
    response_records = [row for row in api_records if row.get("status") == "response"]
    latencies = [float(row.get("elapsed_seconds")) for row in response_records if row.get("elapsed_seconds") is not None]
    usage = {key: sum(int(row.get("usage", {}).get(key) or 0) for row in api_records) for key in ("prompt_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens", "total_tokens")}
    summary = {
        "stage": "hng2-sc2-p-live",
        "run_id": run_id,
        "selected_cases": len(rows),
        "baseline_valid_cards": baseline_valid,
        "round1_valid_cards": r1_valid,
        "cases_with_new_supported_information": cases_with_new_supported,
        "total_new_supported_findings": len(new_findings),
        "unsupported_followup_findings": len(rejected),
        "followup_searches_with_useful_new_evidence": useful_searches,
        "control_followup_finding_count": control_noise,
        "api_calls": len(api_records),
        "baseline_calls": len(rows),
        "round1_calls": len(rows),
        "round2_calls": sum(1 for row in rows for r2 in row.get("round2", []) if r2.get("classification")),
        "round2_supported_finding_count": len(all_supported),
        "retrieval_observation_count": len(retrieval_rows),
        "new_passage_count": sum(len(trace.get("new_opened_refs", [])) for trace in retrieval_rows),
        "usage": usage,
        "median_latency_seconds": statistics.median(latencies) if latencies else 0,
        "max_latency_seconds": max(latencies) if latencies else 0,
        "response_failures": sum(row.get("status") != "response" for row in api_records),
        "canonical_write_back": False,
        "no_frontier_expansion": True,
    }
    write_json(run_dir / "baseline-results.json", {"stage": "hng2-sc2-p-baseline", "cases": [{"case_id": row["case_id"], **row["baseline"]} for row in rows], "canonical_write_back": False})
    write_json(run_dir / "round1-results.json", {"stage": "hng2-sc2-p-round1", "cases": [{"case_id": row["case_id"], **row["round1"]} for row in rows], "canonical_write_back": False})
    write_json(run_dir / "retrieval-trace.json", {"stage": "hng2-sc2-p-retrieval", "traces": retrieval_rows, "canonical_write_back": False})
    write_json(run_dir / "round2-results.json", {"stage": "hng2-sc2-p-round2", "cases": [{"case_id": row["case_id"], "round2": row.get("round2", [])} for row in rows], "canonical_write_back": False})
    write_json(run_dir / "case-results.json", {"stage": "hng2-sc2-p", "cases": rows, "canonical_write_back": False})
    write_json(run_dir / "summary.json", summary)
    write_json(run_dir / "metrics.json", summary)
    write_json(run_dir / "manifest.json", {
        "stage": "hng2-sc2-p-live",
        "run_id": run_id,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "baseline_function": strict_tools.small_card_function_definition(),
        "round1_function": strict_tools.small_card_with_observations_function_definition(),
        "round2_function": strict_tools.round2_resolution_function_definition(),
        "selection_hash": json_hash(selection),
        "input_hashes": {"hng2_schema": hash_tree(ROOT / "data/generated/hng2-schema"), "hng2_sc1": hash_tree(ROOT / "data/generated/hng2-schema-controller-small-card")},
        "raw_api_root": str(raw_dir.relative_to(ROOT)),
        "canonical_write_back": False,
        "no_frontier_expansion": True,
    })
    return {"run_id": run_id, "summary": summary, "cases": rows, "output_root": str(run_dir.relative_to(ROOT))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="run deterministic fixture/retrieval plumbing only")
    parser.add_argument("--live", action="store_true", help="run the frozen live baseline and one follow-up round")
    parser.add_argument("--run-id", default=dt.datetime.now().strftime("%Y%m%dT%H%M%S") + "-HNG2-SC2-P", help="live run directory identifier")
    args = parser.parse_args()
    if args.live and args.offline:
        parser.error("choose only one of --offline or --live")
    result = offline() if not args.live else live(args.run_id)
    print(json.dumps({"stage": result.get("stage") or result.get("summary", {}).get("stage"), "output_root": result.get("output_root", str(OUT.relative_to(ROOT))), "summary": result.get("summary", {"api_calls": result.get("api_calls", 0)})}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
