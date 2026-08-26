#!/usr/bin/env python3
"""Run the isolated HDB2-PSL0 collective identity pilot.

The runner performs one strict predicate call per occurrence with plausible
candidates, then runs the collective fixed-weight inference offline over the
whole sparse graph.  It never writes HDB2, HDB1, canonical, or reviewed data.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hdb2_lj0_common as lj0  # noqa: E402
import hdb2_psl0_common as common  # noqa: E402
from hng2_schema_controller import extract_strict_tool_payload  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402


OUT_ROOT = ROOT / "data/generated/hdb2-psl0"
SELECTION_PATH = ROOT / "data/annotation/hdb2-psl0-selection.json"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def usage(response: Mapping[str, Any]) -> dict[str, int]:
    value = response.get("usage") if isinstance(response, Mapping) else {}
    value = value if isinstance(value, Mapping) else {}
    return {key: int(value.get(key) or 0) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}


def finish_reason(response: Mapping[str, Any]) -> str | None:
    choices = response.get("choices") if isinstance(response, Mapping) else None
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        return str(choices[0].get("finish_reason") or "") or None
    return None


def safe_error(exc: Exception) -> dict[str, Any]:
    return {
        "error_type": type(exc).__name__,
        "error": str(exc)[:500],
        "http_status": getattr(exc, "http_status", None),
        "provider_error_body": str(getattr(exc, "provider_error_body", "") or "")[:1000],
    }


def protected_hashes() -> dict[str, str]:
    paths = [
        "data/people.json",
        "data/relations.json",
        "data/personStory.json",
        "data/annotation/hdb2-f-review-queue.json",
        "data/derived/hdb2-f-occurrence-cases.json",
        "data/derived/hdb2-f-occurrence-ledger.json",
        "data/derived/hdb2-f-relation-projection.json",
        "data/derived/hdb2-f-kinship-projection.json",
        "data/derived/hdb2-f-marriage-projection.json",
        "data/derived/hdb2-f-office-projection.json",
        "data/derived/hdb2-f-person-knowledge.json",
        "data/annotation/hdb2-lj0-selection.json",
        "data/generated/hdb2-lj0/live/20260826T-HDB2-LJ0-02/cases.json",
        "data/generated/hdb2-lj0/live/20260826T-HDB2-LJ0-02/decisions.json",
        "data/annotation/story-temporal-anchors-h0a.json",
        "data/annotation/story-temporal-evidence-h0a.json",
        "data/annotation/ruler-identities-e0.json",
        "site/public/generated/review/hdb2/index.json",
    ]
    return {path: lj0.file_hash(ROOT / path) for path in paths}


def preflight() -> dict[str, Any]:
    started = time.monotonic()
    record: dict[str, Any] = {
        "endpoint": common.STRICT_ENDPOINT,
        "model": common.MODEL,
        "started_at": utc_now(),
    }
    try:
        response = call_deepseek(
            [{"role": "user", "content": "Return a connectivity acknowledgement."}],
            model=common.MODEL,
            temperature=0,
            thinking={"type": "disabled"},
            max_tokens=4,
            timeout=60,
            endpoint=common.STRICT_ENDPOINT,
        )
        record.update({"status": "reachable", "response_model": response.get("model"), "usage": usage(response)})
    except Exception as exc:
        record.update({"status": "provider_request_failure", **safe_error(exc)})
    record.update({"elapsed_seconds": round(time.monotonic() - started, 3), "ended_at": utc_now()})
    return record


def _raw_path(raw_dir: Path, sequence: int, attempt: int) -> Path:
    return raw_dir / f"{sequence:04d}-predicate-attempt{attempt}.json"


def call_predicates(
    *,
    packet: Mapping[str, Any],
    sequence: int,
    raw_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    request = {
        "messages": [
            {"role": "system", "content": common.SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(packet, ensure_ascii=False, sort_keys=True)},
        ],
        "model": common.MODEL,
        "temperature": 0,
        "thinking": {"type": "disabled"},
        "max_tokens": 1500,
        "endpoint": common.STRICT_ENDPOINT,
        "tools": [common.predicate_tool()],
        "tool_choice": common.tool_choice(),
    }
    record: dict[str, Any] = {
        "sequence": sequence,
        "call_type": "predicate_evaluation",
        "mention_id": packet.get("mention", {}).get("mention_id"),
        "story_id": packet.get("mention", {}).get("story_id"),
        "target_surface": packet.get("mention", {}).get("surface"),
        "model": common.MODEL,
        "prompt_version": common.PROMPT_VERSION,
        "input_hash": common.stable_hash(packet),
        "attempts": [],
    }
    payload: dict[str, Any] = {}
    validation: dict[str, Any] = {"valid": False, "errors": ["not_called"]}
    for attempt in (1, 2):
        started = time.monotonic()
        attempt_row: dict[str, Any] = {"attempt": attempt, "started_at": utc_now()}
        try:
            response = call_deepseek(
                request["messages"],
                model=common.MODEL,
                temperature=0,
                thinking={"type": "disabled"},
                max_tokens=1500,
                timeout=180,
                endpoint=common.STRICT_ENDPOINT,
                tools=[common.predicate_tool()],
                tool_choice=common.tool_choice(),
            )
            path = _raw_path(raw_dir, sequence, attempt)
            if path.exists():
                raise RuntimeError(f"immutable_raw_response_exists:{path.name}")
            common.write_json(path, response)
            finish = finish_reason(response)
            attempt_row.update({"classification": "response", "finish_reason": finish, "usage": usage(response), "raw_path": str(path.relative_to(ROOT))})
            if finish == "length":
                attempt_row["classification"] = "response_truncated"
                record["attempts"].append(attempt_row)
                break
            extracted, channel, parse_error = extract_strict_tool_payload(response, expected_function_name=common.FUNCTION_NAME)
            attempt_row["response_channel"] = channel
            if parse_error or not isinstance(extracted, Mapping):
                attempt_row.update({"classification": "response_parse_failure", "parse_error": parse_error or "payload_not_object"})
                record["attempts"].append(attempt_row)
                if attempt == 1:
                    continue
                break
            payload = dict(extracted)
            validation = common.validate_predicates(payload, packet)
            attempt_row.update({"classification": "parsed", "validation": {"valid": validation.get("valid"), "errors": validation.get("errors", [])}})
            record["attempts"].append(attempt_row)
            break
        except Exception as exc:
            attempt_row.update({"classification": "provider_request_failure", **safe_error(exc)})
            record["attempts"].append(attempt_row)
            if attempt == 1:
                continue
        finally:
            attempt_row["elapsed_seconds"] = round(time.monotonic() - started, 3)
            attempt_row["ended_at"] = utc_now()
    record["classification"] = record["attempts"][-1].get("classification") if record["attempts"] else "provider_request_failure"
    record["retry_count"] = max(0, len(record["attempts"]) - 1)
    record["usage"] = {
        key: sum(int((row.get("usage") or {}).get(key) or 0) for row in record["attempts"])
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }
    record["elapsed_seconds"] = round(sum(float(row.get("elapsed_seconds") or 0) for row in record["attempts"]), 3)
    record["request_hash"] = common.stable_hash(request)
    model_record = {
        "sequence": sequence,
        "mention_id": packet.get("mention", {}).get("mention_id"),
        "story_id": packet.get("mention", {}).get("story_id"),
        "payload": payload,
        "validation": validation,
        "classification": record["classification"],
        "request_hash": record["request_hash"],
    }
    return record, model_record


def _neutral_model_record(case: Mapping[str, Any], packet: Mapping[str, Any], reason: str) -> dict[str, Any]:
    return {
        "sequence": None,
        "mention_id": case.get("mention_id"),
        "story_id": case.get("story_id"),
        "payload": {"predicates": [], "note": reason},
        "validation": {"valid": True, "errors": []},
        "classification": "no_call",
        "request_hash": common.stable_hash(packet),
    }


def diagnostic_story(graph: Mapping[str, Any], decisions: Mapping[str, Any]) -> dict[str, Any]:
    rows = [row for row in graph.get("cases", []) if str(row.get("story_id")) == "05-fangzheng-011"]
    target_rows = []
    for row in rows:
        target_rows.append({
            "occurrence_id": row.get("occurrence_id"),
            "surface": row.get("target_surface"),
            "candidate_nodes": [{"key": c.get("candidate_key"), "name": c.get("display_name"), "node": c.get("candidate_node_id")} for c in row.get("candidates", [])],
            "same_story_predicates": row.get("same_story_predicates", []),
        })
    decision_rows = [row for row in decisions.get("records", []) if str(row.get("story_id")) == "05-fangzheng-011"]
    context = [
        {"surface": row.get("surface"), "story_id": row.get("story_id"), "internal_ref": row.get("internal_ref"), "mention_id": row.get("mention_id")}
        for row in graph.get("context_mentions", [])
        if str(row.get("story_id")) == "05-fangzheng-011"
    ]
    story_text = str(rows[0].get("story_context") or "") if rows else ""
    return {
        "story_id": "05-fangzheng-011",
        "requested_chain": ["帝", "武帝", "晉武帝", "司馬炎", "和嶠", "王濟"],
        "target_occurrences": target_rows,
        "psl_decisions": decision_rows,
        "context_mentions": context,
        "surface_presence_in_supplied_story": {surface: surface in story_text for surface in ["帝", "武帝", "晉武帝", "司馬炎", "和嶠", "王武子", "王濟"]},
        "interpretation": {
            "帝_to_武帝": "same_story_coreference_candidate_edge_if_LLM_supports_it",
            "武帝_to_晉武帝_to_司馬炎": "shared reviewed H0A ruler node when registry candidate is present",
            "和嶠": "contextual person mention only; not a candidate for the ruler mention",
            "王濟": "not supplied as a catalogue candidate in this packet; no identity edge is invented",
        },
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _load_lj0_decisions() -> dict[str, Any]:
    return lj0.read_json(ROOT / "data/generated/hdb2-lj0/live/20260826T-HDB2-LJ0-02/decisions.json", {}) or {"records": []}


def _raw_hashes(raw_dir: Path) -> dict[str, str]:
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(raw_dir.glob("*.json"))}


def _finalize(
    *,
    run_dir: Path,
    selection: Mapping[str, Any],
    graph: Mapping[str, Any],
    model_records: list[dict[str, Any]],
    call_records: list[dict[str, Any]],
    validation_failures: list[dict[str, Any]],
    before: Mapping[str, str],
    preflight_record: Mapping[str, Any],
    replayed_without_api: bool = False,
) -> Path:
    valid_predicates: list[dict[str, Any]] = []
    for model_record in model_records:
        validation = model_record.get("validation") or {}
        if validation.get("valid") is True:
            for row in (model_record.get("payload") or {}).get("predicates", []) or []:
                valid_predicates.append({"mention_id": model_record.get("mention_id"), **dict(row)})
    decisions = common.infer_graph(graph, valid_predicates)
    comparison = common.compare_decisions(decisions, _load_lj0_decisions(), graph)
    safety = common.safety_metrics(graph, decisions, validation_failures)
    # No truth-labelled evaluation set is available for this pilot.  The
    # report therefore treats deterministic safety violations as the only
    # observable false-resolution candidates; it does not invent a gold
    # label for an otherwise unresolved human-review case.
    comparison["safety_metrics"] = safety
    comparison["false_resolution_candidates"] = sum(
        int(safety.get(key) or 0)
        for key in (
            "same_surface_automatic_merges",
            "compositional_base_person_collapses",
            "nonperson_person_id_anomalies",
            "hard_veto_promotions",
            "invalid_candidate_keys",
            "invalid_evidence_references",
            "confidence_only_resolutions",
        )
    )
    metrics = common.aggregate_metrics(graph, decisions, comparison, call_records, validation_failures)
    metrics.update({
        "selection_hash": selection.get("selection_hash"),
        "source_lj0_selection_hash": selection.get("source_selection_hash"),
        "semantic_calls": len(call_records),
        "retries": sum(int(row.get("retry_count") or 0) for row in call_records),
        "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in call_records),
        "parse_failures": sum(row.get("classification") == "response_parse_failure" for row in call_records),
        "truncated_responses": sum(row.get("classification") == "response_truncated" for row in call_records),
        "invalid_schema_payloads": len(validation_failures),
        "contextual_predicate_calls": len(call_records),
        "preflight": dict(preflight_record),
        "replayed_without_api": replayed_without_api,
        "safety_metrics": safety,
    })
    after = protected_hashes()
    if dict(before) != after:
        raise RuntimeError("hdb2_psl0_protected_input_changed")
    common.write_json(run_dir / "predicate-results.json", {"records": model_records, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "call-records.json", {"records": call_records, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "decisions.json", decisions)
    common.write_json(run_dir / "comparison.json", comparison)
    common.write_json(run_dir / "metrics.json", metrics)
    common.write_json(run_dir / "validation-failures.json", {"records": validation_failures, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "diagnostic-05-fangzheng-011.json", diagnostic_story(graph, decisions))
    common.write_json(run_dir / "validation-summary.json", {
        "schema": "hdb2-psl0-validation-summary-v1",
        "valid": True,
        "selection_hash": selection.get("selection_hash"),
        "candidate_only": True,
        "canonical_write_back": False,
        "hdb2_decisions_modified": False,
        "protected_hashes_unchanged": dict(before) == after,
        "validation_failures": len(validation_failures),
        "safety_metrics": safety,
        "replayed_without_api": replayed_without_api,
    })
    manifest = common.read_json(run_dir / "manifest.json", {}) or {}
    manifest.update({
        "status": "complete",
        "replayed_without_api": replayed_without_api,
        "semantic_calls": len(call_records),
        "candidate_only": True,
        "canonical_write_back": False,
        "hdb2_decisions_modified": False,
        "protected_hashes_before": dict(before),
        "protected_hashes_after": after,
        "raw_api_hashes": _raw_hashes(run_dir / "raw-api"),
        "postprocessing_replay_hash": common.stable_hash({"graph": graph, "predicates": model_records, "decisions": decisions}),
    })
    common.write_json(run_dir / "manifest.json", manifest)
    return run_dir


def replay(run_dir: Path) -> Path:
    selection = common.read_json(run_dir / "selection.json", {}) or {}
    graph = common.read_json(run_dir / "graph-cases.json", {}) or {}
    packets_document = common.read_json(run_dir / "prompt-packets.json", {}) or {}
    model_document = common.read_json(run_dir / "predicate-results.json", {}) or {}
    records = list(model_document.get("records", []))
    packets = {str(row.get("mention_id")): row.get("packet") or {} for row in packets_document.get("records", [])}
    graph_by_id = {str(row.get("mention_id")): row for row in graph.get("cases", [])}
    refreshed: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for record in records:
        mention_id = str(record.get("mention_id"))
        packet = packets.get(mention_id, {})
        validation = common.validate_predicates(record.get("payload") or {}, packet) if record.get("classification") != "no_call" else {"valid": True, "errors": []}
        record["validation"] = validation
        if validation.get("valid") is not True:
            failures.append({"mention_id": mention_id, "errors": list(validation.get("errors", []))})
        refreshed.append(record)
    calls_document = common.read_json(run_dir / "call-records.json", {}) or {}
    call_records = list(calls_document.get("records", []))
    manifest = common.read_json(run_dir / "manifest.json", {}) or {}
    before = manifest.get("protected_hashes_before") or protected_hashes()
    preflight_record = common.read_json(run_dir / "preflight.json", {}) or {}
    common.write_json(run_dir / "graph-cases.json", graph)
    common.write_json(run_dir / "predicate-results.json", {"records": refreshed, "candidate_only": True, "canonical_write_back": False})
    return _finalize(
        run_dir=run_dir,
        selection=selection,
        graph=graph,
        model_records=refreshed,
        call_records=call_records,
        validation_failures=failures,
        before=before,
        preflight_record=preflight_record,
        replayed_without_api=True,
    )


def run(args: argparse.Namespace) -> Path:
    selection = common.freeze_selection(SELECTION_PATH)
    frozen = common.load_frozen_lj0_cases()
    graph = common.build_graph_cases(frozen)
    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-HDB2-PSL0"
    run_dir = OUT_ROOT / "live" / run_id
    if run_dir.exists():
        raise RuntimeError(f"hdb2_psl0_run_exists:{run_dir}")
    raw_dir = run_dir / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=False)
    before = protected_hashes()
    packets = []
    for case in graph.get("cases", []):
        packet = common.wire_packet(case, graph.get("cases", []), graph)
        packets.append({"mention_id": case.get("mention_id"), "packet": packet})
    common.write_json(run_dir / "selection.json", selection)
    common.write_json(run_dir / "graph-cases.json", graph)
    common.write_json(run_dir / "prompt-packets.json", {"records": packets, "candidate_only": True, "canonical_write_back": False})
    preflight_record = preflight()
    common.write_json(run_dir / "preflight.json", preflight_record)
    manifest = {
        "schema": "hdb2-psl0-live-manifest-v1",
        "run_id": run_id,
        "run_version": common.RUN_VERSION,
        "prompt_version": common.PROMPT_VERSION,
        "model": common.MODEL,
        "temperature": 0,
        "thinking": "disabled",
        "endpoint": common.STRICT_ENDPOINT,
        "selection_hash": selection.get("selection_hash"),
        "source_lj0_selection_hash": selection.get("source_selection_hash"),
        "case_count": len(graph.get("cases", [])),
        "candidate_only": True,
        "canonical_write_back": False,
        "hdb2_decisions_modified": False,
        "protected_hashes_before": before,
        "preflight": preflight_record,
        "created_at": utc_now(),
    }
    common.write_json(run_dir / "manifest.json", manifest)
    if preflight_record.get("status") != "reachable":
        common.write_json(run_dir / "predicate-results.json", {"records": [], "candidate_only": True, "canonical_write_back": False})
        common.write_json(run_dir / "call-records.json", {"records": [], "candidate_only": True, "canonical_write_back": False})
        common.write_json(run_dir / "decisions.json", {"schema": "hdb2-psl0-decisions-v1", "records": [], "candidate_only": True, "canonical_write_back": False})
        return run_dir
    model_records: list[dict[str, Any]] = []
    call_records: list[dict[str, Any]] = []
    validation_failures: list[dict[str, Any]] = []
    sequence = 0
    for case, packet_row in zip(graph.get("cases", []), packets):
        packet = packet_row["packet"]
        if not packet.get("request_predicates"):
            model_records.append(_neutral_model_record(case, packet, "no_plausible_candidates_or_pair_predicates"))
            continue
        sequence += 1
        call_record, model_record = call_predicates(packet=packet, sequence=sequence, raw_dir=raw_dir)
        call_records.append(call_record)
        model_records.append(model_record)
        validation = model_record.get("validation") or {}
        if validation.get("valid") is not True:
            validation_failures.append({"mention_id": case.get("mention_id"), "errors": list(validation.get("errors", [])), "classification": call_record.get("classification")})
    return _finalize(
        run_dir=run_dir,
        selection=selection,
        graph=graph,
        model_records=model_records,
        call_records=call_records,
        validation_failures=validation_failures,
        before=before,
        preflight_record=preflight_record,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()
    if args.replay:
        replay(args.replay if args.replay.is_absolute() else ROOT / args.replay)
        return 0
    if args.prepare_only:
        selection = common.freeze_selection(SELECTION_PATH)
        frozen = common.load_frozen_lj0_cases()
        graph = common.build_graph_cases(frozen)
        print(json.dumps({"selection": str(SELECTION_PATH.relative_to(ROOT)), "selection_hash": selection.get("selection_hash"), "cases": len(graph.get("cases", [])), "context_mentions": len(graph.get("context_mentions", [])), "coreference_pairs": len(graph.get("coreference_pairs", []))}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
