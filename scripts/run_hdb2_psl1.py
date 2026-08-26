#!/usr/bin/env python3
"""Run HDB2-PSL1 as an isolated, candidate-only experiment.

The runner deliberately keeps PSL1 beside (rather than inside) PSL0.  It
reuses the frozen LJ0 selection/candidate construction, sends only local
candidate keys to DeepSeek, and performs all final state transitions in
Python.  The optional adversarial reviewer is called only for the initial
``review_required`` states.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hdb2_lj0_common as lj0  # noqa: E402
import hdb2_psl1_common as common  # noqa: E402
from hng2_schema_controller import extract_strict_tool_payload  # noqa: E402
from smoke_deepseek import call_deepseek  # noqa: E402


OUT_ROOT = ROOT / "data/generated/hdb2-psl1"
SELECTION_PATH = ROOT / "data/annotation/hdb2-psl1-selection.json"


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
        "data/annotation/hdb2-psl0-selection.json",
        "data/generated/hdb2-psl0/live/20260827T-HDB2-PSL0-04/decisions.json",
        "data/annotation/story-temporal-anchors-h0a.json",
        "data/annotation/story-temporal-evidence-h0a.json",
        "data/annotation/ruler-identities-e0.json",
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


def _raw_path(raw_dir: Path, sequence: int, call_type: str, attempt: int) -> Path:
    return raw_dir / f"{sequence:04d}-{call_type}-attempt{attempt}.json"


def _call_tool(
    *,
    packet: Mapping[str, Any],
    sequence: int,
    call_type: str,
    system_prompt: str,
    tool: Mapping[str, Any],
    choice: Mapping[str, Any],
    expected_function: str,
    prompt_version: str,
    raw_dir: Path,
    validator,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    request = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(packet, ensure_ascii=False, sort_keys=True)},
        ],
        "model": common.MODEL,
        "temperature": 0,
        "thinking": {"type": "disabled"},
        "max_tokens": 1800 if call_type == "predicate_evaluation" else 900,
        "endpoint": common.STRICT_ENDPOINT,
        "tools": [dict(tool)],
        "tool_choice": dict(choice),
    }
    mention = packet.get("mention") if isinstance(packet.get("mention"), Mapping) else {}
    record: dict[str, Any] = {
        "sequence": sequence,
        "call_type": call_type,
        "mention_id": mention.get("mention_id"),
        "story_id": mention.get("story_id"),
        "target_surface": mention.get("surface"),
        "model": common.MODEL,
        "prompt_version": prompt_version,
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
                max_tokens=request["max_tokens"],
                timeout=240,
                endpoint=common.STRICT_ENDPOINT,
                tools=[dict(tool)],
                tool_choice=dict(choice),
            )
            path = _raw_path(raw_dir, sequence, call_type, attempt)
            if path.exists():
                raise RuntimeError(f"immutable_raw_response_exists:{path.name}")
            common.write_json(path, response)
            finish = finish_reason(response)
            attempt_row.update({"classification": "response", "finish_reason": finish, "usage": usage(response), "raw_path": str(path.relative_to(ROOT))})
            if finish == "length":
                attempt_row["classification"] = "response_truncated"
                record["attempts"].append(attempt_row)
                break
            extracted, channel, parse_error = extract_strict_tool_payload(response, expected_function_name=expected_function)
            attempt_row["response_channel"] = channel
            if parse_error or not isinstance(extracted, Mapping):
                attempt_row.update({"classification": "response_parse_failure", "parse_error": parse_error or "payload_not_object"})
                record["attempts"].append(attempt_row)
                if attempt == 1:
                    continue
                break
            payload = dict(extracted)
            validation = validator(payload, packet)
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
        "call_type": call_type,
        "mention_id": mention.get("mention_id"),
        "story_id": mention.get("story_id"),
        "payload": payload,
        "validation": validation,
        "classification": record["classification"],
        "request_hash": record["request_hash"],
    }
    failure = None
    if validation.get("valid") is not True:
        failure = {
            "call_type": call_type,
            "mention_id": mention.get("mention_id"),
            "classification": record["classification"],
            "errors": list(validation.get("errors", [])),
        }
    return record, model_record, failure


def _neutral_model_record(case: Mapping[str, Any], reason: str) -> dict[str, Any]:
    return {
        "sequence": None,
        "call_type": "predicate_evaluation",
        "mention_id": case.get("mention_id"),
        "story_id": case.get("story_id"),
        "payload": {"predicates": [], "note": reason},
        "validation": {"valid": True, "errors": []},
        "classification": "no_call",
        "request_hash": None,
    }


def _load_lj0_decisions() -> dict[str, Any]:
    return lj0.read_json(ROOT / "data/generated/hdb2-lj0/live/20260826T-HDB2-LJ0-02/decisions.json", {}) or {"records": []}


def _holdout_comparison(initial: Mapping[str, Any], final: Mapping[str, Any]) -> dict[str, Any]:
    before = {str(row.get("mention_id")): row for row in initial.get("records", [])}
    rows: list[dict[str, Any]] = []
    for row in final.get("records", []):
        old = before.get(str(row.get("mention_id")), {})
        rows.append({
            "mention_id": row.get("mention_id"),
            "occurrence_id": row.get("occurrence_id"),
            "story_id": row.get("story_id"),
            "surface": row.get("surface"),
            "hdb2_current_status": row.get("current_status"),
            "initial_state": old.get("result_state"),
            "final_state": row.get("result_state"),
            "initial_top_candidate": old.get("top_candidate"),
            "final_top_candidate": row.get("top_candidate"),
            "changed": old.get("result_state") != row.get("result_state") or old.get("top_candidate") != row.get("top_candidate"),
            "candidate_only": True,
            "canonical_write_back": False,
        })
    return {
        "schema": "hdb2-psl1-holdout-comparison-v1",
        "records": rows,
        "changed_count": sum(bool(row.get("changed")) for row in rows),
        "candidate_only": True,
        "canonical_write_back": False,
    }


def diagnostic_yanyu(graph: Mapping[str, Any], decisions: Mapping[str, Any]) -> dict[str, Any]:
    story = "02-yanyu-054"
    rows = [row for row in graph.get("cases", []) if str(row.get("story_id")) == story]
    decision_by_id = {str(row.get("mention_id")): row for row in decisions.get("records", [])}
    return {
        "story_id": story,
        "story_text": str(rows[0].get("story_context") or "") if rows else "",
        "distinct_predicates": list(graph.get("distinct_pairs", [])),
        "occurrences": [
            {
                "occurrence_id": row.get("occurrence_id"),
                "surface": row.get("target_surface"),
                "candidates": [
                    {"key": candidate.get("candidate_key"), "name": candidate.get("display_name"), "node": candidate.get("candidate_node_id")}
                    for candidate in row.get("candidates", [])
                ],
                "hard_vetoes": row.get("psl1_hard_vetoes", {}),
                "decision": decision_by_id.get(str(row.get("mention_id"))),
            }
            for row in rows
        ],
        "required_invariant": "Distinct(王長史,劉尹)=1; if 劉尹 has grounded identity support for 劉惔, the shared 劉惔 candidate is not linkable for 王長史",
        "candidate_only": True,
        "canonical_write_back": False,
    }


def _raw_hashes(raw_dir: Path) -> dict[str, str]:
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(raw_dir.glob("*.json"))
    }


def _finalize(
    *,
    run_dir: Path,
    selection: Mapping[str, Any],
    graph_regression: Mapping[str, Any],
    graph_holdout: Mapping[str, Any],
    model_records: Sequence[Mapping[str, Any]],
    call_records: Sequence[Mapping[str, Any]],
    validation_failures: Sequence[Mapping[str, Any]],
    before: Mapping[str, str],
    preflight_record: Mapping[str, Any],
    replayed_without_api: bool = False,
) -> Path:
    valid_predicates: list[dict[str, Any]] = []
    for model_record in model_records:
        if model_record.get("call_type") != "predicate_evaluation":
            continue
        validation = model_record.get("validation") or {}
        if validation.get("valid") is True:
            for row in (model_record.get("payload") or {}).get("predicates", []) or []:
                valid_predicates.append({"mention_id": model_record.get("mention_id"), **dict(row)})
    regression_initial = common.infer_graph(graph_regression, valid_predicates)
    holdout_initial = common.infer_graph(graph_holdout, valid_predicates)
    graph_all = [graph_regression, graph_holdout]
    reviewer_rows = [dict(row) for row in model_records if row.get("call_type") == "adversarial_review"]
    regression_final = common.apply_reviewer(regression_initial, reviewer_rows, graph_regression)
    holdout_final = common.apply_reviewer(holdout_initial, reviewer_rows, graph_holdout)
    lj0_decisions = _load_lj0_decisions()
    regression_comparison = common.compare_regression(regression_final, lj0_decisions, graph_regression)
    holdout_comparison = _holdout_comparison(holdout_initial, holdout_final)
    all_final = [*regression_final.get("records", []), *holdout_final.get("records", [])]
    safety = common.safety_metrics(graph_all, all_final, validation_failures)
    # A contradictory unordered pair is a diagnostic failure, not a source of
    # asymmetric links.  It is counted separately and never promoted.
    coref_conflicts = [
        *regression_initial.get("coreference_pair_conflicts", []),
        *holdout_initial.get("coreference_pair_conflicts", []),
    ]
    metrics = common.aggregate_metrics(
        regression_decisions=regression_final,
        holdout_decisions=holdout_final,
        initial_regression=regression_initial,
        initial_holdout=holdout_initial,
        reviewer_rows=reviewer_rows,
        call_records=call_records,
        validation_failures=validation_failures,
        graph_regression=graph_regression,
        graph_holdout=graph_holdout,
        lj0_decisions=lj0_decisions,
    )
    metrics.update({
        "selection_hash": selection.get("selection_hash"),
        "semantic_calls": len(call_records),
        "retries": sum(int(row.get("retry_count") or 0) for row in call_records),
        "provider_failures": sum(row.get("classification") == "provider_request_failure" for row in call_records),
        "parse_failures": sum(row.get("classification") == "response_parse_failure" for row in call_records),
        "truncated_responses": sum(row.get("classification") == "response_truncated" for row in call_records),
        "invalid_schema_payloads": sum(row.get("classification") == "parsed" and (row.get("validation") or {}).get("valid") is not True for row in model_records),
        "invalid_candidate_key_payloads": sum(
            any("candidate" in str(error).lower() and "invalid" in str(error).lower() for error in row.get("errors", []))
            for row in validation_failures
        ),
        "invalid_candidate_key_violations": sum(
            1
            for row in validation_failures
            for error in row.get("errors", [])
            if "candidate" in str(error).lower() and "invalid" in str(error).lower()
        ),
        "invalid_evidence_reference_payloads": sum(
            1
            for row in validation_failures
            for error in row.get("errors", [])
            if "evidence_reference_invalid" in str(error)
        ),
        "predicate_calls": sum(row.get("call_type") == "predicate_evaluation" for row in call_records),
        "reviewer_calls": sum(row.get("call_type") == "adversarial_review" for row in call_records),
        "coreference_pair_conflicts": len(coref_conflicts),
        "preflight": dict(preflight_record),
        "replayed_without_api": replayed_without_api,
        "safety_metrics": safety,
        "false_resolution_candidates": sum(int(safety.get(key) or 0) for key in (
            "same_surface_automatic_merges",
            "compositional_base_person_collapses",
            "nonperson_person_id_anomalies",
            "hard_veto_promotions",
            "invalid_candidate_keys",
            "invalid_evidence_references",
            "confidence_only_resolutions",
        )),
    })
    auto_resolved = []
    for group, document in (("regression", regression_final), ("holdout", holdout_final)):
        for row in document.get("records", []):
            if row.get("result_state") not in {"stable_entity_resolved", "local_candidate_resolved"}:
                continue
            auto_resolved.append({
                "group": group,
                "occurrence_id": row.get("occurrence_id"),
                "story_id": row.get("story_id"),
                "surface": row.get("surface"),
                "state": row.get("result_state"),
                "candidate": row.get("top_candidate"),
                "candidate_key": row.get("top_candidate_key"),
                "candidate_person_id": row.get("top_candidate_person_id"),
                "margin": row.get("margin"),
                "direct_identity_support": row.get("direct_identity_support"),
                "relational_support_families": row.get("relational_support_families", []),
                "collective_support_predicates": row.get("collective_support_predicates", []),
                "reviewer_resolved": bool(row.get("reviewer_resolved")),
                "candidate_only": True,
                "canonical_write_back": False,
            })
    auto_resolved.sort(key=lambda row: (str(row.get("group")), str(row.get("occurrence_id"))))
    after = protected_hashes()
    if dict(before) != after:
        raise RuntimeError("hdb2_psl1_protected_input_changed")
    common.write_json(run_dir / "model-predicate-results.json", {"records": list(model_records), "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "decisions-initial-regression.json", regression_initial)
    common.write_json(run_dir / "decisions-initial-holdout.json", holdout_initial)
    common.write_json(run_dir / "decisions-final-regression.json", regression_final)
    common.write_json(run_dir / "decisions-final-holdout.json", holdout_final)
    common.write_json(run_dir / "regression-comparison.json", regression_comparison)
    common.write_json(run_dir / "holdout-comparison.json", holdout_comparison)
    common.write_json(run_dir / "metrics.json", metrics)
    common.write_json(run_dir / "auto-resolved-cases.json", {"records": auto_resolved, "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "safety.json", safety)
    common.write_json(run_dir / "validation-failures.json", {"records": list(validation_failures), "candidate_only": True, "canonical_write_back": False})
    common.write_json(run_dir / "diagnostic-02-yanyu-054.json", diagnostic_yanyu(graph_regression, regression_final))
    common.write_json(run_dir / "validation-summary.json", {
        "schema": "hdb2-psl1-validation-summary-v1",
        "valid": not validation_failures and not metrics.get("false_resolution_candidates"),
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
        "postprocessing_replay_hash": common.stable_hash({
            "graph_regression": graph_regression,
            "graph_holdout": graph_holdout,
            "model_records": list(model_records),
            "final_regression": regression_final,
            "final_holdout": holdout_final,
        }),
    })
    common.write_json(run_dir / "manifest.json", manifest)
    return run_dir


def replay(run_dir: Path) -> Path:
    selection = common.read_json(run_dir / "selection.json", {}) or {}
    graph_regression = common.read_json(run_dir / "graph-regression.json", {}) or {}
    graph_holdout = common.read_json(run_dir / "graph-holdout.json", {}) or {}
    model_document = common.read_json(run_dir / "model-predicate-results.json", {}) or {}
    records = [dict(row) for row in model_document.get("records", [])]
    packets_document = common.read_json(run_dir / "prompt-packets.json", {}) or {}
    reviewer_packets_document = common.read_json(run_dir / "reviewer-packets.json", {}) or {}
    packets = {str(row.get("key")): row.get("packet") or {} for row in packets_document.get("records", [])}
    packets.update({str(row.get("key")): row.get("packet") or {} for row in reviewer_packets_document.get("records", [])})
    failures: list[dict[str, Any]] = []
    refreshed: list[dict[str, Any]] = []
    for row in records:
        if row.get("call_type") == "adversarial_review":
            packet = packets.get(f"review:{row.get('mention_id')}", {})
            validation = common.validate_reviewer(row.get("payload") or {}, packet) if packet else {"valid": False, "errors": ["review_packet_missing"]}
        elif row.get("classification") == "no_call":
            validation = {"valid": True, "errors": []}
        else:
            packet = packets.get(f"predicate:{row.get('mention_id')}", {})
            validation = common.validate_predicates(row.get("payload") or {}, packet) if packet else {"valid": False, "errors": ["predicate_packet_missing"]}
        row["validation"] = validation
        if validation.get("valid") is not True:
            failures.append({"mention_id": row.get("mention_id"), "call_type": row.get("call_type"), "errors": list(validation.get("errors", []))})
        refreshed.append(row)
    call_records = list((common.read_json(run_dir / "call-records.json", {}) or {}).get("records", []))
    manifest = common.read_json(run_dir / "manifest.json", {}) or {}
    before = manifest.get("protected_hashes_before") or protected_hashes()
    preflight_record = common.read_json(run_dir / "preflight.json", {}) or {}
    common.write_json(run_dir / "model-predicate-results.json", {"records": refreshed, "candidate_only": True, "canonical_write_back": False})
    return _finalize(
        run_dir=run_dir,
        selection=selection,
        graph_regression=graph_regression,
        graph_holdout=graph_holdout,
        model_records=refreshed,
        call_records=call_records,
        validation_failures=failures,
        before=before,
        preflight_record=preflight_record,
        replayed_without_api=True,
    )


def run(args: argparse.Namespace) -> Path:
    selection = common.freeze_experiment_selection(SELECTION_PATH, holdout_limit=args.holdout_limit)
    regression_input = common.load_regression_cases()
    holdout_input = common.load_holdout_cases({"holdout_cases": selection.get("holdout_cases", [])})
    graph_regression = common.build_graph_cases(regression_input)
    graph_holdout = common.build_graph_cases(holdout_input)
    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-HDB2-PSL1"
    run_dir = OUT_ROOT / "live" / run_id
    if run_dir.exists():
        raise RuntimeError(f"hdb2_psl1_run_exists:{run_dir}")
    raw_dir = run_dir / "raw-api"
    raw_dir.mkdir(parents=True, exist_ok=False)
    before = protected_hashes()
    all_cases: list[tuple[str, Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]] = []
    for group, graph in (("regression", graph_regression), ("holdout", graph_holdout)):
        for case in graph.get("cases", []):
            packet = common.wire_packet(case, graph.get("cases", []), graph)
            all_cases.append((group, case, graph, packet))
    packets = [
        {"key": f"predicate:{case.get('mention_id')}", "group": group, "packet": packet}
        for group, case, _graph, packet in all_cases
    ]
    common.write_json(run_dir / "selection.json", selection)
    common.write_json(run_dir / "graph-regression.json", graph_regression)
    common.write_json(run_dir / "graph-holdout.json", graph_holdout)
    common.write_json(run_dir / "prompt-packets.json", {"records": packets, "candidate_only": True, "canonical_write_back": False})
    preflight_record = preflight()
    common.write_json(run_dir / "preflight.json", preflight_record)
    manifest = {
        "schema": "hdb2-psl1-live-manifest-v1",
        "run_id": run_id,
        "run_version": common.RUN_VERSION,
        "prompt_version": common.PROMPT_VERSION,
        "review_prompt_version": common.REVIEW_PROMPT_VERSION,
        "model": common.MODEL,
        "temperature": 0,
        "thinking": "disabled",
        "endpoint": common.STRICT_ENDPOINT,
        "selection_hash": selection.get("selection_hash"),
        "regression_count": len(graph_regression.get("cases", [])),
        "holdout_count": len(graph_holdout.get("cases", [])),
        "candidate_only": True,
        "canonical_write_back": False,
        "hdb2_decisions_modified": False,
        "protected_hashes_before": before,
        "preflight": preflight_record,
        "created_at": utc_now(),
    }
    common.write_json(run_dir / "manifest.json", manifest)
    if preflight_record.get("status") != "reachable":
        common.write_json(run_dir / "call-records.json", {"records": [], "candidate_only": True, "canonical_write_back": False})
        return _finalize(
            run_dir=run_dir,
            selection=selection,
            graph_regression=graph_regression,
            graph_holdout=graph_holdout,
            model_records=[],
            call_records=[],
            validation_failures=[],
            before=before,
            preflight_record=preflight_record,
        )
    model_records: list[dict[str, Any]] = []
    call_records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    sequence = 0
    for group, case, graph, packet in all_cases:
        if not packet.get("request_predicates"):
            row = _neutral_model_record(case, "no_requested_llm_predicates")
            row["group"] = group
            model_records.append(row)
            continue
        sequence += 1
        call_record, model_record, failure = _call_tool(
            packet=packet,
            sequence=sequence,
            call_type="predicate_evaluation",
            system_prompt=common.SYSTEM_PROMPT,
            tool=common.predicate_tool(),
            choice=common.tool_choice(),
            expected_function=common.FUNCTION_NAME,
            prompt_version=common.PROMPT_VERSION,
            raw_dir=raw_dir,
            validator=common.validate_predicates,
        )
        call_record["group"] = group
        model_record["group"] = group
        call_records.append(call_record)
        model_records.append(model_record)
        if failure:
            failures.append(failure)
    # First pass is now complete.  Reviewer packets depend on the frozen
    # initial graph ranking, never on reviewer output.
    valid_predicates = [
        {"mention_id": row.get("mention_id"), **dict(predicate)}
        for row in model_records
        if row.get("call_type") == "predicate_evaluation"
        and (row.get("validation") or {}).get("valid") is True
        for predicate in ((row.get("payload") or {}).get("predicates", []) or [])
    ]
    initial_regression = common.infer_graph(graph_regression, valid_predicates)
    initial_holdout = common.infer_graph(graph_holdout, valid_predicates)
    initial_by_id = {str(row.get("mention_id")): row for row in [*initial_regression.get("records", []), *initial_holdout.get("records", [])]}
    graph_by_id = {str(row.get("mention_id")): (row, graph_regression if row in graph_regression.get("cases", []) else graph_holdout) for row in [*graph_regression.get("cases", []), *graph_holdout.get("cases", [])]}
    reviewer_packets: list[dict[str, Any]] = []
    reviewer_cases: list[tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]] = []
    for group, case, graph, _packet in all_cases:
        decision = initial_by_id.get(str(case.get("mention_id")))
        if decision and decision.get("result_state") == "review_required":
            packet = common.reviewer_packet(case, graph.get("cases", []), graph, decision)
            reviewer_packets.append({"key": f"review:{case.get('mention_id')}", "group": group, "packet": packet})
            reviewer_cases.append((case, graph, packet))
    common.write_json(run_dir / "reviewer-packets.json", {"records": reviewer_packets, "candidate_only": True, "canonical_write_back": False})
    for case, graph, packet in reviewer_cases:
        sequence += 1
        call_record, model_record, failure = _call_tool(
            packet=packet,
            sequence=sequence,
            call_type="adversarial_review",
            system_prompt=common.REVIEW_SYSTEM_PROMPT,
            tool=common.reviewer_tool(),
            choice=common.reviewer_tool_choice(),
            expected_function=common.REVIEW_FUNCTION_NAME,
            prompt_version=common.REVIEW_PROMPT_VERSION,
            raw_dir=raw_dir,
            validator=common.validate_reviewer,
        )
        model_record["group"] = "regression" if graph is graph_regression else "holdout"
        call_record["group"] = model_record["group"]
        call_records.append(call_record)
        model_records.append(model_record)
        if failure:
            failures.append(failure)
    common.write_json(run_dir / "call-records.json", {"records": call_records, "candidate_only": True, "canonical_write_back": False})
    return _finalize(
        run_dir=run_dir,
        selection=selection,
        graph_regression=graph_regression,
        graph_holdout=graph_holdout,
        model_records=model_records,
        call_records=call_records,
        validation_failures=failures,
        before=before,
        preflight_record=preflight_record,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id")
    parser.add_argument("--holdout-limit", type=int, default=20)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()
    if args.replay:
        replay(args.replay if args.replay.is_absolute() else ROOT / args.replay)
        return 0
    if args.prepare_only:
        selection = common.freeze_experiment_selection(SELECTION_PATH, holdout_limit=args.holdout_limit)
        regression = common.load_regression_cases()
        holdout = common.load_holdout_cases({"holdout_cases": selection.get("holdout_cases", [])})
        print(json.dumps({
            "selection": str(SELECTION_PATH.relative_to(ROOT)),
            "selection_hash": selection.get("selection_hash"),
            "regression_cases": len(regression.get("cases", [])),
            "holdout_cases": len(holdout.get("cases", [])),
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
