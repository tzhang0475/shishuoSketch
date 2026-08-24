#!/usr/bin/env python3
"""Run the consolidated HNG2 historical-context algorithm.

The default command is an offline plumbing replay.  The explicit live mode
uses one strict semantic call per frozen case and never performs a search
round or frontier expansion.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import historical_context_algorithm as algorithm  # noqa: E402
import hng2_schema_controller as controller  # noqa: E402
import historical_entity_schema as entity_schema  # noqa: E402
import run_hng2_schema_controller_hardening as hardening  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402


OUT = ROOT / "data/generated/hng2-consolidation"
MODEL = "deepseek-v4-flash"
PROVIDER = "deepseek"
RUN_VERSION = "hng2-c-v1"
PROMPT_VERSION = "hng2-c-historical-evidence-card-v1"
PREVIOUS_PACKET_LIMIT = 10_000

# These are existing frozen cases, not new research targets.  The categories
# make the live sample auditable while the selection key prevents reordering.
FROZEN_CASES = (
    ("identity_abbreviation", "hng1r2-hng1-raw-relation-921d528c3cf9154fa43c"),
    ("identity_abbreviation", "hng1r2-hng1-raw-relation-7d036391e66574c6f83b"),
    ("title_office", "hng1r2-hng1-raw-relation-2ff2066d8872cbae15f7"),
    ("title_office", "hng2-live-hng2-live-w1-identity-33afe84247b036e9d9cb"),
    ("kinship_marriage", "hng1r2-hng1-raw-relation-b97bdeb3fbec092978bc"),
    ("kinship_marriage", "hng2-hng02-relation-2164c52caaa53337435e"),
    ("interaction_institutional", "hng1r2-hng1-raw-time-5b69a7fab74c509e5426"),
    ("interaction_institutional", "hng1r2-hng1-raw-relation-8d947d5beb14036a7d9f"),
    ("temporal_rich", "hng2-live-hng2-live-w1-temporal-7787c8e7d9f2c14fc5b5"),
    ("temporal_rich", "hng1r2-hng1-raw-time-46252a6e46037881a4da"),
    ("negative_control", "hng1r2-hng1-raw-relation-1153a723032c48422396"),
    ("negative_control", "hng1r2-hng1-raw-relation-e5db687ff626c0efa13e"),
)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + chr(10),
        encoding="utf-8",
    )


def stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def usage(response: Mapping[str, Any]) -> dict[str, int]:
    raw = response.get("usage") if isinstance(response, Mapping) else {}
    raw = raw if isinstance(raw, Mapping) else {}
    return {
        key: int(raw.get(key) or 0)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }


def finish_reason(response: Mapping[str, Any]) -> str | None:
    choices = response.get("choices") if isinstance(response, Mapping) else None
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        return str(choices[0].get("finish_reason") or "") or None
    return None


def safe_error(exc: Exception) -> dict[str, Any]:
    body = str(getattr(exc, "provider_error_body", "") or "")
    secret = os.environ.get("DEEPSEEK_API_KEY")
    if secret:
        body = body.replace(secret, "[REDACTED]")
    message = str(exc)
    if secret:
        message = message.replace(secret, "[REDACTED]")
    return {
        "exception_class": type(exc).__name__,
        "exception_message": message,
        "http_status": getattr(exc, "http_status", None),
        "provider_error_body": body[:4000],
    }


def load_frozen_inputs() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    cases, gaps, sources = hardening.load_inputs()
    return cases, gaps, sources


def build_selection() -> dict[str, Any]:
    cases, gaps, sources = load_frozen_inputs()
    selected: list[dict[str, Any]] = []
    for category, case_id in FROZEN_CASES:
        case = cases.get(case_id)
        if not isinstance(case, Mapping):
            raise RuntimeError(f"frozen_case_missing:{case_id}")
        observation = case.get("observation") if isinstance(case.get("observation"), Mapping) else {}
        source_ref = str(observation.get("source_ref") or "")
        frozen_passages = hardening.passages_for(case_id, case, sources)
        if not source_ref or not frozen_passages:
            raise RuntimeError(f"frozen_case_source_missing:{case_id}")
        selected.append(
            {
                "case_id": case_id,
                "category": category,
                "surface": observation.get("surface"),
                "source_ref": source_ref,
                "selection_key": stable_hash({"algorithm": RUN_VERSION, "case_id": case_id}),
            }
        )
    selected.sort(key=lambda row: (row["selection_key"], row["case_id"]))
    return {
        "stage": "hng2-historical-context-consolidation",
        "algorithm_version": RUN_VERSION,
        "schema_hash": algorithm.schema_hash(),
        "model": MODEL,
        "frozen": True,
        "selected_case_count": len(selected),
        "cases": selected,
        "source_case_namespace": "data/generated/hng2-schema/cases.json",
        "evidence_policy": {
            "known_frozen_results_only": True,
            "max_passages_per_case": 4,
            "max_chars_per_passage": 900,
            "new_historical_expansion": False,
        },
        "mainline_forbids": [
            "research_gap_recursive_loop",
            "search_plan_llm",
            "llm_search_terms",
            "unresolved_observation_follow_up",
            "frontier_expansion",
            "graph_rag",
            "embedding_retrieval",
            "web_search",
        ],
        "canonical_write_back": False,
    }


def ensure_selection() -> dict[str, Any]:
    selection = build_selection()
    path = OUT / "selection.json"
    if path.is_file():
        old = read_json(path, {})
        if stable_hash(old) != stable_hash(selection):
            raise RuntimeError("frozen_selection_mismatch")
    else:
        write_json(path, selection)
    return selection


def load_known_evidence() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name in ("relations.json", "temporal-items.json"):
        document = read_json(ROOT / "data/generated/hng1r2" / name, {}) or {}
        for ref, row in (document.get("evidence") or {}).items():
            if isinstance(row, Mapping):
                result[str(ref)] = dict(row)
    return result


def load_previous_findings() -> dict[str, Any]:
    known = load_known_evidence()
    relation_refs: set[str] = set()
    temporal_refs: set[str] = set()
    for name, key, target in (
        ("relations.json", "relations", relation_refs),
        ("temporal-items.json", "temporal_items", temporal_refs),
    ):
        document = read_json(ROOT / "data/generated/hng1r2" / name, {}) or {}
        for row in document.get(key, []) if isinstance(document.get(key), list) else []:
            if not isinstance(row, Mapping):
                continue
            for ref in row.get("evidence_refs", []) if isinstance(row.get("evidence_refs"), list) else []:
                target.add(str(ref))
    return {
        "evidence_refs": known,
        "relation_evidence_refs": sorted(relation_refs),
        "temporal_evidence_refs": sorted(temporal_refs),
    }


def source_passages(case_id: str, case: Mapping[str, Any], sources: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    # This uses the existing frozen HNG case/source map.  It does not invoke
    # the local FIND infrastructure or discover new passages.
    return hardening.passages_for(case_id, case, sources)


def card_from_tool_response(response: Mapping[str, Any]) -> tuple[Any | None, str | None]:
    payload, channel, error = controller.extract_strict_tool_payload(
        response,
        expected_function_name=algorithm.FUNCTION_NAME,
    )
    if error:
        return None, error
    return payload, channel


def make_fixture_card(case: Mapping[str, Any], bundle: Mapping[str, Any]) -> dict[str, Any]:
    """A deterministic plumbing fixture; it is never counted as a live finding."""

    observation = case.get("observation") if isinstance(case.get("observation"), Mapping) else {}
    target = str(observation.get("surface") or "")
    ref = str(observation.get("source_ref") or "")
    text = next(
        (
            str(row.get("text") or "")
            for row in bundle.get("passages", [])
            if str(row.get("ref") or "") == ref
        ),
        "",
    )
    span = target if target and target in text else str(observation.get("exact_span") or "")
    if not span or span not in text:
        for row in bundle.get("passages", []):
            candidate_span = target or str(observation.get("exact_span") or "")
            if candidate_span and candidate_span in str(row.get("text") or ""):
                ref = str(row.get("ref"))
                span = candidate_span
                break
    interpretation = case.get("interpretation") if isinstance(case.get("interpretation"), Mapping) else {}
    kind = str(interpretation.get("entity_kind") or "unknown")
    reference = str(interpretation.get("reference_form") or "unknown")
    # Frozen HNG interpretation records may describe nearby context rather
    # than this target.  The fixture follows the generic target-span rule so
    # offline plumbing does not reproduce that historical annotation error.
    if kind == "structural_kinship_expression" and not any(
        marker in target for marker in ("父", "母", "兄", "弟", "子", "女", "祖", "孫", "叔", "舅", "婿", "妻", "從")
    ):
        kind = "named_person"
        reference = "full_name"
    if kind not in entity_schema.ENTITY_KINDS:
        kind = "unknown"
    if reference not in entity_schema.REFERENCE_FORMS:
        reference = "unknown"
    return {
        "entities": [
            {
                "entity_key": "e0",
                "surface": target,
                "entity_kind": kind,
                "reference_form": reference,
                "evidence_ref": ref,
                "exact_span": span,
            }
        ]
        if target and ref and span
        else [],
        "relations": [],
        "temporal_assertions": [],
    }


def process_card(
    *,
    case: Mapping[str, Any],
    bundle: Mapping[str, Any],
    payload: Mapping[str, Any],
    known_evidence: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    passages = {
        str(row.get("ref")): dict(row)
        for row in bundle.get("passages", [])
        if isinstance(row, Mapping) and row.get("ref")
    }
    validation = algorithm.validate_card(payload, passages)
    normalization = algorithm.normalize_card(
        validation,
        case=case,
        bundle=bundle,
        known_evidence=known_evidence,
    )
    return validation, normalization


def bundle_records(
    selection: Mapping[str, Any],
    cases: Mapping[str, Mapping[str, Any]],
    sources: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for selected in selection.get("cases", []):
        case_id = str(selected["case_id"])
        bundle = algorithm.select_evidence_bundle(
            cases[case_id],
            source_passages(case_id, cases[case_id], sources),
        )
        prompt = algorithm.prompt_payload(cases[case_id], bundle)
        records.append(
            {
                "case_id": case_id,
                "category": selected.get("category"),
                "target_surface": bundle.get("target_surface"),
                "passages": bundle.get("passages", []),
                "original_total_chars": bundle.get("original_total_chars", 0),
                "selected_total_chars": bundle.get("selected_total_chars", 0),
                "selected_passage_count": len(bundle.get("passages", [])),
                "prompt_payload": prompt,
                "input_hash": stable_hash(prompt),
            }
        )
    return records


def run_offline(selection: Mapping[str, Any]) -> dict[str, Any]:
    cases, gaps, sources = load_frozen_inputs()
    previous = load_previous_findings()
    records = bundle_records(selection, cases, sources)
    output = OUT / "offline-replay"
    output.mkdir(parents=True, exist_ok=True)
    cards: list[dict[str, Any]] = []
    validations: list[dict[str, Any]] = []
    projections: list[dict[str, Any]] = []
    for record in records:
        case = cases[record["case_id"]]
        bundle = {"passages": record["passages"]}
        payload = make_fixture_card(case, bundle)
        validation, normalization = process_card(
            case=case,
            bundle=bundle,
            payload=payload,
            known_evidence=previous["evidence_refs"],
        )
        cards.append({"case_id": record["case_id"], "fixture_only": True, "payload": payload})
        validations.append({"case_id": record["case_id"], **validation})
        projections.append({"case_id": record["case_id"], **normalization})
    result = {
        "stage": "offline_replay",
        "fixture_only": True,
        "api_calls": 0,
        "selection_hash": stable_hash(selection),
        "bundle_count": len(records),
        "cards": cards,
        "validations": validations,
        "projections": projections,
        "invariants": {
            "no_research_gap": True,
            "no_search_plan": True,
            "no_frontier_expansion": True,
            "canonical_write_back": False,
        },
    }
    write_json(output / "replay.json", result)
    write_json(output / "evidence-bundles.json", records)
    return result


def preflight() -> dict[str, Any]:
    start = time.monotonic()
    record: dict[str, Any] = {
        "kind": "network_preflight",
        "start_time": utc_now(),
        "model": MODEL,
        "provider": PROVIDER,
        "canonical_write_back": False,
    }
    try:
        response = call_deepseek(
            [{"role": "user", "content": "Reply only with OK"}],
            model=MODEL,
            temperature=0,
            max_tokens=16,
            thinking={"type": "disabled"},
            timeout=60,
        )
        record.update(
            {
                "status": "reachable",
                "response_model": response.get("model"),
                "usage": usage(response),
            }
        )
    except Exception as exc:
        record.update({"status": "live_network_unavailable", **safe_error(exc)})
    record["elapsed_seconds"] = round(time.monotonic() - start, 3)
    record["end_time"] = utc_now()
    return record


def semantic_call(
    *,
    case_id: str,
    payload: Mapping[str, Any],
    raw_dir: Path,
    sequence: int,
) -> tuple[dict[str, Any], Mapping[str, Any] | None]:
    begin = time.monotonic()
    record: dict[str, Any] = {
        "kind": "semantic",
        "case_id": case_id,
        "sequence": sequence,
        "start_time": utc_now(),
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "input_hash": stable_hash(payload),
        "endpoint": algorithm.STRICT_ENDPOINT,
        "canonical_write_back": False,
        "immutable": True,
    }
    try:
        response = call_deepseek(
            [
                {"role": "system", "content": algorithm.SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)},
            ],
            model=MODEL,
            temperature=0,
            tools=[algorithm.function_definition()],
            tool_choice=algorithm.tool_choice(),
            thinking={"type": "disabled"},
            max_tokens=900,
            timeout=180,
            endpoint=algorithm.STRICT_ENDPOINT,
        )
        record.update({"status": "response", "usage": usage(response), "finish_reason": finish_reason(response)})
        raw_path = raw_dir / f"{sequence:02d}-{case_id}.json"
        write_json(raw_path, response)
        if finish_reason(response) == "length":
            record.update(
                {
                    "classification": "response_truncated",
                    "response_channel": "tool_call",
                    "parse_error": "finish_reason_length",
                }
            )
            return record, None
        payload_out, channel_or_error = card_from_tool_response(response)
        if payload_out is None:
            record.update(
                {
                    "classification": "response_parse_failure",
                    "response_channel": channel_or_error or "tool_call",
                    "parse_error": channel_or_error,
                }
            )
            return record, None
        record.update({"response_channel": channel_or_error, "classification": "parsed"})
        return record, payload_out
    except Exception as exc:
        record.update({"status": "provider_request_failure", **safe_error(exc)})
        return record, None
    finally:
        record["elapsed_seconds"] = round(time.monotonic() - begin, 3)
        record["end_time"] = utc_now()


def _live_case(
    *,
    sequence: int,
    selected: Mapping[str, Any],
    case: Mapping[str, Any],
    bundle_record: Mapping[str, Any],
    raw_dir: Path,
    known_evidence: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    case_id = str(selected["case_id"])
    payload = bundle_record["prompt_payload"]
    record, card = semantic_call(
        case_id=case_id,
        payload=payload,
        raw_dir=raw_dir,
        sequence=sequence,
    )
    result: dict[str, Any] = {
        "case_id": case_id,
        "category": selected.get("category"),
        "input_hash": bundle_record["input_hash"],
        "prompt_payload": payload,
        "transport": record,
        "card": card,
    }
    if card is None:
        result["validation"] = None
        result["normalization"] = None
        return result
    bundle = {"passages": bundle_record["passages"]}
    validation, normalization = process_card(
        case=case,
        bundle=bundle,
        payload=card,
        known_evidence=known_evidence,
    )
    if record.get("finish_reason") == "length":
        record["classification"] = "response_truncated"
    elif not validation.get("valid"):
        record["classification"] = "card_validation_failure"
    elif validation.get("item_rejection_count"):
        record["classification"] = "valid_card_with_item_rejections"
    else:
        record["classification"] = "valid_card"
    result["validation"] = validation
    result["normalization"] = normalization
    return result


def compare_results(
    results: Sequence[Mapping[str, Any]],
    cases: Mapping[str, Mapping[str, Any]],
    previous: Mapping[str, Any],
) -> list[dict[str, Any]]:
    relation_refs = set(previous.get("relation_evidence_refs", []))
    temporal_refs = set(previous.get("temporal_evidence_refs", []))
    rows: list[dict[str, Any]] = []
    for result in results:
        case = cases.get(str(result.get("case_id")), {})
        known_pids = {
            str(row.get("person_id"))
            for row in case.get("candidates", [])
            if isinstance(row, Mapping) and row.get("person_id")
        }
        normalization = result.get("normalization") or {}
        entity_rows = normalization.get("entities", []) if isinstance(normalization, Mapping) else []
        resolved_pids = {
            str(row.get("resolved_person_id"))
            for row in entity_rows
            if isinstance(row, Mapping) and row.get("resolved_person_id")
        }
        temporal_rows = normalization.get("temporal_assertions", []) if isinstance(normalization, Mapping) else []
        relation_rows = normalization.get("relations", []) if isinstance(normalization, Mapping) else []
        rows.append(
            {
                "case_id": result.get("case_id"),
                "known_identity_preserved": bool(known_pids & resolved_pids) if known_pids else None,
                "resolved_person_ids": sorted(resolved_pids),
                "relations_matching_existing_evidence": sum(
                    1 for row in relation_rows if row.get("evidence_ref") in relation_refs
                ),
                "new_source_supported_relation_observations": sum(
                    1 for row in relation_rows if row.get("evidence_ref") not in relation_refs
                ),
                "temporal_h0a_compatible": sum(
                    1 for row in temporal_rows if (row.get("h0a") or {}).get("status") == "compatible"
                ),
                "temporal_h0a_conflicts": sum(
                    1 for row in temporal_rows if (row.get("h0a") or {}).get("status") == "conflict"
                ),
                "previous_temporal_evidence_refs_used": sum(
                    1 for row in temporal_rows if row.get("evidence_ref") in temporal_refs
                ),
            }
        )
    return rows


def metrics_for(
    *,
    selection: Mapping[str, Any],
    bundle_records_value: Sequence[Mapping[str, Any]],
    results: Sequence[Mapping[str, Any]],
    preflight_record: Mapping[str, Any],
) -> dict[str, Any]:
    semantic_records = [row.get("transport", {}) for row in results]
    usages = [row.get("usage", {}) for row in semantic_records if row.get("status") == "response"]
    prompt_tokens = sum(int(row.get("prompt_tokens") or 0) for row in usages)
    completion_tokens = sum(int(row.get("completion_tokens") or 0) for row in usages)
    total_tokens = sum(int(row.get("total_tokens") or 0) for row in usages)
    latencies = [
        float(row.get("elapsed_seconds"))
        for row in semantic_records
        if row.get("status") == "response" and row.get("elapsed_seconds") is not None
    ]
    valid_entities = rejected_entities = valid_relations = rejected_relations = 0
    valid_temporal = rejected_temporal = 0
    resolved_existing = resolved_new = unresolved = 0
    unsupported = 0
    classifications: dict[str, int] = {}
    matching_relations = new_relations = h0a_compatible = h0a_conflicts = 0
    for result in results:
        classification = str((result.get("transport") or {}).get("classification") or "unclassified")
        classifications[classification] = classifications.get(classification, 0) + 1
        validation = result.get("validation") or {}
        valid_entities += len(validation.get("valid_entities", []))
        valid_relations += len(validation.get("valid_relations", []))
        valid_temporal += len(validation.get("valid_temporal_assertions", []))
        rejected_entities += len(validation.get("rejected_entities", []))
        rejected_relations += len(validation.get("rejected_relations", []))
        rejected_temporal += len(validation.get("rejected_temporal_assertions", []))
        unsupported += (
            len(validation.get("rejected_entities", []))
            + len(validation.get("rejected_relations", []))
            + len(validation.get("rejected_temporal_assertions", []))
        )
        for row in (result.get("normalization") or {}).get("entities", []):
            status = row.get("identity_status")
            resolved_existing += int(status == "resolved_existing")
            resolved_new += int(status == "resolved_new_candidate")
            unresolved += int(status in {"unresolved", "ambiguous", "not_single_person", "not_person"})
        for row in (result.get("normalization") or {}).get("relations", []):
            if row.get("matches_existing_evidence_ref"):
                matching_relations += 1
            else:
                new_relations += 1
        for row in (result.get("normalization") or {}).get("temporal_assertions", []):
            h0a_status = (row.get("h0a") or {}).get("status")
            h0a_compatible += int(h0a_status == "compatible")
            h0a_conflicts += int(h0a_status == "conflict")
    bundle_sizes = [int(row.get("selected_total_chars") or 0) for row in bundle_records_value]
    original_sizes = [int(row.get("original_total_chars") or 0) for row in bundle_records_value]
    prompt_char_sizes = [
        len(json.dumps(row.get("prompt_payload"), ensure_ascii=False, sort_keys=True))
        for row in bundle_records_value
    ]
    prompt_token_values = [int(row.get("prompt_tokens") or 0) for row in usages]
    return {
        "cases": selection.get("selected_case_count"),
        "deepseek_semantic_calls": len(results),
        "card_classifications": classifications,
        "valid_card_count": classifications.get("valid_card", 0) + classifications.get("valid_card_with_item_rejections", 0),
        "response_truncated_count": classifications.get("response_truncated", 0),
        "response_parse_failure_count": classifications.get("response_parse_failure", 0),
        "card_validation_failure_count": classifications.get("card_validation_failure", 0),
        "preflight": {
            "performed": True,
            "status": preflight_record.get("status"),
            "separate_from_semantic_calls": True,
        },
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "median_prompt_tokens_per_case": statistics.median(
            prompt_token_values
        ) if usages else 0,
        "maximum_prompt_tokens": max(prompt_token_values or [0]),
        "valid_entities": valid_entities,
        "rejected_entities": rejected_entities,
        "valid_relations": valid_relations,
        "rejected_relations": rejected_relations,
        "valid_temporal_assertions": valid_temporal,
        "rejected_temporal_assertions": rejected_temporal,
        "resolved_existing_persons": resolved_existing,
        "resolved_new_candidate_projections": resolved_new,
        "unresolved_persons": unresolved,
        "unsupported_findings": unsupported,
        "relations_matching_existing_evidence": matching_relations,
        "new_source_supported_relation_observations": new_relations,
        "temporal_assertions_h0a_compatible": h0a_compatible,
        "temporal_assertions_h0a_conflicts": h0a_conflicts,
        "maximum_prompt_chars": max(prompt_char_sizes or [0]),
        "maximum_selected_bundle_chars": max(bundle_sizes or [0]),
        "maximum_original_frozen_packet_chars": max(original_sizes or [0]),
        "median_selected_bundle_chars": statistics.median(bundle_sizes or [0]),
        "oversized_packet_regression": {
            "previous_reference_limit_chars": PREVIOUS_PACKET_LIMIT,
            "cases_over_previous_limit_before_selection": sum(size > PREVIOUS_PACKET_LIMIT for size in original_sizes),
            "cases_over_previous_limit_after_selection": sum(size > PREVIOUS_PACKET_LIMIT for size in bundle_sizes),
        },
        "successful_latency_seconds": {
            "median": statistics.median(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
        },
        "no_search_plan_calls": True,
        "no_follow_up_calls": True,
        "no_frontier_expansion": True,
        "canonical_write_back": False,
    }


def replay_live(run_id: str) -> dict[str, Any]:
    """Rebuild only derived live projections from immutable raw responses."""

    cases, gaps, sources = load_frozen_inputs()
    previous = load_previous_findings()
    selection = ensure_selection()
    out = OUT / "live" / run_id
    old_results = read_json(out / "cards-and-results.json", []) or []
    bundles = read_json(out / "evidence-bundles.json", []) or []
    preflight_record = read_json(out / "preflight.json", {}) or {}
    raw_dir = out / "raw-api"
    selected_by_id = {str(row["case_id"]): row for row in selection.get("cases", [])}
    bundle_by_id = {str(row["case_id"]): row for row in bundles if isinstance(row, Mapping)}
    results: list[dict[str, Any]] = []
    for index, old in enumerate(old_results, start=1):
        case_id = str(old.get("case_id"))
        result = dict(old)
        transport = dict(old.get("transport") or {})
        raw_candidates = sorted(raw_dir.glob(f"{index:02d}-{case_id}.json"))
        if raw_candidates:
            response = read_json(raw_candidates[0], {}) or {}
            transport.update(
                {
                    "status": "response",
                    "usage": usage(response),
                    "finish_reason": finish_reason(response),
                }
            )
            if finish_reason(response) == "length":
                transport.update(
                    {
                        "classification": "response_truncated",
                        "response_channel": "tool_call",
                        "parse_error": "finish_reason_length",
                    }
                )
                result.update({"transport": transport, "card": None, "validation": None, "normalization": None})
            else:
                card, channel_or_error = card_from_tool_response(response)
                if card is None:
                    transport.update(
                        {
                            "classification": "response_parse_failure",
                            "response_channel": channel_or_error or "tool_call",
                            "parse_error": channel_or_error,
                        }
                    )
                    result.update({"transport": transport, "card": None, "validation": None, "normalization": None})
                else:
                    bundle = bundle_by_id[case_id]
                    validation, normalization = process_card(
                        case=cases[case_id],
                        bundle={"passages": bundle.get("passages", [])},
                        payload=card,
                        known_evidence=previous["evidence_refs"],
                    )
                    if not validation.get("valid"):
                        transport["classification"] = "card_validation_failure"
                    elif validation.get("item_rejection_count"):
                        transport["classification"] = "valid_card_with_item_rejections"
                    else:
                        transport["classification"] = "valid_card"
                    result.update(
                        {
                            "transport": transport,
                            "card": card,
                            "validation": validation,
                            "normalization": normalization,
                        }
                    )
        results.append(result)
    comparisons = compare_results(results, cases, previous)
    metrics = metrics_for(
        selection=selection,
        bundle_records_value=bundles,
        results=results,
        preflight_record=preflight_record,
    )
    write_json(out / "cards-and-results.json", results)
    write_json(out / "comparisons.json", comparisons)
    write_json(out / "metrics.json", metrics)
    write_json(
        out / "normalization.json",
        [{"case_id": row.get("case_id"), "normalization": row.get("normalization")} for row in results],
    )
    manifest = read_json(out / "manifest.json", {}) or {}
    manifest["derived_projection_replayed_without_api"] = True
    manifest["raw_api_immutable"] = True
    write_json(out / "manifest.json", manifest)
    return {"run_id": run_id, "metrics": metrics, "results": results, "comparisons": comparisons}


def run_live(selection: Mapping[str, Any], run_id: str | None = None) -> dict[str, Any]:
    cases, gaps, sources = load_frozen_inputs()
    previous = load_previous_findings()
    run_id = run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT / "live" / run_id
    out.mkdir(parents=True, exist_ok=True)
    bundles = bundle_records(selection, cases, sources)
    write_json(out / "evidence-bundles.json", bundles)
    preflight_record = preflight()
    write_json(out / "preflight.json", preflight_record)
    if preflight_record.get("status") != "reachable":
        write_json(
            out / "manifest.json",
            {
                "stage": "hng2-historical-context-consolidation",
                "run_id": run_id,
                "status": "live_network_unavailable",
                "preflight": preflight_record,
                "story_results_created": False,
                "canonical_write_back": False,
            },
        )
        raise RuntimeError("live_network_unavailable")
    raw_dir = out / "raw-api"
    results: list[dict[str, Any]] = []
    selected_by_id = {str(row["case_id"]): row for row in selection.get("cases", [])}
    for index, bundle in enumerate(bundles, start=1):
        case_id = str(bundle["case_id"])
        results.append(
            _live_case(
                sequence=index,
                selected=selected_by_id[case_id],
                case=cases[case_id],
                bundle_record=bundle,
                raw_dir=raw_dir,
                known_evidence=previous["evidence_refs"],
            )
        )
    comparisons = compare_results(results, cases, previous)
    metrics = metrics_for(
        selection=selection,
        bundle_records_value=bundles,
        results=results,
        preflight_record=preflight_record,
    )
    write_json(out / "cards-and-results.json", results)
    write_json(out / "comparisons.json", comparisons)
    write_json(out / "metrics.json", metrics)
    write_json(
        out / "normalization.json",
        [{"case_id": row.get("case_id"), "normalization": row.get("normalization")} for row in results],
    )
    write_json(
        out / "manifest.json",
        {
            "stage": "hng2-historical-context-consolidation",
            "run_id": run_id,
            "status": "complete",
            "selection_hash": stable_hash(selection),
            "schema_hash": algorithm.schema_hash(),
            "raw_api_immutable": True,
            "deepseek_call_policy": "one semantic call per case plus one preflight",
            "canonical_write_back": False,
        },
    )
    return {
        "run_id": run_id,
        "output": str(out),
        "results": results,
        "comparisons": comparisons,
        "metrics": metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline-replay", action="store_true", help="run deterministic plumbing replay; no API calls")
    parser.add_argument("--live", action="store_true", help="run the frozen cases with approved network access")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--replay-live", default=None, metavar="RUN_ID", help="rebuild a completed live projection without API calls")
    args = parser.parse_args()
    if args.offline_replay and args.live:
        parser.error("choose only one of --offline-replay or --live")
    if args.replay_live and (args.offline_replay or args.live):
        parser.error("--replay-live cannot be combined with another run mode")
    selection = ensure_selection()
    if args.replay_live:
        result = replay_live(args.replay_live)
        print(json.dumps({"run_id": result["run_id"], "replayed_without_api": True, "metrics": result["metrics"]}, ensure_ascii=False, indent=2))
        return 0
    if args.live:
        result = run_live(selection, args.run_id)
        print(json.dumps({"run_id": result["run_id"], "metrics": result["metrics"]}, ensure_ascii=False, indent=2))
        return 0
    result = run_offline(selection)
    print(json.dumps({"offline_replay": True, "api_calls": result["api_calls"], "cases": result["bundle_count"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
