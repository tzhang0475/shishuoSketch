#!/usr/bin/env python3
"""HNG2-SC small Historical Evidence Card replay and five-case validation.

The semantic request in this runner is deliberately candidate-blind.  The
strict tool returns only textual entities and source references; the existing
Python controller performs all candidate, constraint, identity and gap
projection afterwards.  The older large-card namespaces are never touched.
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
import hng2_schema_controller as controller  # noqa: E402
import hng2_schema_strict_tools as strict_tools  # noqa: E402
import historical_entity_schema as schema  # noqa: E402
import run_hng2_schema_controller_hardening as hardening  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402


OUT = ROOT / "data/generated/hng2-schema-controller-small-card"
MODEL = "deepseek-v4-flash"
PROVIDER = "deepseek"
PROMPT_VERSION = "hng2-sc1-small-evidence-card-v1"
SEMANTIC_ENDPOINT = strict_tools.STRICT_COMPLETIONS_ENDPOINT

SEMANTIC_SYSTEM = """先阅读给定的历史史料，理解当前 target 在这些原文中的文字意义，并只提交解决当前目标所必需的最小证据卡。
只使用输入的 source_passages；保持 target 与同段上下文人物分开。只有原文直接支持的实体关系才能形成断言，共现本身不是关系。合并能够确定为同一局部实体的重复指称，优先使用最少的必要实体和出处；不要枚举无关事件。
你只负责记录史料文字证据，不作数据库身份、候选、约束、ResearchGap 或图谱决定；不确定时保留不确定性。所有出处只能引用输入 passage ref，不创建任何数据库 ID。请只通过被强制调用的工具提交结果，不输出助手 prose。"""


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


def finish_reason(response: Mapping[str, Any] | None) -> str | None:
    choices = response.get("choices") if isinstance(response, Mapping) else None
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        return text(choices[0].get("finish_reason")) or None
    return None


def usage_from(response: Mapping[str, Any] | None) -> dict[str, int]:
    usage = response.get("usage") if isinstance(response, Mapping) else {}
    usage = usage if isinstance(usage, Mapping) else {}
    return {key: int(usage.get(key) or 0) for key in ("prompt_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens", "total_tokens")}


def candidate_blind_packet(selected: Mapping[str, Any], case: Mapping[str, Any], passages: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    observation = case.get("observation") if isinstance(case.get("observation"), Mapping) else {}
    target = {
        "surface": text(selected.get("surface") or observation.get("surface")),
        "exact_span": text(observation.get("exact_span") or selected.get("surface")),
        "source_ref": text(observation.get("source_ref") or selected.get("source_ref")),
        "source_work": text(observation.get("source_work")),
    }
    source_rows = []
    for ref in sorted(passages):
        row = passages[ref]
        source_rows.append({
            "ref": ref,
            "work": text(row.get("work") or row.get("source_work")),
            "layer": text(row.get("layer") or row.get("source_layer")),
            "source_form": text(row.get("source_form")),
            "text": text(row.get("text") or row.get("original_text")),
        })
    return {"target": target, "source_passages": source_rows}


def make_small_fixture(kind: str, ref: str) -> dict[str, Any]:
    """Create offline cards from the five frozen cases, not new model output."""

    if kind == "title_existing":
        entities = [
            {"entity_key": "e0", "surface": "庾太尉", "entity_kind": "person_office_title", "reference_form": "office_title_only", "evidence_refs": [ref]},
            {"entity_key": "e1", "surface": "庾亮", "entity_kind": "named_person", "reference_form": "full_name", "evidence_refs": [ref]},
        ]
        assertions = [{"assertion_id": "a0", "assertion_type": "title_of", "subject_entity_key": "e0", "object_entity_key": "e1", "evidence_refs": [ref], "confidence": "high"}]
    elif kind == "genuine_unresolved":
        entities = [{"entity_key": "e0", "surface": "宣", "entity_kind": "abbreviated_name", "reference_form": "abbreviated", "evidence_refs": [ref]}]
        assertions = [{"assertion_id": "a0", "assertion_type": "person_mention", "subject_entity_key": "e0", "object_entity_key": "", "evidence_refs": [ref], "confidence": "medium"}]
    elif kind == "abbreviated_existing":
        entities = [
            {"entity_key": "e0", "surface": "廙", "entity_kind": "abbreviated_name", "reference_form": "abbreviated", "evidence_refs": [ref]},
            {"entity_key": "e1", "surface": "王廙", "entity_kind": "named_person", "reference_form": "full_name", "evidence_refs": [ref]},
        ]
        assertions = [{"assertion_id": "a0", "assertion_type": "identity_equivalence", "subject_entity_key": "e0", "object_entity_key": "e1", "evidence_refs": [ref], "confidence": "high"}]
    elif kind == "new_person":
        entities = [{"entity_key": "e0", "surface": "陳騫", "entity_kind": "named_person", "reference_form": "full_name", "evidence_refs": [ref]}]
        assertions = [{"assertion_id": "a0", "assertion_type": "person_mention", "subject_entity_key": "e0", "object_entity_key": "", "evidence_refs": [ref], "confidence": "high"}]
    elif kind == "kinship_target_separation":
        entities = [
            {"entity_key": "e0", "surface": "虞喜", "entity_kind": "named_person", "reference_form": "full_name", "evidence_refs": [ref]},
            {"entity_key": "e1", "surface": "喜弟預女", "entity_kind": "structural_kinship_expression", "reference_form": "kinship_plus_name", "evidence_refs": [ref]},
        ]
        assertions = [{"assertion_id": "a0", "assertion_type": "kinship_relation", "subject_entity_key": "e0", "object_entity_key": "e1", "evidence_refs": [ref], "confidence": "high"}]
    else:
        raise ValueError(f"unknown_small_fixture:{kind}")
    return {"target_entity_key": "e0", "entities": entities, "assertions": assertions, "note": "offline fixture"}


def process_small_card(case: Mapping[str, Any], card: Mapping[str, Any], passages: Mapping[str, Mapping[str, Any]], catalog: Mapping[str, Mapping[str, Any]], index: Mapping[str, Sequence[str]]) -> dict[str, Any]:
    validation = controller.validate_small_card_payload(card, case, passages, require_target=True)
    result: dict[str, Any] = {"validation": validation, "projection": None, "canonical_write_back": False}
    if validation.get("valid"):
        internal = strict_tools.small_card_to_controller_card(card)
        result["projection"] = controller.project_small_card(case, internal, passages, case.get("candidates", []), case.get("constraint_checks", []), [], catalog, index)
    return result


def offline_replay() -> dict[str, Any]:
    cases, gaps, sources = hardening.load_inputs()
    selection = hardening.build_selection(cases, gaps)
    catalog = hng02.person_catalog()
    index = hng02.forms_index(catalog)
    rows = []
    for selected in selection["cases"]:
        case = copy.deepcopy(cases[selected["case_id"]])
        case["research_gap"] = dict(gaps[selected["case_id"]])
        passages = hardening.passages_for(selected["case_id"], case, sources)
        card = make_small_fixture(selected["category"], selected["source_ref"])
        processed = process_small_card(case, card, passages, catalog, index)
        rows.append({"case_id": selected["case_id"], "category": selected["category"], "card": card, **processed})

    # The target/context distinction is also replayed with the actual frozen
    # 虞喜 passage, but the target is deliberately switched to the contextual
    # structural entity for the negative control.
    yuxi = next(row for row in rows if row["category"] == "kinship_target_separation")
    structural_card = copy.deepcopy(yuxi["card"])
    structural_card["target_entity_key"] = "e1"
    structural_case = copy.deepcopy(cases[yuxi["case_id"]])
    structural_case["research_gap"] = dict(gaps[yuxi["case_id"]])
    structural_passages = hardening.passages_for(yuxi["case_id"], structural_case, sources)
    structural = process_small_card(structural_case, structural_card, structural_passages, catalog, index)

    projections = [row.get("projection") for row in rows if isinstance(row.get("projection"), Mapping)]
    statuses = [text((p.get("identity_decision") or {}).get("identity_status")) for p in projections]
    metrics = {
        "stage": "hng2-schema-controller-small-card-replay",
        "api_calls": 0,
        "selected_cases": len(rows),
        "valid_cards": sum(bool((row.get("validation") or {}).get("valid")) for row in rows),
        "invalid_cards": sum(not bool((row.get("validation") or {}).get("valid")) for row in rows),
        "resolved_existing": statuses.count("resolved_existing"),
        "resolved_new_candidate": statuses.count("resolved_new_candidate"),
        "unresolved": statuses.count("unresolved"),
        "structural_target_status": text((structural.get("projection") or {}).get("identity_decision", {}).get("identity_status")),
        "identity_propagation_count": sum(len((p.get("candidate_info") or {}).get("identity_propagations", [])) for p in projections),
        "candidate_upgrade_count": sum(len((p.get("state_delta") or {}).get("upgraded_candidates", [])) for p in projections),
        "canonical_write_back": False,
    }
    replay_dir = OUT / "offline-replay"
    write_json(replay_dir / "selection.json", selection)
    write_json(replay_dir / "cards.json", {"rows": rows, "structural_target_regression": structural, "canonical_write_back": False})
    write_json(replay_dir / "metrics.json", metrics)
    write_json(replay_dir / "manifest.json", {
        "stage": "hng2-schema-controller-small-card-replay",
        "schema": schema.SCHEMA_VERSION,
        "small_card_schema_hash": strict_tools.small_card_schema_hash(),
        "api_calls": 0,
        "canonical_write_back": False,
        "input_hashes": {"hng2_schema": hash_tree(ROOT / "data/generated/hng2-schema"), "hng2_sc07_raw": hash_tree(hardening.SC_RAW)},
    })
    return {"selection": selection, "rows": rows, "structural_target_regression": structural, "metrics": metrics}


def record_request(kind: str, case_id: str, payload: Mapping[str, Any], raw_dir: Path, sequence: int, *, preflight: bool = False) -> dict[str, Any]:
    started = time.monotonic()
    record: dict[str, Any] = {
        "kind": kind, "case_id": case_id, "sequence": sequence, "start_time": now(),
        "model": MODEL, "provider": PROVIDER, "endpoint": SEMANTIC_ENDPOINT if kind == "semantic" else "https://api.deepseek.com/chat/completions",
        "strict_function": kind == "semantic", "prompt_version": PROMPT_VERSION, "input_hash": json_hash(payload),
        "canonical_write_back": False, "immutable": True, "preflight": preflight,
    }
    try:
        if kind == "preflight":
            response = call_deepseek([{"role": "user", "content": "Reply only with OK"}], model=MODEL, temperature=0, tools=[], max_tokens=16, timeout=60)
        else:
            messages = [{"role": "system", "content": SEMANTIC_SYSTEM}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)}]
            response = call_deepseek(messages, model=MODEL, temperature=0, tools=[strict_tools.small_card_function_definition()], tool_choice=strict_tools.strict_tool_choice(), thinking={"type": "disabled"}, max_tokens=900, timeout=180, endpoint=SEMANTIC_ENDPOINT)
        record.update({"status": "response", "response": response, "usage": usage_from(response), "finish_reason": finish_reason(response)})
        if kind == "semantic":
            _, channel, parse_error = controller.extract_strict_tool_payload(response)
            choices = response.get("choices") if isinstance(response, Mapping) else []
            message = choices[0].get("message") if isinstance(choices, list) and choices and isinstance(choices[0], Mapping) else {}
            tool_calls = message.get("tool_calls") if isinstance(message, Mapping) else []
            first = tool_calls[0] if isinstance(tool_calls, list) and tool_calls and isinstance(tool_calls[0], Mapping) else {}
            function = first.get("function") if isinstance(first, Mapping) and isinstance(first.get("function"), Mapping) else {}
            record.update({"response_channel": channel, "parse_error": parse_error, "tool_call_count": len(tool_calls) if isinstance(tool_calls, list) else 0, "tool_name": function.get("name")})
    except Exception as exc:
        http_status = getattr(exc, "http_status", None)
        record.update({"status": "provider_rate_limit" if http_status == 429 else "provider_request_failure", "response": None, "usage": {}, "response_channel": "none", "finish_reason": None, "exception_class": type(exc).__name__, "exception_message": str(exc)[:500], "http_status": http_status})
    record["elapsed_seconds"] = round(time.monotonic() - started, 6)
    write_json(raw_dir / f"{sequence:03d}-{kind}-{case_id}.json", record)
    return record


def classify_semantic(record: Mapping[str, Any], case: Mapping[str, Any], passages: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    response = record.get("response") if isinstance(record, Mapping) else None
    finish = finish_reason(response if isinstance(response, Mapping) else None)
    if record.get("status") != "response":
        return {"classification": "provider_request_failure", "response_channel": "none", "finish_reason": finish, "validation": None}
    payload, channel, parse_error = controller.extract_strict_tool_payload(response or {})
    if finish == "length":
        return {"classification": "response_truncated", "response_channel": channel, "finish_reason": finish, "parse_error": parse_error, "validation": None}
    if payload is None:
        return {"classification": "response_parse_failure", "response_channel": channel, "finish_reason": finish, "parse_error": parse_error, "validation": None}
    validation = controller.validate_small_card_payload(payload, case, passages, require_target=True)
    return {"classification": "valid_card" if validation.get("valid") else "card_validation_failure", "response_channel": channel, "finish_reason": finish, "parse_error": parse_error, "validation": validation, "payload": payload}


def live(run_id: str) -> dict[str, Any]:
    cases, gaps, sources = hardening.load_inputs()
    selection = hardening.build_selection(cases, gaps)
    live_out = OUT / "live" / run_id
    raw_dir = live_out / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=True)
    write_json(live_out / "selection.json", selection)
    preflight_payload = {"purpose": "authenticated_transport_preflight", "model": MODEL}
    preflight = record_request("preflight", "preflight", preflight_payload, raw_dir, 1, preflight=True)
    if preflight.get("status") != "response":
        write_json(live_out / "metrics.json", {"stage": "hng2-schema-controller-small-card-live", "preflight_succeeded": False, "execution_environment_failure": True, "canonical_write_back": False})
        raise RuntimeError("live_network_unavailable")

    catalog = hng02.person_catalog()
    index = hng02.forms_index(catalog)
    validations = []
    runs = []
    sequence = 2
    for selected in selection["cases"]:
        case_id = selected["case_id"]
        case = copy.deepcopy(cases[case_id])
        case["research_gap"] = dict(gaps[case_id])
        passages = hardening.passages_for(case_id, case, sources)
        packet = candidate_blind_packet(selected, case, passages)
        record = record_request("semantic", case_id, packet, raw_dir, sequence)
        sequence += 1
        classification = classify_semantic(record, case, passages)
        validation_row = {"case_id": case_id, "category": selected["category"], **{key: classification.get(key) for key in ("classification", "response_channel", "finish_reason", "parse_error")}, "validation": classification.get("validation"), "canonical_write_back": False}
        validations.append(validation_row)
        run = {"case_id": case_id, "category": selected["category"], "target_packet_hash": json_hash(packet), "classification": classification.get("classification"), "canonical_write_back": False}
        if classification.get("classification") == "valid_card":
            card = classification["payload"]
            internal = strict_tools.small_card_to_controller_card(card)
            projection = controller.project_small_card(case, internal, passages, case.get("candidates", []), case.get("constraint_checks", []), [], catalog, index)
            run.update({"card": card, "projection": projection})
        runs.append(run)
    response_records = [read_json(path, {}) or {} for path in sorted(raw_dir.glob("*-*.json"))]
    semantic_records = [row for row in response_records if row.get("kind") == "semantic"]
    valid_cards = [row for row in validations if row.get("classification") == "valid_card"]
    projections = [row.get("projection") for row in runs if isinstance(row.get("projection"), Mapping)]
    latencies = [float(row.get("elapsed_seconds")) for row in response_records if row.get("status") == "response" and row.get("elapsed_seconds") is not None]
    usage = {key: sum(int(row.get("usage", {}).get(key) or 0) for row in response_records) for key in ("prompt_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens", "total_tokens")}
    status_values = [text((row.get("projection") or {}).get("identity_decision", {}).get("identity_status")) for row in runs if isinstance(row.get("projection"), Mapping)]
    metrics = {
        "stage": "hng2-schema-controller-small-card-live", "selected_cases": len(selection["cases"]), "api_calls": len(response_records), "preflight_succeeded": True, "semantic_calls": len(semantic_records), "valid_strict_tool_calls": sum(row.get("response_channel") == "tool_call" and row.get("tool_name") == strict_tools.FUNCTION_NAME for row in semantic_records), "valid_cards": len(valid_cards), "card_validation_failures": sum(row.get("classification") == "card_validation_failure" for row in validations), "response_truncated": sum(row.get("classification") == "response_truncated" for row in validations), "response_parse_failures": sum(row.get("classification") == "response_parse_failure" for row in validations), "resolved_existing": status_values.count("resolved_existing"), "resolved_new_candidate": status_values.count("resolved_new_candidate"), "unresolved": status_values.count("unresolved"), "not_single_person": status_values.count("not_single_person"), "identity_propagations": sum(len((p.get("candidate_info") or {}).get("identity_propagations", [])) for p in projections), "undefined_field_outputs": sum(sum("unknown_field:" in str(error) or str(error).startswith("unknown_top_field:") for error in ((row.get("validation") or {}).get("errors", []) if isinstance(row.get("validation"), Mapping) else [])) for row in validations), "invented_id_attempts": sum(len((row.get("validation") or {}).get("invented_id_attempts", [])) for row in validations if isinstance(row.get("validation"), Mapping)), "usage": usage, "median_latency_seconds": statistics.median(latencies) if latencies else 0, "max_latency_seconds": max(latencies) if latencies else 0, "small_card_schema_hash": strict_tools.small_card_schema_hash(), "strict_endpoint": SEMANTIC_ENDPOINT, "prompt_version": PROMPT_VERSION, "canonical_write_back": False, "no_additional_semantic_calls": True,
    }
    write_json(live_out / "semantic-cards.json", {"schema": schema.SCHEMA_VERSION, "validations": validations, "canonical_write_back": False})
    write_json(live_out / "case-runs.json", {"schema": schema.SCHEMA_VERSION, "runs": runs, "canonical_write_back": False})
    write_json(live_out / "metrics.json", metrics)
    write_json(live_out / "manifest.json", {"schema": schema.SCHEMA_VERSION, "stage": "hng2-schema-controller-small-card-live", "run_id": run_id, "selection_hash": json_hash(selection), "small_card_schema_hash": strict_tools.small_card_schema_hash(), "strict_endpoint": SEMANTIC_ENDPOINT, "prompt_version": PROMPT_VERSION, "raw_api_root": str(raw_dir.relative_to(ROOT)), "input_hashes": {"hng2_schema": hash_tree(ROOT / "data/generated/hng2-schema"), "hng2_sc07_raw": hash_tree(hardening.SC_RAW)}, "canonical_write_back": False})
    return {"selection": selection, "runs": runs, "validations": validations, "metrics": metrics, "output_root": str(live_out.relative_to(ROOT))}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("replay", "live"), default="replay")
    parser.add_argument("--run-id", default=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    result = offline_replay() if args.mode == "replay" else live(args.run_id)
    if not args.quiet:
        print(json.dumps(result.get("metrics", {}), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
